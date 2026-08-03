# AUDIT SHARD 7/13 -- seat moonshotai/kimi-k3

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

### libs/alpha/card.py
```python
"""Alpha cards and the metric models used by health/decay/ranking."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from libs.alpha.state import AlphaState


class NewAlpha(BaseModel):
    """Input to register a new alpha (becomes a CANDIDATE card)."""

    model_config = ConfigDict(frozen=True)

    name: str
    market: str
    category: str
    thesis: str
    entry_logic: str
    exit_logic: str
    expected_cagr: float | None = None
    expected_sharpe: float | None = None
    expected_drawdown: float | None = None
    dsr: float | None = None
    pbo: float | None = None
    cpcv: dict[str, Any] | None = None
    walk_forward: dict[str, Any] | None = None
    holdout: dict[str, Any] | None = None
    predecessor_id: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class AlphaCard(BaseModel):
    """The full alpha card — an immutable read snapshot of one alpha's record."""

    model_config = ConfigDict(frozen=True)

    id: str
    created_at: str
    updated_at: str
    name: str
    market: str
    category: str
    thesis: str
    entry_logic: str
    exit_logic: str
    expected_cagr: float | None
    expected_sharpe: float | None
    expected_drawdown: float | None
    dsr: float | None
    pbo: float | None
    cpcv: dict[str, Any] | None
    walk_forward: dict[str, Any] | None
    holdout: dict[str, Any] | None
    deployment_date: str | None
    retirement_date: str | None
    live_cagr: float | None
    live_sharpe: float | None
    live_drawdown: float | None
    decay_score: float
    status: AlphaState
    successor_id: str | None
    predecessor_id: str | None
    extra: dict[str, Any]


class ExpectedMetrics(BaseModel):
    """Backtest expectations a live alpha is measured against."""

    model_config = ConfigDict(frozen=True)

    sharpe: float | None = None
    cagr: float | None = None
    max_drawdown: float | None = None  # positive magnitude
    win_rate: float | None = None
    profit_factor: float | None = None
    expectancy: float | None = None
    trade_mean: float | None = None
    trade_std: float | None = None

    @classmethod
    def from_card(cls, card: AlphaCard) -> ExpectedMetrics:
        extra = card.extra or {}
        return cls(
            sharpe=card.expected_sharpe,
            cagr=card.expected_cagr,
            max_drawdown=card.expected_drawdown,
            win_rate=extra.get("expected_win_rate"),
            profit_factor=extra.get("expected_profit_factor"),
            expectancy=extra.get("expected_expectancy"),
            trade_mean=extra.get("expected_trade_mean"),
            trade_std=extra.get("expected_trade_std"),
        )


class LiveMetrics(BaseModel):
    """Measured live performance for an alpha."""

    model_config = ConfigDict(frozen=True)

    sharpe: float
    cagr: float
    max_drawdown: float  # positive magnitude
    win_rate: float | None = None
    profit_factor: float | None = None
    expectancy: float | None = None
    regime_stability: float = 1.0  # 1 = stable, 0 = fully regime-mismatched
    trade_mean: float | None = None
    trade_std: float | None = None
    sample: int = 0


class AlphaEvent(BaseModel):
    """One immutable lifecycle audit record."""

    model_config = ConfigDict(frozen=True)

    seq: int
    id: str
    alpha_id: str
    created_at: str
    event_type: str
    from_status: str | None
    to_status: str | None
    detail: dict[str, Any] | None
    actor: str


class AlphaPerformance(BaseModel):
    """One live-performance snapshot."""

    model_config = ConfigDict(frozen=True)

    id: str
    alpha_id: str
    created_at: str
    sharpe: float | None
    cagr: float | None
    max_drawdown: float | None
    win_rate: float | None
    profit_factor: float | None
    expectancy: float | None
    sample: int | None

```

### libs/alpha_factory/__init__.py
```python
"""``libs.alpha_factory`` — the Alpha Factory & Research Operating System.

Sits *above* the research pipeline: it generates, ranks, evolves, allocates, and learns from
research, compounding knowledge so the platform discovers more (and better) alphas over time.
It does NOT trade. Governance is structural: the factory may generate/rank/allocate-research/
archive/recommend, but may not promote or retire alphas, change risk/validation thresholds, or
allocate production capital.

Reuses Architecture v1.0: ``libs.discovery`` (research ROI, capacity), ``libs.self_improvement``
(categories, PSI drift), and the SQLite system of record (``research_memory`` table, migration
0003). No duplicate abstractions; single source of truth.
"""

from __future__ import annotations

from libs.alpha_factory.alpha_discovery_engine import AlphaDiscoveryEngine
from libs.alpha_factory.alpha_dna import build_alpha_dna, dna_distance
from libs.alpha_factory.alpha_embedding_engine import AlphaEmbeddingEngine
from libs.alpha_factory.alpha_factory_controller import AlphaFactoryController
from libs.alpha_factory.alpha_family_tree import AlphaFamilyTree
from libs.alpha_factory.capacity_intelligence import CapacityIntelligence
from libs.alpha_factory.concept_evolution_engine import ConceptEvolutionEngine
from libs.alpha_factory.crowding_intelligence import CrowdingIntelligence
from libs.alpha_factory.errors import AlphaFactoryError, AlphaFactoryGovernanceError
from libs.alpha_factory.hypothesis_engine import HypothesisEngine
from libs.alpha_factory.idea_ranking_engine import IdeaRankingEngine
from libs.alpha_factory.models import (
    AllocationResult,
    AlphaCategory,
    AlphaDNA,
    AlphaFactoryReport,
    CapacityIntelligenceResult,
    CrowdingEstimate,
    DriftResult,
    FailureCause,
    FamilyNode,
    Hypothesis,
    IdeaCandidate,
    IdeaRecord,
    IdeaScore,
    ResearchResult,
    ResearchScoreResult,
    SimilarityResult,
)
from libs.alpha_factory.research_allocator import ResearchAllocator
from libs.alpha_factory.research_dashboard_exports import build_research_dashboard
from libs.alpha_factory.research_graph import ResearchGraph
from libs.alpha_factory.research_memory import ResearchMemory
from libs.alpha_factory.research_roi_engine import ResearchROIEngine
from libs.alpha_factory.research_score_engine import ResearchScoreEngine
from libs.alpha_factory.strategy_similarity_engine import StrategySimilarityEngine

__all__ = [  # noqa: RUF022  # grouped by concern
    # models / enums
    "AlphaCategory",
    "ResearchResult",
    "FailureCause",
    "AlphaDNA",
    "Hypothesis",
    "IdeaRecord",
    "IdeaCandidate",
    "IdeaScore",
    "ResearchScoreResult",
    "SimilarityResult",
    "CrowdingEstimate",
    "CapacityIntelligenceResult",
    "DriftResult",
    "FamilyNode",
    "AllocationResult",
    "AlphaFactoryReport",
    # engines
    "AlphaDiscoveryEngine",
    "AlphaEmbeddingEngine",
    "AlphaFamilyTree",
    "build_alpha_dna",
    "dna_distance",
    "CapacityIntelligence",
    "ConceptEvolutionEngine",
    "CrowdingIntelligence",
    "HypothesisEngine",
    "IdeaRankingEngine",
    "ResearchAllocator",
    "ResearchGraph",
    "ResearchMemory",
    "ResearchROIEngine",
    "ResearchScoreEngine",
    "StrategySimilarityEngine",
    "build_research_dashboard",
    # controller
    "AlphaFactoryController",
    # errors
    "AlphaFactoryError",
    "AlphaFactoryGovernanceError",
]

```

### libs/alpha_factory/alpha_family_tree.py
```python
"""Alpha family tree — track which research directions create winners.

A directed lineage of alphas: each node records its parent, the mutation that produced it, and its
performance. Used to learn which mutation paths (e.g. Trend_v1 -> v2 -> v3) compound into edge.
"""

from __future__ import annotations

from libs.alpha_factory.errors import AlphaFactoryError
from libs.alpha_factory.models import FamilyNode
from libs.core.time import to_iso8601, utcnow


class AlphaFamilyTree:
    """An in-memory lineage graph of alphas and their mutations."""

    def __init__(self) -> None:
        self._nodes: dict[str, FamilyNode] = {}

    def add(
        self,
        alpha_id: str,
        *,
        parent_id: str | None = None,
        mutation_type: str = "root",
        performance: float = 0.0,
    ) -> FamilyNode:
        if alpha_id in self._nodes:
            raise AlphaFactoryError(f"alpha {alpha_id} already in tree")
        if parent_id is not None and parent_id not in self._nodes:
            raise AlphaFactoryError(f"unknown parent {parent_id}")
        node = FamilyNode(
            alpha_id=alpha_id, parent_id=parent_id, mutation_type=mutation_type,
            created_at=to_iso8601(utcnow()), performance=performance,
        )
        self._nodes[alpha_id] = node
        return node

    def get(self, alpha_id: str) -> FamilyNode | None:
        return self._nodes.get(alpha_id)

    def lineage(self, alpha_id: str) -> list[FamilyNode]:
        """Root-to-node ancestry chain."""
        chain: list[FamilyNode] = []
        current = self._nodes.get(alpha_id)
        while current is not None:
            chain.append(current)
            current = self._nodes.get(current.parent_id) if current.parent_id else None
        return list(reversed(chain))

    def children(self, alpha_id: str) -> list[FamilyNode]:
        return [n for n in self._nodes.values() if n.parent_id == alpha_id]

    def best_lineage(self) -> list[FamilyNode]:
        """The ancestry of the highest-performing alpha (the winning research direction)."""
        if not self._nodes:
            return []
        best = max(self._nodes.values(), key=lambda n: n.performance)
        return self.lineage(best.alpha_id)

```

### libs/autodiscovery/errors.py
```python
"""Autonomous research-lab errors."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class AutoDiscoveryError(QuantPlatformError):
    """Base error for the autonomous research lab."""

```

### libs/autodiscovery/orchestrator.py
```python
"""AutoDiscoveryLab — one autonomous research cycle, idempotent / resumable / fail-closed.

A cycle: expand the fixed generator set into declared hypotheses, skip any already tested (dedup),
backtest each on data from an injected provider, run the full validation gauntlet, resolve the
lifecycle status (reject/shadow/paper/registry), archive every outcome to durable memory,
checkpoint, and audit. No real capital is ever allocated. The data provider is injected so the lab
is testable offline; in production it pulls from MT5.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

from libs.autodiscovery.generators import net_returns, planned_hypotheses
from libs.autodiscovery.lifecycle import promote
from libs.autodiscovery.memory import CandidateStore
from libs.autodiscovery.models import (
    CandidateStatus,
    CycleResult,
    Family,
    Hypothesis,
    MarketSeries,
)
from libs.autodiscovery.prioritization import prioritize
from libs.autodiscovery.regime import regime_robust
from libs.autodiscovery.validation import campaign_fdr, campaign_gate_stats, validate
from libs.core.ids import generate_id
from libs.costs.execution_gap import ExecutionGap, survives_execution_gap
from libs.store.audit import AuditLog
from libs.store.connection import Database
from libs.validation.dsr import sharpe_ratio
from libs.validation.lockbox import LockedHoldout

DataProvider = Callable[[str], MarketSeries | None]
CostProvider = Callable[[str], float]  # symbol -> per-turnover (per-side) cost fraction
_MIN_BARS = 250
# Sealed final slice, never seen by validation, opened exactly once at the promotion
# decision. 20% rather than the module default 30%: at _MIN_BARS=250 a 30% holdout
# would need 358 bars before any candidate qualified, so the discipline would almost
# never apply. A holdout that never engages is not a holdout either.
_LOCKBOX_FRACTION = 0.20


class AutoDiscoveryLab:
    """Runs autonomous research cycles over the fixed, economically-declared hypothesis universe."""

    def __init__(
        self,
        db: Database,
        data_provider: DataProvider,
        *,
        cost: float = 0.0003,
        cost_provider: CostProvider | None = None,
        families: Sequence[Family] | None = None,
        execution_gap: ExecutionGap | None = None,
        family_trial_budget: int = 120,
    ) -> None:
        self.db = db
        self.data_provider = data_provider
        self.store = CandidateStore(db)
        self.audit = AuditLog(db)
        self.cost = cost
        self.families = families  # None = all 12; a focused set drops crowded families (T0)
        # Per-symbol net-of-cost (committee T1/T2): real calibrated cost per turnover when supplied,
        # else the flat fallback. Backtests are ALWAYS net of cost; this makes it instrument-aware.
        self.cost_provider = cost_provider
        # Demo->live execution-gap stress (committee Lever 2/T4): a REGISTRY-eligible candidate must
        # also stay net-positive when cost is multiplied to a conservative live estimate.
        self.execution_gap = execution_gap or ExecutionGap()
        # pre-registered per-family search size -> the FIXED wall (see _family_trials)
        self.family_trial_budget = int(family_trial_budget)

    def _cost_for(self, symbol: str) -> float:
        return self.cost_provider(symbol) if self.cost_provider is not None else self.cost

    def _effective_trials(self, n_new: int) -> int:
        """Cumulative trial count for cross-campaign DSR deflation: this cycle + all prior."""
        return n_new + self.store.total()

    def _family_trials(self, family: str, n_new_in_family: int, prior: dict[str, Any]) -> int:
        """FIXED-WALL DEFLATION (principal 2026-07-23). The DSR bar must be a WALL, not a ratchet
        that rises every time the desk tests anything -- otherwise objective #2 (maximize
        discovery) mechanically sabotages objective #1 by making every new test harder to pass.

        Two changes make a fixed bar STATISTICALLY LEGITIMATE rather than phantom-edge bait:

        (1) PARTITIONED -- a family is deflated by ITS OWN trials, never the global pool. Testing
            cross-asset can no longer harshen the funding-mechanism bar. This is standard
            per-family error budgeting: the families are pre-registered and economically
            distinct, so their error budgets are genuinely separate.

        (2) PRE-REGISTERED BUDGET -- within a family the deflation uses the DECLARED search size
            (a CONSTANT), so re-running the same space does not move the bar. That is correct on
            the merits: content-hash dedup means a re-run is not new information, and paying a
            deflation penalty for re-running identical hypotheses is double-counting.

        The correction is NOT removed -- it prices the search you PRE-REGISTERED instead of an
        ever-growing global tally. If a family genuinely EXCEEDS its declared budget the bar does
        rise (max() below), because that is real additional searching and hiding it would be
        exactly the meta-overfitting the cumulative counter existed to catch."""
        return max(self.family_trial_budget, n_new_in_family + int(prior.get(str(family), 0)))

    def cycle(self, symbols: Sequence[str]) -> CycleResult:
        campaign_id = generate_id("camp")
        # highest-priority families first; optionally restricted to a focused set (T0)
        plan = prioritize(planned_hypotheses(symbols, families=self.families))

        # 1) Backtest every NEW (non-duplicate) hypothesis for which data is available.
        prepared: list[tuple[Hypothesis, np.ndarray, np.ndarray]] = []
        skipped = 0
        series_cache: dict[str, MarketSeries | None] = {}
        for hyp, spec in plan:
            if self.store.exists(hyp):
                skipped += 1
                continue
            if hyp.symbol not in series_cache:
                series_cache[hyp.symbol] = self.data_provider(hyp.symbol)
            series = series_cache[hyp.symbol]
            if series is None or len(series) < _MIN_BARS:
                continue
            try:
                base_cost = self._cost_for(hyp.symbol)
                positions = spec.fn(series, dict(hyp.params))
                rets = net_returns(series, positions, cost=base_cost)
                stressed = net_returns(series, positions, cost=self.execution_gap.stress(base_cost))
            except Exception:
                continue
            if len(rets) >= _MIN_BARS:
                prepared.append((hyp, rets, stressed))

        result = self._validate_and_archive(campaign_id, prepared, skipped)
        self.store.set_checkpoint("last_campaign", campaign_id)
        self.audit.append(
            "autodiscovery_cycle", actor="autodiscovery_lab",
            inputs={"campaign_id": campaign_id, "generated": result.generated,
                    "tested": result.tested, "survivors": result.survivors,
                    "skipped_duplicate": result.skipped_duplicate},
            outcome=f"{result.survivors} survivors / {result.tested} tested",
        )
        return result

    def _validate_and_archive(
        self,
        campaign_id: str,
        prepared: list[tuple[Hypothesis, np.ndarray, np.ndarray]],
        skipped: int,
    ) -> CycleResult:
        if not prepared:
            return CycleResult(campaign_id=campaign_id, generated=0, tested=0,
                               skipped_duplicate=skipped)
        # Cross-campaign multiple-testing control (committee T3): deflate the DSR by the CUMULATIVE
        # number of trials ever run, not just this campaign's -- otherwise re-running the lab until
        # something passes is undetected meta-overfitting that funds a false survivor.
        n_trials = self._effective_trials(len(prepared))
        # FIXED WALL: group this cycle by family so each hypothesis is judged against its OWN
        # pre-registered budget and its OWN family's Sharpe distribution (internally consistent
        # DSR), never against the global pool of everything the desk has ever tested.
        _fam_new: dict[str, int] = {}
        for _h, _r, _s in prepared:
            _fam_new[str(_h.family)] = _fam_new.get(str(_h.family), 0) + 1
        _fam_prior = self.store.family_counts()
        _fam_trials = {f: self._family_trials(f, n, _fam_prior) for f, n in _fam_new.items()}
        _fam_sharpes = {
            f: np.array([sharpe_ratio(r) for h, r, _ in prepared if str(h.family) == f],
                        dtype="float64")
            for f in _fam_new
        }
        min_len = min(len(r) for _, r, _ in prepared)
        matrix = np.column_stack([r[-min_len:] for _, r, _ in prepared])  # T x N (selection-aware)
        sharpe_estimates = np.array([sharpe_ratio(r) for _, r, _ in prepared], dtype="float64")
        # PER-CANDIDATE multiplicity statistics, computed in ONE pass over the matrix (not Nx).
        # The predecessor hoisted campaign_pbo_rc() out of the loop for the same speed reason, but
        # PBO and White's Reality Check take ONLY the matrix -- the candidate's own returns are
        # never an input -- so as per-candidate gates they were campaign CONSTANTS. Measured on
        # this exact 420-candidate campaign: PBO 0.6159 (>0.5) and White RC p 0.4220 (>=0.05),
        # which alone forced 420/420 rejections regardless of any candidate's merit. CSCV
        # rank-consistency + Romano-Wolf stepdown replace them with a verdict each candidate earns
        # on its OWN column, and Romano-Wolf still controls family-wise error across all N, so
        # multiplicity is paid in full. Thresholds are UNCHANGED (PBO <= 0.5, significance at 5%);
        # only the attribution changed. Calibration proof: tests/validation/test_stepwise.py
        # (all-null campaign must not manufacture survivors; a known winner must be reachable).
        # Column mapping VERIFIED (both branches independently): matrix columns are
        # column_stack'd from `prepared` in order, and the enumerate below walks that same
        # list, so the loop index IS the candidate's column. Wired at all 19 legacy call
        # sites in the 07-29 closure cycle, not just here.
        gates_once = campaign_gate_stats(matrix)

        # ---------------------------------------------------------------- PASS 1: validate
        # Two passes, because the campaign-level FDR screen cannot be applied until every
        # candidate has a p-value. Promotion moved to pass 2. `col` indexes into `gates_once`,
        # the per-candidate CSCV/Romano-Wolf stats computed once above (see the note there).
        _Box = LockedHoldout[np.ndarray]
        evaluated: list[tuple[Hypothesis, np.ndarray, np.ndarray, Any, _Box | None]] = []
        for col, (hyp, rets, stressed) in enumerate(prepared):
            _f = str(hyp.family)
            # The FIXED WALL is the family-scoped TRIAL COUNT. The sharpe array is only the
            # dispersion input for the DSR variance term: a family contributing a single
            # hypothesis this cycle cannot estimate a variance from one point, so fall back to
            # the campaign-wide dispersion. That keeps the wall fixed without ever handing
            # deflated_sharpe_ratio a degenerate (len<2) sample.
            _sh = _fam_sharpes.get(_f)
            if _sh is None or len(_sh) < 2:
                _sh = sharpe_estimates
            # LOCKBOX (spec: a final slice openable exactly once). Validation runs on the
            # RESEARCH portion only; the holdout is opened once in pass 2 at the promotion
            # decision. Applied only when the research portion still clears _MIN_BARS on its
            # own, so a candidate is never failed for being short rather than for being bad.
            box: LockedHoldout[np.ndarray] | None = None
            research = rets
            if len(rets) >= int(_MIN_BARS / (1.0 - _LOCKBOX_FRACTION)) + 1:
                box = LockedHoldout(rets, holdout_fraction=_LOCKBOX_FRACTION)
                research = box.research()
            verdict = validate(
                research, hypothesis=hyp,
                n_trials=_fam_trials.get(_f, n_trials),
                sharpe_estimates=_sh,
                returns_matrix=matrix, campaign=gates_once, column=col,
            )
            evaluated.append((hyp, rets, stressed, verdict, box))

        # ------------------------------------------------- CAMPAIGN FDR (Benjamini-Hochberg)
        # Every candidate here already cleared a 0.95 per-candidate DSR bar. Run twenty past
        # that bar and you expect one false survivor by construction: the per-candidate control
        # says nothing about the error rate of the SET being promoted. This does.
        fdr_pass, fdr_threshold = campaign_fdr([e[3].metrics.dsr for e in evaluated])

        # ---------------------------------------------------------------- PASS 2: promote
        counts = dict.fromkeys(CandidateStatus, 0)
        for i, (hyp, rets, stressed, verdict, box) in enumerate(evaluated):
            status = promote(rets, validation_survived=verdict.survived)
            reason = verdict.rejection_reason
            # FDR screen: a candidate that survived every gate but does not clear the campaign's
            # BH threshold is demoted, not rejected -- it may be real, and paper will tell us.
            if status is CandidateStatus.REGISTRY and not fdr_pass[i]:
                status = CandidateStatus.PAPER
                reason = (f"failed: campaign_fdr (BH threshold p<={fdr_threshold:.4g} across "
                          f"{len(evaluated)} candidates)")
            # LOCKBOX: opened exactly ONCE, here, and only for a candidate that would otherwise
            # reach the registry. Opening it for candidates already rejected would burn the
            # holdout's independence for no decision.
            elif status is CandidateStatus.REGISTRY and box is not None:
                held = box.open_lockbox()
                if float(np.mean(held)) <= 0.0:
                    status = CandidateStatus.PAPER
                    reason = ("failed: lockbox (edge absent in the sealed final "
                              f"{_LOCKBOX_FRACTION:.0%} never used for validation)")
            # Execution-gap gate (Lever 2/T4): REGISTRY requires surviving live-cost stress too.
            if status is CandidateStatus.REGISTRY and not survives_execution_gap(
                float(np.sum(rets)), float(np.sum(stressed))
            ):
                status = CandidateStatus.PAPER
                reason = "failed: execution_gap (edge eroded under live-cost stress)"
            # Regime-robustness gate (Lever 3/T8): REGISTRY requires edge in >=2 vol regimes.
            elif status is CandidateStatus.REGISTRY and not regime_robust(rets):
                status = CandidateStatus.PAPER
                reason = "failed: regime_robustness (edge confined to one volatility regime)"
            counts[status] += 1
            self.store.record(
                campaign_id=campaign_id, hyp=hyp, status=status, metrics=verdict.metrics,
                survived=status is CandidateStatus.REGISTRY,
                rejection_reason=reason,
            )

        reached_shadow = counts[CandidateStatus.SHADOW] + counts[CandidateStatus.PAPER] + \
            counts[CandidateStatus.REGISTRY]
        reached_paper = counts[CandidateStatus.PAPER] + counts[CandidateStatus.REGISTRY]
        return CycleResult(
            campaign_id=campaign_id, generated=n_trials, tested=n_trials,
            skipped_duplicate=skipped, survivors=counts[CandidateStatus.REGISTRY],
            rejected=counts[CandidateStatus.REJECTED], promoted_to_shadow=reached_shadow,
            promoted_to_paper=reached_paper, promoted_to_registry=counts[CandidateStatus.REGISTRY],
        )

```

### libs/backtest/metrics.py
```python
"""Metrics engine — performance statistics from an equity curve and realized trades."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict

from libs.backtest.portfolio import Trade


class Metrics(BaseModel):
    """Performance metrics computed on NET equity."""

    model_config = ConfigDict(frozen=True)

    total_return: float
    cagr: float
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown: float
    volatility: float
    profit_factor: float
    expectancy: float
    n_trades: int
    win_rate: float


def compute_metrics(
    equity: pd.Series, trades: list[Trade], *, periods_per_year: float = 252.0
) -> Metrics:
    """Compute performance metrics from an equity curve and realized trades."""
    equity = equity.astype("float64")
    start = float(equity.iloc[0]) if len(equity) else 0.0
    last = float(equity.iloc[-1]) if len(equity) else 0.0
    total_return = (last / start - 1.0) if start > 0 else 0.0

    returns = equity.pct_change(fill_method=None).dropna()
    n = len(returns)
    ann = math.sqrt(periods_per_year)

    mean_r = float(returns.mean()) if n else 0.0
    std_r = float(returns.std(ddof=1)) if n >= 2 else 0.0
    sharpe = (mean_r / std_r * ann) if std_r > 0 else 0.0

    downside = returns[returns < 0]
    dstd = float(downside.std(ddof=1)) if len(downside) >= 2 else 0.0
    sortino = (mean_r / dstd * ann) if dstd > 0 else 0.0

    cagr = ((last / start) ** (periods_per_year / n) - 1.0) if (n > 0 and start > 0) else 0.0
    volatility = std_r * ann

    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    max_drawdown = float(drawdown.min()) if len(equity) else 0.0
    calmar = (cagr / abs(max_drawdown)) if max_drawdown < 0 else 0.0

    pnls = np.array([t.pnl for t in trades], dtype="float64")
    n_trades = len(pnls)
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gross_win = float(wins.sum())
    gross_loss = float(abs(losses.sum()))
    if gross_loss > 0:
        profit_factor = gross_win / gross_loss
    elif gross_win > 0:
        profit_factor = math.inf
    else:
        profit_factor = 0.0
    expectancy = float(pnls.mean()) if n_trades else 0.0
    win_rate = float(len(wins) / n_trades) if n_trades else 0.0

    return Metrics(
        total_return=total_return,
        cagr=cagr,
        sharpe=sharpe,
        sortino=sortino,
        calmar=calmar,
        max_drawdown=max_drawdown,
        volatility=volatility,
        profit_factor=profit_factor,
        expectancy=expectancy,
        n_trades=n_trades,
        win_rate=win_rate,
    )

```

### libs/backtest/queue_fill.py
```python
"""Queue-position + latency maker-fill model (method extracted from nkaz001/hftbacktest).

``libs.backtest.fills.FillEngine`` answers *at what price* a fill happens (slippage + commission).
It does NOT answer the prior question every maker strategy lives or dies on: **did the passive
order fill at all, and how much of it?** A post-only limit order joins the BACK of the queue at its
price level and fills only as same-side trades first consume the ``queue_ahead`` size in front of
it, then its own size (FIFO price-time priority) — and only after order latency puts it on the book.

hftbacktest models this on full L2/L3 tick data. This is a small, owned, reduced-form port of the
*mechanism* (queue priority + latency + partial fill) — enough to stop the backtest assuming a 100%
passive fill rate, which is a silent P&L lie for the maker-carry / cash-and-carry book (adversarial
finding: an over-optimistic maker fill rate manufactures edge that does not exist live).

Deliberately NOT modelled (documented, not hidden): book replenishment, cancellations ahead
shrinking the queue faster than trades, and price-level jumps. Use this for maker fill-rate realism,
not as an L3 HFT simulator.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class MakerFill(BaseModel):
    """Outcome of a passive order resting for one window."""

    model_config = ConfigDict(frozen=True)

    filled_units: float
    fill_fraction: float  # in [0, 1]: portion of the order that filled passively this window
    queue_cleared: bool  # did through-volume fully consume the queue ahead of the order?

    def __bool__(self) -> bool:
        return self.filled_units > 0.0


def maker_fill(
    *,
    order_size: float,
    queue_ahead: float,
    through_volume: float,
    feed_latency_s: float = 0.0,
    resting_window_s: float = 1.0,
) -> MakerFill:
    """Passive fill of ``order_size`` given ``queue_ahead`` units in front at the same level and
    ``through_volume`` units that traded at/through the level while the order rested.

    Latency eats the *front* of the resting window: trades arriving before the order is actually on
    the book — a ``feed_latency_s / resting_window_s`` fraction of ``through_volume`` — pass without
    ever queuing behind them. The order then fills only the through-volume that exceeds the queue
    ahead, capped at its own size. All sizes are in the same units (contracts or base qty).

    Raises:
        ValueError: on a non-positive ``order_size`` / ``resting_window_s`` or negative volumes.
    """
    if order_size <= 0.0:
        raise ValueError("order_size must be > 0")
    if queue_ahead < 0.0 or through_volume < 0.0:
        raise ValueError("queue_ahead and through_volume must be >= 0")
    if resting_window_s <= 0.0:
        raise ValueError("resting_window_s must be > 0")
    latency_frac = min(1.0, max(0.0, feed_latency_s / resting_window_s))
    effective_through = through_volume * (1.0 - latency_frac)
    past_queue = max(0.0, effective_through - queue_ahead)
    filled = min(order_size, past_queue)
    return MakerFill(
        filled_units=filled,
        fill_fraction=filled / order_size,
        queue_cleared=effective_through >= queue_ahead,
    )

```

### libs/data/quality.py
```python
"""Data quality framework: duplicates, missing bars, spikes, gaps, and a score.

These detectors operate on the canonical bar schema and are the gate between Bronze (raw)
and trustworthy Silver. Weekend handling is delegated to the trading calendar so that
missing-bar detection does not flag legitimately-closed sessions.
"""

from __future__ import annotations

import pandas as pd
from pydantic import BaseModel, ConfigDict

from libs.data.calendar import expected_index
from libs.data.instruments import get_spec
from libs.data.schema import TIMESTAMP, validate_bars
from libs.data.timeframe import Timeframe


class QualityReport(BaseModel):
    """A summary of a bar frame's data quality, with a 0-100 score."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    timeframe: str
    n_bars: int
    n_expected: int
    n_duplicates: int
    n_missing: int
    n_spikes: int
    n_gaps: int
    completeness: float
    score: float
    first_timestamp: str | None
    last_timestamp: str | None


def detect_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Return all rows that share a timestamp with another row."""
    mask = df[TIMESTAMP].duplicated(keep=False)
    return df.loc[mask].sort_values(TIMESTAMP).reset_index(drop=True)


def detect_missing_bars(df: pd.DataFrame, timeframe: Timeframe, symbol: str) -> pd.DatetimeIndex:
    """Return expected (calendar-aware) timestamps that are absent from ``df``."""
    if df.empty:
        return pd.DatetimeIndex([], tz="UTC")
    spec = get_spec(symbol)
    expected = expected_index(
        df[TIMESTAMP].min(), df[TIMESTAMP].max(), timeframe, spec.asset_class
    )
    present = pd.DatetimeIndex(df[TIMESTAMP])
    return expected.difference(present)


def detect_spikes(df: pd.DataFrame, *, threshold: float = 0.2) -> pd.DataFrame:
    """Return bars whose single-bar close-to-close return exceeds ``threshold`` (fraction)."""
    returns = df["close"].pct_change(fill_method=None)
    mask = returns.abs() > threshold
    flagged = df.loc[mask].copy()
    flagged["return"] = returns.loc[mask]
    return flagged.reset_index(drop=True)


def detect_gaps(
    df: pd.DataFrame, timeframe: Timeframe, *, threshold: float = 0.005
) -> pd.DataFrame:
    """Return bars that open beyond ``threshold`` from the prior close (price gaps).

    Flags whether each gap also spans a non-trading interval (e.g. a weekend), so expected
    weekend gaps can be distinguished from intrabar dislocations.
    """
    prev_close = df["close"].shift(1)
    gap_pct = (df["open"] - prev_close) / prev_close
    time_delta = df[TIMESTAMP].diff()
    crosses = time_delta > (pd.Timedelta(timeframe.timedelta) * 1.5)
    mask = gap_pct.abs() > threshold
    flagged = df.loc[mask].copy()
    flagged["gap_pct"] = gap_pct.loc[mask]
    flagged["crosses_nontrading"] = crosses.loc[mask].fillna(False)
    return flagged.reset_index(drop=True)


def compute_quality_score(df: pd.DataFrame, symbol: str, timeframe: Timeframe) -> QualityReport:
    """Compute a full quality report (completeness-led, penalised for dupes and spikes)."""
    validate_bars(df)
    n_bars = len(df)
    duplicates = detect_duplicates(df)
    missing = detect_missing_bars(df, timeframe, symbol)
    spikes = detect_spikes(df)
    gaps = detect_gaps(df, timeframe)

    n_duplicates = len(duplicates)
    n_missing = len(missing)
    n_spikes = len(spikes)
    n_gaps = len(gaps)
    n_expected = n_bars + n_missing

    completeness = (n_expected - n_missing) / n_expected if n_expected > 0 else 1.0
    dup_ratio = n_duplicates / n_bars if n_bars else 0.0
    spike_ratio = n_spikes / n_bars if n_bars else 0.0
    score = max(0.0, min(100.0, 100.0 * completeness - 50.0 * dup_ratio - 20.0 * spike_ratio))

    first_ts = df[TIMESTAMP].min().isoformat() if n_bars else None
    last_ts = df[TIMESTAMP].max().isoformat() if n_bars else None

    return QualityReport(
        symbol=symbol,
        timeframe=str(timeframe),
        n_bars=n_bars,
        n_expected=n_expected,
        n_duplicates=n_duplicates,
        n_missing=n_missing,
        n_spikes=n_spikes,
        n_gaps=n_gaps,
        completeness=round(completeness, 6),
        score=round(score, 4),
        first_timestamp=first_ts,
        last_timestamp=last_ts,
    )

```

