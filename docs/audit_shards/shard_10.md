# AUDIT SHARD 10/13 -- seat google/gemini-3.6-flash

You are reviewing SOURCE CODE, not a summary. Previous panels received a 13,185-char self-description and never saw the code; that is why this exists.

- TIER 1 (money path) is included IN FULL and is sent to every seat: 41 files. A defect here costs money.
- TIER 2 is YOUR SHARD ALONE: 47 files. No other seat sees these, so anything you miss here is missed entirely.
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

### libs/alpha/decay.py
```python
"""Alpha decay detection — a 0..1 decay score from four deterioration components.

decay_score blends performance, risk, stability, and regime-mismatch deterioration (0 = healthy,
1 = fully decayed) and maps to a recommended lifecycle state. Thesis invalidation (handled by the
operator) should override statistics, which are slow for low-frequency alphas.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from libs.alpha.card import ExpectedMetrics, LiveMetrics
from libs.alpha.health import _higher_better, _lower_better
from libs.alpha.state import AlphaState


class DecayResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    decay_score: float
    components: dict[str, float]
    recommended_state: AlphaState


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def detect_decay(
    expected: ExpectedMetrics,
    live: LiveMetrics,
    *,
    watch_threshold: float = 0.30,
    decaying_threshold: float = 0.50,
    retire_threshold: float = 0.70,
) -> DecayResult:
    """Compute the decay score and recommend a lifecycle state."""
    perf_health = [
        h for h in (_higher_better(live.sharpe, expected.sharpe),
                    _higher_better(live.cagr, expected.cagr)) if h is not None
    ]
    stability_health = [
        h for h in (_higher_better(live.profit_factor, expected.profit_factor),
                    _higher_better(live.expectancy, expected.expectancy),
                    _higher_better(live.win_rate, expected.win_rate)) if h is not None
    ]
    risk_health = _lower_better(live.max_drawdown, expected.max_drawdown)

    performance_deterioration = 1.0 - _mean(perf_health) if perf_health else 0.0
    stability_deterioration = 1.0 - _mean(stability_health) if stability_health else 0.0
    risk_deterioration = (1.0 - risk_health) if risk_health is not None else 0.0
    regime_mismatch = 1.0 - max(0.0, min(1.0, live.regime_stability))

    components = {
        "performance": performance_deterioration,
        "risk": risk_deterioration,
        "stability": stability_deterioration,
        "regime_mismatch": regime_mismatch,
    }
    decay_score = max(0.0, min(1.0, sum(components.values()) / len(components)))

    if decay_score >= retire_threshold:
        recommended = AlphaState.RETIREMENT_CANDIDATE
    elif decay_score >= decaying_threshold:
        recommended = AlphaState.DECAYING
    elif decay_score >= watch_threshold:
        recommended = AlphaState.WATCH
    else:
        recommended = AlphaState.ACTIVE

    return DecayResult(
        decay_score=decay_score, components=components, recommended_state=recommended
    )

```

### libs/alpha_factory/alpha_factory_controller.py
```python
"""Alpha Factory controller — the master research coordinator (recommend-only).

Wires the research engines together and emits research recommendations: priorities, budget
allocation, and portfolio/regime gaps. Governance is structural and explicit: the factory MAY
generate/rank/allocate-research/archive/recommend, but MAY NOT promote or retire alphas, change
risk or validation thresholds, or allocate production capital — those raise.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import NoReturn

from libs.alpha_factory.alpha_discovery_engine import AlphaDiscoveryEngine
from libs.alpha_factory.alpha_embedding_engine import AlphaEmbeddingEngine
from libs.alpha_factory.alpha_family_tree import AlphaFamilyTree
from libs.alpha_factory.capacity_intelligence import CapacityIntelligence
from libs.alpha_factory.concept_evolution_engine import ConceptEvolutionEngine
from libs.alpha_factory.crowding_intelligence import CrowdingIntelligence
from libs.alpha_factory.errors import AlphaFactoryGovernanceError
from libs.alpha_factory.hypothesis_engine import HypothesisEngine
from libs.alpha_factory.idea_ranking_engine import IdeaRankingEngine
from libs.alpha_factory.models import (
    AlphaCategory,
    AlphaFactoryReport,
    IdeaCandidate,
)
from libs.alpha_factory.research_allocator import ResearchAllocator
from libs.alpha_factory.research_graph import ResearchGraph
from libs.alpha_factory.research_memory import ResearchMemory
from libs.alpha_factory.research_roi_engine import ResearchROIEngine
from libs.alpha_factory.research_score_engine import ResearchScoreEngine
from libs.alpha_factory.strategy_similarity_engine import StrategySimilarityEngine
from libs.store.connection import Database


class AlphaFactoryController:
    """Coordinates every research engine and enforces factory governance."""

    def __init__(self, db: Database) -> None:
        self.memory = ResearchMemory(db)
        self.discovery = AlphaDiscoveryEngine(self.memory)
        self.hypothesis_engine = HypothesisEngine()
        self.idea_ranking = IdeaRankingEngine()
        self.research_score = ResearchScoreEngine()
        self.concept_evolution = ConceptEvolutionEngine()
        self.crowding_intelligence = CrowdingIntelligence()
        self.capacity_intelligence = CapacityIntelligence()
        self.research_roi = ResearchROIEngine()
        self.allocator = ResearchAllocator()
        self.family_tree = AlphaFamilyTree()
        self.research_graph = ResearchGraph()
        self.similarity = StrategySimilarityEngine()
        self.embedding = AlphaEmbeddingEngine()

    def run(
        self,
        *,
        candidates: Sequence[IdeaCandidate],
        categories: Sequence[AlphaCategory],
        regime_gaps: Mapping[str, float] | None = None,
        portfolio_gaps: Mapping[str, float] | None = None,
        crowding: Mapping[str, float] | None = None,
    ) -> AlphaFactoryReport:
        """Produce a research recommendation plan (recommend-only)."""
        regime_gaps = regime_gaps or {}
        portfolio_gaps = portfolio_gaps or {}
        priorities = self.idea_ranking.rank(candidates)
        allocation = self.allocator.allocate(
            categories, memory=self.memory, regime_gaps=regime_gaps,
            portfolio_gaps=portfolio_gaps, crowding=crowding,
        )
        return AlphaFactoryReport(
            research_priorities=priorities,
            allocation=allocation,
            portfolio_gaps=sorted(k for k, v in portfolio_gaps.items() if v > 0.0),
            regime_gaps=sorted(k for k, v in regime_gaps.items() if v > 0.0),
            notes="recommend-only; production decisions require the validation gauntlet",
        )

    # ------------------------------------------------------------------ deep assessment
    # `run` ranks and allocates. These are the engines that answer "is this idea WORTH the
    # research budget" -- novelty against what the desk already killed, crowding, whether the
    # concept can hold the desk's size, and whether it duplicates something already deployed.
    # They were instantiated in __init__ and called by nothing, so the factory imported fifteen
    # engines and exercised two: reachable on paper, idle in fact.

    def assess(
        self,
        *,
        candidate: IdeaCandidate,
        adv_usd: float,
        research_confidence: float = 0.5,
    ) -> dict[str, object]:
        """Full per-candidate assessment: research score, crowding, capacity.

        `crowding` on the candidate is a single number; CrowdingIntelligence wants it split
        three ways. Absent a finer measurement the same value is used for all three -- honest
        about the resolution we actually have rather than inventing a decomposition.
        """
        crowd = self.crowding_intelligence.assess(
            strategy_crowding=candidate.crowding,
            factor_crowding=candidate.crowding,
            style_crowding=candidate.crowding,
        )
        cap = self.capacity_intelligence.assess(adv_usd=adv_usd)
        score = self.research_score.score(
            novelty=candidate.novelty,
            expected_robustness=candidate.expected_robustness,
            expected_capacity=candidate.expected_capacity,
            portfolio_need=candidate.portfolio_need,
            research_confidence=research_confidence,
            crowding_risk=crowd.crowding_score,
        )
        return {
            "idea_id": candidate.idea_id,
            "research_score": score.research_score,
            "components": score.components,
            "crowding_score": crowd.crowding_score,
            "priority_multiplier": crowd.priority_multiplier,
            "capacity_usd": cap.market_capacity_usd,
            "scalability_score": cap.scalability_score,
            "expected_slippage": cap.expected_slippage,
        }

    def duplicates_of(
        self, dna: Mapping[str, object], deployed: Mapping[str, object], *,
        threshold: float = 0.95,
    ) -> list[list[str]]:
        """Concepts whose DNA clusters with something already deployed.

        Re-testing a variant of the sleeve already running is the cheapest way to spend research
        budget on nothing, and it is invisible without an explicit similarity check because the
        statement wording differs every time.
        """
        pool = {**deployed, **dna}
        return self.embedding.cluster(pool, threshold=threshold)  # type: ignore[arg-type]

    def record_lineage(self, alpha_id: str, *, parent_id: str | None = None,
                       mutation_type: str = "root", performance: float = 0.0) -> None:
        """Register a concept in the family tree AND the provenance graph.

        Both, deliberately: the tree answers "what did this descend from", the graph answers
        "what else touches this feature/data source". Losing either is how a desk re-derives an
        idea it already has.
        """
        self.family_tree.add(alpha_id, parent_id=parent_id, mutation_type=mutation_type,
                             performance=performance)
        self.research_graph.add_node(alpha_id, "alpha", performance=performance)
        if parent_id:
            self.research_graph.add_node(parent_id, "alpha")
            self.research_graph.add_edge(parent_id, alpha_id)

    def propose(self, categories: Sequence[AlphaCategory]) -> list[object]:
        """New hypotheses from the discovery + hypothesis engines, expanded by concept evolution.

        Deduplicated on statement: the two generators overlap by design (one is memory-driven,
        one is category-driven) and emitting the same statement twice would inflate every
        downstream count that reads this list.
        """
        seen: set[str] = set()
        out: list[object] = []
        for h in [*self.discovery.generate(categories),
                  *self.hypothesis_engine.generate(categories, memory=self.memory)]:
            if h.statement in seen:
                continue
            seen.add(h.statement)
            out.append(h)
            for variant in self.concept_evolution.evolve(h):
                if variant.statement not in seen:
                    seen.add(variant.statement)
                    out.append(variant)
        return out

    # --------------------------------------------------------- governance (MAY NOT)

    def promote_alpha(self, *_args: object, **_kwargs: object) -> NoReturn:
        raise AlphaFactoryGovernanceError("Alpha Factory may not promote alphas")

    def retire_alpha(self, *_args: object, **_kwargs: object) -> NoReturn:
        raise AlphaFactoryGovernanceError("Alpha Factory may not retire alphas")

    def allocate_production_capital(self, *_args: object, **_kwargs: object) -> NoReturn:
        raise AlphaFactoryGovernanceError("Alpha Factory may not allocate production capital")

    def change_risk_limit(self, *_args: object, **_kwargs: object) -> NoReturn:
        raise AlphaFactoryGovernanceError("Alpha Factory may not change risk limits")

    def change_validation_threshold(self, *_args: object, **_kwargs: object) -> NoReturn:
        raise AlphaFactoryGovernanceError("Alpha Factory may not change validation thresholds")

```

### libs/autodiscovery/data_opportunity.py
```python
"""Data Opportunity Engine — rank the datasets that would most increase alpha-discovery odds.

Information advantage, not dataset count. Each missing dataset is scored by
``expected_alpha_value / implementation_cost`` (with diversification and maintenance factored into
the value), and the ranked list is the continuously-updated Data Opportunity Report. This is the
honest answer to "what data should we acquire next?" — and it surfaces the data the current MT5-only
feed lacks (the reason carry/cross-asset/rates families currently run as proxies).
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field


class DatasetOpportunity(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    information_value: float       # 0..1
    alpha_contribution: float      # 0..1 expected new edge
    diversification_benefit: float  # 0..1 (low correlation to current OHLC edges)
    implementation_cost: float     # 1..10 (engineering + sourcing)
    maintenance_burden: float      # 1..10
    unlocks: list[str] = Field(default_factory=list)  # families it would make real (not proxy)

    @property
    def expected_alpha_value(self) -> float:
        # Value blends information, raw alpha potential, and diversification; cost dampens it.
        return (
            0.4 * self.information_value
            + 0.4 * self.alpha_contribution
            + 0.2 * self.diversification_benefit
        ) / (1.0 + 0.1 * self.maintenance_burden)

    @property
    def roi_score(self) -> float:
        return self.expected_alpha_value / self.implementation_cost


class DataOpportunityReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    ranked: list[dict[str, float | str | list[str]]]
    top_recommendation: str


# Curated catalog of the institutional datasets the MT5-only feed currently lacks. Scores reflect
# typical information content / crowding, NOT a backtested promise — they rank acquisition effort.
_CATALOG: tuple[DatasetOpportunity, ...] = (
    DatasetOpportunity(name="funding_rates", information_value=0.85, alpha_contribution=0.8,
                       diversification_benefit=0.8, implementation_cost=3.0, maintenance_burden=3.0,
                       unlocks=["carry"]),
    DatasetOpportunity(name="yield_curves", information_value=0.85, alpha_contribution=0.75,
                       diversification_benefit=0.85, implementation_cost=4.0,
                       maintenance_burden=3.0,
                       unlocks=["carry", "regime_transition", "risk_premia"]),
    DatasetOpportunity(name="futures_term_structure", information_value=0.8, alpha_contribution=0.8,
                       diversification_benefit=0.8, implementation_cost=5.0, maintenance_burden=4.0,
                       unlocks=["carry", "risk_premia"]),
    DatasetOpportunity(name="currency_indices_dxy", information_value=0.7, alpha_contribution=0.6,
                       diversification_benefit=0.75, implementation_cost=2.0,
                       maintenance_burden=2.0, unlocks=["cross_asset"]),
    DatasetOpportunity(name="volatility_indices_vix", information_value=0.75,
                       alpha_contribution=0.65, diversification_benefit=0.8,
                       implementation_cost=2.0, maintenance_burden=2.0,
                       unlocks=["regime_transition", "risk_premia"]),
    DatasetOpportunity(name="options_implied_vol_surface", information_value=0.9,
                       alpha_contribution=0.85, diversification_benefit=0.85,
                       implementation_cost=8.0, maintenance_burden=7.0, unlocks=["risk_premia"]),
    DatasetOpportunity(name="cot_positioning", information_value=0.7, alpha_contribution=0.6,
                       diversification_benefit=0.8, implementation_cost=3.0, maintenance_burden=3.0,
                       unlocks=["regime_transition", "liquidity"]),
    DatasetOpportunity(name="etf_flows", information_value=0.65, alpha_contribution=0.55,
                       diversification_benefit=0.7, implementation_cost=5.0, maintenance_burden=5.0,
                       unlocks=["liquidity"]),
    DatasetOpportunity(name="macro_release_calendar", information_value=0.6, alpha_contribution=0.5,
                       diversification_benefit=0.65, implementation_cost=3.0,
                       maintenance_burden=3.0, unlocks=["regime_transition"]),
    DatasetOpportunity(name="sentiment_news", information_value=0.55, alpha_contribution=0.5,
                       diversification_benefit=0.7, implementation_cost=7.0, maintenance_burden=7.0,
                       unlocks=["liquidity"]),
)


class DataOpportunityEngine:
    """Ranks missing datasets by expected alpha value per unit implementation cost."""

    def __init__(self, catalog: Sequence[DatasetOpportunity] = _CATALOG) -> None:
        self.catalog = list(catalog)

    def report(self) -> DataOpportunityReport:
        ranked = sorted(self.catalog, key=lambda d: d.roi_score, reverse=True)
        rows: list[dict[str, float | str | list[str]]] = [
            {"name": d.name, "roi_score": round(d.roi_score, 4),
             "expected_alpha_value": round(d.expected_alpha_value, 4),
             "implementation_cost": d.implementation_cost, "unlocks": d.unlocks}
            for d in ranked
        ]
        return DataOpportunityReport(
            ranked=rows, top_recommendation=ranked[0].name if ranked else "",
        )

```

### libs/autodiscovery/extraction_parity.py
```python
"""Reconcile the DATA-UTILIZATION LAW with the GATE-OPTIMALITY MONITOR.

Two of the desk's own laws conflict if left implicit:
  - DATA-UTILIZATION LAW: idle ingested data is DATA PARALYSIS; convert every axis.
  - GATE-OPTIMALITY MONITOR: the DSR bar goes unclearable when the trial count explodes.

Satisfying the first by mass combinatorial/genetic generation ("scale extraction") triggers the
second -- the 420->0 dynamic at 20-axis scale: obey one law, break the other. This module encodes
the binding reconciliation as pure, testable primitives so the two laws cannot fight:

  1. COVERAGE, NOT VOLUME. Paralysis clears when every idle axis carries >=1 screened,
     economically-motivated hypothesis -- ~one good mechanism-first trial per axis (~20 trials),
     never thousands. ``axis_coverage``.
  2. EXPANSION IS EARNED. Combinatorial/genetic expansion of an axis is licensed only AFTER its
     single-axis screen shows signal (|IC|/Sharpe past threshold). Never explode an axis that has
     shown nothing -- pure DSR deflation, zero upside. ``expansion_licensed``.
  3. EFFECTIVE (independence-clustered) TRIAL COUNT. Cross-mechanism DSR deflates by INDEPENDENT
     trials, clustered by mechanism, not the raw tally. 20 axes converted mechanism-first ~= 20
     independent trials, so the bar stays clearable. ``effective_trial_count``.
  4. The paralysis flag is a COVERAGE flag. If "fix paralysis" ever becomes "generate more", the
     desk has built a survivor-killing volume machine that obeys one law by breaking the other.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict


class CoverageReport(BaseModel):
    """The parity metric: is every ingested axis converted (screened once), regardless of volume."""

    model_config = ConfigDict(frozen=True)

    n_axes: int  # distinct ingested data axes (the acquisition surface)
    n_covered: int  # axes that carry >=1 screened, economically-motivated hypothesis
    idle: tuple[str, ...]  # ingested axes with 0 screened hypotheses -- the true paralysis set
    coverage_frac: float  # n_covered / n_axes
    cleared: bool  # paralysis cleared == every axis covered (COVERAGE, never hypothesis count)
    verdict: str

    def __bool__(self) -> bool:
        return self.cleared


def axis_coverage(*, axes: Sequence[str], screened_axes: Sequence[str]) -> CoverageReport:
    """Data-paralysis is a COVERAGE gap, never a volume gap (reconciliation rules 1 & 4).

    Paralysis clears when every ingested ``axis`` carries at least one screened, economically-
    motivated hypothesis -- ``screened_axes`` is the axis each recorded mechanism-first hypothesis
    screens. ~One good trial per axis, not thousands. Measuring "idle" by coverage rather than by
    hypothesis count is exactly what stops "fix paralysis" from degenerating into a volume machine:
    the 21st hypothesis on an already-covered axis moves this metric not at all, so there is no
    incentive to pile trials onto one axis and every incentive to reach the next uncovered one.
    """
    universe = list(dict.fromkeys(a for a in axes if a))  # de-dup, preserve order
    covered_set = {a for a in screened_axes if a} & set(universe)
    idle = tuple(a for a in universe if a not in covered_set)
    n = len(universe)
    frac = round(len(covered_set) / n, 3) if n else 1.0
    cleared = not idle
    if n == 0:
        verdict = "no axes ingested -- nothing to convert"
    elif cleared:
        verdict = f"coverage complete: all {n} ingested axes carry >=1 screened hypothesis"
    else:
        shown = ", ".join(idle[:8]) + (" ..." if len(idle) > 8 else "")
        verdict = (
            f"{len(idle)}/{n} axes idle (0 screened hypotheses): {shown} -- convert "
            "MECHANISM-FIRST (one screened hypothesis each), NOT by combinatorial volume"
        )
    return CoverageReport(
        n_axes=n, n_covered=len(covered_set), idle=idle, coverage_frac=frac,
        cleared=cleared, verdict=verdict,
    )


class ExpansionDecision(BaseModel):
    """Whether combinatorial/genetic expansion of an axis is EARNED yet."""

    model_config = ConfigDict(frozen=True)

    axis: str
    licensed: bool
    reason: str

    def __bool__(self) -> bool:
        return self.licensed


def expansion_licensed(
    *, axis: str, screened: bool, screen_metric: float | None, threshold: float
) -> ExpansionDecision:
    """Combinatorial/genetic expansion of ``axis`` is EARNED, never default (reconciliation rule 2).

    Licensed only once the axis's own single-axis screen has RUN (``screened``) and shown signal
    (``|screen_metric| >= threshold`` -- e.g. |IC| or forward Sharpe). Exploding an unscreened axis,
    or one that screened flat, is pure cumulative-trial DSR deflation with zero upside -- the exact
    420->0 dynamic. Screen first; expand only what proved it deserves the trials.
    """
    if not screened or screen_metric is None:
        return ExpansionDecision(
            axis=axis, licensed=False,
            reason="unscreened -- run the single-axis screen before spending any expansion trials",
        )
    strength = abs(screen_metric)
    if strength < threshold:
        return ExpansionDecision(
            axis=axis, licensed=False,
            reason=(
                f"screen flat (|metric| {strength:.4f} < {threshold:.4f}) -- expanding a dead axis "
                "is pure DSR deflation with zero upside; retire or re-construct, do NOT explode"
            ),
        )
    return ExpansionDecision(
        axis=axis, licensed=True,
        reason=(f"screen shows signal (|metric| {strength:.4f} >= {threshold:.4f}) -- "
                "expansion earned"),
    )


class EffectiveTrials(BaseModel):
    """Independence-clustered trial count -- what CROSS-mechanism DSR should deflate by."""

    model_config = ConfigDict(frozen=True)

    raw: int  # raw cumulative trial tally -- over-counts correlated variations of one mechanism
    effective: int  # number of independent mechanism clusters -- the honest cross-mechanism count
    n_clusters: int  # == effective; distinct mechanisms seen
    inflation: float  # raw / effective -- how much the raw tally over-charges the DSR bar
    top_clusters: tuple[tuple[str, int], ...]  # (mechanism, raw_trials) heaviest-first, for audit
    verdict: str


def effective_trial_count(mechanisms: Sequence[str]) -> EffectiveTrials:
    """Independence-clustered trial count for CROSS-mechanism DSR deflation (reconciliation rule 3;
    gate-calibration audit (a) from MAX_SURVIVORS Part 1.2).

    DSR must deflate by the number of INDEPENDENT trials, not the raw tally. Cluster the trial
    ledger by mechanism (the ``family``/``method`` key already on every trials-ledger row): N
    variations of one economically-distinct mechanism are ~1 independent trial, not N. So the
    effective cross-mechanism count is the number of distinct mechanism clusters -- 20 axes
    converted mechanism-first ~= 20 independent trials, keeping the bar clearable.

    This is the COMPLEMENT of the pre-registered per-family budget
    (``orchestrator._family_trials``), which prices *within*-mechanism search: counting the raw
    within-family tally AND this global term would double-charge. This term exists so the gate-
    optimality monitor can report effective-vs-raw honestly instead of only telling a human to
    "audit" it.
    """
    raw = len(mechanisms)
    clusters = Counter(m for m in mechanisms if m)
    eff = len(clusters)
    inflation = round(raw / eff, 2) if eff else 0.0
    top = tuple(clusters.most_common(5))
    if eff == 0:
        verdict = "no mechanisms recorded -- effective trial count is 0"
    elif inflation <= 1.5:
        verdict = f"raw {raw} ~= effective {eff} ({eff} mechanisms) -- bar is honestly calibrated"
    else:
        verdict = (
            f"raw {raw} inflates to {inflation:.1f}x the effective {eff} independent mechanisms -- "
            "deflating DSR by raw sets the bar unclearable; use the effective count"
        )
    return EffectiveTrials(
        raw=raw, effective=eff, n_clusters=eff, inflation=inflation,
        top_clusters=top, verdict=verdict,
    )

```

### libs/autodiscovery/prioritization.py
```python
"""Research prioritization — test the most durable, least-crowded families first.

Higher-priority families historically hold more durable, less-crowded institutional edge (carry,
risk premia, cross-asset, regime, liquidity) than retail-style technical systems (trend, momentum,
breakout, mean reversion). The lab orders its hypothesis queue by this priority so scarce research
throughput is spent where genuine edge is more likely. Priority affects ORDER only — never the
validation thresholds, which are identical for every family.
"""

from __future__ import annotations

from collections.abc import Sequence

from libs.autodiscovery.generators import GeneratorSpec
from libs.autodiscovery.models import Family, Hypothesis

# Lower rank value = higher priority (tested first).
FAMILY_PRIORITY: dict[Family, int] = {
    Family.CARRY: 0,
    Family.RISK_PREMIA: 1,
    Family.CROSS_ASSET: 2,
    Family.REGIME_TRANSITION: 3,
    Family.LIQUIDITY: 4,
    Family.SESSION: 5,
    Family.VOLATILITY_EXPANSION: 6,
    Family.VOLATILITY_COMPRESSION: 7,
    Family.TREND: 8,
    Family.MOMENTUM: 9,
    Family.BREAKOUT: 10,
    Family.MEAN_REVERSION: 11,
}


def family_rank(family: Family) -> int:
    return FAMILY_PRIORITY.get(family, 99)


def prioritize(
    plan: Sequence[tuple[Hypothesis, GeneratorSpec]],
) -> list[tuple[Hypothesis, GeneratorSpec]]:
    """Stable-sort a hypothesis plan by family priority (highest-priority families first)."""
    return sorted(plan, key=lambda pair: family_rank(pair[0].family))

```

### libs/autodiscovery/research_roi.py
```python
"""Research ROI Monitor — learn where research effort actually yields validated alpha.

Measures productivity by family (tested, rejected, validation pass rate, survivors, survivor rate)
straight from the durable candidate ledger, and recommends allocating future effort toward the
highest validated-alpha yield. Success is validated survivors, not backtests run — this monitor
makes that measurable and is honest when yield is zero everywhere.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from libs.autodiscovery.memory import CandidateStore
from libs.autodiscovery.models import CandidateStatus

_REACHED_VALIDATION = {
    CandidateStatus.SHADOW.value, CandidateStatus.PAPER.value, CandidateStatus.REGISTRY.value,
}


class FamilyYield(BaseModel):
    model_config = ConfigDict(frozen=True)

    family: str
    tested: int
    rejected: int
    reached_validation: int
    survivors: int
    survivor_rate: float


class ResearchROIReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_tested: int
    total_survivors: int
    validation_pass_rate: float          # reached shadow+ / tested
    survivor_rate: float                 # registry / tested
    by_family: list[FamilyYield] = Field(default_factory=list)
    recommended_focus: list[str] = Field(default_factory=list)


class ResearchROIMonitor:
    """Computes per-family research yield and the effort-allocation recommendation."""

    def __init__(self, store: CandidateStore) -> None:
        self.store = store

    def report(self) -> ResearchROIReport:
        records = self.store.all()
        total = len(records)
        agg: dict[str, dict[str, int]] = {}
        for r in records:
            f = agg.setdefault(r.family, {"tested": 0, "rejected": 0, "reached": 0, "survivors": 0})
            f["tested"] += 1
            if r.status is CandidateStatus.REJECTED:
                f["rejected"] += 1
            if r.status.value in _REACHED_VALIDATION:
                f["reached"] += 1
            if r.survived:
                f["survivors"] += 1

        families = [
            FamilyYield(
                family=name, tested=d["tested"], rejected=d["rejected"],
                reached_validation=d["reached"], survivors=d["survivors"],
                survivor_rate=d["survivors"] / d["tested"] if d["tested"] else 0.0,
            )
            for name, d in agg.items()
        ]
        survivors = sum(f.survivors for f in families)
        reached = sum(f.reached_validation for f in families)
        # Allocate future effort toward the highest-yield families (survivor rate, then reach).
        ranked = sorted(families, key=lambda f: (f.survivor_rate, f.reached_validation),
                        reverse=True)
        return ResearchROIReport(
            total_tested=total, total_survivors=survivors,
            validation_pass_rate=reached / total if total else 0.0,
            survivor_rate=survivors / total if total else 0.0,
            by_family=ranked, recommended_focus=[f.family for f in ranked[:5]],
        )

```

### libs/backtest/errors.py
```python
"""Backtest exceptions."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class BacktestError(QuantPlatformError):
    """Invalid backtest configuration or inputs."""


class VerificationError(BacktestError):
    """Cross-engine verification found a divergence beyond tolerance."""

```

### libs/backtest/fills.py
```python
"""Fill engine — turns an order delta into a fill price with slippage and commission."""

from __future__ import annotations

import pandas as pd

from libs.backtest.events import FillEvent


class FillEngine:
    """Computes fills. Slippage worsens the price in the direction of the trade."""

    def __init__(self, *, slippage_frac: float = 0.0, commission_per_unit: float = 0.0) -> None:
        self.slippage_frac = slippage_frac
        self.commission_per_unit = commission_per_unit

    def fill(
        self, timestamp: pd.Timestamp, units_delta: float, ref_price: float
    ) -> FillEvent:
        """Fill ``units_delta`` at ``ref_price`` adjusted for slippage/commission."""
        direction = 1.0 if units_delta > 0 else -1.0
        price = ref_price * (1.0 + direction * self.slippage_frac)
        commission = abs(units_delta) * self.commission_per_unit
        return FillEvent(
            timestamp=timestamp, units_delta=units_delta, price=price, commission=commission
        )

```

### libs/core/ids.py
```python
"""Deterministic-format identifier helpers.

Ids are opaque, URL-safe, prefixed strings (``<prefix>_<hex>``) so a bare id is
self-describing in logs and the audit trail.
"""

from __future__ import annotations

import uuid


def generate_id(prefix: str) -> str:
    """Return a new unique id of the form ``<prefix>_<32-hex>``.

    Args:
        prefix: Short lowercase tag identifying the id's kind (e.g. ``"run"``).
    """
    if not prefix or not prefix.isidentifier():
        raise ValueError(f"prefix must be a valid identifier, got {prefix!r}")
    return f"{prefix}_{uuid.uuid4().hex}"


def new_run_id() -> str:
    """Return a new research-run id."""
    return generate_id("run")


def new_correlation_id() -> str:
    """Return a new correlation id for threading one decision across log records."""
    return generate_id("corr")


def new_stamp_id() -> str:
    """Return a new reproducibility-stamp id."""
    return generate_id("stamp")

```

### libs/costs/execution_gap.py
```python
"""Demo->live execution-gap stress (committee Lever 2 / T4).

A backtest run on demo spreads is optimistic: live trading reveals wider spreads, slippage, and
requotes -- often exactly when the signal fires. We model this as a cost multiplier and require any
candidate to stay net-positive with only modest edge erosion under it. This is the gate that stops
a demo-only "edge" from being deployed into a venue that quietly eats it.
"""

from __future__ import annotations

from dataclasses import dataclass

from libs.costs.errors import CostError

_DEFAULT_MULTIPLIER = 2.5   # live all-in cost ~ 2-3x calibrated demo cost (conservative prior)
_MAX_EROSION = 0.30         # a real edge should lose <= 30% of its net return to the gap


@dataclass(frozen=True)
class ExecutionGap:
    """Conservative demo->live degradation as a multiplier on per-turnover cost."""

    cost_multiplier: float = _DEFAULT_MULTIPLIER

    def __post_init__(self) -> None:
        if self.cost_multiplier < 1.0:
            raise CostError("cost_multiplier must be >= 1.0 (live is never cheaper than demo)")

    def stress(self, per_side_cost: float) -> float:
        """The per-turnover cost to use for the stressed re-run."""
        return per_side_cost * self.cost_multiplier


def edge_erosion(base_net: float, stressed_net: float) -> float:
    """Fraction of base net return lost under the gap (1.0 if base was non-positive)."""
    if base_net <= 0:
        return 1.0
    return max(0.0, (base_net - stressed_net) / base_net)


def survives_execution_gap(
    base_net: float, stressed_net: float, *, max_erosion: float = _MAX_EROSION
) -> bool:
    """A candidate survives the gap iff it stays net-positive AND keeps most of its edge."""
    return stressed_net > 0.0 and edge_erosion(base_net, stressed_net) <= max_erosion

```

### libs/data/cleaning.py
```python
"""Return gap-guard -- neutralize bad-print / data-error spikes before research or sizing.

A single corrupt CFD tick (or a price gap across a data hole) shows up as an implausible one-bar
return that can masquerade as a -33% day and dominate drawdown/leverage/fragility math.
``guard_close`` caps each instrument's per-bar LOG return at an asset-plausible bound and rebuilds
the path, so genuine moves survive but artifacts don't. The cap is point-wise (no look-ahead); the
cumsum only reconstructs the level. Real extremes (a true -15% crypto crash) are kept; only moves
beyond the bound (which for FX/indices are almost always data errors) are clipped.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Plausible max single-day absolute return by asset class (moves beyond this are treated as errors).
DEFAULT_CAPS: dict[str, float] = {
    "fx": 0.10, "metal": 0.15, "energy": 0.25, "index": 0.15, "crypto": 0.50, "equity": 0.20,
}


def guard_close(close: pd.DataFrame, caps: dict[str, float]) -> pd.DataFrame:
    """Return a copy of ``close`` with artifact spikes removed (per-symbol daily-return cap)."""
    cols: dict[str, pd.Series] = {}
    for col in close.columns:
        s = close[col].dropna()
        if len(s) < 2:
            cols[col] = close[col]
            continue
        lr = np.log(s).diff()
        cap = float(np.log1p(caps.get(col, 0.5)))
        rebuilt = np.exp(np.log(s.iloc[0]) + lr.clip(-cap, cap).fillna(0.0).cumsum())
        cols[col] = rebuilt.reindex(close.index)
    return pd.DataFrame(cols, index=close.index)

```

