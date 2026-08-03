# AUDIT SHARD 4/13 -- seat deepseek/deepseek-v4-pro

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

### libs/autodiscovery/crypto_adapter.py
```python
"""Crypto Parquet-lake -> autodiscovery factory adapter (industrialized hypothesis throughput).

Turns lake D1/H8 crypto bars into ``MarketSeries`` (with Level-3 perp ``funding`` attached) so the
generic :class:`AutoDiscoveryLab` can run the SAME validation gauntlet over the whole crypto
universe, net of real perp cost, with cross-campaign DSR deflation on the cumulative trial count.

Honesty: the ``funding_stress_reversal`` generator (LIQUIDITY family) is the one genuinely
crypto-native hypothesis here -- fading crowded perp leverage, economically distinct from the
funding *carry* the desk already harvests. The price-pattern families are EXPECTED to re-confirm
the graveyard (trend/momentum/mean-reversion over crypto majors already failed the gauntlet). That
is the honest point, not a defect: the store's content-hash dedup makes re-tests free after the
first cycle, and cumulative-trial DSR deflation makes a false survivor from breadth-mining
statistically harder, not easier. The factory's durable value is (1) the new funding-stress test,
(2) trial-count accounting across the universe, and (3) reusable infrastructure that auto-tests each
new free data axis (OI / LS / liquidations / stablecoin flows) as its forward clock matures.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from libs.autodiscovery.memory import CandidateStore
from libs.autodiscovery.models import CycleResult, Family, MarketSeries
from libs.autodiscovery.orchestrator import AutoDiscoveryLab
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.store.connection import Database

DataProvider = Callable[[str], MarketSeries | None]

_LAKE_ROOT = "data/lake"
_MIN_BARS = 250
# ~4 bps taker + slippage per side on a liquid perp; backtests are ALWAYS net of this.
COST_PER_SIDE = 5e-4
# Price patterns that fit crypto + LIQUIDITY (carries funding_stress_reversal). Crowded price-only
# families stay in to keep the trial count honest; the gauntlet, not omission, rejects them.
DEFAULT_FAMILIES: tuple[Family, ...] = (
    Family.LIQUIDITY,
    Family.MOMENTUM,
    Family.MEAN_REVERSION,
    Family.TREND,
    Family.VOLATILITY_EXPANSION,
    Family.VOLATILITY_COMPRESSION,
    Family.CROSS_ASSET,  # BTC-relative; ref_close populated below (no-lookahead)
)


def crypto_symbols(
    timeframe: Timeframe = Timeframe.D1, *, lake_root: str = _LAKE_ROOT
) -> list[str]:
    """Every crypto symbol with bars at ``timeframe`` in the lake (sorted, deterministic)."""
    root = Path(lake_root) / "bronze" / "crypto"
    if not root.exists():
        return []
    return sorted(d.name for d in root.iterdir() if (d / timeframe.value).exists())


def _read_frames(symbols: Sequence[str], timeframe: Timeframe, lake_root: str) -> dict[str, Any]:
    """Read + cache each symbol's lake frame once (indexed by timestamp)."""
    lake = ParquetLake(lake_root)
    frames = {}
    for s in symbols:
        register_instrument(InstrumentSpec(symbol=s, asset_class=AssetClass.CRYPTO, description=s))
        frames[s] = lake.read_bars(Layer.BRONZE, s, timeframe).set_index("timestamp")
    return frames


def _provider_from_frames(frames: dict[str, Any], min_bars: int) -> DataProvider:
    # BTC is the cross-asset reference (feeds MarketSeries.ref_close -> the CROSS_ASSET generator).
    # NO-LOOKAHEAD: reindex BTC's close onto each symbol's bar index with PAST-ONLY ffill (a bar's
    # ref is BTC's contemporaneous close, gaps filled from the last KNOWN past close); net_returns
    # then applies lag-1, so the position never sees future data. Leading gaps (symbol older than
    # BTC -- effectively never) leave ref_close None so the generator honestly skips (zeros).
    btc = frames.get("BTCUSDT")
    btc_close = btc["close"] if btc is not None else None

    def provider(symbol: str) -> MarketSeries | None:
        df = frames.get(symbol)
        if df is None or len(df) < min_bars:
            return None
        funding = df["funding"].to_numpy("float64") if "funding" in df.columns else None
        ref_close = None
        if btc_close is not None and symbol != "BTCUSDT":
            ref = btc_close.reindex(df.index).ffill()
            if not ref.isna().any():
                ref_close = ref.to_numpy("float64")
        return MarketSeries(
            close=df["close"].to_numpy("float64"),
            high=df["high"].to_numpy("float64"),
            low=df["low"].to_numpy("float64"),
            volume=df["volume"].to_numpy("float64"),
            hour=np.array([t.hour for t in df.index], dtype="float64"),
            ref_close=ref_close,
            funding=funding,
        )

    return provider


def lake_provider(
    symbols: Sequence[str],
    timeframe: Timeframe = Timeframe.D1,
    *,
    lake_root: str = _LAKE_ROOT,
    min_bars: int = _MIN_BARS,
) -> DataProvider:
    """Build an injectable ``symbol -> MarketSeries`` provider over cached lake frames.

    Frames are read once and cached; a symbol with fewer than ``min_bars`` bars returns ``None`` so
    the lab skips it honestly rather than testing a too-short series. ``funding`` is attached when
    present (Level-3) so the crypto-native generator is a real test, not a degrade-to-flat.
    """
    return _provider_from_frames(_read_frames(symbols, timeframe, lake_root), min_bars)


def load_universe(
    timeframe: Timeframe = Timeframe.D1,
    *,
    limit: int | None = 30,
    lake_root: str = _LAKE_ROOT,
    min_bars: int = _MIN_BARS,
) -> tuple[list[str], DataProvider]:
    """Select the TRADEABLE crypto universe (top-``limit`` by trailing dollar-volume) + a provider.

    Ranking is done OFFLINE from lake bars (median close*volume over the last ~180 bars) -- no live
    API call, so no network/geo-block failure mode in the daily cycle. Capping to the liquid names
    is economically honest AND statistically kinder: testing 200+ microcap perps is breadth-mining
    that inflates the cumulative trial count (harshening the DSR deflation on the real hypotheses)
    while adding near-zero-capacity candidates. It is also operationally robust -- the campaign-wide
    Reality-Check bootstrap over an N-wide candidate matrix is memory-heavy, so an unbounded sweep
    (~1000 candidates) OOM-crashes this box mid-cycle; ~30 liquid names keeps N bounded. The top ~30
    perps hold essentially all real research capacity anyway. ``limit=None`` keeps every symbol.
    """
    all_syms = crypto_symbols(timeframe, lake_root=lake_root)
    frames = _read_frames(all_syms, timeframe, lake_root)
    eligible = [s for s in all_syms if len(frames[s]) >= min_bars]

    def _adv(sym: str) -> float:
        df = frames[sym]
        if "volume" not in df.columns:
            return 0.0
        dollar = (df["close"] * df["volume"]).tail(180)
        return float(dollar.median()) if len(dollar) else 0.0

    eligible.sort(key=_adv, reverse=True)
    selected = eligible if limit is None else eligible[:limit]
    return selected, _provider_from_frames(frames, min_bars)


def build_lab(
    db: Database,
    provider: DataProvider,
    *,
    families: Sequence[Family] | None = DEFAULT_FAMILIES,
    cost_per_side: float = COST_PER_SIDE,
) -> AutoDiscoveryLab:
    """Wire a crypto-fed :class:`AutoDiscoveryLab` (flat per-side cost, family-restricted)."""
    return AutoDiscoveryLab(
        db,
        provider,
        cost_provider=lambda _s: cost_per_side,
        families=list(families) if families is not None else None,
    )


def web_payload(
    store: CandidateStore, result: CycleResult, *, timeframe: str = "D1"
) -> dict[str, object]:
    """Dashboard-ready summary of the crypto factory's cumulative state + this cycle's delta."""
    survivors = [
        {
            "id": r.id,
            "family": r.family,
            "subtype": r.subtype,
            "symbol": r.symbol,
            "annual_sharpe": round(float(r.metrics.annual_sharpe), 3),
            "dsr": round(float(r.metrics.dsr), 3),
        }
        for r in store.survivors()
    ]
    rejection_hist: dict[str, int] = {}
    for rec in store.all():
        if rec.survived or not rec.rejection_reason:
            continue
        body = rec.rejection_reason.removeprefix("failed: ")
        for gate in (g.strip() for g in body.split(",") if g.strip()):
            rejection_hist[gate] = rejection_hist.get(gate, 0) + 1
    return {
        "timeframe": timeframe,
        "cumulative_tested": store.total(),
        "cumulative_survivors": len(survivors),
        "by_family": store.family_counts(),
        "by_status": store.status_counts(),
        "rejection_by_gate": dict(sorted(rejection_hist.items(), key=lambda kv: -kv[1])),
        "this_cycle": {
            "tested": result.tested,
            "skipped_duplicate": result.skipped_duplicate,
            "survivors": result.survivors,
            "rejected": result.rejected,
            "promoted_to_paper": result.promoted_to_paper,
        },
        "survivors": survivors,
        "note": (
            "Industrialized crypto hypothesis factory: same gauntlet, net of real perp cost, "
            "cross-campaign DSR deflation. Zero survivors is the honest expected outcome; the "
            "funding_stress_reversal (LIQUIDITY) generator is the one crypto-native test."
        ),
    }

```

### libs/autodiscovery/regime.py
```python
"""Regime-robustness gate (committee Lever 3 / T8).

A durable edge should not live in a single market state. We split the strategy's own return series
by realized-volatility regime (low / mid / high terciles) and require it to be net-positive in at
least two of them before it can reach REGISTRY. This is the price-derivable part of regime
intelligence; macro regimes (inflation/growth/credit) remain data-gated and are NOT faked.
"""

from __future__ import annotations

import numpy as np

_MIN_BARS = 90
_VOL_WINDOW = 20


def vol_regime_labels(returns: np.ndarray, *, window: int = _VOL_WINDOW) -> np.ndarray:
    """Label each bar 0/1/2 by realized-vol tercile (low/mid/high); -1 where vol is undefined."""
    n = len(returns)
    labels = np.full(n, -1, dtype="int64")
    if n < window + 1:
        return labels
    vol = np.full(n, np.nan, dtype="float64")
    for i in range(window, n):
        vol[i] = returns[i - window + 1: i + 1].std()
    valid = ~np.isnan(vol)
    if valid.sum() < 3:
        return labels
    lo, hi = np.nanquantile(vol, [1 / 3, 2 / 3])
    labels[valid & (vol <= lo)] = 0
    labels[valid & (vol > lo) & (vol <= hi)] = 1
    labels[valid & (vol > hi)] = 2
    return labels


def regime_robust(returns: np.ndarray, *, min_positive_regimes: int = 2) -> bool:
    """True iff the strategy is net-positive in at least ``min_positive_regimes`` vol regimes."""
    if len(returns) < _MIN_BARS:
        return False  # cannot confirm robustness on a short sample -> conservative reject
    labels = vol_regime_labels(returns)
    positive = 0
    present = 0
    for r in (0, 1, 2):
        mask = labels == r
        if mask.any():
            present += 1
            if float(np.sum(returns[mask])) > 0.0:
                positive += 1
    return present >= min_positive_regimes and positive >= min_positive_regimes

```

### libs/backtest/portfolio.py
```python
"""Portfolio engine — cash, signed position, average-cost realized PnL, equity.

Supports long, short, partial exits, and reversals via average-cost accounting on a single
net position per instrument. Realized trades are recorded for profit-factor/expectancy.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from libs.backtest.events import FillEvent


@dataclass(frozen=True)
class Trade:
    """A realized (closed or partially-closed) round-turn portion."""

    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    sign: int
    units: float
    entry_price: float
    exit_price: float
    pnl: float


@dataclass
class PortfolioEngine:
    """Tracks cash, net position, and realized trades through fills."""

    init_cash: float
    cash: float = field(init=False)
    units: float = 0.0
    entry_price: float = 0.0
    entry_time: pd.Timestamp | None = None
    trades: list[Trade] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.cash = self.init_cash

    def apply_fill(self, fill: FillEvent) -> None:
        """Apply a fill to cash/position, recording realized PnL on reductions/reversals."""
        delta = fill.units_delta
        price = fill.price
        self.cash -= delta * price
        self.cash -= fill.commission
        new_units = self.units + delta

        if self.units == 0.0:
            self.entry_price = price
            self.entry_time = fill.timestamp
        elif (self.units > 0 and delta > 0) or (self.units < 0 and delta < 0):
            total = self.entry_price * abs(self.units) + price * abs(delta)
            self.entry_price = total / abs(new_units)
        else:
            closing = min(abs(delta), abs(self.units))
            sign = 1 if self.units > 0 else -1
            pnl = closing * (price - self.entry_price) * sign - fill.commission
            self.trades.append(
                Trade(
                    entry_time=self.entry_time if self.entry_time is not None else fill.timestamp,
                    exit_time=fill.timestamp,
                    sign=sign,
                    units=closing,
                    entry_price=self.entry_price,
                    exit_price=price,
                    pnl=pnl,
                )
            )
            if abs(delta) > abs(self.units):
                self.entry_price = price  # reversal: remainder opens a new position
                self.entry_time = fill.timestamp
            elif new_units == 0.0:
                self.entry_price = 0.0
                self.entry_time = None

        self.units = new_units

    def equity(self, mark_price: float) -> float:
        """Mark-to-market equity at ``mark_price``."""
        return self.cash + self.units * mark_price

```

### libs/data/__init__.py
```python
"""``libs.data`` — MT5 ingestion, the Parquet medallion lake, DuckDB, and data quality."""

from __future__ import annotations

from libs.data.calendar import expected_index, is_open, session_of
from libs.data.duckdb_client import DuckDBClient
from libs.data.errors import DataError, MT5Error
from libs.data.instruments import (
    SUPPORTED_SYMBOLS,
    AssetClass,
    InstrumentSpec,
    get_spec,
    is_supported,
)
from libs.data.lake import Layer, ParquetLake
from libs.data.medallion import build_bronze, build_gold, build_silver
from libs.data.mt5_source import (
    BarSource,
    MT5BarSource,
    load_mt5_bars,
    normalize_timezone,
)
from libs.data.quality import (
    QualityReport,
    compute_quality_score,
    detect_duplicates,
    detect_gaps,
    detect_missing_bars,
    detect_spikes,
)
from libs.data.schema import BAR_COLUMNS, empty_bars, validate_bars
from libs.data.timeframe import Timeframe

__all__ = [  # noqa: RUF022  # grouped by concern
    # instruments / timeframe
    "AssetClass",
    "InstrumentSpec",
    "get_spec",
    "is_supported",
    "SUPPORTED_SYMBOLS",
    "Timeframe",
    # schema
    "BAR_COLUMNS",
    "empty_bars",
    "validate_bars",
    # ingestion
    "BarSource",
    "MT5BarSource",
    "load_mt5_bars",
    "normalize_timezone",
    # calendar
    "is_open",
    "expected_index",
    "session_of",
    # quality
    "QualityReport",
    "detect_duplicates",
    "detect_missing_bars",
    "detect_spikes",
    "detect_gaps",
    "compute_quality_score",
    # lake + duckdb + medallion
    "Layer",
    "ParquetLake",
    "DuckDBClient",
    "build_bronze",
    "build_silver",
    "build_gold",
    # errors
    "DataError",
    "MT5Error",
]

```

### libs/execution/algos.py
```python
"""Execution algorithm framework — deterministic child-order schedules.

Produces a schedule of child orders (offset + quantity) for a parent order without submitting them;
the :class:`ExecutionEngine` submits the slices. Three algos: TWAP (even over time), POV (paced to
a volume curve at a participation rate), and Implementation Shortfall (front-loaded by urgency).
Every schedule's quantities sum exactly to the parent quantity (the final slice absorbs rounding).
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from libs.execution.errors import ExecutionError


class ChildOrder(BaseModel):
    model_config = ConfigDict(frozen=True)

    offset_seconds: int
    qty: float


class ExecutionPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    algo: str
    symbol: str
    side: str
    total_qty: float
    slices: list[ChildOrder] = Field(default_factory=list)
    notes: str = ""

    @property
    def scheduled_qty(self) -> float:
        return sum(c.qty for c in self.slices)


def _validate(symbol: str, side: str, total_qty: float) -> None:
    if side not in ("buy", "sell"):
        raise ExecutionError(f"side must be 'buy' or 'sell', got {side!r}")
    if total_qty <= 0:
        raise ExecutionError("total_qty must be positive")
    if not symbol:
        raise ExecutionError("symbol is required")


def _finalize(
    weights: Sequence[float], total_qty: float, interval_seconds: int
) -> list[ChildOrder]:
    """Turn slice weights into child orders whose quantities sum exactly to ``total_qty``."""
    total_w = sum(weights)
    if total_w <= 0:
        raise ExecutionError("schedule weights must be positive")
    slices: list[ChildOrder] = []
    allocated = 0.0
    n = len(weights)
    for i, w in enumerate(weights):
        if i == n - 1:
            qty = total_qty - allocated  # last slice absorbs rounding
        else:
            qty = round(total_qty * (w / total_w), 10)
            allocated += qty
        slices.append(ChildOrder(offset_seconds=i * interval_seconds, qty=qty))
    return slices


class ExecutionScheduler:
    """Builds deterministic execution schedules."""

    def twap(
        self, *, symbol: str, side: str, total_qty: float, n_slices: int, interval_seconds: int
    ) -> ExecutionPlan:
        _validate(symbol, side, total_qty)
        if n_slices < 1:
            raise ExecutionError("n_slices must be >= 1")
        slices = _finalize([1.0] * n_slices, total_qty, interval_seconds)
        return ExecutionPlan(
            algo="twap", symbol=symbol, side=side, total_qty=total_qty, slices=slices,
            notes=f"even over {n_slices} slices",
        )

    def pov(
        self,
        *,
        symbol: str,
        side: str,
        total_qty: float,
        volume_curve: Sequence[float],
        participation_rate: float,
        interval_seconds: int,
    ) -> ExecutionPlan:
        _validate(symbol, side, total_qty)
        if not 0.0 < participation_rate <= 1.0:
            raise ExecutionError("participation_rate must be in (0, 1]")
        if not volume_curve or any(v < 0 for v in volume_curve):
            raise ExecutionError("volume_curve must be non-empty and non-negative")
        slices: list[ChildOrder] = []
        remaining = total_qty
        for i, bucket_volume in enumerate(volume_curve):
            if remaining <= 0:
                break
            qty = min(remaining, participation_rate * bucket_volume)
            if qty <= 0:
                continue
            slices.append(ChildOrder(offset_seconds=i * interval_seconds, qty=qty))
            remaining -= qty
        if remaining > 1e-12:  # curve capacity exhausted before the order filled
            if slices:
                last = slices[-1]
                slices[-1] = ChildOrder(
                    offset_seconds=last.offset_seconds, qty=last.qty + remaining
                )
            else:
                slices.append(ChildOrder(offset_seconds=0, qty=total_qty))
        return ExecutionPlan(
            algo="pov", symbol=symbol, side=side, total_qty=total_qty, slices=slices,
            notes=f"participation {participation_rate:.2%} of volume",
        )

    def implementation_shortfall(
        self,
        *,
        symbol: str,
        side: str,
        total_qty: float,
        n_slices: int,
        interval_seconds: int,
        urgency: float = 0.5,
    ) -> ExecutionPlan:
        _validate(symbol, side, total_qty)
        if n_slices < 1:
            raise ExecutionError("n_slices must be >= 1")
        urgency = max(0.0, min(1.0, urgency))
        # Front-load with geometric decay: higher urgency -> steeper decay -> more traded early.
        decay = 1.0 - 0.9 * urgency  # urgency 0 -> 1.0 (flat/TWAP), urgency 1 -> 0.1 (steep)
        weights = [decay**i for i in range(n_slices)]
        slices = _finalize(weights, total_qty, interval_seconds)
        return ExecutionPlan(
            algo="implementation_shortfall", symbol=symbol, side=side, total_qty=total_qty,
            slices=slices, notes=f"front-loaded, urgency={urgency:.2f}",
        )

```

### libs/features/errors.py
```python
"""Feature-layer exceptions."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class FeatureError(QuantPlatformError):
    """Generic feature error (bad definition, missing inputs, duplicate version)."""


class LeakageError(FeatureError):
    """A feature looks into the future (lookahead / future / hindsight / full-sample leakage)."""


class ParityError(FeatureError):
    """A feature's offline (training) and online (serving) computations disagree."""

```

### libs/ops/__init__.py
```python
"""``libs.ops`` — disaster recovery, backup, and operational resilience.

Consistent SQLite backups with checksum manifests, a restore drill that proves recoverability,
a heartbeat watchdog, and a fail-closed safe-halt controller that fuses the platform's hard stop
signals. Recommend-only decisions; the execution/risk layers enforce them.
"""

from __future__ import annotations

from libs.ops.backup import BackupManager, BackupManifest, RestoreDrill
from libs.ops.errors import OpsError
from libs.ops.watchdog import HaltDecision, ProcessWatchdog, SafeHaltController

__all__ = [
    "BackupManager",
    "BackupManifest",
    "HaltDecision",
    "OpsError",
    "ProcessWatchdog",
    "RestoreDrill",
    "SafeHaltController",
]

```

### libs/ops/carryover.py
```python
"""§37 CARRY-OVER -- work owed survives an outage and is handed back when the brain returns.

The desk's brain is a metered LLM session. It dies on quota, on session limits, on a bad model
route -- and when it does, the cycle's owed work is simply gone: the next cycle starts from
whatever the sweep happens to report at that moment, with no memory that anything was already
owed, for how long, or how many cycles have passed without it being touched. Detection of the
death already exists (`max_audit.check_stub_deaths` reads the death markers out of the logs).
What did NOT exist is the other half: the work PILING UP across the outage and being handed back.

This module is that half. It keeps an append-only ledger of what each sweep found owed, and from
consecutive snapshots derives the one thing a single sweep can never know -- HOW LONG something
has been owed, and how many cycles have run past it.

THE DISTINCTION THAT MATTERS, and the reason this is not just another queue:

  LOST TO OUTAGE   -- sweeps where the brain died on quota. Items accumulated through no fault of
                      the cycle; the honest response is to hand them back with their true age, not
                      to treat the gap as neglect.
  SEEN AND SKIPPED -- sweeps where the brain RAN, was shown the item, and it survived anyway. That
                      is not a backlog, it is avoidance, and it is the failure mode a plain queue
                      hides: a long queue looks the same whether nobody was home or everybody
                      walked past it.

Only the second is a defect. Conflating them either punishes the desk for an outage or excuses it
for ignoring work -- and the second mistake is the expensive one.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

#: Log fragments that mean a brain cycle died rather than finished. Mirrors
#: ``max_audit._DEATH_MARKERS`` -- kept here so this module stays importable on its own.
DEATH_MARKERS = (
    "out of usage credits", "session limit", "hit your limit", "usage limit",
    "issue with the selected model", "rate limit", "quota",
)

SweepRow = Mapping[str, Any]


def record_sweep(
    path: Path, defect_ids: Sequence[str], *, ts: float, brain_alive: bool = True
) -> None:
    """Append one line: what was owed at this sweep, and whether the brain was up to see it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": float(ts), "ids": sorted(set(defect_ids)), "alive": bool(brain_alive)}
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def load_sweeps(path: Path) -> list[dict[str, Any]]:
    """Read the sweep ledger, skipping corrupt lines rather than losing the whole history."""
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text("utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(r, dict) and "ts" in r and isinstance(r.get("ids"), list):
            rows.append(r)
    return sorted(rows, key=lambda r: float(r["ts"]))


class CarryItem(BaseModel):
    """One defect that has outlived at least one sweep."""

    model_config = ConfigDict(frozen=True)

    defect_id: str
    first_seen: float
    age_days: float
    sweeps_survived: int      # total sweeps this has been owed through
    seen_by_live_brain: int   # of those, how many ran with the brain UP -- the damning number

    @property
    def skipped(self) -> bool:
        """Survived sweeps the brain was awake for: shown the work, did not do it."""
        return self.seen_by_live_brain >= 2


class CarryoverState(BaseModel):
    """What is owed, how old it is, and how much of the gap was an outage."""

    model_config = ConfigDict(frozen=True)

    n_sweeps: int
    n_dead_sweeps: int        # cycles lost to quota/session death
    items: tuple[CarryItem, ...]
    verdict: str

    @property
    def skipped_items(self) -> tuple[CarryItem, ...]:
        return tuple(i for i in self.items if i.skipped)


def carryover_state(sweeps: Sequence[SweepRow], *, now: float) -> CarryoverState:
    """Derive age and skip-count per still-owed defect from consecutive sweep snapshots."""
    if not sweeps:
        return CarryoverState(n_sweeps=0, n_dead_sweeps=0, items=(),
                              verdict="no sweep history yet -- nothing carried")
    first: dict[str, float] = {}
    total: dict[str, int] = {}
    live: dict[str, int] = {}
    for row in sweeps:
        ts, alive = float(row["ts"]), bool(row.get("alive", True))
        for did in row["ids"]:
            d = str(did)
            first.setdefault(d, ts)
            total[d] = total.get(d, 0) + 1
            if alive:
                live[d] = live.get(d, 0) + 1
    still_owed = {str(d) for d in sweeps[-1]["ids"]}
    items = tuple(sorted(
        (CarryItem(defect_id=d, first_seen=first[d],
                   age_days=round((now - first[d]) / 86400.0, 2),
                   sweeps_survived=total[d], seen_by_live_brain=live.get(d, 0))
         for d in still_owed),
        key=lambda i: (-i.seen_by_live_brain, -i.age_days),
    ))
    dead = sum(1 for r in sweeps if not bool(r.get("alive", True)))
    skipped = [i for i in items if i.skipped]

    if not items:
        verdict = f"nothing owed across {len(sweeps)} sweep(s) -- the queue is genuinely empty"
    elif skipped:
        verdict = (
            f"{len(skipped)} item(s) survived sweeps the brain was AWAKE for -- shown the work and "
            f"not done. {dead} cycle(s) were lost to quota; those are not the excuse for these. "
            "A long queue looks identical whether nobody was home or everybody walked past it; "
            "this is the second case."
        )
    elif dead:
        verdict = (f"{len(items)} item(s) owed, {dead} cycle(s) lost to quota -- accumulated "
                   "through no fault of the cycle. Hand them back with their true age.")
    else:
        verdict = f"{len(items)} item(s) owed, all fresh -- nothing has been skipped yet"
    return CarryoverState(n_sweeps=len(sweeps), n_dead_sweeps=dead, items=items, verdict=verdict)


def brief(state: CarryoverState, *, max_items: int = 12) -> str:
    """The block handed to the brain at cycle start -- oldest and most-skipped first."""
    if not state.items:
        return "[§37 CARRY-OVER] queue empty -- nothing owed from previous cycles."
    lines = [
        "[§37 CARRY-OVER] WORK OWED FROM PREVIOUS CYCLES -- do these FIRST, in this order.",
        f"  {state.verdict}",
        f"  ({state.n_sweeps} sweeps on record, {state.n_dead_sweeps} lost to quota/session death)",
        "",
    ]
    for i in state.items[:max_items]:
        mark = "SKIPPED" if i.skipped else "owed"
        lines.append(
            f"  [{mark:7}] {i.defect_id}  age {i.age_days:.1f}d  "
            f"survived {i.sweeps_survived} sweep(s), {i.seen_by_live_brain} with the brain awake"
        )
    if len(state.items) > max_items:
        lines.append(f"  ... and {len(state.items) - max_items} more")
    lines += [
        "",
        "  An item marked SKIPPED was shown to a LIVE cycle at least twice and survived. Either",
        "  do it now, or record in the ledger WHY it is not being done -- silently carrying it a",
        "  third time is the behaviour this brief exists to stop.",
    ]
    return "\n".join(lines)

```

### libs/portfolio/construction.py
```python
"""Crypto sleeve-allocation primitives (portfolio construction).

Pure, tested functions that turn per-sleeve Sharpes + a correlation matrix into long-only sleeve
weights -- the capital-allocation step that sits above the sleeves. Deliberately small and numeric
(no pydantic models) so it wires straight onto crypto_portfolio.json. Reuses risk_parity_weights for
the RP variant. Everything is in-sample by construction; the caller is responsible for the
anti-overfit blend and for treating results as SHADOW until forward-validated.
"""

from __future__ import annotations

import numpy as np


def portfolio_sharpe(weights: np.ndarray, sharpes: np.ndarray, corr: np.ndarray) -> float:
    """Expected portfolio Sharpe for sleeve weights, treating each sleeve's vol as 1 (Sharpe space):
    S_p = wᵀμ / sqrt(wᵀ C w). This is the standard quadrature combine, correlation-aware."""
    w = np.asarray(weights, float)
    mu = np.asarray(sharpes, float)
    c = np.asarray(corr, float)
    var = float(w @ c @ w)
    return float(w @ mu) / (var ** 0.5) if var > 0 else 0.0


def max_sharpe_weights(sharpes: np.ndarray, corr: np.ndarray, *,
                       ridge: float = 1e-2, floor: float = 0.0) -> np.ndarray:
    """Long-only max-Sharpe sleeve weights, w proportional to inv(corr) @ Sharpes; negatives clipped
    to `floor`, renormalised. Ridge-regularised so a near-singular correlation stays invertible."""
    mu = np.asarray(sharpes, float)
    n = len(mu)
    c = np.asarray(corr, float) + ridge * np.eye(n)
    try:
        w = np.linalg.solve(c, mu)
    except np.linalg.LinAlgError:
        w = np.linalg.pinv(c) @ mu
    w = np.clip(w, floor, None)
    s = w.sum()
    return w / s if s > 0 else np.full(n, 1.0 / n)


def concentration_cap(weights: np.ndarray, cap: float = 0.35) -> np.ndarray:
    """Enforce a hard per-sleeve weight cap, redistributing the excess pro-rata to uncapped sleeves
    (the 35% concentration control). Iterates until every weight respects the cap."""
    w = np.asarray(weights, float).copy()
    if cap >= 1.0 or w.sum() <= 0:
        return w
    for _ in range(200):
        over = w > cap + 1e-12
        if not over.any():
            break
        excess = float((w[over] - cap).sum())
        w[over] = cap
        under = ~over
        pool = float(w[under].sum())
        if pool <= 0:
            break
        w[under] += excess * w[under] / pool
    return w


def marginal_sharpe(weights: np.ndarray, sharpes: np.ndarray, corr: np.ndarray) -> np.ndarray:
    """Each sleeve's marginal contribution to portfolio Sharpe = S_p(with) - S_p(without), holding
    the other weights' proportions. The honest 'is this sleeve pulling its weight' number."""
    w = np.asarray(weights, float)
    full = portfolio_sharpe(w, sharpes, corr)
    out = np.zeros(len(w))
    for i in range(len(w)):
        w2 = w.copy()
        w2[i] = 0.0
        s = w2.sum()
        out[i] = full - (portfolio_sharpe(w2 / s, sharpes, corr) if s > 0 else 0.0)
    return out


def blend(w1: np.ndarray, w2: np.ndarray, alpha: float) -> np.ndarray:
    """Convex blend alpha*w1 + (1-alpha)*w2 -- the anti-overfit cap (e.g. 50% model / 50% equal)."""
    return alpha * np.asarray(w1, float) + (1.0 - alpha) * np.asarray(w2, float)


def turnover(old: dict[str, float], new: dict[str, float]) -> float:
    """One-way turnover between two weight books, 0.5 * sum|new-old| (drives the rebalance call)."""
    keys = set(old) | set(new)
    return 0.5 * sum(abs(new.get(k, 0.0) - old.get(k, 0.0)) for k in keys)

```

### libs/research/crossasset.py
```python
"""Cross-asset diversified-portfolio strategy cores (global research, MT5 execution).

Single-name FX directional already returned zero survivors. The construction that rescued crypto
funding (single-name -> dollar-neutral cross-sectional portfolio) is applied here to instruments the
broker can actually trade (FX, metals, energy, indices, crypto CFDs):

  * ``xsec_signal_returns`` -- generic dollar-neutral cross-sectional book driven by ANY global
    signal (price momentum, Binance funding, a macro factor...). Long the top/bottom signal
    quantile, inverse-vol within each leg, turnover band, per-symbol turnover cost, and an optional
    per-symbol DAILY HOLDING COST (CFD overnight financing / swap). Returns are PRICE-ONLY: holding
    an MT5 CFD does not pay perpetual funding, so a funding-derived edge must survive on the price
    move alone, net of the financing you actually pay. This is the honest MT5-execution accounting.
  * ``xsec_momentum_returns`` -- convenience wrapper: signal = trailing return (momentum/reversal).
  * ``trend_basket_returns``  -- time-series momentum (managed-futures): each asset long/short by
    the sign of its own trend, inverse-vol sized, gross-normalized, net of turnover + holding cost.

Pure functions of (close, signal, cost) so the same code drives a backtest and a forward shadow.
No parameter mining inside -- the caller freezes the deployable variant. Decisions use only lagged
information (``.shift(1)``); no look-ahead.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _inv_vol(ret: pd.DataFrame, vol_window: int) -> pd.DataFrame:
    return 1.0 / ret.rolling(vol_window).std().shift(1)


def _hold(prev: pd.Series, hold_cost: dict[str, float] | None) -> float:
    if not hold_cost:
        return 0.0
    return float(sum(abs(prev[s]) * hold_cost.get(s, 0.0) for s in prev.index))


def xsec_signal_returns(
    close: pd.DataFrame,
    signal: pd.DataFrame,
    cost: dict[str, float],
    *,
    q: float,
    band: float,
    vol_window: int = 30,
    min_names: int = 6,
    long_high: bool = True,
    hold_cost: dict[str, float] | None = None,
) -> np.ndarray:
    """Daily PRICE-ONLY net return of a dollar-neutral cross-sectional book on ``signal``.

    ``signal`` is the point-in-time factor (lagged one bar internally). ``long_high`` buys the top
    quantile and shorts the bottom; flip it to long the lowest-signal names. ``hold_cost`` is the
    per-symbol daily financing charged on the position held (CFD swap) -- the cost that makes a
    funding edge expensive to express via CFDs rather than perps.
    """
    ret = close.pct_change(fill_method=None)
    inv_vol = _inv_vol(ret, vol_window)
    sig_l = signal.shift(1)
    out = np.zeros(len(close), dtype="float64")
    prev = pd.Series(0.0, index=close.columns)
    for t in range(1, len(close)):
        s = sig_l.iloc[t].dropna()
        valid = close.iloc[t].reindex(s.index).notna() & ret.iloc[t].reindex(s.index).notna()
        s = s.reindex(s.index[valid]).dropna()
        if len(s) < min_names:
            out[t] = float((prev * ret.iloc[t].reindex(prev.index).fillna(0.0)).sum())
            out[t] -= _hold(prev, hold_cost)
            continue
        k = max(1, int(len(s) * q))
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
        w = w.where(delta > band, prev)                     # turnover band
        price_ret = float((w * ret.iloc[t].reindex(w.index).fillna(0.0)).sum())
        turn_cost = float(sum(abs(w[s2] - prev[s2]) * cost.get(s2, 1.0e-3) for s2 in w.index))
        out[t] = price_ret - turn_cost - _hold(w, hold_cost)
        prev = w
    return out


def xsec_momentum_returns(
    close: pd.DataFrame,
    cost: dict[str, float],
    *,
    lookback: int,
    q: float,
    band: float,
    vol_window: int = 30,
    min_names: int = 6,
    long_high: bool = True,
    hold_cost: dict[str, float] | None = None,
) -> np.ndarray:
    """Cross-sectional momentum (``long_high``) or short-term reversal (``long_high=False``)."""
    signal = close / close.shift(lookback) - 1.0
    return xsec_signal_returns(close, signal, cost, q=q, band=band, vol_window=vol_window,
                               min_names=min_names, long_high=long_high, hold_cost=hold_cost)


def vol_target(
    returns: np.ndarray,
    *,
    target_ann_vol: float = 0.10,
    lookback: int = 30,
    max_leverage: float = 3.0,
    ppy: float = 252.0,
) -> np.ndarray:
    """Scale a return stream to a constant target volatility using trailing realized vol (lagged).

    Standard managed-futures overlay: lever up in calm regimes, cut exposure when realized vol
    spikes (i.e. before/into crises). Leverage is lagged one bar (no look-ahead) and capped. Risk
    engineering, not parameter mining -- it targets tail risk/fragility; Sharpe is invariant to
    *constant* leverage, so any Sharpe change comes only from time-variation in exposure.
    """
    r = np.asarray(returns, dtype="float64")
    s = pd.Series(r)
    realized = s.rolling(lookback).std().shift(1) * np.sqrt(ppy)
    lev = (target_ann_vol / realized).clip(upper=max_leverage)
    lev = lev.fillna(0.0).to_numpy()
    return np.asarray(lev * r, dtype="float64")


def trend_basket_weights(
    close: pd.DataFrame,
    *,
    lookback: int,
    vol_window: int = 30,
    min_names: int = 4,
) -> dict[str, float]:
    """Latest target weights of the trend basket (the brain's decision to hand to execution).

    Gross-normalized to 1 (sum of absolute weights), band-free -- turnover is the executor's job
    (the rebalancer applies the drift threshold). Returns {} if too few names are available.
    """
    if len(close) <= lookback + 1:
        return {}
    ret = close.pct_change(fill_method=None)
    inv_vol = (1.0 / ret.rolling(vol_window).std()).iloc[-1]
    trend = np.sign(close.iloc[-1] / close.iloc[-1 - lookback] - 1.0)
    trend = trend[close.iloc[-1].notna()].dropna()
    if len(trend) < min_names:
        return {}
    raw = trend * inv_vol.reindex(trend.index).fillna(0.0)
    gross = float(raw.abs().sum())
    if gross <= 0:
        return {}
    return {k: float(v) for k, v in (raw / gross).items() if v != 0.0}


def xsec_momentum_weights(
    close: pd.DataFrame,
    *,
    lookback: int,
    q: float,
    vol_window: int = 30,
    min_names: int = 6,
    long_high: bool = True,
) -> dict[str, float]:
    """Latest dollar-neutral cross-sectional momentum target weights (+0.5 long / -0.5 short)."""
    if len(close) <= lookback + 1:
        return {}
    ret = close.pct_change(fill_method=None)
    inv_vol = (1.0 / ret.rolling(vol_window).std()).iloc[-1]
    sig = (close.iloc[-1] / close.iloc[-1 - lookback] - 1.0)
    sig = sig[close.iloc[-1].notna()].dropna()
    if len(sig) < min_names:
        return {}
    k = max(1, int(len(sig) * q))
    ranked = sig.sort_values(ascending=not long_high)
    longs, shorts = ranked.index[:k], ranked.index[-k:]
    lw = inv_vol.reindex(longs).fillna(0.0)
    sw = inv_vol.reindex(shorts).fillna(0.0)
    out: dict[str, float] = {}
    if lw.sum() > 0:
        out.update({s: 0.5 * float(lw[s]) / float(lw.sum()) for s in longs})
    if sw.sum() > 0:
        out.update({s: -0.5 * float(sw[s]) / float(sw.sum()) for s in shorts})
    return out


def combine_weights(*books: dict[str, float], renorm: bool = True) -> dict[str, float]:
    """Equal-risk combine target-weight books, then gross-normalize to 1 (max-robustness book)."""
    n = len(books)
    if n == 0:
        return {}
    keys = sorted({k for b in books for k in b})
    merged = {k: sum(b.get(k, 0.0) for b in books) / n for k in keys}
    if not renorm:
        return merged
    gross = sum(abs(v) for v in merged.values())
    if gross <= 0:
        return {}
    return {k: v / gross for k, v in merged.items() if v != 0.0}


def trend_basket_returns(
    close: pd.DataFrame,
    cost: dict[str, float],
    *,
    lookback: int,
    band: float,
    vol_window: int = 30,
    min_names: int = 4,
    hold_cost: dict[str, float] | None = None,
) -> np.ndarray:
    """Daily net return of a time-series-momentum (managed-futures) basket.

    Each asset is held long or short by the sign of its own lagged ``lookback``-day return, sized
    inverse-vol, with the book gross-normalized to 1 so it is comparable across runs.
    """
    ret = close.pct_change(fill_method=None)
    inv_vol = _inv_vol(ret, vol_window)
    trend = np.sign((close / close.shift(lookback) - 1.0).shift(1))
    out = np.zeros(len(close), dtype="float64")
    prev = pd.Series(0.0, index=close.columns)
    for t in range(1, len(close)):
        tr = trend.iloc[t].dropna()
        valid = close.iloc[t].reindex(tr.index).notna() & ret.iloc[t].reindex(tr.index).notna()
        tr = tr.reindex(tr.index[valid]).dropna()
        if len(tr) < min_names:
            out[t] = float((prev * ret.iloc[t].reindex(prev.index).fillna(0.0)).sum())
            out[t] -= _hold(prev, hold_cost)
            continue
        iv = inv_vol.iloc[t].reindex(tr.index).fillna(0.0)
        raw = tr * iv
        gross = raw.abs().sum()
        w = pd.Series(0.0, index=close.columns)
        if gross > 0:
            w[tr.index] = raw / gross
        delta = (w - prev).abs()
        w = w.where(delta > band, prev)
        price_ret = float((w * ret.iloc[t].reindex(w.index).fillna(0.0)).sum())
        turn_cost = float(sum(abs(w[s] - prev[s]) * cost.get(s, 1.0e-3) for s in w.index))
        out[t] = price_ret - turn_cost - _hold(w, hold_cost)
        prev = w
    return out

```

