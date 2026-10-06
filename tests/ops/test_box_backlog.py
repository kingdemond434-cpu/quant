"""The box backlog drain: state-only commits are superseded, box-only code goes to a review branch.

Measured 2026-10-06: the box's branch was 823 commits ahead of origin. Pushing it whole died on
HTTP 408 (#181), so the state travels as one commit on origin's tip, and this drain lifts any
box-only CODE to `box/backlog-<stamp>` -- never the live branch -- and reports the counts.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from libs.ops import box_backlog as bb
from libs.ops.box_git_env import git_env


def _git(cwd: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e"}
    return subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True,
                          text=True, env=env).stdout


def _write(repo: Path, rel: str, text: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, "utf-8")


@pytest.fixture()
def box(tmp_path: Path) -> tuple[Path, Path]:
    remote = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "live", str(remote))
    repo = tmp_path / "box"
    _git(tmp_path, "init", "-q", "-b", "live", str(repo))
    _git(repo, "config", "commit.gpgsign", "false")
    _write(repo, "libs/a.py", "A = 1\n")
    _write(repo, "desks/mt5/data/state.json", "{}")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "-q", "-u", "origin", "live")
    # backlog: two state-only commits, one code-touching commit, one code change origin also has
    _write(repo, "desks/mt5/data/state.json", '{"n": 1}')
    _git(repo, "commit", "-qam", "state 1")
    _write(repo, "libs/a.py", "A = 2  # box fix\n")
    _write(repo, "desks/mt5/data/state.json", '{"n": 2}')
    _git(repo, "commit", "-qam", "box hand fix")
    _write(repo, "desks/mt5/data/state.json", '{"n": 3}')
    _git(repo, "commit", "-qam", "state 2")
    return repo, remote


def test_classifies_state_only_and_code_touching(box: tuple[Path, Path]) -> None:
    repo, _ = box
    doc = bb.run(repo, upstream="origin/live", push=False)
    assert doc["verdict"] == "MEASURED"
    assert (doc["ahead"], doc["state_only"], doc["code_touching"]) == (3, 2, 1)
    assert doc["code_paths"] == ["libs/a.py"]
    assert doc["push"]["pushed"] is False


def test_pushes_box_code_to_a_review_branch_only(box: tuple[Path, Path], tmp_path: Path) -> None:
    repo, remote = box
    now = datetime(2026, 10, 6, 16, 30, tzinfo=UTC)
    out = tmp_path / "BOX_BACKLOG.json"
    doc = bb.run(repo, upstream="origin/live", push=True, now=now, out=out)
    assert doc["push"]["pushed"] is True, doc
    assert doc["push"]["branch"] == "box/backlog-20261006-1630"
    heads = _git(remote, "for-each-ref", "--format=%(refname)", "refs/heads")
    assert "refs/heads/box/backlog-20261006-1630" in heads
    shown = _git(remote, "show", "box/backlog-20261006-1630:libs/a.py")
    assert "box fix" in shown
    # the review commit sits on origin's tip and carries no state
    assert _git(remote, "rev-parse", "box/backlog-20261006-1630^") == _git(remote, "rev-parse",
                                                                           "live")
    assert _git(remote, "show", "box/backlog-20261006-1630:desks/mt5/data/state.json") == "{}"
    # the live branch itself is untouched
    assert "box fix" not in _git(remote, "show", "live:libs/a.py")
    # a second run with the same box code does not mint another branch
    out.write_text(json.dumps(doc), "utf-8")
    again = bb.run(repo, upstream="origin/live", push=True,
                   now=datetime(2026, 10, 7, 16, 30, tzinfo=UTC), out=out)
    assert again["push"].get("repeated") is True
    assert "20261007" not in _git(remote, "for-each-ref", "--format=%(refname)", "refs/heads")


@pytest.mark.parametrize("ref", ["claude/llm-auto-upgrade-verify-gcjac3", "production", "master",
                                 "release/x", "refs/heads/production", "feature/x"])
def test_refuses_every_ref_but_a_review_branch(ref: str) -> None:
    with pytest.raises(ValueError):
        bb._assert_review_ref(ref)


def test_code_origin_already_has_is_not_drained(box: tuple[Path, Path]) -> None:
    repo, remote = box
    other = remote.parent / "other"
    _git(remote.parent, "clone", "-q", "-b", "live", str(remote), str(other))
    _write(other, "libs/a.py", "A = 2  # box fix\n")
    _git(other, "commit", "-qam", "origin caught up")
    _git(other, "push", "-q", "origin", "live")
    _git(repo, "fetch", "-q", "origin")
    doc = bb.run(repo, upstream="origin/live", push=True)
    assert doc["code_touching"] == 1 and doc["code_paths_differing"] == 0
    assert doc["push"]["pushed"] is False


def test_unreadable_backlog_is_unmeasured(tmp_path: Path) -> None:
    doc = bb.run(tmp_path, upstream="origin/live", push=False)
    assert doc["verdict"] == "UNMEASURED"


def test_git_env_appends_safe_directory_and_keeps_the_callers_entries() -> None:
    base = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
            "GIT_CONFIG_VALUE_0": "AUTHORIZATION: basic eA=="}
    env = git_env(Path("C:\\opt\\quant"), base)
    assert env["GIT_CONFIG_COUNT"] == "2"
    assert env["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraheader"
    assert (env["GIT_CONFIG_KEY_1"], env["GIT_CONFIG_VALUE_1"]) == ("safe.directory",
                                                                     "C:/opt/quant")
    assert git_env(Path("C:\\opt\\quant"), env)["GIT_CONFIG_COUNT"] == "2", "idempotent"
