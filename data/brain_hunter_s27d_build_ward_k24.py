"""BRAIN HUNTER s27d -- wire ward k24, the arm the corrected ruler actually recommends.

s27c scored the whole (method x k) grid on ONE population and ward k=24 won outright
(content +0.3184, z=-38.6, real and control both scored on the identical 101 symbols).
The map carried ward at k48/k96 only, because s26 chose k from a ruler whose population
shrank with k. This ADDS ward k24 and stamps the corrected evidence. It removes no arm:
the k48/k96 arms stay available and their entry is re-pointed at the evidence that now
governs them, so a consumer can still choose them deliberately.

Run: .venv/bin/python data/brain_hunter_s27d_build_ward_k24.py
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from brain_hunter_s27_exact_control import build_panel, cluster_year

GMAP = pathlib.Path(__file__).resolve().parents[1] / "data/mt5_grouping_map.json"
NEW_KS = [24]


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
            m = cluster_year(panel, y - 1, k, "ward")
            if m:
                by[str(y)] = m
        wc[f"k{k}"] = by
        added[f"k{k}"] = {y: len(set(m.values())) for y, m in by.items()}
    meta = gm.setdefault("_meta", {})
    prev = set(meta.get("ward_clusters_requested", []))
    meta["ward_clusters_requested"] = sorted(prev | set(NEW_KS))
    meta["ward_k24_added_by"] = "BRAIN HUNTER s27d 2026-08-29"
    meta["recommended_arm"] = "ward_cluster_by_year.k24"
    meta["recommended_arm_evidence"] = "data/brain_hunter_s27c_common_population.json"
    meta["k_selection_caveat"] = (
        "The k48/k96 arms (s25c/s26b) were selected on rulers whose evaluated population "
        "SHRANK with k, so their content numbers are not comparable across k. On one held "
        "population (s27c) the k-curve is monotone DECREASING for ward. Arms retained, but "
        "k>24 must not be preferred on the s25/s26 evidence."
    )
    GMAP.write_text(json.dumps(gm, indent=1, sort_keys=True) + "\n")
    for k in NEW_KS:
        print("k", k, "years:", len(added[f"k{k}"]), "2024:", added[f"k{k}"].get("2024"),
              "2025:", added[f"k{k}"].get("2025"))


if __name__ == "__main__":
    main()
