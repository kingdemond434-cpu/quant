"""What the book compounds at now, and what each change was actually worth.

Everything here is reported at MATCHED DRAWDOWN. A looser exit wins more R and
carries more heat; compared at equal size it is credited for both and the second
one is not an edge, it is leverage. So every arm is solved by bisection to the
same drawdown budget before its CAGR is read, and the sizes it needed are
printed so the reader can see which arm was quietly betting more.

HALF-EDGE THROUGHOUT. Half the sample mean is subtracted from every return
before compounding. That is a location shift, not a rescale: it assumes half of
everything measured here is selection and survives only the other half. Numbers
without it are the numbers a backtest wants to show you.

THREE ARMS, AND THE THIRD IS THE ONLY NEW ONE

  flat        the sleeve as it was hunted -- fixed target, fixed stop
  trail       best static chandelier, the previous best exit
  tighten     wide, then tightening once the move stops printing new extremes

The engine underneath is the FIXED one: the stop is now evaluated before the
bar's own extreme feeds the trail. Every stored exit_sweep number predates that
and is not comparable to anything printed here, which is why this recomputes the
flat and trail arms rather than quoting them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import families                                    # noqa: E402
from mt5desk.engine import Costs, run_backtest                  # noqa: E402
from mt5desk.sizing import q_for_drawdown                       # noqa: E402
from run_hunt11 import WINDOWS                                  # noqa: E402

UNI = _DESK / "data" / "universe"
OUT = _DESK / "reports" / "growth_now.json"
META = json.loads((UNI / "universe.json").read_text("utf-8"))
SPREAD_MULT, TPY = 2.0, 252
DD_TARGETS = (0.20, 0.35, 0.50)

BOOK = [("XAUUSD", "asia"), ("USDJPY", "asia"), ("CADJPY", "asia"),
        ("EURJPY", "asia"), ("XAUUSD", "london_am")]

_h1: dict = {}


def h1(sym):
    if sym not in _h1:
        _h1[sym] = families._h1(pd.read_parquet(UNI / f"{sym}_H1.parquet"))
    return _h1[sym]


def daily(trades):
    if not trades:
        return pd.Series(dtype=float)
    return pd.Series([t.r_multiple for t in trades],
                     index=pd.Index([t.entry_time.date() for t in trades])
                     ).groupby(level=0).sum()


def growth(r, target):
    """CAGR at the stated drawdown budget, half-edge. Returns (cagr, q, n)."""
    if len(r) < 100:
        return float("nan"), 0.0, len(r)
    shift = 0.5 * float(r.mean())
    q = q_for_drawdown(r.to_numpy(float) - shift, target)
    x = r.to_numpy(float) - shift
    yrs = max((max(r.index) - min(r.index)).days / 365.25, 0.5)
    eq = float(np.prod(1.0 + q * x))
    return ((eq ** (1 / yrs) - 1.0) if eq > 0 else -1.0), q, len(r)


def variant(base, **kw):
    out = []
    for s in base:
        s2 = type(s)(**{**s.__dict__})
        for k, v in kw.items():
            setattr(s2, k, v)
        out.append(s2)
    return out


ARMS = {
    "flat":    dict(),
    "trail":   dict(bank_frac=0.5, bank_protect_k=0.5, runner_trail_k=2.0),
    "tighten": dict(bank_frac=0.0, runner_trail_k=4.0, trail_tighten_k=1.0,
                    trail_stall_bars=3),
}


def main() -> int:
    print(f"BOOK OF {len(BOOK)} SLEEVES — half-edge, {SPREAD_MULT:.0f}x spread, "
          f"matched drawdown, FIXED engine\n")
    series: dict[str, dict] = {a: {} for a in ARMS}
    for sym, win in BOOK:
        df, costs = h1(sym), Costs.from_symbol(META[sym], SPREAD_MULT)
        base = list(families.family_session_range_breakout(df, **WINDOWS[win]))
        for arm, kw in ARMS.items():
            sigs = variant(base, **kw) if kw else base
            series[arm][f"{sym}.{win}"] = daily(run_backtest(df, sigs, costs).trades)

    print(f"{'sleeve':<20}" + "".join(f"{a:>26}" for a in ARMS))
    print(f"{'':<20}" + "".join(f"{'CAGR@35%':>13}{'trades':>13}" for _ in ARMS))
    for name in series["flat"]:
        line = f"{name:<20}"
        for arm in ARMS:
            g, _q, n = growth(series[arm][name], 0.35)
            line += f"{100 * g:>12.1f}%{n:>13}"
        print(line)

    # --- the portfolio ----------------------------------------------------
    print(f"\n{'PORTFOLIO (equal weight, daily R summed)':<44}")
    print(f"{'drawdown budget':<20}" + "".join(f"{a:>14}" for a in ARMS))
    rows = {}
    for tgt in DD_TARGETS:
        line = f"{100 * tgt:>17.0f}%  "
        rows[tgt] = {}
        for arm in ARMS:
            comb = None
            for s in series[arm].values():
                comb = s if comb is None else comb.add(s, fill_value=0.0)
            g, q, n = growth(comb, tgt)
            rows[tgt][arm] = {"cagr": round(g, 5), "q": round(q, 5), "days": n}
            line += f"{100 * g:>13.1f}%"
        print(line)

    print("\nSIZE THE ARMS NEEDED TO HIT 35% (q per unit R) — a bigger q is a "
          "bigger bet,\nnot a better edge, and matching drawdown is what "
          "stops that being confused:")
    for arm in ARMS:
        print(f"  {arm:<10} q = {rows[0.35][arm]['q']:.4f}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"book": [f"{s}.{w}" for s, w in BOOK],
                               "arms": list(ARMS), "portfolio": {
                                   str(k): v for k, v in rows.items()}},
                              indent=1), "utf-8")
    print(f"\nwritten: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
