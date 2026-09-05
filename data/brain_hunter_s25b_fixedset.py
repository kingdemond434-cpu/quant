"""BRAIN HUNTER s25b -- the falsifier for s25's k-curve (L1.7).

s25's |corr| falls monotonically in k, but so does the POPULATION: singleton clusters are dropped
(a group of one has no peers), so k=160 scores 145 symbols and k=8 scores 248. If the symbols that
survive to high k are systematically the easy ones, the curve is a selection artifact, not a
grouping improvement. Control: score every k on the SAME fixed symbol set (those present at every
k), real and random alike.

Run: .venv/bin/python data/brain_hunter_s25b_fixedset.py
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from brain_hunter_s25_kcurve import (  # noqa: E402
    EVAL, MIN_DAYS, RANDOM_DRAWS, SEED, build_panel, cluster_year,
)

OUT = pathlib.Path(__file__).resolve().parents[1] / "data/brain_hunter_s25b_fixedset.json"
KS = [8, 24, 48, 64, 96, 128, 160]


def per_symbol(panel: pd.DataFrame, by_year: dict[str, dict[str, str]]) -> dict[str, float]:
    uw_parts, gr_parts = [], []
    for y in sorted({int(k) for k in by_year}):
        g = by_year.get(str(y))
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
    if not uw_parts:
        return {}
    uw, gr = pd.concat(uw_parts).sort_index(), pd.concat(gr_parts).sort_index()
    out = {}
    for s in uw.columns:
        a, b = uw[s].dropna(), gr[s].dropna()
        idx = a.index.intersection(b.index)
        if len(idx) < MIN_DAYS or a[idx].std() == 0 or b[idx].std() == 0:
            continue
        out[s] = abs(float(a[idx].corr(b[idx])))
    return out


def main() -> None:
    panel = build_panel()
    ev = panel[(panel.index.year >= EVAL[0]) & (panel.index.year <= EVAL[-1])]
    rng = np.random.default_rng(SEED)
    maps, reals = {}, {}
    for k in KS:
        by = {}
        for y in range(EVAL[0], EVAL[-1] + 1):
            m = cluster_year(panel, y - 1, k)
            if m:
                by[str(y)] = m
        maps[k] = by
        reals[k] = per_symbol(ev, by)
    common = set.intersection(*(set(v) for v in reals.values()))
    rows = []
    for k in KS:
        real = float(np.mean([reals[k][s] for s in common]))
        draws = []
        for _ in range(RANDOM_DRAWS):
            shuf = {}
            for y, m in maps[k].items():
                labels = list(m.values())
                rng.shuffle(labels)
                shuf[y] = dict(zip(m.keys(), labels))
            d = per_symbol(ev, shuf)
            got = [d[s] for s in common if s in d]
            if len(got) > 0.9 * len(common):   # else: control UNMEASURED at this k, never "clean"
                draws.append(float(np.mean(got)))
        mu, sd = float(np.mean(draws)), float(np.std(draws, ddof=1))
        rows.append({"k": k, "n_common": len(common), "mean_abs_corr": round(real, 4),
                     "random_ceiling": (None if np.isnan(mu) else round(mu, 4)), "content": (None if np.isnan(mu) else round(mu - real, 4)),
                     "z": round((real - mu) / sd, 1) if sd > 0 else None,
                     "all_symbol_n": len(reals[k])})
        print(rows[-1], flush=True)
    OUT.write_text(json.dumps({"built_at": "2026-08-29", "built_by": "BRAIN HUNTER s25b",
                               "common_symbols": sorted(common), "rows": rows}, indent=1, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
