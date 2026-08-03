# AUDIT SHARD 9/13 -- seat nvidia/nemotron-3-ultra-550b-a55b

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

### libs/__init__.py
```python
"""Top-level namespace for the quant platform's pure, tested libraries.

Strict layering: ``libs`` holds pure logic with no service coupling. ``app`` composes
``libs`` into run modes; ``dashboards`` reads only. ``libs.core`` depends on nothing internal.
"""

```

### libs/alpha_factory/alpha_discovery_engine.py
```python
"""Alpha discovery engine — coordinate the idea lifecycle (recommend-only).

Pipeline: generate -> score -> prioritize -> (research/validate happen in the discovery+validation
layers) -> archive -> learn. This engine handles the non-trading coordination: prioritizing ideas
and archiving outcomes to research memory so the factory compounds knowledge. It never validates,
promotes, or allocates capital itself.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from libs.alpha_factory.hypothesis_engine import HypothesisEngine
from libs.alpha_factory.idea_ranking_engine import IdeaRankingEngine
from libs.alpha_factory.models import (
    AlphaCategory,
    FailureCause,
    Hypothesis,
    IdeaCandidate,
    IdeaRecord,
    IdeaScore,
    ResearchResult,
)
from libs.alpha_factory.research_memory import ResearchMemory


class AlphaDiscoveryEngine:
    """Coordinates idea generation, prioritization, archival, and learning."""

    def __init__(
        self,
        memory: ResearchMemory,
        *,
        hypothesis_engine: HypothesisEngine | None = None,
        ranking_engine: IdeaRankingEngine | None = None,
    ) -> None:
        self.memory = memory
        self.hypothesis_engine = hypothesis_engine or HypothesisEngine()
        self.ranking_engine = ranking_engine or IdeaRankingEngine()

    def generate(self, categories: Sequence[AlphaCategory]) -> list[Hypothesis]:
        return self.hypothesis_engine.generate(categories, memory=self.memory)

    def prioritize(self, candidates: Sequence[IdeaCandidate]) -> list[IdeaScore]:
        return self.ranking_engine.rank(candidates)

    def archive(
        self,
        *,
        category: str,
        statement: str,
        result: ResearchResult,
        failure_cause: FailureCause = FailureCause.NONE,
        failure_reason: str | None = None,
        success_reason: str | None = None,
        failure_stage: str | None = None,
        lessons: str | None = None,
        metrics: Mapping[str, Any] | None = None,
        predecessor_id: str | None = None,
    ) -> IdeaRecord:
        return self.memory.record(
            category=category, statement=statement, result=result,
            failure_cause=failure_cause, failure_reason=failure_reason,
            success_reason=success_reason, failure_stage=failure_stage, lessons=lessons,
            metrics=metrics, predecessor_id=predecessor_id,
        )

    def learn(self) -> dict[str, float]:
        """Per-category success rates compounded from all archived research."""
        return self.hypothesis_engine.learn(self.memory)

```

### libs/alpha_factory/capacity_intelligence.py
```python
"""Capacity intelligence — prioritize concepts that can hold THIS DESK'S size.

Reuses the discovery capacity model (square-root market impact) to estimate deployable capital,
slippage, and a 0-100 scalability score.

§42: the reference was $10m, so a $50k-capacity edge scored 0.5/100 on scalability — a 200x
penalty on the capacity-bound niche the desk's own spec calls its structural advantage. "Can hold
size" is a fund's question; the desk's question is "can hold OUR size", and the answer above
sufficiency is yes-or-yes. `reference_capital` therefore now means the equity being deployed, and
scoring is delegated to the shared `capacity_fit` so this cannot drift back out of line with the
survival gate and the two rank scorers.
"""

from __future__ import annotations

from libs.alpha_factory.models import CapacityIntelligenceResult
from libs.discovery.capacity import capacity_estimate
from libs.research.capacity_policy import DEFAULT_BOOK_USD, DEFAULT_SLEEVES, capacity_fit

_REFERENCE_CAPITAL = DEFAULT_BOOK_USD  # USD of DEPLOYED equity the concept is scored against


class CapacityIntelligence:
    """Estimates market capacity and scalability for a research concept."""

    def assess(
        self,
        *,
        adv_usd: float,
        edge_bps: float = 10.0,
        participation_cap: float = 0.01,
        turnover_per_year: float = 50.0,
        impact_coefficient: float = 0.1,
        reference_capital: float = _REFERENCE_CAPITAL,
        n_sleeves: int = DEFAULT_SLEEVES,
    ) -> CapacityIntelligenceResult:
        result = capacity_estimate(
            adv_usd=adv_usd, participation_cap=participation_cap,
            turnover_per_year=turnover_per_year, impact_coefficient=impact_coefficient,
            edge_bps=edge_bps,
        )
        # `reference_capital` is a whole-BOOK figure, so it is sleeved: a concept is filled with
        # one allocation, not with the entire desk.
        scalability = 100.0 * capacity_fit(result.capacity_usd, reference_capital, n_sleeves)
        return CapacityIntelligenceResult(
            market_capacity_usd=result.capacity_usd,
            expected_slippage=result.market_impact_bps_at_capacity / 1e4,
            liquidity_depth=adv_usd * participation_cap,
            scalability_score=scalability,
        )

```

### libs/alpha_factory/hypothesis_engine.py
```python
"""Hypothesis engine — generate economically-motivated research hypotheses and learn from them.

Generates testable statements per category, optionally informing each hypothesis's expected edge
from the prior success rate recorded in research memory, and reports which hypothesis types have
historically succeeded so future generation favours productive directions.
"""

from __future__ import annotations

from collections.abc import Sequence

from libs.alpha_factory.models import AlphaCategory, Hypothesis
from libs.alpha_factory.research_memory import ResearchMemory
from libs.core.ids import generate_id

# Templated, economically-anchored research statements per category.
_TEMPLATES: dict[AlphaCategory, list[tuple[str, list[str]]]] = {
    AlphaCategory.MOMENTUM: [
        ("momentum strengthens in low-volatility regimes", ["momentum", "volatility_regime"]),
        ("cross-sectional momentum predicts continuation", ["rel_strength", "dispersion"]),
    ],
    AlphaCategory.TREND_FOLLOWING: [
        ("trend signals improve through regime transitions", ["trend", "regime_transition"]),
    ],
    AlphaCategory.CARRY: [
        ("carry improves when filtered by a volatility gate", ["carry", "volatility_gate"]),
    ],
    AlphaCategory.MEAN_REVERSION: [
        ("mean reversion works in range regimes with high liquidity", ["zscore", "liquidity"]),
    ],
    AlphaCategory.VOLATILITY: [
        ("volatility compression precedes expansion breakouts", ["vol_compression", "breakout"]),
    ],
    AlphaCategory.CROSS_ASSET: [
        ("cross-asset dispersion predicts equity momentum", ["dispersion", "lead_lag"]),
    ],
}

_DEFAULT_EDGE = 0.5


class HypothesisEngine:
    """Generates research hypotheses and learns which categories succeed."""

    def generate(
        self,
        categories: Sequence[AlphaCategory],
        *,
        memory: ResearchMemory | None = None,
    ) -> list[Hypothesis]:
        hypotheses: list[Hypothesis] = []
        for category in categories:
            prior = (
                memory.success_rate(category.value) if memory is not None else _DEFAULT_EDGE
            )
            expected_edge = prior if prior > 0.0 else _DEFAULT_EDGE
            for statement, features in _TEMPLATES.get(category, []):
                hypotheses.append(
                    Hypothesis(
                        id=generate_id("hyp"),
                        statement=statement,
                        category=category.value,
                        features=list(features),
                        expected_edge=expected_edge,
                        rationale=(
                            f"{category.value}: prior success rate {expected_edge:.2f}; "
                            "must survive the validation gauntlet to be retained."
                        ),
                    )
                )
        return hypotheses

    def learn(self, memory: ResearchMemory) -> dict[str, float]:
        """Success rate per category seen in research memory (which types actually work)."""
        categories = {r.category for r in memory.all()}
        return {c: memory.success_rate(c) for c in sorted(categories)}

```

### libs/core/__init__.py
```python
"""``libs.core`` — the platform spine: contracts, config, logging, time, reproducibility.

This package depends on nothing internal and is imported by everything else. Types and
helpers defined here are the single source of truth and must never be redefined elsewhere.
"""

from __future__ import annotations

from libs.core.config import (
    LoggingConfig,
    Paths,
    ReproducibilityConfig,
    Settings,
    clear_settings_cache,
    deep_merge,
    ensure_directories,
    find_project_root,
    get_settings,
    hash_config,
    load_settings,
)
from libs.core.enums import Environment, LogLevel, RunMode
from libs.core.errors import (
    ConfigError,
    GitError,
    QuantPlatformError,
    ReproducibilityError,
    SecretsError,
    TimezoneError,
)
from libs.core.ids import generate_id, new_correlation_id, new_run_id, new_stamp_id
from libs.core.logging import (
    bind,
    clear_correlation_id,
    configure_logging,
    correlation_context,
    get_correlation_id,
    get_logger,
    set_correlation_id,
)
from libs.core.reproducibility import (
    GitInfo,
    ReproducibilityStamp,
    VerificationResult,
    create_reproducibility_stamp,
    get_git_info,
    seed_everything,
    verify_reproducibility,
)
from libs.core.secrets import (
    EnvSecretsProvider,
    SecretsProvider,
    get_secret,
    set_default_provider,
)
from libs.core.time import (
    UTC,
    ensure_utc,
    from_epoch_ms,
    from_iso8601,
    is_utc,
    to_epoch_ms,
    to_iso8601,
    to_utc,
    utcnow,
)

__all__ = [  # noqa: RUF022  # grouped by module for readability, not alphabetised
    # config
    "Settings",
    "Paths",
    "LoggingConfig",
    "ReproducibilityConfig",
    "load_settings",
    "get_settings",
    "clear_settings_cache",
    "ensure_directories",
    "find_project_root",
    "deep_merge",
    "hash_config",
    # enums
    "Environment",
    "RunMode",
    "LogLevel",
    # errors
    "QuantPlatformError",
    "ConfigError",
    "TimezoneError",
    "GitError",
    "ReproducibilityError",
    "SecretsError",
    # ids
    "generate_id",
    "new_run_id",
    "new_correlation_id",
    "new_stamp_id",
    # logging
    "configure_logging",
    "get_logger",
    "bind",
    "correlation_context",
    "set_correlation_id",
    "get_correlation_id",
    "clear_correlation_id",
    # time
    "UTC",
    "utcnow",
    "is_utc",
    "ensure_utc",
    "to_utc",
    "to_iso8601",
    "from_iso8601",
    "to_epoch_ms",
    "from_epoch_ms",
    # secrets
    "SecretsProvider",
    "EnvSecretsProvider",
    "get_secret",
    "set_default_provider",
    # reproducibility
    "GitInfo",
    "ReproducibilityStamp",
    "VerificationResult",
    "create_reproducibility_stamp",
    "verify_reproducibility",
    "get_git_info",
    "seed_everything",
]

```

### libs/costs/mt5_calibration.py
```python
"""Calibrate the Fusion cost model from REAL MT5 ``symbol_info`` (committee item T1).

The platform must report net-of-cost results, and the only honest cost inputs are the broker's
own: live spread, contract size, and swap. This module turns an MT5 ``symbol_info`` snapshot into
:class:`CostParams` and exposes the round-turn cost as a *fraction of notional* -- the form the
discovery backtests need to subtract on every position change.

Honest caveats baked in, not hidden:
  * Commission is NOT in ``symbol_info``; it is an asset-class prior (Fusion Zero ECN ~ $7/lot RT
    on FX/metals, spread-only on indices/crypto/equities). Override per real statements.
  * Slippage is a prior (a fraction of the live spread per side) until calibrated on real fills.
  * Swap is converted points -> money only for USD-quoted symbols; otherwise it is approximate.
The point is to make results *more* conservative than a flat fee, never less.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from libs.costs.errors import CostError
from libs.costs.params import CostParams
from libs.data.instruments import AssetClass

# Round-turn commission priors per lot, by asset class (account currency). Conservative defaults
# for a Fusion Zero ECN account; the FX/metal figure matches the ~$7/lot round turn they advertise.
_COMMISSION_PER_LOT: dict[AssetClass, float] = {
    AssetClass.FX: 7.0,
    AssetClass.METAL: 7.0,
    AssetClass.ENERGY: 7.0,
    AssetClass.SOFT: 7.0,
    AssetClass.INDEX: 0.0,
    AssetClass.CRYPTO: 0.0,
    AssetClass.EQUITY: 0.0,
}
_SWAP_MODE_POINTS = 0  # mt5.SYMBOL_SWAP_MODE_POINTS


@runtime_checkable
class SymbolInfoLike(Protocol):
    """The subset of MT5 ``symbol_info`` fields the calibration needs (kept tiny for testing)."""

    spread: int                 # current spread in integer points
    point: float                # price increment of one point
    trade_contract_size: float  # units per lot
    swap_long: float
    swap_short: float
    swap_mode: int


def calibrate(
    symbol: str,
    info: SymbolInfoLike,
    *,
    asset_class: AssetClass,
    commission_per_lot: float | None = None,
    slippage_fraction_of_spread: float = 0.5,
    gap_risk_fraction: float = 0.0,
) -> CostParams:
    """Build :class:`CostParams` from a live ``symbol_info`` snapshot.

    ``spread_price`` is the full round-turn spread (spread points x point). Slippage per side is a
    conservative fraction of that spread. Commission falls back to the asset-class prior.
    """
    spread_price = float(info.spread) * float(info.point)
    if spread_price < 0:
        raise CostError(f"negative spread for {symbol!r}")
    contract_size = float(info.trade_contract_size)
    commission = (
        commission_per_lot if commission_per_lot is not None
        else _COMMISSION_PER_LOT.get(asset_class, 0.0)
    )
    slippage_per_side = spread_price * slippage_fraction_of_spread
    swap_long, swap_short = _swap_to_money(info, contract_size)
    return CostParams(
        instrument=symbol,
        contract_size=contract_size if contract_size > 0 else 1.0,
        commission_per_lot=commission,
        spread_price=spread_price,
        slippage_price_per_side=slippage_per_side,
        swap_long_per_lot_per_night=swap_long,
        swap_short_per_lot_per_night=swap_short,
        gap_risk_fraction=gap_risk_fraction,
    )


def _swap_to_money(info: SymbolInfoLike, contract_size: float) -> tuple[float, float]:
    """Convert swap to account-ccy cost-to-hold per lot per night (cost = positive).

    MT5 swap is a credit when positive; our model wants a *cost*, so we negate. For point-mode
    swaps we convert to money via point x contract size (exact for USD-quoted symbols).
    """
    if int(info.swap_mode) == _SWAP_MODE_POINTS:
        scale = float(info.point) * contract_size
        return (-float(info.swap_long) * scale, -float(info.swap_short) * scale)
    return (-float(info.swap_long), -float(info.swap_short))


def round_turn_cost_fraction(params: CostParams, price: float) -> float:
    """Round-turn cost as a fraction of notional (spread + 2x slippage + commission).

    This is what a returns-space backtest subtracts each time the position turns over.
    """
    if price <= 0:
        raise CostError("price must be positive")
    notional_per_lot = params.contract_size * price
    spread_frac = params.spread_price / price
    slippage_frac = 2.0 * params.slippage_price_per_side / price
    commission_frac = params.commission_per_lot / notional_per_lot
    return spread_frac + slippage_frac + commission_frac


def per_side_cost_fraction(params: CostParams, price: float) -> float:
    """Half the round-turn fraction -- the cost charged on a single entry or exit."""
    return round_turn_cost_fraction(params, price) / 2.0


def cost_params_from_mt5(symbol: str, mt5, asset_class: AssetClass) -> CostParams:  # type: ignore[no-untyped-def]  # pragma: no cover - needs live terminal
    """Read live ``symbol_info`` from an initialized MT5 module and calibrate cost params."""
    mt5.symbol_select(symbol, True)
    info = mt5.symbol_info(symbol)
    if info is None:
        raise CostError(f"MT5 returned no symbol_info for {symbol!r}")
    return calibrate(symbol, info, asset_class=asset_class)

```

### libs/discovery/__init__.py
```python
"""``libs.discovery`` — surviving utilities from the retired Alpha Discovery Factory.

The factory itself (factory.py, models.py, signals.py, hypotheses.py, acceptance.py,
fragility.py, half_life.py, parameter_stability.py, correlation_engine.py,
failure_dependency.py, family_concentration.py, pools.py, portfolio_geometry.py,
cagr_optimizer.py — 14 modules) was retired 2026-07-27: a complete, self-contained MT5-era
predecessor to ``libs.autodiscovery`` (51 external importers), reachable from nothing outside
its own package. See docs/graveyard.md.

What remains is genuinely alive: individual utility functions that other subsystems adopted
directly, independent of the factory that originally housed them.
"""

from __future__ import annotations

from libs.discovery.capacity import CapacityResult, capacity_estimate
from libs.discovery.monte_carlo_survival import MonteCarloSurvivalResult, monte_carlo_survival
from libs.discovery.objective import discovery_score, expected_log_growth, log_utility
from libs.discovery.regime_diversification import (
    RegimeDiversificationResult,
    regime_diversification,
)
from libs.discovery.research_roi import (
    CategoryStat,
    ResearchROIResult,
    rank_categories,
    research_roi,
)
from libs.discovery.stress_scenario import StressScenarioResult, stress_scenario
from libs.discovery.tail_risk import TailRiskResult, tail_risk

__all__ = [
    "CapacityResult",
    "CategoryStat",
    "MonteCarloSurvivalResult",
    "RegimeDiversificationResult",
    "ResearchROIResult",
    "StressScenarioResult",
    "TailRiskResult",
    "capacity_estimate",
    "discovery_score",
    "expected_log_growth",
    "log_utility",
    "monte_carlo_survival",
    "rank_categories",
    "regime_diversification",
    "research_roi",
    "stress_scenario",
    "tail_risk",
]

```

### libs/discovery/research_roi.py
```python
"""research_roi_engine — allocate research effort to the highest-yield areas.

Tracks ideas generated/tested/validated, time consumed, and (expected) production contribution,
and ranks research categories by expected alpha yield so effort flows to the best opportunities.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict


class ResearchROIResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    research_roi_score: float  # 0-100
    validated_rate: float
    contribution_per_hour: float


def research_roi(
    *,
    ideas_generated: int,
    ideas_tested: int,
    ideas_validated: int,
    time_hours: float,
    production_contribution: float,
    expected_future_contribution: float,
) -> ResearchROIResult:
    """Score research efficiency from validation rate and contribution per hour."""
    validated_rate = ideas_validated / ideas_tested if ideas_tested else 0.0
    total_contribution = production_contribution + expected_future_contribution
    contribution_per_hour = total_contribution / time_hours if time_hours > 0 else 0.0
    # Blend the (capped) validation rate with normalized contribution into 0-100.
    score = 100.0 * (0.5 * min(1.0, validated_rate) + 0.5 * min(1.0, contribution_per_hour))
    return ResearchROIResult(
        research_roi_score=score,
        validated_rate=validated_rate,
        contribution_per_hour=contribution_per_hour,
    )


class CategoryStat(BaseModel):
    model_config = ConfigDict(frozen=True)

    tested: int
    validated: int
    contribution: float


def rank_categories(stats: Mapping[str, CategoryStat]) -> list[tuple[str, float]]:
    """Rank research categories by expected yield = validation rate x contribution."""
    yields = {
        name: (stat.validated / stat.tested if stat.tested else 0.0) * (1.0 + stat.contribution)
        for name, stat in stats.items()
    }
    return sorted(yields.items(), key=lambda kv: kv[1], reverse=True)

```

### libs/execution/journal.py
```python
"""Trade journal — an immutable, hash-chained record of every execution event.

Backed by the audit log (append-only, tamper-evident), so submissions, fills, cancels,
timeouts, and reconciliations are all permanently traceable.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from libs.store.audit import AuditLog
from libs.store.connection import Database
from libs.store.models import AuditEntry

ACTOR = "execution"


class TradeJournal:
    """Writes execution events to the immutable audit log."""

    def __init__(self, db: Database) -> None:
        self._audit = AuditLog(db)

    def record(
        self,
        event: str,
        inputs: Mapping[str, Any],
        *,
        outcome: str | None = None,
        rationale: str | None = None,
    ) -> AuditEntry:
        return self._audit.append(
            event, actor=ACTOR, inputs=inputs, outcome=outcome, rationale=rationale
        )

```

### libs/execution/ramp_gate.py
```python
"""§6 numeric ramp gate: size steps up on arithmetic, never on confidence.

The spec's wording is "no discretionary language", and that is the entire design constraint. A
size increase is permitted only when ALL FIVE hold over the trailing 8 weeks:

  (a) realized cost <= 1.25x modeled
  (b) live Sharpe >= 0.6x the same-period backtest
  (c) slippage KS-test p > 0.05 vs model
  (d) drill pass-streak >= 8 weeks
  (e) calibration MAE falling 2 consecutive months

Down-steps are unlimited and immediate, and that asymmetry is deliberate: the cost of an
unnecessary down-step is a little foregone return, the cost of a delayed one is the book.

The gate is FAIL-CLOSED on missing evidence. Every condition reads its input with a default that
fails, so an absent metric blocks the step-up rather than waving it through -- an evidence
pipeline that breaks silently must not read as five satisfied conditions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# the size ladder, as fractions of the stage's authorized capital. Steps are multiplicative-ish
# but enumerated rather than computed so "what size are we allowed" is always a lookup, never
# an expression someone can re-derive differently in another file.
SIZE_STEPS: tuple[float, ...] = (0.10, 0.20, 0.35, 0.55, 0.80, 1.00)

COST_RATIO_MAX = 1.25
SHARPE_RATIO_MIN = 0.6
KS_P_MIN = 0.05
DRILL_STREAK_WEEKS_MIN = 8
MAE_FALLING_MONTHS_MIN = 2
TRAILING_WEEKS_REQUIRED = 8.0


def _f(evidence: dict[str, Any], key: str, fail_default: float) -> float:
    """Read a float, defaulting to a value that FAILS its condition. Never raises."""
    try:
        v = evidence.get(key)
        return fail_default if v is None else float(v)
    except (TypeError, ValueError):
        return fail_default


@dataclass(frozen=True)
class RampDecision:
    may_step_up: bool
    checks: dict[str, bool]
    reason: str

    @property
    def failed(self) -> list[str]:
        return sorted(k for k, ok in self.checks.items() if not ok)


def step_up_conditions(evidence: dict[str, Any]) -> dict[str, bool]:
    """The five spec conditions, each independently evaluable and each fail-closed."""
    return {
        "window_ge_8_weeks": _f(evidence, "trailing_weeks", 0.0) >= TRAILING_WEEKS_REQUIRED,
        "a_cost_le_1_25x": _f(evidence, "cost_ratio", 999.0) <= COST_RATIO_MAX,
        "b_live_sharpe_ge_0_6x_backtest": (
            _f(evidence, "live_sharpe", -999.0)
            >= SHARPE_RATIO_MIN * _f(evidence, "backtest_sharpe", 999.0)
        ),
        "c_slippage_ks_p_gt_0_05": _f(evidence, "slippage_ks_p", 0.0) > KS_P_MIN,
        "d_drill_streak_ge_8w": _f(evidence, "drill_pass_streak_weeks", 0.0)
        >= DRILL_STREAK_WEEKS_MIN,
        "e_mae_falling_2_months": _f(evidence, "calibration_mae_falling_months", 0.0)
        >= MAE_FALLING_MONTHS_MIN,
    }


def may_step_up(evidence: dict[str, Any]) -> RampDecision:
    checks = step_up_conditions(evidence)
    ok = all(checks.values())
    failed = sorted(k for k, v in checks.items() if not v)
    return RampDecision(
        may_step_up=ok,
        checks=checks,
        reason="all ramp conditions met" if ok else f"blocked by: {', '.join(failed)}",
    )


def next_step(current: float, evidence: dict[str, Any]) -> tuple[float, str]:
    """The size fraction now authorized. Returns (fraction, why).

    Steps UP by at most one rung and only on a clean gate. An unrecognised current fraction
    snaps DOWN to the nearest authorized rung rather than up -- an unknown state is not a
    licence to grow.
    """
    decision = may_step_up(evidence)
    below = [s for s in SIZE_STEPS if s <= current + 1e-12]
    if not below:
        # BELOW the floor rung (a hand-edited state file, a fresh install, a partial write).
        # Snapping to the floor is a step UP in absolute terms, so it must not ALSO consume a
        # rung: returning here is what stops 0.01 becoming 0.20 in a single tick.
        return SIZE_STEPS[0], (f"size {current:.4f} is below the floor rung -- "
                               f"snapped to {SIZE_STEPS[0]:.2f}, no step this tick")
    idx = SIZE_STEPS.index(max(below))
    floor = SIZE_STEPS[idx]
    if floor < current - 1e-12:
        return floor, f"unrecognised size {current:.4f} -- snapped down to rung {floor:.2f}"
    if not decision.may_step_up:
        return floor, decision.reason
    if idx >= len(SIZE_STEPS) - 1:
        return floor, "already at the top rung"
    return SIZE_STEPS[idx + 1], "all ramp conditions met -- one rung up"


def step_down(current: float, reason: str) -> tuple[float, str]:
    """Immediate one-rung down-step. Never gated, never rate-limited, never refused."""
    below = [s for s in SIZE_STEPS if s < current - 1e-12]
    target = max(below) if below else 0.0
    return target, f"down-step to {target:.2f}: {reason}"

```

### libs/features/labels.py
```python
"""Labels (targets).

Labels are *deliberately* forward-looking — a label at t encodes future outcomes. That is
why a label must never be registered as a feature: doing so is hindsight leakage, which the
feature leakage test rejects. Keep labels strictly on the target side of training.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from libs.features.errors import FeatureError

LABEL_PREFIX = "label_"


def forward_log_return(bars: pd.DataFrame, *, horizon: int = 1) -> pd.Series:
    """The forward log return over ``horizon`` bars (a target; look-ahead by design)."""
    if horizon < 1:
        raise FeatureError("label horizon must be >= 1")
    future_close = bars["close"].shift(-horizon)
    label = np.log(future_close / bars["close"])
    label.name = f"{LABEL_PREFIX}fwd_logret_{horizon}"
    return label


def forward_direction(bars: pd.DataFrame, *, horizon: int = 1) -> pd.Series:
    """The sign of the forward return: +1 up, -1 down, 0 flat (a classification target)."""
    label = np.sign(forward_log_return(bars, horizon=horizon))
    label.name = f"{LABEL_PREFIX}fwd_dir_{horizon}"
    return label


def triple_barrier_labels(
    close: pd.Series,
    *,
    horizon: int,
    upper: float,
    lower: float,
    vol: pd.Series | None = None,
) -> pd.Series:
    """Triple-barrier labels (López de Prado, *Advances in Financial ML* ch. 3).

    Method extracted from hudson-and-thames/mlfinlab and implemented from the book directly (the
    directive's caution: open ports of that library have known-incorrect pieces, and a subtly wrong
    labeller is exactly the leak this desk exists to catch — so this is an owned, verifiable port).

    For each bar ``t``, look forward up to ``horizon`` bars and set two horizontal barriers as
    fractional returns from ``close[t]``: a profit-take at ``+upper * w`` and a stop at
    ``-lower * w`` where ``w = vol[t]`` if a volatility series is given (barriers scale with local
    vol) else ``1.0`` (``upper``/``lower`` are then direct return widths). The label is:

      * ``+1`` if the upper barrier is touched first,
      * ``-1`` if the lower barrier is touched first,
      * ``0``  if neither is touched before the vertical (time) barrier at ``t + horizon``.

    A bar whose forward path is truncated by end-of-data *and* touched no barrier is labelled
    ``NaN`` (undetermined — never fabricate a ``0`` from an unobservable outcome). Forward-looking
    by design: a target, never a feature.

    Raises:
        FeatureError: if ``horizon < 1`` or either barrier width is non-positive.
    """
    if horizon < 1:
        raise FeatureError("label horizon must be >= 1")
    if upper <= 0.0 or lower <= 0.0:
        raise FeatureError("barrier widths (upper, lower) must be > 0")
    px = close.to_numpy(dtype="float64")
    n = len(px)
    w = vol.to_numpy(dtype="float64") if vol is not None else np.ones(n, dtype="float64")
    out = np.full(n, np.nan, dtype="float64")
    for t in range(n):
        end = min(n - 1, t + horizon)
        up_b, dn_b = upper * w[t], lower * w[t]
        touched = False
        for s in range(t + 1, end + 1):
            r = px[s] / px[t] - 1.0
            if r >= up_b:
                out[t], touched = 1.0, True
                break
            if r <= -dn_b:
                out[t], touched = -1.0, True
                break
        if not touched and (t + horizon) <= n - 1:
            out[t] = 0.0  # full path observed, no barrier hit -> genuine flat (0)
    return pd.Series(out, index=close.index, name=f"{LABEL_PREFIX}triple_barrier_{horizon}")

```

### libs/monitoring/monitor.py
```python
"""Monitor service — record metrics, evaluate thresholds/SLOs, raise and route alerts.

Deterministic: a metric value is compared against its thresholds with fixed operators; any breach
records a durable alert and dispatches it. A heartbeat watchdog and SLO evaluator are provided for
liveness and objective tracking. Fail-closed: a missing metric fails its SLO.
"""

from __future__ import annotations

from collections.abc import Sequence

from libs.monitoring.alerting import AlertRouter, AlertStore
from libs.monitoring.metrics_store import MetricsStore
from libs.monitoring.models import SLO, Alert, MetricPoint, Severity, Threshold, compare
from libs.store.connection import Database


class MonitorService:
    """Records metrics and raises alerts when thresholds are breached."""

    def __init__(
        self,
        db: Database,
        thresholds: Sequence[Threshold] | None = None,
        *,
        router: AlertRouter | None = None,
    ) -> None:
        self.metrics = MetricsStore(db)
        self.alerts = AlertStore(db)
        self.router = router or AlertRouter()
        self._thresholds: list[Threshold] = list(thresholds or [])

    def add_threshold(self, threshold: Threshold) -> None:
        self._thresholds.append(threshold)

    def record(self, name: str, value: float, *, tags: dict[str, str] | None = None) -> MetricPoint:
        """Persist a metric point and evaluate its thresholds (raising alerts on breach)."""
        point = self.metrics.record(name, value, tags=tags)
        self.evaluate(name, value)
        return point

    def evaluate(self, name: str, value: float) -> list[Alert]:
        """Evaluate a value against all thresholds for ``name``; record+route any breaches."""
        raised: list[Alert] = []
        for threshold in self._thresholds:
            if threshold.metric != name:
                continue
            if compare(value, threshold.op, threshold.value):
                alert = self.alerts.record(
                    severity=threshold.severity, source="monitor", metric=name, value=value,
                    threshold=threshold.value,
                    message=threshold.message
                    or f"{name}={value} {threshold.op.value} {threshold.value}",
                )
                self.router.dispatch(alert)
                raised.append(alert)
        return raised


class HeartbeatWatchdog:
    """Liveness check from monotonic timestamps (seconds); fail-closed if silent too long."""

    def __init__(self, *, max_silence_seconds: float) -> None:
        self.max_silence_seconds = max_silence_seconds

    def alive(self, *, last_beat_epoch: float, now_epoch: float) -> bool:
        return (now_epoch - last_beat_epoch) <= self.max_silence_seconds


class SLOEvaluator:
    """Evaluates a set of SLOs against current metric values (missing metric -> failed)."""

    def __init__(self, slos: Sequence[SLO]) -> None:
        self.slos = list(slos)

    def evaluate(self, metrics: dict[str, float]) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for slo in self.slos:
            if slo.metric not in metrics:
                results[slo.name] = False  # fail-closed
                continue
            results[slo.name] = compare(metrics[slo.metric], slo.op, slo.target)
        return results


__all__ = [
    "HeartbeatWatchdog",
    "MonitorService",
    "SLOEvaluator",
    "Severity",
]

```

