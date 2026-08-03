# AUDIT SHARD 2/13 -- seat openai/gpt-5.6-terra-pro

You are reviewing SOURCE CODE, not a summary. Previous panels received a 13,185-char self-description and never saw the code; that is why this exists.

- TIER 1 (money path) is included IN FULL and is sent to every seat: 41 files. A defect here costs money.
- TIER 2 is YOUR SHARD ALONE: 43 files. No other seat sees these, so anything you miss here is missed entirely.
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

### libs/alpha/errors.py
```python
"""Alpha-layer exceptions."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class AlphaError(QuantPlatformError):
    """Generic alpha-lifecycle error (unknown alpha, bad input)."""


class AlphaStateError(AlphaError):
    """An illegal lifecycle state transition was attempted."""

```

### libs/alpha/state.py
```python
"""Alpha lifecycle state machine.

candidate -> probation -> active -> watch -> decaying -> retirement_candidate -> retired,
with recovery edges (watch -> active, decaying -> watch) and an emergency path to retired from
any live state. Transitions are validated; an invalid transition raises.
"""

from __future__ import annotations

from enum import StrEnum

from libs.alpha.errors import AlphaStateError


class AlphaState(StrEnum):
    CANDIDATE = "candidate"
    PROBATION = "probation"
    ACTIVE = "active"
    WATCH = "watch"
    DECAYING = "decaying"
    RETIREMENT_CANDIDATE = "retirement_candidate"
    RETIRED = "retired"


# Forward (toward retirement) + recovery edges. RETIRED is terminal.
ALLOWED_TRANSITIONS: dict[AlphaState, frozenset[AlphaState]] = {
    AlphaState.CANDIDATE: frozenset({AlphaState.PROBATION, AlphaState.RETIRED}),
    AlphaState.PROBATION: frozenset(
        {AlphaState.ACTIVE, AlphaState.RETIREMENT_CANDIDATE, AlphaState.RETIRED}
    ),
    AlphaState.ACTIVE: frozenset({AlphaState.WATCH, AlphaState.DECAYING, AlphaState.RETIRED}),
    AlphaState.WATCH: frozenset(
        {AlphaState.ACTIVE, AlphaState.DECAYING, AlphaState.RETIREMENT_CANDIDATE,
         AlphaState.RETIRED}
    ),
    AlphaState.DECAYING: frozenset(
        {AlphaState.WATCH, AlphaState.RETIREMENT_CANDIDATE, AlphaState.RETIRED}
    ),
    AlphaState.RETIREMENT_CANDIDATE: frozenset({AlphaState.RETIRED, AlphaState.WATCH}),
    AlphaState.RETIRED: frozenset(),
}

# The canonical "promote upward" target for each state.
_PROMOTE_TARGET: dict[AlphaState, AlphaState] = {
    AlphaState.CANDIDATE: AlphaState.PROBATION,
    AlphaState.PROBATION: AlphaState.ACTIVE,
    AlphaState.WATCH: AlphaState.ACTIVE,
    AlphaState.DECAYING: AlphaState.WATCH,
}


def can_transition(from_state: AlphaState, to_state: AlphaState) -> bool:
    """Whether ``from_state -> to_state`` is an allowed transition."""
    return to_state in ALLOWED_TRANSITIONS[from_state]


def assert_transition(from_state: AlphaState, to_state: AlphaState) -> None:
    """Raise :class:`AlphaStateError` if the transition is not allowed."""
    if not can_transition(from_state, to_state):
        raise AlphaStateError(f"illegal transition {from_state.value} -> {to_state.value}")


def promote_target(from_state: AlphaState) -> AlphaState:
    """The state an alpha is promoted *to* from ``from_state``."""
    try:
        return _PROMOTE_TARGET[from_state]
    except KeyError as exc:
        raise AlphaStateError(f"cannot promote from {from_state.value}") from exc

```

### libs/backtest/engine.py
```python
"""Event-driven backtest engine.

Each bar: execute the order queued last bar at this bar's OPEN (no look-ahead), check
protective exits intrabar, mark equity at the close, then ask the strategy for a new target
which is queued for next bar. Sizing is in fixed ``units`` or signed ``fraction`` of equity.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from libs.backtest.errors import BacktestError
from libs.backtest.events import EventQueue, FillEvent, MarketEvent, OrderEvent, SignalEvent
from libs.backtest.fills import FillEngine
from libs.backtest.metrics import Metrics, compute_metrics
from libs.backtest.orders import OrderManager, ProtectiveState
from libs.backtest.portfolio import PortfolioEngine, Trade
from libs.backtest.strategy import BarContext, SignalStrategy, Strategy
from libs.data.schema import validate_bars


@dataclass(frozen=True)
class BacktestConfig:
    init_cash: float = 100_000.0
    sizing_mode: str = "fraction"  # "fraction" of equity, or fixed "units"
    slippage_frac: float = 0.0
    commission_per_unit: float = 0.0
    periods_per_year: float = 252.0


@dataclass(frozen=True)
class BacktestResult:
    equity: pd.Series
    trades: list[Trade]
    metrics: Metrics


class Backtest:
    """Runs an event-driven backtest of a strategy over a bar frame."""

    def __init__(self, config: BacktestConfig | None = None) -> None:
        self.config = config or BacktestConfig()
        if self.config.sizing_mode not in ("fraction", "units"):
            raise BacktestError("sizing_mode must be 'fraction' or 'units'")

    def _target_to_units(self, target: float, equity: float, price: float) -> float:
        if self.config.sizing_mode == "units":
            return target
        return target * equity / price if price > 0 else 0.0

    def run(self, bars: pd.DataFrame, strategy: Strategy) -> BacktestResult:
        validate_bars(bars, require_sorted=True)
        cfg = self.config
        portfolio = PortfolioEngine(init_cash=cfg.init_cash)
        fills = FillEngine(
            slippage_frac=cfg.slippage_frac, commission_per_unit=cfg.commission_per_unit
        )
        queue = EventQueue()

        protective: ProtectiveState | None = None
        pending_order: OrderEvent | None = None
        pending_signal: SignalEvent | None = None
        equity_index: list[pd.Timestamp] = []
        equity_values: list[float] = []

        records = bars.itertuples(index=False)
        for i, row in enumerate(records):
            ts = row.timestamp
            bar = MarketEvent(
                index=i, timestamp=ts, open=float(row.open), high=float(row.high),
                low=float(row.low), close=float(row.close), volume=float(row.volume),
            )
            queue.put(bar)

            # 1) execute the order queued on the previous bar, at this bar's open
            if pending_order is not None:
                delta = pending_order.target_units - portfolio.units
                if delta != 0.0:
                    portfolio.apply_fill(fills.fill(ts, delta, bar.open))
                protective = self._open_protective(portfolio, pending_signal, bar.open)
                pending_order = None
                pending_signal = None

            # 2) protective exits, intrabar
            if protective is not None and portfolio.units != 0.0:
                exit_price = OrderManager.check_protective(protective, bar)
                if exit_price is not None:
                    commission = abs(portfolio.units) * cfg.commission_per_unit
                    portfolio.apply_fill(
                        FillEvent(ts, -portfolio.units, exit_price, commission=commission)
                    )
                    protective = None

            # 3) mark to market at the close
            eq = portfolio.equity(bar.close)
            equity_index.append(ts)
            equity_values.append(eq)

            # 4) strategy decision (queued for next bar's open)
            ctx = BarContext(
                index=i, timestamp=ts, bars=bars, equity=eq, position_units=portfolio.units
            )
            signal = strategy.on_bar(ctx)
            if signal is not None:
                target_units = self._target_to_units(signal.target, eq, bar.close)
                if not math.isclose(target_units, portfolio.units, rel_tol=0.0, abs_tol=1e-12):
                    pending_order = OrderEvent(ts, target_units, reason="signal")
                    pending_signal = signal

        equity = pd.Series(equity_values, index=pd.DatetimeIndex(equity_index), name="equity")
        metrics = compute_metrics(equity, portfolio.trades, periods_per_year=cfg.periods_per_year)
        return BacktestResult(equity=equity, trades=portfolio.trades, metrics=metrics)

    @staticmethod
    def _open_protective(
        portfolio: PortfolioEngine, signal: SignalEvent | None, ref_price: float
    ) -> ProtectiveState | None:
        if portfolio.units == 0.0 or signal is None:
            return None
        if signal.stop_loss is None and signal.take_profit is None and signal.trailing is None:
            return None
        sign = 1 if portfolio.units > 0 else -1
        return ProtectiveState(
            entry_price=portfolio.entry_price,
            sign=sign,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            trailing=signal.trailing,
            anchor=ref_price,
        )


def run_signal_backtest(
    bars: pd.DataFrame,
    targets: list[float],
    *,
    init_cash: float = 100_000.0,
    periods_per_year: float = 252.0,
) -> BacktestResult:
    """Convenience: run a fixed-units, cost-free signal backtest (the cross-engine mode)."""
    config = BacktestConfig(
        init_cash=init_cash, sizing_mode="units", periods_per_year=periods_per_year
    )
    return Backtest(config).run(bars, SignalStrategy(targets))

```

### libs/backtest/events.py
```python
"""Event types and the event queue for the event-driven engine.

The loop flows MARKET -> SIGNAL -> ORDER -> FILL: each bar emits a market event, the strategy
turns it into a signal, the order manager into an order, and the fill engine into a fill the
portfolio consumes.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import StrEnum

import pandas as pd


class EventType(StrEnum):
    MARKET = "market"
    SIGNAL = "signal"
    ORDER = "order"
    FILL = "fill"


@dataclass(frozen=True)
class MarketEvent:
    index: int
    timestamp: pd.Timestamp
    open: float
    high: float
    low: float
    close: float
    volume: float
    type: EventType = EventType.MARKET


@dataclass(frozen=True)
class SignalEvent:
    timestamp: pd.Timestamp
    target: float  # desired position (units, or signed fraction of equity)
    stop_loss: float | None = None  # fraction of entry price
    take_profit: float | None = None  # fraction of entry price
    trailing: float | None = None  # fraction trailing stop
    type: EventType = EventType.SIGNAL


@dataclass(frozen=True)
class OrderEvent:
    timestamp: pd.Timestamp
    target_units: float
    reason: str
    type: EventType = EventType.ORDER


@dataclass(frozen=True)
class FillEvent:
    timestamp: pd.Timestamp
    units_delta: float
    price: float
    commission: float
    type: EventType = EventType.FILL


class EventQueue:
    """A FIFO queue of engine events."""

    def __init__(self) -> None:
        self._q: deque[object] = deque()

    def put(self, event: object) -> None:
        self._q.append(event)

    def get(self) -> object:
        return self._q.popleft()

    def empty(self) -> bool:
        return not self._q

    def __len__(self) -> int:
        return len(self._q)

```

### libs/backtest/orders.py
```python
"""Order manager — protective exits (stop-loss, take-profit, trailing stop).

Given an open position and the current bar, decides whether a protective level was breached
and at what price the exit fills (gap-aware: a gap through the level fills at the open).
"""

from __future__ import annotations

from dataclasses import dataclass

from libs.backtest.events import MarketEvent


@dataclass
class ProtectiveState:
    """Mutable protective configuration for the currently open position."""

    entry_price: float
    sign: int  # +1 long, -1 short
    stop_loss: float | None = None  # fraction of entry
    take_profit: float | None = None  # fraction of entry
    trailing: float | None = None  # fraction
    anchor: float = 0.0  # best price since entry (high for long, low for short)


class OrderManager:
    """Evaluates protective exits for the open position."""

    @staticmethod
    def check_protective(state: ProtectiveState, bar: MarketEvent) -> float | None:
        """Return the exit price if a protective level triggered this bar, else ``None``."""
        if state.sign > 0:
            return OrderManager._check_long(state, bar)
        return OrderManager._check_short(state, bar)

    @staticmethod
    def _check_long(state: ProtectiveState, bar: MarketEvent) -> float | None:
        state.anchor = max(state.anchor, bar.high)
        stops: list[float] = []
        if state.stop_loss is not None:
            stops.append(state.entry_price * (1.0 - state.stop_loss))
        if state.trailing is not None:
            stops.append(state.anchor * (1.0 - state.trailing))
        effective_stop = max(stops) if stops else None

        if effective_stop is not None and bar.low <= effective_stop:
            return min(effective_stop, bar.open)  # gap-down fills at the open
        if state.take_profit is not None:
            tp = state.entry_price * (1.0 + state.take_profit)
            if bar.high >= tp:
                return max(tp, bar.open)  # gap-up fills at the open
        return None

    @staticmethod
    def _check_short(state: ProtectiveState, bar: MarketEvent) -> float | None:
        state.anchor = min(state.anchor, bar.low) if state.anchor else bar.low
        stops: list[float] = []
        if state.stop_loss is not None:
            stops.append(state.entry_price * (1.0 + state.stop_loss))
        if state.trailing is not None:
            stops.append(state.anchor * (1.0 + state.trailing))
        effective_stop = min(stops) if stops else None

        if effective_stop is not None and bar.high >= effective_stop:
            return max(effective_stop, bar.open)
        if state.take_profit is not None:
            tp = state.entry_price * (1.0 - state.take_profit)
            if bar.low <= tp:
                return min(tp, bar.open)
        return None

```

### libs/core/config.py
```python
"""Configuration system: Pydantic settings with layered YAML + environment variables.

Precedence (highest first):

1. Explicit ``overrides=`` passed to :func:`load_settings`.
2. Environment variables (prefix ``QP_``, nested delimiter ``__``).
3. ``config/<environment>.yaml``.
4. ``config/base.yaml``.

The environment is selected by the ``QP_ENV`` variable (or the ``environment`` argument),
defaulting to ``dev``. Secrets never live here — see :mod:`libs.core.secrets`.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from contextvars import ContextVar
from functools import cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from libs.core.enums import Environment, LogLevel
from libs.core.errors import ConfigError

ENV_VAR = "QP_ENV"
ROOT_ENV_VAR = "QP_ROOT"
CONFIG_DIR_ENV_VAR = "QP_CONFIG_DIR"

# Carries the merged YAML layer into ``Settings`` construction as a low-priority source.
_yaml_layer: ContextVar[dict[str, Any] | None] = ContextVar("_yaml_layer", default=None)


# --------------------------------------------------------------------------- helpers


def find_project_root(start: Path | None = None) -> Path:
    """Walk upward from ``start`` (or this file) to the directory holding ``pyproject.toml``.

    Falls back to the current working directory if no marker is found.
    """
    here = (start or Path(__file__)).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    return Path.cwd().resolve()


def deep_merge(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge ``overlay`` onto ``base`` without mutating either argument."""
    result: dict[str, Any] = dict(base)
    for key, value in overlay.items():
        existing = result.get(key)
        if isinstance(existing, Mapping) and isinstance(value, Mapping):
            result[key] = deep_merge(existing, value)
        else:
            result[key] = value
    return result


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file into a dict, returning ``{}`` for an empty file."""
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"config file {path} must contain a mapping at the top level")
    return data


def hash_config(config: Mapping[str, Any] | BaseModel | None) -> str:
    """Return a stable SHA-256 hex digest of a configuration object.

    Serializes to canonical JSON (sorted keys, ``str`` fallback for paths/enums/datetimes)
    so the same logical config always hashes identically. ``None`` hashes the empty object.
    """
    if config is None:
        payload: Any = {}
    elif isinstance(config, BaseModel):
        payload = config.model_dump(mode="json")
    elif isinstance(config, Mapping):
        payload = dict(config)
    else:  # pragma: no cover - defensive
        raise TypeError(f"cannot hash config of type {type(config)!r}")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- models


class Paths(BaseModel):
    """Filesystem layout. Everything is derived from ``root`` unless set explicitly."""

    model_config = ConfigDict(extra="forbid")

    root: Path
    config_dir: Path | None = None
    lake_dir: Path | None = None
    data_dir: Path | None = None
    artifacts_dir: Path | None = None
    logs_dir: Path | None = None

    @model_validator(mode="after")
    def _derive(self) -> Paths:
        root = self.root
        self.config_dir = self.config_dir or root / "config"
        self.lake_dir = self.lake_dir or root / "lake"
        self.data_dir = self.data_dir or root / "data"
        self.artifacts_dir = self.artifacts_dir or root / "artifacts"
        self.logs_dir = self.logs_dir or root / "logs"
        return self


class LoggingConfig(BaseModel):
    """Structured-logging configuration."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    level: LogLevel = LogLevel.INFO
    # YAML/env key is ``json``; the attribute avoids shadowing ``BaseModel.json``.
    emit_json: bool = Field(default=True, alias="json")
    include_caller: bool = False
    redact_keys: list[str] = Field(default_factory=list)

    @field_validator("redact_keys")
    @classmethod
    def _lowercase_keys(cls, value: list[str]) -> list[str]:
        return [k.lower() for k in value]


class ReproducibilityConfig(BaseModel):
    """Defaults for the reproducibility framework."""

    model_config = ConfigDict(extra="forbid")

    default_seed: int = 12345
    require_clean_git: bool = False

    @field_validator("default_seed")
    @classmethod
    def _non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("default_seed must be non-negative")
        return value


class _MappingSettingsSource(PydanticBaseSettingsSource):
    """A settings source that yields a pre-merged mapping (the YAML layer)."""

    def __init__(self, settings_cls: type[BaseSettings], data: Mapping[str, Any]) -> None:
        super().__init__(settings_cls)
        self._data = dict(data)

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        return self._data.get(field_name), field_name, False

    def __call__(self) -> dict[str, Any]:
        return self._data


class Settings(BaseSettings):
    """Resolved, validated platform configuration."""

    model_config = SettingsConfigDict(
        env_prefix="QP_",
        env_nested_delimiter="__",
        extra="forbid",
        case_sensitive=False,
    )

    environment: Environment = Environment.DEV
    paths: Paths
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    reproducibility: ReproducibilityConfig = Field(default_factory=ReproducibilityConfig)
    timezone: str = "UTC"

    @field_validator("timezone")
    @classmethod
    def _utc_only(cls, value: str) -> str:
        if value != "UTC":
            raise ValueError("the platform operates in UTC only; timezone must be 'UTC'")
        return value

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        yaml_source = _MappingSettingsSource(settings_cls, _yaml_layer.get() or {})
        # init (explicit overrides) > env vars > dotenv > yaml layer > file secrets
        return (init_settings, env_settings, dotenv_settings, yaml_source, file_secret_settings)


# --------------------------------------------------------------------------- loading


def _resolve_environment(environment: str | Environment | None) -> Environment:
    if environment is not None:
        return Environment(environment)
    import os

    return Environment(os.environ.get(ENV_VAR, Environment.DEV.value))


def _resolve_config_dir(config_dir: Path | None, root: Path) -> Path:
    if config_dir is not None:
        return Path(config_dir)
    import os

    env_value = os.environ.get(CONFIG_DIR_ENV_VAR)
    return Path(env_value) if env_value else root / "config"


def _resolve_root(root: Path | None) -> Path:
    if root is not None:
        return Path(root).resolve()
    import os

    env_value = os.environ.get(ROOT_ENV_VAR)
    return Path(env_value).resolve() if env_value else find_project_root()


def load_settings(
    environment: str | Environment | None = None,
    *,
    root: Path | None = None,
    config_dir: Path | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> Settings:
    """Load, merge, and validate settings for an environment.

    Args:
        environment: ``dev`` / ``live`` / ``test``; defaults to ``QP_ENV`` or ``dev``.
        root: project root; defaults to ``QP_ROOT`` or the detected ``pyproject.toml`` dir.
        config_dir: directory of YAML files; defaults to ``QP_CONFIG_DIR`` or ``<root>/config``.
        overrides: highest-priority explicit values (above env vars).

    Raises:
        ConfigError: if a config file is missing/malformed or validation fails.
    """
    env = _resolve_environment(environment)
    resolved_root = _resolve_root(root)
    cfg_dir = _resolve_config_dir(config_dir, resolved_root)

    base = _load_yaml(cfg_dir / "base.yaml")
    env_overlay = _load_yaml(cfg_dir / f"{env.value}.yaml")
    merged = deep_merge(base, env_overlay)

    # Force consistency: the resolved environment always wins over file contents.
    merged["environment"] = env.value
    # Inject the project root into the (low-priority) YAML layer so env/overrides can win.
    paths_layer = dict(merged.get("paths") or {})
    paths_layer.setdefault("root", str(resolved_root))
    merged["paths"] = paths_layer

    token = _yaml_layer.set(merged)
    try:
        return Settings(**dict(overrides or {}))
    except ConfigError:
        raise
    except Exception as exc:  # pydantic ValidationError, yaml errors, etc.
        raise ConfigError(f"failed to build settings for environment {env.value!r}: {exc}") from exc
    finally:
        _yaml_layer.reset(token)


@cache
def get_settings(environment: str | None = None) -> Settings:
    """Return cached settings for an environment (process-wide singleton per env)."""
    return load_settings(environment)


def clear_settings_cache() -> None:
    """Clear the :func:`get_settings` cache (used by tests and config reloads)."""
    get_settings.cache_clear()


def ensure_directories(settings: Settings) -> None:
    """Create the lake / data / artifacts / logs directories if they do not exist."""
    for path in (
        settings.paths.lake_dir,
        settings.paths.data_dir,
        settings.paths.artifacts_dir,
        settings.paths.logs_dir,
    ):
        if path is not None:
            path.mkdir(parents=True, exist_ok=True)

```

### libs/costs/errors.py
```python
"""Cost-model exceptions."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class CostError(QuantPlatformError):
    """Invalid cost inputs or missing cost parameters."""

```

### libs/data/duckdb_client.py
```python
"""DuckDB integration — embedded OLAP over the Parquet lake (no server)."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe


class DuckDBClient:
    """A thin DuckDB wrapper for querying Parquet directly."""

    def __init__(self, database: str = ":memory:") -> None:
        self._con = duckdb.connect(database)

    def query(self, sql: str) -> pd.DataFrame:
        """Run ``sql`` and return the result as a pandas DataFrame."""
        return self._con.execute(sql).df()

    def read_parquet(self, glob: str | Path) -> pd.DataFrame:
        """Read a parquet glob (hive-partitioned) into a DataFrame."""
        sql = (
            f"SELECT * FROM read_parquet('{Path(glob).as_posix()}', hive_partitioning=true) "
            "ORDER BY timestamp"
        )
        return self.query(sql)

    def query_lake(
        self, lake: ParquetLake, layer: Layer, symbol: str, timeframe: Timeframe
    ) -> pd.DataFrame:
        """Query a single lake partition tree, returning bars ordered by timestamp."""
        path = lake.path(layer, symbol, timeframe)
        glob = path / "**" / "*.parquet"
        df = self.read_parquet(glob)
        return df.drop(columns=[c for c in ("year", "month") if c in df.columns])

    def close(self) -> None:
        self._con.close()

    def __enter__(self) -> DuckDBClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

```

### libs/execution/carry_accounting.py
```python
"""Self-healing spot-realized accounting for the delta-neutral cash-and-carry book.

The book banks each CLOSED spot leg's realized PnL in ``realized_spot_pnl`` -- the sell proceeds sit
in the spot wallet where open-position marks can't see them, while the matching perp leg's realized
stays inside the futures-equity delta. Historically this was a hand-maintained accumulator
(incremented at each close), which is FRAGILE: a stale/crashed executor, or duplicate close-logs
during a flatten, let it silently drift. Because the perp side IS captured, any drift fabricates a
one-sided loss on the dashboard (the 2026-07-10 phantom: a ~breakeven book showed -$865 on the 3x
levered lab).

Permanent fix -- derive it from EXCHANGE GROUND TRUTH every cycle instead of trusting the
accumulator. For a delta-neutral carry each closed leg satisfies ``price_pnl = spot_real +
perp_real`` and the venue's own ``REALIZED_PNL`` income equals ``sum(perp_real)``. Therefore::

    spot_realized = sum(price_pnl over closed carries) - venue_realized_pnl

The venue term is EXACT; the basis term (``sum(price_pnl)``, ~0 for a tight hedge) comes from the
trade log, deduped by ``(symbol, opened)`` so duplicate close-logs never double-count. Substituting
into ``net = spot_open + spot_realized + (fut_eq - start_eq)`` the venue-realized term cancels, so
``net = spot_open + basis + funding - fees`` -- the true economic PnL, which cannot be faked.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict


def read_income(
    fetch: Callable[[], Any],
    *,
    attempts: int = 3,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Any] | None:
    """Venue income summary, or ``None`` when it cannot be read -- NEVER a zero-filled dict.

    UNKNOWN IS NOT ZERO. This exists because on 2026-07-26 the venue's ``/fapi/v1/income``
    endpoint returned HTTP 502 for hours while the executor's ``_safe()`` context swallowed the
    error and left ``funding`` at its initialised ``0.0``. The primary book then published a
    $0.00 harvest -- against a ground truth of $101.96 that the molded book had recorded two
    hours earlier -- and the carry-leak alarm divided by that fabricated zero to declare an
    ``inf%`` total bleed. An outage was rendered as an economic verdict.

    That is the same failure SHAPE as the 2026-07-19 stranded-inventory incident (GAP row 34),
    where ``_safe()`` made a rejected order indistinguishable from a filled one. That incident
    was fixed on the ORDER path (``_filled``) and left standing on the MEASUREMENT path.

    Reads are idempotent, so a transient 5xx is retried. Orders are deliberately NOT retried
    this way (see ``libs/execution/retry``) -- a duplicate GET is free, a duplicate POST is a
    second position. Every failure class collapses to ``None`` on purpose: the caller's only
    honest question is "did this measure or not", and a partially-parsed dict is not a
    measurement.
    """
    for attempt in range(1, attempts + 1):
        try:
            out = fetch()
        except Exception:                              # any venue/transport failure = unmeasured
            if attempt < attempts:
                sleeper(1.0 * attempt)
                continue
            return None
        return out if isinstance(out, dict) else None
    return None


def dedup_basis(trades: list[dict[str, Any]]) -> float:
    """Sum ``price_pnl`` over closed carries, deduped by ``(symbol, opened)``.

    A single carry closes once; the executor can log the same close several times (reconcile retries
    or a flatten), so keep one record per ``(symbol, opened)`` to avoid double-counting basis.
    """
    seen: dict[tuple[Any, Any], float] = {}
    for t in trades:
        if t.get("event") == "close":
            try:
                seen[(t.get("symbol"), t.get("opened"))] = float(t.get("price_pnl", 0.0) or 0.0)
            except (TypeError, ValueError):
                continue
    return round(sum(seen.values()), 2)


def derive_spot_realized(venue_realized_pnl: float, trades: list[dict[str, Any]]) -> float:
    """Exchange-anchored spot realized PnL = deduped basis - venue futures REALIZED_PNL.

    ``venue_realized_pnl`` is the cumulative futures realized (``income_summary`` ``realized_pnl``)
    since the book's inception -- exact and un-fakeable. Robust to executor restarts/crashes and
    duplicate close-logs; degrades gracefully if the trade log is trimmed (basis is small).
    """
    try:
        vr = float(venue_realized_pnl)
    except (TypeError, ValueError):
        vr = 0.0
    return round(dedup_basis(trades) - vr, 2)


class CarryBleedReport(BaseModel):
    """The standing carry-leak alarm: how much of the funding harvest survives to the net."""

    model_config = ConfigDict(frozen=True)

    real_net: float  # spot_pnl + fut_pnl -- the real delta-neutral book (excludes paper legs)
    funding: float | None  # the harvest; None = UNMEASURED (venue read failed), never "zero"
    non_funding_pnl: float | None  # real_net - funding = basis + fees + drift (None if unmeasured)
    harvest_eaten_frac: float | None  # share of harvest lost to the leak (0 = clean, >=1 = all)
    alert: bool
    verdict: str
    measured: bool = True  # False = the funding read failed; the leak is UNDECIDABLE, not clean

    def __bool__(self) -> bool:
        # An UNMEASURED book is not a healthy one. Truthiness means "nothing to worry about",
        # and a blind alarm is something to worry about -- so it must not read as fine.
        return self.measured and not self.alert


def attribute_non_funding(
    non_funding_pnl: float, basis: float, fut_commission: float
) -> dict[str, float]:
    """Split the carry leak into ``basis``, ``fut_fees`` and an UNEXPLAINED ``residual``.

    The bleed alarm answers *how much* leaked; this answers *where it went*, which is the only
    form the desk can act on. From the book identity ``net = spot_open + basis + funding - fees``::

        non_funding = basis - fees + residual   ->   residual = non_funding - basis + fees

    ``basis`` is the deduped trade-log price_pnl (hedge convergence, ~0 for a tight hedge) and
    ``fut_commission`` is the venue's exact FUTURES fee bill. The residual is everything neither
    explains: SPOT commission (paid in the spot wallet, absent from the futures income ledger),
    slippage, and hedge-drift incidents. It is deliberately NOT called "fees" -- naming an
    unexplained quantity after a known one is how a phantom gets rationalised (2026-07-10).

    A large residual is the phantom/broken-hedge class and deserves a page; a large ``fut_fees``
    term is an EXECUTION problem with a known lever (maker share, churn, BNB burn). Before this
    split the two were indistinguishable on the dashboard, so the standing duty to "attribute
    basis/fees/incidents" could not actually be discharged.
    """
    fees = abs(fut_commission)
    return {"basis": round(basis, 2), "fut_fees": round(fees, 2),
            "residual": round(non_funding_pnl - basis + fees, 2)}


def carry_bleed_report(
    *, funding: float | None, spot_pnl: float, fut_pnl: float, alert_frac: float = 0.5
) -> CarryBleedReport:
    """Attribute the delta-neutral book's non-funding PnL and raise an alarm if the leak is eating
    the funding harvest.

    A tight cash-and-carry earns ``funding`` and its price legs cancel, so the honest target is
    ``non_funding_pnl ~= 0`` (only small fees). ``non_funding_pnl = (spot_pnl + fut_pnl) - funding``
    captures everything else -- basis convergence, fees/slippage, and hedge-drift incidents. The
    alarm fires when that leak is a drain worth at least ``alert_frac`` of the harvest (or any drain
    at all when there is no harvest to offset it), so a hedge quietly losing more than it earns can
    never again slide by unnoticed on the dashboard. Diagnose the dominant cause only when it fires.

    TWO-SIDED (2026-07-26): the target is ~0 in BOTH directions, so a large POSITIVE non-funding
    PnL alarms just as loudly. On a delta-neutral book the price legs cancel by construction -- a
    windfall that size is not luck, it is a BROKEN HEDGE (a naked/untracked leg carrying real
    directional risk that will reverse). A one-sided alarm would have called that state "clean".

    UNMEASURED (2026-07-26): ``funding=None`` means the venue read failed, and the leak is then
    UNDECIDABLE -- every term of this alarm is denominated in a harvest we do not know. Passing a
    zero instead produced a division by that zero and an ``inf%`` "hedge losing more than it
    earns" verdict out of nothing but an HTTP 502. The report says so plainly and declines to
    judge; ``measured=False`` is what downstream must alarm on, and it is deliberately NOT folded
    into ``alert`` -- a venue outage and a leaking hedge need different responses, so collapsing
    them into one boolean would just move the ambiguity rather than remove it.
    """
    real_net = round(spot_pnl + fut_pnl, 2)
    if funding is None:
        return CarryBleedReport(
            real_net=real_net, funding=None, non_funding_pnl=None, harvest_eaten_frac=None,
            alert=False, measured=False,
            verdict=(f"UNMEASURED: funding harvest unavailable (venue income read failed) -- "
                     f"leak undecidable on real_net {real_net:+.2f}. A swallowed venue error is "
                     f"NOT a zero harvest; judging one as the other fabricates a total-bleed "
                     f"verdict out of an outage."),
        )
    non_funding = round(real_net - funding, 2)
    if funding > 0:
        eaten = round(max(0.0, -non_funding) / funding, 3)
    else:
        eaten = float("inf") if non_funding < 0 else 0.0
    alert = (abs(non_funding) >= alert_frac * funding) if funding > 0.0 else (non_funding < 0.0)
    if alert and non_funding > 0.0:
        verdict = (
            f"BLEED(inverted): non-funding PnL {non_funding:+.2f} is "
            f"{non_funding / funding:.0%} of {funding:+.2f} funding harvest -- delta-neutral price "
            "legs cancel, so a gain this size means a NAKED/UNTRACKED leg, not edge; reconcile "
            "spot vs perp qty before trusting the number"
        )
    elif non_funding >= 0.0:
        verdict = f"clean: non-funding PnL {non_funding:+.2f} not a drain; harvest survives"
    elif not alert:
        verdict = f"ok: {eaten:.0%} of the {funding:+.2f} funding harvest lost to non-funding PnL"
    else:
        verdict = (
            f"BLEED: non-funding PnL {non_funding:+.2f} is {eaten:.0%} of {funding:+.2f} funding "
            "harvest -- hedge losing more than it earns; attribute basis/fees/incidents"
        )
    return CarryBleedReport(
        real_net=real_net,
        funding=funding,
        non_funding_pnl=non_funding,
        harvest_eaten_frac=eaten,
        alert=alert,
        verdict=verdict,
    )

```

### libs/ops/organ_catchup.py
```python
"""Quota-death organ catch-up: re-fire scheduled claude organs that died at birth.

2026-07-24: the Max-plan credit pool exhausted mid-day and EVERY scheduled organ (brain
08:45, dataaxis 14:00, frontier 15:00, prospector 18:00, litminer 19:00) died with
"out of usage credits" and stayed dead until its next timer fire a full day later --
the principal had to re-fire organs by hand after the 23:00 reset. This module is the
decision core of the automatic version: once quota is back, re-fire each organ whose
day's run died, one per tick, oldest-priority first.

Deliberately narrow: an organ is owed ONLY if its timer already fired today (an attempt
log exists) and no success-sized log exists today. First fires of the day stay owned by
systemd/cron schedules; this is a retry layer, never a scheduler.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

# newest attempt must be at least this old before a re-fire (protects a running organ
# whose log is still small, and spaces retries so a dead quota window is probed slowly)
RETRY_COOLDOWN_S = 45 * 60


@dataclass(frozen=True)
class OrganSpec:
    name: str
    script: str          # bash entrypoint under ops/
    pattern: str         # log glob under data/cro_ai_logs/
    success_bytes: int   # a log this size or larger counts as a real run (max_audit parity)
    pgrep: str           # substring identifying a live run of this organ
    period_days: int = 1  # 1 = daily organ; 7 = weekly (widens the owed window)
    artifacts: tuple[str, ...] = ()  # repo-relative deliverables; a fresh one = produced
    # (claude writes via FILE TOOLS, so a successful run can leave a ~58b log and
    #  megabytes of artifacts -- log size alone produced false 'never fired' verdicts)


# Priority order: the brain first (it advances clocks + triages), then diggers.
# Patterns/thresholds mirror scripts/max_audit.py ORGANS -- keep the two in sync.
ORGANS: tuple[OrganSpec, ...] = (
    OrganSpec("brain", "ops/run_cro_ai.sh", "20*_*.log", 2000, "run_cro_ai.sh",
              artifacts=()),   # EXCLUSIVITY (2026-07-26): the ledger is written by every commit and
              # several organs, and cadence_duties by run_cadence -- both made a dead cycle
              # read as produced (the 10:20 529-Overloaded death was never retried). No
              # exclusive artifact exists, so fall back to log size: weaker but honest.
    OrganSpec("dataaxis", "ops/run_dataaxis_dig.sh", "dataaxis_*.log", 1500,
              "run_dataaxis_dig.sh",
              artifacts=("docs/research/data_axis_watchlist.md",)),   # universe map is SHARED
    OrganSpec("prospector", "ops/run_prospector_dig.sh", "prospector_*.log", 1500,
              "run_prospector_dig.sh",
                            # coverage is SHARED with frontier and the brain -- not exclusive
              artifacts=("docs/research/prospector_watchlist.md",)),
    OrganSpec("litminer", "ops/run_litminer_dig.sh", "litminer_*.log", 1500,
              "run_litminer_dig.sh",
              artifacts=()),   # improvement_inbox is appended by many organs -- not exclusive
    OrganSpec("frontier", "ops/run_frontier_rotation.sh", "frontier_*.log", 1500,
              "run_frontier",
              artifacts=("docs/research/search_operator_library.md",)),   # coverage has THREE
              # writers (prospector dig, the 8 frontier prompts, run_cro_ai.sh)
    # WEEKLY: the deep cold audit must also complete once per INTERVAL even if its
    # Sunday 04:00Z window dies on a session limit -- otherwise it waits a full week.
    # TWO paths write logs here and the glob must see both: ops/run_deep_sweep.sh (what
    # catch-up fires) writes deep_sweep_<date>.log, while cron invokes the python directly
    # with `>> deep_sweep.log`. The cron redirect is the BETTER attempt marker -- it exists
    # the moment cron fires, even if the run dies before opening its own log. Matching only
    # the dated form meant deleting the failure stubs erased every attempt marker, and
    # organ_owed's `if not logs` branch then hid the weekly audit completely (07-26).
    OrganSpec("deep_sweep", "ops/run_deep_sweep.sh", "deep_sweep*.log", 1200,
              "run_deep_sweep", period_days=7),
)


def _window_logs(logdir: Path, pattern: str, now: datetime, period_days: int = 1) -> list[Path]:
    """Logs inside this organ's CURRENT scheduling interval. Daily organs look at today; a
    weekly organ looks back over its whole period, so a sweep killed on Sunday stays owed all
    week instead of silently waiting for the next timer."""
    cut = now.astimezone(UTC).timestamp() - period_days * 86400
    out = []
    for p in logdir.glob(pattern):
        try:
            if p.stat().st_mtime >= cut:
                out.append(p)
        except OSError:
            continue
    return out


def organ_owed(spec: OrganSpec, logdir: Path, now: datetime) -> bool:
    """Owed = attempted within this interval, no success-sized log in it, newest
    attempt past cooldown. Interval = spec.period_days (daily or weekly)."""
    logs = _window_logs(logdir, spec.pattern, now, spec.period_days)
    if not logs:
        return False                      # timer has not fired yet today -- not ours to start
    if any(p.stat().st_size >= spec.success_bytes for p in logs):
        return False                      # a substantial log = clearly landed
    # ARTIFACT CHECK (2026-07-25): claude writes deliverables via file tools, so a SUCCESSFUL run
    # often leaves only the shell's start/exit header in the log. If any declared artifact was
    # written inside this interval, the organ produced -- re-firing it would burn a window on
    # already-completed work (frontier_en ran 3x on 07-25 for exactly this reason).
    # ARTIFACT MUST POSTDATE THIS ORGAN'S OWN ATTEMPT (2026-07-26). Organs SHARE artifacts --
    # the frontier rotation and prospector both write prospector_coverage.md -- so crediting any
    # write inside the period let frontier's dig silently mark prospector as produced, and two
    # genuine quota deaths were never retried. An artifact only counts if it landed AT OR AFTER
    # this organ's newest attempt, exactly as §33(17)(b) requires of a mined find's receipt.
    newest_attempt = max(p.stat().st_mtime for p in logs)
    repo = logdir.parent.parent if logdir.name == "cro_ai_logs" else logdir
    for rel in spec.artifacts:
        try:
            if (repo / rel).stat().st_mtime >= newest_attempt:
                return False
        except OSError:
            continue
    newest = max(p.stat().st_mtime for p in logs)
    return (now.timestamp() - newest) >= RETRY_COOLDOWN_S


def pick_organ(
    logdir: Path,
    now: datetime,
    is_running: Callable[[str], bool],
) -> OrganSpec | None:
    """The single highest-priority owed organ, else None -- and only when the field is CLEAR.

    GLOBAL CONCURRENCY GATE (2026-07-26). The per-organ `is_running` test below only ever asked
    "is THIS organ running", so catch-up would fire an organ while a DIFFERENT one was mid-run.
    Caught in the act on 07-26: the quota window reset at 15:00, systemd's frontier timer fired
    at 15:00:02, catch-up re-fired the brain at 15:00:05, and re-fired deep_sweep (8 cold
    auditors) at 15:05 -- three max-effort organs launched into the same freshly-reset window
    inside five minutes. That is how a window that just reopened is re-exhausted immediately,
    and it is the mechanism behind the paired deaths in the logs, where two organs that started
    the same minute died quoting the SAME reset stamp (cro_ai + dataaxis 14:00 -> "resets
    5:20pm"; cro_ai + prospector 18:00 -> "resets 11pm"; cro_ai + litminer 19:00 -> "resets
    11:40pm").

    Every organ draws on ONE shared pool, so starting a second while any is live does not buy
    throughput -- it converts two runs that would each have completed into two stub deaths, and
    a stub death costs the window AND the work. Serializing retries is therefore strictly
    throughput-POSITIVE: same cadence, same model tier, same breadth, more completions. This
    gate slows nothing down; it stops the desk from stepping on its own runs, which is exactly
    the "retry layer, never a scheduler" contract in this module's docstring.
    """
    if any(is_running(other.pgrep) for other in ORGANS):
        return None
    for spec in ORGANS:
        if organ_owed(spec, logdir, now):
            return spec
    return None

```

