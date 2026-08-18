"""Year by year: what 5, 8 and 12 sleeves actually net, and how consistently.

A CAGR is one number laid over eight years, and it hides the two things that
decide whether a book is livable: how much the good years carry the average, and
how bad the worst one is. A book that returns 150%/yr as +900%, +40%, -30%,
+80%, -10% is not the same instrument as one that returns 150%/yr as +140%,
+160%, +130%, +170% — and the CAGR cannot tell them apart.

EVERY TABLE HERE IS MATCHED-RISK

Comparing books at the same q per leg gives the wide book more total heat and
therefore more return, which answers nothing. The comparisons below fix either
total heat or worst drawdown and let q fall out of it. See book_sizing.py for
why that reversal matters.

EVERY NUMBER HERE IS HALF-EDGE

The measured expectancy is biased upward: these sleeves were selected out of a
sweep, so the ones that reached this file are the ones that looked best. Every
return below subtracts half the mean daily P&L before compounding — a location
shift, not a rescale, because halving every R would halve the losses too and
that is a lower-volatility book rather than a worse one. The in-sample column is
printed alongside so the size of the haircut is visible rather than implied.

WHAT THESE NUMBERS ARE NOT

They are a backtest of session-range breakouts on H1 bars with modelled spread
and commission, compounded daily at a fixed fraction, with no lot granularity,
no slippage beyond the modelled cost, no swap, no gap risk beyond what the bars
contain, and no allowance for the correlation between sleeves rising in exactly
the drawdown where it would hurt. Real accounts get all of those. Treat the
ORDERING as the finding and the levels as an upper bound.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "research"))

from book_sizing import (  # noqa: E402
    EIGHT, FIVE, compound, half_edge_shift, load_cells, min_capital, policy_q,
    portfolio, q_for_drawdown)

YEARS_VERSION = "bookyears-2026-08-18-a"

#: The heat levels the year-by-year tables are run at. 5% is roughly where the
#: desk's own rule lands the five-sleeve book; the others bracket it.
HEATS = (0.03, 0.05, 0.07)

#: Drawdown the matched-risk euro table is solved to. The stated tolerance.
DD_TARGET = 0.35


def yearly(port: pd.Series, q: float, shift: float = 0.0) -> pd.Series:
    """Calendar-year net return of the fixed-fractional curve.

    Compounded WITHIN the year and reset between years, which is what "net
    yearly return" means to an account holder: the year's own multiple, not a
    slice of a cumulative curve that already carries the previous years' size.
    """
    v = pd.Series(port.to_numpy(dtype=float) - shift,
                  index=pd.to_datetime(pd.Index(port.index)))
    out = {}
    for y, chunk in v.groupby(v.index.year):
        eq = np.cumprod(1.0 + q * chunk.to_numpy())
        out[y] = (float(eq[-1]) - 1.0) if eq.min() > 0 else -1.0
    return pd.Series(out)


def main() -> int:
    cells = load_cells()
    all12 = sorted(cells)
    books = {"5": FIVE, "8": EIGHT, "12": all12}
    built = {}
    for label, names in books.items():
        port, yrs, n_tr = portfolio(cells, names)
        q, heat, keff, rho = policy_q(cells, names)
        built[label] = dict(port=port, yrs=yrs, n_tr=n_tr, n=len(names), q=q,
                            heat=heat, keff=keff, rho=rho, names=names,
                            shift=half_edge_shift(port))

    print(f"NET YEARLY RETURNS — 5 vs 8 vs 12  ({YEARS_VERSION})")
    print("All figures HALF-EDGE unless the column says in-sample.\n")

    # ------------------------------------------------ year by year, matched heat
    for heat in HEATS:
        print("=" * 92)
        print(f"AT {heat:.0%} TOTAL HEAT — the same money at risk, spread over "
              f"5, 8 or 12 legs")
        print("=" * 92)
        cols = {}
        for label, b in built.items():
            cols[label] = yearly(b["port"], heat / b["n"], b["shift"])
        idx = sorted(set().union(*[set(c.index) for c in cols.values()]))
        print(f"{'year':<8}{'q/leg 5':>0}", end="")
        print(f"{'book 5':>14}{'book 8':>14}{'book 12':>14}   winner")
        print("-" * 66)
        for y in idx:
            vals = {k: cols[k].get(y, float('nan')) for k in cols}
            best = max(vals, key=lambda k: (vals[k] if vals[k] == vals[k]
                                            else -9e9))
            partial = "  (partial year)" if y in (idx[0], idx[-1]) else ""
            print(f"{y:<8}" + "".join(f"{vals[k] * 100:>13.1f}%" for k in cols)
                  + f"   {best}{partial}")
        print("-" * 66)
        wins = {k: 0 for k in cols}
        for y in idx:
            vals = {k: cols[k].get(y, -9e9) for k in cols}
            wins[max(vals, key=lambda k: vals[k])] += 1
        print(f"{'best-year count':<8}"
              + "".join(f"{wins[k]:>13}" for k in cols))
        print(f"{'positive':<8}"
              + "".join(f"{int((cols[k] > 0).sum()):>10}/{len(cols[k]):<3}"
                        for k in cols))
        print(f"{'median':<8}"
              + "".join(f"{cols[k].median() * 100:>13.1f}%" for k in cols))
        print(f"{'worst':<8}"
              + "".join(f"{cols[k].min() * 100:>13.1f}%" for k in cols))
        cag = {}
        for label, b in built.items():
            cag[label] = compound(b["port"], heat / b["n"], b["yrs"],
                                  shift=b["shift"])
        print(f"{'CAGR':<8}" + "".join(f"{cag[k][0] * 100:>13.1f}%" for k in cols))
        print(f"{'worst DD':<8}" + "".join(f"{cag[k][1] * 100:>13.1f}%"
                                           for k in cols))
        print()

    # -------------------------------------------- the euro answer, matched DD
    print("=" * 92)
    print(f"IN EUROS — each book at its own minimum capital, sized to a "
          f"{DD_TARGET:.0%} drawdown")
    print("=" * 92)
    print("""
