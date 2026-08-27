"""UNIVERSAL GATE — the ONLY survivor gate for every hunt.

Directive (2026-08-17): the whole quant is tested on the ORIGINAL universal
qquant gates + thresholds only; all separate homegrown survivor gates are
retired. The battery numbers remain in hunt reports as descriptive stats, but
NO survivor claim is made without the universal 10-gate pass.

Gate order (original, verbatim from quant-platform libs/validation):
  1 economic_prior     - mechanism documented
  2 in_sample_screen   - Sharpe > 0
  3 deflated_sharpe    - DSR >= 0.95, null-calibrated effective trial census
  4 pbo                - CSCV PBO <= 0.5 (program-level, full trial matrix)
  5 reality_check_spa  - Hansen SPA p < 0.05 (program-level)
  6 cpcv               - CPCV mean OOS Sharpe > 0 (purge + embargo)
  7 walk_forward       - WalkForwardEngine 4 splits, test_size = len//6,
                         min_oos_sharpe 0, min_stability 0.5
  8 stress_costs       - X3 cost scenario expected R > 0
  9 lockbox            - wf OOS Sharpe >= 0
 10 expected_value     - mean daily R > 0

Covers hunt17/19/20/21/22 + hunt18_* loop-experiment reports. Waits for
reports/DONE_qquant_gates (the hunt12/16 REAL3 path) before starting so the
critical 182 gauntlet finishes first. Run under the quant-platform venv python.

Usage: python research/universal_gate.py
Output: reports/universal_gates_<hunt>.json + reports/UNIVERSAL_SURVIVORS.json
        + DONE markers reports/DONE_universal_<hunt>.
"""

from __future__ import annotations

# ruff: noqa: E402 -- repository and desk roots must be inserted before local imports.
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
REPORTS = BASE / "reports"
UNI = BASE / "data" / "universe"
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "research"))
# REPO ROOT, DERIVED -- not a hardcoded "C:\Users\dell\quant-platform". That path is both the
# retired laptop's user account AND a folder name ("quant-platform") this repo does not even
# have on Contabo (it is checked out as "quant"). libs/validation/* -- everything this gate
# imports next -- lives two levels above desks/mt5, wherever the checkout actually sits, so QP
# is derived from BASE the same way every other path in this repo was fixed to be tonight.
QP = BASE.parent.parent
sys.path.insert(0, str(QP))

from gate_policy import (
    ATTESTATION as GATE_POLICY,
)
from gate_policy import (
    COST_SCENARIO,
    DONE_MARKER,
    DSR_THRESHOLD,
    PBO_THRESHOLD,
    SPA_ALPHA,
    WF_MIN_STABILITY,
    WF_SPLITS,
    all_ten_pass,
    charged_trial_count,
    is_exact_policy,
)
from gate_policy import (
    GATES as GATE_NAMES,
)
from mt5desk import families
from mt5desk.canonical import calibrated_census_report
from mt5desk.engine import Costs, run_backtest

from libs.validation.cpcv import CPCV
from libs.validation.dsr import deflated_sharpe_ratio, sharpe_ratio
from libs.validation.pbo import probability_backtest_overfitting
from libs.validation.reality_check import hansen_spa
from libs.validation.revalidation import WalkForwardEngine, WalkForwardStatus

GATES = list(GATE_NAMES)
HUNTS = ["hunt17", "hunt19", "hunt20", "hunt21", "hunt22", "hunt23", "curve_compendium"]
GATE_MODULES = {  # hunt -> module + report file
    "hunt17": ("run_hunt17", "hunt17.json"),
    "hunt19": ("run_hunt19", "hunt19.json"),
    "hunt20": ("run_hunt20", "hunt20.json"),
    "hunt21": ("run_hunt21", "hunt21.json"),
    "hunt22": ("run_hunt22", "hunt22.json"),
    "hunt23": ("run_hunt23", "hunt23.json"),
    "curve_compendium": ("curve_strategy_screen", "curve_strategy_screen.json"),
}


def retained_exact_survivors(path: Path) -> dict[str, dict]:
    """Retain only already-attested exact passes during an incremental sweep.

    Universal sweeps are incremental because DONE markers skip prior hunts. Starting the output
    from an empty dict therefore deletes every prior survivor, and omitting the policy attestation
    makes the shadow fail closed even when the individual certificate remains present.
    (Grafted back after the 2026-08-25 desk sync trampled this file; the certifier-erase fix
    predates the sync's base and must survive every future restore of it.)
    """
    try:
        current = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not is_exact_policy(current.get("gate_policy")):
        return {}
    survivors = current.get("survivors")
    if not isinstance(survivors, dict):
        return {}
    return {
        str(key): row for key, row in survivors.items()
        if isinstance(row, dict) and all_ten_pass(row.get("gates"))
    }


