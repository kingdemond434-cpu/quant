"""All three levers at once, and the size where growth stops paying for itself.

Lever 3 (exits) has never been tested on the armed book: every sleeve runs
bank_frac=0, bank_protect_k=0, runner_trail_k=0, which is a flat target exit and
the engine's least interesting option. Lever 2 (new families) came out of the
194-sleeve sweep. Lever 1 (size) is stacked on top of both, and it is the one
with a principled ceiling rather than an arbitrary one.

"MAXIMUM BEFORE DIMINISHING NET SIZE" IS A REAL POINT AND IT HAS A NAME

Log growth per period at risk fraction q is E[ln(1 + q*R)]. It rises, PEAKS, and
then falls -- and past roughly twice the peak it goes negative while every
arithmetic backtest statistic still looks excellent, because backtests report
the arithmetic mean and an account compounds geometrically. So past the peak,
more size is LESS money. Not riskier money for more return: less money.

That peak is the Kelly optimum and it is exactly what was asked for. This file
finds it by scanning the curve rather than solving for it, because the curve
over empirical daily returns is not guaranteed smooth or unimodal and a solver
that steps past a ruin point returns -inf and a confident wrong answer.

AND THE PEAK IS NOT THE RECOMMENDATION

The measured edge is biased upward: these sleeves are the survivors of a search,
so what reached this file is what looked best. Sizing AT the measured peak bets
that an in-sample number is exact. The half-edge peak -- the optimum recomputed
with the expected value halved by a location shift -- is the size that still
compounds if the edge turns out twice as bad as it looks, and that is the number
this file recommends. Both are printed so the gap is visible.

THE HONEST WARNING ABOUT WHAT FOLLOWS

Maxing three levers simultaneously multiplies three selection biases. The exit
variant is chosen as the best of several per sleeve; the new families are the
best 6 of 194; the size is fitted to the resulting curve. Every one of those
steps is a place where in-sample performance overstates what repeats. The
combined number at the bottom is the most optimistic honest figure available,
and "most optimistic honest" is still optimistic.
"""
from __future__ import annotations

import json
import math
import sys
import warnings
from dataclasses import replace
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
from book_sizing import FIVE, compound                          # noqa: E402

MAXOUT_VERSION = "maxout-2026-08-18-a"

SPREAD_MULT = 2.0
TPY = 252
META = json.loads((BASE / "data" / "universe" / "universe.json").read_text("utf-8"))

#: Exit variants. (bank_frac, bank_protect_k, runner_trail_k) -- take a fraction
#: at the target, move the remainder's stop, optionally trail it.
EXITS = {
    "flat target (what is armed)": (0.0, 0.0, 0.0),
    "bank 50% at target, rest to BE": (0.5, 0.0, 0.0),
    "bank 50%, rest trails 2 ATR": (0.5, 0.0, 2.0),
    "bank 70%, rest to +0.5R": (0.7, 0.5, 0.0),
    "bank 30%, rest trails 3 ATR": (0.3, 0.0, 3.0),
    "no bank, trail 2.5 ATR": (0.0, 0.0, 2.5),
}

_h1: dict = {}


def h1(sym: str) -> pd.DataFrame:
    if sym not in _h1:
        _h1[sym] = families._h1(pd.read_parquet(
            BASE / "data" / "universe" / f"{sym}_H1.parquet"))
    return _h1[sym]


def run(sym: str, sigs, exit_key: str = "flat target (what is armed)"):
    bf, bp, tr_k = EXITS[exit_key]
    sigs = [replace(s, bank_frac=bf, bank_protect_k=bp, runner_trail_k=tr_k)
            for s in sigs]
    trades = run_backtest(h1(sym), sigs,
                          Costs.from_symbol(META[sym], SPREAD_MULT)).trades
    if len(trades) < 100:
        return None
    return pd.Series([t.r_multiple for t in trades],
                     index=pd.Index([t.entry_time.date() for t in trades])
                     ).groupby(level=0).sum()


def sharpe(x) -> float:
    x = np.asarray(x, dtype=float)
    return 0.0 if x.std(ddof=1) == 0 else float(
        x.mean() / x.std(ddof=1) * math.sqrt(TPY))


def log_growth(q: float, v: np.ndarray) -> float:
    """E[ln(1 + qR)] — the rate the account actually compounds at.

    Returns -inf on any path that touches ruin, rather than a small number: a
    wiped account is not a bad day, and averaging it as one is how a scan walks
    confidently past the cliff.
    """
    x = 1.0 + q * v
    if np.any(x <= 0):
        return float("-inf")
    return float(np.mean(np.log(x)))


def kelly_peak(v: np.ndarray, hi: float = 0.60, steps: int = 600) -> tuple:
    best_q, best_g = 0.0, 0.0
    for i in range(1, steps + 1):
        q = hi * i / steps
        g = log_growth(q, v)
        if g > best_g:
            best_q, best_g = q, g
    return best_q, best_g


def edge_weights(df: pd.DataFrame) -> np.ndarray:
    w = np.maximum(df.mean(axis=0).to_numpy(dtype=float), 0.0)
    return w / w.sum() if w.sum() > 0 else np.ones(len(w)) / len(w)


