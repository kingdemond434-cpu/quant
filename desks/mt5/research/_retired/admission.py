"""When does adding a sleeve RAISE net growth, and when does it dilute?

The measured result -- 5 sleeves beating 8 and 12 -- is easy to misread as
"narrow is better", and that reading is wrong. Breadth is not the problem. The
four sleeves that widened 5 to 12 were the four WEAKEST, three of them outright
negative once gold's spread was charged properly, and equal-weighting then made
each of them cost a slice of XAUUSD.asia's size to fund. That is a bad-sleeve
problem and an allocation problem wearing a breadth costume.

THE TEST IS A THRESHOLD AND IT HAS A CLOSED FORM

A new sleeve improves the portfolio's Sharpe -- and therefore its growth at any
matched drawdown -- exactly when

    SR_new  >  SR_portfolio  x  rho(new, portfolio)

which is the standard marginal-Sharpe condition, and it says three useful things
at once:

    A sleeve UNCORRELATED to the book (rho = 0) improves it at ANY positive
    Sharpe, however small. There is no such thing as too weak if it is genuinely
    independent.

    A sleeve perfectly correlated to the book (rho = 1) must beat the book's own
    Sharpe outright. Adding a worse copy of what you already own is strictly
    destructive.

    Between those, the bar scales linearly in correlation. This is why the
    afternoon sleeves failed: not merely weak, but weak AND highly correlated to
    the asia sleeves that already carry the book.

WHY THE HEAT BUDGET MAKES IT BETTER THAN THAT

Passing the admission test raises the Sharpe. It also raises k_eff, and heat is
budgeted at BASE x sqrt(k_eff), so a genuinely independent sleeve widens the
budget as well as improving the ratio. Both effects push the same way, which is
the mechanism by which a desk is supposed to compound faster as it earns
breadth rather than by taking more risk on what it already has.

k_eff = N/(1 + (N-1)rho) saturates at 1/rho, so at the measured rho of 0.137 the
ceiling is about 7.3 effective bets however many sleeves get added. Past that,
more sleeves of the same correlation buy nothing and the honest answer to "grow
faster" becomes genuinely uncorrelated edges or more capital.

WHAT THE SYNTHETIC SECTION IS AND IS NOT

The second half adds SIMULATED sleeves at a chosen Sharpe and correlation to
show the shape of the answer. Simulated sleeves always behave, so those numbers
are an upper bound on what a real one would do, and they are here to price the
question "what would a new edge need to look like" rather than to forecast.
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
from mt5desk.sizing import solve_size                        # noqa: E402
from run_hunt11 import WINDOWS                                  # noqa: E402
from book_sizing import FIVE, SYMBOLS, WINS, compound, q_for_drawdown  # noqa: E402

ADMISSION_VERSION = "admission-2026-08-18-a"

#: The honest cost: a round trip crosses the median spread twice.
SPREAD_MULT = 2.0

#: Drawdown every comparison is solved to, so growth differences are about edge
#: rather than leverage.
DD_TARGET = 0.35

#: Trading days per year, for annualising a daily Sharpe.
TPY = 252

META = json.loads((BASE / "data" / "universe" / "universe.json").read_text("utf-8"))
_h1: dict = {}
_ser: dict = {}


def h1(sym: str) -> pd.DataFrame:
    if sym not in _h1:
        _h1[sym] = families._h1(pd.read_parquet(
            BASE / "data" / "universe" / f"{sym}_H1.parquet"))
    return _h1[sym]


def series(sym: str, win: str) -> pd.Series:
    if (sym, win) in _ser:
        return _ser[(sym, win)]
    tr = run_backtest(
        h1(sym),
        list(families.family_session_range_breakout(h1(sym), **WINDOWS[win])),
        Costs.from_symbol(META[sym], SPREAD_MULT)).trades
    s = pd.Series([t.r_multiple for t in tr],
                  index=pd.Index([t.entry_time.date() for t in tr])
                  ).groupby(level=0).sum()
    _ser[(sym, win)] = s
    return s


def sharpe(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    return 0.0 if x.std(ddof=1) == 0 else float(x.mean() / x.std(ddof=1)
                                                * math.sqrt(TPY))


def frame(names) -> pd.DataFrame:
    """Daily R per sleeve on a common calendar.

    Zero-filled ACROSS THE BOOK, which is correct here and not correct for
    measuring pairwise correlation: a day one sleeve sat out really does
    contribute zero to portfolio P&L, but treating it as an uncorrelated
    observation when estimating rho would manufacture breadth. rho is measured
    on overlap only, in `pairwise_rho`.
    """
    sl = {k: series(*k.split(".")) for k in names}
    days = sorted(set().union(*[set(v.index) for v in sl.values()]))
    return pd.DataFrame({k: sl[k].reindex(days).fillna(0.0) for k in names},
                        index=days)


def pairwise_rho(a: pd.Series, b: pd.Series) -> float | None:
    com = sorted(set(a.index) & set(b.index))
    if len(com) < 30:
        return None
    x, y = a.reindex(com).to_numpy(), b.reindex(com).to_numpy()
    if x.std() == 0 or y.std() == 0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def edge_weights(df: pd.DataFrame) -> np.ndarray:
    """Weights proportional to measured expectancy, negatives zeroed.

    Equal weights are what made breadth look destructive: they force the best
    sleeve to surrender size to fund the worst. Weighting by edge is the
    baseline any breadth question should be asked against.
    """
    w = np.maximum(df.mean(axis=0).to_numpy(dtype=float), 0.0)
    return w / w.sum() if w.sum() > 0 else np.ones(len(w)) / len(w)


def growth_at_dd(df: pd.DataFrame, target: float = DD_TARGET) -> tuple:
    """CAGR at a matched drawdown, half-edge, with edge weights."""
    w = edge_weights(df)
    port = pd.Series(df.to_numpy(dtype=float) @ w, index=df.index)
    yrs = (max(port.index) - min(port.index)).days / 365.25
    shift = 0.5 * float(port.mean())
    q, cagr, dd = q_for_drawdown(port, yrs, target, shift=shift)
    return cagr, dd, q, sharpe(port.to_numpy(dtype=float) - shift)


def main() -> int:
    all12 = sorted(f"{s}.{w}" for s in SYMBOLS for w in WINS
                   if (BASE / "data" / "universe" / f"{s}_H1.parquet").exists())
    base = frame(FIVE)
    w5 = edge_weights(base)
    port5 = pd.Series(base.to_numpy(dtype=float) @ w5, index=base.index)
    sr5 = sharpe(port5.to_numpy(dtype=float))

    print(f"ADMISSION TEST  ({ADMISSION_VERSION})")
    print(f"the five-sleeve book, edge-weighted, at {SPREAD_MULT:.0f}x the "
          f"median spread")
    print(f"portfolio Sharpe {sr5:.3f} RAW (in-sample). Every candidate below is "
          f"scored raw\ntoo, so the comparison is like-for-like; the growth "
          f"tables further down are all\nhalf-edge, which is why the Sharpe "
          f"there reads about half this.\n")

    print("=" * 90)
    print("SR_new > SR_book x rho   — the exact condition for a sleeve to help")
    print("=" * 90)
    print(f"{'candidate':<22}{'SR':>8}{'rho vs book':>13}{'bar':>8}"
          f"{'margin':>9}   verdict")
    print("-" * 90)
    cands = [k for k in all12 if k not in FIVE]
    for k in sorted(cands, key=lambda k: -sharpe(series(*k.split(".")).to_numpy())):
        s = series(*k.split("."))
        sr = sharpe(s.to_numpy(dtype=float))
        rho = pairwise_rho(s, port5)
        if rho is None:
            print(f"{k:<22}{sr:>8.3f}{'—':>13}   no overlap")
            continue
        bar = sr5 * rho
        ok = sr > bar
        print(f"{k:<22}{sr:>8.3f}{rho:>+13.4f}{bar:>8.3f}{sr - bar:>+9.3f}"
              f"   {'ADMIT' if ok else 'dilutes'}")

    print()
    print("=" * 90)
    print("AND WHAT ACTUALLY HAPPENS WHEN EACH IS ADDED")
    print("=" * 90)
    c5, d5, q5, s5 = growth_at_dd(base)
    print(f"{'book':<30}{'sleeves':>9}{'Sharpe':>9}{'CAGR':>9}{'delta':>9}")
    print("-" * 66)
    print(f"{'the 5 alone':<30}{5:>9}{s5:>9.3f}{c5 * 100:>8.1f}%{'':>9}")
    for k in sorted(cands, key=lambda k: -sharpe(series(*k.split(".")).to_numpy())):
        df = frame(FIVE + [k])
        c, _, _, s = growth_at_dd(df)
        print(f"{'  + ' + k:<30}{6:>9}{s:>9.3f}{c * 100:>8.1f}%"
              f"{(c - c5) * 100:>+8.1f}pp")
    df_all = frame(all12)
    c_all, _, _, s_all = growth_at_dd(df_all)
    print(f"{'all 12, edge-weighted':<30}{12:>9}{s_all:>9.3f}{c_all * 100:>8.1f}%"
          f"{(c_all - c5) * 100:>+8.1f}pp")

    print("""
  THE RULE IS NECESSARY, NOT SUFFICIENT, AND THIS TABLE IS WHERE THAT SHOWS

  USDJPY.london_am passes admission by +0.28 of Sharpe and then costs 11pp of
  CAGR. Nothing is wrong with the arithmetic; the two measures are asking
  different questions. Diagnosed:

      Sharpe    1.638 -> 1.639     mean 0.1205 -> 0.1148, sd 0.5836 -> 0.5559
      worst DD -11.2% -> -12.8%    so q at the matched drawdown falls 3.43% ->
                                   3.02%, and the CAGR falls with it

  Volatility went DOWN and the deepest drawdown went UP. Sharpe cannot see that,
  because it reads the first two moments and a drawdown is a property of the
  ORDER of returns. A sleeve can shrink the average bad day and still lengthen
  the worst losing streak.

  So marginal Sharpe is the SCREEN -- a sleeve that fails it cannot help, and
  three of these fail it decisively -- but passing it earns a path test, not a
  place in the book.

  AND THE PATH TEST ITSELF IS NOISY. Matching on the single worst drawdown in
  eight years keys the entire ranking off one sequence of days. The
  robustness check below re-runs it against risk measures that are not hostage
  to one episode; where those disagree, the difference was noise.""")

    print()
    print("=" * 90)
    print("ROBUSTNESS — the same additions ranked by three different risk matches")
    print("=" * 90)
    print(f"{'book':<28}{'worst DD':>12}{'top-5 DD':>12}{'matched vol':>13}"
          f"   agree?")
    print("-" * 76)

    def at_vol(df: pd.DataFrame, target_vol: float) -> float:
        """CAGR at a matched annualised volatility. Path-INDEPENDENT, so it
        cannot be moved by one unlucky sequence the way a drawdown match can."""
        w = edge_weights(df)
        port = pd.Series(df.to_numpy(dtype=float) @ w, index=df.index)
        yrs = (max(port.index) - min(port.index)).days / 365.25
        shift = 0.5 * float(port.mean())
        v = port.to_numpy(dtype=float) - shift
        q = target_vol / (v.std(ddof=1) * math.sqrt(TPY))
        return compound(port, q, yrs, shift=shift)[0]

    def at_top5(df: pd.DataFrame) -> float:
        """CAGR solved so the MEAN of the five deepest drawdowns hits target.

        Less hostage to one episode than the single worst, while still being a
        drawdown rather than a volatility.
        """
        w = edge_weights(df)
        port = pd.Series(df.to_numpy(dtype=float) @ w, index=df.index)
        yrs = (max(port.index) - min(port.index)).days / 365.25
        shift = 0.5 * float(port.mean())
        v = port.to_numpy(dtype=float) - shift

        def mean_top5(q: float) -> float:
            eq = np.cumprod(1.0 + q * v)
            if eq.min() <= 0:
                return 1.0
            dd = 1.0 - eq / np.maximum.accumulate(eq)
            # the five deepest LOCAL troughs, approximated by the 5 largest
            # values of the running drawdown separated by recoveries
            peaks = np.r_[True, np.maximum.accumulate(eq)[1:]
                          > np.maximum.accumulate(eq)[:-1]]
            seg, cur, out = [], 0.0, []
            for x, p in zip(dd, peaks):
                if p and cur > 0:
                    out.append(cur)
                    cur = 0.0
                cur = max(cur, x)
            out.append(cur)
            out.sort(reverse=True)
            return float(np.mean(out[:5])) if out else 0.0

        # THE SEARCH COMES FROM mt5desk.sizing, THE OBJECTIVE STAYS HERE. `mean_top5` is a
        # genuinely different statistic from a single worst drawdown, so this cannot call
        # `q_for_drawdown` -- but it does not need its own bisection either. `solve_size` bounds
        # the search at `ruin_q(v)`, the q at which one observed day wipes the account out, which
        # the hardcoded 0.20 ceiling here did not: that number never moved when the worst day did.
        q = solve_size(mean_top5, v, DD_TARGET * 0.6)
        return compound(port, q, yrs, shift=shift)[0]

    base_vol = float((pd.Series(base.to_numpy(dtype=float) @ w5).std(ddof=1))
                     * math.sqrt(TPY)) * 0.0343      # q* of the 5, from above
    ref = (c5, at_top5(base), at_vol(base, base_vol))
    print(f"{'the 5 alone':<28}{ref[0] * 100:>11.1f}%{ref[1] * 100:>11.1f}%"
          f"{ref[2] * 100:>12.1f}%")
    for k in sorted(cands, key=lambda k: -sharpe(series(*k.split(".")).to_numpy())):
        df = frame(FIVE + [k])
        got = (growth_at_dd(df)[0], at_top5(df), at_vol(df, base_vol))
        signs = {np.sign(g - r) for g, r in zip(got, ref)}
        mark = "yes" if len(signs) == 1 else "NO — noise"
        print(f"{'  + ' + k:<28}" + "".join(f"{g * 100:>11.1f}%" for g in got)
              + f"   {mark}")
    print("\n  Where the three columns disagree in SIGN, the addition is inside "
          "the noise and\n  the honest answer is that this sample cannot rank "
          "it.")

    # ------------------------------------------------------ the synthetic answer
    print()
    print("=" * 90)
    print("WHAT A NEW EDGE WOULD BUY — simulated sleeves at a chosen SR and rho")
    print("=" * 90)
    print(f"""
