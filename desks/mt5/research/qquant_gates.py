"""QQUANT UNIVERSAL GATES — the original qquant platform validation stack, applied
verbatim to the MT5 hunt survivors. PARALLEL build (same statistics, same
thresholds, same libs — only the orchestration is parallelized).

Uses the EXACT implementations from C:\\Users\\dell\\quant-platform\\libs\\validation
(dsr, pbo/CSCV, reality_check/hansen_spa, cpcv, revalidation/WalkForwardEngine).
Run under the quant-platform venv python.

Gate order (gauntlet.py + run_campaign.py):
  1 economic_prior     - mechanism documented (every MT5 family has a registered rationale)
  2 in_sample_screen   - Sharpe > 0
  3 deflated_sharpe    - DSR >= 0.95, n_trials = max(2, ceil(cells_tested * 7.0))
  4 pbo                - CSCV PBO <= 0.5
  5 reality_check_spa  - Hansen SPA p < 0.05
  6 cpcv               - CPCV mean OOS Sharpe > 0 (purge + embargo)
  7 walk_forward       - WalkForwardEngine: 4 splits, test_size = len//6, min_oos_sharpe 0,
                         min_stability 0.5
  8 stress_costs       - X3 cost scenario: expected R at 3x costs > 0
  9 lockbox            - wf OOS Sharpe >= 0 (holdout proxy)
 10 expected_value     - mean daily R > 0 (explicit EV gate)

Speedup vs old serial version: (a) signals cached per (sym, win) / (sym, fam,
side, win) instead of regenerated for every cell; (b) cell series + stress
series computed by N worker processes; (c) survivor evals run in a pool.

Output: reports/QQUANT_GATES.json + reports/DONE_qquant_gates.
"""

from __future__ import annotations

import json
import itertools
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
from mt5desk.canonical import census_report  # noqa: E402
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
WORKERS = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 8

_worker_ctx: dict = {}


def _init_worker() -> None:
    """Per-process imports + caches (spawn-safe: no closures over main state)."""
    global _worker_ctx
    from run_hunt12 import WINDOWS as W12, day_states
    from run_hunt16 import WINDOWS as W16, FAMILIES as F16
    _worker_ctx = {"W12": W12, "W16": W16, "F16": F16,
                   "h1_cache": {}, "sig_cache": {}, "states_cache": {},
                   "meta": json.loads((BASE / "data" / "universe" / "universe.json")
                                      .read_text("utf-8"))}

    def costs_for(sym: str, mult: float = 1.0) -> Costs:
        m = _worker_ctx["meta"].get(sym, {})
        return Costs(
            spread_per_lot=0.48 * mult if sym == "XAUUSD" else max(
                m.get("median_spread_pts", 1) * m.get("tick_size", 1e-5)
                * m.get("contract_size", 1e5), 0.05) * mult,
            commission_per_lot=3.50 * mult, contract_oz=m.get("contract_size", 1e5))

    _worker_ctx["costs_for"] = costs_for


def _h1_of(sym: str) -> pd.DataFrame:
    if sym not in _worker_ctx["h1_cache"]:
        _worker_ctx["h1_cache"][sym] = families._h1(
            pd.read_parquet(BASE / "data" / "universe" / f"{sym}_H1.parquet"))
    return _worker_ctx["h1_cache"][sym]


def _sigs_of(hunt: int, sym: str, fam: str, side: str, win: str):
    """Signal generation with per-(sym,win) caching (the old code regenerated
    signals for EVERY cell - the main compute waste)."""
    W12 = _worker_ctx["W12"]
    W16 = _worker_ctx["W16"]
    F16 = _worker_ctx["F16"]
    if hunt == 12:
        key = (sym, win)
        if key not in _worker_ctx["sig_cache"]:
            _worker_ctx["sig_cache"][key] = list(
                families.family_session_range_breakout(_h1_of(sym), **W12[win]))
        return _worker_ctx["sig_cache"][key]
    key = (sym, fam, side, win)
    if key not in _worker_ctx["sig_cache"]:
        ffn = F16[fam]
        sday = W16[win].get("signal_at") or W16[win]["range_start"]
        sigs = [s for s in ffn(_h1_of(sym), 1 if side == "LONG" else -1)
                if s.time.hour == sday]
        _worker_ctx["sig_cache"][key] = sigs
    return _worker_ctx["sig_cache"][key]