### libs/research/crypto_regime.py
```python
"""Crypto regime detection + per-regime sleeve performance.

Many crypto edges only work in specific environments (funding carry shines in funding-rich,
leveraged markets; trend in directional regimes; everything correlates in a crash). This labels each
day by three orthogonal regime axes -- trend (bull/bear), volatility (high/low), funding
(rich/poor) -- from lagged BTC/aggregate signals (no look-ahead), and measures each sleeve's Sharpe
within each regime so the portfolio can lean on edges only where they actually pay.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from libs.validation.dsr import sharpe_ratio

_PPY = 365.0


def regime_labels(close: pd.DataFrame, funding: pd.DataFrame, *,
                  btc: str = "BTCUSDT") -> pd.DataFrame:
    """Per-day regime labels (lagged): trend (bull/bear), vol (high/low), funding (rich/poor)."""
    ref = close[btc] if btc in close.columns else close.mean(axis=1)
    ret = ref.pct_change(fill_method=None)
    trend = np.sign(ref / ref.shift(50) - 1.0).shift(1)
    rv = ret.rolling(30).std().shift(1)
    agg_funding = funding.mean(axis=1).rolling(7).mean().shift(1)
    out = pd.DataFrame(index=close.index)
    out["trend"] = np.where(trend > 0, "bull", "bear")
    out["vol"] = np.where(rv > rv.rolling(180, min_periods=60).median(), "high_vol", "low_vol")
    out["funding"] = np.where(agg_funding > agg_funding.rolling(180, min_periods=60).median(),
                              "funding_rich", "funding_poor")
    return out


def _sh(r: np.ndarray) -> float:
    a = r[r != 0.0]
    return round(float(sharpe_ratio(a) * np.sqrt(_PPY)), 2) if len(a) > 5 else 0.0


def regime_performance(
    sleeves: dict[str, np.ndarray], labels: pd.DataFrame, port: np.ndarray,
) -> dict[str, dict[str, float]]:
    """Sharpe of each sleeve + the portfolio within each regime bucket (diagnostic, in-sample)."""
    series = {**sleeves, "portfolio": port}
    out: dict[str, dict[str, float]] = {}
    for axis in labels.columns:
        for bucket in sorted(labels[axis].dropna().unique()):
            mask = (labels[axis] == bucket).to_numpy()
            key = f"{axis}:{bucket}"
            out[key] = {name: _sh(r[mask]) for name, r in series.items()}
            out[key]["_days"] = int(mask.sum())
    return out

```

### libs/research/mine_conversion.py
```python
"""§33 MINED-TO-WIRED law -- zero research inventory, and a closed loop back into generation.

Mined intelligence is INVENTORY, and un-converted inventory is WASTE that depreciates. A finding
that is catalogued and never wired has produced NEGATIVE value: it consumed a cycle, it inflates
the desk's capability inventory, and it makes every downstream audit read the desk as richer than
it is (the map-vs-territory failure this audit family exists to catch). Mining is not the product
-- CONVERSION is. A perfect dig with zero conversions is a FAILED cycle.

This module is the machine-checkable half of §33. It does NOT do conversions (nothing automates
that -- it is irreducibly research work); it makes the backlog impossible to not see, prices it,
and feeds the outcome back into what gets mined next. §31 only started working when a daily check
with a 48h escalation stood behind it; this is the same shape, in four layers:

  1. DISPOSITION (stock)   -- every carded find owes exactly one disposition; silence is a defect.
  2. QUALITY               -- a disposition is not automatically a conversion. `killed` must be
                              backed by a real graveyard entry, so "kill everything" stops being
                              the cheapest legal way to unblock mining.
  3. VALUE (weighted)      -- a Tier-1 defect-closer outranks a Tier-4 operator, so the gate
                              cannot be cleared by converting only the easy tail.
  4. FLOW + FEEDBACK       -- conversion LATENCY and per-class conversion RATES are tracked over
                              time, and the rates become priors that steer future generation.
                              A gate that only blocks is a fence; a gate that reweights is a
                              control system, and the second one is what "maximum utilisation"
                              actually means.

DISPOSITION CONTRACT -- written inline in the dig-output doc as ``[§33: <disposition>]`` on the
item's OWN line (a blanket tag atop a document launders nothing). Four legal values, no fifth:

  wired            -- code exists AND executed AND wrote a real artifact
  screened         -- a Stage-A screen RAN; result in research_memory, --axis tagged
  killed           -- a graveyard entry carrying the MECHANISM of death (never "low priority")
  deferred(DATE)   -- a NAMED blocker and an ISO date. UNDATED DEFERRAL IS ILLEGAL -- it is the
                      hiding place every rotting backlog uses, so it is parsed and rejected.

An optional ``tier:N`` component overrides the inferred tier:
``[§33: deferred(2026-09-01) tier:1]``.

Three anti-gaming rules are structural, not advisory:

  EXPIRY   -- a deferral stops counting the moment its date passes. A promise with a clock, not a
              filing cabinet.
  NO SELF-GRADING -- wired/screened/killed are CLAIMS about artifacts. The caller passes what it
              could corroborate on disk; anything else is UNBACKED. An organ does not grade its
              own homework (same artifact-only credit rule as ``max_audit._converted_axes``).
  NO CHEAP EXIT -- because `killed` is artifact-checked against the graveyard, mass-killing the
              backlog costs strictly more than converting it. The escape hatch is closed by
              construction rather than by asking nicely.
"""

from __future__ import annotations

import json
import re
import statistics
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

#: The id is captured separately so it never lands in ``name`` -- a name of "1. Upbit" would fail
#: to match the artifact "upbit_krw_btc_1m" in either direction and report a real conversion as
#: unbacked. Matches ``source_backlog``'s card_id/name split.
#: Deliberately NOT bold bullets: source cards carry ``- **Provenance**:`` / ``- **Queries used**:``
#: metadata fields, and treating those as finds made the check fire 92/92 on its first real run.
#: A check that flags everything is ignored, so the id-numbered card is the one unambiguous unit.
_ITEM_RE = re.compile(r"^### (?P<cid>\d+)\.\s+(?P<card>.+?)\s*$", re.MULTILINE)
#: The inline disposition tag. Tolerant of "S33"/"section 33" so an ASCII-only writer still counts.
_DISP_RE = re.compile(
    r"\[(?:§|S|section\s*)33:\s*(?P<verb>[a-z-]+)\s*"
    r"(?:\(\s*(?P<until>[0-9]{4}-[0-9]{2}-[0-9]{2})\s*\))?"
    r"(?:[\s,]*tier\s*:\s*(?P<tier>[1-4]))?"
    r"(?:\s*(?:->|@)\s*(?P<art>[^\]]+?))?\s*\]",
    re.IGNORECASE,
)

#: One appended snapshot row: heterogeneous by nature (float ts + list of item dicts).
LedgerRow = Mapping[str, Any]

LEGAL = ("wired", "screened", "killed", "deferred")
#: Terminal dispositions -- the item is finished and never re-enters the backlog.
_TERMINAL = ("wired", "screened", "killed")
#: Every terminal disposition asserts an artifact exists, and is therefore corroborated. `killed`
#: is included ON PURPOSE: it is what closes the mass-graveyard escape hatch.
_CLAIMS_ARTIFACT = _TERMINAL

#: Value weights. A Tier-1 defect-closer stops ongoing bleed and is worth many operators.
TIER_WEIGHT: Mapping[int, int] = {1: 8, 2: 4, 3: 2, 4: 1}

_T1 = ("ground truth", "ground-truth", "diff-verify", "diff verify", "fence", "unblock",
       "blocker", "vendor-replacement", "defect", "backfill")
_T4 = ("operator", "lexicon", "diaspora", "search key", "query", "printpage", "tree-walk")
_T2 = ("prior", "mechanism", "premium", "carry", "funding", "basis", "regime")


def infer_tier(name: str, *, ingested_axes: Sequence[str] = ()) -> int:
    """Best-effort conversion tier (1 = highest ROI). An explicit ``tier:N`` tag always wins.

    Heuristic and deliberately coarse -- its job is to stop a Tier-1 defect-closer being buried
    under cheap Tier-4 wins, not to be a taxonomy. TIER 1 defect-closers (make a permanently-firing
    gate satisfiable) outrank everything because they stop ongoing bleed rather than adding
    capability; TIER 2 is a mechanism prior on an axis ALREADY ingested (pure §31 work on data
    already paid for); TIER 3 a new surface; TIER 4 operators/lexicons/diaspora.
    """
    n = name.lower()
    if any(k in n for k in _T1):
        return 1
    if any(a.lower() in n for a in ingested_axes if a) or any(k in n for k in _T2):
        return 2
    if any(k in n for k in _T4):
        return 4
    return 3


class MinedItem(BaseModel):
    """One carded find plus whatever disposition was written against it."""

    model_config = ConfigDict(frozen=True)

    source: str
    name: str
    disposition: str = ""  # "" = none written == UNDISPOSED (silence is a defect)
    deferred_until: str = ""
    illegal_reason: str = ""
    tier: int = 3
    artifact: str = ""   # explicit repo-relative path from ``-> path`` -- exact, not fuzzy

    @property
    def weight(self) -> int:
        return TIER_WEIGHT.get(self.tier, 1)


def parse_dispositions(
    text: str, *, source: str, ingested_axes: Sequence[str] = ()
) -> list[MinedItem]:
    """Extract every carded find in ``text`` and the disposition written on its own line."""
    items: list[MinedItem] = []
    for line in text.splitlines():
        m = _ITEM_RE.match(line)
        if not m:
            continue
        name = _DISP_RE.sub("", m.group("card")).strip(" -—:")
        d = _DISP_RE.search(line)
        tier = int(d.group("tier")) if (d and d.group("tier")) else infer_tier(
            name, ingested_axes=ingested_axes)
        if not d:
            items.append(MinedItem(source=source, name=name, tier=tier))
            continue
        verb, until = d.group("verb").lower(), (d.group("until") or "")
        art = (d.group("art") or "").strip()
        if verb not in LEGAL:
            items.append(MinedItem(source=source, name=name, tier=tier, artifact=art,
                                   illegal_reason=f"unknown disposition '{verb}'"))
        elif verb == "deferred" and not until:
            # the hiding place: an undated deferral is indistinguishable from abandonment
            items.append(MinedItem(source=source, name=name, tier=tier, artifact=art,
                                   illegal_reason="deferred with NO date"))
        else:
            items.append(MinedItem(source=source, name=name, tier=tier, artifact=art,
                                   disposition=verb, deferred_until=until))
    return items


def is_disposed(item: MinedItem, *, as_of: date) -> bool:
    """True when the item is genuinely finished, or deferred to a date that has NOT yet passed."""
    if item.illegal_reason or not item.disposition:
        return False
    if item.disposition in _TERMINAL:
        return True
    try:
        return date.fromisoformat(item.deferred_until) > as_of
    except ValueError:  # pragma: no cover -- regex already constrains the shape
        return False


def backlog(items: Iterable[MinedItem], *, as_of: date) -> tuple[MinedItem, ...]:
    """Every item still owing a disposition -- untagged, illegally tagged, or expired-deferred."""
    return tuple(i for i in items if not is_disposed(i, as_of=as_of))


def unbacked(
    items: Iterable[MinedItem],
    *,
    backing: Mapping[str, Sequence[str]],
    root: Path | None = None,
    first_seen: Mapping[str, float] | None = None,
) -> tuple[MinedItem, ...]:
    """Terminal claims that could not be corroborated by a real artifact.

    TWO MODES, and the strong one is preferred:

    EXACT (``[§33: wired -> data/upbit_1m.jsonl]``) -- the named path must EXIST and be NON-EMPTY.
    Authoritative: a rename, a deletion, or an empty stub file all fail loudly. This is the mode
    the desk should converge on, because it names the evidence instead of hinting at it.

    FUZZY (no path given) -- substring match in both directions against ``backing`` (wired/screened
    from collector output and research memory; killed from the graveyard). Kept only for backward
    compatibility with cards written before the arrow syntax: a card name and its artifact rarely
    agree character for character ("Tardis" vs "tardis_l2_backfill"). It is genuinely weaker -- a
    rename silently breaks credit and a coincidental substring silently grants it -- so the report
    counts how many claims still rely on it, making the drift toward EXACT visible and pressurable.
    """
    base = root or Path()
    out = []
    for i in items:
        if i.disposition not in _CLAIMS_ARTIFACT:
            continue
        if i.artifact:
            p = base / i.artifact
            try:
                ok = p.is_file() and p.stat().st_size > 0
                # ...and it must POSTDATE the find. Exact was not enough: `-> pyproject.toml`
                # named a real non-empty file and was credited, so any pre-existing file in the
                # repo was a valid receipt for any claim. A file that has not been touched since
                # before the discovery cannot be evidence OF that discovery. Doing the actual
                # work satisfies this for free -- including a graveyard entry, which touches
                # graveyard.md. Skipped when the find has no ledger history yet.
                if ok and first_seen and i.name in first_seen:
                    ok = p.stat().st_mtime > first_seen[i.name]
                if ok:
                    continue
            except OSError:
                pass
            out.append(i)
            continue
        n = i.name.lower()
        cands = [b.lower() for b in backing.get(i.disposition, ()) if b]
        if not any(b in n or n in b for b in cands):
            out.append(i)
    return tuple(out)


def fuzzy_credited(items: Iterable[MinedItem]) -> tuple[MinedItem, ...]:
    """Terminal claims relying on NAME MATCHING rather than a named artifact path.

    Not a defect on its own -- it is the weaker evidence standard, and measuring it is how the
    desk ratchets from "roughly corroborated" to "this exact file, non-empty, or it did not
    happen" without a flag day.
    """
    return tuple(i for i in items if i.disposition in _CLAIMS_ARTIFACT and not i.artifact)


class ConversionReport(BaseModel):
    """The §33 cycle block -- filled from artifacts, never from a narrative."""

    model_config = ConfigDict(frozen=True)

    n_items: int
    n_wired: int
    n_screened: int
    n_killed: int
    n_deferred: int
    n_backlog: int
    n_illegal: int
    n_unbacked: int
    n_fuzzy_credited: int
    weighted_backlog: int
    top_tier_owing: int          # 1..4; 0 when nothing is owed
    kill_share: float            # killed / terminal -- a spike means the escape hatch is in use
    priority_inversion: bool     # a Tier-1/2 item owes while cheaper tiers were converted
    backlog_names: tuple[str, ...]
    illegal_names: tuple[str, ...]
    unbacked_names: tuple[str, ...]
    suspend_mining: bool
    verdict: str


#: Above this share of terminal dispositions being `killed`, the backlog is being cleared by
#: graveyard rather than by conversion. Not proof of gaming -- a genuinely bad batch happens --
#: but it is the signature, and it must be looked at rather than pass silently.
KILL_SHARE_BAR = 0.60


def conversion_report(
    items: Sequence[MinedItem],
    *,
    as_of: date,
    backing: Mapping[str, Sequence[str]] | None = None,
    root: Path | None = None,
    first_seen: Mapping[str, float] | None = None,
    max_shown: int = 8,
) -> ConversionReport:
    """Build the §33 report and decide whether mining is SUSPENDED this cycle.

    Suspension is flow control, not punishment: an organ producing faster than the desk converts
    is not producing value, it is producing debt. Mining resumes the instant the backlog clears.
    An UNBACKED claim suspends too -- otherwise the cheapest way to clear a backlog is to type the
    word "wired", which would make the whole law self-defeating.
    """
    backing = backing or {}
    bl = backlog(items, as_of=as_of)
    illegal = tuple(i for i in items if i.illegal_reason)
    ub = unbacked(items, backing=backing, root=root, first_seen=first_seen)
    fuzzy = fuzzy_credited(items)
    counts = {v: sum(1 for i in items if i.disposition == v and is_disposed(i, as_of=as_of))
              for v in LEGAL}
    # An EXPIRED deferral is backlog, not a deferral -- counting it in both places would let a
    # rotting item read as handled at a glance, the exact failure this law exists to stop.
    n_terminal = sum(counts[v] for v in _TERMINAL)
    kill_share = (counts["killed"] / n_terminal) if n_terminal else 0.0
    weighted = sum(i.weight for i in bl)
    top_tier = min((i.tier for i in bl), default=0)
    # Priority inversion: something expensive still owes while cheaper work was finished. This is
    # the enforceable form of "work the backlog highest-ROI first" -- the doctrine states the
    # order, and without this the order is unenforced prose.
    converted_tiers = [i.tier for i in items if is_disposed(i, as_of=as_of)
                       and i.disposition in _TERMINAL]
    inversion = bool(bl) and top_tier <= 2 and any(t > top_tier for t in converted_tiers)
    suspend = bool(bl) or bool(ub)

    if not items:
        verdict = "no carded finds parsed -- nothing owed"
    elif suspend:
        verdict = (
            f"CONVERSION FIRST -- {len(bl)} item(s) owe a disposition (weighted {weighted}, "
            f"highest tier owing T{top_tier or '-'}), {len(ub)} claim conversion with NO backing "
            "artifact. Spend this run's FIRST effort disposing of them, highest tier first "
            "(wired/screened/killed-with-mechanism/deferred-with-a-date), THEN CONTINUE MINING "
            "AND EXHAUSTING NEW GROUND IN THIS SAME RUN. Mining is never throttled, paused, or "
            "reduced -- acquisition keeps growing while extraction scales up to meet it."
        )
    else:
        verdict = f"backlog clear -- all {len(items)} carded find(s) disposed; mining authorised"

    return ConversionReport(
        n_items=len(items),
        n_wired=counts["wired"], n_screened=counts["screened"],
        n_killed=counts["killed"], n_deferred=counts["deferred"],
        n_backlog=len(bl), n_illegal=len(illegal), n_unbacked=len(ub),
        n_fuzzy_credited=len(fuzzy),
        weighted_backlog=weighted, top_tier_owing=top_tier,
        kill_share=round(kill_share, 3), priority_inversion=inversion,
        backlog_names=tuple(f"T{i.tier} {i.name}" for i in bl[:max_shown]),
        illegal_names=tuple(f"{i.name} ({i.illegal_reason})" for i in illegal[:max_shown]),
        unbacked_names=tuple(f"{i.name} [{i.disposition}]" for i in ub[:max_shown]),
        suspend_mining=suspend, verdict=verdict,
    )


# --------------------------------------------------------------------------------------------
# FLOW + FEEDBACK -- a stock check says whether inventory exists; only a flow check says whether
# the desk is getting FASTER. And conversion outcomes are worthless if they dead-end in an audit
# report: fed back as per-class priors, they steer what gets mined next.
# --------------------------------------------------------------------------------------------

def append_snapshot(path: Path, items: Sequence[MinedItem], *, now: datetime | None = None) -> None:
    """Append one line recording every item's disposition as of now (jsonl, one line per run).

    First-seen and converted-at are DERIVED from consecutive snapshots rather than demanded from
    the miners: a timestamp a human has to remember to write is a timestamp that goes missing.
    """
    ts = (now or datetime.now(UTC)).timestamp()
    row = {"ts": ts, "items": [{"n": i.name, "s": i.source, "d": i.disposition, "t": i.tier}
                               for i in items]}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_ledger(path: Path) -> list[dict[str, Any]]:
    """Read the snapshot ledger, skipping any corrupt line rather than losing the whole history."""
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text("utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(r, dict) and "ts" in r and isinstance(r.get("items"), list):
            rows.append(r)
    return sorted(rows, key=lambda r: float(r["ts"]))


class FlowStats(BaseModel):
    """Conversion THROUGHPUT -- the stock check cannot tell 30-day conversion from 2-day."""

    model_config = ConfigDict(frozen=True)

    n_snapshots: int
    median_latency_days: float   # find -> terminal disposition; -1 when nothing has converted yet
    p90_latency_days: float
    oldest_owing_days: float
    oldest_owing_name: str
    n_converted: int
    latency_worsening: bool      # recent half slower than the earlier half


def flow_stats(
    ledger: Sequence[LedgerRow], *, now: datetime | None = None
) -> FlowStats:
    """Derive find->conversion latency and the age of the oldest still-owing item."""
    ts_now = (now or datetime.now(UTC)).timestamp()
    first_seen: dict[str, float] = {}
    converted_at: dict[str, float] = {}
    for row in ledger:
        ts = float(row["ts"])
        for it in row["items"]:
            name = str(it.get("n", ""))
            if not name:
                continue
            first_seen.setdefault(name, ts)
            if it.get("d") in _TERMINAL and name not in converted_at:
                converted_at[name] = ts
    lat = sorted((converted_at[n] - first_seen[n]) / 86400.0 for n in converted_at)
    owing = {n: t for n, t in first_seen.items() if n not in converted_at}
    oldest_name, oldest_days = "", 0.0
    if owing:
        oldest_name = min(owing, key=lambda n: owing[n])
        oldest_days = (ts_now - owing[oldest_name]) / 86400.0
    worsening = False
    if len(lat) >= 6:
        # ordered by latency, not time -- compare the halves of the CHRONOLOGICAL series instead
        chrono = [(converted_at[n], (converted_at[n] - first_seen[n]) / 86400.0)
                  for n in converted_at]
        chrono.sort()
        half = len(chrono) // 2
        early = statistics.median(v for _, v in chrono[:half])
        late = statistics.median(v for _, v in chrono[half:])
        worsening = late > early * 1.5
    return FlowStats(
        n_snapshots=len(ledger),
        median_latency_days=round(statistics.median(lat), 2) if lat else -1.0,
        p90_latency_days=round(lat[int(len(lat) * 0.9)], 2) if lat else -1.0,
        oldest_owing_days=round(oldest_days, 2), oldest_owing_name=oldest_name,
        n_converted=len(lat), latency_worsening=worsening,
    )


class ClassPrior(BaseModel):
    """What a SOURCE CLASS has historically been worth -- the signal that steers generation."""

    model_config = ConfigDict(frozen=True)

    source: str
    n_seen: int
    n_converted: int
    conversion_rate: float
    median_latency_days: float


def class_priors(
    ledger: Sequence[LedgerRow], *, min_seen: int = 3
) -> tuple[ClassPrior, ...]:
    """Per-source conversion rate and latency -- the closed loop back into what to mine next.

    Conversion data that dead-ends in an audit report is a fence. Fed back as priors, it becomes a
    control system: a source class converting at 60% earns more of the next cycle than one
    converting at 5%, WITHOUT anyone deciding that by hand. Classes below ``min_seen`` are omitted
    rather than shown at a noisy 0/1 rate -- a thin prior that reweights generation is worse than
    no prior at all.
    """
    seen: dict[str, dict[str, float]] = {}
    first: dict[str, float] = {}
    conv: dict[str, float] = {}
    src_of: dict[str, str] = {}
    for row in ledger:
        ts = float(row["ts"])
        for it in row["items"]:
            name, src = str(it.get("n", "")), str(it.get("s", "?"))
            if not name:
                continue
            src_of.setdefault(name, src)
            first.setdefault(name, ts)
            if it.get("d") in _TERMINAL and name not in conv:
                conv[name] = ts
    for name, src in src_of.items():
        b = seen.setdefault(src, {"n": 0.0, "c": 0.0})
        b["n"] += 1
        if name in conv:
            b["c"] += 1
    out = []
    for src, b in sorted(seen.items()):
        if b["n"] < min_seen:
            continue
        lat = sorted((conv[n] - first[n]) / 86400.0 for n, s in src_of.items()
                     if s == src and n in conv)
        out.append(ClassPrior(
            source=src, n_seen=int(b["n"]), n_converted=int(b["c"]),
            conversion_rate=round(b["c"] / b["n"], 3),
            median_latency_days=round(statistics.median(lat), 2) if lat else -1.0,
        ))
    return tuple(sorted(out, key=lambda p: -p.conversion_rate))


def priors_payload(
    priors: Sequence[ClassPrior], *, now: datetime | None = None
) -> dict[str, Any]:
    """The artifact the diggers read: where the next cycle's effort is worth most, and least."""
    ts = (now or datetime.now(UTC))
    ranked = list(priors)
    return {
        "generated_at": ts.isoformat(),
        "law": "§33.4 -- generation is reweighted BY measured conversion, not by enthusiasm",
        "favour": [p.source for p in ranked[:3]],
        "starve": [p.source for p in ranked[-3:] if p.conversion_rate < 0.25],
        "classes": [p.model_dump() for p in ranked],
    }


# --------------------------------------------------------------------------------------------
# SELF-IMPROVEMENT -- the ratchet. Layers 1-4 make conversion visible, priced, and fed back; none
# of them makes it get BETTER. A standard that never moves is a standard the desk grows into and
# then stops at, which is the no-ceiling axiom's exact failure mode. So the bar is the desk's OWN
# BEST-EVER performance: every record tightens it permanently, and it never loosens. There is no
# "good enough" state -- only "better than the best we have ever done", or a regression defect.
# --------------------------------------------------------------------------------------------

class Ratchet(BaseModel):
    """Best-ever conversion performance. Monotone by construction -- records only ever improve."""

    model_config = ConfigDict(frozen=True)

    best_median_latency_days: float = -1.0   # -1 = no record yet
    best_conversion_rate: float = 0.0
    best_at: str = ""
    n_records: int = 0
    #: Ledger high-water marks. Snapshot count only grows and the earliest ts only moves back;
    #: either going the wrong way proves the evidence base was truncated or rewritten.
    n_snapshots: int = 0
    earliest_ts: float = 0.0


class RatchetVerdict(BaseModel):
    """Whether this cycle set a record, held, or REGRESSED against the desk's own best."""

    model_config = ConfigDict(frozen=True)

    improved: bool
    regressed: bool
    latency_vs_best: float   # multiple of best-ever median latency; -1 when no record yet
    rate_vs_best: float      # current conversion rate minus best-ever
    next_bar_days: float     # the tightened bar the NEXT cycle must beat
    verdict: str


def load_ratchet(path: Path) -> Ratchet:
    """Read the ratchet, degrading to a fresh one rather than losing the check on a corrupt file."""
    try:
        return Ratchet.model_validate_json(path.read_text("utf-8"))
    except Exception:
        return Ratchet()


def update_ratchet(
    ratchet: Ratchet,
    flow: FlowStats,
    *,
    conversion_rate: float,
    regress_mult: float = 1.5,
    ledger: Sequence[LedgerRow] = (),
    now: datetime | None = None,
) -> tuple[Ratchet, RatchetVerdict]:
    """Compare this cycle to the best ever, tighten on a record, and flag regression.

    ONE-WAY: a worse cycle never relaxes the bar -- it produces a defect instead. That asymmetry is
    the whole point. Latency improvements and rate improvements both count, so the desk can advance
    by converting FASTER or by converting MORE, and it is never allowed to trade one away for the
    other silently (both are held against their own records).
    """
    ts = (now or datetime.now(UTC)).isoformat()
    cur_lat, best_lat = flow.median_latency_days, ratchet.best_median_latency_days
    have_lat = cur_lat >= 0.0
    lat_record = have_lat and (best_lat < 0.0 or cur_lat < best_lat)
    rate_record = conversion_rate > ratchet.best_conversion_rate
    improved = bool(lat_record or rate_record)

    lat_vs = (cur_lat / best_lat) if (have_lat and best_lat > 0.0) else -1.0
    # A regression is measured against the RECORD, never against last cycle -- otherwise a slow
    # drift downhill reads as "fine" at every single step.
    regressed = bool(have_lat and best_lat > 0.0 and cur_lat > best_lat * regress_mult)

    new = Ratchet(
        best_median_latency_days=(cur_lat if lat_record else best_lat),
        best_conversion_rate=(conversion_rate if rate_record else ratchet.best_conversion_rate),
        best_at=(ts if improved else ratchet.best_at),
        n_records=ratchet.n_records + (1 if improved else 0),
        # high-water marks only ever ratchet the safe way, so a shrunken ledger stays detectable
        n_snapshots=max(ratchet.n_snapshots, len(ledger)),
        earliest_ts=(min(float(r["ts"]) for r in ledger)
                     if ledger and not ratchet.earliest_ts
                     else ratchet.earliest_ts),
    )
    # the bar the next cycle must beat: the (possibly new) record, tightened by the tolerance
    next_bar = (new.best_median_latency_days * regress_mult
                if new.best_median_latency_days > 0.0 else -1.0)

    if improved:
        bits = []
        if lat_record:
            bits.append(f"latency {cur_lat:.1f}d (prev best {best_lat:.1f}d)")
        if rate_record:
            prev = ratchet.best_conversion_rate
            bits.append(f"rate {conversion_rate:.0%} (prev best {prev:.0%})")
        verdict = "RECORD -- " + "; ".join(bits) + ". Bar tightened; it never loosens."
    elif regressed:
        verdict = (f"REGRESSION -- median latency {cur_lat:.1f}d vs best-ever {best_lat:.1f}d "
                   f"({lat_vs:.1f}x). The desk has been faster than this and must be again.")
    else:
        verdict = (f"held -- {cur_lat:.1f}d vs best {best_lat:.1f}d. Holding is not improving: "
                   "the standing bar is the desk's own record, and it only moves down.")
    return new, RatchetVerdict(
        improved=improved, regressed=regressed,
        latency_vs_best=round(lat_vs, 2),
        rate_vs_best=round(conversion_rate - ratchet.best_conversion_rate, 3),
        next_bar_days=round(next_bar, 2), verdict=verdict,
    )


def feedback_applied(
    ledger: Sequence[LedgerRow], priors: Sequence[ClassPrior], *, lookback: int = 2
) -> tuple[bool, str]:
    """Did generation ACTUALLY reweight toward the high-converting classes, or just get told to?

    The loop is only closed if the advice changes behaviour. Compares which source classes NEW
    items arrived in over the last ``lookback`` snapshots against the priors' favour/starve lists.
    A recommendation nothing acts on is the same failure as a law with no monitor -- so the
    feedback step is itself verified rather than assumed.
    """
    if len(ledger) < lookback + 1 or not priors:
        return True, "insufficient history to judge feedback -- not a defect yet"
    starve = {p.source for p in priors if p.conversion_rate < 0.25}
    if not starve:
        return True, "no starved class -- nothing to reweight away from"
    older = {str(i.get("n", "")) for row in ledger[:-lookback] for i in row["items"]}
    fresh: dict[str, int] = {}
    for row in ledger[-lookback:]:
        for i in row["items"]:
            n = str(i.get("n", ""))
            if n and n not in older:
                fresh[str(i.get("s", "?"))] = fresh.get(str(i.get("s", "?")), 0) + 1
    if not fresh:
        return True, "no new finds in the window -- nothing to judge"
    bad = sum(v for k, v in fresh.items() if k in starve)
    share = bad / sum(fresh.values())
    if share > 0.5:
        return False, (f"{share:.0%} of new finds came from classes measured below a 25% "
                       f"conversion rate ({', '.join(sorted(starve))}) -- the priors were "
                       "published and IGNORED. Generation must follow measured conversion.")
    return True, f"new finds skew away from starved classes ({share:.0%} from them)"


# --------------------------------------------------------------------------------------------
# TAMPER-RESISTANCE -- the lesson of the gate file, generalised. Every remaining bypass in §33 was
# the same shape: state that could be DELETED or FORGED. A card can be deleted from the doc; an
# artifact path can point at a file that has been there for months; the ratchet's "never loosens"
# guarantee lived in a gitignored file one `rm` deep. Enforcement is only as strong as its weakest
# erasable surface, so each of these is closed the same way -- derive it, or put it where deleting
# it is VISIBLE.
# --------------------------------------------------------------------------------------------

def first_seen_map(ledger: Sequence[LedgerRow]) -> dict[str, float]:
    """Earliest snapshot timestamp per item name -- when the desk first knew about the find."""
    out: dict[str, float] = {}
    for row in ledger:
        ts = float(row["ts"])
        for it in row["items"]:
            n = str(it.get("n", ""))
            if n:
                out.setdefault(n, ts)
    return out


def vanished(
    current: Sequence[MinedItem], ledger: Sequence[LedgerRow], *, as_of: date
) -> tuple[str, ...]:
    """Finds that were owed a disposition in the last snapshot and have since DISAPPEARED.

    Deleting the card must not delete the obligation. Without this, the cheapest way to clear the
    backlog is an editor: remove the line, and the item stops being counted entirely. The ledger
    remembers, so a name that was undisposed yesterday and is absent today is an erasure, reported
    immediately and by name rather than surfacing weeks later as a confusing rot warning about an
    item nobody can find.
    """
    if not ledger:
        return ()
    prev = ledger[-1]
    was_owing = {str(i.get("n", "")) for i in prev["items"]
                 if i.get("d") not in _TERMINAL and str(i.get("n", ""))}
    now_present = {i.name for i in current}
    # a terminal disposition in THIS pass is a legitimate exit, not an erasure
    now_done = {i.name for i in current if is_disposed(i, as_of=as_of)}
    return tuple(sorted(was_owing - now_present - now_done))


def ledger_regressed(ratchet: Ratchet, ledger: Sequence[LedgerRow]) -> tuple[bool, str]:
    """Has the snapshot history been truncated or rewritten since the last recorded state?

    The ledger is the evidence base for latency, priors and the ratchet itself; erasing it resets
    every one of them. Snapshot count only ever grows and the earliest timestamp only ever moves
    BACKWARD (never forward), so either statistic going the wrong way is proof of tampering or of
    data loss -- both of which invalidate the record and must be seen, not silently absorbed.
    """
    if not ratchet.n_snapshots:
        return False, "no prior record -- nothing to compare"
    n = len(ledger)
    earliest = min((float(r["ts"]) for r in ledger), default=0.0)
    if n < ratchet.n_snapshots:
        return True, (f"snapshot count fell {ratchet.n_snapshots} -> {n}: the conversion ledger "
                      "has been truncated or deleted")
    if ratchet.earliest_ts and earliest > ratchet.earliest_ts + 1.0:
        return True, ("the ledger's earliest snapshot moved forward in time: history was "
                      "rewritten, not appended")
    return False, "ledger intact"


# --------------------------------------------------------------------------------------------
# THE LAW HELD TO ITS OWN STANDARD. Everything above pressures the DESK. Nothing above asks
# whether §33's own machinery is any good -- and a law exempt from the evidence standard it
# enforces is exactly the hypocrisy the NO-CEILING AXIOM forbids ("we are at max" is a claim
# requiring evidence, never a default). Two self-audits close that: the tier weights must be
# shown to track reality, and the law must be shown to have improved conversion at all.
# --------------------------------------------------------------------------------------------

class TierCalibration(BaseModel):
    """Measured behaviour per tier -- are the weights tracking reality or just asserted?"""

    model_config = ConfigDict(frozen=True)

    per_tier: Mapping[int, tuple[int, float, float]]  # tier -> (n, conversion_rate, median_days)
    inverted: bool
    verdict: str


def tier_calibration(
    ledger: Sequence[LedgerRow], *, min_per_tier: int = 4
) -> TierCalibration:
    """Check the TIER WEIGHTS against measured outcomes instead of trusting the heuristic.

    The weighting (T1=8 .. T4=1) is an ASSERTION: it claims Tier-1 finds are the high-ROI ones.
    If in practice Tier-1 items convert less often and slower than Tier-4 items, the weights are
    not merely useless -- they are actively misdirecting effort toward the wrong work while
    reporting that priority is being enforced. This does not silently re-learn the mapping (a
    keyword heuristic quietly rewritten by its own outcomes is unauditable); it DETECTS that the
    mapping is wrong and demands the tiering be corrected, which is the honest version of learning
    when the sample is this thin.
    """
    first: dict[str, float] = {}
    conv: dict[str, float] = {}
    tier_of: dict[str, int] = {}
    for row in ledger:
        ts = float(row["ts"])
        for it in row["items"]:
            n = str(it.get("n", ""))
            if not n:
                continue
            first.setdefault(n, ts)
            tier_of.setdefault(n, int(it.get("t", 3) or 3))
            if it.get("d") in _TERMINAL and n not in conv:
                conv[n] = ts
    per: dict[int, tuple[int, float, float]] = {}
    for tier in (1, 2, 3, 4):
        names = [n for n, t in tier_of.items() if t == tier]
        if not names:
            continue
        done = [n for n in names if n in conv]
        lat = sorted((conv[n] - first[n]) / 86400.0 for n in done)
        per[tier] = (len(names), round(len(done) / len(names), 3),
                     round(statistics.median(lat), 2) if lat else -1.0)

    hi, lo = per.get(1), per.get(4)
    enough = bool(hi and lo and hi[0] >= min_per_tier and lo[0] >= min_per_tier)
    inverted = bool(enough and hi and lo and hi[1] < lo[1])
    if not enough:
        verdict = "insufficient per-tier history to judge the weights -- not a defect yet"
    elif inverted and hi and lo:
        verdict = (f"tier weights INVERTED: T1 converts at {hi[1]:.0%} vs T4 at {lo[1]:.0%}. The "
                   "weighting is steering effort toward work that does not finish.")
    else:
        verdict = "tier weights track measured outcomes"
    return TierCalibration(per_tier=per, inverted=inverted, verdict=verdict)


class LawEffectiveness(BaseModel):
    """Has §33 actually improved conversion, or is it ceremony with good telemetry?"""

    model_config = ConfigDict(frozen=True)

    n_snapshots: int
    early_rate: float
    late_rate: float
    early_latency_days: float
    late_latency_days: float
    improving: bool
    conclusive: bool
    verdict: str


def law_effectiveness(
    ledger: Sequence[LedgerRow], *, min_snapshots: int = 12
) -> LawEffectiveness:
    """Compare the FIRST third of the ledger against the LAST third: is conversion getting better?

    HONEST LIMIT, stated rather than buried: there is no control group and no pre-§33 baseline
    (the ledger begins with the law), so this is a TREND, not a counterfactual -- it cannot prove
    §33 caused an improvement, only that one did or did not happen while §33 was in force. That is
    still the strongest evidence available, and it is strictly better than the alternative the desk
    would otherwise use, which is assuming the law works because it was written carefully. If
    conversion is flat or worse after enough cycles, §33 is ceremony with good telemetry and must
    say so about itself in those words.
    """
    n = len(ledger)
    if n < min_snapshots:
        return LawEffectiveness(
            n_snapshots=n, early_rate=0.0, late_rate=0.0, early_latency_days=-1.0,
            late_latency_days=-1.0, improving=False, conclusive=False,
            verdict=f"{n}/{min_snapshots} snapshots -- too early to judge the law itself")
    third = max(1, n // 3)

    def _window(rows: Sequence[LedgerRow]) -> tuple[float, float]:
        first: dict[str, float] = {}
        conv: dict[str, float] = {}
        for row in rows:
            ts = float(row["ts"])
            for it in row["items"]:
                nm = str(it.get("n", ""))
                if not nm:
                    continue
                first.setdefault(nm, ts)
                if it.get("d") in _TERMINAL and nm not in conv:
                    conv[nm] = ts
        rate = (len(conv) / len(first)) if first else 0.0
        lat = sorted((conv[k] - first[k]) / 86400.0 for k in conv)
        return round(rate, 3), (round(statistics.median(lat), 2) if lat else -1.0)

    e_rate, e_lat = _window(ledger[:third])
    l_rate, l_lat = _window(ledger[-third:])
    faster = l_lat >= 0 and e_lat >= 0 and l_lat < e_lat
    improving = bool(l_rate > e_rate or faster)
    verdict = (
        f"conversion rate {e_rate:.0%} -> {l_rate:.0%}, median latency {e_lat:.1f}d -> {l_lat:.1f}d"
        + (" -- the law is working" if improving else
           " -- NO improvement while §33 has been in force. It is ceremony with good telemetry: "
           "either the enforcement is not biting or the bottleneck is elsewhere. Find out which.")
    )
    return LawEffectiveness(
        n_snapshots=n, early_rate=e_rate, late_rate=l_rate,
        early_latency_days=e_lat, late_latency_days=l_lat,
        improving=improving, conclusive=True, verdict=verdict)

```

