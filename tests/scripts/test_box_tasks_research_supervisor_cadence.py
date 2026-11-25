"""THE MANIFEST DECLARES MT5-ResearchSupervisor AS THE INSTALLER REGISTERS IT.

Reconciled 2026-10-21. `box_tasks.manifest` said "every 30 minutes, at :26" with installer NONE,
while `Install-QuantWindows.ps1` has its own Register-ScheduledTask block for the task with a
5-minute repetition. The manifest is the DR floor's declaration; it now matches the installer,
whose cadence was not changed. If either side moves, this fails until the other follows.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "desks" / "mt5" / "ops" / "box_tasks.manifest"
INSTALLER_REL = "desks/mt5/scripts/Install-QuantWindows.ps1"


def _row() -> dict[str, str]:
    for line in MANIFEST.read_text("utf-8").splitlines():
        if line.startswith('TASK name="MT5-ResearchSupervisor"'):
            return dict(re.findall(r'(\w+)="([^"]*)"', line))
    raise AssertionError("MT5-ResearchSupervisor has no manifest line")


def _installer_minutes() -> int:
    src = (ROOT / INSTALLER_REL).read_text("utf-8", errors="ignore")
    block = src[src.index("$supervisor = Join-Path $DeskRoot"):
                src.index('Register-ScheduledTask -TaskName "MT5-ResearchSupervisor"')]
    m = re.search(r"\$supTrigger\s*=.*?-RepetitionInterval\s*\(New-TimeSpan\s+-Minutes\s+(\d+)\)",
                  block, re.S)
    assert m, "the installer's supervisor trigger moved; re-read it before declaring a cadence"
    return int(m.group(1))


def test_the_manifest_names_the_installer_that_registers_it() -> None:
    assert _row()["installer"] == INSTALLER_REL
    assert (ROOT / INSTALLER_REL).exists()


def test_the_declared_cadence_is_the_registered_one() -> None:
    minutes = _installer_minutes()
    assert minutes == 5, "installer cadence changed; this reconciliation must not change it"
    trigger = _row()["trigger"]
    assert trigger.startswith(f"every {minutes} minutes"), (
        f"manifest declares {trigger!r}; the installer registers every {minutes} minutes")
    assert "30 minutes" not in trigger