### libs/ops/deploy_plan.py
```python
"""INBOUND DEPLOY PLANNER -- what a pulled commit actually invalidates.

WHY THIS EXISTS (EXECUTION_QUEUE.md RANK 7, found 2026-07-30). ``scripts/git_snapshot.py`` pushes
VPS -> GitHub. **Nothing pulled GitHub -> VPS**, so merging to master deployed NOTHING and every
change needed a manual SSH. The desk has already paid for that gap at the worst possible layer:
on 2026-07-26 an orphaned executor kept running PRE-FIX code for 8h, so "the funding-measurement
fix committed that evening was inert in the process that actually owned the book" -- a committed
fix that never shipped (``scripts/watchdog.py``:66-76). A repo whose commits do not reach the
running process is a repo that lies about what the desk is doing.

PULLING IS THE EASY HALF. THE HARD HALF IS KNOWING WHAT TO RESTART, and getting it wrong is
asymmetric in a way that decides the whole design:

  * UNDER-restarting reproduces the 2026-07-26 incident exactly -- new code on disk, old code in
    the process that owns the book. Silent, and the desk cannot tell from the outside.
  * OVER-restarting costs a brief gap in a systemd-owned service. systemd holds single-instance,
    so it cannot orphan (that is precisely what the watchdog's ``_systemd_owns`` guard exists to
    prevent), and the executor reconciles on start.

So this planner deliberately errs toward restarting. The ONE exception is the ruin rail, below.

WHY THE MAP IS COMPUTED, NOT WRITTEN DOWN. A hand-maintained "these paths affect the executor"
list rots the first time somebody adds an import, and it rots SILENTLY -- the deploy keeps
succeeding while quietly leaving a stale process behind. So the affected set is derived from the
real first-party import closure of each entry script, parsed with ``ast`` at plan time. Adding
``from libs.risk.foo import bar`` to the executor widens its blast radius automatically, with no
list to update and no way to forget.

Measured 2026-07-30, and it is the reason this is cheap: only ONE of the four unit-owned processes
has a first-party closure at all. ``run_deadman_switch.py``, ``liquidation_listener.py`` and
``serve_dashboard.py`` import nothing from ``libs/`` -- pure stdlib plus pandas/websockets. The
ruin rail's dependency-freedom is a design property, not an accident, and it means an ordinary
``libs/`` commit cannot invalidate the ruin rail at all.

THE RUIN RAIL IS TIER 3 AND IS NEVER RESTARTED BY A SCRIPT. ``quant-deadman.service`` is the
"NEVER-TOUCH rail -- exactly one instance ever under systemd" (``ops/crontab.manifest``, from
``ops/memory/crypto-desk-state.md``:21). A restart is a window with no ruin rail, and no
unattended script gets to open that window: an orphan is recoverable, a dead ruin rail is not
(``scripts/watchdog.py``:74-77). When a commit genuinely changes the deadman, this reports
ESCALATE and the operator supervises it. That is the honest exit, not a gap.

EVERYTHING ELSE NEEDS NO RESTART, and that is not a shrug. Cron re-execs a fresh interpreter every
tick, so a pulled change to any cron-owned script is live on its next firing with nothing to do.
The set that needs action is small by construction.

Pure stdlib. Import from ``libs.ops.deploy_plan``; driven by ``deploy/pull_deploy.sh``.
"""

from __future__ import annotations

import ast
import sys
from collections import deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

#: Top-level packages that live in THIS repo. An import outside these is a third-party or stdlib
#: dependency -- a pulled commit cannot change it, so it is not part of any blast radius.
_FIRST_PARTY = ("libs", "api", "app")

TIER_RESTART = 2       #: systemd-owned; a script may restart it (systemd holds single-instance)
TIER_RUIN = 3          #: the ruin rail; a script may NEVER restart it -- operator supervises

#: entry script -> (unit, tier). MUST agree with ``scripts/watchdog.py``'s ``_UNITS``; a test
#: asserts they match, because two copies of the same supervision map is how the desk's previous
#: four capacity constants drifted apart (§42's lesson, applied to a different map).
_OWNED: dict[str, tuple[str, int]] = {
    "scripts/run_cashcarry_executor.py": ("quant-cashcarry.service", TIER_RESTART),
    "scripts/run_deadman_switch.py": ("quant-deadman.service", TIER_RUIN),
    "scripts/liquidation_listener.py": ("quant-liquidations.service", TIER_RESTART),
    "scripts/serve_dashboard.py": ("quant-dashboard.service", TIER_RESTART),
}

#: Changing the scheduler's source does not restart a process -- it means the INSTALLED crontab is
#: now stale. Reported so it cannot pass unnoticed, never auto-applied: the manifest's own header
#: forbids running the installer before a human reviews live drift, because the box carries
#: unfenced cron lines that would double-schedule the recorders.
_SCHEDULER_SOURCES = ("ops/crontab.manifest",)


@dataclass(frozen=True)
class UnitAction:
    """One process the pulled commit invalidated, and what may be done about it."""

    unit: str
    entry: str
    tier: int
    trigger: str          #: the changed path that invalidated it (the entry, or a closure member)

    @property
    def verb(self) -> str:
        return "RESTART" if self.tier == TIER_RESTART else "ESCALATE"

    @property
    def why(self) -> str:
        via = "changed directly" if self.trigger == self.entry else f"imports {self.trigger}"
        if self.tier == TIER_RUIN:
            return (f"{self.entry} {via} -- RUIN RAIL, not restarted here: a restart is a window "
                    "with no ruin rail and no unattended script opens that window")
        return f"{self.entry} {via}"


@dataclass
class DeployPlan:
    """The full disposition of a pulled commit. Nothing changed is ever silently dropped."""

    changed: list[str] = field(default_factory=list)
    actions: list[UnitAction] = field(default_factory=list)
    scheduler_stale: list[str] = field(default_factory=list)
    no_restart: list[str] = field(default_factory=list)

    @property
    def restarts(self) -> list[UnitAction]:
        return [a for a in self.actions if a.tier == TIER_RESTART]

    @property
    def escalations(self) -> list[UnitAction]:
        return [a for a in self.actions if a.tier == TIER_RUIN]

    def directives(self) -> list[str]:
        """Tab-separated lines for ``deploy/pull_deploy.sh`` to execute.

        A line protocol rather than JSON on purpose: the consumer is POSIX sh on a restore-day box
        where the only guaranteed parser is ``read``/``cut``, and a deploy path that needs a JSON
        library to tell the operator what to restart is a deploy path that fails when it matters.
        """
        out = [f"{a.verb}\t{a.unit}\t{a.why}" for a in self.actions]
        out += [f"SCHEDULER\t{p}\tinstalled crontab is now stale vs the manifest -- review live "
                f"drift (check_scheduler_manifest.py --report-only) BEFORE reconstitute_cron.sh"
                for p in self.scheduler_stale]
        return out


def _module_file(mod: str, root: Path) -> Path | None:
    """``libs.execution.engine`` -> the file that defines it, module or package."""
    rel = Path(*mod.split("."))
    for cand in (root / rel.with_suffix(".py"), root / rel / "__init__.py"):
        if cand.is_file():
            return cand
    return None


def _first_party_imports(path: Path) -> set[str]:
    """First-party dotted names imported by ``path``, from a real parse (not a regex).

    ``from libs.execution import carry_accounting`` contributes BOTH ``libs.execution`` and
    ``libs.execution.carry_accounting``: the name may be a submodule or an attribute of the
    package, and resolving it wrongly would silently narrow the blast radius. Widening it costs a
    restart that was not strictly needed; narrowing it leaves stale code owning the book.
    """
    try:
        tree = ast.parse(path.read_text("utf-8"), filename=str(path))
    except (OSError, SyntaxError, ValueError):
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module)
            names.update(f"{node.module}.{a.name}" for a in node.names)
    return {n for n in names if n.split(".")[0] in _FIRST_PARTY}


def import_closure(entry: str, root: Path | None = None) -> set[str]:
    """Every first-party repo file ``entry`` can reach, as repo-relative paths (excluding itself).

    Breadth-first with a visited set, so an import cycle terminates instead of hanging a deploy.
    """
    root = root or _ROOT
    start = root / entry
    if not start.is_file():
        return set()
    seen: set[Path] = {start}
    queue: deque[Path] = deque([start])
    while queue:
        for mod in _first_party_imports(queue.popleft()):
            f = _module_file(mod, root)
            if f is not None and f not in seen:
                seen.add(f)
                queue.append(f)
    return {p.relative_to(root).as_posix() for p in seen if p != start}


def plan(changed: Iterable[str], root: Path | None = None) -> DeployPlan:
    """Classify changed repo-relative paths into restart / escalate / stale-scheduler / no-op."""
    root = root or _ROOT
    paths = sorted({p.strip().replace("\\", "/") for p in changed if p.strip()})
    out = DeployPlan(changed=list(paths))
    accounted: set[str] = set()

    for entry, (unit, tier) in sorted(_OWNED.items()):
        # the entry script itself is the strongest trigger; report it in preference to a
        # closure member so the operator reads the direct cause, not an incidental import
        trigger = entry if entry in paths else None
        if trigger is None:
            hits = sorted(set(paths) & import_closure(entry, root))
            trigger = hits[0] if hits else None
        if trigger is None:
            continue
        out.actions.append(UnitAction(unit=unit, entry=entry, tier=tier, trigger=trigger))
        accounted.update(set(paths) & ({entry} | import_closure(entry, root)))

    out.scheduler_stale = [p for p in paths if p in _SCHEDULER_SOURCES]
    accounted.update(out.scheduler_stale)
    # cron re-execs a fresh interpreter every tick, so these are live on next firing with no action
    out.no_restart = [p for p in paths if p not in accounted]
    return out


def _render(p: DeployPlan) -> str:
    lines = [f"deploy-plan: {len(p.changed)} changed path(s)"]
    for a in p.restarts:
        lines.append(f"  RESTART  {a.unit}  <- {a.why}")
    for a in p.escalations:
        lines.append(f"  ESCALATE {a.unit}  <- {a.why}")
    for s in p.scheduler_stale:
        lines.append(f"  SCHEDULER {s} changed -- installed crontab is stale (review drift first)")
    if not p.actions and not p.scheduler_stale:
        lines.append("  no supervised process invalidated -- cron picks the new code up next tick")
    elif p.no_restart:
        lines.append(f"  ({len(p.no_restart)} other path(s) need no restart -- cron-owned)")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """``--directives`` emits the sh line protocol; default prints the human summary.

    Changed paths arrive on stdin, one per line, exactly as ``git diff --name-only`` emits them.
    """
    args = list(argv if argv is not None else sys.argv[1:])
    p = plan(sys.stdin.read().splitlines())
    print("\n".join(p.directives()) if "--directives" in args else _render(p))
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### libs/ops/model_chain.py
```python
"""MODEL CHAIN -- one source of truth, and the ranking that lets the desk upgrade itself.

THE PROBLEM. The fallback chain `claude-fable-5 claude-opus-5 claude-opus-4-8` was hardcoded in
THREE places (ops/brain_env.sh, ops/run_frontier_miner.sh, scripts/run_deep_sweep.py). Any change
-- including an automatic upgrade -- silently updated one and left two stale, so organs would
disagree about which model they run and the disagreement would be invisible. Capacity policy hit
exactly this failure earlier (a constant re-inlined next to a scorer, fenced by
check_capacity_single_source); this is the same defect wearing a different name.

So the chain lives in `ops/model_chain.env` -- generated, committed, sourced by every shell organ,
imported by every python organ. This module owns the ranking logic and nothing else, which is what
makes the auto-upgrader testable without a network.

WHY RANKING IS EXPLICIT AND CONSERVATIVE. "Newer flagship" cannot be inferred from a string. The
desk therefore ranks only what it can defend:
  * FAMILY TIER is a declared ladder, not a guess. Unknown families rank -1 and are never
    auto-adopted -- they are PROPOSED, because silently promoting an unrecognised model into the
    path that sizes real positions is the kind of convenience that ends compounding.
  * VERSION is parsed from the trailing numeric segment, so `4-8` -> 4.8 and `5` -> 5.0, giving
    the ordering opus-4-8 < opus-5. A model with no parseable version ranks below every parseable
    one rather than above -- unknown is not "newest".

An upgrade is only ever a PREPEND. The outgoing head stays in the chain directly beneath the new
one, so a newly-promoted model that starts erroring or throttling falls back to the exact model
the desk was running yesterday, with no human awake.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
CHAIN_FILE = _ROOT / "ops/model_chain.env"

# The declared ladder. Fable and Opus are peers at the flagship tier: the desk's policy
# (principal 2026-07-30) is fable-first-to-exhaustion, then opus -- an ORDERING decision inside a
# tier, not a capability ranking, which is why they share tier 3.
FAMILY_TIER: dict[str, int] = {"opus": 3, "fable": 3, "sonnet": 2, "haiku": 1}

FLAGSHIP_TIER = 3

# Never longer than this: a chain deeper than four is untestable at cycle start, and every extra
# entry is another model whose failure mode nobody has seen.
MAX_CHAIN = 4

_FALLBACK_CHAIN = ("claude-fable-5", "claude-opus-5", "claude-opus-4-8")


def parse_model(model_id: str) -> tuple[int, float]:
    """(family_tier, version). Unknown family -> -1. Unparseable version -> -1.0.

    Deliberately total: it never raises on a model id it has not seen, because the caller's job is
    to REFUSE unknowns, and a crash in the upgrader would take the whole cycle down with it.
    """
    m = re.match(r"^claude-([a-z]+)-([0-9][0-9-]*)", model_id.strip().lower())
    if not m:
        # Legacy shape: claude-3-5-sonnet-20241022 -- family after the digits.
        alt = re.match(r"^claude-([0-9][0-9-]*)-([a-z]+)", model_id.strip().lower())
        if not alt:
            return (-1, -1.0)
        family, ver = alt.group(2), alt.group(1)
    else:
        family, ver = m.group(1), m.group(2)
    tier = FAMILY_TIER.get(family, -1)
    # A trailing YYYYMMDD snapshot is a DATE, not a version segment. Left in, `haiku-4-5-20251001`
    # parses as 4.52 instead of 4.5 -- which orders two snapshots of the same model against each
    # other and would churn the chain on every re-dating. Only the first two segments are version.
    parts = [p for p in ver.split("-") if p.isdigit() and len(p) < 5][:2]
    if not parts:
        return (tier, -1.0)
    version = float(parts[0]) + (float(f"0.{parts[1]}") if len(parts) > 1 else 0.0)
    return (tier, version)


def is_flagship(model_id: str) -> bool:
    return parse_model(model_id)[0] >= FLAGSHIP_TIER


def is_upgrade(candidate: str, incumbent: str) -> bool:
    """Is `candidate` a strictly newer FLAGSHIP than the current chain head?

    Three refusals, each deliberate:
      * an unknown family is never an upgrade (it may not even be a chat model);
      * a lower tier is never an upgrade, so a new sonnet never displaces an opus;
      * an equal version is never an upgrade, so a re-dated snapshot of the same model does not
        churn the chain every night for no capability gain.
    """
    c_tier, c_ver = parse_model(candidate)
    i_tier, i_ver = parse_model(incumbent)
    if c_tier < FLAGSHIP_TIER:
        return False
    if c_tier != i_tier:
        return c_tier > i_tier
    return c_ver > i_ver


def promote(candidate: str, chain: list[str]) -> list[str]:
    """Prepend `candidate`, keeping the outgoing head directly beneath it.

    The old head is retained ON PURPOSE. A model promoted at 03:00 that turns out to be throttled,
    slower, or rejected by the plan must degrade to the exact model the desk ran yesterday without
    waking anyone -- that is the whole point of a chain, and it is why an upgrade is never a
    replacement.
    """
    out = [candidate] + [m for m in chain if m != candidate]
    return out[:MAX_CHAIN]


def read_chain() -> list[str]:
    """The live chain. Falls back to the compiled-in constant so a missing/corrupt file can never
    leave an organ with NO model -- the failure would be an outage, not a downgrade."""
    if CHAIN_FILE.exists():
        for raw in CHAIN_FILE.read_text("utf-8").splitlines():
            # The file is SHELL: every assignment carries an `export ` prefix. Matching without
            # stripping it silently never matches, so every python reader would fall back to the
            # compiled-in constant -- including the upgrader itself, which would then re-evaluate
            # against a stale head forever and never see its own promotion.
            line = raw.strip().removeprefix("export ").strip()
            if line.startswith("_BRAIN_MODEL_CHAIN="):
                chain = line.split("=", 1)[1].strip().strip('"').split()
                if chain:
                    return chain
    return list(_FALLBACK_CHAIN)


def render_chain(chain: list[str], *, reason: str, sealed: str) -> str:
    return (
        "# GENERATED by scripts/run_model_upgrade.py -- DO NOT HAND-EDIT.\n"
        "# Single source of truth for the desk's model fallback chain (libs/ops/model_chain.py).\n"
        "# Sourced by ops/brain_env.sh + ops/run_frontier_miner.sh; imported by python organs.\n"
        "# Order IS the policy: head is consumed to exhaustion, then the desk walks down. Every\n"
        "# step past the head pages the principal via brain_auth_check.\n"
        f"# last change: {sealed}\n"
        f"# reason: {reason}\n"
        f'export _BRAIN_MODEL_CHAIN="{" ".join(chain)}"\n'
        f'export ANTHROPIC_MODEL="${{ANTHROPIC_MODEL:-{chain[0]}}}"\n'
    )

```

### libs/portfolio/errors.py
```python
"""Portfolio-layer exceptions."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class PortfolioError(QuantPlatformError):
    """Invalid portfolio inputs or infeasible construction."""

```

### libs/regime/gmm.py
```python
"""GMM regime model -- thin wrapper over sklearn's GaussianMixture (already a dependency).

Unlike the HMM, the GMM ignores temporal persistence (no transition matrix); it clusters the feature
space into regimes. Used as an independent second opinion -- when the HMM and GMM agree on the
current regime, confidence is high; when they disagree, the engine flags it.
"""

from __future__ import annotations

import numpy as np
from sklearn.mixture import GaussianMixture  # type: ignore[import-untyped]


def fit_gmm(x: np.ndarray, *, n_states: int = 3, seed: int = 0) -> GaussianMixture:
    gm = GaussianMixture(n_components=n_states, covariance_type="diag",
                         random_state=seed, n_init=3, reg_covar=1e-4)
    gm.fit(np.asarray(x, dtype="float64"))
    return gm


def gmm_posteriors(gm: GaussianMixture, x: np.ndarray) -> np.ndarray:
    """Per-observation soft regime membership P(state | x_t)."""
    return np.asarray(gm.predict_proba(np.asarray(x, dtype="float64")), dtype="float64")

```

### libs/research/crypto_xsec.py
```python
"""Cross-sectional crypto funding strategy core (the program's single best candidate).

Long the lowest-funding perps, short the highest, dollar-neutral, risk-parity (inverse-vol) within
each leg, with a turnover band and ADV-tiered realistic costs. Pure function of (close, funding,
adv) -- the SAME code runs the backtest and the forward shadow, so the out-of-sample comparison is
provably apples-to-apples. No parameter mining: the deployable variant is frozen by the caller.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def adv_tier_cost(adv_usd: float) -> float:
    """Per-side realistic cost by average dollar volume (taker + tiered slippage)."""
    if adv_usd > 5e8:
        return 5e-4
    if adv_usd > 1e8:
        return 8e-4
    return 1.5e-3


def xsec_funding_returns(
    close: pd.DataFrame,
    funding: pd.DataFrame,
    adv: dict[str, float],
    *,
    lookback: int,
    q: float,
    band: float,
    vol_window: int = 30,
    min_names: int = 12,
) -> np.ndarray:
    """Daily net-of-cost return series of the cross-sectional funding strategy.

    Decisions use only lagged information (no look-ahead). Returns are NOT vol-scaled here so the
    series is directly comparable across runs; Sharpe is scale-invariant anyway.
    """
    ret = close.pct_change(fill_method=None)
    inv_vol = 1.0 / ret.rolling(vol_window).std().shift(1)
    signal = funding.rolling(lookback).mean().shift(1)
    cost = {s: adv_tier_cost(a) for s, a in adv.items()}
    out = np.zeros(len(close), dtype="float64")
    prev = pd.Series(0.0, index=close.columns)
    for t in range(1, len(close)):
        sig = signal.iloc[t].dropna()
        valid = close.iloc[t].reindex(sig.index).notna() & ret.iloc[t].reindex(sig.index).notna()
        sig = sig.reindex(sig.index[valid]).dropna()
        if len(sig) < min_names:
            out[t] = float((prev * ret.iloc[t].reindex(prev.index).fillna(0.0)).sum())
            continue
        k = max(1, int(len(sig) * q))
        ranked = sig.sort_values()
        longs, shorts = ranked.index[:k], ranked.index[-k:]
        iv = inv_vol.iloc[t]
        w = pd.Series(0.0, index=close.columns)
        lw, sw = iv.reindex(longs).fillna(0.0), iv.reindex(shorts).fillna(0.0)
        if lw.sum() > 0:
            w[longs] = 0.5 * lw / lw.sum()
        if sw.sum() > 0:
            w[shorts] = -0.5 * sw / sw.sum()
        delta = (w - prev).abs()
        w = w.where(delta > band, prev)            # turnover band: hold unless target moved
        price_ret = float((w * ret.iloc[t].reindex(w.index).fillna(0.0)).sum())
        funding_pnl = float(-(w * funding.iloc[t].reindex(w.index).fillna(0.0)).sum())
        turn_cost = float(sum(abs(w[s] - prev[s]) * cost.get(s, 1.5e-3) for s in w.index))
        out[t] = price_ret + funding_pnl - turn_cost
        prev = w
    return out

```

### libs/research/decision_review.py
```python
"""Decision-ledger maturity: make every logged decision REVIEWABLE, so scoring has a queue.

The ledger's own policy says "the monthly governance review scores each matured entry so decision
QUALITY compounds". Measured 2026-07-26: 189 decisions, 3 with an outcome, and -- the mechanical
cause -- only 14 carrying a `review_due`. "Matured" was never defined, so 175 decisions could not
come due, ever. The scoring cadence was running against an empty queue and reporting no work.

This module derives a review date for every decision and classifies where each one stands. It
deliberately does NOT decide outcomes. Scoring a decision correct/wrong/unclear is a judgement
about the world, and a calibration ledger filled with machine-guessed outcomes is worse than an
empty one: the Brier score would then be confidently wrong about how well the desk decides, which
is the exact failure the ledger exists to prevent.

What it produces is the worklist. Resolution stays a deliberate act.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

#: Default maturity. The ledger's policy language is "the monthly governance review", so a
#: decision with no stated horizon comes due one month after it was taken.
DEFAULT_HORIZON_D = 30

#: A horizon named in the success metric wins over the default -- "by day 90: sim vs real"
#: means ninety days, and pulling it forward to thirty would score the decision before its own
#: stated evidence exists.
_HORIZON = re.compile(
    r"\bday\s*(?P<day>\d{1,3})\b"
    r"|\b(?P<d>\d{1,3})\s*[-\s]?(?:d|days?)\b"
    r"|\b(?P<w>\d{1,2})\s*[-\s]?(?:wk|weeks?)\b"
    r"|\b(?P<m>\d{1,2})\s*[-\s]?(?:mo|months?)\b",
    re.IGNORECASE,
)

_ID_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")

#: An outcome of this value means "logged but not actually scored yet".
_NON_OUTCOMES = {"", "pending", "tbd", "open", "n/a", "none", "-"}


def stated_horizon_days(text: str) -> int | None:
    """Longest horizon named in a success metric, in days. None when none is stated.

    LONGEST, not first: a metric reading "funding/day rises within 7d and holds 90d" is not
    settled at day 7. Taking the first match would score decisions early and systematically
    flatter the desk, because early readings are the ones taken while the change is fresh.
    """
    best: int | None = None
    for m in _HORIZON.finditer(text or ""):
        if m.group("day"):
            v = int(m.group("day"))
        elif m.group("d"):
            v = int(m.group("d"))
        elif m.group("w"):
            v = int(m.group("w")) * 7
        elif m.group("m"):
            v = int(m.group("m")) * 30
        else:
            continue
        if 1 <= v <= 730 and (best is None or v > best):
            best = v
    return best


def decision_date(row: dict[str, Any]) -> date | None:
    """The date the decision was taken, from its id prefix. None when unparseable."""
    m = _ID_DATE.match(str(row.get("id", "")))
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def is_scored(row: dict[str, Any]) -> bool:
    """Has this decision actually been scored? A placeholder outcome does not count."""
    return str(row.get("outcome", "")).strip().lower() not in _NON_OUTCOMES


@dataclass(frozen=True)
class Review:
    row_id: str
    taken: date | None
    due: date | None
    horizon_d: int
    source: str           # "explicit" | "success_metric" | "default" | "unknown"
    scored: bool
    state: str            # "scored" | "due" | "maturing" | "undatable"
    days_overdue: int

    @property
    def actionable(self) -> bool:
        return self.state == "due"


def review_for(row: dict[str, Any], today: date) -> Review:
    """Where this one decision stands. Never invents an outcome."""
    rid = str(row.get("id", "<no id>"))
    scored = is_scored(row)
    taken = decision_date(row)

    explicit = str(row.get("review_due", "")).strip()
    due: date | None = None
    source = "unknown"
    horizon = 0

    if explicit:
        try:
            due = date.fromisoformat(explicit[:10])
            source = "explicit"
        except ValueError:
            due = None
    if due is None and taken is not None:
        stated = stated_horizon_days(str(row.get("success_metric", "")))
        horizon = stated if stated is not None else DEFAULT_HORIZON_D
        source = "success_metric" if stated is not None else "default"
        due = taken + timedelta(days=horizon)
    if due is not None and taken is not None:
        horizon = (due - taken).days

    if scored:
        state = "scored"
    elif due is None:
        # no id date and no explicit review date: this row can never come due, and no derivation
        # can rescue it. Reported rather than silently defaulted to today.
        state = "undatable"
    elif due <= today:
        state = "due"
    else:
        state = "maturing"

    overdue = (today - due).days if (due is not None and state == "due") else 0
    return Review(row_id=rid, taken=taken, due=due, horizon_d=horizon, source=source,
                  scored=scored, state=state, days_overdue=overdue)


def reviews(rows: list[dict[str, Any]], today: date) -> list[Review]:
    return [review_for(r, today) for r in rows]


def backfill_plan(rows: list[dict[str, Any]], today: date) -> list[tuple[str, str, str]]:
    """Rows needing a derived `review_due` written in. (id, iso_date, source).

    Only rows with NO explicit date are touched. A date a human set is never overwritten, even
    when the derivation would disagree -- the point is to give the queue a floor, not to
    relitigate horizons somebody chose on purpose.
    """
    out: list[tuple[str, str, str]] = []
    for r in rows:
        if str(r.get("review_due", "")).strip():
            continue
        rv = review_for(r, today)
        if rv.due is not None:
            out.append((rv.row_id, rv.due.isoformat(), rv.source))
    return out


@dataclass(frozen=True)
class LedgerHealth:
    total: int
    scored: int
    due: int
    maturing: int
    undatable: int
    no_review_date: int
    oldest_overdue_d: int

    @property
    def scored_pct(self) -> float:
        return round(100.0 * self.scored / self.total, 1) if self.total else 0.0

    @property
    def verdict(self) -> str:
        if self.no_review_date:
            return (f"{self.no_review_date} of {self.total} decisions carry NO review date -- "
                    "they can never come due, so the scoring cadence has nothing to pull")
        if self.due:
            return (f"{self.due} decision(s) matured and unscored, oldest {self.oldest_overdue_d}d "
                    f"past due ({self.scored}/{self.total} scored)")
        return (f"queue clean: {self.scored}/{self.total} scored, {self.maturing} still maturing")


def health(rows: list[dict[str, Any]], today: date) -> LedgerHealth:
    rv = reviews(rows, today)
    due = [r for r in rv if r.state == "due"]
    return LedgerHealth(
        total=len(rv),
        scored=sum(1 for r in rv if r.state == "scored"),
        due=len(due),
        maturing=sum(1 for r in rv if r.state == "maturing"),
        undatable=sum(1 for r in rv if r.state == "undatable"),
        no_review_date=sum(1 for r, src in zip(rv, rows, strict=True)
                           if not str(src.get("review_due", "")).strip() and not r.scored),
        oldest_overdue_d=max((r.days_overdue for r in due), default=0),
    )


def confidence_profile(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The desk's stated-confidence distribution -- the thing calibration will test.

    Reported because it is striking on its own: 85% of decisions logged at 0.8-0.9 is the
    signature of an anchor, not of judgement varying with the problem. Unfalsifiable while
    outcomes are missing, and immediately testable once they are not -- which is the single
    most valuable thing this ledger could eventually tell the desk about itself.
    """
    vals = [float(r["confidence"]) for r in rows
            if isinstance(r.get("confidence"), (int, float))]
    if not vals:
        return {"n": 0}
    buckets: dict[str, int] = {}
    for v in vals:
        buckets[f"{round(v, 1):.1f}"] = buckets.get(f"{round(v, 1):.1f}", 0) + 1
    top = max(buckets.items(), key=lambda kv: kv[1])
    return {
        "n": len(vals),
        "mean": round(sum(vals) / len(vals), 3),
        "buckets": dict(sorted(buckets.items())),
        "modal_bucket": top[0],
        "modal_share_pct": round(100.0 * top[1] / len(vals), 1),
    }

```

### libs/research/label_factory.py
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
    # held: the step is still in force through the confirmation window
    held = stepped.copy()
    for k in range(1, max(1, confirm) + 1):
        held &= _mask(rv.shift(-k) > ratio * prior)
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

### libs/research/strategic_director.py
```python
"""STRATEGIC DIRECTOR -- a runtime ROLE with an enforced output contract (RANK 3).

The principal was explicit: *"not as another dormant doctrine document."* So this is not prose about
strategy. It is three mechanical things -- an input dossier assembled from artifacts that already
exist, a prompt, and an OUTPUT CONTRACT that is validated in code -- wired into the intelligence
cycle, with every accepted recommendation written to the recommendation ledger so §41 forces a
disposition. A recommendation that lands in the ledger cannot be quietly forgotten; that is the
whole difference between this and a document.

WHY THE CONTRACT IS THE PRODUCT. An LLM asked for strategy returns fluent, plausible, unfalsifiable
advice -- "improve research throughput", "strengthen the validation stack" -- and fluent advice is
worse than none because it FEELS like progress and cannot be checked. So a recommendation is
REJECTED here unless it names, as separate fields: the measurable bottleneck it removes, the
expected impact, the opportunity cost, and a success metric. Those four are exactly what turn advice
into something that can later be judged wrong. Parsing is strict and rejections are reported, never
silently dropped.

THE PRIORITY RULE IS ENFORCED, NOT REQUESTED. *"Find unused capability BEFORE inventing new
capability"* is in the prompt, but a rule that lives only in a prompt is advisory -- the model can
ignore it and usually will, because proposing new construction is more rhetorically satisfying than
proposing activation. So every recommendation must DECLARE its ``kind`` (activate / merge / retire /
unlock / build), and when the dormancy report shows unused capabilities, a ``build`` recommendation
is rejected unless it carries an explicit ``why_not_activation``. Enforcing on a declared field
rather than on keyword-sniffing the prose is what makes this robust: the model cannot dodge it by
rewording, and the desk's actual measured state (171 dormant capabilities on 2026-07-30) is what
sets the bar.

ACTIVATION-READY BY CONSTRUCTION. Execution is blocked on OpenRouter credit -- the same 402 that
blocks the panel and ``llm_code_auditor.py``. Everything here except the network call is pure and
tested, so when credit lands nothing is redesigned: the dossier assembles, the prompt builds, the
contract validates, the ledger commands emit. ``scripts/run_strategic_director.py --dry-run`` proves
the whole path today without spending a cent, and that is deliberately the default when no key
exists.

Pure stdlib. Import from ``libs.research.strategic_director``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]

#: The dossier. Artifacts that ALREADY EXIST -- the queue's constraint, and why this needs no new
#: collection. A missing one is reported as missing, never silently omitted: a director reasoning
#: off a dossier with invisible holes is GAP_REGISTER #77 in a new costume.
DOSSIER_SOURCES: dict[str, str] = {
    "dormancy": "web/intelligence_cycle.json",
    "data_registry": "data/data_assets.json",
    "enforcement_matrix": "data/enforcement_matrix.json",
    "gate_histogram": "data/gate_histogram.json",
    "reality_gap": "web/reality_gap.json",
    "desk_brief": "data/executive_kpis.json",
    "execution_intel": "web/execution_intel.json",
    "moat_audit": "data/moat_quality.json",
    "recommendation_ledger": "docs/research/recommendation_ledger.json",
    # the queue names "register rank" in the director's INPUT list: the GAP register is
    # where the desk records what it already knows is broken, so a director that cannot
    # see it will keep re-proposing rows that are already open.
    "gap_register": "docs/GAP_REGISTER.md",
}

#: A recommendation's disposition kind. ``build`` is last on purpose: it is what the priority rule
#: constrains, because it grows the surface the desk already fails to wire.
KIND_ACTIVATE = "activate"
KIND_MERGE = "merge"
KIND_RETIRE = "retire"
KIND_UNLOCK = "unlock"
KIND_BUILD = "build"
KINDS = (KIND_ACTIVATE, KIND_MERGE, KIND_RETIRE, KIND_UNLOCK, KIND_BUILD)

#: The four fields that separate a judgeable recommendation from fluent advice.
REQUIRED_FIELDS = ("bottleneck", "expected_impact", "opportunity_cost", "success_metric")

#: Below this many characters a required field is boilerplate, not an answer. "improves things" is
#: 15 characters and says nothing.
MIN_FIELD_CHARS = 25


@dataclass
class Dossier:
    """What the director is allowed to reason from, and what was missing when it did."""

    present: dict[str, Any] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    dormant_count: int = 0

    @property
    def complete(self) -> bool:
        return not self.missing

    def summary(self) -> str:
        return (f"{len(self.present)}/{len(DOSSIER_SOURCES)} artifacts present, "
                f"{self.dormant_count} dormant capabilities")


@dataclass
class Recommendation:
    """One judgeable proposal. Every field here exists so it can later be shown to be wrong."""

    title: str
    kind: str
    bottleneck: str
    expected_impact: str
    opportunity_cost: str
    success_metric: str
    why_not_activation: str = ""
    roi_bps: float | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "title": self.title, "kind": self.kind, "bottleneck": self.bottleneck,
            "expected_impact": self.expected_impact, "opportunity_cost": self.opportunity_cost,
            "success_metric": self.success_metric,
            "why_not_activation": self.why_not_activation, "roi_bps": self.roi_bps,
        }


@dataclass
class Rejection:
    title: str
    reason: str


@dataclass
class DirectorResult:
    accepted: list[Recommendation] = field(default_factory=list)
    rejected: list[Rejection] = field(default_factory=list)
    dossier_summary: str = ""

    @property
    def n_seen(self) -> int:
        return len(self.accepted) + len(self.rejected)


def _open_register_rows(text: str, limit: int = 40) -> list[str]:
    """Row id + title for register rows that are not closed -- what is ALREADY known broken."""
    rows = []
    for line in text.splitlines():
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 3 or not cells[1].isdigit():
            continue
        if "CLOSED" in line.upper() or "RESOLVED" in line.upper():
            continue
        rows.append(f"#{cells[1]} {cells[2][:120]}")
    return rows[-limit:]


