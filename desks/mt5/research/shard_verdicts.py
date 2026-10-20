"""WHAT THE JUDGE ALREADY KNOWS, BEFORE ITS MERGE ENDS (2026-10-20, IDEA_QUEUE 159).

The sealed judge publishes each shard's rows the moment that shard's `rule` phase ends
(`external_gauntlet._publish_shard`, patch `patches/judge_funnel_shards/B_shard_publication`), to

    desks/mt5/data/hypotheses/shard_verdicts/<plan token>/shard_<k>.json   (and shard_plan.json)

and, once the merge has written the record, `MERGED.json` beside them. This module READS those
files for every organ that wants the funnel before the merge -- the digest, the mutation arms --
and enforces the three rules a reader of a provisional copy must keep:

  1. ONE ROW PER CELL PER PLAN. A shard published twice (a retry, a resumed sweep) REPLACES its
     file; and a cell met twice is counted once, so nothing is double-counted.
  2. ONLY THE NEWEST UNMERGED PLAN IS IN FLIGHT. A plan with `MERGED.json` is superseded by the
     record (`gate_verdict_ledger.jsonl`, `universal_gates_external.json`); an unmerged plan
     older than a merged one was abandoned (a killed sweep) and is reported, never read as live.
  3. NOTHING HERE PASSES. A FINAL row is the merge's verdict (the merge checks it and records the
     check in MERGED.json); a PROVISIONAL row waits for PBO and SPA and reads `passed: null`. A
     row claiming `passed: true` is refused and counted as a defect. No promotion path reads this
     directory; `test_shard_publication.py` pins that.

It reads; it judges nothing, charges no trial and moves no gate.
"""
from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE / "data" / "hypotheses" / "shard_verdicts"
SCHEMA = "shard_verdicts/1"
STATUSES = ("FINAL", "REJECTED_TERMINAL_PENDING", "PROVISIONAL")
TOP = 40


def _read(path: Path) -> dict[str, Any] | None:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def plans(root: Path = ROOT) -> list[dict[str, Any]]:
    """Every plan directory, newest first, with its merge state and its published shards."""
    out = []
    try:
        dirs = [d for d in root.iterdir() if d.is_dir()]
    except OSError:
        return []
    for d in dirs:
        files = sorted(d.glob("shard_*.json"))
        merged = _read(d / "MERGED.json")
        newest = max((f.stat().st_mtime for f in files), default=d.stat().st_mtime)
        out.append({"token": d.name, "dir": d, "files": files, "merged": merged,
                    "mtime": max(newest, (d / "MERGED.json").stat().st_mtime
                                 if merged is not None else 0.0)})
    return sorted(out, key=lambda p: p["mtime"], reverse=True)


def rows_of(plan: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """The plan's rows, one per cell (first file in name order wins, which is stable)."""
    seen: set[str] = set()
    for f in plan["files"]:
        doc = _read(f)
        if doc is None or doc.get("schema") != SCHEMA:
            continue
        for r in doc.get("rows") or []:
            if not isinstance(r, dict):
                continue
            cid = str(r.get("cell") or "")
            if not cid or cid in seen:
                continue
            seen.add(cid)
            yield r


def in_flight(root: Path = ROOT) -> dict[str, Any]:
    """The newest UNMERGED plan's published rows, counted. UNMEASURED when there is none."""
    ps = plans(root)
    if not ps:
        return {"status": "UNMEASURED", "why": f"no published plan under {root.name}"}
    live = ps[0] if ps[0]["merged"] is None else None
    abandoned = [p["token"] for p in ps[1:] if p["merged"] is None]
    last_merged = next((p for p in ps if p["merged"] is not None), None)
    head: dict[str, Any] = {
        "abandoned_plans": abandoned,
        "last_merged": None if last_merged is None else {
            "token": last_merged["token"],
            **{k: last_merged["merged"].get(k) for k in (
                "merged_at", "published_rows", "final_rows_agree", "final_rows_disagree",
                "absent_from_merge")}},
    }
    if live is None:
        return {"status": "MERGED", "why": "the newest plan is merged: read the record", **head}
    by_status: Counter[str] = Counter()
    final_gates: Counter[str] = Counter()
    unmeasured: Counter[str] = Counter()
    defects: list[str] = []
    for r in rows_of(live):
        st = str(r.get("verdict_status") or "")
        if r.get("passed") is True or st not in STATUSES:
            defects.append(str(r.get("cell")))
            continue
        by_status[st] += 1
        if st == "FINAL":
            kind = str(r.get("terminal_kind") or "")
            if kind == "UNMEASURED":
                unmeasured[str(r.get("terminal_reason") or "")] += 1
            else:
                final_gates[str(r.get("terminal_gate_id") or "")] += 1
    shards = sorted(f.stem.removeprefix("shard_") for f in live["files"])
    return {"status": "IN_FLIGHT", "token": live["token"], "shards_published": shards,
            "rows": sum(by_status.values()), "by_status": dict(by_status),
            "final_by_terminal_gate_id": dict(final_gates.most_common(TOP)),
            "final_unmeasured_by_reason": dict(unmeasured.most_common(TOP)),
            "refused_rows": {"n": len(defects), "sample": defects[:20],
                             "rule": "a published row may never pass a cell"},
            **head}
