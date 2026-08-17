"""hunt15: drawdown-alpha factory (v1).

Scores every hunt12 cell + gold windows + hunt10 gate combos by the
Drawdown Complementarity Score: mean R on the CURRENT portfolio's worst-decile
days (portfolio = today's survivor book). A candidate that earns during the
book's worst days is worth more than its overall expectancy suggests.

Admission: n>=60, exp_worst > 0.05, and NOT already in the book.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mt5desk import families  # noqa: E402
from mt5desk.engine import Costs, run_backtest  # noqa: E402
from portfolio_projection import (GOLD_WINDOWS, build_daily, build_sleeves,  # noqa: E402
                                  cell_trades)

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"
MIN_N = 60
MIN_EXP_WORST = 0.05


def main() -> None:
    meta = json.loads((UNI / "universe.json").read_text(encoding="utf-8"))
    book = build_sleeves()
    book_daily = build_daily(book)
    port = book_daily.sum(axis=1)
    worst = port <= np.quantile(port, 0.10)
    worst_days = set(port.index[worst])
    print(f"portfolio worst-decile: {len(worst_days)} days")

    from research.run_hunt12 import day_states  # noqa: PLC0415
    from research.run_hunt12 import WINDOWS as H12_WINDOWS  # noqa: PLC0415

    cells = []
    partial = BASE / "reports" / "hunt12_partial.json"
    if partial.exists():
        saved = json.loads(partial.read_text(encoding="utf-8"))
        for c in saved.get("all", []):
            cells.append((c["sym"], c["win"], c["state"]))

    results = []
    seen = {s["name"] for s in book}
    for sym, win, state in cells:
        name = f"{sym}_{win}_{state}"
        if name in seen or sym not in meta:
            continue
        print(f"  cell {name}...", flush=True)
        try:
            h1 = families._h1(pd.read_parquet(UNI / f"{sym}_H1.parquet"))
            m = meta[sym]
            costs = Costs(spread_per_lot=0.48 if sym == "XAUUSD" else max(
                m["median_spread_pts"] * m["tick_size"] * m["contract_size"], 0.05),
                commission_per_lot=3.50, contract_oz=m["contract_size"])
            st = day_states(h1)
            tr = cell_trades(sym, win, state, h1, costs, st)
            if len(tr) < MIN_N:
                continue
            rs = pd.Series([t.r_multiple for t in tr],
                       index=pd.Index([t.entry_time.date() for t in tr]))
            daily = rs.groupby(level=0).sum()
            wd = daily.index[daily.index.isin(worst_days)]
            exp_worst = float(daily.loc[wd].mean()) if wd.size else float("nan")
            exp_all = float(daily.mean())
            cum = np.cumsum(rs.to_numpy())
            maxdd = float(min(cum[i] - cum[:i + 1].max() for i in range(len(cum))))
            results.append(dict(name=name, sym=sym, win=win, state=state,
                                n=len(tr), exp=round(exp_all, 4),
                                exp_worst=round(exp_worst, 4),
                                maxdd=round(maxdd, 1)))
        except Exception:
            import traceback
            traceback.print_exc()
            continue

    results.sort(key=lambda r: -(r["exp_worst"] if r["exp_worst"] == r["exp_worst"] else -9))
    print(f"{'name':<28} {'n':>5} {'exp':>7} {'expWorst':>9} {'maxDD':>7}")
    for r in results:
        ew = r["exp_worst"]
        flag = "DDA!" if (r["n"] >= MIN_N and ew == ew and ew > MIN_EXP_WORST
                          and r["exp"] > 0) else ""
        print(f"{r['name']:<28} {r['n']:5d} {r['exp']:+7.3f} "
              f"{ew:+9.3f} {r['maxdd']:7.1f}  {flag}")

    dda = [r for r in results if r["n"] >= MIN_N and r["exp_worst"] == r["exp_worst"]
           and r["exp_worst"] > MIN_EXP_WORST and r["exp"] > 0]
    out = dict(swept_at=datetime.now(timezone.utc).isoformat(),
               drawdown_alpha_candidates=dda, all=results)
    (BASE / "reports" / "hunt15.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"\n{len(dda)} drawdown-alpha candidates -> reports/hunt15.json")


if __name__ == "__main__":
    main()