"""Getting back to a 100%+ CAGR: which levers are real and what each one costs.

The headline was 147.8%. Honest accounting took it to 62.4% at a 35% drawdown.
Three things did that, and they are not the same kind of thing:

    THE GOLD SPREAD BUG, about -45pp. Gold was charged 3% of its spread in every
    backtest this desk has run. NOT RECOVERABLE. That money was never there.

    THE CARRY YEARS, about -50pp. 2022 and 2025 pay 353% and 429% against a
    40-125% median elsewhere. Recoverable only by betting the next few years
    look like the BoJ divergence and the gold melt-up. That is a regime bet, and
    it may well come in -- but it is not something the desk can engineer.

    THE HALF-EDGE HAIRCUT. The selection discount. NOT RECOVERABLE; it is the
    correction, not a cost.

So two thirds of what was lost was never real. What follows is the honest list
of what could actually put a 1 in front of the number again, priced rather than
asserted, worst option first so the good ones are not read as equivalent.

    MORE DRAWDOWN. Always available, buys growth at a linear-ish rate, and buys
    no edge whatsoever. It is the lever that feels like progress and is not.

    NEW FAMILIES. The book runs ONE of the desk's eight signal families, in five
    costumes. A different mechanism is the only cheap source of the low
    correlation the admission test demands. This is where the search should go
    and it is measured below.

    BETTER EXITS. The engine supports partial banking, breakeven stops and
    chandelier trails, and the armed book uses none of them. Raising the Sharpe
    of sleeves already held beats adding correlated ones.
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
from book_sizing import FIVE, compound, q_for_drawdown          # noqa: E402

RECOVER_VERSION = "recover-2026-08-18-a"

SPREAD_MULT = 2.0
TPY = 252
META = json.loads((BASE / "data" / "universe" / "universe.json").read_text("utf-8"))

#: Symbols the new families are searched across. The armed four plus the rest of
#: the universe, because a genuinely uncorrelated sleeve is more likely to be on
#: an instrument the book does not already hold.
SEARCH = [p.stem.replace("_H1", "")
          for p in sorted((BASE / "data" / "universe").glob("*_H1.parquet"))]

_h1: dict = {}


def h1(sym: str) -> pd.DataFrame:
    if sym not in _h1:
        _h1[sym] = families._h1(pd.read_parquet(
            BASE / "data" / "universe" / f"{sym}_H1.parquet"))
    return _h1[sym]


def daily(sym: str, sigs) -> pd.Series | None:
    if not sigs:
        return None
    tr = run_backtest(h1(sym), list(sigs),
                      Costs.from_symbol(META[sym], SPREAD_MULT)).trades
    if len(tr) < 100:
        return None
    return pd.Series([t.r_multiple for t in tr],
                     index=pd.Index([t.entry_time.date() for t in tr])
                     ).groupby(level=0).sum()


def sharpe(x) -> float:
    x = np.asarray(x, dtype=float)
    return 0.0 if x.std(ddof=1) == 0 else float(
        x.mean() / x.std(ddof=1) * math.sqrt(TPY))


def edge_weights(df: pd.DataFrame) -> np.ndarray:
    w = np.maximum(df.mean(axis=0).to_numpy(dtype=float), 0.0)
    return w / w.sum() if w.sum() > 0 else np.ones(len(w)) / len(w)


def book_series(cols: dict) -> pd.Series:
    days = sorted(set().union(*[set(v.index) for v in cols.values()]))
    df = pd.DataFrame({k: v.reindex(days).fillna(0.0) for k, v in cols.items()},
                      index=days)
    return pd.Series(df.to_numpy(dtype=float) @ edge_weights(df), index=days)


def growth(port: pd.Series, dd: float) -> tuple:
    yrs = (max(port.index) - min(port.index)).days / 365.25
    shift = 0.5 * float(port.mean())
    q, c, d = q_for_drawdown(port, yrs, dd, shift=shift)
    return c, d, q


BASE_SLEEVES = {k: daily(k.split(".")[0],
                         families.family_session_range_breakout(
                             h1(k.split(".")[0]), **WINDOWS[k.split(".")[1]]))
                for k in FIVE}
PORT5 = book_series(BASE_SLEEVES)


def main() -> int:
    print(f"RECOVERING 100%+  ({RECOVER_VERSION})")
    print(f"baseline: the five, edge-weighted, {SPREAD_MULT:.0f}x median "
          f"spread, half-edge\n")

    # ---------------------------------------------------- lever 1: drawdown
    print("=" * 88)
    print("LEVER 1 — MORE DRAWDOWN. Always available. Buys growth, buys no edge.")
    print("=" * 88)
    print(f"{'drawdown tolerated':<24}{'q/leg':>9}{'total heat':>12}{'CAGR':>9}"
          f"{'EUR300 -> ':>12}")
    print("-" * 66)
    hit = None
    for dd in (0.25, 0.35, 0.45, 0.55, 0.65, 0.75):
        c, d, q = growth(PORT5, dd)
        if c >= 1.0 and hit is None:
            hit = dd
        print(f"{dd:<24.0%}{q:>9.3%}{q * 5:>12.2%}{c * 100:>8.1f}%"
              f"{300 * (1 + c):>11,.0f}")
    print(f"\n  100% arrives at roughly a {hit:.0%} drawdown."
          if hit else "\n  100% is not reachable on this book by drawdown alone.")
    print("  A 65% drawdown means EUR2,000 becomes EUR700 on the way to the "
          "good years,\n  and the worst drawdown in a backtest is an "
          "UNDERESTIMATE of the worst to come.\n  This lever is real, it is "
          "available today, and it is the least honest way\n  to reach the "
          "number.")

    # ------------------------------------------------- lever 2: new families
    print()
    print("=" * 88)
    print("LEVER 2 — NEW FAMILIES. The book runs 1 of 8, in five costumes.")
    print("=" * 88)
    print("Admission bar: SR_new > SR_book x rho. Anything with rho near zero "
          "helps at any\npositive Sharpe, so a DIFFERENT MECHANISM is worth "
          "more than a better version of\nthe one already held.\n")
    sr5 = sharpe(PORT5.to_numpy(dtype=float))
    print(f"book Sharpe (raw, in-sample) {sr5:.3f}\n")

    cand: dict = {}
    specs = [
        ("asia_momentum", lambda d: families.family_asia_momentum(d)),
        ("dow_effect", lambda d: families.family_dow_effect(d)),
        ("momentum_volgate", lambda d: families.family_momentum_volgate(d)),
        ("monday_gap", lambda d: families.family_monday_gap(d)),
        ("london_close_mom", lambda d: families.family_london_close_momentum(d)),
        ("level_breakout_pdh", lambda d: families.family_level_breakout(d, level="pdh")),
        ("level_breakout_pdl", lambda d: families.family_level_breakout(d, level="pdl")),
        ("failed_breakout_pdh", lambda d: families.family_failed_breakout(d, level="pdh")),
        ("failed_breakout_pdl", lambda d: families.family_failed_breakout(d, level="pdl")),
    ]
    for sym in SEARCH:
        for name, fn in specs:
            try:
                s = daily(sym, fn(h1(sym)))
            except Exception:                                   # noqa: BLE001
                continue
            if s is None:
                continue
            com = sorted(set(s.index) & set(PORT5.index))
            if len(com) < 200:
                continue
            x, y = s.reindex(com).to_numpy(), PORT5.reindex(com).to_numpy()
            if x.std() == 0 or y.std() == 0:
                continue
            rho = float(np.corrcoef(x, y)[0, 1])
            sr = sharpe(s.to_numpy(dtype=float))
            cand[f"{sym}.{name}"] = (sr, rho, sr - sr5 * rho, s)

    passing = {k: v for k, v in cand.items() if v[2] > 0 and v[0] > 0}
    print(f"{len(cand)} candidate sleeves tested across {len(SEARCH)} symbols "
          f"x {len(specs)} families")
    print(f"{len(passing)} clear the admission bar\n")

    # cache for the null comparison, so re-runs do not repeat 194 backtests
    (BASE / "data" / "recover_candidates.json").write_text(json.dumps(
        {k: [v[0], v[1], v[2]] for k, v in cand.items()}, indent=1), "utf-8")

    # ------------------------------------------------- IS 6-OF-194 EVEN A SIGNAL
    #
    # THE COUNT ONLY MEANS SOMETHING AGAINST WHAT CHANCE WOULD PRODUCE. The
    # standard error of an annualised Sharpe over T years is about 1/sqrt(T),
    # which on this 8.4-year sample is 0.35. So a book of sleeves with NO edge
    # at all still throws up a healthy number above any modest bar, and a raw
    # count of survivors is not evidence until it is compared to that.
    yrs_span = (max(PORT5.index) - min(PORT5.index)).days / 365.25
    se_sr = 1.0 / math.sqrt(yrs_span)
    srs = np.array([v[0] for v in cand.values()], dtype=float)
    bars = np.array([sr5 * v[1] for v in cand.values()], dtype=float)
    # P(noise sleeve clears its own bar), averaged over the observed bars
    from math import erf
    p_each = np.mean([0.5 * (1 - erf(b / (se_sr * math.sqrt(2)))) for b in bars])
    exp_n = p_each * len(cand)
    print(f"  NULL CHECK — Sharpe standard error on {yrs_span:.1f} years is "
          f"{se_sr:.3f}.")
    print(f"  A sleeve with NO edge clears its own admission bar {p_each:.1%} of "
          f"the time,")
    print(f"  so {len(cand)} zero-edge candidates would produce about "
          f"{exp_n:.0f} passers by chance.")
    print(f"  Observed: {len(passing)}.  "
          + ("FEWER THAN CHANCE — this search found nothing; the six below are "
             "what\n  a null looks like, and treating them as edges would be "
             "reading noise."
             if len(passing) <= exp_n else
             f"{len(passing) / max(exp_n, 1e-9):.1f}x chance — worth the "
             f"deflated-Sharpe run,\n  not yet worth trading."))
    print(f"  median candidate SR {np.median(srs):+.3f}, mean {srs.mean():+.3f} "
          f"(a real family pool should sit above zero)\n")
    print(f"{'candidate':<34}{'SR':>8}{'rho':>9}{'margin':>9}")
    print("-" * 60)
    for k, (sr, rho, m, _) in sorted(passing.items(), key=lambda kv: -kv[1][2])[:18]:
        print(f"{k:<34}{sr:>8.3f}{rho:>+9.4f}{m:>+9.3f}")

    if passing:
        print()
        print("=" * 88)
        print("WHAT ADDING THE BEST OF THEM ACTUALLY DOES")
        print("=" * 88)
        print(f"{'book':<44}{'N':>4}{'Sharpe':>9}{'CAGR@35%':>11}{'CAGR@45%':>11}")
        print("-" * 79)
        c35, _, _ = growth(PORT5, 0.35)
        c45, _, _ = growth(PORT5, 0.45)
        print(f"{'the 5 alone':<44}{5:>4}{sr5:>9.3f}{c35 * 100:>10.1f}%"
              f"{c45 * 100:>10.1f}%")
        ranked = sorted(passing.items(), key=lambda kv: -kv[1][2])
        for take in (1, 3, 5, 8, 12):
            cols = dict(BASE_SLEEVES)
            for k, (_, _, _, s) in ranked[:take]:
                cols[k] = s
            p = book_series(cols)
            a, _, _ = growth(p, 0.35)
            b, _, _ = growth(p, 0.45)
            print(f"{'  + top ' + str(take) + ' new-family sleeves':<44}"
                  f"{5 + take:>4}{sharpe(p.to_numpy(dtype=float)):>9.3f}"
                  f"{a * 100:>10.1f}%{b * 100:>10.1f}%")
        print("\n  IN-SAMPLE AND UNDEFLATED. These were picked as the best of "
              f"{len(cand)} tested,\n  and picking the best of {len(cand)} "
              f"guarantees a good-looking number even from\n  noise. The "
              f"deflated-Sharpe bar at N={len(cand)} is what decides whether "
              f"any of this\n  survives, and gauntlet_unconditioned is where "
              f"that gets run. Treat this table\n  as a SEARCH DIRECTION, not "
              f"a result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
