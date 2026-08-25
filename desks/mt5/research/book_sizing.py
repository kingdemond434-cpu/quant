"""Five sleeves, eight or twelve — which book earns most, and what each costs.

THE QUESTION THAT LOOKS OBVIOUS AND IS NOT

Twelve sleeves produce more raw R than five: +309R/yr against +203R/yr, from a
book with twice the effective breadth (k_eff 6.40 against 3.23) and a lower mean
correlation. Every one of those facts favours the wide book, and taken together
they look decisive.

They are not, because R per year is not money per year. Money per year is R
multiplied by the size each R is taken at, and size is bounded by drawdown. The
twelve-sleeve book has a lower expectancy per trade — +0.1124R against +0.1658R
— because the four sleeves that widen it are the four weakest ones, and the
lowest of them, USDJPY.afternoon at +0.0124R, is indistinguishable from zero and
does not survive a 3x cost stress. A book that trades more often at a worse edge
is not obviously richer, and the arithmetic has to be done.

WHY "SAME q PER LEG" IS THE WRONG COMPARISON AND FLIPS THE ANSWER

At an equal risk fraction per leg the twelve-sleeve book wins at every level, by
a lot. It also has to: twelve legs at 0.5% each deploys 6.0% of total heat while
five legs at 0.5% deploys 2.5%. That table measures which book was handed more
leverage, and the answer to that question was decided by the comparison itself.

The comparisons that mean something hold RISK fixed rather than size:

    matched total heat  — the same money at risk, spread differently
    matched drawdown    — the same ride, solved for the q that produces it

On both, the ordering reverses and stays reversed: 5 > 8 > 12 at every level
tested. At a 45% worst drawdown the five-sleeve book compounds at 240%/yr on
half the measured edge and the twelve at 170%. The breadth is real and it does
lower the drawdown at matched heat — that part of the wide book's case survives
— but it does not recover the expectancy the extra sleeves gave away.

An earlier version of this comparison sized each book at heat = BASE x
sqrt(k_eff) and reported that the eight-sleeve book won. That comparison was
also handing the books different total heat (8.15% against 6.84%), so it was
measuring the sizing rule and not the books. Matched-risk is the correction, and
it moves the answer from 8 to 5.

THE MINIMUM CAPITAL IS SET BY THE STOP, NOT BY THE MARGIN

Margin was never the constraint; at 0.01 lots the broker will open any of these
at almost any funded balance. The constraint is that 0.01 lots is the SMALLEST
BET AVAILABLE, so below a certain equity the venue's granularity forces a larger
realised risk than policy and the desk runs hotter than it believes it runs.

Two errors are easy here and both were made before this file existed:

    CURRENCY. min_lot * contract_size * stop_distance is correct only when the
    quote currency is the account currency. On the JPY crosses it returns yen
    and reads them as euros. tick_value in universe.json is already in account
    currency, so the honest conversion is
    (stop_distance / tick_size) * tick_value * lot.

    REGIME. Gold traded at $1,300 in 2018 and $3,300 now, so a stop denominated
    in dollars per ounce has roughly tripled. The full-history median puts one
    XAUUSD.asia ticket at EUR7.25 and the last eighteen months put it at
    EUR29.80. Sizing a 2026 account off the first number understates the real
    risk by a factor of four. Edge statistics still use the whole history —
    R-multiples are normalised by the stop and do not have this problem — but
    capital requirements must use the current regime.
"""
from __future__ import annotations

import json
import math
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

SIZING_VERSION = "booksizing-2026-08-18-a"

#: Base total heat with no measured breadth, matching golddesk.growth.BASE_HEAT.
BASE_HEAT = 0.0381

#: The venue's smallest ticket. The entire minimum-capital question.
MIN_LOT = 0.01

#: Stops from this year forward set the capital requirement. Everything before
#: it is a different price regime for gold.
SIZING_FROM_YEAR = 2025

SYMBOLS = ("XAUUSD", "CADJPY", "EURJPY", "USDJPY")
WINS = ("asia", "london_am", "afternoon")

#: The five that clear all ten gates at N=12 in gauntlet_unconditioned, then the
#: three that follow them on expectancy. Membership is recorded here rather than
#: recomputed so the books being compared cannot drift between runs.
FIVE = ["XAUUSD.asia", "USDJPY.asia", "CADJPY.asia", "EURJPY.asia",
        "XAUUSD.london_am"]