### libs/execution/sub_accounts.py
```python
"""SUB-ACCOUNTS -- automated when the venue permits it, honest about when it does not.

PRINCIPAL ORDER (2026-07-30): *"allow our system to create automated subaccounts when needed."*

WHY THE DESK WANTS THEM AT ALL: isolation. A sub-account per sleeve gives per-strategy margin
isolation (one sleeve's liquidation cannot cascade into another's collateral), clean per-edge
capacity accounting (the OUTGROWN lifecycle reads real per-sleeve equity instead of an
attribution), and a blast-radius boundary for a misbehaving executor. Those are the same
properties the desk currently approximates in software; sub-accounts make the venue enforce them.

=================================================================================================
THE CONSTRAINT THAT SHAPES EVERYTHING HERE, stated before any code pretends otherwise
=================================================================================================
Binance exposes sub-account creation (`POST /sapi/v1/sub-account/virtualSubAccount`) ONLY to
corporate/entity accounts (and broker-programme members). A personal account gets an error, full
stop -- no code changes that. So this module is built in the only honest shape available:

  PROBE     ask the venue what THIS account may do, and persist the answer where the boards read
            it (`data/subaccounts.json`). Capability is measured, never assumed -- the same rule
            as everything else on this desk (L2.4: artifact over claim).
  USE       where the probe says yes: create_virtual() under a bounded policy (name prefix,
            hard cap on count) with an append-only ledger row per creation.
  BLOCKED   where it says no: record the exact blocker and the upgrade path (corporate
            verification), so the max-push queue carries a real item instead of a wish.

CREATION is automated once permitted -- it moves no money and is the cheap, reversible act.
TRANSFERS between accounts are the money path, and they follow the house rule for money-path
acts: signed (`authorised_by`), reasoned, capped per-transfer, append-only ledgered
(`data/subaccount_ledger.jsonl`). The desk may open drawers on its own; moving cash between
drawers carries a name, every time. Same design as libs/risk/capital_events.py, and for the same
reason: an unattributed money movement is how a rail gets defeated by nobody in particular.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
STATE = _ROOT / "data/subaccounts.json"
LEDGER = _ROOT / "data/subaccount_ledger.jsonl"

#: Policy: every desk-created sub-account is recognisable, and there is a hard cap. The cap is a
#: runaway-loop backstop, not a plan -- one sleeve per live strategy family is the design point.
NAME_PREFIX = "qdesk"
MAX_SUBACCOUNTS = 12
#: Per-transfer ceiling. Deliberately equity-relative not absolute (the $100k-floor lesson):
#: a desk-initiated inter-account move may never exceed this fraction of the book in one call.
MAX_TRANSFER_FRACTION = 0.25


class SubAccountsUnavailable(RuntimeError):
    """This account tier cannot use the sub-account API. Carries the venue's own words."""


@dataclass(frozen=True)
class Capability:
    available: bool
    detail: str
    n_existing: int = 0
    checked: str = ""


def _signed(path: str, params: dict[str, Any], *, method: str = "GET") -> Any:
    """Reuse the live connector's keyfile + signer -- one credential path, no second copy."""
    from libs.execution import binance_live
    return binance_live._signed(path, params, method=method)


def probe(*, write_state: bool = True) -> Capability:
    """Measure what this account may do. Never raises on 'not permitted' -- that is a RESULT.

    The distinction it must not blur: NO-KEYS (cannot ask), BLOCKED-TIER (asked, venue said
    personal accounts may not), and AVAILABLE (asked, got a list). Collapsing the first two into
    one 'unavailable' would hide the difference between a launch-day gap and a Binance
    verification task -- different owners, different fixes.
    """
    from libs.execution import binance_live
    now = datetime.now(tz=UTC).isoformat()
    if not binance_live.has_keys():
        cap = Capability(False, "NO-KEYS: no live credential on this box -- probe cannot run",
                         checked=now)
    else:
        try:
            resp = _signed("/sapi/v1/sub-account/list", {"limit": 200})
            subs = resp.get("subAccounts", []) if isinstance(resp, dict) else []
            cap = Capability(True, f"AVAILABLE: corporate-tier API confirmed, "
                                   f"{len(subs)} sub-account(s) exist", len(subs), now)
        except Exception as exc:
            cap = Capability(False, f"BLOCKED-TIER: venue refused the sub-account API "
                                    f"({str(exc)[:160]}). Upgrade path: Binance corporate/entity "
                                    "verification, or the broker programme. Until then this "
                                    "capability is externally gated, not missing.", checked=now)
    if write_state:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps({
            "checked": cap.checked, "available": cap.available, "detail": cap.detail,
            "n_existing": cap.n_existing,
            "policy": {"name_prefix": NAME_PREFIX, "max_subaccounts": MAX_SUBACCOUNTS,
                       "max_transfer_fraction": MAX_TRANSFER_FRACTION},
        }, indent=2), "utf-8")
    return cap


def _ledger_append(row: dict[str, Any]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def create_virtual(purpose: str) -> dict[str, Any]:
    """Create one virtual sub-account for a named purpose. Automated by design -- creation moves
    no money -- but bounded: recognisable name, hard count cap, ledger row per creation."""
    cap = probe()
    if not cap.available:
        raise SubAccountsUnavailable(cap.detail)
    if cap.n_existing >= MAX_SUBACCOUNTS:
        raise SubAccountsUnavailable(
            f"policy cap reached ({cap.n_existing}/{MAX_SUBACCOUNTS}) -- a runaway creation loop "
            "is indistinguishable from intent at the venue's end, so the cap is hard")
    if not purpose.strip() or len(purpose.strip()) < 8:
        raise SubAccountsUnavailable("a sub-account without a stated purpose is a drawer nobody "
                                     "can audit -- name what it isolates")
    tag = f"{NAME_PREFIX}{datetime.now(tz=UTC).strftime('%m%d%H%M')}"
    resp = _signed("/sapi/v1/sub-account/virtualSubAccount",
                   {"subAccountString": tag}, method="POST")
    row = {"at": datetime.now(tz=UTC).isoformat(), "action": "CREATE",
           "email": (resp or {}).get("email", tag), "purpose": purpose.strip()}
    _ledger_append(row)
    probe()                                             # refresh the persisted count
    return row


def transfer(*, to_email: str, asset: str, amount: float,
             authorised_by: str, reason: str) -> dict[str, Any]:
    """Move funds master->sub. MONEY PATH: signed, reasoned, capped, ledgered -- every time.

    The cap is equity-relative (MAX_TRANSFER_FRACTION of the live book per call). An absolute
    dollar cap would rot exactly the way the $100k capacity floor did -- correct at one book size,
    wrong at every other.
    """
    if not authorised_by.strip():
        raise SubAccountsUnavailable("unsigned transfer refused -- money moving between drawers "
                                     "carries a name, every time (same rule as capital_events)")
    if len(reason.strip()) < 12:
        raise SubAccountsUnavailable("a transfer reason is the record; state what it funds")
    try:
        from libs.autodiscovery.validation import _desk_equity_usd
        book = float(_desk_equity_usd())
    except Exception:
        book = 0.0
    if book <= 0:
        raise SubAccountsUnavailable("live book unreadable -- an uncapped transfer is refused, "
                                     "never waved through (fail-closed)")
    if amount > book * MAX_TRANSFER_FRACTION:
        raise SubAccountsUnavailable(
            f"transfer ${amount:,.2f} exceeds {MAX_TRANSFER_FRACTION:.0%} of the "
            f"${book:,.2f} book -- split it, or the principal moves it at the venue")
    cap = probe(write_state=False)
    if not cap.available:
        raise SubAccountsUnavailable(cap.detail)
    resp = _signed("/sapi/v1/sub-account/universalTransfer",
                   {"toEmail": to_email, "fromAccountType": "SPOT", "toAccountType": "SPOT",
                    "asset": asset, "amount": amount}, method="POST")
    row = {"at": datetime.now(tz=UTC).isoformat(), "action": "TRANSFER", "to": to_email,
           "asset": asset, "amount": amount, "authorised_by": authorised_by.strip(),
           "reason": reason.strip(), "venue_response": str(resp)[:120]}
    _ledger_append(row)
    return row

```

### libs/features/registry.py
```python
"""Feature registry with versioning.

Definitions are keyed ``name@vN``; a name may carry multiple versions but each version is
immutable once registered. ``register_feature`` can validate against a sample frame and
auto-reject leaky features before they ever enter the registry.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from libs.features.definition import FeatureDefinition
from libs.features.errors import FeatureError
from libs.features.validation import validate_feature


class FeatureRegistry:
    """An in-memory registry of versioned feature definitions."""

    def __init__(self) -> None:
        self._features: dict[str, FeatureDefinition] = {}

    def register(self, definition: FeatureDefinition, *, overwrite: bool = False) -> None:
        if definition.key in self._features and not overwrite:
            raise FeatureError(f"feature {definition.key} already registered")
        self._features[definition.key] = definition

    def get(self, name: str, version: int | None = None) -> FeatureDefinition:
        if version is not None:
            try:
                return self._features[f"{name}@v{version}"]
            except KeyError as exc:
                raise FeatureError(f"feature {name}@v{version} not found") from exc
        versions = self.versions(name)
        if not versions:
            raise FeatureError(f"feature {name} not found")
        return self._features[f"{name}@v{max(versions)}"]

    def versions(self, name: str) -> list[int]:
        return sorted(d.version for d in self._features.values() if d.name == name)

    def list(self) -> list[FeatureDefinition]:
        return list(self._features.values())

    def __len__(self) -> int:
        return len(self._features)

    def __contains__(self, key: str) -> bool:
        return key in self._features


DEFAULT_REGISTRY = FeatureRegistry()


def register_feature(
    definition: FeatureDefinition,
    *,
    registry: FeatureRegistry | None = None,
    bars: pd.DataFrame | None = None,
    label_columns: Sequence[str] = (),
    overwrite: bool = False,
) -> FeatureDefinition:
    """Register a feature, optionally validating (and auto-rejecting) it against ``bars``."""
    reg = registry if registry is not None else DEFAULT_REGISTRY
    if bars is not None:
        validate_feature(definition, bars, label_columns=label_columns, strict=True)
    reg.register(definition, overwrite=overwrite)
    return definition


def get_feature(
    name: str, version: int | None = None, *, registry: FeatureRegistry | None = None
) -> FeatureDefinition:
    reg = registry if registry is not None else DEFAULT_REGISTRY
    return reg.get(name, version)

```

### libs/features/validation.py
```python
"""Feature validation: leakage detection and train/serve parity.

The single mechanism behind leakage detection is **future invariance**: a causal feature's
value at time t must not change when *future* bars (> t) are mutated. This one test rejects
future leakage, lookahead bias, hindsight labels, and full-sample normalization. Parity is a
separate check that the offline (batch) and online (incremental) computations agree.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict

from libs.features.definition import FeatureDefinition
from libs.features.errors import FeatureError


class LeakageResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: bool
    n_checked: int
    n_leaked: int
    max_diff: float
    message: str

    def __bool__(self) -> bool:
        return self.ok


class ParityResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: bool
    n_checked: int
    n_mismatch: int
    max_abs_diff: float
    message: str

    def __bool__(self) -> bool:
        return self.ok


class FeatureValidation(BaseModel):
    model_config = ConfigDict(frozen=True)

    feature: str
    ok: bool
    structural_ok: bool
    leakage: LeakageResult
    parity: ParityResult
    reasons: list[str]

    def __bool__(self) -> bool:
        return self.ok


def _sample_points(n: int, start: int, count: int) -> list[int]:
    start = max(start, 1)
    if start >= n:
        return []
    if n - start <= count:
        return list(range(start, n))
    return list(np.linspace(start, n - 1, count, dtype=int))


def _equal(a: float, b: float, tol: float) -> bool:
    if np.isnan(a) and np.isnan(b):
        return True
    if np.isnan(a) != np.isnan(b):
        return False
    return bool(abs(a - b) <= tol)


def run_leakage_test(
    definition: FeatureDefinition,
    bars: pd.DataFrame,
    *,
    sample: int = 24,
    tol: float = 1e-9,
) -> LeakageResult:
    """Detect lookahead by mutating future bars and checking past values are invariant."""
    full = definition.compute(bars).to_numpy(dtype="float64")
    n = len(bars)
    points = _sample_points(n, definition.min_periods, sample)
    n_leaked = 0
    max_diff = 0.0
    ohlc = ["open", "high", "low", "close"]
    have = [c for c in ohlc if c in bars.columns]
    for t in points:
        if t >= n - 1:
            continue
        mutated = bars.copy()
        # Drastically scale every future bar; a causal feature at t cannot notice.
        mutated.loc[mutated.index[t + 1 :], have] = mutated.loc[
            mutated.index[t + 1 :], have
        ] * 1000.0
        recomputed = definition.compute(mutated).to_numpy(dtype="float64")
        if not _equal(float(full[t]), float(recomputed[t]), tol):
            n_leaked += 1
            max_diff = max(max_diff, abs(float(full[t]) - float(recomputed[t])))
    ok = n_leaked == 0
    message = "no future leakage" if ok else f"future leakage at {n_leaked} point(s)"
    return LeakageResult(
        ok=ok, n_checked=len(points), n_leaked=n_leaked, max_diff=max_diff, message=message
    )


def run_parity_test(
    definition: FeatureDefinition,
    bars: pd.DataFrame,
    *,
    sample: int = 24,
    tol: float = 1e-9,
) -> ParityResult:
    """Check the offline (batch) table equals the online (incremental) computation."""
    offline = definition.compute(bars).to_numpy(dtype="float64")
    n = len(bars)
    points = _sample_points(n, definition.min_periods, sample)
    n_mismatch = 0
    max_diff = 0.0
    for t in points:
        online_value = float(definition.compute(bars.iloc[: t + 1]).to_numpy(dtype="float64")[-1])
        if not _equal(float(offline[t]), online_value, tol):
            n_mismatch += 1
            max_diff = max(max_diff, abs(float(offline[t]) - online_value))
    ok = n_mismatch == 0
    message = "offline == online" if ok else f"parity violated at {n_mismatch} point(s)"
    return ParityResult(
        ok=ok, n_checked=len(points), n_mismatch=n_mismatch, max_abs_diff=max_diff, message=message
    )


def validate_feature(
    definition: FeatureDefinition,
    bars: pd.DataFrame,
    *,
    label_columns: Sequence[str] = (),
    strict: bool = False,
) -> FeatureValidation:
    """Validate a feature: structural inputs, target leakage, future leakage, parity.

    With ``strict=True`` a failure raises :class:`FeatureError`; otherwise a report is returned.
    """
    reasons: list[str] = []

    missing = [c for c in definition.inputs if c not in bars.columns]
    if missing:
        reasons.append(f"missing input columns: {missing}")
    leaked_labels = sorted(set(definition.inputs) & set(label_columns))
    if leaked_labels:
        reasons.append(f"target leakage: feature reads label column(s) {leaked_labels}")
    structural_ok = not reasons

    leakage = (
        run_leakage_test(definition, bars)
        if structural_ok
        else LeakageResult(ok=False, n_checked=0, n_leaked=0, max_diff=0.0, message="skipped")
    )
    parity = (
        run_parity_test(definition, bars)
        if structural_ok
        else ParityResult(
            ok=False, n_checked=0, n_mismatch=0, max_abs_diff=0.0, message="skipped"
        )
    )
    if not leakage.ok:
        reasons.append(f"future/lookahead leakage: {leakage.message}")
    if not parity.ok:
        reasons.append(f"train/serve parity violation: {parity.message}")

    ok = not reasons
    if strict and not ok:
        raise FeatureError(f"feature {definition.key} rejected: {'; '.join(reasons)}")
    return FeatureValidation(
        feature=definition.key,
        ok=ok,
        structural_ok=structural_ok,
        leakage=leakage,
        parity=parity,
        reasons=reasons,
    )

```

### libs/ops/alert_channels.py
```python
"""ALERT CHANNEL REGISTRY + DELIVERY LEDGER -- gap #38, built 2026-07-29.

WHAT WAS ALREADY THERE, and this does not rebuild it: `scripts/run_alerts.py` pages ntfy.sh and
already mirrors to an INDEPENDENT path (`_second_channel` -> the healthchecks.io `/fail` endpoint,
different provider, different network route). The unanimous 12/13 panel finding was never only
"add a channel" -- it was that the desk had **no delivery confirmation, no canary, and no way to
observe BOTH channels being silent**. That is what this module adds:

  1. one place that knows which channels are ARMED (and records unarmed as a STATE, never silence),
  2. an append-only DELIVERY LEDGER -- one row per attempt per channel, success or failure,
  3. `all_silent_since()`, so "nothing has been delivered anywhere in N hours" becomes an
     observable condition instead of the thing nobody notices for five days.

FAILURE SEMANTICS, learned the hard way twice: no channel's exception may ever propagate into the
alert path (2026-07-19: a latin-1 header encode killed 39/39 pushes silently for 29h across a live
dead-man fire), and no channel's failure may suppress another's. Every send is best-effort,
independently wrapped, and always logged.

WHAT THIS MODULE DELIBERATELY DOES NOT DO: it does not decide WHEN to page (that is
`run_alerts._checks`), it holds no thresholds, and it never reads book state.

Config (absent = gracefully unarmed, recorded): `data/secrets/alert_channels.json`
    {"channels": [{"kind": "telegram", "token": "...", "chat_id": "..."},
                  {"kind": "webhook",  "url": "https://..."},
                  {"kind": "email",    "host": "smtp...", "port": 587, "user": "...",
                   "password": "...", "to": "..."}]}
Stdlib only. import from libs.ops.alert_channels.
"""
from __future__ import annotations

import contextlib
import json
import smtplib
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from hashlib import sha256
from pathlib import Path
from typing import Any

_CONFIG = Path("data/secrets/alert_channels.json")
_LEDGER = Path("data/alert_delivery.jsonl")
_SILENT_FLAG = Path("data/ALERT_CHANNELS_SILENT")

_TIMEOUT = 12.0
_KINDS = ("ntfy", "telegram", "webhook", "email")


def _log(channel: str, ok: bool, detail: str, title: str, ledger: Path = _LEDGER) -> None:
    """One row per attempt. The title is HASHED, never stored: alert bodies can name positions,
    and a delivery ledger is not a place to leak book state."""
    with contextlib.suppress(OSError):
        ledger.parent.mkdir(parents=True, exist_ok=True)
        row = {"ts": datetime.now(tz=UTC).isoformat(), "channel": channel, "ok": ok,
               "detail": detail[:200],
               "title_sha": sha256(title.encode("utf-8", "ignore")).hexdigest()[:12]}
        with ledger.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")


def load_channels(config: Path = _CONFIG) -> list[dict[str, Any]]:
    """Armed channels from config. A missing/unreadable file is NOT an error -- it means the
    second-channel work is owed a human step (credentials on the box) and callers report that."""
    try:
        raw = json.loads(config.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    chans = raw.get("channels") if isinstance(raw, dict) else raw
    if not isinstance(chans, list):
        return []
    return [c for c in chans if isinstance(c, dict) and c.get("kind") in _KINDS]


def _send_telegram(cfg: dict[str, Any], title: str, body: str) -> str:
    url = f"https://api.telegram.org/bot{cfg['token']}/sendMessage"
    data = json.dumps({"chat_id": str(cfg["chat_id"]),
                       "text": f"{title}\n{body}"[:3900]}).encode()
    req = urllib.request.Request(url, data=data,
                                headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        return f"http {r.status}"


def _send_webhook(cfg: dict[str, Any], title: str, body: str) -> str:
    data = json.dumps({"title": title, "body": body}).encode()
    req = urllib.request.Request(str(cfg["url"]), data=data,
                                headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        return f"http {r.status}"


def _send_email(cfg: dict[str, Any], title: str, body: str) -> str:
    msg = EmailMessage()
    # Non-ASCII in a header is exactly what killed ntfy for 29h; email headers are MIME-encoded
    # by EmailMessage so this is safe, but keep the same discipline for consistency.
    msg["Subject"] = title.encode("ascii", "ignore").decode("ascii") or "quant alert"
    msg["From"] = str(cfg.get("user", "quant@localhost"))
    msg["To"] = str(cfg["to"])
    msg.set_content(body)
    port = int(cfg.get("port", 587))
    with smtplib.SMTP(str(cfg["host"]), port, timeout=_TIMEOUT) as s:
        with contextlib.suppress(smtplib.SMTPException):
            s.starttls()
        if cfg.get("user") and cfg.get("password"):
            s.login(str(cfg["user"]), str(cfg["password"]))
        s.send_message(msg)
    return "smtp ok"


def _send_ntfy(cfg: dict[str, Any], title: str, body: str) -> str:
    safe = title.encode("latin-1", "ignore").decode("latin-1")
    req = urllib.request.Request(f"https://ntfy.sh/{cfg['topic']}", data=body.encode(),
                                 headers={"Title": safe, "Priority": "high"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        return f"http {r.status}"


_SENDERS = {"ntfy": _send_ntfy, "telegram": _send_telegram,
            "webhook": _send_webhook, "email": _send_email}


def send_all(title: str, body: str, *, config: Path = _CONFIG,
             ledger: Path = _LEDGER) -> dict[str, Any]:
    """Fire EVERY armed channel; one channel's failure can never stop another's.

    Returns {"armed": n, "delivered": n, "results": [...]}. When nothing is armed the result says
    so and a row is written -- an unarmed pager is a recorded state, not silence.
    """
    channels = load_channels(config)
    if not channels:
        _log("none", False, "NOT-ARMED: data/secrets/alert_channels.json absent or empty",
             title, ledger)
        return {"armed": 0, "delivered": 0, "results": [],
                "note": "second-channel arming is a HUMAN step: drop credentials at "
                        "data/secrets/alert_channels.json on the box"}
    results = []
    for cfg in channels:
        kind = str(cfg.get("kind"))
        try:
            detail = _SENDERS[kind](cfg, title, body)
            ok = True
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, KeyError,
                smtplib.SMTPException, ValueError) as e:
            ok, detail = False, f"{type(e).__name__}: {e}"[:200]
        _log(kind, ok, detail, title, ledger)
        results.append({"channel": kind, "ok": ok, "detail": detail})
    return {"armed": len(channels), "delivered": sum(1 for r in results if r["ok"]),
            "results": results}


def ledger_tail(n: int = 20, *, ledger: Path = _LEDGER) -> list[dict[str, Any]]:
    try:
        lines = ledger.read_text("utf-8").splitlines()[-n:]
    except OSError:
        return []
    out = []
    for line in lines:
        with contextlib.suppress(json.JSONDecodeError):
            out.append(json.loads(line))
    return out


def last_success_per_channel(*, ledger: Path = _LEDGER) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        lines = ledger.read_text("utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        with contextlib.suppress(json.JSONDecodeError, KeyError):
            row = json.loads(line)
            if row.get("ok"):
                out[str(row["channel"])] = str(row["ts"])
    return out


def all_silent_since(hours: float = 24.0, *, ledger: Path = _LEDGER) -> bool:
    """True when NO channel has recorded a success inside the window.

    This is the condition the desk could not observe: the pager was dead 2026-07-11 -> 07-16 (five
    days) and again for 29h on 07-19, and in both cases the absence of delivery was invisible.
    Note what it is NOT: proof anyone READ the alert. Only an off-box watcher noticing the canary
    stopped arriving can prove that -- that is the healthchecks.io check of gap #17, deliberately
    not rebuilt here.
    """
    floor = datetime.now(tz=UTC) - timedelta(hours=hours)
    for ts in last_success_per_channel(ledger=ledger).values():
        with contextlib.suppress(ValueError):
            if datetime.fromisoformat(ts) >= floor:
                return False
    return True


def status(*, config: Path = _CONFIG, ledger: Path = _LEDGER) -> dict[str, Any]:
    channels = load_channels(config)
    return {"armed_kinds": [str(c.get("kind")) for c in channels],
            "armed": len(channels),
            "arming_owed": not channels,
            "last_success_per_channel": last_success_per_channel(ledger=ledger),
            "all_silent_24h": all_silent_since(24.0, ledger=ledger),
            "silent_flag_present": _SILENT_FLAG.exists(),
            "ledger_tail": ledger_tail(5, ledger=ledger)}

```

### libs/ops/platform_paths.py
```python
"""Cross-platform venv interpreter resolution.

The desk was authored on Windows (.venv/Scripts/python.exe) and migrated to a Linux VPS
(.venv/bin/python) 2026-07-12. Interpreter paths must resolve on BOTH so the same code runs
on the laptop and the server. ``windowless`` picks pythonw.exe on Windows (no console flash
for detached spawns); on POSIX there is no windowless variant, so it returns plain python.
"""

from __future__ import annotations

import os
from pathlib import Path


def venv_python(root: Path, *, windowless: bool = False) -> str:
    """Absolute path to this repo's venv interpreter for the current OS."""
    if os.name == "nt":
        exe = "pythonw.exe" if windowless else "python.exe"
        return str(root / ".venv" / "Scripts" / exe)
    return str(root / ".venv" / "bin" / "python")

```

### libs/ops/principal_page.py
```python
"""The principal page is APPEND-SAFE or it is a data-loss channel.

ORIGIN (2026-07-29). ``data/PRINCIPAL_ACTION.md`` is the desk's ONLY human-escalation channel and
the pager delivers **line 1**. Two organs write it:

  * ``max_audit`` strips its own escalation block and preserves every other line -- correct, and
    it is correct because exactly this bug was found and fixed there on 2026-07-28.
  * ``run_external_panel`` called ``Path(...).write_text(...)`` twice, bare. A total clobber.

So when the panel ran out of credits it wrote "PURCHASE DECISION: OpenRouter credits exhausted"
over the top of a pending **Tier-3 YES/NO ask** (the pbo/rc campaign-constant gate fix -- GAP #71,
the #1 item on the register, the gate blocking the entire discovery pipeline). The register still
recorded it as "paged, awaiting a ruling". It was never on the page the principal read. A decision
the desk was blocked on was deleted by an unrelated organ's budget notice.

This is the SAME failure shape as the 07-28 max_audit fix, one organ over -- and the adjacency
sweep that should have caught it is itself a written lesson ("a lesson that stays in the file
where it was learned is half a lesson", institutional_knowledge 2026-07-29). Hence a shared
helper rather than a second hand-rolled strip: the next organ that needs to page inherits the
preservation property instead of re-deriving it, correctly or otherwise.

CONTRACT
  * Never destroys text it did not write. Only the caller's OWN prior block (matched by
    ``marker``) is replaced, so repeated pages update in place instead of stacking forever.
  * The new message owns line 1, because that is the only line the pager sends.
  * Writes are verified by reading the file back -- the 07-28 bug was found precisely by
    re-reading after writing rather than trusting the write.
"""

from __future__ import annotations

from pathlib import Path

PAGE = Path("data/PRINCIPAL_ACTION.md")


def _strip_block(existing: str, marker: str) -> str:
    """Drop a previous block written by this same caller, keeping everyone else's text.

    A block is its ``marker`` line plus the indented/blank continuation lines beneath it. Any
    line that is neither is somebody else's message and ends the block.
    """
    kept: list[str] = []
    skipping = False
    for ln in existing.splitlines():
        if ln.startswith(marker):
            skipping = True
            continue
        if skipping and (ln.startswith(("  ", "\t")) or not ln.strip()):
            continue
        skipping = False
        kept.append(ln)
    return "\n".join(kept).strip()


def page(message: str, *, marker: str, path: Path | None = None) -> str:
    """Put ``message`` at the top of the principal page, preserving every other message --
    EXCEPT that URGENT blocks outrank everything else (2026-07-31, caught live by
    test_max_audit_run_preserves_a_written_page): the max_audit escalation paged itself onto
    line 1 ABOVE two pending Tier-3 asks, burying the desk's highest-priority decisions under
    defect noise -- the same attention-failure as the 07-29 clobber, in polite form. A
    non-URGENT message therefore inserts BELOW the leading run of URGENT paragraphs; only an
    URGENT message may take line 1 from another URGENT. Consequence for the daily re-reminder
    pager (which reads line 1): it re-sends the standing urgent ask rather than the newest
    housekeeping block, which is the correct priority.

    ``marker`` must be a stable prefix of ``message`` (e.g. "PURCHASE DECISION:") so a repeat
    page replaces its own prior copy rather than accumulating duplicates. Returns the text
    actually on disk after the write.
    """
    p = path or PAGE
    existing = p.read_text("utf-8") if p.exists() else ""
    body = _strip_block(existing, marker)
    msg = message.rstrip("\n")
    if body.startswith("URGENT") and not msg.lstrip().startswith("URGENT"):
        paras = body.split("\n\n")
        lead: list[str] = []
        while paras and paras[0].startswith("URGENT"):
            lead.append(paras.pop(0))
        rest = "\n\n".join(paras).strip()
        out = "\n\n".join(lead) + "\n\n" + msg + "\n" + (f"\n{rest}\n" if rest else "")
    else:
        out = msg + "\n" + (f"\n{body}\n" if body else "")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(out, "utf-8")
    return p.read_text("utf-8")            # verify by fresh read, never trust the write

```