def costs_for(sym: str, meta: dict, mult: float = 1.0) -> Costs:
    """Fusion Zero costs: `mult=2` baseline round-trip, `mult=3` stress."""
    return Costs.from_symbol(meta.get(sym, {}), mult=mult)


def daily_series(df: pd.DataFrame, sigs: list, costs: Costs) -> pd.Series:
    res = run_backtest(df, sigs, costs)
    # A dict silently retained only the final trade on multi-trade days. Preserve every trade.
    return pd.Series(
        [t.r_multiple for t in res.trades],
        index=[pd.Timestamp(t.entry_time).normalize() for t in res.trades], dtype=float,
    ).groupby(level=0).sum()


class Cell:
    __slots__ = ("costs", "df", "id", "series", "series_x3", "sigs", "sym")

    def __init__(self, cid: str, sym: str, df: pd.DataFrame | None, sigs: list,
                 costs: Costs | None, *, series: pd.Series | None = None,
                 series_x3: pd.Series | None = None):
        self.id, self.sym, self.df, self.sigs, self.costs = cid, sym, df, sigs, costs
        self.series, self.series_x3 = series, series_x3


def iter_hunt_cells(modname: str, meta: dict) -> list[Cell]:
    """Enumerate every tested cell of a hunt (report-all structure rebuilt from
    the hunt's own family code + params)."""
    if modname == "curve_strategy_screen":
        out = []
        series_dir = BASE / "data" / "cell_series" / "curve_compendium"
        for path in sorted(series_dir.glob("*.parquet")):
            frame = pd.read_parquet(path)
            if {"net_return", "stress_x3_return"} <= set(frame):
                symbol = "XAUUSD" if path.stem.startswith("GC_") else "XTIUSD"
                out.append(Cell(path.stem, symbol, None, [], None,
                                series=frame["net_return"].dropna(),
                                series_x3=frame["stress_x3_return"].dropna()))
        return out
    mod = __import__(modname)
    if hasattr(mod, "UNIVERSAL_CELLS"):  # hunt supplies its own cell iterator
        return list(mod.UNIVERSAL_CELLS(meta))
    report = json.loads((REPORTS / f"{modname.replace('run_', '')}.json").read_text("utf-8"))
    all_cells = report.get("all", [])
    if not all_cells:
        return []
    h4_cache: dict[str, tuple[pd.DataFrame, pd.DataFrame]] = {}
    fams = getattr(mod, "FAMILIES", {})
    out: list[Cell] = []
    for c in all_cells:
        sym = c.get("sym")
        fam = c.get("fam") or c.get("family")
        side = 1 if (c.get("side") or "LONG") == "LONG" else -1
        if not sym or fam not in fams or not (UNI / f"{sym}_H1.parquet").exists():
            continue
        if sym not in h4_cache:
            h1 = families._h1(pd.read_parquet(UNI / f"{sym}_H1.parquet"))
            h4_cache[sym] = mod.resample(h1)
        h4, d1 = h4_cache[sym]
        fn = fams[fam]
        params = c.get("params") or {}
        if not params and c.get("param") is not None and hasattr(mod, "PARAMS"):
            pl = mod.PARAMS.get(fam)
            if pl:
                params = pl[int(c["param"])]
        try:
            sigs = fn(h4, d1, side, **params) if params else fn(h4, d1, side)
        except Exception as e:
            print(f"  rebuild fail {sym}.{fam}: {e!r}", flush=True)
            continue
        out.append(Cell(f"{sym}.{fam}.{c.get('param', 0)}.{'L' if side > 0 else 'S'}",
                        sym, h4, sigs, costs_for(sym, meta, mult=2.0)))
    return out


def _ug_daily(args) -> pd.Series | None:
    df, sigs, costs = args
    try:
        if isinstance(df, pd.Series):
            return df
        return daily_series(df, sigs, costs)
    except Exception as e:
        print(f"  daily series error: {e!r}", flush=True)
        return None


