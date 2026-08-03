# AUDIT SHARD 13/13 -- seat meituan/longcat-2.0

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

### libs/alpha_factory/crowding_intelligence.py
```python
"""Crowding intelligence — steer research away from crowded concepts.

Blends strategy, factor, and style crowding into a 0..1 score and a research-priority multiplier
(<1 dampens crowded concepts, >0 favours uncrowded ones).
"""

from __future__ import annotations

from libs.alpha_factory.models import CrowdingEstimate


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class CrowdingIntelligence:
    """Estimates concept crowding and the research-priority adjustment it implies."""

    def assess(
        self,
        *,
        strategy_crowding: float,
        factor_crowding: float,
        style_crowding: float,
    ) -> CrowdingEstimate:
        score = _clip01(
            0.4 * strategy_crowding + 0.3 * factor_crowding + 0.3 * style_crowding
        )
        return CrowdingEstimate(
            strategy_crowding=_clip01(strategy_crowding),
            factor_crowding=_clip01(factor_crowding),
            style_crowding=_clip01(style_crowding),
            crowding_score=score,
            priority_multiplier=1.0 - score,
        )

```

### libs/alpha_factory/hypothesis_novelty.py
```python
"""Pre-compute hypothesis novelty gate — RD-Agent trace-conditioning, applied to avoid re-digging.

RD-Agent conditions every new proposal on the full trace of past experiments; crucially it does not
re-propose ideas close to ones already tried and failed. This desk's documented objection to
automated generation (`GAP_ANALYSIS.md`) is exactly that risk: a generator over the same data
re-discovers the graveyard at real compute cost. `strategy_similarity_engine` already de-dupes but
only AFTER a strategy is built (it needs a returns series); this gate runs BEFORE compute, scoring a
candidate hypothesis's statement + feature set against the durable record of already-FAILED ideas,
so scarce backtest compute and trials-ledger budget go only to genuinely novel hypotheses.

It also serves the live frontier-miner / prospector diggers (not just the orphaned auto-generator):
any workflow that proposes a hypothesis can screen it against the graveyard first. Advisory by
design — it returns a novelty score and the nearest prior failure (with its lesson), never a hard
block. No AI-oracle: deterministic set/token similarity, no model deciding anything.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

_TOKEN = re.compile(r"[a-z0-9]+")


class PriorIdea(BaseModel):
    """A previously-tested (typically failed) idea to screen a candidate against."""

    model_config = ConfigDict(frozen=True)

    id: str
    statement: str
    category: str = ""
    features: tuple[str, ...] = ()
    lesson: str | None = None


class NoveltyResult(BaseModel):
    """How novel a candidate is versus the graveyard, and the nearest prior it resembles."""

    model_config = ConfigDict(frozen=True)

    novelty_score: float  # 1.0 = nothing like it tried; 0.0 = exact match to a prior
    nearest_id: str | None
    nearest_similarity: float
    nearest_lesson: str | None
    is_redundant: bool

    def __bool__(self) -> bool:
        # truthy == worth testing (novel enough); redundant candidates are falsy
        return not self.is_redundant


def _tokens(text: str) -> set[str]:
    """Content tokens of a statement: lowercase alnum words of length >= 3 (crude stopword drop)."""
    return {t for t in _TOKEN.findall(text.lower()) if len(t) >= 3}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def _similarity(
    statement: str, features: Sequence[str], prior: PriorIdea
) -> float:
    """Blend statement-token overlap with feature-set overlap.

    Features encode the mechanism, so when both sides declare them they dominate (0.7) — the same
    mechanism in different words is still a re-test. When features are absent on either side, fall
    back to statement-token similarity alone.
    """
    stmt_sim = _jaccard(_tokens(statement), _tokens(prior.statement))
    if features and prior.features:
        feat_sim = _jaccard(set(features), set(prior.features))
        return 0.7 * feat_sim + 0.3 * stmt_sim
    return stmt_sim


def hypothesis_novelty(
    statement: str,
    *,
    features: Sequence[str] = (),
    priors: Sequence[PriorIdea],
    redundant_threshold: float = 0.7,
) -> NoveltyResult:
    """Score a candidate hypothesis against prior (failed) ideas before spending compute on it.

    Returns the nearest prior, the similarity to it, a novelty score (``1 - nearest_similarity``),
    and whether the candidate is redundant (``nearest_similarity >= redundant_threshold``). With no
    priors the candidate is maximally novel. Advisory only — the caller decides whether to proceed.
    """
    nearest_id: str | None = None
    nearest_sim = 0.0
    nearest_lesson: str | None = None
    for prior in priors:
        sim = _similarity(statement, features, prior)
        if sim > nearest_sim:
            nearest_sim, nearest_id, nearest_lesson = sim, prior.id, prior.lesson
    return NoveltyResult(
        novelty_score=1.0 - nearest_sim,
        nearest_id=nearest_id,
        nearest_similarity=nearest_sim,
        nearest_lesson=nearest_lesson,
        is_redundant=nearest_sim >= redundant_threshold,
    )

```

### libs/autodiscovery/reports.py
```python
"""Automated report builders over the candidate ledger (pure, deterministic).

Feed the daily / weekly / monthly cadence. Honest by construction: every count comes from the
durable ``research_candidates`` table, survivors included or zero.
"""

from __future__ import annotations

from typing import Any

from libs.autodiscovery.memory import CandidateStore


def _rejection_histogram(store: CandidateStore) -> dict[str, int]:
    hist: dict[str, int] = {}
    for rec in store.all():
        if rec.survived or not rec.rejection_reason:
            continue
        body = rec.rejection_reason.removeprefix("failed: ")
        for gate in (g.strip() for g in body.split(",") if g.strip()):
            hist[gate] = hist.get(gate, 0) + 1
    return hist


def research_report(store: CandidateStore) -> dict[str, Any]:
    return {
        "total_candidates": store.total(),
        "by_family": store.family_counts(),
        "by_status": store.status_counts(),
        "survivors": len(store.survivors()),
    }


def failure_analysis_report(store: CandidateStore) -> dict[str, Any]:
    return {"rejection_by_gate": _rejection_histogram(store)}


def survivor_report(store: CandidateStore) -> dict[str, Any]:
    return {
        "survivors": [
            {"id": r.id, "family": r.family, "subtype": r.subtype, "symbol": r.symbol,
             "annual_sharpe": r.metrics.annual_sharpe, "dsr": r.metrics.dsr}
            for r in store.survivors()
        ]
    }


def family_performance_report(store: CandidateStore) -> dict[str, Any]:
    counts = store.family_counts()
    survivors_by_family: dict[str, int] = {}
    for r in store.survivors():
        survivors_by_family[r.family] = survivors_by_family.get(r.family, 0) + 1
    return {
        "families": {
            fam: {"tested": n, "survivors": survivors_by_family.get(fam, 0),
                  "survivor_rate": survivors_by_family.get(fam, 0) / n if n else 0.0}
            for fam, n in counts.items()
        }
    }


def discovery_efficiency_report(store: CandidateStore) -> dict[str, Any]:
    total = store.total()
    survivors = len(store.survivors())
    return {
        "total_tested": total,
        "survivors": survivors,
        "survivor_rate": survivors / total if total else 0.0,
    }


def pipeline_health_report(store: CandidateStore) -> dict[str, Any]:
    return {"funnel": store.status_counts(), "total": store.total()}

```

### libs/data/prediction_markets.py
```python
"""Prediction-market data (Polymarket) -- the one funds-barred, solo-advantaged information domain.

Pulls RESOLVED binary markets (Gamma API) + their pre-resolution price history (CLOB API) so we can
test calibration / favorite-longshot bias: does the de-vigged market probability match the realized
outcome frequency? Free, public, read-only. Point-in-time: only prices strictly BEFORE resolution
are used; the outcome is known only after settlement.
"""

from __future__ import annotations

import json
import time
import urllib.request
from typing import Any

import pandas as pd

_GAMMA = "https://gamma-api.polymarket.com"
_CLOB = "https://clob.polymarket.com"


def _get(url: str, *, tries: int = 4) -> Any:
    last: Exception | None = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "quant-platform/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except Exception as exc:
            last = exc
            time.sleep(1.0)
    raise RuntimeError(f"GET failed: {url} :: {last}")


def fetch_resolved_markets(*, max_markets: int = 1500) -> list[dict[str, Any]]:
    """Resolved binary (Yes/No) markets, highest-volume first. Returns clean 0/1 outcomes only."""
    out: list[dict[str, Any]] = []
    offset = 0
    while len(out) < max_markets:
        url = (f"{_GAMMA}/markets?closed=true&limit=500&offset={offset}"
               f"&order=volumeNum&ascending=false")
        try:
            batch = _get(url)
        except RuntimeError:
            break  # API pagination cap (422) -> return what we have
        if not batch:
            break
        for m in batch:
            try:
                outcomes = json.loads(m.get("outcomes", "[]"))
                prices = json.loads(m.get("outcomePrices", "[]"))
                tokens = json.loads(m.get("clobTokenIds", "[]"))
            except (json.JSONDecodeError, TypeError):
                continue
            if outcomes != ["Yes", "No"] or m.get("umaResolutionStatus") != "resolved":
                continue
            if prices not in (["1", "0"], ["0", "1"]) or len(tokens) != 2:
                continue
            out.append({
                "question": m.get("question", ""), "yes_token": tokens[0],
                "outcome": float(prices[0]),          # 1.0 if Yes won, else 0.0
                "end": m.get("endDate", ""), "start": m.get("startDate", ""),
                "volume": float(m.get("volumeNum", 0.0) or 0.0),
            })
        offset += 500
        time.sleep(0.2)
    return out[:max_markets]


def fetch_price_history(token_id: str, *, fidelity: int = 720) -> pd.DataFrame:
    """YES-token price history (implied probability over time). fidelity in minutes."""
    url = f"{_CLOB}/prices-history?market={token_id}&interval=max&fidelity={fidelity}"
    data = _get(url)
    hist = data.get("history", []) if isinstance(data, dict) else []
    if not hist:
        return pd.DataFrame()
    return pd.DataFrame({
        "ts": pd.to_datetime([h["t"] for h in hist], unit="s", utc=True),
        "p": [float(h["p"]) for h in hist],
    })


def implied_prob_before(
    history: pd.DataFrame, end: pd.Timestamp, *, lead_days: float
) -> float | None:
    """Last YES price >= ``lead_days`` before resolution (no look-ahead); None if unavailable."""
    if history.empty:
        return None
    cutoff = end - pd.Timedelta(days=lead_days)
    prior = history[history["ts"] <= cutoff]
    if prior.empty:
        return None
    return float(prior["p"].iloc[-1])

```

### libs/discovery/capacity.py
```python
"""capacity_optimization_engine — maximum deployable capital and a slippage curve.

Optimizes CAGR x Capacity, not CAGR alone: a strategy that is brilliant at $10k and dead at $1M
is scored at its real capacity. Estimates the size at which market impact erodes the edge.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict

from libs.discovery.errors import DiscoveryError


class CapacityResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    capacity_usd: float
    slippage_curve: dict[float, float]  # notional -> expected slippage (fraction)
    market_impact_bps_at_capacity: float


def capacity_estimate(
    *,
    adv_usd: float,
    participation_cap: float = 0.01,
    turnover_per_year: float = 50.0,
    impact_coefficient: float = 0.1,
    edge_bps: float = 10.0,
) -> CapacityResult:
    """Estimate deployable capital where square-root market impact stays below the edge."""
    if adv_usd <= 0:
        raise DiscoveryError("adv_usd must be positive")
    # Per-trade tradeable notional from participation, annualized by turnover.
    per_trade = adv_usd * participation_cap
    # Square-root impact model: impact_bps = coeff * sqrt(notional / adv) * 1e4.
    # Capacity = size where impact_bps == edge_bps.
    capacity_per_trade = adv_usd * (edge_bps / (impact_coefficient * 1e4)) ** 2
    capacity_usd = min(per_trade, capacity_per_trade) * max(1.0, 252.0 / turnover_per_year)

    curve_points = [per_trade * f for f in (0.25, 0.5, 1.0, 2.0, 4.0)]
    slippage_curve = {
        float(round(notional, 2)): float(
            impact_coefficient * np.sqrt(max(notional, 0.0) / adv_usd)
        )
        for notional in curve_points
    }
    impact_at_capacity = float(
        impact_coefficient * np.sqrt(max(capacity_usd, 0.0) / adv_usd) * 1e4
    )
    return CapacityResult(
        capacity_usd=capacity_usd,
        slippage_curve=slippage_curve,
        market_impact_bps_at_capacity=impact_at_capacity,
    )

```

### libs/execution/__init__.py
```python
"""``libs.execution`` — the MT5 execution engine.

Submits approved orders to a broker gateway with idempotency and safe retries, tracks positions,
reconciles against the broker (the source of truth), and journals every event immutably. No
duplicate orders; safe restart; fail closed.
"""

from __future__ import annotations

from libs.execution.algos import ChildOrder, ExecutionPlan, ExecutionScheduler
from libs.execution.broker import (
    BrokerGateway,
    BrokerOrderResult,
    BrokerPosition,
    MT5Broker,
    OrderRequest,
)
from libs.execution.ea_bridge import EABridge, dump_record, load_record
from libs.execution.engine import (
    ExecStatus,
    ExecutionEngine,
    ExecutionResult,
    ReconciliationReport,
)
from libs.execution.errors import (
    BrokerError,
    BrokerTimeout,
    ExecutionError,
    ReconciliationError,
    TransientBrokerError,
)
from libs.execution.journal import TradeJournal
from libs.execution.paper_broker import PaperBroker
from libs.execution.retry import retry_call
from libs.execution.tca import PostTradeTCA, SlippageAttribution, TcaResult

__all__ = [  # noqa: RUF022  # grouped by concern
    # broker
    "BrokerGateway",
    "OrderRequest",
    "BrokerOrderResult",
    "BrokerPosition",
    "MT5Broker",
    "PaperBroker",
    "EABridge",
    "dump_record",
    "load_record",
    # engine
    "ExecutionEngine",
    "ExecutionResult",
    "ReconciliationReport",
    "ExecStatus",
    # execution algos
    "ExecutionScheduler",
    "ExecutionPlan",
    "ChildOrder",
    # post-trade TCA
    "PostTradeTCA",
    "SlippageAttribution",
    "TcaResult",
    # journal + retry
    "TradeJournal",
    "retry_call",
    # errors
    "ExecutionError",
    "BrokerError",
    "TransientBrokerError",
    "BrokerTimeout",
    "ReconciliationError",
]

```

### libs/execution/errors.py
```python
"""Execution-layer exceptions."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class ExecutionError(QuantPlatformError):
    """Generic execution error (missing approval, unknown order, invalid request)."""


class BrokerError(ExecutionError):
    """The broker reported an error."""


class TransientBrokerError(BrokerError):
    """A retryable broker error (requote, momentary disconnect) — no order was placed."""


class BrokerTimeout(BrokerError):
    """An *ambiguous* broker timeout: the order may or may not have been placed.

    Never assume a fill. The caller must reconcile against the broker before acting.
    """


class ReconciliationError(ExecutionError):
    """Internal state diverged from the broker (the source of truth) — fail closed."""

```

### libs/factory/registry.py
```python
"""Factory governance: dataset registry, edge-family targets, Sharpe milestones, paid-data ranking.

This is the *information-advantage* ledger that turns the sleeve/portfolio machinery into a
continuously-evolving research org. It does NOT rebuild research; it scores and prioritizes.
All scores are honest explicit estimates (0..1 unless noted), not fabricated precision -- they
drive "what to research next", not deployment.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------- edge families (breadth target)
# A mature factory has >= TARGET_PER_FAMILY independent sleeves in each family.
TARGET_PER_FAMILY = 3
EDGE_FAMILIES = (
    "trend", "momentum", "carry", "positioning", "macro",
    "relative_value", "volatility", "seasonality", "flow", "structural",
)

# Map existing sleeve names -> family (used to measure breadth from the portfolio report).
SLEEVE_FAMILY = {
    "trend_all": "trend", "crypto_trend": "trend", "index_trend": "trend",
    "xsec_mom_all": "momentum", "metals_mom": "momentum", "fx_mom": "momentum",
    "gold_silver_rv": "relative_value", "gold_plat_rv": "relative_value",
    "wti_brent_rv": "relative_value",
    "cot_positioning": "positioning", "cot_timeseries": "positioning",
    "swap_carry": "carry", "macro_calendar": "seasonality",
    "gold_crisis_hedge": "macro",
    # ETF sleeves (free expansion) fill the previously-empty macro/structural/flow families
    "rates_trend": "macro", "curve_rv": "structural", "credit_rv": "structural",
    "sector_rotation": "flow",
}

# Portfolio Sharpe milestones the factory drives toward.
MILESTONES = (0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0)


@dataclass(frozen=True)
class Dataset:
    name: str
    source: str
    frequency: str
    cost: str                      # "free" | "low" | "med" | "high"
    pit: bool                      # point-in-time reconstructable (no look-ahead risk)
    status: str                    # "in_use" | "reachable" | "blocked" | "candidate"
    families: tuple[str, ...]      # edge families it could unlock
    exp_alpha: float               # 0..1 expected standalone edge strength
    exp_diversification: float     # 0..1 orthogonality to current book
    impl_difficulty: float         # 0..1 (1 = hard)
    notes: str = ""

    def roi(self) -> float:
        """Expected portfolio ROI = (impact x orthogonality) discounted by cost & difficulty."""
        cost_pen = {"free": 1.0, "low": 0.85, "med": 0.6, "high": 0.35}.get(self.cost, 0.5)
        return round(self.exp_alpha * (0.4 + 0.6 * self.exp_diversification)
                     * cost_pen * (1.0 - 0.5 * self.impl_difficulty), 3)


# Curated dataset registry: what we use, what's reachable, what's blocked, and the paid path.
DATASETS: tuple[Dataset, ...] = (
    Dataset("MT5 OHLC (30 instruments)", "IC Markets MT5", "D1", "free", True, "in_use",
            ("trend", "momentum", "relative_value", "seasonality"), 0.55, 0.2, 0.2,
            "core price lake; trend/momentum already mined to ~0.6 ceiling"),
    Dataset("CFTC Commitments of Traders", "publicreporting.cftc.gov", "weekly", "free", True,
            "in_use", ("positioning",), 0.35, 0.7, 0.3, "orthogonal but weak standalone (~0.1)"),
    Dataset("Broker swap rates", "MT5 symbol_info", "daily", "free", False, "in_use",
            ("carry",), 0.45, 0.75, 0.4, "no history -> forward-only; the live carry hope"),
    Dataset("Binance funding/OI", "Binance fapi", "8h", "free", True, "in_use",
            ("carry", "flow"), 0.8, 0.6, 0.3, "best edge (0.96) but NOT MT5-executable (cashflow)"),
    Dataset("US Treasury par yields", "home.treasury.gov", "daily", "free", True, "reachable",
            ("carry", "macro"), 0.4, 0.6, 0.4, "rates curve; SSL-blocked here, retry path"),
    Dataset("ECB / central-bank rates", "data-api.ecb.europa.eu", "daily", "free", True,
            "reachable", ("carry", "macro"), 0.45, 0.65, 0.5, "EUR reachable; FX carry"),
    Dataset("FRED macro series", "api.stlouisfed.org", "daily", "free", True, "reachable",
            ("macro", "carry"), 0.5, 0.7, 0.4,
            "collector wired 2026-07-16 (api host OK from VPS); key pending (operator)"),
    # ---- FREE expansion candidates (no budget): the real remaining levers ----
    Dataset("MT5 ETF CFDs (TLT/IEF/SHY/LQD/EMB + sectors)", "IC Markets MT5", "D1", "free", True,
            "in_use", ("trend", "macro", "structural", "flow"), 0.15, 0.7, 0.3,
            "ingested; sleeves DON'T clear -- price-only CFD (dividend drag) corrupts bond ETF "
            "trend (-1.2); sector/curve/credit ~0. Tested, mostly rejected."),
    Dataset("MT5 cold indices (NAS100/GER40/JPN225/EU50/HK50)", "IC Markets MT5", "D1", "free",
            True, "candidate", ("trend", "momentum", "seasonality"), 0.4, 0.4, 0.2,
            "more index breadth for rotation + cross-sectional; warm the terminal then ingest"),
    Dataset("CFTC disaggregated / TFF", "publicreporting.cftc.gov", "weekly", "free", True,
            "candidate", ("positioning",), 0.35, 0.7, 0.4,
            "managed-money / leveraged-funds split: cleaner than legacy non-comm"),
    Dataset("Price-derived seasonality", "(from MT5 lake)", "D1", "free", True, "candidate",
            ("seasonality",), 0.25, 0.55, 0.2,
            "turn-of-month done (~0.1); day-of-week / pre-holiday / month effects untested"),
)


def free_next_priorities(top_n: int = 6) -> list[dict[str, object]]:
    """Free/reachable datasets ranked by expected portfolio ROI (the only path -- no budget)."""
    free = [d for d in DATASETS if d.cost == "free" and d.status in {"candidate", "reachable"}]
    ranked = sorted(free, key=lambda d: d.roi(), reverse=True)
    return [{"name": d.name, "status": d.status, "families": list(d.families), "roi": d.roi(),
             "pit": d.pit, "notes": d.notes} for d in ranked[:top_n]]

# Paid datasets ranked by expected portfolio-Sharpe contribution. DEFERRED: no budget -> the factory
# only recommends these once the free path is 100% exhausted. Kept for honest completeness.
@dataclass(frozen=True)
class PaidDataset:
    name: str
    source: str
    cost_usd_per_month: str
    families: tuple[str, ...]
    exp_sharpe_contribution: float   # expected ADD to portfolio Sharpe if it works
    confidence: float                # 0..1
    impl_difficulty: float           # 0..1
    rationale: str = ""

    def priority(self) -> float:
        return round(self.exp_sharpe_contribution * self.confidence
                     * (1.0 - 0.4 * self.impl_difficulty), 3)


PAID_DATASETS: tuple[PaidDataset, ...] = (
    PaidDataset("Futures continuous + term structure", "Nasdaq Data Link (Quandl)", "$50-100",
                ("carry", "structural"), 0.30, 0.6, 0.4,
                "roll-yield carry: real, uncorrelated to trend; MT5-tradeable legs"),
    PaidDataset("Options IV / vol surface", "ORATS / CBOE DataShop", "$100-300",
                ("volatility",), 0.35, 0.55, 0.7,
                "vol-risk-premium: highest premium, but MT5 can't trade options directly"),
    PaidDataset("Economic surprise / calendar (actual vs survey)", "Econoday / TradingEconomics",
                "$50-150", ("macro",), 0.20, 0.5, 0.4,
                "macro-surprise event drift on FX/indices/gold; genuinely orthogonal"),
    PaidDataset("ETF / fund flows", "State Street / ETF.com Pro", "$100-500", ("flow",), 0.20, 0.4,
                0.6, "flow-driven index/sector rotation; capacity-rich but noisy"),
    PaidDataset("Cross-exchange crypto basis/funding history", "Kaiko / Amberdata", "$100-500",
                ("carry", "flow"), 0.25, 0.5, 0.5,
                "deeper funding/basis history to harden the carry sleeve before live"),
)


@dataclass
class MilestoneStatus:
    current: float
    next_milestone: float | None
    gap: float
    families_complete: int
    families_total: int = len(EDGE_FAMILIES)
    bottleneck: str = ""
    notes: list[str] = field(default_factory=list)


def milestone_path(current_sharpe: float, family_counts: dict[str, int]) -> MilestoneStatus:
    nxt = next((m for m in MILESTONES if m > current_sharpe + 1e-9), None)
    complete = sum(1 for f in EDGE_FAMILIES if family_counts.get(f, 0) >= TARGET_PER_FAMILY)
    # the bottleneck family = the one most under target that is also genuinely orthogonal
    deficits = {f: TARGET_PER_FAMILY - family_counts.get(f, 0) for f in EDGE_FAMILIES}
    bottleneck = max(deficits, key=lambda f: deficits[f]) if deficits else ""
    return MilestoneStatus(
        current=round(current_sharpe, 3),
        next_milestone=nxt, gap=round((nxt - current_sharpe), 3) if nxt else 0.0,
        families_complete=complete, bottleneck=bottleneck,
    )


def best_dataset_priorities(top_n: int = 5) -> list[dict[str, object]]:
    ranked = sorted(DATASETS, key=lambda d: d.roi(), reverse=True)
    return [{"name": d.name, "cost": d.cost, "status": d.status, "families": list(d.families),
             "roi": d.roi(), "pit": d.pit, "notes": d.notes} for d in ranked[:top_n]]


def information_advantage_score(
    *, datasets_in_use: int, mechanisms: int, active_sleeves: int, validated_sleeves: int,
    orthogonal_sleeves: int, archive_days: int,
) -> dict[str, object]:
    """Composite information-advantage score -- progress even when no deployable edge exists yet.

    Rewards breadth (datasets/mechanisms), depth (forward archive days), and -- most -- the count of
    genuinely ORTHOGONAL validated sleeves (the scarce resource). Unitless, monotonic; track it up.
    """
    breadth = datasets_in_use * 1.0 + mechanisms * 1.5
    depth = min(archive_days / 30.0, 12.0)                # forward archive maturity (capped ~1yr)
    sleeves = active_sleeves * 0.5 + validated_sleeves * 2.0 + orthogonal_sleeves * 3.0
    score = round(breadth + depth + sleeves, 1)
    return {"score": score, "breadth": round(breadth, 1), "depth": round(depth, 1),
            "sleeve_value": round(sleeves, 1), "datasets_in_use": datasets_in_use,
            "mechanisms": mechanisms, "active_sleeves": active_sleeves,
            "validated_sleeves": validated_sleeves, "orthogonal_sleeves": orthogonal_sleeves,
            "archive_days": archive_days}


def paid_data_path(top_n: int = 5) -> list[dict[str, object]]:
    ranked = sorted(PAID_DATASETS, key=lambda d: d.priority(), reverse=True)
    return [{"name": d.name, "source": d.source, "cost": d.cost_usd_per_month,
             "families": list(d.families), "exp_sharpe_add": d.exp_sharpe_contribution,
             "confidence": d.confidence, "priority": d.priority(), "rationale": d.rationale}
            for d in ranked[:top_n]]

```

### libs/ops/fresh.py
```python
"""CONSUMPTION-TIME FRESHNESS (L1.44) -- a decision is only as live as its inputs.

THE CLASS THIS CLOSES. The desk has five producer-side max-age registries (max_audit,
check_ratchets, check_miner_runway, check_exploration, data_health), all hand-enumerated, all
answering "did the producer run?" -- and NONE knowing who READS what. So a dead producer surfaced
as one idleness line among 25 while its frozen artifact kept steering live decisions as if
current. The desk's own record holds at least five hand-found instances of this one unnamed
class: the max_push queue consumed 2h stale by every brain slot (the L1.28c proving instance),
an idle Holm slot fed by a stale snapshot, panel_verdicts 189h old pinning a payload at its
floor, the ADL force-order window firing after its condition had passed, and the 13,155/4,500
two-sources equity split. Severity is set by the CONSUMER, which is why producer-side registries
could never see it.

THE MECHANISM. Every decision-path read of a produced artifact declares its maximum tolerated
age AT THE READ SITE:

    from libs.ops.fresh import read_fresh
    fr = read_fresh("data/cost_model.json", max_age_h=48.0, caller="executor._rt_bps")
    # fr.data (parsed JSON or None), fr.age_h, fr.fresh, fr.why

Each call appends its contract (path, max_age_h, caller, kind) to
data/freshness_contracts.jsonl, TTL-throttled per (caller, path) exactly like lawful.guard's
marker -- so the registry of who-consumes-what BUILDS ITSELF from actual reads. No sixth hand
list to rot, and the registry is simultaneously the producer->consumer edge list that L1.28c's
event-driven end state requires.

THE THREE DESIGN RULES, each closing a way this class hid:
  * CONTENT `generated` OUTRANKS MTIME. The 10-minute auto-deploy and the puller's revert path
    rewrite files, so mtime lies FRESH after a deploy -- the dangerous direction. All five
    existing registries are mtime-based and share that hole; this helper reads the artifact's
    own stamp first and falls back to mtime only when no stamp exists.
  * kind='state' MEANS GUARDIAN-LIVENESS, NEVER OWN-AGE. A valid-until-changed file
    (stage_state.json) is legitimately old; its read is fresh iff the named GUARDIAN organ's
    artifact is alive within the contract. This distinction is what keeps the fence from crying
    wolf on healthy state (L1.43: a gate that cries wolf gets switched off).
  * THE CALLER NAMES ITS DEGRADE DIRECTION. mode='fallback' returns the data with fresh=False
    and the read site decides (a stale denylist still DENIES; a stale cost may only TIGHTEN a
    gate); mode='strict' raises StaleRead, for reads where acting on frozen input is worse than
    not acting -- the executor-grade direction, mirroring lawful.guard(strict=True).

Recording is best-effort BY DESIGN: a telemetry failure must never break a money-path read. That
is not a silent swallow -- an unwritable registry surfaces at the fence as UNMEASURED (zero
contracts can never read OK, L1.28a), so the failure is still loud; the reader is just not the
organ that screams. Fenced by scripts/check_freshness.py.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REGISTRY_REL = "data/freshness_contracts.jsonl"
_MARKERS_REL = "data/.fresh_markers"
CONTRACT_TTL_S = 6 * 3600     # one contract line per (caller, path) per 6h window
STALE_EVENT_TTL_S = 900       # stale/unreadable events at most every 15min per (caller, path)


class StaleRead(RuntimeError):
    """Raised by read_fresh(mode='strict') -- the caller declared frozen input worse than none."""


@dataclass(frozen=True)
class FreshRead:
    data: Any                 # parsed JSON, or None when unreadable/missing
    age_h: float | None       # None when the age itself could not be measured
    fresh: bool
    why: str
    source: str               # generated | mtime | missing | unreadable | guardian:<source>


def _root() -> Path:
    """Where a RELATIVE path resolves, and where the registry is written: the CURRENT WORKING
    DIRECTORY, not an internally-guessed install path.

    WHY, because the first version guessed and that was a bug of this module's own class. Every
    caller's paths are already cwd-relative -- `_STAGE = Path("data/stage_state.json")` and
    `_COST_MODEL = Path("data/cost_model.json")` sit at the top of the executor, and every organ
    on the desk is written the same way -- and every launcher pins cwd to the platform root
    (`cd "$QUANT_ROOT" &&` opens all 113 cron lines; the systemd units set WorkingDirectory=).
    Resolving against a guessed root instead made read_fresh the ONLY reader in its own process
    consuming a different install's artifacts: a checkout under /home/user marking against the
    live box's /home/quant/quant-platform/data/live_guard.json, and a test that chdir'd to a tmp
    fixture silently scoring production state instead of its own. Two roots inside one process is
    precisely the two-sources-of-truth class this module exists to close (the 13,155/4,500 equity
    split in the docstring above), so the helper must not introduce a second one.

    QUANT_FRESH_ROOT overrides for callers that must pin a root without moving cwd.
    """
    env = os.environ.get("QUANT_FRESH_ROOT")
    return Path(env) if env else Path.cwd()


def _age_of(path: Path) -> tuple[float | None, str, Any]:
    """(age_h, source, parsed_data). Content `generated` stamp preferred; mtime is the fallback
    because a deploy-rewritten mtime lies fresh -- the dangerous direction for an age check."""
    try:
        raw = path.read_text("utf-8")
    except OSError:
        return None, "missing", None
    try:
        data = json.loads(raw)
    except ValueError:
        return None, "unreadable", None
    age_gen: float | None = None
    if isinstance(data, dict) and data.get("generated"):
        try:
            at = datetime.fromisoformat(str(data["generated"]))
            if at.tzinfo is None:
                at = at.replace(tzinfo=UTC)
            age_gen = max(0.0, (datetime.now(tz=UTC) - at).total_seconds() / 3600.0)
        except ValueError:
            age_gen = None      # malformed stamp -> fall back to mtime, never hide the artifact
    if age_gen is not None:
        return age_gen, "generated", data
    try:
        return max(0.0, (time.time() - path.stat().st_mtime) / 3600.0), "mtime", data
    except OSError:
        return None, "missing", data


def _rel(root: Path, p: Path) -> str:
    try:
        return str(p.relative_to(root))
    except ValueError:
        return str(p)


def _record(root: Path, event: str, path: str, caller: str, kind: str,
            max_age_h: float, age_h: float | None, guardian: str | None) -> None:
    """Append to the self-building registry, marker-throttled. Best-effort by design (see module
    docstring): failure here must never break the read; the fence reports the silent registry."""
    key = hashlib.sha1(f"{caller}|{path}|{event}".encode()).hexdigest()[:16]
    suffix = ".c" if event == "contract" else ".s"
    marker = root / _MARKERS_REL / (key + suffix)
    ttl = CONTRACT_TTL_S if event == "contract" else STALE_EVENT_TTL_S
    try:
        if marker.exists() and (time.time() - marker.stat().st_mtime) < ttl:
            return
        marker.parent.mkdir(parents=True, exist_ok=True)
        reg = root / REGISTRY_REL
        reg.parent.mkdir(parents=True, exist_ok=True)
        with reg.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "ts": datetime.now(tz=UTC).isoformat(), "event": event, "path": path,
                "caller": caller, "kind": kind, "max_age_h": max_age_h,
                "age_h": None if age_h is None else round(age_h, 3),
                "guardian": guardian,
            }) + "\n")
        marker.write_text(datetime.now(tz=UTC).isoformat(), "utf-8")
    except OSError:
        return


def read_fresh(path: Path | str, max_age_h: float, *, caller: str,
               kind: str = "measurement", guardian: Path | str | None = None,
               mode: str = "fallback", root: Path | None = None) -> FreshRead:
    """Read a produced artifact under a declared freshness contract. See module docstring.

    kind='measurement' -- age is the artifact's own (generated stamp, else mtime).
    kind='state'       -- age is the GUARDIAN artifact's; requires guardian=. The state file's
                          own age is irrelevant by construction (valid-until-changed).
    """
    root = root or _root()
    p = Path(path)
    p = p if p.is_absolute() else root / p
    guardian_rel: str | None = None
    if kind == "state":
        if guardian is None:
            raise ValueError("kind='state' requires guardian= (the organ artifact whose "
                             "liveness makes this state trustworthy)")
        g = Path(guardian)
        g = g if g.is_absolute() else root / g
        guardian_rel = _rel(root, g)
        age, gsource, _gdata = _age_of(g)
        _own_age, _own_source, data = _age_of(p)
        source = f"guardian:{gsource}"
        fresh = age is not None and age <= max_age_h and data is not None
    else:
        age, source, data = _age_of(p)
        fresh = age is not None and age <= max_age_h
    rel = _rel(root, p)
    why = (f"fresh ({age:.2f}h <= {max_age_h}h via {source})" if fresh else
           f"STALE {age:.2f}h > {max_age_h}h ({source})" if age is not None else
           f"{source}: no age measurable")
    _record(root, "contract", rel, caller, kind, max_age_h, age, guardian_rel)
    if not fresh:
        event = "stale_read" if age is not None else "unreadable_read"
        _record(root, event, rel, caller, kind, max_age_h, age, guardian_rel)
        if mode == "strict":
            raise StaleRead(f"{caller}: {rel} -- {why} (L1.44 strict: frozen input declared "
                            "worse than no input at this read site)")
    return FreshRead(data=data, age_h=age, fresh=fresh, why=why, source=source)

```

### libs/portfolio/exposures.py
```python
"""Exposure aggregation — factor, strategy, asset-class, symbol, and risk contributions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from libs.portfolio.models import AlphaInput
from libs.risk.risk_budget import risk_contributions


def _group(weights: Mapping[str, float], key_of: Mapping[str, str | None]) -> dict[str, float]:
    out: dict[str, float] = {}
    for alpha_id, weight in weights.items():
        key = key_of.get(alpha_id)
        if key is None:
            continue
        out[key] = out.get(key, 0.0) + float(weight)
    return out


def calculate_factor_exposures(
    weights: Mapping[str, float], alphas: Sequence[AlphaInput]
) -> dict[str, float]:
    return _group(weights, {a.alpha_id: a.factor.value for a in alphas})


def calculate_strategy_exposures(
    weights: Mapping[str, float], alphas: Sequence[AlphaInput]
) -> dict[str, float]:
    return _group(weights, {a.alpha_id: a.strategy_type.value for a in alphas})


def calculate_asset_class_exposures(
    weights: Mapping[str, float], alphas: Sequence[AlphaInput]
) -> dict[str, float]:
    return _group(weights, {a.alpha_id: a.asset_class for a in alphas})


def calculate_symbol_exposures(
    weights: Mapping[str, float], alphas: Sequence[AlphaInput]
) -> dict[str, float]:
    return _group(weights, {a.alpha_id: a.symbol for a in alphas})


def calculate_risk_contributions(
    weights: Mapping[str, float], cov: np.ndarray, order: Sequence[str]
) -> dict[str, float]:
    """Fractional risk contributions (sum to 1) per alpha, in ``order``."""
    w = np.array([weights[i] for i in order], dtype="float64")
    rc = risk_contributions(w, np.asarray(cov, dtype="float64"))
    total = float(rc.sum())
    if total <= 0:
        return dict.fromkeys(order, 0.0)
    return {i: float(rc[k] / total) for k, i in enumerate(order)}

```

