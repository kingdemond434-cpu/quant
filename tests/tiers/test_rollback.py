"""Tier S layer 28: the one-operation rollback, against a throwaway git repository.

Nothing here touches this clone: every call names its own `root`, a repo built in `tmp_path`
with a LIVE_MANIFEST that seals one commit and not another.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from libs.tiers import rollback


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True,
                          text=True).stdout.strip()


def _commit(root: Path, msg: str) -> str:
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", msg)
    return _git(root, "rev-parse", "HEAD")


@pytest.fixture()
def repo(tmp_path: Path) -> dict[str, object]:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "rollback-test")
    _git(root, "config", "core.hooksPath", "/dev/null")
    (root / "libs").mkdir()
    (root / "libs" / "a.py").write_text("A = 1\n")
    (root / "libs" / "old.py").write_text("OLD = True\n")
    data = root / "desks" / "mt5" / "data"
    data.mkdir(parents=True)
    (data / "ledger.jsonl").write_text('{"n": 1}\n')
    sealed = _commit(root, "release 1")
    (data / "LIVE_MANIFEST.jsonl").write_text(json.dumps({"code": sealed}) + "\n")
    _commit(root, "seal release 1")
    # the next, unsealed code: a.py edited, old.py removed, new.py added, state appended
    (root / "libs" / "a.py").write_text("A = 2\n")
    (root / "libs" / "old.py").unlink()
    (root / "libs" / "new.py").write_text("NEW = True\n")
    (data / "ledger.jsonl").write_text('{"n": 1}\n{"n": 2}\n')
    unsealed = _commit(root, "release 2 (never sealed)")
    (root / "libs" / "a.py").write_text("A = 3\n")
    head = _commit(root, "release 3")
    return {"root": root, "sealed": sealed, "unsealed": unsealed, "head": head}


def test_sealed_releases_reads_the_manifest(repo: dict[str, object]) -> None:
    root = repo["root"]
    assert isinstance(root, Path)
    assert rollback.sealed_releases(root) == [repo["sealed"]]


def test_plan_names_code_paths_and_keeps_state(repo: dict[str, object]) -> None:
    root = repo["root"]
    assert isinstance(root, Path)
    p = rollback.plan(None, root=root)                 # default: the previous sealed release
    assert p["available"] and p["sealed"] and p["target"] == repo["sealed"]
    assert sorted(p["code_paths"]) == ["libs/a.py", "libs/new.py", "libs/old.py"]  # type: ignore
    # ledger.jsonl and LIVE_MANIFEST are state: the box's state is the box's
    assert p["state_paths_kept"] == 2


def test_apply_makes_one_commit_whose_code_equals_the_sealed_target(
        repo: dict[str, object]) -> None:
    root = repo["root"]
    assert isinstance(root, Path)
    before = int(_git(root, "rev-list", "--count", "HEAD"))
    p = rollback.plan(str(repo["sealed"])[:10], root=root)   # a short SHA resolves too
    sha = rollback.apply(p, root=root)
    assert int(_git(root, "rev-list", "--count", "HEAD")) == before + 1, "exactly one commit"
    assert _git(root, "rev-parse", "HEAD~1") == repo["head"], "history is never rewritten"
    assert sha == _git(root, "rev-parse", "HEAD")
    assert (root / "libs" / "a.py").read_text() == "A = 1\n"
    assert (root / "libs" / "old.py").exists() and not (root / "libs" / "new.py").exists()
    # code now equals the target's; state does not move
    assert _git(root, "diff", "--name-only", str(repo["sealed"]), "HEAD", "--", "libs") == ""
    ledger = root / "desks" / "mt5" / "data" / "ledger.jsonl"
    assert ledger.read_text().count("\n") == 2
    assert _git(root, "status", "--porcelain") == ""
    # a second plan to the same target has nothing left to do
    again = rollback.plan(str(repo["sealed"]), root=root)
    assert rollback.apply(again, root=root).startswith("nothing to roll back")


def test_apply_refuses_an_unsealed_target_before_touching_anything(
        repo: dict[str, object]) -> None:
    root = repo["root"]
    assert isinstance(root, Path)
    p = rollback.plan(str(repo["unsealed"]), root=root)
    assert p["available"] and not p["sealed"]
    with pytest.raises(rollback.RollbackRefused, match="not a sealed release"):
        rollback.apply(p, root=root)
    assert _git(root, "rev-parse", "HEAD") == repo["head"]
    assert (root / "libs" / "a.py").read_text() == "A = 3\n"


def test_unknown_target_and_missing_manifest_are_unavailable(tmp_path: Path,
                                                             repo: dict[str, object]) -> None:
    root = repo["root"]
    assert isinstance(root, Path)
    bad = rollback.plan("0" * 40, root=root)
    assert bad["available"] is False and "not a commit" in str(bad["why"])
    with pytest.raises(rollback.RollbackRefused):
        rollback.apply(bad, root=root)
    (root / "desks" / "mt5" / "data" / "LIVE_MANIFEST.jsonl").unlink()
    none = rollback.plan(None, root=root)
    assert none["available"] is False and "no earlier sealed release" in str(none["why"])