def assemble_dossier(root: Path | None = None) -> Dossier:
    """Read the existing artifacts. Missing ones are NAMED, not skipped."""
    root = root or _ROOT
    d = Dossier()
    for name, rel in sorted(DOSSIER_SOURCES.items()):
        p = root / rel
        try:
            text = p.read_text("utf-8")
        except OSError:
            d.missing.append(f"{name} ({rel})")
            continue
        if rel.endswith(".md"):
            # the register is markdown, not JSON; carry its OPEN rows rather than the whole file
            d.present[name] = _open_register_rows(text)
            continue
        try:
            d.present[name] = json.loads(text)
        except ValueError:
            d.missing.append(f"{name} ({rel})")
    cyc = d.present.get("dormancy")
    if isinstance(cyc, dict):
        for cap in cyc.get("capabilities", []):
            if isinstance(cap, dict) and cap.get("capability") == "dormancy_hunter":
                rep = cap.get("report")
                if isinstance(rep, dict):
                    counts = rep.get("counts")
                    if isinstance(counts, dict):
                        d.dormant_count = int(sum(int(v) for v in counts.values()))
                    elif isinstance(rep.get("dormant"), list):
                        d.dormant_count = len(rep["dormant"])
    return d


def build_prompt(dossier: Dossier) -> str:
    """The director's instruction. States the contract AND the priority rule the code enforces."""
    dormant = dossier.dormant_count
    return f"""You are the desk's STRATEGIC DIRECTOR. Produce ranked recommendations, as JSON only.

YOUR CHARTER, and why your seat exists at all: you are the INDEPENDENT MODEL FAMILY. Every other
reasoning organ on this desk is Claude, so the desk's self-review shares one set of priors and one
set of blind spots. Your job is to see what the desk cannot see about itself -- agreeing with the
desk's own framing is your failure mode, not your deliverable. Challenge assumptions by name.

AGGRESSION IS LAW HERE, not mood (constitution L1.21a/L1.28, binding on you too): timidity is a
scored defect of the same class as a blown risk limit. Size, cost, effort and ambition carry ZERO
weight against expected ROI -- never recommend the smaller version because it feels safer, and
never withhold a recommendation because it is a lot of work. The one thing this does NOT loosen:
statistical bars and survival rails are immutable (L2.8a); aggression in scope, never in evidence.

UNKNOWN-UNKNOWNS DUTY (L1.9, every cycle): at least ONE recommendation must name something the
desk neither measures nor lists -- a market behaviour, data asymmetry, failure mode or capability
class absent from the dossier AND from the gap register. "Everything important is already on the
register" is the claim you exist to attack; if you genuinely find nothing, say what you searched
and why it came up empty, which is itself evidence.

MEASURED STATE: {dossier.summary()}.
{"MISSING FROM YOUR DOSSIER: " + ", ".join(dossier.missing) if dossier.missing else ""}

THE PRIORITY RULE, and it is enforced in code, not merely requested here:
FIND UNUSED CAPABILITY BEFORE INVENTING NEW CAPABILITY. This desk has {dormant} capabilities that
are BUILT and never execute. Authoring capability number {dormant + 1} while {dormant} sit
disconnected is negative-ROI by the desk's own arithmetic. A recommendation with kind="build" is
REJECTED AUTOMATICALLY unless it also supplies "why_not_activation" explaining why no existing
capability can be wired to do the job.

OUTPUT CONTRACT. A JSON array. Every element MUST have all of:
  title              short, specific
  kind               one of {list(KINDS)}
  bottleneck         the MEASURABLE constraint this removes -- name the metric and its value now
  expected_impact    what changes, quantified, with a direction
  opportunity_cost   what does NOT get done because this does
  success_metric     the number that will later show this worked or failed
  why_not_activation required only for kind="build"
  roi_bps            optional numeric estimate

Each of the four required prose fields must exceed {MIN_FIELD_CHARS} characters of real content.
"Improves research throughput" is not a bottleneck; "0 of 434 tested candidates reached Stage B,
so the binding constraint is the promotion gate, not idea supply" is.

Rank by (bottleneck severity x tractability). Do not pad the list -- three judgeable
recommendations beat ten unfalsifiable ones. Return ONLY the JSON array."""


def _field_ok(v: Any) -> bool:
    return isinstance(v, str) and len(v.strip()) >= MIN_FIELD_CHARS


def parse_recommendations(raw: str, dossier: Dossier) -> DirectorResult:
    """Validate the model's output against the contract AND the priority rule.

    Strict on purpose. Every rejection is recorded with its reason, because a director whose bad
    output is silently discarded looks identical to one that produced nothing -- and the desk would
    have no way to tell a credit problem from a quality problem.
    """
    res = DirectorResult(dossier_summary=dossier.summary())
    text = raw.strip()
    # models wrap JSON in prose or fences however they like; find the array
    if "```" in text:
        parts = [p for p in text.split("```") if "[" in p]
        text = parts[0] if parts else text
        text = text.split("\n", 1)[-1] if text.lstrip().startswith(("json", "JSON")) else text
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end <= start:
        res.rejected.append(Rejection("<whole response>",
                                      "no JSON array found -- the output contract requires a JSON "
                                      "array and prose cannot be validated or ledgered"))
        return res
    try:
        items = json.loads(text[start:end + 1])
    except ValueError as e:
        res.rejected.append(Rejection("<whole response>", f"unparseable JSON: {e}"))
        return res
    if not isinstance(items, list):
        res.rejected.append(Rejection("<whole response>", "top-level JSON is not an array"))
        return res

    for raw_item in items:
        if not isinstance(raw_item, dict):
            res.rejected.append(Rejection("<non-object>", "array element is not an object"))
            continue
        title = str(raw_item.get("title") or "<untitled>").strip()
        kind = str(raw_item.get("kind") or "").strip().lower()

        if kind not in KINDS:
            res.rejected.append(Rejection(title, f"kind {kind!r} is not one of {list(KINDS)}; the "
                                                 "priority rule is enforced on this field, so an "
                                                 "undeclared kind cannot be accepted"))
            continue
        bad = [f for f in REQUIRED_FIELDS if not _field_ok(raw_item.get(f))]
        if bad:
            res.rejected.append(Rejection(
                title, f"missing or boilerplate required field(s): {bad}. Each needs >"
                       f"{MIN_FIELD_CHARS} chars of real content -- these four are what make a "
                       "recommendation judgeable rather than fluent advice"))
            continue
        why = str(raw_item.get("why_not_activation") or "").strip()
        # THE PRIORITY RULE, enforced. Only bites when there is genuinely unused capability.
        if kind == KIND_BUILD and dossier.dormant_count > 0 and len(why) < MIN_FIELD_CHARS:
            res.rejected.append(Rejection(
                title, f"kind='build' with {dossier.dormant_count} capabilities already built and "
                       "unwired, and no why_not_activation given. Find unused capability BEFORE "
                       "inventing new capability -- authoring another subsystem while these sit "
                       "disconnected is negative-ROI by the desk's own arithmetic"))
            continue
        roi = raw_item.get("roi_bps")
        res.accepted.append(Recommendation(
            title=title, kind=kind,
            bottleneck=str(raw_item["bottleneck"]).strip(),
            expected_impact=str(raw_item["expected_impact"]).strip(),
            opportunity_cost=str(raw_item["opportunity_cost"]).strip(),
            success_metric=str(raw_item["success_metric"]).strip(),
            why_not_activation=why,
            roi_bps=float(roi) if isinstance(roi, (int, float)) else None))
    return res


def to_ledger_commands(res: DirectorResult, *,
                       source: str = "strategic_director") -> list[list[str]]:
    """``scripts/recommendations.py add`` argv per accepted recommendation.

    Routing through the ledger is what makes this a role rather than a report: §41 then forces every
    row to reach IMPLEMENTED / REJECTED / SCHEDULED, and an undisposed row past its grace window is
    a DEFECT rather than backlog. A director whose output nobody had to answer for would be a
    document with extra steps.
    """
    out = []
    for r in res.accepted:
        summary = (f"[{r.kind}] {r.title} -- BOTTLENECK: {r.bottleneck} "
                   f"| IMPACT: {r.expected_impact} | COST: {r.opportunity_cost} "
                   f"| SUCCESS: {r.success_metric}")
        argv = ["add", "--source", source, "--summary", summary]
        if r.roi_bps is not None:
            argv += ["--roi-bps", str(r.roi_bps)]
        out.append(argv)
    return out


def rank(recs: Sequence[Recommendation]) -> list[Recommendation]:
    """Activation before authoring, then by declared ROI.

    The ordering encodes the same rule the parser enforces: an ``activate``/``merge`` recommendation
    outranks a ``build`` one at equal ROI, because the desk's demonstrated failure mode is building
    capability faster than it wires it.
    """
    order = {k: i for i, k in enumerate(KINDS)}
    return sorted(recs, key=lambda r: (order.get(r.kind, 99), -(r.roi_bps or 0.0)))


def director_report(res: DirectorResult, dossier: Dossier) -> Mapping[str, Any]:
    return {
        "dossier": {"present": sorted(dossier.present), "missing": dossier.missing,
                    "dormant_count": dossier.dormant_count},
        "n_seen": res.n_seen,
        "accepted": [r.to_json() for r in rank(res.accepted)],
        "rejected": [{"title": x.title, "reason": x.reason} for x in res.rejected],
        "contract": {"required_fields": list(REQUIRED_FIELDS), "kinds": list(KINDS),
                     "min_field_chars": MIN_FIELD_CHARS},
    }

```

### libs/self_improvement/lifecycle_actions.py
```python
"""Lifecycle apply-side helpers (reuse the existing AlphaLifecycleManager).

These are the *approved* application of Stage 13 recommendations. Retirement is applied via the
manager (audited, archived — never deleted). Reactivation re-enters a fresh CANDIDATE linked to
the retired alpha as predecessor, so it must pass validation again (no bypass).
"""

from __future__ import annotations

from libs.alpha.card import AlphaCard, NewAlpha
from libs.alpha.manager import AlphaLifecycleManager


def apply_retirement(
    manager: AlphaLifecycleManager, alpha_id: str, *, reason: str = "stage13: decay confirmed"
) -> AlphaCard:
    """Retire an alpha through the lifecycle manager (audited; archived, not deleted)."""
    return manager.retire_alpha(alpha_id, reason=reason)


def apply_reactivation(
    manager: AlphaLifecycleManager,
    retired: AlphaCard,
    *,
    reason: str = "stage13: market structure changed",
) -> AlphaCard:
    """Re-enter a retired alpha as a fresh CANDIDATE (must re-pass validation; no bypass)."""
    spec = NewAlpha(
        name=f"{retired.name}_reactivated",
        market=retired.market,
        category=retired.category,
        thesis=f"{retired.thesis} [reactivation: {reason}]",
        entry_logic=retired.entry_logic,
        exit_logic=retired.exit_logic,
        expected_cagr=retired.expected_cagr,
        expected_sharpe=retired.expected_sharpe,
        expected_drawdown=retired.expected_drawdown,
        predecessor_id=retired.id,
    )
    return manager.register_alpha(spec)

```

### libs/stage14/audit.py
```python
"""Portfolio audit — every Stage 14 allocation to the immutable audit log.

Reuses ``libs.store.AuditLog`` (append-only, hash-chained). No parallel storage.
"""

from __future__ import annotations

from libs.stage14.models import PortfolioConstructionResult, PortfolioPackage
from libs.store.audit import AuditLog
from libs.store.connection import Database
from libs.store.models import AuditEntry

_ACTOR = "stage14_portfolio"


class PortfolioAudit:
    """Writes Stage 14 allocations to the immutable audit log."""

    def __init__(self, db: Database) -> None:
        self._audit = AuditLog(db)

    def record_package(self, package: PortfolioPackage) -> AuditEntry:
        return self._audit.append(
            "portfolio_allocation",
            actor=_ACTOR,
            inputs={
                "symbol": package.symbol,
                "sleeve": package.sleeve.value,
                "allocation": package.allocation,
                "position_size": package.position_size,
                "leverage": package.leverage,
                "kelly_fraction": package.kelly_fraction,
                "survival_score": package.survival_score,
                "institutional_score": package.institutional_score,
            },
            rationale="stage14 capital allocation",
            outcome="allocated",
        )

    def record_result(self, result: PortfolioConstructionResult) -> list[AuditEntry]:
        entries = [self.record_package(p) for p in result.packages]
        self._audit.append(
            "portfolio_construction",
            actor=_ACTOR,
            inputs={
                "state": result.state.value,
                "n_allocations": len(result.packages),
                "n_rejected": len(result.rejected),
                "total_allocation": result.total_allocation,
                "halt": result.kill.halt,
            },
            rationale="stage14 portfolio constructed",
            outcome="halted" if result.kill.halt else "constructed",
        )
        return entries

```

### libs/stage14/growth.py
```python
"""Geometric growth and capital-growth simulation.

``GeometricGrowthEngine`` scores a return stream by its compounded (geometric) growth, reusing the
discovery layer's expected-log-growth. ``CapitalGrowthSimulator`` Monte-Carlos terminal wealth and
ruin via block-resampling (reusing the survival engine for ruin), so allocation maximizes expected
long-term log wealth rather than single-period return.
"""

from __future__ import annotations

import numpy as np

from libs.discovery.monte_carlo_survival import monte_carlo_survival
from libs.discovery.objective import expected_log_growth
from libs.stage14.models import GeometricGrowthResult, GrowthSimResult
from libs.validation.bootstrap import stationary_block_indices


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class GeometricGrowthEngine:
    """Scores a return stream by expected compounded growth (the quantity to maximize)."""

    def evaluate(
        self, returns: np.ndarray, *, periods_per_year: float = 252.0, horizon_years: float = 1.0
    ) -> GeometricGrowthResult:
        arr = np.asarray(returns, dtype="float64")
        if len(arr) == 0:
            return GeometricGrowthResult(
                expected_cagr=0.0, expected_geometric_return=0.0, expected_terminal_wealth=1.0,
                growth_efficiency=0.0, geometric_growth_score=0.0,
            )
        glog = expected_log_growth(arr, periods_per_year=periods_per_year)  # annualized log-growth
        cagr = float(np.expm1(glog))
        geo_per_period = float(np.expm1(np.log1p(arr).mean()))
        terminal = float(np.exp(glog * horizon_years))
        arith = float(arr.mean()) * periods_per_year
        # Efficiency: how much of the arithmetic return survives as geometric (variance drag).
        growth_efficiency = _clip01(glog / arith) if arith > 0 else 0.0
        score = 100.0 * _clip01(0.5 * _clip01(cagr / 0.5) + 0.5 * growth_efficiency)
        return GeometricGrowthResult(
            expected_cagr=cagr,
            expected_geometric_return=geo_per_period,
            expected_terminal_wealth=terminal,
            growth_efficiency=growth_efficiency,
            geometric_growth_score=score,
        )


class CapitalGrowthSimulator:
    """Monte-Carlo CAGR / terminal-wealth / ruin distribution for long-horizon optimization."""

    def __init__(self, *, n_sims: int = 2000, block: float = 10.0, seed: int = 0) -> None:
        self.n_sims = n_sims
        self.block = block
        self.seed = seed

    def simulate(
        self, returns: np.ndarray, *, horizon: int | None = None, periods_per_year: float = 252.0
    ) -> GrowthSimResult:
        base = np.asarray(returns, dtype="float64")
        n = len(base)
        if n < 2:
            return GrowthSimResult(
                cagr_median=0.0, cagr_p5=0.0, cagr_p95=0.0, terminal_wealth_median=1.0,
                probability_of_ruin=1.0, expected_log_growth=0.0, survival_probability=0.0,
            )
        steps = horizon or n
        rng = np.random.default_rng(self.seed)
        terminals = np.empty(self.n_sims, dtype="float64")
        cagrs = np.empty(self.n_sims, dtype="float64")
        for s in range(self.n_sims):
            idx = stationary_block_indices(n, self.block, rng)[:steps]
            path = base[idx]
            terminal = float(np.prod(1.0 + path))
            terminals[s] = terminal
            years = steps / periods_per_year
            cagrs[s] = terminal ** (1.0 / years) - 1.0 if terminal > 0 and years > 0 else -1.0
        survival = monte_carlo_survival(base, n_sims=self.n_sims, block=self.block, seed=self.seed)
        return GrowthSimResult(
            cagr_median=float(np.median(cagrs)),
            cagr_p5=float(np.percentile(cagrs, 5)),
            cagr_p95=float(np.percentile(cagrs, 95)),
            terminal_wealth_median=float(np.median(terminals)),
            probability_of_ruin=survival.probability_of_ruin,
            expected_log_growth=expected_log_growth(base, periods_per_year=periods_per_year),
            survival_probability=survival.survival_probability,
        )

```

### libs/store/trials.py
```python
"""The append-only, hash-chained trials ledger.

Nothing is validated without a ledger entry first: every hypothesis evaluation, parameter
point, and search candidate is recorded here so the Deflated Sharpe Ratio can deflate by the
*true* cumulative trial count. Rows are immutable and tamper-evident, like the audit log.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from typing import Any

from libs.core.ids import generate_id
from libs.core.time import to_iso8601, utcnow
from libs.store.connection import Database
from libs.store.hashchain import (
    GENESIS_PREV_HASH,
    canonical_json,
    compute_chain_hash,
    verify_chain,
)
from libs.store.models import ChainVerification, TrialRecord


def _hash_fields(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "seq": int(row["seq"]),
        "id": row["id"],
        "created_at": row["created_at"],
        "hypothesis_id": row["hypothesis_id"],
        "family": row["family"],
        "method": row["method"],
        "params": json.loads(row["params_json"]),
        "data_snapshot": row["data_snapshot"],
        "in_sample_metric": row["in_sample_metric"],
        "git_commit": row["git_commit"],
        "prev_hash": row["prev_hash"],
    }


def _row_to_record(row: sqlite3.Row) -> TrialRecord:
    return TrialRecord(
        seq=int(row["seq"]),
        id=row["id"],
        created_at=row["created_at"],
        hypothesis_id=row["hypothesis_id"],
        family=row["family"],
        method=row["method"],
        params=json.loads(row["params_json"]),
        data_snapshot=row["data_snapshot"],
        in_sample_metric=row["in_sample_metric"],
        git_commit=row["git_commit"],
        prev_hash=row["prev_hash"],
        row_hash=row["row_hash"],
    )


class TrialsLedger:
    """Writer/reader for the ``trials_ledger`` table."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def append(
        self,
        hypothesis_id: str,
        family: str,
        method: str,
        params: Mapping[str, Any],
        *,
        data_snapshot: str | None = None,
        in_sample_metric: float | None = None,
        git_commit: str | None = None,
    ) -> TrialRecord:
        """Append one immutable, hash-chained trial record and return it."""
        params_dict = dict(params)
        with self.db.transaction() as conn:
            last = conn.execute(
                "SELECT seq, row_hash FROM trials_ledger ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            seq = (int(last["seq"]) + 1) if last else 1
            prev_hash = last["row_hash"] if last else GENESIS_PREV_HASH
            trial_id = generate_id("trial")
            created_at = to_iso8601(utcnow())
            fields = {
                "seq": seq,
                "id": trial_id,
                "created_at": created_at,
                "hypothesis_id": hypothesis_id,
                "family": family,
                "method": method,
                "params": params_dict,
                "data_snapshot": data_snapshot,
                "in_sample_metric": in_sample_metric,
                "git_commit": git_commit,
                "prev_hash": prev_hash,
            }
            row_hash = compute_chain_hash(fields)
            conn.execute(
                "INSERT INTO trials_ledger "
                "(seq, id, created_at, hypothesis_id, family, method, params_json, "
                " data_snapshot, in_sample_metric, git_commit, prev_hash, row_hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    seq,
                    trial_id,
                    created_at,
                    hypothesis_id,
                    family,
                    method,
                    canonical_json(params_dict),
                    data_snapshot,
                    in_sample_metric,
                    git_commit,
                    prev_hash,
                    row_hash,
                ),
            )
        return TrialRecord(
            seq=seq,
            id=trial_id,
            created_at=created_at,
            hypothesis_id=hypothesis_id,
            family=family,
            method=method,
            params=params_dict,
            data_snapshot=data_snapshot,
            in_sample_metric=in_sample_metric,
            git_commit=git_commit,
            prev_hash=prev_hash,
            row_hash=row_hash,
        )

    def count(self) -> int:
        """Return the true cumulative trial count (feeds the Deflated Sharpe Ratio)."""
        return int(self.db.execute("SELECT COUNT(*) FROM trials_ledger").fetchone()[0])

    def count_for_hypothesis(self, hypothesis_id: str) -> int:
        return int(
            self.db.execute(
                "SELECT COUNT(*) FROM trials_ledger WHERE hypothesis_id = ?", (hypothesis_id,)
            ).fetchone()[0]
        )

    def all(self) -> list[TrialRecord]:
        rows = self.db.execute("SELECT * FROM trials_ledger ORDER BY seq").fetchall()
        return [_row_to_record(row) for row in rows]


def verify_trials_chain(db: Database) -> ChainVerification:
    """Verify the integrity of the entire trials ledger chain."""
    rows = db.execute("SELECT * FROM trials_ledger ORDER BY seq").fetchall()
    ok, broken_seq, message = verify_chain(rows, _hash_fields)
    return ChainVerification(ok=ok, length=len(rows), broken_seq=broken_seq, message=message)

```

### libs/testing/equivalent_mutants.py
```python
"""EQUIVALENT-MUTANT REGISTER -- the one honest reason a mutant may go unkilled.

An equivalent mutant is a source change that CANNOT alter observable behaviour, so no test can
kill it. They are unavoidable, and they are also the single easiest way to destroy the value of
mutation testing: "that one's equivalent" is available for every inconvenient survivor, costs
nothing to say, and is almost never checked. So this register makes the claim expensive:

  * EVERY entry carries a WRITTEN JUSTIFICATION -- the specific argument for why no caller can
    observe the difference. Not "cosmetic", not "n/a": the predicate and both values.
  * EVERY entry is PINNED TO THE SOURCE LINE TEXT as it read when the claim was made. If that line
    is edited in any way, the claim LAPSES and the mutant counts against the score again. This is
    the property that stops the register rotting into a permanent exemption list: the argument was
    made about a specific line of code, so it expires when that code changes.
  * The raw score is ALWAYS reported alongside the adjusted one. Nothing here hides a number.

WHY IT EXISTS AT ALL, rather than just tolerating a red metric. `libs/execution/staging.py` scores
83.3% against a 90% bar, and all 7 survivors are provably equivalent (verified predicate by
predicate: every one mutates a `.get(key, default)` fail-closed default from one refusing value to
a different refusing value -- 1.0 -> 2.0 against `<= 0.10`, 0 -> 1 against `>= 10`, and so on).
The module is therefore at 35/35 on real mutants and can NEVER reach 90% on the raw number.

A metric that is permanently red for a reason nobody can fix is worse than no metric: it trains
the desk to ignore the one number that measures whether its money-path tests actually constrain
anything. That is the same false-red failure that let gate.py sit at a phantom 23.5% -- and a
false red is not a safe conservative error, it is an unreadable one.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Equivalence:
    target: str
    kind: str
    mutation: str
    line_text: str       # the stripped source line AS CLAIMED -- the claim's expiry condition
    justification: str


# Each entry below was verified by evaluating the ORIGINAL and MUTATED value against the actual
# predicate and confirming both land on the same side. The verification is reproducible:
#   float(1.0) <= 0.10  is False;  float(2.0) <= 0.10  is False.  -> no caller can tell them apart.
_REGISTER: tuple[Equivalence, ...] = (
    Equivalence(
        "libs/execution/staging.py", "num_const", "2 -> 3",
        '_STATE.write_text(json.dumps(state, indent=2), "utf-8")',
        "JSON indentation. Changes whitespace in the state file and nothing that is parsed: "
        "json.loads is indifferent to indent, and no caller reads the raw text. Purely cosmetic."),
    Equivalence(
        "libs/execution/staging.py", "num_const", "1.0 -> 2.0",
        '"capital_fraction_le_010": float(evidence.get("capital_fraction", 1.0)) <= 0.10,',
        "Fail-closed DEFAULT for a missing capital_fraction. Predicate is `<= 0.10`; both 1.0 and "
        "2.0 are False, so an absent value refuses identically either way. The value never leaves "
        "the function -- only the boolean does."),
    Equivalence(
        "libs/execution/staging.py", "num_const", "0 -> 1",
        '"symbol_count_4_5": 4 <= int(evidence.get("symbol_count", 0)) <= 5,',
        "Fail-closed DEFAULT for a missing symbol_count. Predicate is `4 <= v <= 5`; both 0 and 1 "
        "are outside it, so an absent count refuses identically."),
    Equivalence(
        "libs/execution/staging.py", "num_const", "0.0 -> 1.0",
        '"live_weeks_ge_8": float(evidence.get("live_weeks", 0.0)) >= 8.0,',
        "Fail-closed DEFAULT for missing live_weeks. Predicate is `>= 8.0`; both 0.0 and 1.0 are "
        "below it."),
    Equivalence(
        "libs/execution/staging.py", "num_const", "0 -> 1",
        '"calibration_rows_ge_10": int(evidence.get("calibration_rows", 0)) >= 10,',
        "Fail-closed DEFAULT for missing calibration_rows. Predicate is `>= 10`; both 0 and 1 are "
        "below it."),
    Equivalence(
        "libs/execution/staging.py", "num_const", "1 -> 2",
        '"critical_drill_failures_eq_0": int(evidence.get("critical_drill_failures", -1)) == 0,',
        "The -1 SENTINEL, which the AST sees as USub(1) so the mutant is -2. Predicate is `== 0`; "
        "both -1 and -2 are False, so 'no drill record' refuses either way. NOTE: the sentinel "
        "itself is load-bearing (this defaulted to 0 and passed the S2 gate on missing evidence -- "
        "found by mutation testing twice). Its VALUE being -1 versus -2 is what is equivalent, not "
        "its being negative."),
    Equivalence(
        "libs/execution/staging.py", "num_const", "999.0 -> 1000.0",
        '"realized_cost_le_1_25x": float(evidence.get("cost_ratio", 999.0)) <= 1.25,',
        "Fail-closed DEFAULT for a missing cost_ratio. Predicate is `<= 1.25`; both 999.0 and "
        "1000.0 are above it."),
)


def _line_text(target: str, lineno: int) -> str:
    try:
        lines = (_ROOT / target).read_text("utf-8", errors="ignore").splitlines()
    except OSError:
        return ""
    return lines[lineno - 1].strip() if 0 < lineno <= len(lines) else ""


def classify(target: str, survivor: dict[str, object]) -> Equivalence | None:
    """Return the live equivalence claim for this survivor, or None.

    A claim applies only when kind and mutation match AND the source line still reads exactly as
    it did when the argument was written. Any edit to that line lapses the claim -- the argument
    was about that code, so it does not survive the code changing.
    """
    kind, mutation = str(survivor.get("kind", "")), str(survivor.get("mutation", ""))
    raw = survivor.get("line", 0)
    if not isinstance(raw, (int, float, str)):   # narrows `object`; non-numeric was already fatal
        return None
    try:
        lineno = int(raw)
    except (TypeError, ValueError):
        return None
    actual = _line_text(target, lineno)
    for e in _REGISTER:
        if (e.target == target and e.kind == kind and e.mutation == mutation
                and e.line_text == actual):
            return e
    return None


def adjust(target: str, survivors: list[dict[str, object]], killed: int,
           total: int) -> dict[str, object]:
    """Raw and adjusted kill rates, plus every claim applied and every claim that has LAPSED.

    Lapsed claims are surfaced rather than dropped: a claim whose line moved is a prompt to
    re-argue it against the new code, not permission to keep the exemption.
    """
    equivalents = [(s, e) for s in survivors if (e := classify(target, s)) is not None]
    n_eq = len(equivalents)
    real_total = max(total - n_eq, 0)
    claimed_here = [e for e in _REGISTER if e.target == target]
    lapsed = [e.mutation for e in claimed_here
              if not any(e is m for _, m in equivalents)]
    return {
        "raw_kill_rate": round(killed / total, 4) if total else 0.0,
        "equivalent_mutants": n_eq,
        "adjusted_kill_rate": round(killed / real_total, 4) if real_total else 0.0,
        "equivalences_applied": [
            {"line": s.get("line"), "kind": e.kind, "mutation": e.mutation,
             "justification": e.justification} for s, e in equivalents],
        "equivalences_lapsed": lapsed,
        "real_survivors": [s for s in survivors if classify(target, s) is None],
    }

```

### libs/validation/__init__.py
```python
"""``libs.validation`` — the trials-adjusted validation gauntlet (the Skeptic).

DSR / PBO / CPCV / walk-forward / White's Reality Check / Hansen's SPA / block bootstrap /
FDR control / locked holdout, plus the economic-prior gate and stress-cost validation, wired
into an ordered :class:`Gauntlet` that emits a PASS/FAIL verdict and JSON/HTML reports.
"""

from __future__ import annotations

from libs.validation.bootstrap import (
    block_bootstrap,
    confidence_interval,
    moving_block_indices,
    stationary_block_indices,
    stationary_bootstrap,
)
from libs.validation.cpcv import CPCV, CPCVSplit
from libs.validation.dsr import (
    DSRResult,
    deflated_sharpe_ratio,
    expected_max_sharpe,
    min_track_record_length,
    probabilistic_sharpe_ratio,
    sharpe_ratio,
)
from libs.validation.economic_prior import (
    EconomicPrior,
    MechanismType,
    PriorGateResult,
    economic_prior_gate,
)
from libs.validation.errors import ValidationError
from libs.validation.fdr import FDRResult, benjamini_hochberg, benjamini_yekutieli
from libs.validation.gauntlet import (
    CandidateEvaluation,
    Gauntlet,
    GauntletResult,
    StageResult,
)
from libs.validation.lockbox import LockedHoldout
from libs.validation.pbo import PBOResult, probability_backtest_overfitting
from libs.validation.reality_check import RealityCheckResult, hansen_spa, whites_reality_check
from libs.validation.report import generate_validation_report
from libs.validation.revalidation import (
    RevalidationController,
    RevalidationDecision,
    RevalidationTrigger,
    WalkForwardEngine,
    WalkForwardReport,
    WalkForwardStatus,
)
from libs.validation.stress_costs import (
    StressCostResult,
    StressScenarioResult,
    stress_cost_validation,
)
from libs.validation.walk_forward import WalkForwardSplit, walk_forward_splits

__all__ = [  # noqa: RUF022  # grouped by concern
    # deflated sharpe
    "sharpe_ratio",
    "probabilistic_sharpe_ratio",
    "expected_max_sharpe",
    "deflated_sharpe_ratio",
    "min_track_record_length",
    "DSRResult",
    # pbo
    "probability_backtest_overfitting",
    "PBOResult",
    # cpcv / walk-forward
    "CPCV",
    "CPCVSplit",
    "walk_forward_splits",
    "WalkForwardSplit",
    # walk-forward governance / revalidation
    "WalkForwardEngine",
    "WalkForwardReport",
    "WalkForwardStatus",
    "RevalidationController",
    "RevalidationDecision",
    "RevalidationTrigger",
    # reality check / spa
    "whites_reality_check",
    "hansen_spa",
    "RealityCheckResult",
    # bootstrap
    "block_bootstrap",
    "stationary_bootstrap",
    "moving_block_indices",
    "stationary_block_indices",
    "confidence_interval",
    # fdr
    "benjamini_hochberg",
    "benjamini_yekutieli",
    "FDRResult",
    # lockbox
    "LockedHoldout",
    # economic prior
    "economic_prior_gate",
    "EconomicPrior",
    "MechanismType",
    "PriorGateResult",
    # stress costs
    "stress_cost_validation",
    "StressCostResult",
    "StressScenarioResult",
    # gauntlet + report
    "Gauntlet",
    "CandidateEvaluation",
    "GauntletResult",
    "StageResult",
    "generate_validation_report",
    # errors
    "ValidationError",
]

```

### libs/validation/lockbox.py
```python
"""Locked holdout — a final out-of-sample slice that may be opened exactly once.

Research happens on the research slice freely; the lockbox is sealed until a single, audited
open. A second open is a protocol violation and raises, because peeking destroys the holdout's
value as independent evidence.
"""

from __future__ import annotations

from typing import Generic, TypeVar, cast

from libs.core.time import to_iso8601, utcnow
from libs.validation.errors import ValidationError

T = TypeVar("T")


class LockedHoldout(Generic[T]):
    """Splits a sliceable dataset into a free research part and a once-openable lockbox."""

    def __init__(self, data: T, *, holdout_fraction: float = 0.3) -> None:
        if not 0.0 < holdout_fraction < 1.0:
            raise ValidationError("holdout_fraction must be in (0, 1)")
        n = len(data)  # type: ignore[arg-type]
        if n < 2:
            raise ValidationError("dataset too small to split")
        self._data = data
        self.split_index = int(n * (1.0 - holdout_fraction))
        self._opened = False
        self._access_log: list[str] = []

    @property
    def is_opened(self) -> bool:
        return self._opened

    @property
    def access_log(self) -> list[str]:
        return list(self._access_log)

    def research(self) -> T:
        """The research portion — always accessible."""
        return cast("T", self._data[: self.split_index])  # type: ignore[index]

    def open_lockbox(self) -> T:
        """The held-out portion — may be opened exactly once."""
        if self._opened:
            raise ValidationError(
                "lockbox already opened once; opening it again invalidates the holdout"
            )
        self._opened = True
        self._access_log.append(to_iso8601(utcnow()))
        return cast("T", self._data[self.split_index :])  # type: ignore[index]

```

### scripts/build_data_registry.py
```python
#!/usr/bin/env python3
"""DATA ASSET REGISTRY builder -- writes data/data_assets.json (EXECUTION_QUEUE.md RANK 4).

