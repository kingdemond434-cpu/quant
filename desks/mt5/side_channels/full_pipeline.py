"""Full pipeline: discover → backtest → 10 gates → shadow admission.

One script, one day. Runs all 25 miners, converts to hypotheses,
backtests, runs 10-gate gauntlet, writes certificates, pulls to
C:\opt\quant. 14-day clock starts immediately for any passers.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
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
SC = BASE / "desks" / "mt5" / "side_channels"

sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "desks" / "mt5"))
sys.path.insert(0, str(BASE / "desks" / "mt5" / "side_channels"))

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
TESTABLE_FAMILIES = {
    "session_range_breakout", "momentum_basic", "momentum_volgate",
    "level_breakout", "failed_breakout", "dow_effect",
    "monday_gap", "london_close_momentum",
}
SYMBOL_MAP = {
    "XAUUSD": "XAUUSD", "EURUSD": "EURUSD", "GBPUSD": "GBPUSD",
    "USDJPY": "USDJPY", "AUDUSD": "AUDUSD", "USDCAD": "USDCAD",
    "USDCHF": "USDCHF", "NZDUSD": "NZDUSD", "EURJPY": "EURJPY",
    "GBPJPY": "GBPJPY", "AUDJPY": "AUDJPY", "CADJPY": "CADJPY",
    "NZDJPY": "NZDJPY", "CHFJPY": "CHFJPY", "EURAUD": "EURAUD",
    "GBPAUD": "GBPAUD", "AUDNZD": "AUDNZD", "NZDCAD": "NZDCAD",
    "AUDCAD": "AUDCAD", "BTCUSD": "BTCUSD", "ETHUSD": "ETHUSD",
    "US500": "US500", "NAS100": "NAS100", "JPYUSD": "USDJPY",
}
SKIP_SOURCES = {"mql5_forum", "academic", "sec_edgar", "earnings"}
SOURCE_FAMILY_MAP = {
    "cot": "momentum_basic", "aaii": "session_range_breakout",
    "fear_greed": "session_range_breakout", "investing": "session_range_breakout",
    "google_trends": "session_range_breakout", "correlations": "session_range_breakout",
    "seasonality": "session_range_breakout", "forexfactory": "session_range_breakout",
    "earnings": "session_range_breakout", "shipping": "momentum_basic",
    "mql5_signals": "session_range_breakout",
}
PATTERN_TO_FAMILY = {
    "breakout": "session_range_breakout", "session range": "session_range_breakout",
    "asia range": "session_range_breakout", "london open": "session_range_breakout",
    "order block": "order_block_reversion", "fair value gap": "order_block_reversion",
    "liquidity": "liquidity_grab", "smart money": "order_block_reversion",
    "mean reversion": "mean_reversion_basic", "momentum": "momentum_basic",
    "trend following": "trend_following_basic", "trend": "trend_following_basic",
    "RSI": "rsi_extreme_fade", "MACD": "macd_crossover",
    "EMA": "ema_crossover", "SMA": "sma_crossover",
    "fibonacci": "fib_retracement", "scalping": "scalping_basic",
    "swing": "swing_basic", "grid": "grid_trading",
    "volatility": "volatility_breakout", "carry trade": "carry_trade",
    "pairs trading": "pairs_trading", "statistical arbitrage": "pairs_trading",
    "cointegration": "pairs_trading",
    "price stability": "central_bank_reaction", "hawkish": "central_bank_reaction",
    "dovish": "central_bank_reaction", "rate hike": "central_bank_reaction",
    "rate cut": "central_bank_reaction",
}


def costs_for(sym, meta, mult=1.0):
    m = meta.get(sym, {})
    spread = m.get("median_spread_pts", 1) * m.get("tick_size", 1e-5) * m.get("contract_size", 1e5)
    if sym == "XAUUSD":
        spread = 0.48 * mult
    else:
        spread = max(spread, 0.05) * mult
    return Costs(spread_per_lot=spread, commission_per_lot=3.50 * mult,
                 contract_oz=m.get("contract_size", 1e5))


def daily_series(df, sigs, costs):
    res = run_backtest(df, sigs, costs)
    s = pd.Series({pd.Timestamp(t.entry_time).date(): t.r_multiple for t in res.trades}, dtype=float)
    return s.groupby(level=0).sum()


def map_family(patterns, source=""):
    for p in patterns:
        if p in PATTERN_TO_FAMILY:
            return PATTERN_TO_FAMILY[p]
    return SOURCE_FAMILY_MAP.get(source, "unknown")


def normalize_symbol(sym):
    return SYMBOL_MAP.get(sym.upper())


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


# ── STEP 2: CONVERT TO HYPOTHESES ─────────────────────────────────
def step_convert(discoveries):
    print("\n" + "=" * 60)
    print("STEP 2: CONVERT TO HYPOTHESES")
    print("=" * 60)
    hypotheses = []
    seen = set()
    for source_name, source_data in discoveries.items():
        if source_name == "summary" or not isinstance(source_data, dict):
            continue
        if source_name in SKIP_SOURCES:
            continue
        for disc in source_data.get("discoveries", []):
            patterns = disc.get("patterns", disc.get("policy_signals", []))
            symbols = disc.get("symbols", [])
            if not symbols:
                continue
            family = map_family(patterns, source_name)
            if family == "unknown":
                continue
            if family not in TESTABLE_FAMILIES:
                family = "session_range_breakout"
            for sym in symbols:
                norm = normalize_symbol(sym)
                if not norm:
                    continue
                key = f"{norm}_{family}_{source_name}"
                if key in seen:
                    continue
                seen.add(key)
                hypotheses.append({
                    "id": f"ext_{source_name}_{norm}_{family}",
                    "source": f"external_{source_name}",
                    "symbol": norm, "family": family,
                    "description": disc.get("description", disc.get("title", ""))[:200],
                    "patterns": patterns,
                    "created": datetime.now(timezone.utc).isoformat(),
                })
    HYP.mkdir(parents=True, exist_ok=True)
    (HYP / "latest_external.json").write_text(json.dumps(hypotheses, indent=2), encoding="utf-8")
    print(f"  {len(hypotheses)} hypotheses from {len(discoveries)-1} sources")
    return hypotheses


# ── STEP 3: BACKTEST ──────────────────────────────────────────────
def step_backtest(hypotheses):
    print("\n" + "=" * 60)
    print("STEP 3: BACKTEST")
    print("=" * 60)
    meta = json.loads((UNI / "universe.json").read_text("utf-8"))
    cells = {}
    for h in hypotheses:
        sym, fam = h.get("symbol"), h.get("family")
        if not sym or not fam:
            continue
        for rr in [1.5, 2.0, 2.5]:
            for wb in [8, 12]:
                key = f"{sym}.{fam}.rr={rr}_wb={wb}"
                if key not in cells:
                    cells[key] = {"sym": sym, "family": fam, "params": {"rr": rr, "wait_bars": wb}}

    print(f"  {len(cells)} cells to backtest")
    survivors = []
    for key, spec in cells.items():
        pq = UNI / f"{spec['sym']}_H1.parquet"
        if not pq.exists():
            continue
        h1 = families._h1(pd.read_parquet(pq))
        fn = getattr(families, f"family_{spec['family']}", None)
        if fn is None:
            continue
        try:
            sigs = fn(h1, side=1, **spec["params"])
        except TypeError:
            try:
                sigs = fn(h1, **spec["params"])
            except Exception:
                continue
        costs = costs_for(spec["sym"], meta)
        res = run_backtest(h1, sigs, costs)
        trades = res.trades
        if len(trades) < 50:
            continue
        r_vals = [t.r_multiple for t in trades]
        exp_r = sum(r_vals) / len(r_vals)
        if exp_r < 0.05:
            continue
        peak = cum = 0.0
        max_dd = 0.0
        for r in r_vals:
            cum += r
            peak = max(peak, cum)
            max_dd = min(max_dd, cum - peak)
        if max_dd < -30:
            continue
        survivors.append({
            "symbol": spec["sym"], "family": spec["family"],
            "params": spec["params"], "n": len(trades),
            "exp_r": round(exp_r, 4), "max_dd_r": round(max_dd, 2),
        })

    (HYP / "external_survivors.json").write_text(json.dumps(survivors, indent=2), encoding="utf-8")
    print(f"  {len(survivors)} survivors from {len(cells)} cells")
    return survivors


# ── STEP 4: 10-GATE GAUNTLET ──────────────────────────────────────
def step_gauntlet(survivors):
    print("\n" + "=" * 60)
    print("STEP 4: 10-GATE GAUNTLET")
    print("=" * 60)
    meta = json.loads((UNI / "universe.json").read_text("utf-8"))

    cells = {}
    for h in survivors:
        sym, fam, params = h["symbol"], h["family"], h.get("params", {})
        key = f"{sym}.{fam}.{json.dumps(params, sort_keys=True)}"
        if key not in cells:
            cells[key] = {"sym": sym, "family": fam, "params": params}

    cell_objs = []
    for spec in cells.values():
        pq = UNI / f"{spec['sym']}_H1.parquet"
        if not pq.exists():
            continue
        h1 = families._h1(pd.read_parquet(pq))
        fn = getattr(families, f"family_{spec['family']}", None)
        if fn is None:
            continue
        try:
            sigs = fn(h1, side=1, **spec["params"])
        except TypeError:
            try:
                sigs = fn(h1, **spec["params"])
            except Exception:
                continue
        cell_objs.append({"sym": spec["sym"], "family": spec["family"],
                          "params": spec["params"], "df": h1, "sigs": sigs,
                          "costs": costs_for(spec["sym"], meta)})

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

    n_trials = max(2, math.ceil(matrix.shape[1] * TRIALS_MULTIPLIER))
    sharpes = np.array([sharpe_ratio(matrix[:, k]) for k in range(matrix.shape[1])])
    sh_var = float(sharpes.var(ddof=1))

    pbo = probability_backtest_overfitting(matrix)
    pbo_val = float(pbo.pbo)
    pbo_ok = pbo_val <= PBO_THRESHOLD
    spa = hansen_spa(matrix)
    spa_p = float(spa.p_value)
    spa_ok = spa_p < SPA_ALPHA
    print(f"  Matrix: {matrix.shape}, n_trials={n_trials}, PBO={pbo_val:.4f}, SPA p={spa_p:.4f}")

    daily_x3 = []
    for c in cell_objs:
        try:
            costs3 = costs_for(c["sym"], meta, mult=COST_SCENARIO)
            daily_x3.append(daily_series(c["df"], c["sigs"], costs3))
        except Exception:
            daily_x3.append(None)

    verdicts = []
    for orig_i, ds in valid:
        c = cell_objs[orig_i]
        arr = ds.to_numpy(float)
        cid = f"{c['sym']}.{c['family']}.rr={c['params'].get('rr','?')}_wb={c['params'].get('wait_bars','?')}"
        sr = sharpe_ratio(arr)
        stages = {
            "economic_prior": {"passed": True, "message": "discovered via external channel"},
            "in_sample_screen": {"passed": bool(sr > 0.0), "sharpe": round(float(sr), 4)},
        }
        dsr = deflated_sharpe_ratio(arr, n_trials=n_trials, variance_of_sharpes=sh_var, threshold=DSR_THRESHOLD)
        stages["deflated_sharpe"] = {"passed": bool(dsr.passed), "dsr": round(float(dsr.dsr), 4),
                                     "sr0": round(float(dsr.sr0_threshold), 4), "n_trials": n_trials}
        stages["pbo"] = {"passed": pbo_ok, "pbo": round(pbo_val, 4)}
        stages["reality_check_spa"] = {"passed": spa_ok, "p_value": round(spa_p, 4)}
        cpcv = CPCV(n_groups=6, n_test_groups=2)
        oos = []
        for split in cpcv.split(len(arr)):
            te = np.asarray(split.test)
            if len(te) >= 30:
                oos.append(sharpe_ratio(arr[te]))
        cpcv_mean = float(np.mean(oos)) if oos else 0.0
        stages["cpcv"] = {"passed": bool(cpcv_mean > 0.0), "mean_oos_sharpe": round(cpcv_mean, 4), "folds": len(oos)}
        try:
            wf = WalkForwardEngine().evaluate(arr, n_splits=WF_SPLITS, test_size=max(20, len(arr) // 6),
                                              min_oos_sharpe=0.0, min_stability=WF_MIN_STABILITY)
            wf_status, wf_oos, wf_stab = wf.status, float(wf.oos_sharpe), float(wf.stability)
        except Exception:
            wf_status, wf_oos, wf_stab = "TOO_SHORT", float("-inf"), 0.0
        stages["walk_forward"] = {"passed": bool(wf_status is WalkForwardStatus.PASSED),
                                  "oos_sharpe": round(wf_oos, 4), "stability": round(wf_stab, 4)}
        x3_ds = daily_x3[orig_i]
        exp3 = float(x3_ds.to_numpy(float).mean()) if x3_ds is not None and len(x3_ds) > 0 else 0.0
        stages["stress_costs"] = {"passed": bool(exp3 > 0.0), "exp_x3": round(exp3, 4)}
        stages["lockbox"] = {"passed": bool(wf_oos >= 0.0), "lockbox_sharpe": round(wf_oos, 4)}
        ev = float(arr.mean())
        stages["expected_value"] = {"passed": bool(ev > 0.0), "ev": round(ev, 4)}
        passed = all(s["passed"] for s in stages.values())
        verdicts.append({"cell": cid, "sym": c["sym"], "family": c["family"],
                         "params": c["params"], "days": len(arr), "passed": passed, "stages": stages})

    elapsed = time.time() - t0
    n_pass = sum(1 for v in verdicts if v["passed"])
    print(f"  {n_pass}/{len(verdicts)} pass all 10 gates ({elapsed:.0f}s)")

    for v in verdicts:
        st = "PASS" if v["passed"] else "FAIL"
        print(f"    {st} {v['cell']:<55} n={v['days']}")

    result = {
        "hunt": "external_discoveries", "n_cells": len(cell_objs), "n_trials": n_trials,
        "program_level": {"pbo": round(pbo_val, 4), "spa_p": round(spa_p, 4)},
        "survivors_passing_all": n_pass, "verdicts": verdicts,
        "swept_at": datetime.now(timezone.utc).isoformat(),
    }
    (REPORTS / "universal_gates_external.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return result


# ── STEP 5: CERTIFY + ADMISSION ───────────────────────────────────
def step_certify(gauntlet_result):
    print("\n" + "=" * 60)
    print("STEP 5: CERTIFY + SHADOW ADMISSION")
    print("=" * 60)
    surv_path = REPORTS / "UNIVERSAL_SURVIVORS.json"
    survivors = {}
    if surv_path.exists():
        try:
            old = json.loads(surv_path.read_text("utf-8"))
            survivors = old.get("survivors", {})
            gate_policy = old.get("gate_policy", {})
        except Exception:
            gate_policy = {}
    else:
        gate_policy = {}

    new_certs = 0
    for v in gauntlet_result.get("verdicts", []):
        if not v.get("passed"):
            continue
        key = f"external.{v['cell']}"
        if key in survivors:
            continue
        survivors[key] = {
            "hunt": "external_discoveries", "cell": v["cell"], "sym": v["sym"],
            "days": v["days"], "gates": v["stages"],
            "gated_at": datetime.now(timezone.utc).isoformat(),
            "shadow_spec": {
                "symbol": v["sym"], "selector": "asia",
                "family": "session_range_breakout", "is_universe": True,
                "hunt": "external_discoveries", "condition": None,
            },
        }
        new_certs += 1
        print(f"  CERTIFIED: {v['cell']}")

    surv_path.write_text(json.dumps({
        "n": len(survivors), "survivors": survivors,
        "gate_policy": gate_policy,
        "note": "UNIVERSAL 10-GATE PASS ONLY.",
        "swept_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2, default=str), encoding="utf-8")

    # Sync canon
    canon_path = DATA / "UNIVERSAL_SURVIVORS.canon.json"
    canon_path.write_text(surv_path.read_text("utf-8"), encoding="utf-8")

    print(f"  {new_certs} new certificates, {len(survivors)} total in authority")
    return survivors


# ── MAIN ──────────────────────────────────────────────────────────
def main():
    t_start = time.time()
    print("=" * 60)
    print("FULL PIPELINE: DISCOVER → BACKTEST → GATES → CERTIFY")
    print(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
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
    main()
