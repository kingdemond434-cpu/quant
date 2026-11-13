"""Every manifested box task with an installer has a REAL one, and installer=NONE cannot come back.

THE DEFECT THIS PINS (2026-11-13). Six tasks in `desks/mt5/ops/box_tasks.manifest` --
MT5-AllocatorPulse, MT5-VolArchive, MT5-PrivateNetAudit, MT5-GoldHourSweep, MT5-CertHygiene and
MT5-DashMirror -- carried `installer="NONE"`, so a rebuilt box would never run them and nothing
would say so. Five now have an installer; MT5-DashMirror stays NONE on purpose (it mirrors the
trading box FROM another box, and on the trading box it would scp live files onto themselves).
This file fences four things:

  * every row naming an installer points at a file that exists and NAMES the task;
  * the count of installer=NONE rows never rises (`check_box_tasks.MAX_NO_INSTALLER`);
  * each of the five installers registers what the manifest says it does -- the runner, the
    cadence, the principal -- and is idempotent (replaces, or -IfMissing no-ops).

There is no pwsh on the research host (tests/ops/test_powershell_drive_variable.py parses every
.ps1 when there is), so these read the PowerShell rather than run it.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import check_box_tasks as cbt  # noqa: E402

SCRIPTS = ROOT / "desks" / "mt5" / "scripts"

#: task -> (installer, runner token the action must carry, trigger phrase the manifest declares)
FIVE = {
    "MT5-AllocatorPulse": ("install_allocator_pulse_task.ps1",
                           "allocator_trigger.py",
                           "at startup + every 5 minutes (keep-alive of a 24/7 resident)"),
    "MT5-VolArchive": ("install_vol_archive_task.ps1", "recorders.vol_archive",
                       "every 1 hour, at :40"),
    "MT5-PrivateNetAudit": ("install_private_net_audit_task.ps1", "install_private_net.ps1",
                            "daily at 06:40"),
    "MT5-GoldHourSweep": ("install_gold_hour_sweep_task.ps1", "run_gold_hour_sweep.cmd",
                          "daily 03:30"),
    "MT5-CertHygiene": ("install_cert_hygiene_task.ps1", "certificate_hygiene.py",
                        "daily 03:50"),
}


def _rows() -> dict[str, dict[str, str]]:
    return {r["name"]: r for r in cbt.manifest_rows()}


def _src(name: str) -> str:
    return (SCRIPTS / name).read_text("utf-8")


def test_every_manifest_installer_exists_and_names_its_task() -> None:
    out = cbt.check()
    assert out["installers_not_in_repo"] == [], out["installers_not_in_repo"]
    assert out["installers_not_naming_task"] == [], out["installers_not_naming_task"]


def test_installer_none_never_rises() -> None:
    out = cbt.check()
    assert len(out["no_installer"]) <= cbt.MAX_NO_INSTALLER, (
        f"{len(out['no_installer'])} rows carry installer=NONE, ratchet {cbt.MAX_NO_INSTALLER}")
    assert not [p for p in out["problems"] if "installer" in p or "ratchet" in p], out["problems"]


def test_the_ratchet_actually_fires(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = tmp_path / "box_tasks.manifest"
    rows = "\n".join(f'TASK name="MT5-Fake{i}x" trigger="hourly" runs="UNKNOWN" '
                     f'installer="NONE" lane="ops"' for i in range(cbt.MAX_NO_INSTALLER + 1))
    m.write_text(rows + "\n", "utf-8")
    monkeypatch.setattr(cbt, "MANIFEST", m)
    out = cbt.check(tmp_path)
    assert any("installer=NONE" in p for p in out["problems"]), out["problems"]


@pytest.mark.parametrize("task", sorted(FIVE))
def test_each_of_the_five_has_its_installer(task: str) -> None:
    installer, runner, trigger = FIVE[task]
    row = _rows()[task]
    assert row["installer"] == f"desks/mt5/scripts/{installer}"
    assert row["trigger"] == trigger
    assert row["trigger"] != "UNDECLARED" and row["runs"] != "UNKNOWN"
    src = _src(installer)
    assert f"$TaskName = '{task}'" in src
    assert runner in src
    # Idempotent: an existing registration is replaced, and -IfMissing is the no-op form.
    assert "[switch]$IfMissing" in src or "[switch] $IfMissing" in src
    assert "Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false" in src
    assert "Register-ScheduledTask -TaskName $TaskName" in src
    assert "-MultipleInstances IgnoreNew" in src
    # No secret, no address: nothing that looks like a key, a token or an IPv4 literal.
    assert not re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", src)
    assert not re.search(r"(?i)(api[_-]?key|password|token)\s*=", src)


def test_the_cadences_are_the_ones_registered() -> None:
    assert "-AtStartup" in _src(FIVE["MT5-AllocatorPulse"][0])
    assert "-RepetitionInterval (New-TimeSpan -Minutes 5)" in _src(FIVE["MT5-AllocatorPulse"][0])
    assert "--resident --interval-s 20" in _src(FIVE["MT5-AllocatorPulse"][0])
    assert "[TimeSpan]::Zero" in _src(FIVE["MT5-AllocatorPulse"][0])
    assert ".AddHours(6).AddMinutes(40)" in _src(FIVE["MT5-PrivateNetAudit"][0])
    assert ".AddHours(3).AddMinutes(30)" in _src(FIVE["MT5-GoldHourSweep"][0])
    assert ".AddHours(3).AddMinutes(50)" in _src(FIVE["MT5-CertHygiene"][0])
    assert "--apply" in _src(FIVE["MT5-CertHygiene"][0])


def test_principals() -> None:
    for task in ("MT5-AllocatorPulse", "MT5-PrivateNetAudit", "MT5-GoldHourSweep",
                 "MT5-CertHygiene"):
        assert "-UserId 'SYSTEM' -LogonType ServiceAccount" in _src(FIVE[task][0]), task
    assert "-LogonType S4U" in _src(FIVE["MT5-VolArchive"][0])


def test_private_net_audit_never_schedules_enforcement() -> None:
    src = _src(FIVE["MT5-PrivateNetAudit"][0])
    action = src[src.index("$action ="):src.index("$trigger =")]
    for switch in ("-Enforce", "-Confirm", "-Rollback"):
        assert switch not in action


def test_vol_archive_agrees_with_install_tape_tasks() -> None:
    """Two files register MT5-VolArchive; they must never disagree about what it runs or when."""
    tape = (ROOT / "desks" / "mt5" / "recorders" / "install_tape_tasks.ps1").read_text("utf-8")
    block = tape[tape.index('-Name "MT5-VolArchive"'):]
    assert '"recorders.vol_archive"' in block[:200]
    assert "AddMinutes(40)" in block[:300]
    va = _src(FIVE["MT5-VolArchive"][0])
    assert "'-3 -m recorders.vol_archive'" in va
    assert va.count("AddMinutes(40)") == 2
    assert "(New-TimeSpan -Hours 1)" in va


def test_installers_avoid_the_known_powershell_traps() -> None:
    for installer, _, _ in FIVE.values():
        src = _src(installer)
        # `$x:` inside a double-quoted string is a parse error (test_powershell_drive_variable).
        assert not re.search(r'"[^"\n]*(?<![`{])\$(?!env\b)[A-Za-z_]\w*:(?!:)[^"\n]*"', src)
        # A -Once repetition with no duration expires; the repeating shape copies onto -Daily.
        if "RepetitionInterval" in src:
            assert "New-ScheduledTaskTrigger -Daily" in src and ".Repetition = (" in src
        # The [TimeSpan]::MaxValue duration is rejected by the Task Scheduler service.
        assert "MaxValue" not in src


def test_dash_mirror_is_never_installed_on_the_trading_box() -> None:
    """Auditor HOLD 2026-11-13: dash_mirror.cmd copies QUANT_BOX_HOST:C:/opt/quant/<p> onto the same
    local path. QUANT_BOX_HOST is the trading box, so registering it there truncates live files."""
    row = _rows()["MT5-DashMirror"]
    assert row["installer"] == "NONE"
    assert not (SCRIPTS / "install_dash_mirror_task.ps1").exists()