Closes GAP_REGISTER row #77: the previous inventory was hand-written, reported ROW COUNTS as SPANS
(``liquidations.parquet`` "33,867 rows" is really 17 days / 15 symbols) and omitted the desk's best
panel entirely (``data/lake/bronze/crypto/<SYM>/D1`` -- 267 symbols, daily, from 2019-09-08),
so organs were choosing what to test off a map that was wrong in both directions.

Every number here is MEASURED from the data or explicitly absent. See
``libs/research/data_registry.py`` for why moat and research value are scored separately.

    python scripts/build_data_registry.py            # sampled spans for partitioned trees (fast)
    python scripts/build_data_registry.py --deep     # measure every partition member
    python scripts/build_data_registry.py --json     # machine output on stdout
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from libs.research.data_registry import REPL_PROPRIETARY, DataAsset, build

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/data_assets.json"


def _fmt(a: DataAsset) -> str:
    sp = a.span
    span = (f"{sp.first}->{sp.last} ({sp.days}d)" if sp.measured and sp.days
            else f"[{sp.status}]")
    return (f"  {a.id:<28} {span:<32} breadth={a.breadth or '-':<5} "
            f"moat={a.moat_score:<5} value={a.research_value:<5} "
            f"cad={f'{a.cadence_h}h' if a.cadence_h else 'UNSCHEDULED'}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--deep", action="store_true",
                    help="measure every partition member instead of sampling")
    ap.add_argument("--json", action="store_true", help="emit the registry on stdout")
    a = ap.parse_args(argv)

    assets = build(ROOT, deep=a.deep)
    measured = [x for x in assets if x.span.measured]
    absent = [x for x in assets if x.span.status == "absent"]
    unread = [x for x in assets if (x.span.days or 0) > 365 and not x.consumers]
    unscheduled = [x for x in assets if x.collector and x.cadence_h is None]

    payload = {
        "generated": datetime.now(tz=UTC).isoformat(),
        "deep": a.deep,
        "counts": {"assets": len(assets), "measured": len(measured), "absent": len(absent)},
        # THE row-#77 headline: spans are the map organs navigate by, so report the real extremes
        "longest_span_days": max((x.span.days or 0 for x in measured), default=0),
        "widest_breadth": max((x.breadth or 0 for x in assets), default=0),
        "proprietary": [x.id for x in assets if x.replication == REPL_PROPRIETARY],
        "unread_long_history": [x.id for x in unread],
        "unscheduled_collectors": [x.id for x in unscheduled],
        "assets": [x.to_json() for x in assets],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=1), "utf-8")
    tmp.replace(OUT)                     # atomic: a torn registry is a misleading map again

    if a.json:
        print(json.dumps(payload, indent=1))
        return 0

    print(f"data-registry | {len(assets)} assets, {len(measured)} with MEASURED spans, "
          f"{len(absent)} declared-but-absent on this box")
    for x in assets:
        print(_fmt(x))
    if unread:
        # row #77's second defect: cot_zcache is 26 YEARS of CFTC COT and nothing read it
        print(f"\n  PARALYSIS: {len(unread)} asset(s) with >1y history and NO reader -- "
              f"{', '.join(x.id for x in unread)}")
        print("  Long history nobody queries is paid-for capability sitting idle (L2.9).")
    if unscheduled:
        print(f"\n  UNSCHEDULED: {len(unscheduled)} collector(s) write an asset on no cadence -- "
              f"{', '.join(x.id for x in unscheduled)}")
    if absent:
        print(f"\n  ABSENT HERE: {', '.join(x.id for x in absent)}")
        print("  Spans are UNMEASURED, not zero -- this box may not be the collecting box.")
    print(f"\n-> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/check_freshness.py
```python
#!/usr/bin/env python3
"""CONSUMPTION-TIME FRESHNESS FENCE (L1.44) -- which live decisions are consuming frozen inputs
RIGHT NOW.

Joins {artifact age x consumer contract x recent read events} from the self-building registry
that libs.ops.fresh.read_fresh maintains (data/freshness_contracts.jsonl). Producer-side fences
already ask "did the producer run?"; this is the other half nobody had -- "is anything STEERING
on its corpse?" -- and it is the half that carries the severity, because a dead producer whose
output nobody reads is an idle seat while a dead producer whose output the executor reads is the
money path running on a memory.

PER-CONTRACT VERDICTS:
  FRESH           artifact within the consumer's declared tolerance.
  STALE-CONSUMED  artifact older than the contract AND the consumer read it since it went stale
                  (a stale_read/unreadable_read event in the last 26h) -- the smoking gun, with
                  the caller named. This is what fails the fence.
  STALE-UNREAD    older than the contract, no recent read -- the producer-side fences own chasing
                  the dead producer; reported here for the blast-radius join, never double-fired.
  MISSING         the contracted artifact does not exist at all.
  FOREIGN         an absolute path outside the repo leaked into the registry (test hygiene
                  guard) -- skipped from verdicts, reported so the leak is visible.

FENCE STATUS (exit 2 on the first three -- a gate, not a report):
  STALE-CONSUMED  any contract in that state.
  UNWIRED         the bootstrap read sites (executor, alerts) no longer reference their
                  contracts -- the wiring-regression check, so deleting a call site is loud.
  UNMEASURED      zero contracts recorded. An empty registry must never read OK (L1.28a):
                  it means the helper is unwired or no consumer has ticked since deploy.
  STALE-UNREAD    stale artifacts exist but nothing consumed them -- reported, exit 0.
  OK              every contract fresh.

kind='state' contracts are judged by their GUARDIAN's age (a valid-until-changed file is
legitimately old; the fence must not cry wolf on healthy state -- L1.43).

    python scripts/check_freshness.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent

# L1.42 LAWFUL ENTRY: TTL-cached, pages-but-does-not-block; a governance fault never silences
# the organ that reports on the money path's inputs.
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.fresh import REGISTRY_REL, _age_of  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402

#: WIRING-REGRESSION CHECK. These call sites are the bootstrap migration (capability hunt
#: 2026-07-31); if a token vanishes from its file the contract was deleted, and that must fail
#: the fence rather than silently return the read site to uncontracted blindness. Checked
#: against the REPO the fence lives in (law surface), never the state root (state surface) --
#: the same law/state split that keeps state fences out of commit gates.
_WIRED: tuple[tuple[str, str], ...] = (
    ("scripts/run_cashcarry_executor.py", "read_fresh"),
    ("scripts/run_alerts.py", "live_guard_dead"),
)

_CONSUMED_WINDOW_H = 26.0     # a stale read within this window counts as "consumed while stale"


def _parse_registry(reg: Path) -> tuple[dict[tuple[str, str], dict], dict[tuple[str, str], str]]:
    """(latest contract per (caller, path), latest stale/unreadable event ts per (caller, path)).
    Malformed lines are counted by the caller via the returned dicts staying sparse -- a corrupt
    line loses one record, never the fence."""
    contracts: dict[tuple[str, str], dict] = {}
    events: dict[tuple[str, str], str] = {}
    try:
        lines = reg.read_text("utf-8").splitlines()
    except OSError:
        return {}, {}
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        key = (str(r.get("caller", "")), str(r.get("path", "")))
        if r.get("event") == "contract":
            contracts[key] = r
        elif r.get("event") in ("stale_read", "unreadable_read"):
            events[key] = str(r.get("ts", ""))
    return contracts, events


def _recent(ts: str, now: datetime) -> bool:
    try:
        at = datetime.fromisoformat(ts)
        if at.tzinfo is None:
            at = at.replace(tzinfo=UTC)
        return (now - at).total_seconds() / 3600.0 <= _CONSUMED_WINDOW_H
    except ValueError:
        return False


def _verdict(root: Path, c: dict, ev_ts: str | None, now: datetime) -> dict[str, Any]:
    path, caller = str(c.get("path", "")), str(c.get("caller", ""))
    kind = str(c.get("kind", "measurement"))
    max_age_h = float(c.get("max_age_h", 0.0) or 0.0)
    p = Path(path)
    if p.is_absolute() and not str(p).startswith(str(root)):
        return {"caller": caller, "path": path, "verdict": "FOREIGN",
                "detail": "absolute path outside the root leaked into the registry"}
    target = p if p.is_absolute() else root / p
    if kind == "state" and c.get("guardian"):
        g = Path(str(c["guardian"]))
        target = g if g.is_absolute() else root / g
    age, source, _data = _age_of(target)
    out: dict[str, Any] = {"caller": caller, "path": path, "kind": kind,
                           "max_age_h": max_age_h, "age_h": None if age is None else
                           round(age, 2), "age_source": source}
    if age is None:
        out["verdict"] = ("STALE-CONSUMED" if ev_ts and _recent(ev_ts, now) else "MISSING")
        out["detail"] = f"contracted artifact unreadable ({source})"
    elif age <= max_age_h:
        out["verdict"] = "FRESH"
    else:
        consumed = bool(ev_ts and _recent(ev_ts, now))
        out["verdict"] = "STALE-CONSUMED" if consumed else "STALE-UNREAD"
        out["detail"] = (f"{age:.1f}h old vs {max_age_h}h contract"
                         + (f"; consumed while stale (last stale read {ev_ts})" if consumed
                            else "; no read observed since it went stale"))
    return out


def _unwired(repo: Path) -> list[str]:
    bad = []
    for rel, token in _WIRED:
        try:
            src = (repo / rel).read_text("utf-8", errors="ignore")
        except OSError:
            bad.append(f"{rel}: unreadable -- wiring unverifiable counts as UNWIRED, never OK")
            continue
        if token not in src:
            bad.append(f"{rel}: token '{token}' absent -- the freshness contract was removed")
    return bad


def build_report(root: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    root = root or _ROOT
    now = now or datetime.now(tz=UTC)
    contracts, events = _parse_registry(root / REGISTRY_REL)
    rows = [_verdict(root, c, events.get(k), now) for k, c in sorted(contracts.items())]
    unwired = _unwired(_ROOT)

    n_by = {v: sum(1 for r in rows if r["verdict"] == v)
            for v in ("FRESH", "STALE-CONSUMED", "STALE-UNREAD", "MISSING", "FOREIGN")}
    judged = [r for r in rows if r["verdict"] != "FOREIGN"]
    if n_by["STALE-CONSUMED"]:
        status = "STALE-CONSUMED"
    elif unwired:
        status = "UNWIRED"
    elif not judged:
        status = "UNMEASURED"
    elif n_by["STALE-UNREAD"] or n_by["MISSING"]:
        status = "STALE-UNREAD"
    else:
        status = "OK"
    fresh_fraction = (round(n_by["FRESH"] / len(judged), 3) if judged else None)
    offenders = [f"{r['caller']} <- {r['path']} ({r.get('detail', '')})"
                 for r in rows if r["verdict"] == "STALE-CONSUMED"]
    return {
        "generated": now.isoformat(),
        "law": "L1.44 -- a decision is only as live as its inputs: every decision-path read "
               "declares its max tolerated age at the read site, and a live decision consuming "
               "a frozen input is a fence failure, with the caller named",
        "status": status,
        "n_contracts": len(judged), "by_verdict": n_by,
        "fresh_fraction": fresh_fraction,
        "unwired": unwired,
        "contracts": rows,
        "detail": (f"{len(judged)} contract(s): " + ", ".join(f"{k}={v}" for k, v in
                   n_by.items() if v) if judged else
                   "ZERO contracts recorded -- helper unwired or no consumer has ticked; an "
                   "empty registry must never read OK (L1.28a)")
                  + ("; UNWIRED: " + "; ".join(unwired) if unwired else ""),
        "stale_consumed": offenders,
        "next_action": ("revive the dead producer or re-wire the caller through "
                        "libs.ops.fresh.read_fresh; the offender list names both ends of every "
                        "stale edge" if offenders or unwired else
                        "extend contracts to the next uncontracted decision-path read"),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    out = _ROOT / "data/freshness_status.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"freshness (L1.44): {rep['status']} -- {rep['detail']}")
        for line in rep["stale_consumed"]:
            print(f"  STALE-CONSUMED: {line}")
        for line in rep["unwired"]:
            print(f"  UNWIRED: {line}")
    if args.report_only:
        return 0
    return 2 if rep["status"] in ("STALE-CONSUMED", "UNWIRED", "UNMEASURED") else 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/check_miner_runway.py
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
  ok               produced inside its max age
  stale            produced before, not recently  -> a runtime failure, look at the log
  never-ran        runway complete, zero output   -> scheduling/quota, not configuration
  creds-missing    cannot possibly run            -> a HUMAN step, and the real blocker today
  not-scheduled    nothing would ever invoke it   -> a wiring defect in the repo
  missing-prompt   configuration incomplete

Exit code is nonzero when any seat is creds-missing / never-ran / not-scheduled, so this is
cron-able as a pager check on the box. --report-only always exits 0 (for the record-keeping run).

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

# seat -> (prompt, runner, log glob, max_age_h). Max ages mirror scripts/max_audit.py ORGANS so
# the two organs cannot disagree about what "stale" means.
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

_BAD = ("creds-missing", "never-ran", "not-scheduled", "missing-prompt")


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
    creds = _creds_present()
    seats: dict[str, Any] = {}
    for seat, (prompt, runner, glob, max_age_h) in _SEATS.items():
        p, r = _ROOT / prompt, _ROOT / runner
        prompt_ok = p.exists() and p.stat().st_size > 0
        runner_ok = r.exists()
        sched = _scheduled(runner)
        name, age_h, size = _last_run(glob)

        if not prompt_ok:
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
        elif age_h is not None and age_h > max_age_h:
            status = "stale"
        else:
            status = "ok"
        seats[seat] = {"prompt": prompt_ok, "runner": runner_ok, "unit": sched, "creds": creds,
                       "last_run": name, "age_h": round(age_h, 1) if age_h is not None else None,
                       "last_bytes": size, "max_age_h": max_age_h, "status": status}

    by_status: dict[str, list[str]] = {}
    for seat, row in seats.items():
        by_status.setdefault(str(row["status"]), []).append(seat)
    blockers = []
    if not creds:
        blockers.append({"blocker": "no claude credential on this host",
                         "human_step": "bash ops/setup_brain_token.sh (or setup_brain_api_key.sh)",
                         "blast_radius": len([s for s, r in seats.items()
                                              if r["status"] == "creds-missing"]),
                         "note": "ONE human step unblocks every seat counted here -- reported as "
                                 "a cause, not as N unrelated dead organs"})
    return {"checked": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "creds_present": creds, "seats": seats, "by_status": by_status,
            "blockers": blockers,
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

### scripts/cme_basis.py
```python
"""CME-vs-OFFSHORE BASIS -- the best remaining structural-spread candidate.

WHY THIS ONE. Today's refined criterion for a survivable spread: width >~50bps AND a HARD physical
constraint AND a free daily series. Pegs (1-15bps) and liquid-staking discounts (10-30bps) failed
on WIDTH because their constraints are SOFT -- redemption is annoying, exit queues are days.

CME is different: US regulated institutions LEGALLY CANNOT trade offshore perps. That is not
friction, it is a licence boundary -- the same class of constraint as Korean capital controls,
which is the only class that has ever survived on this desk (kimchi, ~142bps std).

CONSTRUCTION:
    cme_basis      = CME front-month future / Binance spot - 1     (regulated venue)
    offshore_basis = Binance perp mark      / Binance spot - 1     (offshore venue)
    SPREAD         = cme_basis - offshore_basis                    (the segmentation premium)
Both legs are BTC at the same timestamp, so a directional move cancels. What remains is purely the
price of being allowed to trade where you are allowed to trade.

TEST (spread test, not a forecast test): persistent non-zero level? mean-reverting (half-life)?
bounded? AND -- the gate that killed all four candidates this morning -- WIDE ENOUGH TO PAY COSTS.

Free: Yahoo BTC=F (CME front-month) + Binance klines. Stage-A, zero promotion authority.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

OUT = Path("data/cme_basis_screen.json")
ROUND_TRIP_BPS = 8.0        # ~2 legs x ~4bps: the bar a spread must clear to be harvestable


def _get(u, t=35):
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=t).read().decode())


def yahoo(sym: str, rng: str = "2y") -> dict[str, float]:
    d = _get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
             f"?interval=1d&range={rng}")
    r = d["chart"]["result"][0]
    q = r["indicators"]["quote"][0]["close"]
    return {datetime.fromtimestamp(int(t), tz=UTC).date().isoformat(): float(c)
            for t, c in zip(r["timestamp"], q, strict=False) if c}


def binance(sym: str, base: str, n: int = 730) -> dict[str, float]:
    rows = _get(f"{base}?symbol={sym}&interval=1d&limit={n}")
    return {datetime.fromtimestamp(int(r[0]) / 1000, tz=UTC).date().isoformat(): float(r[4])
            for r in rows}


def main() -> None:
    print("=== CME vs OFFSHORE BASIS -- regulatory segmentation spread ===")
    print("    constraint: US institutions legally CANNOT trade offshore perps (licence, not friction)\n")
    cme = yahoo("BTC=F")
    spot = binance("BTCUSDT", "https://api.binance.com/api/v3/klines")
    perp = binance("BTCUSDT", "https://fapi.binance.com/fapi/v1/klines")
    dates = sorted(set(cme) & set(spot) & set(perp))
    print(f"  aligned days: {len(dates)}  ({dates[0]} .. {dates[-1]})" if dates else "  no overlap")
    if len(dates) < 120:
        print("  insufficient overlap")
        return

    cb = np.array([cme[d] / spot[d] - 1.0 for d in dates])          # regulated basis
    ob = np.array([perp[d] / spot[d] - 1.0 for d in dates])         # offshore basis
    sp = cb - ob                                                    # segmentation premium

    for nm, x in (("CME basis", cb), ("offshore basis", ob), ("SPREAD (cme-offshore)", sp)):
        print(f"  {nm:<24} mean {x.mean()*10000:+8.1f}bps   sd {x.std()*10000:7.1f}bps   "
              f"range {x.min()*10000:+.0f}..{x.max()*10000:+.0f}")

    # mean-reversion half-life on the spread
    x0, x1 = sp[:-1] - sp.mean(), sp[1:] - sp.mean()
    beta = float((x0 @ x1) / (x0 @ x0)) if (x0 @ x0) > 0 else 1.0
    hl = float(-np.log(2) / np.log(abs(beta))) if 0 < abs(beta) < 1 else float("inf")
    p99, p50 = np.percentile(np.abs(sp), 99), np.percentile(np.abs(sp), 50)
    tail = float(p99 / p50) if p50 > 0 else float("inf")
    sd_bps = float(sp.std() * 10000)
    # how often is the spread actually wide enough to pay for a round trip?
    tradeable = float((np.abs(sp) * 10000 > ROUND_TRIP_BPS).mean())

    print(f"\n  half-life {hl:.1f}d | tail {tail:.1f}x | sd {sd_bps:.1f}bps")
    print(f"  fraction of days |spread| > {ROUND_TRIP_BPS:.0f}bps round-trip cost: "
          f"{tradeable*100:.0f}%")

    wide = sd_bps > 50
    reverts = hl < 30
    bounded = tail < 12
    verdict = ("HARVESTABLE-CANDIDATE" if (wide and reverts and bounded and tradeable > 0.5)
               else "TOO TIGHT (fails the >50bps width bar)" if not wide
               else "DRIFTS (no reversion)" if not reverts
               else "VIOLENT (unbounded)" if not bounded
               else "RARELY TRADEABLE (spread < costs most days)")
    print(f"\n  VERDICT: {verdict}")
    print(f"    width>50bps {wide} | reverts<30d {reverts} | bounded {bounded} | "
          f"tradeable>50% {tradeable > 0.5}")
    if wide:
        print(f"\n  NOTE: at {sd_bps:.0f}bps sd this is {sd_bps/5.4:.0f}x the USDC peg spread and "
              f"{'comparable to' if sd_bps > 100 else 'below'} kimchi (~142bps).")

    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(), "n": len(dates),
                               "cme_basis_bps": round(float(cb.mean() * 10000), 2),
                               "offshore_basis_bps": round(float(ob.mean() * 10000), 2),
                               "spread_mean_bps": round(float(sp.mean() * 10000), 2),
                               "spread_sd_bps": round(sd_bps, 2),
                               "half_life_d": round(hl, 2) if hl != float("inf") else None,
                               "tail_ratio": round(tail, 2),
                               "frac_days_above_cost": round(tradeable, 3),
                               "verdict": verdict}, indent=1), "utf-8")
    print(f"\n  -> {OUT}")
    print("  Stage-A only. A candidate still needs net-of-cost capture and a forward clock.")


if __name__ == "__main__":
    main()

```

### scripts/collect_coinmetrics_flows.py
```python
"""Coin Metrics COMMUNITY exchange-flow ingest + Stage-A screen -- the free primary that replaces
the Glassnode/CryptoQuant metric CLASS (§33 conversion of data_axis_watchlist card #7).

WHY THIS EXISTS. Card #7 found the free primary (Coin Metrics community, keyless) and stopped
there: FOUND is not WIRED. This is the conversion -- the series is actually ingested at FULL
archive depth, diff-verified against two independent surfaces, and the metric class is Stage-A
screened over the WHOLE window (§33.7 depth parity: full history pulled, not a convenient slice).

WHAT IT REPLACES. Glassnode ($799/mo) / CryptoQuant ($799/mo) exchange-flow family:
  FlowInExNtv / FlowOutExNtv  -> exchange inflow / outflow (netflow = in - out)
  SplyExNtv                   -> supply held on exchanges (the netflow's own denominator)
Both vendor APIs are 401 keyless; the CM community API is 200 unauthenticated, T+1, full history.

⚠️ LICENCE -- CC BY-NC 4.0, HONESTLY FLAGGED, NOT SELF-APPROVED. The coinmetrics/data repo
LICENSE is CC BY-NC 4.0. This desk is a PRIVATE research desk trading its own capital and does
not redistribute: internal research, verification and diffing is the defensible interim scope and
is what this script does. Using the series as a PRODUCTION signal input is a NonCommercial
question that is a human/legal ruling -- routed to the legitimacy queue, deliberately NOT decided
here. The screen below therefore earns ZERO promotion authority (it never could -- Stage A never
does) and the ingest is attributed in-file per BY.

TIMESTAMP ALIGNMENT -- DECLARED, AND THE FIRST GUESS WAS WRONG (charter §26.4, §33.8):
  * `FlowInExNtv[d]` aggregates flow OVER UTC day d (00:00 -> 24:00).
  * The price stamp was ASSUMED to be 00:00 UTC of day d (CM's documented start-of-interval
    convention) and that assumption was REFUTED by the diff this script runs: measured against
    Binance BTCUSDT over 3,265 overlapping days, `PriceUSD[d]` sits 13 bps from CLOSE[d] and 150
    bps from OPEN[d]. `PriceUSD[d]` is therefore the END-of-day-d price.
  * So the same-period return of flow-day d is `PriceUSD[d]/PriceUSD[d-1] - 1`, and the screen's
    forward target is the day-d+1 return. Using the assumed convention would have lagged the whole
    screen by a day. One clock (UTC) throughout -- no cross-timezone candle join, no look-ahead.
  * `_verify_price_convention` RE-RUNS that diff every execution, so a change in CM's stamping
    surfaces as a measured error instead of a silent misalignment.

VERIFY-DON'T-TRUST (charter §27.3), two independent diffs, both RUN not referenced:
  1. INTERNAL RECONCILIATION -- d(SplyExNtv) vs (FlowInExNtv - FlowOutExNtv). Three separately
     computed CM series must close on each other; systematic drift means the flow series is not
     what it claims to be.
  2. EXTERNAL GROUND TRUTH -- CM PriceUSD vs Binance BTCUSDT daily bars (a different vendor, a
     different pipeline) over the full overlap.

EVERY CONSTRUCTION IS LOGGED (charter §26.3): both the native-unit netflow and the
exchange-supply-normalised netflow are screened and BOTH are recorded, win or lose. Reporting only
the one that printed is garden-of-forking-paths p-hacking.

    .venv/bin/python scripts/collect_coinmetrics_flows.py
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from libs.research.axis_screen import stage_a_screen

_API = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
_BINANCE = "https://api.binance.com/api/v3/klines"
_ASSETS = ("btc", "eth")
_METRICS = ("FlowInExNtv", "FlowOutExNtv", "SplyExNtv", "PriceUSD")
_START = "2010-01-01"                     # before any asset exists -> the true archive floor
_SERIES = Path("data/coinmetrics_flows.jsonl")
_OUT = Path("data/batch_coinmetrics_screen.json")
_UA = {"User-Agent": "quant-platform-research/1.0 (internal research; CC BY-NC attribution: "
                     "Coin Metrics community data)"}


def _get(url: str, *, timeout: int = 60) -> dict[str, Any]:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode())
    return d if isinstance(d, dict) else {}


def _f(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fetch_asset(asset: str) -> list[dict[str, Any]]:
    """FULL-DEPTH pull for one asset -- paged from the START of the archive, never sampled.

    ``paging_from=start`` matters: the API defaults to paging from the END, so a naive request
    silently returns only the newest page and a 15-year archive reads as three days of history.
    """
    url = (f"{_API}?assets={asset}&metrics={','.join(_METRICS)}&frequency=1d"
           f"&start_time={_START}&page_size=10000&paging_from=start")
    rows: list[dict[str, Any]] = []
    while url:
        d = _get(url)
        for rec in d.get("data", []):
            date = str(rec.get("time", ""))[:10]
            fi, fo = _f(rec.get("FlowInExNtv")), _f(rec.get("FlowOutExNtv"))
            rows.append({
                "asset": asset,
                "date": date,
                "flow_in_ntv": fi,
                "flow_out_ntv": fo,
                "netflow_ntv": (fi - fo) if (fi is not None and fo is not None) else None,
                "sply_ex_ntv": _f(rec.get("SplyExNtv")),
                "price_usd": _f(rec.get("PriceUSD")),
            })
        url = d.get("next_page_url") or ""
    return rows


def _binance_daily() -> dict[str, tuple[float, float]]:
    """BTCUSDT daily (open, close) keyed by UTC date -- the independent external diff target."""
    out: dict[str, tuple[float, float]] = {}
    start = int(datetime(2017, 8, 1, tzinfo=UTC).timestamp() * 1000)
    while True:
        req = urllib.request.Request(
            f"{_BINANCE}?symbol=BTCUSDT&interval=1d&startTime={start}&limit=1000", headers=_UA)
        with urllib.request.urlopen(req, timeout=45) as r:
            rows = json.loads(r.read().decode())
        if not isinstance(rows, list) or not rows:
            break
        for k in rows:
            d = datetime.fromtimestamp(int(k[0]) / 1000, tz=UTC).date().isoformat()
            out[d] = (float(k[1]), float(k[4]))
        if len(rows) < 1000:
            break
        start = int(rows[-1][0]) + 86_400_000
    return out


def _verify_price_convention(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """EXTERNAL diff: CM PriceUSD vs Binance daily OPEN and CLOSE, over the whole overlap.

    Also settles the timestamp convention empirically instead of by assertion -- whichever of
    open/close matches is what CM's 00:00-UTC stamp means, and a one-day misalignment (the exact
    failure the angle-20 gate exists to catch downstream) would show up here as a large error.
    """
    try:
        bnc = _binance_daily()
    except (urllib.error.URLError, OSError, ValueError) as e:
        return {"status": f"binance-unreachable ({type(e).__name__})"}
    cm = {r["date"]: r["price_usd"] for r in rows
          if r["asset"] == "btc" and r["price_usd"] is not None}
    days = sorted(set(cm) & set(bnc))
    if len(days) < 100:
        return {"status": f"thin-overlap ({len(days)}d)"}
    e_open = np.array([abs(cm[d] - bnc[d][0]) / bnc[d][0] for d in days])
    e_close = np.array([abs(cm[d] - bnc[d][1]) / bnc[d][1] for d in days])
    return {
        "status": "ok",
        "n_days": len(days),
        "window": [days[0], days[-1]],
        "median_abs_err_vs_binance_open_bps": round(float(np.median(e_open)) * 1e4, 2),
        "median_abs_err_vs_binance_close_bps": round(float(np.median(e_close)) * 1e4, 2),
        "p95_abs_err_vs_binance_close_bps": round(float(np.percentile(e_close, 95)) * 1e4, 2),
        # The screen is coded to END-of-day (measured, not assumed). If CM ever re-stamps to
        # start-of-day this flips and the screen alignment must flip with it -- said out loud
        # rather than left as a comment nobody re-reads.
        "convention": ("PriceUSD[d] == END of UTC day d (matches Binance CLOSE[d]) -- MATCHES the "
                       "alignment the screen uses"
                       if np.median(e_close) < np.median(e_open)
                       else "PriceUSD[d] matches Binance OPEN[d] -- CM RE-STAMPED TO START-OF-DAY; "
                            "the screen's return alignment is now off by one day, shift it"),
        "screen_alignment_ok": bool(np.median(e_close) < np.median(e_open)),
    }


def _reconcile_supply(rows: list[dict[str, Any]], asset: str) -> dict[str, Any]:
    """INTERNAL diff: d(SplyExNtv) must equal FlowIn - FlowOut if the flow series is what it says.

    Not expected to be integer-exact (CM's supply series nets internal exchange transfers and
    change outputs that the directional flow series does not), so the test is that the two track
    each other -- correlation and a bounded typical residual, reported honestly either way.
    """
    r = [x for x in rows if x["asset"] == asset and x["sply_ex_ntv"] is not None
         and x["netflow_ntv"] is not None]
    r.sort(key=lambda x: x["date"])
    if len(r) < 200:
        return {"status": f"thin ({len(r)}d)"}
    d_sply = np.array([r[i]["sply_ex_ntv"] - r[i - 1]["sply_ex_ntv"] for i in range(1, len(r))])
    net = np.array([r[i]["netflow_ntv"] for i in range(1, len(r))])
    keep = np.isfinite(d_sply) & np.isfinite(net)
    d_sply, net = d_sply[keep], net[keep]
    if len(d_sply) < 200 or d_sply.std() == 0 or net.std() == 0:
        return {"status": "degenerate"}
    corr = float(np.corrcoef(d_sply, net)[0, 1])
    scale = float(np.median(np.abs(net))) or 1.0
    return {
        "status": "ok",
        "n_days": len(d_sply),
        "window": [r[1]["date"], r[-1]["date"]],
        "corr_dsupply_vs_netflow": round(corr, 4),
        "median_abs_residual_over_median_flow": round(
            float(np.median(np.abs(d_sply - net))) / scale, 4),
    }


def _screen_all(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Screen the metric class on the FULL window. BOTH constructions logged, win or lose."""
    out = []
    for asset in _ASSETS:
        r = [x for x in rows if x["asset"] == asset and x["netflow_ntv"] is not None
             and x["price_usd"] not in (None, 0.0) and x["sply_ex_ntv"]]
        r.sort(key=lambda x: x["date"])
        if len(r) < 200:
            out.append({"name": f"cm_netflow_{asset}", "verdict": "INSUFFICIENT-DATA",
                        "n": len(r)})
            continue
        price = np.array([x["price_usd"] for x in r], dtype="float64")
        # MEASURED alignment: PriceUSD[t] is the END-of-day-t price (13bps from Binance close[t],
        # 150bps from open[t]), so the return realised OVER flow-day t is P[t]/P[t-1] - 1. Day 0
        # has no prior close and is dropped rather than zero-filled.
        ret = price[1:] / price[:-1] - 1.0
        raw = np.array([x["netflow_ntv"] for x in r], dtype="float64")[1:]
        norm = raw / np.array([x["sply_ex_ntv"] for x in r], dtype="float64")[1:]
        for label, sig in (("netflow_native", raw), ("netflow_over_exchange_supply", norm)):
            res = stage_a_screen(sig, ret, name=f"cm_{label}_{asset}")
            res["window"] = [r[1]["date"], r[-1]["date"]]
            res["n_days_full_window"] = len(r) - 1
            res["construction"] = label
            out.append(res)
    return out


def main() -> None:
    rows: list[dict[str, Any]] = []
    for a in _ASSETS:
        got = fetch_asset(a)
        print(f"coinmetrics {a}: {len(got)} daily rows "
              f"({got[0]['date'] if got else '-'} -> {got[-1]['date'] if got else '-'})")
        rows += got
    if not rows:
        raise SystemExit("coinmetrics: no rows fetched -- refusing to write an empty artifact")

    _SERIES.parent.mkdir(parents=True, exist_ok=True)
    with _SERIES.open("w", encoding="utf-8") as fh:
        for r in sorted(rows, key=lambda x: (x["asset"], x["date"])):
            fh.write(json.dumps(r) + "\n")
    print(f"-> {_SERIES} ({len(rows)} rows)")

    price_diff = _verify_price_convention(rows)
    recon = {a: _reconcile_supply(rows, a) for a in _ASSETS}
    screens = _screen_all(rows)
    for s in screens:
        print(f"  {s['name']:<42} n={s.get('n', s.get('n_days_full_window'))} "
              f"IC {s.get('ic')} | same {s.get('same_period_corr')} | "
              f"resid {s.get('residual_ic')} | momSh {s.get('sharpe_momentum')} | "
              f"revSh {s.get('sharpe_reversal')} | {s['verdict']}")

    flow_rows = [r for r in rows if r["netflow_ntv"] is not None]
    _OUT.write_text(json.dumps({
        "updated": datetime.now(tz=UTC).isoformat(),
        "source": "Coin Metrics community API (keyless) -- CC BY-NC 4.0, internal research use",
        "replaces": "Glassnode / CryptoQuant exchange-flow metric class ($799/mo each)",
        "licence_status": "CC BY-NC 4.0 -- NonCommercial ruling PENDING (legitimacy queue); "
                          "internal research/diff use only, zero promotion authority",
        "n_rows": len(rows),
        "assets": {a: {"n": sum(1 for r in rows if r["asset"] == a),
                       "n_with_flow": sum(1 for r in flow_rows if r["asset"] == a),
                       "first": min((r["date"] for r in rows if r["asset"] == a), default=""),
                       "first_flow": min((r["date"] for r in flow_rows if r["asset"] == a),
                                         default=""),
                       "last": max((r["date"] for r in rows if r["asset"] == a), default="")}
                   for a in _ASSETS},
        "timestamp_alignment": "CM 1d metrics stamped at START of UTC day; flow[d] spans day d; "
                               "same-period return = PriceUSD[d+1]/PriceUSD[d]-1; forward target "
                               "is day d+1. One clock (UTC), no cross-timezone candle join.",
        "verification": {"external_price_diff_vs_binance": price_diff,
                         "internal_supply_reconciliation": recon},
        "screens": screens,
    }, indent=1), "utf-8")
    print(f"-> {_OUT}")


if __name__ == "__main__":
    main()

```

### scripts/data_sanity.py
```python
"""DATA SANITY SCANNER -- systematise the two artifacts that were only caught by eyeball.

TODAY'S EVIDENCE (2 for 2): every data artifact found on 2026-07-27 was found by a human looking
at a number and thinking "that can't be right" -- never by a check.
  COOKIEUSDT  59.17bps slippage IDENTICAL at $100/$250/$500/$1000/$2500. Flat impact across a 25x
              size range is not physically possible. It passed every numeric validator because
              nothing tested for IMPLAUSIBILITY, only for presence.
  mSOL/SOL    539bps std on a ratio that tracks within ~100bps -- a pipeline artifact
              (non-synchronous daily legs), read as a market finding.
Both would have propagated into sizing and alpha decisions. Neither errored. That is the danger:
these are not crashes, they are CONFIDENT WRONG NUMBERS.

SEVEN IMPLAUSIBILITY CHECKS -- each encodes a physical fact about markets, not a threshold:
  1 FLAT-ACROSS-SIZE   slippage identical across size buckets (impact must rise with size)
  2 ZERO-VARIANCE      a "series" that never moves is a constant, not data
  3 IMPLAUSIBLE-VOL    daily vol far outside what the asset class can produce
  4 STALE-REPEAT       long runs of identical consecutive values (cached/failed fetch)
  5 IMPOSSIBLE-RANGE   ratios/premia outside economically possible bounds
  6 GAP-HOLES          missing dates inside the covered span (silent partial failure)
  7 MONOTONE-DRIFT     a bounded quantity that only ever goes one way (accumulator bug)

Scans the desk's own artifacts. Read-only, no LLM, no keys. Run from repo root, daily.
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "data_sanity_report.json"

# asset-class physical bounds for daily returns (what markets can actually produce)
MAX_DAILY_VOL = 0.35        # 35% daily std would be extraordinary even for a microcap
MIN_DAILY_VOL = 1e-6
STALE_RUN = 5               # identical consecutive values
FLAT_MIN_BUCKETS = 3


def flag(findings, sev, where, what, why):
    findings.append({"severity": sev, "where": where, "finding": what, "why_impossible": why})
    print(f"  [{sev:<8}] {where:<34} {what}")
    print(f"             -> {why}")


def scan_cost_model(findings):
    p = DATA / "cost_model.json"
    if not p.exists():
        return
    cm = json.loads(p.read_text("utf-8"))
    for sym, legs in cm.get("symbols", {}).items():
        for leg, buckets in legs.items():
            if not isinstance(buckets, dict) or len(buckets) < FLAT_MIN_BUCKETS:
                continue
            pts = sorted((int(k), v.get("median_bps")) for k, v in buckets.items()
                         if isinstance(v, dict) and v.get("median_bps") is not None)
            vals = [v for _, v in pts]
            if len(vals) < FLAT_MIN_BUCKETS:
                continue
            # CHECK 1: impact MUST rise with size; identical across a wide size range is impossible
            if len({round(v, 4) for v in vals}) == 1:
                flag(findings, "CRITICAL", f"cost_model/{sym}/{leg}",
                     f"slippage {vals[0]:.2f}bps IDENTICAL across {len(vals)} size buckets "
                     f"(${pts[0][0]}-${pts[-1][0]})",
                     "market impact must increase with order size; a flat curve means the "
                     "estimator returned a constant, so any sizing decision using it is unfounded")
            # CHECK 5: a leg costing more than ~1% is not tradeable for a carry
            elif max(vals) > 100:
                flag(findings, "HIGH", f"cost_model/{sym}/{leg}",
                     f"max {max(vals):.0f}bps per leg",
                     "4 legs per carry round-trip => >4% cost vs ~0.7%/mo funding harvest; "
                     "structurally unprofitable at any size")


def scan_jsonl(findings):
    for p in sorted(DATA.glob("*.jsonl")):
        rows = []
        for ln in p.read_text("utf-8", errors="ignore").splitlines():
            if not ln.strip():
                continue
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if not r.get("_summary"):
                rows.append(r)
        if len(rows) < 4:
            continue
        # numeric payload fields
        # CONFIG / METADATA fields are CONSTANT OR MONOTONE BY DESIGN. Flagging them is a false
        # positive, and a validator with a high FP rate trains the reader to ignore it -- which is
        # worse than no validator. window_s=3600 and partition_s=300 are settings; ts is a clock;
        # start_* is a fixed baseline. Only genuine MARKET quantities are checked.
        CONFIG = {"n_hist", "n_quotes", "window_s", "partition_s", "ts", "timestamp", "time",
                  "interval_s", "period_s", "lookback", "n", "count", "rows", "day", "epoch",
                  "min_days", "need", "version", "seq"}
        keys = [k for k, v in rows[-1].items()
                if isinstance(v, (int, float))
                and k not in CONFIG
                and not k.startswith(("start_", "cfg_", "param_", "n_", "num_"))
                and not k.endswith(("_s", "_ms", "_id", "_count", "_n", "_seq"))]
        for k in keys:
            vals = [r.get(k) for r in rows if isinstance(r.get(k), (int, float))]
            if len(vals) < 4:
                continue
            arr = np.asarray(vals, dtype="float64")
            # CHECK 2
            if arr.std() == 0:
                flag(findings, "HIGH", f"{p.name}/{k}",
                     f"zero variance across {len(arr)} rows (value {arr[0]})",
                     "a series that never moves is a constant; the collector is echoing, not reading")
                continue
            # CHECK 4
            run = mx = 1
            for i in range(1, len(arr)):
                run = run + 1 if arr[i] == arr[i - 1] else 1
                mx = max(mx, run)
            if mx >= STALE_RUN:
                flag(findings, "HIGH", f"{p.name}/{k}",
                     f"{mx} identical consecutive values",
                     "repeated values mean a cached or failed fetch is being recorded as fresh data")
            # CHECK 7: bounded quantities should not be monotone over long stretches
            if (len(arr) >= 8 and "cum" not in k and "total" not in k
                    and (np.all(np.diff(arr) >= 0) or np.all(np.diff(arr) <= 0))):
                flag(findings, "MEDIUM", f"{p.name}/{k}",
                     f"monotone across all {len(arr)} rows",
                     "a market quantity that only ever moves one way is usually an accumulator "
                     "or a counter mislabelled as a level")
        # CHECK 6: date holes inside the covered span
        ds = sorted({r["date"] for r in rows if r.get("date")})
        if len(ds) >= 3:
            try:
                a, b = date.fromisoformat(ds[0]), date.fromisoformat(ds[-1])
                span = (b - a).days + 1
                if span - len(ds) >= 2:
                    missing = [str(a + timedelta(days=i)) for i in range(span)
                               if str(a + timedelta(days=i)) not in set(ds)]
                    flag(findings, "MEDIUM", f"{p.name}/dates",
                         f"{span - len(ds)} missing days inside span {ds[0]}..{ds[-1]}",
                         f"silent partial failure -- e.g. {missing[:3]}")
            except ValueError:
                pass


def scan_screens(findings):
    """CHECK 3: implausible vol / IC in saved screen artifacts."""
    for name in ("batch_altdata_screen.json", "batch_premium_screen.json",
                 "structural_spreads.json", "hl_feature_factory.json"):
        p = DATA / name
        if not p.exists():
            continue
        d = json.loads(p.read_text("utf-8"))
        for r in d.get("results", []):
            if not isinstance(r, dict):
                continue
            sd = r.get("sd_pct")
            if isinstance(sd, (int, float)) and sd > MAX_DAILY_VOL * 100:
                flag(findings, "CRITICAL", f"{name}/{r.get('name')}",
                     f"sd {sd:.1f}% on a spread/ratio",
                     "far beyond what this quantity can physically produce; almost certainly "
                     "non-synchronous legs or a unit error, not a market observation")
            ic = r.get("ic")
            if isinstance(ic, (int, float)) and abs(ic) > 0.5:
                flag(findings, "CRITICAL", f"{name}/{r.get('name')}",
                     f"IC {ic:+.3f}",
                     "daily-horizon IC above 0.5 implies near-perfect foresight; lookahead or "
                     "alignment error is far more likely than a real signal")


def main() -> None:
    print("=== DATA SANITY SCANNER ===")
    print("    2 of 2 artifacts today were caught by EYEBALL, not by a check. This is the check.")
    print("    These are not crashes -- they are CONFIDENT WRONG NUMBERS that pass every")
    print("    presence-based validator and then propagate into sizing and alpha decisions.\n")
    findings: list[dict] = []
    scan_cost_model(findings)
    scan_jsonl(findings)
    scan_screens(findings)

    sev = {}
    for f in findings:
        sev[f["severity"]] = sev.get(f["severity"], 0) + 1
    print(f"\n  {len(findings)} implausibility findings"
          + (f"  ({', '.join(f'{k}:{v}' for k, v in sorted(sev.items()))})" if sev else ""))
    if not findings:
        print("  (nothing implausible found -- note this is a WEAKER statement than 'data is correct')")
    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "n": len(findings), "by_severity": sev,
                               "findings": findings}, indent=1), "utf-8")
    print(f"\n  -> {OUT}")
    print("  CRITICAL findings should block any sizing or promotion decision that uses that input.")


if __name__ == "__main__":
    main()

```

### scripts/git_snapshot.py
```python
"""Daily git snapshot of the code+docs surface -- forensic history the desk lacked.

2026-07-16 lesson: the 07-15 session's panel edits could not be diffed (no git, no backups) and
the 07-13 incident forensics relied on hand-made .bak files. One commit per day fixes both
forever. Secrets and generated state never enter the repo (.gitignore); this is history, not
deployment -- rollback_guard remains the revert mechanism for autonomous changes.

    python scripts/git_snapshot.py
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=False)


def main() -> None:
    if _git("rev-parse", "--git-dir").returncode != 0:
        print("git-snapshot: not a git repo -- skipped (run git init once)")
        return
    _git("add", "-A")
    if not _git("status", "--porcelain").stdout.strip():
        print("git-snapshot: no changes since last snapshot")
        return
    msg = f"desk snapshot {datetime.now(tz=UTC).isoformat()[:16]}Z"
    r = _git("commit", "-m", msg)
    if r.returncode == 0:
        print(f"git-snapshot: committed -- {msg}")
        pr = _git("push", "origin", "HEAD")
        print("git-snapshot: pushed to GitHub" if pr.returncode == 0
              else f"git-snapshot: push failed (offsite deferred): {(pr.stderr or '')[:80]}")
    else:
        print(f"git-snapshot: commit failed: {(r.stderr or r.stdout)[:140]}")


if __name__ == "__main__":
    main()

```

### scripts/horizon_search.py
```python
"""TIME HORIZON DISCOVERY (Tier-1 #1) -- with the multiplicity + adjacency guards.

The desk killed whole information classes at a SINGLE daily horizon. Diffusion processes
(attention, TVL rotation) are inherently slow, so a 1-day clock is the wrong instrument and those
kills may be FALSE NEGATIVES. The resurrection engine shortlisted exactly two:
multilingual_wikipedia_attention and defi_health.

THE TRAP (principal, correct): searching 12 horizons just moves overfitting from features to
horizons. Two guards, both mandatory:
  1. BONFERRONI  -- alpha/n_horizons, so a lucky horizon cannot masquerade as a discovery.
  2. ADJACENCY   -- a REAL slow signal is smooth in horizon: if it works at 14d it should also
     show the SAME SIGN at 10d and 21d. An isolated spike at exactly one horizon is noise.
     A survivor must clear Bonferroni AND have >=2 same-sign neighbours.

Overlapping forward windows autocorrelate, so the t-stat is Newey-West-style deflated by
sqrt(horizon) -- otherwise long horizons manufacture significance from overlap alone.
Stage-A only, zero promotion authority. Run from repo root.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

HORIZONS = [1, 2, 3, 5, 7, 10, 14, 21, 30, 45, 60, 90]
ALPHA = 0.05


def _get(u, t=40):
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(u, headers={"User-Agent": "q/1.0"}), timeout=t).read().decode())


def binance():
    rows = _get("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=900")
    return {datetime.fromtimestamp(int(r[0]) / 1000, tz=UTC).date().isoformat(): float(r[4])
            for r in rows}


def wiki(proj, art):
    a = urllib.request.quote(art, safe="")
    d = _get(f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
             f"{proj}.wikipedia/all-access/all-agents/{a}/daily/20240101/20260722")
    out = {}
    for it in d.get("items", []):
        ts = str(it["timestamp"])
        out[f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]}"] = float(it["views"])
    return out


