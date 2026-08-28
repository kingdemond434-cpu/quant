"""Run external discovery hypotheses through the backtest pipeline.
Reads test_grid.json, runs each cell, saves results + survivors.
"""
from __future__ import annotations

import inspect
import json
import sys
import time
import warnings

warnings.filterwarnings("ignore")

from pathlib import Path  # noqa: E402

import pandas as pd  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "research"))

from mt5desk import families  # noqa: E402
from mt5desk.engine import Costs, run_backtest  # noqa: E402

_h1_cache: dict = {}
_uni = json.loads((BASE / "data" / "universe" / "universe.json").read_text("utf-8"))

def _family_funcs() -> dict:
    """EVERY registered family, discovered -- never a hand-typed whitelist.

    This was a frozen list of EIGHT names while FAMILY_REGISTRY auto-registers every family_*
    function and families_orthogonal adds fifteen more. A hypothesis naming carry, cot
    positioning, cross-asset residual, gap decay or anything else simply returned None here and
    vanished: the stage reported "cells tested" while whole mechanism classes were unreachable
    from this door (principal 2026-08-28: "no hardcoded exclusion stuck to certain families or
    trading types"). Discovery costs nothing and a family added tomorrow is testable today.
    """
    funcs: dict = {}
    for name in dir(families):
        if name.startswith("family_"):
            fn = getattr(families, name, None)
            if callable(fn):
                funcs[name[len("family_"):]] = fn
    try:
        from mt5desk import families_orthogonal as _fo
        funcs.update(dict(_fo.ORTHOGONAL_FAMILIES))
    except ImportError:
        pass
    return funcs


FAMILY_FUNCS = _family_funcs()


def normalize_grid(grid: list[dict]) -> tuple[list[dict], int]:
    """Keep only executable family parameters and collapse identities made equal by repair."""
    normalized: list[dict] = []
    seen: set[str] = set()
    removed = 0
    for cell in grid:
        func = FAMILY_FUNCS.get(cell.get("family"))
        if func is None:
            continue
        signature = inspect.signature(func)
        accepts_kwargs = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in signature.parameters.values()
        )
        raw = dict(cell.get("params") or {})
        legal = raw if accepts_kwargs else {k: v for k, v in raw.items()
                                             if k in signature.parameters}
        removed += len(raw) - len(legal)
        repaired = {**cell, "params": legal}
        identity = json.dumps({k: repaired.get(k) for k in ("symbol", "family", "params")},
                              sort_keys=True, default=str)
        if identity in seen:
            continue
        seen.add(identity)
        normalized.append(repaired)
    return normalized, removed


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
    raw_grid = json.loads(grid_file.read_text(encoding="utf-8"))
    grid, removed = normalize_grid(raw_grid)
    print(f"Running {len(grid)} executable test cells ({len(raw_grid)} submitted; "
          f"{removed} unsupported parameter occurrence(s) removed)...")

    results = []
    t0 = time.time()
    for i, cell in enumerate(grid):
        r = run_cell(cell)
        if r:
            results.append(r)
            if r["exp_r"] > 0.05:
                print(f"  PASS {r['symbol']:8s}.{r['family']:25s} n={r['n']:4d} "
                      f"exp={r['exp_r']:+.4f}R maxDD={r['max_dd_r']:+.1f}R "
                      f"PF={r['profit_factor']:.2f}")
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

    # ONE PRODUCER PER FILE. This used to ALSO write external_survivors.json directly, which
    # clobbered the merged docket with just this stage's rows at :06 every hour -- measured
    # 2026-08-27: the 00:47 merge shipped 122 candidates, stage 2 overwrote them with its own
    # 0 stage-A passes at 01:06, and the docket sat empty until the next merge. Merge
    # (merge_hypotheses.py) is the only writer of external_survivors.json; this stage's product
    # is external_backtest_results.json above, which merge consumes like every other source.
    return survivors


if __name__ == "__main__":
    run_all()
