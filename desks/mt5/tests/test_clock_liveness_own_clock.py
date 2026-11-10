"""The forward-clock census runs on its own task, and that task can install itself.

CLOCK_LIVENESS.json sat 44h stale on the box (2026-10-12..13) because its only writer was a leg
of an hourly pass the scheduler killed first. Taking a leg off every plan is also the easiest way
to switch it off for good, so every link of the replacement clock is pinned here."""
from __future__ import annotations

import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for p in (str(DESK / "research"), str(DESK), str(ROOT), str(ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import check_own_clock_legs as own  # noqa: E402
import hourly_cycle as hc  # noqa: E402


def test_the_census_runs_on_no_cycle_plan() -> None:
    assert "clock_liveness" in hc.OWN_CLOCK_LEGS
    for plan in ("core", "heavy", "all", "dept:forward"):
        assert not hc.in_plan("clock_liveness", plan), plan


def test_the_rotation_does_not_measure_own_clock_legs() -> None:
    """Its task writes no ledger row, so measured it would sit outside_window forever."""
    full = ["record_tape", "clock_liveness", "state_vector", "external_gauntlet", "publish_state"]
    assert hc.rotation_roster(full) == ["record_tape", "publish_state"]


def test_its_task_is_declared_installed_and_self_registering() -> None:
    assert "clock_liveness" in own.own_clock_legs()
    task, artifact = own.OWN_CLOCK_TASKS["clock_liveness"]
    assert (task, artifact) == ("MT5-ClockLiveness", "reports/CLOCK_LIVENESS.json")
    installer = DESK / "scripts" / "install_clock_liveness_task.ps1"
    src = installer.read_text(encoding="utf-8")
    assert "research\\clock_liveness.py --once" in src and "-IfMissing" in src
    assert "AddMinutes(28)" in src      # clear of MT5-Healers, which rewrites shadow state at :48
    manifest = (DESK / "ops" / "box_tasks.manifest").read_text(encoding="utf-8")
    assert ('TASK name="MT5-ClockLiveness"' in manifest
            and "install_clock_liveness_task.ps1" in manifest)
    adopt = (DESK / "scripts" / "Adopt-And-Seal.ps1").read_text(encoding="utf-8")
    assert 'Task = "MT5-ClockLiveness"; Installer = "install_clock_liveness_task.ps1"' in adopt