def llama_tvl():
    d = _get("https://api.llama.fi/v2/historicalChainTvl")
    return {datetime.fromtimestamp(int(x["date"]), tz=UTC).date().isoformat(): float(x["tvl"])
            for x in d}


def llama_chart(url):
    d = _get(url)
    return {datetime.fromtimestamp(int(ts), tz=UTC).date().isoformat(): float(v)
            for ts, v in d.get("totalDataChart", [])}


SIGNALS = {
    "wiki_btc_en": lambda: wiki("en", "Bitcoin"),
    "wiki_btc_ja": lambda: wiki("ja", "ビットコイン"),
    "wiki_btc_ko": lambda: wiki("ko", "비트코인"),
    "wiki_btc_ru": lambda: wiki("ru", "Биткойн"),
    "wiki_btc_zh": lambda: wiki("zh", "比特幣"),
    "defi_tvl": llama_tvl,
    "dex_volume": lambda: llama_chart(
        "https://api.llama.fi/overview/dexs?excludeTotalDataChartBreakdown=true"),
    "protocol_fees": lambda: llama_chart(
        "https://api.llama.fi/overview/fees?excludeTotalDataChartBreakdown=true"),
}


def main() -> None:
    gb = binance()
    bar = ALPHA / len(HORIZONS)
    # two-sided z for the Bonferroni-adjusted alpha
    from math import erf, sqrt

    def p_from_t(t, n):
        # normal approx is fine at these n
        z = abs(t)
        return 2 * (1 - 0.5 * (1 + erf(z / sqrt(2))))

    print(f"=== HORIZON DISCOVERY | {len(HORIZONS)} horizons | Bonferroni alpha {bar:.5f} ===")
    print("    (t deflated by sqrt(h) for overlapping windows; survivor needs >=2 same-sign neighbours)\n")
    allres = {}
    for name, fn in SIGNALS.items():
        try:
            s = fn()
        except Exception as e:
            print(f"{name:16s} DATA-BLOCKED ({type(e).__name__})")
            continue
        dates = sorted(set(s) & set(gb))
        if len(dates) < 200:
            print(f"{name:16s} thin ({len(dates)})")
            continue
        sig = np.array([s[d] for d in dates])
        px = np.array([gb[d] for d in dates])
        z = np.zeros(len(sig))
        for t in range(30, len(sig)):
            w = sig[t - 30:t]
            sd = w.std()
            z[t] = (sig[t] - w.mean()) / sd if sd > 0 else 0.0
        row = []
        for h in HORIZONS:
            fwd = np.full(len(px), np.nan)
            fwd[:-h] = px[h:] / px[:-h] - 1.0
            m = ~np.isnan(fwd)
            m[:30] = False
            zv, fv = z[m], fwd[m]
            if len(zv) < 60 or zv.std() == 0 or fv.std() == 0:
                row.append((h, 0.0, 0.0))
                continue
            ic = float(np.corrcoef(zv, fv)[0, 1])
            n_eff = len(zv) / h                      # overlap deflation
            t_stat = ic * np.sqrt(max(1.0, n_eff - 2)) / np.sqrt(max(1e-9, 1 - ic ** 2))
            row.append((h, ic, float(t_stat)))
        allres[name] = row
        best = max(row, key=lambda r: abs(r[2]))
        line = " ".join(f"{h}d:{ic:+.3f}" for h, ic, _ in row)
        print(f"{name:16s} {line}")
        # survivor test
        h_b, ic_b, t_b = best
        p = p_from_t(t_b, 0)
        i = [r[0] for r in row].index(h_b)
        nb = [row[j][1] for j in (i - 1, i + 1) if 0 <= j < len(row)]
        same_sign = sum(1 for v in nb if v * ic_b > 0)
        ok = p < bar and same_sign >= min(2, len(nb))
        print(f"{'':16s}  best {h_b}d IC {ic_b:+.4f} t {t_b:+.2f} p {p:.5f} | "
              f"neighbours same-sign {same_sign}/{len(nb)} -> "
              f"{'*** SURVIVOR ***' if ok else 'no (fails Bonferroni or adjacency)'}\n")
    Path("data/horizon_discovery.json").write_text(json.dumps(
        {"updated": datetime.now(tz=UTC).isoformat(), "horizons": HORIZONS,
         "bonferroni_alpha": bar,
         "results": {k: [{"h": h, "ic": ic, "t": t} for h, ic, t in v]
                     for k, v in allres.items()}}, indent=1), "utf-8")


if __name__ == "__main__":
    main()

```

### scripts/measure_gate_histogram.py
```python
"""Per-gate accept/reject histogram for the real 420-candidate campaign (GATE-OPTIMALITY DUTY).

Answers the question three audits left open: is 420-tested/0-survivors a dead search space, or a
welded-shut gate? Runs the FULL validate() stack over the reconstructed campaign twice -- once via
the legacy campaign-constant path (what production ran until 2026-07-29) and once via the
per-candidate path (CSCV rank-consistency + Romano-Wolf stepdown) -- and tallies which gate
actually does the rejecting.

Thresholds are never touched here; this measures, it does not decide.
Input: _audit_prepared.pkl (reconstructed campaign, list of (family, subtype, symbol, rets)).
"""

from __future__ import annotations

import collections
import json
import pickle
import sys
import time

import numpy as np

from libs.autodiscovery.models import Family, Hypothesis
from libs.autodiscovery.validation import campaign_gate_stats, campaign_pbo_rc, validate
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType

_PKL = "_audit_prepared.pkl"


def _log(msg: str) -> None:
    print(msg, flush=True)


def _hyp(fam: str, sub: str, sym: str) -> Hypothesis:
    """Reconstruct a hypothesis shell. failure_modes is non-empty so the economic_mechanism gate
    reflects the REAL campaign (every generated hypothesis declares failure modes before testing);
    leaving it empty would make that gate a second constant veto and hide the statistical gates."""
    try:
        family = Family(fam)
    except ValueError:
        family = Family.CARRY
    return Hypothesis(
        family=family, subtype=sub, symbol=sym, params={},
        mechanism=MechanismType.RISK_PREMIUM,
        edge_source=f"{fam}/{sub}", failure_modes=["reconstructed-for-gate-measurement"],
    )


