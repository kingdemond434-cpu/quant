"""s57: AQR Alternative Thinking 2025-2 ("The Hidden Value of Streaky Returns") on MT5 ground.

MECHANISM (mined from data/external/aqr/pdftext/the-hidden-value-of-streaky-returns-in-stock-
portfolios.txt, readable only after the R0769 extractor fix): the STREAKINESS of a return stream
-- measured by its variance ratio VR(q) = Var(q-period sum)/(q*Var(1-period)) -- is a complexity
risk the marketplace COMPENSATES. AQR report high-VR long-short equity factors earning ~2x the
long-run Sharpe of low-VR factors.

PREDICTED SIGN, DECLARED BEFORE MEASUREMENT (s29 lesson): POSITIVE. Streams with high VR in the
formation window earn HIGHER Sharpe in the disjoint evaluation window.

TAUTOLOGY CONTROL (s55 lesson): VR of a TSMOM return stream is mechanically high exactly when
trend-following works on that symbol, so an IN-SAMPLE VR-vs-Sharpe fit is circular. VR is
therefore measured on the FIRST half of each symbol's history and Sharpe on the SECOND half,
with no overlap. A second arm measures both in-sample as the circularity positive control:
if the disjoint arm is null and the in-sample arm is strong, the AQR result is a same-window
artifact on this ground.

Gross returns; no cost model claimed (s54: the desk's cost model is one number and zero on
seven symbols). This is a SCREEN, not a candidate: no gate, no card, no forward clock.
"""
import json
import pathlib

import numpy as np
import pandas as pd
from scipy import stats

UNIV = pathlib.Path("desks/mt5/data/universe")
OUT = pathlib.Path("data/brain_hunter_s57_streakiness_screen.json")
LOOKBACKS = (24, 72, 168, 336)   # H1 bars: 1d, 3d, 1w, 2w
VR_Q = 20                        # variance-ratio horizon, in return periods


