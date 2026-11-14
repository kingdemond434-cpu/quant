"""The CRO cycle's own two lanes must be a clock the missing-task fence can see.

MEASURED ON THE BOX 2026-11-14. `desks/mt5/reports/SCHEDULED_TASKS.json` read
`n_declared: 26, n_present: 26, n_missing: 0` -- a complete clock -- while `MT5-CycleMidnight`
had never run once in its life: no `desks/mt5/data/cycle_state_midnight.json` had ever existed on
the box, and all 108 rows of `cro_cycle_ledger.jsonl` were the noon lane's.

The cause was a gap between two installers, each correct on its own. `Install-QuantWindows.ps1`
keeps the lanes OUT of its table on purpose (they run S4U as the account holding the claude/codex
logins, not SYSTEM, and fire hourly behind a Europe/Dublin window) and hands them to
`install_cro_cycle_tasks.ps1`. `check_scheduled_tasks.declared()` read only the main installer
plus a hand-written EXTRA_DECLARED tuple for exactly this case -- and nobody added them.

Why it mattered more than one absent task: CRO_CYCLE step 2 makes each lane the independent check
on the other lane's material work. With the midnight lane gone, every noon pass has been
unverified by anyone, and the fence whose whole purpose is to see an absent clock reported the set
complete. This test pins the lanes into the declaration so that absence is MEASURED, which is the
only state from which it can be fixed.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
LANES = ("MT5-CycleNoon", "MT5-CycleMidnight")


def _check() -> Any:
    path = ROOT / "scripts" / "check_scheduled_tasks.py"
    spec = importlib.util.spec_from_file_location("check_scheduled_tasks_lanes", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_both_cro_lanes_are_declared_tasks() -> None:
    declared = _check().declared()
    for lane in LANES:
        assert lane in declared, f"{lane} is not a declared clock: its absence cannot be seen"


def test_the_lane_names_come_from_the_installer_that_owns_them() -> None:
    """Read, never hard-coded -- `declared()`'s own rule: "never a second list"."""
    module = _check()
    assert module._cro_lanes() == set(LANES)
    assert not set(LANES) & set(module.EXTRA_DECLARED), "the names belong to the installer"
    src = module.CRO_INSTALLER.read_text("utf-8")
    for lane in LANES:
        assert re.search(rf"Name\s*=\s*'{lane}'", src), lane


def test_an_unreadable_cro_installer_declares_nothing_rather_than_a_guessed_name(
        monkeypatch) -> None:
    module = _check()
    monkeypatch.setattr(module, "CRO_INSTALLER", ROOT / "does" / "not" / "exist.ps1")
    assert module._cro_lanes() == set()
    # The main installer's own declaration is unaffected by the CRO installer being unreadable.
    assert "MT5-Hourly" in module.declared()


def test_the_main_installer_still_hands_the_lanes_to_the_cro_installer() -> None:
    """If this ever changes, the two scans above are reading the wrong file."""
    src = (ROOT / "desks" / "mt5" / "scripts" / "Install-QuantWindows.ps1").read_text("utf-8")
    assert "install_cro_cycle_tasks.ps1" in src
    for lane in LANES:
        assert not re.search(rf'Name\s*=\s*"{lane}"', src), f"{lane} is in the main table now"


# ------------------------------------------------- a clock that will never tick

def test_a_present_enabled_task_that_never_ran_and_has_no_next_run_is_a_defect() -> None:
    """MT5-CycleMidnight's own scheduler record, 2026-11-14, read verbatim from the box.

    It was PRESENT and "Ready" inside a report whose headline was 26 of 26 present and 0 missing
    -- while the scheduler said LastRunTime 11/30/1999 (the never sentinel), LastTaskResult 267011
    (SCHED_S_TASK_HAS_NOT_RUN), NextRunTime null and NumberOfMissedRuns 0. The lane had produced
    no checkpoint and no ledger row in its entire existence, and nothing in the repository could
    say why, because presence and the word "Ready" were all this fence ever looked at.
    """
    m = _check()
    assert m.never_fires({"state": "Ready", "next_run": "", "last_run": "11/30/1999 00:00:00",
                          "last_result": "267011"})


def test_the_six_legitimate_no_next_run_tasks_on_this_box_are_not_flagged() -> None:
    """Measured over 117 MT5/E8 tasks: seven carry no NextRunTime and only ONE is a defect.

    A guard whose first output is a false positive is a guard the next person switches off --
    this file's sibling `stuck_writers` learned that from `sshd.exe`, so the rule is sized to fire
    once on this box rather than seven times.
    """
    m = _check()
    # Four long-running residents: no next run BECAUSE they are running (SCHED_S_TASK_RUNNING).
    for name, last in (("E8-Spreads", "11/14/2026 12:30:21"),
                       ("MT5-DeskDashboard", "11/12/2026 12:24:28"),
                       ("MT5-DeskTunnel", "11/12/2026 12:24:28"),
                       ("MT5-NewsDesk", "11/12/2026 12:24:28")):
        assert not m.never_fires({"state": "Running", "next_run": "", "last_run": last,
                                  "last_result": "267009"}), name
    # Two that have genuinely run and finished, one successfully and one not.
    assert not m.never_fires({"state": "Ready", "next_run": "",
                              "last_run": "09/21/2026 23:14:41", "last_result": "0"})
    assert not m.never_fires({"state": "Ready", "next_run": "",
                              "last_run": "09/25/2026 04:04:49", "last_result": "1"})


def test_a_task_with_a_next_run_or_an_unreadable_record_is_never_flagged() -> None:
    """A tick in the future is not a defect, and a failed read may not manufacture a red."""
    m = _check()
    assert not m.never_fires({"state": "Ready", "next_run": "11/14/2026 14:42:00",
                              "last_run": "11/30/1999 00:00:00", "last_result": "267011"})
    assert not m.never_fires({})                                   # nothing measured at all
    assert not m.never_fires({"state": "Ready", "next_run": "", "last_run": "",
                              "last_result": ""})                  # info query returned nothing
    assert not m.never_fires({"state": "Disabled", "next_run": "", "last_run": "",
                              "last_result": "267011"})            # DISABLED has its own verdict


def test_a_never_fired_clock_exits_nonzero_like_an_absent_one() -> None:
    m = _check()
    base: dict[str, list] = {"missing": [], "never_fired": [], "stuck_git_writers": []}
    assert not m._defects(base)
    assert m._defects(dict(base, never_fired=[{"task": "MT5-CycleMidnight"}]))
    assert m._defects(dict(base, missing=[{"task": "X"}]))
