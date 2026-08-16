"""Portfolio study for hunt6 survivors: cross-sleeve daily-R correlation and
combined-book statistics (equal 0.02 lots per sleeve)."""

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

WINDOWS = {
    "asia": dict(range_start=7, wait_bars=12, rr=2.0, ttl_bars=12),
    "london_am": dict(range_start=10, range_end=13, signal_at=13, wait_bars=8, rr=2.0, ttl_bars=12),
    "ny_open": dict(range_start=13, range_end=14, signal_at=14, wait_bars=12, rr=2.0, ttl_bars=12),
    "afternoon": dict(range_start=14, range_end=17, signal_at=17, wait_bars=8, rr=2.0, ttl_bars=12),
}

SURVIVORS = [  # (sym, window) unique sleeves passing all gates
    ("XAUUSD", "asia"), ("XAUUSD", "london_am"), ("XAUUSD", "afternoon"),
    ("USDJPY", "asia"), ("USDJPY", "london_am"),
    ("CADJPY", "asia"),
    ("EURJPY", "asia"), ("EURJPY", "london_am"),
    ("GBPJPY", "asia"), ("GBPJPY", "london_am"),
]


def per_symbol_costs(meta: dict, sym: str) -> Costs:
    m = meta[sym]
    spread = 0.48 if sym == "XAUUSD" else (
        m["median_spread_pts"] * m["tick_size"] * m["contract_size"])
    return Costs(spread_per_lot=max(spread, 0.05),
                 commission_per_lot=3.50, contract_oz=m["contract_size"])


def main() -> None:
    meta = json.loads((UNI / "universe.json").read_text(encoding="utf-8"))
    daily = {}
    rows = []
    for sym, win in SURVIVORS:
        h1 = pd.read_parquet(UNI / f"{sym}_H1.parquet")
        h1 = families._h1(h1)
        sigs = families.family_session_range_breakout(h1, **WINDOWS[win])
        res = run_backtest(h1, sigs, per_symbol_costs(meta, sym))
        st = res.stats()
        trades = res.trades
        s = pd.Series(
            [t.r_multiple for t in trades],
            index=pd.DatetimeIndex([t.entry_time for t in trades]).tz_convert("UTC"),
            name=f"{sym}.{win}",
        )
        d = s.groupby(s.index.normalize()).sum()
        daily[f"{sym}.{win}"] = d
        rows.append((f"{sym}.{win}", st["n"], st["expectancy_r"], st["t_stat"],
                     st["profit_factor"], st["max_dd_r"],
                     len(trades) / max((s.index.max() - s.index.min()).days / 365.25, 1)))
        print(f"{sym:>7}.{win:<11} n={st['n']:5d} exp={st['expectancy_r']:+.3f}R "
              f"t={st['t_stat']:5.2f} PF={st['profit_factor']:.2f} maxDD={st['max_dd_r']:6.1f}R "
              f"trades/yr={len(trades) / max((s.index.max() - s.index.min()).days / 365.25, 1):6.1f}")
    yrs = {r[0]: r[6] for r in rows}

    df = pd.DataFrame(daily).fillna(0.0)
    corr = df.corr()
    print("\n=== cross-sleeve daily-R correlation ===")
    print(corr.round(2).to_string())

    comb = df.sum(axis=1)
    rs = comb.to_numpy()
    n = len(rs)
    mean = rs.mean()
    sd = rs.std(ddof=1)
    t_stat = mean / (sd / np.sqrt(n)) if sd > 0 else 0.0
    cum = np.cumsum(rs)
    peak = np.maximum.accumulate(cum)
    max_dd = float((cum - peak).min())
    wins = rs[rs > 0].sum()
    losses = abs(rs[rs < 0].sum())
    years = max((comb.index.max() - comb.index.min()).days / 365.25, 1)
    print("\n=== combined book (10 sleeves x 1 lot each) ===")
    print(f"days={n} years={years:.1f} mean_daily_R={mean:+.4f} daily_t={t_stat:.2f}")
    print(f"PF={wins / losses:.2f} maxDD={max_dd:.1f}R")
    print(f"annualized R (mean*{365.25:.0f}) = {mean * 365.25:.1f}R/yr per 1-lot sleeve set")
    print(f"avg per-trade exp (all sleeves) = {np.mean([r[2] for r in rows]):.3f}R")
    print(f"trades/yr total = {sum(r[6] for r in rows):.0f}")


if __name__ == "__main__":
    main()