### libs/self_improvement/audit.py
```python
"""Improvement audit — every Stage 13 action to the existing immutable audit log.

Reuses ``libs.store.AuditLog`` (append-only, hash-chained). No parallel storage is created.
"""

from __future__ import annotations

from libs.self_improvement.models import ImprovementAction, ImprovementPlan
from libs.store.audit import AuditLog
from libs.store.connection import Database
from libs.store.models import AuditEntry

_ACTOR = "stage13_self_improvement"


class ImprovementAudit:
    """Writes Stage 13 recommendations to the immutable audit log."""

    def __init__(self, db: Database) -> None:
        self._audit = AuditLog(db)

    def record(self, action: ImprovementAction) -> AuditEntry:
        return self._audit.append(
            f"improvement_{action.type.value}",
            actor=_ACTOR,
            inputs={
                "target_id": action.target_id,
                "requires_portfolio_approval": action.requires_portfolio_approval,
                **action.detail,
            },
            rationale=action.rationale,
            outcome="recommended",
        )

    def record_plan(self, plan: ImprovementPlan) -> list[AuditEntry]:
        return [self.record(action) for action in plan.actions]

```

### libs/self_improvement/decay_engine.py
```python
"""Alpha decay detection (reuses ``libs.alpha.detect_decay``; adds PF/Sharpe decay levels).

Decay levels and their recommended (recommend-only) actions follow the Stage 13 spec. Stage 13
never applies these directly — capital reductions require Portfolio Engine approval; retirement
is applied via the existing AlphaLifecycleManager.
"""

from __future__ import annotations

from libs.alpha.card import AlphaCard, ExpectedMetrics, LiveMetrics
from libs.alpha.decay import detect_decay
from libs.self_improvement.models import DecayAssessment, DecayLevel

# decay level -> (recommended_action, weight_multiplier, allow_increase)
_ACTIONS: dict[DecayLevel, tuple[str, float, bool]] = {
    DecayLevel.HEALTHY: ("no_action", 1.0, True),
    DecayLevel.WATCH: ("reduce_weight_10pct", 0.90, True),
    DecayLevel.WEAK: ("reduce_weight_25pct", 0.75, True),
    DecayLevel.DECAYING: ("pause_capital_increases", 1.0, False),
    DecayLevel.DEAD: ("retire", 0.0, False),
}


def classify_decay(*, profit_factor: float | None, sharpe: float) -> DecayLevel:
    """Map profit factor (with a Sharpe proxy/confirmation) to a decay level."""
    pf = profit_factor
    if pf is None:
        pf = 1.5 if sharpe >= 1.5 else (1.0 if sharpe >= 0 else 0.7)
    if pf < 0.8:
        return DecayLevel.DEAD
    if pf < 1.0:
        return DecayLevel.DECAYING
    if pf < 1.2:
        return DecayLevel.WEAK
    if pf < 1.5:
        return DecayLevel.WATCH
    return DecayLevel.HEALTHY if sharpe > 1.5 else DecayLevel.WATCH


class AlphaDecayEngine:
    """Assesses decay and recommends an action (no action is applied here)."""

    def assess(self, card: AlphaCard, live: LiveMetrics) -> DecayAssessment:
        level = classify_decay(profit_factor=live.profit_factor, sharpe=live.sharpe)
        decay = detect_decay(ExpectedMetrics.from_card(card), live)
        action, multiplier, allow_increase = _ACTIONS[level]
        return DecayAssessment(
            alpha_id=card.id,
            decay_level=level,
            decay_score=decay.decay_score,
            recommended_action=action,
            weight_multiplier=multiplier,
            allow_increase=allow_increase,
        )

```

### libs/self_improvement/dormancy.py
```python
"""DORMANCY HUNTER -- the standing version of the discovery that reframed 2026-07-30.

WHY THIS EXISTS. On 2026-07-30 the desk's named "highest-ROI MISSING subsystems" -- research
meta-learning, capital-allocation learning, agent health monitoring, information-advantage
measurement, an alpha-decay lab, experiment ERV ranking -- turned out to be BUILT ALREADY with
ZERO CALLERS. That was found because someone happened to grep for callers. Depending on a human
noticing is not a mechanism, and the class of failure is large enough to deserve one: a capability
that exists and never executes is indistinguishable, from the outside, from a capability that was
never built -- except that the desk has already paid for it.

THE PRIORITY THIS ENCODES (principal, 2026-07-30): **find unused capability before inventing new
capability.** So this module answers, mechanically and every cycle, the question that produced the
find: *which modules does nothing import, and which scripts does nothing schedule?*

REACHABILITY, not popularity. A module is DORMANT only if NOTHING outside its own package imports
it AND nothing schedules it. That is deliberately strict in one direction and forgiving in the
other: a library imported by one live caller is reachable and therefore not dormant, however small
it is. The desk does not want to churn small components -- it wants to find the ones that are
disconnected.

WHAT IT DOES NOT DO: it never deletes, retires, or edits anything. It reports, with the exact
proving command, and the disposition (activate / merge / retire) stays a decision made under the
L2.9 exits with a written reason. An auto-retiring sweep would eventually delete a capability that
was dormant only because its unlock condition had not arrived yet -- which is precisely the state
several of these are legitimately in (0 validated alphas).

Pure stdlib. import from libs.self_improvement.dormancy.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

# Packages whose modules are expected to be imported from outside; a module here with no external
# importer is a genuine reachability finding rather than a naming artifact.
_LIB_SCOPE = ("libs/self_improvement", "libs/alpha", "libs/signal_engine", "libs/portfolio",
              "libs/discovery", "libs/autodiscovery", "libs/features", "libs/store",
              "libs/monitoring", "libs/research", "libs/validation", "libs/risk",
              "libs/execution", "libs/costs", "libs/regime", "libs/backtest")

# Scripts that are legitimately invoked by a human or another organ on demand rather than by a
# scheduler. Listed EXPLICITLY with a reason, because "it's a CLI tool" is otherwise the excuse
# that would let any dormant script escape the check.
_ON_DEMAND: dict[str, str] = {
    "scripts/research_memory.py": "CLI logger called ad hoc by every organ (doctrine duty)",
    "scripts/recommendations.py": "CLI ledger writer called by organs at disposition time",
    "scripts/track_findings.py": "CLI findings writer called by organs",
    "scripts/blind_spot.py": "CLI origin logger called by organs",
    "scripts/run_ci.py": "developer/commit gate, invoked by hand and by pre-push",
    "scripts/run_mutation.py": "measurement harness, invoked when a bar needs re-measuring",
    "scripts/check_scheduler_manifest.py": "invoked by deploy/reconstitute_cron.sh and by hand",
}


@dataclass
class Dormant:
    path: str
    kind: str                      # "module" | "script"
    reason: str
    proving_command: str
    lines: int = 0
    suggested_exit: str = "activate-or-record-unlock-condition"


@dataclass
class DormancyReport:
    dormant: list[Dormant] = field(default_factory=list)
    n_modules_scanned: int = 0
    n_scripts_scanned: int = 0

    @property
    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for d in self.dormant:
            out[d.kind] = out.get(d.kind, 0) + 1
        return out


def _grep(pattern: str, *paths: str) -> list[str]:
    """rg-free grep -rl; returns matching file paths (empty on no match)."""
    try:
        p = subprocess.run(["grep", "-rl", "-E", pattern, *paths],
                           cwd=_ROOT, capture_output=True, text=True, timeout=60, check=False)
    except (subprocess.TimeoutExpired, OSError):
        return []
    return [ln for ln in (p.stdout or "").splitlines() if ln.strip()]


def _external_importers(rel: str) -> list[str]:
    """Files OUTSIDE the module's own package that import it."""
    pkg = str(Path(rel).parent)
    mod = Path(rel).stem
    dotted = pkg.replace("/", ".") + "." + mod
    pattern = rf"(import\s+{re.escape(dotted)}|from\s+{re.escape(dotted)}\s+import|"
    pattern += rf"from\s+{re.escape(pkg.replace('/', '.'))}\s+import\s+[^\n]*\b{re.escape(mod)}\b)"
    hits = _grep(pattern, "scripts", "libs", "app", "api", "tests")
    # Its own package and its own tests do not make it reachable from the running desk.
    return [h for h in hits if not h.startswith(pkg) and not h.startswith("tests/")]


def _scheduled(rel: str) -> bool:
    name = Path(rel).name
    for src in ("ops/crontab.manifest", "scripts/run_cadence.py",
                "scripts/daily_research_cycle.py", "scripts/research_cycle.py"):
        p = _ROOT / src
        if p.exists() and name in p.read_text("utf-8", errors="ignore"):
            return True
    # A unit or shell runner that names it also counts as scheduling.
    return bool(_grep(re.escape(name), "ops"))


def _invoked_by_a_script(rel: str) -> bool:
    """Another script importing it or shelling out to it makes it reachable."""
    name = Path(rel).name
    stem = Path(rel).stem
    hits = _grep(rf"({re.escape(name)}|import\s+{re.escape(stem)}\b)", "scripts", "libs")
    return bool([h for h in hits if h != rel])


def scan(*, include_modules: bool = True, include_scripts: bool = True) -> DormancyReport:
    """Find capabilities nothing imports and nothing schedules."""
    rep = DormancyReport()
    if include_modules:
        for pkg in _LIB_SCOPE:
            d = _ROOT / pkg
            if not d.is_dir():
                continue
            for f in sorted(d.glob("*.py")):
                if f.name.startswith("_"):
                    continue
                rel = f"{pkg}/{f.name}"
                rep.n_modules_scanned += 1
                if _external_importers(rel):
                    continue
                rep.dormant.append(Dormant(
                    path=rel, kind="module",
                    reason="no module outside its own package imports it",
                    proving_command=(f"grep -rl '{pkg.replace('/', '.')}.{f.stem}' scripts/ libs/ "
                                     f"| grep -v {pkg}/"),
                    lines=len(f.read_text('utf-8', errors='ignore').splitlines())))
    if include_scripts:
        sd = _ROOT / "scripts"
        for f in sorted(sd.glob("*.py")):
            rel = f"scripts/{f.name}"
            rep.n_scripts_scanned += 1
            if rel in _ON_DEMAND or _scheduled(rel) or _invoked_by_a_script(rel):
                continue
            rep.dormant.append(Dormant(
                path=rel, kind="script",
                reason="nothing schedules it and no other script invokes or imports it",
                proving_command=(f"grep -c {f.name} ops/crontab.manifest scripts/run_cadence.py "
                                 f"scripts/daily_research_cycle.py"),
                lines=len(f.read_text('utf-8', errors='ignore').splitlines())))
    return rep


def summarise(rep: DormancyReport) -> dict[str, object]:
    """Report shape for the intelligence cycle. Biggest first -- a 500-line dormant subsystem is
    a larger paid-for-and-unused asset than a 20-line one."""
    ranked = sorted(rep.dormant, key=lambda d: -d.lines)
    return {
        "scanned": {"modules": rep.n_modules_scanned, "scripts": rep.n_scripts_scanned},
        "counts": rep.counts,
        "priority": "find unused capability BEFORE inventing new capability (principal 2026-07-30)",
        "exits": "activate / merge / retire -- never auto-deleted; several are legitimately "
                 "waiting on an unlock condition (e.g. 0 validated alphas) and that is a DATA gap",
        "dormant": [{"path": d.path, "kind": d.kind, "lines": d.lines, "reason": d.reason,
                     "proving_command": d.proving_command} for d in ranked[:40]],
        "total_dormant_lines": sum(d.lines for d in rep.dormant),
    }

```

### libs/signal_engine/governance.py
```python
"""Global governance gate — no capital without passing every validation test.

Mirrors the platform-wide rule: a signal may only become BUY/SELL if CPCV, DSR, PBO, Deflated
Sharpe, Reality Check, Capacity, Structural Break, and the live shadow period all pass. The gate
is fail-closed: every verdict defaults to ``False``, so anything unspecified blocks production.
Stage 13.5 consumes these verdicts (from the validation layer); it may not relax the thresholds.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from libs.signal_engine.errors import SignalGovernanceError


class GovernanceVerdict(BaseModel):
    """The eight validation verdicts that gate production capital (fail-closed defaults)."""

    model_config = ConfigDict(frozen=True)

    cpcv_pass: bool = False
    dsr_pass: bool = False
    pbo_pass: bool = False
    deflated_sharpe_pass: bool = False
    reality_check_pass: bool = False
    capacity_pass: bool = False
    structural_break_pass: bool = False
    shadow_period_complete: bool = False


def signal_governance_gate(verdict: GovernanceVerdict) -> bool:
    """True only if every validation gate passes."""
    return bool(
        verdict.cpcv_pass
        and verdict.dsr_pass
        and verdict.pbo_pass
        and verdict.deflated_sharpe_pass
        and verdict.reality_check_pass
        and verdict.capacity_pass
        and verdict.structural_break_pass
        and verdict.shadow_period_complete
    )


def require_governance(verdict: GovernanceVerdict) -> None:
    """Raise :class:`SignalGovernanceError` unless every gate passes."""
    if not signal_governance_gate(verdict):
        raise SignalGovernanceError("signal failed the mandatory validation gauntlet")

```

### libs/signal_engine/shadow.py
```python
"""Shadow deployment — evaluate a candidate signal live without risking capital.

Records the production vs shadow decision and (paper) return on each observation and reports
agreement, cumulative returns, and tracking error. It allocates **no capital** and never promotes;
readiness only signals that enough evidence exists for champion/challenger + walk-forward to judge.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict

from libs.signal_engine.models import Direction


class ShadowResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    variant_id: str
    n_decisions: int
    agreement_rate: float       # fraction where shadow == production direction
    production_return: float    # cumulative (paper)
    shadow_return: float        # cumulative (paper)
    tracking_error: float       # std of per-step return differences
    ready_for_promotion: bool   # enough evidence to evaluate (NOT a promotion itself)


class ShadowDeployment:
    """Accumulates shadow-vs-production observations; capital is never allocated."""

    def __init__(self, variant_id: str) -> None:
        self.variant_id = variant_id
        self._agreements: list[bool] = []
        self._prod_returns: list[float] = []
        self._shadow_returns: list[float] = []

    def observe(
        self,
        *,
        production_direction: Direction,
        shadow_direction: Direction,
        production_return: float,
        shadow_return: float,
    ) -> None:
        self._agreements.append(production_direction is shadow_direction)
        self._prod_returns.append(float(production_return))
        self._shadow_returns.append(float(shadow_return))

    def result(self, *, min_decisions: int = 100) -> ShadowResult:
        n = len(self._agreements)
        if n == 0:
            return ShadowResult(
                variant_id=self.variant_id, n_decisions=0, agreement_rate=0.0,
                production_return=0.0, shadow_return=0.0, tracking_error=0.0,
                ready_for_promotion=False,
            )
        prod = np.asarray(self._prod_returns, dtype="float64")
        shadow = np.asarray(self._shadow_returns, dtype="float64")
        tracking_error = float((shadow - prod).std(ddof=1)) if n > 1 else 0.0
        return ShadowResult(
            variant_id=self.variant_id,
            n_decisions=n,
            agreement_rate=float(np.mean(self._agreements)),
            production_return=float(prod.sum()),
            shadow_return=float(shadow.sum()),
            tracking_error=tracking_error,
            ready_for_promotion=n >= min_decisions,
        )

```

### libs/stage14/__init__.py
```python
"""``libs.stage14`` — institutional portfolio construction & compounding engine.

Transforms approved Stage 13.5 ``SignalPackage`` objects into capital allocations optimized for
long-term compounded wealth: geometric-growth and survival first, fractional-Kelly sizing, risk
budgeting at the sleeve level, dynamic leverage, a portfolio state machine, capacity ENFORCEMENT,
and fail-closed governance + portfolio kill criteria. Survival dominates return.

Reuses Architecture v1.0: ``libs.risk`` (Kelly/drawdown), ``libs.discovery`` (Monte-Carlo survival,
stress scenarios, log-growth), ``libs.validation`` (walk-forward governance), ``libs.portfolio``
(weight-construction substrate), and the immutable ``libs.store`` audit log. No duplicate
abstractions; the orchestrator is ``PortfolioConstructionEngine`` (distinct from
``libs.portfolio.PortfolioEngine``).
"""

from __future__ import annotations

from libs.stage14.allocation import (
    AdaptiveReinvestmentEngine,
    DrawdownAwareAllocator,
    DynamicLeverageEngine,
    PortfolioRiskBudgetEngine,
    SleeveAllocator,
    group_by_sleeve,
)
from libs.stage14.analytics import (
    CapitalEfficiencyEngine,
    MarginalContributionEngine,
    PortfolioConvexityEngine,
    PortfolioCorrelationEngine,
    PortfolioResilienceEngine,
    PortfolioStressEngine,
    PortfolioSurvivalEngine,
)
from libs.stage14.attribution import PortfolioAttribution, PortfolioAttributionEngine
from libs.stage14.audit import PortfolioAudit
from libs.stage14.capacity import PortfolioCapacityEngine, PortfolioCapacityGovernor
from libs.stage14.engine import PortfolioConstructionEngine
from libs.stage14.errors import PortfolioGovernanceError, Stage14Error
from libs.stage14.governance import PortfolioKillCriteria, portfolio_governance_gate
from libs.stage14.growth import CapitalGrowthSimulator, GeometricGrowthEngine
from libs.stage14.kelly import FractionalKellyEngine, KellyEngine, KellyEstimate
from libs.stage14.models import (
    AlphaSleeve,
    CapacityGovernorAction,
    ConvexityResult,
    CorrelationResult,
    EfficiencyResult,
    GeometricGrowthResult,
    GrowthSimResult,
    InstitutionalPortfolioScore,
    KillDecision,
    LeverageDecision,
    MarginalContribution,
    PortfolioCapacityResult,
    PortfolioConstructionResult,
    PortfolioPackage,
    PortfolioState,
    ReinvestmentDecision,
    ResilienceResult,
    RiskBudget,
    StressResult,
    SurvivalResult,
)
from libs.stage14.score import institutional_portfolio_score
from libs.stage14.state_machine import PortfolioStateMachine

__all__ = [  # noqa: RUF022  # grouped by concern
    # models / enums
    "AlphaSleeve",
    "PortfolioState",
    "RiskBudget",
    "GeometricGrowthResult",
    "GrowthSimResult",
    "SurvivalResult",
    "PortfolioCapacityResult",
    "CapacityGovernorAction",
    "StressResult",
    "ResilienceResult",
    "CorrelationResult",
    "ConvexityResult",
    "EfficiencyResult",
    "LeverageDecision",
    "ReinvestmentDecision",
    "MarginalContribution",
    "InstitutionalPortfolioScore",
    "KillDecision",
    "PortfolioPackage",
    "PortfolioConstructionResult",
    # kelly / growth
    "KellyEngine",
    "KellyEstimate",
    "FractionalKellyEngine",
    "GeometricGrowthEngine",
    "CapitalGrowthSimulator",
    # allocation
    "DrawdownAwareAllocator",
    "PortfolioRiskBudgetEngine",
    "SleeveAllocator",
    "DynamicLeverageEngine",
    "AdaptiveReinvestmentEngine",
    "group_by_sleeve",
    # analytics
    "PortfolioCorrelationEngine",
    "PortfolioSurvivalEngine",
    "PortfolioStressEngine",
    "PortfolioResilienceEngine",
    "PortfolioConvexityEngine",
    "MarginalContributionEngine",
    "CapitalEfficiencyEngine",
    # capacity
    "PortfolioCapacityEngine",
    "PortfolioCapacityGovernor",
    # state / score / governance / attribution / audit
    "PortfolioStateMachine",
    "institutional_portfolio_score",
    "portfolio_governance_gate",
    "PortfolioKillCriteria",
    "PortfolioAttributionEngine",
    "PortfolioAttribution",
    "PortfolioAudit",
    # engine
    "PortfolioConstructionEngine",
    # errors
    "Stage14Error",
    "PortfolioGovernanceError",
]

```

### libs/stage14/allocation.py
```python
"""Allocation-side controls: drawdown-aware sizing, risk budgets, sleeves, leverage, reinvestment.

Capital is allocated by *risk* and at the *sleeve* level first, sized down during drawdowns and
instability, levered dynamically (never statically), and reinvested adaptively. Reuses the existing
drawdown governor; survival and growth always dominate return.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import ClassVar

from libs.risk.drawdown import drawdown_governor
from libs.stage14.errors import Stage14Error
from libs.stage14.models import (
    AlphaSleeve,
    LeverageDecision,
    PortfolioState,
    ReinvestmentDecision,
    RiskBudget,
)

_EPS = 1e-12


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class DrawdownAwareAllocator:
    """Scales exposure down in drawdowns; only restores it after recovery is confirmed."""

    def scale(
        self,
        *,
        current_drawdown: float,
        recovered: bool = False,
        regime_stable: bool = True,
        signal_deteriorating: bool = False,
    ) -> float:
        scalar = drawdown_governor(current_drawdown).scalar
        if not regime_stable:
            scalar *= 0.75
        if signal_deteriorating:
            scalar *= 0.5
        # Increase only after recovery confirmation: while still drawn down, cap restoration.
        if current_drawdown > 0.05 and not recovered:
            scalar = min(scalar, 0.5)
        return _clip01(scalar)


class PortfolioRiskBudgetEngine:
    """Allocates risk (not capital): inverse-volatility weights within the vol budget."""

    def inverse_vol_weights(self, vols: Mapping[str, float]) -> dict[str, float]:
        inv = {k: (1.0 / v if v > _EPS else 0.0) for k, v in vols.items()}
        total = sum(inv.values())
        if total <= _EPS:
            return dict.fromkeys(vols, 0.0)
        return {k: w / total for k, w in inv.items()}

    def capital_from_risk(
        self, risk_weights: Mapping[str, float], vols: Mapping[str, float], *, budget: RiskBudget
    ) -> dict[str, float]:
        """Convert risk weights to capital weights targeting the portfolio vol budget."""
        # Crude but robust: scale each name so its risk contribution targets the vol budget.
        out: dict[str, float] = {}
        for k, rw in risk_weights.items():
            vol = vols.get(k, 0.0)
            out[k] = rw * (budget.vol_budget / vol) if vol > _EPS else 0.0
        total = sum(out.values())
        if total > 1.0:  # never allocate more than the available capital
            out = {k: v / total for k, v in out.items()}
        return out


class SleeveAllocator:
    """Budgets capital across alpha sleeves before sizing positions."""

    def __init__(self, *, max_sleeve_weight: float = 0.4) -> None:
        self.max_sleeve_weight = max_sleeve_weight

    def budgets(self, sleeve_scores: Mapping[AlphaSleeve, float]) -> dict[AlphaSleeve, float]:
        positive = {s: max(0.0, v) for s, v in sleeve_scores.items()}
        total = sum(positive.values())
        if total <= _EPS:
            n = len(positive)
            return dict.fromkeys(positive, 1.0 / n if n else 0.0)
        weights = {s: v / total for s, v in positive.items()}
        return self._cap(weights)

    def _cap(self, weights: dict[AlphaSleeve, float]) -> dict[AlphaSleeve, float]:
        w = dict(weights)
        for _ in range(50):
            over = {s: v for s, v in w.items() if v > self.max_sleeve_weight + _EPS}
            if not over:
                break
            excess = sum(v - self.max_sleeve_weight for v in over.values())
            for s in over:
                w[s] = self.max_sleeve_weight
            under = {s: w[s] for s in w if s not in over}
            headroom = sum(max(0.0, self.max_sleeve_weight - v) for v in under.values())
            if headroom <= _EPS:
                break
            for s in under:
                w[s] += excess * max(0.0, self.max_sleeve_weight - w[s]) / headroom
        return w


class DynamicLeverageEngine:
    """Leverage from vol, regime, drawdown, fragility, capacity, survival (never static)."""

    def __init__(self, *, max_leverage: float = 1.0) -> None:
        if max_leverage <= 0:
            raise Stage14Error("max_leverage must be positive")
        self.max_leverage = max_leverage

    def decide(
        self,
        *,
        volatility_state: float = 0.5,
        regime_certainty: float = 1.0,
        drawdown_scalar: float = 1.0,
        fragility: float = 0.0,
        capacity_health: float = 1.0,
        survival_score: float = 100.0,
    ) -> LeverageDecision:
        health = (
            (1.0 - _clip01(volatility_state))
            * _clip01(regime_certainty)
            * _clip01(drawdown_scalar)
            * (1.0 - _clip01(fragility))
            * _clip01(capacity_health)
            * _clip01(survival_score / 100.0)
        )
        leverage = self.max_leverage * health
        return LeverageDecision(
            leverage=max(0.0, min(self.max_leverage, leverage)),
            rationale=f"health={health:.3f} -> leverage scaled from max {self.max_leverage}",
        )


class AdaptiveReinvestmentEngine:
    """Adjusts the reinvestment rate up in stable favorable conditions, down under stress."""

    _STATE_CAP: ClassVar[dict[PortfolioState, float]] = {
        PortfolioState.NORMAL: 1.0,
        PortfolioState.CAUTION: 0.6,
        PortfolioState.DEFENSIVE: 0.3,
        PortfolioState.CRISIS: 0.0,
        PortfolioState.RECOVERY: 0.5,
    }

    def decide(
        self,
        *,
        growth_score: float,
        survival_score: float,
        fragility: float = 0.0,
        regime_uncertainty: float = 0.0,
        state: PortfolioState = PortfolioState.NORMAL,
    ) -> ReinvestmentDecision:
        favorable = _clip01(growth_score / 100.0) * _clip01(survival_score / 100.0)
        dampen = (1.0 - _clip01(fragility)) * (1.0 - _clip01(regime_uncertainty))
        rate = favorable * dampen
        cap = self._STATE_CAP.get(state, 0.5)
        rate = min(rate, cap)
        return ReinvestmentDecision(
            reinvestment_rate=_clip01(rate),
            rationale=f"favorable={favorable:.2f}, dampen={dampen:.2f}, state_cap={cap:.2f}",
        )

    @staticmethod
    def sleeve_of(text: str) -> AlphaSleeve:
        return AlphaSleeve.from_text(text)


def group_by_sleeve(items: Sequence[tuple[str, AlphaSleeve]]) -> dict[AlphaSleeve, list[str]]:
    """Group symbols by their assigned sleeve."""
    grouped: dict[AlphaSleeve, list[str]] = {}
    for symbol, sleeve in items:
        grouped.setdefault(sleeve, []).append(symbol)
    return grouped

```

### libs/stage14_5/factor_exposure.py
```python
"""Factor exposure engine — prevent hidden factor concentration.

Aggregates net USD, net directional, beta, and volatility exposures into a 0-100 score (higher =
more concentrated). The portfolio layer supplies the netted exposures; this scores them against a
cap and flags excessive concentration for hedging.
"""

from __future__ import annotations

from libs.stage14_5.models import FactorExposureResult


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class FactorExposureEngine:
    """Scores portfolio factor concentration."""

    def __init__(self, *, cap: float = 1.0, threshold: float = 70.0) -> None:
        self.cap = cap
        self.threshold = threshold

    def evaluate(
        self,
        *,
        net_usd: float,
        net_directional: float,
        beta: float,
        volatility_exposure: float,
    ) -> FactorExposureResult:
        worst = max(abs(net_usd), abs(net_directional), abs(beta), abs(volatility_exposure))
        score = 100.0 * _clip01(worst / self.cap if self.cap > 0 else 1.0)
        return FactorExposureResult(
            net_usd=net_usd, net_directional=net_directional, beta=beta,
            volatility_exposure=volatility_exposure, factor_exposure_score=score,
            acceptable=score <= self.threshold,
        )

```

### libs/stage14_5/regime_exposure.py
```python
"""Regime exposure engine — maintain alpha-family exposure across all regimes.

Measures how evenly portfolio exposure is spread across regimes (trending / range / high-vol /
low-vol / crisis) and flags uncovered regimes. A balanced book survives regime transitions.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from libs.stage14_5.models import RegimeExposureResult

_DEFAULT_REGIMES = ("trending", "range", "high_vol", "low_vol", "crisis")


def _gini_evenness(values: list[float]) -> float:
    """1 = perfectly even, 0 = fully concentrated."""
    arr = np.array([max(0.0, v) for v in values], dtype="float64")
    total = float(arr.sum())
    n = len(arr)
    if total <= 0 or n < 2:
        return 0.0
    shares = arr / total
    return float(1.0 - np.sum(shares**2) * n / (n - 1) + 1.0 / (n - 1))


class RegimeExposureEngine:
    """Scores regime balance and identifies uncovered regimes."""

    def __init__(
        self, *, required_regimes: Sequence[str] = _DEFAULT_REGIMES, min_exposure: float = 0.05,
        threshold: float = 50.0,
    ) -> None:
        self.required_regimes = list(required_regimes)
        self.min_exposure = min_exposure
        self.threshold = threshold

    def evaluate(self, regime_weights: Mapping[str, float]) -> RegimeExposureResult:
        by_regime = {r: float(regime_weights.get(r, 0.0)) for r in self.required_regimes}
        total = sum(by_regime.values())
        shares = {r: (v / total if total > 0 else 0.0) for r, v in by_regime.items()}
        evenness = _gini_evenness(list(by_regime.values()))
        score = 100.0 * max(0.0, min(1.0, evenness))
        uncovered = [r for r, s in shares.items() if s < self.min_exposure]
        return RegimeExposureResult(
            by_regime=shares, regime_balance_score=score, uncovered_regimes=uncovered,
            balanced=not uncovered and score >= self.threshold,
        )

```

