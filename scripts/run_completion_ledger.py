#!/usr/bin/env python3
"""COMPLETION LEDGER RUNNER -- verify every declared capability against the working tree.

Prose status drifts the moment code changes and lets "built" mean whichever stage the writer had
in mind. This computes it: EXISTS / IMPORTS / TESTS / CALLED / WIRED / PRODUCES / CONSUMED /
MEASURED, and reports the FIRST failing stage, because that is the gap to close.

Publishes unfinished capabilities into the ranked gap queue, so the completion programme cannot
quietly stall: an item that stops being worked reappears in tomorrow's priorities on its own.

    python scripts/run_completion_ledger.py [--json] [--top N]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research.completion_ledger import load, summarise, verify  # noqa: E402
from libs.research.gap_contract import Gap, publish  # noqa: E402

LEDGER = ROOT / "docs" / "research" / "COMPLETION_LEDGER.json"
OUT = ROOT / "data" / "completion_ledger_status.json"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ledger", type=Path, default=LEDGER)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    caps = load(a.ledger)
    if not caps:
        print(f"completion-ledger: BLOCKED -- no capabilities at {a.ledger}. An empty ledger is "
              "not a finished programme; it is an unmeasured one.")
        return 0

    rep = summarise(caps, root=ROOT)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps({"ts": datetime.now(tz=UTC).isoformat(), **rep}, indent=1), "utf-8")

    # UNFINISHED CAPABILITIES BECOME RANKED GAPS. Without this the programme depends on somebody
    # re-reading the ledger; with it, an item that stops being worked reappears in tomorrow's
    # priorities by itself -- which is the difference between a plan and a control.
    gaps = []
    for cap in caps:
        v = verify(cap, root=ROOT)
        if v.status == "VERIFIED_COMPLETE":
            continue
        if v.status == "EXTERNALLY_BLOCKED":
            gaps.append(Gap(
                aspect=f"capability::{cap.capability_id}", source="open_defect",
                current=None, ceiling=1.0,
                detail=f"EXTERNALLY BLOCKED: {cap.external_blocker}",
                action=cap.next_action or "resolve the named external dependency",
                artifact=str(a.out), evidence=cap.economic_reason,
                dependency=cap.external_blocker, tags=("completion-ledger", "blocked")))
            continue
        done = sum(1 for ok in v.stages.values() if ok)
        gaps.append(Gap(
            aspect=f"capability::{cap.capability_id}", source="open_defect",
            current=done / max(len(v.stages), 1), ceiling=1.0,
            detail=f"{v.status} -- first failing stage {v.failed_stage or 'n/a'}: {v.detail}",
            action=cap.next_action or f"close {v.failed_stage}",
            artifact=str(a.out), evidence=cap.economic_reason,
            dependency=cap.source_spec, tags=("completion-ledger",)))
    publish("completion_ledger", gaps)

    if a.json:
        print(json.dumps(rep, indent=1))
        return 0

    print(f"completion-ledger: {rep['headline']}")
    print(f"  next: {rep['next_action']}")
    rows = rep.get("rows")
    partial = [r for r in (rows if isinstance(rows, list) else []) if r["status"] == "PARTIAL"]
    missing = [r for r in (rows if isinstance(rows, list) else []) if r["status"] == "MISSING"]
    blocked = [r for r in (rows if isinstance(rows, list) else [])
               if r["status"] == "EXTERNALLY_BLOCKED"]
    for label, group in (("PARTIAL", partial), ("MISSING", missing), ("BLOCKED", blocked)):
        for r in group[:a.top]:
            stage = f" @{r['failed_stage']}" if r["failed_stage"] else ""
            print(f"  [{label}{stage}] {r['id']}")
        if len(group) > a.top:
            print(f"  ... and {len(group) - a.top} more {label}")
    print(f"  artifact: {a.out} | gaps published: {len(gaps)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
