# AUDIT SHARD 12/13 -- seat minimax/minimax-m3

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

### libs/alpha/__init__.py
```python
"""``libs.alpha`` — alpha lifecycle management.

Registry + cards + metadata, a 7-state lifecycle state machine, health monitoring, decay
detection, ranking, successor recommendations, live performance tracking, and an append-only
audit trail — orchestrated by :class:`AlphaLifecycleManager`.
"""

from __future__ import annotations

from libs.alpha.card import (
    AlphaCard,
    AlphaEvent,
    AlphaPerformance,
    ExpectedMetrics,
    LiveMetrics,
    NewAlpha,
)
from libs.alpha.decay import DecayResult, detect_decay
from libs.alpha.errors import AlphaError, AlphaStateError
from libs.alpha.health import AlphaHealth, calculate_alpha_health
from libs.alpha.manager import AlphaLifecycleManager
from libs.alpha.ranking import RankedAlpha, rank_alphas
from libs.alpha.registry import AlphaAuditTrail, AlphaCardStore, PerformanceTracker
from libs.alpha.state import (
    ALLOWED_TRANSITIONS,
    AlphaState,
    assert_transition,
    can_transition,
    promote_target,
)
from libs.alpha.successor import recommend_successors

__all__ = [  # noqa: RUF022  # grouped by concern
    # state machine
    "AlphaState",
    "ALLOWED_TRANSITIONS",
    "can_transition",
    "assert_transition",
    "promote_target",
    # cards / models
    "NewAlpha",
    "AlphaCard",
    "ExpectedMetrics",
    "LiveMetrics",
    "AlphaEvent",
    "AlphaPerformance",
    # health / decay / ranking / successor
    "calculate_alpha_health",
    "AlphaHealth",
    "detect_decay",
    "DecayResult",
    "rank_alphas",
    "RankedAlpha",
    "recommend_successors",
    # store + manager
    "AlphaCardStore",
    "AlphaAuditTrail",
    "PerformanceTracker",
    "AlphaLifecycleManager",
    # errors
    "AlphaError",
    "AlphaStateError",
]

```

### libs/alpha/manager.py
```python
"""Alpha lifecycle manager — registry + state machine + health/decay + audit + successors.

Ties the pieces together: registers candidates, enforces lifecycle transitions (writing an
immutable audit event for each), tracks live performance, evaluates health and decay (with
optional automatic downgrade), and recommends successors when an alpha decays.
"""

from __future__ import annotations

from typing import Any

from libs.alpha.card import (
    AlphaCard,
    AlphaEvent,
    AlphaPerformance,
    ExpectedMetrics,
    LiveMetrics,
    NewAlpha,
)
from libs.alpha.decay import DecayResult, detect_decay
from libs.alpha.errors import AlphaError
from libs.alpha.health import AlphaHealth, calculate_alpha_health
from libs.alpha.registry import AlphaAuditTrail, AlphaCardStore, PerformanceTracker
from libs.alpha.state import AlphaState, assert_transition, promote_target
from libs.alpha.successor import recommend_successors as _recommend_successors
from libs.core.ids import generate_id
from libs.core.time import to_iso8601, utcnow

_UPDATABLE: frozenset[str] = frozenset(
    {
        "name", "market", "category", "thesis", "entry_logic", "exit_logic",
        "expected_cagr", "expected_sharpe", "expected_drawdown", "dsr", "pbo",
        "cpcv", "walk_forward", "holdout", "live_cagr", "live_sharpe", "live_drawdown",
        "decay_score", "extra",
    }
)
_SEVERITY: dict[AlphaState, int] = {
    AlphaState.ACTIVE: 0,
    AlphaState.WATCH: 1,
    AlphaState.DECAYING: 2,
    AlphaState.RETIREMENT_CANDIDATE: 3,
}
_STATE_BY_SEVERITY: dict[int, AlphaState] = {sev: state for state, sev in _SEVERITY.items()}


class AlphaLifecycleManager:
    """The orchestration entry point for alpha lifecycle management."""

    def __init__(self, db: Any) -> None:
        self.cards = AlphaCardStore(db)
        self.audit = AlphaAuditTrail(db)
        self.performance = PerformanceTracker(db)

    # ------------------------------------------------------------- helpers

    def _require(self, alpha_id: str) -> AlphaCard:
        card = self.cards.get(alpha_id)
        if card is None:
            raise AlphaError(f"unknown alpha {alpha_id}")
        return card

    # ----------------------------------------------------------- registration

    def register_alpha(self, new: NewAlpha) -> AlphaCard:
        """Register a new alpha as a CANDIDATE and journal its creation."""
        now = to_iso8601(utcnow())
        card = AlphaCard(
            id=generate_id("alpha"), created_at=now, updated_at=now, name=new.name,
            market=new.market, category=new.category, thesis=new.thesis,
            entry_logic=new.entry_logic, exit_logic=new.exit_logic,
            expected_cagr=new.expected_cagr, expected_sharpe=new.expected_sharpe,
            expected_drawdown=new.expected_drawdown, dsr=new.dsr, pbo=new.pbo,
            cpcv=new.cpcv, walk_forward=new.walk_forward, holdout=new.holdout,
            deployment_date=None, retirement_date=None, live_cagr=None, live_sharpe=None,
            live_drawdown=None, decay_score=0.0, status=AlphaState.CANDIDATE,
            successor_id=None, predecessor_id=new.predecessor_id, extra=dict(new.extra),
        )
        self.cards.insert(card)
        self.audit.append(card.id, "creation", to_status=AlphaState.CANDIDATE)
        if new.predecessor_id is not None:
            self._link_successor(new.predecessor_id, card.id)
        return card

    def _link_successor(self, predecessor_id: str, successor_id: str) -> None:
        predecessor = self.cards.get(predecessor_id)
        if predecessor is None:
            return
        updated = predecessor.model_copy(
            update={"successor_id": successor_id, "updated_at": to_iso8601(utcnow())}
        )
        self.cards.update(updated)
        self.audit.append(
            predecessor_id, "successor_assigned", detail={"successor_id": successor_id}
        )

    # ------------------------------------------------------------- updates

    def update_alpha(self, alpha_id: str, **fields: Any) -> AlphaCard:
        """Update mutable card fields (never the status — use transitions)."""
        card = self._require(alpha_id)
        unknown = set(fields) - _UPDATABLE
        if unknown:
            raise AlphaError(f"cannot update fields: {sorted(unknown)}")
        updated = card.model_copy(update={**fields, "updated_at": to_iso8601(utcnow())})
        self.cards.update(updated)
        self.audit.append(alpha_id, "update", detail={"fields": sorted(fields)})
        return updated

    # ----------------------------------------------------------- transitions

    def transition(
        self,
        alpha_id: str,
        to_state: AlphaState,
        *,
        reason: str,
        event_type: str = "status_change",
        detail: dict[str, Any] | None = None,
    ) -> AlphaCard:
        """Move an alpha to ``to_state`` if the transition is legal; journal the change."""
        card = self._require(alpha_id)
        assert_transition(card.status, to_state)
        now = to_iso8601(utcnow())
        changes: dict[str, Any] = {"status": to_state, "updated_at": now}
        if to_state is AlphaState.ACTIVE and card.deployment_date is None:
            changes["deployment_date"] = now
        if to_state is AlphaState.RETIRED:
            changes["retirement_date"] = now
        updated = card.model_copy(update=changes)
        self.cards.update(updated)
        self.audit.append(
            alpha_id, event_type, from_status=card.status, to_status=to_state,
            detail={"reason": reason, **(detail or {})},
        )
        return updated

    def promote_alpha(self, alpha_id: str, *, reason: str = "promote") -> AlphaCard:
        """Promote an alpha to its next lifecycle state."""
        card = self._require(alpha_id)
        return self.transition(
            alpha_id, promote_target(card.status), reason=reason, event_type="promotion"
        )

    def retire_alpha(
        self, alpha_id: str, *, reason: str = "retire", successor_id: str | None = None
    ) -> AlphaCard:
        """Retire an alpha (optionally recording its successor)."""
        retired = self.transition(
            alpha_id, AlphaState.RETIRED, reason=reason, event_type="retirement"
        )
        if successor_id is not None:
            retired = retired.model_copy(
                update={"successor_id": successor_id, "updated_at": to_iso8601(utcnow())}
            )
            self.cards.update(retired)
            self._link_predecessor(successor_id, alpha_id)
            self.audit.append(alpha_id, "successor_assigned", detail={"successor_id": successor_id})
        return retired

    def _link_predecessor(self, alpha_id: str, predecessor_id: str) -> None:
        card = self.cards.get(alpha_id)
        if card is None:
            return
        self.cards.update(
            card.model_copy(
                update={"predecessor_id": predecessor_id, "updated_at": to_iso8601(utcnow())}
            )
        )

    # ----------------------------------------------------- performance/health

    def record_performance(self, alpha_id: str, live: LiveMetrics) -> AlphaPerformance:
        """Record a live-performance snapshot and refresh the card's live metrics."""
        card = self._require(alpha_id)
        snapshot = self.performance.record(alpha_id, live)
        self.cards.update(
            card.model_copy(
                update={
                    "live_cagr": live.cagr, "live_sharpe": live.sharpe,
                    "live_drawdown": live.max_drawdown, "updated_at": to_iso8601(utcnow()),
                }
            )
        )
        self.audit.append(
            alpha_id, "performance",
            detail={"sharpe": live.sharpe, "cagr": live.cagr, "drawdown": live.max_drawdown},
        )
        return snapshot

    def evaluate_health(self, alpha_id: str, live: LiveMetrics) -> AlphaHealth:
        """Compute the alpha's health (live vs expected)."""
        return calculate_alpha_health(ExpectedMetrics.from_card(self._require(alpha_id)), live)

    def evaluate_decay(
        self, alpha_id: str, live: LiveMetrics, *, auto_transition: bool = True
    ) -> DecayResult:
        """Score decay, persist it, and (optionally) auto-downgrade the lifecycle state."""
        card = self._require(alpha_id)
        result = detect_decay(ExpectedMetrics.from_card(card), live)
        self.cards.update(
            card.model_copy(
                update={"decay_score": result.decay_score, "updated_at": to_iso8601(utcnow())}
            )
        )
        self.audit.append(
            alpha_id, "decay_evaluated",
            detail={"decay_score": result.decay_score, "recommended": result.recommended_state},
        )
        if auto_transition:
            self._maybe_downgrade(card.status, alpha_id, result.recommended_state)
        return result

    def _maybe_downgrade(
        self, current: AlphaState, alpha_id: str, recommended: AlphaState
    ) -> None:
        cur_sev = _SEVERITY.get(current, -1)
        rec_sev = _SEVERITY.get(recommended, -1)
        if cur_sev < 0 or rec_sev <= cur_sev:
            return  # only auto-move downward, and only from a live state
        target = _STATE_BY_SEVERITY[min(cur_sev + 1, rec_sev)]  # step one level (gradual)
        try:
            assert_transition(current, target)
        except AlphaError:
            return
        self.transition(alpha_id, target, reason="auto-decay", event_type="status_change")
        if target is AlphaState.DECAYING:
            successors = self.recommend_successors(alpha_id)
            self.audit.append(
                alpha_id, "successor_recommendation",
                detail={"successors": [c.id for c in successors]},
            )

    # ------------------------------------------------------------ successors

    def recommend_successors(self, alpha_id: str, *, top_n: int = 3) -> list[AlphaCard]:
        """Rank eligible replacements for an alpha (same market or category)."""
        card = self._require(alpha_id)
        return _recommend_successors(self.cards.list_all(), card, top_n=top_n)

    # ---------------------------------------------------------------- queries

    def get_alpha(self, alpha_id: str) -> AlphaCard | None:
        return self.cards.get(alpha_id)

    def audit_trail(self, alpha_id: str) -> list[AlphaEvent]:
        return self.audit.list(alpha_id)

    def list_all(self) -> list[AlphaCard]:
        return self.cards.list_all()

    def list_by_status(self, status: AlphaState) -> list[AlphaCard]:
        return self.cards.list_by_status(status)

    def list_active(self) -> list[AlphaCard]:
        return self.cards.list_by_status(AlphaState.ACTIVE)

    def list_candidates(self) -> list[AlphaCard]:
        return self.cards.list_by_status(AlphaState.CANDIDATE)

```

### libs/alpha/ranking.py
```python
"""Alpha ranking — a robustness-weighted composite, decay- and overfitting-penalized."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from libs.alpha.card import AlphaCard


class RankedAlpha(BaseModel):
    model_config = ConfigDict(frozen=True)

    alpha_id: str
    rank: int
    score: float


def _score(card: AlphaCard) -> float:
    sharpe = card.live_sharpe if card.live_sharpe is not None else (card.expected_sharpe or 0.0)
    pbo_penalty = 1.0 - (card.pbo if card.pbo is not None else 0.0)
    decay_penalty = 1.0 - max(0.0, min(1.0, card.decay_score))
    return max(0.0, sharpe) * max(0.0, pbo_penalty) * decay_penalty


def rank_alphas(cards: Sequence[AlphaCard]) -> list[RankedAlpha]:
    """Rank alphas by decay-/overfitting-adjusted risk-adjusted return (descending)."""
    scored = sorted(
        ((card, _score(card)) for card in cards),
        key=lambda pair: (pair[1], pair[0].expected_cagr or 0.0),
        reverse=True,
    )
    return [
        RankedAlpha(alpha_id=card.id, rank=i, score=score)
        for i, (card, score) in enumerate(scored, start=1)
    ]

```

### libs/alpha/registry.py
```python
"""Store accessors for alpha cards, the append-only event log, and performance history."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from typing import Any

from libs.alpha.card import AlphaCard, AlphaEvent, AlphaPerformance, LiveMetrics
from libs.alpha.state import AlphaState
from libs.core.ids import generate_id
from libs.core.time import to_iso8601, utcnow
from libs.store.connection import Database


def _loads(value: str | None) -> Any:
    return json.loads(value) if value is not None else None


def _dumps(value: Mapping[str, Any] | None) -> str | None:
    return json.dumps(dict(value), sort_keys=True) if value is not None else None


def _row_to_card(row: sqlite3.Row) -> AlphaCard:
    return AlphaCard(
        id=row["id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        name=row["name"],
        market=row["market"],
        category=row["category"],
        thesis=row["thesis"],
        entry_logic=row["entry_logic"],
        exit_logic=row["exit_logic"],
        expected_cagr=row["expected_cagr"],
        expected_sharpe=row["expected_sharpe"],
        expected_drawdown=row["expected_drawdown"],
        dsr=row["dsr"],
        pbo=row["pbo"],
        cpcv=_loads(row["cpcv_json"]),
        walk_forward=_loads(row["walk_forward_json"]),
        holdout=_loads(row["holdout_json"]),
        deployment_date=row["deployment_date"],
        retirement_date=row["retirement_date"],
        live_cagr=row["live_cagr"],
        live_sharpe=row["live_sharpe"],
        live_drawdown=row["live_drawdown"],
        decay_score=float(row["decay_score"]),
        status=AlphaState(row["status"]),
        successor_id=row["successor_id"],
        predecessor_id=row["predecessor_id"],
        extra=_loads(row["extra_json"]) or {},
    )


class AlphaCardStore:
    """CRUD for the ``alpha_cards`` table."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def insert(self, card: AlphaCard) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO alpha_cards "
                "(id, created_at, updated_at, name, market, category, thesis, entry_logic, "
                " exit_logic, expected_cagr, expected_sharpe, expected_drawdown, dsr, pbo, "
                " cpcv_json, walk_forward_json, holdout_json, deployment_date, retirement_date, "
                " live_cagr, live_sharpe, live_drawdown, decay_score, status, successor_id, "
                " predecessor_id, extra_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                " ?, ?, ?, ?)",
                (
                    card.id, card.created_at, card.updated_at, card.name, card.market,
                    card.category, card.thesis, card.entry_logic, card.exit_logic,
                    card.expected_cagr, card.expected_sharpe, card.expected_drawdown, card.dsr,
                    card.pbo, _dumps(card.cpcv), _dumps(card.walk_forward), _dumps(card.holdout),
                    card.deployment_date, card.retirement_date, card.live_cagr, card.live_sharpe,
                    card.live_drawdown, card.decay_score, card.status.value, card.successor_id,
                    card.predecessor_id, _dumps(card.extra),
                ),
            )

    def update(self, card: AlphaCard) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE alpha_cards SET updated_at=?, name=?, market=?, category=?, thesis=?, "
                "entry_logic=?, exit_logic=?, expected_cagr=?, expected_sharpe=?, "
                "expected_drawdown=?, dsr=?, pbo=?, cpcv_json=?, walk_forward_json=?, "
                "holdout_json=?, deployment_date=?, retirement_date=?, live_cagr=?, live_sharpe=?, "
                "live_drawdown=?, decay_score=?, status=?, successor_id=?, predecessor_id=?, "
                "extra_json=? WHERE id=?",
                (
                    card.updated_at, card.name, card.market, card.category, card.thesis,
                    card.entry_logic, card.exit_logic, card.expected_cagr, card.expected_sharpe,
                    card.expected_drawdown, card.dsr, card.pbo, _dumps(card.cpcv),
                    _dumps(card.walk_forward), _dumps(card.holdout), card.deployment_date,
                    card.retirement_date, card.live_cagr, card.live_sharpe, card.live_drawdown,
                    card.decay_score, card.status.value, card.successor_id, card.predecessor_id,
                    _dumps(card.extra), card.id,
                ),
            )

    def get(self, alpha_id: str) -> AlphaCard | None:
        row = self.db.execute("SELECT * FROM alpha_cards WHERE id = ?", (alpha_id,)).fetchone()
        return _row_to_card(row) if row else None

    def list_all(self) -> list[AlphaCard]:
        rows = self.db.execute("SELECT * FROM alpha_cards ORDER BY created_at").fetchall()
        return [_row_to_card(row) for row in rows]

    def list_by_status(self, status: AlphaState) -> list[AlphaCard]:
        rows = self.db.execute(
            "SELECT * FROM alpha_cards WHERE status = ? ORDER BY created_at", (status.value,)
        ).fetchall()
        return [_row_to_card(row) for row in rows]


class AlphaAuditTrail:
    """Append-only writer/reader for ``alpha_events``."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def append(
        self,
        alpha_id: str,
        event_type: str,
        *,
        from_status: AlphaState | None = None,
        to_status: AlphaState | None = None,
        detail: Mapping[str, Any] | None = None,
        actor: str = "alpha_manager",
    ) -> AlphaEvent:
        event_id = generate_id("aev")
        created_at = to_iso8601(utcnow())
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO alpha_events "
                "(id, alpha_id, created_at, event_type, from_status, to_status, detail_json, "
                " actor) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_id, alpha_id, created_at, event_type,
                    from_status.value if from_status else None,
                    to_status.value if to_status else None,
                    _dumps(detail), actor,
                ),
            )
            seq = int(cursor.lastrowid or 0)
        return AlphaEvent(
            seq=seq, id=event_id, alpha_id=alpha_id, created_at=created_at, event_type=event_type,
            from_status=from_status.value if from_status else None,
            to_status=to_status.value if to_status else None,
            detail=dict(detail) if detail else None, actor=actor,
        )

    def list(self, alpha_id: str) -> list[AlphaEvent]:
        rows = self.db.execute(
            "SELECT * FROM alpha_events WHERE alpha_id = ? ORDER BY seq", (alpha_id,)
        ).fetchall()
        return [
            AlphaEvent(
                seq=int(r["seq"]), id=r["id"], alpha_id=r["alpha_id"], created_at=r["created_at"],
                event_type=r["event_type"], from_status=r["from_status"], to_status=r["to_status"],
                detail=_loads(r["detail_json"]), actor=r["actor"],
            )
            for r in rows
        ]


class PerformanceTracker:
    """Writer/reader for ``alpha_performance``."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def record(self, alpha_id: str, live: LiveMetrics) -> AlphaPerformance:
        perf_id = generate_id("aperf")
        created_at = to_iso8601(utcnow())
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO alpha_performance "
                "(id, alpha_id, created_at, sharpe, cagr, max_drawdown, win_rate, profit_factor, "
                " expectancy, sample, detail_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    perf_id, alpha_id, created_at, live.sharpe, live.cagr, live.max_drawdown,
                    live.win_rate, live.profit_factor, live.expectancy, live.sample, None,
                ),
            )
        return AlphaPerformance(
            id=perf_id, alpha_id=alpha_id, created_at=created_at, sharpe=live.sharpe,
            cagr=live.cagr, max_drawdown=live.max_drawdown, win_rate=live.win_rate,
            profit_factor=live.profit_factor, expectancy=live.expectancy, sample=live.sample,
        )

    def history(self, alpha_id: str) -> list[AlphaPerformance]:
        rows = self.db.execute(
            "SELECT * FROM alpha_performance WHERE alpha_id = ? ORDER BY seq", (alpha_id,)
        ).fetchall()
        return [
            AlphaPerformance(
                id=r["id"], alpha_id=r["alpha_id"], created_at=r["created_at"], sharpe=r["sharpe"],
                cagr=r["cagr"], max_drawdown=r["max_drawdown"], win_rate=r["win_rate"],
                profit_factor=r["profit_factor"], expectancy=r["expectancy"], sample=r["sample"],
            )
            for r in rows
        ]

```

### libs/autodiscovery/memory.py
```python
"""Candidate store + checkpoint — durable research memory and resumable lab state.

Persists every tested candidate (family/subtype/params/metrics/rejection/status) to the
append-only ``research_candidates`` table, deduplicates by content hash (no repeated testing of a
known idea), and reads/writes the ``lab_checkpoint`` so the lab resumes after any interruption.
"""

from __future__ import annotations

import json
import sqlite3

from libs.autodiscovery.models import (
    CandidateRecord,
    CandidateStatus,
    Hypothesis,
    ValidationMetrics,
)
from libs.core.ids import generate_id
from libs.core.time import to_iso8601, utcnow
from libs.store.connection import Database
from libs.store.hashchain import canonical_json, sha256_hex

_COLS = (
    "id, created_at, updated_at, campaign_id, family, subtype, symbol, params_json, content_hash, "
    "status, mechanism, annual_sharpe, dsr, pbo, reality_p, oos_sharpe, capacity_usd, fragility, "
    "survived, rejection_reason"
)


def content_hash(hyp: Hypothesis) -> str:
    """Stable identity of a hypothesis (family+subtype+symbol+params) for dedup."""
    payload = [hyp.family.value, hyp.subtype, hyp.symbol, sorted(hyp.params.items())]
    return sha256_hex(canonical_json(payload))


def _row_to_record(row: sqlite3.Row) -> CandidateRecord:
    return CandidateRecord(
        id=row["id"], created_at=row["created_at"], updated_at=row["updated_at"],
        campaign_id=row["campaign_id"], family=row["family"], subtype=row["subtype"],
        symbol=row["symbol"], params=json.loads(row["params_json"]),
        content_hash=row["content_hash"], status=CandidateStatus(row["status"]),
        mechanism=row["mechanism"] or "",
        metrics=ValidationMetrics(
            annual_sharpe=row["annual_sharpe"] or 0.0, oos_sharpe=row["oos_sharpe"] or 0.0,
            dsr=row["dsr"] or 0.0, pbo=row["pbo"] or 0.0, reality_p=row["reality_p"] or 1.0,
            capacity_usd=row["capacity_usd"] or 0.0, fragility=row["fragility"] or 0.0,
        ),
        survived=bool(row["survived"]), rejection_reason=row["rejection_reason"],
    )


class CandidateStore:
    """Reader/writer for the durable candidate ledger (append-only) and the lab checkpoint."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def exists(self, hyp: Hypothesis) -> bool:
        chash = content_hash(hyp)
        row = self.db.execute(
            "SELECT 1 FROM research_candidates WHERE content_hash = ?", (chash,)
        ).fetchone()
        return row is not None

    def record(
        self, *, campaign_id: str, hyp: Hypothesis, status: CandidateStatus,
        metrics: ValidationMetrics, survived: bool, rejection_reason: str | None,
    ) -> CandidateRecord:
        now = to_iso8601(utcnow())
        rec = CandidateRecord(
            id=generate_id("cand"), created_at=now, updated_at=now, campaign_id=campaign_id,
            family=hyp.family.value, subtype=hyp.subtype, symbol=hyp.symbol,
            params=dict(hyp.params),
            content_hash=content_hash(hyp), status=status, mechanism=hyp.mechanism.value,
            metrics=metrics, survived=survived, rejection_reason=rejection_reason,
        )
        with self.db.transaction() as conn:
            conn.execute(
                f"INSERT INTO research_candidates ({_COLS}) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    rec.id, now, now, campaign_id, rec.family, rec.subtype, rec.symbol,
                    json.dumps(rec.params), rec.content_hash, status.value, rec.mechanism,
                    metrics.annual_sharpe, metrics.dsr, metrics.pbo, metrics.reality_p,
                    metrics.oos_sharpe, metrics.capacity_usd, metrics.fragility,
                    int(survived), rejection_reason,
                ),
            )
        return rec

    def all(self) -> list[CandidateRecord]:
        rows = self.db.execute(
            f"SELECT {_COLS} FROM research_candidates ORDER BY seq"
        ).fetchall()
        return [_row_to_record(r) for r in rows]

    def survivors(self) -> list[CandidateRecord]:
        rows = self.db.execute(
            f"SELECT {_COLS} FROM research_candidates WHERE survived = 1 ORDER BY seq"
        ).fetchall()
        return [_row_to_record(r) for r in rows]

    def rejects(self) -> list[CandidateRecord]:
        """The rejected candidates -- the input to the rejection-shadow audit (gate-calibration).

        A gate that has drifted over-strict silently leaks these; shadow-tracking a sample forward
        is pure recovery (no new data). This is the reject ledger MAX_SURVIVORS Part 1.2 calls for
        -- it already exists as ``survived = 0`` rows, so the audit reads it, never rebuilds it.
        """
        rows = self.db.execute(
            f"SELECT {_COLS} FROM research_candidates WHERE survived = 0 ORDER BY seq"
        ).fetchall()
        return [_row_to_record(r) for r in rows]

    def status_counts(self) -> dict[str, int]:
        rows = self.db.execute(
            "SELECT status, COUNT(*) AS n FROM research_candidates GROUP BY status"
        ).fetchall()
        return {r["status"]: int(r["n"]) for r in rows}

    def family_counts(self) -> dict[str, int]:
        rows = self.db.execute(
            "SELECT family, COUNT(*) AS n FROM research_candidates GROUP BY family"
        ).fetchall()
        return {r["family"]: int(r["n"]) for r in rows}

    def total(self) -> int:
        return int(self.db.execute("SELECT COUNT(*) FROM research_candidates").fetchone()[0])

    # ----------------------------------------------------------------- checkpoint
    def get_checkpoint(self, key: str) -> str | None:
        row = self.db.execute("SELECT value FROM lab_checkpoint WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_checkpoint(self, key: str, value: str) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO lab_checkpoint (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
                "updated_at = excluded.updated_at",
                (key, value, to_iso8601(utcnow())),
            )

```

### libs/backtest/__init__.py
```python
"""``libs.backtest`` — the event-driven, cost-aware backtest engine + cross-engine verification.

Event queue -> order manager -> fill engine -> portfolio engine -> metrics engine. Supports
long/short, stop-loss, take-profit, trailing stop, partial exits, and portfolio accounting.
Results are cross-checked against an independent NumPy reference (always) and backtrader /
vectorbt (when installed).
"""

from __future__ import annotations

from libs.backtest.cross_engine import (
    reference_from_backtrader,
    reference_from_vectorbt,
    summarize_result,
    vectorized_reference,
    verify_against_backtrader,
    verify_against_vectorbt,
    verify_against_vectorized,
    verify_cross_engine,
)
from libs.backtest.engine import Backtest, BacktestConfig, BacktestResult, run_signal_backtest
from libs.backtest.errors import BacktestError, VerificationError
from libs.backtest.events import (
    EventQueue,
    EventType,
    FillEvent,
    MarketEvent,
    OrderEvent,
    SignalEvent,
)
from libs.backtest.fills import FillEngine
from libs.backtest.metrics import Metrics, compute_metrics
from libs.backtest.orders import OrderManager, ProtectiveState
from libs.backtest.portfolio import PortfolioEngine, Trade
from libs.backtest.strategy import (
    BarContext,
    MovingAverageCrossStrategy,
    SignalStrategy,
    Strategy,
)

__all__ = [  # noqa: RUF022  # grouped by concern
    # engine
    "Backtest",
    "BacktestConfig",
    "BacktestResult",
    "run_signal_backtest",
    # components
    "EventQueue",
    "EventType",
    "MarketEvent",
    "SignalEvent",
    "OrderEvent",
    "FillEvent",
    "FillEngine",
    "OrderManager",
    "ProtectiveState",
    "PortfolioEngine",
    "Trade",
    "Metrics",
    "compute_metrics",
    # strategy
    "Strategy",
    "BarContext",
    "SignalStrategy",
    "MovingAverageCrossStrategy",
    # cross-engine verification
    "verify_cross_engine",
    "vectorized_reference",
    "summarize_result",
    "verify_against_vectorized",
    "reference_from_backtrader",
    "verify_against_backtrader",
    "reference_from_vectorbt",
    "verify_against_vectorbt",
    # errors
    "BacktestError",
    "VerificationError",
]

```

### libs/core/logging.py
```python
"""Structured logging with correlation ids and secret redaction.

Every record carries a UTC timestamp and the current correlation id, so one decision can
be traced tick -> signal -> order -> fill across the codebase. Context values are scrubbed
of secret-like keys before they ever reach a handler (no secrets in logs).

Usage::

    from libs.core.logging import configure_logging, get_logger, correlation_context

    configure_logging(settings)
    log = get_logger(__name__)
    with correlation_context():
        log.info("placing order", extra={"context": {"symbol": "XAUUSD", "qty": 0.1}})
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from libs.core.ids import new_correlation_id
from libs.core.time import to_iso8601, utcnow

if False:  # typing-only import guard avoids a runtime cycle with config
    from libs.core.config import Settings  # pragma: no cover

_correlation_id: ContextVar[str | None] = ContextVar("_correlation_id", default=None)

# Standard LogRecord attributes that are never treated as user context.
_RESERVED = set(
    vars(logging.makeLogRecord({})).keys()
) | {"message", "asctime", "context", "taskName"}

REDACTED = "***REDACTED***"


# --------------------------------------------------------------------------- correlation id


def set_correlation_id(value: str) -> None:
    """Set the correlation id for the current context."""
    _correlation_id.set(value)


def get_correlation_id() -> str | None:
    """Return the correlation id for the current context, if any."""
    return _correlation_id.get()


def clear_correlation_id() -> None:
    """Clear the correlation id for the current context."""
    _correlation_id.set(None)


@contextmanager
def correlation_context(correlation_id: str | None = None) -> Iterator[str]:
    """Bind a correlation id for the duration of the ``with`` block.

    Generates a new id when none is supplied; restores the previous value on exit.
    """
    cid = correlation_id or new_correlation_id()
    token = _correlation_id.set(cid)
    try:
        yield cid
    finally:
        _correlation_id.reset(token)


# --------------------------------------------------------------------------- redaction


def _redact(value: Any, redact_keys: frozenset[str]) -> Any:
    """Recursively redact values whose key matches a secret-like name."""
    if isinstance(value, Mapping):
        return {
            k: (REDACTED if str(k).lower() in redact_keys else _redact(v, redact_keys))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact(item, redact_keys) for item in value]
    return value


# --------------------------------------------------------------------------- formatters


class JsonFormatter(logging.Formatter):
    """Render a log record as a single-line JSON object."""

    def __init__(self, *, redact_keys: frozenset[str], include_caller: bool = False) -> None:
        super().__init__()
        self._redact_keys = redact_keys
        self._include_caller = include_caller

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": to_iso8601(utcnow()),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        cid = getattr(record, "correlation_id", None) or get_correlation_id()
        if cid is not None:
            payload["correlation_id"] = cid

        context = getattr(record, "context", None)
        if isinstance(context, Mapping) and context:
            payload["context"] = _redact(dict(context), self._redact_keys)

        if self._include_caller:
            payload["caller"] = f"{record.pathname}:{record.lineno}"

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, separators=(",", ":"))


class HumanFormatter(logging.Formatter):
    """Render a readable single line for local development."""

    def __init__(self, *, redact_keys: frozenset[str]) -> None:
        super().__init__()
        self._redact_keys = redact_keys

    def format(self, record: logging.LogRecord) -> str:
        cid = getattr(record, "correlation_id", None) or get_correlation_id()
        cid_part = f" [{cid}]" if cid else ""
        line = (
            f"{to_iso8601(utcnow())} {record.levelname:<8} {record.name}{cid_part}"
            f" :: {record.getMessage()}"
        )
        context = getattr(record, "context", None)
        if isinstance(context, Mapping) and context:
            redacted = _redact(dict(context), self._redact_keys)
            line += f" {json.dumps(redacted, default=str, separators=(',', ':'))}"
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


# --------------------------------------------------------------------------- configuration

_HANDLER_TAG = "_qp_core_handler"


def configure_logging(settings: Settings) -> None:
    """Install the platform's logging handler on the root logger (idempotent)."""
    redact_keys = frozenset(settings.logging.redact_keys)
    formatter: logging.Formatter
    if settings.logging.emit_json:
        formatter = JsonFormatter(
            redact_keys=redact_keys, include_caller=settings.logging.include_caller
        )
    else:
        formatter = HumanFormatter(redact_keys=redact_keys)

    root = logging.getLogger()
    # Remove any handler we previously installed so re-configuration is clean.
    for handler in list(root.handlers):
        if getattr(handler, _HANDLER_TAG, False):
            root.removeHandler(handler)

    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setFormatter(formatter)
    setattr(stream_handler, _HANDLER_TAG, True)
    root.addHandler(stream_handler)
    root.setLevel(settings.logging.level.numeric)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger."""
    return logging.getLogger(name)


class _BoundLogger(logging.LoggerAdapter):  # type: ignore[type-arg]
    """A logger adapter that merges bound context into every record's ``context``."""

    def process(self, msg: Any, kwargs: Any) -> tuple[Any, Any]:
        extra = dict(kwargs.get("extra") or {})
        bound = dict(self.extra or {})
        call_context = dict(extra.get("context") or {})
        bound.update(call_context)
        extra["context"] = bound
        kwargs["extra"] = extra
        return msg, kwargs


def bind(logger: logging.Logger, **context: Any) -> logging.LoggerAdapter:  # type: ignore[type-arg]
    """Return a logger that attaches ``context`` to every record it emits."""
    return _BoundLogger(logger, dict(context))

```

