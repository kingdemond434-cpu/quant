"""LANDED+CLEAN+IDLE reaps at 8h; unlanded-but-CLEAN reaps at 72h; unmeasured is KEPT.

The reap is lossless because of ONE condition -- the tip is already an ancestor of the live branch
-- not because a tree looks old or finished. Every other condition guards a different way this
could destroy work, and the idle measurement itself nearly got it wrong once (see the module
docstring: a `find` that exited 0 on a rejected argument scored every tree "idle 56 years").
"""
from __future__ import annotations

from pathlib import Path

import pytest

from libs.ops.worktree_reaper import Worktree, reap_plan


def wt(name: str = "w", *, landed: bool = True, dirty: int = 0,
       idle_h: float | None = 24.0, size_mb: int = 500) -> Worktree:
    return Worktree(path=Path(f"/tmp/{name}"), tip="a" * 40, landed=landed, dirty=dirty,
                    idle_h=idle_h, size_mb=size_mb)


class TestVerdict:
    def test_landed_clean_and_idle_is_reapable(self) -> None:
        assert wt().verdict == "REAP"

    def test_unlanded_clean_reaps_only_after_long_cooloff(self) -> None:
        """KEEP-AHEAD protects the BRANCH, not the checkout: a clean tree's commits live in
        shared .git, so past 72h idle the DIRECTORY is redundant (measured 2026-08-26: 25 such
        trees held ~3.5GB and froze the moat backup under its 15%-free disk fuse). DIRTY stays
        absolute -- the working copy may be the sole copy."""
        assert wt(landed=False, idle_h=24.0).verdict == "KEEP-AHEAD"
        assert wt(landed=False, idle_h=71.99).verdict == "KEEP-AHEAD"
        assert wt(landed=False, idle_h=72.0).verdict == "REAP-CLEAN-AHEAD"
        assert wt(landed=False, idle_h=1000.0).verdict == "REAP-CLEAN-AHEAD"
        assert wt(landed=False, dirty=1, idle_h=1000.0).verdict == "KEEP-DIRTY"
        assert wt(landed=False, idle_h=None).verdict == "KEEP-UNMEASURED"

    def test_dirty_is_never_reaped(self) -> None:
        assert wt(dirty=1).verdict == "KEEP-DIRTY"

    def test_recently_active_is_kept(self) -> None:
        assert wt(idle_h=1.0).verdict == "KEEP-ACTIVE"

    def test_boundary_is_inclusive(self) -> None:
        assert wt(idle_h=8.0).verdict == "REAP"
        assert wt(idle_h=7.99).verdict == "KEEP-ACTIVE"

    def test_unmeasured_idle_is_KEPT_not_reaped(self) -> None:
        """A failed measurement must resolve to the SAFE answer, never the permissive one (L1.28a).

        This is the exact case that nearly reaped live sessions: the idle probe failed silently
        and every tree read maximally stale.
        """
        assert wt(idle_h=None).verdict == "KEEP-UNMEASURED"

    def test_conditions_compose__dirty_and_unlanded_still_kept(self) -> None:
        assert wt(landed=False, dirty=3).verdict == "KEEP-DIRTY"

    @pytest.mark.parametrize("min_idle", [1.0, 48.0])
    def test_threshold_is_injectable(self, min_idle: float) -> None:
        w = Worktree(path=Path("/tmp/w"), tip="a" * 40, landed=True, dirty=0, idle_h=24.0,
                     size_mb=1, _min_idle_h=min_idle)
        assert w.verdict == ("REAP" if min_idle <= 24.0 else "KEEP-ACTIVE")


class TestPlan:
    def test_plan_selects_only_reap(self) -> None:
        trees = [wt("a"), wt("b", landed=False), wt("c", dirty=2), wt("d", idle_h=None)]
        reapable, hist = reap_plan(trees)
        assert [w.path.name for w in reapable] == ["a"]
        assert hist == {"REAP": 1, "KEEP-AHEAD": 1, "KEEP-DIRTY": 1, "KEEP-UNMEASURED": 1}

    def test_empty_input_reports_an_empty_histogram(self) -> None:
        """A reap that freed nothing must be distinguishable from one that examined nothing."""
        reapable, hist = reap_plan([])
        assert reapable == [] and hist == {}