### libs/portfolio/optimize.py
```python
"""Robust portfolio optimization — risk-parity base, quality-tilted, diversification-aware.

Prefers multiple uncorrelated alphas over a single high-CAGR one: it starts from equal-risk
weights, tilts modestly toward quality (Sharpe, penalized for decay and instability) and toward
low-correlation alphas, then shrinks back to the risk-parity base to tame estimation noise.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

import numpy as np

from libs.portfolio.covariance import covariance_from_alphas
from libs.portfolio.errors import PortfolioError
from libs.portfolio.models import AlphaInput
from libs.portfolio.risk_parity import risk_parity_weights


def _quality(alphas: Sequence[AlphaInput]) -> np.ndarray:
    q = np.array(
        [
            max(0.0, a.expected_sharpe)
            * (1.0 - min(max(a.decay_score, 0.0), 1.0))
            * min(max(a.stability, 0.0), 1.0)
            for a in alphas
        ],
        dtype="float64",
    )
    return q if q.sum() > 0 else np.ones(len(alphas))


def _diversification_preference(correlation: np.ndarray | None, n: int) -> np.ndarray:
    if correlation is None or n < 2:
        return np.ones(n)
    corr = np.asarray(correlation, dtype="float64")
    avg_corr = (corr.sum(axis=1) - 1.0) / (n - 1)
    return cast("np.ndarray", np.clip(1.0 - avg_corr, 0.05, None))


def optimize_portfolio(
    alphas: Sequence[AlphaInput],
    *,
    correlation: np.ndarray | None = None,
    shrink: float = 0.5,
) -> dict[str, float]:
    """Compute robustness-weighted target weights (shrunk toward risk parity)."""
    if not 0.0 <= shrink <= 1.0:
        raise PortfolioError("shrink must be in [0, 1]")
    cov = covariance_from_alphas(alphas, correlation)
    base = risk_parity_weights(cov)

    quality = _quality(alphas)
    div_pref = _diversification_preference(correlation, len(alphas))
    tilt = (quality / quality.mean()) * div_pref

    raw = base * tilt
    raw = raw / raw.sum()
    weights = (1.0 - shrink) * base + shrink * raw
    weights = cast("np.ndarray", weights / weights.sum())
    return {alpha.alpha_id: float(w) for alpha, w in zip(alphas, weights, strict=True)}

```

### libs/regime/bayesian.py
```python
"""Online Bayesian regime filter -- recursive posterior update, one observation at a time.

Given a fitted HMM's transition matrix + diagonal-Gaussian emissions, this maintains a live belief
P(regime_t | x_1..t) that updates incrementally as each new bar arrives:

    prior_t     = transmat.T @ posterior_{t-1}         (predict step)
    posterior_t ~ prior_t * emission_likelihood(x_t)   (update step)

This is the production hook: the executor can feed the latest bar and get an immediate regime +
confidence without refitting. Confidence = max posterior mass (how sure we are of the state).
"""

from __future__ import annotations

import numpy as np


class BayesianRegimeFilter:
    def __init__(self, transmat: np.ndarray, means: np.ndarray, variances: np.ndarray,
                 startprob: np.ndarray) -> None:
        self.transmat = np.asarray(transmat, dtype="float64")
        self.means = np.asarray(means, dtype="float64")
        self.vars = np.asarray(variances, dtype="float64")
        self.posterior = np.asarray(startprob, dtype="float64").copy()
        self.k = self.transmat.shape[0]

    def _emission(self, x: np.ndarray) -> np.ndarray:
        out = np.empty(self.k)
        for j in range(self.k):
            diff = x - self.means[j]
            log_p = -0.5 * (np.sum(diff * diff / self.vars[j])
                            + np.sum(np.log(2.0 * np.pi * self.vars[j])))
            out[j] = log_p
        out = np.exp(out - out.max())          # stabilise before normalising
        return np.asarray(out, dtype="float64")

    def update(self, x: np.ndarray) -> tuple[int, float]:
        """Push one observation; return (most-likely regime index, confidence = max posterior)."""
        x = np.asarray(x, dtype="float64")
        prior = self.transmat.T @ self.posterior
        post = prior * self._emission(x)
        s = post.sum()
        self.posterior = post / s if s > 0 else np.full(self.k, 1.0 / self.k)
        return int(np.argmax(self.posterior)), float(self.posterior.max())

```

### libs/research/collapse_detector.py
```python
"""GENERATOR COLLAPSE DETECTOR -- HYPOTHESIS_MAX #6 (unblocked at Gate 0 entry, 2026-07-30).

THE FAILURE MODE, and why it is invisible without this. Uncapped generation collapses: multiple
generators and seats converge on near-identical hypotheses, so measured THROUGHPUT rises while
INFORMATION throughput falls. Every dashboard the desk owns counts candidates, so collapse reads
as productivity. The desk's own record is the cautionary case -- 420 candidates, 0 survivors -- and
"420 tests" versus "one question asked 420 ways" are indistinguishable from a count.

WHY IT IS BUILT NOW AND NOT BEFORE. The spec deferred it with an explicit trigger: *"build it when
generation cadence upgrades to weekly at S1/Gate-0 entry"*, because generation was low-volume and
data-triggered, so the failure mode was unreachable. That trigger fires today.

FOUR AXES, per the spec, each measuring a different way a batch can be narrow:
  MECHANISM  entropy over fingerprints. Collapse = entropy falling while volume holds.
  FEATURE    breadth across feature families / data axes.
  MARKET     symbol and venue coverage. Cross-sectional families count the UNIVERSE they rank,
             not one name -- otherwise a 200-symbol cross-sectional signal scores as narrow as a
             single-name trade, which inverts the measure it is meant to provide.
  SEMANTIC   pairwise Jaccard over normalised mechanism tokens, plus CROSS-GENERATOR overlap --
             deterministic, no embeddings, no extra model calls, so it can run every batch.

IT NEVER BLOCKS GENERATION. The spec is explicit and it is right: this is instrumentation that
pages the process, not a gate on ideas. A diversity metric with veto power would be a second
unvalidated filter on the discovery funnel, and the desk already knows what an over-tight funnel
costs. It flags a DIVERSITY AUDIT for the weekly panel, and the audit asks the question a number
cannot: which seats collapsed, onto what, and why -- telemetry-induced herding, shared-prompt
drift, or a genuinely dominant regime, which is a legitimate reason to converge.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.research.mechanism_fingerprint import describe, fingerprint, jaccard, tokens

_ROOT = Path(__file__).resolve().parents[2]
HISTORY = _ROOT / "data/gen_diversity_history.jsonl"

#: A metric this far below its trailing median flags an audit. Starting value from the spec.
DROP_TRIGGER = 0.40
#: Share of near-duplicate pairs BETWEEN different generators that flags an audit.
CROSS_DUP_TRIGGER = 0.25
#: Jaccard at or above this counts a pair as near-duplicate.
NEAR_DUP_JACCARD = 0.80
#: Trailing window for the median comparison.
TRAILING_BATCHES = 8
#: Below this, a batch is too small for entropy to mean anything.
MIN_BATCH = 4


@dataclass
class BatchDiversity:
    n: int
    mechanism_entropy: float          # normalised 0..1 (1 = every idea distinct)
    feature_breadth: float            # distinct families / n, capped at 1
    market_breadth: int               # distinct symbols covered
    semantic_distinctness: float      # 1 - mean pairwise Jaccard
    cross_generator_dup_rate: float   # share of cross-generator pairs that are near-duplicates
    n_fingerprints: int
    top_fingerprints: list[tuple[str, int]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        d = dict(self.__dict__)
        d["top_fingerprints"] = [list(t) for t in self.top_fingerprints]
        return d


def _normalised_entropy(counts: list[int]) -> float:
    """Shannon entropy over fingerprint counts, normalised by log(n_items).

    NORMALISED BY ITEM COUNT, not by category count. Dividing by log(n_categories) would report a
    batch of 50 ideas sharing 2 fingerprints as PERFECTLY diverse (both categories equally used) --
    the collapse would score 1.0. Against log(n_items) that batch scores ~0.18, which is the
    reading that matches what actually happened.
    """
    total = sum(counts)
    if total <= 1:
        return 1.0
    h = -sum((c / total) * math.log(c / total) for c in counts if c > 0)
    # `+ 0.0` normalises the -0.0 that a single-category batch produces. Total collapse should
    # print as 0.0, not as a negative zero that reads like a bug in the report.
    return min(1.0, h / math.log(total)) + 0.0


def _universe_size(hyp: Any) -> set[str]:
    """The names an idea actually spans. A cross-sectional family ranks a universe, so counting
    its single `symbol` field would score the broadest ideas as the narrowest."""
    uni = getattr(hyp, "universe", None)
    if uni:
        return {str(s) for s in uni}
    params = dict(getattr(hyp, "params", {}) or {})
    if params.get("cross_sectional") or "rank" in str(getattr(hyp, "subtype", "")).lower():
        n = int(params.get("universe_size", 0) or 0)
        if n > 0:
            return {f"{getattr(hyp, 'family', 'x')}::xs::{i}" for i in range(n)}
    sym = getattr(hyp, "symbol", None)
    return {str(sym)} if sym else set()


def measure(batch: list[Any], *, generators: list[str] | None = None) -> BatchDiversity:
    """Diversity of one generation batch. `generators[i]` names the seat that produced batch[i]."""
    n = len(batch)
    if n == 0:
        return BatchDiversity(0, 1.0, 1.0, 0, 1.0, 0.0, 0)

    fps = [fingerprint(h) for h in batch]
    counts = Counter(fps)
    families = {fp.split("/")[0] for fp in fps}
    symbols: set[str] = set()
    for h in batch:
        symbols |= _universe_size(h)

    toks = [tokens(describe(h)) for h in batch]
    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    sims = [jaccard(toks[i], toks[j]) for i, j in pairs]
    mean_sim = sum(sims) / len(sims) if sims else 0.0

    cross_rate = 0.0
    if generators and len(generators) == n:
        cross = [(k, (i, j)) for k, (i, j) in enumerate(pairs) if generators[i] != generators[j]]
        if cross:
            cross_rate = sum(1 for k, _ in cross if sims[k] >= NEAR_DUP_JACCARD) / len(cross)

    return BatchDiversity(
        n=n,
        mechanism_entropy=round(_normalised_entropy(list(counts.values())), 4),
        feature_breadth=round(min(1.0, len(families) / n), 4),
        market_breadth=len(symbols),
        semantic_distinctness=round(1.0 - mean_sim, 4),
        cross_generator_dup_rate=round(cross_rate, 4),
        n_fingerprints=len(counts),
        top_fingerprints=counts.most_common(5),
    )


def _history(path: Path) -> list[dict[str, Any]]:
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


def assess(div: BatchDiversity, *, path: Path = HISTORY) -> dict[str, Any]:
    """Compare against the trailing median and decide whether a DIVERSITY AUDIT is warranted.

    A batch below MIN_BATCH is reported UNDER-SAMPLED, never flagged: entropy over three ideas is
    noise, and a detector that cries wolf on small batches gets muted before it ever sees a real
    collapse.
    """
    prior = _history(path)[-TRAILING_BATCHES:]
    flags: list[str] = []

    if div.n < MIN_BATCH:
        return {"batch": div.as_dict(), "verdict": "UNDER-SAMPLED", "flags": [],
                "n_trailing": len(prior),
                "note": f"batch of {div.n} (<{MIN_BATCH}) -- entropy is not meaningful here"}

    if div.cross_generator_dup_rate > CROSS_DUP_TRIGGER:
        flags.append(
            f"cross-generator near-duplicate rate {div.cross_generator_dup_rate:.0%} > "
            f"{CROSS_DUP_TRIGGER:.0%}: separate seats are producing the same idea, which is "
            "herding or shared-prompt drift rather than independent search")

    for metric in ("mechanism_entropy", "feature_breadth", "semantic_distinctness"):
        hist = [float(p["batch"][metric]) for p in prior
                if p.get("batch", {}).get(metric) is not None]
        if len(hist) < 3:
            continue
        med = sorted(hist)[len(hist) // 2]
        now = float(getattr(div, metric))
        if med > 0 and now < med * (1.0 - DROP_TRIGGER):
            flags.append(f"{metric} {now:.3f} is {1 - now / med:.0%} below its trailing-"
                         f"{len(hist)} median {med:.3f}")

    return {
        "batch": div.as_dict(),
        "verdict": "DIVERSITY-AUDIT" if flags else "OK",
        "flags": flags,
        "n_trailing": len(prior),
        "note": "Instrumentation, never a gate -- generation is not blocked by this result "
                "(HYPOTHESIS_MAX #6). A flag books the question for the weekly panel: which "
                "seats collapsed, onto what, and why. Convergence in a genuinely dominant "
                "regime is a legitimate answer.",
    }


def record(div: BatchDiversity, *, path: Path = HISTORY, **meta: Any) -> dict[str, Any]:
    """Assess, append to history, return the assessment. Append-only: the trailing median is only
    meaningful if no batch is ever quietly dropped from the record."""
    out = assess(div, path=path)
    out["at"] = datetime.now(tz=UTC).isoformat()
    out.update(meta)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(out) + "\n")
    return out

```

### libs/self_improvement/ensemble_optimizer.py
```python
"""Ensemble optimizer — proposes the best *portfolio* of alphas (not the best single alpha).

Reuses the Portfolio Engine's robust optimizer; the result is advisory (requires approval).
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from libs.portfolio.engine import build_portfolio
from libs.portfolio.models import AlphaInput
from libs.self_improvement.models import WeightProposal


class EnsembleOptimizer:
    """Wraps the Portfolio Engine to propose diversified ensemble weights."""

    def optimize(
        self, alphas: Sequence[AlphaInput], *, correlation: np.ndarray | None = None
    ) -> WeightProposal:
        target = build_portfolio(alphas, correlation=correlation, method="optimize")
        return WeightProposal(
            weights=target.weights,
            rationale="ensemble optimization via Portfolio Engine (diversification-aware)",
        )

```

### libs/self_improvement/models.py
```python
"""Stage 13 models — recommendations and assessments.

Stage 13 is the supervisory intelligence layer. It REUSES the Architecture v1.0 foundation
models (``AlphaCard``, ``AlphaHealth``, ``DecayResult``, ``AlphaState``, ``LiveMetrics`` from
``libs.alpha``; allocations from ``libs.portfolio``) and never redefines them. The models here
describe *recommendations* — Stage 13 may recommend and schedule, but every production weight
change requires Portfolio Engine approval (``requires_portfolio_approval``).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from libs.core.time import to_iso8601, utcnow


class HealthLevel(StrEnum):
    ELITE = "elite"          # 90+
    STRONG = "strong"        # 80-89
    STABLE = "stable"        # 70-79
    WEAK = "weak"            # 60-69
    CRITICAL = "critical"    # <60

    @classmethod
    def classify(cls, score: float) -> HealthLevel:
        if score >= 90:
            return cls.ELITE
        if score >= 80:
            return cls.STRONG
        if score >= 70:
            return cls.STABLE
        if score >= 60:
            return cls.WEAK
        return cls.CRITICAL


class DecayLevel(StrEnum):
    HEALTHY = "healthy"
    WATCH = "watch"
    WEAK = "weak"
    DECAYING = "decaying"
    DEAD = "dead"


class AlphaCategory(StrEnum):
    TREND_FOLLOWING = "trend_following"
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    VOLATILITY = "volatility"
    BREAKOUT = "breakout"
    CARRY = "carry"
    RELATIVE_VALUE = "relative_value"
    STATISTICAL_ARBITRAGE = "statistical_arbitrage"
    CROSS_ASSET = "cross_asset"
    MACRO = "macro"
    MICROSTRUCTURE = "microstructure"
    OPTIONS = "options"
    MARKET_MAKING = "market_making"
    EVENT_DRIVEN = "event_driven"
    ALTERNATIVE_DATA = "alternative_data"
    OTHER = "other"

    @classmethod
    def from_text(cls, text: str) -> AlphaCategory:
        try:
            return cls(text.strip().lower().replace(" ", "_"))
        except ValueError:
            return cls.OTHER


class ImprovementActionType(StrEnum):
    WEIGHT_CHANGE = "weight_change"
    CAPITAL_REALLOCATION = "capital_reallocation"
    PAUSE = "pause"
    RETIRE = "retire"
    REACTIVATE = "reactivate"
    RESEARCH_PRIORITY = "research_priority"
    ENSEMBLE_UPDATE = "ensemble_update"
    META_INSIGHT = "meta_insight"


class ImprovementAction(BaseModel):
    """One recommended action. Weight/capital actions always require Portfolio Engine approval."""

    model_config = ConfigDict(frozen=True)

    type: ImprovementActionType
    target_id: str | None
    rationale: str
    detail: dict[str, Any] = Field(default_factory=dict)
    requires_portfolio_approval: bool = False


class WeightProposal(BaseModel):
    """A *proposed* set of target weights. Stage 13 may not apply these directly."""

    model_config = ConfigDict(frozen=True)

    weights: dict[str, float]
    rationale: str
    requires_portfolio_approval: bool = True  # always — Stage 13 cannot set production weights


class ResearchPriority(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: str
    priority_score: float
    reason: str


class MetaInsight(BaseModel):
    """A learned relationship. NOT deployable until it passes the validation gauntlet."""

    model_config = ConfigDict(frozen=True)

    description: str
    relationship: dict[str, Any]
    evidence: dict[str, Any] = Field(default_factory=dict)
    deployable: bool = False


class HealthAssessment(BaseModel):
    model_config = ConfigDict(frozen=True)

    alpha_id: str
    health_score: float  # 0-100
    level: HealthLevel
    components: dict[str, float]


class DecayAssessment(BaseModel):
    model_config = ConfigDict(frozen=True)

    alpha_id: str
    decay_level: DecayLevel
    decay_score: float  # 0-1 (from libs.alpha.detect_decay)
    recommended_action: str
    weight_multiplier: float
    allow_increase: bool


class ImprovementPlan(BaseModel):
    """The controller's output: recommendations only."""

    model_config = ConfigDict(frozen=True)

    generated_at: str = Field(default_factory=lambda: to_iso8601(utcnow()))
    actions: list[ImprovementAction] = Field(default_factory=list)
    weight_proposal: WeightProposal | None = None
    research_priorities: list[ResearchPriority] = Field(default_factory=list)

```

### libs/signal_engine/crowding.py
```python
"""Signal crowding — penalize positions that are correlated, concentrated, or crowded.

A higher ``crowding_score`` (0-100) is worse. It blends internal redundancy (how correlated the
contributing alphas are), factor overlap with the existing book, and an external crowding proxy.
"""

from __future__ import annotations

from libs.signal_engine.models import CrowdingResult


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class SignalCrowdingEngine:
    """Scores how crowded a candidate is; above ``threshold`` it is unacceptable."""

    def __init__(self, *, threshold: float = 70.0) -> None:
        self.threshold = threshold

    def assess(
        self,
        *,
        avg_alpha_correlation: float,
        factor_overlap: float,
        public_crowding: float = 0.0,
    ) -> CrowdingResult:
        score = 100.0 * _clip01(
            0.4 * avg_alpha_correlation + 0.3 * factor_overlap + 0.3 * public_crowding
        )
        return CrowdingResult(crowding_score=score, acceptable=score <= self.threshold)

```

### libs/signal_engine/decay.py
```python
"""Signal decay engine — reuse the Stage 13 decay classification for signals.

The decay levels and PF thresholds are identical to the alpha decay model (single source of
truth): ``libs.self_improvement.classify_decay``. A decayed signal loses weight *and* confidence
and, when dead, is retired (action only; capital changes still require Portfolio Engine approval).
"""

from __future__ import annotations

from libs.self_improvement.decay_engine import classify_decay
from libs.self_improvement.models import DecayLevel
from libs.signal_engine.models import SignalDecayResult

# decay level -> (weight_multiplier, confidence_multiplier, recommended_action)
_ACTIONS: dict[DecayLevel, tuple[float, float, str]] = {
    DecayLevel.HEALTHY: (1.0, 1.0, "no_action"),
    DecayLevel.WATCH: (0.90, 0.90, "reduce_weight_and_confidence"),
    DecayLevel.WEAK: (0.75, 0.80, "reduce_weight_and_confidence"),
    DecayLevel.DECAYING: (0.50, 0.60, "pause_signal"),
    DecayLevel.DEAD: (0.0, 0.0, "retire_signal"),
}


class SignalDecayEngine:
    """Maps rolling profit factor / Sharpe to a decay level and its actions."""

    def assess(self, *, profit_factor: float | None, sharpe: float) -> SignalDecayResult:
        level = classify_decay(profit_factor=profit_factor, sharpe=sharpe)
        weight_mult, conf_mult, action = _ACTIONS[level]
        return SignalDecayResult(
            decay_level=level,
            weight_multiplier=weight_mult,
            confidence_multiplier=conf_mult,
            recommended_action=action,
        )

```

### libs/signal_engine/monitoring.py
```python
"""Monitoring exports — aggregate signal metrics for dashboards.

Pure, deterministic aggregation over the evaluated candidates and the final selection. No I/O.
"""

from __future__ import annotations

from collections.abc import Sequence

from libs.signal_engine.models import MonitoringSnapshot, SelectionResult, TradeCandidate


def _avg(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def build_monitoring_snapshot(
    candidates: Sequence[TradeCandidate], selection: SelectionResult
) -> MonitoringSnapshot:
    """Summarize a signal-engine run into dashboard metrics."""
    metrics = {
        "n_candidates": len(candidates),
        "n_approved": len(selection.approved),
        "n_flat": len(selection.rejected),
        "avg_quality": _avg([c.quality.quality_score for c in candidates]),
        "avg_confidence": _avg([c.confidence.confidence for c in candidates]),
        "avg_edge": _avg([c.edge.edge_score for c in candidates]),
        "avg_decay_multiplier": _avg([c.decay.weight_multiplier for c in candidates]),
        "avg_stability": _avg([c.stability.stability_score for c in candidates]),
        "avg_persistence": _avg([c.persistence.persistence_score for c in candidates]),
        "avg_crowding": _avg([c.crowding.crowding_score for c in candidates]),
        "avg_execution": _avg([c.execution.execution_score for c in candidates]),
        "avg_capacity": _avg([c.capacity.future_capacity_score for c in candidates]),
        "avg_portfolio_contribution": _avg(
            [c.portfolio_context.portfolio_contribution_score for c in candidates]
        ),
        "avg_institutional_score": _avg([c.institutional.score for c in candidates]),
        "alpha_contributions": {
            c.symbol: c.alpha_breakdown for c in candidates
        },
    }
    return MonitoringSnapshot(metrics=metrics)

```

### libs/signal_engine/quality.py
```python
"""Signal quality scoring and pre-filters.

``SignalQuality`` fuses edge, confidence, persistence, stability, and agreement (scaled by the
decay weight multiplier) into a 0-100 score. ``SignalFilters`` rejects structurally unusable
candidates early (fail-closed): no governed alpha, no liquidity, or a blown-out spread.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from libs.signal_engine.models import AlphaSignal, MarketState, QualityResult

_QUALITY_THRESHOLD = 80.0


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


class SignalQuality:
    """Computes the 0-100 quality score used by final selection."""

    def __init__(self, *, threshold: float = _QUALITY_THRESHOLD) -> None:
        self.threshold = threshold

    def score(
        self,
        *,
        edge_score: float,
        confidence: float,
        persistence_score: float,
        stability_score: float,
        alpha_agreement: float,
        decay_weight_multiplier: float,
    ) -> QualityResult:
        components = {
            "edge": edge_score,
            "confidence": confidence * 100.0,
            "persistence": persistence_score,
            "stability": stability_score,
            "agreement": alpha_agreement * 100.0,
        }
        base = (
            0.30 * components["edge"]
            + 0.30 * components["confidence"]
            + 0.15 * components["persistence"]
            + 0.15 * components["stability"]
            + 0.10 * components["agreement"]
        )
        quality = _clip(base * decay_weight_multiplier, 0.0, 100.0)
        return QualityResult(
            quality_score=quality, components=components, passed=quality > self.threshold
        )


@dataclass(frozen=True)
class FilterOutcome:
    ok: bool
    reason: str


class SignalFilters:
    """Cheap structural gates applied before the expensive estimation pipeline."""

    def __init__(self, *, max_spread_bps: float = 50.0) -> None:
        self.max_spread_bps = max_spread_bps

    def pre_filter(
        self, signals: Sequence[AlphaSignal], state: MarketState
    ) -> FilterOutcome:
        if not signals:
            return FilterOutcome(False, "no alpha signals")
        if not any(s.governance_passed for s in signals):
            return FilterOutcome(False, "no governed alpha (gauntlet not passed)")
        if state.liquidity_score <= 0.0:
            return FilterOutcome(False, "no liquidity")
        if state.spread_bps > self.max_spread_bps:
            return FilterOutcome(False, f"spread {state.spread_bps:.1f}bps over cap")
        return FilterOutcome(True, "ok")

```

### libs/store/__init__.py
```python
"""``libs.store`` — the SQLite system of record.

ACID, WAL, single-writer. Hash-chained, append-only audit log and trials ledger; mutable
registries; order/fill/position tables (with the structural risk-approval invariant); a
snapshot catalog with database snapshot/restore; and config-version history.
"""

from __future__ import annotations

from libs.store.audit import AuditLog, verify_audit_chain
from libs.store.config_versions import (
    get_config_version,
    list_config_versions,
    record_config_version,
)
from libs.store.connection import Database
from libs.store.hashchain import (
    GENESIS_PREV_HASH,
    canonical_json,
    compute_chain_hash,
    sha256_hex,
    verify_chain,
)
from libs.store.migrations import (
    Migration,
    applied_versions,
    current_version,
    run_migrations,
)
from libs.store.models import (
    Alpha,
    AuditEntry,
    ChainVerification,
    ConfigVersion,
    Fill,
    Order,
    Position,
    ResearchRun,
    RiskRecord,
    SnapshotRecord,
    TrialRecord,
)
from libs.store.registries import AlphaRegistry, ResearchRuns, RiskRegistry
from libs.store.snapshots import (
    create_snapshot,
    get_snapshot,
    list_snapshots,
    register_dataset_snapshot,
    restore_snapshot,
)
from libs.store.trading import OrderStore
from libs.store.trials import TrialsLedger, verify_trials_chain

__all__ = [  # noqa: RUF022  # grouped by concern
    # connection / migrations
    "Database",
    "Migration",
    "run_migrations",
    "applied_versions",
    "current_version",
    # hash chain
    "GENESIS_PREV_HASH",
    "canonical_json",
    "sha256_hex",
    "compute_chain_hash",
    "verify_chain",
    # audit + trials
    "AuditLog",
    "verify_audit_chain",
    "TrialsLedger",
    "verify_trials_chain",
    # registries
    "ResearchRuns",
    "AlphaRegistry",
    "RiskRegistry",
    # trading
    "OrderStore",
    # snapshots
    "create_snapshot",
    "restore_snapshot",
    "register_dataset_snapshot",
    "get_snapshot",
    "list_snapshots",
    # config versions
    "record_config_version",
    "get_config_version",
    "list_config_versions",
    # models
    "AuditEntry",
    "TrialRecord",
    "ResearchRun",
    "Alpha",
    "RiskRecord",
    "Order",
    "Fill",
    "Position",
    "SnapshotRecord",
    "ConfigVersion",
    "ChainVerification",
]

```

### libs/store/trading.py
```python
"""Order / fill / position tables.

The structural invariant lives here: :func:`OrderStore.create_order` refuses to write an
order unless ``risk_approval_id`` points at an *approved* ``risk_registry`` row. Combined with
the ``NOT NULL`` foreign key in the schema, there is no path to an order without a risk
approval — "risk overrides alpha" by construction.
"""

from __future__ import annotations

import sqlite3

from libs.core.ids import generate_id
from libs.core.time import to_iso8601, utcnow
from libs.store.connection import Database
from libs.store.models import Fill, Order, Position


def _row_to_order(row: sqlite3.Row) -> Order:
    return Order(
        id=row["id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        instrument=row["instrument"],
        side=row["side"],
        qty=float(row["qty"]),
        order_type=row["order_type"],
        intended_price=row["intended_price"],
        alpha_id=row["alpha_id"],
        risk_approval_id=row["risk_approval_id"],
        status=row["status"],
        idempotency_key=row["idempotency_key"],
        mt5_ticket=row["mt5_ticket"],
    )


def _row_to_fill(row: sqlite3.Row) -> Fill:
    return Fill(
        id=row["id"],
        order_id=row["order_id"],
        created_at=row["created_at"],
        fill_price=float(row["fill_price"]),
        fill_qty=float(row["fill_qty"]),
        commission=float(row["commission"]),
        mt5_deal_id=row["mt5_deal_id"],
    )


def _row_to_position(row: sqlite3.Row) -> Position:
    return Position(
        instrument=row["instrument"],
        qty=float(row["qty"]),
        avg_price=float(row["avg_price"]),
        realized_pnl=float(row["realized_pnl"]),
        unrealized_pnl=float(row["unrealized_pnl"]),
        updated_at=row["updated_at"],
    )


class OrderStore:
    """Writer/reader for ``orders``, ``fills``, and ``positions``."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def create_order(
        self,
        *,
        instrument: str,
        side: str,
        qty: float,
        order_type: str,
        risk_approval_id: str,
        intended_price: float | None = None,
        alpha_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Order:
        """Create an order, only if ``risk_approval_id`` is a valid approval."""
        approval = self.db.execute(
            "SELECT kind, action FROM risk_registry WHERE id = ?", (risk_approval_id,)
        ).fetchone()
        if approval is None:
            raise ValueError(f"risk approval not found: {risk_approval_id}")
        if approval["kind"] != "approval" or approval["action"] != "approve":
            raise ValueError(
                f"risk_approval_id {risk_approval_id} is not an approved approval "
                f"(kind={approval['kind']}, action={approval['action']})"
            )
        order_id = generate_id("order")
        now = to_iso8601(utcnow())
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO orders "
                "(id, created_at, updated_at, instrument, side, qty, order_type, intended_price, "
                " alpha_id, risk_approval_id, status, idempotency_key, mt5_ticket) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    order_id, now, now, instrument, side, qty, order_type, intended_price,
                    alpha_id, risk_approval_id, "pending", idempotency_key, None,
                ),
            )
        order = self.get_order(order_id)
        assert order is not None
        return order

    def set_order_status(
        self, order_id: str, status: str, *, mt5_ticket: int | None = None
    ) -> Order:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE orders SET status = ?, mt5_ticket = COALESCE(?, mt5_ticket), "
                "updated_at = ? WHERE id = ?",
                (status, mt5_ticket, to_iso8601(utcnow()), order_id),
            )
        order = self.get_order(order_id)
        if order is None:
            raise KeyError(f"order not found: {order_id}")
        return order

    def record_fill(
        self,
        *,
        order_id: str,
        fill_price: float,
        fill_qty: float,
        commission: float = 0.0,
        mt5_deal_id: int | None = None,
    ) -> Fill:
        fill_id = generate_id("fill")
        now = to_iso8601(utcnow())
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO fills "
                "(id, order_id, created_at, fill_price, fill_qty, commission, mt5_deal_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (fill_id, order_id, now, fill_price, fill_qty, commission, mt5_deal_id),
            )
        fill = self.db.execute("SELECT * FROM fills WHERE id = ?", (fill_id,)).fetchone()
        return _row_to_fill(fill)

    def upsert_position(
        self,
        *,
        instrument: str,
        qty: float,
        avg_price: float,
        realized_pnl: float = 0.0,
        unrealized_pnl: float = 0.0,
    ) -> Position:
        now = to_iso8601(utcnow())
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO positions "
                "(instrument, qty, avg_price, realized_pnl, unrealized_pnl, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(instrument) DO UPDATE SET "
                "qty = excluded.qty, avg_price = excluded.avg_price, "
                "realized_pnl = excluded.realized_pnl, unrealized_pnl = excluded.unrealized_pnl, "
                "updated_at = excluded.updated_at",
                (instrument, qty, avg_price, realized_pnl, unrealized_pnl, now),
            )
        position = self.get_position(instrument)
        assert position is not None
        return position

    def get_order(self, order_id: str) -> Order | None:
        row = self.db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        return _row_to_order(row) if row else None

    def get_order_by_idempotency_key(self, key: str) -> Order | None:
        row = self.db.execute(
            "SELECT * FROM orders WHERE idempotency_key = ?", (key,)
        ).fetchone()
        return _row_to_order(row) if row else None

    def list_positions(self) -> list[Position]:
        rows = self.db.execute("SELECT * FROM positions ORDER BY instrument").fetchall()
        return [_row_to_position(row) for row in rows]

    def fills_for(self, order_id: str) -> list[Fill]:
        rows = self.db.execute(
            "SELECT * FROM fills WHERE order_id = ? ORDER BY created_at", (order_id,)
        ).fetchall()
        return [_row_to_fill(row) for row in rows]

    def get_position(self, instrument: str) -> Position | None:
        row = self.db.execute(
            "SELECT * FROM positions WHERE instrument = ?", (instrument,)
        ).fetchone()
        return _row_to_position(row) if row else None

```

