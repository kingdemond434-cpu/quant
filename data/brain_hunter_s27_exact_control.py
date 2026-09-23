"""BRAIN HUNTER s27 (2026-08-29) -- the control was shuffled on the WRONG POPULATION.

s26 voided 26 of 55 cells as UNMEASURED because its size-matched control failed the
population guard, and named "a stratified shuffle within size bands" as the gating work.
That prescription is unnecessary. The defect is an ORDERING one, and it is exact:

  s26 permutes the labels of the cluster map (built on year Y-1's members), and only THEN
  hands the permuted map to the ruler, which restricts to symbols that have data in year Y
  and drops resulting singletons. A permutation preserves the label multiset on the map's
  OWN members -- but the ruler evaluates on a SUBSET of them, and the subset is not random
  with respect to the real labels. Restricting first and permuting second makes the control
  exactly size-matched BY CONSTRUCTION, so the population guard can never fire at any k.

This run measures three things per cell:
  real            the grouping's own mean |corr(group-relative rank, universe-wide rank)|
  control_pre     s26's ordering (permute the map, then restrict) -- kept to MEASURE the drift
  control_post    permute inside the ruler, after restriction -- exact, never voids

and extends k to 256 on ward/average, the range s25 and s26 could not report.

Run: .venv/bin/python data/brain_hunter_s27_exact_control.py
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
OUT = ROOT / "data/brain_hunter_s27_exact_control.json"

MIN_DAYS = 120
EVAL = (2024, 2025)
KS = [24, 48, 96, 128, 160, 192, 256]
METHODS = ["average", "ward", "complete"]
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


def cluster_year(panel: pd.DataFrame, est_year: int, k: int, method: str) -> dict[str, str]:
    """Point-in-time: year Y's clusters come from year Y-1 returns only. euclid metric
    (sqrt(2(1-corr))) throughout, because Ward is only meaningful on a Euclidean metric and
    s26 measured euclid == corr_d to <=0.001 on the linkages invariant to a monotone map."""
    sub = panel[panel.index.year == est_year]
    members = [c for c in sub.columns if sub[c].notna().sum() >= MIN_EST_DAYS]
    if len(members) < k + 2:
        return {}
    sub = sub[members].fillna(0.0)
    corr = np.nan_to_num(sub.corr().to_numpy(), nan=0.0)
    np.fill_diagonal(corr, 1.0)
    corr = np.clip(corr, -1.0, 1.0)
    dist = np.sqrt(np.clip(2.0 * (1.0 - corr), 0.0, None))
    dist = (dist + dist.T) / 2.0
    np.fill_diagonal(dist, 0.0)
    z = linkage(squareform(dist, checks=False), method=method)
    lab = fcluster(z, t=k, criterion="maxclust")
    return {s: f"c{int(v)}" for s, v in zip(members, lab, strict=True)}


def ruler(panel: pd.DataFrame, by_year: dict[str, dict[str, str]],
          rng: np.random.Generator | None = None) -> dict[str, float] | None:
    """s24b's ruler. If rng is given, labels are permuted AFTER member restriction and
    BEFORE the singleton drop -- the exact size-matched control (s27's whole point)."""
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
        lab_values = [g[s] for s in members]
        if rng is not None:
            rng.shuffle(lab_values)
        labels = pd.Series(lab_values, index=members)
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


def summarise(draws: list[dict[str, float]], real: dict[str, float],
              tol: float = 0.10) -> dict[str, object]:
    held = [d for d in draws if abs(d["n"] - real["n"]) <= tol * real["n"]]
    if len(held) < 3:
        drift = [round(d["n"] / real["n"] - 1.0, 3) for d in draws]
        return {"ceiling": None, "content": None, "z": None, "held": len(held),
                "status": f"UNMEASURED: {len(held)}/{len(draws)} controls held population",
                "n_drift": drift}
    vals = [d["mean_abs_corr"] for d in held]
    mu, sd = float(np.mean(vals)), float(np.std(vals, ddof=1))
    return {"ceiling": round(mu, 4), "content": round(mu - real["mean_abs_corr"], 4),
            "z": round((real["mean_abs_corr"] - mu) / sd, 1) if sd > 0 else None,
            "held": len(held), "status": "ok",
            "n_drift": [round(d["n"] / real["n"] - 1.0, 3) for d in draws]}


def main() -> None:
    panel = build_panel()
    eval_panel = panel[(panel.index.year >= EVAL[0]) & (panel.index.year <= EVAL[-1])]
    rows = []
    for method in METHODS:
        for k in KS:
            by_year = {}
            for y in range(EVAL[0], EVAL[-1] + 1):
                m = cluster_year(panel, y - 1, k, method)
                if m:
                    by_year[str(y)] = m
            if not by_year:
                continue
            real = ruler(eval_panel, by_year)
            if real is None:
                continue
            # control_pre: s26's ordering -- permute the MAP, then let the ruler restrict.
            rng_pre = np.random.default_rng(SEED)
            pre = []
            for _ in range(RANDOM_DRAWS):
                shuf: dict[str, dict[str, str]] = {}
                for yy, m in by_year.items():
                    lab = list(m.values())
                    rng_pre.shuffle(lab)
                    shuf[yy] = dict(zip(m.keys(), lab, strict=True))
                r = ruler(eval_panel, shuf)
                if r:
                    pre.append(r)
            # control_post: permute INSIDE the ruler, after restriction -- exact by construction.
            rng_post = np.random.default_rng(SEED)
            post = [r for r in (ruler(eval_panel, by_year, rng=rng_post)
                                for _ in range(RANDOM_DRAWS)) if r]
            rows.append({
                "method": method, "metric": "euclid", "k_requested": k,
                "k_effective": int(np.median([len(set(m.values())) for m in by_year.values()])),
                "n_symbols": real["n"], "coverage": real["coverage"],
                "median_group_size": real["median_group_size"],
                "mean_abs_corr": real["mean_abs_corr"],
                "control_pre": summarise(pre, real),
                "control_post": summarise(post, real),
            })
            p: dict[str, object] = rows[-1]["control_pre"]  # type: ignore[assignment]
            q: dict[str, object] = rows[-1]["control_post"]  # type: ignore[assignment]
            print(f"{method:9s} k={k:4d} n={real['n']:3d} cov={real['coverage']:.3f} "
                  f"real={real['mean_abs_corr']:.4f} | pre={p['content']} ({p['held']}/8) "
                  f"| post={q['content']} z={q['z']} ({q['held']}/8)", flush=True)
    OUT.write_text(json.dumps({
        "built_at": "2026-08-29", "built_by": "BRAIN HUNTER s27",
        "question": "s26 voided 26/55 cells as UNMEASURED -- is that a property of the "
                    "grouping, or of the ORDER in which the control shuffles and restricts?",
        "eval_years": list(EVAL), "random_draws": RANDOM_DRAWS, "seed": SEED,
        "estimation": "clusters for year Y from Y-1 daily log-return correlations only "
                       "(point-in-time)",
        "control_pre": "s26/s24b ordering: permute the cluster map, then restrict to the eval "
                       "year's members and drop singletons. Size-matched on the MAP, not on the "
                       "evaluated population.",
        "control_post": "s27 ordering: restrict to the eval year's members FIRST, then permute, "
                        "then drop singletons. Exactly size-matched on the evaluated population.",
        "rows": rows,
    }, indent=1) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
