"""A daily loss limit, measured at trade level, at a FIXED 100% CAGR.

THE APPROXIMATION THAT HAD TO BE THROWN AWAY

The obvious way to test a daily loss limit is to cap each day's aggregated R.
It is also wrong, and one-sided in the flattering direction: capping the day's
FINAL number can only ever remove a loss, because by the time the total is known
the day is over. A live limit fires the instant cumulative R touches the level,
which also kills every day that dipped to the limit and then RECOVERED. The
aggregate model cannot see those days at all, so it books all of the benefit and
none of the cost.

Counted at trade level on this book, a -2R limit halts 505 days of 2,235. Of
those halts 235 were right -- the day carried on down -- and 136 were WRONG: the
day recovered and the stop paid for it. A test that cannot see those 136 is not
measuring a daily loss limit, it is measuring hindsight.

So this walks each day's trades in entry-time order across the whole book, halts
at the limit, and takes what was on the board at that instant.

WHY FIXED CAGR RATHER THAN FIXED DRAWDOWN

Because the question is what the drawdown COSTS, not what the return is. Every
arm is sized until it compounds at the same 100% a year; the number that varies
is the drawdown each one needed to get there, and lower is unambiguously better
with the upside pinned by construction.

The size is found by SCANNING, not bisecting. CAGR is not monotonic in bet size
-- it peaks at Kelly and falls after -- so a bisection can land past the peak,
read "not enough growth", and respond by betting more. That mistake produced two
entire runs of NaN before it was caught.
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

from cut_drawdown import CORE, TARGET_CAGR, sleeve_trades        # noqa: E402
from mt5desk.sizing import ruin_q                                # noqa: E402

OUT = _DESK / "reports" / "daily_stop.json"
LIMITS = (None, 5.0, 3.0, 2.0, 1.5, 1.0)


def book_trades() -> pd.DataFrame:
    rows = []
    for sym, win in CORE:
        for t in sleeve_trades(sym, win):
            rows.append((t.entry_time, t.entry_time.date(), t.r_multiple))
    return pd.DataFrame(rows, columns=["ts", "day", "r"]).sort_values("ts")


def live_stop(df: pd.DataFrame, limit: float | None):
    """Daily R under a live limit, plus how often it was right or wrong."""
    out, halts, right, wrong = {}, 0, 0, 0
    for day, g in df.groupby("day", sort=True):
        cum = np.cumsum(g["r"].to_numpy(float))
        final = float(cum[-1])
        if limit is None:
            out[day] = final
            continue
        hit = np.where(cum <= -limit)[0]
        if not len(hit):
            out[day] = final
            continue
        halts += 1
        realised = float(cum[hit[0]])
        out[day] = realised
        if final < realised - 1e-12:
            right += 1
        elif final > realised + 1e-12:
            wrong += 1
    return pd.Series(out).sort_index(), halts, right, wrong


def walk(x, q):
    eq, peak, worst = 1.0, 1.0, 0.0
    for v in x:
        eq *= 1.0 + q * v
        if not np.isfinite(eq) or eq <= 0:
            return None, 1.0
        peak = max(peak, eq)
        worst = max(worst, 1.0 - eq / peak)
    return eq, worst


def dd_at_target(s: pd.Series):
    x = s.to_numpy(float) - 0.5 * float(s.mean())              # half-edge
    yrs = max((max(s.index) - min(s.index)).days / 365.25, 0.5)
    grid = np.geomspace(1e-5, min(1.0, ruin_q(x)) * 0.999, 4000)
    best, peak_g = None, -1.0
    for q in grid:
        eq, dd = walk(x, q)
        if eq is None:
            break
        g = eq ** (1 / yrs) - 1.0
        peak_g = max(peak_g, g)
        if g >= TARGET_CAGR and best is None:
            best = (float(q), float(dd), float(g))
    return best, peak_g


def main() -> int:
    df = book_trades()
    print(f"DAILY LOSS LIMIT — {len(df)} trades, "
          f"{df['day'].nunique()} trading days, every arm solved to "
          f"{100 * TARGET_CAGR:.0f}% CAGR, half-edge\n")
    print(f"{'limit':>8}{'mean R/day':>12}{'halts':>8}{'right':>7}{'wrong':>7}"
          f"{'DD @100%':>10}{'q':>10}{'max CAGR':>11}")
    rows = []
    for lim in LIMITS:
        s, halts, right, wrong = live_stop(df, lim)
        best, peak_g = dd_at_target(s)
        lbl = "none" if lim is None else f"-{lim:g}R"
        if best is None:
            print(f"{lbl:>8}{s.mean():>12.4f}{halts:>8}{right:>7}{wrong:>7}"
                  f"{'unreachable':>10}{'-':>10}{100 * peak_g:>10.1f}%")
            rows.append({"limit": lim, "mean_r": round(float(s.mean()), 4),
                         "halts": halts, "right": right, "wrong": wrong,
                         "dd": None, "max_cagr": round(peak_g, 4)})
            continue
        q, dd, g = best
        print(f"{lbl:>8}{s.mean():>12.4f}{halts:>8}{right:>7}{wrong:>7}"
              f"{100 * dd:>9.1f}%{q:>10.5f}{100 * peak_g:>10.1f}%")
        rows.append({"limit": lim, "mean_r": round(float(s.mean()), 4),
                     "halts": halts, "right": right, "wrong": wrong,
                     "dd": round(dd, 4), "q": round(q, 6),
                     "cagr": round(g, 4), "max_cagr": round(peak_g, 4)})

    base = rows[0]
    ok = [r for r in rows[1:] if r["dd"] is not None]
    if ok:
        b = min(ok, key=lambda r: r["dd"])
        print(f"\nno limit: {100 * base['dd']:.1f}% drawdown for 100% CAGR.")
        print(f"best limit {b['limit']:g}R: {100 * b['dd']:.1f}% — "
              f"{100 * (base['dd'] - b['dd']):.1f} points less, and mean R/day "
              f"RISES {base['mean_r']:.4f} -> {b['mean_r']:.4f}.")
        print(f"\nThat the return goes UP as well as the drawdown down is the "
              f"part to be suspicious of, so note what pays for it: {b['right']}"
              f" halts were right and {b['wrong']} were wrong, and the wrong "
              f"ones ARE charged here. Tightening the limit further keeps "
              f"helping in-sample, which is exactly what an over-fitted "
              f"parameter does; {len(LIMITS) - 1} limits were tried.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"target_cagr": TARGET_CAGR, "arms": rows},
                              indent=1), "utf-8")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
