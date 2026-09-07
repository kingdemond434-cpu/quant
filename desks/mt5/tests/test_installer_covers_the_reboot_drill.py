"""The installer must be able to build every task the reboot drill demands.

THE DEFECT THIS PINS. `ops/reboot_drill.ps1` has always required eleven scheduled tasks and
`Install-QuantWindows.ps1` only ever registered five. Nothing connected the two lists, so a box
rebuilt from the canonical installer passed the installer and then failed its own drill -- and
the six it could not build are precisely the ones whose absence is silent: the dashboard
publisher, the git publisher, the stall watchdog, the gauntlet and the two moat organs. A desk
missing those keeps computing and simply stops being seen, judged or healed.

Measured 2026-09-07: `data\\stall_watch.json` last written 2026-09-06T23:57 -- thirteen hours --
and `MT5-ShadowSync` is treated by `ops/box-repair.ps1` as a hard failure when absent, while the
only way to have had one was to remember a separate manual step.

Two properties, and the second matters as much as the first:

  1. every name the drill requires is either registered or EXPLICITLY excluded with a reason;
  2. every script the table names exists under one of the two roots the loop searches.

(2) is the one that bites quietly. A table entry whose path is wrong does not raise -- the loop
prints `[SKIP]` and the installer still exits reporting success, so the task is missing on a box
whose install "worked". `scripts/build_zentech_state.py` lives at the REPOSITORY root, not under
the desk, which is exactly how that happens.

Parsed from the PowerShell source rather than executed: this suite runs on Linux in CI, and the
property being checked is a property of the TABLE, not of the Windows Task Scheduler.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
REPO = BASE.parent.parent
INSTALLER = BASE / "scripts" / "Install-QuantWindows.ps1"
DRILL = REPO / "ops" / "reboot_drill.ps1"


def _installer_text() -> str:
    return INSTALLER.read_text("utf-8")


def _registered_names() -> set[str]:
    """Every task name the installer actually registers, by either route.

    TWO ROUTES, AND ONLY COUNTING ONE IS HOW A DUPLICATE GOT WRITTEN. Most tasks come from the
    `$tasks` table, but several have their own `Register-ScheduledTask` block further down --
    MT5-ShadowSync, MT5-ResearchSupervisor, MT5-RiskUnitsFence, MT5-QQuantGatesCertify -- because
    they need settings the table cannot express (an offset trigger, -MultipleInstances IgnoreNew,
    a daily schedule). A coverage check that reads only the table reports those as MISSING, which
    invites exactly the fix that broke it: adding a table row for a task that already had a
    better block, so both run and the surviving settings are a coin toss.
    """
    text = _installer_text()
    return (set(re.findall(r'@\{\s*Name\s*=\s*"([^"]+)"', text))
            | set(re.findall(r'Register-ScheduledTask\s+-TaskName\s+"([^"]+)"', text)))


def test_no_task_is_registered_by_both_routes() -> None:
    """A task in the table AND in its own block is registered twice, last writer wins.

    That is not harmless redundancy: the two registrations carry different triggers and settings,
    so which ones the box ends up running depends on statement order rather than on intent.
    """
    text = _installer_text()
    table = set(re.findall(r'@\{\s*Name\s*=\s*"([^"]+)"', text))
    blocks = set(re.findall(r'Register-ScheduledTask\s+-TaskName\s+"([^"]+)"', text))
    both = sorted(table & blocks)
    assert not both, f"registered twice, with different settings each time: {both}"


def _table_entries() -> list[tuple[str, str]]:
    """(name, script) for each table entry, with the PowerShell escaping undone.

    The table writes paths as PowerShell double-quoted strings, so `moat\\\\moat_silver.py` in the
    source is the single-backslash path `moat\\moat_silver.py`. Comparing the raw text against the
    filesystem without collapsing that would fail every entry written the escaped way and pass
    every entry written the other -- a test that measures quoting style rather than existence.
    """
    out: list[tuple[str, str]] = []
    for block in re.finditer(
        r'@\{\s*Name\s*=\s*"([^"]+)"(.*?)(?=@\{\s*Name\s*=|\n\)\n)',
        _installer_text(), re.S,
    ):
        name, body = block.group(1), block.group(2)
        m = re.search(r'Script\s*=\s*"([^"]+)"', body)
        if m:
            out.append((name, m.group(1).replace("\\\\", "\\")))
    return out


def _required_names() -> set[str]:
    """Task names `reboot_drill.ps1` fails the box for missing."""
    text = DRILL.read_text("utf-8")
    m = re.search(r"\$required\s*=\s*@\((.*?)\)", text, re.S)
    assert m, "reboot_drill.ps1 no longer declares a $required list"
    return set(re.findall(r"'([^']+)'", m.group(1)))


def test_every_required_task_is_registered_or_explicitly_excluded() -> None:
    required = _required_names()
    registered = _registered_names()
    text = _installer_text()

    unbuildable = sorted(required - registered)
    # An exclusion is only honest if the file SAYS why. A name that appears nowhere is an
    # oversight; a name that appears in the "NOT IN THIS TABLE" block is a decision.
    undocumented = [n for n in unbuildable if n not in text]
    assert not undocumented, (
        "reboot_drill.ps1 fails a box for missing these tasks, and Install-QuantWindows.ps1 "
        f"neither registers nor explains them: {undocumented}"
    )


def test_the_two_documented_exclusions_are_the_only_ones() -> None:
    # Pinned deliberately. Both are unresolved work, not permanent policy: MT5-TerminalBoot needs
    # an interactive logon (ops/box-repair.ps1 documents the schtasks fix) and MT5-Universe names
    # no script in this checkout. If either becomes registerable this test fails and asks for the
    # comment to go with it -- which is the point. What it must never do is grow quietly.
    assert sorted(_required_names() - _registered_names()) == [
        "MT5-TerminalBoot",
        "MT5-Universe",
    ]


@pytest.mark.parametrize(("name", "script"), _table_entries())
def test_every_table_entry_names_a_script_that_exists(name: str, script: str) -> None:
    rel = script.replace("\\", "/")
    if (BASE / rel).exists() or (REPO / rel).exists():
        return
    pytest.fail(
        f"{name} names {script}, which exists under neither {BASE} nor {REPO}. "
        "The installer prints [SKIP] for this and still exits reporting success, so the task "
        "would simply be absent on a box whose install appeared to work."
    )


def test_powershell_tasks_are_not_launched_through_the_python_interpreter() -> None:
    """A .ps1 run by python.exe reports a SyntaxError and task result 1.

    That is indistinguishable in the task history from a script that ran and found a problem,
    which is how a dead watchdog looks exactly like a busy one. The table carries `Kind` for
    this reason, and both PowerShell entries must declare it.
    """
    for name, script in _table_entries():
        if not script.lower().endswith(".ps1"):
            continue
        block = re.search(
            rf'@\{{\s*Name\s*=\s*"{re.escape(name)}"(.*?)(?=@\{{\s*Name\s*=|\n\)\n)',
            _installer_text(), re.S,
        )
        assert block, f"could not re-read the table entry for {name}"
        assert 'Kind = "ps1"' in block.group(1), (
            f'{name} runs {script} but does not declare Kind = "ps1", so the installer would '
            "hand a PowerShell script to the Python interpreter."
        )


def test_the_tick_recorder_is_not_killed_every_four_hours() -> None:
    """The default ExecutionTimeLimit is a ceiling for a PASS, not for a resident loop.

    `moat_recorder.py` is the permanent tape and holds a single-instance lock; the four-hour
    default would punch a four-hourly hole in the one dataset on this desk that cannot be
    re-obtained, because a tick nobody recorded is gone.
    """
    block = re.search(
        r'@\{\s*Name\s*=\s*"MT5-MoatRecorder"(.*?)(?=@\{\s*Name\s*=|\n\)\n)',
        _installer_text(), re.S,
    )
    assert block, "MT5-MoatRecorder is no longer in the installer table"
    assert "TimeLimit" in block.group(1), (
        "MT5-MoatRecorder must override the default 4-hour ExecutionTimeLimit"
    )
