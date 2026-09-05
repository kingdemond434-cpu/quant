"""Run external discovery hypotheses through the backtest pipeline.

v2: ZERO HARDCODING. Auto-discovers families from FAMILY_REGISTRY.
Reads hypotheses, generates test grid from registry, runs each cell,
saves results + survivors. No hardcoded family dict.
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
sys.path.insert(0, str(BASE / "mt5desk"))

from mt5desk import families
from mt5desk.families import (
    FAMILY_REGISTRY, get_family_func, generate_test_grid,
)
from mt5desk.engine import Costs, run_backtest

_h1_cache: dict = {}
_uni = json.loads((BASE / "data" / "universe" / "universe.json").read_text("utf-8"))


def h1(sym: str) -> pd.DataFrame:
    if sym not in _h1_cache:
        _h1_cache[sym] = families._h1(pd.read_parquet(
            BASE / "data" / "universe" / f"{sym}_H1.parquet"))
    return _h1_cache[sym]


def build_grid_from_hypotheses(hypotheses: list[dict]) -> list[dict]:
    """Build test grid from hypotheses. Each hypothesis → family + default params.

    If the hypothesis specifies param overrides, those are merged on top.
    """
    grid = []
    for hyp in hypotheses:
        sym = hyp.get("symbol", "")
        family_name = hyp.get("family", "")
        func = get_family_func(family_name)
        if not func:
            continue
        entry = FAMILY_REGISTRY.get(family_name, {})
        params = dict(entry.get("defaults", {}))
        # Hypothesis can override specific params
        for k, v in hyp.items():
            if k in ("symbol", "family", "id", "source", "description",
                      "url", "confidence", "patterns", "created"):
                continue
            if k in params:
                params[k] = v
        grid.append({
            "symbol": sym,
            "family": family_name,
            "params": params,
            "source_hypothesis": hyp.get("id", ""),
            "source_url": hyp.get("url", ""),
        })
    return grid


def run_cell(cell: dict) -> dict | None:
    sym = cell["symbol"]
    family_name = cell["family"]
    params = cell["params"]
    func = get_family_func(family_name)
    if not func:
        return None
    try:
        meta = _uni.get(sym, {})
        if not meta:
            return None
        df = h1(sym)
        costs = Costs.from_symbol(meta)

        # Some families need extra args (cot, fx) — try with defaults
        import inspect
        sig = inspect.signature(func)
        extra_args = {}
        for pname, param in sig.parameters.items():
            if pname == "df":
                continue
            if pname in params:
                continue
            if pname == "cot" and param.default is inspect.Parameter.empty:
                # Need COT data — check if available
                cot_path = BASE / "data" / "universe" / f"{sym}_COT.csv"
                if cot_path.exists():
                    extra_args["cot"] = pd.read_csv(cot_path)
                else:
                    return None
            elif pname == "fx" and param.default is inspect.Parameter.empty:
                return None  # FX data not available
            elif param.default is not inspect.Parameter.empty:
                pass  # Has default, will be used

        merged = {**params, **extra_args}
        sigs = list(func(df, **merged))
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
    """Run all hypotheses through backtest. No hardcoded family list."""
    hyp_file = BASE / "data" / "hypotheses" / "latest_external.json"
    if not hyp_file.exists():
        print("No latest_external.json. Run convert_to_hypotheses.py first.")
        return []

    hypotheses = json.loads(hyp_file.read_text(encoding="utf-8"))
    grid = build_grid_from_hypotheses(hypotheses)
    print(f"Running {len(grid)} test cells across {len(set(c['family'] for c in grid))} families...")

    # Print family distribution
    fam_counts = {}
    for c in grid:
        f = c["family"]
        fam_counts[f] = fam_counts.get(f, 0) + 1
    for f, n in sorted(fam_counts.items(), key=lambda x: -x[1]):
        print(f"  {f}: {n} cells")

    results = []
    t0 = time.time()
    for i, cell in enumerate(grid):
        r = run_cell(cell)
        if r:
            results.append(r)
            if r["exp_r"] > 0.05:
                print(f"  PASS {r['symbol']:8s}.{r['family']:30s} n={r['n']:4d} "
                      f"exp={r['exp_r']:+.4f}R maxDD={r['max_dd_r']:+.1f}R "
                      f"PF={r['profit_factor']:.2f}")
        if (i + 1) % 20 == 0:
            print(f"  [{i+1}/{len(grid)}] {time.time()-t0:.0f}s elapsed")

    elapsed = time.time() - t0
    out = BASE / "data" / "hypotheses" / "external_backtest_results.json"
    out.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")

    survivors = [r for r in results if r["exp_r"] > 0.05 and r["max_dd_r"] > -30]

    # Count by family
    surv_fams = {}
    for s in survivors:
        f = s["family"]
        surv_fams[f] = surv_fams.get(f, 0) + 1

    print(f"\n{len(results)} cells tested, {len(survivors)} survivors in {elapsed:.0f}s")
    print(f"Survivors across {len(surv_fams)} distinct families:")
    for f, n in sorted(surv_fams.items(), key=lambda x: -x[1]):
        print(f"  {f}: {n}")

    for s in sorted(survivors, key=lambda x: -x["exp_r"]):
        print(f"  {s['symbol']:8s} {s['family']:30s} n={s['n']:4d} exp={s['exp_r']:+.4f}R "
              f"maxDD={s['max_dd_r']:+.1f}R PF={s['profit_factor']:.2f}")

    # ONE PRODUCER PER FILE (2026-08-27, third offender found the same night): the merged
    # docket external_survivors.json is written by merge_hypotheses.py ALONE. This script's
    # direct write clobbered 3,339 merged candidates with its own [] at 02:26 -- run by a
    # resumed digger session, so the fix must live HERE, not in any scheduler. Survivors are
    # returned to the caller and land in this script's own results file; merge folds them in.
    return survivors


if __name__ == "__main__":
    run_all()