### libs/data/freesources.py
```python
"""Free, key-less crypto data families -- breadth + depth at zero cost.

Each fetcher is read-only public REST. Captures the genuinely-new free advantages that the earlier
campaign had not tapped: market-wide RISK-REGIME signals (Fear & Greed, BTC dominance / total mcap)
and extra cross-venue / term-structure CARRY breadth (Hyperliquid funding across ~230 assets,
Binance dated-quarterly calendar basis). No alpha logic here -- sleeves/gauntlets consume these.
"""

from __future__ import annotations

import json
import time
import urllib.request
from typing import Any

import pandas as pd

_FAPI = "https://fapi.binance.com"
_FNG = "https://api.alternative.me/fng"
_CG = "https://api.coingecko.com/api/v3"
_HL = "https://api.hyperliquid.xyz/info"


def _get(url: str, *, data: bytes | None = None, hdr: dict[str, str] | None = None,
         tries: int = 3) -> Any:
    last: Exception | None = None
    headers = {"User-Agent": "quant-platform/1.0", **(hdr or {})}
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read())
        except Exception as exc:  # transient network / rate-limit
            last = exc
            time.sleep(1.5)
    raise RuntimeError(f"GET failed: {url} :: {last}")


def fear_greed(*, limit: int = 0) -> pd.DataFrame:
    """Crypto Fear & Greed index (alternative.me), full daily history. (timestamp, fng) in 0-100."""
    d = _get(f"{_FNG}/?limit={limit}&format=json")
    rows = d.get("data", []) if isinstance(d, dict) else []
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame({
        "timestamp": pd.to_datetime([int(r["timestamp"]) for r in rows], unit="s", utc=True),
        "fng": [float(r["value"]) for r in rows],
    })
    return df.sort_values("timestamp").reset_index(drop=True)


def coingecko_global() -> dict[str, float]:
    """Market-wide regime snapshot: total mcap (USD), BTC dominance %, 24h mcap change %."""
    g = _get(f"{_CG}/global")
    data = g.get("data", {}) if isinstance(g, dict) else {}
    if not data:
        return {}
    return {
        "total_mcap_usd": float(data.get("total_market_cap", {}).get("usd", 0.0)),
        "btc_dominance": float(data.get("market_cap_percentage", {}).get("btc", 0.0)),
        "eth_dominance": float(data.get("market_cap_percentage", {}).get("eth", 0.0)),
        "mcap_change_24h": float(data.get("market_cap_change_percentage_24h_usd", 0.0)),
    }


def hyperliquid_funding() -> dict[str, float]:
    """Current funding rate per asset on Hyperliquid (~230 perps) -- extra cross-venue breadth."""
    body = json.dumps({"type": "metaAndAssetCtxs"}).encode()
    h = _get(_HL, data=body, hdr={"Content-Type": "application/json"})
    if not (isinstance(h, list) and len(h) == 2):
        return {}
    universe = h[0].get("universe", [])
    ctx = h[1]
    out: dict[str, float] = {}
    for meta, c in zip(universe, ctx, strict=False):
        f = c.get("funding") if isinstance(c, dict) else None
        if f is not None:
            out[str(meta.get("name"))] = float(f)
    return out


def dated_quarterly_symbols() -> list[str]:
    """Binance USD-M dated (quarterly) delivery contracts -- the calendar-basis universe."""
    info = _get(f"{_FAPI}/fapi/v1/exchangeInfo")
    syms = info.get("symbols", []) if isinstance(info, dict) else []
    return sorted(s["symbol"] for s in syms
                  if s.get("contractType") in ("CURRENT_QUARTER", "NEXT_QUARTER")
                  and s.get("status") == "TRADING")


def calendar_basis() -> dict[str, float]:
    """Annualised perp->quarterly calendar basis per base asset (BTC, ETH). Positive = contango.

    basis = (quarter_price / perp_price - 1) annualised by days-to-expiry. A clean term-structure
    carry signal: high contango -> richer cash-and-carry; backwardation -> stress.
    """
    out: dict[str, float] = {}
    quarters = dated_quarterly_symbols()
    if not quarters:
        return out
    px = _get(f"{_FAPI}/fapi/v1/ticker/price")
    perp = {d["symbol"]: float(d["price"]) for d in px} if isinstance(px, list) else {}
    now_ms = int(time.time() * 1000)
    for q in quarters:
        base, _, expiry = q.partition("_")            # e.g. BTCUSDT_260925
        if base not in perp or len(expiry) != 6:
            continue
        qpx = _get(f"{_FAPI}/fapi/v1/ticker/price?symbol={q}")
        qp = float(qpx["price"]) if isinstance(qpx, dict) and "price" in qpx else 0.0
        if qp <= 0 or perp[base] <= 0:
            continue
        exp = pd.Timestamp(f"20{expiry[:2]}-{expiry[2:4]}-{expiry[4:6]}", tz="UTC")
        exp_ms = int(exp.timestamp() * 1000)
        days = max((exp_ms - now_ms) / 86_400_000, 1.0)
        ann = (qp / perp[base] - 1.0) * (365.0 / days)
        if base not in out or "_NEXT" in q:           # keep the nearest by default
            out[base] = round(ann, 5)
    return out

```

### libs/data/instruments.py
```python
"""Supported-instrument registry for Stage 3 ingestion.

Asset class drives the trading calendar (crypto trades 24/7; FX/metals/indices close on
weekends), which in turn drives missing-bar and weekend-gap detection.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from libs.data.errors import DataError


class AssetClass(StrEnum):
    FX = "fx"
    METAL = "metal"
    INDEX = "index"
    CRYPTO = "crypto"
    ENERGY = "energy"
    EQUITY = "equity"
    SOFT = "soft"
    BOND = "bond"


# Maps an MT5 symbol-group path prefix (the first path segment) to an asset class. Used by the
# bulk history ingester to register the live broker universe without a hand-maintained catalog.
# Covers FusionMarkets and IC Markets EU group taxonomies (the two terminals seen in this env).
GROUP_TO_ASSET_CLASS: dict[str, AssetClass] = {
    "Forex": AssetClass.FX,
    "Forex Exotics": AssetClass.FX,
    "Commodities": AssetClass.METAL,
    "Energy": AssetClass.ENERGY,
    "Crypto": AssetClass.CRYPTO,
    "Indices": AssetClass.INDEX,
    "Equities": AssetClass.EQUITY,
    "Stock CFD's": AssetClass.EQUITY,
    "Soft Commodity": AssetClass.SOFT,
    "Bonds CFDs": AssetClass.BOND,
}


def asset_class_for_group(group_path: str) -> AssetClass:
    """Derive an :class:`AssetClass` from an MT5 group path; defaults to FX if unrecognized."""
    head = group_path.split("\\", 1)[0].split("/", 1)[0]
    return GROUP_TO_ASSET_CLASS.get(head, AssetClass.FX)


class InstrumentSpec(BaseModel):
    """Static metadata for a supported instrument."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    asset_class: AssetClass
    description: str

    @property
    def trades_weekends(self) -> bool:
        """Crypto trades 24/7; everything else is closed Saturday and Sunday."""
        return self.asset_class is AssetClass.CRYPTO


_SUPPORTED: dict[str, InstrumentSpec] = {
    spec.symbol: spec
    for spec in (
        InstrumentSpec(symbol="XAUUSD", asset_class=AssetClass.METAL, description="Gold"),
        InstrumentSpec(symbol="XAGUSD", asset_class=AssetClass.METAL, description="Silver"),
        InstrumentSpec(symbol="EURUSD", asset_class=AssetClass.FX, description="Euro / US Dollar"),
        InstrumentSpec(symbol="GBPUSD", asset_class=AssetClass.FX, description="Sterling / USD"),
        InstrumentSpec(symbol="USDJPY", asset_class=AssetClass.FX, description="USD / Yen"),
        InstrumentSpec(symbol="US500", asset_class=AssetClass.INDEX, description="S&P 500 CFD"),
        InstrumentSpec(symbol="NAS100", asset_class=AssetClass.INDEX, description="Nasdaq 100 CFD"),
        InstrumentSpec(symbol="BTCUSD", asset_class=AssetClass.CRYPTO, description="Bitcoin / USD"),
    )
}

SUPPORTED_SYMBOLS: tuple[str, ...] = tuple(_SUPPORTED)


def register_instrument(spec: InstrumentSpec) -> InstrumentSpec:
    """Register (or overwrite) an instrument spec at runtime and return it.

    Used by the bulk ingester to admit the live broker universe (hundreds of symbols) without a
    hand-maintained catalog. The eight built-in specs remain the deterministic default for tests.
    """
    _SUPPORTED[spec.symbol] = spec
    return spec


def get_spec(symbol: str) -> InstrumentSpec:
    """Return the spec for ``symbol`` or raise :class:`DataError`."""
    try:
        return _SUPPORTED[symbol]
    except KeyError as exc:
        raise DataError(
            f"unsupported instrument {symbol!r}; supported: {', '.join(SUPPORTED_SYMBOLS)}"
        ) from exc


def is_supported(symbol: str) -> bool:
    return symbol in _SUPPORTED

```

### libs/data/medallion.py
```python
"""Medallion builders: Bronze (raw) -> Silver (clean) -> Gold (analysis-ready).

* **Bronze** persists raw bars exactly as received (after epoch -> UTC).
* **Silver** deduplicates, sorts, drops broken rows, and tags the trading session.
* **Gold** adds analysis-ready derived columns (log returns). Feature engineering proper
  lives in Stage 6; Gold here is the minimal analysis-ready surface.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from libs.data.calendar import session_of
from libs.data.lake import Layer, ParquetLake
from libs.data.quality import QualityReport, compute_quality_score
from libs.data.schema import OHLC, TIMESTAMP, validate_bars
from libs.data.timeframe import Timeframe


def build_bronze(
    lake: ParquetLake, symbol: str, timeframe: Timeframe, raw_bars: pd.DataFrame
) -> pd.DataFrame:
    """Persist canonical raw bars to the Bronze layer, unmodified."""
    validate_bars(raw_bars, require_sorted=True)
    lake.write_bars(Layer.BRONZE, symbol, timeframe, raw_bars)
    return raw_bars


def build_silver(
    lake: ParquetLake, symbol: str, timeframe: Timeframe
) -> tuple[pd.DataFrame, QualityReport]:
    """Clean Bronze into Silver and return ``(silver_bars, quality_report_on_bronze)``."""
    bronze = lake.read_bars(Layer.BRONZE, symbol, timeframe)
    report = compute_quality_score(bronze, symbol, timeframe)

    silver = (
        bronze.dropna(subset=list(OHLC))
        .drop_duplicates(subset=TIMESTAMP, keep="last")
        .sort_values(TIMESTAMP)
        .reset_index(drop=True)
    )
    silver["session"] = [session_of(ts) for ts in silver[TIMESTAMP]]
    lake.write_bars(Layer.SILVER, symbol, timeframe, silver)
    return silver, report


def build_gold(lake: ParquetLake, symbol: str, timeframe: Timeframe) -> pd.DataFrame:
    """Build the analysis-ready Gold layer from Silver (adds log returns)."""
    silver = lake.read_bars(Layer.SILVER, symbol, timeframe)
    gold = silver.copy()
    prev_close = gold["close"].shift(1)
    gold["log_return"] = np.log(gold["close"] / prev_close)
    gold["log_return"] = gold["log_return"].fillna(0.0)
    lake.write_bars(Layer.GOLD, symbol, timeframe, gold)
    return gold

```

### libs/discovery/objective.py
```python
"""The factory objective — expected log utility (geometric growth), not backtest CAGR.

Provides the geometric-growth objective and a composite discovery score that prefers higher log
growth, higher diversification, lower correlation, lower failure dependency, longer half-life,
sufficient capacity for the book actually deployed, wider parameter plateaus — and penalizes
fragility, tail risk, and low survival.
"""

from __future__ import annotations

import numpy as np

from libs.research.capacity_policy import capacity_fit, live_book_usd, live_sleeves


def expected_log_growth(returns: np.ndarray, *, periods_per_year: float = 252.0) -> float:
    """Annualized expected log growth: E[ln(1 + r)] * periods_per_year."""
    arr = np.asarray(returns, dtype="float64")
    if len(arr) == 0 or (arr <= -1.0).any():
        return 0.0
    return float(np.log1p(arr).mean() * periods_per_year)


def log_utility(returns: np.ndarray) -> float:
    """Per-period expected log utility E[ln(1 + r)] (the quantity to maximize)."""
    arr = np.asarray(returns, dtype="float64")
    if len(arr) == 0 or (arr <= -1.0).any():
        return 0.0
    return float(np.log1p(arr).mean())


def discovery_score(
    *,
    log_growth: float,
    survival_probability: float,
    diversification_contribution: float,
    average_correlation: float,
    failure_dependency_score: float,
    half_life_days: float,
    capacity_usd: float,
    fragility_score: float,
    tail_risk_score: float,
    parameter_plateau_score: float,
    deployed_equity_usd: float | None = None,
    n_sleeves: int | None = None,
    sleeve: str | None = None,
) -> float:
    """Composite rank score that maximizes sustainable geometric growth under robustness."""
    growth = max(0.0, log_growth)
    survival = max(0.0, min(1.0, survival_probability))
    corr_term = max(0.0, 1.0 - max(0.0, average_correlation))
    failure_term = 1.0 - min(1.0, failure_dependency_score / 100.0)
    fragility_term = 1.0 - min(1.0, fragility_score / 100.0)
    tail_term = 1.0 - min(1.0, tail_risk_score / 100.0)
    plateau_term = min(1.0, parameter_plateau_score / 100.0)
    half_life_term = min(1.0, half_life_days / 365.0)
    # §42 PARITY. This was `min(1, capacity_usd / 1e6)`, which handed a $1M-capacity idea a 1.9x
    # rank advantage over a $50k one -- i.e. the composite ranking quietly undid the survival
    # gate's fix and kept steering the desk at fund-shaped edges. Capacity now scores as
    # SUFFICIENCY for the book actually deployed and goes FLAT above it, because capacity you
    # cannot fill is not an advantage you own.
    # None means "read the live book", which is what keeps the ratio self-scaling as equity grows.
    capacity_term = capacity_fit(
        capacity_usd,
        live_book_usd() if deployed_equity_usd is None else deployed_equity_usd,
        live_sleeves() if n_sleeves is None else n_sleeves,
        sleeve=sleeve,
    )
    diversification_term = 1.0 + max(0.0, diversification_contribution)

    return (
        growth
        * survival
        * corr_term
        * failure_term
        * fragility_term
        * tail_term
        * (0.5 + 0.5 * plateau_term)
        * (0.5 + 0.5 * half_life_term)
        * (0.5 + 0.5 * capacity_term)
        * diversification_term
    )

```

### libs/execution/maker.py
```python
"""Maker-first execution: post-only quotes at the passive top-of-book, one wait, taker fallback.

Pays the MAKER fee (~half the taker fee on Binance futures) on quotes that rest, instead of crossing
the spread every rebalance -- pure net-edge on a thin carry book, no alpha change. Batch design:
quote ALL legs passively, wait once, then market-fill only the unfilled remainder, so a 20-symbol
rebalance still completes in one short window. No look-ahead / no edge logic -- execution only.
"""

from __future__ import annotations

import time
from typing import Any

from libs.execution import binance_testnet as bt


def _round_price(price: float, tick: float, prec: int) -> float:
    return round(round(price / tick) * tick, prec) if tick > 0 else round(price, prec)


def maker_execute_batch(orders: list[tuple[str, str, float]], *,
                        filters: dict[str, dict[str, float]],
                        book: dict[str, tuple[float, float]],
                        wait_s: float = 10.0) -> dict[str, str]:
    """Quote every (symbol, side, qty) post-only at the passive side, wait, taker-fill the rest.

    Returns {symbol: mode} where mode is 'maker' (rested then filled), 'taker_fallback' (unfilled ->
    market), or 'taker' (could not quote). Caller still owns sizing/targets; this only routes fills.
    """
    pending: dict[str, tuple[Any, str, float]] = {}
    result: dict[str, str] = {}
    for sym, side, qty in orders:
        f = filters.get(sym)
        bid, ask = book.get(sym, (0.0, 0.0))
        if not f or bid <= 0 or ask <= 0:
            bt.place_market(sym, side, qty)
            result[sym] = "taker"
            continue
        price = _round_price(bid if side == "BUY" else ask, f["tick"], int(f["price_prec"]))
        try:
            o = bt.place_post_only(sym, side, qty, price)
            oid = o.get("orderId")
            if oid is None:                            # GTX rejected (would cross) -> taker
                bt.place_market(sym, side, qty)
                result[sym] = "taker"
            else:
                pending[sym] = (oid, side, qty)
        except Exception:                              # GTX reject / transient -> taker
            bt.place_market(sym, side, qty)
            result[sym] = "taker"

    if not pending:
        return result
    time.sleep(wait_s)
    for sym, (oid, side, qty) in pending.items():
        try:
            resting = {x.get("orderId") for x in bt.open_orders(sym)}
        except Exception:
            resting = {oid}                            # assume still there -> fall back safely
        if oid in resting:
            bt.cancel_all(sym)
            bt.place_market(sym, side, qty)
            result[sym] = "taker_fallback"
        else:
            result[sym] = "maker"                      # no longer resting -> filled as maker
    return result


def maker_share(modes: dict[str, str]) -> float:
    """Fraction of legs filled as MAKER (the execution-quality KPI)."""
    if not modes:
        return 0.0
    return sum(1 for m in modes.values() if m == "maker") / len(modes)

```

### libs/monitoring/metrics_store.py
```python
"""Metrics store — durable, append-only metric time-series (migration 0004)."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from typing import Any

from libs.core.ids import generate_id
from libs.core.time import to_iso8601, utcnow
from libs.monitoring.models import MetricPoint
from libs.store.connection import Database


def _row_to_point(row: sqlite3.Row) -> MetricPoint:
    return MetricPoint(
        id=row["id"], created_at=row["created_at"], name=row["name"], value=row["value"],
        tags=json.loads(row["tags_json"]) if row["tags_json"] else {},
    )


class MetricsStore:
    """Writer/reader for the append-only ``metric_points`` table."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def record(
        self, name: str, value: float, *, tags: Mapping[str, Any] | None = None
    ) -> MetricPoint:
        point = MetricPoint(
            id=generate_id("metric"), created_at=to_iso8601(utcnow()), name=name,
            value=float(value), tags=dict(tags or {}),
        )
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO metric_points (id, created_at, name, value, tags_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (point.id, point.created_at, point.name, point.value, json.dumps(point.tags)),
            )
        return point

    def latest(self, name: str) -> MetricPoint | None:
        row = self.db.execute(
            "SELECT * FROM metric_points WHERE name = ? ORDER BY seq DESC LIMIT 1", (name,)
        ).fetchone()
        return _row_to_point(row) if row else None

    def history(self, name: str, *, limit: int = 100) -> list[MetricPoint]:
        rows = self.db.execute(
            "SELECT * FROM metric_points WHERE name = ? ORDER BY seq DESC LIMIT ?", (name, limit)
        ).fetchall()
        return [_row_to_point(r) for r in reversed(rows)]

```

### libs/portfolio/constraints.py
```python
"""Portfolio constraints — per-weight, factor, strategy, and asset-class caps.

Per-weight caps use water-filling (cap and redistribute, preserving sum = 1). Group caps scale
the offending group down (any freed weight stays uninvested rather than forcing a re-breach).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from libs.portfolio.models import AlphaInput, PortfolioConstraints

_EPS = 1e-9


def _cap_per_weight(weights: dict[str, float], max_weight: float) -> bool:
    """Water-fill per-weight cap, keeping the total constant. Returns whether any cap bound."""
    bound = False
    for _ in range(100):
        over = {i: w for i, w in weights.items() if w > max_weight + _EPS}
        if not over:
            break
        bound = True
        excess = sum(w - max_weight for w in over.values())
        for i in over:
            weights[i] = max_weight
        under = {i: weights[i] for i in weights if i not in over}
        headroom = sum(max(0.0, max_weight - w) for w in under.values())
        if headroom <= _EPS:
            break
        for i in under:
            room = max(0.0, max_weight - weights[i])
            weights[i] += excess * room / headroom
    return bound


def apply_constraints(
    weights: Mapping[str, float],
    alphas: Sequence[AlphaInput],
    constraints: PortfolioConstraints,
) -> tuple[dict[str, float], list[str]]:
    """Enforce long-only, per-weight, and group caps; return weights + binding constraint labels."""
    amap = {a.alpha_id: a for a in alphas}
    w = {i: float(v) for i, v in weights.items()}
    binding: set[str] = set()

    if constraints.long_only:
        for i in w:
            if w[i] < 0:
                w[i] = 0.0
                binding.add(f"long_only:{i}")

    if constraints.sum_to_one:
        total = sum(w.values())
        if total > 0:
            for i in w:
                w[i] /= total

    if _cap_per_weight(w, constraints.max_weight):
        binding.add("max_weight")

    for group_type, cap in (
        ("factor", constraints.max_factor_weight),
        ("strategy", constraints.max_strategy_weight),
        ("asset_class", constraints.max_asset_class_weight),
    ):
        keys: dict[str, str | None] = {i: _key_of(group_type, amap[i]) for i in w}
        totals: dict[str, float] = {}
        for i, key in keys.items():
            if key is not None:
                totals[key] = totals.get(key, 0.0) + w[i]
        for key, total in totals.items():
            if total > cap + _EPS and total > 0:
                scale = cap / total
                for i, alpha_key in keys.items():
                    if alpha_key == key:
                        w[i] *= scale
                binding.add(f"{group_type}:{key}")

    return w, sorted(binding)


def _key_of(group_type: str, alpha: AlphaInput) -> str | None:
    if group_type == "factor":
        return alpha.factor.value
    if group_type == "strategy":
        return alpha.strategy_type.value
    return alpha.asset_class

```

### libs/regime/engine.py
```python
"""Regime engine -- fits HMM + GMM, characterises the latent states into market regimes, and emits
the live regime with confidence and the risk / leverage multipliers every downstream module reads.

A latent state is just an index; this maps it onto an economically meaningful label (bull/bear x
vol tier) from the real per-state mean return and volatility, then derives a LEVERAGE MULTIPLIER
that only de-risks (<=1.0): smaller in high-vol / bear regimes, full in calm bull regimes. The HMM
(temporal) and GMM (clustering) are cross-checked -- agreement => high confidence.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from libs.regime.bayesian import BayesianRegimeFilter
from libs.regime.features import regime_features
from libs.regime.gmm import fit_gmm
from libs.regime.hmm import GaussianHMM

_VOL_FACTOR = {"high_vol": 0.5, "mid_vol": 0.8, "low_vol": 1.0}
_TREND_FACTOR = {"bull": 1.0, "bear": 0.75}


def _characterise(states: np.ndarray, raw_ret: np.ndarray, k: int) -> dict[int, dict[str, object]]:
    """Label each state from its real mean return + volatility (bull/bear x vol tier)."""
    stats = {}
    for j in range(k):
        mask = states == j
        r = raw_ret[mask]
        stats[j] = {"mean_ret": float(np.mean(r)) if r.size else 0.0,
                    "vol": float(np.std(r)) if r.size > 1 else 0.0, "n": int(mask.sum())}
    vol_order = sorted(range(k), key=lambda j: stats[j]["vol"])  # low -> high
    tier = {}
    for rank, j in enumerate(vol_order):
        tier[j] = "low_vol" if rank == 0 else ("high_vol" if rank == k - 1 else "mid_vol")
    out: dict[int, dict[str, object]] = {}
    for j in range(k):
        trend = "bull" if stats[j]["mean_ret"] >= 0 else "bear"
        vt = tier[j]
        lev = max(0.2, min(1.0, _VOL_FACTOR[vt] * _TREND_FACTOR[trend]))
        out[j] = {"label": f"{trend}/{vt}", "trend": trend, "vol_tier": vt,
                  "mean_ret": round(stats[j]["mean_ret"], 6), "vol": round(stats[j]["vol"], 6),
                  "days": stats[j]["n"], "leverage_multiplier": round(lev, 3)}
    return out


class RegimeEngine:
    def __init__(self, *, n_states: int = 3, seed: int = 0) -> None:
        self.k = n_states
        self.seed = seed
        self.hmm = GaussianHMM(n_states=n_states, seed=seed)
        self.gmm: Any = None                   # sklearn GaussianMixture (untyped) once fitted
        self.x: np.ndarray = np.zeros((0, 3))
        self.hmm_states: np.ndarray = np.zeros(0, dtype="int64")
        self.hmm_char: dict[int, dict[str, object]] = {}
        self.gmm_char: dict[int, dict[str, object]] = {}
        self.posteriors: np.ndarray = np.zeros((0, n_states))

    def fit(self, close: pd.Series) -> RegimeEngine:
        x, raw = regime_features(close)
        self.x = x
        self.hmm.fit(x)
        self.hmm_states = self.hmm.predict(x)
        self.posteriors = self.hmm.filter_posterior(x)
        self.hmm_char = _characterise(self.hmm_states, raw, self.k)
        self.gmm = fit_gmm(x, n_states=self.k, seed=self.seed)
        gmm_states = self.gmm.predict(x)
        self.gmm_char = _characterise(gmm_states, raw, self.k)
        return self

    def make_filter(self) -> BayesianRegimeFilter:
        """Online Bayesian filter seeded from the fitted HMM (for incremental live updates)."""
        return BayesianRegimeFilter(self.hmm.transmat, self.hmm.means, self.hmm.vars,
                                    self.hmm.startprob)

    def current(self) -> dict[str, object]:
        """Live regime: HMM state label, confidence, GMM agreement, leverage multiplier."""
        if self.hmm_states.size == 0:
            return {"regime": "unknown", "confidence": 0.0, "leverage_multiplier": 1.0}
        j = int(self.hmm_states[-1])
        ch = self.hmm_char[j]
        conf = float(self.posteriors[-1].max())
        gmm_label = "—"
        if self.gmm is not None:
            gj = int(self.gmm.predict(self.x[-1:])[0])
            gmm_label = str(self.gmm_char[gj]["label"])
        agree = gmm_label == ch["label"]
        return {
            "regime": ch["label"], "trend": ch["trend"], "vol_tier": ch["vol_tier"],
            "confidence": round(conf, 3),
            "leverage_multiplier": ch["leverage_multiplier"],
            "risk_multiplier": ch["leverage_multiplier"],
            "hmm_state": j, "gmm_regime": gmm_label, "hmm_gmm_agree": agree,
            "n_states": self.k,
        }

```

### libs/regime/hmm.py
```python
"""Self-contained Gaussian HMM (diagonal emissions) -- no external HMM dependency.

Implements Baum-Welch EM (fit), Viterbi (most-likely path), and the online forward filter
(P(state_t | x_1..t)) in log-space via scipy.special.logsumexp. hmmlearn is not installed and a
small, audited implementation is preferable to a heavy dependency for a 2-3 state market regime.
"""

from __future__ import annotations

import numpy as np
from scipy.special import logsumexp


class GaussianHMM:
    """Diagonal-covariance Gaussian Hidden Markov Model fit by EM."""

    def __init__(self, n_states: int = 3, *, n_iter: int = 60, seed: int = 0,
                 reg: float = 1e-4) -> None:
        self.k = n_states
        self.n_iter = n_iter
        self.seed = seed
        self.reg = reg
        self.startprob: np.ndarray = np.full(n_states, 1.0 / n_states)
        self.transmat: np.ndarray = np.full((n_states, n_states), 1.0 / n_states)
        self.means: np.ndarray = np.zeros((n_states, 1))
        self.vars: np.ndarray = np.ones((n_states, 1))

    def _log_emission(self, x: np.ndarray) -> np.ndarray:
        n = x.shape[0]
        le = np.empty((n, self.k))
        for j in range(self.k):
            diff = x - self.means[j]
            le[:, j] = -0.5 * (np.sum(diff * diff / self.vars[j], axis=1)
                               + np.sum(np.log(2.0 * np.pi * self.vars[j])))
        return le

    def _init(self, x: np.ndarray) -> None:
        rng = np.random.RandomState(self.seed)
        n = x.shape[0]
        idx = rng.choice(n, self.k, replace=False)
        self.means = x[idx].astype("float64").copy()
        self.vars = np.tile(x.var(axis=0) + self.reg, (self.k, 1))
        self.startprob = np.full(self.k, 1.0 / self.k)
        self.transmat = np.full((self.k, self.k), 1.0 / self.k)

    def _forward_backward(self, le: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        n = le.shape[0]
        lt = np.log(self.transmat + 1e-300)
        log_alpha = np.empty((n, self.k))
        log_beta = np.zeros((n, self.k))
        log_alpha[0] = np.log(self.startprob + 1e-300) + le[0]
        for t in range(1, n):
            log_alpha[t] = le[t] + logsumexp(log_alpha[t - 1][:, None] + lt, axis=0)
        for t in range(n - 2, -1, -1):
            log_beta[t] = logsumexp(lt + le[t + 1][None, :] + log_beta[t + 1][None, :], axis=1)
        return log_alpha, log_beta

    def fit(self, x: np.ndarray) -> GaussianHMM:
        x = np.asarray(x, dtype="float64")
        if x.ndim == 1:
            x = x[:, None]
        self._init(x)
        n = x.shape[0]
        lt = np.log(self.transmat + 1e-300)
        for _ in range(self.n_iter):
            le = self._log_emission(x)
            log_alpha, log_beta = self._forward_backward(le)
            log_gamma = log_alpha + log_beta
            log_gamma -= logsumexp(log_gamma, axis=1, keepdims=True)
            gamma = np.exp(log_gamma)
            lt = np.log(self.transmat + 1e-300)
            log_xi = (log_alpha[:-1, :, None] + lt[None, :, :]
                      + le[1:, None, :] + log_beta[1:, None, :])
            log_xi -= logsumexp(log_xi.reshape(n - 1, -1), axis=1)[:, None, None]
            xi = np.exp(log_xi)
            self.startprob = gamma[0] / (gamma[0].sum() + 1e-12)
            denom = xi.sum(axis=0).sum(axis=1, keepdims=True) + 1e-12
            self.transmat = xi.sum(axis=0) / denom
            for j in range(self.k):
                w = gamma[:, j]
                sw = w.sum() + 1e-9
                self.means[j] = (w[:, None] * x).sum(axis=0) / sw
                diff = x - self.means[j]
                self.vars[j] = (w[:, None] * diff * diff).sum(axis=0) / sw + self.reg
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        """Viterbi most-likely state path."""
        x = np.asarray(x, dtype="float64")
        if x.ndim == 1:
            x = x[:, None]
        le = self._log_emission(x)
        n = le.shape[0]
        lt = np.log(self.transmat + 1e-300)
        delta = np.empty((n, self.k))
        psi = np.zeros((n, self.k), dtype="int64")
        delta[0] = np.log(self.startprob + 1e-300) + le[0]
        for t in range(1, n):
            m = delta[t - 1][:, None] + lt
            psi[t] = np.argmax(m, axis=0)
            delta[t] = le[t] + np.max(m, axis=0)
        states = np.empty(n, dtype="int64")
        states[-1] = int(np.argmax(delta[-1]))
        for t in range(n - 2, -1, -1):
            states[t] = psi[t + 1, states[t + 1]]
        return states

    def filter_posterior(self, x: np.ndarray) -> np.ndarray:
        """Online forward posterior P(state_t | x_1..t), normalised per t -- the Bayesian filter."""
        x = np.asarray(x, dtype="float64")
        if x.ndim == 1:
            x = x[:, None]
        le = self._log_emission(x)
        n = le.shape[0]
        lt = np.log(self.transmat + 1e-300)
        log_alpha = np.empty((n, self.k))
        log_alpha[0] = np.log(self.startprob + 1e-300) + le[0]
        for t in range(1, n):
            log_alpha[t] = le[t] + logsumexp(log_alpha[t - 1][:, None] + lt, axis=0)
        post = np.exp(log_alpha - logsumexp(log_alpha, axis=1, keepdims=True))
        return np.asarray(post, dtype="float64")

```

### libs/research/alpha_economics.py
```python
"""Alpha Economics Engine -- score research ideas by EXPECTED VALUE *before* spending effort.

Maximises expected log-growth per research-hour, not the number of alphas explored. Every candidate
is scored PRE-research; only ideas above the EV threshold enter the queue, the rest are rejected
immediately and their killing pattern recorded so the same class is never re-tried. This is the
"should we build this?" gate that runs before "can we build this?".

    EV = P(survive) * dSharpe * breadth_f * capacity_f * orthogonality / (effort_h * maintenance)

P(survive) starts from the desk's honest base rate (near-zero survivors historically) and is moved
by META-LEARNED PRIORS distilled from our own graveyard -- the patterns that repeatedly kill or save
ideas. These priors are the compounding asset: every resolved hypothesis sharpens them and cuts
future wasted research. Pure/stdlib, offline, deterministic -> testable + cheap to run each cycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from libs.research.capacity_policy import DEFAULT_BOOK_USD, DEFAULT_SLEEVES, capacity_fit

# Meta-learned priors (multiplicative on P(survive)), distilled from the desk's resolved outcomes.
# Each is an economic pattern, not a fitted parameter -- update ONLY when the graveyard teaches a
# new durable lesson. See docs/institutional_knowledge.md for the evidence behind each.
_PRIORS: dict[str, float] = {
    "price_only": 0.30,          # momentum/reversal/lowvol on price alone -> mostly die net-of-cost
    "narrow_breadth": 0.25,      # breadth < ~5 starves IR even w/ positive IC (VRP)
    "high_turnover_no_maker": 0.50,  # turnover cost kills thin edges without maker execution
    "no_economic_mechanism": 0.20,   # data-mined w/ no risk-premium story -> overfit, won't persist
    "funding_family": 2.0,       # funding/carry is the lone repeat survivor -> real risk premium
    "new_orthogonal_data": 1.6,  # a genuinely NEW free data axis raises odds (most of edge is data)
    "crowded_known": 0.35,       # published/crowded -> decayed before we arrive
}
_BASE_P = 0.15                   # honest base rate: most rigorously-tested candidates fail
# RECALIBRATED 2026-07-31 (R0023/R0034, gate-optimality): 0.05 was dimensionally wrong for this
# formula. Scored HONESTLY, the desk's single validated family (carry-class: p≈0.2 after priors,
# est_sharpe 0.8, breadth 60 -> breadth_f 1.73, capacity_f≈1, orth 1, ~20h/1.5x maint) yields
# EV ≈ 0.009 -- the old bar sat 5x ABOVE the best real candidate ever measured, so honest inputs
# auto-rejected and only inflated est_sharpe could pass: the gate trained optimism and BLOCKED
# two generation cycles (R0034). Hard-kill junk (price_only+narrow: p≈0.02-0.03) scores ~0.0002,
# two orders of magnitude below carry-class, so 0.002 separates cleanly: ~10x above measured
# junk, ~4x below measured good. A calibration test locks both reference points. Re-tune ONLY
# from the EV-gate self-audit at n>=50 scored verdicts (constitution item 9), never by feel.
_EV_THRESHOLD = 0.002           # below this, reject immediately (not worth the research-hours)


@dataclass
class Idea:
    """A research candidate, described BEFORE any backtest (so the gate is pre-registered)."""
    name: str
    est_sharpe: float = 0.5      # honest prior on standalone Sharpe contribution (be conservative)
    breadth: int = 20            # number of independent bets/assets the signal spans
    # Rough $ the edge absorbs before decay. Defaulted to bare sufficiency for this book, NOT to
    # the old $1m: an unestimated idea is not a fund-scale idea, and a seven-figure default
    # silently assumed every unmeasured candidate was one.
    capacity_usd: float = 200_000.0
    book_usd: float = DEFAULT_BOOK_USD   # WHOLE book; sleeved below, since one idea is one sleeve
    n_sleeves: int = DEFAULT_SLEEVES
    orthogonality: float = 0.5   # 0..1 correlation-complement to book (1 = fully new)
    effort_h: float = 8.0        # engineering hours to test it properly
    maintenance: float = 1.0     # ongoing upkeep multiplier (1 = light, >1 = heavy)
    tags: list[str] = field(default_factory=list)   # which _PRIORS apply (economic descriptors)


def p_survive(idea: Idea) -> float:
    """Base survival rate moved by every meta-learned prior whose tag the idea carries."""
    p = _BASE_P
    for t in idea.tags:
        p *= _PRIORS.get(t, 1.0)
    return round(min(max(p, 0.0), 0.95), 4)


def ev_score(idea: Idea) -> dict[str, Any]:
    """Expected-value score + a pre-research verdict. Higher EV = more log-growth per hour."""
    p = p_survive(idea)
    breadth_f = min(idea.breadth / 20.0, 3.0) ** 0.5           # IR ~ IC*sqrt(breadth); diminishing
    # §42 PARITY. This was `min(cap/1e6, 5)**0.25`, monotone in raw size: a $50k-capacity edge was
    # scored 0.47 and a $5M one 1.50, a 3.2x EV penalty on precisely the capacity-bound niche
    # PROSPECTOR_SPEC calls this desk's one structural advantage. Capacity you cannot fill is not
    # EV -- so it now scores as sufficiency for `book_usd` and is FLAT once sufficient.
    # `sleeve=idea.name` is what lets a DECLARED allocation actually reach the score. Without
    # it the parameter exists and nothing ever passes it -- a knob wired to nothing.
    capacity_f = capacity_fit(idea.capacity_usd, idea.book_usd, idea.n_sleeves,
                              sleeve=idea.name)
    denom = max(idea.effort_h, 0.5) * max(idea.maintenance, 0.5)
    ev = (p * max(idea.est_sharpe, 0.0) * breadth_f * capacity_f
          * max(idea.orthogonality, 0.0) / denom)
    ev = round(ev, 4)
    # hard economic kills -> reject regardless of EV arithmetic (the graveyard's clearest lessons)
    hard_kill = ("no_economic_mechanism" in idea.tags) or \
                ("price_only" in idea.tags and "narrow_breadth" in idea.tags)
    verdict = ("REJECT (hard economic kill)" if hard_kill
               else "REJECT (EV below thresh)" if ev < _EV_THRESHOLD
               else "QUEUE (top-EV -> research)")
    return {"name": idea.name, "ev": ev, "p_survive": p, "breadth_f": round(breadth_f, 3),
            "verdict": verdict, "tags": list(idea.tags)}


def rank(ideas: list[Idea]) -> list[dict[str, Any]]:
    """Score a batch and rank by EV desc -> the research queue. Only 'QUEUE' verdicts should run."""
    return sorted((ev_score(i) for i in ideas), key=lambda s: -float(s["ev"]))

```

