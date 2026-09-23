"""Every MT5 family and symbol under one immutable original screen.

The tested trial count remains provenance, but later experimental or harsher
bars never alter a candidate's admission.  The original PSR>=0.95 against
SR0=0 screen decides zero-capital shadow admission.  Only untouched forward
shadow evidence can subsequently grant capital authority.
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

from book_sizing import FIVE, compound  # noqa: E402
from hunt_deflate import write_candidates  # noqa: E402
from mt5desk import families  # noqa: E402
from mt5desk.engine import Costs, run_backtest  # noqa: E402
from run_hunt11 import WINDOWS  # noqa: E402

from libs.validation.dsr import probabilistic_sharpe_ratio  # noqa: E402

HUNT_VERSION = "fullhunt-2026-08-18-a"

SPREAD_MULT = 2.0
TPY = 252
MIN_TRADES = 120
META = json.loads((BASE / "data" / "universe" / "universe.json").read_text("utf-8"))
SYMBOLS = [p.stem.replace("_H1", "")
           for p in sorted((BASE / "data" / "universe").glob("*_H1.parquet"))]

_h1: dict = {}


def candidate_key(symbol: str, family: str, params: dict) -> str:
    """Stable identity containing every tested parameter, without collisions."""
    encoded = ",".join(
        f"{key}={json.dumps(value, sort_keys=True, separators=(',', ':'))}"
        for key, value in sorted(params.items())
    )
    return f"{symbol}|{family}|{encoded}"


def h1(sym: str) -> pd.DataFrame:
    if sym not in _h1:
        _h1[sym] = families._h1(pd.read_parquet(
            BASE / "data" / "universe" / f"{sym}_H1.parquet"))
    return _h1[sym]


def grid(**kw):
    """Cartesian product of keyword lists -> list of kwarg dicts."""
    keys = list(kw)
    return [dict(zip(keys, vals, strict=True))
            for vals in itertools.product(*kw.values())]


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
    return (lo, *compound(port, lo, yrs, shift=shift))


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
            except Exception:
                continue
            if s is None or len(s) < 200:
                continue
            key = candidate_key(sym, name, kw)
            results[key] = s

    n_trials = attempted
    srs = np.array([ann_sharpe(v.to_numpy(dtype=float)) for v in results.values()])
    svar = float(np.var(srs, ddof=1)) if len(srs) > 1 else 0.01
    print(f"{attempted} cells attempted, {len(results)} produced a usable series")
    print(f"Sharpe across the pool: median {np.median(srs):+.3f}, "
          f"mean {srs.mean():+.3f}, best {srs.max():+.3f}, var {svar:.4f}\n")

    print("=" * 96)
    print("IMMUTABLE ORIGINAL DISCOVERY BAR")
    print("=" * 96)
    print(f"  attempted {n_trials}; usable {len(results)}; "
          "PSR >= 0.95 against SR0=0.0")
    survivors = {}
    screen_rows = []
    for key, series in results.items():
        arr = series.sort_index().to_numpy(dtype=float)
        psr = float(probabilistic_sharpe_ratio(arr, sr_benchmark=0.0))
        passed = psr >= 0.95
        screen_rows.append((key, ann_sharpe(arr), psr, passed))
        if passed:
            survivors[key] = series
    screen_rows.sort(key=lambda row: -row[2])
    print(f"  {len(survivors)} of {len(results)} pass the original bar")
    print(f"{'cell':<60}{'SR':>8}{'PSR':>9}  verdict")
    print("-" * 88)
    for key, sr, psr, passed in screen_rows[:15]:
        print(f"{key[:60]:<60}{sr:>8.3f}{psr:>9.4f}  "
              f"{'PASS' if passed else 'fail'}")

    _cache = BASE / "data" / "full_hunt_series.parquet"
    if results:
        _com = sorted(set.union(*[set(v.index) for v in results.values()]))
        cache_frame = pd.DataFrame(
            {k: v.reindex(_com) for k, v in results.items()},
            index=pd.to_datetime(_com),
        )
        cache_frame.attrs["n_trials_attempted"] = n_trials
        cache_frame.attrs["candidate_identity_version"] = "all-params-v1"
        cache_frame.to_parquet(_cache)
        candidate_out, candidate_rows = write_candidates(cache_frame, n_trials)
        print(f"\n  series cached to {_cache.name} — re-analysis needs no re-run")
        print(f"  {len(candidate_rows)} discovery-screen candidates written to "
              f"{candidate_out.name}; universal ten-gate certification is required for shadow")
    if not survivors:
        print("""
  NOTHING PASSED THE ORIGINAL SCREEN, AND THAT IS THE MEASURED RESULT.

  No later or harsher discovery bar was consulted. The armed five remain the
  only thing standing; levers 1 and 3 below operate on them alone.""")

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
        print(f"\n  of {len(survivors)} original-screen candidates, {len(admitted)} "
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
        q, c, _d = q_for_dd(port, yrs, dd, shift)
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
