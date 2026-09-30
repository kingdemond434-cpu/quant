#!/usr/bin/env python3
"""Observed restart-boundary parity for content-addressed gateway decisions.

The gateway stamps strategy-state and process identities on every decision.  When two process
instances evaluate the same strategy state at the same decision minute, this report proves their
decision payloads equal.  No overlap is UNMEASURED, never a pass.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
LEDGER = DESK / "data" / "decision_ledger.jsonl"
REPORT = DESK / "reports" / "STATE_REPLAY_PARITY.json"


def _minute(value: Any) -> str:
    return str(value or "")[:16]


def _signature(row: dict[str, Any]) -> str:
    body = {k: row.get(k) for k in (
        "outcome", "reason", "side", "price", "sl", "tp", "lot", "chosen_action",
        "size_mult", "execution", "exit_rule", "first_blocking_gate", "failed_gates")}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)


def run() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    try:
        for line in LEDGER.read_text("utf-8").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if (isinstance(row, dict) and row.get("state_identity")
                    and row.get("process_instance_id")):
                rows.append(row)
    except OSError:
        pass
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (str(row["state_identity"]), _minute(row.get("decided_at") or row.get("time")))
        groups[key].append(row)
    overlaps = []
    mismatches = []
    for key, same in groups.items():
        processes = {str(r["process_instance_id"]) for r in same}
        if len(processes) < 2:
            continue
        signatures = {_signature(r) for r in same}
        item = {"state_identity": key[0], "minute": key[1], "processes": sorted(processes),
                "rows": len(same), "equal": len(signatures) == 1}
        overlaps.append(item)
        if not item["equal"]:
            mismatches.append(item)
    status = "FAIL" if mismatches else "PASS" if overlaps else "UNMEASURED"
    doc = {"generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
           "status": status, "identity_rows": len(rows), "overlaps": len(overlaps),
           "mismatches": mismatches, "samples": overlaps[-100:],
           "law": ("warm-start and continuous decisions for one exact strategy-state identity "
                   "must match after a process boundary; absence of overlap is UNMEASURED")}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    tmp = REPORT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1), "utf-8")
    os.replace(tmp, REPORT)
    return doc


def main() -> int:
    doc = run()
    print(f"STATE_REPLAY {doc['status']} rows={doc['identity_rows']} "
          f"overlaps={doc['overlaps']} mismatches={len(doc['mismatches'])}")
    return 1 if doc["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
