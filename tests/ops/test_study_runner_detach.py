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


def test_A_DETACHED_RUN_MUST_NOT_BUFFER_ITS_OWN_PROGRESS(src: str) -> None:
    """THE DETACH FIX MADE THE PROCESS SURVIVABLE AND SIMULTANEOUSLY MADE IT LOOK DEAD.

    Python block-buffers stdout when it is a pipe or a file, so the detached run wrote nothing to
    its log until 4-8KB accumulated. `run_full_sweep` flushed its per-cell lines but not its
    header, so the first cell produced a log containing only "STARTED" -- indistinguishable from a
    hang, and read as one. Two fixes were needed and both belong under test: the environment, and
    the header line itself.
    """
    assert "PYTHONUNBUFFERED=1" in src


def test_EVERY_REGISTERED_STUDY_FLUSHES_ITS_FIRST_PROGRESS_LINE() -> None:
    """It is the only proof the run got past loading bars. A progress line that arrives after the
    work is not progress reporting.

    GENERALISED 2026-09-05. This pinned `scripts/run_full_sweep.py` by name, and that script was
    deleted with the retired crypto-exchange desk -- so the fence raised FileNotFoundError rather
    than asserting anything, which tells a reader nothing about the rule it was defending. The
    rule is about DETACHED STUDIES, not about one sweep: it now reads the registry in
    ops/run_study_on_vps.sh and holds every study actually registered there to it. The registry is
    currently empty under the MT5 mandate, so this passes vacuously TODAY -- and it starts biting
    again by itself the moment a study is registered, which is exactly when it is needed.
    """
    # Only ACTIVE registry lines count. The retired entries stay in the file as commented rows so
    # the shape of the retired registry is still readable, and a fence that read those would be
    # asserting against studies the desk deliberately unscheduled.
    runner = "\n".join(ln for ln in Path("ops/run_study_on_vps.sh").read_text("utf-8").split("\n")
                       if not ln.strip().startswith("#"))
    registered = re.findall(r'\["[a-z0-9_]+"\]="(scripts/[a-z0-9_]+\.py)', runner)
    for rel in registered:
        script = Path(rel)
        assert script.exists(), f"{rel} is registered as a study but does not exist"
        src = script.read_text("utf-8")
        first_print = src.find("print(")
        assert first_print != -1 and "flush=True" in src[first_print:first_print + 400], (
            f"{rel}'s first progress print lost its flush -- a detached run goes silent and a "
            "log containing only STARTED is indistinguishable from a hang")


def test_A_FAILED_STUDY_CANNOT_BE_REPORTED_AS_FINISHED(src: str) -> None:
    """tee and a trailing echo must not turn a crashed study into a green scheduled run."""
    assert "PIPESTATUS[0]" in src
    assert 'echo "FAILED' in src
    assert 'return "$study_rc"' in src
    assert "OVERALL_RC" in src
    assert 'run_one "$name" || true' not in src