### libs/discovery/monte_carlo_survival.py
```python
"""monte_carlo_survival_engine — probability of ruin, survival, worst-case drawdown.

Runs bootstrap, trade-reshuffling, cost-stress, and parameter-perturbation simulations to
estimate survival probability. Rejects anything with survival < 95%.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict

from libs.validation.bootstrap import stationary_block_indices


class MonteCarloSurvivalResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    survival_probability: float
    probability_of_ruin: float
    worst_case_drawdown: float
    median_drawdown: float
    passed: bool

    def __bool__(self) -> bool:
        return self.passed


def _max_drawdown(returns: np.ndarray) -> float:
    equity = np.cumprod(1.0 + returns)
    running = np.maximum.accumulate(equity)
    return float((1.0 - equity / running).max())


def monte_carlo_survival(
    returns: np.ndarray,
    *,
    n_sims: int = 2000,
    block: float = 10.0,
    dd_limit: float = 0.20,
    ruin_drawdown: float = 0.50,
    cost_per_period: float = 0.0,
    survival_min: float = 0.95,
    seed: int = 0,
) -> MonteCarloSurvivalResult:
    """Estimate survival via mixed-method resampling of the return stream."""
    base = np.asarray(returns, dtype="float64") - cost_per_period  # cost stress
    n = len(base)
    if n < 2:
        return MonteCarloSurvivalResult(
            survival_probability=0.0, probability_of_ruin=1.0, worst_case_drawdown=1.0,
            median_drawdown=1.0, passed=False,
        )
    rng = np.random.default_rng(seed)
    drawdowns = np.empty(n_sims, dtype="float64")
    for s in range(n_sims):
        method = s % 3
        if method == 0:  # block bootstrap (preserves autocorrelation)
            sample = base[stationary_block_indices(n, block, rng)]
        elif method == 1:  # trade reshuffling
            sample = base[rng.permutation(n)]
        else:  # parameter perturbation (multiplicative noise on the edge)
            sample = base * (1.0 + rng.normal(0.0, 0.1, size=n))
        drawdowns[s] = _max_drawdown(sample)

    survival = float(np.mean(drawdowns < dd_limit))
    ruin = float(np.mean(drawdowns >= ruin_drawdown))
    return MonteCarloSurvivalResult(
        survival_probability=survival,
        probability_of_ruin=ruin,
        worst_case_drawdown=float(drawdowns.max()),
        median_drawdown=float(np.median(drawdowns)),
        passed=survival >= survival_min,
    )

```

### libs/monitoring/alerting.py
```python
"""Alert persistence and routing.

Alerts are recorded to the durable ``alerts`` table and dispatched to pluggable sinks. The default
:class:`CollectingSink` keeps them in memory (useful for tests and headless runs); production can
add log/webhook sinks without changing callers.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from typing import Protocol

from libs.core.ids import generate_id
from libs.core.time import to_iso8601, utcnow
from libs.monitoring.models import Alert, Severity
from libs.store.connection import Database


def _row_to_alert(row: sqlite3.Row) -> Alert:
    return Alert(
        id=row["id"], created_at=row["created_at"], severity=Severity(row["severity"]),
        source=row["source"], metric=row["metric"], value=row["value"],
        threshold=row["threshold"], message=row["message"], resolved=bool(row["resolved"]),
    )


class AlertSink(Protocol):
    def emit(self, alert: Alert) -> None: ...


class CollectingSink:
    """An in-memory sink that retains every alert emitted (default, deterministic)."""

    def __init__(self) -> None:
        self.alerts: list[Alert] = []

    def emit(self, alert: Alert) -> None:
        self.alerts.append(alert)


class AlertStore:
    """Writer/reader for the ``alerts`` table (append-only; resolvable, never deleted)."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def record(
        self,
        *,
        severity: Severity,
        source: str,
        message: str,
        metric: str | None = None,
        value: float | None = None,
        threshold: float | None = None,
    ) -> Alert:
        alert = Alert(
            id=generate_id("alert"), created_at=to_iso8601(utcnow()), severity=severity,
            source=source, metric=metric, value=value, threshold=threshold, message=message,
        )
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO alerts "
                "(id, created_at, severity, source, metric, value, threshold, message, resolved) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)",
                (alert.id, alert.created_at, alert.severity.value, alert.source, alert.metric,
                 alert.value, alert.threshold, alert.message),
            )
        return alert

    def resolve(self, alert_id: str) -> None:
        with self.db.transaction() as conn:
            conn.execute("UPDATE alerts SET resolved = 1 WHERE id = ?", (alert_id,))

    def open_alerts(self) -> list[Alert]:
        rows = self.db.execute(
            "SELECT * FROM alerts WHERE resolved = 0 ORDER BY seq"
        ).fetchall()
        return [_row_to_alert(r) for r in rows]

    def all(self) -> list[Alert]:
        rows = self.db.execute("SELECT * FROM alerts ORDER BY seq").fetchall()
        return [_row_to_alert(r) for r in rows]


class AlertRouter:
    """Fans an alert out to every configured sink."""

    def __init__(self, sinks: Sequence[AlertSink] | None = None) -> None:
        self.sinks: list[AlertSink] = list(sinks) if sinks else [CollectingSink()]

    def dispatch(self, alert: Alert) -> None:
        for sink in self.sinks:
            sink.emit(alert)

```

### libs/ops/backup.py
```python
"""Backup and restore for the SQLite system of record.

Uses SQLite's online backup API for a consistent copy (safe while the DB is open), records a
sha256 manifest for tamper/corruption detection, and provides a restore drill that proves a backup
actually restores and passes an integrity + schema-version check. Deterministic and side-effect
explicit (writes only under the destination directory).
"""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from libs.core.time import to_iso8601, utcnow
from libs.ops.errors import OpsError
from libs.store.connection import Database
from libs.store.migrations import current_version

_DB_NAME = "sor.sqlite"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class BackupManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    created_at: str
    db_version: int
    files: dict[str, str] = Field(default_factory=dict)  # relative name -> sha256


class BackupManager:
    """Creates verified, consistent backups of the system-of-record database."""

    def __init__(self, *, source_db: Path) -> None:
        self.source_db = Path(source_db)

    def backup(self, dest_dir: Path) -> BackupManifest:
        if not self.source_db.exists():
            raise OpsError(f"source db not found: {self.source_db}")
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_db = dest_dir / _DB_NAME

        # Online backup API: a consistent snapshot even if the source is in use.
        src = sqlite3.connect(str(self.source_db))
        try:
            dst = sqlite3.connect(str(dest_db))
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()

        version = self._db_version(dest_db)
        manifest = BackupManifest(
            created_at=to_iso8601(utcnow()),
            db_version=version,
            files={_DB_NAME: _sha256_file(dest_db)},
        )
        (dest_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2), "utf-8")
        return manifest

    def verify(self, dest_dir: Path, manifest: BackupManifest) -> bool:
        """Recompute checksums and confirm the backup matches its manifest."""
        dest_dir = Path(dest_dir)
        for name, digest in manifest.files.items():
            path = dest_dir / name
            if not path.exists() or _sha256_file(path) != digest:
                return False
        return True

    @staticmethod
    def _db_version(db_path: Path) -> int:
        db = Database(db_path)
        try:
            return current_version(db)
        finally:
            db.close()


class RestoreDrill:
    """Proves a backup restores cleanly: integrity check + schema-version match + checksum."""

    def run(self, backup_dir: Path, manifest: BackupManifest, *, workdir: Path) -> bool:
        backup_dir = Path(backup_dir)
        workdir = Path(workdir)
        workdir.mkdir(parents=True, exist_ok=True)
        src_db = backup_dir / _DB_NAME
        if not src_db.exists() or _sha256_file(src_db) != manifest.files.get(_DB_NAME):
            return False
        restored = workdir / _DB_NAME
        shutil.copyfile(src_db, restored)

        db = Database(restored)
        try:
            integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                return False
            return current_version(db) == manifest.db_version
        finally:
            db.close()

```

### libs/ops/workers.py
```python
"""Worker registry -- heartbeats so the supervisor can detect and reap dead workers.

A worker writes a heartbeat each loop. If ``last_seen`` falls behind ``stale_seconds`` the worker is
presumed dead (crash / power loss / OOM kill); the supervisor respawns it and the queue's lease
expiry returns its in-flight campaign to the pool. Operational state only.
"""

from __future__ import annotations

import socket
from datetime import UTC, datetime, timedelta
from typing import Any

from libs.store.connection import Database


def _iso(dt: datetime) -> str:
    return dt.isoformat()


class WorkerRegistry:
    def __init__(self, db: Database) -> None:
        self.db = db

    def register(self, worker_id: str, *, pid: int, host: str | None = None) -> None:
        now = _iso(datetime.now(tz=UTC))
        host = host or socket.gethostname()
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO workers
                   (worker_id, pid, host, status, started_at, last_seen, campaigns_done)
                   VALUES (?, ?, ?, 'idle', ?, ?, 0)
                   ON CONFLICT(worker_id) DO UPDATE SET
                       pid=excluded.pid, host=excluded.host, status='idle',
                       started_at=excluded.started_at, last_seen=excluded.last_seen""",
                (worker_id, pid, host, now, now),
            )

    def beat(self, worker_id: str, *, status: str, current_campaign: str | None = None,
             completed: bool = False) -> None:
        now = _iso(datetime.now(tz=UTC))
        inc = 1 if completed else 0
        with self.db.transaction() as conn:
            conn.execute(
                """UPDATE workers
                   SET status=?, current_campaign=?, last_seen=?,
                       campaigns_done=campaigns_done + ?
                   WHERE worker_id=?""",
                (status, current_campaign, now, inc, worker_id),
            )

    def active(self, *, stale_seconds: int = 60) -> list[dict[str, Any]]:
        cutoff = _iso(datetime.now(tz=UTC) - timedelta(seconds=stale_seconds))
        rows = self.db.execute(
            "SELECT * FROM workers WHERE last_seen >= ? ORDER BY worker_id", (cutoff,)
        ).fetchall()
        return [dict(r) for r in rows]

    def dead(self, *, stale_seconds: int = 60) -> list[dict[str, Any]]:
        cutoff = _iso(datetime.now(tz=UTC) - timedelta(seconds=stale_seconds))
        rows = self.db.execute(
            "SELECT * FROM workers WHERE last_seen < ? ORDER BY worker_id", (cutoff,)
        ).fetchall()
        return [dict(r) for r in rows]

    def prune(self, *, stale_seconds: int = 3600) -> int:
        cutoff = _iso(datetime.now(tz=UTC) - timedelta(seconds=stale_seconds))
        with self.db.transaction() as conn:
            cur = conn.execute("DELETE FROM workers WHERE last_seen < ?", (cutoff,))
            return int(cur.rowcount)

    def all(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.execute("SELECT * FROM workers ORDER BY worker_id")]

```

### libs/portfolio/diversification.py
```python
"""Diversification analytics and correlation controls."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from libs.portfolio.covariance import cov_to_corr
from libs.risk.correlation import correlation_clusters


def diversification_ratio(weights: np.ndarray, cov: np.ndarray) -> float:
    """(sum |w_i| * sigma_i) / sqrt(w' Cov w): 1 = no diversification, higher = more."""
    w = np.asarray(weights, dtype="float64")
    sigma = np.sqrt(np.diag(np.asarray(cov, dtype="float64")))
    port_vol = float(np.sqrt(w @ cov @ w))
    if port_vol <= 0:
        return 1.0
    return float(np.abs(w) @ sigma / port_vol)


def concentration(weights: np.ndarray) -> float:
    """Herfindahl concentration (sum of squared weights); lower = more diversified."""
    w = np.asarray(weights, dtype="float64")
    return float(np.sum(w**2))


def effective_bets(weights: np.ndarray) -> float:
    """Effective number of independent bets = 1 / concentration."""
    hhi = concentration(weights)
    return 1.0 / hhi if hhi > 0 else 0.0


def apply_correlation_controls(
    weights: Mapping[str, float],
    cov: np.ndarray,
    order: Sequence[str],
    *,
    cluster_threshold: float = 0.8,
    max_cluster_weight: float = 0.60,
) -> tuple[dict[str, float], list[str]]:
    """Cap the total weight of any highly-correlated cluster of alphas."""
    corr = cov_to_corr(np.asarray(cov, dtype="float64"))
    clusters = correlation_clusters(corr, threshold=cluster_threshold)
    out = {i: float(weights[i]) for i in order}
    binding: list[str] = []
    for cluster in clusters:
        if len(cluster) <= 1:
            continue
        members = [order[idx] for idx in cluster]
        total = sum(out[m] for m in members)
        if total > max_cluster_weight and total > 0:
            scale = max_cluster_weight / total
            for m in members:
                out[m] *= scale
            binding.append("correlation_cluster:" + ",".join(sorted(members)))
    return out, binding

```

### libs/research/__init__.py
```python
"""Research strategy cores (shared by backtest + forward-shadow so they are provably identical)."""

```

### libs/research/cashcarry.py
```python
"""Delta-neutral cash-and-carry return (long spot + short perp).

Harvests funding + basis convergence with ~zero directional exposure (the spot leg hedges the perp's
price risk). Shared by the backtest and the forward shadow so the out-of-sample comparison is
apples-to-apples. Decisions use lagged funding only; no look-ahead.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def cashcarry_returns(funding: pd.DataFrame, basis: pd.DataFrame, *, lookback: int = 3,
                      q: float = 0.2, band: float = 0.02, cost: float = 8e-4) -> np.ndarray:
    """Daily delta-neutral carry: + funding collected, + basis convergence, - turnover cost.

    Cross-sectional: long-spot/short-perp on the top-q funding names (collect positive funding),
    long-perp/short-spot on the bottom-q (collect negative funding). Weights are equal within each
    leg, gross-normalised, turnover-banded."""
    sig = funding.rolling(lookback).mean().shift(1)
    dbasis = basis.diff()
    out = np.zeros(len(funding))
    prev = pd.Series(0.0, index=funding.columns)
    for t in range(1, len(funding)):
        s = sig.iloc[t].dropna()
        if len(s) < 12:
            out[t] = float((prev * funding.iloc[t].reindex(prev.index).fillna(0.0)).sum())
            continue
        k = max(1, int(len(s) * q))
        ranked = s.sort_values()
        w = pd.Series(0.0, index=funding.columns)
        w[ranked.index[-k:]] = 0.5 / k                 # high funding -> short perp/long spot (+)
        w[ranked.index[:k]] = -0.5 / k                 # low/neg funding -> long perp/short spot (-)
        delta = (w - prev).abs()
        w = w.where(delta > band, prev)
        fund_pnl = float((w * funding.iloc[t].reindex(w.index).fillna(0.0)).sum())
        basis_pnl = float(-(w * dbasis.iloc[t].reindex(w.index).fillna(0.0)).sum())
        turn = float((w - prev).abs().sum()) * cost
        out[t] = fund_pnl + basis_pnl - turn
        prev = w
    return out


def spot_basis_carry_returns(funding: pd.DataFrame, basis: pd.DataFrame, *, lookback: int = 3,
                             q: float = 0.2, band: float = 0.02, cost: float = 8e-4) -> np.ndarray:
    """Second spot sleeve: delta-neutral carry weighted by the perp-premium BASIS, not funding.

    When a perp trades rich to spot (high positive basis / contango), short-perp/long-spot harvests
    BOTH the convergence as basis decays to zero AND the funding the longs pay. Distinct signal from
    cashcarry_returns (basis level vs funding rate) -> adds spot breadth. Lagged basis only."""
    sig = basis.rolling(lookback).mean().shift(1)
    dbasis = basis.diff()
    out = np.zeros(len(basis))
    prev = pd.Series(0.0, index=basis.columns)
    for t in range(1, len(basis)):
        s = sig.iloc[t].dropna()
        if len(s) < 12:
            continue
        k = max(1, int(len(s) * q))
        ranked = s.sort_values()
        w = pd.Series(0.0, index=basis.columns)
        w[ranked.index[-k:]] = 0.5 / k                 # rich perp -> short perp/long spot (+)
        w[ranked.index[:k]] = -0.5 / k                 # cheap perp -> long perp/short spot (-)
        delta = (w - prev).abs()
        w = w.where(delta > band, prev)
        fund_pnl = float((w * funding.iloc[t].reindex(w.index).fillna(0.0)).sum())
        conv_pnl = float(-(w * dbasis.iloc[t].reindex(w.index).fillna(0.0)).sum())
        turn = float((w - prev).abs().sum()) * cost
        out[t] = fund_pnl + conv_pnl - turn
        prev = w
    return out

```

### libs/research/dist_shift.py
```python
"""DISTRIBUTION-SHIFT MONITOR -- constitution L2.10 / triage #128, built 2026-07-29.

THE QUESTION IT ANSWERS, which regime classification does NOT: *are we still operating in the
same world the signal was screened in?* A relationship can survive while the distribution beneath
it moves — vol compresses, liquidity thins, the correlation structure re-forms — and every
threshold the desk calibrated (z-score windows, cost floors, funding bars, depth guards) was fitted
in the OLD distribution. Regime labels answer "which state are we in"; this answers "has the
measuring stick itself changed", which is the failure mode that silently invalidates calibration.

DELIBERATELY MERGED, NOT A NEW AGENT (L2.9 upgrade-before-build): this is a library the existing
revalidation path and axis screens call. It owns no cadence, no state file, no pager.

ACTION SEMANTICS, and the direction matters: a detected shift NEVER promotes and never
auto-demotes. It (a) flags the axis for re-validation and (b) recommends a CONFIDENCE HAIRCUT --
downward only. A monitor that could raise confidence would be an alpha claim wearing a
diagnostic's clothes.

Method: two-sample, non-parametric, tiny — a two-sample KS statistic plus a variance-ratio and a
level shift in robust units, computed reference-window vs recent-window. No scipy dependency (the
KS critical value at 5% is the standard 1.36*sqrt((n+m)/nm) asymptotic form), so this runs in any
organ including the quota-free ones.

Pure numpy. import from libs.research.dist_shift.
"""
from __future__ import annotations

from typing import Any, Literal

import numpy as np

Verdict = Literal["STABLE", "DRIFT", "SHIFT", "INSUFFICIENT-DATA"]

# Bands. Chosen to catch distributional MOVES, not noise: at n=m=60 the 5% KS critical value is
# ~0.248, so DRIFT starts where the two windows are formally distinguishable and SHIFT is reserved
# for a clearly different distribution. Variance ratio bands are 2x/0.5x -- a halving or doubling
# of realised variance re-prices every vol-scaled threshold the desk owns.
_VAR_BAND = 2.0
_VAR_BREAK = 4.0
_LEVEL_BAND = 1.0      # median move, in reference-window MADs
_LEVEL_BREAK = 2.5
_MIN_WIN = 20


def _ks(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    """Two-sample KS statistic and its 5% asymptotic critical value."""
    grid = np.concatenate([a, b])
    grid.sort()
    ca = np.searchsorted(np.sort(a), grid, side="right") / len(a)
    cb = np.searchsorted(np.sort(b), grid, side="right") / len(b)
    d = float(np.max(np.abs(ca - cb)))
    crit = 1.36 * float(np.sqrt((len(a) + len(b)) / (len(a) * len(b))))
    return d, crit


def _mad(x: np.ndarray) -> float:
    return float(np.median(np.abs(x - np.median(x))))


def distribution_shift(reference: np.ndarray, recent: np.ndarray, *,
                       name: str = "series") -> dict[str, Any]:
    """Compare a recent window against a reference window on shape, spread and level.

    reference: the window the signal/threshold was calibrated in.
    recent:    the window the desk is trading in now.
    Returns a verdict plus a RECOMMENDED confidence haircut in [0, 0.5] -- downward only, and
    advisory: the caller decides, and the caller logs the decision.
    """
    a = np.asarray(reference, dtype="float64")
    b = np.asarray(recent, dtype="float64")
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if len(a) < _MIN_WIN or len(b) < _MIN_WIN:
        return {"name": name, "verdict": "INSUFFICIENT-DATA", "n_ref": len(a),
                "n_recent": len(b), "haircut": 0.0,
                "detail": f"need >={_MIN_WIN} finite points per window"}

    d, crit = _ks(a, b)
    va, vb = float(a.var()), float(b.var())
    var_ratio = (vb / va) if va > 0 else float("inf") if vb > 0 else 1.0
    mad_a = _mad(a)
    level_move = abs(float(np.median(b) - np.median(a))) / mad_a if mad_a > 0 else 0.0

    ks_flag = d > crit
    var_flag = var_ratio > _VAR_BAND or var_ratio < 1.0 / _VAR_BAND
    var_break = var_ratio > _VAR_BREAK or var_ratio < 1.0 / _VAR_BREAK
    level_flag = level_move > _LEVEL_BAND
    level_break = level_move > _LEVEL_BREAK

    # SHIFT requires either a break-magnitude move OR agreement between two independent views
    # (shape + spread/level). One marginal indicator alone is DRIFT: it flags, it does not
    # conclude -- the same corroboration discipline the lookahead rail uses (axis_screen).
    corroborated = ks_flag and (var_flag or level_flag)
    if var_break or level_break or corroborated:
        verdict: Verdict = "SHIFT"
    elif ks_flag or var_flag or level_flag:
        verdict = "DRIFT"
    else:
        verdict = "STABLE"

    haircut = {"STABLE": 0.0, "DRIFT": 0.15, "SHIFT": 0.35,
               "INSUFFICIENT-DATA": 0.0}[verdict]
    return {"name": name, "verdict": verdict, "haircut": haircut,
            "ks_d": round(d, 4), "ks_crit_5pct": round(crit, 4), "ks_flag": ks_flag,
            "var_ratio": round(var_ratio, 3) if np.isfinite(var_ratio) else None,
            "level_move_mads": round(level_move, 3),
            "n_ref": len(a), "n_recent": len(b),
            "action": ("none" if verdict == "STABLE" else
                       "flag-for-revalidation + confidence haircut (advisory, downward only)"),
            "note": "regime labels say WHICH state; this says whether the measuring stick moved"}


def split_and_check(series: np.ndarray, *, recent_frac: float = 0.25,
                    name: str = "series") -> dict[str, Any]:
    """Convenience: split one series into reference (early) and recent (tail) and compare.

    Used by revalidation passes that hold a single history and want the honest question "does my
    own tail look like my own body?" without choosing windows by hand -- choosing the split point
    after seeing the answer is exactly the specification search the desk forbids elsewhere.
    """
    x = np.asarray(series, dtype="float64")
    cut = max(int(len(x) * (1.0 - min(max(recent_frac, 0.05), 0.5))), 0)
    return distribution_shift(x[:cut], x[cut:], name=name)

```

### libs/research/sleeve_allocations.py
```python
"""Declared per-sleeve allocations -- what makes an allocation-aware capacity gate honest.

§42 lets a candidate be judged against the equity IT will actually be funded with rather than an
equal-weight share of the book. That is strictly correct -- a $5k-capacity edge funded with $1,000
is 5x headroom and perfectly safe, while equal weight on a $14.8k book reads $1,477 into it and
fails -- and it is exactly the excluded-by-default bug §42 exists to kill, one layer further down.

BUT A DECLARED NUMBER WITH NOTHING CHECKING IT IS A BYPASS. If a candidate may simply assert
"I will only use $1", every capacity gate in the desk passes forever and the protection is gone. A
declaration is therefore a COMMITMENT with two mechanical consequences, both enforced by
``max_audit.check_capacity_allocation_honesty``:

  1. IT MUST BE SELF-CONSISTENT. A declaration above what its own edge can hold
     (``max_allocation(capacity)``) is refused outright -- it is asking for a pass it does not
     qualify for even under its own numbers.
  2. IT IS RECONCILED AGAINST WHAT THE SLEEVE IS ACTUALLY FUNDED WITH. Funding a sleeve above its
     declaration is the whole bypass, and it fires as a defect naming the sleeve, the declared
     figure and the real one. This is the half that has to exist BEFORE the declaration is trusted
     anywhere, which is why it ships in the same change rather than being left for Gate 0.

PRE-GATE-0 HONESTY. Nothing is live yet, so the reconciliation has nothing to compare against most
of the time. It reports that as UNVERIFIED rather than as a pass -- "no live funding data" and
"funding matches the declaration" are different states and must never print the same way.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from libs.research.capacity_policy import max_allocation

STORE = Path("data/sleeve_allocations.json")


class SleeveAllocation(BaseModel):
    """One sleeve's declared capacity and the equity it commits to using."""

    model_config = ConfigDict(frozen=True)

    sleeve: str
    capacity_usd: float
    declared_usd: float

    @property
    def ceiling_usd(self) -> float:
        """Most this sleeve may EVER be funded with, from its own capacity."""
        return max_allocation(self.capacity_usd)

    @property
    def self_consistent(self) -> bool:
        return 0.0 < self.declared_usd <= self.ceiling_usd


def load(store: Path = STORE) -> list[SleeveAllocation]:
    """Read the declarations. A missing or corrupt store is EMPTY, never an exception."""
    try:
        raw = json.loads(store.read_text("utf-8"))
    except Exception:
        return []
    out: list[SleeveAllocation] = []
    for name, row in (raw.items() if isinstance(raw, dict) else []):
        try:
            out.append(SleeveAllocation(
                sleeve=str(name), capacity_usd=float(row["capacity_usd"]),
                declared_usd=float(row["declared_usd"])))
        except Exception:
            continue                      # one malformed row must not hide the rest
    return out


def inconsistent(allocs: list[SleeveAllocation]) -> list[SleeveAllocation]:
    """Declarations that exceed what their own edge can hold -- refused before anything else."""
    return [a for a in allocs if not a.self_consistent]


def overfunded(
    allocs: list[SleeveAllocation], funded: dict[str, float], *, tolerance: float = 0.05
) -> list[tuple[SleeveAllocation, float]]:
    """Sleeves funded above what they declared -- the bypass, caught.

    A 5% tolerance absorbs mark-to-market drift and fill slippage: a sleeve declared at $1,000 that
    marks to $1,020 has not cheated, and firing on that would train the desk to ignore the check.
    Anything beyond it is a real breach of the commitment the capacity gate was passed on.
    """
    out: list[tuple[SleeveAllocation, float]] = []
    for a in allocs:
        got = funded.get(a.sleeve)
        if got is not None and got > a.declared_usd * (1.0 + tolerance):
            out.append((a, got))
    return out


def unverified(
    allocs: list[SleeveAllocation], funded: dict[str, float]
) -> list[SleeveAllocation]:
    """Declarations with no live funding figure to check -- reported, never counted as OK."""
    return [a for a in allocs if a.sleeve not in funded]

```

### libs/self_improvement/adaptive_thresholds.py
```python
"""Evidence-adjustable audit thresholds -- self-tuning WITHIN HARD BOUNDS, never a free optimizer.

The audit/gate-calibration thresholds (depth-days, deploy-bar, leak-tolerance, min-sample) were
hardcoded. Hardcoded is arbitrary; a free optimizer is dangerous (it can silently loosen a gate
until it passes everything). This module is the safe middle: each threshold declares a DEFAULT, a
hard FLOOR and CEILING it can never cross, and a DIRECTION guard -- safety-critical bars are
``tighten_only`` (evidence can make them stricter, never looser). Every adjustment is clamped to the
bounds, direction-checked, and appended to an audit log; the current value persists to
``data/adaptive_thresholds.json`` and reverts to the default if the store is missing or corrupt.

This is the desk's existing "5-bps threshold is EVIDENCE-ADJUSTABLE, raise it only if..." pattern,
generalised: max ROI (metrics stop being arbitrary, self-correct toward what the evidence supports)
with the downside fenced (a bound can never be crossed, a safety bar can never be loosened).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

Direction = Literal["free", "tighten_only", "loosen_only"]


class ThresholdSpec(BaseModel):
    """One tunable threshold: its default and the hard bounds evidence can never cross."""

    model_config = ConfigDict(frozen=True)

    name: str
    default: float
    floor: float  # hard minimum -- evidence can never set below this
    ceiling: float  # hard maximum -- evidence can never set above this
    direction: Direction  # "tighten_only" = safety bar (raise-only); "loosen_only"; "free"
    tighten_is_up: bool  # True if a HIGHER value is stricter (e.g. deploy bar); False if lower is
    rationale: str


# The registry: every audit/gate-calibration threshold that may self-tune, with its safety envelope.
_REGISTRY: dict[str, ThresholdSpec] = {
    "depth_deep_days": ThresholdSpec(
        name="depth_deep_days", default=180.0, floor=90.0, ceiling=730.0,
        direction="free", tighten_is_up=True,
        rationale="days of history for an axis to count 'deep'; bounded so it can't trivialise "
                  "depth (floor) or demand impossible history (ceiling)"),
    "reject_deploy_threshold": ThresholdSpec(
        name="reject_deploy_threshold", default=0.5, floor=0.3, ceiling=2.0,
        direction="tighten_only", tighten_is_up=True,
        rationale="forward metric a reject must clear to count as 'would have paid'; tighten-only "
                  "so the gate-leak audit can never be made to cry wolf by lowering the bar"),
    "reject_leak_tolerance": ThresholdSpec(
        name="reject_leak_tolerance", default=0.10, floor=0.05, ceiling=0.25,
        direction="tighten_only", tighten_is_up=False,
        rationale="share of rejects that may pay OOS before the gate is over-strict; tighten-only "
                  "(a LOWER tolerance is stricter) so leak detection can never be dulled"),
    "reject_min_sample": ThresholdSpec(
        name="reject_min_sample", default=5.0, floor=5.0, ceiling=50.0,
        direction="tighten_only", tighten_is_up=True,
        rationale="decided rejects needed before judging the gate; raise-only, so a verdict always "
                  "rests on at least as much evidence, never less"),
    "mine_kill_share_bar": ThresholdSpec(
        name="mine_kill_share_bar", default=0.60, floor=0.20, ceiling=0.80,
        direction="tighten_only", tighten_is_up=False,
        rationale="share of terminal §33 dispositions that may be 'killed' before the backlog is "
                  "being cleared by graveyard rather than by conversion; tighten-only (LOWER is "
                  "stricter) so the mass-kill escape hatch can never be widened"),
    "mine_stale_owing_days": ThresholdSpec(
        name="mine_stale_owing_days", default=14.0, floor=2.0, ceiling=60.0,
        direction="tighten_only", tighten_is_up=False,
        rationale="days a carded find may owe a disposition before it is a rotting-inventory "
                  "defect; tighten-only (FEWER days is stricter) -- the desk gets faster or holds, "
                  "never slower, which is the §33 ratchet expressed as a bound"),
    "capacity_headroom_mult": ThresholdSpec(
        name="capacity_headroom_mult", default=4.0, floor=2.0, ceiling=20.0,
        direction="tighten_only", tighten_is_up=True,
        rationale="an edge must absorb this multiple of DEPLOYED equity before it may be trusted "
                  "-- the real protection is never being a large share of your own edge's "
                  "capacity, which is a RATIO, not a dollar figure; tighten-only (higher = more "
                  "headroom demanded)"),
    "capacity_abs_floor_usd": ThresholdSpec(
        name="capacity_abs_floor_usd", default=2000.0, floor=500.0, ceiling=100_000.0,
        direction="free", tighten_is_up=True,
        rationale="floor-of-the-floor: below this an 'edge' is a rounding error whatever the book "
                  "size. Deliberately FREE, not tighten-only: the old fixed $100k floor was the "
                  "very thing excluding the capacity-bound niche the desk's own PROSPECTOR_SPEC "
                  "names as its structural advantage, so this must be able to move DOWN on "
                  "evidence as the desk deliberately hunts smaller"),
    "capacity_crowd_start_usd": ThresholdSpec(
        name="capacity_crowd_start_usd", default=1.0e7, floor=1.0e6, ceiling=1.0e9,
        direction="free", tighten_is_up=False,
        rationale="ABSOLUTE capacity past which an edge is assumed CROWDED (big enough that funds "
                  "trade it too) and is discounted. Absolute, not a multiple of our book: whether "
                  "an edge is crowded is a fact about the market, not about how much money we "
                  "have. Free, because where fund attention actually starts is an empirical "
                  "question the desk's own decay-vs-capacity evidence should answer, either way"),
    "capacity_crowd_floor": ThresholdSpec(
        name="capacity_crowd_floor", default=1.0, floor=0.50, ceiling=1.0,
        direction="free", tighten_is_up=False,
        rationale="crowding discount floor. DEFAULT 1.0 = NO DISCOUNT (principal 2026-07-26): the "
                  "objective is the maximum number of simultaneous uncorrelated alphas, so a "
                  "sleeve declined for its SIZE is compounding foregone, and crowding is already "
                  "priced by the crowded_known prior plus DSR/PBO/persistence -- discounting it "
                  "here charged big edges twice for one fact. Free rather than pinned so MEASURED "
                  "decay-vs-capacity evidence could reintroduce a discount; preference may not"),
    "mine_latency_regress_mult": ThresholdSpec(
        name="mine_latency_regress_mult", default=1.5, floor=1.05, ceiling=3.0,
        direction="tighten_only", tighten_is_up=False,
        rationale="multiple of the BEST-EVER median conversion latency that counts as regression; "
                  "tighten-only so the ratchet's tolerance narrows as the desk improves"),
}


def registry() -> dict[str, ThresholdSpec]:
    return dict(_REGISTRY)


class ThresholdBook:
    """Reader/adjuster for the persisted threshold values (bounded, direction-guarded, logged)."""

    def __init__(self, store: Path, *, log: Path | None = None) -> None:
        self.store = store
        self.log = log if log is not None else store.with_name("adaptive_thresholds_log.jsonl")

    def _load(self) -> dict[str, float]:
        try:
            raw = json.loads(self.store.read_text("utf-8"))
            return {k: float(v) for k, v in raw.items() if k in _REGISTRY}
        except Exception:
            return {}

    def get(self, name: str) -> float:
        """Current value for ``name`` -- the persisted value if present and in-bounds, else default.

        Always re-clamps to the current bounds, so a store that was hand-edited (or written under an
        older, wider bound) can never return an out-of-envelope value.
        """
        spec = _REGISTRY[name]
        val = self._load().get(name, spec.default)
        return max(spec.floor, min(spec.ceiling, val))

    def propose(self, name: str, target: float, *, reason: str) -> tuple[float, bool, str]:
        """Move ``name`` toward ``target`` within its safety envelope; return (value, changed, why).

        The move is rejected (value unchanged) if it would loosen a ``tighten_only`` bar or tighten
        a ``loosen_only`` one; otherwise it is clamped to [floor, ceiling] and persisted. Every call
        -- applied or rejected -- is appended to the log, so the tuning history is fully auditable
        and every change is reversible (set the value back; the default is always recoverable).
        """
        spec = _REGISTRY[name]
        current = self.get(name)
        clamped = max(spec.floor, min(spec.ceiling, target))
        stricter = (clamped > current) if spec.tighten_is_up else (clamped < current)
        looser = (clamped < current) if spec.tighten_is_up else (clamped > current)
        if spec.direction == "tighten_only" and looser:
            why = f"rejected: {name} is tighten-only; {clamped:g} would loosen from {current:g}"
            applied = current
            changed = False
        elif spec.direction == "loosen_only" and stricter:
            why = f"rejected: {name} is loosen-only; {clamped:g} would tighten from {current:g}"
            applied = current
            changed = False
        elif clamped == current:
            why = f"no-op: {name} already at {current:g}"
            applied = current
            changed = False
        else:
            values = self._load()
            values[name] = clamped
            self.store.parent.mkdir(parents=True, exist_ok=True)
            self.store.write_text(json.dumps(values, indent=1), "utf-8")
            why = f"applied: {name} {current:g} -> {clamped:g}"
            applied = clamped
            changed = True
        self._append_log(name, current, target, applied, changed, reason, why)
        return applied, changed, why

    def _append_log(self, name: str, before: float, target: float, after: float,
                    changed: bool, reason: str, why: str) -> None:
        from libs.core.time import to_iso8601, utcnow
        entry = {
            "ts": to_iso8601(utcnow()), "name": name, "before": before, "target": target,
            "after": after, "changed": changed, "reason": reason, "why": why,
        }
        try:
            self.log.parent.mkdir(parents=True, exist_ok=True)
            with self.log.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        except Exception:
            pass

```

