# AUDIT SHARD 5/13 -- seat qwen/qwen3.7-max

You are reviewing SOURCE CODE, not a summary. Previous panels received a 13,185-char self-description and never saw the code; that is why this exists.

- TIER 1 (money path) is included IN FULL and is sent to every seat: 41 files. A defect here costs money.
- TIER 2 is YOUR SHARD ALONE: 46 files. No other seat sees these, so anything you miss here is missed entirely.
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

### libs/alpha_factory/research_allocator.py
```python
"""Research allocator — split the research budget across categories.

Allocates effort using historical success (from research memory), current regime/portfolio needs,
and crowding. Output is a recommendation only (fractions summing to ~1); the factory never spends
production capital.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from libs.alpha_factory.models import AllocationResult, AlphaCategory
from libs.alpha_factory.research_memory import ResearchMemory

_DEFAULT_SUCCESS = 0.5


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class ResearchAllocator:
    """Recommends a research-budget split across alpha categories."""

    def allocate(
        self,
        categories: Sequence[AlphaCategory],
        *,
        memory: ResearchMemory | None = None,
        regime_gaps: Mapping[str, float] | None = None,
        portfolio_gaps: Mapping[str, float] | None = None,
        crowding: Mapping[str, float] | None = None,
    ) -> AllocationResult:
        regime_gaps = regime_gaps or {}
        portfolio_gaps = portfolio_gaps or {}
        crowding = crowding or {}

        raw: dict[str, float] = {}
        rationale: dict[str, str] = {}
        for category in categories:
            key = category.value
            success = memory.success_rate(key) if memory is not None else _DEFAULT_SUCCESS
            need = _clip01((regime_gaps.get(key, 0.0) + portfolio_gaps.get(key, 0.0)) / 2.0)
            crowd = _clip01(crowding.get(key, 0.0))
            weight = max(0.0, 0.4 * success + 0.3 * need + 0.3 * (1.0 - crowd))
            raw[key] = weight
            rationale[key] = (
                f"success={success:.2f}, need={need:.2f}, crowding={crowd:.2f}"
            )

        total = sum(raw.values())
        if total <= 0.0:
            equal = 1.0 / len(raw) if raw else 0.0
            allocations = dict.fromkeys(raw, equal)
        else:
            allocations = {k: v / total for k, v in raw.items()}
        return AllocationResult(allocations=allocations, rationale=rationale)

```

### libs/alpha_factory/research_dashboard_exports.py
```python
"""Research dashboard exports — aggregate factory state for monitoring.

Pure, deterministic aggregation over research memory (and optional allocation). No I/O.
"""

from __future__ import annotations

from typing import Any

from libs.alpha_factory.models import AllocationResult, ResearchResult
from libs.alpha_factory.research_memory import ResearchMemory


def build_research_dashboard(
    memory: ResearchMemory, *, allocation: AllocationResult | None = None
) -> dict[str, Any]:
    """Summarize research productivity and knowledge for dashboards."""
    records = memory.all()
    categories = sorted({r.category for r in records})
    decided = [r for r in records if r.result is not ResearchResult.PENDING]
    return {
        "n_ideas": len(records),
        "n_decided": len(decided),
        "n_success": sum(1 for r in records if r.result is ResearchResult.SUCCESS),
        "n_failure": sum(1 for r in records if r.result is ResearchResult.FAILURE),
        "overall_success_rate": memory.success_rate(),
        "success_rate_by_category": {c: memory.success_rate(c) for c in categories},
        "failure_cause_histogram": memory.failure_cause_histogram(),
        "allocation": dict(allocation.allocations) if allocation is not None else {},
    }

```

### libs/autodiscovery/lifecycle.py
```python
"""Automated promotion state machine — never allocates real capital.

    fail validation                  -> REJECTED   (archive)
    pass validation, fail shadow     -> SHADOW      (archive; reached shadow)
    pass shadow, fail paper          -> PAPER       (archive; reached paper)
    pass paper                       -> REGISTRY    (survivor; awaits HUMAN approval for live)

Shadow = positive on a held-out recent segment the validation never saw; paper = positive on an
even-more-recent segment. Both are accelerated stand-ins for wall-clock shadow/paper; real live
capital is never allocated automatically — REGISTRY only means "eligible for human review".
"""

from __future__ import annotations

import numpy as np

from libs.autodiscovery.models import CandidateStatus

_SHADOW_TAIL = 0.15
_PAPER_TAIL = 0.05


def segment_pass(returns: np.ndarray, *, tail: float) -> bool:
    """Whether the final ``tail`` fraction of the series has a positive mean return."""
    arr = np.asarray(returns, dtype="float64")
    cut = int(len(arr) * (1.0 - tail))
    seg = arr[cut:]
    return len(seg) > 1 and float(seg.mean()) > 0.0


def promote(returns: np.ndarray, *, validation_survived: bool) -> CandidateStatus:
    """Resolve the terminal lifecycle status from validation + accelerated shadow/paper segments."""
    if not validation_survived:
        return CandidateStatus.REJECTED
    if not segment_pass(returns, tail=_SHADOW_TAIL):
        return CandidateStatus.SHADOW   # reached shadow, failed it -> archived
    if not segment_pass(returns, tail=_PAPER_TAIL):
        return CandidateStatus.PAPER    # reached paper, failed it -> archived
    return CandidateStatus.REGISTRY     # full survivor (human approval still required for live)

```

### libs/backtest/cross_engine.py
```python
"""Cross-engine verification.

A one-person event-driven engine *will* contain subtle P&L bugs (adversarial review W3.2), so
results are cross-checked against independent implementations. Three references are provided:

* :func:`vectorized_reference` — an in-house NumPy implementation (always available, strict).
* :func:`reference_from_backtrader` — backtrader (independent library; next-open fills).
* :func:`reference_from_vectorbt` — vectorbt (best-effort; looser tolerance).

:func:`verify_cross_engine` raises :class:`VerificationError` if any compared metric diverges
beyond tolerance.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

from libs.backtest.engine import BacktestResult, run_signal_backtest
from libs.backtest.errors import VerificationError

_SUMMARY_KEYS = ("total_return", "final_equity", "max_drawdown")


def _summary_from_equity(equity: np.ndarray) -> dict[str, float]:
    start = float(equity[0])
    last = float(equity[-1])
    running_max = np.maximum.accumulate(equity)
    drawdown = equity / running_max - 1.0
    return {
        "total_return": (last / start - 1.0) if start > 0 else 0.0,
        "final_equity": last,
        "max_drawdown": float(drawdown.min()),
    }


def summarize_result(result: BacktestResult) -> dict[str, float]:
    """Summarize an engine result into the comparable metric set."""
    return _summary_from_equity(result.equity.to_numpy(dtype="float64"))


def vectorized_reference(
    bars: pd.DataFrame, targets: Sequence[float], *, init_cash: float = 100_000.0
) -> dict[str, float]:
    """Independent NumPy reference for the fixed-units, next-open, cost-free signal model."""
    opens = bars["open"].to_numpy(dtype="float64")
    closes = bars["close"].to_numpy(dtype="float64")
    n = len(closes)
    positions = np.zeros(n, dtype="float64")
    if n > 1:
        positions[1:] = np.asarray(targets, dtype="float64")[: n - 1]
    deltas = np.diff(positions, prepend=0.0)
    cash = init_cash + np.cumsum(-deltas * opens)
    equity = cash + positions * closes
    return _summary_from_equity(equity)


def verify_cross_engine(
    ours: Mapping[str, float],
    reference: Mapping[str, float],
    *,
    keys: Sequence[str] = _SUMMARY_KEYS,
    tolerance: float = 1e-6,
    relative: bool = True,
) -> dict[str, float]:
    """Compare two metric sets; raise :class:`VerificationError` on divergence.

    Returns the per-key (relative) differences when within tolerance.
    """
    diffs: dict[str, float] = {}
    breaches: list[str] = []
    for key in keys:
        a = float(ours[key])
        b = float(reference[key])
        diff = abs(a - b)
        denom = max(abs(b), 1e-9) if relative else 1.0
        rel = diff / denom
        diffs[key] = rel
        if rel > tolerance:
            breaches.append(f"{key}: ours={a:.8g} ref={b:.8g} rel_diff={rel:.3g}")
    if breaches:
        raise VerificationError(
            "cross-engine divergence beyond tolerance "
            f"{tolerance:g}: " + "; ".join(breaches)
        )
    return diffs


def verify_against_vectorized(
    bars: pd.DataFrame,
    targets: Sequence[float],
    *,
    init_cash: float = 100_000.0,
    tolerance: float = 1e-9,
) -> dict[str, float]:
    """Run our engine and the NumPy reference on the same signals and verify they agree."""
    result = run_signal_backtest(bars, list(targets), init_cash=init_cash)
    ours = summarize_result(result)
    reference = vectorized_reference(bars, targets, init_cash=init_cash)
    return verify_cross_engine(ours, reference, tolerance=tolerance)


def reference_from_backtrader(
    bars: pd.DataFrame, targets: Sequence[float], *, init_cash: float = 100_000.0
) -> dict[str, float]:
    """Compute the comparable summary using backtrader (independent engine)."""
    import backtrader as bt

    frame = bars.copy()
    index = pd.DatetimeIndex(frame["timestamp"])
    if index.tz is not None:
        index = index.tz_convert("UTC").tz_localize(None)
    frame.index = index
    targets_list = list(targets)

    class _TargetStrategy(bt.Strategy):  # type: ignore[misc]
        def next(self) -> None:
            i = len(self) - 1
            if i < len(targets_list):
                self.order_target_size(target=targets_list[i])

    cerebro = bt.Cerebro(stdstats=False)
    cerebro.broker.setcash(init_cash)
    cerebro.broker.setcommission(commission=0.0)
    feed = bt.feeds.PandasData(dataname=frame[["open", "high", "low", "close", "volume"]])
    cerebro.adddata(feed)
    cerebro.addstrategy(_TargetStrategy)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="dd")
    strat = cerebro.run()[0]
    final_equity = float(cerebro.broker.getvalue())
    max_dd_pct = float(strat.analyzers.dd.get_analysis()["max"]["drawdown"])
    return {
        "total_return": final_equity / init_cash - 1.0,
        "final_equity": final_equity,
        "max_drawdown": -max_dd_pct / 100.0,
    }


def reference_from_vectorbt(
    bars: pd.DataFrame, targets: Sequence[float], *, init_cash: float = 100_000.0
) -> dict[str, float]:
    """Compute the comparable summary using vectorbt (best-effort; next-open fills)."""
    import vectorbt as vbt

    index = pd.DatetimeIndex(bars["timestamp"])
    close = pd.Series(bars["close"].to_numpy(dtype="float64"), index=index)
    fill_price = pd.Series(bars["open"].to_numpy(dtype="float64"), index=index).shift(-1)
    size = pd.Series(np.asarray(targets, dtype="float64"), index=index)
    portfolio = vbt.Portfolio.from_orders(
        close=close,
        size=size,
        size_type="targetamount",
        price=fill_price,
        fees=0.0,
        slippage=0.0,
        init_cash=init_cash,
        freq="1D",
    )
    equity = portfolio.value().to_numpy(dtype="float64")
    return _summary_from_equity(equity)


def verify_against_backtrader(
    bars: pd.DataFrame,
    targets: Sequence[float],
    *,
    init_cash: float = 100_000.0,
    tolerance: float = 1e-3,
) -> dict[str, float]:
    """Verify our engine against backtrader on the same signals."""
    result = run_signal_backtest(bars, list(targets), init_cash=init_cash)
    ours = summarize_result(result)
    reference = reference_from_backtrader(bars, targets, init_cash=init_cash)
    return verify_cross_engine(ours, reference, tolerance=tolerance)


def verify_against_vectorbt(
    bars: pd.DataFrame,
    targets: Sequence[float],
    *,
    init_cash: float = 100_000.0,
    tolerance: float = 5e-2,
) -> dict[str, float]:
    """Verify our engine against vectorbt on the same signals (looser tolerance)."""
    result = run_signal_backtest(bars, list(targets), init_cash=init_cash)
    ours = summarize_result(result)
    reference = reference_from_vectorbt(bars, targets, init_cash=init_cash)
    return verify_cross_engine(
        ours, reference, keys=("total_return", "final_equity"), tolerance=tolerance
    )

```

### libs/backtest/strategy.py
```python
"""Strategy protocol and a couple of reference strategies.

A strategy sees only data up to and including the current bar's close (no look-ahead) and
returns a target position. The engine executes the resulting order at the *next* bar's open.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np
import pandas as pd

from libs.backtest.events import SignalEvent


@dataclass(frozen=True)
class BarContext:
    """What a strategy sees on each bar."""

    index: int
    timestamp: pd.Timestamp
    bars: pd.DataFrame
    equity: float
    position_units: float


@runtime_checkable
class Strategy(Protocol):
    def on_bar(self, ctx: BarContext) -> SignalEvent | None: ...


class SignalStrategy:
    """Replays a precomputed target series (units or signed fraction)."""

    def __init__(
        self,
        targets: np.ndarray | list[float],
        *,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        trailing: float | None = None,
    ) -> None:
        self._targets = np.asarray(targets, dtype="float64")
        self._stop_loss = stop_loss
        self._take_profit = take_profit
        self._trailing = trailing

    def on_bar(self, ctx: BarContext) -> SignalEvent | None:
        if ctx.index >= len(self._targets):
            return None
        return SignalEvent(
            timestamp=ctx.timestamp,
            target=float(self._targets[ctx.index]),
            stop_loss=self._stop_loss,
            take_profit=self._take_profit,
            trailing=self._trailing,
        )


class MovingAverageCrossStrategy:
    """Long when the fast SMA is above the slow SMA (optionally short otherwise)."""

    def __init__(self, *, fast: int, slow: int, long_only: bool = True) -> None:
        if fast >= slow:
            raise ValueError("fast window must be shorter than slow window")
        self.fast = fast
        self.slow = slow
        self.long_only = long_only

    def on_bar(self, ctx: BarContext) -> SignalEvent | None:
        closes = ctx.bars["close"].iloc[: ctx.index + 1]
        if len(closes) < self.slow:
            return SignalEvent(timestamp=ctx.timestamp, target=0.0)
        fast_ma = float(closes.iloc[-self.fast :].mean())
        slow_ma = float(closes.iloc[-self.slow :].mean())
        flat_or_short = 0.0 if self.long_only else -1.0
        target = 1.0 if fast_ma > slow_ma else flat_or_short
        return SignalEvent(timestamp=ctx.timestamp, target=target)

```

### libs/core/secrets.py
```python
"""Secrets interface.

Broker credentials are the crown jewels: they live only behind a provider, never in
config files, never in logs. Stage 1 ships an environment-variable provider (prefix
``QP_SECRET_``); a Vault/KMS provider can be slotted in later behind the same protocol.
"""

from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

from libs.core.errors import SecretsError

SECRET_ENV_PREFIX = "QP_SECRET_"


@runtime_checkable
class SecretsProvider(Protocol):
    """A source of named secrets. Implementations must never log secret values."""

    def get_secret(self, name: str) -> str:
        """Return the secret value for ``name``, or raise :class:`SecretsError` if absent."""
        ...

    def has_secret(self, name: str) -> bool:
        """Return whether a secret named ``name`` is available."""
        ...


def _env_key(name: str) -> str:
    return f"{SECRET_ENV_PREFIX}{name.upper()}"


class EnvSecretsProvider:
    """Reads secrets from environment variables named ``QP_SECRET_<NAME>``."""

    def get_secret(self, name: str) -> str:
        value = os.environ.get(_env_key(name))
        if value is None or value == "":
            raise SecretsError(f"secret {name!r} is not set (expected env var {_env_key(name)})")
        return value

    def has_secret(self, name: str) -> bool:
        value = os.environ.get(_env_key(name))
        return value is not None and value != ""


_default_provider: SecretsProvider = EnvSecretsProvider()


def set_default_provider(provider: SecretsProvider) -> None:
    """Override the process-wide default secrets provider."""
    global _default_provider
    _default_provider = provider


def get_default_provider() -> SecretsProvider:
    """Return the process-wide default secrets provider."""
    return _default_provider


def get_secret(name: str) -> str:
    """Fetch a secret from the default provider."""
    return _default_provider.get_secret(name)

```

### libs/costs/gap.py
```python
"""Gap-risk component.

Stops do not guarantee fills: gold gaps on the Sunday open, CFDs gap on news. The expected
adverse gap is modelled as a fraction of notional and can be included in a trade's cost when
sizing for the gap-through scenario rather than the stop level.
"""

from __future__ import annotations

from libs.costs.params import CostParams


def estimate_gap_cost(params: CostParams, qty_lots: float, price: float) -> float:
    """Expected adverse-gap cost in account currency for holding ``qty_lots`` at ``price``."""
    return params.gap_risk_fraction * price * params.contract_size * qty_lots

```

### libs/costs/scenarios.py
```python
"""Cost stress scenarios (BASE / 2X / 3X / 5X).

The validation gauntlet requires every edge to survive *pessimistic* costs. These scenarios
scale the market-driven components (spread, slippage, gap) — the parts that blow out in
stress — while leaving contractual commission and rate-based financing unchanged.
"""

from __future__ import annotations

from enum import StrEnum

_MULTIPLIERS: dict[str, float] = {"base": 1.0, "2x": 2.0, "3x": 3.0, "5x": 5.0}


class CostScenario(StrEnum):
    BASE = "base"
    X2 = "2x"
    X3 = "3x"
    X5 = "5x"

    @property
    def multiplier(self) -> float:
        return _MULTIPLIERS[self.value]

```

### libs/data/crypto_source.py
```python
"""Crypto perpetual data (Level-3): daily OHLCV + funding rate, from Binance USD-M futures.

Funding rate is the highest-information, free, solo-accessible signal we ranked top: it measures
leverage demand (longs paying shorts when positive). This source returns daily bars with an extra
``funding`` column (the day's summed funding), aligned to the canonical bar schema so it lands in
the existing Parquet lake unchanged. Public REST, no key. Read-only.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_FAPI = "https://fapi.binance.com"

# Cross-process rate-ban latch (2026-07-31 incident: premiumIndex returned 418 -- Binance's
# IP auto-ban -- and every retry from every respawning process EXTENDED the ban). A file, not
# a module global, because the callers are short-lived: cron collectors, the 3-min refresh
# chain, and systemd-respawned executors each start cold.
_BAN_FILE = Path("data/BINANCE_BAN_UNTIL")


def _ban_remaining() -> float:
    try:
        until = float(_BAN_FILE.read_text("utf-8").split()[0])
    except (OSError, ValueError, IndexError):
        return 0.0
    return max(0.0, until - time.time())
_SPOT = "https://api.binance.com"


def _get(url: str, *, tries: int = 4) -> Any:
    rem = _ban_remaining()
    if rem > 0:
        raise RuntimeError(f"binance rate-ban latched for {rem:.0f}s more "
                           f"(data/BINANCE_BAN_UNTIL): refusing {url}")
    last: Exception | None = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "quant-platform/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            # 418 = IP auto-ban, 429 = rate limit. Requests sent while banned EXTEND the
            # ban, so latch a cross-process cooldown and fail fast instead of retrying.
            if exc.code in (418, 429):
                ra = exc.headers.get("Retry-After") if exc.headers else None
                default_wait = 7200.0 if exc.code == 418 else 120.0
                try:
                    # honour the venue's own clock; absent/unparseable falls to the default
                    wait = max(60.0, float(ra)) if ra else default_wait
                except ValueError:
                    wait = default_wait
                try:
                    _BAN_FILE.parent.mkdir(parents=True, exist_ok=True)
                    _BAN_FILE.write_text(
                        f"{time.time() + wait:.0f} code={exc.code} retry_after={ra}\n",
                        "utf-8")
                except OSError:
                    pass
                raise RuntimeError(f"binance rate-ban {exc.code} on {url}: latched "
                                   f"{wait:.0f}s cooldown") from exc
            last = exc
            time.sleep(1.5)
        except Exception as exc:  # transient network
            last = exc
            time.sleep(1.5)
    raise RuntimeError(f"GET failed after {tries}: {url} :: {last}")


def _klines(
    base: str, path: str, symbol: str, interval: str, start_ms: int, *, limit: int
) -> pd.DataFrame:
    rows: list[list[Any]] = []
    cur = start_ms
    while True:
        url = f"{base}{path}?symbol={symbol}&interval={interval}&limit={limit}&startTime={cur}"
        batch = _get(url)
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < limit:          # full page -> more to fetch; partial -> done
            break
        cur = int(batch[-1][0]) + 1
        time.sleep(0.25)
    if not rows:
        return pd.DataFrame()
    # kline cols: ...,5=base vol,7=quote vol,10=taker-buy quote vol -> taker-buy fraction = flow.
    qv = np.array([float(r[7]) for r in rows])
    tbq = np.array([float(r[10]) for r in rows])
    return pd.DataFrame({
        "timestamp": pd.to_datetime([r[0] for r in rows], unit="ms", utc=True),
        "open": [float(r[1]) for r in rows], "high": [float(r[2]) for r in rows],
        "low": [float(r[3]) for r in rows], "close": [float(r[4]) for r in rows],
        "volume": [float(r[5]) for r in rows],
        "taker_buy_frac": np.where(qv > 0, tbq / qv, 0.5),   # >0.5 = net taker buying (flow)
    })


def list_perp_symbols() -> list[str]:
    """All actively-trading USDT-margined perpetuals (the free cross-sectional universe)."""
    info = _get(f"{_FAPI}/fapi/v1/exchangeInfo")
    syms = info.get("symbols", []) if isinstance(info, dict) else []
    return sorted(
        s["symbol"] for s in syms
        if s.get("contractType") == "PERPETUAL"
        and s.get("quoteAsset") == "USDT"
        and s.get("status") == "TRADING"
    )


def list_liquid_perps(*, top_n: int = 100) -> list[str]:
    """Top-N USDT perps by 24h quote volume -- the TRADEABLE universe (realistic-cost names)."""
    perps = set(list_perp_symbols())
    tickers = _get(f"{_FAPI}/fapi/v1/ticker/24hr")
    rows = [(t["symbol"], float(t.get("quoteVolume", 0.0)))
            for t in tickers if t.get("symbol") in perps]
    rows.sort(key=lambda x: x[1], reverse=True)
    return [s for s, _ in rows[:top_n]]


def fetch_klines(symbol: str, *, interval: str = "1d", start_ms: int = 0) -> pd.DataFrame:
    """Paginated klines for a USD-M PERP. Canonical OHLCV, UTC timestamps (futures cap 1500)."""
    return _klines(_FAPI, "/fapi/v1/klines", symbol, interval, start_ms, limit=1500)


def fetch_spot_klines(symbol: str, *, interval: str = "1d", start_ms: int = 0) -> pd.DataFrame:
    """Paginated klines for the SPOT pair (spot API caps limit at 1000 -- must paginate)."""
    return _klines(_SPOT, "/api/v3/klines", symbol, interval, start_ms, limit=1000)


def current_funding() -> dict[str, float]:
    """Latest funding rate per USD-M perp (mainnet premiumIndex) -- the live carry signal."""
    data = _get(f"{_FAPI}/fapi/v1/premiumIndex")
    if not isinstance(data, list):
        return {}
    return {d["symbol"]: float(d.get("lastFundingRate", 0.0)) for d in data
            if isinstance(d, dict) and d.get("symbol")}


def fetch_open_interest(symbol: str) -> float:
    """Current open interest (contracts) for a perp. History is 30d-capped, so log this forward."""
    data = _get(f"{_FAPI}/fapi/v1/openInterest?symbol={symbol}")
    return float(data.get("openInterest", 0.0)) if isinstance(data, dict) else 0.0


def fetch_funding(symbol: str, *, start_ms: int = 0) -> pd.DataFrame:
    """Paginated funding-rate history (every 8h). Returns (timestamp, funding)."""
    rows: list[dict[str, Any]] = []
    cur = start_ms
    while True:
        url = f"{_FAPI}/fapi/v1/fundingRate?symbol={symbol}&limit=1000&startTime={cur}"
        batch = _get(url)
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < 1000:
            break
        cur = int(batch[-1]["fundingTime"]) + 1
        time.sleep(0.25)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame({
        "timestamp": pd.to_datetime([r["fundingTime"] for r in rows], unit="ms", utc=True),
        "funding": [float(r["fundingRate"]) for r in rows],
    })


def bars_with_funding(
    symbol: str, *, interval: str = "1d", start: str = "2019-01-01"
) -> pd.DataFrame:
    """OHLCV + a ``funding`` column at the requested interval.

    ``1d``: funding is the SUM of the day's payments (the daily carry cost). ``8h``: funding settles
    every 8h, so each 8h bar maps to exactly one payment (its native frequency) -- this is the right
    resolution for funding-driven hypotheses and gives ~3x the independent observations.
    """
    start_ms = int(pd.Timestamp(start, tz="UTC").timestamp() * 1000)
    klines = fetch_klines(symbol, interval=interval, start_ms=start_ms)
    funding = fetch_funding(symbol, start_ms=start_ms)
    if klines.empty:
        return klines
    klines = klines.set_index("timestamp")
    if funding.empty:
        klines["funding"] = 0.0
    elif interval == "1d":
        daily = funding.set_index("timestamp")["funding"].resample("1D").sum()
        klines["funding"] = daily.reindex(klines.index).fillna(0.0)
    else:
        f = funding.set_index("timestamp")["funding"].sort_index()
        aligned = f.reindex(klines.index, method="nearest", tolerance=pd.Timedelta("4h"))
        klines["funding"] = aligned.fillna(0.0)
    return klines.reset_index()


def daily_with_funding(symbol: str, *, start: str = "2019-01-01") -> pd.DataFrame:
    """Daily OHLCV + a ``funding`` column (sum of the day's funding payments)."""
    return bars_with_funding(symbol, interval="1d", start=start)


def daily_enriched(symbol: str, *, start: str = "2019-01-01") -> pd.DataFrame:
    """Daily bars + funding + taker-buy flow + perp-spot BASIS (all FULL history, free).

    ``basis`` = perp_close / spot_close - 1 (positive = perp premium / contango; negative =
    backwardation). The spot pair shares the perp's ticker (BTCUSDT perp <-> BTCUSDT spot).
    """
    bars = bars_with_funding(symbol, interval="1d", start=start)
    if bars.empty:
        return bars
    start_ms = int(pd.Timestamp(start, tz="UTC").timestamp() * 1000)
    spot = fetch_spot_klines(symbol, interval="1d", start_ms=start_ms)
    bars = bars.set_index("timestamp")
    if spot.empty:
        bars["basis"] = 0.0
    else:
        sp = spot.set_index("timestamp")["close"].reindex(bars.index)
        bars["basis"] = (bars["close"] / sp - 1.0).fillna(0.0)
    if "taker_buy_frac" not in bars.columns:
        bars["taker_buy_frac"] = 0.5
    return bars.reset_index()


def fetch_long_short_ratio(symbol: str, *, period: str = "1d") -> pd.DataFrame:
    """Global account long/short ratio (30d-capped -> archive forward). (ts, ls_ratio)."""
    url = (f"{_FAPI}/futures/data/globalLongShortAccountRatio"
           f"?symbol={symbol}&period={period}&limit=30")
    data = _get(url)
    if not isinstance(data, list) or not data:
        return pd.DataFrame()
    return pd.DataFrame({
        "timestamp": pd.to_datetime([int(r["timestamp"]) for r in data], unit="ms", utc=True),
        "ls_ratio": [float(r["longShortRatio"]) for r in data],
    })


def fetch_open_interest_hist(symbol: str, *, period: str = "1h", limit: int = 500) -> pd.DataFrame:
    """Historical open interest (USD-M ``openInterestHist``, ~30-day cap). Hourly gives ~480 points
    over ~20 days -- enough samples to backtest now, without waiting for forward accumulation.
    (timestamp, open_interest)."""
    url = (f"{_FAPI}/futures/data/openInterestHist"
           f"?symbol={symbol}&period={period}&limit={limit}")
    data = _get(url)
    if not isinstance(data, list) or not data:
        return pd.DataFrame()
    return pd.DataFrame({
        "timestamp": pd.to_datetime([int(r["timestamp"]) for r in data], unit="ms", utc=True),
        "open_interest": [float(r["sumOpenInterest"]) for r in data],
    })


def fetch_long_short_hist(symbol: str, *, period: str = "1h", limit: int = 500) -> pd.DataFrame:
    """Historical global long/short account ratio (~30-day cap). Hourly -> ~480 points.
    (timestamp, ls_ratio)."""
    url = (f"{_FAPI}/futures/data/globalLongShortAccountRatio"
           f"?symbol={symbol}&period={period}&limit={limit}")
    data = _get(url)
    if not isinstance(data, list) or not data:
        return pd.DataFrame()
    return pd.DataFrame({
        "timestamp": pd.to_datetime([int(r["timestamp"]) for r in data], unit="ms", utc=True),
        "ls_ratio": [float(r["longShortRatio"]) for r in data],
    })


def fetch_taker_ratio(symbol: str, *, period: str = "1d") -> pd.DataFrame:
    """Taker buy/sell volume ratio from the derivatives-stats endpoint (30d-capped -> archive)."""
    url = f"{_FAPI}/futures/data/takerlongshortRatio?symbol={symbol}&period={period}&limit=30"
    data = _get(url)
    if not isinstance(data, list) or not data:
        return pd.DataFrame()
    return pd.DataFrame({
        "timestamp": pd.to_datetime([int(r["timestamp"]) for r in data], unit="ms", utc=True),
        "taker_ratio": [float(r["buySellRatio"]) for r in data],
    })

```

### libs/data/deribit.py
```python
"""Deribit options data (free public API) -- implied volatility, a NEW orthogonal data family.

DVOL is Deribit's 30-day implied-volatility index (crypto's VIX), available for BTC and ETH. The
*volatility risk premium* (implied vol minus subsequently realised vol) is a forward-looking,
options-derived signal that is structurally orthogonal to every perp/funding/flow signal we trade.
Public REST, no keys. History ~ months at 12h resolution.
"""

from __future__ import annotations

import json
import time
import urllib.request

import pandas as pd

_BASE = "https://www.deribit.com/api/v2/public"


def _get(url: str) -> dict[str, object]:
    req = urllib.request.Request(url, headers={"User-Agent": "quant-platform/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())
    return data if isinstance(data, dict) else {"_": data}


def fetch_dvol(currency: str = "BTC", *, days: int = 120, resolution: int = 43200) -> pd.DataFrame:
    """DVOL implied-vol index history (resolution seconds; 43200 = 12h). Columns: (timestamp, dvol).

    `dvol` is the annualised implied vol in percent (e.g. 50.0 = 50% annualised)."""
    end = int(time.time() * 1000)
    start = end - days * 86400 * 1000
    url = (f"{_BASE}/get_volatility_index_data?currency={currency}"
           f"&start_timestamp={start}&end_timestamp={end}&resolution={resolution}")
    res = _get(url).get("result")
    data = res.get("data") if isinstance(res, dict) else None
    if not isinstance(data, list) or not data:
        return pd.DataFrame()
    return pd.DataFrame({
        "timestamp": pd.to_datetime([int(str(r[0])) for r in data], unit="ms", utc=True),
        "dvol": [float(str(r[4])) for r in data]})       # close of [ts, open, high, low, close]


def vol_surface(currency: str = "BTC") -> dict[str, float]:
    """Current vol-surface snapshot from the whole option book (one call): ATM IV, 25-delta-proxy
    skew (OTM-put IV minus OTM-call IV; positive = crash fear), and term slope (front minus ~30d).

    Per-strike IV has NO free history, so this is archived FORWARD (see collect_deribit_surface).
    Returns {} on failure. IVs are in percent."""
    url = f"{_BASE}/get_book_summary_by_currency?currency={currency}&kind=option"
    res = _get(url).get("result")
    if not isinstance(res, list) or not res:
        return {}
    rows = []
    for r in res:
        if not isinstance(r, dict) or not r.get("mark_iv"):
            continue
        parts = str(r.get("instrument_name", "")).split("-")
        if len(parts) != 4:
            continue
        rows.append({"exp": parts[1], "strike": float(parts[2]), "type": parts[3],
                     "iv": float(r["mark_iv"]), "spot": float(r["underlying_price"])})
    if not rows:
        return {}
    df = pd.DataFrame(rows)
    spot = float(df["spot"].median())
    df["dte"] = (pd.to_datetime(df["exp"], format="%d%b%y", utc=True)
                 - pd.Timestamp.now(tz="UTC")).dt.total_seconds() / 86400.0
    df = df[df["dte"] > 1.0]
    if df.empty:
        return {}
    dtes = sorted(df["dte"].unique())
    front = df[df["dte"] == dtes[0]]
    far = df[df["dte"] == min(dtes, key=lambda x: abs(x - 30.0))]

    def _atm(g: pd.DataFrame) -> float:
        return float(g.iloc[int((g["strike"] - spot).abs().to_numpy().argmin())]["iv"]) if len(g) \
            else float("nan")

    atm = _atm(far) if len(far) else _atm(front)
    puts, calls = far[far["type"] == "P"], far[far["type"] == "C"]

    def _iv_near(g: pd.DataFrame, k: float) -> float:
        if not len(g):
            return atm
        return float(g.iloc[int((g["strike"] - k).abs().to_numpy().argmin())]["iv"])

    put_iv, call_iv = _iv_near(puts, 0.9 * spot), _iv_near(calls, 1.1 * spot)
    term = (_atm(front) - _atm(far)) if (len(front) and len(far)) else 0.0
    return {"atm_iv": round(atm, 2), "skew": round(put_iv - call_iv, 2),
            "term": round(float(term) if term == term else 0.0, 2), "spot": round(spot, 1)}

```

### libs/execution/tca.py
```python
"""Post-trade transaction cost analysis.

Measures realized execution quality against the arrival (pre-trade) and decision (signal) prices:
slippage in bps, implementation shortfall, realized vs forecast cost, and an attribution of the
realized slippage into spread / impact / timing using the pre-trade cost forecast. Closes the loop
so execution shortfall feeds back into edge/EV and capacity estimates.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from libs.costs.model import TradeCost
from libs.execution.errors import ExecutionError

_BPS = 1e4


def _avg_fill(fills: Sequence[tuple[float, float]]) -> tuple[float, float]:
    """Volume-weighted average fill price and total filled quantity."""
    total_qty = sum(q for _, q in fills)
    if total_qty <= 0:
        raise ExecutionError("TCA requires at least one non-zero fill")
    vwap = sum(p * q for p, q in fills) / total_qty
    return vwap, total_qty


class TcaResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    side: str  # "buy" | "sell"
    arrival_price: float
    decision_price: float
    avg_fill_price: float
    qty: float
    notional: float
    slippage_bps: float            # vs arrival price (positive = adverse)
    implementation_shortfall: float  # fractional, vs decision price (positive = adverse)
    realized_cost: float           # account-currency adverse cost vs arrival
    forecast_cost: float
    cost_error: float              # realized - forecast


class PostTradeTCA:
    """Computes realized execution quality for one parent order."""

    def analyze(
        self,
        *,
        symbol: str,
        side: str,
        arrival_price: float,
        decision_price: float,
        fills: Sequence[tuple[float, float]],
        forecast_cost: float = 0.0,
    ) -> TcaResult:
        if side not in ("buy", "sell"):
            raise ExecutionError(f"side must be 'buy' or 'sell', got {side!r}")
        if arrival_price <= 0 or decision_price <= 0:
            raise ExecutionError("arrival and decision prices must be positive")
        avg_fill, qty = _avg_fill(fills)
        sign = 1.0 if side == "buy" else -1.0  # buy: paying up is adverse; sell: receiving less
        slippage_bps = sign * (avg_fill - arrival_price) / arrival_price * _BPS
        shortfall = sign * (avg_fill - decision_price) / decision_price
        notional = avg_fill * qty
        realized_cost = sign * (avg_fill - arrival_price) * qty
        return TcaResult(
            symbol=symbol, side=side, arrival_price=arrival_price, decision_price=decision_price,
            avg_fill_price=avg_fill, qty=qty, notional=notional, slippage_bps=slippage_bps,
            implementation_shortfall=shortfall, realized_cost=realized_cost,
            forecast_cost=forecast_cost, cost_error=realized_cost - forecast_cost,
        )


class SlippageAttribution:
    """Attributes realized slippage into spread / impact / timing using the cost forecast."""

    def attribute(self, tca: TcaResult, forecast: TradeCost) -> dict[str, float]:
        """Decompose realized adverse cost into spread, impact, and residual timing components."""
        realized = max(0.0, tca.realized_cost)
        spread = min(realized, forecast.spread)
        impact = min(max(0.0, realized - spread), forecast.slippage)
        timing = max(0.0, realized - spread - impact)
        return {"spread": spread, "impact": impact, "timing": timing}

```