### libs/stage15/orchestrator.py
```python
"""Research orchestrator — the end-to-end live alpha pipeline.

Threads each candidate through: Discovery -> Validation -> Walk-Forward -> Shadow -> Paper ->
Allocation, gated by the alpha governance gate and overseen by the research kill-switch. It
consumes the verdicts/scores produced by the existing engines (gauntlet, walk-forward governance,
shadow deployment) — it does not re-implement them — and routes each alpha to the furthest stage it
has earned. Recommend-only: it never trades or allocates capital itself.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from libs.stage15.audit import ResearchAudit
from libs.stage15.governance import ResearchGovernanceEngine, alpha_governance_gate
from libs.stage15.models import (
    AlphaScores,
    PipelineRecord,
    PipelineStage,
    ResearchPipelineResult,
)
from libs.stage15.scoring import alpha_quality_score
from libs.validation.gauntlet import GauntletResult


class AlphaPipelineInput(BaseModel):
    """One candidate's evaluated state, as produced by the discovery + validation engines."""

    model_config = ConfigDict(frozen=True)

    alpha_id: str
    scores: AlphaScores
    cpcv_passed: bool = False
    pbo_acceptable: bool = False
    dsr_passed: bool = False
    reality_check_passed: bool = False
    economic_mechanism_present: bool = False
    capacity_acceptable: bool = False
    fragility_acceptable: bool = False
    walk_forward_passed: bool = False
    shadow_ready: bool = False

    @classmethod
    def from_gauntlet(
        cls,
        alpha_id: str,
        gauntlet: GauntletResult,
        scores: AlphaScores,
        *,
        economic_mechanism_present: bool,
        capacity_acceptable: bool,
        fragility_acceptable: bool,
        walk_forward_passed: bool,
        shadow_ready: bool = False,
    ) -> AlphaPipelineInput:
        """Bridge a real gauntlet verdict into the pipeline (the gauntlet runs CPCV/PBO/DSR/SPA)."""
        passed = gauntlet.passed
        return cls(
            alpha_id=alpha_id, scores=scores,
            cpcv_passed=passed, pbo_acceptable=passed, dsr_passed=passed,
            reality_check_passed=passed,
            economic_mechanism_present=economic_mechanism_present,
            capacity_acceptable=capacity_acceptable,
            fragility_acceptable=fragility_acceptable,
            walk_forward_passed=walk_forward_passed, shadow_ready=shadow_ready,
        )


class ResearchOrchestrator:
    """Routes candidates through the live research pipeline under research governance."""

    def __init__(
        self,
        *,
        min_allocation_quality: float = 70.0,
        governance: ResearchGovernanceEngine | None = None,
        audit: ResearchAudit | None = None,
    ) -> None:
        self.min_allocation_quality = min_allocation_quality
        self.governance = governance or ResearchGovernanceEngine()
        self.audit = audit

    def run(
        self,
        candidates: Sequence[AlphaPipelineInput],
        *,
        false_discovery_rate: float = 0.0,
        validation_pass_rate: float = 1.0,
        discovery_quality: float = 100.0,
        decay_rate: float = 0.0,
    ) -> ResearchPipelineResult:
        kill = self.governance.evaluate(
            false_discovery_rate=false_discovery_rate,
            validation_pass_rate=validation_pass_rate,
            discovery_quality=discovery_quality, decay_rate=decay_rate,
        )

        records: list[PipelineRecord] = []
        allocated: list[str] = []
        rejected: list[str] = []
        for cand in candidates:
            quality = alpha_quality_score(cand.scores).score
            verdict = alpha_governance_gate(
                cpcv_passed=cand.cpcv_passed, pbo_acceptable=cand.pbo_acceptable,
                dsr_passed=cand.dsr_passed, reality_check_passed=cand.reality_check_passed,
                economic_mechanism_present=cand.economic_mechanism_present,
                capacity_acceptable=cand.capacity_acceptable,
                fragility_acceptable=cand.fragility_acceptable,
                walk_forward_passed=cand.walk_forward_passed,
            )
            if not verdict.accepted:
                stage, accepted, note = PipelineStage.REJECTED, False, ", ".join(
                    verdict.rejected_reasons
                )
                rejected.append(cand.alpha_id)
            elif kill.halt:
                # Validated, but research is halted -> hold in shadow, no new capital.
                stage, accepted, note = PipelineStage.SHADOW, True, "research halt: no new capital"
            elif not cand.shadow_ready:
                stage, accepted, note = PipelineStage.SHADOW, True, "awaiting shadow completion"
            elif quality < self.min_allocation_quality:
                stage, accepted, note = PipelineStage.PAPER, True, (
                    f"quality {quality:.1f} < {self.min_allocation_quality} -> paper trade"
                )
            else:
                stage, accepted, note = PipelineStage.ALLOCATION, True, "cleared for allocation"
                allocated.append(cand.alpha_id)
            records.append(
                PipelineRecord(
                    alpha_id=cand.alpha_id, stage=stage, quality_score=quality,
                    accepted=accepted, note=note,
                )
            )

        result = ResearchPipelineResult(
            records=records, allocated=allocated, rejected=rejected, kill=kill
        )
        if self.audit is not None:
            self.audit.record_pipeline(result)
        return result

```

### libs/store/connection.py
```python
"""SQLite connection management — ACID, WAL, single-writer.

The :class:`Database` wraps one connection configured for the platform's invariants:
WAL journaling (one writer, many readers), enforced foreign keys, and manual transaction
control. Readers (e.g. dashboards) open a separate read-only connection that physically
cannot write — the single-writer rule made structural.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

# Applied to every writable connection.
_WRITE_PRAGMAS: tuple[str, ...] = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA foreign_keys=ON",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA busy_timeout=5000",
)
_READ_PRAGMAS: tuple[str, ...] = (
    "PRAGMA foreign_keys=ON",
    "PRAGMA busy_timeout=5000",
)


class Database:
    """A single SQLite connection with WAL + foreign keys + manual transactions."""

    def __init__(self, path: str | Path, *, read_only: bool = False) -> None:
        self.path = Path(path)
        self.read_only = read_only
        if read_only:
            uri = f"file:{self.path}?mode=ro"
            self._conn = sqlite3.connect(uri, uri=True, isolation_level=None)
            pragmas = _READ_PRAGMAS
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.path), isolation_level=None)
            pragmas = _WRITE_PRAGMAS
        self._conn.row_factory = sqlite3.Row
        for pragma in pragmas:
            self._conn.execute(pragma)

    @property
    def connection(self) -> sqlite3.Connection:
        """The underlying connection (use within :meth:`transaction` for writes)."""
        return self._conn

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> sqlite3.Cursor:
        """Execute a single statement (autocommit outside a transaction block)."""
        return self._conn.execute(sql, params)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Run a block atomically; commit on success, roll back on any exception."""
        if self.read_only:
            raise RuntimeError("cannot open a write transaction on a read-only Database")
        self._conn.execute("BEGIN")
        try:
            yield self._conn
            self._conn.execute("COMMIT")
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise

    def journal_mode(self) -> str:
        """Return the active journal mode (``wal`` for on-disk databases)."""
        row = self._conn.execute("PRAGMA journal_mode").fetchone()
        return str(row[0]).lower()

    def close(self) -> None:
        """Close the connection."""
        self._conn.close()

    def __enter__(self) -> Database:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

```

### libs/validation/event_study.py
```python
"""Event-study validation -- the promotion path for edges that are EVENTS, not time series.

Every gate the desk owns scores a CONTINUOUS DAILY RETURN SERIES: Sharpe, DSR, PBO, walk-forward,
Newey-West. That is the right shape for carry, trend and cross-sectional sleeves. It is the wrong
shape for the edges a small book actually wants (§42): a day-1 listing funding spike is a handful
of hours, happens a few times a week, and is over. Thirty such events are thirty observations --
but strung into a daily series they are ~2 non-zero days in 30 mostly-flat ones, and every
continuous statistic reads that as noise. The result is that the desk could COLLECT the listing
data (run_listing_watch already does) and never be able to PROMOTE what it found: acquired, not
convertible, at the strategy layer.

This module is that missing path. The unit of evidence is the EVENT.

WHY THIS IS FASTER WITHOUT BEING WEAKER -- the point that matters. At 2-4 new perp listings a
week, 30 events is ~10 weeks: comparable to the 40-day forward clock in calendar terms, but far
richer in statistical content, because 30 events are 30 largely-independent draws whereas 40 daily
returns are 40 autocorrelated ones. The clock shortens because the EVIDENCE is denser, not because
the bar moved. Same argument as reconstructed-history backfill, applied to events.

THE TRAP, AND WHY IT IS CHECKED HERE. Overlapping event windows share the same market moves, so
they are not independent draws: a market-wide shock inside two overlapping windows is one
observation counted twice, and the cross-sectional standard error silently shrinks. Overlap is
therefore MEASURED and reported, and the effective N is discounted by it -- the same
effective-vs-raw discipline §31 applies to trial counts, here applied to observations.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict

from libs.validation.errors import ValidationError

#: Below this an event study says nothing: the cross-sectional t-test needs a usable sample, and
#: crypto event returns are fat-tailed enough that small-N normal approximations mislead badly.
MIN_EVENTS = 20


class Event(BaseModel):
    """One occurrence: when it started, how long it ran, and the return earned across it."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    t_start: float                # epoch seconds
    t_end: float
    ret: float                    # realised return over the window (ABNORMAL if a benchmark
    #                               was subtracted by the caller -- see abnormal_returns)

    @property
    def duration_s(self) -> float:
        return max(0.0, self.t_end - self.t_start)


def abnormal_returns(
    event_rets: np.ndarray, benchmark_rets: np.ndarray | None = None
) -> np.ndarray:
    """Subtract the benchmark earned over each event's own window.

    Without this an event study measures BETA, not edge: a listing study run through a bull month
    reports the market. This is the same error as the video's AI 'beating' a falling S&P by sitting
    in cash -- the number was the benchmark's, not the strategy's.
    """
    r = np.asarray(event_rets, dtype="float64")
    if benchmark_rets is None:
        return r
    b = np.asarray(benchmark_rets, dtype="float64")
    if b.shape != r.shape:
        raise ValidationError("benchmark_rets must align 1:1 with event_rets")
    return np.asarray(r - b, dtype="float64")


def overlap_fraction(events: list[Event]) -> float:
    """Share of events whose window intersects another's -- the independence discount.

    Overlapping windows share market moves, so they are not independent draws. Reported rather
    than silently corrected, because the honest response depends on WHY they overlap.
    """
    if len(events) < 2:
        return 0.0
    ordered = sorted(events, key=lambda e: e.t_start)
    overlapping: set[str] = set()
    for i, a in enumerate(ordered):
        for b in ordered[i + 1:]:
            if b.t_start >= a.t_end:
                break                       # sorted: nothing later can overlap a either
            overlapping.add(a.event_id)
            overlapping.add(b.event_id)
    return round(len(overlapping) / len(events), 3)


class EventStudyResult(BaseModel):
    """Cross-sectional verdict over N events."""

    model_config = ConfigDict(frozen=True)

    n_events: int
    n_effective: float            # N discounted for overlapping windows
    mean_ret: float
    std_ret: float
    t_stat: float                 # cross-sectional (Brown-Warner), on effective N
    hit_rate: float               # share of events with a positive return
    boot_lo: float                # 5th pct of the bootstrapped mean -- fat-tail sanity check
    boot_hi: float
    overlap: float
    bar: float                    # multiplicity-corrected t threshold this had to clear
    passed: bool
    verdict: str


def event_study(
    events: list[Event],
    *,
    n_cohort: int = 1,
    rank: int = 1,
    alpha: float = 0.05,
    min_events: int = MIN_EVENTS,
    n_boot: int = 2000,
    seed: int = 0,
) -> EventStudyResult:
    """Cross-sectional event study with a multiplicity-corrected bar and a bootstrap check.

    ``n_cohort``/``rank`` plug into the desk's existing Holm discipline: an event edge found while
    screening K candidate event-types is one of K, and is deflated exactly as a candidate cohort
    is (``forward_stats.holm_bar``). A single PRE-REGISTERED event hypothesis uses n_cohort=1.

    The bootstrap runs alongside the parametric t on purpose: crypto event returns are strongly
    fat-tailed, and a t-stat that clears on a normal assumption while the bootstrap interval spans
    zero is exactly the false positive this desk exists to refuse.
    """
    from libs.validation.forward_stats import holm_bar

    n = len(events)
    if n < min_events:
        return EventStudyResult(
            n_events=n, n_effective=float(n), mean_ret=0.0, std_ret=0.0, t_stat=0.0,
            hit_rate=0.0, boot_lo=0.0, boot_hi=0.0, overlap=0.0, bar=0.0, passed=False,
            verdict=(f"{n}/{min_events} events -- too few to judge. An event study below ~20 "
                     "observations is a story, not evidence; keep the clock running."),
        )
    r = np.array([e.ret for e in events], dtype="float64")
    ov = overlap_fraction(events)
    # Discount N by overlap: fully-overlapping events are ONE observation, not many. Linear is
    # crude but conservative, and conservative is the correct direction for an independence proxy.
    n_eff = max(1.0, n * (1.0 - ov))
    mean = float(r.mean())
    std = float(r.std(ddof=1)) if n > 1 else 0.0
    # DEGENERATE INPUT. `std == 0.0` is the wrong guard: numpy returns ~3e-19 for identical
    # values, so an exact-equality check never fires and the t-stat explodes (measured: 3e16 for
    # 30 identical returns) -- a constant series would then clear every bar in the module. Real
    # event returns are never constant, so this is a DATA defect (a repeated fill price, a stubbed
    # feed, a join that fanned one row out) and must be refused loudly rather than scored.
    if std <= 1e-12 or not np.isfinite(std):
        return EventStudyResult(
            n_events=n, n_effective=round(n_eff, 1), mean_ret=round(mean, 6), std_ret=0.0,
            t_stat=0.0, hit_rate=round(float((r > 0).mean()), 3), boot_lo=0.0, boot_hi=0.0,
            overlap=ov, bar=0.0, passed=False,
            verdict=(f"DEGENERATE: {n} events with ~zero cross-sectional variance (std={std:.2e}). "
                     "Real event returns are never constant -- this is a data defect (repeated "
                     "price, stubbed feed, fanned-out join), not an edge. Fix the input."),
        )
    t = mean / (std / np.sqrt(n_eff))

    rng = np.random.default_rng(seed)
    boots = rng.choice(r, size=(n_boot, n), replace=True).mean(axis=1)
    lo, hi = (float(np.percentile(boots, 5)), float(np.percentile(boots, 95)))

    bar = holm_bar(max(1, n_cohort), rank, alpha=alpha)
    # BOTH must hold: the corrected t AND a bootstrap interval that excludes zero. Either alone is
    # defeatable -- the t by fat tails, the bootstrap by a lucky resample of a thin sample.
    passed = bool(t >= bar and lo > 0.0)

    if passed:
        verdict = (f"PASS: {n} events (eff {n_eff:.0f}), mean {mean:+.4%}, t={t:.2f} vs bar "
                   f"{bar:.2f}, bootstrap 90% CI [{lo:+.4%}, {hi:+.4%}] excludes zero.")
    elif t >= bar:
        verdict = (f"t={t:.2f} clears the {bar:.2f} bar but the bootstrap CI [{lo:+.4%}, "
                   f"{hi:+.4%}] SPANS ZERO -- fat tails, not edge. Refused.")
    else:
        verdict = (f"t={t:.2f} below the multiplicity-corrected bar {bar:.2f} "
                   f"({n} events, eff {n_eff:.0f}, overlap {ov:.0%}). Keep collecting.")
    return EventStudyResult(
        n_events=n, n_effective=round(n_eff, 1), mean_ret=round(mean, 6),
        std_ret=round(std, 6), t_stat=round(t, 3),
        hit_rate=round(float((r > 0).mean()), 3), boot_lo=round(lo, 6), boot_hi=round(hi, 6),
        overlap=ov, bar=round(bar, 3), passed=passed, verdict=verdict,
    )

```

### scripts/bundle_algo.py
```python
"""Concatenate the complete TRADING CORE into one readable file -> web/algo_full.txt.

The platform is ~300 modules; this bundles the actual algorithm end-to-end (data -> alpha sleeves
-> portfolio construction -> edge-gated leverage -> execution) into a single annotated file you can
read, share, or download from the dashboard URL. Not every helper -- the strategy itself.

    python scripts/bundle_algo.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

# the core pipeline, in execution order
_FILES = [
    ("DATA  -- free Binance perp data (OHLCV + funding + basis + taker flow)",
     "libs/data/crypto_source.py"),
    ("ALPHA -- cross-sectional funding carry (the survivor) + ADV-tiered cost",
     "libs/research/crypto_xsec.py"),
    ("ALPHA -- decorrelated sleeves (basis / taker-flow / momentum) + live weights",
     "libs/research/crypto_sleeves.py"),
    ("ALPHA -- delta-neutral cash-and-carry (spot + perp)", "libs/research/cashcarry.py"),
    ("PORTFOLIO -- combine sleeves into one net target weight per perp",
     "scripts/run_crypto_target.py"),
    ("RISK  -- edge-gated leverage (half-Kelly of forward-validated Sharpe)",
     "libs/risk/edge_gate.py"),
    ("EXEC  -- Binance futures testnet connector (orders, positions, P&L)",
     "libs/execution/binance_testnet.py"),
    ("EXEC  -- maker-first execution (post-only, taker fallback)", "libs/execution/maker.py"),
    ("EXEC  -- the live executor loop (rebalance, throttle, gating, snapshot)",
     "scripts/run_crypto_testnet.py"),
]
_OUT = Path("web/algo_full.txt")


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    parts = [f"QUANT TRADING CORE -- consolidated {datetime.now(tz=UTC).isoformat()}",
             "Generated by bundle_algo.py. Full repo lives at C:/Users/dell/quant-platform.",
             "Order = execution pipeline: data -> alpha -> portfolio -> risk -> execution.", ""]
    n = 0
    for label, rel in _FILES:
        p = root / rel
        if not p.exists():
            continue
        body = p.read_text("utf-8")
        n += body.count("\n")
        parts += ["=" * 100, f"# {label}", f"# FILE: {rel}", "=" * 100, "", body, ""]
    _OUT.write_text("\n".join(parts), "utf-8")
    print(f"bundled {len(_FILES)} core files (~{n} lines) -> {_OUT}")


if __name__ == "__main__":
    main()

```

### scripts/check_organ_liveness.py
```python
#!/usr/bin/env python3
"""ORGAN LIVENESS (R0144) -- is every scheduled organ actually PRODUCING?

PRINCIPAL ORDER (2026-07-31): *"make sure all miners etc run, just do it all yourself, don't tell
me to check -- you make sure all cycles are running as intended."*

That instruction is correct and it exposed a real hole. The desk could already check two things:
`check_scheduler_manifest.py` compares the manifest against `crontab -l` (is the line INSTALLED),
and `check_exploration.py` checks freshness for six named exploration organs. Nothing checked the
question that actually matters for the other hundred-odd lines: **did this organ produce anything
recently?**

Those are genuinely different failures and only the third is the one that costs alpha:

    installed but never runs   -- wrong path, missing venv, a lock never released
    runs but produces nothing  -- auth expired, quota exhausted, an API gone 451
    produces but is stale      -- the cadence silently slipped

An organ can pass the manifest check, appear in `crontab -l`, and have emitted nothing for a week.
That is exactly how a miner goes dark unnoticed: nothing errors, no page fires, and the board stays
green because the board was only ever checking that the LINE existed.

HOW IT WORKS. The manifest already carries the two facts needed, on 79 of its entries:
a cron schedule, and an `# EVIDENCE: script -> artifact` line naming what the organ writes. This
parses both, converts the schedule into an expected interval, and compares against the artifact's
real age. No new bookkeeping -- the manifest was already the genome, it just was not being read
this way.

TOLERANCE IS 3x THE CADENCE, deliberately loose. A single missed tick is a machine hiccup; three
consecutive is a dead organ. A tighter tolerance produces a board that is red most mornings, and a
board that is red most mornings is one nobody reads -- which is the failure this organ exists to
end, not to reproduce.

NEVER-PRODUCED IS ITS OWN STATE, not a very old STALE. An organ that has never once written its
artifact was never working, which is a different diagnosis (wiring) from one that stopped (auth,
quota, upstream). Collapsing them would send someone to debug the wrong thing.

    python scripts/check_organ_liveness.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
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

#: 3 consecutive missed cadences before an organ is called dead. One miss is a hiccup; three is a
#: pattern. Loose on purpose -- a board that is red most mornings is a board nobody reads.
STALE_MULTIPLE = 3.0
#: Floor on the tolerance so a */5 organ is not declared dead 15 minutes after a reboot. 2h is
#: about the shortest window in which "it did not run" is distinguishable from "the box restarted".
MIN_TOLERANCE_H = 2.0