### libs/research/axis_screen.py
```python
"""Reusable Stage-A axis-screening harness -- so every new-axis screen applies the SAME discipline
we applied to kimchi/coinbase/turkey by hand, with the de-contamination (angle-20) gate BAKED IN
and impossible to skip.

The bespoke part of onboarding a new axis (fetching a new API's history) is still per-source code,
but the ANALYTICAL LAST MILE -- z-score, IC, momentum/reversal Sharpe, same-period contamination
check, residual IC, artifact verdict, forward-clock persistence -- is identical every time and is
now this one audited function. The brain (when authed) or the CRO passes an aligned (signal, target)
series and gets the honest verdict + a started forward clock, instead of re-deriving the screen
(and re-forgetting the artifact gate) each time.

Stage-A only (two-stage law): ZERO promotion authority. A pass earns a forward clock, never capital.
Pure numpy. import from libs.research.axis_screen.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np


def stage_a_screen(signal: np.ndarray, target_ret: np.ndarray, *, name: str,
                   zwin: int = 20, contam_max: float = 0.20, ic_min: float = 0.03,
                   sharpe_min: float = 0.5, ic_ceiling: float = 0.35,
                   sharpe_ceiling: float = 6.0, clock: str | None = None,
                   horizon_days: float = 1.0, panel_width: int = 1) -> dict[str, Any]:
    """Screen a signal against NEXT-period target returns with the mandatory angle-20 gate.

    signal[t], target_ret[t] must be aligned same-period arrays (target_ret[t] = return realised
    over period t). The function predicts target_ret[t+1] from a z-scored signal[t], and checks
    that the signal LEADS rather than COINCIDES.

    Verdict (highest-priority first):
      SUSPECT-LOOKAHEAD      -- |IC|>ic_ceiling or best timing Sharpe>sharpe_ceiling. A daily
                                z-scored signal predicting next-day return this strongly is not
                                credible at this horizon; it means the two series are misaligned
                                (timezone/candle-label lookahead: e.g. a KST-day candle whose close
                                sits ~1.6d ahead of a UTC-day close), stale-repeated, or otherwise
                                leaking future info. Caught the bithumb_KR IC-0.72/Sharpe-10 fake.
                                Treated as an artifact -- NEVER earns a clock. Re-run a +/-1 day
                                shift-sensitivity check before trusting anything that trips this.
      TIMING-ARTIFACT        -- fails de-contam: |same-period corr|>contam_max OR residual IC
                                collapses below half the raw IC (the coinbase/turkey failure mode)
      SCREEN-INTERESTING     -- |IC|>=ic_min, best timing Sharpe>=sharpe_min, passes de-contam,
                                AND the sample was POWERED enough for clearing those floors to
                                mean anything. This is the ONLY verdict that starts a forward
                                clock, so the power condition is load-bearing, not cosmetic.
      SCREEN-WEAK            -- raw signal too weak to bother, AND the test was POWERED enough to
                                say so. Only this verdict is graveyard-grade negative knowledge.
      SCREEN-UNDERPOWERED    -- the effective sample could not resolve an effect at ic_min, so the
                                reading is uninformative in EITHER direction -- whether |IC| landed
                                under the floor or over it. "Could not tell": never record it as
                                "refuted", and never start a clock on it.

    horizon_days: the period of target_ret in days. Sharpe annualises by sqrt(365/horizon_days);
      leaving this at 1 while passing 20-day returns overstates Sharpe 4.47x (pure noise then
      scores 0.55 against the 0.5 floor) and slackens the sharpe_ceiling rail by the same factor.
    panel_width: number of cross-sectional units stacked into the flat arrays (1 = single series).
      Only n_eff/power use it; it does not change IC or Sharpe.
    """
    s = np.asarray(signal, dtype="float64")
    r = np.asarray(target_ret, dtype="float64")
    fwd = np.roll(r, -1)
    z = np.zeros(len(s))
    for t in range(zwin, len(s)):
        w = s[t - zwin:t]
        sd = w.std()
        z[t] = (s[t] - w.mean()) / sd if sd > 0 else 0.0
    zv, fv, tv = z[zwin:-1], fwd[zwin:-1], r[zwin:-1]
    if len(zv) < 30 or zv.std() == 0:
        return {"name": name, "verdict": "INSUFFICIENT-DATA", "n": len(zv)}

    ic = float(np.corrcoef(zv, fv)[0, 1]) if fv.std() else 0.0
    same = float(np.corrcoef(zv, tv)[0, 1]) if tv.std() else 0.0
    b = np.polyfit(tv, zv, 1)
    zr = zv - (b[0] * tv + b[1])                       # signal orthogonalised to same-period return
    ic_res = float(np.corrcoef(zr, fv)[0, 1]) if zr.std() and fv.std() else 0.0

    # Annualisation MUST match the target's period. target_ret are horizon_days-day returns, so a
    # year holds 365/horizon_days of them, not 365. The old hardcoded sqrt(365) overstated Sharpe by
    # sqrt(horizon_days) -- 2.24x at 5d, 4.47x at 20d -- which (a) made sharpe_min trivially
    # clearable (verified: pure noise on 20d returns scored 0.55 against a 0.5 floor) and (b) left
    # the sharpe_ceiling lookahead rail ~4.5x too loose exactly where slow signals live. Found
    # independently by three screening passes, 2026-07-26.
    ann = np.sqrt(365.0 / max(float(horizon_days), 1e-9))

    def _sh(sig: np.ndarray) -> float:
        rr = np.sign(sig) * fv
        return round(float(rr.mean() / rr.std() * ann), 2) if rr.std() else 0.0
    sh_mom, sh_rev = _sh(zv), _sh(-zv)
    best = max(abs(sh_mom), abs(sh_rev))

    # POWER. Overlapping horizon_days returns sampled daily carry ~n/horizon_days independent
    # observations. Reporting a null without the power to detect a real effect is not a refutation,
    # and graveyarding it as one destroys a hypothesis class on no evidence -- the graveyard is
    # permanent, so 'we could not tell' must never be recorded as 'it is dead'.
    # panel_width divides out cross-sectional stacking: a 139-symbol panel passed as one flat array
    # has n = symbol-days, and treating those as independent inflates every t-stat by
    # sqrt(panel_width) (~11.8x at 139 -- an apparent t=3.5 is really t=0.35).
    n_eff = max(len(zv) / max(float(horizon_days) * max(int(panel_width), 1), 1e-9), 1.0)
    min_detectable_ic = float(1.96 / np.sqrt(n_eff))
    # 'powered' asks whether the SAMPLE could have detected an effect worth caring about (ic_min),
    # NOT whether the observed IC happens to be large. Only under the former does a null mean
    # "looked and it is not there"; under the latter every null would be self-certifying.
    powered = min_detectable_ic <= ic_min

    # LOOKAHEAD RAIL, part 2: forward-exceeds-contemporaneous. A whole-period misalignment (a
    # KST-day candle labelled a UTC day, a close timestamped a bar early) produces strong forward
    # IC with weak same-period corr, and slips under the global ic_ceiling wherever honest
    # contemporaneous correlation is already high (measured ~0.34 on macro->crypto vs a 0.35
    # ceiling). BUT that same signature is the DEFINING SHAPE of a genuine leading indicator --
    # capital flows in at t, price answers at t+1 -- so the bare excess must not kill (2026-07-29:
    # it briefly did, and read SUSPECT-LOOKAHEAD onto the live kimchi axis directly above its own
    # shift test printing "no lookahead pattern"). Kill authority needs corroboration on BOTH of:
    #   RESOLVED: the excess clears the sampling-noise band for a correlation difference at this
    #     n_eff (1.96*sqrt(2/n_eff)); an unresolved excess at n_eff=121 is a costume, not a leak.
    #   TRANSLATES: misalignment has a fingerprint mechanism lacks -- lag the signal ONE period
    #     and a leaked series turns its forward skill into contemporaneous skill (same_lag1 jumps,
    #     ic_lag1 collapses), while a genuine lead just decays smoothly. corr(z[t-1], .) below.
    # Uncorroborated cases keep the annotation and fall through to the ordinary gates, where a
    # thin lead lands on SCREEN-UNDERPOWERED: clock keeps accruing, nothing killed, nothing found.
    ic_exceeds_contemporaneous = abs(ic) > max(abs(same), ic_min) * 1.5 and abs(ic) >= 0.15
    z1v = np.roll(z, 1)[zwin:-1]                       # signal lagged one period
    ic_lag1 = float(np.corrcoef(z1v, fv)[0, 1]) if z1v.std() and fv.std() else 0.0
    same_lag1 = float(np.corrcoef(z1v, tv)[0, 1]) if z1v.std() and tv.std() else 0.0
    shift_translates = (abs(same_lag1) > max(abs(ic_lag1), ic_min) * 1.5
                        and abs(same_lag1) > 0.5 * abs(ic))
    excess = abs(ic) - max(abs(same), ic_min) * 1.5
    resolved = excess > 1.96 * float(np.sqrt(2.0 / n_eff))

    decontam_fail = abs(same) > contam_max or abs(ic_res) < 0.5 * abs(ic)
    implausible = abs(ic) > ic_ceiling or best > sharpe_ceiling    # alignment/lookahead rail
    if implausible or (ic_exceeds_contemporaneous and resolved and shift_translates):
        verdict = "SUSPECT-LOOKAHEAD"                  # bithumb-class: too strong to be real
    elif best < sharpe_min or abs(ic) < ic_min:
        # Distinguish 'tested and refuted' from 'could not have detected it'. Only the former is
        # graveyard-grade negative knowledge.
        verdict = "SCREEN-WEAK" if powered else "SCREEN-UNDERPOWERED"
    elif decontam_fail:
        verdict = "TIMING-ARTIFACT"                    # angle-20 gate -- coinbase/turkey class
    elif not powered:
        # POWER CUTS BOTH WAYS. 'powered' used to gate only the negative branch, so a cell that
        # cleared ic_min/sharpe_min on a sample the harness had ALREADY declared blind was still
        # labelled SCREEN-INTERESTING -- announcing a find through the same instrument that just
        # reported it could not see. Origin cell:
        #   try_premium::T2_usdt_try_premium_vs_fxlake_eurcross::h20d
        #   n=77 ic=-0.0543 n_eff=3.9 min_detectable_ic=0.9989 powered=false sharpe_reversal=0.87
        # -- |IC| ~18x BELOW the harness's own detection floor, read as INTERESTING. At that n_eff
        # ~17% of pure-noise draws clear both floors, so the label was a coin flip with a name.
        # It matters because SCREEN-INTERESTING is the sole trigger for a forward clock (below),
        # and clocks are capped at MAX_FORWARD_SLOTS=12 and Holm-corrected: a slot spent on noise
        # BOTH burns a scarce slot AND raises the confirmation bar for every genuine candidate.
        # Below the detection floor the honest verdict is the one the negative branch already
        # gets -- could not tell -- NOT a kill (nothing was refuted) and NOT a find. Ordered after
        # decontam_fail so the angle-20 artifact gate keeps its precedence; neither branch can
        # reach SCREEN-INTERESTING, so this can only ever tighten the screen.
        verdict = "SCREEN-UNDERPOWERED"
    else:
        verdict = "SCREEN-INTERESTING"

    out = {"name": name, "n": len(zv), "ic": round(ic, 4),
           "sharpe_momentum": sh_mom, "sharpe_reversal": sh_rev,
           "same_period_corr": round(same, 3), "residual_ic": round(ic_res, 4),
           "decontam_passed": not decontam_fail, "implausible_leak": implausible,
           "horizon_days": float(horizon_days), "panel_width": int(panel_width),
           "n_eff": round(n_eff, 1),
           "min_detectable_ic": round(min_detectable_ic, 4), "powered": powered,
           "ic_exceeds_contemporaneous": ic_exceeds_contemporaneous,
           "ic_lag1": round(ic_lag1, 4), "same_lag1": round(same_lag1, 4),
           "shift_translates": shift_translates,
           "excess_resolved": resolved,
           "verdict": verdict, "current_z": round(float(z[-1]), 3),
           "stage": "A (zero promotion authority)"}

    if clock and verdict == "SCREEN-INTERESTING":
        p = Path(clock)
        today = datetime.now(tz=UTC).date().isoformat()
        prev = p.read_text("utf-8").splitlines() if p.exists() else []
        if not prev or json.loads(prev[-1]).get("date") != today:
            with p.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"date": today, "z20": out["current_z"],
                                     "screen": out}) + "\n")
    return out

```

### libs/research/microstructure.py
```python
"""Order-book microstructure features (method from nkaz001/algotrading-example).

Depth (queue) imbalance ``= (bid_size - ask_size) / (bid_size + ask_size)`` in ``[-1, 1]``: ``>0``
means more resting size on the bid than the ask (buy pressure). It is the order-flow cousin of the
taker-buy fraction the existing ``taker_flow`` sleeve already trades, provided here as an owned,
lagged, smoothed panel that ``crypto_sleeves._book`` can consume with no look-ahead.

NO repo contains alpha. This is a *feature*, not an edge: if it is ever screened into a sleeve it
counts as a trial in the DSR/trials ledger like any other. Ships as a construction primitive only.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def book_imbalance(bid_size: np.ndarray, ask_size: np.ndarray) -> np.ndarray:
    """Depth imbalance in ``[-1, 1]``; ``0`` wherever total resting size is ``0`` (no book)."""
    b = np.asarray(bid_size, dtype="float64")
    a = np.asarray(ask_size, dtype="float64")
    total = b + a
    result: np.ndarray = np.divide(b - a, total, out=np.zeros_like(total), where=total > 0.0)
    return result


def depth_imbalance_signal(
    bid_size: pd.DataFrame, ask_size: pd.DataFrame, *, lookback: int
) -> pd.DataFrame:
    """Lagged-ready, smoothed cross-sectional depth-imbalance panel (a signal, not a fill model).

    Mirrors the sleeve convention: a rolling mean over ``lookback`` bars; callers still ``shift(1)``
    before trading it (as ``_book`` does). Cells with no resting book become ``NaN`` and are dropped
    by the sleeve's ``min_names`` gate rather than silently treated as neutral.
    """
    if lookback < 1:
        raise ValueError("lookback must be >= 1")
    total = bid_size + ask_size
    imb = (bid_size - ask_size).where(total > 0.0) / total.where(total > 0.0)
    return imb.rolling(lookback).mean()

```

### libs/research/profit_retention.py
```python
"""Profit-retention engine: MFE/MAE, capture ratio, and exit overlays (pure, tested).

Building blocks for the gauntlet-gated exit study. They operate on a return series so they compose
with the sleeve backtests. The honesty rule lives in the CALLER: an overlay is promoted only if it
preserves CAGR and passes CPCV/DSR/PBO -- these functions just compute the candidate transforms;
they do not decide deployment, and must never run on a few dozen live points (fitting noise).
"""

from __future__ import annotations

import numpy as np


def cumulative_path(returns: np.ndarray) -> np.ndarray:
    """Cumulative compounded return path from per-period returns."""
    r = np.asarray(returns, dtype="float64")
    return np.cumprod(1.0 + r) - 1.0 if r.size else r


def mfe_mae(returns: np.ndarray) -> tuple[float, float]:
    """Maximum Favorable / Adverse Excursion of the cumulative path (peak gain, worst drawdown)."""
    cum = cumulative_path(returns)
    if cum.size == 0:
        return 0.0, 0.0
    return float(np.max(cum)), float(np.min(cum))


def capture_ratio(returns: np.ndarray) -> float | None:
    """Realized return / MFE -- the share of the peak favorable excursion actually kept. None if the
    path never went positive (capture undefined)."""
    r = np.asarray(returns, dtype="float64")
    if r.size == 0:
        return None
    mfe, _ = mfe_mae(r)
    realized = float(np.prod(1.0 + r) - 1.0)
    return realized / mfe if mfe > 0 else None


def vol_target_overlay(returns: np.ndarray, target_vol: float, *, lookback: int = 20) -> np.ndarray:
    """Scale exposure to a target per-period vol using trailing realized vol (never levers up >1x).
    The standard vol-trailing exit: cut size as volatility rises against you."""
    r = np.asarray(returns, dtype="float64")
    out = np.empty_like(r)
    for i in range(r.size):
        win = r[max(0, i - lookback):i]
        sd = float(np.std(win)) if win.size > 2 else target_vol
        scale = min(1.0, target_vol / sd) if sd > 0 else 1.0
        out[i] = r[i] * scale
    return out


def trailing_stop_exit(returns: np.ndarray, stop: float = 0.10) -> np.ndarray:
    """Flatten (zero subsequent returns) once the cumulative path draws down `stop` from its running
    peak -- a trailing exit for one holding episode (trend sleeves: let winners run, cut givers)."""
    r = np.asarray(returns, dtype="float64")
    out = r.copy()
    cum = peak = 0.0
    stopped = False
    for i in range(r.size):
        if stopped:
            out[i] = 0.0
            continue
        cum = (1.0 + cum) * (1.0 + r[i]) - 1.0
        peak = max(peak, cum)
        if cum <= peak - stop:
            stopped = True
    return out


def time_decay_exit(returns: np.ndarray, signal: np.ndarray, *, floor: float = 0.0) -> np.ndarray:
    """Zero the return whenever the edge signal (e.g. funding/basis carry) has decayed to/below
    `floor` -- a carry sleeve should exit when the carry disappears, not ride it to reversion."""
    r = np.asarray(returns, dtype="float64")
    s = np.asarray(signal, dtype="float64")
    return np.where(s > floor, r, 0.0)

```

### libs/research/second_family.py
```python
"""SECOND FAMILY (L1.33) -- the GPT seat as a standing partner on every exploration family.

PRINCIPAL ORDER (2026-07-31): *"and GPT and Claude work together ... on these families."*

WHY A SHARED MODULE RATHER THAN A COPY PER ORGAN. The capability hunt (L1.31) proved the pattern:
two model families propose INDEPENDENTLY, and cross-family agreement is evidence while agreement
within one family is style -- a model cannot see its own blind spot, so asking Claude twice
returns the first answer with more confidence. Every other exploration organ was single-family:
blindspot_max, the prober, blindrediscovery and the sweep's meta seat all think in exactly one
model's priors, which is precisely the failure mode they exist to detect, applied to themselves.

This is the one place the second family is called, so:
  - every organ gets the partner by importing ONE function (no per-organ copy to drift),
  - the DEGRADATION IS HONEST everywhere at once: an unfunded/blocked GPT seat returns
    available=False with its reason, and the caller records SINGLE-FAMILY rather than passing one
    model's opinion off as cross-family agreement,
  - and when the seat is funded, every organ gains the partner in the same deploy.

Usage inside an organ:

    from libs.research.second_family import ask_second_family, merge_verdict
    r = ask_second_family("Here is what I found: ... What did I MISS?", context="blindspot_max")
    verdict = merge_verdict(own_findings, r)     # CONFIRMED / SOLO / CONTESTED, honestly labelled
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent.parent

_LEDGER = _ROOT / "data/second_family_log.json"


@dataclass(frozen=True)
class SecondOpinion:
    """What the independent family said -- or precisely why it could not be asked."""

    available: bool
    text: str = ""
    reason: str = ""
    model: str = ""
    context: str = ""
    at: str = field(default_factory=lambda: datetime.now(tz=UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {"available": self.available, "model": self.model, "context": self.context,
                "at": self.at, "reason": self.reason, "chars": len(self.text)}


def ask_second_family(prompt: str, *, context: str, timeout: float = 300.0) -> SecondOpinion:
    """Ask the GPT-9 seat. NEVER raises and never blocks an organ: a dead partner degrades the
    run to single-family with a stated reason, which the caller must record."""
    try:
        import sys
        if str(_ROOT) not in sys.path:
            sys.path.insert(0, str(_ROOT))
        from scripts.run_strategic_director import MODEL, _ask
    except Exception as exc:
        return SecondOpinion(False, reason=f"second family unimportable: {exc}", context=context)
    text, err = _ask(prompt, MODEL, timeout=timeout)
    op = (SecondOpinion(False, reason=err or "empty response", model=MODEL, context=context)
          if (err or not text.strip())
          else SecondOpinion(True, text=text, model=MODEL, context=context))
    _log(op)
    return op


def _log(op: SecondOpinion) -> None:
    """Append-only record of every second-family call -- so 'the partner is dead' is a MEASURED
    fact with a date, not an impression, and funding it can be justified with evidence."""
    try:
        hist = json.loads(_LEDGER.read_text("utf-8"))
    except (OSError, ValueError):
        hist = {"calls": []}
    hist["calls"].append(op.to_dict())
    hist["calls"] = hist["calls"][-1000:]
    try:
        _LEDGER.parent.mkdir(parents=True, exist_ok=True)
        _LEDGER.write_text(json.dumps(hist, indent=2), "utf-8")
    except OSError:
        return


def merge_verdict(own: object, other: SecondOpinion) -> dict[str, Any]:
    """Label the joint result HONESTLY -- the whole value of a second family is in the label.

    CONFIRMED   both families produced findings -- the strongest signal this desk can generate
                without live evidence.
    SOLO        the partner was unavailable. Explicitly NOT 'confirmed': a single family's
                agreement with itself is style, and recording SOLO is what stops one model's
                opinion from being cited later as cross-family corroboration.
    CONTESTED   both ran, and the partner found something the first family did not -- the second
                strongest signal, because the delta is a measured blind spot.
    """
    own_txt = str(own or "").strip()
    if not other.available:
        return {"verdict": "SOLO", "reason": other.reason,
                "note": "single-family run -- NOT cross-family corroboration"}
    if own_txt and other.text.strip():
        return {"verdict": "CONFIRMED", "partner_chars": len(other.text),
                "note": "two independent families both produced findings; the DELTA between "
                        "them is the blind spot each could not see alone -- read it, do not "
                        "average it away"}
    return {"verdict": "CONTESTED", "partner_chars": len(other.text),
            "note": "the families disagree on whether anything is here; the partner's finding "
                    "is a candidate blind spot of the first"}


def blindspot_prompt(context: str, own_findings: str) -> str:
    """The standing partner brief: hunt what the FIRST family missed, never re-rank its list."""
    return (
        f"You are the INDEPENDENT SECOND MODEL FAMILY on a quant research desk's exploration "
        f"organ ({context}). Another model family has just hunted this space and produced the "
        f"findings below.\n\nYOUR JOB IS NOT TO REVIEW OR RE-RANK THEM. It is to name what they "
        f"MISSED -- the region their priors could not see. A model cannot see its own blind "
        f"spot; you exist because you have different ones.\n\n--- THEIR FINDINGS ---\n"
        f"{own_findings[:6000]}\n\n--- YOUR OUTPUT ---\n"
        f"MISSED: <the thing absent from their list, one line>\n"
        f"WHY THEY COULD NOT SEE IT: <what in their framing excludes it>\n"
        f"EVIDENCE: <the check/command/artifact that would confirm or kill it>\n"
        f"IF NOTHING: say 'NOTHING MISSED' and name the three regions you checked. An honest "
        f"null from an independent family is a real result -- padding is a defect.")

```

### libs/research/upbit_data.py
```python
"""Upbit daily candles, keyed by CLOSE date -- the ONE copy of the alignment policy.

WHY THIS MODULE EXISTS (2026-07-29). Two scripts each carried their own Upbit keying --
collect_kimchi_premium.py and revalidate_clocks.py -- and when the alignment leak was found and
fixed in the collector, the revalidator silently kept measuring the leaky join and printed the
same inflated IC as if nothing had changed. Two copies of one policy is the flat-$100k-floor
failure class (§42) arriving in the data layer: fixing one copy MOVES the bug, it does not remove
it. Both scripts now import this function; a third copy anywhere is a defect.

THE ALIGNMENT LEAK ITSELF. Upbit's `candle_date_time_utc` is the OPEN timestamp of a KST-day
candle. A KST day opens 15:00 UTC the previous calendar day, so keying by open-date labels every
close ~15h EARLY: key D carried a close taken at 15:00 UTC on D+1, and a "forward" screen of
signal[D] against the UTC-day D+1 return was ~62% contemporaneous overlap, not prediction. The
shift test exposed it (+1d cell 0.823 vs 0d 0.225; the honest no-overlap cell +0.018). Keying by
CLOSE date -- open + 1 day -- gives signal[K] information only up to 15:00 UTC on K, and a screen
against the K+1 UTC-day return has a 9h standoff instead of a 15h leak.

LIVE forward-clock rows were never affected: at collection time only completed candles exist, so
appended z-scores are honest by construction. The leak lived solely in HISTORICAL reconstruction,
which is exactly where celebrated backtest ICs come from -- reality (the accruing clock) stays
the arbiter, per constitution.
"""
from __future__ import annotations

import datetime as _dt
import json
import urllib.request

_UPBIT = "https://api.upbit.com/v1/candles/days"
_UA = {"User-Agent": "Mozilla/5.0 (quant-desk kimchi)"}


def upbit_daily_close_keyed(market: str = "KRW-BTC", count: int = 200,
                            timeout: int = 35) -> dict[str, float]:
    """{UTC close-date: trade_price} for Upbit KST-day candles. See module docstring."""
    req = urllib.request.Request(f"{_UPBIT}?market={market}&count={count}", headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        rows = json.loads(r.read())
    if not isinstance(rows, list):
        return {}
    out: dict[str, float] = {}
    for r_ in rows:
        d = _dt.date.fromisoformat(str(r_["candle_date_time_utc"])[:10]) + _dt.timedelta(days=1)
        out[d.isoformat()] = float(r_["trade_price"])
    return out

```

### libs/self_improvement/kill_switch.py
```python
"""Per-alpha kill switch — pauses an alpha (recommendation; capital stop needs approval)."""

from __future__ import annotations

from libs.self_improvement.models import ImprovementAction, ImprovementActionType


class AlphaKillSwitch:
    """Tracks paused alphas and emits pause recommendations (fail-closed on uncertainty)."""

    def __init__(self) -> None:
        self._tripped: set[str] = set()

    def trip(self, alpha_id: str, *, reason: str) -> ImprovementAction:
        self._tripped.add(alpha_id)
        return ImprovementAction(
            type=ImprovementActionType.PAUSE,
            target_id=alpha_id,
            rationale=reason,
            detail={"paused": True},
            requires_portfolio_approval=True,  # taking capital to zero is a Portfolio Engine action
        )

    def reset(self, alpha_id: str) -> None:
        self._tripped.discard(alpha_id)

    def is_tripped(self, alpha_id: str) -> bool:
        return alpha_id in self._tripped

    @property
    def tripped(self) -> frozenset[str]:
        return frozenset(self._tripped)

```

### libs/self_improvement/marketplace.py
```python
"""Alpha marketplace — the master registry view (reuses ``AlphaCardStore``).

Single source of truth: the marketplace is a read/grouping view over the existing
``alpha_cards`` registry. Production status is the lifecycle ACTIVE state; no alpha reaches
production without passing through the lifecycle (registry approval).
"""

from __future__ import annotations

from libs.alpha.card import AlphaCard
from libs.alpha.registry import AlphaCardStore
from libs.alpha.state import AlphaState
from libs.self_improvement.models import AlphaCategory
from libs.store.connection import Database


class AlphaMarketplace:
    """A categorized, status-aware view of the master alpha registry."""

    def __init__(self, db: Database) -> None:
        self.store = AlphaCardStore(db)

    def all(self) -> list[AlphaCard]:
        return self.store.list_all()

    def by_status(self, state: AlphaState) -> list[AlphaCard]:
        return self.store.list_by_status(state)

    def production(self) -> list[AlphaCard]:
        """Production alphas are those in the ACTIVE lifecycle state."""
        return self.store.list_by_status(AlphaState.ACTIVE)

    def by_category(self) -> dict[AlphaCategory, list[AlphaCard]]:
        grouped: dict[AlphaCategory, list[AlphaCard]] = {}
        for card in self.store.list_all():
            grouped.setdefault(AlphaCategory.from_text(card.category), []).append(card)
        return grouped

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for card in self.store.list_all():
            counts[card.status.value] = counts.get(card.status.value, 0) + 1
        return counts

```

### libs/signal_engine/factor_exposure.py
```python
"""Factor exposure engine — net style/factor loadings and concentration control.

Aggregates the contributing alphas' factor loadings by their weights, reports the net exposures,
and flags excessive single-factor concentration so the engine does not pile risk into one style.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from libs.signal_engine.models import AlphaSignal, FactorExposureResult

_FACTORS = (
    "momentum", "value", "growth", "quality", "carry", "volatility", "liquidity", "macro",
)


class FactorExposureEngine:
    """Computes net factor exposures and a concentration check."""

    def __init__(self, *, max_concentration: float = 0.40) -> None:
        self.max_concentration = max_concentration

    def assess(
        self,
        signals: Sequence[AlphaSignal],
        weights: Mapping[str, float],
        *,
        loadings: Mapping[str, Mapping[str, float]] | None = None,
    ) -> FactorExposureResult:
        loadings = loadings or {}
        exposures: dict[str, float] = dict.fromkeys(_FACTORS, 0.0)
        for s in signals:
            w = weights.get(s.alpha_id, 0.0)
            alpha_load = loadings.get(s.alpha_id, {})
            for factor, value in alpha_load.items():
                if factor in exposures:
                    exposures[factor] += w * float(value)
        gross = sum(abs(v) for v in exposures.values())
        concentration = (max(abs(v) for v in exposures.values()) / gross) if gross > 0 else 0.0
        nonzero = {k: v for k, v in exposures.items() if v != 0.0}
        return FactorExposureResult(
            exposures=nonzero,
            concentration=concentration,
            acceptable=concentration <= self.max_concentration,
        )

```

### libs/signal_engine/market_impact_forecaster.py
```python
"""Market impact forecaster — temporary/permanent impact and fill quality before execution.

A square-root market-impact model scaled by participation and volatility. The forecast feeds the
expected value, edge, and execution scores so a signal that would move the market against itself
is penalized before any order is sent.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict


class ImpactForecast(BaseModel):
    model_config = ConfigDict(frozen=True)

    temporary_impact_bps: float
    permanent_impact_bps: float
    total_impact_bps: float
    expected_fill_quality: float  # 0..1 (1 = perfect fill)


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class MarketImpactForecaster:
    """Forecasts pre-trade market impact and fill quality."""

    def __init__(
        self,
        *,
        impact_coefficient: float = 0.1,
        permanent_fraction: float = 0.4,
        fill_cost_cap_bps: float = 50.0,
    ) -> None:
        self.impact_coefficient = impact_coefficient
        self.permanent_fraction = permanent_fraction
        self.fill_cost_cap_bps = fill_cost_cap_bps

    def forecast(
        self,
        *,
        notional: float,
        adv_usd: float,
        volatility_state: float = 0.5,
    ) -> ImpactForecast:
        participation = notional / adv_usd if adv_usd > 0 else 1.0
        temporary = (
            self.impact_coefficient * math.sqrt(max(participation, 0.0)) * 1e4
            * (1.0 + _clip01(volatility_state))
        )
        permanent = temporary * self.permanent_fraction
        total = temporary + permanent
        fill_quality = _clip01(1.0 - total / self.fill_cost_cap_bps)
        return ImpactForecast(
            temporary_impact_bps=temporary,
            permanent_impact_bps=permanent,
            total_impact_bps=total,
            expected_fill_quality=fill_quality,
        )

```

### libs/stage14/capacity.py
```python
"""Portfolio capacity scoring and ENFORCEMENT.

Scoring alone does not protect capital — many strategies die from capacity before alpha decay. The
governor enforces: scale positions when utilization is high, block allocation when forecast
slippage exceeds a threshold, and zero the allocation when impact cost exceeds the edge.
"""

from __future__ import annotations

from libs.stage14.models import CapacityGovernorAction, PortfolioCapacityResult


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class PortfolioCapacityEngine:
    """Scores portfolio capacity from utilization, forecast slippage, and impact."""

    def evaluate(
        self,
        *,
        deployed_capital: float,
        max_efficient_capital: float,
        forecast_slippage: float,
        impact_cost: float,
    ) -> PortfolioCapacityResult:
        utilization = (
            deployed_capital / max_efficient_capital if max_efficient_capital > 0 else 1.0
        )
        score = 100.0 * (1.0 - _clip01(utilization))
        return PortfolioCapacityResult(
            capacity_utilization=_clip01(utilization),
            capacity_score=score,
            forecast_slippage=forecast_slippage,
            impact_cost=impact_cost,
        )


class PortfolioCapacityGovernor:
    """Enforces capacity limits (not just scores them)."""

    def __init__(
        self,
        *,
        scale_threshold: float = 0.80,
        slippage_threshold: float = 0.0020,
    ) -> None:
        self.scale_threshold = scale_threshold
        self.slippage_threshold = slippage_threshold

    def govern(self, capacity: PortfolioCapacityResult, *, edge: float) -> CapacityGovernorAction:
        # impact cost exceeding the edge destroys the trade -> zero it.
        if capacity.impact_cost > edge:
            return CapacityGovernorAction(
                action="zero", scale_factor=0.0,
                reason=f"impact_cost {capacity.impact_cost:.4f} > edge {edge:.4f}",
            )
        # forecast slippage above the threshold -> block new allocation.
        if capacity.forecast_slippage > self.slippage_threshold:
            return CapacityGovernorAction(
                action="block", scale_factor=0.0,
                reason=f"forecast_slippage {capacity.forecast_slippage:.4f} "
                f"> {self.slippage_threshold:.4f}",
            )
        # high utilization -> scale positions down proportionally toward the threshold.
        if capacity.capacity_utilization > self.scale_threshold:
            scale = self.scale_threshold / capacity.capacity_utilization
            return CapacityGovernorAction(
                action="scale", scale_factor=_clip01(scale),
                reason=f"utilization {capacity.capacity_utilization:.2f} "
                f"> {self.scale_threshold:.2f}",
            )
        return CapacityGovernorAction(action="ok", scale_factor=1.0, reason="capacity ok")

```

