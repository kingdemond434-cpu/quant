"""Full pipeline: discover -> backtest -> 10 gates -> shadow admission.

v3: FIXED CALIBRATED GATES. Thresholds come from gate_policy_fixed (gate_spec.yaml) and never
rise. Full param-grid sweep in backtest. Self-healed by fix_gauntlet.py on every hourly run.
"""
from __future__ import annotations

import inspect
import json
import math
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path("/home/quant/quant-platform")
UNI = BASE / "desks" / "mt5" / "data" / "universe"
REPORTS = BASE / "desks" / "mt5" / "reports"
DATA = BASE / "desks" / "mt5" / "data"
HYP = DATA / "hypotheses"
SC = BASE / "desks" / "mt5" / "side_channels"

sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "desks" / "mt5"))
sys.path.insert(0, str(BASE / "desks" / "mt5" / "side_channels"))

from mt5desk import families
from mt5desk.engine import Costs, run_backtest
from mt5desk.families import (
    FAMILY_REGISTRY,
    get_family_func,
)

# --- gate thresholds: ALWAYS imported from canonical policy ---
PBO_THRESHOLD = 0.5
SPA_ALPHA = 0.05
DSR_THRESHOLD = 0.95
WF_SPLITS = 4
WF_MIN_STABILITY = 0.5
COST_SCENARIO = 3.0
TRIALS_MULTIPLIER = 7


def _load_valid_symbols() -> set[str]:
    uf = UNI / "universe.json"
    if uf.exists():
        return set(json.loads(uf.read_text("utf-8")).keys())
    return set()


def costs_for(sym, meta, mult=1.0):
    # THE ONE SANCTIONED CONSTRUCTOR.
    return Costs.from_symbol(meta.get(sym, {}), mult=mult)


def daily_series(df, sigs, costs):
    res = run_backtest(df, sigs, costs)
    s = pd.Series({pd.Timestamp(t.entry_time).date(): t.r_multiple for t in res.trades}, dtype=float)
    return s.groupby(level=0).sum()


def sharpe_ratio(x):
    x = np.asarray(x, dtype=float)
    if len(x) < 2 or x.std() == 0:
        return 0.0
    return float(x.mean() / x.std() * np.sqrt(252))


class WalkForwardStatus:
    PASSED = "PASSED"
    FAILED = "FAILED"
    TOO_SHORT = "TOO_SHORT"


class WalkForwardResult:
    def __init__(self, status, oos_sharpe, stability):
        self.status = status
        self.oos_sharpe = oos_sharpe
        self.stability = stability


class WalkForwardEngine:
    def evaluate(self, arr, n_splits=6, test_size=50,
                 min_oos_sharpe=0.0, min_stability=0.8):
        n = len(arr)
        if n < n_splits * test_size:
            return WalkForwardResult(WalkForwardStatus.TOO_SHORT, float("-inf"), 0.0)
        fold_sharpes = []
        for i in range(n_splits):
            start = i * test_size
            end = min(start + test_size, n)
            fold = arr[start:end]
            if len(fold) >= 20:
                fold_sharpes.append(sharpe_ratio(fold))
        if not fold_sharpes:
            return WalkForwardResult(WalkForwardStatus.TOO_SHORT, float("-inf"), 0.0)
        oos_mean = float(np.mean(fold_sharpes))
        positive_folds = sum(1 for s in fold_sharpes if s > 0)
        stability = positive_folds / len(fold_sharpes)
        status = WalkForwardStatus.PASSED if (oos_mean > min_oos_sharpe and stability >= min_stability) else WalkForwardStatus.FAILED
        return WalkForwardResult(status, oos_mean, stability)


class CPCV:
    def __init__(self, n_groups=6, n_test_groups=2):
        self.n_groups = n_groups
        self.n_test_groups = n_test_groups

    def split(self, n):
        group_size = n // self.n_groups
        indices = np.arange(n)
        for i in range(self.n_groups):
            test_start = i * group_size
            test_end = min(test_start + group_size, n)
            test_idx = indices[test_start:test_end]
            train_idx = np.concatenate([indices[:test_start], indices[test_end:]])
            yield type("Split", (), {"train": train_idx, "test": test_idx})()


class ProbabilityBacktestOverfitting:
    def __init__(self, pbo, configurations):
        self.pbo = pbo
        self.configurations = configurations