def cadence_hours(cron: str) -> float | None:
    """Expected hours between runs, from a 5-field cron expression."""
    parts = cron.split()
    if len(parts) < 5:
        return None
    m, h, dom, _mon, dow = parts[:5]

    def count(field: str, span: int) -> int:
        if field.startswith("*/"):
            try:
                return max(1, span // int(field[2:]))
            except ValueError:
                return 1
        if field == "*":
            return span
        return len([x for x in field.split(",") if x])
    per_day = count(m, 60) * count(h, 24)
    if dow != "*":
        per_day *= len([x for x in dow.split(",") if x]) / 7.0
    if dom != "*" and dom.startswith("*/"):
        try:
            per_day /= float(dom[2:])
        except ValueError:
            # NOT swallowed: an unparseable day-of-month means the cadence is UNKNOWN, and a
            # wrong cadence produces a wrong tolerance -- which is how this fence would report a
            # live organ as dead, or a dead one as fine. Refuse to guess.
            return None
    elif dom != "*":
        per_day /= 30.0
    return 24.0 / per_day if per_day > 0 else None


def parse_manifest(text: str) -> list[dict[str, Any]]:
    """(schedule, script, artifacts) per scheduled line, from the EVIDENCE block above it."""
    out: list[dict[str, Any]] = []
    evidence: str | None = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("# EVIDENCE:"):
            evidence = s[len("# EVIDENCE:"):].strip()
            continue
        if s.startswith("#") or not s:
            continue
        if not re.match(r"^[\d*]", s) or "SYSTEMD" in s:
            evidence = None if s.startswith("SYSTEMD") else evidence
            continue
        cron = " ".join(s.split()[:5])
        script = None
        ms = re.search(r"((?:scripts|ops)/[\w./-]+\.(?:py|sh))", s)
        if ms:
            script = ms.group(1)
        arts: list[str] = []
        if evidence and "->" in evidence:
            tail = evidence.split("->", 1)[1]
            # SEPARATORS ARE '+', ',' AND ';' -- the first version missed the semicolon, so
            # `data/law_gate.json; docs/CONSTITUTION.md L1.37` parsed as `data/law_gate.json;`
            # and every such organ read NEVER-PRODUCED. That is worse than no fence: a board
            # that is wrongly red gets disabled, which is precisely the failure this exists to
            # end. Trailing punctuation is stripped for the same reason.
            for tok in re.split(r"[+,;]", tail):
                tok = tok.strip().split()[0] if tok.strip() else ""
                tok = tok.strip(";,.)([]")
                # ONLY data/ PATHS COUNT. An EVIDENCE line often CITES a law
                # (`-> data/x.json; docs/CONSTITUTION.md L1.37`), and a citation is not an output.
                # Counting it would satisfy liveness with a static file that never changes, so
                # every organ citing a law would read FRESH forever -- a false GREEN, which is
                # strictly worse than the false RED the semicolon bug produced.
                if not tok or not tok.endswith((".json", ".jsonl")):
                    continue
                tok = tok if "/" in tok else f"data/{tok}"
                if not tok.startswith("data/"):
                    continue
                arts.append(tok)
        out.append({"cron": cron, "script": script, "artifacts": arts,
                    "cadence_h": cadence_hours(cron)})
        evidence = None
    return out


def audit(root: Path | None = None, *, now: float | None = None) -> dict[str, Any]:
    root = root or _ROOT
    now = now if now is not None else time.time()
    try:
        text = (root / "ops/crontab.manifest").read_text("utf-8", errors="ignore")
    except OSError as exc:
        return {"status": "UNMEASURED", "detail": f"manifest unreadable: {exc}", "organs": []}
    rows = parse_manifest(text)
    organs: list[dict[str, Any]] = []
    for r in rows:
        if not r["artifacts"] or not r["cadence_h"]:
            continue                       # no declared evidence: check_build_standard's problem
        tol = max(MIN_TOLERANCE_H, r["cadence_h"] * STALE_MULTIPLE)
        ages = []
        for a in r["artifacts"]:
            p = root / a
            ages.append((now - p.stat().st_mtime) / 3600.0 if p.exists() else None)
        fresh = [x for x in ages if x is not None]
        if not fresh:
            state, age = "NEVER-PRODUCED", None
        else:
            age = min(fresh)
            state = "FRESH" if age <= tol else "STALE"
        organs.append({"script": r["script"], "cron": r["cron"],
                       "cadence_h": round(r["cadence_h"], 2), "tolerance_h": round(tol, 2),
                       "artifacts": r["artifacts"],
                       "age_h": None if age is None else round(age, 2), "state": state})
    dead = [o for o in organs if o["state"] == "NEVER-PRODUCED"]
    stale = [o for o in organs if o["state"] == "STALE"]
    status = ("UNMEASURED" if not organs else
              "DARK" if dead or stale else "OK")
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.28a/L1.28c -- a scheduled line that produces nothing is not a running organ. "
               "Installed, running, and PRODUCING are three different facts and only the third "
               "is worth anything.",
        "status": status,
        "n_checked": len(organs), "n_fresh": len(organs) - len(dead) - len(stale),
        "never_produced": [o["script"] for o in dead],
        "stale": [{"script": o["script"], "age_h": o["age_h"], "tolerance_h": o["tolerance_h"]}
                  for o in stale],
        "organs": organs,
        "diagnosis": ("NEVER-PRODUCED means WIRING (path, venv, lock) -- it was never working. "
                      "STALE means it STOPPED (auth, quota, upstream 451). Different repairs, so "
                      "they are never collapsed into one state."),
        "detail": (f"{len(organs) - len(dead) - len(stale)}/{len(organs)} scheduled organs with "
                   f"declared evidence produced within their own cadence"
                   + (f"; NEVER PRODUCED: {', '.join(o['script'] or '?' for o in dead)}"
                      if dead else "")
                   + (f"; STALE: {', '.join(o['script'] or '?' for o in stale)}" if stale else "")),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = audit()
    out = _ROOT / "data/organ_liveness.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"organ liveness (L1.28c): {rep['status']} -- {rep['detail'][:200]}")
        for o in rep["organs"]:
            if o["state"] != "FRESH":
                print(f"  {o['state']:<16}{o['script']!s:<38}"
                      f"age={o['age_h']} tol={o['tolerance_h']}h")
    if args.report_only:
        return 0
    return 2 if rep["status"] == "DARK" else 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/collect_oi_ls_live.py
```python
"""LIVE OI / LONG-SHORT COLLECTOR -- the desk's best mechanism has been running on 2023 data.

THE FINDING THAT MOTIVATED THIS. data/oi_ls_history.jsonl ends 2023-12-03. It is a static backfill
written once by dl_metrics_history.py for OOS backtesting -- correct as an archive, useless as a
live feed. Meanwhile M_FORCED_DELEVERAGE is the desk's BEST-supported mechanism (2/10 survival,
highest of nine) and holds its ONLY confirmed edge (funding persistence, IC +0.432, t +29.7).

So the mechanism with the strongest evidence has had no live positioning data at all. Binance
publishes both feeds free, no key: openInterestHist and globalLongShortAccountRatio.

MECHANISM, falsifiable as stated:
    crowded positioning -> one side pays funding -> adverse move squeezes the crowd ->
    forced unwind -> the squeeze that positioning predicted
Forced participant: the leveraged crowd. Constraint: margin, which cannot be negotiated or timed.
Why not arbitraged: the data is public but the CONSTRAINT is real -- knowing a crowd is levered
does not let you avoid being the crowd.

UNIVERSE IS THE VIABLE SET, NOT THE FUNDING-RANKED SET. Only symbols whose MEASURED round-trip
lets a carry clear costs (carry_viability: 16 of 30) are collected. Collecting positioning on
COOKIEUSDT -- 130.47bps round-trip against 6.7bps of funding -- would be gathering evidence about
a trade that can never be profitable. The universe switch already applied this to trading; this
applies it to research.

DEFENCES (identical pattern to collect_defi_lending, deliberately):
  schema contract -> quarantine, sanity bounds per row, coverage floor, separate heartbeat.
"""
from __future__ import annotations

import json
import ssl
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/oi_ls_live.jsonl"
HB = ROOT / "data/oi_ls_live_heartbeat"
QUAR = ROOT / "data/oi_ls_live_quarantine.json"
COST = ROOT / "data/cost_model.json"
CTX = ssl.create_default_context()
BASE = "https://fapi.binance.com/futures/data"

PERIOD = "1h"
_MIN_SYMBOLS = 8
_MAX_VIABLE_RT_BPS = 8.0        # matches carry_viability: clears at <=3bp funding over a 24h hold
_FALLBACK = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "SOLUSDT", "DOGEUSDT",
             "AVAXUSDT", "LINKUSDT", "LTCUSDT", "TRXUSDT")


def _get(path: str, params: str):
    r = urllib.request.Request(f"{BASE}/{path}?{params}",
                               headers={"User-Agent": "quant-desk/1.0"})
    return json.loads(urllib.request.urlopen(r, timeout=45, context=CTX).read())


def _viable_universe() -> list[str]:
    """Symbols whose MEASURED round-trip can clear ordinary funding. Never the funding ranking."""
    try:
        cm = json.loads(COST.read_text("utf-8"))["symbols"]
    except Exception:  # blind-except intentional (BLE001)
        return list(_FALLBACK)
    out = []
    for sym, d in cm.items():
        try:
            v = d["pair"]["500"].get("pair_roundtrip_bps")
            if v is not None and float(v) <= _MAX_VIABLE_RT_BPS:
                out.append(sym)
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(out) or list(_FALLBACK)


def _quarantine(reason: str, detail: dict) -> None:
    QUAR.write_text(json.dumps({"ts": datetime.now(tz=UTC).isoformat(), "reason": reason,
                                **detail}, indent=1), "utf-8")
    print(f"  QUARANTINED: {reason}")
    print("  Nothing written. Wrong data is trusted downstream and fails silently;")
    print("  a stopped collector at least announces itself.")


def main() -> None:
    ts = datetime.now(tz=UTC)
    print("=== LIVE OI / LONG-SHORT COLLECTOR -- M_FORCED_DELEVERAGE ===")
    print("    data/oi_ls_history.jsonl ends 2023-12-03 (static archive). The desk's")
    print("    best-supported mechanism has had NO live positioning feed.\n")
    universe = _viable_universe()
    print(f"  universe: {len(universe)} symbols with measured round-trip "
          f"<= {_MAX_VIABLE_RT_BPS}bps (viable set, not funding-ranked)")

    rows, failed = [], []
    for sym in universe:
        try:
            oi = _get("openInterestHist", f"symbol={sym}&period={PERIOD}&limit=1")
            ls = _get("globalLongShortAccountRatio", f"symbol={sym}&period={PERIOD}&limit=1")
            tk = _get("takerlongshortRatio", f"symbol={sym}&period={PERIOD}&limit=1")
            if not oi or not ls:
                failed.append(sym)
                continue
            o, lrow = oi[-1], ls[-1]
            t = tk[-1] if tk else {}
            lsr = float(lrow["longShortRatio"])
            la = float(lrow["longAccount"])
            # sanity: ratio and account share must be internally consistent and bounded
            if not (0.01 < lsr < 100.0 and 0.0 < la < 1.0):
                failed.append(sym)
                continue
            rows.append({
                "ts": ts.isoformat(), "symbol": sym, "period": PERIOD,
                "oi_contracts": float(o["sumOpenInterest"]),
                "oi_usd": float(o["sumOpenInterestValue"]),
                "long_short_ratio": lsr, "long_account": la,
                "short_account": float(lrow["shortAccount"]),
                "taker_buy_sell_ratio": float(t.get("buySellRatio", 0)) or None,
                "src_ts": int(o["timestamp"])})
            time.sleep(0.12)                      # courteous to a free public endpoint
        except Exception:  # blind-except intentional (BLE001)
            failed.append(sym)

    if len(rows) < _MIN_SYMBOLS:
        _quarantine("coverage below floor", {"collected": len(rows), "floor": _MIN_SYMBOLS,
                                             "failed": failed})
        raise SystemExit(1)

    with OUT.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    HB.write_text(f"{ts.isoformat()} symbols={len(rows)}", "utf-8")
    if QUAR.exists():
        QUAR.unlink()

    tot_oi = sum(r["oi_usd"] for r in rows)
    crowd = sorted(rows, key=lambda r: -abs(r["long_short_ratio"] - 1.0))[:6]
    print(f"  collected {len(rows)}/{len(universe)}  failed={failed or 'none'}")
    print(f"  aggregate open interest ${tot_oi/1e9:.2f}bn\n")
    print(f"  {'symbol':<12}{'L/S ratio':>11}{'long%':>8}{'OI $m':>10}{'taker b/s':>11}")
    for r in crowd:
        print(f"  {r['symbol']:<12}{r['long_short_ratio']:>11.3f}{r['long_account']*100:>7.1f}%"
              f"{r['oi_usd']/1e6:>10.0f}{(r['taker_buy_sell_ratio'] or 0):>11.3f}")
    print("\n  CROWDING IS THE OBSERVABLE, NOT THE ALPHA. A ratio far from 1.0 marks where one")
    print("  side is levered and therefore squeezable. Whether that predicts anything net of")
    print("  cost is a Stage-A question this only feeds -- and the same construction died as a")
    print("  standalone signal before, so it earns a forward clock only in combination.")
    print(f"\n  -> {OUT}  (heartbeat {HB.name})")


if __name__ == "__main__":
    main()

```

### scripts/collect_stablecoin_supply.py
```python
"""Broad stablecoin-supply momentum collector + Stage-A screen (2026-07-23 alt-data batch).

Total stablecoin market cap (DefiLlama, ALL issuers/chains) as a macro dollar-liquidity signal:
rising aggregate supply = net minting = new capital entering crypto -> momentum (supply-z up
precedes higher forward BTC return). Cleanest survivor of the alt-data batch: IC +0.067, momentum
Sharpe 0.88, same-period corr +0.08 (orthogonal), residual IC +0.072 (STRENGTHENS -> genuinely
leading), over 900 days. Passes the de-contam + SUSPECT-LOOKAHEAD rails.

RELATIONSHIP TO EXISTING SIGNAL (angle-14, no double-counting): scripts/run_stablecoin_flows.py
already RECORDS a supply figure (USDT+USDC on-chain totalSupply) as a designated signal, but it is
NOT screened or forward-tracked in run_axis_shadows -- it just accrues in an archive. This is the
SAME economic construct with (a) broader coverage (all stablecoins incl. DAI/USDe/FDUSD/PYUSD, not
just USDT+USDC) and (b) the formal Holm-tracked forward clock the archived version lacks. Treat the
two as ONE hypothesis for evidence purposes; this is the evaluated version.

Free DefiLlama API, no key. stdlib + numpy. Run from repo root.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from libs.research.axis_screen import stage_a_screen

_STABLES = "https://stablecoins.llama.fi/stablecoincharts/all"
_BINANCE = "https://api.binance.com/api/v3/klines"
_SERIES = Path("data/stablecoin_supply.jsonl")


def _get(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": "quant-stablesupply/1.0"})
    with urllib.request.urlopen(req, timeout=35) as r:
        return json.loads(r.read().decode())


def _supply() -> dict[str, float]:
    d = _get(_STABLES)
    out: dict[str, float] = {}
    if not isinstance(d, list):        # narrow the untyped JSON boundary, do not assume shape
        return out
    for x in d:
        v = x.get("totalCirculatingUSD") or x.get("totalCirculating") or {}
        peg = v.get("peggedUSD") if isinstance(v, dict) else None
        if peg is not None:
            out[datetime.fromtimestamp(int(x["date"]), tz=UTC).date().isoformat()] = float(peg)
    return out


def _binance_daily(sym: str, n: int = 900) -> dict[str, float]:
    rows = _get(f"{_BINANCE}?symbol={sym}&interval=1d&limit={n}")
    if not isinstance(rows, list):
        return {}
    return {datetime.fromtimestamp(int(r[0]) / 1000, tz=UTC).date().isoformat(): float(r[4])
            for r in rows}


def main() -> None:
    sup = _supply()
    gbtc = _binance_daily("BTCUSDT")
    if not (sup and gbtc):
        raise SystemExit(f"fetch failed: supply={len(sup)} binance={len(gbtc)}")
    dates = sorted(set(sup) & set(gbtc))
    if len(dates) < 90:
        raise SystemExit(f"only {len(dates)} aligned days")

    sig = np.array([sup[d] for d in dates])
    btc = np.array([gbtc[d] for d in dates])
    ret = np.zeros(len(btc))
    ret[1:] = btc[1:] / btc[:-1] - 1.0

    z = np.zeros(len(sig))
    for t in range(20, len(sig)):
        w = sig[t - 20:t]
        sd = w.std()
        z[t] = (sig[t] - w.mean()) / sd if sd > 0 else 0.0

    scr = stage_a_screen(sig, ret, name="stablecoin_supply_momentum")

    today = datetime.now(tz=UTC).date().isoformat()
    rec = {"date": today, "supply_usd": round(float(sig[-1]), 0),
           "z20": round(float(z[-1]), 3), "n_hist": len(dates)}
    prev = _SERIES.read_text("utf-8").strip().splitlines() if _SERIES.exists() else []
    if not prev or json.loads(prev[-1]).get("date") != today:
        with _SERIES.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")

    print(f"STABLECOIN-SUPPLY SCREEN | {len(dates)} aligned days")
    print(f"  current z20: {z[-1]:+.2f}   total supply ${sig[-1]:,.0f}")
    print(f"  IC {scr['ic']:+.4f} | same-period {scr['same_period_corr']:+.3f} "
          f"| residual IC {scr['residual_ic']:+.4f}")
    print(f"  timing Sharpe -- MOMENTUM {scr['sharpe_momentum']}  "
          f"REVERSAL {scr['sharpe_reversal']}")
    print(f"  VERDICT (Stage-A, zero promotion authority): {scr['verdict']}  "
          f"[momentum, direction=+1; SAME construct as stablecoin_flows supply field -- one "
          f"hypothesis, this is the formally-tracked version]")


if __name__ == "__main__":
    main()

```

### scripts/collector_monitor.py
```python
"""ZERO-TRUST COLLECTOR MONITOR (G3) -- assume every collector is lying until it proves otherwise.

THE FAILURE THIS EXISTS FOR: a collector that ERRORS is safe -- something notices. A collector that
silently returns ZEROS, or repeats yesterday's value, or quietly stops updating, is dangerous: the
desk reads a flat market, concludes "no signal", and either suppresses a true signal or fires a
false one. Nothing in the pipeline currently distinguishes "the market was flat" from "the sensor
died". That is the single most dangerous class of bug in an automated desk, and it is invisible to
every downstream statistical test -- the numbers all look fine.

FOUR CHECKS per tracked clock/artifact:
  1. STALENESS   -- is the file still being written? (dead cron / reaped process / auth outage)
  2. ROW RATE    -- did the append rate collapse vs its own history? (partial failure)
  3. FLATLINE    -- are the last N values identical? (the silent-zero / cached-response class)
  4. ZERO-FILL   -- is the newest value exactly 0 or null when history says otherwise?

Any tripped check emits a KILL signal naming the dependent axes, so a live sleeve can be halted
BEFORE it trades on a dead sensor. Zero promotion authority; it only ever says STOP, never GO.

Read-only, no keys, no LLM. Run from repo root on the daily cadence.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "collector_health.json"

# clock -> axes that would trade on it (halt these if the sensor is bad)
DEPENDENTS = {
    "kimchi_premium.jsonl": ["kimchi_premium"],
    "stablecoin_supply.jsonl": ["stablecoin_supply_momentum"],
    "cny_premium.jsonl": ["cny_premium"],
    "onchain_activity.jsonl": ["(retired axis -- input store only)"],
}
STALE_H = 36.0          # a daily collector silent for >36h is not "slow", it is dead
FLAT_N = 5              # identical values across this many rows = flatline
RATE_DROP = 0.5         # append rate below half its historical mean = partial failure


def _rows(p: Path) -> list[dict]:
    out = []
    for ln in p.read_text("utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if not r.get("_summary"):
            out.append(r)
    return out


def _numeric_field(rows: list[dict]) -> str | None:
    """Pick the payload field to sanity-check (first numeric that is not a date/count)."""
    skip = {"n_hist", "n_quotes", "date"}
    for k, v in (rows[-1] if rows else {}).items():
        if k not in skip and isinstance(v, (int, float)) and v is not None:
            return k
    return None


def main() -> None:
    now = datetime.now(tz=UTC)
    results, kills = [], []
    print("=== ZERO-TRUST COLLECTOR MONITOR ===")
    print("    a collector that ERRORS is safe; one that silently returns zeros is not.\n")
    print(f"  {'clock':<28}{'rows':>6}{'age_h':>8}{'status':>10}  detail")

    for fname, deps in DEPENDENTS.items():
        p = DATA / fname
        if not p.exists():
            print(f"  {fname:<28}{'-':>6}{'-':>8}{'MISSING':>10}  file absent")
            results.append({"clock": fname, "status": "MISSING", "dependents": deps})
            kills.append((fname, deps, "file absent"))
            continue
        rows = _rows(p)
        age = (now - datetime.fromtimestamp(p.stat().st_mtime, tz=UTC)).total_seconds() / 3600
        flags = []

        # 1. staleness
        if age > STALE_H:
            flags.append(f"STALE {age:.0f}h (>{STALE_H:.0f}h)")

        # 2. row rate vs own history
        dates = sorted({r.get("date") for r in rows if r.get("date")})
        if len(dates) >= 3:
            span = (datetime.fromisoformat(dates[-1]) - datetime.fromisoformat(dates[0])).days + 1
            expected = span
            if len(dates) < expected * RATE_DROP:
                flags.append(f"RATE-DROP {len(dates)}/{expected} expected days")

        # 3. flatline + 4. zero-fill on the payload field
        fld = _numeric_field(rows)
        if fld and len(rows) >= FLAT_N:
            vals = [r.get(fld) for r in rows[-FLAT_N:] if r.get(fld) is not None]
            if len(vals) == FLAT_N and len(set(vals)) == 1:
                flags.append(f"FLATLINE {fld}={vals[0]} x{FLAT_N}")
            if vals and vals[-1] == 0 and any(v != 0 for v in vals[:-1]):
                flags.append(f"ZERO-FILL {fld} went to 0")

        # null-payload check (cny_premium ships z20=null during warmup -- legitimate, but visible)
        nulls = sum(1 for r in rows if fld and r.get(fld) is None)
        status = "KILL" if flags else ("WARN" if nulls == len(rows) and rows else "OK")
        detail = "; ".join(flags) or (f"{fld}: all null (warmup?)" if status == "WARN"
                                      else f"{fld} healthy")
        print(f"  {fname:<28}{len(rows):>6}{age:>8.1f}{status:>10}  {detail}")
        results.append({"clock": fname, "rows": len(rows), "age_h": round(age, 1),
                        "status": status, "flags": flags, "dependents": deps})
        if flags:
            kills.append((fname, deps, "; ".join(flags)))

    print()
    if kills:
        print("  *** KILL SIGNALS -- halt these axes before they trade on a dead sensor ***")
        for fname, deps, why in kills:
            print(f"    {fname}: {why}")
            for d in deps:
                print(f"      -> HALT {d}")
    else:
        print("  no kill signals -- all monitored collectors passing zero-trust checks")

    OUT.write_text(json.dumps({"updated": now.isoformat(), "stale_hours": STALE_H,
                               "kills": [{"clock": k, "dependents": d, "why": w}
                                         for k, d, w in kills],
                               "collectors": results}, indent=1), "utf-8")
    print(f"\n  -> {OUT}")
    print("  This layer only ever says STOP. It has no authority to promote or resume anything.")


if __name__ == "__main__":
    main()

```

### scripts/coverage_audit.py
```python
"""COVERAGE AUDIT -- one honest number per surface. "Everything is covered" is a claim; this is a
measurement.

Six surfaces, each with a different denominator, because "coverage" means something different at
every layer and quoting the best one is how a desk fools itself.
"""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _j(p, d=None):
    try:
        return json.loads((ROOT / p).read_text("utf-8"))
    except Exception:  # blind-except intentional (BLE001)
        return d


rows = []

# 1 PANEL CODE COVERAGE
sh = _j("data/audit_shards.json", {})
if sh:
    rows.append(("panel: merit code reviewed", sh.get("union_coverage_pct", 0), 100.0,
                 f"{sh.get('tier1_files',0)+sh.get('tier2_files',0)} files; "
                 f"{sh.get('inert_withheld',0)} INERT withheld by design"))

# 2 DQS COLLECTOR COVERAGE -- how many data sources are health-scored at all?
dv = _j("data/data_vitals.json", {})
scored = {c["source"] for c in dv.get("collectors", [])}
all_data = {p.name for p in (ROOT / "data").glob("*.jsonl")}
extra = len([c for c in dv.get("collectors", []) if c["source"] not in all_data])
rows.append(("data: sources health-scored",
             len(scored) / max(len(all_data) + extra, 1) * 100, 100.0,
             f"{len(scored)} scored of {len(all_data)} jsonl + {extra} live sources"))

# 3 MEASUREMENT GATE COVERAGE
mg = _j("data/measurement_gate.json", {})
gated = set(mg.get("datasets", {}))
rows.append(("data: datasets gated", len(gated) / max(len(all_data), 1) * 100, 100.0,
             f"{len(gated)} gated of {len(all_data)} jsonl files"))

# 4 DEPENDENCY GRAPH COVERAGE
dg = _j("data/dependency_graph.json", {})
nodes = dg.get("nodes", [])
unmon = [n for n in nodes if n.get("state") == "UNMONITORED"]
rows.append(("data: graph nodes monitored",
             (len(nodes) - len(unmon)) / max(len(nodes), 1) * 100, 100.0,
             f"{len(unmon)} UNMONITORED of {len(nodes)} declared sources"))

# 5 CONSTRUCTION / FEATURE-SPACE COVERAGE  -- the real research frontier
fl = _j("data/feature_library.json", {})
props = fl.get("n_proposals", 0)
tested = 3
rows.append(("research: construction space tested",
             tested / max(props + tested, 1) * 100, 100.0,
             f"{tested} tested of {props + tested} enumerated cells"))

# 6 NORTH STAR -- alpha pipeline conversion
al = _j("data/alpha_lifecycle.json", {})
alphas = al.get("alphas", [])
deployed = sum(1 for a in alphas if a.get("state") in ("SMALL_CAPITAL", "SCALED", "MONITORED"))
rows.append(("alpha: reached capital", deployed / max(len(alphas), 1) * 100, 100.0,
             f"{deployed} deployed of {len(alphas)} tracked alphas"))

print("=== COVERAGE AUDIT -- one honest number per surface ===")
print("    different denominators; quoting the best one is how a desk fools itself\n")
print(f"  {'surface':<36}{'actual':>9}{'target':>9}   detail")
for name, act, tgt, detail in rows:
    flag = "" if act >= 99.5 else "   <-- GAP"
    print(f"  {name:<36}{act:>8.1f}%{tgt:>8.0f}%   {detail}{flag}")

full = [r for r in rows if r[1] >= 99.5]
print(f"\n  {len(full)}/{len(rows)} surfaces at 100%.")
print("  Anything below is a real gap, not a rounding artifact. 'Everything is covered' is")
print("  false unless every line above reads 100.")

```

### scripts/derive_walcl_clock.py
```python
"""WALCL reserve-impulse forward clock -- R0031, pre-registered 2026-07-31.

STAGE A EVIDENCE (data/fred_macro_screen.json, trial fred_macro::reserve_quantity_impulse::h1b):
IC +0.1106 on n=815 weekly obs, mechanism-consistent momentum sign (Sharpe 0.82), de-contamination
PASSED (residual IC +0.0964), verdict SCREEN-UNDERPOWERED -- the 4-week window sampled weekly
carries ~204 independent obs (t~1.6) against a min-detectable IC of 0.1816. The power wall cannot
be closed retroactively; the honest path is FORWARD ACCRUAL under the Two-Stage law. This clock
fills the Holm slot freed by the kimchi_premium retirement (cohort 11 -> 12, cap 12).

PRE-REGISTERED CONSTRUCTION (mirrors the screen exactly; changing any of it is a NEW trial):
  signal   = 4-week log change in WALCL (Fed H.4.1 balance sheet, weekly Wednesday as-of)
  lag      = +2 calendar days on every observation (Thursday 16:30 ET release -> usable from the
             Friday 00:00Z crypto close; same explicit-lag alignment the screen declared)
  z        = trailing 20-observation z-score of the impulse (inclusive rolling window, past-only)
  direction= +1 (momentum: long BTC when z > 0), target = BTCUSDT next-day close-to-close,
             position held constant between weekly releases (the daily axis-clock evaluation of a
             weekly-held signal IS the weekly-hold strategy; nw_tstat prices the autocorrelation)

The clock's first forward day is its registration day. This deriver NEVER back-writes dates --
forward evidence begins now, or it is not forward evidence.

Laws: L1.25a(b) (survivors hunted daily -- an empty slot with a non-empty candidate space is an
idleness defect), TWO-STAGE DISCOVERY (Stage A earns a clock, never a cent), L1.41 (build
standard). Reads data/fred_macro.json (written daily by collect_fred_macro.py); no network.

    python scripts/derive_walcl_clock.py
"""

from __future__ import annotations

import json
import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_ARCHIVE = _ROOT / "data" / "fred_macro.json"
_CLOCK = _ROOT / "data" / "walcl_impulse.jsonl"

#: Pre-registered constants -- constants for the life of the clock (a second window is a second
#: trial and raises VARIANTS_TRIED at the screen, never a silent edit here).
_IMPULSE_WEEKS = 4
_ZWIN = 20
_RELEASE_LAG_DAYS = 2
#: Refuse to emit a z until the window is genuinely full: a z against a part-window is a
#: different (unregistered) construction.
_MIN_OBS = _IMPULSE_WEEKS + _ZWIN


def _series() -> list[tuple[str, float]]:
    """WALCL (date, value) rows from the FRED archive, oldest first.

    Refusal path (L1.41): a missing/unreadable/short archive returns [] and the caller exits
    non-zero saying so -- this clock must never fabricate a row from absent input.
    """
    try:
        doc = json.loads(_ARCHIVE.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = doc.get("series", {}).get("WALCL", [])
    out = [(str(d), float(v)) for d, v in rows if v]
    out.sort()
    return out


def signal_for(today: str, rows: list[tuple[str, float]]) -> dict | None:
    """The pre-registered z for date `today`, from observations AVAILABLE by then.

    Availability = as-of date + _RELEASE_LAG_DAYS. Returns None when the usable history is
    shorter than _MIN_OBS (refusal, not zero -- a fabricated 0.0 would be a position).
    """
    avail = [(d, v) for d, v in rows
             if (datetime.fromisoformat(d) + timedelta(days=_RELEASE_LAG_DAYS)).date().isoformat()
             <= today]
    if len(avail) < _MIN_OBS:
        return None
    imp = [math.log(avail[i][1]) - math.log(avail[i - _IMPULSE_WEEKS][1])
           for i in range(_IMPULSE_WEEKS, len(avail))]
    win = imp[-_ZWIN:]
    mean = sum(win) / len(win)
    var = sum((x - mean) ** 2 for x in win) / len(win)
    sd = math.sqrt(var)
    if sd < 1e-12:
        return None                # degenerate window (incl. float-noise flat): refuse, loudly
    return {"date": today, "z20": round((imp[-1] - mean) / sd, 4),
            "asof": avail[-1][0], "impulse": round(imp[-1], 6)}


def main() -> int:
    _law_guard()
    today = datetime.now(tz=UTC).date().isoformat()
    rows = _series()
    if not rows:
        print(f"walcl-clock: CANNOT MEASURE -- {_ARCHIVE} missing/unreadable/empty; no row written")
        return 1
    sig = signal_for(today, rows)
    if sig is None:
        print(f"walcl-clock: CANNOT MEASURE -- {len(rows)} obs available, need {_MIN_OBS} "
              "with release lag; no row written")
        return 1
    if _CLOCK.exists():
        for line in _CLOCK.read_text("utf-8").splitlines():
            try:
                if json.loads(line).get("date") == today:
                    print(f"walcl-clock: {today} already recorded (idempotent) -- z {sig['z20']}")
                    return 0
            except json.JSONDecodeError:
                continue
    with _CLOCK.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(sig) + "\n")
    print(f"walcl-clock: {today} z {sig['z20']} (asof {sig['asof']}, "
          f"impulse {sig['impulse']}) -> {_CLOCK.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts/experiment_registry.py
```python
"""EXPERIMENT REGISTRY -- the write path, not another schema.

THE MEASURED FINDING THAT MOTIVATES THIS. The principal's review asks for an Experiment Registry,
Alpha Lineage, Reproducibility Layer, Research Memory and a Decision Log. This desk ALREADY HAS
those tables. I counted the rows:

    data/alpha_registry.sqlite   alpha_registry     0 rows
                                 trials_ledger      0 rows
                                 research_runs      0 rows
                                 snapshots          0 rows
    data/sor_research.sqlite     (same schema)      0 rows
    ... 8 sqlite files, every research table EMPTY
    data/panel_scorecard.json    13 providers, 0 scored, hit_rate null, stale since 2026-07-17

Meanwhile 43 commits landed on 2026-07-27 alone, each one an experiment, NONE of them recorded.

So the bottleneck is NOT missing architecture. It is that nothing WRITES. Adding the twenty-odd
new subsystems in the review as designed would produce twenty-odd more empty tables and one more
layer of things to maintain. The intervention with actual leverage is a harvester that turns the
evidence the desk already emits -- git history, artifacts on disk, the graveyard -- into permanent
experiment objects, automatically, with no discipline required from whoever runs the experiment.
Discipline-dependent logging is what produced the zeros.

WHAT AN EXPERIMENT OBJECT IS HERE (reproducibility is the point):
    id            stable, derived from commit sha -- survives rewrites of this file
    commit        the exact tree that produced the result. `git show <sha>` reproduces it.
    artifacts     which data/*.json it wrote, and whether that file STILL EXISTS
    decision      SURVIVED / REFUTED / INCONCLUSIVE / FIX / INFRA, parsed from the commit record
    mechanism     mapped through the mechanism_board taxonomy, so lineage is at mechanism level
    failure_mode  the autopsy taxonomy where a cause is stated

HONESTY RAIL: anything this cannot classify is reported as UNCLASSIFIED with a count, not guessed
into a bucket. A registry that silently invents decisions is worse than no registry, because the
scoreboard downstream would then allocate research capital against fiction.

Read-only w.r.t. the desk. No LLM, no keys. Run from repo root.
"""
from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/experiment_registry.jsonl"
SUMMARY = ROOT / "data/experiment_registry.json"

# decision parsing -- ordered, first match wins. Tokens taken from THIS desk's actual commit
# vocabulary (I read 43 real subjects), not from a generic list.
DECISION = [
    ("REFUTED", ("refuted", "coincident", "0/3 pass", "0/", "zero predictive", "fails", "failed",
                 "dead)", "-- dead", "exhausted", "no edge", "does not persist", "do not persist",
                 "premise fails", "closed", "kill", "artifact", "not leading")),
    ("SURVIVED", ("survives", "survived", "replicates out-of-sample", "confirmed", "ic +",
                  "holds out-of-sample", "adds value")),
    ("INCONCLUSIVE", ("inconclusive", "underpowered", "blocked", "402", "needs ", "unproven",
                      "likely a synchronisation artifact")),
    ("FIX", ("fix applied", "fixed", "root cause", "correction", "resolved", "restarted",
             "incident", "p0 ")),
]
INFRA_HINT = ("built", "wire", "doctrine", "engine", "scanner", "registry", "library", "digest",
              "snapshot", "monitor", "guard", "simulator", "author", "cli")

MECHANISMS = {
    "M_ATTENTION_DELAY": ("attention", "sentiment", "social", "wikipedia", "search", "narrative"),
    "M_FUNDAMENTAL_PROXY": ("developer", "github", "tvl", "onchain", "on-chain", "unlock"),
    "M_SKILL_PERSISTENCE": ("trader", "elite", "copytrad", "skill", "leaderboard", "whale"),
    "M_STRUCTURAL_BARRIER": ("kimchi", "premium", "structural spread", "cme", "venue", "basis",
                             "collateral", "cross-venue"),
    "M_FORCED_DELEVERAGE": ("funding", "open interest", "oi_", "carry", "liquidation", "leverage",
                            "positioning", "long short"),
    "M_LIQUIDITY_WITHDRAWAL": ("microstructure", "order book", "orderbook", "depth", "spread",
                               "moat", "liquidity", "cost model"),
    "M_FLOW_PRESSURE": ("stablecoin", "flow", "bridge", "reserve"),
    "M_PRICE_PATTERN": ("momentum", "reversal", "breakout", "trend", "horizon discovery",
                        "reflexivity"),
}
FAILURE_MODES = {
    "A_NO_MECHANISM": ("no mechanism", "no causal", "premise fails"),
    "B_WRONG_MEASUREMENT": ("unit error", "scope", "construction", "parser", "misalign"),
    "C_WRONG_TIMING": ("coincident", "horizon", "lead", "same-period", "contemporaneous",
                       "not leading", "half-life"),
    "D_ALREADY_ARBITRAGED": ("arbitraged", "crowded", "competed"),
    "E_DATA_QUALITY": ("artifact", "synchronisation", "lookahead", "stale", "implausible"),
    "F_REGIME_DEPENDENT": ("regime",),
    "G_TOO_EXPENSIVE": ("costs", "cost model", "round-trip", "bps", "survive costs", "slippage"),
    "H_OVERFIT": ("overfit", "underpowered", "n=", "power", "dsr"),
}


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True,
                              check=False, timeout=90).stdout
    except Exception:  # blind-except intentional (BLE001)
        return ""


def _tag(text: str, table: dict[str, Any]) -> list[str]:
    t = text.lower()
    return [k for k, kws in table.items() if any(w in t for w in kws)]


def _decide(text: str) -> str:
    t = text.lower()
    for label, kws in DECISION:
        if any(k in t for k in kws):
            return label
    if any(k in t for k in INFRA_HINT):
        return "INFRA"
    return "UNCLASSIFIED"


def harvest(days: int = 45) -> list[dict[str, Any]]:
    """One record per commit. The commit IS the reproducible unit -- it pins code + params."""
    raw = _git("log", f"--since={days} days ago", "--name-only",
               "--pretty=format:%x00%H%x1f%an%x1f%aI%x1f%s%x1f%b%x02")
    rows = []
    for chunk in raw.split("\x00"):
        if "\x02" not in chunk:
            continue
        head, files_blob = chunk.split("\x02", 1)
        parts = head.split("\x1f")
        if len(parts) < 4:
            continue
        sha, author, iso, subject = parts[0], parts[1], parts[2], parts[3]
        body = parts[4] if len(parts) > 4 else ""
        files = [f.strip() for f in files_blob.splitlines() if f.strip()]
        blob = f"{subject}\n{body}"
        arts = sorted({f for f in files if f.startswith(("data/", "docs/"))})
        code = sorted({f for f in files if f.startswith("scripts/") or f.startswith("libs/")})
        rows.append({
            "id": f"E-{sha[:10]}",
            "commit": sha,
            "date": iso[:10],
            "author": author,
            "title": subject[:180],
            "decision": _decide(blob),
            # SUBJECT ONLY. First pass tagged subject+body+code-paths and produced 2.4 mechanisms
            # per experiment with survival flat at 6-11% across all nine -- the signature of
            # keyword BLEED, not of nine equally productive mechanisms. A file named
            # scripts/run_cost_model.py dragged "cost model" into M_LIQUIDITY_WITHDRAWAL on every
            # commit that touched it. Flat rates across every category mean the tagger is not
            # discriminating, and the allocator downstream would have spent research capital on
            # that noise. The subject line is the one field that states what was actually tested.
            "mechanisms": _tag(subject, MECHANISMS) or ["M_UNMAPPED"],
            "failure_modes": _tag(blob, FAILURE_MODES) if _decide(blob) == "REFUTED" else [],
            "code": code[:8],
            "artifacts": arts[:8],
            # reproducibility: does the thing it wrote still exist in the working tree?
            "artifacts_present": sum(1 for a in arts if (ROOT / a).exists()),
            "artifacts_declared": len(arts),
        })
    return rows


def main() -> None:
    print("=== EXPERIMENT REGISTRY -- harvested, not hand-logged ===")
    print("    the registries this desk already owns hold 0 rows; discipline-based logging")
    print("    is what produced the zeros, so this reads evidence the desk emits anyway\n")
    rows = harvest()
    if not rows:
        raise SystemExit("no git history harvested -- refusing to write an empty registry")

    with OUT.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    dec: dict[str, int] = {}
    for r in rows:
        dec[r["decision"]] = dec.get(r["decision"], 0) + 1
    print(f"  {len(rows)} experiments registered over 45 days\n")
    print(f"  {'decision':<16}{'n':>5}   share")
    for k, v in sorted(dec.items(), key=lambda kv: -kv[1]):
        print(f"  {k:<16}{v:>5}   {v/len(rows)*100:4.0f}%")

    tested = [r for r in rows if r["decision"] in ("REFUTED", "SURVIVED", "INCONCLUSIVE")]
    surv = [r for r in rows if r["decision"] == "SURVIVED"]
    if tested:
        print(f"\n  SURVIVAL RATE  {len(surv)}/{len(tested)} = {len(surv)/len(tested)*100:.1f}% "
              f"of decided experiments")

    mech: dict[str, dict[str, int]] = {}
    for r in tested:
        for m in r["mechanisms"]:
            d = mech.setdefault(m, {"tested": 0, "survived": 0})
            d["tested"] += 1
            d["survived"] += r["decision"] == "SURVIVED"
    tags_per = sum(len(r["mechanisms"]) for r in tested) / max(len(tested), 1)
    print("\n  MECHANISM SURVIVAL (this is the input research allocation should use):")
    print(f"  {'mechanism':<26}{'tested':>7}{'survived':>10}{'rate':>8}")
    for m, d in sorted(mech.items(), key=lambda kv: -kv[1]["tested"]):
        rate = d["survived"] / d["tested"] * 100 if d["tested"] else 0.0
        flag = "  <-- n too small to rank" if d["tested"] < 8 else ""
        print(f"  {m:<26}{d['tested']:>7}{d['survived']:>10}{rate:>7.0f}%{flag}")
    print(f"\n  tag density {tags_per:.2f} mechanisms/experiment "
          f"({'OK -- tags discriminate' if tags_per < 1.4 else 'HIGH -- suspect keyword bleed'})")

    fm: dict[str, int] = {}
    for r in rows:
        for f in r["failure_modes"]:
            fm[f] = fm.get(f, 0) + 1
    if fm:
        print("\n  FAILURE MODES on refuted experiments:")
        for k, v in sorted(fm.items(), key=lambda kv: -kv[1]):
            print(f"    {k:<24}{v:>4}")

    declared = sum(r["artifacts_declared"] for r in rows)
    present = sum(r["artifacts_present"] for r in rows)
    unc = dec.get("UNCLASSIFIED", 0)
    print(f"\n  REPRODUCIBILITY: {present}/{declared} declared artifacts still present "
          f"({present/max(declared,1)*100:.0f}%); every row pins a commit sha, so "
          f"`git show <sha>` reproduces the code that produced it.")
    print(f"  UNCLASSIFIED: {unc} commits ({unc/len(rows)*100:.0f}%) state no decision this can")
    print("  parse. That is a real defect in commit discipline, reported rather than guessed --")
    print("  a registry that invents decisions would corrupt every allocation downstream.")

    SUMMARY.write_text(json.dumps({
        "updated": datetime.now(tz=UTC).isoformat(), "n": len(rows), "decisions": dec,
        "survival_rate": round(len(surv) / len(tested), 4) if tested else None,
        "mechanism_survival": mech, "failure_modes": fm,
        "artifacts_present": present, "artifacts_declared": declared,
        "unclassified": unc}, indent=1), "utf-8")
    print(f"\n  -> {OUT}\n  -> {SUMMARY}")


if __name__ == "__main__":
    main()