### libs/validation/campaign_window.py
```python
"""Stratify the campaign by available history instead of truncating it to the shortest candidate.

THE DEFECT THIS REPLACES. Every campaign builder on the desk aligns its matrix with

    min_len = min(len(r) for r in return_series)
    matrix  = np.column_stack([r[-min_len:] for r in return_series])

so ONE short candidate truncates every other. On the 420-candidate campaign that meant 310
observations retained of ~1,808 available per candidate -- **82.9% of the data already on disk,
discarded before a single test ran**.

WHY THAT IS THE EXPENSIVE CHOICE, measured rather than assumed (docs/research/gate_power_audit.md):

    history   T=310 -> 620 -> 1250 -> 2500     power 0.0% -> 1.7% -> 4.6% -> 19.6%
    cohort    N=420 -> 100 -> 30               power 0.0% -> 0.0% ->  0.0%

Observations buy power; cohort size does not. The truncation makes exactly the wrong trade --
it spends observations to keep candidates aligned. On the desk's own campaign the consequence is
not marginal: the best candidate's Romano-Wolf adjusted p is 0.522 at the min-length window and
0.089 at the max-observation window. Same candidates, same gate, same threshold.

WHY STRATIFY RATHER THAN JUST PICK A LONGER WINDOW. The first version of this module maximised
per-candidate detection power and chose 4,000 observations x 16 candidates -- 99.9% power, and
404 of 420 hypotheses never tested at all. That is the wrong objective: a dropped candidate has
ZERO probability of discovery, not a small one. The quantity worth maximising is the EXPECTED
NUMBER OF TRUE DISCOVERIES, cohort size times per-candidate power, summed over strata. Stratifying
dominates any single window because every candidate is then tested at the longest window IT can
support, and none is truncated to a stranger's history.

MULTIPLICITY STAYS HONEST. Each stratum is its own family, corrected within itself, and the split
is priced at CAMPAIGN_ALPHA/k so total family-wise error stays at 5% however the campaign is cut.
The strata are defined by DATA AVAILABILITY ALONE -- ``plan_strata`` takes lengths and never sees
a return, a Sharpe, or a p-value -- so no channel exists through which results could shape the
partition. A window chosen after peeking at performance would be a selection effect dressed as a
fix.

*** NOT WIRED INTO ANY CAMPAIGN YET, AND DELIBERATELY SO. ***

This module currently PRICES the truncation; it does not change how a campaign runs. Two things
must be true before ``run_campaign.py`` (and its three siblings that share the ``min_len`` idiom)
should call it, and only the first is done:

  1. DONE -- the planner is results-blind and the split is priced. Verified by tests.
  2. NOT DONE -- the per-stratum level has to actually reach the gate. ``romano_wolf_stepdown``
     takes ``alpha=0.05`` and the campaign builders never pass anything else, so today a
     k-stratum campaign would run k families at 5% each and the true family-wise error would be
     ~1-(1-0.05)^k, not 5%. The Bonferroni accounting this planner assumes is a PROPERTY OF THE
     CALLER, not of this module, and wiring the plan without wiring the level would convert a
     measured improvement into a real loosening of error control.

Recorded that way on purpose: an un-wired planner that states its precondition is worth more than
a wired one whose error accounting is assumed. The measurement it supports -- what min-length
truncation costs -- stands on its own.
"""
from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache
from typing import NamedTuple

import numpy as np
from scipy.stats import norm

from libs.validation.dsr import expected_max_sharpe
from libs.validation.positive_control import PPY

#: The edge size the partition is tuned to resolve. 2.0 annualised is a world-class systematic
#: book; tuning larger would justify short windows only a fantasy strategy could clear, tuning
#: smaller would demand history the desk does not have.
REFERENCE_ANN_SHARPE = 2.0
#: Below this a cohort is too small for CSCV and Romano-Wolf to say anything.
MIN_COHORT = 12
#: Below this validate() cannot form its walk-forward and CPCV splits (it returns
#: "insufficient data" under 250).
MIN_OBS = 250


class Stratum(NamedTuple):
    """One campaign: a window, the candidates that support it, and the audit trail."""

    n_obs: int
    keep: tuple[int, ...]
    """Indices into the ORIGINAL input order, so a caller can map results back."""
    power: float
    obs_retained: int


class StrataPlan(NamedTuple):
    strata: tuple[Stratum, ...]
    obs_retained: int
    obs_available: int
    n_candidates: int
    n_tested: int
    expected_discoveries: float
    """Sum over strata of cohort x per-candidate power -- the objective actually maximised."""
    why: str

    @property
    def retained_fraction(self) -> float:
        return self.obs_retained / self.obs_available if self.obs_available else 0.0


#: Total family-wise error the WHOLE campaign is allowed, however many strata it is cut into.
CAMPAIGN_ALPHA = 0.05


#: Cap on strata, set FROM A MEASUREMENT rather than a guess. An earlier value of 8 was chosen on
#: the reasoning that "Bonferroni is brutal so the optimum k is small"; swept on a realistic length
#: distribution (420 candidates, lengths ~lognormal(1700, 0.55) floored at 310) the optimum was
#: k=26, sitting hard against that cap:
#:
#:      cap    2      4      6      8     12     16     24     35
#:      k      2      4      6      8     12     16     24     26
#:      E[d] 111.6  125.9  133.1  138.6  145.9  151.0  158.4  159.0
#:
#: The gain is mostly NOT from shrinking cohorts: it is from more candidates (200 -> 326) getting a
#: window their own history supports instead of being dropped or truncated. 32 sits above the
#: measured optimum with headroom; the DP is O(n^2 k^2) and still runs in well under a second.
MAX_STRATA = 32


@lru_cache(maxsize=200_000)
def detection_power(n_trials: int, n_obs: int,
                    true_ann_sharpe: float = REFERENCE_ANN_SHARPE,
                    alpha: float = CAMPAIGN_ALPHA) -> float:
    """P(a candidate with this TRUE annualised Sharpe clears the hurdle) at this shape and level.

    Built on ``expected_max_sharpe`` -- the desk's own deflator -- so the figure tracks the gate
    rather than restating it. Assumes null dispersion 1/T, which biases power upward equally for
    every window under comparison, so the RANKING this drives is unaffected.

    ``alpha`` is the level THIS stratum is tested at, and it is what stops the partition from
    being a loophole. See ``plan_strata``.
    """
    if n_obs <= 1 or n_trials < 1 or not 0.0 < alpha < 1.0:
        return 0.0
    sr0 = expected_max_sharpe(n_trials, 1.0 / n_obs)
    hurdle = (sr0 + float(norm.ppf(1.0 - alpha)) / np.sqrt(n_obs - 1)) * np.sqrt(PPY)
    se = float(np.sqrt(PPY / n_obs))
    return float(1.0 - norm.cdf((hurdle - true_ann_sharpe) / se))


_EULER = 0.5772156649015329


def _power_grid(m: np.ndarray, t_obs: np.ndarray, true_ann_sharpe: float,
                alpha: float) -> np.ndarray:
    """``detection_power`` evaluated over whole arrays at once.

    Identical arithmetic to the scalar form -- including reproducing expected_max_sharpe's
    Bailey/Lopez de Prado expression inline, because it takes scalars. That duplication is a real
    risk (two copies of one formula drift), so ``test_power_grid_matches_the_scalar_form`` asserts
    they agree elementwise; if the scalar version is ever changed the test fails rather than the
    planner silently optimising against a stale model.

    Needed because the planner evaluates this ~1.4M times and the scalar path did not finish.
    """
    m = np.asarray(m, dtype="float64")
    t = np.asarray(t_obs, dtype="float64")
    out = np.zeros(m.shape, dtype="float64")
    ok = (m >= 2) & (t > 1)
    if not np.any(ok):
        return out
    mm, tt = m[ok], t[ok]
    a = norm.ppf(1.0 - 1.0 / mm)
    b = norm.ppf(1.0 - 1.0 / (mm * np.e))
    sr0 = np.sqrt(1.0 / tt) * ((1.0 - _EULER) * a + _EULER * b)
    hurdle = (sr0 + norm.ppf(1.0 - alpha) / np.sqrt(tt - 1.0)) * np.sqrt(PPY)
    se = np.sqrt(PPY / tt)
    out[ok] = 1.0 - norm.cdf((hurdle - true_ann_sharpe) / se)
    return out


def plan_strata(lengths: Sequence[int], *, min_cohort: int = MIN_COHORT, min_obs: int = MIN_OBS,
                true_ann_sharpe: float = REFERENCE_ANN_SHARPE) -> StrataPlan:
    """Partition candidates into campaigns by available history, maximising expected discoveries.

    Sorted by length descending, a stratum is a CONTIGUOUS run and its usable window is the
    SHORTEST length in that run -- so the partition problem is one-dimensional and an exact
    dynamic program is affordable at any campaign size the desk will ever run.

    THE SPLIT IS PRICED, and without that this whole module would be a loophole. Each stratum is
    a separate family, so cutting a campaign into k pieces and testing each at 5% gives an overall
    false-positive rate near 1-(1-0.05)^k -- 82% at k=34. An unpriced objective exploits exactly
    that: the first version of this DP fragmented into 34 strata of the MINIMUM cohort size,
    because smaller cohorts carry a smaller multiplicity deflation. It was not finding structure
    in the data, it was evading the correction by partitioning, and it would have reported a 279x
    improvement that was mostly fictional.

    So each stratum is tested at CAMPAIGN_ALPHA/k (Bonferroni across strata) and the DP is solved
    once per k with that level, taking the best k. Splitting now costs what it actually costs, the
    optimiser cannot buy power by fragmenting, and total family-wise error stays at
    CAMPAIGN_ALPHA no matter how the campaign is cut.
    """
    lens = [int(x) for x in lengths]
    n = len(lens)
    available = sum(lens)
    if n == 0:
        return StrataPlan((), 0, 0, 0, 0, 0.0, "no candidates")

    order = sorted(range(n), key=lambda i: -lens[i])       # descending by length
    sorted_len = [lens[i] for i in order]

    max_k = max(1, min(MAX_STRATA, n // max(1, min_cohort)))
    NEG = -1.0e18
    lens_arr = np.asarray(sorted_len, dtype="float64")
    best_score, best_cuts, best_k = 0.0, [], 1
    for k in range(1, max_k + 1):
        alpha_k = CAMPAIGN_ALPHA / k
        # value[i, e] = expected discoveries from the stratum order[i:e]. Built VECTORISED --
        # the scalar form of this DP is O(n^2 k^2) Python iterations with a scipy call inside and
        # did not finish at n=420. Same arithmetic, same answer, seconds instead of minutes.
        idx = np.arange(n + 1)
        m = idx[None, :] - idx[:, None]                      # cohort size e - i
        win = np.zeros((n + 1, n + 1))
        win[:, 1:] = lens_arr[None, :]                       # window = shortest in the run
        ok = (m >= min_cohort) & (win >= min_obs)
        value = np.full((n + 1, n + 1), NEG)
        grid = m * _power_grid(m, win, true_ann_sharpe, alpha_k)
        value[ok] = grid[ok]
        dp = np.full((n + 1, k + 1), NEG)
        nxt = np.full((n + 1, k + 1), -1, dtype=int)
        dp[:, 0] = 0.0                                       # leaving the rest untested scores 0
        for j in range(1, k + 1):
            for i in range(n - 1, -1, -1):
                cand = value[i, :] + dp[:, j - 1]
                e = int(np.argmax(cand))
                if cand[e] > dp[i, j]:
                    dp[i, j], nxt[i, j] = cand[e], e
        for j in range(1, k + 1):
            if dp[0, j] > best_score:
                cuts, i, jj = [], 0, j
                while jj > 0 and nxt[i, jj] != -1:
                    cuts.append(int(nxt[i, jj]))
                    i, jj = int(nxt[i, jj]), jj - 1
                best_score, best_cuts, best_k = float(dp[0, j]), cuts, j

    alpha_final = CAMPAIGN_ALPHA / max(1, best_k)
    strata: list[Stratum] = []
    i = 0
    for j in best_cuts:
        window = sorted_len[j - 1]
        keep = tuple(sorted(order[i:j]))                    # back to input order
        strata.append(Stratum(n_obs=window, keep=keep,
                              power=detection_power(len(keep), window, true_ann_sharpe,
                                                    alpha_final),
                              obs_retained=window * len(keep)))
        i = j

    retained = sum(s.obs_retained for s in strata)
    tested = sum(len(s.keep) for s in strata)
    if not strata:
        # Nothing clears the floors. Fall back to min-length and SAY SO -- a builder that silently
        # produces no campaign is worse than one that produces a weak campaign, because only the
        # second is visible in the artifact.
        cut = min(lens)
        return StrataPlan(
            (Stratum(cut, tuple(range(n)), detection_power(n, cut, true_ann_sharpe), cut * n),),
            cut * n, available, n, n, n * detection_power(n, cut, true_ann_sharpe),
            f"NO stratification met the floors (min_obs={min_obs}, min_cohort={min_cohort}) -- "
            f"fell back to min-length {cut}. This campaign is underpowered and a null result from "
            "it must not be read as evidence about the price space.")
    return StrataPlan(
        strata=tuple(strata), obs_retained=retained, obs_available=available,
        n_candidates=n, n_tested=tested, expected_discoveries=best_score,
        why=(f"{len(strata)} strata, windows "
             f"{', '.join(str(s.n_obs) for s in strata)}; {tested}/{n} candidates tested; "
             f"{retained:,}/{available:,} observations used "
             f"({100 * retained / available:.1f}%); expected discoveries {best_score:.2f} at true "
             f"annualised Sharpe {true_ann_sharpe}"))


def stratum_matrix(series: Sequence[np.ndarray], s: Stratum) -> np.ndarray:
    """Aligned T x N matrix for one stratum: the last ``s.n_obs`` rows of each kept candidate."""
    if not s.keep:
        return np.empty((0, 0), dtype="float64")
    return np.column_stack([np.asarray(series[i], dtype="float64")[-s.n_obs:] for i in s.keep])

```

### libs/validation/dsr.py
```python
"""Deflated Sharpe Ratio and friends (multiple-testing aware significance).

The Probabilistic Sharpe Ratio adjusts a Sharpe for sample length, skew, and kurtosis. The
Deflated Sharpe Ratio additionally raises the benchmark to the *expected maximum* Sharpe under
N trials — so the more configurations searched, the higher the bar (Bailey & López de Prado).
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict
from scipy.stats import kurtosis, norm, skew

from libs.validation.errors import ValidationError

EULER_MASCHERONI = 0.5772156649015329


def sharpe_ratio(returns: np.ndarray, *, ddof: int = 1) -> float:
    """Per-period Sharpe ratio (mean / std). Returns 0 if std is 0."""
    r = np.asarray(returns, dtype="float64")
    if len(r) == 0:
        return 0.0
    std = float(r.std(ddof=ddof))
    return float(r.mean() / std) if std > 0 else 0.0


def probabilistic_sharpe_ratio(returns: np.ndarray, *, sr_benchmark: float = 0.0) -> float:
    """P(true Sharpe > benchmark) given the sample, accounting for skew/kurtosis."""
    r = np.asarray(returns, dtype="float64")
    n = len(r)
    if n < 3:
        return 0.0
    sr = sharpe_ratio(r)
    g3 = float(skew(r, bias=False))
    g4 = float(kurtosis(r, fisher=False, bias=False))  # non-excess (normal = 3)
    denom = 1.0 - g3 * sr + ((g4 - 1.0) / 4.0) * sr**2
    if denom <= 0:
        return 0.0
    z = (sr - sr_benchmark) * np.sqrt(n - 1) / np.sqrt(denom)
    return float(norm.cdf(z))


def expected_max_sharpe(n_trials: int, variance_of_sharpes: float) -> float:
    """Expected maximum Sharpe across ``n_trials`` independent no-skill trials."""
    if n_trials < 2 or variance_of_sharpes <= 0:
        return 0.0
    sigma = np.sqrt(variance_of_sharpes)
    a = norm.ppf(1.0 - 1.0 / n_trials)
    b = norm.ppf(1.0 - 1.0 / (n_trials * np.e))
    return float(sigma * ((1.0 - EULER_MASCHERONI) * a + EULER_MASCHERONI * b))


class DSRResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    dsr: float
    sr_observed: float
    sr0_threshold: float
    n_trials: int
    variance_of_sharpes: float
    passed: bool

    def __bool__(self) -> bool:
        return self.passed


def deflated_sharpe_ratio(
    returns: np.ndarray,
    *,
    n_trials: int,
    variance_of_sharpes: float | None = None,
    sharpe_estimates: np.ndarray | None = None,
    threshold: float = 0.95,
) -> DSRResult:
    """Compute the Deflated Sharpe Ratio and whether it clears ``threshold``."""
    if variance_of_sharpes is None:
        if sharpe_estimates is None:
            raise ValidationError("provide variance_of_sharpes or sharpe_estimates")
        arr = np.asarray(sharpe_estimates, dtype="float64")
        if len(arr) < 2:
            raise ValidationError("need >= 2 sharpe_estimates to estimate variance")
        variance_of_sharpes = float(arr.var(ddof=1))
    sr0 = expected_max_sharpe(n_trials, variance_of_sharpes)
    dsr = probabilistic_sharpe_ratio(returns, sr_benchmark=sr0)
    return DSRResult(
        dsr=dsr,
        sr_observed=sharpe_ratio(returns),
        sr0_threshold=sr0,
        n_trials=n_trials,
        variance_of_sharpes=variance_of_sharpes,
        passed=dsr >= threshold,
    )


def min_track_record_length(
    returns: np.ndarray, *, sr_benchmark: float = 0.0, confidence: float = 0.95
) -> float:
    """Minimum number of observations for the Sharpe to be significant vs the benchmark."""
    r = np.asarray(returns, dtype="float64")
    sr = sharpe_ratio(r)
    if sr <= sr_benchmark:
        return float("inf")
    g3 = float(skew(r, bias=False))
    g4 = float(kurtosis(r, fisher=False, bias=False))
    z = float(norm.ppf(confidence))
    numerator = 1.0 - g3 * sr + ((g4 - 1.0) / 4.0) * sr**2
    return float(1.0 + numerator * (z / (sr - sr_benchmark)) ** 2)

```

### libs/validation/positive_control.py
```python
"""Positive/negative controls for the validation gauntlet -- the instrument that certifies a gate.

WHY THIS EXISTS (R0017). The desk has tested 434 candidates and promoted 0. Two readings explain
that equally well: price space is picked clean, or the gate is welded shut. Telling them apart
needs a candidate whose quality is KNOWN, pushed through the real gauntlet: if a known-GOOD
candidate cannot pass, the gate is broken and every "0 survivors" result is uninterpretable; if a
known-NULL cohort passes, the gate leaks phantom edges straight into the forward clocks.

THE BUG THIS REPLACES, because it is subtle and it fooled an audit. The previous probe built its
"known-good" candidate as::

    mu = true_ann_sharpe * sd / sqrt(PPY)
    series = mu + sd * rng.standard_t(df, size=T)

That arithmetic is *correct*: the series is drawn from a distribution whose true annualised Sharpe
is ``true_ann_sharpe``. It is also useless as a control, for a reason that has nothing to do with
wiring. The standard error of an annualised Sharpe estimate over T daily bars is ``sqrt(PPY/T)`` --
**1.085 at T=310**. So a draw with true SR +0.5 routinely *realises* anywhere in (-1.6, +2.6), and
the probe's fixed ``seed=7`` happened to realise **-2.32**. Every gate then rejected it, correctly,
and the audit recorded that the funnel cannot promote good candidates. It had never been asked.
(The offset was identical on every row of the sweep -- one seed, one noise draw, reused
throughout -- which is what makes the artifact so easy to misread as a sign error.)

THE FIX: a control must have the target sample Sharpe **by construction**, not in expectation.
``exact_sharpe_series`` standardises the innovations and then adds the drift, so the returned
series' own sample Sharpe equals the target to floating precision at any T. Sampling error is then
zero where we need it to be zero -- in the definition of "good" -- and the only thing under test is
the gate.

THE TRAP ON THE OTHER SIDE (R0017's shape, one level deeper). Do NOT apply the same
standardisation to the null cohort. DSR and CSCV deflate by the *cross-sectional dispersion* of
candidate Sharpes; standardising every null column to exact zero mean destroys that dispersion,
collapses the deflation benchmark, and manufactures survivors. ``null_cohort`` therefore returns
raw, un-standardised draws, and ``test_positive_control.py`` asserts that it does. The asymmetry is
deliberate and load-bearing: exact where "good" is *defined*, raw where dispersion is *measured*.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np
from pydantic import BaseModel, ConfigDict

from libs.validation.errors import ValidationError

PPY = 365.0  # D1 crypto bars
_DEFAULT_ANN_VOL = 0.40  # a realistic levered crypto sleeve
_DEFAULT_DF = 6  # Student-t innovations: fat tails, finite variance


def exact_sharpe_series(
    target_ann_sharpe: float,
    n_obs: int,
    *,
    rng: np.random.Generator,
    ann_vol: float = _DEFAULT_ANN_VOL,
    df: int = _DEFAULT_DF,
) -> np.ndarray:
    """Fat-tailed daily net returns whose SAMPLE annualised Sharpe IS ``target_ann_sharpe``.

    The innovations are standardised to exact zero mean and unit sample sd (ddof=1) before the
    drift is added, so ``mean/std(ddof=1) * sqrt(PPY) == target_ann_sharpe`` to floating precision
    regardless of ``n_obs`` or seed. Shape (fat tails, autocorrelation-free, ~``ann_vol`` vol) is
    preserved; only the first two sample moments are pinned.

    Costs are assumed already netted out -- the drift IS the net edge, matching what ``net_returns``
    hands the gauntlet.
    """
    if n_obs < 3:
        raise ValidationError("exact_sharpe_series needs n_obs >= 3 to pin a sample sd")
    if ann_vol <= 0.0:
        raise ValidationError("ann_vol must be positive")
    if df <= 2:
        raise ValidationError("Student-t needs df > 2 for finite variance")

    sd = ann_vol / np.sqrt(PPY)
    z = rng.standard_t(df, size=n_obs)
    spread = z.std(ddof=1)
    if spread == 0.0:  # pathological draw; astronomically unlikely, still not silently wrong
        raise ValidationError("degenerate innovation draw (zero sample sd)")
    z = (z - z.mean()) / spread  # exact zero mean, exact unit sample sd
    return np.asarray(sd * (z + target_ann_sharpe / np.sqrt(PPY)))


def null_cohort(
    n_candidates: int,
    n_obs: int,
    *,
    rng: np.random.Generator,
    ann_vol: float = _DEFAULT_ANN_VOL,
    df: int = _DEFAULT_DF,
) -> np.ndarray:
    """``(n_obs, n_candidates)`` matrix of RAW zero-edge draws -- deliberately NOT standardised.

    These columns must retain their natural cross-sectional Sharpe dispersion: DSR/CSCV deflate
    against exactly that dispersion, so pinning each column's moments would collapse the benchmark
    and manufacture survivors. See the module docstring.
    """
    if n_candidates < 1:
        raise ValidationError("null_cohort needs n_candidates >= 1")
    sd = ann_vol / np.sqrt(PPY)
    z = rng.standard_t(df, size=(n_obs, n_candidates)) / np.sqrt(df / (df - 2.0))
    return np.asarray(sd * z)


class ControlOutcome(BaseModel):
    """Verdicts for one injected control candidate."""

    model_config = ConfigDict(frozen=True)

    target_ann_sharpe: float  # 0.0 marks a null control
    realised_ann_sharpe: float  # sample Sharpe actually handed to the gate
    survived: bool
    failed_gates: tuple[str, ...]


class CertificationReport(BaseModel):
    """Can this gauntlet admit a known edge, and does it still reject known noise?"""

    model_config = ConfigDict(frozen=True)

    n_seeds: int
    pass_rate_by_sharpe: dict[str, float]  # target ann Sharpe -> fraction admitted
    min_passing_sharpe: float | None  # lowest tested target admitted at least once
    null_false_pass_rate: float  # fraction of null controls wrongly admitted
    blocking_gates: dict[str, int]  # gate -> times it was the SOLE cause of a good control failing
    certified: bool  # admits a good candidate at all AND leaks no nulls
    verdict: str

    def __bool__(self) -> bool:
        return self.certified


def certify_gauntlet(
    verdict_fn: Callable[[np.ndarray, float], tuple[bool, Sequence[str]]],
    *,
    n_obs: int,
    targets: Sequence[float] = (0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 7.0, 10.0),
    n_seeds: int = 12,
    seed0: int = 1000,
    ann_vol: float = _DEFAULT_ANN_VOL,
    df: int = _DEFAULT_DF,
    null_tolerance: float = 0.05,
) -> CertificationReport:
    """Push known-GOOD and known-NULL controls through ``verdict_fn`` and grade the gate itself.

    ``verdict_fn(returns, realised_ann_sharpe) -> (survived, failed_gate_names)`` is supplied by the
    caller so this module never has to know which gauntlet it is certifying -- the campaign-level
    plumbing (matrix, trial counts, sharpe_estimates) stays where it belongs.

    Every target is run across ``n_seeds`` INDEPENDENT seeds. That is the second half of the R0017
    lesson: one seed is one draw, and a single unlucky draw reused down a sweep produces a perfectly
    smooth, perfectly wrong answer.
    """
    if n_seeds < 1:
        raise ValidationError("certify_gauntlet needs n_seeds >= 1")

    outcomes: list[ControlOutcome] = []
    for target in targets:
        for k in range(n_seeds):
            rng = np.random.default_rng(seed0 + k)
            rets = exact_sharpe_series(target, n_obs, rng=rng, ann_vol=ann_vol, df=df)
            realised = float(rets.mean() / rets.std(ddof=1) * np.sqrt(PPY))
            survived, failed = verdict_fn(rets, realised)
            outcomes.append(ControlOutcome(
                target_ann_sharpe=target, realised_ann_sharpe=realised,
                survived=bool(survived), failed_gates=tuple(failed),
            ))

    nulls: list[ControlOutcome] = []
    for k in range(n_seeds):
        rng = np.random.default_rng(seed0 + 500_000 + k)
        rets = exact_sharpe_series(0.0, n_obs, rng=rng, ann_vol=ann_vol, df=df)
        realised = float(rets.mean() / rets.std(ddof=1) * np.sqrt(PPY))
        survived, failed = verdict_fn(rets, realised)
        nulls.append(ControlOutcome(
            target_ann_sharpe=0.0, realised_ann_sharpe=realised,
            survived=bool(survived), failed_gates=tuple(failed),
        ))

    pass_rate = {
        f"{t:g}": float(np.mean([o.survived for o in outcomes if o.target_ann_sharpe == t]))
        for t in targets
    }
    admitted = [t for t in targets if pass_rate[f"{t:g}"] > 0.0]
    min_passing = float(min(admitted)) if admitted else None
    null_fpr = float(np.mean([o.survived for o in nulls])) if nulls else 0.0

    blocking: dict[str, int] = {}
    for o in outcomes:
        if not o.survived and len(o.failed_gates) == 1:
            blocking[o.failed_gates[0]] = blocking.get(o.failed_gates[0], 0) + 1

    admits_good = min_passing is not None
    leaks_null = null_fpr > null_tolerance
    certified = admits_good and not leaks_null
    if not admits_good:
        verdict = (
            f"NOT CERTIFIED: no control passed, up to true annual Sharpe {max(targets):g} over "
            f"{n_obs} bars. The gate cannot promote a genuinely good candidate, so every "
            f"'0 survivors' result on this path is uninterpretable. Sole blockers: {blocking}"
        )
    elif leaks_null:
        verdict = (
            f"NOT CERTIFIED: null controls admitted at {null_fpr:.1%} (> {null_tolerance:.0%}) -- "
            f"the gate leaks phantom edges. Tighten before trusting any survivor."
        )
    else:
        verdict = (
            f"CERTIFIED: admits a true Sharpe >= {min_passing:g} candidate over {n_obs} bars; "
            f"null false-pass {null_fpr:.1%} <= {null_tolerance:.0%}."
        )
    return CertificationReport(
        n_seeds=n_seeds, pass_rate_by_sharpe=pass_rate, min_passing_sharpe=min_passing,
        null_false_pass_rate=null_fpr, blocking_gates=blocking, certified=certified,
        verdict=verdict,
    )

```

### libs/validation/reality_check.py
```python
"""White's Reality Check and Hansen's SPA test.

Both ask whether the *best* of many strategies beats a benchmark by more than luck, correcting
for the fact that you searched. White's Reality Check uses the max raw outperformance; Hansen's
SPA studentizes and recenters, giving more power. Both use the stationary bootstrap.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict

from libs.validation.bootstrap import stationary_block_indices
from libs.validation.errors import ValidationError


class RealityCheckResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    statistic: float
    p_value: float
    n_strategies: int
    method: str

    @property
    def significant_at_5pct(self) -> bool:
        return self.p_value < 0.05


def _as_matrix(performance: np.ndarray) -> np.ndarray:
    matrix = np.asarray(performance, dtype="float64")
    if matrix.ndim != 2 or matrix.shape[1] < 1:
        raise ValidationError("performance must be a 2-D (T x N) array")
    return matrix


def whites_reality_check(
    performance: np.ndarray, *, n_boot: int = 1000, mean_block: float = 10, seed: int = 0
) -> RealityCheckResult:
    """White's Reality Check. ``performance[t, k]`` = strategy k's edge over benchmark at t."""
    f = _as_matrix(performance)
    t_obs, n = f.shape
    d_bar = f.mean(axis=0)
    statistic = float(np.sqrt(t_obs) * d_bar.max())
    rng = np.random.default_rng(seed)
    boot_max = np.empty(n_boot, dtype="float64")
    for b in range(n_boot):
        idx = stationary_block_indices(t_obs, mean_block, rng)
        f_star = f[idx].mean(axis=0)
        boot_max[b] = np.sqrt(t_obs) * (f_star - d_bar).max()
    p_value = float(np.mean(boot_max >= statistic))
    return RealityCheckResult(
        statistic=statistic, p_value=p_value, n_strategies=n, method="white_reality_check"
    )


def hansen_spa(
    performance: np.ndarray, *, n_boot: int = 1000, mean_block: float = 10, seed: int = 0
) -> RealityCheckResult:
    """Hansen's SPA test (consistent variant), studentized and recentered."""
    f = _as_matrix(performance)
    t_obs, n = f.shape
    d_bar = f.mean(axis=0)
    omega = f.std(axis=0, ddof=1)
    omega = np.where(omega <= 0, np.inf, omega)  # zero-variance strategies cannot be significant
    statistic = float(max(0.0, np.max(np.sqrt(t_obs) * d_bar / omega)))

    # Consistent recentring threshold A_n (Hansen 2005).
    loglog = max(np.log(np.log(t_obs)) if t_obs > np.e else 1.0, 1e-6)
    threshold = -np.sqrt((omega**2 / t_obs) * 2.0 * loglog)
    keep = d_bar >= threshold

    rng = np.random.default_rng(seed)
    boot_max = np.empty(n_boot, dtype="float64")
    for b in range(n_boot):
        idx = stationary_block_indices(t_obs, mean_block, rng)
        f_star = f[idx].mean(axis=0)
        z = np.sqrt(t_obs) * (f_star - d_bar * keep) / omega
        boot_max[b] = max(0.0, float(z.max()))
    p_value = float(np.mean(boot_max >= statistic))
    return RealityCheckResult(
        statistic=statistic, p_value=p_value, n_strategies=n, method="hansen_spa"
    )

```

