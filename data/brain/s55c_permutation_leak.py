"""BRAIN s55c: a time-permutation control is NOT null-preserving under a long-memory smoother.

s55b's shuffle control (sign permuted in time per symbol) BEAT the real momentum signal in
16/16 cells, at z down to -38. That is not a refutation of momentum; it is a LEAK in the
control. Permuting a sign column preserves its FULL-SAMPLE MEAN. Smoothing at a=0.001
(halflife ~693d) turns the position into approximately that full-sample mean -- i.e. an
in-sample oracle on each symbol's drift direction, available from bar 1.

The proof is a second control whose full-sample mean is ~0 by construction:

  PERM   sign permuted in time            -- preserves per-symbol mean sign  (leaky)
  IID    i.i.d. +-1 draws, p=0.5          -- mean sign ~ 0                   (clean)
  MEAN   constant = the symbol's full-sample mean sign (the leak, stated explicitly)

Prediction: PERM ~ MEAN >> IID ~ 0 at a=0.001, and all three collapse toward 0 as a -> 1.
If it holds, any desk control that permutes a signal in time while the policy smooths it is
measuring a lookahead, and the s55b refutation of TSMOM is void.
"""
import json
import pathlib
import re

import numpy as np
import pandas as pd

UNI = pathlib.Path("desks/mt5/data/universe")
OUT = pathlib.Path("data/brain_hunter_s55c_permutation_leak.json")
CCY = {"EUR","USD","GBP","JPY","AUD","NZD","CAD","CHF","NOK","SEK","DKK","PLN","HUF","CZK",
       "TRY","ZAR","MXN","SGD","HKD","CNH"}
ALPHAS = [0.001, 0.01, 0.1, 1.0]
L = 63
N = 12


def run():
    closes = {}
    for p in sorted(UNI.glob("*_H1.parquet")):
        s = p.name[: -len("_H1.parquet")]
        if not (re.fullmatch(r"[A-Z]{6}", s) and s[:3] in CCY and s[3:] in CCY):
            continue
        df = pd.read_parquet(p, columns=["close"])
        t = pd.to_datetime(df.index)
        if np.median(np.diff(t.values).astype("timedelta64[m]").astype(float)) > 120:
            continue
        c = pd.Series(df["close"].to_numpy(), index=t).groupby(lambda x: x.date()).last()
        c.index = pd.to_datetime(c.index)
        if len(c) > 400:
            closes[s] = c
    px = pd.DataFrame(closes).sort_index()
    ret = np.log(px).diff()
    inv = 1.0 / ret.rolling(60).std().replace(0, np.nan)
    sgn = np.sign(np.log(px).diff(L))

    def book(sd):
        t = sd * inv
        return t.div(t.abs().mean(axis=1), axis=0).shift(1).clip(-5, 5).fillna(0.0)

    def sharpe(pos):
        q = (pos.shift(1) * ret).sum(axis=1).dropna()
        return float(q.mean() / q.std() * np.sqrt(252)) if q.std() > 0 else 0.0

    rng = np.random.default_rng(20260903)
    mean_sign = sgn.mean()  # the leak, stated
    res = {"mean_sign_per_symbol": {k: round(float(v), 4) for k, v in mean_sign.items()}}
    for a in ALPHAS:
        sm = (lambda t: t.ewm(alpha=a, adjust=False).mean()) if a < 1 else (lambda t: t)
        perm, iid = [], []
        for _ in range(N):
            perm.append(sharpe(sm(book(sgn.apply(
                lambda c: pd.Series(rng.permutation(c.to_numpy()), index=c.index))))))
            iid.append(sharpe(sm(book(pd.DataFrame(
                rng.choice([-1.0, 1.0], size=sgn.shape), index=sgn.index, columns=sgn.columns)
                .where(sgn.notna()))))) 
        const = pd.DataFrame(np.tile(np.sign(mean_sign.to_numpy()), (len(sgn), 1)),
                             index=sgn.index, columns=sgn.columns).where(sgn.notna())
        res[f"a{a}"] = {
            "signal": round(sharpe(sm(book(sgn))), 4),
            "perm_mean": round(float(np.mean(perm)), 4), "perm_sd": round(float(np.std(perm, ddof=1)), 4),
            "iid_mean": round(float(np.mean(iid)), 4), "iid_sd": round(float(np.std(iid, ddof=1)), 4),
            "full_sample_mean_sign_oracle": round(sharpe(sm(book(const))), 4),
        }
        print(a, res[f"a{a}"], flush=True)
    payload = {"n_symbols": len(closes), "days": int(len(px)), "lag": L, "n_draws": N,
               "seed": 20260903, "gross_only": True, "results": res}
    OUT.write_text(json.dumps(payload, indent=1))


if __name__ == "__main__":
    run()
