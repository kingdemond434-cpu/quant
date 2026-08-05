#!/usr/bin/env python3
"""check_stale_daemons WAS WELDED SHUT BY ITS OWN CLOCK -- and could not fire.

THE DEFECT. The check asked "which imported source files are newer than the process?" and took
the process start time from ``Path("/proc/<pid>").stat().st_mtime``. That is not a start time --
it is the procfs directory inode's mtime, refreshed as the directory is walked, so it reads ~now
for any process something polls. pid 1, which nothing polls, matches its real start exactly; every
supervised daemon does not. The population it is wrong about is precisely the one this check
audits. Measured on this box at the time of the fix::

    pid 1146543  serve_dashboard.py        /proc mtime 0.0167h    TRUE 180.1106h
    pid 1463355  run_deadman_switch.py     /proc mtime 0.0167h    TRUE 139.7547h
    pid 3424622  run_cashcarry_executor.py /proc mtime 0.0167h    TRUE   6.9294h

With ``started ~= now``, ``files newer than started`` can only match a file edited in the last
minute. So the detector for "a committed fix did not ship" -- the class this desk has paid for at
least three times (the carry-leak alarm inert 8.7h over a bleeding book; the --hold-top churn fix
inert 2 days) -- was structurally incapable of firing, and the ``up {age}h`` it printed into every
unsupervised-daemon defect was ~0.0h always: a fabricated number handed to a human.

PROVEN LIVE against the money-path daemon at the moment of the fix::

    AS SHIPPED (/proc mtime)  : 0 stale file(s), age 0.02h
    CORRECT   (btime+field22) : 2 stale file(s), age 6.94h
        libs/data/crypto_source.py, scripts/run_cashcarry_executor.py

WHAT THIS TEST PINS. Not "the numbers above", which are a moment in time -- the PROPERTY that
makes the check work at all: the clock must distinguish two processes of different ages. A test
that merely called ``_proc_start`` and asserted it returned a float would have passed against the
broken version too, which is exactly how this survived.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("_max_audit", _ROOT / "scripts/max_audit.py")
assert _spec and _spec.loader
max_audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(max_audit)


@pytest.mark.skipif(not Path("/proc/self/stat").exists(), reason="procfs-only")
def test_proc_start_is_not_the_procfs_directory_mtime() -> None:
    """THE REGRESSION STOP. Two processes of clearly different ages must read differently.

    Sleep a beat, start a second process, and require the clock to separate them. The broken
    implementation returns ~now for both, so the gap collapses to ~0 and this fails.
    """
    old = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        time.sleep(2.0)
        new = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            gap = max_audit._proc_start(new.pid) - max_audit._proc_start(old.pid)
            assert gap >= 1.0, (
                f"process start clock cannot separate two processes started 2s apart (gap "
                f"{gap:.3f}s). This is the welded-detector defect: with start ~= now, "
                f"check_stale_daemons can only ever see files edited in the last minute.")
        finally:
            new.kill()
            new.wait()
    finally:
        old.kill()
        old.wait()


@pytest.mark.skipif(not Path("/proc/self/stat").exists(), reason="procfs-only")
def test_proc_start_matches_this_process() -> None:
    """Sanity against a known quantity: our own start time is in the past, not the future."""
    start = max_audit._proc_start(os.getpid())
    now = time.time()
    assert 0.0 <= now - start < 86400.0, f"own start {start} vs now {now} is not plausible"


@pytest.mark.skipif(not Path("/proc/1/stat").exists(), reason="procfs-only")
def test_proc_start_agrees_with_an_independent_oracle() -> None:
    """THE ASSERTION THAT MATTERS: the clock is CORRECT, checked against a source that is not us.

    `ps -o lstart=` reads the same kernel fact by a different path, so agreeing with it is real
    evidence rather than a restatement. pid 1 is used because it is old enough that any drifting
    or ~now-tracking clock disagrees by hundreds of hours rather than by seconds.

    Deliberately NOT asserting anything about what /proc/<pid> mtime does. The first version of
    this test did, and was refuted on the spot: pid 1's mtime matches its start almost exactly
    because nothing polls it. The mtime tracks directory ACCESS, so it reads ~now for every
    process something is watching -- which is why the daemons all read 0.0167h and pid 1 did not.
    That is environment-dependent; the correctness of _proc_start is not.
    """
    out = subprocess.run(["ps", "-o", "lstart=", "-p", "1"],
                         capture_output=True, text=True, check=False).stdout.strip()
    if not out:
        pytest.skip("ps unavailable")
    oracle = time.mktime(time.strptime(out))
    assert abs(max_audit._proc_start(1) - oracle) < 120.0, (
        f"_proc_start(1)={max_audit._proc_start(1)} disagrees with `ps -o lstart` ({oracle}). "
        f"A start clock that drifts from the kernel's own answer cannot decide whether a file "
        f"changed before or after a daemon booted.")


def test_git_checkout_mtime_is_not_a_code_change() -> None:
    """THE SECOND HALF. Fixing the clock alone swaps never-fires for always-fires.

    `git checkout`/`merge`/`rebase` rewrite the mtime of every file they touch without changing a
    byte. Measured when this landed: run_deadman_switch.py and serve_dashboard.py both carried
    mtime 02:53:48 from one bulk git op, last committed 6 and 11 days earlier, both identical to
    HEAD. On the mtime signal the TIER-3 RUIN RAIL read as running stale code; on the content
    signal it correctly does not.

    Uses a committed, long-untouched file so the assertion is about the SIGNAL, not about which
    files happen to be dirty in whatever tree this runs in.
    """
    tracked = subprocess.run(["git", "log", "-1", "--format=%ct", "--", "libs/ops/lawful.py"],
                             cwd=_ROOT, capture_output=True, text=True, check=False)
    if not tracked.stdout.strip():
        pytest.skip("no git history available")
    last_commit = float(tracked.stdout.strip())
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "libs/ops/lawful.py"],
                           cwd=_ROOT, capture_output=True, text=True, check=False).stdout.strip()
    if dirty:
        pytest.skip("libs/ops/lawful.py is locally modified in this tree")
    path = _ROOT / "libs/ops/lawful.py"
    # Simulate exactly what a checkout does: bump mtime, change nothing.
    os.utime(path, (time.time(), time.time()))
    since = last_commit + 1.0          # a process started AFTER the last real commit
    assert path.stat().st_mtime > since, "precondition: mtime now looks newer than the process"
    assert max_audit._sources_changed_since({path}, since) == [], (
        "a clean file with a freshly-bumped mtime was reported as changed -- that is the "
        "git-checkout false positive, and it fires on the Tier-3 ruin rail after every merge.")


def test_uncommitted_edit_is_still_caught() -> None:
    """The true-positive half: a real uncommitted edit IS a content change, and must be seen."""
    scratch = _ROOT / "data" / ".stale_daemon_probe.py"
    scratch.parent.mkdir(parents=True, exist_ok=True)
    scratch.write_text("# probe\n", "utf-8")
    try:
        assert max_audit._sources_changed_since({scratch}, time.time() - 3600.0) == [scratch], (
            "an untracked/edited file newer than the process must be reported -- mtime IS the "
            "evidence when git has no committed version to compare against.")
    finally:
        scratch.unlink(missing_ok=True)


def test_stale_daemon_check_uses_the_explicit_clock() -> None:
    """No caller may go back to the procfs-directory mtime inside this check."""
    src = (_ROOT / "scripts/max_audit.py").read_text("utf-8")
    body = src.split("def check_stale_daemons")[1].split("\ndef ")[0]
    assert 'Path(f"/proc/{p}").stat().st_mtime' not in body, (
        "check_stale_daemons is back on the procfs directory mtime -- that reads ~60s for every "
        "pid and welds the detector shut. Use _proc_start().")
    assert "_proc_start" in body, "check_stale_daemons must take process start from _proc_start()"

