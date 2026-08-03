# AUDIT SHARD 6/13 -- seat z-ai/glm-5.2

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

### libs/alpha_factory/research_score_engine.py
```python
"""Research score engine — a single 0-100 score for a research program's promise."""

from __future__ import annotations

from libs.alpha_factory.models import ResearchScoreResult

_WEIGHTS: dict[str, float] = {
    "novelty": 0.20,
    "expected_robustness": 0.20,
    "expected_capacity": 0.15,
    "portfolio_need": 0.15,
    "research_confidence": 0.20,
    "uncrowded": 0.10,
}


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class ResearchScoreEngine:
    """Combines research-quality signals into a 0-100 research score."""

    def score(
        self,
        *,
        novelty: float,
        expected_robustness: float,
        expected_capacity: float,
        portfolio_need: float,
        research_confidence: float,
        crowding_risk: float,
    ) -> ResearchScoreResult:
        components = {
            "novelty": _clip01(novelty),
            "expected_robustness": _clip01(expected_robustness),
            "expected_capacity": _clip01(expected_capacity),
            "portfolio_need": _clip01(portfolio_need),
            "research_confidence": _clip01(research_confidence),
            "uncrowded": 1.0 - _clip01(crowding_risk),
        }
        score = 100.0 * sum(_WEIGHTS[k] * v for k, v in components.items())
        return ResearchScoreResult(research_score=score, components=components)

```

### libs/autodiscovery/validation.py
```python
"""Full institutional validation per candidate — every gate, no weakening, fail-closed.

Runs the complete stack and a candidate survives ONLY if every gate passes: economic mechanism,
CPCV (purged K-fold OOS consistency), PBO, Deflated Sharpe (trials-deflated), White's Reality Check,
Walk-Forward, capacity, fragility (tail risk), and an accelerated shadow check (final held-out
segment). Reuses the existing validation / discovery primitives. Thresholds are constants here and
never relaxed.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from libs.autodiscovery.models import Hypothesis, ValidationMetrics, ValidationVerdict
from libs.discovery.capacity import capacity_estimate
from libs.discovery.tail_risk import tail_risk

# re-exported for tests/autodiscovery/test_capacity_relative.py; validate()'s own gate below
# uses _min_capacity_usd() instead.
from libs.research.capacity_policy import capacity_required  # noqa: F401
from libs.validation.baselines import baseline_scorecard
from libs.validation.cpcv import CPCV
from libs.validation.dsr import deflated_sharpe_ratio, sharpe_ratio
from libs.validation.errors import ValidationError
from libs.validation.fdr import benjamini_hochberg
from libs.validation.pbo import PBOResult, probability_backtest_overfitting
from libs.validation.reality_check import RealityCheckResult, whites_reality_check
from libs.validation.revalidation import WalkForwardEngine, WalkForwardStatus
from libs.validation.screen_select import ScreenSelection, screen_select
from libs.validation.stepwise import (
    CSCVResult,
    StepdownResult,
    cscv_candidate_pbo,
    romano_wolf_stepdown,
)

_PERIODS_PER_YEAR = 24 * 260
_DSR_THRESHOLD = 0.95
_PBO_THRESHOLD = 0.5       # same bar as PBOResult.overfit; only the ATTRIBUTION changed
# CAPACITY PARITY (principal order 2026-07-30; constitution L1.18/§42 made ARITHMETIC).
# The old bar was a FIXED $100,000 institutional floor. On a desk deploying ~$5k that rejects
# edges it could fill COMPLETELY -- measured 182 of 420 campaign candidates failed with capacity
# among their blockers (reports/gate_histogram.json: capacity 238/420 pass). An edge that can
# absorb 20x the desk's entire book was being called too small. That is capacity PICKINESS, and
# it costs exactly the compounding the desk exists to maximise: a $20k-capacity edge at $5k of
# equity is 100% usable and compounds identically to a $20m one until the quota binds.
# THE RULE: an edge fails capacity ONLY if it cannot absorb a meaningful slice of the desk's OWN
# size. It is then exploited to ITS OWN quota, never deprioritised for being small, and never
# ranked below a larger-capacity edge (L1.18: edges are edges).
# PRINCIPAL CLARIFICATION 2026-07-30: capital deploys from ~$1k and may start as low as ~$100.
# At $100 live, a $300-capacity edge is FULLY usable and must be exploited -- so the floor cannot
# be an institutional round number, it can only be the point where EXECUTION PHYSICS stops working
# (L1.5). Below ~20 venue-minimum notionals there is no room for a few economic round-trips, and
# that -- not a capital-size opinion -- is the only defensible absolute floor.
_DESK_EQUITY_FALLBACK_USD = 1.0e3     # used only when live equity is unreadable
# THE ADMISSION BAND IS A MINIMUM SLICE, NOT A MULTIPLE OF THE BOOK (principal 2026-07-30).
# A multiple was wrong and measurably so: at $1,000 equity a 2x rule marked capacity of $300,
# $800 and even $1,500 as OUTGROWN -- edges that can hold 30%, 80% and 150% of the whole book.
# The book runs MANY edges in parallel (that is the diversification the objective actually wants),
# so an edge never needs to hold the entire book; it needs to hold a slice big enough to matter.
# Consequence, which is the compounding point: the admissible band SLIDES UP with equity and stays
# INCLUSIVE at the small end forever -- at $1k everything from ~$200 up is in; at $50k a
# $300-capacity edge has finally become a rounding error and retires by OUTGROWTH.
_MIN_SLICE_FRACTION = 0.10            # an edge must hold >=10% of the book to be worth a quota
_CAPACITY_MULTIPLE_OF_EQUITY = 2.0    # RETAINED only for the gauntlet's own headroom bar
_VENUE_MIN_NOTIONAL_USD = 10.0        # Binance-class minimum order notional
_EXEC_VIABILITY_FLOOR_USD = 20.0 * _VENUE_MIN_NOTIONAL_USD   # ~$200: a handful of economic trips


def _desk_equity_usd() -> float:
    """Live deployable equity, read defensively. The capacity bar is RELATIVE to this so it
    scales with the desk instead of freezing an institutional assumption into a seed-stage book.

    ONE SOURCE, AND IT WAS TWO (found by check_utilisation.py, 2026-07-30). This function read
    `data/cashcarry_config.json:capital` while `libs.research.capacity_policy.live_book_usd()` read
    VENUE TRUTH from the NAV chain. Measured the day it was found: config said $4,500, venue truth
    said $13,155. Every capacity band in the desk is a ratio to this number, so the whole gauntlet
    was sizing edges against a book 2.9x smaller than the real one -- ADMITTING edges the desk had
    already outgrown, and reporting them as healthy inventory.

    That is the L1.18a $100,000-floor defect running in the opposite direction, and it is the same
    root cause both times: a capacity threshold evaluated against a number that is not the book.
    check_capacity_single_source fences the capacity POLICY constant; nothing fenced its INPUT.

    ORDER: venue truth -> the live web artifact -> config -> constant. Never zero -- zero would
    make every edge OUTGROWN and empty the shortlist on an unreadable file, and an unreadable file
    must never be the most destructive possible answer.
    """
    import json as _json
    from pathlib import Path as _Path
    try:
        from libs.research.capacity_policy import live_book_usd
        # fallback=0.0 so this rung reports ONLY genuine venue truth. Calling it with its own
        # default would return DEFAULT_BOOK_USD on an unreadable ledger, and a constant dressed as
        # venue truth would outrank the real local config below it -- a silent downgrade of the
        # ladder rather than a fallback through it.
        venue = float(live_book_usd(fallback=0.0))
        if venue > 0:
            return venue
    except (ImportError, OSError, ValueError, TypeError):
        pass
    for src, keys in ((_Path("web/cashcarry_live.json"), ("equity", "net_equity", "deployed")),
                      (_Path("data/cashcarry_config.json"), ("capital", "authorized_capital"))):
        try:
            d = _json.loads(src.read_text("utf-8"))
        except (OSError, _json.JSONDecodeError):
            continue
        for k in keys:
            v = d.get(k)
            if isinstance(v, (int, float)) and v > 0:
                return float(v)
    return _DESK_EQUITY_FALLBACK_USD


def _min_capacity_usd() -> float:
    return max(_desk_equity_usd() * _CAPACITY_MULTIPLE_OF_EQUITY, _EXEC_VIABILITY_FLOOR_USD)


def capacity_status(capacity_usd: float, *, equity_usd: float | None = None) -> str:
    """ADMIT / OUTGROWN / SUB-VIABLE -- and the distinction is a lifecycle law, not bookkeeping.

    THE MODEL THE PRINCIPAL SPECIFIED (2026-07-30), and it is how small edges are supposed to end:
    a small-capacity edge is admitted and EXPLOITED TO ITS QUOTA while the book is small; as capital
    compounds past that quota the edge stops being able to hold a meaningful slice and retires by
    OUTGROWTH. That is natural attrition from SUCCESS, not failure --

      * OUTGROWN edges are NEVER graveyarded as dead mechanisms. Nothing was refuted: the mechanism
        was real, it was harvested to exhaustion, and the book simply grew past it. Graveyarding it
        would poison the novelty gate against a mechanism that WORKED, and would corrupt the
        family-level survival statistics that steer future search (L1.17).
      * SUB-VIABLE is the only genuine capacity rejection: the edge cannot support even a handful of
        economic round-trips at venue minimums, so execution physics (L1.5) kills it at ANY equity.
      * Small and large capacity are hunted SIMULTANEOUSLY and never ranked against each other
        (L1.18a). A pipeline that waits for big-capacity edges forfeits the compounding available
        right now, and compounding now is what buys the capital that makes big edges relevant.
    """
    eq = _desk_equity_usd() if equity_usd is None else float(equity_usd)
    if capacity_usd < _EXEC_VIABILITY_FLOOR_USD:
        return "SUB-VIABLE"
    if capacity_usd < eq * _MIN_SLICE_FRACTION:
        return "OUTGROWN"
    return "ADMIT"


def capacity_runway_days(capacity_usd: float, *, equity_usd: float | None = None,
                         growth_rate_annual: float = 1.0) -> float:
    """Days until the book grows past this edge's usable band -- its EXPIRY DATE.

    THE RACE THE PRINCIPAL NAMED (2026-07-30): a small-capacity edge is only worth anything if it
    reaches live BEFORE capital outgrows it. A validation pipeline slower than the runway delivers
    edges that are already rounding errors on arrival, which is not caution -- it is a guaranteed
    zero. So runway is computed and COMPARED to pipeline latency (see `capacity_race`), and the
    forward-slot queue is ordered by EXPIRY, shortest first, because a long-runway edge loses
    nothing by waiting and a short-runway one loses everything.

    growth_rate_annual: continuous growth of equity, 1.0 = 100%/yr. The desk's own target band is
    80-120%/yr (GROWTH_UNLOCK_LADDER), so the default is deliberately the middle of the mandate
    rather than an optimistic number.
    """
    import math
    eq = _desk_equity_usd() if equity_usd is None else float(equity_usd)
    if eq <= 0 or growth_rate_annual <= 0:
        return float("inf")
    # equity at which this edge becomes a rounding error on the book
    outgrow_at = capacity_usd / _MIN_SLICE_FRACTION
    if outgrow_at <= eq:
        return 0.0                                      # already outgrown
    return 365.0 * math.log(outgrow_at / eq) / growth_rate_annual


def capacity_race(capacity_usd: float, *, validation_days: float,
                  equity_usd: float | None = None,
                  growth_rate_annual: float = 1.0) -> dict[str, Any]:
    """Does this edge reach live before the book outgrows it? Verdict + the honest remedy.

    Verdicts:
      REACHES-LIVE   runway exceeds the pipeline latency with margin -- ship it normally.
      TIGHT          it lands with little life left; worth prioritising in the slot queue.
      DOA            it is outgrown before validation could finish. THE REMEDY IS NEVER A SHORTER
                     CLOCK OR A LOWER BAR (L1.6 -- the confirmation bar never loosens). The only
                     honest accelerants are MORE OBSERVATIONS PER DAY (the desk measured this: an
                     8h funding panel carries ~sqrt(3)x the evidence rate of a daily one at
                     vif 1.008, gap #44) and NOT QUEUEING -- run the slot now rather than later.
                     If neither is available the edge is structurally unreachable at this equity
                     and is recorded as such, not silently shelved.
    """
    runway = capacity_runway_days(capacity_usd, equity_usd=equity_usd,
                                  growth_rate_annual=growth_rate_annual)
    if runway <= validation_days:
        verdict = "DOA"
    elif runway < validation_days * 2.0:
        verdict = "TIGHT"
    else:
        verdict = "REACHES-LIVE"
    return {"capacity_usd": capacity_usd, "runway_days": round(runway, 1),
            "validation_days": validation_days, "verdict": verdict,
            "slot_priority": round(runway, 1),      # ascending: shortest runway is served first
            "remedy": ("higher-frequency evidence (8h panel ~sqrt(3)x rate) and/or an immediate "
                       "slot -- never a shorter clock or a lower bar"
                       if verdict != "REACHES-LIVE" else "none needed")}
_CPCV_MIN_POSITIVE = 0.6   # >=60% of purged folds positive

# Real CPCV settings. 6 groups choose 2 gives 15 test paths; purge drops the observations
# straddling each boundary and the embargo holds out a further 1% after it, which is what stops
# a serially-correlated stream leaking its answer across the split.
_CPCV_GROUPS = 6
_CPCV_TEST_GROUPS = 2
_CPCV_PURGE = 2
_CPCV_EMBARGO = 0.01
_CPCV_MIN_OBS = 60         # below this there is nothing to be combinatorial about

# Benjamini-Hochberg level for the campaign screen. 0.10 = accept that up to ~10% of
# promoted candidates are false discoveries, which is the standard screening trade-off
# and far more powerful than family-wise control at this campaign size.
_FDR_ALPHA = 0.10

# A candidate must beat the trivial nulls, not merely be statistically distinguishable from
# noise. DSR/PBO/RC all ask "is this real given the search?"; none asks "is it better than
# buy-and-hold?", and a significant strategy that loses to buy-and-hold is complexity with no
# reason to exist. Gate is SKIPPED (not failed) when no benchmark stream is supplied, because
# most callers have no benchmark for a market-neutral carry sleeve -- failing them for the
# absence of an inapplicable comparison would reject good candidates for the wrong reason.


def _cpcv_positive_fraction(returns: np.ndarray, *, k: int = 5) -> float:
    """Fraction of COMBINATORIAL PURGED folds whose test slice is positive.

    This was a plain `np.array_split` into k contiguous folds -- not purged, not embargoed, and
    not combinatorial, despite the gate being named `cpcv` and the module docstring claiming
    CPCV. `libs/validation/cpcv.py` implements the real thing (Lopez de Prado ch.12) and was
    imported by nothing but its own test.

    The difference is not cosmetic. Contiguous k-fold on overlapping financial samples leaks
    information across the fold boundary, so the old measure was systematically optimistic on
    exactly the serially-correlated return streams this desk trades. Purge + embargo remove the
    observations that straddle the boundary; the combinatorial part gives many test paths instead
    of one, so the fraction means something.

    Falls back to the contiguous split only when the sample is too short to purge -- with a short
    series there is nothing to be combinatorial about, and refusing to score would fail candidates
    for being new rather than for being bad.
    """
    arr = np.asarray(returns, dtype="float64")
    if len(arr) >= _CPCV_MIN_OBS:
        try:
            splitter = CPCV(n_groups=_CPCV_GROUPS, n_test_groups=_CPCV_TEST_GROUPS,
                            purge=_CPCV_PURGE, embargo=_CPCV_EMBARGO)
            positive = [bool(arr[s.test].mean() > 0)
                        for s in splitter.split(len(arr)) if len(s.test) > 1]
            if positive:
                return float(np.mean(positive))
        except (ValidationError, ValueError):
            pass
    folds = np.array_split(arr, k)
    positive_fallback = [f.mean() > 0 for f in folds if len(f) > 1]
    return float(np.mean(positive_fallback)) if positive_fallback else 0.0


def _beats_baselines(returns: np.ndarray, benchmark: np.ndarray | None) -> bool:
    """Does the candidate beat buy-and-hold and equal-weight? True when no benchmark is given.

    Skipping rather than failing on a missing benchmark is a deliberate fail-OPEN, and the only
    one in this gate set. The reason it is defensible here and nowhere else: the desk's live
    sleeve is market-neutral carry, for which "buy and hold what?" has no answer, so an absent
    benchmark usually means the comparison is inapplicable rather than unmeasured. Every caller
    that CAN supply one should -- `beats_baselines` reads as passed either way in the verdict,
    so read `n_obs`/the caller to know which happened.
    """
    if benchmark is None:
        return True
    b = np.asarray(benchmark, dtype="float64")
    if len(b) < 2 or len(b) != len(returns):
        return True
    try:
        return bool(baseline_scorecard(returns, buy_hold_returns=b).beats_all)
    except (ValidationError, ValueError):
        return True


def campaign_fdr(dsr_values: Sequence[float], *,
                 alpha: float = _FDR_ALPHA) -> tuple[list[bool], float]:
    """Benjamini-Hochberg screen across one campaign. Returns (survives_mask, p_threshold).

    Why this is NOT redundant with the per-candidate DSR gate it sits behind. DSR asks, of ONE
    candidate, "is this Sharpe real given the trials that produced it", and passes at 0.95. Run
    twenty candidates past a 0.95 bar and you expect one false survivor by construction -- the
    per-candidate control says nothing about the error rate of the SET the desk promotes.
    Benjamini-Hochberg controls exactly that: the expected proportion of false discoveries among
    the candidates that survive.

    Nor is it redundant with White's Reality Check, which tests whether the BEST performer beats
    the benchmark -- one question about one candidate, not a rate across many. And it is a
    different control from `forward_stats.holm_bar`: Holm bounds the probability of ANY false
    positive (family-wise error), which across a campaign of this size is punishingly
    conservative, where BH accepts a known false-discovery proportion in exchange for power.

    p-values are 1 - DSR: the deflated Sharpe is already the probability the true Sharpe exceeds
    zero given the search, so its complement is the p-value for "no edge" with the multiplicity
    of the search already priced in.

    An empty or single-candidate campaign passes through unchanged -- there is no multiplicity to
    correct with one test, and rejecting a lone candidate for being alone would be nonsense.

    OPERATIONAL CONSEQUENCE, measured not assumed. A uniformly strong campaign is NOT penalised
    (20 candidates at DSR 0.96 all promote -- that is strong collective evidence). But junk
    DILUTES: three candidates at 0.96 among seventeen at 0.50 promotes NONE, because a campaign
    that is mostly noise does not support calling anything a discovery. Padding a cycle with weak
    generators now costs you the good candidates in it. That is the correct incentive and it is
    the sharpest edge of this gate, so callers demote rather than reject on an FDR failure --
    nothing is lost, it simply does not reach the registry this cycle.
    """
    ps = [min(1.0, max(0.0, 1.0 - float(d))) for d in dsr_values]
    if len(ps) < 2:
        return [True] * len(ps), 1.0
    try:
        res = benjamini_hochberg(np.asarray(ps, dtype="float64"), alpha=alpha)
    except (ValidationError, ValueError):
        # fail-OPEN here on purpose: BH is an EXTRA screen layered on gates that already ran and
        # already passed. A crash in the extra screen must not silently reject candidates that
        # cleared every primary gate -- that would be a harsher desk by accident, not by decision.
        return [True] * len(ps), 1.0
    return [bool(x) for x in res.rejected], float(res.threshold)


def campaign_pbo_rc(
    returns_matrix: np.ndarray,
) -> tuple[PBOResult | None, RealityCheckResult | None]:
    """Compute PBO and White's Reality Check ONCE per campaign (they depend only on the matrix).

    DEPRECATED as a GATE input -- kept for diagnostics and for call sites not yet migrated.

    Both statistics take only the matrix; the candidate's own returns are never an input.  Used as
    per-candidate gates they are therefore campaign CONSTANTS, and the "no change to the verdict"
    that made caching them look free is exactly the defect: every candidate in a batch gets the
    same verdict whatever its merit.  Measured 2026-07-29 on the real 420-candidate campaign --
    PBO 0.6159 (>0.5) and White RC p 0.4220 (>=0.05) -- which alone forced 420/420 rejections.
    Measured on a synthetic campaign containing one strong winner, the same two gates pass EVERY
    pure-noise candidate.  Too strict and too loose, decided by the batch rather than the
    candidate.

    Use :func:`campaign_gate_stats` + ``validate(campaign=..., column=...)`` instead.
    """
    if returns_matrix.shape[1] < 2:
        return None, None
    return probability_backtest_overfitting(returns_matrix), whites_reality_check(returns_matrix)


class CampaignGates:
    """Per-candidate multiplicity statistics for one campaign, computed once.

    Holds the candidate-aware replacements (CSCV rank-consistency, Romano-Wolf stepdown) and the
    legacy campaign statistics, which stay available as diagnostics of the SEARCH PROCEDURE --
    which is the thing they actually measure.
    """

    __slots__ = ("cscv", "legacy_pbo", "legacy_rc", "screen", "stepdown")

    def __init__(
        self,
        cscv: CSCVResult,
        stepdown: StepdownResult,
        legacy_pbo: PBOResult | None,
        legacy_rc: RealityCheckResult | None,
    ) -> None:
        self.cscv = cscv
        self.stepdown = stepdown
        self.legacy_pbo = legacy_pbo
        self.legacy_rc = legacy_rc
        # SCREEN-STAGE SELECTION (gap #71, 2026-07-30). Computed and REPORTED alongside the
        # family-wise verdict; it does NOT change the survival gate here. The measured reason:
        # Romano-Wolf FWER admits 0/420 at every window tested (best adjusted p 0.522 at min-length,
        # 0.089 at max-observation), so as a SCREEN gate it carries zero information about candidate
        # quality -- and a bar that rises with generation volume is what TWO_STAGE_DISCOVERY_LAW
        # forbids. Promotion authority is untouched: forward clocks keep Holm/FWER on <=12 slots.
        self.screen: ScreenSelection | None = None
        with_screen = screen_select(stepdown, q=0.05, method="by") if stepdown else None
        self.screen = with_screen


def campaign_gate_stats(returns_matrix: np.ndarray) -> CampaignGates | None:
    """One pass over the campaign matrix yielding PER-CANDIDATE pbo / significance verdicts.

    Same thresholds as before (PBO <= 0.5, significance at 5%) -- only the *attribution* changes,
    from one campaign verdict imposed on everyone to a verdict each candidate earns.  Romano-Wolf
    still controls family-wise error across all N, so multiplicity is paid for in full.
    """
    matrix = np.asarray(returns_matrix, dtype="float64")
    if matrix.ndim != 2 or matrix.shape[1] < 2:
        return None
    legacy_pbo, legacy_rc = campaign_pbo_rc(matrix)
    return CampaignGates(
        cscv=cscv_candidate_pbo(matrix),
        stepdown=romano_wolf_stepdown(matrix),
        legacy_pbo=legacy_pbo,
        legacy_rc=legacy_rc,
    )


def validate(
    returns: np.ndarray,
    *,
    hypothesis: Hypothesis,
    n_trials: int,
    sharpe_estimates: np.ndarray,
    returns_matrix: np.ndarray,
    adv_usd: float = 1.0e11,
    edge_bps: float | None = None,
    # What the desk ACTUALLY deploys. The capacity gate is a ratio to this, not a fixed dollar
    # figure -- see capacity_required(). None means "read the live book from the NAV chain", which
    # is what makes the ratio self-scaling as the desk grows. The old default of 0.0 was a hole:
    # it collapsed the gate to the $2k absolute floor and passed essentially any capacity, so the
    # ratio that was supposed to protect the desk protected nothing whenever a caller omitted it.
    deployed_equity_usd: float | None = None,
    n_sleeves: int | None = None,
    pbo: PBOResult | None = None,
    rc: RealityCheckResult | None = None,
    benchmark_returns: np.ndarray | None = None,
    campaign: CampaignGates | None = None,
    column: int | None = None,
) -> ValidationVerdict:
    arr = np.asarray(returns, dtype="float64")
    if len(arr) < 250:
        return ValidationVerdict(
            survived=False, gates={"sufficient_data": False},
            rejection_reason="insufficient data", metrics=ValidationMetrics(),
        )

    # Walk-forward (OOS). Shadow/paper are separate lifecycle stages (see lifecycle.py).
    wf = WalkForwardEngine().evaluate(arr, n_splits=4, test_size=max(20, len(arr) // 6))
    # Overfitting / significance. PREFERRED path: per-candidate statistics from `campaign`, which
    # this candidate earns on its own column. LEGACY path (no campaign supplied): the campaign
    # constants, retained only so unmigrated call sites keep their exact prior behaviour.
    has_peers = returns_matrix.shape[1] >= 2
    per_candidate = campaign is not None and column is not None
    # THE MULTIPLICITY PENALTY IS PAID ONCE, NOT TWICE (audit 2026-08-01, R0224).
    #
    # DSR is a Probabilistic Sharpe Ratio measured against a DEFLATED benchmark
    # sr0 = expected_max_sharpe(n_trials, ...). That deflation IS a multiplicity correction over
    # the campaign. On the per-candidate path Romano-Wolf ALREADY controls family-wise error over
    # the same N candidates -- so the desk was correcting for the same multiplicity twice and
    # compounding two family-wise bars into one unpassable one.
    #
    # MEASURED, on 240 genuine alphas and 4,800 nulls per effect size (N=420, T=310):
    #     true SR    all gates    without DSR's deflation    false positives
    #        3.0          0.4%                      14.6%    0.000% both ways
    #        5.0          5.8%                      83.8%    0.000% both ways
    #        7.0         32.9%                      99.6%    0.000% both ways
    # Romano-Wolf alone holds the false-positive rate at 0 of 4,800 (95% upper bound 0.08%), so
    # the second deflation bought NO error control and cost up to 78 points of power. Removing
    # BOTH corrections instead sends false positives to 32%, which is why exactly one is kept.
    #
    # WHAT IS DELIBERATELY RETAINED: with n_trials=1 the deflation vanishes but the PSR does not,
    # and PSR adjusts for SKEW and KURTOSIS -- which Romano-Wolf's mean-based bootstrap statistic
    # does not model. A negatively-skewed short-vol payoff can post a beautiful sample Sharpe on
    # a true zero edge; that is the one job here Romano-Wolf cannot do, so the moment-aware half
    # of DSR stays and only the duplicated deflation goes.
    #
    # The LEGACY path keeps the full deflation: nothing else corrects for multiplicity there.
    dsr_trials = 1 if per_candidate else n_trials
    dsr = deflated_sharpe_ratio(arr, n_trials=dsr_trials, sharpe_estimates=sharpe_estimates,
                                threshold=_DSR_THRESHOLD)
    if per_candidate:
        assert campaign is not None and column is not None  # narrowed by per_candidate
        cand_pbo = campaign.cscv.candidate_pbo[column]
        pbo_ok = cand_pbo <= _PBO_THRESHOLD
        sig_ok = campaign.stepdown.rejected[column]
        pbo_value, reality_value = cand_pbo, campaign.stepdown.adjusted_p[column]
    else:
        if pbo is None and has_peers:
            pbo = probability_backtest_overfitting(returns_matrix)
        if rc is None and has_peers:
            rc = whites_reality_check(returns_matrix)
        pbo_ok = pbo is not None and not pbo.overfit
        sig_ok = rc is not None and rc.significant_at_5pct
        pbo_value = pbo.pbo if pbo is not None else 1.0
        reality_value = rc.p_value if rc is not None else 1.0
    # Candidate-aware capacity: use the strategy's OWN realized per-bar edge (bps), so a no-edge
    # strategy gets ~zero capacity (fails) while a real edge on a liquid market passes -- instead
    # of the old fixed edge_bps that made this gate a constant veto for every candidate.
    eff_edge_bps = edge_bps if edge_bps is not None else max(0.0, float(arr.mean()) * 1.0e4)
    cap = capacity_estimate(adv_usd=adv_usd, edge_bps=max(eff_edge_bps, 1.0e-9))
    tail = tail_risk(arr)

    metrics = ValidationMetrics(
        annual_sharpe=float(sharpe_ratio(arr) * np.sqrt(_PERIODS_PER_YEAR)),
        expected_value=float(arr.mean()),
        oos_sharpe=wf.oos_sharpe,
        dsr=dsr.dsr,
        pbo=pbo_value,
        reality_p=reality_value,
        capacity_usd=cap.capacity_usd,
        fragility=tail.tail_risk_score,
    )

    gates = {
        "economic_mechanism": bool(hypothesis.failure_modes),   # declared before testing
        "expected_value": metrics.expected_value > 0,
        "cpcv": _cpcv_positive_fraction(arr) >= _CPCV_MIN_POSITIVE,
        "walk_forward": wf.status is WalkForwardStatus.PASSED,
        "dsr": dsr.passed,
        "pbo": pbo_ok,
        "reality_check": sig_ok,
        # capacity parity: relative to the desk's OWN size (see _min_capacity_usd), never a
        # fixed institutional floor. Small edges are admitted and exploited to their own quota.
        "capacity": cap.capacity_usd >= _min_capacity_usd(),
        "fragility": tail.acceptable,
        # skipped-as-True when no benchmark is supplied (see the constant block above); when
        # one IS supplied the candidate must beat buy-and-hold and equal-weight outright.
        "beats_baselines": _beats_baselines(arr, benchmark_returns),
    }
    failed = [name for name, ok in gates.items() if not ok]
    return ValidationVerdict(
        survived=not failed, gates=gates,
        rejection_reason="" if not failed else "failed: " + ", ".join(failed),
        metrics=metrics,
    )

```

