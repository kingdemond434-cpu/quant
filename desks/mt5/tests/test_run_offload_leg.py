"""The offload runner: standby until the cycle lets go, the same calls when it has."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "scripts"))

import run_offload_leg as rol  # noqa: E402


class FakeCycle:
    def __init__(self, own: set[str], tape_rc: int = 0, stamp: bool = True) -> None:
        self.OWN_CLOCK_LEGS = frozenset(own)
        self.tape_calls = 0
        self.tape_rc = tape_rc
        self.stamp = stamp
        self.stamped: list[tuple[dict, datetime]] = []

    def record_tape(self) -> dict:
        self.tape_calls += 1
        return {"exit_code": self.tape_rc, "tape_exit_code": self.tape_rc}

    def _stamp_heavy_pass(self, leg: dict, started: datetime) -> bool:
        self.stamped.append((leg, started))
        return self.stamp and leg.get("exit_code") == 0


def _runner(rc: int, calls: list):
    def run(cmd, timeout, cwd):
        calls.append((cmd, timeout, cwd))
        return SimpleNamespace(returncode=rc)
    return run


def test_tape_and_enrolment_stand_by_while_the_cycle_still_runs_them(tmp_path):
    cyc = FakeCycle(own=set())
    calls: list = []
    for leg in ("record_tape", "forward_enrolment"):
        doc = rol.run_leg(leg, cycle=cyc, runner=_runner(0, calls), out_dir=tmp_path)
        assert doc["status"] == "STANDBY" and doc["exit_code"] == 0
        assert json.loads((tmp_path / f"{leg}.json").read_text("utf-8"))["status"] == "STANDBY"
    assert cyc.tape_calls == 0 and calls == []


def test_tape_runs_the_cycles_own_function_once_handed_over(tmp_path):
    cyc = FakeCycle(own={"record_tape"})
    doc = rol.run_leg("record_tape", cycle=cyc, out_dir=tmp_path)
    assert cyc.tape_calls == 1 and doc["status"] == "RAN" and doc["exit_code"] == 0


def test_tape_failure_is_a_nonzero_receipt(tmp_path):
    cyc = FakeCycle(own={"record_tape"}, tape_rc=1)
    doc = rol.run_leg("record_tape", cycle=cyc, out_dir=tmp_path)
    assert doc["status"] == "FAILED" and doc["exit_code"] == 1


def test_enrolment_uses_the_cycles_arguments_once_handed_over(tmp_path):
    cyc = FakeCycle(own={"forward_enrolment"})
    calls: list = []
    doc = rol.run_leg("forward_enrolment", cycle=cyc, runner=_runner(0, calls), out_dir=tmp_path)
    assert doc["status"] == "RAN"
    cmd, timeout, _cwd = calls[0]
    assert cmd[-3:] == ["--once", "--budget-s", "300"]
    assert cmd[-4].endswith("forward_enrolment.py") and timeout > 300


def test_allocator_heavy_runs_at_once_and_stamps_the_pass(tmp_path):
    cyc = FakeCycle(own=set())
    calls: list = []
    doc = rol.run_leg("pf_allocator_heavy", cycle=cyc, runner=_runner(0, calls),
                      out_dir=tmp_path)
    assert doc["status"] == "RAN" and doc["heavy_pass_stamped"] is True
    assert calls[0][0][-2:] == ["--mode", "heavy"]
    leg, started = cyc.stamped[0]
    assert leg == {"exit_code": 0} and started.tzinfo is UTC


def test_allocator_stand_down_is_named_not_ran(tmp_path):
    cyc = FakeCycle(own=set(), stamp=False)
    doc = rol.run_leg("pf_allocator_heavy", cycle=cyc, runner=_runner(0, []), out_dir=tmp_path)
    assert doc["status"] == "STOOD_DOWN" and doc["exit_code"] == 0
    assert doc["heavy_pass_stamped"] is False


def test_allocator_failure_is_not_stamped(tmp_path):
    cyc = FakeCycle(own=set())
    doc = rol.run_leg("pf_allocator_heavy", cycle=cyc, runner=_runner(3, []), out_dir=tmp_path)
    assert doc["status"] == "FAILED" and doc["exit_code"] == 3
    assert doc["heavy_pass_stamped"] is False


def test_timeout_is_named(tmp_path):
    def run(cmd, timeout, cwd):
        raise subprocess.TimeoutExpired(cmd, timeout)
    doc = rol.run_leg("pf_allocator_heavy", cycle=FakeCycle(own=set()), runner=run,
                      out_dir=tmp_path)
    assert doc["status"] == "TIMEOUT" and doc["exit_code"] is None


def test_the_real_cycle_has_not_handed_these_legs_over_yet():
    # The handover is a separate, later change. Until it lands, the tasks must stand by.
    from research import hourly_cycle
    assert rol.NEEDS_HANDOVER.isdisjoint(hourly_cycle.OWN_CLOCK_LEGS)
    assert hasattr(hourly_cycle, "_stamp_heavy_pass") and hasattr(hourly_cycle, "record_tape")


def test_manifest_declares_every_offload_task_with_its_installer():
    text = (BASE / "ops" / "box_tasks.manifest").read_text("utf-8")
    ps1 = (BASE / "scripts" / "install_hourly_offload_tasks.ps1").read_text("utf-8")
    for name, leg in (("MT5-OffloadForwardEnrolment", "forward_enrolment"),
                      ("MT5-OffloadRecordTape", "record_tape"),
                      ("MT5-OffloadAllocatorHeavy", "pf_allocator_heavy")):
        line = next(ln for ln in text.splitlines() if f'name="{name}"' in ln)
        assert 'installer="desks/mt5/scripts/install_hourly_offload_tasks.ps1"' in line
        assert name in ps1 and f"'{leg}'" in ps1
        assert leg in rol.LEGS


def test_unknown_leg_is_refused(tmp_path):
    try:
        rol.run_leg("nope", cycle=FakeCycle(own=set()), out_dir=tmp_path)
    except SystemExit as exc:
        assert "unknown leg" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("an unknown leg must be refused")
    assert rol.main([]) == 2
