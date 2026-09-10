"""Post-entry Bayesian management study (H_TP1 family).

Tests exit-management variants on the armed gold windows + AUDCAD asia
TREND_DAY: TTL-only (baseline), breakeven trail after +1R, trail after +0.5R,
and TP2 (partial close at +1R, rest to target/TTL). Trade-path evidence showed
16% of losers had +1R available -> the breakeven trail hypothesis.

Variant implemented by post-processing the baseline backtest trades: entry,
stop and target are identical; only the exit rule changes. A trailing stop
raises the stop to entry after price reached entry + k*R (checked against
intrabar high/low).
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
from research.run_hunt12 import day_states  # noqa: E402

#: Fusion Zero's published contract, USD per lot PER SIDE ($4.50 round turn). Mirrors
#: `libs.portfolio.fusion_cost.COMMISSION_PER_LOT_PER_SIDE`; the 3.50 this replaced was a
#: round-turn figure sitting in a per-side field, billing $7.00 a round trip against $4.50.
FUSION_COMMISSION_PER_SIDE = 2.25

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"
WINDOWS = {
    "asia": dict(range_start=7, wait_bars=12, rr=2.0, ttl_bars=12),
    "london_am": dict(range_start=10, range_end=13, signal_at=13, wait_bars=8, rr=2.0, ttl_bars=12),
    "afternoon": dict(range_start=14, range_end=17, signal_at=17, wait_bars=8, rr=2.0, ttl_bars=12),
}
CELLS = [("XAUUSD", w, None) for w in WINDOWS] + [("AUDCAD", "asia", "TREND_DAY")]


def apply_trail(h1: pd.DataFrame, trades: list, k: float | None) -> list[float]:
    """Breakeven-trail approximation over real backtest trades: if price
    touched entry + k*R (side-signed) before the trade exited, and later
    retraced through entry before exit, the outcome is marked 0R (trail stop
    filled at entry). k=None = baseline (no trail)."""
    out = []
    for t in trades:
        if k is None:
            out.append(t.r_multiple)
            continue
        risk = abs(t.entry - t.stop)
        if risk <= 0:
            out.append(t.r_multiple)
            continue
        trail = t.entry + k * risk * t.side
        window = h1.loc[t.entry_time:t.exit_time]
        if t.side > 0:
            trig = window[window["high"] >= trail]
            if len(trig):
                after = window.loc[trig.index[0]:]
                if (after["low"] <= t.entry).any():
                    out.append(0.0)
                    continue
        else:
            trig = window[window["low"] <= trail]
            if len(trig):
                after = window.loc[trig.index[0]:]
                if (after["high"] >= t.entry).any():
                    out.append(0.0)
                    continue
        out.append(t.r_multiple)
    return out


def main() -> None:
    meta = json.loads((UNI / "universe.json").read_text(encoding="utf-8"))
    variants = {"ttl": None, "trail+1R": 1.0, "trail+0.5R": 0.5}
    out = {"cells": {}}
    print(f"{'cell':<28} {'variant':<10} {'n':>5} {'exp':>7} {'PF':>5} {'maxDD':>7}")
    for sym, win, state in CELLS:
        h1 = families._h1(pd.read_parquet(UNI / f"{sym}_H1.parquet"))
        m = meta[sym]
        # COST THROUGH THE ONLY CORRECT CONSTRUCTOR. This site hand-rolled `Costs(...)` and
        # carried both traps `engine.Costs.from_symbol` exists to close:
        #
        #   * no `quote_per_account`, so commission stayed in ACCOUNT CURRENCY and was divided by
        #     contract_size as if it were PRICE -- "184x too little, on the JPY crosses where this
        #     desk's surviving edges actually live, in the direction that manufactures survivors"
        #   * `commission_per_lot=3.50`, a ROUND-TURN figure in a PER-SIDE field, billing $7.00 a
        #     round trip against Fusion Zero's contractual $4.50
        #   * and the gold override `spread_per_lot=0.48`, which the engine's own docstring
        #     records as "0.16/oz median written as dollars PER OUNCE into a field that wants
        #     dollars per lot ... every gold backtest on this desk has run very nearly spread-free"
        #
        # `from_symbol` closes all three, and the net direction is MORE expensive, which is the
        # safe one: it can only remove survivors that were passing on an undercharge.
        costs = Costs.from_symbol(m, commission_per_lot=FUSION_COMMISSION_PER_SIDE)
        sigs = families.family_session_range_breakout(h1, **WINDOWS[win])
        if state:
            st = day_states(h1)
            sdays = [pd.Timestamp(s.time).date() for s in sigs]
            sigs = [s for s, d in zip(sigs, sdays) if st.get(d) == state]
        base = run_backtest(h1, sigs, costs)
        rows = []
        for vname, v in variants.items():
            rs = np.array(apply_trail(h1, base.trades, v))
            n = len(rs)
            if n == 0:
                continue
            exp = float(rs.mean())
            pf = float(rs[rs > 0].sum() / abs(rs[rs < 0].sum())) if (rs < 0).any() else np.inf
            cum = np.cumsum(rs)
            maxdd = float(min(cum[i] - cum[:i + 1].max() for i in range(n)))
            rows.append(dict(variant=vname, n=n, exp=round(exp, 4),
                             pf=round(pf, 3), maxdd=round(maxdd, 1)))
            print(f"{sym+'_'+win+('_'+state if state else ''):<28} {vname:<10} "
                  f"{n:5d} {exp:+7.3f} {pf:5.2f} {maxdd:7.1f}")
        out["cells"][f"{sym}.{win}.{state or 'base'}"] = rows
    (BASE / "reports" / "exit_study.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")
    print("\n-> reports/exit_study.json")


if __name__ == "__main__":
    main()