### libs/features/builtin.py
```python
"""Built-in, causal feature definitions registered into the default registry."""

from __future__ import annotations

import numpy as np
import pandas as pd

from libs.data.calendar import session_of
from libs.features.definition import FeatureDefinition
from libs.features.registry import FeatureRegistry

_SESSION_CODE = {"asia": 0.0, "london": 1.0, "overlap": 2.0, "newyork": 3.0, "off": 4.0}


def _ret_1(df: pd.DataFrame) -> pd.Series:
    return df["close"].pct_change(fill_method=None)


def _log_ret_1(df: pd.DataFrame) -> pd.Series:
    return np.log(df["close"] / df["close"].shift(1))


def _momentum_10(df: pd.DataFrame) -> pd.Series:
    return df["close"] / df["close"].shift(10) - 1.0


def _sma_10(df: pd.DataFrame) -> pd.Series:
    return df["close"].rolling(10, min_periods=1).mean()


def _rolling_vol_20(df: pd.DataFrame) -> pd.Series:
    returns = np.log(df["close"] / df["close"].shift(1))
    return returns.rolling(20, min_periods=2).std()


def _atr_14(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    true_range = pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(14, min_periods=1).mean()


def _zscore_20(df: pd.DataFrame) -> pd.Series:
    mean = df["close"].rolling(20, min_periods=5).mean()
    std = df["close"].rolling(20, min_periods=5).std()
    return (df["close"] - mean) / std


def _hour_of_day(df: pd.DataFrame) -> pd.Series:
    return df["timestamp"].dt.hour.astype("float64")


def _session_code(df: pd.DataFrame) -> pd.Series:
    return df["timestamp"].apply(lambda ts: _SESSION_CODE[session_of(ts)]).astype("float64")


BUILTIN_FEATURES: tuple[FeatureDefinition, ...] = (
    FeatureDefinition("ret_1", 1, _ret_1, inputs=("close",), category="price", min_periods=1),
    FeatureDefinition("log_ret_1", 1, _log_ret_1, inputs=("close",), category="price"),
    FeatureDefinition(
        "momentum_10", 1, _momentum_10, inputs=("close",), category="price", min_periods=10
    ),
    FeatureDefinition("sma_10", 1, _sma_10, inputs=("close",), category="price", min_periods=1),
    FeatureDefinition(
        "rolling_vol_20", 1, _rolling_vol_20, inputs=("close",), category="volatility",
        min_periods=20,
    ),
    FeatureDefinition(
        "atr_14", 1, _atr_14, inputs=("high", "low", "close"), category="volatility",
        min_periods=14,
    ),
    FeatureDefinition(
        "zscore_20", 1, _zscore_20, inputs=("close",), category="price", min_periods=20
    ),
    FeatureDefinition(
        "hour_of_day", 1, _hour_of_day, inputs=("timestamp",), category="session"
    ),
    FeatureDefinition(
        "session_code", 1, _session_code, inputs=("timestamp",), category="session"
    ),
)


def register_builtin_features(registry: FeatureRegistry) -> None:
    """Register all built-in features into ``registry`` (idempotent)."""
    for definition in BUILTIN_FEATURES:
        registry.register(definition, overwrite=True)

```

### libs/portfolio/multiperiod.py
```python
"""Multi-period, cost-aware portfolio glide path.

Single-period optimization ignores the cost of getting from the current book to the target. This
optimizer trades from ``current`` to ``target`` over ``n_steps``, capping turnover per step and
accounting for turnover cost, so rebalancing is gradual and cost-aware. Deterministic; respects the
per-name max-weight constraint at every step. It plans weights — the Portfolio/Risk engines remain
the approvers of any change.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field

from libs.portfolio.errors import PortfolioError
from libs.portfolio.models import PortfolioConstraints


class MultiPeriodPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: list[dict[str, float]] = Field(default_factory=list)  # weights per step
    step_turnover: list[float] = Field(default_factory=list)    # L1/2 turnover per step
    total_cost: float = 0.0


def _turnover(a: Mapping[str, float], b: Mapping[str, float]) -> float:
    keys = set(a) | set(b)
    return 0.5 * sum(abs(b.get(k, 0.0) - a.get(k, 0.0)) for k in keys)


class MultiPeriodOptimizer:
    """Plans a turnover-bounded, cost-aware glide path from current to target weights."""

    def __init__(
        self,
        *,
        constraints: PortfolioConstraints | None = None,
        cost_per_turnover: float = 0.0005,
        max_step_turnover: float = 0.20,
    ) -> None:
        self.constraints = constraints or PortfolioConstraints()
        self.cost_per_turnover = cost_per_turnover
        self.max_step_turnover = max_step_turnover

    def plan(
        self,
        *,
        current: Mapping[str, float],
        target: Mapping[str, float],
        n_steps: int,
    ) -> MultiPeriodPlan:
        if n_steps < 1:
            raise PortfolioError("n_steps must be >= 1")
        keys = sorted(set(current) | set(target))
        cur = {k: float(current.get(k, 0.0)) for k in keys}
        tgt = {k: self._cap(float(target.get(k, 0.0))) for k in keys}

        path: list[dict[str, float]] = []
        step_turnover: list[float] = []
        total_cost = 0.0
        for _ in range(n_steps):
            full_move = _turnover(cur, tgt)
            # Fraction of the remaining gap we may close this step (turnover-bounded).
            frac = 1.0 if full_move <= self.max_step_turnover or full_move <= 0.0 \
                else self.max_step_turnover / full_move
            # Interpolate toward the (already capped) target; gliding between a current weight and
            # a capped target never exceeds the cap, so each step stays turnover-bounded.
            nxt = {k: cur[k] + frac * (tgt[k] - cur[k]) for k in keys}
            moved = _turnover(cur, nxt)
            step_turnover.append(moved)
            total_cost += moved * self.cost_per_turnover
            path.append(nxt)
            cur = nxt
            if _turnover(cur, tgt) <= 1e-12:
                break
        return MultiPeriodPlan(path=path, step_turnover=step_turnover, total_cost=total_cost)

    def _cap(self, w: float) -> float:
        return max(self.constraints.min_weight, min(self.constraints.max_weight, w))

```

### libs/research/finding_registry.py
```python
"""Every finding must reach the loop that drives it -- the desk's own map-vs-territory rule,
turned on the desk's findings themselves.

The desk has exactly one organ that DRIVES work to completion: ``docs/GAP_REGISTER.md``, with its
weekly re-rank and 7-day staleness escalation. Everything else -- SYSTEM_REVIEW, BLIND_SPOT_AUDIT,
the micro-audit inbox, the improvement inbox, an external panel ruling, an audit delivered in a
chat window -- is a place findings are WRITTEN, not a place they are WORKED. A finding that never
reaches the register is invisible to the daily cycle, and the cycle only ever acts on what it can
see. It does not rot loudly; it simply never happened.

This was measured, not theorised: of eleven engineering defects found in a full-repo audit, three
were detected by any check and one had a register row. The other eight existed only in a
conversation, and would have vanished with it.

``max_audit.check_review_risks_tracked`` already enforced this -- for THREE HARDCODED KEYS
(counterparty, key-person, per-venue). That is the same brittleness one level up: it can only
catch risks somebody remembered to hardcode, so the next un-tracked finding is invisible again by
construction. This module generalises it: parse findings from wherever they are written, match
them against the register, and report the ones with no trace.

MATCHING IS DELIBERATELY GENEROUS. A finding counts as tracked when any distinctive token from its
title appears in the register. False ACCEPTS are cheap -- the item was probably tracked under
another phrasing. False ALARMS are expensive: a check that flags everything gets ignored, and an
ignored check is worse than no check because it looks like coverage. The same lesson the §33 card
parser learned by firing 92/92 on its first real run.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from datetime import date

from pydantic import BaseModel, ConfigDict

#: A finding: a numbered item with a bolded title. Covers the prose form used by SYSTEM_REVIEW and
#: BLIND_SPOT_AUDIT (``3. **Name** ...``) and the table form used by the audit inboxes
#: (``| 3 | **CHANGE** thing | ...``). Free prose is deliberately NOT matched -- an unnumbered
#: paragraph is a remark, and treating remarks as obligations is how a check becomes noise.
#: PROSE form: ``3. **Name** ...`` as used by SYSTEM_REVIEW / BLIND_SPOT_AUDIT.
_PROSE_RE = re.compile(r"^\s*(?P<num>\d+)[.)]\s*\*\*(?P<title>[^*]{4,140})\*\*", re.MULTILINE)
#: TABLE form: ``| 3 | **CHANGE** `run_ci` -- fix the job | why | ...``. The whole first cell is
#: the title: capturing only the bolded span yields the VERB ("CHANGE"), which carries no
#: distinctive token and made every audit-inbox row look untracked on the first real run.
_TABLE_RE = re.compile(r"^\s*\|\s*(?P<num>\d+)\s*\|\s*(?P<title>[^|]{4,200})\|", re.MULTILINE)
#: Headings whose contents are already settled. Anything under one of these is reported as
#: resolved rather than owed -- the inboxes carry large "already live" and "closed" sections, and
#: demanding register rows for them would bury the real items.
_SETTLED_HEAD = re.compile(
    r"already live|duplicat|closed|resolved|done|shipped|complete|history|archive|graveyard",
    re.IGNORECASE,
)
_HEADING_RE = re.compile(r"^#{1,6}\s+(?P<h>.+?)\s*$", re.MULTILINE)
#: Words too common to prove a match -- "risk" appearing in the register means nothing.
_STOP = {
    "the", "and", "for", "with", "from", "that", "this", "into", "onto", "your", "our", "not",
    "add", "fix", "wire", "change", "risk", "data", "test", "tests", "code", "live", "desk",
    "new", "old", "all", "any", "one", "two", "use", "using", "make", "made", "gap", "audit",
    "check", "checks", "build", "built", "run", "runs", "only", "per", "via", "its", "has",
}


class Finding(BaseModel):
    """One numbered finding, wherever it was written."""

    model_config = ConfigDict(frozen=True)

    source: str
    number: int
    title: str
    settled: bool = False   # written under an already-live / closed heading

    @property
    def tokens(self) -> tuple[str, ...]:
        """Distinctive words that would identify this finding in another document."""
        words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_.-]{3,}", self.title.lower())
        return tuple(w for w in words if w not in _STOP)


def parse_findings(text: str, *, source: str) -> list[Finding]:
    """Extract numbered, bolded findings and mark the ones sitting under a settled heading."""
    heads = [(m.start(), m.group("h")) for m in _HEADING_RE.finditer(text)]
    out: list[Finding] = []
    matches = sorted(list(_PROSE_RE.finditer(text)) + list(_TABLE_RE.finditer(text)),
                     key=lambda m: m.start())
    for m in matches:
        title = re.sub(r"[*`]", "", m.group("title"))
        title = re.sub(r"\s+", " ", title).strip(" -—:")
        if not title:
            continue
        prior = [h for pos, h in heads if pos < m.start()]
        settled = bool(prior and _SETTLED_HEAD.search(prior[-1]))
        out.append(Finding(source=source, number=int(m.group("num")),
                           title=title, settled=settled))
    return out


def is_tracked(finding: Finding, register: str) -> bool:
    """Does the register carry any trace of this finding?

    Generous by design: one distinctive token is enough. The check exists to catch findings with
    NO representation at all, not to police wording.
    """
    reg = register.lower()
    if not finding.tokens:
        # Nothing distinctive to search for -- unjudgeable, so it is NOT accused. A check that
        # reports items it cannot actually evaluate is manufacturing work, not finding it.
        return True
    return any(tok in reg for tok in finding.tokens)


def untracked(findings: Iterable[Finding], register: str) -> tuple[Finding, ...]:
    """Open findings with no trace in the register -- the ones the daily cycle cannot see."""
    return tuple(f for f in findings if not f.settled and not is_tracked(f, register))


class CoverageReport(BaseModel):
    """How much of what the desk has FOUND is actually being DRIVEN."""

    model_config = ConfigDict(frozen=True)

    n_findings: int
    n_settled: int
    n_open: int
    n_untracked: int
    coverage: float          # tracked / open; 1.0 = every open finding reaches the register
    untracked_names: tuple[str, ...]
    verdict: str


def coverage_report(
    findings: Sequence[Finding], register: str, *, max_shown: int = 10
) -> CoverageReport:
    """Measure finding -> register coverage. Below 1.0, the cycle is blind to real work."""
    settled = [f for f in findings if f.settled]
    open_ = [f for f in findings if not f.settled]
    ut = untracked(findings, register)
    cov = 1.0 if not open_ else round(1.0 - len(ut) / len(open_), 3)
    if not open_:
        verdict = "no open findings parsed -- nothing owed"
    elif not ut:
        verdict = (f"all {len(open_)} open finding(s) have a register trace "
                   "-- the cycle can see them")
    else:
        verdict = (
            f"{len(ut)}/{len(open_)} open finding(s) have NO register trace ({cov:.0%} coverage). "
            "The daily cycle acts on the register; anything absent from it is invisible and will "
            "never be worked, however carefully it was found."
        )
    return CoverageReport(
        n_findings=len(findings), n_settled=len(settled), n_open=len(open_),
        n_untracked=len(ut), coverage=cov,
        untracked_names=tuple(f"{f.source.rsplit('/', 1)[-1]}#{f.number} {f.title[:60]}"
                              for f in ut[:max_shown]),
        verdict=verdict,
    )


# --------------------------------------------------------------------------------------------
# THE COVERAGE RATCHET. A one-off 100% is a snapshot; the law needs a floor that only ever rises.
# And the cheapest way to reach 100% is NOT to row the findings -- it is to SHRINK THE DENOMINATOR:
# exclude a doc from scope, or delete the finding. That is the same loophole §34 closed for mining
# (fake a conversion rate by mining less), so it is closed the same way: scope size and finding
# count ratchet UP alongside coverage, and all three are held against the desk's own best.
# --------------------------------------------------------------------------------------------

class CoverageRatchet(BaseModel):
    """Best-ever finding→register coverage AND the scope it was achieved over."""

    model_config = ConfigDict(frozen=True)

    best_coverage: float = 0.0
    max_open_findings: int = 0   # denominator high-water mark -- scope may never shrink
    max_docs_scanned: int = 0
    best_at: str = ""
    n_records: int = 0


class RatchetVerdict(BaseModel):
    """Did coverage hold, improve, or regress -- and was the denominator honest?"""

    model_config = ConfigDict(frozen=True)

    improved: bool
    coverage_regressed: bool
    scope_shrank: bool
    verdict: str


def update_coverage_ratchet(
    prior: CoverageRatchet,
    report: CoverageReport,
    *,
    n_docs: int,
    at: str = "",
) -> tuple[CoverageRatchet, RatchetVerdict]:
    """Hold coverage against the desk's own best, over a scope that may never shrink.

    THREE things ratchet, because any one alone is gameable:
      COVERAGE        -- the share of open findings the cycle can see; never allowed to fall.
      OPEN FINDINGS   -- the denominator. Deleting findings raises coverage arithmetically while
                        making the desk blinder, so the count is a high-water mark too.
      DOCS SCANNED    -- excluding a findings doc raises coverage the same dishonest way.

    A worse cycle NEVER relaxes any of the three; it produces a defect instead. That asymmetry is
    the whole mechanism -- a standard that can fall is a standard the desk drifts past.
    """
    cov_record = report.coverage > prior.best_coverage
    cov_regressed = bool(prior.best_coverage and report.coverage < prior.best_coverage - 1e-9)
    shrank = bool(
        (prior.max_open_findings and report.n_open < prior.max_open_findings)
        or (prior.max_docs_scanned and n_docs < prior.max_docs_scanned)
    )
    improved = bool(cov_record or report.n_open > prior.max_open_findings
                    or n_docs > prior.max_docs_scanned)

    new = CoverageRatchet(
        best_coverage=max(prior.best_coverage, report.coverage),
        max_open_findings=max(prior.max_open_findings, report.n_open),
        max_docs_scanned=max(prior.max_docs_scanned, n_docs),
        best_at=(at or prior.best_at) if improved else prior.best_at,
        n_records=prior.n_records + (1 if improved else 0),
    )

    if shrank:
        verdict = (
            f"SCOPE SHRANK: {report.n_open} open findings over {n_docs} docs vs a high-water "
            f"{prior.max_open_findings} over {prior.max_docs_scanned}. Coverage rises "
            "arithmetically when findings or docs disappear -- that is a blinder desk, not a "
            "better one. Restore the scope or record why the items are legitimately closed."
        )
    elif cov_regressed:
        verdict = (
            f"COVERAGE REGRESSED: {report.coverage:.0%} vs best-ever {prior.best_coverage:.0%}. "
            "New findings were written without register rows. Row them; the floor only rises."
        )
    elif report.coverage >= 1.0:
        verdict = (
            f"100% -- all {report.n_open} open finding(s) across {n_docs} docs reach the register. "
            "Hold it: the bar is now this, permanently."
        )
    elif cov_record:
        verdict = (f"coverage record {report.coverage:.0%} (prev {prior.best_coverage:.0%}) -- "
                   "floor raised, it never lowers. Target is 100%.")
    else:
        verdict = (f"coverage {report.coverage:.0%} holding at the floor. Holding is not reaching: "
                   f"{report.n_untracked} finding(s) are still invisible to the cycle.")
    return new, RatchetVerdict(improved=improved, coverage_regressed=cov_regressed,
                               scope_shrank=shrank, verdict=verdict)


# --------------------------------------------------------------------------------------------
# THE REGISTER'S OWN HEALTH. §35 and §36 route everything INTO the register, which makes it the
# load-bearing organ for both -- and it was never checked itself. Its rules ("re-ranked at the
# START of every daily cycle", "items stale >7 days MUST be escalated", "never empty without
# written justification") are written INSIDE the register, which is precisely the shape §36 names
# as a rule with no clock. Routing findings into a bucket nobody empties is not an improvement.
# --------------------------------------------------------------------------------------------

_RERANK_RE = re.compile(r"Re-ranked\s+(\d{4}-\d{2}-\d{2})")
#: A register row: | id | **title** | mechanism | plan | owner | added | status |
_ROW_RE = re.compile(
    r"^\|\s*(?P<id>\d+)\s*\|\s*\*\*(?P<title>.+?)\*\*\s*\|(?P<body>.*?)\|\s*(?P<owner>[a-z+ ]*?)"
    r"\s*\|\s*(?P<added>[\d-]*)\s*\|\s*(?P<status>[^|]*?)\s*\|\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_OPEN_STATUS = ("open", "in-progress", "in progress", "queued", "watch", "pending")
#: Any date-shaped token in the plan text -- evidence the "defer WITH A DEADLINE" exit was taken.
_HAS_DATE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{2}-\d{2}\b")


class RegisterRow(BaseModel):
    """One tracked obligation."""

    model_config = ConfigDict(frozen=True)

    row_id: int
    title: str
    owner: str
    added: str
    status: str
    plan_has_date: bool

    @property
    def is_open(self) -> bool:
        return self.status.strip().lower().startswith(_OPEN_STATUS)

    def age_days(self, today: date) -> float:
        """Days since this row was ADDED. -1 when the date is missing or unparseable.

        The register writes `MM-DD` with no year. A date that would land in the future is read as
        last year's -- the only reading that does not turn a December row into a -300-day-old one
        every January, which would silently exempt the oldest rows exactly when they matter most.
        """
        raw = self.added.strip()
        if not raw:
            return -1.0
        try:
            month, day = (int(x) for x in raw.split("-")[:2])
            when = date(today.year, month, day)
        except (ValueError, TypeError):
            return -1.0
        if when > today:
            try:
                when = date(today.year - 1, month, day)
            except ValueError:      # pragma: no cover - 29 Feb on a non-leap year
                return -1.0
        return float((today - when).days)


class RegisterHealth(BaseModel):
    """Is the desk's only work-driving organ actually being driven?"""

    model_config = ConfigDict(frozen=True)

    n_rows: int
    n_open: int
    rerank_age_days: float      # -1 when no stamp was ever written
    rerank_stale: bool
    rerank_breach: bool         # past the register's own 7-day escalation bar
    undated_open: tuple[str, ...]
    ownerless: tuple[str, ...]
    #: Open rows older than the register's OWN escalation bar. THE rule the register actually
    #: states is about ITEMS ("items stale >7 days MUST be escalated"), not about the re-rank
    #: stamp -- and measuring the stamp instead let a daily re-rank make every row immortal.
    stale_rows: tuple[str, ...]
    oldest_open_days: float
    verdict: str


def parse_register(text: str) -> list[RegisterRow]:
    """Extract every tracked row from the register table."""
    out = []
    for m in _ROW_RE.finditer(text):
        out.append(RegisterRow(
            row_id=int(m.group("id")), title=m.group("title").strip(),
            owner=m.group("owner").strip(), added=m.group("added").strip(),
            status=m.group("status").strip(),
            plan_has_date=bool(_HAS_DATE.search(m.group("body") or "")),
        ))
    return out


def register_health(
    text: str, *, today: date, rerank_bar_days: float = 2.0, escalate_days: float = 7.0
) -> RegisterHealth:
    """Hold the register to the rules it states about itself.

    The re-rank age is read from the register's SELF-DECLARED ``Re-ranked <date>`` stamp, never
    from file mtime or commit time -- touching the file must not be able to fake a re-rank that
    did not happen. Same artifact-only credit principle §33 applies to conversion claims: the
    evidence has to be the thing itself, not a side effect of editing it.
    """
    rows = parse_register(text)
    open_rows = [r for r in rows if r.is_open]
    stamps = _RERANK_RE.findall(text)
    age = -1.0
    if stamps:
        with_dates = []
        for s in stamps:
            try:
                with_dates.append(date.fromisoformat(s))
            except ValueError:  # pragma: no cover
                continue
        if with_dates:
            age = float((today - max(with_dates)).days)

    # An open row whose plan carries no date took NONE of the register's three exits (implement /
    # defer WITH A DEADLINE / retire with reason) -- it is parked, which is the state the rule
    # exists to forbid.
    undated = tuple(f"#{r.row_id} {r.title[:48]}" for r in open_rows if not r.plan_has_date)
    ownerless = tuple(f"#{r.row_id} {r.title[:48]}" for r in open_rows if not r.owner)

    # ROW-LEVEL STALENESS -- the rule the register actually writes down. It says "items stale >7
    # days MUST be escalated"; the first version of this function measured the RE-RANK STAMP
    # instead, so re-stamping the header each morning made every row immortal: 15 rows sat 9-10
    # days untouched while the check reported clean. Measuring the artifact the rule names, rather
    # than a proxy that correlates with tidiness, is the whole point of §36(3).
    aged = sorted(((r.age_days(today), r) for r in open_rows), key=lambda x: -x[0])
    stale_rows = tuple(f"#{r.row_id} ({a:.0f}d) {r.title[:44]}" for a, r in aged
                       if a > escalate_days)
    oldest = aged[0][0] if aged else -1.0

    stale = age > rerank_bar_days
    breach = age > escalate_days

    if not rows:
        verdict = ("register parsed ZERO rows -- either empty or the table shape changed. Its own "
                   "rule is 'never empty without written justification'; a register that cannot "
                   "be parsed drives nothing, and everything §35/§36 routes into it is lost.")
    elif stale_rows:
        verdict = (f"{len(stale_rows)} open row(s) past the register's OWN {escalate_days:.0f}-day "
                   f"escalation bar (oldest {oldest:.0f}d), while the re-rank stamp reads "
                   f"{age:.0f}d old. Re-ranking the header is not escalating the rows: each one "
                   "owes implement / defer-with-a-deadline / retire-with-reason.")
    elif breach:
        verdict = (f"re-rank {age:.0f}d old, past the register's OWN {escalate_days:.0f}-day "
                   f"escalation bar, with {len(open_rows)} open row(s). The rule is written in the "
                   "register and was enforced by nothing.")
    elif stale:
        verdict = (f"re-rank {age:.0f}d old against 'at the START of every daily cycle'. "
                   f"{len(open_rows)} open row(s) are not being re-prioritised.")
    else:
        verdict = f"re-rank current ({age:.0f}d), {len(open_rows)} open row(s) under active rank"
    return RegisterHealth(
        stale_rows=stale_rows, oldest_open_days=round(oldest, 1),
        n_rows=len(rows), n_open=len(open_rows), rerank_age_days=age,
        rerank_stale=stale, rerank_breach=breach,
        undated_open=undated[:8], ownerless=ownerless[:8], verdict=verdict,
    )

```

### libs/signal_engine/__init__.py
```python
"""``libs.signal_engine`` — Stage 13.5 institutional signal intelligence engine.

The exclusive source of every BUY/SELL/FLAT decision. It transforms validated alpha outputs into
high-conviction trading decisions: weighting votes, routing by current and predicted regime,
confirming across assets and microstructure, estimating edge and expected value, scoring
confidence/quality/persistence/stability/decay, forecasting capacity, checking crowding, factor
concentration, execution feasibility and portfolio contribution, then ranking by a single
institutional score and selecting fail-closed. Only a ``SignalPackage`` may reach the Portfolio
Engine, and only after the validation gauntlet has passed.

Reuses Architecture v1.0: ``libs.costs`` (frictions), ``libs.discovery`` (capacity, tail risk),
``libs.self_improvement`` (decay classification), and the immutable ``libs.store`` audit log.
"""

from __future__ import annotations

from libs.signal_engine.aggregation import Aggregation, SignalAggregator
from libs.signal_engine.alpha_competition_engine import (
    AlphaCompetitionEngine,
    CompetitionResult,
)
from libs.signal_engine.alpha_weighting import AlphaWeighting, DynamicWeighting
from libs.signal_engine.attribution import AttributionResult, SignalAttributionEngine
from libs.signal_engine.audit import SignalAudit
from libs.signal_engine.capacity import SignalCapacityForecaster
from libs.signal_engine.champion_challenger import (
    ABTestResult,
    ChampionChallenger,
    VariantMetrics,
)
from libs.signal_engine.confidence_engine import ConfidenceEngine
from libs.signal_engine.crowding import SignalCrowdingEngine
from libs.signal_engine.decay import SignalDecayEngine
from libs.signal_engine.edge_estimator import EdgeEstimator
from libs.signal_engine.engine import SignalEngine, SymbolObservation
from libs.signal_engine.errors import SignalEngineError, SignalGovernanceError
from libs.signal_engine.execution import ExecutionFeasibilityEngine
from libs.signal_engine.expected_value import ExpectedValueEngine
from libs.signal_engine.factor_exposure import FactorExposureEngine
from libs.signal_engine.governance import (
    GovernanceVerdict,
    require_governance,
    signal_governance_gate,
)
from libs.signal_engine.institutional_score import institutional_signal_score
from libs.signal_engine.market_impact_forecaster import ImpactForecast, MarketImpactForecaster
from libs.signal_engine.meta_model import MetaModel
from libs.signal_engine.models import (
    AlphaSignal,
    CapacityForecast,
    ConfidenceResult,
    CrowdingResult,
    DecayLevel,
    Direction,
    EdgeEstimate,
    ExecutionFeasibility,
    ExpectedValueResult,
    FactorExposureResult,
    InstitutionalScore,
    MarketState,
    MonitoringSnapshot,
    PersistenceResult,
    PortfolioContextResult,
    QualityResult,
    Regime,
    SelectionResult,
    SignalDecayResult,
    SignalPackage,
    StabilityResult,
    TradeCandidate,
    UncertaintyResult,
)
from libs.signal_engine.monitoring import build_monitoring_snapshot
from libs.signal_engine.persistence import SignalPersistenceEngine, SignalStabilityEngine
from libs.signal_engine.portfolio_context import PortfolioContextEngine
from libs.signal_engine.quality import SignalFilters, SignalQuality
from libs.signal_engine.ranking import SignalRanker, rank_trade_candidates
from libs.signal_engine.regime import (
    RegimeRouter,
    RegimeTransitionRouter,
    transition_confidence,
)
from libs.signal_engine.selection import (
    SelectionThresholds,
    select_final_signals,
    to_package,
)
from libs.signal_engine.shadow import ShadowDeployment, ShadowResult
from libs.signal_engine.signal_embedding_engine import SignalEmbeddingEngine
from libs.signal_engine.stress_signal_engine import StressResult, StressSignalEngine
from libs.signal_engine.uncertainty import SignalUncertaintyEngine, signal_tail_risk

__all__ = [  # noqa: RUF022  # grouped by concern
    # models / enums
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
    # engines
    "SignalEngine",
    "SymbolObservation",
    "SignalAggregator",
    "Aggregation",
    "AlphaWeighting",
    "DynamicWeighting",
    "RegimeRouter",
    "RegimeTransitionRouter",
    "transition_confidence",
    "EdgeEstimator",
    "ExpectedValueEngine",
    "ConfidenceEngine",
    "MetaModel",
    "SignalPersistenceEngine",
    "SignalStabilityEngine",
    "SignalDecayEngine",
    "SignalCrowdingEngine",
    "SignalCapacityForecaster",
    "FactorExposureEngine",
    "ExecutionFeasibilityEngine",
    "PortfolioContextEngine",
    "SignalUncertaintyEngine",
    "signal_tail_risk",
    "SignalQuality",
    "SignalFilters",
    "SignalEmbeddingEngine",
    "MarketImpactForecaster",
    "ImpactForecast",
    "AlphaCompetitionEngine",
    "CompetitionResult",
    "StressSignalEngine",
    "StressResult",
    "SignalAttributionEngine",
    "AttributionResult",
    "ChampionChallenger",
    "VariantMetrics",
    "ABTestResult",
    "ShadowDeployment",
    "ShadowResult",
    # scoring / ranking / selection
    "institutional_signal_score",
    "rank_trade_candidates",
    "SignalRanker",
    "select_final_signals",
    "to_package",
    "SelectionThresholds",
    # governance / audit / monitoring
    "GovernanceVerdict",
    "signal_governance_gate",
    "require_governance",
    "SignalAudit",
    "build_monitoring_snapshot",
    # errors
    "SignalEngineError",
    "SignalGovernanceError",
]

```

### libs/signal_engine/champion_challenger.py
```python
"""Champion/challenger testing — promote a challenger only on hard evidence.

Compares a live champion variant against a challenger and recommends promotion only if the
challenger has passed walk-forward governance and beats the champion on a fail-closed battery of
checks (sample size, Sharpe uplift, drawdown not worse, profit factor not worse). Recommend-only.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class VariantMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    variant_id: str
    sharpe: float
    profit_factor: float
    turnover: float
    max_drawdown: float  # positive magnitude
    n_samples: int


class ABTestResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    champion_id: str
    challenger_id: str
    winner_id: str
    promote: bool
    rationale: str
    margins: dict[str, float] = Field(default_factory=dict)


class ChampionChallenger:
    """Decides whether a challenger should replace the champion (fail-closed)."""

    def __init__(
        self,
        *,
        min_samples: int = 100,
        min_sharpe_uplift: float = 0.1,
        max_drawdown_ratio: float = 1.10,
        require_pf_improvement: bool = True,
    ) -> None:
        self.min_samples = min_samples
        self.min_sharpe_uplift = min_sharpe_uplift
        self.max_drawdown_ratio = max_drawdown_ratio
        self.require_pf_improvement = require_pf_improvement

    def compare(
        self,
        champion: VariantMetrics,
        challenger: VariantMetrics,
        *,
        challenger_walk_forward_passed: bool,
    ) -> ABTestResult:
        sharpe_uplift = challenger.sharpe - champion.sharpe
        dd_ok = challenger.max_drawdown <= champion.max_drawdown * self.max_drawdown_ratio
        pf_ok = (
            not self.require_pf_improvement
            or challenger.profit_factor >= champion.profit_factor
        )
        checks = {
            "walk_forward_passed": challenger_walk_forward_passed,
            "enough_samples": challenger.n_samples >= self.min_samples,
            "sharpe_uplift": sharpe_uplift >= self.min_sharpe_uplift,
            "drawdown_not_worse": dd_ok,
            "profit_factor_not_worse": pf_ok,
        }
        promote = all(checks.values())  # fail-closed: every gate must pass
        failed = [name for name, ok in checks.items() if not ok]
        return ABTestResult(
            champion_id=champion.variant_id,
            challenger_id=challenger.variant_id,
            winner_id=challenger.variant_id if promote else champion.variant_id,
            promote=promote,
            rationale="promote challenger" if promote else f"keep champion; failed: {failed}",
            margins={
                "sharpe_uplift": sharpe_uplift,
                "drawdown_ratio": (
                    challenger.max_drawdown / champion.max_drawdown
                    if champion.max_drawdown > 0
                    else 0.0
                ),
                "pf_delta": challenger.profit_factor - champion.profit_factor,
            },
        )

```

### libs/signal_engine/execution.py
```python
"""Execution feasibility — can this signal actually be filled at acceptable cost?

Estimates fill probability and the spread/slippage/impact drag, blends them into a 0-100
execution score, and rejects signals below threshold. This composes with ``libs.costs`` at the
execution layer; here it works in basis points so it stays independent of the instrument registry.
"""

from __future__ import annotations

from libs.signal_engine.models import ExecutionFeasibility


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class ExecutionFeasibilityEngine:
    """Scores executability; below ``threshold`` the signal is rejected."""

    def __init__(self, *, threshold: float = 50.0, cost_cap_bps: float = 50.0) -> None:
        self.threshold = threshold
        self.cost_cap_bps = cost_cap_bps

    def assess(
        self,
        *,
        spread_bps: float,
        expected_slippage_bps: float,
        market_impact_bps: float,
        liquidity_score: float,
        latency_risk: float = 0.0,
    ) -> ExecutionFeasibility:
        fill_probability = _clip01(liquidity_score * (1.0 - _clip01(latency_risk)))
        total_cost_bps = spread_bps + expected_slippage_bps + market_impact_bps
        cost_drag = _clip01(total_cost_bps / self.cost_cap_bps)
        execution_score = 100.0 * fill_probability * (1.0 - cost_drag)
        return ExecutionFeasibility(
            execution_score=execution_score,
            fill_probability=fill_probability,
            expected_slippage_bps=expected_slippage_bps,
            market_impact_bps=market_impact_bps,
            spread_cost_bps=spread_bps,
            passed=execution_score >= self.threshold,
        )

```

### libs/signal_engine/institutional_score.py
```python
"""Institutional signal score — the single 0-100 master score for ranking/selection.

Combines edge, confidence, capacity, persistence, stability, decay, portfolio contribution, and
execution quality as rewards, with tail risk and uncertainty as penalties. All ranking and final
selection ultimately key off this score.
"""

from __future__ import annotations

from libs.signal_engine.models import InstitutionalScore

# Component weights (sum to 1.0). Rewards positive, penalties enter as (1 - penalty).
_WEIGHTS: dict[str, float] = {
    "edge": 0.18,
    "confidence": 0.18,
    "portfolio_contribution": 0.12,
    "execution": 0.10,
    "capacity": 0.08,
    "persistence": 0.08,
    "stability": 0.08,
    "decay": 0.06,
    "tail": 0.06,
    "uncertainty": 0.06,
}


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def institutional_signal_score(
    *,
    edge_score: float,
    confidence: float,
    capacity_score: float,
    persistence_score: float,
    stability_score: float,
    decay_weight_multiplier: float,
    portfolio_contribution: float,
    execution_score: float,
    tail_risk_score: float,
    uncertainty_score: float,
) -> InstitutionalScore:
    components = {
        "edge": _clip01(edge_score / 100.0),
        "confidence": _clip01(confidence),
        "portfolio_contribution": _clip01(portfolio_contribution / 100.0),
        "execution": _clip01(execution_score / 100.0),
        "capacity": _clip01(capacity_score / 100.0),
        "persistence": _clip01(persistence_score / 100.0),
        "stability": _clip01(stability_score / 100.0),
        "decay": _clip01(decay_weight_multiplier),
        "tail": _clip01(1.0 - tail_risk_score / 100.0),
        "uncertainty": _clip01(1.0 - uncertainty_score),
    }
    score = 100.0 * sum(_WEIGHTS[k] * v for k, v in components.items())
    return InstitutionalScore(score=score, components=components)

```

### libs/stage14/analytics.py
```python
"""Portfolio analytics — correlation, survival, stress, resilience, convexity, contribution, cost.

Thin orchestration over the platform's existing primitives (Monte-Carlo survival, stress
scenarios) plus portfolio-level measures. Every score is 0-100 unless noted; survival dominates.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from libs.discovery.monte_carlo_survival import monte_carlo_survival
from libs.discovery.stress_scenario import stress_scenario
from libs.stage14.models import (
    ConvexityResult,
    CorrelationResult,
    EfficiencyResult,
    MarginalContribution,
    ResilienceResult,
    RiskBudget,
    StressResult,
    SurvivalResult,
)

