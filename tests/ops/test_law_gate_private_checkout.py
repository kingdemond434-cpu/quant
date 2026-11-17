"""run_law_gate._at_head: the private HEAD checkout never touches the caller's repository, even
with git's own GIT_DIR in the environment (as inside the pre-push hook), and it lands where
there is room for it."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from scripts import run_law_gate as lg


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True,
                          check=True).stdout  # fmt: skip


@pytest.fixture
def sparse_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for k in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        monkeypatch.setenv(k, "t")
    for k in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(k, "t@t")
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    r = tmp_path / "r"
    (r / "code").mkdir(parents=True)
    (r / "state").mkdir()
    (r / "code" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (r / "state" / "s.json").write_text("{}\n", encoding="utf-8")
    _git(r, "init", "-q", "-b", "main")
    _git(r, "add", ".")
    _git(r, "commit", "-q", "-m", "base")
    _git(r, "sparse-checkout", "set", "--no-cone", "/code/")
    return r


def _caller(r: Path) -> tuple[str, str, str]:
    return (_git(r, "config", "--bool", "core.sparseCheckout").strip(),
            _git(r, "ls-files", "-t"), _git(r, "status", "--porcelain"))  # fmt: skip


@pytest.mark.parametrize("hooked", [False, True], ids=["plain", "inside-a-hook"])
def test_the_private_checkout_leaves_the_callers_sparsity_alone(
    sparse_repo: Path, monkeypatch: pytest.MonkeyPatch, hooked: bool
) -> None:
    before = _caller(sparse_repo)
    assert before[0] == "true" and "S state/s.json" in before[1] and before[2] == ""
    if hooked:  # what git exports into a pre-push hook
        monkeypatch.setenv("GIT_DIR", str(sparse_repo / ".git"))
    where, subject, why = lg._at_head(sparse_repo)
    try:
        assert where != sparse_repo and why == [], subject
        assert (where / "state" / "s.json").is_file()  # the checkout holds the whole tree
        monkeypatch.delenv("GIT_DIR", raising=False)
        assert _caller(sparse_repo) == before  # sparse config, skip bits, status: untouched
    finally:
        subprocess.run(["git", "-C", str(sparse_repo), "worktree", "remove", "--force",
                        str(where)], capture_output=True, check=False)  # fmt: skip


def test_the_rerun_does_not_inherit_the_callers_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_DIR", "/elsewhere/.git")
    monkeypatch.setenv("GIT_INDEX_FILE", "/elsewhere/.git/index")
    env = lg._private_env(QUANT_LAWGATE_IN_PLACE="1")
    assert "GIT_DIR" not in env and "GIT_INDEX_FILE" not in env
    assert env["QUANT_LAWGATE_IN_PLACE"] == "1"
    src = Path(lg.__file__).read_text("utf-8")
    assert 'env = {**os.environ, "QUANT_LAWGATE_IN_PLACE"' not in src


def test_a_full_disk_moves_the_checkout_to_a_place_with_room(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    disk = tmp_path / "cache" / "quant-lawgate"
    monkeypatch.setattr(lg, "_free", lambda p: 10 if Path(p) == disk else 10**12)
    assert lg._checkout_base(0) == disk  # no size known: the disk, as before
    assert lg._checkout_base(5) == disk  # the disk has room: the disk
    assert lg._checkout_base(1000) != disk  # it does not: somewhere that does
    monkeypatch.setattr(lg, "_free", lambda p: 10)
    assert lg._checkout_base(1000) == disk  # nowhere has room: the disk, and the error is reported