# --------------------------------------------------------------- R0603 residue, 2026-08-20 ----
def test_symlink_into_a_live_tree_does_not_refresh_idle(tmp_path) -> None:
    """A symlink's mtime is its TARGET's, and the target is often the live repo.

    Measured: qp-owed-b3-absorb held three symlinks to data/ files cron rewrites hourly, so the
    reaper computed idle 3.2h against a true local idle of 174.7h -- the age gate permanently
    disabled for any tree containing such a link.
    """
    import os
    import time as _t

    from libs.ops.worktree_reaper import _newest_mtime

    tree = tmp_path / "tree"
    (tree / "sub").mkdir(parents=True)
    old = tree / "sub" / "local.py"
    old.write_text("x", "utf-8")
    stale = _t.time() - 200 * 3600
    os.utime(old, (stale, stale))

    fresh = tmp_path / "live_repo_file.json"          # stands in for the live main checkout
    fresh.write_text("{}", "utf-8")                   # mtime = now
    (tree / "linked.json").symlink_to(fresh)

    newest = _newest_mtime(tree)
    assert newest is not None
    assert newest == pytest.approx(stale, abs=5), (
        "the symlink's target mtime must not be read as local activity")


def test_a_tree_of_only_symlinks_is_unmeasured_not_zero(tmp_path) -> None:
    """L1.28a: absence of measurable local work must not resolve to a reapable verdict."""
    from libs.ops.worktree_reaper import _newest_mtime

    tree = tmp_path / "tree"
    tree.mkdir()
    target = tmp_path / "elsewhere.txt"
    target.write_text("x", "utf-8")
    (tree / "only.txt").symlink_to(target)
    assert _newest_mtime(tree) is None, "None -> KEEP-UNMEASURED, which never reaps"


def test_discover_excludes_the_primary_checkout(tmp_path) -> None:
    """Running from a worktree must never put the MAIN checkout on the candidate list."""
    import os
    import subprocess

    from scripts.reap_worktrees import discover, primary

    main = tmp_path / "main"
    main.mkdir()
    subprocess.run(["git", "init", "-q", str(main)], check=True)
    subprocess.run(["git", "-C", str(main), "commit", "-q", "--allow-empty", "-m", "x"],
                   check=True, env={**os.environ, "GIT_AUTHOR_NAME": "t",
                                    "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                                    "GIT_COMMITTER_EMAIL": "t@t"})
    wt = tmp_path / "wt"
    subprocess.run(["git", "-C", str(main), "worktree", "add", "-q", str(wt)], check=True)

    # asked FROM the worktree -- the case that listed the 9.6GB live tree as a candidate
    assert primary(wt).resolve() == main.resolve()
    assert main.resolve() not in {p.resolve() for p in discover(wt, str(tmp_path))}
    assert wt.resolve() in {p.resolve() for p in discover(wt, str(tmp_path))}


class TestRemoveCheckout:
    """remove_checkout escalates to --force ONLY for expected-untracked dirt, re-verified at
    removal time (measured 2026-08-26: all 9 clean-ahead candidates failed plain removal on
    `?? .venv` while genuinely-dirty trees must stay refused)."""

    @pytest.fixture()
    def repo_with_worktree(self, tmp_path: Path) -> tuple[Path, Path]:
        import subprocess
        repo, wt_dir = tmp_path / "repo", tmp_path / "wt"
        repo.mkdir()
        def run(*a: str) -> None:
            subprocess.run(a, cwd=repo, capture_output=True, text=True, check=True)
        run("git", "init", "-q")
        run("git", "config", "user.email", "t@t")
        run("git", "config", "user.name", "t")
        (repo / "f.txt").write_text("x")
        run("git", "add", "f.txt")
        run("git", "commit", "-q", "-m", "base")
        run("git", "worktree", "add", "-q", "--detach", str(wt_dir))
        return repo, wt_dir

    def test_venv_only_dirt_is_force_removed(self, repo_with_worktree: tuple[Path, Path]) -> None:
        from libs.ops.worktree_reaper import remove_checkout
        repo, wt_dir = repo_with_worktree
        (wt_dir / ".venv").mkdir()
        (wt_dir / ".venv" / "lib.py").write_text("cache")
        ok, why = remove_checkout(wt_dir, repo)
        assert ok, why
        assert not wt_dir.exists()

    def test_real_dirt_refuses(self, repo_with_worktree: tuple[Path, Path]) -> None:
        from libs.ops.worktree_reaper import remove_checkout
        repo, wt_dir = repo_with_worktree
        (wt_dir / "f.txt").write_text("MODIFIED -- the sole copy")
        ok, why = remove_checkout(wt_dir, repo)
        assert not ok
        assert "unexpected dirt" in why
        assert wt_dir.exists()
        assert (wt_dir / "f.txt").read_text() == "MODIFIED -- the sole copy"

    def test_untracked_non_venv_refuses(self, repo_with_worktree: tuple[Path, Path]) -> None:
        from libs.ops.worktree_reaper import remove_checkout
        repo, wt_dir = repo_with_worktree
        (wt_dir / "notes.md").write_text("uncommitted finding")
        ok, _why = remove_checkout(wt_dir, repo)
        assert not ok
        assert wt_dir.exists()
