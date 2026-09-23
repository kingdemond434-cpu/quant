"""Hunt #4: more sleeves - extra breakout windows, Monday gap, close momentum."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from mt5desk import families
from mt5desk.data import load_gold
from mt5desk.engine import Costs, run_backtest, walk_forward_splits
from mt5desk.config import DATA, REPORTS, desk_root  # noqa: E402

COSTS = Costs(spread_per_lot=0.48, commission_per_lot=3.50, contract_oz=100.0)
STRESS = Costs(spread_per_lot=1.00, commission_per_lot=7.00, contract_oz=100.0)

GRIDS: dict[str, list[dict]] = {
    "session_range_breakout": [
        {"range_start": 13, "range_end": 14, "signal_at": 14, "wait_bars": 12, "rr": 2.0, "ttl_bars": 12},
        {"range_start": 10, "range_end": 13, "signal_at": 13, "wait_bars": 8, "rr": 2.0, "ttl_bars": 12},
        {"range_start": 14, "range_end": 17, "signal_at": 17, "wait_bars": 8, "rr": 2.0, "ttl_bars": 12},
        {"range_start": 7, "wait_bars": 12, "rr": 2.0, "ttl_bars": 12, "spread_gate": True},
        {"range_start": 13, "range_end": 14, "signal_at": 14, "wait_bars": 12, "rr": 2.0, "ttl_bars": 12, "spread_gate": True},
    ],
    "monday_gap": [
        {"mode": "momentum", "rr": 1.8, "ttl_bars": 12},
        {"mode": "fade", "rr": 1.8, "ttl_bars": 12},
        {"mode": "momentum", "rr": 2.0, "ttl_bars": 24},
        {"mode": "fade", "rr": 2.0, "ttl_bars": 24},
    ],
    "london_close_momentum": [
        {"lookback": 2, "mom_thresh": 0.3, "ttl_bars": 4, "rr": 1.5},
        {"lookback": 2, "mom_thresh": 0.5, "ttl_bars": 4, "rr": 1.5},
        {"lookback": 3, "mom_thresh": 0.3, "ttl_bars": 4, "rr": 1.5},
    ],
}


def run_one(name: str, params: dict, h1: pd.DataFrame) -> list:
    if name == "session_range_breakout":
        return families.family_session_range_breakout(h1, **params)
    if name == "monday_gap":
        return families.family_monday_gap(h1, **params)
    if name == "london_close_momentum":
        return families.family_london_close_momentum(h1, **params)
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
            "pf": round(st["profit_factor"], 3), "maxdd": round(st["max_dd_r"], 2),
            "exp_stressed": round(stressed["expectancy_r"], 4), "oos": oos_exps,
        }
    return {"n": st["n"], "exp": round(st["expectancy_r"], 4),
            "t": round(st["t_stat"], 2), "pf": round(st["profit_factor"], 3),
            "maxdd": round(st["max_dd_r"], 2), "exp_stressed": None, "oos": []}


def main() -> None:
    print("== MT5 RESEARCH DESK :: HUNT #4 (sleeve hunt) ==")
    gold = load_gold()
    h1 = families._h1(gold.h1)
    rows = []
    for name, grid in GRIDS.items():
        for params in grid:
            sigs = run_one(name, params, h1)
            a = audit(h1, sigs)
            a.update({"family": name, "params": params})
            rows.append(a)
            flag = "PASS" if a["oos"] and a["exp_stressed"] is not None and a["exp_stressed"] > 0 else ("edge?" if a["t"] > 2 else "fail")
            print(f"[{name} {params}] n={a['n']} exp={a['exp']}R t={a['t']} "
                  f"PF={a['pf']} maxDD={a['maxdd']}R stressed={a['exp_stressed']} "
                  f"oos={a['oos']} -> {flag}")

    surv = [r for r in rows if r["oos"] and r["exp_stressed"] is not None and r["exp_stressed"] > 0]
    print(f"\nSURVIVORS: {len(surv)}")
    for r in sorted(surv, key=lambda x: -x["t"]):
        print(f"  {r['family']} {r['params']}: exp={r['exp']}R t={r['t']} "
              f"PF={r['pf']} maxDD={r['maxdd']}R stressed={r['exp_stressed']} oos={r['oos']}")

    report = {"at": datetime.now(tz=UTC).isoformat(), "rows": rows, "survivors": surv}
    out = str(REPORTS / "hunt4.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"report -> {out}")


if __name__ == "__main__":
    main()