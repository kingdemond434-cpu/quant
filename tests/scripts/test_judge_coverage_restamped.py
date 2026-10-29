"""THE FILE WAS WRITTEN, THE TABLE WAS NOT (2026-10-29, measured on the box).

JUDGE_COVERAGE.json carried mtime 2026-10-29T14:26:44Z over `at` 2026-10-27T17:33:15Z: the
bytes were re-laid while the writer of record had not published a table for two days. On the box
(`--require-state`) a file written more than two writer cadences after its own `at` FAILS, and so
does a pass the intake recorded as unpublished (JUDGE_COVERAGE_FAULT.json). In a clone, where the
mtime is checkout time, neither is judged.
"""
from __future__ import annotations

import importlib.util
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def fence(monkeypatch) -> ModuleType:
    monkeypatch.delenv("QUANT_LAWGATE_SOURCE_VIEW", raising=False)
    spec = importlib.util.spec_from_file_location("judge_coverage_restamped",
                                                  REPO / "scripts/check_judge_coverage.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _report(tmp: Path, at: datetime, written: datetime) -> Path:
    doc: dict[str, Any] = {"at": at.isoformat(timespec="seconds"),
                           "families": {"overnight_drift": {"unjudged": 10, "queued": 3,
                                                            "judged_window": 4}}}
    p = tmp / "JUDGE_COVERAGE.json"
    p.write_text(json.dumps(doc), "utf-8")
    os.utime(p, (written.timestamp(), written.timestamp()))
    return p


def test_a_report_written_with_its_own_at_passes(fence, tmp_path):
    now = datetime.now(tz=UTC)
    p = _report(tmp_path, now - timedelta(minutes=20), now - timedelta(minutes=15))
    doc = fence.judge(p, require_state=True, now=now)
    assert doc["verdict"] == "PASS", doc["why"]
    assert any(c["metric"] == "restamped" and c["state"] == "OK" for c in doc["checks"])


def test_a_fresh_file_over_an_old_at_fails_on_the_box(fence, tmp_path):
    """Inside the 6h lease, so only the restamp check can see it: at 3h old, rewritten now."""
    now = datetime.now(tz=UTC)
    p = _report(tmp_path, now - timedelta(hours=3), now - timedelta(minutes=1))
    doc = fence.judge(p, require_state=True, now=now)
    assert doc["verdict"] == "FAIL" and fence._exit(doc["verdict"]) == 1
    assert "report_restamped" in doc["why"]
    row = next(c for c in doc["checks"] if c["metric"] == "restamped")
    assert row["state"] == "FAIL" and row["lag_h"] > 2.0


def test_the_portable_reading_never_judges_the_mtime(fence, tmp_path):
    now = datetime.now(tz=UTC)
    p = _report(tmp_path, now - timedelta(hours=3), now - timedelta(minutes=1))
    doc = fence.judge(p, now=now)
    assert doc["verdict"] == "PASS"
    assert not any(c["metric"] == "restamped" for c in doc["checks"])


def test_an_intake_fault_after_the_table_fails_by_name(fence, tmp_path):
    now = datetime.now(tz=UTC)
    p = _report(tmp_path, now - timedelta(minutes=50), now - timedelta(minutes=50))
    (tmp_path / "JUDGE_COVERAGE_FAULT.json").write_text(json.dumps({
        "at": (now - timedelta(minutes=5)).isoformat(timespec="seconds"),
        "verdict": "FAULT", "why": "RuntimeError: boom"}), "utf-8")
    doc = fence.judge(p, require_state=True, now=now)
    assert doc["verdict"] == "FAIL" and "intake_fault" in doc["why"]
    row = next(c for c in doc["checks"] if c["metric"] == "intake_fault")
    assert "RuntimeError: boom" in row["why"]


def test_a_fault_older_than_the_table_is_history(fence, tmp_path):
    now = datetime.now(tz=UTC)
    p = _report(tmp_path, now - timedelta(minutes=10), now - timedelta(minutes=10))
    (tmp_path / "JUDGE_COVERAGE_FAULT.json").write_text(json.dumps({
        "at": (now - timedelta(minutes=70)).isoformat(timespec="seconds"),
        "verdict": "FAULT", "why": "old"}), "utf-8")
    assert fence.judge(p, require_state=True, now=now)["verdict"] == "PASS"