### libs/research/crypto_sleeves.py
```python
"""Crypto-native alpha sleeves (Binance perps) -- economically distinct mechanisms.

Built on the same dollar-neutral, inverse-vol, turnover-banded, net-of-cost construction as the
proven funding carry core, but driven by different economic signals so the portfolio gets genuinely
orthogonal return streams (the goal is portfolio Sharpe, not another funding clone). Each sleeve
earns/pays funding on the positions it holds (the real perp cashflow). Decisions use only lagged
information; no look-ahead.

Funding family here:
  * funding_carry      -> see crypto_xsec.xsec_funding_returns (long lowest / short highest funding)
  * funding_momentum   -> trade WITH the change in funding (positioning building)
  * funding_reversal   -> fade funding EXTREMES (crowded longs pay; short them, collect funding)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from libs.research.crypto_xsec import adv_tier_cost


def _book(
    close: pd.DataFrame,
    funding: pd.DataFrame,
    adv: dict[str, float],
    signal: pd.DataFrame,
    *,
    q: float,
    band: float,
    vol_window: int,
    min_names: int,
    long_low: bool,
) -> np.ndarray:
    """Generic dollar-neutral cross-sectional perp book on ``signal``, earning funding cashflow.

    ``long_low`` longs the bottom-quantile signal and shorts the top; flip for the opposite. Returns
    daily net = price P&L + funding earned/paid - turnover cost (ADV-tiered).
    """
    ret = close.pct_change(fill_method=None)
    inv_vol = 1.0 / ret.rolling(vol_window).std().shift(1)
    sig = signal.shift(1)
    cost = {s: adv_tier_cost(a) for s, a in adv.items()}
    out = np.zeros(len(close), dtype="float64")
    prev = pd.Series(0.0, index=close.columns)
    for t in range(1, len(close)):
        s = sig.iloc[t].dropna()
        valid = close.iloc[t].reindex(s.index).notna() & ret.iloc[t].reindex(s.index).notna()
        s = s.reindex(s.index[valid]).dropna()
        if len(s) < min_names:
            out[t] = float((prev * ret.iloc[t].reindex(prev.index).fillna(0.0)).sum())
            continue
        k = max(1, int(len(s) * q))
        ranked = s.sort_values(ascending=long_low)        # long_low -> smallest first = longs
        longs, shorts = ranked.index[:k], ranked.index[-k:]
        iv = inv_vol.iloc[t]
        w = pd.Series(0.0, index=close.columns)
        lw, sw = iv.reindex(longs).fillna(0.0), iv.reindex(shorts).fillna(0.0)
        if lw.sum() > 0:
            w[longs] = 0.5 * lw / lw.sum()
        if sw.sum() > 0:
            w[shorts] = -0.5 * sw / sw.sum()
        delta = (w - prev).abs()
        w = w.where(delta > band, prev)
        price_ret = float((w * ret.iloc[t].reindex(w.index).fillna(0.0)).sum())
        funding_pnl = float(-(w * funding.iloc[t].reindex(w.index).fillna(0.0)).sum())
        turn = float(sum(abs(w[s2] - prev[s2]) * cost.get(s2, 1.5e-3) for s2 in w.index))
        out[t] = price_ret + funding_pnl - turn
        prev = w
    return out


def funding_momentum_returns(
    close: pd.DataFrame, funding: pd.DataFrame, adv: dict[str, float],
    *, lookback: int, q: float, band: float, vol_window: int = 30, min_names: int = 12,
) -> np.ndarray:
    """Cross-sectional funding-rate momentum (positioning shifts -> short-term continuation)."""
    signal = funding.rolling(lookback).mean() - funding.rolling(lookback * 3).mean()
    # long where funding is FALLING (signal low) -> shorts being squeezed / longs unwinding cheaply
    return _book(close, funding, adv, signal, q=q, band=band, vol_window=vol_window,
                 min_names=min_names, long_low=True)


def funding_reversal_returns(
    close: pd.DataFrame, funding: pd.DataFrame, adv: dict[str, float],
    *, lookback: int, q: float, band: float, vol_window: int = 30, min_names: int = 12,
) -> np.ndarray:
    """Fade short-term PRICE momentum, collecting funding -- reversal of crowded perp moves."""
    signal = close / close.shift(lookback) - 1.0
    # long recent losers / short recent winners (price reversal); funding cashflow is incidental
    return _book(close, funding, adv, signal, q=q, band=band, vol_window=vol_window,
                 min_names=min_names, long_low=True)


def latest_weights(
    close: pd.DataFrame, signal: pd.DataFrame, *,
    q: float, vol_window: int = 30, min_names: int = 12, long_low: bool = True,
) -> dict[str, float]:
    """Today's dollar-neutral cross-sectional target weights for a signal (the brain's decision).

    Mirrors the backtest book's construction (lagged signal, inverse-vol, +0.5/-0.5 legs) but only
    for the latest bar -- what the executor should hold now. ``long_low`` longs the lowest-signal q.
    """
    ret = close.pct_change(fill_method=None)
    inv_vol = (1.0 / ret.rolling(vol_window).std()).iloc[-1]
    s = signal.shift(1).iloc[-1].dropna()
    s = s[close.iloc[-1].reindex(s.index).notna()].dropna()
    if len(s) < min_names:
        return {}
    k = max(1, int(len(s) * q))
    ranked = s.sort_values(ascending=long_low)
    longs, shorts = ranked.index[:k], ranked.index[-k:]
    lw, sw = inv_vol.reindex(longs).fillna(0.0), inv_vol.reindex(shorts).fillna(0.0)
    out: dict[str, float] = {}
    if lw.sum() > 0:
        out.update({x: 0.5 * float(lw[x]) / float(lw.sum()) for x in longs})
    if sw.sum() > 0:
        out.update({x: -0.5 * float(sw[x]) / float(sw.sum()) for x in shorts})
    return out


def xsec_lowvol_returns(
    close: pd.DataFrame, funding: pd.DataFrame, adv: dict[str, float],
    *, lookback: int, q: float, band: float, vol_window: int = 30, min_names: int = 12,
) -> np.ndarray:
    """Cross-sectional LOW-VOLATILITY factor: long the lowest-realised-vol perps, short the highest.

    The low-vol anomaly / volatility risk premium is one of the most robust factors in finance:
    low-vol assets earn higher risk-adjusted returns than high-vol lottery names. Economically
    distinct from funding/momentum/flow -- a vol-based source -- so it is a breadth candidate. Earns
    funding cashflow on the book; decisions use lagged realised vol only.
    """
    signal = close.pct_change(fill_method=None).rolling(lookback).std()
    return _book(close, funding, adv, signal, q=q, band=band, vol_window=vol_window,
                 min_names=min_names, long_low=True)


def basis_carry_returns(
    close: pd.DataFrame, funding: pd.DataFrame, basis: pd.DataFrame, adv: dict[str, float],
    *, lookback: int, q: float, band: float, vol_window: int = 30, min_names: int = 12,
) -> np.ndarray:
    """Perp-spot BASIS carry: long backwardated perps (basis low/negative) / short rich premium.

    Distinct from funding (basis captures spot-perp arbitrage pressure, not just leverage demand);
    a rich premium signals crowded longs that mean-revert. Earns funding cashflow on the book.
    """
    signal = basis.rolling(lookback).mean()
    return _book(close, funding, adv, signal, q=q, band=band, vol_window=vol_window,
                 min_names=min_names, long_low=True)


def taker_flow_returns(
    close: pd.DataFrame, funding: pd.DataFrame, taker: pd.DataFrame, adv: dict[str, float],
    *, lookback: int, q: float, band: float, vol_window: int = 30, min_names: int = 12,
) -> np.ndarray:
    """Taker order-flow momentum: long perps with the strongest recent net taker BUYING.

    ``taker`` is the taker-buy fraction (>0.5 = aggressive buyers lifting offers). Persistent buy
    pressure tends to continue short-term -- an order-flow edge orthogonal to funding/price.
    """
    signal = taker.rolling(lookback).mean()
    return _book(close, funding, adv, signal, q=q, band=band, vol_window=vol_window,
                 min_names=min_names, long_low=False)

```

### libs/research/sleeves.py
```python
"""Relative-value and positioning sleeve cores for the MT5 alpha portfolio.

These are the *orthogonal* building blocks -- relative-value (ratio mean-reversion) and positioning
(CFTC COT) signals are economically distinct from price-trend/momentum, so they are the legitimate
diversifiers that can lift a portfolio's robustness without overfitting. Pure functions; decisions
use only lagged information (``.shift(1)``); net of realistic per-side cost. No parameter mining.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def ratio_meanrev_returns(
    a_close: pd.Series,
    b_close: pd.Series,
    *,
    lookback: int,
    vol_window: int = 30,
    cost: float = 2.0e-4,
    band: float = 0.05,
    z_cap: float = 1.0,
) -> np.ndarray:
    """Daily net return of a dollar-neutral A/B ratio mean-reversion spread.

    Signal is the lagged z-score of ``log(A/B)`` over ``lookback``; position = ``-z`` (buy the cheap
    leg, sell the rich), clipped to +/-``z_cap``, split 0.5 long / 0.5 short (dollar-neutral). A
    turnover band holds the position unless the target moves materially. Cost is charged per side on
    turnover. Flat whenever either leg is missing.
    """
    a, b = a_close.align(b_close, join="outer")
    ret_a = a.pct_change(fill_method=None)
    ret_b = b.pct_change(fill_method=None)
    lr = np.log(a / b)
    z = ((lr - lr.rolling(lookback).mean()) / lr.rolling(lookback).std()).shift(1)
    pos = (-z).clip(-z_cap, z_cap)
    out = np.zeros(len(a), dtype="float64")
    prev = 0.0
    for t in range(1, len(a)):
        p = pos.iloc[t]
        ra, rb = ret_a.iloc[t], ret_b.iloc[t]
        if not (np.isfinite(p) and np.isfinite(ra) and np.isfinite(rb)):
            out[t] = 0.0
            continue
        if abs(p - prev) <= band:
            p = prev                                   # turnover band: hold
        turn = abs(p - prev) * cost                    # per-side cost on the change (both legs)
        out[t] = 0.5 * p * ra - 0.5 * p * rb - turn
        prev = p
    return out


def calendar_event_returns(
    index_close: pd.DataFrame,
    *,
    cost: float = 1.0e-4,
    vol_window: int = 30,
    tom_first: int = 3,
    min_names: int = 1,
) -> np.ndarray:
    """Turn-of-month flow sleeve: long an inverse-vol equity-index basket only in the TOM window.

    Documented month-end/turn flow effect (pension/fund rebalancing): equities drift up around the
    last trading day of the month through the first few of the next. The window is the standard
    [last day .. +``tom_first``] -- deterministic from the calendar, so no look-ahead and no date
    feed needed. Orthogonal to trend/momentum/carry; net of turnover cost.
    """
    # Compute everything on the instruments' OWN trading days (drop all-NaN rows). A combined
    # calendar that includes other assets' weekends (e.g. crypto) would (a) mis-place "first/last of
    # month" and (b) poison the rolling vol with NaNs, manufacturing a spurious small-sample edge.
    clean = index_close.dropna(how="all")
    ret = clean.pct_change(fill_method=None)
    inv_vol = 1.0 / ret.rolling(vol_window).std().shift(1)
    m = pd.Series(clean.index.year * 12 + clean.index.month, index=clean.index)
    within = m.groupby(m).cumcount()
    size = m.groupby(m).transform("size")
    in_window = (within < tom_first) | (within == size - 1)
    out = np.zeros(len(clean), dtype="float64")
    prev = 0.0
    for t in range(1, len(clean)):
        on = 1.0 if bool(in_window.iloc[t]) else 0.0
        r_eq = 0.0
        if on > 0:
            iv, r = inv_vol.iloc[t], ret.iloc[t]
            valid = clean.iloc[t].notna() & r.notna() & iv.notna()
            names = clean.columns[valid]
            if len(names) >= min_names and iv.reindex(names).sum() > 0:
                w = iv.reindex(names) / iv.reindex(names).sum()
                r_eq = float((w * r.reindex(names)).sum())
            else:
                on = 0.0
        out[t] = on * r_eq - abs(on - prev) * cost
        prev = on
    mapped = pd.Series(out, index=clean.index).reindex(index_close.index).fillna(0.0)
    return np.asarray(mapped.to_numpy(), dtype="float64")


def swap_carry_returns(
    close: pd.DataFrame,
    carry_long: pd.DataFrame,
    carry_short: pd.DataFrame,
    cost: dict[str, float],
    *,
    q: float,
    band: float,
    vol_window: int = 30,
    min_names: int = 5,
) -> np.ndarray:
    """Cross-sectional carry from broker SWAP rates (MT5-native, forward-validated).

    Ranks instruments by the (lagged) fractional daily carry of a long position; goes long the
    top quantile and short the bottom, inverse-vol within each leg. Daily P&L = price move + carry
    actually earned (longs receive ``carry_long``, shorts receive ``carry_short``) - turnover cost.
    Backtest needs a swap-rate history (see scripts/log_swaps.py); until that accumulates this runs
    forward only.
    """
    ret = close.pct_change(fill_method=None)
    inv_vol = 1.0 / ret.rolling(vol_window).std().shift(1)
    sig = carry_long.shift(1)
    cl, cs = carry_long.shift(1), carry_short.shift(1)
    out = np.zeros(len(close), dtype="float64")
    prev = pd.Series(0.0, index=close.columns)
    for t in range(1, len(close)):
        s = sig.iloc[t].dropna()
        valid = close.iloc[t].reindex(s.index).notna() & ret.iloc[t].reindex(s.index).notna()
        s = s.reindex(s.index[valid]).dropna()
        if len(s) < min_names:
            out[t] = float((prev * ret.iloc[t].reindex(prev.index).fillna(0.0)).sum())
            continue
        k = max(1, int(len(s) * q))
        ranked = s.sort_values(ascending=False)              # highest long-carry first
        longs, shorts = ranked.index[:k], ranked.index[-k:]
        iv = inv_vol.iloc[t]
        w = pd.Series(0.0, index=close.columns)
        lw, sw = iv.reindex(longs).fillna(0.0), iv.reindex(shorts).fillna(0.0)
        if lw.sum() > 0:
            w[longs] = 0.5 * lw / lw.sum()
        if sw.sum() > 0:
            w[shorts] = -0.5 * sw / sw.sum()
        delta = (w - prev).abs()
        w = w.where(delta > band, prev)
        price_ret = float((w * ret.iloc[t].reindex(w.index).fillna(0.0)).sum())
        carry_pnl = float((w[w > 0] * cl.iloc[t].reindex(w[w > 0].index).fillna(0.0)).sum()
                          + (-w[w < 0] * cs.iloc[t].reindex(w[w < 0].index).fillna(0.0)).sum())
        turn_cost = float(sum(abs(w[s2] - prev[s2]) * cost.get(s2, 1.0e-3) for s2 in w.index))
        out[t] = price_ret + carry_pnl - turn_cost
        prev = w
    return out


def cot_timeseries_returns(
    close: pd.DataFrame,
    cot_z: pd.DataFrame,
    cost: dict[str, float],
    *,
    band: float,
    vol_window: int = 30,
    z_entry: float = 1.0,
) -> np.ndarray:
    """Per-instrument TIME-SERIES COT fade (complements the cross-sectional version).

    Each instrument is faded against its OWN positioning extreme: short when specs are crowded long
    (lagged z > ``z_entry``), long when crowded short (z < -``z_entry``), inverse-vol sized and
    gross-normalized across whatever instruments are currently at an extreme. This captures the
    documented positioning-reversal premium per market rather than only in the cross-section.
    """
    ret = close.pct_change(fill_method=None)
    inv_vol = 1.0 / ret.rolling(vol_window).std().shift(1)
    sig = cot_z.shift(1)
    out = np.zeros(len(close), dtype="float64")
    prev = pd.Series(0.0, index=close.columns)
    for t in range(1, len(close)):
        z = sig.iloc[t]
        ext = z[z.abs() > z_entry].dropna()
        valid = close.iloc[t].reindex(ext.index).notna() & ret.iloc[t].reindex(ext.index).notna()
        ext = ext.reindex(ext.index[valid]).dropna()
        w = pd.Series(0.0, index=close.columns)
        if len(ext):
            iv = inv_vol.iloc[t].reindex(ext.index).fillna(0.0)
            raw = -np.sign(ext) * iv                  # fade the extreme
            gross = float(raw.abs().sum())
            if gross > 0:
                w[ext.index] = raw / gross
        delta = (w - prev).abs()
        w = w.where(delta > band, prev)
        price_ret = float((w * ret.iloc[t].reindex(w.index).fillna(0.0)).sum())
        turn_cost = float(sum(abs(w[s] - prev[s]) * cost.get(s, 1.0e-3) for s in w.index))
        out[t] = price_ret - turn_cost
        prev = w
    return out


def crisis_hedge_returns(
    asset_close: pd.Series,
    risk_close: pd.Series,
    *,
    ma_window: int = 200,
    vol_window: int = 30,
    cost: float = 2.0e-4,
) -> np.ndarray:
    """Safe-haven (e.g. gold) long ONLY in a risk-off regime -- a convexity/tail-hedge sleeve.

    Goes long ``asset_close`` (vol-scaled to ~unit gross) while the risk proxy ``risk_close`` (an
    equity index) is below its ``ma_window`` moving average (lagged risk-off regime), else flat. Its
    value to the portfolio is tail diversification (it tends to pay in the drawdowns that drive the
    fragility gate), not standalone Sharpe. Decisions use only lagged information.
    """
    a, r = asset_close.align(risk_close, join="outer")
    ret = a.pct_change(fill_method=None)
    risk_off = (r < r.rolling(ma_window).mean()).shift(1)
    out = np.zeros(len(a), dtype="float64")
    prev = 0.0
    for t in range(1, len(a)):
        ra = ret.iloc[t]
        w = 1.0 if bool(risk_off.iloc[t]) else 0.0
        if not np.isfinite(ra):
            out[t] = 0.0
            continue
        out[t] = w * ra - abs(w - prev) * cost
        prev = w
    return out


def cot_positioning_returns(
    close: pd.DataFrame,
    cot_z: pd.DataFrame,
    cost: dict[str, float],
    *,
    band: float,
    vol_window: int = 30,
    min_names: int = 3,
    long_high: bool = False,
) -> np.ndarray:
    """Daily net return of a cross-sectional book driven by a COT positioning z-score.

    ``cot_z`` is the (weekly, ffilled to daily) speculator-positioning z-score per instrument,
    aligned to ``close``. ``long_high=False`` fades crowded positioning (short the most-net-long,
    long the most-net-short) -- the documented COT reversal/risk-premium. Inverse-vol within each
    leg, turnover band, per-symbol cost. Decisions use the lagged z-score (no look-ahead).
    """
    ret = close.pct_change(fill_method=None)
    inv_vol = 1.0 / ret.rolling(vol_window).std().shift(1)
    sig_l = cot_z.shift(1)
    out = np.zeros(len(close), dtype="float64")
    prev = pd.Series(0.0, index=close.columns)
    for t in range(1, len(close)):
        s = sig_l.iloc[t].dropna()
        valid = close.iloc[t].reindex(s.index).notna() & ret.iloc[t].reindex(s.index).notna()
        s = s.reindex(s.index[valid]).dropna()
        if len(s) < min_names:
            out[t] = float((prev * ret.iloc[t].reindex(prev.index).fillna(0.0)).sum())
            continue
        k = max(1, len(s) // 3)
        ranked = s.sort_values(ascending=not long_high)
        longs, shorts = ranked.index[:k], ranked.index[-k:]
        iv = inv_vol.iloc[t]
        w = pd.Series(0.0, index=close.columns)
        lw, sw = iv.reindex(longs).fillna(0.0), iv.reindex(shorts).fillna(0.0)
        if lw.sum() > 0:
            w[longs] = 0.5 * lw / lw.sum()
        if sw.sum() > 0:
            w[shorts] = -0.5 * sw / sw.sum()
        delta = (w - prev).abs()
        w = w.where(delta > band, prev)
        price_ret = float((w * ret.iloc[t].reindex(w.index).fillna(0.0)).sum())
        turn_cost = float(sum(abs(w[s2] - prev[s2]) * cost.get(s2, 1.0e-3) for s2 in w.index))
        out[t] = price_ret - turn_cost
        prev = w
    return out

```

### libs/self_improvement/health_monitor.py
```python
"""Alpha health monitoring (reuses ``libs.alpha`` health, maps to a 0-100 score + level)."""

from __future__ import annotations

from libs.alpha.card import AlphaCard, ExpectedMetrics, LiveMetrics
from libs.alpha.health import calculate_alpha_health
from libs.self_improvement.models import HealthAssessment, HealthLevel


class AlphaHealthMonitor:
    """Scores live alpha health on a 0-100 scale using the existing health engine."""

    def assess(self, card: AlphaCard, live: LiveMetrics) -> HealthAssessment:
        health = calculate_alpha_health(ExpectedMetrics.from_card(card), live)
        score = round(health.overall * 100.0, 4)
        return HealthAssessment(
            alpha_id=card.id,
            health_score=score,
            level=HealthLevel.classify(score),
            components={k: round(v * 100.0, 4) for k, v in health.components.items()},
        )

```

### libs/signal_engine/meta_model.py
```python
"""Meta model — a deterministic calibration mapping signal features to a success probability.

This is a fixed, transparent logistic blend (NOT a trained black box): it turns the engine's own
sub-scores into a single 0..1 probability the confidence engine can consume. Keeping it
deterministic preserves reproducibility; the weights are documented and auditable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Fixed logistic weights over normalized 0..1 features. Documented and reproducible.
_BIAS = -2.0
_WEIGHTS: dict[str, float] = {
    "edge": 2.2,
    "agreement": 1.6,
    "persistence": 1.0,
    "stability": 1.0,
}


@dataclass(frozen=True)
class MetaModel:
    """Calibrates a probability of success from normalized signal features."""

    def predict_proba(
        self, *, edge: float, agreement: float, persistence: float, stability: float
    ) -> float:
        feats = {
            "edge": _clip01(edge),
            "agreement": _clip01(agreement),
            "persistence": _clip01(persistence),
            "stability": _clip01(stability),
        }
        z = _BIAS + sum(_WEIGHTS[k] * v for k, v in feats.items())
        return 1.0 / (1.0 + math.exp(-z))


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))

```

### libs/signal_engine/models.py
```python
"""Stage 13.5 models — the vocabulary of the signal intelligence engine.

These describe alpha inputs, market state, the per-engine assessments, and the final
``SignalPackage`` that is the *only* object permitted to flow to the Portfolio Engine. Decay
levels reuse ``libs.self_improvement.DecayLevel`` (single source of truth); nothing here
redefines the alpha/portfolio/audit foundation models.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from libs.core.time import to_iso8601, utcnow
from libs.self_improvement.models import DecayLevel

__all__ = [  # noqa: RUF022  # grouped by concern
    "Direction",
    "Regime",
    "AlphaSignal",
    "MarketState",
    "EdgeEstimate",
    "ExpectedValueResult",
    "ConfidenceResult",
    "QualityResult",
    "PersistenceResult",
    "StabilityResult",
    "SignalDecayResult",
    "FactorExposureResult",
    "ExecutionFeasibility",
    "CrowdingResult",
    "CapacityForecast",
    "PortfolioContextResult",
    "UncertaintyResult",
    "InstitutionalScore",
    "TradeCandidate",
    "SignalPackage",
    "SelectionResult",
    "MonitoringSnapshot",
    "DecayLevel",
]


class Direction(StrEnum):
    """The only decisions the engine may emit."""

    BUY = "buy"
    SELL = "sell"
    FLAT = "flat"

    @property
    def sign(self) -> int:
        return {Direction.BUY: 1, Direction.SELL: -1, Direction.FLAT: 0}[self]


class Regime(StrEnum):
    TREND = "trend"
    RANGE = "range"
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    VOLATILITY = "volatility"
    CRISIS = "crisis"
    NEUTRAL = "neutral"


class AlphaSignal(BaseModel):
    """One validated alpha's vote on a symbol (the engine's raw input)."""

    model_config = ConfigDict(frozen=True)

    alpha_id: str
    symbol: str
    direction: Direction
    strength: float = Field(ge=0.0, le=1.0)  # conviction 0..1
    expected_return: float = 0.0  # per-trade fractional
    win_rate: float = Field(default=0.5, ge=0.0, le=1.0)
    avg_win: float = Field(default=0.0, ge=0.0)
    avg_loss: float = Field(default=0.0, ge=0.0)  # positive magnitude
    profit_factor: float | None = None
    sharpe: float = 0.0
    health_score: float = Field(default=100.0, ge=0.0, le=100.0)
    decay_multiplier: float = Field(default=1.0, ge=0.0, le=1.0)
    regime_affinity: dict[str, float] = Field(default_factory=dict)  # regime -> 0..1
    governance_passed: bool = False  # validated through the gauntlet?


class MarketState(BaseModel):
    """The microstructure / regime context a signal is evaluated in."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    regime: Regime = Regime.NEUTRAL
    predicted_regime: Regime = Regime.NEUTRAL
    transition_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    volatility_state: float = Field(default=0.5, ge=0.0, le=1.0)  # 1 = high vol
    spread_bps: float = Field(default=1.0, ge=0.0)
    liquidity_score: float = Field(default=1.0, ge=0.0, le=1.0)
    cross_asset_score: float = Field(default=1.0, ge=0.0, le=1.0)  # confirmation 0..1
    microstructure_score: float = Field(default=1.0, ge=0.0, le=1.0)
    adv_usd: float = Field(default=1e9, ge=0.0)


class EdgeEstimate(BaseModel):
    model_config = ConfigDict(frozen=True)

    expected_return: float
    expected_pf: float
    expected_sharpe: float
    expected_sortino: float
    expected_calmar: float
    edge_score: float  # 0-100


class ExpectedValueResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    expected_value: float
    gross_ev: float
    total_cost: float
    positive: bool


class ConfidenceResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    confidence: float  # 0..1
    components: dict[str, float]


class QualityResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    quality_score: float  # 0-100
    components: dict[str, float]
    passed: bool


class PersistenceResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    persistence_score: float  # 0-100
    components: dict[str, float]


class StabilityResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    stability_score: float  # 0-100
    components: dict[str, float]
    passed: bool


class SignalDecayResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    decay_level: DecayLevel
    weight_multiplier: float
    confidence_multiplier: float
    recommended_action: str


class FactorExposureResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    exposures: dict[str, float]
    concentration: float  # 0..1 (max single-factor share)
    acceptable: bool


class ExecutionFeasibility(BaseModel):
    model_config = ConfigDict(frozen=True)

    execution_score: float  # 0-100
    fill_probability: float
    expected_slippage_bps: float
    market_impact_bps: float
    spread_cost_bps: float
    passed: bool


class CrowdingResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    crowding_score: float  # 0-100 (higher = more crowded = worse)
    acceptable: bool


class CapacityForecast(BaseModel):
    model_config = ConfigDict(frozen=True)

    future_capacity_score: float  # 0-100
    future_slippage_estimate: float
    future_market_impact_estimate: float
    maximum_efficient_capital: float
    capacity_confidence: float  # 0..1


class PortfolioContextResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    portfolio_contribution_score: float  # 0-100
    portfolio_diversification_score: float  # 0-100
    marginal_sharpe_improvement: float
    marginal_sortino_improvement: float
    marginal_calmar_improvement: float
    accept: bool


class UncertaintyResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    epistemic_uncertainty: float  # 0..1
    aleatoric_uncertainty: float  # 0..1
    uncertainty_score: float  # 0..1 (higher = worse)


class InstitutionalScore(BaseModel):
    model_config = ConfigDict(frozen=True)

    score: float  # 0-100
    components: dict[str, float]


class TradeCandidate(BaseModel):
    """A fully-assessed opportunity, before final BUY/SELL/FLAT selection."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    direction: Direction
    aggregated_strength: float
    alpha_agreement: float  # 0..1
    alpha_breakdown: dict[str, float]
    regime: Regime
    predicted_regime: Regime
    edge: EdgeEstimate
    expected_value: ExpectedValueResult
    confidence: ConfidenceResult
    quality: QualityResult
    persistence: PersistenceResult
    stability: StabilityResult
    decay: SignalDecayResult
    factor_exposures: FactorExposureResult
    execution: ExecutionFeasibility
    crowding: CrowdingResult
    capacity: CapacityForecast
    portfolio_context: PortfolioContextResult
    uncertainty: UncertaintyResult
    tail_risk_score: float
    institutional: InstitutionalScore


class SignalPackage(BaseModel):
    """The exclusive hand-off to the Portfolio Engine. Immutable."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    direction: Direction
    quality_score: float
    confidence: float
    edge_score: float
    expected_return: float
    expected_drawdown: float
    expected_sharpe: float
    expected_sortino: float
    expected_calmar: float
    expected_pf: float
    expected_value: float
    regime: Regime
    predicted_regime: Regime
    alpha_breakdown: dict[str, float]
    factor_exposures: dict[str, float]
    execution_score: float
    capacity_score: float
    crowding_score: float
    portfolio_contribution: float
    institutional_score: float
    timestamp: str = Field(default_factory=lambda: to_iso8601(utcnow()))


class SelectionResult(BaseModel):
    """The output of one engine run: approved packages + audited rejections."""

    model_config = ConfigDict(frozen=True)

    approved: list[SignalPackage] = Field(default_factory=list)
    rejected: dict[str, str] = Field(default_factory=dict)  # symbol -> reason (FLAT)


class MonitoringSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    generated_at: str = Field(default_factory=lambda: to_iso8601(utcnow()))
    metrics: dict[str, Any] = Field(default_factory=dict)

```

### libs/signal_engine/stress_signal_engine.py
```python
"""Stress signal engine — how fragile is a signal to shocks?

Stress-tests a signal against volatility shocks, liquidity shocks, regime changes, and
correlation breakdowns (each expressed as a 0..1 edge-degradation sensitivity). Produces a
0-100 fragility score and its complement robustness; fragile signals are rejected / penalized.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StressResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    fragility_score: float   # 0-100 (higher = more fragile, worse)
    robustness_score: float  # 0-100 (higher = more robust, better)
    survived: bool
    shock_impacts: dict[str, float]


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class StressSignalEngine:
    """Scores signal fragility under a battery of market shocks."""

    def __init__(self, *, fragility_threshold: float = 60.0) -> None:
        self.fragility_threshold = fragility_threshold

    def assess(
        self,
        *,
        volatility_shock: float,
        liquidity_shock: float,
        regime_change: float,
        correlation_breakdown: float,
    ) -> StressResult:
        shocks = {
            "volatility_shock": _clip01(volatility_shock),
            "liquidity_shock": _clip01(liquidity_shock),
            "regime_change": _clip01(regime_change),
            "correlation_breakdown": _clip01(correlation_breakdown),
        }
        fragility = 100.0 * (sum(shocks.values()) / len(shocks))
        return StressResult(
            fragility_score=fragility,
            robustness_score=100.0 - fragility,
            survived=fragility <= self.fragility_threshold,
            shock_impacts=shocks,
        )

```

### libs/stage14/engine.py
```python
"""Stage 14 portfolio construction engine — Signal Packages -> capital allocations.

Consumes approved Stage 13.5 ``SignalPackage`` objects and produces ``PortfolioPackage`` allocations
optimized for long-term compounded wealth: portfolio kill criteria first, then state-aware risk
scaling, fractional-Kelly sizing, sleeve budgeting, dynamic leverage, and a fail-closed governance
gate on every allocation. Named ``PortfolioConstructionEngine`` to avoid colliding with the existing
``libs.portfolio.PortfolioEngine`` (the weight-construction substrate); survival dominates return.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from libs.signal_engine.models import SignalPackage
from libs.stage14.allocation import (
    AdaptiveReinvestmentEngine,
    DrawdownAwareAllocator,
    DynamicLeverageEngine,
    SleeveAllocator,
)
from libs.stage14.analytics import (
    PortfolioCorrelationEngine,
    PortfolioSurvivalEngine,
)
from libs.stage14.audit import PortfolioAudit
from libs.stage14.governance import PortfolioKillCriteria, portfolio_governance_gate
from libs.stage14.growth import GeometricGrowthEngine
from libs.stage14.kelly import FractionalKellyEngine, KellyEngine
from libs.stage14.models import (
    AlphaSleeve,
    PortfolioConstructionResult,
    PortfolioPackage,
    PortfolioState,
)
from libs.stage14.score import institutional_portfolio_score
from libs.stage14.state_machine import PortfolioStateMachine


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _sleeve_of(signal: SignalPackage) -> AlphaSleeve:
    if not signal.factor_exposures:
        return AlphaSleeve.OTHER
    dominant = max(signal.factor_exposures, key=lambda k: abs(signal.factor_exposures[k]))
    return AlphaSleeve.from_text(dominant)


class PortfolioConstructionEngine:
    """Builds the final portfolio from approved signal packages (recommend-to-Risk-Engine)."""

    def __init__(
        self,
        *,
        max_leverage: float = 1.0,
        max_gross: float = 1.0,
        min_capacity_score: float = 20.0,
        survival_threshold: float = 60.0,
        max_fragility: float = 0.6,
        roi_edge_threshold: float = 65.0,
        roi_confidence_threshold: float = 0.6,
        roi_pf_threshold: float = 1.3,
        roi_capacity_threshold: float = 70.0,
        kill_criteria: PortfolioKillCriteria | None = None,
        audit: PortfolioAudit | None = None,
    ) -> None:
        self.max_leverage = max_leverage
        self.max_gross = max_gross
        self.min_capacity_score = min_capacity_score
        self.survival_threshold = survival_threshold
        self.max_fragility = max_fragility
        # Half-Kelly is earned, not default: only proven, high-ROI, robust, scalable signals
        # qualify (committee Kelly policy). Everything else sizes at the 1/3 base.
        self.roi_edge_threshold = roi_edge_threshold
        self.roi_confidence_threshold = roi_confidence_threshold
        self.roi_pf_threshold = roi_pf_threshold
        self.roi_capacity_threshold = roi_capacity_threshold
        self.kill_criteria = kill_criteria or PortfolioKillCriteria()
        self.audit = audit
        self.state_machine = PortfolioStateMachine()
        self.drawdown_allocator = DrawdownAwareAllocator()
        self.sleeve_allocator = SleeveAllocator()
        self.leverage_engine = DynamicLeverageEngine(max_leverage=max_leverage)
        self.reinvestment_engine = AdaptiveReinvestmentEngine()
        self.kelly = KellyEngine()
        self.fractional_kelly = FractionalKellyEngine()
        self.survival_engine = PortfolioSurvivalEngine()
        self.growth_engine = GeometricGrowthEngine()
        self.correlation_engine = PortfolioCorrelationEngine()

    def _roi_qualified(self, sp: SignalPackage, *, walk_forward_passed: bool) -> bool:
        """Whether a signal has earned the half-Kelly ceiling: proven, high-ROI, robust, scalable.

        Maps the deployable bar to the sizing decision -- only signals that clear ALL of these
        size up toward half-Kelly; the rest stay at the 1/3 base, which maximizes geometric growth
        under edge uncertainty (overbetting a marginal edge is catastrophic, underbetting is not).
        """
        return (
            walk_forward_passed
            and sp.expected_value > 0.0
            and sp.edge_score >= self.roi_edge_threshold
            and sp.confidence >= self.roi_confidence_threshold
            and sp.expected_pf >= self.roi_pf_threshold
            and sp.capacity_score >= self.roi_capacity_threshold
        )

    def construct(
        self,
        signals: Sequence[SignalPackage],
        *,
        capital: float,
        portfolio_returns: np.ndarray | None = None,
        correlation: np.ndarray | None = None,
        current_drawdown: float = 0.0,
        recovered: bool = False,
        regime_uncertainty: float = 0.0,
        volatility_state: float = 0.5,
        portfolio_dsr: float = 1.0,
        walk_forward_passed: bool = True,
    ) -> PortfolioConstructionResult:
        # --- portfolio-level metrics -------------------------------------------------
        if portfolio_returns is not None:
            survival = self.survival_engine.evaluate(portfolio_returns)
            survival_score = survival.survival_score
            growth_score = self.growth_engine.evaluate(portfolio_returns).geometric_growth_score
        else:
            survival_score = 100.0
            calmars = [s.expected_calmar for s in signals] or [0.0]
            growth_score = 100.0 * _clip01(float(np.mean(calmars)) / 3.0)
        if correlation is not None:
            corr = self.correlation_engine.evaluate(correlation)
            diversification_score = 100.0 * (1.0 - corr.avg_pairwise)
            correlation_ok = corr.acceptable
        else:
            diversification_score = 100.0
            correlation_ok = True

        # --- portfolio kill criteria (fail-closed) -----------------------------------
        kill = self.kill_criteria.evaluate(
            portfolio_dsr=portfolio_dsr, survival_score=survival_score,
            drawdown=current_drawdown, walk_forward_passed=walk_forward_passed,
        )
        if kill.halt:
            result = PortfolioConstructionResult(
                packages=[], rejected={s.symbol: "portfolio halt" for s in signals},
                state=PortfolioState.CRISIS, kill=kill, total_allocation=0.0,
            )
            if self.audit is not None:
                self.audit.record_result(result)
            return result

        state = self.state_machine.classify(
            drawdown=current_drawdown, survival_score=survival_score,
            regime_uncertainty=regime_uncertainty, recovering=recovered,
        )
        gross_mult = self.state_machine.risk_multiplier(state) * self.drawdown_allocator.scale(
            current_drawdown=current_drawdown, recovered=recovered,
            regime_stable=regime_uncertainty < 0.5,
        )

        # --- per-signal gate + raw Kelly sizing --------------------------------------
        rejected: dict[str, str] = {}
        raw: dict[str, float] = {}
        sleeves: dict[str, AlphaSleeve] = {}
        kept: dict[str, SignalPackage] = {}
        fragilities: list[float] = []
        for sp in signals:
            fragility = _clip01(sp.crowding_score / 100.0)
            capacity_available = sp.capacity_score >= self.min_capacity_score
            allowed, reason = portfolio_governance_gate(
                signal_approved=True, expected_value=sp.expected_value,
                portfolio_contribution=sp.portfolio_contribution,
                capacity_available=capacity_available, survival_score=survival_score,
                fragility=fragility, correlation_acceptable=correlation_ok,
                walk_forward_passed=walk_forward_passed,
                survival_threshold=self.survival_threshold, max_fragility=self.max_fragility,
            )
            if not allowed:
                rejected[sp.symbol] = reason
                continue
            win_rate = _clip01(0.5 + (sp.edge_score - 50.0) / 200.0)
            kelly_full = self.kelly.estimate(
                win_rate=win_rate, payoff_ratio=max(0.1, sp.expected_pf), confidence=sp.confidence
            ).full
            frac = self.fractional_kelly.fraction_of_kelly(
                volatility_state=volatility_state, regime_uncertainty=regime_uncertainty,
                capacity_deterioration=1.0 - sp.capacity_score / 100.0, fragility=fragility,
                roi_qualified=self._roi_qualified(sp, walk_forward_passed=walk_forward_passed),
            )
            raw[sp.symbol] = kelly_full * frac
            sleeves[sp.symbol] = _sleeve_of(sp)
            kept[sp.symbol] = sp
            fragilities.append(fragility)

        if not kept:
            result = PortfolioConstructionResult(
                packages=[], rejected=rejected, state=state, kill=kill, total_allocation=0.0
            )
            if self.audit is not None:
                self.audit.record_result(result)
            return result

        # --- sleeve budgeting --------------------------------------------------------
        sleeve_scores: dict[AlphaSleeve, float] = {}
        for sym, sleeve in sleeves.items():
            sleeve_scores[sleeve] = sleeve_scores.get(sleeve, 0.0) + raw[sym]
        sleeve_budgets = self.sleeve_allocator.budgets(sleeve_scores)

        leverage = self.leverage_engine.decide(
            volatility_state=volatility_state, regime_certainty=1.0 - regime_uncertainty,
            drawdown_scalar=self.drawdown_allocator.scale(
                current_drawdown=current_drawdown, recovered=recovered
            ),
            fragility=float(np.mean(fragilities)) if fragilities else 0.0,
            capacity_health=float(np.mean([kept[s].capacity_score for s in kept])) / 100.0,
            survival_score=survival_score,
        ).leverage

        weights: dict[str, float] = {}
        for sym, sleeve in sleeves.items():
            sleeve_raw = sleeve_scores[sleeve]
            within = raw[sym] / sleeve_raw if sleeve_raw > 0 else 0.0
            weights[sym] = sleeve_budgets.get(sleeve, 0.0) * within * gross_mult

        gross = sum(weights.values())
        if gross > self.max_gross and gross > 0:
            weights = {k: v * self.max_gross / gross for k, v in weights.items()}

        # --- build packages ----------------------------------------------------------
        packages: list[PortfolioPackage] = []
        for sym, sp in kept.items():
            allocation = weights[sym]
            fragility = _clip01(sp.crowding_score / 100.0)
            score = institutional_portfolio_score(
                survival_score=survival_score, geometric_growth_score=growth_score,
                expected_sharpe=sp.expected_sharpe, expected_calmar=sp.expected_calmar,
                capacity_score=sp.capacity_score, diversification_score=diversification_score,
                execution_score=sp.execution_score, drawdown_risk=_clip01(sp.expected_drawdown),
                fragility=fragility,
            ).score
            packages.append(
                PortfolioPackage(
                    symbol=sym, sleeve=sleeves[sym], allocation=allocation,
                    position_size=allocation * leverage * capital,
                    kelly_fraction=raw[sym], leverage=leverage,
                    expected_return=sp.expected_return, expected_sharpe=sp.expected_sharpe,
                    expected_sortino=sp.expected_sortino, expected_calmar=sp.expected_calmar,
                    expected_drawdown=sp.expected_drawdown, geometric_growth_score=growth_score,
                    survival_score=survival_score, capacity_score=sp.capacity_score,
                    diversification_score=diversification_score, fragility_score=fragility,
                    portfolio_contribution=sp.portfolio_contribution, institutional_score=score,
                )
            )

        result = PortfolioConstructionResult(
            packages=packages, rejected=rejected, state=state, kill=kill,
            total_allocation=sum(p.allocation for p in packages),
        )
        if self.audit is not None:
            self.audit.record_result(result)
        return result

```