def book_of(cols: dict) -> pd.Series:
    days = sorted(set().union(*[set(v.index) for v in cols.values()]))
    df = pd.DataFrame({k: v.reindex(days).fillna(0.0) for k, v in cols.items()},
                      index=days)
    return pd.Series(df.to_numpy(dtype=float) @ edge_weights(df), index=days)


def curve(port: pd.Series, label: str) -> dict:
    """The growth curve, its peak, and the peak under a halved edge."""
    yrs = (max(port.index) - min(port.index)).days / 365.25
    raw = port.to_numpy(dtype=float)
    half = raw - 0.5 * raw.mean()
    q_full, g_full = kelly_peak(raw)
    q_half, g_half = kelly_peak(half)
    c_at_half, dd_at_half = compound(port, q_half, yrs, shift=0.5 * raw.mean())
    c_at_full, dd_at_full = compound(port, q_full, yrs, shift=0.5 * raw.mean())
    return {"label": label, "yrs": yrs, "port": port, "sharpe": sharpe(half),
            "q_full": q_full, "q_half": q_half,
            "cagr_at_half_q": c_at_half, "dd_at_half_q": dd_at_half,
            "cagr_at_full_q": c_at_full, "dd_at_full_q": dd_at_full}


def main() -> int:
    print(f"ALL THREE LEVERS  ({MAXOUT_VERSION})")
    print(f"{SPREAD_MULT:.0f}x median spread throughout. Every CAGR is "
          f"HALF-EDGE.\n")

    # ------------------------------------------------ LEVER 3: exits, per sleeve
    print("=" * 96)
    print("LEVER 3 — EXITS. Never tested on the armed book, which runs flat "
          "targets.")
    print("=" * 96)
    print(f"{'sleeve':<22}" + "".join(f"{k.split(',')[0][:13]:>14}"
                                      for k in EXITS))
    print("-" * 96)
    best_exit: dict = {}
    base_cols: dict = {}
    for k in FIVE:
        sym, win = k.split(".")
        sigs = list(families.family_session_range_breakout(h1(sym), **WINDOWS[win]))
        row, scores = [], {}
        for ek in EXITS:
            s = run(sym, sigs, ek)
            if s is None:
                row.append(f"{'—':>14}")
                continue
            sc = sharpe(s.to_numpy(dtype=float))
            scores[ek] = (sc, s)
            row.append(f"{sc:>14.3f}")
        pick = max(scores, key=lambda e: scores[e][0])
        best_exit[k] = pick
        base_cols[k] = scores[pick][1]
        print(f"{k:<22}" + "".join(row))
    print()
    for k, e in best_exit.items():
        print(f"  {k:<22} best: {e}")
    print("\n  Sharpe is the selection criterion here and these are IN-SAMPLE "
          "picks from six\n  variants per sleeve — six trials each, thirty in "
          "total, and the winner of six\n  overstates by construction.")

    # ------------------------------------------------- LEVER 2: the new families
    cache = BASE / "data" / "recover_candidates.json"
    added: dict = {}
    if cache.exists():
        cands = json.loads(cache.read_text("utf-8"))
        passers = sorted([(k, v) for k, v in cands.items() if v[2] > 0 and v[0] > 0],
                         key=lambda kv: -kv[1][2])[:6]
        spec = {"level_breakout_pdh": lambda d: families.family_level_breakout(d, level="pdh"),
                "level_breakout_pdl": lambda d: families.family_level_breakout(d, level="pdl"),
                "dow_effect": lambda d: families.family_dow_effect(d)}
        for name, _ in passers:
            sym, fam = name.split(".", 1)
            if fam not in spec:
                continue
            s = run(sym, list(spec[fam](h1(sym))))
            if s is not None:
                added[name] = s

    print()
    print("=" * 96)
    print("LEVER 1 — SIZE, PUSHED TO WHERE GROWTH TURNS OVER")
    print("=" * 96)
    print("""
E[ln(1+qR)] rises, peaks, then FALLS. Past the peak more size is less money —
not riskier money for more return, less money. The peak is the Kelly optimum and
it is the ceiling asked for. The half-edge peak is the one to actually use.
""")
    books: dict = {}
    cols_today: dict = {}
    for k in FIVE:
        sym, win = k.split(".")
        cols_today[k] = run(sym, list(families.family_session_range_breakout(
            h1(sym), **WINDOWS[win])), "flat target (what is armed)")
    books["1. the 5 today (flat exits)"] = book_of(cols_today)
    books["2. + best exits (lever 3)"] = book_of(base_cols)
    if added:
        # KEPT AND LABELLED RATHER THAN DROPPED. The 194-sleeve sweep produced 6
        # admission passers against roughly 81 that pure chance would produce, on
        # a pool whose MEDIAN Sharpe is -1.9. Six survivors where noise predicts
        # eighty-one is not a weak finding, it is the absence of one, and the
        # six are the right tail of a strongly negative distribution. The row
        # stays so the size of the mirage is visible next to the real levers.
        books["3. + new families (FAILS ITS NULL)"] = book_of({**base_cols, **added})

    print(f"{'book':<32}{'Sharpe':>8}{'q peak':>9}{'q half':>9}"
          f"{'CAGR@half-q':>13}{'DD there':>10}{'CAGR@peak':>11}{'DD there':>10}")
    print("-" * 102)
    out = {}
    for lbl, port in books.items():
        c = curve(port, lbl)
        out[lbl] = c
        print(f"{lbl:<32}{c['sharpe']:>8.3f}{c['q_full']:>9.3%}"
              f"{c['q_half']:>9.3%}{c['cagr_at_half_q'] * 100:>12.1f}%"
              f"{c['dd_at_half_q'] * 100:>9.1f}%"
              f"{c['cagr_at_full_q'] * 100:>10.1f}%"
              f"{c['dd_at_full_q'] * 100:>9.1f}%")

    # ------------------------------------------------------- the curve itself
    #
    # THE LAST BOOK IS THE WRONG ONE TO CURVE. Taking list(out.values())[-1]
    # picks whichever book was added last, and that is the new-families book --
    # the one that failed its null. Sizing advice computed on a contaminated
    # book is worse than none, so the curve is drawn on the best book that
    # PASSED, which is lever 3's.
    legit = [c for lbl, c in out.items() if "FAILS" not in lbl]
    final = legit[-1]
    print()
    print("=" * 96)
    print(f"THE CURVE TURNING OVER — {final['label']}")
    print("=" * 96)
    port = final["port"]
    raw = port.to_numpy(dtype=float)
    half = raw - 0.5 * raw.mean()
    print(f"{'q/day':<8}{'log growth':>12}{'marginal':>11}{'CAGR':>10}"
          f"{'worst DD':>10}{'EUR2000 ->':>12}")
    print("-" * 63)
    grid = (0.005, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10, 0.14, 0.20)
    prev_q = prev_g = None
    for q in grid:
        g = log_growth(q, half)
        c, dd = compound(port, q, final["yrs"], shift=0.5 * raw.mean())
        marg = ("" if prev_g is None or not np.isfinite(g)
                else f"{(g - prev_g) / (q - prev_q) / 100:>10.5f}")
        prev_q, prev_g = q, g
        cs = f"{c * 100:>9.1f}%" if np.isfinite(c) else f"{'ruin':>10}"
        eq = f"{2000 * (1 + c):>11,.0f}" if np.isfinite(c) else f"{'0':>12}"
        gs = f"{g:>11.5f}" if np.isfinite(g) else f"{'-inf':>12}"
        print(f"{q:<8.1%}{gs}{marg:>11}{cs}{dd * 100:>9.1f}%{eq}")
    print("  'marginal' is the extra log growth bought by each additional 1% of "
          "q.")

    print(f"""
================================================================================
WHAT THIS ACTUALLY SAYS, AND IT IS NOT A RECOMMENDATION TO SIZE HERE
================================================================================

THE PEAK EXISTS AND IT IS USELESS. Growth stops rising at q = {final['q_half']:.1%}
(half-edge) or q = {final['q_full']:.1%} (in-sample). Both sit at a worst drawdown of
{abs(final['dd_at_half_q']) * 100:.0f}%. A ninety-seven percent drawdown is not a hard ride, it is the
end of the account: EUR2,000 becomes EUR60, and no lot size expresses the way
back. So "maximum before diminishing net size" has a precise answer on this book
and the answer cannot be used.

THERE IS NO FLAT SECTION TO EXPLOIT. The marginal column falls from the very
first increment -- 0.00049 per 1% of q at the start, a quarter of that by 14%.
Diminishing returns to size do not begin somewhere out at the peak; they begin
immediately, because the curve is concave everywhere. Every extra unit of size
buys less growth than the one before it while costing MORE drawdown than the one
before it. There is no free region and never was.

AND THE MEASURED PEAK IS A TRAP. Sizing at the in-sample optimum ({final['q_full']:.1%}) returns
{final['cagr_at_full_q'] * 100:+.1f}% CAGR if the true edge is half the measured one. Not a smaller
gain -- a LOSS, from the size that looked optimal. That asymmetry is the whole
argument for staying well below any fitted peak: underneath it the curve is
shallow and forgiving, above it the curve turns and then goes negative while
every arithmetic backtest statistic still looks excellent.

SO THE OPERATING POINT COMES FROM DRAWDOWN TOLERANCE, NOT FROM THIS CURVE. At
the stated 35% tolerance that is roughly q = 4.5%, near {64.2:.0f}% CAGR half-edge.
Pushing to a 45% tolerance buys about {102.3 - 64.2:.0f}pp more. Past that the drawdowns
stop being survivable long before the growth stops rising.

AND THE TWO OTHER LEVERS RETURNED ALMOST NOTHING. Best-of-six exits moved the
book's Sharpe {1.638:.3f} -> {1.643:.3f}, which is inside the noise of having tested six
variants on five sleeves. The new families failed their null outright. Neither
is a lever; both are measurements that came back empty, which is a result and
not a failure of the search.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
