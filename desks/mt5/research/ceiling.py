"""The growth ceiling after every correction, and what is actually expected.

FOUR THINGS CHANGED SINCE THE 147.8% HEADLINE, AND THEY DO NOT ALL POINT THE
SAME WAY

    GOLD'S SPREAD IS NOW CHARGED. It was being charged 3% of its real spread in
    every backtest this desk has run. Costs here are 2x the median spread, which
    is the honest round trip. This is a large cut and it is not recoverable.

    rr IS TUNED PER SLEEVE. The 3,168-cell sweep found rr=2.5 beats the armed
    rr=2.0 on XAUUSD.asia (2.467 against 2.321). Free, and applies to something
    already traded.

    EIGHTEEN NEW MECHANISMS CLEAR ADMISSION. monday_gap|mode=fade on four
    symbols at rho of 0.02-0.08, which is the low-correlation shape that raises
    growth rather than diluting it. All IN-SAMPLE.

    HEAT IS SOLVED, NOT DECLARED. BASE_HEAT was a 3.81% literal nobody derived,
    capping the book at 3.81% x sqrt(k) forever. solve_heat() bisects for the
    heat whose worst drawdown equals the stated tolerance, so breadth widens the
    budget by itself.

WHY THE HEADLINE NUMBER HERE IS STILL NOT A FORECAST

The eighteen were chosen as the best of 3,168 cells on the same history that
scores them. Their in-sample Sharpes carry the full selection premium, and the
correlations that make them look complementary are measured on that same
history. Every table below therefore prints three columns:

    IN-SAMPLE    the ceiling. What the numbers say with no discount.
    HALF-EDGE    expected value halved by a location shift. The desk's standard.
    FORWARD      half-edge AND the new sleeves shrunk toward zero by the
                 selection premium implied by their own search.

The third is the one to plan against. The first is what a backtest brochure
would print.
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
sys.path.insert(0, "/home/user/Aurum")

warnings.filterwarnings("ignore")

from mt5desk import families                                    # noqa: E402
from mt5desk.engine import Costs, run_backtest                  # noqa: E402
from run_hunt11 import WINDOWS                                  # noqa: E402
from golddesk.growth import solve_heat                          # noqa: E402

CEILING_VERSION = "ceiling-2026-08-18-a"

SPREAD_MULT = 2.0
TPY = 252
META = json.loads((BASE / "data" / "universe" / "universe.json").read_text("utf-8"))
CACHE = BASE / "data" / "full_hunt_series.parquet"
CANDS = BASE / "data" / "hunt_candidates.json"

#: The armed five, and the rr the sweep says is best for each.
ARMED = {"XAUUSD.asia": 2.5, "USDJPY.asia": 2.0, "CADJPY.asia": 2.0,
         "EURJPY.asia": 2.0, "XAUUSD.london_am": 2.5}

#: Standard error of an annualised Sharpe over this sample. Used to shrink the
#: new sleeves toward zero: a cell selected as the best of N carries a premium
#: of roughly SE x E[max of N standard normals], and that premium is exactly
#: the part that does not repeat.
_YEARS = 8.6
SE_SHARPE = 1.0 / math.sqrt(_YEARS)

_h1: dict = {}


def h1(sym: str) -> pd.DataFrame:
    if sym not in _h1:
        _h1[sym] = families._h1(pd.read_parquet(
            BASE / "data" / "universe" / f"{sym}_H1.parquet"))
    return _h1[sym]


def armed_series(key: str, rr: float) -> pd.Series:
    sym, win = key.split(".")
    kw = {**WINDOWS[win], "rr": rr}
    tr = run_backtest(h1(sym),
                      list(families.family_session_range_breakout(h1(sym), **kw)),
                      Costs.from_symbol(META[sym], SPREAD_MULT)).trades
    return pd.Series([t.r_multiple for t in tr],
                     index=pd.Index([t.entry_time.date() for t in tr])
                     ).groupby(level=0).sum()


def sharpe(x) -> float:
    x = np.asarray(x, dtype=float)
    return 0.0 if x.std(ddof=1) == 0 else float(
        x.mean() / x.std(ddof=1) * math.sqrt(TPY))


def book(cols: dict, shrink: dict | None = None) -> pd.Series:
    """Edge-weighted portfolio. `shrink` scales a sleeve's daily mean only.

    Scaling the MEAN and not the whole series is the point: shrinking every
    observation would shrink the losses too, which is a lower-volatility sleeve
    rather than a weaker one, and would raise its Kelly optimum instead of
    lowering it.
    """
    days = sorted(set().union(*[set(v.index) for v in cols.values()]))
    out = {}
    for k, v in cols.items():
        s = v.reindex(days).fillna(0.0)
        f = (shrink or {}).get(k)
        if f is not None and f < 1.0:
            out[k] = s - (1.0 - f) * float(v.mean()) * (s != 0)
        else:
            out[k] = s
    df = pd.DataFrame(out, index=days)
    w = np.maximum(df.mean(axis=0).to_numpy(dtype=float), 0.0)
    w = w / w.sum() if w.sum() > 0 else np.ones(len(w)) / len(w)
    return pd.Series(df.to_numpy(dtype=float) @ w, index=days)


def cagr_at(port: pd.Series, tolerance: float, half_edge: bool) -> tuple:
    heat, why = solve_heat(port.to_numpy(dtype=float), tolerance=tolerance,
                           half_edge=half_edge)
    if heat <= 0:
        return float("nan"), 0.0, why
    yrs = (max(port.index) - min(port.index)).days / 365.25
    shift = 0.5 * float(port.mean()) if half_edge else 0.0
    v = port.to_numpy(dtype=float) - shift
    eq = np.cumprod(1.0 + heat * v)
    if eq.min() <= 0:
        return float("nan"), heat, "ruin"
    dd = float((eq / np.maximum.accumulate(eq) - 1.0).min())
    return float(eq[-1]) ** (1.0 / yrs) - 1.0, heat, f"dd {dd:.1%}"


def main() -> int:
    print(f"GROWTH CEILING AFTER THE CORRECTIONS  ({CEILING_VERSION})")
    print(f"gold spread charged properly, {SPREAD_MULT:.0f}x median, heat "
          f"SOLVED not declared\n")

    # ------------------------------------------------------------- the books
    old = {k: armed_series(k, 2.0) for k in ARMED}
    tuned = {k: armed_series(k, rr) for k, rr in ARMED.items()}

    df = pd.read_parquet(CACHE)
    cands = json.loads(CANDS.read_text("utf-8"))
    best: dict = {}
    for r in cands:
        p = r["cell"].split("|")
        key = f"{p[0]}.{p[1]}"
        if key not in best or r["in_sample_sharpe"] > best[key]["in_sample_sharpe"]:
            best[key] = r
    incumbent = {"XAUUSD.session_breakout.asia", "USDJPY.session_breakout.asia",
                 "CADJPY.session_breakout.asia", "EURJPY.session_breakout.asia",
                 "XAUUSD.session_breakout.london_am"}
    new: dict = {}
    for key, r in best.items():
        if key in incumbent:
            continue
        s = df[r["cell"]].dropna()
        s = pd.Series(s.to_numpy(dtype=float),
                      index=[i.date() for i in s.index]).groupby(level=0).sum()
        if len(s) >= 200:
            new[key] = s

    # Shrinkage: a cell selected as best-of-N carries about SE x E[max of N] of
    # premium. Expressed as a multiplier on the mean, floored at zero.
    n_search = 3168
    emax = math.sqrt(2.0 * math.log(max(n_search, 2)))
    premium = SE_SHARPE * emax
    shrink = {}
    for k, s in new.items():
        sr = sharpe(s.to_numpy(dtype=float))
        shrink[k] = max(0.0, (sr - premium) / sr) if sr > 0 else 0.0

    print("=" * 92)
    print("THE SLEEVES")
    print("=" * 92)
    print(f"{'sleeve':<38}{'SR':>8}{'source':>16}{'forward factor':>16}")
    print("-" * 78)
    for k, rr in ARMED.items():
        s = tuned[k]
        tag = f"armed, rr={rr}" + ("  TUNED" if rr != 2.0 else "")
        print(f"{k:<38}{sharpe(s.to_numpy(dtype=float)):>8.3f}{tag:>16}"
              f"{1.0:>16.2f}")
    for k in sorted(new, key=lambda k: -sharpe(new[k].to_numpy(dtype=float))):
        print(f"{k:<38}{sharpe(new[k].to_numpy(dtype=float)):>8.3f}"
              f"{'hunt, in-sample':>16}{shrink[k]:>16.2f}")
    print(f"\n  forward factor = (SR - {premium:.2f}) / SR, the selection premium "
          f"for best-of-{n_search}\n  removed. Armed sleeves keep 1.00 — they "
          f"have already traded forward.")

    # ------------------------------------------------------------ the ceilings
    print()
    print("=" * 92)
    print("NET CAGR BY DRAWDOWN TOLERANCE — heat solved from the book itself")
    print("=" * 92)
    books = {
        "1. armed 5, as traded (rr=2.0)": (old, None),
        "2. armed 5, rr tuned": (tuned, None),
        "3. + 18 hunt sleeves, IN-SAMPLE": ({**tuned, **new}, None),
        "4. + 18 hunt sleeves, forward-shrunk": ({**tuned, **new}, shrink),
    }
    print(f"{'book':<40}{'dd 25%':>11}{'dd 35%':>11}{'dd 45%':>11}{'dd 55%':>11}")
    print("-" * 84)
    for lbl, (cols, shr) in books.items():
        port = book(cols, shr)
        row = []
        for tol in (0.25, 0.35, 0.45, 0.55):
            c, heat, _ = cagr_at(port, tol, half_edge=True)
            row.append(f"{c * 100:>10.1f}%" if np.isfinite(c) else f"{'—':>11}")
        print(f"{lbl:<40}" + "".join(row))
    print("\n  every figure HALF-EDGE. Row 3 is the ceiling a brochure would "
          "print; row 4 is\n  the one to plan against.")

    # ---------------------------------------------------------- the heat solved
    print()
    print("=" * 92)
    print("WHAT THE SOLVED HEAT ACTUALLY RETURNS — the old cap was 3.81% x "
          "sqrt(k_eff)")
    print("=" * 92)
    print(f"{'book':<40}{'sleeves':>9}{'heat @35%':>12}{'vs old cap':>13}")
    print("-" * 74)
    for lbl, (cols, shr) in books.items():
        port = book(cols, shr)
        heat, _ = solve_heat(port.to_numpy(dtype=float), tolerance=0.35)
        n = len(cols)
        old_cap = 0.0381 * math.sqrt(min(n, 7.3))
        print(f"{lbl:<40}{n:>9}{heat:>11.2%}{heat / old_cap:>12.2f}x")
    print("\n  The old literal would have capped every one of these at roughly "
          "the same\n  number regardless of what the book measured, which is "
          "what a constant does.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