def _ug_verdict(args) -> dict:
    cid, sym, arr, arr_x3, pbo_ok, pbo_val, spa_ok, spa_p, n_trials, sh_var = args
    arr = np.asarray(arr, dtype=float)
    if len(arr) < 60:
        return {"cell": cid, "error": "series too short"}
    sr = sharpe_ratio(arr)
    stages = {
        "economic_prior": {"passed": True, "message": "mechanism documented at hunt registration"},
        "in_sample_screen": {"passed": bool(sr > 0.0), "sharpe": round(float(sr), 4)},
    }
    dsr = deflated_sharpe_ratio(arr, n_trials=n_trials,
                                variance_of_sharpes=float(sh_var), threshold=DSR_THRESHOLD)
    stages["deflated_sharpe"] = {"passed": bool(dsr.passed), "dsr": round(float(dsr.dsr), 4),
                                 "sr0": round(float(dsr.sr0_threshold), 4), "n_trials": n_trials}
    stages["pbo"] = {"passed": pbo_ok, "pbo": round(float(pbo_val), 4)}
    stages["reality_check_spa"] = {"passed": spa_ok, "p_value": round(float(spa_p), 4)}
    cpcv = CPCV(n_groups=6, n_test_groups=2)
    oos = []
    for split in cpcv.split(len(arr)):
        te = np.asarray(split.test)
        if len(te) >= 30:
            oos.append(sharpe_ratio(arr[te]))
    cpcv_mean = float(np.mean(oos)) if oos else 0.0
    stages["cpcv"] = {"passed": bool(cpcv_mean > 0.0), "mean_oos_sharpe": round(cpcv_mean, 4),
                      "folds": len(oos)}
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
    exp3 = float(np.asarray(arr_x3, dtype=float).mean()) if len(arr_x3) else 0.0
    stages["stress_costs"] = {"passed": bool(exp3 > 0.0), "exp_x3": round(exp3, 4)}
    stages["lockbox"] = {"passed": bool(wf_oos >= 0.0),
                         "lockbox_sharpe": round(wf_oos, 4)}
    ev = float(arr.mean())
    stages["expected_value"] = {"passed": bool(ev > 0.0), "ev": round(ev, 4)}
    return {"cell": cid, "sym": sym, "days": len(arr),
            "passed": all(s["passed"] for s in stages.values()),
            "stages": stages}


def gauntlet(cells: list[Cell], hunt: str) -> dict:
    import psutil as _ps
    avail_mb = _ps.virtual_memory().available / 1048576
    cap = 1 if os.name != "nt" and avail_mb < 1024 else (2 if os.name != "nt" else 8)
    workers = min(cap, len(cells) or 1)
    if workers <= 1:
        print(f"  {hunt}: sequential mode (free={avail_mb:.0f}MB)", flush=True)
    for attempt in range(3):
        try:
            return _gauntlet_once(cells, hunt, workers)
        except (BrokenPipeError, OSError) as e:
            print(f"  {hunt}: pool died (attempt {attempt + 1}/3, {e!r}); "
                  f"free={avail_mb:.0f}MB, retrying in 60s", flush=True)
            time.sleep(60)
    raise RuntimeError(f"{hunt}: pool kept dying (3 attempts)")


