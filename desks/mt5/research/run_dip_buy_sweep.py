"""Test three DIFFERENT definitions of "buy the dip" on the desk's two
Fusion-executable crypto CFDs, at the honest bar.

    python research/run_dip_buy_sweep.py

WHY THREE MECHANISMS, NOT ONE "dip" FAMILY WITH KNOBS

"Buy the dip" is a label, not a mechanism. `family_dip_pullback_pct` (a
graded retracement that has to stall before entry), `family_dip_rsi_reclaim`
(a momentum oversold-then-turn), and `family_dip_atr_shock` (a single-bar
volatility flush, entered with no confirmation) are three separate claims
about what makes a decline buyable. Folding them into one family with a
"dip_type" parameter would hide exactly the finding that matters most here:
if one survives and the other two don't, that is real information about
which mechanism (if any) has anything to it. A blended family cannot produce
that answer even in principle.

SCOPE, PER THE STANDING MANDATE

BTCUSD and ETHUSD only -- the two Fusion-executable crypto CFDs already in
this desk's MT5 universe (data/universe/universe.json). This is NOT a
crypto-exchange hunt: no Binance/Bybit/OKX data, no crypto-native venue, both
symbols are instruments this desk can already route an order to. That is the
standing mandate's exact carve-out, not an exception to it.

ALL SIGNALS ARE LONG-ONLY, ON PURPOSE

Every cell in this sweep bets on mean-reversion-within-an-uptrend. That
directional bias IS the hypothesis under test, not a design flaw balanced by
adding shorts -- a dip-buy family that also sold rallies would be testing a
different, unrelated claim.

THE BAR

3 mechanisms x parameter grid x 2 symbols. `multiplicity.deflation(trials)`
is computed from THIS sweep's own cell count, same discipline as
run_cot_macro_sweep.py -- never borrowed from a larger or smaller hunt.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore", category=UserWarning)

import json  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from mt5desk import families  # noqa: E402
from mt5desk.engine import Costs, run_backtest  # noqa: E402
from mt5desk.multiplicity import deflation  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"

SYMBOLS = ["BTCUSD", "ETHUSD"]

#: mechanism name -> (family fn, list of parameter dicts to sweep).
#: 3 pullback thresholds + 3 RSI thresholds + 3 ATR-shock multiples = 9
#: cells per symbol -> 18 trials total. Small and deliberate: this is a
#: first honest look, not a fishing expedition.
CELLS = {
    "dip_pullback": (families.family_dip_pullback_pct, [
        {"pullback_pct": 0.03}, {"pullback_pct": 0.05}, {"pullback_pct": 0.08},
    ]),
    "dip_rsi_reclaim": (families.family_dip_rsi_reclaim, [
        {"oversold": 25.0}, {"oversold": 30.0}, {"oversold": 35.0},
    ]),
    "dip_atr_shock": (families.family_dip_atr_shock, [
        {"atr_k": 1.5}, {"atr_k": 2.0}, {"atr_k": 2.5},
    ]),
}


def main() -> int:
    meta = json.loads((UNI / "universe.json").read_text(encoding="utf-8"))
    trials = sum(len(cells) for _, cells in CELLS.values()) * len(SYMBOLS)
    bar = 1.96 + deflation(trials)
    print(f"Dip-buy sweep: {trials} cells "
          f"({sum(len(c) for _, c in CELLS.values())} params x {len(SYMBOLS)} symbols)")
    print(f"required t >= {bar:.2f} (deflated for {trials} trials -- this sweep's own count)\n")

    rows = []
    for sym in SYMBOLS:
        p = UNI / f"{sym}_H1.parquet"
        if not p.exists() or sym not in meta:
            print(f"SKIP {sym}: no H1 parquet or not in universe.json")
            continue
        h1 = pd.read_parquet(p)
        costs = Costs.from_symbol(meta[sym], mult=2.0)

        for mech_name, (fn, param_list) in CELLS.items():
            for params in param_list:
                label = ",".join(f"{k}={v}" for k, v in params.items())
                sigs = fn(h1, **params)
                trades = run_backtest(h1, sigs, costs).trades
                n = len(trades)
                if n < 20:
                    rows.append({"symbol": sym, "mechanism": mech_name, "params": label,
                                "n": n, "t": float("nan"), "exp": float("nan"),
                                "verdict": "TOO FEW TRADES"})
                    continue
                r = np.array([t.r_multiple for t in trades])
                t_stat = float(r.mean() / (r.std(ddof=1) / np.sqrt(n)))
                verdict = "SURVIVOR" if t_stat >= bar else "kill"
                rows.append({"symbol": sym, "mechanism": mech_name, "params": label,
                            "n": n, "t": t_stat, "exp": float(r.mean()), "verdict": verdict})

    print(f"{'symbol':<8} {'mechanism':<16} {'params':<16} {'n':>5} {'exp R':>8} {'t':>7}  verdict")
    for row in sorted(rows, key=lambda r: (-r["t"] if r["t"] == r["t"] else 999)):
        t_disp = f"{row['t']:7.2f}" if row["t"] == row["t"] else "    n/a"
        print(f"{row['symbol']:<8} {row['mechanism']:<16} {row['params']:<16} {row['n']:5d} "
              f"{row['exp']:+8.4f} {t_disp}  {row['verdict']}")

    survivors = [r for r in rows if r["verdict"] == "SURVIVOR"]
    print(f"\n{len(survivors)} of {len(rows)} cells clear t >= {bar:.2f}.")
    if not survivors:
        print("HONEST RESULT: none of these three dip-buy mechanisms survive the desk's own "
              "multiplicity-corrected bar on this data. That is a real answer, not a failure "
              "of the sweep -- reporting a kill is what the bar is for.")
    out = BASE / "reports" / "dip_buy_sweep.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"trials": trials, "required_t": bar, "rows": rows}, indent=2),
                   encoding="utf-8")
    print(f"\n-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