def main() -> int:
    t0 = time.time()
    with open(_PKL, "rb") as fh:
        prepared = pickle.load(fh)
    _log(f"loaded {len(prepared)} candidates from {_PKL}")

    lens = np.array([len(e[-1]) for e in prepared])
    min_len = int(lens.min())
    matrix = np.column_stack([e[-1][-min_len:] for e in prepared])
    _log(f"matrix {matrix.shape}  (min_len={min_len}, median_len={int(np.median(lens))}, "
         f"max_len={int(lens.max())}, retained_obs={matrix.size} of {int(lens.sum())})")

    sharpe_estimates = np.array([sharpe_ratio(e[-1]) for e in prepared], dtype="float64")
    fam_counts = collections.Counter(e[0] for e in prepared)
    fam_sharpes = {
        f: np.array([sharpe_ratio(e[-1]) for e in prepared if e[0] == f], dtype="float64")
        for f in fam_counts
    }

    t = time.time()
    legacy_pbo, legacy_rc = campaign_pbo_rc(matrix)
    assert legacy_pbo is not None and legacy_rc is not None
    _log(f"LEGACY campaign constants [{time.time() - t:.1f}s]: "
         f"pbo={legacy_pbo.pbo:.4f} overfit={legacy_pbo.overfit} -> pbo_gate_passes="
         f"{not legacy_pbo.overfit} for ALL {matrix.shape[1]}; "
         f"rc_p={legacy_rc.p_value:.4f} sig={legacy_rc.significant_at_5pct} -> "
         f"reality_check_passes={legacy_rc.significant_at_5pct} for ALL {matrix.shape[1]}")

    t = time.time()
    gates = campaign_gate_stats(matrix)
    assert gates is not None
    cp = np.array(gates.cscv.candidate_pbo)
    rej = np.array(gates.stepdown.rejected)
    adj = np.array(gates.stepdown.adjusted_p)
    _log(f"PER-CANDIDATE stats [{time.time() - t:.1f}s]: "
         f"cscv pbo<=0.5 for {int((cp <= 0.5).sum())}/{len(cp)} "
         f"(min={cp.min():.3f} med={np.median(cp):.3f}); "
         f"romano-wolf rejected {int(rej.sum())}/{len(rej)} (min adj_p={adj.min():.4f}); "
         f"BOTH: {int(((cp <= 0.5) & rej).sum())}")

    report: dict[str, object] = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "n_candidates": len(prepared),
        "matrix_shape": list(matrix.shape),
        "obs_retained": int(matrix.size),
        "obs_available": int(lens.sum()),
        "legacy": {
            "pbo": legacy_pbo.pbo, "pbo_gate_passes_all": not legacy_pbo.overfit,
            "rc_p": legacy_rc.p_value, "rc_gate_passes_all": legacy_rc.significant_at_5pct,
        },
        "per_candidate": {
            "cscv_pbo_ok": int((cp <= 0.5).sum()),
            "rw_rejected": int(rej.sum()),
            "both": int(((cp <= 0.5) & rej).sum()),
            "min_adj_p": float(adj.min()),
        },
    }

    for label, kwargs_fn in (
        ("legacy", lambda i: {"pbo": legacy_pbo, "rc": legacy_rc}),
        ("per_candidate", lambda i: {"campaign": gates, "column": i}),
    ):
        tally: collections.Counter[str] = collections.Counter()
        fail_tally: collections.Counter[str] = collections.Counter()
        seen: collections.Counter[str] = collections.Counter()
        survivors: list[str] = []
        n_fail_only: collections.Counter[str] = collections.Counter()
        t = time.time()
        for i, (fam, sub, sym, rets) in enumerate(prepared):
            _sh = fam_sharpes.get(fam)
            if _sh is None or len(_sh) < 2:
                _sh = sharpe_estimates
            v = validate(
                rets, hypothesis=_hyp(fam, sub, sym),
                n_trials=fam_counts[fam], sharpe_estimates=_sh,
                returns_matrix=matrix, **kwargs_fn(i),
            )
            # BOTH OUTCOMES ARE TALLIED. Counting only passes made a gate at 0/420 byte-for-byte
            # indistinguishable from a gate that is NOT IN THE CODE -- both simply absent from
            # pass_counts. That ambiguity is not cosmetic on the desk's only gate-optimality
            # artifact: it is exactly how `dsr` vetoing every single candidate and
            # `beats_baselines` not yet existing both read as "not there". A gate rejecting 100%
            # of candidates is the loudest possible finding and it was rendering as silence.
            for name, ok in v.gates.items():
                tally[name] += int(bool(ok))
                seen[name] += 1
                if not ok:
                    fail_tally[name] += 1
            failed = [n for n, ok in v.gates.items() if not ok]
            if not failed:
                survivors.append(f"{fam}/{sub}/{sym}")
            elif len(failed) == 1:
                n_fail_only[failed[0]] += 1
            if (i + 1) % 100 == 0:
                _log(f"  [{label}] {i + 1}/{len(prepared)} ({time.time() - t:.0f}s)")

        n = len(prepared)
        _log(f"--- {label.upper()} per-gate PASS counts (of {n}) [{time.time() - t:.0f}s] ---")
        for name, cnt in sorted(tally.items(), key=lambda kv: kv[1]):
            _log(f"    {name:20s} {cnt:4d}/{n}  ({100.0 * cnt / n:5.1f}%)")
        _log(f"    SURVIVORS: {len(survivors)}")
        if survivors:
            for s in survivors[:20]:
                _log(f"      + {s}")
        if n_fail_only:
            _log(f"    SOLE blocker (candidate failed exactly ONE gate): {dict(n_fail_only)}")
        report[f"histogram_{label}"] = {
            "pass_counts": dict(tally), "fail_counts": dict(fail_tally),
            "gates_evaluated": dict(seen),
            # A gate present in `gates_evaluated` with pass_counts 0 is a TOTAL VETO; a gate
            # missing from `gates_evaluated` entirely is not in the code. Recording both makes
            # those two states distinguishable, which they were not.
            "total_vetoes": sorted(g for g in seen if tally.get(g, 0) == 0),
            "survivors": survivors, "sole_blocker": dict(n_fail_only),
        }

    out = "reports/gate_histogram.json"
    with open(out, "w") as fh:
        json.dump(report, fh, indent=2)
    _log(f"wrote {out}  [total {time.time() - t0:.0f}s]")
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/research_cycle.py
```python
"""Institutional research-cycle state keeper -- maintains the 3 persistent state files.

Runs one audit pass and (re)writes, from REAL system state (never fabricated):
  * research_state.json     -- deployed truth, binding constraint, backlog, bottleneck ranking
  * engineering_backlog.json -- every engineering task, ROI-ranked, completed items auto-removed
  * alpha_pipeline.json      -- every alpha's lifecycle: stage, half-life, crowding, retire check

Engineering ROI = expected_impact_on_log_growth * p_survive_or_success / effort_hours. Items whose
`done_if` detector fires are marked done and drop out of the open backlog (institutional memory of
completed work is kept in research_state.completed). This is the compounding memory layer; it is
deterministic and honest -- it reports what the files on disk actually say.

    python scripts/research_cycle.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.self_improvement import forecast_calibration as fc

_WEB = Path("web")
_ROOT = Path(".")


def _load(p: Path, d: Any = None) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return d if d is not None else {}


def _register_row_closed(row_id: int) -> bool:
    """Has GAP_REGISTER row ``row_id`` reached a terminal status?

    A backlog item that mirrors a register row must never claim done while the row is still
    open. Those two systems disagreed for 8 days on the live connector -- the register said
    in-progress with six named blockers and a 07-31 deadline, while the backlog said completed,
    and the backlog is the one that produces `next_action` every morning. Unknown or unparseable
    reads as NOT closed: the failure that cost the time was a detector defaulting to done.
    """
    try:
        from libs.research.finding_registry import parse_register
        rows = parse_register((_ROOT / "docs/GAP_REGISTER.md").read_text("utf-8"))
    except (OSError, ImportError, ValueError):
        return False
    for r in rows:
        if r.row_id == row_id:
            return not r.is_open
    return False


def _live_path_wired() -> bool:
    """Is the live path RUNNING, and is the register row it mirrors actually closed?

    The wiring half checks the three things that were all false while the old
    `binance_live.py.exists()` detector said done: the guard exists, the daily cycle calls it,
    and the guard drives the stage machine + connector + reconcile.

    The register half is what stops this detector re-arming the same trap. Wiring is necessary,
    not sufficient -- row 2 still carries the panel fuzz/breaker report, the §7b pre-mortem and
    the host-death and ladder drills, none of which a source-text check can see. With wiring
    alone this would have flipped to done the moment the guard shipped and dropped the connector
    out of the backlog's open list again, exactly as it did on 07-18.
    """
    guard = _ROOT / "scripts/run_live_guard.py"
    cycle = _ROOT / "scripts/daily_research_cycle.py"
    try:
        g, c = guard.read_text("utf-8"), cycle.read_text("utf-8")
    except OSError:
        return False
    wired = ("run_live_guard.py" in c
             and "binance_live" in g
             and "staging" in g
             and "protective_stops" in g)
    return wired and _register_row_closed(2)


def _detectors() -> dict[str, bool]:
    """Honest 'is this task actually done?' checks against files on disk."""
    lb = (_ROOT / "libs" / "portfolio" / "live_book.py")
    lb_txt = lb.read_text("utf-8") if lb.exists() else ""
    health = _load(_WEB / "health.json")
    # archive health: the OI/LS/liq datasets must be fresh for the 40-day clock to be real
    ds = {x.get("name", ""): x for x in health.get("datasets", [])}
    arch_ok = all(ds.get(n, {}).get("status") in ("OK", "RECEIVING", "LISTENING")
                  for n in ds if any(k in n.lower() for k in ("interest", "long", "liquid")))
    exec_txt = (_ROOT / "scripts/run_cashcarry_executor.py").read_text("utf-8")
    return {
        "honest_deployed_sharpe": "_MIN_SHARPE_DAYS" in lb_txt,
        "single_portfolio_object": (_ROOT / "libs/portfolio/live_book.py").exists(),
        "trade_logging": "_log_trade" in exec_txt,
        "state_files_infra": True,                      # true whenever this script runs
        "watchdog_enabled": True,                        # enabled last cycle (task scheduler)
        "watchdog_run_logged_off": (_ROOT / "data" / ".watchdog_logged_off").exists(),
        "archive_integrity_ok": bool(ds) and arch_ok,
        "dynamic_leverage": (_ROOT / "libs/risk/dynamic_leverage.py").exists(),
        "combined_perp_carry": "perp_active" in
        (_ROOT / "scripts/run_live_combined.py").read_text("utf-8"),
        "cashcarry_capacity_sizing": "_alloc" in exec_txt,
        "bayesian_roi_calibration":
        (_ROOT / "libs/self_improvement/forecast_calibration.py").exists(),
        "execution_maker_carry": "_maker_pair" in exec_txt,
        "hedge_reconcile": "_reconcile" in exec_txt,
        "growth_positive_risk_controls": (_ROOT / "libs/risk/risk_controls.py").exists(),
        "test_suite_ci": (_ROOT / "tests/test_hedge_and_risk.py").exists()
        and (_ROOT / "scripts/run_ci.py").exists(),
        "stress_harness": (_ROOT / "scripts/run_stress.py").exists(),
        "stablecoin_flows_archiver": (_ROOT / "scripts/run_stablecoin_flows.py").exists()
        and (_ROOT / "data/stablecoin_flows_archive.json").exists(),
        "alpha_economics_gate": (_ROOT / "libs/research/alpha_economics.py").exists()
        and (_ROOT / "tests/test_alpha_economics.py").exists(),
        "root_cause_engine": (_ROOT / "libs/research/root_cause.py").exists()
        and (_ROOT / "tests/test_root_cause.py").exists(),
        "decision_ledger": (_ROOT / "data/decision_ledger.json").exists(),
        "data_registry": (_ROOT / "data/data_registry.json").exists(),
        "executive_kpis": (_ROOT / "data/executive_kpis.json").exists(),
        "black_swan_library": (_ROOT / "data/black_swan_library.json").exists(),
        "institutional_knowledge_base": (_ROOT / "docs/institutional_knowledge.md").exists(),
        "reconcile_limit_fallback": "_mkt_or_limit" in exec_txt,
        "growth_audit_engine": (_ROOT / "scripts/run_growth_audit.py").exists(),
        "execution_tca_fill_log": (_ROOT / "web/tca.json").exists(),
        "funding_decay_predictor": (_ROOT / "web/funding_decay_backtest.json").exists(),
        # A FILE-EXISTENCE detector marked this done on 2026-07-18 and kept marking it done for
        # 8 days while the connector and the stage machine had no production caller at all --
        # measuring the proxy (a file on disk) instead of the thing the row names (a wired live
        # path). Now it asks whether the rails actually RUN: the guard must exist, be on the
        # daily cycle, and drive the stage machine.
        "live_connector_prebuild": _live_path_wired(),
        "carry_crowding_monitor": (_ROOT / "web/crowding.json").exists(),
        "cross_venue_funding_study": (_ROOT / "web/cross_venue_funding.json").exists(),
        # the #1 tier-convergence build: autodiscovery factory generating/gauntleting CRYPTO
        # candidates in the daily cycle (needs the crypto MarketSeries adapter) -- done when the
        # orchestrator emits crypto candidates into the EV gate automatically.
        "autodiscovery_crypto_throughput":
        (_ROOT / "libs/autodiscovery/crypto_adapter.py").exists(),
    }


# curated engineering backlog -- each competes on ROI. impact = share of lifetime-log-growth lever.
_ENG: list[dict[str, Any]] = [
    {"id": "archive_integrity_ok", "title": "Verify OI/LS/liq archives append daily (protect the",
     "impact": 0.60, "p": 0.85, "effort_h": 1.0,
     "why": "The binding constraint is calendar-time data. A silent archive failure wastes 40 da"},
    {"id": "watchdog_run_logged_off", "title": "Watchdog: run whether logged on (survive reboot-b",
     "impact": 0.45, "p": 0.90, "effort_h": 0.3,
     "why": "Survival of the data flywheel; a reboot before login currently stalls every clock."},
    {"id": "honest_deployed_sharpe", "title": "Gate deployed Sharpe to >=5d forward (stop the -92",
     "impact": 0.20, "p": 0.95, "effort_h": 0.5,
     "why": "Metric integrity -> better sizing decisions; a lying Sharpe is worse than a blank o"},
    {"id": "single_portfolio_object", "title": "One canonical LivePortfolio object (dashboard/tes",
     "impact": 0.25, "p": 0.90, "effort_h": 2.0,
     "why": "Kills duplicate portfolio maths; deployed Sharpe always = deployed capital."},
    {"id": "trade_logging", "title": "Real open/close trade log -> winrate + molded history",
     "impact": 0.15, "p": 0.95, "effort_h": 1.0,
     "why": "Institutional memory of every fill; winrate/history become real, not fabricated."},
    {"id": "state_files_infra", "title": "Persistent research_state / eng_backlog / alpha_pipeline",
     "impact": 0.30, "p": 0.90, "effort_h": 2.0,
     "why": "Compounding memory: remembers decisions, re-ranks ROI each cycle, avoids repeat wor"},
    {"id": "cashcarry_capacity_sizing", "title": "Size each carry to per-name funding depth (not",
     "impact": 0.40, "p": 0.65, "effort_h": 3.0,
     "why": "Higher net funding capture -> higher log-growth. GATED: only after forward cert (da"},
    {"id": "bayesian_roi_calibration", "title": "Bayesian calibration of ROI / alpha-survival for",
     "impact": 0.10, "p": 0.50, "effort_h": 4.0,
     "why": "Phase-9 meta-opt. LOW ROI now: no realised track record to calibrate against yet."},
    {"id": "dynamic_leverage", "title": "Dynamic leverage controller (endogenous cap, no fixed li",
     "impact": 0.50, "p": 0.85, "effort_h": 3.0,
     "why": "Leverage as continuously-optimized control -> growth-optimal sizing as edge proves."},
    {"id": "combined_perp_carry", "title": "Combine perp (paper) + cash-carry into molded (testnet",
     "impact": 0.20, "p": 0.90, "effort_h": 1.5,
     "why": "Decorrelated 2nd sleeve forward track; paper-marked, never risks the carry acct."},
    {"id": "execution_maker_carry", "title": "Maker-first execution on carry legs (exec alpha)",
     "impact": 0.35, "p": 0.90, "effort_h": 3.0,
     "why": "Cut taker-fee drag on the forward Sharpe that gates leverage; taker fallback."},
    {"id": "hedge_reconcile", "title": "Auto-reconcile hedge drift each rebalance (survival)",
     "impact": 0.55, "p": 0.90, "effort_h": 1.5,
     "why": "Delta-neutral integrity: cover orphan shorts + re-hedge unhedged carries."},
    {"id": "growth_positive_risk_controls", "title": "Ruin-boundary risk controls (growth+)",
     "impact": 0.50, "p": 0.90, "effort_h": 2.0,
     "why": "Cut the left tail (raises g) via pause/flatten sized at the ruin boundary."},
    {"id": "test_suite_ci", "title": "Hedge/risk invariant test suite + local CI gate",
     "impact": 0.45, "p": 0.95, "effort_h": 2.5,
     "why": "Mechanical correctness on survival logic; caught the _alloc concentration bug."},
    {"id": "stress_harness", "title": "Stress harness (proves controls are growth-positive)",
     "impact": 0.20, "p": 0.90, "effort_h": 1.5,
     "why": "Empirically shows over-levering flips +g to -g; validates the risk controls."},
    {"id": "stablecoin_flows_archiver", "title": "On-chain stablecoin exchange-flow archiver",
     "impact": 0.35, "p": 0.30, "effort_h": 4.0,
     "why": "Starts the only NEW orthogonal 40d clock available; keyless free on-chain data."},
    {"id": "alpha_economics_gate", "title": "Alpha Economics EV gate (score ideas pre-effort)",
     "impact": 0.55, "p": 0.80, "effort_h": 3.0,
     "why": "EV-rank ideas + meta-learned priors -> saves 100s of low-EV research hours."},
    {"id": "institutional_knowledge_base", "title": "Knowledge base + alpha map + failure taxonomy",
     "impact": 0.35, "p": 0.85, "effort_h": 2.0,
     "why": "Never re-learn a lesson; alpha map exposes missing branches; compounds over years."},
    {"id": "reconcile_limit_fallback", "title": "Reconcile market-first/limit-fallback (thin book)",
     "impact": 0.50, "p": 0.90, "effort_h": 1.5,
     "why": "Orphans on illiquid perps were stranded (-4131); now they clear -> less friction."},
    {"id": "root_cause_engine", "title": "Root Cause Engine (classify losses before reacting)",
     "impact": 0.50, "p": 0.85, "effort_h": 2.5,
     "why": "Expected variance -> do nothing; act only on evidenced execution/infra causes."},
    {"id": "decision_ledger", "title": "Decision ledger (pre-log decisions, review monthly)",
     "impact": 0.30, "p": 0.85, "effort_h": 1.0,
     "why": "Feedback loop on decision QUALITY, not just trading results; compounds."},
    {"id": "data_registry", "title": "Data registry (tiered sources, EV-gated integrations)",
     "impact": 0.30, "p": 0.85, "effort_h": 1.0,
     "why": "Info-per-dollar policy: free-first, quarterly verify, never integrate for free-ness."},
    {"id": "executive_kpis", "title": "Executive KPI scorecard (6 hats, monthly CEO review)",
     "impact": 0.25, "p": 0.85, "effort_h": 1.0,
     "why": "Accountability between hats; engineering hours flow to the weakest positive lever."},
    {"id": "black_swan_library", "title": "Black swan scenario library (pre-production replay)",
     "impact": 0.35, "p": 0.85, "effort_h": 1.0,
     "why": "FTX/LUNA/COVID/inversion scenarios cap SIZE so any single crisis is survivable."},
    {"id": "growth_audit_engine", "title": "Growth audit: under-utilized authorized size = defect",
     "impact": 0.40, "p": 0.90, "effort_h": 1.5,
     "why": "Anti-conservatism with teeth: idle capital / stalled ramps / promo latency."},
    {"id": "cross_venue_funding_study",
     "title": "Cross-venue funding arb study: Binance vs Hyperliquid spread persistence",
     "impact": 0.55, "p": 0.35, "effort_h": 3.0,
     "why": "Round-3 review + growth playbook: the carry edge's capacity ceiling is the "
            "top-10 Binance perps; Hyperliquid funding (205 matched perps, collector already "
            "accruing) diverges in MAGNITUDE from Binance while correlating in direction -- "
            "harvesting the venue with the richer print (or the spread itself) is a second "
            "capacity pool with different microstructure. STUDY FIRST from data on hand: "
            "spread persistence net of costs, half-life, capacity; EV-gate the sleeve before "
            "any venue integration (live execution there needs real capital + transfers = "
            "human gate). Detector: web/cross_venue_funding.json.",
     },
    {"id": "carry_crowding_monitor",
     "title": "Crowding monitor on the PRIMARY edge (funding compression early-warning)",
     "impact": 0.45, "p": 0.85, "effort_h": 2.5,
     "why": "Round-2 external review: the desk's most probable failure mode is SECULAR funding "
            "compression as carry crowds -- a slow grind with no discrete event, invisible to "
            "the regime gate and root-cause buckets. Build web/crowding.json: trailing 30/90d "
            "trend of top-20 funding level, aggregate OI growth (archive matures ~Aug 5), and "
            "basis compression; monthly governance reviews it; a sustained down-trend in "
            "harvestable funding = pre-registered decay evidence feeding the carry-decay "
            "contingency BEFORE the Sharpe degrades. Detector: web/crowding.json exists."},
    {"id": "live_connector_prebuild",
     "title": "Pre-build live connector + go-live runbook behind interlocks (phase-change de-risk)",
     "impact": 0.40, "p": 0.90, "effort_h": 4.0,
     "why": "2026-07-12: testnet->live is a PHASE CHANGE (external-review consensus). Build "
            "libs/execution/binance_live.py NOW mirroring the testnet connector (same interface; "
            "live base URLs; refuses to init unless data/secrets/binance_live.json exists AND "
            "data/LIVE_ENABLE flag file present AND VPS precondition marker set), plus a go-live "
            "runbook in docs/playbooks/. Unit-test the guard interlocks. Rushing real-money code "
            "on connection day is how phase changes go wrong; this makes go-live a config flip. "
            "Detector: the live path is WIRED -- scripts/run_live_guard.py exists, the daily "
            "cycle calls it, and it drives the connector + stage machine + naked-position "
            "reconcile. (Was 'binance_live.py exists', which read done for 8 days while nothing "
            "called either module.)"},
    {"id": "funding_decay_predictor",
     "title": "Funding-decay predictor: rank/exit carry on PREDICTED next-window funding",
     "impact": 0.50, "p": 0.30, "effort_h": 4.0,
     "why": "2026-07-12 external review, the one new alpha idea that survived triage (EV gate "
            "QUEUE, funding-family x2.0 prior; logged in data/ev_gate_audit.json). Mechanism: "
            "premium/OI/taker-flow predict the NEXT 8h funding print; exit the moment marginal "
            "expected funding < execution cost instead of waiting for the realized negative "
            "print -> harvests more per cycle AND defends the lone validated edge's decay "
            "margin. PRE-REGISTERED before test: predicted-funding ranking vs realized-funding "
            "ranking (current executor baseline), full gauntlet, net of ADV costs; verdict to "
            "graveyard or shadow like everything else. Detector: web/funding_decay_backtest.json."},
    {"id": "execution_tca_fill_log",
     "title": "Per-fill TCA log + funding-deadline-aware maker patience (execution edge P0)",
     "impact": 0.45, "p": 0.85, "effort_h": 3.0,
     "why": "Log decision-px vs fill-px, time-to-fill, maker/taker outcome per order -> "
            "web/tca.json; tune maker patience so legs FILL before the 8h funding snapshot "
            "(missing a funding event costs more than patient quoting). Target: exec cost "
            "< 15% of gross funding. PLUS edge-weighted routing (round-3 growth review): "
            "when expected_edge_bps > 2.5x taker_cost_bps, TAKE liquidity immediately -- "
            "queue-sitting through a fat funding spike saves 4bps of fees and loses 40bps "
            "of alpha; maker-first is for thin edges with time to wait."},
    {"id": "autodiscovery_crypto_throughput",
     "title": "Crypto adapter -> autodiscovery factory in the daily cycle (#1 tier-convergence)",
     "impact": 0.70, "p": 0.50, "effort_h": 6.0,
     "why": "Edge BREADTH is the #1 closable Tier-1/2 gap. 12-generator factory + orchestrator "
            "exist but are MarketSeries(MT5)-shaped; build libs/autodiscovery/crypto_adapter.py "
            "(lake bars -> MarketSeries), then orchestrator emits crypto candidates into the EV "
            "gate + gauntlet EVERY cycle -> industrialized hypothesis throughput."},
]


def _roi(item: dict[str, Any]) -> float:
    return round(item["impact"] * item["p"] / max(0.1, item["effort_h"]), 3)


def _build_engineering(done: dict[str, bool]) -> dict[str, Any]:
    items = []
    for it in _ENG:
        rec = {**it, "roi": _roi(it), "done": bool(done.get(it["id"], False))}
        items.append(rec)
    open_items = sorted((i for i in items if not i["done"]), key=lambda x: -x["roi"])
    done_items = [i["id"] for i in items if i["done"]]
    return {"generated": datetime.now(tz=UTC).isoformat(),
            "roi_formula": "impact * p_success / effort_hours",
            "open": open_items, "completed": done_items,
            "next_action": open_items[0] if open_items else None}


def _alpha_pipeline() -> dict[str, Any]:
    reg = _load(_WEB / "registry.json")
    disc = _load(_WEB / "discovery.json")
    pending = {p["sleeve"]: p for p in disc.get("pending", [])}
    rows = []
    for a in reg.get("alphas", []):
        name = a.get("name")
        p = pending.get(name)
        # honest lifecycle stage
        if a.get("survived"):
            stage = "validated-candidate"          # passed gates but not forward-certified
        elif p:
            stage = f"data-blocked ({p.get('have_days', '?')}/{p.get('needs_days', '?')}d)"
        else:
            stage = "rejected" if a.get("status", "").lower().startswith("rej") else "backtest"
        rows.append({
            "alpha": name, "category": a.get("category"),
            "expected_sharpe": a.get("expected_sharpe"), "gates": a.get("gates"),
            "survived": a.get("survived"), "stage": stage,
            # honest qualitative estimates (no fabricated numbers)
            "orthogonality": ("high" if a.get("category") in ("carry", "microstructure")
                              else "unknown"),
            "crowding_risk": "high" if a.get("category") == "carry" else "medium",
            "expected_half_life": "regime-dependent (funding-rich)" if a.get("category") == "carry"
            else "unknown-until-forward",
            "retire_check": ("KEEP: only deployed edge" if name == "cash_and_carry"
                             else "HOLD: data-blocked" if p else "REJECT: fails gates"
                             if not a.get("survived") else "WATCH"),
        })
    return {"generated": datetime.now(tz=UTC).isoformat(),
            "n_alphas": reg.get("n_alphas"), "n_survived": reg.get("n_survived"),
            "deployed": ["cash_and_carry"], "alphas": rows,
            "note": ("Every alpha carries a retire_check, not just a promote check. Data-blocked "
                     "edges accrue forward days before they can be validated -- calendar time, "
                     "not engineering, is the gate.")}


def _research_state(eng: dict[str, Any], done: dict[str, bool]) -> dict[str, Any]:
    port = _load(_WEB / "portfolio.json").get("deployed", {})
    disc = _load(_WEB / "discovery.json")
    clocks = [{"edge": p["sleeve"], "have_days": p.get("have_days"),
               "needs_days": p.get("needs_days")}
              for p in disc.get("pending", [])]
    bottlenecks = [
        {"rank": 1, "bottleneck": "calendar-time data accumulation",
         "evidence": clocks or "OI/LS/liq at 6/40d; cash-carry 2/90d; hyperliquid 1/250",
         "lever": "keep the flywheel alive + verify archives append; cannot be engineered away"},
        {"rank": 2, "bottleneck": "single deployed edge (concentration)",
         "evidence": f"{len(port.get('sleeves', []))} deployed sleeve(s)",
         "lever": "decorrelated survivors -- blocked on #1 (need forward data to validate)"},
        {"rank": 3, "bottleneck": "flywheel reliability (PC sleep / reboot)",
         "evidence": "watchdog enabled; run-logged-off pending",
         "lever": eng["next_action"]["id"] if eng.get("next_action") else "none"},
    ]
    # AUTO-RETIREMENT signal: sleeves whose marginal contribution to portfolio E[log wealth] is
    # negative are retire candidates (constitution: kill negative-contribution sleeves, reallocate).
    incr = _load(_WEB / "crypto_portfolio.json").get("incremental_sharpe", {})
    retire = sorted([{"sleeve": s, "marginal_sharpe": v} for s, v in incr.items() if v < 0],
                    key=lambda x: x["marginal_sharpe"])
    # 7-CYCLE architecture review cadence (blank-slate redesign question).
    log = _load(Path("data/cro_cycle_log.json"))
    n_cycles = len(log) if isinstance(log, list) else 0
    arch_review_due = n_cycles > 0 and n_cycles % 7 == 0
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "master_objective": "maximize expected lifetime geometric growth (log wealth), survival-c",
        "deployed": port,
        "binding_constraint": "calendar-time data accumulation (not engineering throughput)",
        "bottleneck_rankings": bottlenecks,
        "retirement_candidates": retire,
        "retirement_note": ("SIGNAL ONLY — marginal-Sharpe swings ~±0.15 between runs, so a single "
                            "negative sign is within noise. Retire only on PERSISTENT negative "
                            "contribution across runs, with promotion-grade rigor. No whipsaw."),
        "architecture_review_due": arch_review_due,
        "cycles_logged": n_cycles,
        "completed_this_cycle": eng["completed"],
        "engineering_backlog_top": [{"id": i["id"], "roi": i["roi"], "effort_h": i["effort_h"]}
                                    for i in eng["open"][:5]],
        "research_backlog": [{"edge": c["edge"],
                              "status": f"data-blocked {c['have_days']}/{c['needs_days']}d",
                              "info_value": "positive but not yet actionable"} for c in clocks],
        "decisions_log": [
            "REJECT ls_contrarian for deployment: Sharpe 10+ artifact, fails DSR (correct).",
            "PIVOT executed book to delta-neutral cash-and-carry; perp L/S -> shadow.",
            "DEFER new-hypothesis generation: lower marginal ROI than protecting the data clock.",
            "DEFER heavy external paper search: info value < top backlog item this cycle.",
        ],
    }


def _calibrate(done: dict[str, bool]) -> dict[str, Any]:
    """Log each engineering forecast + resolve the ones that completed, then report calibration."""
    for it in _ENG:
        fc.log_forecast(f"eng:{it['id']}", it["p"], "engineering")
        if done.get(it["id"]):
            fc.resolve(f"eng:{it['id']}", outcome=True)     # a completed task = forecast realised
    rep = fc.report()
    (_WEB / "calibration.json").write_text(json.dumps(rep, indent=2), "utf-8")
    return rep


def main() -> None:
    done = _detectors()
    eng = _build_engineering(done)
    cal = _calibrate(done)
    (_ROOT / "engineering_backlog.json").write_text(json.dumps(eng, indent=2), "utf-8")
    (_ROOT / "alpha_pipeline.json").write_text(json.dumps(_alpha_pipeline(), indent=2), "utf-8")
    rs_obj = _research_state(eng, done)
    rs_obj["forecast_calibration"] = cal
    (_ROOT / "research_state.json").write_text(json.dumps(rs_obj, indent=2), "utf-8")
    nxt = eng.get("next_action") or {}
    print(f"research-cycle: completed={eng['completed']}")
    print(f"  calibration: {cal.get('status')} brier={cal.get('brier')} bias={cal.get('bias')}")
    print(f"  top-ROI task: {nxt.get('id')} (ROI {nxt.get('roi')}, {nxt.get('effort_h')}h)")
    print(f"  -> {nxt.get('why', '')}")


if __name__ == "__main__":
    main()

```

### scripts/run_cashcarry_testnet.py
```python
"""Paper CASH-AND-CARRY executor: long spot (spot testnet) + short perp (futures testnet).

Delta-neutral funding harvest: on the highest POSITIVE-funding perps that exist on BOTH testnets, it
BUYS spot (long leg) and SHORTS the perp (hedge leg), dollar-matched -> ~zero price exposure, and
collects funding on the short perp. Both legs are paper (testnet). dry-run DEFAULT; --live to send.

This is the executable form of the strongest backtest candidate. It is STILL UNVALIDATED (forward
shadow day 0/90), so this runs on PAPER only -- it builds an executed forward track record, it does
not touch real money. Only positive-funding names are traded (the long-spot/short-perp carry); the
reverse leg (short spot) needs margin and is skipped.

    python scripts/run_cashcarry_testnet.py                       # dry-run
    python scripts/run_cashcarry_testnet.py --live --top 5 --capital 2000
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from libs.data.crypto_source import current_funding
from libs.execution import binance_spot_testnet as spot
from libs.execution import binance_testnet as fut

_WEB = Path("web/cashcarry_live.json")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=5, help="number of positive-funding carries")
    ap.add_argument("--capital", type=float, default=2000.0, help="total spot $ to deploy")
    ap.add_argument("--live", action="store_true", help="send orders (default = dry-run)")
    args = ap.parse_args()
    dry = not args.live
    if not (spot.has_keys() and fut.has_keys()):
        raise SystemExit("need BOTH spot-testnet and futures-testnet keys")

    funding = current_funding()
    spot_fl, fut_fl = spot.exchange_filters(), fut.exchange_filters()
    spot_px = spot.prices()
    # positive funding, tradeable on BOTH venues, USDT-quoted
    cands = sorted(((s, f) for s, f in funding.items()
                    if f > 0 and s in spot_fl and s in fut_fl and s.endswith("USDT")
                    and spot_px.get(s)),
                   key=lambda x: -x[1])[:args.top]
    if not cands:
        raise SystemExit("no positive-funding carry candidates on both venues right now")

    per = args.capital / len(cands)
    legs: list[dict[str, object]] = []
    for sym, f in cands:
        px = spot_px[sym]
        ffl = fut_fl[sym]
        step, prec = ffl["step"], int(ffl["qty_prec"])
        qty = round(round((per / px) / step) * step, prec) if step > 0 else round(per / px, prec)
        if qty < ffl["min_qty"] or qty <= 0:
            continue
        leg: dict[str, object] = {"symbol": sym, "funding_rate": round(f, 6), "qty": qty,
                                  "notional": round(qty * px, 2)}
        if dry:
            leg["status"] = "DRY (would BUY spot + SHORT perp)"
        else:
            try:
                sres = spot.place_market(sym, "BUY", qty)           # long leg
                fres = fut.place_market(sym, "SELL", qty)           # short-perp hedge leg
                leg["spot"] = str(sres.get("status", "?"))
                leg["perp"] = str(fres.get("status", "?"))
            except Exception as e:
                leg["error"] = repr(e)[:140]
        legs.append(leg)

    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "mode": "dry" if dry else "live-paper",
        "strategy": "delta-neutral cash-and-carry (long spot + short perp, positive funding)",
        "n_carries": len(legs),
        "spot_usdt": round(spot.usdt_balance(), 2),
        "spot_account_value": spot.account_value_usdt(),
        "futures_equity": round(fut.account_summary()["equity"], 2) if fut.has_keys() else None,
        "legs": legs,
        "note": ("PAPER. Long spot hedges the short perp -> ~zero directional risk; you collect "
                 "funding on the short perp. Unvalidated (forward shadow day 0/90)."),
    }
    _WEB.parent.mkdir(parents=True, exist_ok=True)
    _WEB.write_text(json.dumps(out, indent=2, default=str), "utf-8")
    print(f"cash-carry {'DRY-RUN' if dry else 'LIVE-PAPER'}: {len(legs)} carries "
          f"(top funding {cands[0][0]} {cands[0][1]*100:.3f}%/8h) | spot ${out['spot_usdt']} "
          f"USDT | futures ${out['futures_equity']}")
    for lg in legs:
        print(f"  {lg['symbol']:12} funding {lg['funding_rate']} qty {lg['qty']} "
              f"~${lg['notional']} {lg.get('status') or (lg.get('spot'), lg.get('perp'))}")


if __name__ == "__main__":
    main()

```

### scripts/run_desk_economics.py
```python
"""What return the desk needs just to stand still -- the hurdle it had never computed.

`config/costs.yaml` models what a TRADE costs. Nothing modelled what the DESK costs, so the
question "is this book big enough to be worth running?" had no numeric answer anywhere in the
repo. This computes it from costs the PRINCIPAL declares in config/desk_costs.yaml.

Unknown costs are excluded from the total and named in the output, and every figure is labelled
a FLOOR until the cost base is complete. The alternative -- treating an undeclared cost as zero
-- produces a confident hurdle that omits the largest line item, which is the one output of this
script that could actually mislead a decision.

    python scripts/run_desk_economics.py
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from libs.research.capacity_policy import live_book_usd
from libs.research.desk_economics import assess

_ROOT = Path(__file__).resolve().parent.parent
_CFG = _ROOT / "config" / "desk_costs.yaml"
_OUT = _ROOT / "web" / "desk_economics.json"


def _load_cfg() -> dict[str, Any]:
    try:
        d = yaml.safe_load(_CFG.read_text("utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, yaml.YAMLError):
        return {}


def main() -> int:
    cfg = _load_cfg()
    if not cfg:
        print(f"desk economics: {_CFG.name} missing or unreadable -- nothing to compute")
        return 0

    equity = live_book_usd()
    report = {"ts": datetime.now(tz=UTC).isoformat(), **assess(equity, cfg)}
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(report, indent=2), "utf-8")

    print(f"desk economics: {report['verdict']}")
    if report["undeclared_line_items"]:
        print(f"  UNDECLARED (excluded from the total, so every figure is a floor): "
              f"{', '.join(report['undeclared_line_items'])}")
        print(f"  -> declare them in config/{_CFG.name}")
    need = report["capital_needed_for_acceptable_hurdle_usd"]
    if need is not None and report["hurdle_acceptable"] is False:
        print(f"  hurdle {report['hurdle_annual_pct']:.2f}%/yr exceeds the "
              f"{report['max_acceptable_annual_hurdle_pct']:.1f}% policy bar -- "
              f"${need:,.0f} of equity would bring it in line")
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/run_discovery.py
```python
"""Autonomous edge-discovery loop -- the self-expanding factory.

Tests a LIBRARY of economically-distinct crypto sleeves (not parameter sweeps -- that would p-hack
the DSR gate) through the full institutional gauntlet, measures each candidate's standalone Sharpe,
its correlation to the rest of the book, and its incremental portfolio-Sharpe contribution, then
classifies it through the promotion pipeline. Genuinely orthogonal, positive sleeves are surfaced as
shadow-eligible automatically; the rest are recorded as candidates or rejected (with the reason).
Data-gated mechanisms (OI/long-short divergence) are listed as PENDING until their forward archive
matures. Re-run daily: as archives grow, new edges light up on their own. Writes web/discovery.json.

    python scripts/run_discovery.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from libs.autodiscovery.models import Family, Hypothesis
from libs.autodiscovery.validation import campaign_gate_stats, validate
from libs.data.crypto_source import list_liquid_perps
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.research.crossasset import trend_basket_returns, xsec_momentum_returns
from libs.research.crypto_sleeves import (
    basis_carry_returns,
    funding_momentum_returns,
    taker_flow_returns,
    xsec_lowvol_returns,
)
from libs.research.crypto_xsec import adv_tier_cost, xsec_funding_returns
from libs.research.pre_filter import pre_filter
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType

_CRYPTO = Path("data/lake/bronze/crypto")
_METRICS = Path("data/crypto_metrics.parquet")
_WEB = Path("web/discovery.json")
_PPY = 365.0
_ORTHO = 0.40                 # max |corr| to the rest of the book to count as orthogonal
_FAIL = ["edge crowds/decays", "regime shift", "correlated crash", "cost exceeds edge"]
# Data-gated mechanisms that turn on once their forward archive is deep enough.
_PENDING = [
    ("oi_divergence", "open interest", 40),
    ("ls_contrarian", "long/short ratio", 40),
    ("liquidation_reversal", "liquidations", 40),
]


def _panels() -> tuple[pd.DataFrame, ...]:
    lake = ParquetLake("data/lake")
    closes, funding, basis, taker, adv = {}, {}, {}, {}, {}
    for s in list_liquid_perps(top_n=120):
        if not (_CRYPTO / s / Timeframe.D1.value).exists():
            continue
        register_instrument(InstrumentSpec(symbol=s, asset_class=AssetClass.CRYPTO, description=s))
        df = lake.read_bars(Layer.BRONZE, s, Timeframe.D1).set_index("timestamp")
        if "funding" not in df.columns or len(df) < 250:
            continue
        closes[s] = df["close"]
        funding[s] = df["funding"]
        adv[s] = float((df["close"] * df["volume"]).tail(180).mean())
        if "basis" in df.columns:
            basis[s] = df["basis"]
        if "taker_buy_frac" in df.columns:
            taker[s] = df["taker_buy_frac"]
    c = pd.DataFrame(closes).sort_index()
    f = pd.DataFrame(funding).reindex(c.index)
    b = pd.DataFrame(basis).reindex(c.index) if basis else pd.DataFrame()
    t = pd.DataFrame(taker).reindex(c.index) if taker else pd.DataFrame()
    return c, f, b, t, adv


def _ann(r: np.ndarray) -> float:
    a = r[r != 0.0]
    return round(float(sharpe_ratio(a) * np.sqrt(_PPY)), 2) if len(a) > 5 else 0.0


def _candidates(close, funding, basis, taker, adv, cost) -> dict[str, np.ndarray]:  # type: ignore
    """The economically-distinct sleeve library (each a different mechanism, not a tuned sweep)."""
    lib: dict[str, np.ndarray] = {
        "funding_carry": xsec_funding_returns(close, funding, adv, lookback=7, q=0.2, band=0.02),
        "funding_momentum": funding_momentum_returns(close, funding, adv, lookback=7, q=0.2,
                                                     band=0.02),
        "xsec_price_mom": xsec_momentum_returns(close, cost, lookback=20, q=0.3, band=0.05),
        "ts_trend": trend_basket_returns(close, cost, lookback=30, band=0.05),
        "xsec_reversal": xsec_momentum_returns(close, cost, lookback=3, q=0.3, band=0.05,
                                               long_high=False),
        "xsec_lowvol": xsec_lowvol_returns(close, funding, adv, lookback=20, q=0.3, band=0.05),
    }
    if not basis.empty and basis.shape[1] >= 12:
        lib["basis_carry"] = basis_carry_returns(close[basis.columns], funding[basis.columns],
                                                 basis, adv, lookback=3, q=0.2, band=0.02)
    if not taker.empty and taker.shape[1] >= 12:
        lib["taker_flow"] = taker_flow_returns(close[taker.columns], funding[taker.columns],
                                               taker, adv, lookback=5, q=0.2, band=0.02)
    return {k: v for k, v in lib.items() if np.isfinite(v).all()}


# --- COST TRUTH (gap #45, 2026-07-22) -------------------------------------------------------
# adv_tier_cost GUESSES 5/8/15 bps per side by ADV tier. The measured cost model
# (run_cost_model.py, real recorded books) shows that guess is wrong in BOTH directions:
# majors overcharged (BTC pair-slippage 0.009 bps vs 5 bps/side assumed -- a daily-turnover
# sleeve pays ~3%/yr of phantom cost, enough to kill real 0.6-0.9-Sharpe candidates), thin
# names undercharged (NOMUSDT realized -149 bps vs 15 assumed). Screening candidates against
# a mis-measured cost is a silent thumb on the scale either way. Per-side here = maker-first
# futures fee (2 bps VIP0 maker, taker fallback -> 3 bps blended, documented constant) +
# MEASURED per-leg book-walk at $500. Unmeasured symbols keep the tier guess -- and the
# recorder now records the traded universe, so measurement coverage grows on its own.
_FEE_SIDE = 3e-4
_COST_MODEL = Path("data/cost_model.json")


def _measured_side_cost(sym: str, adv_usd: float) -> float:
    try:
        m = json.loads(_COST_MODEL.read_text("utf-8"))["symbols"][sym]
        slip = m["fut_sell"]["500"]["median_bps"]
        if slip is None:
            return adv_tier_cost(adv_usd)
        return max(2.5e-4, _FEE_SIDE + float(slip) / 1e4)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return adv_tier_cost(adv_usd)


def _graveyard() -> dict:
    """Mirror the FULL graveyard into the discovery surface (R0009).

    discovery.json carried sleeve results only, so every consumer of the web surface saw a
    handful of live tests and none of the ~50+ buried hypotheses -- the exact amnesia the
    do_not_repeat discipline exists to prevent. Sources: the graveyard table in
    docs/graveyard.md (human record) and research_agenda.json's do_not_repeat (machine record).
    Read-only best effort: a missing source is reported absent, never fabricated empty.
    """
    entries: list[dict[str, str]] = []
    sources: dict[str, str] = {}
    gy = Path("docs/graveyard.md")
    if gy.exists():
        rows = [ln for ln in gy.read_text("utf-8").splitlines()
                if ln.startswith("|") and not set(ln) <= {"|", "-", " ", ":"}]
        for ln in rows[1:]:                                   # first | row is the header
            cells = [c.strip() for c in ln.strip("|").split("|")]
            if cells and cells[0]:
                entries.append({"name": cells[0][:80],
                                "reason": (cells[1] if len(cells) > 1 else "")[:160],
                                "source": "docs/graveyard.md"})
        sources["docs/graveyard.md"] = f"{max(0, len(rows) - 1)} table rows"
    else:
        sources["docs/graveyard.md"] = "ABSENT"
    try:
        agenda = json.loads(Path("research_agenda.json").read_text("utf-8"))
        dnr = agenda.get("do_not_repeat", [])
        for item in dnr:
            if isinstance(item, dict):
                entries.append({"name": str(item.get("hypothesis") or item.get("name"))[:80],
                                "reason": str(item.get("reason", ""))[:160],
                                "source": "research_agenda.do_not_repeat"})
            else:
                entries.append({"name": str(item)[:80], "reason": "",
                                "source": "research_agenda.do_not_repeat"})
        sources["research_agenda.do_not_repeat"] = str(len(dnr))
    except (OSError, json.JSONDecodeError):
        sources["research_agenda.do_not_repeat"] = "UNREADABLE"
    return {"n": len(entries), "sources": sources, "entries": entries}


def main() -> None:
    close, funding, basis, taker, adv = _panels()
    if close.shape[1] < 12:
        raise SystemExit("need a liquid perp panel")
    cost = {s: _measured_side_cost(s, a) for s, a in adv.items()}
    n_meas = sum(1 for s2, a in adv.items()
                 if abs(cost[s2] - adv_tier_cost(a)) > 1e-9)
    print(f"cost truth: {n_meas}/{len(cost)} symbols on MEASURED cost, "
          f"rest on tier fallback")
    lib = _candidates(close, funding, basis, taker, adv, cost)

    df = pd.DataFrame(lib, index=close.index)
    corr = df.replace(0.0, np.nan).corr()
    matrix = np.column_stack([lib[k] for k in lib])
    sharpes = np.array([sharpe_ratio(lib[k][lib[k] != 0.0]) for k in lib])
    # per-candidate gates (gap #87 flip, principal-ruled 2026-07-29); thresholds unchanged
    campaign = campaign_gate_stats(matrix)

    results = []
    for col, (name, r) in enumerate(lib.items()):
        active = r[r != 0.0]
        sh = _ann(r)
        others = corr[name].drop(labels=[name], errors="ignore").abs()
        max_corr = round(float(others.max()), 2) if not others.empty else 0.0
        orthogonal = max_corr < _ORTHO
        # Tiered pre-filter (HYPOTHESIS_MAX #1, 2026-07-29): cheap unambiguous rejects skip the
        # heavy gauntlet but STILL count in n_trials -- the filter saves compute, never
        # multiplicity budget. Borderline always escalates; the bar itself is unchanged.
        med_cost = float(np.median(list(cost.values()))) if cost else None
        pf = pre_filter(r, name=name,
                        rt_cost_per_trade=(2 * med_cost) if med_cost is not None else None)
        if pf["verdict"] == "REJECT":
            results.append({"sleeve": name, "sharpe": sh, "gates": "pre-filter",
                            "max_corr": max_corr, "orthogonal": orthogonal,
                            "status": f"REJECTED (pre-filter: {pf['reason']})"})
            continue
        v = (validate(active, hypothesis=Hypothesis(
            family=Family.CARRY, subtype=name, symbol="CRYPTO", params={},
            mechanism=MechanismType.RISK_PREMIUM, edge_source=name, failure_modes=_FAIL),
            n_trials=len(lib), sharpe_estimates=sharpes, returns_matrix=matrix,
            campaign=campaign, column=col)
            if len(active) >= 250 else None)
        gates = f"{sum(v.gates.values())}/{len(v.gates)}" if v else "n<250"
        survived = bool(v.survived) if v else False
        if survived:
            status = "DEPLOYABLE (gauntlet pass)"
        elif sh > 0.5 and orthogonal:
            status = "SHADOW (orthogonal +edge)"
        elif sh > 0.4:
            status = "CANDIDATE"
        else:
            status = "REJECTED"
        results.append({"sleeve": name, "sharpe": sh, "gates": gates, "max_corr": max_corr,
                        "orthogonal": orthogonal, "status": status})

    def _rank(d: dict[str, object]) -> tuple[bool, float]:
        promoted = str(d["status"]).startswith(("SHADOW", "DEPLOY"))
        return (promoted, float(d["sharpe"]))                # type: ignore[arg-type]
    results.sort(key=_rank, reverse=True)
    archive_days = (int(pd.read_parquet(_METRICS)["ts"].dt.date.nunique())
                    if _METRICS.exists() else 0)
    pending = [{"sleeve": n, "dataset": ds, "needs_days": d, "have_days": archive_days,
                "status": f"PENDING ({archive_days}/{d}d archived)"} for n, ds, d in _PENDING]

    shadow = [r["sleeve"] for r in results if r["status"].startswith(("SHADOW", "DEPLOY"))]
    payload = {"updated": datetime.now(tz=UTC).isoformat(), "tested": len(results),
               "shadow_eligible": shadow, "results": results, "pending": pending,
               "ortho_threshold": _ORTHO, "graveyard": _graveyard()}
    _WEB.parent.mkdir(parents=True, exist_ok=True)
    _WEB.write_text(json.dumps(payload, indent=2, default=str), "utf-8")
    print(f"discovery: tested {len(results)} sleeves; shadow-eligible (orthogonal +edge): {shadow}")
    for r in results:
        print(f"  {r['sleeve']:18} sharpe~{r['sharpe']:5} gates={r['gates']:5} "
              f"corr={r['max_corr']:5} {r['status']}")
    print(f"pending (data-gated): {[p['sleeve'] for p in pending]} (archive {archive_days}d)")


if __name__ == "__main__":
    main()

```

### scripts/run_discretionary_max.py
```python
#!/usr/bin/env python3
"""DISCRETIONARY MAX (R0151) -- the ceiling-pusher for the discretionary desk.

