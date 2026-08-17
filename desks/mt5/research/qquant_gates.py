"""QQUANT UNIVERSAL GATES — the original qquant platform validation stack, applied
verbatim to the MT5 hunt survivors.

Uses the EXACT implementations from C:\\Users\\dell\\quant-platform\\libs\\validation
(dsr, pbo/CSCV, reality_check/hansen_spa, cpcv, revalidation/WalkForwardEngine).
Run under the quant-platform venv python.

Gate order (gauntlet.py + run_campaign.py):
  1 economic_prior     - mechanism documented (every MT5 family has a registered rationale)
  2 in_sample_screen   - Sharpe > 0
  3 deflated_sharpe    - DSR >= 0.95, n_trials = max(2, ceil(cells_tested * 7.0))  [trials ledger x7]
  4 pbo                - CSCV PBO <= 0.5
  5 reality_check_spa  - Hansen SPA p < 0.05
  6 cpcv               - CPCV mean OOS Sharpe > 0 (purge + embargo)
  7 walk_forward       - WalkForwardEngine: 4 splits, test_size = len//6, min_oos_sharpe 0,
                         min_stability 0.5
  8 stress_costs       - X3 cost scenario: expected R at 3x costs > 0
  9 lockbox            - wf OOS Sharpe >= 0 (holdout proxy)
 10 expected_value     - mean daily R > 0 (explicit EV gate)

REAL3 = REAL && all 10 gates pass.

Output: reports/QQUANT_GATES.json (per-survivor verdicts). The merge of REAL3 into
REAL_SURVIVORS.json is done by merge_qquant.py after fragility.py completes.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
REPORTS = BASE / "reports"
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "research"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # quant repo root: libs/validation lives there

from libs.validation.cpcv import CPCV  # noqa: E402
from libs.validation.dsr import deflated_sharpe_ratio, sharpe_ratio  # noqa: E402
from libs.validation.pbo import probability_backtest_overfitting  # noqa: E402
from libs.validation.reality_check import hansen_spa  # noqa: E402
from libs.validation.revalidation import WalkForwardEngine, WalkForwardStatus  # noqa: E402

from mt5desk import families  # noqa: E402
from mt5desk.engine import Costs, run_backtest  # noqa: E402

TRIALS_MULTIPLIER = 7.0
DSR_THRESHOLD = 0.95
PBO_THRESHOLD = 0.5
SPA_ALPHA = 0.05
WF_SPLITS = 4
WF_MIN_STABILITY = 0.5
COST_SCENARIO = 3.0  # X3


def main() -> int:
    from run_hunt12 import WINDOWS as W12, day_states  # noqa
    from run_hunt16 import WINDOWS as W16, FAMILIES as F16  # noqa

    sv = json.loads((REPORTS / "REAL_SURVIVORS.json").read_text("utf-8"))
    meta = json.loads((BASE / "data" / "universe" / "universe.json").read_text("utf-8"))
    h12 = json.loads((REPORTS / "hunt12.json").read_text("utf-8"))
    h16 = json.loads((REPORTS / "hunt16.json").read_text("utf-8"))
    all12 = h12.get("all", [])
    all16 = h16.get("all", [])
    n_cells = {12: len(all12), 16: len(all16)}

    h1_cache: dict[str, pd.DataFrame] = {}
    daily_cache: dict[str, pd.Series] = {}
    CACHE_PKL = REPORTS / "qquant_cache.pkl"

    def save_cache() -> None:
        tmp = REPORTS / "qquant_cache.tmp.pkl"
        pd.to_pickle({"daily": daily_cache, "h1": {k: v.to_dict() for k, v in h1_cache.items()}},
                     tmp)
        tmp.replace(CACHE_PKL)

    if CACHE_PKL.exists():
        try:
            saved = pd.read_pickle(CACHE_PKL)
            daily_cache.update(saved.get("daily", {}))
            for k, v in saved.get("h1", {}).items():
                h1_cache[k] = pd.DataFrame(v)
            print(f"resumed from cache: {len(daily_cache)} cell series", flush=True)
        except Exception as e:
            print(f"cache load failed ({e!r}), building fresh", flush=True)

    def symbol_h1(sym: str) -> pd.DataFrame:
        if sym not in h1_cache:
            h1_cache[sym] = families._h1(
                pd.read_parquet(BASE / "data" / "universe" / f"{sym}_H1.parquet"))
        return h1_cache[sym]

    def costs_for(sym: str, mult: float = 1.0) -> Costs:
        m = meta.get(sym, {})
        return Costs(
            spread_per_lot=0.48 * mult if sym == "XAUUSD" else max(
                m.get("median_spread_pts", 1) * m.get("tick_size", 1e-5) * m.get("contract_size", 1e5), 0.05) * mult,
            commission_per_lot=3.50 * mult, contract_oz=m.get("contract_size", 1e5))

    def cell_series(sym: str, hunt: int, fam, side: str, win: str, state: str) -> pd.Series:
        key = (sym, hunt, fam, side, win, state)
        if key in daily_cache:
            return daily_cache[key]
        h1 = symbol_h1(sym)
        states = day_states(h1)
        if hunt == 12:
            sigs = families.family_session_range_breakout(h1, **W12[win])
            sdays = [pd.Timestamp(s.time).date() for s in sigs]
        else:
            ffn = F16[fam]
            sday = W16[win].get("signal_at") or W16[win]["range_start"]
            sigs = [s for s in ffn(h1, 1 if side == "LONG" else -1) if s.time.hour == sday]
            sdays = [pd.Timestamp(s.time).date() for s in sigs]
        sub = [s for s, d in zip(sigs, sdays) if states.get(d) == state]
        res = run_backtest(h1, sub, costs_for(sym))
        series = pd.Series({pd.Timestamp(t.entry_time).date(): t.r_multiple for t in res.trades},
                           dtype=float)
        series = series.groupby(level=0).sum()
        daily_cache[key] = series
        return series

    def cell_series_stress(sym: str, hunt: int, fam, side: str, win: str, state: str) -> pd.Series:
        key = (sym, hunt, fam, side, win, state, "x3")
        if key in daily_cache:
            return daily_cache[key]
        h1 = symbol_h1(sym)
        states = day_states(h1)
        if hunt == 12:
            sigs = families.family_session_range_breakout(h1, **W12[win])
            sdays = [pd.Timestamp(s.time).date() for s in sigs]
        else:
            ffn = F16[fam]
            sday = W16[win].get("signal_at") or W16[win]["range_start"]
            sigs = [s for s in ffn(h1, 1 if side == "LONG" else -1) if s.time.hour == sday]
            sdays = [pd.Timestamp(s.time).date() for s in sigs]
        sub = [s for s, d in zip(sigs, sdays) if states.get(d) == state]
        res = run_backtest(h1, sub, costs_for(sym, COST_SCENARIO))
        series = pd.Series({pd.Timestamp(t.entry_time).date(): t.r_multiple for t in res.trades},
                           dtype=float)
        series = series.groupby(level=0).sum()
        daily_cache[key] = series
        return series

    def build_matrix(hunt: int) -> tuple[np.ndarray, list[dict]]:
        cells = all12 if hunt == 12 else all16
        cols: list[np.ndarray] = []
        col_meta: list[dict] = []
        for ci, c in enumerate(cells):
            fam = c.get("fam") or c.get("family")
            side = c.get("side") or "LONG"
            s = cell_series(c["sym"], hunt, fam, side, c["win"], c["state"])
            arr = s.to_numpy(float)
            if len(arr) < 60:
                continue
            cols.append(arr)
            col_meta.append(c)
            if ci % 40 == 39:
                save_cache()
                print(f"matrix hunt{hunt}: {ci + 1}/{len(cells)} cells "
                      f"({len(daily_cache)} cached)", flush=True)
        # An EMPTY family is not a zero-width matrix -- it is a family that was not swept.
        # np.column_stack on [] raises, and min() on [] raises, so both are surfaced as an
        # explicit empty result rather than a traceback that looks like a code fault.
        if not cols:
            return np.empty((0, 0)), []
        min_len = min(len(a) for a in cols)
        matrix = np.column_stack([a[-min_len:] for a in cols])
        return matrix, col_meta

    print("building trial matrices (hunt12, hunt16)...", flush=True)
    m12, cm12 = build_matrix(12)
    m16, cm16 = build_matrix(16)
    print(f"matrix hunt12: {m12.shape}  hunt16: {m16.shape}", flush=True)

    sharpes12 = np.array([sharpe_ratio(m12[:, k]) for k in range(m12.shape[1])])
    sharpes16 = np.array([sharpe_ratio(m16[:, k]) for k in range(m16.shape[1])])
    n_trials12 = max(2, math.ceil(n_cells[12] * TRIALS_MULTIPLIER))
    n_trials16 = max(2, math.ceil(n_cells[16] * TRIALS_MULTIPLIER))

    print("program-level: PBO + SPA on full trial matrices...", flush=True)
    pbo12 = probability_backtest_overfitting(m12)
    # hunt16 may be unswept (empty matrix). PBO/SPA on nothing is not "clean" -- it is
    # UNMEASURED, so it fails closed: pbo=1.0 and p=1.0 deny admission rather than granting it.
    class _NullStat:
        pbo = 1.0
        p_value = 1.0
    pbo16 = probability_backtest_overfitting(m16) if m16.size else _NullStat()
    spa12 = hansen_spa(m12)
    spa16 = hansen_spa(m16) if m16.size else _NullStat()
    print(f"hunt12 PBO={pbo12.pbo:.3f} SPA p={spa12.p_value:.3f} | "
          f"hunt16 PBO={pbo16.pbo:.3f} SPA p={spa16.p_value:.3f}", flush=True)

    rows = sv["real_survivors"]
    print(f"running the universal gauntlet on {len(rows)} REAL survivors...", flush=True)

    def eval_candidate(row: dict, matrix: np.ndarray, sharpes: np.ndarray,
                       n_trials: int, pbo_ok: bool, spa_p: float) -> dict:
        fam = row.get("fam")
        side = row.get("side") or "LONG"
        rets = cell_series(row["sym"], 12 if row["hunt"] == "hunt12.json" else 16,
                           fam, side, row["win"], row["state"])
        if len(rets) < 60:
            return {"error": f"series too short ({len(rets)})"}
        arr = rets.to_numpy(float)
        stages: dict[str, dict] = {}

        sr = sharpe_ratio(arr)
        stages["economic_prior"] = {"passed": True,
                                    "message": "mechanism documented at hunt registration"}
        stages["in_sample_screen"] = {"passed": bool(sr > 0.0), "sharpe": round(float(sr), 4)}
        dsr = deflated_sharpe_ratio(arr, n_trials=n_trials,
                                    variance_of_sharpes=float(sharpes.var(ddof=1)),
                                    threshold=DSR_THRESHOLD)
        stages["deflated_sharpe"] = {"passed": bool(dsr.passed), "dsr": round(float(dsr.dsr), 4),
                                     "sr0": round(float(dsr.sr0_threshold), 4), "n_trials": n_trials}
        stages["pbo"] = {"passed": bool(pbo_ok), "pbo": round(float(pbo12.pbo if row["hunt"] == "hunt12.json" else pbo16.pbo), 4)}
        stages["reality_check_spa"] = {"passed": bool(spa_p < SPA_ALPHA), "p_value": round(float(spa_p), 4)}
        cpcv = CPCV(n_groups=6, n_test_groups=2)
        oos_sharpes = []
        for split in cpcv.split(len(arr)):
            te_idx = np.asarray(split.test)
            if len(te_idx) < 30:
                continue
            oos_sharpes.append(sharpe_ratio(arr[te_idx]))
        cpcv_mean = float(np.mean(oos_sharpes)) if oos_sharpes else 0.0
        stages["cpcv"] = {"passed": bool(cpcv_mean > 0.0), "mean_oos_sharpe": round(cpcv_mean, 4),
                          "folds": len(oos_sharpes)}
        wf = WalkForwardEngine().evaluate(arr, n_splits=WF_SPLITS,
                                          test_size=max(20, len(arr) // 6),
                                          min_oos_sharpe=0.0, min_stability=WF_MIN_STABILITY)
        stages["walk_forward"] = {"passed": bool(wf.status is WalkForwardStatus.PASSED),
                                  "oos_sharpe": round(float(wf.oos_sharpe), 4),
                                  "stability": round(float(wf.stability), 4)}
        sx = cell_series_stress(row["sym"], 12 if row["hunt"] == "hunt12.json" else 16,
                                fam, side, row["win"], row["state"])
        exp3 = float(sx.mean()) if len(sx) else 0.0
        stages["stress_costs"] = {"passed": bool(exp3 > 0.0), "exp_x3": round(exp3, 4)}
        stages["lockbox"] = {"passed": bool(float(wf.oos_sharpe) >= 0.0),
                             "lockbox_sharpe": round(float(wf.oos_sharpe), 4)}
        ev = float(arr.mean())
        stages["expected_value"] = {"passed": bool(ev > 0.0), "ev": round(ev, 4)}
        passed = all(s["passed"] for s in stages.values())
        return {"passed": passed, "stages": stages, "days": len(arr)}

    verdicts = []
    for r in rows:
        hunt = r["hunt"]
        if hunt == "hunt12.json":
            ev = eval_candidate(r, m12, sharpes12, n_trials12,
                                bool(pbo12.pbo <= PBO_THRESHOLD), float(spa12.p_value))
        else:
            ev = eval_candidate(r, m16, sharpes16, n_trials16,
                                bool(pbo16.pbo <= PBO_THRESHOLD), float(spa16.p_value))
        ev["id"] = f"{r['sym']} {r.get('fam') or 'breakout'} {r.get('side') or 'LONG'} {r['win']} {r['state']}"
        ev["hunt"] = hunt
        verdicts.append(ev)

    n_pass = sum(1 for v in verdicts if v.get("passed"))
    gate_fails: dict[str, int] = {}
    for v in verdicts:
        for name, s in v.get("stages", {}).items():
            if not s["passed"]:
                gate_fails[name] = gate_fails.get(name, 0) + 1
    out = {
        "n_trials": {"hunt12": n_trials12, "hunt16": n_trials16},
        "program_level": {
            "hunt12": {"pbo": round(float(pbo12.pbo), 4), "spa_p": round(float(spa12.p_value), 4)},
            "hunt16": {"pbo": round(float(pbo16.pbo), 4), "spa_p": round(float(spa16.p_value), 4)},
        },
        "gates": [n for n in ("economic_prior", "in_sample_screen", "deflated_sharpe", "pbo",
                              "reality_check_spa", "cpcv", "walk_forward", "stress_costs",
                              "lockbox", "expected_value")],
        "survivors_passing_all": n_pass,
        "survivors_total": len(verdicts),
        "gate_fails": gate_fails,
        "verdicts": verdicts,
        "swept_at": datetime.now(timezone.utc).isoformat(),
    }
    (REPORTS / "QQUANT_GATES.json").write_text(json.dumps(out, indent=2, default=str),
                                               encoding="utf-8")
    (REPORTS / "DONE_qquant_gates").write_text(
        datetime.now(timezone.utc).isoformat(), encoding="utf-8")
    print(f"\nUNIVERSAL GAUNTLET: {n_pass}/{len(verdicts)} survivors pass all 10 gates", flush=True)
    for name, cnt in sorted(gate_fails.items()):
        print(f"  gate fail [{name}]: {cnt}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())