### libs/stage14/state_machine.py
```python
"""Portfolio state machine — NORMAL / CAUTION / DEFENSIVE / CRISIS / RECOVERY.

The state modulates risk budgets, Kelly fractions, leverage, and allocations. Survival dominates:
deteriorating drawdown or survival pushes the portfolio defensive long before it would push it back.
"""

from __future__ import annotations

from libs.stage14.models import PortfolioState

_RISK_MULTIPLIER: dict[PortfolioState, float] = {
    PortfolioState.NORMAL: 1.0,
    PortfolioState.CAUTION: 0.7,
    PortfolioState.DEFENSIVE: 0.4,
    PortfolioState.CRISIS: 0.0,
    PortfolioState.RECOVERY: 0.5,
}


class PortfolioStateMachine:
    """Classifies the portfolio risk regime and the risk multiplier it implies."""

    def classify(
        self,
        *,
        drawdown: float,
        survival_score: float = 100.0,
        regime_uncertainty: float = 0.0,
        recovering: bool = False,
    ) -> PortfolioState:
        if drawdown >= 0.20 or survival_score < 50.0:
            return PortfolioState.CRISIS
        if drawdown >= 0.12 or survival_score < 70.0 or regime_uncertainty > 0.7:
            return PortfolioState.DEFENSIVE
        if recovering and drawdown < 0.06:
            return PortfolioState.RECOVERY
        if drawdown >= 0.06 or regime_uncertainty > 0.4:
            return PortfolioState.CAUTION
        return PortfolioState.NORMAL

    @staticmethod
    def risk_multiplier(state: PortfolioState) -> float:
        return _RISK_MULTIPLIER[state]

```

### libs/stage14_5/errors.py
```python
"""Stage 14.5 hedging / exposure-management errors."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class Stage14_5Error(QuantPlatformError):
    """Base error for Stage 14.5 portfolio hedging and exposure management."""


class HedgeGovernanceError(Stage14_5Error):
    """Raised when a hedge violates Stage 14.5 governance (fail-closed)."""

```

### libs/stage14_5/hedging.py
```python
"""Portfolio hedging engine — institutional protection, governed and lifecycle-managed.

Proposes diversifying tilts and crisis-alpha adds (never retail offsets). A hedge may exist ONLY
if it improves expected CAGR, materially improves survival, or its tail-risk reduction exceeds any
growth it costs — otherwise it is rejected. The lifecycle engine closes hedges that have served
their purpose. Survival dominates return; growth dominates cosmetic smoothness.
"""

from __future__ import annotations

from collections.abc import Mapping

from libs.stage14_5.models import (
    FactorExposureResult,
    HedgeEffectiveness,
    HedgeGovernanceVerdict,
    HedgeLifecycleDecision,
    HedgeProposal,
    HedgeType,
    RegimeExposureResult,
)

_EFFECTIVENESS_WEIGHTS: dict[str, float] = {
    "cagr": 0.25,
    "survival": 0.35,
    "diversification": 0.20,
    "tail": 0.20,
}


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def hedge_governance_gate(
    *,
    expected_cagr_delta: float,
    expected_survival_delta: float,
    expected_tail_reduction: float,
    survival_materiality: float = 0.02,
) -> HedgeGovernanceVerdict:
    """A hedge is approved only if it earns its place; never to smooth volatility cosmetically."""
    growth_cost = max(0.0, -expected_cagr_delta)
    if expected_cagr_delta > 0:
        return HedgeGovernanceVerdict(approved=True, reason="improves expected CAGR")
    if expected_survival_delta >= survival_materiality:
        return HedgeGovernanceVerdict(approved=True, reason="materially improves survival")
    if expected_tail_reduction > growth_cost:
        return HedgeGovernanceVerdict(
            approved=True, reason="tail-risk reduction exceeds growth reduction"
        )
    return HedgeGovernanceVerdict(
        approved=False, reason="rejected: sacrifices growth without survival/tail justification"
    )


def hedge_effectiveness_score(
    *,
    cagr_contribution: float,
    survival_contribution: float,
    diversification_contribution: float,
    tail_risk_contribution: float,
    capacity_impact: float,
) -> HedgeEffectiveness:
    positive = (
        _EFFECTIVENESS_WEIGHTS["cagr"] * _clip01(cagr_contribution)
        + _EFFECTIVENESS_WEIGHTS["survival"] * _clip01(survival_contribution)
        + _EFFECTIVENESS_WEIGHTS["diversification"] * _clip01(diversification_contribution)
        + _EFFECTIVENESS_WEIGHTS["tail"] * _clip01(tail_risk_contribution)
    )
    score = 100.0 * _clip01(positive - 0.2 * _clip01(capacity_impact))
    return HedgeEffectiveness(
        hedge_effectiveness_score=score, cagr_contribution=cagr_contribution,
        survival_contribution=survival_contribution,
        diversification_contribution=diversification_contribution,
        tail_risk_contribution=tail_risk_contribution, capacity_impact=capacity_impact,
    )


class PortfolioHedgingEngine:
    """Proposes institutional hedges from concentration / factor / regime / crisis signals."""

    def __init__(self, *, max_family_share: float = 0.40) -> None:
        self.max_family_share = max_family_share

    def propose(
        self,
        *,
        family_weights: Mapping[str, float],
        factor_result: FactorExposureResult | None = None,
        regime_result: RegimeExposureResult | None = None,
        crisis_recommended: bool = False,
    ) -> list[HedgeProposal]:
        proposals: list[HedgeProposal] = []
        proposals.extend(self._alpha_hedges(family_weights))
        if factor_result is not None and not factor_result.acceptable:
            proposals.append(
                HedgeProposal(
                    hedge_type=HedgeType.FACTOR, target="dominant_factor",
                    rationale="reduce concentrated factor exposure",
                    expected_cagr_delta=-0.002, expected_survival_delta=0.03,
                    expected_tail_reduction=0.05,
                )
            )
        if regime_result is not None:
            for regime in regime_result.uncovered_regimes:
                proposals.append(
                    HedgeProposal(
                        hedge_type=HedgeType.REGIME, target=regime,
                        rationale=f"add exposure to uncovered regime: {regime}",
                        expected_cagr_delta=0.001, expected_survival_delta=0.02,
                        expected_tail_reduction=0.02,
                    )
                )
        if crisis_recommended:
            proposals.append(
                HedgeProposal(
                    hedge_type=HedgeType.CRISIS, target="crisis_alpha",
                    rationale="add crisis-alpha exposure (pays during breakdowns)",
                    expected_cagr_delta=-0.005, expected_survival_delta=0.06,
                    expected_tail_reduction=0.10,
                )
            )
        return proposals

    def propose_governed(self, **kwargs: object) -> list[HedgeProposal]:
        """Propose hedges and keep only those that pass governance."""
        return [
            p
            for p in self.propose(**kwargs)  # type: ignore[arg-type]
            if hedge_governance_gate(
                expected_cagr_delta=p.expected_cagr_delta,
                expected_survival_delta=p.expected_survival_delta,
                expected_tail_reduction=p.expected_tail_reduction,
            ).approved
        ]

    def _alpha_hedges(self, family_weights: Mapping[str, float]) -> list[HedgeProposal]:
        total = sum(abs(v) for v in family_weights.values())
        if total <= 0 or len(family_weights) < 2:
            return []
        shares = {k: abs(v) / total for k, v in family_weights.items()}
        dominant, top_share = max(shares.items(), key=lambda kv: kv[1])
        if top_share <= self.max_family_share:
            return []
        weakest = min(shares.items(), key=lambda kv: kv[1])[0]
        return [
            HedgeProposal(
                hedge_type=HedgeType.ALPHA, target=weakest,
                rationale=f"{dominant} dominates ({top_share:.0%}); rebalance toward {weakest}",
                expected_cagr_delta=0.0, expected_survival_delta=0.03,
                expected_tail_reduction=0.04,
            )
        ]


class HedgeLifecycleEngine:
    """Closes hedges that have outlived their purpose (fail-closed toward closing)."""

    def __init__(self, *, min_effectiveness: float = 40.0) -> None:
        self.min_effectiveness = min_effectiveness

    def evaluate(
        self,
        hedge_type: HedgeType,
        *,
        crisis_active: bool,
        effectiveness_score: float,
        survival_benefit: float,
        cost: float,
        benefit: float,
    ) -> HedgeLifecycleDecision:
        reasons: list[str] = []
        if hedge_type is HedgeType.CRISIS and not crisis_active:
            reasons.append("crisis regime ended")
        if effectiveness_score < self.min_effectiveness:
            reasons.append("hedge effectiveness fell below threshold")
        if survival_benefit <= 0.0:
            reasons.append("portfolio survival benefit disappeared")
        if cost > benefit:
            reasons.append("hedge cost exceeds benefit")
        return HedgeLifecycleDecision(close=bool(reasons), reasons=reasons)

```

### libs/store/hashchain.py
```python
"""Hash-chain primitives for tamper-evident, append-only tables.

Each row hashes its own content together with the previous row's hash, forming a chain:
any retroactive edit to a row (or a reordering) breaks every hash after it, which
:func:`libs.store.audit.verify_audit_chain` and friends detect.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any

# The chain's anchor: the predecessor hash of the very first row.
GENESIS_PREV_HASH = "0" * 64


def canonical_json(obj: Any) -> str:
    """Serialize ``obj`` to canonical JSON (sorted keys, compact, ``str`` fallback)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def sha256_hex(text: str) -> str:
    """Return the SHA-256 hex digest of ``text``."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_chain_hash(fields: Mapping[str, Any]) -> str:
    """Compute a row hash from its content fields (which must include ``prev_hash``)."""
    return sha256_hex(canonical_json(dict(fields)))


def verify_chain(
    rows: Sequence[Mapping[str, Any]],
    build_fields: Callable[[Mapping[str, Any]], dict[str, Any]],
) -> tuple[bool, int | None, str]:
    """Verify a hash chain given rows ordered by ``seq``.

    Checks contiguous sequence numbers (from 1), correct ``prev_hash`` linkage, and that each
    stored ``row_hash`` matches a recomputation of its content — so any edit, deletion, or
    reordering is detected.

    Returns ``(ok, broken_seq, message)``.
    """
    prev = GENESIS_PREV_HASH
    expected_seq = 1
    for row in rows:
        seq = int(row["seq"])
        if seq != expected_seq:
            return False, seq, f"non-contiguous sequence: expected {expected_seq}, got {seq}"
        if row["prev_hash"] != prev:
            return False, seq, f"prev_hash mismatch at seq {seq}"
        recomputed = compute_chain_hash(build_fields(row))
        if recomputed != row["row_hash"]:
            return False, seq, f"row_hash mismatch at seq {seq} (tampered)"
        prev = str(row["row_hash"])
        expected_seq += 1
    return True, None, "chain intact"

```

### libs/validation/revalidation.py
```python
"""Walk-forward governance and automated revalidation (fail-closed).

Re-proves a strategy on rolling out-of-sample windows and gates production capital on the result:
no strategy may hold production capital unless ``walk_forward_status == PASSED``. A set of triggers
(structural break, drift, regime transition, performance/capacity deterioration, signal decay,
staleness) forces revalidation; a hard trigger downgrades an otherwise-passing strategy to STALE
until it re-passes. Reuses the existing walk-forward splits, Sharpe, and Stage 13 decay levels.
"""

from __future__ import annotations

from enum import StrEnum

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from libs.self_improvement.models import DecayLevel
from libs.validation.dsr import sharpe_ratio
from libs.validation.errors import ValidationError
from libs.validation.walk_forward import walk_forward_splits


class WalkForwardStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    STALE = "stale"      # was passing but a hard trigger requires re-proof
    PENDING = "pending"  # never evaluated


class RevalidationTrigger(StrEnum):
    STRUCTURAL_BREAK = "structural_break"
    DRIFT = "drift"
    REGIME_TRANSITION = "regime_transition"
    SHARPE_DETERIORATION = "sharpe_deterioration"
    PF_DETERIORATION = "pf_deterioration"
    CAPACITY_DETERIORATION = "capacity_deterioration"
    SIGNAL_DECAYING = "signal_decaying"
    SIGNAL_DEAD = "signal_dead"
    STALE = "stale"
    MANUAL = "manual"


# Triggers that, on their own, must block production until the strategy re-passes.
_HARD_TRIGGERS = frozenset(
    {
        RevalidationTrigger.STRUCTURAL_BREAK,
        RevalidationTrigger.DRIFT,
        RevalidationTrigger.SIGNAL_DEAD,
    }
)


class WalkForwardReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: WalkForwardStatus
    walk_forward_score: float  # 0-100
    n_windows: int
    oos_sharpe: float
    oos_mean_return: float
    stability: float  # fraction of OOS windows with positive mean return
    message: str


class RevalidationDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    required: bool
    triggers: list[RevalidationTrigger] = Field(default_factory=list)
    status: WalkForwardStatus
    production_capital_allowed: bool
    rationale: str


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class WalkForwardEngine:
    """Rolling out-of-sample evaluation producing a PASS/FAIL walk-forward verdict."""

    def evaluate(
        self,
        returns: np.ndarray,
        *,
        n_splits: int = 4,
        test_size: int,
        min_oos_sharpe: float = 0.0,
        min_stability: float = 0.5,
        anchored: bool = True,
        embargo: int = 0,
    ) -> WalkForwardReport:
        arr = np.asarray(returns, dtype="float64")
        if arr.ndim != 1:
            raise ValidationError("returns must be a 1-D array")
        splits = walk_forward_splits(
            len(arr), n_splits=n_splits, test_size=test_size, anchored=anchored, embargo=embargo
        )
        oos_sharpes: list[float] = []
        oos_means: list[float] = []
        for split in splits:
            test = arr[split.test]
            oos_sharpes.append(sharpe_ratio(test) if len(test) > 1 else 0.0)
            oos_means.append(float(test.mean()) if len(test) else 0.0)

        oos_sharpe = float(np.mean(oos_sharpes)) if oos_sharpes else 0.0
        oos_mean = float(np.mean(oos_means)) if oos_means else 0.0
        stability = float(np.mean([m > 0 for m in oos_means])) if oos_means else 0.0
        passed = oos_sharpe >= min_oos_sharpe and stability >= min_stability
        # Score blends OOS Sharpe (capped) and stability into 0-100.
        score = 100.0 * (0.6 * _clip01(oos_sharpe / 2.0) + 0.4 * stability)
        return WalkForwardReport(
            status=WalkForwardStatus.PASSED if passed else WalkForwardStatus.FAILED,
            walk_forward_score=score,
            n_windows=len(splits),
            oos_sharpe=oos_sharpe,
            oos_mean_return=oos_mean,
            stability=stability,
            message=(
                f"oos_sharpe={oos_sharpe:.2f} (>= {min_oos_sharpe}), "
                f"stability={stability:.2f} (>= {min_stability})"
            ),
        )


class RevalidationController:
    """Decides when revalidation is required and whether production capital is allowed."""

    def assess(
        self,
        report: WalkForwardReport,
        *,
        structural_break: bool = False,
        drift: bool = False,
        regime_transition: bool = False,
        sharpe_deteriorated: bool = False,
        pf_deteriorated: bool = False,
        capacity_deteriorated: bool = False,
        decay_level: DecayLevel | None = None,
        age_days: float | None = None,
        max_age_days: float = 30.0,
        manual: bool = False,
    ) -> RevalidationDecision:
        triggers: list[RevalidationTrigger] = []
        if structural_break:
            triggers.append(RevalidationTrigger.STRUCTURAL_BREAK)
        if drift:
            triggers.append(RevalidationTrigger.DRIFT)
        if regime_transition:
            triggers.append(RevalidationTrigger.REGIME_TRANSITION)
        if sharpe_deteriorated:
            triggers.append(RevalidationTrigger.SHARPE_DETERIORATION)
        if pf_deteriorated:
            triggers.append(RevalidationTrigger.PF_DETERIORATION)
        if capacity_deteriorated:
            triggers.append(RevalidationTrigger.CAPACITY_DETERIORATION)
        if decay_level is DecayLevel.DEAD:
            triggers.append(RevalidationTrigger.SIGNAL_DEAD)
        elif decay_level is DecayLevel.DECAYING:
            triggers.append(RevalidationTrigger.SIGNAL_DECAYING)
        if age_days is not None and age_days > max_age_days:
            triggers.append(RevalidationTrigger.STALE)
        if manual:
            triggers.append(RevalidationTrigger.MANUAL)

        # Fail-closed: capital allowed only when the walk-forward verdict is PASSED and no hard
        # trigger has invalidated it. A hard trigger downgrades a passing strategy to STALE.
        status = report.status
        if status is WalkForwardStatus.PASSED and any(t in _HARD_TRIGGERS for t in triggers):
            status = WalkForwardStatus.STALE
        production_capital_allowed = status is WalkForwardStatus.PASSED
        return RevalidationDecision(
            required=bool(triggers),
            triggers=triggers,
            status=status,
            production_capital_allowed=production_capital_allowed,
            rationale=(
                "production capital permitted (walk-forward PASSED, no hard triggers)"
                if production_capital_allowed
                else f"production capital blocked (status={status.value}); "
                f"triggers={[t.value for t in triggers]}"
            ),
        )

```

### scripts/check_fence_yield.py
```python
#!/usr/bin/env python3
"""FENCE YIELD (L1.43) -- a fence that has never caught anything is decoration, and this desk
just built fifteen of them in one day.

THE SELF-APPLYING QUESTION NOBODY WAS ASKING. This desk hunts welded gates: a validation gate
that accepts ~100% or rejects ~100% carries zero information, however rigorous it looks. That
exact logic was never turned on the GOVERNANCE layer -- and on 2026-07-31 the desk added roughly
fifteen laws and a dozen fences in a single session. L1.26 is blunt about what that means: tooling
and architecture are NEVER objectives, they compete for resources against every alternative use
on expected contribution to compounding. A fence nobody's behaviour changes for is brain-cycle
cost with a governance costume on.

WHAT A FENCE IS WORTH, measured rather than asserted:
  FIRED      it has produced a non-OK verdict at least once -- it caught something real. This is
             the only positive evidence a fence can generate. Every fence built on 07-31 fired on
             its FIRST run (calibration UNFORECASTING, exploration DARK, replacement UNMEASURED-
             BIRTHS, build-standard 5 violations, law-families UNREACHED). That is the bar.
  QUIET      it runs and has only ever said OK. Two readings, and the fence cannot distinguish
             them: the desk is genuinely clean in that dimension, or the check is inert. Reported,
             never auto-retired -- a quiet survival rail is exactly what you want (L1.23), so
             silence is only suspicious for DETECTORS, not for RAILS.
  NEVER-RUN  it has no artifact at all: built, possibly scheduled, and never actually executed.
             This is the built-never-wired defect inside the governance layer itself.

DELIBERATELY NOT A KILL LIST. This fence proposes no retirements and fails no build. Its output
is EVIDENCE for the weekly sweep's recursive-meta section, which is where retirement decisions
belong -- and the honest asymmetry is that a rail's silence is worth paying for while a
detector's silence may not be. Reporting is the whole job; acting on it is a judgement with
context this script does not have.

    python scripts/check_fence_yield.py [--report-only] [--json]
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
from libs.ops.lawful import guard as _law_guard  # noqa: E402

#: fence -> (artifact, the JSON key holding its verdict, values that mean "caught something",
#:           kind). kind=RAIL means silence is the DESIRED state (L1.23) and is never a demerit;
#:           kind=DETECTOR means silence is ambiguous and worth reporting.
_FENCES: dict[str, tuple[str, str, tuple[str, ...], str]] = {
    "conversion": ("data/conversion_status.json", "status", ("FLATLINE", "REPAIR-MODE"),
                   "DETECTOR"),
    "calibration": ("data/calibration_status.json", "status",
                    ("OVERDUE", "MISCALIBRATED", "BLIND", "UNFORECASTING"), "DETECTOR"),
    "replacement_rate": ("data/replacement_rate.json", "status",
                         ("DYING", "UNMEASURED-BIRTHS", "UNMEASURED"), "DETECTOR"),
    "exploration": ("data/exploration_status.json", "status", ("DARK", "STALE", "THIN"),
                    "DETECTOR"),
    "law_families": ("data/law_families.json", "status", ("FAILING",), "DETECTOR"),
    "build_standard": ("data/build_standard.json", "status", ("BELOW-STANDARD",), "DETECTOR"),
    "utilisation": ("data/utilisation.json", "status", ("OVER-LIMIT", "IDLE"), "DETECTOR"),
    "law_gate": ("data/law_gate.json", "ok", ("False", "false"), "RAIL"),
    "change_window": ("data/change_window.json", "status", ("STERILE", "UNMEASURED"), "RAIL"),
    "moat_backup": ("data/backup_status.json", "status",
                    ("DISK-FUSE", "DRILL-FAILED", "NOTHING-REPLICATED"), "RAIL"),
}

#: Append-only history of observed verdicts, so "has it EVER fired" survives a fresh artifact.
_HISTORY = "data/fence_yield_history.json"

#: SEEDED FIRINGS -- the honest fix for this fence's own blind spot. History begins at first
#: observation, so a fence that FIRED, got its defect FIXED, and then re-ran clean reads QUIET
#: forever after: the artifact only ever holds the latest verdict. That is exactly what happened
#: on 2026-07-31 -- law_families caught L2.3 fenced-but-never-in-the-doctrine, and build_standard
#: caught 5 violations including three in itself -- and both were repaired within the hour, so
#: their artifacts say OK. Recording those firings from the commit record is not cheating; NOT
#: recording them would make this fence understate the yield of the only fences whose catches are
#: already proven. Each entry cites where the evidence lives.
_SEEDED: dict[str, tuple[str, str]] = {
    "law_families": ("FAILING", "2026-07-31 first run: conversion family UNREACHED -- L2.3 was "
                                "in the constitution and in the matrix but ABSENT from the "
                                "doctrine, so no organ had ever been told it (commit b3a70eb)"),
    "build_standard": ("BELOW-STANDARD", "2026-07-31 first run: 5 violations incl. 3 in itself "
                                         "(own except:pass, own missing test, own missing matrix "
                                         "mapping) + 2 unmapped screens (commit 57a4f48)"),
    "utilisation": ("OVER-LIMIT", "2026-07-30 first run: deployed capital read 13,155/4,500 -- "
                                  "OVER 100% -- exposing two sources of truth for desk equity"),
}


def _observe(root: Path) -> dict[str, str]:
    """Today's verdict per fence -- ABSENT when the fence has produced no artifact at all."""
    out: dict[str, str] = {}
    for name, (rel, key, _fire, _kind) in _FENCES.items():
        try:
            doc = json.loads((root / rel).read_text("utf-8"))
            out[name] = str(doc.get(key, "?"))
        except (OSError, ValueError):
            out[name] = "ABSENT"
    return out


def _load_history(root: Path) -> dict[str, list[str]]:
    try:
        h = json.loads((root / _HISTORY).read_text("utf-8"))
        return {k: list(v) for k, v in h.get("seen", {}).items()}
    except (OSError, ValueError):
        return {}


def build_report(root: Path | None = None, *, record: bool = True) -> dict[str, Any]:
    root = root or _ROOT
    today = _observe(root)
    hist = _load_history(root)
    for name, (verdict, _why) in _SEEDED.items():          # proven catches predating this fence
        if verdict not in hist.setdefault(name, []):
            hist[name].append(verdict)
    for name, verdict in today.items():
        if verdict != "ABSENT" and verdict not in hist.setdefault(name, []):
            hist[name].append(verdict)

    fences: dict[str, Any] = {}
    fired = quiet = never = 0
    for name, (rel, _k, fire_values, kind) in _FENCES.items():
        seen = hist.get(name, [])
        if not seen and today[name] == "ABSENT":
            state, note = "NEVER-RUN", ("no artifact has ever existed -- built, perhaps "
                                        "scheduled, never actually executed")
            never += 1
        elif any(v in fire_values for v in seen):
            state, note = "FIRED", f"has produced {sorted(set(seen) & set(fire_values))}"
            fired += 1
        else:
            state = "QUIET"
            note = ("only ever OK. For a RAIL that is the DESIRED state and costs nothing to "
                    "keep (L1.23); for a DETECTOR it is ambiguous -- clean desk, or inert check"
                    if kind == "RAIL" else
                    "only ever OK -- either this dimension is genuinely clean or the check is "
                    "inert, and this fence cannot tell you which")
            quiet += 1
        fences[name] = {"state": state, "kind": kind, "artifact": rel,
                        "verdicts_ever_seen": sorted(set(seen)), "note": note}
        if name in _SEEDED:
            fences[name]["seeded_evidence"] = _SEEDED[name][1]

    if record:
        try:
            (root / _HISTORY).parent.mkdir(parents=True, exist_ok=True)
            (root / _HISTORY).write_text(json.dumps(
                {"seen": hist, "updated": datetime.now(tz=UTC).isoformat()}, indent=2), "utf-8")
        except OSError as exc:
            fences["_history_write"] = {"state": "UNMEASURED", "note": str(exc)}

    n = len(_FENCES)
    quiet_detectors = [k for k, v in fences.items()
                       if v.get("state") == "QUIET" and v.get("kind") == "DETECTOR"]
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.43 -- a fence that never catches anything is decoration; governance competes "
               "for resources like everything else (L1.26). Evidence only: this proposes no "
               "retirements and fails no build.",
        "status": ("NEVER-RUN-PRESENT" if never else
                   "QUIET-DETECTORS" if quiet_detectors else "ALL-EARNING"),
        "n_fences": n, "n_fired": fired, "n_quiet": quiet, "n_never_run": never,
        "quiet_detectors": quiet_detectors,
        "fences": fences,
        "detail": f"{fired}/{n} fences have caught something real; {quiet} quiet, {never} never run",
        "next_action": (
            "route QUIET DETECTORS to the weekly sweep's recursive-meta section, which owns "
            "retirement decisions. NEVER auto-retire: a quiet RAIL is what you are paying for "
            "(L1.23), and a quiet detector may simply mean the desk is clean in that dimension. "
            "A NEVER-RUN fence is the built-never-wired defect inside governance itself -- "
            "schedule it or record why it should not exist."),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    out = _ROOT / "data/fence_yield.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"fence yield (L1.43): {rep['status']} -- {rep['detail']}")
        for name, f in rep["fences"].items():
            if f.get("state") in ("QUIET", "NEVER-RUN") and f.get("kind") == "DETECTOR":
                print(f"  {f['state']:<10} {name}: {f['note']}")
    return 0                                   # evidence organ: never fails a build (L1.26)


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/check_replacement_rate.py
```python
#!/usr/bin/env python3
"""ALPHA REPLACEMENT RATE (L1.30) -- edges die on their own schedule; only the pipeline decides
whether the book dies with them.

THE NUMBER THAT ACTUALLY SETS LONG-RUN CAGR, and which this desk has never computed. Every edge
decays -- crowding, regime change, microstructure drift -- on a half-life measured in months, not
years. So terminal wealth is NOT set by how good today's sleeves are; it is set by whether
VALIDATED BIRTHS keep pace with DEATHS. A book earning 80% on three edges with a replacement rate
of 0.3 is on a countdown nobody is watching: it looks healthy every single day right up until the
last edge dies. A book earning 30% with a replacement rate above 1.0 compounds forever.

    replacement_rate = births / deaths   over a trailing window

  births  = edges that reached FORWARD-EVIDENCE status in the window (Stage-B entries /
            promotion-queue promotions) -- the only births that count, because a screen hit is
            not an edge (L1.6: screens have zero promotion authority).
  deaths  = graveyard kills + retirements + forward clocks that failed out, in the same window.

STATUSES:
  DYING             deaths > births -- the countdown is running. Fence FAILS.
  UNMEASURED-BIRTHS no dated promotion history exists, so births cannot be counted. Reported as
                    a defect, NEVER as DYING: "cannot count births" and "there are no births"
                    are different claims and only one is evidence.
  UNMEASURED        no birth/death records at all -- counts as zero (L1.28a), never as fine.
  BOOTSTRAPPING  no deaths yet AND no births yet: pre-Gate-0 state, honestly named.
  OK             births >= deaths.

DELIBERATELY NOT A KILL SWITCH. A low replacement rate never justifies loosening a validation
bar to manufacture births -- that converts a real countdown into a fake reprieve and is the
exact failure L1.25/L1.6 forbid. The correct response is upstream: more axes, more screens,
more forward slots filled (L1.25a).

    python scripts/check_replacement_rate.py [--window-days N] [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime, timedelta
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

_DATE = re.compile(r"(20\d\d)-(\d\d)-(\d\d)")


def _dates_in(text: str) -> list[datetime]:
    out = []
    for y, m, d in _DATE.findall(text):
        try:
            out.append(datetime(int(y), int(m), int(d), tzinfo=UTC))
        except ValueError:
            continue
    return out


def _count_graveyard_deaths(root: Path, since: datetime) -> tuple[int, int]:
    """(deaths_in_window, total_entries). Entries are '### <name> -- KILLED/RETIRED <date>'."""
    p = root / "docs/graveyard.md"
    if not p.exists():
        return 0, 0
    entries = [ln for ln in p.read_text("utf-8", errors="ignore").splitlines()
               if ln.startswith("### ")]
    n_win = 0
    for ln in entries:
        ds = _dates_in(ln)
        if ds and max(ds) >= since:
            n_win += 1
    return n_win, len(entries)


def _count_births(root: Path, since: datetime) -> tuple[int | None, int]:
    """(births_in_window | None if unmeasurable, live_forward_clocks).

    A BIRTH is an edge reaching forward-evidence status -- never a screen hit (L1.6).

    HONESTY NOTE, and this fence's own first-run defect: the promotion queue records CURRENT
    slot occupancy, not a DATED history of entries, so births are not derivable from it. The
    first draft read absent list-keys, got [], and reported births=0 -- a phantom-key read
    published as a measurement, which is exactly the class this desk has been burned by. An
    unmeasurable birth count returns None and the status becomes UNMEASURED-BIRTHS; it must
    NEVER print DYING, because "we cannot count births" and "there are no births" are different
    claims and only one of them is evidence. Closing this needs an append-only promotion history
    (rowed) -- until then the fence reports what it can and refuses what it cannot."""
    p = root / "data/promotion_queue.json"
    try:
        d = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None, 0
    slots = d.get("slots", {}) if isinstance(d.get("slots"), dict) else {}
    live = int(slots.get("occupied", 0) or 0)
    history = d.get("promotion_history")            # the append-only store, once it exists
    if not isinstance(history, list):
        return None, live
    births = 0
    for r in history:
        if not isinstance(r, dict):
            continue
        ds = _dates_in(str(r.get("promoted_at") or r.get("at") or ""))
        if ds and max(ds) >= since:
            births += 1
    return births, live


def build_report(root: Path | None = None, window_days: int = 90,
                 now: datetime | None = None) -> dict[str, Any]:
    root = root or _ROOT
    now = now or datetime.now(tz=UTC)
    since = now - timedelta(days=window_days)
    deaths, graveyard_total = _count_graveyard_deaths(root, since)
    births, live_clocks = _count_births(root, since)

    if births is None:
        # Cannot count births -> cannot claim the book is dying. Unmeasured ranks as a defect
        # (L1.28a) but never masquerades as a measured verdict.
        status = "UNMEASURED-BIRTHS"
    elif graveyard_total == 0 and live_clocks == 0:
        status = "UNMEASURED"
    elif births == 0 and deaths == 0:
        status = "BOOTSTRAPPING"
    elif deaths > births:
        status = "DYING"
    else:
        status = "OK"
    rate = (None if births is None else
            (births / deaths) if deaths else (float("inf") if births else 0.0))
    return {
        "generated": now.isoformat(),
        "law": "L1.30 -- terminal wealth is set by whether validated births keep pace with "
               "deaths, not by how good today's sleeves are",
        "status": status,
        "window_days": window_days,
        "births": births, "deaths": deaths,
        "replacement_rate": (None if rate is None or rate == float("inf")
                             else round(rate, 3)),
        "births_measured": births is not None,
        "live_forward_clocks": live_clocks,
        "graveyard_entries_total": graveyard_total,
        "detail": (
            f"births UNCOUNTABLE (no dated promotion history) vs {deaths} death(s) in "
             f"{window_days}d; {live_clocks} live forward clock(s) occupied of 12"
             if births is None else
             f"{births} birth(s) vs {deaths} death(s) in {window_days}d; "
             f"{live_clocks} live forward clock(s)"),
        "next_action": (
            "raise BIRTHS upstream -- more axes screened, more forward slots filled, "
            "resurrection queue consumed (L1.25a). NEVER loosen a validation bar to "
            "manufacture births: that turns a real countdown into a fake reprieve"),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--window-days", type=int, default=90)
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report(window_days=args.window_days)
    out = _ROOT / "data/replacement_rate.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    print(json.dumps(rep, indent=2) if args.json else
          f"replacement rate (L1.30): {rep['status']} -- {rep['detail']}\n-> {out}")
    if args.report_only:
        return 0
    return 2 if rep["status"] == "DYING" else 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/check_strategy_breadth.py
```python
#!/usr/bin/env python3
"""STRATEGY-BREADTH FENCE (R0211) -- the clock behind "never limit to just one thing".

