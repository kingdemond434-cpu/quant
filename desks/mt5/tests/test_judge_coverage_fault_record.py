"""AN INTAKE PASS THAT DOES NOT PUBLISH THE TABLE SAYS SO (2026-10-29).

`order_docket` is JUDGE_COVERAGE.json's writer of record. A fault in it returned the rows as
they arrived and left the report as the last good pass wrote it, with a stdout line as the only
trace -- so on the box the table sat at `at` 2026-10-27T17:33Z for two days. The pass now writes
JUDGE_COVERAGE_FAULT.json beside the report, leaves the report byte-identical, and the next pass
that publishes deletes the fault in its own commit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import judge_coverage as jc  # noqa: E402


def _isolate(monkeypatch, tmp_path: Path) -> Path:
    report = tmp_path / "reports" / "JUDGE_COVERAGE.json"
    report.parent.mkdir(parents=True)
    monkeypatch.setattr(jc, "REPORT", report)
    monkeypatch.setattr(jc, "TIMEOUT_REPORT", report.with_name("JUDGE_COVERAGE_TIMEOUT.json"))
    monkeypatch.setattr(jc, "RATCHET", tmp_path / "judge_backlog_ratchet.json")
    monkeypatch.setattr(jc, "UNRUNNABLE_BANK", tmp_path / "unrunnable_specs.json")
    return report


def test_a_faulted_pass_records_why_and_leaves_the_report(monkeypatch, tmp_path) -> None:
    report = _isolate(monkeypatch, tmp_path)
    old = json.dumps({"at": "2026-10-27T17:33:15+00:00", "families": {"a": {"judged_total": 1}}})
    report.write_text(old, "utf-8")

    def boom(*a, **k):
        raise RuntimeError("allocator fault")

    monkeypatch.setattr(jc, "build", boom)
    rows = [{"family": "a", "symbol": "EURUSD"}]
    out, doc = jc.order_docket([dict(r) for r in rows], publish=True)
    assert out == rows and doc["verdict"] == "UNMEASURED"
    assert report.read_text("utf-8") == old, "the report is never restamped by a faulted pass"
    fault = json.loads(jc.fault_path().read_text("utf-8"))
    assert fault["verdict"] == "FAULT" and "allocator fault" in fault["why"]
    assert fault["report_at"] == "2026-10-27T17:33:15+00:00" and fault["report_untouched"]


def test_a_measuring_pass_records_nothing(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(jc, "build", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    jc.order_docket([{"family": "a"}], publish=False)
    assert not jc.fault_path().exists(), "publish=False writes nothing"


def test_the_next_publishing_pass_clears_the_fault(monkeypatch, tmp_path) -> None:
    report = _isolate(monkeypatch, tmp_path)
    assert jc.write_fault("FAULT", "earlier") is not None and jc.fault_path().exists()
    monkeypatch.setattr(jc, "_docket_keff", lambda: None)
    jc.write({"at": "2026-10-29T15:00:00+00:00", "families": {"a": {"unjudged": 1}},
              "totals": {}})
    assert json.loads(report.read_text("utf-8"))["at"] == "2026-10-29T15:00:00+00:00"
    assert not jc.fault_path().exists()
