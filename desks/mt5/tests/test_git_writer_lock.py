"""EVERY PROCESS THAT WRITES THIS REPOSITORY TAKES ONE LOCK -- including the Python ones.

WHAT BROKE. Four PowerShell writers on the trading box -- adopt-and-seal, seal-if-clean,
intel-ship-adopt and shadow-sync -- serialise on a named mutex. Nothing in Python did, and
Python is most of what runs there. Measured 2026-09-23, the hourly adoption died mid-`git add`
on

    fatal: Unable to create 'C:/opt/quant/.git/index.lock': File exists.

`Adopt-Release` then exits 1, `Adopt-And-Seal` refuses to seal a half-matching tree, and the
gateway runs unshipped code for another hour. It did that for four days.

WHAT THIS SUITE PINS:

  * the lock is mutually exclusive, and a refusal says WHY rather than inventing contention;
  * a lock file whose owner is gone is taken over -- with the fact recorded, not silently;
  * `.git/index.lock` is removed ONLY when it is debris (old AND no git alive), and every
     non-removal reports its own reason, because "no lock" and "somebody's lock" have opposite
     remedies (L1.28a);
  * `run_git` retries a contended index with a bounded backoff and reports what it saw;
  * the Python names are the SAME names the PowerShell helper creates -- two locks with
    different names are no lock at all;
  * every Python writer in this repository actually takes it (UNWIRED IS A DEFECT, LAWS III.16).
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops import git_writer_lock as gwl  # noqa: E402

MUTEX_HELPER = ROOT / "desks" / "mt5" / "scripts" / "GitWriterMutex.ps1"


def _repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    return tmp_path


# ------------------------------------------------------------------- the lock is a real lock
def test_a_second_writer_waits_and_then_says_who_it_waited_for(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    with gwl.git_writer_lock(repo, mechanism="file", timeout_s=0.5) as first:
        assert first.held
        with gwl.git_writer_lock(repo, mechanism="file", timeout_s=0.5) as second:
            assert not second.held
            assert "another writer" in second.why
    # released: the next acquisition succeeds
    with gwl.git_writer_lock(repo, mechanism="file", timeout_s=0.5) as third:
        assert third.held


def test_a_lock_whose_owner_is_gone_is_taken_over_and_said_so(tmp_path: Path) -> None:
    """A writer killed mid-pass -- a task limit, a reboot, an OOM -- must not wedge every writer
    after it. Taking over silently would be just as wrong: the takeover IS the diagnosis."""
    repo = _repo(tmp_path)
    stale = repo / ".git" / "quant-git-writer.lock"
    # A pid that cannot be alive: 0 is never a user process on either platform.
    stale.write_text("0 1.0\n", encoding="utf-8")
    old = time.time() - 600
    os.utime(stale, (old, old))
    with gwl.git_writer_lock(repo, mechanism="file", timeout_s=5.0, stale_s=60.0) as lock:
        assert lock.held
        assert any("took over a lock file" in n for n in lock.notes)


def test_the_body_always_runs_and_the_caller_decides(tmp_path: Path) -> None:
    """A governance fault must not stop the desk (L1.37). The context manager reports; it never
    refuses to yield, because a lock that could not be examined is not evidence of anything."""
    repo = _repo(tmp_path)
    ran = False
    with gwl.git_writer_lock(repo, mechanism="file", timeout_s=0.2) as outer:
        assert outer.held
        with gwl.git_writer_lock(repo, mechanism="file", timeout_s=0.2) as inner:
            ran = True
            assert inner.as_dict()["held"] is False
            assert inner.as_dict()["why"]
    assert ran


# ---------------------------------------------------------------------- the index.lock itself
def test_a_lock_file_owned_by_pid_zero_is_never_read_as_held(tmp_path: Path) -> None:
    """`tasklist /fi "pid eq 0"` answers with the System Idle Process, so an owner field of 0 --
    or anything that parses to <= 0 -- would otherwise look alive forever on Windows."""
    assert gwl._pid_alive(0) is False
    assert gwl._pid_alive(-1) is False
    assert gwl._pid_alive(None) is False


def test_no_index_lock_and_somebody_s_index_lock_never_render_the_same(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    absent = gwl.clear_stale_index_lock(repo)
    assert absent == {"present": False, "removed": False, "age_s": None, "why": "no index.lock"}

    lock = repo / ".git" / "index.lock"
    lock.write_text("", encoding="utf-8")
    young = gwl.clear_stale_index_lock(repo, stale_s=600.0, alive=lambda: False)
    assert young["present"] and not young["removed"]
    assert "live writer between two of its own git calls" in young["why"]
    assert lock.exists()


def test_an_old_lock_a_live_git_holds_is_never_removed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    lock = repo / ".git" / "index.lock"
    lock.write_text("", encoding="utf-8")
    old = time.time() - 900
    os.utime(lock, (old, old))
    rec = gwl.clear_stale_index_lock(repo, stale_s=60.0, alive=lambda: True)
    assert rec["present"] and not rec["removed"]
    assert "could corrupt that writer's index" in rec["why"]
    assert lock.exists(), "a lock a live git holds was removed -- that corrupts an index"


def test_debris_is_removed_and_the_removal_is_the_record(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    lock = repo / ".git" / "index.lock"
    lock.write_text("", encoding="utf-8")
    old = time.time() - 900
    os.utime(lock, (old, old))
    rec = gwl.clear_stale_index_lock(repo, stale_s=60.0, alive=lambda: False)
    assert rec["removed"] is True
    assert "REMOVED" in rec["why"].upper() or "removed a stale index.lock" in rec["why"]
    assert rec["age_s"] is not None and rec["age_s"] > 60
    assert not lock.exists()


def test_run_git_retries_a_contended_index_and_reports_every_attempt(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path)
    calls: list[list[str]] = []

    def fake_run(argv: Any, timeout: float = 0.0, cwd: Any = None) -> tuple[int, str]:
        calls.append(list(argv))
        if len(calls) < 3:
            return 128, "fatal: Unable to create '.git/index.lock': File exists."
        return 0, "ok"

    monkeypatch.setattr(gwl, "_run", fake_run)
    rc, out, notes = gwl.run_git(repo, ["add", "--", "x"], sleep=lambda _s: None)
    assert rc == 0 and out == "ok"
    assert len(calls) == 3, "the contended index was not retried"
    assert len([n for n in notes if "lost the index lock" in n]) == 2


def test_the_retry_is_bounded_so_a_wedged_index_becomes_a_defect_not_a_loop(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path)
    calls: list[int] = []

    def always_contended(*_a: Any, **_k: Any) -> tuple[int, str]:
        calls.append(1)
        return 128, "fatal: Unable to create '.git/index.lock': File exists."

    monkeypatch.setattr(gwl, "_run", always_contended)
    rc, _out, notes = gwl.run_git(repo, ["add", "--", "x"], attempts=4, sleep=lambda _s: None)
    assert rc != 0
    assert len(calls) == 4
    assert notes, "a bounded retry that gives up silently is the failure it was added to fix"


def test_a_failure_that_is_not_the_lock_is_not_retried(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path)
    calls: list[int] = []

    def phantom_pathspec(*_a: Any, **_k: Any) -> tuple[int, str]:
        calls.append(1)
        return 128, "fatal: pathspec 'x' did not match any files"

    monkeypatch.setattr(gwl, "_run", phantom_pathspec)
    rc, _out, notes = gwl.run_git(repo, ["add", "--", "x"], sleep=lambda _s: None)
    assert rc == 128
    assert len(calls) == 1 and notes == []


# --------------------------------------------------------------------- one lock, not two locks
def test_the_python_names_are_the_powershell_names() -> None:
    src = MUTEX_HELPER.read_text(encoding="utf-8")
    for name in gwl.MUTEX_NAMES:
        assert f'"{name}"' in src, f"{name} is not the name GitWriterMutex.ps1 creates"
    assert f'"{gwl.LEGACY_MUTEX_NAME}"' in src


@pytest.mark.skipif(sys.platform != "win32", reason="the named mutex exists only on Windows")
def test_on_windows_the_real_named_mutex_is_openable_by_this_principal() -> None:
    """The four-day outage WAS this call failing: a mutex created under one principal's default
    descriptor that no other principal could open. The Python half must not re-create it."""
    with gwl.git_writer_lock(ROOT, mechanism="mutex", timeout_s=5.0) as lock:
        assert lock.mechanism == "mutex"
        assert lock.name in gwl.MUTEX_NAMES
        # held or not-held are both acceptable here (a real writer may hold it), but "no mutex
        # name could be opened" is the failure this module exists to prevent.
        assert "no mutex name could be opened" not in lock.why


# ------------------------------------------------ UNWIRED IS A DEFECT: the writers take it
#: Every Python file in this repository that writes the git INDEX, and therefore has to queue
#: behind the same lock as the PowerShell writers. A new one added without the lock is a new
#: `.git/index.lock` the adoption can lose to.
INDEX_WRITERS = (
    "scripts/git_snapshot.py",
    "scripts/check_doc_replay_fence.py",
    "scripts/check_unit_health.py",
    "desks/mt5/scripts/arm_and_pass.py",
)


@pytest.mark.parametrize("rel", INDEX_WRITERS)
def test_every_python_index_writer_takes_the_lock(rel: str) -> None:
    src = (ROOT / rel).read_text(encoding="utf-8")
    assert "git_writer_lock" in src, f"{rel} writes the index without taking the desk's lock"
    assert "with git_writer_lock(" in src, f"{rel} imports the lock but never holds it"
    # And declines rather than writing through a lock it could not take.
    assert "lock.held" in src, f"{rel} does not check whether it actually got the lock"


#: The PowerShell writers. All five dot the helper -- what this pins is that each keeps the
#: WHOLE handle, because `.Mutex` alone drops the legacy name (so a writer running pre-2026-09-23
#: code is not coordinated with at all) and turns "the lock could not be opened" into a silent
#: $null whose `.WaitOne()` fails non-terminating and reads as contention nobody measured. That
#: exact confusion is what kept this box from adopting for four days.
PS_WRITERS = (
    "desks/mt5/scripts/Adopt-And-Seal.ps1",
    "desks/mt5/scripts/Seal-IfClean.ps1",
    "desks/mt5/scripts/intel_ship_adopt.ps1",
    "desks/mt5/scripts/sync_shadow_to_git.ps1",
)


@pytest.mark.parametrize("rel", PS_WRITERS)
def test_every_powershell_writer_keeps_the_whole_lock_handle(rel: str) -> None:
    src = (ROOT / rel).read_text(encoding="utf-8")
    assert "Open-GitWriterMutex" in src, f"{rel} does not take the desk's git-writer lock"
    assert "(Open-GitWriterMutex).Mutex" not in src, (
        f"{rel} keeps only .Mutex: the legacy name is dropped and a lock that could not be "
        f"opened becomes a $null that reads as contention")
    assert "$null -eq" in src, f"{rel} never checks whether the lock could be opened at all"
    assert "not evidence that another writer holds it" in src or \
        "could not be examined" in src, (
        f"{rel} reports a refusal without saying whether anything was actually measured")


def test_the_precommit_guard_is_deliberately_not_on_that_list() -> None:
    """A hook runs INSIDE somebody else's `git commit`, which already holds the index. Taking
    the lock there would deadlock against the writer that invoked it, so the guard is excluded
    on purpose -- recorded here so a future sweep does not "fix" it."""
    guard = ROOT / "scripts" / "moneypath_precommit_guard.py"
    assert guard.exists()
    assert "git_writer_lock" not in guard.read_text(encoding="utf-8")