Two different constraints are stacked here and both are real. The MINIMUM is
what the venue's 0.01-lot floor demands before every leg can be sized at policy.
The RISK is solved separately, from the drawdown you are willing to sit through.
A book can clear the first and still be sized by the second.
""")
    print(f"{'book':<6}{'min cap':>10}{'q/leg':>9}{'heat':>8}{'CAGR':>9}"
          f"{'yr-1 net':>11}{'median yr':>11}{'worst yr':>11}")
    print("-" * 75)
    for label, b in built.items():
        q, c, dd = q_for_drawdown(b["port"], b["yrs"], DD_TARGET, shift=b["shift"])
        cap = min_capital(cells, b["names"], b["q"])
        yr = yearly(b["port"], q, b["shift"])
        print(f"{label:<6}{cap:>10,.0f}{q:>9.3%}{q * b['n']:>8.2%}"
              f"{c * 100:>8.1f}%{cap * c:>10,.0f}{yr.median() * 100:>10.1f}%"
              f"{yr.min() * 100:>10.1f}%")
    print("\n  yr-1 net is CAGR applied to the minimum capital — the first "
          "year's euros\n  before any compounding, which is the number that "
          "decides whether the book is\n  worth running at that size at all.")

    # ------------------------------------------------------- and the honest part
    print()
    print("=" * 92)
    print("THE SAME BOOKS WITHOUT THE HALF-EDGE HAIRCUT, AND WHY YOU SHOULD "
          "IGNORE IT")
    print("=" * 92)
    print(f"{'book':<6}{'in-sample':>12}{'half-edge':>12}{'quarter':>12}"
          f"{'ratio':>9}")
    print("-" * 51)
    for label, b in built.items():
        q, _, _ = q_for_drawdown(b["port"], b["yrs"], DD_TARGET, shift=b["shift"])
        ins, _ = compound(b["port"], q, b["yrs"])
        hlf, _ = compound(b["port"], q, b["yrs"], shift=b["shift"])
        qtr, _ = compound(b["port"], q, b["yrs"], shift=1.5 * b["shift"])
        print(f"{label:<6}{ins * 100:>11.1f}%{hlf * 100:>11.1f}%"
              f"{qtr * 100:>11.1f}%{ins / max(hlf, 1e-9):>8.1f}x")
    print("\n  The in-sample column is 5-6x the half-edge one. That gap is not "
          "conservatism,\n  it is the cost of selection: these twelve cells were "
          "chosen from a sweep, and\n  the amount by which a chosen cell "
          "outperforms is exactly what does not repeat.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
