"""How much should a winner breathe, and how much should be banked on the way?

The pyramid sweep lost 135 times out of 135 and the reason was structural: these
sleeves carry a fixed target, so an add at +2R fills essentially at the exit and
pays a full round trip for no runway. That is a statement about the EXIT, not
about pyramiding, and it makes the exit the thing worth sweeping.

The engine's exit is a three-stage machine and every stage is a dial:

    target(rr) -> bank `bank_frac` of the position
               -> survivor's stop jumps to entry + stop_dist * bank_protect_k
               -> survivor trails at stop_dist * runner_trail_k off the extreme
               -> or dies on ttl

So "let it breathe" and "bank the profit" are not opposed, they are two knobs on
one mechanism, and the question is where the pair sits, per sleeve.

THREE THINGS THIS DOES THAT A NAIVE SWEEP WOULD NOT

  MATCHED DRAWDOWN. Every arm is solved to the same 35% budget before its CAGR
  is read. A looser trail wins more R and carries more heat; compared at equal
  q it would look better for the second reason and be credited for the first.

  THE TRIAL COUNT IS PRINTED. 216 exits per sleeve is 216 chances to find a
  lucky one. The desk's standing rule is to judge on the raw threshold and not
  move the bar -- that is about not INFLATING the bar, not about pretending the
  search was one test. The count is reported so whatever consumes this can
  deflate honestly.

  THE PYRAMID GOES BACK ON THE WINNER. The whole point of the exercise is to
  test whether pyramiding pays once a runner has somewhere to run. That is a
  prediction the last sweep made, so it gets checked rather than assumed.
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
OUT = _DESK / "reports" / "exit_sweep.json"
META = json.loads((UNI / "universe.json").read_text("utf-8"))
SPREAD_MULT, DD_TARGET, TPY = 2.0, 0.35, 252

BOOK = [("XAUUSD", "asia"), ("USDJPY", "asia"), ("CADJPY", "asia"),
        ("EURJPY", "asia"), ("XAUUSD", "london_am")]

RR = (1.0, 1.5, 2.0)              # where the bank happens
BANK = (0.25, 0.5, 0.75)          # how much comes off there
PROTECT = (0.0, 0.5, 1.0)         # survivor's stop after the bank, in R
TRAIL = (1.0, 2.0, 3.0, 5.0)      # chandelier width -- the breathing room
TTL_MULT = (1, 3)                 # how long the runner is allowed to live

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


def q_for_dd(r, target, shift):
    """Delegates to `mt5desk.sizing` -- this file carried its own copy of the ruin bug.

    THE COPY THAT WAS HERE SIZED **UP** PAST RUIN. At a large enough q some day has
    `1 + q*x <= 0`, the account is not drawn down but GONE, cumprod goes negative, the drawdown
    expression yields NaN, and `NaN > target` evaluates to False -- so the search concluded the
    budget was respected and raised q. It was also unbounded above at 0.5 regardless of how bad
    the worst observed day was.

    `mt5desk/sizing.py` was made the single implementation on 2026-08-19 precisely to end this,
    and its commit named `growth_now.py` and `exit_sweep.py` as the latent siblings. This copy
    survived anyway -- it reached the merged tree from master rather than from the branch that
    did the rewiring, which is row 110's defect class one more time: a fix applied where it was
    found and not swept for twins.
    """
    return q_for_drawdown(r.to_numpy(float) - shift, target)


def growth(r):
    if len(r) < 100:
        return -1.0, 0.0
    shift = 0.5 * float(r.mean())
    q = q_for_dd(r, DD_TARGET, shift)
    x = r.to_numpy(float) - shift
    yrs = max((max(r.index) - min(r.index)).days / 365.25, 0.5)
    eq = float(np.prod(1.0 + q * x))
    return (eq ** (1 / yrs) - 1.0 if eq > 0 else -1.0), q


def variant(base, **kw):
    out = []
    for s in base:
        s2 = type(s)(**{**s.__dict__})
        for k, v in kw.items():
            setattr(s2, k, v)
        out.append(s2)
    return out


def main() -> int:
    grid = list(itertools.product(RR, BANK, PROTECT, TRAIL, TTL_MULT))
    print(f"EXIT SWEEP  {len(grid)} exits/sleeve, matched {100 * DD_TARGET:.0f}% "
          f"drawdown, half-edge, {SPREAD_MULT:.0f}x spread\n")
    rows, summary = [], []
    for sym, win in BOOK:
        df, costs = h1(sym), Costs.from_symbol(META[sym], SPREAD_MULT)
        base = list(families.family_session_range_breakout(df, **WINDOWS[win]))
        ttl0 = base[0].ttl_bars if base else 12
        flat = daily(run_backtest(df, base, costs).trades)
        g0, q0 = growth(flat)
        best = None
        for rr, bank, prot, trail, tm in grid:
            sigs = variant(base, bank_frac=bank, bank_protect_k=prot,
                           runner_trail_k=trail, ttl_bars=int(ttl0 * tm))
            for s, b in zip(sigs, base, strict=True):
                sd = abs(b.stop - (b.trigger if b.trigger is not None else b.stop))
                if sd > 0:
                    s.target = (b.trigger if b.trigger is not None else b.target) \
                        + b.side * sd * rr
            ser = daily(run_backtest(df, sigs, costs).trades)
            g, q = growth(ser)
            rec = {"sleeve": f"{sym}.{win}", "rr": rr, "bank_frac": bank,
                   "bank_protect_k": prot, "runner_trail_k": trail,
                   "ttl_mult": tm, "cagr": round(g, 5),
                   "delta": round(g - g0, 5), "q": round(q, 5),
                   "n_days": len(ser)}
            rows.append(rec)
            if best is None or g > best["cagr"]:
                best = rec
        # does the pyramid pay NOW, on the loosest-breathing winner?
        pyr = None
        if best:
            sigs = variant(base, bank_frac=best["bank_frac"],
                           bank_protect_k=best["bank_protect_k"],
                           runner_trail_k=best["runner_trail_k"],
                           ttl_bars=int(ttl0 * best["ttl_mult"]),
                           add_every_r=1.0, add_max=2, add_frac=0.5,
                           add_ratchets_stop=True)
            for s, b in zip(sigs, base, strict=True):
                sd = abs(b.stop - (b.trigger if b.trigger is not None else b.stop))
                if sd > 0:
                    s.target = (b.trigger if b.trigger is not None else b.target) \
                        + b.side * sd * best["rr"]
            gp, _ = growth(daily(run_backtest(df, sigs, costs).trades))
            pyr = round(gp - best["cagr"], 5)
        summary.append({"sleeve": f"{sym}.{win}", "flat_cagr": round(g0, 5),
                        "best": best, "pyramid_delta_on_best": pyr})
        print(f"{sym + '.' + win:<20} flat {100 * g0:6.1f}%   "
              f"best {100 * best['cagr']:6.1f}% "
              f"({100 * best['delta']:+5.1f}%)  "
              f"rr={best['rr']} bank={best['bank_frac']} "
              f"prot={best['bank_protect_k']} trail={best['runner_trail_k']} "
              f"ttl x{best['ttl_mult']}")
        print(f"{'':<20} pyramid on that exit: {100 * pyr:+.1f}%")
    won = [r for r in rows if r["delta"] > 0]
    print(f"\n{len(won)} of {len(rows)} exits beat their flat baseline "
          f"({len(grid)} trials per sleeve -- deflate accordingly).")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"grid_size": len(grid), "dd_target": DD_TARGET,
                               "summary": summary, "rows": rows}, indent=1),
                   "utf-8")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