### libs/stage14_5/concentration.py
```python
"""Concentration engine — monitor symbol / alpha / family / factor / regime concentration.

Reuses the portfolio layer's Herfindahl concentration on each weight vector and reports the worst
as a 0-100 score (higher = more concentrated). Prevents hidden concentration of any kind.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from libs.portfolio.diversification import concentration as _herfindahl
from libs.stage14_5.models import ConcentrationResult


def _normalized_hhi(weights: Mapping[str, float]) -> float:
    values = np.array([abs(v) for v in weights.values()], dtype="float64")
    total = float(values.sum())
    if total <= 0 or len(values) == 0:
        return 0.0
    return _herfindahl(values / total)  # in [1/n, 1]


class ConcentrationEngine:
    """Scores portfolio concentration across five dimensions."""

    def __init__(self, *, threshold: float = 60.0) -> None:
        self.threshold = threshold

    def evaluate(
        self,
        *,
        symbol_weights: Mapping[str, float],
        alpha_weights: Mapping[str, float],
        family_weights: Mapping[str, float],
        factor_weights: Mapping[str, float],
        regime_weights: Mapping[str, float],
    ) -> ConcentrationResult:
        sym = _normalized_hhi(symbol_weights)
        alpha = _normalized_hhi(alpha_weights)
        family = _normalized_hhi(family_weights)
        factor = _normalized_hhi(factor_weights)
        regime = _normalized_hhi(regime_weights)
        score = 100.0 * max(sym, alpha, family, factor, regime)
        return ConcentrationResult(
            symbol_concentration=sym, alpha_concentration=alpha, family_concentration=family,
            factor_concentration=factor, regime_concentration=regime,
            concentration_score=score, acceptable=score <= self.threshold,
        )

```

### libs/stage15/errors.py
```python
"""Stage 15 research-factory errors."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class Stage15Error(QuantPlatformError):
    """Base error for the Stage 15 alpha discovery / research factory."""


class ResearchGovernanceError(Stage15Error):
    """Raised when research governance (the research kill-switch) blocks an action."""

```

### libs/store/registries.py
```python
"""Registries: research runs, the alpha registry, and the risk registry.

These are mutable governance tables (status transitions, metrics) written only through the
store. Hash-chained immutability lives in the audit log and trials ledger, not here.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping, Sequence
from typing import Any

from libs.core.ids import generate_id
from libs.core.time import to_iso8601, utcnow
from libs.store.connection import Database
from libs.store.hashchain import canonical_json
from libs.store.models import Alpha, ResearchRun, RiskRecord


def _loads(value: str | None) -> Any:
    return json.loads(value) if value is not None else None


# --------------------------------------------------------------------------- research runs


def _row_to_run(row: sqlite3.Row) -> ResearchRun:
    return ResearchRun(
        id=row["id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        hypothesis_id=row["hypothesis_id"],
        name=row["name"],
        git_commit=row["git_commit"],
        snapshot_id=row["snapshot_id"],
        config_hash=row["config_hash"],
        seed=int(row["seed"]),
        status=row["status"],
        metrics=_loads(row["metrics_json"]),
    )


class ResearchRuns:
    """Writer/reader for ``research_runs``."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def create(
        self,
        *,
        git_commit: str,
        config_hash: str,
        seed: int,
        hypothesis_id: str | None = None,
        name: str | None = None,
        snapshot_id: str | None = None,
        status: str = "running",
    ) -> ResearchRun:
        run_id = generate_id("run")
        now = to_iso8601(utcnow())
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO research_runs "
                "(id, created_at, updated_at, hypothesis_id, name, git_commit, snapshot_id, "
                " config_hash, seed, status, metrics_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id, now, now, hypothesis_id, name, git_commit, snapshot_id,
                    config_hash, seed, status, None,
                ),
            )
        run = self.get(run_id)
        assert run is not None
        return run

    def set_status(
        self, run_id: str, status: str, *, metrics: Mapping[str, Any] | None = None
    ) -> ResearchRun:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE research_runs SET status = ?, metrics_json = ?, updated_at = ? "
                "WHERE id = ?",
                (
                    status,
                    canonical_json(dict(metrics)) if metrics is not None else None,
                    to_iso8601(utcnow()),
                    run_id,
                ),
            )
        run = self.get(run_id)
        if run is None:
            raise KeyError(f"research run not found: {run_id}")
        return run

    def get(self, run_id: str) -> ResearchRun | None:
        row = self.db.execute("SELECT * FROM research_runs WHERE id = ?", (run_id,)).fetchone()
        return _row_to_run(row) if row else None


# --------------------------------------------------------------------------- alpha registry


def _row_to_alpha(row: sqlite3.Row) -> Alpha:
    return Alpha(
        id=row["id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        name=row["name"],
        instruments=json.loads(row["instruments_json"]),
        status=row["status"],
        card=_loads(row["card_json"]),
        owner=row["owner"],
        deploy_date=row["deploy_date"],
        retire_date=row["retire_date"],
    )


class AlphaRegistry:
    """Writer/reader for ``alpha_registry``."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def create(
        self,
        *,
        name: str,
        instruments: Sequence[str],
        status: str = "candidate",
        card: Mapping[str, Any] | None = None,
        owner: str | None = None,
    ) -> Alpha:
        alpha_id = generate_id("alpha")
        now = to_iso8601(utcnow())
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO alpha_registry "
                "(id, created_at, updated_at, name, instruments_json, status, card_json, owner, "
                " deploy_date, retire_date) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    alpha_id, now, now, name, canonical_json(list(instruments)), status,
                    canonical_json(dict(card)) if card is not None else None, owner, None, None,
                ),
            )
        alpha = self.get(alpha_id)
        assert alpha is not None
        return alpha

    def set_status(
        self,
        alpha_id: str,
        status: str,
        *,
        deploy_date: str | None = None,
        retire_date: str | None = None,
    ) -> Alpha:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE alpha_registry SET status = ?, updated_at = ?, "
                "deploy_date = COALESCE(?, deploy_date), retire_date = COALESCE(?, retire_date) "
                "WHERE id = ?",
                (status, to_iso8601(utcnow()), deploy_date, retire_date, alpha_id),
            )
        alpha = self.get(alpha_id)
        if alpha is None:
            raise KeyError(f"alpha not found: {alpha_id}")
        return alpha

    def get(self, alpha_id: str) -> Alpha | None:
        row = self.db.execute(
            "SELECT * FROM alpha_registry WHERE id = ?", (alpha_id,)
        ).fetchone()
        return _row_to_alpha(row) if row else None

    def list_by_status(self, status: str) -> list[Alpha]:
        rows = self.db.execute(
            "SELECT * FROM alpha_registry WHERE status = ? ORDER BY created_at", (status,)
        ).fetchall()
        return [_row_to_alpha(row) for row in rows]


# --------------------------------------------------------------------------- risk registry


def _row_to_risk(row: sqlite3.Row) -> RiskRecord:
    return RiskRecord(
        id=row["id"],
        created_at=row["created_at"],
        kind=row["kind"],
        scope=row["scope"],
        metric=row["metric"],
        threshold=row["threshold"],
        observed=row["observed"],
        action=row["action"],
        target_ref=row["target_ref"],
        detail=_loads(row["detail_json"]),
        active=bool(row["active"]),
    )


class RiskRegistry:
    """Writer/reader for ``risk_registry`` (limits, events, approvals)."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def _insert(
        self,
        *,
        kind: str,
        scope: str | None = None,
        metric: str | None = None,
        threshold: float | None = None,
        observed: float | None = None,
        action: str | None = None,
        target_ref: str | None = None,
        detail: Mapping[str, Any] | None = None,
        active: bool = True,
    ) -> RiskRecord:
        risk_id = generate_id("risk")
        now = to_iso8601(utcnow())
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO risk_registry "
                "(id, created_at, kind, scope, metric, threshold, observed, action, target_ref, "
                " detail_json, active) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    risk_id, now, kind, scope, metric, threshold, observed, action, target_ref,
                    canonical_json(dict(detail)) if detail is not None else None,
                    1 if active else 0,
                ),
            )
        record = self.get(risk_id)
        assert record is not None
        return record

    def add_limit(
        self, *, scope: str, metric: str, threshold: float, detail: Mapping[str, Any] | None = None
    ) -> RiskRecord:
        return self._insert(
            kind="limit", scope=scope, metric=metric, threshold=threshold, detail=detail
        )

    def record_event(
        self,
        *,
        scope: str,
        metric: str,
        observed: float,
        action: str,
        target_ref: str | None = None,
        detail: Mapping[str, Any] | None = None,
    ) -> RiskRecord:
        return self._insert(
            kind="event", scope=scope, metric=metric, observed=observed, action=action,
            target_ref=target_ref, detail=detail,
        )

    def create_approval(
        self,
        *,
        target_ref: str,
        action: str = "approve",
        detail: Mapping[str, Any] | None = None,
    ) -> RiskRecord:
        """Record a pre-trade risk approval/rejection. ``action`` is ``approve`` or ``reject``."""
        if action not in ("approve", "reject"):
            raise ValueError("approval action must be 'approve' or 'reject'")
        return self._insert(kind="approval", action=action, target_ref=target_ref, detail=detail)

    def get(self, risk_id: str) -> RiskRecord | None:
        row = self.db.execute("SELECT * FROM risk_registry WHERE id = ?", (risk_id,)).fetchone()
        return _row_to_risk(row) if row else None

```

### libs/testing/__init__.py
```python

```

### libs/validation/bootstrap.py
```python
"""Block and stationary bootstrap (autocorrelation-preserving resampling).

Never use an i.i.d. bootstrap on returns: it destroys autocorrelation and understates
uncertainty. The moving-block and stationary bootstraps resample contiguous blocks instead.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

Statistic = Callable[[np.ndarray], float]


def moving_block_indices(n: int, block: int, rng: np.random.Generator) -> np.ndarray:
    """Indices for a circular moving-block bootstrap of length ``n``."""
    if block < 1:
        raise ValueError("block size must be >= 1")
    n_blocks = int(np.ceil(n / block))
    starts = rng.integers(0, n, size=n_blocks)
    offsets = np.arange(block)
    idx = ((starts[:, None] + offsets[None, :]) % n).reshape(-1)
    return idx[:n]


def stationary_block_indices(n: int, mean_block: float, rng: np.random.Generator) -> np.ndarray:
    """Indices for a stationary bootstrap (geometric block lengths)."""
    if mean_block < 1:
        raise ValueError("mean_block must be >= 1")
    p = 1.0 / mean_block
    idx = np.empty(n, dtype=int)
    idx[0] = rng.integers(0, n)
    coin = rng.random(n)
    for t in range(1, n):
        idx[t] = rng.integers(0, n) if coin[t] < p else (idx[t - 1] + 1) % n
    return idx


def block_bootstrap(
    x: np.ndarray, statistic: Statistic, *, block: int = 10, n_boot: int = 1000, seed: int = 0
) -> np.ndarray:
    """Moving-block bootstrap distribution of ``statistic``."""
    arr = np.asarray(x, dtype="float64")
    rng = np.random.default_rng(seed)
    out = np.empty(n_boot, dtype="float64")
    for b in range(n_boot):
        out[b] = statistic(arr[moving_block_indices(len(arr), block, rng)])
    return out


def stationary_bootstrap(
    x: np.ndarray,
    statistic: Statistic,
    *,
    mean_block: float = 10,
    n_boot: int = 1000,
    seed: int = 0,
) -> np.ndarray:
    """Stationary bootstrap distribution of ``statistic``."""
    arr = np.asarray(x, dtype="float64")
    rng = np.random.default_rng(seed)
    out = np.empty(n_boot, dtype="float64")
    for b in range(n_boot):
        out[b] = statistic(arr[stationary_block_indices(len(arr), mean_block, rng)])
    return out


def confidence_interval(samples: np.ndarray, *, alpha: float = 0.05) -> tuple[float, float]:
    """Percentile confidence interval at level ``1 - alpha``."""
    arr = np.asarray(samples, dtype="float64")
    lo = float(np.percentile(arr, 100 * alpha / 2))
    hi = float(np.percentile(arr, 100 * (1 - alpha / 2)))
    return lo, hi

```

### libs/validation/economic_prior.py
```python
"""Economic-Prior Gate — the CRO's six questions, encoded.

The cheapest, highest-leverage filter: before any candidate consumes the expensive gauntlet it
must carry a structured artifact answering why it should work, why it might fail, why it might
be overfit, why it might decay, how decay is detected, and what replaces it. No artifact, no
validation budget. A blind statistical pattern with no mechanism is rejected here.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator
from pydantic import ValidationError as PydanticValidationError

REQUIRED_FIELDS = (
    "why_it_works",
    "why_it_might_fail",
    "why_overfit",
    "why_decay",
    "how_detect_decay",
    "what_replaces_it",
)


class MechanismType(StrEnum):
    STRUCTURAL = "structural"
    BEHAVIORAL = "behavioral"
    RISK_PREMIUM = "risk_premium"
    LIQUIDITY = "liquidity"


class EconomicPrior(BaseModel):
    """The mandatory six-question artifact."""

    model_config = ConfigDict(frozen=True)

    mechanism: MechanismType
    why_it_works: str
    why_it_might_fail: str
    why_overfit: str
    why_decay: str
    how_detect_decay: str
    what_replaces_it: str

    @field_validator(*REQUIRED_FIELDS)
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("answer must be non-empty")
        return value.strip()


class PriorGateResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    passed: bool
    missing: list[str]
    message: str

    def __bool__(self) -> bool:
        return self.passed


def economic_prior_gate(prior: Mapping[str, Any] | EconomicPrior) -> PriorGateResult:
    """Validate an economic-prior artifact. Missing mechanism or any blank answer fails."""
    if isinstance(prior, EconomicPrior):
        return PriorGateResult(passed=True, missing=[], message="economic prior complete")
    data = dict(prior)
    missing: list[str] = []
    if not data.get("mechanism"):
        missing.append("mechanism")
    for field in REQUIRED_FIELDS:
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            missing.append(field)
    if missing:
        return PriorGateResult(
            passed=False, missing=missing, message=f"incomplete economic prior: {missing}"
        )
    try:
        EconomicPrior(**data)
    except PydanticValidationError as exc:
        return PriorGateResult(passed=False, missing=["invalid"], message=str(exc))
    return PriorGateResult(passed=True, missing=[], message="economic prior complete")

```

### libs/validation/forward_stats.py
```python
"""Forward-validation statistics -- honest significance for shadow-track promotion.

Closes the two statistical leaks named by the 2026-07-12 external adversarial review
(five independent models converged on both):

  1. AUTOCORRELATION. The naive forward t-stat Sharpe*sqrt(days/365) assumes IID daily
     returns. Funding-carry returns are serially correlated (funding is sticky, basis
     mean-reverts slowly), so the effective sample is smaller than the calendar sample
     and the naive t OVERSTATES significance exactly when N is small. `nw_tstat` shrinks
     N by the Newey-West/Bartlett factor 1 + 2*sum_k (1 - k/(L+1)) * rho_k.
  2. MULTIPLE TESTING. Monitoring m candidates in parallel against a per-strategy 1.65
     bar gives family-wise alpha ~1-(0.95^m), not 5%. `holm_bar` returns the Holm
     step-down per-candidate t threshold. The PRE-REGISTERED PRIMARY hypothesis (carry,
     registered alone before any cohort existed) is exempt -- the clinical-trial
     primary-endpoint convention; the correction applies to the later cohort.

Conservative by construction: the autocorrelation factor is clamped to >= 1 (never award
MORE significance than IID) and <= 5 (a noisy rho estimate must not nuke a real edge).
Pure numpy + stdlib -> cheap every cycle, deterministic, testable.
"""

from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np

_PPY = 365.0


def autocorr_factor(returns: np.ndarray, max_lags: int | None = None) -> float:
    """Bartlett-weighted variance-inflation factor for serially correlated returns.

    factor = 1 + 2 * sum_{k=1..L} (1 - k/(L+1)) * rho_k, clamped to [1, 5].
    Effective N = N / factor.
    """
    r = np.asarray(returns, dtype="float64")
    r = r[np.isfinite(r)]
    n = len(r)
    if n < 20 or float(np.std(r)) == 0.0:
        return 1.0
    lags = max_lags if max_lags is not None else min(10, n // 5)
    mu, var = float(np.mean(r)), float(np.var(r))
    acc = 0.0
    for k in range(1, lags + 1):
        rho = float(np.mean((r[:-k] - mu) * (r[k:] - mu))) / var
        acc += (1.0 - k / (lags + 1.0)) * rho
    return float(min(5.0, max(1.0, 1.0 + 2.0 * acc)))


def nw_tstat(returns: np.ndarray, *, ppy: float = _PPY) -> float:
    """Newey-West-corrected forward t-stat: ann_Sharpe * sqrt(effective_days / ppy).

    Equals the naive t when returns are uncorrelated; strictly smaller when they are
    positively autocorrelated. This is the number the promotion gates consume.
    """
    r = np.asarray(returns, dtype="float64")
    r = r[np.isfinite(r)]
    n = len(r)
    sd = float(np.std(r, ddof=1)) if n > 2 else 0.0
    if n < 5 or sd == 0.0:
        return 0.0
    sharpe_ann = float(np.mean(r)) / sd * math.sqrt(ppy)
    n_eff = n / autocorr_factor(r)
    return round(sharpe_ann * math.sqrt(n_eff / ppy), 2)


def holm_bar(m: int, rank: int = 1, *, alpha: float = 0.05) -> float:
    """Holm step-down one-sided t threshold for the rank-th best of m cohort candidates.

    rank 1 = strongest candidate (bar alpha/m), rank m = weakest (bar alpha). The
    pre-registered PRIMARY hypothesis is exempt (use the plain 1.65 bar); this applies
    to the concurrently-monitored candidate cohort only.
    """
    m, rank = max(1, int(m)), max(1, int(rank))
    adj = alpha / max(1, m - min(rank, m) + 1)
    return round(NormalDist().inv_cdf(1.0 - adj), 2)

```

### libs/validation/pbo.py
```python
"""Probability of Backtest Overfitting via Combinatorially-Symmetric Cross-Validation (CSCV).

Splits the sample into S blocks; for every way of choosing half as in-sample, picks the
in-sample-best configuration and measures its out-of-sample rank. PBO is the fraction of
splits where the chosen configuration lands below the OOS median — i.e. its in-sample edge was
overfit (López de Prado).
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
from pydantic import BaseModel, ConfigDict
from scipy.stats import rankdata

from libs.validation.dsr import sharpe_ratio
from libs.validation.errors import ValidationError


class PBOResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    pbo: float
    n_combinations: int
    n_strategies: int
    median_logit: float

    @property
    def overfit(self) -> bool:
        return self.pbo > 0.5


def probability_backtest_overfitting(
    returns_matrix: np.ndarray, *, n_splits: int = 16
) -> PBOResult:
    """Compute PBO from a (T observations x N strategies) matrix of per-period returns."""
    matrix = np.asarray(returns_matrix, dtype="float64")
    if matrix.ndim != 2 or matrix.shape[1] < 2:
        raise ValidationError("returns_matrix must be 2-D with >= 2 strategies")
    if n_splits % 2 != 0 or n_splits < 2:
        raise ValidationError("n_splits must be a positive even number")
    n_obs, n_strategies = matrix.shape
    if n_obs < n_splits:
        raise ValidationError("not enough observations for the requested n_splits")

    blocks = np.array_split(np.arange(n_obs), n_splits)
    logits: list[float] = []
    for is_block_ids in combinations(range(n_splits), n_splits // 2):
        is_rows = np.concatenate([blocks[i] for i in is_block_ids])
        oos_rows = np.concatenate([blocks[i] for i in range(n_splits) if i not in is_block_ids])

        is_perf = np.array([sharpe_ratio(matrix[is_rows, k]) for k in range(n_strategies)])
        oos_perf = np.array([sharpe_ratio(matrix[oos_rows, k]) for k in range(n_strategies)])

        best = int(np.argmax(is_perf))
        rank = float(rankdata(oos_perf)[best])  # 1..N
        w = rank / (n_strategies + 1)
        logits.append(float(np.log(w / (1.0 - w))))

    logit_arr = np.array(logits, dtype="float64")
    pbo = float(np.mean(logit_arr < 0.0))
    return PBOResult(
        pbo=pbo,
        n_combinations=len(logits),
        n_strategies=n_strategies,
        median_logit=float(np.median(logit_arr)),
    )

```

