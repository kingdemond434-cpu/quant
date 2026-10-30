"""The moat backup and its restore drill have a clock on the trading box.

THE DEFECT THIS PINS (2026-10-29). scripts/run_moat_backup.py and scripts/run_restore_drill.py
were scheduled only by Linux timers on the old VPS, never by a Windows task, so the replica in
backups/moat/ stopped at 2026-08-29 and the 10-27 restore drill failed against it. Parsed from the
PowerShell source: this suite runs on Linux in CI.
"""
from __future__ import annotations

import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
REPO = BASE.parent.parent
INSTALLER = BASE / "scripts" / "install_moat_backup_tasks.ps1"


def _jobs() -> dict[str, str]:
    text = INSTALLER.read_text("utf-8")
    return dict(re.findall(r"Name = '([^']+)'; Script = '([^']+)'", text))


def test_both_organs_are_registered_and_their_scripts_exist() -> None:
    jobs = _jobs()
    assert jobs == {
        "MT5-MoatBackup": r"scripts\run_moat_backup.py",
        "MT5-RestoreDrill": r"scripts\run_restore_drill.py",
    }
    for script in jobs.values():
        assert (REPO / script.replace("\\", "/")).is_file(), script


def test_each_task_runs_from_the_repository_root_and_never_stacks() -> None:
    """A relative script path with no working directory runs nothing (lesson l0294)."""
    text = INSTALLER.read_text("utf-8")
    assert "cd /d $repo" in text and "-WorkingDirectory $repo" in text
    assert "-MultipleInstances IgnoreNew" in text
    assert "-Daily -At '06:40'" in text
    assert "-Weekly -DaysOfWeek Sunday -At '07:20'" in text


def test_neither_task_runs_in_the_money_window() -> None:
    """01:00-05:00Z holds the gold Asia placements and the money-path quiet window."""
    text = INSTALLER.read_text("utf-8")
    for hh in re.findall(r"-At '(\d\d):\d\d'", text):
        assert not 1 <= int(hh) < 5, hh


def test_the_installer_never_names_secrets() -> None:
    assert "secrets" not in INSTALLER.read_text("utf-8").lower().replace(
        "neither reads data/secrets", ""
    )