### libs/research/data_registry.py
```python
"""DATA ASSET REGISTRY -- one measured row per dataset (EXECUTION_QUEUE.md RANK 4).

WHY THIS EXISTS: GAP_REGISTER row #77. The desk's previous data inventory was hand-written, and it
failed in BOTH directions at once, which is why "just keep it updated" was never the fix:

  * OVERSTATED. It reported ROW COUNTS as if they were SPANS. ``liquidations.parquet`` read as
    "33,867 rows" -- it is **17 days / 15 symbols**. ``hyperliquid_funding`` and ``crypto_metrics``
    read as large; both are **28 days**. A "14k+ events" framing invites monthly-horizon work the
    span cannot support, and it did: a BIS Table-7 replication was started and had to be downgraded
    before it became a 17-day overfit.
  * UNDERSTATED. ``data/lake/bronze/crypto/<SYM>/D1/*.parquet`` -- **267 symbols, daily, from
    2019-09-08**, funding + basis + taker_buy_frac, all non-null -- was **absent entirely**, and it
    is the desk's best panel (wider and longer than the BIS paper's own).

So the map hid which mechanisms were blocked AND which were unblocked, and research organs were
choosing what to test off it. The binding constraint on the whole forgotten-literature ground turned
out to be HISTORY LENGTH -- a conclusion only reachable once real spans were measured.

THREE DESIGN CONSEQUENCES, each aimed at one of those failures:

1. SPAN IS MEASURED, NEVER COUNTED. ``measure_span`` opens the data and reads the min/max of its
   real date column. ``rows`` is still reported but as a separate field that cannot be mistaken for
   duration. A span this cannot measure is ``None`` with a status saying why -- never 0, never a
   guess. An honest hole is navigable; a confident wrong number is not.

2. DISCOVERY IS DERIVED, NOT LISTED. Assets are found by scanning the paths the desk's own
   collectors write, plus a recursive sweep of the lake that follows partitioned
   ``<axis>/<SYM>/<TF>/`` trees. That is precisely what a flat hand-list missed: the best panel was
   invisible because it is 267 per-symbol directories rather than one file. A registry that can be
   out of date the moment somebody adds a collector rebuilds the original defect.

3. MOAT AND RESEARCH VALUE ARE SEPARATE SCORES. Conflating them mis-ranks in both directions, and
   the desk's own doctrine already draws the line: ``data/moat`` order-book snapshots are "the only
   PROPRIETARY dataset the desk owns: nobody else has these snapshots at these timestamps.
   Everything else it researches (GitHub, TVL, on-chain, social) is available to anyone"
   (``scripts/moat_audit.py``:9-11). So:

     * ``data/cot_zcache.parquet`` -- CFTC COT, 26 YEARS, 11 assets -- has ZERO moat (anyone can
       re-download all of it) and very HIGH research value. Scoring it as a moat would be a lie;
       dismissing it for having no moat would waste the longest panel on the desk. Row #77 also
       notes nothing reads it, which is why ``consumers`` is a field.
     * Perishable public feeds (funding, OI, long/short) DO earn moat: the venue serves only recent
       history, so the archive exists only because the desk was recording. Being early is the moat,
       not exclusivity.

Pure stdlib + optional pandas (parquet). Import from ``libs.research.data_registry``; the CLI is
``scripts/build_data_registry.py``.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]

#: Column names that carry a row's date, most-specific first. A dataset whose date lives under a
#: name absent here is reported ``no-date-column`` rather than silently spanless -- the whole point
#: is that an unmeasured span is visible.
_DATE_COLS = ("date", "day", "ts", "timestamp", "time", "open_time", "dt", "datetime")

#: Where partitioned trees live. Depth-2 under the axis dir is ``<SYM>/<TF>/`` (the shape that was
#: invisible to the flat inventory); depth-1 is ``<SYM>/``.
_LAKE = "data/lake/bronze"

#: How hard is this to obtain if the desk lost it today? This decides MOAT, not size.
REPL_REFETCHABLE = "public-refetchable"    #: anyone can re-download the full history -> no moat
REPL_PERISHABLE = "public-perishable"      #: public API, recent-only -> the archive IS the moat
REPL_PROPRIETARY = "proprietary-recorded"  #: our own snapshots at our own timestamps -> max moat

#: Feeds whose venue serves only a short recent window, so history cannot be re-acquired. Matched
#: against the asset id. Being early is the moat.
_PERISHABLE = ("funding", "oi_ls", "oi_", "long_short", "liquidation", "premium", "breadth",
               "deribit", "surface", "taker", "defi_lending", "stablecoin", "tail_")

#: Recorded-by-us datasets. Nobody else holds these timestamps.
_PROPRIETARY = ("moat", "orderbook", "book_snapshot", "venue_truth")


@dataclass(frozen=True)
class AssetSpan:
    """A dataset's real time extent. ``None`` fields mean UNMEASURED, and ``status`` says why."""

    first: str | None = None
    last: str | None = None
    days: int | None = None
    status: str = "unmeasured"

    @property
    def measured(self) -> bool:
        return self.status == "measured"


@dataclass(frozen=True)
class DataQuality:
    """DQS and its components, measured from the data. ``None`` means UNMEASURED, never "fine".

    The three components are the ones moat_audit already found matter on this desk's own data
    (``scripts/moat_audit.py``:14-19): a feed can be present and still be worthless because it has
    HOLES (the recorder died and nobody noticed), because it is STALE (the recorder echoing its last
    value rather than reading), or because it is full of NULLs. A row count catches none of those --
    which is the same family of error as reporting row counts as spans.
    """

    completeness: float | None = None   #: observed days / span days -- 1.0 means no missing days
    stale_frac: float | None = None     #: fraction of consecutive-identical rows (recorder echo)
    null_frac: float | None = None      #: fraction of null cells
    dqs: float | None = None            #: 0..100 composite; None when it could not be measured

    @property
    def measured(self) -> bool:
        return self.dqs is not None


@dataclass
class DataAsset:
    """One row of the registry. Every numeric field is measured or explicitly absent."""

    id: str
    path: str
    kind: str = "flat"                       #: "flat" | "partitioned"
    collector: str | None = None             #: the script that WRITES it
    consumers: list[str] = field(default_factory=list)   #: scripts that READ it
    dependencies: list[str] = field(default_factory=list)  #: assets its collector READS to build it
    span: AssetSpan = field(default_factory=AssetSpan)
    quality: DataQuality = field(default_factory=DataQuality)
    rows: int | None = None                  #: reported SEPARATELY from span, never as duration
    breadth: int | None = None               #: distinct symbols / partitions
    bytes: int | None = None
    cadence_h: float | None = None           #: from ops/crontab.manifest, None = unscheduled
    replication: str = REPL_REFETCHABLE
    moat_score: float = 0.0
    research_value: float = 0.0
    #: ALPHA CONTRIBUTION is deliberately None, not 0.0, while the desk holds 0 validated alphas.
    #: A zero would read as "measured and worthless"; None reads as "nothing has been attributed
    #: yet", which is the true state and the difference organs must not have to guess at.
    alpha_contribution: float | None = None
    maintenance_runs_per_day: float | None = None   #: scheduled runs/day -- the real recurring cost
    needs_credentials: bool = False          #: a feed that can silently die on an expired key
    last_validated: str | None = None        #: ISO date the asset was last measured on disk
    notes: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        d["span"] = asdict(self.span)
        d["quality"] = asdict(self.quality)
        return d


# --------------------------------------------------------------------------- span measurement

def _iso_day(v: Any) -> str | None:
    """Best-effort ISO date from a cell that may be a date string or an epoch in s/ms/us/ns."""
    from datetime import UTC, datetime

    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        return s[:10]
    try:
        n = float(s)
    except ValueError:
        return None
    # epoch unit inferred by magnitude; a 2001-09-09 s-timestamp is 1e9, ms is 1e12, ...
    for div in (1.0, 1e3, 1e6, 1e9):
        t = n / div
        if 3e8 < t < 4e9:                     # ~1979..2096, the only plausible band
            return datetime.fromtimestamp(t, tz=UTC).date().isoformat()
    return None


def _span_from_days(days: list[str]) -> AssetSpan:
    from datetime import date

    ds = sorted(d for d in days if d)
    if not ds:
        return AssetSpan(status="no-date-column")
    try:
        n = (date.fromisoformat(ds[-1]) - date.fromisoformat(ds[0])).days + 1
    except ValueError:
        return AssetSpan(first=ds[0], last=ds[-1], status="measured")
    return AssetSpan(first=ds[0], last=ds[-1], days=n, status="measured")


def _measure_jsonl(p: Path) -> tuple[AssetSpan, int | None, int | None]:
    """Span/rows/breadth for newline-delimited JSON, streamed (these grow unbounded)."""
    days: list[str] = []
    syms: set[str] = set()
    rows = 0
    try:
        with p.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.strip():
                    continue
                rows += 1
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(rec, dict):
                    continue
                for c in _DATE_COLS:
                    if c in rec:
                        d = _iso_day(rec[c])
                        if d:
                            days.append(d)
                        break
                for k in ("symbol", "sym", "ticker", "pair", "asset"):
                    if rec.get(k):
                        syms.add(str(rec[k]))
                        break
    except OSError:
        return AssetSpan(status="unreadable"), None, None
    # keep only the extremes; holding every day of a multi-year feed is pointless memory
    return _span_from_days(days), rows, len(syms) or None


def _measure_parquet(p: Path) -> tuple[AssetSpan, int | None, int | None]:
    try:
        import pandas as pd
    except ImportError:
        return AssetSpan(status="no-parquet-reader"), None, None
    try:
        df = pd.read_parquet(p)
    except Exception:
        return AssetSpan(status="unreadable"), None, None
    rows = len(df)
    col = next((c for c in _DATE_COLS if c in df.columns), None)
    if col is None:
        idx = df.index
        got = getattr(idx, "is_all_dates", False) or "datetime" in str(getattr(idx, "dtype", ""))
        if not got:
            return AssetSpan(status="no-date-column"), rows, None
        days = [d for d in (_iso_day(v) for v in (idx.min(), idx.max())) if d]
    else:
        s = df[col].dropna()
        days = [d for d in (_iso_day(s.min()), _iso_day(s.max())) if d] if len(s) else []
    breadth = None
    for k in ("symbol", "sym", "ticker", "pair", "asset"):
        if k in df.columns:
            breadth = int(df[k].nunique())
            break
    return _span_from_days(days), rows, breadth


def measure_span(path: Path) -> tuple[AssetSpan, int | None, int | None]:
    """(span, rows, breadth) for one file. Absent is ``absent``, never a zero-length span."""
    if not path.exists():
        return AssetSpan(status="absent"), None, None
    if path.suffix == ".parquet":
        return _measure_parquet(path)
    if path.suffix in (".jsonl", ".ndjson"):
        return _measure_jsonl(path)
    return AssetSpan(status="unsupported-format"), None, None


def measure_quality(path: Path, span: AssetSpan, rows: int | None,
                    breadth: int | None) -> DataQuality:
    """DQS from the data itself. Every component is measured or the whole score stays ``None``.

    COMPLETENESS is the one that catches the failure this desk actually has: a recorder dies, the
    file keeps existing, the span still looks long, and only the count of DISTINCT DAYS against the
    span reveals the hole. STALENESS catches the other half -- a recorder that is alive but echoing
    its previous value reads as perfect completeness and carries no information at all.
    """
    if not span.measured or not span.days or path.suffix != ".parquet":
        # jsonl/absent assets: completeness is still computable from span vs rows when both exist,
        # but a partial score invites the same false confidence a partial map does. Report None.
        return DataQuality()
    try:
        import pandas as pd
        df = pd.read_parquet(path)
    except Exception:
        return DataQuality()
    if df.empty:
        return DataQuality()

    col = next((c for c in _DATE_COLS if c in df.columns), None)
    completeness = None
    if col is not None:
        days_seen = df[col].map(_iso_day).dropna().nunique()
        expected = span.days * max(1, breadth or 1) if breadth and breadth > 1 else span.days
        # per-symbol panels have breadth*days expected rows; a flat series has days
        completeness = min(1.0, float(days_seen) / float(span.days)) if span.days else None
        del expected

    num = df.select_dtypes(include="number")
    stale = None
    if len(num) > 1 and not num.empty:
        same = (num.diff().abs().sum(axis=1) == 0)
        stale = float(same.iloc[1:].mean())

    null_frac = float(df.isna().to_numpy().mean()) if df.size else None

    parts = [p for p in (completeness,
                         None if stale is None else 1.0 - stale,
                         None if null_frac is None else 1.0 - null_frac) if p is not None]
    dqs = round(100.0 * sum(parts) / len(parts), 1) if parts else None
    return DataQuality(
        completeness=None if completeness is None else round(completeness, 4),
        stale_frac=None if stale is None else round(stale, 4),
        null_frac=None if null_frac is None else round(null_frac, 4),
        dqs=dqs)


# --------------------------------------------------------------------------- classification

def classify_replication(asset_id: str) -> str:
    low = asset_id.lower()
    if any(t in low for t in _PROPRIETARY):
        return REPL_PROPRIETARY
    if any(t in low for t in _PERISHABLE):
        return REPL_PERISHABLE
    return REPL_REFETCHABLE


def score(asset: DataAsset) -> tuple[float, float]:
    """(moat_score, research_value), 0..100, deliberately driven by DIFFERENT inputs.

    MOAT answers "could a competitor stand this up tomorrow?" -- so it is replication class first,
    and length only matters for a perishable feed (where length IS the head start). A fully
    re-fetchable public panel scores 0 no matter how long it is: 26 years of CFTC COT is not an
    advantage the desk owns, it is an advantage the desk noticed.

    RESEARCH VALUE answers "what can be tested on it?" -- so it is span and breadth, because those
    are what bound the horizons and cross-sections a study can support. This is the axis row #77's
    "binding constraint is HISTORY LENGTH" conclusion lives on, and it is why an unread 26-year
    public panel can be the most valuable row here while scoring zero moat.
    """
    days = asset.span.days or 0
    breadth = asset.breadth or 1

    if asset.replication == REPL_PROPRIETARY:
        moat = 70.0 + min(30.0, days / 365.0 * 30.0)
    elif asset.replication == REPL_PERISHABLE:
        moat = min(60.0, days / 365.0 * 60.0)      # a 28-day funding archive is ~4.6, honestly
    else:
        moat = 0.0

    # span dominates: a 17-day/15-symbol set supports nothing a 267-symbol/6-year set does
    span_pts = min(60.0, days / 365.0 * 20.0)
    breadth_pts = min(30.0, breadth / 10.0)
    unread = 10.0 if (days > 365 and not asset.consumers) else 0.0   # #77's paralysis bonus
    return round(moat, 1), round(min(100.0, span_pts + breadth_pts + unread), 1)


# --------------------------------------------------------------------------- discovery

def _writers_and_readers(root: Path) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Map data paths -> the script that writes them, and -> scripts that read them.

    Grep-derived on purpose: a hand-kept owner column is the field most likely to be stale, and a
    stale OWNER is how row #77's inventory drifted from reality in the first place.
    """
    writers: dict[str, str] = {}
    readers: dict[str, list[str]] = {}
    pat = re.compile(r'["\']((?:data/)[A-Za-z0-9_./-]+\.(?:parquet|jsonl|ndjson))["\']')
    for py in sorted((root / "scripts").glob("*.py")) + sorted((root / "libs").rglob("*.py")):
        try:
            src = py.read_text("utf-8", errors="replace")
        except OSError:
            continue
        rel = py.relative_to(root).as_posix()
        for m in pat.finditer(src):
            path = m.group(1)
            # a writer names the path near a write call; everything else is a reader
            near = src[max(0, m.start() - 220):m.end() + 220]
            if re.search(r"to_parquet|write_text|open\([^)]*[\"']a|\.write\(|dump|append", near):
                writers.setdefault(path, rel)
            else:
                readers.setdefault(path, [])
                if rel not in readers[path]:
                    readers[path].append(rel)
    return writers, readers


def _dependencies_of(collector: str | None, own: str,
                     readers: Mapping[str, list[str]]) -> list[str]:
    """Assets this one is DERIVED from: paths its own collector also reads.

    Lineage matters for a reason row #77 makes concrete: a derived asset can never be longer or
    cleaner than its source, so a study sized off the derived span is really sized off the source's.
    """
    if not collector:
        return []
    return sorted({Path(src).stem for src, rdrs in readers.items()
                   if collector in rdrs and src != own})


def _needs_credentials(root: Path, collector: str | None) -> bool:
    """Does the collector read a secret? Those are the feeds that die silently on key expiry."""
    if not collector:
        return False
    try:
        src = (root / collector).read_text("utf-8", errors="replace")
    except OSError:
        return False
    return "data/secrets" in src or "API_KEY" in src or "api_key" in src


def _mtime_day(p: Path) -> str | None:
    from datetime import UTC, datetime
    try:
        return datetime.fromtimestamp(p.stat().st_mtime, tz=UTC).date().isoformat()
    except OSError:
        return None


def _cadence_hours(root: Path) -> dict[str, float]:
    """script -> hours between runs, parsed from ops/crontab.manifest."""
    mf = root / "ops/crontab.manifest"
    if not mf.exists():
        return {}
    out: dict[str, float] = {}
    for line in mf.read_text("utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith(("SYSTEMD", "QUANT_ROOT")):
            continue
        parts = s.split(None, 5)
        if len(parts) < 6:
            continue
        minute, hour = parts[0], parts[1]
        every = 24.0
        if minute.startswith("*/"):
            with_ = minute[2:]
            every = float(with_) / 60.0 if with_.isdigit() else 1.0
        elif hour.startswith("*/") and hour[2:].isdigit():
            every = float(hour[2:])
        elif hour == "*":
            every = 1.0
        for m in re.finditer(r"(scripts/[A-Za-z0-9_./-]+\.py)", parts[5]):
            out[m.group(1)] = min(every, out.get(m.group(1), 1e9))
    return out


def _partitioned_assets(root: Path) -> list[tuple[str, Path, list[Path]]]:
    """(id, axis_dir, member files) for each partitioned lake tree.

    THE ROW-#77 CASE. ``data/lake/bronze/crypto/<SYM>/D1/*.parquet`` is 267 symbol directories, so
    a flat scan of ``data/`` sees nothing and the desk's best panel vanishes from its own map.
    """
    base = root / _LAKE
    if not base.is_dir():
        return []
    out = []
    for axis in sorted(p for p in base.iterdir() if p.is_dir()):
        files = sorted(axis.rglob("*.parquet")) + sorted(axis.rglob("*.jsonl"))
        if files:
            out.append((f"lake_{axis.name}", axis, files))
    return out


def build(root: Path | None = None, *, deep: bool = False) -> list[DataAsset]:
    """Discover and MEASURE every data asset. ``deep`` measures every partition member.

    Without ``deep`` a partitioned tree is measured from a sample of members (first/middle/last),
    which is what makes a 267-symbol daily panel affordable to register every day. Breadth is
    always exact -- it is a directory count, not a sample.
    """
    root = root or _ROOT
    writers, readers = _writers_and_readers(root)
    cadence = _cadence_hours(root)
    assets: list[DataAsset] = []
    seen: set[str] = set()

    def cad_for(collector: str | None) -> float | None:
        return cadence.get(collector) if collector else None

    for rel in sorted(set(writers) | set(readers)):
        p = root / rel
        if p.is_dir() or rel in seen:
            continue
        seen.add(rel)
        aid = Path(rel).stem
        span, rows, breadth = measure_span(p)
        collector = writers.get(rel)
        cad = cad_for(collector)
        a = DataAsset(
            id=aid, path=rel, kind="flat", collector=collector,
            consumers=readers.get(rel, []),
            dependencies=_dependencies_of(collector, rel, readers),
            span=span, quality=measure_quality(p, span, rows, breadth),
            rows=rows, breadth=breadth,
            bytes=p.stat().st_size if p.exists() else None,
            cadence_h=cad, replication=classify_replication(aid),
            maintenance_runs_per_day=(round(24.0 / cad, 2) if cad else None),
            needs_credentials=_needs_credentials(root, collector),
            last_validated=_mtime_day(p),
        )
        if span.status == "absent":
            a.notes.append("declared by a collector but NOT PRESENT on this box -- span "
                           "unmeasured, not zero (this box may not be the collecting box)")
        a.moat_score, a.research_value = score(a)
        assets.append(a)

    for aid, axis_dir, files in _partitioned_assets(root):
        members = files if deep else (files[:1] + files[len(files) // 2:len(files) // 2 + 1]
                                      + files[-1:])
        days: list[str] = []
        rows = 0
        for f in members:
            s, r, _ = measure_span(f)
            rows += r or 0
            days += [d for d in (s.first, s.last) if d]
        # breadth is the EXACT partition count, never the sample size
        breadth = len({f.relative_to(axis_dir).parts[0] for f in files})
        rel = axis_dir.relative_to(root).as_posix()
        coll = writers.get(rel)
        cad = cad_for(coll)
        span = _span_from_days(days)
        a = DataAsset(
            id=aid, path=rel + "/**", kind="partitioned",
            collector=coll, consumers=readers.get(rel, []),
            dependencies=_dependencies_of(coll, rel, readers),
            span=span,
            # quality is measured on ONE representative member: reading 267 symbol files to score
            # the panel would cost more than the score is worth, and the failure modes it catches
            # (recorder holes, echoed values) are per-file properties anyway
            quality=measure_quality(members[0], span, rows, breadth) if members else DataQuality(),
            rows=rows if deep else None,
            breadth=breadth,
            bytes=sum(f.stat().st_size for f in files),
            cadence_h=cad,
            replication=classify_replication(aid),
            maintenance_runs_per_day=(round(24.0 / cad, 2) if cad else None),
            needs_credentials=_needs_credentials(root, coll),
            last_validated=_mtime_day(members[0]) if members else None,
        )
        a.notes.append(f"{len(files)} partition file(s) across {breadth} partition(s)"
                       + ("" if deep else f"; span sampled from {len(members)}, breadth exact"))
        a.moat_score, a.research_value = score(a)
        assets.append(a)

    return sorted(assets, key=lambda x: (-x.research_value, x.id))

```

### libs/research/information_value.py
```python
"""Information-value accounting -- judge research by UNCERTAINTY REMOVED, not alpha count.

The factory's honest success metric is not "how many strategies did we test" but "how much did
we learn per unit effort". This logs, per experiment, the EV-gate prior P(survive), the actual
outcome, and the Shannon surprise = -log2(P(observed outcome)) -- high surprise = high
information gain (a confidently-predicted result teaches little; a surprising one teaches a lot).
The running summary answers the questions that decide whether SCALING generation is worth it:

  - information gain per experiment (bits) -- is throughput buying learning or just noise?
  - distinct alpha FAMILIES explored -- is breadth growing, or are we re-drawing one pool?
  - survivor rate + forward-validated survivors -- the number that settles "scale or not".

Pure stdlib, append-only JSONL -> cheap to call from the research cycle, permanent record.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_LOG = Path("data/information_value.jsonl")
_EPS = 1e-6


def surprise_bits(prior_survive: float, survived: bool) -> float:
    """Shannon surprise of the observed outcome in bits. Prior clamped to (0,1)."""
    p = min(1.0 - _EPS, max(_EPS, float(prior_survive)))
    p_obs = p if survived else (1.0 - p)
    return round(-math.log2(p_obs), 4)


def log_experiment(name: str, family: str, prior_survive: float, survived: bool,
                   *, forward_validated: bool = False, lesson: str = "",
                   log: Path = _LOG) -> dict[str, Any]:
    """Append one experiment's information record. Returns the record (incl. surprise bits)."""
    rec = {
        "ts": datetime.now(tz=UTC).isoformat(), "name": name, "family": family,
        "prior_survive": round(float(prior_survive), 4), "survived": bool(survived),
        "forward_validated": bool(forward_validated),
        "info_bits": surprise_bits(prior_survive, survived), "lesson": lesson,
    }
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def record_factory_cycle(tested: int, survivors: int, *, base_prior: float = 0.15,
                         timeframe: str = "D1", log: Path = _LOG,
                         web: Path = Path("web/pilot.json")) -> dict[str, Any]:
    """Log one factory cycle's NEW candidates and refresh the pilot dashboard card.

    Each newly-tested hypothesis is scored against the desk's honest base survival rate
    (0.15); a survivor at that prior is high-surprise (high info), a reject is low. Over the
    30-day pilot this accumulates the ONE number that settles scale-or-not:
    forward-validated survivors per 1,000 + info-bits per experiment. tested is NEW-this-cycle
    (the factory dedups), so the log does not bloat after the first sweep.
    """
    fam = f"crypto_{timeframe}"
    for _ in range(max(0, survivors)):
        log_experiment("factory_survivor", fam, base_prior, True, log=log)
    for _ in range(max(0, tested - survivors)):
        log_experiment("factory_reject", fam, base_prior, False, log=log)
    s = summary(log=log)
    per_1000 = round(1000.0 * s.get("survivors", 0) / max(1, s.get("experiments", 1)), 2)
    card = {"updated": datetime.now(tz=UTC).isoformat(),
            "pilot": "factory 30-day measurement (survivors per 1,000 decides scale-or-not)",
            "survivors_per_1000": per_1000, **s}
    web.parent.mkdir(parents=True, exist_ok=True)
    web.write_text(json.dumps(card, indent=2), "utf-8")
    return card


def summary(log: Path = _LOG) -> dict[str, Any]:
    """Aggregate information-value metrics -- the scale-or-not decision numbers."""
    if not log.exists():
        return {"experiments": 0, "note": "no experiments logged yet"}
    rows = []
    for line in log.read_text("utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    n = len(rows)
    if not n:
        return {"experiments": 0, "note": "no experiments logged yet"}
    survivors = sum(1 for r in rows if r.get("survived"))
    fwd = sum(1 for r in rows if r.get("forward_validated"))
    families = sorted({r.get("family", "?") for r in rows})
    total_bits = sum(float(r.get("info_bits", 0.0)) for r in rows)
    return {
        "experiments": n,
        "survivors": survivors,
        "forward_validated_survivors": fwd,
        "survivor_rate": round(survivors / n, 4),
        "distinct_families": len(families),
        "families": families,
        "total_information_bits": round(total_bits, 2),
        "info_bits_per_experiment": round(total_bits / n, 4),
        # the scale-or-not verdict keys off DURABLE SURVIVORS, not raw info -- rejections
        # trivially accumulate bits (you learn an idea is dead), so info-bits alone would
        # wrongly reward a pure-reject run. Forward-validated survivors are the honest signal.
        "verdict_hint": (
            f"{fwd} forward-validated survivor(s) in {n} trials -- scaling generation may be "
            "EV-positive; the CPU rental is now evidence-backed" if fwd > 0
            else f"0 durable survivors in {n} trials -- throughput is re-drawing a known pool; "
            "the constraint is DATA/MECHANISM, not volume. Do NOT rent hardware yet"),
    }

```

### libs/research/listing_events.py
```python
"""Turn the listing collector's log into event-study observations -- the acquired->convertible step.

``scripts/run_listing_watch.py`` has been logging every new USDT perp with its funding rate at
detection. That is ACQUISITION. Nothing consumed it, so the day-1 listing dislocation -- the
capacity-tiny, structurally recurring edge §42 calls the desk's niche -- could accumulate evidence
forever without ever being able to earn a promotion. This module is the consumer: it shapes those
rows into ``Event`` observations that ``libs.validation.event_study`` can actually rule on.

PRE-REGISTRATION, AND WHY IT IS A MODULE CONSTANT. The hypothesis is fixed HERE, in code, before
the data is looked at:

    A new perp listing whose day-1 funding is extreme-positive (spec longs, no arb capital yet)
    earns a positive abnormal return to the SHORT side over the following HOLD_HOURS.

Direction, holding period and the funding threshold are constants, not arguments. If they were
tunable the script would sweep them, report the best, and the desk would have data-mined its own
collector -- and the multiplicity correction would be a lie, because the trials would be invisible.
Changing any of them is a NEW hypothesis: bump ``VARIANTS_TRIED`` so the Holm bar rises to match,
which is the only honest way to try a second window.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from libs.features.labels import triple_barrier_labels
from libs.validation.event_study import Event, EventStudyResult, event_study

#: Holding period for the pre-registered hypothesis. Fixed, not swept.
HOLD_HOURS = 48.0
#: Day-1 funding above this counts as the extreme-positive regime the hypothesis is about.
#: Binance funding is 8-hourly, so 0.10% per interval is ~110% annualised -- genuinely dislocated,
#: not merely "a bit rich".
FUNDING_THRESHOLD = 0.0010
#: Barrier exits for the same hypothesis, as multiples of the entry price. A fixed 48h window is
#: not how anyone actually trades a dislocation -- you take the profit when it arrives and cut when
#: it does not -- so the honest exit is a triple barrier: profit-take, stop, or time, whichever is
#: touched first. Pre-registered like everything else, never swept.
TP_FRAC = 0.06      # short-side profit target: the listing premium bleeding off
SL_FRAC = 0.04      # stop: the listing keeps squeezing and the short is wrong

#: Every distinct (direction, window, threshold, EXIT RULE) ever tried against this collector. The
#: event study's Holm bar reads this: a second exit rule is a second trial, and pretending
#: otherwise is how a screen becomes a "discovery". RAISE IT when you add a variant; never lower.
#: 2 = {fixed 48h close-to-close, triple-barrier}. Both are offered, so both are counted, even
#: though only one will be reported -- the bar must price the trials CONSIDERED, not the ones kept.
VARIANTS_TRIED = 2

LISTINGS_LOG = Path("data/listings.jsonl")


def listing_rows(path: Path = LISTINGS_LOG) -> list[dict[str, Any]]:
    """Parse the collector's log, keeping only listings (a delisting is a different event)."""
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue                      # a torn append must not take the whole study down
        if row.get("event") == "listed":
            rows.append(row)
    return rows


def qualifying(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Listings in the extreme-positive-funding regime the hypothesis is actually about."""
    return [r for r in rows
            if float(r.get("funding_at_detect", 0.0) or 0.0) >= FUNDING_THRESHOLD]


def build_events(
    rows: list[dict[str, Any]],
    forward_return: Callable[[str, float], float | None],
    benchmark_return: Callable[[float], float | None] | None = None,
    *,
    hold_hours: float = HOLD_HOURS,
) -> list[Event]:
    """Shape qualifying listings into events, SHORT-side and benchmark-adjusted.

    ``forward_return(symbol, t_start)`` returns the long-side return over the holding window, or
    None when the window is not yet complete -- an incomplete window is DROPPED, never zero-filled,
    because a zero is an observation and a missing bar is not.

    The sign flip is the hypothesis: extreme-positive funding is a crowded long, so the trade is
    the short. Benchmark is subtracted over the SAME window, otherwise a listing panel collected
    through a bear month reports -beta and calls it edge.
    """
    events: list[Event] = []
    for r in qualifying(rows):
        sym = str(r.get("symbol", ""))
        t_start = _epoch(r.get("ts"))
        if not sym or t_start is None:
            continue
        long_ret = forward_return(sym, t_start)
        if long_ret is None:
            continue                      # window still open -- not evidence yet
        bench = benchmark_return(t_start) if benchmark_return is not None else 0.0
        if bench is None:
            continue                      # no benchmark means we would be measuring beta
        # short side, benchmark-adjusted: -(asset - benchmark)
        events.append(Event(event_id=f"{sym}@{t_start:.0f}", t_start=t_start,
                            t_end=t_start + hold_hours * 3600.0,
                            ret=-(long_ret - bench)))
    return events


def barrier_return(path: list[float], *, tp: float = TP_FRAC, sl: float = SL_FRAC) -> float | None:
    """SHORT-side return from a price path, exiting at the first barrier touched.

    Delegates the barrier logic to ``libs.features.labels.triple_barrier_labels`` -- the desk's
    audited Lopez de Prado port -- rather than re-implementing a second copy of it. That module had
    correct code, a full test file, and NO production consumer; a labeller nobody calls is an
    orphaned artifact (§36), and the fix for an orphan is a real caller, not deletion.

    Barrier semantics are inverted here because the hypothesis is a SHORT: the price falling to the
    profit target is the win. The labeller reports which barrier the LONG path touched first, so a
    -1 (price fell to the lower barrier) is the short's profit-take.

    Returns None when the path is too short or the outcome is undetermined -- never a fabricated
    zero, for the same reason `build_events` drops incomplete windows.
    """
    if len(path) < 2:
        return None
    import pandas as pd
    # `upper`/`lower` are the LONG-side barriers; the short's target is the long's lower barrier.
    lab = triple_barrier_labels(pd.Series(path, dtype="float64"),
                                horizon=len(path) - 1, upper=sl, lower=tp)
    first = lab.iloc[0]
    if pd.isna(first):
        return None                       # path truncated before any barrier -- not evidence
    if first == -1.0:
        return tp                         # price fell to the target: the short took profit
    if first == 1.0:
        return -sl                        # price squeezed to the stop: the short was cut
    return -(path[-1] / path[0] - 1.0)    # time barrier: exit at the close, short side


def build_events_barrier(
    rows: list[dict[str, Any]],
    price_path: Callable[[str, float], list[float] | None],
    benchmark_return: Callable[[float], float | None] | None = None,
    *,
    hold_hours: float = HOLD_HOURS,
) -> list[Event]:
    """Events exited at the first barrier touched, rather than held blindly for a fixed window.

    Same hypothesis, same pre-registration, honest exit: `price_path(symbol, t_start)` returns the
    hourly closes over the window and the trade leaves at the profit target, the stop, or the time
    barrier -- whichever comes first. That is how the trade would actually be run, so it is what
    the study should measure.

    The benchmark is still subtracted, for the same reason as the fixed-window build: without it a
    panel collected through a falling market reports -beta and calls it edge. Subtracting it from a
    barrier exit is an approximation (the exit time varies per event while the benchmark window
    does not), and it is the CONSERVATIVE direction -- it cannot manufacture edge that is not
    there, only understate one that is.
    """
    events: list[Event] = []
    for r in qualifying(rows):
        sym = str(r.get("symbol", ""))
        t_start = _epoch(r.get("ts"))
        if not sym or t_start is None:
            continue
        path = price_path(sym, t_start)
        if not path:
            continue                      # window still open -- not evidence yet
        ret = barrier_return(path)
        if ret is None:
            continue
        bench = benchmark_return(t_start) if benchmark_return is not None else 0.0
        if bench is None:
            continue
        events.append(Event(event_id=f"{sym}@{t_start:.0f}b", t_start=t_start,
                            t_end=t_start + hold_hours * 3600.0, ret=ret + bench))
    return events


def study_listings(events: list[Event]) -> EventStudyResult:
    """Run the pre-registered listing hypothesis through the event-study gate."""
    return event_study(events, n_cohort=VARIANTS_TRIED, rank=1)


def _epoch(ts: object) -> float | None:
    from datetime import datetime
    if isinstance(ts, int | float):
        return float(ts)
    if not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts).timestamp()
    except ValueError:
        return None

```

