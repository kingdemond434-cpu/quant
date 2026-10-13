"""SOURCE ROI: every lane's durable cursor carries the funnel, and the funnel reprices compute.

    zuck, 2026-09-30: source_id, last_seen_version, last_scan, last_content_hash, coverage_depth,
    items_seen, items_new, mechanisms_extracted, cells_emitted, cells_judged, survivors,
    forward_survivors, incremental_k_eff, compute_seconds, ROI.

ROI = validated information per compute second, where information is counted with the weights
below: a judged cell is worth a little (it moved the frontier), a gauntlet survivor a lot, a
forward survivor most; non-alpha outcomes are credited at their consumer's own small weight so a
lane that only feeds negative knowledge (LEAN regression tests) is not priced at zero. The
weights are published with the numbers, so the pricing can be argued with.

`budget_shares()` turns ROI into the next pass's fetch ORDER and per-lane item budget. It never
takes a lane to zero (the principal's standing rule: never throttle raw mining); the floor share
keeps every lane walking its cursor, and the rest is split by ROI with a novelty bonus for lanes
too young to be judged (a lane with no verdict yet is UNMEASURED, not bad).
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

WEIGHTS: dict[str, float] = {"cells_judged": 1.0, "survivors": 50.0,
                             "forward_survivors": 200.0, "mechanisms_extracted": 0.2,
                             "outcomes_routed": 0.05, "incremental_k_eff": 400.0}
FLOOR_SHARE = 0.5          # half of every pass is split EVENLY: no lane is ever starved
MIN_ITEMS = 20


def roi(row: Mapping[str, Any]) -> float | None:
    """Information per compute second; None (UNMEASURED) when no compute was recorded."""
    secs = float(row.get("compute_seconds") or 0.0)
    if secs <= 0:
        return None
    info = sum(float(row.get(k) or 0) * w for k, w in WEIGHTS.items())
    return round(info / secs, 6)


def funnel(source_id: str, *, cursor: Mapping[str, Any], records: int, new: int,
           mechanisms: int, cells: int, judged: int, survivors: int, forward: int,
           outcomes: int, compute_seconds: float, k_eff_increment: float | None = None
           ) -> dict[str, Any]:
    row: dict[str, Any] = {
        "source_id": source_id,
        "last_seen_version": cursor.get("last_sha") or cursor.get("walk_sha") or "",
        "last_scan": cursor.get("last_run"),
        "last_outcome": cursor.get("last_outcome"),
        "last_content_hash": cursor.get("last_content_hash") or "",
        "coverage_depth": _depth(cursor),
        "items_seen": records, "items_new": new, "mechanisms_extracted": mechanisms,
        "cells_emitted": cells, "cells_judged": judged, "survivors": survivors,
        "forward_survivors": forward, "outcomes_routed": outcomes,
        "incremental_k_eff": k_eff_increment if k_eff_increment is not None else "UNMEASURED",
        "compute_seconds": round(float(compute_seconds), 3),
    }
    r = roi({**row, "incremental_k_eff": k_eff_increment or 0.0})
    row["ROI"] = r if r is not None else "UNMEASURED"
    return row


def _depth(cursor: Mapping[str, Any]) -> float | str:
    """How far through its ground a lane is: walk position / total for a repo backfill, done
    for a completed backfill, pages walked for a listing; UNMEASURED otherwise."""
    tot = cursor.get("walk_total")
    if cursor.get("backfill_done"):
        return 1.0
    if isinstance(tot, int) and tot > 0:
        return round(min(1.0, int(cursor.get("walk_pos") or 0) / tot), 4)
    if cursor.get("sitemap_urls"):
        pending = int(cursor.get("sitemap_pending") or 0)
        total = int(cursor.get("sitemap_urls") or 0)
        return round(1 - pending / total, 4) if total else "UNMEASURED"
    return "UNMEASURED"


def budget_shares(rows: Mapping[str, Mapping[str, Any]], total_items: int
                  ) -> dict[str, int]:
    """Per-lane item budget for the next pass. Even floor + ROI-weighted remainder; lanes
    with UNMEASURED ROI get the median ROI (novelty is not penalised)."""
    ids = sorted(rows)
    if not ids:
        return {}
    measured = sorted(float(r["ROI"]) for r in rows.values()
                      if isinstance(r.get("ROI"), (int, float)))
    med = measured[len(measured) // 2] if measured else 1.0
    w = {i: max(1e-9, float(rows[i]["ROI"]) if isinstance(rows[i].get("ROI"), (int, float))
                else med) for i in ids}
    floor = total_items * FLOOR_SHARE / len(ids)
    rest = total_items * (1 - FLOOR_SHARE)
    tw = sum(w.values())
    return {i: max(MIN_ITEMS, math.floor(floor + rest * w[i] / tw)) for i in ids}
