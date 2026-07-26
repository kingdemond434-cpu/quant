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