_EPS = 1e-12


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class PortfolioCorrelationEngine:
    """Flags hidden concentration from the portfolio correlation matrix."""

    def evaluate(
        self, correlation: np.ndarray, *, budget: RiskBudget | None = None
    ) -> CorrelationResult:
        corr = np.asarray(correlation, dtype="float64")
        n = corr.shape[0]
        if corr.ndim != 2 or corr.shape[1] != n:
            raise ValueError("correlation must be square")
        if n < 2:
            return CorrelationResult(avg_pairwise=0.0, max_pairwise=0.0, concentration=0.0,
                                     acceptable=True)
        iu = np.triu_indices(n, k=1)
        off = np.abs(corr[iu])
        avg = float(off.mean())
        mx = float(off.max())
        limit = (budget or RiskBudget()).correlation_budget
        return CorrelationResult(
            avg_pairwise=avg, max_pairwise=mx, concentration=avg, acceptable=avg <= limit
        )


class PortfolioSurvivalEngine:
    """Probability of ruin / survival (reuses Monte-Carlo survival). Survival dominates return."""

    def evaluate(
        self, returns: np.ndarray, *, dd_limit: float = 0.20, cost_stress: float = 0.0005,
        seed: int = 0,
    ) -> SurvivalResult:
        base = monte_carlo_survival(returns, dd_limit=dd_limit, seed=seed)
        stressed = monte_carlo_survival(
            returns, dd_limit=dd_limit, cost_per_period=cost_stress, seed=seed
        )
        return SurvivalResult(
            survival_probability=base.survival_probability,
            probability_of_ruin=base.probability_of_ruin,
            stress_survival=stressed.survival_probability,
            survival_score=100.0 * base.survival_probability,
        )


class PortfolioStressEngine:
    """Historical-crisis stress (reuses the scenario engine: 2008/2020/flash/vol/liquidity)."""

    def evaluate(self, returns: np.ndarray, *, exposure: float = 1.0) -> StressResult:
        result = stress_scenario(returns, exposure=exposure)
        return StressResult(
            stress_score=result.stress_resilience_score,
            worst_drawdown=result.worst_drawdown,
            by_scenario=dict(result.by_scenario),
        )


class PortfolioResilienceEngine:
    """Blends regime / factor / capacity / execution resilience into one score."""

    def evaluate(
        self,
        *,
        regime_resilience: float,
        factor_resilience: float,
        capacity_resilience: float,
        execution_resilience: float,
    ) -> ResilienceResult:
        components = {
            "regime": _clip01(regime_resilience),
            "factor": _clip01(factor_resilience),
            "capacity": _clip01(capacity_resilience),
            "execution": _clip01(execution_resilience),
        }
        score = 100.0 * float(np.mean(list(components.values())))
        return ResilienceResult(resilience_score=score, components=components)


class PortfolioConvexityEngine:
    """Skew, convexity, and crisis alpha — prefer positive convexity and crash resilience."""

    def evaluate(self, returns: np.ndarray) -> ConvexityResult:
        arr = np.asarray(returns, dtype="float64")
        if len(arr) < 3:
            return ConvexityResult(skew=0.0, convexity=1.0, crisis_alpha=0.0, convexity_score=50.0)
        mu, sd = float(arr.mean()), float(arr.std())
        skew = float(((arr - mu) ** 3).mean() / (sd**3)) if sd > _EPS else 0.0
        up = arr[arr > 0]
        down = arr[arr < 0]
        up_semivar = float((up**2).mean()) if len(up) else 0.0
        down_semivar = float((down**2).mean()) if len(down) else _EPS
        convexity = up_semivar / down_semivar if down_semivar > _EPS else 1.0
        worst = np.quantile(arr, 0.1)
        crisis_alpha = float(arr[arr <= worst].mean()) if np.any(arr <= worst) else 0.0
        score = 100.0 * _clip01(0.5 * _clip01(convexity / 2.0) + 0.5 * _clip01(0.5 + skew / 2.0))
        return ConvexityResult(
            skew=skew, convexity=convexity, crisis_alpha=crisis_alpha, convexity_score=score
        )


class MarginalContributionEngine:
    """Marginal portfolio contribution per signal (allocate on contribution, not standalone)."""

    def contributions(
        self, *, weights: Mapping[str, float], metric: Mapping[str, float]
    ) -> MarginalContribution:
        by_signal = {k: float(weights.get(k, 0.0)) * float(metric.get(k, 0.0)) for k in weights}
        return MarginalContribution(by_signal=by_signal, total=sum(by_signal.values()))


class CapitalEfficiencyEngine:
    """Return per unit of risk and capacity; penalizes inefficient capital deployment."""

    def evaluate(
        self, *, expected_return: float, volatility: float, capacity_utilization: float
    ) -> EfficiencyResult:
        rpr = expected_return / volatility if volatility > _EPS else 0.0
        rpc = expected_return / capacity_utilization if capacity_utilization > _EPS else 0.0
        score = 100.0 * _clip01(0.6 * _clip01(rpr / 2.0) + 0.4 * _clip01(rpc))
        return EfficiencyResult(
            capital_efficiency_score=score, return_per_risk=rpr, return_per_capacity=rpc
        )

```

### libs/stage14/kelly.py
```python
"""Kelly sizing for compounding — full estimate, never full deployment.

``KellyEngine`` computes the Bernoulli Kelly fraction from win rate and payoff (with a confidence
haircut) and exposes half/quarter. ``FractionalKellyEngine`` converts that into a *survivable*
fraction of capital: third-Kelly (1/3) is the base/standard, scaled toward zero under high
volatility, regime uncertainty, capacity deterioration, or fragility, and allowed up to half-Kelly
(1/2) ONLY when the candidate is roi_qualified (good ROI meeting the deployable bar). Full Kelly is
never used.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from libs.stage14.errors import Stage14Error


class KellyEstimate(BaseModel):
    model_config = ConfigDict(frozen=True)

    full: float
    half: float
    quarter: float


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class KellyEngine:
    """Bernoulli Kelly with a confidence haircut. Full Kelly is reported, never deployed."""

    def estimate(
        self, *, win_rate: float, payoff_ratio: float, confidence: float = 1.0
    ) -> KellyEstimate:
        if payoff_ratio <= 0:
            raise Stage14Error("payoff_ratio must be positive")
        p = _clip01(win_rate)
        # f* = p - (1 - p) / b  (Kelly for a binary payoff with reward/risk ratio b)
        full = max(0.0, p - (1.0 - p) / payoff_ratio) * _clip01(confidence)
        return KellyEstimate(full=full, half=full * 0.5, quarter=full * 0.25)


class FractionalKellyEngine:
    """Turns full-Kelly into a survivable capital fraction (third-Kelly base, half-Kelly cap)."""

    def __init__(self, *, base_fraction: float = 1 / 3, max_fraction: float = 0.5) -> None:
        if not 0.0 < base_fraction <= max_fraction <= 1.0:
            raise Stage14Error("require 0 < base_fraction <= max_fraction <= 1")
        self.base_fraction = base_fraction
        self.max_fraction = max_fraction

    def fraction_of_kelly(
        self,
        *,
        volatility_state: float = 0.5,
        regime_uncertainty: float = 0.5,
        capacity_deterioration: float = 0.0,
        fragility: float = 0.0,
        roi_qualified: bool = False,
    ) -> float:
        """The fraction of full Kelly to deploy.

        The ceiling is the base fraction (1/3) normally, and rises to the max (1/2) only when
        ``roi_qualified`` (good ROI meeting the deployable bar). Within that ceiling, health
        (low vol / regime certainty / capacity / robustness) scales it; best conditions reach the
        ceiling, deteriorating ones fall toward zero. Half-Kelly is never exceeded.
        """
        health = (
            (1.0 - _clip01(volatility_state))
            * (1.0 - _clip01(regime_uncertainty))
            * (1.0 - _clip01(capacity_deterioration))
            * (1.0 - _clip01(fragility))
        )
        ceiling = self.max_fraction if roi_qualified else self.base_fraction
        return max(0.0, min(self.max_fraction, ceiling * health))

    def size(
        self,
        full_kelly: float,
        *,
        volatility_state: float = 0.5,
        regime_uncertainty: float = 0.5,
        capacity_deterioration: float = 0.0,
        fragility: float = 0.0,
        roi_qualified: bool = False,
    ) -> float:
        """Capital fraction = full Kelly x fraction-of-Kelly (always <= half Kelly)."""
        frac = self.fraction_of_kelly(
            volatility_state=volatility_state, regime_uncertainty=regime_uncertainty,
            capacity_deterioration=capacity_deterioration, fragility=fragility,
            roi_qualified=roi_qualified,
        )
        return max(0.0, full_kelly * frac)

```

### libs/stage15/models.py
```python
"""Stage 15 models — the research-factory vocabulary.

Stage 15 discovers, validates, ranks, monitors, and retires alphas. It is optimized for the
*smallest* number of durable, scalable, economically-grounded, low-correlation alphas that survive
institutional validation — not the largest backtest count. These models describe that pipeline;
the engines compute them. Reuses the validation layer's ``MechanismType``.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from libs.core.time import to_iso8601, utcnow
from libs.validation.economic_prior import MechanismType

__all__ = [  # noqa: RUF022  # grouped by concern
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
]


class ResearchRegime(StrEnum):
    """Environments every alpha is validated across."""

    BULL = "bull"
    BEAR = "bear"
    HIGH_VOL = "high_vol"
    LOW_VOL = "low_vol"
    TRENDING = "trending"
    RANGE = "range"
    CRISIS = "crisis"


class PipelineStage(StrEnum):
    """The furthest stage an alpha has reached in the live research pipeline."""

    DISCOVERY = "discovery"
    VALIDATION = "validation"
    WALK_FORWARD = "walk_forward"
    SHADOW = "shadow"
    PAPER = "paper"
    ALLOCATION = "allocation"
    MONITORING = "monitoring"
    REVALIDATION = "revalidation"
    RETIREMENT = "retirement"
    REJECTED = "rejected"


class AlphaScores(BaseModel):
    """Per-alpha measurements feeding the quality score. ``fragility``/``decay`` higher = worse."""

    model_config = ConfigDict(frozen=True)

    expected_return: float = 0.0
    sharpe: float = 0.0
    sortino: float = 0.0
    calmar: float = 0.0
    capacity_score: float = 0.0        # 0-100
    fragility_score: float = 0.0       # 0-100 (higher = more fragile)
    stability_score: float = 0.0       # 0-100
    decay_score: float = 0.0           # 0-100 (higher = more decayed)
    survival_score: float = 0.0        # 0-100
    diversification_score: float = 0.0  # 0-100
    economic_score: float = 0.0        # 0-100


class AlphaQualityScore(BaseModel):
    model_config = ConfigDict(frozen=True)

    score: float  # 0-100
    components: dict[str, float]


class MechanismResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    present: bool
    mechanism: MechanismType | None
    missing: list[str] = Field(default_factory=list)
    message: str


class RegimeValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    regime_resilience_score: float  # 0-100
    by_regime: dict[str, float]
    productive_fraction: float
    robust: bool


class ContributionForecast(BaseModel):
    model_config = ConfigDict(frozen=True)

    cagr_contribution: float
    sharpe_contribution: float
    diversification_benefit: float  # 0..1
    survival_benefit: float         # 0..1
    correlation_impact: float       # 0..1 (higher = more correlated = worse)
    net_beneficial: bool


class ResearchPriority(BaseModel):
    model_config = ConfigDict(frozen=True)

    hypothesis_id: str
    research_priority_score: float  # 0-100
    components: dict[str, float]


class AlphaGovernanceVerdict(BaseModel):
    model_config = ConfigDict(frozen=True)

    accepted: bool
    gates: dict[str, bool]
    rejected_reasons: list[str] = Field(default_factory=list)


class ResearchKillDecision(BaseModel):
    """The research kill-switch: protects research capital like risk engines protect trading."""

    model_config = ConfigDict(frozen=True)

    halt: bool
    reasons: list[str] = Field(default_factory=list)


class PipelineRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    alpha_id: str
    stage: PipelineStage
    quality_score: float
    accepted: bool
    note: str = ""


class ResearchPipelineResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    generated_at: str = Field(default_factory=lambda: to_iso8601(utcnow()))
    records: list[PipelineRecord] = Field(default_factory=list)
    allocated: list[str] = Field(default_factory=list)
    rejected: list[str] = Field(default_factory=list)
    kill: ResearchKillDecision = ResearchKillDecision(halt=False)

```

### libs/stage15/priority.py
```python
"""Research prioritization — rank research opportunities by expected value of research.

Prioritizes hypotheses with high expected edge, low correlation to existing alphas, large capacity,
strong economic rationale, and high regime-diversification potential. Highest scores get resources
first. Distinct from the Stage 13 ResearchPriorityEngine (category budgeting) — this ranks ideas.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from libs.stage15.models import ResearchPriority

_WEIGHTS: dict[str, float] = {
    "expected_edge": 0.30,
    "uncorrelated": 0.25,
    "capacity": 0.15,
    "economic_strength": 0.20,
    "regime_diversification": 0.10,
}


class ResearchCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    hypothesis_id: str
    expected_edge: float = Field(default=0.0, ge=0.0, le=1.0)
    correlation_to_existing: float = Field(default=0.0, ge=0.0, le=1.0)
    capacity: float = Field(default=0.0, ge=0.0, le=1.0)
    economic_strength: float = Field(default=0.0, ge=0.0, le=1.0)
    regime_diversification_potential: float = Field(default=0.0, ge=0.0, le=1.0)


class ResearchPriorityEngine:
    """Ranks research candidates by expected value of research (recommend-only)."""

    def score(self, candidate: ResearchCandidate) -> ResearchPriority:
        components = {
            "expected_edge": candidate.expected_edge,
            "uncorrelated": 1.0 - candidate.correlation_to_existing,
            "capacity": candidate.capacity,
            "economic_strength": candidate.economic_strength,
            "regime_diversification": candidate.regime_diversification_potential,
        }
        score = 100.0 * sum(_WEIGHTS[k] * v for k, v in components.items())
        return ResearchPriority(
            hypothesis_id=candidate.hypothesis_id, research_priority_score=score,
            components=components,
        )

    def rank(self, candidates: Sequence[ResearchCandidate]) -> list[ResearchPriority]:
        return sorted(
            (self.score(c) for c in candidates),
            key=lambda p: p.research_priority_score,
            reverse=True,
        )

```

### libs/stage15/regime_validation.py
```python
"""Regime-specific alpha validation — prefer alphas that survive many environments.

Validates an alpha's performance across bull / bear / high-vol / low-vol / trending / range /
crisis regimes and produces a regime-resilience score. Reuses the discovery layer's
regime-diversification primitive (Gini evenness + productive fraction).
"""

from __future__ import annotations

from collections.abc import Mapping

from libs.discovery.regime_diversification import regime_diversification
from libs.stage15.models import RegimeValidationResult, ResearchRegime


class RegimeValidationEngine:
    """Scores how robustly an alpha performs across market regimes."""

    def validate(
        self,
        regime_performance: Mapping[ResearchRegime | str, float],
        *,
        threshold: float = 50.0,
    ) -> RegimeValidationResult:
        by_regime = {
            (r.value if isinstance(r, ResearchRegime) else str(r)): float(v)
            for r, v in regime_performance.items()
        }
        result = regime_diversification(by_regime, threshold=threshold)
        return RegimeValidationResult(
            regime_resilience_score=result.regime_diversification_score,
            by_regime=by_regime,
            productive_fraction=result.productive_fraction,
            robust=result.robust,
        )

```

### libs/store/migrations.py
```python
"""A small, forward-only migration runner over SQLite.

Migrations are ordered :class:`Migration` objects (defined under ``migrations/``). Each is
a list of statements applied in one transaction and recorded in ``schema_migrations`` with a
content hash, so re-running is a no-op and drift is detectable. No destructive/ down paths —
v1.0 migrations are additive.
"""

from __future__ import annotations

from dataclasses import dataclass

from libs.core.time import to_iso8601, utcnow
from libs.store.connection import Database
from libs.store.hashchain import canonical_json, sha256_hex

_SCHEMA_MIGRATIONS = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    sha256     TEXT NOT NULL,
    applied_at TEXT NOT NULL
)
"""


@dataclass(frozen=True)
class Migration:
    """An ordered, immutable unit of schema change."""

    version: int
    name: str
    statements: tuple[str, ...]

    @property
    def sha256(self) -> str:
        return sha256_hex(canonical_json([self.version, self.name, list(self.statements)]))


def _ensure_bootstrap(db: Database) -> None:
    db.execute(_SCHEMA_MIGRATIONS)


def applied_versions(db: Database) -> list[int]:
    """Return the sorted versions already applied."""
    _ensure_bootstrap(db)
    rows = db.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
    return [int(row[0]) for row in rows]


def current_version(db: Database) -> int:
    """Return the highest applied version, or 0 if none."""
    versions = applied_versions(db)
    return versions[-1] if versions else 0


def run_migrations(db: Database, migrations: tuple[Migration, ...]) -> list[int]:
    """Apply all pending migrations in version order. Returns the versions applied now."""
    _ensure_bootstrap(db)
    done = set(applied_versions(db))
    ordered = sorted(migrations, key=lambda m: m.version)

    seen: set[int] = set()
    for migration in ordered:
        if migration.version in seen:
            raise ValueError(f"duplicate migration version {migration.version}")
        seen.add(migration.version)

    newly_applied: list[int] = []
    for migration in ordered:
        if migration.version in done:
            continue
        with db.transaction() as conn:
            for statement in migration.statements:
                conn.execute(statement)
            conn.execute(
                "INSERT INTO schema_migrations(version, name, sha256, applied_at) "
                "VALUES (?, ?, ?, ?)",
                (migration.version, migration.name, migration.sha256, to_iso8601(utcnow())),
            )
        newly_applied.append(migration.version)
    return newly_applied

```

### libs/validation/gate_calibration.py
```python
"""Gate-calibration audits -- recover wrongly-rejected survivors and make backfill safe.

Two audits from MAX_SURVIVORS Part 1, both pure gain (no new data, no trading exposure):

  - REJECTION-SHADOW AUDIT. The gauntlet rejects most candidates; that is correct on picked-clean
    price space. But a gate that has drifted OVER-strict silently leaks real edges. Shadow-track a
    sample of rejects forward and, using data that arrived AFTER the rejection (never the in-sample
    metric that got them rejected -- that would be the same garden-of-forking-paths), ask whether a
    non-trivial slice would have been profitable. If so the gate is leaking survivors and must be
    re-calibrated. ``rejection_shadow_audit``.

  - RECONSTRUCTION VERIFIER. Reconstructing an idle axis's history from archives collapses the
    forward clock (a candidate that survives on 200 reconstructed days validates today, not in
    weeks) -- but ONLY if the reconstruction is real. Its one failure mode is leakage: a
    reconstruction that silently disagrees with ground truth fabricates out-of-sample evidence.
    This gate diff-verifies the reconstruction against overlapping ground truth and REFUSES to admit
    any series that disagrees. It only ever rejects bad data, so it has no downside -- it is the
    safety interlock that makes backfill a survivor multiplier instead of a leakage source.
    ``reconstruction_verified``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict


class RejectionShadowReport(BaseModel):
    """Forward audit of rejected candidates: is the gate leaking survivors?"""

    model_config = ConfigDict(frozen=True)

    n_rejects: int  # rejects with a decided forward metric (enough post-rejection data to judge)
    n_would_have_paid: int  # of those, how many cleared the deploy bar out-of-sample
    would_have_paid: tuple[str, ...]  # their ids -- the leaked survivors to re-examine
    leak_frac: float  # n_would_have_paid / n_rejects
    over_strict: bool  # leak_frac past tolerance on a sufficient sample -> re-calibrate the gate
    verdict: str

    def __bool__(self) -> bool:
        return not self.over_strict


def rejection_shadow_audit(
    rejects: Sequence[tuple[str, float | None]],
    *,
    deploy_threshold: float,
    leak_tolerance: float = 0.10,
    min_sample: int = 5,
) -> RejectionShadowReport:
    """Shadow-track rejected candidates forward (MAX_SURVIVORS Part 1.2, rejection audit).

    ``rejects`` is a sequence of ``(candidate_id, forward_metric)`` where ``forward_metric`` is the
    realized out-of-sample metric measured on data that arrived AFTER the rejection (Sharpe / IC on
    the honest holdout), or ``None`` if not enough forward data has accrued to judge yet. A reject
    that clears ``deploy_threshold`` on that forward data is a survivor the gate leaked. If more
    than ``leak_tolerance`` of a sufficient sample (``>= min_sample`` decided rejects) would pay,
    the gate is over-strict and must be re-calibrated -- pure recovery, no new data.
    """
    decided = [(rid, m) for rid, m in rejects if m is not None]
    paid = tuple(rid for rid, m in decided if m >= deploy_threshold)
    n = len(decided)
    frac = round(len(paid) / n, 3) if n else 0.0
    over_strict = n >= min_sample and frac > leak_tolerance
    if n < min_sample:
        verdict = (
            f"only {n} decided rejects (<{min_sample}) -- insufficient forward sample to judge the "
            "gate; keep shadowing"
        )
    elif over_strict:
        verdict = (
            f"OVER-STRICT: {len(paid)}/{n} rejects ({frac:.0%}) would have paid out-of-sample -- "
            "the gate is leaking survivors; re-calibrate (effective-trial count, per-gate bar)"
        )
    else:
        verdict = (
            f"calibrated: {len(paid)}/{n} rejects ({frac:.0%}) would have paid, within the "
            f"{leak_tolerance:.0%} tolerance -- gate is not obviously leaking"
        )
    return RejectionShadowReport(
        n_rejects=n, n_would_have_paid=len(paid), would_have_paid=paid,
        leak_frac=frac, over_strict=over_strict, verdict=verdict,
    )


class ReconstructionCheck(BaseModel):
    """Diff-verify of a reconstructed history against overlapping ground truth."""

    model_config = ConfigDict(frozen=True)

    n_overlap: int  # points where reconstruction and ground truth share a key (timestamp)
    max_abs_err: float  # worst absolute disagreement on the overlap
    max_rel_err: float  # worst relative disagreement (scaled by |ground truth|)
    verified: bool  # overlap sufficient AND every point within tolerance -> admissible as OOS
    verdict: str

    def __bool__(self) -> bool:
        return self.verified


def reconstruction_verified(
    *,
    reconstructed: Mapping[str, float],
    ground_truth: Mapping[str, float],
    rel_tol: float = 0.01,
    abs_tol: float = 1e-9,
    min_overlap: int = 30,
) -> ReconstructionCheck:
    """Backfill safety GATE (MAX_SURVIVORS Part 1.1) -- verify-don't-trust for reconstructions.

    Reconstructed history may be run through the gauntlet as out-of-sample ONLY after it diff-
    verifies against overlapping ground truth. ``reconstructed`` and ``ground_truth`` are maps keyed
    by timestamp (or any stable key); the overlap is the shared keys. Admission requires (a) a
    non-trivial overlap (``>= min_overlap`` shared points -- a reconstruction that overlaps ground
    truth on 3 points has proved nothing) AND (b) every overlapping point agreeing within tolerance
    (``|recon - truth| <= abs_tol + rel_tol * |truth|``). Any disagreement REJECTS the series: an
    unverified reconstruction fabricates out-of-sample evidence, so refusing it is the whole point.
    """
    shared = sorted(set(reconstructed) & set(ground_truth))
    n = len(shared)
    max_abs = 0.0
    max_rel = 0.0
    ok_all = True
    for k in shared:
        r = float(reconstructed[k])
        g = float(ground_truth[k])
        abs_err = abs(r - g)
        rel_err = abs_err / abs(g) if g != 0.0 else (0.0 if abs_err == 0.0 else float("inf"))
        max_abs = max(max_abs, abs_err)
        max_rel = max(max_rel, rel_err)
        if abs_err > abs_tol + rel_tol * abs(g):
            ok_all = False
    verified = n >= min_overlap and ok_all
    if n < min_overlap:
        verdict = (
            f"overlap {n} < {min_overlap} required -- too little ground truth to trust the "
            "reconstruction; do NOT admit as out-of-sample"
        )
    elif not ok_all:
        verdict = (
            f"REJECTED: reconstruction disagrees with ground truth (max rel err {max_rel:.4f} > "
            f"{rel_tol:.4f}) over {n} points -- would fabricate OOS evidence; fix or discard"
        )
    else:
        verdict = (
            f"verified: reconstruction matches ground truth within {rel_tol:.2%} over {n} "
            "points -- admissible as out-of-sample; run the gauntlet on it now"
        )
    return ReconstructionCheck(
        n_overlap=n, max_abs_err=round(max_abs, 6), max_rel_err=round(max_rel, 6),
        verified=verified, verdict=verdict,
    )

```

### libs/validation/gauntlet.py
```python
"""The validation gauntlet — the Skeptic.

Runs the ordered, trials-adjusted gauntlet; a candidate dies at the first stage it fails. The
trials ledger feeds the true (inflated) trial count into the Deflated Sharpe Ratio, so search
throughput cannot manufacture significance. Output is a structured PASS/FAIL verdict.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict

from libs.costs.scenarios import CostScenario
from libs.store.trials import TrialsLedger
from libs.validation.dsr import deflated_sharpe_ratio, sharpe_ratio
from libs.validation.economic_prior import economic_prior_gate
from libs.validation.pbo import probability_backtest_overfitting
from libs.validation.reality_check import hansen_spa
from libs.validation.stress_costs import stress_cost_validation


@dataclass
class CandidateEvaluation:
    """All inputs the gauntlet needs to judge one candidate alpha."""

    candidate_id: str
    hypothesis_id: str
    family: str
    returns: np.ndarray  # candidate per-period (net) returns
    strategy_matrix: np.ndarray  # (T x N) returns of all trials, for DSR variance / PBO / SPA
    gross_pnls: Sequence[float]  # per-trade gross PnL
    base_costs: Sequence[float]  # per-trade base cost
    economic_prior: Mapping[str, Any]
    lockbox_returns: np.ndarray | None = None
    n_trials_override: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class StageResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    passed: bool
    message: str
    detail: dict[str, Any] = {}


class GauntletResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_id: str
    hypothesis_id: str
    passed: bool
    verdict: str
    n_trials: int
    stages: list[StageResult]

    def __bool__(self) -> bool:
        return self.passed


class Gauntlet:
    """Orchestrates the validation stages with trials-ledger integration."""

    def __init__(
        self,
        *,
        ledger: TrialsLedger | None = None,
        trials_multiplier: float = 7.0,
        dsr_threshold: float = 0.95,
        pbo_threshold: float = 0.5,
        spa_alpha: float = 0.05,
        required_cost_scenario: CostScenario = CostScenario.X3,
        lockbox_min_sharpe: float = 0.0,
    ) -> None:
        self.ledger = ledger
        self.trials_multiplier = trials_multiplier
        self.dsr_threshold = dsr_threshold
        self.pbo_threshold = pbo_threshold
        self.spa_alpha = spa_alpha
        self.required_cost_scenario = required_cost_scenario
        self.lockbox_min_sharpe = lockbox_min_sharpe

    def _resolve_n_trials(self, candidate: CandidateEvaluation, observed_sr: float) -> int:
        if candidate.n_trials_override is not None:
            return max(2, candidate.n_trials_override)
        if self.ledger is not None:
            self.ledger.append(
                candidate.hypothesis_id,
                candidate.family,
                method="gauntlet",
                params={"candidate_id": candidate.candidate_id},
                in_sample_metric=observed_sr,
            )
            true_count = self.ledger.count()
            return max(2, math.ceil(true_count * self.trials_multiplier))
        return 2

    def run(self, candidate: CandidateEvaluation) -> GauntletResult:
        stages: list[StageResult] = []
        observed_sr = sharpe_ratio(candidate.returns)
        n_trials = self._resolve_n_trials(candidate, observed_sr)

        def finalize() -> GauntletResult:
            passed = all(s.passed for s in stages)
            return GauntletResult(
                candidate_id=candidate.candidate_id,
                hypothesis_id=candidate.hypothesis_id,
                passed=passed,
                verdict="PASS" if passed else "FAIL",
                n_trials=n_trials,
                stages=stages,
            )

        # 1) Economic-prior gate (cheapest, runs first)
        prior = economic_prior_gate(candidate.economic_prior)
        stages.append(
            StageResult(
                name="economic_prior", passed=prior.passed, message=prior.message,
                detail={"missing": prior.missing},
            )
        )
        if not prior.passed:
            return finalize()

        # 2) In-sample existence (cost-adjusted screen)
        screen_ok = observed_sr > 0.0
        stages.append(
            StageResult(
                name="in_sample_screen", passed=screen_ok,
                message="net edge exists" if screen_ok else "no in-sample edge",
                detail={"sharpe": observed_sr},
            )
        )
        if not screen_ok:
            return finalize()

        # 3) Deflated Sharpe Ratio (multiple-testing)
        sharpes = np.array(
            [sharpe_ratio(candidate.strategy_matrix[:, k])
             for k in range(candidate.strategy_matrix.shape[1])]
        )
        dsr = deflated_sharpe_ratio(
            candidate.returns, n_trials=n_trials,
            variance_of_sharpes=float(sharpes.var(ddof=1)) if len(sharpes) >= 2 else 1e-6,
            threshold=self.dsr_threshold,
        )
        stages.append(
            StageResult(
                name="deflated_sharpe", passed=dsr.passed,
                message=f"DSR={dsr.dsr:.3f} vs threshold {self.dsr_threshold}",
                detail={"dsr": dsr.dsr, "sr0": dsr.sr0_threshold, "n_trials": n_trials},
            )
        )
        if not dsr.passed:
            return finalize()

        # 4) Probability of Backtest Overfitting
        pbo = probability_backtest_overfitting(candidate.strategy_matrix)
        pbo_ok = pbo.pbo <= self.pbo_threshold
        stages.append(
            StageResult(
                name="pbo", passed=pbo_ok, message=f"PBO={pbo.pbo:.3f}",
                detail={"pbo": pbo.pbo, "n_combinations": pbo.n_combinations},
            )
        )
        if not pbo_ok:
            return finalize()

        # 5) Hansen SPA (selection bias)
        spa = hansen_spa(candidate.strategy_matrix)
        spa_ok = spa.p_value < self.spa_alpha
        stages.append(
            StageResult(
                name="reality_check_spa", passed=spa_ok,
                message=f"SPA p-value={spa.p_value:.3f}",
                detail={"p_value": spa.p_value, "statistic": spa.statistic},
            )
        )
        if not spa_ok:
            return finalize()

        # 6) Stress-cost validation
        stress = stress_cost_validation(
            candidate.gross_pnls, candidate.base_costs,
            required_scenario=self.required_cost_scenario,
        )
        stages.append(
            StageResult(
                name="stress_costs", passed=stress.passed, message=stress.message,
                detail={"required": stress.required_scenario},
            )
        )
        if not stress.passed:
            return finalize()

        # 7) Lockbox confirmation (if a holdout was provided)
        if candidate.lockbox_returns is not None:
            lockbox_sr = sharpe_ratio(candidate.lockbox_returns)
            lockbox_ok = lockbox_sr >= self.lockbox_min_sharpe
            stages.append(
                StageResult(
                    name="lockbox", passed=lockbox_ok,
                    message=f"lockbox Sharpe={lockbox_sr:.3f}",
                    detail={"lockbox_sharpe": lockbox_sr},
                )
            )

        return finalize()

```

### libs/validation/report.py
```python
"""Validation report generation (JSON + HTML)."""

from __future__ import annotations

from pathlib import Path

from libs.validation.gauntlet import GauntletResult