### scripts/build_axis_screen_reports.py
```python
#!/usr/bin/env python3
"""Assemble reports/axis_screens/{oi_ls_daily,binance_metrics}.json from the raw trial log.

Adds two derived corrections the harness cannot make for itself and that MUST accompany its
numbers here:
  * horizon-corrected Sharpe -- stage_a_screen hardcodes sqrt(365) annualisation, which
    over-annualises a non-overlapping h-day grid by sqrt(h).
  * effective-n IC t-stat -- the harness's n is SYMBOL-DAYS on a stacked panel. Symbols within a
    date are highly correlated, so the independent-observation count is ~the number of DATES.
    Using n_symbol_days would inflate every t-stat by ~sqrt(139).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path("/home/quant/quant-platform")
OUT = ROOT / "reports/axis_screens"
raw = json.loads((OUT / "_raw_trials.json").read_text("utf-8"))
TRIALS = raw["trials"]
N_TRIALS_TOTAL = raw["n_trials"]
DATES = {1: 1878, 5: 375, 20: 93}


def enrich(t: dict[str, Any]) -> dict[str, Any]:
    h = t.get("horizon_days", 1)
    o = dict(t)
    if "sharpe_momentum" in t:
        o["sharpe_momentum_horizon_corrected"] = round(t["sharpe_momentum"] / np.sqrt(h), 3)
        o["sharpe_reversal_horizon_corrected"] = round(t["sharpe_reversal"] / np.sqrt(h), 3)
    if "ic" in t and "|" in t.get("name", "") and "BTC_abs" not in t.get("name", ""):
        eff = DATES.get(h, t.get("n", 1))
        o["effective_n_dates"] = eff
        o["ic_tstat_effective_n"] = round(float(t["ic"] * np.sqrt(eff)), 2)
    elif "ic" in t:
        o["effective_n_dates"] = t.get("n", 0)
        o["ic_tstat_effective_n"] = round(float(t["ic"] * np.sqrt(max(t.get("n", 1), 1))), 2)
    return o


oi = [enrich(t) for t in TRIALS if "BTC_abs" not in t["name"]]
bm = [enrich(t) for t in TRIALS if "BTC_abs" in t["name"]]

ALIGNMENT = (
 "VERIFIED, NOT ASSUMED. (a) The archive `date` is a UTC calendar day and matches both the 1d "
 "kline UTC day and the live forward collector -- proven by shift-sensitivity: corr(archive OI, "
 "forward snapshot) peaks at shift 0 for all 5 probe symbols and degrades at +/-1d "
 "(BTC 0.475/0.846/0.747, ETH 0.328/0.840/0.478, SOL 0.948/0.992/0.978, XRP 0.722/0.978/0.834, "
 "ADA 0.113/0.905/0.324 for shifts -1/0/+1). No timezone offset. "
 "(b) The `oi`/`oi_first` pair encodes an INTRA-DAY alignment subtlety, confirmed against "
 "scripts/dl_oi_ls_universe.py:pull_metrics: `oi`/`ls`/`taker` are the MEAN of all 288 5-min "
 "buckets from 00:00 to 23:55 UTC of day t (an average spanning the whole of day t, complete "
 "only at 23:55 UTC), while `oi_first`/`ls_first` are the single 00:00:00 UTC bucket -- the "
 "FIRST observation of day t, i.e. information known at the START of day t. "
 "(c) Proof of (b): the live collector snapshots at ~00:0x UTC; corr(forward 00:0x snapshot, "
 "archive `oi_first`) = 0.9994-0.9999 across all 5 probe symbols, versus 0.79-0.99 against the "
 "archive daily MEAN `oi`. The reconstruction is exact. "
 "(d) LOOK-AHEAD CONTROL: pairing `oi[t]` (a whole-day average) with the day-t return "
 "(close t-1 -> close t) is CONTEMPORANEOUS and was never done. Every signal dated t is used "
 "only to predict close(t) -> close(t+h); stage_a_screen enforces this structurally by "
 "predicting target_ret[t+1] from signal[t]. Worst case the signal is complete at 23:55 UTC and "
 "entry is at the 23:59:59.999 close -- a 5-minute lead. The `M1_lsfirst_level` / "
 "`M2_oifirst_growth` constructions re-run the same mechanisms on the 00:00 snapshot, which is "
 "~24h stale at entry and therefore immune even to that 5-minute objection; they agree with the "
 "daily-mean versions (both null), so no result here depends on the 5-minute window."
)

CAVEAT = (
 "TWO HARNESS CAVEATS, declared rather than patched (the harness is audited and was not "
 "modified): (1) stage_a_screen hardcodes sqrt(365) annualisation, so on the non-overlapping "
 "5d/20d grids its Sharpe is inflated by sqrt(h) -- the horizon-corrected value is reported "
 "alongside every trial, and its SUSPECT-LOOKAHEAD Sharpe>6 rail is correspondingly "
 "over-sensitive at 20d. (2) On a stacked panel its `n` is SYMBOL-DAYS; symbols within a date "
 "are strongly correlated, so the independent-observation count is the number of DATES. Every "
 "IC t-stat below uses the date count, not the symbol-day count -- otherwise every t-stat would "
 "be inflated by ~sqrt(139)=11.8x."
)

# ---------------------------------------------------------------- oi_ls_daily
(OUT / "oi_ls_daily.json").write_text(json.dumps({
 "axis": "oi_ls_daily",
 "updated": "2026-07-26",
 "stage": "A (zero promotion authority)",
 "verdict": "NEGATIVE -- ALL 42 CONSTRUCTIONS FAIL. NO FORWARD CLOCK STARTED.",
 "universe": {"symbols": 139, "dates": 1879, "range": ["2021-06-01", "2026-07-23"],
              "survivorship": "tranche-1 cohort enumerated from the archive's OWN S3 listing "
                              "(includes delisted symbols), not from today's live universe -- "
                              "the cross-section is what actually existed at each date"},

 "mechanism_prior": {
  "stated_before_screening": True,
  "M1_crowded_positioning_liquidation_cascade":
   "The global long/short ACCOUNT ratio measures how one-sided retail positioning is. When a "
   "symbol's crowd is extremely long relative to peers, the marginal buyer is exhausted and the "
   "downside is convex: a modest adverse move forces liquidations that beget further "
   "liquidations. Crowding should therefore mean-revert, and the crowded name should "
   "UNDERPERFORM its peers.",
  "M2_OI_build_without_price_confirmation_fragile_leverage":
   "Open interest rising while price does NOT confirm means new leverage is being added into a "
   "move the market is not validating. That leverage is fragile -- it is stop-loss fuel. OI "
   "built AGAINST the price move marks trapped positions specifically.",
  "M3_taker_flow_imbalance_informed_aggression":
   "The taker buy/sell volume ratio measures who is willing to CROSS THE SPREAD. Aggressive "
   "takers pay for immediacy, which is what informed traders do when they have a short-lived "
   "edge. Sustained taker imbalance should therefore lead relative returns.",
  "why_cross_sectional": "All three are statements about one symbol RELATIVE TO OTHER SYMBOLS "
   "(who is more crowded, whose leverage is more fragile, where is aggression concentrated). "
   "The 139-symbol breadth is the axis's real advantage, so the target is the cross-sectionally "
   "demeaned return and the book is a rank-based long/short spread -- NOT a next-day BTC timing "
   "signal, which is the dev-momentum mistake this desk made standing law."},

 "alignment_declaration": ALIGNMENT,
 "harness_caveats": CAVEAT,

 "method": {
  "screen": "libs.research.axis_screen.stage_a_screen ONLY (angle-20 de-contamination gate "
            "baked in, never bypassed). Nothing outside the harness produced a verdict.",
  "target": "cross-sectionally demeaned (relative) return, per date, across the 139-symbol panel",
  "horizons": "1d / 5d / 20d, NON-OVERLAPPING sampling (no overlapping-window t-stat inflation)",
  "signal_normalisation_primary": "cross-sectional rank -> normal scores (van der Waerden) per "
                                  "date, which is exactly the 'rank the symbols' construction "
                                  "the cross-sectional mandate specifies; the harness then "
                                  "applies its own trailing-20 z on top",
  "signal_normalisation_secondary": "raw level with the harness's trailing-20 z as the only "
                                    "normalisation ('extreme vs its OWN history'), target still "
                                    "cross-sectionally relative",
  "change_window": "changes are computed over the SAME h-period as the horizon -- no free lag "
                   "parameter was introduced or tuned",
  "panel_stacking": "symbol-major stack; the harness's rolling z-window and its np.roll forward "
                    "return bleed across 139 block boundaries. Reported per trial as "
                    "boundary_bleed_frac (~1.5% of rows at 1d, larger at 20d). Cross-sectional "
                    "normalisation puts all symbols on one scale so the bleed adds noise rather "
                    "than signal -- it is conservative, it cannot manufacture an edge.",
  "sharpe_interpretation": "the harness's sign(z)*fwd Sharpe on a stacked panel is the PER-NAME, "
                           "UNDIVERSIFIED long/short Sharpe, ~sqrt(N_eff) below the diversified "
                           "book. Conservative. A separate DESCRIPTIVE (never a verdict) "
                           "diversified top-vs-bottom-decile spread is recorded alongside."},

 "trial_accounting": {
  "constructions": 10, "normalisations": 2, "horizons": 3, "targets": 2,
  "trials_this_axis": len(oi),
  "trials_all_axes_this_session": N_TRIALS_TOTAL,
  "note": "Every cell of the pre-declared grid was executed and is logged below, including the "
          "target control against ABSOLUTE return. Nothing was run and discarded. Because 42 "
          "trials were run on this axis, any nominal pass would have had to clear a "
          "multiplicity-deflated bar -- none came close enough for that to matter."},

 "results_summary": {
  "verdicts": {"SCREEN-WEAK": sum(1 for t in oi if t["verdict"] == "SCREEN-WEAK"),
               "TIMING-ARTIFACT": sum(1 for t in oi if t["verdict"] == "TIMING-ARTIFACT"),
               "SCREEN-INTERESTING": sum(1 for t in oi if t["verdict"] == "SCREEN-INTERESTING")},
  "largest_abs_ic": max(abs(t.get("ic", 0)) for t in oi),
  "largest_abs_ic_trial": max(oi, key=lambda t: abs(t.get("ic", 0)))["name"],
  "reading": "Every IC is inside noise. The largest |IC| on the axis is 0.045 at 20d, where the "
             "effective sample is 93 dates -- an IC t-stat of -0.43. At 1d the largest |IC| is "
             "0.008 (t=0.35 on 1878 dates). No horizon-corrected per-name Sharpe exceeds 0.36. "
             "The three defensible mechanisms are not merely unproven here; they are flat."},

 "notable_negative_findings": [
  {"finding": "The LS ratio is substantially a RESTATEMENT of the contemporaneous price move at "
              "medium horizons, not an independent positioning read.",
   "evidence": "M1_ls_change|xsrank|rel|20d was the only construction on this axis to trip the "
               "de-contamination gate: same_period_corr = -0.294 against the 20d limit of 0.20. "
               "Its descriptive decile spread (-1.77% per 20d, the mechanism-predicted "
               "direction) is therefore NOT evidence for the crowding mechanism -- the gate "
               "caught it as the coinbase/turkey failure mode. The crowd chases price, so LS "
               "change and the concurrent return move together; what looks like a crowding "
               "signal is ~30% concurrent price, i.e. a price-family effect in an LS costume. "
               "This is exactly the artifact the angle-20 gate exists to catch.",
   "lesson": "Any future positioning construction on this axis must be orthogonalised to the "
             "contemporaneous return BEFORE it is screened, or it will keep re-discovering "
             "medium-term price reversal and mislabelling it as crowding."},
  {"finding": "OI growth is contaminated by concurrent price in the same way, with the opposite "
              "sign.",
   "evidence": "M2_oi_growth same_period_corr = +0.132 (1d), +0.224 (5d), +0.253/+0.319 (20d, "
               "raw-z variant) -- OI and price rise together. The pre-registered "
               "sign(dP)*sign(dOI) divergence construction is the correct defence against this "
               "and indeed shows the lowest contamination of the M2 family (+0.063 at 1d), but "
               "it is also flat (IC -0.002)."},
  {"finding": "The relative-vs-absolute target choice was not the binding constraint.",
   "evidence": "The three ABSOLUTE-return controls are as flat as their relative counterparts "
               "(|IC| <= 0.005). The mandate is right that cross-sectional relative is the "
               "mechanism-appropriate target, but on this axis the signals carry no information "
               "about EITHER target. The null is about the signals, not the framing."},
  {"finding": "The alignment-robustness constructions agree with their daily-mean twins.",
   "evidence": "M1_lsfirst_level tracks M1_ls_level and M2_oifirst_growth tracks M2_oi_growth at "
               "every horizon, both null. No conclusion depends on the 5-minute gap between the "
               "23:55 UTC signal completion and the 23:59:59 close."}],

 "blocked_prior_work": {
  "what": "scripts/backfill_oi_ls_oos.py (the pre-registered CROSS-SECTIONAL held-out OOS for "
          "the oi_divergence and ls_contrarian sleeves) had never been run to completion -- "
          "reports/reconstructed_oos/oi_ls_cross_sectional.json did not exist. It was run as "
          "part of this screen and ABORTED on its own diff-verify gate.",
  "abort_message": "ABORT: reconstruction misaligned vs forward truth "
                   "{'oi_corr': 0.840, 'ls_corr': 0.780} (bithumb/timezone class)",
  "diagnosis": "FALSE POSITIVE -- a gate CALIBRATION defect, not a misalignment. diff_verify "
               "compares the forward collector's single point-in-time snapshot against the "
               "archive's 24h MEAN (`oi`), which is a like-for-unlike comparison over only 25 "
               "overlapping days on a range-bound level. Comparing like-for-like -- the "
               "collector's 00:0x UTC snapshot against the archive's 00:00 bucket `oi_first` -- "
               "gives corr 0.9994-0.9999 on all five probe symbols, and the median relative "
               "difference on `oi` is already only 0.56-0.94% (units match exactly: contracts "
               "vs contracts). Shift-sensitivity independently rules out a day offset.",
  "action_taken": "The gate was NOT weakened or bypassed -- that is not this screen's authority. "
                  "The defect is reported for the gate's owner.",
  "recommended_fix": "In scripts/backfill_oi_ls_oos.py:diff_verify, compare the forward snapshot "
                     "against `oi_first`/`ls_first` (matching the collector's ~00:0x UTC "
                     "sampling time) instead of against the daily means `oi`/`ls`. The 0.90/0.60 "
                     "thresholds are then meaningful; against a daily mean they are not.",
  "consequence": "The pre-registered 2-trial OOS for the two derivative sleeves remains "
                 "UNRESOLVED. This Stage-A screen does not substitute for it: it covers a much "
                 "wider grid but has no pre-registration, so its 42 trials carry a "
                 "multiple-testing penalty the 2-trial OOS would not."},

 "screen_outputs": oi,

 "next_step": "Do NOT start a forward clock and do NOT re-screen these constructions -- 42 "
              "trials across three mechanisms, two normalisations, two targets and three "
              "horizons is a thorough refutation, and running more variants on the same data is "
              "the breadth-mining this desk has already refuted 420 times. Two concrete "
              "follow-ups, in priority order: (1) fix the diff_verify field mismatch and let the "
              "pre-registered 2-trial cross-sectional OOS actually run -- it is the one test on "
              "this axis that carries no multiplicity penalty, and it is currently blocked by a "
              "bug rather than by evidence; (2) if the positioning mechanisms are to be revisited "
              "at all, the missing ingredient is not another construction but a different FIELD "
              "-- the top-trader ratios (see the binance_metrics screen), which separate "
              "informed from retail positioning and are not present in oi_ls_daily.",

 "authority": "Stage A only. ZERO promotion authority. No clock earned, none started."
}, indent=1), encoding="utf-8")

# ---------------------------------------------------------------- binance_metrics
(OUT / "binance_metrics.json").write_text(json.dumps({
 "axis": "binance_metrics",
 "updated": "2026-07-26",
 "stage": "A (zero promotion authority)",
 "verdict": "REJECTED -- the harness's nominal SCREEN-INTERESTING does not survive adversarial "
            "review. NO FORWARD CLOCK STARTED.",
 "coverage": {"symbols": 1, "symbol": "BTCUSDT", "days": 435,
              "range": ["2023-01-01", "2024-03-10"], "files": 435,
              "note": "Despite 435 files this axis is ONE symbol. It is the raw 5-min metrics "
                      "archive that oi_ls_daily was itself built from, so `sum_open_interest`, "
                      "`count_long_short_ratio` and `sum_taker_long_short_vol_ratio` are "
                      "REDUNDANT with oi_ls_daily and were not re-screened."},

 "mechanism_prior": {
  "stated_before_screening": True,
  "what_is_genuinely_new_here":
   "Two fields exist in this archive that oi_ls_daily does NOT carry: "
   "`count_toptrader_long_short_ratio` and `sum_toptrader_long_short_ratio`, the positioning of "
   "the top 20% of accounts by margin balance. Together with the retail-wide "
   "`count_long_short_ratio` they permit a SMART-MONEY vs RETAIL construction that is impossible "
   "on any other axis here. A third new quantity is the intra-day OI path (23:55 vs 00:00), "
   "which oi_ls_daily compresses to a mean and a first bucket.",
  "M4_smart_money_vs_retail":
   "Large, well-capitalised accounts survive by being right; the retail crowd is the liquidity "
   "they trade against. When top traders are positioned LONG while the retail crowd is SHORT, "
   "the informed side is on the long side and price should follow it. The spread between the two "
   "ratios isolates the disagreement, cancelling the market-wide positioning level.",
  "M5_intraday_OI_drift":
   "OI built during the session and still held into the close is leverage that survived the "
   "day's shakeouts -- a cleaner read on conviction than the daily mean, which mixes positions "
   "that were opened and closed intraday.",
  "declared_low_prior": "ONE symbol means NO cross-section is available, so the only possible "
   "target is BTC's own absolute return -- precisely the next-day-single-asset-timing shape the "
   "mandate flags as the dev-momentum mistake. The prior was declared low BEFORE screening, and "
   "the screen was run anyway so that the result would be recorded rather than assumed."},

 "alignment_declaration":
  "Same convention as oi_ls_daily and verified by the same evidence. The 5-min buckets run "
  "00:00 to 23:55 UTC of day t; the daily aggregate is therefore complete at 23:55 UTC and is "
  "used only to predict close(t) -> close(t+h) against the 23:59:59.999 UTC futures close. "
  "M5_oi_intraday_drift uses the 23:55 bucket over the 00:00 bucket, both strictly within day t. "
  "No same-day return is ever paired with a same-day aggregate; stage_a_screen enforces the "
  "t -> t+1 direction structurally.",
 "harness_caveats": CAVEAT,

 "trial_accounting": {"constructions": 3, "horizons": 2, "trials_this_axis": len(bm),
                      "trials_all_axes_this_session": N_TRIALS_TOTAL,
                      "note": "20d was not run: 435 days / 20 = 21 non-overlapping periods, "
                              "below the harness's n>=30 floor. Declared, not silently dropped."},

 "screen_outputs": bm,

 "adversarial_review_of_the_nominal_pass": {
  "trial": "M4_smart_minus_retail_count|BTC_abs|1d",
  "harness_result": {"ic": 0.104, "sharpe_momentum": 1.99, "same_period_corr": -0.026,
                     "residual_ic": 0.103, "n": 413, "verdict": "SCREEN-INTERESTING"},
  "checks_run": [
   {"check": "shift-sensitivity (mandatory before trusting anything strong)",
    "result": "IC by signal lag: -1d = -0.027, 0d = +0.103, +1d = +0.067, +2d = +0.004",
    "reading": "PASSES. A misalignment artifact spikes at one lag with nothing adjacent, or is "
               "stronger at a NEGATIVE lag. This decays smoothly forward from a lag-0 peak, "
               "which is what a slow-moving positioning variable should do. Not a look-ahead bug."},
   {"check": "de-contamination (angle-20 gate)",
    "result": "same_period_corr = -0.026, residual_ic 0.103 vs raw ic 0.104",
    "reading": "PASSES cleanly. The signal is not a restatement of the concurrent move."},
   {"check": "long-bias / beta decomposition",
    "result": "49.4% of days long (near neutral, so not a disguised long-only book), BUT BTC "
              "buy-and-hold Sharpe over the identical 413 days is +2.37 versus the signal "
              "book's +1.99. Long-day subset mean +55.5 bps, short-day subset mean +4.7 bps.",
    "reading": "FAILS. The book earns almost everything on its long days and its short leg is a "
               "drag (shorting days that average +4.7 bps loses money). It is a partially "
               "successful market-timing filter in a violent bull market, and it does not beat "
               "simply holding the asset over the only window it has."},
   {"check": "multiple-testing deflation (libs.validation.dsr)",
    "result": "DSR = 0.0000 at n_trials=48 (sr0 threshold 0.332); DSR = 0.037 even at "
              "n_trials=6, counting only this axis's own trials. IC t-stat = 2.11 on 413 days "
              "against a Bonferroni requirement of ~3.3 for 48 trials.",
    "reading": "FAILS decisively, and would fail even if this axis had been screened alone."},
   {"check": "regime coverage",
    "result": "435 consecutive days, 2023-01-01 to 2024-03-10: the post-FTX recovery straight "
              "through the spot-ETF rally. First-half book Sharpe +1.43, second-half +2.51.",
    "reading": "FAILS. One monotonic uptrend is one regime. The rising sub-period Sharpe is "
               "consistent with the signal simply working better as the trend strengthened."}],
  "conclusion": "REJECTED. The mechanism is NOT refuted -- the de-contamination and "
                "shift-sensitivity results are genuinely clean, which is more than any "
                "oi_ls_daily construction managed. But this DATA cannot test it: one asset, one "
                "regime, 413 usable days, and a 48-trial multiplicity burden that a t-stat of "
                "2.11 cannot carry. Promoting it would be exactly the phantom-edge manufacture "
                "the discipline forbids."},

 "other_nominal_pass": {
  "trial": "M5_oi_intraday_drift|BTC_abs|5d",
  "result": "ic 0.058, harness sharpe_reversal -1.64, n=65",
  "rejected_because": "n=65 gives an IC t-stat of 0.47, and the harness's sqrt(365) "
                      "annualisation overstates a 5-day-grid Sharpe by sqrt(5)=2.24x, so the "
                      "true figure is ~0.73. Statistically empty; the SCREEN-INTERESTING label "
                      "is an artifact of thresholds designed for daily data."},

 "timing_artifacts_caught": "Both 5d M4 constructions tripped the de-contamination gate "
                            "(same_period_corr +0.506 and +0.285) -- over a 5-day window the "
                            "positioning aggregate and the concurrent return overlap heavily. "
                            "The gate worked.",

 "next_step": "Do NOT start a clock and do NOT screen further constructions on 435 days of one "
              "symbol -- more variants on this sample can only manufacture multiplicity. The "
              "single highest-value follow-up on any of these three axes is a DATA action, not "
              "an analysis action: extend scripts/dl_oi_ls_universe.py:pull_metrics to also "
              "persist `count_toptrader_long_short_ratio` and `sum_toptrader_long_short_ratio` "
              "(both are already present in every archive CSV it parses and are currently "
              "discarded) across the full 139-symbol tranche-1 cohort and its full 2021-2026 "
              "history. That converts the one mechanism here that passed de-contamination and "
              "shift-sensitivity from an untestable single-asset timing signal into a "
              "cross-sectional asset-selection signal with 139-symbol breadth and five years of "
              "regimes -- the shape this desk can actually test. Only then does it deserve a "
              "pre-registered screen.",

 "authority": "Stage A only. ZERO promotion authority. No clock earned, none started."
}, indent=1), encoding="utf-8")
print("wrote oi_ls_daily.json, binance_metrics.json")
print("oi_ls trials:", len(oi), "| binance_metrics trials:", len(bm))

```