def _series_of(hunt: int, sym: str, fam: str, side: str, win: str, state: str,
               stress: bool) -> pd.Series | None:
    from run_hunt12 import day_states
    h1 = _h1_of(sym)
    if sym not in _worker_ctx["states_cache"]:
        _worker_ctx["states_cache"][sym] = day_states(h1)
    states = _worker_ctx["states_cache"][sym]
    sigs = _sigs_of(hunt, sym, fam, side, win)
    sdays = [pd.Timestamp(s.time).date() for s in sigs]
    sub = [s for s, d in zip(sigs, sdays) if states.get(d) == state]
    if not sub:
        return None
    res = run_backtest(h1, sub, _worker_ctx["costs_for"](
        sym, COST_SCENARIO if stress else 1.0))
    series = pd.Series({pd.Timestamp(t.entry_time).date(): t.r_multiple
                        for t in res.trades}, dtype=float)
    series = series.groupby(level=0).sum()
    return series if len(series) >= 60 else None


def worker_cell(cell: dict) -> tuple:
    """Compute normal + stress series for one cell. Returns picklable tuple."""
    hunt = cell["_hunt"]
    fam = cell.get("fam") or cell.get("family")
    side = cell.get("side") or "LONG"
    sym = cell["sym"]
    win, state = cell["win"], cell["state"]
    try:
        s = _series_of(hunt, sym, fam, side, win, state, stress=False)
        sx = _series_of(hunt, sym, fam, side, win, state, stress=True)
        return (sym, fam, side, win, state,
                s.to_dict() if s is not None else None,
                sx.to_dict() if sx is not None else None)
    except Exception as e:
        return (sym, fam, side, win, state, None, str(e))


