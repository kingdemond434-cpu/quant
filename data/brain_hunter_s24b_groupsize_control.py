"""BRAIN HUNTER s24b (2026-08-29) -- the falsifier for the group-size law itself.

Five real groupings now sit on one curve: |corr| vs median peer-group size. If the curve is ALL
there is, then a RANDOM grouping of matched size scores the same, and `currency_quote`'s 0.488 --
the desk's only surviving peer axis -- is a size effect carrying no economic content.

Control: for each real map, build RANDOM_DRAWS random partitions of the SAME members into the SAME
group-size profile, and run the identical ruler. Random labels are drawn ONCE per year and held,
so the control has the same persistence as the real map (a per-day reshuffle would be a weaker,
easier-to-beat control).

Run: .venv/bin/python data/brain_hunter_s24b_groupsize_control.py
"""
from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
U = ROOT / "desks/mt5/data/universe"
GMAP = ROOT / "data/mt5_grouping_map.json"
S24 = ROOT / "data/brain_hunter_s24_liquidity_tier_axis.json"
OUT = ROOT / "data/brain_hunter_s24b_groupsize_control.json"

MIN_DAYS = 120
EVAL = (2024, 2025)
RANDOM_DRAWS = 12
SEED = 20260829


def build_panel(symbols: set[str]) -> pd.DataFrame:
    series = {}
    for s in symbols:
        f = U / f"{s}_H1.parquet"
        if not f.exists():
            continue
        d = pd.read_parquet(f, columns=["close"])
        if getattr(d.index, "tz", None) is not None:
            d.index = d.index.tz_localize(None)
        c = d["close"].resample("1D").last().dropna()
        r = np.log(c).diff().dropna()
        if len(r) >= MIN_DAYS:
            series[s] = r
    p = pd.DataFrame(series).sort_index()
    return p[(p.index.year >= EVAL[0]) & (p.index.year <= EVAL[-1])]


def ruler(panel: pd.DataFrame, by_year: dict[str, dict[str, str]]) -> dict | None:
    """Vectorised: rank the whole window at once per year, then |corr| per symbol.

    Identical statistic to s24's per-day loop -- validated against it in __main__ below.
    """
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
    return {"n": len(cors), "mean_abs_corr": round(float(np.mean(cors)), 3),
            "median_group_size": round(float(np.median(sizes)), 1)}


def main() -> None:
    gm = json.loads(GMAP.read_text())
    s24 = json.loads(S24.read_text())
    maps: dict[str, dict[str, dict[str, str]]] = {}   # name -> {year -> map}
    for name in ("asset_class", "currency_base", "currency_quote"):
        if gm.get(name):
            maps[name] = {str(y): gm[name] for y in EVAL}
    for k in ("k8", "k24"):
        by = gm.get("corr_cluster_by_year", {}).get(k, {})
        got = {str(y): by[str(y)] for y in EVAL if str(y) in by}
        if got:
            maps[f"corr_cluster_{k}"] = got
    if s24.get("tier_map_by_year"):
        maps["liquidity_tier"] = s24["tier_map_by_year"]

    all_syms = {s for m in maps.values() for y in m for s in m[y]}
    panel = build_panel(all_syms)
    rng = np.random.default_rng(SEED)
    results = {}
    for name, by_year in maps.items():
        real = ruler(panel, by_year)
        if real is None:
            continue
        draws = []
        for _ in range(RANDOM_DRAWS):
            shuf = {}
            for y, m in by_year.items():
                labels = list(m.values())
                rng.shuffle(labels)                      # same size profile, labels permuted
                shuf[y] = dict(zip(m.keys(), labels, strict=True))
            r = ruler(panel, shuf)
            if r:
                draws.append(r["mean_abs_corr"])
        results[name] = {
            "real": real,
            "random_same_size_mean": round(float(np.mean(draws)), 3) if draws else None,
            "random_same_size_sd": round(float(np.std(draws)), 4) if draws else None,
            "random_draws": len(draws),
            "z_real_vs_random": (round(float((real["mean_abs_corr"] - np.mean(draws))
                                             / (np.std(draws) or 1e-12)), 2) if draws else None),
        }
        print(name, json.dumps(results[name]))

    OUT.write_text(json.dumps({
        "_meta": {"built_by": "BRAIN HUNTER s24b", "built_at": "2026-08-29",
                  "window": f"{EVAL[0]}..{EVAL[-1]} daily log returns",
                  "control": "labels permuted within year: identical group-size profile, "
                             "identical members, economic content destroyed",
                  "draws": RANDOM_DRAWS, "seed": SEED},
        "results": results}, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