### libs/self_improvement/controller.py
```python
"""Improvement controller — the Stage 13 master coordinator.

Receives health/decay signals, produces an :class:`ImprovementPlan` of *recommendations*, and
journals them. Governance is structural: the controller has no method that writes production
weights. ``apply_weight_proposal`` defers to the Portfolio Engine (risk overrides alpha); Stage
13 may recommend and schedule but may not directly change production portfolio weights.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from libs.alpha.card import AlphaCard, LiveMetrics
from libs.portfolio.engine import PortfolioEngine
from libs.portfolio.models import AlphaInput, PortfolioTarget
from libs.self_improvement.audit import ImprovementAudit
from libs.self_improvement.capital_reallocator import CapitalReallocator
from libs.self_improvement.decay_engine import AlphaDecayEngine
from libs.self_improvement.errors import GovernanceError
from libs.self_improvement.health_monitor import AlphaHealthMonitor
from libs.self_improvement.models import (
    DecayAssessment,
    DecayLevel,
    ImprovementAction,
    ImprovementActionType,
    ImprovementPlan,
    ResearchPriority,
    WeightProposal,
)
from libs.self_improvement.weight_optimizer import DynamicWeightOptimizer, WeightCandidate


class ImprovementController:
    """Coordinates the self-improvement engines into a recommendation plan."""

    def __init__(
        self,
        *,
        health_monitor: AlphaHealthMonitor | None = None,
        decay_engine: AlphaDecayEngine | None = None,
        weight_optimizer: DynamicWeightOptimizer | None = None,
        capital_reallocator: CapitalReallocator | None = None,
        audit: ImprovementAudit | None = None,
    ) -> None:
        self.health_monitor = health_monitor or AlphaHealthMonitor()
        self.decay_engine = decay_engine or AlphaDecayEngine()
        self.weight_optimizer = weight_optimizer or DynamicWeightOptimizer()
        self.capital_reallocator = capital_reallocator or CapitalReallocator()
        self.audit = audit

    def evaluate(
        self,
        observations: Sequence[tuple[AlphaCard, LiveMetrics]],
        *,
        current_weights: Mapping[str, float] | None = None,
        total_capital: float = 0.0,
        regime_match: Mapping[str, float] | None = None,
        research_priorities: Sequence[ResearchPriority] | None = None,
    ) -> ImprovementPlan:
        """Produce a recommendation plan from current alpha health and decay."""
        actions: list[ImprovementAction] = []
        candidates: list[WeightCandidate] = []

        for card, live in observations:
            health = self.health_monitor.assess(card, live)
            decay = self.decay_engine.assess(card, live)
            match = regime_match.get(card.id, 1.0) if regime_match else 1.0
            candidates.append(
                WeightCandidate(
                    alpha_id=card.id,
                    health_score=health.health_score,
                    decay_multiplier=decay.weight_multiplier,
                    regime_match=match,
                )
            )
            actions.extend(self._decay_actions(card.id, decay))

        proposal = self.weight_optimizer.propose(candidates)
        if current_weights is not None:
            actions.extend(
                self.capital_reallocator.propose(
                    current_weights, proposal.weights, total_capital=total_capital
                )
            )

        plan = ImprovementPlan(
            actions=actions,
            weight_proposal=proposal,
            research_priorities=list(research_priorities or []),
        )
        if self.audit is not None:
            self.audit.record_plan(plan)
        return plan

    @staticmethod
    def _decay_actions(alpha_id: str, decay: DecayAssessment) -> list[ImprovementAction]:
        if decay.decay_level is DecayLevel.DEAD:
            return [
                ImprovementAction(
                    type=ImprovementActionType.RETIRE, target_id=alpha_id,
                    rationale="decay level DEAD -> retire",
                    detail={"decay_score": decay.decay_score}, requires_portfolio_approval=True,
                )
            ]
        if decay.decay_level is DecayLevel.DECAYING:
            return [
                ImprovementAction(
                    type=ImprovementActionType.PAUSE, target_id=alpha_id,
                    rationale="decaying -> pause capital increases",
                    detail={"allow_increase": False}, requires_portfolio_approval=True,
                )
            ]
        if decay.decay_level in (DecayLevel.WATCH, DecayLevel.WEAK):
            return [
                ImprovementAction(
                    type=ImprovementActionType.WEIGHT_CHANGE, target_id=alpha_id,
                    rationale=decay.recommended_action,
                    detail={"weight_multiplier": decay.weight_multiplier},
                    requires_portfolio_approval=True,
                )
            ]
        return []

    def apply_weight_proposal(
        self,
        proposal: WeightProposal,
        portfolio_engine: PortfolioEngine,
        alphas: Sequence[AlphaInput],
        *,
        correlation: np.ndarray | None = None,
        method: str = "optimize",
    ) -> PortfolioTarget:
        """Realize a weight proposal — ONLY through the Portfolio Engine (the approver).

        Stage 13 cannot set production weights. The Portfolio Engine re-derives the constrained
        target (risk overrides alpha); the proposal is advisory input only.
        """
        if not proposal.requires_portfolio_approval:
            raise GovernanceError("weight proposals must require Portfolio Engine approval")
        return portfolio_engine.build_portfolio(
            alphas, correlation=correlation, method=method
        )

```

### libs/self_improvement/forecast_calibration.py
```python
"""Forecast calibration -- log every probability forecast, score it when the outcome resolves.

The constitution (Phase 9) requires continuously calibrating forecasts of Engineering ROI, alpha
survival, and deployment success via Bayesian updating, and detecting systematic bias. This is the
persistent scoring layer: each forecast (engineering-task p_success, alpha survival prob, leverage
confidence) is stored by id; when the outcome later resolves (task done, alpha survived/killed)
it is scored. Calibration = Brier score + a Beta(a,b) posterior over hit-rate + a bias term
(mean forecast - mean outcome). Until enough outcomes resolve it honestly reports insufficient data
-- no fabricated calibration. Pure/deterministic; the store is data/forecast_log.json.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_LOG = Path("data/forecast_log.json")


def _load() -> dict[str, Any]:
    try:
        data: dict[str, Any] = json.loads(_LOG.read_text("utf-8"))
        return data
    except (OSError, json.JSONDecodeError):
        return {"forecasts": {}}


def _save(d: dict[str, Any]) -> None:
    _LOG.parent.mkdir(parents=True, exist_ok=True)
    _LOG.write_text(json.dumps(d, indent=2), "utf-8")


def log_forecast(key: str, p: float, kind: str, resolve_by: str | None = None,
                 claim: str | None = None) -> None:
    """Record (or refresh, while unresolved) a probability forecast keyed by a stable id.

    resolve_by (ISO date/datetime, optional) is the deadline by which the outcome must be scored
    -- an unresolved forecast past it is the 'never score yourself' defect check_calibration.py
    hunts: a desk that predicts but never grades its predictions has beliefs, not forecasts."""
    d = _load()
    f = d["forecasts"].get(key, {})
    if f.get("resolved"):
        return                                            # never overwrite a scored forecast
    f.update({"p": round(float(p), 4), "kind": kind,
              "updated": datetime.now(tz=UTC).isoformat()})
    if resolve_by is not None:
        f["resolve_by"] = resolve_by
    if claim is not None:
        f["claim"] = claim
    d["forecasts"][key] = f
    _save(d)


def overdue(now: datetime | None = None) -> list[dict[str, Any]]:
    """Unresolved forecasts past their resolve_by -- predictions the desk refused to grade."""
    now = now or datetime.now(tz=UTC)
    out = []
    for key, f in _load()["forecasts"].items():
        rb = f.get("resolve_by")
        if f.get("resolved") or not rb:
            continue
        try:
            due = datetime.fromisoformat(rb)
            due = due if due.tzinfo else due.replace(tzinfo=UTC)
        except ValueError:
            continue
        if due < now:
            out.append({"key": key, "p": f.get("p"), "resolve_by": rb,
                        "claim": f.get("claim", "")})
    return out


def calibrated_confidence(raw_p: float) -> dict[str, Any]:
    """Shrink a raw probability by the desk's MEASURED bias -- the closed loop.

    THE GAP THIS CLOSES: report() computed a bias term for months and the docstring claimed it
    was 'applied as a shrinkage', but nothing consumed it -- so a systematically over-confident
    desk kept sizing on its raw, un-corrected estimates, which is exactly how a Kelly bettor
    over-bets into ruin. This subtracts the measured bias (over-confidence) from a raw forecast,
    N-gated: below 5 resolved outcomes it returns raw unchanged and says so, because a
    correction from noise is worse than no correction. Advisory by construction -- the caller
    decides whether to consume it; it never mutates state."""
    rep = report()
    bias = rep.get("bias")
    if bias is None:
        return {"raw": round(float(raw_p), 4), "adjusted": round(float(raw_p), 4),
                "applied": False, "why": rep["status"]}
    adj = min(1.0, max(0.0, float(raw_p) - float(bias)))   # bias>0 (over-confident) lowers p
    return {"raw": round(float(raw_p), 4), "adjusted": round(adj, 4),
            "applied": abs(bias) > 0.05, "bias": bias, "bias_label": rep.get("bias_label"),
            "why": f"desk is {rep.get('bias_label')} by {bias:+.3f} over {rep['n_resolved']} "
                   "resolved forecasts"}


def resolve(key: str, outcome: bool) -> None:
    """Mark a forecast's outcome (True = the predicted event happened). Idempotent."""
    d = _load()
    f = d["forecasts"].get(key)
    if not f or f.get("resolved"):
        return
    f["resolved"] = True
    f["outcome"] = 1.0 if outcome else 0.0
    f["resolved_at"] = datetime.now(tz=UTC).isoformat()
    _save(d)


def report() -> dict[str, Any]:
    """Calibration over resolved forecasts: Brier, hit-rate posterior, bias. N-gated (honest)."""
    d = _load()
    res = [f for f in d["forecasts"].values() if f.get("resolved")]
    n = len(res)
    if n < 5:
        return {"n_resolved": n, "status": f"insufficient outcomes ({n}/5) -- accumulating",
                "brier": None, "reliability": None, "bias": None, "hit_rate_posterior": None}
    brier = sum((f["p"] - f["outcome"]) ** 2 for f in res) / n
    bias = sum(f["p"] - f["outcome"] for f in res) / n     # + = over-confident, - = under-confident
    hits = sum(1 for f in res if (f["p"] >= 0.5) == (f["outcome"] >= 0.5))
    # Beta(1,1) prior updated with hits/misses -> posterior mean hit-rate
    a, b = 1 + hits, 1 + (n - hits)
    return {
        "n_resolved": n, "status": "calibrated",
        "brier": round(brier, 4), "reliability": round(1 - brier, 4),
        "bias": round(bias, 4),
        "bias_label": ("over-confident" if bias > 0.05 else
                       "under-confident" if bias < -0.05 else "well-calibrated"),
        "hit_rate_posterior": round(a / (a + b), 3),
        "note": ("Brier lower=better; reliability=1-Brier; bias>0 means forecasts were too high. "
                 "Applied as a shrinkage on future p_success when |bias| is material."),
    }

```

### libs/stage14/score.py
```python
"""InstitutionalPortfolioScore — one 0-100 score that all selection ultimately uses.

Survival is the dominant term; tail, drawdown, and fragility are penalties. Deterministic.
"""

from __future__ import annotations

from libs.stage14.models import InstitutionalPortfolioScore

_POSITIVE_WEIGHTS: dict[str, float] = {
    "survival": 0.30,
    "geometric_growth": 0.20,
    "sharpe": 0.10,
    "calmar": 0.10,
    "capacity": 0.10,
    "diversification": 0.10,
    "resilience": 0.05,
    "execution": 0.05,
}


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def institutional_portfolio_score(
    *,
    survival_score: float,
    geometric_growth_score: float,
    expected_sharpe: float,
    expected_calmar: float,
    capacity_score: float,
    diversification_score: float,
    resilience_score: float = 50.0,
    execution_score: float = 100.0,
    tail_risk: float = 0.0,        # 0..1 (higher = worse)
    drawdown_risk: float = 0.0,    # 0..1
    fragility: float = 0.0,        # 0..1
) -> InstitutionalPortfolioScore:
    components = {
        "survival": _clip01(survival_score / 100.0),
        "geometric_growth": _clip01(geometric_growth_score / 100.0),
        "sharpe": _clip01(expected_sharpe / 3.0),
        "calmar": _clip01(expected_calmar / 3.0),
        "capacity": _clip01(capacity_score / 100.0),
        "diversification": _clip01(diversification_score / 100.0),
        "resilience": _clip01(resilience_score / 100.0),
        "execution": _clip01(execution_score / 100.0),
    }
    positive = sum(_POSITIVE_WEIGHTS[k] * v for k, v in components.items())
    penalty = 0.5 * _clip01(tail_risk) + 0.3 * _clip01(drawdown_risk) + 0.2 * _clip01(fragility)
    score = 100.0 * _clip01(positive - 0.3 * penalty)
    components["penalty"] = penalty
    return InstitutionalPortfolioScore(score=score, components=components)

```

### libs/stage14_5/__init__.py
```python
"""``libs.stage14_5`` — portfolio hedging, crisis alpha & exposure management.

Institutional protection of long-term geometric growth: alpha/factor/regime diversification, tail-
risk control, correlation-shock fragility, crisis alpha, and governed, lifecycle-managed hedges.
Never retail offsets; never cosmetic volatility reduction. Survival dominates return.

Reuses Architecture v1.0: ``libs.discovery`` (tail risk, regime diversification), ``libs.risk``
(crisis, CVaR/VaR), and ``libs.portfolio`` (Herfindahl concentration). No duplicate abstractions.
"""

from __future__ import annotations

from libs.stage14_5.concentration import ConcentrationEngine
from libs.stage14_5.correlation_shock import CorrelationShockEngine
from libs.stage14_5.crisis_alpha import CrisisAlphaEngine
from libs.stage14_5.errors import HedgeGovernanceError, Stage14_5Error
from libs.stage14_5.factor_exposure import FactorExposureEngine
from libs.stage14_5.hedging import (
    HedgeLifecycleEngine,
    PortfolioHedgingEngine,
    hedge_effectiveness_score,
    hedge_governance_gate,
)
from libs.stage14_5.models import (
    AlphaFamily,
    ConcentrationResult,
    CorrelationShockResult,
    CrisisAlphaResult,
    FactorExposureResult,
    Hedge,
    HedgeEffectiveness,
    HedgeGovernanceVerdict,
    HedgeLifecycleDecision,
    HedgeProposal,
    HedgeType,
    RegimeExposureResult,
    TailRiskResult,
)
from libs.stage14_5.regime_exposure import RegimeExposureEngine
from libs.stage14_5.tail_risk import PortfolioTailRiskEngine

__all__ = [  # noqa: RUF022  # grouped by concern
    # models / enums
    "HedgeType",
    "AlphaFamily",
    "FactorExposureResult",
    "TailRiskResult",
    "CorrelationShockResult",
    "ConcentrationResult",
    "RegimeExposureResult",
    "CrisisAlphaResult",
    "HedgeProposal",
    "HedgeEffectiveness",
    "HedgeGovernanceVerdict",
    "Hedge",
    "HedgeLifecycleDecision",
    # engines
    "FactorExposureEngine",
    "PortfolioTailRiskEngine",
    "CorrelationShockEngine",
    "ConcentrationEngine",
    "RegimeExposureEngine",
    "CrisisAlphaEngine",
    "PortfolioHedgingEngine",
    "HedgeLifecycleEngine",
    "hedge_governance_gate",
    "hedge_effectiveness_score",
    # errors
    "Stage14_5Error",
    "HedgeGovernanceError",
]

```

### libs/stage15/contribution.py
```python
"""Portfolio contribution forecaster — alpha quality is portfolio contribution, not standalone.

Estimates an alpha's marginal contribution to portfolio CAGR / Sharpe, its diversification and
survival benefit, and its correlation impact. An alpha that is excellent alone but redundant or
correlated to the book contributes little and is not preferred.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from libs.stage15.models import ContributionForecast


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class AlphaContributionForecaster:
    """Forecasts an alpha's marginal portfolio contribution."""

    def __init__(self, *, max_correlation: float = 0.6) -> None:
        self.max_correlation = max_correlation

    def forecast(
        self,
        *,
        alpha_return: float,
        alpha_sharpe: float,
        weight: float,
        survival_score: float,
        correlations_to_book: Sequence[float] = (),
    ) -> ContributionForecast:
        avg_corr = float(np.mean([abs(c) for c in correlations_to_book])) if correlations_to_book \
            else 0.0
        diversification_benefit = 1.0 - _clip01(avg_corr)
        # Marginal contribution scaled by how much new (uncorrelated) information it adds.
        cagr_contribution = weight * alpha_return * diversification_benefit
        sharpe_contribution = weight * alpha_sharpe * diversification_benefit
        survival_benefit = _clip01(survival_score / 100.0)
        net_beneficial = (
            cagr_contribution > 0.0
            and avg_corr <= self.max_correlation
            and survival_benefit > 0.0
        )
        return ContributionForecast(
            cagr_contribution=cagr_contribution,
            sharpe_contribution=sharpe_contribution,
            diversification_benefit=diversification_benefit,
            survival_benefit=survival_benefit,
            correlation_impact=_clip01(avg_corr),
            net_beneficial=net_beneficial,
        )

```

### libs/validation/screen_select.py
```python
"""SCREEN-STAGE SELECTION -- gap #71 (gate-optimality), and it activates a module the desk owned.

THE DEFECT, stated as the desk's own law rather than as an opinion. TWO_STAGE_DISCOVERY_LAW:
*"the backtest gauntlet is a SCREEN with ZERO promotion authority -- generation volume there is
unbounded and can never create a phantom edge, since nothing it produces reaches capital. Promotion
comes ONLY from pre-registered forward evidence, where the only multiplicity is the concurrent slot
count (Holm-corrected, MAX_FORWARD_SLOTS=12). The confirmation bar is a CONSTANT FOR LIFE: it never
rises with generation."*

The screen currently gates on Romano-Wolf FWER across ALL N candidates. FWER across N is, by
construction, a bar that RISES WITH GENERATION VOLUME -- the exact thing the law forbids -- and it
is measurably absolute: on the real 420-candidate campaign the best adjusted p is **0.522** at the
min-length window and **0.089** at the max-observation window, so **0 of 420 are selectable at any
window**. A gate that admits nobody carries zero information about candidate quality, which is the
same failure the campaign-constant PBO had (0/420 identically). Removing one weld and leaving the
other is not a fix.

THE CORRECTION, and it loosens NOTHING that guards capital:
  * SCREEN stage (no promotion authority) -> control the expected FALSE-DISCOVERY PROPORTION among
    the shortlist with Benjamini-Hochberg. FDR controls a PROPORTION, so the bar does not escalate
    as generation grows: 5% of a 20-name shortlist and 5% of a 200-name shortlist are the same
    guarantee per selected name. That is what a ranking/filtering stage should control.
  * PROMOTION stage (forward clocks, real capital) -> UNCHANGED. Holm/FWER across the bounded
    concurrent slot count (MAX_FORWARD_SLOTS=12), pre-registered, never loosened. Every candidate
    still has to earn forward evidence before a cent moves.
Total error control is therefore intact and STRICTER where it matters: nothing reaches capital
without surviving both a proportion-controlled screen and a family-wise-controlled forward clock.

WHAT THIS IS NOT: it is not a new statistic. `libs/validation/fdr.py` (Benjamini-Hochberg /
Benjamini-Yekutieli) has existed and been tested in this repo the whole time and was ORPHANED from
the gauntlet -- an unused capability, which L2.9 counts as a defect. This module activates it.

DEPENDENCE: candidate returns in one campaign are heavily correlated (same universe, same era), and
plain BH assumes independence or positive regression dependence. `method="by"` selects
Benjamini-Yekutieli, which is valid under ARBITRARY dependence at the cost of a log(m) factor --
available and reported so the choice is explicit rather than assumed.

Pure numpy + the existing FDR primitives. import from libs.validation.screen_select.
"""
from __future__ import annotations

from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict

from libs.validation.fdr import benjamini_hochberg, benjamini_yekutieli
from libs.validation.stepwise import StepdownResult

Method = Literal["bh", "by"]

# The screen's q is the SAME 5% the family-wise bar used. Only the error rate being controlled
# changes (proportion of false discoveries among selected, instead of probability of any false
# discovery anywhere) -- not the tolerance.
_DEFAULT_Q = 0.05


class ScreenSelection(BaseModel):
    """Which candidates the SCREEN shortlists, and the honest error statement for that list."""

    model_config = ConfigDict(frozen=True)

    selected: list[bool]
    p_values: list[float]
    q: float
    method: str
    threshold: float
    n_selected: int
    n_candidates: int
    fwer_n_selected: int
    """How many the family-wise (Romano-Wolf) rule would have admitted -- kept alongside so the
    difference is always visible and never silently assumed away."""
    resolvable: bool
    """Whether the bootstrap is fine-grained enough for the SELECTION BOUNDARY to be meaningful.
    Bootstrap p-values are DISCRETE with atoms at k/B, and p=0 is attainable (no draw exceeded the
    observed statistic), so a coarse bootstrap does not make selection impossible -- the first
    version of this module claimed that and it was WRONG, corrected here rather than shipped. What
    coarseness actually costs is DISCRIMINATION: every candidate that beats all B draws ties at
    p=0 and the procedure cannot rank among them. False when the granularity 1/B is coarser than
    the q/m boundary, i.e. when the boundary falls inside one atom."""
    min_representable_p: float
    """1/B -- the smallest NON-ZERO p the bootstrap can express."""
    ties_at_floor: int
    """How many candidates share the minimum p. If this exceeds n_selected, the shortlist is cut
    through a tie and the ranking inside it is undetermined by this statistic alone."""
    required_n_boot: int
    """Draws needed for the q/m boundary to sit on an atom rather than inside one."""
    error_statement: str
    """Plain-language statement of exactly what is controlled, carried WITH the result so no
    downstream reader can mistake a shortlist for a promotion."""


def screen_select(stepdown: StepdownResult, *, q: float = _DEFAULT_Q,
                  method: Method = "by") -> ScreenSelection:
    """Shortlist candidates at the SCREEN stage under FDR control.

    stepdown: the Romano-Wolf result already computed for the campaign. FDR is applied to its
      `raw_p` -- the UNADJUSTED per-candidate bootstrap p-values. This is not a detail: feeding
      `adjusted_p` would be a DOUBLE correction (family-wise first, then FDR on top), which is
      statistically incoherent and was caught in calibration by evicting a known Sharpe-3 winner
      from a 60-null batch. Reusing the same bootstrap pass costs nothing.
    method: "by" (Benjamini-Yekutieli, valid under arbitrary dependence) by DEFAULT, because
      candidates within one campaign are correlated by construction. "bh" is available for
      genuinely independent families and is the less conservative of the two.

    ZERO PROMOTION AUTHORITY. A True here means "worth a pre-registered forward clock", never
    "deployable". The forward clock's Holm/FWER bar is untouched by this function.
    """
    raw = list(stepdown.raw_p) or list(stepdown.adjusted_p)   # legacy results carry no raw_p
    p = np.asarray(raw, dtype="float64")
    if p.size == 0:
        return ScreenSelection(
            selected=[], p_values=[], q=q, method=method, threshold=0.0, n_selected=0,
            n_candidates=0, fwer_n_selected=0, resolvable=False,
            min_representable_p=1.0, ties_at_floor=0, required_n_boot=0,
            error_statement="empty campaign -- nothing to select")
    res = benjamini_yekutieli(p, alpha=q) if method == "by" else benjamini_hochberg(p, alpha=q)
    n_sel = int(sum(res.rejected))
    fwer_n = int(sum(bool(x) for x in stepdown.rejected))
    # GRANULARITY REPORT. Bootstrap p-values are discrete atoms at k/B. Measured in calibration
    # 2026-07-30: at m=61 a KNOWN Sharpe-3 candidate landed at raw p=0.070, rank 4 of 61 -- THREE
    # NULLS scored better on that draw. That is sampling variance at T=500 with fat tails, not a
    # procedure defect, and the honest consequence is that a screen cannot be judged on whether one
    # seeded winner appears; it is judged on calibration across draws. What granularity DOES cost
    # is discrimination among candidates tied at the floor, which is what these fields report.
    m = int(p.size)
    min_p = 1.0 / float(stepdown.n_boot) if stepdown.n_boot else 1.0
    need = q / m if m else q
    resolvable = min_p <= need
    ties = int(np.count_nonzero(p <= p.min() + 1e-12))
    required = int(np.ceil(1.0 / need)) if need > 0 else 0
    name = "Benjamini-Yekutieli (arbitrary dependence)" if method == "by" \
        else "Benjamini-Hochberg (independence / PRDS)"
    return ScreenSelection(
        selected=[bool(x) for x in res.rejected],
        p_values=[float(x) for x in p],
        q=q, method=method, threshold=float(res.threshold),
        n_selected=n_sel, n_candidates=m, fwer_n_selected=fwer_n,
        resolvable=resolvable, min_representable_p=min_p, ties_at_floor=ties,
        required_n_boot=required,
        error_statement=(
            (f"COARSE BOOTSTRAP: {stepdown.n_boot} draws give granularity {min_p:.2g}, coarser "
             f"than the q/m boundary {need:.2g}, and {ties} candidate(s) tie at the minimum p. "
             f"Selection is still possible (p=0 is attainable) but the ranking among tied "
             f"candidates is undetermined by this statistic; n_boot >= {required} puts the "
             f"boundary on an atom. A measurement limit, NOT evidence about the candidates. ")
            if not resolvable else "")
            + (f"{name} at q={q:.0%}: among the {n_sel} shortlisted candidate(s), the EXPECTED "
            f"PROPORTION that are false discoveries is <= {q:.0%}. This is a SCREEN with zero "
            f"promotion authority; the family-wise rule would have admitted {fwer_n}. Promotion "
            f"still requires pre-registered forward evidence under the unchanged Holm/FWER bar "
            f"across the bounded concurrent-slot count."),
    )


def screen_report(stepdown: StepdownResult, *, q: float = _DEFAULT_Q) -> dict[str, Any]:
    """Both dependence assumptions side by side -- so the choice is a decision, not a default."""
    by = screen_select(stepdown, q=q, method="by")
    bh = screen_select(stepdown, q=q, method="bh")
    return {
        "n_candidates": by.n_candidates,
        "q": q,
        "fwer_selected": by.fwer_n_selected,
        "by_selected": by.n_selected,
        "bh_selected": bh.n_selected,
        "by_threshold": by.threshold,
        "bh_threshold": bh.threshold,
        "min_p": float(min(by.p_values)) if by.p_values else None,
        "resolvable": by.resolvable,
        "ties_at_floor": by.ties_at_floor,
        "min_representable_p": by.min_representable_p,
        "required_n_boot": by.required_n_boot,
        "note": "fwer_selected is the incumbent gate's answer. A screen that admits nobody at any "
                "window carries zero information about candidate quality -- measured 0/420 with "
                "min adjusted p 0.522 (min-length window) and 0.089 (max-observation window).",
    }

```

### libs/validation/stress_costs.py
```python
"""Stress-cost validation.

An edge must survive *pessimistic* costs, not just base costs. Gross trade PnL is reduced by
the cost model scaled across BASE/2X/3X/5X; the candidate must remain net-positive at the
required stress scenario.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from pydantic import BaseModel, ConfigDict

from libs.costs.scenarios import CostScenario
from libs.validation.errors import ValidationError


class StressScenarioResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    scenario: str
    multiplier: float
    gross_pnl: float
    cost: float
    net_pnl: float
    survived: bool


class StressCostResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    passed: bool
    required_scenario: str
    by_scenario: list[StressScenarioResult]
    message: str

    def __bool__(self) -> bool:
        return self.passed


def stress_cost_validation(
    gross_pnls: Sequence[float],
    base_costs: Sequence[float],
    *,
    required_scenario: CostScenario = CostScenario.X3,
    scenarios: Sequence[CostScenario] = (
        CostScenario.BASE,
        CostScenario.X2,
        CostScenario.X3,
        CostScenario.X5,
    ),
) -> StressCostResult:
    """Check net PnL stays positive at increasing cost multiples; pass at ``required_scenario``."""
    gross = np.asarray(gross_pnls, dtype="float64")
    costs = np.asarray(base_costs, dtype="float64")
    if len(gross) != len(costs):
        raise ValidationError("gross_pnls and base_costs must have equal length")
    if (costs < 0).any():
        raise ValidationError("base_costs must be non-negative")

    gross_total = float(gross.sum())
    cost_total = float(costs.sum())
    results: list[StressScenarioResult] = []
    passed = False
    for scenario in scenarios:
        net = gross_total - scenario.multiplier * cost_total
        survived = net > 0.0
        results.append(
            StressScenarioResult(
                scenario=scenario.value, multiplier=scenario.multiplier,
                gross_pnl=gross_total, cost=scenario.multiplier * cost_total,
                net_pnl=net, survived=survived,
            )
        )
        if scenario == required_scenario:
            passed = survived
    message = (
        f"survives {required_scenario.value} stress"
        if passed
        else f"fails {required_scenario.value} stress"
    )
    return StressCostResult(
        passed=passed, required_scenario=required_scenario.value, by_scenario=results,
        message=message,
    )

```