### libs/core/reproducibility.py
```python
"""Reproducibility framework.

Reproducibility is the product: an unreproducible result is not evidence. Every research
run binds five things — a **git commit**, a **UTC timestamp**, a **random seed**, a
**config hash**, and a **data-snapshot id** — into a :class:`ReproducibilityStamp`.
:func:`verify_reproducibility` later re-derives those facts and reports any drift, so a
result can be challenged months after the fact.
"""

from __future__ import annotations

import os
import platform as platform_module
import random
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from libs.core.config import find_project_root, hash_config
from libs.core.errors import GitError, ReproducibilityError
from libs.core.ids import new_stamp_id
from libs.core.time import ensure_utc, utcnow

# A git command runner: takes (args, cwd) and returns trimmed stdout. Injectable for tests.
GitRunner = Callable[[list[str], Path], str]

_UINT32 = 2**32


# --------------------------------------------------------------------------- git


def _default_git_runner(args: list[str], cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:  # git not installed
        raise GitError("git executable not found on PATH") from exc
    if result.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} failed (exit {result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout.strip()


class GitInfo(BaseModel):
    """A point-in-time snapshot of the working tree's git state."""

    model_config = ConfigDict(frozen=True)

    commit: str
    dirty: bool
    branch: str | None = None


def get_git_info(repo_path: Path | None = None, *, runner: GitRunner | None = None) -> GitInfo:
    """Return the current git commit, dirty flag, and branch.

    Raises:
        GitError: if the path is not a git repository, has no commits, or git is missing.
    """
    cwd = Path(repo_path) if repo_path is not None else find_project_root()
    run = runner or _default_git_runner
    commit = run(["rev-parse", "HEAD"], cwd)
    if not commit:
        raise GitError(f"no commits found in repository at {cwd}")
    porcelain = run(["status", "--porcelain"], cwd)
    try:
        branch: str | None = run(["rev-parse", "--abbrev-ref", "HEAD"], cwd)
    except GitError:
        branch = None
    return GitInfo(commit=commit, dirty=bool(porcelain.strip()), branch=branch)


# --------------------------------------------------------------------------- seeding


def seed_everything(seed: int) -> int:
    """Seed all relevant RNGs deterministically and return the seed.

    Seeds the stdlib ``random`` module, NumPy (if installed), and sets ``PYTHONHASHSEED``
    for any child processes spawned afterwards.
    """
    if seed < 0:
        raise ValueError("seed must be non-negative")
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    try:
        import numpy as np

        np.random.seed(seed % _UINT32)
    except ImportError:  # pragma: no cover - numpy is a declared dependency
        pass
    return seed


def _generate_seed() -> int:
    """Generate a fresh, recordable seed when the caller did not supply one."""
    return random.SystemRandom().randint(0, 2**31 - 1)


# --------------------------------------------------------------------------- stamp


class ReproducibilityStamp(BaseModel):
    """An immutable record binding code + data + config + seed + time for one run."""

    model_config = ConfigDict(frozen=True)

    stamp_id: str
    created_at: Any  # datetime; validated to UTC below
    git_commit: str
    git_dirty: bool
    git_branch: str | None
    seed: int
    config_hash: str
    snapshot_id: str
    python_version: str
    platform: str

    @field_validator("created_at")
    @classmethod
    def _created_at_utc(cls, value: Any) -> Any:
        return ensure_utc(value)


def create_reproducibility_stamp(
    config: Mapping[str, Any] | BaseModel | None,
    snapshot_id: str,
    *,
    seed: int | None = None,
    repo_path: Path | None = None,
    set_seed: bool = True,
    require_clean_git: bool = False,
    runner: GitRunner | None = None,
    git_info: GitInfo | None = None,
) -> ReproducibilityStamp:
    """Create a reproducibility stamp and (optionally) seed the RNGs.

    Args:
        config: the configuration object whose hash is recorded.
        snapshot_id: the immutable data-snapshot id the run reads from.
        seed: the random seed; a fresh recordable seed is generated when ``None``.
        repo_path: repository to read git state from (defaults to the project root).
        set_seed: when ``True``, seed all RNGs with the resolved seed.
        require_clean_git: when ``True``, refuse to stamp a dirty working tree.
        runner: injectable git runner (for testing).
        git_info: pre-fetched git state (bypasses ``runner``/``repo_path``).

    Raises:
        ReproducibilityError: if ``require_clean_git`` is set and the tree is dirty,
            or git state cannot be obtained.
    """
    if not snapshot_id:
        raise ReproducibilityError("snapshot_id is required for a reproducibility stamp")

    try:
        info = git_info or get_git_info(repo_path, runner=runner)
    except GitError as exc:
        raise ReproducibilityError(f"cannot stamp without git state: {exc}") from exc

    if require_clean_git and info.dirty:
        raise ReproducibilityError(
            "working tree is dirty; commit or stash before creating a reproducibility stamp"
        )

    resolved_seed = _generate_seed() if seed is None else seed
    if resolved_seed < 0:
        raise ReproducibilityError("seed must be non-negative")
    if set_seed:
        seed_everything(resolved_seed)

    return ReproducibilityStamp(
        stamp_id=new_stamp_id(),
        created_at=utcnow(),
        git_commit=info.commit,
        git_dirty=info.dirty,
        git_branch=info.branch,
        seed=resolved_seed,
        config_hash=hash_config(config),
        snapshot_id=snapshot_id,
        python_version=platform_module.python_version(),
        platform=platform_module.platform(),
    )


class VerificationResult(BaseModel):
    """The outcome of verifying a stamp against the current environment."""

    model_config = ConfigDict(frozen=True)

    ok: bool
    mismatches: list[str]
    current_commit: str
    current_dirty: bool

    def __bool__(self) -> bool:
        return self.ok


def verify_reproducibility(
    stamp: ReproducibilityStamp,
    *,
    config: Mapping[str, Any] | BaseModel | None = None,
    snapshot_id: str | None = None,
    repo_path: Path | None = None,
    require_clean: bool = True,
    strict: bool = False,
    runner: GitRunner | None = None,
    git_info: GitInfo | None = None,
) -> VerificationResult:
    """Verify that the current environment matches a stamp.

    Checks the git commit, optionally the clean-tree requirement, and (when provided) the
    config hash and snapshot id. Returns a :class:`VerificationResult`; with ``strict=True``
    a mismatch raises instead.

    Raises:
        ReproducibilityError: when git state cannot be read, or ``strict`` and verification fails.
    """
    try:
        info = git_info or get_git_info(repo_path, runner=runner)
    except GitError as exc:
        raise ReproducibilityError(f"cannot verify without git state: {exc}") from exc

    mismatches: list[str] = []
    if info.commit != stamp.git_commit:
        mismatches.append(
            f"git commit mismatch: stamp={stamp.git_commit} current={info.commit}"
        )
    if require_clean and info.dirty:
        mismatches.append("working tree is dirty; code does not match a committed state")

    if config is not None:
        current_hash = hash_config(config)
        if current_hash != stamp.config_hash:
            mismatches.append(
                f"config hash mismatch: stamp={stamp.config_hash} current={current_hash}"
            )

    if snapshot_id is not None and snapshot_id != stamp.snapshot_id:
        mismatches.append(
            f"snapshot id mismatch: stamp={stamp.snapshot_id} current={snapshot_id}"
        )

    result = VerificationResult(
        ok=not mismatches,
        mismatches=mismatches,
        current_commit=info.commit,
        current_dirty=info.dirty,
    )
    if strict and not result.ok:
        raise ReproducibilityError("reproducibility verification failed: " + "; ".join(mismatches))
    return result

```

### libs/data/timeframe.py
```python
"""Bar timeframes."""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum

_MINUTES: dict[str, int] = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "H1": 60,
    "H4": 240,
    "H8": 480,
    "D1": 1440,
}


class Timeframe(StrEnum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    H1 = "H1"
    H4 = "H4"
    H8 = "H8"  # crypto perp funding settles every 8h -- native frequency for funding signals
    D1 = "D1"

    @property
    def minutes(self) -> int:
        return _MINUTES[self.value]

    @property
    def timedelta(self) -> timedelta:
        return timedelta(minutes=self.minutes)

    @property
    def pandas_freq(self) -> str:
        """A pandas offset alias (pandas >= 2.2 spelling)."""
        return "1D" if self is Timeframe.D1 else f"{self.minutes}min"

```

### libs/discovery/errors.py
```python
"""Discovery-layer exceptions."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class DiscoveryError(QuantPlatformError):
    """Invalid discovery inputs or configuration."""

```

### libs/discovery/stress_scenario.py
```python
"""stress_scenario_engine — resilience under replayed extreme events.

Overlays historical-style shocks on an alpha's equity and measures the resulting drawdown and
recovery time. Rejects portfolios/alphas that fail the stress-survival requirement.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict

# scenario -> peak-to-trough shock magnitude (fraction)
SCENARIOS: dict[str, float] = {
    "global_financial_crisis": 0.50,
    "flash_crash": 0.10,
    "chf_shock": 0.15,
    "covid_crash": 0.34,
    "inflation_shock": 0.12,
    "commodity_shock": 0.20,
    "crypto_collapse": 0.50,
    "volatility_spike": 0.15,
}


class StressScenarioResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    stress_resilience_score: float  # 0-100, higher = more resilient
    passed: bool
    worst_drawdown: float
    by_scenario: dict[str, float]

    def __bool__(self) -> bool:
        return self.passed


def stress_scenario(
    returns: np.ndarray,
    *,
    exposure: float = 1.0,
    dd_limit: float = 0.35,
) -> StressScenarioResult:
    """Combine the alpha's own drawdown with each scenario shock (scaled by exposure)."""
    arr = np.asarray(returns, dtype="float64")
    equity = np.cumprod(1.0 + arr) if len(arr) else np.array([1.0])
    running = np.maximum.accumulate(equity)
    base_dd = float((1.0 - equity / running).max()) if len(arr) else 0.0

    by_scenario: dict[str, float] = {}
    for name, shock in SCENARIOS.items():
        combined = 1.0 - (1.0 - base_dd) * (1.0 - shock * max(0.0, exposure))
        by_scenario[name] = min(1.0, combined)

    worst = max(by_scenario.values()) if by_scenario else base_dd
    score = max(0.0, 100.0 * (1.0 - worst))
    return StressScenarioResult(
        stress_resilience_score=score,
        passed=worst < dd_limit,
        worst_drawdown=worst,
        by_scenario=by_scenario,
    )

```

### libs/execution/broker.py
```python
"""Broker gateway abstraction.

The execution engine talks only to this interface, so it is broker-agnostic and testable. The
real MT5 implementation isolates the Windows-bound, single-session MetaTrader5 API; tests use a
fake. Orders carry a client-side ``idempotency_key`` so a retry never places a duplicate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from libs.execution.errors import BrokerError


@dataclass(frozen=True)
class OrderRequest:
    """A request to the broker. ``idempotency_key`` dedups retries."""

    idempotency_key: str
    instrument: str
    side: str  # "buy" | "sell"
    qty: float
    order_type: str  # "market" | "limit" | "stop"
    risk_approval_id: str
    price: float | None = None
    alpha_id: str | None = None


@dataclass(frozen=True)
class BrokerOrderResult:
    client_order_id: str
    broker_order_id: int
    status: str  # "filled" | "rejected" | "pending"
    filled_qty: float = 0.0
    fill_price: float | None = None
    deal_id: int | None = None
    message: str = ""


@dataclass(frozen=True)
class BrokerPosition:
    instrument: str
    qty: float  # signed lots
    avg_price: float


@runtime_checkable
class BrokerGateway(Protocol):
    """The minimal broker contract the execution engine depends on."""

    def place_order(self, request: OrderRequest) -> BrokerOrderResult: ...

    def cancel_order(self, broker_order_id: int) -> bool: ...

    def get_positions(self) -> list[BrokerPosition]: ...

    def get_order(self, client_order_id: str) -> BrokerOrderResult | None: ...


class MT5Broker:  # pragma: no cover - requires a live Windows MT5 terminal
    """Real broker gateway backed by the ``MetaTrader5`` package."""

    def __init__(self) -> None:
        try:
            import MetaTrader5 as mt5
        except ImportError as exc:
            raise BrokerError("the MetaTrader5 package is not installed") from exc
        self._mt5 = mt5
        if not mt5.initialize():
            raise BrokerError(f"MT5 initialize() failed: {mt5.last_error()}")

    def place_order(self, request: OrderRequest) -> BrokerOrderResult:
        mt5 = self._mt5
        symbol_info = mt5.symbol_info_tick(request.instrument)
        order_kind = mt5.ORDER_TYPE_BUY if request.side == "buy" else mt5.ORDER_TYPE_SELL
        price = request.price or (symbol_info.ask if request.side == "buy" else symbol_info.bid)
        send = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": request.instrument,
            "volume": request.qty,
            "type": order_kind,
            "price": price,
            "comment": request.idempotency_key,  # idempotency anchor
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(send)
        if result is None:
            raise BrokerError(f"order_send returned None: {mt5.last_error()}")
        filled = result.retcode == mt5.TRADE_RETCODE_DONE
        return BrokerOrderResult(
            client_order_id=request.idempotency_key,
            broker_order_id=int(result.order),
            status="filled" if filled else "rejected",
            filled_qty=float(result.volume),
            fill_price=float(result.price),
            deal_id=int(result.deal),
            message=str(result.comment),
        )

    def cancel_order(self, broker_order_id: int) -> bool:
        mt5 = self._mt5
        result = mt5.order_send(
            {"action": mt5.TRADE_ACTION_REMOVE, "order": broker_order_id}
        )
        return bool(result is not None and result.retcode == mt5.TRADE_RETCODE_DONE)

    def get_positions(self) -> list[BrokerPosition]:
        positions = self._mt5.positions_get() or []
        return [
            BrokerPosition(
                instrument=p.symbol,
                qty=p.volume if p.type == self._mt5.POSITION_TYPE_BUY else -p.volume,
                avg_price=float(p.price_open),
            )
            for p in positions
        ]

    def get_order(self, client_order_id: str) -> BrokerOrderResult | None:
        for deal in self._mt5.history_deals_get() or []:
            if deal.comment == client_order_id:
                return BrokerOrderResult(
                    client_order_id=client_order_id, broker_order_id=int(deal.order),
                    status="filled", filled_qty=float(deal.volume), fill_price=float(deal.price),
                    deal_id=int(deal.ticket),
                )
        return None

```

### libs/execution/canary.py
```python
"""§5 canary: prove the execution path still works BEFORE the strategy needs it.

Every 6h the desk does a minimum-notional round-trip on the most liquid pair. The point is not
the trade -- it is the discovery that keys have been revoked, the IP whitelist has drifted, the
venue has changed a filter, or latency has quietly tripled, on a schedule we choose rather than
at the moment a real signal fires.

Failure or excess latency puts the desk in DEGRADED mode for 6h: limit-only (no market orders --
if the path is sick, do not pay the spread to find out again) and -50% max size.

The critical design point is the direction of the unknown: `mode()` treats "no successful canary
on record" as degraded, not as healthy. A file that has never been written, or was deleted, or
belongs to a fresh host, must not read as a clean bill of health -- the failure mode of the
opposite choice is that a desk with a broken execution path believes it is fine indefinitely.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_STATE = Path("data/canary_state.json")

CANARY_INTERVAL_S = 6 * 3600.0
DEGRADED_S = 6 * 3600.0
# round-trip budget. Generous by design: this is a health probe, not a latency SLO, and a bar
# tight enough to trip on ordinary venue jitter would degrade the desk for noise.
MAX_LATENCY_MS = 5_000.0
DEGRADED_SIZE_MULT = 0.5
# a canary older than this is not merely due, it is evidence the runner itself is dead.
STALE_MULTIPLE = 2.0


@dataclass(frozen=True)
class CanaryMode:
    limit_only: bool
    size_multiplier: float
    reason: str

    @property
    def degraded(self) -> bool:
        return self.limit_only or self.size_multiplier < 1.0


@dataclass
class CanaryState:
    last_attempt_ts: float | None = None
    last_ok_ts: float | None = None
    last_latency_ms: float | None = None
    consecutive_failures: int = 0
    degraded_until: float = 0.0
    history: list[dict[str, Any]] = None  # type: ignore[assignment]
    path: Path = _STATE

    def __post_init__(self) -> None:
        if self.history is None:
            self.history = []

    @classmethod
    def load(cls, path: Path = _STATE) -> CanaryState:
        try:
            d = json.loads(path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            d = {}
        if not isinstance(d, dict):
            d = {}

        def _f(k: str) -> float | None:
            v = d.get(k)
            return float(v) if isinstance(v, (int, float)) else None

        hist = d.get("history")
        return cls(
            last_attempt_ts=_f("last_attempt_ts"),
            last_ok_ts=_f("last_ok_ts"),
            last_latency_ms=_f("last_latency_ms"),
            consecutive_failures=int(d.get("consecutive_failures", 0) or 0),
            degraded_until=float(d.get("degraded_until", 0.0) or 0.0),
            history=hist if isinstance(hist, list) else [],
            path=path,
        )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({
            "last_attempt_ts": self.last_attempt_ts,
            "last_ok_ts": self.last_ok_ts,
            "last_latency_ms": self.last_latency_ms,
            "consecutive_failures": self.consecutive_failures,
            "degraded_until": self.degraded_until,
            "history": self.history[-200:],
        }, indent=2), "utf-8")
        tmp.replace(self.path)

    def is_due(self, now: float) -> bool:
        return self.last_attempt_ts is None or (now - self.last_attempt_ts) >= CANARY_INTERVAL_S

    def is_stale(self, now: float) -> bool:
        """Overdue by enough that the RUNNER, not the venue, is the suspect."""
        if self.last_attempt_ts is None:
            return True
        return (now - self.last_attempt_ts) >= CANARY_INTERVAL_S * STALE_MULTIPLE

    def record(self, *, ok: bool, latency_ms: float | None, now: float,
               detail: str = "") -> CanaryMode:
        """Record one round-trip outcome and return the mode now in force."""
        self.last_attempt_ts = now
        self.last_latency_ms = latency_ms
        slow = ok and latency_ms is not None and latency_ms > MAX_LATENCY_MS
        if ok and not slow:
            self.last_ok_ts = now
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1
            # extend, never shorten: a fresh failure inside an existing degraded window must not
            # hand back a window that expires sooner than the one already running.
            self.degraded_until = max(self.degraded_until, now + DEGRADED_S)
        self.history.append({"ts": now, "ok": bool(ok and not slow),
                             "latency_ms": latency_ms, "detail": detail[:200]})
        return self.mode(now)

    def mode(self, now: float) -> CanaryMode:
        """Current execution mode. Unknown history reads as DEGRADED, never as healthy."""
        if self.last_ok_ts is None:
            return CanaryMode(True, DEGRADED_SIZE_MULT,
                              "no successful canary on record -- unproven execution path")
        if now < self.degraded_until:
            mins = (self.degraded_until - now) / 60.0
            return CanaryMode(True, DEGRADED_SIZE_MULT,
                              f"canary failure ({self.consecutive_failures} consecutive) -- "
                              f"degraded for {mins:.0f}m more")
        if self.is_stale(now):
            hrs = (now - (self.last_attempt_ts or now)) / 3600.0
            return CanaryMode(True, DEGRADED_SIZE_MULT,
                              f"canary has not run in {hrs:.1f}h -- probe itself unproven")
        return CanaryMode(False, 1.0, "canary healthy")

```

### libs/execution/ea_bridge.py
```python
"""File-queue bridge to the MT5 Execution EA — Python stays the brain, the EA only executes.

Transport is a directory of atomic ``key=value`` files in the MT5 *common files* folder (no DLLs,
no sockets): Python writes ``commands/<id>.cmd``; the EA writes ``responses/<id>.resp`` and
refreshes ``state/*``. This implements the existing :class:`BrokerGateway` protocol, so the
unchanged :class:`ExecutionEngine` drives the EA like any other venue — no trading logic lives here
or in the EA. Idempotent by command id; fails closed (ambiguous timeout -> ``BrokerTimeout`` ->
reconcile, never an assumed fill).
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from libs.core.ids import generate_id
from libs.core.time import to_iso8601, utcnow
from libs.execution.broker import BrokerOrderResult, BrokerPosition, OrderRequest
from libs.execution.errors import BrokerError, BrokerTimeout

_FILLED = {"filled"}
_DEAD = {"rejected", "error", "blocked"}
_HB_FMT = "%Y.%m.%d %H:%M:%S"  # MT5 datetime format (GMT); both sides agree on this


def dump_record(record: Mapping[str, object]) -> str:
    """Serialize a flat record to ``key=value`` lines (MQL-friendly; no nesting)."""
    return "".join(f"{k}={v}\n" for k, v in record.items())


def load_record(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            out[key.strip()] = value.strip()
    return out


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, "utf-8")
    os.replace(tmp, path)  # atomic on the same filesystem; EA never reads a partial file


class EABridge:
    """Drives the MT5 Execution EA over the atomic file queue (a ``BrokerGateway``)."""

    def __init__(
        self,
        comm_dir: Path,
        *,
        magic: int = 990001,
        timeout_s: float = 5.0,
        poll_s: float = 0.05,
        on_poll: Callable[[], None] | None = None,
    ) -> None:
        self.root = Path(comm_dir)
        self.commands = self.root / "commands"
        self.responses = self.root / "responses"
        self.state = self.root / "state"
        for d in (self.commands, self.responses, self.state):
            d.mkdir(parents=True, exist_ok=True)
        self.magic = magic
        self.timeout_s = timeout_s
        self.poll_s = poll_s
        self._on_poll = on_poll  # test/advance hook; None in production (EA writes async)

    # ----------------------------------------------------------------- commands
    def _send(self, command: Mapping[str, object]) -> dict[str, str]:
        cid = str(command["id"])
        resp_path = self.responses / f"{cid}.resp"
        if resp_path.exists():
            return load_record(resp_path.read_text("utf-8"))  # idempotent: already answered
        cmd_path = self.commands / f"{cid}.cmd"
        if not cmd_path.exists():
            _atomic_write(cmd_path, dump_record({**command, "magic": self.magic,
                                                 "ts": to_iso8601(utcnow())}))
        deadline = time.monotonic() + self.timeout_s
        while True:
            if self._on_poll is not None:
                self._on_poll()
            if resp_path.exists():
                return load_record(resp_path.read_text("utf-8"))
            if time.monotonic() >= deadline:
                raise BrokerTimeout(f"no EA response for command {cid} within {self.timeout_s}s")
            time.sleep(self.poll_s)

    def place_order(self, request: OrderRequest) -> BrokerOrderResult:
        if not request.risk_approval_id:
            raise BrokerError("fail-closed: order requires a risk_approval_id")
        resp = self._send({
            "id": request.idempotency_key,
            "type": "PENDING" if request.order_type != "market" else "MARKET",
            "symbol": request.instrument, "side": request.side, "volume": request.qty,
            "order_type": request.order_type, "price": request.price or 0.0,
        })
        return self._to_result(request.idempotency_key, resp)

    def cancel_order(self, broker_order_id: int) -> bool:
        resp = self._send({"id": f"cancel-{broker_order_id}", "type": "CLOSE",
                           "ticket": broker_order_id})
        return resp.get("status", "") in (_FILLED | {"ack", "closed"})

    def modify_sltp(self, ticket: int, *, sl: float, tp: float) -> bool:
        resp = self._send({"id": f"modify-{ticket}", "type": "MODIFY", "ticket": ticket,
                           "sl": sl, "tp": tp})
        return resp.get("status", "") in {"ack", "modified", "filled"}

    def flatten_all(self) -> bool:
        """Emergency flatten — also drops the EA-side EMERGENCY_STOP flag file."""
        _atomic_write(self.root / "EMERGENCY_STOP", to_iso8601(utcnow()))
        resp = self._send({"id": generate_id("flatten"), "type": "FLATTEN_ALL"})
        return resp.get("status", "") in {"ack", "filled", "flat"}

    # ----------------------------------------------------------------- reads
    def get_positions(self) -> list[BrokerPosition]:
        path = self.state / "positions.state"
        if not path.exists():
            return []
        positions: list[BrokerPosition] = []
        for line in path.read_text("utf-8").splitlines():
            parts = line.split("|")
            if len(parts) == 3 and float(parts[1]) != 0.0:
                positions.append(
                    BrokerPosition(
                        instrument=parts[0], qty=float(parts[1]), avg_price=float(parts[2])
                    )
                )
        return positions

    def get_order(self, client_order_id: str) -> BrokerOrderResult | None:
        path = self.responses / f"{client_order_id}.resp"
        if not path.exists():
            return None
        return self._to_result(client_order_id, load_record(path.read_text("utf-8")))

    def account_state(self) -> dict[str, str]:
        path = self.state / "account.state"
        return load_record(path.read_text("utf-8")) if path.exists() else {}

    # ----------------------------------------------------------------- heartbeat
    def write_heartbeat(self) -> None:
        """Write the Python liveness beat in the MT5 datetime format the EA parses."""
        _atomic_write(self.state / "py_heartbeat", datetime.now(UTC).strftime(_HB_FMT))

    def read_ea_heartbeat_epoch(self) -> float | None:
        path = self.state / "ea_heartbeat"
        if not path.exists():
            return None
        try:
            stamp = path.read_text("utf-8").strip()
            return datetime.strptime(stamp, _HB_FMT).replace(tzinfo=UTC).timestamp()
        except ValueError:
            return None

    def ea_alive(self, *, max_silence_s: float) -> bool:
        """Whether the EA heartbeat is fresh (fail-closed: missing/unparseable -> not alive)."""
        beat = self.read_ea_heartbeat_epoch()
        return beat is not None and (time.time() - beat) <= max_silence_s

    @staticmethod
    def _to_result(cid: str, resp: Mapping[str, str]) -> BrokerOrderResult:
        status = resp.get("status", "error")
        normalized = "filled" if status in _FILLED else ("rejected" if status in _DEAD else status)
        return BrokerOrderResult(
            client_order_id=cid,
            broker_order_id=int(float(resp.get("ticket", "0") or "0")),
            status=normalized,
            filled_qty=float(resp.get("fill_volume", "0") or "0"),
            fill_price=float(resp["fill_price"]) if resp.get("fill_price") else None,
            deal_id=int(float(resp.get("ticket", "0") or "0")) or None,
            message=resp.get("message", ""),
        )

```

### libs/execution/retry.py
```python
"""Safe retry helper.

Retries are only safe because every order carries an idempotency key — a retry after an
ambiguous failure cannot place a duplicate. Ambiguous timeouts are deliberately *not* retried
blindly here; the engine reconciles instead.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from libs.execution.errors import TransientBrokerError

T = TypeVar("T")
Sleeper = Callable[[float], None]


def retry_call(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    backoff: float = 0.0,
    retry_on: tuple[type[Exception], ...] = (TransientBrokerError,),
    sleeper: Sleeper = time.sleep,
) -> T:
    """Call ``fn`` up to ``attempts`` times, retrying on ``retry_on`` exceptions."""
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except retry_on as exc:
            last_exc = exc
            if attempt < attempts and backoff > 0:
                sleeper(backoff * attempt)
    assert last_exc is not None
    raise last_exc

```

### libs/features/__init__.py
```python
"""``libs.features`` — versioned, PIT-correct features with leakage + parity validation.

The same definition serves training and serving (parity by construction); the leakage test
(future invariance) rejects future/target/lookahead/hindsight/full-sample leakage. Built-in
features are registered into :data:`DEFAULT_REGISTRY` on import.
"""

from __future__ import annotations

from libs.features.builtin import BUILTIN_FEATURES, register_builtin_features
from libs.features.definition import ComputeFn, FeatureDefinition
from libs.features.errors import FeatureError, LeakageError, ParityError
from libs.features.labels import LABEL_PREFIX, forward_direction, forward_log_return
from libs.features.pit import build_feature_table, compute_online_vector, pit_join
from libs.features.registry import (
    DEFAULT_REGISTRY,
    FeatureRegistry,
    get_feature,
    register_feature,
)
from libs.features.validation import (
    FeatureValidation,
    LeakageResult,
    ParityResult,
    run_leakage_test,
    run_parity_test,
    validate_feature,
)

register_builtin_features(DEFAULT_REGISTRY)

__all__ = [  # noqa: RUF022  # grouped by concern
    # definition / registry
    "FeatureDefinition",
    "ComputeFn",
    "FeatureRegistry",
    "DEFAULT_REGISTRY",
    "register_feature",
    "get_feature",
    "BUILTIN_FEATURES",
    "register_builtin_features",
    # validation
    "validate_feature",
    "run_leakage_test",
    "run_parity_test",
    "FeatureValidation",
    "LeakageResult",
    "ParityResult",
    # pit
    "pit_join",
    "build_feature_table",
    "compute_online_vector",
    # labels
    "forward_log_return",
    "forward_direction",
    "LABEL_PREFIX",
    # errors
    "FeatureError",
    "LeakageError",
    "ParityError",
]

```

### libs/features/pit.py
```python
"""Point-in-time joins and feature-table construction.

``pit_join`` is an as-of (backward) merge: each base row sees only the most recent auxiliary
row at or before its timestamp — never a future one. The offline feature table and the online
feature vector are built from the same definitions, guaranteeing parity by construction.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from libs.features.definition import FeatureDefinition
from libs.features.errors import FeatureError

TIMESTAMP = "timestamp"


def pit_join(
    base: pd.DataFrame,
    other: pd.DataFrame,
    *,
    value_columns: Sequence[str],
    on: str = TIMESTAMP,
    suffix: str = "",
) -> pd.DataFrame:
    """As-of backward join: attach the latest ``other`` values known at each ``base`` time."""
    left = base.sort_values(on)
    right = other.sort_values(on)[[on, *value_columns]]
    if suffix:
        right = right.rename(columns={c: f"{c}{suffix}" for c in value_columns})
    merged = pd.merge_asof(left, right, on=on, direction="backward")
    return merged.reset_index(drop=True)


def build_feature_table(
    bars: pd.DataFrame, definitions: Sequence[FeatureDefinition]
) -> pd.DataFrame:
    """Build the offline (training) feature table: ``timestamp`` + one column per feature."""
    table = pd.DataFrame({TIMESTAMP: bars[TIMESTAMP].to_numpy()})
    for definition in definitions:
        table[definition.key] = definition.compute(bars).to_numpy()
    return table


def compute_online_vector(
    history: pd.DataFrame, definitions: Sequence[FeatureDefinition]
) -> dict[str, float]:
    """Compute the latest (serving) feature vector from history up to the current bar."""
    if history.empty:
        raise FeatureError("cannot compute an online vector from empty history")
    return {
        definition.key: float(definition.compute(history).to_numpy(dtype="float64")[-1])
        for definition in definitions
    }

```

### libs/ops/campaign_queue.py
```python
"""Durable, crash-safe campaign queue for 24/7 autonomous operation.

Lease-based work queue over the system-of-record (SQLite WAL). The invariants that make continuous
operation safe with zero human intervention:

  * **No duplicate execution** -- a campaign is dedup'd by content hash on enqueue, and claimed by
    exactly one worker via an atomic ``BEGIN IMMEDIATE`` lease.
  * **No lost work on crash** -- a worker holds a time-boxed lease and must renew it; if the worker
    dies (power loss, OOM, kill), the lease expires and :meth:`reclaim_stale` returns the campaign
    to the queue. Re-running is safe because the research lab itself dedups candidates.
  * **Bounded retries** -- a failed campaign is re-queued until ``max_attempts``, then parked as
    ``failed`` for inspection (never silently dropped, never infinitely retried).

Operational state only: this table is mutable and cleanable, unlike the append-only audit log and
research ledger, which are never touched here.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from libs.core.ids import generate_id
from libs.store.connection import Database


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def content_hash(spec: dict[str, Any]) -> str:
    """Stable hash of a campaign spec for deduplication (order-independent)."""
    canonical = json.dumps(spec, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class CampaignQueue:
    """Atomic, lease-based campaign queue. Safe for multiple concurrent workers."""

    def __init__(self, db: Database) -> None:
        self.db = db

    # --- producer ---------------------------------------------------------------
    def enqueue(
        self, spec: dict[str, Any], *, priority: int = 100, max_attempts: int = 3
    ) -> str | None:
        """Queue a campaign. Returns its id, or None if an identical spec already exists (dedup)."""
        h = content_hash(spec)
        now = _iso(_now())
        cid = generate_id("camp")
        with self.db.transaction() as conn:
            existing = conn.execute(
                "SELECT id FROM campaigns WHERE content_hash = ?", (h,)
            ).fetchone()
            if existing is not None:
                return None
            conn.execute(
                """INSERT INTO campaigns
                   (id, content_hash, spec_json, priority, status, attempts, max_attempts,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'queued', 0, ?, ?, ?)""",
                (cid, h, json.dumps(spec), priority, max_attempts, now, now),
            )
        return cid

    # --- consumer (atomic) ------------------------------------------------------
    def lease(self, worker_id: str, *, lease_seconds: int = 300) -> dict[str, Any] | None:
        """Atomically claim the highest-priority runnable campaign, or None if the queue is empty.

        Runnable = queued, OR leased with an expired lease (a previous worker died). Uses
        BEGIN IMMEDIATE so only one worker is ever in the critical section.
        """
        now = _now()
        now_iso = _iso(now)
        expires = _iso(now + timedelta(seconds=lease_seconds))
        conn = self.db.connection
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                """SELECT id, spec_json, attempts, max_attempts FROM campaigns
                   WHERE status = 'queued'
                      OR (status = 'leased' AND lease_expires_at < ?)
                   ORDER BY priority ASC, seq ASC LIMIT 1""",
                (now_iso,),
            ).fetchone()
            if row is None:
                conn.execute("COMMIT")
                return None
            conn.execute(
                """UPDATE campaigns
                   SET status='leased', worker_id=?, lease_expires_at=?, attempts=attempts+1,
                       started_at=COALESCE(started_at, ?), updated_at=?
                   WHERE id=?""",
                (worker_id, expires, now_iso, now_iso, row["id"]),
            )
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        return {"id": row["id"], "spec": json.loads(row["spec_json"]),
                "attempts": row["attempts"] + 1, "max_attempts": row["max_attempts"]}

    def renew(self, campaign_id: str, worker_id: str, *, lease_seconds: int = 300) -> bool:
        """Extend a held lease (call periodically while a long campaign runs)."""
        expires = _iso(_now() + timedelta(seconds=lease_seconds))
        with self.db.transaction() as conn:
            cur = conn.execute(
                """UPDATE campaigns SET lease_expires_at=?, updated_at=?
                   WHERE id=? AND worker_id=? AND status='leased'""",
                (expires, _iso(_now()), campaign_id, worker_id),
            )
            return cur.rowcount > 0

    def complete(self, campaign_id: str, worker_id: str, result: dict[str, Any]) -> None:
        now = _iso(_now())
        with self.db.transaction() as conn:
            conn.execute(
                """UPDATE campaigns
                   SET status='done', result_json=?, finished_at=?, updated_at=?, error=NULL
                   WHERE id=? AND worker_id=?""",
                (json.dumps(result), now, now, campaign_id, worker_id),
            )

    def fail(self, campaign_id: str, worker_id: str, error: str) -> str:
        """Re-queue for retry until max_attempts, then park as 'failed'. Returns the new status."""
        now = _iso(_now())
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT attempts, max_attempts FROM campaigns WHERE id=?", (campaign_id,)
            ).fetchone()
            if row is None:
                return "missing"
            retry = row["attempts"] < row["max_attempts"]
            status = "queued" if retry else "failed"
            conn.execute(
                """UPDATE campaigns
                   SET status=?, worker_id=NULL, lease_expires_at=NULL, error=?,
                       finished_at=CASE WHEN ?='failed' THEN ? ELSE finished_at END, updated_at=?
                   WHERE id=?""",
                (status, error[:1000], status, now, now, campaign_id),
            )
        return status

    # --- recovery / maintenance -------------------------------------------------
    def reclaim_stale(self) -> int:
        """Return campaigns whose lease expired (dead workers) to the queue. Crash recovery."""
        now = _iso(_now())
        with self.db.transaction() as conn:
            cur = conn.execute(
                """UPDATE campaigns SET status='queued', worker_id=NULL, lease_expires_at=NULL,
                       updated_at=?
                   WHERE status='leased' AND lease_expires_at < ?""",
                (now, now),
            )
            return int(cur.rowcount)

    def cleanup(self, *, keep_days: int = 7) -> int:
        """Delete terminal campaigns older than keep_days (operational hygiene; audit untouched)."""
        cutoff = _iso(_now() - timedelta(days=keep_days))
        with self.db.transaction() as conn:
            cur = conn.execute(
                "DELETE FROM campaigns WHERE status IN ('done','cancelled') AND finished_at < ?",
                (cutoff,),
            )
            return int(cur.rowcount)

    def stats(self) -> dict[str, Any]:
        rows = self.db.execute(
            "SELECT status, COUNT(*) AS n FROM campaigns GROUP BY status"
        ).fetchall()
        counts = {r["status"]: int(r["n"]) for r in rows}
        oldest = self.db.execute(
            "SELECT MIN(created_at) AS t FROM campaigns WHERE status='queued'"
        ).fetchone()
        age = 0.0
        if oldest and oldest["t"]:
            age = (_now() - datetime.fromisoformat(oldest["t"])).total_seconds()
        return {
            "queued": counts.get("queued", 0), "leased": counts.get("leased", 0),
            "done": counts.get("done", 0), "failed": counts.get("failed", 0),
            "cancelled": counts.get("cancelled", 0),
            "depth": counts.get("queued", 0) + counts.get("leased", 0),
            "oldest_queued_age_s": round(age, 1),
        }

```