### libs/research/mechanism_fingerprint.py
```python
"""MECHANISM FINGERPRINT -- the shared identity of an idea, used by #3 and #6 (HYPOTHESIS_MAX).

The spec defines one fingerprint and two consumers, so it lives in one place:

    fingerprint = feature family + signal transform + horizon bucket

  #3 TRIVIAL-VARIATION BLOCKER  two hypotheses with the same fingerprint are the SAME IDEA wearing
                                different parameters. Re-testing one is not new evidence, it is a
                                fresh multiplicity charge for a question already asked -- the
                                garden of forking paths with a lookback knob.
  #6 COLLAPSE DETECTOR          entropy over fingerprints across a generation batch. Collapse
                                shows as entropy falling while VOLUME HOLDS: the desk looks
                                productive and is asking one question repeatedly.

WHY THE BUCKETING IS COARSE ON PURPOSE. A 20-day and a 21-day lookback are the same hypothesis;
treating them as distinct is exactly the failure this exists to catch. Horizons therefore collapse
into log-spaced buckets (intraday / days / weeks / months / quarters), and continuous params are
dropped entirely -- they are the knob, never the idea. The cost of coarseness is occasionally
calling two genuinely different ideas the same; the cost of fineness is a desk that believes 400
reparameterisations of one mechanism are 400 tests. The second error is the one that has actually
happened here (420 candidates, 0 survivors), so the bucketing errs toward coarse.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

#: horizon in days -> bucket. Log-spaced, because the meaningful distinction between a 1-day and a
#: 5-day signal is large while 20 vs 21 days is noise.
_HORIZON_BUCKETS: tuple[tuple[float, str], ...] = (
    (1.0, "intraday"), (5.0, "days"), (21.0, "weeks"), (63.0, "months"),
    (252.0, "quarters"), (float("inf"), "annual+"),
)

#: signal transforms the desk actually uses, normalised to a canonical token.
_TRANSFORMS: dict[str, tuple[str, ...]] = {
    "zscore": ("zscore", "z-score", "standardi", "normali"),
    "rank": ("rank", "cross-section", "cross_section", "percentile", "decile", "quantile"),
    "momentum": ("momentum", "trend", "roc", "rate-of-change", "breakout"),
    "reversal": ("reversal", "mean-revert", "mean_revert", "contrarian", "fade"),
    "carry": ("carry", "funding", "basis", "roll", "yield"),
    "spread": ("spread", "divergence", "premium", "arb", "dislocation"),
    "level": ("level", "raw", "absolute", "threshold"),
    "vol": ("vol", "variance", "realized_vol", "garch", "dispersion"),
    "flow": ("flow", "netflow", "inflow", "outflow", "volume", "oi", "liquidation"),
}


def horizon_bucket(days: float | None) -> str:
    if days is None or days <= 0:
        return "unspecified"
    for upper, name in _HORIZON_BUCKETS:
        if float(days) <= upper:
            return name
    return "annual+"


def signal_transform(text: str) -> str:
    """The canonical transform named anywhere in the idea's text. First match wins, and the order
    of _TRANSFORMS is therefore meaningful -- specific mechanics before generic shapes."""
    low = (text or "").lower()
    for canon, needles in _TRANSFORMS.items():
        if any(n in low for n in needles):
            return canon
    return "unclassified"


def feature_family(hyp: Any) -> str:
    """The data axis an idea draws on. `family` when the model carries one, else the edge_source
    stem -- never the SYMBOL, because 40 symbols on one mechanism is one idea, not forty."""
    fam = getattr(hyp, "family", None)
    if fam is not None:
        return str(getattr(fam, "value", fam))
    src = str(getattr(hyp, "edge_source", "") or "")
    return src.split("/")[0].strip().lower() or "unknown"


def _horizon_of(hyp: Any) -> float | None:
    params = dict(getattr(hyp, "params", {}) or {})
    for key in ("horizon_days", "horizon", "lookback_days", "lookback", "window", "holding_days"):
        if key in params:
            try:
                return float(params[key])
            except (TypeError, ValueError):
                continue
    return None


def fingerprint(hyp: Any) -> str:
    """feature-family / signal-transform / horizon-bucket -- the idea, with the knobs removed."""
    text = " ".join(str(x) for x in (
        getattr(hyp, "subtype", ""), getattr(hyp, "edge_source", ""),
        getattr(getattr(hyp, "mechanism", None), "value", getattr(hyp, "mechanism", "")),
    ))
    return f"{feature_family(hyp)}/{signal_transform(text)}/{horizon_bucket(_horizon_of(hyp))}"


def fingerprint_hash(hyp: Any) -> str:
    return hashlib.sha256(fingerprint(hyp).encode("utf-8")).hexdigest()[:16]


_TOKEN = re.compile(r"[a-z0-9]+")
#: Words that carry no mechanism information. Without this the Jaccard proxy scores every pair as
#: similar on English scaffolding alone and the metric never moves.
_STOP = frozenset((
    "the", "a", "an", "of", "in", "on", "for", "to", "and", "or", "is", "are", "be", "as", "by",
    "with", "that", "this", "it", "its", "from", "at", "we", "our", "when", "than", "then",
    "signal", "strategy", "hypothesis", "returns", "return", "market", "price", "prices", "data",
))


def tokens(text: str) -> frozenset[str]:
    return frozenset(t for t in _TOKEN.findall((text or "").lower())
                     if len(t) > 2 and t not in _STOP)


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def describe(hyp: Any) -> str:
    """The text the semantic proxy compares. Excludes SYMBOL and raw numeric params -- the same
    mechanism on BTC and on ETH is one idea -- but INCLUDES the horizon bucket.

    THE BUG THAT REQUIRED THE HORIZON, caught by its own test: without it a 7-day and a 90-day
    carry signal produced identical token sets, so the near-duplicate check scored them at
    Jaccard 1.00 and BLOCKED the 90-day version -- despite their fingerprints differing
    (carry/carry/weeks vs carry/carry/quarters). The semantic proxy was overriding the structured
    dimension it is supposed to complement, and silently deleting a genuinely different question.
    That is precisely the over-tight-funnel failure this whole module warns about, produced by the
    module itself. The proxy must agree with the fingerprint, never fight it.
    """
    return " ".join(str(x) for x in (
        feature_family(hyp), getattr(hyp, "subtype", ""), getattr(hyp, "edge_source", ""),
        getattr(getattr(hyp, "mechanism", None), "value", ""),
        f"horizon_{horizon_bucket(_horizon_of(hyp))}",
        " ".join(getattr(hyp, "failure_modes", []) or []),
    ))

```

### libs/research/pre_filter.py
```python
"""Tiered gauntlet pre-filter -- HYPOTHESIS_MAX_SPEC component #1, the cheap stage before
heavy validation compute (spec'd 2026-07-20, built 2026-07-29).

WHY THIS EXISTS, measured not asserted: the 420-candidate campaign burned full-gauntlet compute
on every candidate, and the per-candidate gates show most died for CHEAP reasons -- weak
in-sample edge, cost exceeding gross edge, degenerate activity -- all detectable in
microseconds from the return stream alone. The pre-filter rejects ONLY on cheap, unambiguous
evidence; anything borderline ESCALATES to the full gauntlet. It must never become a silent
alpha killer, so every decision lands in an append-only ledger with pass/fail counts and a
spot-audit cadence (audit every 3 days once >=50 rejects accumulate in the window, weekly
otherwise -- principal 2026-07-20: audit cadence is gated by throughput volume, not data drift).

MULTIPLICITY, the rule that keeps this honest: a pre-filter REJECT still counts in the trial
ledger (n_trials / DSR budget). The filter saves COMPUTE, never multiplicity budget -- a
candidate we looked at is a candidate we tested, however cheaply. Anything else would let the
desk peek for free, which is the exact overfitting engine the gauntlet exists to stop.

The novelty/graveyard half of spec component #1 deliberately lives UPSTREAM at generation time
(run_axis_generate's do_not_repeat + the novelty gate that blocked coinmetrics netflow on
2026-07-28) -- identity checks belong where names are minted, numeric checks belong here.

Stage-A discipline: ZERO promotion authority. PASS means "worth heavy compute", nothing more.
Pure numpy. import from libs.research.pre_filter.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

_LEDGER = Path("data/pre_filter_ledger.jsonl")

# REJECT thresholds -- deliberately far from the gauntlet's own bars, so this stage can only
# remove candidates the full gauntlet would reject with near-certainty. Borderline escalates.
_T_REJECT = 0.0          # in-sample t <= 0: the sample itself points the wrong way
_GROSS_COST_MULT = 2.0   # spec: gross edge must exceed 2x modeled round-trip cost
_MIN_ACTIVE_FRAC = 0.02  # <2% of periods active = degenerate turnover (a handful of bets)
_MIN_ACTIVE_N = 20       # and never judge economics on fewer than 20 active periods
_SIGN_WINDOWS = 4        # sign stability: quarters of the active sample
_MAX_ONE_WINDOW_FRAC = 0.90  # >90% of total P&L from one quarter = single-event artifact


def pre_filter(returns: np.ndarray, *, name: str,
               rt_cost_per_trade: float | None = None,
               ledger: Path | None = _LEDGER) -> dict[str, Any]:
    """Cheap numeric screen on a candidate's per-period return stream.

    returns: full-length per-period simple returns, 0.0 = flat/inactive (the run_discovery
    convention). rt_cost_per_trade: modeled round-trip cost per position change, in return
    units (e.g. 9e-4 for 9 bps); None = cost check skipped (escalate on cost).

    Verdicts:
      REJECT   -- cheap, unambiguous: wrong-sign in-sample t, gross edge under 2x modeled
                  round-trip cost, degenerate activity, or single-window P&L concentration.
                  Routed to the graveyard by the caller WITH the reason; still charges a trial.
      ESCALATE -- everything else, including every borderline: full gauntlet, unchanged bar.
    There is deliberately no PASS-and-skip-the-gauntlet outcome. The filter only ever saves
    compute on the doomed, never certifies the promising.
    """
    r = np.asarray(returns, dtype="float64")
    active = r[r != 0.0]
    n_act = len(active)
    out: dict[str, Any] = {"name": name, "n": len(r), "n_active": n_act,
                           "stage": "pre-filter (zero promotion authority)"}

    if n_act < _MIN_ACTIVE_N or n_act < _MIN_ACTIVE_FRAC * len(r):
        # Too few bets to call the economics unambiguous in EITHER direction -- but a strategy
        # that basically never trades cannot clear a gauntlet built on >=250 active days either.
        # This is the one structural reject: not "the edge is bad" but "there is no strategy here".
        out.update(verdict="REJECT", reason="degenerate-turnover",
                   detail=f"{n_act} active of {len(r)} periods")
        return _log(out, ledger)

    sd = float(active.std())
    t_is = float(active.mean() / sd * np.sqrt(n_act)) if sd > 0 else 0.0
    out["t_insample"] = round(t_is, 2)
    if t_is <= _T_REJECT:
        out.update(verdict="REJECT", reason="wrong-sign-insample",
                   detail=f"t={t_is:.2f} on n={n_act}")
        return _log(out, ledger)

    # Cost-floor sanity (spec): GROSS per-trade edge must beat 2x the modeled round-trip cost.
    # Position changes approximated by activity transitions -- cheap and direction-agnostic.
    if rt_cost_per_trade is not None and rt_cost_per_trade > 0:
        trades = max(int(np.count_nonzero(np.diff((r != 0.0).astype("int8")) != 0)) // 2, 1)
        gross_per_trade = float(active.sum()) / trades
        out["gross_per_trade"] = round(gross_per_trade, 6)
        out["rt_cost"] = float(rt_cost_per_trade)
        if gross_per_trade < _GROSS_COST_MULT * rt_cost_per_trade:
            out.update(verdict="REJECT", reason="cost-exceeds-edge",
                       detail=(f"gross/trade {gross_per_trade:.5f} < "
                               f"{_GROSS_COST_MULT}x rt {rt_cost_per_trade:.5f}"))
            return _log(out, ledger)

    # Sign stability: split the ACTIVE stream into quarters; a candidate whose entire P&L sits
    # in one quarter is a single-event artifact, not a mechanism (the 2020-01-03 Soleimani
    # relabelling, register #79, is the canonical instance of this failure).
    chunks = np.array_split(active, _SIGN_WINDOWS)
    sums = np.array([c.sum() for c in chunks])
    out["window_sums"] = [round(float(x), 5) for x in sums]
    # Dominance is measured against GROSS window P&L (sum of |window sums|), not net: on a
    # near-zero-sum noise stream the net denominator collapses and one lucky window reads as
    # ">90% of total" -- a false trip measured on the first calibration run. Gross dominance
    # only fires when one window carries essentially all the P&L that exists anywhere.
    gross = float(np.abs(sums).sum())
    if gross > 0 and float(sums.max()) / gross > _MAX_ONE_WINDOW_FRAC:
        out.update(verdict="REJECT", reason="single-window-concentration",
                   detail=f"{float(sums.max()) / gross:.0%} of gross P&L in one window")
        return _log(out, ledger)

    out.update(verdict="ESCALATE", reason=None,
               detail="cleared cheap checks -- full gauntlet, unchanged bar")
    return _log(out, ledger)


def _log(out: dict[str, Any], ledger: Path | None) -> dict[str, Any]:
    if ledger is not None:
        ledger.parent.mkdir(parents=True, exist_ok=True)
        row = {"ts": datetime.now(tz=UTC).isoformat(), **out}
        with ledger.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")
    return out


def ledger_counts(ledger: Path = _LEDGER, *, window_days: float = 7.0) -> dict[str, int]:
    """Pass/fail counts over the trailing window -- the KPI feed and the audit trigger input."""
    counts = {"ESCALATE": 0, "REJECT": 0}
    if not ledger.exists():
        return counts
    floor = datetime.now(tz=UTC) - timedelta(days=window_days)
    for line in ledger.read_text("utf-8").splitlines():
        try:
            row = json.loads(line)
            if datetime.fromisoformat(str(row["ts"])) >= floor:
                v = str(row.get("verdict", ""))
                counts[v] = counts.get(v, 0) + 1
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    return counts


def audit_due(ledger: Path = _LEDGER, *, state: Path | None = None) -> bool:
    """Spot-audit cadence per spec: >=50 rejects in the trailing week -> audit every 3 days;
    otherwise weekly. The AUDIT itself is a human/organ action (re-derive a sample of rejects
    at full depth and check the filter was right); this only answers "is one due now".
    state: json file holding {"last_audit": iso} (default data/pre_filter_audit_state.json).
    """
    st = state if state is not None else Path("data/pre_filter_audit_state.json")
    every = 3.0 if ledger_counts(ledger)["REJECT"] >= 50 else 7.0
    try:
        last = datetime.fromisoformat(json.loads(st.read_text("utf-8"))["last_audit"])
    except (OSError, json.JSONDecodeError, KeyError, ValueError):
        return True
    return datetime.now(tz=UTC) - last >= timedelta(days=every)

```

### libs/research/promotion_latency.py
```python
"""SHADOW -> LIVE LATENCY, MEASURED -- and the only two honest ways to shorten it.

THE PRINCIPAL'S CONCERN (2026-07-30), stated exactly: the promotion process must not be so slow
that *"by the time they reach live the capital is already outgrown its capacity."* At 100%/yr the
book doubles in 253 days; at the desk's stretch pace it doubles in weeks. An edge that needs 90
days of clock plus an unbounded queue wait can be a rounding error on arrival. That is not caution
-- caution that guarantees a zero is just a slower way of declining.

`libs.autodiscovery.validation.capacity_race` already answers "does this edge reach live before the
book outgrows it?" -- but it takes `validation_days` as an ARGUMENT, and until now every caller was
a test passing a hardcoded 90. The race was therefore run against an assumption. This module
measures the number instead, decomposed, with the PROVENANCE of each component attached, because
an unmeasured component quoted as measured is precisely the reality gap L2.10 exists to catch.

THREE COMPONENTS, and the middle one is the one everybody forgets:
  CLOCK       the pre-registered forward window itself.
  QUEUE WAIT  time spent waiting for a free forward slot. The cohort is capped at
              MAX_FORWARD_SLOTS=12 (that cap is what keeps the Holm bar fixed), so when every slot
              is occupied a new candidate accrues NOTHING while its capacity decays. This is real
              latency, it is invisible in any per-candidate view, and it is usually the largest
              term when the desk is busy.
  DECISION    clock completion -> a promotion decision actually taken.

=================================================================================================
THE ACCELERANT, AND THE TRAP INSIDE IT
=================================================================================================
L1.6 is not negotiable: the confirmation bar never loosens, and a DOA edge is NEVER fixed by a
shorter clock. So the only honest accelerants are (1) NOT QUEUEING -- run the slot now rather than
later, which costs nothing statistically -- and (2) MORE OBSERVATIONS PER DAY.

The second one is where a desk quietly deceives itself, so it is fenced here.

  * FOR EVENT-DRIVEN P&L -- funding settlements, auctions, rebalances, discrete cash flows -- a
    higher observation frequency means MORE ACTUAL EVENTS. Perp funding settles 3x daily, so an 8h
    panel accrues 3 realised payments per day instead of 1. The desk measured these at vif 1.008,
    i.e. essentially independent, so effective N genuinely triples and the same t-stat bar is
    reached in roughly a third of the wall clock. The BAR IS UNCHANGED; only the calendar moves.

  * FOR DIFFUSIVE P&L -- anything whose return is a price change -- it is FALSE. Estimating the
    drift of a diffusion depends on the HORIZON, not the sampling frequency: sampling a 90-day
    window hourly instead of daily gives 24x the rows and no additional information about the
    mean. (Merton 1980; it is why realised volatility converges under fine sampling and expected
    return does not.) A desk that "accelerates" a price-based signal by sampling faster has not
    accelerated anything -- it has manufactured a t-stat out of oversampling and loosened its own
    bar while believing it did the opposite.

So `frequency_accelerant` REFUSES to grant a speed-up unless the caller declares the P&L is
event-driven AND the event rate itself rises. Refusal is the default: an unknown process gets no
accelerant. This is the direction that costs a few days of calendar and cannot manufacture edge.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]

#: Design clock for a cohort candidate, in days. The cash-carry PRIMARY carries a measured 40-day
#: fast-track (run_cashcarry_shadow.py) because it was registered alone, before any cohort; a
#: cohort entrant carries the Holm correction and the full window.
DESIGN_CLOCK_DAYS = 90.0

#: Measured variance-inflation for 8h funding observations (gap #44). Near 1.0 => near-independent.
FUNDING_8H_VIF = 1.008

#: Observations per day at each supported cadence.
_CADENCE_PER_DAY = {"daily": 1.0, "8h": 3.0, "hourly": 24.0}


@dataclass(frozen=True)
class LatencyComponent:
    days: float
    provenance: str          # MEASURED | DESIGN | ESTIMATED
    detail: str


@dataclass(frozen=True)
class PipelineLatency:
    clock: LatencyComponent
    queue_wait: LatencyComponent
    decision: LatencyComponent
    generated: str = field(default_factory=lambda: datetime.now(tz=UTC).isoformat())

    @property
    def total_days(self) -> float:
        return self.clock.days + self.queue_wait.days + self.decision.days

    @property
    def fully_measured(self) -> bool:
        return all(c.provenance == "MEASURED"
                   for c in (self.clock, self.queue_wait, self.decision))

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_days": round(self.total_days, 1),
            "fully_measured": self.fully_measured,
            "generated": self.generated,
            "components": {name: {"days": round(c.days, 1), "provenance": c.provenance,
                                  "detail": c.detail}
                           for name, c in (("clock", self.clock), ("queue_wait", self.queue_wait),
                                           ("decision", self.decision))},
        }


def _slot_occupancy() -> tuple[int, int, list[str]]:
    """(occupied, cap, names). Import-guarded: a missing registry must not crash the queue."""
    try:
        from libs.research.slot_registry import MAX_FORWARD_SLOTS, derive_slots
    except ImportError:
        return 0, 12, []
    snap = derive_slots()
    slots = snap.get("slots", []) or []
    return len(slots), int(MAX_FORWARD_SLOTS), [str(s.get("name", "?")) for s in slots]


def queue_wait_days() -> LatencyComponent:
    """How long a NEW candidate waits before its clock can even start.

    THE TERM EVERYBODY FORGETS. The forward cohort is capped so the Holm bar stays fixed; when the
    cap is full, a new candidate accrues zero evidence while its capacity decays against a growing
    book. Per-candidate views never show this -- the candidate looks 'in progress' while it is
    actually parked. It is real latency and it belongs in the race.
    """
    occupied, cap, names = _slot_occupancy()
    free = cap - occupied
    if free > 0:
        return LatencyComponent(
            0.0, "MEASURED",
            f"{free}/{cap} forward slots free ({occupied} occupied) -- a new clock starts today")
    # Full cohort: the wait is until the longest-running clock completes. Without per-slot start
    # dates this is the design clock, and it is labelled as such rather than dressed as measured.
    return LatencyComponent(
        DESIGN_CLOCK_DAYS, "ESTIMATED",
        f"cohort FULL ({occupied}/{cap}: {', '.join(names[:6])}) -- a new candidate cannot start "
        f"a clock until one completes; upper-bounded by the design clock")


def clock_days(*, fast_track_eligible: bool = False) -> LatencyComponent:
    """The pre-registered forward window. Never shortened by this module -- only reported."""
    if fast_track_eligible:
        return LatencyComponent(
            40.0, "MEASURED",
            "40d fast-track (run_cashcarry_shadow.py): NW-t>=1.65 + fwd>=0.5x backtest + regime "
            "evidence. Applies to a PRE-REGISTERED PRIMARY registered before any cohort, which is "
            "why it is Holm-exempt -- it is not a shorter bar, it is a smaller family")
    return LatencyComponent(
        DESIGN_CLOCK_DAYS, "DESIGN",
        "design forward window for a cohort entrant (carries the Holm correction over all "
        "trailing-180d entrants including killed ones)")


def decision_lag_days() -> LatencyComponent:
    """Clock completion -> decision taken. Measured from the decision ledger when it has rows."""
    ledger = _ROOT / "data/decision_ledger.json"
    try:
        rows = json.loads(ledger.read_text("utf-8"))
        rows = rows.get("decisions", rows) if isinstance(rows, dict) else rows
    except (OSError, ValueError):
        rows = []
    lags: list[float] = []
    for r in rows if isinstance(rows, list) else []:
        raised, closed = r.get("raised") or r.get("opened"), r.get("closed") or r.get("decided")
        if not (raised and closed):
            continue
        try:
            lags.append((datetime.fromisoformat(str(closed))
                         - datetime.fromisoformat(str(raised))).total_seconds() / 86400.0)
        except ValueError:
            continue
    if len(lags) >= 3:
        lags.sort()
        med = lags[len(lags) // 2]
        return LatencyComponent(max(med, 0.0), "MEASURED",
                                f"median of {len(lags)} closed decision-ledger rows")
    # The cycle runs daily, so one day is the floor a decision can possibly take.
    return LatencyComponent(1.0, "ESTIMATED",
                            f"only {len(lags)} closed ledger rows (<3) -- floored at the daily "
                            "cycle cadence; re-measures automatically as the ledger fills")


def measure(*, fast_track_eligible: bool = False) -> PipelineLatency:
    return PipelineLatency(clock=clock_days(fast_track_eligible=fast_track_eligible),
                           queue_wait=queue_wait_days(), decision=decision_lag_days())


def frequency_accelerant(cadence: str, *, pnl_is_event_driven: bool,
                         event_rate_rises: bool, vif: float = FUNDING_8H_VIF) -> dict[str, Any]:
    """Wall-clock speed-up from observing faster -- GRANTED ONLY WHERE IT IS REAL.

    Returns the multiplier on effective sample size and the resulting wall-clock divisor, or a
    REFUSED verdict with the reason. Refusal is the default.

    The refusal is the entire value of this function. Granting a diffusive process a speed-up for
    finer sampling would loosen the confirmation bar while looking like an optimisation -- the
    exact shape of self-deception L1.6 and the two-stage law exist to prevent, and the shape a
    desk under time pressure is most likely to talk itself into.
    """
    per_day = _CADENCE_PER_DAY.get(cadence)
    if per_day is None:
        return {"granted": False, "divisor": 1.0,
                "reason": f"unknown cadence {cadence!r} -- no accelerant without a declared rate"}
    if per_day <= 1.0:
        return {"granted": False, "divisor": 1.0, "reason": "cadence is not faster than daily"}
    if not pnl_is_event_driven:
        return {"granted": False, "divisor": 1.0,
                "reason": "P&L is DIFFUSIVE (price-change). Drift estimation depends on the "
                          "HORIZON, not the sampling frequency -- finer sampling of the same "
                          "window adds rows and zero information about the mean. Granting a "
                          "speed-up here would manufacture a t-stat out of oversampling."}
    if not event_rate_rises:
        return {"granted": False, "divisor": 1.0,
                "reason": "P&L is event-driven but the EVENT RATE does not rise at this cadence "
                          "-- sampling between events resamples the same cash flows"}
    eff = per_day / max(vif, 1e-9)
    return {"granted": True, "divisor": eff, "effective_n_multiple": round(eff, 3),
            "reason": f"event-driven P&L at {per_day:.0f} events/day, vif {vif} -- effective N "
                      f"x{eff:.2f}, so the SAME t-stat bar is reached in 1/{eff:.2f} of the wall "
                      "clock. The bar is unchanged; only the calendar moves."}

```

### libs/research/source_backlog.py
```python
"""Source-verification backlog picker -- clears the EXISTING catalogue queue, never generates more.

The desk's data-hunting organs (prospector/litminer/dataaxis) already catalogue candidate sources
faster than they get verified (docs/research/data_axis_watchlist.md carries a real backlog). The
bottleneck was never generation -- it is VERIFICATION (read the actual docs/ToS, test the actual
endpoint; the Baidu-vs-NAVER distinction this session took real reading, not a prompt).
So this module does NOT propose new sources; it parses the EXISTING catalogue's source cards and
picks the next ones still genuinely pending -- "if not already in system" -- so a cycle spends its
verification effort on the real backlog instead of re-litigating settled cards or, worse, growing
the pile faster than it shrinks.

Grade taxonomy (as written in the source cards, natural-language, not a rigid enum):
  RESOLVED     -- verified-clean or destroyed-at-source, with no other component pending. Excluded
                  from every queue: it is "already in system," settled, work is over.
  VERIFICATION -- needs-monitoring / UNVERIFIED (bare, or as any component of a compound grade like
                  "needs-monitoring (forward) / destroyed-at-source (backfill)" -- a partial
                  resolution still leaves real work, so the whole card stays pending, conservative).
                  This is a TECHNICAL check: read the docs, hit the endpoint, diff vs ground truth.
  LEGITIMACY   -- needs-legitimacy-review. A POLICY/legal decision (account-gating, ToS, licensing),
                  not a technical test -- kept in its own queue so it is never silently treated as
                  "verified" by a mechanical script, and never mixed with technical-check items.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

_CARD_RE = re.compile(r"^### (\d+)\.\s+(.+?)\s+—\s+grade:\s*(.+?)\s*$", re.MULTILINE)


class SourceCard(BaseModel):
    """One catalogued source card, as written in the watchlist."""

    model_config = ConfigDict(frozen=True)

    card_id: int
    name: str
    grade_raw: str
    category: str  # "resolved" | "verification" | "legitimacy"


def _classify(grade_raw: str) -> str:
    g = grade_raw.lower()
    # Check non-terminal substrings FIRST -- a compound grade with ANY pending component (e.g.
    # "needs-monitoring (forward) / destroyed-at-source (backfill)") stays pending as a whole; a
    # partially-resolved card still has real work left, so it is never silently closed out.
    if "needs-legitimacy-review" in g:
        return "legitimacy"
    if "needs-monitoring" in g or "unverified" in g:
        return "verification"
    if "verified-clean" in g or "destroyed-at-source" in g:
        return "resolved"
    return "verification"  # unrecognized grade text -- fail open to pending, never silently drop


def parse_watchlist(text: str) -> list[SourceCard]:
    """Extract every ``### N. Name — grade: ...`` source card from a watchlist markdown body."""
    cards = []
    for m in _CARD_RE.finditer(text):
        card_id, name, grade_raw = int(m.group(1)), m.group(2).strip(), m.group(3).strip()
        cards.append(SourceCard(
            card_id=card_id, name=name, grade_raw=grade_raw, category=_classify(grade_raw),
        ))
    return cards


class BacklogReport(BaseModel):
    """The parsed backlog, split by queue -- resolved cards are reported but never re-worked."""

    model_config = ConfigDict(frozen=True)

    n_total: int
    n_resolved: int
    n_verification_pending: int
    n_legitimacy_pending: int
    next_verification: tuple[str, ...]  # names, priority order, capped
    next_legitimacy: tuple[str, ...]
    verdict: str


def next_pending(cards: Sequence[SourceCard], *, limit: int = 0) -> BacklogReport:
    """Pick the next items to work THIS cycle -- excluding anything already resolved.

    Priority within the verification queue: ``needs-monitoring`` cards (already partially
    corroborated -- cheaper to finish) before bare ``UNVERIFIED`` ones (found, nothing confirmed --
    more work), then by card id (oldest backlog first, so a shiny new catalogue entry never jumps a
    card that has been waiting -- the same anti-hype-bias reasoning as near-miss-first reject
    scoring). ``limit`` <= 0 (the default) surfaces ALL pending cards --
    conversion is never throttled; a positive value caps the batch for display only.
    """
    resolved = [c for c in cards if c.category == "resolved"]
    verif = [c for c in cards if c.category == "verification"]
    legit = [c for c in cards if c.category == "legitimacy"]

    def _verif_rank(c: SourceCard) -> tuple[int, int]:
        cheaper = 0 if "needs-monitoring" in c.grade_raw.lower() else 1
        return (cheaper, c.card_id)

    verif_sorted = sorted(verif, key=_verif_rank)
    legit_sorted = sorted(legit, key=lambda c: c.card_id)
    # limit <= 0 means UNBOUNDED (principal 2026-07-25: conversion must always maximise and
    # exhaust; a cap on how many findings are even SURFACED throttles conversion before work
    # starts). Note `[:0]` is EMPTY, not unbounded -- the slice must be skipped, not zeroed.
    next_v = tuple(c.name for c in (verif_sorted if limit <= 0 else verif_sorted[:limit]))
    next_l = tuple(c.name for c in (legit_sorted if limit <= 0 else legit_sorted[:limit]))

    if not verif and not legit:
        verdict = f"backlog clear: all {len(resolved)} catalogued source(s) resolved"
    else:
        verdict = (
            f"{len(verif)} pending technical verification, {len(legit)} pending a legitimacy/"
            f"policy decision, {len(resolved)} already resolved (excluded) -- this cycle: "
            f"verify {list(next_v) or 'none'}"
        )
    return BacklogReport(
        n_total=len(cards), n_resolved=len(resolved),
        n_verification_pending=len(verif), n_legitimacy_pending=len(legit),
        next_verification=next_v, next_legitimacy=next_l, verdict=verdict,
    )


def backlog_from_file(path: Path, *, limit: int = 0) -> BacklogReport:
    """Convenience: parse a watchlist file straight to its next-pending report."""
    return next_pending(parse_watchlist(path.read_text("utf-8")), limit=limit)

```

### libs/research/stationarity.py
```python
"""Cointegration / stationarity tests and GARCH volatility — thin wrappers over statsmodels + arch.

The constitution bans hand-rolled ADF/GARCH: a subtly-wrong stationarity test admits a spurious
stat-arb card (gold-silver / pairs style), which is exactly the leak this desk exists to catch. So
rather than own these, we defer to the battle-tested references and keep only a thin, typed seam.

Optional dependency (kept out of the core install): ``pip install -e ".[stats]"``. Each function
raises :class:`StatsBackendMissing` with the exact remedy if its backend is absent, so a lean core
install still imports this module fine — the cost lands only when a stat-arb card is actually built.
"""

from __future__ import annotations

import numpy as np

_REMEDY = "install the optional extra: pip install -e '.[stats]'"


class StatsBackendMissing(RuntimeError):
    """Raised when an optional statistics backend (statsmodels / arch) is not installed."""


def adf_pvalue(series: np.ndarray) -> float:
    """Augmented Dickey-Fuller p-value. H0 = a unit root (non-stationary); a low p-value (<0.05)
    rejects it — evidence the series is stationary. AIC-selected lag order."""
    try:
        from statsmodels.tsa.stattools import adfuller
    except ImportError as exc:  # pragma: no cover
        raise StatsBackendMissing(f"statsmodels missing; {_REMEDY}") from exc
    return float(adfuller(np.asarray(series, dtype="float64"), autolag="AIC")[1])


def engle_granger_pvalue(y: np.ndarray, x: np.ndarray) -> float:
    """Engle-Granger cointegration p-value for ``y`` on ``x``. A low p-value (<0.05) is evidence the
    pair is cointegrated (a stationary linear combination exists) — the precondition for a pairs /
    stat-arb card."""
    try:
        from statsmodels.tsa.stattools import coint
    except ImportError as exc:  # pragma: no cover
        raise StatsBackendMissing(f"statsmodels missing; {_REMEDY}") from exc
    return float(coint(np.asarray(y, dtype="float64"), np.asarray(x, dtype="float64"))[1])


def garch_conditional_vol(returns: np.ndarray, *, p: int = 1, q: int = 1) -> np.ndarray:
    """Fitted conditional volatility series from a GARCH(``p``, ``q``) on ``returns`` (same length).

    Returns per-period conditional standard deviations in the units of ``returns``. Use for a
    volatility-regime / vol-targeting input where a rolling std is too naive."""
    try:
        from arch import arch_model
    except ImportError as exc:  # pragma: no cover
        raise StatsBackendMissing(f"arch missing; {_REMEDY}") from exc
    r = np.asarray(returns, dtype="float64")
    res = arch_model(r, vol="GARCH", p=p, q=q, mean="Zero", rescale=False).fit(disp="off")
    return np.asarray(res.conditional_volatility, dtype="float64")

```

### libs/self_improvement/errors.py
```python
"""Self-improvement (Stage 13) exceptions."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class SelfImprovementError(QuantPlatformError):
    """Invalid self-improvement inputs or configuration."""


class GovernanceError(SelfImprovementError):
    """A governance rule was violated (e.g. deploying an unvalidated learned policy, or
    Stage 13 attempting to change production weights without Portfolio Engine approval)."""

```

### libs/signal_engine/aggregation.py
```python
"""Signal aggregation — combine weighted alpha votes into one net directional view.

Produces the net direction, an aggregated strength (net signed weight), an alpha-agreement ratio
(how much of the weight pulls the same way), and a per-alpha signed breakdown used for the
explainability layer and audit.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from libs.signal_engine.models import AlphaSignal, Direction

_EPS = 1e-12


@dataclass(frozen=True)
class Aggregation:
    direction: Direction
    aggregated_strength: float  # 0..1
    alpha_agreement: float  # 0..1
    breakdown: dict[str, float]  # alpha_id -> signed contribution


class SignalAggregator:
    """Aggregates directional alpha votes weighted by :class:`DynamicWeighting`."""

    def __init__(self, *, flat_band: float = 1e-6) -> None:
        # Net strength within +/- flat_band is treated as no edge -> FLAT.
        self.flat_band = flat_band

    def aggregate(
        self, signals: Sequence[AlphaSignal], weights: Mapping[str, float]
    ) -> Aggregation:
        breakdown = {
            s.alpha_id: weights.get(s.alpha_id, 0.0) * s.direction.sign for s in signals
        }
        net = sum(breakdown.values())
        total_weight = sum(weights.get(s.alpha_id, 0.0) for s in signals)

        if abs(net) <= self.flat_band:
            return Aggregation(Direction.FLAT, 0.0, 0.0, breakdown)

        direction = Direction.BUY if net > 0 else Direction.SELL
        # Agreement = share of total weight pulling in the net direction.
        agreeing = sum(
            weights.get(s.alpha_id, 0.0)
            for s in signals
            if s.direction.sign == direction.sign
        )
        agreement = agreeing / total_weight if total_weight > _EPS else 0.0
        return Aggregation(
            direction=direction,
            aggregated_strength=min(1.0, abs(net)),
            alpha_agreement=min(1.0, agreement),
            breakdown=breakdown,
        )

```

### libs/signal_engine/alpha_competition_engine.py
```python
"""Alpha competition engine — alphas compete continuously for influence.

Each alpha earns influence proportional to its current expected risk-adjusted contribution
(Sharpe x health x durability x conviction). The allocation is stateless, so no alpha holds a
permanent preference: influence migrates every bar toward whoever is strongest right now.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from libs.signal_engine.models import AlphaSignal

_EPS = 1e-12


class CompetitionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    influence: dict[str, float]  # alpha_id -> share (sums to ~1, or all 0)
    ranking: list[str]           # alpha_ids best -> worst
    scores: dict[str, float]


def _score(signal: AlphaSignal) -> float:
    return (
        max(0.0, signal.sharpe)
        * max(0.0, signal.health_score / 100.0)
        * max(0.0, signal.decay_multiplier)
        * max(0.0, signal.strength)
    )


class AlphaCompetitionEngine:
    """Allocates influence among alphas by current risk-adjusted strength."""

    def compete(self, signals: Sequence[AlphaSignal]) -> CompetitionResult:
        scores = {s.alpha_id: _score(s) for s in signals}
        total = sum(scores.values())
        if total <= _EPS:
            influence = dict.fromkeys(scores, 0.0)
        else:
            influence = {k: v / total for k, v in scores.items()}
        ranking = sorted(scores, key=lambda k: scores[k], reverse=True)
        return CompetitionResult(influence=influence, ranking=ranking, scores=scores)

```