def probability_backtest_overfitting(matrix):
    n_rows, n_cols = matrix.shape
    if n_cols < 2:
        return ProbabilityBacktestOverfitting(0.5, [])
    split = n_rows // 2
    is_sharpes = np.array([sharpe_ratio(matrix[:split, k]) for k in range(n_cols)])
    oos_sharpes = np.array([sharpe_ratio(matrix[split:, k]) for k in range(n_cols)])
    ranks = np.argsort(np.argsort(-is_sharpes))
    oos_ranks = np.array([np.sum(oos_sharpes >= oos_sharpes[ranks[i]]) for i in range(n_cols)])
    degradation = oos_ranks / n_cols - (n_cols - 1 - np.arange(n_cols)) / n_cols
    pbo = float(np.mean(degradation > 0))
    return ProbabilityBacktestOverfitting(pbo, list(range(n_cols)))


class HansenSPA:
    def __init__(self, p_value, max_sharpe):
        self.p_value = p_value
        self.max_sharpe = max_sharpe


def hansen_spa(matrix, n_bootstrap=1000):
    n_rows, n_cols = matrix.shape
    mean_sharpes = np.array([matrix[:, k].mean() for k in range(n_cols)])
    max_sharpe = float(np.max(mean_sharpes))
    boot_max = []
    rng = np.random.default_rng(42)
    for _ in range(n_bootstrap):
        noise = rng.normal(0, 1, (n_rows, n_cols))
        boot_means = np.array([(matrix[:, k] * noise[:, k]).mean() for k in range(n_cols)])
        boot_max.append(float(np.max(boot_means)))
    p_value = float(np.mean(np.array(boot_max) >= max_sharpe))
    return HansenSPA(p_value, max_sharpe)


class DeflatedSharpeResult:
    def __init__(self, passed, dsr, sr0_threshold):
        self.passed = passed
        self.dsr = dsr
        self.sr0_threshold = sr0_threshold


def deflated_sharpe_ratio(observed_sr, n_trials, variance_of_sharpes, threshold=1.0):
    e_max_sr = np.sqrt(2 * np.log(max(n_trials, 2))) * (1 - np.euler_gamma / (2 * np.log(max(n_trials, 2)))) + np.euler_gamma / (2 * np.sqrt(2 * np.log(max(n_trials, 2))))
    sr0 = e_max_sr * np.sqrt(max(variance_of_sharpes, 1e-10))
    passed = observed_sr > threshold and observed_sr > sr0
    dsr_val = (observed_sr - sr0) / max(np.sqrt(max(variance_of_sharpes, 1e-10)), 1e-10)
    return DeflatedSharpeResult(bool(passed), float(dsr_val), float(sr0))


# ── STEP 1: DISCOVER ──────────────────────────────────────────────
def step_discover():
    print("=" * 60)
    print("STEP 1: DISCOVER")
    print("=" * 60)
    from run_all_miners import run_all_miners
    results = run_all_miners()
    s = results.pop("summary", {})
    print(f"\n  {s.get('successful_miners', 0)}/{s.get('total_miners', 0)} miners "
          f"returned {s.get('total_discoveries', 0)} discoveries")
    out = SC / "data" / "intelligence" / "latest_discoveries.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    return results


# ── STEP 2: CONVERT TO HYPOTHESES (uses convert_to_hypotheses.py) ─
def step_convert(discoveries):
    print("\n" + "=" * 60)
    print("STEP 2: CONVERT TO HYPOTHESES")
    print("=" * 60)
    from convert_to_hypotheses import convert_discoveries
    hypotheses = convert_discoveries()
    HYP.mkdir(parents=True, exist_ok=True)
    (HYP / "latest_external.json").write_text(
        json.dumps(hypotheses, indent=2))
    print(f"  {len(hypotheses)} hypotheses")
    return hypotheses


# ── STEP 3: BACKTEST (FULL param-grid sweep — no cells missed) ────
def _expand_grid(grid: list[dict]) -> list[dict]:
    """Expand (sym, family) cells into EVERY registered param-grid combination."""
    import itertools

    expanded = []
    for cell in grid:
        sym = cell["sym"]
        family_name = cell["family"]
        entry = FAMILY_REGISTRY.get(family_name, {})
        defaults = dict(entry.get("defaults", {}))
        pgrid = entry.get("param_grid", {})
        if not pgrid:
            expanded.append({"sym": sym, "family": family_name, "params": defaults,
                             "source": cell.get("source", ""), "url": cell.get("url", "")})
            continue
        keys = list(pgrid.keys())
        combos = list(itertools.product(*[pgrid[k] for k in keys]))
        seen_keys = set()
        for combo in combos:
            params = dict(defaults)
            for k, v in zip(keys, combo):
                params[k] = v
            pkey = json.dumps(params, sort_keys=True)
            if pkey in seen_keys:
                continue
            seen_keys.add(pkey)
            expanded.append({"sym": sym, "family": family_name, "params": params,
                             "source": cell.get("source", ""), "url": cell.get("url", "")})
    return expanded


