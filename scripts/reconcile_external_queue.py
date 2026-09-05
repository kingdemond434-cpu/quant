#!/usr/bin/env python3
"""Reconcile external Stage-A cards with their one canonical gauntlet.

The queue is a lineage projection, not a second executor: external_gauntlet.py
consumes external_survivors.json and is the only verdict authority.  This
prevents a card from sitting forever as generic PENDING or reaching run_hunt18,
which is a different H4/D1-only executor.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def _write_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     delete=False) as handle:
        json.dump(value, handle, indent=1, default=str)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _cell_id(symbol: str, family: str, params: dict[str, Any]) -> str:
    """The canonical executable identity used by the external gauntlet."""
    if "rr" in params or "wait_bars" in params:
        return f"{symbol}.{family}.rr={params.get('rr', '?')}_wb={params.get('wait_bars', '?')}"
    payload = json.dumps(params, sort_keys=True, separators=(",", ":"), default=str)
    return f"{symbol}.{family}.p={hashlib.sha256(payload.encode()).hexdigest()[:16]}"


def reconcile(root: Path, *, write: bool = True) -> dict[str, Any]:
    desk = root / "desks" / "mt5"
    queue_path = desk / "data" / "research_queue.json"
    docket_path = desk / "data" / "hypotheses" / "external_survivors.json"
    report_path = desk / "reports" / "universal_gates_external.json"
    queue, docket, report = _read(queue_path, []), _read(docket_path, []), _read(report_path, {})
    if not isinstance(queue, list):
        raise ValueError("research queue is unreadable or not a list")
    if not isinstance(docket, list):
        raise ValueError("external survivor docket is unreadable or not a list")
    if not isinstance(report, dict):
        raise ValueError("external gauntlet report is unreadable or not an object")
    docket_ids = {
        _cell_id(str(row.get("symbol") or row.get("sym") or ""), str(row.get("family") or ""),
                 dict(row.get("params") or {}))
        for row in docket if isinstance(row, dict)
    }
    verdicts = {str(row.get("cell")): row for row in report.get("verdicts", [])
                if isinstance(row, dict)}
    stamp = datetime.now(UTC).isoformat()
    counts = {"passed": 0, "rejected": 0, "awaiting": 0, "blocked": 0, "ignored": 0}
    active = {"PENDING", "QUEUED_CANONICAL_GAUNTLET", "AWAITING_CANONICAL_GAUNTLET"}
    for card in queue:
        if not isinstance(card, dict) or not (str(card.get("id", "")).startswith("ext-")
                                              and card.get("external_screen")):
            counts["ignored"] += 1
            continue
        if str(card.get("status") or "") not in active:
            counts["ignored"] += 1
            continue
        screen = card["external_screen"]
        symbol = str(screen.get("symbol") or "") if isinstance(screen, dict) else ""
        cell = _cell_id(symbol, str(card.get("family") or ""), dict(card.get("params") or {}))
        card.update({"route": "external_gauntlet", "canonical_cell": cell,
                     "reconciled_at": stamp, "promotion_authority": False})
        verdict = verdicts.get(cell)
        if verdict is not None:
            passed = verdict.get("passed") is True
            card.update({"canonical_verdict": "PASSED" if passed else "REJECTED",
                         "canonical_report": str(report_path.relative_to(root)),
                         "status": "GAUNTLET_PASSED" if passed else "GAUNTLET_REJECTED"})
            counts["passed" if passed else "rejected"] += 1
        elif cell in docket_ids:
            card.update({"status": "AWAITING_CANONICAL_GAUNTLET",
                         "blocked_on": "canonical gauntlet has not emitted an individual verdict for this docket cell"})
            counts["awaiting"] += 1
        else:
            card.update({"status": "BLOCKED_CANONICAL_DOCKET_MISSING",
                         "blocked_on": "exact external Stage-A card absent from external_survivors docket"})
            counts["blocked"] += 1
    result = {"reconciled_at": stamp,
              "authority": "EXTERNAL_GAUNTLET_ONLY; queue rows have no promotion authority",
              "queue_path": str(queue_path.relative_to(root)),
              "docket_path": str(docket_path.relative_to(root)),
              "report_path": str(report_path.relative_to(root)), "counts": counts}
    if write:
        _write_atomic(queue_path, queue)
        _write_atomic(desk / "reports" / "external_queue_reconciliation.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(reconcile(args.root.resolve(), write=not args.dry_run), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
