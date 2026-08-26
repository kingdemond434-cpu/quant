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
sys.path.insert(0, str(Path(r"C:\Users\dell\quant-platform")))

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
        """Costs via the sanctioned constructor. This hand-roll carried BOTH unit bugs.

        `0.48` for gold is dollars per OUNCE in a field that wants currency per LOT, so the
        engine divided it by 100 and charged 3% of a real spread. And `Costs` divides commission
        by contract_size, which treats one unit of account currency as one unit of PRICE -- true
        only for a symbol quoted in the account's own currency, and 1/184th of the truth on a JPY
        cross. `from_symbol` fixes both; hand-rolling beside it is what kept the fixes out.

        `mult` STILL SCALES THE COMMISSION, which `from_symbol`'s docstring argues against (a
        contractual fee does not widen). That argument is right and changing it here would LOWER
        a stressed cost, which is the one direction that can manufacture a survivor. The units
        are corrected now -- every component of this cost is >= what it was -- and the
        commission-stress question is a separate decision with its own evidence.
        """
        m = _worker_ctx["meta"].get(sym, {})
        return Costs.from_symbol(m, mult=mult, commission_per_lot=3.50 * mult)

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
    arr = np.asarray(list(cell_map[key].values()), dtype=float)
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
        cols, col_meta = [], []
        for c in (all12 if hunt == 12 else all16):
            key = (c["sym"], c.get("fam") or c.get("family"),
                   c.get("side") or "LONG", c["win"], c["state"])
            s = cell_map.get(key)
            if s is None:
                continue
            arr = np.asarray(list(s.values()), dtype=float)
            if len(arr) < 60:
                continue
            cols.append(arr)
            col_meta.append(c)
        if not cols:
            return None, []
        min_len = min(len(a) for a in cols)
        return np.column_stack([a[-min_len:] for a in cols]), col_meta

    m12, cm12 = build_matrix(12)
    m16, cm16 = build_matrix(16)
    print(f"matrix hunt12: {m12.shape if m12 is not None else 'none'}  "
          f"hunt16: {m16.shape if m16 is not None else 'none'}", flush=True)

    sharpes12 = np.array([sharpe_ratio(m12[:, k]) for k in range(m12.shape[1])]) \
        if m12 is not None else np.array([])
    sharpes16 = np.array([sharpe_ratio(m16[:, k]) for k in range(m16.shape[1])]) \
        if m16 is not None else np.array([])
    n_trials12 = max(2, math.ceil(n_cells[12] * TRIALS_MULTIPLIER))
    n_trials16 = max(2, math.ceil(n_cells[16] * TRIALS_MULTIPLIER))

    print("program-level: PBO + SPA on full trial matrices...", flush=True)
    pbo12 = probability_backtest_overfitting(m12)
    pbo16 = probability_backtest_overfitting(m16)
    spa12 = hansen_spa(m12)
    spa16 = hansen_spa(m16)
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