EIGHT = FIVE + ["USDJPY.london_am", "CADJPY.london_am", "XAUUSD.afternoon"]

META = json.loads((BASE / "data" / "universe" / "universe.json").read_text("utf-8"))

_h1: dict = {}


def h1(sym: str) -> pd.DataFrame:
    if sym not in _h1:
        _h1[sym] = families._h1(pd.read_parquet(
            BASE / "data" / "universe" / f"{sym}_H1.parquet"))
    return _h1[sym]


def cell(sym: str, win: str) -> dict | None:
    """One unconditioned symbol-window sleeve: daily R, and euros per ticket."""
    m = META[sym]
    cost = Costs.from_symbol(m, mult=2.0)  # canonical costs (round-trip spread * 2)
    sigs = list(families.family_session_range_breakout(h1(sym), **WINDOWS[win]))
    trades = run_backtest(h1(sym), sigs, cost).trades
    if len(trades) < 60:
        return None
    r = pd.Series([t.r_multiple for t in trades],
                  index=pd.Index([t.entry_time.date() for t in trades])
                  ).groupby(level=0).sum()

    def eur(ts):
        return np.array([abs(t.entry - t.stop) / m["tick_size"]
                         * m["tick_value"] * MIN_LOT for t in ts], dtype=float)

    recent = [t for t in trades if t.entry_time.year >= SIZING_FROM_YEAR]
    e_all = eur(trades)
    e_now = eur(recent) if len(recent) >= 30 else e_all
    return {"r": r, "n": len(trades),
            "eur_med": float(np.median(e_now)),
            "eur_p90": float(np.percentile(e_now, 90)),
            "eur_max": float(e_now.max()),
            "eur_med_all": float(np.median(e_all))}


def load_cells() -> dict:
    out = {}
    for s in SYMBOLS:
        for w in WINS:
            c = cell(s, w)
            if c is not None:
                out[f"{s}.{w}"] = c
    return out


def rho_of(cells: dict, names) -> float:
    """Mean pairwise correlation on OVERLAPPING DAYS ONLY.

    Zero-filling absent days counts "one sleeve traded, the other did not" as an
    uncorrelated observation. That inflates measured breadth, which widens the
    heat budget, which is the one direction an error here must never go.
    """
    vals = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            com = sorted(set(cells[a]["r"].index) & set(cells[b]["r"].index))
            if len(com) < 30:
                continue
            x = cells[a]["r"].reindex(com).to_numpy()
            y = cells[b]["r"].reindex(com).to_numpy()
            if x.std() > 0 and y.std() > 0:
                vals.append(float(np.corrcoef(x, y)[0, 1]))
    return float(np.mean(vals)) if vals else 0.0


def portfolio(cells: dict, names) -> tuple:
    days = sorted(set().union(*[set(cells[k]["r"].index) for k in names]))
    yrs = (max(days) - min(days)).days / 365.25
    port = pd.DataFrame({k: cells[k]["r"].reindex(days).fillna(0.0)
                         for k in names}, index=days).sum(axis=1)
    return port, yrs, sum(cells[k]["n"] for k in names)


def compound(port: pd.Series, q: float, yrs: float, shift: float = 0.0) -> tuple:
    """CAGR and worst equity drawdown of the fixed-fractional curve.

    CAGR, never the total multiple. Eight years of daily compounding turns any
    positive edge into a number with no intuition attached, and it is the total
    that makes a 0.16R expectancy read as a printing press.
    """
    v = port.to_numpy(dtype=float) - shift
    eq = np.cumprod(1.0 + q * v)
    if eq.min() <= 0:
        return float("nan"), -1.0
    dd = float((eq / np.maximum.accumulate(eq) - 1.0).min())
    return float(eq[-1]) ** (1.0 / yrs) - 1.0, dd


def half_edge_shift(port: pd.Series) -> float:
    """Half the mean daily P&L — a LOCATION SHIFT, not a rescale.

    Scaling every R by 0.5 halves the losses too, which is not a worse edge: it
    is the same edge at half the volatility, and its Kelly optimum is HIGHER.
    Edge degradation shows up in the wins and the hit rate, so subtracting from
    the mean is the transformation that models it.
    """
    return 0.5 * float(port.mean())


