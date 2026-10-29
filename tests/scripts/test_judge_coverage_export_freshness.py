"""An exported historical desk report is not a current portable law verdict."""
import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path


def test_stale_export_is_unmeasured_but_live_freshness_still_fails(tmp_path):
    path = Path(__file__).resolve().parents[2] / "scripts/check_judge_coverage.py"
    spec = importlib.util.spec_from_file_location("coverage_export_control", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    now = datetime(2026, 10, 16, tzinfo=UTC)
    report = tmp_path / "coverage.json"
    doc = {"at": (now - timedelta(hours=7)).isoformat(),
           "families": {"example": {"unjudged": 10, "queued": 0}}}
    report.write_text(json.dumps(doc))
    before = report.read_bytes()
    assert module.judge(report, now=now)["verdict"] == "UNMEASURED"
    live = module.judge(report, now=now, require_state=True)
    assert live["verdict"] == "FAIL"
    assert any(r["metric"] == "freshness" and r["state"] == "FAIL" for r in live["checks"])
    assert before == report.read_bytes()
    doc["at"] = now.isoformat()
    report.write_text(json.dumps(doc))
    assert module.judge(report, now=now)["verdict"] == "FAIL"