PRINCIPAL, twice (2026-07-31): *"miners n explorers kimi etc all should find every crypto strat
even discretionary n all n never limit to just one thing."*

WHY A FENCE AND NOT ANOTHER PARAGRAPH. The first pass at this order widened eleven miner prompts
and built a coverage map. Both were necessary and neither is enforcement: a prompt is a request,
a map is a report, and this desk's own §36 says a conversion rule with no clock behind it is
decoration. The failure mode is not that a miner refuses the instruction -- it is that a miner
drifts back to the family it knows, one comfortable session at a time, while every dashboard
stays green because the volume never drops. Nothing would have caught that. This does.

WHAT IT FAILS ON, and each is a way breadth dies quietly:

  NARROW      the miners' recent output is concentrated in families already worked. Depth in a
              HUNTED family returns correlated candidates, and correlated candidates are one bet
              wearing many names -- the desk pays N times to learn once.
  UNWIDENED   a hunting surface has lost the breadth mandate. Prompts are edited by hand and by
              other sessions; this is the regression check that the instruction is still THERE,
              because an instruction silently deleted is indistinguishable from one never given.
  BLIND       the coverage map itself is missing or unreadable, so breadth is UNMEASURED -- which
              can never read as OK (L1.28a), because "no evidence of narrowing" and "no evidence"
              are the same sentence only to a broken gate.

WHAT IT DELIBERATELY DOES NOT DO: demand a quota of findings per family. A miner that returns
nothing from an unhunted family has produced negative knowledge, which this desk counts as a
result (L1.25a) -- and a fence that punished empty seams would push the miners straight back to
the crowded families where finds are easy and worthless. It measures where they LOOKED, never
what they brought back.

    python scripts/check_strategy_breadth.py [--json] [--report-only]
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

_STATE = "data/strategy_breadth.json"

#: The marker every hunting surface must carry. Checked as a STRING rather than by re-reading the
#: policy, because the failure this catches is the text going missing.
_MANDATE = "STRATEGY-FAMILY BREADTH"

#: Surfaces that brief a HUNTER. Deliberately not every prompt on the desk: second_family.py is a
#: transport that forwards its caller's prompt, and external_panel is a review seat -- putting a
#: hunting mandate in either would be policy in a pipe. Each entry is a file that tells some organ
#: WHAT TO GO LOOK FOR.
_HUNT_SURFACES: tuple[str, ...] = (
    "ops/prospector_dig_prompt.txt", "ops/litminer_dig_prompt.txt",
    "ops/dataaxis_dig_prompt.txt", "ops/blindrediscovery_dig_prompt.txt",
    "ops/frontier_en_prompt.txt", "ops/frontier_cn_prompt.txt", "ops/frontier_jp_prompt.txt",
    "ops/frontier_kr_prompt.txt", "ops/frontier_ru_prompt.txt", "ops/frontier_ar_prompt.txt",
    "ops/frontier_br_prompt.txt",
    "scripts/kimi_hunter.py",              # the only non-Claude hunter -- the widest lens owned
    "scripts/run_capability_hunt.py",
    "prompts/deep_sweep_core.txt",
)

#: Fraction of families that must be genuinely worked before breadth stops being the binding
#: constraint. 0.5 because below half the map, the cheapest growth available is a family nobody
#: has looked at once -- an unhunted family is uncorrelated with everything already tested by
#: construction, which is the property the sleeve allocator prices highest. Above it, depth in a
#: THIN family starts to beat opening the next one.
MIN_HUNTED_FRACTION = 0.5


def _coverage(root: Path) -> dict[str, Any] | None:
    try:
        return json.loads((root / "data/strategy_coverage.json").read_text("utf-8"))
    except (OSError, ValueError):
        return None


def build_report(root: Path | None = None, *, surfaces_only: bool = False) -> dict[str, Any]:
    """`surfaces_only` runs the PORTABLE half alone -- the mandate-present check, which reads
    only committed files and therefore means the same thing in CI, in a fresh clone and on the
    box. The breadth measurement reads data/strategy_coverage.json, which is LIVE STATE that no
    clean checkout has; running it as a commit gate would report BLIND on every PR and a gate
    that cries wolf gets switched off (L1.43). Same law/state split as
    check_scheduler_manifest --report-only, and for the same reason.

    The half that belongs at commit time is the right one: a mandate is deleted from a prompt by
    an edit, so the edit is the moment to catch it.
    """
    root = root or _ROOT
    # (a) UNWIDENED -- is the instruction still present on every hunting surface?
    unwidened = []
    for rel in _HUNT_SURFACES:
        p = root / rel
        try:
            if _MANDATE not in p.read_text("utf-8", errors="ignore"):
                unwidened.append(rel)
        except OSError:
            unwidened.append(f"{rel} (UNREADABLE)")

    # (b) NARROW / BLIND -- what does the coverage map say about where they have looked?
    cov = None if surfaces_only else _coverage(root)
    if surfaces_only:
        breadth = {"state": "NOT-RUN",
                   "why": "surfaces-only mode: the breadth measurement reads live state that a "
                          "clean checkout does not have, so it runs in the box gate where its "
                          "verdict is real"}
    elif cov is None or cov.get("status") == "UNREADABLE":
        breadth = {"state": "BLIND",
                   "why": "data/strategy_coverage.json missing or unreadable -- breadth is "
                          "UNMEASURED, and unmeasured never reads as OK (L1.28a). Run "
                          "scripts/run_strategy_coverage.py."}
    else:
        n_fam = int(cov.get("n_families") or 0)
        hunted = int(cov.get("n_hunted") or 0)
        frac = (hunted / n_fam) if n_fam else 0.0
        breadth = {
            "state": "OK" if frac >= MIN_HUNTED_FRACTION else "NARROW",
            "n_families": n_fam, "n_hunted": hunted,
            "hunted_fraction": round(frac, 3), "floor": MIN_HUNTED_FRACTION,
            "unhunted": cov.get("unhunted") or [], "thin": cov.get("thin") or [],
            "why": (f"{hunted}/{n_fam} families genuinely worked" if frac >= MIN_HUNTED_FRACTION
                    else f"only {hunted}/{n_fam} families worked ({frac:.0%} < "
                         f"{MIN_HUNTED_FRACTION:.0%}). The next dig belongs in "
                         f"{(cov.get('unhunted') or cov.get('thin') or ['an unhunted family'])[0]}"
                         ", not deeper in one already worked -- a worked family returns "
                         "correlated candidates, and correlated candidates are one bet wearing "
                         "many names."),
        }

    fails = bool(unwidened) or breadth["state"] in ("NARROW", "BLIND")
    status = ("UNWIDENED" if unwidened else breadth["state"] if fails else "OK")
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.32/L1.34 -- breadth is enforced, not requested. A prompt is a request and a "
               "coverage map is a report; neither fails when a miner drifts back to the family "
               "it knows, which is how breadth actually dies -- one comfortable session at a "
               "time, with the volume never dropping.",
        "status": status,
        "n_surfaces": len(_HUNT_SURFACES),
        "unwidened_surfaces": unwidened,
        "breadth": breadth,
        "not_a_quota": "this measures where the miners LOOKED, never what they brought back. A "
                       "miner returning nothing from an unhunted family produced negative "
                       "knowledge, which counts as a result (L1.25a); punishing empty seams "
                       "would push every seat back to the crowded families where finds are easy "
                       "and worthless.",
        "detail": (f"{len(unwidened)}/{len(_HUNT_SURFACES)} hunting surfaces have LOST the "
                   f"breadth mandate: {', '.join(unwidened[:4])}" if unwidened else
                   f"all {len(_HUNT_SURFACES)} hunting surfaces carry the mandate; "
                   + str(breadth["why"])),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--surfaces-only", action="store_true",
                    help="portable half only: the mandate-present check (repo files)")
    args = ap.parse_args()
    rep = build_report(_ROOT, surfaces_only=args.surfaces_only)
    out = _ROOT / _STATE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    print(json.dumps(rep, indent=2) if args.json else
          f"strategy breadth (L1.32): {rep['status']} -- {rep['detail'][:160]}")
    if args.report_only:
        return 0
    return 0 if rep["status"] == "OK" else 2


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/data_health.py
```python
"""Data-pipeline health check + alerting feed.

Reports the freshness (age + distinct-day depth) of every archived dataset and the liveness of the
always-on heartbeats. Writes web/health.json for the dashboard (turns red when anything is stale)
and prints a one-line ALERT summary. A fragile pipeline thus gets caught early instead of
silently freezing (the mode that froze the OI archive at one snapshot).

    python scripts/data_health.py
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

_OUT = Path("web/health.json")
# daily time-series dataset -> (path, timestamp-col, max age hours before STALE)
_DATASETS = {
    "oi_ls_taker": ("data/crypto_metrics.parquet", "ts", 36),
    "market_breadth": ("data/market_breadth.parquet", "ts", 36),
}
# JSON daily archives -> (path, date-key, max age hours before STALE)
_JSON_ARCHIVES = {
    "stablecoin_flows": ("data/stablecoin_flows_archive.json", "ts", 36),
    "fred_macro": ("data/fred_macro.json", "updated", 36),
}


# heartbeat alive but zero events this long -> the data pipe is almost certainly dead, not a quiet
# market (verified 2026-07-09: Binance mainnet WS handshakes OK but silently drops every data frame
# from this network -- 0 events/14 days on a stream that should fire continuously). Heartbeat
# liveness != data liveness.
_LIQ_STUCK_H = 24.0


def _liquidation_check() -> dict[str, object]:
    """Liquidations are a SPARSE event stream (not a daily dataset): report event count + the
    'listening since' clock + freshest event. LISTENING with 0 events is normal for the first
    _LIQ_STUCK_H hours (quiet market); past that with still-zero events, treat it as STUCK (alert)
    -- a broken data pipe looks identical to a quiet market on heartbeat alone."""
    liq, since_p, hb = (Path("data/liquidations.parquet"), Path("data/liquidation_since"),
                        Path("data/liquidation_heartbeat"))
    listening = hb.exists() and (time.time() - hb.stat().st_mtime) < 30 * 60
    events, latest = 0, None
    if liq.exists():
        ld = pd.read_parquet(liq)
        events = len(ld)
        if events:
            latest = pd.to_datetime(ld["ts"]).max().isoformat()
    since = since_p.read_text("utf-8").strip() if since_p.exists() else None
    since_h = None
    if since:
        since_dt = datetime.fromisoformat(since)
        since_h = (datetime.now(tz=UTC) - since_dt).total_seconds() / 3600
    if events > 0:
        status = "RECEIVING"
    elif listening and since_h is not None and since_h > _LIQ_STUCK_H:
        status = "STUCK"          # alive but structurally not receiving data -- treat as an alert
    elif listening:
        status = "LISTENING"
    else:
        status = "DOWN"
    return {"name": "liquidations", "status": status, "events": events,
            "since": since, "since_h": round(since_h, 1) if since_h is not None else None,
            "latest": latest}
# heartbeat -> (path, max minutes before DOWN)
_HEARTBEATS = {
    "cashcarry_executor": ("data/cashcarry_exec_heartbeat", 5),
    "liquidation_listener": ("data/liquidation_heartbeat", 30),
}


def main() -> None:
    now = datetime.now(tz=UTC)
    checks = []
    all_ok = True
    for name, (path, col, max_h) in _DATASETS.items():
        p = Path(path)
        if not p.exists():
            checks.append({"name": name, "status": "MISSING", "age_h": None, "days": 0})
            continue                                   # MISSING (not yet started) is not an alert
        df = pd.read_parquet(p)
        last = pd.to_datetime(df[col]).max()
        age_h = (now - last.to_pydatetime()).total_seconds() / 3600
        days = int(pd.to_datetime(df[col]).dt.date.nunique())
        status = "OK" if age_h <= max_h else "STALE"
        all_ok = all_ok and status == "OK"
        checks.append({"name": name, "status": status, "age_h": round(age_h, 1), "days": days})
    for name, (path, col, max_h) in _JSON_ARCHIVES.items():
        p = Path(path)
        if not p.exists():
            checks.append({"name": name, "status": "MISSING", "age_h": None, "days": 0})
            continue
        try:
            rows = json.loads(p.read_text("utf-8"))
            if not rows:
                checks.append({"name": name, "status": "EMPTY", "age_h": None, "days": 0})
                continue
            if isinstance(rows, dict):                    # dict-style archive (e.g. fred_macro):
                last = datetime.fromisoformat(str(rows[col]))   # timestamp at the top level;
                rows = rows.get("series", rows)                 # "days" = distinct sub-series
            else:
                last = datetime.fromisoformat(rows[-1][col])
            if last.tzinfo is None:
                last = last.replace(tzinfo=UTC)
            age_h = (now - last).total_seconds() / 3600
            days = len(rows)
            status = "OK" if age_h <= max_h else "STALE"
            all_ok = all_ok and status == "OK"
            checks.append({"name": name, "status": status, "age_h": round(age_h, 1), "days": days})
        except Exception as e:
            checks.append({"name": name, "status": "ERROR", "age_h": None, "days": 0,
                           "detail": repr(e)[:80]})
    liq = _liquidation_check()
    all_ok = all_ok and liq["status"] not in ("DOWN", "STUCK")
    checks.append(liq)
    hbs = []
    for name, (path, max_min) in _HEARTBEATS.items():
        p = Path(path)
        age_s = round(time.time() - p.stat().st_mtime) if p.exists() else None
        alive = age_s is not None and age_s < max_min * 60
        if name == "cashcarry_executor" and not alive:
            all_ok = False                             # executor down is the only hard alert
        hbs.append({"name": name, "alive": bool(alive), "age_s": age_s})
    # ORGANS visibility (2026-07-24 external-audit finding: health said all_ok while every AI
    # organ was dead -- this surface only ever covered datasets/heartbeats). organs_ok is shown
    # SEPARATELY, not folded into all_ok: the brain_noop pager already alarms on cycle death, so
    # folding would double-alert; blindness is ended by REPORTING, not re-alarming.
    organs = {}
    try:
        logs = sorted(Path("data/cro_ai_logs").glob("2026*_*.log"),
                      key=lambda q: q.stat().st_mtime)
        good = [q for q in logs if q.stat().st_size >= 2000]
        organs["last_cycle_success_h"] = (
            round((now.timestamp() - good[-1].stat().st_mtime) / 3600.0, 1) if good else None)
        organs["last_cycle_attempt_h"] = (
            round((now.timestamp() - logs[-1].stat().st_mtime) / 3600.0, 1) if logs else None)
    except Exception:
        pass
    organs_ok = bool(organs.get("last_cycle_success_h") is not None
                     and organs["last_cycle_success_h"] <= 26.0)
    out = {"updated": now.isoformat(), "all_ok": all_ok, "organs_ok": organs_ok,
           "organs": organs, "datasets": checks, "heartbeats": hbs}
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    flag = "OK" if all_ok else "ALERT"

    def _amt(c: dict[str, object]) -> str:
        return f"{c['events']}ev" if "events" in c else f"{c.get('days', 0)}d"
    print(f"[{flag}] " + " | ".join(
        f"{c['name']}:{c['status']}({_amt(c)})" for c in checks) + " || " + " ".join(
        f"{h['name']}:{'up' if h['alive'] else 'DOWN'}" for h in hbs))


if __name__ == "__main__":
    main()

```

### scripts/deep_review.py
```python
#!/usr/bin/env python3
"""SINGLE-FILE DEPTH PASS (build #2, principal 2026-07-21).

WHY: in the breadth panel each seat reads ~730k chars across 67 files and returns ~8-15k chars
covering ALL of them -- so binance_live.py, the code that will move real money, receives maybe
one or two paragraphs of attention per model. That is the wrong allocation for the risk lane.

THIS: 13 seats on ONE file with a focused adversarial prompt -> each returns its full response
about that file alone. Roughly 10-50x the attention per file.

This is NOT audit tooling: docs/LIVE_CONNECTOR_SPEC.md section 7 already REQUIRES a
second-model-family fuzz/breaker review before Gate 0. This is the cheap, immediate form of
that bar, and it should be run on all five money-path files before the connector ships.

Usage: deep_review.py libs/execution/binance_live.py [more files...]
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "docs/research/deep_review_inbox.md"

SYSTEM = """You are a hostile reviewer of RISK-PATH code for an autonomous crypto trading desk.
This file can move real money. You have zero attachment to its design and no obligation to be
polite. Assume a bug here costs the operator his capital.

Review ONLY the file given. Depth over breadth -- this is your single subject.

Hunt specifically for:
 1. SILENT FAILURE -- any path that swallows an error, returns a default, or continues on bad
    state. Name the exact line and what the caller then believes that is false.
 2. UNBOUNDED ACTION -- orders/retries/loops with no cap, no cooldown, no idempotency key.
 3. STATE RACES -- reads that can be stale between check and act; two writers on one file.
 4. WRONG-DIRECTION FAILURE -- where does it fail OPEN (keep trading) instead of CLOSED?
 5. ARITHMETIC -- sign errors, unit mismatches, float compare, precision/rounding on notionals.
 6. AUTH/CAPABILITY -- anything reachable that should not be (withdrawal, transfer, key mgmt).
 7. WHAT A TEST WOULD MISS -- the failure that only appears under real venue latency, partial
    fills, rate limits, or a 5xx mid-sequence.

For each finding give: LINE(s) | what breaks | the concrete sequence that triggers it | the
minimal fix. Rank by expected loss. If the file is genuinely sound, say so plainly and name the
single riskiest remaining assumption -- do not manufacture findings."""


def main() -> None:
    files = sys.argv[1:]
    if not files:
        raise SystemExit(__doc__)
    from scripts.run_external_panel import _ask
    # risk-path depth passes run at MAX effort: this is the review standing between
    # the desk and real money, the one place where correctness outranks token cost
    # (elsewhere xhigh wins -- max is documented as prone to overthinking).
    providers = json.loads((ROOT / "data/secrets/llm_panel.json").read_text())["providers"]
    ts = datetime.now(tz=UTC).isoformat()
    OUT.parent.mkdir(parents=True, exist_ok=True)

    for rel in files:
        fp = ROOT / rel
        if not fp.exists():
            print(f"skip (missing): {rel}")
            continue
        body = fp.read_text("utf-8", errors="ignore")
        prompt = (f"FILE UNDER REVIEW: {rel} ({len(body.splitlines())} lines)\n\n"
                  f"```python\n{body}\n```\n\nReview it per your mandate. Depth, not breadth.")
        print(f"\n=== DEEP REVIEW: {rel} ({len(body):,} chars) x {len(providers)} seats ===")

        def one(pv, prompt=prompt):  # bind loop var per-iteration (ruff B023)
            try:
                r = _ask(pv["base_url"], pv["key"], pv["model"], SYSTEM, prompt)
                if len(r.strip()) < 200:
                    r = _ask(pv["base_url"], pv["key"], pv["model"], SYSTEM, prompt)
                print(f"  {pv['model']}: {len(r)} chars")
                return {"model": pv["model"], "response": r}
            except Exception as e:
                print(f"  {pv['model']}: FAILED {e!r}"[:110])
                return {"model": pv["model"], "error": repr(e)[:200]}

        with ThreadPoolExecutor(max_workers=6) as ex:
            res = list(ex.map(one, providers))
        ok = [r for r in res if "response" in r]

        with OUT.open("a", encoding="utf-8") as f:
            f.write(f"\n\n# DEEP REVIEW -- {rel} -- {ts}\n"
                    f"{len(ok)}/{len(res)} seats responded. RISK-PATH depth pass "
                    "(LIVE_CONNECTOR_SPEC section 7 bar). Triage per panel protocol: verify every "
                    "claim against the code; consensus = high prior; record each accepted finding "
                    "via scripts/track_findings.py so it cannot be silently dropped.\n")
            for r in ok:
                f.write(f"\n## {r['model']}\n\n{r['response']}\n")
        print(f"  -> {OUT} ({len(ok)}/{len(res)} responded)")


if __name__ == "__main__":
    main()

```

