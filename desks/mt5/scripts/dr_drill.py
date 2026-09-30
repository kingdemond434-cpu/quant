#!/usr/bin/env python3
"""DISASTER-RECOVERY DRILL, RUNNABLE ON THE BOX (Tier-1 audit item #19).

Restores every box store FROM THE OFF-BOX COPY (the origin branch's committed objects) into a
temp directory, replays the execution journal, and counts duplicate accepted intents -- the three
checks a lost box would need to pass before a rebuilt one could trade. It never touches a live
path and never places or cancels anything. The same checks run hourly inside
`research/ops_redundancy.py` (leg `ops_redundancy`); this is the drill a person runs on demand,
e.g. after a restore, and it exits non-zero on FAIL so a task can alarm on it.

    python desks\\mt5\\scripts\\dr_drill.py            (on the box, from C:\\opt\\quant)
    -> desks/mt5/reports/DR_DRILL.json
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ops_redundancy as ops  # noqa: E402

OUT = DESK / "reports" / "DR_DRILL.json"


def run() -> dict[str, Any]:
    drill = ops.restore_drill()
    journal = ops.journal_replay()
    dup = ops.duplicate_guard()
    parts = {"offbox_restore": drill["status"], "journal_replay": journal["status"],
             "duplicate_guard": dup["status"]}
    return {"generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "verdict": ("FAIL" if "FAIL" in parts.values() else
                        "PASS" if all(v == "PASS" for v in parts.values()) else "PARTIAL"),
            "components": parts, "offbox_restore": drill, "journal_replay": journal,
            "duplicate_guard": dup}


def main() -> int:
    doc = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, default=str), "utf-8")
    print(f"DR drill: {doc['verdict']} -- {doc['components']}")
    return 1 if doc["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
