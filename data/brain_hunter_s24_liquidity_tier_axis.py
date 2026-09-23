"""BRAIN HUNTER s24 (2026-08-29) -- s23's NEXT-GROUND item 1.

Two questions, one script:

  A. Is the registry's `median_spread_pts` (a WHOLE-HISTORY median, which s23's cost tiering
     consumed) a usable cost estimate?  The H1 tape carries a per-bar `spread` column, so the
     statistic is auditable: measure the zero-fraction by era and rebuild the median on a
     TRAILING window only.
  B. s11's ruler on the resulting liquidity tier: does a tier `group_rank` decorrelate from
     universe-wide rank by more than `currency_quote`'s 0.493?  Tiers for year Y are assigned
     from year Y-1 spreads only -- a whole-sample tier map would be lookahead by construction.

Run: .venv/bin/python data/brain_hunter_s24_liquidity_tier_axis.py
"""
from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
U = ROOT / "desks/mt5/data/universe"
OUT = ROOT / "data/brain_hunter_s24_liquidity_tier_axis.json"
GMAP = ROOT / "data/mt5_grouping_map.json"

MIN_DAYS = 120        # s11's per-year overlap bar, reused unchanged
N_TIERS = 4           # s23's tiering, so the comparison is like-for-like
MIN_GROUP = 2
EVAL_YEARS = (2024, 2025)


def load(sym: str) -> pd.DataFrame | None:
    f = U / f"{sym}_H1.parquet"
    if not f.exists():
        return None
    d = pd.read_parquet(f, columns=["close", "spread"])
    if getattr(d.index, "tz", None) is not None:
        d.index = d.index.tz_localize(None)   # +00:00 is a LABEL not a clock (recorded lesson)
    return d