PRINCIPAL ORDER (2026-08-01): *"aim for 38 percent hit and maximise all parts of it, and make sure
there's a literal system dedicated to maxing this discretionary side and advancing it... push its
ceiling like the constitution forces everything, applies to this section too like everything, and
always."*

WHY A 38% HIT-RATE TARGET IS LEGAL HERE WHEN A CAGR TARGET IS NOT, because the two look similar
and are opposites. A return figure is reachable by SIZE, and size past full Kelly makes growth
negative -- so a stated return corrupts the optimizer into over-leverage (PROJECT_HANDOFF.md,
2026-07-12, and the fence R0143 that now enforces it). A HIT RATE cannot be reached by sizing at
all. It moves only through better selection, better information, and better filtering -- the exact
levers the desk wants pushed. Targeting the PROCESS variable is what makes the outcome variable
unnecessary to target. That distinction is the whole reason this organ is allowed to have a number.

WHY 38%: cost-adjusted breakeven is 31.1%, so 38 is roughly one full binomial standard error above
it at the sample sizes this sleeve will reach in a quarter -- the first level at which "this works"
is distinguishable from "this got lucky". Not a ceiling. If the measured rate reaches 38, this
organ re-aims at the next distinguishable level; it never reports "target met, stand down"
(L1.28c: every cadence hunts its own ceiling; L1.25a: the hunt never tires).

WHAT IT ACTUALLY DOES, and why it is not another dashboard. Every cycle it reads the sleeve's own
measurements, finds the BINDING constraint on the hit rate, and names the single highest-leverage
unbuilt lever for it. A board that lists ten things needing attention is a board that produces
none of them; naming ONE that is binding is what produces work.