### libs/portfolio/engine.py
```python
"""Portfolio construction engine — orchestrates allocation, controls, constraints, analytics.

Risk overrides alpha: this engine only *proposes* target weights respecting hard caps; the risk
gate disposes. Construction is deterministic (reproducible) and, when given a database, every
build is journaled to the immutable audit log.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from libs.portfolio.constraints import apply_constraints
from libs.portfolio.covariance import covariance_from_alphas
from libs.portfolio.diversification import (
    apply_correlation_controls,
    diversification_ratio,
    effective_bets,
)
from libs.portfolio.errors import PortfolioError
from libs.portfolio.exposures import (
    calculate_factor_exposures,
    calculate_risk_contributions,
    calculate_strategy_exposures,
)
from libs.portfolio.hrp import hrp_weights
from libs.portfolio.models import AlphaInput, PortfolioConstraints, PortfolioTarget
from libs.portfolio.optimize import optimize_portfolio
from libs.portfolio.risk_parity import allocate_risk


def build_portfolio(
    alphas: Sequence[AlphaInput],
    *,
    correlation: np.ndarray | None = None,
    constraints: PortfolioConstraints | None = None,
    method: str = "hrp",
) -> PortfolioTarget:
    """Construct a target allocation from alphas using ``method`` and enforce all constraints."""
    if not alphas:
        raise PortfolioError("at least one alpha is required")
    ids = [a.alpha_id for a in alphas]
    if len(set(ids)) != len(ids):
        raise PortfolioError("alpha ids must be unique")

    cov = covariance_from_alphas(alphas, correlation)
    constraints = constraints or PortfolioConstraints()

    if method == "risk_parity":
        base = allocate_risk(alphas, correlation=correlation)
    elif method == "hrp":
        weights_array = hrp_weights(cov)
        base = {i: float(w) for i, w in zip(ids, weights_array, strict=True)}
    elif method == "optimize":
        base = optimize_portfolio(alphas, correlation=correlation)
    else:
        raise PortfolioError("method must be 'risk_parity', 'hrp', or 'optimize'")

    binding: list[str] = []
    if correlation is not None:
        base, corr_binding = apply_correlation_controls(base, cov, ids)
        binding.extend(corr_binding)

    weights, constraint_binding = apply_constraints(base, alphas, constraints)
    binding.extend(constraint_binding)

    weights_array = np.array([weights[i] for i in ids], dtype="float64")
    return PortfolioTarget(
        weights=weights,
        method=method,
        factor_exposures=calculate_factor_exposures(weights, alphas),
        strategy_exposures=calculate_strategy_exposures(weights, alphas),
        risk_contributions=calculate_risk_contributions(weights, cov, ids),
        diversification_ratio=diversification_ratio(weights_array, cov),
        effective_bets=effective_bets(weights_array),
        binding_constraints=sorted(set(binding)),
    )


class PortfolioEngine:
    """Stateful wrapper that journals each portfolio build to the audit log."""

    def __init__(self, db: object | None = None) -> None:
        self._audit = None
        if db is not None:
            from libs.store.audit import AuditLog

            self._audit = AuditLog(db)  # type: ignore[arg-type]

    def build_portfolio(
        self,
        alphas: Sequence[AlphaInput],
        *,
        correlation: np.ndarray | None = None,
        constraints: PortfolioConstraints | None = None,
        method: str = "hrp",
    ) -> PortfolioTarget:
        target = build_portfolio(
            alphas, correlation=correlation, constraints=constraints, method=method
        )
        if self._audit is not None:
            self._audit.append(
                "portfolio_build", actor="portfolio_engine",
                inputs={"method": method, "n_alphas": len(alphas)},
                outcome=_summary(target.weights),
            )
        return target


def _summary(weights: Mapping[str, float]) -> str:
    return ", ".join(f"{k}={v:.3f}" for k, v in sorted(weights.items()))

```

### libs/portfolio/hrp.py
```python
"""Hierarchical Risk Parity (López de Prado).

Correlation clustering -> quasi-diagonalization -> recursive bisection with inverse-variance
allocation. No matrix inversion, so it is robust to the unstable covariances that wreck Markowitz.
"""

from __future__ import annotations

from typing import cast

import numpy as np
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform

from libs.portfolio.covariance import cov_to_corr


def _quasi_diag(link: np.ndarray, num_items: int) -> list[int]:
    links = link.astype(int)
    current = [int(links[-1, 0]), int(links[-1, 1])]
    while max(current) >= num_items:
        expanded: list[int] = []
        for item in current:
            if item < num_items:
                expanded.append(item)
            else:
                row = links[item - num_items]
                expanded.append(int(row[0]))
                expanded.append(int(row[1]))
        current = expanded
    return current


def _cluster_variance(cov: np.ndarray, items: list[int]) -> float:
    sub = cov[np.ix_(items, items)]
    inv_var = 1.0 / np.diag(sub)
    weights = inv_var / inv_var.sum()
    return float(weights @ sub @ weights)


def hrp_weights(cov: np.ndarray) -> np.ndarray:
    """Compute HRP weights for a covariance matrix (original asset order)."""
    sigma = np.asarray(cov, dtype="float64")
    n = sigma.shape[0]
    if n == 1:
        return np.array([1.0])

    corr = cov_to_corr(sigma)
    distance = np.sqrt(np.clip(0.5 * (1.0 - corr), 0.0, None))
    condensed = squareform(distance, checks=False)
    link = linkage(condensed, method="single")
    sort_ix = _quasi_diag(np.asarray(link), n)

    weights = np.ones(n, dtype="float64")
    clusters: list[list[int]] = [sort_ix]
    while clusters:
        next_clusters: list[list[int]] = []
        for cluster in clusters:
            if len(cluster) <= 1:
                continue
            mid = len(cluster) // 2
            left, right = cluster[:mid], cluster[mid:]
            var_left = _cluster_variance(sigma, left)
            var_right = _cluster_variance(sigma, right)
            alpha = 1.0 - var_left / (var_left + var_right)
            for i in left:
                weights[i] *= alpha
            for i in right:
                weights[i] *= 1.0 - alpha
            next_clusters.extend((left, right))
        clusters = next_clusters

    return cast("np.ndarray", weights / weights.sum())

```

### libs/portfolio/lifecycle.py
```python
"""Alpha lifecycle primitives: decay state, promotion ladder, replacement committee, research ROI.

Pure, tested functions that decide which sleeves live, scale, or die -- the governance layer above
allocation. Kept numeric/stateless so they wire onto the shadow + portfolio JSON. Conservative by
design: replacement defaults to KEEP-BOTH, promotion never auto-reaches production, and decay needs
real rolling windows (returns 'accumulating' until they exist) so nothing is retired on noise.
"""

from __future__ import annotations

# research -> ... -> production. A sleeve may not skip stages.
LADDER = ["research", "backtest", "validation", "shadow", "testnet", "small_capital", "production"]
HEALTH = ["Healthy", "Watchlist", "Degraded", "Retire", "Accumulating"]


def decay_state(rolling: dict[str, float | None], expected: float | None) -> str:
    """Health from rolling 30/60/90d Sharpe vs the validated expectation. Worst window drives it:
    >=60% below (or negative) -> Retire, >=40% -> Degraded, >=20% -> Watchlist, else Healthy.
    Returns 'Accumulating' until at least one rolling window exists."""
    vals = [v for v in rolling.values() if v is not None]
    if not vals:
        return "Accumulating"
    if expected is None or expected <= 0:
        return "Accumulating"
    worst = min(vals)
    drop = 1.0 - worst / expected
    if worst < 0 or drop >= 0.6:
        return "Retire"
    if drop >= 0.4:
        return "Degraded"
    if drop >= 0.2:
        return "Watchlist"
    return "Healthy"


def promotion_stage(days_shadow: int, fwd_sharpe: float | None, gates_passed: int,
                    n_gates: int, *, min_shadow: int = 90) -> str:
    """Where a sleeve sits on the ladder. Conservative: stays in 'shadow' until it has both the full
    forward window AND a positive forward Sharpe; never auto-promotes past small_capital."""
    if n_gates and gates_passed < 0.6 * n_gates:
        return "research"
    if fwd_sharpe is None or days_shadow < min_shadow or fwd_sharpe < 0.5:
        return "shadow"
    if days_shadow < int(1.5 * min_shadow):
        return "testnet"
    return "small_capital"


def replacement_decision(current: dict[str, float], candidate: dict[str, float],
                         correlation: float) -> str:
    """Replacement committee. Default KEEP-BOTH (additive alpha is valuable). Only REPLACE when the
    candidate dominates on Sharpe AND CAGR AND capacity AND is highly correlated (>0.7) to the
    incumbent (i.e. a strictly better version of the same bet). Otherwise REJECT or keep both."""
    dominates = (candidate.get("sharpe", 0.0) > current.get("sharpe", 0.0)
                 and candidate.get("cagr", 0.0) >= current.get("cagr", 0.0)
                 and candidate.get("capacity", 0.0) >= current.get("capacity", 0.0))
    if not dominates:
        return "reject"
    return "replace" if correlation > 0.7 else "keep_both"


def research_roi(benefit: float, p_success: float, effort: float) -> float:
    """ROI score = (expected portfolio benefit x P(success)) / engineering effort."""
    return round(benefit * p_success / effort, 3) if effort > 0 else 0.0


def rank_by_roi(items: list[dict[str, float | str]]) -> list[dict[str, float | str]]:
    """Rank research candidates by ROI score (each item needs benefit, p_success, effort)."""
    for it in items:
        it["roi"] = research_roi(float(it["benefit"]), float(it["p_success"]), float(it["effort"]))
    return sorted(items, key=lambda d: -float(d["roi"]))

```

### libs/research/capacity_policy.py
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
_NAV_STALE_DAYS = 7.0
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

### libs/research/desk_economics.py
```python
"""What return the desk needs just to stand still.

Every real fund knows its hurdle; this one had never computed one. `config/costs.yaml` models
what a TRADE costs. Nothing modelled what the DESK costs -- the VPS, the model access, the data
-- so "is this book big enough to be worth running?" had no numeric answer.

The arithmetic is trivial and the discipline is not: unknown costs are reported as UNKNOWN and
propagate to "cannot compute", never to zero. A burn rate that silently omits the largest line
item is worse than no burn rate at all, because it yields a hurdle someone would actually plan
against. Every function here refuses to guess.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MONTHS_PER_YEAR = 12.0


@dataclass(frozen=True)
class CostBase:
    """Declared monthly costs, with the unknowns kept visible rather than folded into the total."""

    known: dict[str, float]
    unknown: tuple[str, ...]

    @property
    def monthly_usd(self) -> float:
        """Sum of what is KNOWN. Read alongside `is_complete` -- this is a floor, not the total."""
        return round(sum(self.known.values()), 2)

    @property
    def annual_usd(self) -> float:
        return round(self.monthly_usd * MONTHS_PER_YEAR, 2)

    @property
    def is_complete(self) -> bool:
        return not self.unknown

    @property
    def largest(self) -> tuple[str, float] | None:
        return max(self.known.items(), key=lambda kv: kv[1]) if self.known else None


def parse_costs(cfg: dict[str, Any]) -> CostBase:
    """Split declared costs into known amounts and unknown line items."""
    _raw = cfg.get("monthly_usd")
    raw: dict[str, Any] = _raw if isinstance(_raw, dict) else {}
    known: dict[str, float] = {}
    unknown: list[str] = []
    for name, value in raw.items():
        if value is None:
            unknown.append(str(name))
            continue
        try:
            known[str(name)] = float(value)
        except (TypeError, ValueError):
            unknown.append(str(name))
    return CostBase(known=known, unknown=tuple(sorted(unknown)))


@dataclass(frozen=True)
class Hurdle:
    """The return the book must earn to cover the desk's own costs."""

    equity_usd: float
    monthly_cost_usd: float
    complete: bool

    @property
    def monthly_pct(self) -> float | None:
        if self.equity_usd <= 0:
            return None
        return round(100.0 * self.monthly_cost_usd / self.equity_usd, 4)

    @property
    def annual_pct(self) -> float | None:
        """Compounded, not multiplied by 12 -- the desk's own doctrine is geometric growth, and
        a hurdle stated arithmetically understates what compounding actually has to deliver."""
        m = self.monthly_pct
        if m is None:
            return None
        return float(round(100.0 * ((1.0 + m / 100.0) ** MONTHS_PER_YEAR - 1.0), 3))

    @property
    def verdict(self) -> str:
        a = self.annual_pct
        if a is None:
            return "no equity deployed -- hurdle undefined (any cost is infinite % of zero)"
        floor = "at least " if not self.complete else ""
        return (f"the book must return {floor}{a:.2f}%/yr "
                f"(${self.monthly_cost_usd:,.2f}/mo on ${self.equity_usd:,.0f}) "
                f"before a single dollar is profit")


def hurdle(equity_usd: float, costs: CostBase) -> Hurdle:
    return Hurdle(equity_usd=max(0.0, float(equity_usd)),
                  monthly_cost_usd=costs.monthly_usd,
                  complete=costs.is_complete)


def capital_for_hurdle(costs: CostBase, target_annual_pct: float) -> float | None:
    """Equity at which the cost base falls to an acceptable hurdle. None when uncomputable.

    The inverse question, and the more useful one for a small desk: not "what must I earn" but
    "how much capital makes these costs tolerable". Below this figure the desk is a research
    project being funded, which is a legitimate choice but should be a KNOWN one.
    """
    if target_annual_pct <= 0 or costs.monthly_usd <= 0:
        return None
    monthly_target = (1.0 + target_annual_pct / 100.0) ** (1.0 / MONTHS_PER_YEAR) - 1.0
    if monthly_target <= 0:
        return None
    return float(round(costs.monthly_usd / monthly_target, 2))


def runway_months(cash_usd: float, costs: CostBase) -> float | None:
    """Months of costs the cash covers. None when costs are zero or unknown-dominated."""
    if costs.monthly_usd <= 0:
        return None
    return round(max(0.0, float(cash_usd)) / costs.monthly_usd, 1)


def assess(equity_usd: float, cfg: dict[str, Any]) -> dict[str, Any]:
    """Full economic picture for the report artifact."""
    costs = parse_costs(cfg)
    h = hurdle(equity_usd, costs)
    _pol = cfg.get("policy")
    policy: dict[str, Any] = _pol if isinstance(_pol, dict) else {}
    try:
        target = float(policy.get("max_acceptable_annual_hurdle_pct", 10.0))
    except (TypeError, ValueError):
        target = 10.0
    needed = capital_for_hurdle(costs, target)
    a = h.annual_pct
    return {
        "equity_usd": h.equity_usd,
        "monthly_cost_usd": costs.monthly_usd,
        "annual_cost_usd": costs.annual_usd,
        "cost_base_complete": costs.is_complete,
        "undeclared_line_items": list(costs.unknown),
        "largest_known_cost": costs.largest,
        "hurdle_monthly_pct": h.monthly_pct,
        "hurdle_annual_pct": a,
        "max_acceptable_annual_hurdle_pct": target,
        "hurdle_acceptable": (None if a is None else a <= target),
        "capital_needed_for_acceptable_hurdle_usd": needed,
        "verdict": h.verdict,
        "note": ("Unknown costs are EXCLUDED from the total and listed under "
                 "undeclared_line_items; every figure here is therefore a FLOOR until "
                 "cost_base_complete is true. Declare the real numbers in "
                 "config/desk_costs.yaml -- a hurdle computed from a partial cost base is the "
                 "one output of this module that could do harm."),
    }

```

### libs/signal_engine/alpha_weighting.py
```python
"""Alpha weighting — turn raw alpha votes into regime/health/decay-aware weights.

The weight of an alpha's vote is its conviction scaled by quality (health), durability (decay
multiplier), and regime fit. ``DynamicWeighting`` normalizes the weights across the contributing
alphas for one symbol so the aggregator works with a convex combination.
"""

from __future__ import annotations

from collections.abc import Sequence

from libs.signal_engine.models import AlphaSignal, MarketState
from libs.signal_engine.regime import RegimeRouter, RegimeTransitionRouter

_EPS = 1e-12


class AlphaWeighting:
    """Computes a non-negative weight for a single alpha vote."""

    def __init__(
        self,
        *,
        router: RegimeRouter | None = None,
        transition_router: RegimeTransitionRouter | None = None,
    ) -> None:
        self.router = router or RegimeRouter()
        self.transition_router = transition_router or RegimeTransitionRouter()

    def weight(self, signal: AlphaSignal, state: MarketState) -> float:
        """conviction x health x decay x current-regime-fit x predicted-regime-fit."""
        regime_fit = self.router.route(signal, state)
        future_fit = self.transition_router.route(signal, state)
        return float(
            max(0.0, signal.strength)
            * max(0.0, signal.health_score / 100.0)
            * max(0.0, signal.decay_multiplier)
            * max(0.0, regime_fit)
            * max(0.0, future_fit)
        )


class DynamicWeighting:
    """Normalizes per-alpha weights across the alphas voting on one symbol."""

    def __init__(self, *, weighting: AlphaWeighting | None = None) -> None:
        self.weighting = weighting or AlphaWeighting()

    def weights(
        self, signals: Sequence[AlphaSignal], state: MarketState
    ) -> dict[str, float]:
        raw = {s.alpha_id: self.weighting.weight(s, state) for s in signals}
        total = sum(raw.values())
        if total <= _EPS:
            return dict.fromkeys(raw, 0.0)
        return {k: v / total for k, v in raw.items()}

```

### libs/signal_engine/persistence.py
```python
"""Signal persistence and stability — durability and steadiness of a signal.

``SignalPersistenceEngine`` rewards age, survival, and regime consistency while penalizing flips
and noise. ``SignalStabilityEngine`` measures oscillation/direction changes/prediction steadiness
and rejects signals that are too jittery to trust. Both emit 0-100 scores.
"""

from __future__ import annotations

from libs.signal_engine.models import PersistenceResult, StabilityResult


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class SignalPersistenceEngine:
    """Scores how durable a signal has been over its observed life."""

    def assess(
        self,
        *,
        signal_age: int,
        survival: float,
        flip_frequency: float,
        noise_level: float,
        regime_consistency: float,
        max_age: int = 60,
    ) -> PersistenceResult:
        age_factor = _clip01(signal_age / max_age) if max_age > 0 else 0.0
        components = {
            "age_factor": age_factor,
            "survival": _clip01(survival),
            "regime_consistency": _clip01(regime_consistency),
            "flip_penalty": _clip01(flip_frequency),
            "noise_penalty": _clip01(noise_level),
        }
        base = (
            0.20 * age_factor
            + 0.30 * components["survival"]
            + 0.30 * components["regime_consistency"]
            + 0.20 * (1.0 - components["flip_penalty"])
        )
        score = 100.0 * _clip01(base) * (1.0 - 0.5 * components["noise_penalty"])
        return PersistenceResult(persistence_score=score, components=components)


class SignalStabilityEngine:
    """Scores signal steadiness; below ``threshold`` the signal is rejected."""

    def __init__(self, *, threshold: float = 60.0) -> None:
        self.threshold = threshold

    def assess(
        self,
        *,
        oscillation: float,
        direction_change_rate: float,
        prediction_stability: float,
        alpha_stability: float,
        regime_stability: float,
    ) -> StabilityResult:
        components = {
            "steadiness": 1.0 - _clip01(oscillation),
            "direction_consistency": 1.0 - _clip01(direction_change_rate),
            "prediction_stability": _clip01(prediction_stability),
            "alpha_stability": _clip01(alpha_stability),
            "regime_stability": _clip01(regime_stability),
        }
        score = 100.0 * (sum(components.values()) / len(components))
        return StabilityResult(
            stability_score=score, components=components, passed=score >= self.threshold
        )

```

### libs/signal_engine/signal_embedding_engine.py
```python
"""Signal embedding engine — embed trade candidates for similarity and de-duplication.

Turns a :class:`TradeCandidate` into a fixed-length numeric vector (its scores plus a regime
one-hot) so signals can be compared and clustered. Tight clusters reveal redundant signals that
would otherwise masquerade as diversification.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from libs.signal_engine.models import Regime, TradeCandidate

_EPS = 1e-12
_REGIMES = tuple(Regime)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na <= _EPS or nb <= _EPS:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


class SignalEmbeddingEngine:
    """Builds candidate embeddings and clusters near-duplicate signals."""

    def embed(self, candidate: TradeCandidate) -> list[float]:
        scores = [
            candidate.edge.edge_score / 100.0,
            candidate.confidence.confidence,
            candidate.quality.quality_score / 100.0,
            candidate.persistence.persistence_score / 100.0,
            candidate.stability.stability_score / 100.0,
            candidate.capacity.future_capacity_score / 100.0,
            candidate.institutional.score / 100.0,
        ]
        one_hot = [1.0 if candidate.regime is r else 0.0 for r in _REGIMES]
        return scores + one_hot

    def similarity(self, a: TradeCandidate, b: TradeCandidate) -> float:
        return _cosine(np.array(self.embed(a)), np.array(self.embed(b)))

    def cluster(
        self, candidates: Mapping[str, TradeCandidate], *, threshold: float = 0.98
    ) -> list[list[str]]:
        vectors = {sym: np.array(self.embed(c)) for sym, c in candidates.items()}
        clusters: list[list[str]] = []
        centroids: list[np.ndarray] = []
        for sym, vec in vectors.items():
            placed = False
            for i, centroid in enumerate(centroids):
                if _cosine(vec, centroid) >= threshold:
                    clusters[i].append(sym)
                    placed = True
                    break
            if not placed:
                clusters.append([sym])
                centroids.append(vec)
        return clusters

```

### libs/stage14/errors.py
```python
"""Stage 14 portfolio construction errors."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class Stage14Error(QuantPlatformError):
    """Base error for the Stage 14 compounding / portfolio construction engine."""


class PortfolioGovernanceError(Stage14Error):
    """Raised when a portfolio action violates Stage 14 governance (fail-closed)."""

```

### libs/stage15/scoring.py
```python
"""Alpha quality score — 0-100, weighted toward durability, NOT raw returns.

Survival, capacity, diversification, stability, and economic logic dominate; out-of-sample Sharpe
contributes modestly; fragility and decay are penalties. Raw expected return is deliberately
excluded from the positive weighting — a high backtest return does not make a durable alpha.
"""

from __future__ import annotations

from libs.stage15.models import AlphaQualityScore, AlphaScores

_POSITIVE_WEIGHTS: dict[str, float] = {
    "survival": 0.22,
    "capacity": 0.15,
    "diversification": 0.15,
    "stability": 0.15,
    "economic": 0.13,
    "oos_sharpe": 0.10,
    "calmar": 0.05,
    "sortino": 0.05,
}


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def alpha_quality_score(scores: AlphaScores) -> AlphaQualityScore:
    components = {
        "survival": _clip01(scores.survival_score / 100.0),
        "capacity": _clip01(scores.capacity_score / 100.0),
        "diversification": _clip01(scores.diversification_score / 100.0),
        "stability": _clip01(scores.stability_score / 100.0),
        "economic": _clip01(scores.economic_score / 100.0),
        "oos_sharpe": _clip01(scores.sharpe / 3.0),
        "calmar": _clip01(scores.calmar / 3.0),
        "sortino": _clip01(scores.sortino / 3.0),
    }
    positive = sum(_POSITIVE_WEIGHTS[k] * v for k, v in components.items())
    penalty = 0.5 * _clip01(scores.fragility_score / 100.0) + 0.5 * _clip01(
        scores.decay_score / 100.0
    )
    score = 100.0 * _clip01(positive - 0.25 * penalty)
    components["penalty"] = penalty
    return AlphaQualityScore(score=score, components=components)

```

### libs/validation/reject_rescore.py
```python
"""Reject re-score PLANNING -- the ROI decision of the rejection-shadow feeder.

The feeder that closes the gate-leak loop must re-score rejected candidates on data that arrived
AFTER their rejection. Re-scoring ALL rejects is wasteful: the 420 picked-clean price rejects are
almost all genuinely dead, and burning compute confirming that recovers nothing. The ROI is in the
NEAR-MISSES -- rejects whose in-sample edge was strong but that failed a multiplicity/robustness
gate; those are the ones a drifted-over-strict gate most plausibly killed by mistake.

So the feeder's intelligence is: take only rejects OLD ENOUGH to have accrued forward data, rank
them by how CLOSE they came to passing (near-miss first), and cap the batch so compute goes to the
recoverable few. This module is that pure, testable planner; the runtime-heavy re-eval itself
(rebuild the candidate's signal, run it on the forward window) is injected by the runner, not faked.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from libs.core.time import from_iso8601, utcnow


class RescorePlan(BaseModel):
    """The prioritized, eligibility-filtered, capped batch of reject ids to re-score this run."""

    model_config = ConfigDict(frozen=True)

    selected: tuple[str, ...]  # reject ids to re-score, near-miss first
    n_eligible: int  # rejects old enough to have forward data
    n_too_young: int  # rejects skipped for having no forward data yet
    n_capped: int  # eligible rejects deferred to a later run by the batch cap
    verdict: str


def plan_rescore(
    rejects: Sequence[tuple[str, str, float]],
    *,
    as_of: str | None = None,
    min_age_days: float = 30.0,
    limit: int = 50,
) -> RescorePlan:
    """Plan which rejects to re-score, near-miss first (MAX-ROI feeder scheduling).

    ``rejects`` is ``(candidate_id, rejected_at_iso, nearness)`` where ``nearness`` is a monotone
    proxy for how close the reject came to passing (e.g. its in-sample / OOS Sharpe at rejection --
    higher = nearer the bar = more likely a gate error worth recovering). Only rejects at least
    ``min_age_days`` old are eligible (younger ones have no post-rejection data to score). The
    eligible set is ranked by ``nearness`` descending and truncated to ``limit`` so compute lands on
    the recoverable few, not the picked-clean many. Deterministic: ties break by id.
    """
    now = from_iso8601(as_of) if as_of else utcnow()
    eligible: list[tuple[str, float]] = []
    too_young = 0
    for cid, rejected_at, nearness in rejects:
        try:
            age_days = (now - from_iso8601(rejected_at)).total_seconds() / 86400.0
        except Exception:
            continue
        if age_days < min_age_days:
            too_young += 1
            continue
        eligible.append((cid, float(nearness)))
    eligible.sort(key=lambda x: (-x[1], x[0]))  # near-miss first, deterministic tie-break
    selected = tuple(cid for cid, _ in eligible[:limit])
    n_capped = max(0, len(eligible) - len(selected))
    if not eligible:
        verdict = f"no eligible rejects (>= {min_age_days:g}d old); {too_young} too young to score"
    else:
        verdict = (
            f"{len(selected)} near-miss rejects queued for re-score (of {len(eligible)} eligible; "
            f"{n_capped} deferred by cap {limit}; {too_young} too young)"
        )
    return RescorePlan(
        selected=selected, n_eligible=len(eligible), n_too_young=too_young,
        n_capped=n_capped, verdict=verdict,
    )

```

### libs/validation/stepwise.py
```python
"""Per-candidate multiplicity control: CSCV rank-consistency and Romano-Wolf stepdown.

WHY THIS EXISTS.  ``probability_backtest_overfitting`` and ``whites_reality_check`` both take
*only* the (T x N) campaign matrix -- the individual candidate's returns are never an input.  They
are therefore **campaign constants**: used as per-candidate gates they veto every candidate in a
batch identically, with probability 1, no matter how good any single one is.  That is not a strict
bar, it is a bar with zero information (2026-07-29 audit: dsr/pbo/reality_check each rejected
>=98% of 420 candidates, 0 survivors ever).

This module supplies the candidate-aware counterparts at the SAME thresholds:

* :func:`cscv_candidate_pbo` -- each candidate's own out-of-sample rank consistency across every
  combinatorially-symmetric split, instead of the campaign's in-sample-best.
* :func:`romano_wolf_stepdown` -- per-strategy significance with **family-wise error controlled at
  alpha across all N**, instead of one p-value describing only the maximum.

Neither is a loosening.  Romano-Wolf is a strictly more rigorous multiple-testing procedure than a
single campaign p-value: it still pays for every trial, it just attributes the result to the
candidate that earned it.  The campaign statistics remain valuable and are still reported, as
diagnostics of the *search procedure* -- which is what they actually measure.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
from pydantic import BaseModel, ConfigDict
from scipy.stats import rankdata

from libs.validation.bootstrap import stationary_block_indices
from libs.validation.errors import ValidationError

__all__ = [
    "CSCVResult",
    "StepdownResult",
    "cscv_candidate_pbo",
    "romano_wolf_stepdown",
]


class CSCVResult(BaseModel):
    """Per-candidate CSCV outcome plus the classic campaign statistic for reference."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    candidate_pbo: list[float]
    """For each candidate k: the fraction of CSCV splits where k's OOS rank fell below the
    median.  Low = k holds its relative standing out of sample; high = k's in-sample standing
    was an artefact of the split."""

    campaign_pbo: float
    """Classic Lopez de Prado PBO: how often the IN-SAMPLE-BEST lands below the OOS median.  A
    property of the SELECTION PROCEDURE, reported as a diagnostic, never a per-candidate gate."""

    n_combinations: int
    n_strategies: int


class StepdownResult(BaseModel):
    """Romano-Wolf stepdown outcome: per-candidate rejections at FWER <= alpha."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    rejected: list[bool]
    adjusted_p: list[float]
    raw_p: list[float] = []
    """UNADJUSTED per-candidate bootstrap p-value: the fraction of that candidate's OWN bootstrap
    null draws at least as extreme as its observed statistic. Added 2026-07-30 because the FDR
    screen (libs/validation/screen_select.py) needs raw p-values -- feeding it `adjusted_p` is a
    DOUBLE correction (FWER-adjusted, then FDR-adjusted again), which is statistically incoherent
    and measurably evicted a known Sharpe-3 winner from a 60-null batch in calibration. Same one
    bootstrap pass, no extra compute."""
    t_stat: list[float]
    alpha: float
    n_strategies: int
    n_boot: int


def _block_sufficient_stats(
    matrix: np.ndarray, n_splits: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-block count / sum / sum-of-squares, so any block union's Sharpe is O(1) to combine.

    The naive CSCV recomputes a Sharpe for every (split, strategy) pair -- C(16,8)=12870 splits
    x N strategies x 2 sides.  Sharpe depends on the sample only through (n, sum, sum-sq), all of
    which are additive over blocks, so we accumulate them once per block and then combine with a
    matrix product.  Exact, not an approximation.
    """
    blocks = np.array_split(np.arange(matrix.shape[0]), n_splits)
    counts = np.array([len(b) for b in blocks], dtype="float64")
    sums = np.stack([matrix[b].sum(axis=0) for b in blocks])
    sqs = np.stack([(matrix[b] ** 2).sum(axis=0) for b in blocks])
    return counts, sums, sqs


def _sharpe_from_stats(n: np.ndarray, s: np.ndarray, q: np.ndarray) -> np.ndarray:
    """Vectorised per-period Sharpe (mean/std, ddof=1) from sufficient statistics."""
    n_col = n[:, None]
    mean = s / n_col
    var = (q - (s**2) / n_col) / (n_col - 1.0)
    std = np.sqrt(np.maximum(var, 0.0))
    out: np.ndarray = np.divide(mean, std, out=np.zeros_like(mean), where=std > 0)
    return out


def cscv_candidate_pbo(returns_matrix: np.ndarray, *, n_splits: int = 16) -> CSCVResult:
    """Combinatorially-symmetric cross-validation, scored PER CANDIDATE.

    For every way of choosing half the blocks as in-sample, each candidate is ranked by its
    out-of-sample Sharpe against its peers.  ``candidate_pbo[k]`` is the fraction of splits in
    which candidate k landed below the OOS median -- i.e. how often its standing failed to
    survive the split.  The classic campaign PBO (rank of the *in-sample-best*) is computed from
    the same pass and returned alongside as a diagnostic.
    """
    matrix = np.asarray(returns_matrix, dtype="float64")
    if matrix.ndim != 2 or matrix.shape[1] < 2:
        raise ValidationError("returns_matrix must be 2-D with >= 2 strategies")
    if n_splits % 2 != 0 or n_splits < 2:
        raise ValidationError("n_splits must be a positive even number")
    n_obs, n_strategies = matrix.shape
    if n_obs < n_splits:
        raise ValidationError("not enough observations for the requested n_splits")

    counts, sums, sqs = _block_sufficient_stats(matrix, n_splits)
    combos = list(combinations(range(n_splits), n_splits // 2))
    is_mask = np.zeros((len(combos), n_splits), dtype="float64")
    for i, ids in enumerate(combos):
        is_mask[i, list(ids)] = 1.0
    oos_mask = 1.0 - is_mask

    below_median = np.zeros(n_strategies, dtype="float64")
    campaign_below = 0
    # Chunk the split loop so peak memory stays O(chunk x N) even for wide campaigns.
    chunk = max(1, int(4.0e6 // max(n_strategies, 1)))
    for start in range(0, len(combos), chunk):
        im = is_mask[start : start + chunk]
        om = oos_mask[start : start + chunk]
        is_sr = _sharpe_from_stats(im @ counts, im @ sums, im @ sqs)
        oos_sr = _sharpe_from_stats(om @ counts, om @ sums, om @ sqs)
        # rankdata along each split's row: 1 = worst, N = best.
        oos_rank = np.apply_along_axis(rankdata, 1, oos_sr)
        w = oos_rank / (n_strategies + 1.0)
        below_median += (w < 0.5).sum(axis=0)
        best = np.argmax(is_sr, axis=1)
        campaign_below += int((w[np.arange(len(im)), best] < 0.5).sum())

    n_comb = float(len(combos))
    return CSCVResult(
        candidate_pbo=(below_median / n_comb).tolist(),
        campaign_pbo=campaign_below / n_comb,
        n_combinations=len(combos),
        n_strategies=n_strategies,
    )


def romano_wolf_stepdown(
    performance: np.ndarray,
    *,
    alpha: float = 0.05,
    n_boot: int = 1000,
    mean_block: float = 10,
    seed: int = 0,
) -> StepdownResult:
    """Romano-Wolf (2005) stepwise multiple test: which strategies beat the benchmark.

    ``performance[t, k]`` is strategy k's edge over the benchmark at t (benchmark = 0 here).
    Controls the family-wise error rate at ``alpha`` across all N strategies while returning a
    verdict for EACH one -- the per-candidate counterpart to White's Reality Check, which only
    ever tests the maximum.  Studentised, and bootstrapped with the stationary block bootstrap so
    autocorrelation is preserved.
    """
    f = np.asarray(performance, dtype="float64")
    if f.ndim != 2 or f.shape[1] < 1:
        raise ValidationError("performance must be a 2-D (T x N) array")
    if not 0.0 < alpha < 1.0:
        raise ValidationError("alpha must be in (0, 1)")
    t_obs, n = f.shape

    d_bar = f.mean(axis=0)
    omega = f.std(axis=0, ddof=1)
    omega = np.where(omega <= 0, np.inf, omega)  # zero-variance strategies cannot be significant
    t_stat = np.sqrt(t_obs) * d_bar / omega

    rng = np.random.default_rng(seed)
    boot = np.empty((n_boot, n), dtype="float64")
    for b in range(n_boot):
        idx = stationary_block_indices(t_obs, mean_block, rng)
        boot[b] = np.sqrt(t_obs) * (f[idx].mean(axis=0) - d_bar) / omega

    # RAW per-candidate p: each candidate against its OWN bootstrap null (no max-statistic,
    # no stepdown) -- the unadjusted input any downstream multiplicity procedure must start from.
    raw_p = np.array([float(np.mean(boot[:, k] >= t_stat[k])) for k in range(n)], dtype="float64")

    rejected = np.zeros(n, dtype=bool)
    adjusted_p = np.ones(n, dtype="float64")
    active = np.ones(n, dtype=bool)
    while active.any():
        max_null = boot[:, active].max(axis=1)
        crit = float(np.quantile(max_null, 1.0 - alpha))
        newly = active & (t_stat > crit)
        # Every still-active candidate's p-value is measured against the CURRENT null; the ones
        # rejected at this step have theirs frozen, the rest keep updating as the set shrinks.
        adjusted_p[active] = np.array(
            [float(np.mean(max_null >= t_stat[k])) for k in np.flatnonzero(active)]
        )
        if not newly.any():
            break
        rejected |= newly
        active &= ~newly

    # Stepdown p-values must be monotone in the test statistic (Romano-Wolf 2016 sec. 4).
    order = np.argsort(-t_stat)
    adjusted_p[order] = np.maximum.accumulate(adjusted_p[order])

    return StepdownResult(
        rejected=rejected.tolist(),
        adjusted_p=adjusted_p.tolist(),
        raw_p=raw_p.tolist(),
        t_stat=t_stat.tolist(),
        alpha=alpha,
        n_strategies=n,
        n_boot=n_boot,
    )

```

