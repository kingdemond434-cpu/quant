"""BRAIN HUNTER s30c (2026-08-29) -- s29's named next ground #2, run.

s29b refuted coarse ranking as a turnover lever and LOCALISED the constraint:
this family's turnover is a property of the FEATURE's autocorrelation, not of the
ranking operator. That points at exactly one identified lever -- smooth the
FEATURE -- and the BRAIN platform ships it as a first-class setting (`decay: 30`,
applied as `decay_linear`: a linear-weighted moving average over the last d values
of the alpha, weights d, d-1, ... 1).

This ports THAT operator (mechanism, not formula) onto the desk's own tape and
measures whether it is a real cost lever on `reversal_1`, the highest-turnover
cell in the family and the one s28 scored best gross.

PRE-REGISTERED before the first number:
  (a) MECHANICAL SANITY -- daily_turnover is strictly decreasing in d. If this
      fails the port is wrong, not the hypothesis, and the run is void.
  (b) THE SUBSTANTIVE CLAIM -- decay is a real cost lever for this family, i.e.
      break-even cost (bp_per_unit_turnover_to_zero, the round-trip bp that takes
      the cell to zero) is MAXIMISED at some d > 1.
  FALSIFIER: if break-even bp is maximised at d = 1 on the ward_k24 arm, the lever
      is REFUTED for this family and the only identified lever on the constraint
      that kills every cell in it is gone -- which is a result worth as much as a
      find, and is reported as one.

No random-label control is run here and the reason is stated rather than left to
inference: the question is about a COST lever within a fixed neutralisation arm,
not about whether grouping carries information. s27's exact control answers the
latter and s28-s30 already ran it on this family.

NO BAR IS APPLIED (L1.60). Every d tried is reported, winners and losers.

Run: .venv/bin/python data/brain_hunter_s30c_decay_lever.py
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
from brain_hunter_s28_group_cells import run_cell, EVAL_YEARS, MIN_NAMES

ROOT = pathlib.Path(__file__).resolve().parents[1]
GMAP = ROOT / "data/mt5_grouping_map.json"
OUT = ROOT / "data/brain_hunter_s30c_decay_lever.json"

DECAYS = [1, 2, 3, 5, 10, 20, 30]


def decay_linear(panel: pd.DataFrame, d: int) -> pd.DataFrame:
    """BRAIN's decay_linear, ported: linear-weighted MA of the last d values with
    weights d, d-1, ..., 1 (most recent heaviest), normalised to sum 1.

    Rolled over each symbol's OWN VALID OBSERVATIONS then reindexed -- the s28
    calendar bug (a union-calendar NaN annihilating the window for every symbol)
    applies to any rolling window, this one included.
    """
    if d <= 1:
        return panel
    wts = np.arange(d, 0, -1, dtype=float)
    wts /= wts.sum()
    out = {}
    for c in panel.columns:
        s = panel[c].dropna()
        out[c] = (s.rolling(d, min_periods=d)
                   .apply(lambda a: float(np.dot(a[::-1], wts)), raw=True)
                   .reindex(panel.index))
    return pd.DataFrame(out, index=panel.index)


def main() -> None:
    gm = json.loads(GMAP.read_text())
    panel = build_panel()
    fwd = panel.shift(-1)
    base = -panel                       # reversal_1, PIT: value at t applied to t+1
    cells: dict[str, Any] = {}
    trials = 0
    for d in DECAYS:
        f = decay_linear(base, d)
        row: dict[str, Any] = {}
        for arm in ("universe", "ward_k24"):
            trials += 1
            res = run_cell(f, fwd, arm, gm, None)
            row[arm] = res if res else {"status": "UNMEASURED (too few bars)"}
        cells[f"decay_{d}"] = row

    def series(arm: str, key: str) -> dict[int, float]:
        got = {}
        for d in DECAYS:
            v = cells[f"decay_{d}"][arm].get(key)
            if isinstance(v, (int, float)):
                got[d] = float(v)
        return got

    verdict: dict[str, Any] = {}
    for arm in ("universe", "ward_k24"):
        turn = series(arm, "daily_turnover")
        be = series(arm, "bp_per_unit_turnover_to_zero")
        ds = sorted(turn)
        mono = all(turn[a] > turn[b] for a, b in zip(ds, ds[1:])) if len(ds) > 1 else None
        best_d = max(be, key=lambda k: be[k]) if be else None
        verdict[arm] = {
            "turnover_by_d": {str(k): round(v, 3) for k, v in turn.items()},
            "breakeven_bp_by_d": {str(k): round(v, 3) for k, v in be.items()},
            "sharpe_gross_by_d": {str(k): v for k, v in series(arm, "sharpe_gross").items()},
            "turnover_strictly_decreasing_in_d": mono,
            "breakeven_maximised_at_d": best_d,
            "breakeven_gain_vs_d1": (round(be[best_d] - be[1], 3)
                                     if be and best_d is not None and 1 in be else None),
        }
    wk = verdict["ward_k24"]
    if wk["turnover_strictly_decreasing_in_d"] is False:
        call = "VOID (mechanical sanity check (a) failed -- the port is wrong, not the claim)"
    elif wk["breakeven_maximised_at_d"] is None:
        call = "UNMEASURED"
    elif wk["breakeven_maximised_at_d"] > 1:
        call = "LEVER SURVIVES on ward_k24"
    else:
        call = "REFUTED -- break-even bp is maximised at d=1; decay is not a cost lever here"

    out = {
        "session": "brain_hunter_s30c", "date": "2026-08-29",
        "tests": ("BRAIN's decay_linear ported as a MECHANISM and pointed at the constraint "
                  "s29b localised: is smoothing the FEATURE a real cost lever on reversal_1?"),
        "preregistered": {
            "a_mechanical": "daily_turnover strictly decreasing in d, else the run is VOID",
            "b_substantive": "break-even bp maximised at some d > 1 on the ward_k24 arm",
            "falsifier": "break-even bp maximised at d=1 REFUTES the lever for this family",
        },
        "eval_years": list(EVAL_YEARS), "min_names": MIN_NAMES,
        "decays_tried": DECAYS, "trials_run": trials,
        "multiplicity_note": ("every d tried is reported, winners and losers; no bar applied "
                              "here (L1.60) -- trial count is handed to the gauntlet"),
        "costs_note": ("sharpe_gross is BEFORE costs; bp_per_unit_turnover_to_zero is the "
                       "round-trip bp that takes the cell to zero, compared against real spread"),
        "verdict": {"call": call, **verdict},
        "cells": cells,
    }
    OUT.write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
    print(json.dumps(out["verdict"], indent=1))


if __name__ == "__main__":
    main()
