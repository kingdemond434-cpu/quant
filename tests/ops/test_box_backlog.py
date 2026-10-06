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


def test_an_adopted_origin_version_is_not_drained(tmp_path: Path) -> None:
    """Audit D1: Adopt-Release records an adoption as a NON-merge commit of origin's code. The box
    adopts v1, origin moves to v2: the box's v1 blob differs from origin's tip but is origin's own
    history, and draining it would revert origin."""
    remote = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "live", str(remote))
    dev = tmp_path / "dev"
    _git(tmp_path, "init", "-q", "-b", "live", str(dev))
    _git(dev, "config", "commit.gpgsign", "false")
    _write(dev, "libs/a.py", "A = 0\n")
    _git(dev, "add", ".")
    _git(dev, "commit", "-q", "-m", "v0")
    _git(dev, "remote", "add", "origin", str(remote))
    _git(dev, "push", "-q", "-u", "origin", "live")
    box = tmp_path / "box"
    _git(tmp_path, "clone", "-q", "-b", "live", str(remote), str(box))
    _write(dev, "libs/a.py", "A = 1  # v1\n")
    _git(dev, "commit", "-qam", "v1")
    _git(dev, "push", "-q", "origin", "live")
    # the box ADOPTS v1 as a non-merge commit of origin's tree (Adopt-Release's shape)
    _write(box, "libs/a.py", "A = 1  # v1\n")
    _git(box, "commit", "-qam", "adopt release v1")
    _write(dev, "libs/a.py", "A = 2  # v2\n")
    _git(dev, "commit", "-qam", "v2")
    _git(dev, "push", "-q", "origin", "live")
    _git(box, "fetch", "-q", "origin")
    doc = bb.run(box, upstream="origin/live", push=True)
    assert doc["code_touching"] == 1
    assert doc["code_paths_differing"] == 0, doc
    assert any("origin's history" in s["why"] for s in doc["skipped"])
    assert doc["push"]["pushed"] is False


def test_a_planted_secret_refuses_the_whole_push(box: tuple[Path, Path]) -> None:
    """Audit D2: the repository is public. A box-local credential file is denied by name, and a
    credential inside a code file refuses the whole push -- only path names are recorded."""
    repo, remote = box
    _write(repo, "desks/mt5/terminal.ini", "[login]\npassword=hunter2\n")
    _write(repo, "libs/b.py", 'KEY = "ghp_' + "a" * 36 + '"\n')
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "box local config")
    doc = bb.run(repo, upstream="origin/live", push=True)
    assert "desks/mt5/terminal.ini" in doc["denied_paths"]
    assert doc["secret_screen_hits"] == ["libs/b.py"]
    assert doc["push"]["pushed"] is False and doc["push"]["why"].startswith("REFUSED")
    assert "hunter2" not in json.dumps(doc) and "ghp_" not in json.dumps(doc)
    heads = _git(remote, "for-each-ref", "--format=%(refname)", "refs/heads")
    assert "box/backlog" not in heads


@pytest.mark.parametrize("rel", ["desks/mt5/terminal.ini", "x/.env", ".env.local", "a/my_secret.py",
                                 "creds/credentials.json", "k/server.pem", "k/id.key", "c.pfx",
                                 "data/secrets/x.json", "ops/github_token.txt"])
def test_denied_names(rel: str) -> None:
    assert bb._denied_name(rel)


def test_ordinary_code_is_not_denied() -> None:
    assert not bb._denied_name("libs/ops/box_backlog.py")