def main() -> None:
    univ = json.loads((U / "universe.json").read_text())
    era: dict[str, dict] = {}
    yearly_spread: dict[str, dict[int, float]] = {}
    px_by_year: dict[str, dict[int, float]] = {}
    rets: dict[str, pd.Series] = {}

    for s in univ:
        d = load(s)
        if d is None or d.empty:
            continue
        sp = d["spread"]
        z = sp == 0
        zf_year = z.groupby(d.index.year).mean()
        yearly_spread[s] = {
            int(y): float(g[g > 0].median())
            for y, g in sp.groupby(d.index.year) if (g > 0).sum() >= 100
        }
        px_by_year[s] = {int(y): float(g.median()) for y, g in d["close"].groupby(d.index.year)}
        era[s] = {
            "zero_frac_all": round(float(z.mean()), 4),
            "median_all": float(sp.median()),
            "median_nonzero_all": (float(sp[~z].median()) if (~z).any() else None),
            "registry_median_spread_pts": univ[s].get("median_spread_pts"),
            "first_year_zero_free": (int(zf_year[zf_year < 0.05].index.min())
                                     if (zf_year < 0.05).any() else None),
        }
        c = d["close"].resample("1D").last().dropna()
        r = np.log(c).diff().dropna()
        if len(r) >= MIN_DAYS:
            rets[s] = r

    # ---- A. how badly does the whole-history median misprice the recent tape? -----------------
    digits = {s: univ[s].get("digits") for s in univ}

    def bps(sym: str, pts: float | None, year: int) -> float | None:
        dg, px = digits.get(sym), px_by_year.get(sym, {}).get(year)
        if pts is None or dg is None or not px or px <= 0:
            return None
        return pts * (10.0 ** -dg) / px * 1e4

    ref_year = 2025
    cmp_rows = []
    for s in era:
        reg = era[s]["registry_median_spread_pts"]
        tr = yearly_spread.get(s, {}).get(ref_year)
        a, b = bps(s, reg, ref_year), bps(s, tr, ref_year)
        if a is None or b is None:
            continue
        cmp_rows.append({"symbol": s, "registry_bps": a, "trailing_bps": b,
                         "ratio": (b / a) if a > 0 else None,
                         "zero_frac_all": era[s]["zero_frac_all"]})
    understated = [r for r in cmp_rows if r["registry_bps"] == 0.0 or (r["ratio"] or 0) > 1.5]

    # ---- B. point-in-time tier map, then s11's ruler ------------------------------------------
    tier_map_by_year: dict[str, dict[str, str]] = {}
    for y in EVAL_YEARS:
        prev = {s: v[y - 1] for s, v in yearly_spread.items() if (y - 1) in v}
        prev_bps = {s: bps(s, p, y - 1) for s, p in prev.items()}
        prev_bps = {s: v for s, v in prev_bps.items() if v is not None and v > 0}
        if len(prev_bps) < N_TIERS * MIN_GROUP:
            continue
        order = sorted(prev_bps, key=prev_bps.get)
        m = {s: f"L{1 + i * N_TIERS // len(order)}" for i, s in enumerate(order)}
        tier_map_by_year[str(y)] = m

    panel = pd.DataFrame(dict(rets)).sort_index()
    panel = panel[(panel.index.year >= EVAL_YEARS[0]) & (panel.index.year <= EVAL_YEARS[-1])]

    def ruler(get_group) -> dict | None:
        """|corr| between within-group rank and universe-wide rank, per symbol, over the window."""
        gr_all, uw_all = {}, {}
        for day, row in panel.iterrows():
            g = get_group(day.year)
            if not g:
                continue
            v = row.dropna()
            v = v[[s for s in v.index if s in g]]
            if len(v) < 4:
                continue
            uw = v.rank(pct=True)
            gr = v.groupby([g[s] for s in v.index]).rank(pct=True)
            for s in v.index:
                uw_all.setdefault(s, []).append((day, uw[s]))
                gr_all.setdefault(s, []).append((day, gr[s]))
        cors, sizes = [], []
        for s in gr_all:
            a = pd.Series(dict(uw_all[s]))
            b = pd.Series(dict(gr_all[s]))
            if len(a) < MIN_DAYS or b.std() == 0 or a.std() == 0:
                continue
            cors.append(abs(float(a.corr(b))))
        if not cors:
            return None
        # median peer-group size, the axis s11 found independence tracks
        for day, row in panel.iterrows():
            g = get_group(day.year)
            if not g:
                continue
            v = [s for s in row.dropna().index if s in g]
            if len(v) >= 4:
                c = pd.Series([g[s] for s in v]).value_counts()
                sizes.append(float(c.median()))
        return {"n": len(cors), "mean_abs_corr": round(float(np.mean(cors)), 3),
                "median_abs_corr": round(float(np.median(cors)), 3),
                "median_group_size": round(float(np.median(sizes)), 1) if sizes else None}

    def tier_g(year: int):
        m = tier_map_by_year.get(str(year))
        if not m:
            return None
        cnt = pd.Series(list(m.values())).value_counts()
        return {s: g for s, g in m.items() if cnt[g] >= MIN_GROUP}

    results = {"liquidity_tier_pit": ruler(tier_g)}

    # controls: re-run the ruler on s11's own maps over the IDENTICAL window and members
    if GMAP.exists():
        gm = json.loads(GMAP.read_text())
        for name in ("asset_class", "currency_quote"):
            m = gm.get(name) or {}
            results[name + "_control"] = ruler(lambda _y, m=m: m)

    out = {
        "_meta": {
            "built_by": "BRAIN HUNTER s24",
            "built_at": "2026-08-29",
            "window": f"{EVAL_YEARS[0]}-01-01..{EVAL_YEARS[-1]}-12-31 daily log returns",
            "tier_assignment": "tier for year Y from year Y-1 nonzero-median spread only (PIT)",
            "baseline": "universe-wide rank over the same members, same days",
            "s11_reference": {"currency_quote": 0.493, "asset_class": 0.819},
        },
        "A_spread_statistic_audit": {
            "n_symbols_with_tape": len(era),
            "n_registry_median_zero": sum(1 for s in era
                                          if era[s]["registry_median_spread_pts"] == 0),
            "n_zero_frac_over_20pct": sum(1 for s in era if era[s]["zero_frac_all"] > 0.20),
            "n_compared": len(cmp_rows),
            "n_understated_by_registry": len(understated),
            "worst_understatements": sorted(
                understated, key=lambda r: (-(r["ratio"] or 1e9) if r["registry_bps"] else 1e9)
            )[:15],
            "per_symbol": era,
        },
        "B_ruler": results,
        "tier_map_by_year": tier_map_by_year,
    }
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "tier_map_by_year"},
                     indent=1, default=str)[:4000])


if __name__ == "__main__":
    main()
