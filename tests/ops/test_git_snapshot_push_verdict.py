"""The offsite snapshot must not announce success for a push the remote refused.

`git push` EXITS 0 ON A REMOTE REJECT: the pre-receive hook declines, the transport succeeded,
and the exit code reports the transport. This desk has paid for that at least three times, and
on 2026-08-28 it was still live in the one organ whose product is an offsite copy --
daily_research_cycle recorded:

    [git_snapshot] {'ok': True, 'rc': 0, 'tail': ' ! [remote rejected]   HEAD -> desk-sy'}

i.e. the snapshot reported green while shipping nothing. A backup that reports green while
shipping nothing is worse than no backup: it is the failure nobody goes looking for.

These tests drive the real verdict function with a stubbed `_git`, so they exercise behaviour
rather than asserting on source text.
"""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from scripts import git_snapshot


def _proc(rc: int = 0, out: str = "", err: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["git"], returncode=rc, stdout=out, stderr=err)


@pytest.fixture
def fake_git(monkeypatch):
    """Route every _git call through a scripted table keyed on the first argument."""
    calls: list[tuple[str, ...]] = []
    table: dict[str, subprocess.CompletedProcess[str]] = {}

    def _fake(*args: str):
        calls.append(args)
        return table.get(args[0], _proc())

    monkeypatch.setattr(git_snapshot, "_git", _fake)
    return SimpleNamespace(calls=calls, table=table)


def _on_remote(fake, *, landed: bool, sha: str = "abc123") -> None:
    fake.table["rev-parse"] = _proc(0, "desk-sync-clean\n")
    fake.table["ls-remote"] = _proc(0, f"{sha}\trefs/heads/desk-sync-clean\n")
    fake.table["merge-base"] = _proc(0 if landed else 1)


def test_a_remote_reject_is_never_reported_as_pushed(fake_git, capsys):
    """The exact shape seen in production: rc=0 with '! [remote rejected]' in the output."""
    _on_remote(fake_git, landed=False)
    git_snapshot._report_push(_proc(0, "", " ! [remote rejected]   HEAD -> desk-sync-clean\n"))
    said = capsys.readouterr().out
    assert "PUSH DID NOT LAND" in said
    assert "REJECTED by the remote" in said
    assert "pushed to GitHub" not in said


def test_exit_zero_that_did_not_reach_the_remote_is_caught_by_the_second_arm(fake_git, capsys):
    """Silent non-landing with no refusal word: only the remote check can catch this."""
    _on_remote(fake_git, landed=False)
    git_snapshot._report_push(_proc(0, "Everything up-to-date\n"))
    said = capsys.readouterr().out
    assert "PUSH DID NOT LAND" in said
    assert "HEAD is not on the upstream ref" in said


def test_a_genuine_push_still_reports_success(fake_git, capsys):
    """The fix must not turn every healthy push into a false alarm."""
    _on_remote(fake_git, landed=True)
    git_snapshot._report_push(_proc(0, "To github.com:x/y.git\n   a1b2c3d..e4f5g6h  HEAD\n"))
    assert "pushed to GitHub" in capsys.readouterr().out


def test_the_remote_check_asks_the_server_not_a_local_tracking_ref(fake_git):
    """`@{u}` is a local cache and need not exist at all when pushing `origin HEAD`."""
    _on_remote(fake_git, landed=True)
    assert git_snapshot._head_is_on_remote() is True
    assert any(c[0] == "ls-remote" for c in fake_git.calls), fake_git.calls
    assert not any("@{u}" in a for c in fake_git.calls for a in c), fake_git.calls


def test_a_detached_head_never_claims_to_have_landed(fake_git):
    """Detached: there is no branch to compare, so the honest answer is 'not verified'."""
    fake_git.table["rev-parse"] = _proc(0, "HEAD\n")
    assert git_snapshot._head_is_on_remote() is False


def test_an_unreachable_remote_is_not_read_as_landed(fake_git, capsys):
    """A failed ls-remote is UNMEASURED, and unmeasured never resolves to clean (L1.28a)."""
    fake_git.table["rev-parse"] = _proc(0, "desk-sync-clean\n")
    fake_git.table["ls-remote"] = _proc(128, "", "fatal: could not read from remote repository")
    assert git_snapshot._head_is_on_remote() is False
    git_snapshot._report_push(_proc(0, "Everything up-to-date\n"))
    assert "PUSH DID NOT LAND" in capsys.readouterr().out
