"""Portfolio projection for all current survivors (gold book + hunt12 cells).

Recomputes per-trade cost-adjusted R for every survivor cell, builds aligned
daily-R series, then reports:
  - per-sleeve stats + rank
  - cross-sleeve correlation / effective independent count
  - portfolio net Sharpe (daily R, annualized) and 8y CAGR at two risk
    budgets (q_total = 5.5% and 5.5%*sqrt(N_eff), per-day R units)

All R figures are net of the validation cost model (spread+commission).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mt5desk import families  # noqa: E402
from mt5desk.engine import Costs, run_backtest  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"

GOLD_WINDOWS = {
    "asia": dict(range_start=7, wait_bars=12, rr=2.0, ttl_bars=12),
    "london_am": dict(range_start=10, range_end=13, signal_at=13, wait_bars=8, rr=2.0, ttl_bars=12),
    "ny_open": dict(range_start=13, range_end=14, signal_at=14, wait_bars=12, rr=2.0, ttl_bars=12),
    "afternoon": dict(range_start=14, range_end=17, signal_at=17, wait_bars=8, rr=2.0, ttl_bars=12),
}
H12_WINDOWS = GOLD_WINDOWS  # identical structure in run_hunt12


def cell_trades(sym: str, win: str, state: str | None, h1: pd.DataFrame,
                costs: Costs, states: dict | None) -> list:
    sigs = families.family_session_range_breakout(h1, **H12_WINDOWS[win])
    if states is not None:
        sdays = [pd.Timestamp(s.time).date() for s in sigs]
        sigs = [s for s, d in zip(sigs, sdays) if states.get(d) == state]
    r = run_backtest(h1, sigs, costs)
    return r.trades


def load_h12_survivors() -> list[dict]:
    p = BASE / "reports" / "hunt12_partial.json"
    if not p.exists():
        return []
    saved = json.loads(p.read_text(encoding="utf-8"))
    return [c for c in saved.get("all", []) if c.get("gate")]


def main() -> None:
    meta = json.loads((UNI / "universe.json").read_text(encoding="utf-8"))

    sleeves = []  # dicts: name, sym, win, state, trades(list of r_multiple), dates

    h1g = families._h1(pd.read_parquet(UNI / "XAUUSD_H1.parquet"))
    gold_costs = Costs(spread_per_lot=0.48, commission_per_lot=3.50, contract_oz=100)
    for wname, wp in GOLD_WINDOWS.items():
        tr = cell_trades("XAUUSD", wname, None, h1g, gold_costs, None)
        sleeves.append(dict(name=f"gold_{wname}", sym="XAUUSD", win=wname,
                            state="base",
                            r=[t.r_multiple for t in tr],
                            dates=[t.entry_time.date() for t in tr]))

    from research.run_hunt12 import day_states  # noqa: PLC0415

    for cell in load_h12_survivors():
        sym, win, state = cell["sym"], cell["win"], cell["state"]
        h1 = families._h1(pd.read_parquet(UNI / f"{sym}_H1.parquet"))
        m = meta[sym]
        costs = Costs(spread_per_lot=0.48 if sym == "XAUUSD" else max(
            m["median_spread_pts"] * m["tick_size"] * m["contract_size"], 0.05),
            commission_per_lot=3.50, contract_oz=m["contract_size"])
        states = day_states(h1)
        tr = cell_trades(sym, win, state, h1, costs, states)
        sleeves.append(dict(name=f"{sym}_{win}_{state}", sym=sym, win=win,
                            state=state,
                            r=[t.r_multiple for t in tr],
                            dates=[t.entry_time.date() for t in tr]))

    print(f"{'rank':>4} {'sleeve':<26} {'n':>5} {'exp':>7} {'PF':>5} "
          f"{'maxDD':>7} {'S/trade':>7} {'annSharpe':>9}")
    rows = []
    for s in sleeves:
        rs = np.array(s["r"])
        n = len(rs)
        exp = float(rs.mean())
        std = float(rs.std(ddof=1)) if n > 1 else 0.0
        pf = float(rs[rs > 0].sum() / abs(rs[rs < 0].sum())) if (rs < 0).any() else np.inf
        cum = np.cumsum(rs)
        maxdd = float(min(cum[i] - cum[:i + 1].max() for i in range(len(cum))))
        st = exp / std if std > 0 else 0.0
        days = len(set(s["dates"]))
        ann = st * np.sqrt(252 * days / max(n, 1))
        s.update(n=n, exp=exp, pf=pf, maxdd=maxdd, st=st, ann=ann)
        rows.append(s)

    rows.sort(key=lambda s: -s["ann"])
    for i, s in enumerate(rows, 1):
        print(f"{i:4d} {s['name']:<26} {s['n']:5d} {s['exp']:+7.3f} {s['pf']:5.2f} "
              f"{s['maxdd']:7.1f} {s['st']:7.3f} {s['ann']:9.2f}")

    # aligned daily R per sleeve
    alldays = sorted({d for s in sleeves for d in s["dates"]})
    daily = pd.DataFrame(index=alldays,
                         columns=[s["name"] for s in rows],
                         dtype=float)
    for s in rows:
        d = pd.Series(s["r"], index=pd.Index(s["dates"]))
        daily[s["name"]] = d.groupby(level=0).sum().reindex(alldays).fillna(0.0)

    corr = daily.corr()
    vals = corr.values
    off = vals[~np.eye(len(vals), dtype=bool)]
    mean_corr = float(off.mean()) if len(off) else 0.0
    n_eff = len(rows) / (1 + (len(rows) - 1) * mean_corr)

    port = daily.sum(axis=1)
    m, s = port.mean(), port.std(ddof=1)
    sharpe = m / s * np.sqrt(252) if s > 0 else 0.0
    print(f"\nmean cross-sleeve corr = {mean_corr:.3f} | effective N = {n_eff:.1f} "
          f"of {len(rows)} sleeves")

    for q in (0.055, 0.055 * np.sqrt(n_eff)):
        w = (1.0 + q * port).prod()
        years = (max(alldays) - min(alldays)).days / 365.25
        cagr = w ** (1 / years) - 1
        worst = float((1.0 + q * port).cumprod().min())
        print(f"q_total={q:.3f}/day-R: net Sharpe {sharpe:.2f}, 8y CAGR {cagr*100:.1f}%, "
              f"min wealth {worst:.3f}")

    out = dict(rows=[{k: s[k] for k in ("name", "sym", "win", "state", "n",
                                        "exp", "pf", "maxdd", "st", "ann")}
                     for s in rows],
               mean_corr=mean_corr, n_eff=n_eff, port_sharpe=sharpe,
               port_daily_mean=m, port_daily_std=s)
    (BASE / "reports" / "portfolio_projection.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")
    print("\n-> reports/portfolio_projection.json")


if __name__ == "__main__":
    main()