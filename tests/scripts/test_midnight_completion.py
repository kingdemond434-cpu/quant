from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "run_midnight_completion", ROOT / "scripts" / "run_midnight_completion.py"
)
assert SPEC and SPEC.loader
completion = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = completion
SPEC.loader.exec_module(completion)


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), "utf-8")


def test_plan_reuses_canonical_organs_in_dependency_order() -> None:
    stages = completion.canonical_stages("python")
    names = [stage.name for stage in stages]
    assert names == [
        "canonical_external_pipeline", "external_queue_projection",
        "external_queue_reconciliation", "certificate_projection", "fusion_state_pull",
        "forward_identity_reconciliation", "forward_clock_reconciliation",
        "forward_lane_heal", "zero_capital_shadow_forward", "mechanism_independence",
        "same_day_fence", "certificate_yield_fence", "forward_clock_fence",
    ]
    commands = " ".join(part for stage in stages for part in stage.command)
    assert "quant-external-pipeline.service" in commands
    assert "shadow-forward.service" in commands
    assert "external_gauntlet.py" not in commands
    assert "promote_mature" not in commands
    assert "--place" not in commands


def test_completion_continues_after_failure_and_publishes_counts(tmp_path: Path) -> None:
    desk = tmp_path / "desks" / "mt5"
    _write(desk / "data" / "research_queue.json", [
        {"status": "QUEUED_CANONICAL_GAUNTLET"}, {"status": "GAUNTLET_PASSED"}
    ])
    _write(desk / "data" / "hypotheses" / "external_survivors.json", [
        {"symbol": "XAUUSD", "family": "x", "params": {}}
    ])
    _write(desk / "reports" / "universal_gates_external.json", {
        "n_cells_discovered": 1,
        "verdicts": [{"cell": "XAUUSD.x.p=44136fa355b3678a", "passed": False,
                      "stages": {"economic_prior": {"passed": False}}}],
    })
    _write(desk / "reports" / "UNIVERSAL_SURVIVORS.json", {"survivors": {"gold": {}}})
    _write(desk / "reports" / "shadow" / "shadow_state.json", {
        "gold": {"status": "ACTIVE"}, "dead": {"status": "RETIRED_GATE_FAIL"}
    })
    stages = (
        completion.Stage("broken", ("broken",), 1),
        completion.Stage("diagnostic", ("diagnostic",), 1,
                         frozenset({0, 1}), True),
        completion.Stage("still_runs", ("still-runs",), 1),
    )
    calls: list[str] = []

    def fake_runner(command, timeout, root):
        del timeout, root
        calls.append(command[0])
        rc = {"broken": 9, "diagnostic": 1}.get(command[0], 0)
        return completion.CommandResult(rc, f"ran {command[0]}", "")

    output = tmp_path / "completion.json"
    report = completion.execute(tmp_path, stages, fake_runner, output)
    assert calls == ["broken", "diagnostic", "still-runs"]
    assert report["hard_failures"] == ["broken"]
    assert report["diagnostic_findings"] == ["diagnostic"]
    assert report["needs_controller"] is True
    assert report["after"] == {
        "queue_total": 2,
        "queue_by_status": {"GAUNTLET_PASSED": 1, "QUEUED_CANONICAL_GAUNTLET": 1},
        "external_screen_survivors": 1,
        "universal_certificates": 1,
        "active_forward_clocks": 1,
    }
    assert json.loads(output.read_text("utf-8"))["complete"] is False


def test_catch_up_restarts_the_same_service_until_no_cell_is_deferred(tmp_path: Path) -> None:
    report_path = (tmp_path / "desks" / "mt5" / "reports"
                   / "universal_gates_external.json")
    calls = 0

    def fake_runner(command, timeout, root):
        nonlocal calls
        del command, timeout
        calls += 1
        verdict = ({"cell": "x", "passed": None,
                    "downstream_status": "NOT_RUN_BUILD_BUDGET_DEFERRED"}
                   if calls == 1 else {"cell": "x", "passed": False})
        _write(root / report_path.relative_to(tmp_path), {
            "n_cells_discovered": 1, "verdicts": [verdict]
        })
        return completion.CommandResult(0, "", "", 1.0)

    stage = completion.Stage("canonical_external_pipeline", ("canonical",), 1,
                             catch_up=True)
    result = completion.execute(tmp_path, (stage,), fake_runner,
                                tmp_path / "completion.json")
    assert calls == 2
    assert result["hard_failures"] == []
    assert result["stages"][0]["passes"][-1]["outstanding_after"] == 0
    checkpoint = json.loads(
        (tmp_path / "data" / "intelligence"
         / "midnight_completion_checkpoint.json").read_text("utf-8")
    )
    assert checkpoint["stages"]["canonical_external_pipeline"] == {
        "status": "DONE",
        "finished_at": checkpoint["stages"]["canonical_external_pipeline"]["finished_at"],
        "returncode": 0,
        "passes_completed": 2,
    }
