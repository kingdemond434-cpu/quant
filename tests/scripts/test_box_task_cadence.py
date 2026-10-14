"""Installer triggers must agree with the box task manifest (check_box_tasks (e)).

Found 2026-10-14: Install-QuantWindows.ps1 registered MT5-QQuantGatesCertify daily at 23:00
against a manifest "every 1 hour, at :27", so a reinstall would have left the certifier's
180-minute organ contract red for good."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("check_box_tasks", ROOT / "scripts" /
                                              "check_box_tasks.py")
assert SPEC is not None and SPEC.loader is not None
cbt = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cbt)


def test_no_installer_trigger_disagrees_with_the_manifest() -> None:
    assert cbt.check()["installer_trigger_drift"] == []


def test_the_certifier_and_the_risk_fence_take_their_cadence_from_the_manifest() -> None:
    regs = cbt.installer_triggers()
    for name in ("MT5-QQuantGatesCertify", "MT5-RiskUnitsFence"):
        assert regs[name] == [("desks/mt5/scripts/Install-QuantWindows.ps1", -1)], name
    rows = {r["name"]: r for r in cbt.manifest_rows()}
    assert cbt.manifest_period_min(rows["MT5-QQuantGatesCertify"]["trigger"]) == 60


def test_a_daily_trigger_against_an_hourly_manifest_is_caught(tmp_path: Path) -> None:
    ps = tmp_path / "desks" / "mt5" / "scripts" / "install_x.ps1"
    ps.parent.mkdir(parents=True)
    ps.write_text('$t = New-ScheduledTaskTrigger -Daily -At "23:00"\r\n'
                  'Register-ScheduledTask -TaskName "MT5-X" -Action $a `\r\n'
                  '    -Trigger $t | Out-Null\r\n', "utf-8")
    assert cbt.installer_triggers(tmp_path) == {"MT5-X": [("desks/mt5/scripts/install_x.ps1",
                                                          1440)]}
    assert cbt.manifest_period_min("every 1 hour, at :27") == 60


def test_a_daily_trigger_with_an_hourly_repetition_reads_hourly(tmp_path: Path) -> None:
    ps = tmp_path / "desks" / "mt5" / "scripts" / "install_y.ps1"
    ps.parent.mkdir(parents=True)
    ps.write_text("$trigger = New-ScheduledTaskTrigger -Daily -At $x\n"
                  "$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At $x `\n"
                  "    -RepetitionInterval (New-TimeSpan -Hours 1) `\n"
                  "    -RepetitionDuration (New-TimeSpan -Days 1)).Repetition\n"
                  'Register-ScheduledTask -TaskName "MT5-Y" -Action $a -Trigger $trigger\n',
                  "utf-8")
    assert cbt.installer_triggers(tmp_path)["MT5-Y"] == [("desks/mt5/scripts/install_y.ps1", 60)]


def test_every_known_drift_still_resolves_to_its_recorded_period() -> None:
    out = cbt.check()
    assert out["stale_known_trigger_drift"] == []
    assert len(cbt.KNOWN_TRIGGER_DRIFT) <= cbt.MAX_KNOWN_TRIGGER_DRIFT == 5
    # Pinned EQUAL to the measured blind spot: a fixed site forces the constant down, and
    # raising a constant to admit a new blind site fails here.
    assert len(out["unresolved_registrations"]) == cbt.MAX_UNRESOLVED_REGISTRATIONS == 5
    assert len(out["uncompared_triggers"]) == cbt.MAX_UNCOMPARED_TRIGGERS == 11
    assert not [p for p in out["problems"] if "trigger" in p.lower() or "Register" in p]


def _fixture(tmp_path: Path, monkeypatch, minutes: int) -> None:
    ps = tmp_path / "desks" / "mt5" / "scripts" / "install_z.ps1"
    ps.parent.mkdir(parents=True, exist_ok=True)
    ps.write_text(f"$t = New-ScheduledTaskTrigger -Once -At $x `\n"
                  f"    -RepetitionInterval (New-TimeSpan -Minutes {minutes})\n"
                  'Register-ScheduledTask -TaskName "MT5-Z" -Action $a -Trigger $t\n', "utf-8")
    monkeypatch.setattr(cbt, "manifest_rows", lambda path=None: [
        {"name": "MT5-Z", "trigger": "every 1 hour", "installer": "NONE"}])
    monkeypatch.setattr(cbt, "KNOWN_TRIGGER_DRIFT", {"MT5-Z": 15})


def test_a_listed_drift_is_exempt_only_at_its_recorded_period(tmp_path: Path,
                                                              monkeypatch) -> None:
    _fixture(tmp_path, monkeypatch, 15)
    assert cbt.check(tmp_path)["installer_trigger_drift"] == []
    _fixture(tmp_path, monkeypatch, 5)
    out = cbt.check(tmp_path)
    assert out["installer_trigger_drift"] and out["stale_known_trigger_drift"] == ["MT5-Z"]


def test_a_fixed_drift_left_in_the_list_is_a_breach(tmp_path: Path, monkeypatch) -> None:
    _fixture(tmp_path, monkeypatch, 60)
    out = cbt.check(tmp_path)
    assert out["installer_trigger_drift"] == [] and out["stale_known_trigger_drift"] == ["MT5-Z"]
    assert any("no longer resolves" in p for p in out["problems"])


def test_a_literal_task_name_variable_resolves_and_a_loop_variable_is_counted(
        tmp_path: Path) -> None:
    ps = tmp_path / "desks" / "mt5" / "scripts" / "install_w.ps1"
    ps.parent.mkdir(parents=True)
    ps.write_text("param([string]$TaskName = 'MT5-W')\n"
                  "$trigger = New-ScheduledTaskTrigger -Daily -At $x\n"
                  "Register-ScheduledTask -TaskName $TaskName -Action $a -Trigger $trigger\n"
                  "foreach ($lane in $lanes) {\n"
                  "    Register-ScheduledTask -TaskName $lane.Name -Action $a -Trigger $trigger\n"
                  "}\n", "utf-8")
    regs, unresolved = cbt.installer_scan(tmp_path)
    assert regs == {"MT5-W": [("desks/mt5/scripts/install_w.ps1", 1440)]}
    assert unresolved == ["desks/mt5/scripts/install_w.ps1:5"]


def test_a_task_name_also_assigned_a_computed_value_stays_unresolved(tmp_path: Path) -> None:
    ps = tmp_path / "desks" / "mt5" / "scripts" / "install_v.ps1"
    ps.parent.mkdir(parents=True)
    ps.write_text("param([string]$TaskName = 'MT5-V')\n"
                  "if ($Lane) { $TaskName = \"MT5-V$Lane\" }\n"
                  "$trigger = New-ScheduledTaskTrigger -Daily -At $x\n"
                  "Register-ScheduledTask -TaskName $TaskName -Action $a -Trigger $trigger\n",
                  "utf-8")
    assert cbt.installer_scan(tmp_path) == ({}, ["desks/mt5/scripts/install_v.ps1:4"])
