"""A HEAD law verdict covers the full tree even from a sparse source checkout."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from scripts.run_law_gate import _at_head


@pytest.mark.parametrize("dirty", [True, False])
@pytest.mark.parametrize("orphan_skip_bit", [True, False])
def test_sparse_caller_does_not_remove_committed_fence_inputs(tmp_path: Path,
                                                           monkeypatch, dirty: bool,
                                                           orphan_skip_bit: bool) -> None:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=tmp_path, capture_output=True,
                              text=True, check=True).stdout

    git("init", "-q")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "test")
    for name in ("source", "policy"):
        (tmp_path / name).mkdir()
    (tmp_path / "source" / "code.txt").write_text("committed", encoding="utf-8")
    (tmp_path / "policy" / "seal.txt").write_text("sealed", encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "fixture")
    git("sparse-checkout", "set", "source")
    if dirty:
        (tmp_path / "source" / "code.txt").write_text("dirty", encoding="utf-8")
    assert not (tmp_path / "policy" / "seal.txt").exists()
    if orphan_skip_bit:
        # Reproduce a per-file bit surviving the sparse-mode transition, as the
        # operator's manually staged seal did. Use real Git for the final restore.
        import scripts.run_law_gate as gate

        run = gate._checkout_run

        def retained_skip(args, **kwargs):
            result = run(args, **kwargs)
            if args[-2:] == ["sparse-checkout", "disable"] and result.returncode == 0:
                worktree = Path(args[args.index("-C") + 1])
                subprocess.run(["git", "-C", str(worktree), "update-index",
                                "--skip-worktree", "policy/seal.txt"], check=True,
                               capture_output=True)
                (worktree / "policy" / "seal.txt").unlink()
            return result

        monkeypatch.setattr(gate, "_checkout_run", retained_skip)
    where, subject, errors = _at_head(tmp_path)
    try:
        assert errors == [] and "HEAD" in subject
        assert (where / "policy" / "seal.txt").read_text("utf-8") == "sealed"
        assert (where / "source" / "code.txt").read_text("utf-8") == "committed"
        assert not (tmp_path / "policy" / "seal.txt").exists()
        assert git("sparse-checkout", "list").strip() == "source"
    finally:
        git("worktree", "remove", "--force", str(where))


def test_a_hook_environment_never_reaches_the_callers_sparse_settings(tmp_path: Path,
                                                                    monkeypatch) -> None:
    """Git runs pre-push with GIT_DIR naming the pushing worktree. Reproduced 2026-11-05: the
    private checkout's `sparse-checkout disable` obeyed that GIT_DIR and wrote
    core.sparseCheckout=false into the BUILDER'S config.worktree on every push."""
    main, builder = tmp_path / "main", tmp_path / "builder"
    main.mkdir()

    def git(cwd: Path, *args: str) -> str:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                              text=True, check=True).stdout

    git(main, "init", "-q")
    git(main, "config", "user.email", "test@example.invalid")
    git(main, "config", "user.name", "test")
    for name in ("source", "policy"):
        (main / name).mkdir()
    (main / "source" / "code.txt").write_text("committed", encoding="utf-8")
    (main / "policy" / "seal.txt").write_text("sealed", encoding="utf-8")
    git(main, "add", "-A")
    git(main, "commit", "-qm", "fixture")
    git(main, "worktree", "add", "-q", "--detach", str(builder), "HEAD")
    git(builder, "sparse-checkout", "set", "--no-cone", "/source/")
    (builder / "source" / "code.txt").write_text("dirty", encoding="utf-8")
    gitdir = git(builder, "rev-parse", "--absolute-git-dir").strip()
    # What git exports to a hook in a linked worktree.
    monkeypatch.setenv("GIT_DIR", gitdir)
    monkeypatch.setenv("GIT_COMMON_DIR", str(main / ".git"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(Path(gitdir) / "index"))
    where, subject, errors = _at_head(builder)
    monkeypatch.delenv("GIT_DIR")
    monkeypatch.delenv("GIT_COMMON_DIR")
    monkeypatch.delenv("GIT_INDEX_FILE")
    try:
        assert errors == [] and "HEAD" in subject and where != builder
        assert (where / "policy" / "seal.txt").read_text("utf-8") == "sealed"
        assert (where / "source" / "code.txt").read_text("utf-8") == "committed"
        assert git(builder, "config", "--bool", "core.sparseCheckout").strip() == "true"
        assert git(builder, "sparse-checkout", "list").strip() == "/source/"
        assert not (builder / "policy" / "seal.txt").exists()
        assert (builder / "source" / "code.txt").read_text("utf-8") == "dirty"
    finally:
        git(builder, "worktree", "remove", "--force", str(where))