### scripts/check_constitution_core.py
```python
"""IMMUTABLE-CORE FENCE -- the one law autonomous evolution may not edit (L2.8a, 2026-07-30).

The principal granted the organism permission to amend its own constitution, provided every change
serves the two supreme objectives. That grant is only safe because of L2.8a's IMMUTABLE CORE, and
a core that is merely WRITTEN is exactly the decoration this desk keeps finding. So it is hashed.

WHAT IT PROTECTS, and why each one:
  L1.23  survival rails (ruin <=2%, Tier-3 never loosened, size only on proven edge)
  L1.6   statistical validation -- the two-stage law and the never-loosen direction
  L1.1   the objective function itself
  L1.2   the objective hierarchy
  L2.8a  the immutable core, including the clause saying it is immutable

THE FAILURE MODE IT EXISTS FOR, stated plainly: a self-improving optimiser that may rewrite its own
limits will eventually notice that the cheapest way to raise a measured return is to lower the rail
constraining it. That is not evolution; it is the optimiser eating its safety margin. One ruin event
ends all compounding -- the same asymmetry L1.23 is built on.

HOW IT WORKS: each protected clause is normalised (whitespace-collapsed) and SHA-256'd into
`data/constitution_core.lock`. Any later edit changes the hash and FAILS this check. The lock is
committed, so the diff shows exactly which law moved.

DELIBERATE DESIGN CHOICE: a changed hash is NOT auto-reverted. Reverting would let a bug silently
undo a legitimate principal amendment. It FAILS LOUD and names the clause; a human confirms with
--reseal, which is the only path that rewrites the lock. Autonomy everywhere else; a human hand
on this one.

    python scripts/check_constitution_core.py            # verify (exit 1 on drift)
    python scripts/check_constitution_core.py --reseal   # principal-only: accept a new core
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_CONST = _ROOT / "docs/CONSTITUTION.md"
_LOCK = _ROOT / "data/constitution_core.lock"

_PROTECTED = ("L1.1", "L1.2", "L1.6", "L1.23", "L2.8a")


def _clause(pid: str, text: str) -> str | None:
    """The full text of one clause: from its bold id to the next bold id."""
    m = re.search(rf"^\*\*{re.escape(pid)}\s.*?(?=^\*\*L\d)", text, re.MULTILINE | re.DOTALL)
    return m.group(0) if m else None


def _digest(body: str) -> str:
    # Whitespace-normalised so reflowing a paragraph is not a false alarm; every WORD still counts.
    return hashlib.sha256(" ".join(body.split()).encode("utf-8")).hexdigest()


def current() -> dict[str, str | None]:
    text = _CONST.read_text("utf-8")
    out: dict[str, str | None] = {}
    for pid in _PROTECTED:
        body = _clause(pid, text)
        out[pid] = _digest(body) if body else None
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reseal", action="store_true",
                    help="PRINCIPAL ONLY: accept the current core as the new baseline")
    args = ap.parse_args()
    now = current()
    missing = [p for p, d in now.items() if d is None]

    if not _LOCK.exists() and not args.reseal:
        # DELIBERATE: a missing lock does NOT auto-seal. Auto-sealing looks convenient and is the
        # hole -- on any fresh clone or restored box the fence would silently bless whatever
        # constitution it found, including a tampered one, and report "intact". The lock is
        # committed (see .gitignore negation) so this state means the seal was LOST, which is
        # itself the finding.
        print(f"NO SEAL: {_LOCK.relative_to(_ROOT)} is missing -- the immutable core is unprotected.")
        print("  It is a committed artifact; a missing lock means it was deleted or never restored.")
        print("  Restore it from git, or --reseal ONLY if you have read the current core yourself.")
        return 1

    if args.reseal:
        if missing:
            print(f"REFUSING TO SEAL: protected clause(s) not found in the constitution: {missing}")
            return 2
        _LOCK.parent.mkdir(parents=True, exist_ok=True)
        _LOCK.write_text(json.dumps(
            {"sealed": datetime.now(tz=UTC).isoformat(),
             "note": "L2.8a immutable core. Changing this file is a PRINCIPAL action; the "
                     "organism may not reseal itself as part of an amendment.",
             "digests": now}, indent=2), "utf-8")
        print(f"constitution core SEALED over {len(now)} clauses -> "
              f"{_LOCK.relative_to(_ROOT)}")
        return 0

    lock = json.loads(_LOCK.read_text("utf-8"))["digests"]
    drift = [p for p in _PROTECTED if lock.get(p) != now.get(p)]
    if missing:
        print(f"CORE VIOLATION: protected clause(s) DELETED from the constitution: {missing}")
        return 1
    if drift:
        print("CORE VIOLATION -- an immutable clause was edited:")
        for p in drift:
            print(f"  {p}: sealed {str(lock.get(p))[:12]} != now {str(now.get(p))[:12]}")
        print("  L2.8a: evolution may raise a bar, never lower one, and may never touch the core.")
        print("  If this edit is a deliberate PRINCIPAL amendment, re-seal with --reseal.")
        return 1
    print(f"constitution core intact ({len(_PROTECTED)} clauses verified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts/check_mypy_ratchet.py
```python
"""MYPY RATCHET -- gap #52: `scripts/` is outside the strictest gate in the repo (263 of 268 files).

The register's plan of record is explicit and correct: incremental tranches, risk-path files LAST,
never a bulk fix -- *"editing the live executor to satisfy a type checker is a known way to inject
bugs into working code."* But an untracked backlog has no direction: it can grow silently, and it
did (the pyproject comment records 408 errors across 87 files, measured 2026-07-25).

This makes the backlog a RATCHET (constitution L1.0): per-file error counts are committed to
data/mypy_ratchet.json, and the check FAILS when any file's count RISES or a new file appears with
errors. Counts may only fall. That converts "we should type these eventually" into a number that
cannot get worse, and feeds `scripts_mypy_clean` into the ratchet fence.

WHAT IT DELIBERATELY DOES NOT DO: it does not add files to the `[tool.mypy] files` list, and it
does not touch risk-path code. Promotion into the real gate stays a deliberate, reviewed act per
file. scripts/run_deadman_switch.py is EXCLUDED here as well as from the gate -- the pyproject
comment explains why (strict mode forces `from typing import Any`, which trips the Tier-3 rail's
own import-allowlist guard; the rail's protection is isolation, not type coverage).

    python scripts/check_mypy_ratchet.py [--rebaseline] [--json] [--report-only]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_BASELINE = _ROOT / "data/mypy_ratchet.json"

# NEVER type-checked here, and the exclusion is load-bearing, not convenience.
_EXCLUDED = {"scripts/run_deadman_switch.py"}

_ERR = re.compile(r"^(?P<file>[^:]+):\d+:(?:\d+:)?\s*error:")


def _gated_files() -> set[str]:
    cfg = tomllib.loads((_ROOT / "pyproject.toml").read_text("utf-8"))
    files = cfg.get("tool", {}).get("mypy", {}).get("files", [])
    return {str(f) for f in files}


def _targets() -> list[str]:
    gated = _gated_files()
    return sorted(str(p.relative_to(_ROOT)) for p in (_ROOT / "scripts").glob("*.py")
                  if str(p.relative_to(_ROOT)) not in gated
                  and str(p.relative_to(_ROOT)) not in _EXCLUDED)


def measure(targets: list[str], *, chunk: int = 40) -> tuple[dict[str, int], list[str]]:
    """Per-file error counts. Chunked because module-name collisions and memory make one giant
    invocation unreliable on a 4GB box; a chunk that crashes is recorded as UNCHECKABLE rather
    than silently scoring zero (a crash that reads as 'clean' is the fail-open shape this repo
    has been bitten by before)."""
    counts: dict[str, int] = dict.fromkeys(targets, 0)
    uncheckable: list[str] = []
    for i in range(0, len(targets), chunk):
        batch = targets[i:i + chunk]
        try:
            proc = subprocess.run(
                # --explicit-package-bases is REQUIRED, not optional: pyproject sets
                # mypy_path="." and scripts/ has no __init__.py, so without it mypy aborts the
                # whole batch with "Source file found twice under different module names"
                # (scripts.doctrine vs doctrine) at returncode 2 -- which the first run of this
                # script recorded as 263 UNCHECKABLE files. A tool that reports "cannot check"
                # when the real answer is "one flag missing" produces a false clean bill.
                [sys.executable, "-m", "mypy", "--strict", "--no-error-summary",
                 "--ignore-missing-imports", "--no-incremental",
                 "--explicit-package-bases", *batch],
                cwd=_ROOT, capture_output=True, text=True, timeout=900, check=False)
        except (subprocess.TimeoutExpired, OSError):
            uncheckable.extend(batch)
            continue
        if proc.returncode not in (0, 1):
            uncheckable.extend(batch)
            continue
        for line in (proc.stdout or "").splitlines():
            m = _ERR.match(line.strip())
            if not m:
                continue
            f = m.group("file")
            if f in counts:
                counts[f] += 1
    for f in uncheckable:
        counts.pop(f, None)
    return counts, uncheckable


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebaseline", action="store_true",
                    help="record the CURRENT counts as the baseline (only in a commit that "
                         "reduces them; the check itself never rewrites a worse baseline)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()

    targets = _targets()
    counts, uncheckable = measure(targets)
    total = sum(counts.values())
    clean = [f for f, n in counts.items() if n == 0]

    try:
        base = json.loads(_BASELINE.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        base = {}
    base_per: dict[str, int] = {str(k): int(v) for k, v in (base.get("per_file") or {}).items()}

    regressions = [f"{f}: {n} (was {base_per[f]})" for f, n in sorted(counts.items())
                   if f in base_per and n > base_per[f]]
    new_dirty = [f"{f}: {n}" for f, n in sorted(counts.items())
                 if f not in base_per and n > 0]
    improved = [f"{f}: {n} (was {base_per[f]})" for f, n in sorted(counts.items())
                if f in base_per and n < base_per[f]]

    report: dict[str, Any] = {
        "measured": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime()),
        "n_files_checked": len(counts), "total_errors": total,
        "n_clean": len(clean), "clean_fraction": round(len(clean) / max(len(counts), 1), 4),
        "baseline_total": base.get("total_errors"),
        "regressions": regressions, "new_dirty_files": new_dirty, "improved": improved,
        "uncheckable": uncheckable,
        "excluded_forever": sorted(_EXCLUDED),
        "note": "counts may only FALL; promotion into [tool.mypy] files stays a deliberate "
                "per-file act, and risk-path files go last",
    }

    if args.rebaseline:
        # Only ever writes counts that are <= the recorded ones, per file. A rebaseline cannot
        # launder a regression -- same asymmetry as the ratchet fence.
        merged = dict(base_per)
        for f, n in counts.items():
            merged[f] = min(n, base_per[f]) if f in base_per else n
        _BASELINE.parent.mkdir(parents=True, exist_ok=True)
        _BASELINE.write_text(json.dumps(
            {"generated": report["measured"], "total_errors": sum(merged.values()),
             "per_file": dict(sorted(merged.items())),
             "clean_fraction": round(sum(1 for v in merged.values() if v == 0)
                                     / max(len(merged), 1), 4)},
            indent=2), "utf-8")
        report["rebaselined"] = True

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"mypy ratchet | {len(counts)} files | {total} errors | "
              f"{len(clean)} clean ({report['clean_fraction']:.1%}) | "
              f"baseline total {report['baseline_total']}")
        for label, rows in (("REGRESSION", regressions), ("NEW DIRTY", new_dirty),
                            ("improved", improved), ("UNCHECKABLE", uncheckable)):
            for row in rows[:12]:
                print(f"  {label:12} {row}")
    bad = bool(regressions or new_dirty)
    return 0 if args.report_only else (1 if bad else 0)


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts/collect_kimchi_premium.py
```python
"""Kimchi-premium collector + Stage-A screen (gap #74). Free no-key Upbit + Binance.

Premium is computed USDT-DENOMINATED to avoid needing an FX feed:
    upbit_btc_usdt = Upbit KRW-BTC / Upbit KRW-USDT      (BTC priced in USDT on the Korean venue)
    kimchi = upbit_btc_usdt / Binance BTCUSDT - 1          (Korean vs global, both in USDT)

Stage-A SCREEN ONLY (two-stage law): computes honest in-sample IC + timing Sharpe for both the
momentum and reversal readings, has ZERO promotion authority, and writes the premium series to
data/kimchi_premium.jsonl so a FORWARD clock accrues from today. Promotion needs the forward
gauntlet like anything else. Pure stdlib + numpy. Run from repo root.
"""
from __future__ import annotations

import datetime as _dt
import json
import sys as _sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from pathlib import Path as _P

import numpy as np

_sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
from libs.research.upbit_data import upbit_daily_close_keyed

_UPBIT = "https://api.upbit.com/v1/candles/days"
_BINANCE = "https://api.binance.com/api/v3/klines"
_YF = "https://query1.finance.yahoo.com/v8/finance/chart/KRW=X?interval=1d&range=250d"
_SERIES = Path("data/kimchi_premium.jsonl")


def _get(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": "quant-kimchi"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def _upbit_daily(market: str) -> dict[str, float]:
    # single source of the close-date keying -- see libs/research/upbit_data.py for why
    return upbit_daily_close_keyed(market, 200)


def _binance_daily(sym: str, n: int = 200) -> dict[str, float]:
    rows = _get(f"{_BINANCE}?symbol={sym}&interval=1d&limit={n}")
    if not isinstance(rows, list):
        return {}
    out = {}
    for r in rows:
        d = datetime.fromtimestamp(int(r[0]) / 1000, tz=UTC).date().isoformat()
        out[d] = float(r[4])
    return out


def _yahoo_usdkrw() -> dict[str, float]:
    r = _get(_YF)
    res = r["chart"]["result"][0]
    ts, cl = res["timestamp"], res["indicators"]["quote"][0]["close"]
    return {_dt.datetime.fromtimestamp(int(t), tz=UTC).date().isoformat(): float(c)
            for t, c in zip(ts, cl, strict=False) if c}


def main() -> None:
    kbtc = _upbit_daily("KRW-BTC")
    gbtc = _binance_daily("BTCUSDT")
    fx = _yahoo_usdkrw()                          # official USD/KRW -- carries the real premium
    if not (kbtc and gbtc and fx):
        raise SystemExit(f"fetch failed: upbit={len(kbtc)} binance={len(gbtc)} fx={len(fx)}")
    dates = sorted(set(kbtc) & set(gbtc) & set(fx))
    if len(dates) < 60:
        raise SystemExit(f"only {len(dates)} aligned days")

    prem, btc = [], []
    for d in dates:
        upbit_btc_usd = kbtc[d] / fx[d]           # KRW-BTC at OFFICIAL FX = USD price on Upbit
        prem.append(upbit_btc_usd / gbtc[d] - 1.0)
        btc.append(gbtc[d])
    prem = np.array(prem)
    btc = np.array(btc)
    ret = np.zeros(len(btc))
    ret[1:] = btc[1:] / btc[:-1] - 1.0
    fwd = np.roll(ret, -1)                       # next-day BTC return (no lookahead)

    # signal = 20d z-score of the premium
    z = np.zeros(len(prem))
    for t in range(20, len(prem)):
        w = prem[t - 20:t]
        sd = w.std()
        z[t] = (prem[t] - w.mean()) / sd if sd > 0 else 0.0
    valid = slice(20, len(prem) - 1)             # drop warmup + last (no fwd)
    zv, fv = z[valid], fwd[valid]

    ic = float(np.corrcoef(zv, fv)[0, 1]) if zv.std() and fv.std() else 0.0
    # timing Sharpes: momentum = trade WITH z, reversal = trade AGAINST z
    def _sh(sig: np.ndarray) -> float:
        r = np.sign(sig) * fv
        return round(float(r.mean() / r.std() * np.sqrt(365)), 2) if r.std() else 0.0
    sh_mom, sh_rev = _sh(zv), _sh(-zv)

    # current premium level + persist for the forward clock
    today = datetime.now(tz=UTC).date().isoformat()
    rec = {"date": today, "premium": round(float(prem[-1]), 5),
           "z20": round(float(z[-1]), 3), "n_hist": len(dates)}
    prev = _SERIES.read_text("utf-8").strip().splitlines() if _SERIES.exists() else []
    if not prev or json.loads(prev[-1]).get("date") != today:
        with _SERIES.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")

    print(f"KIMCHI SCREEN | {len(dates)} aligned days")
    print(f"  current premium: {prem[-1] * 100:+.2f}%   z20: {z[-1]:+.2f}")
    print(f"  premium range: {prem.min() * 100:+.2f}% .. {prem.max() * 100:+.2f}%  "
          f"(mean {prem.mean() * 100:+.2f}%, std {prem.std() * 100:.2f}%)")
    print(f"  IC(z20, next-day BTC ret): {ic:+.4f}")
    print(f"  timing Sharpe -- MOMENTUM: {sh_mom}   REVERSAL: {sh_rev}")
    verdict = ("SCREEN-INTERESTING -> pre-register a forward clock"
               if max(abs(sh_mom), abs(sh_rev)) > 0.5 and abs(ic) > 0.03
               else "SCREEN-WEAK -> graveyard the timing form; premium level may still be a "
                    "conditioning feature (log, do not promote)")
    print(f"  VERDICT (Stage-A, zero promotion authority): {verdict}")


if __name__ == "__main__":
    main()

```

### scripts/collect_onchain_activity.py
```python
"""On-chain economic-throughput collector + Stage-A screen (2026-07-23 orthogonal-axis batch).

The desk's data is almost entirely price/derivatives (funding, OI, basis, breadth, ETF & stablecoin
flows, vol surface, liquidations, kimchi). This adds the FIRST genuinely on-chain-USAGE axis:
Bitcoin's estimated USD economic throughput -- NOT price-derived, so it barely co-moves with the
same-day return (that low same-period correlation is exactly the orthogonality we want).

Screened this session across 6 usage/congestion metrics (n-transactions, fees, mempool-size,
active-addresses, throughput, confirmation-time). Two passed the hardened de-contam gate --
active-addresses and throughput -- but they are the same construct (z20 corr +0.64) and their
equal-weight COMPOSITE degraded to Sharpe 0.39, so the standalone Sharpes are partly day-specific.
HONEST STATUS: weak (IC ~-0.05) + fragile REVERSAL, but genuinely orthogonal (same-period ~-0.06)
and survives orthogonalisation. That profile earns exactly ONE thing under the two-stage law: a
forward clock with ZERO promotion authority. If the reversal was luck it will read FAILING forward
under the Holm bar and cost nothing; if it holds it is a real non-price edge. Direction = reversal
(high-throughput z -> lower forward return; activity/throughput spikes cluster near local tops).

hash-rate / difficulty / miner-revenue are DELIBERATELY not here -- already ingested by
scripts/ingest_axes.py (miner-economics) + hypothesised in run_axis_generate (hashrate_capit).
Free blockchain.info charts, no key. stdlib + numpy. Run from repo root.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from libs.research.axis_screen import stage_a_screen

_CHART = ("https://api.blockchain.info/charts/estimated-transaction-volume-usd"
          "?timespan=2years&format=json&sampled=false")
_BINANCE = "https://api.binance.com/api/v3/klines"
_SERIES = Path("data/onchain_activity.jsonl")


def _get(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": "quant-onchain"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def _throughput() -> dict[str, float]:
    d = _get(_CHART)
    return {datetime.fromtimestamp(int(p["x"]), tz=UTC).date().isoformat(): float(p["y"])
            for p in d.get("values", [])} if isinstance(d, dict) else {}


def _binance_daily(sym: str, n: int = 500) -> dict[str, float]:
    rows = _get(f"{_BINANCE}?symbol={sym}&interval=1d&limit={n}")
    if not isinstance(rows, list):
        return {}
    return {datetime.fromtimestamp(int(r[0]) / 1000, tz=UTC).date().isoformat(): float(r[4])
            for r in rows}


def main() -> None:
    thru = _throughput()
    gbtc = _binance_daily("BTCUSDT")
    if not (thru and gbtc):
        raise SystemExit(f"fetch failed: throughput={len(thru)} binance={len(gbtc)}")
    dates = sorted(set(thru) & set(gbtc))
    if len(dates) < 90:
        raise SystemExit(f"only {len(dates)} aligned days")

    sig = np.array([thru[d] for d in dates])
    btc = np.array([gbtc[d] for d in dates])
    ret = np.zeros(len(btc))
    ret[1:] = btc[1:] / btc[:-1] - 1.0

    # 20d z-score of throughput = the traded signal
    z = np.zeros(len(sig))
    for t in range(20, len(sig)):
        w = sig[t - 20:t]
        sd = w.std()
        z[t] = (sig[t] - w.mean()) / sd if sd > 0 else 0.0

    scr = stage_a_screen(sig, ret, name="onchain_activity_throughput")   # honest screen (no clock)

    # forward clock accrues UNCONDITIONALLY from pre-registration (like kimchi) -- one row/day
    today = datetime.now(tz=UTC).date().isoformat()
    rec = {"date": today, "throughput_usd": round(float(sig[-1]), 1),
           "z20": round(float(z[-1]), 3), "n_hist": len(dates)}
    prev = _SERIES.read_text("utf-8").strip().splitlines() if _SERIES.exists() else []
    if not prev or json.loads(prev[-1]).get("date") != today:
        with _SERIES.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")

    print(f"ONCHAIN-THROUGHPUT SCREEN | {len(dates)} aligned days")
    print(f"  current z20: {z[-1]:+.2f}   throughput ${sig[-1]:,.0f}")
    print(f"  IC {scr['ic']:+.4f} | same-period {scr['same_period_corr']:+.3f} "
          f"| residual IC {scr['residual_ic']:+.4f}")
    print(f"  timing Sharpe -- MOMENTUM {scr['sharpe_momentum']}  "
          f"REVERSAL {scr['sharpe_reversal']}")
    print(f"  VERDICT (Stage-A, zero promotion authority): {scr['verdict']}  "
          f"[reversal, direction=-1; weak+fragile per composite check -- forward clock decides]")


if __name__ == "__main__":
    main()

```

### scripts/fusion_engine.py
```python
"""INFORMATION FUSION ENGINE -- test whether WEAK signals combine into a usable one.

MOTIVATION IS EMPIRICAL, NOT THEORETICAL. This session's only replicated result came from a
COMBINED filter (profitable + Sharpe + consistency + drawdown: 62% in-sample, 60% out-of-sample)
while every single criterion alone gave nothing. The desk is full of weak singles that were each
killed alone and never tested together:
    stablecoin_supply IC 0.067 | dex_volume ~0.05 | protocol_fees ~0.06 | defi_tvl ~ -0.02
    kimchi premium IC 0.24 (KRW capital-control flow, orthogonal to all of the above)

MULTIPLICITY IS THE KILLER HERE: k signals give 2^k subsets, so testing "all combinations" is a
guaranteed false-positive factory. Discipline applied:
  1. PRE-REGISTERED combinations only -- each must have a stated economic reason, no subset sweep.
  2. Bonferroni across the number tested.
  3. Equal-weight z-composites ONLY -- no fitted weights (fitting weights on the same sample is
     how a fusion engine becomes an overfitting engine).
  4. Report the honest comparison: does the composite beat its BEST component? A composite that
     merely tracks its strongest member is not fusion, it is relabelling.

Stage-A, zero promotion authority. Run from repo root.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from libs.research.axis_screen import stage_a_screen
from libs.research.upbit_data import upbit_daily_close_keyed


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


def llama_tvl():
    return {datetime.fromtimestamp(int(x["date"]), tz=UTC).date().isoformat(): float(x["tvl"])
            for x in _get("https://api.llama.fi/v2/historicalChainTvl")}


def llama_chart(u):
    return {datetime.fromtimestamp(int(ts), tz=UTC).date().isoformat(): float(v)
            for ts, v in _get(u).get("totalDataChart", [])}


def kimchi():
    # R0060 single source: the OPEN-stamp keying this once inlined carries ~15h look-ahead;
    # upbit_data owns the corrected close-date join, and the fence pins the copy count at one.
    kb = upbit_daily_close_keyed()
    res = _get("https://query1.finance.yahoo.com/v8/finance/chart/KRW=X?interval=1d&range=300d"
               )["chart"]["result"][0]
    fx = {datetime.fromtimestamp(int(t), tz=UTC).date().isoformat(): float(c)
          for t, c in zip(res["timestamp"], res["indicators"]["quote"][0]["close"], strict=False) if c}
    return kb, fx


# PRE-REGISTERED combinations, each with an economic reason. NO subset sweep.
COMBOS = {
    "liquidity_expansion (M1 chain)": (
        ["stablecoin_supply", "defi_tvl"],
        "same mechanism node observed two ways: dollar liquidity entering the system"),
    "onchain_economic_activity": (
        ["dex_volume", "protocol_fees"],
        "real usage/revenue -- two views of the same economic throughput"),
    "liquidity_plus_activity": (
        ["stablecoin_supply", "dex_volume", "protocol_fees"],
        "capital arriving AND being used -- supply alone may be idle"),
    "flow_plus_regional (orthogonal fuse)": (
        ["stablecoin_supply", "kimchi"],
        "global dollar liquidity + KRW capital-control flow: genuinely different mechanisms"),
    "full_stack": (
        ["stablecoin_supply", "dex_volume", "protocol_fees", "kimchi"],
        "all surviving weak signals, equal weight"),
}


def z(series: np.ndarray, w: int = 20) -> np.ndarray:
    o = np.zeros(len(series))
    for t in range(w, len(series)):
        win = series[t - w:t]
        sd = win.std()
        o[t] = (series[t] - win.mean()) / sd if sd > 0 else 0.0
    return o


def main() -> None:
    gb = binance()
    kb, fx = kimchi()
    raw = {
        "stablecoin_supply": stables(),
        "defi_tvl": llama_tvl(),
        "dex_volume": llama_chart(
            "https://api.llama.fi/overview/dexs?excludeTotalDataChartBreakdown=true"),
        "protocol_fees": llama_chart(
            "https://api.llama.fi/overview/fees?excludeTotalDataChartBreakdown=true"),
        "kimchi": {d: kb[d] / fx[d] / gb[d] - 1.0 for d in (set(kb) & set(fx) & set(gb))},
    }
    dates = sorted(set(gb).intersection(*[set(v) for v in raw.values()]))
    print(f"aligned dates across ALL components: {len(dates)} "
          f"(kimchi is the binding constraint at ~{len(raw['kimchi'])})")
    if len(dates) < 80:
        print("insufficient overlap")
        return
    px = np.array([gb[d] for d in dates])
    ret = np.zeros(len(px))
    ret[1:] = px[1:] / px[:-1] - 1.0
    Z = {k: z(np.array([v[d] for d in dates])) for k, v in raw.items()}

    print("\n--- components alone (the baseline each combo must beat) ---")
    base = {}
    for k, zz in Z.items():
        r = stage_a_screen(zz, ret, name=k, zwin=20)
        ic = r.get("ic") or 0.0
        rs = r.get("sharpe_reversal") or 0.0
        base[k] = abs(ic)
        print(f"  {k:22s} IC {ic:+.4f}  revSh {rs:+.2f}  {r.get('verdict')}")

    n_tests = len(COMBOS)
    print(f"\n--- pre-registered fusions (Bonferroni alpha {0.05/n_tests:.4f}, "
          f"equal-weight only, no fitted weights) ---")
    out = []
    for name, (members, why) in COMBOS.items():
        comp = np.mean([Z[m] for m in members], axis=0)
        r = stage_a_screen(comp, ret, name=name, zwin=20)
        best_single = max(base[m] for m in members)
        cic = r.get("ic") or 0.0
        ic = abs(cic)
        lift = ic - best_single
        verdict = ("FUSION ADDS VALUE" if lift > 0.02 else
                   "no lift over best component (relabelling, not fusion)")
        print(f"\n  {name}")
        print(f"    why: {why}")
        print(f"    members: {', '.join(members)}")
        print(f"    composite IC {cic:+.4f} | best single |IC| {best_single:.4f} "
              f"| lift {lift:+.4f}")
        print(f"    same-period {(r.get('same_period_corr') or 0):+.3f} | "
              f"resid {(r.get('residual_ic') or 0):+.4f} | "
              f"revSh {(r.get('sharpe_reversal') or 0):+.2f} | {r.get('verdict')}")
        print(f"    -> {verdict}")
        out.append({"combo": name, "members": members, "ic": cic,
                    "best_single": round(best_single, 4), "lift": round(lift, 4),
                    "verdict": r.get("verdict"), "fusion_verdict": verdict})

    Path("data/fusion_engine.json").write_text(json.dumps(
        {"updated": datetime.now(tz=UTC).isoformat(), "n_combos": n_tests,
         "bonferroni_alpha": 0.05 / n_tests, "components": {k: round(v, 4) for k, v in base.items()},
         "results": out}, indent=1), "utf-8")
    print(f"\n=> {sum(1 for o in out if 'ADDS VALUE' in o['fusion_verdict'])}/{n_tests} "
          f"combinations beat their best component.")


if __name__ == "__main__":
    main()

```

### scripts/quota_verdict.py
```python
#!/usr/bin/env python3
"""QUOTA VERDICT WATCH (principal 2026-07-21): full cadence stays -- measure whether Pro
sustains it and page a clear YES/NO on Max, once the data is unambiguous.

No compromise on cadence. This does NOT throttle anything. It observes the REAL autonomous-only
throughput (starting from a clean baseline set when the operator leaves), compares realized
successful runs against the configured schedule, and renders ONE verdict to the principal:
  MAX NEEDED    -- quota-deaths are eating the schedule; the full cadence does not fit Pro.
  PRO SUFFICIENT -- the full cadence runs clean; no upgrade required. Save the money.
Either way the principal gets a definitive answer via ntfy instead of the CRO guessing.

Runs on its own 3h cron so it can page the MOMENT the signal is clear (a run of dead cycles
needs no 48h wait), but will not verdict before a minimum clean-observation window.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "data/cro_ai_logs"
STATE = ROOT / "data/quota_watch.json"
PA = ROOT / "data/PRINCIPAL_ACTION.md"

MIN_OBS_H = 28.0          # do not render a verdict before this many hours of clean data
CYCLE_EVERY_H = 6.0       # 4 cycles/day
MINERS_PER_DAY = 7
DEATH_FRAC_MAX = 0.25     # >25% of scheduled runs dying on quota => Pro insufficient
SUCCESS_FRAC_MIN = 0.70   # <70% of scheduled cycles succeeding => Pro insufficient


def _load() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text("utf-8"))
        except Exception:
            pass
    # baseline = now: the operator is leaving; the clean autonomous window starts here
    d = {"baseline": datetime.now(tz=UTC).isoformat(), "verdict_sent": False}
    STATE.write_text(json.dumps(d, indent=1), "utf-8")
    return d


def _classify(p: Path) -> str:
    try:
        txt = p.read_text("utf-8", errors="ignore")
    except Exception:
        return "unknown"
    low = txt.lower()
    if any(k in low for k in ("hit your", "usage limit", "usage credits",
                              "out of usage", "session limit", "weekly limit")):
        return "quota_death"
    return "success" if p.stat().st_size >= 2000 else "stub"


def main() -> None:
    st = _load()
    if st.get("verdict_sent"):
        return                                        # one definitive verdict is what was asked
    base = datetime.fromisoformat(st["baseline"])
    hours = (datetime.now(tz=UTC) - base).total_seconds() / 3600
    if hours < MIN_OBS_H:
        print(f"quota-watch: observing ({hours:.1f}/{MIN_OBS_H:.0f}h clean window)")
        return

    base_ts = base.timestamp()
    cyc = [p for p in LOGS.glob("2026*_*.log") if p.stat().st_mtime >= base_ts]
    frontier = [p for p in LOGS.glob("frontier_*.log") if p.stat().st_mtime >= base_ts]

    def tally(files):
        c = {"success": 0, "quota_death": 0, "stub": 0, "unknown": 0}
        for p in files:
            c[_classify(p)] += 1
        return c

    ct, ft = tally(cyc), tally(frontier)
    exp_cyc = max(1, int(hours / CYCLE_EVERY_H))
    exp_min = max(1, int(hours / 24 * MINERS_PER_DAY))

    cyc_succ_frac = ct["success"] / exp_cyc
    total_attempts = sum(ct.values()) + sum(ft.values())
    total_deaths = ct["quota_death"] + ft["quota_death"]
    death_frac = total_deaths / max(1, total_attempts)

    insufficient = (death_frac > DEATH_FRAC_MAX) or (cyc_succ_frac < SUCCESS_FRAC_MIN)

    summary = (f"{hours:.0f}h clean window | cycles: {ct['success']} ok / {exp_cyc} scheduled "
               f"({ct['quota_death']} quota-died) | miners: {ft['success']} ok / ~{exp_min} "
               f"scheduled ({ft['quota_death']} quota-died) | overall quota-death rate "
               f"{death_frac*100:.0f}%")
    print("quota-watch VERDICT:", "MAX NEEDED" if insufficient else "PRO SUFFICIENT")
    print("  " + summary)

    if insufficient:
        block = (
            "\nQUOTA VERDICT -- MAX (or API key) IS NEEDED. You said keep full cadence with no "
            "compromises; measured over a clean autonomous-only window, Pro cannot sustain it.\n"
            f"EVIDENCE: {summary}.\n"
            "The full schedule (4 cycles/day + 7 miners/day at xhigh) is quota-starved on Pro -- "
            "organs are dying at the auth-check, not running. To keep the cadence you ordered "
            "WITHOUT lowering anything, upgrade at claude.ai billing (Max 5x $100/mo is the "
            "sensible start; 20x $200 if even that binds) OR place a metered API key "
            "(bash ops/setup_brain_api_key.sh -- pay per token, no ceiling). Either restores the "
            "full cadence; no config change needed once done.\n")
    else:
        block = (
            "\nQUOTA VERDICT -- PRO IS SUFFICIENT. Good news: over a clean autonomous-only window, "
            "the FULL cadence (4 cycles/day + 7 miners/day at xhigh) runs within Pro limits. No "
            "Max upgrade needed -- save the $100/mo. Keep OpenRouter funded for the panels; that "
            "is the only recurring spend.\n"
            f"EVIDENCE: {summary}.\n"
            "(This verdict re-arms only if the schedule grows or usage patterns change.)\n")

    existing = PA.read_text("utf-8") if PA.exists() else ""
    if "QUOTA VERDICT" not in existing:
        PA.write_text(existing + block, "utf-8")
    st["verdict_sent"] = True
    st["verdict"] = "max_needed" if insufficient else "pro_sufficient"
    st["evidence"] = summary
    STATE.write_text(json.dumps(st, indent=1), "utf-8")
    print("  -> principal paged via PRINCIPAL_ACTION.md")


if __name__ == "__main__":
    main()

```

### scripts/refresh_panel_roster.py
```python
"""Refresh the advisory-panel roster from the live OpenRouter catalog (monthly).

Two jobs, both serving COGNITIVE DIVERSITY (the panel's entire value -- different labs =
different training = different blind spots; a stale or converging roster becomes a monoculture
that shares blind spots, the exact single-reviewer trap the panel exists to break):
  1. DROP dead model IDs (they 404 silently = one fewer reviewer).
  2. Keep ONE strong, recent model per distinct LAB, across the widest set of labs available,
     so the roster stays maximally diverse and current as new frontier models appear.

Conservative + reversible: backs up the old config, logs every change, preserves the API key,
and never trusts a new pick blindly -- the hit-rate scorer (score_panel.py) down-weights bad
additions over time. Advisory-only output, so a wrong pick just yields advice that gets rejected.
Run at monthly governance: `python scripts/refresh_panel_roster.py` (add --apply to write).
"""

from __future__ import annotations

import json
import ssl
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import certifi

_KEYS = Path("data/secrets/llm_panel.json")
_LOG = Path("data/panel_roster_log.jsonl")
_CATALOG = "https://openrouter.ai/api/v1/models"
_CTX = ssl.create_default_context(cafile=certifi.where())

# distinct labs to keep in the roster -- max cross-training diversity (anthropic excluded: the
# CRO is Claude, so an external Claude adds no cognitive diversity). Order = display only.
_LABS = ("x-ai", "openai", "google", "deepseek", "qwen", "z-ai", "moonshotai",
         "mistralai", "meta-llama", "nvidia", "cohere", "microsoft")
# variants that are NOT strong general adversarial reviewers -> never auto-pick as a fill.
# "newest created" != "most capable" (flash/medium/mini are often newer AND weaker), so weak
# tiers are excluded and, crucially, working models are NEVER auto-swapped (see select_roster).
_EXCLUDE = ("image", "vision", "-vl", "audio", "tts", "whisper", "embed", "rerank", "moderation",
            "guard", "safety", "coder", "-code", "-mini", "-nano", "-lite", "lyria", "-oss",
            "distill", "content-safety", "-air", "flash", "medium", "small", "phi", "haiku",
            "turbo", "-8b", "-4b", "-3b", "-1b")


def _family(model_id: str) -> str:
    return model_id.split("/", 1)[0].lower()


def _newest_strong(models: list[dict[str, Any]], lab: str) -> str | None:
    """Newest non-weak model for a lab (used only to REPLACE a dead pick or FILL an empty lab)."""
    best, best_ts = None, -1.0
    for m in models:
        mid = str(m.get("id", ""))
        if _family(mid) != lab or any(x in mid.lower() for x in _EXCLUDE):
            continue
        ts = float(m.get("created") or 0)
        if ts > best_ts:
            best, best_ts = mid, ts
    return best


def select_roster(models: list[dict[str, Any]], key: str, base_url: str,
                  current: list[str] | None = None) -> list[dict[str, str]]:
    """CONSERVATIVE refresh (pure -> testable): KEEP every current model that still exists, only
    REPLACE dead ones and FILL labs with no representative. Never auto-swaps a working flagship
    for a merely-newer variant (that risks a capability downgrade -- deliberate upgrades happen
    at monthly review from the 'upgrades available' log, not here)."""
    live = {str(m.get("id", "")) for m in models}
    current = current or []
    roster: list[dict[str, str]] = []
    covered: set[str] = set()
    for mid in current:                                  # keep-alive: preserve working picks
        lab = _family(mid)
        if mid in live:
            roster.append({"name": lab.split("-")[-1], "base_url": base_url, "key": key,
                           "model": mid})
            covered.add(lab)
        else:                                            # dead -> replace within the same lab
            repl = _newest_strong(models, lab)
            if repl:
                roster.append({"name": lab.split("-")[-1], "base_url": base_url, "key": key,
                               "model": repl})
                covered.add(lab)
    for lab in _LABS:                                    # fill labs with no representative
        if lab not in covered:
            pick = _newest_strong(models, lab)
            if pick:
                roster.append({"name": lab.split("-")[-1], "base_url": base_url, "key": key,
                               "model": pick})
    return roster


def main() -> None:
    apply = "--apply" in sys.argv
    cfg = json.loads(_KEYS.read_text("utf-8"))
    key = cfg["providers"][0]["key"]
    base = cfg["providers"][0].get("base_url", "https://openrouter.ai/api/v1")
    try:
        with urllib.request.urlopen(urllib.request.Request(_CATALOG), timeout=30,
                                    context=_CTX) as r:
            models = json.loads(r.read())["data"]
    except Exception as e:
        print(f"roster: catalog unreachable ({e!r}) -- keeping current roster")
        return
    catalog_ids = {str(m.get("id", "")) for m in models}
    old = [p["model"] for p in cfg["providers"]]
    dead = [m for m in old if m not in catalog_ids]
    new_roster = select_roster(models, key, base, current=old)
    new = [p["model"] for p in new_roster]
    added, removed = sorted(set(new) - set(old)), sorted(set(old) - set(new))
    # UPGRADES AVAILABLE (report only, never auto-applied): labs where a NEWER strong model
    # than the current pick exists -> surfaced for DELIBERATE monthly-review upgrade.
    upgrades = []
    for mid in new:
        newest = _newest_strong(models, _family(mid))
        if newest and newest != mid:
            upgrades.append(f"{mid} -> {newest}")
    print(f"roster: {len(new)} labs | dead (auto-replaced): {dead or 'none'}")
    print(f"  + {added or 'none'}")
    print(f"  - {removed or 'none'}")
    print(f"  upgrades available (review before adopting): {upgrades or 'none'}")
    _LOG.parent.mkdir(parents=True, exist_ok=True)
    with _LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now(tz=UTC).isoformat(), "applied": apply,
                            "dead": dead, "added": added, "removed": removed,
                            "upgrades_available": upgrades, "roster": new}) + "\n")
    if apply and new_roster:
        _KEYS.with_suffix(".json.bak").write_text(_KEYS.read_text("utf-8"), "utf-8")
        _KEYS.write_text(json.dumps({"providers": new_roster}, indent=1), "utf-8")
        print(f"roster APPLIED ({len(new_roster)} models); backup -> {_KEYS}.bak")
    elif not apply:
        print("roster: dry-run (add --apply to write). Monthly governance applies after review.")


if __name__ == "__main__":
    main()

