"""BRAIN HUNTER s26 (2026-08-29) -- the LINKAGE and METRIC axis, never swept.

s25 measured the k-curve for correlation clustering and chose k=96 as the operating point,
because content keeps rising past it while COVERAGE collapses (86% at k=96 -> 58% at k=160):
more and more symbols become singletons and singletons have no peers. s25's own next-ground
item 2 named the suspicion: that collapse is a property of AVERAGE LINKAGE on `1 - corr`, the
one method every cluster number on this desk has ever used. A linkage that splits the central
blob instead of shaving singletons off it would push the operating point past k=96 WITHOUT the
coverage cost that decided against k=128.

This sweeps method x metric x k with s24b's ruler and s24b's size-matched random control at
every cell, and reports COVERAGE as a first-class column beside content -- the two are the
trade s25 could only see along one axis.

Metrics:
  corr_d   d = 1 - corr                    (the desk's convention, all prior numbers)
  euclid   d = sqrt(2 * (1 - corr))        (a true Euclidean metric; Ward is only meaningful here)
  lw       d = sqrt(2 * (1 - corr_shrunk)) (Ledoit-Wolf shrunk correlation, n_obs ~ 250 vs p ~ 240
                                            so the sample correlation is near-singular by construction)

Run: .venv/bin/python data/brain_hunter_s26_linkage.py
"""
from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from sklearn.covariance import ledoit_wolf

ROOT = pathlib.Path(__file__).resolve().parents[1]
U = ROOT / "desks/mt5/data/universe"
OUT = ROOT / "data/brain_hunter_s26_linkage.json"

MIN_DAYS = 120
EVAL = (2024, 2025)
KS = [24, 48, 96, 128, 160]
METHODS = ["average", "ward", "complete", "single"]
METRICS = ["corr_d", "euclid", "lw"]
RANDOM_DRAWS = 8
SEED = 20260829
MIN_EST_DAYS = 100


def build_panel() -> pd.DataFrame:
    series = {}
    for f in sorted(U.glob("*_H1.parquet")):
        s = f.name[: -len("_H1.parquet")]
        d = pd.read_parquet(f, columns=["close"])
        if getattr(d.index, "tz", None) is not None:
            d.index = d.index.tz_localize(None)
        c = d["close"].resample("1D").last().dropna()
        r = np.log(c).diff().dropna()
        if len(r) >= MIN_DAYS:
            series[s] = r
    return pd.DataFrame(series).sort_index()


def _corr(sub: pd.DataFrame, metric: str) -> np.ndarray:
    if metric == "lw":
        cov, _ = ledoit_wolf(sub.to_numpy(), assume_centered=False)
        sd = np.sqrt(np.diag(cov))
        sd[sd == 0] = 1.0
        corr = cov / np.outer(sd, sd)
    else:
        corr = sub.corr().to_numpy()
    corr = np.nan_to_num(corr, nan=0.0)
    np.fill_diagonal(corr, 1.0)
    return np.clip(corr, -1.0, 1.0)


def cluster_year(panel: pd.DataFrame, est_year: int, k: int, method: str, metric: str) -> dict[str, str]:
    sub = panel[panel.index.year == est_year]
    members = [c for c in sub.columns if sub[c].notna().sum() >= MIN_EST_DAYS]
    if len(members) < k + 2:
        return {}
    sub = sub[members].fillna(0.0)
    corr = _corr(sub, metric)
    dist = (1.0 - corr) if metric == "corr_d" else np.sqrt(np.clip(2.0 * (1.0 - corr), 0.0, None))
    dist = (dist + dist.T) / 2.0
    np.fill_diagonal(dist, 0.0)
    z = linkage(squareform(dist, checks=False), method=method)
    lab = fcluster(z, t=k, criterion="maxclust")
    return {s: f"c{int(v)}" for s, v in zip(members, lab)}


def ruler(panel: pd.DataFrame, by_year: dict[str, dict[str, str]]) -> dict | None:
    """s24b's ruler, verbatim, plus coverage (share of members retained after singleton drop)."""
    uw_parts, gr_parts, sizes, cov = [], [], [], []
    for y in sorted({int(k) for k in by_year}):
        g = by_year.get(str(y))
        if not g:
            continue
        sub = panel[panel.index.year == y]
        members = [s for s in sub.columns if s in g and sub[s].notna().any()]
        if len(members) < 4:
            continue
        n0 = len(members)
        sub = sub[members]
        labels = pd.Series([g[s] for s in members], index=members)
        keep = labels.map(labels.value_counts()) >= 2
        members = [s for s in members if keep[s]]
        if len(members) < 4:
            continue
        cov.append(len(members) / n0)
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
            "median_group_size": round(float(np.median(sizes)), 1),
            "coverage": round(float(np.mean(cov)), 3)}


def main() -> None:
    panel = build_panel()
    eval_panel = panel[(panel.index.year >= EVAL[0]) & (panel.index.year <= EVAL[-1])]
    rng = np.random.default_rng(SEED)
    rows = []
    for metric in METRICS:
        for method in METHODS:
            if method == "ward" and metric == "corr_d":
                continue  # Ward is only defined on a Euclidean metric; 1-corr is not one.
            for k in KS:
                by_year = {}
                for y in range(EVAL[0], EVAL[-1] + 1):
                    m = cluster_year(panel, y - 1, k, method, metric)
                    if m:
                        by_year[str(y)] = m
                if not by_year:
                    continue
                real = ruler(eval_panel, by_year)
                if real is None:
                    continue
                draws = []
                for _ in range(RANDOM_DRAWS):
                    shuf = {}
                    for y, m in by_year.items():
                        lab = list(m.values())
                        rng.shuffle(lab)
                        shuf[y] = dict(zip(m.keys(), lab))
                    r = ruler(eval_panel, shuf)
                    if r and abs(r["n"] - real["n"]) <= 0.10 * real["n"]:
                        draws.append(r["mean_abs_corr"])
                if len(draws) >= 3:
                    mu = float(np.mean(draws))
                    sd = float(np.std(draws, ddof=1))
                    content, ceiling, status = round(mu - real["mean_abs_corr"], 4), round(mu, 4), "ok"
                    zs = round((real["mean_abs_corr"] - mu) / sd, 1) if sd > 0 else None
                else:
                    content = ceiling = zs = None
                    status = f"UNMEASURED: only {len(draws)}/{RANDOM_DRAWS} controls held population"
                rows.append({
                    "metric": metric, "method": method, "k_requested": k,
                    "k_effective": int(np.median([len(set(m.values())) for m in by_year.values()])),
                    "n_symbols": real["n"], "coverage": real["coverage"],
                    "median_group_size": real["median_group_size"],
                    "mean_abs_corr": real["mean_abs_corr"],
                    "random_ceiling": ceiling, "content": content, "z": zs,
                    "control_status": status,
                })
                print(rows[-1], flush=True)
    OUT.write_text(json.dumps({
        "built_at": "2026-08-29", "built_by": "BRAIN HUNTER s26",
        "question": "is the high-k coverage collapse a property of average linkage on 1-corr?",
        "eval_years": list(EVAL), "random_draws": RANDOM_DRAWS, "seed": SEED,
        "estimation": "clusters for year Y from Y-1 daily log-return correlations only (point-in-time)",
        "ruler": "s24b mean |corr(group-relative pct rank, universe-wide pct rank)|, "
                 "size-matched label-shuffle control, control voided if population moves >10%",
        "rows": rows,
    }, indent=1) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