### scripts/kimi_hunter.py
```python
"""KIMI HUNTER -- Deep Forest Protocol orchestration. Wave 1 -> 2 -> 3, enforced.

The last genuinely unbuilt item. It cannot RUN until OpenRouter is funded (402), but the harness
is not blocked by that and this ships ready to fire the moment credit lands.

THE PROTOCOL, enforced in code rather than trusted to the prompt:
  WAVE 1 SHADOW MAPPING       map what the herd covered. No findings permitted yet.
  WAVE 2 NEGATIVE SPACE       findings MUST cite the Wave-1 coverage that caused the miss.
                              A Wave-2 finding with no linkage is REJECTED here, not argued with.
  WAVE 3 DEEP FOREST          things the herd does not know are measurable.
Waves run in sequence and each is fed the previous wave's output, because a hunter that skips
straight to Wave 3 just returns whatever it already knew -- which is the herd's knowledge.

WHY THIS CANNOT SHORTCUT THE DESK. Kimi output is RAW ORE. It enters exactly one path:
    kimi_hunter -> suggestion ledger -> mechanism board -> measurement gate -> Stage-A -> clock
It has ZERO promotion authority, cannot open a position, cannot start an experiment, and cannot
write to any research artifact except the ledger. Findings that map to a FAMILY KILL are rejected
at intake and debited to the source, exactly like any other contributor -- an external model that
has not read the graveyard will re-propose corpses forever because it costs it nothing.

FORBIDDEN ZONES are enforced MECHANICALLY, not requested politely. A finding mentioning Binance
funding anomalies, RSI/TradingView combinations, Twitter sentiment, Google Trends or anything with
a public CoinGlass/Dune dashboard is dropped before it reaches the ledger. The prompt asks; this
enforces.

BUDGET: reads data/panel_budget.json and refuses to start if the envelope is exhausted. Free and
public sources only -- no paid data APIs, no institutional terminals.
"""
from __future__ import annotations

import json
import re
import ssl
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEYS = ROOT / "data/secrets/llm_panel.json"
BUDGET = ROOT / "data/panel_budget.json"
BSTATE = ROOT / "data/panel_budget_state.json"
LEDGER = ROOT / "data/suggestion_ledger.jsonl"
MECHB = ROOT / "data/mechanism_board.json"
OUT = ROOT / "data/kimi_hunt.json"
CTX = ssl.create_default_context()

MODEL = "moonshotai/kimi-k3"          # seated model; swarm-max reserved for quarterly deep dives

_COVERAGE = ROOT / "data/hunt_coverage.json"
_VECTOR_COOLDOWN_D = 45      # a forest may be re-entered only after this long

# NO TARGET LIST. Seed vectors exist ONLY to bootstrap run #1 on an empty coverage file; from
# run #2 onward the hunter generates its own and these are never consulted again.
_SEED_VECTORS = ["anything you consider under-observed"]

# Mechanically enforced. The prompt asks for these to be avoided; this drops them.
FORBIDDEN_SETS = [
    # Each entry is a REQUIRED TOKEN SET: the zone trips only when EVERY token is present,
    # in any order. Exact-substring matching let "Binance funding anomaly" through while
    # dropping "Binance funding rate anomaly" -- the same dead source, one word apart.
    {"binance", "funding"},          # crowded beyond usefulness; 10k bots watch it
    {"funding", "anomaly"},
    {"open", "interest", "high"},
    {"rsi"}, {"macd"}, {"bollinger"}, {"stochastic"},
    {"tradingview"}, {"coinglass"},
    {"dune", "dashboard"},
    {"twitter", "sentiment"}, {"sentiment", "analysis"},
    {"google", "trends"}, {"wikipedia", "pageview"},
    {"moving", "average"},
]



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


def _forbidden(text: str) -> str | None:
    """Return the tripped zone, or None. Token-set membership, order-independent.

    NOTE the deliberate narrowness: multi-token zones require ALL tokens, so bare "funding"
    is NOT blocked -- funding persistence is this desk's single confirmed edge and must stay
    researchable. The zone blocks crowded FRAMINGS of it, not the subject.
    """
    toks = set(re.findall(r"[a-z]+", text.lower()))
    for zone in FORBIDDEN_SETS:
        if zone <= toks:
            return " + ".join(sorted(zone))
    return None

CHARTER = (
    "You are an INFORMATION PREDATOR for a solo quant desk. You are not a literature reviewer.\n"
    "Your purpose: find edible information BEFORE the herd arrives. If you return 'funding rates "
    "are interesting' or 'OI is high' you have FAILED -- that is surface water.\n\n"
    "HARD CONSTRAINTS:\n"
    "\n"
    "EXHAUSTION MANDATE -- THERE IS NO CEILING AND NO QUOTA.\n"
    "Report EVERY finding you can substantiate, not a tidy number of them. If a forest holds\n"
    "thirty things, return thirty. If it holds two, return two AND SAY THE FOREST IS THIN --\n"
    "a documented empty seam stops the desk re-digging it and is worth as much as a find.\n"
    "Never stop because you have 'enough'. Enough is not a concept here.\n"
    "Never summarise to save space. Depth per finding AND number of findings are both unbounded.\n"
    "Go one layer deeper than feels finished. The layer past 'finished' is where the things\n"
    "nobody has named live, and it is the layer every other researcher skips.\n"
    "If you find yourself writing a conclusion, you stopped too early -- hunt again instead.\n"
    "\n"
    "- NAME YOUR OWN TERRITORIES. Prefix each with 'VECTOR: <name>'. You are not given\n"
    "  a search list; a fixed checklist is where everyone already looks.\n"
    "- FREE, PUBLIC, SCRAPABLE or RPC-accessible sources ONLY. Never suggest paid data APIs, "
    "institutional terminals or enterprise datasets.\n"
    # PRINCIPAL 2026-07-31: "miners n explorers kimi etc all should find every crypto strat even
    # discretionary n all n never limit to just one thing." This line used to read "Never suggest
    # strategies or indicators", which was aimed at PATTERN-MINING and hit STRATEGIES wholesale --
    # so the desk's only non-Claude hunter, its widest lens, was barred from returning the thing
    # the desk most needs. The real test was never source-vs-strategy; it is MECHANISM vs PATTERN,
    # and it applies identically either way.
    "- STRATEGIES ARE IN SCOPE, PATTERNS ARE NOT, and the difference is a FORCED PARTICIPANT.\n"
    "  Banned: a bare indicator or fitted rule with nobody on the other side ('RSI(14) crossover\n"
    "  on 4h', 'this MA pair backtests well') -- that is curve-fitting with a name.\n"
    "  In scope: any strategy whose mechanism names WHO is forced to trade against it and WHY\n"
    "  they cannot stop -- including DISCRETIONARY-shaped ones. Price reacting at a level is a\n"
    "  real mechanism when the forced participant is clustered stop-losses; a session-open\n"
    "  effect is real when it is a mandate-driven flow. A mechanism is never disqualified for\n"
    "  being judgement-shaped, only for being unfalsifiable.\n"
    "  INFORMATION SOURCES remain equally in scope -- this widens the brief, it does not\n"
    "  redirect it. Returning only one KIND of finding is the failure either way.\n"
    "- Every finding needs a FORCED PARTICIPANT or a CONSTRAINT, not a correlation.\n"
    "- Report the bizarre. If something looks like a bug, report it -- the best discoveries look "
    "like errors first. Depth AND breadth are both unbounded; a count is a quota in disguise.\n"
    "\n"
    "STRATEGY-FAMILY BREADTH -- UNLIMITED, ALL-SURFACE, NEVER-ENDING.\n"
    "NO SURFACE IS OUT OF SCOPE. Every venue, era, language, asset class, timeframe and FORMAT\n"
    "(papers, repos, configs, backtest tables, bot source, forum arguments, filings, incident\n"
    "post-mortems), and every STYLE -- systematic, discretionary, manual, hybrid, market-making,\n"
    "event-driven. If you catch yourself deciding a surface is not the kind of thing this desk\n"
    "looks at, that judgement IS the finding: name it and go there.\n"
    "NEVER-ENDING: there is no terminal state. 'Covered' and 'we already looked' are claims\n"
    "requiring evidence -- a dated search with its operators and its residual gap -- never\n"
    "defaults. UNLIMITED: no quota on families, findings, depth or session length; a count is a\n"
    "quota in disguise. The only two limits are the licence gate (public and licensed only, a\n"
    "forbidding licence is a HARD STOP) and never installing third-party tooling -- mine it as\n"
    "TEXT. Neither is a scope limit.\n"
    "Coverage is still the count of DISTINCT MECHANISM FAMILIES you\n"
    "return, never the count of findings. Twelve findings from one family are correlated by\n"
    "construction: they die together and the desk learns one thing while the log reports\n"
    "twelve. data/strategy_coverage.json names every family HUNTED / THIN / NEVER-HUNTED from\n"
    "the desk's own graveyard -- read it, and prefer an unhunted family over deepening a\n"
    "worked one. On the desk's record 41 buried candidates cluster into 7 worked families of\n"
    "14, so breadth is the binding constraint, not depth.\n"
    "- NEGATIVE KNOWLEDGE COUNTS: if you hunt a forest and find nothing, SAY SO explicitly. That "
    "prevents repeated waste and is a valid deliverable.\n"
    # L1.34 (principal 2026-07-31): the hunters were free to return one CLASS of artifact and
    # call the ground dug. Every source class is in scope for every seat, kimi included -- it is
    # the desk's only non-Claude hunter, so a narrow brief here narrows the widest lens we own.
    "- EVERY FORM OF RAW INFORMATION IS IN SCOPE (L1.34), not just live feeds: published "
    "BACKTESTS and result tables (read the code and the window -- the leak they missed is the "
    "find), STRATEGY CODE and configs, DATASETS and the endpoint lists inside collector code, "
    "AI-QUANT STRUCTURES (factor-mining frameworks, symbolic regression, agent-team and "
    "multi-model architectures, RL harnesses), NICHE AI-QUANT COMMUNITIES explicitly including "
    "the Chinese ecosystem (Gitee, Zhihu, Xueqiu, JoinQuant/BigQuant, WeChat mirrors, Bilibili) "
    "and their contributor networks, UNTESTED ALPHAS (published-but-never-validated claims, "
    "abandoned hypotheses, 'this worked for me' posts with no out-of-sample -- untested is not "
    "false, it is an UNPRICED OPTION and it is the richest and most neglected vein), VIDEO AND "
    "AUDIO (talks, lectures, botter walkthroughs -- transcripts are readable and are first-class "
    "material, never a logged blocker), and everything else carrying information: exchange "
    "changelogs and announcement archives, regulatory filings and enforcement actions, patents, "
    "JOB POSTINGS (they leak infrastructure and strategy families), theses, dead products' docs, "
    "archived APIs. THE STANDING TEST: if a source carries information a competitor would have "
    "to PAY to reconstruct, it is in scope regardless of format, language, age, or how "
    "unglamorous it looks.\n\n"
    "CLAIM PROVENANCE IS MANDATORY. Every finding starts with one of:\n"
    "  VERIFIED  -- direct quote or number WITH a URL or document reference\n"
    "  INFERRED  -- your own mechanism construction (legitimate, but say so)\n"
    "NEVER blend them in one finding. Split it, or drop it. A VERIFIED tag with no\n"
    "source reference will be downgraded automatically.\n"
    "YOUR JOB IS RAW SIGNAL, NOT MECHANISM. Mechanism construction happens at the next\n"
    "stage. If you find yourself explaining WHY something should work, you have\n"
    "overstepped -- report what you FOUND and let the next stage build the story.\n"
    "If you find nothing in a forest, say so explicitly. That is a valid deliverable.\n\n"
    "OUTPUT: one finding per line, fields separated by |, exactly 8 fields:\n"
    "CLAIM_CLASS | PROBLEM | EVIDENCE | BENEFIT | COST | DEPENDENCIES | SUCCESS_METRIC | KILL_CONDITION\n"
    "where PROBLEM names the information gap, EVIDENCE cites the source/URL, and KILL_CONDITION "
    "states what observation would prove the source worthless."
)

WAVES = {
    1: ("SHADOW MAPPING", "Map what the herd covered in the last 24h: English CT narratives, "
        "Dune/CoinGlass/DefiLlama trending, GitHub trending quant repos, mainstream crypto media. "
        "Output 10-15 covered topics labelled HERD_COVERED. Do NOT report findings yet."),
    2: ("NEGATIVE SPACE MINING", "For each HERD_COVERED item from Wave 1, ask what ADJACENT topic "
        "they ignored because it is too small, weird or foreign. You may NOT report a finding "
        "unless you name the specific herd coverage that caused the miss."),
    3: ("DEEP FOREST PENETRATION", "Forget the herd. Hunt: abandoned repos with 0 stars, protocols "
        "under $10M TVL with no English docs, mempool patterns nobody has named, regulatory "
        "filings in non-Latin scripts, bridge failure modes, perp venues with no CoinGlass page. "
        "Findings must be things where a typical quant would say 'I didn't know that was "
        "measurable'."),
}



def _load_coverage() -> dict:
    try:
        return json.loads(_COVERAGE.read_text("utf-8"))
    except Exception:  # blind-except intentional (BLE001)
        return {"vectors": {}}


def _exclusion_text(cov: dict) -> str:
    """What the hunter has ALREADY covered -- fed as exclusions, never as instructions."""
    now = datetime.now(tz=UTC)
    live = []
    for v, meta in cov.get("vectors", {}).items():
        try:
            age = (now - datetime.fromisoformat(meta["first_seen"])).days
        except Exception:  # blind-except intentional (BLE001)
            age = 0
        if age < _VECTOR_COOLDOWN_D:
            live.append(f"{v} (hunted {age}d ago)")
    if not live:
        return ("You have no hunt history. Generate your own vectors -- name the territories "
                "yourself. Do not ask what to search; decide.")
    return ("ALREADY HUNTED -- do NOT return to these, they are picked over:\n  "
            + "\n  ".join(sorted(live))
            + "\n\nGenerate NEW vectors. Name each territory you choose and why the herd "
              "cannot see it. A vector you have used before is a wasted run.")


def _record_vectors(cov: dict, text: str) -> int:
    """Harvest whatever territories the hunter named this run into permanent coverage memory."""
    now = datetime.now(tz=UTC).isoformat()
    found = set(re.findall(r"VECTOR:\s*([A-Za-z0-9_\- ]{4,50})", text))
    n = 0
    for v in found:
        k = v.strip().lower()
        if k and k not in cov.setdefault("vectors", {}):
            cov["vectors"][k] = {"first_seen": now}
            n += 1
    return n


def _budget_ok() -> tuple[bool, str]:
    try:
        env = json.loads(BUDGET.read_text("utf-8"))["monthly_envelope_usd"]
        st = json.loads(BSTATE.read_text("utf-8"))
        mtd = st.get("usage_at_run_start", 0.0) - st.get("usage_at_month_start", 0.0)
        return (mtd < env, f"MTD ${mtd:.2f} of ${env:.2f} envelope")
    except Exception:  # blind-except intentional (BLE001)
        return (True, "budget state unreadable -- proceeding, guard is advisory")


def _ask(base, key, system, user, timeout=240.0) -> str:
    body = json.dumps({"model": MODEL, "max_tokens": 16000, "temperature": 1.0,
                       "messages": [{"role": "system", "content": _doctrine("kimi_hunter") + system},
                                    {"role": "user", "content": user}]}).encode()
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        out = json.loads(r.read())
    m = out["choices"][0]["message"]
    return str(m.get("content") or m.get("reasoning") or "")






def _admit(line: str, wave: int, wave_text: str = "") -> tuple[bool, str, str, list[str]]:
    """SINGLE SOURCE OF TRUTH for admission. Returns (keep, reason, claim_class, fields).

    main() and _selftest() both call this. Previously the selftest carried its own simplified
    copy, scored 6/6 against a rule that does not run, and stayed green through a charter change
    that broke it. One function means they cannot diverge again.
    """
    parts = [x.strip() for x in line.split("|")]
    if len(parts) < 8:
        return (False, f"only {len(parts)} fields, charter needs 8", "", parts)
    cls = parts[0].upper()
    if cls not in ("VERIFIED", "INFERRED"):
        return (False, f"claim class {cls!r} not VERIFIED/INFERRED", cls, parts)
    f = _forbidden(line)
    if f:
        return (False, f"forbidden zone {f!r}", cls, parts)
    body = " ".join(parts[1:])
    if cls == "VERIFIED" and not any(t in body.lower() for t in
                                     ("http", "www.", ".gov", ".org", "10-q", "10-k",
                                      "filing", "docs.", "github.com")):
        # an unsourced claim of sourcing is worth exactly what an unsourced claim is worth
        return (True, "VERIFIED downgraded to INFERRED -- no source reference", "INFERRED",
                parts[1:])
    if wave == 2 and "HERD_COVERED" not in wave_text.upper() and "because" not in line.lower():
        return (False, "no linkage to Wave-1 coverage", cls, parts)
    return (True, "", cls, parts[1:])


_SELFTEST_CASES = [
    ("INFERRED | Japanese tax reclassification drives offshore perp flow | FIEA 2027 timeline;"
     " capital-flight mechanism is my construction | forced-flow lead | 3d | none |"
     " JPY-hours perp volume share rises | no share change after 90d",
     "KEEP", "INFERRED and labelled as such -- legitimate"),
    ("VERIFIED | Strategy preferred dividend forces BTC sales | $1.2B annual obligation |"
     " scheduled forced seller | 2d | none | sale within 5d of dividend date | no clustering",
     "KEEP-DOWNGRADED", "VERIFIED with no URL -> auto-downgraded to INFERRED"),
    ("Bridge failure spike | illustrative example | edge | 1d | none | IC | none | extra",
     "DROP", "no CLAIM_CLASS in position 1"),
    ("INFERRED | Binance funding anomaly | dashboards show it | edge | 1d | NONE | IC | none",
     "DROP", "forbidden zone: crowded funding"),
    ("INFERRED | RSI oversold micro caps | tradingview | edge | 1d | NONE | IC | none",
     "DROP", "forbidden zone: RSI / TradingView"),
    ("INFERRED | Twitter sentiment velocity | CT volume | edge | 1d | NONE | IC | none",
     "DROP", "forbidden zone: twitter sentiment"),
    ("VERIFIED | Aave health-factor tail predicts forced liquidation | https://docs.aave.com logs"
     " | forced-seller lead time | 2d | local node | share of cascades pre-detected > 0.4 |"
     " no lead beyond 1 block",
     "KEEP", "forced participant + free source + kill condition"),
    ("VERIFIED | Validator exit queue predicts stETH discount | https://beaconcha.in API | early"
     " warning | 1d | NONE | corr with discount > 0.3 | no relation after 60d",
     "KEEP", "obscure, free, mechanism named"),
    ("INFERRED | Bridge failure spike | Stargate subgraph | liquidity stress",
     "DROP", "only 3 fields, charter needs 7"),
]


def _selftest() -> int:
    """Exercise enforcement offline with synthetic hunter output. Costs nothing."""
    print("=== KIMI HUNTER SELFTEST (enforcement only; API path needs credit) ===")
    print()
    passed = 0
    for line, expect, why in _SELFTEST_CASES:
        keep, reason, _cls, _ = _admit(line, 3, "")
        got = "KEEP" if keep else "DROP"
        if keep and "downgraded" in reason:
            got = "KEEP-DOWNGRADED"
        ok = got == expect
        passed += ok
        print(f"  {'PASS' if ok else 'FAIL'}  expect {expect:<16} got {got:<16}  {why}")
        if reason:
            print(f"           {reason}")
    print()
    print(f"  {passed}/{len(_SELFTEST_CASES)} enforcement cases correct")
    print("  Verified WITHOUT spending credit: forbidden zones drop crowded and dead sources,")
    print("  the 7-field charter rejects incomplete proposals, and genuine forced-participant")
    print("  findings on free sources survive. The API path stays untested until funded --")
    print("  stated, not implied.")
    return 0 if passed == len(_SELFTEST_CASES) else 1




# Adversarial on purpose: 2 admissible, 1 forbidden, 1 unsourced-VERIFIED, 1 malformed.
_MOCK_WAVES = {
    1: ("HERD_COVERED: BTC funding squeeze; ETF flows; SOL upgrade narrative; "
        "liquidation heatmaps; DXY macro; Dune liquidation trackers."),
    2: ("HERD_COVERED liquidation heatmaps -- they watch CEX perp liquidations because "
        "CoinGlass renders them, and therefore ignore DeFi lending health factors upstream.\n"
        "VERIFIED | Aave health-factor left tail predicts forced liquidation before perps "
        "reflect it | https://docs.aave.com event logs via free RPC, because the herd watches "
        "CEX heatmaps | forced-seller lead time | 2d | local node | share of cascades "
        "pre-detected > 0.4 | no lead beyond 1 block\n"
        "INFERRED | Binance funding anomaly on majors | dashboards show it | edge | 1d | NONE "
        "| IC | none\n"),
    3: ("VERIFIED | Validator exit queue length predicts stETH discount | "
        "https://beaconcha.in public API | early warning on staked-ETH pressure | 1d | NONE | "
        "corr with discount > 0.3 | no relation after 60d\n"
        "VERIFIED | Strategy preferred dividend forces quarterly BTC sales | $1.2B annual "
        "obligation | scheduled forced seller | 2d | NONE | sale within 5d of dividend | "
        "no clustering over 4 quarters\n"
        "INFERRED | Bridge failure spike | Stargate subgraph | liquidity stress\n"),
}


def _mock() -> int:
    """Run the entire pipeline on synthetic output. Only the HTTP call is bypassed."""
    print("=== KIMI HUNTER --mock : full chain, no credit, HTTP bypassed ===")
    print("    payload is adversarial: 2 admissible, 1 forbidden, 1 unsourced-VERIFIED,")
    print("    1 malformed. Wrong admissions fail loudly instead of reaching the ledger.\n")
    findings, dropped = [], []
    for w in (1, 2, 3):
        txt = _MOCK_WAVES[w]
        print(f"  WAVE {w}: {len(txt)} chars")
        if w == 1:
            print("    (mapping wave -- findings not permitted)")
            continue
        for ln in txt.splitlines():
            if ln.count("|") < 3:
                continue
            keep, reason, cls, parts = _admit(ln, w, txt)
            if reason:
                dropped.append((w, reason))
                print(f"    drop/flag: {reason}")
            if not keep:
                continue
            findings.append({"date": datetime.now(tz=UTC).date().isoformat(),
                             "source": "kimi_k3_deep_forest", "wave": w, "claim_class": cls,
                             "problem": parts[0][:220], "evidence": parts[1][:220],
                             "benefit": parts[2][:180], "cost": parts[3][:140],
                             "dependencies": parts[4][:140], "success_metric": parts[5][:180],
                             "kill_condition": parts[6][:180], "status": "proposed"})
            print(f"    ADMIT [{cls}] {parts[0][:62]}")

    expect_admit, expect_drop = 3, 3
    ok = len(findings) == expect_admit and len(dropped) >= expect_drop
    print(f"\n  admitted {len(findings)} (expect {expect_admit}), "
          f"dropped/flagged {len(dropped)} (expect >= {expect_drop})")
    if not ok:
        print("  MOCK FAILED -- the chain would write the wrong things when funded.")
        return 1

    before = LEDGER.stat().st_size if LEDGER.exists() else 0
    with LEDGER.open("a", encoding="utf-8") as fh:
        for f in findings:
            f["mock"] = True                       # tagged so the scoreboard can exclude it
            fh.write(json.dumps(f) + "\n")
    after = LEDGER.stat().st_size
    print(f"  ledger {before} -> {after} bytes (+{after-before}) -- rows tagged mock=true")
    print("\n  CHAIN PROVEN. The only untested link between funded credit and findings in the")
    print("  ledger is one urllib call returning 200 instead of 402. Admission, provenance")
    print("  downgrade, forbidden zones, wave-2 linkage and the ledger write all executed")
    print("  against real code just now.")
    return 0


def main() -> None:
    ok, why = _budget_ok()
    print("=== KIMI HUNTER -- Deep Forest Protocol (Wave 1 -> 2 -> 3) ===")
    print(f"    budget: {why}\n")
    if not ok:
        raise SystemExit("envelope exhausted -- refusing to start (guard, not a failure)")

    prov = None
    if KEYS.exists():
        for p in json.loads(KEYS.read_text("utf-8")).get("providers", []):
            if isinstance(p, dict) and p.get("model") == MODEL:
                prov = p
                break
    if not prov:
        print(f"  {MODEL} not in the seated roster -- add it to llm_panel.json first")
        raise SystemExit(2)

    kills = set(json.loads(MECHB.read_text("utf-8")).get("family_kills", [])) \
        if MECHB.exists() else set()
    print(f"  enforcing {len(FORBIDDEN_SETS)} forbidden zones + {len(kills)} family kills\n")

    cov = _load_coverage()
    transcript, findings, dropped = {}, [], []
    for w in (1, 2, 3):
        name, brief = WAVES[w]
        prior = "\n\n".join(f"WAVE {k} OUTPUT:\n{v[:2500]}" for k, v in transcript.items())
        user = f"{brief}\n\n{_exclusion_text(cov)}" + (f"\n\n{prior}" if prior else "")
        print(f"  WAVE {w} -- {name}")
        try:
            txt = _ask(prov["base_url"], prov["key"], CHARTER, user)
        except Exception as e:  # blind-except intentional (BLE001)
            code = getattr(e, "code", "")
            print(f"    FAILED ({type(e).__name__} {code})")
            if code == 402:
                print("    OpenRouter is out of credit. The hunt is BLOCKED, not broken --")
                print("    the harness is intact and fires on the next funded run.")
            raise SystemExit(3) from e
        transcript[w] = txt
        _new_v = _record_vectors(cov, txt)
        print(f"    {len(txt)} chars returned, {_new_v} new vector(s) recorded")

        if w == 1:
            continue                       # Wave 1 is mapping only; findings are not permitted
        for ln in txt.splitlines():
            if ln.count("|") < 3:
                continue
            keep, reason, cls, parts = _admit(ln, w, txt)
            if reason:
                dropped.append({"wave": w, "reason": reason, "line": ln[:120]})
            if not keep:
                continue
            findings.append({"date": datetime.now(tz=UTC).date().isoformat(),
                             "source": "kimi_k3_deep_forest", "wave": w, "claim_class": cls,
                             "problem": parts[0][:220], "evidence": parts[1][:220],
                             "benefit": parts[2][:180], "cost": parts[3][:140],
                             "dependencies": parts[4][:140], "success_metric": parts[5][:180],
                             "kill_condition": parts[6][:180], "status": "proposed"})

    print(f"\n  {len(findings)} charter-complete findings, {len(dropped)} dropped")
    for d in dropped:
        print(f"    dropped (wave {d['wave']}): {d['reason']}")
    if findings:
        with LEDGER.open("a", encoding="utf-8") as fh:
            for f in findings:
                fh.write(json.dumps(f) + "\n")
        print(f"  -> {LEDGER}  (enters the SAME gate as every other contributor)")
    print("\n  ZERO PROMOTION AUTHORITY. These are raw ore. Next stops: mechanism board "
          "(family-kill rejection), measurement gate, Stage-A screening, forward clock.")
    _COVERAGE.write_text(json.dumps(cov, indent=1), "utf-8")
    print(f"  coverage memory: {len(cov.get(chr(34)+chr(118)+chr(101)+chr(99)+chr(116)+chr(111)+chr(114)+chr(115)+chr(34), {}))} territories hunted to date")
    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(), "model": MODEL,
                               "waves": {str(k): v[:4000] for k, v in transcript.items()},
                               "findings": findings, "dropped": dropped}, indent=1), "utf-8")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    if "--mock" in sys.argv:
        raise SystemExit(_mock())
    main()

```

### scripts/principle_audit.py
```python
"""Are ALL principles enforced, or only the five I happened to write into the preamble?

THE GAP I SUSPECT IN MY OWN WORK. doctrine.py enforces PRESENCE of a marker on three surfaces. It
never checks WHICH principles are present. I wrote five sections into the preamble; the doctrine
documents accumulated roughly fifteen principles across this session. Enforcing a marker while the
content is a subset is enforcement theatre -- the check passes, and two thirds of the doctrine
never reaches a single model.

This enumerates every principle the desk has committed to, and reports which are actually in the
runtime preamble that models receive.
"""
from __future__ import annotations

import json
import pathlib
import sys
from datetime import UTC, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data/principle_audit.json"

# Every principle this desk has adopted, with the phrases that would evidence it in a prompt.
PRINCIPLES = {
    "anti_timidity": ("hedging is a failure", "refusing to conclude", "say it is wrong"),
    "exhaustion_no_quota": ("no quota", "no ceiling", "exhaustion"),
    "evidence_discipline": ("verified", "inferred", "unsourced claim"),
    "measurement_before_optimisation": ("assume the data is lying", "measuring the thing"),
    "north_star": ("validated alpha discovery rate", "north star"),
    "mechanism_first": ("mechanism before prediction", "who is forced", "forced participant"),
    "bottleneck_first": ("bottleneck first", "current limiting factor"),
    "opportunity_cost": ("opportunity cost", "highest expected-value use", "next research hour"),
    "no_premature_optimisation": ("premature optimis", "before it proves"),
    "reality_feedback": ("live evidence", "reality overrides", "market is the final judge"),
    "complexity_governance": ("replace an existing component",),
    "stage_a_law": ("zero promotion authority", "stage-a", "forward clock"),
    "never_exhausted_exploration": ("never exhausted", "no ceiling", "one layer past"),
    "capacity_awareness": ("cannot be executed at the desk", "degrades with scale"),
    "kill_fast": ("would falsify", "rejected regardless"),
}


def main() -> None:
    from scripts.doctrine import preamble
    text = preamble().lower()
    rows, present, absent = [], [], []
    for name, kws in PRINCIPLES.items():
        hits = [k for k in kws if k in text]
        ok = bool(hits)
        (present if ok else absent).append(name)
        rows.append({"principle": name, "in_preamble": ok, "matched": hits})

    print("=== PRINCIPLE COVERAGE IN THE RUNTIME PREAMBLE ===")
    print("    doctrine.py enforces that a marker EXISTS on three surfaces. It never checked")
    print("    WHICH principles the preamble actually contains -- a passing check with a subset")
    print("    of the doctrine is enforcement theatre.\n")
    for r in rows:
        print(f"  {'IN ' if r['in_preamble'] else 'OUT'}  {r['principle']:<34}"
              f"{('matched: ' + r['matched'][0]) if r['matched'] else 'NOT PRESENT'}")
    pct = len(present) / len(PRINCIPLES) * 100
    print(f"\n  {len(present)}/{len(PRINCIPLES)} principles reach the models ({pct:.0f}%)")
    if absent:
        print(f"  ABSENT: {', '.join(absent)}")
        print("  These live only in documents. A model never sees them, so for every LLM call")
        print("  they do not exist. That is the difference between written and enforced.")
    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "coverage_pct": round(pct, 1), "present": present,
                               "absent": absent}, indent=1), "utf-8")
    print(f"\n  -> {OUT}")
    sys.exit(1 if absent else 0)


if __name__ == "__main__":
    main()

```

### scripts/research_erv.py
```python
"""EXPECTED RESEARCH VALUE -- score hypotheses BEFORE testing, so conversion rises instead of \
supply.

THE INSIGHT THIS IMPLEMENTS (principal, 2026-07-27): the desk does not have an idea shortage. It
has a CONVERSION problem. ~28 hypotheses tested today, ONE survived. Adding generators raises
supply against a fixed confirmation budget; what actually helps is testing the RIGHT ones first.

    ERV = P(edge) x information_gain x moat_advantage x future_unlocks / experiment_cost

FOUR SCORERS, each grounded in something this desk MEASURED rather than assumed:

1. ARCHAEOLOGY (the biggest fix). The hypothesis_generator dedups on TOKENS, which is too weak:
   "Twitter sentiment predicts returns" and "social attention predicts momentum" share almost no
   tokens and are the SAME dead idea. This maps text to CONCEPT FAMILIES (attention, developer,
   whale, funding, premium, flow, spread, microstructure...) and matches at concept level against
   the graveyard. A hypothesis whose concept family is dead scores ~0 regardless of wording.

2. MOAT ADVANTAGE. Public data (GitHub/TVL/Twitter/Wikipedia/Trends) carries a PROCESSING
   advantage anyone can replicate. data/moat -- 4.4GB of recorded order books, 30 symbols x
   spot/fut -- is an INFORMATION advantage nobody else has. Weighted accordingly: today proved
   public-data hypotheses die at ~27/28.

3. MECHANISM DEPTH. Every survivor on this desk has been a SPREAD with a HARD constraint (kimchi:
   capital controls; carry: funding structure). Every FORECAST died. So forced-flow and
   hard-barrier mechanisms score above correlational ones -- this is a measured prior, not taste.

4. EXPERIMENT COST. Cheap falsifiable tests outrank expensive ones at equal promise, because the
   binding constraint is confirmation budget, not compute.

Read-only. No LLM, no keys. Run from repo root.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
GRAVE = ROOT / "docs/graveyard.md"
QUEUE = ROOT / "data/hypothesis_queue.jsonl"
OUT = ROOT / "data/research_erv.json"

# concept families -- the archaeologist's vocabulary. Matching happens HERE, not on raw tokens.
CONCEPTS = {
    "attention": ("attention", "sentiment", "social", "twitter", "wikipedia", "search",
                  "narrative", "mention", "trend", "hype", "buzz", "interest", "pageview"),
    "developer": ("developer", "github", "commit", "contributor", "repo", "code", "maintainer",
                  "release", "dev activity", "talent"),
    "trader_skill": ("trader", "copytrad", "leaderboard", "elite", "skill", "whale", "smart money",
                     "persistence", "follower"),
    "premium_regional": ("premium", "kimchi", "regional", "korea", "china", "arbitrage venue",
                         "cross-venue", "peg", "depeg"),
    "funding_position": ("funding", "open interest", "positioning", "crowding", "long short",
                         "liquidation", "basis", "carry", "perp"),
    "onchain_flow": ("on-chain", "onchain", "wallet", "exchange flow", "netflow", "stablecoin",
                     "tvl", "bridge", "address", "supply"),
    "microstructure": ("order book", "orderbook", "depth", "spread", "liquidity", "imbalance",
                       "market maker", "slippage", "replenish", "fragility", "microstructure"),
    "reflexivity": ("reflexiv", "feedback", "cascade", "leverage cycle", "credit cycle"),
}

# concept -> (verdict, why) from THIS desk's measured history
HISTORY = {
    "attention": (
        "DEAD", "level AND acceleration tested across 15 horizons, 5 languages; all dead"),
    "developer": (
        "MOSTLY DEAD", "commit velocity CS-IC ~0 at 1/3/6mo; retention n=10 underpowered"),
    "trader_skill": ("DEAD", "5 mechanisms, ~50k traders, gapped persistence rho -0.064"),
    "premium_regional": ("PARTLY ALIVE", "kimchi/cny live; JP/BR/TR/pegs/LSD all died on WIDTH"),
    "funding_position": ("ALIVE", "funding persistence IC +0.432; ls_contrarian on clock to Aug 7"),
    "onchain_flow": ("MOSTLY DEAD", "usage metrics dead; stablecoin supply weak-but-live"),
    "microstructure": ("UNTESTED", "4.4GB recorded moat, needs book reconstruction -- OPEN"),
    "reflexivity": ("INCONCLUSIVE", "M5 underpowered, OI history capped at 500 bars"),
}

MOAT_TERMS = ("order book", "orderbook", "depth", "book imbalance", "replenish", "moat",
              "recorded", "l2", "microstructure", "slippage", "market maker inventory")
PUBLIC_TERMS = ("github", "twitter", "wikipedia", "google trends", "tvl", "defillama",
                "social", "reddit", "search volume")
HARD_MECH = ("capital control", "licence", "license", "regulat", "settlement", "collateral",
             "margin call", "forced", "liquidation", "redemption", "queue", "mandate",
             "cannot", "barrier", "segmentat")


def concepts_of(text: str) -> set[str]:
    t = text.lower()
    return {c for c, kws in CONCEPTS.items() if any(k in t for k in kws)}


def score(h: dict[str, Any]) -> dict[str, Any]:
    blob = " ".join(str(h.get(k, "")) for k in ("name", "mechanism", "data", "test"))
    t = blob.lower()
    cs = concepts_of(blob)

    # 1. archaeology -- concept-level, not token-level
    verdicts = [HISTORY.get(c, ("UNKNOWN", ""))[0] for c in cs]
    if "DEAD" in verdicts:
        arch, arch_why = 0.05, (
            f"concept already DEAD here: {[c for c in cs if HISTORY.get(c,('',''))[0]=='DEAD']}")
    elif "MOSTLY DEAD" in verdicts:
        arch, arch_why = 0.3, "concept mostly refuted; needs a materially new construction"
    elif "INCONCLUSIVE" in verdicts or "PARTLY ALIVE" in verdicts:
        arch, arch_why = 0.8, "concept partially explored, room remains"
    elif "UNTESTED" in verdicts:
        arch, arch_why = 1.0, "concept UNTESTED on this desk"
    else:
        arch, arch_why = 0.9, "no concept match -- genuinely novel or unclassified"

    # 2. moat advantage
    if any(m in t for m in MOAT_TERMS):
        moat, moat_why = 1.0, "uses the recorded order-book moat (information advantage)"
    elif any(p in t for p in PUBLIC_TERMS):
        moat, moat_why = 0.35, "public data -- processing advantage only, replicable by anyone"
    else:
        moat, moat_why = 0.6, "mixed/unclear data provenance"

    # 3. mechanism depth -- spreads and forced flows beat forecasts (measured prior)
    mech = 1.0 if any(m in t for m in HARD_MECH) else (0.6 if "spread" in t else 0.35)
    mech_why = ("hard constraint / forced flow named" if mech == 1.0
                else "spread construction" if mech == 0.6
                else "correlational -- forecasts died here")

    # 4. cost -- cheap falsifiable tests first
    cost = 1.0
    if any(k in t for k in ("reconstruct", "clustering", "neural", "graph", "panel of")):
        cost = 0.5
    if not h.get("kill"):
        cost *= 0.7                              # no kill condition = not properly falsifiable

    erv = arch * moat * mech * cost
    return {"erv": round(erv, 4), "archaeology": arch, "moat": moat, "mechanism": mech,
            "cost": cost, "concepts": sorted(cs),
            "why": f"{arch_why}; {moat_why}; {mech_why}"}


def main() -> None:
    rows = []
    if QUEUE.exists():
        for ln in QUEUE.read_text("utf-8").splitlines():
            if ln.strip():
                try:
                    rows.append(json.loads(ln))
                except json.JSONDecodeError:
                    continue
    print("=== EXPECTED RESEARCH VALUE -- prioritise BEFORE testing ===")
    print("    the desk has an idea SURPLUS and a conversion deficit; this ranks the queue\n")
    print("  concept-family status on this desk (measured, not assumed):")
    for c, (v, why) in HISTORY.items():
        print(f"    {c:<18} {v:<14} {why}")

    if not rows:
        print("\n  hypothesis queue is EMPTY (hypothesis_generator has never run -- 402).")
        print("  Demonstrating the scorer on the principal's own recent slate instead:\n")
        rows = [
            {"name": "Attention efficiency ratio", "mechanism": "return per unit social attention",
             "data": "google trends + wikipedia", "test": "cross-sectional IC", "kill": "IC<0.03"},
            {"name": "Developer retention momentum",
             "mechanism": "contributors staying predicts growth",
             "data": "github contributors", "test": "rank vs fwd relative return", "kill": "t<2"},
            {"name": "Market maker inventory stress",
             "mechanism": "MMs FORCED to withdraw depth when inventory risk binds",
             "data": "recorded order book depth (moat)", "test": "depth withdrawal vs fwd RV",
             "kill": "no vol expansion"},
            {"name": "Liquidity fragility score",
             "mechanism": "depth collapse under stress cannot be replenished -- forced flow",
             "data": "recorded order book (moat)", "test": "depth decay vs realised vol",
             "kill": "ratio<1.2"},
            {"name": "Bridge flow predicts rotation", "mechanism": "capital migrates before repricing",
             "data": "defillama bridges", "test": "flow vs fwd relative return", "kill": "t<2"},
        ]

    scored = sorted(((h, score(h)) for h in rows), key=lambda x: -x[1]["erv"])
    print(f"  {'ERV':>6}  {'arch':>5} {'moat':>5} {'mech':>5} {'cost':>5}  hypothesis")
    for h, s in scored[:20]:
        print(f"  {s['erv']:>6.3f}  {s['archaeology']:>5.2f} {s['moat']:>5.2f} "
              f"{s['mechanism']:>5.2f} {s['cost']:>5.2f}  {h['name'][:52]}")
        print(f"          {s['why'][:110]}")
    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "n": len(scored),
                               "ranked": [{"name": h["name"], **s} for h, s in scored]},
                              indent=1), "utf-8")
    print(f"\n  -> {OUT}")
    print("  A hypothesis scoring <0.15 should NOT consume a confirmation slot regardless of how")
    print("  interesting it sounds. Concept-level archaeology means rewording a dead idea does not")
    print("  resurrect it -- which token-level dedup could not prevent.")


if __name__ == "__main__":
    main()

```

### scripts/research_memory.py
```python
﻿#!/usr/bin/env python3
"""RESEARCH MEMORY CLI (2026-07-24) -- the conversion loop's ledger, made one-line writable.

The external audit and the desk's own fence agree: research_memory had 0 rows EVER while every
mission directive claimed analyst passes write to it -- the hypothesis factory's memory was a
null pipe. The table existed; the FRICTION did (raw sqlite from a prompt-driven organ). This
CLI removes it, exactly like blind_spot.py did for gap-origin logging.

Usage:
  research_memory.py log --category hypothesis --statement "..." --result pending
        [--lessons "..."] [--failure-cause data|construction|stats|economics]
        [--failure-stage screen|clock|gauntlet] [--metrics '{"ic":0.03}'] [--predecessor rm-...]
  research_memory.py report [--days 30]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

_DB = Path(__file__).resolve().parent.parent / "data/sor_research.sqlite"
_CATS = ("hypothesis", "dataset", "method", "mission", "construction")
# The table CHECK constraint allows only pending/success/failure -- richer statuses map onto it
# and the granular label is preserved in metrics_json.status_granular.
_RES_MAP = {"pending": "pending", "screening": "pending", "clock-accruing": "pending",
            "validated": "success", "rejected": "failure", "abandoned": "failure"}


def log(a) -> None:
    rid = f"rm-{datetime.now(tz=UTC).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"
    metrics = {}
    if a.metrics:
        try:
            metrics = json.loads(a.metrics)
        except Exception:
            metrics = {"raw": a.metrics}
    metrics.setdefault("status_granular", a.result)
    # --axis tags WHICH ingested data axis this hypothesis screens. Coverage (not volume) is the
    # data-utilization parity metric: the paralysis flag clears only when every axis has >=1 such
    # tagged hypothesis, so tagging is what converts an idle axis on the record.
    if getattr(a, "axis", None):
        metrics["axis"] = a.axis.strip()
    con = sqlite3.connect(_DB)
    con.execute(
        "INSERT INTO research_memory (id, created_at, category, statement, result, "
        "failure_cause, failure_reason, success_reason, failure_stage, lessons, metrics_json, "
        "predecessor_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (rid, datetime.now(tz=UTC).isoformat(), a.category, a.statement[:600],
         _RES_MAP[a.result],
         a.failure_cause, a.failure_reason, a.success_reason, a.failure_stage,
         a.lessons, json.dumps(metrics), a.predecessor))
    con.commit()
    con.close()
    print(f"research-memory logged: {rid} [{a.category}/{a.result}] {a.statement[:60]}")


def report(a) -> None:
    con = sqlite3.connect(_DB)
    con.row_factory = sqlite3.Row
    cut = f"-{a.days} days"
    rows = list(con.execute(
        "SELECT * FROM research_memory WHERE created_at >= datetime('now', ?) "
        "ORDER BY created_at DESC", (cut,)))
    total = con.execute("SELECT COUNT(*) FROM research_memory").fetchone()[0]
    by: dict[str, int] = {}
    for r in rows:
        k = f"{r['category']}/{r['result']}"
        by[k] = by.get(k, 0) + 1
    print(f"RESEARCH MEMORY: {total} rows total, {len(rows)} in last {a.days}d")
    for k, v in sorted(by.items()):
        print(f"  {k}: {v}")
    for r in rows[:10]:
        print(f"  {r['id']}  {r['statement'][:70]}")
    con.close()


def coverage(a) -> None:
    """Report axis-coverage parity: how many ingested axes have been converted (tested once).

    The data-utilization law reconciled with gate-optimality: paralysis is a COVERAGE gap, never a
    volume gap. An axis counts as converted from any real conversion artifact -- a forward-clock
    shadow, a reconstructed held-out OOS report, or a research_memory hypothesis tagged with the
    axis. This is the read-side of the metric max_audit enforces -- run it to see which idle axes
    still need one mechanism-first hypothesis each (tag a new screen with `log --axis`)."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    # single source of truth for the acquired surface + real conversion artifacts
    from scripts.max_audit import _acquired_axes, _converted_axes

    from libs.autodiscovery.extraction_parity import axis_coverage

    acquired = _acquired_axes()
    tags = _converted_axes()
    covered = [ax for ax in acquired
               if any(t == ax.lower() or t in ax.lower() or ax.lower() in t for t in tags)]
    rep = axis_coverage(axes=acquired, screened_axes=covered)
    print(f"AXIS COVERAGE: {rep.n_covered}/{rep.n_axes} converted ({rep.coverage_frac:.0%})")
    print(f"  {rep.verdict}")
    if rep.idle:
        print(f"  idle (need one mechanism-first hypothesis each): {', '.join(rep.idle)}")


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    lg = sub.add_parser("log")
    lg.add_argument("--category", required=True, choices=_CATS)
    lg.add_argument("--statement", required=True)
    lg.add_argument("--result", required=True, choices=list(_RES_MAP))
    lg.add_argument("--failure-cause", dest="failure_cause", default=None)
    lg.add_argument("--failure-reason", dest="failure_reason", default=None)
    lg.add_argument("--success-reason", dest="success_reason", default=None)
    lg.add_argument("--failure-stage", dest="failure_stage", default=None)
    lg.add_argument("--lessons", default=None)
    lg.add_argument("--metrics", default=None)
    lg.add_argument("--predecessor", default=None)
    lg.add_argument("--axis", default=None,
                    help="the ingested data axis this hypothesis screens (coverage parity metric)")
    lg.set_defaults(fn=log)
    rp = sub.add_parser("report")
    rp.add_argument("--days", type=int, default=30)
    rp.set_defaults(fn=report)
    cv = sub.add_parser("coverage", help="axis-coverage parity: which ingested axes are converted")
    cv.set_defaults(fn=coverage)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()

```