### libs/signal_engine/confidence_engine.py
```python
"""Confidence engine — fuse every corroborating signal into a single 0..1 confidence.

Combines the meta-model probability, alpha agreement, current/future regime confidence,
cross-asset and microstructure confirmation, capacity confidence, and portfolio contribution.
The blend rewards broad agreement (mean) but punishes any single weak link (min), so a high
confidence requires *all* corroborations, not just one strong one (fail-closed bias).
"""

from __future__ import annotations

from libs.signal_engine.meta_model import MetaModel
from libs.signal_engine.models import ConfidenceResult


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class ConfidenceEngine:
    """Produces a 0..1 confidence and its component breakdown."""

    def __init__(self, *, meta_model: MetaModel | None = None) -> None:
        self.meta_model = meta_model or MetaModel()

    def estimate(
        self,
        *,
        edge_score: float,
        alpha_agreement: float,
        regime_confidence: float,
        future_regime_confidence: float,
        cross_asset_confirmation: float,
        microstructure_confirmation: float,
        capacity_confidence: float,
        portfolio_contribution: float,
        persistence: float,
        stability: float,
    ) -> ConfidenceResult:
        meta = self.meta_model.predict_proba(
            edge=edge_score / 100.0,
            agreement=alpha_agreement,
            persistence=persistence,
            stability=stability,
        )
        components = {
            "meta_model": _clip01(meta),
            "alpha_agreement": _clip01(alpha_agreement),
            "regime_confidence": _clip01(regime_confidence),
            "future_regime_confidence": _clip01(future_regime_confidence),
            "cross_asset_confirmation": _clip01(cross_asset_confirmation),
            "microstructure_confirmation": _clip01(microstructure_confirmation),
            "capacity_confidence": _clip01(capacity_confidence),
            "portfolio_contribution": _clip01(portfolio_contribution),
        }
        values = list(components.values())
        mean = sum(values) / len(values)
        weakest = min(values)
        confidence = _clip01(0.5 * mean + 0.5 * weakest)
        return ConfidenceResult(confidence=confidence, components=components)

```

### libs/signal_engine/engine.py
```python
"""SignalEngine — the exclusive source of all BUY/SELL/FLAT decisions.

No trade may reach the Portfolio Engine, Risk Engine, or Execution Engine without passing through
here. The engine collects, validates, weights, regime-routes, confirms, scores, ranks, and
selects alpha outputs into ``SignalPackage`` objects. It is fail-closed: any missing
corroboration, failed gate, or error resolves to FLAT.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from libs.signal_engine.aggregation import SignalAggregator
from libs.signal_engine.alpha_weighting import DynamicWeighting
from libs.signal_engine.audit import SignalAudit
from libs.signal_engine.capacity import SignalCapacityForecaster
from libs.signal_engine.confidence_engine import ConfidenceEngine
from libs.signal_engine.crowding import SignalCrowdingEngine
from libs.signal_engine.decay import SignalDecayEngine
from libs.signal_engine.edge_estimator import EdgeEstimator
from libs.signal_engine.execution import ExecutionFeasibilityEngine
from libs.signal_engine.expected_value import ExpectedValueEngine
from libs.signal_engine.factor_exposure import FactorExposureEngine
from libs.signal_engine.governance import GovernanceVerdict, signal_governance_gate
from libs.signal_engine.institutional_score import institutional_signal_score
from libs.signal_engine.models import (
    AlphaSignal,
    Direction,
    MarketState,
    SelectionResult,
    TradeCandidate,
)
from libs.signal_engine.persistence import SignalPersistenceEngine, SignalStabilityEngine
from libs.signal_engine.portfolio_context import PortfolioContextEngine
from libs.signal_engine.quality import SignalFilters, SignalQuality
from libs.signal_engine.ranking import rank_trade_candidates
from libs.signal_engine.regime import RegimeRouter, transition_confidence
from libs.signal_engine.selection import SelectionThresholds, select_final_signals
from libs.signal_engine.uncertainty import SignalUncertaintyEngine

_EPS = 1e-12


class SymbolObservation(BaseModel):
    """All inputs the engine needs to evaluate one symbol on one bar."""

    model_config = ConfigDict(frozen=True)

    signals: list[AlphaSignal]
    state: MarketState
    governance_verdict: GovernanceVerdict | None = None
    # decay (rolling metrics; fall back to the edge estimate when absent)
    rolling_profit_factor: float | None = None
    rolling_sharpe: float | None = None
    # capacity / costs (basis points unless stated)
    intended_notional: float = 0.0
    edge_bps: float = 10.0
    slippage_bps: float = 1.0
    commission_frac: float = 0.0
    execution_failure_risk: float = 0.0
    latency_risk: float = 0.0
    # crowding
    avg_alpha_correlation: float = 0.0
    factor_overlap: float = 0.0
    public_crowding: float = 0.0
    # factor exposure
    factor_loadings: dict[str, dict[str, float]] = Field(default_factory=dict)
    # portfolio context
    correlation_to_portfolio: float = 0.0
    marginal_diversification: float = 1.0
    concentration_after: float = 0.0
    # uncertainty / tail
    sample_size: int = 100
    tail_risk_score: float = 0.0
    # persistence
    signal_age: int = 60
    survival: float = 1.0
    flip_frequency: float = 0.0
    noise_level: float = 0.0
    regime_consistency: float = 1.0
    # stability
    oscillation: float = 0.0
    direction_change_rate: float = 0.0
    prediction_stability: float = 1.0
    alpha_stability: float = 1.0
    regime_stability: float = 1.0


class SignalEngine:
    """Coordinates every sub-engine into the exclusive signal pipeline."""

    def __init__(
        self,
        *,
        audit: SignalAudit | None = None,
        thresholds: SelectionThresholds | None = None,
    ) -> None:
        self.filters = SignalFilters()
        self.weighting = DynamicWeighting()
        self.aggregator = SignalAggregator()
        self.router = RegimeRouter()
        self.edge_estimator = EdgeEstimator()
        self.ev_engine = ExpectedValueEngine()
        self.confidence_engine = ConfidenceEngine()
        self.persistence_engine = SignalPersistenceEngine()
        self.stability_engine = SignalStabilityEngine()
        self.decay_engine = SignalDecayEngine()
        self.crowding_engine = SignalCrowdingEngine()
        self.capacity_forecaster = SignalCapacityForecaster()
        self.factor_engine = FactorExposureEngine()
        self.execution_engine = ExecutionFeasibilityEngine()
        self.portfolio_context = PortfolioContextEngine()
        self.uncertainty_engine = SignalUncertaintyEngine()
        self.quality_engine = SignalQuality()
        self.thresholds = thresholds or SelectionThresholds()
        self.audit = audit

    def evaluate(self, observations: Sequence[SymbolObservation]) -> SelectionResult:
        """Evaluate observations and return approved packages plus FLAT reasons."""
        candidates: list[TradeCandidate] = []
        pre_flat: dict[str, str] = {}

        for obs in observations:
            outcome = self._build_candidate(obs)
            if isinstance(outcome, str):
                pre_flat[obs.state.symbol] = outcome
            else:
                candidates.append(outcome)

        ranked = rank_trade_candidates(candidates)
        selection = select_final_signals(ranked, thresholds=self.thresholds)
        merged_rejected = {**pre_flat, **selection.rejected}
        result = SelectionResult(approved=selection.approved, rejected=merged_rejected)

        if self.audit is not None:
            self.audit.record_selection(result)
        return result

    def _build_candidate(self, obs: SymbolObservation) -> TradeCandidate | str:
        """Return a TradeCandidate, or a FLAT reason string (fail-closed)."""
        signals, state = obs.signals, obs.state

        gate = self.filters.pre_filter(signals, state)
        if not gate.ok:
            return gate.reason
        if obs.governance_verdict is not None and not signal_governance_gate(
            obs.governance_verdict
        ):
            return "governance gate failed"

        weights = self.weighting.weights(signals, state)
        aggregation = self.aggregator.aggregate(signals, weights)
        if aggregation.direction is Direction.FLAT:
            return "no net direction"

        edge = self.edge_estimator.estimate(signals, weights, state)
        capacity = self.capacity_forecaster.forecast(
            adv_usd=state.adv_usd, intended_notional=obs.intended_notional, edge_bps=obs.edge_bps
        )
        ev = self.ev_engine.estimate(
            signals, weights,
            spread_bps=state.spread_bps, slippage_bps=obs.slippage_bps,
            market_impact_bps=capacity.future_market_impact_estimate,
            commission_frac=obs.commission_frac,
            execution_failure_risk=obs.execution_failure_risk,
        )
        persistence = self.persistence_engine.assess(
            signal_age=obs.signal_age, survival=obs.survival,
            flip_frequency=obs.flip_frequency, noise_level=obs.noise_level,
            regime_consistency=obs.regime_consistency,
        )
        stability = self.stability_engine.assess(
            oscillation=obs.oscillation, direction_change_rate=obs.direction_change_rate,
            prediction_stability=obs.prediction_stability, alpha_stability=obs.alpha_stability,
            regime_stability=obs.regime_stability,
        )
        decay = self.decay_engine.assess(
            profit_factor=obs.rolling_profit_factor
            if obs.rolling_profit_factor is not None
            else edge.expected_pf,
            sharpe=obs.rolling_sharpe if obs.rolling_sharpe is not None else edge.expected_sharpe,
        )
        crowding = self.crowding_engine.assess(
            avg_alpha_correlation=obs.avg_alpha_correlation,
            factor_overlap=obs.factor_overlap, public_crowding=obs.public_crowding,
        )
        factor = self.factor_engine.assess(signals, weights, loadings=obs.factor_loadings)
        execution = self.execution_engine.assess(
            spread_bps=state.spread_bps, expected_slippage_bps=obs.slippage_bps,
            market_impact_bps=capacity.future_market_impact_estimate,
            liquidity_score=state.liquidity_score, latency_risk=obs.latency_risk,
        )
        uncertainty = self.uncertainty_engine.estimate(
            alpha_agreement=aggregation.alpha_agreement, n_alphas=len(signals),
            sample_size=obs.sample_size, volatility_state=state.volatility_state,
        )
        portfolio_ctx = self.portfolio_context.evaluate(
            candidate_sharpe=edge.expected_sharpe, candidate_sortino=edge.expected_sortino,
            candidate_calmar=edge.expected_calmar,
            correlation_to_portfolio=obs.correlation_to_portfolio,
            marginal_diversification=obs.marginal_diversification,
            concentration_after=obs.concentration_after,
        )

        regime_conf = self._regime_confidence(signals, weights, state)
        same_regime = state.predicted_regime == state.regime
        future_conf = 1.0 if same_regime else transition_confidence(state)
        confidence = self.confidence_engine.estimate(
            edge_score=edge.edge_score, alpha_agreement=aggregation.alpha_agreement,
            regime_confidence=regime_conf, future_regime_confidence=future_conf,
            cross_asset_confirmation=state.cross_asset_score,
            microstructure_confirmation=state.microstructure_score,
            capacity_confidence=capacity.capacity_confidence,
            portfolio_contribution=portfolio_ctx.portfolio_contribution_score / 100.0,
            persistence=persistence.persistence_score / 100.0,
            stability=stability.stability_score / 100.0,
        )
        # Decay erodes confidence directly.
        confidence = confidence.model_copy(
            update={"confidence": confidence.confidence * decay.confidence_multiplier}
        )
        quality = self.quality_engine.score(
            edge_score=edge.edge_score, confidence=confidence.confidence,
            persistence_score=persistence.persistence_score,
            stability_score=stability.stability_score,
            alpha_agreement=aggregation.alpha_agreement,
            decay_weight_multiplier=decay.weight_multiplier,
        )
        institutional = institutional_signal_score(
            edge_score=edge.edge_score, confidence=confidence.confidence,
            capacity_score=capacity.future_capacity_score,
            persistence_score=persistence.persistence_score,
            stability_score=stability.stability_score,
            decay_weight_multiplier=decay.weight_multiplier,
            portfolio_contribution=portfolio_ctx.portfolio_contribution_score,
            execution_score=execution.execution_score,
            tail_risk_score=obs.tail_risk_score,
            uncertainty_score=uncertainty.uncertainty_score,
        )

        return TradeCandidate(
            symbol=state.symbol, direction=aggregation.direction,
            aggregated_strength=aggregation.aggregated_strength,
            alpha_agreement=aggregation.alpha_agreement, alpha_breakdown=aggregation.breakdown,
            regime=state.regime, predicted_regime=state.predicted_regime,
            edge=edge, expected_value=ev, confidence=confidence, quality=quality,
            persistence=persistence, stability=stability, decay=decay,
            factor_exposures=factor, execution=execution, crowding=crowding,
            capacity=capacity, portfolio_context=portfolio_ctx, uncertainty=uncertainty,
            tail_risk_score=obs.tail_risk_score, institutional=institutional,
        )

    def _regime_confidence(
        self, signals: Sequence[AlphaSignal], weights: Mapping[str, float], state: MarketState
    ) -> float:
        total = sum(weights.get(s.alpha_id, 0.0) for s in signals)
        if total <= _EPS:
            return 0.0
        weighted = sum(
            weights.get(s.alpha_id, 0.0) * self.router.route(s, state) for s in signals
        )
        return weighted / total

```

### libs/stage14/governance.py
```python
"""Stage 14 governance — per-allocation gate and portfolio-level kill criteria (fail-closed).

No allocation is permitted unless every rule passes; failing any rule sets the allocation to zero.
Portfolio kill criteria are distinct from per-strategy kills: they can halt the whole book, force
defensive mode, or stop new capital based on portfolio DSR, survival, drawdown, and walk-forward.
"""

from __future__ import annotations

from libs.stage14.models import KillDecision


def portfolio_governance_gate(
    *,
    signal_approved: bool,
    expected_value: float,
    portfolio_contribution: float,
    capacity_available: bool,
    survival_score: float,
    fragility: float,
    correlation_acceptable: bool,
    walk_forward_passed: bool,
    survival_threshold: float = 60.0,
    max_fragility: float = 0.6,
) -> tuple[bool, str]:
    """Return (allowed, reason). Allocation must be zeroed unless allowed is True."""
    if not signal_approved:
        return False, "signal not approved"
    if expected_value <= 0:
        return False, "expected value not positive"
    if portfolio_contribution <= 0:
        return False, "portfolio contribution not positive"
    if not capacity_available:
        return False, "capacity unavailable"
    if survival_score < survival_threshold:
        return False, f"survival score {survival_score:.1f} < {survival_threshold}"
    if fragility > max_fragility:
        return False, f"fragility {fragility:.2f} > {max_fragility}"
    if not correlation_acceptable:
        return False, "portfolio correlation unacceptable"
    if not walk_forward_passed:
        return False, "portfolio walk-forward not passed"
    return True, "approved"


class PortfolioKillCriteria:
    """Portfolio-level halt / defensive / no-new-capital decisions."""

    def __init__(
        self,
        *,
        min_dsr: float = 0.0,
        min_survival_score: float = 50.0,
        max_drawdown: float = 0.20,
    ) -> None:
        self.min_dsr = min_dsr
        self.min_survival_score = min_survival_score
        self.max_drawdown = max_drawdown

    def evaluate(
        self,
        *,
        portfolio_dsr: float,
        survival_score: float,
        drawdown: float,
        walk_forward_passed: bool,
    ) -> KillDecision:
        reasons: list[str] = []
        halt = False
        defensive = False
        no_new_capital = False
        if portfolio_dsr < self.min_dsr:
            halt = True
            reasons.append(f"portfolio DSR {portfolio_dsr:.2f} < {self.min_dsr}")
        if survival_score < self.min_survival_score:
            halt = True
            reasons.append(f"survival score {survival_score:.1f} < {self.min_survival_score}")
        if drawdown > self.max_drawdown:
            defensive = True
            reasons.append(f"drawdown {drawdown:.2%} > {self.max_drawdown:.2%}")
        if not walk_forward_passed:
            no_new_capital = True
            reasons.append("portfolio walk-forward failed")
        return KillDecision(
            halt=halt, defensive_mode=defensive, no_new_capital=no_new_capital, reasons=reasons
        )

```

### libs/stage14_5/crisis_alpha.py
```python
"""Crisis alpha engine — find and prioritize alphas that perform when markets break.

Scores an alpha by its performance across crisis scenarios (crashes, volatility spikes, liquidity
shocks, correlation breakdowns). Crisis alpha carries strategic portfolio value beyond standalone
return: it pays when everything else is failing.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from libs.stage14_5.models import CrisisAlphaResult

_CRISIS_SCENARIOS = ("market_crash", "volatility_spike", "liquidity_shock", "correlation_breakdown")


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class CrisisAlphaEngine:
    """Scores crisis alpha from per-scenario performance (positive = pays during crises)."""

    def __init__(self, *, threshold: float = 55.0, return_scale: float = 0.10) -> None:
        self.threshold = threshold
        self.return_scale = return_scale  # return that maps to a full 0..1 scenario score

    def evaluate(self, scenario_returns: Mapping[str, float]) -> CrisisAlphaResult:
        by_scenario = {
            s: _clip01(0.5 + float(scenario_returns.get(s, 0.0)) / (2.0 * self.return_scale))
            for s in _CRISIS_SCENARIOS
        }
        score = 100.0 * float(np.mean(list(by_scenario.values())))
        return CrisisAlphaResult(
            crisis_alpha_score=score, by_scenario=by_scenario,
            is_crisis_alpha=score >= self.threshold,
        )

```

### libs/stage14_5/models.py
```python
"""Stage 14.5 models — hedging, crisis alpha, and exposure management.

Institutional hedging, not retail offset: protect long-term geometric growth via alpha/factor/
regime diversification and crisis alpha, never by cosmetically reducing volatility. Survival
dominates return; geometric growth dominates smoothness. These models describe exposures, scores,
hedge proposals, governance and lifecycle; the engines compute them.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from libs.core.time import to_iso8601, utcnow


class HedgeType(StrEnum):
    ALPHA = "alpha"        # rebalance toward under-represented alpha families
    FACTOR = "factor"      # reduce a concentrated factor exposure
    REGIME = "regime"      # add exposure to under-covered regimes
    CRISIS = "crisis"      # add crisis-alpha exposure


class AlphaFamily(StrEnum):
    TREND = "trend"
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    VOLATILITY = "volatility"
    CARRY = "carry"
    MACRO = "macro"
    STRUCTURAL = "structural"


class FactorExposureResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    net_usd: float
    net_directional: float
    beta: float
    volatility_exposure: float
    factor_exposure_score: float  # 0-100 (higher = more concentrated = worse)
    acceptable: bool


class TailRiskResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    tail_loss_probability: float
    expected_tail_loss: float
    extreme_drawdown_risk: float
    correlation_collapse_risk: float
    tail_risk_score: float  # 0-100 (higher = worse)
    acceptable: bool


class CorrelationShockResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    base_avg_correlation: float
    shocked_avg_correlation: float
    diversification_loss: float       # 0..1 fraction of effective bets lost under shock
    correlation_fragility_score: float  # 0-100 (higher = more fragile)
    fragile: bool


class ConcentrationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol_concentration: float
    alpha_concentration: float
    family_concentration: float
    factor_concentration: float
    regime_concentration: float
    concentration_score: float  # 0-100 (higher = more concentrated = worse)
    acceptable: bool


class RegimeExposureResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    by_regime: dict[str, float]
    regime_balance_score: float  # 0-100 (higher = better balanced)
    uncovered_regimes: list[str]
    balanced: bool


class CrisisAlphaResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    crisis_alpha_score: float  # 0-100 (higher = stronger crisis alpha)
    by_scenario: dict[str, float]
    is_crisis_alpha: bool


class HedgeProposal(BaseModel):
    """A proposed institutional hedge (diversifying tilt / crisis-alpha add), recommend-only."""

    model_config = ConfigDict(frozen=True)

    hedge_type: HedgeType
    target: str                 # family / factor / regime / crisis-alpha id
    rationale: str
    expected_cagr_delta: float  # may be slightly negative if survival/tail justify it
    expected_survival_delta: float
    expected_tail_reduction: float


class HedgeEffectiveness(BaseModel):
    model_config = ConfigDict(frozen=True)

    hedge_effectiveness_score: float  # 0-100
    cagr_contribution: float
    survival_contribution: float
    diversification_contribution: float
    tail_risk_contribution: float
    capacity_impact: float


class HedgeGovernanceVerdict(BaseModel):
    model_config = ConfigDict(frozen=True)

    approved: bool
    reason: str


class Hedge(BaseModel):
    """An active hedge tracked by the lifecycle engine."""

    model_config = ConfigDict(frozen=True)

    hedge_id: str
    hedge_type: HedgeType
    target: str
    purpose: str
    opened_at: str = Field(default_factory=lambda: to_iso8601(utcnow()))


class HedgeLifecycleDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    close: bool
    reasons: list[str] = Field(default_factory=list)

```

### libs/validation/baselines.py
```python
"""Naive-baseline scorecard (philosophy from microsoft/qlib's benchmark harness).

The gauntlet (DSR, SPA, CPCV) asks "is this edge statistically distinguishable from noise, given the
search?". It does NOT ask the blunter question a qlib-style benchmark harness always asks first:
**does it even beat a trivial baseline?** A strategy can clear DSR and still lose to buy-and-hold or
to equal-weight — in which case it is complexity with no reason to exist. This scores a candidate's
per-period return stream against those trivial nulls so a "significant" result that fails to beat
buy-and-hold is caught before promotion, not after deployment.

Owned, ~1 file: prevents deploying DSR-significant-but-baseline-losing strategies. No dependency.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict

from libs.validation.errors import ValidationError


def _sharpe(returns: np.ndarray) -> float:
    r = np.asarray(returns, dtype="float64")
    if len(r) < 2:
        return 0.0
    sd = float(r.std(ddof=1))
    return float(r.mean() / sd) if sd > 0 else 0.0


class BaselineScorecard(BaseModel):
    """A candidate's edge over each trivial baseline. ``beats_all`` is the promotion pre-gate."""

    model_config = ConfigDict(frozen=True)

    strategy_sharpe: float
    buy_hold_sharpe: float
    equal_weight_sharpe: float
    excess_over_buy_hold: float  # strategy total return minus buy-and-hold total return
    excess_over_equal_weight: float
    beats_all: bool

    def __bool__(self) -> bool:
        return self.beats_all


def _total_return(returns: np.ndarray) -> float:
    return float(np.prod(1.0 + np.asarray(returns, dtype="float64")) - 1.0)


def baseline_scorecard(
    strategy_returns: np.ndarray,
    *,
    buy_hold_returns: np.ndarray,
    universe_returns: np.ndarray | None = None,
) -> BaselineScorecard:
    """Score ``strategy_returns`` against buy-and-hold and (optionally) an equal-weight universe.

    ``buy_hold_returns`` is the per-period return of holding the benchmark instrument (e.g. BTC).
    ``universe_returns`` is a 2-D array (periods x instruments) whose cross-sectional mean forms the
    equal-weight baseline; if omitted, the equal-weight baseline falls back to buy-and-hold. A
    candidate ``beats_all`` only if its Sharpe strictly exceeds every baseline's Sharpe.

    Raises:
        ValidationError: if the strategy and buy-and-hold streams differ in length.
    """
    strat = np.asarray(strategy_returns, dtype="float64")
    bh = np.asarray(buy_hold_returns, dtype="float64")
    if len(strat) != len(bh):
        raise ValidationError("strategy and buy_hold return streams must be the same length")
    if universe_returns is not None:
        ew = np.asarray(universe_returns, dtype="float64").mean(axis=1)
    else:
        ew = bh
    strat_sr, bh_sr, ew_sr = _sharpe(strat), _sharpe(bh), _sharpe(ew)
    return BaselineScorecard(
        strategy_sharpe=strat_sr,
        buy_hold_sharpe=bh_sr,
        equal_weight_sharpe=ew_sr,
        excess_over_buy_hold=_total_return(strat) - _total_return(bh),
        excess_over_equal_weight=_total_return(strat) - _total_return(ew),
        beats_all=strat_sr > bh_sr and strat_sr > ew_sr,
    )

```

### libs/validation/cpcv.py
```python
"""Combinatorial Purged Cross-Validation (CPCV) with purge + embargo.

Financial CV must drop training samples whose label windows overlap the test set (**purge**)
and a buffer immediately after it (**embargo**) — otherwise overlapping labels leak. CPCV
forms many train/test splits by choosing several test groups at once.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import comb

import numpy as np

from libs.validation.errors import ValidationError


@dataclass(frozen=True)
class CPCVSplit:
    train: np.ndarray
    test: np.ndarray


class CPCV:
    """Combinatorial purged cross-validation splitter."""

    def __init__(
        self,
        *,
        n_groups: int = 6,
        n_test_groups: int = 2,
        purge: int = 0,
        embargo: float = 0.0,
    ) -> None:
        if n_test_groups >= n_groups or n_test_groups < 1:
            raise ValidationError("require 1 <= n_test_groups < n_groups")
        if purge < 0 or embargo < 0:
            raise ValidationError("purge and embargo must be non-negative")
        self.n_groups = n_groups
        self.n_test_groups = n_test_groups
        self.purge = purge
        self.embargo = embargo

    def n_splits(self) -> int:
        return comb(self.n_groups, self.n_test_groups)

    @staticmethod
    def _contiguous_blocks(indices: np.ndarray) -> list[tuple[int, int]]:
        if len(indices) == 0:
            return []
        sorted_idx = np.sort(indices)
        blocks: list[tuple[int, int]] = []
        start = prev = int(sorted_idx[0])
        for value in sorted_idx[1:]:
            v = int(value)
            if v == prev + 1:
                prev = v
            else:
                blocks.append((start, prev))
                start = prev = v
        blocks.append((start, prev))
        return blocks

    def split(self, n_samples: int) -> list[CPCVSplit]:
        if n_samples < self.n_groups:
            raise ValidationError("n_samples must be >= n_groups")
        groups = np.array_split(np.arange(n_samples), self.n_groups)
        embargo_size = round(self.embargo * n_samples)
        splits: list[CPCVSplit] = []
        for test_ids in combinations(range(self.n_groups), self.n_test_groups):
            test = np.concatenate([groups[i] for i in test_ids])
            test_set = set(test.tolist())
            train_set = set(range(n_samples)) - test_set
            for a, b in self._contiguous_blocks(test):
                for i in range(a - self.purge, b + self.purge + 1):  # purge overlapping labels
                    train_set.discard(i)
                for i in range(b + 1, b + 1 + embargo_size):  # embargo after test
                    train_set.discard(i)
            train = np.array(sorted(train_set), dtype=int)
            splits.append(CPCVSplit(train=train, test=np.sort(test)))
        return splits

```

