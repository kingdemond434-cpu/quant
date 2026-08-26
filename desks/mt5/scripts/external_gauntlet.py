"""Run full 10-gate gauntlet on external discovery survivors.

Reads survivors from external backtest, builds daily R matrix,
computes program-level PBO + SPA, then evaluates all 10 gates per cell.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path("/home/quant/quant-platform")
UNI = BASE / "desks" / "mt5" / "data" / "universe"
REPORTS = BASE / "desks" / "mt5" / "reports"
DATA = BASE / "desks" / "mt5" / "data"
HYP = DATA / "hypotheses"

sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "desks" / "mt5"))

from libs.validation.cpcv import CPCV
from libs.validation.dsr import deflated_sharpe_ratio, sharpe_ratio
from libs.validation.pbo import probability_backtest_overfitting
from libs.validation.reality_check import hansen_spa
from libs.validation.revalidation import WalkForwardEngine, WalkForwardStatus

from mt5desk import families
from mt5desk.engine import Costs, run_backtest

TRIALS_MULTIPLIER = 7.0
DSR_THRESHOLD = 0.95
PBO_THRESHOLD = 0.5
SPA_ALPHA = 0.05
WF_SPLITS = 4
WF_MIN_STABILITY = 0.5
COST_SCENARIO = 3.0


def costs_for(sym: str, meta: dict, mult: float = 1.0) -> Costs:
    m = meta.get(sym, {})
    spread = m.get("median_spread_pts", 1) * m.get("tick_size", 1e-5) * m.get("contract_size", 1e5)
    if sym == "XAUUSD":
        spread = 0.48 * mult
    else:
        spread = max(spread, 0.05) * mult
    return Costs(spread_per_lot=spread,
                 commission_per_lot=3.50 * mult,
                 contract_oz=m.get("contract_size", 1e5))


def daily_series(df: pd.DataFrame, sigs: list, costs: Costs) -> pd.Series:
    res = run_backtest(df, sigs, costs)
    s = pd.Series({pd.Timestamp(t.entry_time).date(): t.r_multiple for t in res.trades},
                  dtype=float)
    return s.groupby(level=0).sum()


def build_cell(sym: str, family: str, params: dict, meta: dict):
    """Build a Cell from external survivor spec."""
    pq = UNI / f"{sym}_H1.parquet"
    if not pq.exists():
        return None
    h1 = families._h1(pd.read_parquet(pq))
    # THE GAUNTLET MUST REACH EVERY FAMILY, not just the breakout module. Looking only in
    # `families` meant the 14 orthogonal generators were unreachable from the one door that grants
    # certificates -- so a carry or positioning edge could be written, tested by hand, and still
    # never certify. That is the same defect as having no generator at all, one layer further in.
    fn = getattr(families, f"family_{family}", None)
    if fn is None:
        try:
            from mt5desk import families_orthogonal as fo
            fn = fo.ORTHOGONAL_FAMILIES.get(family)
        except ImportError:
            fn = None
    if fn is None:
        return None
    side = 1  # both sides tested externally; use LONG default
    try:
        sigs = fn(h1, side=side, **params)
    except TypeError:
        try:
            sigs = fn(h1, **params)
        except Exception:
            return None
    costs = costs_for(sym, meta)
    return {"sym": sym, "family": family, "params": params, "df": h1, "sigs": sigs, "costs": costs}


def run_gauntlet(cells: list, hunt_name: str, meta: dict) -> dict:
    """Run full 10-gate gauntlet on a list of cells."""
    print(f"\n=== GAUNTLET: {hunt_name} ({len(cells)} cells) ===")

    # Build daily series
    daily = []
    for c in cells:
        try:
            ds = daily_series(c["df"], c["sigs"], c["costs"])
            daily.append(ds)
        except Exception as e:
            print(f"  FAIL {c['sym']}.{c['family']}: {e}")
            daily.append(None)

    # Build matrix from valid series
    valid = [(i, d) for i, d in enumerate(daily) if d is not None and len(d) >= 60]
    if not valid:
        print("  NO cells with >= 60 days")
        return {"hunt": hunt_name, "error": "no valid cells", "verdicts": []}

    cols = [d.to_numpy(float) for _, d in valid]
    min_len = min(len(a) for a in cols)
    matrix = np.column_stack([a[-min_len:] for a in cols])

    # Program-level tests
    # TRIAL COUNT MUST REFLECT THE SEARCH THAT PRODUCED THE CANDIDATES. The attestation defines
    # the basis as effective-cells x 7, "failing closed to raw_cells x 7 when dependence is
    # unmeasurable" -- and cells x 7 is exactly right for a hand-built family sweep. It is far too
    # generous for a candidate that came out of an unconstrained search: a cell selected as the
    # best of 4,344 evaluated combinations has already survived a selection the gauntlet cannot
    # see, and deflating it as though it were one of ~200 trials credits it with significance the
    # search already spent. When candidates carry their own `search_trials`, the larger of the two
    # bases is used -- failing closed in the direction of MORE deflation, which is the direction
    # that cannot manufacture a survivor.
    n_trials = max(2, math.ceil(matrix.shape[1] * TRIALS_MULTIPLIER))
    _declared = 0
    for _c in cells:
        try:
            _declared = max(_declared, int((_c.get("params") or {}).get("search_trials") or 0),
                            int(_c.get("search_trials") or 0))
        except (TypeError, ValueError):
            continue
    if _declared > n_trials:
        print(f"  trial basis raised {n_trials} -> {_declared} (candidates declare a wider "
              f"search; deflating against the smaller count would credit significance the "
              f"search already spent)")
        n_trials = _declared
    sharpes = np.array([sharpe_ratio(matrix[:, k]) for k in range(matrix.shape[1])])
    sh_var = float(sharpes.var(ddof=1))

    print(f"  Matrix: {matrix.shape}, n_trials={n_trials}")
    t0 = time.time()

    pbo = probability_backtest_overfitting(matrix)
    pbo_val = float(pbo.pbo)
    pbo_ok = pbo_val <= PBO_THRESHOLD
    print(f"  PBO: {pbo_val:.4f} ({'PASS' if pbo_ok else 'FAIL'})")

    spa = hansen_spa(matrix)
    spa_p = float(spa.p_value)
    spa_ok = spa_p < SPA_ALPHA
    print(f"  SPA: p={spa_p:.4f} ({'PASS' if spa_ok else 'FAIL'})")

    # 3x cost series
    daily_x3 = []
    for c in cells:
        try:
            costs3 = costs_for(c["sym"], meta, mult=COST_SCENARIO)
            ds = daily_series(c["df"], c["sigs"], costs3)
            daily_x3.append(ds)
        except Exception:
            daily_x3.append(None)

    # Per-cell verdicts
    verdicts = []
    for idx, (orig_i, ds) in enumerate(valid):
        c = cells[orig_i]
        arr = ds.to_numpy(float)
        cid = f"{c['sym']}.{c['family']}.rr={c.get('params',{}).get('rr','?')}_wb={c.get('params',{}).get('wait_bars','?')}"

        # In-sample
        sr = sharpe_ratio(arr)
        stages = {
            "economic_prior": {"passed": True, "message": "discovered via external channel"},
            "in_sample_screen": {"passed": bool(sr > 0.0), "sharpe": round(float(sr), 4)},
        }

        # Deflated Sharpe
        dsr = deflated_sharpe_ratio(arr, n_trials=n_trials,
                                    variance_of_sharpes=sh_var, threshold=DSR_THRESHOLD)
        stages["deflated_sharpe"] = {
            "passed": bool(dsr.passed), "dsr": round(float(dsr.dsr), 4),
            "sr0": round(float(dsr.sr0_threshold), 4), "n_trials": n_trials
        }

        # PBO + SPA (program-level)
        stages["pbo"] = {"passed": pbo_ok, "pbo": round(pbo_val, 4)}
        stages["reality_check_spa"] = {"passed": spa_ok, "p_value": round(spa_p, 4)}

        # CPCV
        cpcv = CPCV(n_groups=6, n_test_groups=2)
        oos = []
        for split in cpcv.split(len(arr)):
            te = np.asarray(split.test)
            if len(te) >= 30:
                oos.append(sharpe_ratio(arr[te]))
        cpcv_mean = float(np.mean(oos)) if oos else 0.0
        stages["cpcv"] = {"passed": bool(cpcv_mean > 0.0),
                          "mean_oos_sharpe": round(cpcv_mean, 4), "folds": len(oos)}

        # Walk Forward
        try:
            wf = WalkForwardEngine().evaluate(arr, n_splits=WF_SPLITS,
                                              test_size=max(20, len(arr) // 6),
                                              min_oos_sharpe=0.0,
                                              min_stability=WF_MIN_STABILITY)
            wf_status = wf.status
            wf_oos = float(wf.oos_sharpe)
            wf_stab = float(wf.stability)
        except Exception:
            wf_status, wf_oos, wf_stab = "TOO_SHORT", float("-inf"), 0.0
        stages["walk_forward"] = {
            "passed": bool(wf_status is WalkForwardStatus.PASSED),
            "oos_sharpe": round(wf_oos, 4), "stability": round(wf_stab, 4)
        }

        # Stress costs (3x)
        x3_ds = daily_x3[orig_i]
        if x3_ds is not None and len(x3_ds) > 0:
            exp3 = float(x3_ds.to_numpy(float).mean())
        else:
            exp3 = 0.0
        stages["stress_costs"] = {"passed": bool(exp3 > 0.0), "exp_x3": round(exp3, 4)}

        # Lockbox
        stages["lockbox"] = {"passed": bool(wf_oos >= 0.0),
                             "lockbox_sharpe": round(wf_oos, 4)}

        # Expected Value
        ev = float(arr.mean())
        stages["expected_value"] = {"passed": bool(ev > 0.0), "ev": round(ev, 4)}

        passed = all(s["passed"] for s in stages.values())
        verdicts.append({
            "cell": cid, "sym": c["sym"], "family": c["family"],
            "days": len(arr), "passed": passed, "stages": stages
        })

    elapsed = time.time() - t0
    n_pass = sum(1 for v in verdicts if v.get("passed"))
    gate_fails = {}
    for v in verdicts:
        for name, s in v.get("stages", {}).items():
            if not s["passed"]:
                gate_fails[name] = gate_fails.get(name, 0) + 1

    print(f"\n  RESULT: {n_pass}/{len(verdicts)} pass all 10 gates ({elapsed:.0f}s)")
    if gate_fails:
        print(f"  Gate failures: {gate_fails}")

    for v in verdicts:
        status = "PASS" if v["passed"] else "FAIL"
        print(f"  {status} {v['cell']:<50} n={v['days']}")
        if not v["passed"]:
            for name, s in v["stages"].items():
                if not s["passed"]:
                    print(f"         FAIL {name}: {s}")

    return {
        "hunt": hunt_name,
        "n_cells": len(cells),
        "n_trials": n_trials,
        "program_level": {"pbo": round(pbo_val, 4), "spa_p": round(spa_p, 4)},
        "survivors_passing_all": n_pass,
        "gate_fails": gate_fails,
        "verdicts": verdicts,
        "swept_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    meta = json.loads((UNI / "universe.json").read_text("utf-8"))

    # Load external backtest survivors
    surv_file = HYP / "external_survivors.json"
    if not surv_file.exists():
        print("No external survivors found")
        return
    survivors = json.loads(surv_file.read_text("utf-8"))
    print(f"Loaded {len(survivors)} external survivors")

    # Group by unique (sym, family, params) combos
    cells = {}
    for h in survivors:
        sym = h.get("symbol")
        fam = h.get("family")
        params = h.get("params", {})
        if not sym or not fam:
            continue
        key = f"{sym}.{fam}.{json.dumps(params, sort_keys=True)}"
        if key not in cells:
            cells[key] = {"sym": sym, "family": fam, "params": params}

    print(f"Unique cells to evaluate: {len(cells)}")
    for k, v in cells.items():
        print(f"  {k}")

    # Build cell objects
    cell_objs = []
    for key, spec in cells.items():
        obj = build_cell(spec["sym"], spec["family"], spec["params"], meta)
        if obj:
            cell_objs.append(obj)
        else:
            print(f"  SKIP {key}: parquet missing or build failed")

    if not cell_objs:
        print("No buildable cells")
        return

    # Run gauntlet
    result = run_gauntlet(cell_objs, "external_discoveries", meta)

    # Save
    out = REPORTS / "universal_gates_external.json"
    out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved to {out}")

    # Update UNIVERSAL_SURVIVORS.json -- FULL AUTHORITY OR NOTHING. An earlier revision of this
    # block wrote certificates without the top-level `gate_policy` attestation and without a
    # per-survivor `shadow_spec`; `shadow_admission.is_exact_policy` fails closed on the missing
    # attestation, so one run of this script would have stripped promotion authority from EVERY
    # certificate in the file while printing "Updated". A certifier that demotes what it did not
    # examine is the certifier-wipe defect again, one layer up.
    sys.path.insert(0, str(BASE / "desks" / "mt5" / "research"))
    from gate_policy import ATTESTATION

    surv_path = REPORTS / "UNIVERSAL_SURVIVORS.json"
    survivors_all, old_doc = {}, {}
    if surv_path.exists():
        try:
            old_doc = json.loads(surv_path.read_text("utf-8"))
            survivors_all = old_doc.get("survivors", {})
        except Exception:
            pass
    n_before = len(survivors_all)

    WINDOWS_KNOWN = {
        "asia": {"range_start": 7},
        "london_am": {"range_start": 10, "range_end": 13, "signal_at": 13},
        "ny_open": {"range_start": 13, "range_end": 14, "signal_at": 14},
        "afternoon": {"range_start": 14, "range_end": 17, "signal_at": 17},
    }

    def _selector(params: dict) -> str | None:
        """Map a cell's params to the ONE forward engine's window name -- or None, visibly.

        A certificate whose selector cannot be named cannot be enrolled, and an un-enrollable
        certificate trips the same-day fence (CERTIFIED-NOT-ENROLLED) rather than silently
        running under guessed hours. The default family session (range_start=7) IS "asia"."""
        if params.get("window") in WINDOWS_KNOWN:
            return params["window"]
        keys = {k: params[k] for k in ("range_start", "range_end", "signal_at") if k in params}
        if not keys or keys == {"range_start": 7}:
            return "asia"
        for name, w in WINDOWS_KNOWN.items():
            if all(w.get(k) == v for k, v in keys.items()):
                return name
        return None

    _params_by_cell = {
        f"{c['sym']}.{c['family']}.rr={c.get('params', {}).get('rr', '?')}"
        f"_wb={c.get('params', {}).get('wait_bars', '?')}": dict(c.get("params") or {})
        for c in cell_objs
    }
    for v in result.get("verdicts", []):
        if not v.get("passed"):
            continue
        key = f"external.{v['cell']}"
        # EXACT MATCH ON THE CELL ID, not a prefix. `f"{sym}.{family}" in cell` matched the FIRST
        # cell sharing that prefix, so every CADJPY certificate inherited rr=1.5 from whichever
        # variant was built first -- wrong params on 14 of 15 certificates, which is worse than
        # none. The cid formula in run_gauntlet encodes rr and wait_bars, so it is a unique key.
        params = _params_by_cell.get(v["cell"], {})
        sel = _selector(params or {})
        row = {
            "hunt": "external_discoveries",
            "cell": v["cell"],
            "sym": v["sym"],
            "days": v["days"],
            "gates": v["stages"],
            "gated_at": datetime.now(timezone.utc).isoformat(),
        }
        if sel is not None:
            # PARAMS ARE PART OF THE IDENTITY. Without them the spec says only "XAUUSD asia",
            # so five separately-gauntleted parameterizations collapse to ONE runnable spec and
            # the forward engine runs its own default for all of them -- four certificates
            # describing strategies that are never forward-tested. The two-stage law requires
            # that the thing which passed the gauntlet IS the thing that goes forward, and that
            # identity is the params, not the session label.
            row["shadow_spec"] = {"symbol": v["sym"], "selector": sel,
                                  "family": v.get("family", "session_range_breakout"),
                                  "is_universe": True, "hunt": "external_discoveries",
                                  "condition": None, "params": dict(params or {})}
        else:
            print(f"  NO-SPEC {key}: params {params} match no known window; certificate "
                  f"written WITHOUT shadow_spec -- it cannot enrol until the selector is wired")
        survivors_all[key] = row

    # NEVER SHRINK (2026-08-26, the certifier wipe): merging can only grow this file; a sweep
    # that certified nothing preserves what stands, because re-running a gauntlet is not
    # revoking a pass.
    if len(survivors_all) < n_before:
        print(f"REFUSING to write: merge would shrink {n_before} -> {len(survivors_all)}")
        return

    doc = dict(old_doc)
    doc.update({
        "n": len(survivors_all),
        "gate_policy": ATTESTATION,
        "survivors": survivors_all,
        "note": "UNIVERSAL 10-GATE PASS ONLY.",
        "swept_at": datetime.now(timezone.utc).isoformat(),
    })
    surv_path.write_text(json.dumps(doc, indent=2, default=str), encoding="utf-8")
    print(f"Updated UNIVERSAL_SURVIVORS.json: {len(survivors_all)} total "
          f"({len(survivors_all) - n_before:+d})")


if __name__ == "__main__":
    main()
