"""Run the full MT5 research hunt: all families, walk-forward, costed, reported."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from mt5desk import families
from mt5desk.data import load_fx_h4, load_gold
from mt5desk.engine import Costs, run_backtest, walk_forward_splits
from mt5desk.config import DATA, REPORTS, desk_root  # noqa: E402

H1_UNIVERSE = [
    "usd_session_shock",
    "comex_settlement_effect",
    "spread_state_avoidance",
    "momentum_volgate",
    "session_range_breakout",
]


def run_family(name: str, df: pd.DataFrame, fx: pd.DataFrame | None) -> list:
    if name == "usd_session_shock":
        return families.family1_usd_session_shock(df, fx)
    if name == "comex_settlement_effect":
        return families.family4_comex_settlement_effect(df)
    if name == "spread_state_avoidance":
        return families.family7_spread_state_avoidance(df)
    if name == "momentum_volgate":
        return families.family_momentum_volgate(df)
    if name == "session_range_breakout":
        return families.family_session_range_breakout(df)
    raise KeyError(name)


def main() -> None:
    print("== MT5 RESEARCH DESK :: HUNT #1 ==")
    print("loading gold data...")
    gold = load_gold()
    h1 = gold.h1
    fx = load_fx_h4("EURUSD")
    print(f"H1 bars: {len(h1)} | {h1.index.min()} -> {h1.index.max()}")
    print(f"EURUSD H4 bars: {len(fx) if fx is not None else 0}")

    costs = Costs(spread_per_lot=0.48, commission_per_lot=3.50, contract_oz=100.0)
    results: dict = {}
    for name in H1_UNIVERSE:
        sigs = run_family(name, h1, fx)
        full = run_backtest(h1, sigs, costs)
        st = full.stats()
        # walk-forward
        splits = walk_forward_splits(len(h1), folds=4)
        wf_rows = []
        sig_locs = np.searchsorted(
            h1.index.to_numpy().astype("datetime64[ns]").astype("int64"),
            np.array([pd.Timestamp(s.time).value for s in sigs], dtype="int64"),
        )
        for (t0, t1, v1, o0, o1) in splits:
            sub = h1.iloc[t0:t1]
            sub_sigs = [s for s, sl in zip(sigs, sig_locs) if t0 <= sl < t1]
            res = run_backtest(sub, sub_sigs, costs)
            s = res.stats()
            oos_sigs = [s2 for s2, sl in zip(sigs, sig_locs) if o0 <= sl < o1]
            oos_res = run_backtest(h1.iloc[o0:o1], oos_sigs, costs)
            oos = oos_res.stats()
            wf_rows.append(
                {"train_n": s["n"], "train_exp": round(s["expectancy_r"], 4),
                 "train_t": round(s["t_stat"], 2),
                 "oos_n": oos["n"], "oos_exp": round(oos["expectancy_r"], 4)}
            )
        results[name] = {
            "signals": full.signal_count,
            "n": st["n"],
            "expectancy_r": round(st["expectancy_r"], 4),
            "t_stat": round(st["t_stat"], 2),
            "profit_factor": round(st["profit_factor"], 3),
            "win_rate": round(st["win_rate"], 3),
            "avg_win_r": round(st["avg_win_r"], 3),
            "avg_loss_r": round(st["avg_loss_r"], 3),
            "max_dd_r": round(st["max_dd_r"], 2),
            "walk_forward": wf_rows,
        }
        verdict = "PASS" if (st["t_stat"] > 2.0 and st["expectancy_r"] > 0) else "fail"
        print(f"\n[{name}] n={st['n']} exp={st['expectancy_r']:.3f}R "
              f"t={st['t_stat']:.2f} PF={st['profit_factor']:.2f} "
              f"win={st['win_rate']:.1%} maxDD={st['max_dd_r']:.1f}R -> {verdict}")
        for wf in wf_rows:
            print(f"    WF train n={wf['train_n']} exp={wf['train_exp']} "
                  f"t={wf['train_t']} | OOS n={wf['oos_n']} exp={wf['oos_exp']}")

    report = {
        "at": datetime.now(tz=UTC).isoformat(),
        "universe": "XAUUSD H1 via Vantage cache",
        "costs": {"spread_per_lot": costs.spread_per_lot,
                  "commission_per_lot": costs.commission_per_lot},
        "results": results,
    }
    out = str(REPORTS / "hunt1.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nreport -> {out}")


if __name__ == "__main__":
    main()