def _gauntlet_once(cells: list[Cell], hunt: str, workers: int) -> dict:
    import multiprocessing as mp
    daily_args = [((c.series, None, None) if c.series is not None
                   else (c.df, c.sigs, c.costs)) for c in cells]
    # Baseline already crosses 2x the measured spread. X3 means three crossings, not baseline*3;
    # contractual commission does not widen with market stress.
    x3_args = []
    for c in cells:
        if c.series_x3 is not None:
            x3_args.append((c.series_x3, None, None))
        else:
            # DERIVE, NEVER REBUILD. This constructed a fresh `Costs` from three of the four
            # fields, so `quote_per_account` reverted to its 1.0 default and un-did the account-
            # currency conversion the baseline had already applied. Measured 2026-08-27 on
            # CADJPY: baseline round trip 1699.29, this line 607.00, correct 1899.29 -- the x3
            # cost-stress gate was testing at 0.36x, weaker than the baseline it stresses, on the
            # JPY crosses that carry this desk's live family. `stressed()` carries every field
            # by construction, so a field added later cannot be dropped here again.
            x3_args.append((c.df, c.sigs, c.costs.stressed(COST_SCENARIO / 2.0)))
    if workers <= 1:
        daily = [_ug_daily(a) for a in daily_args]
        daily_x3 = [_ug_daily(a) for a in x3_args]
    else:
        with mp.Pool(workers) as pool:
            daily = list(pool.map(_ug_daily, daily_args))
            daily_x3 = list(pool.map(_ug_daily, x3_args))
    cols: dict[str, pd.Series] = {}
    for idx, s in enumerate(daily):
        if s is None:
            continue
        if len(s) >= 60:
            cols[f"c{idx}"] = s
    if not cols:
        return {"hunt": hunt, "error": "no cells with >=60 days", "verdicts": []}
    # Joint gates require the same calendar row across trials. Non-trading calendar days are true
    # zero P&L for the program matrix, while each cell's own gates below retain active observations.
    matrix_frame = pd.DataFrame(cols).sort_index().fillna(0.0)
    matrix = matrix_frame.to_numpy(float)
    sharpes = np.array([sharpe_ratio(matrix[:, k]) for k in range(matrix.shape[1])])
    census = calibrated_census_report(
        [matrix[:, k] for k in range(matrix.shape[1])],
        sd_sharpe=float(sharpes.std(ddof=1)) if len(sharpes) > 1 else 0.0,
    )
    n_trials, trial_basis = charged_trial_count(
        len(cols), census.get("n_effective"), census.get("method"))
    pbo = probability_backtest_overfitting(matrix)
    spa = hansen_spa(matrix)
    pbo_ok = float(pbo.pbo) <= PBO_THRESHOLD
    spa_ok = float(spa.p_value) < SPA_ALPHA
    print(f"  {hunt}: matrix {matrix.shape} PBO={float(pbo.pbo):.3f} "
          f"SPA p={float(spa.p_value):.4f} n_trials={n_trials} ({trial_basis})", flush=True)

    args = []
    for k, c in enumerate(cells):
        if daily[k] is None:
            args.append((c.id, c.sym, np.array([]), np.array([]),
                         pbo_ok, float(pbo.pbo), spa_ok, float(spa.p_value),
                         n_trials, float(sharpes.var(ddof=1))))
            continue
        arr = daily[k].to_numpy(float)
        if len(arr) < 60:
            args.append((c.id, c.sym, np.array([]), np.array([]),
                         pbo_ok, float(pbo.pbo), spa_ok, float(spa.p_value),
                         n_trials, float(sharpes.var(ddof=1))))
            continue
        x3 = daily_x3[k]
        args.append((c.id, c.sym, arr, x3.to_numpy(float) if x3 is not None
                     else np.array([]),
                     pbo_ok, float(pbo.pbo), spa_ok, float(spa.p_value),
                     n_trials, float(sharpes.var(ddof=1))))
    if workers <= 1:
        verdicts = [_ug_verdict(a) for a in args]
    else:
        with mp.Pool(workers) as pool:
            verdicts = list(pool.map(_ug_verdict, args))
    gate_fails: dict[str, int] = {}
    for v in verdicts:
        for name, s in v.get("stages", {}).items():
            if not s["passed"]:
                gate_fails[name] = gate_fails.get(name, 0) + 1
    n_pass = sum(1 for v in verdicts if v.get("passed"))
    print(f"  {hunt}: {n_pass}/{len(verdicts)} cells pass all 10 gates", flush=True)
    return {
        "hunt": hunt, "n_cells": len(cells), "n_trials": n_trials,
        "trial_count_basis": trial_basis, "trial_census": census,
        "program_level": {"pbo": round(float(pbo.pbo), 4), "spa_p": round(float(spa.p_value), 4)},
        "survivors_passing_all": n_pass, "gate_fails": gate_fails, "verdicts": verdicts,
        "swept_at": datetime.now(UTC).isoformat(),
    }


