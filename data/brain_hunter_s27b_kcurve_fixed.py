"""BRAIN HUNTER s27b (2026-08-29) -- the k-curve past 96, on a guard that cannot fire.

s27 established the mechanism that voided 26 of s26's 55 cells (and s25's k=128/160):
the population guard compared the UNION of symbols retained across eval years. Per-year
retention is EXACTLY size-matched under a label permutation and was never the problem --
measured at ward/k=128: real 179/180 per year, every shuffled draw also 179/180. But the
union is real 207 vs shuffled 229-235, because REAL SINGLETONS ARE THE SAME SYMBOLS EVERY
YEAR (a genuinely independent symbol is a loner in 2024 and again in 2025) while a shuffle
re-rolls which symbols land alone. The guard therefore fired UPWARD at every high-k cell --
144/144 draws drifted positive, never once negative -- and reported a property of ITSELF as
UNMEASURED evidence about the grouping.

Two consequences, and the second is the one that matters:
  1. The guard is replaced by the per-year population, which is exact by construction.
  2. Content is reported on a FIXED SET: the symbols the real grouping retains in EVERY
     eval year. Both arms then answer the identical question on the identical population,
     and the union artifact cannot enter the number at all.

`content_union` is kept beside it to show the size of the bias the old ruler carried.

Run: .venv/bin/python data/brain_hunter_s27b_kcurve_fixed.py
"""
from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd
from brain_hunter_s27_exact_control import EVAL, MIN_DAYS, build_panel, cluster_year

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data/brain_hunter_s27b_kcurve_fixed.json"

KS = [24, 48, 96, 128, 160, 192, 224]
METHODS = ["ward", "average", "complete"]
RANDOM_DRAWS = 8
SEED = 20260829


def rank_frames(ev: pd.DataFrame, by_year: dict[str, dict[str, str]],
                rng: np.random.Generator | None = None,
                ) -> tuple[pd.DataFrame | None, pd.DataFrame | None, dict[int, set[str]]]:
    """Returns (uw, gr, per_year_retained). Labels permuted after member restriction."""
    uw, gr, retained = [], [], {}
    for y in sorted(int(k) for k in by_year):
        g = by_year[str(y)]
        sub = ev[ev.index.year == y]
        mem = [s for s in sub.columns if s in g and sub[s].notna().any()]
        if len(mem) < 4:
            continue
        sub = sub[mem]
        lv = [g[s] for s in mem]
        if rng is not None:
            rng.shuffle(lv)
        lab = pd.Series(lv, index=mem)
        keep = lab.map(lab.value_counts()) >= 2
        mem = [s for s in mem if keep[s]]
        if len(mem) < 4:
            continue
        retained[y] = set(mem)
        sub, lab = sub[mem], lab[mem]
        uw.append(sub.rank(axis=1, pct=True))
        gr.append(sub.T.groupby(lab).rank(pct=True).T)
    if not uw:
        return None, None, {}
    return pd.concat(uw).sort_index(), pd.concat(gr).sort_index(), retained


def score(uw: pd.DataFrame, gr: pd.DataFrame, cols: list[str] | None) -> tuple[float, int]:
    cors = []
    for s in (cols if cols is not None else list(uw.columns)):
        if s not in uw.columns or s not in gr.columns:
            continue
        a, b = uw[s].dropna(), gr[s].dropna()
        idx = a.index.intersection(b.index)
        if len(idx) < MIN_DAYS or a[idx].std() == 0 or b[idx].std() == 0:
            continue
        cors.append(abs(float(a[idx].corr(b[idx]))))
    return (float(np.mean(cors)) if cors else float("nan")), len(cors)


def main() -> None:
    panel = build_panel()
    ev = panel[(panel.index.year >= EVAL[0]) & (panel.index.year <= EVAL[-1])]
    rows = []
    for method in METHODS:
        for k in KS:
            by_year = {}
            for y in range(EVAL[0], EVAL[-1] + 1):
                m = cluster_year(panel, y - 1, k, method)
                if m:
                    by_year[str(y)] = m
            if len(by_year) < 2:
                rows.append({"method": method, "k_requested": k, "status":
                             f"NOT RUN: only {len(by_year)} eval year(s) had >= k+2 members"})
                print(rows[-1], flush=True)
                continue
            uw, gr, ret = rank_frames(ev, by_year)
            if uw is None:
                continue
            fixed = sorted(set.intersection(*ret.values()))
            real_u, n_u = score(uw, gr, None)
            real_f, n_f = score(uw, gr, fixed)
            rng = np.random.default_rng(SEED)
            cu, cf, guard_ok, cov_f = [], [], True, []
            for _ in range(RANDOM_DRAWS):
                u2, g2, ret2 = rank_frames(ev, by_year, rng=rng)
                if u2 is None:
                    continue
                for y in ret:
                    if len(ret2.get(y, ())) != len(ret[y]):
                        guard_ok = False
                a, _ = score(u2, g2, None)
                b, nb = score(u2, g2, fixed)
                cu.append(a)
                cf.append(b)
                cov_f.append(nb / max(n_f, 1))
            mu_f, sd_f = float(np.mean(cf)), float(np.std(cf, ddof=1))
            mu_u = float(np.mean(cu))
            rows.append({
                "method": method, "metric": "euclid", "k_requested": k,
                "k_effective": int(np.median([len(set(m.values())) for m in by_year.values()])),
                "per_year_retained": {str(y): len(v) for y, v in ret.items()},
                "per_year_guard": "EXACT" if guard_ok else "BROKEN",
                "n_union": n_u, "n_fixed": n_f,
                "fixed_set_coverage_in_control": round(float(np.mean(cov_f)), 3),
                "real_union": round(real_u, 4), "control_union": round(mu_u, 4),
                "content_union": round(mu_u - real_u, 4),
                "real_fixed": round(real_f, 4), "control_fixed": round(mu_f, 4),
                "content_fixed": round(mu_f - real_f, 4),
                "z_fixed": round((real_f - mu_f) / sd_f, 1) if sd_f > 0 else None,
                "status": "ok",
            })
            r = rows[-1]
            print(f"{method:9s} k={k:4d} nfix={n_f:3d} nuni={n_u:3d} guard={r['per_year_guard']} "
                  f"| fixed {real_f:.4f} vs {mu_f:.4f} content={r['content_fixed']:+.4f} "
                  f"z={r['z_fixed']} | union content={r['content_union']:+.4f}", flush=True)
    OUT.write_text(json.dumps({
        "built_at": "2026-08-29", "built_by": "BRAIN HUNTER s27b",
        "question": "with a guard that cannot fire, where does the k-curve actually peak?",
        "eval_years": list(EVAL), "random_draws": RANDOM_DRAWS, "seed": SEED,
        "estimation": "clusters for year Y from Y-1 daily log-return correlations only "
                       "(point-in-time)",
        "guard": "per-year retained population, exact under a post-restriction label permutation",
        "fixed_set": "symbols the REAL grouping retains in EVERY eval year; both arms scored on it",
        "supersedes": "the k=128/160 UNMEASURED cells of s25 and s26 (union-guard artifact)",
        "rows": rows,
    }, indent=1) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