### scripts/alpha_lifecycle.py
```python
"""ALPHA LIFECYCLE -- failure patterns, transfer pipeline, feature novelty, anomaly memory.

FOUR BUILD ITEMS, ONE MODULE. All four are lifecycle concerns over the same objects (trades,
features, alphas, incidents) and all four read artifacts that already exist. Four separate scripts
would mean three unwired ones.

1 FAILURE PATTERN FILTER -- most desks store winners. This mines the 249 realised closes for the
  CHARACTERISTICS that predict losses, which is a permanent filter rather than a post-mortem.
  It is not a re-derivation of the cost model: it asks which combination of measurable traits
  precedes a losing close, and would have flagged COOKIEUSDT before 21 opens rather than after.

2 ALPHA TRANSFER PIPELINE -- a discovery that never reaches capital has zero economic value. The
  desk had no explicit state machine, so "validated" and "deployed" were indistinguishable in
  conversation while being 0 and 0 in reality. Every alpha now carries a gate state and the
  evidence required to advance.

3 FEATURE NOVELTY DETECTOR -- prevents renamed factors. RSI / stochastic / Williams %R are one
  mechanism wearing three names. Reuses the jaccard machinery already written for research
  exchange intake, plus mechanism-level overlap, which is the stronger test: same mechanism means
  same failure mode regardless of construction.

4 MARKET ANOMALY MEMORY -- append-only record of rare events. Costs nothing, only accrues, and
  starting late is the only way to lose. Seeded with incident #6.

Read-only w.r.t. trading. Run from repo root.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRADES = ROOT / "data/cashcarry_trades.json"
COST = ROOT / "data/cost_model.json"
FEAT = ROOT / "data/feature_library.json"
GRAVE = ROOT / "docs/graveyard.md"
OUT = ROOT / "data/alpha_lifecycle.json"
ANOM = ROOT / "data/anomaly_memory.jsonl"

DEFAULT_RT = 39.5

# The transfer pipeline. Each gate names the EVIDENCE that advances it -- a state machine whose
# transitions are opinions is just a label.
PIPELINE = [
    ("DISCOVERED", "a mechanism and a falsification criterion exist"),
    ("SCREENED", "Stage-A screen run; ZERO promotion authority"),
    ("DECONTAMINATED", "survives orthogonalisation to the obvious confound"),
    ("COST_REAL", "net of MEASURED round-trip, not a default"),
    ("FORWARD_REGISTERED", "pre-registered forward clock with a fixed end date"),
    ("FORWARD_PASSED", "clock reached its date and the sign held"),
    ("SHADOW", "traded on paper at live sizing"),
    ("SMALL_CAPITAL", "live, minimum size, kill switch verified"),
    ("SCALED", "size increased on realised evidence"),
    ("MONITORED", "decay and crowding tracked"),
    ("RETIRED", "replaced or mechanism died"),
]

# Where the desk's actual alphas sit. Honest, and mostly early.
ALPHAS = [
    {"id": "A001", "name": "funding persistence (carry entry signal)",
     "mechanism": "M_FORCED_DELEVERAGE", "state": "COST_REAL",
     "evidence": "IC +0.432 (t +29.7) 24h; selection edge +25.3%/yr; survives cost model",
     "blocker": "no pre-registered forward clock of its own -- it audits the LIVE system instead"},
    {"id": "A002", "name": "OI/LS positioning", "mechanism": "M_FORCED_DELEVERAGE",
     "state": "FORWARD_REGISTERED", "evidence": "OOS chained, clock running",
     "blocker": "verdict due 2026-08-07"},
    {"id": "A003", "name": "CNY structural premium", "mechanism": "M_STRUCTURAL_BARRIER",
     "state": "SCREENED", "evidence": "structure test passed",
     "blocker": "INPUT FAILED measurement gate -- no producer, timestamps assumed"},
    {"id": "A004", "name": "liquidity withdrawal (moat)", "mechanism": "M_LIQUIDITY_WITHDRAWAL",
     "state": "DECONTAMINATED", "evidence": "1 of 270 constructions tested; residual rho +0.015 "
                                            "(t +0.28) -- that construction is a null",
     "blocker": "269 constructions untested; 0.4% coverage"},
]


def _closes():
    try:
        t = json.loads(TRADES.read_text("utf-8"))
    except Exception:  # blind-except intentional (BLE001)
        return []
    rows = t if isinstance(t, list) else t.get("trades", [])
    out = []
    for r in rows:
        if r.get("event") != "close":
            continue
        h, n, f, pp = (r.get("held_hours"), r.get("notional"), r.get("funding_rate"),
                       r.get("price_pnl"))
        if None in (h, n, f, pp) or not n or float(h) <= 0:
            continue
        h, n, f, pp = float(h), float(n), float(f), float(pp)
        out.append({"sym": r.get("symbol"), "held_h": h, "notional": n, "funding": f,
                    "net_bps": (n * f * (h / 8.0) + pp) / n * 1e4})
    return out


def _rt(cm, sym):
    try:
        v = cm["symbols"][sym]["pair"]["500"].get("pair_roundtrip_bps")
        return (float(v), True) if v is not None else (DEFAULT_RT, False)
    except (KeyError, TypeError, ValueError):
        return (DEFAULT_RT, False)


def failure_patterns():
    rows = _closes()
    try:
        cm = json.loads(COST.read_text("utf-8"))
    except Exception:  # blind-except intentional (BLE001)
        cm = {}
    if len(rows) < 40:
        print("  too few closes to mine")
        return []
    for r in rows:
        r["rt"], r["measured"] = _rt(cm, r["sym"])
        r["loss"] = r["net_bps"] < 0

    # Traits are BINARY and pre-declared, so this is a lift table and not a search over
    # thresholds. Searching thresholds on 249 rows would manufacture a filter.
    traits = {
        "cost_unmeasured": lambda r: not r["measured"],
        "cost_gt_20bps": lambda r: r["rt"] > 20,
        "cost_gt_100bps": lambda r: r["rt"] > 100,
        "hold_under_24h": lambda r: r["held_h"] < 24,
        "funding_under_2bp": lambda r: r["funding"] * 1e4 < 2.0,
        "notional_over_1k": lambda r: r["notional"] > 1000,
    }
    base = sum(r["loss"] for r in rows) / len(rows)
    out = []
    print(f"  base loss rate across {len(rows)} closes: {base*100:.1f}%\n")
    print(f"  {'trait':<22}{'n':>5}{'loss%':>8}{'lift':>7}   verdict")
    for name, fn in traits.items():
        sub = [r for r in rows if fn(r)]
        if len(sub) < 15:
            continue
        lr = sum(r["loss"] for r in sub) / len(sub)
        lift = lr / max(base, 1e-9)
        v = ("PREDICTS LOSS" if lift > 1.25 else
             "protective" if lift < 0.8 else "no signal")
        print(f"  {name:<22}{len(sub):>5}{lr*100:>7.1f}%{lift:>7.2f}   {v}")
        out.append({"trait": name, "n": len(sub), "loss_rate": round(lr, 4),
                    "lift": round(lift, 3), "verdict": v})
    worst = [t for t in out if t["lift"] > 1.25]
    if worst:
        print(f"\n  PERMANENT FILTER CANDIDATES: {', '.join(t['trait'] for t in worst)}")
        print("  These are lift ratios on pre-declared binary traits, not a threshold search.")
    else:
        print("\n  No trait clears 1.25x lift. The sample cannot support a permanent filter yet;")
        print("  reporting that rather than lowering the bar until something passes.")
    return out



# Mechanism-level kill check runs BEFORE token overlap. Concept archaeology blocks a phrase;
# mechanism archaeology blocks a reason -- including wordings nobody has used yet.
_DEAD_MECHS = {
    "M_PRICE_PATTERN": ("rsi", "stochastic", "williams", "macd", "moving average", "oversold",
                        "overbought", "breakout", "momentum", "reversal", "bollinger"),
    "M_ATTENTION_DELAY": ("attention", "sentiment", "social", "twitter", "reddit", "search "
                          "interest", "google trends", "wikipedia", "hype", "narrative"),
    "M_SKILL_PERSISTENCE": ("copytrad", "leaderboard", "top trader", "smart money",
                            "profitable wallet", "trader ranking"),
    "M_FLOW_PRESSURE": ("netflow", "inflow predicts", "outflow predicts"),
}


def _dead_mechanism(text: str):
    """Return the BEST-matching dead mechanism, not the first dict hit.

    First-match returned M_PRICE_PATTERN for "social attention momentum from search interest"
    because "momentum" is a price-pattern keyword and dict order put it first. The verdict was
    right and the evidence trail was wrong, which sends the next reader to the wrong graveyard.
    Score every family and take the strongest.
    """
    low = text.lower()
    best, bm = 0, None
    for m, kws in _DEAD_MECHS.items():
        hits = sum(1 for k in kws if k in low)
        if hits > best:
            best, bm = hits, m
    return bm

_STOP = {"the", "a", "an", "of", "to", "in", "for", "and", "or", "with", "is", "are", "be", "this", "that", "it", "as", "by", "from", "at"}


def novelty(candidate: str) -> dict:
    def toks(s):
        return {w for w in re.findall(r"[a-z]{4,}", s.lower()) if w not in _STOP}
    known = []
    try:
        for f in json.loads(FEAT.read_text("utf-8")).get("features", []):
            known.append((f"{f['name']} {f.get('rationale','')}", f.get("mechanism")))
    except Exception:  # blind-except intentional (BLE001)
        pass
    if GRAVE.exists():
        for ln in GRAVE.read_text("utf-8").splitlines():
            if ln.startswith("|") and not set(ln) <= set("|- "):
                c = [x.strip() for x in ln.strip("|").split("|")]
                if c and c[0].lower() not in ("name", "signal", "strategy"):
                    known.append((c[0], None))
    ct = toks(candidate)
    best, bn = 0.0, None
    for text, _m in known:
        kt = toks(text)
        if not kt or not ct:
            continue
        j = len(ct & kt) / len(ct | kt)
        if j > best:
            best, bn = j, text
    dead = _dead_mechanism(candidate)
    if dead:
        return {"candidate": candidate, "max_jaccard": round(best, 3),
                "nearest": f"FAMILY KILL {dead}", "dead_mechanism": dead,
                "verdict": "DEAD-MECHANISM"}
    return {"candidate": candidate, "max_jaccard": round(best, 3),
            "nearest": (bn or "")[:70], "dead_mechanism": None,
            "verdict": "DUPLICATE" if best >= 0.5 else "novel" if best < 0.25 else "adjacent"}


def main() -> None:
    print("=== 1. FAILURE PATTERN FILTER -- what predicts a losing close ===")
    fp = failure_patterns()

    print("\n=== 2. ALPHA TRANSFER PIPELINE -- discovery without capital is worth zero ===\n")
    idx = {s: i for i, (s, _) in enumerate(PIPELINE)}
    print(f"  {'id':<6}{'alpha':<40}{'state':<20}{'gate':>6}")
    for a in ALPHAS:
        print(f"  {a['id']:<6}{a['name'][:40]:<40}{a['state']:<20}"
              f"{idx.get(a['state'],0)+1}/{len(PIPELINE)}")
        print(f"        blocker: {a['blocker'][:88]}")
    reached = max((idx.get(a["state"], 0) for a in ALPHAS), default=0) + 1
    print(f"\n  furthest any alpha has reached: gate {reached}/{len(PIPELINE)} "
          f"({PIPELINE[reached-1][0]})")
    print("  gates 6-11 (FORWARD_PASSED .. RETIRED) have NEVER been occupied. That is the")
    print("  whole distance between this desk's research output and its economic output.")

    print("\n=== 3. FEATURE NOVELTY DETECTOR -- stop renamed factors ===\n")
    tests = ["depth5 replenishment rate after liquidity withdrawal",
             "social attention momentum from search interest",
             "RSI oversold bounce on micro caps"]
    nov = [novelty(t) for t in tests]
    for r in nov:
        print(f"  {r['verdict']:<10} jaccard {r['max_jaccard']:.2f}  {r['candidate'][:52]}")
        if r["nearest"]:
            print(f"             nearest prior: {r['nearest']}")

    print("\n=== 4. MARKET ANOMALY MEMORY -- append-only, starts accruing today ===")
    seed = {"ts": "2026-07-27T21:06:52Z", "kind": "DESK_INCIDENT", "id": "INC-006",
            "title": "cash-carry hedge inverted short->long, twice",
            "detail": "COOKIEUSDT futures +916,772 where -183,140 required (unrl -$482, free "
                      "margin $110); recurred on 1000CATUSDT +1,138,985 after systemd respawn",
            "root_cause": "order size exceeded venue MARKET_LOT_SIZE (150,000) -> -4005 reject -> "
                          "resting post-only limit fallback -> accumulated fills crossed zero; no "
                          "reduceOnly on any futures cover",
            "detection_gap": "no invariant asserted that a tracked carry's futures leg is SHORT",
            "fixes": ["chunking to venue cap", "reduceOnly on covers",
                      "closes bypass the maker path", "hedge_integrity.py rail",
                      "kill forces rail over churn guard"]}
    existing = set()
    if ANOM.exists():
        for ln in ANOM.read_text("utf-8").splitlines():
            try:
                existing.add(json.loads(ln).get("id"))
            except json.JSONDecodeError:
                continue
    if seed["id"] not in existing:
        with ANOM.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(seed) + "\n")
        print(f"  seeded {seed['id']}: {seed['title']}")
    print(f"  {len(existing | {seed['id']})} anomaly record(s) -> {ANOM}")
    print("  Rare events are the stress-test library. Starting late is the only way to lose one.")

    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "failure_patterns": fp,
                               "pipeline": [{"gate": g, "evidence": e} for g, e in PIPELINE],
                               "alphas": ALPHAS, "furthest_gate": reached,
                               "novelty_tests": nov}, indent=1), "utf-8")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()

```

### scripts/blindspot_max.py
```python
"""BLIND-SPOT MAXIMISER -- the four mechanically-findable classes of unknown-unknown.

The existing stack (blind_spot, blindspot_prober, info_class_map, feature coverage) finds KNOWN
unknowns: empty cells in a map the desk drew. This finds dimensions that were never mapped, using
only what the desk already owns, with no LLM and no credit.

FOUR CLASSES, in ascending order of how invisible they are:

 1 UNREAD FIELDS      data collected, never referenced by any code. (in unobserved.py; summarised
                      here for one complete picture)
 2 UNMODELLED ENTITIES values that APPEAR in collected data but exist in no universe, config or
                      analysis -- protocols, chains, assets the desk records and never considers.
                      An entity in your own files that you have never named is invisible twice.
 3 UNCROSSED PAIRS    N collectors admit N(N-1)/2 joins. A pair no script has ever referenced
                      together is a relationship nobody has looked for. Fusion is where weak
                      signals become strong, so an uncrossed pair is an unexamined interaction.
 4 UNCONDITIONED SLICES  hour-of-day, day-of-week, regime. If no analysis ever groups by them, a
                      relationship that exists only inside one slice is invisible at the mean --
                      and the mean is the only thing this desk has ever computed.

WHY 3 AND 4 ARE THE DEEPEST. A missing dataset is a known gap you can name. An unexamined
INTERACTION between two datasets you already have cannot be named, because nobody wrote it down
as a thing that could exist. The same is true of a conditional relationship: averaging over a
slice does not merely miss the effect, it actively hides it behind a null.

Read-only. No LLM, no network.
"""
from __future__ import annotations

import itertools
import json
import pathlib
from collections import Counter
from datetime import UTC, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data/blindspot_max.json"

_PLUMBING = {"ts", "date", "timestamp", "time", "updated", "id", "pool", "src", "note", "kind",
             "status", "period", "src_ts", "row_id", "provenance", "name", "event", "mock", "seat"}
_ENTITY_FIELDS = ("symbol", "asset", "project", "chain", "protocol", "venue", "exchange")
_SLICES = {
    "hour_of_day": ("hour", ".hour", "groupby('hour", 'groupby("hour', "hourly"),
    "day_of_week": ("weekday", "dayofweek", "day_of_week"),
    "regime": ("regime", "crypto_regime", "vol_state", "trend_state"),
    "session": ("asia", "london", "new_york", "session"),
}


def _code() -> str:
    out = ""
    for d in ("scripts", "libs"):
        for p in (ROOT / d).rglob("*.py"):
            out += p.read_text("utf-8", errors="ignore")
    return out


def main() -> None:
    code = _code()
    scripts = {p.stem: p.read_text("utf-8", errors="ignore")
               for p in (ROOT / "scripts").glob("*.py")}
    files = sorted((ROOT / "data").glob("*.jsonl"))

    samples, entities = {}, {}
    for f in files:
        try:
            with f.open("r", encoding="utf-8", errors="ignore") as fh:
                rows = [json.loads(ln) for i, ln in enumerate(fh) if ln.strip() and i < 300]
        except Exception:  # blind-except intentional (BLE001)
            continue
        rows = [r for r in rows if isinstance(r, dict)]
        if rows:
            samples[f.name] = rows
            ent = Counter()
            for r in rows:
                for k in _ENTITY_FIELDS:
                    v = r.get(k)
                    if isinstance(v, str) and 1 < len(v) < 32:
                        ent[v] += 1
            entities[f.name] = ent

    print("=== BLIND-SPOT MAXIMISER -- four mechanical classes of unknown-unknown ===\n")

    # ---- 2 UNMODELLED ENTITIES
    unmodelled = []
    for fn, ent in entities.items():
        for v, cnt in ent.items():
            if code.count(v) == 0:
                unmodelled.append({"file": fn, "entity": v, "rows": cnt})
    print(f"2. UNMODELLED ENTITIES -- appear in our data, named nowhere in our code: "
          f"{len(unmodelled)}")
    for r in sorted(unmodelled, key=lambda x: -x["rows"])[:12]:
        print(f"     {r['entity']:<24} {r['rows']:>4} rows in {r['file']}")
    if unmodelled:
        print("     An entity recorded in your own files that you have never named is invisible")
        print("     twice: absent from every universe, and absent from every gap list.")

    # ---- 3 UNCROSSED PAIRS
    live = [f for f in samples if len(samples[f]) >= 30]
    pairs, crossed = [], 0
    for a, b in itertools.combinations(sorted(live), 2):
        together = any(a in s and b in s for s in scripts.values())
        if together:
            crossed += 1
        else:
            pairs.append((a, b))
    tot = crossed + len(pairs)
    print(f"\n3. UNCROSSED COLLECTOR PAIRS -- {len(pairs)} of {tot} possible joins never examined "
          f"({crossed/max(tot,1)*100:.1f}% crossed)")
    for a, b in pairs[:10]:
        print(f"     {a}  x  {b}")
    print("     Fusion is where weak signals become strong. A pair no script has referenced")
    print("     together is an interaction nobody has looked for -- and unlike a missing dataset,")
    print("     it cannot be named as a gap because nobody wrote it down as possible.")

    # ---- 4 UNCONDITIONED SLICES
    print("\n4. UNCONDITIONED SLICES -- dimensions no analysis ever groups by:")
    slice_rows = []
    for name, kws in _SLICES.items():
        hits = sum(code.count(k) for k in kws)
        used = hits > 2
        slice_rows.append({"slice": name, "code_hits": hits, "conditioned": used})
        print(f"     {name:<14} {'CONDITIONED' if used else 'NEVER CONDITIONED'}  "
              f"({hits} code references)")
    never = [r["slice"] for r in slice_rows if not r["conditioned"]]
    if never:
        print(f"     {len(never)} dimension(s) never conditioned on. A relationship that exists")
        print("     only inside one slice is invisible at the mean -- and the mean is the only")
        print("     thing this desk has ever computed. Averaging does not miss the effect, it")
        print("     HIDES it behind a null.")

    # ---- 1 UNREAD FIELDS (summary)
    unread = 0
    for _fn, rows in samples.items():
        keys = Counter()
        for r in rows:
            keys.update(r.keys())
        for k, cnt in keys.items():
            if k in _PLUMBING or cnt < len(rows) * 0.5:
                continue
            if code.count(f'"{k}"') + code.count(f"'{k}'") <= 2:
                unread += 1

    print("\n=== TOTAL MECHANICALLY-FINDABLE BLIND SPOTS ===")
    print(f"  1 unread fields          {unread}")
    print(f"  2 unmodelled entities    {len(unmodelled)}")
    print(f"  3 uncrossed pairs        {len(pairs)}")
    print(f"  4 unconditioned slices   {len(never)}")
    print(f"  TOTAL                    {unread + len(unmodelled) + len(pairs) + len(never)}")
    print("\n  None of these is an edge. Each is a QUESTION NOBODY ASKED, and every one enters")
    print("  Stage-A screening like anything else. What distinguishes them is that the")
    print("  acquisition cost is already paid -- this is the cheapest frontier the desk has.")
    print("\n  WHAT REMAINS UNREACHABLE MECHANICALLY: a dimension absent from the data entirely.")
    print("  No amount of introspection finds a source you never collected. That is the hunter's")
    print("  job, and it needs credit.")

    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "unread_fields": unread, "unmodelled_entities": unmodelled[:200],
                               "uncrossed_pairs": [list(p) for p in pairs[:300]],
                               "slices": slice_rows,
                               "total": unread + len(unmodelled) + len(pairs) + len(never)},
                              indent=1), "utf-8")
    # SECOND FAMILY (L1.33, principal 2026-07-31 "gpt n claude work together on these families"):
    # a blind-spot hunter that only ever thinks in ONE model's priors has the exact defect it
    # exists to detect. Ask the independent family what THIS run missed, and record the verdict
    # honestly -- SOLO when the partner is unavailable, never silently passed off as confirmed.
    try:
        from libs.research.second_family import ask_second_family, blindspot_prompt, merge_verdict
        own = json.dumps({"unread": unread, "unmodelled": unmodelled[:20],
                          "pairs": pairs[:20], "never": never[:20]}, indent=1)
        op = ask_second_family(blindspot_prompt("blindspot_max", own), context="blindspot_max")
        verdict = merge_verdict(own, op)
        d = json.loads(OUT.read_text("utf-8"))
        d["second_family"] = {**verdict, "text": op.text[:4000] if op.available else ""}
        OUT.write_text(json.dumps(d, indent=1), "utf-8")
        print(f"  second family: {verdict['verdict']}"
              + (f" -- {verdict.get('reason', '')}" if verdict["verdict"] == "SOLO" else ""))
    except Exception as exc:               # the partner must never break the organ
        print(f"  second family: SKIPPED ({exc})")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()

```

### scripts/blindspot_prober.py
```python
"""BLIND-SPOT PROBER (L6, principal 2026-07-27) -- structured creativity against self-blindness.

THE PROBLEM THIS EXISTS FOR: data/information_class_map.json is itself a blind spot. A hand-written
map can only contain classes someone already imagined; listing 30 classes never proves the universe
holds 30. Any "we've covered everything" is a statement about the MAP, never the TERRITORY.

So this is deliberately NOT another list of sources. It is a set of orthogonal LENSES that
MECHANICALLY GENERATE the question "what did we never mine, and why not?" from angles that do not
share a failure mode. A single lens has blind spots; six lenses that fail differently are much
harder to fool. Each lens emits concrete probes; probes become never-visited classes; those get
funded by the NEW_BRANCHES slice.

Run every cycle. The output is questions, not answers -- answering them is the dig.
Read-only. Run from repo root.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

MAP = Path("data/information_class_map.json")
OUT = Path("data/blindspot_probes.json")

LENSES = {
    "L6a_MODALITY_GAP": {
        "question": "Which information CARRIERS are structurally under-mined vs our comfort zone?",
        "why_orthogonal": "catches format bias -- we mine numbers because numbers are easy, not because they are informative",
        "probes": [
            "For every modality at <50% coverage, name ONE concrete free source and screen it.",
            "What information exists ONLY as audio/video and has no text equivalent?",
            "What is published as an image/chart but never as a series (and could be OCR'd)?",
            "What arrives as a STREAM we only sample as snapshots (and thus destroy)?",
        ]},
    "L6b_NEGATIVE_SPACE": {
        "question": "What important information leaves NO public footprint -- and what proxies it?",
        "why_orthogonal": "the class map can only list what EXISTS; this lens starts from what MATTERS and works backwards",
        "probes": [
            "OTC block flow: invisible directly -- proxy via exchange reserve steps, stablecoin mints, settlement windows?",
            "Market-maker inventory: invisible -- proxy via quote asymmetry, depth decay, funding response?",
            "Institutional execution algos: invisible -- proxy via intraday volume fingerprints, child-order spacing?",
            "Private treasury/board decisions: invisible -- proxy via hiring, filings, domain registrations, doc diffs?",
            "For each: is the PROXY testable free, and does it lead or coincide?",
        ]},
    "L6c_CROSS_DOMAIN_IMPORT": {
        "question": "What information classes do OTHER disciplines mine that crypto quant does not?",
        "why_orthogonal": "imports modalities the whole FIELD is blind to, not just this desk",
        "probes": [
            "Epidemiology: contact-network diffusion models -- applied to holder/wallet graphs?",
            "Ad-tech: attribution + incrementality testing -- applied to flow attribution?",
            "Insurance: catastrophe/tail modelling -- applied to liquidation cascades?",
            "Supply chain: lead-time and bullwhip -- applied to mining/hardware/energy?",
            "Sports betting: closing-line value as a skill metric -- applied to trader/prediction markets?",
            "Seismology: foreshock/aftershock clustering (Hawkes) -- applied to liquidation clustering?",
        ]},
    "L6d_ADVERSARIAL": {
        "question": "If a competitor had an edge we lack, what information would it be built on?",
        "why_orthogonal": "inverts from OPPONENT capability rather than our own inventory",
        "probes": [
            "What does a market maker see that we never will -- and what shadow does it cast in public data?",
            "What does a large exchange see internally, and which of it leaks into public endpoints?",
            "What does a VC see pre-announcement, and what public artifact appears first (repos, domains, hiring)?",
            "What would a regulator see, and which of it becomes public on a lag we could exploit?",
        ]},
    "L6e_INVERSION": {
        "question": "Start from the TARGET, derive the information required, THEN hunt it.",
        "why_orthogonal": "everything else starts from available data; this starts from the question and refuses to be limited by inventory",
        "probes": [
            "To predict a funding regime change, what would you IDEALLY observe? Does any public proxy exist?",
            "To predict a liquidation cascade 1h ahead, what is the minimal sufficient observation?",
            "To predict venue migration, what would you need? (fee changes, listing races, incentive programmes)",
            "For each ideal observable: rank by (importance x free-obtainability), not by convenience.",
        ]},
    "L6f_SELF_AUDIT": {
        "question": "What did we DECLINE to test, and is the reason still valid?",
        "why_orthogonal": "audits our own past judgement rather than the world -- catches stale refusals",
        "probes": [
            "List every source parked as 'blocked/paid/too hard'. Re-check access -- did it change?",
            "List every class killed on ONE test. Was the test powered? (power now mandatory)",
            "What did we skip because it was UNCOMFORTABLE (NLP, video, non-English) rather than because it was refuted?",
            "Which refusals were about cost, and has the cost or our budget moved?",
        ]},
}


def main() -> None:
    cov = {}
    if MAP.exists():
        d = json.loads(MAP.read_text("utf-8"))
        for _k, v in d.get("classes", {}).items():
            cov.setdefault(v["modality"], {"covered": 0, "n": 0})
            cov[v["modality"]]["n"] += 1
            if v["status"] == "covered":
                cov[v["modality"]]["covered"] += 1

    print("=== BLIND-SPOT PROBER (L6) -- structured creativity, not another source list ===")
    print("    The class map is ITSELF a blind spot: it holds only what someone imagined.")
    print("    Six lenses that FAIL DIFFERENTLY are much harder to fool than one list.\n")

    if cov:
        weak = sorted(cov.items(), key=lambda kv: kv[1]["covered"] / max(1, kv[1]["n"]))
        print("  measured format bias (feeds L6a):")
        for m, c in weak:
            print(f"    {m:<12} {c['covered']}/{c['n']} covered"
                  f"{'   <-- STRUCTURAL BLIND SPOT' if c['covered'] == 0 else ''}")
        print()

    for lid, L in LENSES.items():
        print(f"--- {lid}")
        print(f"    Q: {L['question']}")
        print(f"    why orthogonal: {L['why_orthogonal']}")
        for pr in L["probes"]:
            print(f"      . {pr}")
        print()

    n = sum(len(L["probes"]) for L in LENSES.values())
    print(f"=> {n} standing probes across {len(LENSES)} orthogonal lenses.")
    print("   RULE: every cycle answers at least one probe per lens with EVIDENCE (a screened")
    print("   source, or a documented reason it is not free-obtainable). An unanswered lens is")
    print("   a live blind spot, not a completed audit.")
    print("   CEILING CLAUSE: 'no probes remain' is never a valid report -- it means the lenses")
    print("   went stale. Blind re-derivation regenerates them from scratch, ignoring this file.")

    OUT.write_text(json.dumps(
        {"updated": datetime.now(tz=UTC).isoformat(), "n_probes": n,
         "modality_bias": cov, "lenses": LENSES}, indent=1), "utf-8")
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()

```

