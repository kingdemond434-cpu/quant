"""Build the MT5 peer-grouping map that `libs.alpha_factory.wq_operators.group_rank`/`group_zscore`
refuse to run without (BRAIN HUNTER s11, 2026-08-29).

Three schemes, all from data already on the box:
  asset_class      -- registry field, the direct IndClass.sector analogue
  currency_base /
  currency_quote   -- the FX-native analogue with no equity counterpart
  corr_cluster_<Y> -- POINT-IN-TIME clusters: the map used in year Y is estimated on year Y-1 only,
                      so no bar is ever grouped using its own future. A single whole-sample cluster
                      map would be lookahead by construction and is deliberately NOT produced.

Unlabelled symbols are OMITTED, never pooled into an "other" bucket (wq_operators docstring).
Run: .venv/bin/python data/brain_hunter_s11_build_grouping_map.py
"""
from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

ROOT = pathlib.Path(__file__).resolve().parents[1]
UNIV = ROOT / "desks/mt5/data/universe/universe.json"
OUT = ROOT / "data/mt5_grouping_map.json"

CCY = {
    "USD", "EUR", "JPY", "GBP", "CHF", "AUD", "NZD", "CAD", "SEK", "NOK", "DKK", "PLN", "HUF",
    "CZK", "TRY", "ZAR", "MXN", "SGD", "HKD", "CNH", "RUB", "ILS", "THB", "INR", "KRW", "BRL",
}
MIN_GROUP = 2          # a group of one has no rank to compute (wq_operators)
MIN_DAYS = 120         # per-year overlap required before a symbol may be clustered
CORR_CLUSTERS = (8, 24)   # two cuts, fixed a priori. k=8 is the natural asset-class-scale cut and
#: is DOMINATED by one 125-member equity blob (measured, s11); k=24 is carried alongside it so the
#: peer-size axis is visible to whoever consumes the map rather than baked in by this builder.


def split_fx(sym: str) -> tuple[str, str] | None:
    if len(sym) != 6:
        return None
    base, quote = sym[:3].upper(), sym[3:].upper()
    if base in CCY and quote in CCY:
        return base, quote
    return None


def drop_singletons(m: dict[str, str]) -> dict[str, str]:
    counts: dict[str, int] = {}
    for g in m.values():
        counts[g] = counts.get(g, 0) + 1
    return {s: g for s, g in m.items() if counts[g] >= MIN_GROUP}


def main() -> None:
    univ = json.loads(UNIV.read_text())

    asset_class = drop_singletons(
        {s: v["asset_class"] for s, v in univ.items() if v.get("asset_class")}
    )
    base, quote = {}, {}
    for s in univ:
        legs = split_fx(s)
        if legs:
            base[s], quote[s] = legs
    base, quote = drop_singletons(base), drop_singletons(quote)

    # --- daily returns from the H1 tape, for the point-in-time correlation clusters -------------
    series: dict[str, pd.Series] = {}
    for s in univ:
        f = UNIV.parent / f"{s}_H1.parquet"
        if not f.exists():
            continue
        d = pd.read_parquet(f, columns=["close"])
        if getattr(d.index, "tz", None) is not None:
            d.index = d.index.tz_localize(None)   # the +00:00 stamp is a LABEL, not a clock:
            # 173/197 files are naive and all carry the same broker EET wall clock (recorded
            # lesson, 2026-08-29). Stripping the label ALIGNS them; "converting" would add 3h.
        c = d["close"].resample("1D").last().dropna()
        r = np.log(c).diff().dropna()
        if len(r) >= MIN_DAYS:
            series[s] = r
    panel = pd.DataFrame(series).sort_index()

    clusters: dict[str, dict[str, dict[str, str]]] = {f"k{k}": {} for k in CORR_CLUSTERS}
    years = sorted({int(y) for y in panel.index.year.unique()})
    for est_year in years:
        sub = panel[panel.index.year == est_year]
        sub = sub.loc[:, sub.notna().sum() >= MIN_DAYS]
        if sub.shape[1] < 4:
            continue
        corr = sub.corr(min_periods=MIN_DAYS)
        corr = corr.loc[corr.notna().sum() > 1, corr.notna().sum() > 1]
        if corr.shape[0] < 4:
            continue
        dist = np.sqrt(np.clip(2.0 * (1.0 - corr.fillna(0.0).to_numpy()), 0.0, None))
        np.fill_diagonal(dist, 0.0)
        dist = (dist + dist.T) / 2.0
        link = linkage(squareform(dist, checks=False), method="average")
        for k in CORR_CLUSTERS:
            lab = fcluster(link, t=min(k, corr.shape[0] - 1), criterion="maxclust")
            m = drop_singletons({sym: f"cc{int(g)}" for sym, g in zip(corr.columns, lab)})
            if len(set(m.values())) >= 2:
                clusters[f"k{k}"][str(est_year + 1)] = m   # ESTIMATED on est_year, USABLE from Y+1

    out = {
        "_meta": {
            "built_by": "BRAIN HUNTER s11",
            "built_at": "2026-08-29",
            "universe_file": str(UNIV.relative_to(ROOT)),
            "symbols_in_registry": len(univ),
            "min_group": MIN_GROUP,
            "corr_clusters_requested": list(CORR_CLUSTERS),
            "corr_estimation": "calendar-year daily log returns; key Y is estimated on Y-1",
            "unlabelled_policy": "omitted, never pooled into an 'other' bucket",
        },
        "asset_class": asset_class,
        "currency_base": base,
        "currency_quote": quote,
        "corr_cluster_by_year": clusters,
    }
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")

    def desc(name: str, m: dict[str, str]) -> str:
        return f"{name}: {len(m)} symbols, {len(set(m.values()))} groups"

    print(desc("asset_class", asset_class))
    print(desc("currency_base", base))
    print(desc("currency_quote", quote))
    print(f"corr panel: {panel.shape[1]} symbols, {panel.index.min().date()}..{panel.index.max().date()}")
    for k in clusters:
        last = sorted(clusters[k])[-1]
        print(desc(f"corr_cluster {k} (latest {last}, {len(clusters[k])} years)", clusters[k][last]))


if __name__ == "__main__":
    main()