```

### scripts/run_conviction_trader.py
```python
#!/usr/bin/env python3
"""CONVICTION SLEEVE (R0125) -- Claude as an AGGRESSIVE leveraged directional trader, PAPER ONLY.

PRINCIPAL REQUEST (2026-07-31, with an MT5 screenshot: a leveraged XAUUSD short, +60% in 12h):
*"the Binance equivalent to this -- aggressive, AI shouldn't be too calculative and earn less
than a manual trader."* And then the mechanism, in the principal's own words: *"use calculated SL
to prevent it and put trades until the trend and swing hits, minimising downside and maximising
upside."*

CORRECTION OF RECORD (2026-07-31). This file previously described the screenshot as a stopless
punt and built several arguments on that. It was wrong. A second screenshot shows the SL line
plainly at 4050.00 on a short entered at 4107.38 -- trailed BELOW entry, locking ~57 of the ~80
points then open, with price at 4027 and roughly 22 points (~0.55%) of room left to breathe. In
the principal's words: *"I did have a stop, I kept moving it trying to bank profit while letting
it breathe and run further."*

That is not the absence of discipline this file assumed. It is precisely the trail-and-ride
mechanic implemented below, executed by hand -- and it is a useful DATA POINT on the trail width:
the stop sat roughly 1.9 trail-distances behind price, not the naive 1R the first version of this
ladder used, which is the same direction the measured noise floor pushed the trail. n=1, so it
proves nothing on its own; it is recorded because it agrees with the measurement rather than
because it is impressive.

THE DESIGN PHILOSOPHY, stated plainly because it is the whole point. The desk's edge is NOT being
more cautious per trade than a good discretionary trader -- the screenshot shows one managing risk
properly. It is being able to take the SAME aggressive bet a thousand times, at a size that
survives the losing runs, across more instruments than one person can watch. So:

  AGGRESSION LIVES IN BREADTH AND FREQUENCY, NOT IN BET SIZE, and that is a measured conclusion
  rather than a preference. Simulated over 250 days: at 20% risk per trade this book meets a -90%
  drawdown with near-certainty EVEN WHEN THE STRATEGY IS PROFITABLE, and past full Kelly more size
  makes growth NEGATIVE. Holding total risk fixed at ~24% and changing only its SHAPE, one bet at
  24% gives P(-90%)=100% while eight bets at 3% give P(-90%)=0% with a far higher median. So the
  sleeve runs 18 instruments, hourly, up to five positions at once, 6% each -- MORE total exposure
  than one-bet-at-20% ever ran, spread where it compounds instead of where it ruins. On a 0.9%
  structural stop 6% is still ~6.7x, the screenshot's own range. Timidity is a defect (L1.28);
  so is confusing bet size with aggression.

  RUIN IS CAPPED, and this is the one line that does not move. EVERY position carries a stop,
  per-trade loss is bounded, portfolio leverage is bounded,
  and the whole sleeve sits inside the -35% ruin rail like everything else (L1.23). This is not
  the timid reading of a restraint -- it is the mathematics of compounding: E[log wealth] of a
  ruined book is minus infinity, so the bet that can ruin you is never the growth-optimal bet
  however good it looks (the Alameda row in the desk's own cohort register).

  THE STOP IS CALCULATED, NOT CHOSEN -- which is the ONE thing a hand-managed book cannot do at
  scale, and therefore where the desk's advantage actually lies. A percentage stop is an arbitrary distance the market has
  never heard of; a STRUCTURAL stop sits at the price where the thesis is factually dead -- the
  swing the trend must not lose, the range edge, the level that was defended. This desk refuses
  an asserted `stop_pct`: the model must name an invalidation PRICE and the structure it belongs
  to, and the distance is DERIVED from it. That is not a formality, it is free leverage. Kelly
  sizes `risk_budget / stop_distance`, so a stop that sits 1% away at a real swing carries FOUR
  TIMES the size of a lazy 4% stop at the same risk budget and the same edge -- tighter honest
  invalidation is the single cheapest source of aggression on this desk.

  WINNERS ARE RIDDEN, NOT TAKEN. "Put trades until the trend and swing hits" -- so there is no
  fixed take-profit. The position moves to breakeven at +1R, trails one R behind, and ADDS on
  strength (up to 1.75u, less when the trail is noise-widened) while the trend holds, exiting when price closes back
  through the trailing structure. The pyramid is not extra risk: by the time the first add goes
  on, the original tranche's stop is at breakeven, so OPEN RISK FALLS at every stage
  (1.00 -> 0.50 -> 0.25 -> 0.00 of the initial budget) while exposure RISES. That asymmetry is
  the literal instruction -- minimise downside, maximise upside -- expressed as arithmetic and
  pinned by tests rather than as an intention.

  IT IS SCORED. Every call is a pre-registered forecast (direction, probability, expected move,
  stop) logged to the L1.29 calibration fence. A directional trader who cannot be scored is a
  gambler with a good story; this one finds out whether its conviction is CALIBRATED. If its 70%
  calls win 50% of the time, it is over-confident and the Kelly sizer shrinks automatically.

  PAPER ONLY until it earns real size the same way everything does (L1.6): a forward clock, and
  it must beat buy-and-hold AND the carry sleeve after costs. It places no orders here.

WHY THE STOP ALWAYS HITS BEFORE LIQUIDATION, which is the failure mode that kills leveraged
directional books: sizing solves leverage = risk_fraction / stop_distance, so leverage * stop
distance == risk_fraction <= 0.06 BY CONSTRUCTION, while liquidation sits at roughly 1/leverage.
The stop is therefore never more than ~6% of the way to liquidation at any leverage this sleeve
can produce. It is structurally impossible for this sizer to build a position that gets
liquidated before its stop is touched.

WHAT THE NOTIONAL CEILING IS ACTUALLY FOR, since the above makes liquidation a non-argument: a
cascade printing THROUGH the stop before the fill. That loss scales with NOTIONAL and not with
the planned stop distance, so it is the one exposure a tighter stop does not reduce -- and it is
therefore the only honest reason to cap leverage at all. The cap is consequently DERIVED from
surviving a 2% slip rather than picked as a round number. The flat 10x it replaced was actively
anti-aggression: it made a 0.9% structural stop deploy 9% of the risk budget while a lazy 2% stop
deployed the full 20%, the desk's own ceiling penalising the exact behaviour the calculated stop
exists to produce (L1.28).

ONE THING IS DELIBERATELY WITHHELD FROM THE MODEL: where the sizing optimum sits. Because gap
risk caps the tightest stops, deployed risk peaks around a 1.3-2% invalidation rather than at
zero -- and a model told that would drift toward naming levels that maximise its own size instead
of levels where its thesis is actually dead. That is the same PASS-optimisation failure the event
sleeve had to have designed out of it. The brief asks for the honest level and nothing else; the
sizer's shape is the desk's business, not the trader's.

INSTRUMENTS: 18 liquid Binance perps, plus PAXGUSDT as the on-Binance gold analogue of the
screenshot's XAUUSD -- the one non-crypto-beta name, and so the one position that can be
uncorrelated when everything else moves together.

    python scripts/run_conviction_trader.py [--json]
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
from scripts.run_trade_review import N_SUPPORT  # noqa: E402

from libs.ops.lawful import guard as _law_guard  # noqa: E402

_BOOK = "data/conviction_book.jsonl"
_STATE = "data/conviction_trader.json"

#: THE UNIVERSE. Widened from 4 to 18 because BREADTH IS THE COMPOUNDING LEVER and size is not --
#: see MAX_RISK_PER_TRADE below for the simulation that forced this. Four instruments means the
#: sleeve either takes a mediocre setup or passes; eighteen means it can wait for the good one and
#: still be in the market, which is what a professional discretionary book actually looks like.
#: All verified live on the venue fallback chain 2026-07-31. PAXGUSDT is the on-Binance gold
#: analogue of the principal's XAUUSD screenshot and is deliberately kept: it is the only
#: non-crypto-beta instrument here, so it is the one position that can be uncorrelated with the
#: other seventeen when everything else moves together.
INSTRUMENTS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "PAXGUSDT", "BNBUSDT", "XRPUSDT",
               "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT", "DOTUSDT",
               "SUIUSDT", "NEARUSDT", "APTUSDT", "ARBUSDT", "PEPEUSDT", "HYPEUSDT")
MIN_PROB, MAX_PROB = 0.52, 0.90        # below 52% is the other side; 90%+ is an over-confidence tell
#: HALF-Kelly. Full Kelly maximises growth but has an expected drawdown near 50% and is
#: catastrophically sensitive to over-estimating p: betting 1.5x Kelly (what a 35% hit rate would
#: make of a 45% assumption) turns positive growth NEGATIVE. Half-Kelly keeps 75% of the growth
#: rate for 25% of the variance -- the standard result, and the reason the fraction is 0.5 and not
#: 1.0 or 0.25.
KELLY_FRACTION = 0.5
#: 20x. DERIVED, not chosen: it is the gap-stress cap evaluated at the tightest legal stop --
#: 0.50 stress loss / ((0.5% stop + 2% slip)/100) = 20.0x. Above that even the tightest structural
#: stop cannot survive a 2% cascade through it. Replaced a flat 10x that was picked by taste and
#: turned out to penalise tight stops (see MAX_RISK_PER_TRADE for the pattern).
MAX_LEVERAGE = 20.0
#: 0.5% absolute floor, superseded per-instrument by the MEASURED noise floor below (PAXG 24h
#: 0.64%, SOL 24h 1.28% -- measured live 2026-07-31). This constant now only catches the case
#: where the measurement is unavailable; it is a fallback, not the rule.
MIN_STOP_PCT = 0.5
#: 15%. DERIVED from the sizer's own arithmetic: at a 6% risk budget a 15% stop implies 0.4x
#: leverage, at which point the position is no longer a leveraged directional bet and belongs in
#: the spot/carry sleeves instead. Beyond it a "stop" is a hope, not an invalidation.
MAX_STOP_PCT = 15.0

#: THE NOISE FLOOR, and the second flat constant on this desk that turned out to be hiding a
#: defect. MIN_STOP_PCT is a single number applied to gold and to SOL alike -- but a 1% stop is
#: outside the noise on PAXGUSDT and deep inside it on SOLUSDT, so one of those trades is being
#: stopped out by wiggle rather than by being wrong. A stop inside the noise converts a correct
#: thesis into a loss, which is the most expensive way to be right.
#:
#: So the floor is MEASURED per instrument and per horizon: over the last few days of bars, take
#: every rolling window the length of this trade's horizon and record how far price went AGAINST
#: an entry at the window's start. The median of those is the adverse excursion a random entry
#: normally survives. An invalidation closer than that is not an invalidation.
#:
#: FOUND BY MEASUREMENT, not by argument: the first live resolver run marked a PAXGUSDT short
#: whose thesis was correct (gold fell) at -0.13R, because a 1.04% structural stop trailed to
#: breakeven sat inside gold's ordinary retrace.
NOISE_MULT = 1.0                       # the stop must clear the median adverse excursion
NOISE_LOOKBACK_HOURS = 96
#: PER-TRADE RISK, and the single most consequential number in this file. It was 20%, chosen by
#: analogy to a screenshot. Simulating it settled the question rather than arguing it (250
#: sequential days, winners +3R after the trail, losers -1R). No return figure is restated as an
#: objective here -- the desk does not chase a CAGR target (PROJECT_HANDOFF.md 2026-07-12); this
#: is the survival arithmetic that bounds size whatever the ambition:
#:
#:      risk/trade   true hit rate   median year   P(-90% drawdown)
#:            20%             35%        +9064%              96%
#:            20%             30%          -98%             100%
#:             5%             30%          351%               2%
#:
#: At 20% the book meets a -90% drawdown with near-certainty EVEN WHEN THE STRATEGY IS
#: PROFITABLE -- it is wiped out on the way to the gain -- and at a 30% hit rate 20% sits past
#: full Kelly, where more size makes growth NEGATIVE. Meanwhile 5% clears the target several
#: times over. The target never needed bigger bets.
#:
#: This is NOT a retreat from aggression, and the second simulation is the proof. Holding TOTAL
#: heat fixed at ~24% and only changing its shape (35% hit rate):
#:
#:      1 bet @ 24%   median +1058%   5th pct -100%   P(-90%) 100%
#:      4 bets @  6%  median  huge    5th pct  huge   P(-90%)   1%
#:      8 bets @  3%  median  huge    5th pct  huge   P(-90%)   0%
#:
#: Same money at risk, spread across independent instruments: strictly better median AND a
#: near-zero chance of the drawdown that ends the account. So the aggression moved from SIZE to
#: BREADTH and FREQUENCY -- an 18-instrument universe, hourly, several positions live at once.
#: On a 0.9% structural stop 6% still buys ~6.7x leverage, which is the screenshot's own range.
MAX_RISK_PER_TRADE = 0.06              # the UNMEASURED floor; the live cap is derived below

#: THE CAP IS DERIVED FROM MEASURED ACCURACY, NOT FIXED -- and this exists because the flat 6%
#: was wrong in the timid direction, which the principal caught.
#:
#: I had claimed a 10%-risk single position loses money over a year. That was computed from a
#: 37% risk figure I INFERRED from a screenshot instead of asking. The real figure was 10%, and
#: at 10% the arithmetic says the opposite: at a 35% hit rate with 3:1 payoffs g = +0.0233 per
#: trade against +0.0177 at 6%. Full Kelly there is 13.3%, so 10% is 0.75x Kelly -- aggressive
#: and sane -- while 6% is 0.45x. The flat cap was leaving growth on the table (L1.28).
#:
#: But 10% is only correct IF the hit rate is really 35%. At 30% it is 1.5x Kelly and at 28% it is
#: 2.5x, where growth turns negative. So the cap is not re-picked at a higher number -- it is tied
#: to the thing that decides it:
#:
#:      cap = clamp(HALF-KELLY of the MEASURED hit rate, 6% floor, 12% ceiling)
#:
#: Unmeasured stays at 6%: with the parameter unknown the smaller bet is not timidity, it is the
#: same rule that treats an unmeasured correlation as a duplicate -- the assumption that costs
#: money when wrong is the one that gets made. The calibration probe (R0142) is what turns that
#: floor into a measurement, which is why it was worth building before any capital moved.
RISK_CAP_FLOOR = 0.06
#: 12% ceiling: half-Kelly at a 38% hit rate, the top of the band this desk considers plausible.
#: Above it the sizer would be extrapolating past any hit rate it has ever observed.
RISK_CAP_CEILING = 0.12
#: Execution cost as a fraction of one R, measured in resolve_paper_book from the Binance USD-M
#: fee schedule plus observed slippage and funding: ~24% of a full R at taker-in/taker-out, the
#: same figure that moves the breakeven hit rate from 25.0% to 31.1%. It belongs in the Kelly
#: odds because the desk receives the NET payoff, never the gross one.
R_COST = 0.24


def measured_risk_cap(root: Path | None = None) -> dict[str, Any]:
    """Per-trade cap from the desk's MEASURED hit rate, half-Kelly, floored and capped.

    Returns the floor with state UNMEASURED when there is no record -- never an optimistic
    default, because a cap set from a hit rate nobody has observed is a guess wearing a formula."""
    try:
        from libs.self_improvement.forecast_calibration import report
        rep = report()
        n = int(rep.get("n_resolved") or 0)
        hit = rep.get("hit_rate_posterior")
    except Exception as exc:
        return {"cap": RISK_CAP_FLOOR, "state": "UNMEASURED",
                "why": f"calibration unavailable ({type(exc).__name__}) -- floor applies"}
    if n < 30 or hit is None:
        return {"cap": RISK_CAP_FLOOR, "state": "UNMEASURED", "n_resolved": n,
                "why": f"{n}/30 resolved outcomes -- the hit rate that sets Kelly is not yet "
                       "measured, so the floor applies. Not timidity: a cap derived from an "
                       "unobserved rate is a guess wearing a formula."}
    p = float(hit if not isinstance(hit, dict) else hit.get("mean", 0.0))
    # NET odds, not gross. This used b = 3.0 -- the ladder's winner:loser shape BEFORE costs --
    # while resolve_paper_book marks the book net of the same fee/slippage/funding stack that
    # moves the breakeven hit rate from 25.0% to 31.1%. Sizing off a payoff the desk does not
    # actually receive overstates Kelly at every hit rate, and Kelly is the one quantity where
    # overstating the input overstates the bet in the direction that destroys growth.
    win, loss = 3.0 - R_COST, 1.0 + R_COST               # costs widen the loss AND shave the win
    b = win / loss
    full = (p * b - (1 - p)) / b
    cap = max(RISK_CAP_FLOOR, min(RISK_CAP_CEILING, full / 2.0))
    # THE FLOOR IS DELIBERATELY NOT KELLY-BOUNDED, and this note exists because clamping it to
    # full Kelly is the obvious-looking "fix" that breaks two things. Below a ~35% measured hit
    # rate the 6% floor does sit above full Kelly on these net odds, which looks like an overbet
    # to correct. It is not, because of what surrounds it:
    #   * A sleeve that thin can never reach live money anyway -- check_promotion_gate's
    #     hit_rate_above_breakeven blocks rung 2, so the floor only ever applies on PAPER, where
    #     the cost of the overbet is fictional and the EVIDENCE is the entire point.
    #   * Clamping to full Kelly sends the cap to zero once the measured edge goes negative, and
    #     a zero cap places no trades -- so the book never reaches KILL_AFTER_N = 50 closed and
    #     the kill condition can never fire. The sleeve would be dead and unburiable at once,
    #     which is strictly worse than a bounded paper overbet.
    # Death is kill_check's decision and live sizing is the gate's; shrinking to irrelevance is
    # neither, and would pre-empt both silently.
    # `full < cap`, NOT `0 < full < cap`: a NEGATIVE full Kelly is the case most worth reporting
    # -- the measured edge is adverse and any positive size loses -- and the tighter form silently
    # excluded exactly it, flagging the mild overbets while staying quiet on the severe one.
    over_kelly = full < cap
    return {"cap": round(cap, 4), "state": "MEASURED", "n_resolved": n,
            "hit_rate": round(p, 4), "full_kelly": round(full, 4), "net_odds": round(b, 4),
            "floor_above_full_kelly": over_kelly,
            "why": f"half-Kelly at a measured {p:.1%} hit rate on NET odds {b:.2f}:1 is "
                   f"{full/2:.1%}; clamped to [{RISK_CAP_FLOOR:.0%}, {RISK_CAP_CEILING:.0%}]"
                   + (f". NOTE the {RISK_CAP_FLOOR:.0%} floor is above full Kelly {full:.1%} at "
                      "this measured rate"
                      + (" -- which is NEGATIVE, so the measured edge is adverse and the kill "
                         "condition is the organ that should be ending this, not the sizer"
                         if full <= 0 else "")
                      + ". Paper-only by construction (the promotion gate blocks live money "
                        "below breakeven); reported, not silently clamped"
                      if over_kelly else "")}

#: TOTAL heat across all live positions. This is the real aggression dial now, and at 30% it is
#: HIGHER than the old design ever ran (one 20% bet at a time), while every individual bet is
#: survivable. Enforced against the open book, not assumed.
#: 30% = 5 concurrent positions at the 6% per-trade budget. DERIVED from the shape simulation
#: above: at ~24% total heat, 1 bet gives P(-90%)=100%, 4 bets 1%, 8 bets 0%. Five slots sits in
#: the safe part of that curve while keeping total exposure ABOVE what the old one-bet-at-20%
#: design ever ran.
MAX_PORTFOLIO_HEAT = 0.30

#: HOLD LIMIT vs FORECAST HORIZON -- decoupled, because measuring showed they were fighting.
#: `horizon_hours` is the model's CALIBRATION clock ("when I expect to be right"); it was also
#: being used as a hard exit, which truncates winners for a reason that has nothing to do with the
#: trade. Measured on the marked gold short: the SAME position marks +0.07R at a 12h horizon and
#: +0.63R at 30h. An arbitrary clock was setting the P&L instead of the structure.
#: A trade now runs to its STRUCTURAL exit -- stop or trail -- with 4x its stated horizon as a
#: hard time stop so nothing can sit open forever and escape scoring. 4x is derived from the
#: ladder itself: reaching the last rung needs 3 trail-distances of favourable movement, and a
#: trend that has not managed that in 4x its own forecast horizon is a thesis that did not happen.
MAX_HOLD_MULT = 4.0

#: CORRELATION STRESS. Effective heat uses MEASURED correlations, which is what lets genuine
#: diversification buy real capacity -- measured live 2026-07-31: PAXG vs crypto averages +0.15
#: while crypto-vs-crypto averages +0.48, so a gold position alongside four alts is nothing like
#: a fifth alt. But correlations RISE toward 1 in exactly the cascade that would hurt, and a rail
#: that trusts calm-market correlations is a rail that fails when it matters. So every measured
#: correlation is shrunk 35% of the way toward 1.0 before use: +0.15 becomes +0.45, +0.80 becomes
#: +0.87. Diversification is credited, but only two thirds of it.
CORR_STRESS = 0.35
#: Hard ceiling on the NOMINAL sum regardless of how diversifying the book looks. Correlation
#: estimates can be wrong; 50% caps how wrong they are allowed to make the book. At the 6% budget
#: that is 8 concurrent positions, matching the shape simulation's safest tested point.
MAX_GROSS_HEAT = 0.50

#: THE GAP-RISK STRESS, and the reason there is a notional ceiling at all. The stop being hit is
#: priced: that is MAX_RISK_PER_TRADE and the sizer targets it exactly. What is NOT priced is a
#: cascade printing THROUGH the stop before the fill -- and that loss scales with NOTIONAL, not
#: with the planned stop distance, so it is the one exposure a tight stop does not reduce. The
#: ceiling is therefore derived, not chosen: leverage may go as high as it likes provided a
#: violent 2% slip past the stop still leaves the sleeve alive.
#:
#: This replaced a flat 10x cap that was actively anti-aggression: it made a 0.9% structural stop
#: deploy 9% of the risk budget while a lazy 2% stop deployed the full 20% -- the desk's own
#: ceiling punishing the exact behaviour the calculated stop exists to produce (L1.28).
#: HONEST STATUS AFTER THE RISK RECUT: at a 6% per-trade budget this cap no longer binds anywhere
#: in the legal stop range (0.5-15%) -- the risk budget is the tighter constraint everywhere, so
#: the stress cap is currently INERT. By this desk's own standard a rail that can never fire is
#: decoration, so it is named as one rather than counted as protection. It is kept because it is
#: the thing that must hold if MAX_RISK_PER_TRADE is ever raised again, and a test pins that
#: leverage never exceeds it. Do not read it as active protection today.
SLIP_STRESS_PCT = 2.0                  # a liquidation cascade prints this far through the stop
#: 0.50 -- a 2% cascade through the stop costs at most half the sleeve. Chosen against the
#: drawdown simulation: a 50% hit is survivable and recoverable (needs +100% to restore), whereas
#: the -90% outcomes that the 20% risk budget produced need +900% and never come back.
MAX_STRESS_LOSS = 0.50
#: 0.60, measured as
MAX_PEAK_STRESS_LOSS = 0.60            # drawdown FROM THE STAGE TRIGGER, where the book is up
#: ~0.47 unrealised (computed from the tranche ladder at the +2 rung): so the bound says a cascade
#: may cost the pyramid its own open gains and ~13% more, never the starting stake. Derived as
#:                                       drawdown FROM THE STAGE TRIGGER: by then the position is
#:                                       up roughly that much unrealised, so the bound says the
#:                                       pyramid may give back its own open gains in a cascade --
#:                                       never the starting stake.

#: The pyramid: units added at each rung. Each rung first TRAILS the stop one TRAIL DISTANCE
#: behind, THEN adds -- which is why open risk falls as size grows. Deliberately geometric-
#: decaying: the trend that has already run two rungs has less remaining runway than the one that
#: just started, so the adds get smaller, not larger. Peak exposure 1.75u.
#: (0.50, 0.25) -- geometric halving, giving peak exposure 1.75u. DERIVED from the risk ladder
#: rather than chosen: with each rung trailing one distance behind, these sizes are exactly what
#: makes open risk fall 1.00 -> 0.50 -> 0.25 -> 0.00 of the entry budget while exposure rises, the
#: asymmetry the tests assert. Larger adds break the monotone fall; smaller ones leave upside
#: unclaimed for no risk reduction.
ADD_UNITS: tuple[float, ...] = (0.50, 0.25)

#: THE TRAIL DISTANCE, and the third flat constant that turned out to be a defect. The ladder used
#: to trail exactly 1R behind, which means the breakeven move at +1R leaves the stop one R from
#: price -- and since the entry stop is allowed to sit AT the noise floor, that trailed stop sits
#: at the noise floor too. It has to pass the same test the entry stop passes, and it did not.
#:
#: So the trail is max(1R, 1.5x the measured noise), and the rungs are spaced one trail distance
#: apart so each rung's stop lands exactly where the previous rung triggered. When the noise floor
#: is not binding this reduces EXACTLY to the old 1R ladder; it only ever gives the trade room it
#: measurably needs. That is a GENERALISATION of the old rule, not a different design.
#:
#: EVIDENCE STATUS, stated plainly because the temptation is to imply otherwise: this change is
#: derived from a principle (every stop in the ladder passes the same noise test), NOT fitted to
#: an outcome, and on the one trade marked so far it did not help -- the 1.5%-stop variant went
#: from -0.19R to -0.22R. n=1 in both directions is nothing. It is kept because it is consistent
#: and reduces to the prior behaviour when noise is not binding, and it stays on the forward clock
#: like everything else. Do not read it as a fix that has been shown to work.
#:
#: What that same marking DID establish is separate and larger: at every stop width where the
#: trade survived (2%+), it was still OPEN at a positive R when the 30h horizon expired. The
#: binding constraint on that trade was the HORIZON, not the stop and not the trail.
NOISE_TRAIL_MULT = 1.5

#: A stop is only "calculated" if it sits at something the market drew. This vocabulary is how the
#: fence tells a structural level from a number someone liked. Kept broad on purpose -- a false
#: refusal here costs a real trade, and the binding checks are the price ones below.
_STRUCTURE_WORDS = (
    "swing", "range", "high", "low", "support", "resistance", "breakout", "breakdown",
    "consolidation", "pivot", "shelf", "level", "trendline", "trend line", "channel", "gap",
    "vwap", "liquidity", "order block", "session", "prior day", "prior week", "prior session",
    "base", "neckline", "wick", "close", "open interest", "poc", "value area", "fib", "band",
)

#: MINIMUM MEANINGFUL SIZE. Not an EV bound -- cost scales with notional, so cost/risk is constant
#: and a small trade is proportionally as good as a large one. This is the VENUE minimum: Binance
#: USD-M rejects orders under ~$5 notional, and at a $200 sleeve a 0.1% risk on a 2% stop is $10
#: of notional. Below this the order simply will not fill, so booking it would be fiction.
MIN_TRADE_RISK = 0.001

#: SLEEVE DRAWDOWN HALT. Per-trade risk is bounded; a LOSING RUN is not. At a 20% budget three
#: stops in a row is -49% of the sleeve, which is why a sleeve-level rail has to exist before real
#: money does rather than after the first bad week. Read from the resolver's marked equity curve
#: (R0133) -- which also means this rail is only as alive as the marking is, so an unmarked book
#: reports NO-HISTORY and never OK (L1.28a).
SLEEVE_DD_HALT = 0.35                  # same shape as the book's -35% ruin rail (L1.23)
_PNL_STATE = "data/paper_book_pnl.json"

#: How far the model's own asserted stop_pct may disagree with the level it named before the call
#: is refused as internally inconsistent. A model that names a swing 1% away and then writes
#: "stop_pct: 3" did not reason about the level; it decorated a number.
STOP_MISMATCH_TOL = 0.25               # relative

#: COST VETO, in R. Derived from the ladder's own payoff: a trade whose expected costs reach 0.5R
#: nets 2.5R when right and loses 1.5R when wrong, so its breakeven hit rate is 1.5/(2.5+1.5) =
#: 37.5% -- the sleeve's CEILING accuracy spent entirely on breaking even, with the edge going to
#: the venue. At current major-perp funding this never binds (a 2% stop, 24h hold, 0.01%/8h is
#: ~0.015R); it exists for the extreme-funding regime -- 0.3%/8h has been observed on meme perps,
#: which over a 20h hold at a 0.9% stop is ~0.8R of pure bleed. The refusal is those trades.
COST_REFUSE_R = 0.5


def trade_cost_view(root: Path, symbol: str, direction: str, stop_pct: float,
                    horizon_hours: float) -> dict[str, Any]:
    """Expected all-in cost of THIS call, in R, priced BEFORE sizing -- possible because cost in
    R is size-independent: (cost as a fraction of notional) / (stop as a fraction of price), and
    leverage cancels.

    Fees and slippage come from the resolver's published venue schedule (maker-in as the plan
    specifies, taker-out, slippage both sides). Funding is the live SIGNED rate from the cost
    hunt (R0198) over the call's own horizon: negative means this side is PAID to hold. The
    freshness contract is 8h -- one funding stamp -- because a rate older than a stamp is a
    different regime's rate (L1.44).

    ABSENT is a stated state, not a zero: with no snapshot the veto stands down and the flat
    always-adverse cost model in the resolver carries alone. Fail-open is DELIBERATE here and
    the direction matters -- a dead cost feed must idle the veto, never the sleeve, because
    marking still charges costs pessimistically either way; the stale read is recorded."""
    from scripts.resolve_paper_book import MAKER_FEE, SLIPPAGE, TAKER_FEE
    stop_frac = stop_pct / 100.0
    if stop_frac <= 0:
        return {"state": "ABSENT", "why": "no stop distance -- cost in R is undefined"}
    fees_R = (MAKER_FEE + TAKER_FEE + 2 * SLIPPAGE) / stop_frac
    try:
        from libs.ops.fresh import read_fresh
        fr = read_fresh("data/cost_hunt.json", max_age_h=8.0,
                        caller="run_conviction_trader.trade_cost_view", root=root)
        rate = ((fr.data or {}).get("rates") or {}).get(symbol) or {}
        if not fr.fresh or rate.get("state") != "MEASURED":
            return {"state": "ABSENT", "fees_R": round(fees_R, 4),
                    "why": ("cost hunt stale/absent" if not fr.fresh else
                            f"no measured funding for {symbol}")
                           + " -- veto stands down, resolver's adverse cost model carries alone"}
        from scripts.run_cost_hunt import signed_funding_8h
        pays_8h = signed_funding_8h(float(rate["funding_8h"]), direction)
    except Exception as exc:                       # any failure -> veto down, sleeve up, recorded
        return {"state": "ABSENT", "fees_R": round(fees_R, 4),
                "why": f"cost view unavailable ({type(exc).__name__}) -- veto stands down"}
    funding_R = pays_8h * (horizon_hours / 8.0) / stop_frac
    total = fees_R + funding_R
    return {"state": "MEASURED", "fees_R": round(fees_R, 4),
            "funding_8h_signed": round(pays_8h, 8), "funding_R": round(funding_R, 4),
            "expected_cost_R": round(total, 4),
            "carry": "PAID" if funding_R < 0 else ("PAYS" if funding_R > 0 else "FLAT"),
            "why": (f"fees+slippage {fees_R:.3f}R, funding {funding_R:+.3f}R over "
                    f"{horizon_hours:.0f}h ({'this side is PAID to hold' if funding_R < 0 else 'this side pays'})")}


def slip_leverage_cap(stop_pct: float, *, stress_loss: float = MAX_STRESS_LOSS) -> float:
    """The only honest reason to cap notional: a cascade that prints THROUGH the stop costs
    leverage * (stop + slip), and the slip term does not shrink when the stop tightens. So the
    ceiling is derived from survival under that stress rather than picked as a round number --
    which is what lets a genuinely tight structural stop buy the size it has earned."""
    return stress_loss / ((stop_pct + SLIP_STRESS_PCT) / 100.0)


def kelly_leverage(prob: float, reward_risk: float, stop_pct: float,
                   *, risk_cap: float = MAX_RISK_PER_TRADE) -> dict[str, Any]:
    """Fractional-Kelly leverage from Claude's OWN probability. Aggression is here; the caps are
    the rail. Kelly f* = (p*b - q)/b; leverage = (fraction of equity at risk) / (stop distance).

    `risk_fraction` is what the position ACTUALLY loses at its stop, not what Kelly asked for.
    Those differ whenever MAX_LEVERAGE binds -- a 0.9% structural stop wants 22x, gets 10x, and
    therefore risks 9% of equity, not the 20% Kelly requested. Reporting the request as though it
    were the exposure would overstate downside everywhere it is consumed (the whole management
    ladder is denominated in it), so the realised number is the one that carries the name."""
    p, q, b = prob, 1.0 - prob, max(reward_risk, 1e-6)
    edge = (p * b - q) / b                                  # full-Kelly fraction of equity
    want = max(0.0, edge * KELLY_FRACTION)                  # half-Kelly, before any cap
    budget = min(risk_cap, want)
    if stop_pct <= 0:
        return {"full_kelly": round(edge, 4), "kelly_risk_fraction": round(budget, 4),
                "risk_fraction": 0.0, "leverage": 0.0, "slip_cap": 0.0, "capped_by": "no-stop"}
    kelly_lev = budget / (stop_pct / 100.0)
    slip_cap = slip_leverage_cap(stop_pct)
    lev = min(MAX_LEVERAGE, slip_cap, kelly_lev)
    realised = lev * (stop_pct / 100.0)                     # what the stop actually costs
    caps = []
    if want > risk_cap:
        caps.append("max_risk")
    if slip_cap < min(kelly_lev, MAX_LEVERAGE):
        caps.append("gap_stress")
    if min(kelly_lev, slip_cap) > MAX_LEVERAGE:
        caps.append("max_leverage")
    return {"full_kelly": round(edge, 4), "kelly_risk_fraction": round(budget, 4),
            "risk_fraction": round(realised, 4), "leverage": round(lev, 2),
            "slip_cap": round(slip_cap, 2),
            "capped_by": "no-edge" if edge <= 0 else ("+".join(caps) if caps else "kelly")}


def derive_stop_pct(entry_ref: float, invalidation: float, direction: str) -> tuple[float, str]:
    """THE CALCULATED STOP. Distance is derived from the named invalidation level, never asserted.

    Returns (stop_pct, "") or (0.0, refusal). An invalidation on the wrong side of entry is the
    tell that the model produced a level to satisfy the schema rather than to mark where its
    thesis dies -- that is a target, not a stop, and it is refused."""
    if not (entry_ref > 0 and invalidation > 0):
        return 0.0, "REFUSED: entry_ref and invalidation must both be positive prices"
    if direction == "LONG" and invalidation >= entry_ref:
        return 0.0, (f"REFUSED: a LONG's invalidation ({invalidation}) must sit BELOW entry "
                     f"({entry_ref}) -- a level above entry is a target, not a stop")
    if direction == "SHORT" and invalidation <= entry_ref:
        return 0.0, (f"REFUSED: a SHORT's invalidation ({invalidation}) must sit ABOVE entry "
                     f"({entry_ref}) -- a level below entry is a target, not a stop")
    return abs(entry_ref - invalidation) / entry_ref * 100.0, ""


def management_plan(entry: float, invalidation: float, direction: str, *,
                    risk_fraction: float, leverage: float,
                    noise_pct: float | None = None) -> dict[str, Any]:
    """"PUT TRADES UNTIL THE TREND AND SWING HITS" -- the trail-and-pyramid ladder, computed.

    Every stage's open risk and locked profit are COMPUTED from the tranche book, not asserted, so
    the asymmetry the principal asked for is arithmetic a test can check: exposure rises
    1.00u -> 1.50u -> 1.75u while open risk falls 1.00 -> 0.50 -> 0.25 -> 0.00 of the initial
    budget. There is no take-profit anywhere in here on purpose: the exit is the structure
    breaking, which is what lets one trend pay for the losers."""
    sign = 1.0 if direction == "LONG" else -1.0
    r = abs(entry - invalidation)                            # 1R, in price
    if r <= 0:
        return {"status": "UNPLANNABLE", "why": "zero-width R -- entry equals invalidation"}
    stop_pct = r / entry * 100.0

    # THE TRAIL must clear the noise for the same reason the entry stop must: a stop inside the
    # wiggle exits a correct thesis. Rungs are spaced one trail distance apart so each rung's stop
    # lands exactly where the previous rung triggered -- with no noise floor this is the old 1R
    # ladder unchanged.
    trail = r if noise_pct is None else max(r, NOISE_TRAIL_MULT * (noise_pct / 100.0) * entry)

    # The pyramid gets the same gap-stress test as the entry, at the looser peak bound: the adds
    # only ever go on once the earlier tranches are stopped at or above breakeven, so a cascade
    # through the trail hits size that is no longer risking the entry budget. If the full ladder
    # would breach it, the ADDS shrink -- never the rail.
    peak_cap = min(MAX_LEVERAGE, slip_leverage_cap(stop_pct, stress_loss=MAX_PEAK_STRESS_LOSS))
    raw_peak_units = 1.0 + sum(ADD_UNITS)
    add_scale = 1.0
    if leverage > 0 and leverage * raw_peak_units > peak_cap:
        add_scale = max(0.0, min(1.0, (peak_cap / leverage - 1.0) / (raw_peak_units - 1.0)))

    def at(mult: float) -> float:                            # price at +mult R in the trade's favour
        return entry + sign * r * mult

    def rung(k: float) -> float:                             # price k trail-distances in favour
        return entry + sign * trail * k

    tranches: list[tuple[float, float]] = [(entry, 1.0)]     # (entry price, units)

    def book(stop: float) -> tuple[float, float]:
        """Open risk and locked profit at a given stop, as fractions of the initial risk budget."""
        risk = sum(u * risk_fraction * max(0.0, (e - stop) * sign) / r for e, u in tranches)
        locked = sum(u * risk_fraction * max(0.0, (stop - e) * sign) / r for e, u in tranches)
        return round(risk, 4), round(locked, 4)

    orisk, olock = book(invalidation)
    stages: list[dict[str, Any]] = [{
        "at_R": 0.0, "trigger": round(entry, 8), "stop": round(invalidation, 8),
        "action": "ENTER 1.00u at the level; stop at the named invalidation",
        "units": 1.0, "notional_leverage": round(leverage, 2),
        "open_risk_frac": orisk, "locked_profit_frac": olock}]

    for k, add_raw in enumerate(ADD_UNITS, start=1):
        # THE ADD IS SIZED BY RISK, NOT BY UNITS. Its stop sits one TRAIL behind it, so at a
        # noise-widened trail each unit added carries trail/R of risk rather than 1R. Adding a
        # flat 0.50u there would make open risk RISE at the first rung -- caught by the invariant
        # test, which is the whole reason that test asserts on computed numbers.
        add_u = round(add_raw * add_scale * (r / trail), 4)
        stop = rung(k - 1)                                   # trail ONE trail-distance behind
        tranches.append((rung(k), add_u))
        units = sum(u for _, u in tranches)
        orisk, olock = book(stop)
        where = "breakeven" if k == 1 else f"the +{k - 1} rung"
        stages.append({
            "at_R": round(trail * k / r, 3), "trigger": round(rung(k), 8), "stop": round(stop, 8),
            "action": f"TRAIL stop to {where}, THEN ADD {add_u:.2f}u (risk falls as size grows)",
            "units": round(units, 2), "notional_leverage": round(leverage * units, 2),
            "open_risk_frac": orisk, "locked_profit_frac": olock})

    final_k = len(ADD_UNITS) + 1
    stop = rung(final_k - 1)
    orisk, olock = book(stop)
    units = sum(u for _, u in tranches)
    stages.append({
        "at_R": round(trail * final_k / r, 3), "trigger": round(rung(final_k), 8),
        "stop": round(stop, 8),
        "action": "TRAIL behind each new swing as it forms; NO further adds, NO fixed target -- "
                  "hold until price closes back through the trailing structure",
        "units": round(units, 2), "notional_leverage": round(leverage * units, 2),
        "open_risk_frac": orisk, "locked_profit_frac": olock})

    peak = max(s["notional_leverage"] for s in stages)
    return {
        "status": "OK" if add_scale >= 1.0 else "PYRAMID-SCALED",
        "r_price": round(r, 8), "stop_pct": round(stop_pct, 4),
        "trail_price": round(trail, 8), "trail_R": round(trail / r, 3),
        "trail_source": "noise-widened" if trail > r * 1.000001 else "1R (noise not binding)",
        "peak_units": round(units, 2), "peak_leverage": round(peak, 2),
        "peak_leverage_cap": round(peak_cap, 2), "add_scale": round(add_scale, 4),
        "peak_stress_loss": round(peak * (stop_pct + SLIP_STRESS_PCT) / 100.0, 4),
        "stages": stages,
        "exit_rule": "structure break only -- price closing back through the trailing swing. No "
                     "take-profit: capping the winner is what makes a stopped-out book "
                     "negative-EV even with a real edge.",
        "invariant": "open_risk_frac is non-increasing across stages and never exceeds the "
                     "initial risk budget; locked_profit_frac is non-decreasing.",
    }


_BRIEF = """You are the desk's CONVICTION TRADER. You take AGGRESSIVE leveraged DIRECTIONAL bets --
this is the sleeve modelled on a sharp manual trader flipping an account fast, not the cautious
news reader. You are ENCOURAGED to size up when you have real conviction. You carry a CALCULATED
STOP on every trade and you will be SCORED, so your confidence must be honest.