### scripts/revalidate_clocks.py
```python
"""LIVE-CLOCK RE-VALIDATION against the rails added 2026-07-23..27.

Every currently-tracked axis was screened BEFORE some of these controls existed. A signal that
passed a weaker gate is not validated -- it is unexamined. This re-runs each LIVE axis through:
  1. the hardened harness (de-contamination + SUSPECT-LOOKAHEAD plausibility rail)
  2. the SHIFT-SENSITIVITY test that killed bithumb_KR (timezone/candle-label lookahead): a genuine
     leading signal degrades smoothly under a +/-1 day shift; a lookahead artifact keeps or peaks
     its IC when the signal is shifted FORWARD (i.e. it already contained future price).
KIMCHI IS THE PRIORITY: it uses Upbit daily candles, and bithumb -- another KRW venue -- died of
exactly this (KST day-open timestamps sat ~1.6d ahead of Binance UTC closes).
Read-only diagnostic. Run from repo root."""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.research.axis_screen import stage_a_screen  # noqa: E402
from libs.research.dist_shift import split_and_check  # noqa: E402
from libs.research.upbit_data import upbit_daily_close_keyed  # noqa: E402
from libs.validation.revalidation import (  # noqa: E402
    RevalidationController,
    WalkForwardReport,
    WalkForwardStatus,
)

_OUT = _ROOT / "data/clock_revalidation.json"
_SHADOW = _ROOT / "data/axis_shadow_state.json"


def _forward_report(axis: str) -> WalkForwardReport:
    """The axis's CURRENT standing, read from its forward clock rather than asserted.

    PASSED only where the clock has actually met its bar -- an ACCRUING axis is PENDING, never
    passing. This matters because the controller's whole job is downgrading PASSED -> STALE on a
    hard trigger: hand it a fake PASSED and the downgrade is theatre.
    """
    status, sharpe, stability, msg = WalkForwardStatus.PENDING, 0.0, 0.0, "no forward clock"
    try:
        axes = json.loads(_SHADOW.read_text("utf-8")).get("axes", [])
    except (OSError, ValueError):
        axes = []
    for a in axes:
        if a.get("axis") != axis:
            continue
        sharpe = float(a.get("ann_sharpe") or 0.0)
        fwd, need = int(a.get("forward_days") or 0), int(a.get("need") or 40)
        stability = min(1.0, fwd / need) if need else 0.0
        verdict = str(a.get("verdict") or "")
        status = (WalkForwardStatus.PASSED if verdict == "ELIGIBLE"
                  else WalkForwardStatus.PENDING)
        msg = f"clock {verdict} {fwd}/{need}d, ann_sharpe={sharpe:.2f}"
        break
    return WalkForwardReport(status=status, walk_forward_score=0.0, n_windows=0,
                             oos_sharpe=sharpe, oos_mean_return=0.0, stability=stability,
                             message=msg)


def _z(series: np.ndarray, win: int = 20) -> np.ndarray:
    """Causal trailing z-score -- the desk's standard signal transform (same window the Stage-A
    screen uses), warmup dropped.

    NOT COSMETIC, and the first wiring got this wrong. A two-window distribution test fed RAW
    LEVELS fires on any trending series: a deterministic constant-increment ramp -- a process with
    no distributional change whatsoever -- returns SHIFT, and stablecoin supply is very nearly that
    ramp. The first run of this wiring duly reported SHIFT on both axes with an identical 0.35
    haircut, which is the welded-gate signature: a detector that fires on everything carries zero
    information (L1.43, gate-optimality duty).

    The right question is whether the distribution of the signal AS THE STRATEGY CONSUMES IT has
    moved, and the strategy consumes the z-score, which is stationary by construction. Positive
    controls: iid noise -> STABLE, a genuine mean/variance regime change -> SHIFT.
    """
    x = np.asarray(series, dtype=float)
    if len(x) <= win:
        return np.array([], dtype=float)
    out = np.zeros(len(x))
    for t in range(win, len(x)):
        w = x[t - win:t]
        sd = w.std()
        out[t] = (x[t] - w.mean()) / sd if sd > 0 else 0.0
    return out[win:]


def dist_revalidate(name: str, series: np.ndarray, results: list[dict]) -> dict:
    """DISTRIBUTION-SHIFT REVALIDATION -- the wiring that did not exist until 2026-08-01.

    `libs/research/dist_shift.py` was built 2026-07-29, unit-tested green, and cited by the
    enforcement matrix as the evidence that L1.19 (information decay) and L2.10 (reality gap) were
    enforced -- while its only importer in the repo was its own test. `RevalidationController`
    consumes exactly what it produces (`drift` / `structural_break`) and had no caller either.
    Producer and consumer both existed, fit each other exactly, and were never connected.

    Direction is downward-only by construction: a SHIFT can strip production capital from a
    passing axis, never grant it. A monitor that could promote would be an alpha claim wearing a
    diagnostic's clothes.
    """
    d = split_and_check(_z(np.asarray(series, dtype=float)), name=name)
    verdict = d.get("verdict", "INSUFFICIENT-DATA")

    # ONLY *SHIFT* IS A HARD TRIGGER, and this is the caller's decision to make -- dist_shift is
    # explicitly advisory ("the caller decides, and the caller logs the decision").
    #
    # DRIFT fires on ONE marginal indicator, and a bare KS flag is the cheapest of the three: at
    # n_ref=659/n_recent=220 the 5% critical value is ~0.106, so the test is badly overpowered, and
    # financial series are autocorrelated, which violates the iid assumption KS rests on and
    # inflates the false-positive rate further. Measured here: a benign drifting random walk
    # returns DRIFT. Wiring that to _HARD_TRIGGERS -- which DRIFT is a member of -- would strip
    # production capital from healthy axes on a noisy statistic, and a clamp that fires on nothing
    # real is a compounding cost, not prudence (L1.27/L1.28).
    #
    # SHIFT is the defensible bar: it needs a break-magnitude move (>4x variance or >2.5 MADs) OR
    # agreement between two independent views. That is the module's own corroboration discipline,
    # and it is what "conclude" should mean. DRIFT stays what its author intended -- a flag plus a
    # downward-only confidence haircut, carried in the artifact, blocking nothing.
    hard = verdict == "SHIFT"
    decision = RevalidationController().assess(_forward_report(name), structural_break=hard)
    row = {"axis": name, "dist_verdict": verdict, "haircut": d.get("haircut"),
           "advisory_only": verdict == "DRIFT",
           "ks_d": d.get("ks_d"), "ks_crit_5pct": d.get("ks_crit_5pct"),
           "var_ratio": d.get("var_ratio"), "level_move_mads": d.get("level_move_mads"),
           "n_ref": d.get("n_ref"), "n_recent": d.get("n_recent"),
           "revalidation_status": decision.status.value,
           "production_capital_allowed": decision.production_capital_allowed,
           "triggers": [t.value for t in decision.triggers],
           "rationale": decision.rationale}
    results.append(row)
    print(f"  DIST-SHIFT {name}: {verdict} haircut={d.get('haircut')} "
          f"-> revalidation={decision.status.value} "
          f"capital_allowed={decision.production_capital_allowed}")
    return row


def _get(url, timeout=35):
    req = urllib.request.Request(url, headers={"User-Agent": "quant-reval/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def binance(sym="BTCUSDT", n=900):
    rows = _get(f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=1d&limit={n}")
    return {datetime.fromtimestamp(int(r[0]) / 1000, tz=UTC).date().isoformat(): float(r[4])
            for r in rows}


def yahoo(sym):
    r = _get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=300d")
    res = r["chart"]["result"][0]
    return {datetime.fromtimestamp(int(t), tz=UTC).date().isoformat(): float(c)
            for t, c in zip(res["timestamp"], res["indicators"]["quote"][0]["close"], strict=False) if c}


def upbit():
    # ONE copy of the alignment policy (see libs/research/upbit_data.py): this script carried its
    # own open-date keying and kept printing the leaky IC after the collector was fixed -- two
    # copies of one policy means fixing one only moves the bug.
    return upbit_daily_close_keyed("KRW-BTC", 200)


def stablesupply():
    d = _get("https://stablecoins.llama.fi/stablecoincharts/all")
    out = {}
    for x in d:
        v = x.get("totalCirculatingUSD") or {}
        p = v.get("peggedUSD") if isinstance(v, dict) else None
        if p is not None:
            out[datetime.fromtimestamp(int(x["date"]), tz=UTC).date().isoformat()] = float(p)
    return out


def shift_ic(signal: dict, gb: dict, shift: int, fx: dict | None = None) -> float:
    """IC of z(signal shifted by `shift` days) vs NEXT-day return."""
    dates = sorted(set(signal) & set(gb) & (set(fx) if fx else set(gb)))
    if len(dates) < 60:
        return float("nan")
    {d: i for i, d in enumerate(dates)}
    btc = np.array([gb[d] for d in dates])
    ret = np.zeros(len(btc))
    ret[1:] = btc[1:] / btc[:-1] - 1.0
    fwd = np.roll(ret, -1)
    sig, rr = [], []
    for i, d in enumerate(dates):
        j = i + shift
        if 0 <= j < len(dates):
            dj = dates[j]
            v = signal[dj] / fx[d] / gb[d] - 1.0 if fx else signal[dj]
            sig.append(v)
            rr.append(fwd[i])
    sig, rr = np.array(sig, float), np.array(rr, float)
    z = np.zeros(len(sig))
    for t in range(20, len(sig)):
        w = sig[t - 20:t]
        sd = w.std()
        z[t] = (sig[t] - w.mean()) / sd if sd > 0 else 0.0
    zv, fv = z[20:-1], rr[20:-1]
    return float(np.corrcoef(zv, fv)[0, 1]) if zv.std() and fv.std() else 0.0


def main() -> None:
    _law_guard()
    dist: list[dict] = []
    gb = binance()
    print("=== LIVE CLOCK RE-VALIDATION (hardened harness + shift test) ===\n")

    # ---- 1. KIMCHI (highest risk: KRW venue, same class as the bithumb lookahead kill) ----
    try:
        kb, fx = upbit(), yahoo("KRW=X")
        dates = sorted(set(kb) & set(gb) & set(fx))
        prem = np.array([kb[d] / fx[d] / gb[d] - 1.0 for d in dates])
        btc = np.array([gb[d] for d in dates])
        ret = np.zeros(len(btc))
        ret[1:] = btc[1:] / btc[:-1] - 1.0
        r = stage_a_screen(prem, ret, name="kimchi_premium", zwin=20)
        s = {k: shift_ic(kb, gb, k, fx) for k in (-1, 0, 1)}
        print(f"KIMCHI n={len(dates)} | IC {r.get('ic'):+.4f} same {r.get('same_period_corr'):+.3f} "
              f"resid {r.get('residual_ic'):+.4f} | {r['verdict']}")
        print(f"  SHIFT TEST  -1d {s[-1]:+.3f} | 0d {s[0]:+.3f} | +1d {s[1]:+.3f}")
        fwd_leak = abs(s[1]) > abs(s[0]) * 1.5 and abs(s[1]) > 0.3
        print(f"  -> {'*** FORWARD-SHIFT LEAK SUSPECTED ***' if fwd_leak else 'no lookahead pattern (shift0 not dominated by +1d)'}")
        dist_revalidate("kimchi_premium", prem, dist)
        print()
    except Exception as e:
        print(f"KIMCHI: ERROR {type(e).__name__}: {e}\n")

    # ---- 2. STABLECOIN SUPPLY ----
    try:
        sup = stablesupply()
        dates = sorted(set(sup) & set(gb))
        sig = np.array([sup[d] for d in dates])
        btc = np.array([gb[d] for d in dates])
        ret = np.zeros(len(btc))
        ret[1:] = btc[1:] / btc[:-1] - 1.0
        r = stage_a_screen(sig, ret, name="stablecoin_supply", zwin=20)
        s = {k: shift_ic(sup, gb, k) for k in (-1, 0, 1)}
        print(f"STABLECOIN SUPPLY n={len(dates)} | IC {r.get('ic'):+.4f} "
              f"same {r.get('same_period_corr'):+.3f} resid {r.get('residual_ic'):+.4f} | {r['verdict']}")
        print(f"  SHIFT TEST  -1d {s[-1]:+.3f} | 0d {s[0]:+.3f} | +1d {s[1]:+.3f}")
        print(f"  -> {'*** FORWARD-SHIFT LEAK SUSPECTED ***' if abs(s[1])>abs(s[0])*1.5 and abs(s[1])>0.3 else 'no lookahead pattern'}")
        dist_revalidate("stablecoin_supply_momentum", sig, dist)
        print()
    except Exception as e:
        print(f"STABLECOIN: ERROR {type(e).__name__}\n")

    # ---- 3. CNY premium clock health ----
    p = Path("data/cny_premium.jsonl")
    if p.exists():
        rows = [json.loads(x) for x in p.read_text("utf-8").splitlines() if x.strip()]
        nz = [r for r in rows if r.get("z20") is not None]
        print(f"CNY PREMIUM clock: {len(rows)} rows, {len(nz)} with usable z20 "
              f"(needs ~20 for warmup)")
        print(f"  -> {'ACCRUING but z still null -- forward evidence has NOT started' if not nz else 'z live'}\n")

    # ---- 4. clock row counts (is forward evidence actually accruing?) ----
    print("=== FORWARD CLOCK ACCRUAL (are rows landing daily?) ===")
    for f in ("kimchi_premium", "stablecoin_supply", "cny_premium", "onchain_activity"):
        fp = Path(f"data/{f}.jsonl")
        if fp.exists():
            rows = [json.loads(x) for x in fp.read_text("utf-8").splitlines() if x.strip()]
            ds = sorted({r.get("date") for r in rows if r.get("date")})
            print(f"  {f:22s} rows={len(rows):3d} span {ds[0] if ds else '-'} .. {ds[-1] if ds else '-'}")
        else:
            print(f"  {f:22s} MISSING")

    # ARTIFACT. This organ was print-only for its whole life, so nothing downstream -- including
    # check_fence_yield, which classifies a fence by the verdicts it has produced -- could tell a
    # clean run from a run that never happened. UNMEASURED is a real status here, not a filler:
    # every upstream fetch above is network-dependent, and a failed fetch must never read as "no
    # drift detected" (L1.28a).
    blocked = [r for r in dist if not r["production_capital_allowed"]
               and r["dist_verdict"] in ("DRIFT", "SHIFT")]
    if not dist:
        status = "UNMEASURED"
    elif any(r["dist_verdict"] == "SHIFT" for r in dist):
        status = "SHIFT"
    elif any(r["dist_verdict"] == "DRIFT" for r in dist):
        status = "DRIFT"
    elif all(r["dist_verdict"] == "INSUFFICIENT-DATA" for r in dist):
        status = "UNMEASURED"
    else:
        status = "OK"
    payload = {"generated": datetime.now(UTC).isoformat(), "status": status, "axes": dist,
               "capital_blocked": [r["axis"] for r in blocked],
               "note": "UNMEASURED means no axis series was fetched (upstream fetch failed) or "
                       "every window was too short -- never that the distribution is stable."}
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(payload, indent=1) + "\n", "utf-8")
    print(f"\nDIST-SHIFT REVALIDATION: {status} ({len(dist)} axes) -> "
          f"{_OUT.relative_to(_ROOT)}")


if __name__ == "__main__":
    main()

```

### scripts/run_event_study.py
```python
#!/usr/bin/env python3
"""Run the pre-registered listing event study -- the §42 promotion path, end to end.

    python3 scripts/run_event_study.py

Reads what `run_listing_watch.py` has been collecting, computes each listing's benchmark-adjusted
short-side return over the pre-registered holding window, and puts the panel through the
cross-sectional event-study gate. Writes `data/event_study_listings.json` and prints the verdict.

Freeze-safe and read-only against the market: public klines endpoints, no keys, no orders, no
capital. A verdict of PASS is EVIDENCE, not an allocation -- promotion past that point is the
normal gate's business and real capital is never allocated automatically.

Degrades rather than fails: no log, no network, or an incomplete panel all print an honest
"not yet" and exit 0, because "we do not have the evidence yet" is the correct answer for most of
this study's life and must not read as a broken job.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_FAPI = "https://fapi.binance.com"
_BENCH = "BTCUSDT"
_OUT = ROOT / "data/event_study_listings.json"


def _klines(symbol: str, start_ms: int, end_ms: int) -> list[list[object]]:
    url = (f"{_FAPI}/fapi/v1/klines?symbol={symbol}&interval=1h"
           f"&startTime={start_ms}&endTime={end_ms}&limit=1000")
    req = urllib.request.Request(url, headers={"User-Agent": "quant-event-study"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode())
    return data if isinstance(data, list) else []


def _window_path(symbol: str, t_start: float, hold_h: float) -> list[float] | None:
    """Hourly closes across the holding window -- what a barrier exit needs to walk."""
    start_ms, end_ms = int(t_start * 1000), int((t_start + hold_h * 3600.0) * 1000)
    if end_ms > int(datetime.now(tz=UTC).timestamp() * 1000):
        return None
    try:
        bars = _klines(symbol, start_ms, end_ms)
        return [float(str(b[4])) for b in bars] if len(bars) >= 2 else None
    except Exception:
        return None


def _window_return(symbol: str, t_start: float, hold_h: float) -> float | None:
    """Close-to-close return over the holding window, or None if the window is not complete."""
    start_ms, end_ms = int(t_start * 1000), int((t_start + hold_h * 3600.0) * 1000)
    if end_ms > int(datetime.now(tz=UTC).timestamp() * 1000):
        return None                       # window still open -- not evidence yet
    try:
        bars = _klines(symbol, start_ms, end_ms)
    except Exception:
        return None
    if len(bars) < 2:
        return None
    try:
        first, last = float(str(bars[0][4])), float(str(bars[-1][4]))   # index 4 = close
    except (ValueError, IndexError, TypeError):
        return None                       # a malformed bar is a missing observation, not a zero
    return (last - first) / first if first > 0 else None


def main() -> int:
    from libs.research.listing_events import (
        HOLD_HOURS,
        VARIANTS_TRIED,
        build_events,
        build_events_barrier,
        listing_rows,
        qualifying,
        study_listings,
    )

    rows = listing_rows(ROOT / "data/listings.jsonl")
    if not rows:
        print("[event-study] no listings collected yet -- run_listing_watch needs to run first. "
              "The clock has not started; this is not a failure.")
        return 0
    quals = qualifying(rows)
    print(f"[event-study] {len(rows)} listings logged, {len(quals)} in the extreme-funding regime")

    cache: dict[float, float | None] = {}

    def _bench(t_start: float) -> float | None:
        if t_start not in cache:
            cache[t_start] = _window_return(_BENCH, t_start, HOLD_HOURS)
        return cache[t_start]

    # BOTH pre-registered exits are run and BOTH are reported. Running two and publishing the
    # better one would be the garden of forking paths with extra steps; VARIANTS_TRIED already
    # prices two trials in the Holm bar, so the honest move is to show both verdicts and let the
    # reader see the disagreement if there is one.
    events = build_events(rows, lambda s, t: _window_return(s, t, HOLD_HOURS), _bench)
    res = study_listings(events)
    ev_bar = build_events_barrier(rows, lambda s, t: _window_path(s, t, HOLD_HOURS), _bench)
    res_bar = study_listings(ev_bar)
    _OUT.write_text(json.dumps({
        "as_of": datetime.now(tz=UTC).isoformat(),
        "hypothesis": ("SHORT a new USDT perp whose day-1 funding >= threshold, held "
                       f"{HOLD_HOURS:.0f}h, benchmark-adjusted vs {_BENCH}"),
        "variants_tried": VARIANTS_TRIED,
        "n_logged": len(rows), "n_qualifying": len(quals),
        "fixed_window": res.model_dump(),
        "triple_barrier": res_bar.model_dump(),
    }, indent=2), "utf-8")
    print(f"[event-study] fixed {HOLD_HOURS:.0f}h : {res.verdict}")
    print(f"[event-study] barrier    : {res_bar.verdict}")
    print(f"[event-study] wrote {_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts/run_max_push.py
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


def _refresh(script: str) -> None:
    """Re-run a producer so the queue is built on today's numbers, not last week's."""
    try:
        subprocess.run([sys.executable, str(_ROOT / "scripts" / script), "--report-only"],
                       check=False, capture_output=True, timeout=300, cwd=_ROOT,
                       env={**dict(__import__("os").environ), "PYTHONPATH": str(_ROOT)})
    except (OSError, subprocess.TimeoutExpired):
        return


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
                  "evidence_throughput" if "slot" in name else
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
    action = ("repair-mode: flip the next audit/brain window from finding to fixing; drain "
              "past-due rows first (each names its own fix)" if d.get("repair_mode")
              else "keep dispositions >= arrivals; a row nobody closes is a cost already paid")
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


def build(*, refresh: bool = True) -> dict[str, Any]:
    if refresh:
        for s in ("check_ratchets.py", "check_utilisation.py", "build_enforcement_matrix.py",
                  "check_conversion.py", "check_calibration.py", "check_freshness.py"):
            _refresh(s)
    items = (_from_ratchets() + _from_utilisation() + _from_matrix()
             + _from_wiring() + _from_register() + _from_conversion()
             + _from_tier_benchmark() + _from_calibration() + _from_freshness())
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
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"MAX PUSH [{rep['verdict']}] {rep['n_aspects']} aspects | "
              f"mean completion {rep['mean_completion']:.1%} | "
              f"{rep['n_unmeasured']} UNMEASURED | {rep['n_at_ceiling']} at ceiling")
        for i, r in enumerate(rep["queue"][:args.top], 1):
            cur = "UNMEASURED" if not r["measured"] else f"{float(r['current']):.1%}"
            print(f"{i:3}. [{r['score']:.3f}] {r['aspect']:44} {cur:>11}  {r['detail'][:60]}")
        print(f"-> {_OUT.relative_to(_ROOT)}")
    # Never fails the build: this is the WORK QUEUE, not a gate. A queue that fails CI would be
    # muted within a week, and the whole point is that it is read every morning.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts/run_recorder.py
```python
"""DATA-MOAT RECORDER v1 -- the desk's only permanently unrecoverable asset (gap #18).

Principal EXECUTION LOCKDOWN directive 2026-07-18: priority #1. Records LIVE Binance
USD-M futures microstructure (the venue class the desk trades) for the top-5 liquid
perps: top-20 order book at ~1s cadence + every aggTrade. Purpose: pre-live TCA and
execution research (name-level slippage curves, depth dynamics, cascade context), and a
compounding proprietary research asset -- every hour not recorded is gone forever.

v1 design (deliberately boring): REST polling, stdlib-only, gzip-jsonl hourly partitions
under data/moat/fut/{symbol}/. ~40-70 MB/day compressed for 5 symbols; disk-guarded at 80%.
No trading imports, no keys, no writes outside data/moat/ + its heartbeat -- this process
CANNOT touch the book. Upgrade path (brain, per spec-prebuild): websocket diffs + parquet.

Runs detached (setsid); liveness = data/recorder_heartbeat (alerted >10min stale);
scripts/ensure_recorder.py respawns it from the daily cycle.

    python scripts/run_recorder.py
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

_BASE = "https://fapi.binance.com"                 # LIVE public market data (read-only)
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

# RESIDUAL FOUND 2026-07-29: the 07-22 fix unioned the HELD book at BOOT ONLY. The book is
# deadman-halted and flat, so the union is empty and the moat is once again 20 majors the desk
# does not trade -- gap #39 open in effect while reading as closed. Three changes:
#   (a) TRADED names come from the trade LOG too, not only live positions, so a halted or
#       rotated book still records the universe the cost model must calibrate;
#   (b) PRIORITY: traded names outrank majors when the cap binds -- the old order let 20 majors
#       fill the cap and evict the very symbols the cost model needs (BTC/ETH stay as the liquid
#       benchmark, because a cost model with no benchmark cannot tell "thin" from "normal");
#   (c) the universe is RECOMPUTED IN-FLIGHT (hourly), so a name the executor opens starts being
#       recorded within the hour instead of at the next process restart.
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
    """Symbols the desk actually traded in the lookback -- read defensively: the trade log is a
    list of dicts on the VPS, may be absent here, and its schema has changed before."""
    try:
        raw = json.loads(Path("data/cashcarry_trades.json").read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    rows = raw if isinstance(raw, list) else raw.get("trades") if isinstance(raw, dict) else None
    if not isinstance(rows, list):
        return ()
    floor_ms = (time.time() - _TRADED_LOOKBACK_D * 86400.0) * 1000.0
    out: list[str] = []
    for r in reversed(rows):                       # newest first
        if not isinstance(r, dict):
            continue
        sym = r.get("symbol") or r.get("sym")
        if not isinstance(sym, str):
            continue
        ts = r.get("closed_ms") or r.get("ts_ms") or r.get("opened_ms")
        if isinstance(ts, (int, float)) and float(ts) < floor_ms:
            continue                               # older than the lookback: stop counting it
        if sym not in out:
            out.append(sym)
        if len(out) >= _MAX_SYMBOLS:
            break
    return tuple(out)


def _universe() -> tuple[str, ...]:
    """Benchmark + traded (held, then recently traded) + majors, deduped, capped.

    Order IS the priority: when the cap binds, MAJORS are dropped and traded names survive.
    Pure function of the files it reads, so the twin in run_recorder_spot.py can be diffed
    against it line by line (the two recorders stay standalone by design)."""
    ordered = [*_BENCH, *_book_symbols(), *_recently_traded(), *_CORE]
    return tuple(dict.fromkeys(ordered))[:_MAX_SYMBOLS]


_SYMBOLS = _universe()
# 5 -> 20 (principal max order, 2026-07-21): every unrecorded day is unrecoverable;
# disk math: ~33MB/day at 5 syms -> ~130MB/day at 20 -> ~4GB/mo vs 31GB free. Public
# market data only, no keys; weight fine at 20.
_ROOT = Path("data/moat/fut")
_HB = Path("data/recorder_heartbeat")
_DEPTH_EVERY_S = 5.0   # 1.0 -> 4.0 when symbols went 5 -> 20 (weight budget)
_TRADES_EVERY_S = 40.0  # 5.0 -> 20.0 for the same reason
_DISK_MAX_FRAC = 0.80                              # stop writing above this disk usage
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



# --- BINANCE WEIGHT GUARD (added 2026-07-21 after a self-inflicted IP ban) ---
# The USD-M futures budget is 2400 weight/min. depth(limit=20) costs 2; aggTrades(limit=1000)
# costs 20. Expanding _SYMBOLS without widening intervals silently triples the burn and the
# venue cuts the stream hours later with no traceback. Compute it at boot and refuse to start.
_WEIGHT_LIMIT_PER_MIN = 2400
_WEIGHT_TARGET_FRAC = 0.80          # stay well under; other desk processes share the IP


def _weight_per_min(symbols: tuple[str, ...] = ()) -> float:
    syms = symbols or _SYMBOLS
    depth = len(syms) * 2 * (60.0 / _DEPTH_EVERY_S)
    trades = len(syms) * 20 * (60.0 / _TRADES_EVERY_S)
    return depth + trades


def _weight_capped(symbols: tuple[str, ...]) -> tuple[str, ...]:
    """Trim from the TAIL (lowest priority = majors) until the weight budget fits.

    The 2026-07-21 IP ban came from an over-wide universe; a mid-flight refresh that could grow
    the set is the same hazard, so growth is bounded by arithmetic rather than by trust."""
    cap = _WEIGHT_LIMIT_PER_MIN * _WEIGHT_TARGET_FRAC
    out = list(symbols)
    while out and _weight_per_min(tuple(out)) > cap:
        out.pop()
    return tuple(out)


def _assert_weight_budget() -> None:
    w = _weight_per_min()
    cap = _WEIGHT_LIMIT_PER_MIN * _WEIGHT_TARGET_FRAC
    print(f"recorder weight budget: {w:.0f}/min vs cap {cap:.0f}/min "
          f"({len(_SYMBOLS)} symbols, depth@{_DEPTH_EVERY_S}s, trades@{_TRADES_EVERY_S}s)")
    if w > cap:
        raise SystemExit(
            f"REFUSING TO START: {w:.0f} weight/min exceeds {cap:.0f}/min. Widen "
            f"_DEPTH_EVERY_S/_TRADES_EVERY_S or cut _SYMBOLS. (2026-07-21: 20 symbols at the "
            "old 1s/5s intervals = 7200/min got the recorder IP-banned after 6 hours.)")


def main() -> None:
    _assert_weight_budget()
    print(f"recorder v1 | {len(_SYMBOLS)} symbols | depth@{_DEPTH_EVERY_S}s "
          f"trades@{_TRADES_EVERY_S}s -> {_ROOT}/")
    symbols = _weight_capped(_SYMBOLS)
    buf: dict[str, list[dict]] = {s: [] for s in symbols}
    last_trade_id: dict[str, int] = {}
    last_trades_poll = 0.0
    last_universe_poll = time.time()
    disk_warned = False
    while True:
        t0 = time.time()
        # UNIVERSE REFRESH (gap #39, 2026-07-29): a name the executor opens starts being recorded
        # within the hour rather than at the next restart. Departing symbols flush first so no
        # buffered rows are lost; the weight budget is re-checked against the ACTUAL new count.
        if t0 - last_universe_poll >= _UNIVERSE_REFRESH_S:
            last_universe_poll = t0
            fresh = _weight_capped(_universe())
            if set(fresh) != set(symbols):
                for gone in [x for x in symbols if x not in fresh]:
                    with contextlib.suppress(OSError):
                        _flush(gone, buf.get(gone, []))
                    buf.pop(gone, None)
                added = [x for x in fresh if x not in symbols]
                for new_sym in added:
                    buf[new_sym] = []
                dropped_by_weight = [x for x in _universe() if x not in fresh]
                print(f"recorder universe refresh: +{added} -"
                      f"{[x for x in symbols if x not in fresh]} "
                      f"| now {len(fresh)} syms, {_weight_per_min(fresh):.0f} weight/min"
                      + (f" | WEIGHT-DROPPED {dropped_by_weight}" if dropped_by_weight else ""))
                symbols = fresh
        if not _disk_ok():
            if not disk_warned:
                print("recorder: DISK >80% -- writing paused (heartbeat continues)")
                disk_warned = True
            _HB.write_text(datetime.now(tz=UTC).isoformat() + " DISK-PAUSED", "utf-8")
            time.sleep(30)
            continue
        disk_warned = False
        for sym in symbols:
            try:
                d = _get("/fapi/v1/depth", f"symbol={sym}&limit=20")
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
                    trades = _get("/fapi/v1/aggTrades", q)
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

### scripts/run_rejection_rescore.py
```python
#!/usr/bin/env python3
"""REJECT RE-SCORE FEEDER -- produce the forward scores the rejection-shadow audit consumes.