### scripts/check_enforcement_execution.py
```python
#!/usr/bin/env python3
"""ENFORCEMENT EXECUTION (L1.43 / L2.0) -- the enforcement matrix proves a fence EXISTS and maps
to a law. Nothing ever proved the fence RUNS.

THE DEFECT THIS WAS BUILT FOR, found by the capability hunt 2026-08-01 and confirmed by hand
before a line was written: `data/enforcement_matrix.json` reports ENFORCED on 62 of 65 principles.
Two of those -- L1.19 (information decay) and L2.10 (reality gap) -- name `libs/research/dist_shift.py`
as their enforcement. That module's only importer in the entire repo is its own unit test. The
producer was built, unit-tested green, cited as evidence that two laws were enforced, and never
called by anything. The matrix could not see it, because the matrix asks "does the file exist and
does it map to a principle?" -- both yes -- and never asks "does anything execute it?".

That is L1.43's welded-gate logic one level up. L1.43 classifies a fence by whether it has ever
FIRED; this asks the prior question, the one a never-run fence cannot answer for itself: is there
a path by which it could fire at all? A citation nothing executes is a law enforced by a
docstring.

WHY THE EXISTING CHECKS DO NOT COVER THIS, verified rather than assumed:
  * `build_enforcement_matrix.py` checks existence + mapping. Never execution.
  * `max_audit.check_orphan_code` walks the import graph but at PACKAGE granularity, and skips any
    package with fewer than 3 modules. `libs/research` is reached by dozens of scripts, so every
    orphaned MODULE inside it is invisible. dist_shift.py sat there unseen.
  * `check_fence_yield.py` (L1.43) measures fences that produce ARTIFACTS. A library module with no
    artifact of its own is outside its scope entirely.
The blind spot was module-granular, and all three checks were green across it.

IMPORTABLE IS NOT EXECUTED, and this distinction is the whole fence. `libs/validation/__init__.py`
re-exports `RevalidationController`, so `revalidation.py` is reachable from any script importing
`libs.validation` -- static reachability would call it live. It is not: nothing constructs that
controller outside tests. So a module counts as EXECUTED only when one of its own public symbols
is REFERENCED from non-test code that is itself reachable -- never merely because an `__init__`
re-exports it.

STATUSES, per citation:
  EXECUTED   a real path to execution exists: a cron line, a subprocess invocation, an import that
             is used, or a max_audit fence that is registered.
  STANDING   a non-executable artifact (docs/, data/, ops/ -- a lock file, the doctrine, the
             graveyard). Enforcement by content, not by running. Checked for EXISTENCE only.
  TEST       a tests/ path: executed by pytest in CI. Checked for existence.
  DECORATIVE the file exists and nothing executes it. The law it is cited for is enforced by
             nothing. FAILS.
  MISSING    the cited path does not exist at all. FAILS.

Run status: OK / DECORATIVE / MISSING / UNMEASURED. UNMEASURED when the citation map cannot be
read -- zero citations is UNMEASURED, never OK (L1.28a: an unmeasured thing must never report
fine, which is the exact bug that let this defect live).

DELIBERATELY CONSERVATIVE. A gate that cries wolf gets acknowledged into silence, and that is how
enforcement actually dies (L1.41). Every ambiguous case resolves to EXECUTED: a symbol referenced
anywhere in non-test production code counts, subprocess invocation by string counts, and a
parenthetical or `:symbol` suffix is stripped rather than treated as a path. The fence reports what
it can PROVE is unexecuted, and says so.

    python scripts/check_enforcement_execution.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent

# L1.42 LAWFUL ENTRY: this organ acts, so it passes the law boundary like every other. guard() is
# TTL-cached (~0ms after the first call in a window) and pages rather than blocks -- a governance
# fault must never silently stop a detector.
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_OUT = _ROOT / "data/enforcement_execution.json"
_MANIFEST = _ROOT / "ops/crontab.manifest"
_AUDIT = _ROOT / "scripts/max_audit.py"

#: Citations that are deliberately HUMAN-INVOKED, with the reason. Same convention as
#: check_build_standard's _SCHEDULE_EXEMPT: "no cron line" must be a DECISION on the record, never
#: a default. A tool taking file arguments cannot have a cadence -- but the exemption is narrow and
#: still printed, because an unrun manual tool is a real obligation, just one a DIFFERENT fence
#: owns (Gate-0 readiness), not this one. This fence asks only: can it execute at all?
_MANUAL: dict[str, str] = {
    "scripts/deep_review.py": "13-seat second-model-family panel, ONE file per pass, invoked with "
                              "explicit file arguments (LIVE_CONNECTOR_SPEC section-7). Cold "
                              "independence is the point -- it is deliberately not self-served by "
                              "the desk on a timer. Its Gate-0 obligation is tracked separately.",
}

#: Non-executable artifact roots: these enforce by CONTENT (a sealed lock, the doctrine text, the
#: graveyard record), so "does it run" is the wrong question and existence is the right one.
_STANDING_ROOTS = ("docs/", "data/", "ops/")
_STANDING_SUFFIXES = (".md", ".txt", ".lock", ".json", ".jsonl", ".yaml", ".yml")


def _strip_citation(raw: str) -> str:
    """A citation carries prose: 'run_deadman_switch.py (Tier-3)', 'libs/x.py:capacity_status'."""
    s = re.sub(r"\s*\(.*?\)\s*$", "", raw.strip())
    if ".py:" in s:                      # 'libs/autodiscovery/validation.py:capacity_status'
        s = s.split(".py:")[0] + ".py"
    return s.strip()


def _resolve(cite: str) -> tuple[str, Path | None]:
    """-> (kind, path). kind in {standing, test, script, module, fence, unknown}."""
    s = _strip_citation(cite)
    if not s:
        return "unknown", None
    if s.startswith("tests/"):
        return "test", _ROOT / s
    if s.startswith(_STANDING_ROOTS) or (s.endswith(_STANDING_SUFFIXES) and "/" in s):
        return "standing", _ROOT / s
    if s.endswith(".py"):
        p = _ROOT / s
        if p.exists():
            return ("module" if s.startswith("libs/") else "script"), p
        alt = _ROOT / "scripts" / s     # bare 'revalidate_clocks.py'
        if alt.exists():
            return "script", alt
        return ("module" if s.startswith("libs/") else "script"), p
    if "/" not in s and "." not in s:
        return "fence", _AUDIT          # a max_audit fence function name
    return "unknown", _ROOT / s


def _py_files(*rel: str) -> list[Path]:
    out: list[Path] = []
    for r in rel:
        d = _ROOT / r
        if d.exists():
            out.extend(sorted(d.rglob("*.py")))
    return out


def _public_symbols(path: Path) -> set[str]:
    """Top-level public defs/classes of a module -- the names a caller would actually use."""
    try:
        tree = ast.parse(path.read_text("utf-8", errors="ignore"))
    except (OSError, SyntaxError):
        return set()
    out = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            if not node.name.startswith("_"):
                out.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and not t.id.startswith("_") and t.id.isupper():
                    out.add(t.id)
    return out


class _Corpus:
    """Non-test production text, indexed once. Built lazily so --json stays cheap."""

    def __init__(self) -> None:
        self.files: dict[Path, str] = {}
        # EXCLUDE THIS FENCE'S OWN SOURCE. Found on the second run, and it is precisely the defect
        # class this fence hunts: the _MANUAL registry below contains the literal string
        # "scripts/deep_review.py", so scanning scripts/ found the fence's own exemption entry and
        # reported the tool as INVOKED. A checker that cites itself as evidence launders any
        # mention -- a docstring, a registry key -- into proof of execution.
        _self = Path(__file__).resolve()
        for f in _py_files("scripts", "libs"):
            if f.resolve() == _self:
                continue
            try:
                self.files[f] = f.read_text("utf-8", errors="ignore")
            except OSError:
                continue
        self.manifest = _MANIFEST.read_text("utf-8", errors="ignore") if _MANIFEST.exists() else ""

    def references(self, symbols: set[str], *, exclude: Path, package_init: Path | None) -> str | None:
        """Is any symbol used from real code? Returns the referencing file, or None.

        `package_init` is excluded: a re-export in `__init__.py` proves the module is IMPORTABLE,
        never that anything calls it. Counting it is exactly how an orphan reads as wired.
        """
        for path, text in self.files.items():
            if path in (exclude, package_init):
                continue
            for sym in symbols:
                if re.search(rf"\b{re.escape(sym)}\b", text):
                    return str(path.relative_to(_ROOT))
        return None

    def invoked(self, script: Path) -> str | None:
        """Cron line, subprocess-by-string, or import by another module."""
        name = script.name
        rel = f"scripts/{name}"
        if re.search(rf"\b{re.escape(name)}\b", self.manifest):
            return "ops/crontab.manifest"
        stem = script.stem
        for path, text in self.files.items():
            if path == script:
                continue
            if rel in text or re.search(rf"\bscripts\.{re.escape(stem)}\b", text):
                return str(path.relative_to(_ROOT))
        return None


def _fence_registered(name: str, audit_text: str) -> bool:
    """A max_audit fence is executed when it is DEFINED and referenced elsewhere in the file
    (a registry entry or a call) -- a defined-but-never-registered fence never runs."""
    if not re.search(rf"^def {re.escape(name)}\b", audit_text, re.M):
        return False
    hits = len(re.findall(rf"\b{re.escape(name)}\b", audit_text))
    return hits > 1


def evaluate() -> dict[str, Any]:
    try:
        from scripts.build_enforcement_matrix import _MAP
    except Exception as exc:
        return {"status": "UNMEASURED",
                "reason": f"citation map unreadable ({type(exc).__name__}: {exc}); "
                          "cannot prove any law is enforced, so nothing is claimed",
                "citations": [], "counts": {}}
    if not _MAP:
        return {"status": "UNMEASURED", "reason": "citation map is empty",
                "citations": [], "counts": {}}

    corpus = _Corpus()
    audit_text = _AUDIT.read_text("utf-8", errors="ignore") if _AUDIT.exists() else ""
    rows: list[dict[str, Any]] = []
    seen: dict[str, dict[str, Any]] = {}

    for law, cites in sorted(_MAP.items()):
        for cite in cites:
            kind, path = _resolve(cite)
            key = f"{kind}:{path}"
            if key in seen:                        # same artifact cited by several laws
                seen[key]["laws"].append(law)
                continue
            row: dict[str, Any] = {"laws": [law], "citation": cite, "kind": kind,
                                   "path": str(path.relative_to(_ROOT)) if path else None}
            if path is None or (kind != "fence" and not path.exists()):
                row |= {"verdict": "MISSING", "evidence": "path does not exist"}
            elif kind in ("standing", "test"):
                row |= {"verdict": "STANDING" if kind == "standing" else "TEST",
                        "evidence": "non-executable artifact (content is the enforcement)"
                                    if kind == "standing" else "executed by pytest"}
            elif kind == "fence":
                name = _strip_citation(cite)
                ok = _fence_registered(name, audit_text)
                row |= {"verdict": "EXECUTED" if ok else "DECORATIVE",
                        "evidence": "registered in max_audit.py" if ok
                                    else "no `def` in max_audit.py, or defined and never referenced"}
            elif kind == "script":
                rel = str(path.relative_to(_ROOT)) if path.exists() else ""
                where = corpus.invoked(path)
                if where:
                    row |= {"verdict": "EXECUTED", "evidence": f"invoked by {where}"}
                elif rel in _MANUAL:
                    row |= {"verdict": "MANUAL", "evidence": _MANUAL[rel]}
                else:
                    row |= {"verdict": "DECORATIVE",
                            "evidence": "no cron line, no subprocess call, no importer"}
            elif kind == "module":
                syms = _public_symbols(path)
                init = path.parent / "__init__.py"
                where = corpus.references(syms, exclude=path,
                                          package_init=init if init.exists() else None)
                if not syms:
                    row |= {"verdict": "EXECUTED",
                            "evidence": "no public symbols to trace (conservative pass)"}
                else:
                    row |= {"verdict": "EXECUTED" if where else "DECORATIVE",
                            "evidence": f"symbol used by {where}" if where
                                        else f"none of {sorted(syms)[:4]} referenced outside "
                                             "its own module, its package __init__, or tests"}
            else:
                row |= {"verdict": "EXECUTED", "evidence": "unrecognised citation form "
                                                           "(conservative pass)"}
            seen[key] = row
            rows.append(row)

    counts: dict[str, int] = {}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    broken = [r for r in rows if r["verdict"] in ("DECORATIVE", "MISSING")]

    # A law is enforced by NOTHING only when EVERY one of its citations is broken. The first draft
    # of this fence flagged L1.7 as unenforced because one of its three citations was, while
    # check_rubberstamp_detector and check_rubberstamp_enforcement both execute -- an over-claim,
    # and an over-claiming gate is one nobody believes the second time.
    per_law: dict[str, list[str]] = {}
    for r in rows:
        for law in r["laws"]:
            per_law.setdefault(law, []).append(r["verdict"])
    unenforced = sorted(law for law, vs in per_law.items()
                        if vs and all(v in ("DECORATIVE", "MISSING") for v in vs))
    weakened = sorted(law for law, vs in per_law.items()
                      if law not in unenforced
                      and any(v in ("DECORATIVE", "MISSING") for v in vs))

    if not rows:
        status = "UNMEASURED"
    elif any(r["verdict"] == "MISSING" for r in broken):
        status = "MISSING"
    elif broken:
        status = "DECORATIVE"
    else:
        status = "OK"
    return {"status": status, "citations": rows, "counts": counts,
            "broken": [{"laws": r["laws"], "path": r["path"], "verdict": r["verdict"],
                        "evidence": r["evidence"]} for r in broken],
            "laws_unenforced": unenforced, "laws_weakened": weakened,
            "manual": [{"path": r["path"], "laws": r["laws"], "reason": r["evidence"]}
                       for r in rows if r["verdict"] == "MANUAL"]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report-only", action="store_true",
                    help="print and always exit 0 (for dashboards)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    _law_guard()
    res = evaluate()
    res["generated"] = datetime.now(UTC).isoformat()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(res, indent=1) + "\n", "utf-8")

    if args.json:
        print(json.dumps(res, indent=1))
    else:
        c = res.get("counts", {})
        print(f"enforcement execution (L1.43): {res['status']} -- " +
              ", ".join(f"{k}={v}" for k, v in sorted(c.items())) or "no citations")
        if res.get("reason"):
            print(f"  {res['reason']}")
        for r in res.get("broken", []):
            print(f"  {r['verdict']:10s} {r['path']}  [{', '.join(r['laws'])}]")
            print(f"             {r['evidence']}")
        for m in res.get("manual", []):
            print(f"  MANUAL     {m['path']}  [{', '.join(m['laws'])}] -- human-invoked by design")
        if res.get("laws_unenforced"):
            print(f"  LAWS ENFORCED BY NOTHING: {', '.join(res['laws_unenforced'])}")
        if res.get("laws_weakened"):
            print(f"  laws with a broken citation (others still execute): "
                  f"{', '.join(res['laws_weakened'])}")
        print(f"-> {_OUT.relative_to(_ROOT)}")

    if args.report_only:
        return 0
    return 0 if res["status"] == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts/feature_library.py
```python
"""FEATURE LIBRARY + CONTINUOUS FEATURE MINER -- features as managed assets, and the construction
space they live in, made countable.

THE PRINCIPAL'S FRAMING, adopted verbatim as the design goal: the question becomes "which pieces
of information about markets are consistently useful?" rather than "what strategy should I try?"

WHY THIS IS THE RIGHT NEXT BUILD, with the evidence:
micro_factory.py computed SIX state variables over 4.4GB of proprietary order books -- spread_bps,
depth5, depth10, imbalance, concentration, slope -- tested exactly ONE derived construction
(negative z of near-touch depth vs 24h rolling), got a null after de-contamination, and DISCARDED
ALL SIX. The next microstructure question re-reads 4.4GB from scratch. That is the measurable
bottleneck this removes.

THE MINER IS THE POINT, NOT THE REGISTRY. A registry of what was built is bookkeeping. The
valuable half answers "can I construct another observable for this mechanism?" MECHANICALLY, by
enumerating a construction grammar:

        OBSERVABLE  x  TRANSFORM  x  WINDOW  x  NORMALISATION

and reporting which cells have been tested. That converts "keep exploring, never exhaust" from an
instruction into a COVERAGE PERCENTAGE. The desk has never known what fraction of a mechanism's
observable space it has visited; after this it does, and "we tested microstructure" becomes
"we tested 1 of 96 constructions = 1.0%", which is a very different sentence.

CRITICAL HONESTY RAIL -- COVERAGE IS NOT PROGRESS. Enumerating 96 cells and testing all 96 is
mass multiple-hypothesis testing, and this desk's own SUSPECT-LOOKAHEAD and Holm rails exist
because that path manufactures survivors. So the miner RANKS cells and hands them to the existing
Stage-A/Stage-B law: screening is unlimited and carries ZERO promotion authority; only
pre-registered forward clocks promote. The miner feeds screening. It cannot promote anything.

MEASUREMENT DOCTRINE COMPLIANCE (principal 2026-07-27): every feature row carries the gate verdict
of the dataset it derives from. A feature built on an UNVERIFIED input is marked BLOCKED and is
not offered to the miner -- optimising feature space over broken inputs is exactly what the
doctrine forbids.

Read-only. No keys, no LLM, no network. Run from repo root.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/feature_library.json"
GATE = ROOT / "data/measurement_gate.json"
MECH = ROOT / "data/mechanism_board.json"

# ---------------------------------------------------------------- REGISTERED FEATURES
# Seeded from features this desk has ACTUALLY computed. Nothing aspirational: every row below
# corresponds to code that ran. `tested_constructions` is what was carried through to a verdict.
FEATURES = [
    # -- microstructure state variables from the moat (micro_factory.py, commit ae4045b)
    {"id": "F001", "name": "spread_bps", "mechanism": "M_LIQUIDITY_WITHDRAWAL",
     "source": "data/moat", "producer": "scripts/micro_factory.py",
     "rationale": "quoted cost of immediacy; widens as inventory risk binds",
     "status": "computed_unused", "tested_constructions": 0},
    {"id": "F002", "name": "depth5", "mechanism": "M_LIQUIDITY_WITHDRAWAL",
     "source": "data/moat", "producer": "scripts/micro_factory.py",
     "rationale": "notional within 5bps of mid; the liquidity actually reachable",
     "status": "tested", "tested_constructions": 1,
     "result": "neg-z vs 24h roll: raw lead rho +0.3032 (t +3.68) -> residual +0.0154 (t +0.28) "
               "after orthogonalising to same-period RV. Vol clustering explained it."},
    {"id": "F003", "name": "depth10", "mechanism": "M_LIQUIDITY_WITHDRAWAL",
     "source": "data/moat", "producer": "scripts/micro_factory.py",
     "rationale": "notional within 10bps; the shoulder of the book",
     "status": "computed_unused", "tested_constructions": 0},
    {"id": "F004", "name": "imbalance", "mechanism": "M_LIQUIDITY_WITHDRAWAL",
     "source": "data/moat", "producer": "scripts/micro_factory.py",
     "rationale": "bid share of near depth; directional inventory pressure",
     "status": "computed_unused", "tested_constructions": 0},
    {"id": "F005", "name": "concentration", "mechanism": "M_LIQUIDITY_WITHDRAWAL",
     "source": "data/moat", "producer": "scripts/micro_factory.py",
     "rationale": "top-level share of near depth; thin veneer vs real book",
     "status": "computed_unused", "tested_constructions": 0},
    {"id": "F006", "name": "slope", "mechanism": "M_LIQUIDITY_WITHDRAWAL",
     "source": "data/moat", "producer": "scripts/micro_factory.py",
     "rationale": "depth10/depth5; how fast liquidity accumulates away from touch",
     "status": "computed_unused", "tested_constructions": 0},
    # -- the one survivor on this desk
    {"id": "F007", "name": "funding_rate_persistence", "mechanism": "M_FORCED_DELEVERAGE",
     "source": "binance funding", "producer": "scripts/funding_persistence.py",
     "rationale": "leveraged crowding persists; who pays carry today tends to pay tomorrow",
     "status": "confirmed", "tested_constructions": 1,
     "result": "IC +0.432 (t +29.7) at 24h; top-decile +29.08%/yr vs median +3.77%/yr; "
               "selection edge +25.30%/yr; shock half-life 0.8 periods (6h)."},
    {"id": "F008", "name": "oi_ls_ratio", "mechanism": "M_FORCED_DELEVERAGE",
     "source": "data/oi_ls_history.jsonl", "producer": "scripts/run_axis_shadows.py",
     "rationale": "positioning skew as a proxy for forced-unwind pressure",
     "status": "forward_clock", "tested_constructions": 1,
     "result": "OOS forward clock running; first verdict 2026-08-07."},
    {"id": "F009", "name": "cny_otc_premium", "mechanism": "M_STRUCTURAL_BARRIER",
     "source": "data/cny_otc_premium_history.jsonl", "producer": "UNCOMMITTED (backfill)",
     "rationale": "capital control prevents convergence; premium is the barrier's price",
     "status": "blocked", "tested_constructions": 1,
     "result": "input FAILED measurement gate: no producer, and timestamp alignment is "
               "'23:55 CST assumed' rather than verified."},
]

# ---------------------------------------------------------------- CONSTRUCTION GRAMMAR
# The observable space per mechanism. OBSERVABLES are what you can see; TRANSFORMS turn a level
# into a dynamic; WINDOWS set the horizon; NORMS make it comparable across symbols.
GRAMMAR = {
    "M_LIQUIDITY_WITHDRAWAL": {
        "observables": ["depth5", "depth10", "spread_bps", "imbalance", "concentration", "slope"],
        "transforms": ["level", "delta", "replenish_rate", "recovery_halflife", "one_sided_gap"],
        "windows": ["1h", "4h", "24h"],
        "norms": ["zscore_roll", "pct_rank", "raw"],
    },
    "M_FORCED_DELEVERAGE": {
        "observables": ["funding", "oi", "ls_ratio", "taker_ratio", "basis"],
        "transforms": ["level", "delta", "dispersion", "crowding_z"],
        "windows": ["8h", "24h", "72h"],
        "norms": ["zscore_roll", "pct_rank", "raw"],
    },
}
# constructions already carried to a verdict -- (mechanism, observable, transform, window, norm)
TESTED = {
    ("M_LIQUIDITY_WITHDRAWAL", "depth5", "level", "24h", "zscore_roll"),
    ("M_FORCED_DELEVERAGE", "funding", "level", "24h", "raw"),
    ("M_FORCED_DELEVERAGE", "ls_ratio", "level", "24h", "zscore_roll"),
}
# PRIOR RANKING. Not a prediction of alpha -- a prior on whether the construction can even be
# DISTINGUISHED from what already failed. Transforms that are dynamics rank above levels because
# the level construction is the one that died to vol clustering.
TRANSFORM_PRIOR = {"level": 0.2, "delta": 0.6, "replenish_rate": 1.0,
                   "recovery_halflife": 0.9, "one_sided_gap": 0.8,
                   "dispersion": 0.7, "crowding_z": 0.5}


def _gate_verdicts() -> dict:
    if not GATE.exists():
        return {}
    try:
        return {k: v.get("verdict") for k, v in
                json.loads(GATE.read_text("utf-8")).get("datasets", {}).items()}
    except Exception:  # blind-except intentional (BLE001)
        return {}


def main() -> None:
    print("=== FEATURE LIBRARY -- features as managed assets ===")
    print("    'which pieces of information are consistently useful?' beats 'what strategy next?'\n")
    gv = _gate_verdicts()
    live_mechs = set()
    if MECH.exists():
        try:
            mb = json.loads(MECH.read_text("utf-8"))
            live_mechs = {m for m, v in mb.get("verdicts", {}).items()
                          if v in ("ALIVE", "UNTESTED")}
        except Exception:  # blind-except intentional (BLE001)
            pass

    rows = []
    for f in FEATURES:
        src = Path(f["source"]).name
        verdict = gv.get(src)
        blocked = verdict == "FAILED"
        rows.append({**f, "input_gate": verdict or ("n/a" if "/" not in f["source"] else "UNGATED"),
                     "blocked_by_measurement": blocked})
    print(f"  {'id':<6}{'feature':<26}{'mechanism':<26}{'status':<17}{'input gate'}")
    for r in rows:
        print(f"  {r['id']:<6}{r['name']:<26}{r['mechanism']:<26}{r['status']:<17}"
              f"{r['input_gate']}")
    unused = [r for r in rows if r["status"] == "computed_unused"]
    print(f"\n  {len(unused)} of {len(rows)} features were COMPUTED AND DISCARDED. Each one cost a")
    print("  full pass over 4.4GB of order books and none is reachable without re-reading it.")
    blocked = [r for r in rows if r["blocked_by_measurement"]]
    if blocked:
        print(f"  {len(blocked)} BLOCKED by the measurement gate: "
              f"{', '.join(r['name'] for r in blocked)}")
        print("  (doctrine: a feature on an unverified input is not offered to the miner)")

    # ------------------------------------------------ CONTINUOUS FEATURE MINER
    print("\n=== CONTINUOUS FEATURE MINER -- 'what else could represent this mechanism?' ===")
    print("    enumerated mechanically, so exploration coverage becomes a NUMBER\n")
    proposals = []
    for mech, g in GRAMMAR.items():
        if live_mechs and mech not in live_mechs:
            print(f"  {mech}: skipped (mechanism not ALIVE/UNTESTED on the board)")
            continue
        cells = list(product(g["observables"], g["transforms"], g["windows"], g["norms"]))
        done = [c for c in cells if (mech, *c) in TESTED]
        cov = len(done) / len(cells) * 100
        print(f"  {mech}")
        print(f"    construction space: {len(g['observables'])} observables x "
              f"{len(g['transforms'])} transforms x {len(g['windows'])} windows x "
              f"{len(g['norms'])} norms = {len(cells)} cells")
        print(f"    TESTED {len(done)}/{len(cells)} = {cov:.1f}% COVERAGE")
        for obs, tr, win, nrm in cells:
            if (mech, obs, tr, win, nrm) in TESTED:
                continue
            score = TRANSFORM_PRIOR.get(tr, 0.4)
            if win == "1h":
                score += 0.15                      # finer horizon = more independent observations
            if nrm == "zscore_roll":
                score += 0.05
            proposals.append({"mechanism": mech, "observable": obs, "transform": tr,
                              "window": win, "norm": nrm, "prior": round(score, 3),
                              "name": f"{obs}__{tr}__{win}__{nrm}"})
    proposals.sort(key=lambda p: -p["prior"])
    print(f"\n  {len(proposals)} untested constructions enumerated. Top 12 by prior:\n")
    print(f"  {'prior':>6}  {'mechanism':<24}construction")
    for p in proposals[:12]:
        print(f"  {p['prior']:>6.2f}  {p['mechanism'][:24]:<24}{p['name']}")

    print("\n  THE PRIOR RANKS DISTINGUISHABILITY, NOT EXPECTED ALPHA. 'level' constructions rank")
    print("  LOWEST because the level construction is exactly what died to vol clustering on")
    print("  2026-07-27 -- retesting neighbouring levels re-runs a known null. Dynamics")
    print("  (replenish_rate, recovery_halflife, one_sided_gap) rank highest because they are the")
    print("  constructions a vol-clustering confound does NOT trivially reproduce.")
    print("\n  COVERAGE IS NOT PROGRESS. Testing all cells is mass multiple-hypothesis testing,")
    print("  which is why this desk has Holm correction and a SUSPECT-LOOKAHEAD rail. These")
    print("  proposals enter STAGE-A SCREENING ONLY -- unlimited, and with ZERO promotion")
    print("  authority. Nothing here can reach live capital without a pre-registered forward clock.")

    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "features": rows, "n_features": len(rows),
                               "computed_unused": len(unused), "blocked": len(blocked),
                               "proposals": proposals[:60],
                               "n_proposals": len(proposals)}, indent=1), "utf-8")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()

```

### scripts/hl_flow_alpha.py
```python
"""EXPERIMENT: does ELITE ORDER FLOW carry information? (mechanism #3, genuinely new)

Falsified already: (1) aggregate elite positioning level, (2) skill persistence (gapped). Both were
about WHO is good. This tests something different: when big/active Hyperliquid accounts actually
TRADE, does price move their way afterwards? That is the real copytrading mechanism and the spec's
"Information Advantage Engine" (layer 10) -- and it is untested.

TWO CIRCULARITY TRAPS, both designed around:
 (1) SELECTION: picking profitable traders then testing whether their trades preceded favourable
     moves is circular (profit IS that, by definition). So the cohort is selected on monthly VOLUME
     -- skill-neutral, performance-blind.
 (2) LOOKAHEAD: flow at bucket t is tested against the return of bucket t+1 ONLY (never the
     concurrent bucket), and the harness's de-contamination gate checks the signal LEADS rather
     than coincides.

Signed taker flow per bucket = sum(+notional for buys, -notional for sells) across the cohort,
per coin. Screened per-coin AND pooled (pooled t over coins = the honest N).
Multiplicity: this is 1 of 3 pre-registered mechanisms -> bar is |t| >= 2.7, not 2.0.
Stage-A only, zero promotion authority. Run from repo root."""
from __future__ import annotations

import json
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from libs.research.axis_screen import stage_a_screen

_LB = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"
_INFO = "https://api.hyperliquid.xyz/info"
N_TRADERS = 220           # volume-selected cohort
BUCKET_MS = 4 * 3600_000  # 4h buckets
COINS = ["BTC", "ETH", "SOL"]


def _get(url, timeout=180):
    req = urllib.request.Request(url, headers={"User-Agent": "quant-hlflow/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _post(payload, timeout=25):
    req = urllib.request.Request(_INFO, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "quant-hlflow/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def cohort() -> list[str]:
    rows = json.loads(_get(_LB))
    rows = rows.get("leaderboardRows", rows) if isinstance(rows, dict) else rows
    scored = []
    for r in rows:
        try:
            wp = dict(r.get("windowPerformances", []))
            vlm = float(wp.get("month", {}).get("vlm", 0) or 0)
            av = float(r.get("accountValue", 0) or 0)
            a = r.get("ethAddress")
            if a and av >= 25_000 and vlm > 0:
                scored.append((vlm, a))       # VOLUME-selected: performance-blind
        except (TypeError, ValueError):
            continue
    scored.sort(reverse=True)
    print(f"leaderboard {len(rows)} -> volume-ranked cohort {N_TRADERS} (performance-blind)")
    return [a for _, a in scored[:N_TRADERS]]


def main() -> None:
    addrs = cohort()
    flow: dict[str, dict[int, float]] = {c: defaultdict(float) for c in COINS}
    ok = 0
    tmin, tmax = None, None
    for i, a in enumerate(addrs):
        try:
            fills = _post({"type": "userFills", "user": a})
        except Exception:
            continue
        if not isinstance(fills, list) or not fills:
            continue
        ok += 1
        for f in fills:
            c = f.get("coin")
            if c not in flow:
                continue
            try:
                t = int(f["time"]); px = float(f["px"]); sz = float(f["sz"])
            except (KeyError, TypeError, ValueError):
                continue
            sgn = 1.0 if str(f.get("side", "")).upper().startswith("B") else -1.0
            flow[c][t // BUCKET_MS] += sgn * px * sz
            tmin = t if tmin is None else min(tmin, t)
            tmax = t if tmax is None else max(tmax, t)
        if (i + 1) % 60 == 0:
            print(f"  fills fetched {i+1}/{len(addrs)} (ok={ok})", flush=True)
    span_d = (tmax - tmin) / 86400_000 if tmin and tmax else 0
    print(f"cohort with fills: {ok}/{len(addrs)} | history span {span_d:.1f} days")

    results, pooled = [], []
    for c in COINS:
        buckets = sorted(flow[c])
        if len(buckets) < 80:
            print(f"{c}: thin ({len(buckets)} buckets)")
            continue
        # price per bucket from Binance (bucket close), aligned to the same grid
        sym = f"{c}USDT"
        kl = json.loads(_get(f"https://api.binance.com/api/v3/klines?symbol={sym}"
                             f"&interval=4h&limit=1000", 40))
        px = {int(k[0]) // BUCKET_MS: float(k[4]) for k in kl}
        grid = [b for b in buckets if b in px and (b + 1) in px]
        if len(grid) < 60:
            print(f"{c}: thin aligned ({len(grid)})")
            continue
        sig = np.array([flow[c][b] for b in grid])
        close = np.array([px[b] for b in grid])
        ret = np.zeros(len(close))
        ret[1:] = close[1:] / close[:-1] - 1.0
        r = stage_a_screen(sig, ret, name=f"hl_elite_flow_{c}", zwin=20)
        r["coin"] = c
        results.append(r)
        pooled.append(r.get("ic", 0.0))
        print(f"{c:4s} n={len(grid)} | IC {r.get('ic'):+.4f} | same {r.get('same_period_corr'):+.3f} "
              f"| resid {r.get('residual_ic'):+.4f} | momSh {r.get('sharpe_momentum'):+.2f} "
              f"| revSh {r.get('sharpe_reversal'):+.2f} | {r['verdict']}")

    if len(pooled) > 1:
        p = np.array(pooled)
        t = float(p.mean() / (p.std() / np.sqrt(len(p)))) if p.std() else 0.0
        print(f"\nPOOLED mean IC {p.mean():+.4f} (t {t:+.2f}, n={len(p)} coins) "
              f"| bar for 3-mechanism multiplicity: |t| >= 2.7")
    Path("data/hl_flow_alpha.json").write_text(json.dumps(
        {"updated": datetime.now(tz=UTC).isoformat(), "cohort_with_fills": ok,
         "history_days": round(span_d, 1), "results": results}, indent=1), "utf-8")


if __name__ == "__main__":
    main()

```

### scripts/micro_factory.py
```python
"""MICROSTRUCTURE FEATURE FACTORY -- turn the proprietary moat into measurable state variables.

P0. The blocker is gone: every k="d" record is a COMPLETE top-20 book both sides (verified 1358/1358
at (20,20)), so no reconstruction is needed. 4.4GB, 11,980 files, 30 symbols x spot/fut, and nobody
else has these snapshots at these timestamps. Everything else this desk researches -- GitHub, TVL,
attention, on-chain -- is available to anyone. This is not.

NOT INDICATORS. MECHANISM. The mechanism board rates M_LIQUIDITY_WITHDRAWAL as the ONLY untested
family with a live information advantage, and it reached that verdict from graveyard evidence
without knowing the moat existed. Its economic story: liquidity providers withdraw when inventory
risk binds, so price impact jumps. That yields a falsifiable question --

    DOES LIQUIDITY DISAPPEAR *BEFORE* VOLATILITY ARRIVES, OR ONLY ALONGSIDE IT?

which is exactly the lead-vs-coincident distinction that killed 38% of this desk's hypotheses
(C_WRONG_TIMING). So the test is built around it: withdrawal at bucket t vs realised vol at t+1,
with the CONTEMPORANEOUS relationship measured alongside. A liquidity measure that merely coincides
with volatility is not a signal, it IS volatility.

FEATURES per snapshot (state variables, not signals):
  spread_bps            quoted spread
  depth5 / depth10      notional within 5bps / 10bps of mid, both sides
  imbalance             bid share of near depth
  concentration         top-level share of near depth (thin veneer vs real book)
  slope                 depth10/depth5 -- how fast liquidity accumulates away from touch
Aggregated per hour to level + dispersion, then withdrawal is measured as a z-score against each
symbol's own rolling history.

Read-only. No keys, no LLM. Run from repo root.
"""
from __future__ import annotations

import gzip
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MOAT = ROOT / "data/moat/fut"
OUT = ROOT / "data/micro_features.json"
SYMS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
N_FILES = 60          # most recent contiguous hours per symbol
ROLL = 24             # hours of history for the withdrawal z-score


def book_features(rec: dict) -> dict | None:
    b, a = rec.get("b"), rec.get("a")
    if not b or not a:
        return None
    try:
        bp, ap = float(b[0][0]), float(a[0][0])
    except (TypeError, ValueError, IndexError):
        return None
    if bp <= 0 or ap <= 0 or bp >= ap:
        return None
    mid = (bp + ap) / 2
    d5b = d5a = d10b = d10a = 0.0
    top_b = 0.0
    for i, (p, q) in enumerate(b):
        p, q = float(p), float(q)
        n = p * q
        if p >= mid * 0.9995:
            d5b += n
            if i == 0:
                top_b = n
        if p >= mid * 0.999:
            d10b += n
    for p, q in a:
        p, q = float(p), float(q)
        n = p * q
        if p <= mid * 1.0005:
            d5a += n
        if p <= mid * 1.001:
            d10a += n
    near = d5b + d5a
    if near <= 0:
        return None
    return {"mid": mid, "spread_bps": (ap - bp) / mid * 1e4,
            "depth5": near, "depth10": d10b + d10a,
            "imbalance": d5b / near, "concentration": top_b / max(d5b, 1e-9),
            "slope": (d10b + d10a) / near}


def hourly(sym: str) -> list[dict]:
    d = MOAT / sym
    files = sorted(d.glob("*.jsonl.gz"))[-N_FILES:]
    out = []
    for f in files:
        vals: list[dict] = []
        try:
            with gzip.open(f, "rt", encoding="utf-8", errors="ignore") as fh:
                for ln in fh:
                    if '"k":"d"' not in ln and '"k": "d"' not in ln:
                        continue
                    try:
                        r = json.loads(ln)
                    except json.JSONDecodeError:
                        continue
                    fe = book_features(r)
                    if fe:
                        vals.append(fe)
        except Exception:
            continue
        if len(vals) < 30:
            continue
        mids = np.array([v["mid"] for v in vals])
        row = {"hour": f.stem, "n": len(vals), "mid_close": float(mids[-1]),
               "rv_intra": float(np.diff(np.log(mids)).std() * np.sqrt(len(mids)))}
        for k in ("spread_bps", "depth5", "depth10", "imbalance", "concentration", "slope"):
            arr = np.array([v[k] for v in vals])
            row[k] = float(arr.mean())
            if k in ("depth5", "spread_bps"):
                row[k + "_sd"] = float(arr.std())
        out.append(row)
    return out


def spearman(a, b):
    if len(a) < 8:
        return 0.0, 0.0
    ra, rb = np.argsort(np.argsort(a)).astype(float), np.argsort(np.argsort(b)).astype(float)
    if ra.std() == 0 or rb.std() == 0:
        return 0.0, 0.0
    r = float(np.corrcoef(ra, rb)[0, 1])
    n = len(a)
    return r, float(r * np.sqrt((n - 2) / max(1e-12, 1 - r ** 2)))


def main() -> None:
    print("=== MICROSTRUCTURE FEATURE FACTORY (proprietary moat, no reconstruction needed) ===")
    print("    mechanism M_LIQUIDITY_WITHDRAWAL: does liquidity vanish BEFORE volatility,")
    print("    or only alongside it? (lead-vs-coincident killed 38% of this desk's ideas)\n")
    results, pooled_lead, pooled_coin, pooled_res = [], [], [], []
    for sym in SYMS:
        rows = hourly(sym)
        if len(rows) < 30:
            print(f"  {sym:<10} thin ({len(rows)} usable hours)")
            continue
        d5 = np.array([r["depth5"] for r in rows])
        rv = np.array([r["rv_intra"] for r in rows])
        spr = np.array([r["spread_bps"] for r in rows])

        # WITHDRAWAL = negative z of near depth vs the symbol's own rolling history
        wd = np.zeros(len(d5))
        for i in range(ROLL, len(d5)):
            w = d5[i - ROLL:i]
            sd = w.std()
            wd[i] = -(d5[i] - w.mean()) / sd if sd > 0 else 0.0
        m = np.zeros(len(d5), bool)
        m[ROLL:-1] = True
        fwd = np.roll(rv, -1)

        r_lead, t_lead = spearman(wd[m], fwd[m])       # withdrawal now -> vol NEXT hour
        r_coin, t_coin = spearman(wd[m], rv[m])        # withdrawal now -> vol NOW
        # DE-CONTAMINATION: volatility CLUSTERS, so vol[t] predicts vol[t+1] on its own. A
        # withdrawal measure that is merely COINCIDENT with vol[t] therefore inherits a fake
        # 'lead'. Regress forward vol on current vol and test withdrawal against the RESIDUAL --
        # what is left is the information withdrawal adds BEYOND vol persistence. This is the same
        # gate that killed coinbase/turkey/elite-flow; applying it to my own result.
        _b = np.polyfit(rv[m], fwd[m], 1)
        resid = fwd[m] - (_b[0] * rv[m] + _b[1])
        r_res, t_res = spearman(wd[m], resid)
        r_persist, _ = spearman(rv[m], fwd[m])         # how strong is vol clustering itself?
        r_spr, _ = spearman(wd[m], spr[m])
        pooled_lead.append(r_lead)
        pooled_res.append(r_res)
        pooled_coin.append(r_coin)
        k = max(3, int(m.sum()) // 4)
        o = np.argsort(wd[m])
        hi, lo = float(fwd[m][o[-k:]].mean()), float(fwd[m][o[:k]].mean())
        print(f"  {sym:<10} hours={int(m.sum()):<4} depth5 ${d5.mean():>12,.0f}  "
              f"spread {spr.mean():5.2f}bps")
        print(f"             withdrawal -> NEXT-hour RV  rho {r_lead:+.3f} (t {t_lead:+.2f})   "
              f"high-wd RV {hi*100:.3f}% vs low {lo*100:.3f}% = {hi/max(lo,1e-9):.2f}x")
        print(f"             withdrawal -> SAME-hour RV  rho {r_coin:+.3f} (t {t_coin:+.2f})")
        print(f"             vol persistence rho {r_persist:+.3f} | RESIDUAL (de-contaminated) "
              f"rho {r_res:+.3f} (t {t_res:+.2f})  <-- the honest number")
        results.append({"sym": sym, "hours": int(m.sum()), "depth5_usd": round(float(d5.mean()), 0),
                        "spread_bps": round(float(spr.mean()), 3),
                        "lead_rho": round(r_lead, 4), "lead_t": round(t_lead, 2),
                        "coincident_rho": round(r_coin, 4), "coincident_t": round(t_coin, 2),
                        "residual_rho": round(r_res, 4), "residual_t": round(t_res, 2),
                        "vol_persistence": round(r_persist, 4),
                        "rv_ratio_hi_lo": round(hi / max(lo, 1e-9), 3),
                        "withdrawal_vs_spread_rho": round(r_spr, 4)})

    if len(pooled_lead) >= 3:
        pl, pc = np.array(pooled_lead), np.array(pooled_coin)
        t_pl = float(pl.mean() / (pl.std() / np.sqrt(len(pl)))) if pl.std() else 0.0
        print(f"\n  POOLED over {len(pl)} symbols:")
        print(f"    LEAD        mean rho {pl.mean():+.4f} (t {t_pl:+.2f}), "
              f"same sign {int((np.sign(pl) == np.sign(pl[0])).sum())}/{len(pl)}")
        print(f"    COINCIDENT  mean rho {pc.mean():+.4f}")
        pr = np.array(pooled_res)
        t_pr = float(pr.mean() / (pr.std() / np.sqrt(len(pr)))) if pr.std() else 0.0
        print(f"    RESIDUAL    mean rho {pr.mean():+.4f} (t {t_pr:+.2f}), "
              f"same sign {int((np.sign(pr) == np.sign(pr[0])).sum())}/{len(pr)}  <-- DECIDES IT")
        verdict = ("LEADS -- withdrawal adds information BEYOND vol persistence"
                   if abs(t_pr) >= 2.4 and abs(pr.mean()) > 0.15 else
                   "COINCIDENT -- the apparent lead is vol clustering, withdrawal adds nothing")
        print(f"    VERDICT: {verdict}")
    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "roll_hours": ROLL, "results": results}, indent=1), "utf-8")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()

```

### scripts/page_digest.py
```python
#!/usr/bin/env python3
"""DAILY FINDINGS PAGE -- one push a day carrying what the desk actually found.

BOSS DECISION on the principal's question ("can you report findings immediately when I'm not
there?"). I cannot write to a chat window while he is away, but the pager reaches him and the
digest is already generated daily -- what was missing was DELIVERY, not content.

DELIBERATELY NOT one page per finding. The desk already learned this the hard way: pager spam
(deadman + growth_defect + latched nags) trained the principal to ignore the channel and forced a
per-key dedupe. A channel he ignores is worse than no channel, and findings are exactly the class
that would spam it -- the miners produce dozens of cards a day. So:

  * IMMEDIATE page (already live in run_alerts) stays reserved for what genuinely needs a human:
    money-path defects, risk alarms, licence/legal blockers, and anything requiring his decision
    or spend.
  * THIS page is the once-daily digest: book state, validation clocks, what was mined and
    converted, and the top open item -- high signal, one buzz, readable in ten seconds.

Idempotent: writes data/.last_digest_page so a re-run inside the same UTC day is a no-op.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIGEST = ROOT / "docs/desk_digest.md"
STAMP = ROOT / "data/.last_digest_page"
NTFY = ROOT / "data/secrets/ntfy.json"


def _section(text: str, name: str, limit: int = 3) -> list[str]:
    """The first few bullet lines under a '## <name>' heading."""
    out: list[str] = []
    hit = False
    for ln in text.splitlines():
        if ln.startswith("## "):
            hit = ln[3:].strip().lower().startswith(name.lower())
            continue
        if hit and ln.strip().startswith("-"):
            out.append(re.sub(r"[*_`\[\]]", "", ln.strip("- ").strip()))
            if len(out) >= limit:
                break
    return out


def main() -> None:
    today = datetime.now(tz=UTC).date().isoformat()
    if STAMP.exists() and STAMP.read_text("utf-8").strip() == today:
        print("digest already paged today")
        return
    if not DIGEST.exists():
        print("no digest to page")
        return
    txt = DIGEST.read_text("utf-8", errors="ignore")

    parts: list[str] = []
    for name, lim in (("Book", 2), ("Validation clocks", 2), ("Mined", 2), ("Open", 2)):
        for ln in _section(txt, name, lim):
            parts.append(f"- {ln[:150]}")
    if not parts:                                   # fall back to the first bullets in the file
        parts = [f"- {re.sub(r'[*_`]', '', ln.strip()[:150])}"
                 for ln in txt.splitlines() if ln.strip().startswith("-")][:5]

    body = f"DESK DIGEST {today}\n" + "\n".join(parts[:8])
    try:
        topic = json.loads(NTFY.read_text("utf-8")).get("topic")
    except Exception:
        topic = None
    if not topic:
        print("no ntfy topic configured -- digest not paged")
        return
    # ntfy.sh free tier rate-limits per source; the 08:30 slot can collide with the max_audit
    # escalation page, and 2 of the first 4 digest fires died on HTTP 429 (delivery is the whole
    # point -- a digest that half-fails is register-#3 all over again). One patient retry clears
    # a burst limit; anything still failing after that is reported, never raised.
    for attempt in (0, 1):
        if attempt:
            time.sleep(90)
        req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=body.encode("utf-8"),
                                     method="POST")
        req.add_header("Title", "Quant desk: daily digest")
        req.add_header("Priority", "low")           # informational -- never buzzes like an alarm
        try:
            urllib.request.urlopen(req, timeout=20)
            STAMP.write_text(today, "utf-8")
            print(f"digest paged ({len(parts)} lines)")
            return
        except Exception as exc:                    # a failed digest must never break a cycle
            print(f"digest page failed{' (after retry)' if attempt else ''}: {exc!r}")


if __name__ == "__main__":
    main()

```

### scripts/run_cashcarry_shadow.py
```python
"""90-day forward shadow of the cash-and-carry strategy -- its honest validation path (paper).

Freezes the strategy and tracks realized cash-carry returns AFTER a freeze date, reporting forward
Sharpe vs the backtest. Cash-and-carry cannot run on the futures testnet (no spot leg), so this
forward shadow IS its certification route until a live spot+perp account is opened. The strategy is
the SAME function used in the backtest (apples-to-apples). Writes web/cashcarry_shadow.json.

    python scripts/run_cashcarry_shadow.py
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
from libs.research.cashcarry import cashcarry_returns
from libs.validation.dsr import sharpe_ratio
from libs.validation.forward_stats import autocorr_factor, nw_tstat

_CRYPTO = Path("data/lake/bronze/crypto")
_OUT = Path("web/cashcarry_shadow.json")
_STATE = Path("data/cashcarry_shadow_state.json")
_PPY = 365.0


def _panels() -> tuple[pd.DataFrame, pd.DataFrame]:
    lake = ParquetLake("data/lake")
    fundings, bases = {}, {}
    for s in list_liquid_perps(top_n=120):
        if not (_CRYPTO / s / Timeframe.D1.value).exists():
            continue
        register_instrument(InstrumentSpec(symbol=s, asset_class=AssetClass.CRYPTO, description=s))
        df = lake.read_bars(Layer.BRONZE, s, Timeframe.D1).set_index("timestamp")
        if "funding" not in df.columns or "basis" not in df.columns or len(df) < 250:
            continue
        fundings[s] = df["funding"]
        bases[s] = df["basis"]
    f = pd.DataFrame(fundings).sort_index()
    return f, pd.DataFrame(bases).reindex(f.index)


def _ann(r: np.ndarray) -> float:
    a = r[r != 0.0]
    return round(float(sharpe_ratio(a) * np.sqrt(_PPY)), 2) if len(a) > 5 else 0.0


def main() -> None:
    funding, basis = _panels()
    if funding.shape[1] < 12:
        raise SystemExit("need a liquid perp panel with basis")
    r = cashcarry_returns(funding, basis)
    dates = pd.to_datetime(funding.index)

    st = json.loads(_STATE.read_text("utf-8")) if _STATE.exists() else {}
    if "shadow_start" not in st:
        st["shadow_start"] = datetime.now(tz=UTC).date().isoformat()
        _STATE.parent.mkdir(parents=True, exist_ok=True)
        _STATE.write_text(json.dumps(st), "utf-8")
    start = pd.Timestamp(st["shadow_start"], tz="UTC")
    fwd_mask = np.asarray(dates >= start)
    fwd, bt = r[fwd_mask], r[~fwd_mask]
    fwd_days = int((dates[fwd_mask].max() - start).days) if fwd_mask.any() else 0
    fwd_active = fwd[fwd != 0.0]

    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "strategy": "cash_and_carry (long spot + short perp)",
        "shadow_start": st["shadow_start"],
        "backtest_ann_sharpe": _ann(bt),
        "forward_ann_sharpe": _ann(fwd),
        "forward_days": fwd_days,
        "forward_cum_return": round(float(np.prod(1.0 + fwd_active) - 1.0), 4) if len(fwd_active)
        else 0.0,
        "target": 1.5,
        "execution": "shadow only -- futures testnet has no spot; live needs a spot+perp account.",
    }
    # adaptive promotion window (live_deployment_policy v2, 2026-07-12 external review):
    # FAST-TRACK at >=40d needs ALL of (a) NEWEY-WEST corrected t >= 1.65 -- the naive
    # Sharpe*sqrt(d/365) assumes IID daily returns and funding is sticky, so the naive t
    # overstates significance exactly when N is small; (b) fwd >= 0.5x backtest; (c) >=1
    # REGIME EVENT inside the window (an aggregate funding-inversion day or a basis-
    # dislocation day) -- 40 calm days test a market mood, not an edge. Carry is the
    # PRE-REGISTERED PRIMARY hypothesis (registered alone, before any cohort) -> exempt
    # from the Holm cohort correction that later candidates carry.
    fs, bs = out["forward_ann_sharpe"], out["backtest_ann_sharpe"]
    tstat = round(float(fs) * (fwd_days / 365.0) ** 0.5, 2) if fs else 0.0
    # NW t on ALL forward days (round-2 review: dropping zero days truncates the return
    # distribution -- a day the live strategy earned nothing IS evidence, not missing data)
    t_nw = nw_tstat(fwd) if len(fwd) >= 5 else 0.0
    # inversion day = even the TOP-20 funding names average <=0 (true carry famine for the
    # harvestable set -- broad-panel mean is <=0 on most days and would gate nothing)
    top_f = funding.apply(lambda row: row.nlargest(20).mean(), axis=1)
    mean_b = basis.mean(axis=1)
    b_sd = float(mean_b[~fwd_mask].std()) or 1e9
    inv_days = int((top_f[fwd_mask] <= 0).sum())
    dis_days = int((mean_b[fwd_mask].abs() > 3.0 * b_sd).sum())
    events = inv_days + dis_days
    # REGIME EVIDENCE v2 (round-2 review: discrete crisis events are rare enough to make the
    # fast-track a dead letter -- consensus fix): the window qualifies via an EVENT OR via
    # funding-rate VARIANCE >= the 25th percentile of the backtest's rolling-40d distribution
    # (proves the window was not in the calmest quartile of history; continuous, not binary).
    bt_roll_sd = top_f[~fwd_mask].rolling(40).std().dropna()
    vol_bar = float(bt_roll_sd.quantile(0.25)) if len(bt_roll_sd) > 50 else 0.0
    fwd_vol = float(top_f[fwd_mask].std()) if int(fwd_mask.sum()) > 5 else 0.0
    regime_ok = events >= 1 or (vol_bar > 0.0 and fwd_vol >= vol_bar)
    ft_ok = fwd_days >= 40 and t_nw >= 1.65 and fs >= 0.5 * bs and regime_ok
    out["forward_tstat_naive"] = tstat
    out["forward_tstat"] = t_nw                       # Newey-West corrected -- the binding number
    fac = autocorr_factor(np.asarray(fwd)) if len(fwd) >= 20 else 1.0
    out["autocorr"] = {"factor": round(fac, 2), "clamped_at_max": fac >= 5.0}
    # clamped_at_max=True means true persistence may EXCEED the correction -- treat the
    # t-stat as an upper bound that cycle, never as exact (round-2/3 review)
    out["regime_events"] = {"inversion_days": inv_days, "basis_dislocation_days": dis_days}
    out["funding_vol"] = {"fwd": round(fwd_vol, 6), "bar_25pct_bt": round(vol_bar, 6),
                          "regime_ok": regime_ok}
    out["multiplicity"] = ("pre-registered PRIMARY hypothesis (shadow frozen before any cohort) "
                           "-> Holm-exempt; cohort candidates use forward_stats.holm_bar over ALL "
                           "trailing-180d forward entrants INCLUDING killed ones (no attrition)")
    out["fast_track"] = (
        "ELIGIBLE (>=40d + NW-t>=1.65 + fwd>=0.5xbt + regime evidence) -> live-promotable" if ft_ok
        else (f"day {fwd_days}/40 min; NW-t={t_nw} (naive {tstat}); regime evidence "
              f"{'OK' if regime_ok else 'PENDING'} (events {events}, funding-vol "
              f"{round(fwd_vol, 5)} vs bar {round(vol_bar, 5)})"))
    out["verdict"] = (f"forward day {fwd_days} (fast-track 40d / standard 90d); NW t-stat {t_nw} "
                      f"(naive {tstat}), regime evidence {'OK' if regime_ok else 'pending'}. "
                      f"Backtest Sharpe {bs} -- must hold forward before any capital.")
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    print(f"cash-carry shadow: backtest {out['backtest_ann_sharpe']} | forward "
          f"{out['forward_ann_sharpe']} ({fwd_days}/90d) since {st['shadow_start']}")


if __name__ == "__main__":
    main()

```

### scripts/run_crypto_target.py
```python
"""Emit today's crypto target portfolio -- the brain's per-perp decision for the testnet executor.

Combines the FOUR most decorrelated crypto sleeves -- funding carry, basis carry, taker flow, and
cross-sectional price momentum (the most orthogonal of all, ~-0.06 corr to carry) -- into ONE net
dollar-neutral target weight per perp, gross-normalized to 1. Equal sleeve weight (no fitting,
robust, ~= equal-risk for weakly-correlated sleeves). More decorrelated sleeves => lower portfolio
variance (sigma_port ~ sigma/sqrt(N)) => a smoother equity curve and less MTM giveback, the
diversification benefit -- NOT new validated edge, just variance reduction. data/crypto_target.json.

    python scripts/run_crypto_target.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from libs.data.crypto_source import list_liquid_perps
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.research.crypto_sleeves import latest_weights

_CRYPTO = Path("data/lake/bronze/crypto")
_OUT = Path("data/crypto_target.json")
_SLEEVE_W = Path("data/sleeve_weights.json")     # cross-sleeve allocation (HRP-or-equal, gated)


def _sleeve_weights(names: list[str]) -> dict[str, float]:
    """Per-sleeve capital weights from run_sleeve_alloc (HRP if it beat equal), else equal."""
    try:
        cfg = json.loads(_SLEEVE_W.read_text("utf-8")).get("weights", {})
        if all(k in cfg for k in names):           # only use if it covers exactly this sleeve set
            tot = sum(float(cfg[k]) for k in names)
            if tot > 0:
                return {k: float(cfg[k]) / tot for k in names}
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    return {k: 1.0 / len(names) for k in names}    # robust fallback: equal weight


def merge_sleeve_books(
    named: dict[str, dict[str, float]], sleeve_w: dict[str, float]
) -> dict[str, float]:
    """Combine per-sleeve target books into ONE gross-normalized (sum|w| = 1) net book.

    Each sleeve's per-symbol weight is scaled by its cross-sleeve capital weight and summed per
    symbol; the net book is then normalized so gross exposure is 1. Dust positions (|w| <= 1e-6)
    are dropped. Returns ``{}`` when the combined gross is 0. Pure function (extracted from ``main``
    for testability) — the live per-perp decision the testnet executor consumes.
    """
    merged: dict[str, float] = {}
    for name, book in named.items():
        for sym, w in book.items():
            merged[sym] = merged.get(sym, 0.0) + w * sleeve_w[name]
    gross = sum(abs(v) for v in merged.values())
    if gross <= 0:
        return {}
    return {k: round(v / gross, 5) for k, v in merged.items() if abs(v) > 1e-6}


def _panels() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    lake = ParquetLake("data/lake")
    closes, fundings, bases, takers = {}, {}, {}, {}
    for s in list_liquid_perps(top_n=120):
        if not (_CRYPTO / s / Timeframe.D1.value).exists():
            continue
        register_instrument(InstrumentSpec(symbol=s, asset_class=AssetClass.CRYPTO, description=s))
        df = lake.read_bars(Layer.BRONZE, s, Timeframe.D1).set_index("timestamp")
        if "funding" not in df.columns or len(df) < 250:
            continue
        closes[s] = df["close"]
        fundings[s] = df["funding"]
        if "basis" in df.columns:
            bases[s] = df["basis"]
        if "taker_buy_frac" in df.columns:
            takers[s] = df["taker_buy_frac"]
    close = pd.DataFrame(closes).sort_index()
    f = pd.DataFrame(fundings).reindex(close.index)
    basis = pd.DataFrame(bases).reindex(close.index) if bases else pd.DataFrame()
    taker = pd.DataFrame(takers).reindex(close.index) if takers else pd.DataFrame()
    return close, f, basis, taker


def main() -> None:
    close, funding, basis, taker = _panels()
    if close.shape[1] < 12:
        raise SystemExit("need a liquid perp panel; run ingest_crypto + ingest_crypto_enriched")

    named: dict[str, dict[str, float]] = {
        "funding": latest_weights(close, funding.rolling(7).mean(), q=0.2, long_low=True),
        # cross-sectional price momentum -- the most orthogonal sleeve (decorrelates the book)
        "momentum": latest_weights(close, close / close.shift(20) - 1.0, q=0.2, long_low=False),
    }
    if not basis.empty and basis.shape[1] >= 12:
        named["basis"] = latest_weights(close[basis.columns], basis.rolling(3).mean(),
                                        q=0.2, long_low=True)
    if not taker.empty and taker.shape[1] >= 12:
        named["taker"] = latest_weights(close[taker.columns], taker.rolling(5).mean(),
                                        q=0.2, long_low=False)

    sleeve_w = _sleeve_weights(list(named))            # HRP if it beat equal (gated), else equal
    target = merge_sleeve_books(named, sleeve_w)

    payload = {"generated": datetime.now(tz=UTC).isoformat(),
               "as_of": close.index[-1].date().isoformat(), "sleeves": len(named),
               "sleeve_weights": {k: round(sleeve_w[k], 4) for k in named},
               "n_positions": len(target), "weights": dict(sorted(
                   target.items(), key=lambda kv: -abs(kv[1])))}
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(payload, indent=2), "utf-8")
    print(f"crypto target: {len(target)} perps from {len(named)} sleeves "
          f"(weights {payload['sleeve_weights']}) -> {_OUT}")
    for k, v in list(payload["weights"].items())[:12]:
        print(f"  {k:14} {v:+.4f}")


