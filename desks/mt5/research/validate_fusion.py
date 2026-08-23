"""Fusion cost audit + re-validation.

Run AFTER installing/logging into the Fusion MT5 terminal and setting
data/terminal_path.txt to the Fusion terminal64.exe.

  python research/validate_fusion.py               # audit only (no changes)
  python research/validate_fusion.py --apply       # write Fusion profile into
                                                   # universe.json (backup kept)
  python research/validate_fusion.py --validate    # re-run batteries of gold
                                                   # book + hunt12 survivor
                                                   # cells under Fusion costs

Order: audit -> review -> --apply -> --validate. If spreads are LOWER or equal
to recorded (expected on ECN Zero), the desk passes unchanged; if materially
higher, sleeves must be re-approved before pointing the gateway at Fusion.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mt5desk.config import terminal_path  # noqa: E402
from mt5desk.engine import Costs, run_backtest  # noqa: E402
from mt5desk import families  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"
META_FILE = UNI / "universe.json"
AUDIT = BASE / "reports" / "fusion_costs_audit.json"
VAL = BASE / "reports" / "fusion_validation.json"

GOLD_WINDOWS = {
    "asia": dict(range_start=7, wait_bars=12, rr=2.0, ttl_bars=12),
    "london_am": dict(range_start=10, range_end=13, signal_at=13, wait_bars=8, rr=2.0, ttl_bars=12),
    "ny_open": dict(range_start=13, range_end=14, signal_at=14, wait_bars=12, rr=2.0, ttl_bars=12),
    "afternoon": dict(range_start=14, range_end=17, signal_at=17, wait_bars=8, rr=2.0, ttl_bars=12),
}
E_MAX_9 = 1.49
# Fusion Zero published contract: USD 2.25/lot/side, USD 4.50 round turn.
FUSION_COMMISSION = 2.25


def connect() -> bool:
    import MetaTrader5 as mt5  # noqa: PLC0415
    if mt5.terminal_info() is None:
        if not mt5.initialize(path=terminal_path()):
            print(f"init failed: {mt5.last_error()} (is the Fusion terminal logged in?)")
            return False
    ti = mt5.terminal_info()
    ai = mt5.account_info()
    print(f"terminal: {ti.name} | account {ai.login} | balance {ai.balance}")
    if ai.trade_mode != 0:
        print(f"WARNING: trade_mode={ai.trade_mode} (0=FULL needed; 2=CLOSEONLY blocks orders)")
    return True


def live_spreads() -> dict:
    import MetaTrader5 as mt5  # noqa: PLC0415
    meta = json.loads(META_FILE.read_text(encoding="utf-8"))
    out = {}
    for sym in meta:
        info = mt5.symbol_info(sym)
        if info is None:
            print(f"{sym:8s} not offered on this broker")
            continue
        pts = []
        for _ in range(10):
            si = mt5.symbol_info(sym)
            if si is not None:
                pts.append(float(si.spread))
            time.sleep(0.35)
        med = float(np.median(pts)) if pts else float("nan")
        out[sym] = {
            "live_spread_pts": med,
            "recorded_spread_pts": meta[sym]["median_spread_pts"],
            "live_contract": float(info.trade_contract_size),
            "live_tick_size": float(info.trade_tick_size),
            "live_tick_value": float(info.trade_tick_value),
            "live_min_volume": float(info.volume_min),
            "volume_step": float(info.volume_step),
        }
        delta = med - meta[sym]["median_spread_pts"]
        print(f"{sym:8s} spread pts live={med:6.1f} recorded={meta[sym]['median_spread_pts']:6.1f} "
              f"delta={delta:+6.1f}")
    return out


def audit() -> None:
    if not connect():
        sys.exit(2)
    profile = live_spreads()
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT.write_text(json.dumps({"audited_at": datetime.now(timezone.utc).isoformat(),
                                 "commission_per_lot": FUSION_COMMISSION,
                                 "profile": profile}, indent=2), encoding="utf-8")
    worse = [s for s, p in profile.items() if p["live_spread_pts"] > p["recorded_spread_pts"] * 1.25]
    print(f"\naudit -> {AUDIT}")
    if worse:
        print(f"NOTE: {len(worse)} symbols more than 25% worse: {worse}")
    else:
        print("costs OK: no symbol >25% worse than recorded")


def apply() -> None:
    if not AUDIT.exists():
        print("run audit first")
        sys.exit(2)
    data = json.loads(AUDIT.read_text(encoding="utf-8"))["profile"]
    meta = json.loads(META_FILE.read_text(encoding="utf-8"))
    META_FILE.with_suffix(".json.bak").write_text(
        json.dumps(meta, indent=2), encoding="utf-8")
    changed = []
    for sym, p in data.items():
        if sym not in meta:
            continue
        meta[sym]["median_spread_pts"] = p["live_spread_pts"]
        meta[sym]["contract_size"] = p["live_contract"]
        meta[sym]["tick_size"] = p["live_tick_size"]
        meta[sym]["tick_value"] = p["live_tick_value"]
        meta[sym]["min_volume"] = p["live_min_volume"]
        meta[sym]["volume_step"] = p["volume_step"]
        meta[sym]["broker"] = "fusion"
        changed.append(sym)
    META_FILE.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"universe.json updated for {len(changed)} symbols (backup: universe.json.bak)")


def fusion_costs(sym: str, profile: dict) -> Costs:
    p = profile.get(sym, {})
    # Honest baseline: cross the measured spread entering and exiting. The old XAUUSD=0.48
    # special case repeated the per-ounce/per-lot unit defect fixed in Costs.from_symbol().
    spread = max(
        2.0 * p.get("live_spread_pts", 0.5) * p.get("live_tick_size", 1e-5)
        * p.get("live_contract", 100_000), 0.05)
    return Costs(spread_per_lot=spread, commission_per_lot=FUSION_COMMISSION,
                 contract_oz=p.get("live_contract", 100_000))


def gold_battery(h1: pd.DataFrame, sigs: list, costs: Costs) -> dict:
    r = run_backtest(h1, sigs, costs).stats()
    r2 = run_backtest(h1, sigs, Costs(costs.spread_per_lot * 3,
                                      costs.commission_per_lot,
                                      costs.contract_oz)).stats()
    idx_ns = h1.index.to_numpy().astype("datetime64[ns]").astype("int64")
    sig_ns = np.array([pd.Timestamp(s.time).value for s in sigs], dtype="int64")
    sig_locs = np.searchsorted(idx_ns, sig_ns)
    n = len(h1)
    fold = n // 3
    wf = []
    for k in range(3):
        o0, o1 = k * fold, (k + 1) * fold if k < 2 else n
        sub = [s for s, sl in zip(sigs, sig_locs) if o0 <= sl < o1]
        rr = run_backtest(h1.iloc[o0:o1], sub, costs)
        wf.append(float(np.mean([t.r_multiple for t in rr.trades])) if rr.n >= 20 else np.nan)
    defl = r["t_stat"] - E_MAX_9
    gate = (r["n"] > 60 and defl > 2 and r["profit_factor"] > 1.05
            and r["max_dd_r"] > -30
            and len(wf) == 3 and all(w == w and w > 0 for w in wf)
            and r2["expectancy_r"] > 0 and r2["t_stat"] > 1.5)
    return dict(n=r["n"], exp=r["expectancy_r"], t=r["t_stat"], defl=defl,
                pf=r["profit_factor"], maxdd=r["max_dd_r"], wf=wf, gate=bool(gate))


def validate() -> None:
    import MetaTrader5 as mt5  # noqa: PLC0415
    if not connect():
        sys.exit(2)
    profile = live_spreads()
    out = {"validated_at": datetime.now(timezone.utc).isoformat(),
           "commission_per_lot": FUSION_COMMISSION, "cells": []}

    h1 = pd.read_parquet(UNI / "XAUUSD_H1.parquet")
    h1 = families._h1(h1)
    gold_costs = fusion_costs("XAUUSD", profile)
    for wname, wp in GOLD_WINDOWS.items():
        sigs = families.family_session_range_breakout(h1, **wp)
        b = gold_battery(h1, sigs, gold_costs)
        out["cells"].append(dict(sym="XAUUSD", win=wname, state="base", **b))
        print(f"XAUUSD {wname:<10} base     n={b['n']:5d} exp={b['exp']:+.3f} "
              f"PF={b['pf']:.2f} {'PASS' if b['gate'] else 'fail'}")

    from research.run_hunt12 import battery as h12_battery  # noqa: PLC0415
    from research.run_hunt12 import WINDOWS as H12_WINDOWS  # noqa: PLC0415
    from research.run_hunt12 import STATES, day_states  # noqa: PLC0415
    partial = BASE / "reports" / "hunt12_partial.json"
    if partial.exists():
        saved = json.loads(partial.read_text(encoding="utf-8"))
        for cell in saved.get("all", []):
            if not cell.get("gate"):
                continue
            sym, wname, st_name = cell["sym"], cell["win"], cell["state"]
            ch1 = pd.read_parquet(UNI / f"{sym}_H1.parquet")
            ch1 = families._h1(ch1)
            costs = fusion_costs(sym, profile)
            sigs = families.family_session_range_breakout(ch1, **H12_WINDOWS[wname])
            sdays = [pd.Timestamp(s.time).date() for s in sigs]
            states = day_states(ch1)
            sub = [s for s, d in zip(sigs, sdays) if states.get(d) == st_name]
            b = h12_battery(ch1, sub, costs)
            out["cells"].append(dict(sym=sym, win=wname, state=st_name, **b))
            print(f"{sym:>8} {wname:<10} {st_name:<12} n={b['n']:5d} exp={b['exp']:+.3f} "
                  f"PF={b['pf']:.2f} {'PASS' if b['gate'] else 'fail'}")
    mt5.shutdown()
    VAL.parent.mkdir(parents=True, exist_ok=True)
    VAL.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    fails = [c for c in out["cells"] if not c["gate"]]
    print(f"\n{len(out['cells']) - len(fails)}/{len(out['cells'])} cells PASS under Fusion costs")
    if fails:
        print("FAILED:", [(c["sym"], c["win"], c["state"]) for c in fails])


if __name__ == "__main__":
    args = set(sys.argv[1:])
    if "--apply" in args:
        apply()
    elif "--validate" in args:
        validate()
    else:
        audit()
