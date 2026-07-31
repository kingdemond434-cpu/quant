#!/usr/bin/env python3
"""CHART CONTEXT (R0134) -- the chart the discretionary sleeve was never shown.

THE GAP THIS CLOSES, and it is embarrassing once seen. The principal asked for "a strategy where
Claude acts like a human trader with a brain and trades 24/7 at charts". What was built reads
funding, liquidations and announcements -- and NO PRICE STRUCTURE AT ALL. It was asked to name a
swing high it had never been shown. A discretionary trader with no chart is not a discretionary
trader; it is a headline reader with a leverage dial, which is exactly the "too calculative,
earns less than a manual trader" failure the principal described.

So this organ builds, per instrument, what a professional actually has on screen before deciding:

  MULTI-TIMEFRAME STRUCTURE -- 15m/1h/4h swing highs and lows located by fractal pivots, with
  their prices, ages and how many times each has been touched. A level touched three times and
  held is not the same object as a level touched once, and the difference is most of what
  discretionary edge IS.

  TREND STATE per timeframe, from the swing sequence itself (higher-highs-and-higher-lows, or
  lower-lows-and-lower-highs, or neither) rather than from a moving average, because the sequence
  is what the stop has to respect. A trade with the 4h trend and against the 15m pullback is a
  different animal from one fighting both.

  POSITION IN RANGE, and DISTANCE TO THE NEAREST LEVEL each way, in percent. This is the number
  that decides whether a trade has room: long into resistance 0.3% away with an invalidation 2%
  below is a bad trade at any conviction, and no amount of narrative fixes it.

  VOLATILITY REGIME -- current ATR against its own 30-day median, so expansion and contraction
  are visible. The same 1% stop is generous in a dead tape and inside the noise in an expanding
  one, which the noise floor already prices and the model should be able to see coming.

  MOMENTUM over 1h/4h/24h/7d, and where price sits in the day's and week's range.

WHY A SEPARATE ORGAN AND NOT INLINE IN THE TRADER: this makes ~3 venue calls per instrument
across a widened universe. Inline, that is a slow, failure-prone trader; as an organ it is cached,
scheduled, individually testable, and its failures are visible as staleness rather than as a
trader that silently reasoned over nothing. UNAVAILABLE instruments are RECORDED, never dropped
silently -- a universe that quietly shrinks to whatever happened to answer is a universe nobody
chose.

    python scripts/build_chart_context.py [--json] [--symbols BTCUSDT,ETHUSDT]
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

_OUT = "data/chart_context.json"

#: Pivot half-width: a bar is a swing high if its high exceeds the highs of PIVOT_K bars on BOTH
#: sides. 3 is the usual discretionary reading -- 2 finds noise, 5 finds only the obvious.
PIVOT_K = 3
#: How close two swings must be (percent) to count as the SAME level being retested rather than
#: two separate levels. This is what turns a list of pivots into a level with a touch count.
LEVEL_TOL_PCT = 0.35
MAX_LEVELS = 4

#: Timeframe -> (bars to fetch, lookback hours). 4h context is what keeps a scalp from fighting
#: the daily trend; 15m is where the invalidation actually sits.
_TFS: tuple[tuple[str, int, int], ...] = (("15m", 200, 60), ("1h", 200, 220), ("4h", 200, 850))


def pivots(bars: list[tuple[int, float, float, float, float]], k: int = PIVOT_K
           ) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """Fractal swing highs and lows: the levels a structural stop is allowed to sit behind."""
    highs, lows = [], []
    for i in range(k, len(bars) - k):
        window = bars[i - k:i + k + 1]
        if bars[i][2] == max(b[2] for b in window) and bars[i][2] > bars[i - 1][2]:
            highs.append((i, bars[i][2]))
        if bars[i][3] == min(b[3] for b in window) and bars[i][3] < bars[i - 1][3]:
            lows.append((i, bars[i][3]))
    return highs, lows


def cluster_levels(points: list[tuple[int, float]], n_bars: int, *, tol_pct: float = LEVEL_TOL_PCT,
                   limit: int = MAX_LEVELS) -> list[dict[str, Any]]:
    """Collapse nearby pivots into LEVELS with a touch count and an age.

    A level touched three times and held is a different object from one touched once, and telling
    them apart is most of what discretionary structure reading is. Sorted by touches then recency,
    because a heavily-defended level matters more than a fresher accidental one."""
    levels: list[dict[str, Any]] = []
    for idx, px in sorted(points, key=lambda p: -p[0]):          # newest first
        for lv in levels:
            if abs(px - lv["price"]) / max(lv["price"], 1e-9) * 100.0 <= tol_pct:
                lv["touches"] += 1
                lv["price"] = (lv["price"] * (lv["touches"] - 1) + px) / lv["touches"]
                break
        else:
            levels.append({"price": px, "touches": 1, "last_bar": idx})
    for lv in levels:
        lv["price"] = round(lv["price"], 8)
        lv["bars_ago"] = n_bars - 1 - lv.pop("last_bar")
    levels.sort(key=lambda lv: (-lv["touches"], lv["bars_ago"]))
    return levels[:limit]


def trend_state(highs: list[tuple[int, float]], lows: list[tuple[int, float]]) -> str:
    """Trend from the SWING SEQUENCE, not a moving average -- the sequence is what the stop has to
    respect, and it is what a human means by 'the trend is up'."""
    if len(highs) < 2 or len(lows) < 2:
        return "UNREADABLE -- too few swings"
    hh = highs[-1][1] > highs[-2][1]
    hl = lows[-1][1] > lows[-2][1]
    if hh and hl:
        return "UPTREND (higher highs, higher lows)"
    if not hh and not hl:
        return "DOWNTREND (lower highs, lower lows)"
    return "RANGE/TRANSITION (swings disagree)"


def atr_pct(bars: list[tuple[int, float, float, float, float]], n: int = 14) -> float | None:
    if len(bars) < n + 1:
        return None
    trs = []
    for prev, cur in zip(bars[-n - 1:-1], bars[-n:]):
        trs.append(max(cur[2] - cur[3], abs(cur[2] - prev[4]), abs(cur[3] - prev[4])))
    last = bars[-1][4]
    return round(sum(trs) / len(trs) / last * 100.0, 4) if last else None


def _pct(a: float, b: float) -> float | None:
    return round((a - b) / b * 100.0, 3) if b else None


def timeframe_view(bars: list[tuple[int, float, float, float, float]]) -> dict[str, Any]:
    if len(bars) < PIVOT_K * 2 + 5:
        return {"state": "UNMEASURED", "why": f"only {len(bars)} bars"}
    price = bars[-1][4]
    highs, lows = pivots(bars)
    hi, lo = max(b[2] for b in bars), min(b[3] for b in bars)
    res = [lv for lv in cluster_levels(highs, len(bars)) if lv["price"] > price]
    sup = [lv for lv in cluster_levels(lows, len(bars)) if lv["price"] < price]
    atr = atr_pct(bars)
    med_atr = None
    if len(bars) >= 60:
        window = [atr_pct(bars[:i]) for i in range(30, len(bars), 5)]
        vals = sorted(v for v in window if v is not None)
        med_atr = vals[len(vals) // 2] if vals else None
    return {
        "state": "OK",
        "trend": trend_state(highs, lows),
        "price": round(price, 8),
        "range_high": round(hi, 8), "range_low": round(lo, 8),
        "position_in_range": round((price - lo) / (hi - lo), 3) if hi > lo else None,
        "resistance_levels": res, "support_levels": sup,
        "nearest_resistance_pct": _pct(res[0]["price"], price) if res else None,
        "nearest_support_pct": _pct(sup[0]["price"], price) if sup else None,
        "atr_pct": atr,
        "atr_vs_30d_median": (round(atr / med_atr, 2) if atr and med_atr else None),
        "vol_regime": ("EXPANDING" if atr and med_atr and atr > med_atr * 1.25 else
                       "CONTRACTING" if atr and med_atr and atr < med_atr * 0.8 else
                       "NORMAL" if atr and med_atr else "UNMEASURED"),
        "n_swing_highs": len(highs), "n_swing_lows": len(lows),
    }


def build_symbol(symbol: str, *, fetch=None, now: datetime | None = None) -> dict[str, Any]:
    if fetch is None:
        from scripts.resolve_paper_book import fetch_bars as fetch
    now = now or datetime.now(tz=UTC)
    now_ms = int(now.timestamp() * 1000)
    out: dict[str, Any] = {"symbol": symbol, "timeframes": {}}
    last_bars: list[tuple[int, float, float, float, float]] = []
    for tf, _n, hours in _TFS:
        bars, source = fetch(symbol, now_ms - hours * 3600 * 1000, now_ms, tf)
        if not bars:
            out["timeframes"][tf] = {"state": "UNAVAILABLE", "why": source}
            continue
        out["timeframes"][tf] = {**timeframe_view(bars), "source": source, "bars": len(bars)}
        if tf == "15m":
            last_bars = bars
    if last_bars:
        px = last_bars[-1][4]
        out["momentum_pct"] = {}
        for label, back in (("1h", 4), ("4h", 16), ("24h", 96), ("7d", 672)):
            out["momentum_pct"][label] = (_pct(px, last_bars[-back - 1][4])
                                          if len(last_bars) > back else None)
        day = last_bars[-96:] if len(last_bars) >= 96 else last_bars
        dh, dl = max(b[2] for b in day), min(b[3] for b in day)
        out["day_range"] = {"high": round(dh, 8), "low": round(dl, 8),
                            "position": round((px - dl) / (dh - dl), 3) if dh > dl else None}
        out["_returns"] = _returns(last_bars)          # stripped after the correlation pass
    ok = [v for v in out["timeframes"].values() if v.get("state") == "OK"]
    out["state"] = "OK" if len(ok) == len(_TFS) else ("PARTIAL" if ok else "UNAVAILABLE")
    return out


def _returns(bars: list[tuple[int, float, float, float, float]], n: int = 96) -> list[float]:
    closes = [b[4] for b in bars[-(n + 1):]]
    return [(b - a) / a for a, b in zip(closes, closes[1:]) if a]


def correlations(series: dict[str, list[float]]) -> dict[str, dict[str, float]]:
    """Pairwise return correlation across the universe.

    THIS IS WHAT MAKES BREADTH REAL. The simulation that justified spreading risk across many
    positions assumed the bets were INDEPENDENT -- but five crypto longs in a correlated tape is
    one position wearing five names, and summing their risk as though they were separate both
    overstates safety AND blocks trades that were genuinely diversifying. Measured correlation
    lets the heat rail do the honest thing in both directions."""
    out: dict[str, dict[str, float]] = {}
    for a, xs in series.items():
        out[a] = {}
        for b, ys in series.items():
            n = min(len(xs), len(ys))
            if n < 30:
                out[a][b] = 1.0 if a == b else 0.9      # too little data -> assume the WORST case
                continue
            x, y = xs[-n:], ys[-n:]
            mx, my = sum(x) / n, sum(y) / n
            sxy = sum((i - mx) * (j - my) for i, j in zip(x, y))
            sxx = sum((i - mx) ** 2 for i in x)
            syy = sum((j - my) ** 2 for j in y)
            out[a][b] = round(sxy / (sxx * syy) ** 0.5, 4) if sxx > 0 and syy > 0 else 0.9
    return out


def build(symbols: tuple[str, ...], *, fetch=None, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    charts = {s: build_symbol(s, fetch=fetch, now=now) for s in symbols}
    series = {s: c["_returns"] for s, c in charts.items() if c.get("_returns")}
    corr = correlations(series)
    for c in charts.values():
        c.pop("_returns", None)
    unavailable = [s for s, c in charts.items() if c["state"] == "UNAVAILABLE"]
    partial = [s for s, c in charts.items() if c["state"] == "PARTIAL"]
    return {
        "generated": now.isoformat(),
        "law": "L1.28a -- the discretionary sleeve was asked to read charts it had never been "
               "shown. Unavailable instruments are RECORDED, never silently dropped: a universe "
               "that shrinks to whatever answered is a universe nobody chose.",
        "status": "OK" if not unavailable and not partial else (
            "DEGRADED" if not unavailable else "PARTIAL-UNIVERSE"),
        "n_symbols": len(symbols), "n_ok": len(symbols) - len(unavailable) - len(partial),
        "unavailable": unavailable, "partial": partial,
        "detail": (f"{len(symbols) - len(unavailable) - len(partial)}/{len(symbols)} instruments "
                   f"charted across {len(_TFS)} timeframes"
                   + (f"; UNAVAILABLE: {', '.join(unavailable)}" if unavailable else "")
                   + (f"; PARTIAL: {', '.join(partial)}" if partial else "")),
        "charts": charts,
        "correlations": corr,
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.symbols:
        syms = tuple(s.strip().upper() for s in args.symbols.split(",") if s.strip())
    else:
        from scripts.run_conviction_trader import INSTRUMENTS as syms
    rep = build(tuple(syms))
    out = _ROOT / _OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    print(json.dumps(rep, indent=2) if args.json else
          f"chart context (R0134): {rep['status']} -- {rep['detail']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