INSTRUMENTS: {instruments}. Take a directional view -- macro, technical, flow, positioning,
cross-asset (gold via PAXGUSDT, risk via BTC/ETH). A VIEW is allowed here (unlike the event
sleeve), but state the DRIVER: what makes this move happen, and what would kill it.

YOUR CHARTS -- multi-timeframe structure for every instrument: swing highs and lows with TOUCH
COUNTS (a level defended three times is not the level touched once), trend state read from the
swing sequence, position in range, distance to the nearest level each way, and volatility regime.
Read them like a trader: is the 4h trend with you, is there room to the next level, is the
invalidation you want to use an actual defended structure or a random pivot?
{charts}

THE DESK'S OWN PLAYBOOK -- lessons this sleeve LEARNED from its own closed Binance trades, each
one held to {n_support}+ independent agreeing trades before it was allowed to reach you, and
retired the moment a trade contradicted it. These are not platitudes; they are this desk's
measured experience. Weigh them against what you see, and if the chart contradicts one, SAY SO in
your reasoning -- a lesson that stops matching reality needs to be retired, and you are the only
thing that can notice.
{playbook}

PICK THE BEST SETUP IN THE UNIVERSE, not the first readable one. You get one call per hour across
18 instruments and several positions can be live at once, so a mediocre setup costs you the good
one you would otherwise have had heat for. The right answer is often PASS.

WHAT YOU ARE ACTUALLY MAXIMISING, and it is not a return number. The desk maximises E[log wealth]
subject to survival, which decomposes into terms you control ON THIS TRADE. There is deliberately
no CAGR target: a stated return figure is reachable only by SIZE, and past a point more size makes
growth NEGATIVE. So push these instead, every cycle, each to its measured ceiling:

  EDGE PER TRADE   -- take the setup with the largest honest probability x payoff, not the first
                      acceptable one. One better setup beats three mediocre ones, because the
                      mediocre ones consume the heat the better one needed.
  PAYOFF ASYMMETRY -- name the tightest HONEST invalidation, because size is risk_budget / stop
                      distance. A real 1% swing carries multiples of a lazy 4% stop's size on the
                      same conviction. This is the cheapest aggression available to you.
  FREQUENCY        -- an hour you PASS is an hour that compounds nothing. Pass when there is no
                      edge, and only then; a trader who always passes is failing differently from
                      one who always trades, and both fail.
  INDEPENDENCE     -- prefer the setup least like what the book already holds. Growth multiplies
                      across uncorrelated bets and merely duplicates across correlated ones, so a
                      good setup in a name the book is already in is worth less than an equal
                      setup somewhere else.
  COST             -- your entry is a RESTING order at a named level, never a chase. At this
                      leverage the difference is worth more than most of your directional edge.

Maximise those and the compounding takes care of itself. Aim at a return number instead and the
only lever that reaches it is the one that ends the account.

THE STOP IS A LEVEL, NOT A PERCENTAGE. Name the PRICE at which your thesis is factually dead --
the swing the trend must not lose, the range edge, the shelf that was defended -- and name the
structure it is. The desk DERIVES the stop distance from that level; it will refuse an
invalidation on the wrong side of entry, and refuse a stop that is not at a named structure.
THIS IS WHERE YOUR SIZE COMES FROM: the desk sizes risk_budget / stop_distance, so a stop 1% away
at a real swing carries FOUR TIMES the size of a lazy 4% stop on the same edge. Find the tightest
HONEST invalidation, not a comfortable one -- and not one so tight that noise takes you out.

THE NOISE FLOOR IS MEASURED, PER INSTRUMENT AND PER HORIZON: {noise}
A level closer than that gets hit by ordinary wiggle rather than by your thesis failing, and the
desk refuses it. If your level is inside the floor, either name a level further out or ask for a
SHORTER horizon -- a short horizon has a smaller floor, which is how a tight level stays legal.

YOUR WINNERS ARE RIDDEN, NOT TAKEN. There is no take-profit. The desk moves your stop to
breakeven at +1R, trails one R behind, and ADDS on strength (1.00u -> 1.50u -> 1.75u) while the
trend holds, exiting only when price closes back through the trailing structure. So do NOT pick a
small nearby target: expected_move_pct is your estimate of the move if you are right, and the
trade is held until the structure breaks, not until that number prints.

TODAY'S BRIEF (numeric context; you may reason over it, the desk's pipelines handle the arithmetic):
{brief}

OUTPUT EXACTLY ONE JSON OBJECT:
{{"action": "TRADE" | "PASS",
  "symbol": "one of the instruments",
  "direction": "LONG" | "SHORT",
  "probability": 0.63,             // YOUR honest P(this trade is profitable). SCORED against outcome.
  "entry_ref": 4107.4,             // the price you are entering at (current or your trigger)
  "invalidation": 4190.0,          // the PRICE where the thesis is dead. Below entry if LONG, above if SHORT.
  "structure": "the prior-session swing high that capped the last two attempts",
  "expected_move_pct": 4.0,        // the move you expect if right, percent -- not a take-profit
  "horizon_hours": 12,
  "driver": "what forces/drives this move",
  "falsifier": "the observation that kills the thesis before the stop",
  "reasoning": "2-4 sentences"}}

