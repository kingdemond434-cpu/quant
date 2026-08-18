"""Realistic CAGRs for all three books, as each backtest convenience is removed.

The year-by-year table says the five-sleeve book returns a 112% median with NINE
POSITIVE YEARS OUT OF NINE. Books that good do not exist, so that number is
measuring something other than the edge, and the job is to find out how much of
it each convenience is worth -- for every book, not just the one that won.

FOUR CONVENIENCES, REMOVED CUMULATIVELY

    COSTS. The engine charges a median spread and a commission. It does not
    charge slippage, and these are STOP-ENTRY breakouts, which slip in one
    direction by construction: the order fills when price is already moving
    through it. 2x and 3x cost multiples stand in for that.

    THE REGIME. 2022 and 2025 pay 353% and 429% against a 40-125% median
    elsewhere. Those are the BoJ policy-divergence year and the gold melt-up. A
    session-range breakout is a volatility harvester, so its best years are the
    high-volatility years -- and an eight-year sample contains two of them.
    Dropping both asks what the book earns in an ordinary regime.

    SELECTION. Every figure is half-edge: half the mean daily P&L subtracted
    before compounding. A location shift, not a rescale, because halving every R
    would halve the losses too and that is a lower-volatility book rather than a
    worse one.

    LOT GRANULARITY. Reported separately at the end. The compounding assumes
    risk can be set to 1.00% exactly; the venue sells gold in EUR29.80 units.

EVERY BOOK IS RUN AT THE SAME TOTAL HEAT

5% across the book, whether that is five legs at 1.00% or twelve at 0.42%.
Comparing at equal q PER LEG would hand the twelve-sleeve book 2.4x the total
risk and then report that it earned more, which answers nothing. See
book_sizing.py for the matched-risk argument in full.

THE ASYMMETRY IS THE FINDING

Down the ladder the CAGR falls roughly 6x while the drawdown gets WORSE. Costs
eat the wins and leave the losses intact, so the pessimistic case is not a
smaller version of the optimistic one -- it is a much worse Sharpe at the same
pain.
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "research"))

warnings.filterwarnings("ignore")

from mt5desk import families                                    # noqa: E402
from mt5desk.engine import Costs, run_backtest                  # noqa: E402
from run_hunt11 import WINDOWS                                  # noqa: E402
from book_sizing import EIGHT, FIVE, SYMBOLS, WINS, compound    # noqa: E402

REALITY_VERSION = "bookreality-2026-08-18-b"

#: Total heat every book is run at. The middle of the three settings in
#: book_years.py, and roughly where the desk's own rule lands the five book.
TOTAL_HEAT = 0.05

#: The two years that carry the sample. Named rather than detected, so the
#: choice is arguable instead of fitted.
CARRY_YEARS = (2022, 2025)

META = json.loads((BASE / "data" / "universe" / "universe.json").read_text("utf-8"))
_h1: dict = {}
_ser: dict = {}


def h1(sym: str) -> pd.DataFrame:
    if sym not in _h1:
        _h1[sym] = families._h1(pd.read_parquet(
            BASE / "data" / "universe" / f"{sym}_H1.parquet"))
    return _h1[sym]


def series(sym: str, win: str, mult: float) -> pd.Series:
    """Daily R for one sleeve at a cost multiple. Cached: 12 cells x 3 mults."""
    key = (sym, win, mult)
    if key in _ser:
        return _ser[key]
    m = META[sym]
    base = 0.48 if sym == "XAUUSD" else max(
        m["median_spread_pts"] * m["tick_size"] * m["contract_size"], 0.05)
    cost = Costs(spread_per_lot=base * mult, commission_per_lot=3.50 * mult,
                 contract_oz=m["contract_size"])
    sigs = list(families.family_session_range_breakout(h1(sym), **WINDOWS[win]))
    tr = run_backtest(h1(sym), sigs, cost).trades
    s = pd.Series([t.r_multiple for t in tr],
                  index=pd.Index([t.entry_time.date() for t in tr])
                  ).groupby(level=0).sum()
    _ser[key] = s
    return s


def portfolio(names, mult: float) -> tuple:
    sl = {k: series(*k.split("."), mult) for k in names}
    days = sorted(set().union(*[set(v.index) for v in sl.values()]))
    port = pd.DataFrame({k: v.reindex(days).fillna(0.0) for k, v in sl.items()},
                        index=days).sum(axis=1)
    return port, sum(len(v) for v in sl.values())


def yearly(port: pd.Series, q: float, shift: float) -> pd.Series:
    """Calendar-year net return, compounded within the year and reset between.

    That is what "net yearly return" means to an account holder: the year's own
    multiple, not a slice of a cumulative curve already carrying prior size.
    """
    v = pd.Series(port.to_numpy(dtype=float) - shift,
                  index=pd.to_datetime(pd.Index(port.index)))
    return pd.Series({y: (float(np.cumprod(1 + q * c.to_numpy())[-1]) - 1.0)
                      for y, c in v.groupby(v.index.year)})


def measure(names, mult: float, drop_carry: bool) -> dict:
    """One book, one scenario. Half-edge throughout.

    The half-edge shift is computed on the FULL series before any years are
    dropped, so removing the carry years removes their returns without also
    lowering the penalty applied to the rest. Recomputing it on the survivors
    would quietly hand the pessimistic scenario a smaller haircut.
    """
    port, n_tr = portfolio(names, mult)
    shift = 0.5 * float(port.mean())
    if drop_carry:
        idx = pd.to_datetime(pd.Index(port.index))
        port = port[~idx.year.isin(CARRY_YEARS)]
    yrs = (max(port.index) - min(port.index)).days / 365.25
    q = TOTAL_HEAT / len(names)
    cagr, dd = compound(port, q, yrs, shift=shift)
    y = yearly(port, q, shift)
    return {"cagr": cagr, "dd": dd, "median": float(y.median()),
            "worst": float(y.min()), "best": float(y.max()),
            "pos": int((y > 0).sum()), "n_years": len(y), "n_tr": n_tr,
            "q": q, "yearly": y}


SCENARIOS = (
    ("as backtested (median spread + commission)", 1.0, False),
    ("2x costs — a first pass at stop-order slippage", 2.0, False),
    ("3x costs — the desk's own stress gate", 3.0, False),
    ("1x costs, ordinary regime (no 2022/2025)", 1.0, True),
    ("2x costs, ordinary regime", 2.0, True),
    ("3x costs AND ordinary regime — the floor", 3.0, True),
)


def main() -> int:
    all12 = sorted(f"{s}.{w}" for s in SYMBOLS for w in WINS
                   if (BASE / "data" / "universe" / f"{s}_H1.parquet").exists())
    books = {"5": FIVE, "8": EIGHT, "12": all12}

    print(f"REALISTIC NET CAGR — 5 vs 8 vs 12  ({REALITY_VERSION})")
    print(f"every book at {TOTAL_HEAT:.0%} TOTAL heat, half-edge, 2018-2026\n")

    res = {lbl: {sc[0]: measure(names, sc[1], sc[2]) for sc in SCENARIOS}
           for lbl, names in books.items()}

    print("=" * 94)
    print("NET CAGR")
    print("=" * 94)
    print(f"{'scenario':<48}{'book 5':>12}{'book 8':>12}{'book 12':>12}"
          f"{'  winner':>10}")
    print("-" * 94)
    for name, _, _ in SCENARIOS:
        v = {k: res[k][name]["cagr"] for k in books}
        best = max(v, key=lambda k: v[k])
        print(f"{name:<48}" + "".join(f"{v[k] * 100:>11.1f}%" for k in books)
              + f"{best:>10}")

    print()
    print("=" * 94)
    print("MEDIAN YEAR — the typical year, not the average one")
    print("=" * 94)
    print(f"{'scenario':<48}{'book 5':>12}{'book 8':>12}{'book 12':>12}")
    print("-" * 94)
    for name, _, _ in SCENARIOS:
        print(f"{name:<48}"
              + "".join(f"{res[k][name]['median'] * 100:>11.1f}%" for k in books))

    print()
    print("=" * 94)
    print("WORST YEAR, WORST DRAWDOWN, AND HOW MANY YEARS WERE POSITIVE")
    print("=" * 94)
    print(f"{'scenario':<42}" + "".join(f"{'book ' + k:>17}" for k in books))
    print("-" * 94)
    for name, _, _ in SCENARIOS:
        cells = []
        for k in books:
            r = res[k][name]
            cells.append(f"{r['worst'] * 100:>6.0f}% {r['dd'] * 100:>5.0f}% "
                         f"{r['pos']}/{r['n_years']}")
        print(f"{name:<42}" + "".join(f"{c:>17}" for c in cells))
    print("\n  columns: worst calendar year | worst drawdown | positive years")

    print()
    print("=" * 94)
    print("THE ASYMMETRY — return collapses, risk does not")
    print("=" * 94)
    print(f"{'book':<6}{'best case':>12}{'floor':>10}{'ratio':>8}"
          f"{'DD best':>10}{'DD floor':>10}   what the floor costs")
    print("-" * 94)
    for k in books:
        top = res[k][SCENARIOS[0][0]]
        flr = res[k][SCENARIOS[-1][0]]
        print(f"{k:<6}{top['cagr'] * 100:>11.1f}%{flr['cagr'] * 100:>9.1f}%"
              f"{top['cagr'] / max(flr['cagr'], 1e-9):>7.1f}x"
              f"{top['dd'] * 100:>9.0f}%{flr['dd'] * 100:>9.0f}%"
              f"   {(flr['dd'] - top['dd']) * 100:>+5.0f}pp of drawdown")
    print("\n  Costs eat the wins and leave the losses intact. The floor is not a\n"
          "  smaller version of the best case, it is a much worse Sharpe at the\n"
          "  same pain — which is why the ladder matters more than any one row.")

    print()
    print("=" * 94)
    print("YEAR BY YEAR AT THE FLOOR (3x costs, ordinary regime)")
    print("=" * 94)
    floor = SCENARIOS[-1][0]
    years = sorted(set().union(*[set(res[k][floor]["yearly"].index)
                                 for k in books]))
    print(f"{'year':<8}{'book 5':>12}{'book 8':>12}{'book 12':>12}")
    print("-" * 44)
    for y in years:
        print(f"{y:<8}" + "".join(
            f"{res[k][floor]['yearly'].get(y, float('nan')) * 100:>11.1f}%"
            for k in books))

    print()
    print("=" * 94)
    print("LOT GRANULARITY — the sizes the venue actually sells")
    print("=" * 94)
    print("The tables above assume risk can be set exactly. It cannot: 0.01 lots "
          "is the\nsmallest ticket, and on gold that ticket is large enough to "
          "overshoot policy\nby itself.\n")
    equity, q5 = 2177.0, TOTAL_HEAT / 5
    want = q5 * equity
    for k in FIVE:
        sym, win = k.split(".")
        m = META[sym]
        base = 0.48 if sym == "XAUUSD" else max(
            m["median_spread_pts"] * m["tick_size"] * m["contract_size"], 0.05)
        sigs = list(families.family_session_range_breakout(h1(sym), **WINDOWS[win]))
        tr = run_backtest(h1(sym), sigs,
                          Costs(base, 3.50, m["contract_size"])).trades
        rec = [t for t in tr if t.entry_time.year >= 2025]
        tick = float(np.median([abs(t.entry - t.stop) / m["tick_size"]
                                * m["tick_value"] * 0.01 for t in rec]))
        lots = max(1, round(want / tick))
        print(f"  {k:<20} ticket EUR{tick:>6.2f}  policy wants EUR{want:>6.2f}"
              f"  -> {lots:>2} x 0.01 = EUR{lots * tick:>6.2f}"
              f"   realised {lots * tick / equity:>5.2%} "
              f"({lots * tick / want - 1:+.0%} vs policy)")
    print(f"\n  At EUR{equity:,.0f} gold has no expressible size: one ticket "
          f"overshoots or undershoots\n  and there is nothing in between. The "
          f"fixed-fractional compounding every table\n  above assumes is not "
          f"available at this equity.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
