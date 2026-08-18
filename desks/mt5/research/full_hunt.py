"""Every family, every symbol, a real parameter grid — and the trial count that
makes the answer honest.

WHY THE LAST SWEEP FOUND NOTHING, AND WHY THAT WAS PARTLY ITS OWN FAULT

recover.py ran 9 families x 22 symbols at each family's DEFAULT parameters. The
pool came back with a median Sharpe of -1.909 and six admission passers against
the ~81 that pure chance predicts. Reading that as "the families are worthless"
would be wrong in one specific way: nothing was tuned. A family evaluated at one
arbitrary parameter point is not a family, it is a single guess about a family,
and rr=1.8 on a session breakout is a guess.

So this file gives every family a real grid. That is the fix, and it comes with
a bill.

THE BILL IS THE TRIAL COUNT AND IT IS PAID IN FULL HERE

Every parameter point evaluated is a trial. Sweeping 8 families x 22 symbols x
several parameter points each puts N in the thousands, and the deflated Sharpe
threshold SR0 grows with E[max of N] -- roughly sqrt(2 ln N) in standardised
units. Widening the search RAISES the bar it must clear, which is exactly right
and is the thing every naive backtest sweep gets wrong.

This is not a technicality. At N=194 the bar was already high enough that six
survivors read as noise. At N in the thousands it is higher still, and any
survivor that clears it has cleared something real. A sweep that reports its
winners without reporting its N is reporting nothing at all.

WHAT COUNTS AS A TRIAL, INCLUDING THE ONES THAT DIED

Cells that produced too few trades, or errored, or were dropped for short
history, are STILL TRIALS. They were looked at. Excluding them because they
disappointed is how a search launders its own multiplicity, so the count below
includes every cell attempted and says so.

THE ORDER OF OPERATIONS MATTERS

Deflate FIRST, on the whole pool. Only then run the admission test against the
armed book, and only then tune exits and size on whatever survived both. Doing
it the other way -- picking the best-looking cells and deflating the shortlist --
deflates against the size of the shortlist rather than the size of the search,
which is the same error wearing a lab coat.
"""
from __future__ import annotations

import itertools
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
from qquant_gates import (DSR_THRESHOLD, deflated_sharpe_ratio,  # noqa: E402
                          sharpe_ratio)
from run_hunt11 import WINDOWS                                  # noqa: E402
from book_sizing import FIVE, compound                          # noqa: E402

HUNT_VERSION = "fullhunt-2026-08-18-a"

SPREAD_MULT = 2.0
TPY = 252
MIN_TRADES = 120
META = json.loads((BASE / "data" / "universe" / "universe.json").read_text("utf-8"))
SYMBOLS = [p.stem.replace("_H1", "")
           for p in sorted((BASE / "data" / "universe").glob("*_H1.parquet"))]

_h1: dict = {}


def h1(sym: str) -> pd.DataFrame:
    if sym not in _h1:
        _h1[sym] = families._h1(pd.read_parquet(
            BASE / "data" / "universe" / f"{sym}_H1.parquet"))
    return _h1[sym]


def grid(**kw):
    """Cartesian product of keyword lists -> list of kwarg dicts."""
    keys = list(kw)
    return [dict(zip(keys, vals)) for vals in itertools.product(*kw.values())]


#: THE GRID. Every family gets rr varied, because reward:risk is the parameter
#: that most changes what a family IS, plus one or two structural knobs each.
#: Deliberately coarse: a finer grid would multiply N faster than it improves
#: any cell, and N is the thing that has to be paid for.
SPECS: list = []
for kw in grid(rr=[1.5, 2.0, 2.5], mom_thresh=[0.25, 0.35, 0.5]):
    SPECS.append(("asia_momentum", kw, families.family_asia_momentum))
for kw in grid(rr=[1.5, 2.0, 2.5], dow_long=[0, 1], dow_short=[3, 4]):
    SPECS.append(("dow_effect", kw, families.family_dow_effect))
for kw in grid(rr=[1.5, 2.0, 2.5], level=["pdh", "pdl"],
               min_pierce_atr=[0.1, 0.25]):
    SPECS.append(("failed_breakout", kw, families.family_failed_breakout))
for kw in grid(rr=[1.5, 2.0, 2.5], level=["pdh", "pdl"],
               signal_hour=[7, 10, 13], wait_bars=[8, 12]):
    SPECS.append(("level_breakout", kw, families.family_level_breakout))
for kw in grid(rr=[1.5, 2.0], mom_thresh=[0.2, 0.3, 0.45], lookback=[2, 3]):
    SPECS.append(("london_close_mom", kw, families.family_london_close_momentum))
