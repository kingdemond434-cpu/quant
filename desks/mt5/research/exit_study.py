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

#: MEASURED, not published: 2.00 in ACCOUNT CURRENCY per lot per side, over all 433
#: deals the live Fusion account has ever done (reports/COST_TRUTH.json, 2026-09-23, p10=p50=p90).
#: Mirrors `libs.portfolio.fusion_cost.COMMISSION_PER_LOT_PER_SIDE`. The 2.25 this
#: replaced was the brochure's USD figure fed to a field `Costs.from_symbol` converts as
#: ACCOUNT currency -- a 1.125x overcharge on the term that is ~98% of this book's cost.
FUSION_COMMISSION_PER_SIDE = 2.00

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"
WINDOWS = {
    "asia": dict(range_start=7, wait_bars=12, rr=2.0, ttl_bars=12),
    "london_am": dict(range_start=10, range_end=13, signal_at=13, wait_bars=8, rr=2.0, ttl_bars=12),
    "afternoon": dict(range_start=14, range_end=17, signal_at=17, wait_bars=8, rr=2.0, ttl_bars=12),
}
CELLS = [("XAUUSD", w, None) for w in WINDOWS] + [("AUDCAD", "asia", "TREND_DAY")]

# Small, preregistered structural grid. These are not arbitrary P&L stops: a candidate fires
# only after a completed M5 bar has reclaimed the breakout level, adverse excursion has become
# material, and favourable follow-through has remained weak. Every arm is reported as a trial.
FAST_FAIL_VARIANTS = {
    "ff2_bal": dict(max_bars=2, min_mae_r=0.15, max_mfe_r=0.10, reclaim_closes=1),
    "ff4_bal": dict(max_bars=4, min_mae_r=0.20, max_mfe_r=0.20, reclaim_closes=1),
    "ff4_confirm": dict(max_bars=4, min_mae_r=0.15, max_mfe_r=0.20, reclaim_closes=2),
    "ff6_slow": dict(max_bars=6, min_mae_r=0.25, max_mfe_r=0.25, reclaim_closes=2),
}


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


def apply_fast_fail(m5: pd.DataFrame, trades: list, **rule: float | int) -> dict:
    """Replay a structural failed-breakout exit on completed M5 bars without lookahead.

    The first M5 bar that crosses the exact baseline entry locates the fill. Decisions begin on
    the following completed bar and exit at the *next* M5 open. A hard stop/target touched first
    keeps the baseline outcome because intrabar ordering is unknowable. Trades without adequate
    M5 coverage are excluded rather than silently assigned the baseline result.
    """
    base_r: list[float] = []
    test_r: list[float] = []
    triggered = 0
    for trade in trades:
        risk = abs(float(trade.entry) - float(trade.stop))
        if not risk > 0:
            continue
        start = pd.Timestamp(trade.entry_time)
        finish = pd.Timestamp(trade.exit_time)
        hour = m5[(m5.index >= start) & (m5.index < start + pd.Timedelta(hours=1))]
        crossed = (hour["high"] >= trade.entry) if trade.side > 0 else (hour["low"] <= trade.entry)
        if not bool(crossed.any()):
            continue
        fill_at = crossed[crossed].index[0]
        # Strictly before the baseline exit bar: observing that bar and then choosing a better
        # exit would use information the baseline trade had already exited on.
        path = m5[(m5.index > fill_at) & (m5.index < finish)]
        need = int(rule["max_bars"]) + 1       # the +1 bar supplies an executable next open
        if len(path) < 2:
            continue
        window = path.iloc[:need]
        gross_base = ((float(trade.exit) - float(trade.entry)) * int(trade.side) / risk)
        cost_r = gross_base - float(trade.r_multiple)
        candidate = float(trade.r_multiple)
        mfe_r = 0.0
        mae_r = 0.0
        adverse_closes = 0
        bars_seen = 0
        for j in range(min(int(rule["max_bars"]), len(window) - 1)):
            bar = window.iloc[j]
            # Preserve pessimism when the certified hard exit and a fast-fail condition are
            # both possible in one bar: the hard exit owns the ambiguous ordering.
            if trade.side > 0:
                if float(bar["low"]) <= trade.stop or float(bar["high"]) >= trade.target:
                    break
                mfe_r = max(mfe_r, (float(bar["high"]) - trade.entry) / risk)
                mae_r = max(mae_r, (trade.entry - float(bar["low"])) / risk)
                reclaimed = float(bar["close"]) < trade.entry
            else:
                if float(bar["high"]) >= trade.stop or float(bar["low"]) <= trade.target:
                    break
                mfe_r = max(mfe_r, (trade.entry - float(bar["low"])) / risk)
                mae_r = max(mae_r, (float(bar["high"]) - trade.entry) / risk)
                reclaimed = float(bar["close"]) > trade.entry
            adverse_closes = adverse_closes + 1 if reclaimed else 0
            bars_seen += 1
            if (mae_r >= float(rule["min_mae_r"])
                    and mfe_r <= float(rule["max_mfe_r"])
                    and adverse_closes >= int(rule["reclaim_closes"])):
                exit_price = float(window.iloc[j + 1]["open"])
                candidate = ((exit_price - trade.entry) * trade.side / risk) - cost_r
                triggered += 1
                break
        base_r.append(float(trade.r_multiple))
        test_r.append(float(candidate))
    return {"baseline": base_r, "variant": test_r, "triggered": triggered,
            "eligible": len(base_r), "bars_rule": int(rule["max_bars"])}


def _stats(rs: list[float]) -> dict:
    arr = np.asarray(rs, dtype=float)
    if not len(arr):
        return {"n": 0, "exp": None, "pf": None, "maxdd": None}
    losses = arr[arr < 0]
    pf = float(arr[arr > 0].sum() / abs(losses.sum())) if len(losses) else float("inf")
    cum = np.cumsum(arr)
    maxdd = float(min(cum[i] - cum[:i + 1].max() for i in range(len(arr))))
    return {"n": len(arr), "exp": round(float(arr.mean()), 4),
            "pf": round(pf, 3), "maxdd": round(maxdd, 1)}


def main() -> None:
    meta = json.loads((UNI / "universe.json").read_text(encoding="utf-8"))
    variants = {"ttl": None, "trail+1R": 1.0, "trail+0.5R": 0.5}
    out = {"cells": {}, "fast_fail": {"trial_count_per_cell": len(FAST_FAIL_VARIANTS),
                                         "cells": {}}}
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
        if sym == "XAUUSD" and (UNI / f"{sym}_M5.parquet").exists():
            m5 = pd.read_parquet(UNI / f"{sym}_M5.parquet").sort_index()
            ff_rows = []
            for name, rule in FAST_FAIL_VARIANTS.items():
                result = apply_fast_fail(m5, base.trades, **rule)
                before, after = _stats(result["baseline"]), _stats(result["variant"])
                delta = (None if before["exp"] is None or after["exp"] is None
                         else round(float(after["exp"]) - float(before["exp"]), 4))
                ff_rows.append({"variant": name, "rule": rule, "eligible": result["eligible"],
                                "triggered": result["triggered"], "baseline": before,
                                "result": after, "delta_expectancy_r": delta,
                                "status": "SCREEN_ONLY_NOT_PROMOTED"})
            out["fast_fail"]["cells"][f"{sym}.{win}.{state or 'base'}"] = ff_rows
    (BASE / "reports" / "exit_study.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")
    print("\n-> reports/exit_study.json")


if __name__ == "__main__":
    main()
