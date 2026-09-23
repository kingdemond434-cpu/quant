"""LOCK LIVENESS: A CORPSE MUST NEVER BLOCK, AND A LIVING OWNER MUST NEVER BE ROBBED.

Two regressions live here, in the two opposite directions, and the file covers both because
fixing either one alone is what produced the other.

DIRECTION 1 -- liveness recovery was dead code on the only box that runs it (2026-08-27).
Death was detected by catching `ProcessLookupError` from `os.kill(pid, 0)`. Windows never
raises that. MEASURED on the desk box (win32), where every heavy search actually executes: a
nonexistent pid raises plain `OSError` with `winerror=87` (ERROR_INVALID_PARAMETER), errno 22;
a live pid raises nothing. The bare `except OSError` beneath swallowed it, so the function could
only ever answer "not dead" there and the 45-minute age rule was the only recovery the box has
ever had. The failure is silent and one-directional: a crashed writer's lock survives its owner,
every attempt in the next 45 minutes is REFUSED, and the refusal reads "duplicate writer" --
naming a process that does not exist.

DIRECTION 2 -- age reclaimed a lock whose owner was demonstrably alive (2026-08-28). A boolean
"is it dead" lets the caller use liveness to ADD staleness but never to VETO it, so a lock older
than STALE_SECONDS was reclaimed from a working owner. With sweeps that legitimately run 60-90
minutes against a 45-minute timer that is not an edge case, it GUARANTEES a duplicate: two
external_gauntlet processes at once, 66 and 22 minutes, both sweeping, saturating the box.

THE API FOLLOWS FROM THAT. `_owner_state` is a TRI-STATE -- "DEAD", "ALIVE", "UNKNOWN" -- and
these tests assert the state itself rather than a boolean, because the boolean collapsed ALIVE
and UNKNOWN into one value and the difference between them is the whole fix: ALIVE VETOES the
age rule, UNKNOWN FALLS BACK to it. A test that cannot tell those apart cannot see the bug.

These tests fix the platform under test rather than the platform running them, so the Windows
branch is exercised on Linux CI too -- otherwise the one path that was broken is the one path
never covered.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "research"))

import job_lock as J  # noqa: E402

LOCK = '{"token": "t", "pid": 6904, "host": "%s", "started_at": "2026-08-27T14:51:42+00:00"}'


def _lock(tmp_path, monkeypatch, host: str | None = None) -> Path:
    import socket
    path = tmp_path / "edge_search.json"
    path.write_text(LOCK % (host or socket.gethostname()), "utf-8")
    monkeypatch.setattr(J, "LOCK_ROOT", tmp_path)
    return path


def _raise(exc):
    def _kill(pid, sig):
        raise exc
    return _kill


def _win_not_a_process() -> OSError:
    """The exact exception the desk box raises for a pid that is gone."""
    err = OSError(22, "The parameter is incorrect")
    err.winerror = 87
    return err


def test_a_dead_windows_owner_is_recognised_as_dead(tmp_path, monkeypatch):
    """THE REGRESSION. The exact exception the desk box raises for a pid that is gone."""
    path = _lock(tmp_path, monkeypatch)
    monkeypatch.setattr(J.sys, "platform", "win32")
    monkeypatch.setattr(J.os, "kill", _raise(_win_not_a_process()))

    assert J._owner_state(path) == "DEAD", (
        "a Windows pid that no longer exists must read as DEAD; reading it as alive is what "
        "made every attempt in the next 45 minutes refuse against a corpse")


def test_a_live_windows_owner_reads_alive_not_merely_not_dead(tmp_path, monkeypatch):
    """The direction that would be far worse: two writers on one artifact.

    ALIVE is asserted by name. Under the old boolean this case and the UNKNOWN cases below were
    indistinguishable, and that collapse is precisely what let age reclaim a live owner's lock.
    """
    path = _lock(tmp_path, monkeypatch)
    monkeypatch.setattr(J.sys, "platform", "win32")
    monkeypatch.setattr(J.os, "kill", lambda pid, sig: None)   # live pid raises nothing

    assert J._owner_state(path) == "ALIVE"


def test_an_oserror_of_unknown_origin_stays_unknown(tmp_path, monkeypatch):
    """Narrow on purpose. Only the documented not-a-process signature counts as death.

    Reclaiming a lock from a process that is merely UNREACHABLE would let two writers run at
    once, which is worse than waiting out the age rule -- so an error the desk cannot interpret
    stays UNKNOWN and falls through to the timer (L1.28a: unmeasured is its own answer, never a
    clean verdict).
    """
    path = _lock(tmp_path, monkeypatch)
    monkeypatch.setattr(J.sys, "platform", "win32")
    monkeypatch.setattr(J.os, "kill", _raise(OSError(22, "something else entirely")))

    assert J._owner_state(path) == "UNKNOWN"


def test_windows_access_denied_reaches_the_permissionerror_branch_not_the_winerror_one(
        tmp_path, monkeypatch):
    """MEASURED, and it is not what the winerror table suggests.

    Python maps errno to an OSError SUBCLASS at construction, so Windows ERROR_ACCESS_DENIED
    (winerror 5 -> errno 13/EACCES) arrives as `PermissionError` and is answered ALIVE by the
    branch above -- it never reaches the `winerror == 87` test at all. That is the correct
    answer (OpenProcess denies access to a process that EXISTS), but the routing is invisible
    from the code, so it is pinned here: an earlier version of this test built its "access
    denied" case as `OSError(13, ...)` and asserted the fall-through, which passed only because
    the old boolean API collapsed ALIVE and UNKNOWN into one value. The assertion could never
    have reached the branch it named.

    Verified on this interpreter: OSError(13) -> PermissionError, OSError(22) -> OSError.
    """
    path = _lock(tmp_path, monkeypatch)
    err = OSError(13, "Access is denied")
    err.winerror = 5
    assert isinstance(err, PermissionError), (
        "if this ever stops being true the module's branch order must be revisited: the "
        "winerror==87 test would then start seeing access-denied errors")
    monkeypatch.setattr(J.sys, "platform", "win32")
    monkeypatch.setattr(J.os, "kill", _raise(err))

    assert J._owner_state(path) == "ALIVE"


def test_posix_behaviour_is_unchanged(tmp_path, monkeypatch):
    """The fix must not move the platform that was already correct."""
    path = _lock(tmp_path, monkeypatch)
    monkeypatch.setattr(J.sys, "platform", "linux")
    monkeypatch.setattr(J.os, "kill", _raise(ProcessLookupError()))
    assert J._owner_state(path) == "DEAD"

    # And a win32-shaped OSError on POSIX is still unknown: the errno means something else there.
    monkeypatch.setattr(J.os, "kill", _raise(_win_not_a_process()))
    assert J._owner_state(path) == "UNKNOWN"


def test_a_permission_error_is_alive_not_unknown(tmp_path, monkeypatch):
    """A process owned by another user is RUNNING, and running vetoes age.

    Downgrading this to UNKNOWN would hand the lock back to the timer and re-open direction 2.
    """
    path = _lock(tmp_path, monkeypatch)
    monkeypatch.setattr(J.sys, "platform", "linux")
    monkeypatch.setattr(J.os, "kill", _raise(PermissionError()))
    assert J._owner_state(path) == "ALIVE"


def test_another_hosts_lock_is_never_judged(tmp_path, monkeypatch):
    """A pid number means nothing on a machine that did not write it -- pids collide."""
    path = _lock(tmp_path, monkeypatch, host="some-other-box")
    monkeypatch.setattr(J.sys, "platform", "win32")
    monkeypatch.setattr(J.os, "kill", _raise(_win_not_a_process()))

    assert J._owner_state(path) == "UNKNOWN"


def test_an_unreadable_lock_is_unknown_not_dead(tmp_path, monkeypatch):
    """Garbage on disk must fall back to the age rule, never be read as an invitation."""
    path = tmp_path / "edge_search.json"
    path.write_text("{not json", "utf-8")
    monkeypatch.setattr(J, "LOCK_ROOT", tmp_path)
    assert J._owner_state(path) == "UNKNOWN"


def test_a_dead_owner_actually_lets_the_next_writer_in(tmp_path, monkeypatch):
    """END TO END, because the unit above is only half the claim.

    `_owner_state` answering "DEAD" is worth nothing unless `exclusive_job` then reclaims and
    yields True -- a wiring fix that is one link short still reports success.
    """
    _lock(tmp_path, monkeypatch)
    monkeypatch.setattr(J.sys, "platform", "win32")
    real_kill = J.os.kill
    err = _win_not_a_process()
    monkeypatch.setattr(J.os, "kill", lambda pid, sig: _raise(err)(pid, sig)
                        if pid == 6904 else real_kill(pid, sig))

    with J.exclusive_job("edge_search") as granted:
        assert granted is True, "the lock of a dead owner must be reclaimable, not merely detected"


def test_a_live_owner_of_an_ancient_lock_is_never_robbed(tmp_path, monkeypatch):
    """END TO END for direction 2 -- the half the boolean API could not express.

    A lock OLDER than STALE_SECONDS whose owner is still running must be REFUSED, not reclaimed.
    This is the path that produced two concurrent sweeps on one box; without this test the fix
    that changed the API is itself uncovered end to end.
    """
    path = _lock(tmp_path, monkeypatch)
    ancient = time.time() - (J.STALE_SECONDS + 600)
    os.utime(path, (ancient, ancient))
    monkeypatch.setattr(J.sys, "platform", "win32")
    real_kill = J.os.kill
    monkeypatch.setattr(J.os, "kill",
                        lambda pid, sig: None if pid == 6904 else real_kill(pid, sig))

    with J.exclusive_job("edge_search") as granted:
        assert granted is False, (
            "an old lock with a LIVING owner is a long job, not an abandoned one; reclaiming it "
            "is what put two sweeps on the box at once")
    assert path.exists(), "the live owner's lock must survive the refusal"


def test_an_ancient_lock_with_an_unknown_owner_still_falls_back_to_age(tmp_path, monkeypatch):
    """UNKNOWN must keep the age rule, or direction 1 returns wearing a different costume.

    This is the case the tri-state exists to separate: ALIVE vetoes the timer, UNKNOWN obeys it.
    """
    path = _lock(tmp_path, monkeypatch, host="some-other-box")   # never judged -> UNKNOWN
    ancient = time.time() - (J.STALE_SECONDS + 600)
    os.utime(path, (ancient, ancient))

    with J.exclusive_job("edge_search") as granted:
        assert granted is True, (
            "a lock the desk cannot judge must still time out, otherwise an unreadable or "
            "foreign lock blocks the job forever")


# ------------------------------------------------- admission on what a job ACTUALLY uses

def test_a_job_is_admitted_on_its_measured_peak_not_its_declaration(tmp_path, monkeypatch):
    """MEASURED 2026-09-05. `external_gauntlet` declared 1200MB -- taken from a 1926MB peak in
    August and never revisited -- and was found holding 4882MB ten minutes into a legitimate run
    on an 8GB box. Admission passed on 1200MB of headroom, the process grew to four times its
    declaration, 280MB was left, and `edge_search` (2000MB) and `orthogonal_sweep` (1250MB) could
    not start: their artifacts went 28 and 23 hours stale. The guard was right; its number was
    stale, and nothing measured that.
    """
    import job_lock as jl
    monkeypatch.setattr(jl, "LOCK_ROOT", tmp_path)
    assert jl.measured_need_mb("gauntlet", 1200)[0] == 1200        # nothing measured yet
    jl.record_peak("gauntlet", 4882)
    need, why = jl.measured_need_mb("gauntlet", 1200)
    # Matched on the NUMBER, not the prose. The statistic behind this figure changed from max to
    # p75 on 2026-09-05 (one 4882MB outlier had locked the gauntlet out of the box for a day), and
    # pinning the wording made a correct fix look like a regression.
    assert need == 4882 and "4882MB" in why


def test_the_declaration_is_a_floor_and_a_light_run_never_lowers_it(tmp_path, monkeypatch):
    """It may only RAISE. A job cannot talk its way into a box that cannot hold it, and one
    small docket does not undo the peak the job is capable of reaching."""
    import job_lock as jl
    monkeypatch.setattr(jl, "LOCK_ROOT", tmp_path)
    jl.record_peak("gauntlet", 300)
    assert jl.measured_need_mb("gauntlet", 1200)[0] == 1200        # below the floor: floor wins
    jl.record_peak("gauntlet", 4882)
    jl.record_peak("gauntlet", 310)
    assert jl.measured_need_mb("gauntlet", 1200)[0] == 4882        # the peak still stands


def test_the_history_is_bounded_so_a_job_that_got_lighter_is_believed(tmp_path, monkeypatch):
    """Held to its peak, but not forever: past PEAK_HISTORY runs the old peak leaves the window."""
    import job_lock as jl
    monkeypatch.setattr(jl, "LOCK_ROOT", tmp_path)
    jl.record_peak("gauntlet", 4882)
    for _ in range(jl.PEAK_HISTORY):
        jl.record_peak("gauntlet", 400)
    assert 4882 not in jl.observed_peaks("gauntlet")
    assert jl.measured_need_mb("gauntlet", 1200)[0] == 1200


def test_an_unwritable_ledger_never_costs_the_run(tmp_path, monkeypatch):
    """Note-taking that fails is worth strictly less than the job it was taking notes about."""
    import job_lock as jl
    monkeypatch.setattr(jl, "LOCK_ROOT", tmp_path / "nope" / "\0bad")
    jl.record_peak("gauntlet", 4882)                                # must not raise
    assert jl.observed_peaks("gauntlet") == []
    assert jl.measured_need_mb("gauntlet", 1200) == (1200, "declared 1200MB (no run measured yet)")