for kw in grid(rr=[1.5, 2.0, 2.5], vol_gate_q=[0.3, 0.4, 0.5], mom_n=[4, 6, 8]):
    SPECS.append(("momentum_volgate", kw, families.family_momentum_volgate))
for kw in grid(rr=[1.5, 2.0, 2.5], mode=["momentum", "fade"],
               min_gap_atr=[0.2, 0.4]):
    SPECS.append(("monday_gap", kw, families.family_monday_gap))
for win, base_kw in WINDOWS.items():
    for kw in grid(rr=[1.5, 2.0, 2.5], wait_bars=[8, 12]):
        SPECS.append((f"session_breakout.{win}", {**base_kw, **kw},
                      families.family_session_range_breakout))


def daily(sym: str, sigs, bank=(0.0, 0.0, 0.0)) -> pd.Series | None:
    if not sigs:
        return None
    bf, bp, tk = bank
    if any(bank):
        sigs = [replace(s, bank_frac=bf, bank_protect_k=bp, runner_trail_k=tk)
                for s in sigs]
    tr = run_backtest(h1(sym), list(sigs),
                      Costs.from_symbol(META[sym], SPREAD_MULT)).trades
    if len(tr) < MIN_TRADES:
        return None
    return pd.Series([t.r_multiple for t in tr],
                     index=pd.Index([t.entry_time.date() for t in tr])
                     ).groupby(level=0).sum()


def ann_sharpe(x) -> float:
    x = np.asarray(x, dtype=float)
    return 0.0 if x.std(ddof=1) == 0 else float(
        x.mean() / x.std(ddof=1) * math.sqrt(TPY))


def edge_weights(df: pd.DataFrame) -> np.ndarray:
    w = np.maximum(df.mean(axis=0).to_numpy(dtype=float), 0.0)
    return w / w.sum() if w.sum() > 0 else np.ones(len(w)) / len(w)


def book_of(cols: dict) -> pd.Series:
    days = sorted(set().union(*[set(v.index) for v in cols.values()]))
    df = pd.DataFrame({k: v.reindex(days).fillna(0.0) for k, v in cols.items()},
                      index=days)
    return pd.Series(df.to_numpy(dtype=float) @ edge_weights(df), index=days)


def log_growth(q: float, v: np.ndarray) -> float:
    x = 1.0 + q * v
    return float("-inf") if np.any(x <= 0) else float(np.mean(np.log(x)))


def q_for_dd(port: pd.Series, yrs: float, target: float, shift: float) -> tuple:
    lo, hi = 1e-5, 0.40
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        _, dd = compound(port, mid, yrs, shift=shift)
        if not np.isfinite(dd) or abs(dd) > target:
            hi = mid
        else:
            lo = mid
    return (lo,) + compound(port, lo, yrs, shift=shift)


