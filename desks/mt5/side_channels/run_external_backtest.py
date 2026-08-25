"""Run external discovery hypotheses through the backtest pipeline.
Reads test_grid.json, runs each cell, saves results + survivors.
"""
from __future__ import annotations
import json
import sys
import time
import warnings
warnings.filterwarnings("ignore")

from pathlib import Path
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "research"))

from mt5desk import families
from mt5desk.engine import Costs, run_backtest

_h1_cache: dict = {}
_uni = json.loads((BASE / "data" / "universe" / "universe.json").read_text("utf-8"))

FAMILY_FUNCS = {
    "session_range_breakout": families.family_session_range_breakout,
    "asia_momentum": families.family_asia_momentum,
    "momentum_volgate": families.family_momentum_volgate,
    "level_breakout": families.family_level_breakout,
    "failed_breakout": families.family_failed_breakout,
    "dow_effect": families.family_dow_effect,
    "monday_gap": families.family_monday_gap,
    "london_close_momentum": families.family_london_close_momentum,
}


def h1(sym: str) -> pd.DataFrame:
    if sym not in _h1_cache:
        _h1_cache[sym] = families._h1(pd.read_parquet(
            BASE / "data" / "universe" / f"{sym}_H1.parquet"))
    return _h1_cache[sym]


def run_cell(cell: dict) -> dict | None:
    sym = cell["symbol"]
    family_name = cell["family"]
    params = cell["params"]
    func = FAMILY_FUNCS.get(family_name)
    if not func:
        return None
    try:
        meta = _uni.get(sym, {})
        if not meta:
            return None
        df = h1(sym)
        costs = Costs.from_symbol(meta)
        sigs = list(func(df, **params))
        if len(sigs) < 20:
            return None
        result = run_backtest(df, sigs, costs=costs)
        st = result.stats()
        if st["n"] < 20:
            return None
        return {
            "symbol": sym, "family": family_name, "params": params,
            "n": st["n"], "exp_r": round(st["expectancy_r"], 4),
            "max_dd_r": round(st["max_dd_r"], 2), "t_stat": round(st["t_stat"], 2),
            "profit_factor": round(st["profit_factor"], 3),
            "win_rate": round(st["win_rate"], 4),
            "source": cell.get("source_hypothesis", ""),
            "url": cell.get("source_url", ""),
        }
    except Exception as e:
        print(f"  ERR {sym}.{family_name}: {e}")
        return None


def run_all() -> list[dict]:
    grid_file = BASE / "data" / "hypotheses" / "test_grid.json"
    if not grid_file.exists():
        print("No test_grid.json. Run bridge_to_hunt.py first.")
        return []
    grid = json.loads(grid_file.read_text(encoding="utf-8"))
    print(f"Running {len(grid)} test cells...")

    results = []
    t0 = time.time()
    for i, cell in enumerate(grid):
        r = run_cell(cell)
        if r:
            results.append(r)
            if r["exp_r"] > 0.05:
                print(f"  PASS {r['symbol']:8s}.{r['family']:25s} n={r['n']:4d} exp={r['exp_r']:+.4f}R maxDD={r['max_dd_r']:+.1f}R PF={r['profit_factor']:.2f}")
        if (i + 1) % 10 == 0:
            print(f"  [{i+1}/{len(grid)}] {time.time()-t0:.0f}s elapsed")

    elapsed = time.time() - t0
    out = BASE / "data" / "hypotheses" / "external_backtest_results.json"
    out.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")

    survivors = [r for r in results if r["exp_r"] > 0.05 and r["max_dd_r"] > -30]
    print(f"\n{len(results)} cells tested, {len(survivors)} survivors in {elapsed:.0f}s")
    for s in sorted(survivors, key=lambda x: -x["exp_r"]):
        print(f"  {s['symbol']:8s} {s['family']:25s} n={s['n']:4d} exp={s['exp_r']:+.4f}R "
              f"maxDD={s['max_dd_r']:+.1f}R PF={s['profit_factor']:.2f}")

    surv_out = BASE / "data" / "hypotheses" / "external_survivors.json"
    surv_out.write_text(json.dumps(survivors, indent=2, default=str), encoding="utf-8")
    return survivors


if __name__ == "__main__":
    run_all()
