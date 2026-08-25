"""A blob over GitHub's limit must never reach a commit (L1.28b / §33 unpushed-did-not-happen).

The push-failure pager already explains that one >100MB blob rejects the whole range and needs a
history rewrite to clear. These tests pin the half that makes such a rewrite DURABLE: the snapshot
organ must refuse to stage the oversized blob in the first place, without deleting the smaller
version it already ships.
"""

from __future__ import annotations

import subprocess

import pytest
from scripts.git_snapshot import _GH_BLOB_LIMIT, _drop_oversized_blobs


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, check=False)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    r = tmp_path / "r"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    monkeypatch.chdir(r)
    return r


def test_limit_is_githubs_actual_pre_receive_limit():
    assert _GH_BLOB_LIMIT == 100 * 1024 * 1024


def test_small_files_are_left_staged(repo):
    (repo / "small.txt").write_text("fine")
    _git(repo, "add", "-A")
    assert _drop_oversized_blobs() == []
    assert "small.txt" in _git(repo, "diff", "--cached", "--name-only").stdout


def _sparse(path, size: int) -> None:
    """A file of `size` bytes that occupies ~none of the box's RAM (R0407 class).

    `/tmp` HERE IS A tmpfs ON A 3.8GB SWAPLESS BOX, so a 100MB test fixture is 100MB of RESIDENT
    memory owned by no process -- never reclaimed under pressure, invisible to every RSS check,
    and retained after the run by `tmp_path_retention_policy=failed`. Measured 2026-08-19: this
    file's two fixtures held 101MB of the 110MB under /tmp/pytest-of-quant while MemAvailable on
    the box was 167MB, and the host-tmpfs ceiling was already breached at 651MB.

    `truncate` gives the same `st_size` and the same bytes on read -- a hole reads as zeros -- so
    every assertion below is unchanged; what disappears is the allocation. This is the fixture
    doing what the code under test does: refusing to materialise 100MB it does not need.
    """
    with open(path, "wb") as fh:
        fh.truncate(size)


def test_oversized_new_file_is_unstaged_and_stays_on_disk(repo):
    big = repo / "big.bin"
    _sparse(big, _GH_BLOB_LIMIT + 1024)
    _git(repo, "add", "-A")

    over = _drop_oversized_blobs()

    assert [p for p, _ in over] == ["big.bin"]
    assert over[0][1] > _GH_BLOB_LIMIT
    # nothing staged -> the commit that would have blocked every future push cannot form
    assert "big.bin" not in _git(repo, "diff", "--cached", "--name-only").stdout
    # and the data itself is untouched: refusing to SHIP it is not deleting it
    assert big.exists() and big.stat().st_size > _GH_BLOB_LIMIT


def test_oversized_update_keeps_the_last_pushable_version_committed(repo):
    """The regression that matters: `rm --cached` here would stage a DELETION of a real backup."""
    f = repo / "backup.db"
    f.write_bytes(b"x" * 1024)                  # small, pushable ancestor
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "small backup")

    _sparse(f, _GH_BLOB_LIMIT + 1024)               # grows past the limit (sparse: see _sparse)
    _git(repo, "add", "-A")

    assert [p for p, _ in _drop_oversized_blobs()] == ["backup.db"]

    # index must be clean vs HEAD -- neither the huge update NOR a deletion is staged
    assert _git(repo, "diff", "--cached", "--name-only").stdout.strip() == ""
    assert "backup.db" in _git(repo, "ls-files").stdout          # still tracked
    assert _git(repo, "cat-file", "-s", "HEAD:backup.db").stdout.strip() == "1024"