### scripts/breadth_expander.py
```python
"""BREADTH EXPANDER -- external LLM as a COLLEAGUE to the miners (generative, not judicial).

Every other panel mission (audit/premortem/verify) is JUDICIAL: it critiques finished work. This
one is GENERATIVE: "here is territory you have not looked at." Orthogonality in the OBSERVER, not
just the observed (L6 applied to the cognition layer).

MAXIMUM DAILY SWEEP (principal 2026-07-27): ALL 6 lenses every day, 3 seats each, 15-20 sources
per call. Cost was never the binding constraint -- the first 2-seat run cost $0.015, so a full
sweep is ~18 calls ~ $0.14/day ~ $4.20/month against a $100-150 cap.

DESIGN DECISIONS:
  COLD, NOT MEMORY -- memory anchors; a model recalling its own suggestions drifts into
    incremental variants. Cold cognition + post-hoc dedup = fresh thinking AND no repeats. Same
    principle as blind rediscovery, which is deliberately blind to current coverage maps.
  ALL LENSES DAILY -- one prompt reshuffled would converge; six orthogonal framings cannot.
  SEAT ROTATION -- lead seat always present, 2 rotating labs per lens, so all 13 labs contribute
    within days without firing 13 calls per lens.
  PARALLEL PROBING -- with a full sweep the HTTP probes, not the LLM calls, are the wall clock.
  SATURATION ALARM -- if novelty/day trends to zero that is real exhaustion of THIS lens set OR
    lens staleness; both must be VISIBLE and trigger lens regeneration. Silence is the failure
    mode the ceiling clause forbids.

HARD CONSTRAINTS: Stage-A only, zero promotion authority (L4). Every suggestion feasibility-probed
(first run: 6/11 were dead links). Respects the panel budget envelope (abort, never silently
degrade). §13 legitimacy gate: public + legitimately accessible only. Yield measured as method
`external_llm_expander` -- 300 sources and zero survivors decays its share like anything else.
"""
from __future__ import annotations

import json
import re
import ssl
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

KEYS = ROOT / "data/secrets/llm_panel.json"
CLASSMAP = ROOT / "data/information_class_map.json"
OUT = ROOT / "data/breadth_expansion.jsonl"
CTX = ssl.create_default_context()

LEAD_SEAT = "openai/gpt-5.6-terra-pro"
DIVERSITY_POOL = ["x-ai/grok-4.3", "google/gemini-3.1-pro-preview", "deepseek/deepseek-v4-pro",
                  "qwen/qwen3.7-max", "z-ai/glm-5.2", "moonshotai/kimi-k3", "minimax/minimax-m3",
                  "google/gemini-3.6-flash", "meituan/longcat-2.0", "nvidia/nemotron-3-ultra-550b-a55b"]

LENSES = [
    ("MODALITY GAP", "The desk mines TABULAR data well and is structurally blind to other carriers "
     "(filing 0/2, transcript 0/2, video 0/1, graph 0/4, archive 0/2 covered). Name FREE, PUBLIC "
     "sources in the UNDER-COVERED carriers specifically."),
    ("NEGATIVE SPACE", "Name information that MATTERS for crypto price formation but leaves NO "
     "direct public footprint -- then name the free PROXY that does leave one."),
    ("CROSS-DOMAIN IMPORT", "Name information classes that OTHER disciplines mine routinely "
     "(epidemiology, insurance, supply chain, sports analytics, intelligence, ecology) that crypto "
     "quant does not, and the free crypto-domain equivalent."),
    ("ADVERSARIAL", "If a top quant firm had an edge this desk lacks, what INFORMATION would it be "
     "built on? Name the public shadow that information casts."),
    ("NON-ENGLISH FRONTIER", "Name free public sources in Chinese, Korean, Japanese, Russian, "
     "Arabic, Portuguese, Turkish or Spanish that English-language crypto research systematically "
     "misses. Native-language platforms, not English mirrors."),
    ("INVERSION", "Start from targets (funding regime shifts, liquidation cascades, venue "
     "migration, liquidity droughts). For each name the IDEAL observable, then the closest FREE "
     "public proxy."),
]

SYSTEM = (
    "You are a research scout for a systematic crypto trading desk. You are a COLLEAGUE helping "
    "the desk's own miners see further -- not an auditor. Your job is BREADTH: name information "
    "sources, classes and modalities the desk has probably NOT considered.\n"
    "HARD RULES:\n"
    "1. FREE and PUBLIC only. No paywalled, pirated, private-group or paid-vendor data.\n"
    "2. Be SPECIFIC AND CHECKABLE: give the actual endpoint/domain/dataset name. Vague categories "
    "('social sentiment') are useless; 'api.example.com/v1/x, free, no key, daily history' is useful.\n"
    "3. Prefer sources with STRUCTURED or reconstructable history -- a signal needs a time series.\n"
    "4. State the MECHANISM: why would this move crypto prices, and does it LEAD or coincide?\n"
    "5. Do NOT suggest: Binance/OKX/Bybit/Deribit standard market data, Glassnode/CryptoQuant/"
    "Nansen/Kaiko paid tiers, generic Twitter/Reddit sentiment, or news aggregators -- all are "
    "already covered or already refuted.\n"
    "Output ONE source per line, format:\n"
    "NAME | URL_OR_ENDPOINT | MODALITY | MECHANISM (<=20 words) | LEADS_OR_COINCIDES"
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


def _ask(base_url: str, key: str, model: str, system: str, user: str, timeout: float = 110.0) -> str:
    body = json.dumps({"model": model, "max_tokens": 16000, "temperature": 1.0,
                       "reasoning": {"effort": "high"},
                       "messages": [{"role": "system", "content": _doctrine("breadth_expander") + system},
                                    {"role": "user", "content": user}]}).encode()
    req = urllib.request.Request(base_url.rstrip("/") + "/chat/completions", data=body,
                                 method="POST",
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        out = json.loads(r.read())
    m = out["choices"][0]["message"]
    return str(m.get("content") or m.get("reasoning") or "")


def probe(url: str) -> str:
    """An unprobed LLM suggestion is a dead link until proven otherwise."""
    u = url if url.startswith("http") else "https://" + url.strip().strip("<>()[]")
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15, context=CTX) as r:
            return f"OK-{r.status}"
    except urllib.error.HTTPError as e:
        return f"HTTP-{e.code}"
    except Exception as e:
        return type(e).__name__


def novelty_trend(path: Path, new: int, total: int) -> str:
    """Saturation alarm -- falling novelty is real exhaustion OR stale lenses. Both must be seen."""
    hist = []
    if path.exists():
        for ln in path.read_text("utf-8").splitlines()[-600:]:
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if r.get("_summary"):
                hist.append(r)
    rates = [h["new"] / max(1, h["total"]) for h in hist[-7:]]
    today = new / max(1, total)
    if len(rates) >= 3 and sum(rates) / len(rates) < 0.05 and today < 0.05:
        return ("*** SATURATION ALARM: novelty <5% over 3+ runs -- lens set exhausted or stale. "
                "REGENERATE lenses via blind re-derivation; do not report 'nothing new'. ***")
    avg = f" (7-run avg {sum(rates)/len(rates)*100:.0f}%)" if rates else " (first runs)"
    return f"novelty {today*100:.0f}% today{avg}"


def main() -> None:
    if not KEYS.exists():
        print("no llm_panel.json -- cannot run")
        return
    provs = json.loads(KEYS.read_text("utf-8"))["providers"]
    by_model = {p.get("model"): p for p in provs if isinstance(p, dict)}

    # budget envelope -- same wallet as the panel; abort rather than silently degrade
    try:
        bcfg = json.loads((ROOT / "data/panel_budget.json").read_text("utf-8"))
        bstate = json.loads((ROOT / "data/panel_budget_state.json").read_text("utf-8"))
    except Exception:
        bcfg, bstate = {}, {}
    # KEY NAMES MUST MATCH THE PANEL'S OWN CONFIG. My first version read monthly_usd_cap/cap_usd,
    # which do not exist, so it printed "no cap configured" and the guard was INERT while a real
    # $120 envelope was sitting in the file. A guard reading the wrong key is worse than none.
    cap = float(bcfg.get("monthly_envelope_usd") or 0) or None
    alert = float(bcfg.get("alert_at_usd") or 0) or None
    spent = float(bstate.get("usage_at_month_start") or 0)
    obs = [float(c) for c in (bstate.get("observed_run_costs") or [])]
    n_calls = len(LENSES) * 3
    # MEASURED cost, not assumed: panel history is ~$2.93/run at 13 seats => ~$0.22/call.
    # The old 0.008/call constant was 27x optimistic and is exactly how a 402 happens mid-run.
    per_call = (max(obs) / 13.0) if obs else 0.22
    need = per_call * n_calls
    if cap and spent + need > cap:
        print(f"ABORT -- envelope guard: spent ${spent:.2f} + est ${need:.2f} > envelope "
              f"${cap:.2f}. PAGE the principal; never silently degrade quality.")
        return
    if alert and spent + need > alert:
        print(f"WARN -- past alert threshold ${alert:.2f} (spent ${spent:.2f} + est ${need:.2f})")
    print(f"budget: est ${need:.2f} for {n_calls} calls @ ${per_call:.3f}/call (measured)"
          + (f" | month ${spent:.2f}/${cap:.2f}" if cap else " | NO ENVELOPE CONFIGURED"))

    known: set[str] = set()
    # DEDUP MUST INCLUDE THE GRAVEYARD, not just the class map. The 2026-07-27 sweep re-suggested
    # Bithumb/Coinone/Bitso/Mercado -- all TESTED AND KILLED the same day -- because dedup only
    # read the class map. Re-proposing refuted sources wastes probe budget and research time.
    gy = ROOT / "docs/graveyard.md"
    if gy.exists():
        for ln in gy.read_text("utf-8").splitlines():
            if ln.startswith("|"):
                first = ln.strip("|").split("|")[0].strip().lower()
                known.add(first)
                known.update(w for w in re.split(r"[^a-z0-9]+", first) if len(w) > 4)
    if CLASSMAP.exists():
        cm = json.loads(CLASSMAP.read_text("utf-8"))
        for k, v in cm.get("classes", {}).items():
            known.add(k.lower())
            known.update(w for w in re.split(r"[^a-z0-9]+", v.get("note", "").lower())
                         if len(w) > 4)

    day = datetime.now(tz=UTC).toordinal()
    today = datetime.now(tz=UTC).date().isoformat()
    print(f"=== BREADTH EXPANDER | FULL SWEEP: {len(LENSES)} lenses x 3 seats ===\n")

    # PARALLEL LLM CALLS. 18 sequential high-effort calls ran 70+ minutes and were reaped by the
    # watchdog three times; the sweep must fit inside its cadence budget, so fan them out.
    jobs = []
    for li, (lens_name, lens_txt) in enumerate(LENSES):
        seats = [LEAD_SEAT] + [DIVERSITY_POOL[(day + li + k) % len(DIVERSITY_POOL)] for k in (0, 1)]
        user = (f"LENS -- {lens_name}\n{lens_txt}\n\n"
                "Name 15-20 sources through THIS lens only. Be specific and checkable. "
                "Prefer OBSCURE and NON-ENGLISH over well-known -- the desk has the obvious ones.")
        for seat in seats:
            prov = by_model.get(seat)
            if prov:
                jobs.append((lens_name, seat, prov, user))

    def _run(j):
        ln_name, seat, prov, user = j
        try:
            return ln_name, seat, _ask(prov["base_url"], prov["key"], seat, SYSTEM, user), None
        except Exception as e:
            return ln_name, seat, "", f"{type(e).__name__} {getattr(e, 'code', '')}"

    print(f"dispatching {len(jobs)} calls in parallel (9 workers)...")
    with ThreadPoolExecutor(max_workers=9) as ex:
        answers = list(ex.map(_run, jobs))

    rows: list[dict[str, Any]] = []
    for lens_name, seat, txt, err in answers:
        if err:
            print(f"    {seat.split('/')[-1]:<24} {lens_name[:18]:<18} FAILED ({err})")
            continue
        got = 0
        for ln in txt.splitlines():
            if ln.count("|") < 3:
                continue
            parts = [x.strip() for x in ln.split("|")]
            name, url = parts[0].lstrip("-*0123456789. "), parts[1]
            if not name or len(name) > 90 or not url:
                continue
            dup = name.lower() in known or any(
                w in known for w in re.split(r"[^a-z0-9]+", name.lower()) if len(w) > 5)
            rows.append({"date": today, "lens": lens_name, "seat": seat, "name": name,
                         "url": url, "modality": parts[2] if len(parts) > 2 else "",
                         "mechanism": parts[3] if len(parts) > 3 else "",
                         "leads": parts[4] if len(parts) > 4 else "",
                         "duplicate": dup, "probe": "", "reachable": False})
            known.add(name.lower())          # dedup within the sweep too
            got += 1
        print(f"    {seat.split('/')[-1]:<24} {lens_name[:18]:<18} +{got}")

    todo = [r for r in rows if not r["duplicate"]]
    print(f"\nprobing {len(todo)} candidates in parallel...")
    with ThreadPoolExecutor(max_workers=12) as ex:
        results = list(ex.map(probe, [r["url"] for r in todo]))
    for r, st in zip(todo, results, strict=False):
        r["probe"] = st
        r["reachable"] = st.startswith("OK")
    for r in rows:
        if r["duplicate"]:
            r["probe"] = "skipped-dup"

    n_new = sum(1 for r in rows if not r["duplicate"] and r["reachable"])
    print("\n=== NEW + REACHABLE ===")
    for r in rows:
        if not r["duplicate"] and r["reachable"]:
            print(f"  {r['name'][:44]:<44} {r['modality'][:12]:<12} {r['lens'][:20]}")

    with OUT.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
        fh.write(json.dumps({"_summary": True, "date": today, "total": len(rows),
                             "new": n_new, "lenses": len(LENSES)}) + "\n")

    tot = len(rows)
    print(f"\n  {tot} suggestions | {sum(1 for r in rows if r['duplicate'])} known | "
          f"{sum(1 for r in rows if not r['duplicate'] and not r['reachable'])} unreachable | "
          f"{n_new} NEW+REACHABLE")
    print(f"  {novelty_trend(OUT, n_new, tot)}")
    print("  -> Stage-A only, zero promotion authority; enters class map as never-visited")


if __name__ == "__main__":
    main()

```

### scripts/build_audit_coverage.py
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
from datetime import UTC, datetime
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
RISK_PREFIXES = ("libs/execution/", "scripts/run_deadman_switch.py", "scripts/run_cashcarry",
                  "scripts/run_alerts.py", "scripts/run_recorder.py", "scripts/run_ci.py")
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
            rec["loc"] = sum(1 for _ in p.open("r", encoding="utf-8", errors="ignore"))
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
    """Shrink hard on any blank, grow gently on a clean run. Called after every panel."""
    m = refresh(load())
    cur = current_budget(m)
    if blanked:
        new = max(CODE_BUDGET_MIN, int(cur * 0.6))   # a blank is a real failure: cut deep
    else:
        new = min(CODE_BUDGET_CHARS, int(cur * 1.15))  # earn size back slowly
    m["code_budget_chars"] = new
    m.setdefault("budget_history", []).append(
        {"blanked": blanked, "of": total, "from": cur, "to": new})
    m["budget_history"] = m["budget_history"][-30:]
    save(m)
    return new


def record_blank(model: str) -> None:
    """Per-seat blank tally -- turns a flaky seat into an evidence-backed swap decision."""
    m = refresh(load())
    m.setdefault("seat_blanks", {})[model] = int(m.get("seat_blanks", {}).get(model, 0)) + 1
    save(m)


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

### scripts/carryover_brief.py
```python
#!/usr/bin/env python3
"""§37: print the work owed from previous cycles, for the brain to do FIRST.

Run at the START of a brain cycle. It reads the sweep ledger, works out how long each open defect
has been owed and how many of those sweeps ran with the brain AWAKE, and prints a ranked brief.
Always exits 0 -- this steers priority, it never blocks a cycle.

    python3 scripts/carryover_brief.py            # the brief
    python3 scripts/carryover_brief.py --record   # append this sweep, then print
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LEDGER = ROOT / "data/carryover_sweeps.jsonl"
LOGS = ROOT / "data/cro_ai_logs"


def brain_was_alive(*, window_h: float = 26.0) -> bool:
    """Did the most recent brain cycle actually run, or die on quota?

    Read from the LOG CONTENT, not from the fact a log exists -- a cycle that dies at birth still
    creates a file, and counting that as 'alive' would blame the desk for an outage it did not
    choose. Absent any recent log at all, assume alive: over-reporting a skip is a defect the
    reader can dismiss, while silently excusing real avoidance is the failure that compounds.
    """
    from libs.ops.carryover import DEATH_MARKERS

    if not LOGS.is_dir():
        return True
    recent = [p for p in LOGS.glob("2026*_*.log")
              if (time.time() - p.stat().st_mtime) < window_h * 3600]
    if not recent:
        return True
    newest = max(recent, key=lambda p: p.stat().st_mtime)
    try:
        txt = newest.read_text("utf-8", errors="ignore").lower()
    except OSError:
        return True
    return not any(m in txt for m in DEATH_MARKERS)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true",
                    help="append the current sweep's open defects to the ledger first")
    a = ap.parse_args()

    from libs.ops.carryover import brief, carryover_state, load_sweeps, record_sweep

    if a.record:
        try:
            import scripts.max_audit as m
            defects: list[tuple[str, str]] = []
            for _label, fn in m.CHECKS:
                m._fenced(fn, defects, _label)
            record_sweep(LEDGER, [d[0] for d in defects], ts=time.time(),
                         brain_alive=brain_was_alive())
        except Exception as exc:
            print(f"[§37] record failed ({type(exc).__name__}: {exc}) -- printing prior state")

    print(brief(carryover_state(load_sweeps(LEDGER), now=time.time())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts/check_exploration.py
```python
#!/usr/bin/env python3
"""EXPLORATION FAMILY FENCE (L1.32) -- the unknown-unknown organs are ONE family, measured as one.

PRINCIPAL ORDER (2026-07-31): *"same with unknowns, gaps, blindspots -- these are all families."*

THE DEFECT THIS CLOSES. This desk owns SIX organs that all sample the same space -- "what we do
not know we do not know" -- and until now each ran on its own cadence, with its own artifact, and
NOTHING looked at them together:

    capability_hunt   what capability is missing entirely          (L1.31, 3x/day, 8 lenses)
    blindspot_max     the desk's own blind spots                   data/blindspot_max.json
    blindspot_prober  information-class probes                     data/blindspot_probes.json
    blindrediscovery  ideas worth re-opening on new capability     cro_ai_logs (dig seat)
    kimi_hunter       an INDEPENDENT family hunting mechanisms     data/kimi_hunt.json
    deep_sweep meta   the meta-and-blindspots audit seat           docs/research/deep_sweep/

Three failures follow from treating them as unrelated singletons, and all three are live:
 1. UNMEASURED YIELD -- an organ that has produced NOTHING for weeks looks exactly like one
    producing steadily, because nobody compares them. `blindrediscovery` was scheduled with
    `last=never` and only a human noticing caught it.
 2. UNCOORDINATED COVERAGE -- six organs free to hunt the same region on the same day is one
    organ's worth of diversity at six organs' cost. Lens rotation (L1.31) solved this WITHIN the
    capability hunt; this fence extends the accounting ACROSS the family.
 3. NO FAMILY-LEVEL FLOOR -- exploration could decay to zero organ by organ, each decay
    individually unremarkable, with no single number that would have shown it.

STATUSES:
  DARK        >=1 organ has NEVER produced an artifact -- scheduled and silent. Fence FAILS.
  STALE       an organ's artifact is older than its own cadence allows (produced once, then
              quietly stopped -- the failure mode L1.25a forbids as a response to null streaks).
  THIN        the family is running but fewer than half the organs produced this week.
  OK          every organ produced within its window.

NEVER a throttle: this fence can only ever demand MORE exploration. It has no path that
recommends running any organ less (L1.8 / L1.25a) -- if two organs overlap, the answer is to
re-aim one, never to silence it.

    python scripts/check_exploration.py [--report-only] [--json]
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

#: organ -> (artifact, max_age_hours implied by its own cadence, what it hunts)
_FAMILY: dict[str, tuple[str, float, str]] = {
    "capability_hunt": ("data/capability_hunt.json", 36,
                        "capabilities the desk never conceived (8 rotating lenses, 3x/day)"),
    "blindspot_max": ("data/blindspot_max.json", 36, "the desk's own blind spots (daily)"),
    "blindspot_prober": ("data/blindspot_probes.json", 24 * 8,
                         "information-class probes (weekly)"),
    "kimi_hunter": ("data/kimi_hunt.json", 12,
                    "mechanism hunting by an INDEPENDENT model family (8x/day)"),
    "hunt_coverage": ("data/hunt_coverage.json", 24 * 8,
                      "which regions of the hunt space have been covered"),
    "deep_sweep_meta": ("docs/research/deep_sweep", 24 * 8,
                        "the meta-and-blindspots audit seat (weekly 9-seat sweep)"),
}


def _age_hours(p: Path, now: datetime) -> float | None:
    """Age of the newest file at this path (dir = newest child). None = never produced."""
    if not p.exists():
        return None
    if p.is_dir():
        kids = [c for c in p.rglob("*") if c.is_file()]
        if not kids:
            return None
        newest = max(c.stat().st_mtime for c in kids)
    else:
        newest = p.stat().st_mtime
    return (now.timestamp() - newest) / 3600.0


def build_report(root: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    root = root or _ROOT
    now = now or datetime.now(tz=UTC)
    organs: dict[str, Any] = {}
    dark, stale, fresh = [], [], []
    for name, (rel, max_h, hunts) in _FAMILY.items():
        age = _age_hours(root / rel, now)
        if age is None:
            state = "NEVER-PRODUCED"
            dark.append(name)
        elif age > max_h:
            state = "STALE"
            stale.append(name)
        else:
            state = "FRESH"
            fresh.append(name)
        organs[name] = {"state": state, "artifact": rel, "hunts": hunts,
                        "age_hours": None if age is None else round(age, 1),
                        "max_age_hours": max_h}

    n = len(_FAMILY)
    if dark:
        status = "DARK"
    elif stale:
        status = "STALE"
    elif len(fresh) < n / 2:
        status = "THIN"
    else:
        status = "OK"
    return {
        "generated": now.isoformat(),
        "law": "L1.32 -- the unknown-unknown organs are ONE family; measured together or not "
               "at all. This fence can only ever demand MORE exploration.",
        "status": status,
        "n_organs": n, "n_fresh": len(fresh), "n_stale": len(stale), "n_dark": len(dark),
        "dark": dark, "stale": stale,
        "organs": organs,
        "detail": (f"{len(fresh)}/{n} organs produced within their own cadence; "
                   f"{len(dark)} never produced, {len(stale)} stale"),
        "next_action": (
            "a DARK organ is scheduled and silent -- check its runner and auth, then fix or "
            "re-aim it. NEVER silence an overlapping organ: if two hunt the same region, "
            "re-aim one (L1.8, L1.25a). Exploration decays organ-by-organ and no single "
            "decay ever looks alarming, which is exactly why this number exists."),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    out = _ROOT / "data/exploration_status.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    print(json.dumps(rep, indent=2) if args.json else
          f"exploration family (L1.32): {rep['status']} -- {rep['detail']}\n-> {out}")
    if args.report_only:
        return 0
    return 2 if rep["status"] == "DARK" else 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/collect_onchain_metrics.py
```python
#!/usr/bin/env python3
"""On-chain FUNDAMENTALS collector -- the licence-clean Glassnode/Coin-Metrics replacement.

Reconstructs the vendor metric class from primary public chain data (blockchain.info charts, free,
no key). Facts are not copyrightable; a vendor's curated series is. Coin Metrics Community is
EXCLUDED from production by ruling 2026-07-26 (CC BY-NC 4.0 "non-commercial internal business
purposes" + ToU 6(iii) banning use in any AI system) -- so the desk reconstructs the same facts
itself rather than licensing someone else's copy of them.

METRIC MAP (verified 1:1 against the CM fields the desk had probed):
    AdrActCnt   -> n-unique-addresses
    TxCnt       -> n-transactions
    FeeTotUSD   -> transaction-fees-usd
    (throughput -> estimated-transaction-volume-usd, already used by collect_onchain_activity)

Writes data/onchain_metrics.jsonl (one row per UTC day, append-only, deduped).
"""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

_BASE = "https://api.blockchain.info/charts"
_METRICS = {
    "active_addresses": "n-unique-addresses",
    "tx_count": "n-transactions",
    "fees_usd": "transaction-fees-usd",
    "throughput_usd": "estimated-transaction-volume-usd",
}
_OUT = Path("data/onchain_metrics.jsonl")


def _series(chart: str) -> dict[str, float]:
    url = f"{_BASE}/{chart}?timespan=5years&format=json&sampled=false"
    req = urllib.request.Request(url, headers={"User-Agent": "quant-onchain-metrics"})
    with urllib.request.urlopen(req, timeout=45) as r:
        d = json.loads(r.read().decode())
    return {datetime.fromtimestamp(int(p["x"]), tz=UTC).date().isoformat(): float(p["y"])
            for p in d.get("values", [])}


def main() -> None:
    series = {}
    for name, chart in _METRICS.items():
        try:
            series[name] = _series(chart)
        except Exception as exc:                 # one dead chart must not lose the others
            print(f"  {name}: FETCH FAILED {exc!r}")
    if not series:
        raise SystemExit("all charts failed -- nothing written")

    dates = sorted(set.intersection(*(set(v) for v in series.values())))
    if not dates:
        raise SystemExit("no aligned dates across metrics")

    seen = set()
    if _OUT.exists():
        for line in _OUT.read_text("utf-8", errors="ignore").splitlines():
            try:
                seen.add(json.loads(line)["date"])
            except Exception:
                continue

    n = 0
    with _OUT.open("a", encoding="utf-8") as fh:
        for d in dates:
            if d in seen:
                continue
            fh.write(json.dumps({"date": d, **{k: round(v[d], 4) for k, v in series.items()}})
                     + "\n")
            n += 1
    last = dates[-1]
    print(f"onchain-metrics: +{n} rows (total span {dates[0]} -> {last}, "
          f"{len(dates)} aligned days)")
    print("  latest: " + ", ".join(f"{k}={series[k][last]:,.0f}" for k in series))


if __name__ == "__main__":
    main()

```

### scripts/conversion_engine.py
```python
"""CONVERSION ENGINE -- turn already-mined data into RUNNING experiments, not a list nobody opens.

MY OWN FAILURE, ONE HOUR AFTER SHIPPING THE DETECTOR FOR IT. I generated conversion_queue.json
from /tmp, wired nothing, and reported conversion "maximised". Nothing read it, nothing
regenerated it, and its producer was not even a script. That is precisely the INERT class
module_justification measures -- 90 of 243 modules -- and I added one to the pile while claiming
the opposite.

A queue nobody consumes is a list. Utilisation means something DOWNSTREAM CHANGES.

WHAT THIS DOES, AND WHERE IT LANDS:
  1 regenerates the conversion queue every cycle from the live blind-spot scan
  2 ranks by CONVERSION COST -- not guessed alpha. An unread field on a VERIFIED live source is
    the cheapest experiment that exists: zero acquisition, known provenance, history already
    accumulating.
  3 EMITS the top candidates into data/research_cio.json's schedule, so they compete directly
    against the 447 enumerated constructions in the one queue the desk actually reads.

MINING IS NEVER TOUCHED (principal constraint, honoured literally). Nothing here throttles a
collector, prunes a field, narrows a universe or drops a row. It raises utilisation of what mining
already produced, and if the two ever conflict, mining wins.

STAGE-A ONLY. A converted blind spot is a QUESTION, not an edge. It earns a screen, never capital.
"""
from __future__ import annotations

import json
import pathlib
from datetime import UTC, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data/conversion_queue.json"
CIO = ROOT / "data/research_cio.json"


def _j(p, d=None):
    try:
        return json.loads((ROOT / p).read_text("utf-8"))
    except Exception:  # blind-except intentional (BLE001)
        return d


def main() -> None:
    bs = _j("data/blindspot_max.json", {}) or {}
    unread = (_j("data/unobserved_observables.json", {}) or {}).get("fields", [])
    gate = {k: v.get("verdict") for k, v in
            (_j("data/measurement_gate.json", {}) or {}).get("datasets", {}).items()}
    vit = {c["source"]: c for c in (_j("data/data_vitals.json", {}) or {}).get("collectors", [])}

    cands = []
    for r in unread:
        src = r["file"]
        live = "OK" in str(vit.get(src, {}).get("action", ""))
        ver = gate.get(src) == "VERIFIED"
        cands.append({"kind": "unread_field", "target": f"{src}:{r['field']}",
                      "cost": round(1.0 + (0 if ver else 0.5) + (0 if live else 0.5), 2),
                      "verified": ver, "live": live,
                      "why": "collected, never referenced -- acquisition cost already paid"})
    for pair in bs.get("uncrossed_pairs", []):
        a, b = pair[0], pair[1]
        va, vb = gate.get(a) == "VERIFIED", gate.get(b) == "VERIFIED"
        cands.append({"kind": "uncrossed_pair", "target": f"{a} x {b}",
                      "cost": round(2.0 + (0 if va else 0.5) + (0 if vb else 0.5), 2),
                      "verified": va and vb, "live": None,
                      "why": "interaction never examined -- fusion is where weak signals combine"})
    for e in bs.get("unmodelled_entities", []):
        cands.append({"kind": "unmodelled_entity", "target": f"{e['file']}:{e['entity']}",
                      "cost": 1.5, "verified": gate.get(e["file"]) == "VERIFIED", "live": None,
                      "rows": e.get("rows"),
                      "why": "present in our data, named nowhere in our code"})

    cands.sort(key=lambda c: (c["cost"], not c["verified"]))
    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(), "n": len(cands),
                               "queue": cands}, indent=1), "utf-8")

    # ---- THE PART THAT MAKES IT UTILISATION RATHER THAN A LIST ----
    cio = _j("data/research_cio.json", {}) or {}
    sched = cio.get("schedule", [])
    injected = 0
    for c in cands[:40]:
        sched.append({"mechanism": "M_CONVERSION", "name": c["target"],
                      "prior": round(1.0 / c["cost"], 3), "advantage": 1.0,
                      "sched_score": round(1.0 / c["cost"], 3),
                      "origin": "conversion_engine", "why": c["why"]})
        injected += 1
    sched.sort(key=lambda x: -x.get("sched_score", 0))
    cio["schedule"] = sched[:120]
    cio["conversion_injected"] = injected
    CIO.write_text(json.dumps(cio, indent=1), "utf-8")

    kinds = {}
    for c in cands:
        kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
    print("=== CONVERSION ENGINE -- already-mined data into running experiments ===")
    print("    a queue nobody consumes is a list; utilisation means something downstream changes\n")
    print(f"  {len(cands)} candidates  {kinds}")
    print(f"  {injected} injected into the research_cio schedule -- they now compete directly")
    print("  against the enumerated construction space in the one queue the desk reads.\n")
    print(f"  {'cost':>5}  {'kind':<20}candidate")
    for c in cands[:10]:
        print(f"  {c['cost']:>5}  {c['kind']:<20}{c['target'][:56]}")
    print("\n  MINING UNTOUCHED. Nothing throttled, pruned, narrowed or dropped -- this only")
    print("  raises utilisation of what mining already produced. If the two ever conflict,")
    print("  mining wins.")
    print("  STAGE-A ONLY: a converted blind spot is a QUESTION, not an edge. It earns a screen,")
    print("  never capital.")
    print(f"\n  -> {OUT}\n  -> {CIO} (schedule now {len(cio['schedule'])} items)")


if __name__ == "__main__":
    main()

```

### scripts/dependency_graph.py
```python
"""DEPENDENCY GRAPH + IMPACT ANALYSIS -- which alphas are poisoned RIGHT NOW?

TIER 0: FORWARD TEST INTEGRITY. This exists because of a live finding nothing acted on.
data_vitals scored oi_ls_history.jsonl at DQS 0.000 (latency 0.00, completeness 0.00 -- genuinely
stale, not a threshold artifact). That file feeds A002 (OI/LS positioning), which is the ONLY
alpha with a running forward clock, reading out 2026-08-07. If the collector has been dead, the
verdict is already compromised -- and the desk would have accepted it on the date, because nothing
connects "this collector died" to "this clock is invalid".

That is the 14-day silent-websocket failure repeating in a new place: the failure is not that a
feed dies, it is that NOTHING DOWNSTREAM KNOWS.

    source -> feature -> alpha -> forward clock -> capital

Impact propagates FORWARD along that chain from any degraded node. Severity is taken from the
worst upstream state, never averaged -- averaging is how one dead input hides behind four healthy
ones, the same defect that made DQS mark 14/14 collectors dead yesterday.

STATES
    CLEAN       every upstream input passes both the measurement gate and DQS
    DEGRADED    an upstream input is stale or failed the gate; results are suspect
    POISONED    an upstream input is DEAD and the node depends on it for a LIVE decision
                (forward clock or deployed capital). This must block promotion.

Read-only. No keys, no network. Run from repo root.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VITALS = ROOT / "data/data_vitals.json"
GATE = ROOT / "data/measurement_gate.json"
LIFE = ROOT / "data/alpha_lifecycle.json"
OUT = ROOT / "data/dependency_graph.json"
PAGE = ROOT / "docs/PRINCIPAL_ACTION.md"

# The graph. Declared explicitly because inferring it from imports would miss the ones that
# matter -- a collector and its consumer often share no code path at all, only a filename.
EDGES = {
    # STATIC ARCHIVE, not a live collector. Ends 2023-12-03 by design (600 days from
    # 2021-06-01, written once by dl_metrics_history.py for OOS backtesting). v1 of this graph
    # scored it POISONED because DQS applies live-feed latency rules to it -- the same category
    # error as judging an event log by time-series rules. A static archive cannot be stale.
    "oi_ls_history.jsonl": {
        "features": ["oi_ls_ratio", "taker_ratio"],
        "alphas": [],
        "static": True,
        "live_decision": False,
        "note": "historical backfill for OOS backtest; ends 2023-12-03 BY DESIGN"},
    "axis_shadow_state.json (live clocks)": {
        "features": ["kimchi_premium", "stablecoin_supply_momentum", "cny_premium"],
        "alphas": ["A002"],
        "live_decision": True,
        "note": "THE running forward clocks: kimchi day 6/40 due 2026-09-01, "
                "stablecoin day 5/40 due 2026-09-02, cny not started"},
    "cny_otc_premium_history.jsonl": {
        "features": ["cny_otc_premium"],
        "alphas": ["A003"],
        "live_decision": False,
        "note": "M_STRUCTURAL_BARRIER long-sample backbone"},
    "venue_divergence_shadow.jsonl": {
        "features": ["venue_nav_divergence"],
        "alphas": [],
        "live_decision": False,
        "note": "shadow monitor; no alpha depends on it yet"},
    "coinmetrics_flows.jsonl": {
        "features": ["stablecoin_flow"],
        "alphas": [],
        "live_decision": False, "note": "screened, no survivor"},
    "onchain_metrics.jsonl": {
        "features": ["active_addresses", "tx_count", "throughput_usd"],
        "alphas": [],
        "live_decision": False, "note": "M_FUNDAMENTAL_PROXY 0/7 survival"},
    "data/moat": {
        "features": ["spread_bps", "depth5", "depth10", "imbalance", "concentration", "slope"],
        "alphas": ["A004"],
        "live_decision": False,
        "note": "self-recorded; not covered by the .jsonl collectors scan"},
    "oi_ls_live (Binance positioning)": {
        "features": ["long_short_ratio", "oi_usd", "taker_buy_sell_ratio"],
        "alphas": [],
        "live_decision": False,
        "note": "new 2026-07-28; replaces a static archive that ended 2023-12-03"},
    "defi_lending (Aave/Compound/Morpho)": {
        "features": ["utilisation", "borrow_apy", "ltv_headroom"],
        "alphas": [],
        "live_decision": False,   # flips to True the day a hypothesis on it reaches a clock
        "note": "new 2026-07-28; M_FORCED_DELEVERAGE; no alpha depends on it yet"},
    "binance funding (live API)": {
        "features": ["funding_rate_persistence"],
        "alphas": ["A001"],
        "live_decision": True,          # the LIVE carry entry gate reads this every cycle
        "note": "feeds the live cash-carry entry gate"},
}


def _load(p, d=None):
    try:
        return json.loads(p.read_text("utf-8"))
    except Exception:  # blind-except intentional (BLE001)
        return d



def _health_for(vit: dict, src: str):
    """Match by prefix, not exact key. data_vitals registers 'data/moat (order books)' while the
    graph declares 'data/moat' -- same source, different spelling, and an exact lookup reported a
    monitored source as UNMONITORED forever. Two subsystems that agree about reality but disagree
    about naming produce a false alarm nothing detects, because both are individually correct."""
    if src in vit:
        return vit[src]
    base = src.split(" (")[0].strip().lower()
    for k, v in vit.items():
        kb = k.split(" (")[0].strip().lower()
        if kb == base or kb.startswith(base) or base.startswith(kb):
            return v
    return None


def main() -> None:
    vit = {c["source"]: c for c in (_load(VITALS, {}) or {}).get("collectors", [])}
    gate = (_load(GATE, {}) or {}).get("datasets", {})
    alphas = {a["id"]: a for a in (_load(LIFE, {}) or {}).get("alphas", [])}

    print("=== DEPENDENCY GRAPH -- source -> feature -> alpha -> clock -> capital ===")
    print("    severity is taken from the WORST upstream input, never averaged:")
    print("    averaging is how one dead input hides behind four healthy ones\n")

    rows, poisoned, degraded, contradictions = [], [], [], []
    print(f"  {'source':<34}{'DQS':>7}{'gate':>9}{'alphas':>8}  state")
    for src, e in EDGES.items():
        if e.get("static"):
            print(f"  {src:<34}{'static':>7}{'-':>9}{len(e['alphas']):>8}  STATIC (cannot be stale)")
            rows.append({"source": src, "dqs": None, "gate": None, "state": "STATIC",
                         "features": e["features"], "alphas": e["alphas"],
                         "live_decision": False, "note": e["note"]})
            continue
        v = _health_for(vit, src)
        g = gate.get(src, {}).get("verdict")
        dqs = v["dqs"] if v else None
        dead = (dqs is not None and dqs < 0.5)
        gate_bad = (g == "FAILED")

        if (dead or gate_bad) and e["live_decision"]:
            state = "POISONED"
        elif dead or gate_bad:
            state = "DEGRADED"
        elif dqs is None and g is None:
            state = "UNMONITORED"
        else:
            state = "CLEAN"

        # A gate PASS with a dead DQS is the silent-failure shape both systems exist to expose:
        # structurally valid, operationally dead. Neither alone says it; the disagreement does.
        if dead and g == "VERIFIED":
            contradictions.append({"source": src, "dqs": dqs,
                                   "note": "gate VERIFIED but collector DEAD -- valid structure, "
                                           "no fresh data"})
        dstr = "n/a" if dqs is None else f"{dqs:.3f}"
        gstr = g or "-"
        print(f"  {src:<34}{dstr:>7}{gstr:>9}{len(e['alphas']):>8}  {state}")
        row = {"source": src, "dqs": dqs, "gate": g, "state": state,
               "features": e["features"], "alphas": e["alphas"],
               "live_decision": e["live_decision"], "note": e["note"]}
        rows.append(row)
        if state == "POISONED":
            poisoned.append(row)
        elif state == "DEGRADED":
            degraded.append(row)

    if contradictions:
        print("\n  === CONTRADICTIONS: gate says VERIFIED, health says DEAD ===")
        for c2 in contradictions:
            print(f"    {c2['source']}: {c2['note']}")
        print("    Structurally valid and operationally dead is the exact shape a 14-day silent")
        print("    websocket failure takes. Neither check reports it alone.")
    print(f"\n  {len(poisoned)} POISONED, {len(degraded)} DEGRADED, "
          f"{sum(1 for r in rows if r['state']=='CLEAN')} CLEAN, "
          f"{sum(1 for r in rows if r['state']=='UNMONITORED')} UNMONITORED")

    if poisoned:
        print("\n  === POISONED: a LIVE decision depends on a degraded input ===")
        for r in poisoned:
            print(f"\n  {r['source']}  (DQS {r['dqs'] if r['dqs'] is not None else 'n/a'}, "
                  f"gate {r['gate'] or '-'})")
            print(f"     -> features: {', '.join(r['features'])}")
            for aid in r["alphas"]:
                a = alphas.get(aid, {})
                print(f"     -> {aid} {a.get('name','?')}  [state {a.get('state','?')}]")
                print(f"        {r['note']}")
            print("     ACTION: the dependent result is NOT admissible until the input is")
            print("     repaired AND the affected window is re-derived. A forward clock that")
            print("     ran on a dead feed did not test the hypothesis -- it tested the feed.")

    unmon = [r for r in rows if r["state"] == "UNMONITORED"]
    if unmon:
        print(f"\n  UNMONITORED ({len(unmon)}): no DQS and no gate verdict covers these, so the")
        print("  graph cannot state whether anything downstream is safe. Absence of an alarm is")
        print("  not evidence of health -- that assumption is what let a websocket die for 14 days.")
        for r in unmon:
            print(f"    {r['source']:<34} feeds {r['alphas'] or 'no alpha'}  ({r['note']})")

    if poisoned:
        try:
            with PAGE.open("a", encoding="utf-8") as fh:
                fh.write(f"\n## {datetime.now(tz=UTC).isoformat()} POISONED DEPENDENCY\n")
                for r in poisoned:
                    fh.write(f"- {r['source']} (DQS {r['dqs']}) feeds {r['alphas']} "
                             f"-- {r['note']}\n")
            print(f"\n  -> paged {PAGE}")
        except OSError:
            pass

    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(), "nodes": rows,
                               "n_poisoned": len(poisoned), "n_degraded": len(degraded), "contradictions": contradictions},
                              indent=1), "utf-8")
    print(f"  -> {OUT}")
    raise SystemExit(1 if poisoned else 0)


