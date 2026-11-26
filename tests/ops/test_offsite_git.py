"""Off-site git leg: the box's own deploy key (public half only published), capped priority
selection, append pushes in batches, squash after prune, and a refused push named as such."""
from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desks" / "mt5" / "scripts"))
import offsite_git as og  # noqa: E402

from libs.ops import backup_watch as bw  # noqa: E402


def test_select_priority_cap_and_big_files(tmp_path: Path) -> None:
    ev, other = tmp_path / "evidence", tmp_path / "other"
    sizes = {str(ev / "a"): 40, str(ev / "big"): 500, str(other / "b"): 30, str(other / "c"): 50}
    keep, skipped = og.select(sizes, [str(ev)], cap=100, max_file=100, size=sizes.__getitem__)
    assert keep == sorted([str(ev / "a"), str(other / "b")])
    assert skipped[0] == (str(ev / "big"), 500) and (str(other / "c"), 50) in skipped


@pytest.mark.skipif(not shutil.which("ssh-keygen"), reason="no ssh-keygen")
def test_ensure_key_publishes_only_the_public_half(tmp_path: Path) -> None:
    key, pub = tmp_path / "secrets" / "k", tmp_path / "reports" / "K.pub"
    ok, why = og.ensure_key(key, pub)
    assert ok, why
    assert pub.read_text().startswith("ssh-ed25519 ") and "PRIVATE" not in pub.read_text()
    first = key.read_bytes()
    assert og.ensure_key(key, pub)[0] and key.read_bytes() == first   # never regenerated


def _git(*a: str, cwd: Path | None = None) -> str:
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True,
                          check=True).stdout


@pytest.mark.skipif(not shutil.which("git"), reason="no git")
def test_push_append_in_batches_then_squash_after_prune(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    _git("init", "-q", "--bare", str(remote))
    work = tmp_path / "work"
    (work / "data" / "ab").mkdir(parents=True)
    (work / "locks").mkdir()
    (work / "config").write_text("cfg")
    (work / "locks" / "l1").write_text("lock")
    for i in range(3):
        (work / "data" / "ab" / f"p{i}").write_bytes(b"x" * 600)
    key = tmp_path / "k"
    r = og.push_repo(work, key, tmp_path / "kh", url=str(remote), batch=1000)
    assert r["ok"] and r["mode"] == "append" and r["batches"] >= 2, r
    files = _git("--git-dir", str(remote), "ls-tree", "-r", "--name-only", og.BRANCH).split()
    assert "config" in files and "data/ab/p2" in files
    assert not any(f.startswith("locks") for f in files)
    assert og.push_repo(work, key, tmp_path / "kh", url=str(remote))["mode"] == "unchanged"
    (work / "data" / "ab" / "p0").unlink()                      # prune removed a pack
    (work / "data" / "ab" / "p9").write_bytes(b"y")
    r = og.push_repo(work, key, tmp_path / "kh", url=str(remote))
    assert r["ok"] and r["mode"] == "squash", r
    log = _git("--git-dir", str(remote), "rev-list", "--count", og.BRANCH).strip()
    files = _git("--git-dir", str(remote), "ls-tree", "-r", "--name-only", og.BRANCH).split()
    assert log == "1" and "data/ab/p0" not in files and "data/ab/p9" in files


def test_refused_push_is_named(tmp_path: Path) -> None:
    def run(cmd: list[str], env: object, cwd: object) -> subprocess.CompletedProcess[str]:
        bad = "push" in cmd
        return subprocess.CompletedProcess(cmd, 1 if bad else 0,
                                           "?? config\n" if "status" in cmd else "",
                                           "ERROR: deploy key access denied" if bad else "")
    (tmp_path / ".git").mkdir()
    (tmp_path / "config").write_text("c")
    r = og.push_repo(tmp_path, tmp_path / "k", tmp_path / "kh", run=run)
    assert not r["ok"] and r["key_unregistered"]
    now = datetime.now(UTC)
    assert "OFFSITE_KEY_UNREGISTERED" in bw.judge({"offsite_git": {"key_unregistered": True}}, now)


def test_load_or_init_never_replaces(tmp_path: Path) -> None:
    c = tmp_path / "s" / "offsite_git.json"
    d = og.load_or_init(c)
    assert d["password"] and og.load_or_init(c)["password"] == d["password"]
    c.write_text("not json")
    assert og.load_or_init(c) == {} and c.read_text() == "not json"


def test_over_cap_repo_is_never_pushed(tmp_path: Path) -> None:
    work = tmp_path / "w"
    (work / "data").mkdir(parents=True)
    (work / "data" / "p").write_bytes(b"x" * 2000)
    (work / ".git").mkdir()
    (work / ".git" / "big").write_bytes(b"x" * 10_000)    # git's own copy is not counted
    calls: list[list[str]] = []

    def run(cmd: list[str], env: object, cwd: object) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    assert og.repo_bytes(work) == 2000
    r = og.push_repo(work, tmp_path / "k", tmp_path / "kh", run=run, cap=1000)
    assert not r["ok"] and r["over_cap"] and calls == []
    now = datetime.now(UTC)
    assert "OFFSITE_OVER_CAP" in bw.judge({"offsite_git": {"over_cap": True}}, now)