```

### scripts/finalize_axis_screens.py
```python
"""Post-process the 2026-07-26 axis screens: correct a harness annualization defect, attach
IC t-statistics, apply the multiplicity bar, and write the axis-level verdicts.

WHY THIS EXISTS -- HARNESS DEFECT FOUND DURING THIS CAMPAIGN
-----------------------------------------------------------
`libs/research/axis_screen.py::_sh` computes

    rr = np.sign(sig) * fv;  return rr.mean() / rr.std() * np.sqrt(365)

The sqrt(365) is HARDCODED, i.e. it assumes every element of `target_ret` is a ONE-DAY return.
But the documented way to test the 5d/20d horizons the mandate requires is to hand the harness
NON-OVERLAPPING DOWNSAMPLED periods (this is exactly what the desk's own
scripts/screen_cme_basis.py does). When each element is a k-day return there are 365/k periods
per year, so the correct factor is sqrt(365/k) -- and the reported Sharpe is inflated by sqrt(k):
~2.24x at 5d and ~4.47x at 20d. Verified by simulation against an analytically-known Sharpe
(inflation measured 1.51x at 5d and 3.99x at 20d, converging on sqrt(k) as noise shrinks).

TWO CONSEQUENCES, BOTH BAD, BOTH AFFECTING WORK ALREADY ON FILE:
  1. The sharpe_min=0.5 promotion floor is effectively 0.22 at 5d and 0.11 at 20d, so downsampled
     screens are systematically OVER-promoted to SCREEN-INTERESTING.
  2. The sharpe_ceiling=6.0 SUSPECT-LOOKAHEAD rail -- the safety rail that caught the bithumb
     IC-0.72/Sharpe-10 fake -- is effectively 13.4 at 5d and 26.8 at 20d. THE LOOKAHEAD RAIL IS
     PARTLY BLIND AT LONG HORIZONS. That is the more dangerous of the two.
  3. Already on file: reports/axis_screens/cme_basis_20260724.json trial `cme_basis_ann->btc_5d`
     is recorded SCREEN-INTERESTING at Sharpe 1.74; corrected it is 0.78.

The audited harness is NOT edited here -- changing it is a desk decision requiring its own review.
The correction is applied transparently at the reporting layer and flagged for the CRO.

MULTIPLICITY: the desk's own history (420 price-family hypotheses, 0 survivors) is the reason a
nominal pass means nothing without a multiplicity bar. Each trial's IC t-stat is compared against
a Bonferroni bar at alpha=0.05 both per-axis and campaign-wide across all 37 screened trials.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "reports" / "axis_screens"
SHARPE_MIN, IC_MIN = 0.5, 0.03


def _step(name: str) -> int:
    m = re.search(r"_(\d+)d\b", name.replace("->", "_"))
    if not m:
        return 1
    v = int(m.group(1))
    return v if v in (1, 5, 20) else 1


def _norm_ppf(p: float) -> float:
    """Acklam inverse-normal, good to ~1e-9 -- avoids a scipy dependency."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    pl = 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        return ((((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])
                / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1))
    if p > 1 - pl:
        q = math.sqrt(-2 * math.log(1 - p))
        return (-(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])
                / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1))
    q, r = p - 0.5, (p - 0.5) ** 2
    return ((((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q
            / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1))


def _bar(m: int) -> float:
    return round(abs(_norm_ppf(0.05 / (2 * m))), 2)


AXES = ("mining", "wikipedia", "fx")
TOTAL_TRIALS = 37  # 12 mining + 13 wikipedia + 12 fx (+ etf_flows not screenable)
CAMPAIGN_BAR = _bar(TOTAL_TRIALS)

VERDICTS = {
    "mining": (
        "NO SURVIVOR. 12 pre-declared trials, 3 printed a nominal SCREEN-INTERESTING and none "
        "survives correction. (a) The single best, hash_ribbon->btc_5d (IC +0.093), has the "
        "OPPOSITE SIGN to the pre-registered mechanism: capitulation was predicted to be FOLLOWED "
        "by higher returns (negative IC), and a positive IC says rising hashrate leads rising "
        "price. Per the graveyard's xsec_lowvol rule the sign is NOT flipped and re-sold as "
        "momentum. (b) Its sign also INVERTS between adjacent horizons (+0.093 at 5d, -0.113 at "
        "20d) -- the signature of noise, not structure. (c) Corrected Sharpe 0.83, and its IC "
        "t=2.02 fails both the per-axis (2.87) and campaign (3.20) bars. (d) difficulty_5d and "
        "hashprice_usd_5d fall below the 0.5 Sharpe floor once the annualization is corrected. "
        "ONE GENUINE POSITIVE FINDING: the ribbon is NOT lagged price momentum -- the raw ribbon "
        "level correlates +0.30 with trailing 60d BTC return, but the 20d Z-SCORE the harness "
        "actually screens correlates only +0.01..+0.04, so the z-scoring strips the momentum "
        "component. The construction is genuinely orthogonal to the trend book; it simply has no "
        "edge. The pre-registered contamination prediction for hashprice_usd was also CONFIRMED "
        "(same-period corr 0.157 vs 0.007 for the BTC-denominated twin), reproducing the cm_mvrv "
        "price-numerator lesson on a new dataset."),
    "wikipedia": (
        "NO SURVIVOR -- and the result CLOSES THE TWO ESCAPE HATCHES the graveyarded "
        "multilingual_wikipedia_attention kill left open. That kill kept the door ajar for a "
        "different OBJECT and a different TARGET; both are now tested and both fail. (a) Gateway/"
        "onboarding attention (Coinbase+Binance+Cryptocurrency = purchase intent, which should "
        "LEAD deposits, unlike news-reading which LAGS the print) is weak at every horizon: the "
        "5d nominal pass corrects to Sharpe 0.39, below the floor. (b) Cross-sectional relative "
        "attention as an ASSET-SELECTION signal fails on sign stability: ETH flips -0.042 (1d) -> "
        "+0.052 (5d) -> +0.011 (lagged); SOL is -0.001 (1d) but +0.055 LAGGED, i.e. STRONGER with "
        "a stale signal, which is mechanically incoherent for an attention signal that should "
        "decay in hours and is a clean noise tell. DOGE 1d carries same-period corr 0.18, close to "
        "the 0.20 contamination bar -- meme attention co-moves with meme price, exactly the "
        "'attention co-moves with, does not lead' finding of the original kill. Nothing clears the "
        "per-axis (2.87) or campaign (3.20) multiplicity bar. Extends the existing kill from "
        "'not a daily timing signal' to 'not an asset-selection signal either'."),
    "fx": (
        "NO SURVIVOR, and the axis AS INGESTED CANNOT TEST ITS OWN MECHANISM. The fx lake holds 57 "
        "crosses and not one high-barrier currency (no KRW, CNY/CNH, BRL, ARS, NGN, VND, EGP, "
        "INR); EURRUB terminates 2022-02-28 on the sanctions cut. The graveyard's era-evidence "
        "entry states the governing law -- premium magnitude tracks BARRIER HEIGHT -- so the only "
        "currencies available are precisely the ones the mechanism predicts should NOT pay. That "
        "is a data-coverage verdict, not an economic one. Of 12 trials: the EM debasement basket "
        "is weak at 1d/20d and its 5d nominal pass corrects to Sharpe 0.32; synthetic DXY is weak "
        "everywhere; TRY-only is weak, independently reproducing the graveyard's finding that "
        "Turkey arbs global too tightly. TWO DIAGNOSTICS EARNED THEIR KEEP. (1) DENOMINATION "
        "CONTROL: the same signal scores HIGHER against BTC priced in TRY (IC +0.043) than against "
        "BTC/USDT (+0.032) -- because BTC-in-TRY return mechanically CONTAINS the next TRY move, "
        "so that build is partly FX autocorrelation, not a crypto edge. This is why both "
        "denominations must be logged. (2) SHIFT TEST: at +1d -- deliberately feeding the signal "
        "from the FUTURE -- |IC| jumps 5x to 0.073, while at -1d it is flat at 0.015. A "
        "relationship that is far stronger when you peek forward is CONTEMPORANEOUS, not leading: "
        "EM FX and BTC both load on the same global risk factor and the 20d depreciation is a "
        "LAGGING read of risk-off that already happened. There is no lead to trade."),
}
NEXT = {
    "mining": ("Do NOT clock and do NOT fish further hashrate variants -- 12 trials is already the "
               "multiplicity budget for this axis. The mechanism is not refuted, only the daily/"
               "weekly public aggregates are: hashrate and difficulty are network-wide averages "
               "that cannot see WHICH cohort is capitulating. "
               "The honest escalation, pre-registered "
               "and on its own clock slot, is miner TREASURY OUTFLOWS (known miner wallet -> "
               "exchange transfers), which observes the forced selling directly rather than "
               "inferring it from a Poisson-noisy block-count estimate."),
    "wikipedia": ("Do NOT clock. Recommend the graveyard entry for "
                  "multilingual_wikipedia_attention "
                  "be AMENDED to record that the object arm (gateway/onboarding pages) and the "
                  "target arm (cross-sectional asset selection) have now also been tested and "
                  "failed, so the category is closed on all three arms and no future agent spends "
                  "budget re-opening it."),
    "fx": ("Do NOT clock. The productive action is INGESTION, not more screening: this axis "
           "deserves its high prior only if the lake carries high-barrier currencies. Request "
           "USDKRW, USDCNY/CNH, USDBRL, USDARS, USDNGN, USDVND before any further fx screening. "
           "Re-screening the majors would be breadth-mining the currencies the mechanism already "
           "predicts pay nothing. "
           "RUB is re-testable as a data/infra kill if the feed is restored."),
}


def main() -> None:
    summary = []
    for axis in AXES:
        p = OUT / f"{axis}.json"
        rep = json.loads(p.read_text("utf-8"))
        screened = [t for t in rep["trials"] if "verdict" in t and t.get("n")]
        axis_bar = _bar(len(screened))
        for t in screened:
            k = _step(t["name"])
            best = max(abs(t.get("sharpe_momentum", 0)), abs(t.get("sharpe_reversal", 0)))
            corr = round(best / math.sqrt(k), 2)
            t["period_days"] = k
            t["sharpe_best_reported"] = best
            t["sharpe_best_corrected"] = corr
            t["sharpe_correction_note"] = (
                "harness hardcodes sqrt(365); for k-day periods the correct factor is "
                f"sqrt(365/{k}), so reported Sharpe is inflated by "
                f"sqrt({k})={round(math.sqrt(k),2)}x"
                if k > 1 else "1d periods -- harness annualization correct, no adjustment")
            tstat = round(abs(t.get("ic", 0)) * math.sqrt(max(t["n"] - 2, 1)), 2)
            t["ic_t_stat"] = tstat
            t["clears_axis_multiplicity_bar"] = bool(tstat > axis_bar)
            t["clears_campaign_multiplicity_bar"] = bool(tstat > CAMPAIGN_BAR)
            # Controls and future-peeking diagnostics can NEVER be candidates, however they score.
            # SHIFT_*_plus1d feeds the signal from the FUTURE; a strong score there is evidence of
            # contemporaneous co-movement (an ARTIFACT), which rule 8 says is never an edge.
            nm = t["name"]
            is_ctrl = ("DENOM-CONTROL" in nm or "LOOKAHEAD-CONTROL" in nm
                       or "SHIFT_" in nm or "_LAG1d" in nm)
            if is_ctrl:
                kind = ("future-peeking shift diagnostic" if "plus1d" in nm else
                        "denomination artifact control" if "DENOM-CONTROL" in nm else
                        "look-ahead control" if "LOOKAHEAD-CONTROL" in nm else
                        "conservative-lag robustness check")
                t["is_candidate"] = False
                t["verdict_adjusted"] = (
                    f"NOT-A-CANDIDATE ({kind}; raw harness verdict {t['verdict']}). "
                    "Diagnostics are read for what they reveal, never promoted.")
            elif t["verdict"] == "SCREEN-INTERESTING":
                t["is_candidate"] = True
                if corr < SHARPE_MIN:
                    t["verdict_adjusted"] = ("SCREEN-WEAK (Sharpe fails the 0.5 floor once the "
                                             "harness annualization defect is corrected)")
                elif not t["clears_campaign_multiplicity_bar"]:
                    t["verdict_adjusted"] = (f"SCREEN-WEAK (IC t={tstat} fails the multiplicity "
                                             f"bar: axis {axis_bar}, campaign {CAMPAIGN_BAR})")
                else:
                    t["verdict_adjusted"] = "SCREEN-INTERESTING (survives correction+multiplicity)"
            else:
                t["is_candidate"] = True
                t["verdict_adjusted"] = t["verdict"]
        rep["harness_defect_found"] = {
            "location": "libs/research/axis_screen.py::_sh (line ~69)",
            "defect": "np.sqrt(365) hardcoded; assumes 1-day target periods",
            "impact": ("downsampled 5d/20d screens report Sharpe inflated by sqrt(k) (2.24x / "
                       "4.47x). Promotion floor effectively 0.22/0.11 and -- more dangerous -- the "
                       "SUSPECT-LOOKAHEAD ceiling of 6.0 becomes 13.4/26.8, so the rail that "
                       "caught bithumb is partly blind at long horizons."),
            "also_affects": "reports/axis_screens/cme_basis_20260724.json (5d Sharpe 1.74 -> 0.78)",
            "action": "NOT patched here -- harness is audited; flagged for CRO decision.",
        }
        rep["multiplicity"] = {"axis_trials": len(screened), "axis_bonferroni_t": axis_bar,
                               "campaign_trials": TOTAL_TRIALS,
                               "campaign_bonferroni_t": CAMPAIGN_BAR}
        rep["verdict"] = VERDICTS[axis]
        rep["forward_clock"] = (
            "NO -- no construction survived; Stage A has zero promotion authority")
        rep["next_step"] = NEXT[axis]
        p.write_text(json.dumps(rep, indent=1, default=str), "utf-8")

        surv = [t for t in screened if t["verdict_adjusted"].startswith("SCREEN-INTERESTING")]
        summary.append((axis, len(screened), len(surv)))
        print(f"\n=== {axis}: {len(screened)} trials, {len(surv)} survive correction+multiplicity "
              f"(axis bar t>{axis_bar}, campaign t>{CAMPAIGN_BAR}) ===")
        for t in sorted(screened, key=lambda x: -abs(x.get("ic", 0)))[:5]:
            print(f"  {t['name']:46s} IC={t['ic']:+.4f} t={t['ic_t_stat']:.2f} "
                  f"Sh {t['sharpe_best_reported']:.2f}->{t['sharpe_best_corrected']:.2f}  "
                  f"{t['verdict_adjusted'][:58]}")
    print("\n", summary)


if __name__ == "__main__":
    main()

```

### scripts/mechanism_board.py
```python
"""PHASE A -- Mechanism Graveyard + Hypothesis Portfolio + Mechanism Review Board.

Built as ONE module because they are one system, not three: the mechanism taxonomy produces the
verdicts, the verdicts drive portfolio correlation, and the review board enforces both at the gate.

WHY MECHANISM LEVEL BEATS CONCEPT LEVEL (the principal's key point):
    concept view:   Twitter / Google Trends / Wikipedia / Reddit  = 4 different failed datasets
    mechanism view: ATTENTION -> information arrives AFTER sophisticated participants -> 1 dead
                    mechanism, and every future variant inherits the evidence
Concept archaeology stops "social attention momentum" impersonating "Twitter sentiment". Mechanism
archaeology stops the whole family -- including variants nobody has worded yet. It is the
difference between blocking a phrase and blocking a reason.

THE THREE PARTS:
 1 MECHANISM GRAVEYARD -- maps every graveyard entry to its ECONOMIC MECHANISM (who is forced to
   act, and why the edge could exist), then aggregates verdicts per mechanism.
 2 PORTFOLIO CONSTRUCTION -- ranking by ERV alone concentrates the book: today's top-5 by ERV were
   ALL liquidity-stress variants, i.e. ONE BET WEARING FIVE HATS. This applies a correlation
   penalty so the second liquidity idea is worth less than the first.
 3 MECHANISM REVIEW BOARD -- four questions every hypothesis must answer BEFORE consuming a slot:
   why should this exist / who is FORCED to trade / why is it not already arbitraged / what kills
   it. Anything failing is rejected pre-test. Cheap gate, and 64% of this desk's failures were
   measurement or timing rather than alpha -- exactly what a pre-test gate can catch.

Read-only. No LLM, no keys. Run from repo root.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
GRAVE = ROOT / "docs/graveyard.md"
ERV = ROOT / "data/research_erv.json"
AUTOPSY = ROOT / "data/research_autopsy.json"
OUT = ROOT / "data/mechanism_board.json"

# ECONOMIC MECHANISM taxonomy -- "who is forced to act, and why can the edge persist?"
# Deliberately NOT a dataset taxonomy. Many concepts collapse into one mechanism.
MECHANISMS = {
    "M_ATTENTION_DELAY": {
        "story": "attention/information reaches us AFTER sophisticated participants have priced it",
        "kws": ("attention", "sentiment", "social", "twitter", "wikipedia", "search", "trend",
                "narrative", "mention", "reddit", "influencer", "hype", "pageview"),
    },
    "M_FUNDAMENTAL_PROXY": {
        "story": "a fundamental (developer effort, usage, revenue) is assumed to lead valuation",
        "kws": ("developer", "github", "commit", "contributor", "tvl", "revenue", "usage",
                "active address", "transaction count", "adoption", "release"),
    },
    "M_SKILL_PERSISTENCE": {
        "story": "some participants are skilled and their past performance predicts future",
        "kws": ("trader", "elite", "copytrad", "leaderboard", "skill", "whale", "smart money",
                "persistence", "retention"),
    },
    "M_STRUCTURAL_BARRIER": {
        "story": "a HARD barrier (capital control, licence, settlement, collateral) stops "
                 "convergence -- the only mechanism family with a live survivor on this desk",
        "kws": ("capital control", "kimchi", "cny", "premium", "regulat", "licence", "license",
                "segment", "barrier", "peg", "redemption", "queue", "cross-venue"),
    },
    "M_FORCED_DELEVERAGE": {
        "story": "leveraged participants are FORCED to unwind (margin, liquidation, funding cost)",
        "kws": ("funding", "open interest", "leverage", "liquidation", "margin", "crowding",
                "positioning", "long short", "basis", "carry", "squeeze"),
    },
    "M_LIQUIDITY_WITHDRAWAL": {
        "story": "liquidity providers withdraw when inventory risk binds, so price impact jumps",
        "kws": ("depth", "spread", "order book", "orderbook", "market maker", "liquidity",
                "imbalance", "slippage", "replenish", "fragility", "microstructure"),
    },
    "M_FLOW_PRESSURE": {
        "story": "observable capital movement precedes the price impact of that capital",
        "kws": ("flow", "netflow", "inflow", "outflow", "stablecoin", "bridge", "exchange "
                "reserve", "mint", "supply"),
    },
    "M_PRICE_PATTERN": {
        "story": "price history alone predicts price -- no participant story at all",
        "kws": ("momentum", "reversal", "breakout", "rsi", "macd", "moving average", "kama",
                "squeeze", "donchian", "indicator", "lowvol", "trend"),
    },
}

# the four questions -- a hypothesis that cannot answer these should not consume a slot
BOARD = [
    ("why_exists", "Why should this edge exist at all?", ("because", "mechanism", "due to",
                                                          "driven by", "caused")),
    ("who_forced", "WHO is forced to trade against their own interest?",
     ("forced", "must", "liquidat", "margin", "redemption", "mandate", "rebalanc", "cannot",
      "obliged", "required")),
    ("why_not_arbed", "Why has this not already been arbitraged away?",
     ("barrier", "control", "licence", "license", "constraint", "cost", "capacity", "latency",
      "illiquid", "segment", "regulat", "queue", "friction")),
    ("kill_condition", "What observation kills it?", ("kill", "if ic", "t<", "below", "fails",
                                                      "reject if", "abandon")),
]


def mech_of(text: str) -> list[str]:
    t = text.lower()
    return [m for m, d in MECHANISMS.items() if any(k in t for k in d["kws"])]


def main() -> None:
    # ---------- 1. MECHANISM GRAVEYARD -------------------------------------------------
    rows = []
    for ln in GRAVE.read_text("utf-8").splitlines() if GRAVE.exists() else []:
        if not ln.startswith("|") or set(ln) <= set("|- "):
            continue
        c = [x.strip() for x in ln.strip("|").split("|")]
        if len(c) < 3 or c[0].lower() in ("name", "signal", "strategy"):
            continue
        rows.append({"name": c[0][:80], "blob": " ".join(c), "mechs": mech_of(" ".join(c))})

    tally: dict[str, int] = {}
    for r in rows:
        for m in r["mechs"] or ["M_UNMAPPED"]:
            tally[m] = tally.get(m, 0) + 1

    # a mechanism with many deaths and no survivor is a FAMILY KILL
    LIVE = {"M_STRUCTURAL_BARRIER", "M_FORCED_DELEVERAGE"}      # kimchi/cny, funding persistence
    OPEN = {"M_LIQUIDITY_WITHDRAWAL"}                            # moat, untested
    print("=== 1. MECHANISM-LEVEL GRAVEYARD ===")
    print("    concept archaeology blocks a PHRASE; mechanism archaeology blocks a REASON\n")
    print(f"  {'mechanism':<26}{'deaths':>7}  verdict / economic story")
    verdicts = {}
    for m, n in sorted(tally.items(), key=lambda kv: -kv[1]):
        if m == "M_UNMAPPED":
            v = "UNMAPPED"
        elif m in LIVE:
            v = "ALIVE"
        elif m in OPEN:
            v = "UNTESTED"
        elif n >= 5:
            v = "FAMILY KILL"
        else:
            v = "WEAK"
        verdicts[m] = v
        story = MECHANISMS.get(m, {}).get("story", "-")
        print(f"  {m:<26}{n:>7}  {v:<12} {story[:74]}")

    dead_fams = [m for m, v in verdicts.items() if v == "FAMILY KILL"]
    print(f"\n  FAMILY KILLS: {dead_fams}")
    print("  Any future hypothesis mapping to these inherits the evidence and must show a NEW")
    print("  asymmetry or forced-flow story -- not merely a new dataset.")

    # ---------- 2. HYPOTHESIS PORTFOLIO CONSTRUCTION ------------------------------------
    print("\n=== 2. HYPOTHESIS PORTFOLIO (ERV alone concentrates the book) ===")
    ranked = []
    if ERV.exists():
        ranked = json.loads(ERV.read_text("utf-8")).get("ranked", [])
    if not ranked:
        print("  no ERV output -- run scripts/research_erv.py first")
    else:
        used_mech: dict[str, int] = {}
        out: list[dict[str, Any]] = []
        for h in ranked:
            ms = mech_of(h.get("name", "") + " " + " ".join(h.get("concepts", []))) or ["M_UNMAPPED"]
            # correlation penalty: each prior selection in the same mechanism halves the value
            overlap = max(used_mech.get(m, 0) for m in ms)
            adj = h.get("erv", 0) / (2 ** overlap)
            out.append({**h, "mechs": ms, "overlap": overlap, "erv_adj": round(adj, 4)})
            for m in ms:
                used_mech[m] = used_mech.get(m, 0) + 1
        out.sort(key=lambda x: -x["erv_adj"])
        print(f"  {'ERV':>6}{'ADJ':>7}  {'mech':<24} hypothesis")
        for h in out[:10]:
            print(f"  {h['erv']:>6.3f}{h['erv_adj']:>7.3f}  {h['mechs'][0][:24]:<24} "
                  f"{h['name'][:44]}")
        dupes = [h for h in out if h["overlap"] > 0]
        print(f"\n  {len(dupes)} hypotheses de-rated for mechanism overlap -- these were ONE BET")
        print("  WEARING SEVERAL HATS. Ranking by raw ERV would have funded the same idea 5x.")

    # ---------- 3. MECHANISM REVIEW BOARD ------------------------------------------------
    print("\n=== 3. MECHANISM REVIEW BOARD (pre-test gate) ===")
    print("    64% of this desk's failures were TIMING or MEASUREMENT, not alpha -- exactly what")
    print("    a pre-test gate catches for free\n")
    samples = [
        {"name": "Low RSI predicts bounce",
         "text": "rsi oversold below 30 tends to bounce, momentum indicator"},
        {"name": "Liquidation cascade exhaustion",
         "text": "forced liquidations must sell into thin books, exceeding available depth; "
                 "the constraint is that liquidated accounts CANNOT choose timing; not arbitraged "
                 "because capacity is limited by book depth. kill if IC<0 over 12 months"},
        {"name": "Attention efficiency ratio",
         "text": "return per unit of social attention growth predicts continuation"},
    ]
    for s in samples:
        t = (s["name"] + " " + s["text"]).lower()
        answers = {k: any(w in t for w in kws) for k, q, kws in BOARD}
        ms = mech_of(t) or ["M_UNMAPPED"]
        fam = [m for m in ms if verdicts.get(m) == "FAMILY KILL"]
        passed = all(answers.values()) and not fam
        print(f"  {s['name'][:44]:<44} {'PASS' if passed else 'REJECT'}")
        for k, q, _ in BOARD:
            if not answers[k]:
                print(f"      unanswered: {q}")
        if fam:
            print(f"      mechanism {fam[0]} is a FAMILY KILL -- needs a new asymmetry story")

    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "mechanism_deaths": tally, "verdicts": verdicts,
                               "family_kills": dead_fams,
                               "portfolio": out if ranked else []}, indent=1), "utf-8")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()

```

### scripts/prove_future.py
```python
"""PROVE future enforcement, do not assert it. Plant violations, confirm the guards fail, remove.

The principal has asked repeatedly whether this is really enforced. Every previous answer was a
CLAIM about current state. This is an adversarial test of FUTURE state: it creates exactly the
things that would appear tomorrow -- a new LLM caller that forgets doctrine, a new prompt file
without the mandate, and a principle silently dropped from the preamble -- and verifies each guard
catches it.

A guard that has never been shown to fail has never been shown to work.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(".")
PY = ".venv/bin/python"
results = []


def run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
    return r.returncode


# ---------------------------------------------------------------- baseline
d0 = run(f"{PY} scripts/doctrine.py")
p0 = run(f"{PY} scripts/principle_audit.py")
results.append(("BASELINE doctrine guard", d0 == 0, f"exit {d0} (expect 0)"))
results.append(("BASELINE principle guard", p0 == 0, f"exit {p0} (expect 0)"))

# ---------------------------------------------------------------- test 1: future LLM caller
fake = ROOT / "scripts/_tmp_future_caller.py"
fake.write_text(
    'import json, urllib.request\n'
    'def ask(k, system, user):\n'
    '    body = json.dumps({"model": "x", "messages": ['
    '{"role": "system", "content": system}]}).encode()\n'
    '    return urllib.request.urlopen("https://openrouter.ai/api/v1/chat/completions")\n',
    "utf-8")
d1 = run(f"{PY} scripts/doctrine.py")
results.append(("FUTURE LLM caller without doctrine is CAUGHT", d1 != 0,
                f"exit {d1} (expect non-zero)"))
fake.unlink()

# ---------------------------------------------------------------- test 2: future prompt file
fp = ROOT / "prompts/panel_missions/_tmp_future_mission.txt"
fp.write_text("ROLE: analyse the desk and report findings.\n", "utf-8")
d2 = run(f"{PY} scripts/doctrine.py")
results.append(("FUTURE prompt file without mandate is CAUGHT", d2 != 0,
                f"exit {d2} (expect non-zero)"))
fp.unlink()

# ---------------------------------------------------------------- test 3: dropped principle
doc = ROOT / "scripts/doctrine.py"
orig = doc.read_text("utf-8")
# Remove the SECTION BODY, not just its header -- v1 removed only the title and the audit
# still matched on body text, so the "dropped principle" proof passed vacuously.
i = orig.index("BOTTLENECK FIRST")
j = orig.index("OPPORTUNITY COST")
tampered = orig[:i] + orig[j:]
doc.write_text(tampered, "utf-8")
p3 = run(f"{PY} scripts/principle_audit.py")
results.append(("PRINCIPLE silently dropped is CAUGHT", p3 != 0, f"exit {p3} (expect non-zero)"))
doc.write_text(orig, "utf-8")

# ---------------------------------------------------------------- restore check
d4 = run(f"{PY} scripts/doctrine.py")
p4 = run(f"{PY} scripts/principle_audit.py")
results.append(("RESTORED doctrine guard", d4 == 0, f"exit {d4} (expect 0)"))
results.append(("RESTORED principle guard", p4 == 0, f"exit {p4} (expect 0)"))

print("=== ADVERSARIAL PROOF OF FUTURE ENFORCEMENT ===")
print("    guards are not asserted -- violations are planted and the guards must FAIL on them\n")
for name, ok, detail in results:
    print(f"  {'PASS' if ok else 'FAIL'}  {name:<50} {detail}")
bad = [r for r in results if not r[1]]
print(f"\n  {len(results)-len(bad)}/{len(results)} proofs passed")
if bad:
    print("  A guard that does not fail on a planted violation does not work.")
else:
    print("  Every guard fails on a planted violation and passes when restored. Enforcement is")
    print("  demonstrated for callers, prompts and principles that DO NOT EXIST YET.")
sys.exit(1 if bad else 0)

```

### scripts/recommendations.py
```python
#!/usr/bin/env python3
"""RECOMMENDATION LEDGER (§42, principal 2026-07-26) -- nothing recommended is ever forgotten.

THE HOLE. track_findings.py governs PANEL findings only (model / summary / accepted-or-rejected).
Everything else this desk produces a recommendation from -- max_audit defects, the weekly deep cold
audit, cycle reports, the proactive battery, external reviews -- had no ledger and no forced
disposition. A deep sweep could name eight high-ROI improvements, the report gets written, the
window closes, and by the next Sunday nobody knows they existed. That is the same class as the
findings hole it was built to close, one layer up.

THE LAW. Every recommendation gets exactly one row, and every row must reach a DISPOSITION:
IMPLEMENTED (with a commit), REJECTED (with a real reason), or SCHEDULED (with a due date that is
itself enforced). "No decision" is not a state a row may rest in -- an undisposed row past its
grace window is a DEFECT, not backlog. Rejection is always available and is a legitimate answer,
because the principal's instruction is that nothing is SKIPPED, not that everything is BUILT: a
reasoned no is a decision, silence is the failure.

WHY IT CANNOT BE GAMED. Rows are never deleted and dispositions never revert to none, so the
cheap escape -- quietly dropping an inconvenient row -- is closed the same way the mining ratchet
closes shrinking the denominator. A rejection needs a substantive reason (a bare "no" is refused
at the CLI), and a SCHEDULED row that passes its due date fires exactly like an orphan, so
"scheduled" cannot become a place recommendations go to die.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "docs/research/recommendation_ledger.json"

# A recommendation may sit undisposed for one cycle -- long enough to be triaged in the next
# organ run, short enough that it cannot quietly become permanent.
GRACE_H = 24.0
_TERMINAL = ("implemented", "rejected")
_MIN_REASON = 25          # a bare "no" / "wontfix" is not a disposition


def _load() -> dict[str, Any]:
    if LEDGER.exists():
        try:
            loaded: dict[str, Any] = json.loads(LEDGER.read_text("utf-8"))
            return loaded
        except Exception as e:
            # A corrupt ledger must NEVER read as empty-healthy: `report` would print
            # "0 total, nothing overdue" and the next _save would atomically replace
            # every row with the empty dict -- the mass-deletion the ledger law forbids.
            # Observed live 2026-07-31: merge-conflict markers committed to origin read
            # here as a clean empty ledger. Refuse loudly; git history repairs it.
            raise SystemExit(
                f"REFUSING: {LEDGER} exists but cannot be parsed ({e}); repair it from "
                "git history -- an unreadable ledger must never become an empty one") from e
    return {"recommendations": []}


def _save(d: dict[str, Any]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    tmp = LEDGER.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, indent=1), "utf-8")
    tmp.replace(LEDGER)          # atomic: a torn ledger would lose the very rows it protects


def _age_h(iso: str) -> float:
    try:
        return (datetime.now(tz=UTC) - datetime.fromisoformat(iso)).total_seconds() / 3600.0
    except Exception:
        return 0.0


def _next_id(d: dict) -> str:
    """Allocate past BOTH the local ledger and the last-fetched origin/master copy (R0152).

    Count-based allocation minted the same id on two boxes three times on 2026-07-31
    (R0135-37, R0143, R0144): each box counts its own rows, so concurrent sessions collide
    and every merge renumbers rows and repoints code comments. Max-known-id with origin
    consulted (git show reads the fetched ref -- no network) shrinks the race window from
    all-day to since-last-fetch; an unreadable origin falls back to the local max, which
    still never re-mints an id a renumber has already retired.
    """
    import re
    import subprocess
    nums = [int(m.group(1)) for r in d["recommendations"]
            if (m := re.match(r"R(\d+)$", str(r.get("id", ""))))]
    try:
        remote = subprocess.run(
            ["git", "show", "origin/master:docs/research/recommendation_ledger.json"],
            capture_output=True, text=True, timeout=10,
            cwd=Path(__file__).resolve().parent.parent)
        if remote.returncode == 0:
            nums += [int(x) for x in re.findall(r'"id":\s*"R(\d+)"', remote.stdout)]
    except (OSError, subprocess.SubprocessError):
        pass                                   # offline clone: local max still monotonic
    return f"R{(max(nums) if nums else 0) + 1:04d}"


def add(a: argparse.Namespace) -> None:
    d = _load()
    # DEDUPE on (source, summary): organs re-read the same audit report every cycle, and a ledger
    # that grows a duplicate row per read becomes noise nobody triages -- which is the failure it
    # exists to prevent, arriving by a different route.
    for r in d["recommendations"]:
        if r["source"] == a.source and r["summary"].strip() == a.summary.strip():
            print(f"{r['id']} already ledgered ({r['status']})")
            return
    rid = _next_id(d)
    d["recommendations"].append({
        "id": rid, "source": a.source, "summary": a.summary,
        "roi_bps": a.roi_bps, "raised": datetime.now(tz=UTC).isoformat(),
        "status": "open", "reason": None, "commit": None, "due": None, "disposed": None})
    _save(d)
    print(f"{rid} ledgered from {a.source} -- OPEN, disposition owed within {GRACE_H:.0f}h")


def dispose(a: argparse.Namespace) -> None:
    d = _load()
    row = next((r for r in d["recommendations"] if r["id"] == a.id), None)
    if row is None:
        raise SystemExit(f"no such recommendation: {a.id}")
    if row["status"] in _TERMINAL:
        raise SystemExit(f"{a.id} is already {row['status']} -- dispositions do not revert. "
                         "If it was MISFILED, use `correct --id --reason`, which logs the "
                         "reversal in the row history rather than erasing it.")
    # GUARD AGAINST DISPOSING THE WRONG ROW (2026-07-26): ids are assigned by count, so a
    # concurrent writer -- the weekly sweep ledgering seven rows mid-session -- shifts the id
    # a caller assumed. --expect makes the caller name what it thinks it is deciding.
    if a.expect and a.expect.lower() not in row["summary"].lower():
        raise SystemExit(
            f"{a.id} does not match --expect {a.expect!r}. Its summary is:\n  "
            f"{row['summary'][:200]}\nAnother writer may have taken the id you assumed.")
    if a.status == "rejected" and len((a.reason or "").strip()) < _MIN_REASON:
        raise SystemExit(
            f"a rejection needs a real reason (>={_MIN_REASON} chars). The principal's "
            "standard is that nothing is SKIPPED, not that everything is built -- a "
            "reasoned no is a decision, a bare no is silence wearing a label.")
    if a.status == "scheduled" and not a.due:
        raise SystemExit("a scheduled recommendation needs --due YYYY-MM-DD, else 'scheduled' "
                         "becomes the place recommendations go to die")
    if a.status == "implemented" and not a.commit:
        raise SystemExit("an implemented recommendation needs --commit: the desk's standing rule "
                         "is that an artifact proves the work, never a claim")
    row.update(status=a.status, reason=a.reason, commit=a.commit, due=a.due,
               disposed=datetime.now(tz=UTC).isoformat())
    _save(d)
    print(f"{a.id} -> {a.status.upper()}")


def correct(a: argparse.Namespace) -> None:
    """Reverse a MIS-ENTERED disposition, permanently logging that it happened.

    "Dispositions never revert" is the right guard against gaming and the wrong one against error:
    it made an honest mis-entry unfixable. What actually prevents laundering is not immovability
    but VISIBILITY -- a correction keeps the original disposition, its reason, and the reason it
    was wrong in the row's own history, so the record reads as "decided, then found misfiled",
    never as "never decided". Corrections are cheap to audit and impossible to hide.
    """
    d = _load()
    row = next((r for r in d["recommendations"] if r["id"] == a.id), None)
    if row is None:
        raise SystemExit(f"no such recommendation: {a.id}")
    if row["status"] == "open":
        raise SystemExit(f"{a.id} is already open -- nothing to correct")
    if len((a.reason or "").strip()) < _MIN_REASON:
        raise SystemExit(f"a correction needs a real reason (>={_MIN_REASON} chars): what was "
                         "misfiled, and why the original disposition did not apply to this row")
    row.setdefault("corrections", []).append({
        "was": row["status"], "was_reason": row.get("reason"),
        "was_commit": row.get("commit"), "was_due": row.get("due"),
        "corrected": datetime.now(tz=UTC).isoformat(), "why": a.reason})
    row.update(status="open", reason=None, commit=None, due=None, disposed=None)
    _save(d)
    print(f"{a.id} corrected -> OPEN (prior disposition kept in its history); "
          "a fresh disposition is now owed")


def owed(d: dict[str, Any]) -> tuple[list[Any], list[Any]]:
    """(undisposed past grace, scheduled past due) -- the two ways a row goes stale."""
    now = datetime.now(tz=UTC)
    orphans = [r for r in d["recommendations"]
               if r["status"] == "open" and _age_h(r["raised"]) > GRACE_H]
    overdue = []
    for r in d["recommendations"]:
        if r["status"] != "scheduled" or not r.get("due"):
            continue
        try:
            if datetime.fromisoformat(str(r["due"])).replace(tzinfo=UTC) < now:
                overdue.append(r)
        except Exception:
            overdue.append(r)          # an unparseable due date is not a valid schedule
    return orphans, overdue


def report(_a: argparse.Namespace) -> None:
    d = _load()
    rows = d["recommendations"]
    orphans, overdue = owed(d)
    done = [r for r in rows if r["status"] == "implemented"]
    print(f"recommendations: {len(rows)} total | {len(done)} implemented | "
          f"{sum(1 for r in rows if r['status'] == 'rejected')} rejected | "
          f"{sum(1 for r in rows if r['status'] == 'scheduled')} scheduled | "
          f"{sum(1 for r in rows if r['status'] == 'open')} open")
    for label, group in (("UNDISPOSED past grace", orphans), ("SCHEDULED past due", overdue)):
        for r in group:
            print(f"  DEFECT [{label}] {r['id']} ({r['source']}, {_age_h(r['raised']) / 24:.1f}d): "
                  f"{r['summary'][:110]}")
    if not orphans and not overdue:
        print("  no orphans, nothing overdue -- every recommendation has a decision")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add", help="ledger a recommendation (status opens as undisposed)")
    p.add_argument("--source", required=True,
                   help="max_audit | deep_sweep | cycle | panel | proactive_battery | principal")
    p.add_argument("--summary", required=True)
    p.add_argument("--roi-bps", dest="roi_bps", type=float, default=None)
    p.set_defaults(func=add)
    p = sub.add_parser("dispose", help="record the decision -- the only way a row leaves open")
    p.add_argument("--id", required=True)
    p.add_argument("--status", required=True, choices=["implemented", "rejected", "scheduled"])
    p.add_argument("--reason")
    p.add_argument("--commit")
    p.add_argument("--due", help="YYYY-MM-DD, required for scheduled")
    p.add_argument("--expect", help="substring the target summary must contain -- "
                                    "guards against disposing a row another writer "
                                    "took the id of")
    p.set_defaults(func=dispose)
    p = sub.add_parser("correct", help="reverse a MISFILED disposition, logged")
    p.add_argument("--id", required=True)
    p.add_argument("--reason", required=True)
    p.set_defaults(func=correct)
    p = sub.add_parser("report", help="orphans and overdue -- both are defects, not backlog")
    p.set_defaults(func=report)
    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()

```

### scripts/research_exchange.py
```python
"""RESEARCH EXCHANGE -- the ChatGPT <-> Claude daily loop, and the scoreboard that judges both.

THE PRINCIPAL'S QUESTION: "im copy pasting ur responses to claude and claudes to urs, is there a
way to make them communicate w eachother daily?"

THE PRINCIPAL'S OWN ANSWER IS THE CORRECT ONE AND THIS IMPLEMENTS IT LITERALLY: "evidence sits
between them. They shouldn't persuade each other -- they should respond to the same data and
deterministic validation results." So there is NO model-to-model channel here, deliberately. Two
LLMs arguing directly produce consensus, and consensus between two systems trained on overlapping
corpora is not evidence -- it is correlated error wearing the costume of agreement. Worse, the
loser of an argument is decided by rhetoric, which is the single thing an LLM is best at and the
single thing that should carry no weight on a trading desk.

So the channel is a SHARED ARTEFACT, and both models are downstream of it:

    desk state (measured)  --brief-->  each model, independently, cold
                                            |
                                       proposals
                                            |
                                        --intake-->  suggestion ledger (attributed, deduped)
                                            |
                                       deterministic validation (the desk's existing gates)
                                            |
                                        --score-->  contributor scoreboard -> research allocation

Three verbs, one file, because they are one loop and splitting them would produce three scripts of
which two go unwired -- this desk already has 179 of those.

    python scripts/research_exchange.py brief          # -> docs/DESK_BRIEF.md  (paste to either)
    python scripts/research_exchange.py intake FILE --source chatgpt
    python scripts/research_exchange.py score

WHY THE SCOREBOARD IS THE POINT, NOT THE BRIEF. data/panel_scorecard.json has existed since
2026-07-17 with 13 providers and this content: 0 scored, hit_rate null, for EVERY provider. The
desk has never once measured which intelligence source produced value, so every allocation it has
ever made between sources was made on reputation. The brief is easy; attribution is the part that
was missing, and attribution only works if it is stamped at INTAKE, before anyone knows whether
the idea was any good. Scoring proposals after the fact, from memory, is how you get a scorecard
of nulls.

DEDUPE IS A HARD GATE, NOT A CONVENIENCE. An external model that has not read the graveyard will
re-propose dead mechanisms indefinitely -- it costs it nothing. Intake checks every proposal
against the mechanism FAMILY KILLS and the graveyard before it is allowed to consume a slot, and
records the rejection against the source's record. A source that mostly re-proposes corpses should
lose allocation for exactly that reason, and now it can be shown to.

Read-only w.r.t. trading. No keys, no network. Run from repo root.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "data/suggestion_ledger.jsonl"
BRIEF = ROOT / "docs/DESK_BRIEF.md"
SCORE = ROOT / "data/contributor_scoreboard.json"
GRAVE = ROOT / "docs/graveyard.md"

# status ladder -- a proposal earns its way up. Weights are the reward function, so they are the
# whole design: a source is paid for CHANGING A DECISION, not for sounding insightful.
LADDER = {"proposed": 0.0, "rejected_dup": -0.5, "rejected_dead": -1.0, "accepted": 0.5,
          "built": 2.0, "changed_decision": 4.0, "improved_live": 10.0}

_STOP = {"the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "with", "is", "are", "be", "this", "that", "it", "as", "by", "from", "at", "we", "you", "your", "our", "their", "its", "should", "could", "would", "may", "might", "can", "will", "not", "no", "yes", "if", "then", "than", "more", "most", "less", "least", "very", "much", "many", "some", "any", "all", "new", "use", "used", "using", "into", "over", "under", "when", "what", "which", "who", "whom", "whose", "how", "why", "where", "research", "desk", "system", "data"}


def _toks(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", s.lower()) if w not in _STOP}


def _read(p: Path, default=None):
    try:
        return json.loads(p.read_text("utf-8"))
    except Exception:  # blind-except intentional (BLE001)
        return default


def _ledger() -> list[dict]:
    if not LEDGER.exists():
        return []
    out = []
    for ln in LEDGER.read_text("utf-8").splitlines():
        ln = ln.strip()
        if ln:
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    return out


# ------------------------------------------------------------------ BRIEF
def brief() -> None:
    """One machine-generated evidence file. No prose, no argument, no framing -- numbers only.

    Framing is how an LLM gets led. If the brief said "our carry is underperforming, what should
    we do?" every model would return carry ideas. It states measured quantities and lets the model
    decide what is interesting; a model that ignores the biggest number in the file is telling you
    something about the model.
    """
    reg = _read(ROOT / "data/experiment_registry.json", {}) or {}
    aut = _read(ROOT / "data/research_autopsy.json", {}) or {}
    mb = _read(ROOT / "data/mechanism_board.json", {}) or {}
    erv = _read(ROOT / "data/research_erv.json", {}) or {}
    mic = _read(ROOT / "data/micro_features.json", {}) or {}
    hold = _read(ROOT / "data/optimal_hold.json", {}) or {}

    L = [f"# DESK BRIEF -- {datetime.now(tz=UTC).strftime('%Y-%m-%d %H:%MZ')}",
         "",
         "Machine-generated from measured desk state. Every number traces to an artifact in",
         "`data/`. Nothing here is an argument. Respond to the evidence, not to another model.",
         "",
         "## Standing rules that bind any proposal",
         "1. Every proposal must name the MEASURABLE BOTTLENECK it removes, the metric that should",
         "   move, and the observation that would kill it. Missing any of the three = rejected.",
         "2. A proposal mapping to a FAMILY KILL below must present a NEW forced-flow or asymmetry",
         "   story. A new dataset for a dead mechanism is not a new hypothesis.",
         "3. Prefer DELETE/MERGE over ADD. This desk has 226 scripts and ~179 unwired.",
         "4. Screening is unlimited and carries ZERO promotion authority. Only pre-registered",
         "   forward clocks promote.",
         ""]

    if reg:
        d = reg.get("decisions", {})
        L += ["## Experiment record (45d, harvested from git -- one row per commit)",
              f"- experiments: **{reg.get('n')}**; decided: "
              f"{sum(d.get(k,0) for k in ('SURVIVED','REFUTED','INCONCLUSIVE'))}",
              f"- survival rate: **{(reg.get('survival_rate') or 0)*100:.1f}%** "
              f"({d.get('SURVIVED',0)} survived / {d.get('REFUTED',0)} refuted / "
              f"{d.get('INCONCLUSIVE',0)} inconclusive)",
              f"- unclassified commit decisions: {reg.get('unclassified')} (commit-discipline defect)",
              ""]
        ms = reg.get("mechanism_survival", {})
        if ms:
            L += ["| mechanism | tested | survived | rate |", "|---|---:|---:|---:|"]
            for m, v in sorted(ms.items(), key=lambda kv: -kv[1]["tested"]):
                r = v["survived"] / v["tested"] * 100 if v["tested"] else 0
                L.append(f"| {m} | {v['tested']} | {v['survived']} | {r:.0f}% |")
            L.append("")
        fm = reg.get("failure_modes", {})
        if fm:
            tot = sum(fm.values())
            L += ["### Why experiments died (45d)", ""]
            for k, v in sorted(fm.items(), key=lambda kv: -kv[1]):
                L.append(f"- `{k}` {v} ({v/tot*100:.0f}%)")
            meas = fm.get("E_DATA_QUALITY", 0) + fm.get("B_WRONG_MEASUREMENT", 0)
            L += ["", f"**{meas}/{tot} = {meas/tot*100:.0f}% of refutations are MEASUREMENT "
                      "failures (data quality + wrong construction), not absent alpha.**", ""]
    if mb.get("family_kills"):
        L += ["## FAMILY KILLS -- mechanisms closed by evidence",
              "", ", ".join(f"`{m}`" for m in mb["family_kills"]),
              "", "Every future variant inherits this evidence.", ""]
    if aut.get("lessons"):
        L += ["## Transferable lessons (family -> dominant failure mode)", ""]
        for x in aut["lessons"][:8]:
            L.append(f"- **{x['family']}** -> `{x['dominant_mode']}` (n={x['n']})")
        L.append("")
    if mic.get("results"):
        r0 = mic["results"]
        L += ["## Proprietary moat (4.4GB order books, 30 symbols, top-20 snapshots)",
              "",
              "M_LIQUIDITY_WITHDRAWAL, construction = negative z of near-touch depth vs 24h roll:",
              f"- raw lead rho pooled: {sum(x['lead_rho'] for x in r0)/len(r0):+.4f}",
              "- **after orthogonalising forward RV against current RV: residual rho +0.0154 "
              "(t +0.28), sign 1/5 -> the lead was vol clustering.**",
              "- ONE construction tested only. The mechanism is NOT refuted. Untested: "
              "replenishment rate, one-sided withdrawal, book shape, migration, recovery "
              "half-life, d(book)/dt.", ""]
    if hold:
        L += ["## Live carry", "",
              "- entry gate `_DEFAULT_RT_BPS` 4.5 -> 39.5 (p90 of measured round-trip) on "
              "2026-07-27; bar is now ~8.8x the funding floor. Effect unmeasured until 24-48h "
              "of rotations accumulate.",
              "- pre-fix: funding harvested $113 vs implied costs $876 = **7.75x**.",
              "- hold-time scan: 8h -39.2%/yr, 24h +5.8%/yr (LIVE), 48h +14.0%/yr, 72h +17.0%/yr. "
              "`_MIN_HOLD_H` is still 24. ~+11pp/yr unclaimed.", ""]
    if erv.get("ranked"):
        L += ["## Highest-ERV open hypotheses", ""]
        for h in erv["ranked"][:6]:
            L.append(f"- {h.get('erv', 0):.3f} — {h.get('name','')[:88]}")
        L.append("")
    L += ["## Known blockers", "",
          "- OpenRouter 402: 4 written LLM roles have NEVER executed (code auditor, blind "
          "researcher, hypothesis generator, architecture board).",
          "- `health.json` reports all_ok=True against 14 stub vs 13 real logs (fail-open).",
          "- First forward-clock verdict: 2026-08-07 (OI/LS). Confirmed alphas to date: 0.", ""]
    BRIEF.parent.mkdir(parents=True, exist_ok=True)
    BRIEF.write_text("\n".join(L), "utf-8")
    print(f"wrote {BRIEF}  ({len(L)} lines)")
    print("Paste this ONE file to each model independently. Do not paste one model's reply to the")
    print("other -- that is persuasion. Paste their replies back through `intake` instead.")


# ------------------------------------------------------------------ INTAKE
def _dead_terms() -> tuple[set[str], list[str]]:
    mb = _read(ROOT / "data/mechanism_board.json", {}) or {}
    kills = set(mb.get("family_kills", []))
    names = []
    if GRAVE.exists():
        for ln in GRAVE.read_text("utf-8").splitlines():
            if ln.startswith("|") and not set(ln) <= set("|- "):
                c = [x.strip() for x in ln.strip("|").split("|")]
                if c and c[0].lower() not in ("name", "signal", "strategy"):
                    names.append(c[0])
    return kills, names


def intake(path: str, source: str) -> None:
    txt = Path(path).read_text("utf-8", errors="ignore")
    kills, _dead_names = _dead_terms()
    mb_kw = {
        "M_ATTENTION_DELAY": ("attention", "sentiment", "social", "twitter", "reddit", "trends"),
        "M_SKILL_PERSISTENCE": ("trader", "copytrad", "leaderboard", "smart money", "skill"),
        "M_FLOW_PRESSURE": ("netflow", "inflow", "outflow", "stablecoin flow", "bridge flow"),
        "M_PRICE_PATTERN": ("momentum", "rsi", "macd", "breakout", "moving average", "reversal"),
    }
    prior = _ledger()
    prior_toks = [(_toks(p.get("problem", "") + " " + p.get("benefit", "")), p) for p in prior]

    rows, stats = [], {"kept": 0, "dup": 0, "dead": 0, "incomplete": 0}
    for ln in txt.splitlines():
        if ln.count("|") < 2:
            continue
        parts = [x.strip() for x in ln.split("|") if x.strip()]
        if len(parts) < 7:
            stats["incomplete"] += 1          # looked like a proposal, missing mandatory fields
            continue
        rec = {"date": datetime.now(tz=UTC).date().isoformat(), "source": source,
               "problem": parts[0][:220], "evidence": parts[1][:220], "benefit": parts[2][:180],
               "cost": parts[3][:140], "dependencies": parts[4][:140],
               "success_metric": parts[5][:180], "kill_condition": parts[6][:180],
               "status": "proposed"}
        blob = " ".join(parts).lower()
        tk = _toks(rec["problem"] + " " + rec["benefit"])

        hit = next((m for m, kws in mb_kw.items() if m in kills and any(k in blob for k in kws)),
                   None)
        if hit:
            rec["status"] = "rejected_dead"
            rec["reason"] = f"maps to FAMILY KILL {hit} with no new asymmetry story"
            stats["dead"] += 1
        else:
            best, bp = 0.0, None
            for ptk, p in prior_toks:
                if not ptk or not tk:
                    continue
                j = len(tk & ptk) / len(tk | ptk)
                if j > best:
                    best, bp = j, p
            if best >= 0.55:
                rec["status"] = "rejected_dup"
                rec["reason"] = f"jaccard {best:.2f} vs prior {bp.get('source','?')} proposal"
                stats["dup"] += 1
            else:
                stats["kept"] += 1
        rows.append(rec)

    if not rows:
        print("no charter-complete proposals found. Required per line, '|'-separated:")
        print("PROBLEM|EVIDENCE|BENEFIT|COST|DEPENDENCIES|SUCCESS_METRIC|KILL_CONDITION")
        print(f"({stats['incomplete']} lines looked like proposals but lacked all 7 fields)")
        return
    with LEDGER.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    print(f"source={source}  {stats['kept']} accepted-for-review, {stats['dup']} duplicate, "
          f"{stats['dead']} re-proposed a dead mechanism, {stats['incomplete']} incomplete")
    for r in rows:
        if r["status"] != "proposed":
            print(f"  [{r['status']}] {r['problem'][:64]}\n      {r.get('reason','')}")
    print(f"-> {LEDGER}")
    print("\nStatus is advanced by HUMAN/desk decision, never by the proposer:")
    print("  proposed -> accepted -> built -> changed_decision -> improved_live")


# ------------------------------------------------------------------ SCORE
def score() -> None:
    rows = _ledger()
    print("=== CONTRIBUTOR SCOREBOARD ===")
    print("    data/panel_scorecard.json has held 13 providers at 0 scored / hit_rate null since")
    print("    2026-07-17. Every allocation between sources so far was made on reputation.\n")
    if not rows:
        print("  ledger EMPTY -- 0 external proposals have ever been ingested.")
        print("  That is the honest state: there is nothing to score yet, and a scoreboard that")
        print("  reported numbers here would be fabricating them. Run `intake` first.")
        SCORE.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                                     "sources": {}, "n": 0}, indent=1), "utf-8")
        return
    by: dict[str, dict] = {}
    for r in rows:
        s = r.get("source") or r.get("seat") or "unknown"
        d = by.setdefault(s, dict.fromkeys(LADDER, 0))
        d[r.get("status", "proposed")] = d.get(r.get("status", "proposed"), 0) + 1
    print(f"  {'source':<26}{'prop':>6}{'dead':>6}{'dup':>5}{'built':>7}{'live':>6}{'score':>8}"
          f"{'yield':>8}")
    out = {}
    for s, d in sorted(by.items()):
        n = sum(d.values())
        pts = sum(LADDER.get(k, 0) * v for k, v in d.items())
        conv = (d.get("built", 0) + d.get("changed_decision", 0) + d.get("improved_live", 0)) / n
        print(f"  {s:<26}{n:>6}{d.get('rejected_dead',0):>6}{d.get('rejected_dup',0):>5}"
              f"{d.get('built',0):>7}{d.get('improved_live',0):>6}{pts:>8.1f}{conv*100:>7.0f}%")
        out[s] = {"n": n, "points": round(pts, 2), "conversion": round(conv, 4), "detail": d}
    print("\n  SCORE weights the ladder: improved_live 10, changed_decision 4, built 2,")
    print("  accepted 0.5, re-proposing a dead mechanism -1. A source producing 200 clever")
    print("  proposals and one live improvement ranks BELOW one producing 20 of which five")
    print("  became infrastructure. Volume is not rewarded anywhere in this function.")
    SCORE.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                                 "weights": LADDER, "sources": out, "n": len(rows)}, indent=1),
                     "utf-8")
    print(f"  -> {SCORE}")


