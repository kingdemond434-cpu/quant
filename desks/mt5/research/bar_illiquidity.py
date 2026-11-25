"""BAR ILLIQUIDITY -- a liquidity state built from the bars the desk already holds, for the hours
the tick tape cannot see (IDEA_QUEUE row 218).

The tick moat is dead in published state, so the desk has no measured liquidity state at all.
The M1 / M5 charts in `desks/mt5/data/universe/<SYMBOL>_<TF>.parquet` (columns open, high, low,
close, tick_volume, spread, real_volume; tz-aware UTC index -- the same files
`research/blind_reviewer.load_bars` reads) carry enough to estimate two classic measures:

    CORWIN-SCHULTZ (2012) high-low spread, per pair of CONSECUTIVE bars (t-1, t):
        beta  = ln(H[t-1]/L[t-1])^2 + ln(H[t]/L[t])^2
        gamma = ln(max(H[t-1],H[t]) / min(L[t-1],L[t]))^2
        k     = 3 - 2*sqrt(2)
        alpha = (sqrt(2*beta) - sqrt(beta)) / k - sqrt(gamma / k)
        S     = 2*(exp(alpha) - 1) / (1 + exp(alpha))
      with the paper's gap adjustment (bar t's range is shifted onto close[t-1] when it gapped
      clear of it) and the paper's convention that a negative pair estimate is set to 0. The
      share of negative pairs is reported beside it, so a clipped zero is never mistaken for a
      measured zero. A pair whose bars are not adjacent on the bar clock is skipped.

    AMIHUD (tick-volume) proxy:  |ln(C[t]/C[t-1])| / tick_volume[t]   (bars with 0 ticks skipped)
    KYLE-LAMBDA proxy:           slope of r[t] on sign(r[t]) * sqrt(tick_volume[t]) within the
                                 bucket (OLS through the origin). real_volume is 0 on CFDs, so
                                 both use tick volume; the label says so.

BUCKETS AND POINT IN TIME. Each measure is aggregated per (UTC date, hour-of-day) bucket using only
bars inside that hour (a CS pair belongs to the hour of its LATER bar, so it reaches back one bar,
never forward). For every hour-of-day the CURRENT value is the latest bucket at or before `as_of`,
and its z-score is taken against that hour's OWN PRIOR buckets for the same symbol and timeframe
(strictly earlier dates, at most `--lookback-days`). Bars after `as_of` are dropped before anything
is computed. Fewer than `--min-history` prior buckets reads `z: UNMEASURED`, never 0.

FRESHNESS. Each symbol/timeframe carries first_bar, last_bar, n_bars and last_bar_age_h; an input
older than `--stale-h` is flagged STALE (the z is still the z AS OF that last bar, and says so).
No M1/M5 chart at all writes `status: UNMEASURED`.

No tape, no network, report only: `desks/mt5/reports/BAR_ILLIQUIDITY.json`.

    python desks/mt5/research/bar_illiquidity.py [--as-of 2026-09-11T23:59Z]

NO SCRIPT ENTRY GUARD (birth-obligation law, scripts/check_birth_obligations.py).
The hourly leg `bar_illiquidity` (research/hourly_cycle.py) calls `main()`
in-process. By hand, from the repo root:
    python -c "import sys; sys.path[:0]=['desks/mt5'];
        from research import bar_illiquidity as M; M.main()"
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
UNIVERSE = DESK / "data" / "universe"
OUT = DESK / "reports" / "BAR_ILLIQUIDITY.json"

SCHEMA = "bar-illiquidity/1"
UNMEASURED = "UNMEASURED"
TIMEFRAMES = {"M1": pd.Timedelta(minutes=1), "M5": pd.Timedelta(minutes=5)}
_K = 3.0 - 2.0 * math.sqrt(2.0)
MEASURES = ("cs_spread", "amihud_tick", "kyle_lambda_tick")
#: Minimum bars in an hour bucket for the bucket to count (M1: 60 max, M5: 12 max).
MIN_BARS = {"M1": 20, "M5": 6}


# ------------------------------------------------------------------------------------- loading


def load_bars(path: Path) -> pd.DataFrame | None:
    """The chart on its own UTC bar clock (blind_reviewer.load_bars' two fallback rules), sorted,
    de-duplicated; None when absent, unreadable or missing OHLC/tick_volume."""
    if not path.exists():
        return None
    try:
        frame = pd.read_parquet(path)
    except Exception:
        return None
    if "time" in frame.columns:
        frame = frame.set_index("time")
    if "timestamp" in frame.columns:
        frame = frame.set_index("timestamp")
    try:
        frame.index = pd.DatetimeIndex(frame.index)
    except (TypeError, ValueError):
        return None
    if frame.index.tz is None:
        frame.index = frame.index.tz_localize("UTC")
    else:
        frame.index = frame.index.tz_convert("UTC")
    need = {"high", "low", "close", "tick_volume"}
    if not need.issubset(frame.columns) or frame.empty:
        return None
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    return frame


# ------------------------------------------------------------------------------------ estimators


def corwin_schultz_pairs(bars: pd.DataFrame, step: pd.Timedelta) -> pd.DataFrame:
    """Per consecutive pair (t-1, t), indexed at t: raw `alpha`-based spread `s_raw` and the
    clipped `s` (negative -> 0, the paper's convention). Non-adjacent pairs are dropped."""
    h = bars["high"].astype(float).to_numpy()
    lo = bars["low"].astype(float).to_numpy()
    c = bars["close"].astype(float).to_numpy()
    idx = bars.index
    if len(bars) < 2:
        return pd.DataFrame(columns=["s_raw", "s"], index=pd.DatetimeIndex([], tz="UTC"))
    h0, l0, c0 = h[:-1], lo[:-1], c[:-1]
    h1, l1 = h[1:].copy(), lo[1:].copy()
    # gap adjustment onto the previous close
    up = l1 > c0
    adj = np.where(up, l1 - c0, 0.0)
    h1, l1 = h1 - adj, l1 - adj
    down = h1 < c0
    adj = np.where(down, c0 - h1, 0.0)
    h1, l1 = h1 + adj, l1 + adj
    with np.errstate(divide="ignore", invalid="ignore"):
        beta = np.log(h0 / l0) ** 2 + np.log(h1 / l1) ** 2
        gamma = np.log(np.maximum(h0, h1) / np.minimum(l0, l1)) ** 2
        alpha = (np.sqrt(2.0 * beta) - np.sqrt(beta)) / _K - np.sqrt(gamma / _K)
        s_raw = 2.0 * (np.exp(alpha) - 1.0) / (1.0 + np.exp(alpha))
    adjacent = (idx[1:] - idx[:-1]) == step
    valid = adjacent & np.isfinite(s_raw) & (l0 > 0) & (l1 > 0)
    out = pd.DataFrame({"s_raw": s_raw, "s": np.maximum(s_raw, 0.0)}, index=idx[1:])
    return out[valid]


def bar_flow(bars: pd.DataFrame, step: pd.Timedelta) -> pd.DataFrame:
    """Per bar t (adjacent to t-1, tick_volume > 0): log return r, |r|/ticks, signed sqrt ticks."""
    c = bars["close"].astype(float)
    v = bars["tick_volume"].astype(float)
    r = np.log(c / c.shift(1))
    adjacent = pd.Series(bars.index, index=bars.index).diff() == step
    ok = adjacent & (v > 0) & np.isfinite(r)
    df = pd.DataFrame({"r": r, "amihud": r.abs() / v, "sv": np.sign(r) * np.sqrt(v)})
    return df[ok]


def _kyle(g: pd.DataFrame) -> float:
    sv, r = g["sv"].to_numpy(), g["r"].to_numpy()
    den = float(np.dot(sv, sv))
    return float(np.dot(sv, r) / den) if den > 0 else float("nan")


def hourly_buckets(bars: pd.DataFrame, tf: str) -> pd.DataFrame:
    """One row per (UTC date, hour) bucket with each measure; buckets short of MIN_BARS dropped.
    Index: the bucket's START (tz UTC). Columns: MEASURES + n_bars + cs_negative_share."""
    step = TIMEFRAMES[tf]
    cs = corwin_schultz_pairs(bars, step)
    fl = bar_flow(bars, step)
    cs_g = cs.groupby(cs.index.floor("h"))
    fl_g = fl.groupby(fl.index.floor("h"))
    out = pd.DataFrame(
        {
            "cs_spread": cs_g["s"].mean(),
            "cs_negative_share": cs_g["s_raw"].apply(lambda x: float((x < 0).mean())),
            "n_cs_pairs": cs_g["s"].size(),
        }
    )
    flow = pd.DataFrame(
        {
            "amihud_tick": fl_g["amihud"].mean(),
            "kyle_lambda_tick": fl_g[["r", "sv"]].apply(_kyle),
            "n_bars": fl_g["r"].size(),
        }
    )
    out = out.join(flow, how="outer")
    keep = (out["n_cs_pairs"].fillna(0) >= MIN_BARS[tf]) | (out["n_bars"].fillna(0) >= MIN_BARS[tf])
    return out[keep].sort_index()


def _num(x: Any) -> Any:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return UNMEASURED
    return round(f, 10) if math.isfinite(f) else UNMEASURED


def zscore_by_hour(
    buckets: pd.DataFrame, as_of: pd.Timestamp, lookback_days: int, min_history: int
) -> dict[str, Any]:
    """For each hour-of-day: the latest bucket at or before `as_of` and its z against strictly
    earlier buckets of the same hour (no look-ahead: later buckets are never read)."""
    res: dict[str, Any] = {}
    b = buckets[buckets.index + pd.Timedelta(hours=1) <= as_of + pd.Timedelta(microseconds=1)]
    for hour, g in b.groupby(b.index.hour):
        cur_ts = g.index[-1]
        hist = g[(g.index < cur_ts) & (g.index >= cur_ts - pd.Timedelta(days=lookback_days))]
        row: dict[str, Any] = {
            "bucket_start_utc": cur_ts.isoformat(),
            "n_bars": _num(g["n_bars"].iloc[-1]),
            "cs_negative_share": _num(g["cs_negative_share"].iloc[-1]),
        }
        for m in MEASURES:
            cur = g[m].iloc[-1]
            h = hist[m].dropna()
            entry: dict[str, Any] = {"value": _num(cur), "n_history": len(h)}
            if len(h) >= min_history and np.isfinite(cur):
                mu, sd = float(h.mean()), float(h.std(ddof=1))
                entry["mean"], entry["std"] = _num(mu), _num(sd)
                entry["z"] = _num((cur - mu) / sd) if sd > 0 else UNMEASURED
            else:
                entry["mean"] = entry["std"] = UNMEASURED
                entry["z"] = UNMEASURED
                entry["why"] = (
                    f"{len(h)} prior buckets < {min_history}"
                    if np.isfinite(cur)
                    else "no current value"
                )
            row[m] = entry
        res[f"{hour:02d}"] = row
    return res


# ---------------------------------------------------------------------------------------- build


def discover(universe: Path) -> dict[str, dict[str, Path]]:
    out: dict[str, dict[str, Path]] = {}
    for tf in TIMEFRAMES:
        for p in sorted(universe.glob(f"*_{tf}.parquet")):
            out.setdefault(p.name[: -len(f"_{tf}.parquet")], {})[tf] = p
    return out


def analyse(
    bars: pd.DataFrame,
    tf: str,
    as_of: pd.Timestamp,
    *,
    lookback_days: int = 60,
    min_history: int = 10,
    stale_h: float = 48.0,
    now: datetime | None = None,
) -> dict[str, Any]:
    bars = bars[bars.index <= as_of]
    now = now or datetime.now(tz=UTC)
    if bars.empty:
        return {"status": UNMEASURED, "why": "no bars at or before as_of"}
    last = bars.index[-1]
    age_h = (pd.Timestamp(now) - last).total_seconds() / 3600.0
    fresh = {
        "first_bar_utc": bars.index[0].isoformat(),
        "last_bar_utc": last.isoformat(),
        "n_bars": len(bars),
        "last_bar_age_h": round(age_h, 2),
        "stale": bool(age_h > stale_h),
        "stale_threshold_h": stale_h,
    }
    buckets = hourly_buckets(bars, tf)
    if buckets.empty:
        return {"status": UNMEASURED, "why": "no complete hour buckets", "freshness": fresh}
    hours = zscore_by_hour(buckets, as_of, lookback_days, min_history)
    return {
        "status": "STALE" if fresh["stale"] else "OK",
        "freshness": fresh,
        "n_buckets": len(buckets),
        "hours": hours,
    }


def build(
    universe: Path = UNIVERSE,
    as_of: datetime | None = None,
    *,
    lookback_days: int = 60,
    min_history: int = 10,
    stale_h: float = 48.0,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    cut = pd.Timestamp(as_of or now)
    cut = cut.tz_localize("UTC") if cut.tzinfo is None else cut.tz_convert("UTC")
    doc: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_utc": now.isoformat(),
        "as_of_utc": cut.isoformat(),
        "source": "own M1/M5 bars (data/universe/<SYM>_<TF>.parquet); no tape, no network",
        "params": {
            "lookback_days": lookback_days,
            "min_history": min_history,
            "stale_h": stale_h,
            "min_bars_per_bucket": MIN_BARS,
        },
        "method": {
            "cs_spread": "Corwin-Schultz 2012, gap-adjusted, negative pairs -> 0 "
            "(cs_negative_share reported)",
            "amihud_tick": "|log return| / tick_volume per bar, hour mean",
            "kyle_lambda_tick": "OLS slope of log return on sign*sqrt(tick_volume) "
            "through the origin, per hour bucket",
            "z": "against the same symbol/timeframe/hour-of-day's strictly earlier "
            "buckets within lookback_days",
        },
    }
    found = discover(universe)
    if not found:
        doc.update(
            {
                "status": UNMEASURED,
                "why": f"no *_M1/*_M5 parquet under {universe}",
                "symbols": UNMEASURED,
            }
        )
        return doc
    symbols: dict[str, Any] = {}
    for sym, tfs in sorted(found.items()):
        for tf, path in tfs.items():
            bars = load_bars(path)
            symbols.setdefault(sym, {})[tf] = (
                {"status": UNMEASURED, "why": f"{path.name} unreadable"}
                if bars is None
                else analyse(
                    bars,
                    tf,
                    cut,
                    lookback_days=lookback_days,
                    min_history=min_history,
                    stale_h=stale_h,
                    now=now,
                )
            )
    statuses = {v["status"] for s in symbols.values() for v in s.values()}
    doc["status"] = (
        "OK"
        if statuses == {"OK"}
        else "STALE"
        if "OK" not in statuses and "STALE" in statuses
        else "PARTIAL"
        if "OK" in statuses
        else UNMEASURED
    )
    doc["symbols"] = symbols
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--universe", type=Path, default=UNIVERSE)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--as-of", default=None, help="ISO timestamp; default now (UTC)")
    ap.add_argument("--lookback-days", type=int, default=60)
    ap.add_argument("--min-history", type=int, default=10)
    ap.add_argument("--stale-h", type=float, default=48.0)
    a = ap.parse_args(argv)
    as_of = pd.Timestamp(a.as_of).to_pydatetime() if a.as_of else None
    doc = build(
        a.universe,
        as_of,
        lookback_days=a.lookback_days,
        min_history=a.min_history,
        stale_h=a.stale_h,
    )
    a.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = a.out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    tmp.replace(a.out)
    print(f"{doc['status']} -> {a.out}")
    return 0

