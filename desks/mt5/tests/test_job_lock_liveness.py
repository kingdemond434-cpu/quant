"""LOCK LIVENESS RECOVERY WAS DEAD CODE ON THE ONLY BOX THAT RUNS IT (regression, 2026-08-27).

`_owner_is_dead` exists so that live work never waits 45 minutes on a corpse -- its docstring says
so, and cites the searcher being blocked that way. It detected death by catching
`ProcessLookupError` from `os.kill(pid, 0)`.

Windows never raises that. MEASURED on the desk box (win32), which is where every heavy search
actually executes: a nonexistent pid raises plain `OSError` with `winerror=87`
(ERROR_INVALID_PARAMETER) and errno 22; a live pid raises nothing. The bare `except OSError:
return False` beneath swallowed it, so the function could only ever return False there and the
45-minute age rule was the only recovery the box has ever had.

The failure is silent and one-directional: a crashed writer's lock survives its owner, every
attempt in the next 45 minutes is REFUSED, and the refusal message reads "duplicate writer" --
naming a process that does not exist. Nothing distinguishes that from healthy contention.

These tests fix the platform under test rather than the platform running them, so the Windows
branch is exercised on Linux CI too -- otherwise the one path that was broken is the one path
never covered.
"""
from __future__ import annotations

import sys
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


def test_a_dead_windows_owner_is_recognised_as_dead(tmp_path, monkeypatch):
    """THE REGRESSION. The exact exception the desk box raises for a pid that is gone."""
    path = _lock(tmp_path, monkeypatch)
    err = OSError(22, "The parameter is incorrect")
    err.winerror = 87
    monkeypatch.setattr(J.sys, "platform", "win32")
    monkeypatch.setattr(J.os, "kill", _raise(err))

    assert J._owner_is_dead(path) is True, (
        "a Windows pid that no longer exists must read as DEAD; reading it as alive is what "
        "made every attempt in the next 45 minutes refuse against a corpse")


def test_a_live_windows_owner_is_never_reclaimed(tmp_path, monkeypatch):
    """The direction that would be far worse: two writers on one artifact."""
    path = _lock(tmp_path, monkeypatch)
    monkeypatch.setattr(J.sys, "platform", "win32")
    monkeypatch.setattr(J.os, "kill", lambda pid, sig: None)   # live pid raises nothing

    assert J._owner_is_dead(path) is False


@pytest.mark.parametrize(("winerror", "why"), [
    (5, "access denied -- the process may well exist under another token"),
    (None, "an OSError with no winerror at all: origin unknown"),
])
def test_any_other_oserror_stays_unknown(tmp_path, monkeypatch, winerror, why):
    """Narrow on purpose. Only the documented not-a-process signature counts as death.

    Reclaiming a lock from a process that is merely UNREACHABLE would let two writers run at
    once, which is worse than waiting out the age rule -- so everything else stays UNKNOWN and
    falls through to the timer (L1.28a).
    """
    path = _lock(tmp_path, monkeypatch)
    err = OSError(13, "denied")
    if winerror is not None:
        err.winerror = winerror
    monkeypatch.setattr(J.sys, "platform", "win32")
    monkeypatch.setattr(J.os, "kill", _raise(err))

    assert J._owner_is_dead(path) is False, why


def test_posix_behaviour_is_unchanged(tmp_path, monkeypatch):
    """The fix must not move the platform that was already correct."""
    path = _lock(tmp_path, monkeypatch)
    monkeypatch.setattr(J.sys, "platform", "linux")
    monkeypatch.setattr(J.os, "kill", _raise(ProcessLookupError()))
    assert J._owner_is_dead(path) is True

    # And a win32-shaped OSError on POSIX is still unknown: the errno means something else there.
    err = OSError(22, "invalid")
    err.winerror = 87
    monkeypatch.setattr(J.os, "kill", _raise(err))
    assert J._owner_is_dead(path) is False


def test_another_hosts_lock_is_never_judged(tmp_path, monkeypatch):
    """A pid number means nothing on a machine that did not write it -- pids collide."""
    path = _lock(tmp_path, monkeypatch, host="some-other-box")
    err = OSError(22, "The parameter is incorrect")
    err.winerror = 87
    monkeypatch.setattr(J.sys, "platform", "win32")
    monkeypatch.setattr(J.os, "kill", _raise(err))

    assert J._owner_is_dead(path) is False


def test_a_dead_owner_actually_lets_the_next_writer_in(tmp_path, monkeypatch):
    """END TO END, because the unit above is only half the claim.

    `_owner_is_dead` returning True is worth nothing unless `exclusive_job` then reclaims and
    yields True -- a wiring fix that is one link short still reports success.
    """
    _lock(tmp_path, monkeypatch)
    err = OSError(22, "The parameter is incorrect")
    err.winerror = 87
    monkeypatch.setattr(J.sys, "platform", "win32")
    real_kill = J.os.kill
    monkeypatch.setattr(J.os, "kill", lambda pid, sig: _raise(err)(pid, sig)
                        if pid == 6904 else real_kill(pid, sig))

    with J.exclusive_job("edge_search") as granted:
        assert granted is True, "the lock of a dead owner must be reclaimable, not merely detected"