Added on top of the five, edge-weighted, solved to the same {DD_TARGET:.0%}
drawdown. Simulated sleeves always behave, so read these as an UPPER BOUND on
what a real one delivers, and as a price list for the question "what would a new
edge need to look like".

  the five alone: Sharpe {s5:.3f}, CAGR {c5 * 100:.1f}%
""")
    rng = np.random.default_rng(11)
    z = ((port5 - port5.mean()) / port5.std()).to_numpy(dtype=float)
    vol = float(base.std(axis=0).mean())
    n = len(z)
    print(f"{'':<10}" + "".join(f"{'rho=' + f'{r:+.2f}':>15}"
                                for r in (0.00, 0.15, 0.40, 0.70)))
    print("-" * 72)
    for sr_new in (0.30, 0.60, 1.00, 1.50):
        cells = []
        for rho_new in (0.00, 0.15, 0.40, 0.70):
            reps = []
            for seed in range(12):                  # average over draws
                r2 = np.random.default_rng(seed * 97 + 5)
                eps = r2.standard_normal(n)
                eps = (eps - eps.mean()) / eps.std()
                x = rho_new * z + math.sqrt(max(0.0, 1 - rho_new ** 2)) * eps
                x = x / x.std() * vol
                x = x + (sr_new / math.sqrt(TPY)) * vol - x.mean()
                df = base.copy()
                df["synthetic"] = x
                reps.append(growth_at_dd(df)[0])
            cells.append(f"{float(np.mean(reps)) * 100:>14.1f}%")
        print(f"SR {sr_new:<7.2f}" + "".join(cells))
    print(f"\n  every cell against the five alone at {c5 * 100:.1f}%. A sleeve "
          f"at rho=0 helps at\n  ANY positive Sharpe; at rho=0.70 it has to beat "
          f"{sr5 * 0.70:.2f} just to break even.")

    # --------------------------------------------------------- and the ceiling
    print()
    print("=" * 90)
    print("THE CEILING — adding MANY sleeves of the same quality")
    print("=" * 90)
    print(f"{'added':<10}" + "".join(f"{'rho=' + f'{r:.2f}':>14}"
                                     for r in (0.00, 0.15, 0.40)))
    print("-" * 52)
    for k_new in (1, 3, 5, 10):
        cells = []
        for rho_new in (0.00, 0.15, 0.40):
            reps = []
            for seed in range(6):
                r2 = np.random.default_rng(seed * 31 + k_new)
                df = base.copy()
                for j in range(k_new):
                    eps = r2.standard_normal(n)
                    eps = (eps - eps.mean()) / eps.std()
                    x = rho_new * z + math.sqrt(max(0.0, 1 - rho_new ** 2)) * eps
                    x = x / x.std() * vol
                    x = x + (0.60 / math.sqrt(TPY)) * vol - x.mean()
                    df[f"syn{j}"] = x
                reps.append(growth_at_dd(df)[0])
            cells.append(f"{float(np.mean(reps)) * 100:>13.1f}%")
        print(f"{k_new:<10}" + "".join(cells))
    print("\n  all added sleeves at SR 0.60, correlated to the book AND to each "
          "other at the\n  stated rho. k_eff = N/(1+(N-1)rho) saturates at 1/rho: "
          "at 0.15 that ceiling is\n  about 6.7 effective bets and at 0.40 it is "
          "2.5, which is why the rho=0.40\n  column stops paying long before the "
          "rho=0.00 one does.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
