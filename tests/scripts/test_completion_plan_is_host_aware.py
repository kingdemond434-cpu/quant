"""The canonical completion plan must be runnable on the host that runs the desk.

THREE OF THE FOUR HARD FAILURES WERE `systemctl` ON A WINDOWS BOX (measured 2026-09-14):

    fusion_state_pull            rc=127  ['systemctl','--user','start','quant-desk-pull.service']
    zero_capital_shadow_forward  rc=127  ['systemctl','--user','start','shadow-forward.service']
    canonical_external_pipeline  rc=127  ['systemctl','--user','start','quant-external-pipeline..']

127 is "command not found". The machine running the gateway, the forward clocks and the promoter
is Windows and has no systemd, so `complete: true` was UNREACHABLE BY CONSTRUCTION -- not because
research had failed, but because three stages invoked a program absent from the host. No amount of
desk work could ever have closed the loop.

The VPS is unchanged: where systemctl exists the original units still run.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

mc = pytest.importorskip("scripts.run_midnight_completion")


def test_no_stage_shells_out_to_systemd_when_it_is_absent(monkeypatch):
    monkeypatch.setattr(mc.shutil, "which", lambda name: None)
    stages = mc.canonical_stages("python")
    offenders = [s.name for s in stages if s.command and s.command[0] == "systemctl"]
    assert not offenders, f"these stages cannot run on a host without systemd: {offenders}"


def test_the_units_are_still_used_where_systemd_exists(monkeypatch):
    """This adds a host; it does not migrate one. The VPS plan must be byte-identical."""
    monkeypatch.setattr(mc.shutil, "which", lambda name: "/usr/bin/systemctl")
    stages = {s.name: s.command for s in mc.canonical_stages("python")}
    assert stages["fusion_state_pull"][:3] == ("systemctl", "--user", "start")
    assert stages["zero_capital_shadow_forward"][3] == "shadow-forward.service"
    assert stages["canonical_external_pipeline"][3] == "quant-external-pipeline.service"


def test_every_stage_is_executable_off_systemd(monkeypatch):
    """A plan whose stages cannot run is not a plan. Each must name an interpreter or a script."""
    monkeypatch.setattr(mc.shutil, "which", lambda name: None)
    for s in mc.canonical_stages("python"):
        assert s.command, f"{s.name} has no command"
        head = str(s.command[0])
        assert head == "python" or head.endswith("python.exe") or Path(head).name.startswith(
            "python"), f"{s.name} does not invoke the interpreter: {s.command}"


def test_the_desk_pull_is_a_declared_no_op_not_a_failure(monkeypatch):
    """It moves state FROM this box TO the VPS. On the box that is meaningless, not broken --
    and a stage that cannot apply here must never be reported as a defect here (L1.28a)."""
    monkeypatch.setattr(mc.shutil, "which", lambda name: None)
    cmd = {s.name: s.command for s in mc.canonical_stages("python")}["fusion_state_pull"]
    joined = " ".join(cmd)
    assert "SKIPPED" in joined
    assert "no-op, not a failure" in joined
