"""regime_discovery: unsupervised latent-regime challenger (REGIME_DISCOVERY LAB).

Machine-discovered states from market features X ONLY (never future P&L).
K-Means (numpy, Lloyd) over z-scored daily features, fitted inside the training
fold only; CLUSTER_STABILITY measured (silhouette, transition matrix, expected
duration, bootstrap assignment agreement, OOS size match). Then the latent state
is used as a PERMISSION FILTER, not a predictor: cluster-conditional expectancy
of the session-range-breakout family on that symbol.

Genealogy note: every K/feature variant is part of the strategy's genealogy
(multiplicity is not inflated by this file — it only reports evidence).

Usage: python regime_discovery.py [SYM ...]
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
REPORTS = BASE / "reports"
SESSIONS = {"asia": (0, 6), "london_am": (7, 12), "ny_open": (13, 15), "afternoon": (16, 23)}


def daily_features(h1: pd.DataFrame) -> pd.DataFrame:
    o = h1["open"].to_numpy(float)
    h = h1["high"].to_numpy(float)
    l = h1["low"].to_numpy(float)
    c = h1["close"].to_numpy(float)
    r = np.diff(np.log(c))
    ar = np.abs(r)
    days = pd.Series(c, index=h1.index).resample("D")
    d_c = days.last()
    d_o = pd.Series(o, index=h1.index).resample("D").first()
    d_h = pd.Series(h, index=h1.index).resample("D").max()
    d_l = pd.Series(l, index=h1.index).resample("D").min()
    dr = np.log(d_c).diff()
    rng = (d_h - d_l).replace(0, np.nan)
    atr = rng.ffill().rolling(14).mean()
    df = pd.DataFrame({
        "realized_vol": pd.Series(r, index=h1.index[1:]).resample("D").std() * np.sqrt(24),
        "range_eff": (d_c - d_o) / rng,
        "trend_strength": dr.abs() / atr,
        "direction_persist": np.sign(dr.dropna()).rolling(21).apply(
            lambda s: np.corrcoef(s[:-1], s[1:])[0, 1] if len(s) > 5 and s.std() > 0 else np.nan),
        "skew": pd.Series(r, index=h1.index[1:]).resample("D").apply(lambda x: pd.Series(x).skew()),
        "jump_intensity": pd.Series(ar, index=h1.index[1:]).resample("D").apply(
            lambda x: float((x > 4.0 * (x.std() + 1e-12)).mean())),
        "spread_proxy": ((d_h - d_l) / d_c).replace(0, np.nan),
        "ny_share": pd.Series(ar, index=h1.index[1:]).resample("D").apply(lambda x: 0.0),
    })
    hours = h1.index.hour
    ars = pd.Series(ar, index=h1.index[1:])
    ny_mask = hours.to_numpy()[1:] >= 13
    ny_sum = ars[ny_mask].resample("D").sum()
    day_sum = ars.resample("D").sum()
    df["ny_share"] = ny_sum / day_sum.replace(0, np.nan)
    return df.replace([np.inf, -np.inf], np.nan).dropna()


def kmeans(X: np.ndarray, k: int, iters: int = 30, seed: int = 7) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    n = len(X)
    idx = rng.choice(n, k, replace=False)
    cen = X[idx].copy()
    for _ in range(iters):
        d = np.linalg.norm(X[:, None, :] - cen[None, :, :], axis=2)
        lab = np.argmin(d, axis=1)
        new = np.array([X[lab == i].mean(axis=0) if np.any(lab == i) else cen[i] for i in range(k)])
        if np.allclose(new, cen, atol=1e-9):
            break
        cen = new
    return lab, cen


def silhouette(X: np.ndarray, lab: np.ndarray) -> float:
    n = len(X)
    if n < 4 or len(set(lab)) < 2:
        return float("nan")
    tot = 0.0
    cnt = 0
    for i in range(0, n, 251):
        chunk = range(i, min(i + 251, n))
        for j in chunk:
            own = X[lab == lab[j]]
            a = float(np.linalg.norm(own - X[j]).mean()) if len(own) > 1 else 0.0
            bs = []
            for kk in set(lab):
                if kk == lab[j]:
                    continue
                bs.append(float(np.linalg.norm(X[lab == kk] - X[j]).mean()))
            b = min(bs) if bs else a
            denom = max(a, b)
            tot += (b - a) / denom if denom > 0 else 0.0
            cnt += 1
    return float(tot / max(cnt, 1))


def bootstrap_agreement(X: np.ndarray, lab: np.ndarray, k: int, seeds: int = 5) -> float:
    n = len(X)
    agree = []
    for s in range(seeds):
        rng = np.random.default_rng(s)
        idx = rng.choice(n, n, replace=True)
        l2, _ = kmeans(X[idx], k, seed=s)
        lf = np.full(n, -1)
        lf[idx] = l2
        good = lf[lf >= 0]
        orig = lab[lf >= 0]
        if len(good) < 50:
            continue
        pr = np.random.default_rng(1).choice(len(good), (2000, 2), replace=True)
        same = ((good[pr[:, 0]] == good[pr[:, 1]]) == (orig[pr[:, 0]] == orig[pr[:, 1]])).mean()
        agree.append(float(same))
    return float(np.mean(agree)) if agree else float("nan")


def transition_stats(lab: np.ndarray) -> dict:
    k = lab.max() + 1
    T = np.zeros((k, k))
    for a, b in zip(lab[:-1], lab[1:]):
        T[a, b] += 1
    row = T.sum(axis=1, keepdims=True)
    P = T / np.where(row > 0, row, 1.0)
    stay = [float(P[i, i]) for i in range(k)]
    dur = [float(1.0 / (1.0 - P[i, i])) if P[i, i] < 1.0 else float("inf") for i in range(k)]
    return {"transition_matrix": [[round(float(x), 3) for x in r] for r in P],
            "expected_duration_days": [round(x, 1) if x != float("inf") else None for x in dur]}


def main() -> int:
    syms = list(sys.argv[1:]) if len(sys.argv) > 1 else ["XAUUSD", "AUDCAD", "AUDJPY", "EURUSD"]
    meta = json.loads((UNI / "universe.json").read_text("utf-8"))
    out: dict[str, dict] = {}
    for sym in syms:
        fp = UNI / f"{sym}_H1.parquet"
        if not fp.exists():
            print(f"{sym}: no parquet, skip", flush=True)
            continue
        h1 = families._h1(pd.read_parquet(fp))
        feats = daily_features(h1)
        if len(feats) < 400:
            print(f"{sym}: only {len(feats)} days, skip", flush=True)
            continue
        X = feats.to_numpy(float)
        n = len(X)
        split = int(n * 0.7)
        Xtr, Xte = X[:split], X[split:]
        mu, sd = Xtr.mean(axis=0), Xtr.std(axis=0)
        Ztr = (Xtr - mu) / np.where(sd > 0, sd, 1.0)
        Zte = (Xte - mu) / np.where(sd > 0, sd, 1.0)
        best = None
        for k in range(2, 7):
            lab, cen = kmeans(Ztr, k)
            sil = silhouette(Ztr, lab)
            if best is None or (sil == sil and sil > best[0]):
                best = (sil, k, lab, cen)
        sil, k, lab, cen = best
        boot = bootstrap_agreement(Ztr, lab, k)
        ts = transition_stats(lab)
        lab_te, _ = kmeans(Zte, k) if False else (None, None)
        d = np.linalg.norm(Zte[:, None, :] - cen[None, :, :], axis=2)
        lab_te = np.argmin(d, axis=1)
        te_size = np.bincount(lab_te, minlength=k).tolist()
        tr_size = np.bincount(lab, minlength=k).tolist()
        oos_match = float(np.corrcoef(tr_size, te_size)[0, 1]) if len(set(tr_size)) > 1 and len(set(te_size)) > 1 else float("nan")
        day_idx = feats.index.to_numpy()
        full_lab = np.full(len(feats), -1)
        full_lab[:split] = lab
        full_lab[split:] = lab_te
        sigs_all = families.family_session_range_breakout(
            h1, range_start=10, range_end=13, signal_at=13, wait_bars=8, rr=2.0, ttl_bars=12)
        m = meta.get(sym, {})
        costs = Costs(spread_per_lot=0.48 if sym == "XAUUSD" else max(
            m.get("median_spread_pts", 1) * m.get("tick_size", 1e-5) * m.get("contract_size", 1e5), 0.05),
            commission_per_lot=3.50, contract_oz=m.get("contract_size", 1e5))
        cells = {}
        for cl in range(k):
            days = {pd.Timestamp(d).date() for d in day_idx[full_lab == cl]}
            sub = [s for s in sigs_all if pd.Timestamp(s.time).date() in days]
            if len(sub) >= 30:
                st = run_backtest(h1, sub, costs).stats()
                cells[cl] = {"n": st["n"], "exp_r": round(st["expectancy_r"], 3),
                             "t": round(st["t_stat"], 2), "pf": round(st["profit_factor"], 2)}
            else:
                cells[cl] = {"n": len(sub), "exp_r": None, "t": None, "pf": None}
        out[sym] = {
            "k": k, "silhouette": round(sil, 3), "bootstrap_agreement": round(boot, 3),
            "oos_size_corr": round(oos_match, 3) if oos_match == oos_match else None,
            "train_size": tr_size, "oos_size": te_size,
            "expected_duration_days": ts["expected_duration_days"],
            "features": list(feats.columns),
            "centroids_z": [[round(float(x), 2) for x in row] for row in cen],
            "cluster_conditional_exp": cells,
            "note": "K-Means on daily X-features (fit on 70% fold); cluster-conditional exp "
                    "of session-range-breakout on the SAME symbol = permission-filter evidence",
            "swept_at": datetime.now(timezone.utc).isoformat(),
        }
        print(f"{sym}: k={k} sil={out[sym]['silhouette']} boot={out[sym]['bootstrap_agreement']} "
              f"cells={cells}", flush=True)
    (REPORTS / "latent_regimes.json").write_text(json.dumps(out, indent=2, default=str),
                                                 encoding="utf-8")
    print("latent_regimes.json written", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())