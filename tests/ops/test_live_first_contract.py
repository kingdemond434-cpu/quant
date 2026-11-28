"""Quant-WorkflowGate is judged on live-first's own pass, not its exit code (2026-11-17 20:37Z:
the sweep read UNCONTRACTED while its runs were killed at the limit and a LIVE run sat queued)."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ops"))
import organ_contract as oc  # noqa: E402

REL = "desks/mt5/reports/LIVE_FIRST_CI.json"


def test_the_sweep_has_a_contract_on_live_firsts_stamp() -> None:
    artifact, max_age, purpose = oc.CONTRACTS["Quant-WorkflowGate"]
    assert artifact == REL and 0 < max_age <= 60 and "live-first" in purpose
    assert oc.INTERNAL_STAMPS[REL] == "at"
    src = (ROOT / "scripts" / "live_first_ci.py").read_text("utf-8")
    assert 'REPORT = ROOT / "desks" / "mt5" / "reports" / "LIVE_FIRST_CI.json"' in src
    assert src.count('_save(state, {"at": at,') == 2  # every non-dry pass stamps it
    gate = (ROOT / "ops" / "box" / "workflow_gate.ps1").read_text("utf-8")
    assert "desks\\mt5\\reports\\LIVE_FIRST_CI.json" in gate  # the path the sweep passes


def test_age_is_the_stamp_not_the_mtime(tmp_path: Path) -> None:
    now = datetime(2026, 11, 17, 20, 40, tzinfo=UTC)
    p = tmp_path / REL
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"at": (now - timedelta(minutes=55)).isoformat(), "owed": []}))
    age = oc.artifact_age_min(REL, root=tmp_path, now=now)
    assert age is not None and abs(age - 55) < 0.01  # fresh mtime, stale pass: STALE at 40
    p.write_text(json.dumps({"owed": []}))
    assert oc.artifact_age_min(REL, root=tmp_path, now=now) is None  # unstamped = nothing
