"""placebo_test: machinery audit — does the hunt pipeline manufacture alpha from noise?

The SAME family (session range breakout) and the SAME gate (n>=60, t>2, PF>1.05,
maxDD>-30R, 2x cost stress) are run on bar-return-permutation null markets:
log-returns (and bar ranges) are shuffled in 4-bar blocks, destroying both
cross-day AND intraday serial dependence while preserving return/range
distributions and session hours.

Expected result if the machinery is honest: ~0-2 survivors across the whole battery,
consistent with family deflation (E[max of 8 iid normal] ~ 1.42). Many survivors
would mean the pipeline manufactures alpha from noise (selection bias, stop/target
asymmetry, spread assumptions).

AUDIT ONLY — never a gate, never rejects real candidates.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mt5desk import families  # noqa: E402
from mt5desk.engine import Costs, run_backtest  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"
N_REPS = 15
BLOCK_DAYS = 21
E_MAX_8 = 1.42  # expected max of 8 iid standard normals (2 syms x 4 windows)
GATE = dict(min_n=60, min_t=2.0, min_pf=1.05, min_dd=-30.0)
WINDOWS = {
    "asia": dict(range_start=7, wait_bars=12, rr=2.0, ttl_bars=12),
    "london_am": dict(range_start=10, range_end=13, signal_at=13, wait_bars=8, rr=2.0, ttl_bars=12),
    "ny_open": dict(range_start=13, range_end=14, signal_at=14, wait_bars=12, rr=2.0, ttl_bars=12),
    "afternoon": dict(range_start=14, range_end=17, signal_at=17, wait_bars=8, rr=2.0, ttl_bars=12),
}
BASE_COSTS = Costs(spread_per_lot=0.48, commission_per_lot=3.50, contract_oz=100)


def null_market(h1: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Bar-return permutation null (blocks of 4 bars): destroys BOTH cross-day and
    intraday serial dependence while preserving the distribution of returns and
    bar ranges (vol of the OHLC envelope). Rebuilds a synthetic OHLC path on the
    real index (hours/session structure preserved).

    NOTE: an earlier day-level permutation was WRONG for intraday mechanisms —
    shuffling whole days preserves intraday range->breakout continuation, so the
    same-day family still 'survived' on noise and produced false SUSPECT verdicts
    on the gold book and on AUDJPY non-asia windows. Bar-level permutation is the
    honest null: it removes the dependence the mechanism actually feeds on.
    """
    c = h1["close"].to_numpy(float)
    n = len(c)
    r = np.diff(np.log(c))                      # n-1 returns
    mid = (h1["high"].to_numpy(float) + h1["low"].to_numpy(float)) / 2
    hl = (h1["high"].to_numpy(float) - h1["low"].to_numpy(float)) / np.where(mid > 0, mid, 1.0)
    hl = hl[1:]                                 # n-1 ranges, aligned to the returns
    block = 4
    n_b = len(r) // block
    rp = r[: n_b * block].reshape(n_b, block)
    hp = hl[: n_b * block].reshape(n_b, block)
    order = rng.permutation(n_b)
    rp, hp = rp[order], hp[order]
    rs = rp.reshape(-1)
    hs = hp.reshape(-1)
    base = float(c[0])
    # path must have EXACTLY n rows (same index as h1); append the leftover tail
    # returns (0..3 bars) so lengths always match.
    path = np.empty(n)
    path[0] = base
    path[1 : n_b * block + 1] = base * np.exp(np.cumsum(rs))
    tail = r[n_b * block :]
    if len(tail):
        path[n_b * block + 1 :] = path[n_b * block] * np.exp(np.cumsum(tail))
    else:
        path[n_b * block + 1 :] = path[n_b * block]
    out = h1.copy()
    o = np.empty(n)
    o[0] = path[0]
    o[1:] = path[:-1]
    hs_full = np.concatenate([hs, [hs[-1] if len(hs) else 0.0] * (n - len(hs))])
    h = np.maximum(o, path) + hs_full * np.maximum(o, path)
    l = np.minimum(o, path) - hs_full * np.minimum(o, path)
    out["open"] = o
    out["close"] = path
    out["high"] = h
    out["low"] = l
    return out


def run_cell(h1: pd.DataFrame, win: str, p: dict, stress: float = 2.0) -> dict:
    sigs = families.family_session_range_breakout(h1, **p)
    res = run_backtest(h1, sigs, Costs(
        spread_per_lot=BASE_COSTS.spread_per_lot * stress,
        commission_per_lot=BASE_COSTS.commission_per_lot * stress,
        contract_oz=BASE_COSTS.contract_oz))
    return res.stats()


def passes(s: dict) -> bool:
    return (s["n"] >= GATE["min_n"] and s["t_stat"] > GATE["min_t"]
            and s["profit_factor"] > GATE["min_pf"] and s["max_dd_r"] > GATE["min_dd"]
            and s["expectancy_r"] > 0)


def main() -> int:
    rng = np.random.default_rng(20260817)
    rows = []
    syms = list(sys.argv[1:]) if len(sys.argv) > 1 else ["AUDCAD", "AUDJPY", "XAUUSD"]
    for sym in syms:
        fp = UNI / f"{sym}_H1.parquet"
        if not fp.exists():
            print(f"{sym}: no parquet, skipping", flush=True)
            continue
        h1 = families._h1(pd.read_parquet(fp))
        for rep in range(N_REPS):
            null = null_market(h1, rng)
            for win, p in WINDOWS.items():
                st = run_cell(null, win, p)
                st.update(sym=sym, win=win, rep=rep, survived=passes(st))
                rows.append(st)
    df = pd.DataFrame(rows)
    n_cells = len(df)
    surv = df[df.survived]
    by_win = surv.groupby(["sym", "win"]).size().to_dict()
    ts = df.groupby("rep").t_stat.max()
    out = {
        "cells_tested": int(n_cells),
        "reps": N_REPS,
        "survivors": int(len(surv)),
        "by_cell": {f"{k[0]}_{k[1]}": int(v) for k, v in by_win.items()},
        "max_t_per_rep": [round(float(x), 2) for x in ts],
        "mean_max_t": round(float(ts.mean()), 2),
        "e_max_8_benchmark": E_MAX_8,
        "max_survivor_exp_r": round(float(surv.expectancy_r.max()), 3) if len(surv) else None,
        "verdict": ("CLEAN" if len(surv) <= 2 else "SUSPECT"),
        "note": ("bar-return permutation null (blocks of 4), same family+gate, 2x costs; "
                 "destroys intraday AND cross-day dependence; expect ~0-2 survivors "
                 "if the machinery is honest"),
        "swept_at": datetime.now(timezone.utc).isoformat(),
    }
    text = (f"placebo pipeline audit: {n_cells} cells (2 syms x 4 windows x {N_REPS} reps)\n"
            f"  survivors from noise: {len(surv)}\n"
            f"  by cell: {by_win}\n"
            f"  max t per rep: {out['max_t_per_rep']}  mean {out['mean_max_t']}  "
            f"(E_max_8 = {E_MAX_8})\n"
            f"  VERDICT: {out['verdict']}\n"
            f"  {out['note']}")
    print(text, flush=True)
    (BASE / "reports" / "placebo_test.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")
    (BASE / "reports" / "DONE_placebo").write_text(
        datetime.now(timezone.utc).isoformat(), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())