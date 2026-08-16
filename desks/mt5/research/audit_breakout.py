"""Robustness audit for session_range_breakout: params x periods x timeframes."""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from mt5desk import families
from mt5desk.data import load_gold
from mt5desk.engine import Costs, run_backtest

costs = Costs(spread_per_lot=0.48, commission_per_lot=3.50, contract_oz=100.0)
gold = load_gold()


def stats(sigs, h1) -> dict:
    st = run_backtest(h1, sigs, costs).stats()
    return st


def fmt(name, st, combos, periods):
    print(f"== {name} ==")
    for combo, st2 in zip(combos, periods):
        print(f"  {combo}: n={st2['n']} exp={st2['expectancy_r']:.3f}R "
              f"t={st2['t_stat']:.2f} PF={st2['profit_factor']:.2f} "
              f"maxDD={st2['max_dd_r']:.1f}R")


def audit(tf, label):
    h1 = families._h1(tf)
    combos = list(
        itertools.product([6, 7, 8], [4, 8, 12], [1.5, 2.0, 2.5])
    )
    rows = []
    for rs, wb, rr in combos:
        sigs = families.family_session_range_breakout(
            h1, range_start=rs, wait_bars=wb, rr=rr
        )
        st = stats(sigs, h1)
        rows.append((f"rs={rs} wait={wb} rr={rr}", st))
        if (rs, wb, rr) == (7, 8, 2.0):
            base = st
    print(f"== {label}: base n={base['n']} exp={base['expectancy_r']:.3f} "
          f"t={base['t_stat']:.2f} PF={base['profit_factor']:.2f} "
          f"maxDD={base['max_dd_r']:.1f}R ==")
    print("  all 27 combos exp/t:")
    for name, st in rows:
        print(f"  {name}: n={st['n']} exp={st['expectancy_r']:.3f} t={st['t_stat']:.2f}")
    pos = sum(1 for _, st in rows if st["t_stat"] > 2 and st["expectancy_r"] > 0)
    print(f"  combos with t>2 AND exp>0: {pos}/27")
    edges = pd.Timestamp("2013-06-01", tz="UTC"), pd.Timestamp("2019-06-01", tz="UTC")
    cuts = [
        (h1.index[0], edges[0], "2007-06 -> 2013-05"),
        (edges[0], edges[1], "2013-06 -> 2019-05"),
        (edges[1], h1.index[-1], "2019-06 -> 2026-08"),
    ]
    for a, b, lab in cuts:
        sub = h1.loc[a:b]
        sigs = families.family_session_range_breakout(sub)
        st = stats(sigs, sub)
        print(f"  sub {lab}: n={st['n']} exp={st['expectancy_r']:.3f} "
              f"t={st['t_stat']:.2f} PF={st['profit_factor']:.2f}")


audit(gold.h1, "H1")
print()
audit(gold.h4, "H4")
print()
audit(gold.m15, "M15")