### scripts/audit_gate_power.py
```python
#!/usr/bin/env python3
"""STATISTICAL AUDIT OF THE VALIDATION GAUNTLET -- Type I and Type II, per gate and jointly.

THE QUESTION, asked without assuming the answer: is this gate stack over-conservative,
under-conservative, or near-optimal for maximising long-run compounded return? A gate stack is not
free. Every gate buys a reduction in false positives and pays for it in false negatives, and only
the desk's own objective -- E[log wealth] -- prices that trade. Nobody had measured either side.

METHOD. One cohort is simulated per replication, ``n_true`` of its candidates carrying a genuine
edge and the rest pure noise, then scored through the REAL ``validate()`` with the REAL campaign
statistics. Auditing the live function rather than a reimplementation is the whole point: a
reimplementation would certify a model of the gauntlet, not the gauntlet. Because
``campaign_gate_stats`` is computed once and shared across the cohort's candidates, one expensive
replication yields N verdicts -- which is what makes a Monte Carlo of this size affordable at all.

Every candidate's per-gate booleans AND its continuous statistics are recorded, so Type I error,
power, leave-one-out marginal contributions, ROC curves and calibration all come from the same
pass rather than from separate runs that could disagree.

WHAT IS DELIBERATELY NOT DONE: no threshold is tuned to raise the pass rate. The output is a
measurement. Where it recommends a change, the change must improve expected OUT-OF-SAMPLE
performance -- a higher pass rate on its own is a cost, not a benefit.

    python -u scripts/audit_gate_power.py --n 420 --t 310 --reps 20
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np  # noqa: E402

from libs.autodiscovery.models import Family, Hypothesis  # noqa: E402
from libs.autodiscovery.validation import (  # noqa: E402
    CampaignGates,
    campaign_gate_stats,
    validate,
)
from libs.validation.dsr import sharpe_ratio  # noqa: E402
from libs.validation.economic_prior import MechanismType  # noqa: E402
from libs.validation.positive_control import PPY  # noqa: E402
from libs.validation.stepwise import cscv_candidate_pbo, romano_wolf_stepdown  # noqa: E402

_OUT = Path("reports/gate_power_audit.json")
_HYP = Hypothesis(
    family=Family.LIQUIDITY, subtype="audit", symbol="BTCUSDT", params={},
    mechanism=MechanismType.LIQUIDITY, edge_source="simulated",
    failure_modes=["simulated -- never tradeable"],
)
#: Every gate validate() reports, in the order it reports them.
GATES = ("economic_mechanism", "expected_value", "cpcv", "walk_forward", "dsr", "pbo",
         "reality_check", "capacity", "fragility", "beats_baselines")
#: Annualised vol of a simulated candidate. Sets the scale only -- Sharpe is scale-free -- but a
#: realistic figure keeps the capacity gate's dollar arithmetic in a plausible range.
_ANN_VOL = 0.60


def simulate_returns(
    true_ann_sharpe: float,
    n_obs: int,
    rng: np.random.Generator,
    *,
    common: np.ndarray | None = None,
    rho: float = 0.0,
    ar1: float = 0.0,
    df: float | None = None,
    regime: str = "none",
) -> np.ndarray:
    """A candidate's return stream, with the departures from textbook iid-normal that actually
    change a gate's verdict.

    ``rho``    loading on a shared factor -- this is what makes a cohort's effective number of
               independent tests smaller than its candidate count, and multiplicity corrections
               price the RAW count.
    ``ar1``    serial correlation. Inflates a naive Sharpe's precision and is precisely what the
               purge/embargo in CPCV and the stationary-block bootstrap exist to handle, so a gate
               stack must be audited under it rather than only under white noise.
    ``df``     Student-t degrees of freedom for fat tails; None means Gaussian.
    ``regime`` "none", "decay" (edge halves in the second half), "reverse" (edge flips sign), or
               "late" (edge only appears in the final third). A real alpha is not stationary, and
               a gate stack that only admits stationary alphas rejects most true ones.
    """
    sd = _ANN_VOL / np.sqrt(PPY)
    z = rng.standard_normal(n_obs) if df is None else (
        rng.standard_t(df, n_obs) / np.sqrt(df / (df - 2.0)))
    if ar1:
        # AR(1) with unit-variance innovations scaled so the marginal variance stays 1.
        e = z * np.sqrt(1.0 - ar1**2)
        for i in range(1, n_obs):
            e[i] += ar1 * e[i - 1]
        z = e
    if common is not None and rho:
        z = np.sqrt(rho) * common + np.sqrt(max(0.0, 1.0 - rho)) * z
    # per-period Sharpe is mu/sd, so annualised (mu/sd)*sqrt(PPY) == true_ann_sharpe
    mu = true_ann_sharpe * sd / np.sqrt(PPY)
    drift = np.full(n_obs, mu)
    if regime == "decay":
        drift[n_obs // 2:] *= 0.5
    elif regime == "reverse":
        drift[n_obs // 2:] *= -1.0
    elif regime == "late":
        drift[: 2 * n_obs // 3] = 0.0
        drift[2 * n_obs // 3:] *= 3.0        # same total alpha, concentrated late
    return np.asarray(drift + sd * z)


def simulate_cohort(
    n: int, n_obs: int, rng: np.random.Generator, *, n_true: int, true_ann_sharpe: float,
    rho: float = 0.0, ar1: float = 0.0, df: float | None = None, regime: str = "none",
) -> tuple[np.ndarray, np.ndarray]:
    """Returns ``(matrix[T,N], is_true[N])``. The true alphas are placed FIRST but that is
    irrelevant to every gate here -- none of them reads column order."""
    common = rng.standard_normal(n_obs) if rho else None
    cols, flags = [], np.zeros(n, dtype=bool)
    for k in range(n):
        is_true = k < n_true
        flags[k] = is_true
        cols.append(simulate_returns(
            true_ann_sharpe if is_true else 0.0, n_obs, rng,
            common=common, rho=rho, ar1=ar1, df=df, regime=(regime if is_true else "none")))
    return np.column_stack(cols), flags


def effective_n_tests(matrix: np.ndarray) -> dict[str, float]:
    """How many INDEPENDENT tests the cohort really represents.

    Multiplicity corrections deflate by the number of trials, and every one of them here is handed
    the RAW candidate count. When candidates are correlated -- and 420 variants over one universe
    in one era are heavily correlated -- the raw count overstates the true multiplicity, so the
    deflation is too harsh by a factor that nobody has ever measured on this desk.

    Two standard estimators, reported together because they disagree in informative ways:
    ``kaiser`` counts eigenvalues above 1 (components carrying more than one variable's worth of
    variance) and ``participation`` is the participation ratio (sum L)^2 / sum L^2, which is
    smooth and does not depend on a cutoff.
    """
    m = np.asarray(matrix, dtype="float64")
    if m.shape[1] < 2:
        return {"n_raw": float(m.shape[1]), "kaiser": 1.0, "participation": 1.0, "li_ji": 1.0}
    c = np.corrcoef(m, rowvar=False)
    c = np.nan_to_num(c, nan=0.0)
    lam = np.linalg.eigvalsh(c)
    lam = np.clip(lam, 0.0, None)
    n_raw = float(m.shape[1])
    part = float(lam.sum() ** 2 / np.sum(lam**2)) if np.sum(lam**2) > 0 else n_raw
    kaiser = float(np.sum(lam > 1.0))
    # Li & Ji (2005): sum over eigenvalues of [I(L>=1) + (L - floor(L))]
    li_ji = float(np.sum((lam >= 1.0).astype(float) + (lam - np.floor(lam))))
    return {"n_raw": n_raw, "kaiser": kaiser, "participation": part, "li_ji": min(li_ji, n_raw)}


def campaign_stats_fast(matrix: np.ndarray) -> CampaignGates:
    """The per-candidate campaign statistics WITHOUT the legacy campaign constants.

    Pure cost control, and it changes no verdict -- which is asserted, not assumed, by
    ``test_fast_campaign_path_is_verdict_identical``. ``campaign_gate_stats`` also computes
    ``campaign_pbo_rc``, whose classic PBO enumerates C(16,8)=12,870 splits unvectorised and costs
    >100s at N=420 -- roughly 25x everything else in this audit combined. The per-candidate path
    reads ``cscv`` and ``stepdown`` only; ``legacy_pbo``/``legacy_rc`` are consumed exclusively by
    the legacy branch of validate(), which is selected by passing pbo=/rc= instead of campaign=.

    Skipping it turns a ~2-minute replication into a ~5-second one, which is the difference
    between a Monte Carlo with usable confidence intervals and a handful of anecdotes.
    """
    return CampaignGates(cscv=cscv_candidate_pbo(matrix),
                         stepdown=romano_wolf_stepdown(matrix),
                         legacy_pbo=None, legacy_rc=None)


def score_cohort(matrix: np.ndarray, flags: np.ndarray, *, n_trials: int | None = None,
                 per_candidate: bool = True, fast: bool = True) -> list[dict[str, Any]]:
    """Every candidate's per-gate verdict AND continuous statistics, from the REAL validate().

    Campaign statistics are computed once for the whole cohort and shared, which is both what the
    live campaign does and what makes the replication affordable.
    """
    gates = campaign_stats_fast(matrix) if (fast and per_candidate) \
        else campaign_gate_stats(matrix)
    if gates is None:
        raise RuntimeError("campaign_gate_stats returned None")
    sh = np.array([sharpe_ratio(matrix[:, i]) for i in range(matrix.shape[1])])
    n_tr = int(n_trials if n_trials is not None else matrix.shape[1])
    rows: list[dict[str, Any]] = []
    for k in range(matrix.shape[1]):
        kw: dict[str, Any] = {"campaign": gates, "column": k} if per_candidate else {
            "pbo": gates.legacy_pbo, "rc": gates.legacy_rc}
        v = validate(matrix[:, k], hypothesis=_HYP, n_trials=n_tr, sharpe_estimates=sh,
                     returns_matrix=matrix, **kw)
        rows.append({
            "is_true": bool(flags[k]),
            "survived": bool(v.survived),
            "gates": {g: bool(v.gates.get(g, True)) for g in GATES},
            "dsr": float(v.metrics.dsr),
            "pbo": float(v.metrics.pbo),
            "reality_p": float(v.metrics.reality_p),
            "oos_sharpe": float(v.metrics.oos_sharpe),
            "realised_ann_sharpe": float(sharpe_ratio(matrix[:, k]) * np.sqrt(PPY)),
        })
    return rows


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval -- correct at the 0 and 1 boundaries, where this audit lives and
    where the normal approximation gives a zero-width interval and a false sense of precision."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1.0 + z**2 / n
    c = (p + z**2 / (2 * n)) / d
    h = z * np.sqrt(max(0.0, p * (1 - p) / n + z**2 / (4 * n**2))) / d
    return (max(0.0, c - h), min(1.0, c + h))


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Type I, power, per-gate blocking rates, and the leave-one-out marginals."""
    nulls = [r for r in rows if not r["is_true"]]
    trues = [r for r in rows if r["is_true"]]

    def rate(sub: list[dict[str, Any]], key: str) -> dict[str, Any]:
        k = sum(1 for r in sub if r[key])
        lo, hi = _wilson(k, len(sub))
        return {"k": k, "n": len(sub), "rate": (k / len(sub)) if sub else None,
                "ci95": [lo, hi]}

    per_gate = {}
    for g in GATES:
        # A gate's Type I contribution is how often it PASSES a null (lets noise through); its
        # Type II contribution is how often it BLOCKS a true alpha.
        per_gate[g] = {
            "passes_null": rate([{**r, "_": r["gates"][g]} for r in nulls], "_"),
            "blocks_true": {**rate([{**r, "_": not r["gates"][g]} for r in trues], "_")},
        }

    # LEAVE-ONE-OUT: what the pipeline would do without each gate. This is the marginal
    # contribution question -- a gate that costs power without buying false-positive reduction is
    # pure loss, and only this comparison can show it.
    loo = {}
    for g in GATES:
        others = [x for x in GATES if x != g]
        fp = sum(1 for r in nulls if all(r["gates"][o] for o in others))
        tp = sum(1 for r in trues if all(r["gates"][o] for o in others))
        base_fp = sum(1 for r in nulls if r["survived"])
        base_tp = sum(1 for r in trues if r["survived"])
        loo[g] = {
            "fpr_without": (fp / len(nulls)) if nulls else None,
            "power_without": (tp / len(trues)) if trues else None,
            "delta_fpr": ((fp - base_fp) / len(nulls)) if nulls else None,
            "delta_power": ((tp - base_tp) / len(trues)) if trues else None,
        }

    # SUBSET POWER: leave-one-out cannot see REDUNDANCY. When two gates block the same candidates,
    # removing either alone changes nothing and both look free -- the classic masking result. The
    # only way to price a pair is to remove it as a pair, so the multiplicity corrections (which
    # all deflate for the SAME family of N candidates and are therefore the prime suspects for
    # double-counting) are scored jointly here as well as singly.
    def _subset(keep: tuple[str, ...]) -> dict[str, Any]:
        fp = sum(1 for r in nulls if all(r["gates"][g] for g in keep))
        tp = sum(1 for r in trues if all(r["gates"][g] for g in keep))
        lo_f, hi_f = _wilson(fp, len(nulls))
        lo_t, hi_t = _wilson(tp, len(trues))
        return {"kept": list(keep),
                "fpr": (fp / len(nulls)) if nulls else None, "fpr_ci95": [lo_f, hi_f],
                "power": (tp / len(trues)) if trues else None, "power_ci95": [lo_t, hi_t]}

    _MULT = ("dsr", "reality_check", "pbo")
    _ECON = tuple(g for g in GATES if g not in _MULT)
    subsets = {
        "all_gates": _subset(GATES),
        "without_dsr": _subset(tuple(g for g in GATES if g != "dsr")),
        "without_reality_check": _subset(tuple(g for g in GATES if g != "reality_check")),
        "without_dsr_and_reality_check": _subset(
            tuple(g for g in GATES if g not in ("dsr", "reality_check"))),
        "without_all_three_multiplicity": _subset(_ECON),
        "only_dsr": _subset(("dsr",)),
        "only_reality_check": _subset(("reality_check",)),
        "only_pbo": _subset(("pbo",)),
    }

    # SOLE BLOCKER: among true alphas the pipeline killed, which single gate did it alone? A gate
    # that is never the sole blocker is redundant; one that usually is, is the binding constraint.
    sole: dict[str, int] = {}
    for r in trues:
        failed = [g for g in GATES if not r["gates"][g]]
        if len(failed) == 1:
            sole[failed[0]] = sole.get(failed[0], 0) + 1
    return {
        "n_null": len(nulls), "n_true": len(trues),
        "type_i_joint": rate(nulls, "survived"),
        "power_joint": rate(trues, "survived"),
        "per_gate": per_gate,
        "leave_one_out": loo,
        "gate_subsets": subsets,
        "sole_blocker_of_true_alpha": dict(sorted(sole.items(), key=lambda x: -x[1])),
    }


def calibration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Are the corrections SIZED correctly? Under the null a p-value must be ~uniform and a
    posterior-style score like DSR must exceed 0.95 about 5% of the time. A correction that is
    far tighter than its nominal level is over-conservative BY CONSTRUCTION rather than by
    configuration, and no threshold change fixes that -- it is the wrong instrument."""
    nulls = [r for r in rows if not r["is_true"]]
    if not nulls:
        return {}
    dsr = np.array([r["dsr"] for r in nulls])
    rcp = np.array([r["reality_p"] for r in nulls])
    pbo = np.array([r["pbo"] for r in nulls])
    return {
        "dsr_nominal_fpr": 0.05,
        "dsr_realised_fpr": float(np.mean(dsr >= 0.95)),
        "dsr_quantiles": {q: float(np.quantile(dsr, q)) for q in (0.5, 0.9, 0.95, 0.99)},
        "reality_p_nominal_fpr": 0.05,
        "reality_p_realised_fpr": float(np.mean(rcp <= 0.05)),
        "reality_p_mean_should_be_0.5_if_uniform": float(np.mean(rcp)),
        "reality_p_quantiles": {q: float(np.quantile(rcp, q)) for q in (0.05, 0.1, 0.5, 0.9)},
        "pbo_realised_fpr_at_0.5": float(np.mean(pbo <= 0.5)),
        "pbo_mean": float(np.mean(pbo)),
    }


def roc(rows: list[dict[str, Any]], key: str, *, higher_is_better: bool) -> list[dict[str, float]]:
    """ROC for one continuous statistic, so a gate's DISCRIMINATION is separated from its
    THRESHOLD. A statistic with good AUC and a badly-placed threshold is a configuration problem;
    one with AUC ~0.5 is uninformative at every threshold and no re-tuning will save it."""
    nulls = np.array([r[key] for r in rows if not r["is_true"]])
    trues = np.array([r[key] for r in rows if r["is_true"]])
    if not len(nulls) or not len(trues):
        return []
    cuts = np.unique(np.concatenate([nulls, trues]))
    out = []
    for c in cuts:
        tpr = float(np.mean(trues >= c) if higher_is_better else np.mean(trues <= c))
        fpr = float(np.mean(nulls >= c) if higher_is_better else np.mean(nulls <= c))
        out.append({"cut": float(c), "tpr": tpr, "fpr": fpr})
    return out


def auc(rows: list[dict[str, Any]], key: str, *, higher_is_better: bool) -> float | None:
    """Mann-Whitney AUC: P(a true alpha scores better than a null one)."""
    nulls = np.array([r[key] for r in rows if not r["is_true"]])
    trues = np.array([r[key] for r in rows if r["is_true"]])
    if not len(nulls) or not len(trues):
        return None
    gt = float(np.mean(trues[:, None] > nulls[None, :]))
    eq = float(np.mean(trues[:, None] == nulls[None, :]))
    a = gt + 0.5 * eq
    return a if higher_is_better else 1.0 - a


def _merge(all_rows: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [r for rep in all_rows for r in rep]


def run_condition(*, n: int, n_obs: int, true_sr: float, n_true: int, reps: int, seed0: int,
                  rho: float = 0.0, ar1: float = 0.0, df: float | None = None,
                  regime: str = "none", n_trials: int | None = None,
                  per_candidate: bool = True, verbose: bool = True) -> dict[str, Any]:
    reps_rows, neff = [], []
    for i in range(reps):
        rng = np.random.default_rng(seed0 + 7919 * i)
        m, flags = simulate_cohort(n, n_obs, rng, n_true=n_true, true_ann_sharpe=true_sr,
                                   rho=rho, ar1=ar1, df=df, regime=regime)
        t0 = time.time()
        reps_rows.append(score_cohort(m, flags, n_trials=n_trials, per_candidate=per_candidate))
        neff.append(effective_n_tests(m))
        if verbose:
            print(f"    rep {i + 1}/{reps} [{time.time() - t0:5.1f}s]", flush=True)
    rows = _merge(reps_rows)
    s = summarise(rows)
    s["condition"] = {"n": n, "t": n_obs, "true_sr": true_sr, "n_true": n_true, "reps": reps,
                      "rho": rho, "ar1": ar1, "df": df, "regime": regime,
                      "n_trials": n_trials or n, "path": "per_candidate" if per_candidate
                      else "legacy"}
    s["effective_n_tests"] = {k: float(np.mean([d[k] for d in neff])) for k in neff[0]}
    # THE ESTIMATOR'S OWN FLOOR, measured on an INDEPENDENT cohort of the same shape. When T < N
    # the sample correlation matrix has rank <= T, so every eigenvalue-based N_eff is biased below
    # N even with zero true dependence: at N=420, T=310 the participation ratio reads ~179 on
    # perfectly independent columns. Reporting the raw figure alone would manufacture a finding
    # ("only 179 independent tests!") out of an estimation artifact. The interpretable quantity is
    # the RATIO of the measured value to this baseline.
    rng_b = np.random.default_rng(seed0 + 104729)
    base_m, _ = simulate_cohort(n, n_obs, rng_b, n_true=0, true_ann_sharpe=0.0, rho=0.0)
    s["effective_n_tests_independent_baseline"] = effective_n_tests(base_m)
    s["effective_n_tests_ratio_vs_baseline"] = {
        k: (s["effective_n_tests"][k] / v if v else None)
        for k, v in s["effective_n_tests_independent_baseline"].items()}
    s["calibration"] = calibration(rows)
    s["auc"] = {"dsr": auc(rows, "dsr", higher_is_better=True),
                "reality_p": auc(rows, "reality_p", higher_is_better=False),
                "pbo": auc(rows, "pbo", higher_is_better=False),
                "oos_sharpe": auc(rows, "oos_sharpe", higher_is_better=True)}
    return s


#: The campaign the desk's 0-of-420 record was measured on -- every study is anchored to it.
_BASE_N, _BASE_T = 420, 310
_N_TRUE = 20                        # ~5% of the cohort genuinely has an edge; a realistic prior


def _studies(reps: int, n_true: int) -> dict[str, list[dict[str, Any]]]:
    """Every condition this audit runs, as data.

    Each study isolates ONE candidate explanation for the desk's 0-survivor record, so the
    bottleneck question is answered by comparison rather than by argument: if lengthening the
    sample moves power and widening the cohort does not, the bottleneck is history, not campaign
    size -- and the reverse is equally decidable.
    """
    base = {"reps": reps, "n_true": n_true}
    return {
        # A. the power curve at the campaign's OWN shape -- the headline number
        "power_curve": [{**base, "n": _BASE_N, "n_obs": _BASE_T, "true_sr": sr}
                        for sr in (0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 7.0, 10.0)],
        # B. sample length, holding cohort size fixed
        "history_length": [{**base, "n": _BASE_N, "n_obs": t, "true_sr": 2.0}
                           for t in (310, 620, 1250, 2500)],
        # C. campaign size, holding history fixed
        "campaign_size": [{**base, "n": n, "n_obs": _BASE_T, "true_sr": 2.0,
                           "n_true": max(2, int(n * n_true / _BASE_N))}
                          for n in (30, 100, 420)],
        # D. correlation -- the effective-multiplicity question
        "correlation": [{**base, "n": _BASE_N, "n_obs": _BASE_T, "true_sr": 3.0, "rho": r}
                        for r in (0.0, 0.3, 0.6, 0.9)],
        # E. departures from iid-normal that a real alpha actually exhibits
        "realism": [
            {**base, "n": _BASE_N, "n_obs": _BASE_T, "true_sr": 3.0, "ar1": 0.2},
            {**base, "n": _BASE_N, "n_obs": _BASE_T, "true_sr": 3.0, "df": 4.0},
            {**base, "n": _BASE_N, "n_obs": _BASE_T, "true_sr": 3.0, "regime": "decay"},
            {**base, "n": _BASE_N, "n_obs": _BASE_T, "true_sr": 3.0, "regime": "reverse"},
            {**base, "n": _BASE_N, "n_obs": _BASE_T, "true_sr": 3.0, "regime": "late"},
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--study", default="power_curve",
                    help="power_curve|history_length|campaign_size|correlation|realism|all")
    ap.add_argument("--reps", type=int, default=12)
    ap.add_argument("--n-true", type=int, default=_N_TRUE)
    ap.add_argument("--seed0", type=int, default=90210)
    ap.add_argument("--out", default=str(_OUT))
    args = ap.parse_args()

    studies = _studies(args.reps, args.n_true)
    names = list(studies) if args.study == "all" else [args.study]
    out: dict[str, Any] = {"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                           "base_shape": {"n": _BASE_N, "t": _BASE_T}, "studies": {}}
    p = Path(args.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    for name in names:
        out["studies"][name] = []
        for spec in studies[name]:
            s = dict(spec)
            if s["true_sr"] <= 0:
                s["n_true"] = 0
            print(f"== {name}: {s} ==", flush=True)
            out["studies"][name].append(run_condition(seed0=args.seed0, **s))
            # CHECKPOINT per condition: a long sweep that dies at 90% must not discard the 90%.
            p.write_text(json.dumps(out, indent=2), "utf-8")
    print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts/check_promotion_gate.py
```python
#!/usr/bin/env python3
"""PROMOTION GATE (R0150) -- what evidence buys what expansion, fixed BEFORE the evidence exists.

PRINCIPAL (2026-07-31): *"if it works we will expand and advance this after a week, maxxing it."*

Right. And the honest moment to define "works" and "expand" is NOW, while nobody knows the answer.

WHY THIS IS THE SYMMETRIC HALF OF THE KILL CONDITION. R0142 pre-registered the exit: 50 trades,
under a 25% hit rate, graveyard, no extensions. The desk therefore had a defined way to DIE and no
defined way to GROW -- which is not caution, it is an asymmetry that makes expansion an improvised
decision taken in the mood of a good week. A week of wins creates pressure to scale immediately,
and scaling on 50 trades is how a lucky streak becomes a large loss.

THE TRAP THIS CLOSES, and it is the specific one a good week produces: 50 trades in seven days is
ONE MARKET REGIME. A sleeve that made money in a single trending week has evidence about trending
weeks and nothing else. So every rung requires CALENDAR TIME as well as sample size -- they are
different evidence and only one of them can be manufactured by raising the cadence.

THE LADDER. Each rung states its cost of being wrong, and no rung may be skipped:

  RUNG 0  PAPER, 6% floor cap                     -- where it is now
  RUNG 1  50 closed + 14 days + hit > breakeven   -> per-trade cap rises to measured half-Kelly
          + attribution clean                        (still PAPER; this is the R0145 mechanism)
  RUNG 2  100 closed + 30 days + beats buy-and-   -> LIVE at 1% of book. The first real money, at
          hold AND carry after costs + Brier<0.25    a size where being wrong is tuition
  RUNG 3  200 closed + 60 days + rung 2 held      -> LIVE at 5% of book
          + max drawdown inside the sleeve rail
  RUNG 4  400 closed + 120 days + two regimes     -> LIVE at 15% of book, the ceiling for one
          + independent of the carry sleeve          discretionary sleeve

WHY THE STEPS ARE SMALL AT THE BOTTOM. The first live rung is 1%, not 10%, because the transition
from paper to live is where unmodelled costs appear -- real slippage, real fills, real funding at
the moment it matters. A sleeve that survives paper and dies on execution should cost tuition, not
capital.

REFUSES TO SKIP. Meeting rung 3's trade count while failing rung 2's benchmark grants rung 1, not
rung 3. Evidence is a ladder, not a maximum.

UNMEASURED IS NEVER A PASS: a criterion that cannot be evaluated blocks the rung, because the
alternative is a promotion granted by a broken reader.

    python scripts/check_promotion_gate.py [--json]
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

_STATE = "data/promotion_gate.json"

#: ARITHMETIC cost-adjusted breakeven: the hit rate at which EXPECTED R is zero, from the measured
#: fee/slippage/funding stack in resolve_paper_book (3:1 structural payoff => 25.0% gross; costs
#: ~24% of one R at taker-in/taker-out => 31.1%). Kept because it is the number the kill floor and
#: the desk documents are stated against -- but it is NOT the promotion standard. See below.
BREAKEVEN_HIT = 0.311

#: THE PAYOFF, from resolve_paper_book's own derivation: a structural stop is one R and the
#: trail-and-pyramid plan pays ~3R on a runner, which is what makes 25.0% the GROSS breakeven.
#: Costs are charged on notional regardless of outcome, so they widen the loss and shave the win.
_R_WIN, _R_LOSS, _R_COST = 3.0, 1.0, 0.24


def log_breakeven(risk_fraction: float) -> float:
    """The hit rate at which E[log wealth] is zero -- the standard this desk actually maximises.

    WHY THE ARITHMETIC FIGURE IS THE WRONG GATE, and in the permissive direction. 31.1% is where
    expected R turns positive; it is NOT where the book starts compounding. Between the two lies
    variance drag: a sequence averaging a positive R can still shrink capital geometrically,
    because a loss removes a larger share of the base than the same-sized gain restores. Solving
    p*ln(1 + w*f) + (1-p)*ln(1 - l*f) = 0 puts the real threshold at 33.6% at the 6% floor cap,
    rising to 36.1% at the 12% ceiling -- the drag GROWS with size, so the sleeve's own promotions
    raise the bar it must clear.

    What it was costing: a sleeve measured at 32% cleared `hit_rate_above_breakeven`, took rung 1's
    cap increase and then rung 2's real money, while compounding the book DOWNWARD the whole way --
    a gate certifying growth that was not there. Every desk rule here (fractional Kelly, the heat
    budget, survival-first sizing) is written against E[log wealth]; this criterion was the one
    place measuring expected value instead, which is why the gap went unseen.

    Derived, not chosen: the threshold is solved from the same measured payoff and cost stack the
    resolver marks against, and moves when they move.
    """
    f = max(1e-6, min(0.99 / (_R_LOSS + _R_COST), float(risk_fraction)))
    win, loss = math.log(1 + (_R_WIN - _R_COST) * f), math.log(1 - (_R_LOSS + _R_COST) * f)
    # p*win + (1-p)*loss = 0  =>  p = -loss / (win - loss)
    return -loss / (win - loss)

#: THE LADDER. (rung, closed trades, calendar days, extra criteria, what it grants).
#: Calendar days are NOT redundant with trade count: 50 trades in a week is ONE regime, and
#: cadence can manufacture sample size but never time.
_RUNGS: tuple[dict[str, Any], ...] = (
    {"rung": 1, "trades": 50, "days": 14,
     "needs": ("hit_rate_above_breakeven", "attribution_clean"),
     "grants": "per-trade cap rises from the 6% floor to measured half-Kelly (still PAPER)"},
    {"rung": 2, "trades": 100, "days": 30,
     "needs": ("hit_rate_above_breakeven", "attribution_clean", "beats_buy_and_hold",
               "calibration_informative"),
     "grants": "LIVE at 1% of book -- the first real money, at a size where being wrong is tuition"},
    {"rung": 3, "trades": 200, "days": 60,
     "needs": ("hit_rate_above_breakeven", "attribution_clean", "beats_buy_and_hold",
               "calibration_informative", "drawdown_inside_rail"),
     "grants": "LIVE at 5% of book"},
    {"rung": 4, "trades": 400, "days": 120,
     "needs": ("hit_rate_above_breakeven", "attribution_clean", "beats_buy_and_hold",
               "calibration_informative", "drawdown_inside_rail", "two_regimes",
               "independent_of_carry"),
     "grants": "LIVE at 15% of book -- the ceiling for one discretionary sleeve"},
)


def _criteria(root: Path) -> dict[str, dict[str, Any]]:
    """Evaluate every criterion the ladder can ask about. UNMEASURED is never True."""
    out: dict[str, dict[str, Any]] = {}

    def put(k: str, ok: bool | None, why: str) -> None:
        out[k] = {"ok": bool(ok) if ok is not None else None,
                  "state": "UNMEASURED" if ok is None else ("PASS" if ok else "FAIL"), "why": why}

    try:
        pnl = json.loads((root / "data/paper_book_pnl.json").read_text("utf-8"))
    except (OSError, ValueError) as exc:
        pnl = {}
        put("hit_rate_above_breakeven", None, f"paper book unmarked ({type(exc).__name__})")
        put("beats_buy_and_hold", None, "paper book unmarked")
        put("drawdown_inside_rail", None, "paper book unmarked")
    if pnl:
        n = int(pnl.get("n_resolved") or 0)
        hit = pnl.get("win_rate")
        # The bar is set at the risk fraction ACTUALLY IN FORCE, because variance drag grows with
        # size: promoting the cap raises the hit rate required to keep compounding. Median of the
        # closed marks, so one outsized trade cannot set the standard; the 6% floor if unmeasured.
        sized = sorted(float((m.get("sizing") or {}).get("risk_fraction") or 0.0)
                       for m in (pnl.get("marks") or []) if m.get("closed"))
        sized = [f for f in sized if f > 0.0]
        f_used = sized[len(sized) // 2] if sized else 0.06
        bar = log_breakeven(f_used)
        put("hit_rate_above_breakeven",
            None if hit is None or n < 20 else float(hit) > bar,
            f"{hit} vs {bar:.1%} LOG-breakeven at {f_used:.1%} risk over {n} closed "
            f"(arithmetic breakeven {BREAKEVEN_HIT:.1%} is not the standard -- a positive expected "
            f"R still shrinks the book between the two)"
            if hit is not None else "no closed trades")
        bh = pnl.get("beats_buy_and_hold")
        put("beats_buy_and_hold", None if bh is None else bool(bh),
            f"sleeve {pnl.get('sleeve_return')} vs buy-and-hold {pnl.get('buy_and_hold_return')}")
        eq = pnl.get("equity") or {}
        mdd = eq.get("max_drawdown")
        put("drawdown_inside_rail", None if mdd is None else float(mdd) < 0.35,
            f"max drawdown {mdd} vs the 35% sleeve rail")

    try:
        att = json.loads((root / "data/mechanism_attribution.json").read_text("utf-8"))
        put("attribution_clean", att.get("status") == "ATTRIBUTED",
            f"attribution status {att.get('status')}")
    except (OSError, ValueError) as exc:
        put("attribution_clean", None, f"attribution unreadable ({type(exc).__name__})")

    try:
        probe = json.loads((root / "data/calibration_probe.json").read_text("utf-8"))
        v = (probe.get("verdict") or {}).get("state")
        put("calibration_informative", None if v in (None, "ACCUMULATING", "UNMEASURED")
            else v == "INFORMATIVE", f"calibration verdict {v}")
    except (OSError, ValueError) as exc:
        put("calibration_informative", None, f"probe unreadable ({type(exc).__name__})")

    try:
        alloc = json.loads((root / "data/sleeve_allocation.json").read_text("utf-8"))
        st = alloc.get("status")
        put("independent_of_carry", None if st in (None, "UNMEASURED") else st == "DIVERSIFIED",
            f"sleeve allocation status {st}")
    except (OSError, ValueError) as exc:
        put("independent_of_carry", None, f"allocation unreadable ({type(exc).__name__})")

    # TWO REGIMES -- now MEASURED rather than permanently blocking. Every trade is already tagged
    # with the volatility regime at entry (run_conviction_trader.setup_features), so "did this
    # record span more than one tape" is answerable from the marks. A criterion that can never be
    # satisfied is not a standard, it is a wall, and a wall that nobody can climb gets removed
    # rather than met -- which is how a ladder quietly loses its top rung.
    regimes = {(m.get("setup") or {}).get("vol_regime") for m in (pnl.get("marks") or [])
               if m.get("closed") and (m.get("setup") or {}).get("vol_regime")}
    regimes.discard("UNKNOWN")
    regimes.discard(None)
    put("two_regimes", None if not regimes else len(regimes) >= 2,
        f"closed trades span {sorted(regimes)}" if regimes else
        "no regime tags on any closed trade yet -- UNMEASURED, not satisfied")
    return out


def evaluate(root: Path | None = None, *, now: datetime | None = None) -> dict[str, Any]:
    root = root or _ROOT
    now = now or datetime.now(tz=UTC)
    crit = _criteria(root)
    try:
        pnl = json.loads((root / "data/paper_book_pnl.json").read_text("utf-8"))
        n_closed = int(pnl.get("n_resolved") or 0)
        marks = [m.get("exit_at") for m in pnl.get("marks", []) if m.get("exit_at")]
        days = ((now - datetime.fromisoformat(min(marks))).days if marks else 0)
    except (OSError, ValueError, KeyError):
        n_closed, days = 0, 0

    granted, blocked_at = 0, None
    rows = []
    for r in _RUNGS:
        fails = [c for c in r["needs"] if not (crit.get(c, {}).get("ok"))]
        ok = n_closed >= r["trades"] and days >= r["days"] and not fails
        rows.append({"rung": r["rung"], "grants": r["grants"],
                     "trades": f"{n_closed}/{r['trades']}", "days": f"{days}/{r['days']}",
                     "unmet": ([f"trades {n_closed}/{r['trades']}"] if n_closed < r["trades"] else [])
                              + ([f"calendar days {days}/{r['days']}"] if days < r["days"] else [])
                              + fails,
                     "met": ok})
        # NO SKIPPING: the ladder stops at the first unmet rung, whatever later counts say.
        if ok and blocked_at is None:
            granted = r["rung"]
        elif blocked_at is None:
            blocked_at = r["rung"]

    return {
        "generated": now.isoformat(),
        "law": "L1.6 -- promotion is bought with evidence, on a ladder fixed BEFORE the evidence "
               "existed. A week of wins is one regime, and cadence can manufacture sample size "
               "but never calendar time.",
        "granted_rung": granted,
        "granted": ("PAPER at the 6% floor cap" if granted == 0
                    else _RUNGS[granted - 1]["grants"]),
        "blocked_at_rung": blocked_at,
        "n_closed": n_closed, "days_of_record": days,
        "criteria": crit,
        "ladder": rows,
        "no_skipping": "meeting a later rung's trade count while failing an earlier rung's "
                       "benchmark grants the EARLIER rung. Evidence is a ladder, not a maximum.",
        "detail": (f"rung {granted} granted ({rows[granted]['unmet'][:1] if granted < len(rows) else []}"
                   f" blocks rung {blocked_at})" if blocked_at else f"rung {granted} granted"),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = evaluate(_ROOT)
    out = _ROOT / _STATE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"promotion gate (L1.6): rung {rep['granted_rung']} -- {rep['granted']}")
        for row in rep["ladder"]:
            if not row["met"]:
                print(f"  rung {row['rung']} blocked by: {', '.join(map(str, row['unmet'][:4]))}")
                break
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/check_utilisation.py
```python
"""UTILISATION FENCE (L1.28a) -- every ceiling this desk owns, measured against its limit.

THE LAW: unused headroom is not safety, it is an unbooked loss. Capital, forward-confirmation
slots, model quota, data already paid for, built capability, scheduler cadence -- each is utilised
to its limit at all times, and idle headroom anywhere is a defect of the same class as a missed
edge.

WHY IDLENESS IS THE MOST EXPENSIVE FAILURE AVAILABLE, and why it needs a fence rather than an
intention: a wrong trade costs a bounded amount and announces itself. Idle capacity costs its
ENTIRE forward output stream and announces nothing. An unfilled forward slot is evidence that will
never be accrued. An unread dataset is a hypothesis never tested. A dormant module is engineering
already paid for returning zero forever. An idle dollar is compounding that never starts. None of
it appears in any P&L, and none of it generates an error -- which is exactly why it persists.

THE RULE THIS ENFORCES: every ceiling declares a LIMIT, carries a MEASURED utilisation, and where
utilisation is short of the limit, names the BINDING CONSTRAINT with a resolution path. Two design
choices follow from the law and both are deliberate:

  * UNMEASURED COUNTS AS ZERO. A ceiling nobody measures is idle by default and nobody would know.
    Treating "no measurement" as "probably fine" is how every one of these gaps survived.
  * A BINDING CONSTRAINT MUST BE NAMED, not implied. "Running at 60% and that seems fine" is a
    defect; "60%, bound by an unfunded OpenRouter key, re-test on funding" is a decision. The
    difference is whether anyone can act on it.

THE ONLY LEGITIMATE IDLE HEADROOM is a survival rail (L1.23 -- drawdown buffer, ruin margin,
Tier-3 reserve) or a named external blocker on the register with a re-test date.

    python scripts/check_utilisation.py [--json] [--report-only]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_OUT = _ROOT / "data/utilisation.json"
_LOGS = _ROOT / "data/cro_ai_logs"

#: Below this fraction of the limit, idle headroom must be explained by a named binding constraint.
_EXPECT = 0.90


@dataclass
class Ceiling:
    name: str
    limit: float
    used: float
    unit: str
    measured: bool
    binding_constraint: str      # "" = none named; required when utilisation < _EXPECT
    why_it_matters: str

    @property
    def utilisation(self) -> float:
        if not self.measured:
            return 0.0           # unmeasured counts as zero -- see module docstring
        return 0.0 if self.limit <= 0 else min(self.used / self.limit, 1.0)

    @property
    def status(self) -> str:
        if not self.measured:
            return "UNMEASURED"
        # OVER-LIMIT IS A MEASUREMENT DEFECT, NOT SATURATION, and clamping it to 100% is how it
        # hides. First run of this fence read deployed capital at $13,155 against $4,500 equity
        # and displayed a comfortable "SATURATED 100%". Either the two numbers come from different
        # sources, or the book is levered and the ceiling is wrong. Both need a human, and neither
        # is the healthy state the clamp implied. A ceiling you cannot trust is worse than one you
        # know is idle: it reports success while measuring nothing.
        if self.limit > 0 and self.used > self.limit * 1.02:
            return "OVER-LIMIT"
        if self.utilisation >= _EXPECT:
            return "SATURATED"
        return "IDLE-EXPLAINED" if self.binding_constraint else "IDLE-UNEXPLAINED"


def _forward_slots() -> Ceiling:
    """The single most load-bearing ceiling on the desk's only path from research to capital."""
    try:
        from libs.research.slot_registry import MAX_FORWARD_SLOTS, derive_slots
        snap = derive_slots()
        used, cap = float(len(snap.get("slots", []) or [])), float(MAX_FORWARD_SLOTS)
        measured = True
    except (ImportError, OSError, ValueError, KeyError):
        used, cap, measured = 0.0, 12.0, False
    return Ceiling(
        "forward_confirmation_slots", cap, float(used), "concurrent clocks", measured,
        "" if used >= cap * _EXPECT else
        "candidate supply into the forward queue -- see scripts/run_promotion_queue.py",
        "An empty slot accrues NO evidence while every candidate's capacity decays against a "
        "growing book. Idle slots are the direct mechanism by which an edge arrives already "
        "outgrown (L1.18a runway).")


def _capital() -> Ceiling:
    try:
        from libs.autodiscovery.validation import _desk_equity_usd
        from libs.research.capacity_policy import live_book_usd
        book, eq = float(live_book_usd()), float(_desk_equity_usd())
        measured = eq > 0
    except (ImportError, OSError, ValueError, AttributeError):
        book, eq, measured = 0.0, 0.0, False
    return Ceiling(
        "deployed_capital", eq, book, "USD", measured,
        "" if (measured and eq > 0 and book >= eq * _EXPECT) else
        "live connector not funded (EXECUTION_QUEUE gap #2) -- named external blocker",
        "An idle dollar is compounding that never starts. Under-deployment is a REAL cost "
        "reported as loudly as a risk breach (L1.20, doctrine).")


def _organs() -> Ceiling:
    """Scheduler saturation: manifest entries that actually produced a log in the last 48h."""
    if not _LOGS.exists():
        return Ceiling("scheduler_cadence", 1.0, 0.0, "organs fresh", False,
                       "log directory absent", "A scheduled organ that never runs is a cadence "
                       "declared and not kept -- the capability is paid for and returns zero.")
    manifest = _ROOT / "ops/crontab.manifest"
    scripts = set()
    if manifest.exists():
        for line in manifest.read_text("utf-8").splitlines():
            if line.strip().startswith("#") or "python" not in line:
                continue
            for tok in line.split():
                if tok.endswith(".py"):
                    scripts.add(Path(tok).stem)
    cutoff = (datetime.now(tz=UTC) - timedelta(hours=48)).timestamp()
    fresh = {p.stem.split("_20")[0] for p in _LOGS.glob("*.log") if p.stat().st_mtime >= cutoff}
    hit = sum(1 for s in scripts if any(s in f or f in s for f in fresh))
    return Ceiling(
        "scheduler_cadence", float(len(scripts)), float(hit), "organs run in 48h",
        bool(scripts),
        "" if scripts and hit >= len(scripts) * _EXPECT else
        "organs silent in 48h -- check_organs/check_stale_daemons name which; a fresh container "
        "shows zero because no cron has fired yet",
        "A scheduled organ that never runs is a cadence declared and not kept -- capability "
        "already paid for, returning zero.")


def _capability() -> Ceiling:
    """Built code that nothing imports and nothing schedules: engineering paid for, unused."""
    try:
        from libs.self_improvement.dormancy import scan
        rep = scan()
        total = float(rep.n_scripts_scanned + getattr(rep, "n_modules_scanned", 0))
        dormant = float(len(rep.dormant))
        measured = total > 0
    except (ImportError, OSError, ValueError, AttributeError, TypeError):
        total, dormant, measured = 0.0, 0.0, False
    return Ceiling(
        "capability_wired", total, max(total - dormant, 0.0), "reachable units", measured,
        "" if measured and total > 0 and (total - dormant) >= total * _EXPECT else
        "wiring backlog -- scripts/run_wiring_agent.py --apply auto-wires the provably-inert "
        "ones daily; the remainder are money-path/spend-capable and need a human cadence call",
        "A dormant capability is engineering already paid for that returns zero forever, and it "
        "compounds: nobody maintains it, so it rots into a liability (L2.9).")


def _data_assets() -> Ceiling:
    """Datasets acquired vs datasets actually READ by something. Paid-for and unread is the
    purest form of the defect: the cost is already sunk and the return is exactly zero."""
    reg = _ROOT / "data/data_assets.json"
    try:
        rows = json.loads(reg.read_text("utf-8"))
        rows = rows.get("assets", rows) if isinstance(rows, dict) else rows
        # PRESENT assets only. An asset absent from this box is a COLLECTION question ("is the
        # collector scheduled, is this even the collecting box"), not an idle-capacity one --
        # scoring the two together would blame the desk for not reading a file it never had, and
        # the number would stop meaning anything actionable.
        present = [r for r in rows if (r.get("rows") or r.get("bytes") or r.get("span"))]
        total = float(len(present))
        # THE COLLECTOR IS NOT A CONSUMER. Counting it read 97.8% -- a comfortable number meaning
        # "almost every dataset is used" -- when many of those sole "consumers" were the very
        # script that WRITES the file. A dataset read only by its own collector is precisely the
        # idle asset L1.28a is about: paid for, collected on a cadence, and feeding no research.
        used = float(sum(1 for r in present
                         if [c for c in (r.get("consumers") or [])
                             if Path(str(c)).name != Path(str(r.get("collector") or "")).name]))
        measured = total > 0
    except (OSError, ValueError, AttributeError, TypeError):
        total, used, measured = 0.0, 0.0, False
    return Ceiling(
        "data_assets_read", total, used, "present datasets with a consumer", measured,
        "" if measured and total > 0 and used >= total * _EXPECT else
        "assets present on this box with no consumer -- run scripts/build_data_registry.py and "
        "read the `consumers` column; an absent asset is a collection gap, not an idle one",
        "An unread dataset is a hypothesis never tested against evidence already bought. The "
        "26-year CFTC COT panel sat unread for weeks -- that is the proving instance (L1.3).")