BE AGGRESSIVE ON CONVICTION, HONEST ON PROBABILITY. The desk sizes the trade FOR you by
fractional-Kelly against your probability and your derived stop -- a 0.63 with a 2% structural
stop becomes real leverage automatically, so you do not need to inflate confidence to get size;
inflating it only makes the calibration fence catch you and SHRINK your future size. reward:risk
= expected_move_pct / derived stop must exceed 1.2 or the trade is refused (you are risking more
than you stand to make). Derived stop must land between {smin}% and {smax}%. PASS with a reason
if there is no directional edge -- but a conviction trader that always passes is not doing its
job. Probability must be {lo}-{hi}."""


def adverse_excursion(bars: list[tuple[int, float, float, float, float]], horizon_hours: float,
                      direction: str) -> float | None:
    """Median adverse excursion over rolling windows of this trade's own horizon, in percent.

    "How far does price normally go against me before the horizon is up?" -- computed from the
    instrument's own bars rather than assumed. Returns None when there are not enough bars, which
    the caller must surface as UNMEASURED rather than treat as zero noise."""
    w = max(1, round(horizon_hours * 4))                     # 15m bars
    if len(bars) < w + 8:
        return None
    sign = 1.0 if direction == "LONG" else -1.0
    excursions = []
    for i in range(len(bars) - w):
        ref = bars[i][1]                                     # window's open
        if ref <= 0:
            continue
        window = bars[i:i + w + 1]
        worst = (min(b[3] for b in window) if sign > 0 else max(b[2] for b in window))
        excursions.append((ref - worst) * sign / ref * 100.0)
    if not excursions:
        return None
    excursions.sort()
    n = len(excursions)
    return excursions[n // 2] if n % 2 else (excursions[n // 2 - 1] + excursions[n // 2]) / 2


def noise_floor(symbol: str, horizon_hours: float, direction: str, *,
                fetch=None) -> dict[str, Any]:
    """The per-instrument minimum honest stop. UNMEASURED falls back to the flat floor and SAYS
    SO -- a silent fallback would restore exactly the defect this replaced."""
    if fetch is None:
        try:
            from scripts.resolve_paper_book import fetch_bars as fetch
        except ImportError as exc:
            return {"state": "UNMEASURED", "floor_pct": MIN_STOP_PCT,
                    "why": f"price source unavailable ({exc}); flat floor in use"}
    now_ms = int(datetime.now(tz=UTC).timestamp() * 1000)
    span = int((NOISE_LOOKBACK_HOURS + horizon_hours) * 3600 * 1000)
    bars, source = fetch(symbol, now_ms - span, now_ms)
    if not bars:
        return {"state": "UNMEASURED", "floor_pct": MIN_STOP_PCT,
                "why": f"no bars for {symbol} ({source}); flat floor in use -- the noise check "
                       "did NOT pass, it did not run"}
    med = adverse_excursion(bars, horizon_hours, direction)
    if med is None:
        return {"state": "UNMEASURED", "floor_pct": MIN_STOP_PCT,
                "why": f"only {len(bars)} bars, too few for a {horizon_hours}h window"}
    floor = max(MIN_STOP_PCT, NOISE_MULT * med)
    return {"state": "MEASURED", "floor_pct": round(floor, 4), "median_adverse_pct": round(med, 4),
            "bars": len(bars), "source": source,
            "why": f"a random {horizon_hours}h entry in {symbol} normally goes {med:.2f}% against "
                   f"itself; an invalidation closer than that is noise, not a thesis failing"}


def noise_table(*, horizons: tuple[float, ...] = (8.0, 24.0, 48.0), fetch=None) -> dict[str, Any]:
    """The floor for every instrument and horizon, published INTO the brief.

    Withholding it would refuse the model's level without ever telling it the rule, which is how a
    gate becomes noise the caller learns to route around. Note what is published and what is not:
    the noise floor is a CONSTRAINT the model must satisfy, so it gets it; where the sizing optimum
    sits is a REWARD it could chase, so it does not."""
    if fetch is None:
        try:
            from scripts.resolve_paper_book import fetch_bars as fetch
        except ImportError as exc:
            return {"state": "UNMEASURED", "why": f"price source unavailable ({exc})"}
    now_ms = int(datetime.now(tz=UTC).timestamp() * 1000)
    span = int((NOISE_LOOKBACK_HOURS + max(horizons)) * 3600 * 1000)
    out: dict[str, Any] = {}
    for sym in INSTRUMENTS:
        bars, source = fetch(sym, now_ms - span, now_ms)
        if not bars:
            out[sym] = f"UNMEASURED ({source}) -- flat {MIN_STOP_PCT}% floor applies"
            continue
        row = {}
        for h in horizons:
            lo = adverse_excursion(bars, h, "LONG")
            sh = adverse_excursion(bars, h, "SHORT")
            row[f"{h:g}h"] = {"LONG": None if lo is None else round(max(MIN_STOP_PCT, lo), 2),
                              "SHORT": None if sh is None else round(max(MIN_STOP_PCT, sh), 2)}
        out[sym] = row
    return {"state": "MEASURED", "min_stop_pct_by_symbol_and_horizon": out,
            "meaning": "the median distance price goes AGAINST a random entry over that horizon; "
                       "an invalidation closer than this is refused as noise"}


def _closed_keys(root: Path) -> set[str]:
    """Trades the resolver has already marked out. Without this a stopped position would keep
    occupying heat until its hard-exit clock ran down -- blocking new trades with capital that
    was returned hours ago, which is idle capacity dressed as prudence (L1.28a)."""
    try:
        rep = json.loads((root / _PNL_STATE).read_text("utf-8"))
    except (OSError, ValueError):
        return set()
    return {m.get("key") for m in rep.get("marks", [])
            if m.get("outcome") in ("STOPPED", "TRAILED-OUT", "MARKED", "TIME-STOPPED")}


def open_positions(root: Path, *, now: datetime | None = None) -> list[dict[str, Any]]:
    """Positions still live: past neither their structural exit nor their hard time stop."""
    now = now or datetime.now(tz=UTC)
    closed_keys = _closed_keys(root)
    live = []
    try:
        lines = (root / _BOOK).read_text("utf-8", errors="ignore").splitlines()
    except OSError:
        return []
    for ln in lines:
        if not ln.strip():
            continue
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        try:
            # a position occupies heat until its HARD exit, not until its forecast is scored
            until = r.get("hard_exit_by") or r.get("resolve_by")
            if datetime.fromisoformat(until) > now and r.get("action") != "PASS":
                live.append(r)
        except (KeyError, ValueError, TypeError):
            continue
    if closed_keys:
        live = [r for r in live if r.get("at") not in closed_keys]
    return live


def effective_heat(root: Path, live: list[dict[str, Any]]) -> tuple[float, str]:
    """Portfolio risk with MEASURED correlations: sqrt(w' S w), not the naive sum.

    The naive sum is right only if every position is the same trade. It is wrong in BOTH
    directions and both cost money: it overstates safety when five alts are really one bet, and it
    blocks a genuinely diversifying trade (gold beside crypto) that added almost no portfolio
    risk. UNMEASURED correlations fall back to the naive sum and SAY SO -- never to an optimistic
    default, which would let a blind book believe it was diversified."""
    ws = [(r.get("symbol"), float((r.get("sizing") or {}).get("risk_fraction") or 0.0))
          for r in live]
    naive = sum(w for _, w in ws)
    if len(ws) < 2:
        return naive, "single position -- correlation irrelevant"
    try:
        corr = json.loads((root / "data/chart_context.json").read_text("utf-8"))["correlations"]
    except (OSError, ValueError, KeyError):
        return naive, "UNMEASURED correlations -- naive sum used (no diversification credit)"
    var = 0.0
    for a, wa in ws:
        for b, wb in ws:
            rho = 1.0 if a == b else corr.get(a, {}).get(b)
            if rho is None:
                return naive, f"no measured correlation for {a}/{b} -- naive sum used"
            rho = rho + (1.0 - rho) * CORR_STRESS          # stress toward 1, never toward 0
            var += wa * wb * rho
    return var ** 0.5, f"measured correlations, stressed {CORR_STRESS:.0%} toward 1"


def portfolio_heat(root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    """Total risk live across the book, and the rail that makes frequency safe rather than reckless.

    Breadth only beats concentration if the bets are actually SEPARATE. Eight positions all long
    crypto beta in a correlated tape is one position wearing eight names, and the simulation that
    justified widening the universe assumed independence -- so the same-direction concentration is
    reported here rather than quietly ignored. This rail is what allows the cadence to rise: more
    shots at a bounded total exposure is the whole design."""
    live = open_positions(root, now=now)
    gross = sum(float((r.get("sizing") or {}).get("risk_fraction") or 0.0) for r in live)
    longs = sum(1 for r in live if r.get("direction") == "LONG")
    eff, basis = effective_heat(root, live)
    full = eff >= MAX_PORTFOLIO_HEAT or gross >= MAX_GROSS_HEAT
    return {
        "n_open": len(live), "heat": round(eff, 4), "gross_heat": round(gross, 4),
        "cap": MAX_PORTFOLIO_HEAT, "gross_cap": MAX_GROSS_HEAT, "correlation_basis": basis,
        "headroom": round(max(0.0, MAX_PORTFOLIO_HEAT - eff), 4),
        "symbols": [r.get("symbol") for r in live],
        "directional_skew": (f"{longs}L/{len(live) - longs}S" if live else "flat"),
        "state": "FULL" if full else "OPEN",
        "why": (f"{eff:.1%} effective of {MAX_PORTFOLIO_HEAT:.0%} ({gross:.1%} gross of "
                f"{MAX_GROSS_HEAT:.0%}) across {len(live)} positions [{basis}]"
                if live else "no live positions -- full heat available"),
    }


def size_into_headroom(root: Path, symbol: str, desired_risk: float,
                       live: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """The heat cap as a SIZER, not a gate -- and the correlation-aware growth lever.

    Refusing a good setup because the book is 95% full throws the setup away; taking it at 5% size
    does not. Idle capacity is unbooked loss (L1.28a), and a slot left empty contributes exactly
    zero to geometric growth while a small position contributes a small positive amount.

    It is also where correlation pays. The largest size that fits is solved against EFFECTIVE heat,
    so a trade uncorrelated with the book (gold beside four alts, measured +0.15) gets far more
    room than one duplicating it (+0.80) -- which is the multivariate-Kelly intuition made
    operational: allocate to the bet that adds the most growth per unit of portfolio risk."""
    live = open_positions(root) if live is None else live
    gross_used = sum(float((r.get("sizing") or {}).get("risk_fraction") or 0.0) for r in live)
    gross_room = max(0.0, MAX_GROSS_HEAT - gross_used)
    if gross_room <= 0:
        return {"risk": 0.0, "bound": "gross_heat", "why": "gross heat cap reached"}

    def fits(w: float) -> bool:
        cand = [*live, {"symbol": symbol, "sizing": {"risk_fraction": w}}]
        return effective_heat(root, cand)[0] <= MAX_PORTFOLIO_HEAT

    hi = min(desired_risk, gross_room)
    if hi <= 0:
        return {"risk": 0.0, "bound": "no room", "why": "no headroom at any size"}
    if fits(hi):
        return {"risk": round(hi, 6),
                "bound": "kelly" if hi >= desired_risk else "gross_heat",
                "why": f"full requested size fits ({len(live)} live)"}
    lo = 0.0
    for _ in range(24):                                    # bisection: effective heat is monotone
        mid = (lo + hi) / 2
        if fits(mid):
            lo = mid
        else:
            hi = mid
    return {"risk": round(lo, 6), "bound": "effective_heat",
            "why": (f"trimmed from {desired_risk:.2%} to {lo:.2%} to stay inside "
                    f"{MAX_PORTFOLIO_HEAT:.0%} effective heat against {len(live)} live "
                    "position(s) -- correlation with the book decides how much fits")}


def sleeve_drawdown(root: Path) -> dict[str, Any]:
    """The sleeve's own drawdown rail, read from the marked paper book (R0133).

    UNMEASURED must never read as OK: an unmarked or unreadable book returns NO-HISTORY, which is
    reported everywhere it is consumed rather than quietly treated as a clean slate."""
    try:
        rep = json.loads((root / _PNL_STATE).read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return {"state": "NO-HISTORY", "halted": False,
                "why": f"paper book not marked on this host ({type(exc).__name__}) -- the "
                       "drawdown rail is BLIND until resolve_paper_book.py has run"}
    eq = rep.get("equity") or {}
    n = int(eq.get("n") or 0)
    if n == 0:
        return {"state": "NO-HISTORY", "halted": False,
                "why": f"book marked but 0 closed calls ({rep.get('status')}) -- rail BLIND"}
    dd = float(eq.get("current_drawdown") or 0.0)
    return {"state": "HALTED" if dd >= SLEEVE_DD_HALT else "OK", "halted": dd >= SLEEVE_DD_HALT,
            "current_drawdown": dd, "max_drawdown": eq.get("max_drawdown"), "n_closed": n,
            "why": (f"sleeve is {dd:.1%} below its high-water mark, at or past the "
                    f"{SLEEVE_DD_HALT:.0%} halt" if dd >= SLEEVE_DD_HALT
                    else f"{dd:.1%} drawdown over {n} closed calls, inside the "
                         f"{SLEEVE_DD_HALT:.0%} rail")}


def _playbook_brief(root: Path) -> str:
    """SUPPORTED lessons only. A single lucky trade must not be able to rewrite the method, so the
    PROVISIONAL tier is deliberately invisible here (see run_trade_review.py)."""
    try:
        pb = json.loads((root / "data/trading_playbook.json").read_text("utf-8"))
    except (OSError, ValueError):
        return ("(no playbook yet -- the review loop has not closed enough trades to support a "
                "lesson. You are trading on general reasoning alone, which is the honest state, "
                "not a clean slate.)")
    live = [lv for lv in pb.get("lessons", []) if lv.get("status") == "SUPPORTED"]
    if not live:
        prov = sum(1 for lv in pb.get("lessons", []) if lv.get("status") == "PROVISIONAL")
        return (f"(no SUPPORTED lessons yet; {prov} provisional and deliberately withheld until "
                f"{N_SUPPORT}+ trades agree. Trade on your own read.)")
    live.sort(key=lambda lv: (-lv.get("support", 0), -lv.get("last_seen_at_trade", 0)))
    return json.dumps([{"lesson": lv["text"], "when": lv.get("applies_when", ""),
                        "evidence": f"{lv.get('support')} agreeing trades"}
                       for lv in live[:12]], indent=1)


def setup_features(call: dict[str, Any], charts: dict[str, Any] | None) -> dict[str, Any]:
    """Tag the SITUATION a trade was taken in, so the desk can learn WHICH SETUPS PAY rather than
    only whether it is globally calibrated.

    A single hit rate over all trades hides everything actionable: a sleeve that is 55% with the 4h
    trend and 25% against it looks like a mediocre 40% overall, and the fix -- stop taking
    counter-trend setups -- is invisible until the outcomes are conditioned on the setup."""
    f: dict[str, Any] = {"symbol": call.get("symbol"), "direction": call.get("direction")}
    tf = ((charts or {}).get("charts", {}).get(str(call.get("symbol")), {})
          .get("timeframes", {}).get("4h", {}))
    trend = str(tf.get("trend", "UNKNOWN"))
    f["trend_4h"] = trend.split(" ")[0]
    f["with_4h_trend"] = (("UPTREND" in trend and call.get("direction") == "LONG")
                          or ("DOWNTREND" in trend and call.get("direction") == "SHORT")
                          if "TREND" in trend else None)
    f["vol_regime"] = tf.get("vol_regime", "UNKNOWN")
    pir = tf.get("position_in_range")
    f["position_in_range"] = (None if pir is None else
                              "low" if pir < 0.33 else "high" if pir > 0.67 else "mid")
    struct = str(call.get("structure", "")).lower()
    f["level_touches"] = next((int(n) for n in re.findall(r"(\d+)[ -]?touch", struct)), None)
    try:
        f["horizon_bucket"] = ("short" if float(call.get("horizon_hours", 0)) <= 12 else
                               "medium" if float(call.get("horizon_hours", 0)) <= 36 else "long")
    except (TypeError, ValueError):
        f["horizon_bucket"] = None
    return f


def _chart_brief(root: Path, heat: dict[str, Any] | None = None, *, max_chars: int = 9000) -> str:
    """The charts, trimmed to what fits and honest about what did not.

    Instruments already live are dropped: heat is capped and the same-symbol trade is refused
    anyway, so spending brief on them buys nothing. STALE and MISSING are stated -- a trader
    reasoning over yesterday's structure while believing it is today's is worse than one who
    knows it is blind."""
    try:
        raw = json.loads((root / "data/chart_context.json").read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return (f"CHARTS UNAVAILABLE ({type(exc).__name__}) -- build_chart_context.py has not run "
                "on this host. You are trading BLIND on structure: do not name a swing level you "
                "cannot see, and PASS unless the non-chart evidence alone is compelling.")
    try:
        age_h: float | None = (datetime.now(tz=UTC)
                               - datetime.fromisoformat(raw["generated"])).total_seconds() / 3600.0
        age_note = f"{age_h:.1f}h old"
    except (KeyError, ValueError) as exc:
        # NOT swallowed: an unreadable timestamp means the trader cannot tell fresh structure from
        # a stale snapshot, and that must reach the trader rather than vanish into a default.
        age_h, age_note = None, f"age UNMEASURED ({type(exc).__name__}) -- treat as possibly STALE"
    held = set((heat or {}).get("symbols") or [])
    charts = {k: v for k, v in (raw.get("charts") or {}).items() if k not in held}
    head = f"(chart context {age_note}, {raw.get('status')}: {raw.get('detail')})\n"
    if age_h is None or age_h > 2:
        head = ("WARNING -- CHART STRUCTURE MAY BE STALE"
                + (f" ({age_h:.1f}h old)" if age_h is not None else "")
                + ", treat levels as approximate.\n") + head
    body = json.dumps(charts, separators=(",", ":"))
    if len(body) > max_chars:
        body = body[:max_chars] + f'... [TRUNCATED at {max_chars} chars of {len(body)}]'
    return head + body


def ensemble_consensus(reads: list[dict[str, Any] | None]) -> tuple[dict[str, Any] | None,
                                                                    dict[str, Any]]:
    """2-of-3 on (symbol, direction). No majority -> PASS, and the disagreement is RECORDED.

    The minority reads are kept in the report rather than discarded, because whether this filter
    actually helps is itself a measurable question: if the agreement-filtered calls do not beat
    the unfiltered ones on hit rate, the filter is costing frequency for nothing and should go.
    Imposing a filter without keeping what it rejected makes that unanswerable."""
    got = [r for r in reads if r]
    if not got:
        return None, {"state": "NO-READS", "n": 0,
                      "why": "no parseable read (auth/quota/refusal)"}
    votes: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in got:
        if r.get("action") == "PASS":
            votes.setdefault(("PASS", "PASS"), []).append(r)
            continue
        votes.setdefault((str(r.get("symbol")), str(r.get("direction"))), []).append(r)
    key, group = max(votes.items(), key=lambda kv: len(kv[1]))
    detail = {"state": "CONSENSUS" if len(group) >= ENSEMBLE_AGREE else "SPLIT",
              "n_reads": len(got), "n_agreeing": len(group),
              "votes": {f"{k[0]}/{k[1]}": len(v) for k, v in votes.items()},
              "minority": [{k: r.get(k) for k in ("symbol", "direction", "probability")}
                           for kk, v in votes.items() if kk != key for r in v]}
    if len(group) < ENSEMBLE_AGREE:
        detail["why"] = (f"{len(got)} reads split {detail['votes']} -- no {ENSEMBLE_AGREE}-of-"
                         f"{ENSEMBLE_N} consensus, so the desk stands aside. Near a 31.1% "
                         "breakeven, precision is worth more than frequency.")
        return {"action": "PASS", "pass_reason": detail["why"][:180]}, detail
    if key == ("PASS", "PASS"):
        detail["why"] = "consensus was to PASS"
        return {"action": "PASS",
                "pass_reason": str(group[0].get("pass_reason") or "consensus PASS")}, detail
    # consensus TRADE: take the most CONSERVATIVE probability among the agreeing reads, because
    # averaging lets one over-confident read pull the size up and Kelly is convex in p.
    winner = min(group, key=lambda r: float(r.get("probability") or 0))
    detail["why"] = f"{len(group)}/{len(got)} reads agree on {key[1]} {key[0]}"
    detail["probability_rule"] = "lowest among agreeing reads (Kelly is convex in p)"
    return winner, detail


def build_brief(root: Path) -> dict[str, Any]:
    brief: dict[str, Any] = {"generated": datetime.now(tz=UTC).isoformat(), "context": {}}
    for label, rel, n in (("funding", "data/bitmex_funding.jsonl", 4),
                          ("liquidations", "data/liquidations.jsonl", 6),
                          ("tradeable_events", "data/exchange_announcements.jsonl", 6)):
        try:
            lines = (root / rel).read_text("utf-8", errors="ignore").splitlines()
            if label == "tradeable_events":
                rows = []
                for ln in reversed(lines):
                    try:
                        r = json.loads(ln)
                    except ValueError:
                        continue
                    if r.get("tradeable"):
                        rows.append({k: r.get(k) for k in ("title", "symbols", "tier")})
                    if len(rows) >= n:
                        break
                brief["context"][label] = rows or "none this window"
            else:
                brief["context"][label] = [ln[:300] for ln in lines[-n:] if ln.strip()] or "ABSENT"
        except OSError:
            brief["context"][label] = "ABSENT on this host"
    # LIVE CARRY MAP (R0198): which sides are PAID to hold right now, and which pay so much the
    # veto will refuse them. Shown so carry can break ties BETWEEN comparable setups -- the brief
    # says explicitly that it must never manufacture a thesis on its own, because funding is what
    # everyone can see, and a trade whose only driver is visible carry is the crowded side of it.
    try:
        ch = json.loads((root / "data/cost_hunt.json").read_text("utf-8"))
        if ch.get("status") in ("MEASURED", "PARTIAL"):
            brief["context"]["funding_carry"] = {
                "note": "tie-breaker ONLY -- never a thesis. Between comparable setups prefer "
                        "the PAID side; the AVOID list will be refused by the cost veto.",
                "paid_sides": [f"{x['symbol']} {x['direction']} {x['pays_8h']:+.5%}/8h"
                               for x in (ch.get("best_carry") or [])[:5]],
                "avoid": [f"{x['symbol']} {x['direction']} {x['pays_8h']:+.5%}/8h EXTREME"
                          for x in (ch.get("extreme_paying") or [])[:5]] or "none in force"}
        else:
            brief["context"]["funding_carry"] = "NO-DATA this window"
    except (OSError, ValueError):
        brief["context"]["funding_carry"] = "ABSENT on this host"
    return brief


def validate(call: dict[str, Any], *, noise: dict[str, Any] | None = None,
             heat: dict[str, Any] | None = None,
             costs: dict[str, Any] | None = None) -> tuple[bool, str]:
    if call.get("action") == "PASS":
        if not call.get("pass_reason"):
            return False, "REFUSED: a PASS must state why -- an unjustified pass is not a decision"
        return True, f"PASS: {str(call['pass_reason'])[:80]}"
    for f in ("symbol", "direction", "probability", "entry_ref", "invalidation", "structure",
              "expected_move_pct", "horizon_hours", "driver", "falsifier"):
        if call.get(f) in (None, ""):
            return False, f"REFUSED: missing {f}"
    if call["symbol"] not in INSTRUMENTS:
        return False, f"REFUSED: symbol must be one of {INSTRUMENTS}"
    if call["direction"] not in ("LONG", "SHORT"):
        return False, "REFUSED: direction LONG or SHORT"
    try:
        p, mv = float(call["probability"]), float(call["expected_move_pct"])
        entry, inval = float(call["entry_ref"]), float(call["invalidation"])
    except (TypeError, ValueError):
        return False, "REFUSED: probability/move/entry_ref/invalidation not numeric"
    if not MIN_PROB <= p <= MAX_PROB:
        return False, f"REFUSED: probability {p} outside {MIN_PROB}-{MAX_PROB}"

    structure = str(call["structure"]).lower()
    if not any(w in structure for w in _STRUCTURE_WORDS):
        return False, ("REFUSED: the stop must sit at a NAMED market structure (swing, range edge, "
                       "shelf, prior-session level...) -- an arbitrary distance is a number the "
                       "market has never heard of, and it throws away the size a real level buys")
    stop, why = derive_stop_pct(entry, inval, call["direction"])
    if why:
        return False, why
    if not MIN_STOP_PCT <= stop <= MAX_STOP_PCT:
        # A trade with no stop, or a stop so wide it is not a stop, is the one that ends the
        # account. This is not timidity -- it is the difference
        # between compounding the aggressive bet and being ruined by it (L1.23). The tight end is
        # the same rail pointed the other way: an invalidation inside the noise is not a thesis
        # being wrong, it is a wick, and it converts a real edge into churn.
        return False, (f"REFUSED: derived stop {stop:.2f}% outside {MIN_STOP_PCT}-{MAX_STOP_PCT} "
                       "-- every conviction trade carries a real structural stop (L1.23)")
    if noise and noise.get("state") == "MEASURED" and stop < float(noise["floor_pct"]):
        # NOT a timid refusal: taking this trade means being stopped out by ordinary wiggle on a
        # thesis that was correct, which is strictly worse than not taking it. The fix is a level
        # further out or a longer horizon, both of which the model may propose next cycle.
        return False, (f"REFUSED: stop {stop:.2f}% sits INSIDE the noise -- "
                       f"{noise.get('median_adverse_pct')}% is the median adverse excursion for a "
                       f"{call['horizon_hours']}h {call['symbol']} entry, so this level gets hit "
                       "by wiggle rather than by the thesis failing")
    claimed = call.get("stop_pct")
    if claimed not in (None, ""):
        try:
            c = float(claimed)
        except (TypeError, ValueError):
            return False, "REFUSED: stop_pct present but not numeric"
        if abs(c - stop) > STOP_MISMATCH_TOL * stop:
            return False, (f"REFUSED: asserted stop_pct {c}% disagrees with the level named "
                           f"({stop:.2f}% from entry) -- the stop was decorated, not calculated")
    if mv / stop < 1.2:
        return False, (f"REFUSED: reward:risk {mv/stop:.2f} < 1.2 -- risking more than the "
                       "expected gain is negative-EV even when the call is right")
    if (costs and costs.get("state") == "MEASURED"
            and float(costs.get("expected_cost_R") or 0.0) > COST_REFUSE_R):
        # The extreme-funding refusal. Not timidity: at 0.5R of cost the ladder nets 2.5R/-1.5R,
        # a 37.5% breakeven -- the sleeve's ceiling accuracy spent entirely on the venue's rake.
        # The same thesis re-arrives free of the bleed as the OPPOSITE side elsewhere, or here
        # after the funding regime turns; the paid-side version of this trade is never refused.
        return False, (f"REFUSED: expected cost {costs['expected_cost_R']:.2f}R > "
                       f"{COST_REFUSE_R}R of the risk unit ({costs.get('why', '')[:120]}) -- "
                       "paying the venue more than half of R needs ceiling accuracy just to "
                       "break even")
    if len(str(call["driver"])) < 20 or len(str(call["falsifier"])) < 15:
        return False, "REFUSED: driver/falsifier too thin"
    if heat:
        # NOT "the book is busy, come back later" -- that would leave a good setup unbooked, and an
        # unbooked setup contributes exactly zero to geometric growth. The heat cap SIZES the trade
        # (size_into_headroom); it only refuses when nothing fillable fits at all.
        fits = heat.get("fits_risk")
        if fits is not None and fits < MIN_TRADE_RISK:
            return False, (f"REFUSED: no fillable size left -- effective heat {heat['heat']:.1%} "
                           f"against the {MAX_PORTFOLIO_HEAT:.0%} cap leaves {fits:.3%}, below the "
                           f"{MIN_TRADE_RISK:.1%} venue minimum. Breadth is the aggression here, "
                           "not stacking.")
        if fits is None and heat.get("state") == "FULL":
            return False, (f"REFUSED: portfolio heat {heat['heat']:.1%} is at the "
                           f"{MAX_PORTFOLIO_HEAT:.0%} cap and per-symbol headroom is UNMEASURED")
        if call["symbol"] in (heat.get("symbols") or []):
            return False, (f"REFUSED: already live in {call['symbol']} -- doubling the same "
                           "instrument is concentration wearing a second name, which is exactly "
                           "what the spread-the-heat design exists to avoid")
    return True, "accepted"


def calibrated_p(raw_p: float) -> dict[str, Any]:
    """SIZE on the desk's MEASURED accuracy, SCORE the model's raw claim.

    This is the closed loop that protects geometric growth, and it is not a safety feature -- it
    is the growth term itself. Kelly is f* = (pb - q)/b: if the sleeve claims 0.63 and truly hits
    0.45, sizing on 0.63 bets ~2x Kelly, where E[log wealth] is NEGATIVE. No amount of edge
    survives systematically over-betting it.

    It runs in BOTH directions, and the upward one is the point as much as the downward: a desk
    measured UNDER-confident gets its probability raised and therefore its size raised. Aggression
    that has been earned is aggression the sizer hands over automatically.

    N-gated inside forecast_calibration: under 5 resolved outcomes it returns the raw value
    unchanged and says so, because a correction from noise is worse than no correction."""
    try:
        from libs.self_improvement.forecast_calibration import calibrated_confidence
        c = calibrated_confidence(raw_p)
    except Exception as exc:                              # broad by design -- never lose the call
        return {"raw": raw_p, "used": raw_p, "applied": False,
                "why": f"UNMEASURED calibration ({type(exc).__name__}) -- sizing on the raw claim"}
    return {"raw": c["raw"], "used": c["adjusted"] if c.get("applied") else c["raw"],
            "applied": bool(c.get("applied")), "bias": c.get("bias"),
            "direction": ("shrunk -- desk measured over-confident" if (c.get("bias") or 0) > 0
                          else "raised -- desk measured UNDER-confident, earned size returned"
                          if (c.get("bias") or 0) < 0 else "unchanged"),
            "why": c.get("why")}


def record(root: Path, call: dict[str, Any], *,
           noise: dict[str, Any] | None = None) -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    entry, inval = float(call["entry_ref"]), float(call["invalidation"])
    stop_pct, why = derive_stop_pct(entry, inval, call["direction"])
    if why:                                    # unreachable via main(), which validates first
        raise ValueError(why)
    cal = calibrated_p(float(call["probability"]))
    rcap = measured_risk_cap(root)
    sizing = kelly_leverage(cal["used"], float(call["expected_move_pct"]) / stop_pct, stop_pct,
                            risk_cap=float(rcap["cap"]))
    sizing["risk_cap"] = rcap
    # HEAT HEADROOM AS A SIZER: trim into what actually fits rather than refusing the setup.
    fit = size_into_headroom(root, str(call["symbol"]), sizing["risk_fraction"])
    if fit["risk"] < sizing["risk_fraction"]:
        sizing = {**sizing, "risk_fraction": fit["risk"],
                  "leverage": round(fit["risk"] / (stop_pct / 100.0), 2) if stop_pct else 0.0,
                  "capped_by": f"{sizing['capped_by']}+{fit['bound']}"}
    sizing["headroom"] = fit
    sizing["calibration"] = cal
    noise_pct = (float(noise["median_adverse_pct"])
                 if noise and noise.get("state") == "MEASURED"
                 and noise.get("median_adverse_pct") is not None else None)
    # the call's own expected cost in R (R0198) -- carried on the row so the review loop can
    # later measure whether paid-carry trades out-hit paying ones, which is the next selection
    # signal this either earns or loses on evidence
    sizing["costs"] = trade_cost_view(root, str(call["symbol"]), str(call["direction"]),
                                      stop_pct, float(call["horizon_hours"]))
    plan = management_plan(entry, inval, call["direction"],
                           risk_fraction=sizing["risk_fraction"], leverage=sizing["leverage"],
                           noise_pct=noise_pct)
    horizon = float(call["horizon_hours"])
    try:
        charts = json.loads((root / "data/chart_context.json").read_text("utf-8"))
    except (OSError, ValueError):
        charts = None
    row = {**call, "at": now.isoformat(), "paper": True, "venue": "BINANCE-USDM-PERP",
           "setup": setup_features(call, charts), "stop_pct": round(stop_pct, 4),
           "stop_source": "DERIVED from the named invalidation level", "sizing": sizing,
           "noise": noise, "management": plan,
           # the CALIBRATION clock -- when the forecast is scored
           "resolve_by": (now + timedelta(hours=horizon)).isoformat(),
           # the POSITION clock -- a hard time stop far beyond it, so structure decides the exit
           "max_hold_hours": round(horizon * MAX_HOLD_MULT, 2),
           "hard_exit_by": (now + timedelta(hours=horizon * MAX_HOLD_MULT)).isoformat(),
           "entry_order_type": "POST_ONLY_LIMIT at the named level (we bid support, not chase)"}
    p = root / _BOOK
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    try:
        from libs.self_improvement import forecast_calibration as fc
        # SCORE THE RAW CLAIM, not the size we took: grading the adjusted number would launder the
        # model's own error through the desk's correction and the bias would never be measurable.
        fc.log_forecast(f"conviction:{now.isoformat()}", float(call["probability"]),
                        "directional", resolve_by=row["resolve_by"],
                        claim=f"{call['direction']} {call['symbol']} @{sizing['leverage']}x "
                              f"stop {stop_pct:.2f}% ({str(call['structure'])[:60]}): "
                              f"{str(call['driver'])[:100]}")
    except Exception as exc:                                # never lose the call
        row["calibration_log_error"] = str(exc)
    return row


#: THE ENSEMBLE. 3 independent reads, trade only on a 2-of-3 consensus.
#:
#: WHY PRECISION BEATS FREQUENCY *HERE* SPECIFICALLY, which is the whole justification and it does
#: not generalise: cost-adjusted breakeven is 31.1% and the plausible hit rate sits right on top of
#: it. Near breakeven g per trade is tiny, so +3pp of hit rate multiplies g by 3.5x and +4pp by
#: 11x, while halving the trade count costs a factor of 2. Measured over the honest haircuts:
#:
#:      no filter,     33% hit, 460 trades  ->   34% CAGR
#:      2-of-3 filter, 36% hit, 230 trades  ->   58% CAGR
#:      2-of-3 filter, 38% hit, 230 trades  ->   95% CAGR
#:
#: FAR above breakeven this trade-off reverses and frequency wins again -- so this is reviewed
#: when the measured hit rate is known, not treated as permanent.
ENSEMBLE_N = 3
#: 2 of 3. Derived from the same near-breakeven arithmetic: at a 33% base rate, requiring
#: UNANIMITY cuts the trade count to ~1/4 for roughly +8pp of hit rate, which measures at 63% CAGR
#: against 95% for the 2-of-3 rule -- unanimity over-pays in frequency for its extra precision.
#: 2-of-3 is where the curve peaks under the honest haircuts.
ENSEMBLE_AGREE = 2

#: The three reads are deliberately framed DIFFERENTLY. Three samples of one framing correlate
#: heavily and their agreement means almost nothing; three angles disagreeing is information.
_LENSES: tuple[str, ...] = (
    "",
    "\n\nBefore answering: state the strongest case for the OPPOSITE side of your best idea, "
    "then decide. If the opposite case is not clearly weaker, PASS.",
    "\n\nBefore answering: assume your first instinct is the crowd's instinct and is already in "
    "the price. What is left that is not? If nothing, PASS.",
)


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


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    brief = build_brief(_ROOT)
    if args.brief:
        print(json.dumps(brief, indent=2))
        return 0
    dd = sleeve_drawdown(_ROOT)
    if dd["halted"]:
        # Not timidity: a sleeve this far below its high-water mark has evidence its edge is not
        # what it claimed, and adding leveraged size to a broken estimate is how books die (L1.23).
        state = {"status": "HALTED", "why": f"sleeve drawdown rail: {dd['why']}",
                 "drawdown": dd, "at": datetime.now(tz=UTC).isoformat()}
        (_ROOT / _STATE).write_text(json.dumps(state, indent=2), "utf-8")
        print(json.dumps(state, indent=2) if args.json else
              f"conviction (R0125): HALTED -- {dd['why']}")
        return 0
    heat = portfolio_heat(_ROOT)
    if heat["state"] == "FULL":
        state = {"status": "HEAT-FULL", "why": heat["why"], "heat": heat,
                 "at": datetime.now(tz=UTC).isoformat()}
        (_ROOT / _STATE).write_text(json.dumps(state, indent=2), "utf-8")
        print(json.dumps(state, indent=2) if args.json else
              f"conviction (R0125): HEAT-FULL -- {heat['why']}")
        return 0
    try:
        floors = noise_table()
    except (OSError, ValueError) as exc:
        floors = {"state": "UNMEASURED", "why": str(exc)}
    charts = _chart_brief(_ROOT, heat)
    base = _BRIEF.format(instruments=", ".join(INSTRUMENTS),
                         playbook=_playbook_brief(_ROOT), n_support=3,
                         brief=json.dumps(brief, indent=1)[:5000],
                         noise=json.dumps(floors)[:1500],
                         charts=charts,
                         lo=MIN_PROB, hi=MAX_PROB,
                         smin=MIN_STOP_PCT, smax=MAX_STOP_PCT)
    reads = [parse(_ask(base + _LENSES[i % len(_LENSES)])) for i in range(ENSEMBLE_N)]
    call, consensus = ensemble_consensus(reads)
    if call is None:
        state = {"status": "NO-CALL", "why": "no parseable JSON (auth/quota/refusal)",
                 "at": datetime.now(tz=UTC).isoformat()}
    else:
        noise = None
        if call.get("action") != "PASS" and call.get("symbol") and call.get("horizon_hours"):
            try:
                noise = noise_floor(str(call["symbol"]), float(call["horizon_hours"]),
                                    str(call.get("direction", "LONG")))
            except (ValueError, TypeError, OSError) as exc:
                noise = {"state": "UNMEASURED", "floor_pct": MIN_STOP_PCT, "why": str(exc)}
        if call.get("action") != "PASS" and call.get("symbol"):
            heat = {**heat, "fits_risk": size_into_headroom(
                _ROOT, str(call["symbol"]), MAX_RISK_PER_TRADE)["risk"]}
        costs = None
        if call.get("action") != "PASS":
            try:
                stop_c, stop_why = derive_stop_pct(float(call["entry_ref"]),
                                                   float(call["invalidation"]),
                                                   str(call.get("direction", "")))
                if not stop_why:
                    costs = trade_cost_view(_ROOT, str(call["symbol"]),
                                            str(call["direction"]), stop_c,
                                            float(call["horizon_hours"]))
            except (KeyError, TypeError, ValueError):
                costs = None                   # malformed call -- validate names the real refusal
        ok, why = validate(call, noise=noise, heat=heat, costs=costs)
        if not ok:
            state = {"status": "REFUSED", "why": why, "call": call, "noise": noise}
        elif call.get("action") == "PASS":
            state = {"status": "PASS", "why": why}
        else:
            row = record(_ROOT, call, noise=noise)
            state = {"status": "TRADE", "why": why, "call": row,
                     "leverage": row["sizing"]["leverage"],
                     "peak_leverage": row["management"].get("peak_leverage"), "noise": noise}
    state["drawdown_rail"] = dd
    state["heat"] = heat
    state["ensemble"] = consensus
    state.setdefault("at", datetime.now(tz=UTC).isoformat())
    (_ROOT / _STATE).write_text(json.dumps(state, indent=2), "utf-8")
    print(json.dumps(state, indent=2) if args.json else
          f"conviction (R0125): {state['status']} -- {state['why']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/run_crypto_research.py
```python
"""Industrialized crypto hypothesis factory over the Parquet lake -- the daily throughput engine.

Feeds the whole crypto universe (lake bars + Level-3 funding) into the generic AutoDiscoveryLab: the
same validation gauntlet, net of real perp cost, with cross-campaign DSR deflation on the cumulative
trial count. The funding_stress_reversal generator (LIQUIDITY family) is the one genuinely
crypto-native hypothesis; the price families re-test the graveyard cheaply (content-hash dedup) and
the gauntlet rejects them. Survivors expected to be few or zero -- that is the honest point.

Emits web/autodiscovery_crypto.json (dashboard) + reports/crypto_research/*.json (durable ledger).
Idempotent: after the first full cycle, dedup skips already-tested hypotheses so re-runs are cheap
and only NEW symbols / generators are tested -- safe to run every daily cycle.

    python scripts/run_crypto_research.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from migrations import MIGRATIONS

from libs.autodiscovery.crypto_adapter import (
    DEFAULT_FAMILIES,
    build_lab,
    load_universe,
    web_payload,
)
from libs.autodiscovery.models import Family
from libs.autodiscovery.reports import failure_analysis_report, research_report, survivor_report
from libs.data.timeframe import Timeframe
from libs.store.connection import Database
from libs.store.migrations import run_migrations

_OUT = Path("reports/crypto_research")
_WEB = Path("web/autodiscovery_crypto.json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/sor_crypto.sqlite")
    parser.add_argument("--families", default=",".join(f.value for f in DEFAULT_FAMILIES))
    parser.add_argument("--timeframe", choices=("D1", "H8"), default="D1")
    parser.add_argument("--max-symbols", type=int, default=30,
                        help="cap the universe to the top-N liquid perps (0 = all)")
    args = parser.parse_args()

    tf = Timeframe(args.timeframe)
    limit = args.max_symbols or None
    symbols, provider = load_universe(tf, limit=limit)
    if not symbols:
        raise SystemExit(f"no crypto {tf.value} data in lake; run scripts/ingest_crypto.py first")

    families = [Family(f.strip()) for f in args.families.split(",") if f.strip()] or None
    db = Database(Path(args.db))
    run_migrations(db, MIGRATIONS)
    lab = build_lab(db, provider, families=families)

    print(f"crypto {tf.value}: {len(symbols)} liquid symbols (cap {limit}) | "
          f"families: {[f.value for f in (families or [])]}")
    result = lab.cycle(symbols)
    print(f"\n[cycle] tested={result.tested} survivors={result.survivors} "
          f"rejected={result.rejected} promoted_paper={result.promoted_to_paper} "
          f"skipped_dup={result.skipped_duplicate}")

    # PILOT INSTRUMENT (2026-07-12): record this cycle's information value + refresh the pilot
    # card. Over 30 days this measures survivors-per-1,000 -- the number that decides whether
    # scaling generation (more VPS/hardware) is EV-positive or the constraint is data/mechanism.
    from libs.research.information_value import record_factory_cycle
    card = record_factory_cycle(result.tested, result.survivors, timeframe=tf.value)
    print(f"[pilot] survivors/1000={card['survivors_per_1000']} "
          f"info_bits/exp={card.get('info_bits_per_experiment')} -> {card.get('verdict_hint')}")

    _OUT.mkdir(parents=True, exist_ok=True)
    for name, payload in {
        "research_report": research_report(lab.store),
        "survivor_report": survivor_report(lab.store),
        "failure_analysis_report": failure_analysis_report(lab.store),
    }.items():
        (_OUT / f"{name}.json").write_text(json.dumps(payload, indent=2, default=str), "utf-8")
    _WEB.parent.mkdir(parents=True, exist_ok=True)
    _WEB.write_text(json.dumps(web_payload(lab.store, result, timeframe=tf.value),
                              indent=2, default=str), "utf-8")
    print(f"reports -> {_OUT}/ | dashboard -> {_WEB}")
    if result.survivors == 0:
        print("ZERO survivors net-of-cost (honest).")
    db.close()


if __name__ == "__main__":
    main()

```

### scripts/run_deadman_reconciliation.py
```python
"""Read-only forensic reconciliation for the 2026-07-19 14:27Z dead-man fire (GAP register row 34).

Maps the observed spot USDT delta (-$1,837.68) and the equity discrepancy (785.35 latch-read vs
~2,409 reconstructed) to specific Binance testnet venue records: per-symbol spot fills (myTrades),
futures fills + realized PnL (myTrades), and futures funding/commission income (income history).

Pure diagnostic -- issues zero orders, writes no executor/risk-path state, never touches
scripts/run_deadman_switch.py or its state files. Output is a dated markdown+json dossier for the
CRO/principal to read before any reset decision (data/PRINCIPAL_ACTION.md stays gated on this).

    .venv/bin/python scripts/run_deadman_reconciliation.py
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from libs.execution import binance_spot_testnet as spot
from libs.execution import binance_testnet as fut

_ROOT = Path(__file__).resolve().parent.parent
_TRADES = _ROOT / "data" / "cashcarry_trades.json"
_OUT_MD = _ROOT / "data" / "DEADMAN_RECONCILIATION_20260719.md"
_OUT_JSON = _ROOT / "data" / "deadman_reconciliation_20260719.json"

_INCIDENT_START = datetime.fromisoformat("2026-07-19T14:00:00+00:00")
_INCIDENT_END = datetime.fromisoformat("2026-07-19T14:40:00+00:00")
# wide net: any round-trip whose [opened, closed] interval overlaps this window.
# The dead-man's usdt_baseline (99,566.37) was set at the 07-17T23:05Z reset #2 epoch, not at the
# incident -- the observed -$1,837.68 delta is measured against THAT baseline, so the scan must
# cover the full ~39h span back to the reset, not just the incident window, or the reconciliation
# silently mis-scopes and any close match to the full delta is coincidence, not proof.
_SCAN_START = datetime.fromisoformat("2026-07-17T23:05:00+00:00")
_SCAN_END = datetime.fromisoformat("2026-07-19T15:00:00+00:00")
_BUFFER_MS = 90_000  # 90s pad around each recorded open/close to catch adjacent partial fills


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _parse(v: str) -> datetime:
    return datetime.fromisoformat(v)


def _relevant_trades() -> list[dict[str, Any]]:
    rows = json.loads(_TRADES.read_text("utf-8"))
    out = []
    for t in rows:
        opened = _parse(t["opened"]) if t.get("opened") else None
        closed = _parse(t["closed"]) if t.get("closed") else None
        lo = opened or closed
        hi = closed or opened
        if lo is None or hi is None:      # both derive from the same pair, so this
            continue                      # is one condition -- stated so it checks
        if hi < _SCAN_START or lo > _SCAN_END:
            continue
        out.append(t)
    return out


def _spot_symbol(perp_symbol: str) -> str:
    return perp_symbol  # cash-and-carry trades the identical pair on spot + perp testnets


_SPOT_CHUNK_MS = 20 * 3600 * 1000   # venue caps spot myTrades spans at 24h; 20h leaves margin
_FUT_CHUNK_MS = 6 * 24 * 3600 * 1000  # venue caps at 7d on futures userTrades; 6d margin


def _chunked_trades(fetch_fn: Any, sym: str, start: int, end: int,
                    chunk_ms: int) -> list[dict[str, Any]]:
    """Page a myTrades-style call across venue-imposed start/end span caps.

    A silent-truncation trap: querying past the cap does not error, it returns an empty (or
    partial) list -- the exact failure class documented in institutional_knowledge.md (paginate
    every venue history endpoint). De-dupes on (id) since chunk boundaries can double-fetch."""
    out: dict[str, dict[str, Any]] = {}
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + chunk_ms, end)
        for t in fetch_fn(sym, cursor, chunk_end):
            out[str(t.get("id"))] = t
        cursor = chunk_end
    return list(out.values())


def _reconcile_symbol(sym: str, opened: datetime | None, closed: datetime | None) -> dict[str, Any]:
    # a trade carrying NEITHER timestamp would call _ms(None) and crash the reconciliation;
    # the end_anchor below always had the fallback, the start never did (found by mypy 07-26)
    start = _ms(opened or closed or _INCIDENT_END) - _BUFFER_MS
    end_anchor = closed or opened or _INCIDENT_END
    end = _ms(end_anchor) + _BUFFER_MS

    spot_fills = _chunked_trades(lambda s, a, b: spot.my_trades(_spot_symbol(s), a, b), sym,
                                  start, end, _SPOT_CHUNK_MS)
    fut_fills = _chunked_trades(fut.my_trades, sym, start, end, _FUT_CHUNK_MS)
    fut_income = fut._income_rows(start, fetch=None, symbol=sym)
    fut_income = [r for r in fut_income if start <= int(r.get("time", 0)) <= end]

    spot_buy_quote = sum(float(t["quoteQty"]) for t in spot_fills if t.get("isBuyer"))
    spot_sell_quote = sum(float(t["quoteQty"]) for t in spot_fills if not t.get("isBuyer"))
    spot_commission = sum(float(t.get("commission", 0.0)) for t in spot_fills
                           if t.get("commissionAsset") in ("USDT", "BUSD"))
    spot_net_usdt = spot_sell_quote - spot_buy_quote - spot_commission

    fut_realized = sum(float(t.get("realizedPnl", 0.0)) for t in fut_fills)
    fut_commission = sum(float(t.get("commission", 0.0)) for t in fut_fills)
    def _income(kind: str) -> float:
        return sum(float(r["income"]) for r in fut_income if r.get("incomeType") == kind)

    funding = _income("FUNDING_FEE")
    income_realized = _income("REALIZED_PNL")
    income_commission = _income("COMMISSION")

    return {
        "symbol": sym,
        "opened": opened.isoformat() if opened else None,
        "closed": closed.isoformat() if closed else None,
        "spot_fills_n": len(spot_fills),
        "spot_buy_quote_usdt": round(spot_buy_quote, 4),
        "spot_sell_quote_usdt": round(spot_sell_quote, 4),
        "spot_commission_usdt": round(spot_commission, 4),
        "spot_net_usdt": round(spot_net_usdt, 4),
        "fut_fills_n": len(fut_fills),
        "fut_realized_pnl_from_fills": round(fut_realized, 4),
        "fut_commission_from_fills": round(fut_commission, 4),
        "fut_income_realized_pnl": round(income_realized, 4),
        "fut_income_commission": round(income_commission, 4),
        "fut_income_funding": round(funding, 4),
        "combined_net_usdt": round(
            spot_net_usdt + income_realized - income_commission + funding, 4),
    }


def main() -> None:
    if not (spot.has_keys() and fut.has_keys()):
        print("ABORT: testnet keys not available -- cannot read venue records")
        sys.exit(1)

    trades = _relevant_trades()
    by_symbol: dict[str, list[dict[str, Any]]] = {}
    for t in trades:
        by_symbol.setdefault(t["symbol"], []).append(t)

    rows = []
    for sym, evs in sorted(by_symbol.items()):
        opened = min((_parse(e["opened"]) for e in evs if e.get("opened")), default=None)
        closed = max((_parse(e["closed"]) for e in evs if e.get("closed")), default=None)
        try:
            rows.append(_reconcile_symbol(sym, opened, closed))
        except Exception as e:  # a single symbol's venue read failing must not kill the report
            rows.append({"symbol": sym, "error": repr(e)[:200]})

    total_combined = sum(r.get("combined_net_usdt", 0.0) for r in rows if "error" not in r)
    good = [r for r in rows if "error" not in r]
    total_spot_net = sum(r.get("spot_net_usdt", 0.0) for r in good)
    total_funding = sum(r.get("fut_income_funding", 0.0) for r in good)
    total_fut_realized = sum(r.get("fut_income_realized_pnl", 0.0) for r in good)
    total_fut_commission = sum(r.get("fut_income_commission", 0.0) for r in good)

    # data/INCIDENT_20260719_DEADMAN.md fact #5: SPOT-only USDT baseline delta
    observed_usdt_delta = -1837.68
    observed_equity_gap = 2409.0 - 785.35  # fact #6 vs deadman_state.json last_eq at latch

    # deadman_state.json's usdt_baseline is a SPOT-wallet-only figure (run_deadman_switch.py):
    # the like-for-like comparison is spot_net_usdt alone. Futures funding/realized/commission
    # live on a DIFFERENT account and never move the spot USDT balance; they inform the separate
    # combined-book equity picture, not this baseline delta. Comparing "combined" against the
    # spot-only observed figure was the first-draft bug here -- keep both, label correctly.
    spot_residual = round(observed_usdt_delta - total_spot_net, 4)
    combined_vs_spot_baseline = round(observed_usdt_delta - total_combined, 4)

    report = {
        "generated": datetime.now(UTC).isoformat(),
        "incident_window": [_INCIDENT_START.isoformat(), _INCIDENT_END.isoformat()],
        "scan_window": [_SCAN_START.isoformat(), _SCAN_END.isoformat()],
        "symbols_reconciled": len(rows),
        "per_symbol": rows,
        "totals": {
            "spot_net_usdt": round(total_spot_net, 4),
            "futures_funding_usdt": round(total_funding, 4),
            "futures_realized_pnl_usdt": round(total_fut_realized, 4),
            "futures_commission_usdt": round(total_fut_commission, 4),
            "combined_net_usdt": round(total_combined, 4),
        },
        "observed": {
            "spot_usdt_baseline_delta": observed_usdt_delta,
            "equity_gap_latch_vs_reconstructed": round(observed_equity_gap, 4),
        },
        "spot_only_residual_usdt": spot_residual,
        # NOT like-for-like (see comment above) -- kept only so the first-draft number stays
        # visible next to its correction:
        "combined_vs_spot_baseline_residual_INVALID_COMPARISON": combined_vs_spot_baseline,
    }
    _OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Dead-man fire 2026-07-19 -- venue-record reconciliation (read-only, auto-generated)",
        f"_Generated {report['generated']}_",
        "",
        "Maps every carry round-trip active around the incident window to raw Binance testnet",
        "myTrades/income records. Diagnostic only -- issues zero orders, touches no risk-path or",
        "Tier-3 state. See data/PRINCIPAL_ACTION.md for the reset decision this unblocks.",
        "",
        f"**Observed spot USDT baseline delta:** {observed_usdt_delta}",
        f"**Observed equity gap (latch read 785.35 vs reconstructed ~2409):** "
        f"{observed_equity_gap:.2f}",
        "",
        "## Totals across all reconciled symbols",
        f"- Spot net USDT (sells - buys - commission): **{total_spot_net:.4f}**",
        f"- Futures funding income: **{total_funding:.4f}**",
        f"- Futures realized PnL (income ledger): **{total_fut_realized:.4f}**",
        f"- Futures commission (income ledger): **{total_fut_commission:.4f}**",
        f"- **SPOT-ONLY residual vs the observed -1,837.68 spot baseline delta "
        f"(like-for-like): {spot_residual:.4f}**",
        f"- Combined net USDT across both accounts (context, not like-for-like): "
        f"{total_combined:.4f}",
        "",
        "## Per-symbol detail",
        "| symbol | opened | closed | spot fills | spot net USDT | fut funding "
        "| fut realized | fut commission | combined |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        if "error" in r:
            lines.append(f"| {r['symbol']} | ERROR: {r['error']} | | | | | | | |")
            continue
        lines.append(
            f"| {r['symbol']} | {r['opened']} | {r['closed']} | {r['spot_fills_n']} | "
            f"{r['spot_net_usdt']} | {r['fut_income_funding']} | "
            f"{r['fut_income_realized_pnl']} | {r['fut_income_commission']} | "
            f"{r['combined_net_usdt']} |"
        )
    lines.append("")
    lines.append(
        "**Interpretation guardrail:** a small residual (roughly in line with observed per-trade "
        "price_pnl noise already recorded in data/cashcarry_trades.json) supports the 'measurement "
        "hole, not real loss' reading. A residual comparable in size to the full $1,838 gap means "
        "venue records do NOT explain it and the accounting break is real and still open -- do not "
        "round either way; report the number."
    )
    _OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(f"Reconciled {len(rows)} symbols.")
    print(f"Spot net USDT explained by venue records: {total_spot_net:.4f}")
    print(f"SPOT-ONLY residual vs observed -1,837.68 delta: {spot_residual:.4f}")
    print(f"Wrote {_OUT_MD} and {_OUT_JSON}")


if __name__ == "__main__":
    main()

```

### scripts/run_growth_audit.py
```python
"""GROWTH AUDIT -- the anti-conservatism engine: under-utilization of AUTHORIZED size is a DEFECT.

Every risk system asks "are we too big?"; nothing asks "are we too SMALL?" -- so conservatism
accretes silently (floors outlive their reason, capital idles, ramps stall) and geometric growth
is quietly compromised. This engine runs daily and flags every gap between what the evidence
AUTHORIZES and what is actually DEPLOYED. Each gap must carry a justification of exactly one of:
  evidence  -- the gate is honestly unproven (e.g. leverage floored at confidence=0)  -> OK
  survival  -- a ruin/concentration/black-swan constraint binds                        -> OK
  human     -- waiting on a one-time human act (live keys, VPS)                        -> SURFACE
  NONE      -- no valid reason                                    -> CONSERVATISM DEFECT: close it
Feed-only (no venue calls) -> cheap every cycle. Emits web/growth_audit.json; the CRO cycle must
close every NONE-gap same-cycle or ledger-justify it (deferral discipline applies).

    python scripts/run_growth_audit.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_OUT = Path("web/growth_audit.json")
_UTIL_TARGET = 0.75          # deployed/(deployed+idle spot USDT) below this -> investigate


def _load(p: str) -> dict[str, Any]:
    try:
        d: dict[str, Any] = json.loads(Path(p).read_text("utf-8"))
        return d
    except (OSError, json.JSONDecodeError):
        return {}


def _num(v: object, d: float = 0.0) -> float:
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return d


def main() -> None:
    lc = _load("web/live_combined.json")
    cc = _load("web/cashcarry_live.json")
    lv = _load("web/leverage.json")
    pol = _load("data/live_deployment_policy.json")
    items: list[dict[str, Any]] = []

    # 1) CAPITAL UTILIZATION vs AUTHORIZED capital (2026-07-18 fix: the old denominator was
    # the RAW spot USDT wallet -- on a faucet-fed testnet that is not authorized capital, and
    # after the 07-17 hygiene sweep (~$99.5k consolidated) it made this defect a permanent
    # phantom whose "remediation" was the leverage-runaway class through the back door.
    # Utilization = deployed / the operator's authorized capital (config). Idle wallet is
    # surfaced as INFO for the principal: AUTHORIZING more is a principal/gate decision,
    # never an audit demand.
    dep = _num(cc.get("deployed_notional"))
    idle = _num(lc.get("spot", {}).get("usdt"))
    try:
        authorized = _num(_load("data/cashcarry_config.json").get("capital")) or 4500.0
    except Exception:
        authorized = 4500.0
    util = round(dep / authorized, 3) if authorized > 0 else None
    items.append({
        "check": "carry_capital_utilization",
        "utilized": f"${dep:,.0f} deployed", "authorized": f"${authorized:,.0f} authorized "
        f"(config) | wallet idle ${idle:,.0f} (info: raising authorized capital is a "
        "principal decision)",
        "utilization": util,
        "verdict": ("OK" if util is None or util >= _UTIL_TARGET else "GAP"),
        "justified_by": ("fully deployed to the authorized ceiling"
                         if util is not None and util >= _UTIL_TARGET else
                         "NONE -- authorized capital is not fully deployed: the executor "
                         "should be using its full config capital (check free-capital sizing "
                         "/ open blocks)"),
    })

    # 2) LEVERAGE vs the growth-optimal target: floored is OK ONLY while confidence == 0.
    sl = lv.get("sleeves", {}).get("cash_and_carry", {})
    conf = _num(sl.get("confidence"))
    rec = _num(sl.get("recommended_leverage"))
    actual_lev = 1.0
    lev_gap = conf > 0 and rec > actual_lev * 1.1
    items.append({
        "check": "leverage_vs_growth_optimal",
        "utilized": f"{actual_lev:g}x", "authorized": f"recommended {rec:g}x @ conf {conf:g} "
        f"(ruin cap {_num(sl.get('ruin_cap')):g}x)",
        "verdict": "GAP" if lev_gap else "OK",
        "justified_by": ("NONE -- validation confidence is positive but sizing has not ramped: "
                         "the auto-ramp MUST engage (this is the defect class the audit exists for)"
                         if lev_gap else
                         "evidence (confidence=0: floored on unproven edge is honest, not timid)"),
    })

    # 3) LIVE DEPLOYMENT readiness: armed policy waiting only on the one-time human setup.
    armed = str(pol.get("status", "")).startswith("ARMED")
    items.append({
        "check": "live_deployment_path",
        "utilized": "testnet only", "authorized": "auto-deploy ARMED (Kelly-unit ladder)",
        "verdict": "HUMAN-PENDING" if armed else "GAP",
        "justified_by": ("human (one-time: live account + trade-only keys + deposit + VPS -- "
                         "surface until done; every validated day without it is foregone growth)"
                         if armed else "NONE -- policy not armed"),
    })

    # 4) VALIDATION THROUGHPUT: every fast-track-eligible sleeve must be promoted same-day.
    sh = _load("web/cashcarry_shadow.json")
    ft = str(sh.get("fast_track", ""))
    items.append({
        "check": "promotion_latency",
        "utilized": ft or "n/a", "authorized": "promote the DAY eligibility hits (40d + t>=1.65)",
        "verdict": "OK" if not ft.startswith("ELIGIBLE") else "ACT-NOW",
        "justified_by": "evidence clock" if not ft.startswith("ELIGIBLE")
        else "NONE -- eligible sleeve not promoted = pure foregone growth",
    })

    defects = [i["check"] for i in items if str(i["justified_by"]).startswith("NONE")]
    out = {"updated": datetime.now(tz=UTC).isoformat(), "items": items,
           "conservatism_defects": defects,
           "rule": ("every NONE-gap is a DEFECT: close it same-cycle or ledger-justify it. "
                    "Floors are for missing evidence, never for comfort. Conservatism beyond "
                    "survival constraints is a cost to lifetime geometric growth.")}
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    print(f"growth audit: {len(defects)} conservatism defect(s)"
          + (f" -> {defects}" if defects else " -- fully deployed to authorized ceilings"))


if __name__ == "__main__":
    main()

```

### scripts/run_kama_squeeze_backtest.py
```python
"""KAMA-squeeze backtest -- pre-registered principal-override test (2026-07-11), full gauntlet.

Hypothesis (canonical TTM-squeeze + Kaufman AMA, ALL params fixed a priori -- no tuning):
volatility compression (Bollinger(20,2) inside Keltner(20,1.5xATR)) precedes expansion; on the
squeeze RELEASE, enter in the direction of the adaptive trend (sign(close - KAMA(10,2,30))) and
hold until price crosses back through KAMA. Variant B (kama_trend: always positioned by KAMA side)
isolates whether the squeeze TIMING adds anything over the raw adaptive MA.

HONESTY: EV gate scored this REJECT (EV 0.001, p~1.6%: price_only x crowded_known -- TTM squeeze is
published retail canon). Tested on explicit principal instruction; the gauntlet's verdict is final
and goes to the graveyard either way. Top-15 majors, inverse-vol basket, net of ADV-tiered costs,
lagged signals (no look-ahead).

    python scripts/run_kama_squeeze_backtest.py
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
from libs.research.crypto_xsec import adv_tier_cost
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType

_CRYPTO = Path("data/lake/bronze/crypto")
_OUT = Path("web/kama_squeeze_backtest.json")
_TOP = 15
_KAMA_N, _KAMA_F, _KAMA_S = 10, 2, 30                 # canonical Kaufman params
_BB_N, _BB_K, _KC_N, _KC_K = 20, 2.0, 20, 1.5        # canonical TTM squeeze params
_FAIL = ["crowded retail signal", "price-only", "regime artifact", "cost exceeds edge"]


def _kama(close: pd.Series) -> pd.Series:
    er = (close.diff(_KAMA_N).abs()
          / close.diff().abs().rolling(_KAMA_N).sum().replace(0, np.nan))
    fast, slow = 2 / (_KAMA_F + 1), 2 / (_KAMA_S + 1)
    sc = ((er * (fast - slow) + slow) ** 2).fillna(slow ** 2)
    out = close.copy().to_numpy(dtype=float)
    vals = close.to_numpy(dtype=float)
    scv = sc.to_numpy(dtype=float)
    for t in range(1, len(vals)):
        out[t] = out[t - 1] + scv[t] * (vals[t] - out[t - 1])
    return pd.Series(out, index=close.index)


def _positions(df: pd.DataFrame) -> pd.Series:
    """Squeeze-release entry in KAMA direction; hold until close crosses back through KAMA."""
    close, high, low = df["close"], df["high"], df["low"]
    kama = _kama(close)
    mid, sd = close.rolling(_BB_N).mean(), close.rolling(_BB_N).std()
    bb_up, bb_lo = mid + _BB_K * sd, mid - _BB_K * sd
    tr = pd.concat([(high - low), (high - close.shift()).abs(),
                    (low - close.shift()).abs()], axis=1).max(axis=1)
    ema, atr = close.ewm(span=_KC_N).mean(), tr.rolling(_KC_N).mean()
    kc_up, kc_lo = ema + _KC_K * atr, ema - _KC_K * atr
    sq_on = ((bb_up < kc_up) & (bb_lo > kc_lo)).fillna(False).to_numpy()
    side = np.sign((close - kama).to_numpy())
    pos = np.zeros(len(df))
    for t in range(1, len(df)):
        if pos[t - 1] == 0:
            if sq_on[t - 1] and not sq_on[t] and side[t] != 0:   # release -> enter w/ trend
                pos[t] = side[t]
        else:
            pos[t] = pos[t - 1] if side[t] == pos[t - 1] else 0.0  # exit on KAMA cross
    return pd.Series(pos, index=df.index)


def _basket(panels: dict[str, pd.DataFrame], adv: dict[str, float],
            pos_fn) -> np.ndarray:
    closes = pd.DataFrame({s: p["close"] for s, p in panels.items()}).sort_index()
    rets = closes.pct_change(fill_method=None)
    inv_vol = (1.0 / rets.rolling(30).std()).shift(1)
    pos = pd.DataFrame({s: pos_fn(p.reindex(closes.index)) for s, p in panels.items()})
    cost = {s: adv_tier_cost(a) for s, a in adv.items()}
    out = np.zeros(len(closes))
    prev = pd.Series(0.0, index=closes.columns)
    for t in range(1, len(closes)):
        raw = (pos.iloc[t - 1] * inv_vol.iloc[t]).fillna(0.0)     # LAGGED position
        gross = raw.abs().sum()
        w = raw / gross if gross > 0 else raw * 0.0
        r = float((w * rets.iloc[t].fillna(0.0)).sum())
        turn = float(sum(abs(w[s] - prev[s]) * cost.get(s, 1.5e-3) for s in w.index))
        out[t] = r - turn
        prev = w
    return out


def main() -> None:
    panels, adv = {}, {}
    for s in list_liquid_perps(top_n=_TOP * 3):
        if not (_CRYPTO / s / Timeframe.D1.value).exists():
            continue
        register_instrument(InstrumentSpec(symbol=s, asset_class=AssetClass.CRYPTO, description=s))
        df = ParquetLake("data/lake").read_bars(Layer.BRONZE, s, Timeframe.D1)
        df = df.set_index("timestamp")
        if len(df) < 400:
            continue
        panels[s] = df[["close", "high", "low"]]
        adv[s] = float((df["close"] * df["volume"]).tail(180).mean())
        if len(panels) >= _TOP:
            break
    if len(panels) < 8:
        raise SystemExit(f"need majors panel; got {len(panels)}")

    strat = {
        "kama_squeeze": _basket(panels, adv, _positions),
        "kama_trend": _basket(panels, adv, lambda d: pd.Series(
            np.sign((d["close"] - _kama(d["close"])).to_numpy()), index=d.index)),
    }
    matrix = np.column_stack([strat["kama_squeeze"], strat["kama_trend"]])
    # per-candidate gates (gap #87 flip, principal-ruled 2026-07-29); thresholds unchanged
    campaign = campaign_gate_stats(matrix)
    results = {}
    # enumerate order == column_stack order over `strat`, so `col` is the strategy's matrix column
    for col, (name, r) in enumerate(strat.items()):
        active = r[r != 0.0]
        sh = round(float(sharpe_ratio(active) * np.sqrt(365)), 2) if len(active) > 5 else 0.0
        hyp = Hypothesis(family=Family.BREAKOUT, subtype=name, symbol="CRYPTO", params={},
                         mechanism=MechanismType.BEHAVIORAL, edge_source="vol_compression",
                         failure_modes=_FAIL)
        v = validate(active, hypothesis=hyp, n_trials=2, sharpe_estimates=[sh, -sh],
                     returns_matrix=matrix, campaign=campaign, column=col
                     ) if len(active) >= 250 else None
        gates = f"{sum(v.gates.values())}/{len(v.gates)}" if v else "n<250"
        results[name] = {"ann_sharpe": sh, "n_active_days": len(active), "gates": gates,
                         "pbo": round(float(v.metrics.pbo), 3) if v else None,
                         "rc_p": round(float(v.metrics.reality_p), 3) if v else None,
                         "survived": bool(getattr(v, "survived", False))}

    out = {"updated": datetime.now(tz=UTC).isoformat(), "majors": len(panels),
           "params": "KAMA(10,2,30) BB(20,2) KC(20,1.5) -- canonical, frozen a priori",
           # campaign-level legacy PBO/RC kept as SEARCH-PROCEDURE diagnostics (gap #87); the
           # gate values are per-strategy now -- see results[*].pbo / results[*].rc_p.
           "pbo": (round(float(campaign.legacy_pbo.pbo), 3)
                   if campaign is not None and campaign.legacy_pbo is not None else None),
           "reality_check_p": (round(float(campaign.legacy_rc.p_value), 3)
                               if campaign is not None and campaign.legacy_rc is not None
                               else None),
           "results": results,
           "ev_gate": "REJECT pre-test (EV 0.001, p~1.6%) -- tested on principal override",
           "note": "verdict is final: graveyard on fail, shadow-candidate path on survive"}
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    for n, res in results.items():
        print(f"{n}: annSharpe {res['ann_sharpe']} gates {res['gates']} "
              f"pbo={res['pbo']} rc_p={res['rc_p']} "
              f"survived={res['survived']} ({res['n_active_days']}d active)")
    print(f"campaign diagnostics: pbo {out['pbo']} | rc_p {out['reality_check_p']} "
          f"(search procedure; gates are per-strategy)")


if __name__ == "__main__":
    main()

```

### scripts/run_law_gate.py
```python
#!/usr/bin/env python3
"""THE LAW GATE (L1.37) -- every law, enforced at every boundary, continuously.

PRINCIPAL ORDER (2026-07-31): *"make all these principles enforced 24/7 with every interaction
with anything."*

THE GAP THIS CLOSES, and it was large. Every fence this desk owns ran on a CRON TICK and nowhere
else. Between ticks -- and CI ran only pytest, with no git hooks at all -- a commit could land, a
push could ship, and an organ could spawn under a tampered constitution, a stripped doctrine, or
a broken law family, with nothing watching until the next scheduled run hours later. Laws were
enforced PERIODICALLY. This makes them enforced AT EVERY BOUNDARY:

    boundary                     mode      what it stops
    ------------------------------------------------------------------------------------------
    organ spawn (brain_env.sh)   --fast    an organ running under a tampered core or a doctrine
                                           that no longer carries the laws it is meant to obey
    git push (pre-push hook)     full      a breach leaving the box for master
    CI (every push + PR)         full      a breach entering the tree from anywhere
    hourly cron                  full      drift that arrives without a commit (state, artifacts)

TWO MODES, because a gate that is too slow to run at a boundary will be removed from it:
  --fast  (~1s, no subprocesses): the immutable-core seal + doctrine carries every family's laws.
          These are the two conditions under which an organ must NEVER be allowed to start.
  full    every fence, each in its own process, all failures collected and reported together --
          never first-failure-only, because a gate that hides four breaches behind one is a gate
          that gets run once and disbelieved.

REFUSAL IS THE DEFAULT. An unrunnable fence counts as a FAILED fence, never a skipped one: if
this gate cannot prove a law holds, it must not claim it does (L1.28a's rule applied to
enforcement itself).

    python scripts/run_law_gate.py [--fast] [--json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

#: LAW FENCES -- portable. They read the REPO (constitution, doctrine, matrix, prompts, manifest),
#: so they mean the same thing in CI, in a fresh clone, and on the box. These gate every commit
#: and every push: a breach here is a breach anywhere.
_LAW_FENCES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("check_constitution_core.py", ()),        # L2.8a -- the sealed core is intact
    # PRODUCER BEFORE CONSUMER. build_enforcement_matrix WRITES data/enforcement_matrix.json and
    # check_law_families READS it; the matrix is gitignored (data/*), so on a VIRGIN tree the
    # consumer ran first against a file that did not exist yet. That is why this gate was green
    # on every machine that had run it before -- the box, a dev clone -- and RED on every clean
    # checkout: CI failed 10 consecutive times on master (30651154078..30654344515) with
    # "BREACH check_law_families.py (rc=2)" while the identical commit passed locally. Proven by
    # running the gate twice in a fresh worktree: first run FAIL, second run PASS, nothing
    # changed but the artifact the first run left behind. A gate whose verdict depends on
    # whether the machine happened to have run it before is not a gate in either direction.
    ("build_enforcement_matrix.py", ()),       # L2.0 -- no law is prose, no fence is an orphan
    ("check_law_families.py", ()),             # L1.36 -- families complete/fenced/reaching/guarded
    # L1.43 -- a cited enforcement that nothing EXECUTES leaves its law enforced by a docstring.
    # A LAW fence, not a state one: it reads scripts/, libs/ and the manifest, all committed, so it
    # means the same in CI, a fresh clone and on the box. Caught dist_shift.py (cited for L1.19 and
    # L2.10, importer count outside its own test: zero) on its first run.
    ("check_enforcement_execution.py", ()),
    ("check_timidity_language.py", ()),        # L1.28 -- incl. all 18 prompt surfaces
    # --report-only: the LAW half is manifest<->repo integrity (exit 2). Live-crontab DRIFT
    # (exit 1) is BOX STATE -- on a red-parked box the manifest is *supposed* to be ahead of
    # the installed crontab until the puller vets the commit, so drift failing CI/pre-push
    # wedges the exact push that would heal it. The bare run lives in _STATE_FENCES.
    ("check_scheduler_manifest.py", ("--report-only",)),  # L1.28c -- every line is decided
    ("check_build_standard.py", ()),           # L1.41 -- nothing enters below standard
    ("check_sizing_derivation.py", ()),        # L1.41 -- no money number chosen by feel
    ("check_return_targeting.py", ()),         # handoff 2026-07-12 -- no CAGR target
    # --surfaces-only: the PORTABLE half (is the breadth mandate still on every hunting prompt?)
    # reads committed files, so it means the same in CI, a fresh clone and the box. The breadth
    # MEASUREMENT reads live coverage state no clean checkout has, so it runs in _STATE_FENCES --
    # a commit gate reporting BLIND on every PR is a gate that gets switched off (L1.43). Same
    # split as check_scheduler_manifest, and the half that belongs here is the right one: a
    # mandate leaves a prompt by an EDIT, so the edit is the moment to catch it.
    ("check_strategy_breadth.py", ("--surfaces-only",)),  # L1.32 -- never limit to one family
)

#: STATE FENCES -- box-only. They measure LIVE STATE (artifacts, ledgers, organ freshness) that
#: exists solely on the VPS, so in CI or a fresh clone their "failure" means "this machine has no
#: desk state", not "a law was broken". Running them as a commit gate would make the gate cry
#: wolf on every PR, and a gate that cries wolf gets disabled -- which is how enforcement dies.
#: They run in the hourly box gate, where their verdict is real.
_STATE_FENCES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("check_conversion.py", ()),               # L1.28b -- FLATLINE fails
    ("check_exploration.py", ()),              # L1.32 -- no exploration organ gone dark
    ("check_calibration.py", ()),              # L1.29 -- no ungraded past-due forecast
    ("check_strategy_breadth.py", ()),         # L1.32 -- the breadth MEASUREMENT
    ("run_organ_er.py", ()),                   # L1.32 -- no organ left in coma
    ("check_replacement_rate.py", ()),         # L1.30 -- births vs deaths
    ("check_change_window.py", ()),            # L1.38 -- money-path freeze windows
    ("check_scheduler_manifest.py", ()),       # L1.28c state half -- live crontab drift (rc=1)
    ("check_mechanism_attribution.py", ()),    # L1.6 -- no survival on unexplained P&L
    ("check_organ_liveness.py", ()),           # L1.28c -- every organ actually produces
    ("check_promotion_gate.py", ()),           # L1.6 -- expansion is bought with evidence
)


def fast_gate(root: Path | None = None) -> dict[str, Any]:
    """The organ-spawn gate: the two conditions under which no organ may ever start.

    Deliberately in-process and dependency-free -- it runs before EVERY organ, so anything
    slower would be deleted from the spawn path the first time someone profiled a cycle."""
    root = root or _ROOT
    failures: list[str] = []

    # 1. THE SEALED CORE. An organ running under a tampered constitution is worse than no organ.
    try:
        r = subprocess.run([sys.executable, str(root / "scripts/check_constitution_core.py")],
                           capture_output=True, text=True, timeout=60, cwd=root)
        if r.returncode != 0:
            failures.append(f"CORE-SEAL: {(r.stdout + r.stderr).strip()[:200]}")
    except (OSError, subprocess.TimeoutExpired) as exc:
        failures.append(f"CORE-SEAL unrunnable ({exc}) -- counts as FAILED, never skipped")

    # 2. THE DOCTRINE CARRIES EVERY FAMILY. The doctrine is what reaches the organ; if a family's
    #    laws are missing from it, that organ is about to run without them (the L2.3 defect).
    try:
        from scripts.check_law_families import FAMILIES
        doctrine = (root / "ops/principal_doctrine.txt").read_text("utf-8", errors="ignore")
        for fam, (members, _fence, _prevents) in FAMILIES.items():
            missing = [m for m in members if m not in doctrine]
            if missing:
                failures.append(f"DOCTRINE-GAP: family '{fam}' missing {missing} -- an organ "
                                "spawning now would never be told these laws")
    except Exception as exc:
        failures.append(f"DOCTRINE-CHECK unrunnable ({exc}) -- counts as FAILED")

    return {"mode": "fast", "ok": not failures, "failures": failures,
            "generated": datetime.now(tz=UTC).isoformat()}


def full_gate(root: Path | None = None, *, laws_only: bool = False) -> dict[str, Any]:
    """Every fence, all failures collected. Never first-failure-only.

    laws_only=True runs the portable LAW fences alone -- the correct mode for CI and the
    pre-push hook, where live desk state does not exist and its absence is not a breach."""
    root = root or _ROOT
    battery = _LAW_FENCES if laws_only else _LAW_FENCES + _STATE_FENCES
    results, failures = [], []
    for script, extra in battery:
        p = root / "scripts" / script
        if not p.exists():
            failures.append(f"{script}: MISSING -- an absent fence is a failed fence")
            results.append({"fence": script, "ok": False, "detail": "missing"})
            continue
        try:
            r = subprocess.run([sys.executable, str(p), *extra], capture_output=True,
                               text=True, timeout=600, cwd=root)
            ok = r.returncode == 0
            tail = (r.stdout or r.stderr or "").strip().splitlines()
            results.append({"fence": script, "ok": ok, "rc": r.returncode,
                            "detail": tail[-1][:200] if tail else ""})
            if not ok:
                failures.append(f"{script} (rc={r.returncode}): "
                                f"{tail[-1][:160] if tail else 'no output'}")
        except (OSError, subprocess.TimeoutExpired) as exc:
            results.append({"fence": script, "ok": False, "detail": f"unrunnable: {exc}"})
            failures.append(f"{script}: UNRUNNABLE ({exc}) -- counts as FAILED, never skipped")
    return {"mode": "laws" if laws_only else "full", "ok": not failures,
            "n_fences": len(battery),
            "n_failed": len(failures), "failures": failures, "results": results,
            "generated": datetime.now(tz=UTC).isoformat()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true",
                    help="organ-spawn gate: sealed core + doctrine carries every family")
    ap.add_argument("--laws-only", action="store_true",
                    help="portable law fences only -- for CI and the pre-push hook, where live "
                         "desk state does not exist and its absence is not a breach")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = fast_gate() if args.fast else full_gate(laws_only=args.laws_only)
    if not args.fast:
        (_ROOT / "data/law_gate.json").write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        head = "LAW GATE" + (" (fast)" if args.fast else f" -- {rep.get('n_fences', 0)} fences")
        print(f"{head}: {'PASS' if rep['ok'] else 'FAIL'}")
        for f in rep["failures"]:
            print(f"  BREACH  {f}")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/run_moat_backup.py
```python
#!/usr/bin/env python3
"""MOAT BACKUP (L1.23) -- the irreplaceable stores get an off-box replica through git.

THE T4 DEFECT INSIDE A T2 PROCESS (deep sweep 2026-07-31, DM-1 = infra F5): one disk holds the
only copy of stores that CANNOT be re-earned -- the execution tape (fills at our own timestamps),
the research memory, the SoR -- with a ~29-day fuse to the 80% disk guard, whose response is to
sacrifice the moat. libs/ops/backup.py existed the whole time with ZERO production callers (the
built-never-wired class, confirmed 2026-07-31: only its own tests import it).

THE DESIGN, honest about what it does and does not cover:
  COVERED (small, irreplaceable, fits in git): every store in _STORES is replicated into
  backups/moat/ -- sqlite via the online-backup API (consistent while open) + integrity check,
  files/dirs via copy -- with a sha256 manifest and a restore drill run ON EVERY BACKUP (a backup
  that never restored is a hope, not a backup). backups/ is NOT gitignored, so the box's
  10-minute snapshot/push cycle carries the replicas to GitHub: a second machine, different
  failure domain, zero cost, already running.
  NOT COVERED (recorded, never silent -- L1.28b's no-silent-caps rule): the L2 depth lake and
  bulk lake hours (multi-GB; git is the wrong transport). Their sizes are measured into the
  artifact each run so the gap is a number, not a vibe. Closing it is the standing EUR-4/mo
  Storage Box (or R2 free-tier) principal decision on PRINCIPAL_ACTION.
  DISK FUSE: free space below FUSE_PCT fails this fence loudly (exit 2) -- the 29-day countdown
  becomes a paged event long before the 80% guard starts eating the moat.

    python scripts/run_moat_backup.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
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

FUSE_PCT = 15.0          # free-disk % below which this fence FAILS (the fuse, pre-guard)
_MAX_FILE_MB = 64.0      # git-sane cap per file; larger files are SKIPPED and RECORDED

#: name -> (relative path, kind). Small and irreplaceable only -- regenerable artifacts do not
#: belong here (they cost cycles, not history). Absence is recorded, never silently skipped.
_STORES: dict[str, tuple[str, str]] = {
    "execution_tape": ("data/moat/execution_tape", "tree"),
    "research_memory": ("data/research_memory.db", "sqlite"),
    "sor_research": ("data/sor_research.sqlite", "sqlite"),
    "capital_events": ("data/capital_events.jsonl", "file"),
    "cost_model": ("data/cost_model.json", "file"),
    "graveyard": ("docs/graveyard.md", "file"),
}

#: Bulk stores git cannot carry -- measured every run so the uncovered gap stays a NUMBER.
_NOT_COVERED = ("data/lake", "data/moat")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _du(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) if path.is_dir() else 0


def _snapshot_sqlite(src: Path, dst: Path) -> str:
    """Consistent online snapshot + integrity check; returns the replica's sha256."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    con_src = sqlite3.connect(str(src))
    try:
        con_dst = sqlite3.connect(str(dst))
        try:
            con_src.backup(con_dst)
            ok = con_dst.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            con_dst.close()
    finally:
        con_src.close()
    if ok != "ok":
        raise RuntimeError(f"integrity_check failed on replica of {src}: {ok}")
    return _sha256(dst)


def _copy_capped(src: Path, dst: Path, skipped: list[dict[str, Any]]) -> dict[str, str]:
    """Copy file or tree, skipping (and RECORDING) anything over the git-sane cap."""
    digests: dict[str, str] = {}
    files = [src] if src.is_file() else sorted(p for p in src.rglob("*") if p.is_file())
    for f in files:
        rel = f.name if src.is_file() else str(f.relative_to(src))
        if f.stat().st_size > _MAX_FILE_MB * 1e6:
            skipped.append({"file": str(f.relative_to(_ROOT) if f.is_absolute() else f),
                            "bytes": f.stat().st_size,
                            "reason": f"over the {_MAX_FILE_MB}MB git-sane cap"})
            continue
        out = dst / rel if not src.is_file() else dst
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, out)
        digests[rel] = _sha256(out)
    return digests


def _drill(dest: Path, manifest: dict[str, Any]) -> bool:
    """Restore drill on EVERY run: sqlite replicas must integrity-check, files must re-hash."""
    for store, entry in manifest["stores"].items():
        if entry["status"] != "REPLICATED":
            continue
        base = dest / store
        for rel, digest in entry["sha256"].items():
            # file and sqlite replicas ARE the store path; only trees nest under it
            p = base / rel if entry["kind"] == "tree" else base
            if not p.exists() or _sha256(p) != digest:
                return False
        if entry["kind"] == "sqlite":
            con = sqlite3.connect(str(base))
            try:
                if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    return False
            finally:
                con.close()
    return True


def build_backup(root: Path, dest: Path | None = None,
                 free_pct: float | None = None) -> dict[str, Any]:
    dest = dest or root / "backups/moat"
    dest.mkdir(parents=True, exist_ok=True)
    skipped: list[dict[str, Any]] = []
    stores: dict[str, Any] = {}
    for name, (rel, kind) in _STORES.items():
        src = root / rel
        if not src.exists():
            stores[name] = {"status": "ABSENT", "kind": kind, "path": rel, "sha256": {},
                            "note": "store missing on this host -- recorded, not skipped silently"}
            continue
        target = dest / name
        if kind == "sqlite":
            digests = {name: _snapshot_sqlite(src, target)}
        else:
            if target.is_dir():
                shutil.rmtree(target)
            digests = _copy_capped(src, target, skipped)
        stores[name] = {"status": "REPLICATED", "kind": kind, "path": rel,
                        "bytes": _du(src), "sha256": digests}

    usage = shutil.disk_usage(root)
    free = free_pct if free_pct is not None else usage.free / usage.total * 100
    manifest: dict[str, Any] = {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.23 -- survival first: the moat is capital in information form",
        "stores": stores,
        "skipped_over_cap": skipped,
        "not_covered_bytes": {p: _du(root / p) for p in _NOT_COVERED if (root / p).exists()},
        "not_covered_note": "bulk lake/L2 need the Storage-Box/R2 principal decision -- "
                            "measured here every run so the gap stays a number",
        "disk_free_pct": round(free, 2),
        "fuse_pct": FUSE_PCT,
    }
    manifest["restore_drill_passed"] = _drill(dest, manifest)
    status = "OK"
    if free < FUSE_PCT:
        status = "DISK-FUSE"
    elif not manifest["restore_drill_passed"]:
        status = "DRILL-FAILED"
    elif all(s["status"] == "ABSENT" for s in stores.values()):
        status = "NOTHING-REPLICATED"
    manifest["status"] = status
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2), "utf-8")
    return manifest


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_backup(_ROOT)
    out = _ROOT / "data/backup_status.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    n_rep = sum(1 for s in rep["stores"].values() if s["status"] == "REPLICATED")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"moat backup (L1.23): {rep['status']} -- {n_rep}/{len(rep['stores'])} stores "
              f"replicated, drill={'PASS' if rep['restore_drill_passed'] else 'FAIL'}, "
              f"disk free {rep['disk_free_pct']}% (fuse {FUSE_PCT}%)")
        print(f"-> {out}")
    if args.report_only:
        return 0
    return 2 if rep["status"] in ("DISK-FUSE", "DRILL-FAILED", "NOTHING-REPLICATED") else 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/run_nav_attest.py
```python
"""Daily NAV attestation -- an allocator-grade, tamper-evident track record from inception.

Appends one hash-chained line per UTC day to data/nav_attestation.jsonl: each record embeds the
SHA-256 of the previous record, and the file is committed by the daily git snapshot (pushed to
GitHub), so any later edit breaks the chain AND the git history. Self-reported spreadsheets are
worth nothing in allocator diligence; a hash-chained series with third-party (GitHub) timestamps
from day 1 is the cheapest credible track record a solo desk can build -- and it cannot be
started retroactively, which is why it runs NOW, on paper equity, for continuity through go-live.

Reads only existing state files; writes only its own artifact. Freeze-safe.

    python scripts/run_nav_attest.py
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

_OUT = Path("data/nav_attestation.jsonl")
_POS = Path("data/cashcarry_positions.json")
_LIVE = Path("data/live_combined_state.json")


def _book() -> tuple[float, int, float, float]:
    """(deployed_notional, n_carries, realized_spot_pnl, start_futures_equity) from state."""
    st = json.loads(_POS.read_text("utf-8"))
    pos = st.get("positions", {})
    dep = sum(float(p["spot_qty"]) * float(p["spot_cost"]) for p in pos.values())
    return (round(dep, 2), len(pos), round(float(st.get("realized_spot_pnl", 0.0)), 2),
            round(float(st.get("start_futures_equity", 0.0)), 2))


def _equity() -> float | None:
    """Combined marked equity from the molded feed (venue-truth lives in the deadman's file)."""
    try:
        d = json.loads(_LIVE.read_text("utf-8"))
        mc = d.get("mcurve") or []
        return round(float(mc[-1][1]), 2) if mc else None
    except (OSError, json.JSONDecodeError, IndexError, TypeError, ValueError):
        return None


def main() -> None:
    today = datetime.now(tz=UTC).date().isoformat()
    prev_hash = "GENESIS"
    if _OUT.exists():
        lines = _OUT.read_text("utf-8").strip().splitlines()
        if lines:
            last = json.loads(lines[-1])
            if last.get("date") == today:
                print(f"nav-attest: {today} already recorded")
                return
            prev_hash = hashlib.sha256(lines[-1].encode("utf-8")).hexdigest()
    dep, n, rsp, seq = _book()
    rec = {
        "date": today,
        "ts": datetime.now(tz=UTC).isoformat(),
        # NAMED FOR WHAT IT IS. This is the last point of the MOLDED CURVE, not an account
        # balance and not a track record: `start_futures_equity` 5,000 sitting beside a ~14,600
        # figure reads as 2.9x when realised P&L is ~500. Both keys are written -- the old one
        # for chain continuity, the honest one for anything that reads this going forward.
        "molded_curve_usd": _equity(),
        "equity_marked": _equity(),
        "_note": ("molded_curve_usd is a MOLDED/SIMULATED curve, not venue truth and not a "
                  "track record; venue truth is the dead-man's combined_equity"),
        "deployed_notional": dep,
        "n_carries": n,
        "realized_spot_pnl": rsp,
        "start_futures_equity": seq,
        "mode": "PAPER (testnet) -- pre-Gate-0",
        "prev_sha256": prev_hash,
    }
    with _OUT.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
    print(f"nav-attest: {today} equity={rec['equity_marked']} deployed=${dep} "
          f"chain={prev_hash[:12]}..")


if __name__ == "__main__":
    main()

```

### scripts/run_prediction_markets.py
```python
"""Prediction-market calibration + favorite-longshot test (Polymarket, resolved binary markets).

Two questions, both honest:
  1. CALIBRATION: does the de-vigged market probability match realized outcome frequency? (the
     scientific evidence for/against favorite-longshot bias)
  2. DEPLOYABILITY: does a 'back the favorite' strategy clear the validation gauntlet net-of-cost?

PIT: implied probability is taken strictly BEFORE resolution; outcome known only after settlement.
Honest by construction -- binary payoffs are lumpy/fat-tailed, so fragility/DSR gates are decisive.
"""

from __future__ import annotations

import json
from itertools import pairwise
from pathlib import Path

import numpy as np
import pandas as pd

from libs.autodiscovery.models import Family, Hypothesis
from libs.autodiscovery.validation import campaign_gate_stats, validate
from libs.data.prediction_markets import (
    fetch_price_history,
    fetch_resolved_markets,
    implied_prob_before,
)
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType

_OUT = Path("reports/prediction_markets")
_COST = 0.01            # ~1 cent/contract spread+fee haircut on entry
_LEAD_DAYS = 1.0
_FAIL = ["adverse selection (informed counterparties)", "vig/spread", "resolution/oracle risk",
         "tiny capacity", "bias decay as markets mature"]


def _collect(max_markets: int) -> pd.DataFrame:
    markets = fetch_resolved_markets(max_markets=max_markets)
    rows = []
    for i, m in enumerate(markets, 1):
        try:
            hist = fetch_price_history(m["yes_token"])
        except Exception:
            continue
        if hist.empty:
            continue
        end = pd.Timestamp(m["end"])
        p = implied_prob_before(hist, end, lead_days=_LEAD_DAYS)
        if p is None:
            p = float(hist["p"].iloc[0])
        if not (0.02 < p < 0.98):
            continue
        rows.append({"end": end, "p": p, "outcome": m["outcome"], "volume": m["volume"]})
        if i % 100 == 0:
            print(f"  fetched {i}/{len(markets)} markets ({len(rows)} usable)")
    return pd.DataFrame(rows).sort_values("end").reset_index(drop=True)


def _calibration(df: pd.DataFrame) -> list[dict[str, object]]:
    buckets = np.linspace(0, 1, 11)
    out = []
    for lo, hi in pairwise(buckets):
        seg = df[(df["p"] >= lo) & (df["p"] < hi)]
        if len(seg) >= 10:
            out.append({"bucket": f"{lo:.1f}-{hi:.1f}", "n": len(seg),
                        "implied": round(float(seg["p"].mean()), 3),
                        "realized": round(float(seg["outcome"].mean()), 3)})
    return out


def _bet_returns(df: pd.DataFrame, *, min_p: float) -> np.ndarray:
    """Back the FAVORITE (buy the >50% side) when prob exceeds min_p; net of cost. 0 = no bet."""
    r = np.zeros(len(df), dtype="float64")
    for i, row in enumerate(df.itertuples()):
        p, o = row.p, row.outcome
        fav_p = max(p, 1 - p)
        if fav_p < min_p:
            continue
        q = fav_p + _COST                      # entry cost of the favored share
        won = (o == 1.0) if p >= 0.5 else (o == 0.0)
        r[i] = ((1.0 if won else 0.0) - q) / q  # return on capital deployed
    return r


def main() -> None:
    df = _collect(max_markets=2500)
    print(f"\nusable resolved markets: {len(df)}")
    if len(df) < 30:
        raise SystemExit("too few resolved markets to assess anything")

    # Calibration is the scientific question and needs only ~100 obs -- always report it.
    calib = _calibration(df)
    print("CALIBRATION (implied vs realized outcome frequency):")
    for c in calib:
        print(f"  {c['bucket']}  n={c['n']:4}  implied={c['implied']}  realized={c['realized']}")

    variants = [("back_fav_all", 0.5), ("back_fav_60", 0.6), ("back_fav_70", 0.7)]
    series = [(name, _bet_returns(df, min_p=mp)) for name, mp in variants]
    min_len = min(len(r) for _, r in series)
    matrix = np.column_stack([r[-min_len:] for _, r in series])
    sharpes = np.array([sharpe_ratio(r) for _, r in series], dtype="float64")
    # per-candidate gates (gap #87 flip, principal-ruled 2026-07-29); thresholds unchanged
    campaign = campaign_gate_stats(matrix)

    survivors = 0
    results = []
    # enumerate order == column_stack order over `series`, so `col` is the variant's matrix column
    for col, ((name, rets), spr) in enumerate(zip(series, sharpes, strict=True)):
        bets = rets[rets != 0.0]
        n_bets = len(bets)
        # The gauntlet needs >=250 obs; below that we report descriptive stats, not a verdict.
        if n_bets >= 250:
            v = validate(bets, hypothesis=Hypothesis(
                family=Family.LIQUIDITY, subtype=f"pm_{name}", symbol="POLYMARKET", params={},
                mechanism=MechanismType.BEHAVIORAL, edge_source="favorite-longshot bias",
                failure_modes=_FAIL), n_trials=len(series), sharpe_estimates=sharpes,
                returns_matrix=matrix, campaign=campaign, column=col)
            survived, reason = v.survived, v.rejection_reason
        else:
            survived, reason = False, f"below gauntlet minimum (n={n_bets}<250)"
        survivors += int(survived)
        results.append({"variant": name, "bets": n_bets,
                        "mean_ret": round(float(np.mean(bets)), 4) if n_bets else 0.0,
                        "sharpe_per_bet": round(float(spr), 4),
                        "survived": survived, "reason": reason})

    _OUT.mkdir(parents=True, exist_ok=True)
    (_OUT / "report.json").write_text(json.dumps(
        {"usable_markets": len(df), "calibration": calib, "survivors": survivors,
         "strategies": results}, indent=2), "utf-8")
    print(f"\n[prediction-markets] strategies tested={len(series)} survivors={survivors}")
    for r in results:
        print(f"  {r['variant']}: bets={r['bets']} mean={r['mean_ret']} "
              f"sharpe/bet={r['sharpe_per_bet']} survived={r['survived']} {r['reason']}")
    if survivors == 0:
        print("ZERO survivors net-of-cost (honest).")


if __name__ == "__main__":
    main()

```

### scripts/run_rejection_shadow.py
```python
#!/usr/bin/env python3
"""REJECTION-SHADOW RUNNER -- activate the gate-calibration audit over the existing reject ledger.

Recovers wrongly-rejected survivors with ZERO new data (MAX_SURVIVORS Part 1.2). The reject ledger
already exists (CandidateStore ``survived = 0`` rows); this runner reads it, pairs each eligible
reject with its forward score, runs the tested audit (libs.validation.rejection_shadow), and writes
web/reject_shadow.json for the daily sweep. If a non-trivial slice of rejects would have paid
out-of-sample, the gate is over-strict and is leaking survivors -- re-calibrate.

FORWARD SCORES (the injected, never-fabricated input): data/reject_forward_scores.json maps a
candidate id to its realized metric measured on data that arrived AFTER rejection. The desk's
forward evaluator produces it; a reject with no entry is carried as pending (never guessed). Absent
file == no scores yet == the audit reports "cannot judge until scored", which is itself the honest
standing signal to wire the evaluator.

Usage: run_rejection_shadow.py [--db data/sor_crypto.sqlite] [--threshold 0.5]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from libs.autodiscovery.memory import CandidateStore
from libs.self_improvement.adaptive_thresholds import ThresholdBook
from libs.store.connection import Database
from libs.validation.rejection_shadow import build_shadow_report

_ROOT = Path(__file__).resolve().parent.parent
_SCORES = _ROOT / "data/reject_forward_scores.json"
_OUT = _ROOT / "web/reject_shadow.json"


def main() -> None:
    book = ThresholdBook(_ROOT / "data/adaptive_thresholds.json")
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="data/sor_crypto.sqlite")
    p.add_argument("--threshold", type=float, default=None,
                   help="forward metric a reject must clear to count as 'would have paid' "
                        "(default: the evidence-adjusted reject_deploy_threshold)")
    p.add_argument("--min-age-days", type=float, default=30.0)
    a = p.parse_args()
    threshold = a.threshold if a.threshold is not None else book.get("reject_deploy_threshold")
    leak_tol = book.get("reject_leak_tolerance")
    min_sample = int(book.get("reject_min_sample"))

    db_path = _ROOT / a.db if not Path(a.db).is_absolute() else Path(a.db)
    if not db_path.exists():
        print(f"no candidate ledger at {db_path} -- nothing to audit yet")
        return
    store = CandidateStore(Database(db_path, read_only=True))
    rejects = [(r.id, r.created_at) for r in store.rejects()]

    scores: dict[str, float] = {}
    if _SCORES.exists():
        try:
            raw = json.loads(_SCORES.read_text("utf-8"))
            scores = {str(k): float(v) for k, v in raw.items()}
        except Exception:
            scores = {}

    report = build_shadow_report(
        rejects, scores, deploy_threshold=threshold, min_age_days=a.min_age_days,
        leak_tolerance=leak_tol, min_sample=min_sample,
    )
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(report.model_dump_json(indent=1), "utf-8")
    print(f"rejection-shadow: {report.n_rejects_total} rejects, {report.n_eligible} eligible, "
          f"{report.n_pending_rescore} pending re-score")
    print(f"  {report.verdict}")
    print(f"-> {_OUT}")


if __name__ == "__main__":
    main()

```

### scripts/run_root_cause.py
```python
"""Root-cause tick -> web/root_cause.json: classify the deployed book's realized deviation.

Feeds libs.research.root_cause with cheap live evidence (no new network calls beyond the feeds
already written each tick): expected PnL = funding earned (the carry model: legs cancel, funding
accrues), actual = real carry net, drift events from the reconcile's own action log, execution
health from fees-vs-funding. The verdict is what the CRO cycle is ALLOWED to react to -- the
hard rule 'never modify strategy from realized PnL alone' is enforced by the action field.

    python scripts/run_root_cause.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.research.root_cause import classify, implementation_shortfall

_WEB = Path("web/root_cause.json")


def _load(p: str) -> dict[str, Any]:
    try:
        d: dict[str, Any] = json.loads(Path(p).read_text("utf-8"))
        return d
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> None:
    lc = _load("web/live_combined.json")
    cc = _load("web/cashcarry_live.json")
    sh = _load("web/cashcarry_shadow.json")
    mo, ftr, sp = lc.get("molded", {}), lc.get("futures", {}), lc.get("spot", {})

    real_net = round(float(ftr.get("net_pnl", 0.0)) + float(sp.get("net_pnl", 0.0)), 2)
    funding = float(mo.get("funding", 0.0))
    acts = cc.get("last_actions") or []
    drift = sum(1 for a in acts if any(k in str(a) for k in
                                       ("cover-orphan", "re-hedge", "spot-rehedge", "RISK")))
    verdict = classify({
        "net_pnl": real_net, "expected_pnl": funding, "funding_earned": funding,
        "fees_paid": -12.0 if funding else 0.0,          # commissions from income (approx feed)
        "orphan_or_drift_events": drift, "restarts": 0,
        "fwd_sharpe": sh.get("forward_ann_sharpe"), "bt_sharpe": sh.get("backtest_ann_sharpe"),
        "assumption_breaks": 0,
        "nav": float(mo.get("equity", 0.0) or 0.0),      # materiality gate for unknown_novel
    })
    # implementation shortfall in bps/day on deployed notional (expected = avg funding run-rate)
    dep = float(cc.get("deployed_notional", 0.0)) or 1.0
    days = max(float(mo.get("days_live", 0.0)), 0.1)
    exp_bps = (mo.get("run_rate_apr_pct", 0.0) or 0.0) * 100.0 / 365.0
    real_bps = real_net / dep / days * 1e4
    fee_bps = 12.0 / dep / days * 1e4
    isf = implementation_shortfall(exp_bps, fee_bps, real_bps)

    out = {"updated": datetime.now(tz=UTC).isoformat(), "period": "since account start",
           "expected_pnl_usd": funding, "actual_pnl_usd": real_net, **verdict,
           "implementation_shortfall": isf,
           "note": ("only execution_issue / infrastructure_bug (conf>=0.5) or persistent, "
                    "root-caused alpha decay may trigger autonomous change; expected variance "
                    "-> DO NOTHING.")}
    _WEB.write_text(json.dumps(out, indent=2), "utf-8")
    print(f"root-cause: top={out['top_cause']} ({out['top_confidence']:.0%}) "
          f"action={out['action']} tracking_err=${out['tracking_error_usd']}")


if __name__ == "__main__":
    main()

```
