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
    ps.write_text("$trigger = New-ScheduledTaskTrigger -Daily -At ((Get-Date).Date.AddMinutes(12))\n"
                  "$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At $x `\n"
                  "    -RepetitionInterval (New-TimeSpan -Hours 1) `\n"
                  "    -RepetitionDuration (New-TimeSpan -Days 1)).Repetition\n"
                  'Register-ScheduledTask -TaskName "MT5-Y" -Action $a -Trigger $trigger\n',
                  "utf-8")
    assert cbt.installer_triggers(tmp_path)["MT5-Y"] == [("desks/mt5/scripts/install_y.ps1", 60)]
