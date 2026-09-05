"""BRAIN HUNTER s29 (2026-08-29) -- s28's named next ground #1, run as a PRE-REGISTERED test.

s28 read a MECHANISM CLAIM off six cells: "cluster neutralisation HELPS
reversal/dispersion features and HURTS trend features" (ward_k24 vs universe:
reversal_1 +, lowvol_20 +, accel +; mom_5 -, mom_20 -, mom_60 - at z=-7.8).
Six cells is where a rule is BORN, never where it is confirmed -- the split was
chosen after seeing the numbers, which is exactly the garden of forking paths.

THIS RUN TESTS IT ON SIX FEATURES S28 NEVER SAW, with the side declared BEFORE
the run (see PREDICT below, and it is written into the artifact verbatim):

  TREND arm      (predict neutralisation HURTS: delta = ward_k24 - universe < 0)
      mom_120, mom_250, mom_60_skip5
  DISPERSION arm (predict neutralisation HELPS: delta > 0)
      reversal_5, lowvol_60, absret_20

The falsifier is stated and it is strict: the rule SURVIVES only if all six deltas
carry their predicted sign. 5/6 or fewer is a REFUTATION of the rule as stated --
a 6-cell coin-flip lands 6/6 with probability 1/64, so anything less is not
evidence a rule exists, it is evidence s28 described its own sample.

Every cell also runs the s27 EXACT control (labels permuted AFTER member
restriction) so a delta cannot be credited to the mere ACT of grouping.

NO BAR IS APPLIED (L1.60). This screen sorts and reports; the ten gates decide.
Every trial is reported, winners and losers, with n beside every number.

Run: .venv/bin/python data/brain_hunter_s29_neutraliser_rule.py
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
OUT = ROOT / "data/brain_hunter_s29_neutraliser_rule.json"
RANDOM_DRAWS = 8

# PRE-REGISTERED, written before the first number was produced.
PREDICT = {
    "mom_120":     ("trend",      "negative"),
    "mom_250":     ("trend",      "negative"),
    "mom_60_skip5":("trend",      "negative"),
    "reversal_5":  ("dispersion", "positive"),
    "lowvol_60":   ("dispersion", "positive"),
    "absret_20":   ("dispersion", "positive"),
}


def features(panel: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """All PIT: value at t uses returns up to and including t, applied to t+1's return."""
    r = panel
    absr = r.abs()
    return {
        "mom_120": _roll(r, 120, "sum"),
        "mom_250": _roll(r, 250, "sum"),
        # classic skip-the-last-week momentum: the trend without the reversal tail
        "mom_60_skip5": _roll(r, 60, "sum") - _roll(r, 5, "sum"),
        "reversal_5": -_roll(r, 5, "sum"),
        "lowvol_60": -_roll(r, 60, "std"),
        # dispersion in level, not in second moment: low mean |return| = quiet name
        "absret_20": -_roll(absr, 20, "sum"),
    }


def main() -> None:
    gm = json.loads(GMAP.read_text())
    panel = build_panel()
    fwd = panel.shift(-1)
    feats = features(panel)
    cells: dict[str, Any] = {}
    verdicts: dict[str, Any] = {}
    trials = 0
    for fname, f in feats.items():
        side, pred = PREDICT[fname]
        row: dict[str, Any] = {}
        for arm in ("universe", "ward_k24", "asset_class", "currency_quote"):
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
        cells[fname] = row

        u, w = row["universe"], row["ward_k24"]
        if isinstance(u, dict) and "sharpe_gross" in u and "sharpe_gross" in w:
            delta = round(w["sharpe_gross"] - u["sharpe_gross"], 3)
            got = "positive" if delta > 0 else ("negative" if delta < 0 else "zero")
            vs_ctrl = (round(w["sharpe_gross"] - float(np.mean(ctrl)), 3)
                       if ctrl else None)
            z_ctrl = None
            if len(ctrl) > 1 and np.std(ctrl, ddof=1) > 0:
                z_ctrl = round((w["sharpe_gross"] - float(np.mean(ctrl)))
                               / float(np.std(ctrl, ddof=1)), 2)
            verdicts[fname] = {
                "side": side, "predicted": pred, "observed": got,
                "delta_ward_minus_universe": delta,
                "sharpe_universe": u["sharpe_gross"], "sharpe_ward_k24": w["sharpe_gross"],
                "mean_names_universe": u["mean_names"], "mean_names_ward": w["mean_names"],
                "days": w["days"],
                "delta_vs_exact_random_control": vs_ctrl, "z_vs_random_control": z_ctrl,
                "prediction_held": got == pred,
            }
        else:
            verdicts[fname] = {"side": side, "predicted": pred,
                               "observed": "UNMEASURED", "prediction_held": None}

    held = [k for k, v in verdicts.items() if v.get("prediction_held") is True]
    failed = [k for k, v in verdicts.items() if v.get("prediction_held") is False]
    unmeasured = [k for k, v in verdicts.items() if v.get("prediction_held") is None]
    n_scored = len(held) + len(failed)
    rule = ("SURVIVES" if n_scored == 6 and not failed
            else "REFUTED" if n_scored >= 4
            else "UNMEASURED")
    out = {
        "session": "brain_hunter_s29", "date": "2026-08-29",
        "tests": ("s28's per-feature neutraliser rule, on six features s28 never saw, "
                  "with the side pre-registered before the run"),
        "preregistered_prediction": {k: {"side": v[0], "delta_sign": v[1]}
                                     for k, v in PREDICT.items()},
        "falsifier": ("rule survives ONLY at 6/6 predicted signs; a coin flip reaches 6/6 "
                      "with p=1/64, so <=5/6 is a refutation of the rule AS STATED"),
        "eval_years": list(EVAL_YEARS), "min_names": MIN_NAMES, "trials_run": trials,
        "multiplicity_note": ("every cell tried is reported, winners and losers; no bar "
                              "applied here (L1.60) -- trial count is handed to the gauntlet"),
        "verdict": {"rule": rule, "held": held, "failed": failed,
                    "unmeasured": unmeasured, "score": f"{len(held)}/{n_scored}"},
        "per_feature": verdicts,
        "cells": cells,
    }
    OUT.write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"verdict": out["verdict"], "per_feature": verdicts}, indent=1))


if __name__ == "__main__":
    main()
