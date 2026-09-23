"""Hold CAGR at 100% and ask what each variant costs in DRAWDOWN.

Every previous study fixed the drawdown and read the return. That answers "how
much can I make inside this budget" and it is the wrong question once the budget
itself is what you want to shrink. So this inverts: solve the bet size until
each variant compounds at the SAME 100% a year, then report the drawdown it took
to get there. Lower is strictly better, with the upside held constant by
construction rather than by argument.

WHY THE SIZE SOLVER HAS TO SIMULATE THE PATH

Two of the three levers change the return series as a function of the equity
curve, so they cannot be evaluated by scaling a fixed vector. A drawdown
governor sizes from the equity peak; a daily loss cap truncates the day it
happens on. Both need a real path walk, and both are strictly causal -- the size
used on day t depends only on equity through t-1.

THE THREE LEVERS, AND WHY THESE THREE

  DRAWDOWN GOVERNOR   cut size while under water, restore on recovery. This is
                      the only lever that attacks drawdown DIRECTLY rather than
                      as a side effect. It obviously reduces return too; the
                      question is purely whether it reduces drawdown faster.

  DAILY LOSS CAP      truncate the worst days. Drawdowns are built out of tails
                      and clusters, and a cap attacks the tail half. It also
                      throws away real winners' days, so it is not free.

  MACRO BLACKOUT      skip trades whose life spans a scheduled US release. This
                      is the one with a mechanism rather than a statistic behind
                      it: fading a data print is not fading liquidity, it is
                      taking the other side of information. Only NFP and initial
                      claims are testable across the whole sample -- they follow
                      rules -- because calendar_us.FIXED covers 2026 alone, so
                      FOMC/CPI/PPI cannot be backtested here and are NOT quietly
                      dropped from the claim.
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import families                                    # noqa: E402
from mt5desk.calendar_us import us_eastern_offset               # noqa: E402
from mt5desk.engine import Costs, run_backtest                  # noqa: E402
from run_hunt11 import WINDOWS                                  # noqa: E402

UNI = _DESK / "data" / "universe"
OUT = _DESK / "reports" / "cut_drawdown.json"
META = json.loads((UNI / "universe.json").read_text("utf-8"))
SPREAD_MULT = 2.0
TARGET_CAGR = 1.00

CORE = [("XAUUSD", "asia"), ("USDJPY", "asia"), ("CADJPY", "asia"),
        ("EURJPY", "asia"), ("XAUUSD", "london_am")]
EXIT = dict(bank_frac=0.0, runner_trail_k=4.0, trail_tighten_k=1.0,
            trail_stall_bars=3)

_h1: dict = {}


def h1(sym):
    if sym not in _h1:
        _h1[sym] = families._h1(pd.read_parquet(UNI / f"{sym}_H1.parquet"))
    return _h1[sym]


def rule_releases(y0: int, y1: int) -> set[date]:
    """Dates carrying a RULE-DERIVED US release: NFP and initial claims.

    Deliberately not calendar_us.releases(), which refuses outside 2026 -- and
    is right to. The rule-derived subset is exact for every year, so it is what
    can honestly be tested over an eight-year sample; the table-driven events
    are absent and the conclusion is scoped to say so.
    """
    out: set[date] = set()
    for y in range(y0, y1 + 1):
        for m in range(1, 13):                      # NFP: first Friday
            d = date(y, m, 1)
            out.add(d + timedelta(days=(4 - d.weekday()) % 7))
        d = date(y, 1, 1)                            # claims: every Thursday
        d += timedelta(days=(3 - d.weekday()) % 7)
        while d.year == y:
            out.add(d)
            d += timedelta(days=7)
    return out


def sleeve_trades(sym, win):
    df, costs = h1(sym), Costs.from_symbol(META[sym], SPREAD_MULT)
    base = list(families.family_session_range_breakout(df, **WINDOWS[win]))
    sigs = []
    for s in base:
        s2 = type(s)(**{**s.__dict__})
        for k, v in EXIT.items():
            setattr(s2, k, v)
        sigs.append(s2)
    return run_backtest(df, sigs, costs).trades


def to_daily(trades, skip_dates=None):
    rows = [(t.entry_time.date(), t.r_multiple) for t in trades
            if skip_dates is None or t.entry_time.date() not in skip_dates]
    if not rows:
        return pd.Series(dtype=float)
    return pd.Series([r for _, r in rows],
                     index=pd.Index([d for d, _ in rows])
                     ).groupby(level=0).sum()


def walk(x, q, gov_floor=None, gov_at=None, cap=None):
    """Equity path. Size on day t uses equity through t-1 only."""
    eq, peak, worst = 1.0, 1.0, 0.0
    for r in x:
        if cap is not None:
            r = max(r, -cap)
        size = q
        if gov_at is not None:
            dd = 1.0 - eq / peak
            if dd > gov_at:
                size = q * gov_floor
        eq *= 1.0 + size * r
        if not np.isfinite(eq) or eq <= 0:
            return None, 1.0
        peak = max(peak, eq)
        worst = max(worst, 1.0 - eq / peak)
    return eq, worst


def q_for_cagr(x, yrs, target, **kw):
    """Smallest q reaching `target` CAGR, plus the best CAGR available at all.

    BISECTION IS THE WRONG TOOL AND THAT COST TWO RUNS. CAGR is NOT monotonic in
    bet size: it rises to the Kelly point and falls after it, because volatility
    drag eventually outruns the extra edge. A bisection probing the midpoint can
    land on the far side of that peak, read "growth below target", conclude it
    must bet MORE, and march away from the answer it was looking for. Every arm
    pinned at its upper bound with a NaN CAGR.

    (The first version had a second, separate defect on the same lines: `walk`
    returned None on a wiped-out account, that became g = -1.0, and -1.0 < target
    also sent q upward. I had fixed exactly that in mt5desk.sizing an hour
    earlier and then rewrote it here. The failure shape is always the same -- an
    error branch that compares as "not enough yet".)

    A scan over the whole valid range makes no monotonicity assumption, stops at
    the first ruinous size because nothing beyond it is meaningful, and takes the
    SMALLEST q that clears the target -- which is the one with the least
    drawdown, and therefore the only one that answers the question being asked.
    """
    from mt5desk.sizing import ruin_q
    grid = np.geomspace(1e-5, min(1.0, ruin_q(x)) * 0.999, 4000)
    best_q, best_g = None, -1.0
    for q in grid:
        eq, _dd = walk(x, q, **kw)
        if eq is None or not np.isfinite(eq) or eq <= 0:
            break                        # ruin: nothing above this is valid
        g = eq ** (1 / yrs) - 1.0
        best_g = max(best_g, g)
        if g >= target and best_q is None:
            best_q = float(q)            # SMALLEST q reaching target = least DD
    return best_q, best_g


def evaluate(series, label, **kw):
    r = series.dropna().sort_index()
    x = r.to_numpy(float) - 0.5 * float(r.mean())          # half-edge
    yrs = max((max(r.index) - min(r.index)).days / 365.25, 0.5)
    q, best_g = q_for_cagr(x, yrs, TARGET_CAGR, **kw)
    if q is None:
        # Cannot reach the target at ANY size. Saying so beats reporting the
        # closest miss as though the arm had been solved.
        return {"label": label, "cagr": None, "max_dd": None, "q": None,
                "best_cagr": round(best_g, 4), "days": len(r)}
    eq, dd = walk(x, q, **kw)
    g = eq ** (1 / yrs) - 1.0
    return {"label": label, "cagr": round(g, 4), "max_dd": round(dd, 4),
            "q": round(q, 6), "best_cagr": round(best_g, 4), "days": len(r)}


def main() -> int:
    print(f"CUT THE DRAWDOWN — every arm solved to the SAME "
          f"{100 * TARGET_CAGR:.0f}% CAGR, half-edge.\n"
          f"Lower drawdown is strictly better; the upside is held fixed.\n")

    trades = {f"{s}.{w}": sleeve_trades(s, w) for s, w in CORE}
    base = None
    for t in trades.values():
        s = to_daily(t)
        base = s if base is None else base.add(s, fill_value=0.0)

    y0, y1 = min(base.index).year, max(base.index).year
    rel = rule_releases(y0, y1)
    no_rel = None
    for t in trades.values():
        s = to_daily(t, skip_dates=rel)
        no_rel = s if no_rel is None else no_rel.add(s, fill_value=0.0)
    dropped = len(base) - len(no_rel.reindex(base.index).dropna())

    rows = [evaluate(base, "0. baseline (tighten exit)")]
    for at, floor in ((0.10, 0.5), (0.15, 0.5), (0.20, 0.5), (0.15, 0.25)):
        rows.append(evaluate(
            base, f"1. governor: size x{floor} once {100 * at:.0f}% under water",
            gov_at=at, gov_floor=floor))
    for cap in (2.0, 3.0, 5.0):
        rows.append(evaluate(base, f"2. daily loss cap at -{cap:.0f}R", cap=cap))
    rows.append(evaluate(no_rel, "3. skip NFP + claims days"))
    rows.append(evaluate(no_rel, "4. skip releases + governor 15%/x0.5",
                         gov_at=0.15, gov_floor=0.5))
    rows.append(evaluate(no_rel, "5. skip releases + cap -3R + governor",
                         gov_at=0.15, gov_floor=0.5, cap=3.0))

    ok = [r for r in rows if r["max_dd"] is not None]
    best = min(ok, key=lambda r: r["max_dd"]) if ok else None
    print(f"{'arm':<48}{'CAGR':>8}{'max DD':>9}{'q':>10}{'best CAGR':>11}")
    for r in rows:
        mark = "  <-- least drawdown" if r is best else ""
        if r["max_dd"] is None:
            print(f"{r['label']:<48}{'—':>8}{'—':>9}{'—':>10}"
                  f"{100 * r['best_cagr']:>10.1f}%   cannot reach target")
            continue
        print(f"{r['label']:<48}{100 * r['cagr']:>7.1f}%"
              f"{100 * r['max_dd']:>8.1f}%{r['q']:>10.5f}"
              f"{100 * r['best_cagr']:>10.1f}%{mark}")

    b0 = rows[0]
    if b0["max_dd"] is None:
        print(f"\nBASELINE CANNOT REACH {100 * TARGET_CAGR:.0f}% AT ANY SIZE — "
              f"its best is {100 * b0['best_cagr']:.1f}%. Every arm that DOES "
              f"reach it is therefore adding return, not just moving risk "
              f"around, and that is a bigger claim than this study set out to "
              f"test. Treat it with suspicion, not enthusiasm.")
    elif best:
        print(f"\nbaseline needs {100 * b0['max_dd']:.1f}% drawdown for "
              f"{100 * b0['cagr']:.0f}% CAGR; best arm needs "
              f"{100 * best['max_dd']:.1f}% — "
              f"{100 * (b0['max_dd'] - best['max_dd']):.1f} points less for the "
              f"same return.")
    print(f"\nNFP/claims filter removed {dropped} trading days of "
          f"{len(base)} ({100 * dropped / len(base):.1f}%). FOMC, CPI, PPI, GDP "
          f"and PCE are NOT in this test: calendar_us.FIXED covers 2026 only, "
          f"so they cannot be dated across an eight-year sample. The macro "
          f"result below is therefore a LOWER BOUND on what a full calendar "
          f"would do, not an estimate of it.")
    print(f"\n{len(rows) - 1} arms tried on one book. Treat the best as a "
          f"candidate, not a finding.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"target_cagr": TARGET_CAGR, "arms": rows},
                              indent=1), "utf-8")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
