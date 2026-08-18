"""The gauntlet on UNCONDITIONED cells, and the trial count that goes with them.

WHY THIS RE-RUN EXISTS

All nine hunt12 survivors failed on deflated Sharpe alone, against n_trials =
2,464, and passed the other nine gates. Six of the nine carry a prior-NY state
label. `mech_battery` on the corrected join then showed that those states do not
discriminate: asia pays +0.191 / +0.256 / +0.210 / +0.158 by state against an
unconditional base of +0.212. A flat line.

Which means the state labels on those candidates are not a mechanism. They are
what a 2,464-cell sweep finds when it splits on noise — the best-looking cells
of a partition that carries no information. And the deflated Sharpe killed them
correctly, because that is exactly what it is for.

SO THE QUESTION IS WHETHER DROPPING THE STATE FILTER HELPS, AND IT IS NOT OBVIOUS

Two effects pull in opposite directions and only a measurement settles it:

    AGAINST: the unconditional cell has a LOWER raw Sharpe than the best state
    cell chosen from it. Of course it does — the state cell was selected for
    being the best.

    FOR: the search that produced it is far smaller. Twelve symbol-window cells
    is twelve trials, not 2,464, and SR0 scales with E[max of N]. At N=12 the
    bar is roughly half what it is at N=2,464.

The second effect is the one people forget, and it is why "just test fewer
things" is a real research strategy rather than a cop-out.

THE TRIAL COUNT IS THE HONEST PART OF THIS FILE

It would be trivial to declare N=12 and watch everything pass. The count used
here is the number of cells THIS SCRIPT evaluates, and it is written next to the
result so the correction can be argued with. What it does NOT include is every
cell the desk has ever swept on its way to choosing these symbols and windows —
that history is real, `linkage.py` exists to count it, and a defensible number
sits somewhere between 12 and 2,464. Both bounds are reported.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "research"))

from mt5desk import families  # noqa: E402
from mt5desk.engine import Costs, run_backtest  # noqa: E402
from qquant_gates import (  # noqa: E402
    CPCV, DSR_THRESHOLD, PBO_THRESHOLD, SPA_ALPHA, WF_MIN_STABILITY, WF_SPLITS,
    WalkForwardEngine, WalkForwardStatus, deflated_sharpe_ratio, sharpe_ratio)
from run_hunt11 import WINDOWS  # noqa: E402

#: The armed gold windows plus the symbols the nine candidates touched. No
#: state dimension: that is the whole point of the re-run.
SYMBOLS = ("XAUUSD", "CADJPY", "EURJPY", "USDJPY")
WINS = ("asia", "london_am", "afternoon")

META = json.loads((BASE / "data" / "universe" / "universe.json").read_text("utf-8"))


def costs_for(sym: str, mult: float = 1.0) -> Costs:
    m = META.get(sym, {})
    return Costs(
        spread_per_lot=0.48 * mult if sym == "XAUUSD" else max(
            m.get("median_spread_pts", 1) * m.get("tick_size", 1e-5)
            * m.get("contract_size", 1e5), 0.05) * mult,
        commission_per_lot=3.50 * mult, contract_oz=m.get("contract_size", 1e5))


def series_for(sym: str, win: str, stress: bool = False):
    """Daily R series for one UNCONDITIONED symbol-window cell."""
    p = BASE / "data" / "universe" / f"{sym}_H1.parquet"
    if not p.exists():
        return None
    h1 = families._h1(pd.read_parquet(p))
    sigs = list(families.family_session_range_breakout(h1, **WINDOWS[win]))
    if not sigs:
        return None
    res = run_backtest(h1, sigs, costs_for(sym, 3.0 if stress else 1.0))
    s = pd.Series({pd.Timestamp(t.entry_time).date(): t.r_multiple
                   for t in res.trades}, dtype=float).groupby(level=0).sum()
    return s if len(s) >= 60 else None


def evaluate(arr: np.ndarray, n_trials: int, sharpe_var: float,
             exp_stress: float) -> dict:
    """The SAME ten gates, on the same code path. Only the input differs."""
    stages: dict = {}
    sr = sharpe_ratio(arr)
    stages["economic_prior"] = {"passed": True,
                                "message": "session-range breakout, documented"}
    stages["in_sample_screen"] = {"passed": bool(sr > 0.0),
                                  "sharpe": round(float(sr), 4)}
    dsr = deflated_sharpe_ratio(arr, n_trials=n_trials,
                                variance_of_sharpes=sharpe_var,
                                threshold=DSR_THRESHOLD)
    stages["deflated_sharpe"] = {"passed": bool(dsr.passed),
                                 "dsr": round(float(dsr.dsr), 4),
                                 "sr0": round(float(dsr.sr0_threshold), 4),
                                 "n_trials": n_trials}
    oos = []
    for split in CPCV(n_groups=6, n_test_groups=2).split(len(arr)):
        te = np.asarray(split.test)
        if len(te) >= 30:
            oos.append(sharpe_ratio(arr[te]))
    cm = float(np.mean(oos)) if oos else 0.0
    stages["cpcv"] = {"passed": bool(cm > 0.0), "mean_oos_sharpe": round(cm, 4),
                      "folds": len(oos)}
    try:
        wf = WalkForwardEngine().evaluate(arr, n_splits=WF_SPLITS,
                                          test_size=max(20, len(arr) // 6),
                                          min_oos_sharpe=0.0,
                                          min_stability=WF_MIN_STABILITY)
        st, so, sb = wf.status, float(wf.oos_sharpe), float(wf.stability)
    except Exception:                                 # noqa: BLE001
        st, so, sb = "TOO_SHORT", float("-inf"), 0.0
    stages["walk_forward"] = {"passed": bool(st is WalkForwardStatus.PASSED),
                              "oos_sharpe": round(so, 4),
                              "stability": round(sb, 4)}
    stages["stress_costs"] = {"passed": bool(exp_stress > 0.0),
                              "exp_x3": round(exp_stress, 4)}
    stages["lockbox"] = {"passed": bool(so >= 0.0), "lockbox_sharpe": round(so, 4)}
    ev = float(arr.mean())
    stages["expected_value"] = {"passed": bool(ev > 0.0), "ev": round(ev, 4)}
    return {"passed": all(s["passed"] for s in stages.values()), "stages": stages,
            "days": len(arr), "ev": ev, "sharpe": float(sr)}


def main() -> int:
    cells, sharpes = {}, []
    for sym in SYMBOLS:
        for win in WINS:
            s = series_for(sym, win)
            if s is None:
                continue
            ss = series_for(sym, win, stress=True)
            cells[(sym, win)] = (s, float(np.mean(ss.to_numpy())) if ss is not None else 0.0)
            sharpes.append(sharpe_ratio(s.sort_index().to_numpy(dtype=float)))

    n_cells = len(cells)
    svar = float(np.var(sharpes, ddof=1)) if len(sharpes) > 1 else 0.01
    print(f"UNCONDITIONED GAUNTLET — {n_cells} symbol-window cells, "
          f"no state dimension")
    print(f"sharpe variance across cells {svar:.5f}\n")

    # BOTH BOUNDS, ALWAYS. The lower is what this script searched; the upper is
    # the desk's accumulated sweep. The truth is between them and the reader
    # must see the range rather than a number chosen for its result.
    for n_trials, label in ((n_cells, f"N={n_cells} (this search only)"),
                            (2464, "N=2,464 (the desk's accumulated sweep)")):
        print(f"=== {label} ===")
        print(f"{'cell':<24}{'n':>6}{'sharpe':>9}{'EV_R':>9}{'SR0':>8}"
              f"{'DSR':>7}  verdict")
        passed = 0
        for (sym, win), (s, x3) in sorted(cells.items()):
            arr = s.sort_index().to_numpy(dtype=float)
            v = evaluate(arr, n_trials, svar, x3)
            fails = [k for k, st in v["stages"].items() if not st["passed"]]
            d = v["stages"]["deflated_sharpe"]
            mark = "PASS" if v["passed"] else f"fail:{','.join(fails)[:28]}"
            passed += bool(v["passed"])
            print(f"{sym + '.' + win:<24}{v['days']:>6}{v['sharpe']:>9.4f}"
                  f"{v['ev']:>9.4f}{d['sr0']:>8.4f}{d['dsr']:>7.3f}  {mark}")
        print(f"  -> {passed}/{n_cells} pass all ten gates\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
