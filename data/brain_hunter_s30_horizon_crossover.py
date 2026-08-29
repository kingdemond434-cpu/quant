"""BRAIN HUNTER s30 (2026-08-29) -- s29's named next ground #1, pre-registered.

s29 refuted s28's per-FEATURE neutraliser rule ("cluster neutralisation helps
dispersion, hurts trend") 5/6 -- and the single failure was informative rather
than noise: mom_250 came in at delta = +0.194 (z = +5.51 vs the exact control)
when the rule demanded a negative sign, while mom_120 held negative. That is not
a feature-family rule at all; it is a HORIZON claim with a crossover somewhere
between 120d and 250d.

THIS RUN TESTS THE HORIZON CLAIM DIRECTLY, on ONE feature family (mom_H = sum of
the last H daily log returns) so the family axis is held constant and only the
horizon moves. The sign of every scored cell is declared BELOW, before the first
number was produced:

    H =   5,  20,  60,  90, 120   ->  delta = ward_k24 - universe  NEGATIVE
    H = 180, 250, 300             ->  delta                        POSITIVE
    H = 150                       ->  UNPREDICTED (the crossover region itself;
                                      reported, never scored -- scoring the cell
                                      the hypothesis is silent about is exactly
                                      the forking path s29 was built to close)

FALSIFIER, strict and stated in advance: the horizon rule SURVIVES only at 8/8
predicted signs. A coin flip reaches 8/8 with p = 1/256. <= 7/8 REFUTES the rule
as stated; the observed pattern is then reported as a description of this sample,
never as a rule, which is precisely the error s28 made and s29 caught.

SECOND, INDEPENDENT CHECK -- monotonicity. The crossover story implies delta is
monotone non-decreasing in H. Spearman(H, delta) over the nine horizons is
reported alongside. A sign rule can hold while monotonicity fails (or vice
versa); both are reported, neither is allowed to rescue the other.

Every cell also runs the s27 EXACT control (labels permuted AFTER member
restriction) so no delta can be credited to the mere ACT of grouping.

NO BAR IS APPLIED (L1.60). This screen sorts and reports; the ten gates decide.
Every trial is reported, winners and losers, with n beside every number.

Run: .venv/bin/python data/brain_hunter_s30_horizon_crossover.py
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from brain_hunter_s27_exact_control import build_panel
from brain_hunter_s28_group_cells import _roll, run_cell, EVAL_YEARS, MIN_NAMES, SEED

ROOT = pathlib.Path(__file__).resolve().parents[1]
GMAP = ROOT / "data/mt5_grouping_map.json"
OUT = ROOT / "data/brain_hunter_s30_horizon_crossover.json"
RANDOM_DRAWS = 4

HORIZONS = [5, 20, 60, 90, 120, 150, 180, 250, 300]
# PRE-REGISTERED, written before the first number was produced. None = unscored.
PREDICT: dict[int, str | None] = {
    5: "negative", 20: "negative", 60: "negative", 90: "negative", 120: "negative",
    150: None,
    180: "positive", 250: "positive", 300: "positive",
}


def main() -> None:
    gm = json.loads(GMAP.read_text())
    panel = build_panel()
    fwd = panel.shift(-1)
    cells: dict[str, Any] = {}
    verdicts: dict[str, Any] = {}
    trials = 0
    for h in HORIZONS:
        f = _roll(panel, h, "sum")
        row: dict[str, Any] = {}
        for arm in ("universe", "ward_k24"):
            trials += 1
            res = run_cell(f, fwd, arm, gm, None)
            row[arm] = res if res else {"status": "UNMEASURED (too few bars)"}
        ctrl = []
        for i in range(RANDOM_DRAWS):
            trials += 1
            r = run_cell(f, fwd, "ward_k24", gm, np.random.default_rng(SEED + i))
            if r:
                ctrl.append(r["sharpe_gross"])
        row["random_k24"] = (
            {"draws": len(ctrl), "sharpe_mean": round(float(np.mean(ctrl)), 3),
             "sharpe_sd": round(float(np.std(ctrl, ddof=1)), 3) if len(ctrl) > 1 else None}
            if ctrl else {"status": "UNMEASURED"})
        cells[f"mom_{h}"] = row

        u, w = row["universe"], row["ward_k24"]
        if "sharpe_gross" in u and "sharpe_gross" in w:
            delta = round(w["sharpe_gross"] - u["sharpe_gross"], 3)
            got = "positive" if delta > 0 else ("negative" if delta < 0 else "zero")
            z_ctrl = None
            if len(ctrl) > 1 and np.std(ctrl, ddof=1) > 0:
                z_ctrl = round((w["sharpe_gross"] - float(np.mean(ctrl)))
                               / float(np.std(ctrl, ddof=1)), 2)
            pred = PREDICT[h]
            verdicts[f"mom_{h}"] = {
                "horizon_days": h, "predicted": pred, "observed": got,
                "scored": pred is not None,
                "delta_ward_minus_universe": delta,
                "sharpe_universe": u["sharpe_gross"], "sharpe_ward_k24": w["sharpe_gross"],
                "mean_names_universe": u["mean_names"], "mean_names_ward": w["mean_names"],
                "days": w["days"], "z_vs_random_control": z_ctrl,
                "prediction_held": None if pred is None else got == pred,
            }
        else:
            verdicts[f"mom_{h}"] = {"horizon_days": h, "predicted": PREDICT[h],
                                    "observed": "UNMEASURED", "prediction_held": None}

    scored = [v for v in verdicts.values() if v.get("scored")]
    held = [v["horizon_days"] for v in scored if v.get("prediction_held") is True]
    failed = [v["horizon_days"] for v in scored if v.get("prediction_held") is False]
    n_scored = len(held) + len(failed)
    rule = ("SURVIVES" if n_scored == 8 and not failed
            else "REFUTED" if n_scored >= 6 else "UNMEASURED")

    # independent monotonicity check over ALL nine horizons (incl. the unscored one)
    pairs = [(v["horizon_days"], v["delta_ward_minus_universe"]) for v in verdicts.values()
             if isinstance(v.get("delta_ward_minus_universe"), float)]
    spearman = None
    if len(pairs) >= 4:
        hs = pd.Series([p[0] for p in pairs]).rank()
        ds = pd.Series([p[1] for p in pairs]).rank()
        spearman = round(float(hs.corr(ds)), 3)

    out = {
        "session": "brain_hunter_s30", "date": "2026-08-29",
        "tests": ("s29's residual: is the ward-vs-universe neutralisation delta a HORIZON "
                  "effect with a single crossover, rather than a feature-family rule?"),
        "preregistered_prediction": {str(k): v for k, v in PREDICT.items()},
        "falsifier": ("rule survives ONLY at 8/8 predicted signs over the scored horizons; "
                      "a coin flip reaches 8/8 with p=1/256, so <=7/8 refutes it as stated. "
                      "H=150 is deliberately unscored -- the hypothesis is silent there."),
        "eval_years": list(EVAL_YEARS), "min_names": MIN_NAMES, "trials_run": trials,
        "multiplicity_note": ("every cell tried is reported, winners and losers; no bar "
                              "applied here (L1.60) -- trial count is handed to the gauntlet"),
        "verdict": {"rule": rule, "held": held, "failed": failed,
                    "score": f"{len(held)}/{n_scored}",
                    "spearman_horizon_vs_delta": spearman,
                    "monotonicity_note": ("Spearman over all nine horizons incl. the unscored "
                                          "one; a sign rule and monotonicity are separate "
                                          "claims and neither rescues the other")},
        "per_horizon": verdicts,
        "cells": cells,
    }
    OUT.write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"verdict": out["verdict"], "per_horizon": verdicts}, indent=1))


if __name__ == "__main__":
    main()
