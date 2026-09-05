"""BRAIN HUNTER s26b -- wire the Ward arms into the grouping map the operators read.

s26 measured that the coverage/content trade s25 accepted at k=96 is a property of AVERAGE
linkage, not of correlation clustering: Ward on the Euclidean correlation metric beats average
linkage on BOTH axes at the same k (k=96: |corr| 0.433 vs 0.477 on 232 symbols vs 214; k=48:
|corr| 0.531 at 99.8% coverage). This adds `ward_cluster_by_year` k48/k96 on the SAME
point-in-time convention as every other arm. It ADDS keys and rewrites nothing.

Run: .venv/bin/python data/brain_hunter_s26b_build_ward_arms.py
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from brain_hunter_s26_linkage import build_panel, cluster_year  # noqa: E402

GMAP = pathlib.Path(__file__).resolve().parents[1] / "data/mt5_grouping_map.json"
NEW_KS = [48, 96]


def main() -> None:
    gm = json.loads(GMAP.read_text())
    panel = build_panel()
    years = sorted({int(y) for y in panel.index.year.unique()})
    wc = gm.setdefault("ward_cluster_by_year", {})
    added = {}
    for k in NEW_KS:
        by = {}
        for y in years:
            if y - 1 < years[0]:
                continue
            m = cluster_year(panel, y - 1, k, "ward", "euclid")
            if m:
                by[str(y)] = m
        wc[f"k{k}"] = by
        added[f"k{k}"] = {y: len(set(m.values())) for y, m in by.items()}
    meta = gm.setdefault("_meta", {})
    meta["ward_clusters_requested"] = NEW_KS
    meta["ward_linkage"] = "scipy ward on d = sqrt(2*(1-corr)); same PIT convention (Y from Y-1)"
    meta["ward_added_by"] = "BRAIN HUNTER s26b 2026-08-29"
    meta["ward_evidence"] = "data/brain_hunter_s26_linkage.json"
    GMAP.write_text(json.dumps(gm, indent=1, sort_keys=True) + "\n")
    for k in NEW_KS:
        print(k, "years:", len(added[f"k{k}"]), "2024:", added[f"k{k}"].get("2024"),
              "2025:", added[f"k{k}"].get("2025"))


if __name__ == "__main__":
    main()
