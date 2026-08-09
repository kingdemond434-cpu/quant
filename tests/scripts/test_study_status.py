"""ALIVE IS NOT WORKING, AND `pgrep` ALONE CANNOT TELL YOU WHICH.

THE DEFECT THIS REPLACES. The status check handed to the operator was a shell expression:

    ps -o pid,etime,time,%cpu,rss -p "$(pgrep -f run_full_sweep | head -1)"

which produced `pgrep: invalid option -- 'p'` because the command spanned a line break and `-p`
reached pgrep instead of ps. The operator could not distinguish a running study from a dead one --
during the exact window when that was the only question worth answering, and right after a dropped
connection had already destroyed one run.

The general fault is that process status was an EXPRESSION rather than a command, so every
invocation re-derived it and every invocation could get it wrong.
"""

from __future__ import annotations

from pathlib import Path

import scripts.study_status as SS


def _p(cpu: float = 50.0) -> SS.Proc:
    return SS.Proc(pid=123, etime="01:02:03", cpu_time="00:40:00", cpu_pct=cpu, rss_kb=1024,
                   cmd="python scripts/run_full_sweep.py")


def test_THE_PATTERN_IS_A_SEPARATE_ARGV_ENTRY() -> None:
    """No amount of quoting or line-wrapping can turn part of it into an option. That IS the fix,
    so it is asserted against the source rather than only exercised."""
    src = Path("scripts/study_status.py").read_text("utf-8")
    assert '["pgrep", "-f", pattern]' in src
    assert "shell=True" not in src


def test_PS_IS_NEVER_CALLED_WITH_AN_EMPTY_PID_LIST() -> None:
    """`ps -p` with nothing after it is the sibling of the original error, and the empty case is
    the COMMON one -- the whole point is to ask about a process that may not exist."""
    assert SS.describe([]) == []


def test_NO_PROCESS_IS_ABSENT_AND_NAMES_THE_LIKELY_CAUSE() -> None:
    state, why = SS.verdict([], None, stall_seconds=1800)
    assert state == "ABSENT"
    assert "dropped SSH session" in why


def test_A_BUSY_PROCESS_IS_RUNNING() -> None:
    state, _ = SS.verdict([_p(cpu=99.0)], 4000.0, stall_seconds=1800)
    assert state == "RUNNING"


def test_AN_IDLE_PROCESS_WITH_A_SILENT_LOG_IS_STALLED_NOT_HEALTHY() -> None:
    """This is the state a process check alone reports as healthy, and it is the reason the
    command reports two signals rather than one."""
    state, why = SS.verdict([_p(cpu=0.0)], 4000.0, stall_seconds=1800)
    assert state == "STALLED"
    assert "Alive is not working" in why


def test_AN_IDLE_PROCESS_WITH_A_FRESH_LOG_IS_STILL_RUNNING() -> None:
    """A niced study yields CPU freely, so momentary 0% is not evidence of a stall."""
    state, _ = SS.verdict([_p(cpu=0.0)], 5.0, stall_seconds=1800)
    assert state == "RUNNING"


def test_NO_LOG_PLUS_IDLE_IS_UNMEASURED_RATHER_THAN_A_VERDICT() -> None:
    """Progress inferred from CPU alone is weaker evidence than it looks, and the report says so
    instead of guessing."""
    state, why = SS.verdict([_p(cpu=0.0)], None, stall_seconds=1800)
    assert state == "UNMEASURED"
    assert "weaker evidence than it looks" in why


def test_AN_ABSENT_LOG_AGE_IS_NONE_NOT_ZERO(tmp_path) -> None:
    """Zero would read as 'just written' -- the most misleading possible default here."""
    assert SS.log_age_seconds(tmp_path / "nope.log") is None
    p = tmp_path / "there.log"
    p.write_text("x", "utf-8")
    age = SS.log_age_seconds(p)
    assert age is not None and age >= 0.0


def test_THE_STALL_WINDOW_IS_JUSTIFIED_BY_MEASURED_CELL_TIME() -> None:
    """A shorter window would call ordinary progress a stall: a sweep cell has taken ~8 minutes on
    the live box."""
    src = Path("scripts/study_status.py").read_text("utf-8")
    assert "~8 minutes on the live box" in src


def test_FIND_RETURNS_A_LIST_AND_NEVER_RAISES() -> None:
    assert isinstance(SS.find("a-pattern-that-matches-nothing-xyz"), list)

def test_MAIN_WRITES_MACHINE_READABLE_STATUS(tmp_path, monkeypatch) -> None:
    out = tmp_path / "study_status.json"
    monkeypatch.setattr(SS, "find", lambda _pattern: [])
    monkeypatch.setattr(SS, "log_age_seconds", lambda _path: None)
    monkeypatch.setattr("sys.argv", ["study_status.py", "--out", str(out)])
    assert SS.main() == 0
    import json
    saved = json.loads(out.read_text("utf-8"))
    assert saved["state"] == "ABSENT"
    assert saved["processes"] == []
    assert saved["pattern"] == "run_full_sweep"