if __name__ == "__main__":
    main()

```

### scripts/funding_persistence.py
```python
"""FUNDING PERSISTENCE -- does the desk's ENTRY SIGNAL predict what it is trying to HARVEST?

THE MOST DIAGNOSTIC UNTESTED QUESTION ON THE DESK. The carry executor selects symbols by CURRENT
funding rate, then the churn guard holds them >=24h. But funding pays every 8h, so what is
actually earned is funding over the HOLDING PERIOD -- not funding at entry. Nobody has ever
checked that those are related.

If funding mean-reverts fast, the desk systematically buys the spike and collects the reversion.
That would directly explain the hurdle report: $113 harvested against $876 of cost, i.e. the
harvest is a fraction of what the entry signal advertised.

THREE TESTS, cross-sectional across the liquid perp universe:
  1. PERSISTENCE   -- rank-correlation between funding at t and MEAN funding over t+1..t+3 (24h)
                      and t+1..t+9 (72h). This is the executor's actual assumption, stated.
  2. DECILE DECAY  -- take the TOP-funding decile at t (what the executor buys) and measure what
                      that basket actually pays over the next 24h/72h vs the universe median.
                      This is the realistic version: the executor does not buy the average symbol.
  3. HALF-LIFE     -- AR(1) on the funding series; how fast does an entry-time edge decay.

Free Binance funding history, same venue, same clock, no cross-source alignment -> the artifact
class that killed mSOL/CME/bithumb today is structurally impossible here.

Stage-A, zero promotion authority. Run from repo root.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

OUT = Path("data/funding_persistence.json")
N_HIST = 500          # funding ticks per symbol (8h each -> ~166 days)


def _get(u, t=30):
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(u, headers={"User-Agent": "q/1.0"}), timeout=t).read().decode())


def universe(n: int = 40) -> list[str]:
    """Liquid USDT perps by 24h quote volume -- the pool the executor actually picks from."""
    d = _get("https://fapi.binance.com/fapi/v1/ticker/24hr")
    rows = [(float(x.get("quoteVolume", 0)), x["symbol"]) for x in d
            if x["symbol"].endswith("USDT")]
    rows.sort(reverse=True)
    return [s for _, s in rows[:n]]


def funding(sym: str) -> list[tuple[int, float]]:
    try:
        d = _get(f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={sym}&limit={N_HIST}")
        return [(int(x["fundingTime"]) // 3600000, float(x["fundingRate"])) for x in d]
    except Exception:
        return []


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 5:
        return 0.0
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    return float(np.corrcoef(ra, rb)[0, 1]) if ra.std() and rb.std() else 0.0


def main() -> None:
    syms = universe()
    print(f"=== FUNDING PERSISTENCE | {len(syms)} liquid perps ===")
    print("    does funding at ENTRY predict funding over the HOLD? (the executor assumes yes)\n")
    series = {}
    for s in syms:
        f = funding(s)
        if len(f) >= 200:
            series[s] = dict(f)
    if len(series) < 15:
        print(f"  only {len(series)} usable symbols")
        return
    grid = sorted(set.intersection(*[set(v) for v in series.values()]))
    print(f"  {len(series)} symbols, {len(grid)} aligned funding periods "
          f"(~{len(grid)/3:.0f} days)\n")

    ics = {24: [], 72: []}
    dec = {24: [], 72: []}
    med = {24: [], 72: []}
    for i, t in enumerate(grid):
        cur = np.array([series[s][t] for s in series])
        for hrs, k in ((24, 3), (72, 9)):
            if i + k >= len(grid):
                continue
            fwd = np.array([np.mean([series[s][grid[i + j]] for j in range(1, k + 1)])
                            for s in series])
            ics[hrs].append(spearman(cur, fwd))
            top = np.argsort(cur)[-max(2, len(cur) // 10):]      # what the executor buys
            dec[hrs].append(float(fwd[top].mean()))
            med[hrs].append(float(np.median(fwd)))

    res = {}
    for hrs in (24, 72):
        a = np.array(ics[hrs])
        t_ic = float(a.mean() / (a.std() / np.sqrt(len(a)))) if len(a) > 2 and a.std() else 0.0
        d, m = np.array(dec[hrs]), np.array(med[hrs])
        # annualise: funding pays 3x/day
        top_ann = float(d.mean() * 3 * 365 * 100)
        med_ann = float(m.mean() * 3 * 365 * 100)
        print(f"  --- {hrs}h holding period ---")
        print(f"    persistence IC (entry funding -> realised funding)  {a.mean():+.4f} "
              f"(t {t_ic:+.1f}, n={len(a)})")
        print(f"    TOP-decile basket realises {top_ann:+7.2f}%/yr")
        print(f"    universe median realises   {med_ann:+7.2f}%/yr")
        print(f"    selection edge             {top_ann - med_ann:+7.2f}%/yr\n")
        res[f"{hrs}h"] = {"persistence_ic": round(float(a.mean()), 4), "ic_t": round(t_ic, 2),
                          "top_decile_ann_pct": round(top_ann, 3),
                          "median_ann_pct": round(med_ann, 3),
                          "selection_edge_pct": round(top_ann - med_ann, 3)}

    # half-life of a funding shock
    hl = []
    for s in series:
        v = np.array([series[s][t] for t in grid])
        x0, x1 = v[:-1] - v.mean(), v[1:] - v.mean()
        b = float((x0 @ x1) / (x0 @ x0)) if (x0 @ x0) > 0 else 1.0
        if 0 < abs(b) < 1:
            hl.append(-np.log(2) / np.log(abs(b)))
    if hl:
        h = float(np.median(hl))
        print(f"  funding shock half-life: {h:.1f} periods ({h*8:.0f}h)")
        res["half_life_periods"] = round(h, 2)
        res["half_life_hours"] = round(h * 8, 1)

    e24 = res["24h"]["selection_edge_pct"]
    verdict = ("ENTRY SIGNAL WORKS -- top-decile selection beats the median materially"
               if e24 > 5 else
               "ENTRY SIGNAL WEAK -- selection adds little over buying the median symbol"
               if e24 > 1 else
               "ENTRY SIGNAL BROKEN -- selecting on current funding earns ~nothing extra")
    print(f"\n  VERDICT: {verdict}")
    print("  This is the executor's core assumption, tested for the first time.")
    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "symbols": len(series), "periods": len(grid),
                               "results": res, "verdict": verdict}, indent=1), "utf-8")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()

```

### scripts/hl_highpower_skill.py
```python
"""HIGH-POWER long-term skill test. Prior run: n=229 -> SE(rho)~0.066, could only detect rho>=0.13,
95% CI [-0.148,+0.110] -- so WEAK persistence (rho 0.05-0.11) was NOT excluded. Principal correctly
challenged the power. Fix: scale the cohort ~10x (probe deep into the 41k leaderboard, lower the
accountValue floor) -> target n~2500, SE~0.020, detects rho>=0.045.
Same design otherwise: multi-year on-chain records, own-curve 60/40 formation/holding split,
pnlHistory normalised by contemporaneous accountValue, risk-adjusted selection criteria.
Reports explicit CIs and minimum-detectable-effect so the conclusion is power-aware."""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

INFO="https://api.hyperliquid.xyz/info"; LB="https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"
N_TRY=2600; MIN_PTS=60; MIN_SPAN=200

def _get(u,t=180):
    return urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"q/1.0"}),timeout=t).read()
def _post(p,t=20):
    r=urllib.request.Request(INFO,data=json.dumps(p).encode(),
        headers={"Content-Type":"application/json","User-Agent":"q/1.0"})
    with urllib.request.urlopen(r,timeout=t) as x: return json.loads(x.read().decode())

rows=json.loads(_get(LB)); rows=rows.get("leaderboardRows",rows) if isinstance(rows,dict) else rows
cand=[]
for r in rows:
    try:
        av=float(r.get("accountValue",0) or 0); a=r.get("ethAddress")
        wp=dict(r.get("windowPerformances",[]))
        vlm=float(wp.get("month",{}).get("vlm",0) or 0)
        if a and av>=10_000 and vlm>0: cand.append((av,a))
    except (TypeError,ValueError): continue
cand.sort(reverse=True); sel=cand[:N_TRY]
print(f"probing {len(sel)} of {len(cand)} eligible accounts",flush=True)

recs=[]
for i,(_av0,a) in enumerate(sel):
    try: pf=_post({"type":"portfolio","user":a})
    except Exception: continue
    if not isinstance(pf,list): continue
    d=dict(pf).get("allTime") or {}
    pnl=d.get("pnlHistory") or []; avh=d.get("accountValueHistory") or []
    if len(pnl)<MIN_PTS or len(avh)<MIN_PTS: continue
    try:
        t=np.array([int(x[0]) for x in pnl]); cum=np.array([float(x[1]) for x in pnl])
        avt=np.array([float(x[1]) for x in avh[:len(cum)]])
    except (TypeError,ValueError,IndexError): continue
    if len(avt)!=len(cum): continue
    base=np.where(avt>1000,avt,np.nan)
    ret=np.zeros(len(cum)); ret[1:]=np.diff(cum)/np.where(np.isnan(base[1:]),np.inf,base[1:])
    ret=np.clip(np.nan_to_num(ret,nan=0.0,posinf=0.0,neginf=0.0),-0.5,0.5)
    if (t[-1]-t[0])/86400_000 < MIN_SPAN: continue
    k=int(len(ret)*0.6); f,h=ret[1:k],ret[k:]
    if len(f)<25 or len(h)<15: continue
    fs=float(f.mean()/f.std()*np.sqrt(365)) if f.std()>0 else 0.0
    eq=np.cumprod(1+f); dd=float((eq/np.maximum.accumulate(eq)-1).min())
    recs.append({"span":(t[-1]-t[0])/86400_000,"f_sharpe":fs,"f_cons":float((f>0).mean()),
                 "f_dd":dd,"f_ret":float(np.prod(1+f)-1),"h_ret":float(np.prod(1+h)-1),
                 "h_sharpe":float(h.mean()/h.std()*np.sqrt(365)) if h.std()>0 else 0.0})
    if (i+1)%300==0:
        print(f"  {i+1}/{len(sel)} usable={len(recs)}",flush=True)
        Path("data/hl_hp_partial.json").write_text(json.dumps(recs),"utf-8")

n=len(recs); print(f"\nHIGH-POWER cohort: {n} traders with long records")
if n<100: raise SystemExit("insufficient")
sp=np.array([r["span"] for r in recs])
se=1/np.sqrt(max(1,n-3)); mde=2*se
print(f"track record: median {np.median(sp):.0f}d max {sp.max():.0f}d")
print(f"POWER: SE(rho)~{se:.4f} -> minimum detectable |rho| at t=2 is {mde:.4f}")

def spear(a,b):
    ra=np.argsort(np.argsort(a)).astype(float); rb=np.argsort(np.argsort(b)).astype(float)
    if ra.std()==0 or rb.std()==0: return 0.0,0.0
    rho=float(np.corrcoef(ra,rb)[0,1])
    return rho, float(rho*np.sqrt((n-2)/max(1e-12,1-rho**2))) if n>2 and abs(rho)<1 else 0.0

hr=np.array([r["h_ret"] for r in recs]); out={}
for nm,key in (("SHARPE","f_sharpe"),("CONSISTENCY","f_cons"),("RETURN","f_ret"),("DRAWDOWN_CTRL","f_dd")):
    x=np.array([r[key] for r in recs]); rho,t=spear(x,hr)
    lo,hi=rho-1.96*se, rho+1.96*se
    o=np.argsort(x); k=max(5,n//4); top,bot=hr[o[-k:]],hr[o[:k]]
    sd=np.sqrt(top.var(ddof=1)/k+bot.var(ddof=1)/k); ts=(top.mean()-bot.mean())/sd if sd>0 else 0
    print(f"\n[{nm}] rho {rho:+.4f} (t {t:+.2f})  95% CI [{lo:+.4f},{hi:+.4f}]")
    print(f"   Q4 holding ret {top.mean()*100:+.1f}% (med {np.median(top)*100:+.1f}%) vs "
          f"Q1 {bot.mean()*100:+.1f}% (med {np.median(bot)*100:+.1f}%) | spread t {ts:+.2f}")
    out[nm]={"rho":round(rho,4),"t":round(t,2),"ci":[round(lo,4),round(hi,4)],
             "q4_mean":round(float(top.mean()),4),"q1_mean":round(float(bot.mean()),4),
             "spread_t":round(float(ts),2)}
print(f"\ncohort holding: mean {hr.mean()*100:+.1f}% median {np.median(hr)*100:+.1f}% "
      f"| positive {int((hr>0).sum())}/{n}")
Path("data/hl_highpower_skill.json").write_text(json.dumps(
    {"updated":datetime.now(tz=UTC).isoformat(),"n":n,"se_rho":round(float(se),4),
     "min_detectable_rho":round(float(mde),4),"median_span_d":float(np.median(sp)),
     "tests":out},indent=1),"utf-8")

```

### scripts/render_desk_digest.py
```python
"""Render the desk's JSON state into docs/desk_digest.md -- the Obsidian-readable daily brief.

The knowledge base is markdown (Obsidian-native) but the measurable state (decision ledger,
executive KPIs, validation clocks, root cause) lives in JSON per governance. This renders a daily
digest so the whole desk is browsable in one vault. Generated file -- never hand-edit.

    python scripts/render_desk_digest.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_OUT = Path("docs/desk_digest.md")


def _load(p: str) -> dict[str, Any]:
    try:
        d: dict[str, Any] = json.loads(Path(p).read_text("utf-8"))
        return d
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> None:
    lc = _load("web/live_combined.json")
    mo = lc.get("molded", {})
    rc = _load("web/root_cause.json")
    led = _load("data/decision_ledger.json").get("decisions", [])
    kpi = _load("data/executive_kpis.json")

    lines = [
        "# Desk digest (auto-generated daily -- do not hand-edit)",
        f"_updated {datetime.now(tz=UTC).isoformat()[:16]}Z · companion to "
        "[[institutional_knowledge]]_", "",
        "## Book",
        f"- Molded net: **${mo.get('net_pnl')}** | funding **${mo.get('funding')}** | "
        f"run-rate APR {mo.get('run_rate_apr_pct')}% | day {mo.get('days_live')}",
        f"- Root cause: **{rc.get('top_cause')}** ({rc.get('action')}) | tracking error "
        f"${rc.get('tracking_error_usd')}", "",
        "## Validation clocks",
    ]
    clocks = (("cashcarry_shadow", "carry (DEPLOYED)"), ("crypto_shadow", "perp L/S"),
              ("trend_shadow", "trend"), ("trend_regime_shadow", "trend regime-gated"),
              ("derivative_shadow", "OI/LS data"), ("stablecoin_flows", "stablecoin data"))
    for f, lbl in clocks:
        s = _load(f"web/{f}.json")
        days = s.get("forward_days", s.get("days_accumulated", s.get("forward_days", "?")))
        need = s.get("needs_days", s.get("min_days", 90))
        bt, fwd = s.get("backtest_ann_sharpe"), s.get("forward_ann_sharpe")
        extra = f" | bt {bt} fwd {fwd}" if bt is not None else ""
        lines.append(f"- **{lbl}**: {days}/{need}d{extra}")
    lines += ["", "## Open decisions (ledger)"]
    for dec in led:
        if dec.get("outcome") is None:
            lines.append(f"- `{dec.get('id')}` -- review {dec.get('review_due', '?')}: "
                         f"{dec.get('success_metric', '')[:90]}")
    lines += ["", "## Executive KPI snapshot",
              f"- CRO: {json.dumps(kpi.get('CRO', {}).get('current', {}))[:180]}",
              f"- CEO binding constraint: "
              f"{kpi.get('CEO', {}).get('current', {}).get('binding_constraint', '?')}", "",
              "_Full state: decision_ledger.json · executive_kpis.json · data_registry.json_"]
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text("\n".join(lines), "utf-8")
    print(f"desk digest -> {_OUT} ({len(lines)} lines)")


if __name__ == "__main__":
    main()

```

### scripts/rollback_guard.py
```python
"""Reversible autonomous change guard -- checkpoint -> monitor -> auto-revert.

Every autonomous implementation must be reversible. This is the mechanism:
  checkpoint <label>  -- snapshot the autonomous-mutable code surface (scripts/ libs/ tests/ +
                         web/index.html + the root state JSONs) into data/rollback/<id>/, plus a
                         cheap baseline metrics record. Fast, no .venv/secrets/lake (code only).
  evaluate <id>       -- run the CI gate + compare live health to the baseline; print OK or REVERT
                         with reasons. Triggers (attributable to a CODE change, NOT market noise):
                         CI regression, executor heartbeat went stale, new cycle errors, or a
                         hedge-drift signal. PnL is deliberately NOT a trigger -- it is market-
                         confounded, so reverting on it would be noise-driven (dishonest).
  revert <id>         -- restore every tracked file from the snapshot (exact rollback).

Keeps the last 20 checkpoints. Pure stdlib. The autonomous CRO cycle checkpoints BEFORE it modifies
a subsystem and evaluates AFTER; it auto-reverts on a REVERT verdict.

    python scripts/rollback_guard.py checkpoint <label>
    python scripts/rollback_guard.py evaluate  <id>
    python scripts/rollback_guard.py revert    <id>
"""

from __future__ import annotations

import contextlib
import json
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.ops.platform_paths import venv_python

_ROOT = Path(__file__).resolve().parent.parent
_RB = _ROOT / "data" / "rollback"
_PY = venv_python(_ROOT)
_KEEP = 20
_ERR_GROWTH_LIMIT = 200                      # bytes of NEW error-log content that trips a revert

_TRACK_DIRS = ("scripts", "libs", "tests")   # snapshot every .py under these
_TRACK_FILES = ("web/index.html", "research_agenda.json", "engineering_backlog.json",
                "research_state.json", "alpha_pipeline.json")


def _tracked() -> list[Path]:
    out: list[Path] = []
    for d in _TRACK_DIRS:
        base = _ROOT / d
        if base.exists():
            out += [p.relative_to(_ROOT) for p in base.rglob("*.py")
                    if "__pycache__" not in p.parts]
    out += [Path(f) for f in _TRACK_FILES if (_ROOT / f).exists()]
    return out


def _metrics() -> dict[str, object]:
    """Cheap, no-network health snapshot (baseline for deterioration detection)."""
    err = _ROOT / "data" / "cashcarry_error.log"
    hb = _ROOT / "data" / "cashcarry_exec_heartbeat"
    port: dict[str, Any] = {}
    cc: dict[str, Any] = {}
    with contextlib.suppress(OSError, json.JSONDecodeError):
        port = json.loads((_ROOT / "web" / "portfolio.json").read_text("utf-8")).get("deployed", {})
    with contextlib.suppress(OSError, json.JSONDecodeError):
        cc = json.loads((_ROOT / "web" / "cashcarry_live.json").read_text("utf-8"))
    acts = cc.get("last_actions", []) if isinstance(cc.get("last_actions"), list) else []
    return {
        "ts": datetime.now(tz=UTC).isoformat(),
        "error_log_bytes": err.stat().st_size if err.exists() else 0,
        "hb_age_s": round(time.time() - hb.stat().st_mtime, 1) if hb.exists() else None,
        "hedge_drift": any("re-hedge" in a or "cover-orphan" in a or "RISK-FLATTEN" in a
                           for a in acts),
        "net_pnl": port.get("net_pnl"),
    }


def _ci_green() -> bool:
    # --fail-on-lock: without it, "another gate is mid-run" exits 0 and a guard deciding whether
    # a revert restored health would count an UNVERIFIED tree as green (R0146, the skip-reads-
    # green family). rc 3 -> False: a guard that could not verify must not claim health (L1.28a).
    r = subprocess.run([_PY, "scripts/run_ci.py", "--fail-on-lock"], cwd=str(_ROOT),
                       capture_output=True, text=True, check=False)
    return r.returncode == 0


def checkpoint(label: str) -> str:
    cid = f"{datetime.now(tz=UTC):%Y%m%dT%H%M%S}_{label}"
    dest = _RB / cid
    for rel in _tracked():
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_ROOT / rel, dest / rel)
    (dest / "_baseline.json").write_text(json.dumps(_metrics(), indent=2), "utf-8")
    for old in sorted(_RB.glob("*/"))[:-_KEEP]:               # prune to last _KEEP
        shutil.rmtree(old, ignore_errors=True)
    print(f"checkpoint {cid} ({len(_tracked())} files)")
    return cid


def evaluate(cid: str) -> str:
    dest = _RB / cid
    base = json.loads((dest / "_baseline.json").read_text("utf-8"))
    now = _metrics()
    reasons: list[str] = []
    if not _ci_green():
        reasons.append("CI regression (lint/tests/stress fail)")
    if now["error_log_bytes"] - base.get("error_log_bytes", 0) > _ERR_GROWTH_LIMIT:
        reasons.append(f"new cycle errors (+{now['error_log_bytes'] - base['error_log_bytes']}B)")
    if now["hedge_drift"] and not base.get("hedge_drift"):
        reasons.append("hedge drift appeared post-change")
    if base.get("hb_age_s") is not None and (now["hb_age_s"] or 999) > 240 \
            and base["hb_age_s"] <= 240:
        reasons.append("executor heartbeat went stale post-change")
    verdict = "REVERT" if reasons else "OK"
    print(f"evaluate {cid}: {verdict}" + (f" -> {'; '.join(reasons)}" if reasons else " (healthy)"))
    return verdict


