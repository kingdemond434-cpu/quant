"""The disposition registry must shrink the queue only with recorded, substantive verdicts
(gap-fixer 2026-08-26). Before it, the audit demanded 'an explicit block/archive disposition'
and provided nowhere to record one -- every weekly seat re-inspected the same modules. Pins:

  * a valid verdict re-statuses the row (DISPOSED_*), leaving UNWIRED_REVIEW,
  * a malformed row (short reason / unknown verdict) is REFUSED and counted, never silently
    applied -- a disposition that shrinks the queue without a decision is the launder shape,
  * reachability outranks any verdict: a disposed module with a real consumer reports
    REACHABLE with the disposition flagged stale.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_mt5_capability_reuse import audit


def _tree(tmp_path: Path, dispositions: dict) -> Path:
    (tmp_path / "libs").mkdir()
    (tmp_path / "libs" / "orphan.py").write_text("X = 1\n")
    (tmp_path / "libs" / "used.py").write_text("Y = 2\n")
    (tmp_path / "desks/mt5").mkdir(parents=True)
    # NOTE the import must be dotted: the scanner resolves `from libs.used import Y` but is
    # blind to `from libs import used` (resolve_local walks module prefixes only) -- a measured
    # false-UNWIRED source, discovered writing this test.
    (tmp_path / "desks/mt5/consumer.py").write_text("from libs.used import Y\n")
    reg = tmp_path / "docs/research/mt5_capability_dispositions.json"
    reg.parent.mkdir(parents=True)
    reg.write_text(json.dumps({"dispositions": dispositions}), "utf-8")
    return tmp_path


GOOD_REASON = ("Superseded by the MT5 desk's own organ; wiring it back would recreate "
               "the two-lineage disease.")


def _rows(payload: dict) -> dict[str, dict]:
    return {r["module"]: r for r in payload["rows"]}


def test_valid_disposition_restatuses_row(tmp_path: Path) -> None:
    root = _tree(tmp_path, {"libs.orphan": {"verdict": "SUPERSEDED", "reason": GOOD_REASON}})
    payload = audit(root)
    assert _rows(payload)["libs.orphan"]["status"] == "DISPOSED_SUPERSEDED"
    assert payload["counts"].get("UNWIRED_REVIEW", 0) == 0
    assert "DISPOSITION_INVALID" not in payload["counts"]


def test_malformed_disposition_refused_and_counted(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "libs.orphan": {"verdict": "SUPERSEDED", "reason": "too short"},
    })
    payload = audit(root)
    assert _rows(payload)["libs.orphan"]["status"] == "UNWIRED_REVIEW"
    assert payload["counts"]["DISPOSITION_INVALID"] == 1


def test_reachability_outranks_disposition(tmp_path: Path) -> None:
    root = _tree(tmp_path, {"libs.used": {"verdict": "BLOCKED", "reason": GOOD_REASON}})
    row = _rows(audit(root))["libs.used"]
    assert row["status"] == "REACHABLE_MT5_STATIC"
    assert row["disposition"]["stale"] is True