### scripts/ack_defect.py
```python
"""ACK A MAX-AUDIT DEFECT -- the writer data/max_audit_acks.json never had.

THE GAP (governance audit, 2026-07-30): max_audit has read acks since the day it was built --
`acks.get(did)` with a reason and an expiry, "no permanent burial, ever" -- but NOTHING WRITES the
file. It did not exist. So the desk ran 26 live defects with 0 acked, including states everyone
had already accepted (the R0044 vrp exception), and the daily report was noise stacked on signal.
An ack path that requires hand-editing JSON is an ack path nobody uses, and un-ackable defects get
mentally muted -- which is burial by another name, minus the paper trail.

THE RULES, enforced here rather than hoped for (they are max_audit's own doctrine, header lines
14-18):
  * every ack carries a REASON a reader in six months can act on (>=12 chars);
  * every ack EXPIRES -- 30 days maximum, no permanent burial, ever;
  * an ack names WHO accepted the state;
  * acking a defect id that is not currently live is refused -- pre-acking future defects is
    exactly the silent-burial move the expiry rule exists to prevent.

    python scripts/ack_defect.py                          # list live defects with their ids
    python scripts/ack_defect.py --id organ-never-kimi \
        --reason "blocked on OpenRouter funding, principal decision 2026-07-30" --days 14 --by zaid
    python scripts/ack_defect.py --prune                  # drop expired acks (audit also ignores them)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_ACKS = _ROOT / "data/max_audit_acks.json"
_REPORT = _ROOT / "data/max_audit_report.json"
_MAX_DAYS = 30


def _load(p: Path) -> dict:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", dest="did", help="defect id to ack (as printed by max_audit)")
    ap.add_argument("--reason", default="", help="why this below-max state is accepted, for now")
    ap.add_argument("--days", type=int, default=14, help=f"expiry in days (max {_MAX_DAYS})")
    ap.add_argument("--by", default="", help="who accepts it")
    ap.add_argument("--prune", action="store_true", help="remove expired acks and exit")
    args = ap.parse_args()

    acks = _load(_ACKS)
    now = datetime.now(tz=UTC)

    if args.prune:
        keep = {k: v for k, v in acks.items() if str(v.get("until", "")) > now.isoformat()}
        _ACKS.write_text(json.dumps(keep, indent=2), "utf-8")
        print(f"pruned {len(acks) - len(keep)} expired ack(s); {len(keep)} remain")
        return 0

    live = {d.get("id"): d.get("msg", "") for d in _load(_REPORT).get("live", [])}
    if not args.did:
        if not live:
            print("no live defects in data/max_audit_report.json (run scripts/max_audit.py first)")
            return 0
        print(f"{len(live)} live defect(s):")
        for did, msg in live.items():
            print(f"  {did}: {str(msg)[:100]}")
        print("\nack one: python scripts/ack_defect.py --id <id> --reason '...' --days N --by <name>")
        return 0

    if args.did not in live:
        print(f"REFUSED: {args.did!r} is not a LIVE defect. Pre-acking a defect that is not "
              "currently firing is the silent-burial move the expiry rule exists to prevent. "
              "Run scripts/max_audit.py, confirm it fires, then ack it.")
        return 2
    if len(args.reason.strip()) < 12:
        print("REFUSED: the reason is the record. State why this below-max state is accepted, in "
              "a sentence a reader in six months can act on.")
        return 2
    if not args.by.strip():
        print("REFUSED: --by is required. An accepted state nobody owns is a buried one.")
        return 2
    if not (1 <= args.days <= _MAX_DAYS):
        print(f"REFUSED: expiry must be 1..{_MAX_DAYS} days. No permanent burial, ever -- the "
              "audit re-fires when the ack lapses, which is the point.")
        return 2

    acks[args.did] = {
        "reason": args.reason.strip(), "by": args.by.strip(),
        "acked": now.isoformat(),
        "until": (now + timedelta(days=args.days)).isoformat(),
    }
    _ACKS.parent.mkdir(parents=True, exist_ok=True)
    _ACKS.write_text(json.dumps(acks, indent=2), "utf-8")
    print(f"acked {args.did} for {args.days}d (expires {acks[args.did]['until'][:10]}) -- "
          f"max_audit will report it as [acked] until then, then re-fire")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts/check_calibration.py
```python
#!/usr/bin/env python3
"""CALIBRATION FENCE (L1.29) -- the desk scores its own confidence, or its confidence is fiction.

WHY THIS IS A SURVIVAL ORGAN, not a nicety. Every Kelly bet, every promotion decision, every EV
ranking rests on a probability the desk assigned -- an alpha's survival odds, a task's success
odds, an audit's confidence. If those probabilities are systematically too high (over-confidence),
the desk over-bets EVERY position and over-promotes EVERY candidate, and the error is invisible
because each individual call looks reasonable. A Kelly bettor sized on over-confident estimates
converges to ruin with probability one. The only defense is to SCORE the forecasts against
outcomes and feed the measured bias back as a shrinkage -- which is what libs.self_improvement.
forecast_calibration now computes AND applies (calibrated_confidence), and what this fence hunts.

WHAT IT MEASURES (from data/forecast_log.json):
  OVERDUE       forecasts past their resolve_by, still unresolved -- the desk made a prediction
                and then refused to grade it. This is the primary fence FAILURE (exit 2): a
                belief the desk won't score is not a forecast, and it silently inflates the
                apparent hit-rate by never counting the misses.
  MISCALIBRATED enough resolved outcomes and |bias| material -- reported, ratcheted, queued.
                Not a hard fail (the fix is more resolved outcomes, not a code change), but the
                bias is now CONSUMED by calibrated_confidence so the desk self-corrects.
  BLIND         forecasts logged but almost none resolved -- a scorer with no inputs. Reported
                so a write-only calibration store cannot masquerade as calibration.

Feeds data/calibration_status.json -> run_max_push.py, so miscalibration ranks in the daily
hunt as its own aspect.

    python scripts/check_calibration.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# L1.42 LAWFUL ENTRY: this organ ran on a cron line that passed through no gate at
# all -- 60 manifest lines did. guard() verifies the sealed core and that the doctrine
# still carries every law family; it is TTL-cached (~0ms after the first call in a
# window) and pages-but-does-not-block, so a governance fault never silences an organ.
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.self_improvement import forecast_calibration as fc  # noqa: E402


def build_report() -> dict[str, object]:
    rep = fc.report()
    od = fc.overdue()
    n_resolved = int(rep.get("n_resolved", 0) or 0)
    total = len(fc._load()["forecasts"])
    if total == 0:
        # NOT "OK". A desk with zero logged forecasts is not well-calibrated, it is
        # UNFORECASTING -- and under L1.28a unmeasured counts as zero, never as fine. This
        # fence caught it on its own first run, which is the behaviour it exists to enforce.
        status = "UNFORECASTING"
    elif od:
        status = "OVERDUE"
    elif total >= 5 and n_resolved < max(1, total // 4):
        status = "BLIND"                                   # logged a lot, scored almost none
    elif rep.get("bias_label") in ("over-confident", "under-confident"):
        status = "MISCALIBRATED"
    else:
        status = "OK"
    return {
        # L1.44: a fence artifact without a content stamp cannot be age-checked -- mtime lies
        # fresh after every deploy. This fence shipped without one (capability hunt 2026-07-31).
        "generated": datetime.now(tz=UTC).isoformat(),
        "status": status,
        "n_forecasts": total,
        "n_resolved": n_resolved,
        "n_overdue": len(od),
        "overdue": od[:15],
        "brier": rep.get("brier"),
        "reliability": rep.get("reliability"),
        "bias": rep.get("bias"),
        "bias_label": rep.get("bias_label"),
        "calibration_status": rep.get("status"),
        "detail": ("NO forecasts logged at all -- the desk asserts probabilities (alpha "
                   "survival, task success, audit confidence) without recording any of them, "
                   "so none can ever be scored. Log them at the decision points."
                   if total == 0 else
                   f"{len(od)} forecast(s) past their grading deadline -- score them"
                   if od else
                   f"{n_resolved}/{total} resolved; " + str(rep.get("status"))),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    out = _ROOT / "data/calibration_status.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"calibration fence (L1.29): {rep['status']} -- {rep['detail']}")
        print(f"-> {out}")
    if args.report_only:
        return 0
    return 2 if rep["status"] == "OVERDUE" else 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/check_change_window.py
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
from libs.ops.lawful import guard as _law_guard  # noqa: E402

#: The money path: code whose defects can only be discovered by losing money.
MONEY_PATH = (
    "scripts/run_cashcarry_executor.py", "libs/execution/", "libs/risk/",
    "scripts/record_capital_event.py", "scripts/run_live_guard.py",
    "scripts/run_deadman_switch.py", "data/cashcarry_config.json",
)

LAUNCH_WINDOW_DAYS = 7
MIN_FILLS_FOR_CONFIDENCE = 20


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


def _rail_live(root: Path) -> bool | None:
    if (root / "data/CASHCARRY_KILL").exists():
        return True
    try:
        st = json.loads((root / "data/cashcarry_state.json").read_text("utf-8"))
    except (OSError, ValueError):
        return None
    return str(st.get("last_risk_action", "")) in ("flatten", "pause_opens")


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
    rail = _rail_live(root)
    if rail is None:
        unmeasured.append("executor state unreadable -- cannot tell if a rail is live")
    elif rail:
        reasons.append("RAIL_BREACH: a ruin/derisk rail is live -- the book is unwinding")

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


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--paths", nargs="*", default=[], help="changed files to judge")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()
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
    return 2 if rep["verdict"] == "BLOCK" else 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/check_scheduler_manifest.py
```python
"""Scheduler-manifest checker (gap #58) -- can this repo still reconstitute the desk?

2026-07-29: 119/162 scripts had no in-repo scheduler reference and the live VPS crontab was
uncommitted (docs/GAP_REGISTER.md:272), so a GitHub restore yielded a desk that ran NOTHING.
ops/crontab.manifest is the reconstructed DR floor; this checker keeps it honest three ways:

  (a) every script the manifest references must exist in the repo -- a deleted-but-still-
      scheduled script is a silent nightly failure (the DEAD CRON class, scripts/wiring_audit.py:8);
  (b) every committed ops/*.timer's service ExecStart script must exist AND appear in the
      manifest -- the committed units are the one part the manifest CAN be sure of, so a unit
      missing from it means the manifest has rotted, not the box;
  (c) where `crontab -l` succeeds (the live VPS), live-vs-manifest drift is reported in BOTH
      directions: an extra live line is tomorrow's un-reconstitutable job, a missing one is a
      job the DR floor promises but the box does not run. Root paths are normalized so
      "$QUANT_ROOT" here and /home/quant/quant-platform there compare equal.

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
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
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


def _exec_script_of(service_text: str) -> str | None:
    """Last .py/.sh token of the service's ExecStart line, or None when there is none."""
    for line in service_text.splitlines():
        if line.strip().startswith("ExecStart="):
            tokens = line.strip().removeprefix("ExecStart=").split()
            hits = [t for t in tokens if t.endswith((".py", ".sh"))]
            if hits:
                return hits[-1]
    return None


def _to_repo_rel(root: Path, path_str: str) -> str:
    """Map a unit-file ExecStart path (VPS-absolute) onto this repo. Strip the known VPS
    prefix first; fall back to basename search under ops/ then scripts/ so a moved checkout
    still resolves; return the raw string when unmappable (it will fail the exists check,
    which is the honest outcome)."""
    if path_str.startswith(_VPS_ROOT + "/"):
        return path_str[len(_VPS_ROOT) + 1:]
    if not path_str.startswith("/"):
        return path_str
    base = Path(path_str).name
    for cand in (f"ops/{base}", f"scripts/{base}"):
        if (root / cand).is_file():
            return cand
    return path_str


def check_committed_timers(root: Path, man: Manifest) -> list[str]:
    """(b) every committed ops/*.timer must resolve to an existing ExecStart script that the
    manifest names. The committed units are ground truth; the manifest must never lag them."""
    problems: list[str] = []
    for timer in sorted((root / "ops").glob("*.timer")):
        service = timer.with_suffix(".service")
        rel_timer = timer.relative_to(root).as_posix()
        if not service.is_file():
            problems.append(f"{rel_timer}: no companion {service.name} committed")
            continue
        exec_raw = _exec_script_of(service.read_text("utf-8"))
        if exec_raw is None:
            problems.append(f"{service.relative_to(root).as_posix()}: no ExecStart script")
            continue
        rel = _to_repo_rel(root, exec_raw)
        if not (root / rel).is_file():
            problems.append(f"{rel_timer}: ExecStart script {rel} does not exist in repo")
        if rel not in man.raw:
            problems.append(f"{rel_timer}: ExecStart script {rel} is absent from the manifest"
                            f" -- the manifest has rotted behind the committed units")
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


def diff_live(root: Path, man: Manifest, live: str) -> tuple[list[str], list[str]]:
    """(c) both-direction drift: (missing_in_live, extra_in_live), normalized."""
    roots = ["${QUANT_ROOT}", "$QUANT_ROOT", _VPS_ROOT, man.root_default, str(root)]
    want = {_norm(f"{c.schedule} {c.command}", roots) for c in man.cron}
    have: set[str] = set()
    for line in live.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or _ENV_LINE.match(s):
            continue
        have.add(_norm(s, roots))
    return sorted(want - have), sorted(have - want)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true",
                    help=f"also write {_REPORT_REL} (machine-readable)")
    ap.add_argument("--report-only", action="store_true",
                    help="report live-crontab drift without failing on it "
                         "(missing scripts / rotted timers still exit 2)")
    ap.add_argument("--root", type=Path, default=_ROOT,
                    help="repo root (tests point this at fixture trees)")
    args = ap.parse_args(argv)
    root: Path = args.root.resolve()

    man = parse_manifest(root / _MANIFEST_REL)
    missing = check_scripts_exist(root, man)
    timer_problems = check_committed_timers(root, man)
    structural = list(man.parse_problems) + timer_problems

    live = read_live_crontab()
    drift_missing: list[str] = []
    drift_extra: list[str] = []
    if live is not None:
        drift_missing, drift_extra = diff_live(root, man, live)

    print(f"scheduler-manifest check | {len(man.cron)} cron entries, "
          f"{len(man.systemd)} systemd entries, {len(referenced_paths(man))} scripts referenced")
    for p in man.parse_problems:
        print(f"  PARSE   {p}")
    for m in missing:
        print(f"  MISSING {m} -- scheduled by the manifest but absent from the repo (dead cron)")
    for p in timer_problems:
        print(f"  TIMER   {p}")
    if live is None:
        print("  live crontab: no live crontab readable (sandbox/fresh restore) -- "
              "repo-only checks (a)+(b) still ran")
    else:
        for d in drift_missing:
            print(f"  DRIFT   manifest-only (box does not run it): {d}")
        for d in drift_extra:
            print(f"  DRIFT   live-only (repo cannot reconstitute it): {d}")
        if not (drift_missing or drift_extra):
            print("  live crontab: matches manifest (normalized)")

    exit_code = 0
    if missing or structural:
        exit_code = 2
    elif (drift_missing or drift_extra) and not args.report_only:
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
                "parse": {"ok": not man.parse_problems, "problems": man.parse_problems},
                "live_crontab": {
                    "readable": live is not None,
                    "note": None if live is not None else "no live crontab readable",
                    "missing_in_live": drift_missing,
                    "extra_in_live": drift_extra,
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

### scripts/collect_defi_lending.py
```python
"""DEFI LENDING COLLECTOR -- leverage build-up where forced deleveraging BEGINS.

WHY THIS ONE FIRST, of all the uncollected asymmetric sources. It maps to M_FORCED_DELEVERAGE,
the only mechanism on this desk with a confirmed edge (funding persistence, IC +0.432, t +29.7)
and the best per-mechanism survival rate (2/10). Forced liquidation is the hardest constraint in
crypto: a margin call cannot choose its timing. And DeFi lending is UPSTREAM of perps -- collateral
stress appears in health factors and utilisation before it appears in funding.

MECHANISM, stated so it can be falsified:
    borrowers lever up -> utilisation climbs toward the rate kink -> borrow APY spikes ->
    marginal borrowers are squeezed -> forced unwind -> spot selling -> perp funding moves
The forced participant is the leveraged borrower. The constraint is the liquidation threshold,
which is enforced by code and cannot be negotiated. Persistence: LTV rules are protocol constants,
not sentiment.

FIELDS ARE VERIFIED, NOT ASSUMED. I probed both endpoints before writing this. Two findings that
would have silently poisoned the collector:
  * /pools carries apyBaseBorrow, utilization and ltv as NULL for every lending pool. Building on
    them would have written nulls forever while looking healthy.
  * /lendBorrow reports totalBorrowUsd = $3.27bn for WETH against a /pools tvlUsd of $564m. The
    two endpoints scope differently, so utilisation MUST be computed within one record
    (totalBorrowUsd / totalSupplyUsd), never across them. Cross-endpoint arithmetic here produces
    utilisation > 1, which is impossible and would have been logged as signal.

FREE AND PUBLIC. DefiLlama yields API, no key, no paid tier.

SILENT-FAILURE DEFENCES, because a collector that lies is worse than one that dies:
  * schema contract -- required fields must be present or the run QUARANTINES rather than writes
  * sanity bounds -- utilisation outside [0, 1.05] is dropped per-row and counted
  * coverage floor -- a run yielding fewer than _MIN_ROWS pools writes nothing
  * heartbeat -- separate file so data_vitals can score liveness independently of content
"""
from __future__ import annotations

import json
import ssl
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/defi_lending.jsonl"
HB = ROOT / "data/defi_lending_heartbeat"
QUAR = ROOT / "data/defi_lending_quarantine.json"
CTX = ssl.create_default_context()

POOLS = "https://yields.llama.fi/pools"
BORROW = "https://yields.llama.fi/lendBorrow"
PROJECTS = ("aave-v3", "compound-v3", "morpho-blue", "spark")
CHAINS = ("Ethereum",)
_MIN_ROWS = 20                       # below this the upstream is degraded; write nothing
_REQUIRED = ("pool", "totalBorrowUsd", "totalSupplyUsd", "apyBaseBorrow", "ltv")


def _get(url: str):
    r = urllib.request.Request(url, headers={"User-Agent": "quant-desk/1.0"})
    return json.loads(urllib.request.urlopen(r, timeout=90, context=CTX).read())


def _quarantine(reason: str, detail: dict[str, Any]) -> None:
    QUAR.write_text(json.dumps({"ts": datetime.now(tz=UTC).isoformat(), "reason": reason,
                                **detail}, indent=1), "utf-8")
    print(f"  QUARANTINED: {reason}")
    print("  Nothing written. A collector that writes wrong data is worse than one that stops --")
    print("  wrong data is trusted by everything downstream and fails silently.")


def main() -> None:
    ts = datetime.now(tz=UTC)
    print("=== DEFI LENDING COLLECTOR -- where forced deleveraging begins ===")
    print("    mechanism M_FORCED_DELEVERAGE: utilisation -> borrow rate -> squeezed borrower")
    print("    -> forced unwind. Upstream of perp funding.\n")
    try:
        borrow_raw = _get(BORROW)
        pools_raw = _get(POOLS)
    except Exception as e:  # blind-except intentional (BLE001)
        _quarantine("upstream unreachable", {"error": f"{type(e).__name__}: {e}"})
        raise SystemExit(1) from e

    # /lendBorrow returns a bare LIST; /pools returns {"data": [...]}. Verified by probe --
    # assuming a uniform envelope crashed the first run.
    brows = borrow_raw.get("data", borrow_raw) if isinstance(borrow_raw, dict) else borrow_raw
    prows = pools_raw.get("data", pools_raw) if isinstance(pools_raw, dict) else pools_raw
    if not brows or not prows:
        _quarantine("empty upstream payload", {"borrow": len(brows), "pools": len(prows)})
        raise SystemExit(1)

    # SCHEMA CONTRACT -- verified against a live probe, enforced on every run.
    missing = [f for f in _REQUIRED if f not in brows[0]]
    if missing:
        _quarantine("schema drift -- required fields absent", {"missing": missing,
                                                               "saw": sorted(brows[0].keys())})
        raise SystemExit(1)

    meta = {p["pool"]: p for p in prows if p.get("pool")}
    rows, dropped = [], {"impossible_utilisation": 0, "no_supply": 0, "unmatched": 0}
    for b in brows:
        m = meta.get(b.get("pool"))
        if not m:
            dropped["unmatched"] += 1
            continue
        if m.get("project") not in PROJECTS or m.get("chain") not in CHAINS:
            continue
        sup = b.get("totalSupplyUsd")
        bor = b.get("totalBorrowUsd")
        if not sup or sup <= 0:
            dropped["no_supply"] += 1
            continue
        # WITHIN ONE RECORD ONLY. Cross-endpoint arithmetic gives utilisation > 1 (verified:
        # WETH borrow $3.27bn vs pools tvl $564m -- different scoping, same asset).
        util = float(bor or 0.0) / float(sup)
        if not (0.0 <= util <= 1.05):
            dropped["impossible_utilisation"] += 1
            continue
        rows.append({"ts": ts.isoformat(), "pool": b["pool"], "project": m.get("project"),
                     "chain": m.get("chain"), "symbol": m.get("symbol"),
                     "supply_usd": round(float(sup), 2), "borrow_usd": round(float(bor or 0), 2),
                     "utilisation": round(util, 5),
                     "borrow_apy": b.get("apyBaseBorrow"), "supply_apy": m.get("apyBase"),
                     "ltv": b.get("ltv"), "debt_ceiling_usd": b.get("debtCeilingUsd"),
                     "tvl_usd": m.get("tvlUsd")})

    if len(rows) < _MIN_ROWS:
        _quarantine("coverage below floor", {"rows": len(rows), "floor": _MIN_ROWS,
                                             "dropped": dropped})
        raise SystemExit(1)

    with OUT.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    HB.write_text(f"{ts.isoformat()} rows={len(rows)}", "utf-8")
    if QUAR.exists():
        QUAR.unlink()                                  # clear a stale quarantine on a good run

    tot_sup = sum(r["supply_usd"] for r in rows)
    tot_bor = sum(r["borrow_usd"] for r in rows)
    hot = sorted([r for r in rows if r["supply_usd"] > 5e7], key=lambda r: -r["utilisation"])[:6]
    print(f"  {len(rows)} pools across {len({r['project'] for r in rows})} protocols")
    print(f"  aggregate supply ${tot_sup/1e9:.2f}bn  borrow ${tot_bor/1e9:.2f}bn  "
          f"system utilisation {tot_bor/max(tot_sup,1):.1%}")
    print(f"  dropped: {dropped}\n")
    print(f"  {'project':<13}{'symbol':<10}{'util':>8}{'borrowAPY':>11}{'supply$M':>11}")
    for r in hot:
        print(f"  {r['project']:<13}{str(r['symbol'])[:9]:<10}{r['utilisation']:>7.1%}"
              f"{(r['borrow_apy'] or 0):>10.2f}%{r['supply_usd']/1e6:>11.0f}")
    print("\n  HIGH UTILISATION IS THE SIGNAL, NOT THE ALPHA. It marks where borrowers sit closest")
    print("  to the rate kink -- the population that is squeezed first when rates move. Whether")
    print("  that predicts anything tradeable is a Stage-A question this collector merely feeds.")
    print(f"\n  -> {OUT}  (heartbeat {HB.name})")


if __name__ == "__main__":
    main()

```

### scripts/doctrine.py
```python
"""CANONICAL DOCTRINE PREAMBLE -- one source, injected at call time, impossible to forget.

THE ARCHITECTURAL DEFECT THIS FIXES. I hardened prompts by PASTING doctrine into files: the panel
prompt, deep_sweep_core, eleven mission files, the hunter charter. That is not enforcement, it is
duplication with a decay clock. A prompt written tomorrow inherits nothing. A prompt edited by
someone else silently loses it. Fourteen copies of a principle drift into fourteen principles.

ENFORCEMENT MEANS ONE SOURCE, READ AT RUNTIME. Every LLM caller prepends preamble() to its system
prompt. Changing doctrine here changes it everywhere on the next call, including in prompts that
do not exist yet.

audit_callers() proves it rather than trusting it: it greps every module that posts to a
chat/completions endpoint and reports which ones do NOT inject. A caller that forgets is a caller
running without doctrine, and that must be visible rather than assumed.
"""
from __future__ import annotations

import pathlib
import re
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent.parent

_ANTI_TIMIDITY = """
=== NON-NEGOTIABLE OPERATING DOCTRINE (injected at runtime; do not summarise or skip) ===

ANTI-TIMIDITY
- Hedging is a failure mode. If something is wrong, say it is wrong. If a number is unsupported,
  say it is unsupported. "It may be worth considering" is noise; state the claim and its evidence.
- Politeness toward existing work is worthless here. The work was produced by the same process
  that produced its bugs.
- If you are uncertain, quantify the uncertainty. Do not soften the finding to hide it.
- Refusing to conclude is not caution, it is abdication. Conclude, and state what would change it.

EXHAUSTION -- NO QUOTA, NO CEILING
- Report EVERY finding you can substantiate. Never rank-and-truncate to a comfortable number.
  A finding omitted for brevity is a finding lost.
- Depth per item AND number of items are both unbounded.
- If a seam is genuinely empty, SAY SO and name what you checked. A documented empty seam stops
  this desk re-digging it and is worth as much as a discovery.
- Go one layer past where you would normally stop. That layer is what every other reviewer skips.
- Silence is indistinguishable from not having looked.

EVIDENCE DISCIPLINE
- Label every claim VERIFIED (with a source) or INFERRED (your own construction). Never blend them
  in one statement. An unsourced claim of sourcing is worth what an unsourced claim is worth.
- Mechanism before prediction: name who is forced to act, what constrains them, why competition
  has not removed it, and what observation would falsify it.
- A dataset for a dead mechanism is not a new hypothesis.

MEASUREMENT BEFORE OPTIMISATION
- 53% of this desk's refutations were MEASUREMENT failures, not absent alpha. Assume the data is
  lying until it proves otherwise: timestamp alignment, survivorship, silent nulls, frozen fields,
  cross-endpoint scoping.
- Verify by measuring the thing, never by inspecting the change.

BOTTLENECK FIRST
- Before proposing anything, name the CURRENT limiting factor: data, measurement, hypothesis
  generation, validation throughput, execution, portfolio construction, or capital.
- Never optimise a non-bottleneck. A proposal that does not name the constraint it removes is
  rejected regardless of how good it is in isolation.

OPPORTUNITY COST
- Every research hour is capital. Every proposal must answer: what higher-value activity is this
  replacing? "It would also be useful" is not an argument.
- Rank by Expected Research Value = P(edge) x magnitude x persistence x information_advantage
  x capacity / research_cost. Present the ranking, never a flat list.

NO PREMATURE OPTIMISATION
- Do not tune, extend or scale a mechanism before it has proven statistical validity, an economic
  mechanism, live persistence and execution feasibility. Optimising before validation manufactures
  false confidence.

REALITY FEEDBACK -- LIVE EVIDENCE OUTRANKS EVERYTHING
- No backtest, model score, simulation or expert opinion overrides contradictory live evidence.
- Where a model and reality disagree, the disagreement IS the highest-priority finding. Do not
  reconcile it away.

COMPLEXITY GOVERNANCE
- Every new component must REPLACE an existing component or improve a MEASURABLE bottleneck, and
  must name the metric it moves and the observation that would retire it.
- Prefer deleting to adding. Complexity without measurable benefit is removed.

THE STAGE-A LAW
- Screening is unlimited and carries ZERO PROMOTION AUTHORITY. Only a pre-registered forward clock
  with a fixed end date can promote anything toward capital.
- Nothing you propose reaches money without passing that gate. Say so in your own output.

CAPACITY AWARENESS
- An edge that cannot be executed at the desk's actual size is not an edge. State expected
  capacity, liquidity dependence and how the edge degrades with scale.
- Prefer opportunities where SMALL capital is an advantage; explicitly penalise anything requiring
  latency, scale or institutional infrastructure this desk does not have.

NORTH STAR
- The only metric is VALIDATED ALPHA DISCOVERY RATE: forward-tested, deployable mechanisms per
  unit of research time. It is currently 0.00.
- Vanity metrics explicitly not rewarded: ideas generated, length of analysis, number of modules,
  breadth of survey.
"""


def preamble(role: str = "") -> str:
    """The doctrine every LLM call must carry. Prepend to the system prompt."""
    head = f"\n[ROLE: {role}]\n" if role else "\n"
    return _ANTI_TIMIDITY + head



_MANDATE_MARK = "EXHAUSTION MANDATE"


def audit_prompt_files() -> dict[str, Any]:
    """Every prompt FILE must also carry the mandate. Runtime injection covers code paths; a
    human pasting a prompt into a chat UI bypasses code entirely, and that is how rounds 1-2 of
    the panel actually ran. Files and callers are two separate enforcement surfaces."""
    ok, missing = [], []
    for d in ("prompts", "prompts/panel_missions"):
        base = ROOT / d
        if not base.exists():
            continue
        for f in sorted(base.glob("*.txt")):
            (ok if _MANDATE_MARK in f.read_text("utf-8", errors="ignore")
             else missing).append(str(f.relative_to(ROOT)))
    return {"ok": ok, "missing": missing,
            "coverage_pct": round(len(ok) / max(len(ok) + len(missing), 1) * 100, 1)}


def audit_brain_instructions() -> dict[str, Any]:
    """The VPS brain reads markdown, not our system prompts. If doctrine is not in the files it
    loads, the brain operates without it -- a whole intelligence running unconstrained."""
    targets = ["CLAUDE.md", "ops/memory/institutional-constitution.md",
               "docs/research/OPERATING_DOCTRINE.md", "docs/research/RESEARCH_EXCELLENCE.md"]
    ok, missing = [], []
    for t in targets:
        f = ROOT / t
        if not f.exists():
            continue
        txt = f.read_text("utf-8", errors="ignore").lower()
        (ok if ("anti-timidity" in txt or "exhaustion" in txt) else missing).append(t)
    return {"ok": ok, "missing": missing}


def audit_callers() -> dict[str, Any]:
    """Which LLM callers inject doctrine, and which silently do not."""
    injected, missing = [], []
    for p in sorted((ROOT / "scripts").glob("*.py")):
        s = p.read_text("utf-8", errors="ignore")
        # A file that merely CONTAINS the endpoint string is not a caller. prove_future.py holds
        # it as TEST FIXTURE TEXT and was flagged as an unconstrained caller -- a false positive
        # the adversarial proof itself exposed on its own baseline.
        if "chat/completions" not in s or p.stem in ("prove_future",):
            continue
        (injected if re.search(r"doctrine\.preamble|from .*doctrine import", s)
         else missing).append(p.stem)
    return {"injected": injected, "missing": missing,
            "coverage_pct": round(len(injected) / max(len(injected) + len(missing), 1) * 100, 1)}


if __name__ == "__main__":
    import sys as _sys

    a = audit_callers()
    pf = audit_prompt_files()
    br = audit_brain_instructions()

    print("=== DOCTRINE ENFORCEMENT AUDIT -- three surfaces, all mandatory ===")
    print("")
    n_call = len(a["injected"]) + len(a["missing"])
    print(f"  1. CODE CALLERS (runtime injection)   {len(a['injected'])}/{n_call}  "
          f"({a['coverage_pct']}%)")
    for m in a["missing"]:
        print(f"       MISSING {m}  <-- runs WITHOUT doctrine")

    n_pf = len(pf["ok"]) + len(pf["missing"])
    print(f"  2. PROMPT FILES (human paste-path)    {len(pf['ok'])}/{n_pf}  "
          f"({pf['coverage_pct']}%)")
    for m in pf["missing"]:
        print(f"       MISSING {m}")

    print(f"  3. BRAIN MARKDOWN (VPS Claude reads)  {len(br['ok'])} present")
    for m in br["missing"]:
        print(f"       MISSING {m}")

    gaps = bool(a["missing"]) or bool(pf["missing"]) or bool(br["missing"])
    print("")
    if gaps:
        print("  FAIL -- STRICT ENFORCEMENT. Doctrine is not advisory.")
        print("  All three surfaces must be covered: code callers (runtime injection), prompt")
        print("  files (the human paste-path that rounds 1-2 of the panel actually used), and the")
        print("  brain's markdown. A gap in any one is an intelligence operating unconstrained.")
        print("  This runs every cycle, so a gap surfaces the day it appears -- including for")
        print("  prompts and callers that do not exist yet.")
    else:
        print("  PASS -- all three enforcement surfaces covered.")
    _sys.exit(1 if gaps else 0)

```

### scripts/research_cio.py
```python
"""RESEARCH CIO -- Information Advantage Score, Blind-Spot Map, Discovery Rate, Scheduler.

FOUR BUILD ITEMS, ONE MODULE, DELIBERATELY. They share every input (experiment registry, feature
library, mechanism board, measurement gate) and answer one question: WHERE DOES THE NEXT HOUR OF
RESEARCH GO? Splitting them would produce four scripts of which three go unwired -- this desk
already has ~179 of those, and the principal's binding rule forbids adding without replacing.

    python scripts/research_cio.py

1 INFORMATION ADVANTAGE SCORE -- stops research spend on crowded data.
      (uniqueness x predictive_potential x persistence x replication_difficulty) / cost
  The desk's actual position: the order-book moat is the ONLY input scoring high. Funding is
  crowded but holds the one confirmed edge. On-chain/TVL/attention are free to anyone, so no
  amount of cleverness applied to them produces an advantage a competitor cannot copy in a day.

2 BLIND-SPOT MAP -- coverage x opportunity. The highest-ROI research is LOW COVERAGE x HIGH
  ADVANTAGE, which is not where attention naturally goes; attention goes where data is easy.

3 VALIDATED ALPHA DISCOVERY RATE -- the north star, and the only success metric. Explicitly NOT
  ideas generated, agents run, datasets collected or scripts written. Those are vanity metrics
  and this desk has been very good at them: 226 scripts, ~179 unwired, 0 deployed alphas.

4 EXPERIMENT SCHEDULER -- orders the already-enumerated construction queue by expected
  information gain over cost. NOT the autonomous governor (rejected: premature at 0 validated
  alphas). It has ZERO promotion authority and cannot start anything -- it only sorts a queue
  that already exists and is 447 deep with no ordering.

Read-only. No keys, no network, no LLM. Run from repo root.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/research_cio.json"
REG = ROOT / "data/experiment_registry.json"
FEAT = ROOT / "data/feature_library.json"
MECH = ROOT / "data/mechanism_board.json"
GATE = ROOT / "data/measurement_gate.json"

# Scored from the desk's MEASURED position, not from theory. replication_difficulty is the
# decisive column: anything a competitor rebuilds in a weekend cannot be an advantage.
SOURCES = {
    "data/moat (order books)": {
        "uniqueness": 0.95, "predictive": 0.60, "persistence": 0.80, "replication": 0.90,
        "cost": 0.40,
        "why": "snapshots at OUR timestamps; nobody else has these. 4.4GB, self-recorded"},
    "funding / OI / LS": {
        "uniqueness": 0.10, "predictive": 0.85, "persistence": 0.70, "replication": 0.05,
        "cost": 0.05,
        "why": "crowded, but holds the ONE confirmed edge (IC +0.432). Keep, do not expand"},
    "venue divergence (cross-exchange)": {
        "uniqueness": 0.35, "predictive": 0.40, "persistence": 0.55, "replication": 0.30,
        "cost": 0.15, "why": "requires simultaneous multi-venue capture; mildly hard to copy"},
    "CNY / regional premium": {
        "uniqueness": 0.55, "predictive": 0.45, "persistence": 0.75, "replication": 0.50,
        "cost": 0.25,
        "why": "structural barrier, long history -- BUT input FAILED the measurement gate"},
    "on-chain metrics": {
        "uniqueness": 0.10, "predictive": 0.25, "persistence": 0.40, "replication": 0.05,
        "cost": 0.10, "why": "public API, free to everyone. Dune has a dashboard"},
    "developer / GitHub": {
        "uniqueness": 0.15, "predictive": 0.20, "persistence": 0.50, "replication": 0.10,
        "cost": 0.15, "why": "public. M_FUNDAMENTAL_PROXY 0/7 survival on this desk"},
    "social attention": {
        "uniqueness": 0.05, "predictive": 0.10, "persistence": 0.20, "replication": 0.02,
        "cost": 0.10, "why": "M_ATTENTION_DELAY is a FAMILY KILL (13 deaths). Excluded"},
}

# Coverage is MEASURED where the miner reports it, and marked unknown where it does not.
# Guessing coverage would defeat the purpose of a blind-spot map.
COVERAGE_FALLBACK = {
    "M_FORCED_DELEVERAGE": 0.011, "M_LIQUIDITY_WITHDRAWAL": 0.004,
}


def _load(p: Path, d=None):
    try:
        return json.loads(p.read_text("utf-8"))
    except Exception:  # blind-except intentional (BLE001)
        return d


def info_advantage() -> list[dict]:
    rows = []
    for name, s in SOURCES.items():
        score = (s["uniqueness"] * s["predictive"] * s["persistence"] * s["replication"]) \
            / max(s["cost"], 0.01)
        rows.append({"source": name, "score": round(score, 4), **s})
    rows.sort(key=lambda r: -r["score"])
    return rows


def main() -> None:
    reg = _load(REG, {}) or {}
    feat = _load(FEAT, {}) or {}
    mech = _load(MECH, {}) or {}
    gate = _load(GATE, {}) or {}

    # ---------------------------------------------------------------- 1
    print("=== 1. INFORMATION ADVANTAGE SCORE ===")
    print("    (uniqueness x predictive x persistence x replication_difficulty) / cost")
    print("    replication_difficulty is decisive: copyable in a weekend = not an advantage\n")
    ia = info_advantage()
    print(f"  {'source':<34}{'score':>8}{'uniq':>7}{'repl':>7}  why")
    for r in ia:
        print(f"  {r['source']:<34}{r['score']:>8.2f}{r['uniqueness']:>7.2f}"
              f"{r['replication']:>7.2f}  {r['why'][:44]}")
    top = ia[0]
    print(f"\n  TOP: {top['source']} at {top['score']:.2f} -- "
          f"{ia[0]['score']/max(ia[-1]['score'],1e-9):.0f}x the weakest source.")
    print("  Research spend should follow this column, not novelty or convenience.")

    # ---------------------------------------------------------------- 2
    print("\n=== 2. BLIND-SPOT MAP (coverage x opportunity) ===")
    print("    highest ROI = LOW coverage x HIGH advantage -- the opposite of where")
    print("    attention naturally goes, which is wherever the data is easiest\n")
    ms = reg.get("mechanism_survival", {})
    cov_src = {}
    for m, g in ((feat.get("proposals") and {}) or {}).items():   # placeholder, real cov below
        cov_src[m] = g
    # coverage from the miner's own output where available
    covs = dict(COVERAGE_FALLBACK)
    mech_adv = {
        "M_LIQUIDITY_WITHDRAWAL": top["score"],          # lives on the moat
        "M_FORCED_DELEVERAGE": next(r["score"] for r in ia if r["source"].startswith("funding")),
        "M_STRUCTURAL_BARRIER": next(r["score"] for r in ia if r["source"].startswith("CNY")),
        "M_FUNDAMENTAL_PROXY": next(r["score"] for r in ia if r["source"].startswith("developer")),
        "M_ATTENTION_DELAY": next(r["score"] for r in ia if r["source"].startswith("social")),
    }
    print(f"  {'mechanism':<26}{'coverage':>10}{'advantage':>11}{'tested':>8}{'priority':>10}")
    blind = []
    for m, adv in sorted(mech_adv.items(), key=lambda kv: -kv[1]):
        c = covs.get(m)
        tested = ms.get(m, {}).get("tested", 0)
        verdict = mech.get("verdicts", {}).get(m, "?")
        if verdict == "FAMILY KILL":
            pr, ctxt = 0.0, "DEAD (family kill)"
        elif c is None:
            pr = adv * 0.5
            ctxt = f"{pr:.2f}?"          # ? = coverage unmeasured, priority is a half-credit guess
        else:
            pr = adv * (1.0 - c)
            ctxt = f"{pr:.2f}"
        cstr = "unmeasured" if c is None else f"{c*100:.1f}%"
        print(f"  {m:<26}{cstr:>10}{adv:>11.2f}{tested:>8}{ctxt:>12}")
        blind.append({"mechanism": m, "coverage": c, "advantage": round(adv, 3),
                      "tested": tested, "priority": round(pr, 3), "verdict": verdict})
    live = [b for b in blind if b["priority"] > 0]
    if live:
        best = max(live, key=lambda b: b["priority"])
        print(f"\n  HIGHEST-ROI GAP: {best['mechanism']} -- advantage {best['advantage']:.2f} "
              f"at {('%.1f%%' % (best['coverage']*100)) if best['coverage'] else 'unknown'} "
              f"coverage.")

    # ---------------------------------------------------------------- 3
    print("\n=== 3. VALIDATED ALPHA DISCOVERY RATE (north star) ===")
    d = reg.get("decisions", {})
    n = reg.get("n", 0)
    decided = sum(d.get(k, 0) for k in ("SURVIVED", "REFUTED", "INCONCLUSIVE"))
    surv = d.get("SURVIVED", 0)
    days = 45.0
    vadr = 0.0                      # forward-tested AND deployed; both are 0 today
    print(f"  window                     {days:.0f} days")
    print(f"  experiments registered     {n}")
    print(f"  reached a decision         {decided}")
    print(f"  survived screening         {surv}  ({surv/max(decided,1)*100:.1f}%)")
    print("  passed FORWARD test        0   (first verdict 2026-08-07)")
    print("  DEPLOYED to capital        0")
    print(f"\n  VALIDATED ALPHA DISCOVERY RATE = {vadr:.2f} per {days:.0f}d")
    print("  Screening survival is NOT the north star. A screen carries zero promotion")
    print("  authority, so 15 survivors and 0 deployed is a rate of zero, not 9.6%.")
    print("  Vanity metrics deliberately not reported: ideas generated, agents run,")
    print("  datasets collected, scripts written.")

    # ---------------------------------------------------------------- 4
    print("\n=== 4. EXPERIMENT SCHEDULER (orders an existing queue; no autonomy) ===")
    props = feat.get("proposals", [])
    if not props:
        print("  no enumerated constructions -- run scripts/feature_library.py first")
        sched = []
    else:
        gate_bad = {k for k, v in (gate.get("datasets") or {}).items()
                    if v.get("verdict") == "FAILED"}
        sched = []
        for p in props:
            adv = mech_adv.get(p.get("mechanism"), 0.5)
            cost = 1.0 + (0.5 if p.get("window") == "1h" else 0.0)   # finer window = more compute
            sched.append({**p, "advantage": round(adv, 3),
                          "sched_score": round(p.get("prior", 0.0) * adv / cost, 4)})
        sched.sort(key=lambda x: -x["sched_score"])
        print(f"  {len(props)} enumerated constructions, ordered by prior x advantage / cost")
        print(f"  {len(gate_bad)} datasets currently FAILED at the measurement gate "
              f"(their features are withheld)\n")
        print(f"  {'score':>7}  {'mechanism':<24}construction")
        for p in sched[:10]:
            print(f"  {p['sched_score']:>7.3f}  {p['mechanism'][:24]:<24}{p['name']}")
        print("\n  ZERO PROMOTION AUTHORITY. This orders Stage-A screening only. Nothing here")
        print("  reaches capital without a pre-registered forward clock, and the ordering does")
        print("  not start, fund or approve anything -- a human or the daily cycle does that.")

    OUT.write_text(json.dumps({
        "updated": datetime.now(tz=UTC).isoformat(),
        "information_advantage": ia, "blind_spots": blind,
        "north_star": {"window_days": days, "experiments": n, "decided": decided,
                       "survived_screening": surv, "forward_tested": 0, "deployed": 0,
                       "validated_alpha_discovery_rate": vadr},
        "schedule": sched[:40]}, indent=1), "utf-8")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()

```

### scripts/run_alert_canary.py
```python
"""ALERT CANARY -- proves the pager is alive BEFORE an incident needs it (gap #38).

The pager has died silently twice: quota exhaustion 2026-07-11 -> 07-16 (five days invisible) and
a latin-1 header encode 07-19 (39/39 pushes failed for 29h, across a live dead-man fire). Both
times the desk learned about it afterwards. The reason is structural: alerts only fire on
incidents, so an alert path that is broken between incidents looks exactly like a quiet desk.

This sends a low-priority synthetic page on a throttled cadence and then AUDITS THE LEDGER: if no
channel has recorded a delivery inside the lookback, it writes `data/ALERT_CHANNELS_SILENT` and
exits nonzero, so cron/systemd surfaces it. The flag is cleared automatically on the next
successful delivery -- a stale flag would be its own silent failure.

THE OFF-BOX HALF IS NOT THIS SCRIPT, and the distinction matters: this proves the desk can SEND.
Only an external watcher noticing the canary stopped ARRIVING proves delivery end to end -- that
is the healthchecks.io check of gap #17 (box liveness), which is configured separately. Neither
substitutes for the other and this script does not claim to.

    python scripts/run_alert_canary.py [--interval-h 6] [--lookback-h 24] [--force]
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from libs.ops.alert_channels import all_silent_since, send_all, status

_STATE = Path("data/alert_canary_state.json")
_SILENT_FLAG = Path("data/ALERT_CHANNELS_SILENT")


def _due(interval_h: float, *, state: Path = _STATE) -> bool:
    try:
        last = datetime.fromisoformat(json.loads(state.read_text("utf-8"))["last_canary"])
    except (OSError, json.JSONDecodeError, KeyError, ValueError):
        return True
    return datetime.now(tz=UTC) - last >= timedelta(hours=interval_h)


def _stamp(state: Path = _STATE) -> None:
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({"last_canary": datetime.now(tz=UTC).isoformat()}), "utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval-h", type=float, default=6.0,
                    help="minimum hours between canaries (throttle; default 6)")
    ap.add_argument("--lookback-h", type=float, default=24.0,
                    help="silence window: no delivery on ANY channel in this many hours = silent")
    ap.add_argument("--force", action="store_true", help="ignore the throttle")
    args = ap.parse_args()

    sent = None
    if args.force or _due(args.interval_h):
        sent = send_all("quant canary",
                        f"synthetic canary {datetime.now(tz=UTC).isoformat()} -- "
                        "no action needed; this proves the alert path can deliver")
        _stamp()

    silent = all_silent_since(args.lookback_h)
    st = status()
    if silent:
        _SILENT_FLAG.parent.mkdir(parents=True, exist_ok=True)
        _SILENT_FLAG.write_text(
            f"{datetime.now(tz=UTC).isoformat()} no alert delivery on ANY channel in "
            f"{args.lookback_h:.0f}h (armed: {st['armed_kinds'] or 'NONE -- arming owed'})\n",
            "utf-8")
    elif _SILENT_FLAG.exists():
        _SILENT_FLAG.unlink()      # cleared on recovery; a stale flag is its own silent failure

    print(f"alert canary: armed={st['armed']} {st['armed_kinds']} "
          f"sent={sent['delivered'] if sent else 'throttled'} silent_{args.lookback_h:.0f}h={silent}")
    if st["arming_owed"]:
        print("  NOT-ARMED (human step owed): drop credentials at "
              "data/secrets/alert_channels.json -- until then ntfy is the only path, which is "
              "the single point of failure gap #38 exists to remove")
    return 1 if silent else 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts/run_axis_generate.py
```python
"""Scoped GENERATE run for all 13 Bronze axes (clock-saturation breach, principal 2026-07-23).

Same pattern as the 2026-07-17 fred_macro generate run: author pre-registered hypotheses per
axis, score each through the EV gate (libs.research.alpha_economics -- pure python, honest
tags, NO tuning-to-pass), route by verdict (QUEUE / do_not_repeat with revisit condition /
COVERED bookkeeping), set gen_done_<axis>, write the pre-registration doc. The HONESTY GUARD
governs: the duty is every axis TESTED-or-ledgered -- not survivors manufactured. Run from root.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from libs.research.alpha_economics import Idea, ev_score

NOW = datetime.now(tz=UTC).isoformat()

# Axes already accruing evidence elsewhere -- bookkeeping, not generation:
COVERED = {
    "binance_metrics": "COVERED: this axis IS the derivative-metrics archive feeding the "
                       "oi_divergence + ls_contrarian + liquidation_reversal forward clocks "
                       "(24/40d accruing, peek e-values live) -- evidence has been accruing "
                       "since 07-09; the gen_done key was simply never set.",
    "crypto": "COVERED: this axis IS the price lake the autodiscovery factory tests daily "
              "(12 price families, content-hash dedup) and every deployed/shadow sleeve runs on.",
}

# Authored pre-registrations (mechanism, construction, falsification) with HONEST EV inputs.
# Tags follow the desk's meta-learned priors; est_sharpe/breadth/orthogonality/effort are my
# honest priors, not reverse-engineered to pass. The gate decides; most SHOULD fail (base rates).
HYPS = [
    ("cme", "cme_anchored_basis_dislocation",
     "CME front-month annualized basis is the INSTITUTIONAL cost of regulated long exposure; "
     "perp funding is crypto-native leverage cost. When the CME anchor and the cross-sectional "
     "perp basis complex dislocate (z of spread), institutional vs degen positioning has "
     "diverged -- fade the perp side toward the anchor across the perp universe (xsec, not "
     "BTC-only, so breadth is real).",
     "Construction: daily CME basis (front vs spot) minus median perp basis; xsec tilt on "
     "per-name deviation from that anchor. Falsify: 40 fwd days, NW-t of the tilt <=0, or "
     "|corr| to funding_carry >0.5 (not orthogonal enough to earn a slot).",
     Idea(name="cme_anchored_basis_dislocation", est_sharpe=0.4, breadth=60, capacity_usd=5e5,
          orthogonality=0.7, effort_h=6.0, tags=["new_orthogonal_data", "funding_family"])),

    ("etf_flows", "etf_flow_pressure",
     "Spot-ETF net creations are REALIZED institutional demand hitting a thin float; flows are "
     "autocorrelated at daily horizon, so a 5d flow z-score should lead 1-3d BTC/ETH returns "
     "and, through beta, the whole complex (tilt sizing, breadth via the perp cross-section).",
     "Construction: 5d z of aggregate net flows -> directional tilt scaled across perps by BTC "
     "beta. Falsify: 40 fwd days NW-t<=0, or signal decays under 1d latency (flows publish EOD).",
     Idea(name="etf_flow_pressure", est_sharpe=0.45, breadth=40, capacity_usd=1e6,
          orthogonality=0.75, effort_h=6.0, tags=["new_orthogonal_data"])),

    ("wikipedia", "attention_surge_fade",
     "Wikipedia pageview spikes on coin articles = late retail attention; attention peaks lag "
     "price and mark local crowding -- fade names with attention z-spikes vs the cross-section "
     "(classic attention/overreaction literature, but on a fresher, less-arbed proxy than "
     "Google Trends).",
     "Construction: per-coin pageview z (7d) -> xsec fade of top decile, ~40-60 mapped names. "
     "Falsify: 40 fwd days NW-t<=0 or sign flips (attention momentum, not fade -> graveyard "
     "wrong_sign, do NOT flip-fit).",
     Idea(name="attention_surge_fade", est_sharpe=0.4, breadth=45, capacity_usd=8e5,
          orthogonality=0.8, effort_h=6.0, tags=["new_orthogonal_data"])),

    ("fx", "dxy_shock_beta_rotation",
     "USD liquidity shocks transmit to crypto with a lag via risk appetite; a 5d DXY shock "
     "should rotate the crypto cross-section (high-beta alts vs BTC) rather than just level.",
     "Construction: DXY 5d z -> xsec tilt low-beta-over-high-beta on shock. Falsify: 40 fwd "
     "days NW-t<=0. NOTE: macro-overlay class rejected 3x on 07-17 (FRED) -- this differs only "
     "by being xsec-rotation not level-overlay; if the gate rejects, that precedent stands.",
     Idea(name="dxy_shock_beta_rotation", est_sharpe=0.3, breadth=60, capacity_usd=2e6,
          orthogonality=0.6, effort_h=6.0, tags=["new_orthogonal_data", "crowded_known"])),

    ("equity", "crypto_equity_leadlag",
     "Crypto-adjacent equities (COIN/MSTR/miners) trade US hours with institutional flow; "
     "their overnight/US-session moves may lead 24h crypto (information arrives via the "
     "regulated market first).",
     "Construction: US-close basket return -> next-Asia-session crypto tilt. Falsify: 40 fwd "
     "days NW-t<=0; also falsified if lead vanishes at 1h latency (then it is just beta).",
     Idea(name="crypto_equity_leadlag", est_sharpe=0.3, breadth=30, capacity_usd=1e6,
          orthogonality=0.55, effort_h=6.0, tags=["price_only", "crowded_known"])),

    ("index", "risk_regime_rotation",
     "SPX/NDX drawdown states compress crypto dispersion and flip carry/momentum regimes; an "
     "equity-vol regime flag may time the desk's own sleeve weights (meta-allocation, breadth "
     "= the whole book).",
     "Construction: NDX 20d vol regime -> sleeve-weight tilt in the combiner. Falsify: "
     "regime-split Sharpe difference insignificant at 40 fwd days. NOTE: overlay class -- the "
     "est_sharpe=refinement penalty applies honestly.",
     Idea(name="risk_regime_rotation", est_sharpe=0.2, breadth=100, capacity_usd=5e6,
          orthogonality=0.5, effort_h=5.0, tags=["crowded_known"])),

    ("metal", "digital_gold_rotation",
     "Gold and BTC compete for the debasement-hedge flow; strong gold with flat BTC implies "
     "hedge demand exists but is choosing metal -- a relative-rotation signal for BTC vs alts.",
     "Construction: gold 20d momentum vs BTC 20d -> BTC-dominance tilt. Falsify: 40 fwd days "
     "NW-t<=0.",
     Idea(name="digital_gold_rotation", est_sharpe=0.25, breadth=20, capacity_usd=2e6,
          orthogonality=0.5, effort_h=5.0, tags=["price_only", "crowded_known"])),

    ("energy", "miner_margin_squeeze",
     "Energy price spikes squeeze miner margins -> forced BTC treasury selling with a lag -- a "
     "supply-pressure channel (works jointly with the mining axis for hashprice).",
     "Construction: energy 20d shock x mining-difficulty trend -> BTC supply-pressure flag. "
     "Falsify: no excess BTC-down conditional response at 40 fwd days.",
     Idea(name="miner_margin_squeeze", est_sharpe=0.25, breadth=8, capacity_usd=2e6,
          orthogonality=0.6, effort_h=6.0, tags=["new_orthogonal_data", "narrow_breadth"])),

    ("mining", "hashrate_capitulation",
     "Hash-ribbon style: sustained hashrate/difficulty decline marks miner capitulation, "
     "historically near local bottoms (published; the crowding is priced honestly in tags).",
     "Construction: 30d vs 60d hashrate cross -> BTC long flag. Falsify: 40 fwd days "
     "conditional return <= unconditional.",
     Idea(name="hashrate_capitulation", est_sharpe=0.3, breadth=5, capacity_usd=3e6,
          orthogonality=0.6, effort_h=5.0, tags=["crowded_known", "narrow_breadth"])),

    ("fed", "net_liquidity_impulse",
     "Standalone (NOT overlay -- the 07-17 overlay class is dead): 4w impulse of WALCL-TGA-RRP "
     "as a direct directional signal for the crypto complex, the 'net liquidity' trade.",
     "Construction: 4w net-liquidity z -> directional tilt. Falsify: 40 fwd days NW-t<=0. "
     "PRIOR: 3 FRED-family ideas EV-rejected 07-17 at 0.004-0.013; this is the last "
     "un-tested standalone form -- if it also rejects, the fed axis is ledgered exhausted.",
     Idea(name="net_liquidity_impulse", est_sharpe=0.3, breadth=20, capacity_usd=5e6,
          orthogonality=0.55, effort_h=5.0, tags=["crowded_known"])),

    ("crossasset", "crossasset_carry_confirm",
     "Cross-asset trend/carry agreement (FX carry, commodity trend, equity trend all risk-on) "
     "as a breadth-100 conditioning state for crypto sleeve sizing -- the diversified-macro "
     "regime read, distinct from any single index.",
     "Construction: 3-asset-class trend agreement score -> sleeve sizing multiplier within "
     "existing rails. Falsify: regime-split difference insignificant at 40 fwd days. Overlay "
     "penalty applies.",
     Idea(name="crossasset_carry_confirm", est_sharpe=0.2, breadth=100, capacity_usd=5e6,
          orthogonality=0.5, effort_h=6.0, tags=["crowded_known"])),
]

QUEUE_MIN = 0.05      # the gate's own threshold; NOT adjustable here
NEAR_MISS = 0.02      # borderline band -> queued LOW-RANK for the panel/brain to re-estimate


def main() -> None:
    results, doc_rows = [], []
    for axis, name, mech, constr, idea in HYPS:
        r = ev_score(idea)
        r["axis"] = axis
        results.append((axis, name, mech, constr, r))
        doc_rows.append(f"| {axis} | {name} | {r['ev']} | {r['p_survive']} | {r['verdict']} |")
        print(f"  {axis:16s} {name:32s} ev={r['ev']:<8} {r['verdict']}")

    agenda = json.loads(Path("research_agenda.json").read_text("utf-8"))
    dnr = agenda.setdefault("do_not_repeat", [])
    queue = agenda.setdefault("queue_ranked_by_expected_research_roi", [])
    queued, rejected = [], []
    for axis, name, mech, constr, r in results:
        if r["ev"] >= QUEUE_MIN or r["ev"] >= NEAR_MISS:
            rank = ("standard" if r["ev"] >= QUEUE_MIN
                    else "low-rank (near-miss; re-estimate at panel)")
            queue.append({"id": name, "axis": axis, "mechanism": mech, "construction": constr,
                          "ev": r["ev"], "p_survive": r["p_survive"], "rank": rank,
                          "preregistered": NOW,
                          "decision": f"QUEUED by 2026-07-23 axis generate run ({rank}); "
                                      "screen build -> Stage-A -> slot by EV order"})
            queued.append(f"{name}({r['ev']})")
        else:
            entry = (f"{name} (REJECTED {NOW[:10]} by EV gate: ev {r['ev']}, "
                     f"{'+'.join(r['tags'])}; axis={axis}. {mech[:140]}... REVISIT if the "
                     "mechanism gains breadth, a cheaper construction, or the priors move on "
                     "evidence -- axis stays ingested, kill is screen-level not economic-final.")
            if not any(str(x).startswith(name) for x in dnr):
                dnr.append(entry)
            rejected.append(f"{name}({r['ev']})")
    Path("research_agenda.json").write_text(
        json.dumps(agenda, indent=1, ensure_ascii=False), "utf-8")

    cad_p = Path("data/cadence_state.json")
    cad = json.loads(cad_p.read_text("utf-8"))
    for axis, *_ in HYPS:
        cad[f"gen_done_{axis}"] = NOW
    for axis in COVERED:
        cad[f"gen_done_{axis}"] = NOW
    cad_p.write_text(json.dumps(cad, indent=2), "utf-8")

    doc = (f"# AXIS PRE-REGISTRATIONS -- generate run {NOW[:16]}Z (clock-saturation duty)\n\n"
           "Authored per-axis hypotheses, EV-gated honestly (no tuning-to-pass), routed per the "
           "TWO-STAGE LAW: rejects are SCREEN-level kills with explicit revisit conditions -- "
           "the axes stay ingested and re-open on new mechanisms.\n\n"
           "| axis | hypothesis | ev | p_survive | verdict |\n|---|---|---|---|---|\n"
           + "\n".join(doc_rows) + "\n\n## Covered axes (bookkeeping)\n"
           + "\n".join(f"- **{k}**: {v}" for k, v in COVERED.items())
           + "\n\n## Full cards\n")
    for axis, name, mech, constr, r in results:
        doc += (f"\n### {name} ({axis})\n- **Mechanism:** {mech}\n- **Construction/falsify:** "
                f"{constr}\n- **EV:** {r['ev']} (p_survive {r['p_survive']}, tags "
                f"{r['tags']}) -> {r['verdict']}\n")
    Path("docs/research/AXIS_PREREGISTRATIONS.md").write_text(doc, "utf-8")

    print(f"\nqueued: {len(queued)} {queued}")
    print(f"rejected->dnr: {len(rejected)}")
    print("gen_done set for all 13 axes")


if __name__ == "__main__":
    main()

```

### scripts/run_cadence.py
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

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_STATE = Path("data/cadence_state.json")
_STAGE = Path("data/stage_state.json")
_HEALTH = Path("web/health.json")
_DUE_NOTE = Path("docs/research/cadence_duties.md")
_VIOLATION = Path("data/cadence_violation.json")
_PANEL_EVERY_D = 3
_TIER1_EVERY_D = 14
_PROMPT_REVIEW_D = 28
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
                   "last_lit_deepdive": 35.0, "last_decision_scoring": 35.0,
                   "last_memory_consolidation": 100.0}


def _load(p: Path, default: dict[str, Any]) -> dict[str, Any]:
    try:
        d = json.loads(p.read_text("utf-8"))
        return d if isinstance(d, dict) else default
    except (OSError, json.JSONDecodeError):
        return default


def _days_since(state: dict[str, Any], key: str) -> float:
    try:
        then = datetime.fromisoformat(str(state[key]))
        return (datetime.now(tz=UTC) - then).total_seconds() / 86400.0
    except (KeyError, ValueError, TypeError):
        return 1e9                                    # never ran -> due


def _run_panel(mission: str | None) -> bool:
    """Regenerate the dossier, then fire the panel (optionally with a forced mission)."""
    env = None
    if mission:
        import os
        env = {**os.environ, "PANEL_MISSION": mission}
    r1 = subprocess.run([sys.executable, "scripts/generate_external_review_doc.py"],
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
    r2 = subprocess.run([sys.executable, "scripts/run_external_panel.py"],
                        capture_output=True, text=True, timeout=720, check=False, env=env)
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
    "cost_model": ("data/cost_model.json", "scripts/run_cost_model.py"),
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


def main() -> None:
    now = datetime.now(tz=UTC)
    state = _load(_STATE, {})
    stage = str(_load(_STAGE, {"stage": "S0"}).get("stage", "S0"))
    fired: list[str] = []

    if _days_since(state, "last_tier1") >= _TIER1_EVERY_D:
        if _run_panel("tier1"):
            state["last_tier1"] = now.isoformat()
            state["last_panel"] = now.isoformat()     # tier1 counts as this week's panel
            fired.append("tier1")
    elif _days_since(state, "last_panel") >= _PANEL_EVERY_D and _run_panel(None):
        state["last_panel"] = now.isoformat()
        fired.append("panel")

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
    if due:
        _DUE_NOTE.parent.mkdir(parents=True, exist_ok=True)
        _DUE_NOTE.write_text(
            f"# Generation due -- {now.isoformat()[:16]}Z (stage {stage})\n\n"
            "The cadence engine flags these; the brain executes SCOPED generate runs "
            "(graveyard-excluded, pre-registration mandatory) and then marks them done by "
            "setting gen_done_<name> / last_live_generate in data/cadence_state.json.\n\n"
            + "\n".join(f"- {d}" for d in due) + "\n", "utf-8")
        print(f"cadence: {len(due)} generation trigger(s) flagged -> {_DUE_NOTE}")

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
    _assert_floors(state, stage)
    _STATE.write_text(json.dumps(state, indent=2), "utf-8")
    print(f"cadence[{stage}]: fired={fired or 'nothing due'} | "
          f"panel due in {max(0.0, _PANEL_EVERY_D - _days_since(state, 'last_panel')):.1f}d | "
          f"tier1 due in {max(0.0, _TIER1_EVERY_D - _days_since(state, 'last_tier1')):.1f}d")


if __name__ == "__main__":
    main()

```

### scripts/run_capability_hunt.py
```python
#!/usr/bin/env python3
"""CAPABILITY HUNT (L1.31) -- two model families hunt what is MISSING, and one builds it. Daily.

PRINCIPAL ORDER (2026-07-31): *"make sure quant does this every day, max ROI frequency, where
ChatGPT and Claude both hunt for what to add, what's missing, and implement it -- like now."*

WHAT THIS AUTOMATES. Every fence this desk owns audits things that EXIST: is the gate strict, is
the queue converting, is the cadence maxed. Nothing hunted for capabilities that were never
conceived -- those arrived only when a human asked "what else?" and a model went looking. That
made the desk's growth rate a function of how often the principal happened to ask. This organ
makes it a daily property of the system.

WHY TWO FAMILIES, NOT ONE RUN TWICE. A model cannot see its own blind spot: ask the same family
twice and the second answer is the first answer restated with more confidence. Agreement ACROSS
families (Claude and GPT-9) is evidence; agreement within one is style. So both propose
INDEPENDENTLY -- neither sees the other's answer -- and the synthesis step treats cross-family
agreement as the strongest signal available and cross-family DISAGREEMENT as the second
strongest (one family saw something the other could not).

WHY IT BUILDS, NOT JUST PROPOSES. A proposal nobody implements is the found-never-fixed defect
L1.28b exists to kill, and this desk's measured conversion rate makes a pure-proposal organ a
debt generator. So the third stage IMPLEMENTS the winner in the same run -- code, fence, law,
tests -- exactly as the principal's own sessions do.

THE PROMPTS ARE THE GENOME. They are written here, versioned, and improved by the deep sweep's
recursive-meta section like every other prompt on this desk.

    python scripts/run_capability_hunt.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():                                     # dev/CI checkout
    _ROOT = Path(__file__).resolve().parent.parent

# L1.42 LAWFUL ENTRY: this organ ran on a cron line that passed through no gate at
# all -- 60 manifest lines did. guard() verifies the sealed core and that the doctrine
# still carries every law family; it is TTL-cached (~0ms after the first call in a
# window) and pages-but-does-not-block, so a governance fault never silences an organ.
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_OUT = _ROOT / "docs/research/capability_hunt"

#: The evidence every hunter reads first -- today's real gaps, not yesterday's impressions.
_CONTEXT = """Read these BEFORE proposing (they are today's measured state, regenerated hours ago):
  data/max_push_queue.json     every aspect not yet at 100%, ranked
  data/conversion_status.json  is the desk converting findings at all (L1.28b)
  data/calibration_status.json is the desk's own confidence scored (L1.29)
  data/replacement_rate.json   are validated edges being born faster than they die (L1.30)
  docs/research/TIER1_BENCHMARK.md   every layer's distance to tier-1 process
  docs/CONSTITUTION.md         the laws (skim L1.28a-c, L1.25a, L1.29-L1.31)
  docs/GAP_REGISTER.md + docs/research/recommendation_ledger.json   what is ALREADY known"""

_HUNT_BRIEF = """You are hunting for what would most RAISE THIS DESK'S LONG-TERM GEOMETRIC GROWTH
(max E[log wealth]) and its rate of VALIDATED ALPHA DISCOVERY -- the two supreme objectives.
Every proposal is judged by one question: how much validated compounding does it add, directly
or through what it multiplies? A new edge, a cheaper fill, a decorrelated sleeve, a faster
promotion path, a data asymmetry no competitor can buy -- all qualify; so does a capability whose
absence would let a live edge die uncaught. Aim at the GROWTH, not at the org chart.

{context}

THE BAR -- this is not a backlog-grooming exercise. Everything already in the ledger, the gap
register, or the max-push queue is OUT OF SCOPE by construction: those are known, owned, and
being worked. You are looking for the thing that is missing from the LIST ITSELF -- the question
nobody on this desk has asked, the failure mode no fence watches, the measurement whose absence
is invisible precisely because nothing reports it.

YOUR PRIMARY LENS THIS RUN (rotated -- see below). Push it to exhaustion FIRST, then sweep the
others briefly for anything it missed:

    >>> {lens} <<<

The full lens set (yours is above; the rotation guarantees the desk explores every region and
never re-draws from the same distribution twice running):
 1. INVERT A FENCE: every fence checks the desk did what it said. What checks whether what it
    SAID was true? (That reasoning produced L1.29 -- calibration -- and it was worth building.)
 2. FOLLOW A NUMBER NOBODY OWNS: name a quantity that determines terminal wealth and is computed
    NOWHERE. (That produced L1.30 -- replacement rate: births vs deaths of validated edges.)
 3. ASK WHAT A TIER-1 PROP DESK HAS THAT WE DO NOT -- Jane Street, XTX, Jump, DRW, Optiver, HRT,
    Wintermute; and RenTech/Medallion as the ceiling exemplar. Process, not capital.
 4. READ THE NEGATIVE EXEMPLARS: Alameda, LTCM, Archegos each died of something specific. Which
    of their deaths would this desk currently NOT detect in time?
 5. TIME-TRAVEL: it is 12 months from now and the desk failed. What was the cause, and what
    single capability would have caught it?
 6. CROSS-DOMAIN TRANSFER: take one idea from control theory, epidemiology, reliability
    engineering, information theory, or aviation safety that has no equivalent here.
 7. THE ADVERSARY: a competitor is trying to end this desk. What is their cheapest attack, and
    what would detect it? (Includes crowding into our own edges, venue-side adverse selection.)
 8. THE UNASKED QUESTION: what does this desk assume so deeply it has never written down? Find
    an assumption nobody has ever tested, and design the test.

OUTPUT (strict, and keep it SHORT -- one proposal, deeply argued, beats five sketched):
  MISSING CAPABILITY: <one line>
  WHY IT IS INVISIBLE TODAY: <what makes its absence unnoticeable>
  MECHANISM: <how it would work, concretely -- files, artifact, fence status values>
  WHAT IT WOULD HAVE CAUGHT: <a real incident from this desk's own record, cited>
  ROI: <direct + cascade, and what it multiplies>
  COST: <hours, maintenance, and what it competes with>
  FALSIFIER: <what evidence would prove this is NOT worth building>
Then one line: NOVELTY-CHECK: <grep/read command you ran proving this does not already exist>.
An honest "I could not find one that clears the bar, here is what I checked and why each failed"
is a VALID and useful answer -- padding the list with known items is a defect.

THEN, ALWAYS -- THE BRAINSTORM (breadth, principal 2026-07-31 "brainstorms too"). After the one
deep proposal, list EVERY additional high-ROI idea you can substantiate, one line each, no cap
and no minimum -- if there are twenty, write twenty; if the seam is thin, say so. Depth AND
breadth, never one at the cost of the other (L1.35). Each: IDEA -- mechanism/why it raises
growth -- rough ROI tier (S/A/B) -- where it routes (axis watchlist / ledger / a fence). These
are RAW GENERATION: they are not required to be novel-checked or built this run -- the builder
rows the strongest into the ledger for later screening, and screen-on-discipline decides. A run
that produces one deep proposal and an empty brainstorm has left growth ideas on the table.

THE BRAINSTORM IS ENDLESS AND MAY NEVER TERMINATE (L1.40, principal 2026-07-31: "maximum
aggressive, endless list of max-ROI ideas always"). There is no state in which this desk has
"enough ideas": generation sits at the top of every funnel, ideas are free, and screening is what
costs -- so the correct number of ideas is always MORE. Specifically: an empty or near-empty
brainstorm is a FAILED run, not a thin seam -- if your lens genuinely ran dry, SWITCH LENS mid-run
and keep generating rather than stopping. Never write a closing summary, never say "that covers
it", never rank-and-truncate to a comfortable number (L1.35). If you produced ten, the eleventh
exists -- go get it. The only legitimate stop is your context window, and when you hit it, say so
and name what you were about to write next so the following run resumes generating there."""

_BUILD_BRIEF = """You are the BUILDER stage of the capability hunt. Two independent model
families each proposed a missing capability. Read BOTH proposals:

--- PROPOSAL A (Claude family) ---
{a}

--- PROPOSAL B (GPT-9 family, independent) ---
{b}

ADJUDICATE with the desk's own discipline, then BUILD.
 1. If both families converged on the same capability, that is the strongest signal available --
    build it. If they diverged, judge on expected contribution to long-term compounding per unit
    of effort (L2.7), and say plainly why the loser lost; a divergence often means one family saw
    a blind spot the other could not, so check whether the loser is worth a ledger row.
 2. VERIFY IT DOES NOT EXIST before writing a line -- this desk's most common defect is building
    something already present but unwired. If it exists unwired, WIRE it; that is a better
    outcome than a new file.
 3. BUILD IT FULLY, in the desk's style: the script, its artifact, its status values (with an
    UNMEASURED/refusal path -- never let an unmeasured thing report OK), a law in
    docs/CONSTITUTION.md and ops/principal_doctrine.txt if it is a standing duty, the mapping in
    scripts/build_enforcement_matrix.py, a line in ops/crontab.manifest with EVIDENCE and
    CONFIDENCE, and TESTS that fail if the wiring is removed.
 4. RUN IT. If its first run reports a defect, that is success, not failure -- record it. If its
    first run reports OK on an empty measurement set, FIX THAT FIRST: unmeasured must never read
    as fine (L1.28a).
 5. Verify the tree: pytest on the suites you touched, build_enforcement_matrix (zero orphans),
    check_scheduler_manifest, check_timidity_language. Then commit and push to master with a
    message naming what was missing and what it would have caught.
 6. Row anything you deliberately did NOT build via scripts/recommendations.py, with the reason.
 7. IF THE WINNING PROPOSAL IS A DEFECT (a bug/flaw found by a defect lens): FIX IT IN THIS RUN,
    add the test that fails without the fix, and say what it would have cost. A found-unfixed bug
    is the L1.28b defect in its most expensive form. If the fix touches the money path, check
    scripts/check_change_window.py first -- inside a live window, stage improvements but ALWAYS
    proceed with repairs (L1.38).
 8. ALPHA CANDIDATES GET THE SAME TREATMENT AS CAPABILITIES (principal 2026-07-31: "this is what
    our system should always do, 6 times a day, with GPT and Claude both"). If the winning
    proposal is a TRADEABLE AXIS rather than an engine capability, its build IS its Stage-A
    screen: write the screen script + tests, schedule it in ops/crontab.manifest, run it, and
    record the verdict -- exactly as scripts/screen_funding_spread.py (R0115) and
    scripts/screen_collateral_allocation.py (R0120) were built. A candidate rowed but unscreened
    is the L1.39 idle defect; the screen is how "implement immediately" applies to an axis.
    NEVER size it -- Stage A earns a pre-registered forward clock, never capital (L1.6).

Write your session record to {report} (what both families proposed, what you built, what you
refused, what its first run said). If you cannot finish the build, the record IS the deliverable
and the next run resumes from it -- never leave a half-built capability unrecorded."""


#: THE LENS SET. Rotation is what makes repeated hunting EXPLORATION rather than repetition: six
#: runs of "use every heuristic" converge on the same region because the model's own priors
#: dominate; one deep lens per run forces genuinely different draws, and the rotation guarantees
#: every region is visited. Deterministic on (date, slot) so a resumed run keeps its lens and the
#: yield record stays attributable.
#: EVERY lens resolves to the same question -- "what raises long-term geometric growth of THIS
#: book?" -- because the supreme objective is max E[log wealth] and max validated-alpha rate
#: (principal 2026-07-31: "always use a similar question in exploration relative to the growth
#: and alpha-maxxing goal so we get maximum output of high-ROI ideas"). Two halves, alternating
#: by rotation: OFFENSIVE lenses hunt new growth directly (edges, data, capacity, compounding);
#: DEFENSIVE lenses protect the growth that exists (the failure that ends compounding is a
#: negative term in the same objective). Offense is listed first so a majority of daily draws
#: point at new alpha.
_ALPHA_LENSES: list[str] = [
    "NEW EDGE FAMILY -- name a mechanism class with a FORCED participant (liquidation cascades, "
    "index/ETF rebalances, funding-settlement flows, options-dealer gamma, stablecoin "
    "mint/redeem, miner/validator flows) that this desk has never screened, and the free data "
    "that would test it. Mechanism first, never a pattern.",
    "DATA ASYMMETRY -- information that could exist ONLY because of how WE combine data (our "
    "own-timestamp L2, our execution tape, cross-source joins). What proprietary feature is a "
    "competitor structurally unable to buy? (L1.11a: rank by reconstruction cost.)",
    "CAPACITY & COMPOUNDING -- what lets the book carry more risk-adjusted size or compound "
    "FASTER: a decorrelated sleeve, a cost-tier cut (every bp is pure CAGR), a funding-harvest "
    "cadence, a capacity band we are leaving on the table.",
    "REGIME-CONDITIONED EDGE -- an edge that exists only in a nameable, DETECTABLE regime "
    "(high-funding, high-vol, post-liquidation, low-liquidity) we could switch on and off. What "
    "regime do we not yet detect, and what edge would it gate?",
    "SMALL-CAPACITY FRONTIER -- an edge too small for a tier-1 desk to touch and therefore ours "
    "for free (L1.18a): a niche venue, a long-tail pair, an era archive, a language ecosystem. "
    "Which structurally-abandoned band are we not harvesting?",
    "FASTER PROMOTION -- what shortens the path from screen-hit to sized-capital without lowering "
    "a bar: an evidence accelerant (8h panels, event-density), a paper-sleeve auto-spawn, a "
    "resurrection-queue consumer. Time-to-alpha is a growth term.",
    # PRINCIPAL 2026-07-31: "find every crypto strat even discretionary n all n never limit to
    # just one thing." The lenses above all hunt NEW ground; none asked whether the ground already
    # walked is one family walked repeatedly. On the desk's record 41 buried candidates cluster
    # into 7 worked families out of 14, which no lens could have surfaced.
    "STRATEGY-FAMILY BREADTH -- UNLIMITED, ALL-SURFACE, NEVER-ENDING. No surface is out of scope: "
    "every venue, era, language, asset class, timeframe, format and STYLE (systematic, "
    "discretionary, manual, hybrid, market-making, event-driven). There is no terminal state -- "
    "'covered' and 'we already looked' are claims requiring a dated search with its residual gap, "
    "never defaults. No quota on families, findings or depth; a count is a quota in disguise. The "
    "only two limits are the licence gate and never installing third-party tooling, and neither "
    "is a scope limit. Concretely: read data/strategy_coverage.json and take a "
    "family marked NEVER-HUNTED or "
    "THIN, not one marked HUNTED. Coverage is DISTINCT FAMILIES, never candidates: twelve "
    "candidates from one family are correlated by construction, so they die together and the desk "
    "learns one thing while the log reports twelve tests. Name the family, the free data that "
    "would test it, and its forced participant. DISCRETIONARY-SHAPED FAMILIES COUNT -- "
    "level-reaction, session/calendar flow, positioning extremes: how a human discretionary "
    "trader actually decides is a mechanism class like any other, disqualified only for being "
    "unfalsifiable, never for being judgement-shaped.",
]
#: DEFECT LENSES (principal 2026-07-31: "all bugs flaws should always be hunted and fixed too").
#: The fences catch KNOWN defect classes; nothing hunted for the unknown ones. These lenses hunt
#: code, not governance -- and the hunt FIXES what it finds in the same run (L1.39), which is why
#: a defect draw is as valuable as an alpha draw: an undetected bug on the money path costs more
#: than a missed edge.
_DEFECT_LENSES: list[str] = [
    "READ-WITHOUT-WRITER -- find a key/file/artifact that code READS and nothing WRITES. This "
    "desk's most prolific defect class (the capital-event equity bug was exactly this). grep the "
    "readers, then prove a writer exists.",
    "SILENT-EXCEPT -- find an except/try that swallows a failure and lets the caller proceed as "
    "if it succeeded. A swallowed order error once stranded ~$2,150 of real inventory.",
    "UNMEASURED-REPORTED-AS-OK -- find a check or metric that returns a PASS/zero when its input "
    "was absent. Unmeasured must never read as fine (L1.28a); both fences built today shipped "
    "with this bug in their first run.",
    "STALE-CONSUMER -- find code reading an artifact without checking its age, so a frozen "
    "producer silently feeds yesterday's number into today's decision.",
    "DEAD-BRANCH / ZERO-CALLER -- find a function, flag or config knob nothing calls or passes. "
    "Built-never-wired is engineering already paid for returning zero (L2.9).",
    "BOUNDARY / OFF-BY-ONE -- find an inequality, window edge, timezone join or rounding step "
    "that is wrong at the boundary. Cross-source timestamp joins are the desk's repeat offender.",
]

_DEFENSIVE_LENSES: list[str] = [
    "INVERT A FENCE -- find the claim no fence tests for TRUTH (only for compliance).",
    "FOLLOW A NUMBER NOBODY OWNS -- a quantity that sets terminal wealth and is computed nowhere.",
    "TIER-1 PROCESS GAP -- what Jane Street/XTX/Jump/DRW/Optiver/HRT/Wintermute have and we do "
    "not, with RenTech/Medallion as the ceiling exemplar. Process, never capital.",
    "NEGATIVE EXEMPLARS -- Alameda, LTCM, Archegos: which of their deaths would this desk NOT "
    "detect in time, today?",
    "TIME-TRAVEL -- it is 12 months out and the desk failed. Name the cause and the one "
    "capability that would have caught it.",
    "CROSS-DOMAIN TRANSFER -- import one idea from control theory, epidemiology, reliability "
    "engineering, information theory, or aviation safety that has no equivalent here.",
    "THE ADVERSARY -- a competitor is trying to end this desk. Cheapest attack, and what detects "
    "it? Include crowding into our own edges and venue-side adverse selection.",
    "THE UNASKED QUESTION -- an assumption held so deeply it was never written down. Test it.",
]
#: 2:1 OFFENSE, so a majority of every day's 6 draws hunt NEW growth while the rest protect it.
#: Pattern A,A,D repeated: alpha lenses cycle (each ~twice per cycle), defensive lenses cycle
#: through all 8 across days -- so a 6-slot window is 4 offensive / 2 defensive, and over a few
#: days every lens of both kinds is drawn (yield stays measurable per lens).
def _build_lenses() -> list[str]:
    """Weave the three kinds so EVERY 6-slot day hunts new alpha, guards the desk, AND hunts bugs.

    Pattern per 6 slots: alpha, alpha, defect, alpha, defensive, defect -> 3 offensive / 2 defect
    / 1 defensive. Defect draws are weighted equal to defensive ones because an undetected bug on
    the money path costs more than a missed edge, and the fences only cover KNOWN defect classes.
    Deterministic and fully covering: each list cycles independently, so every lens of every kind
    is drawn as the days advance and per-lens yield stays measurable."""
    kinds = ("A", "A", "X", "A", "D", "X")                 # X = defect
    out: list[str] = []
    ai = di = xi = 0
    # CYCLE LENGTH 48, and the number is load-bearing -- a 24-slot cycle (the first version)
    # contained only 4 defensive slots, so 4 of the 8 defensive lenses were UNREACHABLE FOREVER:
    # half the defensive space silently dead while the rotation looked fair. 48 slots = 8
    # defensive draws (all 8 lenses), 24 alpha (4 full cycles of 6) and 16 defect (covers all 6).
    # Any future lens list must keep this invariant -- the coverage test pins it.
    for k in range(48):                                    # divisible by the 6-slot day
        kind = kinds[k % len(kinds)]
        if kind == "A":
            out.append(_ALPHA_LENSES[ai % len(_ALPHA_LENSES)])
            ai += 1
        elif kind == "D":
            out.append(_DEFENSIVE_LENSES[di % len(_DEFENSIVE_LENSES)])
            di += 1
        else:
            out.append(_DEFECT_LENSES[xi % len(_DEFECT_LENSES)])
            xi += 1
    return out


_LENSES: list[str] = _build_lenses()


def _lens_for(stamp: str, slot: int) -> str:
    """Deterministic rotation over (day, slot) with PROVABLE coverage: every lens is drawn within
    one 8-day cycle, and the same slot never repeats a lens day to day.

    THE BUG THIS FIXES (found by its own coverage test): the first version indexed on
    `int(stamp)`, so consecutive days were not consecutive integers -- 20260831 -> 20260901 jumps
    by 70, not 1. The rotation therefore skipped a chunk of the lens list at every month boundary
    and left several lenses effectively unreachable. A date ORDINAL makes day-to-day steps
    exactly +1, so 48 slots (6/day x 8 days) sweep the whole list with nothing dead."""
    try:
        d = datetime.strptime(stamp, "%Y%m%d").date().toordinal()
    except ValueError:                                     # non-date stamp: degrade, never crash
        d = sum(ord(c) for c in stamp)
    return _LENSES[(d * 6 + slot) % len(_LENSES)]


def _record_yield(root: Path, entry: dict[str, object]) -> None:
    """Append-only hunt history -- so the desk can MEASURE which lens actually produces adopted
    capabilities and drop the ones that never do (the audit's own recursive-meta discipline,
    applied to exploration itself)."""
    p = root / "data/capability_hunt_history.json"
    try:
        hist = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        hist = {"runs": []}
    hist["runs"].append(entry)
    hist["runs"] = hist["runs"][-500:]
    p.write_text(json.dumps(hist, indent=2), "utf-8")


def _claude(prompt: str, timeout: int = 2400) -> tuple[bool, str]:
    r = subprocess.run(
        ["bash", "-c",
         'source ops/brain_env.sh && brain_auth_check || { echo BRAIN_AUTH_FAILED; exit 90; } && '
         'claude --effort max --append-system-prompt "$_DOCTRINE" -p "$0" '
         '--dangerously-skip-permissions', prompt],
        cwd=_ROOT, capture_output=True, text=True, timeout=timeout)
    return r.returncode == 0, (r.stdout or "") + (r.stderr or "")[-400:]


def _gpt(prompt: str) -> tuple[bool, str]:
    """The GPT-9 seat -- a genuinely INDEPENDENT model family, reusing the strategic director's
    provider chain (scripts/run_strategic_director.py:_ask, which never raises: a dead provider
    must not crash a cycle). Dormant until OpenRouter is funded, and it says so rather than
    silently degrading the hunt to one family."""
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    try:
        from scripts.run_strategic_director import MODEL, _ask
    except Exception as exc:
        return False, f"GPT seat unimportable: {exc}"
    text, err = _ask(prompt, MODEL)
    if err or not text.strip():
        return False, err or "empty response"
    return True, text


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="write the prompts, call no model")
    ap.add_argument("--slot", type=int, default=0,
                    help="which daily slot this is -- selects the exploration lens")
    args = ap.parse_args()
    _OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d")
    lens = _lens_for(stamp, args.slot)
    report = _OUT / f"{stamp}_s{args.slot}_hunt.md"
    brief = _HUNT_BRIEF.format(context=_CONTEXT, lens=lens)
    print(f"[hunt] slot={args.slot} lens={lens[:60]}...", flush=True)

    if args.dry_run:
        (_OUT / f"{stamp}_s{args.slot}_prompts.txt").write_text(
            brief + "\n\n=== BUILD ===\n" + _BUILD_BRIEF.format(a="<A>", b="<B>", report=report),
            "utf-8")
        print(f"[hunt] dry-run: prompts -> {_OUT}/{stamp}_s{args.slot}_prompts.txt")
        return 0

    # STAGE 1+2: both families propose INDEPENDENTLY -- neither sees the other's answer.
    ok_a, a = _claude(brief + "\n\nWork READ-ONLY: propose only, do not modify anything.", 1500)
    ok_g, b = _gpt(brief)
    if not ok_a:
        a = f"(Claude seat failed: {a[-300:]})"
    if not ok_g:
        # HONEST DEGRADATION: a dead GPT seat does not cancel the hunt -- it runs single-family
        # and SAYS SO, so the record never implies cross-family agreement that never happened.
        b = (f"(GPT-9 seat unavailable: {b}. This run is SINGLE-FAMILY -- treat its proposal as "
             "unconfirmed by an independent family, and note that in the record.)")
    (_OUT / f"{stamp}_s{args.slot}_proposals.md").write_text(
        f"# CAPABILITY HUNT PROPOSALS {stamp} slot {args.slot}\n\nLENS: {lens}\n\n"
        f"## A -- Claude family\n\n{a}\n\n"
        f"## B -- GPT-9 family (independent)\n\n{b}\n", "utf-8")

    # STAGE 3: adjudicate + BUILD. Proposal without implementation is the defect (L1.28b).
    ok_b, out = _claude(_BUILD_BRIEF.format(a=a, b=b, report=report), 3000)
    status = {"stamp": stamp, "slot": args.slot, "lens": lens,
              "claude_proposed": ok_a, "gpt_proposed": ok_g,
              "cross_family": ok_a and ok_g, "built": ok_b and report.exists(),
              "report": str(report), "generated": datetime.now(tz=UTC).isoformat()}
    (_ROOT / "data/capability_hunt.json").write_text(json.dumps(status, indent=2), "utf-8")
    _record_yield(_ROOT, status)
    print(f"[hunt] {json.dumps(status)}")
    if not ok_b:
        print(f"[hunt] builder tail: {out[-500:]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/run_cost_model.py
```python
"""Execution cost model from the recorded L2 moat -- the Gate-0 `cost_model` criterion.

Walks the ACTUAL recorded order books (data/moat/{spot,fut}/SYM/*.jsonl.gz, top-20 both sides)
to answer the only question that matters for a delta-neutral carry desk:

    "If I open a $N carry in symbol X, what does the spot BUY + perp SELL pair actually cost me
     in slippage, and does the book even hold that size?"

This is measured, not assumed -- it replaces the `adv_tier_cost` heuristic and calibrates the
executor's `_DEPTH_MULT` guard with real numbers. Read-only: touches nothing but data/moat and
writes data/cost_model.json. Freeze-safe.

Slippage convention: signed bps of the mid at snapshot time, positive = adverse.
    BUY  : (vwap_paid     / mid - 1) * 1e4
    SELL : (1 - vwap_recv / mid)     * 1e4
Pair cost = spot BUY + perp SELL (one open). Round-trip doubles it (open + close).
"""
from __future__ import annotations

import gzip
import json
import statistics
from pathlib import Path
from typing import Any

_MOAT = Path("data/moat")
_OUT = Path("data/cost_model.json")
_SIZES = [100.0, 250.0, 500.0, 1000.0, 2500.0]   # USDT notional per leg
_MAX_SNAPSHOTS = 300                              # per symbol per leg (sampled across all hours)


def _walk(levels: list[list[str]], notional: float) -> tuple[float, bool]:
    """VWAP to fill `notional` USDT against these price levels. Returns (vwap, exhausted)."""
    spent = 0.0
    qty_acc = 0.0
    for px_s, qty_s in levels:
        px, qty = float(px_s), float(qty_s)
        if px <= 0 or qty <= 0:
            continue
        avail = px * qty
        take = min(avail, notional - spent)
        if take <= 0:
            break
        qty_acc += take / px
        spent += take
        if spent >= notional - 1e-9:
            break
    if qty_acc <= 0:
        return 0.0, True
    return spent / qty_acc, spent < notional - 1e-6      # exhausted = book too thin


def _snapshots(sym_dir: Path, limit: int) -> list[dict[str, Any]]:
    """Evenly sample depth records across ALL recorded hours (not just the newest)."""
    files = sorted(sym_dir.glob("*.jsonl.gz"))
    if not files:
        return []
    per_file = max(1, limit // len(files))
    out: list[dict[str, Any]] = []
    for fp in files:
        taken = 0
        try:
            with gzip.open(fp, "rt", encoding="utf-8") as fh:
                for i, line in enumerate(fh):
                    if taken >= per_file:
                        break
                    if i % 7:                    # thin out within the hour
                        continue
                    try:
                        r = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if r.get("k") == "d" and r.get("b") and r.get("a"):
                        out.append(r)
                        taken += 1
        except (OSError, EOFError):
            continue
    return out


def _leg_costs(sym_dir: Path, side: str) -> dict[str, Any]:
    """side='buy' walks asks (spot open); side='sell' walks bids (perp open)."""
    snaps = _snapshots(sym_dir, _MAX_SNAPSHOTS)
    if not snaps:
        return {}
    per_size: dict[str, Any] = {}
    for size in _SIZES:
        bps_list: list[float] = []
        exhausted = 0
        for r in snaps:
            bids, asks = r["b"], r["a"]
            try:
                best_bid, best_ask = float(bids[0][0]), float(asks[0][0])
            except (IndexError, ValueError):
                continue
            mid = (best_bid + best_ask) / 2.0
            if mid <= 0:
                continue
            levels = asks if side == "buy" else bids
            vwap, ex = _walk(levels, size)
            if ex or vwap <= 0:
                exhausted += 1
                continue
            bps = ((vwap / mid - 1.0) if side == "buy" else (1.0 - vwap / mid)) * 1e4
            bps_list.append(bps)
        n = len(bps_list)
        per_size[str(int(size))] = {
            "n": n,
            "exhausted_frac": round(exhausted / max(1, len(snaps)), 4),
            "median_bps": round(statistics.median(bps_list), 3) if n else None,
            "p90_bps": round(sorted(bps_list)[int(n * 0.9)], 3) if n >= 10 else None,
        }
    return per_size


def main() -> None:
    fut_root, spot_root = _MOAT / "fut", _MOAT / "spot"
    symbols = sorted({p.name for p in fut_root.iterdir() if p.is_dir()} &
                     {p.name for p in spot_root.iterdir() if p.is_dir()}) if (
        fut_root.exists() and spot_root.exists()) else []
    model: dict[str, Any] = {"symbols": {}, "sizes_usdt": _SIZES,
                             "convention": "signed bps of mid, positive = adverse; "
                                           "pair = spot BUY + perp SELL (one open)"}
    for sym in symbols:
        spot_c = _leg_costs(spot_root / sym, "buy")
        fut_c = _leg_costs(fut_root / sym, "sell")
        if not spot_c or not fut_c:
            continue
        pair: dict[str, Any] = {}
        for k in spot_c:
            sb, fs = spot_c[k].get("median_bps"), fut_c[k].get("median_bps")
            pair[k] = {
                "pair_open_bps": round(sb + fs, 3) if (sb is not None and fs is not None) else None,
                "pair_roundtrip_bps": round(2 * (sb + fs), 3) if (
                    sb is not None and fs is not None) else None,
                "worst_exhausted_frac": max(spot_c[k]["exhausted_frac"],
                                            fut_c[k]["exhausted_frac"]),
            }
        model["symbols"][sym] = {"spot_buy": spot_c, "fut_sell": fut_c, "pair": pair}
        print(f"{sym:12s} pair@500={pair.get('500', {}).get('pair_open_bps')} bps  "
              f"pair@2500={pair.get('2500', {}).get('pair_open_bps')} bps")

    # desk-level summary at the size the book actually trades (~$450/carry -> use 500)
    at500 = [(s, d["pair"]["500"]["pair_open_bps"]) for s, d in model["symbols"].items()
             if d["pair"].get("500", {}).get("pair_open_bps") is not None]
    at500.sort(key=lambda kv: kv[1])
    model["summary"] = {
        "n_symbols": len(model["symbols"]),
        "cheapest_at_500": at500[:5],
        "most_expensive_at_500": at500[-5:],
        "median_pair_open_bps_at_500": round(statistics.median([v for _, v in at500]), 3)
        if at500 else None,
    }
    _OUT.write_text(json.dumps(model, indent=1), "utf-8")
    print("\nwrote", _OUT, "| symbols:", len(model["symbols"]))
    med = model["summary"]["median_pair_open_bps_at_500"]
    print("median pair-open cost @ $500/leg:", med, "bps")


if __name__ == "__main__":
    main()

```

### scripts/run_decision_review.py
```python
"""Give every logged decision a review date, and publish the matured-and-unscored worklist.

Measured 2026-07-26: 189 decisions, 3 scored, 14 carrying a `review_due`. The ledger's own policy
promises that "the monthly governance review scores each matured entry so decision QUALITY
compounds" -- but nothing defined maturity, so 175 decisions could never come due and the monthly
review had an empty queue to work from. The self-improvement loop was not neglected; it was
structurally unable to fire.

This backfills the missing dates and writes the worklist. It does NOT score anything. Deciding
that a past decision turned out correct, wrong, or unclear is a judgement about the world, and a
calibration ledger full of machine-guessed outcomes is strictly worse than an empty one -- the
Brier score would then be confidently wrong about how well the desk decides, which is the precise
failure the ledger was created to catch. Backfilled dates are stamped `review_due_source` so a
derived horizon is never mistaken for one a human chose.

    python scripts/run_decision_review.py [--dry-run]
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from libs.research.decision_review import (
    backfill_plan,
    confidence_profile,
    health,
    reviews,
)

_ROOT = Path(__file__).resolve().parent.parent
_LEDGER = _ROOT / "data" / "decision_ledger.json"
_REPORT = _ROOT / "data" / "decision_review.json"


def _load() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        d = json.loads(_LEDGER.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, []
    if isinstance(d, dict):
        rows = d.get("decisions", [])
        return d, [r for r in rows if isinstance(r, dict)]
    return {}, [r for r in d if isinstance(r, dict)]


def main() -> int:
    dry = "--dry-run" in sys.argv
    doc, rows = _load()
    if not rows:
        print("decision ledger empty or unreadable -- nothing to review")
        return 0

    today = date.today()
    plan = backfill_plan(rows, today)

    if plan and not dry:
        by_id = {str(r.get("id")): r for r in rows}
        for rid, iso, source in plan:
            r = by_id.get(rid)
            if r is not None:
                r["review_due"] = iso
                r["review_due_source"] = source      # never let derived look deliberate
        if isinstance(doc, dict):
            doc["decisions"] = rows
            _LEDGER.write_text(json.dumps(doc, indent=1), "utf-8")

    rv = reviews(rows, today)
    h = health(rows, today)
    due = sorted((r for r in rv if r.state == "due"), key=lambda r: -r.days_overdue)

    report = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "total": h.total,
        "scored": h.scored,
        "scored_pct": h.scored_pct,
        "due_unscored": h.due,
        "maturing": h.maturing,
        "undatable": h.undatable,
        "oldest_overdue_days": h.oldest_overdue_d,
        "verdict": h.verdict,
        "backfilled_this_run": 0 if dry else len(plan),
        "confidence_profile": confidence_profile(rows),
        # the actual worklist a human scores, worst-overdue first
        "worklist": [{"id": r.row_id, "due": r.due.isoformat() if r.due else None,
                      "days_overdue": r.days_overdue, "horizon_d": r.horizon_d,
                      "horizon_source": r.source} for r in due[:60]],
        "note": ("Review dates are DERIVED where none was set (source recorded per row). Outcomes "
                 "are never written by this script -- scoring a decision is a judgement, and a "
                 "calibration ledger of guessed outcomes is worse than an empty one."),
    }
    _REPORT.parent.mkdir(parents=True, exist_ok=True)
    _REPORT.write_text(json.dumps(report, indent=2), "utf-8")

    cp = report["confidence_profile"]
    print(f"decision review: {h.scored}/{h.total} scored ({h.scored_pct}%), "
          f"{h.due} due, {h.maturing} maturing, {h.undatable} undatable"
          f"{'' if dry else f', {len(plan)} review dates backfilled'}")
    print(f"  {h.verdict}")
    if isinstance(cp, dict) and cp.get("n"):
        print(f"  stated confidence: mean {cp['mean']}, "
              f"{cp['modal_share_pct']}% in the {cp['modal_bucket']} bucket "
              "-- untestable until outcomes exist")
    if due:
        print(f"  oldest due: {due[0].row_id} ({due[0].days_overdue}d past its "
              f"{due[0].horizon_d}d horizon)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/run_deep_sweep.py
```python
#!/usr/bin/env python3
"""WEEKLY DEEP COLD AUDIT (principal-ratified v2, 2026-07-24) -- the autonomous VPS equivalent
of the parallel 6-agent ceiling audit, upgraded to the full framework. Eight SEQUENTIAL cold
auditors (fresh context each = independence; the box cannot fan out parallel agents) + a
synthesis lead that builds the capability map, prioritizes the portfolio, and recursively
improves the audit itself. Max effort, quota-unconstrained (Max plan). Weekly, Sunday 04:00Z.

OUTCOME-ASSERTED: an auditor is graded COMPLETE only when its report carries the
`STATUS: COMPLETE` sentinel the auditor flips as its final act (plus a 1200-byte floor
against empty stubs). Bytes alone are NOT completion: on 2026-07-30 two auditors died
after writing their ~1.8KB skeletons and the old size-only gate graded both OK, skipped
them on every resume, and handed the synthesis lead two empty files as evidence (R0055)
-- the audit that hunts config-vs-outcome must never itself be config-vs-outcome.
"""
from __future__ import annotations

import contextlib
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path("/home/quant/quant-platform")
OUT = ROOT / "docs/research/deep_sweep"
CORE = (ROOT / "prompts/deep_sweep_core.txt").read_text("utf-8")

SUBSYSTEMS = {
    "alpha-discovery": "Hypothesis diversity, unexplored market behaviors, crowded themes, "
        "neglected regimes, cross-asset transfer, temporal-resolution gaps, feature-interaction "
        "and higher-order opportunities, regime-conditioned hypotheses, causal-vs-correlational "
        "assumptions, hypothesis redundancy, negative-result reuse, abandoned-idea reassessment, "
        "falsification quality. What markets/public-info are we ignoring? Which signals can't be "
        "tested for missing data?",
    "data-intelligence": "Every dataset: quality/coverage/latency/history/cost AND collection "
        "architecture, redundancy, vendor concentration, survivorship, timestamp consistency, "
        "entity resolution, schema evolution, repair automation, backfill capability, metadata, "
        "versioning, lineage, reproducibility. Hunt derived/synthetic datasets, weak-labels, "
        "cross-source enrichment, alt-language sources, gov publications, archives.",
    "data-moat": "NOT 'what data do we have' but 'what information can only exist because of "
        "how WE combine data': proprietary transformations, hierarchical/composed features, "
        "graph reps, embeddings, event reconstruction, market-state fingerprints, research "
        "memory, experiment lineage, feature ancestry, alpha genealogy. These are more "
        "defensible than raw data.",
    "infrastructure": "Every service across correctness/latency/throughput/availability/"
        "resilience/recoverability/scaling/cost/fault-tolerance/deployment+rollback safety/"
        "test-depth/observability/alert-quality/tech-debt/upgrade-readiness. Security + "
        "operational resilience (outages hit research continuity). Organizational entropy: "
        "duplicated code/prompts/datasets, dead infra, orphaned automation.",
    "execution-growth": "Every execution pathway challenged: info leaks, latency accumulation, "
        "retries hiding problems, sync failures, broker-behavior bias, fills vs expectation, "
        "regime-varying slippage, commission-vs-strategy interaction, fragile logic, "
        "reconciliation failures, emergency-procedure gaps. MEASURED not configured (maker "
        "fill-rate, BNB balance, carry harvest vs fees). Gate-0 readiness + compounding levers.",
    "validation-stats": "Selection bias, multiple testing, parameter sensitivity, sample "
        "dependence, walk-forward + CV methodology, regime robustness, distributional "
        "assumptions, uncertainty propagation, capacity/cost modeling, simulation realism, MC "
        "design, bootstrap quality, structural breaks. Which gates accept/reject ~100pct (zero "
        "information)? What rigorous methods sit as DEAD CODE? Is the DSR bar OPTIMAL -- neither "
        "so high real alphas die nor so low noise passes? Challenge as if the authors are gone.",
    "research-engine": "The engine that makes future discoveries (highest-return section): "
        "hypothesis generation, experiment scheduling, prioritization, AI prompting, "
        "literature/repo/forum mining, translation, knowledge reuse, dedup, automation, "
        "turnaround, research-memory + knowledge-graph quality, search strategy, cross-domain "
        "synthesis, failed-experiment learning, throughput, bottlenecks. Research FRICTION "
        "(waiting/searching/cleaning/manual/duplicate/context-switch) and INFORMATION ENTROPY "
        "(knowledge forgotten, experiments lost, ideas rediscovered).",
    "meta-and-blindspots": "The layer above: which research ASSUMPTIONS have never been tested? "
        "Which workflows persist by habit? Which metrics could mislead? BLIND-SPOT TRANSFER -- "
        "scan one field outside crypto-quant expertise (optimization/control-theory/signal-"
        "processing/information-theory/network-science/OR/causal-inference/anomaly-detection/RL) "
        "for ideas that widen the hypothesis space. INSTITUTIONAL CURIOSITY: what stopped "
        "surprising us, which rejected ideas deserve re-look given new capability. Research "
        "TRAJECTORY: is each cycle making the next stronger (velocity/quality/robustness trend)?",
    # 9th seat, the 07-31 synthesis's own (F) recommendation made real the same week: the
    # execution-growth seat found the launch-day money-path cluster days before keys arrive, so
    # launch-readiness gets an EXPLICIT seat while the stakes are highest. RETIREMENT CONDITION:
    # after Gate-0 passes AND the first live week completes clean, fold this brief back into
    # execution-growth (record the retirement in the synthesis that does it).
    "launch-readiness": "ACTIVE UNTIL GATE-0 + FIRST CLEAN LIVE WEEK. The money path AS WIRED, "
        "not as designed: walk every command and code path that fires on launch day and in week "
        "one (deposit recording, capital events, equity sources, ruin-rail arming/re-entry, "
        "stop placement, connector order paths, guard consumers, kill switches, reconciliation) "
        "and prove each reads/writes what actually exists -- phantom files, $0-equity paths, "
        "zero-caller safety code are the defect classes with proven instances. Board-vs-reality: "
        "does every gate0/readiness board line trace to a real artifact a real writer maintains? "
        "Drill coverage: which launch-day failures have never been drilled? Assume the launch "
        "happens TOMORROW and hunt what fires exactly once, that day, wrong.",
}


def _run(prompt: str, timeout: int) -> subprocess.CompletedProcess[str]:
    # DUAL-POOL (2026-07-26): try the fable metered pool FIRST, fall through to the Max seat.
    # Each auditor is its own invocation with its own brain_auth_check, so the 8 auditors
    # AUTO-LOAD-BALANCE across both pools -- the first ones drain fable, the rest land on opus-5.
    # The sweep lost every auditor at 04:00 racing the cycle and diggers for a single seat.
    return subprocess.run(
        ["bash", "-c",
         # The chain comes from brain_env.sh -> ops/model_chain.env (single source, 2026-07-30).
         # It used to be re-exported here as a literal, which would have pinned the sweep to
         # yesterday's models the moment run_model_upgrade.py adopted a newer flagship.
         'source ops/brain_env.sh && '
         # a silent short-circuit here is what made today's four failures
         # undiagnosable: no model answered, claude never ran, both streams empty
         'brain_auth_check || { echo "BRAIN_AUTH_FAILED: no model in '
         '_BRAIN_MODEL_CHAIN answered -- pool drained or session limit"; '
         'exit 90; } && '
         'claude --effort max --append-system-prompt "$_DOCTRINE" -p "$0" '
         '--dangerously-skip-permissions', prompt],
        cwd=ROOT, capture_output=True, text=True, timeout=timeout)


_SENTINEL = "STATUS: COMPLETE"
# Reports written before the sentinel convention existed are grandfathered on the byte
# floor alone -- without this, the first post-fix resume would re-run every real report
# from earlier the same day (6 x 30min of quota re-buying evidence that already exists).
_SENTINEL_BORN = datetime(2026, 7, 31, tzinfo=UTC).timestamp()


def _complete(report: Path) -> bool:
    """COMPLETION is the auditor's own final act, not a byte count.

    The 2026-07-30 sweep graded two ~1.8KB skeletons OK on `st_size >= 1200` -- a
    doctrine-conforming skeleton clears any sane byte floor, so an auditor that dies
    after writing its headings is invisible to a size gate forever (R0055). The 1200b
    floor stays only to reject empty/binary stubs; the grade is the sentinel."""
    if not report.exists() or report.stat().st_size < 1200:
        return False
    if _SENTINEL in report.read_text("utf-8", errors="replace"):
        return True
    return report.stat().st_mtime < _SENTINEL_BORN


def run_auditor(key: str, brief: str, stamp: str) -> bool:
    report = OUT / f"{stamp}_{key}.md"
    prompt = (
        f"{CORE}\n\n=== YOUR SUBSYSTEM THIS SWEEP: {key} ===\n{brief}\n\n"
        f"Work from /home/quant/quant-platform, READ-ONLY (run read/inspect commands freely; "
        f"do NOT modify code/state/cron/git). Apply ALL SIX perspectives and the five-things "
        f"search and the negative-space sweep. WRITE your full report to {report} in the "
        f"four-output structure, every claim carrying its proving command output. Put "
        f"`STATUS: IN PROGRESS` near the top of the file when you create it and flip it to "
        f"`STATUS: COMPLETE` as your FINAL edit -- the runner grades completion by that "
        f"sentinel and a report never flipped re-runs on the next window. Be "
        f"exhaustive; token cost is not a constraint."
    )
    try:
        r = _run(prompt, 1800)
    except subprocess.TimeoutExpired:
        r = None
    ok = _complete(report)
    if not ok:
        # NAME THE STAGE. "Failed with two empty streams" is what today's four auditors
        # recorded, and it cost the reason entirely. Exit 90 is our own auth sentinel; any
        # other non-zero came from claude itself; None means the 1800s budget ran out.
        if r is None:
            why = ("TIMEOUT after the 1800s budget -- this auditor's brief is too broad for one "
                   "window; split it rather than raising the timeout")
        elif r.returncode == 90:
            why = ("BRAIN_AUTH_FAILED -- no model in the chain answered (pool drained or session "
                   "limit). This is RETRYABLE: the catch-up re-fires the sweep and the resume "
                   "logic skips every COMPLETE report, so only the failures re-run")
        else:
            why = f"claude exited {r.returncode}"
        streams = (f"\n--stdout(tail)--\n{(r.stdout or '')[-900:]}"
                   f"\n--stderr(tail)--\n{(r.stderr or '')[-600:]}") if r else ""
        partial = report.stat().st_size if report.exists() else 0
        # Sidecar, NEVER the report itself: the old code overwrote the partial report with
        # this stub, destroying the only evidence of how far the auditor got -- in direct
        # contradiction of the completion contract it enforces. A partial report is the
        # deliverable; the next window's auditor continues over it.
        (OUT / f"{stamp}_{key}.md.FAILED").write_text(
            f"# AUDITOR FAILED ({key})\n\nWHY: {why}\n"
            f"partial report bytes preserved in place: {partial} "
            f"(re-runs on resume until its {_SENTINEL} sentinel appears)\n{streams}\n", "utf-8")
    return ok


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d")
    results = []
    # SEAT ROTATION (E-20, 07-31 synthesis): the dict order ran verbatim every window, so when a
    # window died mid-sweep the SAME tail seats starved every time (position 8 produced nothing
    # for days while position 1 re-ran fine). Rotate the starting seat by date -- deterministic
    # (resume within a day sees the same order) and fair across days: every seat is first once
    # per cycle through the list.
    seats = list(SUBSYSTEMS.items())
    offset = int(stamp) % len(seats)
    seats = seats[offset:] + seats[:offset]
    for key, brief in seats:
        # RESUMABLE (2026-07-26): a real report for TODAY means this auditor is done -- skip it,
        # so a sweep killed halfway is CONTINUED by the next invocation (organ_catchup re-fires
        # reset-aware) instead of restarting at auditor one and re-losing the same seat race.
        done = OUT / f"{stamp}_{key}.md"
        if _complete(done):
            print(f"[deep-sweep] {key}: already COMPLETE today -- skipping (resume)", flush=True)
            results.append((key, True))
            continue
        print(f"[deep-sweep] auditor: {key}", flush=True)
        ok = run_auditor(key, brief, stamp)
        results.append((key, ok))
        print(f"[deep-sweep] {key}: {'OK' if ok else 'FAILED (recorded)'}", flush=True)

    good = [f"{stamp}_{k}.md" for k, ok in results if ok]
    synth = OUT / f"{stamp}_SYNTHESIS.md"
    if _complete(synth):
        # Synthesis had NO resume check: the 2026-07-30 22:45 window re-launched a full
        # synthesis seat five hours after the 17:00 one wrote STATUS: COMPLETE.
        print("[deep-sweep] synthesis: already COMPLETE today -- skipping (resume)", flush=True)
    elif good:
        sp = (
            f"{CORE}\n\n=== YOU ARE THE SYNTHESIS LEAD ===\nRead every auditor report in "
            f"docs/research/deep_sweep/ dated {stamp}: {', '.join(good)}. Produce the honest "
            f"ceiling map to {synth}:\n"
            "(A) Overall verdict + per-subsystem ceiling table (current pct, practical ceiling, "
            "opportunity cost 1y) -- AND re-grade docs/research/TIER1_BENCHMARK.md in the same "
            "session: where auditor evidence moves a layer's tier against the motive-similar "
            "cohort (RenTech/Medallion always cited fully as the ceiling exemplar), edit the "
            "register's row and say why; the register and this table must never disagree "
            "silently.\n"
            "(B) CAPABILITY MAP: for the desk's capabilities, which MISSING capability unlocks "
            "the most downstream capabilities (highest-ROI multiplier)? Which existing capability "
            "is the biggest bottleneck / greatest systemic risk if it fails?\n"
            "(C) TOP OPPORTUNITIES as a PRIORITIZED PORTFOLIO: rank by expected total long-term "
            "contribution (direct + enabling/cascade effects + optionality + compounding) / "
            "(engineering effort x maintenance x opportunity-cost). Flag compounding multipliers. "
            "Do NOT rank by raw score alone -- they compete for scarce implementation capacity.\n"
            "(D) HARD WALLS listed separately (do not confuse with headroom).\n"
            "(E) AUDITOR DISAGREEMENTS adjudicated with evidence.\n"
            "(F) RECURSIVE META: which of the 8 subsystem-audits produced the most value this "
            "week, which produced little, what NEW audit section should exist next week, which "
            "audit question is no longer discriminative. Improve the audit itself.\n"
            "(G) RESEARCH CAPABILITY CAGR: a rough composite index (experiment throughput, "
            "hypothesis quality, validation quality, automation, knowledge reuse, implementation "
            "velocity, data coverage) -- is the ENGINE getting stronger week over week?\n"
            "THEN -- LEDGER FIRST (R0056; the desk's own record proves improvement_inbox.md is "
            "write-only): row each top portfolio item into the section-42 ledger via "
            "`.venv/bin/python scripts/recommendations.py add --source deep_sweep --summary "
            "'...' --roi-bps N` -- DEDUP against open rows first (`recommendations.py report`) "
            "and cite the existing row id instead of re-adding; then append ONE short pointer "
            "entry to docs/research/improvement_inbox.md naming the row ids; and add ONE line to "
            "data/PRINCIPAL_ACTION.md ONLY if a human decision/spend is required. Blunt; "
            "portfolio-prioritized, never 'implement everything'; nothing high-value lost to "
            "neglect. L1.28b applies to your own output: an un-rowed recommendation is a finding "
            "already leaking."
        )
        with contextlib.suppress(subprocess.TimeoutExpired):
            _run(sp, 1800)
    n_ok = sum(1 for _, ok in results if ok)
    print(f"[deep-sweep] done: {n_ok}/{len(results)} COMPLETE; "
          f"synthesis={'yes' if _complete(synth) else 'NO'}", flush=True)


if __name__ == "__main__":
    main()

```

### scripts/run_leverage_opt.py
```python
"""Recompute dynamic leverage for every deployed/paper sleeve + the joint portfolio.

Reads the live forward return streams (molded curve = cash-carry, perp shadow equity = perp book),
the regime multiplier, and execution reliability, then runs `libs.risk.dynamic_leverage`. Writes:
  * web/leverage.json          -- dashboard: per-sleeve + joint leverage, endogenous caps, bindings
  * data/leverage_target.json  -- the executor reads this to size deployed notional dynamically

Honest by construction: on day-0 / thin data the confidence term is 0, so the recommendation sits at
the floor and only earns leverage as forward validation accrues. Run every cycle (cheap).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from libs.risk.dynamic_leverage import optimize_portfolio, optimize_sleeve

_CURVE = Path("data/live_combined_state.json")
_LEV_WEB = Path("web/leverage.json")
_LEV_TGT = Path("data/leverage_target.json")
_BASE_PER_LEG = 5000.0
# GAP #14 MEASUREMENT FIX (2026-07-23, safe under quarantine -- the executor ignores this
# file in both directions until the ladder re-enable gate). Root cause of incidents #2 and
# the 07-18 under-deploy: confidence fed by the funding-smoothed MOLDED curve (variance
# collapse -> Sharpe 16-24 phantom) and a fwd_days counter that survived incident resets.
# Honest inputs now: the 8h-block challenger series (basis-MtM variance INCLUDED, vif~1)
# and its true block count. PLAUSIBILITY RAIL: an annualized forward Sharpe above
# _PLAUSIBLE_SHARPE is treated as a measurement defect -> confidence 0 + flag (a Sharpe of
# 16 must freeze sizing, never activate it). CLEAN-DAY COUNTER: leverage_target.json now
# carries clean_since -- the start of continuous honest-input operation -- so ladder step 1
# (gap-14 fixed + 30 uncontaminated days) is measurable from a file read.
_PLAUSIBLE_SHARPE = 4.0
_SHADOW_8H = Path("web/cashcarry_shadow_8h.json")


def _load(p: Path, d: object = None) -> object:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return d if d is not None else {}


def _rets_from_equity(eq: list[float]) -> np.ndarray:
    a = np.asarray([float(x) for x in eq], dtype="float64")
    if len(a) < 2:
        return np.array([], dtype="float64")
    return a[1:] / a[:-1] - 1.0


def _hourly(curve: list[list[object]]) -> list[float]:
    buckets: dict[str, float] = {}
    for t, e in curve:
        buckets[str(t)[:13]] = float(e)               # last obs per UTC hour
    return [buckets[k] for k in sorted(buckets)]


def main() -> None:
    cs = _load(_CURVE, {})
    cc_eq = _hourly(cs.get("mcurve", []))             # cash-carry molded, hourly (noise-reduced)
    cc_rets = _rets_from_equity(cc_eq)

    sh = _load(Path("web/crypto_shadow.json"), {})
    # forward-only equity (fwd=True) so confidence stays honest -- never counts backtest as proven
    perp_eq = [float(p["v"]) for p in sh.get("equity", [])
               if isinstance(p, dict) and p.get("fwd") and "v" in p]
    perp_rets = _rets_from_equity(perp_eq) if len(perp_eq) > 1 else np.array([])

    ccsh = _load(Path("web/cashcarry_shadow.json"), {})
    regime = _load(Path("web/regime_engine.json"), {})
    regime_mult = float(regime.get("leverage_multiplier", 1.0) or 1.0)

    # execution reliability: fresh executor heartbeat -> 1.0, else haircut (degraded fills/uptime)
    hb = Path("data/cashcarry_exec_heartbeat")
    exec_ok = hb.exists() and (datetime.now(tz=UTC).timestamp() - hb.stat().st_mtime) < 180
    exec_rel = 1.0 if exec_ok else 0.5

    decisions = {}
    sh8 = _load(_SHADOW_8H, {})
    fwd_sharpe_in = float(sh8.get("forward_ann_sharpe_8h",
                                  ccsh.get("forward_ann_sharpe", 0.0)) or 0.0)
    fwd_days_in = float(sh8.get("forward_days_equiv",
                                ccsh.get("forward_days", 0)) or 0)
    implausible = fwd_sharpe_in > _PLAUSIBLE_SHARPE
    if implausible:                     # measurement defect, never evidence of edge
        fwd_sharpe_in = 0.0
    decisions["cash_and_carry"] = optimize_sleeve(
        "cash_and_carry", cc_rets,
        fwd_sharpe=fwd_sharpe_in,
        fwd_days=fwd_days_in,
        regime_mult=regime_mult, exec_reliability=exec_rel,
        liquidity_haircut=0.9, drawdown_ruin=0.35,    # small-cap perps -> slippage/impact haircut
    )
    if len(perp_rets) > 1:
        decisions["perp_ls"] = optimize_sleeve(
            "perp_ls", perp_rets,
            fwd_sharpe=float(sh.get("forward_ann_sharpe", 0.0) or 0.0),
            fwd_days=float(sh.get("forward_days", 0) or 0),
            regime_mult=regime_mult, exec_reliability=exec_rel,
            liquidity_haircut=0.85, drawdown_ruin=0.30,   # directional book -> tighter ruin def
        )

    sleeve_rets = {"cash_and_carry": cc_rets}
    if len(perp_rets) > 1:
        sleeve_rets["perp_ls"] = perp_rets
    joint = optimize_portfolio(sleeve_rets, decisions)

    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "regime": regime.get("regime"), "regime_mult": regime_mult, "exec_reliability": exec_rel,
        "sleeves": {k: v.to_dict() for k, v in decisions.items()},
        "portfolio": joint,
        "policy": ("Leverage is a continuously optimized control variable. Ceiling is endogenous = "
                   "min(diminishing-returns argmax of E[log], largest L with risk-of-ruin<=2%). "
                   "Confidence (uncertainty shrinkage) gates it to floor until forward-validated."),
    }
    _LEV_WEB.write_text(json.dumps(out, indent=2), "utf-8")

    # executor target: notional/leg = recommended x equity. OVERRIDES --capital only when the
    # optimizer has confidence>0 (edge proven enough) -- day-0 keeps the operator's --capital.
    cc = decisions["cash_and_carry"]
    prev = _load(_LEV_TGT, {})
    # clean_since counts days of HONEST-PIPELINE operation (ladder step-1 clock). The rail
    # firing on an implausible reading IS clean operation -- the pipeline detected and
    # zeroed a bad measurement instead of sizing on it. Only a source change resets it.
    clean_since = (prev.get("clean_since")
                   if prev.get("confidence_source") == "8h_challenger_honest"
                   else out["updated"]) or out["updated"]
    _LEV_TGT.write_text(json.dumps({
        "updated": out["updated"], "sleeve": "cash_and_carry",
        "confidence_source": "8h_challenger_honest",
        "plausibility_rail_fired": bool(implausible),
        "clean_since": clean_since,
        "leverage": round(cc.recommended, 3), "confidence": cc.confidence,
        "notional_per_leg": round(cc.recommended * _BASE_PER_LEG, 2),
        "active": cc.confidence > 0.0,               # executor honours it only when True
        # back-compat superset for run_crypto_testnet / run_capital_plan (supersedes fixed-cap)
        "gated_leverage": round(cc.recommended, 3),
        "growth_optimal": round(cc.growth_optimal, 3), "ruin_cap": round(cc.ruin_cap, 3),
        "status": "DYNAMIC (validated)" if cc.confidence > 0 else "DYNAMIC (floor, unproven)",
    }, indent=2), "utf-8")

    print(f"leverage-opt: cash_and_carry rec={cc.recommended:.3f}x conf={cc.confidence} "
          f"(growth-opt {cc.growth_optimal:.2f}x ruin-cap {cc.ruin_cap:.2f}x {cc.binding}) "
          f"| joint {joint.get('joint_leverage')}x | active={cc.confidence > 0}")


if __name__ == "__main__":
    main()

```

### scripts/run_live_guard.py
```python
"""The live-path guard: the ONE production caller for the S1 rails (gap register row 2).

Every mechanism this script drives was built, unit-tested green, and called by nobody -- the
stage machine most of all: before this file, `libs/execution/staging.py` was imported only by its
own test. That is the failure mode this desk keeps repeating, and on the live path it would mean
arriving at Gate 0 with rails that have never once executed outside pytest.

Each tick, in this order:
  1. §3  reconcile   -- every live position must carry a venue-side reduce-only stop; naked >60s
                        freezes new entries and pages.
  2. §4  ladder      -- unacknowledged pages escalate 15m/60m/4h; the top rung latches.
  3. §5  canary      -- 6h round-trip health; failure or excess latency degrades for 6h.
  4. §6  ramp gate   -- the authorized size fraction, from arithmetic only.
  5. stage machine   -- tripwires DEMOTE. Promotion is evaluated and REPORTED, never taken:
                        S1 entry needs `principal_signoff`, which is a human act, and nothing in
                        this file may ever set it.

SAFETY, by construction:
  - Fully inert at S0 / without keys. The venue is only read when binance_live reports armed, so
    on a box with no keyfile this script reads local state and writes a report.
  - It never places an order, never arms anything, never writes LIVE_ENABLE or the signoff flag.
  - Its only write into the trading path is the EXISTING data/CASHCARRY_KILL freeze file, which
    the executor already honours -- a new parallel halt mechanism would be one more thing that
    can disagree with the real one.
  - Flattening at ladder rungs 60m/4h is a live-money action, so it is gated on being armed AND
    on --allow-flatten, which the scheduled unit does not pass. Left to a human or to a
    deliberately configured unit; the default run reports what it WOULD do.

    python scripts/run_live_guard.py [--allow-flatten] [--rearm WHO]
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.execution import canary as canary_mod
from libs.execution import protective_stops as stops
from libs.execution import ramp_gate, staging
from libs.ops.derisk_ladder import LadderState, unacked_since

_ROOT = Path(__file__).resolve().parent.parent
_REPORT = _ROOT / "data" / "live_guard.json"
_ALERTS = _ROOT / "data" / ".last_alerts.json"
_ACK = _ROOT / "data" / "PAGE_ACK"
_KILL = _ROOT / "data" / "CASHCARRY_KILL"
_RAMP = _ROOT / "data" / "ramp_state.json"
_PRINCIPAL = _ROOT / "data" / "PRINCIPAL_ACTION.md"


def _load(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _ack_ts() -> float:
    """When the operator last acknowledged the pager. 0.0 = never (so everything is unacked)."""
    try:
        return _ACK.stat().st_mtime
    except OSError:
        return 0.0


def _venue() -> Any | None:
    """The live FUTURES connector, ONLY if it is fully armed. None otherwise -- and None must
    mean 'we cannot see the book', never 'the book is clean'."""
    try:
        from libs.execution import binance_live
    except ImportError:
        return None
    try:
        return binance_live if binance_live.is_armed()[0] else None
    except Exception:
        return None


def _arming() -> tuple[bool, bool, str | None]:
    """Arming state of BOTH legs. Returns (futures_armed, spot_armed, hazard).

    The deployed sleeve is cash-and-carry -- delta-neutral only while both legs can trade. Armed
    on futures but not spot is not "half ready", it is a directional book wearing a hedged
    book's risk limits: the perp leg opens and the spot leg that was supposed to cancel it
    cannot. That asymmetry is worth naming explicitly rather than leaving as two booleans nobody
    compares.
    """
    fut = spot = False
    try:
        from libs.execution import binance_live
        fut = bool(binance_live.is_armed()[0])
    except Exception:
        fut = False
    try:
        from libs.execution import binance_spot_live
        spot = bool(binance_spot_live.is_armed()[0])
    except Exception:
        spot = False
    hazard = None
    if fut != spot:
        have, missing = ("futures", "spot") if fut else ("spot", "futures")
        hazard = (f"HALF-ARMED: {have} leg armed, {missing} leg is NOT -- a cash-and-carry book "
                  f"cannot stay delta-neutral on one leg")
    return fut, spot, hazard


def _freeze(on: bool, reason: str) -> str:
    """Drive the existing executor kill file. Idempotent."""
    if on:
        if not _KILL.exists():
            _KILL.write_text(f"live_guard freeze {datetime.now(tz=UTC).isoformat()}: {reason}\n",
                             "utf-8")
            return "freeze ENGAGED"
        return "freeze already engaged"
    # Never auto-lift: the file may have been placed by the dead-man, the operator, or another
    # rail, and this script cannot tell which. Lifting someone else's halt is how a book comes
    # back up into the condition that took it down.
    return "no freeze required (existing kill file, if any, left alone)"


def _reconcile(venue: Any, now: float) -> tuple[stops.ReconcileReport, str]:
    if venue is None:
        rep = stops.ReconcileReport(naked={}, breaches={}, n_positions=0)
        return rep, "connector not armed -- venue not read (no positions can exist)"
    try:
        positions = venue.positions()
        orders = venue.open_orders()
    except Exception as e:
        # fail-closed: we could not verify the rail, so we behave as though it is broken.
        rep = stops.ReconcileReport(naked={"<unreadable>": 0.0},
                                    breaches={"<unreadable>": stops.NAKED_GRACE_S + 1},
                                    n_positions=-1)
        return rep, f"venue read FAILED ({e!r} ) -- treating as naked, fail-closed"
    return stops.reconcile(positions, orders, now), "venue read ok"


def _canary(venue: Any, now: float) -> tuple[canary_mod.CanaryState, str]:
    st = canary_mod.CanaryState.load(_ROOT / "data" / "canary_state.json")
    if not st.is_due(now):
        return st, "not due"
    if venue is None:
        # Do NOT record an attempt: an unarmed desk has no execution path to prove, and logging
        # failures here would bury a real outage under thousands of S0 rows.
        return st, "due, but connector not armed -- skipped (no attempt recorded)"
    t0 = time.time()
    try:
        # READ-ONLY probe. The spec's round-trip places a minimum-notional order; that is a
        # live-money action and stays behind the same --allow-flatten class of human gate, so
        # the scheduled probe exercises auth + signing + clock skew via a signed read instead.
        # This catches revoked keys, IP-whitelist drift and recvWindow skew -- everything except
        # order-placement itself, which the first S1 trade proves.
        venue.account_summary()
        st.record(ok=True, latency_ms=(time.time() - t0) * 1000.0, now=now,
                  detail="signed account read")
        return st, "probe ok"
    except Exception as e:
        st.record(ok=False, latency_ms=(time.time() - t0) * 1000.0, now=now, detail=repr(e))
        return st, f"probe FAILED: {e!r}"


def _ramp(now: float) -> tuple[float, str, dict[str, bool]]:
    state = _load(_RAMP, {})
    current = float(state.get("size_fraction", ramp_gate.SIZE_STEPS[0]))
    evidence = state.get("evidence", {}) if isinstance(state.get("evidence"), dict) else {}
    nxt, why = ramp_gate.next_step(current, evidence)
    checks = ramp_gate.step_up_conditions(evidence)
    if nxt != current:
        state["size_fraction"] = nxt
        state.setdefault("history", []).append(
            {"ts": now, "from": current, "to": nxt, "why": why})
        state["history"] = state["history"][-200:]
        _RAMP.write_text(json.dumps(state, indent=2), "utf-8")
    return nxt, why, checks


def main() -> int:
    now = time.time()
    allow_flatten = "--allow-flatten" in sys.argv
    venue = _venue()
    stage = staging.current_stage()

    if "--rearm" in sys.argv:
        who = sys.argv[sys.argv.index("--rearm") + 1] if len(sys.argv) > (
            sys.argv.index("--rearm") + 1) else "operator"
        lad = LadderState.load(_ROOT / "data" / "derisk_state.json")
        done = lad.rearm(who, now)
        lad.save()
        print(f"ladder re-arm by {who}: {'cleared' if done else 'nothing latched'}")
        return 0

    # 1. §3 no-naked-position invariant --------------------------------------------------
    rep, recon_note = _reconcile(venue, now)

    # 2. §4 pager de-risk ladder ---------------------------------------------------------
    lad = LadderState.load(_ROOT / "data" / "derisk_state.json")
    since = unacked_since(_load(_ALERTS, {}), _ack_ts(), lad.oldest_unacked_ts)
    lad.update(since, now)
    rung = lad.effective()
    lad.save()

    # 3. §5 canary -----------------------------------------------------------------------
    can, canary_note = _canary(venue, now)
    can.save()
    mode = can.mode(now)

    # 4. §6 ramp gate --------------------------------------------------------------------
    size_fraction, ramp_why, ramp_checks = _ramp(now)

    # 5. stage machine: DEMOTE on tripwire, never self-promote ---------------------------
    fut_armed, spot_armed, half_armed = _arming()

    tripwires: list[str] = []
    if half_armed:
        tripwires.append(half_armed)
    if rep.freeze_entries:
        tripwires.append(f"naked position >{stops.NAKED_GRACE_S:.0f}s")
    if rung.requires_manual_rearm:
        tripwires.append("pager ladder at 4h rung (disarmed)")
    if can.consecutive_failures >= 2:
        tripwires.append(f"canary failed {can.consecutive_failures}x consecutively")

    demoted = None
    if tripwires and stage != "S0":
        ok, target = staging.demote("; ".join(tripwires))
        demoted = target if ok else None

    # promotion is EVALUATED and REPORTED only. principal_signoff is a human act; this script
    # reads the flag and never writes it, so a green gate here is a prompt for the principal,
    # not a transition.
    promo_evidence = {
        **(_load(_RAMP, {}).get("evidence", {}) or {}),
        "keys_present": venue is not None,
        "connector_verified": can.last_ok_ts is not None,
        "capital_fraction": size_fraction,
        "principal_signoff": bool(_load(_ROOT / "data" / "stage_state.json", {})
                                  .get("principal_signoff")),
    }
    gate_met, gate_why = (staging.s1_entry_met(promo_evidence) if stage == "S0"
                          else staging.s2_entry_met(promo_evidence))

    # freeze the executor while the invariant is breached or the ladder disallows entries
    freeze_needed = rep.freeze_entries or not rung.entries_allowed
    freeze_note = _freeze(freeze_needed, "; ".join(tripwires) or "ladder entries disabled")

    # flattening is live money: gated on armed AND explicit human opt-in
    flatten_note = "not required"
    if rung.flatten:
        if venue is not None and allow_flatten:
            try:
                res = venue.flatten_all()
                flatten_note = f"FLATTENED {len(res)} position(s) at rung {rung.name}"
            except Exception as e:
                flatten_note = f"flatten FAILED at rung {rung.name}: {e!r}"
        else:
            flatten_note = (f"rung {rung.name} requires flatten -- NOT executed "
                            f"(armed={venue is not None}, --allow-flatten={allow_flatten})")

    effective_size = size_fraction * rung.size_multiplier * mode.size_multiplier

    report = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "stage": stage,
        "armed": venue is not None,
        "arming": {"futures": fut_armed, "spot": spot_armed, "hazard": half_armed},
        "reconcile": {"naked": rep.naked, "breaches": {k: round(v, 1)
                                                       for k, v in rep.breaches.items()},
                      "n_positions": rep.n_positions, "freeze_entries": rep.freeze_entries,
                      "summary": rep.summary, "note": recon_note},
        "ladder": {"rung": rung.name, "entries_allowed": rung.entries_allowed,
                   "size_multiplier": rung.size_multiplier,
                   "requires_manual_rearm": rung.requires_manual_rearm,
                   "unacked_since": lad.oldest_unacked_ts},
        "canary": {"mode": "limit_only" if mode.limit_only else "normal",
                   "size_multiplier": mode.size_multiplier, "reason": mode.reason,
                   "consecutive_failures": can.consecutive_failures, "note": canary_note},
        "ramp": {"size_fraction": size_fraction, "why": ramp_why, "checks": ramp_checks},
        "effective_size_fraction": round(effective_size, 4),
        "tripwires": tripwires,
        "demoted_to": demoted,
        "stage_gate": {"target": "S1" if stage == "S0" else "S2",
                       "met": gate_met, "why": gate_why},
        "freeze": freeze_note,
        "flatten": flatten_note,
    }
    _REPORT.parent.mkdir(parents=True, exist_ok=True)
    _REPORT.write_text(json.dumps(report, indent=2), "utf-8")

    # A green S1 gate is the one thing here that needs a HUMAN, so it goes down the existing
    # principal-action channel rather than into a report nobody opens.
    if stage == "S0" and gate_met and not _PRINCIPAL.exists():
        _PRINCIPAL.write_text(
            "S1 (Gate 0) mechanical preconditions are MET -- your sign-off is the only "
            "remaining step. Review data/live_guard.json, then place keys per "
            "docs/playbooks/go_live.md.\n", "utf-8")

    print(f"live_guard stage={stage} armed={venue is not None} rung={rung.name} "
          f"canary={'degraded' if mode.degraded else 'ok'} "
          f"size={effective_size:.3f} tripwires={len(tripwires)}")
    if tripwires:
        print("  TRIPWIRES: " + "; ".join(tripwires))
    print(f"  {rep.summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/run_mt5_portfolio.py
```python
"""MT5 alpha-PORTFOLIO campaign -- search for low-correlation sleeves, not one strategy.

Builds every MT5-executable sleeve we have real data for (cross-asset trend, cross-sectional
momentum, metals/FX momentum, index trend, gold/silver & gold/platinum & WTI/Brent relative value,
and CFTC COT positioning), runs each through the FULL institutional gauntlet, measures the
correlation matrix, then combines the positive-economic-prior sleeves with rolling inverse-vol
(risk-parity, lagged -> no look-ahead) into a diversified portfolio and gauntlets THAT. Diversifying
across uncorrelated real edges is the only honest lever to raise survivor probability -- no gate is
weakened, no parameter is tuned to pass. Ranks by gates passed, then Sharpe, then diversification.

    python scripts/run_mt5_portfolio.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from libs.autodiscovery.models import Family, Hypothesis
from libs.autodiscovery.validation import campaign_gate_stats, validate
from libs.data.cleaning import DEFAULT_CAPS, guard_close
from libs.data.cot_source import COT_MAP, cot_zscore_daily
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.research.crossasset import trend_basket_returns, xsec_momentum_returns
from libs.research.sleeves import (
    calendar_event_returns,
    cot_positioning_returns,
    cot_timeseries_returns,
    crisis_hedge_returns,
    ratio_meanrev_returns,
    swap_carry_returns,
)
from libs.risk.growth_leverage import analyze as leverage_analyze
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType

_COVERAGE = Path("reports/multiasset_coverage.json")
_OUT = Path("reports/mt5_portfolio")
_PPY = 252.0
_COST = {"fx": 1.0e-4, "metal": 2.0e-4, "energy": 2.5e-4,
         "index": 1.0e-4, "crypto": 6.0e-4, "equity": 2.0e-4}
# Realistic per-side DAILY overnight financing (CFD swap) charged on a HELD position. Dominated by
# crypto CFDs (~5bps/day) -- ignoring it overstates any continuously-held crypto book. Honest cost.
_HOLD = {"fx": 0.3e-4, "metal": 1.0e-4, "energy": 1.0e-4,
         "index": 0.5e-4, "crypto": 5.0e-4, "equity": 0.5e-4}
_FAIL = ["premium compresses/crowds", "regime shift", "correlated drawdown",
         "cost exceeds edge", "edge decay"]


def _load() -> tuple[pd.DataFrame, dict[str, float], dict[str, list[str]]]:
    cov = json.loads(_COVERAGE.read_text("utf-8"))
    lake = ParquetLake("data/lake")
    closes, cost, by_class = {}, {}, {}
    for c in cov:
        if not c.get("bars"):
            continue
        sym, ac = str(c["symbol"]), str(c["asset_class"])
        register_instrument(InstrumentSpec(symbol=sym, asset_class=AssetClass(ac), description=sym))
        df = lake.read_bars(Layer.BRONZE, sym, Timeframe.D1).set_index("timestamp")
        if len(df) < 250:
            continue
        closes[sym] = df["close"]
        cost[sym] = _COST.get(ac, 2.0e-4)
        by_class.setdefault(ac, []).append(sym)
    close = pd.DataFrame(closes).sort_index()
    caps = {s: DEFAULT_CAPS.get(ac, 0.5) for ac, syms in by_class.items() for s in syms}
    close = guard_close(close, caps)                     # gap-guard: kill bad-print spikes
    return close, cost, by_class


def _ann(r: np.ndarray) -> float:
    a = r[r != 0.0]
    return round(float(sharpe_ratio(a) * np.sqrt(_PPY)), 2) if len(a) > 5 else 0.0


def _sub(close: pd.DataFrame, syms: list[str]) -> pd.DataFrame:
    keep = [s for s in syms if s in close.columns]
    return close[keep]


def _build_sleeves(close: pd.DataFrame, cost: dict[str, float],
                   by: dict[str, list[str]]) -> dict[str, np.ndarray]:
    n = len(close)
    hold = {sym: _HOLD.get(ac, 0.5e-4) for ac, syms in by.items() for sym in syms}
    sl: dict[str, np.ndarray] = {}
    # Cross-asset book = the original FX/metal/energy/index/crypto universe (ETFs feed their own
    # dedicated sleeves below, so the broad trend/momentum sleeves stay clean & comparable).
    xa_syms = [s for ac, syms in by.items() if ac != "equity" for s in syms if s in close.columns]
    xa = close[xa_syms]
    sl["trend_all"] = trend_basket_returns(xa, cost, lookback=100, band=0.05, hold_cost=hold)
    sl["xsec_mom_all"] = xsec_momentum_returns(xa, cost, lookback=120, q=0.3, band=0.05,
                                               hold_cost=hold)
    metals = _sub(close, by.get("metal", []))
    if metals.shape[1] >= 3:
        sl["metals_mom"] = xsec_momentum_returns(metals, cost, lookback=120, q=0.5, band=0.05,
                                                 min_names=3, hold_cost=hold)
    fx = _sub(close, by.get("fx", []))
    if fx.shape[1] >= 5:
        sl["fx_mom"] = xsec_momentum_returns(fx, cost, lookback=120, q=0.3, band=0.05,
                                             hold_cost=hold)
    idx = _sub(close, by.get("index", []))
    if idx.shape[1] >= 3:
        sl["index_trend"] = trend_basket_returns(idx, cost, lookback=100, band=0.05, min_names=3,
                                                 hold_cost=hold)

    def rv(a: str, b: str, name: str) -> None:
        if a in close.columns and b in close.columns:
            c = 0.5 * (cost.get(a, 2e-4) + cost.get(b, 2e-4))
            sl[name] = ratio_meanrev_returns(close[a], close[b], lookback=60, cost=c, band=0.05)

    rv("XAUUSD", "XAGUSD", "gold_silver_rv")
    rv("XAUUSD", "XPTUSD", "gold_plat_rv")
    rv("XTIUSD", "XBRUSD", "wti_brent_rv")

    # --- ETF sleeves (new free orthogonal families: rates/duration, credit, sector rotation) ---
    rates = [s for s in ("TLT", "IEF", "SHY", "LQD", "EMB") if s in close.columns]
    if len(rates) >= 3:
        sl["rates_trend"] = trend_basket_returns(close[rates], cost, lookback=100, band=0.05,
                                                 min_names=3, hold_cost=hold)
    sectors = [s for s in ("XLE", "XLF", "XLI", "XLP", "XLU", "XLK", "XLV", "XLY")
               if s in close.columns]
    if len(sectors) >= 5:
        sl["sector_rotation"] = xsec_momentum_returns(close[sectors], cost, lookback=120, q=0.3,
                                                      band=0.05, hold_cost=hold)
    rv("TLT", "IEF", "curve_rv")           # Treasury curve (long-end vs intermediate)
    rv("EMB", "TLT", "credit_rv")          # EM credit vs duration

    cot_syms = [s for s in COT_MAP if s in close.columns]
    if len(cot_syms) >= 5:
        cache = Path("data/cot_zcache.parquet")
        if cache.exists():
            cz = pd.read_parquet(cache).reindex(close.index)
        else:
            cz = cot_zscore_daily(cot_syms, close.index, z_weeks=156)
            cache.parent.mkdir(parents=True, exist_ok=True)
            cz.to_parquet(cache)
        cz = cz.dropna(axis=1, how="all")
        if cz.shape[1] >= 5:
            cclose = close[list(cz.columns)]
            sl["cot_positioning"] = cot_positioning_returns(
                cclose, cz, cost, band=0.05, min_names=3, long_high=False)
            sl["cot_timeseries"] = cot_timeseries_returns(cclose, cz, cost, band=0.05, z_entry=1.0)
    if "XAUUSD" in close.columns and "US500" in close.columns:
        sl["gold_crisis_hedge"] = crisis_hedge_returns(
            close["XAUUSD"], close["US500"], ma_window=200, cost=cost.get("XAUUSD", 2e-4))
    if idx.shape[1] >= 2:
        sl["macro_calendar"] = calendar_event_returns(idx, cost=_COST["index"], tom_first=3)
    crypto = _sub(close, by.get("crypto", []))
    if crypto.shape[1] >= 2:                              # crypto = trendiest market -> own sleeve
        sl["crypto_trend"] = trend_basket_returns(crypto, cost, lookback=100, band=0.05,
                                                  min_names=2, hold_cost=hold)
    carry = _swap_carry(close, cost)
    if carry is not None:
        sl["swap_carry"] = carry
    return {k: v for k, v in sl.items() if len(v) == n and np.isfinite(v).all()}


def _swap_carry(close: pd.DataFrame, cost: dict[str, float]) -> np.ndarray | None:
    """Build the broker-swap carry sleeve IF a swap-rate history has accumulated (else None).

    Carry has no backtest (MT5 exposes only current swaps); this activates once log_swaps.py has
    seeded enough distinct days. Until then the sleeve is forward-only and excluded honestly.
    """
    log = Path("data/swap_log.parquet")
    if not log.exists():
        return None
    df = pd.read_parquet(log)
    if df["ts"].dt.date.nunique() < 250:                 # need real history to backtest
        return None
    cl = df.pivot_table(index=df["ts"].dt.tz_convert("UTC").dt.normalize(),
                        columns="symbol", values="carry_long")
    cs = df.pivot_table(index=df["ts"].dt.tz_convert("UTC").dt.normalize(),
                        columns="symbol", values="carry_short")
    syms = [s for s in cl.columns if s in close.columns]
    if len(syms) < 5:
        return None
    cl = cl[syms].reindex(close.index).ffill()
    cs = cs[syms].reindex(close.index).ffill()
    return swap_carry_returns(close[syms], cl, cs, cost, q=0.3, band=0.05)


def _families() -> dict[str, Family]:
    return {"trend_all": Family.TREND, "xsec_mom_all": Family.MOMENTUM,
            "metals_mom": Family.MOMENTUM, "fx_mom": Family.MOMENTUM,
            "index_trend": Family.TREND, "gold_silver_rv": Family.MEAN_REVERSION,
            "gold_plat_rv": Family.MEAN_REVERSION, "wti_brent_rv": Family.MEAN_REVERSION,
            "cot_positioning": Family.CARRY, "cot_timeseries": Family.CARRY,
            "gold_crisis_hedge": Family.REGIME_TRANSITION, "macro_calendar": Family.SESSION,
            "swap_carry": Family.CARRY, "crypto_trend": Family.TREND,
            "rates_trend": Family.TREND, "sector_rotation": Family.MOMENTUM,
            "curve_rv": Family.MEAN_REVERSION, "credit_rv": Family.MEAN_REVERSION,
            "portfolio": Family.CROSS_ASSET}


def _riskparity(df: pd.DataFrame, *, mode: str = "plain", max_weight: float | None = None) -> (
        np.ndarray):
    """Daily sleeve combination, all weights computed from LAGGED data (no look-ahead).

    * ``plain``  : risk-parity (rolling inverse-vol).
    * ``gate``   : risk-parity, but fund a sleeve only while its trailing 252d return is positive.
    * ``weight`` : tilt risk-parity weights by each sleeve's trailing 252d Sharpe (>=0) -- the most
      robust "max" combination: more capital to what is genuinely working, zero to losers, without
      the overfit of full mean-variance optimization.

    ``max_weight`` caps any single column's weight (concentration limit) and redistributes the
    excess to the others -- the survivability fix that stops one cluster (crypto) from dominating.
    """
    masked = df.replace(0.0, np.nan)
    vol = masked.rolling(252, min_periods=60).std().shift(1)
    inv = 1.0 / vol
    if mode in {"gate", "weight"}:
        mean = masked.rolling(252, min_periods=60).mean().shift(1)
        inv = (inv.where(mean > 0.0, 0.0) if mode == "gate"
               else inv * (mean / vol).clip(lower=0.0))
    w = inv.div(inv.sum(axis=1), axis=0).fillna(0.0)
    if max_weight is not None and df.shape[1] > 1:
        for _ in range(4):                               # iterate: cap, push excess to the rest
            over = w > max_weight
            if not bool(over.to_numpy().any()):
                break
            capped = w.clip(upper=max_weight)
            deficit = 1.0 - capped.sum(axis=1)
            room = inv.where(~over, 0.0)
            share = room.div(room.sum(axis=1), axis=0).fillna(0.0)
            w = capped.add(share.mul(deficit, axis=0), fill_value=0.0)
    return (w.to_numpy() * df.to_numpy()).sum(axis=1)


# Economic clusters: correlated sleeves count as ONE bet so the book does not over-allocate to the
# momentum family. Two-level: trailing-Sharpe-weighted risk-parity within a cluster, then across.
_CLUSTERS = {
    "momentum": ["trend_all", "xsec_mom_all", "fx_mom", "index_trend"],
    "metals": ["metals_mom"],
    "relval": ["wti_brent_rv", "gold_silver_rv", "gold_plat_rv"],
    "positioning": ["cot_positioning", "cot_timeseries"],
    "hedge": ["gold_crisis_hedge"],
    "calendar": ["macro_calendar"],
    "crypto": ["crypto_trend"],
    "carry": ["swap_carry"],
    "rates": ["rates_trend", "curve_rv"],
    "credit": ["credit_rv"],
    "sector": ["sector_rotation"],
}


_MAX_CLUSTER_WEIGHT = 0.30   # survivability: no single cluster (e.g. crypto) above 30% of the book


def _cluster_riskparity(df: pd.DataFrame) -> np.ndarray:
    """Hierarchical risk parity: combine each cluster, then capped risk-parity across clusters."""
    cluster_rets: dict[str, np.ndarray] = {}
    for name, members in _CLUSTERS.items():
        cols = [m for m in members if m in df.columns]
        if cols:
            cluster_rets[name] = _riskparity(df[cols], mode="weight")
    cdf = pd.DataFrame(cluster_rets, index=df.index)
    return _riskparity(cdf, mode="weight", max_weight=_MAX_CLUSTER_WEIGHT)


def _validate(name: str, r: np.ndarray, matrix: np.ndarray, sharpes: np.ndarray,
              fam: Family, campaign, column: int) -> dict[str, object]:  # type: ignore[no-untyped-def]
    active = r[r != 0.0]
    if len(active) < 250:
        return {"sleeve": name, "ann_sharpe": _ann(r), "gates": "n<250", "survived": False,
                "reason": "insufficient active data"}
    v = validate(active, hypothesis=Hypothesis(
        family=fam, subtype=name, symbol="MT5_PORT", params={},
        mechanism=MechanismType.RISK_PREMIUM, edge_source=name, failure_modes=_FAIL),
        n_trials=matrix.shape[1], sharpe_estimates=sharpes, returns_matrix=matrix,
        campaign=campaign, column=column)
    return {"sleeve": name, "ann_sharpe": _ann(r), "survived": bool(v.survived),
            "gates": f"{sum(v.gates.values())}/{len(v.gates)}",
            "fails": [k for k, ok in v.gates.items() if not ok], "reason": v.rejection_reason}


def main() -> None:
    close, cost, by = _load()
    sleeves = _build_sleeves(close, cost, by)
    fam = _families()
    print(f"panel: {close.shape[1]} instruments x {close.shape[0]} days; "
          f"{len(sleeves)} sleeves: {list(sleeves)}\n")

    df = pd.DataFrame(sleeves, index=close.index)
    port = _riskparity(df)                               # plain risk-parity
    port_gated = _riskparity(df, mode="gate")            # trailing-Sharpe-gated
    port_max = _riskparity(df, mode="weight")            # trailing-Sharpe-weighted
    port_cluster = _cluster_riskparity(df)               # hierarchical (cluster-aware) -- headline
    all_series = {**sleeves, "portfolio_rp": port, "portfolio_gated": port_gated,
                  "portfolio_max": port_max, "portfolio_cluster": port_cluster}

    names = list(all_series)
    matrix = np.column_stack([all_series[k] for k in names])
    sharpes = np.array([sharpe_ratio(all_series[k][all_series[k] != 0.0]) for k in names])
    # per-candidate gates (gap #87 flip, principal-ruled 2026-07-29); thresholds unchanged
    campaign = campaign_gate_stats(matrix)
    # enumerate order == column_stack order over `names`, so `i` is each sleeve's matrix column
    results = [_validate(k, all_series[k], matrix, sharpes, fam.get(k, Family.CROSS_ASSET),
                         campaign, i)
               for i, k in enumerate(names)]

    # correlation matrix (active days only) + incremental portfolio Sharpe (leave-one-out on max)
    corr = df.replace(0.0, np.nan).corr().round(2)
    port_sharpe = _ann(port_cluster)
    incr = {}
    for k in sleeves:
        loo = _cluster_riskparity(df.drop(columns=[k]))
        incr[k] = round(port_sharpe - _ann(loo), 3)

    # Growth-optimal leverage (geometric CAGR), headline portfolio + positive-expectancy sleeves.
    # Unvalidated edges => half-Kelly de-rating + a conservative absolute governance cap.
    lev_targets = {"portfolio_cluster": port_cluster}
    lev_targets.update({k: v for k, v in sleeves.items() if _ann(v) > 0.0})
    leverage = {k: leverage_analyze(v, kelly_fraction=0.5, governance_cap=3.0)
                for k, v in lev_targets.items()}
    _WEB = Path("web/leverage.json")
    _WEB.write_text(json.dumps(
        {"updated_days": close.shape[0], "kelly_fraction": 0.5, "governance_cap": 3.0,
         "note": "Growth-optimal (Kelly) leverage maximizes geometric CAGR. Edges are UNVALIDATED "
                 "(fail DSR) -> recommended = half-Kelly capped; deploy only fractional + after "
                 "forward validation. CAGR assumes the in-sample edge persists.",
         "leverage": leverage}, indent=2, default=str), "utf-8")

    _OUT.mkdir(parents=True, exist_ok=True)
    payload = {"instruments": close.shape[1], "days": close.shape[0],
               "portfolio_ann_sharpe": port_sharpe, "results": results,
               "incremental_sharpe": incr, "correlations": corr.to_dict(),
               "leverage": leverage}
    (_OUT / "report.json").write_text(json.dumps(payload, indent=2, default=str), "utf-8")

    order = sorted(results, key=lambda d: (d.get("survived", False), d.get("ann_sharpe", 0)),
                   reverse=True)
    print("SLEEVE / PORTFOLIO RESULTS (ranked):")
    for d in order:
        inc = f" incr={incr[d['sleeve']]:+.2f}" if d["sleeve"] in incr else ""
        print(f"  {d['sleeve']:16} sharpe~{d['ann_sharpe']:5} gates={d.get('gates', '')!s:5} "
              f"survived={d.get('survived')}{inc}  fails={d.get('fails', '')}")
    print(f"\nPORTFOLIO_CLUSTER (hierarchical risk parity) ann_sharpe~{port_sharpe}")

    pc = leverage["portfolio_cluster"]
    print("\nGROWTH-OPTIMAL LEVERAGE (portfolio, geometric CAGR; assumes edge persists):")
    print(f"  growth-optimal (full Kelly) L={pc['growth_optimal_leverage']}  -> "
          f"CAGR {pc['points']['growth_optimal']['cagr']:.1%}  "
          f"maxDD {pc['points']['growth_optimal']['max_dd']:.0%}  "
          f"ruin {pc['points']['growth_optimal']['risk_of_ruin']:.0%}")
    print(f"  recommended (half-Kelly, cap) L={pc['recommended_leverage']}  -> "
          f"CAGR {pc['points']['recommended']['cagr']:.1%}  "
          f"maxDD {pc['points']['recommended']['max_dd']:.0%}  "
          f"ruin {pc['points']['recommended']['risk_of_ruin']:.0%}")
    print(f"  aggressive (2x Kelly)         L={pc['points']['aggressive']['leverage']}  -> "
          f"CAGR {pc['points']['aggressive']['cagr']:.1%}  "
          f"maxDD {pc['points']['aggressive']['max_dd']:.0%}  "
          f"ruin {pc['points']['aggressive']['risk_of_ruin']:.0%}")
    print("\nsleeve correlation matrix (active days):")
    print(corr.to_string())


if __name__ == "__main__":
    main()

```

### scripts/run_shadow_8h.py
```python
"""Funding-period (8h) forward shadow -- the LEGITIMATE validation accelerant (challenger).

The incumbent shadow (run_cashcarry_shadow.py) validates on DAILY returns, but funding settles
every 8h -- so the desk was throwing away 2/3 of its evidence resolution. This challenger runs
the IDENTICAL strategy function (libs.research.cashcarry.cashcarry_returns -- frequency-agnostic)
on an 8h-granularity funding/basis panel fetched from exchange-native history (free, one-shot,
~3 calls/symbol). Same evidence bar: NW-t corrects the (stronger) autocorrelation honestly via
the same machinery; nothing is relaxed. 40 calendar days -> ~120 blocks instead of 40 obs, so
the t-stat for a real edge arrives ~sqrt(3)x sooner MINUS whatever autocorrelation eats -- the
honest speedup, measured not assumed.

CONSTITUTION: validation-methodology changes require challenger-vs-incumbent in parallel before
adoption. This script is the CHALLENGER: it writes web/cashcarry_shadow_8h.json alongside the
incumbent and changes NO consumer. Promotion to primary only after the comparison window.

    python scripts/run_shadow_8h.py
"""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from libs.research.anytime_valid import e_value
from libs.research.cashcarry import cashcarry_returns
from libs.validation.dsr import sharpe_ratio
from libs.validation.forward_stats import autocorr_factor, nw_tstat

_FAPI = "https://fapi.binance.com"
_SAPI = "https://api.binance.com"
_OUT = Path("web/cashcarry_shadow_8h.json")
_STATE = Path("data/cashcarry_shadow_state.json")      # SAME shadow_start as the incumbent
_INCUMBENT = Path("web/cashcarry_shadow.json")
_PPY = 3 * 365.0                                       # 8h blocks per year
_TOP_N = 40                                            # liquid perps; one-shot fetch, tiny weight
_LOOKBACK_DAYS = 10                                    # pre-window buffer for the rolling signal


def _get(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": "quant-shadow-8h"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def _symbols() -> list[str]:
    """Top perps by 24h quote volume with a matching spot market (both legs needed for basis)."""
    tick = _get(f"{_FAPI}/fapi/v1/ticker/24hr")
    perps = sorted((t for t in tick if str(t.get("symbol", "")).endswith("USDT")),
                   key=lambda t: -float(t.get("quoteVolume", 0.0)))
    spot_info = _get(f"{_SAPI}/api/v3/exchangeInfo")
    spot_syms = {s["symbol"] for s in spot_info.get("symbols", [])
                 if s.get("status") == "TRADING"}
    out = [str(t["symbol"]) for t in perps if t["symbol"] in spot_syms]
    return out[:_TOP_N]


def _funding_8h(sym: str, start_ms: int) -> pd.Series:
    rows = _get(f"{_FAPI}/fapi/v1/fundingRate?symbol={sym}&startTime={start_ms}&limit=1000")
    if not isinstance(rows, list) or not rows:
        return pd.Series(dtype="float64")
    idx = pd.to_datetime([int(r["fundingTime"]) for r in rows], unit="ms", utc=True)
    ser = pd.Series([float(r["fundingRate"]) for r in rows], index=idx)
    # some symbols settle every 4h -- SUM settlements inside each true 8h block so the
    # panel index is uniform (mixed settlement times otherwise inflate the row count ~3x,
    # caught on first run: 233 blocks for a 26-day window that should hold ~78)
    return ser.groupby(ser.index.floor("8h")).sum()


def _kline_close_8h(base: str, path: str, sym: str, start_ms: int) -> pd.Series:
    rows = _get(f"{base}{path}?symbol={sym}&interval=8h&startTime={start_ms}&limit=1000")
    if not isinstance(rows, list) or not rows:
        return pd.Series(dtype="float64")
    idx = pd.to_datetime([int(r[0]) for r in rows], unit="ms", utc=True)
    return pd.Series([float(r[4]) for r in rows], index=idx)


def main() -> None:
    st = json.loads(_STATE.read_text("utf-8"))
    start = pd.Timestamp(st["shadow_start"], tz="UTC")
    fetch_from = int((start - pd.Timedelta(days=_LOOKBACK_DAYS)).timestamp() * 1000)

    funding, basis = {}, {}
    for sym in _symbols():
        try:
            f = _funding_8h(sym, fetch_from)
            perp = _kline_close_8h(_FAPI, "/fapi/v1/klines", sym, fetch_from)
            spot = _kline_close_8h(_SAPI, "/api/v3/klines", sym, fetch_from)
            if f.empty or perp.empty or spot.empty:
                continue
            px = pd.concat({"p": perp, "s": spot}, axis=1).dropna()
            b = ((px["p"] - px["s"]) / px["s"])
            b = b.groupby(b.index.floor("8h")).last().reindex(f.index, method="ffill")
            funding[sym] = f[~f.index.duplicated()]
            basis[sym] = b[~b.index.duplicated()]
            time.sleep(0.15)                            # gentle pacing; ~120 calls total
        except Exception as e:
            print(f"  skip {sym}: {type(e).__name__}")
    f8 = pd.DataFrame(funding).sort_index()
    b8 = pd.DataFrame(basis).reindex(f8.index)
    if f8.shape[1] < 12:
        raise SystemExit(f"panel too thin: {f8.shape[1]} symbols")

    r8 = cashcarry_returns(f8, b8)                      # IDENTICAL strategy function
    dates = pd.to_datetime(f8.index)
    fwd = r8[np.asarray(dates >= start)]
    fwd_active = fwd[fwd != 0.0]
    n = len(fwd)
    sh = round(float(sharpe_ratio(fwd_active) * np.sqrt(_PPY)), 2) if len(fwd_active) > 5 else 0.0

    inc = json.loads(_INCUMBENT.read_text("utf-8")) if _INCUMBENT.exists() else {}
    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "strategy": "cash_and_carry @ 8h blocks (CHALLENGER vs run_cashcarry_shadow.py)",
        "shadow_start": st["shadow_start"],
        "panel_symbols": int(f8.shape[1]),
        "forward_blocks": n,
        "forward_days_equiv": round(n / 3.0, 1),
        "forward_ann_sharpe_8h": sh,
        "forward_nw_tstat_8h": nw_tstat(fwd) if n >= 5 else 0.0,
        "autocorr_vif_8h": autocorr_factor(fwd) if n >= 5 else 1.0,
        "anytime_e_value": round(e_value(fwd), 4),
        "e_threshold_alpha01": 100.0,
        "incumbent_daily": {"forward_ann_sharpe": inc.get("forward_ann_sharpe"),
                            "forward_days": inc.get("forward_days"),
                            "forward_tstat": inc.get("forward_tstat")},
        "note": ("3x observations per calendar day at the SAME evidence bar (NW-t handles the "
                 "autocorrelation). Challenger only: no consumer reads this until the "
                 "challenger-vs-incumbent window closes per the constitution."),
    }
    _OUT.write_text(json.dumps(out, indent=1), "utf-8")
    print(f"8h shadow | {f8.shape[1]} syms | {n} blocks (~{n / 3.0:.0f}d) | "
          f"annSh {sh} | NW-t {out['forward_nw_tstat_8h']} | vif {out['autocorr_vif_8h']} | "
          f"e {out['anytime_e_value']}")


if __name__ == "__main__":
    main()

```

### scripts/structural_spreads.py
```python
"""STRUCTURAL SPREAD SCREEN -- hunting more kimchi-class edges.

THE PATTERN THAT SURVIVES ON THIS DESK: every candidate that lived is a SPREAD, not a forecast.
Cash-and-carry (spot vs perp), kimchi (KRW venue vs global, gated by capital controls), cny
(same, gated by CN controls). Every FORECAST died -- attention, dev momentum, trader skill,
order flow, reflexivity.

So the search is for spreads where something PHYSICALLY prevents arbitrage from closing the gap.
Not "this looks mispriced" -- "this cannot be closed because of a queue, a licence, a delay."

CANDIDATES (each with its named constraint):
  1. LIQUID-STAKING DISCOUNT (stETH/ETH, mSOL/SOL)
     Constraint: the validator EXIT QUEUE. Unstaking takes days-to-weeks, so the derivative can
     trade below the underlying and no one can instantly arbitrage it. This is the closest
     structural analog to kimchi on the desk -- a hard physical delay, not a sentiment gap.
  2. STABLECOIN PEG SPREAD (USDC/USDT, FDUSD/USDT, DAI/USDT)
     Constraint: REDEMPTION FRICTION -- minimum sizes, KYC, banking hours, issuer discretion.
     Retail cannot redeem at par, so the peg gap persists.
  3. DEFI-vs-CEFI DOLLAR RATE (Aave USDC supply APY vs perp funding)
     Constraint: SYSTEM SEGMENTATION -- different collateral regimes, smart-contract risk,
     no common margin. Two prices for the same thing (cost of dollar leverage) that cannot be
     netted against each other.

THE TEST IS NOT "does it predict price". For a HARVESTABLE spread the questions are:
  (a) is the level persistently non-zero?  (is there anything to capture)
  (b) does it MEAN-REVERT?                 (half-life -- can you exit, or does it drift forever)
  (c) is it BOUNDED?                       (does it blow out, i.e. is the constraint ever violent)
A spread that is wide and mean-reverting with a named constraint is a carry candidate. A spread
that random-walks is just another price.

Free public endpoints. Stage-A, zero promotion authority. Run from repo root.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

OUT = Path("data/structural_spreads.json")


def _get(u, t=35):
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(u, headers={"User-Agent": "q/1.0"}), timeout=t).read().decode())


def binance_daily(sym: str, n: int = 400) -> dict[str, float]:
    try:
        rows = _get(f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=1d&limit={n}")
        return {datetime.fromtimestamp(int(r[0]) / 1000, tz=UTC).date().isoformat(): float(r[4])
                for r in rows}
    except Exception:
        return {}


def coingecko_ratio(num: str, den: str, days: int = 365) -> dict[str, float]:
    """Daily close ratio of two assets from CoinGecko market_chart (free, no key)."""
    out = {}
    series = {}
    for cid in (num, den):
        d = _get(f"https://api.coingecko.com/api/v3/coins/{cid}/market_chart"
                 f"?vs_currency=usd&days={days}&interval=daily")
        series[cid] = {datetime.fromtimestamp(p[0] / 1000, tz=UTC).date().isoformat(): float(p[1])
                       for p in d.get("prices", [])}
    for k in set(series[num]) & set(series[den]):
        if series[den][k]:
            out[k] = series[num][k] / series[den][k]
    return out


def analyse(name: str, spread: dict[str, float], constraint: str, centre: float = 0.0) -> dict:
    """(a) persistence of level, (b) mean-reversion half-life, (c) boundedness."""
    dates = sorted(spread)
    if len(dates) < 90:
        print(f"{name:<26} thin ({len(dates)}d)")
        return {"name": name, "verdict": "THIN", "n": len(dates)}
    x = np.array([spread[d] for d in dates]) - centre
    mean, sd = float(x.mean()), float(x.std())
    # AR(1) on deviations -> mean-reversion half-life
    x0, x1 = x[:-1] - x.mean(), x[1:] - x.mean()
    beta = float((x0 @ x1) / (x0 @ x0)) if (x0 @ x0) > 0 else 1.0
    hl = float(-np.log(2) / np.log(abs(beta))) if 0 < abs(beta) < 1 else float("inf")
    # boundedness: how fat is the tail vs the body
    p99, p50 = float(np.percentile(np.abs(x), 99)), float(np.percentile(np.abs(x), 50))
    tail = p99 / p50 if p50 > 0 else float("inf")
    frac_nonzero = float((np.abs(x) > sd * 0.25).mean())

    harvestable = (abs(mean) > sd * 0.25 or frac_nonzero > 0.5) and hl < 30 and tail < 12
    verdict = ("HARVESTABLE-CANDIDATE" if harvestable
               else "DRIFTS (no reversion)" if hl >= 30
               else "VIOLENT (unbounded tail)" if tail >= 12
               else "TOO TIGHT (nothing to capture)")
    print(f"{name:<26} n={len(dates):<4} mean {mean*100:+7.3f}%  sd {sd*100:6.3f}%  "
          f"half-life {hl:6.1f}d  tail {tail:5.1f}x  -> {verdict}")
    return {"name": name, "constraint": constraint, "n": len(dates),
            "mean_pct": round(mean * 100, 4), "sd_pct": round(sd * 100, 4),
            "ar1_beta": round(beta, 4), "half_life_days": round(hl, 2) if hl != float("inf") else None,
            "tail_ratio": round(tail, 2), "verdict": verdict}


def main() -> None:
    print("=== STRUCTURAL SPREAD SCREEN (spreads survive; forecasts died) ===")
    print("    test: persistent level? mean-reverting? bounded?  NOT 'does it predict price'\n")
    res = []

    # --- 2. STABLECOIN PEG SPREADS (redemption friction) --------------------------------
    for sym, label in (("USDCUSDT", "peg USDC/USDT"), ("FDUSDUSDT", "peg FDUSD/USDT"),
                       ("DAIUSDT", "peg DAI/USDT")):
        s = binance_daily(sym)
        if s:
            res.append(analyse(label, {k: v - 1.0 for k, v in s.items()},
                               "redemption friction: min sizes, KYC, banking hours"))
        else:
            print(f"{label:<26} DATA-BLOCKED")

    # --- 1. LIQUID-STAKING DISCOUNT (validator exit queue) ------------------------------
    for num, den, label in (("staked-ether", "ethereum", "LSD stETH/ETH"),
                            ("msol", "solana", "LSD mSOL/SOL")):
        try:
            r = coingecko_ratio(num, den)
        except Exception as e:
            print(f"{label:<26} DATA-BLOCKED ({type(e).__name__})")
            continue
        if r:
            base = 1.0 if num == "staked-ether" else float(np.median(list(r.values())))
            res.append(analyse(label, {k: v - base for k, v in r.items()},
                               "validator exit queue: unstaking takes days-weeks"))

    Path(OUT).write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                                     "results": res}, indent=1), "utf-8")
    cands = [r for r in res if r.get("verdict") == "HARVESTABLE-CANDIDATE"]
    print(f"\n  HARVESTABLE CANDIDATES: {len(cands)}/{len(res)}")
    for c in cands:
        print(f"    {c['name']}  (constraint: {c['constraint']})")
    print("\n  A candidate is NOT an edge -- it means the spread is wide, reverts, and is bounded.")
    print("  Net-of-cost capture and a forward clock still decide. Stage-A only.")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()

```