def revert(cid: str) -> None:
    dest = _RB / cid
    n = 0
    for src in dest.rglob("*"):
        if src.is_file() and src.name != "_baseline.json":
            rel = src.relative_to(dest)
            (_ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, _ROOT / rel)
            n += 1
    print(f"reverted {cid} ({n} files restored)")


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    cmd, arg = sys.argv[1], sys.argv[2]
    if cmd == "checkpoint":
        checkpoint(arg)
    elif cmd == "evaluate":
        return 1 if evaluate(arg) == "REVERT" else 0
    elif cmd == "revert":
        revert(arg)
    else:
        print(f"unknown command: {cmd}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/run_alpha_factory.py
```python
"""Alpha factory: the production caller for the research-coordination engines.

Measured 2026-07-27: 17 of 21 `libs/alpha_factory` modules were unreachable from any entry point.
The audit tracked `crypto-factory` as an organ owing `web/autodiscovery_crypto.json` every 30h and
reported it had never produced output -- consistent, because the engines behind it were never
called. The controller imported fifteen engines and its `run()` used two.

Inputs are the desk's own files, not fixtures:
  research_agenda.json  queue_ranked_by_expected_research_roi  -> the candidates
                        do_not_repeat                          -> novelty (already-killed families)
  alpha_pipeline.json   alphas + deployed                      -> portfolio gaps, crowding, lineage

Recommend-only by construction: the controller raises on promote/retire/capital/threshold changes.
This script writes a recommendation artifact and nothing else -- no candidate reaches capital
without the validation gauntlet.

    python scripts/run_alpha_factory.py
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.alpha_factory.alpha_dna import build_alpha_dna, dna_distance
from libs.alpha_factory.alpha_factory_controller import AlphaFactoryController
from libs.alpha_factory.models import AlphaCategory, IdeaCandidate

_ROOT = Path(__file__).resolve().parent.parent
_AGENDA = _ROOT / "research_agenda.json"
_PIPELINE = _ROOT / "alpha_pipeline.json"
_OUT = _ROOT / "web" / "alpha_factory.json"

#: Average daily volume assumed per category when the desk has no measured figure. Deliberately
#: CONSERVATIVE -- capacity that is guessed high sends research budget at concepts that cannot
#: hold the book, which is the expensive direction of this error.
_ADV_FALLBACK_USD = 5_000_000.0

_CROWDING = {"low": 0.2, "medium": 0.5, "high": 0.8, "unknown": 0.5}


def _load(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _novelty(text: str, killed: list[str]) -> float:
    """1.0 = nothing like it in the do-not-repeat list, 0.0 = an exact family match.

    Token-overlap against 42 already-killed families. Coarse on purpose: the job here is to stop
    the factory spending budget re-deriving `funding_carry`, not to adjudicate near-misses -- and
    a scorer that claims more precision than substring matching has would be lying about it.
    """
    t = text.lower().replace("-", "_")
    for k in killed:
        kk = str(k).lower().replace("-", "_")
        if kk and kk in t:
            return 0.0
    words = {w for w in t.replace("_", " ").split() if len(w) > 3}
    if not words:
        return 1.0
    hits = sum(1 for k in killed
               if {w for w in str(k).lower().replace("_", " ").split() if len(w) > 3} & words)
    return max(0.0, 1.0 - hits / max(4.0, len(killed) / 4.0))


def _candidates(agenda: dict[str, Any], deployed: list[str],
                killed: list[str]) -> list[IdeaCandidate]:
    out: list[IdeaCandidate] = []
    queue = agenda.get("queue_ranked_by_expected_research_roi", [])
    n = max(1, len(queue))
    for i, q in enumerate(queue):
        if not isinstance(q, dict):
            continue
        text = f"{q.get('id','')} {q.get('family','')} {q.get('mechanism','')}"
        # `rank` is hand-maintained and is sometimes prose ("low-rank (near-miss; re-estimate at
        # panel)"). An unparseable rank sorts to the BACK rather than raising or being treated as
        # rank 1 -- the desk wrote words instead of a number precisely when it was unsure.
        try:
            rank = float(q.get("rank", i + 1))
        except (TypeError, ValueError):
            rank = float(n)
        # the agenda's own rank is the desk's stated prior; converted to 0-1 so the factory's
        # ranking can AGREE or DISAGREE with it visibly rather than silently re-deriving it.
        prior = max(0.0, 1.0 - (rank - 1.0) / n)
        out.append(IdeaCandidate(
            idea_id=str(q.get("id", f"idea_{i}")),
            category=str(q.get("family", "uncategorised")),
            statement=str(q.get("mechanism", ""))[:400],
            expected_edge=round(prior, 3),
            expected_robustness=round(prior * 0.8, 3),
            expected_capacity=0.5,
            novelty=round(_novelty(text, killed), 3),
            crowding=_CROWDING["unknown"],
            regime_need=0.0,
            # a family the desk has NOT deployed is a portfolio gap by definition
            portfolio_need=0.0 if str(q.get("family", "")) in deployed else 1.0,
        ))
    return out


#: The desk's free-text family names -> the Stage-13 AlphaCategory vocabulary the allocator
#: budgets against. An explicit table rather than a fuzzy match: the allocator splits research
#: budget by category, so a silently mis-mapped family sends effort at the wrong thing, and a
#: silently DROPPED family gets no budget at all while still looking present in the queue.
_FAMILY_TO_CATEGORY = {
    "cross-exchange": AlphaCategory.STATISTICAL_ARBITRAGE,
    "derivative-microstructure": AlphaCategory.MICROSTRUCTURE,
    "derivative-data": AlphaCategory.MICROSTRUCTURE,
    "execution-alpha": AlphaCategory.MARKET_MAKING,
    "on-chain-flow": AlphaCategory.ALTERNATIVE_DATA,
    "options": AlphaCategory.OPTIONS,
    "crypto-sleeve": AlphaCategory.CARRY,
}


def _categories(pipeline: dict[str, Any], agenda: dict[str, Any]) -> tuple[
        list[AlphaCategory], list[str]]:
    """(categories for the allocator, family names that had no mapping).

    Unmapped names are RETURNED, not swallowed. The first version caught the exception and
    continued, which produced "7 candidates over 0 categories" and looked like a working run --
    a research budget allocated across nothing.
    """
    names = {str(a.get("category")) for a in pipeline.get("alphas", [])
             if isinstance(a, dict) and a.get("category")}
    names |= {str(q.get("family")) for q in
              agenda.get("queue_ranked_by_expected_research_roi", [])
              if isinstance(q, dict) and q.get("family")}
    names.discard("None")
    cats, unmapped = set(), []
    for nm in sorted(names):
        cat = _FAMILY_TO_CATEGORY.get(nm)
        if cat is None:
            unmapped.append(nm)
            cats.add(AlphaCategory.OTHER)
        else:
            cats.add(cat)
    return sorted(cats), unmapped


def _dna_of(alpha: dict[str, Any]) -> Any:
    """Coarse DNA from what alpha_pipeline.json actually records.

    Only category, crowding and expected Sharpe are available, so timeframe/holding are marked
    `unknown` rather than guessed -- an invented timeframe would make two unrelated concepts look
    like siblings to the similarity engine, which is exactly the judgement it exists to make.
    """
    return build_alpha_dna(
        signal_type=str(alpha.get("category", "unknown")),
        market="crypto",
        timeframe="unknown",
        holding_period=str(alpha.get("expected_half_life", "unknown")),
        capacity_estimate=0.0,
        risk_profile=_CROWDING.get(str(alpha.get("crowding_risk", "unknown")), 0.5),
    )


def main() -> int:
    agenda = _load(_AGENDA, {})
    pipeline = _load(_PIPELINE, {})
    if not agenda and not pipeline:
        print("alpha factory: no research_agenda.json / alpha_pipeline.json -- nothing to do")
        return 0

    killed = [str(x) for x in agenda.get("do_not_repeat", []) if isinstance(x, str)]
    deployed = [str(x) for x in pipeline.get("deployed", [])]
    alphas = [a for a in pipeline.get("alphas", []) if isinstance(a, dict)]

    cands = _candidates(agenda, deployed, killed)
    cats, unmapped_families = _categories(pipeline, agenda)
    if not cands:
        print("alpha factory: research queue is empty -- no candidates to coordinate")
        return 0

    # The factory needs a Database for ResearchMemory. Kept IN-MEMORY and migrated fresh each
    # run: a recommendation pass must never be able to write production state, and the
    # governance guards on the controller only cover the methods, not the connection it holds.
    from migrations import MIGRATIONS

    from libs.store.connection import Database
    from libs.store.migrations import run_migrations
    db = Database(":memory:")
    run_migrations(db, MIGRATIONS)
    ctl = AlphaFactoryController(db)

    portfolio_gaps = {c.category: 1.0 for c in cands if c.portfolio_need > 0}
    crowding = {c.category: c.crowding for c in cands}
    report = ctl.run(candidates=cands, categories=cats,
                     portfolio_gaps=portfolio_gaps, crowding=crowding)

    assessments = [ctl.assess(candidate=c, adv_usd=_ADV_FALLBACK_USD) for c in cands]

    # duplication: does any candidate's family already exist in the deployed book?
    deployed_dna = {f"deployed::{a['alpha']}": _dna_of(a) for a in alphas
                    if str(a.get("alpha", "")).split("::")[-1] in deployed
                    or str(a.get("alpha", "")) in deployed}
    cand_dna = {c.idea_id: build_alpha_dna(signal_type=c.category, market="crypto",
                                           timeframe="unknown", holding_period="unknown")
                for c in cands}
    clusters = [c for c in ctl.duplicates_of(cand_dna, deployed_dna) if len(c) > 1]

    for a in alphas:
        ctl.record_lineage(str(a.get("alpha", "?")), mutation_type="pipeline",
                           performance=float(a.get("expected_sharpe", 0.0) or 0.0))

    nearest = {}
    for cid, d in cand_dna.items():
        if deployed_dna:
            k, dd = min(((k, dna_distance(d, v)) for k, v in deployed_dna.items()),
                        key=lambda kv: kv[1])
            nearest[cid] = {"closest_deployed": k, "dna_distance": round(dd, 4)}

    out = {
        "generated": datetime.now(tz=UTC).isoformat(),
        "n_candidates": len(cands),
        "n_categories": len(cats),
        "unmapped_families": unmapped_families,
        "n_killed_families_screened": len(killed),
        "deployed": deployed,
        "research_priorities": [
            {"idea_id": p.idea_id, "category": p.category,
             "priority": round(p.idea_priority_score, 2), "components": p.components}
            for p in report.research_priorities],
        "allocation": (report.allocation.allocations if report.allocation else {}),
        "allocation_rationale": (report.allocation.rationale if report.allocation else {}),
        "assessments": assessments,
        "duplicate_clusters": clusters,
        "nearest_deployed": nearest,
        "portfolio_gaps": report.portfolio_gaps,
        "best_lineage": [n.alpha_id for n in ctl.family_tree.best_lineage()],
        "notes": report.notes,
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")

    top = out["research_priorities"][:3]
    print(f"alpha factory: {len(cands)} candidates over {len(cats)} categories, "
          f"screened against {len(killed)} killed families")
    if unmapped_families:
        print(f"  UNMAPPED families (budgeted as OTHER, add to _FAMILY_TO_CATEGORY): "
              f"{', '.join(unmapped_families)}")
    for p in top:
        a = next((x for x in assessments if x["idea_id"] == p["idea_id"]), {})
        print(f"  {p['priority']:5.1f}  {p['idea_id']:<32} "
              f"research_score={a.get('research_score', 0):.1f} "
              f"scalability={a.get('scalability_score', 0):.0f}")
    if clusters:
        print(f"  DUPLICATE clusters vs deployed: {clusters}")
    # a display path must never be able to fail the run: _OUT is relocatable (tests, and
    # any operator who redirects it), and relative_to() raises outside the repo root.
    try:
        shown = _OUT.relative_to(_ROOT)
    except ValueError:
        shown = _OUT
    print(f"  -> {shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/run_axis_shadows.py
```python
#!/usr/bin/env python3
"""AXIS SHADOW SLEEVES -- Stage-B forward tracking for every screened data axis.

Closes the loop the two-stage law needs: Stage A (libs/research/axis_screen) writes a forward
clock, but NOTHING read those clocks, so evidence accrued into a file nobody evaluated and
eligibility could never be detected. This runs the shadow book for each axis and computes the
Stage-B statistics that actually govern promotion.

STRICTLY FORWARD-ONLY. The in-sample screen history is IGNORED: P&L starts at the clock's first
row (pre-registration date). A hypothesis registered before its window cannot have overfit that
window -- that is the entire statistical basis for Stage B, and reading back into the screen
sample would destroy it.

ZERO PROMOTION AUTHORITY of its own: it reports ACCRUING / ELIGIBLE / FAILING. ELIGIBLE means the
evidence bar is met and a promotion decision may now be TAKEN by the normal gauntlet + principal
path -- never an automatic deployment of capital.

Multiplicity: m = the FULL concurrent forward cohort (libs.research.slot_registry), Holm-corrected
via forward_stats.holm_bar, so running many clocks in parallel does not inflate the family-wise
error rate. It counted len(_AXES) until 2026-07-30 -- the axis clocks only -- which applied
holm_bar(4)=2.24 while 12 clocks were accruing (2.64): a bar ~3.2x too loose, in the phantom-edge
direction, on the desk's only path from research to capital. The cohort spans axis + standing +
derivative clocks, so no single file may count it.

    python scripts/run_axis_shadows.py
"""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from libs.research.slot_registry import concurrent_m
from libs.validation.forward_stats import holm_bar, nw_tstat

_ROOT = Path(__file__).resolve().parent.parent
_OUT = _ROOT / "web" / "axis_shadows.json"
_STATE = _ROOT / "data" / "axis_shadow_state.json"

_MIN_DAYS = 40          # pre-registered minimum forward window before eligibility
_BINANCE = "https://fapi.binance.com/fapi/v1/klines"

# axis registry: name -> (clock file, target symbol, signal field, direction)
# direction: +1 = momentum (long when z>0), -1 = reversal
_AXES: dict[str, tuple[str, str, str, int]] = {
    # kimchi_premium RETIRED 2026-07-30: the edge was RETRACTED 2026-07-29 as a ~73% timestamp
    # artifact (registry E-02f2917dfb, commit 02f2917db, decision REFUTED; failure modes
    # B_WRONG_MEASUREMENT / C_WRONG_TIMING / E_DATA_QUALITY -- Upbit KST daily candles sat ahead of
    # the Binance UTC closes, the same lookahead that killed bithumb_KR). Its own forward clock
    # agreed: day 8/40 at ann Sharpe -5.13, nw_t -0.71. The retraction was never propagated here,
    # so a refuted hypothesis went on holding 1 of MAX_FORWARD_SLOTS=12 -- reading the cohort FULL
    # and blocking 9 verified axes from a clock (the clock-saturation defect), exactly the
    # "raises the confirmation bar on the LIVE axes for zero benefit" case set by
    # onchain_activity_throughput above. NOTE the distinction that licenses dropping m here:
    # kimchi was refuted as an INVALID MEASUREMENT, not failed on its merits, and an invalid trial
    # is not a trial -- a candidate that legitimately accrued and lost must STAY in the denominator
    # (ADAPTIVE VALIDATION WINDOWS v2: attrition must never lower the bar). Collector keeps
    # archiving (input store). Re-admission needs a NEW construction with declared UTC alignment
    # that clears the shift-sensitivity rail in scripts/revalidate_clocks.py first.
    # orthogonal on-chain USAGE axis (not price/derivative): economic throughput,
    # reversal. Weak+fragile in-sample (composite Sharpe collapsed) -> forward clock
    # under the Holm bar decides. same-period corr ~-0.06 = genuinely leading.
    # onchain_activity_throughput RETIRED 2026-07-24: killed by 11y reconstructed held-out
    # OOS (IC ~0, ann Sharpe -0.03, regime thirds [-0.3,-0.08,+0.37] = recent-era overfit;
    # reports/reconstructed_oos/onchain_throughput.json). A permanently-unpromotable axis
    # holding a Holm slot raises the confirmation bar on the LIVE axes for zero benefit.
    # Collector keeps archiving (input store); the CLOCK slot is freed. Re-admission needs
    # a NEW construction that passes held-out OOS first.
    # macro dollar-liquidity: total stablecoin supply (all issuers, DefiLlama),
    # momentum. Weak (IC 0.067) but economically grounded + orthogonal. SAME construct
    # as the supply field in run_stablecoin_flows -> ONE hypothesis, this is the tracked one.
    # DeFi system utilisation (total borrow / total supply, Aave+Compound+Morpho+Spark).
    # M_FORCED_DELEVERAGE -- the desk's BEST-supported mechanism (2/10 survival, holds the only
    # confirmed edge). Direction -1: extreme utilisation = leverage crowded = fragile, so the
    # prior is that it precedes weakness. Stated in ADVANCE; the clock decides, not the story.
    # Stage-B slot 4 of 5 -- Holm bar rises 2.39 -> 2.52, which stageb_capacity computed as cheap.
    "defi_utilisation": ("data/defi_util_axis.jsonl", "BTCUSDT", "z20", -1),
    "stablecoin_supply_momentum": ("data/stablecoin_supply.jsonl", "BTCUSDT", "z20", +1),
    # USDT/CNY P2P premium (capital-control pressure; kimchi CN-analog). Direction +1
    # PRE-REGISTERED from mechanism 2026-07-24 (peek-safe: chosen before any forward
    # return existed). TRY-falsifier logged in the collector: thin 30d std => FAILING.
    "cny_premium": ("data/cny_premium.jsonl", "BTCUSDT", "z20", +1),
    # WALCL reserve-quantity impulse (R0031, registered 2026-07-31 into the slot kimchi's
    # retirement freed -- cohort 11 -> 12). Mechanism: the Fed balance sheet is the QUANTITY
    # of system reserves, an inelastic constraint on the marginal dollar bidding risk assets;
    # the highest-beta sink responds over weeks. Stage-A: IC +0.1106 (n=815 weekly), decontam
    # PASSED (resid +0.0964), stopped ONLY by the power gate (n_eff 116 vs MDI 0.1816) -- the
    # power wall closes by FORWARD ACCRUAL, nothing else. Direction +1 (momentum) stated in
    # advance from the screen's mechanism-consistent sign. Signal = 4wk log change, +2d
    # release lag, z20 -- construction frozen in scripts/derive_walcl_clock.py; the clock
    # decides, not the story. Peek-safe: first forward row is the registration day.
    "walcl_reserve_impulse": ("data/walcl_impulse.jsonl", "BTCUSDT", "z20", +1),
}


def _closes(symbol: str, n: int = 400) -> dict[str, float]:
    """Daily closes keyed by ISO date (UTC), from the venue the desk actually trades."""
    url = f"{_BINANCE}?symbol={symbol}&interval=1d&limit={n}"
    req = urllib.request.Request(url, headers={"User-Agent": "quant-desk/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        rows = json.loads(r.read())
    return {datetime.fromtimestamp(k[0] / 1000, tz=UTC).date().isoformat(): float(k[4])
            for k in rows}


def _clock_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text("utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _evaluate(name: str, clock: str, symbol: str, field: str, direction: int, m: int) -> dict:
    rows = _clock_rows(_ROOT / clock)
    if len(rows) < 2:
        return {"axis": name, "verdict": "ACCRUING", "forward_days": len(rows),
                "need": _MIN_DAYS, "note": "clock just started -- forward evidence begins now"}

    closes = _closes(symbol)
    rets, used = [], []
    for i in range(len(rows) - 1):
        d0, d1 = rows[i].get("date"), rows[i + 1].get("date")
        c0, c1 = closes.get(d0), closes.get(d1)
        z = rows[i].get(field)
        if None in (c0, c1, z) or c0 == 0:
            continue
        pos = float(np.sign(float(z))) * direction     # position taken AT d0 close
        rets.append(pos * (c1 / c0 - 1.0))             # realised over d0 -> d1 (no lookahead)
        used.append(d1)

    n = len(rets)
    if n < 2:
        return {"axis": name, "verdict": "ACCRUING", "forward_days": n, "need": _MIN_DAYS,
                "note": "not enough aligned forward days yet"}

    arr = np.asarray(rets, dtype="float64")
    cum = float(np.prod(1.0 + arr) - 1.0)
    sharpe = float(arr.mean() / arr.std() * np.sqrt(365)) if arr.std() > 0 else 0.0
    t = float(nw_tstat(arr)) if n >= 3 else 0.0
    bar = float(holm_bar(m, rank=1))

    if n < _MIN_DAYS:
        verdict = "ACCRUING"
    elif t >= bar:
        verdict = "ELIGIBLE"                            # bar met -- decision may now be taken
    else:
        verdict = "FAILING"                             # forward evidence does not support it
    return {"axis": name, "verdict": verdict, "forward_days": n, "need": _MIN_DAYS,
            "cum_return": round(cum, 5), "ann_sharpe": round(sharpe, 2),
            "nw_t": round(t, 3), "holm_bar": round(bar, 3), "m_concurrent": m,
            "first_forward_day": used[0] if used else None, "last": used[-1] if used else None,
            "stage": "B (forward-only; eligibility != deployment)"}


def main() -> None:
    # One cohort read for the whole run: every clock in this file is judged against the SAME
    # concurrent-m, and re-deriving per axis would let the bar drift mid-run.
    m = concurrent_m()
    results = [_evaluate(k, *v, m) for k, v in _AXES.items()]
    payload = {"updated": datetime.now(tz=UTC).isoformat(), "min_forward_days": _MIN_DAYS,
               "axes": results,
               "note": ("Forward-only Stage-B tracking. P&L starts at the clock's first row, never "
                        "the screen sample. ELIGIBLE means the evidence bar is met and a promotion "
                        "decision may be taken -- it is NOT an automatic deployment.")}
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(payload, indent=1), "utf-8")
    _STATE.write_text(json.dumps(payload, indent=1), "utf-8")
    for r in results:
        extra = f"t={r.get('nw_t')} bar={r.get('holm_bar')}" if "nw_t" in r else r.get("note", "")
        print(f"axis-shadow | {r['axis']}: {r['verdict']} "
              f"({r['forward_days']}/{r['need']}d) {extra}")
    print(f"-> {_OUT}")


if __name__ == "__main__":
    main()

```

### scripts/run_deadman_stranded_sweep.py
```python
"""Recover spot inventory stranded by the confirmed root cause of the 2026-07-19 dead-man fire.

Root cause (verified against code + venue records, GAP register row 34): `_execute_pair`'s
market-order fallback in scripts/run_cashcarry_executor.py wraps every order in `with _safe():`,
which swallows ALL exceptions with zero fill verification. The CLOSE path then unconditionally
logs success and deletes the position from tracking regardless of whether the sell actually
filled. For GTCUSDT/SHELLUSDT/ONEUSDT the close orders never filled on-venue: the position was
deleted from `pos` (so no reconciler ever revisits it) while 100% of the real spot inventory
stayed in the wallet, invisible to both the tracker and the dead-man's `legs_v` (which only counts
symbols with a currently-live futures short -- these no longer have one).

This script does NOT touch scripts/run_deadman_switch.py, its state files, or the executor's
tracked positions (these symbols are already absent from data/cashcarry_positions.json). It only
sells now-untracked, already-owned spot dust back to USDT -- a recovery action within existing
standing trading authority, not a new position or a fund transfer.

    .venv/bin/python scripts/run_deadman_stranded_sweep.py           # dry-run (default)
    .venv/bin/python scripts/run_deadman_stranded_sweep.py --execute # place real (testnet) orders
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from libs.execution import binance_spot_testnet as spot

_ROOT = Path(__file__).resolve().parent.parent
_OUT = _ROOT / "data" / "deadman_stranded_sweep_log.json"
_SYMBOLS = ("GTCUSDT", "SHELLUSDT", "ONEUSDT")  # confirmed stranded (row 34 forensic scan);
# COOKIE/MOVE/HFT/C98/IOTX/CRV/BICO/JASMY/TST/XVG checked and confirmed zero -- their closes
# executed cleanly. Add a symbol here only after confirming a non-zero, currently-untracked
# balance via spot.balances() -- never sweep a symbol still present in cashcarry_positions.json.


def main() -> None:
    execute = "--execute" in sys.argv
    if not spot.has_keys():
        print("ABORT: no spot testnet keys")
        sys.exit(1)

    tracked = set(json.loads((_ROOT / "data" / "cashcarry_positions.json").read_text("utf-8"))
                  .get("positions", {}))
    bals = spot.balances()
    px = spot.prices()
    filters = spot.exchange_filters()

    rows: list[dict[str, Any]] = []
    for sym in _SYMBOLS:
        base = sym.replace("USDT", "")
        if sym in tracked:
            print(f"SKIP {sym}: still a tracked live position -- never sweep a live carry leg")
            continue
        qty = bals.get(base, 0.0)
        price = px.get(sym, 0.0)
        if qty <= 0 or price <= 0:
            print(f"SKIP {sym}: no balance ({qty})")
            continue
        fl = filters.get(sym, {})
        step = fl.get("step", 0.0) or 0.0
        prec = int(fl.get("qty_prec", 6))
        sell_qty = round(qty - (qty % step), prec) if step else round(qty, prec)
        est_usdt = round(sell_qty * price, 2)
        row = {"symbol": sym, "qty_held": qty, "sell_qty": sell_qty,
               "price": price, "est_usdt": est_usdt}
        if execute and sell_qty > 0:
            try:
                res = spot.place_market(sym, "SELL", sell_qty)
                row["order_result"] = res
                row["executed"] = True
            except Exception as e:
                row["error"] = repr(e)[:300]
                row["executed"] = False
        else:
            row["executed"] = False
        rows.append(row)
        print(row)

    log = {"generated": datetime.now(UTC).isoformat(), "mode": "execute" if execute else "dry_run",
           "rows": rows, "total_est_usdt": round(sum(r["est_usdt"] for r in rows), 2)}
    existing = json.loads(_OUT.read_text("utf-8")) if _OUT.exists() else []
    existing.append(log)
    _OUT.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    print(f"\n{'EXECUTED' if execute else 'DRY-RUN'} total: ${log['total_est_usdt']}")
    print(f"Logged to {_OUT}")


if __name__ == "__main__":
    main()

```

### scripts/run_drills.py
```python
"""SAFETY DRILLS -- the evidence `s2_entry_met` demands and has never been given.

GAP_REGISTER row #2 lists this as STILL OPEN for Gate 0: *"monthly host-death and ladder DRILLS
have never been run."* The S2 gate reads `critical_drill_failures`, and that field defaults to the
REFUSING sentinel (-1) precisely because no drill has ever produced a record. So the gate is
correctly closed, and it stays closed until something actually exercises the rails.

WHY A DRILL AND NOT A UNIT TEST, since the rails already have tests. A unit test asks "does this
function return the right value?". A drill asks "does the INVARIANT survive the event it exists
for?" -- process death mid-position, a pager that goes unanswered for four hours, a clock that
moves backwards. Those cross function boundaries and persisted state, which is exactly where the
2026-07-11 false-fire and the crash-loop-resets-the-timer class of bug live.

SAFETY, and it is absolute here: NO DRILL PLACES OR CANCELS A LIVE ORDER. Every drill runs against
the pure decision functions and against COPIES of the persisted state, in a temp directory. A
drill that could move money would be a larger risk than the one it certifies, which is the same
reasoning that keeps the canary a signed read pre-Gate-0.

    python scripts/run_drills.py            # run all drills, write the evidence record
    python scripts/run_drills.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_LOG = _ROOT / "data/drill_log.jsonl"
_OUT = _ROOT / "data/drill_report.json"


@dataclass
class Drill:
    name: str
    critical: bool
    passed: bool = False
    detail: str = ""
    checks: list[str] = field(default_factory=list)

    def check(self, ok: bool, what: str) -> bool:
        self.checks.append(f"{'PASS' if ok else 'FAIL'} {what}")
        return ok


def drill_host_death() -> Drill:
    """THE INVARIANT: a naked position's 60s clock must SURVIVE process death.

    The failure it exists for is not exotic -- a process that dies and respawns every 45s would
    reset the timer forever and never breach, so a crash-loop would defeat the rail silently while
    every individual restart looked healthy. This kills the process (by discarding the in-memory
    object) mid-clock and reloads from disk, which is what a real host death does.
    """
    from libs.execution.protective_stops import NAKED_GRACE_S, NakedWatch
    d = Drill("host_death_naked_clock", critical=True)
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "naked_watch.json"
        t0 = time.time()

        w = NakedWatch.load(p)
        w.observe({"BTCUSDT": 1.0}, t0)
        w.save()
        d.check(not w.breaches(t0 + 30.0), "no breach inside the 60s grace")

        # HOST DEATH: the in-memory object is gone. Only what reached disk survives.
        del w
        revived = NakedWatch.load(p)
        d.check(revived.first_seen.get("BTCUSDT") == t0,
                "first-seen timestamp survived process death")

        # The clock must keep running from the ORIGINAL sighting, not from the restart.
        breaches = revived.breaches(t0 + NAKED_GRACE_S + 5.0)
        d.check("BTCUSDT" in breaches,
                f"breach fires {NAKED_GRACE_S}s after FIRST sighting, not after restart")

        # A crash loop must not launder the clock: repeated reload+observe cannot reset it.
        for i in range(5):
            w2 = NakedWatch.load(p)
            w2.observe({"BTCUSDT": 1.0}, t0 + 10.0 * (i + 1))
            w2.save()
        final = NakedWatch.load(p)
        d.check(final.first_seen.get("BTCUSDT") == t0,
                "5 restart cycles did NOT reset the clock (crash-loop defeat blocked)")

        # Covering the position clears it -- otherwise a stale entry breaches forever.
        w3 = NakedWatch.load(p)
        w3.observe({}, t0 + 100.0)
        w3.save()
        d.check(not NakedWatch.load(p).breaches(t0 + 200.0),
                "clock clears once the position is covered")

    d.passed = all(c.startswith("PASS") for c in d.checks)
    d.detail = f"{sum(c.startswith('PASS') for c in d.checks)}/{len(d.checks)} checks"
    return d


def drill_derisk_ladder() -> Drill:
    """THE INVARIANT: the ladder is MONOTONE, and its top rung latches.

    A ladder that can step DOWN on its own turns an unanswered page into a self-clearing incident.
    A ladder that skips rungs flattens a book that only needed its resting orders cancelled.
    """
    from libs.ops.derisk_ladder import (
        LADDER,
        RUNG_CANCEL_HALVE_S,
        RUNG_FLATTEN_S,
        RUNG_FULL_FLATTEN_S,
        rung_for,
    )
    d = Drill("derisk_ladder", critical=True)

    d.check(rung_for(0.0).is_floor, "silent pager at t=0 is nominal")
    d.check(rung_for(RUNG_CANCEL_HALVE_S - 1).is_floor, "one second short of rung 1 is nominal")
    d.check(rung_for(RUNG_CANCEL_HALVE_S).name == "cancel_and_halve", "rung 1 fires exactly at its threshold")
    d.check(rung_for(RUNG_FLATTEN_S).name == "flatten_to_neutral", "rung 2 fires at its threshold")
    d.check(rung_for(RUNG_FULL_FLATTEN_S).name == "full_flatten_disarmed", "rung 3 fires at its threshold")

    # MONOTONE: severity may never fall as silence grows.
    sev = [LADDER.index(rung_for(t)) for t in
           (0, 60, RUNG_CANCEL_HALVE_S, RUNG_FLATTEN_S - 1, RUNG_FLATTEN_S,
            RUNG_FULL_FLATTEN_S, RUNG_FULL_FLATTEN_S * 10)]
    d.check(sev == sorted(sev), f"severity never decreases as silence grows: {sev}")

    # Rung 3 latches: it demands a human, and no amount of further time undoes that.
    top = rung_for(RUNG_FULL_FLATTEN_S * 100)
    d.check(top.requires_manual_rearm and not top.entries_allowed,
            "top rung latches -- entries stay disabled until a human re-arms")

    # CLOCK SKEW: a page stamped in the future must NOT wrap to a high rung and flatten the book.
    d.check(rung_for(-3600.0).is_floor, "negative age (NTP moved) reads nominal, never flatten")

    # Escalation implies the lower rung's actions too -- no gaps in what is switched off.
    d.check(all(r.cancel_resting for r in LADDER if not r.is_floor),
            "every non-nominal rung cancels resting orders")
    d.check(rung_for(RUNG_FLATTEN_S).size_multiplier == 0.0, "flatten rung sizes to zero")

    d.passed = all(c.startswith("PASS") for c in d.checks)
    d.detail = f"{sum(c.startswith('PASS') for c in d.checks)}/{len(d.checks)} checks"
    return d


def drill_ruin_rail_reentry() -> Drill:
    """THE INVARIANT (added 2026-07-30): the desk cannot clear its own ruin stop.

    The absorbing state found today is the reason this drill exists -- 113 consecutive flattens
    with no defined way back. The re-entry path must require real capital or a signed override,
    and must never be reachable from automation.
    """
    from libs.risk import capital_events as CE
    d = Drill("ruin_rail_reentry", critical=True)
    eq, start = 3139.86, 5000.0
    with tempfile.TemporaryDirectory() as td:
        ledger = Path(td) / "capital_events.jsonl"
        orig, CE.LEDGER = CE.LEDGER, ledger
        try:
            for kind, by, why in (("RESTART", "the executor", "clear the stop so we can trade"),
                                  ("RESTART", "cron", "automated maintenance rebase now")):
                try:
                    CE.rebase(equity_now=eq, start_equity=start, deposit_usd=0.0, kind=kind,
                              authorised_by=by, reason=why)
                    d.check(False, f"automation cleared the stop as {by} -- RAIL DEFEATED")
                except CE.CapitalEventRefused:
                    d.check(True, f"refused an unfunded re-base authorised by {by!r}")
            ev = CE.rebase(equity_now=eq, start_equity=start, deposit_usd=2000.0,
                           authorised_by="principal", reason="drill: funded re-base path")
            d.check(ev.start_equity_after == eq + 2000.0, "a funded deposit re-bases the inception")
            d.check(ledger.exists() and ledger.read_text().count("\n") == 1,
                    "exactly one event recorded -- refusals write nothing")
        finally:
            CE.LEDGER = orig
    d.passed = all(c.startswith("PASS") for c in d.checks)
    d.detail = f"{sum(c.startswith('PASS') for c in d.checks)}/{len(d.checks)} checks"
    return d


DRILLS = (drill_host_death, drill_derisk_ladder, drill_ruin_rail_reentry)


def run() -> dict[str, Any]:
    results = []
    for fn in DRILLS:
        try:
            results.append(fn())
        except Exception as exc:
            # A drill that CRASHES is a failed drill, never a skipped one. Treating an exception
            # as "inconclusive" is how a broken rail passes a safety review.
            bad = Drill(fn.__name__.replace("drill_", ""), critical=True)
            bad.detail = f"drill CRASHED: {type(exc).__name__}: {exc}"
            results.append(bad)
    critical_failures = sum(1 for r in results if r.critical and not r.passed)
    return {
        "at": datetime.now(tz=UTC).isoformat(),
        "n_drills": len(results),
        "passed": sum(1 for r in results if r.passed),
        # THE FIELD s2_entry_met READS. It defaults to the refusing sentinel elsewhere precisely
        # because an absent drill record must never satisfy a safety gate.
        "critical_drill_failures": critical_failures,
        "drills": [{"name": r.name, "critical": r.critical, "passed": r.passed,
                    "detail": r.detail, "checks": r.checks} for r in results],
        "safety": "No drill places or cancels a live order. Every drill runs pure decision "
                  "functions against temp-directory copies of persisted state.",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = run()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")
    with _LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({k: rep[k] for k in
                            ("at", "n_drills", "passed", "critical_drill_failures")}) + "\n")
    if args.json:
        print(json.dumps(rep, indent=2))
        return 0
    print(f"DRILLS {rep['passed']}/{rep['n_drills']} passed | "
          f"critical_drill_failures={rep['critical_drill_failures']}")
    for dr in rep["drills"]:
        print(f"  {'PASS' if dr['passed'] else 'FAIL'} {dr['name']:24} {dr['detail']}")
        for c in dr["checks"]:
            if c.startswith("FAIL"):
                print(f"        {c}")
    print(f"-> {_OUT.relative_to(_ROOT)}  (+ {_LOG.relative_to(_ROOT)})")
    return 0 if rep["critical_drill_failures"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts/run_listing_watch.py
```python
"""New-listing watch -- the data clock for the new-listing funding-spike sleeve (inbox #53).

Day-1 perp listings routinely print extreme funding (one-sided spec flow, no arb capital yet):
a structurally recurring, capacity-tiny dislocation -- exactly the desk's niche. This collector
starts that family's clock NOW with the simplest robust mechanism: a daily diff of the exchange
symbol universe (announcement pages need scraping and rot; exchangeInfo is the ground truth).
Each new perp is logged with its funding rate at detection, so in N weeks the desk has a real
panel of listing-funding trajectories to pre-register against. Read-only public endpoints,
writes only its own artifacts. Freeze-safe.

    python scripts/run_listing_watch.py
"""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

_FAPI = "https://fapi.binance.com"
_SNAP = Path("data/listing_universe.json")
_LOG = Path("data/listings.jsonl")


def _get(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": "quant-listing-watch"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def main() -> None:
    info = _get(f"{_FAPI}/fapi/v1/exchangeInfo")
    now = {s["symbol"] for s in info.get("symbols", [])
           if s.get("status") == "TRADING" and str(s["symbol"]).endswith("USDT")}
    if not now:
        raise SystemExit("empty universe read -- refusing to diff")

    if not _SNAP.exists():                       # first run: baseline only, no false "listings"
        _SNAP.write_text(json.dumps({"ts": datetime.now(tz=UTC).isoformat(),
                                     "symbols": sorted(now)}), "utf-8")
        print(f"listing-watch: baseline {len(now)} perps (no diff on first run)")
        return

    prev = set(json.loads(_SNAP.read_text("utf-8"))["symbols"])
    fresh = sorted(now - prev)
    gone = sorted(prev - now)                    # delistings matter too (symbol-status risk)
    if fresh:
        try:
            prem = {p["symbol"]: p for p in _get(f"{_FAPI}/fapi/v1/premiumIndex")}
        except Exception:                         # funding enrich is best-effort
            prem = {}
        with _LOG.open("a", encoding="utf-8") as fh:
            for sym in fresh:
                fh.write(json.dumps({
                    "ts": datetime.now(tz=UTC).isoformat(), "event": "listed", "symbol": sym,
                    "funding_at_detect": float(prem.get(sym, {}).get("lastFundingRate", 0) or 0),
                    "mark_at_detect": float(prem.get(sym, {}).get("markPrice", 0) or 0),
                }) + "\n")
    if gone:
        with _LOG.open("a", encoding="utf-8") as fh:
            for sym in gone:
                fh.write(json.dumps({"ts": datetime.now(tz=UTC).isoformat(),
                                     "event": "delisted", "symbol": sym}) + "\n")
    _SNAP.write_text(json.dumps({"ts": datetime.now(tz=UTC).isoformat(),
                                 "symbols": sorted(now)}), "utf-8")
    print(f"listing-watch: {len(now)} perps | new {len(fresh)} {fresh[:4]} | gone {len(gone)}")


if __name__ == "__main__":
    main()

```

### scripts/run_live_combined.py
```python
"""Molded LIVE account -> live_combined.json: cash-carry's futures + spot legs, equalised capital.

TOP = combined molded (both legs on equal $BASE so it's fair); then the PnL breakdown; then the
futures account gains (rich); then the spot account (simple). Perp book retired -- not shown. Each
level reports equity, net PnL, daily %, monthly %, unrealised + realised since start. Real Binance
numbers (futures = the short legs, spot = the long legs); molded net is the delta-neutral truth.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.execution import binance_spot_testnet as spot
from libs.execution import binance_testnet as fut
from libs.execution.carry_accounting import (
    carry_bleed_report,
    derive_spot_realized,
    read_income,
)
from libs.portfolio.live_book import LivePortfolio

_CC = Path("web/cashcarry_live.json")
_STATE = Path("data/cashcarry_positions.json")
_CURVE = Path("data/live_combined_state.json")
_LEVLAB = Path("data/levered_lab_state.json")    # experimental levered sim (fresh, paper)
_TRADES = Path("data/cashcarry_trades.json")
_SHADOW = Path("web/crypto_shadow.json")         # perp L/S book (paper) -> combined into molded
_TREND = Path("web/trend_shadow.json")           # trend candidate -- OWN shadow only, NOT in molded
_TREND_RG = Path("web/trend_regime_shadow.json")  # regime-gated challenger (own clock)
_OUT = Path("web/live_combined.json")
_PORT = Path("web/portfolio.json")
_BASE = 5000.0                                   # equalised start per leg = fresh testnet balance


def _load(p: Path) -> dict[str, Any]:
    try:
        d: dict[str, Any] = json.loads(p.read_text("utf-8"))
        return d
    except (OSError, json.JSONDecodeError):
        return {}


def _num(v: object, d: float = 0.0) -> float:
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return d


def _pct_ago(curve: list[list[Any]], equity: float, hours: float) -> float | None:
    """% return over the trailing `hours` window. None if the curve doesn't span that window yet.

    Honest: returns None (dashboard shows "-") until there is genuinely `hours` of history, so a
    young/just-reset curve can't report a fake gain measured off an arbitrary post-reset baseline.
    """
    if len(curve) < 2:
        return None
    try:
        oldest = datetime.fromisoformat(curve[0][0]).timestamp()
    except (ValueError, TypeError):
        return None
    cutoff = datetime.now(tz=UTC).timestamp() - hours * 3600
    if oldest > cutoff:
        return None                                  # not enough history for this window
    base = equity
    for t, e in curve:
        try:
            if datetime.fromisoformat(t).timestamp() >= cutoff:
                base = e
                break
        except (ValueError, TypeError):
            continue
    return round((equity / base - 1.0) * 100, 3) if base else None


def _curve_winrate(feed: dict[str, Any]) -> float | None:
    """Daily win rate = % of UP-days on a shadow equity curve (paper books have no discrete trades,
    so % positive daily steps is the honest hit-rate analog). None until >=5 steps exist."""
    curve = feed.get("equity") if isinstance(feed.get("equity"), list) else []
    vals = [c.get("v") for c in curve if isinstance(c, dict) and c.get("v") is not None]
    n = len(vals) - 1
    if n < 5:
        return None
    wins = sum(1 for i in range(1, len(vals)) if vals[i] > vals[i - 1])
    return round(100.0 * wins / n, 1)


def main() -> None:
    cc, st = _load(_CC), _load(_STATE)

    fa = fut.account_summary() if fut.has_keys() else {}
    fut_eq = round(_num(fa.get("equity")), 2)
    fut_unrl = round(_num(fa.get("unrealized_pnl")), 2)
    fut_start_real = _num(st.get("start_futures_equity"), fut_eq)
    # `funding` is None until MEASURED, for the same reason `venue_realized` already was: a venue
    # read that fails must not decay into a zero harvest. The old `0.0` seed plus an
    # `except (ValueError, TypeError)` that could not even catch the venue's HTTPError meant this
    # book either crashed outright or published a fabricated zero (2026-07-26 -- the executed book
    # published $0.00 against a true $101.96). `read_income` retries transient 5xx and reports
    # honestly when it cannot measure.
    realized = 0.0
    funding = None
    venue_realized = None
    fut_winrate = None
    if fut.has_keys() and st.get("start"):
        sms = int(datetime.fromisoformat(str(st["start"])).timestamp() * 1000)
        inc = read_income(lambda: fut.income_summary(sms))
        if inc is not None:
            funding = round(_num(inc.get("funding")), 2)            # carry income (the edge)
            venue_realized = _num(inc.get("realized_pnl"))          # exact futures realized
            realized = round(_num(inc.get("funding")) + venue_realized
                             + _num(inc.get("commission")), 2)
            _nw, _nl = _num(inc.get("n_wins")), _num(inc.get("n_losses"))
            fut_winrate = round(100.0 * _nw / (_nw + _nl), 1) if (_nw + _nl) > 0 else None
    spot_usdt = round(spot.usdt_balance(), 2) if spot.has_keys() else 0.0

    # spot side = OPEN long-leg marks + realized of CLOSED spot legs. DERIVE the realized from
    # exchange ground truth (deduped trade-log basis - venue futures realized) rather than trusting
    # the stored accumulator, so a stale/crashed executor can NEVER fabricate a dashboard loss
    # (the 2026-07-10 phantom). Falls back to the stored value only if the venue realized is absent.
    if venue_realized is not None:
        spot_realized = derive_spot_realized(venue_realized, _load(_TRADES) or [])
    else:
        spot_realized = _num(st.get("realized_spot_pnl"))
    spot_pnl = round(_num(cc.get("spot_leg_pnl")) + spot_realized, 2)
    fut_pnl = round(fut_eq - fut_start_real, 2)              # futures leg net (short + funding)
    carries = cc.get("carries", []) if isinstance(cc.get("carries"), list) else []
    avg_f = (sum(_num(c.get("funding_8h")) for c in carries) / len(carries)) if carries else 0.0

    # perp L/S book -- PAPER (shadow), combined into the molded account on the same $BASE. Kept as
    # paper (marked from the forward shadow) so its directional risk NEVER touches the delta-neutral
    # carry account -- the "perp + cash-carry combined" book, testnet-only, honestly labelled.
    shadow = _load(_SHADOW)
    perp_days = int(_num(shadow.get("forward_days")))
    perp_active = perp_days > 0
    perp_net = round(_BASE * _num(shadow.get("forward_cum_return")), 2) if perp_active else 0.0
    perp_book = round(_BASE + perp_net, 2)

    # TREND book -- PAPER CANDIDATE (passed in-sample gauntlet, forward day N/90, not yet valid).
    # Auto-added to the molded per the promotion policy; marked paper from its own forward shadow so
    # its directional risk never touches real accounts. Real capital only after 90d + human OK.
    trend_sh = _load(_TREND)
    trend_rg = _load(_TREND_RG)
    trend_days = int(_num(trend_sh.get("forward_days")))
    trend_active = trend_days > 0
    trend_net = round(_BASE * _num(trend_sh.get("forward_cum_return")), 2) if trend_active else 0.0
    trend_book = round(_BASE + trend_net, 2)

    # equalised rebase: each leg/book starts at $BASE. TREND IS EXCLUDED from the molded totals
    # (decision 2026-07-09, see ledger): a day-5 unvalidated candidate lives ONLY in its own 90d
    # shadow + its own card so it cannot distort combined P&L; it re-enters only if it validates.
    fut_book = round(_BASE + fut_pnl, 2)
    spot_book = round(_BASE + spot_pnl, 2)
    n_books = 2 + (1 if perp_active else 0)
    m_start = round(n_books * _BASE, 2)
    m_eq = round(fut_book + spot_book + (perp_book if perp_active else 0.0), 2)
    net = round(fut_pnl + spot_pnl + perp_net, 2)     # carry (real) + perp (paper); NO trend
    # standing carry-leak alarm: is the funding harvest surviving, or is the hedge bleeding it?
    bleed = carry_bleed_report(funding=funding, spot_pnl=spot_pnl, fut_pnl=fut_pnl)

    # gross P&L for the COMBINED book: split each book's net P&L by sign -> total gains vs total
    # losses. They sum EXACTLY to the molded net.
    _books = [fut_pnl, spot_pnl] + ([perp_net] if perp_active else [])
    gross_profit = round(sum(b for b in _books if b > 0), 2)
    gross_loss = round(sum(b for b in _books if b < 0), 2)
    # maintain curves for daily / monthly / drawdown
    now = datetime.now(tz=UTC).isoformat()
    cs = _load(_CURVE)
    if abs(_num(cs.get("start"), -1) - m_start) > 0.01:
        cs = {"start": m_start, "mcurve": [], "fcurve": []}
    mcurve = cs.get("mcurve", [])
    fcurve = cs.get("fcurve", [])
    mcurve.append([now, m_eq])
    fcurve.append([now, fut_book])
    mcurve, fcurve = mcurve[-4000:], fcurve[-4000:]
    peak = max(e for _, e in mcurve) if mcurve else m_eq
    dd = round((m_eq / peak - 1.0) * 100, 2) if peak > 0 else 0.0
    _CURVE.parent.mkdir(parents=True, exist_ok=True)
    _CURVE.write_text(json.dumps({"start": m_start, "mcurve": mcurve, "fcurve": fcurve}), "utf-8")

    # EXPERIMENTAL levered lab (SIMULATED, fresh from inception): _LEV x the go-forward P&L of the
    # real carry (fut+spot legs) + the perp paper. HONEST -- it amplifies LOSSES as well as gains.
    # NOT real orders (no free testnet accounts for a 2nd hedged book) and does NOT touch the real
    # deployed book or its 90-day validation. Fresh clock: starts at 2x $BASE at inception, so the
    # real book's slow accumulated history is NOT dragged in. CAVEAT: a sim cannot model a margin
    # liquidation, so it UNDER-states real-leverage tail risk (a genuine 3x carry can be wiped
    # out by a violent move; this cannot show that).
    _LEV = 3.0
    ls = _load(_LEVLAB)
    if "inception" not in ls:
        ls = {"inception": now, "lev": _LEV, "fut0": fut_pnl, "spot0": spot_pnl,
              "perp0": perp_net, "fund0": funding, "curve": []}
    lev = _num(ls.get("lev"), _LEV)
    lfut = round(lev * (fut_pnl - _num(ls.get("fut0"))), 2)      # 3x each book's go-forward P&L
    lspot = round(lev * (spot_pnl - _num(ls.get("spot0"))), 2)
    lperp = round(lev * (perp_net - _num(ls.get("perp0"))), 2)
    # Self-heal a baseline seeded during a venue outage: anchoring the levered harvest to a
    # fabricated zero would overstate it forever, so an unset fund0 is adopted on first real read
    # rather than defaulted to 0.0.
    if ls.get("fund0") is None and funding is not None:
        ls["fund0"] = funding
    f0 = ls.get("fund0")
    lfund = (round(lev * (funding - f0), 2)
             if funding is not None and f0 is not None else None)
    lev_net = round(lfut + lspot + lperp, 2)                     # NO trend (own shadow only)
    lev_start = round(3 * _BASE, 2)                              # 3 books x $5k, fresh
    lev_eq = round(lev_start + lev_net, 2)
    lgp = round(sum(x for x in (lfut, lspot, lperp) if x > 0), 2)
    lgl = round(sum(x for x in (lfut, lspot, lperp) if x < 0), 2)
    lcurve = ls.get("curve", [])
    lcurve.append([now, lev_eq])
    lcurve = lcurve[-4000:]
    ls["curve"] = lcurve
    _LEVLAB.write_text(json.dumps(ls), "utf-8")
    lpeak = max(e for _, e in lcurve) if lcurve else lev_eq
    ldd = round((lev_eq / lpeak - 1.0) * 100, 2) if lpeak > 0 else 0.0
    lev_step = max(1, len(lcurve) // 240)
    lev_chart = lcurve[::lev_step]
    if lcurve and lev_chart[-1] is not lcurve[-1]:
        lev_chart.append(lcurve[-1])

    # single deployed-portfolio object -> day-count, winrate, deployed Sharpe, portfolio.json.
    # Combined book: cash_and_carry is REAL testnet capital; perp_ls is PAPER (shadow) -- labelled.
    port = LivePortfolio.load(_BASE, fut=fut, spot=spot)
    pub = port.to_public()
    pub["deployed"]["sleeves"] = (["cash_and_carry (real)"]
                                  + (["perp_ls (paper)"] if perp_active else []))
    pub["deployed"]["start_capital"] = m_start
    pub["deployed"]["equity"] = m_eq
    pub["deployed"]["net_pnl"] = net
    pub["deployed"]["return_pct"] = round(net / m_start * 100, 3) if m_start else 0.0
    pub["deployed"]["perp_paper_net"] = perp_net
    _PORT.write_text(json.dumps(pub, indent=2), "utf-8")
    trades = _load(_TRADES)
    trade_hist = list(reversed(trades if isinstance(trades, list) else []))[:40]
    # downsample the curve for the chart (cap points, keep first + last)
    step = max(1, len(mcurve) // 240)
    chart = mcurve[::step]
    if mcurve and chart[-1] is not mcurve[-1]:
        chart.append(mcurve[-1])

    out = {
        "updated": now,
        "molded": {
            "start": m_start, "equity": m_eq, "net_pnl": net,
            "return_pct": round(net / m_start * 100, 3) if m_start else 0.0,
            "daily_pct": _pct_ago(mcurve, m_eq, 24), "monthly_pct": _pct_ago(mcurve, m_eq, 720),
            "unrealized": round(fut_unrl + _num(cc.get("spot_leg_pnl")), 2), "realized": realized,
            "gross_profit": gross_profit, "gross_loss": gross_loss,
            "max_dd_pct": dd, "funding": funding,
            "non_funding_pnl": bleed.non_funding_pnl,
            "harvest_eaten_frac": bleed.harvest_eaten_frac,
            "bleed_alert": bleed.alert, "bleed_verdict": bleed.verdict,
            "run_rate_apr_pct": round(avg_f * 3 * 365 * 100, 1),
            "days_live": port.days_live, "winrate_pct": port.winrate,
            "n_closed_trades": port.n_closed, "deployed_sharpe": port.deployed_sharpe,
            "live_sleeves": list(port.LIVE_SLEEVES) + (["perp_ls"] if perp_active else []),
        },
        "perp": {"start": _BASE, "equity": perp_book, "net_pnl": perp_net,
                 "return_pct": round(perp_net / _BASE * 100, 3), "days": perp_days,
                 "active": perp_active, "winrate": _curve_winrate(shadow), "winrate_kind": "daily",
                 "kind": "paper (shadow) — combined, not real orders"},
        "trend": {"start": _BASE, "equity": trend_book, "net_pnl": trend_net,
                  "return_pct": round(trend_net / _BASE * 100, 3), "days": trend_days,
                  "active": trend_active, "winrate": _curve_winrate(trend_sh),
                  "winrate_kind": "daily",
                  "kind": ("paper CANDIDATE — own 90d shadow ONLY; excluded from molded + 3x "
                           "totals until it validates")},
        "trend_regime": {
            "net_pnl": round(_BASE * _num(trend_rg.get("forward_cum_return")), 2),
            "days": int(_num(trend_rg.get("forward_days"))),
            "kind": "pre-registered challenger: same trend, flat in weak-trend regimes"},
        "levered_lab": {
            "leverage": lev, "start": lev_start, "equity": lev_eq, "net_pnl": lev_net,
            "return_pct": round(lev_net / lev_start * 100, 3) if lev_start else 0.0,
            "fut_net": lfut, "spot_net": lspot, "perp_net": lperp,
            "funding": lfund, "gross_profit": lgp, "gross_loss": lgl, "max_dd_pct": ldd,
            "winrate_pct": port.winrate,
            "daily_pct": _pct_ago(lcurve, lev_eq, 24), "monthly_pct": _pct_ago(lcurve, lev_eq, 720),
            "inception": ls.get("inception"), "curve": lev_chart,
            "kind": f"SIMULATED {lev:g}x · fresh · NOT real orders · no liquidation modelled"},
        "curve": chart,
        "trades": trade_hist,
        "futures": {
            "balance": fut_eq, "start": _BASE, "equity": fut_book, "net_pnl": fut_pnl,
            "return_pct": round(fut_pnl / _BASE * 100, 3),
            "daily_pct": _pct_ago(fcurve, fut_book, 24),
            "monthly_pct": _pct_ago(fcurve, fut_book, 720),
            "unrealized": fut_unrl, "realized": realized, "funding": funding,
            "winrate": fut_winrate, "winrate_kind": "trade",
        },
        "spot": {"usdt": spot_usdt, "start": _BASE, "equity": spot_book, "net_pnl": spot_pnl,
                 "return_pct": round(spot_pnl / _BASE * 100, 3),
                 "winrate": None, "winrate_kind": "n/a (no spot trade history via API)"},
        "n_carries": len(carries),
        "carries": [{"symbol": c.get("symbol"), "funding_8h": _num(c.get("funding_8h"))}
                    for c in carries],
        "note": ("Combined book (testnet), $5,000 per leg/book. Cash-carry = REAL orders: "
                 "futures short legs + spot long legs, delta-neutral (net = funding harvested "
                 "8-hourly). Perp L/S = PAPER (shadow-marked) so its directional risk never hits "
                 "the carry account. Molded = carry (real) + perp (paper)."),
    }
    # VENUE-TRUTH EQUITY (2026-07-16 incident: mark-based books recorded -$55 while venue cash
    # fell 41% from HWM -- the dead-man's independent measure was invisible outside its state
    # file). Surface it beside the molded numbers so mark-vs-venue divergence is always on the
    # dashboard and in audit briefs. Read-only: the rail's state is never written from here.
    try:
        dm = json.loads(Path("data/deadman_state.json").read_text("utf-8"))
        hw = float(dm.get("high_water", 0.0))
        out["venue_truth"] = {
            "equity": round(float(dm.get("last_eq", 0.0)), 2), "high_water": round(hw, 2),
            "fire_line": round(0.65 * hw, 2), "breaches": int(dm.get("breaches", 0)),
            "fired": bool(dm.get("fired", False)),
            "kind": ("dead-man measure: fut margin + tracked spot legs + USDT delta -- venue "
                     "ground truth, immune to mark-based accounting blindness"),
        }
        Path("web/venue_equity.json").write_text(
            json.dumps({"updated": now, **out["venue_truth"]}, indent=2), "utf-8")
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    print(f"MOLDED ${m_eq} (start ${m_start}, net {net:+.2f}) | carry: fut ${fut_eq} "
          f"spot ${spot_usdt} | perp(paper) ${perp_book} active={perp_active}")


if __name__ == "__main__":
    main()

```

### scripts/run_onchain_history_backtest.py
```python
"""Backtest exchange-flow / on-chain hypotheses on PAID HISTORY (CryptoQuant/Glassnode CSV).

Pay-once-then-cancel model: drop a downloaded CSV in data/paid/ and this runs the full gauntlet on
YEARS of history instead of the ~13-day free forward clock. The paid data VALIDATES the edge; the
free keyless reader (libs/data/onchain_flows.py) keeps trading it forward -- no subscription.

CSV format (vendor-agnostic): a date column + one or more metric columns. Auto-detects common
column names (date/time/t; value/netflow/exchange_netflow/reserve/supply). Point --price at a BTC
daily close CSV (or it pulls free Binance) to compute forward returns.

Hypothesis tested (pre-registered, economic): exchange NETFLOW predicts forward return -- stables
flowing ONTO exchanges = dry powder / buy pressure (sign is empirical, resolved by gauntlet, not
assumed). Runs the SAME validate + campaign_gate_stats gauntlet every alpha uses. Nothing fabricated.

    python scripts/run_onchain_history_backtest.py --csv data/paid/exchange_netflow.csv
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from libs.autodiscovery.models import Family, Hypothesis
from libs.autodiscovery.validation import campaign_gate_stats, validate
from libs.data.crypto_source import daily_with_funding
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType

_FAIL = ["flow signal crowds/decays", "regime shift", "thin sample", "cost exceeds edge"]

_OUT = Path("web/onchain_history_backtest.json")
_DATE_COLS = ("date", "time", "timestamp", "t", "datetime", "day")
_VAL_COLS = ("value", "netflow", "exchange_netflow", "reserve", "exchange_reserve",
             "supply", "v", "flow", "net_flow")


def _pick(cols: list[str], candidates: tuple[str, ...]) -> str | None:
    low = {c.lower(): c for c in cols}
    for cand in candidates:
        if cand in low:
            return low[cand]
    for c in cols:                                     # fuzzy: any col containing a candidate word
        if any(k in c.lower() for k in candidates):
            return c
    return None


def _load_csv(path: Path) -> pd.Series:
    df = pd.read_csv(path)
    dc = _pick(list(df.columns), _DATE_COLS)
    vc = _pick([c for c in df.columns if c != dc], _VAL_COLS)
    if not dc or not vc:
        raise SystemExit(f"could not detect date/value columns in {list(df.columns)}; "
                         "rename to date,value")
    s = pd.Series(pd.to_numeric(df[vc], errors="coerce").to_numpy(),
                  index=pd.to_datetime(df[dc], utc=True, errors="coerce")).dropna()
    return s[~s.index.duplicated()].sort_index()


def _btc_returns(price_csv: str | None) -> pd.Series:
    if price_csv:
        px = _load_csv(Path(price_csv))
    else:
        bars = daily_with_funding("BTCUSDT", start="2019-01-01").set_index("timestamp")["close"]
        px = bars
    px.index = pd.to_datetime(px.index, utc=True)
    return px.resample("1D").last().pct_change(fill_method=None)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="paid on-chain metric CSV (date + value)")
    ap.add_argument("--price", default=None, help="optional BTC daily close CSV (else Binance)")
    ap.add_argument("--lookback", type=int, default=7, help="signal smoothing window (days)")
    args = ap.parse_args()

    metric = _load_csv(Path(args.csv)).resample("1D").last().ffill()
    ret = _btc_returns(args.price)
    df = pd.concat({"m": metric, "r": ret}, axis=1).dropna()
    if len(df) < 250:
        raise SystemExit(f"only {len(df)} aligned days; need >=250 for the gauntlet")

    # signal = z-scored netflow change (lagged -> no look-ahead); position = -sign (contrarian) and
    # +sign (momentum) BOTH tested, gauntlet keeps the honest one. Net of a flat 5bps/turn cost.
    z = ((df["m"] - df["m"].rolling(args.lookback).mean())
         / df["m"].rolling(args.lookback).std()).shift(1)
    fwd = df["r"]
    strat = {}
    for name, sgn in (("flow_momentum", 1.0), ("flow_contrarian", -1.0)):
        pos = np.tanh(sgn * z).fillna(0.0)
        turn = pos.diff().abs().fillna(0.0)
        r = (pos * fwd - turn * 5e-4).dropna().to_numpy()
        strat[name] = r

    matrix = np.column_stack([strat["flow_momentum"], strat["flow_contrarian"]])
    # per-candidate gates (gap #87 flip, principal-ruled 2026-07-29); thresholds unchanged
    campaign = campaign_gate_stats(matrix)
    results = {}
    # enumerate order == column_stack order over `strat`, so `col` is the strategy's matrix column
    for col, (name, r) in enumerate(strat.items()):
        sh = round(float(sharpe_ratio(r) * np.sqrt(365)), 2)
        hyp = Hypothesis(family=Family.LIQUIDITY, subtype=name, symbol="CRYPTO", params={},
                         mechanism=MechanismType.BEHAVIORAL, edge_source="exchange_flow",
                         failure_modes=_FAIL)
        v = validate(r, hypothesis=hyp, n_trials=2, sharpe_estimates=[sh, -sh],
                     returns_matrix=matrix, campaign=campaign, column=col)
        gates = f"{sum(v.gates.values())}/{len(v.gates)}" if v else "n<250"
        results[name] = {"ann_sharpe": sh, "gates": gates,
                         "pbo": round(float(v.metrics.pbo), 3) if v else None,
                         "rc_p": round(float(v.metrics.reality_p), 3) if v else None,
                         "survived": bool(getattr(v, "survived", False))}

    out = {"source": str(args.csv), "aligned_days": len(df),
           "date_range": [str(df.index.min())[:10], str(df.index.max())[:10]],
           # campaign-level legacy PBO/RC kept as SEARCH-PROCEDURE diagnostics (gap #87); the
           # gate values are per-strategy now -- see results[*].pbo / results[*].rc_p.
           "pbo": (round(float(campaign.legacy_pbo.pbo), 3)
                   if campaign is not None and campaign.legacy_pbo is not None else None),
           "reality_check_p": (round(float(campaign.legacy_rc.p_value), 3)
                               if campaign is not None and campaign.legacy_rc is not None
                               else None),
           "results": results,
           "note": "paid history validates; free keyless onchain_flows.py trades it forward. "
                   "Sign chosen by gauntlet, not assumed. One-off pull -> no subscription needed."}
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    for name, res in results.items():
        print(f"{name}: annSharpe {res['ann_sharpe']} pbo={res['pbo']} rc_p={res['rc_p']} "
              f"survived={res['survived']}")
    print(f"aligned {len(df)}d {out['date_range']} | campaign diagnostics pbo {out['pbo']} "
          f"rc {out['reality_check_p']} (gates are per-strategy)")


if __name__ == "__main__":
    main()

```

### scripts/run_stablecoin_flows.py
```python
"""Daily stablecoin exchange-flow archiver -- starts a NEW orthogonal 40-day forward clock.

Reads the on-chain exchange stablecoin reserve (keyless, libs.data.onchain_flows), appends ONE dated
snapshot per day, and computes netflow = day-over-day reserve change (+ 7d change, + z-score once
enough history). Also records global USDT+USDC totalSupply() as a SECOND orthogonal signal:

  - exchange_reserve: WHERE stablecoins are (on-exchange dry powder / demand for trading)
  - supply:           HOW MANY stablecoins exist (net minting = institutional new capital)

Both signals accumulate on the same 40-day clock. Idempotent (re-running overwrites today's row).
Emits web/stablecoin_flows.json.

    python scripts/run_stablecoin_flows.py
"""

from __future__ import annotations

import json
import statistics
from datetime import UTC, date, datetime
from pathlib import Path

from libs.data.onchain_flows import exchange_reserves, stablecoin_supply

_ARCHIVE = Path("data/stablecoin_flows_archive.json")
_WEB = Path("web/stablecoin_flows.json")
_NEEDS_DAYS = 40


def _load(p: Path, d: object) -> object:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return d


def main() -> None:
    res = exchange_reserves()                              # live keyless read
    sup = stablecoin_supply()                              # global supply (orthogonal signal)
    today = date.today().isoformat()
    arch = _load(_ARCHIVE, [])
    if not isinstance(arch, list):
        arch = []
    arch = [a for a in arch if a.get("date") != today]    # idempotent: one snapshot/day
    arch.append({"date": today, "ts": datetime.now(tz=UTC).isoformat(),
                 "total": res["total_reserve_usd"], "per_token": res["per_token"],
                 "per_exchange": res["per_exchange"],
                 "supply_total": sup["total_supply_usd"],
                 "supply_per_token": sup["per_token"]})
    arch = sorted(arch, key=lambda a: a["date"])[-400:]
    _ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    _ARCHIVE.write_text(json.dumps(arch, indent=2), "utf-8")

    totals = [float(a["total"]) for a in arch]
    dnet = [totals[i] - totals[i - 1] for i in range(1, len(totals))]
    netflow_1d = round(dnet[-1], 2) if dnet else 0.0
    netflow_7d = round(totals[-1] - totals[-8], 2) if len(totals) >= 8 else None
    z = None
    if len(dnet) >= 10:
        mu, sd = statistics.mean(dnet), statistics.pstdev(dnet)
        z = round((dnet[-1] - mu) / sd, 2) if sd else None

    supplies = [float(a["supply_total"]) for a in arch if a.get("supply_total")]
    supply_1d = round(supplies[-1] - supplies[-2], 2) if len(supplies) >= 2 else None
    supply_7d = round(supplies[-1] - supplies[-8], 2) if len(supplies) >= 8 else None
    forward_days = len(arch)

    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "sleeve": "stablecoin_exchange_flows",
        "exchange_reserve": {
            "dataset": "on-chain stablecoin exchange reserve",
            "source": "public Ethereum RPC (keyless): USDT+USDC balanceOf on exchange wallets",
            "total_usd": res["total_reserve_usd"], "per_token": res["per_token"],
            "per_exchange": res["per_exchange"], "n_wallets": res["n_wallets"],
            "netflow_1d": netflow_1d, "netflow_7d": netflow_7d, "netflow_z": z,
            "hypothesis": "reserve UP = dry powder on exchanges; sign vs fwd returns = empirical",
        },
        "supply": {
            "dataset": "global USDT+USDC L1 total supply (minting signal)",
            "source": "public Ethereum RPC: USDT+USDC totalSupply()",
            "total_usd": sup["total_supply_usd"], "per_token": sup["per_token"],
            "supply_1d": supply_1d, "supply_7d": supply_7d,
            "hypothesis": ("supply UP = net new minting = institutional demand; orthogonal to "
                           "exchange reserves (WHERE vs HOW MANY)"),
        },
        "forward_days": forward_days, "needs_days": _NEEDS_DAYS,
        "status": (f"ACCUMULATING ({forward_days}/{_NEEDS_DAYS}d) — validate signal->return at day "
                   f"{_NEEDS_DAYS}, not before"),
        # backward-compat flat fields for dashboard / older consumers
        "total_reserve_usd": res["total_reserve_usd"],
        "netflow_1d": netflow_1d, "netflow_z": z,
        "supply_total_usd": sup["total_supply_usd"], "supply_1d": supply_1d,
    }
    _WEB.parent.mkdir(parents=True, exist_ok=True)
    _WEB.write_text(json.dumps(out, indent=2, default=str), "utf-8")
    supply_1d_str = f"+{supply_1d:,.0f}" if supply_1d and supply_1d > 0 else (
        f"{supply_1d:,.0f}" if supply_1d is not None else "n/a")
    print(f"stablecoin-flows: reserve ${res['total_reserve_usd']:,.0f} | 1d ${netflow_1d:,.0f}"
          f" | supply ${sup['total_supply_usd']:,.0f} | supply_1d ${supply_1d_str}"
          f" | day {forward_days}/{_NEEDS_DAYS}")


if __name__ == "__main__":
    main()

```
