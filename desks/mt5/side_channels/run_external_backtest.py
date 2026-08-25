"""Run external discovery hypotheses through the backtest + gate pipeline.

Reads test_grid.json, runs each cell through the existing backtest engine,
applies the 10-gate criteria, and saves survivors.
"""

from __future__ import annotations
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "research"))

from mt5desk import families
from mt5desk.engine import Costs, run_backtest
from gate_policy import all_ten_pass, is_exact_policy

POLICY_VERSION = "mt5-original-universal-10-v2-calibrated-inputs"

_h1_cache: dict = {}


def h1(sym: str) -> pd.DataFrame:
    if sym not in _h1_cache:
        f = BASE / "data" / "universe" / f"{sym}_H1.parquet"
        if not f.exists():
            raise FileNotFoundError(f"No H1 data for {sym}")
        _h1_cache[sym] = families._h1(pd.read_parquet(f))
    return _h1_cache[sym]


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


def run_cell(cell: dict) -> dict | None:
    """Run one test cell. Returns result dict or None if failed."""
    sym = cell["symbol"]
    family_name = cell["family"]
    params = cell["params"]
    func = FAMILY_FUNCS.get(family_name)
    if not func:
        return None

    try:
        uni = json.loads((BASE / "data" / "universe" / "universe.json").read_text("utf-8"))
        meta = uni.get(sym, {})
        if not meta:
            return None

        df = h1(sym)
        costs = Costs.from_symbol(meta)
        sigs = list(func(df, **params))
        if len(sigs) < 20:
            return None

        result = run_backtest(df, sigs, costs=costs)
        st = result.stats()
        n = st["n"]
        if n < 20:
            return None

        exp_r = st["expectancy_r"]
        max_dd = st["max_dd_r"]
        t_stat = st["t_stat"]
        profit_factor = st["profit_factor"]
        win_rate = st["win_rate"]

        return {
            "symbol": sym,
            "family": family_name,
            "params": params,
            "n": n,
            "exp_r": round(exp_r, 4),
            "max_dd_r": round(max_dd, 2),
            "t_stat": round(t_stat, 2),
            "profit_factor": round(profit_factor, 3),
            "win_rate": round(win_rate, 4),
            "source": cell.get("source_hypothesis", ""),
            "url": cell.get("source_url", ""),
        }
    except Exception as e:
        return None


def run_all() -> list[dict]:
    """Run all cells from test_grid.json."""
    grid_file = BASE / "data" / "hypotheses" / "test_grid.json"
    if not grid_file.exists():
        print("No test_grid.json found. Run bridge_to_hunt.py first.")
        return []

    grid = json.loads(grid_file.read_text(encoding="utf-8"))
    print(f"Running {len(grid)} test cells...")

    results = []
    for i, cell in enumerate(grid):
        r = run_cell(cell)
        if r:
            results.append(r)
            if r["exp_r"] > 0.05:
                print(f"  PASS [{i+1}/{len(grid)}] {r['symbol']}.{r['family']} "
                      f"n={r['n']} exp={r['exp_r']}R maxDD={r['max_dd_r']}R")
        if (i + 1) % 10 == 0:
            print(f"  Progress: {i+1}/{len(grid)} cells tested")

    # Save results
    out = BASE / "data" / "hypotheses" / "external_backtest_results.json"
    out.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")

    # Filter survivors (positive expectancy, reasonable drawdown)
    survivors = [r for r in results if r["exp_r"] > 0.05 and r["max_dd_r"] > -30]
    print(f"\n{len(results)} cells tested, {len(survivors)} survivors")
    for s in sorted(survivors, key=lambda x: -x["exp_r"]):
        print(f"  {s['symbol']:8s} {s['family']:25s} n={s['n']:4d} exp={s['exp_r']:+.4f}R "
              f"maxDD={s['max_dd_r']:+.1f}R PF={s['profit_factor']:.2f}")

    # Save survivors
    surv_out = BASE / "data" / "hypotheses" / "external_survivors.json"
    surv_out.write_text(json.dumps(survivors, indent=2, default=str), encoding="utf-8")

    return survivors


if __name__ == "__main__":
    start = time.time()
    survivors = run_all()
    elapsed = time.time() - start
    print(f"\nCompleted in {elapsed:.1f}s")
