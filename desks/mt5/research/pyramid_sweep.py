"""Does pyramiding raise E[log] on the sleeves we actually hold?

The engine gained winner-pyramiding today. Whether it is worth USING is a
separate question from whether it is correctly implemented, and it is not
answerable from theory: adding into a winner lengthens the right tail, which
log-utility likes, and raises variance, which log-utility dislikes. Which term
wins is arithmetic on the actual return series, so this measures it.

WHY THE ANSWER IS NOT OBVIOUS IN EITHER DIRECTION

E[log(1+qR)] is concave. It pays for skew and charges for dispersion, and a
pyramid delivers both at once. On a mean-reverting sleeve the adds fill just
before the reversion and cost money; on a trending one they fill early in a run
that keeps going. Our five sleeves are session breakouts, which is the case
where it could plausibly go either way -- a breakout that works tends to keep
working, and one that fails does so immediately.

THE COMPARISON IS AT MATCHED DRAWDOWN, NOT MATCHED SIZE

Comparing a pyramided cell to a flat one at the same q hands the pyramid more
total heat and then congratulates it for the extra return. Every arm below is
solved to the same drawdown budget, so the difference that survives is edge
rather than leverage. This is the same trap the 5-vs-12-sleeve comparison fell
into and it is the reason that comparison was wrong for a week.

EVERY ADD PAYS ITS OWN ROUND TRIP, and add_ratchets_stop is ON. The unratcheted
variant exists in the engine to be measured, not traded, and is not swept here.
"""
from __future__ import annotations

import itertools
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import families                                   # noqa: E402
from mt5desk.engine import Costs, run_backtest                 # noqa: E402
from mt5desk.sizing import q_for_drawdown  # noqa: E402
from run_hunt11 import WINDOWS                                 # noqa: E402

UNI = _DESK / "data" / "universe"
OUT = _DESK / "reports" / "pyramid_sweep.json"
META = json.loads((UNI / "universe.json").read_text("utf-8"))
SPREAD_MULT = 2.0
DD_TARGET = 0.35
TPY = 252

#: the book the re-run actually produced
BOOK = [("XAUUSD", "asia"), ("USDJPY", "asia"), ("CADJPY", "asia"),
        ("EURJPY", "asia"), ("XAUUSD", "london_am")]

GRID = list(itertools.product((0.5, 1.0, 2.0), (1, 2, 3), (0.25, 0.5, 1.0)))

_h1: dict = {}


def h1(sym: str) -> pd.DataFrame:
    if sym not in _h1:
        _h1[sym] = families._h1(pd.read_parquet(UNI / f"{sym}_H1.parquet"))
    return _h1[sym]


def daily(trades) -> pd.Series:
    if not trades:
        return pd.Series(dtype=float)
    return pd.Series([t.r_multiple for t in trades],
                     index=pd.Index([t.entry_time.date() for t in trades])
                     ).groupby(level=0).sum()


# THE LOCAL q_for_drawdown THAT LIVED HERE SIZED **UP** PAST RUIN, and the half-edge docstring
# on it made it read as the careful path. At a large enough q some day has `1 + q*x <= 0` -- the
# account is GONE, not drawn down -- cumprod goes negative, the drawdown expression yields NaN,
# and `NaN > target` is False, so the search concluded the budget held and raised q. Its `hi = 0.5`
# bound was unrelated to the data: it did not fall when the worst observed day got worse.
#
# `mt5desk/sizing.py` is the single implementation (2026-08-19): ruin returns a drawdown of 1.0 so
# it compares as a violation, and the search is bounded at `1/|min(x)|`, the q at which one
# observed day can wipe the account out. The half-edge shift stays at the CALL SITE, where it is
# visible, rather than inside a helper whose name says nothing about it.


def growth(r: pd.Series) -> tuple[float, float]:
    """(CAGR, q) at the matched drawdown, half-edge."""
    if len(r) < 100:
        return 0.0, 0.0
    shift = 0.5 * float(r.mean())
    q = q_for_drawdown(r.to_numpy(float) - shift, DD_TARGET)
    x = r.to_numpy(float) - shift
    yrs = max((max(r.index) - min(r.index)).days / 365.25, 0.5)
    eq = float(np.prod(1.0 + q * x))
    return (eq ** (1 / yrs) - 1.0 if eq > 0 else -1.0), q


def main() -> int:
    rows = []
    print(f"PYRAMID SWEEP  matched drawdown {100 * DD_TARGET:.0f}%, half-edge, "
          f"costs {SPREAD_MULT:.0f}x spread\n")
    print(f"{'sleeve':<20}{'arm':<22}{'n':>6}{'E[R]':>9}{'SR':>7}"
          f"{'q':>8}{'CAGR':>9}{'delta':>9}")
    for sym, win in BOOK:
        df, costs = h1(sym), Costs.from_symbol(META[sym], SPREAD_MULT)
        base_sigs = list(families.family_session_range_breakout(
            df, **WINDOWS[win]))
        flat = daily(run_backtest(df, base_sigs, costs).trades)
        g0, q0 = growth(flat)
        sr0 = (float(flat.mean() / flat.std(ddof=1) * math.sqrt(TPY))
               if len(flat) > 1 and flat.std(ddof=1) else 0.0)
        print(f"{sym + '.' + win:<20}{'flat (baseline)':<22}{len(flat):>6}"
              f"{flat.mean():>9.4f}{sr0:>7.2f}{q0:>8.4f}{100 * g0:>8.1f}%"
              f"{'--':>9}")
        best = None
        for every, mx, frac in GRID:
            sigs = []
            for s in base_sigs:
                s2 = type(s)(**{**s.__dict__})
                s2.add_every_r, s2.add_max, s2.add_frac = every, mx, frac
                s2.add_ratchets_stop = True
                sigs.append(s2)
            ser = daily(run_backtest(df, sigs, costs).trades)
            g, q = growth(ser)
            sr = (float(ser.mean() / ser.std(ddof=1) * math.sqrt(TPY))
                  if len(ser) > 1 and ser.std(ddof=1) else 0.0)
            rec = {"sleeve": f"{sym}.{win}", "add_every_r": every,
                   "add_max": mx, "add_frac": frac, "n_days": len(ser),
                   "expectancy_r": round(float(ser.mean()), 5),
                   "sharpe": round(sr, 3), "q": round(q, 5),
                   "cagr": round(g, 5), "delta_cagr": round(g - g0, 5)}
            rows.append(rec)
            if best is None or g > best["cagr"]:
                best = rec
        b = best
        print(f"{'':<20}{'best: r=%.1f x%d f=%.2f' % (b['add_every_r'], b['add_max'], b['add_frac']):<22}"
              f"{b['n_days']:>6}{b['expectancy_r']:>9.4f}{b['sharpe']:>7.2f}"
              f"{b['q']:>8.4f}{100 * b['cagr']:>8.1f}%"
              f"{100 * b['delta_cagr']:>+8.1f}%")
        print()

    helped = [r for r in rows if r["delta_cagr"] > 0]
    print(f"{len(helped)} of {len(rows)} pyramid configurations beat their own "
          f"flat baseline at matched drawdown.")
    print(f"(chance alone, if pyramiding did nothing, gives about "
          f"{len(rows) // 2}.)")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"dd_target": DD_TARGET, "grid": len(GRID),
                               "rows": rows}, indent=1), "utf-8")
    print(f"\nwritten: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
