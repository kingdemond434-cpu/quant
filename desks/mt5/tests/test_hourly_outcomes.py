"""Producer verdicts must reach compute allocation without executing real desk work."""
import importlib.util
from pathlib import Path

import pytest

from libs.ops import compute_ledger


@pytest.fixture
def cycle(monkeypatch, tmp_path):
    monkeypatch.setattr(compute_ledger, "LEDGER", tmp_path / "compute.jsonl")
    path = Path(__file__).resolve().parents[1] / "research" / "hourly_cycle.py"
    spec = importlib.util.spec_from_file_location("hourly_outcome_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("result,expected", [
    ({"exit_code": 0, "status": "OK"}, "ok"),
    ({"exit_code": 1}, "exit_code=1"),
    ({"exit_code": None, "timeout_s": 45}, "TIMEOUT"),
    ({"exit_code": None, "status": "MISSING"}, "MISSING"),
    ({"error": "broken input"}, "FAILED: broken input"),
])
def test_returned_verdict_is_recorded(cycle, result, expected):
    assert cycle._costed("producer", lambda: result) is result
    assert compute_ledger.rows()[-1]["outcome"] == expected
    assert compute_ledger.cost_by_run()["producer"]["failures"] == int(expected != "ok")


def test_failed_leg_does_not_prevent_next_leg(cycle):
    def fail():
        raise SystemExit(2)

    assert cycle._costed("failed", fail)["status"] == "FAILED"
    assert cycle._costed("next", lambda: {"exit_code": 0}) == {"exit_code": 0}
    assert [r["run"] for r in compute_ledger.rows()] == ["failed", "next"]
