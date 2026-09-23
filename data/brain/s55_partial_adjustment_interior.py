"""BRAIN s55: give s54's P1 test power (interior argmax), and re-price it with R0762 fixed.

s54 found a* pinned at the grid EDGE (a=0.02) in every cost arm INCLUDING c=0, so
  P1 (a* decreasing in cost) had no power and the win was attributed to nothing.
Two changes, both of which can flip the s54 reading:

  1. GRID: extend below 0.02 to a=0.001 so the argmax can be INTERIOR. An argmax at the
     boundary is a censored measurement, never a result.
  2. COST INPUT: s54's own "real" arm used a plain median of the tape `spread` column --
     the exact R0762 defect s54 carded. On 7 FX symbols that median is 0.0, so the arm
     priced them FREE. Recompute the real arm from the NONZERO-bar median with a physical
     floor, and report both arms side by side: the delta IS R0762's cost in Sharpe.

Research-only: reads desk parquets, writes data/ only.
"""
import json
import pathlib
import re

import numpy as np
import pandas as pd

UNI = pathlib.Path("desks/mt5/data/universe")
OUT = pathlib.Path("data/brain_hunter_s55_partial_adjustment_interior.json")
CCY = {"EUR","USD","GBP","JPY","AUD","NZD","CAD","CHF","NOK","SEK","DKK","PLN","HUF","CZK",
       "TRY","ZAR","MXN","SGD","HKD","CNH"}
LAGS = [21, 63, 126, 252]
ALPHAS = [0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.10, 0.20, 0.35, 0.50, 0.75, 1.00]
COSTS_BP = [0.0, 1.0, 3.0, 10.0, 30.0]


def fx_symbols():
    out = []
    for p in sorted(UNI.glob("*_H1.parquet")):
        s = p.name[: -len("_H1.parquet")]
        if re.fullmatch(r"[A-Z]{6}", s) and s[:3] in CCY and s[3:] in CCY:
            out.append((s, p))
    return out


def daily_close(path):
    df = pd.read_parquet(path, columns=["close", "spread"])
    t = pd.to_datetime(df.index)
    gap = np.median(np.diff(t.values).astype("timedelta64[m]").astype(float))
    if gap > 120:
        return None
    s = pd.Series(df["close"].to_numpy(), index=t).groupby(lambda x: x.date()).last()
    s.index = pd.to_datetime(s.index)
    px_med = float(df["close"].median())
    digits = 3 if px_med > 20 else 5
    pt = 10.0 ** (-digits)
    sp = np.asarray(df["spread"], dtype=float)
    naive_pts = float(np.median(sp))                       # s54 / expand_universe.py:144
    nz = sp[sp > 0]
    fixed_pts = float(np.median(nz)) if nz.size else float("nan")   # R0762 fix
    zero_frac = float((sp <= 0).mean())
    to_bp = lambda pts: 0.5 * pts * pt / px_med * 1e4
    return s, to_bp(naive_pts), to_bp(fixed_pts), zero_frac, naive_pts, fixed_pts


def run():
    closes, naive, fixed, zfrac, raw = {}, {}, {}, {}, {}
    for s, p in fx_symbols():
        try:
            got = daily_close(p)
        except Exception:
            got = None
        if got is not None and len(got[0]) > 400:
            closes[s], naive[s], fixed[s], zfrac[s] = got[0], got[1], got[2], got[3]
            raw[s] = {"naive_pts": got[4], "nonzero_pts": got[5]}
    px = pd.DataFrame(closes).sort_index()
    ret = np.log(px).diff()
    vol = ret.rolling(60).std()

    res = {}
    for L in LAGS:
        sig = np.log(px).diff(L)
        target = np.sign(sig) / vol.replace(0, np.nan)
        target = target.div(target.abs().mean(axis=1), axis=0).shift(1)
        target = target.clip(-5, 5).fillna(0.0)
        for a in ALPHAS:
            pos = target.ewm(alpha=a, adjust=False).mean() if a < 1 else target
            turn = pos.diff().abs()
            gross = (pos.shift(1) * ret).sum(axis=1)
            arms = {f"c{c}": gross - (c * 1e-4) * turn.sum(axis=1) for c in COSTS_BP}
            for name, tbl in (("real_naive", naive), ("real_fixed", fixed)):
                hs = pd.Series(tbl).reindex(turn.columns).astype(float) * 1e-4
                arms[name] = gross - (turn * hs).sum(axis=1)
            for ck, pnl in arms.items():
                q = pnl.dropna()
                sh = float(q.mean() / q.std() * np.sqrt(252)) if q.std() > 0 else 0.0
                res.setdefault(ck, {}).setdefault(f"L{L}", {})[f"a{a}"] = round(sh, 4)

    summary = {ck: {Lk: max(d, key=d.get) for Lk, d in byL.items()} for ck, byL in res.items()}
    interior = {
        ck: {Lk: (am not in ("a0.001", "a1.0")) for Lk, am in byL.items()}
        for ck, byL in summary.items()
    }
    payload = {
        "n_symbols": len(closes), "days": int(len(px)),
        "start": str(px.index[0].date()), "end": str(px.index[-1].date()),
        "grid": {"lags": LAGS, "alphas": ALPHAS, "costs_bp": COSTS_BP},
        "half_spread_bp_naive": {k: round(v, 3) for k, v in sorted(naive.items())},
        "half_spread_bp_fixed": {k: round(v, 3) for k, v in sorted(fixed.items())},
        "spread_zero_fraction": {k: round(v, 4) for k, v in sorted(zfrac.items())},
        "spread_points_raw": raw,
        "sharpe": res, "argmax_alpha": summary, "argmax_is_interior": interior,
    }
    OUT.write_text(json.dumps(payload, indent=1))
    print(f"symbols={len(closes)} days={len(px)} {px.index[0].date()}..{px.index[-1].date()}")
    zeros = [k for k, v in naive.items() if v == 0.0]
    print(f"naive-zero-cost symbols ({len(zeros)}): {zeros}")
    for ck in res:
        print(ck, summary[ck], "interior:", interior[ck])


if __name__ == "__main__":
    run()
