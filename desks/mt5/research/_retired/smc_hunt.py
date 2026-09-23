"""Price the two SMC encodings the desk had never measured, on the same rig.

Retail SMC material presents five concepts as a set. Three of them already live
in families.py under mechanism names -- a liquidity sweep IS failed_breakout, a
break of structure IS level_breakout, and HH/HL is a trend label rather than an
entry. Only fair-value gap and order block were genuinely untested here, and
this runs them across the whole universe with the desk's honest costs.

WHAT WOULD MAKE THIS DISHONEST, AND IS THEREFORE GUARDED

  - Cheap costs. Costs.from_symbol(meta, mult=2.0): a round trip crosses the
    spread twice and half of all fills are worse than the median. Gold's spread
    was understated 33x on this desk once already.
  - A parameter sweep reported as if it were one test. Every point of the grid
    is counted and the raw per-cell numbers are printed with the trial count
    beside them, so whatever gate consumes this can deflate correctly. The
    desk's standing rule is to judge on the raw threshold; that rule is about
    not MOVING the bar, not about hiding how many bets were placed.
  - A verdict from three fills. MIN_TRADES is enforced per cell.

Output: reports/smc_hunt.json + a ranked console table.
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import families                                    # noqa: E402
from mt5desk.engine import Costs, run_backtest                  # noqa: E402

UNI = _DESK / "data" / "universe"
OUT = _DESK / "reports" / "smc_hunt.json"
MIN_TRADES = 30

GRID_FVG = {
    "min_gap_atr": [0.15, 0.25, 0.40],
    "fill_depth": [0.0, 0.5],
    "rr": [1.5, 2.0, 3.0],
    "stop_atr": [0.3, 0.6],
}
GRID_OB = {
    "disp_atr": [0.8, 1.2],
    "lookback": [3, 6],
    "fill_depth": [0.0, 0.5],
    "rr": [1.5, 2.0, 3.0],
    "stop_atr": [0.3, 0.6],
}
FAMS = {
    "fair_value_gap": (families.family_fair_value_gap, GRID_FVG),
    "order_block": (families.family_order_block, GRID_OB),
}


def _points(grid: dict) -> list[dict]:
    keys = sorted(grid)
    return [dict(zip(keys, combo, strict=True))
            for combo in itertools.product(*(grid[k] for k in keys))]


def main() -> int:
    meta_all = json.loads((UNI / "universe.json").read_text("utf-8"))
    symbols = sorted({p.stem.rpartition("_")[0] or p.stem for p in UNI.glob("*.parquet")})
    rows: list[dict] = []
    trials = 0
    for sym in symbols:
        meta = meta_all.get(sym)
        if not meta:
            continue
        df = pd.read_parquet(UNI / f"{sym}_H1.parquet")
        df.index = pd.DatetimeIndex(pd.to_datetime(df.index))
        costs = Costs.from_symbol(meta, mult=2.0)
        for fam, (fn, grid) in FAMS.items():
            for params in _points(grid):
                trials += 1
                try:
                    sigs = fn(df, **params)
                except Exception as exc:                        # noqa: BLE001
                    print(f"  {sym} {fam}: generator failed ({exc})")
                    continue
                if len(sigs) < MIN_TRADES:
                    continue
                res = run_backtest(df, sigs, costs)
                st = res.stats()
                if st["n"] < MIN_TRADES:
                    continue
                rs = np.array([t.r_multiple for t in res.trades])
                rows.append({
                    "cell": f"{sym}|{fam}|" + ",".join(
                        f"{k}={v}" for k, v in sorted(params.items())),
                    "symbol": sym, "family": fam, "n": int(st["n"]),
                    "expectancy_r": round(st["expectancy_r"], 4),
                    "t_stat": round(st["t_stat"], 3),
                    "sharpe_per_trade": round(
                        float(rs.mean() / rs.std(ddof=1)) if rs.std(ddof=1) > 0 else 0.0, 4),
                    "win_rate": round(st["win_rate"], 3),
                    "profit_factor": round(min(st["profit_factor"], 99.0), 3),
                    "max_dd_r": round(st["max_dd_r"], 2),
                    "total_r": round(float(rs.sum()), 2),
                })
    rows.sort(key=lambda r: -r["t_stat"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(
        {"trials_run": trials, "cells_with_enough_trades": len(rows),
         "min_trades": MIN_TRADES, "cost_basis": "from_symbol(mult=2.0)",
         "rows": rows}, indent=1), "utf-8")

    print(f"SMC HUNT  {trials} parameter points, "
          f"{len(rows)} cells cleared n>={MIN_TRADES}")
    print(f"{'cell':<62}{'n':>5}{'E[R]':>8}{'t':>7}{'PF':>7}{'totR':>9}")
    for r in rows[:20]:
        print(f"{r['cell']:<62}{r['n']:>5}{r['expectancy_r']:>8.3f}"
              f"{r['t_stat']:>7.2f}{r['profit_factor']:>7.2f}{r['total_r']:>9.1f}")
    if not rows:
        print("  no cell produced enough trades. That is a result, not a bug --")
        print("  record it and stop, rather than loosening MIN_TRADES until")
        print("  something appears.")
        return 0
    pos = [r for r in rows if r["t_stat"] > 0]
    print(f"\n{len(pos)} of {len(rows)} cells have a positive t-stat "
          f"(chance alone gives ~{len(rows)//2}).")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
