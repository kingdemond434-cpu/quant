"""A STUDY MAY NOT BE TIED TO THE LIFETIME OF A TERMINAL.

MEASURED 2026-08-08 and it cost a real run. The full sweep started over SSH at 09:56Z and reached
~40% -- 359,424 of 898,560 candidates across 8 of 20 cells -- when the connection dropped
(`client_loop: send disconnect: Connection reset`). The studies ran in the FOREGROUND of the
invoking shell, so SIGHUP killed it. Afterwards: no process, no OOM line, no traceback, and no
`data/full_sweep.json`, because the report is only written at the end.

THE FAILURE MODE IS SILENT AND TOTAL. An hour of niced compute produced nothing, the eight cells
of results existed only in terminal scrollback, and every diagnostic the operator could run
afterwards showed a clean box. That is worse than a crash, which at least leaves a trace.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_SCRIPT = Path("ops/run_study_on_vps.sh")


@pytest.fixture(scope="module")
def src() -> str:
    return _SCRIPT.read_text("utf-8")


def test_AN_INTERACTIVE_RUN_RE_EXECS_DETACHED(src: str) -> None:
    assert "setsid nohup bash" in src, "a dropped SSH session must not be able to kill a study"
    assert "STUDY_DETACHED=1" in src, "the re-exec needs a guard or it recurses forever"


def test_THE_GUARD_TESTS_FOR_A_CONTROLLING_TERMINAL_NOT_FOR_A_TTY_STDOUT(src: str) -> None:
    """SIGHUP reaches the foreground process group of the CONTROLLING TERMINAL regardless of
    where stdout was redirected.

    `[ -t 1 ]` would take the inline path for `bash ops/run_study_on_vps.sh | tee run.log` -- the
    most natural way an operator would run this -- and that invocation is exactly as exposed to a
    dropped connection as the bare one. The first version of this guard had that bug.
    """
    guard = re.search(r"^if .*STUDY_DETACHED.*$", src, re.MULTILINE)
    assert guard, "the detach guard is gone"
    assert "/dev/tty" in guard.group(0)
    assert "-t 1" not in guard.group(0), "stdout-is-a-tty is the wrong test -- see the docstring"


def test_CRON_AND_SYSTEMD_ARE_UNAFFECTED(src: str) -> None:
    """They have no controlling terminal, so they take the inline path and the scheduled runs are
    byte-for-byte unchanged. A guard that altered them would be a change to the money-adjacent
    cadence disguised as an ergonomics fix."""
    assert "cron and systemd" in src


def test_THERE_IS_AN_EXPLICIT_OPT_OUT(src: str) -> None:
    """Debugging a study needs the inline path, and an escape hatch that is not named in the
    script is an escape hatch nobody finds."""
    assert "STUDY_FOREGROUND" in src
    assert "STUDY_FOREGROUND=1 runs inline" in src


def test_THE_OPERATOR_IS_TOLD_HOW_TO_FOLLOW_AND_STOP_IT(src: str) -> None:
    """Detaching without handing back the log path replaces one silent failure with another."""
    assert "follow:  tail -f" in src
    assert "stop:    kill" in src


def test_THE_DETACHED_RUN_WRITES_ITS_OWN_TIMESTAMPED_LOG(src: str) -> None:
    """Sharing one log across concurrent detached runs would interleave two studies into a record
    neither of them can be read out of."""
    assert 'data/study_runs_$(date -u +%Y%m%dT%H%M%SZ).log' in src


def test_THE_SCRIPT_STILL_PARSES() -> None:
    import subprocess
    r = subprocess.run(["bash", "-n", str(_SCRIPT)], capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stderr
