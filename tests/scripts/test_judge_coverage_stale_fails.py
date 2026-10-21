"""ON THE BOX A STALE OR UNDATED COVERAGE REPORT FAILS (2026-10-21).

`--require-state` used to append a freshness FAIL row and compute the verdict from the family
rules alone, so a 30h-old report whose last reading was healthy read PASS, rc 0; a missing or
unparseable `at` skipped the freshness check entirely. The portable reading is unchanged.
"""
from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 10, 21, 3, 0, tzinfo=UTC)


@pytest.fixture
def fence(monkeypatch) -> ModuleType:
    monkeypatch.delenv("QUANT_LAWGATE_SOURCE_VIEW", raising=False)
    spec = importlib.util.spec_from_file_location("judge_coverage_stale_fails",
                                                  REPO / "scripts/check_judge_coverage.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _healthy(at: Any) -> dict[str, Any]:
    doc: dict[str, Any] = {"families": {"overnight_drift": {"unjudged": 10, "queued": 3,
                                                            "judged_window": 4}}}
    if at is not None:
        doc["at"] = at
    return doc


def _write(tmp: Path, doc: dict[str, Any]) -> Path:
    p = tmp / "JUDGE_COVERAGE.json"
    p.write_text(json.dumps(doc), "utf-8")
    return p


def test_a_fresh_healthy_report_still_passes(fence, tmp_path):
    p = _write(tmp_path, _healthy(NOW.isoformat()))
    assert fence.judge(p, require_state=True, now=NOW)["verdict"] == "PASS"
    assert fence.judge(p, now=NOW)["verdict"] == "PASS"


def test_a_30h_old_healthy_report_fails_on_the_box(fence, tmp_path):
    p = _write(tmp_path, _healthy((NOW - timedelta(hours=30)).isoformat()))
    doc = fence.judge(p, require_state=True, now=NOW)
    assert doc["verdict"] == "FAIL" and fence._exit(doc["verdict"]) == 1
    assert doc["why"].startswith("the report is stale past its lease")
    assert any(c["metric"] == "freshness" and c["state"] == "FAIL" for c in doc["checks"])


@pytest.mark.parametrize("at", [None, "", "not-a-date"])
def test_an_undated_report_fails_on_the_box(fence, tmp_path, at):
    p = _write(tmp_path, _healthy(at))
    doc = fence.judge(p, require_state=True, now=NOW)
    assert doc["verdict"] == "FAIL" and doc["why"].startswith("the report is undated")


def test_portable_readings_are_unchanged(fence, tmp_path, monkeypatch):
    stale = _write(tmp_path, _healthy((NOW - timedelta(hours=30)).isoformat()))
    assert fence.judge(stale, now=NOW)["verdict"] == "UNMEASURED"
    undated = tmp_path / "u.json"
    undated.write_text(json.dumps(_healthy(None)), "utf-8")
    assert fence.judge(undated, now=NOW)["verdict"] == "PASS"         # judged as before
    monkeypatch.setenv("QUANT_LAWGATE_SOURCE_VIEW", "1")
    assert fence.judge(stale, now=NOW)["verdict"] == "UNMEASURED"
    assert fence.judge(undated, now=NOW)["verdict"] == "UNMEASURED"


def test_a_family_failure_reads_exactly_as_before(fence, tmp_path):
    doc = _healthy(NOW.isoformat())
    doc["families"]["overnight_drift"]["queued"] = 0
    out = fence.judge(_write(tmp_path, doc), require_state=True, now=NOW)
    assert out["why"] == "1 family(ies) failed a coverage rule: overnight_drift"
    assert fence.STALE_H == 6.0
