"""run_ci lock semantics -- a deploy decision must never read "someone else is mid-gate" as green.

2026-07-31 (R0145): run_ci.py exits 0 on lock contention so an organ's routine gate is not failed
by a concurrent run -- correct for organs, but pull_deploy.sh interpreted that same rc 0 as "CI
green" and would have deployed an unvetted commit. The --fail-on-lock flag gives deployers an
honest verdict: rc 3 = "could not gate", retry next tick. These tests pin both semantics so
neither caller's contract can silently regress.
"""
from __future__ import annotations

import fcntl
import json

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


def _isolate(tmp_path, monkeypatch):
    """Point run_ci at a scratch root so a test can never clobber the real CI marker."""
    monkeypatch.setattr(run_ci, "_ROOT", tmp_path)
    monkeypatch.setattr(run_ci, "_LOCK", tmp_path / "ci.lock")
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)


def _marker(tmp_path):
    return json.loads((tmp_path / "data/.ci_last_run.json").read_text("utf-8"))


def test_scratch_file_failure_does_not_claim_the_desk_gate_is_down(tmp_path, monkeypatch):
    # Several agent sessions share ONE working tree on this box, so the gate also judges whatever
    # a sibling has half-written. That breakage belongs to no commit and the observer cannot fix
    # it -- it must not raise the desk-wide alarm, but the author's exit code must still be red.
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setattr(run_ci, "_STEPS", [("lint (ruff)", ["sh", "-c", "exit 1"], 60)])
    monkeypatch.setattr(run_ci, "_inflight_py", lambda: ["libs/ops/scratch.py"])
    monkeypatch.setattr(run_ci, "_scoped_to_tracked", lambda *_: ["sh", "-c", "exit 0"])
    rc = run_ci.main([])
    m = _marker(tmp_path)
    assert rc == 1, "the author running the gate must still see their own breakage"
    assert m["ok"] is False, "whole-tree meaning is preserved for pre-existing readers"
    assert m["tracked_ok"] is True, "committed code is clean -- do not cry wolf"
    assert m["failed_tracked"] == []
    assert m["inflight"] == ["libs/ops/scratch.py"], "recorded, never swallowed"


def test_committed_failure_still_escalates_even_amid_scratch_files(tmp_path, monkeypatch):
    # The expensive half: on 2026-08-05 two REAL mypy errors sat in committed code while five
    # lint errors from a sibling's scratch files filled the same red verdict. A scratch file
    # present must never mask a genuine failure.
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setattr(run_ci, "_STEPS", [("types (mypy)", ["sh", "-c", "exit 1"], 60)])
    monkeypatch.setattr(run_ci, "_inflight_py", lambda: ["libs/ops/scratch.py"])
    monkeypatch.setattr(run_ci, "_scoped_to_tracked", lambda *_: ["sh", "-c", "exit 1"])
    assert run_ci.main([]) == 1
    m = _marker(tmp_path)
    assert m["tracked_ok"] is False
    assert m["failed_tracked"] == ["types (mypy)"]


def test_unscopable_step_is_attributed_to_committed_code():
    # Fail-safe direction: attribution may only ever retract an alarm it has PROVEN belongs to
    # scratch files. A step it cannot scope (the stress harness takes no file arguments) stays
    # blamed on committed code.
    assert run_ci._scoped_to_tracked("stress harness", ["x"], ["a.py"]) is None
    assert run_ci._scoped_to_tracked("lint (ruff)", ["x"], []) is None
    assert run_ci._scoped_to_tracked("lint (ruff)", ["x"], ["a.py"])[-2:] == ["--extend-exclude",
                                                                             "a.py"]
    assert "--ignore=a.py" in run_ci._scoped_to_tracked("tests (pytest)", ["x"], ["a.py"])
    assert run_ci._scoped_to_tracked("types (mypy)", ["x"], ["a.py"])[-1] == r"(a\.py)"


def test_old_marker_without_attribution_still_escalates():
    # max_audit falls back to `ok` when `tracked_ok` is absent, so a marker written before this
    # fix keeps escalating rather than silently reading as green.
    src = (run_ci._ROOT / "scripts/max_audit.py").read_text("utf-8")
    assert 'ci.get("tracked_ok", ci.get("ok"))' in src


def test_puller_invokes_strict_and_guards_the_tree():
    # The shell half. `--fail-on-lock` is unchanged: pull_deploy must still demand the strict
    # verdict, because "another gate is mid-run" is not "green" for a deploy decision.
    #
    # THE SECOND ASSERTION MOVED UP, NOT AWAY (R0246, 2026-08-05). It used to require
    # `refused-revert-tree-moved` -- the guard that stopped an unconditional `git reset --hard`
    # from destroying a session's only copy of its work (2026-07-31, R0144). The gate now runs in
    # a detached worktree and the live tree is merged ONLY on green, so there is no revert left to
    # guard: the destroyed-work class is gone by construction rather than by a check. What is
    # pinned here now is the stronger property that replaced it -- the refusal is on the MERGE,
    # and refusing costs nothing because the tree was never touched. tests/ops/
    # test_pull_deploy_gate.py proves the ordering end-to-end against a real scratch repo.
    src = (run_ci._ROOT / "deploy/pull_deploy.sh").read_text("utf-8")
    assert "run_ci.py\" --fail-on-lock" in src
    assert "refused-merge-tree-moved" in src
    code = [ln for ln in src.splitlines() if not ln.lstrip().startswith("#")]
    assert not [ln for ln in code if "reset --hard" in ln]