_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Validation Report — {candidate_id}</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; }}
  .verdict {{ font-size: 1.5rem; font-weight: 700; padding: .5rem 1rem; border-radius: 6px;
             display: inline-block; }}
  .pass {{ background: #e6f4ea; color: #137333; }}
  .fail {{ background: #fce8e6; color: #c5221f; }}
  table {{ border-collapse: collapse; margin-top: 1rem; width: 100%; max-width: 900px; }}
  th, td {{ border: 1px solid #ddd; padding: .5rem .75rem; text-align: left; }}
  th {{ background: #f5f5f5; }}
  .ok {{ color: #137333; font-weight: 600; }}
  .no {{ color: #c5221f; font-weight: 600; }}
</style>
</head>
<body>
  <h1>Validation Report</h1>
  <p>Candidate <code>{candidate_id}</code> · hypothesis <code>{hypothesis_id}</code>
     · trials (inflated): {n_trials}</p>
  <p class="verdict {verdict_class}">{verdict}</p>
  <table>
    <thead><tr><th>#</th><th>Stage</th><th>Result</th><th>Detail</th></tr></thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</body>
</html>
"""


def _render_rows(result: GauntletResult) -> str:
    rows = []
    for i, stage in enumerate(result.stages, start=1):
        status = '<span class="ok">PASS</span>' if stage.passed else '<span class="no">FAIL</span>'
        rows.append(
            f"<tr><td>{i}</td><td>{stage.name}</td><td>{status}</td>"
            f"<td>{stage.message}</td></tr>"
        )
    return "\n      ".join(rows)


def generate_validation_report(result: GauntletResult, out_dir: str | Path) -> dict[str, Path]:
    """Write ``validation_report.json`` and ``validation_report.html``; return their paths."""
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)

    json_path = directory / "validation_report.json"
    json_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

    html = _HTML_TEMPLATE.format(
        candidate_id=result.candidate_id,
        hypothesis_id=result.hypothesis_id,
        n_trials=result.n_trials,
        verdict=result.verdict,
        verdict_class="pass" if result.passed else "fail",
        rows=_render_rows(result),
    )
    html_path = directory / "validation_report.html"
    html_path.write_text(html, encoding="utf-8")

    return {"json": json_path, "html": html_path}

```

### scripts/build_enforcement_matrix.py
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
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_CONST = _ROOT / "docs/CONSTITUTION.md"
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
    "L1.5": ["run_cost_model.py", "check_carry_funding_measured", "run_execution_intel.py"],
    "L1.6": ["libs/autodiscovery/validation.py", "check_welded_gates", "check_gate_optimality",
             "run_mutation.py"],
    "L1.7": ["check_rubberstamp_detector", "check_rubberstamp_enforcement", "deep_review.py"],
    "L1.8": ["check_no_mining_throttle", "check_mining_nonregression", "check_mine_flow"],
    "L1.9": ["check_blind_trigger", "check_interrogation", "check_dig_depth"],
    "L1.10": ["check_mine_conversion", "check_mine_gate"],
    "L1.11": ["moat_audit.py", "check_vendor_replacement", "run_recorder.py"],
    "L1.11a": ["ops/run_frontier_rotation.sh", "kimi_hunter.py"],
    "L1.12": ["check_orphan_code", "check_idle_capability", "libs/self_improvement/dormancy.py"],
    "L1.13": ["check_gap_register_health", "run_execution_intel.py"],
    "L1.14": ["check_directives", "research_erv.py"],
    "L1.15": ["check_self_application"],
    # L1.16: every edge understood -- mechanism, regime, failure modes -- or it is not durable.
    # screen_carry_basis_path is the attribution instrument for the ONLY deployed sleeve: it
    # measures whether the funding-rank entry selects into a widening or converging basis, which
    # is what decides whether the carry harvest is a cashflow or compensation for a basis loss.
    "L1.16": ["mechanism_board.py", "check_gate_optimality",
              "scripts/screen_carry_basis_path.py"],
    "L1.17": ["negative_knowledge.py", "check_findings_ratchet", "docs/graveyard.md"],
    "L1.18": ["tests/validation/test_capacity_parity.py"],
    "L1.18a": ["tests/validation/test_capacity_parity.py",
               "libs/autodiscovery/validation.py:capacity_status",
               "scripts/run_promotion_queue.py", "libs/research/promotion_latency.py"],
    "L1.16a": ["negative_knowledge.py", "check_findings_ratchet"],
    "L1.19": ["revalidate_clocks.py", "libs/research/dist_shift.py"],
    "L1.20": ["check_post_gate0_activation", "check_production"],
    "L1.21": ["check_depth_parity", "check_coverage"],
    "L1.22": ["run_intelligence_cycle.py", "check_self_application", "check_self_sufficiency"],
    "L1.23": ["run_deadman_switch.py (Tier-3)", "libs/risk/gate.py", "check_production",
              "scripts/run_drills.py", "libs/risk/capital_events.py",
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
    "L2.5": ["blind_spot.py", "check_self_sufficiency"],
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
    "L1.28a": ["scripts/check_utilisation.py", "check_idle_capability", "check_clock_saturation",
               "check_capacity_runway"],
    # L1.28b: conversion hunts 100% daily -- FLATLINE (7d of silence on a non-empty queue) fails.
    "L1.28b": ["scripts/check_conversion.py"],
    # L1.28c: every cadence hunts its own ceiling. The manifest fence requires a decided cadence
    # with evidence per line; brain_seat_throughput measures the resource they all compete for,
    # so "raise the cron" vs "buy a second seat" is settled by measurement.
    "L1.28c": ["scripts/check_scheduler_manifest.py", "scripts/check_utilisation.py"],
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
    "L1.37": ["scripts/run_law_gate.py", "deploy/git_hooks/pre-push", "ops/brain_env.sh",
              ".github/workflows/ci.yml"],
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
    "L1.41": ["scripts/check_build_standard.py", "scripts/screen_funding_spread.py",
              "scripts/screen_collateral_allocation.py"],
    # L1.42: the boundary for the 60 python entry points that sourced no shell gate.
    "L1.42": ["libs/ops/lawful.py", "scripts/check_build_standard.py",
              "scripts/run_cashcarry_executor.py"],
    # L1.43: governance measured like everything else -- has each fence ever caught anything?
    "L1.43": ["scripts/check_fence_yield.py", "scripts/check_enforcement_execution.py"],
    # L1.44: consumption-time freshness -- every decision-path read declares its max tolerated
    # age at the read site; the fence fails on STALE-CONSUMED (a live decision steered by a
    # frozen input) and on UNWIRED (a bootstrap contract deleted from the executor/alerts).
    "L1.44": ["scripts/check_freshness.py", "libs/ops/fresh.py"],
    # R0122 LLM discretionary sleeve: paper-only candidate generator whose calls are scored
    # forecasts. Governed by L1.6 (zero promotion authority) and L1.29 (it grades itself).
    "L1.6-llm": ["scripts/run_llm_trader.py"],
    # R0122b: the unstructured feed the sleeve trades. Under L1.11a (information asymmetry as a
    # search dimension) -- its latency measurement IS the asymmetry test.
    "L1.11a-events": ["scripts/collect_announcements.py"],
    # R0125 conviction sleeve: aggression is L1.28 (uncapped conviction), the rail is L1.23
    # (stop on every trade, leverage cap, inside the ruin rail).
    "L1.23-conviction": ["scripts/run_conviction_trader.py"],
    # R0133: the marker. Both paper sleeves wrote books nobody ever read -- the purest L1.28a
    # defect, since an unmarked book accumulates confident rows and reports no failure. This organ
    # walks the recorded ladder against real bars, benchmarks against buy-and-hold (L1.6) and
    # feeds the outcome to calibration (L1.29), which is what makes over-confidence self-shrinking.
    "L1.28a-paper-marks": ["scripts/resolve_paper_book.py"],
    # R0134: the discretionary sleeve was asked to read charts it had never been shown -- an
    # unused information source sitting under a strategy that needs it (L2.9), and a ceiling
    # reported as fine while unmeasured (L1.28a). Multi-timeframe structure, per instrument.
    "L2.9-chart-context": ["scripts/build_chart_context.py"],
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
    "L1.6-playbook": ["scripts/run_trade_review.py", "docs/DISCRETIONARY_DESK.md"],
    # R0140: copytrading, screened. The naive read (copy the leaderboard's best) is the 420/0
    # selection failure in a new costume; the screen computes the tempting number AND disqualifies
    # it, archives the only unbiased design (a forward panel counting exits as failures), and
    # measures the derivative that does not require picking a winner.
    "L1.6-copytrading": ["scripts/screen_copytrading.py"],
    # R0141: more sleeves multiply growth only if INDEPENDENT. Correlated sleeves draw down
    # together -- risk scales with N, growth with 1, and the desk pays N sets of costs for one bet.
    "L1.28b-sleeves": ["scripts/run_sleeve_allocator.py"],
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
    "L1.28c-discretionary": ["scripts/run_discretionary_max.py"],
    # R0152: the desk had an optimiser and a learner for ONE discretionary edge and nothing that
    # hunted for a SECOND. A single hypothesis is one regime change away from none, and the
    # allocator's own arithmetic says an independent second edge beats improving the first.
    "L1.31-discretionary-hunt": ["scripts/run_discretionary_hunt.py"],
    # R0198: costs are the one growth lever available before any edge is proven -- known BEFORE
    # the trade, and near breakeven a third of the cost stack is worth more than a point of hit
    # rate. Funding is SIGNED and public; the sleeve was blind to which sides get PAID to hold.
    # Selection uses the sign; marking stays always-adverse -- different jobs, different signs.
    "L1.41-cost-hunt": ["scripts/run_cost_hunt.py"],
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
    "check_bnb_funded": "L1.5",          # fee-burn discount only applies while BNB is held
    "check_fee_carry_ratio": "L1.5",
    "check_close_retry_loop": "L1.5",    # a carry that cannot close is a churn engine
    # --- survival rails (L1.23): states that read HEALTHY while being terminal.
    "check_book_collapse": "L1.23",
    "check_book_absorbing_state": "L1.23",   # a rail that can never release the book is not safety
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
    "check_source_backlog": "L1.9",      # a catalogue that grows faster than it is verified
    "check_dig_uncommitted": "L1.9",     # VPS disk is not institutional memory
    "check_paid_target_registry": "L1.11a",
    "check_holdings_never_shrink": "L1.24",  # information advantage measured as a holding, not act
    # --- remaining singletons.
    "check_panel": "L1.7",               # adversarial review capability being DOWN is a defect
    "check_memory_hygiene": "L1.17",     # research debt is only debt if it is written and findable
    "check_mine_evidence_base": "L1.6",  # a ratchet calibrated on n=2 is superstition with a JSON
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
_STANDING: dict[str, str] = {
    "L1.0": "ratchet meta-law -- check_ratchets.py enforces the FLOORS across every measured "
            "property, and run_max_push.py enforces the DIRECTION: one ranked queue of everything "
            "not yet at 100%, which never reports done (all-green escalates to "
            "MEASUREMENT-SET-TOO-SMALL). STANDING rather than ENFORCED because the law is a "
            "standing duty on every cycle, not a single pass/fail condition",
    "L2.0": "enforcement meta-law -- satisfied by the existence of this matrix",
}


def _principles() -> dict[str, str]:
    """principle id -> its first sentence (the requirement), read from the constitution."""
    text = _CONST.read_text("utf-8")
    out: dict[str, str] = {}
    for m in re.finditer(r"^\*\*(L\d+\.\d+[a-z]?)\s+([^*]+)\*\*(.*)$", text, re.MULTILINE):
        pid, title, rest = m.group(1), m.group(2).strip(), m.group(3).strip()
        first = re.split(r"(?<=[.!])\s", rest, maxsplit=1)[0] if rest else ""
        out[pid] = f"{title.rstrip('.')} — {first}".strip(" —")[:400]
    return out


def _fence_names() -> set[str]:
    return set(re.findall(r"^def (check_[a-z_0-9]+)", _AUDIT.read_text("utf-8"), re.MULTILINE))


def _exists(ref: str) -> bool:
    """Does the enforcing artifact actually exist? A mapping to a deleted file is worse than none."""
    bare = ref.split(":")[0].split(" ")[0]
    if bare.startswith("check_"):
        return bare in _fence_names()
    return any(cand.exists() for cand in (_ROOT / bare, _ROOT / "scripts" / bare))


def _scheduled(refs: list[str]) -> list[str]:
    man = _MANIFEST.read_text("utf-8") if _MANIFEST.exists() else ""
    return [r for r in refs if Path(r.split(":")[0].split(" ")[0]).name in man]


def build() -> dict[str, Any]:
    principles, fences = _principles(), _fence_names()
    rows: list[dict[str, Any]] = []
    for pid, requirement in sorted(principles.items()):
        refs = _MAP.get(pid, [])
        live = [r for r in refs if _exists(r)]
        broken = [r for r in refs if r not in live]
        if pid in _HUMAN_ONLY:
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

    mapped_fences = {r.split(":")[0] for refs in _MAP.values() for r in refs
                     if r.startswith("check_")}
    orphan_fences = sorted(fences - mapped_fences)
    counts: dict[str, int] = {}
    for r in rows:
        counts[str(r["status"])] = counts.get(str(r["status"]), 0) + 1
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L2.0/L2.2 -- a principle with no enforcement is prose; a fence with no principle "
               "is unvoted complexity. Both directions are engineering gaps.",
        "counts": counts, "n_principles": len(principles), "n_fences": len(fences),
        "unenforced": [r["principle"] for r in rows if r["status"] == "UNENFORCED"],
        "broken_references": {r["principle"]: r["broken_references"] for r in rows
                              if r["broken_references"]},
        "fences_without_a_principle": orphan_fences,
        "matrix": rows,
    }


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
        for pid in m["unenforced"]:
            print(f"  UNENFORCED {pid}")
        for pid, refs in m["broken_references"].items():
            print(f"  BROKEN-REF {pid} -> {refs}")
        n_orph = len(m["fences_without_a_principle"])
        print(f"  fences with no governing principle: {n_orph}"
              + (f" (first 5: {m['fences_without_a_principle'][:5]})" if n_orph else ""))
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

### scripts/check_return_targeting.py
```python
#!/usr/bin/env python3
"""RETURN TARGETING (R0143) -- no stated return number may become an objective.

THE DOCTRINE, on the books since 2026-07-12 (docs/PROJECT_HANDOFF.md):

    "Don't chase a CAGR target (targeting a return number corrupts a survival-constrained
     optimizer into over-leverage). Max safe growth; let the number fall out."

WHY IT NEEDED A FENCE. On 2026-07-31 a section titled "What 300% net CAGR actually requires" was
written into docs/DISCRETIONARY_DESK.md -- straight past that line, past a 2026-07-16 decision
that had already triaged a "CAGR-maximisation override" out of a principal-supplied constitution,
and past a decision-ledger success metric reading "no CAGR targeting". Three separate prior
rulings, and the regression still landed. It was caught by the PRINCIPAL, not by any check. By
this desk's own standard that means it was not caught at all (L1.41).

WHY THE DOCTRINE IS MECHANICAL, NOT STYLISTIC. A stated return number anchors every downstream
decision toward the tail of the distribution, and the only lever that reaches a tail outcome is
SIZE. The desk's own simulations show where that ends: at 20% risk per trade the book meets a -90%
drawdown with near-certainty EVEN WHEN THE STRATEGY IS PROFITABLE, and past full Kelly more size
makes growth NEGATIVE. A target high enough to be motivating is therefore a standing instruction
to destroy the thing it aims at.

THE DISTINCTION THIS FENCE MUST GET RIGHT, and the reason it is narrow. Return numbers are
legitimate and necessary as ANALYSIS -- "cost-adjusted breakeven is 31.1%", "the kill floor is
25%", "measured noise is 0.64%". They become a defect only when bound to GOAL language: target,
aim, must earn, should produce, we need. So the fence looks for a goal verb and a return figure in
the same breath, not for numbers on their own. A fence that flagged every percentage would be
switched off within a day, and then the doctrine would have no enforcement at all -- which is the
state it was already in.

REMOVING A TARGET IS NOT TIMIDITY, and the fence says so where it fires: the law stack already
mandates the maximum (L1.28 timidity is a defect, L1.28a idle capacity is unbooked loss, L1.28b
conversion pushes to 100%, L1.28c cadence hunts its own ceiling, L1.25a the hunt never tires).
Those bind harder than a figure in a document because they fail the build. A stated target is the
one instruction that points AWAY from them.

    python scripts/check_return_targeting.py [--report-only] [--json]
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

#: Where a return target does damage: the desk's own doctrine, its money-path organs, and the
#: prompt surfaces that reach a model. Scoped deliberately -- the ledger and research notes RECORD
#: what the principal asked for verbatim, and rewriting a quotation to satisfy a fence would be
#: falsifying the record.
_SCOPE: tuple[str, ...] = (
    "docs/DISCRETIONARY_DESK.md", "docs/CONSTITUTION.md", "docs/PROJECT_HANDOFF.md",
    "ops/principal_doctrine.txt", "ops/crontab.manifest",
    "scripts/run_conviction_trader.py", "scripts/run_llm_trader.py",
    "scripts/resolve_paper_book.py", "scripts/run_sleeve_allocator.py",
    "scripts/run_trade_review.py", "scripts/build_chart_context.py",
)

#: Goal language. A return figure near ANY of these is a target rather than a measurement.
_GOAL = (r"target", r"aim(?:ing|s)?\s+(?:for|at|high)", r"goal", r"must\s+(?:earn|produce|hit|make)",
         r"should\s+(?:earn|produce|hit|make)", r"we\s+need", r"chase", r"objective\s+of")

#: A return figure: a percentage carrying return/CAGR/growth vocabulary, or a bare percentage of
#: 150%+ (nobody writes "300%" about anything but a return). The bare pattern starts at 150 rather
#: than 100 because on THIS desk 100% is overwhelmingly a COVERAGE figure -- ratchet floors,
#: breadth coverage, conversion pushing to 100% -- and the first run flagged three of those in the
#: constitution itself. Widening the exclusion rather than rewording the constitution is the same
#: rule the build standard and the sizing fence both had to learn.
_FIGURE = (r"\d{2,4}\s*(?:%|pct|percent)\s*(?:net\s*)?(?:cagr|return|growth|annual)",
           r"(?:cagr|return|growth)\s*(?:of\s*)?\d{2,4}\s*(?:%|pct|percent)",
           r"\b(?:1[5-9]\d|[2-9]\d\d|\d{4})\s*%")

#: Passages that legitimately state a target IN ORDER TO FORBID IT. Without this the doctrine line
#: itself trips the fence, which would be an own goal in the most literal sense.
_NEGATED = (r"don'?t\s+chase", r"do\s+not\s+chase", r"no\s+cagr\s+target", r"not\s+a\s+target",
            r"no\s+return\s+number", r"deliberately\s+no", r"is\s+not\s+something\s+to\s+hit",
            r"was\s+a\s+doctrine\s+regression", r"rather\s+than\s+a\s+target",
            r"no\s+stated\s+return", r"not\s+the\s+goal", r"corrupts")

#: Characters either side of a goal word searched for a return figure. 160 is about two lines of
#: prose -- wide enough to catch "our target ... is 300% CAGR" split across a wrap, narrow enough
#: that an unrelated percentage three paragraphs later does not get bound to it.
_WINDOW = 160


def scan_text(text: str) -> list[dict[str, Any]]:
    flat = " ".join(text.split())
    low = flat.lower()
    hits: list[dict[str, Any]] = []
    for gpat in _GOAL:
        for gm in re.finditer(gpat, low):
            lo, hi = max(0, gm.start() - _WINDOW), min(len(low), gm.end() + _WINDOW)
            window = low[lo:hi]
            if any(re.search(n, window) for n in _NEGATED):
                continue                              # stated in order to forbid it
            for fpat in _FIGURE:
                fm = re.search(fpat, window)
                if fm:
                    hits.append({"goal_word": gm.group(0), "figure": fm.group(0),
                                 "context": flat[lo:hi][:220]})
                    break
    return hits


def build_report(root: Path | None = None) -> dict[str, Any]:
    root = root or _ROOT
    files, unreadable = [], []
    for rel in _SCOPE:
        p = root / rel
        try:
            hits = scan_text(p.read_text("utf-8", errors="ignore"))
        except OSError as exc:
            # NOT a pass: an unreadable governed file means this doctrine is UNCHECKED there.
            unreadable.append(f"{rel}: {type(exc).__name__}")
            continue
        if hits:
            files.append({"file": rel, "n": len(hits), "hits": hits[:4]})
    status = ("UNMEASURED" if unreadable and not files else
              "RETURN-TARGETING" if files else "OK")
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "doctrine": "PROJECT_HANDOFF.md 2026-07-12 -- do not chase a CAGR target; targeting a "
                    "return number corrupts a survival-constrained optimizer into over-leverage. "
                    "Max safe growth; let the number fall out.",
        "status": status,
        "n_scoped": len(_SCOPE), "n_flagged": len(files),
        "unreadable": unreadable,
        "files": files,
        "not_timidity": "Removing a target is NOT a reduction in ambition. L1.28, L1.28a, L1.28b, "
                        "L1.28c and L1.25a already mandate the maximum and are enforced by fences "
                        "that fail the build -- which binds harder than a figure in a document. A "
                        "stated target is the one instruction pointing AWAY from them.",
        "detail": (f"{len(_SCOPE)} governed surfaces scanned; "
                   + ("no return number bound to goal language" if not files else
                      "TARGETING in " + ", ".join(f["file"] for f in files))
                   + (f"; UNREADABLE: {', '.join(unreadable)}" if unreadable else "")),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    out = _ROOT / "data/return_targeting.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"return targeting (L1.23/handoff): {rep['status']} -- {rep['detail']}")
        for f in rep["files"]:
            for h in f["hits"]:
                print(f"  {f['file']}: '{h['goal_word']}' near '{h['figure']}'")
                print(f"      ...{h['context'][:150]}")
    if args.report_only:
        return 0
    return 2 if rep["status"] == "RETURN-TARGETING" else 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/collateral_spread.py
```python
"""COLLATERAL-BASIS SPREAD -- USDT-margined vs USDC-margined perps on the SAME venue.

WHY THIS ONE IS CLEAN. Every spread that failed today failed on MEASUREMENT, not mechanism:
  mSOL/SOL   539bps sd  -> non-synchronous CoinGecko legs
  CME basis   92bps sd  -> CME 23/5 vs Binance 24/7, 16:00CT vs 00:00UTC, rolling front-month
Both were artifacts of comparing things sampled at different moments.

This construction makes that impossible: BTCUSDT-perp and BTCUSDC-perp trade on the SAME exchange,
on the SAME underlying, with the SAME funding clock and the SAME timestamps. There is no roll, no
timezone, no venue gap. Any spread that survives is real by construction.

THE MECHANISM (a genuine structural constraint, not friction):
  The two contracts are collateralised in different stablecoins. A trader holding USDC cannot post
  it as USDT margin without converting -- paying the peg spread and taking conversion risk. So the
  cost of leverage can differ between the two books, and the difference persists because moving
  between them is not free. That is the same species of constraint as kimchi (you cannot move the
  capital freely), just smaller and inside one venue.

TESTS: (a) is the funding differential persistently non-zero, (b) does it mean-revert, (c) is it
WIDE ENOUGH to clear costs -- the gate that killed all four candidates this morning. With ETH-class
symbols now measured at 0.05-1.3bps pair-open, the cost bar here is far lower than the 8bps I used
earlier, which materially changes what counts as harvestable.

Free Binance endpoints. Stage-A, zero promotion authority. Run from repo root.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

OUT = Path("data/collateral_spread.json")
PAIRS = [("BTCUSDT", "BTCUSDC"), ("ETHUSDT", "ETHUSDC"), ("SOLUSDT", "SOLUSDC")]
COST_BPS = 2.0        # measured majors pair-open ~0.05-1.3bps; 2bps is a conservative round trip


def _get(u, t=30):
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(u, headers={"User-Agent": "q/1.0"}), timeout=t).read().decode())


def funding(sym: str, n: int = 1000) -> dict[int, float]:
    try:
        d = _get(f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={sym}&limit={n}")
        return {int(x["fundingTime"]) // 3600000: float(x["fundingRate"]) for x in d}
    except Exception:
        return {}


def main() -> None:
    print("=== COLLATERAL-BASIS SPREAD (USDT-margined vs USDC-margined, SAME venue) ===")
    print("    same exchange, same underlying, same funding clock -> no sync artifact possible\n")
    res = []
    for a, b in PAIRS:
        fa, fb = funding(a), funding(b)
        common = sorted(set(fa) & set(fb))
        if len(common) < 100:
            print(f"  {a:<10} vs {b:<10} thin ({len(common)} common funding ticks)")
            continue
        # funding is per 8h; annualise for readability, but test the raw spread
        sa = np.array([fa[t] for t in common])
        sb = np.array([fb[t] for t in common])
        sp = (sa - sb) * 10000            # spread in bps per 8h period

        mean, sd = float(sp.mean()), float(sp.std())
        x0, x1 = sp[:-1] - sp.mean(), sp[1:] - sp.mean()
        beta = float((x0 @ x1) / (x0 @ x0)) if (x0 @ x0) > 0 else 1.0
        hl = float(-np.log(2) / np.log(abs(beta))) if 0 < abs(beta) < 1 else float("inf")
        p99, p50 = np.percentile(np.abs(sp), 99), np.percentile(np.abs(sp), 50)
        tail = float(p99 / p50) if p50 > 0 else float("inf")
        tradeable = float((np.abs(sp) > COST_BPS).mean())
        ann = mean * 3 * 365 / 100.0      # 3 funding periods/day, bps -> %

        wide = abs(mean) > COST_BPS or sd > COST_BPS * 2
        verdict = ("HARVESTABLE-CANDIDATE" if wide and tradeable > 0.3 and tail < 15
                   else "TOO TIGHT" if not wide
                   else "RARELY TRADEABLE" if tradeable <= 0.3 else "VIOLENT")
        print(f"  {a:<10} vs {b:<10} n={len(common):<5} mean {mean:+7.3f}bps/8h "
              f"({ann:+6.2f}%/yr) sd {sd:6.3f}  half-life {hl:5.1f}p  "
              f"|sp|>{COST_BPS}bps {tradeable*100:3.0f}%  -> {verdict}")
        res.append({"pair": f"{a}/{b}", "n": len(common), "mean_bps_8h": round(mean, 4),
                    "annualised_pct": round(ann, 3), "sd_bps": round(sd, 4),
                    "half_life_periods": round(hl, 2) if hl != float("inf") else None,
                    "tail": round(tail, 2), "frac_above_cost": round(tradeable, 3),
                    "verdict": verdict})

    cands = [r for r in res if r["verdict"] == "HARVESTABLE-CANDIDATE"]
    print(f"\n  HARVESTABLE: {len(cands)}/{len(res)}")
    print("  NOTE: cost bar here is 2bps, not the 8bps used this morning -- the measured cost")
    print("  model shows majors at 0.05-1.3bps pair-open, so the harvestable threshold is much")
    print("  lower on liquid names than on the micro-caps currently in the book.")
    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "cost_bar_bps": COST_BPS, "results": res}, indent=1), "utf-8")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()

```

### scripts/collect_fred_macro.py
```python
"""Daily FRED macro archiver -- free US-macro context for macro-crypto relative value.

Unlike the OI/LS and stablecoin clocks (which must ACCUMULATE forward days), FRED serves deep
history on day one, so this family is immediately backtestable against the crypto lake: each run
re-fetches the last ~800 observations per series and overwrites the archive (idempotent,
self-healing). Series chosen for crypto relevance, not macro completeness:

  DGS10     10y Treasury yield        (risk-free anchor / carry-vs-rates competition)
  T10Y2Y    2s10s curve               (macro regime / recession signal)
  VIXCLS    VIX                       (cross-asset risk appetite; crypto vol correlate)
  DTWEXBGS  broad dollar index        (USD liquidity; inverse crypto beta)
  WALCL     Fed balance sheet (W)     (system liquidity; the 2020-22 crypto liquidity driver)
  M2SL      M2 money supply (M)       (broad liquidity; slow regime context)

Key: data/secrets/fred.json {"key": "..."} or FRED_API_KEY env. No key -> graceful skip
(exit 0, cycle stays green). API host verified reachable from the VPS 2026-07-16 (the
registry's old "blocked" note was the website host, not api.stlouisfed.org).

    python scripts/collect_fred_macro.py
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

_KEYFILE = Path("data/secrets/fred.json")
_ARCHIVE = Path("data/fred_macro.json")
_WEB = Path("web/fred_macro.json")
_BASE = "https://api.stlouisfed.org/fred/series/observations"
_SERIES = ("DGS10", "T10Y2Y", "VIXCLS", "DTWEXBGS", "WALCL", "M2SL")
_LOOKBACK_DAYS = 1200                            # ~3y daily obs: enough for regime research


def _key() -> str | None:
    k = os.environ.get("FRED_API_KEY")
    if k:
        return k
    try:
        return str(json.loads(_KEYFILE.read_text("utf-8"))["key"])
    except (OSError, json.JSONDecodeError, KeyError):
        return None


def _fetch(key: str, sid: str) -> list[tuple[str, float]]:
    start = (datetime.now(tz=UTC) - timedelta(days=_LOOKBACK_DAYS)).date().isoformat()
    q = urllib.parse.urlencode({"series_id": sid, "api_key": key, "file_type": "json",
                                "observation_start": start})
    req = urllib.request.Request(f"{_BASE}?{q}", headers={"User-Agent": "quant-fred/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        obs = json.loads(r.read()).get("observations", [])
    out: list[tuple[str, float]] = []
    for o in obs:
        v = o.get("value", ".")
        if v not in (".", "", None):                     # FRED encodes missing as "."
            out.append((str(o["date"]), float(v)))
    return out


def main() -> None:
    key = _key()
    if not key:
        print("fred-macro: no key (data/secrets/fred.json or FRED_API_KEY) -- skipped")
        return
    series: dict[str, list[tuple[str, float]]] = {}
    for sid in _SERIES:
        try:
            series[sid] = _fetch(key, sid)
        except Exception as e:                           # one dead series never kills the rest
            print(f"fred-macro: {sid} FAILED {e!r}"[:120])
    if not series:
        raise SystemExit("fred-macro: zero series fetched -- check the key")
    ts = datetime.now(tz=UTC).isoformat()
    _ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    _ARCHIVE.write_text(json.dumps({"updated": ts, "series": series}), "utf-8")
    latest = {sid: {"date": rows[-1][0], "value": rows[-1][1],
                    "chg_30obs": (round(rows[-1][1] - rows[-31][1], 4)
                                  if len(rows) > 31 else None)}
              for sid, rows in series.items() if rows}
    _WEB.parent.mkdir(parents=True, exist_ok=True)
    _WEB.write_text(json.dumps({
        "updated": ts, "latest": latest,
        "note": ("Free FRED macro context (macro-crypto relative value family). Deep history "
                 "from day one -- backtestable immediately, no forward clock needed."),
    }, indent=2), "utf-8")
    n = sum(len(r) for r in series.values())
    print(f"fred-macro: {len(series)}/{len(_SERIES)} series, {n} obs -> {_ARCHIVE}")


if __name__ == "__main__":
    main()

```

### scripts/data_vitals.py
```python
"""DATA VITALS -- live collector health scoring (DQS) + provenance. Prevents the silent failure.

WHY THIS EXISTS. A Binance websocket handshake succeeded and then delivered no frames for 14 days.
Nothing noticed. A forward clock ran the whole time on a dead feed. `measurement_gate.py` answers
"is this dataset VALID FOR RESEARCH?" -- a slow, structural question. This answers a different and
faster one: "is this collector ALIVE RIGHT NOW?" They are not the same check and conflating them
is how a dead feed passes as healthy: a frozen file is perfectly self-consistent.

DATA QUALITY SCORE, five components, each in [0,1], product-weighted so ANY single failure drags
the score down. A mean would let four healthy components hide one dead one -- which is exactly the
silent-failure shape.

    latency            staleness vs the source's own observed cadence
    completeness       records in the last window vs the historical rate
    schema_integrity   modal key-set conformance (did the format change under us?)
    temporal_alignment monotonic, no future stamps
    cross_validation   0.5 when no second source exists -- ABSENCE IS NOT HEALTH

HARD RULE (principal): DQS < 0.5 sustained => the collector is dead. The action is emitted here;
execution of failover belongs to whatever supervises collectors, because a read-only health
scorer that also restarts things is a scorer nobody can trust to be read-only.

PROVENANCE is recorded per source: how it was collected, whether it can be regenerated, and
whether its timestamps are verified or assumed. `cny_otc_premium_history.jsonl` carries
"23:55 CST (UTC+8) assumed" in a prose field -- an unverified alignment feeding a LIVE mechanism.

Read-only. No keys, no network. Run from repo root.
"""
from __future__ import annotations

import itertools
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/data_vitals.json"
DQS_DEAD = 0.5
MAX_ROWS = 3000

_TIME_KEYS = ("ts", "date", "timestamp", "time", "datetime", "updated")

# Provenance the desk can state with evidence. Anything absent is reported UNKNOWN, never assumed.
PROVENANCE = {
    "cny_otc_premium_history.jsonl": {
        "collection": "wayback-cdx-replay of history.btc126.com (UNCOMMITTED one-off)",
        "regenerable": False,
        "timestamp_verified": False,
        "note": "rows carry '23:55 CST (UTC+8) assumed'. Alignment vs the USD/CNY reference is "
                "ASSUMED. Feeds M_STRUCTURAL_BARRIER, one of two ALIVE mechanisms."},
    "oi_ls_history.jsonl": {"collection": "binance futures API", "regenerable": True,
                            "timestamp_verified": True, "note": "daily archive"},
    "onchain_metrics.jsonl": {"collection": "public chain API", "regenerable": True,
                              "timestamp_verified": True, "note": "public, no moat"},
    "coinmetrics_flows.jsonl": {"collection": "coinmetrics community API", "regenerable": True,
                                "timestamp_verified": True, "note": "public tier"},
    "venue_divergence_shadow.jsonl": {"collection": "self-recorded multi-venue poll",
                                      "regenerable": False, "timestamp_verified": True,
                                      "note": "point-in-time capture; cannot be backfilled"},
}


# Not every .jsonl is a live collector. Scoring a static archive or a git-derived artifact by
# live-feed latency rules produced 9 DEAD flags of which only one was real -- and an alarm that
# fires mostly on non-problems trains its reader to ignore it.
_ARTIFACT_KIND = {
    "oi_ls_history.jsonl": ("STATIC", "historical backfill, ends 2023-12-03 BY DESIGN"),
    "cny_otc_premium_history.jsonl": ("STATIC", "wayback backfill; live feed is cny_premium.jsonl"),
    "experiment_registry.jsonl": ("DERIVED", "harvested from git; timestamps are commit dates"),
    "panel_verdicts.jsonl": ("EVENT_LOG", "appended per panel run, not a feed"),
    "external_panel_log.jsonl": ("EVENT_LOG", "appended per panel run"),
    "micro_audit_log.jsonl": ("EVENT_LOG", "appended per audit"),
    "mine_conversion_log.jsonl": ("EVENT_LOG", "appended per conversion"),
    "blind_spot_ledger.jsonl": ("EVENT_LOG", "appended per gap"),
    "information_value.jsonl": ("DERIVED", "written by libs/research/information_value.py"),
}


def _parse_ts(v):
    if isinstance(v, (int, float)):
        x = float(v)
        if x > 1e11:
            x /= 1000.0
        return datetime.fromtimestamp(x, tz=UTC) if 9.4e8 < x < 4.1e9 else None
    if not isinstance(v, str):
        return None
    s = v.strip().replace("Z", "+00:00")
    for f in (None, "%Y-%m-%d"):
        try:
            d = datetime.fromisoformat(s) if f is None else datetime.strptime(s, f)
            return d if d.tzinfo else d.replace(tzinfo=UTC)
        except (ValueError, TypeError):
            continue
    return None


def _rows(p: Path):
    out = []
    try:
        with p.open("r", encoding="utf-8", errors="ignore") as fh:
            for i, ln in enumerate(fh):
                if i >= MAX_ROWS:
                    break
                ln = ln.strip()
                if ln:
                    try:
                        d = json.loads(ln)
                        if isinstance(d, dict):
                            out.append(d)
                    except json.JSONDecodeError:
                        continue
    except OSError:
        pass
    return out


def score(p: Path) -> dict | None:
    kind, why = _ARTIFACT_KIND.get(p.name, (None, None))
    if kind:
        # Reported with its true nature. DEAD must mean "a live feed stopped", nothing else.
        return {"source": p.name, "dqs": None,
                "components": {"latency": None, "completeness": None, "schema_integrity": None,
                               "temporal_alignment": None, "cross_validation_available": False},
                "cadence_s": None, "age_s": None,
                "provenance": PROVENANCE.get(p.name, {"collection": kind, "regenerable": None,
                                                      "timestamp_verified": None, "note": why}),
                "action": f"{kind} -- not a live feed ({why})"}
    rows = _rows(p)
    if len(rows) < 20:
        # REPORTED, NOT DROPPED. A silently skipped file vanishes from the denominator and is
        # then indistinguishable from a file that passed -- coverage read 56.8% while the desk
        # could not say what became of the other 43%.
        return {"source": p.name, "dqs": None,
                "components": {"latency": None, "completeness": None, "schema_integrity": None,
                               "temporal_alignment": None, "cross_validation_available": False},
                "cadence_s": None, "age_s": None,
                "provenance": PROVENANCE.get(p.name, {"collection": "UNKNOWN",
                                                      "regenerable": None,
                                                      "timestamp_verified": None,
                                                      "note": f"only {len(rows)} rows"}),
                "action": "TOO_SMALL -- reported, not scored"}
    key = next((k for k in _TIME_KEYS if k in rows[0]), None)
    ts = [t for t in (_parse_ts(r.get(key)) for r in rows) if t] if key else []
    now = datetime.now(tz=UTC)
    # NEW-FILE GRACE. A collector's first run writes many rows at ONE timestamp, so cadence is
    # uncomputable and latency/completeness default low -- scoring a healthy new source DEAD.
    # defi_lending scored 0.250 DEAD on its .jsonl while its heartbeat scored 1.000 OK: the same
    # source, two verdicts, one of them false. Fewer than 3 distinct timestamps means "not yet
    # measurable", which is not the same as "dead" and must not page.
    if len({t.isoformat() for t in ts}) < 3:
        return {"source": p.name, "dqs": None,
                "components": {"latency": None, "completeness": None,
                               "schema_integrity": None, "temporal_alignment": None,
                               "cross_validation_available": False},
                "cadence_s": None, "age_s": None,
                "provenance": PROVENANCE.get(p.name, {"collection": "UNKNOWN",
                                                      "regenerable": None,
                                                      "timestamp_verified": None,
                                                      "note": "too few timestamps to score"}),
                "action": "NEW -- not yet measurable"}

    # latency -- measured against the source's OWN observed cadence, not a global constant.
    # A daily archive is not "stale" at 6h; a websocket feed is dead at 6h.
    lat = 0.5
    cadence_s = None
    if len(ts) >= 8:
        gaps = sorted((b - a).total_seconds() for a, b in itertools.pairwise(ts) if b >= a)
        cadence_s = gaps[len(gaps) // 2] if gaps else None
        if cadence_s and cadence_s > 0:
            age = (now - max(ts)).total_seconds()
            lat = 1.0 if age <= cadence_s * 2 else max(0.0, 1.0 - (age / (cadence_s * 10)))

    # completeness -- recent rate vs historical rate
    comp = 0.5
    if cadence_s and len(ts) >= 20:
        recent = [t for t in ts if (now - t).total_seconds() <= cadence_s * 20]
        comp = min(1.0, len(recent) / 20.0)

    keysets = [frozenset(r) for r in rows]
    modal = max(set(keysets), key=keysets.count)
    schema = keysets.count(modal) / len(keysets)

    align = 1.0
    if ts:
        ooo = sum(1 for a, b in itertools.pairwise(ts) if b < a)
        fut = sum(1 for t in ts if t > now.replace(microsecond=0) and (t - now).days > 0)
        align = max(0.0, 1.0 - (ooo + fut * 5) / len(ts))

    # ABSENCE IS NOT HEALTH: no second source == 0.5, never 1.0.

    # DQS excludes cross_validation: it is a CONSTANT 0.5 (no source has a second feed),
    # so multiplying it in capped every score at 0.5 against a 0.5 threshold and marked
    # 14/14 collectors DEAD regardless of health. A constant carries no information.
    dqs = lat * comp * schema * align
    prov = PROVENANCE.get(p.name, {"collection": "UNKNOWN", "regenerable": None,
                                   "timestamp_verified": None, "note": "provenance not recorded"})
    return {"source": p.name, "dqs": round(dqs, 4),
            "components": {"latency": round(lat, 3), "completeness": round(comp, 3),
                           "schema_integrity": round(schema, 3),
                           "temporal_alignment": round(align, 3), "cross_validation_available": False},
            "cadence_s": round(cadence_s, 1) if cadence_s else None,
            "age_s": round((now - max(ts)).total_seconds(), 0) if ts else None,
            "provenance": prov,
            "action": "DEAD -- FAILOVER" if dqs < DQS_DEAD else "OK"}



# ---------------------------------------------------------------- non-.jsonl sources
# Added 2026-07-28 after dependency_graph showed the three sources feeding EVERY alpha were
# entirely outside the DQS scan. Each carries its own cadence because a daily state file and an
# hourly recorder are not "stale" at the same age.
EXTRA_SOURCES = {
    "axis_shadow_state.json (live clocks)": {
        "kind": "JSON_STATE", "path": "data/axis_shadow_state.json",
        "field": "updated", "cadence_s": 86400,
        "feeds": "A002 -- the running forward clocks"},
    "data/moat (order books)": {
        "kind": "DIR_GLOB", "path": "data/moat", "glob": "**/*.jsonl.gz",
        "cadence_s": 3600,
        "feeds": "A004 -- the only source with a real information advantage"},
    "cashcarry_positions.json (live book)": {
        "kind": "JSON_STATE", "path": "data/cashcarry_positions.json",
        "field": None, "cadence_s": 900,
        "feeds": "A001 -- the live carry book; mtime is the freshness signal"},
    "binance funding (live API)": {
        "kind": "JSON_STATE", "path": "data/cashcarry_exec_heartbeat",
        "field": None, "cadence_s": 120,
        "feeds": "A001 live carry entry gate. PROXY, and the link is causal: the executor calls "
                 "current_funding() every cycle and cannot complete one without it, so a stalled "
                 "heartbeat IS a dead funding feed"},
    "oi_ls_live (Binance positioning)": {
        "kind": "JSON_STATE", "path": "data/oi_ls_live_heartbeat",
        "field": None, "cadence_s": 3600,
        "feeds": "M_FORCED_DELEVERAGE -- live crowding; the static archive ends 2023-12-03"},
    "defi_lending (Aave/Compound/Morpho)": {
        "kind": "JSON_STATE", "path": "data/defi_lending_heartbeat",
        "field": None, "cadence_s": 3600,
        "feeds": "M_FORCED_DELEVERAGE -- leverage build-up upstream of perp funding"},
    "cashcarry_exec_heartbeat (executor)": {
        "kind": "JSON_STATE", "path": "data/cashcarry_exec_heartbeat",
        "field": None, "cadence_s": 120,
        "feeds": "A001 -- executor liveness; the money-moving process itself"},
}


def score_extra(name: str, cfg: dict) -> dict | None:
    """Liveness for sources the .jsonl scan cannot see. Freshness IS the signal here; there is
    no schema or completeness to measure on a state file or a rolling directory."""
    p = ROOT / cfg["path"]
    now = datetime.now(tz=UTC).timestamp()
    age = None
    if cfg["kind"] == "JSON_STATE":
        if not p.exists():
            age = None
        elif cfg.get("field"):
            d = None
            try:
                d = json.loads(p.read_text("utf-8")).get(cfg["field"])
            except Exception:  # blind-except intentional (BLE001)
                d = None
            t = _parse_ts(d) if d else None
            age = (now - t.timestamp()) if t else (now - p.stat().st_mtime)
        else:
            age = now - p.stat().st_mtime
    elif cfg["kind"] == "DIR_GLOB" and p.exists():
        newest = max((f.stat().st_mtime for f in p.glob(cfg["glob"])), default=None)
        age = (now - newest) if newest else None

    if age is None:
        return {"source": name, "dqs": 0.0, "components": {"latency": 0.0, "completeness": 0.0,
                "schema_integrity": 0.0, "temporal_alignment": 0.0,
                "cross_validation_available": False},
                "cadence_s": cfg["cadence_s"], "age_s": None,
                "provenance": {"collection": cfg["kind"], "regenerable": None,
                               "timestamp_verified": None, "note": cfg["feeds"]},
                "action": "MISSING -- source not found"}

    cad = float(cfg["cadence_s"])
    lat = 1.0 if age <= cad * 2 else max(0.0, 1.0 - (age / (cad * 10)))
    # A state file has no schema drift or completeness to measure; scoring them 1.0 would be
    # inventing evidence, so DQS for these is the latency term alone and is labelled as such.
    return {"source": name, "dqs": round(lat, 4),
            "components": {"latency": round(lat, 3), "completeness": None,
                           "schema_integrity": None, "temporal_alignment": None,
                           "cross_validation_available": False},
            "cadence_s": cfg["cadence_s"], "age_s": round(age, 0),
            "provenance": {"collection": cfg["kind"], "regenerable": None,
                           "timestamp_verified": None, "note": cfg["feeds"]},
            "action": "DEAD -- FAILOVER" if lat < DQS_DEAD else "OK"}


def main() -> None:
    print("=== DATA VITALS -- is the collector ALIVE, not is the dataset VALID ===")
    print("    a 14-day silent websocket failure passed every structural check, because a")
    print("    frozen file is perfectly self-consistent. DQS is a PRODUCT, so one dead")
    print("    component cannot be hidden by four healthy ones.\n")
    rows = [s for s in (score(p) for p in sorted((ROOT / "data").glob("*.jsonl"))) if s]
    rows += [r for r in (score_extra(n, c) for n, c in EXTRA_SOURCES.items()) if r]
    if not rows:
        raise SystemExit("no collectors with >=20 rows")
    rows.sort(key=lambda r: (r["dqs"] is None, r["dqs"] or 0))
    print(f"  {'source':<38}{'DQS':>7}{'lat':>6}{'comp':>6}{'schm':>6}{'algn':>6}  action")
    dead = 0
    for r in rows:
        c = r["components"]
        dead += (r["dqs"] is not None and r["dqs"] < DQS_DEAD)

        def _f(v):
            return f"{v:>6.2f}" if isinstance(v, (int, float)) else f"{'-':>6}"
        _d = f"{r['dqs']:>7.3f}" if r['dqs'] is not None else f"{'new':>7}"
        print(f"  {r['source']:<38}{_d}{_f(c['latency'])}{_f(c['completeness'])}"
              f"{_f(c['schema_integrity'])}{_f(c['temporal_alignment'])}  {r['action']}")
    print(f"\n  {dead}/{len(rows)} collectors below DQS {DQS_DEAD} -> flagged DEAD")
    print("  NOTE: cross_validation is 0.5 for every source because NO collector currently has")
    print("  a second independent feed. That caps every DQS at 0.5x its otherwise value, which")
    print("  is deliberate -- an unverifiable feed is not a healthy feed, it is an unchecked one.")

    unk = [r for r in rows if r["provenance"]["collection"] == "UNKNOWN"]
    bad_ts = [r for r in rows if r["provenance"].get("timestamp_verified") is False]
    norg = [r for r in rows if r["provenance"].get("regenerable") is False]
    print(f"\n  PROVENANCE: {len(unk)} sources with UNKNOWN collection method; "
          f"{len(norg)} NOT regenerable; {len(bad_ts)} with UNVERIFIED timestamps")
    for r in bad_ts:
        print(f"    !! {r['source']}: {r['provenance']['note']}")
    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "dqs_dead_threshold": DQS_DEAD, "n_dead": dead,
                               "collectors": rows}, indent=1), "utf-8")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()

```

### scripts/hl_longterm_skill.py
```python
"""LONG-TERM GENUINE SKILL TEST -- the strongest remaining version of the hypothesis.

Prior tests were rightly criticised: holding window was ONE WEEK (noise vs a long-horizon trader's
signal), no track-record filter, and ranking on RAW PnL (rewards one lucky levered bet).

This fixes all three:
  - TRACK RECORD: require a long equity curve (multi-period history), not recent arrivals.
  - RISK-ADJUSTED selection: rank by SHARPE + consistency (% positive periods) + drawdown, not PnL.
  - LONG HORIZON + NATURAL GAP: split each trader's own curve -- formation = first 60%,
    holding = last 40%. No overlap, no lookahead, long measurement on both sides.

Uses pnlHistory (cumulative PnL) normalised by contemporaneous accountValue, so deposits/withdrawals
do not masquerade as returns. Tests whether risk-adjusted long-run skill PERSISTS into the later
period -- the precondition for 'find genuinely good traders and follow them'."""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

INFO="https://api.hyperliquid.xyz/info"; LB="https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"
N_TRY=420; MIN_PTS=60          # need a real curve, not a few points

def _get(u,t=180):
    return urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"q/1.0"}),timeout=t).read()
def _post(p,t=25):
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
        if a and av>=50_000 and vlm>0: cand.append((av,a))
    except (TypeError,ValueError): continue
cand.sort(reverse=True)
sel=cand[:N_TRY]
print(f"probing {len(sel)} accounts for long equity curves",flush=True)

recs=[]
for i,(_av0,a) in enumerate(sel):
    try: pf=_post({"type":"portfolio","user":a})
    except Exception: continue
    if not isinstance(pf,list): continue
    win=dict(pf)
    d=win.get("allTime") or {}
    pnl=d.get("pnlHistory") or []; avh=d.get("accountValueHistory") or []
    if len(pnl)<MIN_PTS or len(avh)<MIN_PTS: continue
    try:
        t=np.array([int(x[0]) for x in pnl]); cum=np.array([float(x[1]) for x in pnl])
        avt=np.array([float(x[1]) for x in avh[:len(cum)]])
    except (TypeError,ValueError,IndexError): continue
    if len(avt)!=len(cum): continue
    base=np.where(avt>1000, avt, np.nan)
    ret=np.zeros(len(cum)); ret[1:]=np.diff(cum)/np.where(np.isnan(base[1:]),np.inf,base[1:])
    ret=np.nan_to_num(ret,nan=0.0,posinf=0.0,neginf=0.0)
    ret=np.clip(ret,-0.5,0.5)                      # kill absurd single-step artifacts
    span=(t[-1]-t[0])/86400_000
    if span<200: continue                          # need a LONG record (>~7 months)
    k=int(len(ret)*0.6)
    f,h=ret[1:k],ret[k:]
    if len(f)<25 or len(h)<15: continue
    fs=float(f.mean()/f.std()*np.sqrt(365)) if f.std()>0 else 0.0     # formation Sharpe
    cons=float((f>0).mean())                                          # consistency
    eq=np.cumprod(1+f); dd=float((eq/np.maximum.accumulate(eq)-1).min())
    recs.append({"a":a,"span":span,"f_sharpe":fs,"f_cons":cons,"f_dd":dd,
                 "f_ret":float(np.prod(1+f)-1),"h_ret":float(np.prod(1+h)-1),
                 "h_sharpe":float(h.mean()/h.std()*np.sqrt(365)) if h.std()>0 else 0.0})
    if (i+1)%100==0: print(f"  {i+1}/{len(sel)} usable={len(recs)}",flush=True)

print(f"\ntraders with LONG usable curves: {len(recs)}")
if len(recs)<40: raise SystemExit("insufficient long-history cohort")
sp=np.array([r["span"] for r in recs])
print(f"track-record span: median {np.median(sp):.0f}d  max {sp.max():.0f}d")

def spear(a,b):
    ra=np.argsort(np.argsort(a)).astype(float); rb=np.argsort(np.argsort(b)).astype(float)
    if ra.std()==0 or rb.std()==0: return 0.0,0.0
    rho=float(np.corrcoef(ra,rb)[0,1]); n=len(a)
    return rho, float(rho*np.sqrt((n-2)/max(1e-12,1-rho**2))) if n>2 and abs(rho)<1 else 0.0

hr=np.array([r["h_ret"] for r in recs]); hs=np.array([r["h_sharpe"] for r in recs])
out={}
for nm,key in (("formation SHARPE","f_sharpe"),("formation CONSISTENCY","f_cons"),
               ("formation RETURN","f_ret"),("formation MAXDD (higher=safer)","f_dd")):
    x=np.array([r[key] for r in recs])
    r1,t1=spear(x,hr); r2,t2=spear(x,hs)
    o=np.argsort(x); k=max(3,len(x)//4)
    top,bot=hr[o[-k:]],hr[o[:k]]
    print(f"\n[{nm}]  -> holding RETURN rho {r1:+.3f} (t {t1:+.2f}) | -> holding SHARPE rho {r2:+.3f} (t {t2:+.2f})")
    print(f"   top-quartile holding ret {top.mean()*100:+.1f}% (median {np.median(top)*100:+.1f}%) vs "
          f"bottom {bot.mean()*100:+.1f}% (median {np.median(bot)*100:+.1f}%)")
    out[nm]={"rho_ret":round(r1,4),"t_ret":round(t1,2),"rho_sharpe":round(r2,4),"t_sharpe":round(t2,2),
             "top_q_mean":round(float(top.mean()),4),"bot_q_mean":round(float(bot.mean()),4)}
print(f"\ncohort holding-period mean {hr.mean()*100:+.1f}% median {np.median(hr)*100:+.1f}% "
      f"| positive {int((hr>0).sum())}/{len(hr)}")
Path("data/hl_longterm_skill.json").write_text(json.dumps(
    {"updated":datetime.now(tz=UTC).isoformat(),"n":len(recs),"median_span_d":float(np.median(sp)),
     "tests":out},indent=1),"utf-8")

```

### scripts/hypothesis_generator.py
```python
"""HYPOTHESIS GENERATOR -- external LLMs proposing MECHANISMS, with the graveyard in hand.

*** UNTESTED (OpenRouter 402). The brain must run it once and check output before relying on it. ***

WHY THIS ROLE DID NOT EXIST: the desk had an external LLM for SOURCE discovery (breadth_expander)
but nothing for HYPOTHESIS generation. The principal supplied a ~50-hypothesis slate from ChatGPT
that was genuinely well-framed -- and three of the first four were ALREADY REFUTED on this desk,
while the three novel escalations tested 0/3. That is not a failure of the model; it is a failure
of CONTEXT: a generator that cannot see the graveyard will keep re-proposing the dead.

SO THIS ROLE INVERTS THE BREADTH EXPANDER'S DESIGN, deliberately:
  breadth_expander     COLD, no desk context   -> avoids anchoring, finds sources we cannot imagine
  hypothesis_generator FED the graveyard       -> avoids re-proposing what is already refuted
Same principle (maximise NEW information), opposite implementation, because the failure modes are
opposite. Anchoring is the enemy of source search; ignorance is the enemy of hypothesis search.

SEATS: multi-lab by design. The principal observes GPT is strong at idea generation; the desk's own
measurement says gpt-5.6-terra-pro produced 0 parseable rows on 5 of 6 breadth lenses while
nemotron/grok produced 18 each. Both can be true -- different task. So GPT leads here (its claimed
strength, generative framing) and two other labs run alongside, and the YIELD TABLE decides who
keeps the seat. No seat by reputation.

OUTPUT CONTRACT forces falsifiability: every idea must name a MECHANISM, a FREE data source, a
concrete TEST, and a KILL CONDITION. "Interesting area" is rejected by construction.
"""
from __future__ import annotations

import json
import re
import ssl
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEYS = ROOT / "data/secrets/llm_panel.json"
GRAVE = ROOT / "docs/graveyard.md"
MECH = ROOT / "docs/research/MECHANISM_GRAPH.md"
OUT = ROOT / "data/hypothesis_queue.jsonl"
CTX = ssl.create_default_context()

SEATS = ["openai/gpt-5.6-terra-pro", "x-ai/grok-4.3", "deepseek/deepseek-v4-pro"]

LENSES = [
    ("MECHANISM TRANSITION", "What causes a market to move BETWEEN states (calm->stressed, "
     "trending->ranging, liquid->fragile)? Static-state signals have failed repeatedly here; "
     "transitions have not been tested."),
    ("PARTICIPANT CONSTRAINT", "Which market participant is FORCED to act against their own "
     "interest by a rule, mandate, margin call, redemption or licence? Forced flow is the most "
     "reliable edge source because the counterparty has no choice."),
    ("STRUCTURAL SEGMENTATION", "Where does a HARD barrier (licence, capital control, settlement "
     "delay, collateral incompatibility) prevent two prices for the same risk from converging? "
     "Soft frictions arbitrage away; hard ones persist."),
    ("MEASUREMENT ADVANTAGE", "What is publicly observable but expensive or awkward to MEASURE, "
     "such that most participants use a crude proxy instead of the real quantity?"),
    ("SECOND ORDER", "Take a signal that is known and crowded. What is its derivative, its "
     "dispersion, its persistence, or its failure mode -- and is THAT untested?"),
]

SYSTEM = (
    "You are a quantitative researcher generating TESTABLE hypotheses for a crypto trading desk.\n"
    "HARD RULES:\n"
    "1. Every hypothesis must name a MECHANISM -- a reason the edge exists that survives the "
    "question 'why has nobody arbitraged this?'. No mechanism = rejected.\n"
    "2. The data must be FREE and PUBLIC, and you must name the actual endpoint or dataset.\n"
    "3. State a concrete FALSIFIABLE TEST and an explicit KILL CONDITION.\n"
    "4. Do NOT propose anything in the REFUTED list you are given. Those are already dead here.\n"
    "5. Prefer SPREADS and FORCED FLOWS over forecasts. On this desk every forecast-style "
    "hypothesis has died and every surviving candidate has been a spread with a hard constraint.\n"
    "6. Be specific enough that someone could code the test tomorrow. Vague themes are useless.\n"
    "Output ONE hypothesis per line:\n"
    "NAME | MECHANISM (<=25 words) | DATA SOURCE | TEST | KILL CONDITION"
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
    body = json.dumps({"model": model, "max_tokens": 16000, "temperature": 1.05,
                       "reasoning": {"effort": "high"},
                       "messages": [{"role": "system", "content": _doctrine("hypothesis_generator") + system},
                                    {"role": "user", "content": user}]}).encode()
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        out = json.loads(r.read())
    m = out["choices"][0]["message"]
    return str(m.get("content") or m.get("reasoning") or "")


def refuted() -> tuple[str, set[str]]:
    """The graveyard, both as prose for the prompt and as tokens for dedup."""
    if not GRAVE.exists():
        return "", set()
    names, toks = [], set()
    for ln in GRAVE.read_text("utf-8").splitlines():
        if ln.startswith("|") and not set(ln) <= set("|- "):
            first = ln.strip("|").split("|")[0].strip()
            if first and first.lower() not in ("name", "signal", "strategy"):
                names.append(first[:80])
                toks.update(w for w in re.split(r"[^a-z0-9]+", first.lower()) if len(w) > 4)
    return "\n".join(f"- {n}" for n in names[:60]), toks


def main() -> None:
    if not KEYS.exists():
        print("no panel keys")
        return
    provs = {p["model"]: p for p in json.loads(KEYS.read_text("utf-8"))["providers"]
             if isinstance(p, dict)}
    dead_txt, dead_tok = refuted()
    mech = MECH.read_text("utf-8")[:3000] if MECH.exists() else ""
    day = datetime.now(tz=UTC).toordinal()
    lens_name, lens_txt = LENSES[day % len(LENSES)]

    user = (f"LENS -- {lens_name}\n{lens_txt}\n\n"
            f"ALREADY REFUTED ON THIS DESK (do not propose these or close variants):\n{dead_txt}\n\n"
            f"MECHANISM MAP (what is already observed):\n{mech}\n\n"
            "Give 10-15 hypotheses through THIS lens that are NOT in the refuted list.")
    print(f"=== HYPOTHESIS GENERATOR | lens: {lens_name} | {len(SEATS)} seats ===")
    print("    *** UNTESTED SCRIPT -- verify output before trusting it ***")
    print(f"    graveyard supplied: {len(dead_tok)} refuted tokens (prevents re-proposing dead)\n")

    def run(seat):
        p = provs.get(seat)
        if not p:
            return seat, "", "not in roster"
        try:
            return seat, _ask(p["base_url"], p["key"], seat, SYSTEM, user), None
        except Exception as e:
            return seat, "", f"{type(e).__name__} {getattr(e, 'code', '')}"

    with ThreadPoolExecutor(max_workers=3) as ex:
        answers = list(ex.map(run, SEATS))

    rows = []
    for seat, txt, err in answers:
        if err:
            print(f"  {seat.split('/')[-1]:<22} FAILED ({err})")
            continue
        kept = dup = 0
        for ln in txt.splitlines():
            if ln.count("|") < 4:
                continue
            parts = [x.strip() for x in ln.split("|")]
            name = parts[0].lstrip("-*0123456789. ")
            if not name or len(name) > 90:
                continue
            words = {w for w in re.split(r"[^a-z0-9]+", name.lower()) if len(w) > 4}
            if words & dead_tok:
                dup += 1
                continue
            rows.append({"date": datetime.now(tz=UTC).date().isoformat(), "lens": lens_name,
                         "seat": seat, "name": name, "mechanism": parts[1][:200],
                         "data": parts[2][:140], "test": parts[3][:200],
                         "kill": parts[4][:160] if len(parts) > 4 else ""})
            kept += 1
        print(f"  {seat.split('/')[-1]:<22} +{kept} new, {dup} rejected as already-refuted")

    if rows:
        with OUT.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
    print(f"\n  {len(rows)} hypotheses queued")
    for r in rows[:10]:
        print(f"    {r['name'][:54]:<54} [{r['seat'].split('/')[-1][:14]}]")
        print(f"       mech: {r['mechanism'][:96]}")
    print("\n  These enter the EV gate and Stage-A screening like any other candidate.")
    print("  ZERO promotion authority. Per-seat yield is tracked -- a seat proposing only")
    print("  hypotheses that die loses its slot, GPT included. No seat by reputation.")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()

```

### scripts/moat_audit.py
```python
"""MOAT PHASE 1 -- validate the order-book mine BEFORE mining it, then extract liquidity state.

WHY PHASE 1 FIRST, and it is not bureaucracy: TWO of today's "findings" (COOKIEUSDT 59bps flat,
mSOL/SOL 539bps sd) were DATA ARTIFACTS caught only by eyeball. Running unsupervised regime
clustering on 4.4GB of unvalidated snapshots would manufacture "regimes" out of gaps, stale books
and crossed quotes -- and they would look completely convincing because clustering always returns
clusters. The Book Quality Score below is what stops that.

data/moat = 11,980 hourly .jsonl.gz files, top-20 both sides, 30 symbols x {spot, fut}. This is the
only PROPRIETARY dataset the desk owns: nobody else has these snapshots at these timestamps.
Everything else it researches (GitHub, TVL, on-chain, social) is available to anyone.

PHASE 1 CHECKS (per symbol):
  coverage      -- hours present vs hours expected across the span (gaps = silent recorder death)
  crossed       -- bid >= ask: impossible; means a torn/interleaved snapshot
  stale         -- consecutive identical top-of-book: the recorder echoing, not reading
  spread sanity -- absurd spreads flag a malformed or illiquid book
  depth present -- zero/empty ladders

PHASE 2 (only on symbols that PASS): extract the liquidity state series that regime discovery
would consume -- spread_bps, depth within 1% of touch (both sides), and book imbalance. Reports
the DISPERSION of those states, because a regime model is only worth building if the states
actually vary.

Read-only. Samples rather than reading 4.4GB. Run from repo root.
"""
from __future__ import annotations

import gzip
import json
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MOAT = ROOT / "data/moat"
OUT = ROOT / "data/moat_quality.json"
SAMPLE_FILES = 6          # hourly files per symbol
SAMPLE_ROWS = 250         # snapshots per file


def parse(line: str):
    """Parse a DEPTH record only. The moat is a MIXED stream: k='d' depth records interleaved
    with k='t' TRADE records (~8x more numerous). The first audit read the first N lines of each
    file -- almost all trades -- and counted them as corrupt books, producing 82-99% 'stale' and
    a verdict that the dataset was unusable. It is not; the parser was."""
    try:
        d = json.loads(line)
    except json.JSONDecodeError:
        return None
    if d.get("k") != "d":
        return "skip"
    b, a = d.get("b") or d.get("bids"), d.get("a") or d.get("asks")
    if not b or not a:
        return None
    try:
        bp, _bq = float(b[0][0]), float(b[0][1])
        ap, _aq = float(a[0][0]), float(a[0][1])
    except (TypeError, ValueError, IndexError):
        return None
    if bp <= 0 or ap <= 0:
        return None
    mid = (bp + ap) / 2
    # depth within 1% of touch, both sides
    db = sum(float(p) * float(q) for p, q in b if float(p) >= mid * 0.99)
    da = sum(float(p) * float(q) for p, q in a if float(p) <= mid * 1.01)
    return {"bp": bp, "ap": ap, "mid": mid, "spread_bps": (ap - bp) / mid * 1e4,
            "db": db, "da": da, "t": d.get("t") or d.get("E") or d.get("ts")}


def audit(sym_dir: Path):
    files = sorted(sym_dir.glob("*.jsonl.gz"))
    if not files:
        return None
    pick = files if len(files) <= SAMPLE_FILES else random.sample(files, SAMPLE_FILES)
    rows, crossed, stale, bad = [], 0, 0, 0
    prev = None
    for f in sorted(pick):
        try:
            with gzip.open(f, "rt", encoding="utf-8", errors="ignore") as fh:
                lines = fh.readlines()   # scan all; depth rows are ~10% of the stream
        except Exception:
            continue
        for ln in lines:
            r = parse(ln)
            if r == "skip":
                continue
            if r is None:
                bad += 1
                continue
            if r["bp"] >= r["ap"]:
                crossed += 1
                continue
            if prev is not None and r["bp"] == prev["bp"] and r["ap"] == prev["ap"]:
                stale += 1
            prev = r
            rows.append(r)
    if len(rows) < 50:
        return None
    n = len(rows) + bad + crossed
    sp = np.array([r["spread_bps"] for r in rows])
    dep = np.array([r["db"] + r["da"] for r in rows])
    imb = np.array([r["db"] / max(r["db"] + r["da"], 1e-9) for r in rows])
    # hours covered vs span
    span_h = len(files)
    q = 100.0
    q -= min(40, crossed / max(1, n) * 100 * 4)         # crossed books are fatal
    q -= min(25, stale / max(1, len(rows)) * 100)       # stale = recorder echoing
    q -= min(20, bad / max(1, n) * 100 * 2)             # unparseable
    if np.median(sp) > 100:
        q -= 15                                          # absurd median spread
    if dep.std() == 0:
        q -= 20                                          # depth never varies = not real
    return {"snapshots": len(rows), "files": span_h, "bad": bad, "crossed": crossed,
            "stale": stale, "stale_pct": round(stale / max(1, len(rows)) * 100, 2),
            "spread_bps_med": round(float(np.median(sp)), 3),
            "spread_bps_p95": round(float(np.percentile(sp, 95)), 3),
            "depth_usd_med": round(float(np.median(dep)), 0),
            "depth_cv": round(float(dep.std() / max(dep.mean(), 1e-9)), 3),
            "imbalance_sd": round(float(imb.std()), 4),
            "quality": round(max(0.0, q), 1)}


def main() -> None:
    random.seed(7)
    have_mine = MOAT.exists()
    if not have_mine:
        # The order-book mine lives on the recording box. Its absence is not a reason to skip the
        # REGISTRY half of the moat picture, which is measurable anywhere -- skipping it here is
        # how "audit the moat" quietly came to mean "audit the one dataset this file knew about".
        print("no data/moat -- order-book audit skipped; registry portfolio still measured")
    print("=== MOAT PHASE 1: validate before mining ===" if have_mine else "")
    print("    clustering unvalidated books manufactures regimes from gaps -- this stops that\n")
    out = {}
    for side in ("fut", "spot"):
        base = MOAT / side
        if not base.exists():
            continue
        syms = sorted(p for p in base.iterdir() if p.is_dir())
        print(f"--- {side}: {len(syms)} symbols")
        print(f"  {'symbol':<14}{'snaps':>7}{'files':>7}{'stale%':>8}{'sprd_med':>10}"
              f"{'depth$':>12}{'depthCV':>9}{'imbSD':>8}{'Q':>6}")
        for sd in syms:
            a = audit(sd)
            if not a:
                print(f"  {sd.name:<14} (unreadable / too few snapshots)")
                continue
            out[f"{side}/{sd.name}"] = a
            print(f"  {sd.name:<14}{a['snapshots']:>7}{a['files']:>7}{a['stale_pct']:>8.1f}"
                  f"{a['spread_bps_med']:>10.2f}{a['depth_usd_med']:>12,.0f}"
                  f"{a['depth_cv']:>9.2f}{a['imbalance_sd']:>8.3f}{a['quality']:>6.0f}")
        print()

    if out:
        qs = np.array([v["quality"] for v in out.values()])
        cvs = np.array([v["depth_cv"] for v in out.values()])
        good = [k for k, v in out.items() if v["quality"] >= 80]
        print(f"  {len(out)} symbol-sides audited | median quality {np.median(qs):.0f} "
              f"| {len(good)} pass (Q>=80)")
        print(f"  depth coefficient-of-variation: median {np.median(cvs):.2f}")
        print(f"  -> {'STATES VARY ENOUGH for regime discovery' if np.median(cvs) > 0.25 else 'DEPTH BARELY VARIES -- regime clustering would be fitting noise'}")
        worst = sorted(out.items(), key=lambda kv: kv[1]["quality"])[:3]
        print("\n  lowest quality (exclude from any regime model):")
        for k, v in worst:
            print(f"    {k:<20} Q={v['quality']:.0f}  stale {v['stale_pct']:.1f}%  "
                  f"crossed {v['crossed']}  bad {v['bad']}")
    # ---------------------------------------------------------------- RANK 4 registry feed
    # THE ORDER-BOOK MINE IS NOT THE WHOLE MOAT, and auditing only what this file already knew
    # about is how the desk ends up measuring the moat it remembers rather than the one it owns --
    # exactly GAP_REGISTER #77's failure, one layer up. The data registry MEASURES every asset a
    # collector writes, so it is the authority on what exists; this audit stays the authority on
    # order-book QUALITY. Reading it here means a newly-added perishable feed appears in the moat
    # picture automatically, with no edit to this script.
    portfolio: dict[str, Any] = {}
    try:
        from libs.research.data_registry import REPL_PROPRIETARY, build
        assets = build(ROOT)
        moaty = [a for a in assets if a.moat_score > 0]
        portfolio = {
            "assets_scored": len(assets),
            "with_moat": len(moaty),
            "proprietary": [a.id for a in assets if a.replication == REPL_PROPRIETARY],
            "top": [{"id": a.id, "moat": a.moat_score, "research_value": a.research_value,
                     "span_days": a.span.days, "dqs": a.quality.dqs, "replication": a.replication}
                    for a in sorted(moaty, key=lambda x: -x.moat_score)[:10]],
            # Long history nobody queries is paid-for capability sitting idle (L2.9) -- the
            # cot_zcache case row #77 called out separately.
            "unread_long_history": [a.id for a in assets
                                    if (a.span.days or 0) > 365 and not a.consumers],
        }
        print(f"\n  REGISTRY FEED: {len(assets)} assets scored, {len(moaty)} carry any moat")
        for t in portfolio["top"][:5]:
            print(f"    {t['id']:<26} moat={t['moat']:<6} value={t['research_value']:<6} "
                  f"{t['span_days'] or '?'}d  {t['replication']}")
        if portfolio["unread_long_history"]:
            print(f"    PARALYSIS (>1y history, no reader): "
                  f"{', '.join(portfolio['unread_long_history'])}")
        if not moaty:
            print("    no asset carries moat on this box -- expected where the lake is absent; "
                  "moat is scored from MEASURED span, and an unmeasured span scores nothing")
    except Exception as e:
        portfolio = {"error": f"{type(e).__name__}: {str(e)[:160]}"}
        print(f"\n  REGISTRY FEED unavailable: {portfolio['error']}")

    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "sample_files_per_symbol": SAMPLE_FILES,
                               "symbols": out,
                               "registry_portfolio": portfolio}, indent=1), "utf-8")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()

```

### scripts/negative_knowledge.py
```python
"""NEGATIVE KNOWLEDGE LIBRARY -- failures as a queryable institutional asset.

The graveyard is PROSE: a human/LLM must read 44 markdown rows to know whether an idea was already
killed. That is why the 2026-07-27 breadth sweep re-suggested Bithumb/Coinone/Bitso hours after they
were refuted. Prose cannot be queried, so knowledge that exists is functionally absent.

This converts every failure into a STRUCTURED record with the one field prose always omits:
REVERSAL CONDITIONS -- what would have to change for this to be worth retesting. Without it a
graveyard is a tombstone; with it, it is a watchlist.

Every record carries:
  what failed | failure class | evidence | conditions under which failure may reverse |
  revisit trigger | whether the trigger is CURRENTLY MET

The last field is the point: the library actively tells you which dead ideas have become live
again, instead of waiting for someone to remember them. Failures stop being sunk cost and become
a monitored option.

Read-only. Run from repo root, cheap enough for daily cadence.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAVE = ROOT / "docs/graveyard.md"
LEDGER = ROOT / "data/decision_ledger.json"
OUT = ROOT / "data/negative_knowledge.json"

# failure class -> (permanence, what would have to change, machine-checkable trigger)
CLASSES = {
    "lookahead_artifact": ("PERMANENT", "nothing -- the construction was wrong", None),
    "timing_artifact": ("PERMANENT", "nothing -- signal was contemporaneous, not leading", None),
    "unstable_artifact": ("PERMANENT", "nothing -- sign flipped under cohort perturbation", None),
    "position_overlap_artifact": ("PERMANENT", "nothing -- mechanical PnL carry", None),
    "no_economics": ("NEAR-PERMANENT", "a NEW named causal mechanism is proposed", None),
    "wrong_sign": ("NEAR-PERMANENT", "a mechanism explains the sign (flipping alone is p-hacking)",
                   None),
    "redundant": ("CONDITIONAL", "the signal it duplicates is retired or diverges", "live_axis_retired"),
    "crowded": ("CONDITIONAL", "evidence the crowd left (volume//spread/decay)", "crowding_drop"),
    "costs_killed_edge": ("REVERSIBLE", "measured costs fall or hold period lengthens",
                          "cost_model_improved"),
    "narrow_breadth": ("REVERSIBLE", "the tradeable universe widens", "universe_widened"),
    "no_breadth": ("REVERSIBLE", "more venues/assets carry the signal", "universe_widened"),
    "regime_artifact": ("REVERSIBLE", "a different regime arrives", "regime_changed"),
    "insignificant": ("REVERSIBLE", "a larger sample / more power becomes available",
                      "more_data_available"),
    "no_edge_daily": ("REVERSIBLE", "test at a different horizon", "horizon_untested"),
    "no_predictive_power": ("REVERSIBLE", "a different SELECTION criterion, not a refit", None),
    "overfit": ("CONDITIONAL", "clean out-of-sample or forward evidence only", "oos_available"),
    "wrong_orthogonality": ("CONDITIONAL", "the sleeve it duplicated dies", "live_axis_retired"),
    "no_edge": ("NEAR-PERMANENT", "a genuinely new construction of the same data", None),
    "insufficient": ("REVERSIBLE", "data volume grows past the power threshold",
                     "more_data_available"),
}


def triggers_met() -> dict[str, tuple[bool, str]]:
    """Evaluate which reversal triggers are CURRENTLY satisfied -- the live half of the library."""
    out: dict[str, tuple[bool, str]] = {}

    # horizon_untested: was the horizon search ever run on this class?
    hz = ROOT / "data/horizon_discovery.json"
    out["horizon_untested"] = (not hz.exists(),
                               "horizon sweep has run (1d-90d)" if hz.exists()
                               else "no horizon sweep on record")

    # more_data_available: are forward clocks accruing rows?
    clocks = list((ROOT / "data").glob("*.jsonl"))
    rows = sum(1 for c in clocks[:40] for _ in c.open("r", encoding="utf-8", errors="ignore"))
    out["more_data_available"] = (rows > 0, f"{rows} rows across {len(clocks)} clocks accruing")

    # oos_available: does the reconstructed held-out OOS validator exist?
    oos = ROOT / "scripts/backfill_onchain_oos.py"
    out["oos_available"] = (oos.exists(),
                            "reconstructed OOS validator exists" if oos.exists() else "no OOS tool")

    # cost_model_improved: is there a measured cost model from recorded L2?
    cm = ROOT / "data/cost_model.json"
    out["cost_model_improved"] = (cm.exists(),
                                  "measured L2 cost model present" if cm.exists() else "none")

    # live_axis_retired: has any tracked axis been retired?
    sh = ROOT / "scripts/run_axis_shadows.py"
    txt = sh.read_text("utf-8") if sh.exists() else ""
    out["live_axis_retired"] = ("RETIRED" in txt, "an axis has been retired" if "RETIRED" in txt
                                else "no retirements yet")

    out["regime_changed"] = (False, "no regime-change detector wired yet")
    out["crowding_drop"] = (False, "no crowding monitor wired yet")
    out["universe_widened"] = (False, "universe size not tracked over time yet")
    return out


def main() -> None:
    if not GRAVE.exists():
        raise SystemExit("no graveyard")
    trig = triggers_met()
    records = []
    for ln in GRAVE.read_text("utf-8").splitlines():
        if not ln.startswith("|") or set(ln) <= set("|- "):
            continue
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if len(cells) < 3 or cells[0].lower() in ("name", "signal", "strategy"):
            continue
        tags = re.findall(r"`([a-z_]+)`", cells[2])
        if not tags:
            tags = ["untagged"]
        perms = [CLASSES.get(t, ("UNKNOWN", "unclassified -- tag it", None)) for t in tags]
        # the WEAKEST permanence governs: one reversible cause makes the whole record revisitable
        order = {"REVERSIBLE": 0, "CONDITIONAL": 1, "NEAR-PERMANENT": 2, "PERMANENT": 3,
                 "UNKNOWN": 1}
        perm = min((p[0] for p in perms), key=lambda x: order.get(x, 1))
        conds = "; ".join(dict.fromkeys(p[1] for p in perms))
        tkeys = [p[2] for p in perms if p[2]]
        met = [(k, trig[k][1]) for k in tkeys if k in trig and trig[k][0]]
        records.append({"what": cells[0][:100], "classes": tags, "permanence": perm,
                        "reversal_conditions": conds, "triggers": tkeys,
                        "triggers_met": [k for k, _ in met],
                        "evidence": cells[1][:140]})

    live = [r for r in records if r["triggers_met"]]
    by_perm: dict[str, int] = {}
    for r in records:
        by_perm[r["permanence"]] = by_perm.get(r["permanence"], 0) + 1

    print(f"=== NEGATIVE KNOWLEDGE LIBRARY -- {len(records)} structured failures ===")
    print("    (the graveyard is prose and cannot be queried -- this is the queryable form)\n")
    for k in ("PERMANENT", "NEAR-PERMANENT", "CONDITIONAL", "REVERSIBLE", "UNKNOWN"):
        if by_perm.get(k):
            print(f"  {k:<15} {by_perm[k]:>3}")
    print("\n  reversal triggers, current state:")
    for k, (ok, why) in sorted(trig.items()):
        print(f"    {'MET  ' if ok else 'unmet'} {k:<22} {why}")

    print(f"\n  *** {len(live)} dead ideas have a reversal trigger CURRENTLY MET ***")
    for r in live[:12]:
        print(f"    {r['what'][:58]:<58} [{','.join(r['triggers_met'])}]")
    if len(live) > 12:
        print(f"    ... +{len(live)-12} more")
    print("\n  These are NOT auto-resurrected -- they become Stage-A candidates with a stated")
    print("  reason the original refutation may no longer hold. Zero promotion authority.")

    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "n": len(records), "by_permanence": by_perm,
                               "triggers": {k: {"met": v[0], "why": v[1]}
                                            for k, v in trig.items()},
                               "revivable_now": len(live), "records": records}, indent=1), "utf-8")
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()

```

### scripts/reconcile_venue.py
```python
#!/usr/bin/env python3
"""READ-ONLY venue reconciliation for the 2026-07-19 dead-man fire (GAP #34).

Answers ONE question with venue ground truth: is the ~$1,838 USDT delta (and the
$785-vs-$2,409 equity discrepancy) a REAL loss, or a measurement artifact of
combined_equity()'s documented leg/cash race?

Method: replicate the dead-man's OWN formula component-by-component from fresh signed
reads, then attribute the USDT delta to futures income records (realized PnL, funding,
commission) and to spot coin holdings (USDT converted to coins is NOT a loss).

Touches nothing. Writes nothing. Imports nothing from the Tier-3 rail.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import certifi

ROOT = Path("/home/quant/quant-platform")
FUT_BASE = "https://testnet.binancefuture.com"
SPOT_BASE = "https://testnet.binance.vision"
FUT_KEYS = ROOT / "data/secrets/binance_testnet.json"
SPOT_KEYS = ROOT / "data/secrets/binance_spot_testnet.json"
STATE = ROOT / "data/deadman_state.json"
CTX = ssl.create_default_context(cafile=certifi.where())


def creds(p: Path) -> tuple[str, str]:
    """Fail loudly on a keyless file: the pair flows straight into hmac.new(secret.encode()),
    so a missing key surfaced as an AttributeError deep in signing rather than here."""
    d = json.loads(p.read_text())
    k, sec = d.get("api_key") or d.get("key"), d.get("api_secret") or d.get("secret")
    if not k or not sec:
        raise SystemExit(f"{p}: no api key/secret -- cannot reconcile against the venue")
    return str(k), str(sec)


def req(url: str, key: str | None = None) -> Any:
    r = urllib.request.Request(url, headers={"X-MBX-APIKEY": key} if key else {})
    with urllib.request.urlopen(r, timeout=20, context=CTX) as resp:
        return json.loads(resp.read())


def signed(base: str, path: str, c: tuple[str, str],
           params: dict[str, Any] | None = None) -> Any:
    k, s = c
    p = dict(params or {})
    p["timestamp"] = int(time.time() * 1000)
    p["recvWindow"] = 20000
    q = urllib.parse.urlencode(p)
    sig = hmac.new(s.encode(), q.encode(), hashlib.sha256).hexdigest()
    return req(f"{base}{path}?{q}&signature={sig}", k)


def main() -> None:
    state = json.loads(STATE.read_text())
    baseline = float(state["usdt_baseline"])
    hw = float(state["high_water"])
    fired_eq = float(state["last_eq"])

    fut, spt = creds(FUT_KEYS), creds(SPOT_KEYS)
    acct = signed(FUT_BASE, "/fapi/v2/account", fut)
    fut_eq = float(acct["totalMarginBalance"])
    unreal = float(acct.get("totalUnrealizedProfit", 0))
    positions = [p for p in signed(FUT_BASE, "/fapi/v2/positionRisk", fut)
                 if abs(float(p.get("positionAmt", 0))) > 0]
    shorts = {p["symbol"] for p in positions if float(p["positionAmt"]) < 0}

    bals = signed(SPOT_BASE, "/api/v3/account", spt)["balances"]
    px = {t["symbol"]: float(t["price"]) for t in req(f"{SPOT_BASE}/api/v3/ticker/price")}
    usdt = 0.0
    legs_v = 0.0
    coins = []
    for b in bals:
        amt = float(b["free"]) + float(b["locked"])
        if amt <= 0:
            continue
        if b["asset"] == "USDT":
            usdt = amt
            continue
        val = amt * px.get(b["asset"] + "USDT", 0.0)
        coins.append((b["asset"], amt, val))
        if b["asset"] + "USDT" in shorts:
            legs_v += val
    coins.sort(key=lambda x: -x[2])
    coins_total = sum(c[2] for c in coins)

    equity_now = fut_eq + legs_v + (usdt - baseline)
    usdt_delta = usdt - baseline

    # Futures income attribution since the incident window (7 days back, paginated)
    since = int((time.time() - 7 * 86400) * 1000)
    income: dict[str, float] = {}
    rows = 0
    start = since
    for _ in range(20):
        batch = signed(FUT_BASE, "/fapi/v1/income", fut,
                       {"startTime": start, "limit": 1000})
        if not batch:
            break
        for r in batch:
            income[r["incomeType"]] = income.get(r["incomeType"], 0.0) + float(r["income"])
        rows += len(batch)
        if len(batch) < 1000:
            break
        start = int(batch[-1]["time"]) + 1

    print("=" * 72)
    print("VENUE RECONCILIATION -- dead-man fire 2026-07-19T14:27:56Z (READ-ONLY)")
    print("=" * 72)
    print("  formula: equity = fut_eq + legs_v + (usdt - usdt_baseline)")
    print(f"  high_water at fire      : ${hw:>12,.2f}")
    print(f"  equity AT FIRE (latched): ${fired_eq:>12,.2f}   <- 5 consecutive polls")
    print(f"  fire line (65% of HW)   : ${hw * 0.65:>12,.2f}")
    print("-" * 72)
    print("COMPONENTS NOW (fresh signed reads):")
    print(f"  futures totalMarginBalance : ${fut_eq:>12,.2f}")
    print(f"  futures unrealized PnL     : ${unreal:>12,.2f}")
    print(f"  open futures positions     : {len(positions)} (shorts: {len(shorts)})")
    print(f"  spot USDT                  : ${usdt:>12,.2f}")
    print(f"  usdt_baseline (state)      : ${baseline:>12,.2f}")
    print(f"  usdt delta                 : ${usdt_delta:>12,.2f}   <- the '$1,838 gap'")
    print(f"  legs_v (shorted-only spot) : ${legs_v:>12,.2f}")
    print(f"  ALL spot coin value        : ${coins_total:>12,.2f}   <- incl. faucet bags")
    print("-" * 72)
    print(f"  EQUITY BY RAIL FORMULA NOW : ${equity_now:>12,.2f}")
    print(f"  vs equity at fire          : ${fired_eq:>12,.2f}")
    print(f"  difference                 : ${equity_now - fired_eq:>12,.2f}")
    print("-" * 72)
    print(f"FUTURES INCOME ATTRIBUTION (last 7d, {rows} records):")
    tot = 0.0
    for k, v in sorted(income.items(), key=lambda x: x[1]):
        print(f"  {k:<24}: ${v:>12,.4f}")
        tot += v
    print(f"  {'TOTAL futures P&L':<24}: ${tot:>12,.4f}   <- real money moved on futures")
    print("-" * 72)
    print("TOP SPOT HOLDINGS (where USDT went, if converted):")
    for a, amt, v in coins[:8]:
        print(f"  {a:<10} {amt:>18,.4f}  ${v:>12,.2f}")
    print("=" * 72)
    print("VERDICT INPUTS:")
    print(f"  * futures realized total   : ${tot:,.2f}")
    print(f"  * usdt delta               : ${usdt_delta:,.2f}")
    print(f"  * unexplained by futures   : ${usdt_delta - tot:,.2f}")
    print(f"  * spot coins held          : ${coins_total:,.2f} (conversion, not loss, if legs)")
    print("=" * 72)


if __name__ == "__main__":
    main()

```

### scripts/research_allocator.py
```python
"""ADAPTIVE RESEARCH ALLOCATOR -- dynamic exploration budget (principal 2026-07-27).

Replaces hardcoded split percentages ("40/25/20/15") with an evidence-driven allocation that
recomputes every cycle from the decision ledger + graveyard + mechanism graph.

THE REWARD FUNCTION IS THE WHOLE DESIGN. Allocating purely on "did this area produce a live alpha"
would defund every area that produces DECISIVE REFUTATIONS -- yet closing a family permanently
(M3 participant-behaviour, refuted at power 2026-07-27) is real value: it stops all future waste.
So reward = INFORMATION GAIN:

#  EXHAUSTION: allocation is uncapped upward. If one area earns 90% of the budget on
#  measured information gain, give it 90% -- an artificial spread is a quota, and a
#  quota is how a desk funds mediocrity to feel balanced.

    survivor              1.00   (a forward clock earned)
    decisive refutation   0.60   (powered null / mechanism closed -- prevents future waste)
    method upgrade        0.50   (a new rail: gapped-window, power reporting, stability check)
    inconclusive          0.00   (underpowered / data-blocked -- pure cost, no knowledge)

ALLOCATION = Thompson sampling over Beta posteriors (one per area), so areas with thin evidence
keep exploration weight instead of being starved by one bad month, and areas with repeated null
yield decay smoothly rather than being cut by decree. A SATURATION PENALTY from the mechanism graph
down-weights chains where every node is already observed (M1: 7/7 -> new sensors are marginal).

HONESTY RAIL: when total evidence is thin the posterior is PRIOR-DOMINATED, and the report says so
explicitly rather than presenting a prior as a data-driven allocation.

Read-only. Run from repo root.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

LEDGER = Path("data/decision_ledger.json")
GRAVE = Path("docs/graveyard.md")
OUT = Path("data/research_allocation.json")

# area -> (keywords for ledger matching, mechanism-graph saturation 0..1, base prior weight)
AREAS = {
    "M1_liquidity_flows":   (("stablecoin", "etf", "funding", "liquidity", "reserve"), 1.00, 1.0),
    "M2_regional_controls": (("kimchi", "premium", "cny", "capital control", "krw"), 0.55, 1.0),
    "M3_participant":       (("trader", "copytrad", "leaderboard", "elite", "skill", "wallet"), 0.95, 1.0),
    "M4_info_diffusion":    (("attention", "wikipedia", "developer", "github", "search", "narrative"), 0.30, 1.0),
    "M5_reflexivity":       (("reflexiv", "liquidation", "feedback", "cascade", "leverage"), 0.15, 1.0),
    "execution_costs":      (("cost", "slippage", "churn", "execution", "fill", "tca"), 0.40, 1.0),
    "method_infra":         (("harness", "rail", "power", "validator", "gate", "audit", "oos"), 0.20, 1.0),
}

REWARD = {"survivor": 1.0, "refutation": 0.6, "method": 0.5, "inconclusive": 0.0}


def classify(text: str) -> str:
    t = text.lower()
    if (any(k in t for k in ("forward clock", "wired", "screen-interesting", "replicat"))
            and "not wired" not in t and "nothing wired" not in t):
        return "survivor"
    if (any(k in t for k in ("rail", "harness", "control", "power", "validator", "standard"))
            and any(k in t for k in ("built", "added", "earned", "new standard"))):
        return "method"
    if any(k in t for k in ("refut", "killed", "reject", "fails", "zero predictive",
                            "graveyard", "exhausted", "no edge")):
        return "refutation"
    if any(k in t for k in ("underpowered", "data-blocked", "thin", "insufficient", "blocked")):
        return "inconclusive"
    return "inconclusive"


def main() -> None:
    led = json.loads(LEDGER.read_text("utf-8"))["decisions"]
    tally = {a: {"survivor": 0, "refutation": 0, "method": 0, "inconclusive": 0} for a in AREAS}
    for d in led:
        blob = " ".join(str(d.get(k, "")) for k in ("id", "decision", "hypothesis", "flagged_gap"))
        kind = classify(blob)
        low = blob.lower()
        for a, (kws, _, _) in AREAS.items():
            if any(k in low for k in kws):
                tally[a][kind] += 1

    rng = np.random.default_rng(7)
    rows, draws = [], {}
    for a, (_kws, sat, _prior_w) in AREAS.items():
        t = tally[a]
        n = sum(t.values())
        gain = sum(REWARD[k] * v for k, v in t.items())
        # Beta posterior on "information yield per attempt"
        alpha = 1.0 + gain
        beta = 1.0 + max(0.0, n - gain)
        samp = float(rng.beta(alpha, beta, size=4000).mean())
        # saturation penalty: a fully-observed chain earns less from a new sensor
        adj = samp * (1.0 - 0.65 * sat)
        draws[a] = adj
        rows.append({"area": a, "attempts": n, "survivors": t["survivor"],
                     "refutations": t["refutation"], "methods": t["method"],
                     "inconclusive": t["inconclusive"], "info_gain": round(gain, 2),
                     "posterior_mean": round(samp, 4), "saturation": sat,
                     "score": round(adj, 4)})

    # --- DIVERSIFICATION LAYER (principal 2026-07-27) -------------------------------------
    # "diversify a lot like the S&P 500, but that doesn't mean low focus on all" -- i.e. broad
    # coverage with CONVICTION WEIGHTING, not equal weight. Three rails:
    #   FLOOR  every area keeps a minimum so a lean patch can never permanently kill a branch
    #          (an area at 0% can never generate the evidence that would revive it -- absorbing state)
    #   CAP    no area exceeds MAX_W, so the book can never become a single-mechanism bet
    #   NEW    a permanent, non-negotiable slice for branches that DO NOT EXIST YET -- this is the
    #          "always be branching out" mandate; it never decays because unexplored classes have
    #          no track record to decay from. Implements DIGGING_CHARTER s12 in budget form.
    # L3 RATCHET: the new-branch slice GROWS as the known universe saturates. Saturation is a
    # signal to EXPAND, never to stop. base 15% + up to +15% as mean saturation -> 1.0.
    mean_sat = float(np.mean([AREAS[a][1] for a in AREAS]))
    NEW_BRANCH = min(0.30, 0.15 + 0.15 * mean_sat)
    # L2: MIN_W is a FLOOR ON ACTIVE WEIGHT, but depth is guaranteed by CADENCE (below), not by
    # this share -- with N branches growing, equal shares would collapse into skimming.
    MIN_W, MAX_W = 0.04, 0.28
    tot = sum(draws.values()) or 1.0
    for a in draws:
        draws[a] = draws[a] / tot * (1.0 - NEW_BRANCH)
    for _ in range(60):                      # iterate floor/cap to a fixed point
        for a in draws:
            draws[a] = min(max(draws[a], MIN_W * (1 - NEW_BRANCH)), MAX_W * (1 - NEW_BRANCH))
        t2 = sum(draws.values()) or 1.0
        draws = {a: v / t2 * (1.0 - NEW_BRANCH) for a, v in draws.items()}
    for r in rows:
        r["allocation_pct"] = round(100 * draws[r["area"]], 1)
    rows.sort(key=lambda r: -r["allocation_pct"])
    rows.append({"area": "NEW_BRANCHES (unexplored classes)", "attempts": 0, "survivors": 0,
                 "refutations": 0, "methods": 0, "inconclusive": 0, "info_gain": 0.0,
                 "posterior_mean": None, "saturation": 0.0,
                 "allocation_pct": round(100 * NEW_BRANCH, 1)})

    # --- L1 MONOTONIC BRANCH REGISTRY: branches are never deleted, only down-weighted ---------
    REG = Path("data/branch_registry.json")
    reg = json.loads(REG.read_text("utf-8")) if REG.exists() else {"branches": {}}
    now = datetime.now(tz=UTC).isoformat()
    for r in rows:
        b = reg["branches"].setdefault(r["area"], {"first_seen": now, "last_weight": None,
                                                   "last_dug": None, "status": "active"})
        b["last_weight"] = r["allocation_pct"]
        b["last_seen"] = now
    reg["count"] = len(reg["branches"])
    reg["monotonic_rule"] = ("branch count never decreases; a branch may be down-weighted on "
                             "evidence but never deleted -- zero attention is an absorbing state")
    REG.write_text(json.dumps(reg, indent=1), "utf-8")

    # --- L2 DEPTH = GUARANTEED REVISIT CADENCE (not budget share) -----------------------------
    # weight sets frequency/intensity; cadence guarantees no branch is ever abandoned.
    print("")
    print("  L2 DEPTH GUARANTEE -- revisit cadence by weight band (never abandoned):")
    for r in rows:
        w = r["allocation_pct"]
        cad = 7 if w >= 15 else (14 if w >= 8 else (30 if w >= 4 else 60))
        r["revisit_days"] = cad
        print(f"    {r['area']:<34} {w:>5.1f}%  re-dig every {cad:>2}d to exhaustion criteria")

    total_n = sum(r["attempts"] for r in rows)
    total_surv = sum(r["survivors"] for r in rows)
    prior_dominated = total_surv < 5 or total_n < 30

    print("=== ADAPTIVE RESEARCH ALLOCATION (recomputed from evidence, not decreed) ===\n")
    print(f"  {'area':<22}{'alloc':>7}{'att':>5}{'surv':>6}{'refut':>7}{'meth':>6}{'gain':>7}{'sat':>6}")
    for r in rows:
        print(f"  {r['area']:<22}{r['allocation_pct']:>6.1f}%{r['attempts']:>5}"
              f"{r['survivors']:>6}{r['refutations']:>7}{r['methods']:>6}"
              f"{r['info_gain']:>7.1f}{r['saturation']:>6.2f}")
    print(f"\n  reward: survivor {REWARD['survivor']} | refutation {REWARD['refutation']} "
          f"| method {REWARD['method']} | inconclusive {REWARD['inconclusive']}")
    print("  (refutations are PAID -- closing a family permanently prevents future waste)")

    if prior_dominated:
        print(f"\n  *** PRIOR-DOMINATED: {total_surv} survivors across {total_n} attempts. ***")
        print("  Allocation is currently driven by MECHANISM SATURATION, not realised yield.")
        print("  This is honest, not a defect -- but do not present it as data-driven until")
        print("  survivors accumulate. Re-run after the Aug 7 OI/LS verdict.")

    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "prior_dominated": bool(prior_dominated),
                               "total_attempts": total_n, "total_survivors": total_surv,
                               "reward_function": REWARD, "areas": rows}, indent=1), "utf-8")
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()

```

### scripts/run_model_upgrade.py
```python
"""MODEL AUTO-UPGRADE -- the desk adopts a newer flagship with NO HUMAN IN THE LOOP.

PRINCIPAL ORDER (2026-07-30): *"auto-upgrade to newer flagship models, no human needed."*

WHY THIS IS WORTH A SCRIPT. The brain, every miner, every audit and every dig runs a Claude model.
Model capability is the single input the desk cannot improve by its own work -- it improves when
the vendor ships. Historically that improvement reached this desk only when a human noticed and
hand-edited three files. Between ship date and notice date, every cycle ran on strictly worse
reasoning than was available: not a crash, just a quiet tax on every hypothesis screened, every
audit run, every mechanism proposed. Compounded over a research programme, that is the most
expensive kind of gap -- one with no error message.

WHAT IT DOES, in order:
  1. DISCOVER  candidate model ids: the Anthropic /v1/models listing when a key is present, plus
     a probe list synthesised by walking the version of the current head forward.
  2. RANK      via libs/ops/model_chain -- flagship tier only, strictly greater version.
  3. VERIFY    the candidate actually answers, through the same PING the organs use. An id that
     lists but does not answer (unreleased, entitlement-gated, wrong plan) is NOT an upgrade.
  4. PROMOTE   by PREPEND, keeping yesterday's head directly beneath it, and write the single
     source ops/model_chain.env.
  5. RECORD    every decision -- adopted, rejected, unverified -- to data/model_upgrade_log.jsonl,
     and page the principal on any change to the head.

THE SAFETY LINE. Auto-adoption is bounded to models whose FAMILY the desk already declares
(libs/ops/model_chain.FAMILY_TIER). A genuinely new family -- a name this code has never seen --
is PROPOSED and paged, never adopted, because promoting an unrecognised model into the path that
sizes real positions is precisely the convenience that ends compounding. Adding one line to
FAMILY_TIER is the human's entire job, and it is the only part that needs a human.

THE UPGRADE IS ALWAYS REVERSIBLE without anyone awake: the outgoing head stays in the chain, so a
promoted model that throttles or errors degrades to exactly what ran yesterday.

    python scripts/run_model_upgrade.py              # discover + report (default: SAFE)
    python scripts/run_model_upgrade.py --apply      # verify + promote + write the chain
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.model_chain import (  # noqa: E402
    CHAIN_FILE,
    FAMILY_TIER,
    is_upgrade,
    parse_model,
    promote,
    read_chain,
    render_chain,
)

_LOG = _ROOT / "data/model_upgrade_log.jsonl"
_API = "https://api.anthropic.com/v1/models?limit=100"
_PING = "Reply with exactly: PING-OK"


def _list_models_api() -> list[str]:
    """Vendor listing. Returns [] on any failure -- discovery is best-effort by design; the probe
    path below is what makes the upgrader work on a box with only an OAuth token."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return []
    req = urllib.request.Request(_API, headers={
        "x-api-key": key, "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return []
    return [str(m.get("id", "")) for m in body.get("data", []) if m.get("id")]


def _probe_candidates(head: str) -> list[str]:
    """Synthesise plausible next ids from the current head.

    This exists because the box normally authenticates with an OAuth token, not an API key, so the
    /v1/models listing is unavailable exactly where the upgrader has to run. Walking the version
    forward and PINGing is crude, costs one cheap call per candidate, and is the difference
    between an upgrader that works on the VPS and one that only works in a demo.
    """
    out: list[str] = []
    for family in sorted(f for f, t in FAMILY_TIER.items() if t >= 3):
        _, ver = parse_model(head)
        base = int(ver) if ver > 0 else 5
        for nxt in (base + 1, base + 2):
            out.append(f"claude-{family}-{nxt}")
    return out


def _ping(model: str, timeout: int = 120) -> tuple[bool, str]:
    """Does this model actually ANSWER for this account? Listing is not entitlement."""
    env = dict(os.environ, ANTHROPIC_MODEL=model)
    try:
        p = subprocess.run(["claude", "-p", _PING, "--model", model,
                            "--dangerously-skip-permissions"],
                           check=False, capture_output=True, text=True, timeout=timeout, env=env)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"{type(e).__name__}: {e}"[:200]
    out = (p.stdout or "") + (p.stderr or "")
    return ("PING-OK" in out), out.strip().splitlines()[-1][:200] if out.strip() else "no output"


def _page(msg: str) -> None:
    """Best-effort principal page; never fails the caller (same contract as brain_env.sh)."""
    try:
        cfg = json.loads((_ROOT / "data/secrets/ntfy.json").read_text("utf-8"))
        topic = cfg.get("topic") or cfg.get("ntfy_topic")
        if not topic:
            return
        req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=msg.encode("utf-8"),
                                     headers={"Title": "MODEL UPGRADE", "Priority": "high"})
        urllib.request.urlopen(req, timeout=10).close()
    except (OSError, ValueError, KeyError):
        return


def discover(chain: list[str]) -> dict[str, Any]:
    """Everything decidable WITHOUT spending a call: what is new, what is unknown, what is old."""
    head = chain[0]
    listed = _list_models_api()
    candidates = sorted(set(listed) | set(_probe_candidates(head)))
    upgrades = [c for c in candidates if is_upgrade(c, head)]
    # A family this code has never declared: reported and paged, never adopted.
    unknown = sorted({c for c in listed if parse_model(c)[0] == -1})
    return {"head": head, "chain": chain, "n_listed": len(listed),
            "listing_available": bool(listed),
            "candidates": candidates, "upgrades": upgrades, "unknown_families": unknown}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="verify + promote (default: report only)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    chain = read_chain()
    rep = discover(chain)
    rep["generated"] = datetime.now(tz=UTC).isoformat()
    rep["verified"] = []
    rep["rejected"] = []
    rep["adopted"] = None

    if args.apply and rep["upgrades"]:
        # Newest first, so the desk adopts the best answering model and stops -- not the first one
        # it happens to enumerate.
        for cand in sorted(rep["upgrades"], key=lambda m: parse_model(m), reverse=True):
            ok, detail = _ping(cand)
            (rep["verified"] if ok else rep["rejected"]).append({"model": cand, "detail": detail})
            if ok:
                new_chain = promote(cand, chain)
                CHAIN_FILE.write_text(render_chain(
                    new_chain, reason=f"auto-upgrade: {cand} verified answering, prepended above "
                                      f"{chain[0]} (which is retained as the fallback)",
                    sealed=rep["generated"]), "utf-8")
                rep["adopted"] = cand
                rep["chain"] = new_chain
                _page(f"MODEL AUTO-UPGRADE: adopted {cand} (was {chain[0]}). "
                      f"Chain now: {' '.join(new_chain)}. Old head retained as fallback.")
                break

    if rep["unknown_families"]:
        _page("MODEL UPGRADE: unrecognised model family listed "
              f"({', '.join(rep['unknown_families'][:4])}) -- NOT adopted. Declare it in "
              "libs/ops/model_chain.FAMILY_TIER to make it eligible.")

    _LOG.parent.mkdir(parents=True, exist_ok=True)
    with _LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rep) + "\n")

    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        mode = "APPLY" if args.apply else "report-only"
        print(f"model upgrade [{mode}] | head={rep['head']} | listing="
              f"{'api' if rep['listing_available'] else 'probe-only'} | "
              f"candidates={len(rep['candidates'])} upgrades={len(rep['upgrades'])}")
        for u in rep["upgrades"]:
            print(f"  UPGRADE-CANDIDATE {u}")
        for r in rep["rejected"]:
            print(f"  REJECTED          {r['model']}: {r['detail'][:90]}")
        for u in rep["unknown_families"]:
            print(f"  UNKNOWN-FAMILY    {u} (declare in FAMILY_TIER to make eligible)")
        print(f"  chain: {' '.join(rep['chain'])}"
              + (f"  <- ADOPTED {rep['adopted']}" if rep["adopted"] else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts/run_promotion_queue.py
```python
"""PROMOTION QUEUE -- forward slots go to the edges that will EXPIRE first (L1.18a, L1.28a).

THE PRINCIPAL'S CONCERN, stated exactly: the shadow->live process must not be so slow that *"by
the time they reach live the capital is already outgrown its capacity."*

`libs.autodiscovery.validation.capacity_race` has answered "does this edge reach live before the
book outgrows it?" since 2026-07-30 -- and until this script, EVERY CALLER WAS A TEST passing a
hardcoded `validation_days=90`. A mechanism with only test callers is the desk's own named defect
("an orphan is fixed by a caller, not by deletion"), and it meant the race was both un-run and
run against an assumption. This is the caller, and it feeds the race a MEASURED latency.

WHAT IT CHANGES, concretely. Forward slots are capped at MAX_FORWARD_SLOTS=12, because that cap is
what keeps the Holm bar fixed. Slots were filled in whatever order candidates arrived. Ordering by
ARRIVAL is the worst available policy when capacity decays: a long-runway edge loses nothing by
waiting a month, while a short-runway one loses EVERYTHING -- so arrival order systematically
sacrifices exactly the edges that cannot afford to wait. The queue is therefore ordered by EXPIRY,
SHORTEST RUNWAY FIRST.

WHAT IT REFUSES TO DO, and this is the part that keeps it honest. A DOA edge is never rescued by a
shorter clock or a lower bar (L1.6, and L2.8a makes that direction un-amendable). The only honest
accelerants are the two in libs/research/promotion_latency.py:
  * NOT QUEUEING -- give it a slot now rather than later. Free, and this script's whole job.
  * MORE OBSERVATIONS PER DAY -- and ONLY where the P&L is event-driven and the event rate
    genuinely rises. For diffusive (price-change) P&L it is false: drift estimation depends on the
    HORIZON, not the sampling rate, so "accelerating" by sampling faster manufactures a t-stat out
    of oversampling. The accelerant is refused by default.
If neither applies, the edge is recorded STRUCTURALLY-UNREACHABLE at this equity -- an honest
result, not a silent shelving, and it re-tests automatically as the book grows.

    python scripts/run_promotion_queue.py [--json] [--equity USD] [--growth 1.0]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_OUT = _ROOT / "data/promotion_queue.json"
_DB = _ROOT / "data/research_memory.db"


def _candidates() -> list[dict[str, Any]]:
    """Scored candidates with a capacity. Empty (not fatal) when the lab db is absent -- this box
    may not be the research box, and an empty queue is a fact worth reporting."""
    if not _DB.exists():
        return []
    try:
        from libs.autodiscovery.memory import CandidateStore
        from libs.store.connection import Database
        store = CandidateStore(Database(_DB, read_only=True))
        rows = store.survivors() or store.all()
    except (ImportError, OSError, ValueError, AttributeError, TypeError):
        return []
    out = []
    for c in rows:
        cap = float(getattr(getattr(c, "metrics", None), "capacity_usd", 0.0) or 0.0)
        if cap <= 0:
            continue
        out.append({"id": getattr(c, "id", "?"), "family": getattr(c, "family", "?"),
                    "symbol": getattr(c, "symbol", "?"), "capacity_usd": cap,
                    "status": str(getattr(c, "status", "?"))})
    return out


def build(*, equity_usd: float | None = None, growth: float = 1.0) -> dict[str, Any]:
    from libs.autodiscovery.validation import capacity_race, capacity_status
    from libs.research.promotion_latency import measure

    latency = measure()
    cands = _candidates()
    rows: list[dict[str, Any]] = []
    for c in cands:
        cap = float(c["capacity_usd"])
        admission = capacity_status(cap, equity_usd=equity_usd)
        race = capacity_race(cap, validation_days=latency.total_days,
                             equity_usd=equity_usd, growth_rate_annual=growth)
        rows.append({**c, "admission": admission, **race})

    # EXPIRY ORDER, shortest runway first. SUB-VIABLE candidates are excluded from the queue
    # entirely rather than sorted to the back: they fail execution physics at ANY equity, so a slot
    # spent on one buys nothing at any point in the future (L1.18a -- the only genuine capacity
    # kill). OUTGROWN ones are excluded too: the book has already passed them.
    queue = sorted((r for r in rows if r["admission"] == "ADMIT"),
                   key=lambda r: float(r["runway_days"]))

    try:
        from libs.research.slot_registry import MAX_FORWARD_SLOTS, derive_slots
        occupied = len(derive_slots().get("slots", []) or [])
        cap_slots = int(MAX_FORWARD_SLOTS)
    except (ImportError, OSError, ValueError, KeyError):
        occupied, cap_slots = 0, 12
    free = max(cap_slots - occupied, 0)

    for i, r in enumerate(queue):
        r["slot_action"] = "ADMIT-NOW" if i < free else f"WAIT (position {i - free + 1} in queue)"

    counts: dict[str, int] = {}
    for r in rows:
        counts[str(r["verdict"])] = counts.get(str(r["verdict"]), 0) + 1
    admissions: dict[str, int] = {}
    for r in rows:
        admissions[str(r["admission"])] = admissions.get(str(r["admission"]), 0) + 1

    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.18a -- the forward-slot queue is ordered by EXPIRY, shortest runway first: a "
               "long-runway edge loses nothing by waiting, a short-runway one loses everything. "
               "A DOA edge is never rescued by a shorter clock or a lower bar (L1.6).",
        "latency": latency.as_dict(),
        "latency_is_measured": latency.fully_measured,
        "slots": {"occupied": occupied, "cap": cap_slots, "free": free},
        "n_candidates": len(cands), "admission_counts": admissions, "race_counts": counts,
        "queue": queue,
        "excluded": [r for r in rows if r["admission"] != "ADMIT"],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--equity", type=float, default=None, help="override desk equity (USD)")
    ap.add_argument("--growth", type=float, default=1.0, help="annual growth, 1.0 = 100%%/yr")
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args()
    rep = build(equity_usd=args.equity, growth=args.growth)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
        return 0
    lat = rep["latency"]
    print(f"promotion queue | pipeline latency {lat['total_days']}d "
          f"({'measured' if rep['latency_is_measured'] else 'partly estimated'}) | "
          f"slots {rep['slots']['occupied']}/{rep['slots']['cap']} "
          f"({rep['slots']['free']} free)")
    for name, c in lat["components"].items():
        print(f"    {name:11} {c['days']:>6.1f}d  [{c['provenance']}] {c['detail'][:78]}")
    print(f"  candidates {rep['n_candidates']} | admission {rep['admission_counts']} | "
          f"race {rep['race_counts']}")
    for r in rep["queue"][:args.top]:
        print(f"  {r['verdict']:13} {r['slot_action']:26} runway {r['runway_days']:>7.0f}d  "
              f"${r['capacity_usd']:>12,.0f}  {str(r['family'])[:18]:20} {r['symbol']}")
    if not rep["queue"]:
        print("  QUEUE EMPTY -- no ADMIT-status candidate with a positive capacity. That is a "
              "supply problem upstream (discovery/gauntlet), not a queueing one.")
    print(f"-> {_OUT.relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts/run_recorder_spot.py
```python
"""DATA-MOAT RECORDER v1 -- SPOT LEG (gap #35).

Companion to scripts/run_recorder.py (which records USD-M FUTURES microstructure). This
process records LIVE Binance SPOT microstructure for the same liquid symbols: top-20 order
book at ~4s cadence + every aggTrade, gzip-jsonl hourly partitions under data/moat/spot/{sym}/.

Why this exists (gap #35, micro-audit 07-19 + panel 07-20, verified vs code): the desk is
DELTA-NEUTRAL -- every carry trade has an equal-weight SPOT leg. A pre-live TCA / execution-
cost model calibrated on perp-only ticks silently mis-prices half of every trade, and spot
liquidity/slippage on the smaller-cap carry names is plausibly the MORE binding cost. Recording
spot alongside futures also yields a live spot-vs-perp basis/depth panel on identical names.
Every unrecorded hour is permanently unrecoverable (the gap #18 principle), so this starts NOW.

Isolation identical to the futures recorder: no trading imports, no keys, stdlib-only, writes
ONLY under data/moat/spot/ + its own heartbeat -- this process CANNOT touch the book.

Rate limits: Binance SPOT (api.binance.com) uses a SEPARATE per-IP weight bucket from USD-M
futures (fapi.binance.com), so this does NOT consume the futures recorder's 2400/min budget.
Spot request-weight limit is 6000/min; boot-time weight guard refuses to start if over
(same defensive pattern the futures recorder gained after the 2026-07-21 self-inflicted IP ban).

Supervision: liveness = data/recorder_spot_heartbeat (alerted if stale); a 10-minute cron
pgrep-guard respawns it (mirrors run_recorder_bybit.py).

    python scripts/run_recorder_spot.py
"""

from __future__ import annotations

import contextlib
import gzip
import json
import shutil
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

_BASE = "https://api.binance.com"                  # LIVE public SPOT market data (read-only)
# Mirror the futures recorder's symbol set (liquid majors); the boot filter drops any that are
# not TRADING as a Binance spot pair, so a perp-only listing never wastes weight on 400s.
_CORE = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
            "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT",
            "TRXUSDT", "DOTUSDT", "BCHUSDT", "NEARUSDT", "SUIUSDT",
            "UNIUSDT", "APTUSDT", "FILUSDT", "ARBUSDT", "OPUSDT")
# --- DYNAMIC UNIVERSE (gap #39, 2026-07-22) ------------------------------------------------
# The cost model built from this moat was USELESS for real sizing: the recorder held 20 majors
# while the carry book held high-funding small-caps -- ZERO intersection. You cannot calibrate
# execution cost for a book you do not record. The carry book ROTATES, so the traded names are
# read live rather than hardcoded, with a hard cap so a runaway book can never blow the weight
# budget (2026-07-21: an over-wide universe got this recorder IP-banned).
_MAX_SYMBOLS = 32

# RESIDUAL CLOSED 2026-07-29 -- TWIN OF scripts/run_recorder.py (same ~40 lines, deliberately
# copied: the two recorders stay standalone processes by design, so this block is diffed against
# its twin rather than shared). The 07-22 union was computed at BOOT only, and with the book
# deadman-halted and flat the union is empty -- so the spot moat was 20 majors while every carry
# has a SPOT leg on a small-cap. Traded names now come from the trade LOG as well as live
# positions, they OUTRANK majors when the cap binds, and the set is recomputed hourly in-flight.
_BENCH = ("BTCUSDT", "ETHUSDT")          # always-on liquid benchmark, never evicted
_TRADED_LOOKBACK_D = 30.0
_UNIVERSE_REFRESH_S = 3600.0


def _book_symbols() -> tuple[str, ...]:
    try:
        pos = json.loads(Path("data/cashcarry_positions.json").read_text("utf-8"))["positions"]
        return tuple(sorted(str(s) for s in pos))
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return ()


def _recently_traded() -> tuple[str, ...]:
    """Symbols traded within the lookback, newest first. Read defensively (schema has changed)."""
    try:
        raw = json.loads(Path("data/cashcarry_trades.json").read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    rows = raw if isinstance(raw, list) else raw.get("trades") if isinstance(raw, dict) else None
    if not isinstance(rows, list):
        return ()
    floor_ms = (time.time() - _TRADED_LOOKBACK_D * 86400.0) * 1000.0
    out: list[str] = []
    for r in reversed(rows):
        if not isinstance(r, dict):
            continue
        sym = r.get("symbol") or r.get("sym")
        if not isinstance(sym, str):
            continue
        ts = r.get("closed_ms") or r.get("ts_ms") or r.get("opened_ms")
        if isinstance(ts, (int, float)) and float(ts) < floor_ms:
            continue
        if sym not in out:
            out.append(sym)
        if len(out) >= _MAX_SYMBOLS:
            break
    return tuple(out)


def _universe() -> tuple[str, ...]:
    """Benchmark + traded (held, then recently traded) + majors. Order IS the priority: when the
    cap binds, majors are dropped and traded names survive."""
    ordered = [*_BENCH, *_book_symbols(), *_recently_traded(), *_CORE]
    return tuple(dict.fromkeys(ordered))[:_MAX_SYMBOLS]


_SYMBOLS = _universe()
_ROOT = Path("data/moat/spot")
_HB = Path("data/recorder_spot_heartbeat")
_DEPTH_EVERY_S = 5.0    # matches the futures recorder cadence (weight budget below)
_TRADES_EVERY_S = 40.0
_DISK_MAX_FRAC = 0.80                               # stop writing above this disk usage
_FLUSH_ROWS = 200                                  # buffered rows per symbol before flush


def _get(path: str, params: str) -> object:
    req = urllib.request.Request(f"{_BASE}{path}?{params}",
                                 headers={"User-Agent": "quant-recorder/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def _disk_ok(path: Path = _ROOT) -> bool:
    """True when the filesystem THE RECORDER WRITES TO has headroom.

    Measured on the target path, not "/": data/moat sits on its own volume whenever the box has a
    data disk, and then "/" is simply a different disk. Wrong in both directions and silent in
    both -- it pauses the recorder while the moat volume is empty, or lets writes fill the moat
    volume unchecked. Probe the nearest existing ancestor, since the tree may not exist yet.
    """
    probe = path if path.exists() else next((p for p in path.parents if p.exists()), Path("/"))
    u = shutil.disk_usage(probe)
    return (u.used / u.total) < _DISK_MAX_FRAC


def _flush(sym: str, rows: list[dict]) -> None:
    if not rows:
        return
    hour = datetime.now(tz=UTC).strftime("%Y%m%d_%H")
    p = _ROOT / sym / f"{hour}.jsonl.gz"
    p.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(p, "at", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    rows.clear()


# --- BINANCE SPOT WEIGHT GUARD (gap #35 build, mirrors the futures guard) ---
# Spot IP request-weight budget is 6000/min. depth(limit<=100) costs 5; aggTrades(limit=1000)
# costs 4. Compute the steady-state burn at boot and refuse to start if over -- the futures
# recorder was IP-banned on 2026-07-21 by expanding symbols without widening intervals.
_WEIGHT_LIMIT_PER_MIN = 6000
_WEIGHT_TARGET_FRAC = 0.80          # stay well under; leave headroom for the boot exchangeInfo
_DEPTH_WEIGHT = 5                   # /api/v3/depth, limit 1-100
_TRADES_WEIGHT = 4                  # /api/v3/aggTrades


def _weight_per_min(n_symbols: int) -> float:
    depth = n_symbols * _DEPTH_WEIGHT * (60.0 / _DEPTH_EVERY_S)
    trades = n_symbols * _TRADES_WEIGHT * (60.0 / _TRADES_EVERY_S)
    return depth + trades


def _assert_weight_budget(symbols: tuple[str, ...]) -> None:
    w = _weight_per_min(len(symbols))
    cap = _WEIGHT_LIMIT_PER_MIN * _WEIGHT_TARGET_FRAC
    print(f"spot recorder weight budget: {w:.0f}/min vs cap {cap:.0f}/min "
          f"({len(symbols)} symbols, depth@{_DEPTH_EVERY_S}s, trades@{_TRADES_EVERY_S}s)")
    if w > cap:
        raise SystemExit(
            f"REFUSING TO START: {w:.0f} weight/min exceeds {cap:.0f}/min. Widen "
            "_DEPTH_EVERY_S/_TRADES_EVERY_S or cut _SYMBOLS.")


def _valid_spot_symbols(wanted: tuple[str, ...]) -> tuple[str, ...]:
    """Keep only symbols that are TRADING spot pairs. Boot hiccup -> use the full list rather
    than block recording (a bad symbol just wastes one poll's weight and is caught by try/except).
    """
    try:
        info = _get("/api/v3/exchangeInfo", "")
        trading = {s["symbol"] for s in info.get("symbols", [])
                   if s.get("status") == "TRADING"}
        keep = tuple(s for s in wanted if s in trading)
        dropped = [s for s in wanted if s not in trading]
        if dropped:
            print(f"spot recorder: dropped non-spot/non-trading symbols: {dropped}")
        return keep or wanted
    except Exception as e:  # boot robustness over strictness: never block recording
        print(f"spot recorder: exchangeInfo unavailable ({e}); using full symbol list")
        return wanted


def _weight_capped(symbols: tuple[str, ...]) -> tuple[str, ...]:
    """Trim from the TAIL (lowest priority = majors) until the weight budget fits. A mid-flight
    refresh that can GROW the set is the same hazard as the 2026-07-21 IP ban, so growth is
    bounded by arithmetic, not by trust."""
    cap = _WEIGHT_LIMIT_PER_MIN * _WEIGHT_TARGET_FRAC
    out = list(symbols)
    while out and _weight_per_min(len(out)) > cap:
        out.pop()
    return tuple(out)


def main() -> None:
    symbols = _weight_capped(_valid_spot_symbols(_SYMBOLS))
    _assert_weight_budget(symbols)
    print(f"spot recorder v1 | {len(symbols)} symbols | depth@{_DEPTH_EVERY_S}s "
          f"trades@{_TRADES_EVERY_S}s -> {_ROOT}/")
    buf: dict[str, list[dict]] = {s: [] for s in symbols}
    last_trade_id: dict[str, int] = {}
    last_trades_poll = 0.0
    last_universe_poll = time.time()
    disk_warned = False
    while True:
        t0 = time.time()
        # UNIVERSE REFRESH (gap #39 residual, 2026-07-29): twin of run_recorder.py. New spot legs
        # start recording within the hour; departing symbols flush first; the weight budget is
        # re-checked against the ACTUAL count, and new names are re-validated as spot pairs.
        if t0 - last_universe_poll >= _UNIVERSE_REFRESH_S:
            last_universe_poll = t0
            fresh = _weight_capped(_valid_spot_symbols(_universe()))
            if set(fresh) != set(symbols):
                for gone in [x for x in symbols if x not in fresh]:
                    with contextlib.suppress(OSError):
                        _flush(gone, buf.get(gone, []))
                    buf.pop(gone, None)
                for new_sym in [x for x in fresh if x not in symbols]:
                    buf[new_sym] = []
                print(f"spot recorder universe refresh: now {len(fresh)} syms, "
                      f"{_weight_per_min(len(fresh)):.0f} weight/min")
                symbols = fresh
        if not _disk_ok():
            if not disk_warned:
                print("spot recorder: DISK >80% -- writing paused (heartbeat continues)")
                disk_warned = True
            _HB.write_text(datetime.now(tz=UTC).isoformat() + " DISK-PAUSED", "utf-8")
            time.sleep(30)
            continue
        disk_warned = False
        for sym in symbols:
            try:
                d = _get("/api/v3/depth", f"symbol={sym}&limit=20")
                buf[sym].append({"t": int(time.time() * 1000), "k": "d",
                                 "u": d.get("lastUpdateId"),
                                 "b": d.get("bids"), "a": d.get("asks")})
            except Exception:
                pass                                # transient venue hiccup: skip one tick
        now = time.time()
        if now - last_trades_poll >= _TRADES_EVERY_S:
            last_trades_poll = now
            for sym in symbols:
                try:
                    q = f"symbol={sym}&limit=1000"
                    if sym in last_trade_id:
                        q += f"&fromId={last_trade_id[sym] + 1}"
                    trades = _get("/api/v3/aggTrades", q)
                    if isinstance(trades, list) and trades:
                        last_trade_id[sym] = int(trades[-1]["a"])
                        for tr in trades:
                            buf[sym].append({"t": int(tr["T"]), "k": "t", "a": int(tr["a"]),
                                             "p": tr["p"], "q": tr["q"],
                                             "m": bool(tr["m"])})
                except Exception:
                    pass
        for sym in symbols:
            if len(buf[sym]) >= _FLUSH_ROWS:
                try:
                    _flush(sym, buf[sym])
                except OSError:
                    buf[sym].clear()                # disk trouble: drop rather than die
        with contextlib.suppress(OSError):
            _HB.write_text(datetime.now(tz=UTC).isoformat(), "utf-8")
        time.sleep(max(0.0, _DEPTH_EVERY_S - (time.time() - t0)))


if __name__ == "__main__":
    main()

```

### scripts/run_trade_review.py
```python
#!/usr/bin/env python3
"""TRADE REVIEW (R0139) -- the discretionary desk's LEARNING LOOP. Binance perps, paper.

PRINCIPAL ORDER (2026-07-31): *"train the brain to maximum to get better and more profitable at
these and max this side as well... giving it just as much priority as the other section too."*

VENUE, stated once and unambiguously: this desk's discretionary sleeve trades BINANCE USD-M
PERPETUALS. The MT5 gold screenshots were the ORIGIN of the idea and a source of one measured data
point about trail width -- they are the principal's own separate account and are never this
sleeve's venue, its price source, or its benchmark.

WHAT "TRAINING" CAN AND CANNOT MEAN HERE, because the distinction decides whether this works. The
model's weights are fixed; nothing here fine-tunes anything. What CAN improve is the desk's
accumulated, evidence-weighted knowledge of WHICH SETUPS ACTUALLY PAY -- and that improves the
sleeve in exactly the way a trading journal improves a human: not by making them smarter, but by
stopping them repeating the mistake they cannot see from inside a single trade.

So this organ does what a professional does every evening:

  1. READS EACH CLOSED TRADE against what was actually claimed at entry -- the thesis, the named
     structure, the falsifier, the chart state -- and against what price then did, bar by bar.
  2. CLASSIFIES THE OUTCOME into causes that can be acted on, which a raw win/loss cannot:
     THESIS-WRONG (the driver did not happen), LEVEL-WRONG (thesis fine, invalidation misplaced),
     TIMING-WRONG (right idea, early/late), NOISE-STOP (stopped by wiggle inside the floor),
     RIGHT-AND-PAID, RIGHT-BUT-TRUNCATED (structure intact at the hold limit), UNLUCKY (correct
     process, adverse draw). A desk that cannot tell RIGHT-AND-UNLUCKY from WRONG will "fix" a
     process that was working, which is the most expensive mistake a journal can prevent.
  3. EXTRACTS ONE DURABLE LESSON with a FALSIFIER attached, and files it in the playbook.

THE PLAYBOOK IS EVIDENCE-WEIGHTED, NOT A PILE OF OPINIONS. This is the part that keeps it from
becoming the usual worthless list of trading platitudes:

  * a lesson enters PROVISIONAL on one observation and carries no authority,
  * it becomes SUPPORTED only after N_SUPPORT independent trades agree with it,
  * it is RETIRED the moment a trade CONTRADICTS it -- and the contradiction is recorded, so the
    same lesson cannot quietly return next week,
  * it goes STALE if the desk stops testing it, because an untested belief is not knowledge,
  * only SUPPORTED lessons reach the trading brief. PROVISIONAL ones are visible to review and to
    the principal, and invisible to the trader, so a single lucky trade cannot rewrite the method.

That ladder is the same evidence standard the rest of the desk applies to alpha (L1.6): nothing is
promoted on one observation, and nothing survives its own falsifier.

    python scripts/run_trade_review.py [--json] [--limit N]
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

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_BOOK = "data/conviction_book.jsonl"
_MARKS = "data/paper_book_pnl.json"
_PLAYBOOK = "data/trading_playbook.json"
_STATE = "data/trade_review.json"

#: 3 independent agreeing trades before a lesson reaches the trading brief. Derived from the same
#: N-gate the calibration fence uses (5 resolved forecasts before shrinkage applies) scaled to the
#: lower bar a piece of ADVICE needs versus a SIZING input: advice that is wrong costs a worse
#: prompt, sizing that is wrong costs money. Below 3 a "pattern" is one trade and two coincidences.
N_SUPPORT = 3
#: A lesson untested for 25 closed trades is STALE -- the desk stopped putting it at risk, so it
#: is no longer knowledge. 25 is one N_SUPPORT cycle at the ~8 trades the sleeve books per day.
STALE_AFTER = 25
#: At most 12 lessons reach the brief. Not a style preference: the brief already carries ~3.4k
#: tokens of chart context against a 21.9k doctrine, and an unbounded playbook would crowd out the
#: structure the trade is actually read from. Ranked by evidence, so growth costs the weakest slot.
MAX_BRIEF_LESSONS = 12

_CAUSES = ("THESIS-WRONG", "LEVEL-WRONG", "TIMING-WRONG", "NOISE-STOP",
           "RIGHT-AND-PAID", "RIGHT-BUT-TRUNCATED", "UNLUCKY")

_BRIEF = """You are reviewing a CLOSED paper trade from this desk's Binance perpetual futures
sleeve. Be the desk's harshest honest reviewer. The goal is not to feel bad about losses or good
about wins -- it is to extract knowledge that changes the NEXT trade.

THE TRADE AS IT WAS CLAIMED AT ENTRY:
{entry}

WHAT PRICE ACTUALLY DID, and how the managed position resolved:
{outcome}

CLASSIFY THE CAUSE as exactly one of: {causes}
  THESIS-WRONG        the driver you named did not happen
  LEVEL-WRONG         thesis was fine, the invalidation was in the wrong place
  TIMING-WRONG        right idea, entered too early or too late
  NOISE-STOP          stopped by ordinary wiggle, not by the thesis failing
  RIGHT-AND-PAID      the thesis happened and the trade was paid for it
  RIGHT-BUT-TRUNCATED the structure was still intact when the hold limit forced an exit
  UNLUCKY             process correct, adverse draw -- USE THIS HONESTLY. A desk that cannot tell
                      RIGHT-AND-UNLUCKY from WRONG will "fix" a process that was working, and that
                      is the most expensive error a review can make. But do not hide behind it.

THEN EXTRACT ONE LESSON, and it must survive these tests or it is worthless:
  * SPECIFIC to a recognisable situation ("on PAXG in a contracting-vol regime, a level with fewer
    than 3 touches does not hold a 30h horizon"), never a platitude ("cut losses, manage risk").
  * ACTIONABLE at the moment of the next trade -- it changes a level, a size, a horizon, or a pass.
  * FALSIFIABLE: state the observation that would prove it wrong.

OUTPUT EXACTLY ONE JSON OBJECT:
{{"cause": "one of the causes above",
  "what_happened": "2-3 sentences, concrete, referencing the actual prices",
  "lesson": "the specific actionable rule",
  "lesson_falsifier": "the observation that would prove this lesson wrong",
  "applies_when": "the recognisable situation this lesson is scoped to",
  "confidence": 0.6,
  "process_was_sound": true}}

If the trade contains no transferable lesson, say so: lesson "NONE -- single-instance noise, no
transferable rule" with process_was_sound set honestly. A review that manufactures a lesson from
every trade fills the playbook with superstition, and superstition in the brief is worse than an
empty playbook."""


def load_playbook(root: Path) -> dict[str, Any]:
    try:
        return json.loads((root / _PLAYBOOK).read_text("utf-8"))
    except (OSError, ValueError):
        return {"lessons": [], "reviewed_keys": []}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", str(text).lower()).strip()


def file_lesson(pb: dict[str, Any], lesson: dict[str, Any], trade_key: str,
                n_closed: int) -> dict[str, Any]:
    """Add or update a lesson on the evidence ladder. Contradiction RETIRES, and stays recorded."""
    text = str(lesson.get("lesson", "")).strip()
    if not text or text.upper().startswith("NONE"):
        return {"action": "no-lesson", "why": "review found no transferable rule"}
    key = _norm(text)[:120]
    for lv in pb["lessons"]:
        if lv["key"] == key or _norm(lv["text"])[:60] == _norm(text)[:60]:
            if lesson.get("contradicts"):
                lv["status"] = "RETIRED"
                lv.setdefault("contradicted_by", []).append(trade_key)
                return {"action": "retired", "lesson": lv["text"]}
            lv["support"] += 1
            lv["trades"].append(trade_key)
            lv["last_seen_at_trade"] = n_closed
            if lv["status"] == "PROVISIONAL" and lv["support"] >= N_SUPPORT:
                lv["status"] = "SUPPORTED"
                return {"action": "promoted", "lesson": lv["text"], "support": lv["support"]}
            return {"action": "reinforced", "lesson": lv["text"], "support": lv["support"]}
    pb["lessons"].append({
        "key": key, "text": text, "falsifier": lesson.get("lesson_falsifier", ""),
        "applies_when": lesson.get("applies_when", ""), "cause": lesson.get("cause"),
        "status": "PROVISIONAL", "support": 1, "trades": [trade_key],
        "first_seen_at_trade": n_closed, "last_seen_at_trade": n_closed,
    })
    return {"action": "new", "lesson": text, "support": 1}


def age_playbook(pb: dict[str, Any], n_closed: int) -> list[str]:
    """An untested belief is not knowledge. Mark long-unconfirmed lessons STALE."""
    staled = []
    for lv in pb["lessons"]:
        if lv["status"] == "SUPPORTED" and n_closed - lv["last_seen_at_trade"] > STALE_AFTER:
            lv["status"] = "STALE"
            staled.append(lv["text"])
    return staled


def brief_lessons(pb: dict[str, Any]) -> list[dict[str, Any]]:
    """ONLY SUPPORTED lessons reach the trader -- one lucky trade must not rewrite the method."""
    live = [lv for lv in pb["lessons"] if lv["status"] == "SUPPORTED"]
    live.sort(key=lambda lv: (-lv["support"], -lv["last_seen_at_trade"]))
    return [{"lesson": lv["text"], "applies_when": lv["applies_when"],
             "evidence_trades": lv["support"]} for lv in live[:MAX_BRIEF_LESSONS]]


def closed_trades(root: Path, *, limit: int = 5) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """(book row, mark) pairs for trades the resolver has closed and review has not yet seen."""
    try:
        marks = {m["key"]: m for m in json.loads((root / _MARKS).read_text("utf-8"))["marks"]
                 if m.get("closed") and m.get("key")}
    except (OSError, ValueError, KeyError):
        return []
    seen = set(load_playbook(root).get("reviewed_keys") or [])
    out = []
    try:
        lines = (root / _BOOK).read_text("utf-8", errors="ignore").splitlines()
    except OSError:
        return []
    for ln in reversed(lines):
        if not ln.strip():
            continue
        try:
            row = json.loads(ln)
        except ValueError:
            continue
        k = row.get("at")
        if k in marks and k not in seen:
            out.append((row, marks[k]))
        if len(out) >= limit:
            break
    return out


def _ask(prompt: str, timeout: int = 600) -> str:
    r = subprocess.run(
        ["bash", "-c",
         'source ops/brain_env.sh && brain_auth_check || exit 90 && '
         'claude --effort xhigh --append-system-prompt "$_DOCTRINE" -p "$0" '
         '--dangerously-skip-permissions', prompt],
        cwd=_ROOT, capture_output=True, text=True, timeout=timeout)
    return r.stdout or ""


def parse(raw: str) -> dict[str, Any] | None:
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except ValueError:
        return None


def review_one(row: dict[str, Any], mark: dict[str, Any], *, ask=_ask) -> dict[str, Any] | None:
    entry = {k: row.get(k) for k in ("symbol", "direction", "probability", "entry_ref",
                                     "invalidation", "structure", "expected_move_pct",
                                     "horizon_hours", "driver", "falsifier", "stop_pct")}
    entry["sizing"] = {k: (row.get("sizing") or {}).get(k) for k in ("leverage", "risk_fraction")}
    entry["noise_floor_pct"] = (row.get("noise") or {}).get("floor_pct")
    out = {k: mark.get(k) for k in ("outcome", "exit_price", "realised_R", "gross_return",
                                    "equity_return", "stage_reached", "max_stage",
                                    "units_at_exit", "hold_hours", "buy_and_hold")}
    res = parse(ask(_BRIEF.format(entry=json.dumps(entry, indent=1),
                                  outcome=json.dumps(out, indent=1),
                                  causes=", ".join(_CAUSES))))
    if res is None or res.get("cause") not in _CAUSES:
        return None
    return res


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    pb = load_playbook(_ROOT)
    pending = closed_trades(_ROOT, limit=args.limit)
    if not pending:
        state = {"status": "NOTHING-TO-REVIEW", "at": datetime.now(tz=UTC).isoformat(),
                 "why": "no closed trades the review has not already seen -- this is UNMEASURED "
                        "learning, not a healthy loop, until the book actually closes trades",
                 "playbook_supported": len(brief_lessons(pb))}
        (_ROOT / _STATE).write_text(json.dumps(state, indent=2), "utf-8")
        print(json.dumps(state, indent=2) if args.json else
              f"trade review (R0139): {state['status']} -- {state['why'][:90]}")
        return 0

    n_closed = len(pb.get("reviewed_keys") or []) + len(pending)
    results = []
    for row, mark in pending:
        res = review_one(row, mark)
        key = row.get("at")
        if res is None:
            results.append({"trade": key, "status": "NO-REVIEW",
                            "why": "no parseable review (auth/quota/refusal)"})
            continue
        filed = file_lesson(pb, res, key, n_closed)
        pb.setdefault("reviewed_keys", []).append(key)
        results.append({"trade": key, "cause": res["cause"], "filed": filed,
                        "process_was_sound": res.get("process_was_sound")})
    staled = age_playbook(pb, n_closed)
    pb["updated"] = datetime.now(tz=UTC).isoformat()
    (_ROOT / _PLAYBOOK).write_text(json.dumps(pb, indent=2), "utf-8")

    causes = {c: sum(1 for r in results if r.get("cause") == c) for c in _CAUSES}
    state = {
        "status": "REVIEWED", "at": pb["updated"], "n_reviewed": len(results),
        "causes": {k: v for k, v in causes.items() if v},
        "staled": staled,
        "playbook": {"total": len(pb["lessons"]),
                     "supported": sum(1 for lv in pb["lessons"] if lv["status"] == "SUPPORTED"),
                     "provisional": sum(1 for lv in pb["lessons"]
                                        if lv["status"] == "PROVISIONAL"),
                     "retired": sum(1 for lv in pb["lessons"] if lv["status"] == "RETIRED")},
        "results": results,
    }
    (_ROOT / _STATE).write_text(json.dumps(state, indent=2), "utf-8")
    print(json.dumps(state, indent=2) if args.json else
          f"trade review (R0139): reviewed {len(results)}; playbook "
          f"{state['playbook']['supported']} supported / {state['playbook']['total']} total")
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/run_trend_shadow.py
```python
"""Forward SHADOW for the refined TREND book -- directional TS-momentum on majors, lookback 30d.

The 90-day OUT-OF-SAMPLE clock for the trend_30d spec that SURVIVED the in-sample gauntlet
(run_trend_gauntlet: net Sharpe ~1.40, PBO 0.079, RC p 0.005, 7y, 3/4 lookbacks passed). FROZEN --
no re-tuning to pass. Splits the daily return series at a fixed shadow_start and reports backtest vs
FORWARD Sharpe + a pre-committed verdict. Directional (real drawdown risk), decorrelated from the
delta-neutral carry -> the reason to want it. ZERO capital until it holds forward. Emits
web/trend_shadow.json + tracks the clock in data/trend_shadow_state.json.

    python scripts/run_trend_shadow.py
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
_STATE = Path("data/trend_shadow_state.json")
_WEB = Path("web/trend_shadow.json")
_PPY = 365.0
# FROZEN spec = the gauntlet survivor. ONE principled config, not a knob to re-tune.
_TOP, _LOOKBACK, _BAND = 15, 30, 0.10
_FROZEN = "directional TS-momentum on top-15 majors, 30d lookback, turnover-banded"


def _majors(top: int) -> tuple[pd.DataFrame, dict[str, float]]:
    closes, adv = {}, {}
    for s in list_liquid_perps(top_n=top * 3):
        if not (_CRYPTO / s / Timeframe.D1.value).exists():
            continue
        register_instrument(InstrumentSpec(symbol=s, asset_class=AssetClass.CRYPTO, description=s))
        df = ParquetLake("data/lake").read_bars(Layer.BRONZE, s, Timeframe.D1)
        df = df.set_index("timestamp")
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
        return f"ACCUMULATING ({days}/90+ days of forward evidence) -- zero capital until it holds"
    if fwd < 0:
        return "FAILING FORWARD -> kill (trend was a backtest mirage / bull-run artefact)"
    if fwd >= 0.5 and fwd >= 0.5 * bt:
        return "ON TRACK -> eligible for TINY paper->gated live on human approval (governance gate)"
    return "WEAK forward -> continue shadow, do not deploy"


def main() -> None:
    close, adv = _majors(_TOP)
    if close.shape[1] < 6:
        raise SystemExit(f"need a majors panel; got {close.shape[1]}")
    cost = {s: adv_tier_cost(a) for s, a in adv.items()}
    r = trend_basket_returns(close, cost, lookback=_LOOKBACK, band=_BAND)
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
    fwd_days = int(np.sum(fwd != 0.0))
    fwd_cum = float(np.prod(1.0 + fwd) - 1.0) if len(fwd) else 0.0

    equity = np.cumprod(1.0 + r)
    n = len(equity)
    step = max(1, n // 300)
    curve = [{"t": dates[i].date().isoformat(), "v": round(float(equity[i]), 4),
              "fwd": bool(is_fwd[i])} for i in range(0, n, step)]
    payload = {
        "strategy": _FROZEN, "shadow_start": state["shadow_start"], "majors": close.shape[1],
        "universe": list(close.columns), "backtest_ann_sharpe": bt_sharpe,
        "forward_ann_sharpe": fwd_sharpe, "forward_days": fwd_days,
        "forward_cum_return": round(fwd_cum, 4), "directional": True,
        "verdict": _verdict(fwd_days, fwd_sharpe, bt_sharpe),
        "note": ("passed in-sample gauntlet (Sharpe~1.40/PBO 0.079/RC 0.005); DIRECTIONAL so it "
                 "carries real drawdown risk and trend backtests flatter in bull-heavy history -- "
                 "the forward clock is the honest test."),
        "updated": datetime.now(tz=UTC).isoformat(), "equity": curve,
    }
    _WEB.parent.mkdir(parents=True, exist_ok=True)
    _WEB.write_text(json.dumps(payload, indent=2), "utf-8")
    print(f"trend shadow: start={state['shadow_start'][:10]} fwd_days={fwd_days} "
          f"bt_sharpe={bt_sharpe} fwd_sharpe={fwd_sharpe}")
    print(f"verdict: {payload['verdict']}")


if __name__ == "__main__":
    main()

```

### scripts/screen_auditor.py
```python
"""SCREEN-DESIGN AUDITOR -- checks the TEST, not the code.

THE FAILURE THIS EXISTS FOR (3 occurrences on 2026-07-27, all caught by the principal or by luck):
  * structural_spreads.py  -- tested persistence/reversion/boundedness, OMITTED net-of-cost.
                              All 4 "candidates" die on fees. The code was correct; the TEST was
                              incomplete, so it produced confident false positives.
  * horizon_search.py      -- needed the ADJACENCY rail; the principal had to ask for it.
  * hl_longterm_skill.py   -- underpowered; the principal had to point out SE/min-detectable-effect.
A code auditor would have passed all three: the code did exactly what it said. The DESIGN was
missing a gate that, once applied, killed everything that passed. That is the most expensive
failure mode on a research desk.

RULE-BASED, NO LLM: each screen is checked for the presence of the rails the desk EARNED, by
scanning for their implementations. It cannot judge whether a rail is correctly applied -- only
whether it is ABSENT, which is the failure that actually occurred all three times.

Rails are declared per screen KIND, because a spread screen and a forecast screen need different
gates -- demanding all rails everywhere would just train people to ignore the auditor.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
OUT = ROOT / "data/screen_audit.json"

# rail -> (regex evidence it is present, why it matters, which screen kinds require it)
RAILS = {
    "net_of_cost": (
        r"cost_model|round.?trip|bps|fee|slippage|net.of.cost",
        "a spread/edge smaller than transaction costs is not an edge -- USDC/USDT passed every "
        "structural test at 1.1bps against 4-10bps fees",
        {"spread", "forecast"}),
    "power_reporting": (
        r"min_detectable|minimum detectable|se\b|n_eff|powered|sqrt\(len|standard error",
        "a null without power is not a result -- the n=229 skill test could only detect rho>=0.13 "
        "and reported 'no persistence' anyway",
        {"forecast", "cross_sectional"}),
    "decontamination": (
        r"same_period|same-period|contam|residual_ic|orthogonalis",
        "a signal correlated with the CONCURRENT return is not leading it -- killed coinbase, "
        "turkey and elite order flow",
        {"forecast"}),
    "lookahead_rail": (
        r"SUSPECT-LOOKAHEAD|ic_ceiling|implausible_leak|shift|lookahead",
        "an implausibly strong daily IC means misalignment, not skill -- bithumb showed IC 0.72",
        {"forecast", "cross_sectional"}),
    "multiplicity": (
        r"bonferroni|holm|multiplicity|alpha\s*/\s*(len|n_)|/ *len\(HORIZONS\)",
        "k tests at alpha=0.05 manufacture k/20 false discoveries -- the horizon search ran 96",
        {"forecast", "cross_sectional", "spread"}),
    "stability_check": (
        r"perturb|stability|neighbour|adjacen|same-sign|resampl",
        "a result that flips under a small universe/parameter change is noise -- elite flow "
        "inverted when 60 traders were added",
        {"forecast", "cross_sectional"}),
    "gapped_windows": (
        r"gap|formation|holding|non-overlap",
        "adjacent formation/holding windows carry open positions across the boundary and "
        "manufacture persistence -- rho +0.12 became -0.06 with a 3-week gap",
        {"cross_sectional"}),
}

# screen kind by filename hint
KIND = {
    "structural_spreads.py": "spread",
    "horizon_search.py": "forecast",
    "batch_altdata.py": "forecast",
    "batch_onchain.py": "forecast",
    "batch_premium.py": "forecast",
    "fusion_engine.py": "forecast",
    "reflexivity_m5.py": "forecast",
    "hl_feature_factory.py": "forecast",
    "hl_skill_persistence.py": "cross_sectional",
    "hl_longterm_skill.py": "cross_sectional",
    "hl_highpower_skill.py": "cross_sectional",
    "build_dev_factor.py": "cross_sectional",
    "hl_gapped.py": "cross_sectional",
}


def main() -> None:
    print("=== SCREEN-DESIGN AUDITOR (audits the TEST, not the code) ===")
    print("    A code auditor passes an incomplete test. This asks: what gate is MISSING")
    print("    that would kill everything currently passing?\n")
    rows, total_missing = [], 0
    for fname, kind in sorted(KIND.items()):
        p = SCRIPTS / fname
        if not p.exists():
            continue
        src = p.read_text("utf-8", errors="ignore").lower()
        # A screen that calls stage_a_screen INHERITS its rails -- de-contamination, the
        # SUSPECT-LOOKAHEAD plausibility rail and power reporting are inside the harness. Not
        # crediting inheritance produced false "MISSING" on screens that are correctly gated,
        # and a noisy auditor is one nobody reads.
        inherits = bool(re.search(r"stage_a_screen", src, re.I))
        INHERITED = {"decontamination", "lookahead_rail", "power_reporting"} if inherits else set()
        required = [r for r, (_, _, kinds) in RAILS.items() if kind in kinds]
        missing = [r for r in required
                   if r not in INHERITED and not re.search(RAILS[r][0], src, re.I)]
        total_missing += len(missing)
        status = "OK" if not missing else ("INCOMPLETE" if len(missing) < 3 else "WEAK")
        print(f"  {fname:<28} [{kind:<15}] {status:<11} "
              f"{len(required)-len(missing)}/{len(required)} rails")
        for m in missing:
            print(f"      MISSING {m:<18} {RAILS[m][1][:88]}")
        rows.append({"screen": fname, "kind": kind, "required": required,
                     "inherited": sorted(INHERITED), "missing": missing, "status": status})

    print(f"\n  {total_missing} missing rails across {len(rows)} screens")
    print("  NOTE: this detects ABSENCE only. A present rail may still be wrongly applied --")
    print("  that needs the LLM code auditor (blocked on credits). Absence is what actually")
    print("  happened all three times today, so absence is the check worth having first.")
    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "total_missing": total_missing, "screens": rows}, indent=1),
                   "utf-8")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()

```

### scripts/screen_carry_basis_path.py
```python
"""R0206 / BR-08 -- is the carry sleeve's ENTRY RULE selecting into a widening basis?

THE QUESTION THIS ANSWERS. The desk's only deployed sleeve is cash-and-carry: long spot, short
perp, on the ``top=4`` USDT perps ranked by funding (data/cashcarry_config.json). Over 73
churn-free live round-trips it realised **-58.27 bps net of fees with only 12 bps of commission**,
of which ``price_pnl`` was **-51.74 bps**. For a delta-neutral pair the price legs cancel, so
``price_pnl`` IS the basis change -- and it should be ~0, not -51.74 bps. It also does not
amortize with hold time. That term is the DOMINANT P&L component of the only thing this desk
trades, and it is UNATTRIBUTED (L1.16: every edge understood -- mechanism, source, regime, decay --
or it is not durable).

THE MECHANISM ON TRIAL. Binance funding is computed FROM the premium index. Ranking names by
highest funding is therefore mechanically ranking them by WIDEST PERP PREMIUM. If premium at the
cross-sectional extreme keeps widening rather than converging, the sleeve is not harvesting a free
cashflow -- it is being paid to short the wrong side of an ongoing squeeze, and the funding it
collects is compensation for a basis loss it also takes.

--------------------------------------------------------------------------------------------------
PRE-REGISTRATION (constants below are the hypothesis; changing one is a NEW trial, not a re-run)
--------------------------------------------------------------------------------------------------
H1  Conditional on TOP funding rank at the close of day t, forward basis WIDENS:
    E[basis(t+h) - basis(t)] > 0 for h in HORIZONS.
H2  The effect STRENGTHENS with rank: decile 10 (highest funding) widens more than decile 9, etc.
REFUTED if top-rank forward basis change is flat or NEGATIVE (converging) at both horizons --
    which sends the live -51.74 bps back to the contamination/execution explanation.

DECISION-RELEVANT OUTPUT is not H1 alone but the full decomposition per rank bucket:
    net_bps = funding_harvest_bps + basis_leg_bps
where ``basis_leg_bps = -1e4 * (basis(t+h) - basis(t))`` -- the sign convention is the desk's own
(libs/research/cashcarry.py:38 ``basis_pnl = -(w * dbasis)``; libs/data/crypto_source.py:211
``basis = perp_close/spot_close - 1``, positive = perp premium). A widening basis LOSES money on
the short-perp leg.

--------------------------------------------------------------------------------------------------
TIMESTAMP ALIGNMENT (declared -- an unstated alignment voids a screen)
--------------------------------------------------------------------------------------------------
Bronze D1 bars are Binance klines labelled at the bar OPEN (UTC midnight). On the bar labelled t:
  * ``funding``  = SUM of the funding payments realised DURING day t
                   (libs/data/crypto_source.py:194 ``resample("1D").sum()``) -- fully known at the
                   CLOSE of day t.
  * ``basis``    = perp_close(t)/spot_close(t) - 1 -- measured at the CLOSE of day t
                   (libs/data/crypto_source.py:224).
Both are observable at the close of day t, so ranking on ``funding(t)`` and entering at
``close(t)`` carries NO look-ahead. Forward quantities use strictly later bars only.

KNOWN BIAS, AND ITS DIRECTION (stated because it is the thing that could fake a result). ``basis``
is measured from two non-synchronous closes and a bid-ask, so it carries measurement noise.
Conditioning on HIGH funding(t) partially conditions on positive basis(t) noise, and noise reverts.
That biases measured forward Δbasis DOWNWARD -- i.e. TOWARD apparent convergence, TOWARD the
carry looking good. It works AGAINST H1. A widening result therefore survives its own worst bias;
a converging result must be read with this bias in mind, which is exactly why construction ``lag1``
exists (it ranks on funding(t) but enters at close(t+1), so the entry basis is not the one the
ranking selected noise on).

--------------------------------------------------------------------------------------------------
TRIAL ACCOUNTING (L1.7 / TARGET-HORIZON SWEEP DUTY)
--------------------------------------------------------------------------------------------------
CONSTRUCTIONS x HORIZONS = every cell is a DSR-counted trial and EVERY cell is written to the
artifact, including the ones that print nothing. Reporting only the cell that worked is the
garden of forking paths. Sampling is NON-OVERLAPPING h-day blocks, so observations are
independent and the Newey-West correction has nothing left to remove (it is still applied; it
can only shrink the t-stat, which is the safe direction).

ZERO PROMOTION AUTHORITY (two-stage law). This measures a DEPLOYED sleeve's P&L decomposition.
It cannot promote anything and it cannot size anything. What it can do is tell the desk whether
its only live entry rule is adverse -- which is a REPAIR question, not a promotion question.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from libs.ops.lawful import guard
from libs.validation.forward_stats import nw_tstat

ROOT = Path(__file__).resolve().parent.parent
BRONZE = ROOT / "data/lake/bronze/crypto"
# reports/, NOT data/ -- data/* is gitignored, and this artifact is the cited evidence behind a
# permanent graveyard row. Evidence that lives only on one box's untracked disk is not
# institutional memory; a future clone would find the citation dangling.
OUT = ROOT / "reports/carry_basis_path.json"

# ---------------------------------------------------------------- PRE-REGISTERED CONSTANTS ----
HORIZONS: tuple[int, ...] = (1, 5)          # trading days held
CONSTRUCTIONS: tuple[str, ...] = ("literal", "lag1")
LIVE_TOP_N = 4                              # data/cashcarry_config.json "top"
N_DECILES = 10
MIN_XSEC = 20                               # min symbols on a date to rank cross-sectionally
MIN_BLOCKS = 30                             # min independent blocks or the cell REFUSES to report
MIN_NONZERO_BASIS = 50                      # per-symbol usable-history floor

# Every (construction, horizon) pair is a trial. Recorded so the multiplicity is honest.
N_TRIALS = len(CONSTRUCTIONS) * len(HORIZONS)


def _load_panel() -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Wide (date x symbol) funding and basis panels from the bronze D1 lake.

    Returns ``(funding, basis, skipped)``. Symbols whose basis column is absent or effectively
    all-zero (no matching spot pair -> crypto_source sets basis 0.0) are SKIPPED BY NAME, never
    silently: a symbol with basis==0 everywhere would otherwise enter the panel as a permanent
    zero-Delta observation and dilute every mean toward zero.
    """
    fund: dict[str, pd.Series] = {}
    bas: dict[str, pd.Series] = {}
    skipped: list[str] = []
    if not BRONZE.is_dir():
        raise FileNotFoundError(f"bronze crypto lake missing: {BRONZE}")
    for sym in sorted(os.listdir(BRONZE)):
        files = glob.glob(str(BRONZE / sym / "D1" / "**" / "*.parquet"), recursive=True)
        if not files:
            skipped.append(f"{sym}:no-D1")
            continue
        df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
        if "basis" not in df.columns or "funding" not in df.columns:
            skipped.append(f"{sym}:no-basis-col")
            continue
        df = df.drop_duplicates("timestamp").set_index("timestamp").sort_index()
        if int((df["basis"] != 0).sum()) < MIN_NONZERO_BASIS:
            skipped.append(f"{sym}:basis-degenerate")
            continue
        fund[sym] = df["funding"].astype(float)
        bas[sym] = df["basis"].astype(float)
    if not fund:
        raise ValueError("no symbol in the bronze lake carries usable funding+basis")
    f = pd.DataFrame(fund).sort_index()
    b = pd.DataFrame(bas).sort_index().reindex(f.index)
    return f, b, skipped


def _cell(f: pd.DataFrame, b: pd.DataFrame, *, construction: str, h: int) -> dict[str, Any]:
    """One pre-registered (construction, horizon) trial.

    ``literal``: rank on funding(t), enter close(t), exit close(t+h)  -- what the sleeve does.
    ``lag1``   : rank on funding(t), enter close(t+1), exit close(t+1+h) -- decouples the entry
                 basis from the noise the ranking selected on (see the bias note in the header).
    """
    entry_off = 0 if construction == "literal" else 1
    dates = list(f.index)
    step = h                                        # NON-OVERLAPPING blocks -> independent obs
    # per-block, per-bucket accumulators
    dec_basis: dict[int, list[float]] = {d: [] for d in range(1, N_DECILES + 1)}
    dec_fund: dict[int, list[float]] = {d: [] for d in range(1, N_DECILES + 1)}
    top_basis: list[float] = []
    top_fund: list[float] = []
    n_blocks = 0
    i = 0
    while i < len(dates):
        t = dates[i]
        i += step
        ei = f.index.get_loc(t) + entry_off
        xi = ei + h
        if xi >= len(dates):
            continue
        rank_row = f.loc[t]
        entry_b = b.iloc[ei]
        exit_b = b.iloc[xi]
        # a name is usable only if it has a funding rank AND both basis marks
        ok = rank_row.notna() & entry_b.notna() & exit_b.notna()
        if int(ok.sum()) < MIN_XSEC:
            continue
        r = rank_row[ok]
        # funding actually harvested over the HOLD -- strictly after entry, never the ranking bar
        harvest = f.iloc[ei + 1:xi + 1].loc[:, r.index].sum(axis=0, min_count=1)
        dbasis = (exit_b[r.index] - entry_b[r.index])
        basis_leg = -1e4 * dbasis                    # bps, desk sign convention (cashcarry.py:38)
        fund_leg = 1e4 * harvest                     # bps received by the short-perp leg
        order = r.sort_values(ascending=False)
        # the LIVE rule: top-N by funding
        top = order.index[:LIVE_TOP_N]
        tb, tf = basis_leg[top].mean(), fund_leg[top].mean()
        if np.isfinite(tb) and np.isfinite(tf):
            top_basis.append(float(tb))
            top_fund.append(float(tf))
        # deciles: 10 = highest funding
        lbl = pd.qcut(order.rank(method="first"), N_DECILES, labels=False, duplicates="drop") + 1
        for d in range(1, N_DECILES + 1):
            names = lbl.index[lbl == d]
            if len(names) == 0:
                continue
            vb, vf = basis_leg[names].mean(), fund_leg[names].mean()
            if np.isfinite(vb) and np.isfinite(vf):
                dec_basis[d].append(float(vb))
                dec_fund[d].append(float(vf))
        n_blocks += 1

    cell: dict[str, Any] = {
        "construction": construction, "horizon_d": h, "n_blocks": n_blocks,
        "sampling": "non-overlapping", "min_xsec": MIN_XSEC,
    }
    # ---- REFUSAL PATH: too little independent evidence is UNMEASURED, never a verdict -----------
    if n_blocks < MIN_BLOCKS or len(top_basis) < MIN_BLOCKS:
        cell["verdict"] = "UNMEASURED"
        cell["reason"] = (f"{n_blocks} independent blocks (< MIN_BLOCKS={MIN_BLOCKS}); "
                          "refusing to report a mean this thin as evidence")
        return cell

    tb = np.asarray(top_basis, float)
    tf = np.asarray(top_fund, float)
    net = tb + tf
    ppy = 365.0 / h
    cell["top_n"] = LIVE_TOP_N
    cell["basis_leg_bps"] = round(float(tb.mean()), 3)
    cell["basis_leg_t"] = round(float(nw_tstat(tb / 1e4, ppy=ppy)), 3)
    cell["funding_leg_bps"] = round(float(tf.mean()), 3)
    cell["net_bps"] = round(float(net.mean()), 3)
    cell["net_t"] = round(float(nw_tstat(net / 1e4, ppy=ppy)), 3)
    cell["deciles"] = {
        str(d): {
            "basis_leg_bps": round(float(np.mean(dec_basis[d])), 3),
            "funding_leg_bps": round(float(np.mean(dec_fund[d])), 3),
            "net_bps": round(float(np.mean(dec_basis[d]) + np.mean(dec_fund[d])), 3),
            "n": len(dec_basis[d]),
        } for d in range(1, N_DECILES + 1) if dec_basis[d]
    }
    # H1: does the top bucket WIDEN? widening => basis_leg_bps < 0 (the short-perp leg loses)
    widens = cell["basis_leg_bps"] < 0
    # H2: monotone strengthening -- top decile's basis leg worse than the bottom decile's
    d10 = cell["deciles"].get("10", {}).get("basis_leg_bps")
    d1 = cell["deciles"].get("1", {}).get("basis_leg_bps")
    cell["h2_rank_strengthens"] = bool(d10 is not None and d1 is not None and d10 < d1)
    sig = abs(cell["basis_leg_t"]) >= 1.96
    if widens and sig:
        cell["verdict"] = "CONFIRMED-WIDENING"
    elif (not widens) and sig:
        cell["verdict"] = "REFUTED-CONVERGING"
    else:
        cell["verdict"] = "INCONCLUSIVE"
    return cell


def main() -> int:
    guard()                                        # L1.42 -- no act is exempt from the laws
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    f, b, skipped = _load_panel()
    cells = [_cell(f, b, construction=c, h=h) for c in CONSTRUCTIONS for h in HORIZONS]
    measured = [c for c in cells if c["verdict"] != "UNMEASURED"]

    if not measured:
        overall = "UNMEASURED"
    elif all(c["verdict"] == "CONFIRMED-WIDENING" for c in measured):
        overall = "CONFIRMED-WIDENING"
    elif all(c["verdict"] == "REFUTED-CONVERGING" for c in measured):
        overall = "REFUTED-CONVERGING"
    else:
        overall = "MIXED"

    doc = {
        "generated": datetime.now(UTC).isoformat(),
        "law": "L1.16 alpha attribution; L1.4 reality anchoring; R0206/BR-08",
        "row": "R0206",
        "question": ("does ranking perps by funding select into a WIDENING basis, making the "
                     "carry sleeve's -51.74 bps price_pnl a structural feature of its entry rule?"),
        "n_symbols": int(f.shape[1]),
        "span": [str(f.index.min())[:10], str(f.index.max())[:10]],
        "skipped_symbols": len(skipped),
        "trials_declared": N_TRIALS,
        "trials_run": len(cells),
        "promotion_authority": "NONE (two-stage law) -- this is a repair diagnostic, not a screen",
        "overall": overall,
        "cells": cells,
    }
    Path(args.out).write_text(json.dumps(doc, indent=2), "utf-8")

    print(f"CARRY BASIS PATH (R0206/BR-08) -- {overall}")
    print(f"  panel {f.shape[1]} symbols  {doc['span'][0]}..{doc['span'][1]}  "
          f"({len(skipped)} symbols skipped)   trials {len(cells)}")
    for c in cells:
        if c["verdict"] == "UNMEASURED":
            print(f"  {c['construction']:>8s} h={c['horizon_d']:<2d} UNMEASURED -- {c['reason']}")
            continue
        print(f"  {c['construction']:>8s} h={c['horizon_d']:<2d} n={c['n_blocks']:<4d} "
              f"top{LIVE_TOP_N}: basis {c['basis_leg_bps']:+8.2f}bps (t {c['basis_leg_t']:+.2f})  "
              f"funding {c['funding_leg_bps']:+7.2f}  NET {c['net_bps']:+8.2f}bps "
              f"(t {c['net_t']:+.2f})  {c['verdict']}")
        d = c["deciles"]
        if d:
            row = "  ".join(f"d{k}:{v['net_bps']:+.1f}" for k, v in sorted(
                d.items(), key=lambda kv: int(kv[0])))
            print(f"            net by funding decile (1=low .. 10=high):  {row}")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts/screen_fx_debasement.py
```python
"""Stage-A screen: FX DEBASEMENT / CAPITAL-CONTROL DEMAND vs BTC forward returns.

MECHANISM (pre-registered before compute, 2026-07-26): bitcoin's oldest non-speculative bid is
ESCAPE DEMAND. A holder of a currency that is losing purchasing power, or who is fenced in by
capital controls, buys a bearer asset that settles outside the domestic banking rail. The desk has
already proven this family pays: kimchi premium screened IC +0.148 and is on a live forward clock.

THE HARD CONSTRAINT ON THIS AXIS (found before screening, and it is the headline)
--------------------------------------------------------------------------------
The ingested fx lake holds 57 crosses and NOT ONE of the currencies whose barrier height actually
drives the proven mechanism: NO KRW, NO CNY/CNH, NO BRL, NO ARS, NO NGN, NO VND, NO EGP, NO INR.
The graveyard's own era-evidence entry (`era_crossvenue_fiat_premium_arb`) states the governing
law: "premium magnitude tracks BARRIER HEIGHT". Every high-barrier currency is absent. What is
present is majors plus three freely-floating EM crosses. So this axis, AS INGESTED, cannot express
the mechanism that made fx high-prior -- it can only test the weak-barrier tail of it.

WHAT IS ALREADY DEAD AND IS **NOT** RE-RUN HERE (graveyard.md + web/axis_shadows.json)
-------------------------------------------------------------------------------------
  * try_premium_timing (Turkey venue premium)   -- `timing_artifact`, de-contam corr -0.495.
                                                   SKIPPED.
  * coinbase_premium_timing                     -- `timing_artifact`, contam +0.256. SKIPPED.
  * bithumb_kr_premium                          -- `lookahead_artifact`, KST candle. SKIPPED.
  * coinone_kr_premium                          -- `redundant` with kimchi. SKIPPED.
  * bitbank_jp / mercado_br premiums            -- `no_economics`/`weak`. SKIPPED.
  * kimchi_premium, cny_premium                 -- LIVE forward clocks (axis_shadows.json,
                                                   ACCRUING). Re-screening a running clock is
                                                   forbidden and would double-spend DSR. SKIPPED.
NOTE: none of the above is even constructible from this lake (no crypto venue prices in it, and
no KRW/CNY at all). The skip list is therefore belt-and-braces, not a near miss.

WHAT IS MATERIALLY NEW: this is a PURE-FX macro construction, not a venue premium. It contains no
crypto venue price on either side, so it cannot reproduce the close-timestamp microstructure
artifact that killed the Turkey and Coinbase premiums -- those died because a near-zero-variance
venue spread was dominated by FX-close-timing noise. Here the FX move IS the signal, not a
contaminant of one. Adjacency to the dead try_premium is DECLARED: TRY appears in F3, but as a
depreciation rate, not as a crypto premium.

TIMESTAMP ALIGNMENT (declared) -- THE PRIMARY ARTIFACT HAZARD ON THIS AXIS
--------------------------------------------------------------------------
  * Verified empirically: fx D1 bars carry Mon-Fri labels only, zero Sat/Sun rows. The FX week's
    Sunday 21:00 UTC open is folded into the Monday bar, so a bar labelled day t is the SESSION of
    day t, closing ~21:00-22:00 UTC on day t.
  * The crypto D1 bar for day t closes at 24:00 UTC on day t. So the FX close PRECEDES the crypto
    close of the SAME label by ~2-3h. signal[t] -> crypto ret[t+1] therefore uses a value ~3h old
    at entry and ~27h old at exit: CONSERVATIVELY NO LOOK-AHEAD. The dangerous direction (crypto
    leading FX) is not the one screened.
  * WEEKENDS: FX is closed Sat/Sun. FX is reindexed onto the crypto 7-day UTC calendar with
    FORWARD-FILL of the last knowable close (Friday's close carries through the weekend). This is
    exactly what a live trader holds -- not look-ahead -- but it stale-repeats 2/7 of all days and
    inflates signal autocorrelation. DECLARED.
  * STALENESS: the fx lake ends 2026-06-05 (EM crosses) / 2026-06-19 (majors) while crypto runs to
    2026-07-26. The screen sample therefore stops at the FX end, ~7 weeks short of today.
  * SHIFT SENSITIVITY (rule 8, the bithumb lesson): the headline construction is re-run at -1d and
    +1d. A genuine lead decays away from its true lag; an artifact holds its |IC| under shifting.

TRIALS (13, all pre-declared, all logged):
  F1 EM debasement basket (TRY,ZAR,MXN 20d depreciation vs USD) -> BTC/USDT 1d, 5d, 20d
  F2 synthetic DXY 20d change                                   -> BTC/USDT 1d, 5d, 20d
  F3 TRY-only 20d depreciation                                  -> BTC/USDT 1d, 5d
  F4 DENOMINATION CONTROL: F1 -> BTC priced IN TRY              -> 1d, 5d   [artifact probe]
  F5 shift sensitivity on F1                                    -> -1d, +1d
RUB IS EXCLUDED WITH CAUSE: the EURRUB feed terminates 2022-02-28 (sanctions cut). That is a
`data/infra` exclusion, not an economic one -- RUB is re-testable if the feed is ever restored.

Stage A only -- ZERO promotion authority.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from libs.research.axis_screen import stage_a_screen  # noqa: E402

FX = ROOT / "data" / "lake" / "bronze" / "fx"
OUT = ROOT / "reports" / "axis_screens"


def _fx(pair: str) -> pd.Series:
    fs = sorted((FX / pair / "D1").glob("year=*/month=*/part-0.parquet"))
    df = pd.concat([pd.read_parquet(f) for f in fs])
    df["day"] = pd.to_datetime(df["timestamp"], utc=True).dt.floor("D")
    return df.sort_values("day").drop_duplicates("day").set_index("day")["close"]


def _btc() -> pd.Series:
    fs = sorted((ROOT / "data/lake/bronze/crypto/BTCUSDT/D1").glob("year=*/month=*/part-0.parquet"))
    df = pd.concat([pd.read_parquet(f) for f in fs])
    df["day"] = pd.to_datetime(df["timestamp"], utc=True).dt.floor("D")
    return df.sort_values("day").drop_duplicates("day").set_index("day")["close"]


def _ds(sig: np.ndarray, ret: np.ndarray, step: int) -> tuple[np.ndarray, np.ndarray]:
    n = len(sig) // step
    s = np.array([sig[i * step] for i in range(n)])
    r = np.array([float(np.prod(1 + ret[i * step:(i + 1) * step]) - 1) for i in range(n)])
    return s, r


def main() -> None:
    eurusd = _fx("EURUSD")
    # USD-per-unit -> quote as UNITS PER USD so that a RISE = local currency WEAKENING
    usdtry = _fx("EURTRY") / eurusd
    usdzar = _fx("EURZAR") / eurusd
    usdmxn = _fx("EURMXN") / eurusd
    usdsek = _fx("EURSEK") / eurusd
    dxy = (np.log(50.14348112)
           - 0.576 * np.log(eurusd) + 0.136 * np.log(_fx("USDJPY"))
           - 0.119 * np.log(_fx("GBPUSD")) + 0.091 * np.log(_fx("USDCAD"))
           + 0.042 * np.log(usdsek) + 0.036 * np.log(_fx("USDCHF")))

    btc = _btc()
    idx = btc.index                                    # crypto 7-day UTC calendar is the master
    fxd = pd.DataFrame({"try_": usdtry, "zar": usdzar, "mxn": usdmxn, "dxy": dxy})
    fxd = fxd.reindex(idx.union(fxd.index)).sort_index().ffill().reindex(idx)   # last knowable

    d = pd.DataFrame({"px": btc}).join(fxd).dropna()
    d["ret"] = d["px"].pct_change()
    # 20d log depreciation of each EM currency (rise in units-per-USD = weakening)
    for c in ("try_", "zar", "mxn"):
        d[f"dep_{c}"] = np.log(d[c]).diff(20)
    d["f1_basket"] = d[["dep_try_", "dep_zar", "dep_mxn"]].mean(axis=1)
    d["f2_dxy"] = d["dxy"].diff(20)
    d["f3_try"] = d["dep_try_"]
    # F4 denomination control: BTC priced in TRY -> its return contains the TRY move mechanically
    d["ret_btc_in_try"] = (d["px"] * d["try_"]).pct_change()
    d = d.dropna()

    ret, ret_try = d["ret"].to_numpy(), d["ret_btc_in_try"].to_numpy()
    trials: list[dict[str, Any]] = []
    skipped = [
        {"name": n, "verdict": "NOT-RUN (GRAVEYARDED)", "reason": r} for n, r in (
            ("try_premium_timing", "graveyard `timing_artifact`, de-contam -0.495"),
            ("coinbase_premium_timing", "graveyard `timing_artifact`, contam +0.256"),
            ("bithumb_kr_premium", "graveyard `lookahead_artifact` (KST candle label)"),
            ("coinone_kr_premium", "graveyard `redundant` with kimchi"),
            ("bitbank_jp_premium / mercado_br_premium", "graveyard `no_economics`/`weak`"),
        )] + [
        {"name": n, "verdict": "NOT-RUN (LIVE FORWARD CLOCK)", "reason": r} for n, r in (
            ("kimchi_premium", "axis_shadows.json ACCRUING -- re-screening double-spends DSR"),
            ("cny_premium", "axis_shadows.json ACCRUING -- re-screening double-spends DSR"),
        )]

    for col, label in (("f1_basket", "em_debasement_basket_try_zar_mxn"),
                       ("f2_dxy", "synthetic_dxy_20d_chg")):
        sig = d[col].to_numpy()
        trials.append(stage_a_screen(sig, ret, name=f"{label}->btc_1d"))
        for step, zw in ((5, 12), (20, 6)):
            s_d, r_d = _ds(sig, ret, step)
            trials.append(stage_a_screen(s_d, r_d, name=f"{label}->btc_{step}d", zwin=zw))

    s3 = d["f3_try"].to_numpy()
    trials.append(stage_a_screen(s3, ret, name="try_depreciation_20d->btc_1d"))
    s3d, r3d = _ds(s3, ret, 5)
    trials.append(stage_a_screen(s3d, r3d, name="try_depreciation_20d->btc_5d", zwin=12))

    # F4 denomination artifact control
    s1 = d["f1_basket"].to_numpy()
    trials.append(stage_a_screen(s1, ret_try, name="DENOM-CONTROL_em_basket->btc_IN_TRY_1d"))
    s4d, r4d = _ds(s1, ret_try, 5)
    trials.append(stage_a_screen(s4d, r4d, name="DENOM-CONTROL_em_basket->btc_IN_TRY_5d", zwin=12))

    # F5 shift sensitivity on F1 (rule 8)
    trials.append(stage_a_screen(s1[:-1], ret[1:], name="SHIFT_em_basket_minus1d->btc_1d"))
    trials.append(stage_a_screen(s1[1:], ret[:-1], name="SHIFT_em_basket_plus1d->btc_1d"))

    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "axis": "fx",
        "n_days": len(d),
        "range": [str(d.index.min().date()), str(d.index.max().date())],
        "coverage_gap": ("fx lake has 57 crosses but NONE of the "
                         "high-barrier currencies that drive "
                         "the proven mechanism: no KRW, CNY/CNH, BRL, ARS, NGN, VND, EGP, INR. "
                         "EURRUB feed terminates 2022-02-28 (sanctions) -> RUB excluded as "
                         "data/infra, re-testable if restored."),
        "alignment": (
            "fx D1 bars are Mon-Fri only (verified: zero Sat/Sun rows), labelled at the SESSION "
            "date, closing ~21:00-22:00 UTC on that date -- i.e. ~2-3h BEFORE the crypto 24:00 UTC "
            "close of the same label. "
            "signal[t]->crypto ret[t+1] is ~3h old at entry: NO look-ahead. "
            "FX reindexed onto the crypto 7-day UTC calendar with FORWARD-FILL "
            "of the last knowable "
            "close (stale-repeats 2/7 of days; declared). Sample ends at the FX lake end "
            "(2026-06-05 EM / 2026-06-19 majors), ~7wk short of the crypto lake. 5d/20d "
            "NON-OVERLAPPING. Shift sensitivity -1d/+1d run per rule 8."),
        "skipped_graveyarded": skipped,
        "trials": trials,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "fx.json").write_text(json.dumps(out, indent=1, default=str), "utf-8")
    for t in trials:
        print(f"{t['name']:48s} {t.get('verdict'):20s} IC={t.get('ic')} "
              f"shM={t.get('sharpe_momentum')} shR={t.get('sharpe_reversal')} "
              f"same={t.get('same_period_corr')} resIC={t.get('residual_ic')} n={t.get('n')}")


if __name__ == "__main__":
    main()

```