def main() -> None:
    a = sys.argv[1:]
    if not a or a[0] not in ("brief", "intake", "score"):
        print(__doc__)
        return
    if a[0] == "brief":
        brief()
    elif a[0] == "score":
        score()
    else:
        if len(a) < 2:
            raise SystemExit("usage: research_exchange.py intake FILE --source NAME")
        src = a[a.index("--source") + 1] if "--source" in a else "unknown"
        intake(a[1], src)


if __name__ == "__main__":
    main()

```

### scripts/run_ci.py
```python
"""Local CI gate -- lint + tests + stress, in one command. Free (no cloud, no cost).

Runs ruff (lint) and the test suite, then the stress harness. Non-zero exit if anything fails, so
it can gate a commit or a deploy. This is the always-available substitute for hosted CI: correctness
of the survival-critical logic (hedge reconcile, risk controls, sizing, leverage) is checked
mechanically, not by hand.

NOTE (2026-07-18): the pytest step names specific files/dirs rather than the whole `tests/` tree
-- a full-tree collection currently fails on pre-existing duplicate test-module basenames across
directories (e.g. two unrelated `test_regime.py`, two unrelated `test_registry.py`; see GAP
register). `tests/execution/` (the risk-path/execution directory, incl. the live connector +
stage machine) was added to the gate 2026-07-18 since that code must never silently go untested;
other directories (risk/, portfolio/, features/, regime/, ...) are NOT yet gated here -- a real
open gap, tracked separately, not fixed by this comment.

    python scripts/run_ci.py
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from libs.ops.platform_paths import venv_python

_ROOT = Path(__file__).resolve().parent.parent
_PY = venv_python(_ROOT)

_STEPS = [
    ("lint (ruff)", [_PY, "-m", "ruff", "check", "scripts", "libs", "tests"]),
    # WHOLE TREE (2026-07-25): was 4 named files + tests/execution = ~147 of ~1099 tests, leaving
    # tests/risk (the ruin path) and tests/validation (the anti-false-positive path) ungated, and
    # every newly-shipped test ungated by default. GAP 31's stated blocker -- duplicate basenames
    # breaking collection -- EXPIRED once pyproject set --import-mode=importlib: the tree collects
    # and was run 100% GREEN this session (only optional-dep skips), so gating it is proven safe.
    ("tests (pytest)", [_PY, "-m", "pytest", "tests/", "-q"]),
    ("stress harness", [_PY, "scripts/run_stress.py"]),
]


_LOCK = _ROOT / "data/.ci_run.lock"


def _acquire() -> object | None:
    """Take the CI lock, or return None if another run already holds it.

    Non-blocking on purpose: a second concurrent gate tests the same tree, so it adds no
    information while doubling peak RAM on a 3.8 GiB box with no swap -- where the OOM-killer's
    victim could be the dead-man rail. Declining beats queueing.
    """
    _LOCK.parent.mkdir(parents=True, exist_ok=True)
    fh = _LOCK.open("w")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    return fh


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    fail_on_lock = "--fail-on-lock" in args
    _fh = _acquire()
    if _fh is None:
        # Another gate is mid-run on the same tree. For an ORGAN's routine gate, exit 0 and DO
        # NOT touch the marker: non-zero would fail its cycle for the non-error of someone else
        # already checking, and writing the marker here IS the last-writer-wins race.
        # For a DEPLOY decision that exit 0 is a lie -- pull_deploy read "skipped" as "green"
        # and would have shipped an unvetted commit (found 2026-07-31, R0145). --fail-on-lock
        # returns 3: "could not gate", which a deployer must treat as not-green and retry.
        if fail_on_lock:
            print("CI: another run holds the lock -- cannot gate this tree state (rc 3)")
            return 3
        print("CI: another run holds the lock -- skipping (marker left untouched)")
        return 0
    failed: list[str] = []
    for label, cmd in _STEPS:
        r = subprocess.run(cmd, cwd=str(_ROOT), capture_output=True, text=True, check=False)
        ok = r.returncode == 0
        tail = (r.stdout or r.stderr or "").strip().splitlines()[-1:] or [""]
        print(f"[{'PASS' if ok else 'FAIL'}] {label}: {tail[0][:120]}")
        if not ok:
            failed.append(label)
    print("CI:", "ALL GREEN" if not failed else f"FAILED -> {failed}")
    # Freshest-truth CI status marker (2026-07-23): a red desk-wide gate sat undetected 81h
    # because the brain cycle that runs run_ci was quota-dead; max_audit now surfaces this
    # marker so a red gate always enters the escalation path. Additive; never affects the gate.
    with contextlib.suppress(OSError):
        (_ROOT / "data/.ci_last_run.json").write_text(
            json.dumps({"ok": not failed, "ts": datetime.now(tz=UTC).isoformat(),
                        "failed": failed}), "utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/run_derivative_shadow.py
```python
"""Derivative-data shadow sleeves (Phase 5): OI Divergence + Long/Short Contrarian.

ECONOMIC HYPOTHESES (pre-registered, no peeking):
  * OI Divergence  -- price up + OI up = genuine trend participation (follow); price up + OI DOWN =
                      short-covering (weak, fade). Signal = sign(dPrice)*sign(dOI), cross-sectional.
  * L/S Contrarian -- crowded retail positioning mean-reverts. Signal = -zscore(long/short ratio),
                      cross-sectional (fade the crowd).

We have NO usable history for these (the derivative metrics only exist from when our own archiver
started), so we DO NOT fabricate a backtest. Instead we accumulate forward and report progress. The
moment >= MIN_DAYS distinct days exist, this computes real forward sleeve returns + Sharpe and the
discovery gauntlet (CPCV/DSR/PBO) takes over. Writes web/derivative_shadow.json.

    python scripts/run_derivative_shadow.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from libs.data.crypto_source import fetch_klines
from libs.research.anytime_valid import e_value

_METRICS = Path("data/crypto_metrics.parquet")
_OUT = Path("web/derivative_shadow.json")
_MIN_DAYS = 40


def _sharpe(r: np.ndarray) -> float:
    sd = float(np.std(r))
    return round(float(np.mean(r)) / sd * (365 ** 0.5), 2) if sd else 0.0


def _forward_returns(df: pd.DataFrame) -> dict[str, float]:
    """Compute OI-divergence + L/S-contrarian forward sleeve Sharpes once enough days exist."""
    df = df.copy()
    df["date"] = pd.to_datetime(df["ts"]).dt.date
    piv_oi = df.pivot_table(index="date", columns="symbol", values="open_interest")
    piv_ls = df.pivot_table(index="date", columns="symbol", values="ls_ratio")
    syms = list(piv_oi.columns)
    start_ms = int((pd.Timestamp(min(df["date"])) - pd.Timedelta(days=2)).timestamp() * 1000)
    px = {}
    for s in syms:
        try:
            k = fetch_klines(s, interval="1d", start_ms=start_ms)
            if not k.empty:
                px[s] = k.set_index(k["timestamp"].dt.date)["close"].astype(float)
        except Exception:
            continue
    prices = pd.DataFrame(px).reindex(piv_oi.index).ffill()
    pr_ret = prices.pct_change().shift(-1)                    # next-day return (no lookahead)
    d_price = prices.pct_change()
    d_oi = piv_oi.pct_change()
    oi_sig = np.sign(d_price) * np.sign(d_oi)                 # +1 confirm trend, -1 divergence
    ls_z = (piv_ls.sub(piv_ls.mean(axis=1), axis=0)).div(piv_ls.std(axis=1) + 1e-9, axis=0)
    ls_sig = -ls_z                                            # fade the crowd
    out = {}
    for name, sig in (("oi_divergence", oi_sig), ("ls_contrarian", ls_sig)):
        w = sig.sub(sig.mean(axis=1), axis=0)                 # market-neutral
        w = w.div(w.abs().sum(axis=1) + 1e-9, axis=0)
        out[name] = (w * pr_ret).sum(axis=1).dropna().to_numpy()
    return out


def main() -> None:
    now = datetime.now(tz=UTC)
    # REGISTRY-DRIVEN ROSTER (principal 2026-07-23): built-ins plus anything registered in
    # data/shadow_sleeves.json, so a new sleeve starts accruing forward evidence the moment it
    # is registered -- no code edit, nothing silently left off the clocks. Safe to scale now
    # that DSR deflation is per-family and pre-registered (fixed wall), so parallel challengers
    # no longer inflate each other's bar. Order is deterministic for reproducible runs.
    sleeves = ["oi_divergence", "ls_contrarian"]
    try:
        _extra = json.loads(Path("data/shadow_sleeves.json").read_text("utf-8"))
        if isinstance(_extra, list):
            sleeves = sorted({*sleeves, *(str(x) for x in _extra if str(x).strip())})
    except Exception:
        pass
    if not _METRICS.exists():
        days, quality = 0, "no archive yet"
        result: dict[str, object] = {}
    else:
        df = pd.read_parquet(_METRICS)
        days = int(pd.to_datetime(df["ts"]).dt.date.nunique())
        nsym = int(df["symbol"].nunique())
        nan_ls = float(df["ls_ratio"].isna().mean())
        quality = f"{nsym} symbols/day, L/S NaN {nan_ls:.0%}"
        # PEEK RULE (2026-07-22): the e-process is anytime-valid (Ville) -- reading it
        # daily spends NO alpha, so it may be published while the clock accrues. The
        # interim Sharpe is NOT peek-safe and stays unpublished until min_days.
        series = _forward_returns(df) if days >= 12 else {}
    ready = days >= _MIN_DAYS
    result = {k: _sharpe(v) if len(v) > 5 else 0.0 for k, v in series.items()} if ready else {}
    peek = {k: {"e_value": round(e_value(v), 3), "n": len(v), "threshold": 100.0,
                "decisive": bool(e_value(v) >= 100.0)} for k, v in series.items()}
    eta = (now + timedelta(days=max(0, _MIN_DAYS - days))).date().isoformat()
    out = {
        "updated": now.isoformat(),
        "sleeves": sleeves,
        "days_accumulated": days,
        "min_days": _MIN_DAYS,
        "data_quality": quality,
        "validation_progress_pct": round(100 * min(1.0, days / _MIN_DAYS), 1),
        "expected_ready_date": eta,
        "status": "VALIDATING" if ready else "ACCUMULATING (no backtest fabricated)",
        "forward_sharpe": result,
        "anytime_peek": peek,
        "peek_rule": "e_value is anytime-valid: safe to read daily. decisive=True at "
                     "alpha=0.01 BEFORE day 40 = early evidence; Sharpe stays "
                     "unpublished until min_days (not peek-safe). Promotion still "
                     "requires the full gauntlet.",
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    print(f"derivative shadow: {days}/{_MIN_DAYS} days ({out['validation_progress_pct']}%), "
          f"ETA {eta}, status {out['status']}")


if __name__ == "__main__":
    main()

```

### scripts/run_discretionary_hunt.py
```python
#!/usr/bin/env python3
"""DISCRETIONARY EDGE HUNT (R0152) -- find the NEXT discretionary edge, not just tune the current one.

PRINCIPAL ORDER (2026-08-01): *"a whole system dedicated to this and improving the brain and
finding MULTIPLE discretionary edges this way, trading like a compounding human trader with the
philosophy of that screenshot."*

THE GAP THIS FILLS, and it is the one the rest of the section did not cover. The discretionary desk
has an optimiser (R0151 pushes the hit rate of the sleeve that exists) and a learner (R0139 extracts
lessons from closed trades). Both improve ONE edge. Neither ever asks whether there is a SECOND
one -- and the allocator's own arithmetic says a second INDEPENDENT edge is worth more than a large
improvement to the first, because growth multiplies across uncorrelated bets and merely adds within
one. A desk with a single discretionary hypothesis is one regime change away from having none.

WHAT A DISCRETIONARY EDGE IS HERE, stated so the hunt does not drift into indicator soup. It is a
situation a skilled human trader RECOGNISES and can act on, that has a MECHANISM (someone is forced
to trade, or is systematically late, or is priced off the wrong thing), and that fails a stated
observation. "RSI below 30" is not one -- it names no participant and no compulsion. "The stop
cluster above a triple-touched high gets swept before the real move, because resting stops are the
only guaranteed liquidity at that level" is one: it names who is forced and why.

THE FORCED-PARTICIPANT TEST is inherited from the event sleeve and is the single strongest filter
this desk owns. Every candidate must answer: WHO has to trade against you, and WHY can they not
wait? A hypothesis with no forced counterparty is a pattern, and the desk's record on patterns is
420 tested, 0 survived.

ANTI-REPETITION. Every candidate is registered permanently. A hunt that regenerates the same six
ideas every night looks productive and produces nothing, which is the failure mode of every
brainstorming loop ever built. Previously-seen candidates are shown to the model as ALREADY HUNTED
and it is told to go elsewhere -- and repeats are counted, because a rising repeat rate means the
search space is exhausted and the lenses need re-aiming rather than the cadence raising.

WHAT IT DOES NOT DO: promote anything. A survivor earns a pre-registered forward clock and a place
in the sleeve allocator's independence test, nothing more (L1.6). The allocator then decides
whether it is a genuine second edge or the first one wearing a new name -- which is the question
that decides whether "multiple edges" compounds or just costs more fees.

    python scripts/run_discretionary_hunt.py [--json] [--n 4]
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

_REGISTRY = "data/discretionary_edges.json"
_STATE = "data/discretionary_hunt.json"

#: 4 candidates per run. Enough that a weak lens still yields one usable idea, few enough that each
#: gets real reasoning rather than a list. Raising it trades depth for length, which is the wrong
#: direction when the binding constraint is candidate QUALITY and not candidate count.
N_CANDIDATES = 4

#: A repeat rate above this means the search space under the current lenses is exhausted: the
#: honest response is to re-aim the lenses, NOT to raise the cadence, which would just regenerate
#: the same ideas faster. 0.5 = half the batch already known.
EXHAUSTION_REPEAT_RATE = 0.5

#: LENSES -- each is a different WAY a human trader finds an edge, rotated so the hunt does not
#: circle one region forever. Deliberately about market participants and compulsion, not about
#: indicators.
_LENSES: tuple[tuple[str, str], ...] = (
    ("FORCED LIQUIDITY",
     "who is FORCED to transact at a price they would not choose -- liquidations, margin calls, "
     "index rebalances, expiries, redemption windows, stop clusters"),
    ("STRUCTURAL LATENESS",
     "who is systematically LATE -- mandates that can only act after a print, desks that hedge on "
     "a schedule, funds that cannot trade until a threshold is breached"),
    ("WRONG-PRICE ANCHOR",
     "what is priced off the WRONG reference -- a stale index, a lagging proxy, a correlation "
     "everyone assumes still holds, a funding rate anchored to a different venue"),
    ("SESSION AND CALENDAR",
     "what changes at a KNOWN TIME -- session opens and closes, funding stamps, settlement, "
     "weekend gaps, holiday liquidity, the hours no desk is staffed"),
    ("FAILED EXPECTATION",
     "where a widely-expected move FAILS -- failed breakouts, unbought dips, news that does not "
     "move price. The failure itself is information about positioning"),
    ("CROSS-ASSET DIVERGENCE",
     "when two things that normally move together STOP -- gold vs real yields, BTC vs risk, a "
     "perp vs its own spot, one venue vs another"),
)


def load_registry(root: Path) -> dict[str, Any]:
    try:
        return json.loads((root / _REGISTRY).read_text("utf-8"))
    except (OSError, ValueError):
        return {"edges": []}


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", str(text).lower()).strip()[:90]


def lens_for(stamp: str, slot: int = 0) -> tuple[str, str]:
    """Date-ordinal rotation so coverage is provable rather than random."""
    try:
        ordinal = datetime.strptime(stamp, "%Y%m%d").date().toordinal()
    except ValueError:
        ordinal = 0
    return _LENSES[(ordinal + slot) % len(_LENSES)]


_BRIEF = """You are hunting for a NEW DISCRETIONARY TRADING EDGE on Binance USD-M perpetuals -- the
kind a skilled human trader recognises on a chart and in the flow, not a statistical pattern.

TONIGHT'S LENS -- {lens_name}: {lens_body}

WHAT COUNTS AS AN EDGE HERE, and most proposals fail this:
  * it names a FORCED PARTICIPANT. Who has to trade against you, and why can they not wait?
    Liquidation engines, margin calls, index rebalances, mandates that must act after a print.
    "RSI below 30" names nobody and is not an edge. If you cannot name who is compelled, say so
    and discard the candidate rather than dressing it up.
  * a HUMAN could recognise it in real time from price, structure and the desk's feeds. If it
    needs a fitted model it belongs to the systematic side, not here.
  * it has a FALSIFIER -- the specific observation that would prove it is not real.

ALREADY HUNTED -- do NOT propose these again, go somewhere else entirely:
{seen}

THE DESK'S OWN LEARNED LESSONS, from its closed trades (weigh these, and say if one is wrong):
{playbook}

OUTPUT EXACTLY ONE JSON OBJECT:
{{"candidates": [
  {{"name": "short handle",
    "situation": "what a human sees, concretely, in one or two sentences",
    "forced_participant": "WHO must trade against you and why they cannot wait",
    "mechanism": "why this produces a price move that is not already arbitraged",
    "falsifier": "the observation that proves it is not real",
    "how_measured": "what data on this desk would test it -- charts, funding, liquidations, "
                    "announcements, copy-flow, cross-venue",
    "why_not_arbitraged": "why this survives being obvious",
    "confidence": 0.4}}
]}}

{n} candidates. Fewer good ones beats more weak ones -- a candidate with no forced participant
should not be in the list at all. If this lens is genuinely exhausted, return fewer and say so in
a candidate named "LENS-EXHAUSTED"."""


def _ask(prompt: str, timeout: int = 900) -> str:
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


def validate(c: dict[str, Any]) -> tuple[bool, str]:
    """The forced-participant test, and the falsifier. Both or it is a pattern."""
    for f in ("name", "situation", "forced_participant", "mechanism", "falsifier"):
        if not str(c.get(f, "")).strip():
            return False, f"REFUSED: missing {f}"
    fp = str(c["forced_participant"]).lower()
    if len(fp) < 25 or any(w in fp for w in ("traders", "the market", "everyone", "participants")):
        return False, ("REFUSED: forced participant is generic -- 'traders' and 'the market' name "
                       "nobody. A hypothesis with no identifiable compelled counterparty is a "
                       "pattern, and this desk is 420-tested/0-survived on patterns")
    if len(str(c["falsifier"])) < 20:
        return False, "REFUSED: falsifier too thin to act on"
    if len(str(c["mechanism"])) < 40:
        return False, "REFUSED: mechanism too thin -- state why the move is not already arbitraged"
    return True, "accepted"


def register(root: Path, cands: list[dict[str, Any]], lens: str,
             ) -> dict[str, Any]:
    reg = load_registry(root)
    seen = {e["key"] for e in reg["edges"]}
    now = datetime.now(tz=UTC).isoformat()
    new, repeat, refused = [], [], []
    for c in cands:
        ok, why = validate(c)
        if not ok:
            refused.append({"name": c.get("name"), "why": why})
            continue
        k = _key(c.get("name", "") + " " + c.get("situation", ""))
        if k in seen:
            repeat.append(c.get("name"))
            continue
        seen.add(k)
        reg["edges"].append({**c, "key": k, "lens": lens, "found": now,
                             "status": "CANDIDATE",
                             "authority": "forward clock only -- never capital (L1.6)"})
        new.append(c.get("name"))
    reg["updated"] = now
    (root / _REGISTRY).parent.mkdir(parents=True, exist_ok=True)
    (root / _REGISTRY).write_text(json.dumps(reg, indent=2), "utf-8")
    total = len(new) + len(repeat)
    return {"new": new, "repeats": repeat, "refused": refused,
            "repeat_rate": round(len(repeat) / total, 3) if total else None,
            "registry_size": len(reg["edges"])}


def build_report(root: Path | None = None, *, n: int = N_CANDIDATES, ask=_ask,
                 stamp: str | None = None) -> dict[str, Any]:
    root = root or _ROOT
    stamp = stamp or datetime.now(tz=UTC).strftime("%Y%m%d")
    lens_name, lens_body = lens_for(stamp)
    reg = load_registry(root)
    seen_txt = "\n".join(f"  - {e.get('name')}: {str(e.get('situation'))[:90]}"
                         for e in reg["edges"][-40:]) or "  (none yet)"
    try:
        from scripts.run_conviction_trader import _playbook_brief
        pb = _playbook_brief(root)
    except Exception as exc:
        pb = f"(playbook unavailable: {type(exc).__name__})"
    raw = ask(_BRIEF.format(lens_name=lens_name, lens_body=lens_body, seen=seen_txt,
                            playbook=pb[:1500], n=n))
    obj = parse(raw)
    if not obj or not isinstance(obj.get("candidates"), list):
        return {"generated": datetime.now(tz=UTC).isoformat(), "lens": lens_name,
                "status": "NO-CANDIDATES",
                "why": "no parseable JSON (auth/quota/refusal) -- this is UNMEASURED hunting, "
                       "not an empty search space"}
    res = register(root, obj["candidates"], lens_name)
    rr = res["repeat_rate"]
    exhausted = rr is not None and rr >= EXHAUSTION_REPEAT_RATE
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.6/L1.31 -- a second INDEPENDENT edge is worth more than a large improvement to "
               "the first, because growth multiplies across uncorrelated bets and merely adds "
               "within one. A desk with a single discretionary hypothesis is one regime change "
               "away from having none.",
        "lens": lens_name, "status": "HUNTED",
        **res,
        "exhaustion": ("LENS-EXHAUSTED -- re-aim the lenses, do NOT raise the cadence: a higher "
                       "cadence on an exhausted space regenerates the same ideas faster"
                       if exhausted else "search space still yielding"),
        "authority": "candidates earn a pre-registered forward clock and a place in the sleeve "
                     "allocator's independence test. They earn no capital (L1.6), and the "
                     "allocator decides whether a survivor is a real second edge or the first one "
                     "wearing a new name.",
        "detail": (f"lens {lens_name}: {len(res['new'])} new, {len(res['repeats'])} repeats, "
                   f"{len(res['refused'])} refused; registry {res['registry_size']}"),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=N_CANDIDATES)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report(_ROOT, n=args.n)
    out = _ROOT / _STATE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    print(json.dumps(rep, indent=2) if args.json else
          f"discretionary hunt (R0152): {rep.get('detail') or rep.get('why')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/run_generation_diversity.py
```python
"""GENERATION DIVERSITY -- the wiring for HYPOTHESIS_MAX #2/#3/#6 (single Lane-A task).

The spec's wiring clause: *"metrics computed per batch and appended to the seat scoreboard
(data/panel_scorecard.json field `gen_diversity`)"*. This is that task, and it is what stops the
three components from being three more built-and-never-called modules -- the defect L2.9 exists
for, and the one this desk has repeatedly produced.

WHAT IT REPORTS, and why each number is one the desk did not previously have:

  novel_rate           of the ideas generated, the share that were genuinely NEW questions rather
                       than reparameterisations. Volume without this is throughput, not
                       information -- and "420 candidates tested" versus "one question asked 420
                       ways" are identical from a count. The desk has never been able to tell
                       those apart, and 420/0 is exactly the record that needed telling apart.
  mechanism_entropy    diversity of the fingerprints in the batch, normalised by ITEM count.
  market_breadth       names actually spanned, counting a cross-sectional universe properly.
  cross_generator_dup  whether separate seats are producing the same idea (herding).

IT NEVER BLOCKS GENERATION. Per the spec, the collapse detector is instrumentation that pages the
process, not a gate on ideas -- a diversity metric with veto power would be a second unvalidated
filter on a funnel this desk has already measured as too tight. The variation blocker DOES block,
but only on an exact fingerprint match or a >=0.90 Jaccard near-duplicate, and every block is
recorded with what it duplicated so "blocked" never means "lost".

    python scripts/run_generation_diversity.py [--json]
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

from libs.research import collapse_detector as CD  # noqa: E402
from libs.research import variation_blocker as VB  # noqa: E402

_OUT = _ROOT / "data/gen_diversity.json"
_SCORECARD = _ROOT / "data/panel_scorecard.json"
_DB = _ROOT / "data/research_memory.db"


def _batch() -> tuple[list[Any], list[str]]:
    """The most recent generation batch, with the seat that produced each idea.

    Reads the candidate store. Returns ([], []) when the lab db is absent -- this box may not be
    the research box, and an empty batch is a fact worth reporting rather than an error.
    """
    if not _DB.exists():
        return [], []
    try:
        from libs.autodiscovery.memory import CandidateStore
        from libs.store.connection import Database
        rows = CandidateStore(Database(_DB, read_only=True)).all()
    except (ImportError, OSError, ValueError, AttributeError, TypeError):
        return [], []
    rows = sorted(rows, key=lambda c: str(getattr(c, "created_at", "")))[-200:]
    gens = [str(getattr(c, "campaign_id", "") or "unknown") for c in rows]
    return list(rows), gens


def build() -> dict[str, Any]:
    batch, gens = _batch()
    div = CD.measure(batch, generators=gens)
    assessment = CD.assess(div)
    tel = VB.telemetry()
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "n_in_batch": len(batch),
        "gen_diversity": div.as_dict(),
        "assessment": assessment,
        "variation_telemetry": tel,
        "law": "HYPOTHESIS_MAX #2/#3/#6. The detector NEVER blocks generation; the blocker blocks "
               "only exact-fingerprint or >=0.90-Jaccard duplicates, and records what each block "
               "duplicated so the ledger stays a map of the searched space.",
    }


