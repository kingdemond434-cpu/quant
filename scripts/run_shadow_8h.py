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