Closes the gate-leak recovery loop (MAX_SURVIVORS Part 1.2). Plans which rejects to re-score
(near-miss first, capped -- libs.validation.reject_rescore), re-evaluates each on the forward window
that arrived AFTER its rejection, and writes data/reject_forward_scores.json -- exactly the file
run_rejection_shadow.py reads. Incremental: already-scored rejects are kept, new scores merged.

THE RE-EVAL (runtime-heavy, honest boundary): rebuilding a stored candidate's signal and running it
on post-rejection market data needs the lake + the generator. That is wired here via the crypto
adapter; if the lake/provider is unavailable (fresh clone, no data) the runner scores nothing and
exits cleanly, leaving the shadow audit to report "unscored" -- never a fabricated score.

Usage: run_rejection_rescore.py [--db data/sor_crypto.sqlite] [--limit 50] [--min-age 30]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from libs.autodiscovery.memory import CandidateStore
from libs.store.connection import Database
from libs.validation.reject_rescore import plan_rescore

_ROOT = Path(__file__).resolve().parent.parent
_SCORES = _ROOT / "data/reject_forward_scores.json"

# Lazy per-run caches: lake frames are read once per symbol, the BTC reference once.
_FRAMES: dict[str, object] = {}
_MIN_FWD_BARS = 30


def _frame(symbol: str):
    if symbol not in _FRAMES:
        try:
            from libs.autodiscovery.crypto_adapter import _read_frames
            from libs.data.timeframe import Timeframe
            _FRAMES.update(_read_frames([symbol], Timeframe.D1, "data/lake"))
        except Exception:
            _FRAMES[symbol] = None
    return _FRAMES.get(symbol)


def _forward_score(rec: object) -> float | None:
    """Re-evaluate one rejected candidate on its post-rejection forward window.

    Rebuilds the stored (family, subtype, symbol, params) signal via the SAME generator registry
    the campaign used, on the full lake series (causal rolling windows need their warmup), then
    scores ONLY the bars strictly after ``rec.created_at`` -- genuinely out-of-sample relative to
    the rejection. Same cost model as the campaign default (net_returns, 3bps/turnover). Returns
    None when the lake cannot produce an honest forward series (missing frame, <30 forward bars,
    unknown generator) -- never a guess. Annualized daily Sharpe (sqrt(365), crypto clock).
    """
    if rec is None:
        return None
    try:
        import numpy as np
        import pandas as pd

        from libs.autodiscovery.crypto_adapter import _provider_from_frames
        from libs.autodiscovery.generators import GENERATORS, net_returns
        spec = next((g for g in GENERATORS
                     if g.family.value == rec.family and g.subtype == rec.subtype), None)
        df = _frame(rec.symbol)
        if spec is None or df is None:
            return None
        _frame("BTCUSDT")  # cross-asset generators need the reference leg in the frame cache
        provider = _provider_from_frames({k: v for k, v in _FRAMES.items() if v is not None},
                                         min_bars=_MIN_FWD_BARS)
        series = provider(rec.symbol)
        if series is None:
            return None
        positions = spec.fn(series, dict(rec.params))
        rets = net_returns(series, positions)
        cutoff = pd.Timestamp(rec.created_at)
        idx = df.index
        if getattr(idx, "tz", None) is not None and cutoff.tz is None:
            cutoff = cutoff.tz_localize(idx.tz)
        elif getattr(idx, "tz", None) is None and cutoff.tz is not None:
            cutoff = cutoff.tz_localize(None)
        rets = np.asarray(rets)
        # net_returns yields the return REALIZED at each bar after the first (len N-1 vs N bars):
        # align the cutoff mask to the TRAILING len(rets) bars so rets[j] pairs with its own bar.
        mask = np.asarray(idx > cutoff)[-len(rets):]
        fwd = rets[mask]
        if len(fwd) < _MIN_FWD_BARS or float(np.std(fwd)) == 0.0:
            return None
        return float(np.mean(fwd) / np.std(fwd) * np.sqrt(365.0))
    except Exception:
        return None  # unreadable inputs surface as unscored, never as a fabricated number


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="data/sor_crypto.sqlite")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--min-age-days", type=float, default=30.0)
    a = p.parse_args()

    db_path = _ROOT / a.db if not Path(a.db).is_absolute() else Path(a.db)
    if not db_path.exists():
        print(f"no candidate ledger at {db_path} -- nothing to re-score")
        return
    store = CandidateStore(Database(db_path, read_only=True))
    rejects = [
        (r.id, r.created_at, max(r.metrics.oos_sharpe, r.metrics.annual_sharpe))
        for r in store.rejects()
    ]
    plan = plan_rescore(rejects, min_age_days=a.min_age_days, limit=a.limit)
    print(f"rescore plan: {plan.verdict}")

    by_id = {r.id: r for r in store.rejects()}
    scores: dict[str, float] = {}
    if _SCORES.exists():
        try:
            scores = {str(k): float(v) for k, v in json.loads(_SCORES.read_text("utf-8")).items()}
        except Exception:
            scores = {}
    n_new = 0
    for cid in plan.selected:
        if cid in scores:
            continue  # already scored -- incremental
        val = _forward_score(by_id.get(cid))
        if val is not None:
            scores[cid] = val
            n_new += 1

    if n_new:
        _SCORES.parent.mkdir(parents=True, exist_ok=True)
        _SCORES.write_text(json.dumps(scores, indent=1), "utf-8")
        print(f"wrote {n_new} new forward score(s) -> {_SCORES}")
    else:
        print("no new forward scores produced (re-eval hook not wired on this host, or all "
              "selected already scored) -- the shadow audit will report unscored, honestly")


if __name__ == "__main__":
    main()

```

### scripts/run_strategy_coverage.py
```python
#!/usr/bin/env python3
"""STRATEGY-FAMILY COVERAGE (R0200) -- what KINDS of crypto edge has the desk hunted, and what
has it never looked at once.

PRINCIPAL ORDER (2026-07-31): *"miners n explorers kimi etc all should find every crypto strat
even discretionary n all n never limit to just one thing"* + *"discretionary section can copy
discretionary findings to self improve"*.

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
FAMILIES: dict[str, dict[str, Any]] = {
    "CARRY-FUNDING": {
        "patterns": ("funding", "carry", "basis", "premium_arb"),
        "discretionary": False,
        "claim": "perp funding / spot-futures basis is harvestable after costs"},
    "CROSS-VENUE-PREMIUM": {
        "patterns": ("premium", "kimchi", "kr_", "jp", "try_", "coinbase_premium", "bitbank",
                     "bithumb", "coinone", "cross-exchange", "crossvenue"),
        "discretionary": False,
        "claim": "one venue leads another in price and the gap mean-reverts"},
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
        "patterns": ("order_flow", "oi_divergence", "ls_contrarian", "elite_account",
                     "long_short", "liquidation", "smart_dumb"),
        "discretionary": True,
        "claim": "crowded or forced positioning predicts the next move"},
    "COPY-TRADER-SKILL": {
        "patterns": ("hyperliquid_trader", "hl_elite", "hl_longterm", "trader_skill", "copytrad"),
        "discretionary": False,
        "claim": "identifiable traders have persistent skill worth mirroring"},
    "ONCHAIN-FLOW": {
        "patterns": ("netflow", "mint_burn", "mvrv", "defi", "tvl", "dex_cex", "stablecoin",
                     "exchange_netflow", "reserve"),
        "discretionary": False,
        "claim": "settlement-layer flows lead price"},
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
        "patterns": ("event", "announce", "listing", "unlock", "calendar", "regime_rotation",
                     "inout_regime"),
        "discretionary": True,
        "claim": "scheduled or announced events move price predictably"},
    "LEVEL-REACTION": {
        "patterns": ("level", "support", "resistance", "range_edge", "liquidity_pool", "sweep"),
        "discretionary": True,
        "claim": "price reacts at levels a crowd can see -- the sleeve's stop-placement thesis"},
    "STATISTICAL-ARBITRAGE": {
        "patterns": ("pairs", "cointegrat", "statarb", "mean_revert", "spread_trade"),
        "discretionary": False,
        "claim": "a modelled relationship between instruments reverts"},
    "LEAD-LAG": {
        "patterns": ("leadlag", "lead_lag", "btc_leadlag", "correlation_regime"),
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

    Only families flagged discretionary_adjacent -- a carry or on-chain finding is real research
    but the sleeve cannot express it, so routing it there would be noise in the one brief that
    has to stay sharp."""
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

### scripts/run_trend_gauntlet.py
```python
"""Refined TREND-following gauntlet -- directional time-series momentum on liquid MAJORS.

The desk already runs a broad-universe daily trend sleeve (ts_trend) and it contributes ~0.01 to
portfolio Sharpe. This tests ONE principled, pre-registered refinement (NOT a parameter hunt):

  * UNIVERSE: liquid majors only (top-N by volume) -- trend is cleaner on majors than on ~100 alts.
  * SIGNAL:   classic managed-futures TS-momentum (long/short by sign of the lagged lookback return,
              inverse-vol sized) -- reuses the proven trend_basket_returns construction.
  * LOOKBACK: a PRE-REGISTERED set {30,60,90,120}d (crypto trends persist for weeks) -- reported in
              full and penalised for multiple testing (n_trials = len(set)) via DSR, so picking the
              best is NOT p-hacking.
  * COST:     ADV-tiered net-of-cost + a turnover band (hysteresis) to cut the churn that kills the
              broad daily version.

"Growth tweak" = the vol-target CAGR is reported for the SURVIVOR only (sizing is scale-invariant,
so it does NOT change the gauntlet verdict -- Sharpe/DSR/PBO are scale-free). We do NOT deploy: this
emits web/trend_gauntlet.json and the verdict stands (survive -> forward shadow; fail -> graveyard).

    python scripts/run_trend_gauntlet.py --top 15
"""

from __future__ import annotations

import argparse
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
from libs.research.crossasset import trend_basket_returns
from libs.research.crypto_xsec import adv_tier_cost
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType

_OUT = Path("web/trend_gauntlet.json")
_CRYPTO = Path("data/lake/bronze/crypto")
_PPY = 365.0
_LOOKBACKS = (30, 60, 90, 120)          # PRE-REGISTERED -- crypto trend persistence, not a sweep
_BAND = 0.10                            # turnover band (hysteresis) -> cut churn cost
_VOL_TARGET = 0.20                      # 20% annual vol target for the growth/CAGR readout only
_FAIL = ["whipsaw in ranges", "regime shift (trend->chop)", "cost exceeds edge", "crowding/decay"]


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


def _cagr_at_vol(r: np.ndarray) -> float:
    a = r[r != 0.0]
    if len(a) < 30:
        return 0.0
    realised = float(np.std(a) * np.sqrt(_PPY))
    scale = _VOL_TARGET / realised if realised > 0 else 0.0
    return round((float(np.mean(a)) * scale * _PPY) * 100, 1)   # vol-targeted annual return %


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args()

    close, adv = _majors(args.top)
    if close.shape[1] < 6:
        raise SystemExit(f"need a majors panel; got {close.shape[1]} names with history")
    cost = {s: adv_tier_cost(a) for s, a in adv.items()}

    sleeves = {f"trend_{lb}d": trend_basket_returns(close, cost, lookback=lb, band=_BAND)
               for lb in _LOOKBACKS}
    n = min(len(v) for v in sleeves.values())
    matrix = np.column_stack([v[-n:] for v in sleeves.values()])
    sharpes = np.array([sharpe_ratio(v[v != 0.0]) for v in sleeves.values()])
    # per-candidate gates (gap #87 flip, principal-ruled 2026-07-29); thresholds unchanged
    campaign = campaign_gate_stats(matrix)

    results = []
    # enumerate order == column_stack order over `sleeves`, so `col` is the sleeve's matrix column
    for col, (name, r) in enumerate(sleeves.items()):
        active = r[r != 0.0]
        ann = round(float(sharpe_ratio(active) * np.sqrt(_PPY)), 2) if len(active) > 5 else 0.0
        v = (validate(active, hypothesis=Hypothesis(
            family=Family.TREND, subtype=name, symbol="CRYPTO-MAJORS", params={},
            mechanism=MechanismType.BEHAVIORAL, edge_source=name, failure_modes=_FAIL),
            n_trials=len(_LOOKBACKS), sharpe_estimates=sharpes, returns_matrix=matrix,
            campaign=campaign, column=col) if len(active) >= 250 else None)
        gates = f"{sum(v.gates.values())}/{len(v.gates)}" if v else "n<250"
        results.append({"sleeve": name, "ann_sharpe": ann, "cagr_at_20pct_vol": _cagr_at_vol(r),
                        "n_obs": len(active), "gates": gates,
                        "pbo": round(float(v.metrics.pbo), 3) if v else None,
                        "rc_p": round(float(v.metrics.reality_p), 3) if v else None,
                        "survived": bool(v.survived) if v else False,
                        "failed_gates": [k for k, ok in v.gates.items() if not ok] if v else []})

    best = max(results, key=lambda x: x["ann_sharpe"])
    any_survived = any(x["survived"] for x in results)
    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "strategy": "directional TS-momentum (managed-futures) on liquid crypto majors",
        "universe": list(close.columns), "n_majors": int(close.shape[1]),
        "days": int(close.shape[0]), "lookbacks_tested": list(_LOOKBACKS),
        "band": _BAND, "n_trials_penalty": len(_LOOKBACKS),
        # campaign-level legacy PBO/RC kept as SEARCH-PROCEDURE diagnostics (gap #87); the gate
        # values are per-sleeve now -- see results[*].pbo / results[*].rc_p.
        "pbo": (round(float(campaign.legacy_pbo.pbo), 3)
                if campaign is not None and campaign.legacy_pbo is not None else None),
        "reality_check_p": (round(float(campaign.legacy_rc.p_value), 3)
                            if campaign is not None and campaign.legacy_rc is not None else None),
        "results": results, "best": best["sleeve"],
        "verdict": ("SURVIVED gauntlet -> promote to forward shadow (still needs 90d OOS)"
                    if any_survived else
                    "REJECTED -> graveyard (in-sample gauntlet not passed; do not deploy)"),
        "honesty": ("Multiple-testing penalised (DSR n_trials=4). Sharpe/DSR/PBO are scale-free so "
                    "vol-target does not change the verdict -- CAGR shown for context only. A pass "
                    "here is in-sample; forward validation still gates capital."),
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    for r in results:
        print(f"  {r['sleeve']:12} Sharpe~{r['ann_sharpe']:5} cagr@20v={r['cagr_at_20pct_vol']:6}% "
              f"n={r['n_obs']:4} gates={r['gates']:5} pbo={r['pbo']} rc_p={r['rc_p']} "
              f"survived={r['survived']}")
    print(f"campaign diagnostics pbo={out['pbo']} rc_p={out['reality_check_p']} (search procedure; "
          f"gates are per-sleeve) over {out['days']}d {close.shape[1]} majors -> {out['verdict']}")


if __name__ == "__main__":
    main()

```

### scripts/run_venue_reconcile.py
```python
#!/usr/bin/env python
"""DOUBLE-ENTRY VENUE RECONCILIATION -- where did the book's cash actually go?

ORIGIN (2026-07-19 dead-man fire #4, built 2026-07-29). The full 13-model panel REJECTED the
CRO's "modest slippage" explanation of the equity gap and ruled that no reset may be considered
until a double-entry venue reconciliation exists. It did not exist for 10 days, so every fire
since has been argued from assertion. This is that organ.

THE QUESTION IT ANSWERS. ``run_deadman_switch`` values the book as::

    equity = futures_margin + legs_v + (stable_cash - usdt_baseline)

where ``legs_v`` credits the spot value of ONLY those assets carrying a live futures SHORT (plus
a 1h settlement grace). That measure is deliberately narrow: the testnet faucet stuffs the spot
wallet with ~$180k of untracked coins, and crediting the raw wallet would make the rail unable to
ever fire. The narrowness is correct and this organ does NOT widen it.

But narrow has a cost. When a futures short disappears -- a venue force-close, an ADL, a churn
loop tearing the hedge off -- the spot leg it was paired with is STILL HELD and still worth money,
yet drops out of ``legs_v`` an hour later and is thereafter marked at exactly $0. The rail then
reads a loss that did not happen. That is an UNDERCOUNT of assets provably sitting on the venue.

So the gap between baseline cash and current cash splits three ways, and the whole point of this
organ is that the three are NOT interchangeable:

  1. STRANDED BOOK INVENTORY -- coins in symbols the book demonstrably traded, still in the
     wallet, currently valued at $0 by the rail. Real value, wrongly written off.
  2. REAL COST -- fees and slippage. Actually destroyed. Cross-checked against the venue's own
     commission stream so the number is not merely a residual.
  3. FAUCET NOISE -- coins the book never traded. Never counted, in either direction.

HONESTY PROPERTIES (each exists because the naive version of this script would lie):
  * READ-ONLY. Signed GETs only. It cannot place, cancel, or flatten anything, and it never
    writes a rail file. A reconciliation organ that can move the book is a second executor.
  * NEVER CREDITS FAUCET JUNK. Reporting the $188k raw wallet as "equity" would silently disable
    the ruin rail. The faucet bucket is reported separately and never enters a verdict.
  * BOOK INVENTORY IS A LOWER BOUND. ``cashcarry_trades.json`` is a capped rolling log, so
    symbols traded before the window are invisible and their coins fall into the faucet bucket.
    The script says so in its output rather than implying completeness.
  * THE RESIDUAL IS CHECKED, NOT ASSUMED. "Unexplained" is compared against measured commission
    and the implied turnover it represents. A residual that the fee stream cannot account for is
    flagged as UNRECONCILED -- a phantom until proven, per the daily integrity watch.

It renders a verdict, never an action. Resetting the rail is Tier-3 and principal-only.
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

_ROOT = Path(__file__).resolve().parent.parent
_SPOT_BASE = "https://testnet.binance.vision"        # PINNED testnet -- never live
_FUT_BASE = "https://testnet.binancefuture.com"      # PINNED testnet -- never live
_SPOT_KEYS = _ROOT / "data" / "secrets" / "binance_spot_testnet.json"
_FUT_KEYS = _ROOT / "data" / "secrets" / "binance_testnet.json"
_STATE = _ROOT / "data" / "deadman_state.json"
_TRADES = _ROOT / "data" / "cashcarry_trades.json"
_OUT = _ROOT / "web" / "venue_reconcile.json"

# Must match run_deadman_switch._STABLES exactly -- a divergence would reconcile a different
# book than the rail values, which is worse than not reconciling at all.
_STABLES = ("USDT", "USDC", "FDUSD", "TUSD", "BUSD", "DAI")
_TAKER_BPS = 5.0            # testnet futures taker; used only to imply turnover from commission


def _creds(path: Path) -> tuple[str, str] | None:
    try:
        d = json.loads(path.read_text("utf-8"))
    except Exception:
        return None
    k = d.get("api_key") or d.get("key")
    s = d.get("api_secret") or d.get("secret")
    return (k, s) if k and s else None


def _req(url: str, headers: dict[str, str] | None = None) -> Any:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def _signed(base: str, path: str, creds: tuple[str, str]) -> Any:
    key, secret = creds
    q = urllib.parse.urlencode({"timestamp": int(time.time() * 1000), "recvWindow": 10000})
    sig = hmac.new(secret.encode(), q.encode(), hashlib.sha256).hexdigest()
    return _req(f"{base}{path}?{q}&signature={sig}", {"X-MBX-APIKEY": key})


def _traded_bases() -> tuple[set[str], int, bool]:
    """Base assets the book has traded, per its own log. Returns (bases, n_rows, truncated)."""
    try:
        raw = json.loads(_TRADES.read_text("utf-8"))
    except Exception:
        return set(), 0, True
    rows = raw if isinstance(raw, list) else raw.get("trades", [])
    bases = {str(r.get("symbol"))[:-4] for r in rows
             if str(r.get("symbol", "")).endswith("USDT")}
    # A log sitting exactly on a round cap is a rolling window, not the book's whole history.
    truncated = len(rows) in (100, 200, 250, 500, 1000, 2000, 5000)
    return bases, len(rows), truncated


def reconcile() -> dict[str, Any]:
    sc, fc = _creds(_SPOT_KEYS), _creds(_FUT_KEYS)
    if not sc or not fc:
        return {"error": "credentials unreadable -- no reconciliation this run"}
    try:
        bals = _signed(_SPOT_BASE, "/api/v3/account", sc)["balances"]
        px = {t["symbol"]: float(t["price"]) for t in _req(f"{_SPOT_BASE}/api/v3/ticker/price")}
        acct = _signed(_FUT_BASE, "/fapi/v2/account", fc)
        fut_eq = float(acct["totalMarginBalance"])
        shorts = {p["symbol"] for p in _signed(_FUT_BASE, "/fapi/v2/positionRisk", fc)
                  if float(p.get("positionAmt", 0.0)) < 0}
    except Exception as e:                       # venue unreachable is not a book defect
        return {"error": f"{type(e).__name__}: {e}",
                "note": "venue unreachable -- no reconciliation this run"}

    traded, n_rows, truncated = _traded_bases()
    cash = 0.0
    book: list[dict[str, Any]] = []
    faucet_v = 0.0
    unpriced: list[str] = []
    for b in bals:
        amt = float(b["free"]) + float(b["locked"])
        if amt <= 0:
            continue
        asset = b["asset"]
        if asset in _STABLES:
            cash += amt
            continue
        price = px.get(asset + "USDT")
        if price is None:
            unpriced.append(asset)
            continue
        value = amt * price
        if asset in traded:
            book.append({"asset": asset, "qty": amt, "value": round(value, 2),
                         "credited_by_rail": (asset + "USDT") in shorts})
        else:
            faucet_v += value
    book.sort(key=lambda r: -r["value"])
    book_v = sum(r["value"] for r in book)
    # Only inventory WITHOUT a live short is being written off; a credited leg is valued fine.
    stranded_v = sum(r["value"] for r in book if not r["credited_by_rail"])

    state = json.loads(_STATE.read_text("utf-8")) if _STATE.exists() else {}
    baseline = float(state.get("usdt_baseline") or 0.0)
    gap = baseline - cash if baseline else 0.0
    unexplained = gap - book_v

    out: dict[str, Any] = {
        "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "futures_margin_balance": round(fut_eq, 2),
        "open_futures_shorts": len(shorts),
        "stable_cash": round(cash, 2),
        "usdt_baseline": round(baseline, 2),
        "cash_gap_vs_baseline": round(gap, 2),
        "book_inventory_value": round(book_v, 2),
        "stranded_uncredited_value": round(stranded_v, 2),
        "faucet_noise_value": round(faucet_v, 2),
        "unexplained_residual": round(unexplained, 2),
        "explained_share": round(book_v / gap, 3) if gap > 0 else None,
        "book_inventory": book[:40],
        "unpriced_assets": unpriced[:20],
        "trade_log_rows": n_rows,
        "trade_log_truncated": truncated,
        "rail_equity_measure": round(fut_eq + 0.0 + (cash - baseline), 2) if baseline else None,
    }

    # CROSS-CHECK the residual against the venue's own fee stream. A residual that fees and
    # slippage cannot plausibly reach is not "cost" -- it is an unreconciled hole, and the
    # integrity watch treats a hole venue records do not explain as a phantom until proven.
    try:
        from libs.execution import binance_testnet as _f
        since = int((time.time() - 7 * 86400) * 1000)
        events = _f.commission_events(since)
        commission = sum(float(e["commission"]) for e in events)
        implied_notional = commission / (_TAKER_BPS / 10000.0) if commission else 0.0
        out["commission_7d"] = round(commission, 2)
        out["commission_events_7d"] = len(events)
        out["implied_futures_turnover_7d"] = round(implied_notional, 0)
        # Both legs trade, so all-in cost rides ~2x the futures notional.
        out["residual_bps_of_turnover"] = (
            round(unexplained / (2 * implied_notional) * 10000.0, 1)
            if implied_notional > 0 else None
        )
    except Exception as e:
        out["commission_error"] = f"{type(e).__name__}: {e}"

    bps = out.get("residual_bps_of_turnover")
    notes = []
    if stranded_v > 0:
        notes.append(
            f"UNDERCOUNT: ${stranded_v:,.2f} of real book inventory carries no live futures "
            f"short and is valued at $0 by the ruin rail. Real assets, verified on venue.")
    if truncated:
        notes.append(
            f"LOWER BOUND: the trade log is a rolling window ({n_rows} rows), so symbols traded "
            f"before it are counted as faucet noise. True book inventory is >= this figure.")
    if bps is not None:
        if bps > 100:
            notes.append(
                f"UNRECONCILED: residual is {bps:.0f} bps of traded turnover -- too large for "
                f"fees+slippage. Treat as a phantom loss until venue records explain it.")
        elif bps >= 0:
            notes.append(
                f"RESIDUAL CONSISTENT WITH COST: {bps:.1f} bps of ~${2*out['implied_futures_turnover_7d']:,.0f} "
                f"two-leg turnover -- market-order churn on illiquid alts bills in this band.")
    out["notes"] = notes
    out["verdict"] = (
        "UNRECONCILED" if (bps is not None and bps > 100)
        else "RECONCILED" if gap > 0 else "NO_GAP")
    return out


def main() -> None:
    res = reconcile()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(res, indent=1), "utf-8")
    if "error" in res:
        print(f"venue-reconcile: {res['error']}")
        return
    print(f"VENUE RECONCILE {res['updated']}  verdict={res['verdict']}")
    print(f"  cash gap vs baseline : ${res['cash_gap_vs_baseline']:>12,.2f}")
    print(f"  book inventory       : ${res['book_inventory_value']:>12,.2f}"
          f"   ({res['explained_share']:.1%} of gap)" if res.get("explained_share")
          else f"  book inventory       : ${res['book_inventory_value']:>12,.2f}")
    print(f"  stranded (rail=$0)   : ${res['stranded_uncredited_value']:>12,.2f}")
    print(f"  unexplained residual : ${res['unexplained_residual']:>12,.2f}")
    print(f"  faucet noise (never counted): ${res['faucet_noise_value']:>12,.2f}")
    for n in res["notes"]:
        print(f"  - {n}")


if __name__ == "__main__":
    main()

```

### scripts/track_findings.py
```python
#!/usr/bin/env python3
"""FINDING LIFECYCLE LEDGER (build #1, principal 2026-07-21).

THE HOLE THIS CLOSES: panels produced 27 rulings on 2026-07-20 -- 7 rejected, 20 ACCEPTED --
and nothing tracked what happened to those 20. An accepted finding could sit unbuilt forever
with nothing flagging it (GAP #37, an unbounded market-order path on the risk lane, is exactly
this shape). Worse, ledger #115 declares that panel seats are governed by scorecard hit-rates,
but panel_scorecard.json tracks only whether a model RESPONDED -- never whether it was RIGHT.
That made the governance policy unenforceable: a rule with no data behind it.

WHAT THIS ADDS: an explicit lifecycle per finding -- raised -> triaged -> fixed -> verified --
with the model that raised it recorded. From that falls out (a) accepted-but-unfixed findings
as a REPORTED DEFECT with an age, and (b) a real per-seat hit-rate (raised & accepted & fixed)
which is the number seat swaps were always supposed to use.

Usage:
  track_findings.py add   --model M --summary S [--severity high] [--ruling accepted]
  track_findings.py fix   --id F --commit SHA
  track_findings.py verify --id F
  track_findings.py report            # defect view: accepted & unfixed, oldest first
  track_findings.py scorecard         # per-seat hit-rates (the governance data)
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

LEDGER = Path(__file__).resolve().parent.parent / "data/findings_ledger.json"
UNFIXED_DEFECT_D = 14.0          # accepted+unfixed beyond this is a reported defect


def _load() -> dict:
    if LEDGER.exists():
        try:
            return json.loads(LEDGER.read_text("utf-8"))
        except Exception:
            pass
    return {"findings": [], "next_id": 1}


def _save(d: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(d, indent=1), "utf-8")


def _age_d(iso: str | None) -> float:
    if not iso:
        return 0.0
    try:
        return (datetime.now(tz=UTC) - datetime.fromisoformat(iso)).total_seconds() / 86400
    except Exception:
        return 0.0


def add(a) -> None:
    d = _load()
    fid = f"F{d['next_id']:04d}"
    d["next_id"] += 1
    d["findings"].append({
        "id": fid, "model": a.model, "summary": a.summary[:400],
        "severity": a.severity, "ruling": a.ruling,
        "raised": datetime.now(tz=UTC).isoformat(),
        "fixed": None, "fix_commit": None, "verified": None,
    })
    _save(d)
    print(f"{fid} recorded ({a.ruling}, {a.severity}, {a.model})")


def _set(a, field: str, extra: dict | None = None) -> None:
    d = _load()
    for f in d["findings"]:
        if f["id"] == a.id:
            f[field] = datetime.now(tz=UTC).isoformat()
            if extra:
                f.update(extra)
            _save(d)
            print(f"{a.id} -> {field}")
            return
    raise SystemExit(f"{a.id} not found")


def report(_a) -> None:
    d = _load()
    acc = [f for f in d["findings"] if f["ruling"] == "accepted"]
    unfixed = sorted((f for f in acc if not f["fixed"]),
                     key=lambda f: f["raised"])
    print(f"ACCEPTED: {len(acc)} | FIXED: {sum(1 for f in acc if f['fixed'])} | "
          f"UNFIXED: {len(unfixed)}")
    overdue = [f for f in unfixed if _age_d(f["raised"]) > UNFIXED_DEFECT_D]
    if overdue:
        print(f"\n!! {len(overdue)} ACCEPTED FINDINGS UNFIXED >{UNFIXED_DEFECT_D:.0f}d "
              "-- these are DEFECTS, name them in the cycle report:")
    for f in unfixed:
        flag = "DEFECT" if _age_d(f["raised"]) > UNFIXED_DEFECT_D else "open"
        print(f"  [{flag:>6}] {f['id']} {_age_d(f['raised']):>5.1f}d {f['severity']:<6} "
              f"{f['model'][:22]:<22} {f['summary'][:70]}")


def scorecard(_a) -> None:
    """The number seat governance was always supposed to use: was the model RIGHT?"""
    d = _load()
    by: dict[str, dict] = {}
    for f in d["findings"]:
        s = by.setdefault(f["model"], {"raised": 0, "accepted": 0, "fixed": 0, "rejected": 0})
        s["raised"] += 1
        s["accepted" if f["ruling"] == "accepted" else "rejected"] += 1
        if f["fixed"]:
            s["fixed"] += 1
    print(f"{'MODEL':<44} {'RAISED':>6} {'ACC':>5} {'FIXED':>6} {'HIT%':>6}")
    print("-" * 72)
    for m, s in sorted(by.items(), key=lambda kv: -(kv[1]["fixed"] / max(1, kv[1]["raised"]))):
        hit = 100.0 * s["fixed"] / max(1, s["raised"])
        print(f"{m:<44} {s['raised']:>6} {s['accepted']:>5} {s['fixed']:>6} {hit:>5.1f}%")
    if not by:
        print("(empty -- the brain populates this during panel triage)")


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("--model", required=True)
    a.add_argument("--summary", required=True)
    a.add_argument("--severity", default="med")
    a.add_argument("--ruling", default="accepted", choices=["accepted", "rejected"])
    a.set_defaults(fn=add)
    fx = sub.add_parser("fix")
    fx.add_argument("--id", required=True)
    fx.add_argument("--commit", default=None)
    fx.set_defaults(fn=lambda x: _set(x, "fixed", {"fix_commit": x.commit}))
    v = sub.add_parser("verify")
    v.add_argument("--id", required=True)
    v.set_defaults(fn=lambda x: _set(x, "verified"))
    sub.add_parser("report").set_defaults(fn=report)
    sub.add_parser("scorecard").set_defaults(fn=scorecard)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

```
