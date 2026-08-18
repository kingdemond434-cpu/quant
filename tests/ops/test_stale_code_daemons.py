"""The stale-code daemon detector must be able to FIRE -- for two years it could not.

A daemon running code older than its own source is a fix that did not ship. max_audit has carried
a check for exactly that since 2026-07-26, and on 2026-08-04 five stale-code daemons (the executor
and the bybit recorder among them) still had to be found by hand, because the check was blind in
two independent ways at once:

  * the CLOCK -- process start time was read from the /proc/<pid> directory mtime, which on this
    kernel is the same value for every pid and tracks roughly now. `started` therefore read as
    ~now, no file could be newer than it, and the staleness test was unsatisfiable by
    construction. A 164h-old dashboard was reported as up 0.07h.
  * the ROSTER -- only the four scripts with a systemd unit were ever examined, against eight
    long-lived organ processes on the box.

Both failures made the check report ALL CLEAR rather than error, which is why nothing noticed. So
these tests do not assert on its wording; they stand up a real process running a real repo file,
make that file newer than the process, and demand the defect.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location("max_audit", _ROOT / "scripts" / "max_audit.py")
assert _SPEC and _SPEC.loader
_M = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_M)


def test_proc_start_agrees_with_ps() -> None:
    """The regression guard on the clock itself: /proc dir mtime disagreed with ps by DAYS."""
    pid = os.getpid()
    started = _M._proc_start(pid)
    assert started is not None
    etimes = float(subprocess.run(["ps", "-o", "etimes=", "-p", str(pid)],
                                  capture_output=True, text=True, check=True).stdout.strip())
    assert abs((time.time() - started) - etimes) <= 2.0


def test_proc_start_distinguishes_two_processes() -> None:
    """The broken clock returned one shared value for every pid, so ordering was meaningless."""
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        time.sleep(1.1)
        mine, theirs = _M._proc_start(os.getpid()), _M._proc_start(child.pid)
        assert mine is not None and theirs is not None
        assert theirs > mine, "a later-started process must have a later start time"
    finally:
        child.kill()
        child.wait(timeout=10)


def test_proc_start_on_a_dead_pid_is_none() -> None:
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait(timeout=10)
    assert _M._proc_start(child.pid) is None


def _probe(tmp_name: str) -> Path:
    # data/ is gitignored, so a probe script here is a scratch file and never a tracked artifact.
    p = _ROOT / "data" / tmp_name
    p.write_text("import time\ntime.sleep(120)\n", "utf-8")
    return p


def test_a_running_organ_outside_the_systemd_roster_is_discovered() -> None:
    """`_DAEMONS` knows four scripts; the box runs eight-plus organs. Discovery is by process."""
    probe = _probe(".organ_probe_discovery.py")
    proc = subprocess.Popen([sys.executable, str(probe)])
    try:
        time.sleep(1.2)
        organs = _M._live_organs()
        rel = probe.relative_to(_ROOT).as_posix()
        assert rel in organs, f"{rel} not discovered; got {sorted(organs)}"
        assert proc.pid in organs[rel]
    finally:
        proc.kill()
        proc.wait(timeout=10)
        probe.unlink(missing_ok=True)


def test_stale_code_actually_raises_a_defect(monkeypatch) -> None:
    """END TO END: a live process whose source changed after it started MUST be reported.

    This is the assertion that would have failed every day since the check was written.
    """
    probe = _probe(".organ_probe_stale.py")
    proc = subprocess.Popen([sys.executable, str(probe)])
    try:
        time.sleep(1.2)
        # THE FIX LANDS AFTER THE PROCESS LOADED THE MODULE -- stated by construction rather than
        # raced for. `probe.touch()` set mtime to "now", which is ~1.2s after start and therefore
        # INSIDE `_START_SLOP_S`; the test only passed while that constant was 0.5, and it went red
        # the moment the slop was widened to cover /proc/stat's whole-second `btime` truncation.
        # Racing a wall-clock sleep against a tolerance constant tests the sleep. Setting the mtime
        # relative to the measured start time and the slop tests the DETECTOR, and keeps testing it
        # whatever the constant becomes.
        started = _M._proc_start(proc.pid)
        assert started, "cannot read the probe's start time -- the clock this check depends on"
        stamp = started + _M._START_SLOP_S + 5.0
        os.utime(probe, (stamp, stamp))
        monkeypatch.setattr(_M, "_ORGAN_MIN_UP_H", 0.0)   # no waiting an hour for the verdict
        defects: list[tuple] = []
        _M.check_stale_daemons(defects)
        hits = [d for d in defects if ".organ_probe_stale.py" in d[1]]
        assert hits, f"stale-code process not reported; defects={[d[0] for d in defects]}"
        assert "INERT" in hits[0][1]
    finally:
        proc.kill()
        proc.wait(timeout=10)
        probe.unlink(missing_ok=True)


def test_a_bulk_git_rewrite_of_identical_bytes_stays_quiet(tmp_path, monkeypatch) -> None:
    """A rebase/checkout rewrites mtimes without changing bytes; the RUIN RAIL must not page.

    Measured 2026-08-18: run_deadman_switch.py carried mtime 2026-08-09 from one bulk git
    operation, content identical to its 2026-07-30 commit, and the process started 63s AFTER
    that commit -- yet daemon-stale-code paged a human to restart the deadman, daily, on the
    mtime half of the union alone. Content-vs-pre-start-commit is the discriminating evidence:
    an identical rewrite stays quiet, while a dirty edit and a genuine rollback swap (the case
    the mtime half exists for) both still fire.
    """
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, env=env, check=True, capture_output=True)

    git("init", "-q")
    organ = tmp_path / "organ.py"
    organ.write_text("x = 1\n")
    git("add", "organ.py")
    git("commit", "-qm", "born")
    monkeypatch.setattr(_M, "ROOT", tmp_path)
    floor = time.time() + 60.0                 # the process "started" after the commit
    stamp = floor + 120.0
    os.utime(organ, (stamp, stamp))            # bulk git op: mtime rewritten, bytes identical
    assert _M._mtime_is_content_change(organ, floor) is False

    organ.write_text("x = 2\n")                # dirty edit under the running process
    assert _M._mtime_is_content_change(organ, floor) is True

    git("add", "organ.py")
    git("commit", "-qm", "v2")                 # still before the (future) floor
    subprocess.run(["git", "checkout", "HEAD~1", "--", "organ.py"],
                   cwd=tmp_path, env=env, check=True, capture_output=True)
    assert _M._mtime_is_content_change(organ, floor) is True  # rollback swap must fire


def test_a_freshly_started_organ_is_not_stale(monkeypatch) -> None:
    """Noise discipline: unchanged source since start must stay silent."""
    probe = _probe(".organ_probe_fresh.py")
    proc = subprocess.Popen([sys.executable, str(probe)])
    try:
        time.sleep(1.2)
        monkeypatch.setattr(_M, "_ORGAN_MIN_UP_H", 0.0)
        defects: list[tuple] = []
        _M.check_stale_daemons(defects)
        assert not [d for d in defects if ".organ_probe_fresh.py" in d[1]]
    finally:
        proc.kill()
        proc.wait(timeout=10)
        probe.unlink(missing_ok=True)


def test_import_closure_follows_the_api_package() -> None:
    """ops_server.py's only repo import is `from api import adapters`; `api` was not a root, so
    its closure was itself alone and every change under api/ was invisible."""
    closure = _M._import_closure(_ROOT / "scripts" / "ops_server.py")
    assert any(p.as_posix().split("/")[-2:][0] == "api" or "/api/" in p.as_posix()
               for p in closure), f"api/ not followed: {sorted(p.name for p in closure)}"