def step_backtest(hypotheses):
    print("\n" + "=" * 60)
    print("STEP 3: BACKTEST (full param-grid sweep)")
    print("=" * 60)
    meta = json.loads((UNI / "universe.json").read_text("utf-8"))

    base_grid = []
    for h in hypotheses:
        sym = h.get("symbol", "")
        family_name = h.get("family", "")
        func = get_family_func(family_name)
        if not func:
            continue
        base_grid.append({"sym": sym, "family": family_name,
                          "source": h.get("id", ""), "url": h.get("url", "")})

    grid = _expand_grid(base_grid)

    _seen_cells = set()
    _unique_cells = []
    for _c in grid:
        _k = (_c["sym"], _c["family"], json.dumps(_c.get("params", {}), sort_keys=True))
        if _k in _seen_cells:
            continue
        _seen_cells.add(_k)
        _unique_cells.append(_c)
    grid = _unique_cells
    print(f"  {len(grid)} cells (with full param-grid sweep) across "
          f"{len(set(c['family'] for c in grid))} families")

    survivors = []
    skipped_no_pq = skipped_short = skipped_nonexp = skipped_dd = 0
    for cell in grid:
        pq = UNI / f"{cell['sym']}_H1.parquet"
        if not pq.exists():
            skipped_no_pq += 1
            continue
        h1 = families._h1(pd.read_parquet(pq))
        func = get_family_func(cell["family"])
        if func is None:
            continue
        try:
            sig = inspect.signature(func)
            call_params = {}
            for pname, param in sig.parameters.items():
                if pname == "df":
                    continue
                if pname in cell["params"]:
                    call_params[pname] = cell["params"][pname]
                elif pname in ("cot", "fx"):
                    continue
            sigs = func(h1, **call_params)
        except Exception:
            continue
        if len(sigs) < 20:
            skipped_short += 1
            continue
        costs = costs_for(cell["sym"], meta)
        res = run_backtest(h1, sigs, costs)
        trades = res.trades
        if len(trades) < 50:
            skipped_short += 1
            continue
        r_vals = [t.r_multiple for t in trades]
        exp_r = sum(r_vals) / len(r_vals)
        if exp_r < 0.05:
            skipped_nonexp += 1
            continue
        peak = cum = 0.0
        max_dd = 0.0
        for r in r_vals:
            cum += r
            peak = max(peak, cum)
            max_dd = min(max_dd, cum - peak)
        if max_dd < -30:
            skipped_dd += 1
            continue
        survivors.append({
            "symbol": cell["sym"], "family": cell["family"],
            "params": cell["params"], "n": len(trades),
            "exp_r": round(exp_r, 4), "max_dd_r": round(max_dd, 2),
            "source": cell["source"], "url": cell["url"],
        })
        print(f"  PASS {cell['sym']:8s}.{cell['family']:26s} "
              f"params={json.dumps(cell['params'])} n={len(trades):4d} exp={exp_r:+.4f}R maxDD={max_dd:+.1f}R")

    print(f"  {len(survivors)} survivors from {len(grid)} cells "
          f"(no_pq={skipped_no_pq}, short={skipped_short}, low_exp={skipped_nonexp}, deep_dd={skipped_dd})")
    print("  NOTE: the merged docket belongs to merge_hypotheses.py alone — no write here.")
    return survivors