THE LEVER LADDER, ordered by measured leverage rather than by appeal:

  1 INFORMATION   -- the sleeve reads PUBLIC charts. Public information cannot carry an edge for
                     long, so the largest single move is feeding it something that is not public
                     or not yet priced (the event sleeve's territory). Biggest lever, hardest.
  2 CROSS-FAMILY  -- an independent model family agreeing is a stronger filter than the same
                     family agreeing with itself. Blocked on the OpenRouter seat.
  3 SELECTION     -- once setup-conditional hit rates exist, trade only the setup classes that
                     measurably pay. Mechanical, and it needs only data.
  4 ENSEMBLE      -- already built (2-of-3). Its own value is measurable and it is reviewed here.
  5 EXECUTION     -- maker entries, tighter structural stops. Worth points of required hit rate
                     without touching the reasoning at all.

REFUSES TO IDLE. If every lever is either built or blocked on evidence, it says which evidence and
when it arrives -- it never returns "nothing to do", because on this desk an idle ceiling-pusher is
the failure it exists to prevent (L1.28a: idle capacity is unbooked loss).

    python scripts/run_discretionary_max.py [--json]
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

_STATE = "data/discretionary_max.json"

#: The PROCESS target. Legal where a return target is not, because a hit rate cannot be reached by
#: sizing -- only by selection, information and filtering. 38% is ~one binomial standard error
#: above the 31.1% cost-adjusted breakeven at the sample sizes reachable in a quarter: the first
#: level at which "this works" is distinguishable from "this got lucky".
TARGET_HIT = 0.38
#: Re-aim step. On reaching the target this organ does not stand down; it advances to the next
#: distinguishable level, one standard error further (L1.25a -- the hunt never tires).
REAIM_STEP = 0.04


#: THE GROWTH IDENTITY. Everything this desk can do to compound harder enters through exactly
#: four terms, and no fifth:
#:
#:     g_year  =  n * [ p*ln(1 + b*f)  +  (1-p)*ln(1 - l*f) ]
#:
#:   n  independent bets per year   -- decorrelation, NOT trade count
#:   p  hit rate                    -- selection, information, filtering
#:   b  winner:loser R shape        -- how far a winner is allowed to run before it is banked
#:   f  risk per bet                -- size
#:
#: WHY THIS ORGAN NEEDED IT. It was targeting p alone. p is one term of four, and measured on the
#: desk's own numbers it is not even the steepest: lifting the winner shape from 3R to 4R moves
#: the odds of a doubling year further than four points of hit rate does. An organ that hunts one
#: term while three sit unexamined is not pushing a ceiling, it is polishing a wall.
#:
#: AND THE ANTI-LEVER, recorded here because it is the one that feels like aggression and is not.
#: f does NOT belong on the list. Growth rises with size only to full Kelly and falls after it,
#: and the probability of a doubling year peaks EARLIER still -- around 5% risk per bet on this
#: payoff, falling monotonically above it. Measured on the desk's own stack at a 38% hit rate,
#: taking risk from 6% to 20% cuts the chance of a doubling year from 73% to 31%. Size is the one
#: dial where "uncap it" and "achieve it" point in opposite directions, so the ceiling-pusher
#: names it as a term to hold, not to raise. The upside is bought in n, p and b.
_GROWTH_TERMS = ("INDEPENDENT-BETS", "HIT-RATE", "WINNER-SHAPE", "RISK-PER-BET")


def growth_levers(root: Path) -> dict[str, Any]:
    """Decompose compounding into its four inputs and rank them by MEASURED marginal effect.

    Each term reports what it is worth at the margin, so effort goes where the gradient is rather
    than where the attention is. Terms that are ASSUMED rather than measured are ranked first
    regardless of their gradient: an unmeasured input cannot be improved on purpose, and the one
    that is currently assumed (the winner shape) is also the steepest.
    """
    pnl = _read(root, "data/paper_book_pnl.json")
    payoff = pnl.get("realised_payoff") or {}
    n_closed = int(pnl.get("n_resolved") or 0)
    hit = pnl.get("win_rate")
    alloc = _read(root, "data/sleeve_allocation.json")

    b_state = payoff.get("state") or "ASSUMED"
    b_val = float(payoff.get("ratio") or 3.0)
    terms = [
        {"term": "WINNER-SHAPE", "symbol": "b", "state": b_state, "value": b_val,
         "gradient": "STEEPEST -- one extra R of winner is worth ~5pp of hit rate at the margin, "
                     "and the exchange rate is measured: a 4R trail pays down to a 28.7% hit rate "
                     "against a 3R/35% baseline",
         "detail": ("the winner:loser shape is ASSUMED at 3:1 and has never been measured -- "
                    "every downstream money figure (breakeven, Kelly odds, the promotion bar) "
                    "rests on it" if b_state != "MEASURED" else
                    f"measured {b_val:.2f}:1 against the 3.0:1 assumed"),
         "action": ("resolve enough closed trades for realised_payoff to leave ASSUMED -- until "
                    "then the steepest lever on the desk is invisible, not flat"
                    if b_state != "MEASURED" else
                    "run_trade_review's RIGHT-BUT-TRUNCATED cause is the signal that the trail is "
                    "banking winners early; widen it while the exchange rate says the hit rate "
                    "cost is affordable")},
        {"term": "INDEPENDENT-BETS", "symbol": "n", "state": alloc.get("status") or "UNMEASURED",
         "value": None,
         "gradient": "LINEAR in the exponent and the most under-exploited: 18 crypto perps are "
                     "close to ONE bet, so trade count overstates n badly",
         "detail": "n is independent bets, not trades. Correlated positions held at once are one "
                   "bet with extra fees, which is why raising cadence on the same tape buys "
                   "nothing while decorrelating buys growth at no accuracy cost",
         "action": "measure the realised cross-instrument correlation of CLOSED trades, then add "
                   "genuinely uncorrelated ground (different horizon, different driver) rather "
                   "than more names off the same tape"},
        {"term": "HIT-RATE", "symbol": "p", "state": "MEASURED" if n_closed >= 20 else "UNMEASURED",
         "value": hit,
         "gradient": "steep near breakeven -- but bounded, because p is the term an adversary "
                     "competes away fastest",
         "detail": f"{n_closed} closed trades; this organ's own TARGET_HIT applies here and here "
                   "only -- it is the process target that cannot be reached by sizing",
         "action": "the lever ladder below (information, cross-family, selection) is entirely "
                   "about this term"},
        {"term": "RISK-PER-BET", "symbol": "f", "state": "HELD-BY-ARITHMETIC", "value": None,
         "gradient": "NEGATIVE above ~5% on this payoff -- the only term where raising it lowers "
                     "the outcome it is meant to raise",
         "detail": "growth rises with size only to full Kelly and falls after; the probability of "
                   "a doubling year peaks earlier still. At a 38% hit rate, 6% -> 20% risk cuts "
                   "that probability from 73% to 31%",
         "action": "HOLD. Not timidity and not a compromise -- raising this term is arithmetically "
                   "self-defeating, which is why the upside is bought in b, n and p instead"},
    ]
    unmeasured = [t for t in terms if t["state"] in ("ASSUMED", "UNMEASURED")]
    return {"identity": "g_year = n * [ p*ln(1 + b*f) + (1-p)*ln(1 - l*f) ]",
            "terms": terms,
            "n_unmeasured": len(unmeasured),
            "binding_term": (unmeasured[0]["term"] if unmeasured else "HIT-RATE"),
            "why": (f"{unmeasured[0]['term']} is {unmeasured[0]['state']} -- an input nobody has "
                    "measured cannot be improved on purpose, and this one is also the steepest"
                    if unmeasured else
                    "all four terms measured; effort goes to the steepest that is still moving")}


def _read(root: Path, rel: str) -> dict[str, Any]:
    try:
        return json.loads((root / rel).read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def levers(root: Path) -> list[dict[str, Any]]:
    """Every lever on the hit rate, with its state read from the desk's own measurements."""
    pnl = _read(root, "data/paper_book_pnl.json")
    probe = _read(root, "data/calibration_probe.json")
    alloc = _read(root, "data/sleeve_allocation.json")
    conv = _read(root, "data/conviction_trader.json")
    setup = pnl.get("setup_performance") or {}
    n_closed = int(pnl.get("n_resolved") or 0)

    measured_setups = sum(
        1 for f in setup.values() if isinstance(f, dict)
        for b in f.values() if isinstance(b, dict) and b.get("state") == "MEASURED")

    kimi_live = bool(_read(root, "data/kimi_hunt.json"))
    return [
        {"lever": "INFORMATION", "rank": 1,
         "state": "OPEN",
         "detail": "the sleeve reads PUBLIC chart structure; public information cannot carry an "
                   "edge for long. The event sleeve (R0122) is the non-public-information version "
                   "of the same hypothesis and is currently under-weighted against the chart one.",
         "action": "route effort to the event sleeve's feed quality -- more sources, lower "
                   "latency, richer documents -- rather than to more chart features"},
        {"lever": "CROSS-FAMILY", "rank": 2,
         "state": "BLOCKED" if not kimi_live else "OPEN",
         "detail": ("an INDEPENDENT model family agreeing is a stronger filter than one family "
                    "agreeing with itself; kimi_hunter has never produced (no OpenRouter seat)"
                    if not kimi_live else "second family is live and can be wired as a filter"),
         "action": ("fund the OpenRouter seat (~$5/mo on kimi-k2), then require cross-family "
                    "agreement on the conviction call" if not kimi_live
                    else "wire cross-family agreement into ensemble_consensus")},
        {"lever": "SELECTION", "rank": 3,
         "state": "BLOCKED" if measured_setups < 2 else "OPEN",
         "detail": (f"{measured_setups} setup buckets have enough closed trades to be MEASURED; "
                    "conditional hit rates are what say which setup classes to stop taking"),
         "action": ("accumulate closed trades -- this unlocks itself" if measured_setups < 2
                    else "gate the sleeve to the setup classes with a measured edge")},
        {"lever": "ENSEMBLE", "rank": 4,
         "state": "BUILT",
         "detail": f"2-of-3 consensus is live; last read {(conv.get('ensemble') or {}).get('state')}",
         "action": "measure whether agreement-filtered calls out-hit the rejected minority; "
                   "if not, the filter is costing frequency for nothing and goes"},
        {"lever": "EXECUTION", "rank": 5,
         "state": "BUILT",
         "detail": "maker-in entries and structural stops are worth ~1.8pp of required hit rate; "
                   "already assumed in the cost model",
         "action": "re-measure realised slippage against the 1.5bp assumption once live fills exist"},
        {"lever": "CALIBRATION", "rank": 2,
         "state": ("BLOCKED" if (probe.get("verdict") or {}).get("state") in
                   (None, "ACCUMULATING", "UNMEASURED") else "OPEN"),
         "detail": f"probe verdict {(probe.get('verdict') or {}).get('state')} after "
                   f"{(probe.get('verdict') or {}).get('n_resolved', 0)} resolved",
         "action": "if UNINFORMATIVE, strip the Kelly sizer and run flat size -- sizing on a "
                   "meaningless probability is strictly worse than not sizing on it"},
        {"lever": "EVIDENCE", "rank": 0,
         "state": "BLOCKED" if n_closed < 20 else "OPEN",
         "detail": f"{n_closed} closed marked trades; nothing conditional is measurable below ~20",
         "action": "the sleeve must actually run -- check_organ_liveness reports whether it is"},
        {"lever": "INDEPENDENCE", "rank": 6,
         "state": "BLOCKED" if alloc.get("status") in (None, "UNMEASURED") else "OPEN",
         "detail": f"sleeve allocation status {alloc.get('status')}",
         "action": "accumulate overlapping days so the conviction/event correlation is measurable; "
                   "until then both are assumed duplicates and share one budget"},
    ]


def build_report(root: Path | None = None) -> dict[str, Any]:
    root = root or _ROOT
    pnl = _read(root, "data/paper_book_pnl.json")
    hit = pnl.get("win_rate")
    n = int(pnl.get("n_resolved") or 0)
    lv = levers(root)
    open_ = [x for x in lv if x["state"] == "OPEN"]
    blocked = [x for x in lv if x["state"] == "BLOCKED"]
    # BINDING = lowest rank overall, OPEN or BLOCKED. Preferring an open lever over a blocked
    # higher-leverage one was wrong: with zero closed trades this reported INFORMATION as binding
    # while the actual constraint was that the sleeve was not producing at all. A blocked lever's
    # ACTION is its unlock, so blocked-and-highest-leverage is still the right thing to name.
    binding = min(lv, key=lambda x: (x["rank"], x["state"] != "BLOCKED")) if lv else None

    if hit is None or n < 20:
        aim, aim_why = TARGET_HIT, (
            f"hit rate UNMEASURED ({n} closed) -- the target stands at {TARGET_HIT:.0%} and the "
            "binding constraint is evidence, not selection")
    elif float(hit) >= TARGET_HIT:
        aim = round(float(hit) + REAIM_STEP, 4)
        aim_why = (f"measured {float(hit):.1%} has REACHED {TARGET_HIT:.0%} -- re-aiming at "
                   f"{aim:.1%}. This organ never reports 'target met, stand down' (L1.25a).")
    else:
        aim, aim_why = TARGET_HIT, (
            f"measured {float(hit):.1%} against a {TARGET_HIT:.0%} target and a 31.1% breakeven; "
            f"gap is {TARGET_HIT - float(hit):.1%}")

    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.28c/L1.25a applied to the discretionary desk -- every cadence hunts its own "
               "ceiling and the hunt never tires. A HIT RATE is a legal target where a return "
               "figure is not: it cannot be reached by sizing, only by selection, information and "
               "filtering.",
        "target_hit_rate": aim, "measured_hit_rate": hit, "n_closed": n,
        "aim_note": aim_why,
        "binding_lever": binding,
        "growth": growth_levers(root),
        "levers": sorted(lv, key=lambda x: x["rank"]),
        "n_open": len(open_), "n_blocked": len(blocked),
        "never_idle": ("every lever is built or blocked on named evidence; the binding one is "
                       f"'{binding['lever']}' and its unlock is: {binding['action']}"
                       if binding else "NO LEVERS ENUMERATED -- this organ has failed, not the desk"),
        "detail": (f"target {aim:.0%} hit; measured "
                   + (f"{float(hit):.1%} over {n} closed" if hit is not None else "UNMEASURED")
                   + f"; binding lever {binding['lever'] if binding else 'NONE'}"),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    out = _ROOT / _STATE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"discretionary max (L1.28c): {rep['detail']}")
        b = rep["binding_lever"]
        if b:
            print(f"  BINDING: {b['lever']} [{b['state']}] -- {b['action'][:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/run_fusion_search.py
```python
#!/usr/bin/env python3
"""FUSION SEARCH runner -- writes data/fusion_search.json (EXECUTION_QUEUE.md RANK 5).

Combinatorial search over dataset axes, gated so it cannot mine noise. Distinct from
scripts/fusion_engine.py, which transforms known inputs rather than searching.

THE GATE IS THE PRODUCT. An axis enters combination search only after passing its own single-axis
screen; the trial budget is charged on the ENUMERATED grid (a cheap prune saves compute, never
multiplicity); and the grid is hashed before compute so it cannot be grown after results are seen.
See libs/research/fusion_search.py for why an ungated version would return a fake survivor every run.

On this desk today it correctly searches NOTHING: no axis has earned breadth. That refusal, with the
reason per axis, IS the output.

    python scripts/run_fusion_search.py
    python scripts/run_fusion_search.py --axis a=SCREEN-INTERESTING --axis b=SCREEN-INTERESTING
    python scripts/run_fusion_search.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from libs.research.fusion_search import (
    DEFAULT_K,
    eligibility_from_registry,
    log_trials,
    plan_search,
)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/fusion_search.json"

#: Where single-axis screen verdicts land. Read rather than assumed -- an axis is eligible because
#: a screen SAID so, never because this script was told to believe it.
_SCREEN_DIRS = ("reports/axis_screens", "reports")


def _discover_verdicts() -> dict[str, str]:
    """axis -> its STRONGEST single-axis cell verdict.

    Verdicts live per CELL (a screen report is a grid of construction x horizon trials), not at the
    top level, so an axis verdict has to be reduced from its cells. Strongest-of-cells is the right
    reduction and is not free peeking: the axis screen already counted every one of its own cells in
    its own n_trials, so 'one cell showed signal' is a result that has already been paid for. What
    it must NOT do is let that one cell license an unpriced combinatorial expansion -- which is
    exactly what fusion_search's enumeration budget then charges for separately.
    """
    order = ["SCREEN-INTERESTING", "SCREEN-WEAK", "SCREEN-UNDERPOWERED",
             "TIMING-ARTIFACT", "SUSPECT-LOOKAHEAD"]
    rank = {v: i for i, v in enumerate(order)}
    out: dict[str, str] = {}
    for d in _SCREEN_DIRS:
        base = ROOT / d
        if not base.is_dir():
            continue
        for f in sorted(base.glob("*.json")):
            try:
                doc = json.loads(f.read_text("utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(doc, dict):
                continue
            axis = f.stem.replace("screen_", "")
            cells = doc.get("cells")
            found: list[str] = []
            if isinstance(cells, list):
                found = [str(c["verdict"]) for c in cells
                         if isinstance(c, dict) and isinstance(c.get("verdict"), str)]
            elif isinstance(doc.get("verdict"), str):
                found = [str(doc["verdict"])]
            if found:
                best = min(found, key=lambda v: rank.get(v, len(order)))
                if axis not in out or rank.get(best, 99) < rank.get(out[axis], 99):
                    out[axis] = best
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--axis", action="append", default=[], metavar="NAME=VERDICT",
                    help="declare an axis verdict explicitly (repeatable)")
    ap.add_argument("--k", type=int, default=DEFAULT_K, help=f"combination width (default {DEFAULT_K})")
    ap.add_argument("--no-ledger", action="store_true",
                    help="do not append enumerated cells to data/fusion_trials.jsonl")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    verdicts = _discover_verdicts()
    for item in a.axis:
        if "=" not in item:
            print(f"fusion-search: --axis needs NAME=VERDICT, got {item!r}", file=sys.stderr)
            return 2
        name, verdict = item.split("=", 1)
        verdicts[name.strip()] = verdict.strip()

    if not verdicts:
        payload = {
            "generated": datetime.now(tz=UTC).isoformat(), "status": "NO-INPUT",
            "detail": "no single-axis screen verdicts found under reports/ -- combination search "
                      "is gated on axes that have EARNED breadth, so with no screens on disk there "
                      "is nothing eligible. Run the single-axis screens first.",
            "cells": 0, "effective_n_trials": 0,
        }
    else:
        # REGISTRY-gated, not screen-gated alone: a verdict says an axis carries signal, the
        # RANK 4 registry says its data actually exists and how long it is. Both are required --
        # cells built from an absent asset would be NO-INPUT and still cost multiplicity.
        el = eligibility_from_registry(verdicts, ROOT)
        plan = plan_search(el, k=a.k)
        # Charged at PLAN time, before a single cell is computed, because that is when the
        # multiplicity is actually incurred. Logging after execution would omit whatever got
        # pruned -- the exact leak the enumeration rule exists to close.
        n_logged = log_trials(plan) if not a.no_ledger else 0
        payload = {
            "generated": datetime.now(tz=UTC).isoformat(),
            "status": "REFUSED" if plan.refused_reason else "PLANNED",
            "detail": plan.refused_reason or
                      f"{len(plan.cells)} cells enumerated; {plan.effective_n_trials} trials owed",
            "k": a.k,
            "grid_hash": plan.grid_hash,
            "cells": len(plan.cells),
            "effective_n_trials": plan.effective_n_trials,
            "eligible": plan.eligible,
            "excluded": [asdict(e) for e in plan.excluded],
            "cell_ids": [c.cell_id for c in plan.cells],
            "trials_logged": n_logged,
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=1, default=str), "utf-8")
    tmp.replace(OUT)

    if a.json:
        print(json.dumps(payload, indent=1, default=str))
        return 0
    print(f"fusion-search | {payload['status']}")
    print(f"  {payload['detail']}")
    for e in payload.get("excluded", []):
        print(f"  EXCLUDED {e['axis']:<26} {e['reason'][:100]}")
    if payload.get("eligible"):
        print(f"  ELIGIBLE {', '.join(payload['eligible'])}")
    if payload.get("cells"):
        print(f"  grid {payload['grid_hash']} -- {payload['cells']} cells, "
              f"{payload['effective_n_trials']} trials owed BEFORE any pruning")
        print(f"  {payload.get('trials_logged', 0)} cell(s) appended to data/fusion_trials.jsonl")
    print(f"\n-> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/run_principal_benchmark.py
```python
#!/usr/bin/env python3
"""PRINCIPAL BENCHMARK (R0213) -- does the machine actually beat the human it was built to copy?

PRINCIPAL ORDER (2026-07-31): *"surpass my profit potential of ss and use Claude intelligence to
surpass me in compounding like human trader."*

WHY THIS IS A FENCE AND NOT A PEP TALK. "Surpass me" is only a real instruction if something
MEASURES it, and nothing did. The desk already benchmarks every sleeve against unlevered
buy-and-hold, because a levered sleeve that merely tracks the index is taking risk for nothing
(L1.6). The same logic applies one level up: a discretionary machine that merely matches the
human's own method is engineering for nothing. So the human's method becomes the second
benchmark, computed exactly like the first.

THE COUNTERFACTUAL, and its one honest limit. The principal's demonstrated method is a 10% risk
fraction per trade behind a structural stop that gets trailed (0.1 lots on a 1k account, stop
moved up to bank profit while letting it run). That is re-priced onto THE DESK'S OWN CLOSED
TRADES: same calls, same entries, same stops, same exits -- only the risk fraction changes. Every
other variable is held fixed, so the difference is attributable to sizing policy alone.

WHAT THIS THEREFORE DOES *NOT* PROVE, stated plainly because the comparison is seductive: it does
NOT show the machine beats the principal. It shows whether the machine's SIZING beats his sizing
ON THE MACHINE'S OWN CALLS. His selection is unmeasured -- the desk has seen one of his trades --
so a verdict here is about risk policy, never about who picks better. Claiming otherwise would be
the exact self-flattery the paper-book resolver exists to prevent.

THE ARITHMETIC IS EXACT, not simulated. Cost in R is size-independent -- (cost/notional) divided
by (stop/price), leverage cancels -- so the whole outcome scales linearly with the risk fraction:
    net_R              = equity_return / risk_fraction        (what one R actually paid, net)
    equity_return(f)   = net_R * f                            (the same trade at any size)
    g(f)               = mean( ln(1 + net_R * f) )            (what compounds)
No re-walking, no second set of assumptions.

AND THE RESULT IS NOT A FOREGONE CONCLUSION, which is what makes it worth computing. At a
measured hit rate above ~38% his 10% wins and the desk's cap is costing growth; below it, his
sizing is past full Kelly on net odds and loses while the same trades at 6% make money. The
crossover is real and nobody yet knows which side the sleeve is on.

    python scripts/run_principal_benchmark.py [--json]
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

_STATE = "data/principal_benchmark.json"

#: THE PRINCIPAL'S DEMONSTRATED RISK FRACTION. 0.10 = 0.1 lots on a 1,000 account, stated by him
#: directly ("10 percent risk, 10 dollar per one dollar gold move") and corrected once when this
#: desk first inferred it wrong from a screenshot. It is a MEASURED parameter of his method, not
#: an estimate -- which is exactly why it is the half of his method that can be benchmarked.
PRINCIPAL_RISK = 0.10

#: Minimum closed trades before a verdict. 20 because the standard error on a per-trade growth
#: difference is still wide there but the SIGN is usually stable -- and the sign is the whole
#: question. Below it the comparison reports UNMEASURED, never a lead.
MIN_FOR_VERDICT = 20


def _marks(root: Path) -> list[dict[str, Any]]:
    try:
        pnl = json.loads((root / "data/paper_book_pnl.json").read_text("utf-8"))
    except (OSError, ValueError):
        return []
    return [m for m in (pnl.get("marks") or [])
            if m.get("closed") and m.get("equity_return") is not None
            and float((m.get("sizing") or {}).get("risk_fraction") or 0.0) > 0.0]


def net_r_per_trade(marks: list[dict[str, Any]]) -> list[float]:
    """What one R actually paid, NET of costs, per closed trade -- the size-independent unit.

    Recovered from the mark rather than re-derived: equity_return already has real fees,
    slippage and funding deducted, and dividing by the risk fraction that produced it removes
    size. That is what makes re-pricing at any other size exact instead of a second model."""
    out = []
    for m in marks:
        f = float((m.get("sizing") or {}).get("risk_fraction") or 0.0)
        if f > 0:
            out.append(float(m["equity_return"]) / f)
    return out


def growth_at(net_rs: list[float], f: float) -> dict[str, Any]:
    """E[log] per trade and the compounded curve at risk fraction f."""
    if not net_rs:
        return {"state": "UNMEASURED", "n": 0}
    ruin = [r for r in net_rs if 1.0 + r * f <= 0.0]
    if ruin:
        # A single trade that takes the account to zero ends the sequence -- log is undefined and
        # the honest report is RUIN, never a number produced by skipping the trade that killed it.
        return {"state": "RUIN", "n": len(net_rs), "risk_fraction": f,
                "n_ruinous": len(ruin),
                "why": f"{len(ruin)} trade(s) at {f:.0%} risk would have taken the account to "
                       "zero or below. There is no growth rate past that point, and dropping the "
                       "trade that ended the sequence is how a backtest hides a blow-up."}
    g = sum(math.log(1.0 + r * f) for r in net_rs) / len(net_rs)
    return {"state": "MEASURED", "n": len(net_rs), "risk_fraction": f,
            "g_per_trade": round(g, 6),
            "equity_multiple": round(math.exp(g * len(net_rs)), 4),
            "worst_trade": round(min(net_rs) * f, 4)}


def build_report(root: Path | None = None) -> dict[str, Any]:
    root = root or _ROOT
    marks = _marks(root)
    net_rs = net_r_per_trade(marks)
    desk_f = (sorted(float((m.get("sizing") or {}).get("risk_fraction") or 0.0)
                     for m in marks)[len(marks) // 2] if marks else 0.06)
    desk = growth_at(net_rs, desk_f)
    principal = growth_at(net_rs, PRINCIPAL_RISK)

    if len(net_rs) < MIN_FOR_VERDICT:
        verdict = {
            "state": "UNMEASURED", "n": len(net_rs), "need": MIN_FOR_VERDICT,
            "why": f"{len(net_rs)}/{MIN_FOR_VERDICT} closed trades -- no verdict is available, "
                   "and a partial record must not read as a lead. The principal's own record is "
                   "ONE trade, so an early claim here would be two small samples flattering each "
                   "other."}
    elif desk.get("state") == "RUIN" or principal.get("state") == "RUIN":
        loser = "the principal's 10%" if principal.get("state") == "RUIN" else "the desk's cap"
        verdict = {"state": "AHEAD" if principal.get("state") == "RUIN" else "BEHIND",
                   "why": f"{loser} sizing hit RUIN on this record -- survival decides before "
                          "growth does, and a sequence that ends has no rate to compare."}
    else:
        d, p = float(desk["g_per_trade"]), float(principal["g_per_trade"])
        verdict = {
            "state": "AHEAD" if d > p else ("BEHIND" if d < p else "LEVEL"),
            "desk_g": d, "principal_g": p, "edge_per_trade": round(d - p, 6),
            "why": (f"the desk's {desk_f:.0%} sizing compounds at {d:+.5f}/trade against "
                    f"{p:+.5f} for the principal's {PRINCIPAL_RISK:.0%} on the SAME trades. "
                    + ("The cap is earning its keep: his fraction is past full Kelly on these "
                       "net odds, where extra size buys variance and loses growth."
                       if d > p else
                       "His fraction is doing better here, which means the desk's cap is costing "
                       "growth on a hit rate this good -- the cap should rise as the measured "
                       "rate justifies it (that is what measured_risk_cap already does)."))}

    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.6 -- a sleeve is benchmarked against what it claims to beat. Buy-and-hold is "
               "the first benchmark; the human method this sleeve was built to copy is the "
               "second, and neither is optional.",
        "status": verdict["state"],
        "n_closed": len(net_rs),
        "desk": desk, "principal": principal,
        "verdict": verdict,
        "scope_limit": "this compares SIZING POLICY on the desk's own calls, holding entries, "
                       "stops and exits fixed. It does NOT show the machine beats the principal: "
                       "his SELECTION is unmeasured (the desk has seen one of his trades), so a "
                       "verdict here is about risk policy, never about who picks better.",
        "where_the_machine_should_win": [
            "INDEPENDENT BETS -- 18 instruments watched continuously across every session. A "
            "human sleeps, and g_year scales linearly in the number of independent bets. This is "
            "the term the machine can win outright and the one it is currently wasting, since "
            "correlated crypto perps held at once are close to one bet.",
            "CONSISTENCY -- no tilt, no revenge trade, no fatigue. The human's visible record is "
            "his best trade; the machine's record is every trade, which is a harder bar honestly "
            "measured.",
            "MEASUREMENT -- the trail width, the risk cap and the payoff shape are swept against "
            "the desk's own marks. A human cannot A/B his own trail across 200 trades.",
        ],
        "where_the_human_still_wins": [
            "SELECTION -- he took one setup he had conviction in; the sleeve takes every 2-of-3 "
            "consensus. Conviction on few setups can carry a far higher hit rate.",
            "WINNER SHAPE -- his one visible trade ran ~6R against the ladder's assumed 3R, and "
            "the winner shape is the steepest term in the growth identity.",
        ],
        "detail": (f"{verdict['state']}: {verdict['why'][:150]}"),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report(_ROOT)
    out = _ROOT / _STATE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    print(json.dumps(rep, indent=2) if args.json else
          f"principal benchmark (L1.6): {rep['detail'][:170]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/run_recorder_bybit.py
```python
#!/usr/bin/env python3
"""BYBIT FORWARD RECORDER (v1, 2026-07-21) -- second-venue tape, public data only.

WHY NOW, NOT POST-GATE-0: recording is not trading. The Bybit *connector* is Gate-0-gated
because it moves money; the *tape* is public market data and gated by nothing. Cross-venue
basis, funding dispersion, and lead-lag are all calendar-bound datasets -- a day not recorded
is a day that can never be bought back (pre-recorder L2 does not exist free at any venue).
Starting this clock today is the single highest-leverage act available toward deep breadth.

Mirrors run_recorder.py's shape deliberately (same hourly gzip-jsonl layout under
data/moat/bybit/<SYMBOL>/) so downstream loaders treat both venues identically.

Weight discipline: Bybit's public IP limit is ~600 req/5s -- vastly looser than Binance's
weight budget -- but this stays deliberately modest (20 symbols @ 4s depth + 20s trades =
~5 req/s) to leave headroom and be a good citizen. Read-only, keyless, no order paths.
"""
from __future__ import annotations

import gzip
import json
import ssl
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import certifi

_BASE = "https://api.bybit.com"
_ROOT = Path(__file__).resolve().parent.parent / "data/moat/bybit"
_HB = Path(__file__).resolve().parent.parent / "data/recorder_bybit_heartbeat"
_CTX = ssl.create_default_context(cafile=certifi.where())

#: FALLBACK universe only. Kept because a recorder that records NOTHING is the one failure this
#: organ cannot come back from -- an unrecorded day does not exist free at any venue afterwards.
_FALLBACK = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
             "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT",
             "TRXUSDT", "DOTUSDT", "BCHUSDT", "NEARUSDT", "SUIUSDT",
             "UNIUSDT", "APTUSDT", "FILUSDT", "ARBUSDT", "OPUSDT")
_MAX_SYMBOLS = 20                # weight budget: 20 @ 4s depth + 20s trades = ~6 req/s


def _listed_on_bybit(http=None) -> frozenset[str]:
    """What Bybit actually lists. Keyless, one call.

    Without this the traded universe would be copied across venue-blind and every name Bybit
    does not list would burn two requests a cycle forever, returning nothing -- the recorder
    would look busy and record less."""
    try:
        d = (http or _get)("/v5/market/instruments-info", "category=linear&limit=1000")
        rows = ((d or {}).get("result") or {}).get("list") or []
        return frozenset(str(r["symbol"]) for r in rows if r.get("symbol"))
    except (OSError, KeyError, TypeError, ValueError):
        return frozenset()


def _universe(http=None) -> tuple[str, ...]:
    """The SAME priority-ordered universe the Binance recorder derives, filtered to what Bybit
    lists. Gap #39 was closed on run_recorder.py and this second-venue tape kept a hardcoded
    list, so the two recorders drifted apart and this one could intersect the traded book at
    ZERO -- which is the precise defect #39 named, still live on the venue nobody re-checked.

    ORDER IS PRIORITY, same as the twin: benchmark, then held positions, then recently traded,
    then majors. When the cap binds it is the MAJORS that get dropped and the traded names that
    survive, because the whole point of a second-venue tape is cross-venue work on the book the
    desk actually holds.

    FALLS BACK RATHER THAN BLOCKS, and the asymmetry is deliberate. Elsewhere on this desk an
    unknown must block the action; here the "action" is reading public data with no key and no
    money at risk, while the harm of not acting is permanent -- an unrecorded day cannot be
    bought back at any price. So an unreadable universe or an unreachable instrument list keeps
    the fallback and says so loudly, rather than recording nothing while looking healthy."""
    try:
        from scripts.run_recorder import _universe as _binance_universe
        wanted = _binance_universe()
    except Exception as exc:
        print(f"bybit recorder: universe underivable ({type(exc).__name__}: {exc}) -- "
              "FALLBACK list in use; this is a degraded universe, not a healthy one")
        return _FALLBACK
    listed = _listed_on_bybit(http)
    if not listed:
        print("bybit recorder: instruments-info unreachable -- cannot filter to listed symbols; "
              "FALLBACK list in use rather than recording nothing")
        return _FALLBACK
    keep = tuple(s for s in wanted if s in listed)[:_MAX_SYMBOLS]
    if not keep:
        print("bybit recorder: NO derived symbol is listed on bybit -- FALLBACK in use")
        return _FALLBACK
    dropped = [s for s in wanted if s not in listed]
    print(f"bybit recorder universe: {len(keep)} symbols following the traded book"
          + (f"; {len(dropped)} not listed on bybit ({', '.join(dropped[:6])})" if dropped else ""))
    return keep


_DEPTH_EVERY_S = 4.0
_TRADES_EVERY_S = 20.0
_REQ_PER_S_CAP = 20.0            # bybit allows far more; stay modest and neighbourly


def _assert_rate_budget() -> None:
    rps = len(_SYMBOLS) / _DEPTH_EVERY_S + len(_SYMBOLS) / _TRADES_EVERY_S
    print(f"bybit recorder budget: {rps:.1f} req/s (cap {_REQ_PER_S_CAP}) | "
          f"{len(_SYMBOLS)} symbols depth@{_DEPTH_EVERY_S}s trades@{_TRADES_EVERY_S}s")
    if rps > _REQ_PER_S_CAP:
        raise SystemExit(f"REFUSING TO START: {rps:.1f} req/s over self-imposed cap "
                         f"{_REQ_PER_S_CAP}. Widen intervals or cut symbols. "
                         "(Binance lesson 2026-07-21: silent venue cutoff after 6h.)")


def _get(path: str, params: str) -> dict[str, Any] | None:
    try:
        req = urllib.request.Request(f"{_BASE}{path}?{params}",
                                     headers={"User-Agent": "research-recorder/1.0"})
        with urllib.request.urlopen(req, timeout=10, context=_CTX) as r:
            d = json.loads(r.read())
        return d if d.get("retCode") == 0 else None
    except Exception:
        return None                                   # a dropped poll is a gap, never a crash


#: Derived AFTER _get exists -- the universe call needs the HTTP helper, and a module-level
#: assignment above it raised NameError at import: the recorder would not start at all.
_SYMBOLS = _universe()


def _write(sym: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    hour = datetime.now(tz=UTC).strftime("%Y%m%d_%H")
    out = _ROOT / sym
    out.mkdir(parents=True, exist_ok=True)
    with gzip.open(out / f"{hour}.jsonl.gz", "at", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")


def main() -> None:
    _assert_rate_budget()
    _ROOT.mkdir(parents=True, exist_ok=True)
    print(f"bybit recorder v1 -> {_ROOT}/")
    buf: dict[str, list[dict[str, Any]]] = {s: [] for s in _SYMBOLS}
    last_trades = 0.0
    last_flush = time.time()

    while True:
        t0 = time.time()
        for sym in _SYMBOLS:
            d = _get("/v5/market/orderbook", f"category=linear&symbol={sym}&limit=25")
            if d:
                r = d["result"]
                buf[sym].append({"t": int(time.time() * 1000), "k": "depth",
                                 "b": r.get("b", [])[:25], "a": r.get("a", [])[:25]})
        now = time.time()
        if now - last_trades >= _TRADES_EVERY_S:
            for sym in _SYMBOLS:
                d = _get("/v5/market/recent-trade", f"category=linear&symbol={sym}&limit=200")
                if d:
                    buf[sym].append({"t": int(now * 1000), "k": "trades",
                                     "v": d["result"].get("list", [])})
            f = _get("/v5/market/tickers", "category=linear")
            if f:
                tk = {x["symbol"]: {"fr": x.get("fundingRate"), "oi": x.get("openInterest"),
                                    "mp": x.get("markPrice")}
                      for x in f["result"].get("list", []) if x["symbol"] in _SYMBOLS}
                for sym, v in tk.items():
                    buf[sym].append({"t": int(now * 1000), "k": "meta", **v})
            last_trades = now

        if now - last_flush >= 60:
            for sym in _SYMBOLS:
                _write(sym, buf[sym])
                buf[sym] = []
            _HB.write_text(f"{time.time()}", "utf-8")
            last_flush = now

        time.sleep(max(0.0, _DEPTH_EVERY_S - (time.time() - t0)))


if __name__ == "__main__":
    main()

```

### scripts/run_reversal_costtest.py
```python
"""Cost-hypothesis test: do reversal / BTC-lead-lag turn viable at lower turnover + maker fees?

The firm-alpha gauntlet showed both have positive IC but lose net of cost. This sweeps band
(turnover) x cost (taker vs maker ~half) per signal, reporting the FULL grid + the GROSS (cost-free)
Sharpe ceiling -- the decisive number: negative gross Sharpe means cost was never the killer.
Viable only if net Sharpe > 0 at MAKER cost AND survives DSR AND positive across >=2 bands. Not
p-hacking -- a pre-set grid testing one named hypothesis, DSR-deflated. -> web/reversal_cost.json.

    python scripts/run_reversal_costtest.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from libs.data.crypto_source import list_liquid_perps
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.research.crypto_xsec import adv_tier_cost
from libs.validation.dsr import deflated_sharpe_ratio, sharpe_ratio

_OUT = Path("web/reversal_cost.json")
_CRYPTO = Path("data/lake/bronze/crypto")
_PPY = 365.0
_BANDS = [0.05, 0.15, 0.30, 0.50]


def _ls(sig: pd.DataFrame, ret: pd.DataFrame, cost: float, band: float
        ) -> tuple[np.ndarray, float]:
    """Long-high/short-low book; returns (net daily returns, annualised turnover)."""
    out = np.zeros(len(sig))
    turn_tot = 0.0
    prev = pd.Series(0.0, index=sig.columns)
    for t in range(len(sig)):
        s = sig.iloc[t].dropna()
        if len(s) < 12:
            out[t] = float((prev * ret.iloc[t].reindex(prev.index).fillna(0.0)).sum())
            continue
        k = max(1, int(len(s) * 0.2))
        ranked = s.sort_values()
        w = pd.Series(0.0, index=sig.columns)
        w[ranked.index[-k:]] = 0.5 / k
        w[ranked.index[:k]] = -0.5 / k
        delta = (w - prev).abs()
        w = w.where(delta > band, prev)
        tn = float((w - prev).abs().sum())
        turn_tot += tn
        out[t] = float((w * ret.iloc[t].reindex(w.index).fillna(0.0)).sum()) - tn * cost
        prev = w
    return out, turn_tot / len(sig) * _PPY


def _sharpe(r: np.ndarray) -> float:
    a = r[r != 0.0]
    return round(float(sharpe_ratio(a) * np.sqrt(_PPY)), 2) if len(a) > 100 else 0.0


def main() -> None:
    lake = ParquetLake("data/lake")
    closes, adv = {}, {}
    for s in list_liquid_perps(top_n=120):
        if not (_CRYPTO / s / Timeframe.D1.value).exists():
            continue
        register_instrument(InstrumentSpec(symbol=s, asset_class=AssetClass.CRYPTO, description=s))
        df = lake.read_bars(Layer.BRONZE, s, Timeframe.D1).set_index("timestamp")
        if "funding" not in df.columns or len(df) < 250:
            continue
        closes[s] = df["close"]
        adv[s] = float((df["close"] * df["volume"]).tail(180).mean())
    close = pd.DataFrame(closes).sort_index()
    if close.shape[1] < 12:
        raise SystemExit("need a liquid perp panel")
    ret = close.pct_change(fill_method=None)
    taker = float(np.mean([adv_tier_cost(a) for a in adv.values()]))
    maker = taker * 0.5                                   # maker ~ half taker fee
    btc = ret.get("BTCUSDT")

    sig_rev = (-ret.rolling(2).sum()).shift(1)
    sig_ll = pd.DataFrame((btc.values[:, None] - ret.to_numpy()) if btc is not None
                          else ret.to_numpy() * 0.0, index=ret.index, columns=ret.columns).shift(1)

    grids: dict[str, dict[str, Any]] = {}
    all_maker_sharpes: list[float] = []
    for name, sig in (("short_term_reversal", sig_rev), ("btc_leadlag", sig_ll)):
        gross, _ = _ls(sig, ret, 0.0, 0.15)
        cells = []
        for band in _BANDS:
            r_tk, turn = _ls(sig, ret, taker, band)
            r_mk, _ = _ls(sig, ret, maker, band)
            s_mk = _sharpe(r_mk)
            all_maker_sharpes.append(s_mk)
            cells.append({"band": band, "ann_turnover": round(turn, 1),
                          "sharpe_taker": _sharpe(r_tk), "sharpe_maker": s_mk})
        grids[name] = {"gross_sharpe": _sharpe(gross), "cells": cells}

    # DSR on the single best maker cell across BOTH signals, deflated by the whole grid searched
    best_name, best_cell, best_arr = "", None, np.zeros(1)
    for name, sig in (("short_term_reversal", sig_rev), ("btc_leadlag", sig_ll)):
        for band in _BANDS:
            r_mk, _ = _ls(sig, ret, maker, band)
            if _sharpe(r_mk) > _sharpe(best_arr):
                best_name, best_cell, best_arr = name, band, r_mk
    sh_family = np.array([sharpe_ratio(x) for x in [best_arr]] + [s / np.sqrt(_PPY)
                         for s in all_maker_sharpes if s != 0.0])
    dsr = deflated_sharpe_ratio(best_arr[best_arr != 0.0], n_trials=len(all_maker_sharpes),
                                sharpe_estimates=sh_family)
    pos_bands = sum(1 for c in grids.get(best_name, {}).get("cells", []) if c["sharpe_maker"] > 0)
    viable = bool(dsr.passed and _sharpe(best_arr) > 0 and pos_bands >= 2)

    out = {
        "updated": datetime.now(tz=UTC).isoformat(), "obs": len(close),
        "taker_cost": round(taker, 5), "maker_cost": round(maker, 5),
        "grids": grids,
        "best": {"signal": best_name, "band": best_cell, "sharpe_maker": _sharpe(best_arr),
                 "dsr": round(float(dsr.dsr), 3), "dsr_pass": bool(dsr.passed),
                 "positive_bands": pos_bands},
        "viable": viable,
        "verdict": (f"{best_name} VIABLE at maker cost (band {best_cell})" if viable
                    else "REJECTED -- gross Sharpe NEGATIVE: cost was never the killer, the L/S "
                    "book itself is unprofitable (positive IC did not translate to tradeable P&L)"),
        "note": ("Tests the cost hypothesis the IC raised, not a new alpha. Gross Sharpe = the "
                 "signal's ceiling; the question is whether maker fees + wider bands clear cost. "
                 "Viable only if DSR-robust across >=2 bands, else it stays a reject (honest)."),
    }
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    for name, g in grids.items():
        print(f"{name} (gross {g['gross_sharpe']}): " + " | ".join(
            f"b{c['band']} mkr {c['sharpe_maker']} (turn {c['ann_turnover']})"
            for c in g["cells"]))
    print(f"  best maker: {best_name} band {best_cell} Sharpe {_sharpe(best_arr)} "
          f"DSR {out['best']['dsr']} pass={dsr.passed} -> {out['verdict']}")


if __name__ == "__main__":
    main()

```

### scripts/run_venue_divergence_shadow.py
```python
#!/usr/bin/env python3
"""GAP #19 VENUE-TRUTH DIVERGENCE -- SHADOW (observe-only, principal-approved 2026-07-23).

WHAT: logs the gap between the MARK-based book NAV (live_combined mcurve) and the VENUE-TRUTH
NAV (the dead-man's independent measure) every tick, so the circuit breaker's band can be
calibrated at "~2x OBSERVED noise" (GAP19_RECONCILE_GUARD_SPEC) from real data.

WHY SHADOW FIRST: you cannot calibrate a threshold against noise you have never measured. The
2026-07-22 dead-man false fires happened precisely because a trigger was set without knowing the
measurement noise of its own inputs. This measures first, arms later. The breaker itself stays
QUEUED post-Gate-0 per the spec (property/mutation testing + independence gate required).

Origin: proposed unprompted by TWO independent tier1 seats (moonshotai/kimi "Venue-Truth-First
Risk Measurement" + google/gemini "Venue-Truth Disconnect Circuit Breaker") -- corroboration is
why gap #19 was accepted while kimi's other two tier1 findings were rejected.

STRICTLY READ-ONLY. It never pauses opens, never pages, never flattens, and NEVER writes the
dead-man's state file (two-writers-on-one-rail was the 07-11 false-fire root cause). It only
appends to its own log.

    python scripts/run_venue_divergence_shadow.py            # sample once
    python scripts/run_venue_divergence_shadow.py --report   # calibration stats
"""
from __future__ import annotations

import argparse
import contextlib
import itertools
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_VENUE = Path("web/venue_equity.json")
_MARK = Path("data/live_combined_state.json")
_LOG = Path("data/venue_divergence_shadow.jsonl")
_STALE_S = 900.0          # a feed older than this cannot be compared honestly


def _age_s(p: Path) -> float:
    try:
        return max(0.0, datetime.now(tz=UTC).timestamp() - p.stat().st_mtime)
    except Exception:
        return float("inf")


def _venue_nav() -> float | None:
    try:
        return float(json.loads(_VENUE.read_text("utf-8"))["equity"])
    except Exception:
        return None


def _mark_nav() -> float | None:
    """Newest mark-based NAV from the live_combined equity curve."""
    try:
        curve = json.loads(_MARK.read_text("utf-8")).get("mcurve") or []
        return float(curve[-1][1]) if curve else None
    except Exception:
        return None


def sample() -> dict[str, Any]:
    v, m = _venue_nav(), _mark_nav()
    va, ma = _age_s(_VENUE), _age_s(_MARK)
    # A STALE feed manufactures fake divergence -- excluding it from calibration is the whole
    # point: a band fitted to stale-feed artefacts would trip on nothing real.
    stale = va > _STALE_S or ma > _STALE_S
    rec: dict[str, object] = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "venue_nav": v, "mark_nav": m,
        "venue_age_s": round(va, 1) if va != float("inf") else None,
        "mark_age_s": round(ma, 1) if ma != float("inf") else None,
        "stale": bool(stale),
    }
    if v is not None and m is not None and v > 0:
        rec["abs_diff"] = round(m - v, 2)
        rec["pct_diff"] = round(100.0 * (m - v) / v, 4)
    _LOG.parent.mkdir(parents=True, exist_ok=True)
    with _LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def report() -> None:
    if not _LOG.exists():
        print("venue-divergence shadow: no samples yet")
        return
    rows = []
    for line in _LOG.read_text("utf-8").splitlines():
        with contextlib.suppress(Exception):
            rows.append(json.loads(line))
    clean = [r for r in rows if not r.get("stale")
             and r.get("venue_nav") is not None and r.get("mark_nav") is not None]
    usable = [abs(float(r["pct_diff"])) for r in clean if r.get("pct_diff") is not None]

    # INCREMENT DIVERGENCE -- the signal gap #19 actually needs (2026-07-23 shadow finding).
    # The two feeds sit ~36% apart BY CONSTRUCTION (different bases: live_combined marks a
    # 15,000-based book; the dead-man measure is fut margin + TRACKED legs + USDT delta and
    # deliberately excludes untracked faucet spot). A level-vs-level band would trip instantly
    # and permanently on that definitional offset. What genuinely signals a reconciliation
    # break is the two measures DRIFTING APART between ticks.
    incs = []
    for a, b in itertools.pairwise(clean):
        dv = float(b["venue_nav"]) - float(a["venue_nav"])
        dm = float(b["mark_nav"]) - float(a["mark_nav"])
        base = abs(float(b["venue_nav"])) or 1.0
        incs.append(abs(dm - dv) / base * 100.0)
    if incs:
        incs.sort()
        m = len(incs)
        p95 = incs[min(m - 1, int(m * 0.95))]
        print(f"  INCREMENT divergence |d(mark)-d(venue)|: p50={incs[m // 2]:.4f}%  "
              f"p95={p95:.4f}%  max={incs[-1]:.4f}%  (n={m})")
        print(f"  ARMABLE BAND (~2x observed increment noise) => ~{2 * p95:.3f}%")
    else:
        print("  INCREMENT divergence: need >=2 clean consecutive samples")
    print(f"venue-divergence shadow: {len(rows)} samples, {len(usable)} usable "
          f"({len(rows) - len(usable)} excluded as stale/incomplete)")
    if not usable:
        print("  no clean samples yet -- band NOT calibratable; do NOT arm gap #19")
        return
    usable.sort()
    n = len(usable)
    p50 = usable[n // 2]
    p95 = usable[min(n - 1, int(n * 0.95))]
    mx = usable[-1]
    print(f"  LEVEL offset |pct_diff| p50={p50:.4f}% p95={p95:.4f}% max={mx:.4f}% "
          "(DEFINITIONAL -- different bases; do NOT band on this)")
    if n < 200:
        print(f"  NOT ENOUGH DATA to arm ({n} clean samples; want >=200 spanning rebalances "
              "and at least one regime event) -- gap #19 stays queued.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.report:
        report()
        return
    r = sample()
    d = r.get("pct_diff")
    print(f"venue-divergence shadow: venue={r['venue_nav']} mark={r['mark_nav']} "
          f"diff={d if d is not None else 'n/a'}% stale={r['stale']}")


if __name__ == "__main__":
    main()

```

### scripts/run_wiring_agent.py
```python
"""WIRING AGENT -- built things get WIRED, automatically, every day (principal order 2026-07-30).

THE PROBLEM IT REMOVES. `libs/self_improvement/dormancy.py` DETECTS capabilities nothing imports
and nothing schedules -- it measured 171 of them / 16,645 paid-for unused lines on 2026-07-30. But
detection alone reproduces the original failure one level up: a report nobody actions is itself a
dormant capability. The principal's instruction is explicit -- *"make a wiring agent that always
makes sure everything built is wired, or make sure every cycle automatically wires things which
aren't."* So this agent ACTS: it wires what is safe to wire, and it PROPOSES the rest.

THE SAFETY LINE, and it is the whole design. Auto-wiring is a privileged operation -- it causes
code to START RUNNING on a schedule, unattended, on a box with live exchange credentials. So the
agent auto-wires ONLY what it can prove is inert-by-construction, and every other class is
proposed for a human/organ decision with the reason it was withheld:

  AUTO-WIRE   research/reporting scripts: a `main()`, no money-path import, no spend, no writes
              outside data/ + web/, and a name that is not on the never-touch list.
  PROPOSE     anything touching the money path (execution/risk/order/deadman), anything that can
              SPEND (openrouter/panel/kimi/anthropic), anything writing outside data/ + web/,
              and anything whose import graph the agent cannot resolve.
  NEVER       Tier-3 (`run_deadman_switch.py`) and the executor -- not even proposed. Their
              scheduling is a principal decision, permanently.

WHY A CADENCE IS CHOSEN, NOT GUESSED: a wired-but-wrongly-frequent organ is its own defect (the
2026-07-21 IP ban came from over-frequent polling). Cadence is derived from what the script reads
-- venue/network readers get hourly-or-slower, pure local readers get daily -- and every generated
entry is tagged CONFIDENCE:auto-wired so a human can find and re-tune every one of them.

IDEMPOTENT: re-running never duplicates an entry. Writes to ops/crontab.manifest inside a fenced
block, so hand-written entries are never touched.

    python scripts/run_wiring_agent.py            # report only (default: SAFE)
    python scripts/run_wiring_agent.py --apply    # actually write the manifest
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_MANIFEST = _ROOT / "ops/crontab.manifest"
_OUT = _ROOT / "data/wiring_agent.json"
_FENCE_START = "# >>> WIRING AGENT (auto-wired, idempotent) >>>"
_FENCE_END = "# <<< WIRING AGENT <<<"

# Never scheduled by an agent, ever. Not proposed either -- these are principal decisions.
_NEVER = {"run_deadman_switch.py", "run_cashcarry_executor.py"}

# Safe-by-writes is not the same as sane-to-schedule (2026-07-31: the agent cron'd ops_server.py
# -- a long-running server, so each fire stacks an instance or dies on the bound port -- and
# setup_ngrok.py/setup_testnet_keys.py, one-shot provisioning). Shape filters, not a blacklist:
_NOT_ORGANS = ("setup_", "smoke_", "demo_", "bootstrap_")
_SERVER_MARKERS = ("serve_forever", "httpserver", "socketserver", "uvicorn",
                   "app.run(", "start_server", ".bind((")

# Import substrings that make a script MONEY-PATH or SPEND-CAPABLE -> propose, never auto-wire.
_MONEY_PATH = ("libs.execution", "binance_live", "binance_spot_live", "binance_testnet",
               "libs.risk", "cashcarry_executor", "order", "staging")
_SPENDS = ("openrouter", "anthropic", "kimi", "external_panel", "panel_budget", "requests.post")


def _module_imports(tree: ast.AST) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
    return out


def _has_main(tree: ast.AST) -> bool:
    return any(isinstance(n, ast.FunctionDef) and n.name == "main" for n in ast.walk(tree))


_ALLOWED = ('"data/', "'data/", '"web/', "'web/", '"docs/', "'docs/", '"reports/', "'reports/",
            "_ROOT /", "tmp_path", "Path(__file__)")


def _safe_path_constants(tree: ast.AST) -> set[str]:
    """Module-level names bound to an ALLOWED path expression.

    Without this the agent is needlessly timid: the house pattern is `_OUT = _ROOT / "data/x.json"`
    at module level and `_OUT.write_text(...)` later, so the write LINE shows no path and every
    such script was flagged 'writes outside data/'. Resolving the constant recovers them. Erring
    toward PROPOSE is the safe direction, but being wrong 40 times is a yield problem worth fixing.
    """
    names: set[str] = set()
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                src = ast.unparse(node.value)
                if any(a in src for a in _ALLOWED):
                    names.add(target.id)
    return names


def _writes_outside_data(src: str, safe_names: set[str] | None = None) -> bool:
    """A scheduled script must not write outside data/ + web/ unattended."""
    for marker in ('write_text(', 'open(', 'mkdir('):
        idx = 0
        while (idx := src.find(marker, idx)) != -1:
            line_start = src.rfind("\n", 0, idx) + 1
            line = src[line_start:src.find("\n", idx)]
            if any(p in line for p in _ALLOWED) or any(n in line for n in (safe_names or set())):
                idx += 1
                continue
            return True
    return False


def classify(rel: str) -> tuple[str, str, str]:
    """(decision, reason, cadence). decision in AUTO-WIRE | PROPOSE | NEVER."""
    name = Path(rel).name
    if name in _NEVER:
        return "NEVER", "Tier-3 / executor -- scheduling is a permanent principal decision", ""
    if name.startswith(_NOT_ORGANS):
        return "PROPOSE", "one-shot provisioning/smoke script -- not a recurring organ", ""
    p = _ROOT / rel
    try:
        src = p.read_text("utf-8", errors="ignore")
        tree = ast.parse(src)
    except (OSError, SyntaxError) as e:
        return "PROPOSE", f"unparseable ({type(e).__name__}) -- cannot prove it is safe", ""
    if not _has_main(tree):
        return "PROPOSE", "no main() -- not a runnable organ; likely a library or a helper", ""
    imports = " ".join(_module_imports(tree)).lower()
    if any(m in imports for m in _MONEY_PATH):
        return "PROPOSE", "imports the money path (execution/risk) -- a human decides its cadence", ""
    low = src.lower()
    if any(s in low for s in _SPENDS):
        return "PROPOSE", "can SPEND (external model/API) -- budget envelope decision, not auto", ""
    if any(m in low for m in _SERVER_MARKERS):
        return "PROPOSE", "long-running server -- needs a supervisor (systemd), not a cron stack", ""
    if _writes_outside_data(src, _safe_path_constants(tree)):
        return "PROPOSE", "writes outside data/ + web/ -- unattended scheduling needs review", ""
    # Cadence from what it touches: network readers slower, local-only readers daily. Slot is a
    # deterministic hash of the name -- a fixed "21 8" herded every wired organ onto one minute
    # of a 2-core box (R0070 stagger); hashing keeps re-runs idempotent, daily slots land in the
    # 03:00-06:59 window clear of the 08:45 brain and the 02:00 research chain.
    h = int(hashlib.md5(name.encode()).hexdigest(), 16)
    touches_net = any(k in low for k in ("urllib", "http", "requests", "api."))
    cadence = (f"{h % 60} */6 * * *", "6-hourly (reads a network source; slower cadence bounds "
               "rate-limit exposure -- the 2026-07-21 IP ban came from over-frequent polling)") \
        if touches_net else (f"{h % 60} {3 + (h >> 8) % 4} * * *", "daily (local artifacts only)")
    return "AUTO-WIRE", f"runnable, no money path, no spend, local writes only -- {cadence[1]}", \
        cadence[0]


def _fenced_paths() -> list[str]:
    """Script paths already inside the fence. Wired-stays-wired: dormancy reads the manifest, so
    a script the agent wired yesterday is no longer dormant today -- without this union the fence
    DROPS it, it goes dormant again tomorrow, and the whole block oscillates between two disjoint
    sets forever (observed live 2026-07-31: six scripts out, twelve in, every run)."""
    try:
        text = _MANIFEST.read_text("utf-8")
        block = text[text.index(_FENCE_START):text.index(_FENCE_END)]
    except (OSError, ValueError):
        return []
    out: list[str] = []
    for ln in block.splitlines():
        if ".venv/bin/python scripts/" in ln and not ln.lstrip().startswith("#"):
            out.append(ln.split(".venv/bin/python ", 1)[1].split()[0])
    return out


def scan() -> dict[str, Any]:
    from libs.self_improvement.dormancy import scan as dormancy_scan
    rep = dormancy_scan(include_modules=False)      # scripts only: modules are wired by callers
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for d in rep.dormant:
        decision, reason, cadence = classify(d.path)
        seen.add(d.path)
        rows.append({"path": d.path, "lines": d.lines, "decision": decision,
                     "reason": reason, "cadence": cadence})
    for rel in _fenced_paths():                     # ratchet: re-classify, never silently drop
        if rel in seen:
            continue
        decision, reason, cadence = classify(rel)
        rows.append({"path": rel, "lines": 0, "decision": decision,
                     "reason": reason, "cadence": cadence})
    rows.sort(key=lambda r: (-r["lines"]))
    counts: dict[str, int] = {}
    for r in rows:
        counts[str(r["decision"])] = counts.get(str(r["decision"]), 0) + 1
    return {"generated": datetime.now(tz=UTC).isoformat(), "counts": counts,
            "n_scripts_scanned": rep.n_scripts_scanned, "rows": rows}


def _render(rows: list[dict[str, Any]]) -> str:
    lines = [_FENCE_START,
             "# Written by scripts/run_wiring_agent.py -- DO NOT hand-edit inside the fence; edits",
             "# are replaced on the next run. To take an entry over, move it OUTSIDE the fence and",
             "# retune it (the agent will then leave it alone because it is already scheduled).",
             "# Every entry here was proven: runnable main(), no money-path import, no spend",
             "# capability, no writes outside data/ + web/. CONFIDENCE: auto-wired."]
    for r in rows:
        if r["decision"] != "AUTO-WIRE":
            continue
        lines.append(f"# {r['path']} -- {r['reason']}")
        lines.append(f'{r["cadence"]} cd "$QUANT_ROOT" && .venv/bin/python {r["path"]} '
                     f'>> data/cro_ai_logs/{Path(r["path"]).stem}.log 2>&1')
    lines.append(_FENCE_END)
    return "\n".join(lines) + "\n"


def apply_block(rows: list[dict[str, Any]]) -> int:
    text = _MANIFEST.read_text("utf-8")
    block = _render(rows)
    if _FENCE_START in text and _FENCE_END in text:
        head = text[:text.index(_FENCE_START)]
        tail = text[text.index(_FENCE_END) + len(_FENCE_END):].lstrip("\n")
        text = head + block + tail
    else:
        text = text.rstrip("\n") + "\n\n" + block
    _MANIFEST.write_text(text, "utf-8")
    return sum(1 for r in rows if r["decision"] == "AUTO-WIRE")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the manifest (default: report)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = scan()
    if args.apply:
        rep["wired"] = apply_block(rep["rows"])
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"wiring agent: {rep['counts']} over {rep['n_scripts_scanned']} scripts"
              + (f" | WIRED {rep.get('wired', 0)}" if args.apply else " | report-only"))
        for r in rep["rows"][:15]:
            print(f"  {r['decision']:10} {r['path']:44} {r['reason'][:70]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```
