"""BRAIN HUNTER s25 (2026-08-29) -- where does the correlation-cluster grouping STOP improving?

s24b established: independence (low |corr| between a group-relative rank and the universe-wide
rank) = a group-size CEILING minus the economic content of the labels. `corr_cluster k24` carried
the largest content term of any map measured (0.678 vs a 0.895 size-matched random ceiling), and
nobody has asked where the curve stops. This sweeps k = 8..96 point-in-time (clusters for year Y
estimated on Y-1 returns only, s11's convention), runs the SAME ruler as s24b, and runs the SAME
size-matched random control at every k so a fall in |corr| driven purely by smaller groups is
never read as content.

Run: .venv/bin/python data/brain_hunter_s25_kcurve.py
"""
from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

ROOT = pathlib.Path(__file__).resolve().parents[1]
U = ROOT / "desks/mt5/data/universe"
OUT = ROOT / "data/brain_hunter_s25_kcurve.json"

MIN_DAYS = 120
EVAL = (2024, 2025)
KS = [8, 12, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160]
RANDOM_DRAWS = 12
SEED = 20260829
MIN_EST_DAYS = 100


def build_panel() -> pd.DataFrame:
    series = {}
    for f in sorted(U.glob("*_H1.parquet")):
        s = f.name[:-len("_H1.parquet")]
        d = pd.read_parquet(f, columns=["close"])
        if getattr(d.index, "tz", None) is not None:
            d.index = d.index.tz_localize(None)
        c = d["close"].resample("1D").last().dropna()
        r = np.log(c).diff().dropna()
        if len(r) >= MIN_DAYS:
            series[s] = r
    return pd.DataFrame(series).sort_index()


def cluster_year(panel: pd.DataFrame, est_year: int, k: int) -> dict[str, str]:
    """Point-in-time: labels for year est_year+1, estimated ONLY on est_year returns."""
    sub = panel[panel.index.year == est_year]
    members = [c for c in sub.columns if sub[c].notna().sum() >= MIN_EST_DAYS]
    if len(members) < k + 2:
        return {}
    sub = sub[members].fillna(0.0)
    corr = sub.corr().to_numpy()
    corr = np.nan_to_num(corr, nan=0.0)
    np.fill_diagonal(corr, 1.0)
    dist = np.clip(1.0 - corr, 0.0, 2.0)
    dist = (dist + dist.T) / 2.0
    np.fill_diagonal(dist, 0.0)
    z = linkage(squareform(dist, checks=False), method="average")
    lab = fcluster(z, t=k, criterion="maxclust")
    return {s: f"c{int(v)}" for s, v in zip(members, lab)}


def ruler(panel: pd.DataFrame, by_year: dict[str, dict[str, str]]) -> dict | None:
    """Identical statistic to s24b's ruler (validated there against s24's per-day loop)."""
    uw_parts, gr_parts, sizes = [], [], []
    for y in sorted({int(k) for k in by_year}):
        g = by_year.get(str(y))
        if not g:
            continue
        sub = panel[panel.index.year == y]
        members = [s for s in sub.columns if s in g and sub[s].notna().any()]
        if len(members) < 4:
            continue
        sub = sub[members]
        labels = pd.Series([g[s] for s in members], index=members)
        keep = labels.map(labels.value_counts()) >= 2
        members = [s for s in members if keep[s]]
        if len(members) < 4:
            continue
        sub, labels = sub[members], labels[members]
        uw_parts.append(sub.rank(axis=1, pct=True))
        gr_parts.append(sub.T.groupby(labels).rank(pct=True).T)
        sizes.append(float(labels.value_counts().median()))
    if not uw_parts:
        return None
    uw = pd.concat(uw_parts).sort_index()
    gr = pd.concat(gr_parts).sort_index()
    cors = []
    for s in uw.columns:
        a, b = uw[s].dropna(), gr[s].dropna()
        idx = a.index.intersection(b.index)
        if len(idx) < MIN_DAYS or a[idx].std() == 0 or b[idx].std() == 0:
            continue
        cors.append(abs(float(a[idx].corr(b[idx]))))
    if not cors:
        return None
    return {"n": len(cors), "mean_abs_corr": round(float(np.mean(cors)), 4),
            "median_group_size": round(float(np.median(sizes)), 1)}


def main() -> None:
    panel = build_panel()
    eval_panel = panel[(panel.index.year >= EVAL[0]) & (panel.index.year <= EVAL[-1])]
    rng = np.random.default_rng(SEED)
    rows = []
    for k in KS:
        by_year = {}
        for y in range(EVAL[0], EVAL[-1] + 1):
            m = cluster_year(panel, y - 1, k)
            if m:
                by_year[str(y)] = m
        real = ruler(eval_panel, by_year)
        if real is None:
            continue
        draws = []
        for _ in range(RANDOM_DRAWS):
            shuf = {}
            for y, m in by_year.items():
                labels = list(m.values())
                rng.shuffle(labels)
                shuf[y] = dict(zip(m.keys(), labels))
            r = ruler(eval_panel, shuf)
            if r:
                draws.append(r["mean_abs_corr"])
        mu, sd = float(np.mean(draws)), float(np.std(draws, ddof=1))
        rows.append({
            "k_requested": k,
            "k_effective": int(np.median([len(set(m.values())) for m in by_year.values()])),
            "n_symbols": real["n"],
            "median_group_size": real["median_group_size"],
            "mean_abs_corr": real["mean_abs_corr"],
            "random_ceiling": round(mu, 4),
            "random_sd": round(sd, 4),
            "content": round(mu - real["mean_abs_corr"], 4),
            "z": round((real["mean_abs_corr"] - mu) / sd, 1) if sd > 0 else None,
        })
        print(rows[-1], flush=True)
    OUT.write_text(json.dumps({
        "built_at": "2026-08-29", "built_by": "BRAIN HUNTER s25",
        "eval_years": list(EVAL), "random_draws": RANDOM_DRAWS, "seed": SEED,
        "estimation": "clusters for year Y from Y-1 daily log-return correlations only (point-in-time)",
        "linkage": "average, distance = 1 - corr", "rows": rows,
    }, indent=1) + "\n")


if __name__ == "__main__":
    main()