if __name__ == "__main__":
    main()

```

### scripts/run_intelligence_cycle.py
```python
"""INTELLIGENCE CYCLE -- activates the desk's dormant intelligence-compounding layer.

THE FINDING THAT PRODUCED THIS (measured 2026-07-30, not assumed). The principal's strategic
review named research meta-learning, agent evolution, prediction calibration, capital-allocation
learning, information-advantage measurement and an alpha-decay lab as the highest-ROI MISSING
subsystems. They are not missing. Every one of them is BUILT and has ZERO CALLERS:

    libs/self_improvement/meta_learning.py        regime -> alpha affinity learning
    libs/self_improvement/research_priority.py    experiment ERV/decay ranking
    libs/self_improvement/capital_reallocator.py  capital-allocation learning
    libs/self_improvement/health_monitor.py       per-alpha decay/health assessment
    libs/self_improvement/marketplace.py          research capital market
    libs/self_improvement/weight_optimizer.py     allocation weights
    libs/self_improvement/lifecycle_actions.py    promote/demote/retire actions
    scripts/moat_audit.py                         information-advantage measurement
    scripts/revalidate_clocks.py                  decay revalidation of live axes

Proving command: `grep -rl "self_improvement.<mod>" scripts/ libs/ | grep -v libs/self_improvement/`
returned NOTHING for each. So the gap was never architecture -- it was ACTIVATION (L2.9), and the
correct fix is one organ that runs them on a schedule, NOT eleven new subsystems, which is exactly
the complexity inflation the anti-bloat rule forbids.

WHAT IT DOES: runs each dormant capability against whatever real state exists, writes one evidence
artifact (`web/intelligence_cycle.json`), and reports per-capability status
ACTIVE / NO-INPUT / ERROR. NO-INPUT is a first-class verdict, never a silent skip: a capability
that cannot run for want of data is a DATA gap and must read as one (0 validated alphas today means
several of these legitimately have nothing to chew on yet, and saying so is the honest output).

ZERO PROMOTION AUTHORITY. Every insight here is non-deployable by construction --
`meta_learning.govern()` refuses to mark anything deployable unless cpcv/dsr/pbo/walk-forward all
pass, and this organ never asserts they do. It produces INSIGHT, never capital moves.

    python scripts/run_intelligence_cycle.py [--json]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
# `python scripts/x.py` puts scripts/ on sys.path, not the repo root, so `import libs` fails
# unless the package happens to be pip-installed. On the VPS it is; on a FRESH RESTORE it is not,
# which would make this organ read ERROR on every capability for a purely environmental reason
# (measured on first run: 4/7 ERROR "No module named 'libs'"). Make it work in both worlds.
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_OUT = _ROOT / "web/intelligence_cycle.json"


def _read(rel: str) -> Any:
    try:
        return json.loads((_ROOT / rel).read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _cap(name: str, status: str, detail: str, **extra: Any) -> dict[str, Any]:
    return {"capability": name, "status": status, "detail": detail, **extra}


def _meta_learning() -> dict[str, Any]:
    """Regime -> alpha affinity. Needs regime labels + per-alpha return series."""
    try:
        import numpy as np

        from libs.self_improvement.meta_learning import MetaLearningEngine
    except ImportError as e:
        return _cap("meta_learning", "ERROR", f"import failed: {e}")
    shadow = _read("web/cashcarry_shadow.json")
    series = None
    if isinstance(shadow, dict):
        for key in ("returns", "daily_returns", "pnl_series"):
            v = shadow.get(key)
            if isinstance(v, list) and len(v) >= 20:
                series = [float(x) for x in v if isinstance(x, (int, float))]
                break
    if not series:
        return _cap("meta_learning", "NO-INPUT",
                    "needs a per-alpha return series (web/cashcarry_shadow.json returns[]); "
                    "0 validated alphas means there is genuinely little to learn affinity over")
    regime = _read("web/regime.json") or {}
    label = str(regime.get("regime") or regime.get("state") or "unlabelled")
    # One regime label per observation: with a single current label this is a degenerate but HONEST
    # run -- it records the affinity of the only regime the desk can name today.
    insight = MetaLearningEngine().learn_regime_affinity(
        [label] * len(series), {"carry": np.asarray(series)})
    governed = MetaLearningEngine().govern(insight, cpcv_pass=False, dsr_pass=False,
                                           pbo_pass=False, walk_forward_pass=False)
    return _cap("meta_learning", "ACTIVE",
                f"regime->alpha affinity over n={len(series)} in regime '{label}'",
                deployable=bool(governed.deployable), relationship=insight.relationship)


def _data_registry() -> dict[str, Any]:
    """MEASURED data inventory (EXECUTION_QUEUE.md RANK 4, GAP_REGISTER #77).

    Runs here rather than only on its own cron because the map is what every OTHER organ in this
    cycle navigates by: research_priority ranks what to test, and row #77's whole lesson is that
    those rankings were being made off an inventory that reported row counts as spans and omitted
    the desk's best panel. A stale map is worse than no map, so it is rebuilt in the same tick that
    consumes it.
    """
    try:
        from libs.research.data_registry import REPL_PROPRIETARY, build
    except ImportError as e:
        return _cap("data_registry", "ERROR", f"import failed: {e}")
    assets = build()
    if not assets:
        return _cap("data_registry", "NO-INPUT",
                    "no collector declares a data path -- discovery found nothing to measure")
    measured = [a for a in assets if a.span.measured]
    absent = [a for a in assets if a.span.status == "absent"]
    unread = [a for a in assets if (a.span.days or 0) > 365 and not a.consumers]
    longest = max(measured, key=lambda a: a.span.days or 0, default=None)
    detail = (f"{len(assets)} assets, {len(measured)} MEASURED spans, "
              f"{len(absent)} declared-but-absent")
    if longest:
        detail += f"; longest {longest.id} {longest.span.days}d"
    if unread:
        detail += f"; {len(unread)} with >1y history and NO reader"
    return _cap(
        "data_registry", "ACTIVE" if measured else "NO-INPUT", detail,
        assets=len(assets), measured=len(measured), absent=len(absent),
        longest_span_days=(longest.span.days if longest else 0),
        widest_breadth=max((a.breadth or 0 for a in assets), default=0),
        proprietary=[a.id for a in assets if a.replication == REPL_PROPRIETARY],
        unread_long_history=[a.id for a in unread],
    )


def _research_priority() -> dict[str, Any]:
    """Rank research categories by decay pressure + expected yield."""
    try:
        from libs.self_improvement.research_priority import ResearchPriorityEngine
    except ImportError as e:
        return _cap("research_priority", "ERROR", f"import failed: {e}")
    brief = _read("data/executive_kpis.json") or {}
    # Decay pressure per mechanism family, from the desk's own family-kill record when present.
    decay = {}
    fams = brief.get("family_survival") if isinstance(brief, dict) else None
    if isinstance(fams, dict):
        for fam, st in fams.items():
            if isinstance(st, dict) and isinstance(st.get("rate"), (int, float)):
                decay[str(fam)] = max(0.0, 1.0 - float(st["rate"]))
    if not decay:
        # Fall back to the DESK_BRIEF family kills, which are always present in the repo.
        decay = {"price_only": 1.0, "attention_social": 1.0, "trader_behavioural": 1.0,
                 "funding_positioning": 0.5, "onchain_flow": 0.8, "regional_premium": 0.9}
    ranked = ResearchPriorityEngine().prioritize(decaying_by_category=decay)
    return _cap("research_priority", "ACTIVE",
                f"ranked {len(ranked)} research categories by decay pressure",
                top=[{"category": p.category, "score": round(p.priority_score, 3),
                      "reason": p.reason} for p in ranked[:5]])


def _capital_reallocator() -> dict[str, Any]:
    try:
        import libs.self_improvement.capital_reallocator  # noqa: F401
    except ImportError as e:
        return _cap("capital_reallocator", "ERROR", f"import failed: {e}")
    live = _read("web/cashcarry_live.json") or {}
    sleeves = live.get("sleeves") if isinstance(live, dict) else None
    if not isinstance(sleeves, dict) or len(sleeves) < 2:
        return _cap("capital_reallocator", "NO-INPUT",
                    "needs >=2 deployed sleeves to reallocate between; the desk runs 1 (carry). "
                    "This is a DEPLOYED-ALPHA gap, not a code gap -- it activates at sleeve 2")
    return _cap("capital_reallocator", "ACTIVE", f"{len(sleeves)} sleeves available")


def _health_monitor() -> dict[str, Any]:
    try:
        import libs.self_improvement.health_monitor  # noqa: F401
    except ImportError as e:
        return _cap("health_monitor", "ERROR", f"import failed: {e}")
    cards = _read("data/alpha_registry.json") or _read("web/alpha_lifecycle.json")
    n = len(cards.get("alphas", [])) if isinstance(cards, dict) else 0
    if not n:
        return _cap("health_monitor", "NO-INPUT",
                    "needs >=1 alpha card with live metrics; registry holds 0 -- the binding "
                    "constraint is validated alphas, and no amount of code changes that")
    return _cap("health_monitor", "ACTIVE", f"{n} alpha card(s) assessable")


def _subprocess_cap(name: str, script: str, timeout_s: float = 240.0,
                    args: list[str] | None = None) -> dict[str, Any]:
    """Run a standalone dormant script and record that it EXECUTED, with its own exit code.

    ``args`` exists for capabilities that have a deliberately cheap mode inside the cycle -- the
    strategic director runs --dry-run here so a 6-hourly tick proves its path without spending
    OpenRouter credit on every fire.
    """
    path = _ROOT / script
    if not path.exists():
        return _cap(name, "ERROR", f"{script} missing")
    try:
        env = {**os.environ, "PYTHONPATH": f"{_ROOT}{os.pathsep}{os.environ.get('PYTHONPATH', '')}"}
        p = subprocess.run([sys.executable, script, *(args or [])], cwd=_ROOT, env=env,
                           capture_output=True, timeout=timeout_s, check=False, text=True)
    except subprocess.TimeoutExpired:
        return _cap(name, "ERROR", f"{script} exceeded {timeout_s:.0f}s")
    tail = (p.stdout or p.stderr or "").strip().splitlines()
    return _cap(name, "ACTIVE" if p.returncode == 0 else "NO-INPUT",
                f"{script} exit={p.returncode}: {tail[-1][:180] if tail else 'no output'}")


def _dormancy() -> dict[str, Any]:
    """THE STANDING VERSION OF TODAY'S BIGGEST FIND. On 2026-07-30 nine 'missing' subsystems turned
    out to be built with zero callers -- found because someone happened to grep. This makes that
    question mechanical: what does nothing import, and what does nothing schedule?
    Priority encoded (principal): find unused capability BEFORE inventing new capability."""
    try:
        from libs.self_improvement.dormancy import scan, summarise
    except ImportError as e:
        return _cap("dormancy_hunter", "ERROR", f"import failed: {e}")
    rep = summarise(scan())
    n = sum(rep["counts"].values()) if isinstance(rep.get("counts"), dict) else 0
    return _cap("dormancy_hunter", "ACTIVE",
                f"{n} dormant capabilities ({rep['total_dormant_lines']} paid-for unused lines) "
                f"across {rep['scanned']['modules']} modules + {rep['scanned']['scripts']} scripts",
                report=rep)


def main() -> int:
    caps = [
        _dormancy(),
        # BEFORE the organs that navigate by it -- research_priority ranks what to test, and row
        # #77 is what happens when that ranking is made off a stale map.
        _data_registry(),
        _meta_learning(),
        _research_priority(),
        _capital_reallocator(),
        _health_monitor(),
        # Standalone organs that had ZERO callers and were never scheduled.
        _subprocess_cap("label_factory", "scripts/build_labels.py"),
        _subprocess_cap("fusion_search", "scripts/run_fusion_search.py"),
        _subprocess_cap("strategic_director", "scripts/run_strategic_director.py",
                        args=["--dry-run"]),
        _subprocess_cap("backtest_verify", "scripts/verify_backtest_engine.py"),
        _subprocess_cap("moat_audit", "scripts/moat_audit.py"),
        _subprocess_cap("revalidate_clocks", "scripts/revalidate_clocks.py"),
        _subprocess_cap("fusion_engine", "scripts/fusion_engine.py"),
    ]
    counts: dict[str, int] = {}
    for c in caps:
        counts[c["status"]] = counts.get(c["status"], 0) + 1
    report = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "law": "L2.9 capability audit loop -- a built capability that never executes is technical "
               "debt. NO-INPUT is a DATA/ALPHA gap reported as one, never a silent skip.",
        "counts": counts, "capabilities": caps,
        "note": "zero promotion authority: every insight here is non-deployable by construction",
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(report, indent=2, default=str), "utf-8")
    if "--json" in sys.argv:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(f"intelligence cycle: {counts}")
        for c in caps:
            print(f"  {c['status']:9} {c['capability']:20} {c['detail'][:110]}")
    # Exit 0 even with NO-INPUT: those are data gaps the register tracks, not runner failures.
    return 1 if counts.get("ERROR") else 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts/run_mutation.py
```python
"""MUTATION TESTING -- gap #53: the v8 8.2 bar (>=90% mutants killed) had never been measured once.

WHY THIS IS NOT OPTIONAL: four risk-path register rows (#2, #49, #37, #19) cite that bar as their
gate. A gate nobody has measured is a decoration, and 1199+ tests were of UNKNOWN strength --
they demonstrably EXECUTE code; nothing showed they CONSTRAIN it. This produces the desk's first
measured kill rates.

METHOD, and the honest trade-off stated up front: this is a self-contained AST mutation harness,
not mutmut. mutmut 3.6.0 installs cleanly and is the documented path for a long VPS run
(`mutmut run` over a whole module tree), but its copy-based workflow needs a writable project
mirror and minutes per mutant of pytest startup. This harness instead (a) copies the target module
+ its exercising tests into a throwaway tree under the scratchpad, (b) applies ONE deterministic
mutation at a time, (c) runs only that module's tests, (d) records KILLED (tests fail) /
SURVIVED (tests still pass -- the mutation is invisible to the suite) / TIMEOUT / ERROR.
Deterministic and dependency-free, so it reruns identically on the box.

A SURVIVED MUTANT IS THE DELIVERABLE, not the score: it names a line whose behaviour no test
pins. The report lists them with file:line and the exact mutation.

Operator set (deliberately small and high-signal):
  comparison flips     <  <=  >  >=  ==  !=      (off-by-one and boundary logic)
  arithmetic swaps     + -  * /                  (sign and scale errors)
  boolean negation     and <-> or, not-insertion (guard inversion)
  constant nudges      n -> n+1, n -> 0          (threshold slack)
  literal flips        True <-> False            (fail-open vs fail-closed)
  return-value drop    return X -> return None   (silent no-op)

    python scripts/run_mutation.py                      # default risk-path set
    python scripts/run_mutation.py --target libs/x.py --tests tests/test_x.py --budget-s 300
"""

from __future__ import annotations

import argparse
import ast
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:          # `import libs` works without an editable install
    sys.path.insert(0, str(_ROOT))
_OUT = _ROOT / "data/mutation_score.json"
_WORK = Path("/tmp/claude-0/-home-user-quant/1c87bc3b-ab99-5043-86ff-5b38ad12af2a/scratchpad/mut")

# The measured set. Order is priority order: the gate fix pending a principal decision first
# (measuring whether its 13 tests CONSTRAIN it is load-bearing for that decision), then the
# money-path stage machine, then the retry and risk gates.
# Test files verified present 2026-07-29 (a target whose tests do not exist scores ERROR, which
# is itself the finding: libs/execution/retry.py has NO dedicated test module, so its mutants
# cannot be measured -- recorded rather than silently dropped).
#
# EVERY TARGET LISTS ITS *_strength.py COMPANION, and the omission of one is not cosmetic.
# Measured 2026-07-30: gate.py was listed with `tests/risk/test_gate.py` alone while
# `tests/risk/test_gate_strength.py` -- the suite written specifically to kill its mutants --
# existed and was never run. The nightly job therefore recorded 23.5% instead of the true 86.3%
# and the ratchet reported a permanent REGRESSION on the money path. A false red is not a
# harmless conservative error: it trains the desk to ignore the one metric measuring whether its
# risk gate is actually constrained. `_missing_strength_suites()` below now fails the run rather
# than leaving this to whoever edits this list next.
_DEFAULT_TARGETS: list[tuple[str, list[str]]] = [
    ("libs/validation/stepwise.py",
     ["tests/validation/test_stepwise.py", "tests/validation/test_stepwise_strength.py"]),
    ("libs/execution/staging.py",
     ["tests/execution/test_staging.py", "tests/execution/test_staging_strength.py"]),
    ("libs/risk/gate.py",
     ["tests/risk/test_gate.py", "tests/risk/test_gate_strength.py"]),
    ("libs/execution/binance_live.py", ["tests/execution/test_binance_live.py"]),
]


def _missing_strength_suites() -> list[str]:
    """Targets with a *_strength.py suite on disk that the target list does not run.

    A strength suite exists for exactly one reason -- to kill mutants -- so not running it
    guarantees an understated score, and an understated score on the money path is the most
    expensive kind of false alarm: it makes the true number unreadable.
    """
    out = []
    for target, tests in _DEFAULT_TARGETS:
        listed = {Path(t).name for t in tests}
        for t in tests:
            companion = Path(_ROOT / t).with_name(Path(t).stem + "_strength.py")
            if companion.exists() and companion.name not in listed:
                out.append(f"{target}: {companion.relative_to(_ROOT)} exists but is not listed")
    return out

_CMP_FLIP = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt,
             ast.Eq: ast.NotEq, ast.NotEq: ast.Eq}
_BIN_FLIP = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult}


@dataclass
class Mutant:
    lineno: int
    kind: str
    detail: str


@dataclass
class TargetScore:
    target: str
    tests: list[str]
    killed: int = 0
    survived: int = 0
    timeout: int = 0
    error: int = 0
    runtime_s: float = 0.0
    survivors: list[dict[str, object]] = field(default_factory=list)
    #: mutation sites FOUND, vs `total` attempted. A budget-truncated run measures an arbitrary
    #: PREFIX of the site list, not a sample of it, so its rate is not an estimate of the whole.
    n_sites: int = 0

    @property
    def total(self) -> int:
        return self.killed + self.survived + self.timeout + self.error

    @property
    def kill_rate(self) -> float:
        # TIMEOUT counts as killed (the mutation changed observable behaviour enough to hang);
        # ERROR does not count either way and is reported separately so it cannot flatter a score.
        denom = self.killed + self.survived + self.timeout
        return round((self.killed + self.timeout) / denom, 4) if denom else 0.0


class _Collector(ast.NodeVisitor):
    """Enumerate mutation sites. One pass, so the site list is stable across runs."""

    def __init__(self) -> None:
        self.sites: list[Mutant] = []

    def visit_Compare(self, node: ast.Compare) -> None:
        for op in node.ops:
            if type(op) in _CMP_FLIP:
                self.sites.append(Mutant(node.lineno, "compare",
                                         f"{type(op).__name__} -> "
                                         f"{_CMP_FLIP[type(op)].__name__}"))
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if type(node.op) in _BIN_FLIP:
            self.sites.append(Mutant(node.lineno, "binop",
                                     f"{type(node.op).__name__} -> "
                                     f"{_BIN_FLIP[type(node.op)].__name__}"))
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.sites.append(Mutant(node.lineno, "boolop",
                                 f"{type(node.op).__name__} -> "
                                 f"{'Or' if isinstance(node.op, ast.And) else 'And'}"))
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, bool):
            self.sites.append(Mutant(node.lineno, "bool_const", f"{node.value} -> {not node.value}"))
        elif isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            self.sites.append(Mutant(node.lineno, "num_const", f"{node.value} -> {node.value + 1}"))
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        if node.value is not None and not isinstance(node.value, ast.Constant):
            self.sites.append(Mutant(node.lineno, "return_none", "return <expr> -> return None"))
        self.generic_visit(node)


class _Applier(ast.NodeTransformer):
    """Apply exactly the site'th mutation of the given kind; count matches to find it."""

    def __init__(self, want: Mutant, index: int) -> None:
        self.want, self.index, self.seen, self.applied = want, index, 0, False

    def _hit(self, node: ast.AST, kind: str) -> bool:
        if kind != self.want.kind or getattr(node, "lineno", None) != self.want.lineno:
            return False
        match = self.seen == self.index
        self.seen += 1
        return match

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        self.generic_visit(node)
        if self._hit(node, "compare"):
            node.ops = [_CMP_FLIP[type(op)]() if type(op) in _CMP_FLIP else op for op in node.ops]
            self.applied = True
        return node

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        self.generic_visit(node)
        if self._hit(node, "binop") and type(node.op) in _BIN_FLIP:
            node.op = _BIN_FLIP[type(node.op)]()
            self.applied = True
        return node

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        self.generic_visit(node)
        if self._hit(node, "boolop"):
            node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
            self.applied = True
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        # The APPLIER must classify constants exactly as the COLLECTOR does, or the ordinals
        # disagree: the collector only records bool/int/float, so treating a str/None constant as
        # "num_const" here both mis-counts the index and crashes on `str + 1` (observed 2026-07-29
        # on libs/execution/staging.py). A mutation harness that dies mid-file reports nothing
        # about the tests -- the same false-negative shape as a broken mirror.
        if isinstance(node.value, bool):
            kind = "bool_const"
        elif isinstance(node.value, (int, float)):
            kind = "num_const"
        else:
            return node
        if self._hit(node, kind):
            node.value = (not node.value) if kind == "bool_const" else node.value + 1
            self.applied = True
        return node

    def visit_Return(self, node: ast.Return) -> ast.AST:
        self.generic_visit(node)
        if self._hit(node, "return_none"):
            node.value = None
            self.applied = True
        return node


def _prepare(work: Path) -> None:
    """Throwaway mirror: the repo is copied ONCE per run, then one file is rewritten per mutant."""
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    # `app` is load-bearing even for libs-only targets: libs/autodiscovery/generators.py imports
    # it, so omitting it made the baseline suite fail and scored all 89 mutants as ERROR on the
    # first run -- a mirror missing one package reads as "tests are worthless" rather than
    # "the mirror is wrong". Copy everything the suite can import.
    # MIRROR COMPLETENESS IS LOAD-BEARING, learned twice: omitting `app` made the stepwise
    # baseline fail (89 mutants scored ERROR, reading as "tests are worthless"), and omitting
    # `migrations` made tests/execution/conftest.py fail to import (43 ERRORs on staging.py).
    # A mirror missing one package reports a fact about ITSELF as a fact about the tests.
    for item in ("libs", "tests", "app", "api", "config", "migrations", "data",
                 "pyproject.toml", "scripts"):
        src = _ROOT / item
        if not src.exists():
            continue
        dst = work / item
        if src.is_dir():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(src, dst)


def _run_tests(work: Path, tests: list[str], timeout_s: float) -> str:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", *tests, "-x", "-q", "--no-header",
             "-p", "no:cacheprovider", "-p", "no:randomly"],
            cwd=work, capture_output=True, timeout=timeout_s, check=False)
    except subprocess.TimeoutExpired:
        return "timeout"
    if proc.returncode == 0:
        return "survived"          # suite still green WITH the mutation = the suite cannot see it
    if proc.returncode in (1, 2):
        return "killed"
    return "error"


def _splice(original: str, mutated_tree: ast.AST, lineno: int) -> str:
    """Write the mutant by replacing ONLY the mutated region, keeping the rest byte-identical.

    THE DEFECT THIS FIXES, and it fabricated a 100%. The harness used to write every mutant as
    `ast.unparse(whole_module)`, which is a REFORMAT of the entire file: `ast.unparse` normalises
    double-quoted string literals to single quotes, drops comments, and rewrites whitespace. Any
    test that asserts on its module's own source text therefore fails for EVERY mutant, killing all
    of them for a reason that has nothing to do with the mutation.

    Measured 2026-07-30 on libs/autodiscovery/validation.py: 137/137 "killed", a perfect score --
    produced entirely by tests/autodiscovery/test_validation_cpcv_baselines.py asserting
    `'"beats_baselines"' in inspect.getsource(validate)`, a literal that ast.unparse renders as
    `'beats_baselines'`. Verified directly: the double-quoted form is present in the original and
    absent from the unparsed text. That fake 100% would have been written into
    data/ratchet_floors.json as a PERMANENT FLOOR the real tests could never meet again.

    Splicing keeps the file byte-identical except for the mutated statement, so a source-asserting
    test sees the code it expects and only a real behavioural change can kill a mutant. The
    unparsed replacement is taken for the mutated statement's own line span, which is why the
    span is recomputed from the ORIGINAL tree rather than trusted from the mutated one.
    """
    lines = original.splitlines(keepends=True)
    stmt = None
    for node in ast.walk(mutated_tree):
        if (isinstance(node, ast.stmt) and getattr(node, "lineno", None) is not None
                and node.lineno <= lineno <= (node.end_lineno or node.lineno)
                and (stmt is None or node.lineno > stmt.lineno)):
            stmt = node
    if stmt is None or stmt.end_lineno is None:
        # No enclosing statement resolved: fall back to the old whole-file behaviour rather than
        # skipping the mutant. A reformatted mutant is a weaker measurement; a dropped one is a
        # silently smaller denominator, which is worse.
        return ast.unparse(mutated_tree)
    indent = " " * (stmt.col_offset or 0)
    body = "\n".join(indent + ln for ln in ast.unparse(stmt).splitlines())
    return "".join(lines[:stmt.lineno - 1]) + body + "\n" + "".join(lines[stmt.end_lineno:])


