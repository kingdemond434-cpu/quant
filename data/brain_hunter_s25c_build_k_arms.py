"""BRAIN HUNTER s25c -- wire s25's result into the grouping map the operators read.

s25/s25b measured that the correlation-cluster grouping keeps buying independence out to k~128,
while the desk's map (built by s11) stops at k=8/k=24. This adds k=48 and k=96 arms on the SAME
point-in-time convention already recorded in the map's _meta (year Y clustered on Y-1 only), for
every year the panel supports. It ADDS keys; it never rewrites k8/k24.

Run: .venv/bin/python data/brain_hunter_s25c_build_k_arms.py
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from brain_hunter_s25_kcurve import build_panel, cluster_year  # noqa: E402

GMAP = pathlib.Path(__file__).resolve().parents[1] / "data/mt5_grouping_map.json"
NEW_KS = [48, 96]


def main() -> None:
    gm = json.loads(GMAP.read_text())
    panel = build_panel()
    years = sorted({int(y) for y in panel.index.year.unique()})
    cc = gm.setdefault("corr_cluster_by_year", {})
    added = {}
    for k in NEW_KS:
        by = {}
        for y in years:
            if y - 1 < years[0]:
                continue
            m = cluster_year(panel, y - 1, k)
            if m:
                by[str(y)] = m
        cc[f"k{k}"] = by
        added[f"k{k}"] = {y: len(set(m.values())) for y, m in by.items()}
    meta = gm.setdefault("_meta", {})
    meta.setdefault("corr_clusters_requested", [])
    for k in NEW_KS:
        if k not in meta["corr_clusters_requested"]:
            meta["corr_clusters_requested"].append(k)
    meta["corr_clusters_requested"] = sorted(meta["corr_clusters_requested"])
    meta["k48_k96_added_by"] = "BRAIN HUNTER s25c 2026-08-29"
    meta["k48_k96_evidence"] = "data/brain_hunter_s25_kcurve.json + s25b_fixedset.json"
    GMAP.write_text(json.dumps(gm, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: {"years": len(v)} for k, v in added.items()}, indent=1))
    for k in NEW_KS:
        yrs = added[f"k{k}"]
        print(k, "2024:", yrs.get("2024"), "2025:", yrs.get("2025"))


if __name__ == "__main__":
    main()
