"""The two daily lanes: they must resume, they must not stack, and they must not lie when idle.

Two autonomous passes run twelve hours apart against this repository and the live box. What is
pinned here is the wiring and the failure behaviour -- what the agents actually DO is in
`docs/DESK_CYCLE_PROMPT.md`, which is prose on purpose and not something a test can judge.

THE FAILURE THIS DESK ALREADY PAID FOR, and the reason the launcher exits non-zero when its CLI
is missing: `MT5-ShadowSync` fired every fifteen minutes and returned exit 0 while publishing
nothing for thirty-three hours, because its skip branch exited 0 when the sources were absent.
Publishing nothing and publishing successfully were byte-identical to every watchdog. A scheduled
task that cannot do its job must say so in its exit code.
"""
from __future__ import annotations

import re
from pathlib import Path

DESK = Path(__file__).resolve().parent.parent
REPO = DESK.parent.parent
LAUNCHER = DESK / "scripts" / "Run-DeskCycle.ps1"
PROMPT = REPO / "docs" / "DESK_CYCLE_PROMPT.md"
INSTALLER = DESK / "scripts" / "Install-QuantWindows.ps1"


def _installer() -> str:
    return INSTALLER.read_text("utf-8")


def _block(name: str) -> str:
    m = re.search(rf'@\{{\s*Name\s*=\s*"{re.escape(name)}"(.*?)(?=@\{{\s*Name\s*=|\n\)\n)',
                  _installer(), re.S)
    assert m, f"{name} is not in the installer table"
    return m.group(1)


# ------------------------------------------------------------------ the pair exists
def test_both_lanes_are_registered() -> None:
    for name in ("MT5-CycleNoon", "MT5-CycleMidnight"):
        assert f'Name = "{name}"' in _installer()


def test_the_lanes_run_at_noon_and_midnight_twelve_hours_apart() -> None:
    assert '-Daily -At "12:00"' in _block("MT5-CycleNoon")
    assert '-Daily -At "00:00"' in _block("MT5-CycleMidnight")


def test_each_lane_passes_its_own_lane_argument() -> None:
    """The lane selects a slot and a checkpoint file -- not a scope.

    Both passes run the complete prompt. The argument still matters: without it the two lanes
    would share one checkpoint and the midnight pass would read noon's DONE and exit.
    """
    assert "-Lane noon" in _block("MT5-CycleNoon")
    assert "-Lane midnight" in _block("MT5-CycleMidnight")


# ------------------------------------------------------------------ resumption
def test_both_lanes_repeat_hourly_so_an_interrupted_pass_resumes_within_the_hour() -> None:
    """Without repetition, a pass killed by the time limit waits a full DAY to continue.

    The daily trigger alone gives a 24-hour recovery window; hourly repetition makes it one hour,
    and a healthy box pays for that with cheap no-ops that exit on a single file read.
    """
    for name in ("MT5-CycleNoon", "MT5-CycleMidnight"):
        block = _block(name)
        assert "RepetitionInterval (New-TimeSpan -Hours 1)" in block, name


def test_the_repetition_stops_before_the_other_lane_starts() -> None:
    """Eleven hours, not twelve.

    At twelve the noon lane would still be waking up as midnight begins, and two agents in one
    repository is exactly what the lane split exists to prevent.
    """
    for name in ("MT5-CycleNoon", "MT5-CycleMidnight"):
        block = _block(name)
        m = re.search(r"RepetitionDuration \(New-TimeSpan -Hours (\d+)\)", block)
        assert m, f"{name} declares no repetition duration"
        assert int(m.group(1)) < 12, f"{name} repeats into the other lane's slot"


def test_the_time_limit_leaves_room_for_the_other_lane() -> None:
    for name in ("MT5-CycleNoon", "MT5-CycleMidnight"):
        m = re.search(r"TimeLimit = \(New-TimeSpan -Hours (\d+)\)", _block(name))
        assert m and int(m.group(1)) <= 11, f"{name} may still be running when the other starts"


