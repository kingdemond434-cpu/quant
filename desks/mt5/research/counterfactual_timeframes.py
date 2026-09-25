"""THE SAME TRADE, REPLAYED ON EVERY CHART -- counterfactual attribution per timeframe.

THE GAP THE LEDGER NAMED (Tier-1 B23): *"arms are priced per decision on one axis, not per trade
at M1, M5, M15 and H1."* `counterfactual_replay` prices size, execution and exit arms for each
decision on the H1 tape and nothing else, so every number it publishes inherits one assumption
nobody states: that an hourly bar is a fine enough description of what happened. It is not. A stop
and a target inside the SAME hourly bar resolve in whatever order the hour's high and low are
guessed to have come in; on M5 that order is observed. A desk that prices its exits on H1 and
executes them in real time is scoring itself on a chart it does not trade.

WHAT IS MEASURED. For each priced decision the desk actually made, the identical row is re-priced
by the SAME pricer (`libs.research.counterfactual_world.price_row`, unchanged) on each chart the
desk holds bars for. Two numbers come back per chart:

    baseline_r      what the desk's own bracket earned when the path is replayed at that
                    resolution -- the resolution effect, isolated, because the decision, the
                    stop, the target and the cost model are identical across charts
    best_arm        the best alternative arm at that resolution, so the road-not-taken question
                    is asked at every horizon rather than at one

    TIMEFRAME_ALPHA(tf) = baseline_r(tf) - baseline_r(reference chart)

positive means the finer chart says the trade did BETTER than the H1 replay believed, negative
that H1 flattered it. The aggregate per chart is published with its n and its interval; a chart
with no bars on this host is UNMEASURED with that reason and never a zero (L1.28a).

THE HORIZON DIFFERENCE IS NAMED, NOT HIDDEN. The pricer's time exit is counted in BARS, so the
same `TTL_BARS` is a different number of hours on each chart. Every row carries `ttl_hours` for
the chart it was priced on, so a reader can tell a resolution effect from a horizon effect
instead of attributing both to the chart.

WHAT CONSUMES IT. `miner_candidate_compiler.expand_axes` expands every mechanism onto every
intraday chart the desk holds bars for, in a FIXED order that no measurement ever informed. It now
asks this organ which charts have actually paid and tests those FIRST. Nothing is dropped, no
chart is refused and no threshold is applied (L1.60; the principal's never-reduce-aggressiveness
order): this is the ORDER work is done in.

    python desks/mt5/research/counterfactual_timeframes.py --once --budget-s 240
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import counterfactual_world as cw  # noqa: E402

DATASET = DESK / "data" / "decision_dataset.jsonl"
TWIN = DESK / "reports" / "EXECUTION_TWIN.json"
SURFACE = DESK / "reports" / "FILL_SURFACE.json"
UNIVERSE = DESK / "data" / "universe" / "universe.json"
UNI = DESK / "data" / "universe"
OUT = DESK / "reports" / "COUNTERFACTUAL_TIMEFRAMES.json"

CHARTS = ("M1", "M5", "M15", "H1")
REFERENCE = "H1"
CHART_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60}
MIN_N = 5                  # rows per chart below this: UNMEASURED with its n
MAX_ROWS = 400             # newest decisions first; the pass is hourly and the tape is append-only


def _read_json(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _decisions(limit: int = MAX_ROWS) -> list[dict[str, Any]]:
    try:
        lines = DATASET.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("minute") and row.get("symbol"):
            rows.append(row)
        if len(rows) >= limit:
            break
    return rows


def bars_for(symbol: str, chart: str, cache: dict[str, list[cw.Bar]]) -> list[cw.Bar]:
    """The symbol's bars on one chart, as the pricer's own Bar list. Absent parquet -> []."""
    key = f"{symbol}|{chart}"
    if key in cache:
        return cache[key]
    rows: list[cw.Bar] = []
    path = UNI / f"{symbol}_{chart}.parquet"
    if path.exists():
        try:
            import pandas as pd
            df = pd.read_parquet(path)
            need = ("open", "high", "low", "close")
            if all(c in df.columns for c in need):
                idx = df.index
                if "time" in df.columns:
                    idx = pd.to_datetime(df["time"], utc=True, errors="coerce")
                rows = cw.bars_from_rows(
                    [(t, o, h, lo, c) for t, o, h, lo, c in
                     zip(idx, df["open"], df["high"], df["low"], df["close"], strict=False)])
        except Exception:                          # a torn parquet is NO_BARS, never a failed pass
            rows = []
    cache[key] = rows
    return rows


def _cost_for(symbol: str, price: float | None, twin: dict[str, Any], surface: dict[str, Any],
              universe: dict[str, Any], cache: dict[str, cw.CostModel]) -> cw.CostModel:
    if symbol in cache:
        return cache[symbol]
    meta = universe.get(symbol) if isinstance(universe.get(symbol), dict) else None
    cache[symbol] = cw.resolve_cost_model(symbol, twin=twin or None, surface=surface or None,
                                          meta=meta, price=price)
    return cache[symbol]


def _baseline_r(block: dict[str, Any]) -> float | None:
    base = block.get("baseline") if isinstance(block.get("baseline"), dict) else None
    for key in ("r", "r_multiple", "realised_r"):
        v = (base or {}).get(key)
        try:
            f = float(v)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            return f
    return None


def _best_arm(block: dict[str, Any]) -> dict[str, Any] | None:
    best = block.get("best_alternative")
    return best if isinstance(best, dict) else None


def _stat(values: list[float]) -> dict[str, Any]:
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": None, "se": None, "verdict": "UNMEASURED",
                "why": "no row priced on this chart"}
    mean = sum(values) / n
    if n < MIN_N:
        return {"n": n, "mean": round(mean, 8), "se": None, "verdict": "UNMEASURED",
                "why": f"{n} row(s), under the floor of {MIN_N}"}
    var = sum((v - mean) ** 2 for v in values) / (n - 1) if n > 1 else 0.0
    se = math.sqrt(var / n)
    return {"n": n, "mean": round(mean, 8), "se": round(se, 8),
            "ci95": [round(mean - 1.96 * se, 8), round(mean + 1.96 * se, 8)],
            "verdict": "MEASURED"}


def chart_order(symbol: str, charts: list[str]) -> list[str]:
    """THE CONSUMER'S DOOR. `miner_candidate_compiler.expand_axes` hands its chart list here and
    expands in the order that comes back: the charts whose replay paid MOST first.

    Every chart the measurement does not know keeps its original position after the measured
    ones. Nothing is dropped and no chart is refused -- an unmeasured chart is still expanded."""
    doc = _read_json(OUT)
    ranked: dict[str, float] = {}
    _per = doc.get("per_chart_by_symbol")
    per: dict[str, Any] = dict(_per) if isinstance(_per, dict) else {}
    _rows = per.get(symbol)
    if not isinstance(_rows, dict):
        _all = doc.get("per_chart")
        _rows = _all if isinstance(_all, dict) else {}
    rows: dict[str, Any] = dict(_rows)
    for chart, row in rows.items():
        if isinstance(row, dict) and row.get("verdict") == "MEASURED" \
                and row.get("mean") is not None:
            ranked[str(chart)] = float(row["mean"])
    if not ranked:
        return list(charts)
    known = sorted([c for c in charts if c in ranked], key=lambda c: -ranked[c])
    return [*known, *[c for c in charts if c not in ranked]]


def build(budget_s: float = 240.0, limit: int = MAX_ROWS) -> dict[str, Any]:
    t0 = time.monotonic()
    rows = _decisions(limit)
    if not rows:
        return {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": ("no data/decision_dataset.jsonl rows on this host: the counterfactual "
                        "world has priced nothing yet, so there is no trade to re-price"),
                "n_rows": 0, "per_chart": {}, "seconds": round(time.monotonic() - t0, 3)}
    twin, surface, universe = _read_json(TWIN), _read_json(SURFACE), _read_json(UNIVERSE)
    bars_cache: dict[str, list[cw.Bar]] = {}
    cost_cache: dict[str, cw.CostModel] = {}
    per_chart_vals: dict[str, list[float]] = {c: [] for c in CHARTS}
    per_sym_vals: dict[str, dict[str, list[float]]] = {}
    statuses: dict[str, dict[str, int]] = {c: {} for c in CHARTS}
    priced_rows: list[dict[str, Any]] = []
    for row in rows:
        if time.monotonic() - t0 > budget_s:
            break
        symbol = str(row.get("symbol"))
        _chosen = row.get("chosen_action")
        chosen: dict[str, Any] = dict(_chosen) if isinstance(_chosen, dict) else {}
        price: float | None
        try:
            price = float(chosen.get("price"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            price = None
        cost = _cost_for(symbol, price, twin, surface, universe, cost_cache)
        by_chart: dict[str, Any] = {}
        for chart in CHARTS:
            bars = bars_for(symbol, chart, bars_cache)
            if not bars:
                by_chart[chart] = {"status": cw.NO_BARS,
                                   "why": f"no {symbol}_{chart}.parquet on this host"}
                statuses[chart][cw.NO_BARS] = statuses[chart].get(cw.NO_BARS, 0) + 1
                continue
            block = cw.price_row(row, bars, cost)
            st = str(block.get("status"))
            statuses[chart][st] = statuses[chart].get(st, 0) + 1
            entry = {"status": st, "baseline_r": _baseline_r(block),
                     "best_alternative": _best_arm(block),
                     "ttl_hours": round(cw.TTL_BARS * CHART_MINUTES.get(chart, 60) / 60.0, 3)}
            by_chart[chart] = entry
        ref = by_chart.get(REFERENCE) or {}
        ref_r = ref.get("baseline_r") if isinstance(ref, dict) else None
        if ref_r is not None:
            for chart, entry in by_chart.items():
                r = entry.get("baseline_r") if isinstance(entry, dict) else None
                if r is None or chart == REFERENCE:
                    continue
                d = float(r) - float(ref_r)  # type: ignore[arg-type]
                entry["timeframe_alpha_r"] = round(d, 8)
                per_chart_vals[chart].append(d)
                per_sym_vals.setdefault(symbol, {}).setdefault(chart, []).append(d)
        priced_rows.append({"minute": row.get("minute"), "symbol": symbol,
                            "side": row.get("side"), "by_chart": by_chart})
    per_chart = {c: {**_stat(v), "ttl_hours": round(cw.TTL_BARS * CHART_MINUTES.get(c, 60) / 60.0,
                                                    3),
                     "status_census": statuses[c]}
                 for c, v in per_chart_vals.items()}
    per_chart_by_symbol = {sym: {c: _stat(v) for c, v in charts.items()}
                           for sym, charts in per_sym_vals.items()}
    measured = [c for c, v in per_chart.items() if v["verdict"] == "MEASURED"]
    return {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "status": "OK" if measured else "UNMEASURED",
        "n_rows": len(priced_rows), "n_offered": len(rows),
        "charts": list(CHARTS), "reference_chart": REFERENCE,
        "pricer_version": cw.PRICER_VERSION, "ttl_bars": cw.TTL_BARS,
        "sign": ("TIMEFRAME_ALPHA(tf) = baseline_r(tf) - baseline_r(H1): positive means the "
                 "finer chart says the trade did BETTER than the hourly replay believed"),
        "per_chart": per_chart,
        "per_chart_by_symbol": per_chart_by_symbol,
        "rows": priced_rows[:60],
        "min_n": MIN_N,
        "consumers": [
            "desks/mt5/research/miner_candidate_compiler.py expand_axes -> chart_order(): the "
            "charts whose replay paid most are expanded first; nothing is dropped",
            "reports/COUNTERFACTUAL_TIMEFRAMES.json -> the per-chart record beside "
            "COUNTERFACTUAL_WORLD.json's single-axis one",
        ],
        "boundary": (
            "THE SAME PRICER, THE SAME DECISION, DIFFERENT BARS. `counterfactual_world` is "
            "imported unchanged; no arm, cost model or risk fraction is redefined here, and no "
            "chart is refused -- an unmeasured chart is still expanded by the compiler."),
        "seconds": round(time.monotonic() - t0, 3),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--limit", type=int, default=MAX_ROWS)
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s, limit=a.limit)
    try:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    except OSError as exc:
        print(f"counterfactual timeframes: could not write {OUT}: {exc}")
        return 1
    if doc["status"] == "UNMEASURED" and not doc.get("per_chart"):
        print(f"counterfactual timeframes: UNMEASURED -- {doc.get('why')}")
    else:
        print(f"counterfactual timeframes: {doc['n_rows']} decision(s) re-priced on "
              f"{len(doc['charts'])} chart(s), reference {doc['reference_chart']}")
        for chart, row in doc["per_chart"].items():
            print(f"   {chart:<4} {row['verdict']:<10} n={row['n']:<4} "
                  f"mean_alpha_r={row['mean']} ttl_h={row['ttl_hours']}")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
