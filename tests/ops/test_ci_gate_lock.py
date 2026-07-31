"""run_ci lock semantics -- a deploy decision must never read "someone else is mid-gate" as green.

2026-07-31 (R0136): run_ci.py exits 0 on lock contention so an organ's routine gate is not failed
by a concurrent run -- correct for organs, but pull_deploy.sh interpreted that same rc 0 as "CI
green" and would have deployed an unvetted commit. The --fail-on-lock flag gives deployers an
honest verdict: rc 3 = "could not gate", retry next tick. These tests pin both semantics so
neither caller's contract can silently regress.
"""
from __future__ import annotations

import fcntl

import scripts.run_ci as run_ci


def _hold_lock(tmp_path, monkeypatch):
    lock = tmp_path / "ci.lock"
    monkeypatch.setattr(run_ci, "_LOCK", lock)
    fh = lock.open("w")
    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    return fh


def test_lock_contention_is_rc3_for_deployers(tmp_path, monkeypatch):
    fh = _hold_lock(tmp_path, monkeypatch)
    try:
        assert run_ci.main(["--fail-on-lock"]) == 3
    finally:
        fh.close()


def test_lock_contention_stays_rc0_for_organs(tmp_path, monkeypatch):
    # organs' routine gates keep exit 0 on contention -- someone else already checking the same
    # tree is a non-error for them, and failing their whole cycle for it would be a false alarm.
    fh = _hold_lock(tmp_path, monkeypatch)
    try:
        assert run_ci.main([]) == 0
    finally:
        fh.close()


def test_puller_invokes_strict_and_guards_the_revert():
    # the shell half: pull_deploy must ask for the strict verdict AND refuse a revert when the
    # tree moved during its CI window (the 2026-07-31 destroyed-work class, R0135).
    src = (run_ci._ROOT / "deploy/pull_deploy.sh").read_text("utf-8")
    assert "run_ci.py\" --fail-on-lock" in src
    assert "refused-revert-tree-moved" in src