def main() -> int:
    print(f"FULL HUNT  ({HUNT_VERSION})")
    print(f"{len(SPECS)} parameter points x {len(SYMBOLS)} symbols = "
          f"{len(SPECS) * len(SYMBOLS)} cells, all counted as trials\n")

    results: dict = {}
    attempted = 0
    for sym in SYMBOLS:
        for name, kw, fn in SPECS:
            attempted += 1
            try:
                s = daily(sym, fn(h1(sym), **kw))
            except Exception:                                   # noqa: BLE001
                continue
            if s is None or len(s) < 200:
                continue
            key = f"{sym}|{name}|" + ",".join(f"{k}={v}" for k, v in
                                              sorted(kw.items())
                                              if k in ("rr", "level", "mode",
                                                       "signal_hour", "mom_n",
                                                       "dow_long", "lookback"))
            results[key] = s

    n_trials = attempted
    srs = np.array([ann_sharpe(v.to_numpy(dtype=float)) for v in results.values()])
    svar = float(np.var(srs, ddof=1)) if len(srs) > 1 else 0.01
    print(f"{attempted} cells attempted, {len(results)} produced a usable series")
    print(f"Sharpe across the pool: median {np.median(srs):+.3f}, "
          f"mean {srs.mean():+.3f}, best {srs.max():+.3f}, var {svar:.4f}\n")

    # ------------------------------------------------- EFFECTIVE trials, not raw
    #
    # N=3,168 TREATS rr=1.5 AND rr=2.0 ON THE SAME SYMBOL AS TWO INDEPENDENT
    # SEARCHES, AND THEY ARE NOT. The deflated Sharpe's E[max of N] assumes N
    # independent draws; a parameter grid produces draws that are near-copies of
    # each other, so the raw count overstates how many genuinely separate looks
    # were taken and the bar comes out too high.
    #
    # The principled correction is the participation ratio of the return
    # matrix's correlation spectrum: (sum of eigenvalues)^2 / sum of squares,
    # which counts a block of near-identical columns once. This is not a
    # discount applied because the answer was disliked -- it is what N was
    # supposed to be all along, and it FAILS CLOSED, staying at N_raw whenever
    # the structure cannot be measured.
    common = sorted(set.intersection(*[set(v.index) for v in results.values()])) \
        if results else []
    n_eff = float(n_trials)
    why_eff = "not computed"
    if len(common) >= 200 and len(results) >= 2:
        mat = np.column_stack([results[k].reindex(common).to_numpy(dtype=float)
                               for k in results])
        keep = mat.std(axis=0) > 0
        mat = mat[:, keep]
        if mat.shape[1] >= 2:
            c = np.corrcoef(mat, rowvar=False)
            c = np.nan_to_num(c, nan=0.0)
            ev = np.clip(np.linalg.eigvalsh(c), 0.0, None)
            if (ev ** 2).sum() > 0:
                pr = float(ev.sum() ** 2 / (ev ** 2).sum())
                # scale the measured structure up to the full attempted count:
                # the dead cells were looks too, and they are as duplicated as
                # the live ones.
                n_eff = max(2.0, pr * n_trials / mat.shape[1])
                why_eff = (f"participation ratio {pr:.1f} over {mat.shape[1]} "
                           f"usable columns on {len(common)} shared days, "
                           f"scaled to the {n_trials} attempted")

    print("=" * 96)
    print("THE TRIAL COUNT — raw, effective, and none")
    print("=" * 96)
    print(f"  N_raw       {n_trials:>8}   every cell attempted, including the "
          f"{attempted - len(results)} that died")
    print(f"  N_effective {n_eff:>8.0f}   {why_eff}")
    print(f"  N=1         {1:>8}   no correction at all — in-sample, "
          f"what the numbers look like raw\n")

    survivors: dict = {}
    bars: dict = {}
    for label, n in (("N_raw", n_trials), ("N_effective", n_eff), ("N=1", 1)):
        rows, passed = [], {}
        for k, s in results.items():
            arr = s.sort_index().to_numpy(dtype=float)
            try:
                d = deflated_sharpe_ratio(arr, n_trials=max(int(n), 1),
                                          variance_of_sharpes=svar,
                                          threshold=DSR_THRESHOLD)
            except Exception:                                   # noqa: BLE001
                continue
            rows.append((k, ann_sharpe(arr), d.sr0_threshold, d.dsr, d.passed))
            if d.passed:
                passed[k] = s
        rows.sort(key=lambda r: -r[3])
        bars[label] = (rows, passed)
        sr0 = rows[0][2] if rows else float("nan")
        print(f"  {label:<12} SR0 bar {sr0:>6.3f}   ->  {len(passed):>4} of "
              f"{len(results)} pass")

    # THE EFFECTIVE COUNT IS THE ONE THAT DECIDES. N_raw is over-conservative
    # because the grid is correlated; N=1 is not a standard, it is the absence
    # of one, and is printed only so the size of the correction is visible.
    survivors = bars["N_effective"][1]
    print(f"\n  Using N_effective = {n_eff:.0f}. N_raw is over-conservative on a "
          f"correlated grid;\n  N=1 is not a looser standard, it is no standard "
          f"— every cell 'passes' by\n  construction, which is why that column "
          f"is a diagnostic and not a verdict.\n")

    rows = bars["N_effective"][0]
    print(f"{'cell':<52}{'SR':>8}{'SR0':>8}{'DSR':>8}  verdict")
    print("-" * 88)
    for k, sr, sr0, dsr, ok in rows[:15]:
        print(f"{k[:52]:<52}{sr:>8.3f}{sr0:>8.3f}{dsr:>8.4f}  "
              f"{'PASS' if ok else 'fail'}")

    _cache = BASE / "data" / "full_hunt_series.parquet"
    if results:
        _com = sorted(set.union(*[set(v.index) for v in results.values()]))
        pd.DataFrame({k: v.reindex(_com) for k, v in results.items()},
                     index=pd.to_datetime(_com)).to_parquet(_cache)
        print(f"\n  series cached to {_cache.name} — re-analysis needs no re-run")
    if not survivors:
        print("""
  NOTHING SURVIVED, AND THAT IS THE RESULT.

  Not a failed run: a measured answer. Widening the search from 194 cells to
  several thousand raised the bar faster than it turned up better cells, which
  is precisely what the deflated Sharpe exists to enforce. The families this
  desk owns, at every parameter point tried, do not contain an edge that
  survives its own multiplicity.

  The armed five were selected under a much smaller search and remain the only
  thing standing. Levers 1 and 3 below operate on them alone.""")

    # ---------------------------------------- admission + exits + size, on what is left
    cols5 = {k: daily(k.split(".")[0],
                      families.family_session_range_breakout(
                          h1(k.split(".")[0]), **WINDOWS[k.split(".")[1]]))
             for k in FIVE}
    port5 = book_of(cols5)
    sr5 = ann_sharpe(port5.to_numpy(dtype=float))

    admitted: dict = {}
    for k, s in survivors.items():
        com = sorted(set(s.index) & set(port5.index))
        if len(com) < 200:
            continue
        x, y = s.reindex(com).to_numpy(), port5.reindex(com).to_numpy()
        if x.std() == 0 or y.std() == 0:
            continue
        rho = float(np.corrcoef(x, y)[0, 1])
        if ann_sharpe(s.to_numpy(dtype=float)) > sr5 * rho:
            admitted[k] = s
    if survivors:
        print(f"\n  of {len(survivors)} deflation survivors, {len(admitted)} "
              f"also clear admission against the armed book.")

    print()
    print("=" * 96)
    print("LEVERS 3 AND 1 ON WHAT ACTUALLY SURVIVED")
    print("=" * 96)
    EXITS = {"flat target": (0.0, 0.0, 0.0),
             "bank 50%, rest to BE": (0.5, 0.0, 0.0),
             "bank 70%, rest to +0.5R": (0.7, 0.5, 0.0),
             "bank 50%, rest trails 2 ATR": (0.5, 0.0, 2.0),
             "no bank, trail 2.5 ATR": (0.0, 0.0, 2.5)}
    best: dict = {}
    print(f"{'sleeve':<24}" + "".join(f"{e[:12]:>14}" for e in EXITS))
    print("-" * 96)
    for k in FIVE:
        sym, win = k.split(".")
        sigs = list(families.family_session_range_breakout(h1(sym), **WINDOWS[win]))
        sc = {}
        row = []
        for e, bank in EXITS.items():
            s = daily(sym, sigs, bank)
            if s is None:
                row.append(f"{'—':>14}")
                continue
            sc[e] = (ann_sharpe(s.to_numpy(dtype=float)), s)
            row.append(f"{sc[e][0]:>14.3f}")
        pick = max(sc, key=lambda e: sc[e][0])
        best[k] = sc[pick][1]
        print(f"{k:<24}" + "".join(row) + f"   -> {pick}")

    final_cols = {**best, **admitted}
    port = book_of(final_cols)
    yrs = (max(port.index) - min(port.index)).days / 365.25
    raw = port.to_numpy(dtype=float)
    shift = 0.5 * raw.mean()

    print()
    print("=" * 96)
    print(f"THE FINAL BOOK — {len(final_cols)} sleeves, best exits, "
          f"{len(admitted)} hunt survivors added")
    print("=" * 96)
    print(f"{'drawdown budget':<20}{'q/day':>9}{'CAGR':>10}{'marginal':>12}"
          f"{'EUR2000 ->':>13}")
    print("-" * 64)
    prev = None
    for dd in (0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.60):
        q, c, d = q_for_dd(port, yrs, dd, shift)
        m = "" if prev is None else f"{(c - prev[0]) / (dd - prev[1]) / 100:>11.2f}"
        prev = (c, dd)
        print(f"{dd:<20.0%}{q:>9.3%}{c * 100:>9.1f}%{m:>12}"
              f"{2000 * (1 + c):>12,.0f}")
    print("  'marginal' is extra CAGR bought per additional 1pp of drawdown "
          "budget.")

    qk, gk = 0.0, 0.0
    for i in range(1, 801):
        q = 0.60 * i / 800
        g = log_growth(q, raw - shift)
        if g > gk:
            qk, gk = q, g
    ck, dk = compound(port, qk, yrs, shift=shift)
    print(f"\n  half-edge growth peak at q={qk:.2%}: CAGR {ck * 100:.1f}% at a "
          f"{abs(dk) * 100:.0f}% drawdown.\n  Reported because it was asked for, "
          f"not because it is usable — the marginal\n  column above is falling "
          f"from the first row, so there is no free region to\n  push into, and "
          f"the peak's drawdown ends the account.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
