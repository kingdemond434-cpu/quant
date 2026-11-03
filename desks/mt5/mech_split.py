"""Mechanism decomposition v1: what makes the Asia gold window work?

Decomposes the Asia session label into prior-NY causal states (Mechanism
Desk flagship). Prior NY = 13:00-22:00 UTC of the previous day, classified
on closed data at 22:00:
  - TREND_DAY:     prior-NY range > 1.5x its 20-day median range
  - RANGE_DAY:     prior-NY range < 0.75x its 20-day median range
  - NORMAL_DAY:    otherwise
  - FAILED_BREAK:  prior-NY traded beyond the day-before's high/low but
                   closed back inside (displacement failure)
Then the Asia gold window (07:00 bracket) is evaluated conditioned on each
state. If one state carries most of the edge, "Asia works" is really
"Asia-after-X works" - and X becomes a state to hunt across the universe.
"""

import json
import sys
from datetime import UTC, datetime
from datetime import date as Date
from pathlib import Path

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parent
ROOT = DESK.parent.parent
for _path in (ROOT, DESK):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from mt5desk import families  # noqa: E402
from mt5desk.engine import run_backtest  # noqa: E402

from libs.portfolio.fusion_cost import costs_for_symbol  # noqa: E402

DATA = DESK / "data" / "universe"

ASIA = {"range_start": 7, "wait_bars": 12, "rr": 2.0, "ttl_bars": 12}


def carry_to_next_trading_day(
    raw_states: dict[Date, str], bar_dates: list[Date],
) -> dict[Date, str]:
    """Make a completed session state usable only on the next date with broker bars."""
    trading_dates = sorted(set(bar_dates))
    return {trading_dates[i + 1]: raw_states[d]
            for i, d in enumerate(trading_dates[:-1]) if d in raw_states}


def main() -> None:
    meta = json.loads((DATA / "universe.json").read_text("utf-8"))["XAUUSD"]
    costs = costs_for_symbol(meta)
    h1 = pd.read_parquet(DATA / "XAUUSD_H1.parquet")
    h1 = families._h1(h1)
    ny = h1.between_time("13:00", "22:00")
    day = h1.assign(date=h1.index.date)
    ny_by_day = ny.assign(date=ny.index.date).groupby("date").agg(
        hi=("high", "max"), lo=("low", "min"), rng=("high", "sum"))
    ny_by_day["rng"] = ny_by_day["hi"] - ny_by_day["lo"]
    ny_by_day["rng_med"] = ny_by_day["rng"].shift(1).rolling(20, min_periods=10).median()
    day_hi = day.groupby("date").agg(hi=("high", "max"), lo=("low", "min"))
    day_hi["dhi"] = day_hi["hi"].shift(1)
    day_hi["dlo"] = day_hi["lo"].shift(1)
    ny_by_day = ny_by_day.join(day_hi[["dhi", "dlo"]])

    raw_states = {}
    for d in ny_by_day.index:
        r = ny_by_day.loc[d]
        rng, med = r["rng"], r["rng_med"]
        if not med or np.isnan(med):
            raw_states[d] = "NONE"
            continue
        if rng > 1.5 * med:
            raw_states[d] = "TREND_DAY"
        elif rng < 0.75 * med:
            raw_states[d] = "RANGE_DAY"
        else:
            raw_states[d] = "NORMAL_DAY"
        hi, lo = r["hi"], r["lo"]
        dhi, dlo = r["dhi"], r["dlo"]
        if dhi and dlo and (hi > dhi or lo < dlo):
            nyc = ny[ny.index.date == d]
            if len(nyc) and ((nyc["close"].iloc[-1] < dhi and hi > dhi)
                             or (nyc["close"].iloc[-1] > dlo and lo < dlo)):
                raw_states[d] = "FAILED_BREAK"

    # A signal at 07:00 cannot use the 13:00-22:00 state from that same date.  Carry each New
    # York classification to the NEXT date that actually has broker bars; this also maps Friday
    # to Monday rather than inventing empty weekend sessions.
    states = carry_to_next_trading_day(raw_states, list(h1.index.date))

    sigs = families.family_session_range_breakout(h1, **ASIA)
    sig_days = [pd.Timestamp(s.time).date() for s in sigs]
    out = {}
    print(f"{'state':<12} {'n':>5} {'exp_R':>7} {'t':>5} {'PF':>5} {'maxDD_R':>7}")
    for name in ["ALL", "TREND_DAY", "RANGE_DAY", "NORMAL_DAY", "FAILED_BREAK"]:
        if name == "ALL":
            sub = sigs
        else:
            sub = [s for s, d in zip(sigs, sig_days, strict=True) if states.get(d) == name]
        r = run_backtest(h1, sub, costs).stats()
        out[name] = {"n": r["n"], "exp": r["expectancy_r"], "t": r["t_stat"],
                     "pf": r["profit_factor"], "maxdd": r["max_dd_r"]}
        print(f"{name:<12} {r['n']:5d} {r['expectancy_r']:+7.3f} "
              f"{r['t_stat']:5.2f} {r['profit_factor']:5.2f} {r['max_dd_r']:7.1f}")

    counts = {k: sum(1 for d in sig_days if states.get(d) == k)
              for k in ["TREND_DAY", "RANGE_DAY", "NORMAL_DAY", "FAILED_BREAK"]}
    out["signal_counts_by_state"] = counts
    (DESK / "reports" / "mech_split.json").write_text(
        json.dumps({"swept_at": datetime.now(UTC).isoformat(),
                    **out}, indent=2, default=str), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