def _append_scorecard(rep: dict[str, Any]) -> bool:
    """Append `gen_diversity` to the seat scoreboard, per the spec's wiring clause."""
    try:
        card = json.loads(_SCORECARD.read_text("utf-8")) if _SCORECARD.exists() else {}
    except (OSError, ValueError):
        card = {}
    if not isinstance(card, dict):
        return False
    card["gen_diversity"] = {
        "at": rep["generated"], "n": rep["n_in_batch"],
        **{k: rep["gen_diversity"][k] for k in
           ("mechanism_entropy", "feature_breadth", "market_breadth",
            "semantic_distinctness", "cross_generator_dup_rate")},
        "verdict": rep["assessment"]["verdict"],
        "novel_rate": rep["variation_telemetry"].get("novel_rate"),
    }
    _SCORECARD.parent.mkdir(parents=True, exist_ok=True)
    _SCORECARD.write_text(json.dumps(card, indent=2), "utf-8")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build()
    rep["scorecard_updated"] = _append_scorecard(rep)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
        return 0
    d, a, t = rep["gen_diversity"], rep["assessment"], rep["variation_telemetry"]
    print(f"generation diversity [{a['verdict']}] over {rep['n_in_batch']} candidates")
    if rep["n_in_batch"] == 0:
        print("  NO BATCH -- no research db on this box. That is a supply fact, not a health "
              "reading; the metrics below would be fabricated if reported as measured.")
    else:
        print(f"  mechanism entropy   {d['mechanism_entropy']:.3f}  "
              f"({d['n_fingerprints']} distinct fingerprints)")
        print(f"  feature breadth     {d['feature_breadth']:.3f}")
        print(f"  market breadth      {d['market_breadth']} names")
        print(f"  semantic distinct.  {d['semantic_distinctness']:.3f}")
        print(f"  cross-gen duplicate {d['cross_generator_dup_rate']:.1%}")
        for fp, n in d["top_fingerprints"][:3]:
            print(f"      most attempted: {fp}  x{n}")
    for f in a["flags"]:
        print(f"  FLAG {f[:110]}")
    if t.get("n"):
        print(f"  variation blocker: {t['n_novel']}/{t['n']} genuinely new "
              f"(novel_rate {t['novel_rate']:.1%}), {t['n_blocked']} blocked")
    print(f"-> {_OUT.relative_to(_ROOT)}"
          + ("  + panel_scorecard.gen_diversity" if rep["scorecard_updated"] else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts/run_generation_roi_test.py
```python
#!/usr/bin/env python3
"""Monte-Carlo falsification: does batch hypothesis generation over a FIXED data set pay?

Runs synthetic candidate batches of growing size through the REAL novelty gate + DSR gauntlet
(libs/autodiscovery/generation_roi) and prints the survivor rate, the deflated DSR bar, and the cost
per survivor as the batch grows. A few candidates carry a true edge; the rest are noise.

    python scripts/run_generation_roi_test.py

Demonstrates the economics behind the Discovery-Factory deferral: as the batch (and thus the trial
count) grows, the DSR bar rises and the survivor rate collapses — mass generation over the same data
is self-defeating. A SECOND discovery method here shares the same trial ledger, so it deflates both
rather than diversifying. Positive ROI needs a NEW data axis (unexhausted space, low trial count).
"""

from __future__ import annotations

import numpy as np

from libs.autodiscovery.generation_roi import Candidate, generation_roi
from libs.validation.dsr import sharpe_ratio


def _candidate(
    cid: str, rng: np.random.Generator, *, edge_sharpe: float,
    n_periods: int = 500, sigma: float = 0.01,
) -> Candidate:
    mu = edge_sharpe * sigma
    r = rng.normal(mu, sigma, n_periods)
    return Candidate(
        id=cid, statement=f"hypothesis {cid}", features=(f"feat_{cid}",),
        returns=tuple(float(x) for x in r),
    )


def _batch(
    n: int, rng: np.random.Generator, *, edge_frac: float, edge_sharpe: float
) -> list[Candidate]:
    out: list[Candidate] = []
    for i in range(n):
        s = edge_sharpe if rng.random() < edge_frac else 0.0
        out.append(_candidate(f"n{n}_{i}", rng, edge_sharpe=s))
    return out


def main() -> None:
    rng = np.random.default_rng(20260723)
    edge_frac, edge_sharpe = 0.03, 0.15
    print("Generation-ROI Monte-Carlo -- batch generation over a FIXED data set")
    print(f"({edge_frac:.0%} carry a true ~{edge_sharpe}/period Sharpe edge; the rest are null)\n")

    cols = ("batch N", "tested", "survivors", "surv_rate", "DSR_bar", "cost/surv")
    widths = (8, 8, 10, 10, 9, 10)
    print("".join(f"{c:>{w}}" for c, w in zip(cols, widths, strict=True)))
    print("-" * sum(widths))
    for n in (10, 50, 200, 1000):
        batch = _batch(n, rng, edge_frac=edge_frac, edge_sharpe=edge_sharpe)
        sharpes = [sharpe_ratio(np.asarray(c.returns, dtype="float64")) for c in batch]
        rep = generation_roi(batch, variance_of_sharpes=float(np.var(sharpes, ddof=1)))
        cps = "inf" if rep.cost_per_survivor == float("inf") else f"{rep.cost_per_survivor:.1f}"
        vals = (n, rep.backtested, rep.survivors, f"{rep.survivor_rate:.3f}",
                f"{rep.deflated_bar_sr0:.3f}", cps)
        print("".join(f"{v:>{w}}" for v, w in zip(vals, widths, strict=True)))

    print("\nRead: as N grows the DSR bar rises and the survivor rate collapses.")
    print("Mass generation over the SAME data is self-defeating under multiplicity correction.")
    print("A second method shares this SAME trial ledger -- it deflates both, not diversifies.")
    print("Positive ROI needs a NEW data axis (unexhausted space, low trial count).")


if __name__ == "__main__":
    main()

```

### scripts/screen_exchange_netflow.py
```python
"""STAGE-A SCREEN: exchange netflow as a supply-pressure timing signal (BTC + ETH, 16y).

MECHANISM (stated BEFORE any compute, per SCREEN-ON-DISCOVERY point 2 -- screening a catalogued
axis without a mechanism prior is breadth-mining with extra steps, which the 420/0 result already
refuted): coins moving ONTO exchanges are supply arriving at the only venue where it can be sold,
so positive netflow is revealed selling intent and should precede WEAKER returns; coins moving OFF
exchanges are custody/accumulation and should precede STRONGER returns. Expected IC sign is
NEGATIVE. This is a genuine TIMING signal for the asset itself, so absolute forward return is the
mechanism-appropriate target (only 2 assets exist here, so a cross-sectional build would be a
2-wide panel -- reported as unavailable rather than faked).

TIMESTAMP ALIGNMENT (declared, per SCREEN-ON-DISCOVERY point 4 -- unstated alignment VOIDS the
screen): signal and target come from the SAME Coin Metrics daily rows, keyed by the same `date`
field, ingested from one source. `netflow_ntv` is a UTC-day aggregate and `price_usd` is that same
UTC day's reference price, so signal[t] (flow during UTC day t) predicts the return realised over
the FOLLOWING period, which is exactly the t -> t+1 shift stage_a_screen performs. There is no
cross-source timezone join here, which is the defect class that turned the kimchi and Turkey
premia into pure timing artifacts (a KST-day close sits ~1.6d ahead of a UTC-day close). LOOK-AHEAD
RISK: LOW for that reason; the residual risk is Coin Metrics revising a day's flow after
publication, which this local archive cannot detect.

EVERY CONSTRUCTION TRIED IS LOGGED (point 3 -- reporting only the build that printed is
garden-of-forking-paths p-hacking). Two builds x three horizons x two assets = 12 cells, and ALL
12 are reported and counted as trials regardless of which one looks best:
  raw    -- netflow_ntv as-is
  scaled -- netflow_ntv / sply_ex_ntv, a flow/stock ratio. Economically the right normalisation
            over a 16-year window where native-unit volumes grew ~1000x; the raw build's z-score
            has to absorb that drift through a 20-day window alone.

ZERO PROMOTION AUTHORITY (point 5): Stage A earns a pre-registered forward clock at most, never
capital. Negative screens are first-class deliverables (point 6) and are graveyarded with reason.
"""

from __future__ import annotations

import collections
import json
import sys

import numpy as np

from libs.alpha_factory.hypothesis_novelty import PriorIdea, hypothesis_novelty
from libs.research.axis_screen import stage_a_screen

_SRC = "data/coinmetrics_flows.jsonl"
_HORIZONS = (1, 5, 20)


def _log(m: str) -> None:
    print(m, flush=True)


def _load() -> dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """asset -> (netflow, exchange_supply, price) as date-sorted daily arrays."""
    rows: dict[str, dict[str, tuple[float, float, float]]] = collections.defaultdict(dict)
    with open(_SRC) as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except Exception:
                continue
            a, day = d.get("asset"), str(d.get("date", ""))[:10]
            nf, sx, px = d.get("netflow_ntv"), d.get("sply_ex_ntv"), d.get("price_usd")
            if not a or not day or nf is None or px is None:
                continue
            try:
                rows[a][day] = (float(nf), float(sx) if sx is not None else float("nan"),
                                float(px))
            except (TypeError, ValueError):
                continue
    out = {}
    for a, byday in rows.items():
        days = sorted(byday)
        arr = np.array([byday[d] for d in days], dtype="float64")
        out[a] = (arr[:, 0], arr[:, 1], arr[:, 2])
        _log(f"  {a}: {len(days)} daily rows {days[0]} -> {days[-1]}")
    return out


def _forward_returns(price: np.ndarray, h: int) -> np.ndarray:
    """target_ret[t] = simple return realised OVER period t, where a period is h days.

    stage_a_screen applies the t -> t+1 shift itself, so this must be the CONTEMPORANEOUS
    h-day return, never a shifted one -- shifting here too would double-count the lead and
    manufacture a look-ahead.
    """
    r = np.full(len(price), np.nan)
    r[h:] = price[h:] / price[:-h] - 1.0
    return r


def main() -> int:
    nov = hypothesis_novelty(
        "Exchange netflow (coins moving onto exchanges) is revealed selling intent and precedes "
        "weaker forward returns; outflow to custody precedes stronger returns.",
        features=["netflow_ntv", "sply_ex_ntv", "exchange_supply", "supply_pressure"],
        priors=[
            PriorIdea(id="onchain-reversal", statement="On-chain activity mean-reverts price over "
                      "multi-day horizons", category="onchain",
                      features=["active_addresses", "tx_count", "throughput_usd"],
                      lesson="Killed on 11y held-out OOS (backfill_onchain_oos)."),
            PriorIdea(id="kimchi-premium", statement="Korean exchange price premium predicts BTC "
                      "returns", category="cross-venue", features=["kimchi_premium", "prem_btc"],
                      lesson="Retracted: ~73% timestamp artifact, KST vs UTC candle labels."),
        ],
    )
    _log(f"NOVELTY GATE: novelty={nov.novelty_score:.3f} redundant={nov.is_redundant} "
         f"nearest={nov.nearest_id!r} sim={nov.nearest_similarity:.3f}")
    if nov.is_redundant:
        _log("REDUNDANT -> refusing to spend compute (novelty gate).")
        return 0

    _log(f"loading {_SRC}")
    data = _load()

    results = []
    for asset, (netflow, exsupply, price) in sorted(data.items()):
        builds = {"raw": netflow}
        with np.errstate(divide="ignore", invalid="ignore"):
            scaled = np.where(exsupply > 0, netflow / exsupply, np.nan)
        if np.isfinite(scaled).sum() > 400:
            builds["scaled"] = scaled
        else:
            _log(f"  {asset}: 'scaled' build UNAVAILABLE (sply_ex_ntv too sparse) -- reported, "
                 "not silently dropped")
        for build, sig in builds.items():
            for h in _HORIZONS:
                tgt = _forward_returns(price, h)
                ok = np.isfinite(sig) & np.isfinite(tgt)
                if ok.sum() < 300:
                    _log(f"  SKIP {asset}/{build}/h={h}: only {ok.sum()} aligned obs")
                    continue
                res = stage_a_screen(
                    sig[ok], tgt[ok], name=f"exchange_netflow_{asset}_{build}_h{h}",
                    horizon_days=float(h),
                )
                res.update({"asset": asset, "build": build, "horizon_d": h, "n_obs": int(ok.sum())})
                results.append(res)
                # INSUFFICIENT-DATA returns only name/verdict/n, so never assume 'ic' is present.
                _ic = res.get("ic")
                _log(f"  {asset}/{build}/h={h:2d}  n={ok.sum():5d}  "
                     f"IC={f'{_ic:+.4f}' if _ic is not None else '   n/a'}  "
                     f"resid_IC={res.get('residual_ic')}  verdict={res.get('verdict')}")

    _log(f"\n=== ALL {len(results)} CELLS ARE DSR-COUNTED TRIALS (target/horizon sweep duty) ===")
    for r in sorted(results, key=lambda x: -abs(x.get("ic") or 0.0)):
        _ic = r.get("ic")
        _log(f"  {r['asset']:4s} {r['build']:7s} h={r['horizon_d']:2d}  "
             f"IC={f'{_ic:+.4f}' if _ic is not None else '   n/a'}  verdict={r.get('verdict')}")
    interesting = [r for r in results if "INTERESTING" in str(r.get("verdict", ""))]
    _log(f"\nSCREEN-INTERESTING cells: {len(interesting)} of {len(results)}")

    out = "reports/screen_exchange_netflow.json"
    with open(out, "w") as fh:
        json.dump({"novelty": {"score": nov.novelty_score, "nearest": nov.nearest_id,
                               "similarity": nov.nearest_similarity},
                   "n_trials": len(results), "cells": results}, fh, indent=2, default=str)
    _log(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/screen_fred_macro_axis.py
```python
"""SCOPED GENERATE RUN -- fred_macro family (owed item, docs/research/generation_due.md line 5).

WHAT WAS ACTUALLY OWED, AND WHAT WAS ALREADY PAID
-------------------------------------------------
`generation_due.md` is a 2026-07-16 SNAPSHOT and was never regenerated. The cadence engine's own
condition (scripts/run_cadence.py:202) is

    Path("data/fred_macro.json").exists() and not state.get("gen_done_fred_macro_family")

and `data/cadence_state.json` has carried `gen_done_fred_macro_family = 2026-07-17T08:55:24Z`
since the day after the snapshot. So the PAPER duty (author + EV-gate pre-registrations) is
closed and the flag is stale. What was never done is the part the flag's own justification
promised -- "deep history available ... immediately backtestable against the crypto lake": not one
fred_macro series has ever been put through the audited Stage-A harness. This run does that.

THE HONEST PRIOR, STATED UP FRONT (this run does not get to pretend it is exploring virgin ground)
--------------------------------------------------------------------------------------------------
The macro->crypto class has been EV-rejected SIX times by this desk: 3 FRED-family overlays on
2026-07-17 (EV 0.004-0.013), then `dxy_shock_beta_rotation` (fx, 0.0052), `risk_regime_rotation`
(index, 0.0027) and `net_liquidity_impulse` (fed, 0.0026) on 2026-07-22 -- the last carrying the
note "if it also rejects, the fed axis is ledgered exhausted". It rejected. Those are ECONOMIC
priors, not measurements: nobody ever looked. Screening is the empirical complement, run at the
SAME bar, and it cannot reopen the EV verdict -- Stage A has zero promotion authority and no cell
here is passed a `clock=`, so nothing on this axis can start a forward clock no matter how it
prints. A "good" IC here would be a finding to report, never a decision.

PRE-DECLARED POWER VERDICT (computed from sample LENGTH alone, before any IC is seen)
-------------------------------------------------------------------------------------
stage_a_screen calls a cell powered only when 1.96/sqrt(n_eff) <= ic_min=0.03, i.e. it needs
n_eff >= 4268 independent observations. The deepest fred_macro series aligned to BTC gives ~4030
US business days (DTWEXBGS from 2006-01, VIXCLS from 1990-01, both clipped by BTC history starting
2010-07), and n_eff is then divided again by the mean calendar spacing. EVERY cell in this run is
therefore expected to return SCREEN-UNDERPOWERED, at every horizon, before a single number is
computed. They are run anyway -- the ICs are recorded evidence a later meta-analysis can pool, and
"we never looked" is the exact defect the data-utilization law exists to kill -- but they are
counted as trials and NOT reported as if the null were a refutation.

Deliberately NOT screened, with reasons (declared, not silently dropped):
  * M2SL -- monthly (~192 obs once aligned to BTC), ~25-day publication lag, AND FRED serves the
    CURRENT VINTAGE of a series that is revised. A backtest on current-vintage M2 uses numbers
    that were not knowable at the time: look-ahead THROUGH REVISION, which no timestamp alignment
    can fix. Untestable honestly from this archive.

TIMESTAMP ALIGNMENT (declared per series; every one is a BACKWARD/stale offset except WALCL,
whose forward release lag is handled by an explicit lag)
--------------------------------------------------------------------------------------------------
  crypto leg  Coin Metrics community daily BTC close, PriceUSD dated d == fixed close at 00:00 UTC
              on d+1. VERIFIED against the Binance D1 lake on the 2515 overlapping days: same-date
              log-return corr +0.994, and shifting either leg one day collapses it to
              -0.047 / -0.066. Same date label = same instant.
  DGS10,
  T10Y2Y      Treasury H.15 constant-maturity yields struck ~15:30 ET on business day d, published
              ~16:15 ET the same day => 3.5-4.5h STALE vs the 00:00Z d+1 crypto close. BACKWARD.
  VIXCLS      CBOE VIX official close 16:15 ET day d, published same day => ~3h STALE. BACKWARD.
  DTWEXBGS    Fed H.10 broad dollar index, NOON ET buying rates on day d, published ~16:15 ET day
              d => ~7h STALE. BACKWARD.
  WALCL       H.4.1 balance sheet AS OF Wednesday d but RELEASED Thursday 16:30 ET. The value
              dated d is NOT knowable at the day-d close. LOOK-AHEAD RISK: REAL, and it is the
              only one in this run. Handled by shifting the series +2 calendar days before any
              alignment, so the signal is first used at the d+2 close -- strictly after the
              release. WALCL is an accounting statement and is not materially revised.

SAMPLING: FRED observation dates INTERSECT BTC dates; the target is the BTC return between
CONSECUTIVE SAMPLED dates, so a Friday->Monday step is a 3-calendar-day return. `horizon_days`
passed to the harness is the MEAN realised calendar spacing of the sampled blocks, so the Sharpe
annualisation sqrt(365/h) matches the actual period and n_eff is if anything under-credited
(non-overlapping blocks need no overlap correction at all). Blocks are non-overlapping, so
signal[k] is observed strictly inside period k and predicts period k+1.

    .venv/bin/python scripts/screen_fred_macro_axis.py
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.screen_idle_axes import _graveyard_priors, block_idx  # noqa: E402

from libs.alpha_factory.hypothesis_novelty import PriorIdea, hypothesis_novelty  # noqa: E402
from libs.research.alpha_economics import Idea, ev_score  # noqa: E402
from libs.research.axis_screen import stage_a_screen  # noqa: E402

OUT = ROOT / "data/fred_macro_screen.json"
DEEP = ROOT / "data/fred_macro_deep.json"
FRED = "https://api.stlouisfed.org/fred/series/observations"
ZWIN = {1: 20, 5: 12, 20: 6}
TRIALS: list[dict] = []


# ------------------------------------------------------------------- candidate pre-registrations
# (series, name, mechanism, construction, horizons, novelty features, EV Idea)
CANDIDATES = [
    ("DTWEXBGS", "dollar_funding_squeeze",
     "The broad trade-weighted dollar is the numeraire of global dollar FUNDING, not just a "
     "relative price. A sharp broad-dollar appreciation raises the cost of the offshore dollar "
     "borrowing that levered carry runs on, and levered carry unwinds are forced, not "
     "discretionary -- so a dollar squeeze should push a marginal, highly levered dollar-funded "
     "asset class down with a short lag.",
     "signal = 5-business-day log change in DTWEXBGS (a squeeze is a MOVE, not a level), "
     "z-scored by the harness; target = absolute BTC return over the next block. Absolute, not "
     "cross-sectional, because a funding shock is market-wide and has no asset-selection content.",
     (1, 5, 20), ("broad_dollar_shock", "dollar_funding", "btc_timing", "macro_overlay"),
     Idea(name="dollar_funding_squeeze", est_sharpe=0.3, breadth=1, capacity_usd=2e6,
          orthogonality=0.6, effort_h=6.0, tags=["new_orthogonal_data", "crowded_known"])),

    ("WALCL", "reserve_quantity_impulse",
     "The Fed's balance sheet is the QUANTITY of system reserves. Reserve creation/destruction is "
     "an inelastic quantity constraint on the marginal dollar available to bid risk assets -- a "
     "structural mechanism, not a sentiment read -- and the highest-beta sink for that marginal "
     "dollar should respond over weeks, the speed at which reserves actually settle through.",
     "signal = 4-week log change in WALCL, series LAGGED +2 calendar days for the Thursday "
     "16:30 ET H.4.1 release; target = absolute BTC return between consecutive weekly samples.",
     (1, 5), ("fed_balance_sheet", "reserve_quantity", "btc_timing", "liquidity_impulse"),
     Idea(name="reserve_quantity_impulse", est_sharpe=0.3, breadth=1, capacity_usd=2e6,
          orthogonality=0.5, effort_h=6.0, tags=["crowded_known"])),

    ("VIXCLS", "equity_vol_deleveraging",
     "VIX is the price of equity tail insurance and the input that mechanical vol-target and "
     "risk-parity books size on. A VIX spike mechanically shrinks their risk budget, and the "
     "highest-beta sleeve is cut first -- so the deleveraging is a forced flow, not a mood.",
     "signal = VIXCLS level, z-scored by the harness; target = absolute BTC return over the next "
     "block.",
     (1, 5, 20), ("equity_implied_vol", "risk_appetite", "btc_timing", "vol_target_deleveraging"),
     Idea(name="equity_vol_deleveraging", est_sharpe=0.3, breadth=1, capacity_usd=2e6,
          orthogonality=0.4, effort_h=6.0, tags=["crowded_known"])),

    ("T10Y2Y", "curve_slope_policy_path",
     "The 2s10s slope is the market's forward read of the policy path; a steepening driven by the "
     "front end prices expected easing, i.e. future reserve creation, ahead of the fact. A "
     "liquidity-sensitive asset should discount that path before the reserves arrive.",
     "signal = T10Y2Y level, z-scored by the harness; target = absolute BTC return over the next "
     "block.",
     (5, 20), ("yield_curve_slope", "policy_path", "btc_timing", "macro_overlay"),
     Idea(name="curve_slope_policy_path", est_sharpe=0.25, breadth=1, capacity_usd=2e6,
          orthogonality=0.5, effort_h=6.0, tags=["crowded_known"])),

    ("DGS10", "nominal_yield_opportunity_cost",
     "The 10y nominal yield is the opportunity cost of parking capital in a zero-cashflow "
     "store-of-value. When the risk-free alternative pays more, the hurdle for holding a "
     "non-yielding asset rises and the marginal allocator rotates out.",
     "signal = DGS10 level, z-scored by the harness; target = absolute BTC return over the next "
     "block.",
     (5, 20), ("nominal_yield", "opportunity_cost", "btc_timing", "macro_overlay"),
     Idea(name="nominal_yield_opportunity_cost", est_sharpe=0.25, breadth=1, capacity_usd=2e6,
          orthogonality=0.5, effort_h=6.0, tags=["crowded_known"])),
]

NOT_SCREENED = {
    "M2SL": "monthly (~192 obs once aligned to BTC), ~25-day publication lag, and FRED serves the "
            "CURRENT VINTAGE of a REVISED series -- a backtest would use numbers that were not "
            "knowable at the time (look-ahead through revision, which no alignment can fix). "
            "Untestable honestly from this archive; NOT a null result.",
}


# ------------------------------------------------------------------------------------- priors ---
def _prereg_priors() -> list[PriorIdea]:
    """The EV-rejected pre-registration cards -- the NEAREST priors to anything macro->crypto.

    The graveyard alone does not contain them (they died at the EV gate, before compute), so a
    novelty gate that only reads the graveyard would call a sixth macro overlay 'novel'.
    """
    txt = (ROOT / "docs/research/AXIS_PREREGISTRATIONS.md").read_text("utf-8")
    out: list[PriorIdea] = []
    for block in txt.split("\n### ")[1:]:
        head, _, body = block.partition("\n")
        m = re.match(r"(\S+)\s*\(([^)]+)\)", head.strip())
        if not m:
            continue
        out.append(PriorIdea(id=f"prereg:{m.group(1)}", category=m.group(2),
                             statement=body.replace("\n", " ")[:1500],
                             lesson="EV-gate REJECT before compute; the class is ledgered"))
    return out


def novelty(name: str, statement: str, features: tuple[str, ...]) -> dict:
    priors = _graveyard_priors() + _prereg_priors()
    r = hypothesis_novelty(statement, features=features, priors=priors)
    out = {"candidate": name, "novelty_score": round(r.novelty_score, 3),
           "nearest_id": r.nearest_id, "nearest_similarity": round(r.nearest_similarity, 3),
           "is_redundant": r.is_redundant, "nearest_lesson": (r.nearest_lesson or "")[:160],
           "n_priors": len(priors)}
    print(f"  NOVELTY {name:34s} score {out['novelty_score']:<6} "
          f"nearest={out['nearest_id']} sim={out['nearest_similarity']} "
          f"redundant={out['is_redundant']}")
    return out


# --------------------------------------------------------------------------------------- data ---
def fred_deep(sid: str, key: str) -> pd.Series:
    q = urllib.parse.urlencode({"series_id": sid, "api_key": key, "file_type": "json",
                                "observation_start": "1900-01-01"})
    req = urllib.request.Request(f"{FRED}?{q}", headers={"User-Agent": "quant-fred-screen/1.0"})
    with urllib.request.urlopen(req, timeout=45) as r:
        obs = json.loads(r.read()).get("observations", [])
    d = {pd.Timestamp(o["date"], tz="UTC"): float(o["value"])
         for o in obs if o.get("value") not in (".", "", None)}
    return pd.Series(d).sort_index()


def coinmetrics_btc() -> pd.Series:
    out: dict = {}
    with (ROOT / "data/coinmetrics_flows.jsonl").open(encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if r.get("asset") == "btc" and r.get("price_usd") and r.get("date"):
                out[pd.Timestamp(str(r["date"])[:10], tz="UTC")] = float(r["price_usd"])
    return pd.Series(out).sort_index()


# -------------------------------------------------------------------------------------- screen ---
def cell(name: str, sid: str, sig: np.ndarray, ret: np.ndarray, h: int, span_days: np.ndarray,
         extra: dict) -> dict:
    """One DSR-counted trial. Recorded whatever it prints -- including the certain-underpowered."""
    hd = float(np.mean(span_days)) * h
    r = stage_a_screen(sig, ret, name=f"fred_macro::{name}::h{h}b", zwin=ZWIN[h], horizon_days=hd)
    r.update({"axis": "fred_macro", "series": sid, "construction": name,
              "blocks_of_business_days": h, "mean_calendar_days_per_block": round(hd, 3),
              "zwin": ZWIN[h], "target_kind": "absolute BTC timing return", **extra})
    TRIALS.append(r)
    print(f"  {name:32s} h={h:2d}b({hd:5.1f}d) n={r.get('n'):5d} IC={r.get('ic'):+.4f} "
          f"same={r.get('same_period_corr'):+.3f} resid={r.get('residual_ic'):+.4f} "
          f"momSh={r.get('sharpe_momentum'):+.2f} n_eff={r.get('n_eff')} "
          f"mdi={r.get('min_detectable_ic')} pw={r.get('powered')} -> {r['verdict']}")
    return r


def transform(sid: str, s: pd.Series) -> pd.Series:
    """The pre-declared construction per series (see CANDIDATES)."""
    if sid == "DTWEXBGS":
        return np.log(s).diff(5).dropna()                    # 5-business-day dollar move
    if sid == "WALCL":
        lagged = pd.Series(s.to_numpy(), index=s.index + pd.Timedelta(days=2))   # release lag
        return np.log(lagged).diff(4).dropna()               # 4-week reserve impulse
    return s.dropna()                                        # levels: VIXCLS / T10Y2Y / DGS10


def main() -> None:
    key = json.loads((ROOT / "data/secrets/fred.json").read_text("utf-8"))["key"]
    btc = coinmetrics_btc()
    print(f"BTC leg (coinmetrics daily close): n={len(btc)} "
          f"{btc.index.min().date()} -> {btc.index.max().date()}\n")

    print("=" * 100)
    print("NOVELTY GATE (before compute) -- graveyard + live sleeves + EV-rejected prereg cards")
    print("=" * 100)
    nov = {c[1]: novelty(c[1], f"{c[2]} {c[3]}", c[5]) for c in CANDIDATES}

    print("\n" + "=" * 100)
    print("EV GATE (pre-registered, honest inputs, no tuning-to-pass)")
    print("=" * 100)
    ev = {}
    for c in CANDIDATES:
        e = ev_score(c[6])
        ev[c[1]] = e
        print(f"  EV {c[1]:34s} {e['ev']:<8} p_survive={e['p_survive']:<7} -> {e['verdict']}")

    deep: dict[str, list] = {}
    print("\n" + "=" * 100)
    print("STAGE-A SCREENS (audited harness, artifact gate baked in, NO clock passed on any cell)")
    print("=" * 100)
    for sid, name, mech, _constr, horizons, _feat, _idea in CANDIDATES:
        raw = fred_deep(sid, key)
        deep[sid] = [[d.strftime("%Y-%m-%d"), v] for d, v in raw.items()]
        s = transform(sid, raw)
        common = s.index.intersection(btc.index)
        if len(common) < 60:
            TRIALS.append({"axis": "fred_macro", "series": sid, "construction": name,
                           "verdict": "INSUFFICIENT-DATA", "n": len(common),
                           "note": f"{len(common)} aligned obs < 60"})
            print(f"  {name}: only {len(common)} aligned obs -- INSUFFICIENT-DATA")
            continue
        sv = s.reindex(common).to_numpy()
        bv = btc.reindex(common).to_numpy()
        gap = np.diff(common.to_numpy().astype("datetime64[D]").astype(int))
        print(f"\n  {sid} raw n={len(raw)} {raw.index.min().date()}->{raw.index.max().date()} | "
              f"aligned {len(common)} obs {common.min().date()}->{common.max().date()} | "
              f"mean spacing {gap.mean():.2f}d")
        print(f"    mechanism: {mech[:150]}")
        for h in horizons:
            idx = block_idx(len(common), h)
            b_h = bv[idx]
            ret_h = np.zeros(len(idx))
            ret_h[1:] = b_h[1:] / b_h[:-1] - 1.0
            cell(name, sid, sv[idx], ret_h, h, gap,
                 {"aligned_obs": len(common), "n_blocks": len(idx),
                  "mdi_block": round(float(1.96 / np.sqrt(max(len(idx), 1))), 4),
                  "span": f"{common.min().date()}..{common.max().date()}",
                  "novelty": nov[name], "ev": ev[name]})

    DEEP.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                                "note": "deep FRED history fetched for RESEARCH only -- the daily "
                                        "collector (scripts/collect_fred_macro.py, 1200d window) "
                                        "and web/fred_macro.json are untouched",
                                "series": deep}, indent=1), "utf-8")
    payload = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "stage": "A (zero promotion authority) -- no cell was passed a clock; none can start one",
        "duty": "generation_due.md line 5 -- fred_macro family scoped generate run",
        "cadence_note": "gen_done_fred_macro_family has been set since 2026-07-17T08:55:24Z; the "
                        "generation_due.md snapshot (2026-07-16) is stale. The PAPER duty was "
                        "closed then; this run adds the empirical screens that were never done.",
        "prior_ev_rejections": "macro->crypto EV-rejected 6x: 3 FRED overlays 2026-07-17 "
                               "(0.004-0.013); dxy_shock_beta_rotation 0.0052, "
                               "risk_regime_rotation 0.0027, net_liquidity_impulse 0.0026 "
                               "(2026-07-22, 'fed axis ledgered exhausted').",
        "timestamp_alignment": __doc__.split("TIMESTAMP ALIGNMENT")[1].split("SAMPLING")[0].strip(),
        "sampling": __doc__.split("\nSAMPLING:")[1].split("\n\n")[0].strip(),
        "not_screened": NOT_SCREENED,
        "novelty_gate": list(nov.values()),
        "ev_gate": list(ev.values()),
        "trials": TRIALS,
    }
    OUT.write_text(json.dumps(payload, indent=1), "utf-8")
    print(f"\n{len(TRIALS)} DSR-counted trials -> {OUT}")
    for v in sorted({t["verdict"] for t in TRIALS}):
        print(f"  {v}: {sum(1 for t in TRIALS if t['verdict'] == v)}")
    print(f"  deep FRED history archived -> {DEEP}")


if __name__ == "__main__":
    main()

```

### scripts/stage_a_executor.py
```python
"""STAGE-A EXECUTOR -- actually RUN the ranked queue. Ranking is not utilisation.

THE GAP THIS CLOSES. blindspot_max finds 214 unknown-unknowns; conversion_engine ranks them and
injects 40 into the schedule; and then nothing happens. Only stageb_capacity reads that schedule,
and only to COUNT it. I had moved the problem one link down the chain -- from a list nobody reads
to a ranked queue nobody executes -- and called it utilisation.

This runs a genuine screen on the top unscreened candidates every cycle: aligns the field to a
forward return, computes rank IC, and puts the result through the leakage contract that already
exists (reverse-causality, orthogonalisation to the same-period confound, suspect magnitude,
shift test). Verdicts persist so a candidate is never re-screened by accident, and the queue
drains instead of accumulating.

STAGE-A LAW, UNCHANGED AND ENFORCED IN CODE: this has ZERO promotion authority. It can mark a
candidate SCREEN-PASS. It cannot start a forward clock, size a position, or touch capital. A pass
here means "worth one of five scarce Stage-B slots", nothing more.

HONESTY RAILS:
  * a candidate with fewer than _MIN_N aligned observations returns UNDERPOWERED, never a verdict
  * any leakage flag downgrades the result regardless of how good the IC looks
  * verdicts record n, IC, t, residual IC and every flag, so a pass can be audited later
"""
from __future__ import annotations

import json
import math
import pathlib
import sys
from datetime import UTC, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

CIO = ROOT / "data/research_cio.json"
LEDGER = ROOT / "data/stage_a_verdicts.jsonl"
PRICE_SRC = ROOT / "data/coinmetrics_flows.jsonl"
_MIN_N = 60
_BATCH = 6                    # screened per cycle; unbounded queue, bounded compute per run


def _rows(p: pathlib.Path, cap: int = 20000):
    out = []
    try:
        with p.open("r", encoding="utf-8", errors="ignore") as fh:
            for i, ln in enumerate(fh):
                if i >= cap:
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


def _price_series() -> dict[str, float]:
    """Daily BTC close from the coinmetrics archive -- the desk's longest clean price history."""
    out = {}
    for r in _rows(PRICE_SRC):
        if r.get("asset") == "btc" and r.get("price_usd") and r.get("date"):
            out[str(r["date"])[:10]] = float(r["price_usd"])
    return out


def _spearman(a, b):
    n = len(a)
    if n < 8:
        return 0.0, 0.0
    ra = sorted(range(n), key=lambda i: a[i])
    rb = sorted(range(n), key=lambda i: b[i])
    A, B = [0.0] * n, [0.0] * n
    for rank, i in enumerate(ra):
        A[i] = rank
    for rank, i in enumerate(rb):
        B[i] = rank
    ma, mb = sum(A) / n, sum(B) / n
    va = math.sqrt(sum((x - ma) ** 2 for x in A))
    vb = math.sqrt(sum((x - mb) ** 2 for x in B))
    if va == 0 or vb == 0:
        return 0.0, 0.0
    r = sum((A[i] - ma) * (B[i] - mb) for i in range(n)) / (va * vb)
    t = r * math.sqrt((n - 2) / max(1e-12, 1 - r * r))
    return r, t


def screen(file_name: str, field: str, px: dict) -> dict:
    """One genuine screen: field(t) vs forward return(t+1), with the leakage contract applied."""
    rows = _rows(ROOT / "data" / file_name)
    series = {}
    for r in rows:
        d = r.get("date") or r.get("ts")
        v = r.get(field)
        if d and isinstance(v, (int, float)) and not isinstance(v, bool):
            series[str(d)[:10]] = float(v)
    dates = sorted(set(series) & set(px))
    if len(dates) < _MIN_N:
        return {"verdict": "UNDERPOWERED", "n": len(dates),
                "note": f"{len(dates)} aligned days < {_MIN_N} required"}

    xs, fwd, same = [], [], []
    for i in range(len(dates) - 1):
        d0, d1 = dates[i], dates[i + 1]
        p0, p1 = px[d0], px[d1]
        if p0 <= 0:
            continue
        xs.append(series[d0])
        fwd.append((p1 - p0) / p0)
        prev = px[dates[i - 1]] if i > 0 else p0
        same.append((p0 - prev) / prev if prev > 0 else 0.0)
    if len(xs) < _MIN_N:
        return {"verdict": "UNDERPOWERED", "n": len(xs), "note": "insufficient aligned pairs"}

    ic, t = _spearman(xs, fwd)
    flags = []
    try:
        from leakage_detector import audit
        a = audit(xs, fwd, same, name=f"{file_name}:{field}")
        flags = a.get("flags", [])
        resid = a.get("notes", {}).get("residual_ic")
    except Exception:  # blind-except intentional (BLE001)
        resid = None

    if flags:
        v = "SCREEN-FLAGGED"
    elif abs(t) >= 2.5 and abs(ic) >= 0.05:
        v = "SCREEN-PASS"
    elif abs(t) >= 1.5:
        v = "SCREEN-WEAK"
    else:
        v = "SCREEN-NULL"
    return {"verdict": v, "n": len(xs), "ic": round(ic, 4), "t": round(t, 2),
            "residual_ic": resid, "flags": flags}


def main() -> None:
    px = _price_series()
    if len(px) < 200:
        raise SystemExit("price history unavailable -- refusing to screen against nothing")

    done = set()
    if LEDGER.exists():
        for ln in LEDGER.read_text("utf-8").splitlines():
            try:
                done.add(json.loads(ln)["candidate"])
            except Exception:  # blind-except intentional (BLE001)
                continue

    sched = (json.loads(CIO.read_text("utf-8")) if CIO.exists() else {}).get("schedule", [])
    queue = [s for s in sched if s.get("origin") == "conversion_engine"
             and s.get("name") not in done and ":" in str(s.get("name", ""))]

    print("=== STAGE-A EXECUTOR -- running the queue, not ranking it ===")
    print("    ZERO promotion authority: a pass earns one of five scarce Stage-B slots, never")
    print("    capital. Ranking was never utilisation.\n")
    print(f"  price history {len(px)} days | {len(done)} already screened | "
          f"{len(queue)} unscreened in queue\n")
    if not queue:
        print("  queue drained -- every conversion candidate has a verdict.")
        return

    out = []
    for s in queue[:_BATCH]:
        name = s["name"]
        fn, _, fld = name.partition(":")
        res = screen(fn, fld, px)
        rec = {"ts": datetime.now(tz=UTC).isoformat(), "candidate": name, **res}
        out.append(rec)
        extra = (f"IC {res.get('ic'):+.4f} t {res.get('t'):+.2f}"
                 if res.get("ic") is not None else res.get("note", ""))
        print(f"  {res['verdict']:<16} {name[:46]:<46} n={res['n']:<5} {extra}")
        for f in res.get("flags", [])[:1]:
            print(f"                   leak: {f[:78]}")

    with LEDGER.open("a", encoding="utf-8") as fh:
        for r in out:
            fh.write(json.dumps(r) + "\n")

    passes = [r for r in out if r["verdict"] == "SCREEN-PASS"]
    print(f"\n  {len(out)} screened this cycle, {len(passes)} PASS, "
          f"{len(queue)-len(out)} still queued")
    if passes:
        print("  PASS candidates are eligible for a Stage-B slot -- eligibility, not promotion.")
        print("  A human or the allocator picks from them; nothing here starts a clock.")
    print(f"  -> {LEDGER}")


if __name__ == "__main__":
    main()

```
