#!/usr/bin/env python3
"""Publish the gateway's canonical decision ledger as a queryable WHY-NOT report.

This creates no second ledger.  It is a deterministic materialized view of
``data/decision_ledger.jsonl``: first blocker, every failed gate, actual versus required detail,
suppression reason, and process quality kept separate from economic outcome.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research.decision_ledger import read, summarise  # noqa: E402

LEDGER = DESK / "data" / "decision_ledger.jsonl"
REPORT = DESK / "reports" / "WHY_NOT.json"
MAX_DETAIL_ROWS = 500


def run() -> dict:
    decisions = read(LEDGER)
    doc = {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": str(LEDGER.relative_to(ROOT)),
        "law": ("one canonical decision ledger; every evaluated opportunity is executed or has "
                "a structured first blocker; process quality is never inferred from P&L"),
        **summarise(decisions),
        "latest": [
            {
                "decision_id": d.decision_id, "at": d.decided_at, "symbol": d.symbol,
                "sleeve": d.sleeve or d.strategy_id, "outcome": d.outcome,
                "first_blocking_gate": d.first_blocking_gate,
                "failed_gates": d.failed_gates, "suppressions": d.suppressions,
                "process_quality": d.process_quality,
            }
            for d in decisions[-MAX_DETAIL_ROWS:]
        ],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    tmp = REPORT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, REPORT)
    return doc


def main() -> int:
    doc = run()
    print(f"WHY_NOT decisions={doc.get('decisions', 0)} "
          f"blockers={len((doc.get('why_not') or {}).get('first_blocking_gate', {}))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
