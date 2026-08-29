"""BRAIN HUNTER s27c (2026-08-29) -- one population for the whole grid, or no comparison.

s27b fixed the guard and the k-curve turned over. But its `n_fixed` moves with BOTH axes
(ward k=24 scores 240 symbols, k=224 scores 28), so every cross-cell comparison in it --
including "average beats ward at k=128" and "the peak is at k=128" -- is a comparison of
numbers computed on DIFFERENT POPULATIONS. That is the same defect s27 just found in the
guard, one level up, and it is the defect s25 was corrected for.

Here every arm and every control is scored on ONE population: the symbols that are
non-singleton in EVERY (method, k) cell and in EVERY eval year. k=192+ is excluded from the
grid because its retained sets are small enough (27-28) to collapse the common set for
everyone else -- an exclusion stated, not silently applied (L1.28a).

Run: .venv/bin/python data/brain_hunter_s27c_common_population.py
"""
from __future__ import annotations

import json
import pathlib

import numpy as np
from brain_hunter_s27_exact_control import EVAL, build_panel, cluster_year
from brain_hunter_s27b_kcurve_fixed import rank_frames, score

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data/brain_hunter_s27c_common_population.json"

KS = [24, 48, 96, 128, 160]
METHODS = ["ward", "average", "complete"]
RANDOM_DRAWS = 8
SEED = 20260829


def main() -> None:
    panel = build_panel()
    ev = panel[(panel.index.year >= EVAL[0]) & (panel.index.year <= EVAL[-1])]
    cells: dict[tuple[str, int], tuple[dict[str, dict[str, str]], object, object,
                                       dict[int, set[str]]]] = {}
    retained_sets: list[set[str]] = []
    for method in METHODS:
        for k in KS:
            by_year = {}
            for y in range(EVAL[0], EVAL[-1] + 1):
                m = cluster_year(panel, y - 1, k, method)
                if m:
                    by_year[str(y)] = m
            if len(by_year) < 2:
                continue
            uw, gr, ret = rank_frames(ev, by_year)
            if uw is None:
                continue
            cells[(method, k)] = (by_year, uw, gr, ret)
            retained_sets.extend(ret.values())
    common = sorted(set.intersection(*retained_sets))
    print(f"common population: {len(common)} symbols across {len(cells)} cells", flush=True)

    rows = []
    for (method, k), (by_year, uw, gr, _ret) in cells.items():
        real, n_real = score(uw, gr, common)
        rng = np.random.default_rng(SEED)
        ctrl, ns = [], []
        for _ in range(RANDOM_DRAWS):
            u2, g2, _ = rank_frames(ev, by_year, rng=rng)
            v, nv = score(u2, g2, common)
            if np.isfinite(v):
                ctrl.append(v)
                ns.append(nv)
        mu, sd = float(np.mean(ctrl)), float(np.std(ctrl, ddof=1))
        rows.append({
            "method": method, "k": k, "n_scored_real": n_real,
            "n_scored_control_mean": round(float(np.mean(ns)), 1),
            "real": round(real, 4), "control": round(mu, 4),
            "content": round(mu - real, 4),
            "z": round((real - mu) / sd, 1) if sd > 0 else None,
        })
        r = rows[-1]
        print(f"{method:9s} k={k:4d} n={n_real:3d}/{r['n_scored_control_mean']:5.1f} "
              f"real={real:.4f} ctrl={mu:.4f} content={r['content']:+.4f} z={r['z']}", flush=True)

    best = max(rows, key=lambda r: float(r["content"]))  # type: ignore[arg-type]
    OUT.write_text(json.dumps({
        "built_at": "2026-08-29", "built_by": "BRAIN HUNTER s27c",
        "question": "on ONE population, which (method, k) grouping carries the most content?",
        "population_definition": "symbols non-singleton in every cell of the grid and every "
                                  "eval year",
        "population_size": len(common), "population_symbols": common,
        "grid_methods": METHODS, "grid_ks": KS,
        "excluded": "k>=192: retained sets of 27-28 symbols collapse the common population",
        "eval_years": list(EVAL), "random_draws": RANDOM_DRAWS, "seed": SEED,
        "best": best, "rows": rows,
    }, indent=1) + "\n")
    print(f"BEST {best}\nwrote {OUT}")


if __name__ == "__main__":
    main()
