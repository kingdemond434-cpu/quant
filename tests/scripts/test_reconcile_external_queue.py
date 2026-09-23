from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "reconcile_external_queue", ROOT / "scripts" / "reconcile_external_queue.py"
)
assert SPEC and SPEC.loader
reconcile_external_queue = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reconcile_external_queue)


def _paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    desk = tmp_path / "desks" / "mt5"
    queue = desk / "data" / "research_queue.json"
    docket = desk / "data" / "hypotheses" / "external_survivors.json"
    report = desk / "reports" / "universal_gates_external.json"
    queue.parent.mkdir(parents=True)
    docket.parent.mkdir(parents=True)
    report.parent.mkdir(parents=True)
    return queue, docket, report


def test_reconcile_routes_only_external_cards_to_canonical_verdict(tmp_path: Path) -> None:
    queue, docket, report = _paths(tmp_path)
    card = {
        "id": "ext-1", "status": "PENDING", "family": "session_range_breakout",
        "params": {"rr": 2.0, "wait_bars": 8}, "external_screen": {"symbol": "XAUUSD"},
    }
    queue.write_text(json.dumps([card, {"id": "h18-1", "status": "QUEUED"}]))
    docket.write_text(json.dumps([{
        "symbol": "XAUUSD", "family": "session_range_breakout", "params": card["params"],
    }]))
    report.write_text(json.dumps({"verdicts": [{
        "cell": "XAUUSD.session_range_breakout.rr=2.0_wb=8", "passed": False,
    }]}))

    outcome = reconcile_external_queue.reconcile(tmp_path)
    rows = json.loads(queue.read_text())

    assert outcome["counts"]["rejected"] == 1
    assert rows[0]["status"] == "GAUNTLET_REJECTED"
    assert rows[0]["route"] == "external_gauntlet"
    assert rows[0]["promotion_authority"] is False
    assert rows[1] == {"id": "h18-1", "status": "QUEUED"}


def test_reconcile_reports_missing_docket_as_blocked_not_rejected(tmp_path: Path) -> None:
    queue, docket, report = _paths(tmp_path)
    queue.write_text(json.dumps([{
        "id": "ext-2", "status": "PENDING", "family": "carry", "params": {},
        "external_screen": {"symbol": "AUDUSD"},
    }]))
    docket.write_text("[]")
    report.write_text(json.dumps({"verdicts": []}))

    outcome = reconcile_external_queue.reconcile(tmp_path)
    row = json.loads(queue.read_text())[0]

    assert outcome["counts"]["blocked"] == 1
    assert row["status"] == "BLOCKED_CANONICAL_DOCKET_MISSING"
    assert "absent" in row["blocked_on"]
