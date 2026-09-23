"""A pid no unit owns must not be judged as that unit's staleness (gap-fixer 2026-08-26).

`_live_organs()` maps a script to EVERY pid running it, and the staleness check collapsed them
into ONE verdict keyed on the OLDEST. Measured on the live box: three `serve_dashboard.py`
processes with three different owners -- `quant-dashboard.service` (/system.slice), the
token-gated desk-web unit, and an ORPHAN left in `/user.slice/.../session-91168.scope` by an ssh
session that had since closed.

The orphan was the oldest, so `daemon-stale-code-quant-dashboard` reported ITS staleness under
the UNIT's label. `run_stale_daemon_repair` then restarted the unit on every run -- the restart
WORKED (the unit's pid changed) and the verdict came back STILL-STALE, because the stale process
was never part of that unit. The defect had stood 53.9h that way: a detector and an actuator
both running, both correct in isolation, permanently unable to close.

The orphan was also invisible to the `daemon-unsupervised` arm, which asks whether MainPID is
anywhere in the pid SET -- and it was, via a legitimate sibling. An orphan hiding inside a
supervised script's pid set is exactly the case that arm exists to catch.
"""
from __future__ import annotations

from scripts import max_audit


def test_owner_unit_reads_a_service_cgroup(tmp_path, monkeypatch):
    monkeypatch.setattr(max_audit, "Path", _FakePath(
        {"/proc/4242/cgroup": "0::/system.slice/quant-dashboard.service"}))
    assert max_audit._owner_unit(4242) == "quant-dashboard.service"


def test_a_login_session_scope_owns_nothing(tmp_path, monkeypatch):
    """The orphan's actual cgroup on the live box."""
    monkeypatch.setattr(max_audit, "Path", _FakePath(
        {"/proc/2484799/cgroup": "0::/user.slice/user-1000.slice/session-91168.scope"}))
    assert max_audit._owner_unit(2484799) == ""


def test_an_unreadable_cgroup_owns_nothing(monkeypatch):
    """A pid that exited mid-audit must not be attributed to a unit by accident."""
    monkeypatch.setattr(max_audit, "Path", _FakePath({}))
    assert max_audit._owner_unit(999999) == ""


class _FakePath:
    """Minimal stand-in: only /proc/<pid>/cgroup reads are exercised here."""

    def __init__(self, files: dict[str, str]):
        self._files = files

    def __call__(self, p):
        return _FakeFile(self._files.get(str(p)))


class _FakeFile:
    def __init__(self, text):
        self._text = text

    def read_text(self, *_a, **_k):
        if self._text is None:
            raise OSError("no such file")
        return self._text