def q_for_drawdown(port: pd.Series, yrs: float, target: float,
                   shift: float = 0.0) -> tuple:
    """Bisect for the risk fraction whose worst drawdown equals `target`."""
    lo, hi = 1e-5, 0.20
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        _, dd = compound(port, mid, yrs, shift=shift)
        if not np.isfinite(dd) or abs(dd) > target:
            hi = mid
        else:
            lo = mid
    return (lo,) + compound(port, lo, yrs, shift=shift)


def policy_q(cells: dict, names) -> tuple:
    """The desk's own sizing rule: heat = BASE x sqrt(k_eff), split evenly."""
    n = len(names)
    rho = rho_of(cells, names)
    keff = max(1.0, min(n, n / (1 + (n - 1) * rho)))
    heat = BASE_HEAT * math.sqrt(keff)
    return heat / n, heat, keff, rho


def min_capital(cells: dict, names, q: float, which: str = "eur_med") -> float:
    """Equity at which EVERY leg can be sized at policy with 0.01 lots.

    The maximum over legs, not the mean: a book is expressible when its WIDEST
    sleeve is, and averaging would report a figure at which the gold leg is
    still over-risked.
    """
    return max(cells[k][which] / q for k in names)


def main() -> int:
    cells = load_cells()
    all12 = sorted(cells)
    books = {"5": FIVE, "8": EIGHT, "12": all12}

    print(f"BOOK SIZING  ({SIZING_VERSION})")
    print("=" * 98)
    print("PER-SLEEVE — what one minimum ticket risks, and what it pays")
    print("=" * 98)
    print(f"EUR columns are {SIZING_FROM_YEAR}+ stops at {MIN_LOT} lots, the "
          f"regime the account will trade in.\n'2018-26' is the full-history "
          f"median, shown only to make the drift visible.\n")
    print(f"{'sleeve':<22}{'trades':>7}{'exp_R':>9}{'EUR@0.01':>10}{'p90':>8}"
          f"{'worst':>8}{'2018-26':>9}   book")
    for k in all12:
        c = cells[k]
        tag = "5" if k in FIVE else ("8" if k in EIGHT else "12")
        print(f"{k:<22}{c['n']:>7}{c['r'].sum() / c['n']:>+9.4f}"
              f"{c['eur_med']:>10.2f}{c['eur_p90']:>8.2f}{c['eur_max']:>8.2f}"
              f"{c['eur_med_all']:>9.2f}   {tag}")

    print()
    print("=" * 98)
    print("AT THE DESK'S OWN SIZING RULE — heat = 3.81% x sqrt(k_eff), split "
          "evenly")
    print("=" * 98)
    hdr = (f"{'book':<6}{'N':>3}{'k_eff':>7}{'rho':>8}{'heat':>7}{'q/leg':>8}"
           f"{'exp_R':>9}{'tr/yr':>7}{'R/yr':>8}{'CAGRis':>9}{'half':>9}"
           f"{'quarter':>9}{'wDD':>8}{'minEUR':>8}")
    print(hdr)
    print("-" * len(hdr))
    rows = {}
    for label, names in books.items():
        port, yrs, n_tr = portfolio(cells, names)
        q, heat, keff, rho = policy_q(cells, names)
        d = half_edge_shift(port)
        ins, _ = compound(port, q, yrs)
        hlf, dd = compound(port, q, yrs, shift=d)
        qtr, _ = compound(port, q, yrs, shift=1.5 * d)
        need = min_capital(cells, names, q)
        rows[label] = dict(port=port, yrs=yrs, n=len(names), q=q, need=need)
        print(f"{label:<6}{len(names):>3}{keff:>7.2f}{rho:>+8.4f}{heat:>6.2%}"
              f"{q:>8.3%}{port.sum() / n_tr:>+9.4f}{n_tr / yrs:>7.0f}"
              f"{port.sum() / yrs:>+8.1f}{ins * 100:>8.1f}%{hlf * 100:>8.1f}%"
              f"{qtr * 100:>8.1f}%{dd * 100:>7.1f}%{need:>8.0f}")
    print("\nThis table hands each book a DIFFERENT total heat, so it ranks the "
          "sizing rule\nrather than the books. The matched-risk tables below are "
          "the comparison.")

    print()
    print("=" * 98)
    print("MINIMUM CAPITAL — set by the widest-stop sleeve, never by margin")
    print("=" * 98)
    for label, names in books.items():
        r = rows[label]
        binding = max(names, key=lambda k: cells[k]["eur_med"])
        print(f"\n  book of {label}:  q/leg {r['q']:.3%}")
        for k in sorted(names, key=lambda k: -cells[k]["eur_med"])[:3]:
            c = cells[k]
            print(f"    {k:<22} EUR{c['eur_med']:>7.2f}/ticket -> needs "
                  f"EUR{c['eur_med'] / r['q']:>7.0f}"
                  + ("   <-- BINDING" if k == binding else ""))
        print(f"    MINIMUM, all legs at policy:     EUR{r['need']:>7.0f}")
        print(f"    at p90 stops instead of median:  "
              f"EUR{min_capital(cells, names, r['q'], 'eur_p90'):>7.0f}")
        hot = max(cells[k]["eur_med"] for k in names) / 300.0
        print(f"    on EUR300 the widest leg risks {hot:.1%} per trade "
              f"({hot / r['q']:.1f}x policy)")

    print()
    print("=" * 98)
    print("WHAT EUR300 CAN ACTUALLY RUN — gold is the whole constraint")
    print("=" * 98)
    print("\nEvery binding number above is a gold sleeve. One 0.01-lot gold "
          "ticket risks\nEUR29.80 at the median 2025-26 stop; the same ticket on "
          "USDJPY risks EUR2.91.\nThat 10x gap in the smallest available bet is "
          "why the gold book needs four\nfigures and a JPY book does not.\n")
    variants = (
        ("gold only (3)", [k for k in all12 if k.startswith("XAU")]),
        ("JPY asia (3)", ["USDJPY.asia", "CADJPY.asia", "EURJPY.asia"]),
        ("JPY, all 9", [k for k in all12 if not k.startswith("XAU")]),
        ("the 5", FIVE), ("the 8", EIGHT), ("all 12", all12))
    for label, names in variants:
        port, yrs, n_tr = portfolio(cells, names)
        q, _, _, _ = policy_q(cells, names)
        need = min_capital(cells, names, q)
        c, _ = compound(port, q, yrs, shift=half_edge_shift(port))
        print(f"  {label:<16} N={len(names):<3} q/leg {q:>6.3%}  "
              f"needs EUR{need:>6.0f}  exp {port.sum() / n_tr:>+7.4f}R  "
              f"{port.sum() / yrs:>+6.0f}R/yr  half-edge CAGR {c * 100:>6.1f}%  "
              + ("RUNS ON EUR300" if need <= 300 else f"needs {need / 300:.1f}x"))

    print()
    print("=" * 98)
    print("MATCHED DRAWDOWN — the comparison that is about edge, not leverage")
    print("=" * 98)
    for target in (0.25, 0.35, 0.45):
        print(f"\n  at a {target:.0%} worst drawdown (half-edge):")
        for label in books:
            r = rows[label]
            d = half_edge_shift(r["port"])
            q, c, dd = q_for_drawdown(r["port"], r["yrs"], target, shift=d)
            print(f"    book of {label:<3} q/leg {q:>6.3%}  total heat "
                  f"{q * r['n']:>6.2%}  ->  CAGR {c * 100:>7.1f}%  "
                  f"(dd {dd * 100:>5.1f}%)")

    print()
    print("=" * 98)
    print("MATCHED TOTAL HEAT — the same money at risk, spread differently")
    print("=" * 98)
    print(f"{'total heat':<12}{'book 5':>18}{'book 8':>18}{'book 12':>18}"
          "     (half-edge CAGR)")
    for heat in (0.03, 0.05, 0.07, 0.09):
        out = []
        for label in books:
            r = rows[label]
            c, dd = compound(r["port"], heat / r["n"], r["yrs"],
                             shift=half_edge_shift(r["port"]))
            out.append(f"{c * 100:>11.1f}% ({dd * 100:>3.0f}%)")
        print(f"{heat:<12.1%}{''.join(out)}")
    print("\n  5 > 8 > 12 at every matched level. The wide book's lower "
          "correlation is real\n  and shows up in its drawdown column, but it "
          "does not recover the expectancy\n  the four weakest sleeves gave "
          "away.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