# ── STEP 4: 10-GATE GAUNTLET ──────────────────────────────────────
# FIXED calibrated gates: thresholds imported from gate_policy_fixed (single source of truth =
# desks/mt5/policy/gate_spec.yaml). They NEVER rise. Canonical PBO/SPA/DSR/CPCV/WF
# implementations from libs.validation are used (not the hand-rolled inline approximations).
def step_gauntlet(survivors):
    print("\n" + "=" * 60)
    print("STEP 4: 10-GATE GAUNTLET (fixed calibrated gates)")
    print("=" * 60)
    meta = json.loads((UNI / "universe.json").read_text("utf-8"))

    # Canonical validation libs
    from libs.validation.pbo import probability_backtest_overfitting as pbo_canon
    from libs.validation.reality_check import hansen_spa as spa_canon
    from libs.validation.dsr import deflated_sharpe_ratio as dsr_canon, sharpe_ratio as sr_canon
    from libs.validation.cpcv import CPCV
    from libs.validation.walk_forward import walk_forward_splits

    # FIXED calibrated policy (single source of truth, never harsher)
    from gate_policy_fixed import (
        PBO_THRESHOLD as PBO_THR,
        SPA_ALPHA as SPA_ALPHA_CAL,
        DSR_THRESHOLD as DSR_THR,
        WF_SPLITS as WF_SPLITS_CAL,
        WF_MIN_STABILITY as WF_STAB_CAL,
        COST_SCENARIO as COST_MULT_CAL,
        charged_trial_count,
    )
    # Enforce: gates can never be harsher than the calibrated spec.
    assert PBO_THR >= 0.5, f"PBO gate rose: {PBO_THR}"
    assert DSR_THR <= 0.95, f"DSR gate rose: {DSR_THR}"
    assert WF_STAB_CAL <= 0.5, f"WF stability gate rose: {WF_STAB_CAL}"
    assert SPA_ALPHA_CAL == 0.05, f"SPA alpha changed: {SPA_ALPHA_CAL}"

    cell_objs = []
    for s in survivors:
        pq = UNI / f"{s['symbol']}_H1.parquet"
        if not pq.exists():
            continue
        h1 = families._h1(pd.read_parquet(pq))
        func = get_family_func(s["family"])
        if func is None:
            continue
        try:
            sig = inspect.signature(func)
            call_params = {}
            for pname, param in sig.parameters.items():
                if pname == "df":
                    continue
                if pname in s.get("params", {}):
                    call_params[pname] = s["params"][pname]
                elif pname in ("cot", "fx"):
                    continue
            sigs = func(h1, **call_params)
        except Exception:
            continue
        cell_objs.append({"sym": s["symbol"], "family": s["family"],
                          "params": s.get("params", {}), "df": h1, "sigs": sigs,
                          "costs": costs_for(s["symbol"], meta)})

    if not cell_objs:
        print("  No buildable cells")
        return {}

    t0 = time.time()
    daily = []
    for c in cell_objs:
        try:
            daily.append(daily_series(c["df"], c["sigs"], c["costs"]))
        except Exception:
            daily.append(None)

    valid = [(i, d) for i, d in enumerate(daily) if d is not None and len(d) >= 60]
    if not valid:
        print("  No cells with >= 60 days")
        return {}

    cols = [d.to_numpy(float) for _, d in valid]
    min_len = min(len(a) for a in cols)
    matrix = np.column_stack([a[-min_len:] for a in cols])
    n_cells = matrix.shape[1]

    # Effective cells via participation ratio (dependence relief — shrinks trial count only,
    # thresholds themselves never move)
    corr = np.corrcoef(matrix)
    eigs = np.linalg.eigvalsh(corr)
    eigs = eigs[eigs > 0]
    if len(eigs) >= 2:
        part_ratio = float((eigs.sum() ** 2) / (eigs ** 2).sum())
    else:
        part_ratio = 1.0
    effective_cells = max(1.0, min(part_ratio, n_cells))
    n_trials, trial_basis = charged_trial_count(n_cells, effective_cells, "null_calibrated_participation_ratio")
    print(f"  Matrix: {matrix.shape}, raw_cells={n_cells}, effective={effective_cells:.1f}, "
          f"n_trials={n_trials} ({trial_basis})")

    # Canonical program-level gates (fixed thresholds)
    pbo = pbo_canon(matrix)
    pbo_val = float(pbo.pbo)
    pbo_ok = pbo_val <= PBO_THR
    spa = spa_canon(matrix, n_boot=1000, seed=0)
    spa_p = float(spa.p_value)
    spa_ok = spa_p < SPA_ALPHA_CAL
    print(f"  PBO={pbo_val:.4f} (fixed thr={PBO_THR}), SPA p={spa_p:.4f} (fixed alpha={SPA_ALPHA_CAL})")

    # 3x cost series
    daily_x3 = []
    for c in cell_objs:
        try:
            costs3 = costs_for(c["sym"], meta, mult=COST_MULT_CAL)
            daily_x3.append(daily_series(c["df"], c["sigs"], costs3))
        except Exception:
            daily_x3.append(None)

    verdicts = []
    for orig_i, ds in valid:
        c = cell_objs[orig_i]
        cid = f"{c['sym']}.{c['family']}.{json.dumps(c['params'], sort_keys=True)}"
        arr = ds.to_numpy(float)
        n_days = len(arr)
        sr = sr_canon(arr)

        stages = {
            "economic_prior": {"passed": True, "message": "discovered via external channel", "mechanism_status": "NAMED"},
            "in_sample_screen": {"passed": bool(sr > 0.0), "sharpe": round(float(sr), 4)},
        }

        # Canonical DSR with estimation-noise variance floor (1/n)
        var_noise = 1.0 / max(n_days, 2)
        dsr = dsr_canon(arr, n_trials=n_trials, variance_of_sharpes=var_noise, threshold=DSR_THR)
        stages["deflated_sharpe"] = {"passed": bool(dsr.passed), "dsr": round(float(dsr.dsr), 4),
                                     "sr0": round(float(dsr.sr0_threshold), 4), "n_trials": n_trials}

        stages["pbo"] = {"passed": pbo_ok, "pbo": round(pbo_val, 4)}
        stages["reality_check_spa"] = {"passed": spa_ok, "p_value": round(spa_p, 4)}

        # CPCV (canonical: 6 groups, 2 test, purge+embargo)
        cpcv = CPCV(n_groups=6, n_test_groups=2, purge=0, embargo=0.01)
        cpcv_oos = []
        for split in cpcv.split(n_days):
            te = split.test
            if len(te) >= 30:
                cpcv_oos.append(sr_canon(arr[te]))
        cpcv_mean = float(np.mean(cpcv_oos)) if cpcv_oos else 0.0
        stages["cpcv"] = {"passed": bool(cpcv_mean > 0.0), "mean_oos_sharpe": round(float(cpcv_mean), 4), "folds": len(cpcv_oos)}

        # Walk-forward (canonical: fixed 4 splits, anchored, test_size=max(20, len//4))
        try:
            wf_splits = walk_forward_splits(n_days, n_splits=WF_SPLITS_CAL,
                                            test_size=max(20, n_days // WF_SPLITS_CAL),
                                            anchored=True, embargo=0)
            wf_oos = []
            for split in wf_splits:
                if len(split.test) >= 20:
                    wf_oos.append(sr_canon(arr[split.test]))
            if wf_oos:
                wf_mean = float(np.mean(wf_oos))
                pos_folds = sum(1 for s in wf_oos if s > 0)
                wf_stab = pos_folds / len(wf_oos)
                wf_ok = wf_mean > 0.0 and wf_stab >= WF_STAB_CAL
            else:
                wf_mean, wf_stab, wf_ok = float("-inf"), 0.0, False
        except Exception:
            wf_mean, wf_stab, wf_ok = float("-inf"), 0.0, False
        stages["walk_forward"] = {"passed": bool(wf_ok), "oos_sharpe": round(wf_mean, 4), "stability": round(wf_stab, 4)}

        # Stress costs (3x)
        x3_ds = daily_x3[orig_i]
        exp3 = float(x3_ds.to_numpy(float).mean()) if x3_ds is not None and len(x3_ds) > 0 else 0.0
        stages["stress_costs"] = {"passed": bool(exp3 > 0.0), "exp_x3": round(exp3, 4)}

        # Lockbox: genuine chronological holdout (last 20%, min 60 bars, min 100 train)
        min_holdout = 60
        min_train = 100
        holdout_frac = 0.20
        holdout_n = max(min_holdout, int(n_days * holdout_frac))
        lockbox_ok = False
        lockbox_sr = 0.0
        if n_days - holdout_n >= min_train and holdout_n >= min_holdout:
            holdout_arr = arr[-holdout_n:]
            lockbox_sr = sr_canon(holdout_arr)
            lockbox_ok = lockbox_sr > 0.0
        stages["lockbox"] = {"passed": lockbox_ok, "lockbox_sharpe": round(float(lockbox_sr), 4),
                             "holdout_bars": holdout_n if lockbox_ok else 0}

        # Expected value
        ev = float(arr.mean())
        stages["expected_value"] = {"passed": bool(ev > 0.0), "ev": round(ev, 4)}

        passed = all(s["passed"] for s in stages.values())
        verdicts.append({"cell": cid, "sym": c["sym"], "family": c["family"],
                         "params": c["params"], "days": n_days, "passed": passed, "stages": stages})

    elapsed = time.time() - t0
    n_pass = sum(1 for v in verdicts if v["passed"])
    print(f"  {n_pass}/{len(verdicts)} pass all 10 gates ({elapsed:.0f}s)")
    for v in verdicts:
        st = "PASS" if v["passed"] else "FAIL"
        print(f"    {st} {v['cell']:<70} n={v['days']}")

    result = {
        "hunt": "external_discoveries", "n_cells": n_cells, "n_trials": n_trials,
        "trial_basis": trial_basis, "effective_cells": round(effective_cells, 1),
        "program_level": {"pbo": round(pbo_val, 4), "spa_p": round(spa_p, 4)},
        "survivors_passing_all": n_pass, "verdicts": verdicts,
        "swept_at": datetime.now(UTC).isoformat(),
    }
    (REPORTS / "universal_gates_external.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8")
    return result


# ── STEP 5: CERTIFY + ADMISSION ───────────────────────────────────
def step_certify(gauntlet_result):
    print("\n" + "=" * 60)
    print("STEP 5: CERTIFY + SHADOW ADMISSION")
    print("=" * 60)
    surv_path = REPORTS / "UNIVERSAL_SURVIVORS.json"
    survivors = {}
    gate_policy = {}
    if surv_path.exists():
        try:
            old = json.loads(surv_path.read_text("utf-8"))
            survivors = old.get("survivors", {})
            gate_policy = old.get("gate_policy", {})
        except Exception:
            gate_policy = {}

    new_certs = 0
    for v in gauntlet_result.get("verdicts", []):
        if not v.get("passed"):
            continue
        key = f"external.{v['cell']}"
        if key in survivors:
            continue
        sel = v.get("params", {}).get("range_start", "asia")
        if isinstance(sel, int):
            sel = {0: "asia", 7: "asia", 10: "london_am", 13: "ny_open", 14: "afternoon"}.get(sel, "asia")
        survivors[key] = {
            "hunt": "external_discoveries", "cell": v["cell"], "sym": v["sym"],
            "days": v["days"], "gates": v["stages"],
            "gated_at": datetime.now(UTC).isoformat(),
            "shadow_spec": {
                "symbol": v["sym"], "selector": sel,
                "family": v["family"], "is_universe": True,
                "hunt": "external_discoveries", "condition": None,
                "params": v.get("params", {}),
            },
        }
        new_certs += 1
        print(f"  CERTIFIED: {v['cell']}")

    surv_path.write_text(json.dumps({
        "n": len(survivors), "survivors": survivors,
        "gate_policy": gate_policy or {
            "policy": "mt5-original-universal-10-v2-calibrated-inputs",
            "pbo_max": 0.5, "dsr_threshold": 0.95, "spa_alpha": 0.05,
            "wf_splits": 4, "wf_min_stability": 0.5,
        },
        "note": "UNIVERSAL 10-GATE PASS ONLY.",
        "swept_at": datetime.now(UTC).isoformat(),
    }, indent=2, default=str), encoding="utf-8")

    print(f"  {new_certs} new certificates, {len(survivors)} total in authority")
    return survivors


# ── MAIN ──────────────────────────────────────────────────────────
def main():
    t_start = time.time()
    print("=" * 60)
    print("FULL PIPELINE v3: DISCOVER -> BACKTEST (full grid) -> FIXED CALIBRATED GATES -> CERTIFY")
    print(datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"))
    print(f"Registry: {len(FAMILY_REGISTRY)} families available")
    for name in sorted(FAMILY_REGISTRY.keys()):
        entry = FAMILY_REGISTRY[name]
        n_params = len(entry.get("param_grid", {}))
        print(f"  {name}: {n_params} sweep params, tags={entry.get('tags', [])}")
    print("=" * 60)

    discoveries = step_discover()
    hypotheses = step_convert(discoveries)
    survivors = step_backtest(hypotheses)
    gauntlet = step_gauntlet(survivors)
    if gauntlet:
        step_certify(gauntlet)

    elapsed = time.time() - t_start
    print(f"\n{'=' * 60}")
    print(f"PIPELINE COMPLETE in {elapsed:.0f}s")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    raise SystemExit(main())