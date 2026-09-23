"""BRAIN s55b: is the a->0 win the momentum SIGNAL, or a near-static exposure?

s55 found the partial-adjustment argmax runs away to the new grid floor a=0.001 at EVERY
cost including c=0. At a=0.001 the EWM halflife is ~693 days on an 8,318-day sample, so the
"optimal" policy is nearly a CONSTANT position. Three controls decide what is being paid for:

  SIGNAL   sign(mom_L)      -- the s54/s55 arm
  SHUFFLE  sign permuted in time per symbol (seeded) -- keeps the marginal, destroys timing
  ALWAYS   sign replaced by +1 -- pure vol-scaled static long

If SHUFFLE/ALWAYS reproduce the SIGNAL Sharpe at a=0.001, the a->0 win is a static exposure
and the GP/partial-adjustment reading of s54 is void.
"""
import json
import pathlib
import re

import numpy as np
import pandas as pd

UNI = pathlib.Path("desks/mt5/data/universe")
OUT = pathlib.Path("data/brain_hunter_s55b_static_control.json")
CCY = {"EUR","USD","GBP","JPY","AUD","NZD","CAD","CHF","NOK","SEK","DKK","PLN","HUF","CZK",
       "TRY","ZAR","MXN","SGD","HKD","CNH"}
LAGS = [21, 63, 126, 252]
ALPHAS = [0.001, 0.01, 0.1, 1.0]
N_SHUFFLE = 20


def daily_close(path):
    df = pd.read_parquet(path, columns=["close"])
    t = pd.to_datetime(df.index)
    if np.median(np.diff(t.values).astype("timedelta64[m]").astype(float)) > 120:
        return None
    s = pd.Series(df["close"].to_numpy(), index=t).groupby(lambda x: x.date()).last()
    s.index = pd.to_datetime(s.index)
    return s


def sharpe(p):
    q = p.dropna()
    return float(q.mean() / q.std() * np.sqrt(252)) if q.std() > 0 else 0.0


def run():
    closes = {}
    for p in sorted(UNI.glob("*_H1.parquet")):
        s = p.name[: -len("_H1.parquet")]
        if not (re.fullmatch(r"[A-Z]{6}", s) and s[:3] in CCY and s[3:] in CCY):
            continue
        try:
            c = daily_close(p)
        except Exception:
            c = None
        if c is not None and len(c) > 400:
            closes[s] = c
    px = pd.DataFrame(closes).sort_index()
    ret = np.log(px).diff()
    vol = ret.rolling(60).std()
    inv = (1.0 / vol.replace(0, np.nan))

    def book(sign_df):
        t = (sign_df * inv)
        t = t.div(t.abs().mean(axis=1), axis=0).shift(1).clip(-5, 5).fillna(0.0)
        return t

    res = {}
    rng = np.random.default_rng(20260903)
    for L in LAGS:
        sgn = np.sign(np.log(px).diff(L))
        arms = {"signal": book(sgn), "always": book(pd.DataFrame(1.0, index=px.index, columns=px.columns))}
        shuffles = []
        for _ in range(N_SHUFFLE):
            perm = sgn.apply(lambda col: pd.Series(rng.permutation(col.to_numpy()), index=col.index))
            shuffles.append(book(perm))
        for a in ALPHAS:
            for name, tgt in arms.items():
                pos = tgt.ewm(alpha=a, adjust=False).mean() if a < 1 else tgt
                res.setdefault(f"L{L}", {}).setdefault(f"a{a}", {})[name] = round(
                    sharpe((pos.shift(1) * ret).sum(axis=1)), 4)
            sh = [sharpe(((t.ewm(alpha=a, adjust=False).mean() if a < 1 else t).shift(1) * ret).sum(axis=1))
                  for t in shuffles]
            res[f"L{L}"][f"a{a}"]["shuffle_mean"] = round(float(np.mean(sh)), 4)
            res[f"L{L}"][f"a{a}"]["shuffle_sd"] = round(float(np.std(sh, ddof=1)), 4)
            z = (res[f"L{L}"][f"a{a}"]["signal"] - np.mean(sh)) / (np.std(sh, ddof=1) or np.nan)
            res[f"L{L}"][f"a{a}"]["signal_z_vs_shuffle"] = round(float(z), 3)

    payload = {"n_symbols": len(closes), "days": int(len(px)),
               "start": str(px.index[0].date()), "end": str(px.index[-1].date()),
               "n_shuffle": N_SHUFFLE, "seed": 20260903, "gross_only": True, "sharpe": res}
    OUT.write_text(json.dumps(payload, indent=1))
    for L in res:
        for a in res[L]:
            r = res[L][a]
            print(L, a, "signal", r["signal"], "shuffle", r["shuffle_mean"], "+-", r["shuffle_sd"],
                  "always", r["always"], "z", r["signal_z_vs_shuffle"])


if __name__ == "__main__":
    run()