def _mutation() -> Ceiling:
    """Test STRENGTH, not coverage: the fraction of injected faults the suite actually kills."""
    f = _ROOT / "data/mutation_score.json"
    try:
        d = json.loads(f.read_text("utf-8"))
        # The artifact is PER-TARGET (run_mutation.py writes a `targets` list), so a top-level
        # `kill_rate` lookup silently returned 0.0 and this ceiling read UNMEASURED while a real
        # measurement sat in the file. The aggregate is mutants-weighted, not a mean of rates:
        # a 10-mutant file at 100% must not cancel a 200-mutant file at 80%.
        targets = d.get("targets") or []
        killed = float(sum(float(t.get("killed", 0)) for t in targets))
        total = float(sum(float(t.get("total", 0)) for t in targets))
        score = killed / total if total > 0 else float(d.get("kill_rate", 0.0))
        score = score / 100.0 if score > 1.0 else score
        measured = score > 0
    except (OSError, ValueError, TypeError, AttributeError):
        score, measured = 0.0, False
    return Ceiling(
        "test_kill_rate", 1.0, score, "mutants killed (fraction)", measured,
        "" if score >= _EXPECT else
        "surviving mutants in libs/execution/staging.py and libs/risk/gate.py -- the survivor "
        "list IS the work queue (L1.0c)",
        "An unkilled mutant is a real code change the suite cannot see. On the money path that "
        "is a silent correctness ceiling under every other guarantee.")


def _test_suites_runnable() -> Ceiling:
    """Test modules that can actually EXECUTE here, vs modules that skip on a missing dependency.

    A `pytest.importorskip` skip prints one grey line and exits 0, so a suite covering the
    backtest cross-engine, GARCH stationarity, or any other optional-dep path reads as GREEN while
    testing nothing. Measured 2026-07-30: arch, backtrader and vectorbt are all DECLARED in
    pyproject and all absent, so five test modules have been silently inert.

    That is L1.28a exactly -- capability paid for (the tests are written, the deps are chosen) and
    returning zero, with no error to notice. Unmeasured counts as zero, so it belongs on this
    board rather than in a skip line nobody reads.
    """
    import importlib.util
    declared = ("arch", "backtrader", "vectorbt")
    have = [m for m in declared if importlib.util.find_spec(m) is not None]
    return Ceiling(
        "optional_test_deps", float(len(declared)), float(len(have)), "declared deps importable",
        True,
        "" if len(have) >= len(declared) * _EXPECT else
        f"missing {sorted(set(declared) - set(have))} -- their test modules skip silently and "
        "read as green; `pip install -e '.[research]'` on the box that runs CI",
        "A test that skips on a missing dependency prints one grey line and exits 0. The suite "
        "reports green while those paths are untested -- the same 'could not measure counted as "
        "satisfied' failure the Gate 0 board refuses.")


def _brain_seat() -> Ceiling:
    """THE SEAT: how much of the day the desk's ONE serial brain is actually working.

    THE UNMEASURED CEILING (found 2026-07-31 answering "is anything still below max
    frequency"): every claude-invoking organ takes /tmp/quant_brain.lock, and every LOSER
    appends a DEFERRED line to brain_mutex.log -- a complete, free record of contention that
    NOTHING had ever read. So the desk raised and lowered LLM cadences for weeks with no
    measurement of the resource they all compete for: the exact "we are running at 60% and
    that seems fine" defect L1.28a exists to kill, sitting on the desk's scarcest input.

    THE METRIC, and why it is deferrals rather than wall-clock: a deferral is a run the desk
    WANTED and did not get, which is precisely the thing extra cadence is supposed to buy. Two
    readings, both actionable:
      deferral rate LOW  -> the seat has idle windows: RAISE cadences (headroom exists).
      deferral rate HIGH -> the seat is the binding constraint: raising cron changes nothing;
                            only a second seat (the research twin) or shorter runs do.
    Utilisation is reported as attempts-that-ran / attempts-made over the trailing 24h, so
    100% means nothing was ever turned away and lower means real contention. UNMEASURED (no
    log yet, e.g. this container) counts as ZERO by law -- never as healthy."""
    log = _LOGS / "brain_mutex.log"
    since = datetime.now(tz=UTC) - timedelta(hours=24)
    deferred = 0
    try:
        for line in log.read_text("utf-8", errors="ignore").splitlines():
            stamp = line.split(" ", 1)[0]
            try:
                if datetime.fromisoformat(stamp.replace("Z", "+00:00")) >= since:
                    deferred += 1
            except ValueError:
                continue
        measured = True
    except OSError:
        measured = False
    # Attempts = organ fires that reached the mutex. Runs = attempts - deferrals. The daily
    # scheduled claude-organ fire count is the denominator's floor; deferrals add the rest.
    scheduled_fires = 34.0                                  # claude-invoking cron lines/day
    attempts = scheduled_fires + deferred
    ran = attempts - deferred
    return Ceiling(
        "brain_seat_throughput", attempts if measured else scheduled_fires,
        ran if measured else 0.0, "organ runs/24h (vs attempted)", measured,
        "" if (measured and deferred == 0) else
        ("ONE serial brain seat: every deferred organ is a run the desk wanted and did not "
         "get. The resolution path is a SECOND SEAT (research twin, ops/role=research) -- "
         "raising cron cadence cannot add throughput to a saturated mutex"
         if measured else
         "brain_mutex.log absent on this host -- measurable only where organs actually run"),
        "This is the resource EVERY llm cadence competes for. Unmeasured, the desk cannot tell "
        "'raise the cadence' (headroom) from 'buy a second seat' (contention) -- and it has "
        "been raising cadences blind. Deferrals are the only honest signal of which is true.")


def collect() -> list[Ceiling]:
    return [_capital(), _forward_slots(), _capability(), _data_assets(), _organs(), _mutation(),
            _test_suites_runnable(), _brain_seat()]


def build() -> dict[str, Any]:
    ceilings = collect()
    rows = [{**asdict(c), "utilisation": round(c.utilisation, 3), "status": c.status}
            for c in ceilings]
    unexplained = [r["name"] for r in rows if r["status"] == "IDLE-UNEXPLAINED"]
    unmeasured = [r["name"] for r in rows if r["status"] == "UNMEASURED"]
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.28a -- unused headroom is not safety, it is an unbooked loss. Unmeasured "
               "utilisation counts as ZERO: a ceiling nobody measures is idle by default.",
        "expect_fraction": _EXPECT,
        "mean_utilisation": round(sum(c.utilisation for c in ceilings) / max(len(ceilings), 1), 3),
        "idle_unexplained": unexplained, "unmeasured": unmeasured, "ceilings": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()
    rep = build()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"utilisation (L1.28a): mean {rep['mean_utilisation']:.0%} across "
              f"{len(rep['ceilings'])} ceilings")
        for r in rep["ceilings"]:
            bar = f"{r['used']:,.0f}/{r['limit']:,.0f} {r['unit']}"
            print(f"  {r['status']:17} {r['name']:26} {r['utilisation']:6.1%}  {bar}")
            if r["binding_constraint"]:
                print(f"  {'':17} └─ bound by: {r['binding_constraint'][:100]}")
        print(f"-> {_OUT.relative_to(_ROOT)}")
    return 0 if (args.report_only or not rep["idle_unexplained"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts/claim_verifier.py
```python
"""CLAIM VERIFIER -- does every number the desk PUBLISHES survive contact with its own source?

THREE MEASURED FAILURES ON 2026-07-27, all the same shape: a dashboard confidently reported a
state that was not true, and nothing cross-checked it.
  health.json     said all_ok: true          while every AI organ had been dead 4+ days
  portfolio.json  said equity $14,853        while the venue reported $5,262 (175% divergence)
  axis_shadows    said cny "ACCRUING 1/40"   while it had 0 usable z-values (evidence not started)

None of these were crashes. Each was a CONFIDENT WRONG CLAIM, and a claim is what you act on.
The NAV gap was found by accident while checking an unrelated false positive -- nothing was
looking for it. This looks for it.

METHOD: for each published claim, read the SOURCE independently and compare. Never trust a
summary artifact to describe itself; a self-report cannot detect its own divergence.

PRIORITISED BY CAPITAL CONSEQUENCE, not by ease: a wrong NAV corrupts every sizing, leverage and
risk decision downstream, so it is checked first and hardest.

Read-only, no LLM, no keys. Run from repo root, daily.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
WEB = ROOT / "web"
OUT = DATA / "claim_verification.json"


def load(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except Exception:
        return None


def jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    out = []
    for ln in p.read_text("utf-8", errors="ignore").splitlines():
        if ln.strip():
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if not r.get("_summary"):
                out.append(r)
    return out


def check(findings, sev, claim, claimed, actual, consequence):
    ok = sev == "OK"
    findings.append({"severity": sev, "claim": claim, "claimed": str(claimed)[:90],
                     "actual": str(actual)[:90], "consequence": consequence})
    tag = "OK      " if ok else sev
    print(f"  [{tag}] {claim}")
    if not ok:
        print(f"             claims : {claimed}")
        print(f"             source : {actual}")
        print(f"             -> {consequence}")


def main() -> None:
    print("=== CLAIM VERIFIER -- every published number, traced to its source ===")
    print("    a self-report cannot detect its own divergence. 3 dashboards lied today.\n")
    f: list[dict] = []

    # ---- 1. NAV SCOPE -- corrected 2026-07-27 -------------------------------------------
    # ORIGINAL CHECK WAS WRONG and escalated a false CRITICAL. It compared venue_nav against
    # portfolio equity as if they measured the same thing. They never did:
    #   venue_equity.json  = "fut margin + tracked spot legs + USDT delta" (FUTURES scope, ~$5k;
    #                        venue 5,169 / start_futures 5,000 = 1.03x)
    #   portfolio.equity   = the whole book (TOTAL scope, ~$14.4k / start 15,000 = 0.96x)
    # So the "175% divergence" was a UNIT ERROR of mine, not a lost $9k. No money is missing.
    #
    # THE REAL DEFECT IS DOWNSTREAM: run_venue_divergence_shadow.py logs pct_diff between these
    # two scopes, and its stated purpose is calibrating the GAP #19 circuit breaker at "~2x
    # OBSERVED noise". A breaker calibrated on a 175% phantom gap either never fires or always
    # fires. Its own docstring says the 07-22 dead-man false fires happened "because a trigger was
    # set without knowing the measurement noise of its own inputs" -- this is that same failure,
    # one level up. So the check now verifies SCOPE COMPARABILITY, which is the thing that matters.
    port = load(WEB / "portfolio.json") or {}
    equity = (port.get("deployed") or {}).get("equity")
    ven = load(WEB / "venue_equity.json") or {}
    vneq = ven.get("equity")
    att = jsonl(DATA / "nav_attestation.jsonl")
    fut_start = att[-1].get("start_futures_equity") if att else None
    if equity and vneq and fut_start:
        vratio = vneq / fut_start                      # ~1.0 => venue tracks the futures scope
        pratio = equity / (port.get("deployed") or {}).get("start_capital", 1)
        scope_mismatch = abs(equity - vneq) / max(vneq, 1e-9) > 0.5 and 0.5 < vratio < 2.0
        sev = "HIGH" if scope_mismatch else "OK"
        check(f, sev, "venue and book NAV are compared on the SAME scope",
              f"venue ${vneq:,.0f} (={vratio:.2f}x futures start) vs "
              f"book ${equity:,.0f} (={pratio:.2f}x total start)",
              "venue=FUTURES scope, portfolio=TOTAL scope -- not comparable"
              if scope_mismatch else "scopes comparable",
              "run_venue_divergence_shadow logs pct_diff between these and that series is what "
              "calibrates the GAP #19 breaker; calibrating on a scope mismatch produces a breaker "
              "that never fires or always fires. Fix the shadow to compare like-for-like BEFORE "
              "arming anything from it.")

    # ---- 2. HEALTH: does all_ok survive the organ logs? --------------------------------
    health = load(WEB / "health.json") or {}
    logs = DATA / "cro_ai_logs"
    stubs = fresh = 0
    if logs.exists():
        for lg in sorted(logs.glob("*.log"))[-40:]:
            sz = lg.stat().st_size
            age_h = (datetime.now(tz=UTC).timestamp() - lg.stat().st_mtime) / 3600
            if age_h < 48:
                if sz < 600:
                    stubs += 1
                else:
                    fresh += 1
    claimed_ok = health.get("all_ok")
    organs_ok = health.get("organs_ok")
    sev = "HIGH" if (claimed_ok and stubs > fresh and stubs > 0) else "OK"
    check(f, sev, "health all_ok is consistent with organ logs",
          f"all_ok={claimed_ok}, organs_ok={organs_ok}",
          f"{stubs} stub logs vs {fresh} real logs in last 48h",
          "a green dashboard while organs are dead means silent research outage")

    # ---- 3. CLOCK PROGRESS: are 'accruing' days actually usable? -----------------------
    sh = load(WEB / "axis_shadows.json") or {}
    for ax in sh.get("axes", []):
        name = ax.get("axis", "?")
        fwd = ax.get("forward_days", 0)
        fn = {"kimchi_premium": "kimchi_premium.jsonl",
              "stablecoin_supply_momentum": "stablecoin_supply.jsonl",
              "cny_premium": "cny_premium.jsonl"}.get(name)
        if not fn:
            continue
        rows = jsonl(DATA / fn)
        usable = sum(1 for r in rows if r.get("z20") is not None)
        sev = "HIGH" if (fwd > 0 and usable == 0) else ("MEDIUM" if usable < fwd else "OK")
        check(f, sev, f"{name}: reported forward days are usable",
              f"forward_days={fwd}", f"{usable}/{len(rows)} rows have a usable z20",
              "an axis reported as accruing evidence that has not started will read as "
              "'failing' later for the wrong reason, and its Holm slot is wasted meanwhile")

    # ---- 4. DEPLOYMENT: does claimed notional match the positions? ---------------------
    cc = load(WEB / "cashcarry_live.json") or {}
    n, dep = cc.get("n_carries"), cc.get("deployed_notional")
    carries = cc.get("carries") or []
    if n is not None:
        sev = "HIGH" if n != len(carries) else "OK"
        check(f, sev, "carry count matches the position list",
              f"n_carries={n}, notional=${dep:,.0f}" if dep else f"n_carries={n}",
              f"{len(carries)} positions listed",
              "a mismatch means the executor and the dashboard disagree about the book")

    # ---- 5. FRESHNESS: does 'updated' match the file's own mtime? ----------------------
    for name in ("portfolio.json", "health.json", "axis_shadows.json"):
        p = WEB / name
        d = load(p)
        if not d or "updated" not in d:
            continue
        try:
            claimed_t = datetime.fromisoformat(str(d["updated"]).replace("Z", "+00:00"))
        except ValueError:
            continue
        mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=UTC)
        drift_h = abs((mtime - claimed_t).total_seconds()) / 3600
        age_h = (datetime.now(tz=UTC) - claimed_t).total_seconds() / 3600
        sev = "HIGH" if age_h > 24 else ("MEDIUM" if drift_h > 2 else "OK")
        check(f, sev, f"{name} freshness claim is true",
              f"updated {claimed_t:%Y-%m-%d %H:%M}", f"age {age_h:.1f}h, mtime drift {drift_h:.1f}h",
              "a stale artifact presented as current is read as live state")

    bad = [x for x in f if x["severity"] != "OK"]
    sev_counts: dict[str, int] = {}
    for x in bad:
        sev_counts[x["severity"]] = sev_counts.get(x["severity"], 0) + 1
    print(f"\n  {len(f)} claims checked | {len(bad)} FAILED"
          + (f"  ({', '.join(f'{k}:{v}' for k, v in sorted(sev_counts.items()))})" if bad else ""))
    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "checked": len(f), "failed": len(bad),
                               "by_severity": sev_counts, "claims": f}, indent=1), "utf-8")
    print(f"  -> {OUT}")
    print("  CRITICAL here should block Gate-0: the desk does not know what it owns.")


if __name__ == "__main__":
    main()

```

### scripts/collect_tail_funding_divergence.py
```python
#!/usr/bin/env python3
"""Cross-venue funding divergence on the thin tail of the perp universe (§42 hunting ground).

    python3 scripts/collect_tail_funding_divergence.py

Reads public funding + open-interest endpoints on Binance and Bybit, keeps the THIN half of the
shared universe by open interest, and logs every harvestable cross-venue funding gap to
`data/tail_funding_divergence.jsonl`. Starting the clock is the whole job: a divergence that shows
up once is noise, and only a panel accumulated over weeks can say whether these gaps PERSIST long
enough to be worth two venues of operational overhead.

WHY THE TAIL. §42: the liquid names are where every funded arbitrageur already looks, so a gap
there is gone before a small book reaches it. A thin perp listed on two venues can carry a
persistent gap for days because nobody with real capital will build plumbing for a $30k position.
That is the one place a book this size is not the worst-capitalised participant in the trade.

Read-only public endpoints, no keys, no orders, no capital. Freeze-safe. Degrades to an honest
"could not read venue X" and exit 0 rather than failing the daily cycle -- a collector that breaks
the cycle when one exchange has a bad minute is worse than a collector that skips a day.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_OUT = ROOT / "data/tail_funding_divergence.jsonl"
_TIMEOUT = 20


def _get(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": "quant-tail-funding"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        return json.loads(r.read().decode())


def _binance() -> list[object]:
    """Funding + mark from premiumIndex, open interest from the 24h ticker (quoteVolume proxy)."""
    from libs.research.tail_funding import VenueQuote
    prem = _get("https://fapi.binance.com/fapi/v1/premiumIndex")
    tick = _get("https://fapi.binance.com/fapi/v1/ticker/24hr")
    vol = {str(t["symbol"]): float(t.get("quoteVolume", 0) or 0)
           for t in tick if isinstance(t, dict)}
    out = []
    for p in prem if isinstance(prem, list) else []:
        sym = str(p.get("symbol", ""))
        if not sym.endswith("USDT"):
            continue
        out.append(VenueQuote(symbol=sym, venue="binance",
                              funding_rate=float(p.get("lastFundingRate", 0) or 0),
                              open_interest_usd=vol.get(sym, 0.0)))
    return out


def _bybit() -> list[object]:
    from libs.research.tail_funding import VenueQuote
    data = _get("https://api.bybit.com/v5/market/tickers?category=linear")
    rows = (data or {}).get("result", {}).get("list", []) if isinstance(data, dict) else []
    out = []
    for r in rows:
        sym = str(r.get("symbol", ""))
        if not sym.endswith("USDT"):
            continue
        out.append(VenueQuote(symbol=sym, venue="bybit",
                              funding_rate=float(r.get("fundingRate", 0) or 0),
                              open_interest_usd=float(r.get("turnover24h", 0) or 0)))
    return out


def main() -> int:
    from libs.research.tail_funding import divergences

    quotes: list[object] = []
    reached: list[str] = []
    for name, fn in (("binance", _binance), ("bybit", _bybit)):
        try:
            got = fn()
        except Exception as exc:
            print(f"[tail-funding] {name} unreachable ({type(exc).__name__}) -- skipping")
            continue
        quotes.extend(got)
        reached.append(name)
        print(f"[tail-funding] {name}: {len(got)} USDT perps")

    if len(reached) < 2:
        print("[tail-funding] need TWO venues for a spread -- nothing to compare, not a failure")
        return 0

    divs = divergences(quotes)  # type: ignore[arg-type]
    credible = [d for d in divs if d.credible]
    now = datetime.now(tz=UTC).isoformat()
    with _OUT.open("a", encoding="utf-8") as fh:
        for d in divs:
            fh.write(json.dumps({"ts": now, "venues": reached, **d.model_dump()}) + "\n")

    print(f"[tail-funding] {len(divs)} gap(s) over the bar, {len(credible)} credible")
    for d in credible[:5]:
        print(f"  {d.symbol:<14} {d.spread_annual:>7.1%} annual  long {d.long_venue} / "
              f"short {d.short_venue}  thin-leg OI ${d.min_oi_usd:,.0f}")
    for d in (x for x in divs if not x.credible):
        print(f"  [FLAGGED] {d.symbol}: {d.note[:90]}")
    print(f"[tail-funding] appended to {_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts/daily_research_cycle.py
```python
"""Daily institutional research cycle -- the CRO everyday loop.

ONE complete cycle, run daily by Task Scheduler:
  1. run_daily_research.py   -- forward-accumulating pipeline: candidate generation + validation +
                                data archiving (feeds the research system for testing)
  2. research_cycle.py       -- regenerate the 3 state files, ROI reprioritization, calibration
  3. run_leverage_opt.py     -- recompute growth-optimal leverage per sleeve + joint
  4. run_live_combined.py    -- refresh the molded book
Then it appends a DATED entry to data/cro_cycle_log.json (bottleneck, next highest-ROI task,
deployed metrics, calibration, candidates tested) and prints the next action. Continuous process:
no terminal state except the absence of positive expected-Research-ROI work.

Each step is isolated -- one failure never aborts the cycle. Idempotent + safe to re-run.

    python scripts/daily_research_cycle.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from libs.ops.platform_paths import venv_python

_ROOT = Path(__file__).resolve().parent.parent
_PY = venv_python(_ROOT)
_LOG = _ROOT / "data" / "cro_cycle_log.json"

# ordered pipeline; (label, script, timeout_s). Heavy research first, then bookkeeping.
_STEPS = [
    # 1200s: the whole-tree gate (2026-07-25) runs ~8min; the old 300s was sized for the 4-file
    # gate and silently killed this step by timeout every run since (R0146, stale-consumer class).
    ("ci_gate",           "scripts/run_ci.py",             1200),
    ("recorder_watch",    "scripts/ensure_recorder.py",      60),  # data moat must never sleep
    ("stablecoin_flows",  "scripts/run_stablecoin_flows.py", 180),  # daily on-chain clock tick
    ("fred_macro",        "scripts/collect_fred_macro.py",   120),  # free US-macro (key-gated)
    ("walcl_clock",       "scripts/derive_walcl_clock.py",    60),  # R0031 forward clock, reads
    #                      the fred archive the previous step just refreshed (phase = cadence)
    ("naver_krsearch",    "scripts/collect_naver_krsearch.py", 60),  # KR attention (key-gated)
    ("root_cause",        "scripts/run_root_cause.py",       120),  # classify losses pre-reaction
    ("desk_digest",       "scripts/render_desk_digest.py",    60),  # Obsidian-readable daily brief
    ("micro_audit",       "scripts/run_micro_audit.py",      480),  # 3 cold LLMs on 24h delta
    ("cadence",           "scripts/run_cadence.py",          900),  # stage-aware review scheduler
    ("research_feed",     "scripts/collect_research_feed.py", 120),  # arXiv q-fin -> vault inbox
    ("growth_audit",      "scripts/run_growth_audit.py",       60),  # under-utilization = defect
    ("research_pipeline", "scripts/run_daily_research.py",  7200),
    ("autodiscovery",     "scripts/run_crypto_research.py", 1800),  # industrialized crypto factory
    # the research-coordination engines: rank the agenda queue, screen novelty against the
    # do-not-repeat list, assess crowding/capacity, and flag candidates that duplicate a
    # deployed sleeve. 17 of 21 alpha_factory modules had no caller before this.
    ("alpha_factory",     "scripts/run_alpha_factory.py",   180),
    ("state_files",       "scripts/research_cycle.py",      300),
    ("trade_forensics",   "scripts/run_trade_forensics.py",  60),  # class-bleed probe (daily)
    ("nav_attest",        "scripts/run_nav_attest.py",       60),  # hash-chained track record
    # gap-2 §3-§6: the ONE production caller for the S1 rails (naked-position reconcile, pager
    # de-risk ladder, 6h canary, numeric ramp gate, stage machine). Inert at S0/without keys --
    # but it must run daily from S0 so the rails are exercised BEFORE they are load-bearing,
    # rather than executing for the first time on the day real money is behind them.
    ("live_guard",        "scripts/run_live_guard.py",       120),
    ("listing_watch",     "scripts/run_listing_watch.py",    60),  # gap-53 data clock
    # §42(6): the CONSUMER for that clock. Collection without a promotion path is acquisition the
    # desk can never convert, so the study runs on the same cadence as the collector rather than
    # waiting for someone to remember it exists.
    ("event_study",       "scripts/run_event_study.py",     300),
    # §42: cross-venue funding on the THIN tail -- where a small book is not the worst-capitalised
    # participant. The liquid names are already screened; this starts the clock on the other end.
    ("tail_funding",      "scripts/collect_tail_funding_divergence.py", 120),
    ("kimchi_premium",    "scripts/collect_kimchi_premium.py", 90),  # gap-74 forward clock
    ("onchain_activity",  "scripts/collect_onchain_activity.py", 120),
    # licence-clean Glassnode/Coin-Metrics replacement (facts reconstructed from chain)
    ("onchain_metrics",   "scripts/collect_onchain_metrics.py", 180),  # on-chain throughput
    ("stablecoin_supply", "scripts/collect_stablecoin_supply.py", 120),  # supply momentum clock
    ("breadth_expander", "scripts/breadth_expander.py", 420),  # external-LLM breadth scout (Stage-A only)
    ("signal_halflife",  "scripts/signal_halflife.py", 180),  # signal ageing/decay tracker
    ("measurement_gate",  "scripts/measurement_gate.py", 120),  # inputs must be verified before any optimisation
    ("exec_bottleneck",   "scripts/execution_bottleneck.py", 60),  # live book vs live gate
    ("collector_monitor","scripts/collector_monitor.py", 90),  # G3 zero-trust sensor kill-switch
    ("stage_a_exec",       "scripts/stage_a_executor.py", 120),  # RUN the ranked queue, not order it
    ("defi_axis",          "scripts/build_defi_axis.py", 60),  # pool rows -> daily z20 axis feed
    ("conversion",        "scripts/conversion_engine.py", 90),  # mined data -> ranked experiments, every cycle
    ("enforce_proof",     "scripts/prove_future.py", 90),  # adversarial: guards must FAIL on planted violations
    ("principle_audit",   "scripts/principle_audit.py", 30),  # STRICT: all 15 principles must reach models
    ("blindspot_max",     "scripts/blindspot_max.py", 120),  # 4 classes of mechanical unknown-unknown
    ("doctrine_guard",      "scripts/doctrine.py", 30),  # STRICT: fails if any LLM caller runs without doctrine
    ("unobserved",          "scripts/unobserved.py", 90),  # unknown-unknowns we already own and never read
    ("module_justify",      "scripts/module_justification.py", 120),  # would I build this today -- merit audit of existing code
    ("coverage_audit",      "scripts/coverage_audit.py", 60),  # one honest coverage number per surface
    ("knowledge_engine",   "scripts/knowledge_engine.py", 90),  # memory + causal graph + genome + revival
    ("dependency_graph",   "scripts/dependency_graph.py", 60),  # impact analysis: what is poisoned now
    ("data_vitals",         "scripts/data_vitals.py", 90),  # live collector DQS + provenance
    ("alpha_lifecycle",     "scripts/alpha_lifecycle.py", 90),  # failure patterns + transfer pipeline + novelty + anomalies
    ("research_cio",        "scripts/research_cio.py", 90),  # info advantage + blind spots + north star + scheduler
    ("hedge_integrity",     "scripts/hedge_integrity.py", 60),  # venue-truth hedge invariant
    ("feature_library",     "scripts/feature_library.py", 90),  # feature assets + construction coverage
    ("leakage_detector",    "scripts/leakage_detector.py", 60),  # self-validating leakage contract
    ("experiment_registry", "scripts/experiment_registry.py", 90),  # harvest experiments -> permanent objects
    ("desk_brief",          "scripts/research_exchange.py brief", 60),  # daily research board / external-LLM brief
    # --- installed 2026-07-29 (closure cycle). Every one of these is an organ that would
    # otherwise be built-but-idle, which L2.9 counts as a defect. Cheap, read-only, no risk path.
    ("ratchets",            "scripts/check_ratchets.py --ratchet", 60),  # L1.0: every metric toward 100%, floors only rise
    ("execution_intel",     "scripts/run_execution_intel.py", 60),  # cross-feed cost-DRIFT (recommend-only)
    ("reality_gap",         "scripts/run_reality_gap.py", 60),  # L2.10: backtest->shadow->live->venue-truth
    ("miner_runway",        "scripts/check_miner_runway.py --report-only", 60),  # why a seat never produced
    ("scheduler_manifest",  "scripts/check_scheduler_manifest.py --report-only", 60),  # DR floor + live drift
    ("mypy_ratchet",        "scripts/check_mypy_ratchet.py --report-only", 900),  # type backlog is a ceiling
    ("contributor_score",   "scripts/research_exchange.py score", 60),  # which intelligence source earns allocation
    ("claim_verifier",    "scripts/claim_verifier.py", 90),  # verify every published claim vs source
    ("claim_escalate",    "scripts/claim_escalate.py", 60),  # escalate false claims to pager + Gate-0
    ("data_sanity",       "scripts/data_sanity.py", 120),  # implausibility scan (2 artifacts today)
    ("hurdle_rate",       "scripts/hurdle_rate.py", 90),  # is the desk beating T-bills/BTC?
    ("negative_knowledge", "scripts/negative_knowledge.py", 60),  # revival triggers on dead ideas
    ("research_autopsy",  "scripts/research_autopsy.py", 60),  # failure-mode taxonomy + lessons
    ("research_erv",      "scripts/research_erv.py", 60),  # rank hypotheses before spending slots
    ("mechanism_board",   "scripts/mechanism_board.py", 60),  # mechanism kills + portfolio + gate
    ("screen_auditor",    "scripts/screen_auditor.py", 60),  # missing-rail audit on screens
    ("cny_premium",       "scripts/collect_cny_premium.py", 60),  # USDT/CNY P2P premium (#76)
    ("axis_shadows",      "scripts/run_axis_shadows.py",     120),  # Stage-B forward eval
    ("reject_rescore",    "scripts/run_rejection_rescore.py", 300),  # feed near-miss reject scores
    ("rejection_shadow",  "scripts/run_rejection_shadow.py",  60),  # gate-leak recovery audit
    ("cost_model",        "scripts/run_cost_model.py",      600),  # measured exec costs (daily)
    ("shadow_8h",         "scripts/run_shadow_8h.py",       420),  # 3x-obs challenger shadow
    ("leverage_opt",      "scripts/run_leverage_opt.py",    120),
    ("molded_refresh",    "scripts/run_live_combined.py",   120),
    # the self-improvement queue: derive review dates so decisions can MATURE, and publish
    # the matured-and-unscored worklist. Never writes an outcome -- scoring is a judgement.
    ("decision_review",   "scripts/run_decision_review.py",  60),
    # what the DESK costs, vs what a trade costs -- the hurdle it must clear to stand still
    ("desk_economics",    "scripts/run_desk_economics.py",   30),
    ("git_snapshot",      "scripts/git_snapshot.py",        120),  # daily forensic code history
]


def _run(script: str, timeout: int) -> dict[str, object]:
    try:
        r = subprocess.run([_PY, script], cwd=str(_ROOT), timeout=timeout,
                           capture_output=True, text=True, check=False)
        tail = (r.stdout or r.stderr or "").strip().splitlines()[-1:] or [""]
        return {"ok": r.returncode == 0, "rc": r.returncode, "tail": tail[0][:160]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "rc": "timeout", "tail": f"timeout after {timeout}s"}
    except Exception as e:
        return {"ok": False, "rc": "error", "tail": repr(e)[:160]}


def _load(p: Path, d: object) -> object:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return d


def main() -> None:
    steps: dict[str, object] = {}
    for label, script, timeout in _STEPS:
        steps[label] = _run(script, timeout)
        print(f"[{label}] {steps[label]}")

    # read resulting institutional state for the dated cycle log
    eng = _load(_ROOT / "engineering_backlog.json", {})
    state = _load(_ROOT / "research_state.json", {})
    port = _load(_ROOT / "web" / "portfolio.json", {}).get("deployed", {})
    cal = _load(_ROOT / "web" / "calibration.json", {})
    disc = _load(_ROOT / "web" / "discovery.json", {})
    nxt = eng.get("next_action")

    entry = {
        "date": datetime.now(tz=UTC).strftime("%Y-%m-%d"),
        "ts": datetime.now(tz=UTC).isoformat(),
        "steps_ok": {k: v.get("ok") for k, v in steps.items()},
        "binding_constraint": state.get("binding_constraint"),
        "next_highest_roi_task": ({"id": nxt.get("id"), "roi": nxt.get("roi")} if nxt else None),
        "open_backlog": [i.get("id") for i in eng.get("open", [])],
        "deployed": {k: port.get(k) for k in ("equity", "net_pnl", "days_live", "deployed_sharpe")},
        "calibration": {k: cal.get(k) for k in ("n_resolved", "brier", "bias_label")},
        "data_clocks": [p.get("status") for p in disc.get("pending", [])],
    }
    log = _load(_LOG, [])
    if not isinstance(log, list):
        log = []
    log.append(entry)
    _LOG.write_text(json.dumps(log[-400:], indent=2), "utf-8")

    print(f"CRO cycle {entry['date']}: next-ROI={entry['next_highest_roi_task']} "
          f"| constraint={entry['binding_constraint']}")
    if nxt is None:
        print("  no positive-ROI engineering task -> research capital = WAIT on data clocks "
              "+ scope next orthogonal free-data stream (see research_agenda.json).")


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/hurdle_rate.py
```python
"""HURDLE RATE -- the benchmark the desk has never had.

THE GAP: nothing in this desk has ever asked "is this better than doing nothing?". Today's own
data answered it accidentally and badly: the 8,026-trader cohort averaged -1.14% while BTC was
-0.15%, i.e. active leveraged trading UNDERPERFORMED holding. The desk itself is -4% on total
capital over 25 days. Neither number was ever compared to an alternative, so neither could be
judged.

A strategy is not "working" because it is positive. It is working when it beats what you could
have had for free, net of everything. Three benchmarks, hardest first:

  1. RISK-FREE   -- US 3-month T-bill (^IRX). Capital has a price; ignoring it flatters everything.
  2. BUY-AND-HOLD BTC -- the zero-effort crypto alternative.
  3. 50/50 BTC+cash   -- the honest risk-matched comparison for a market-neutral book, since a
                        delta-neutral carry should NOT be compared to full BTC beta.

Also computes the CARRY-SPECIFIC hurdle: funding harvested must exceed fee drag, or the sleeve is
structurally unprofitable regardless of direction.

Free (Yahoo + Binance + the desk's own state). Read-only. Run from repo root, daily.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/hurdle_rate.json"


def _get(u, t=35):
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=t).read().decode())


def load(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except Exception:
        return None


def main() -> None:
    port = (load(ROOT / "web/portfolio.json") or {}).get("deployed") or {}
    cc = load(ROOT / "web/cashcarry_live.json") or {}
    days = float(port.get("days_live") or 0)
    ret = float(port.get("return_pct") or 0) / 100.0
    if days <= 0:
        print("no live history yet")
        return

    # --- benchmarks over the SAME window ---------------------------------------------------
    try:
        irx = _get("https://query1.finance.yahoo.com/v8/finance/chart/%5EIRX"
                   "?interval=1d&range=1mo")["chart"]["result"][0]
        rf_annual = float([c for c in irx["indicators"]["quote"][0]["close"] if c][-1]) / 100.0
    except Exception:
        rf_annual = 0.045
    rf = rf_annual * (days / 365.0)

    try:
        kl = _get("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=400")
        n = min(int(days) + 1, len(kl))
        btc = float(kl[-1][4]) / float(kl[-n][1]) - 1.0
    except Exception:
        btc = float("nan")
    half = btc / 2 + rf / 2

    ann = (1 + ret) ** (365 / days) - 1 if days > 0 else 0.0
    print("=== HURDLE RATE -- is this better than doing nothing? ===")
    print(f"    window: {days:.1f} days live\n")
    print(f"  {'DESK':<26} {ret*100:+8.2f}%   ({ann*100:+.1f}%/yr annualised)")
    print(f"  {'risk-free (T-bill)':<26} {rf*100:+8.2f}%   ({rf_annual*100:.2f}%/yr)")
    print(f"  {'buy-and-hold BTC':<26} {btc*100:+8.2f}%")
    print(f"  {'50/50 BTC + cash':<26} {half*100:+8.2f}%   <- risk-matched for a neutral book")

    beats = {"risk_free": ret > rf, "btc_hold": ret > btc, "half_btc": ret > half}
    print()
    for k, v in beats.items():
        print(f"  beats {k:<12} {'YES' if v else 'NO'}   "
              f"(excess {(ret - {'risk_free': rf, 'btc_hold': btc, 'half_btc': half}[k])*100:+.2f}%)")

    # --- carry-specific hurdle: does funding actually exceed fee drag? ----------------------
    fund = float(cc.get("funding_harvested") or 0)
    net = float(cc.get("net_pnl") or 0)
    legs = float(cc.get("spot_leg_pnl") or 0) + float(cc.get("perp_leg_pnl") or 0)
    costs = fund + legs - net          # residual = what neither funding nor legs explain
    print("\n  === CARRY DECOMPOSITION (the structural question) ===")
    print(f"    funding harvested  {fund:+10.2f}")
    print(f"    legs (spot+perp)   {legs:+10.2f}   <- ~0 confirms delta-neutrality holds")
    print(f"    net P&L            {net:+10.2f}")
    print(f"    implied costs      {costs:+10.2f}   <- residual")
    if fund > 0:
        ratio = abs(costs) / fund
        print(f"    cost / funding     {ratio:8.2f}x   "
              f"{'STRUCTURALLY UNPROFITABLE -- costs exceed the harvest' if ratio > 1 else 'harvest covers costs'}")

    verdict = ("PASSES" if all(beats.values()) else
               "FAILS -- does not beat " + ", ".join(k for k, v in beats.items() if not v))
    print(f"\n  HURDLE VERDICT: {verdict}")
    print("  A strategy is not 'working' because it is positive. It works when it beats what you")
    print("  could have had for free, net of everything. Nothing should get capital until it does.")

    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "days": days, "desk_return": ret, "annualised": ann,
                               "risk_free": rf, "btc_hold": btc, "half_btc": half,
                               "beats": beats, "funding": fund, "legs": legs,
                               "implied_costs": costs, "verdict": verdict}, indent=1), "utf-8")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()

