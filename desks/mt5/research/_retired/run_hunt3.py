"""Hunt #3: full-grid sweep of every family, audit survivors, cost stress."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from mt5desk import families
from mt5desk.data import load_cot, load_fx_h4, load_gold
from mt5desk.engine import Costs, run_backtest, walk_forward_splits
from mt5desk.config import DATA, REPORTS, desk_root  # noqa: E402

COSTS = Costs(spread_per_lot=0.48, commission_per_lot=3.50, contract_oz=100.0)
STRESS = Costs(spread_per_lot=1.00, commission_per_lot=7.00, contract_oz=100.0)

GRIDS: dict[str, list[dict]] = {
    "usd_session_shock": [
        {"fx": "EURUSD", "london_start": 7, "london_end": 16, "shock_atr": 2.0, "ttl_bars": 12, "rr": 1.8},
        {"fx": "EURUSD", "london_start": 7, "london_end": 16, "shock_atr": 1.5, "ttl_bars": 8, "rr": 1.8},
        {"fx": "EURUSD", "london_start": 8, "london_end": 15, "shock_atr": 2.0, "ttl_bars": 12, "rr": 2.0},
        {"fx": "EURUSD", "london_start": 7, "london_end": 21, "shock_atr": 2.5, "ttl_bars": 12, "rr": 1.8},
        {"fx": "GBPUSD", "london_start": 7, "london_end": 16, "shock_atr": 2.0, "ttl_bars": 12, "rr": 1.8},
        {"fx": "USDJPY", "london_start": 7, "london_end": 16, "shock_atr": 2.0, "ttl_bars": 12, "rr": 1.8},
    ],
    "comex_settlement_effect": [
        {"settle_hour": 20, "vol_floor": 0.5, "move_thresh": 0.75, "ttl_bars": 12, "rr": 1.6},
        {"settle_hour": 20, "vol_floor": 0.5, "move_thresh": 1.0, "ttl_bars": 12, "rr": 1.6},
        {"settle_hour": 20, "vol_floor": 0.75, "move_thresh": 0.75, "ttl_bars": 12, "rr": 1.6},
        {"settle_hour": 22, "vol_floor": 0.5, "move_thresh": 0.75, "ttl_bars": 12, "rr": 1.6},
        {"settle_hour": 22, "vol_floor": 0.5, "move_thresh": 1.0, "ttl_bars": 12, "rr": 1.6},
        {"settle_hour": 20, "vol_floor": 0.5, "move_thresh": 1.5, "ttl_bars": 12, "rr": 2.0},
    ],
    "spread_state_avoidance": [
        {"high_spread_frac": 0.5, "mom_n": 4, "ttl_bars": 10, "rr": 1.8},
        {"high_spread_frac": 0.7, "mom_n": 4, "ttl_bars": 10, "rr": 1.8},
        {"high_spread_frac": 0.5, "mom_n": 6, "ttl_bars": 12, "rr": 1.8},
    ],
    "momentum_volgate": [
        {"mom_n": 6, "vol_gate_q": 0.4, "ttl_bars": 12, "rr": 1.8, "mom_thresh": 0.0012},
        {"mom_n": 6, "vol_gate_q": 0.6, "ttl_bars": 12, "rr": 1.8, "mom_thresh": 0.0012},
        {"mom_n": 8, "vol_gate_q": 0.4, "ttl_bars": 12, "rr": 2.0, "mom_thresh": 0.0015},
    ],
    "session_range_breakout": [
        {"range_start": 7, "wait_bars": 8, "rr": 2.0, "ttl_bars": 12},
        {"range_start": 6, "wait_bars": 12, "rr": 2.0, "ttl_bars": 12},
        {"range_start": 7, "wait_bars": 12, "rr": 2.0, "ttl_bars": 12},
        {"range_start": 13, "range_end": 14, "signal_at": 14, "wait_bars": 8, "rr": 2.0, "ttl_bars": 12},
        {"range_start": 13, "range_end": 14, "signal_at": 14, "wait_bars": 12, "rr": 2.0, "ttl_bars": 12},
    ],
    "asia_momentum": [
        {"asia_start": 0, "asia_end": 7, "mom_thresh": 0.35, "ttl_bars": 12, "rr": 1.8},
        {"asia_start": 0, "asia_end": 7, "mom_thresh": 0.25, "ttl_bars": 12, "rr": 1.8},
        {"asia_start": 0, "asia_end": 7, "mom_thresh": 0.5, "ttl_bars": 12, "rr": 1.8},
        {"asia_start": 0, "asia_end": 7, "mom_thresh": 0.35, "ttl_bars": 8, "rr": 2.0},
    ],
    "dow_effect": [
        {"dow_long": 0, "dow_short": 3},
        {"dow_long": 4, "dow_short": 1},
    ],
}


def run_one(name: str, params: dict, h1: pd.DataFrame, fx: dict) -> list:
    if name == "usd_session_shock":
        return families.family1_usd_session_shock(h1, fx[params["fx"]], **{
            k: v for k, v in params.items() if k != "fx"})
    if name == "comex_settlement_effect":
        return families.family4_comex_settlement_effect(h1, **params)
    if name == "spread_state_avoidance":
        return families.family7_spread_state_avoidance(h1, **params)
    if name == "momentum_volgate":
        return families.family_momentum_volgate(h1, **params)
    if name == "session_range_breakout":
        return families.family_session_range_breakout(h1, **params)
    if name == "asia_momentum":
        return families.family_asia_momentum(h1, **params)
    if name == "dow_effect":
        return families.family_dow_effect(h1, **params)
    raise KeyError(name)


def audit(h1: pd.DataFrame, sigs: list) -> dict:
    full = run_backtest(h1, sigs, COSTS)
    st = full.stats()
    if st["n"] >= 60 and st["t_stat"] > 2.0 and st["expectancy_r"] > 0:
        stressed = run_backtest(h1, sigs, STRESS).stats()
        splits = walk_forward_splits(len(h1), folds=4)
        sig_locs = np.searchsorted(
            h1.index.to_numpy().astype("datetime64[ns]").astype("int64"),
            np.array([pd.Timestamp(s.time).value for s in sigs], dtype="int64"),
        )
        oos_exps = []
        for (t0, t1, v1, o0, o1) in splits:
            oos_sigs = [s2 for s2, sl in zip(sigs, sig_locs) if o0 <= sl < o1]
            oos = run_backtest(h1.iloc[o0:o1], oos_sigs, COSTS).stats()
            if oos["n"] >= 10:
                oos_exps.append(round(oos["expectancy_r"], 4))
        return {
            "n": st["n"], "exp": round(st["expectancy_r"], 4), "t": round(st["t_stat"], 2),
            "pf": round(st["profit_factor"], 3), "win": round(st["win_rate"], 3),
            "maxdd": round(st["max_dd_r"], 2),
            "exp_stressed": round(stressed["expectancy_r"], 4),
            "oos": oos_exps,
        }
    return {"n": st["n"], "exp": round(st["expectancy_r"], 4),
            "t": round(st["t_stat"], 2), "pf": round(st["profit_factor"], 3),
            "maxdd": round(st["max_dd_r"], 2), "exp_stressed": None, "oos": []}


def main() -> None:
    print("== MT5 RESEARCH DESK :: HUNT #3 (full grid) ==")
    gold = load_gold()
    h1 = families._h1(gold.h1)
    fx = {sym: load_fx_h4(sym) for sym in ["EURUSD", "GBPUSD", "USDJPY"]}
    fx = {k: v for k, v in fx.items() if v is not None and len(v) > 300}
    print(f"H1 bars: {len(h1)} | fx available: {list(fx)}")

    rows: list[dict] = []
    for name, grid in GRIDS.items():
        for params in grid:
            sigs = run_one(name, params, h1, fx)
            a = audit(h1, sigs)
            a.update({"family": name, "params": params})
            rows.append(a)
            flag = "PASS" if a["oos"] and a["exp_stressed"] is not None and a["exp_stressed"] > 0 else ("edge?" if a["t"] > 2 else "fail")
            print(f"[{name} {params}] n={a['n']} exp={a['exp']}R t={a['t']} "
                  f"PF={a['pf']} maxDD={a['maxdd']}R stressed={a['exp_stressed']} "
                  f"oos={a['oos']} -> {flag}")

    surv = [r for r in rows if r["oos"] and r["exp_stressed"] is not None and r["exp_stressed"] > 0]
    print(f"\nSURVIVORS (t>2, n>=60, cost-stress positive, WF OOS positive): {len(surv)}")
    for r in sorted(surv, key=lambda x: -x["t"]):
        print(f"  {r['family']} {r['params']}: exp={r['exp']}R t={r['t']} "
              f"PF={r['pf']} maxDD={r['maxdd']}R stressed={r['exp_stressed']} oos={r['oos']}")

    report = {
        "at": datetime.now(tz=UTC).isoformat(),
        "costs": {"measured": {"spread": 0.48, "commission": 3.50},
                  "stress": {"spread": 1.00, "commission": 7.00}},
        "grid": {k: v for k, v in GRIDS.items()},
        "rows": rows,
        "survivors": surv,
    }
    out = str(REPORTS / "hunt3.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"report -> {out}")


if __name__ == "__main__":
    main()