def main() -> int:
    done_flag = REPORTS / DONE_MARKER
    held_flag = BASE / "data" / "HOLD_qquant_gates"
    if not done_flag.exists() and not held_flag.exists():
        print(f"waiting for {DONE_MARKER} (current original ten-gate run) ...", flush=True)
        while not done_flag.exists():
            time.sleep(60)
        print("qquant gates done, starting universal gauntlet", flush=True)
    meta = json.loads((UNI / "universe.json").read_text("utf-8"))
    survivor_path = REPORTS / "UNIVERSAL_SURVIVORS.json"
    survivors_all: dict[str, dict] = retained_exact_survivors(survivor_path)
    for hunt in HUNTS:
        marker = REPORTS / f"DONE_universal_{hunt}"
        if marker.exists():
            print(f"{hunt}: already gated ({marker}), skipping", flush=True)
            continue
        modname, report_name = GATE_MODULES[hunt]
        if not (REPORTS / report_name).exists():
            print(f"{hunt}: report missing, skipping", flush=True)
            continue
        print(f"gauntlet: {hunt} ...", flush=True)
        cells = iter_hunt_cells(modname, meta)
        if not cells:
            print(f"{hunt}: no cells, skipping", flush=True)
            continue
        res = gauntlet(cells, hunt)
        (REPORTS / f"universal_gates_{hunt}.json").write_text(
            json.dumps(res, indent=2, default=str), encoding="utf-8")
        for v in res.get("verdicts", []):
            if v.get("passed"):
                survivors_all[f"{hunt}.{v['cell']}"] = {
                    "hunt": f"{hunt}.json", "cell": v["cell"], "sym": v["sym"],
                    "days": v["days"], "gates": v["stages"],
                    "gated_at": datetime.now(UTC).isoformat()}
        (REPORTS / f"DONE_universal_{hunt}").write_text(
            datetime.now(UTC).isoformat(), encoding="utf-8")
    # hunt18 loop-experiment reports
    # Clear run_hunt17 anchor cache so it reloads fresh T10YIE
    import run_hunt17 as _rh17
    if hasattr(_rh17, "_ANC"):
        _rh17._ANC = None
    import mt5desk.families as _mt5fam
    if hasattr(_mt5fam, "_ANC"):
        _mt5fam._ANC = None
    for rp in sorted(REPORTS.glob("hunt18_*.json")):
        marker = REPORTS / f"DONE_universal_{rp.stem}"
        if marker.exists():
            continue
        report = json.loads(rp.read_text("utf-8"))
        fam = report.get("family")
        if not fam:
            print(f"{rp.stem}: no family key, skipping", flush=True)
            continue
        from run_hunt17 import FAMILIES as F17
        from run_hunt17 import resample as r17resample
        fn = F17.get(fam)
        if not fn:
            continue
        side = 1 if (report.get("side") or "LONG") == "LONG" else -1
        params = report.get("params") or {}
        cells = []
        for c in report.get("all", []):
            sym = c.get("sym")
            if not (UNI / f"{sym}_H1.parquet").exists():
                continue
            h1 = families._h1(pd.read_parquet(UNI / f"{sym}_H1.parquet"))
            h4, d1 = r17resample(h1)
            try:
                sigs = fn(h4, d1, side, **params)
            except Exception:
                continue
            cells.append(Cell(f"{sym}.{fam}.{side}", sym, h4, sigs,
                              costs_for(sym, meta, mult=2.0)))
        if not cells:
            continue
        res = gauntlet(cells, rp.stem)
        (REPORTS / f"universal_gates_{rp.stem}.json").write_text(
            json.dumps(res, indent=2, default=str), encoding="utf-8")
        for v in res.get("verdicts", []):
            if v.get("passed"):
                survivors_all[f"{rp.stem}.{v['cell']}"] = {
                    "hunt": rp.name, "cell": v["cell"], "sym": v["sym"],
                    "days": v["days"], "gates": v["stages"],
                    "gated_at": datetime.now(UTC).isoformat()}
        (REPORTS / f"DONE_universal_{rp.stem}").write_text(
            datetime.now(UTC).isoformat(), encoding="utf-8")

    # Re-read immediately before publication. Another certified producer (notably QQUANT) may
    # have published while this expensive sweep was running; never erase that result.
    latest = retained_exact_survivors(survivor_path)
    latest.update(survivors_all)
    survivors_all = latest
    survivor_path.write_text(
        json.dumps({"n": len(survivors_all), "survivors": survivors_all,
                    "gate_policy": GATE_POLICY,
                    "note": "UNIVERSAL 10-GATE PASS ONLY. Placebo null + fragility "
                            "apply before portfolio entry.",
                    "swept_at": datetime.now(UTC).isoformat()},
                   indent=2, default=str), encoding="utf-8")
    ledger_path = REPORTS / "SURVIVORS_LEDGER.json"
    ledger: dict = {}
    if ledger_path.exists():
        try:
            ledger = json.loads(ledger_path.read_text("utf-8")).get("claims", {})
        except Exception:
            ledger = {}
    for k, v in survivors_all.items():
        ledger[k] = {**v, "status": "UNIVERSAL",
                     "updated_at": datetime.now(UTC).isoformat()}
    ledger_path.write_text(
        json.dumps({"n": len(ledger), "claims": ledger}, indent=2, default=str),
        encoding="utf-8")
    print(f"\nUNIVERSAL SURVIVORS: {len(survivors_all)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