```

### scripts/info_class_map.py
```python
"""INFORMATION CLASS MAP (L5 modality-blind mandate, principal 2026-07-27).

The branch registry tracks MECHANISMS. This tracks the orthogonal axis: MODALITY x ACCESS -- the
KINDS of information carrier the desk can mine. "Raw information is information no matter how it
was mined": text, audio, video, transcript, image, code, tabular, graph, stream, filing, archive.
Format never determines value; only testable-signal-per-source does.

Purpose: make "expand classes not yet searched" MEASURABLE. Every class carries a status; the
never-visited ones are the concrete target list that the NEW_BRANCHES budget slice funds. A class
is retired only to `low-yield-archived` (never deleted -- L1 monotonic), and archived classes are
re-surfaced by the quarterly blind re-derivation.

LEGITIMACY GATE (DIGGING_CHARTER s13, unchanged and non-negotiable): public + legitimately
accessible only. Public forums/groups/videos/transcripts/filings = YES. Paywalled, pirated,
cracked, private-group, or paid-DB-mirrored content = NO, regardless of expected value.

Read-only report. Run from repo root.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

OUT = Path("data/information_class_map.json")

# class -> (modality, status, note)
#   covered      = actively mined today
#   partial      = touched but not systematically mined
#   never-visited= concrete expansion target (funded by NEW_BRANCHES)
#   blocked      = legitimacy gate or hard access wall (kept visible, never silently dropped)
CLASSES = {
    # --- structured / numeric (the desk's comfort zone) -----------------------------------
    "exchange_api_ohlcv":        ("tabular", "covered", "recorders + klines, multi-venue"),
    "derivatives_metrics":       ("tabular", "covered", "funding/OI/liquidations/vol surface"),
    "onchain_rpc":               ("tabular", "covered", "stablecoin flows, reserves, throughput"),
    "macro_series":              ("tabular", "covered", "FRED/SOMA/RRP/TGA net liquidity"),
    "orderbook_l2":              ("stream", "covered", "recorded L2 -> measured cost model"),
    # --- code / developer ------------------------------------------------------------------
    "source_repositories":       ("code", "covered", "prospector; commit/contributor tested 07-27"),
    "package_registries":        ("tabular", "never-visited", "npm/PyPI/crates download curves = adoption proxy"),
    "smart_contract_bytecode":   ("code", "never-visited", "deployment/verification rate, upgrade cadence"),
    # --- text ------------------------------------------------------------------------------
    "academic_papers":           ("text", "covered", "arXiv/SSRN feed -> litminer"),
    "regional_forums":           ("text", "partial", "CN/KR/JP/RU charter-mandated; not systematically parsed"),
    "protocol_governance":       ("text", "never-visited", "Snapshot/Tally proposals, delegate behaviour"),
    "regulatory_filings":        ("filing", "never-visited", "SEC/CFTC/FCA/MAS/FSA actions + licences"),
    "public_company_reports":    ("filing", "never-visited", "Virtu/Flow Traders 10-Ks = real execution economics"),
    "protocol_documentation":    ("text", "never-visited", "docs/roadmap diffs via archive snapshots"),
    # --- audio / video / transcript (explicitly named by the principal) ---------------------
    "video_transcripts":         ("transcript", "never-visited", "public conference/earnings/AMA talks; auto-caption"),
    "podcast_transcripts":       ("transcript", "never-visited", "public feeds; entity + commitment extraction"),
    "livestream_chat":           ("stream", "never-visited", "public stream chat = retail attention proxy"),
    "conference_talks":          ("video", "never-visited", "devcon/ETHGlobal schedules = roadmap leading indicator"),
    # --- social / group --------------------------------------------------------------------
    "public_group_messages":     ("text", "never-visited", "PUBLIC Telegram/Discord only (s13 gate)"),
    "social_graph_structure":    ("graph", "never-visited", "who-follows-whom topology, not sentiment"),
    "search_interest":           ("tabular", "covered", "Wikipedia pageviews tested; multilingual attention DEAD at all horizons"),
    # --- network / graph -------------------------------------------------------------------
    "wallet_transaction_graph":  ("graph", "partial", "addresses read; clustering/identity not built"),
    "bridge_flow_graph":         ("graph", "blocked", "DefiLlama bridges API now 402 paid"),
    "validator_topology":        ("graph", "never-visited", "stake concentration, client diversity, geography"),
    # --- infrastructure telemetry ----------------------------------------------------------
    "mempool_state":             ("stream", "partial", "size/fees tested SCREEN-WEAK; pending-tx stream unbuilt"),
    "rpc_node_health":           ("stream", "never-visited", "latency/failure as stress proxy"),
    "oracle_update_timing":      ("stream", "never-visited", "update cadence deviation = stress signal"),
    # --- archives --------------------------------------------------------------------------
    "web_archive_diffs":         ("archive", "never-visited", "Wayback diffs on docs/terms/roadmaps"),
    "historical_dumps":          ("archive", "partial", "binance.vision used for OI/LS backfill"),
    "prediction_markets":        ("tabular", "partial", "libs/data/prediction_markets.py exists, unmined"),
}

MODALITY_NOTE = ("format never determines value -- a transcript and a candle are both raw "
                 "information; only testable-signal-per-source ranks them")


def main() -> None:
    by_status, by_mod = {}, {}
    for name, (mod, status, note) in CLASSES.items():
        by_status.setdefault(status, []).append((name, mod, note))
        by_mod.setdefault(mod, []).append(status)

    print("=== INFORMATION CLASS MAP (modality x access) ===")
    print(f"    {MODALITY_NOTE}\n")
    order = ["covered", "partial", "never-visited", "blocked"]
    for st in order:
        items = by_status.get(st, [])
        print(f"--- {st.upper()} ({len(items)})")
        for name, mod, note in sorted(items):
            print(f"    {name:<28} [{mod:<10}] {note}")
        print()

    nv = by_status.get("never-visited", [])
    print(f"=> EXPANSION TARGET LIST: {len(nv)} classes never visited "
          f"({100*len(nv)/len(CLASSES):.0f}% of the mapped universe)")
    print("   These are what the NEW_BRANCHES budget slice funds. Modality coverage:")
    for mod in sorted(by_mod):
        sts = by_mod[mod]
        cov = sum(1 for s in sts if s == "covered")
        print(f"     {mod:<12} {cov}/{len(sts)} covered")
    print("\n   LEGITIMACY GATE (s13, non-negotiable): public + legitimately accessible ONLY.")
    print("   Public forums/groups/videos/transcripts/filings YES. Paywalled/pirated/private NO,")
    print("   regardless of expected value.")

    OUT.write_text(json.dumps(
        {"updated": datetime.now(tz=UTC).isoformat(), "n_classes": len(CLASSES),
         "never_visited": len(nv), "modality_note": MODALITY_NOTE,
         "classes": {k: {"modality": v[0], "status": v[1], "note": v[2]}
                     for k, v in CLASSES.items()}}, indent=1), "utf-8")
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()

```

### scripts/optimal_hold.py
```python
"""OPTIMAL HOLDING PERIOD -- optimise the alpha that WORKS instead of hunting a new one.

Today established: the entry signal is real (funding persistence IC +0.43, top-decile +29%/yr vs
+3.8% median). The strategy is not broken; its ECONOMICS are. So the highest-value remaining
question is not "what else predicts returns" but "what holding period maximises NET capture".

THE TRADE-OFF, both sides now measured:
  LONGER hold  -> more funding periods collected per round trip (cost amortises)
               -> but the selection edge DECAYS (top-decile advantage falls as the entry-time
                  ranking goes stale; funding shock half-life is ~6h)
  SHORTER hold -> captures the freshest, richest funding
               -> but pays the round trip more often

_MIN_HOLD_H = 24 was chosen to STOP CHURN (gap #42), not because 24h maximised anything. It has
never been optimised against measured persistence and measured cost. This computes the optimum
directly from both.

METHOD: for each candidate hold H, walk the funding panel -- at each rebalance take the top-decile
by current funding, hold H hours, sum the funding actually realised, subtract one round trip, and
annualise. The winner is the H with the highest NET annualised capture.

Free Binance funding + the desk's own measured cost model. Stage-A. Run from repo root.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

OUT = Path("data/optimal_hold.json")
HOLDS_H = [8, 16, 24, 32, 48, 72, 120, 168]      # 1 period .. 1 week
N_HIST = 500


def _get(u, t=30):
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(u, headers={"User-Agent": "q/1.0"}), timeout=t).read().decode())


def universe(n: int = 40) -> list[str]:
    d = _get("https://fapi.binance.com/fapi/v1/ticker/24hr")
    rows = [(float(x.get("quoteVolume", 0)), x["symbol"]) for x in d if x["symbol"].endswith("USDT")]
    rows.sort(reverse=True)
    return [s for _, s in rows[:n]]


def funding(sym: str) -> dict[int, float]:
    try:
        d = _get(f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={sym}&limit={N_HIST}")
        return {int(x["fundingTime"]) // 3600000: float(x["fundingRate"]) for x in d}
    except Exception:
        return {}


def cost_bps() -> dict[str, float]:
    try:
        m = json.loads(Path("data/cost_model.json").read_text("utf-8"))["symbols"]
    except Exception:
        return {}
    out = {}
    for s, d in m.items():
        v = d.get("pair", {}).get("500", {}).get("pair_roundtrip_bps")
        if v is not None:
            out[s] = float(v)
    return out


def main() -> None:
    syms = universe()
    ser = {s: f for s in syms if len(f := funding(s)) >= 200}
    if len(ser) < 15:
        print(f"only {len(ser)} usable symbols")
        return
    grid = sorted(set.intersection(*[set(v) for v in ser.values()]))
    costs = cost_bps()
    med_cost = float(np.median(list(costs.values()))) if costs else 5.7
    print("=== OPTIMAL HOLDING PERIOD (optimising the alpha that works) ===")
    print(f"    {len(ser)} symbols, {len(grid)} funding periods (~{len(grid)/3:.0f} days)")
    print(f"    round-trip cost: median measured {med_cost:.2f} bps"
          f" ({len(costs)} symbols priced)\n")
    print(f"  {'hold':>6} {'gross %/yr':>11} {'cost %/yr':>10} {'NET %/yr':>10} {'rotations/yr':>13}")

    res = []
    for H in HOLDS_H:
        k = max(1, H // 8)                      # funding periods per hold
        gross, used = [], 0
        for i in range(0, len(grid) - k, k):    # non-overlapping rotations
            t = grid[i]
            cur = np.array([ser[s][t] for s in ser])
            names = list(ser)
            top = np.argsort(cur)[-max(2, len(cur) // 10):]
            picked = [names[j] for j in top]
            # funding actually realised over the hold, per picked symbol
            realised = [sum(ser[s][grid[i + j]] for j in range(1, k + 1)) for s in picked]
            gross.append(float(np.mean(realised)))
            used += 1
        if not gross:
            continue
        per_rot = float(np.mean(gross))                       # fraction, per rotation
        rots = 365 * 24 / H
        gross_ann = per_rot * rots * 100
        # cost: one round trip per rotation, weighted to the picked (liquid) names
        cost_ann = (med_cost / 1e4) * rots * 100
        net_ann = gross_ann - cost_ann
        print(f"  {H:>5}h {gross_ann:>10.2f}% {cost_ann:>9.2f}% {net_ann:>9.2f}% {rots:>12.0f}")
        res.append({"hold_h": H, "gross_pct_yr": round(gross_ann, 3),
                    "cost_pct_yr": round(cost_ann, 3), "net_pct_yr": round(net_ann, 3),
                    "rotations_yr": round(rots, 1), "n_rotations_tested": used})

    if res:
        best = max(res, key=lambda r: r["net_pct_yr"])
        cur24 = next((r for r in res if r["hold_h"] == 24), None)
        print(f"\n  OPTIMUM: {best['hold_h']}h  ->  net {best['net_pct_yr']:+.2f}%/yr")
        if cur24:
            d = best["net_pct_yr"] - cur24["net_pct_yr"]
            print(f"  CURRENT _MIN_HOLD_H = 24h -> net {cur24['net_pct_yr']:+.2f}%/yr")
            print(f"  IMPROVEMENT AVAILABLE: {d:+.2f} %/yr by moving 24h -> {best['hold_h']}h"
                  if abs(d) > 0.5 else "  24h is at/near the optimum -- leave it alone")
        print("\n  CAVEAT: gross uses the LIQUID top-40 universe and the MEDIAN measured cost.")
        print("  A book trading unmeasured illiquid names pays far more than this and its true")
        print("  optimum is LONGER (cost amortises over more periods). Re-run per-universe.")
    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "median_cost_bps": med_cost, "results": res}, indent=1), "utf-8")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()

```

### scripts/research_autopsy.py
```python
"""RESEARCH AUTOPSY -- every failure must produce a LESSON, not just a tombstone.

THE GAP: the graveyard records WHAT died and a cause tag. It does not record the FAILURE MODE, so
the desk cannot learn sentences like "crypto attention features fail because they are COINCIDENT,
not delayed" -- which is the kind of statement that prevents a whole future family of experiments.
negative_knowledge.py classifies PERMANENCE (can this revive?). This classifies AETIOLOGY (why did
it die?) and then AGGREGATES across families to extract institutional lessons.

EIGHT FAILURE MODES (the principal's taxonomy, mapped onto this desk's measured history):
  A NO_MECHANISM        no causal story that survives "why has nobody arbitraged this?"
  B WRONG_MEASUREMENT   the construction measured something other than the intended quantity
  C WRONG_TIMING        real relationship, wrong horizon or lead/lag
  D ALREADY_ARBITRAGED  the edge exists but is competed to below cost
  E DATA_QUALITY        the finding was an artifact of the pipeline, not the market
  F REGIME_DEPENDENT    worked in one environment, not generally
  G TOO_EXPENSIVE       real edge, smaller than its own transaction cost
  H OVERFIT             fit the sample, not the process

WHY THIS MATTERS MORE THAN IT LOOKS: the desk killed ~28 hypotheses today. If each is stored as
"rejected", that is 28 tombstones. If each is stored with its MODE, patterns emerge that are worth
more than any single experiment -- e.g. if most public-data failures are mode D or G, the lesson is
not "try different public data", it is "public data cannot clear costs here", which retires an
entire search direction.

Read-only. No LLM, no keys. Run from repo root.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
GRAVE = ROOT / "docs/graveyard.md"
OUT = ROOT / "data/research_autopsy.json"

MODES = {
    "A_NO_MECHANISM": ("no_economics", "no mechanism", "no causal", "no named mechanism",
                       "base rate", "no strong pre-registered"),
    "B_WRONG_MEASUREMENT": ("construction", "scope", "unit error", "misalign", "mismatch",
                            "parser", "fragment", "measured the wrong"),
    "C_WRONG_TIMING": ("horizon", "daily", "no_edge_daily", "timing", "lead", "coincid",
                       "same-period", "contemporaneous", "half-life"),
    "D_ALREADY_ARBITRAGED": ("crowded", "arbitraged", "tightly arbitraged", "competed",
                             "pre-arbitraged", "everyone"),
    "E_DATA_QUALITY": ("artifact", "lookahead", "degenerate", "non-synchronous", "timezone",
                       "stale", "silent-zero", "implausible", "data-blocked"),
    "F_REGIME_DEPENDENT": ("regime", "only-recent-era", "bull", "inverts", "regime_artifact"),
    "G_TOO_EXPENSIVE": ("cost", "fee", "bps", "round-trip", "costs_killed", "slippage",
                        "unprofitable", "too tight"),
    "H_OVERFIT": ("overfit", "dsr", "p-hack", "specification search", "unstable", "n=",
                  "underpowered", "insignificant", "fat sharpe"),
}

FAMILY = {
    "attention/social": ("attention", "wikipedia", "sentiment", "social", "narrative", "search"),
    "developer": ("developer", "github", "commit", "contributor", "dev "),
    "trader/behavioural": ("trader", "elite", "copytrad", "leaderboard", "skill", "whale"),
    "regional premium": ("premium", "kimchi", "bithumb", "coinone", "turk", "cny", "peg", "lsd",
                         "staking"),
    "funding/positioning": ("funding", "oi_", "open interest", "ls_contrarian", "basis", "carry"),
    "on-chain/flow": ("onchain", "on-chain", "stablecoin", "throughput", "flow", "bridge", "dex"),
    "price-only/TA": ("momentum", "reversal", "breakout", "kama", "squeeze", "lowvol", "trend",
                      "illiquidity", "indicator"),
}


def classify(text: str, table: dict[str, Any]) -> list[str]:
    t = text.lower()
    return [k for k, kws in table.items() if any(w in t for w in kws)]


def main() -> None:
    if not GRAVE.exists():
        raise SystemExit("no graveyard")
    rows = []
    for ln in GRAVE.read_text("utf-8").splitlines():
        if not ln.startswith("|") or set(ln) <= set("|- "):
            continue
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if len(cells) < 3 or cells[0].lower() in ("name", "signal", "strategy"):
            continue
        blob = " ".join(cells)
        modes = classify(blob, MODES) or ["UNCLASSIFIED"]
        fams = classify(blob, FAMILY) or ["other"]
        rows.append({"name": cells[0][:80], "modes": modes, "families": fams,
                     "evidence": cells[1][:110]})

    print(f"=== RESEARCH AUTOPSY -- {len(rows)} failures, cause of death classified ===")
    print("    a tombstone says WHAT died; an autopsy says WHY, and why is what transfers\n")

    mc: dict[str, int] = {}
    for r in rows:
        for m in r["modes"]:
            mc[m] = mc.get(m, 0) + 1
    print("  FAILURE MODES across the graveyard:")
    for m, c in sorted(mc.items(), key=lambda kv: -kv[1]):
        print(f"    {m:<24} {c:>3}  ({c/len(rows)*100:.0f}%)")

    print("\n  FAMILY x DOMINANT MODE -- this is where the transferable lesson lives:")
    fam_modes: dict[str, dict[str, int]] = {}
    for r in rows:
        for f in r["families"]:
            d = fam_modes.setdefault(f, {})
            for m in r["modes"]:
                d[m] = d.get(m, 0) + 1
    lessons = []
    for f, d in sorted(fam_modes.items(), key=lambda kv: -sum(kv[1].values())):
        top = sorted(d.items(), key=lambda kv: -kv[1])[:2]
        n = sum(d.values())
        print(f"    {f:<22} n={n:<3} -> {', '.join(f'{k}({v})' for k, v in top)}")
        if top and top[0][1] >= 2:
            lessons.append({"family": f, "dominant_mode": top[0][0], "count": top[0][1],
                            "n": n})

    print("\n  INSTITUTIONAL LESSONS (family + dominant failure mode, n>=2):")
    TEXT = {
        "C_WRONG_TIMING": "the relationship may be real but is COINCIDENT or on the wrong horizon "
                          "-- do not retry at the same frequency",
        "G_TOO_EXPENSIVE": "the edge is smaller than its own transaction cost -- only revisit if "
                           "costs fall structurally, not if the signal looks better",
        "H_OVERFIT": "died to sample/power, not to the world -- a properly powered re-test is "
                     "legitimate, a re-fit is not",
        "E_DATA_QUALITY": "the finding was a PIPELINE artifact -- fix measurement before "
                          "concluding anything about the market",
        "A_NO_MECHANISM": "no causal story survived scrutiny -- needs a NEW named mechanism, not "
                          "new data",
        "D_ALREADY_ARBITRAGED": "competed away -- only revisit with evidence the crowd left",
        "F_REGIME_DEPENDENT": "environment-specific -- test conditional on regime or not at all",
        "B_WRONG_MEASUREMENT": "measured something other than intended -- rebuild the construction",
    }
    for L in lessons:
        print(f"    {L['family']:<22} {TEXT.get(L['dominant_mode'], L['dominant_mode'])}")

    unc = sum(1 for r in rows if r["modes"] == ["UNCLASSIFIED"])
    print(f"\n  {unc} entries UNCLASSIFIED -- each is a graveyard row whose cause was never")
    print("  written precisely enough to learn from. That is itself a defect worth fixing.")
    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(), "n": len(rows),
                               "mode_counts": mc, "family_modes": fam_modes,
                               "lessons": lessons, "unclassified": unc,
                               "autopsies": rows}, indent=1), "utf-8")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()

```

### scripts/run_carry_harvest.py
```python
"""Delta-neutral crypto funding-CARRY harvest -- the last economically-distinct niche test.

Mechanism: perp funding is a leverage-demand RISK PREMIUM (persistently positive). Harvest it
market-neutral: short perp + long spot when funding>0 (receive funding), reverse when funding<0.
The price legs cancel EXCEPT the perp-spot basis -- which blows out in crashes. That basis term is
included on purpose, so this is an HONEST test (a funding-income-only model would hide the crash
risk and manufacture a false survivor). Validated through the existing gauntlet (CPCV/PBO/DSR/RC/
walk-forward/fragility/capacity), net of fees. Survivors reported honestly.

    python scripts/run_carry_harvest.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from libs.autodiscovery.models import Family, Hypothesis
from libs.autodiscovery.validation import campaign_gate_stats, validate
from libs.data.crypto_source import fetch_spot_klines
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType

_CRYPTO = Path("data/lake/bronze/crypto")
_OUT = Path("reports/carry_harvest")
_FEE_PER_FLIP_LEG = 8e-4          # taker on perp+spot, one-way per unit |delta position|
_THRESHOLDS = (0.0, 0.0001, 0.0003)  # harvest when |funding| exceeds (0, ~11%/yr, ~33%/yr)
_FAIL_MODES = ["basis blowout in crash", "funding regime flip negative", "exchange/counterparty"]


def _symbols() -> list[str]:
    if not _CRYPTO.exists():
        return []
    return sorted(d.name for d in _CRYPTO.iterdir() if (d / Timeframe.H8.value).exists())


def _carry_returns(perp: np.ndarray, spot: np.ndarray, funding: np.ndarray,
                   threshold: float) -> np.ndarray:
    n = len(perp)
    perp_ret = np.zeros(n)
    perp_ret[1:] = perp[1:] / perp[:-1] - 1.0
    spot_ret = np.zeros(n)
    spot_ret[1:] = spot[1:] / spot[:-1] - 1.0
    # Decision at t uses funding known at t; applied to the NEXT bar (no look-ahead).
    h = np.where(np.abs(funding) > threshold, np.sign(funding), 0.0)
    hd = np.zeros(n)
    hd[1:] = h[:-1]                              # lag-1 position
    flips = np.abs(np.diff(hd, prepend=0.0))
    # short perp + long spot when hd>0 -> receive funding, pay the basis move (perp-spot return)
    return hd * (funding - (perp_ret - spot_ret)) - flips * _FEE_PER_FLIP_LEG


def main() -> None:
    symbols = _symbols()
    if not symbols:
        raise SystemExit("no crypto H8 data; run scripts/ingest_crypto.py --interval 8h first")
    for s in symbols:
        register_instrument(InstrumentSpec(symbol=s, asset_class=AssetClass.CRYPTO, description=s))
    lake = ParquetLake("data/lake")

    prepared: list[tuple[str, str, np.ndarray]] = []
    for sym in symbols:
        df = lake.read_bars(Layer.BRONZE, sym, Timeframe.H8).set_index("timestamp")
        if "funding" not in df.columns or len(df) < 500:
            continue
        start_ms = int(df.index[0].timestamp() * 1000)
        spot_df = fetch_spot_klines(sym, interval="8h", start_ms=start_ms).set_index("timestamp")
        if spot_df.empty:
            continue
        joined = df.join(spot_df["close"].rename("spot"), how="inner").dropna()
        if len(joined) < 500:
            continue
        perp = joined["close"].to_numpy("float64")
        spot = joined["spot"].to_numpy("float64")
        funding = joined["funding"].to_numpy("float64")
        for thr in _THRESHOLDS:
            rets = _carry_returns(perp, spot, funding, thr)
            prepared.append((sym, f"thr={thr}", rets))
        print(f"  {sym}: {len(joined)} aligned 8h bars")

    if not prepared:
        raise SystemExit("no aligned perp/spot series")

    min_len = min(len(r) for _, _, r in prepared)
    matrix = np.column_stack([r[-min_len:] for _, _, r in prepared])
    sharpes = np.array([sharpe_ratio(r) for _, _, r in prepared], dtype="float64")
    n_trials = len(prepared)
    # per-candidate gates (gap #87 flip, principal-ruled 2026-07-29); thresholds unchanged
    campaign = campaign_gate_stats(matrix)

    survivors = 0
    gate_fail: dict[str, int] = {}
    rows = []
    # enumerate order == column_stack order over `prepared`, so `col` is the matrix column.
    for col, ((sym, sub, rets), spr) in enumerate(zip(prepared, sharpes, strict=True)):
        hyp = Hypothesis(family=Family.CARRY, subtype=f"funding_carry_{sub}", symbol=sym,
                         params={}, mechanism=MechanismType.RISK_PREMIUM,
                         edge_source="perp funding carry delta-neutral", failure_modes=_FAIL_MODES)
        v = validate(rets, hypothesis=hyp, n_trials=n_trials, sharpe_estimates=sharpes,
                     returns_matrix=matrix, campaign=campaign, column=col)
        survivors += int(v.survived)
        for g, ok in v.gates.items():
            if not ok:
                gate_fail[g] = gate_fail.get(g, 0) + 1
        rows.append({"symbol": sym, "variant": sub, "sharpe_per_bar": round(float(spr), 4),
                     "ann_sharpe": round(float(v.metrics.annual_sharpe), 2),
                     "survived": v.survived, "reason": v.rejection_reason})

    _OUT.mkdir(parents=True, exist_ok=True)
    (_OUT / "carry_report.json").write_text(
        json.dumps({"n_trials": n_trials, "survivors": survivors,
                    "rejection_by_gate": gate_fail, "candidates": rows}, indent=2), "utf-8")
    print(f"\n[carry] tested={n_trials} survivors={survivors}")
    print(f"rejection_by_gate={gate_fail}")
    best = max(rows, key=lambda r: r["sharpe_per_bar"])
    print(f"best raw sharpe/bar: {best['symbol']} {best['variant']} "
          f"sharpe={best['sharpe_per_bar']} survived={best['survived']}")
    if survivors == 0:
        print("ZERO survivors net-of-cost (honest) -- funding-carry niche does not clear.")


if __name__ == "__main__":
    main()

```

### scripts/run_crossasset_shadow.py
```python
"""Forward SHADOW + target-portfolio emitter for the MT5 cross-asset book (zero capital).

This is the Python brain executing the architecture end-to-end in shadow: it researches globally
(the full multi-asset lake), builds the most ROBUST MT5-executable book -- an equal-risk combo of
two premia that showed real net-of-cost edge (cross-asset TREND + cross-sectional MOMENTUM) -- runs
it through the FULL gauntlet, tracks live out-of-sample performance vs backtest, and emits today's
TARGET PORTFOLIO (per MT5 instrument). That target file is exactly what the rebalancer + EABridge +
QuantPlatformExecutor.mq5 consume; the EA only executes it. No capital is allocated. Promotion to
tiny live requires the pre-committed rule in docs/KILL_THESIS.md + human approval.

Frozen (pre-registered, never re-optimized): trend lookback=100, momentum lookback=120, q=0.3.

    python scripts/run_crossasset_shadow.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from libs.autodiscovery.models import Family, Hypothesis
from libs.autodiscovery.validation import campaign_gate_stats, validate
from libs.data.cleaning import DEFAULT_CAPS, guard_close
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.research.crossasset import (
    combine_weights,
    trend_basket_returns,
    trend_basket_weights,
    xsec_momentum_returns,
    xsec_momentum_weights,
)
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType

_COVERAGE = Path("reports/multiasset_coverage.json")
_OUT = Path("reports/mt5_crossasset_shadow")
_WEB = Path("web/crossasset_shadow.json")
_TARGET = Path("data/target_portfolio.json")
_STATE = Path("data/crossasset_shadow_state.json")
_PPY = 252.0
_FROZEN = {"trend_lb": 100, "mom_lb": 120, "q": 0.3, "band": 0.05}   # pre-registered
_COST = {"fx": 1.0e-4, "metal": 2.0e-4, "energy": 2.5e-4,
         "index": 1.0e-4, "crypto": 6.0e-4, "equity": 2.0e-4}
_FAIL = ["trend/momentum premia compress or crowd", "regime shift (trend->chop)",
         "correlated cross-asset drawdown", "broker cost exceeds edge", "edge decay"]


def _load() -> tuple[pd.DataFrame, dict[str, float], dict[str, str]]:
    cov = json.loads(_COVERAGE.read_text("utf-8"))
    lake = ParquetLake("data/lake")
    closes, cost, klass = {}, {}, {}
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
        klass[sym] = ac
    close = pd.DataFrame(closes).sort_index()
    caps = {s: DEFAULT_CAPS.get(klass[s], 0.5) for s in close.columns}
    close = guard_close(close, caps)                     # gap-guard before emitting target weights
    return close, cost, klass


def _ann(r: np.ndarray) -> float:
    a = r[r != 0.0]
    return round(float(sharpe_ratio(a) * np.sqrt(_PPY)), 2) if len(a) > 5 else 0.0


def _verdict(fwd_days: int, fwd: float, bt: float) -> str:
    if fwd_days < 90:
        return f"ACCUMULATING ({fwd_days}/90+ days of forward evidence)"
    if fwd < 0:
        return "FAILING FORWARD -> kill candidate"
    if fwd >= 0.5 and fwd >= 0.5 * bt:
        return "ON TRACK -> eligible for TINY live on human approval (governance gate)"
    return "WEAK forward -> continue shadow, do not deploy"


def main() -> None:
    close, cost, klass = _load()
    if close.shape[1] < 6:
        raise SystemExit("need the multi-asset lake; run scripts/ingest_multiasset.py first")
    tlb, mlb, q, band = (_FROZEN["trend_lb"], _FROZEN["mom_lb"], _FROZEN["q"], _FROZEN["band"])

    r_trend = trend_basket_returns(close, cost, lookback=tlb, band=band)
    r_mom = xsec_momentum_returns(close, cost, lookback=mlb, q=q, band=band)
    r_combo = 0.5 * r_trend + 0.5 * r_mom

    # Gauntlet on the combo (peers = the two sub-books for the multiplicity stats)
    matrix = np.column_stack([r_trend, r_mom, r_combo])
    sharpes = np.array([sharpe_ratio(x[x != 0.0]) for x in (r_trend, r_mom, r_combo)])
    # per-candidate gates (gap #87 flip, principal-ruled 2026-07-29); thresholds unchanged
    campaign = campaign_gate_stats(matrix)
    active = r_combo[r_combo != 0.0]
    verdict_gauntlet = validate(
        active, hypothesis=Hypothesis(
            family=Family.CROSS_ASSET, subtype="trend+momentum combo", symbol="MT5_XASSET",
            params={}, mechanism=MechanismType.RISK_PREMIUM,
            edge_source="cross-asset trend + x-sec momentum (equal risk, costed)",
            failure_modes=_FAIL), n_trials=3, sharpe_estimates=sharpes,
        returns_matrix=matrix, campaign=campaign, column=2)  # r_combo = matrix column 2

    # Forward shadow split
    dates = close.index
    state = json.loads(_STATE.read_text("utf-8")) if _STATE.exists() else {}
    if "shadow_start" not in state:
        state["shadow_start"] = dates[-1].isoformat()
        _STATE.parent.mkdir(parents=True, exist_ok=True)
        _STATE.write_text(json.dumps(state), "utf-8")
    shadow_start = pd.Timestamp(state["shadow_start"])
    is_fwd = dates >= shadow_start
    bt_sharpe, fwd_sharpe = _ann(r_combo[~is_fwd]), _ann(r_combo[is_fwd])
    fwd_days = int(np.sum(r_combo[is_fwd] != 0.0))

    # Today's TARGET PORTFOLIO (the brain's decision -> executor -> EA). Snapshot each instrument at
    # its latest available close (ffill) so a weekend bar -- when only crypto CFDs trade -- does not
    # collapse the book to crypto-only. ffill is for the as-of snapshot ONLY; returns stay unfilled.
    close_asof = close.ffill()
    w_trend = trend_basket_weights(close_asof, lookback=tlb)
    w_mom = xsec_momentum_weights(close_asof, lookback=mlb, q=q)
    target = combine_weights(w_trend, w_mom)
    target_payload = {
        "strategy": "mt5_crossasset_trend_momentum_combo",
        "as_of": dates[-1].date().isoformat(),
        "generated": datetime.now(tz=UTC).isoformat(),
        "deployable": bool(verdict_gauntlet.survived),
        "note": "SHADOW target weights (zero capital). Execution requires human approval per "
                "docs/KILL_THESIS.md; the EA only executes an approved target.",
        "weights": {k: round(v, 4) for k, v in sorted(target.items(),
                                                       key=lambda kv: -abs(kv[1]))},
    }

    equity = np.cumprod(1.0 + r_combo)
    n = len(equity)
    step = max(1, n // 300)
    curve = [{"t": dates[i].date().isoformat(), "v": round(float(equity[i]), 4),
              "fwd": bool(is_fwd[i])} for i in range(0, n, step)]
    web = {
        "strategy": "MT5 cross-asset (trend+momentum combo, frozen)",
        "shadow_start": state["shadow_start"], "symbols": close.shape[1],
        "backtest_ann_sharpe": bt_sharpe, "forward_ann_sharpe": fwd_sharpe,
        "forward_days": fwd_days,
        "gates_passed": f"{sum(verdict_gauntlet.gates.values())}/{len(verdict_gauntlet.gates)}",
        "deployable": bool(verdict_gauntlet.survived),
        "verdict": _verdict(fwd_days, fwd_sharpe, bt_sharpe),
        "updated": datetime.now(tz=UTC).isoformat(), "equity": curve,
        "target_weights": target_payload["weights"],
    }

    _OUT.mkdir(parents=True, exist_ok=True)
    (_OUT / "report.json").write_text(json.dumps(web, indent=2), "utf-8")
    _WEB.parent.mkdir(parents=True, exist_ok=True)
    _WEB.write_text(json.dumps(web, indent=2), "utf-8")
    _TARGET.parent.mkdir(parents=True, exist_ok=True)
    _TARGET.write_text(json.dumps(target_payload, indent=2), "utf-8")

    print(f"cross-asset combo: bt_sharpe={bt_sharpe} fwd_sharpe={fwd_sharpe} "
          f"gates={web['gates_passed']} deployable={web['deployable']}")
    print(f"gauntlet: {verdict_gauntlet.rejection_reason or 'PASSED'}")
    print(f"verdict: {web['verdict']}")
    print(f"target weights ({len(target)} instruments) -> {_TARGET}:")
    for k, v in target_payload["weights"].items():
        print(f"  {k:8} {klass.get(k,'?'):7} {v:+.4f}")


if __name__ == "__main__":
    main()

```

### scripts/run_llm_trader.py
```python
#!/usr/bin/env python3
"""LLM DISCRETIONARY SLEEVE (R0122) -- Claude as a human-style trader, 24/7, PAPER ONLY.

PRINCIPAL REQUEST (2026-07-31): *"a strategy where Claude acts like a human trader with a brain
and trades 24/7 at charts."*

WHAT THIS IS, AND WHAT IT DELIBERATELY IS NOT. It is NOT an LLM staring at chart images calling
breakouts, and refusing that is not timidity -- it is the two measured facts. (1) Language models
reason poorly over precise numeric OHLC: the desk's own numeric pipelines already dominate on
anything expressible as arithmetic, so a model eyeballing candles is a worse version of a tool
that exists. (2) "It looked like a breakout" is a PATTERN WITH NO MECHANISM, which is precisely
the class the 420-tested/0-survived record refuted -- carding it would be breadth-mining with a
narrator attached (L1.16, L1.25).

WHERE AN LLM GENUINELY HAS AN EDGE, and this sleeve lives exactly there: UNSTRUCTURED
INFORMATION THAT NUMERIC MODELS CANNOT PARSE AT ALL. Exchange announcements, listing/delisting
notices, contract-spec changes, chain incidents, regulatory statements, unusual forum activity --
text a human trader reads and reacts to, arriving 24/7 while a human sleeps. The mechanism is
stated and falsifiable: *an event whose implication requires reading prose is priced more slowly
than one expressible as a number, and the desk can read it continuously.* That is a FORCED-
PARTICIPANT-adjacent claim (someone must reposition when a contract spec changes) and it is
testable.

THE HONEST HARNESS, which is what makes this worth running at all:
  * EVERY call is a PRE-REGISTERED FORECAST -- direction, horizon, and an explicit PROBABILITY --
    logged to libs.self_improvement.forecast_calibration. It is therefore SCORED automatically
    (Brier, bias, hit-rate) by the L1.29 calibration fence, and its measured over-confidence is
    fed back as a shrinkage. An LLM trader that cannot be scored is a story generator; this one
    grades itself whether it likes the answer or not.
  * EVERY call states a MECHANISM and a FALSIFIER, or it is refused at write time. No mechanism,
    no trade -- the same bar every axis on this desk faces.
  * PAPER ONLY, permanently, until it earns promotion the same way as everything else: a
    pre-registered forward clock, a Holm slot, and Stage-B evidence (L1.6). This file places no
    orders and imports no connector -- a test asserts it.
  * Its benchmark is not zero. A discretionary sleeve must beat BUY-AND-HOLD and the desk's own
    carry sleeve after costs, or it is an expensive way to be average.

    python scripts/run_llm_trader.py --brief        # build the market brief only
    python scripts/run_llm_trader.py                # brief -> call -> log forecast -> paper mark
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_BOOK = "data/llm_trader_book.jsonl"
_STATE = "data/llm_trader.json"
MIN_PROB, MAX_PROB = 0.50, 0.95      # a call below 50% is a call the other way; 95%+ is a tell
#: 3 concurrent calls. DERIVED from the same simulation that set the conviction sleeve's heat cap:
#: at equal total risk, 1 bet has P(-90% drawdown)=100% while 4 bets have 1% and 8 have 0%. This
#: sleeve carries no stop, so its per-call loss is unbounded in a way the conviction sleeve's is
#: not -- 3 is the point where it stays a portfolio rather than a punt, without pretending the
#: no-stop payoff is safe to spread thinly.
MAX_OPEN = 3

#: CONTROLLED MECHANISM TAXONOMY (external critique, 2026-07-31). Free-text mechanisms cannot be
#: AGGREGATED, so "which mechanism families actually produce alpha" is unanswerable and every
#: thesis looks equally novel. Forcing each call into one of these makes mechanism survival
#: measurable exactly like an axis: after N calls the desk can retire the families that never
#: pay and concentrate on the ones that do. NEW families are added deliberately, never invented
#: per-call -- an unbounded vocabulary is the same as no vocabulary.
MECHANISMS = (
    "FORCED_LIQUIDATION",      # leveraged positions must close at any price
    "COLLATERAL_CHANGE",       # margin/leverage/haircut rules force repositioning
    "LIQUIDITY_MIGRATION",     # venue/pool listing or delisting moves where trading happens
    "INVENTORY_ADJUSTMENT",    # market makers rebalance inventory
    "ARBITRAGE_DISLOCATION",   # a link between venues/instruments breaks
    "SUPPLY_SHOCK",            # unlocks, emissions, burns, treasury movement
    "REGULATORY_CONSTRAINT",   # access/eligibility restricted or expanded
    "INFRASTRUCTURE_FAILURE",  # exploit, bridge/validator/RPC outage
    "GOVERNANCE_CHANGE",       # tokenomics, fees, emissions decided
)

#: WHO IS FORCED TO TRANSACT -- the external critique's sharpest structural suggestion. "LONG
#: because bullish" is untestable; "market makers must reduce inventory" names a participant
#: whose behaviour can be checked against OI, depth and flow. Forced flows persist; discretionary
#: ones do not, and this field is what lets the desk tell them apart afterwards.
PARTICIPANTS = ("LEVERAGED_LONGS", "LEVERAGED_SHORTS", "MARKET_MAKERS", "ARBITRAGEURS",
                "VALIDATORS_MINERS", "TREASURY_ISSUER", "ETF_AUTHORIZED_PARTICIPANTS",
                "LENDING_PROTOCOL_USERS", "NOBODY_FORCED")

_CALL_BRIEF = """You are the desk's DISCRETIONARY TRADER. You trade like a thoughtful human: you
read what happened, you form a view with a REASON, you state how confident you are, and you say
what would prove you wrong. You are PAPER-TRADING -- no capital moves on your word, and your only
route to real size is the same forward-evidence gate every other strategy faces.

YOUR EDGE IS NOT CHARTS. The desk's numeric pipelines beat you at anything arithmetic: momentum,
carry, z-scores, cross-sectional ranks. Do not compete there -- you will lose and you will waste
the slot. YOUR EDGE IS PROSE: exchange announcements, contract-spec changes, listing/delisting
notices, chain incidents, regulatory statements, unusual community activity -- information whose
IMPLICATION requires reading, arriving at 3am while humans sleep. Trade the implication of an
EVENT, not the shape of a line.

TODAY'S BRIEF:
{brief}

OUTPUT EXACTLY ONE JSON OBJECT, no prose around it:
{{"action": "CALL" | "PASS",
  "symbol": "BTCUSDT",
  "direction": "LONG" | "SHORT",
  "horizon_hours": 8,
  "probability": 0.62,            // YOUR honest P(this call is right). It WILL be scored.
  "mechanism": "who is forced to do what, and why that moves price",
  "falsifier": "the observation that would prove this wrong",
  "reasoning": "2-4 sentences"}}

PASS IS A FIRST-CLASS ANSWER and most windows deserve it: if nothing happened that requires
reading prose to understand, there is no edge here and a call would be noise. A desk that trades
every window is a desk with no filter. REFUSED AT WRITE TIME: any call without a real mechanism
(not a pattern), without a falsifier, or with a probability outside {lo}-{hi}.

BUT A PASS IS ALSO SCORED, and you must justify it. A model that passes on everything gets a
beautiful calibration score and contributes nothing -- so a PASS carries
`passed_on` (the most material event you declined) and `pass_reason` (already priced / no
mechanism / not tradeable / unclear direction). Those declines are marked against the same
horizon as a real call, so the desk can measure whether your filter ADDS value or merely avoids
deciding. Passing is allowed; passing without saying what you passed on is not.

FIELDS REQUIRED ON EVERY CALL, in addition to the above:
  "mechanism_class": one of {mechs}
  "forced_participant": one of {parts} -- who MUST transact, not who might want to
  "compressible": true if a simple IF-THEN rule on the event text would produce this same call.
    ANSWER HONESTLY: if most of your calls are compressible, the desk should replace you with
    ten lines of code, and finding that out is a win, not a loss."""


def build_brief(root: Path) -> dict[str, Any]:
    """Market state + the unstructured feeds this sleeve actually trades on."""
    brief: dict[str, Any] = {"generated": datetime.now(tz=UTC).isoformat(), "sources": {}}
    for label, rel, n in (("funding", "data/bitmex_funding.jsonl", 5),
                          ("defi_lending", "data/defi_lending.jsonl", 2),
                          ("liquidations", "data/liquidations.jsonl", 8),
                          ("announcements", "data/exchange_announcements.jsonl", 10),
                          ("news", "data/news_feed.jsonl", 10)):
        try:
            lines = (root / rel).read_text("utf-8", errors="ignore").splitlines()
            if label == "announcements":
                # ONLY TRADEABLE ITEMS reach the trader (R0122b): fresh enough to still be
                # unpriced AND material enough to force repositioning. Handing it the archive
                # is how a sleeve "trades" a three-year-old exploit.
                import json as _j
                rows = []
                for ln in reversed(lines):
                    try:
                        r = _j.loads(ln)
                    except ValueError:
                        continue
                    if r.get("tradeable"):
                        rows.append({k: r[k] for k in
                                     ("source", "title", "symbols", "latency_minutes", "tier")
                                     if k in r})
                    if len(rows) >= n:
                        break
                brief["sources"][label] = rows or "no TRADEABLE events this window"
                continue
            brief["sources"][label] = [ln[:400] for ln in lines[-n:] if ln.strip()]
        except OSError:
            # ABSENT, never silently empty: a brief that hides its missing feeds invites a call
            # made on nothing (L1.28a).
            brief["sources"][label] = "ABSENT on this host"
    return brief


def validate_call(call: dict[str, Any]) -> tuple[bool, str]:
    """The write-time bar. A call that cannot state WHY is not a call (L1.16)."""
    if call.get("action") == "PASS":
        # A PASS IS A DECISION AND IS SCORED. Without this the model optimises toward passing:
        # perfect calibration, zero economic value (external critique, 2026-07-31).
        if not call.get("pass_reason"):
            return False, ("REFUSED: a PASS must say WHY -- an unjustified pass is how a model "
                           "farms a clean Brier score while contributing nothing")
        return True, f"PASS recorded and scored: {str(call.get('pass_reason'))[:80]}"
    for field in ("symbol", "direction", "horizon_hours", "probability", "mechanism",
                  "falsifier", "mechanism_class", "forced_participant"):
        if not call.get(field):
            return False, f"REFUSED: missing {field}"
    if call["direction"] not in ("LONG", "SHORT"):
        return False, "REFUSED: direction must be LONG or SHORT"
    try:
        p = float(call["probability"])
    except (TypeError, ValueError):
        return False, "REFUSED: probability not numeric"
    if not MIN_PROB <= p <= MAX_PROB:
        return False, (f"REFUSED: probability {p} outside {MIN_PROB}-{MAX_PROB} -- below 50% is "
                       "a call the other way, above 95% is a tell that the model is not scoring "
                       "itself honestly")
    mech = str(call["mechanism"])
    if len(mech) < 25:
        return False, "REFUSED: mechanism too thin to be a mechanism"
    # A PATTERN is not a MECHANISM -- this is the 420/0 lesson enforced at write time.
    pattern_words = ("breakout", "support", "resistance", "trend line", "trendline",
                     "head and shoulders", "golden cross", "oversold", "overbought")
    if any(w in mech.lower() for w in pattern_words) and "because" not in mech.lower():
        return False, ("REFUSED: mechanism reads as a chart PATTERN, not a mechanism -- name who "
                       "is forced to do what and why (L1.16). Patterns are the class the desk's "
                       "420-tested/0-survived record already refuted")
    if len(str(call["falsifier"])) < 15:
        return False, "REFUSED: no real falsifier"
    if call["mechanism_class"] not in MECHANISMS:
        return False, (f"REFUSED: mechanism_class must be one of {MECHANISMS} -- free-text "
                       "mechanisms cannot be aggregated, so mechanism survival becomes "
                       "unmeasurable and weak families never get retired")
    if call["forced_participant"] not in PARTICIPANTS:
        return False, f"REFUSED: forced_participant must be one of {PARTICIPANTS}"
    if call["forced_participant"] == "NOBODY_FORCED":
        return False, ("REFUSED: no forced participant means no forced flow -- that is a VIEW, "
                       "not a mechanism, and views are what the 420/0 record already refuted")
    return True, "accepted"


def record_call(root: Path, call: dict[str, Any]) -> dict[str, Any]:
    """Append to the paper book AND log the forecast so L1.29 scores it automatically."""
    now = datetime.now(tz=UTC)
    row = {**call, "at": now.isoformat(),
           "resolve_by": (now + timedelta(hours=float(call.get("horizon_hours", 8)))).isoformat(),
           "paper": True}
    p = root / _BOOK
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    if call.get("action") == "CALL":
        try:
            from libs.self_improvement import forecast_calibration as fc
            fc.log_forecast(f"llm_trader:{now.isoformat()}", float(call["probability"]),
                            "discretionary", resolve_by=row["resolve_by"],
                            claim=f"{call['direction']} {call['symbol']}: {call['mechanism'][:120]}")
        except Exception as exc:                            # never lose the call
            row["calibration_log_error"] = str(exc)
    return row


def _ask_claude(prompt: str, timeout: int = 600) -> str:
    r = subprocess.run(
        ["bash", "-c",
         'source ops/brain_env.sh && brain_auth_check || exit 90 && '
         'claude --effort xhigh --append-system-prompt "$_DOCTRINE" -p "$0" '
         '--dangerously-skip-permissions', prompt],
        cwd=_ROOT, capture_output=True, text=True, timeout=timeout)
    return r.stdout or ""


def parse_call(raw: str) -> dict[str, Any] | None:
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except ValueError:
        return None


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", action="store_true", help="build the brief and stop")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    brief = build_brief(_ROOT)
    if args.brief:
        print(json.dumps(brief, indent=2))
        return 0

    raw = _ask_claude(_CALL_BRIEF.format(brief=json.dumps(brief, indent=1)[:6000],
                                         lo=MIN_PROB, hi=MAX_PROB,
                                         mechs=" | ".join(MECHANISMS),
                                         parts=" | ".join(PARTICIPANTS)))
    call = parse_call(raw)
    if call is None:
        state = {"status": "NO-CALL", "why": "model returned no parseable JSON (auth, quota, or "
                                             "a refusal) -- recorded, never treated as a PASS",
                 "at": datetime.now(tz=UTC).isoformat()}
    else:
        ok, why = validate_call(call)
        if not ok:
            state = {"status": "REFUSED", "why": why, "call": call,
                     "at": datetime.now(tz=UTC).isoformat()}
        else:
            row = record_call(_ROOT, call)
            state = {"status": call.get("action", "CALL"), "why": why, "call": row,
                     "at": row["at"]}
    (_ROOT / _STATE).write_text(json.dumps(state, indent=2), "utf-8")
    print(json.dumps(state, indent=2) if args.json else
          f"llm trader (R0122): {state['status']} -- {state['why']}")
    return 0                          # a refused call is a working filter, never a build failure


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/run_ngrok.py
```python
"""Run ngrok for the dashboard (:8080) + publish the URL. IDEMPOTENT single session, no thrash.

ngrok FREE allows only ONE simultaneous session, so this never runs two agents:
  * if a tunnel is ALREADY serving (local 4040 API returns a url), it does NOT launch a second --
    it just refreshes the heartbeat and returns (a peer agent is healthy);
  * otherwise it kills any stray ngrok.exe (clean the session), launches exactly ONE agent, and
    holds the heartbeat while it lives. It does NOT loop-relaunch internally (that was the bug that
    piled up agents and thrashed the session -> ERR_NGROK_3200). When ngrok dies, this exits and the
    watchdog respawns it (gated on heartbeat freshness), so there is always exactly one agent.

With a static/persistent account domain the URL never rotates.

    python scripts/run_ngrok.py
"""

from __future__ import annotations

import contextlib
import json
import subprocess
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

_NGROK = Path("tools/ngrok.exe")
_SECRETS = Path("data/secrets/ngrok.json")
_TUN = Path("web/tunnel.json")
_HB = Path("data/tunnel_heartbeat")
_HB_TICK = 30


def _public_url() -> str | None:
    try:
        raw = urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=5).read()
        for t in json.loads(raw).get("tunnels", []):
            u = t.get("public_url", "")
            if u.startswith("https"):
                return str(u)
    except Exception:
        return None
    return None


def _kill_stray_ngrok() -> None:
    """Kill every ngrok.exe -- free tier allows ONE session; strays thrash it offline."""
    with contextlib.suppress(Exception):
        subprocess.run(["taskkill", "/F", "/IM", "ngrok.exe"], capture_output=True, check=False)
    time.sleep(2)


def _beat() -> None:
    _HB.write_text(datetime.now(tz=UTC).isoformat(), "utf-8")


def _publish(url: str) -> None:
    _TUN.write_text(json.dumps({"url": url, "updated": datetime.now(tz=UTC).isoformat()}), "utf-8")


def main() -> None:
    # IDEMPOTENT: a healthy tunnel already up -> refresh heartbeat + URL, launch no 2nd agent
    # (covers a directly-started ngrok too -- we just monitor it and take over only if it dies).
    up = _public_url()
    if up:
        _publish(up)
        _beat()
        print(f"tunnel already up ({up}) -- monitoring, no second agent")
        return

    _kill_stray_ngrok()                                    # ensure a single clean session
    creds = json.loads(_SECRETS.read_text("utf-8")) if _SECRETS.exists() else {}
    args = [str(_NGROK), "http", "8080", "--log=stdout"]
    if creds.get("domain"):
        args.append("--url=" + str(creds["domain"]))
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    for _ in range(20):                                    # wait up to ~60s for the URL
        _beat()
        time.sleep(3)
        url = _public_url()
        if url:
            _publish(url)
            print(f"ngrok live: {url}")
            break

    while proc.poll() is None:                    # hold heartbeat while alive; NO relaunch
        _beat()
        time.sleep(_HB_TICK)
    print("ngrok exited -- watchdog will respawn")   # exit -> watchdog respawns one agent


if __name__ == "__main__":
    main()

```

### scripts/run_strategic_director.py
```python
#!/usr/bin/env python3
"""STRATEGIC DIRECTOR runner -- writes data/strategic_director.json (EXECUTION_QUEUE.md RANK 3).

A runtime ROLE, not a doctrine document: dossier assembled from artifacts that already exist ->
prompt -> ENFORCED output contract -> accepted recommendations written to the recommendation ledger,
where §41 forces every row to reach implemented / rejected / scheduled.

ACTIVATION-READY. Execution needs OpenRouter credit (the same 402 that blocks the panel and
llm_code_auditor.py). Everything except the network call is pure and tested, so --dry-run proves the
entire path today for free, and no redesign is needed when credit lands. --dry-run is the automatic
default when no key file exists.

    python scripts/run_strategic_director.py --dry-run     # dossier + prompt + contract, no spend
    python scripts/run_strategic_director.py               # live (needs data/secrets/llm_panel.json)
    python scripts/run_strategic_director.py --from-file r.json --ledger   # parse + ledger a response
"""
from __future__ import annotations

import argparse
import json
import ssl
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research.strategic_director import (  # noqa: E402
    assemble_dossier,
    build_prompt,
    director_report,
    parse_recommendations,
    to_ledger_commands,
)

OUT = ROOT / "data/strategic_director.json"
KEYS = ROOT / "data/secrets/llm_panel.json"
# overridable; any reasoning model satisfies the contract -- but the DEFAULT is deliberately a
# GPT model, not a Claude one (principal order 2026-07-31, and it was the design intent from the
# start: "GPT Strategic Director"). Every other reasoning organ on this desk is Claude, so a
# Claude strategist re-reads the desk with the same eyes that built it -- same priors, same blind
# spots, zero independence. The strategist exists precisely to be the OTHER model family: the
# same reason the v8 8.2 bar demands a second-model-family fuzz report rather than more of the
# first family's opinion. gpt-9 is the flagship seat the panel roster already vets.
MODEL = "openai/gpt-9"
_CTX = ssl.create_default_context()


def _ask(prompt: str, model: str, timeout: float = 360.0) -> tuple[str, str]:
    """(response, error). Never raises -- a dead provider must not crash the cycle."""
    try:
        providers = json.loads(KEYS.read_text("utf-8"))["providers"]
    except (OSError, ValueError, KeyError) as e:
        return "", f"key file unreadable: {e}"
    for prov in providers:
        base, key = prov.get("base_url", ""), prov.get("key", "")
        if not base or not key:
            continue
        body = json.dumps({
            "model": model, "max_tokens": 8000, "temperature": 0.4,
            "reasoning": {"effort": "high"},
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request(
            base.rstrip("/") + "/chat/completions", data=body, method="POST",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
                doc = json.loads(r.read())
            msg = doc["choices"][0]["message"]
            return str(msg.get("content") or msg.get("reasoning") or ""), ""
        except Exception as e:
            last = f"{type(e).__name__}: {str(e)[:120]}"
            continue
    return "", last if providers else "no providers configured"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="assemble + build the prompt, spend nothing (default without a key)")
    ap.add_argument("--from-file", type=Path, default=None,
                    help="parse a response already captured (manual mode / replay)")
    ap.add_argument("--ledger", action="store_true",
                    help="write accepted recommendations to the recommendation ledger")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    dossier = assemble_dossier(ROOT)
    prompt = build_prompt(dossier)

    raw, err, mode = "", "", "dry-run"
    if a.from_file is not None:
        try:
            raw, mode = a.from_file.read_text("utf-8"), "replay"
        except OSError as e:
            print(f"strategic-director: cannot read {a.from_file}: {e}", file=sys.stderr)
            return 2
    elif not a.dry_run:
        if not KEYS.exists():
            # NOT an error: the designed state until credit lands. Prove the path, spend nothing.
            err, mode = "no data/secrets/llm_panel.json -- dry-run (activation-ready)", "dry-run"
        else:
            raw, err = _ask(prompt, a.model)
            mode = "live" if raw else "blocked"

    payload: dict[str, object] = {
        "generated": datetime.now(tz=UTC).isoformat(), "mode": mode, "model": a.model,
        "dossier_summary": dossier.summary(),
        "dossier_missing": dossier.missing,
        "dormant_count": dossier.dormant_count,
        "prompt_chars": len(prompt),
        "error": err,
    }

    if raw:
        res = parse_recommendations(raw, dossier)
        payload["report"] = director_report(res, dossier)
        payload["status"] = "ACTIVE"
        ledgered = 0
        if a.ledger:
            for argv_add in to_ledger_commands(res):
                r = subprocess.run(
                    [sys.executable, str(ROOT / "scripts/recommendations.py"), *argv_add],
                    capture_output=True, text=True, check=False, cwd=str(ROOT))
                ledgered += int(r.returncode == 0)
        payload["ledgered"] = ledgered
    else:
        payload["status"] = "BLOCKED" if mode == "blocked" else "READY"
        # The contract and dossier are still emitted, so the artifact PROVES activation-readiness
        # rather than asserting it -- and a reviewer can check the prompt without paying for a run.
        payload["report"] = director_report(parse_recommendations("[]", dossier), dossier)
        payload["prompt"] = prompt

    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=1, default=str), "utf-8")
    tmp.replace(OUT)

    if a.json:
        print(json.dumps(payload, indent=1, default=str))
        return 0
    print(f"strategic-director | {payload['status']} ({mode})")
    print(f"  dossier: {dossier.summary()}")
    if dossier.missing:
        print(f"  MISSING: {', '.join(dossier.missing)}")
    if err:
        print(f"  {err}")
    rep = payload.get("report")
    if isinstance(rep, dict):
        acc, rej = rep.get("accepted", []), rep.get("rejected", [])
        if acc or rej:
            print(f"  {len(acc)} accepted, {len(rej)} rejected by the output contract")
            for r in acc:
                print(f"    [{r['kind']}] {r['title']}")
            for r in rej:
                print(f"    REJECTED {r['title']}: {r['reason'][:100]}")
    if payload.get("ledgered"):
        print(f"  {payload['ledgered']} recommendation(s) ledgered -- §41 now owes a disposition")
    print(f"\n-> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/run_tunnel.py
```python
"""Public tunnel: expose the local dashboard at a free https://<random>.trycloudflare.com URL.

This makes the link work for ANYONE you send it to (not just devices on your Wi-Fi). Runs the
portable cloudflared (no account, no admin), parses the assigned URL, and writes it to
web/tunnel.json so the dashboard header shows the current public link. ONLY read-only performance
data is served (web/ has no API keys/secrets). A heartbeat thread keeps liveness fresh so the
watchdog won't needlessly restart it (a restart changes the random URL). To stop sharing publicly:
kill cloudflared. The quick-tunnel URL changes on restart -- always read the current one from
web/tunnel.json or the dashboard.

    python scripts/run_tunnel.py
"""

from __future__ import annotations

import json
import re
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_CF = _ROOT / "tools" / "cloudflared.exe"
_OUT = _ROOT / "web" / "tunnel.json"
_HB = _ROOT / "data" / "tunnel_heartbeat"
_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def _write(url: str | None, status: str) -> None:
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                                "url": url, "status": status}, indent=2), "utf-8")


