"""Model what the related markets DON'T explain, then ask if the leftover pays.

    XAU_t = b1*XAG_t + b2*USD_t + b3*RISK_t + eps_t

and eps is the object of interest. This is the "residual trading" layer of a
statistical-alpha stack and it is also the XAU/XAG relative-value sleeve, which
is the same computation seen from two directions: a hedge ratio and a spread.

FOUR THINGS THAT WOULD MAKE THIS A LIE, AND WHAT IS DONE ABOUT EACH

1. FULL-SAMPLE BETAS. Regressing the whole history and calling the residual a
   signal is lookahead of the purest kind -- the beta that defines "unexplained"
   was fitted on the very move being called unexplained. Betas here are rolling
   and estimated STRICTLY on bars before the one they price.

2. A z-SCORE THAT KNOWS THE FUTURE. The residual's mean and sigma are rolling
   and lagged for the same reason.

3. AN EDGE MEASURED IN SIGMA AND SPENT IN DOLLARS. A residual signal is worth
   nothing until it beats the round trip. Every horizon is reported against the
   break-even information coefficient, cost / (0.7979 * sigma_h), computed from
   the desk's own corrected Costs. That number killed sub-15-minute gold order
   flow before any data was bought, and it applies here unchanged.

4. NO CONTROL. A residual will always look interesting to someone who wants it
   to. `--shuffle` reruns the whole pipeline with the residual's dates permuted:
   any IC that survives THAT is measuring the harness, not the market.

Usage:
    python residual_alpha.py                 # XAUUSD on silver + USD + risk
    python residual_alpha.py --target EURUSD
    python residual_alpha.py --shuffle       # the null control
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk.engine import Costs                                # noqa: E402

UNI = _DESK / "data" / "universe"
OUT = _DESK / "reports" / "residual_alpha.json"

# USD basket legs, signed so that +1 means "USD stronger".
USD_LEGS = {"EURUSD": -1, "GBPUSD": -1, "AUDUSD": -1, "NZDUSD": -1,
            "USDJPY": +1, "USDCHF": +1, "USDCAD": +1}
RISK_LEGS = {"AUDJPY": +1, "NZDJPY": +1}      # carry/risk-appetite proxy
BETA_WIN = 500        # bars of history the hedge ratios are fitted on
Z_WIN = 500           # bars the residual's own mean/sigma are measured over
HORIZONS = (1, 4, 12, 24)


def _load(sym: str) -> pd.Series:
    df = pd.read_parquet(UNI / f"{sym}_H1.parquet")
    df.index = pd.DatetimeIndex(pd.to_datetime(df.index))
    return np.log(pd.Series(df["close"].to_numpy(), index=df.index)).diff()


def _panel(target: str) -> pd.DataFrame:
    cols = {target: _load(target)}
    have = {p.stem.replace("_H1", "") for p in UNI.glob("*_H1.parquet")}
    if target != "XAGUSD" and "XAGUSD" in have:
        cols["XAG"] = _load("XAGUSD")
    usd = [s * _load(k) for k, s in USD_LEGS.items() if k in have and k != target]
    if usd:
        cols["USD"] = pd.concat(usd, axis=1, sort=False).mean(axis=1)
    risk = [s * _load(k) for k, s in RISK_LEGS.items() if k in have and k != target]
    if risk:
        cols["RISK"] = pd.concat(risk, axis=1, sort=False).mean(axis=1)
    return pd.DataFrame(cols).dropna()


def rolling_residual(panel: pd.DataFrame, target: str,
                     win: int = BETA_WIN) -> pd.Series:
    """eps_t = y_t - x_t . beta(t), beta fitted on [t-win, t-1] ONLY.

    The loop is deliberate rather than a vectorised trick: the whole point is
    that bar t is priced by a model that has not seen bar t, and that is easier
    to verify by eye in a loop than in a stack of shifted matrices.
    """
    y = panel[target].to_numpy()
    X = panel.drop(columns=[target]).to_numpy()
    n, k = X.shape
    eps = np.full(n, np.nan)
    for t in range(win, n):
        xs, ys = X[t - win:t], y[t - win:t]
        xs = np.column_stack([np.ones(win), xs])
        try:
            beta, *_ = np.linalg.lstsq(xs, ys, rcond=None)
        except np.linalg.LinAlgError:
            continue
        eps[t] = y[t] - float(beta[0] + X[t] @ beta[1:])
    return pd.Series(eps, index=panel.index, name="eps")


def evaluate(target: str, shuffle: bool = False, seed: int = 0) -> dict:
    panel = _panel(target)
    if panel.shape[1] < 2 or len(panel) < BETA_WIN + Z_WIN + max(HORIZONS) + 50:
        raise SystemExit(f"{target}: not enough overlapping history")
    eps = rolling_residual(panel, target)
    if shuffle:
        v = eps.to_numpy().copy()
        ok = ~np.isnan(v)
        rng = np.random.default_rng(seed)
        vals = v[ok]
        rng.shuffle(vals)
        v[ok] = vals
        eps = pd.Series(v, index=eps.index, name="eps")

    mu = eps.rolling(Z_WIN).mean().shift(1)
    sd = eps.rolling(Z_WIN).std().shift(1)
    z = ((eps - mu) / sd).replace([np.inf, -np.inf], np.nan)

    ret = panel[target]
    sig_h1 = float(ret.std())
    meta = json.loads((UNI / "universe.json").read_text("utf-8"))[target]
    costs = Costs.from_symbol(meta, mult=2.0)
    # cost as a fraction of price: per-oz round trip / price level
    px = float(pd.read_parquet(UNI / f"{target}_H1.parquet")["close"].iloc[-1])
    cost_frac = (costs.per_oz_roundtrip() / costs.contract_oz) / px

    rows = []
    for h in HORIZONS:
        fwd = ret.rolling(h).sum().shift(-h)
        d = pd.concat([z, fwd], axis=1).dropna()
        d.columns = ["z", "fwd"]
        if len(d) < 500:
            continue
        ic = float(d["z"].corr(d["fwd"], method="spearman"))
        pear = float(d["z"].corr(d["fwd"]))
        sigma_h = sig_h1 * np.sqrt(h)
        ic_min = cost_frac / (0.7979 * sigma_h)
        # sign convention: mean reversion means a HIGH residual predicts a LOW
        # forward return, i.e. negative IC. Report both the raw number and the
        # tradeable |IC| so the direction is never quietly flipped to taste.
        # TAIL-CONDITIONAL EDGE. An unconditional IC averages over every bar,
        # including the ~85% where the residual is unremarkable and no
        # relative-value trader would have a position. A spread strategy is
        # DEFINED by its tail entry, so the number that decides it is the mean
        # forward return after |z| crosses the threshold -- signed by the side
        # the rule would take -- against the round trip in the same units.
        tails = {}
        for thr in (1.5, 2.0, 2.5):
            hit = d[d["z"].abs() >= thr]
            if len(hit) < 100:
                continue
            # fade the residual: short it when rich, long it when cheap
            pnl_all = -np.sign(hit["z"].to_numpy()) * hit["fwd"].to_numpy()
            gross = float(pnl_all.mean())

            # NON-OVERLAPPING t. An h-bar forward return sampled every bar shares
            # h-1 bars with its neighbour, so n counts the same move up to h
            # times and the naive t is inflated by roughly sqrt(h). At h=4 that
            # is a factor of two -- large enough to turn noise into a finding,
            # and this desk has shipped that error before. Keep only hits
            # separated by at least h bars, which costs sample size and buys a
            # t that means what it says. The single-position engine could not
            # have taken the discarded ones anyway.
            pos = np.flatnonzero(d["z"].abs().to_numpy() >= thr)
            keep, last = [], -10 ** 9
            for p in pos:
                if p - last >= h:
                    keep.append(p)
                    last = p
            zk = d["z"].to_numpy()[keep]
            fk = d["fwd"].to_numpy()[keep]
            pnl = -np.sign(zk) * fk
            g_ind = float(pnl.mean()) if len(pnl) else 0.0
            se = float(pnl.std(ddof=1) / np.sqrt(len(pnl))) if len(pnl) > 1 else 0.0
            tails[f"z>={thr}"] = {
                "n_overlapping": int(len(hit)),
                "n_independent": int(len(pnl)),
                "gross_per_trade": round(g_ind, 6),
                "net_per_trade": round(g_ind - cost_frac, 6),
                "t_gross": round(g_ind / se, 2) if se > 0 else 0.0,
                "t_naive_overlapping": round(
                    float(gross / (pnl_all.std(ddof=1) / np.sqrt(len(pnl_all)))), 2)
                if len(pnl_all) > 1 and pnl_all.std(ddof=1) > 0 else 0.0,
                "clears_cost": bool(g_ind > cost_frac),
            }
        rows.append({
            "horizon_bars": h, "n": len(d),
            "spearman_ic": round(ic, 5), "pearson_ic": round(pear, 5),
            "sigma_h": round(float(sigma_h), 6),
            "break_even_ic": round(float(ic_min), 5),
            "clears": bool(abs(ic) > ic_min),
            "direction": "mean-reverting" if ic < 0 else "continuing",
            "tail_conditional": tails,
        })
    return {"target": target, "regressors": [c for c in panel.columns if c != target],
            "bars": len(panel), "beta_window": BETA_WIN, "z_window": Z_WIN,
            "cost_frac_of_price": round(float(cost_frac), 8),
            "shuffled_control": shuffle, "rows": rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="XAUUSD")
    ap.add_argument("--shuffle", action="store_true",
                    help="permute the residual: the null the real run must beat")
    args = ap.parse_args()
    res = evaluate(args.target, shuffle=args.shuffle)
    tag = "  [SHUFFLED CONTROL]" if args.shuffle else ""
    print(f"RESIDUAL ALPHA  {res['target']} ~ {' + '.join(res['regressors'])}{tag}")
    print(f"  {res['bars']} bars, betas on {BETA_WIN}, z on {Z_WIN}")
    print(f"  round trip = {res['cost_frac_of_price']:.6f} of price\n")
    print(f"{'h':>4}{'n':>8}{'IC':>10}{'break-even':>12}{'verdict':>12}  direction")
    for r in res["rows"]:
        v = "CLEARS" if r["clears"] else "below cost"
        print(f"{r['horizon_bars']:>4}{r['n']:>8}{r['spearman_ic']:>10.4f}"
              f"{r['break_even_ic']:>12.4f}{v:>12}  {r['direction']}")
    print("\nTAIL-CONDITIONAL (fade the residual once |z| crosses the threshold)")
    print(f"{'h':>4}{'gate':>10}{'n_ind':>7}{'gross':>11}"
          f"{'net':>11}{'t':>7}{'t_naive':>9}")
    for r in res["rows"]:
        for gate, t in r["tail_conditional"].items():
            mark = "  <-- CLEARS" if t["clears_cost"] else ""
            print(f"{r['horizon_bars']:>4}{gate:>10}{t['n_independent']:>7}"
                  f"{t['gross_per_trade']:>11.6f}"
                  f"{t['net_per_trade']:>11.6f}{t['t_gross']:>7.2f}"
                  f"{t['t_naive_overlapping']:>9.2f}{mark}")
    print("  t = non-overlapping;  t_naive = the inflated one, shown so the gap"
          " is visible")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    prev = json.loads(OUT.read_text("utf-8")) if OUT.exists() else {}
    prev[("shuffled_" if args.shuffle else "") + res["target"]] = res
    OUT.write_text(json.dumps(prev, indent=1), "utf-8")
    print(f"\nwritten: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