def test_a_second_instance_is_refused_by_the_scheduler_and_by_the_script() -> None:
    """Hourly repetition plus a slow pass is a stack unless something says no -- twice.

    The scheduler setting is not readable from the script, and the script's check is not visible
    in the task list, so both exist.
    """
    assert "-MultipleInstances IgnoreNew" in _installer()
    src = LAUNCHER.read_text("utf-8")
    assert "ALREADY RUNNING" in src
    assert "Test-ProcessAlive" in src


def test_done_is_only_set_on_a_clean_exit() -> None:
    """Marking DONE on a bad exit silently converts an interrupted pass into a finished one, and
    the stages it never reached would wait a full day."""
    src = LAUNCHER.read_text("utf-8")
    assert 'status = "DONE"' in src
    # the DONE write must be inside the rc==0 branch, and a resumable write must exist for the rest
    assert re.search(r"if \(\$code -eq 0\)(.|\n)*?status = \"DONE\"", src)
    assert "left RESUMABLE" in src


def test_a_finished_lane_exits_immediately_instead_of_re_running() -> None:
    src = LAUNCHER.read_text("utf-8")
    assert "already DONE" in src


def test_an_unreadable_checkpoint_starts_fresh_rather_than_crashing() -> None:
    """A corrupt state file must not be able to stop the desk's daily pass forever."""
    src = LAUNCHER.read_text("utf-8")
    assert "catch { return $null }" in src


# ------------------------------------------------------------------ honest failure
def test_a_missing_agent_cli_exits_non_zero() -> None:
    """The MT5-ShadowSync defect, refused by design: a task that cannot do its job must not
    report success, or the task list stays green while nothing runs."""
    src = LAUNCHER.read_text("utf-8")
    assert "exit 3" in src
    assert "is not on PATH" in src
    assert re.search(r"exit 0\s*\n\s*\}\s*\n\s*if \(\$state\.status -eq \"RUNNING\" -and", src) \
        or "already DONE" in src          # the only legitimate early exit-0 is a finished lane


def test_a_missing_prompt_is_fatal() -> None:
    """Running an agent against this repository with no brief is worse than not running one."""
    src = LAUNCHER.read_text("utf-8")
    assert "refusing to run an agent with no brief" in src
    assert "exit 2" in src


def test_the_launcher_guards_native_stderr() -> None:
    """Same trap that killed Adopt-Release: agent progress on stderr must not terminate the pass."""
    src = LAUNCHER.read_text("utf-8")
    assert '$ErrorActionPreference = "Continue"' in src


# ------------------------------------------------------------------ the brief itself
def test_the_prompt_exists_and_states_the_laws() -> None:
    text = PROMPT.read_text("utf-8")
    for law in ("No gate, threshold, floor or law is ever loosened",
                "Never raise leverage or size by fiat",
                "Never resolve a merge conflict by picking a winner",
                "never leaves the box",
                "Targeted `git add` only",
                "MT5 universe mandate",
                "UNMEASURED is a verdict"):
        assert law in text, f"the prompt no longer states: {law}"


def test_the_prompt_names_both_lanes_and_the_checkpoint() -> None:
    text = PROMPT.read_text("utf-8")
    assert "NOON" in text and "MIDNIGHT" in text
    assert "Both lanes do everything below" in text
    assert "cycle_state_<lane>.json" in text
    assert "Do not redo them" in text


def test_the_prompt_requires_a_fixer_and_a_refusal_record() -> None:
    """The two things that make a pass compound instead of repeat."""
    text = PROMPT.read_text("utf-8")
    assert "Every repair ships with a fixer" in text
    assert "Refusals are output, not silence" in text
    assert "desk_lessons.jsonl" in text


def test_the_prompt_makes_the_checklist_a_floor() -> None:
    """A pass that only checks the board can only find what something else already found."""
    text = PROMPT.read_text("utf-8")
    assert "The board is the floor, not the ceiling" in text
    assert "Optimal, not merely working" in text


def test_the_prompt_closes_canonically() -> None:
    """Two lanes a day producing forks is how a desk ends up with several quants and no quant."""
    text = PROMPT.read_text("utf-8")
    assert "The canonical close" in text
    assert "Reconcile, never overwrite" in text
    assert "Seal alone" in text
    assert "running SHA == RELEASE.code_sha" in text