def variance_ratio(r: np.ndarray, q: int) -> float:
    r = r[np.isfinite(r)]
    if len(r) < 10 * q:
        return np.nan
    v1 = np.var(r, ddof=1)
    n = (len(r) // q) * q
    vq = np.var(r[:n].reshape(-1, q).sum(axis=1), ddof=1)
    return float(vq / (q * v1)) if v1 > 0 else np.nan


def sharpe(r: np.ndarray) -> float:
    r = r[np.isfinite(r)]
    if len(r) < 200 or np.std(r, ddof=1) == 0:
        return np.nan
    return float(np.mean(r) / np.std(r, ddof=1) * np.sqrt(24 * 252))


def main() -> None:
    rows = []
    for p in sorted(UNIV.glob("*_H1.parquet")):
        sym = p.stem[:-3]
        try:
            df = pd.read_parquet(p, columns=["close"])
        except Exception:
            continue
        c = df["close"].astype(float)
        if len(c) < 4000:
            continue
        ret = np.log(c).diff()
        for lb in LOOKBACKS:
            sig = np.sign(np.log(c).diff(lb)).shift(1)          # TSMOM, no lookahead
            pnl = (sig * ret).to_numpy()
            h = len(pnl) // 2
            rows.append({
                "symbol": sym, "lookback": lb, "n": int(len(pnl)),
                "vr_first": variance_ratio(pnl[:h], VR_Q),
                "sharpe_second": sharpe(pnl[h:]),
                "vr_full": variance_ratio(pnl, VR_Q),
                "sharpe_full": sharpe(pnl),
            })
    df = pd.DataFrame(rows)
    res = {"n_cells": int(len(df)), "vr_q": VR_Q, "lookbacks": list(LOOKBACKS),
           "predicted_sign": "positive", "arms": {}}
    for name, xk, yk in (("disjoint_vr_first_sharpe_second", "vr_first", "sharpe_second"),
                         ("circularity_control_full_full", "vr_full", "sharpe_full")):
        sub = df[[xk, yk, "lookback"]].dropna()
        rho, p = stats.spearmanr(sub[xk], sub[yk])
        per_lb = {}
        for lb, g in sub.groupby("lookback"):
            r_, p_ = stats.spearmanr(g[xk], g[yk])
            per_lb[int(lb)] = {"n": int(len(g)), "spearman": round(float(r_), 4),
                               "p": float(p_)}
        # AQR's own framing: top vs bottom tercile mean Sharpe
        qs = sub[xk].quantile([1 / 3, 2 / 3]).to_numpy()
        lo = sub[sub[xk] <= qs[0]][yk]
        hi = sub[sub[xk] >= qs[1]][yk]
        t, pt = stats.ttest_ind(hi, lo, equal_var=False)
        res["arms"][name] = {
            "n": int(len(sub)), "spearman": round(float(rho), 4), "p": float(p),
            "per_lookback": per_lb,
            "tercile_hi_mean_sharpe": round(float(hi.mean()), 4),
            "tercile_lo_mean_sharpe": round(float(lo.mean()), 4),
            "tercile_welch_t": round(float(t), 3), "tercile_p": float(pt),
        }
    OUT.write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()


def control() -> None:
    """Decisive control: does VR_first predict Sharpe_second BEYOND Sharpe_first?

    A symbol dominated by bid-ask bounce has low VR AND bad TSMOM Sharpe in BOTH halves, so the
    headline correlation could be pure persistence of symbol quality rather than the AQR
    complexity premium. Partial Spearman of (VR_first, Sharpe_second) controlling Sharpe_first.
    """
    rows = []
    for p in sorted(UNIV.glob("*_H1.parquet")):
        try:
            c = pd.read_parquet(p, columns=["close"])["close"].astype(float)
        except Exception:
            continue
        if len(c) < 4000:
            continue
        ret = np.log(c).diff()
        for lb in LOOKBACKS:
            pnl = (np.sign(np.log(c).diff(lb)).shift(1) * ret).to_numpy()
            h = len(pnl) // 2
            rows.append({"lookback": lb, "vr_first": variance_ratio(pnl[:h], VR_Q),
                         "sharpe_first": sharpe(pnl[:h]), "sharpe_second": sharpe(pnl[h:]),
                         "lag1_ac": float(pd.Series(ret).autocorr(1))})
    df = pd.DataFrame(rows).dropna()
    out = {}

    def partial(x, y, z):
        rx = stats.rankdata(x); ry = stats.rankdata(y); rz = stats.rankdata(z)
        ex = rx - np.poly1d(np.polyfit(rz, rx, 1))(rz)
        ey = ry - np.poly1d(np.polyfit(rz, ry, 1))(rz)
        r, p = stats.pearsonr(ex, ey)
        return round(float(r), 4), float(p)

    out["raw_vr_first_vs_sharpe_second"] = [round(float(v), 4) for v in
                                            stats.spearmanr(df.vr_first, df.sharpe_second)]
    out["sharpe_first_vs_sharpe_second"] = [round(float(v), 4) for v in
                                            stats.spearmanr(df.sharpe_first, df.sharpe_second)]
    out["vr_first_vs_sharpe_first"] = [round(float(v), 4) for v in
                                       stats.spearmanr(df.vr_first, df.sharpe_first)]
    out["partial_vr_controlling_sharpe_first"] = partial(
        df.vr_first, df.sharpe_second, df.sharpe_first)
    out["vr_first_vs_lag1_autocorr"] = [round(float(v), 4) for v in
                                        stats.spearmanr(df.vr_first, df.lag1_ac)]
    out["partial_vr_controlling_lag1_ac"] = partial(df.vr_first, df.sharpe_second, df.lag1_ac)
    out["n"] = int(len(df))
    pathlib.Path("data/brain_hunter_s57_streakiness_control.json").write_text(
        json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
