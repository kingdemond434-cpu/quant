"""pbo_cpcv: selection-bias audit over the hunt population.

PBO (Probability of Backtest Overfitting, Bailey & Lopez de Prado): how much of
the best IS performance is an artifact of picking the best of many tested
configurations? Computed by bootstrapping the tested population and measuring
how often the best-in-sample config's OOS performance is <= 0.

CPCV (Combinatorial Purged Cross-Validation, rough variant): we only have 3
walk-forward folds per cell, so CPCV is implemented as fold-combination
evaluation: for each config the 3 OOS folds are evaluated in all 2-of-3
combinations; report the distribution of OOS Sharpe and the probability that
the best-IS config lands in the top quartile OOS.

Inputs: reports/hunt12.json (all tested cells with exp, t, wf[]). Same logic
can be applied to hunt16.json when complete.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent.parent
REPORTS = BASE / "reports"


def sharpe_from_exp(exp: float, wf: list) -> float:
    """OOS Sharpe proxy from walk-forward fold expectancy (per-trade R)."""
    arr = np.array(wf, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan")
    return float(arr.mean() / (arr.std() + 1e-12)) if arr.std() > 0 else float("nan")


def run(hunt_file: str, out_file: str) -> dict:
    data = json.loads((REPORTS / hunt_file).read_text("utf-8"))
    cells = data.get("all", [])
    is_s = []
    oos_s = []
    wf_count = []
    for c in cells:
        wf = [float(x) for x in c.get("wf", []) if x == x]
        if not wf:
            continue
        is_s.append(float(c.get("t", 0.0)))
        oos_s.append(sharpe_from_exp(float(c.get("exp", 0.0)), wf))
        wf_count.append(len(wf))
    is_s = np.array(is_s)
    oos_s = np.array(oos_s)
    n = len(is_s)
    if n < 30 or not np.any(np.isfinite(is_s)):
        print(f"{hunt_file}: {n} cells with wf — too few for PBO, skipped", flush=True)
        return {"hunt": hunt_file, "cells_tested": int(n), "pbo": None,
                "note": "insufficient finite wf cells"}
    rng = np.random.default_rng(20260817)
    B = 1000
    best_is_idx = []
    best_oos = []
    for _ in range(B):
        idx = rng.choice(n, n, replace=True)
        b = idx[np.nanargmax(is_s[idx])]
        best_is_idx.append(b)
        best_oos.append(oos_s[b])
    best_oos = np.array(best_oos)
    obs_best = np.nanargmax(is_s)
    pbo = float(np.mean(best_oos <= 0.0))
    cpcv = {}
    if max(wf_count) >= 3:
        oos_means = {}
        for i, c in enumerate(cells):
            wf = [float(x) for x in c.get("wf", []) if x == x]
            if len(wf) >= 2:
                combos = [[0, 1], [0, 2], [1, 2]][: len(wf)]
                for combo in combos:
                    if max(combo) >= len(wf):
                        continue
                    mean_o = float(np.mean([wf[j] for j in combo]))
                    oos_means.setdefault(i, []).append(mean_o)
        flat = []
        for k, v in oos_means.items():
            flat.extend(v)
        flat = np.array(flat)
        cpcv = {
            "oos_fold_means_tested": int(len(oos_means)),
            "mean_oos_exp_all_fold_combos": round(float(flat.mean()), 3),
            "frac_combos_below_zero": round(float(np.mean(flat <= 0)), 3),
            "best_is_rank_quartile_oos": None,
        }
        top_is = np.argsort(is_s)[::-1][: max(1, n // 10)]
        ranks = []
        for i in top_is:
            if i in oos_means:
                m = np.mean(oos_means[i])
                ranks.append(float(np.mean([m >= np.mean(v) for v in oos_means.values()])))
        if ranks:
            cpcv["best_is_rank_quartile_oos"] = round(float(np.mean(ranks)), 3)
    out = {
        "hunt": hunt_file,
        "cells_tested": int(n),
        "survivors": int(len(data.get("survivors", []))),
        "pbo": round(pbo, 4),
        "pbo_interpretation": ("PBO<0.05: best-IS config reliably beats the null OOS; "
                               "PBO>0.30: search selection dominates, treat survivors with suspicion"),
        "observed_best_is_t": round(float(is_s[obs_best]), 2),
        "observed_best_oos_sharpe": round(float(oos_s[obs_best]), 3),
        "median_oos_sharpe_all_tested": round(float(np.nanmedian(oos_s)), 3),
        "frac_tested_oos_positive": round(float(np.nanmean(oos_s > 0)), 3),
        "cpcv": cpcv,
        "swept_at": datetime.now(timezone.utc).isoformat(),
    }
    (REPORTS / out_file).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"{out_file}: PBO={out['pbo']} best_IS_t={out['observed_best_is_t']} "
          f"best_OOS_sharpe={out['observed_best_oos_sharpe']} "
          f"median_OOS={out['median_oos_sharpe_all_tested']}", flush=True)
    return out


if __name__ == "__main__":
    for hf in ["hunt12.json", "hunt13.json", "hunt15.json", "hunt16.json"]:
        if not (REPORTS / hf).exists():
            print(f"{hf}: not present yet", flush=True)
            continue
        if (REPORTS / hf.replace(".json", "").replace("hunt", "DONE_hunt")).exists() or True:
            run(hf, f"pbo_cpcv_{hf}")