def _beat(proc: subprocess.Popen[str]) -> None:
    _HB.parent.mkdir(parents=True, exist_ok=True)
    while proc.poll() is None:
        _HB.write_text(str(time.time()), "utf-8")
        time.sleep(15)


def _run_once() -> None:
    proc = subprocess.Popen(
        [str(_CF), "tunnel", "--url", "http://localhost:8080", "--no-autoupdate"],
        cwd=str(_ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    threading.Thread(target=_beat, args=(proc,), daemon=True).start()
    url: str | None = None
    assert proc.stdout is not None
    for line in proc.stdout:
        m = _URL_RE.search(line)
        if m and not url:
            url = m.group(0)
            _write(url, "up")
            print("PUBLIC URL:", url, flush=True)
    proc.wait()


def main() -> None:
    if not _CF.exists():
        raise SystemExit("cloudflared not found at tools/cloudflared.exe")
    while True:                              # self-heal: quick-tunnels drop; relaunch on exit
        _write(None, "starting")
        try:
            _run_once()
        except Exception as e:
            print(f"tunnel error: {e!r}"[:120], flush=True)
        _write(None, "reconnecting")
        time.sleep(5)


if __name__ == "__main__":
    main()

```

### scripts/screen_smart_dumb.py
```python
"""ELITE-TRADER INTELLIGENCE -- the falsifiable KERNEL of the 26-layer spec.

The spec's premise: skilled traders carry extractable predictive information. Rather than build
26 subsystems on an unproven premise, this tests the premise itself with the cheapest decisive
experiment the desk can run TODAY.

ANGLE-14: the desk ALREADY collects globalLongShortAccountRatio (ALL accounts = the RETAIL CROWD,
314 symbols/day) and already DSR-KILLED ls_contrarian on it. What it does NOT have is Binance's
TOP-TRADER positioning -- topLongShortPositionRatio / topLongShortAccountRatio -- i.e. the
"elite" cohort. Probe confirms they genuinely diverge (retail 66.8% long vs top 55.1% long).

Three signals screened at 4h granularity (~83d):
  1. elite_pos      -- top-trader POSITION ratio (size-weighted elite conviction)
  2. elite_acct     -- top-trader ACCOUNT ratio (elite headcount)
  3. smart_dumb_div -- elite MINUS retail (the smart-money-vs-dumb-money divergence; the single
                      most direct test of "do skilled traders lead the crowd?")

Hardened harness (de-contam + SUSPECT-LOOKAHEAD rails). Stage-A only, zero promotion authority.
Run from repo root."""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from libs.research.axis_screen import stage_a_screen

_F = "https://fapi.binance.com/futures/data"
_K = "https://fapi.binance.com/fapi/v1/klines"
SYMS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
PERIOD, LIMIT = "4h", 500


def _get(url: str, timeout: int = 30):
    req = urllib.request.Request(url, headers={"User-Agent": "quant-elite/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _ratio(endpoint: str, sym: str) -> dict[int, float]:
    d = _get(f"{_F}/{endpoint}?symbol={sym}&period={PERIOD}&limit={LIMIT}")
    return {int(x["timestamp"]): float(x["longAccount"]) for x in d} if isinstance(d, list) else {}


def _klines(sym: str) -> dict[int, float]:
    d = _get(f"{_K}?symbol={sym}&interval={PERIOD}&limit={LIMIT}")
    return {int(r[0]): float(r[4]) for r in d} if isinstance(d, list) else {}


def main() -> None:
    results, pooled = [], {}
    for sym in SYMS:
        try:
            elite_pos = _ratio("topLongShortPositionRatio", sym)
            elite_acc = _ratio("topLongShortAccountRatio", sym)
            retail = _ratio("globalLongShortAccountRatio", sym)
            px = _klines(sym)
        except Exception as e:  # blind-except intentional (BLE001)
            print(f"{sym:9s} DATA-BLOCKED ({type(e).__name__})")
            continue
        ts = sorted(set(elite_pos) & set(elite_acc) & set(retail) & set(px))
        if len(ts) < 90:
            print(f"{sym:9s} thin ({len(ts)})")
            continue
        close = np.array([px[t] for t in ts])
        ret = np.zeros(len(close))
        ret[1:] = close[1:] / close[:-1] - 1.0
        sigs = {"elite_pos": np.array([elite_pos[t] for t in ts]),
                "elite_acct": np.array([elite_acc[t] for t in ts]),
                "smart_dumb_div": np.array([elite_pos[t] - retail[t] for t in ts]),
                "retail_baseline": np.array([retail[t] for t in ts])}
        for name, sig in sigs.items():
            r = stage_a_screen(sig, ret, name=f"{sym}:{name}", zwin=20)
            r["symbol"], r["signal"] = sym, name
            results.append(r)
            pooled.setdefault(name, []).append((r.get("ic", 0.0), r.get("sharpe_momentum", 0.0),
                                                r.get("sharpe_reversal", 0.0)))
        print(f"{sym:9s} n={len(ts)} | " + " | ".join(
            f"{k}: IC {next(x for x in results if x['symbol']==sym and x['signal']==k).get('ic'):+.3f}"
            for k in sigs))

    print("\n=== POOLED across symbols (the honest read: N = symbols, not observations) ===")
    for name, vals in pooled.items():
        ics = np.array([v[0] for v in vals])
        mom = np.array([v[1] for v in vals])
        rev = np.array([v[2] for v in vals])
        t = float(ics.mean() / (ics.std() / np.sqrt(len(ics)))) if len(ics) > 1 and ics.std() else 0.0
        print(f"  {name:18s} mean IC {ics.mean():+.4f} (t {t:+.2f}, n={len(ics)}) | "
              f"mean momSh {mom.mean():+.2f} | mean revSh {rev.mean():+.2f}")
    surv = [r["name"] for r in results if r["verdict"] == "SCREEN-INTERESTING"]
    print(f"\nper-symbol SCREEN-INTERESTING: {len(surv)}/{len(results)} -> {surv[:8]}")
    Path("data/elite_trader_screen.json").write_text(json.dumps(
        {"updated": datetime.now(tz=UTC).isoformat(), "period": PERIOD,
         "results": results}, indent=1), "utf-8")


if __name__ == "__main__":
    main()

```

### scripts/signal_halflife.py
```python
"""SIGNAL HALF-LIFE / DECAY TRACKER (Level-5 layer, instrumentation-first).

WHY BUILD IT BEFORE THERE IS A SURVIVOR: a decay curve needs a TIME SERIES THAT STARTS NOW. If
this waits until a signal is confirmed, the pre-confirmation baseline is permanently lost -- you
cannot retroactively record what you never instrumented. Recording is cheap and irreversible if
skipped; MODEL-FITTING is what must wait for evidence. So this appends one honest observation per
run from day zero and refuses to fit a decay curve until it has enough points.

The graveyard handles DEATH (a signal that failed validation). This handles AGEING -- a signal
that WORKED and is losing potency, which is invisible to a pass/fail gate and is how live books
quietly bleed. Tracks per signal: rolling IC over successive windows, its trend, and a half-life
estimate once enough history exists.

Appends to data/signal_halflife.jsonl (one row per signal per run). Read-only w.r.t. everything
else. Run from repo root, ideally on the daily cadence.
"""
from __future__ import annotations

import contextlib
import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from libs.research.upbit_data import upbit_daily_close_keyed

SERIES = Path("data/signal_halflife.jsonl")
REPORT = Path("data/signal_halflife_report.json")
MIN_POINTS_TO_FIT = 8          # refuse to estimate a half-life below this


def _get(u, t=40):
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(u, headers={"User-Agent": "q/1.0"}), timeout=t).read().decode())


def binance():
    rows = _get("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=900")
    return {datetime.fromtimestamp(int(r[0]) / 1000, tz=UTC).date().isoformat(): float(r[4])
            for r in rows}


def stables():
    d = _get("https://stablecoins.llama.fi/stablecoincharts/all")
    o = {}
    for x in d:
        v = x.get("totalCirculatingUSD") or {}
        p = v.get("peggedUSD") if isinstance(v, dict) else None
        if p is not None:
            o[datetime.fromtimestamp(int(x["date"]), tz=UTC).date().isoformat()] = float(p)
    return o


def kimchi(gb):
    # R0060 single source: inline keying here used the OPEN stamp (~15h look-ahead) -- this is
    # the copy that printed a contaminated "kimchi STRENGTHENING" row during the refutation audit.
    kb = upbit_daily_close_keyed()
    res = _get("https://query1.finance.yahoo.com/v8/finance/chart/KRW=X?interval=1d&range=300d"
               )["chart"]["result"][0]
    fx = {datetime.fromtimestamp(int(t), tz=UTC).date().isoformat(): float(c)
          for t, c in zip(res["timestamp"], res["indicators"]["quote"][0]["close"], strict=False) if c}
    return {d: kb[d] / fx[d] / gb[d] - 1.0 for d in (set(kb) & set(fx) & set(gb))}


def rolling_ic(sig: dict, gb: dict, win: int = 60, step: int = 20):
    """IC computed over successive non-overlapping-ish windows -> the ageing curve."""
    dates = sorted(set(sig) & set(gb))
    if len(dates) < win + 25:
        return []
    s = np.array([sig[d] for d in dates])
    px = np.array([gb[d] for d in dates])
    ret = np.zeros(len(px))
    ret[1:] = px[1:] / px[:-1] - 1.0
    fwd = np.roll(ret, -1)
    z = np.zeros(len(s))
    for t in range(20, len(s)):
        w = s[t - 20:t]
        sd = w.std()
        z[t] = (s[t] - w.mean()) / sd if sd > 0 else 0.0
    out = []
    for a in range(20, len(s) - win - 1, step):
        zv, fv = z[a:a + win], fwd[a:a + win]
        if zv.std() and fv.std():
            out.append({"end_date": dates[a + win], "ic": float(np.corrcoef(zv, fv)[0, 1])})
    return out


def half_life(ics: list[float]) -> float | None:
    """Fit |IC| decay: |IC_t| ~ |IC_0| * exp(-t/tau). Returns tau in windows, None if not decaying."""
    y = np.array([abs(v) for v in ics])
    y = np.where(y < 1e-4, 1e-4, y)
    x = np.arange(len(y), dtype=float)
    b, _a = np.polyfit(x, np.log(y), 1)
    if b >= -1e-6:
        return None                      # flat or improving -- no decay to report
    return float(-np.log(2) / b)


def main() -> None:
    gb = binance()
    sigs = {}
    with contextlib.suppress(Exception):
        sigs["stablecoin_supply"] = stables()
    with contextlib.suppress(Exception):
        sigs["kimchi_premium"] = kimchi(gb)

    today = datetime.now(tz=UTC).date().isoformat()
    rows, report = [], []
    for name, s in sigs.items():
        curve = rolling_ic(s, gb)
        if not curve:
            print(f"{name:22s} insufficient history for a curve")
            continue
        ics = [c["ic"] for c in curve]
        recent = float(np.mean(ics[-2:])) if len(ics) >= 2 else ics[-1]
        early = float(np.mean(ics[:2])) if len(ics) >= 2 else ics[0]
        trend = recent - early
        hl = half_life(ics) if len(ics) >= MIN_POINTS_TO_FIT else None
        status = ("AGEING" if trend < -0.03 else
                  "STRENGTHENING" if trend > 0.03 else "STABLE")
        rows.append({"date": today, "signal": name, "n_windows": len(ics),
                     "ic_early": round(early, 4), "ic_recent": round(recent, 4),
                     "trend": round(trend, 4), "half_life_windows": hl, "status": status,
                     "curve": [round(v, 4) for v in ics]})
        report.append(rows[-1])
        hl_s = f"{hl:.1f} windows" if hl else ("n/a (not decaying)" if len(ics) >= MIN_POINTS_TO_FIT
                                               else f"n/a (<{MIN_POINTS_TO_FIT} pts)")
        print(f"{name:22s} windows={len(ics):2d} | IC early {early:+.4f} -> recent {recent:+.4f} "
              f"| trend {trend:+.4f} | half-life {hl_s} | {status}")
        print(f"{'':22s} curve: " + " ".join(f"{v:+.3f}" for v in ics))

    if rows:
        with SERIES.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps({k: v for k, v in r.items() if k != "curve"}) + "\n")
        REPORT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                                      "signals": report}, indent=1), "utf-8")
    print(f"\nappended {len(rows)} observations -> {SERIES}")
    print("NOTE: ageing is invisible to a pass/fail gate -- a signal can pass validation and still")
    print("      be losing potency. Half-life is only FIT once >=8 windows exist; until then the")
    print("      tracker records and refuses to estimate.")


if __name__ == "__main__":
    main()

```