def worker_eval(row: dict, pbo_val: float, spa_p: float, n_trials: int,
                sharpes: np.ndarray) -> dict:
    """The original gauntlet evaluation for ONE survivor (identical code path).
    cell_map comes from the process global set by the pool initializer."""
    cell_map = _worker_ctx["cell_map"]
    key = (row["sym"], row.get("fam") or row.get("family"), row.get("side") or "LONG",
           row["win"], row["state"])
    if key not in cell_map or cell_map[key] is None:
        return {"error": f"series missing for {key}"}
    # SORTED BY DATE EXPLICITLY. `arr` feeds CPCV and the walk-forward engine, both of which split
    # by index POSITION and therefore assume chronological order. Taking `list(dict.values())`
    # relied on dict insertion order surviving a Series.to_dict() and a multiprocessing pickle --
    # an unstated dependency that, if it ever broke, would shuffle time inside the two gates whose
    # entire purpose is to respect it, and would do so silently. Sharpe is order-invariant, so the
    # failure would show up only in the gates that matter.
    _ser = pd.Series(cell_map[key], dtype=float).dropna()
    _ser.index = pd.to_datetime(pd.Series(list(_ser.index)), errors="coerce").values
    arr = _ser[pd.notna(_ser.index)].sort_index().to_numpy(dtype=float)
    if len(arr) < 60:
        return {"error": f"series too short ({len(arr)})"}
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
    stages["pbo"] = {"passed": bool(pbo_val <= PBO_THRESHOLD), "pbo": round(float(pbo_val), 4)}
    stages["reality_check_spa"] = {"passed": bool(spa_p < SPA_ALPHA),
                                   "p_value": round(float(spa_p), 4)}
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
    try:
        wf = WalkForwardEngine().evaluate(arr, n_splits=WF_SPLITS,
                                          test_size=max(20, len(arr) // 6),
                                          min_oos_sharpe=0.0, min_stability=WF_MIN_STABILITY)
        wf_status = wf.status
        wf_oos = float(wf.oos_sharpe)
        wf_stab = float(wf.stability)
    except Exception:
        wf_status, wf_oos, wf_stab = "TOO_SHORT", float("-inf"), 0.0
    stages["walk_forward"] = {"passed": bool(wf_status is WalkForwardStatus.PASSED),
                              "oos_sharpe": round(wf_oos, 4),
                              "stability": round(wf_stab, 4)}
    sx_key = (row["sym"], row.get("fam") or row.get("family"),
              row.get("side") or "LONG", row["win"], row["state"], "x3")
    exp3 = 0.0
    if sx_key in cell_map:
        exp3 = float(np.mean(list(cell_map[sx_key].values()))) if cell_map[sx_key] else 0.0
    stages["stress_costs"] = {"passed": bool(exp3 > 0.0), "exp_x3": round(exp3, 4)}
    stages["lockbox"] = {"passed": bool(wf_oos >= 0.0),
                         "lockbox_sharpe": round(wf_oos, 4)}
    ev = float(arr.mean())
    stages["expected_value"] = {"passed": bool(ev > 0.0), "ev": round(ev, 4)}
    passed = all(s["passed"] for s in stages.values())
    return {"passed": passed, "stages": stages, "days": len(arr)}


def _init_eval_worker(cell_map_arg: dict) -> None:
    _init_worker()
    _worker_ctx["cell_map"] = cell_map_arg


def worker_eval_row(r: dict, pbo12_v: float, pbo16_v: float, spa12_v: float,
                    spa16_v: float, nt12: int, nt16: int,
                    sh12: np.ndarray, sh16: np.ndarray) -> dict:
    if r["hunt"] == "hunt12.json":
        ev = worker_eval(r, pbo12_v, spa12_v, nt12, sh12)
    else:
        ev = worker_eval(r, pbo16_v, spa16_v, nt16, sh16)
    ev["id"] = (f"{r['sym']} {r.get('fam') or 'breakout'} "
                f"{r.get('side') or 'LONG'} {r['win']} {r['state']}")
    ev["hunt"] = r["hunt"]
    return ev


def main() -> int:
    import multiprocessing as mp
    from run_hunt12 import WINDOWS as W12  # noqa
    from run_hunt16 import WINDOWS as W16  # noqa

    sv = json.loads((REPORTS / "REAL_SURVIVORS.json").read_text("utf-8"))
    h12 = json.loads((REPORTS / "hunt12.json").read_text("utf-8"))
    h16 = json.loads((REPORTS / "hunt16.json").read_text("utf-8"))
    all12 = h12.get("all", [])
    all16 = h16.get("all", [])
    n_cells = {12: len(all12), 16: len(all16)}
    t0 = datetime.now(timezone.utc)

    cells = []
    for c in all12:
        c = dict(c); c["_hunt"] = 12; cells.append(c)
    for c in all16:
        c = dict(c); c["_hunt"] = 16; cells.append(c)
    print(f"{len(cells)} cells -> {WORKERS} workers ({t0.isoformat()})", flush=True)

    with mp.Pool(WORKERS, initializer=_init_worker) as pool:
        results = []
        for k, r in enumerate(pool.imap_unordered(worker_cell, cells, chunksize=4)):
            results.append(r)
            if (k + 1) % 50 == 0:
                el = (datetime.now(timezone.utc) - t0).total_seconds()
                print(f"cells {k + 1}/{len(cells)} "
                      f"({el / (k + 1) * len(cells) / 60:.1f} min ETA)", flush=True)

    cell_map: dict = {}
    ok = fail = 0
    for (sym, fam, side, win, state, s, sx) in results:
        if s is not None:
            cell_map[(sym, fam, side, win, state)] = s
            cell_map[(sym, fam, side, win, state, "x3")] = sx if sx is not None else None
            ok += 1
        else:
            fail += 1
    print(f"cell series computed: {ok} ok, {fail} empty/failed "
          f"in {(datetime.now(timezone.utc) - t0).total_seconds():.0f}s", flush=True)

    # ----- original program-level stats on the full trial matrices ----------
    def build_matrix(hunt: int) -> tuple[np.ndarray | None, list]:
        """Date-aligned trial matrix: row t is THE SAME CALENDAR DAY in every column.

        IT WAS NEITHER ALIGNED NOR COMPLETE, AND THE ALIGNMENT BUG IS THE WORSE OF THE TWO.
        Each cell's series is a {date: return} dict. The old code did

            arr = np.asarray(list(s.values()))          # dates discarded
            ...
            min_len = min(len(a) for a in cols)
            np.column_stack([a[-min_len:] for a in cols])

        which stacked the last N values of each column POSITIONALLY. Cells trade on different
        days, so row 5 of column A and row 5 of column B were different dates. Every number
        computed from the joint structure of that matrix -- PBO/CSCV, Hansen SPA, the correlation
        implied across trials -- was measured on a cross-section that never existed. Those are
        precisely the gates that decide whether a survivor is a curve fit.

        The truncation was the second defect: `min_len` clipped every column to the shortest,
        so one sparse cell with 60 observations reduced a matrix whose other cells had thousands
        to a 167-day window. Both defects have the same root -- the date index was thrown away --
        and both are fixed by joining on it.

        NON-TRADING DAYS ARE 0.0 HERE, AND THAT IS NOT THE BANNED ZERO-FILL. The distinction is
        what the number is being used FOR. Writing 0.0 into a series to estimate CORRELATION
        between sleeves fabricates decorrelation, inflates k_eff and raises leverage -- that is
        the defect in `record_sleeve_returns` and it stays forbidden. Here the columns are
        calendar P&L streams of individual strategies, and a day a strategy held no position
        genuinely returned nothing: the zero is a true statement about that day, not a
        substitute for a missing observation. PBO compares in-sample against out-of-sample
        selection over the SAME periods, which requires a common calendar; an inner join across
        thousands of cells that trade on different days would collapse to almost no rows.
        """
        cols, col_meta = {}, []
        for c in (all12 if hunt == 12 else all16):
            key = (c["sym"], c.get("fam") or c.get("family"),
                   c.get("side") or "LONG", c["win"], c["state"])
            s = cell_map.get(key)
            if s is None:
                continue
            ser = pd.Series(s, dtype=float).dropna()
            if len(ser) < 60:
                continue                  # too thin to characterise, at any alignment
            ser.index = pd.to_datetime(pd.Series(list(ser.index)), errors="coerce").values
            ser = ser[pd.notna(ser.index)]
            if len(ser) < 60:
                continue
            # Duplicate dates within one cell are summed: two trades on one day are one day's P&L.
            ser = ser.groupby(level=0).sum().sort_index()
            cols[f"c{len(col_meta)}"] = ser
            col_meta.append(c)
        # AN UNSWEPT FAMILY RETURNS AN EMPTY MATRIX, NOT None. `sharpes12` below indexes
        # `m12.shape[1]` unconditionally, so returning None raises AttributeError three lines
        # later and reads like a code fault rather than "this family had no cells". An empty
        # (0, 0) array flows through: the comprehension yields nothing and the `.size` guards
        # further down do the rest. np.column_stack([]) and min([]) both raise, so the guard has
        # to be here either way.
        #
        # (The progress-print that lived here indexed `ci` and `cells`, which this loop does not
        # define -- a fragment left behind by an earlier loop shape. Dropped with the refactor.)
        if not cols:
            return np.empty((0, 0)), []
        # The join is the fix. pandas aligns on the index, so every row is one calendar day
        # across all columns, and the matrix spans the UNION of trading days rather than being
        # clipped to the thinnest cell.
        df = pd.DataFrame(cols).sort_index().fillna(0.0)
        print(f"matrix hunt{hunt}: {df.shape[0]} calendar days x {df.shape[1]} cells "
              f"({df.index.min().date()} -> {df.index.max().date()}), date-aligned",
              flush=True)
        return df.to_numpy(dtype=float), col_meta

    m12, cm12 = build_matrix(12)
    m16, cm16 = build_matrix(16)
    print(f"matrix hunt12: {m12.shape if m12 is not None else 'none'}  "
          f"hunt16: {m16.shape if m16 is not None else 'none'}", flush=True)

    sharpes12 = np.array([sharpe_ratio(m12[:, k]) for k in range(m12.shape[1])])
    sharpes16 = np.array([sharpe_ratio(m16[:, k]) for k in range(m16.shape[1])])
    n_trials12 = max(2, math.ceil(n_cells[12] * TRIALS_MULTIPLIER))
    n_trials16 = max(2, math.ceil(n_cells[16] * TRIALS_MULTIPLIER))

    # HOW MANY SEARCHES WERE ACTUALLY PERFORMED, as distinct from how many cells were counted.
    # The DSR threshold scales with E[max of N], derived for N INDEPENDENT draws, and a sweep over
    # (symbol x family x side x window x state x params) manufactures near-copies structurally:
    # rr=2.0/ttl=12 and rr=2.0/ttl=13 are one search sampled twice. Reported at BOTH counts and
    # never silently substituted -- lowering N makes every threshold easier, so the correction has
    # to be visible. The gates below still run on n_trials (the raw count); this census is the
    # evidence for whether that count is the right one.
    census = {}
    for hunt, mat, sh, n_raw in ((12, m12, sharpes12, n_trials12),
                                 (16, m16, sharpes16, n_trials16)):
        if mat.size and mat.shape[1] >= 2:
            sd = float(np.std(sh)) if len(sh) > 1 else 0.0
            rep = census_report([mat[:, k] for k in range(mat.shape[1])], sd_sharpe=sd)
            rep["n_raw_declared"] = n_raw     # cells x TRIALS_MULTIPLIER, what the gates use
            census[f"hunt{hunt}"] = rep
            print(f"trial census hunt{hunt}: {rep['n_raw']} cells behave as "
                  f"{rep['n_effective']} independent searches ({rep['inflation']}x inflation); "
                  f"SR0 {rep['sr0_raw']} -> {rep['sr0_effective']}", flush=True)
        else:
            census[f"hunt{hunt}"] = {"status": "UNMEASURABLE", "n_raw_declared": n_raw,
                                     "why": "fewer than two usable columns in the trial matrix"}

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
    print(f"running the universal gauntlet on {len(rows)} REAL survivors "
          f"({WORKERS} workers)...", flush=True)

    with mp.Pool(WORKERS, initializer=_init_eval_worker, initargs=(cell_map,)) as pool:
        verdicts = list(pool.imap(worker_eval_row, rows,
                                  itertools.repeat(float(pbo12.pbo)),
                                  itertools.repeat(float(pbo16.pbo)),
                                  itertools.repeat(float(spa12.p_value)),
                                  itertools.repeat(float(spa16.p_value)),
                                  itertools.repeat(n_trials12),
                                  itertools.repeat(n_trials16),
                                  itertools.repeat(sharpes12),
                                  itertools.repeat(sharpes16)))
    n_pass = sum(1 for v in verdicts if v.get("passed"))
    gate_fails: dict[str, int] = {}
    for v in verdicts:
        for name, s in v.get("stages", {}).items():
            if not s["passed"]:
                gate_fails[name] = gate_fails.get(name, 0) + 1
    out = {
        "n_trials": {"hunt12": n_trials12, "hunt16": n_trials16},
        # The multiplicity burden the gates actually applied, next to the burden
        # the search actually earned. Both, always -- see mt5desk.canonical.
        "trial_census": census,
        "program_level": {
            "hunt12": {"pbo": round(float(pbo12.pbo), 4),
                       "spa_p": round(float(spa12.p_value), 4)},
            "hunt16": {"pbo": round(float(pbo16.pbo), 4),
                       "spa_p": round(float(spa16.p_value), 4)},
        },
        "gates": [n for n in ("economic_prior", "in_sample_screen", "deflated_sharpe",
                              "pbo", "reality_check_spa", "cpcv", "walk_forward",
                              "stress_costs", "lockbox", "expected_value")],
        "survivors_passing_all": n_pass,
        "survivors_total": len(verdicts),
        "gate_fails": gate_fails,
        "verdicts": verdicts,
        "swept_at": datetime.now(timezone.utc).isoformat(),
        "wall_s": round((datetime.now(timezone.utc) - t0).total_seconds(), 1),
        "workers": WORKERS,
    }
    (REPORTS / "QQUANT_GATES.json").write_text(json.dumps(out, indent=2, default=str),
                                               encoding="utf-8")
    (REPORTS / "DONE_qquant_gates").write_text(
        datetime.now(timezone.utc).isoformat(), encoding="utf-8")
    print(f"\nUNIVERSAL GAUNTLET: {n_pass}/{len(verdicts)} survivors pass all 10 gates "
          f"(wall {(datetime.now(timezone.utc) - t0).total_seconds() / 60:.1f} min)",
          flush=True)
    for name, cnt in sorted(gate_fails.items()):
        print(f"  gate fail [{name}]: {cnt}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())