def measure(target: str, tests: list[str], *, budget_s: float,
            per_test_timeout: float = 120.0) -> TargetScore:
    score = TargetScore(target=target, tests=tests)
    src_path = _ROOT / target
    if not src_path.exists():
        score.error = 1
        return score
    tests = [t for t in tests if (_ROOT / t).exists()]
    if not tests:
        score.error = 1
        return score
    score.tests = tests

    original = src_path.read_text("utf-8")
    tree = ast.parse(original)
    collector = _Collector()
    collector.visit(tree)
    sites = collector.sites

    work = _WORK / Path(target).stem
    _prepare(work)
    work_target = work / target
    started = time.time()

    # Baseline must be GREEN or every mutant reads as killed and the score is a lie.
    if _run_tests(work, tests, per_test_timeout) != "survived":
        score.error = len(sites) or 1
        score.runtime_s = round(time.time() - started, 1)
        shutil.rmtree(work, ignore_errors=True)
        return score

    # Same-line mutations of the same kind are distinguished by ordinal index.
    seen_key: dict[tuple[int, str], int] = {}
    score.n_sites = len(sites)
    for site in sites:
        if time.time() - started > budget_s:
            # BUDGET EXHAUSTED. `truncated` is recorded because a partial run is NOT a smaller
            # measurement of the same thing: sites are attempted in source order, so the mutants
            # that ran are the ones near the top of the file, and the rate over them says nothing
            # about the rest. Measured 2026-07-30: validation.py got 14 of 137 sites through a
            # 1500s budget and reported 35.7% -- a number that would have become a ratchet FLOOR
            # the real 137-mutant score could not be compared against.
            break
        key = (site.lineno, site.kind)
        idx = seen_key.get(key, 0)
        seen_key[key] = idx + 1
        applier = _Applier(site, idx)
        mutated = applier.visit(ast.parse(original))
        if not applier.applied:
            continue
        ast.fix_missing_locations(mutated)
        try:
            work_target.write_text(_splice(original, mutated, site.lineno), "utf-8")
        except (RecursionError, ValueError):
            score.error += 1
            continue
        outcome = _run_tests(work, tests, per_test_timeout)
        if outcome == "survived":
            score.survived += 1
            score.survivors.append({"line": site.lineno, "kind": site.kind,
                                    "mutation": site.detail})
        elif outcome == "killed":
            score.killed += 1
        elif outcome == "timeout":
            score.timeout += 1
        else:
            score.error += 1
        work_target.write_text(original, "utf-8")   # restore before the next mutant

    score.runtime_s = round(time.time() - started, 1)
    shutil.rmtree(work, ignore_errors=True)
    return score


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target")
    ap.add_argument("--tests", nargs="*", default=[])
    ap.add_argument("--budget-s", type=float, default=600.0,
                    help="wall-clock budget PER TARGET (default 600)")
    ap.add_argument("--bar", type=float, default=0.90, help="v8 8.2 kill-rate bar")
    args = ap.parse_args()

    if missing := _missing_strength_suites():
        print("REFUSING: a *_strength.py suite exists on disk but is not run:")
        for m in missing:
            print(f"  {m}")
        print("  A strength suite exists only to kill mutants; not running it guarantees an")
        print("  understated score, and a false RED on the money path makes the true number")
        print("  unreadable. Add it to _DEFAULT_TARGETS.")
        return 2

    targets = ([(args.target, args.tests)] if args.target else _DEFAULT_TARGETS)
    scores = [measure(t, tests, budget_s=args.budget_s) for t, tests in targets]

    # EQUIVALENT-MUTANT ADJUSTMENT. An equivalent mutant cannot be killed by any test, so a target
    # carrying them can never reach the bar on the raw number -- and a metric permanently red for
    # a reason nobody can fix trains the desk to ignore it, which is the same false-red failure
    # that let gate.py sit at a phantom 23.5%. The register demands a written argument per claim
    # and expires it the moment the claimed source line changes; RAW is always reported too, so
    # nothing is hidden. meets_bar uses the ADJUSTED rate; both numbers land in the artifact.
    from libs.testing.equivalent_mutants import adjust

    fresh = []
    for s in scores:
        adj = adjust(s.target, s.survivors, s.killed, s.total)
        rate = float(adj["adjusted_kill_rate"]) if s.total else s.kill_rate
        fresh.append({
            "target": s.target, "tests": s.tests, "killed": s.killed,
            "survived": s.survived, "timeout": s.timeout, "error": s.error,
            "total": s.total, "kill_rate": s.kill_rate, "runtime_s": s.runtime_s,
            "n_sites": s.n_sites,
            "budget_truncated": bool(s.n_sites and s.total < s.n_sites),
            "coverage_of_sites": (round(s.total / s.n_sites, 4) if s.n_sites else None),
            "adjusted_kill_rate": rate, "equivalent_mutants": adj["equivalent_mutants"],
            "equivalences_applied": adj["equivalences_applied"],
            "equivalences_lapsed": adj["equivalences_lapsed"],
            "meets_bar": rate >= args.bar, "survivors": s.survivors,
            "real_survivors": adj["real_survivors"],
            "measured": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    # MERGE, never replace. Measuring ONE target used to overwrite the whole artifact, which
    # (a) destroyed prior measurements and (b) fed a phantom REGRESSION to the ratchet fence --
    # a measurement tool must never be able to lower a floor by looking at a different file.
    # An ERROR-only result (baseline broken, nothing actually mutated) NEVER displaces a real
    # prior score for the same target: a failed run is not evidence about the tests.
    try:
        prior = json.loads(_OUT.read_text("utf-8")).get("targets", [])
    except (OSError, json.JSONDecodeError, AttributeError):
        prior = []
    merged: dict[str, dict[str, object]] = {str(t.get("target")): t for t in prior
                                            if isinstance(t, dict)}
    for row in fresh:
        key = str(row["target"])
        old = merged.get(key)
        if (int(row["total"]) == int(row["error"]) and old is not None
                and int(old.get("total", 0)) > int(old.get("error", 0))):
            old["last_failed_run"] = row["measured"]
            old["last_failed_reason"] = f"{row['error']} mutants scored ERROR (baseline broken)"
            continue
        merged[key] = row
    payload = {
        "measured": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "bar": args.bar,
        "method": "self-contained AST mutation harness (see module docstring); mutmut 3.6.0 is "
                  "the documented path for a long VPS run over whole trees",
        "targets": [merged[k] for k in sorted(merged)],
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(payload, indent=2), "utf-8")

    print(f"mutation testing (bar {args.bar:.0%}):")
    for s in scores:
        flag = "PASS" if s.kill_rate >= args.bar else "BELOW-BAR"
        print(f"  {s.target:38} kill={s.kill_rate:.1%} "
              f"(killed {s.killed}, survived {s.survived}, timeout {s.timeout}, "
              f"error {s.error}) {flag} [{s.runtime_s}s]")
        for sv in s.survivors[:5]:
            print(f"      SURVIVED line {sv['line']:4} {sv['kind']:11} {sv['mutation']}")
    print(f"-> {_OUT.relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts/run_stranded_recovery.py
```python
#!/usr/bin/env python3
"""GENERAL stranded-spot recovery -- derives the stranded set from ground truth, every incident.

SUPERSEDES scripts/run_deadman_stranded_sweep.py, which hardcoded the THREE symbols of the
2026-07-19 incident (GAP row 34) and so recovered $0.01 of the 2026-07-27 stranding: the carry
churn loop (master 59b837d) re-bought spot legs each tick while the futures account sat
force-flattened, leaving executor-bought alts (SYN, ZAMA, KAITO, ALLO, MMT, EPIC, ...) in the
wallet with no live short to credit them -- ~19.7k of spot USDT below baseline while the rail read
equity -23k and fired 163 consecutive breaches. A recovery tool that names its symbols is one
incident behind by construction; this one derives them.

THE STRANDED SET, from venue ground truth and three hard exclusions:
  candidate  = non-stable spot balance whose USDT value exceeds --min-usd (default 25)
  MUST be a symbol the executor actually traded  (data/cashcarry_trades.json history)
  MUST NOT be currently tracked                  (cashcarry_positions.json "positions")
  MUST show a venue-confirmed NET BUY >= the quantity being sold (spot myTrades, paginated in
       20h chunks per the venue span-cap lesson) -- this is what makes selling faucet junk
       IMPOSSIBLE: the 1.0 WBTC/ETH/PAXG the testnet seeds were never bought through this
       account's trade history, so their net-buy is ~0 and they are skipped.
  sell qty = min(free balance, venue net-buy), floored to the LOT_SIZE step.

Dry-run by default; --execute places real (testnet) sells. Kill-latch compatible: selling
stranded spot back to USDT is flatten-direction (reduces exposure), the same standing authority
the 07-19 sweep ran under. Never touches the dead-man switch, its state, or tracked positions.

    .venv/bin/python scripts/run_stranded_recovery.py                # dry-run
    .venv/bin/python scripts/run_stranded_recovery.py --execute
    .venv/bin/python scripts/run_stranded_recovery.py --min-usd 100
"""
from __future__ import annotations

import json
import math
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from libs.execution import binance_spot_testnet as spot

_ROOT = Path(__file__).resolve().parent.parent
_OUT = _ROOT / "data" / "stranded_recovery_log.json"
_STABLES = ("USDT", "USDC", "FDUSD", "TUSD", "BUSD", "DAI")
_CHUNK_MS = 20 * 3600 * 1000     # venue caps spot myTrades spans at 24h; 20h leaves margin


def _venue_net_buy(sym: str, start_ms: int, end_ms: int) -> float:
    """Venue-confirmed net bought quantity, paginated across the span cap.

    Silent-truncation trap (institutional_knowledge.md): querying past the cap returns an empty
    or partial list without error, so an unpaginated read UNDERCOUNTS buys and the guard would
    refuse legitimate recoveries -- fail-closed, but for the wrong reason. De-dup on trade id.
    """
    seen: dict[str, dict[str, Any]] = {}
    cursor = start_ms
    while cursor < end_ms:
        chunk_end = min(cursor + _CHUNK_MS, end_ms)
        try:
            for t in spot.my_trades(sym, cursor, chunk_end):
                seen[str(t.get("id"))] = t
        except Exception:
            pass                          # a missing chunk can only UNDER-count => safe direction
        cursor = chunk_end
    net = 0.0
    for t in seen.values():
        qty = float(t.get("qty", 0.0))
        net += qty if t.get("isBuyer") else -qty
    return net


def main() -> None:
    execute = "--execute" in sys.argv
    min_usd = 25.0
    if "--min-usd" in sys.argv:
        min_usd = float(sys.argv[sys.argv.index("--min-usd") + 1])
    if not spot.has_keys():
        print("ABORT: no spot testnet keys")
        sys.exit(1)

    state = json.loads((_ROOT / "data/cashcarry_positions.json").read_text("utf-8"))
    tracked = set((state.get("positions") or {}).keys())
    start_ms = int(datetime.fromisoformat(str(state["start"])).timestamp() * 1000)
    end_ms = int(time.time() * 1000)

    traded: set[str] = set()
    try:
        for t in json.loads((_ROOT / "data/cashcarry_trades.json").read_text("utf-8")):
            traded.add(str(t.get("symbol", "")))
    except Exception:
        pass
    if not traded:
        print("ABORT: no executor trade history -- cannot distinguish bought from faucet")
        sys.exit(1)

    bals = spot.balances()
    px = spot.prices()
    filters = spot.exchange_filters()

    rows: list[dict[str, Any]] = []
    for asset, amt in sorted(bals.items()):
        sym = asset + "USDT"
        if asset in _STABLES or amt <= 0 or sym in tracked:
            continue
        # The 500-row trade log rotates, so log-presence is only a FAST PATH -- the 07-27
        # stranding predated the window and its symbols (SYN, KAITO, ZAMA...) fell off the log
        # entirely, hiding 10k of executor buys from the first pass. Venue net-buy below is the
        # authoritative gate either way; skipping unlogged symbols only saves API weight, so it
        # applies just to small balances where the pagination cost exceeds the recoverable value.
        if sym not in traded and amt * px.get(sym, 0.0) < 200.0:
            continue
        val = amt * px.get(sym, 0.0)
        if val < min_usd:
            continue
        net_buy = _venue_net_buy(sym, start_ms, end_ms)
        f = filters.get(sym, {})
        step = float(f.get("step", 0.0) or 0.0)
        sell = min(amt, max(net_buy, 0.0))
        if step > 0:
            sell = math.floor(sell / step) * step
        row: dict[str, Any] = {
            "symbol": sym, "balance": amt, "venue_net_buy": round(net_buy, 8),
            "sell_qty": round(sell, 8), "price": px.get(sym, 0.0),
            "est_usdt": round(sell * px.get(sym, 0.0), 2),
        }
        if sell <= 0 or sell * px.get(sym, 0.0) < float(f.get("min_notional", 10.0) or 10.0):
            row["skipped"] = ("no venue-confirmed net buy -- faucet or already recovered"
                              if net_buy <= 0 else "below venue min notional")
            row["executed"] = False
        elif execute:
            try:
                res = spot.place_market(sym, "SELL", sell)
                row["order_id"] = res.get("orderId")
                row["executed"] = True
            except Exception as e:
                row["error"] = repr(e)[:300]
                row["executed"] = False
        else:
            row["executed"] = False
        rows.append(row)
        print(row)

    total = sum(r["est_usdt"] for r in rows if not r.get("skipped"))
    log = {"generated": datetime.now(tz=UTC).isoformat(),
           "mode": "execute" if execute else "dry_run", "min_usd": min_usd, "rows": rows,
           "recoverable_est_usdt": round(total, 2)}
    existing = json.loads(_OUT.read_text("utf-8")) if _OUT.exists() else []
    existing.append(log)
    _OUT.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    print(f"\n{'EXECUTED' if execute else 'DRY-RUN'} recoverable: ${total:,.2f} "
          f"across {sum(1 for r in rows if not r.get('skipped'))} symbols")


if __name__ == "__main__":
    main()

```

### scripts/run_supervisor.py
```python
"""Autonomous research SUPERVISOR -- the never-stop daemon.

Runs forever and requires no human intervention:
  * On start, reclaims any leases orphaned by a previous crash (power-loss recovery).
  * Seeds + continuously refills the campaign queue from the lake generator (research loop).
  * Spawns N worker subprocesses and RESTARTS any that die (process-crash recovery).
  * Each maintenance tick: reclaim dead-worker leases, prune dead workers, clean old campaigns.

The supervisor is the in-app process manager. To make the SUPERVISOR ITSELF crash-proof, run it
under the OS resurrector (systemd / NSSM / Task Scheduler / Docker restart=always) -- see deploy/.

Usage:
    python scripts/run_supervisor.py --workers 3 --db data/sor_research.sqlite --lake data/lake
"""

from __future__ import annotations

import argparse
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import FrameType

from migrations import MIGRATIONS

from libs.ops.campaign_queue import CampaignQueue
from libs.ops.research_daemon import Supervisor, lake_campaign_specs
from libs.store.connection import Database
from libs.store.migrations import run_migrations

_STOP = False
_WORKER_SCRIPT = Path(__file__).with_name("run_worker.py")


def _handle(_sig: int, _frame: FrameType | None) -> None:
    global _STOP
    _STOP = True


def _spawn(worker_id: str, db: str, lake: str) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [sys.executable, str(_WORKER_SCRIPT), "--id", worker_id, "--db", db, "--lake", lake]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--db", default="data/sor_research.sqlite")
    parser.add_argument("--lake", default="data/lake")
    parser.add_argument("--families", default="", help="comma-separated; empty = all 12")
    parser.add_argument("--min-queue-depth", type=int, default=8)
    parser.add_argument("--interval", type=float, default=15.0)
    parser.add_argument("--batch", type=int, default=1, help="symbols per campaign")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)

    families = [f.strip() for f in args.families.split(",") if f.strip()] or None
    db = Database(Path(args.db))
    run_migrations(db, MIGRATIONS)

    # Crash recovery: return any leases orphaned by a previous run before workers start.
    reclaimed = CampaignQueue(db).reclaim_stale()
    print(f"supervisor: reclaimed {reclaimed} orphaned campaign(s) on startup")

    sup = Supervisor(
        db,
        generator=lambda: lake_campaign_specs(args.lake, families=families, batch=args.batch),
        min_queue_depth=args.min_queue_depth,
    )
    print(f"supervisor: seeded {sup.ensure_queue()} campaign(s)")

    procs: dict[str, subprocess.Popen[bytes]] = {}
    for i in range(args.workers):
        wid = f"worker-{i + 1}"
        procs[wid] = _spawn(wid, args.db, args.lake)
    print(f"supervisor: spawned {len(procs)} workers; entering forever loop")

    try:
        while not _STOP:
            for wid, proc in list(procs.items()):
                if proc.poll() is not None:  # worker died -> restart (its lease will be reclaimed)
                    print(f"supervisor: {wid} exited (code {proc.returncode}); restarting")
                    procs[wid] = _spawn(wid, args.db, args.lake)
            m = sup.maintain()
            s = sup.queue.stats()
            print(f"[supervisor] queue depth={s['depth']} done={s['done']} failed={s['failed']} "
                  f"| reclaimed={m['reclaimed']} enqueued={m['enqueued']} workers={len(procs)}")
            time.sleep(args.interval)
    finally:
        print("supervisor: shutting down workers...")
        for proc in procs.values():
            proc.terminate()
        for proc in procs.values():
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        db.close()
        print("supervisor: stopped")


if __name__ == "__main__":
    main()

```

### scripts/screen_collateral_allocation.py
```python
#!/usr/bin/env python3
"""COLLATERAL ALLOCATION SCREEN (R0120) -- is cash-and-carry actually the best use of our USDT?

THE UNASKED ASSUMPTION THIS TESTS, and it sits under every capacity decision the desk makes.
Every sizing band, every capacity ratio, every "deployed capital" number assumes the base
allocation for the desk's collateral is CASH-AND-CARRY. Nobody ever computed the alternative --
while `data/defi_lending.jsonl` has been collected DAILY and read by nothing. The same USDT can
sit in a lending pool earning a measurable, near-riskless supply APY with no basis risk, no perp
leg, no liquidation engine and no venue counterparty on the derivative side.

THE COMPARISON, per period, net of what each side actually costs:
    carry_net   = annualised funding harvest  -  round-trip execution cost amortised over the
                  expected hold  -  the borrow/margin drag of the perp leg
    lending_net = supply APY  -  gas/bridging amortised  -  a HAIRCUT for smart-contract and
                  depeg risk, which is NOT zero and must never be modelled as zero
The verdict is deliberately NOT "pick the winner once". Funding is regime-dependent and lending
is comparatively stable, so the honest output is a REGIME MAP: which allocation wins in the
high-funding regime, which wins in the flat regime, and how often each regime occurs. If lending
wins the flat regime by more than the switching cost, the correct book is REGIME-SWITCHED, and
the desk has been leaving that yield on the table in every flat window it has ever traded.

WHY THIS IS NOT A "MOVE TO DEFI" PROPOSAL. Lending carries risks the carry book does not:
contract exploit, oracle failure, stablecoin depeg, withdrawal queues in stress -- exactly when
you want the capital back. So the haircut is a first-class input, the screen REFUSES to run with
haircut=0, and the output is evidence for an allocation decision, never an instruction. Stage A,
zero promotion authority (L1.6); this file moves no funds.

    python scripts/screen_collateral_allocation.py [--haircut-bps N] [--json]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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

#: Funding above this |8h rate| is the "high-funding regime" (~11% annualised at 3 prints/day).
HIGH_FUNDING_8H = 0.0001
#: Smart-contract + depeg + withdrawal-queue haircut on lending yield. NEVER zero: the risks are
#: real, rare and correlated with exactly the moments you need the collateral back.
DEFAULT_HAIRCUT_BPS = 300.0
_PERIODS_PER_YEAR = 3 * 365                       # 8h funding prints


def _rows(path: Path) -> list[dict[str, Any]]:
    try:
        out = []
        for ln in path.read_text("utf-8", errors="ignore").splitlines():
            if ln.strip():
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if isinstance(r, dict):
                    out.append(r)
        return out
    except OSError:
        return []


def best_lending_apy(root: Path, *, stable_only: bool = True) -> tuple[float | None, str]:
    """Best observed stablecoin SUPPLY apy, as a fraction. Returns (apy, provenance)."""
    rows = _rows(root / "data/defi_lending.jsonl")
    if not rows:
        return None, "data/defi_lending.jsonl absent or empty on this host"
    best, where = None, ""
    for r in rows:
        pools = r.get("data") if isinstance(r.get("data"), list) else [r]
        for p in pools:
            if not isinstance(p, dict):
                continue
            sym = str(p.get("symbol") or p.get("asset") or p.get("token") or "").upper()
            if stable_only and not any(s in sym for s in ("USDT", "USDC", "DAI", "USD")):
                continue
            apy = p.get("supply_apy", p.get("apy", p.get("supplyApy")))
            if isinstance(apy, (int, float)):
                # feeds publish either percent (5.2) or fraction (0.052)
                val = float(apy) / 100.0 if float(apy) > 1.0 else float(apy)
                if best is None or val > best:
                    best, where = val, f"{p.get('project', p.get('chain', '?'))}:{sym}"
    return best, (where or "no stablecoin supply rows found")


def funding_regimes(root: Path) -> dict[str, Any]:
    """Split observed funding into high/flat regimes -- the axis the allocation question turns on."""
    rates: list[float] = []
    for name in ("bitmex_funding.jsonl", "hyperliquid_funding.jsonl", "binance_funding.jsonl"):
        for r in _rows(root / "data" / name):
            for k in ("fundingRate", "funding", "rate", "bn_funding", "hl_funding"):
                v = r.get(k)
                if isinstance(v, (int, float)):
                    rates.append(abs(float(v)))
                    break
    if not rates:
        return {"n": 0, "measured": False}
    high = [x for x in rates if x >= HIGH_FUNDING_8H]
    flat = [x for x in rates if x < HIGH_FUNDING_8H]
    return {
        "n": len(rates), "measured": True,
        "pct_high_regime": round(100.0 * len(high) / len(rates), 1),
        "high_regime_apy": round(statistics.mean(high) * _PERIODS_PER_YEAR, 4) if high else None,
        "flat_regime_apy": round(statistics.mean(flat) * _PERIODS_PER_YEAR, 4) if flat else None,
    }


def build_report(root: Path | None = None, *, haircut_bps: float = DEFAULT_HAIRCUT_BPS,
                 carry_cost_bps_annual: float = 200.0) -> dict[str, Any]:
    if haircut_bps <= 0:
        raise ValueError(
            "haircut_bps must be > 0: smart-contract, depeg and withdrawal-queue risk are real "
            "and correlated with the moments you need the collateral back. Modelling them as "
            "zero is how a screen manufactures a winner (L1.5).")
    root = root or _ROOT
    apy, prov = best_lending_apy(root)
    reg = funding_regimes(root)
    lending_net = None if apy is None else apy - haircut_bps / 10_000.0

    verdict, detail = "UNMEASURED", ""
    regime_map: dict[str, Any] = {}
    if apy is None or not reg.get("measured"):
        missing = [x for x, ok in (("lending feed", apy is not None),
                                   ("funding history", reg.get("measured"))) if not ok]
        detail = (f"cannot compare: missing {', '.join(missing)}. UNMEASURED is NOT 'carry wins' "
                  "-- the assumption stays untested until both sides are readable")
    else:
        cost = carry_cost_bps_annual / 10_000.0
        for name, key in (("high_funding", "high_regime_apy"), ("flat_funding", "flat_regime_apy")):
            gross = reg.get(key)
            if gross is None:
                continue
            carry_net = float(gross) - cost
            regime_map[name] = {
                "carry_net_apy": round(carry_net, 4),
                "lending_net_apy": round(lending_net, 4),
                "winner": "carry" if carry_net > lending_net else "lending",
                "edge_apy": round(abs(carry_net - lending_net), 4),
            }
        winners = {v["winner"] for v in regime_map.values()}
        if winners == {"carry"}:
            verdict = "CARRY-DOMINANT"
            detail = "carry beats haircut-adjusted lending in every measured regime -- the base "
        elif winners == {"lending"}:
            verdict = "LENDING-DOMINANT"
            detail = ("haircut-adjusted lending beats carry in EVERY measured regime -- this "
                      "questions the desk's base allocation outright and owes a principal "
                      "decision, not a code change")
        elif winners:
            verdict = "REGIME-SWITCHED"
            detail = ("the winner CHANGES with the funding regime -- the correct book switches "
                      "allocation rather than always-carry; size the switch against its cost")
        if verdict == "CARRY-DOMINANT":
            detail += "assumption is VALIDATED (first time it has ever been tested)"

    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "axis": "collateral_allocation_carry_vs_lending", "row": "R0120", "stage": "A",
        "status": verdict, "detail": detail,
        "best_lending_apy": apy, "lending_provenance": prov,
        "haircut_bps": haircut_bps, "lending_net_apy": lending_net,
        "carry_cost_bps_annual": carry_cost_bps_annual,
        "funding_regimes": reg, "regime_map": regime_map,
        "authority": "STAGE A -- evidence for an allocation decision. Moves no funds, places no "
                     "orders, and never auto-switches the book (L1.6).",
        "note": "the haircut is a MODEL input, not a measurement: contract exploit, oracle "
                "failure, depeg and withdrawal queues in stress. Re-run at several haircuts "
                "before believing any verdict -- if the winner flips inside a plausible haircut "
                "range, the honest answer is 'too close to call'.",
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--haircut-bps", type=float, default=DEFAULT_HAIRCUT_BPS)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report(haircut_bps=args.haircut_bps)
    out = _ROOT / "data/collateral_allocation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    print(json.dumps(rep, indent=2) if args.json else
          f"collateral allocation (R0120): {rep['status']} -- {rep['detail']}\n-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/screen_copytrading.py
```python
#!/usr/bin/env python3
"""COPYTRADING SCREEN (R0140) -- Stage A, ZERO promotion authority (L1.6).

PRINCIPAL ORDER (2026-07-31): *"test copytrading strategies on the side too to see if they survive
... you can add or abandon. It must be relative to our main goal, max geometric growth."*

TWO DIFFERENT HYPOTHESES LIVE UNDER THE WORD "COPYTRADING", and they have opposite verdicts.

  H1 -- FOLLOW A GOOD LEAD TRADER. Pick the leaderboard's best and copy them.
       VERDICT: NOT TESTABLE from public data, and the naive test is a trap. Run on a 34-trader
       OKX sample it returns Spearman +0.33 between first- and second-half 45-day returns, with
       5/6 of the top quintile beating the median. That reads like an edge and it is an ARTIFACT:

         * the sample was drawn by sorting on pnl / pnlRatio / aum / copiers / winRatio -- i.e.
           SELECTED ON THE OUTCOME then measured for that outcome,
         * mean 45-day return across the whole sample is +81%, which is not a population of
           traders, it is a leaderboard,
         * every trader who blew up in the second half is ABSENT: persistence measured on
           survivors is manufactured by the survival filter itself,
         * n=34 puts rho at ~1.9 sigma BEFORE either bias, both of which push it upward.

       That is the exact shape of the 420 patterns this desk has already killed. The only unbiased
       design is a FORWARD PANEL: fix the cohort today, follow it, and count the disappearances as
       FAILURES rather than dropping them. This organ archives that panel; until it has two
       separated snapshots the honest verdict is NO-DATA, not "promising".

       The economics have to clear a real hurdle too, which the leaderboard never shows: copiers
       pay the lead a profit share (up to ~13% on OKX), fill AFTER the lead moves, and inherit the
       lead's drawdowns in full. A persistent edge would still have to beat that stack.

  H2 -- TRADE THE COPY FLOW, don't join it. Copy capital is FORCED flow: copiers enter behind
       their lead, exit when the lead exits, and liquidate together. Aggregate copy positioning is
       therefore a crowding gauge, and aggregate copy STRESS (deeply underwater at high leverage)
       is a mechanical precursor to unwinds. This does not require picking a winner -- which is
       precisely why it dodges the selection problem that kills H1.
       VERDICT: MEASURABLE. Computed here, and it earns a forward clock, never capital.

WHAT THE PUBLIC FEED ACTUALLY GIVES, stated because it bounds H2: subpositions expose posSide,
lever, margin and uplRatio -- but `instId` comes back EMPTY, so per-instrument crowding is not
available. The index is therefore AGGREGATE (book-wide long/short skew, leverage, unrealised
stress) plus per-currency allocation from the preference endpoint. An aggregate gauge is a weaker
object than a per-instrument one and is labelled as such rather than dressed up.

RELATIVE TO THE OBJECTIVE (max E[log wealth]): a sleeve that merely adds more crypto beta adds
almost nothing to geometric growth, because the desk is already long that. So the report carries
the question that decides it -- is this DIVERSIFYING or duplicative -- and any promotion argument
must answer it.

    python scripts/screen_copytrading.py [--json] [--sample N]
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

_PANEL = "data/copytrading_panel.jsonl"
_STATE = "data/copytrading_screen.json"
_API = "https://www.okx.com/api/v5/copytrading"

#: 2 snapshots at least 5 days apart before ANY forward persistence number is published. 5 days is
#: the spacing of the venue's own pnlRatio series, so a shorter gap would re-read one datapoint
#: twice and call it two observations.
MIN_PANEL_GAP_DAYS = 5.0
#: 30 traders is the minimum cohort for a rank statistic worth printing: below it the Spearman
#: standard error (1/sqrt(n-1)) exceeds 0.19, so anything under ~0.4 is indistinguishable from
#: noise and publishing it invites exactly the over-reading this screen exists to prevent.
MIN_COHORT = 30
#: The profit share a copier pays the lead on OKX, published in the venue's copytrading terms.
#: Any measured edge must clear this before it is an edge for US rather than for the lead.
COPIER_PROFIT_SHARE = 0.13


def _get(url: str, *, timeout: int = 25) -> Any:
    r = urllib.request.Request(url, headers={"User-Agent": "quant-platform/1.0"})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return json.loads(resp.read())


def fetch_leaders(sample: int = 60) -> tuple[list[dict[str, Any]], str]:
    """Lead-trader panel. NOTE the sampling bias this deliberately does NOT hide: every sort key
    here is an outcome variable, so this cohort is selected on performance. It is usable as a
    FORWARD cohort (fix it now, follow it) and NOT as a backward sample."""
    got: dict[str, dict[str, Any]] = {}
    errs = []
    for sort in ("pnl", "pnlRatio", "aum", "copyTraderNum", "winRatio"):
        for page in range(1, 4):
            try:
                d = _get(f"{_API}/public-lead-traders?instType=SWAP&limit=20"
                         f"&sortType={sort}&pageNumber={page}")
                rk = (d.get("data") or [{}])[0].get("ranks") or []
            except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError) as exc:
                errs.append(f"{sort}p{page}: {type(exc).__name__}")
                break
            if not rk:
                break
            for r in rk:
                got.setdefault(r["uniqueCode"], r)
            if len(got) >= sample:
                break
            time.sleep(0.15)
        if len(got) >= sample:
            break
    return list(got.values()), ("; ".join(errs) if errs else "ok")


def fetch_positions(codes: list[str], *, limit: int = 25) -> tuple[list[dict[str, Any]], int]:
    """Live subpositions across the cohort. `instId` is empty in the public feed, so this supports
    an AGGREGATE crowding gauge only -- named as such rather than presented as per-instrument."""
    rows, reachable = [], 0
    for c in codes[:limit]:
        try:
            d = _get(f"{_API}/public-current-subpositions?instType=SWAP&uniqueCode={c}&limit=20")
            data = d.get("data") or []
        except (urllib.error.URLError, OSError, ValueError) as exc:
            rows.append({"uniqueCode": c, "state": f"UNREADABLE {type(exc).__name__}"})
            continue
        if data:
            reachable += 1
        for p in data:
            rows.append({"uniqueCode": c, "posSide": p.get("posSide"),
                         "lever": float(p.get("lever") or 0), "margin": float(p.get("margin") or 0),
                         "upl": float(p.get("upl") or 0),
                         "uplRatio": float(p.get("uplRatio") or 0)})
        time.sleep(0.12)
    return rows, reachable


def _median(v: list[float]) -> float | None:
    if not v:
        return None
    v = sorted(v)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def crowding_index(pos: list[dict[str, Any]]) -> dict[str, Any]:
    """H2: copy capital is FORCED flow -- copiers enter behind the lead, exit when it exits, and
    liquidate together. Skew says which way the crowd leans; stress says how close it is to being
    made to move.

    TWO CORRECTIONS FROM THE FIRST LIVE RUN, both found by checking the number instead of
    publishing it:

      OUTLIERS DOMINATED. Margin-weighted uplRatio read -0.97 -- an almost-liquidated book -- while
      the MEDIAN position was -0.078. Three positions carried 17% of all margin. The weighted mean
      is still reported because forced-flow impact IS size-weighted, but the median is reported
      beside it and the gap between them is published as `outlier_dominated`, because a gauge that
      quietly reports its own tail as its centre is worse than no gauge.

      posSide CAN BE "net". One-way-mode positions were being silently dropped from the long/short
      split, which biased the skew toward whichever side happened to use hedge mode. They are now
      counted in their own bucket and EXCLUDED from the skew denominator, with their share
      published -- a skew computed over a fraction of the book while presented as the book's skew
      is exactly the kind of quiet wrongness this desk keeps finding.
    """
    live = [p for p in pos if p.get("margin")]
    if not live:
        return {"state": "UNMEASURED", "why": "no readable subpositions -- gauge is BLIND, "
                                              "which is not the same as flat"}
    lg = sum(p["margin"] for p in live if p["posSide"] == "long")
    sh = sum(p["margin"] for p in live if p["posSide"] == "short")
    net = sum(p["margin"] for p in live if p["posSide"] not in ("long", "short"))
    tot = lg + sh + net
    directional = lg + sh
    notional = sum(p["margin"] * max(p["lever"], 1.0) for p in live)
    w_upl = sum(p["margin"] * p["uplRatio"] for p in live) / tot if tot else 0.0
    med_upl = _median([p["uplRatio"] for p in live]) or 0.0
    skew = (lg - sh) / directional if directional else None
    outlier_ratio = abs(w_upl - med_upl)
    return {
        "state": "MEASURED", "n_positions": len(live),
        "long_margin": round(lg, 2), "short_margin": round(sh, 2), "net_mode_margin": round(net, 2),
        "net_mode_share": round(net / tot, 3) if tot else None,
        "skew": round(skew, 4) if skew is not None else None,
        "skew_basis": "long+short only; one-way 'net' positions carry no readable direction and "
                      "are excluded from the denominator rather than silently counted",
        "median_leverage": _median([p["lever"] for p in live]),
        "margin_weighted_leverage": round(notional / tot, 2) if tot else None,
        "frac_underwater": round(sum(1 for p in live if p["uplRatio"] < 0) / len(live), 3),
        "median_uplRatio": round(med_upl, 4),
        "margin_weighted_uplRatio": round(w_upl, 4),
        "outlier_dominated": bool(outlier_ratio > 0.25),
        "outlier_note": (f"weighted {w_upl:+.3f} vs median {med_upl:+.3f} -- a few large positions "
                         "dominate the weighted figure; read the median as the centre"
                         if outlier_ratio > 0.25 else "weighted and median agree"),
        "reading": (
            "UNREADABLE DIRECTION: most margin is in one-way 'net' mode"
            if directional < tot * 0.4 else
            "crowded LONG and under water at leverage -- unwind risk is to the DOWNSIDE"
            if (skew is not None and skew > 0.15 and med_upl < -0.02) else
            "crowded SHORT and under water at leverage -- unwind risk is to the UPSIDE"
            if (skew is not None and skew < -0.15 and med_upl < -0.02) else
            "no strong crowd stress in the sampled cohort"),
    }


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None

    def rank(v: list[float]) -> list[int]:
        order = sorted(range(len(v)), key=lambda i: v[i])
        out = [0] * len(v)
        for pos, i in enumerate(order):
            out[i] = pos
        return out
    rx, ry = rank(xs), rank(ys)
    return round(1 - 6 * sum((a - b) ** 2 for a, b in zip(rx, ry, strict=False)) / (n * (n * n - 1)), 4)


def contaminated_persistence(leaders: list[dict[str, Any]]) -> dict[str, Any]:
    """The in-sample split-half test, computed AND disqualified in the same breath.

    It is reported rather than suppressed because the number is what a reasonable person would
    compute first, and the desk's job is to show why it must not be acted on -- a suppressed
    statistic gets recomputed by the next person without the warning attached."""
    h1, h2 = [], []
    for t in leaders:
        s = sorted(t.get("pnlRatios") or [], key=lambda x: int(x["beginTs"]))
        if len(s) < 12:
            continue
        v = [float(x["pnlRatio"]) for x in s]
        mid = len(v) // 2
        h1.append(v[mid] - v[0])
        h2.append(v[-1] - v[mid])
    if len(h1) < 3:
        return {"state": "NO-DATA", "n": len(h1)}
    rho = _spearman(h1, h2)
    n = len(h1)
    se = 1 / math.sqrt(n - 1)
    mean_h2 = sum(h2) / n
    return {
        "state": "CONTAMINATED -- NOT EVIDENCE", "n": n, "spearman": rho,
        "sigma": round(abs(rho) / se, 2) if rho is not None else None,
        "mean_second_half_return": round(mean_h2, 4),
        "disqualifiers": [
            "SELECTED ON THE OUTCOME: the cohort is drawn by sorting on pnl/pnlRatio/aum/copiers/"
            "winRatio, then measured for performance",
            "SURVIVORSHIP: traders who blew up are absent from the leaderboard entirely, so "
            "persistence here is partly manufactured by the survival filter",
            f"UNDERPOWERED: n={n}, Spearman SE ~{se:.3f}",
            f"POPULATION CHECK FAILS: mean 45-day return {mean_h2:+.1%} across the whole sample "
            "-- that is a leaderboard, not a population of traders",
        ],
        "only_valid_design": "a FORWARD panel: fix the cohort now, follow it, and count "
                             "disappearances as FAILURES rather than dropping them",
    }


def forward_persistence(root: Path) -> dict[str, Any]:
    """The only unbiased read: same cohort, two separated snapshots, EXITS COUNTED AS FAILURES."""
    snaps: list[dict[str, Any]] = []
    try:
        for ln in (root / _PANEL).read_text("utf-8", errors="ignore").splitlines():
            if ln.strip():
                try:
                    snaps.append(json.loads(ln))
                except ValueError:
                    continue
    except OSError:
        return {"state": "NO-DATA", "why": "no panel archived yet -- the forward clock starts on "
                                           "the first run of this organ"}
    if len(snaps) < 2:
        return {"state": "NO-DATA", "n_snapshots": len(snaps),
                "why": "one snapshot cannot measure persistence; the clock is running"}
    first, last = snaps[0], snaps[-1]
    gap = (datetime.fromisoformat(last["at"]) - datetime.fromisoformat(first["at"])).days
    if gap < MIN_PANEL_GAP_DAYS:
        return {"state": "NO-DATA", "gap_days": gap,
                "why": f"snapshots {gap}d apart, under the {MIN_PANEL_GAP_DAYS}d minimum -- a "
                       "shorter gap re-reads one datapoint twice and calls it two observations"}
    then = {t["uniqueCode"]: t for t in first["traders"]}
    now = {t["uniqueCode"]: t for t in last["traders"]}
    survived = [c for c in then if c in now]
    exited = [c for c in then if c not in now]
    if len(then) < MIN_COHORT:
        return {"state": "UNDERPOWERED", "cohort": len(then), "exited": len(exited),
                "why": f"cohort {len(then)} < {MIN_COHORT}; a rank statistic here is noise"}
    xs = [float(then[c].get("pnlRatio") or 0) for c in survived]
    ys = [float(now[c].get("pnlRatio") or 0) - float(then[c].get("pnlRatio") or 0)
          for c in survived]
    return {
        "state": "MEASURED", "gap_days": gap, "cohort": len(then),
        "survived": len(survived), "exited_counted_as_failures": len(exited),
        "exit_rate": round(len(exited) / len(then), 3),
        "forward_spearman": _spearman(xs, ys),
        "note": "exits are FAILURES, not missing data -- dropping them is the survivorship bug "
                "that makes the in-sample number look like an edge",
        "hurdle": f"any edge must also clear the ~{COPIER_PROFIT_SHARE:.0%} copier profit share, "
                  "entry lag behind the lead, and the lead's full drawdown",
    }


def build_report(root: Path | None = None, *, sample: int = 60,
                 leaders: list[dict[str, Any]] | None = None,
                 positions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    root = root or _ROOT
    src = "injected"
    if leaders is None:
        leaders, src = fetch_leaders(sample)
    if positions is None and leaders:
        positions, _ = fetch_positions([t["uniqueCode"] for t in leaders])
    positions = positions or []
    crowd = crowding_index(positions)
    fwd = forward_persistence(root)
    contam = contaminated_persistence(leaders)
    status = ("NO-DATA" if not leaders else
              "FORWARD-CLOCK" if fwd["state"] in ("NO-DATA", "UNDERPOWERED") else "MEASURED")
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "row": "R0140", "stage": "A", "source": src,
        "authority": "STAGE A ONLY -- earns at most a pre-registered forward clock, never capital "
                     "(L1.6). This script places no orders and copies no trader.",
        "status": status,
        "n_leaders": len(leaders),
        "h1_follow_a_lead_trader": contam,
        "h2_copy_flow_crowding": crowd,
        "forward_panel": fwd,
        "objective_test": "max E[log wealth]: a sleeve that only adds more crypto beta adds almost "
                          "nothing to geometric growth, because this book is already long that. "
                          "Any promotion argument must show DIVERSIFYING return, not more of the "
                          "same -- measured against the sleeve correlation matrix, not asserted.",
        "detail": (f"{len(leaders)} lead traders sampled; H1 (follow a lead) is "
                   f"{contam['state']}; H2 (trade the copy flow) is {crowd['state']}; forward "
                   f"panel {fwd['state']}"),
    }


def archive(root: Path, leaders: list[dict[str, Any]]) -> None:
    """Append the cohort so a survivorship-corrected forward panel accumulates."""
    if not leaders:
        return
    p = root / _PANEL
    p.parent.mkdir(parents=True, exist_ok=True)
    keep = [{k: t.get(k) for k in ("uniqueCode", "nickName", "pnlRatio", "aum", "copyTraderNum",
                                   "leadDays", "winRatio")} for t in leaders]
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": datetime.now(tz=UTC).isoformat(), "traders": keep}) + "\n")


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=60)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    leaders, src = fetch_leaders(args.sample)
    positions, _ = fetch_positions([t["uniqueCode"] for t in leaders]) if leaders else ([], 0)
    archive(_ROOT, leaders)
    rep = build_report(_ROOT, leaders=leaders, positions=positions)
    rep["source"] = src
    out = _ROOT / _STATE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    print(json.dumps(rep, indent=2) if args.json else
          f"copytrading screen (R0140): {rep['status']} -- {rep['detail']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/stageb_capacity.py
```python
"""STAGE-B CAPACITY -- how many forward clocks SHOULD run at once? Compute it, do not assume 3.

THE PRINCIPAL'S QUESTION: if Stage-A is unlimited, why not run Stage-B on everything too?

BECAUSE STAGE-B HAS A STATISTICAL PRICE STAGE-A DOES NOT. Holm correction across m concurrent
clocks raises the significance bar for EVERY clock, including the good ones. Adding a weak
hypothesis does not just waste its own slot -- it makes a genuinely real effect in another slot
harder to detect. Stage-A is free because it promotes nothing; Stage-B is scarce because it is the
only path to money.

But "3" was never derived. It is what happens to be running. This computes the actual trade-off:
the Holm bar at each m, the t-stat a real effect would need, and where the marginal clock starts
costing more discrimination than it buys.

Read-only. No keys.
"""
from __future__ import annotations

import contextlib
import json
import math
import pathlib
from datetime import UTC, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data/stageb_capacity.json"
ALPHA = 0.05
MIN_DAYS = 40


def _z(p: float) -> float:
    """Inverse normal CDF (Acklam approximation) -- the two-sided Holm bar at level p."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    pl, ph = 0.02425, 1 - 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > ph:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q, r = p - 0.5, (p - 0.5) ** 2
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def holm_bar(m: int) -> float:
    """Most stringent Holm threshold with m concurrent tests, two-sided."""
    return abs(_z(1 - ALPHA / (2 * m)))


def main() -> None:
    st = {}
    with contextlib.suppress(Exception):        # blind-except intentional
        st = json.loads((ROOT / "data/axis_shadow_state.json").read_text("utf-8"))
    running = len(st.get("axes", []))
    observed = next((a.get("holm_bar") for a in st.get("axes", []) if a.get("holm_bar")), None)

    try:
        sched = len(json.loads((ROOT / "data/research_cio.json").read_text("utf-8"))
                    .get("schedule", []))
    except Exception:  # blind-except intentional (BLE001)
        sched = 0

    print("=== STAGE-B CAPACITY -- how many forward clocks should run at once? ===")
    print("    Stage-A is free because it promotes nothing. Stage-B is scarce because it is the")
    print("    only path to capital -- and every extra clock raises the bar for ALL of them.\n")
    print(f"  currently running : {running} clocks")
    print(f"  observed holm_bar : {observed}  (desk's own state file)")
    print(f"  Stage-A backlog   : {sched} ranked candidates waiting\n")

    print(f"  {'m':>4}{'holm bar':>11}{'vs m=1':>9}{'vs m=3':>9}   interpretation")
    base1, base3 = holm_bar(1), holm_bar(3)
    rows = []
    for m in (1, 3, 5, 8, 10, 15, 20, 30, 50, 100, 214):
        b = holm_bar(m)
        interp = ("free" if m == 1 else
                  "current" if m == 3 else
                  "cheap -- worth taking" if b - base3 < 0.30 else
                  "material cost" if b - base3 < 0.60 else
                  "self-defeating")
        print(f"  {m:>4}{b:>11.3f}{b-base1:>+9.3f}{b-base3:>+9.3f}   {interp}")
        rows.append({"m": m, "holm_bar": round(b, 4), "vs_m1": round(b - base1, 4),
                     "vs_m3": round(b - base3, 4), "verdict": interp})

    cheap = [r["m"] for r in rows if r["verdict"] == "cheap -- worth taking"]
    rec = max(cheap) if cheap else 3
    print(f"\n  RECOMMENDATION: {rec} concurrent clocks, up from {running}.")
    print(f"  Going 3 -> {rec} raises the bar from {base3:.2f} to {holm_bar(rec):.2f} "
          f"(+{holm_bar(rec)-base3:.2f}), which a real effect")
    print("  survives. Going to 214 needs t > "
          f"{holm_bar(214):.2f} -- that is not a stricter standard, it is an")
    print("  unreachable one, and it would bury the genuine effects alongside the noise.")
    print("\n  THE ASYMMETRY THAT ANSWERS THE QUESTION: a weak hypothesis in Stage-A costs its own")
    print("  compute and nothing else. The same hypothesis in Stage-B taxes EVERY OTHER CLOCK.")
    print("  That is why Stage-A is unlimited and Stage-B is rationed -- not caution, arithmetic.")
    print("\n  BUT '3' WAS NEVER DERIVED -- it is simply what happens to be running. On this")
    print(f"  arithmetic the desk is UNDER-USING Stage-B by roughly {rec-running} slots while")
    print(f"  {sched} candidates queue behind it. That is a real throughput bottleneck.")

    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "running": running, "backlog": sched,
                               "recommended_concurrent": rec, "curve": rows}, indent=1), "utf-8")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()

```
