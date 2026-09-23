"""L1.55 -- an absent gitignored artifact is evidence about the VANTAGE POINT, not about the box."""
from __future__ import annotations

from pathlib import Path

from libs.ops import box_state


def test_a_main_checkout_reads_itself(tmp_path):
    (tmp_path / ".git").mkdir()
    root, basis = box_state.data_root(tmp_path)
    assert (root, basis) == (tmp_path, box_state.OWN)
    assert box_state.resolved(basis)


def test_an_explicit_root_with_no_git_is_taken_at_its_word(tmp_path):
    """Every fence test hands this function a bare tmp_path. Second-guessing an explicit
    instruction would break them all and would be its own defect."""
    root, basis = box_state.data_root(tmp_path)
    assert (root, basis) == (tmp_path, box_state.OWN)


def test_a_linked_worktree_resolves_to_the_checkout_that_holds_the_state(tmp_path):
    main = tmp_path / "main"
    (main / ".git").mkdir(parents=True)
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {main}/.git/worktrees/wt\n", "utf-8")

    root, basis = box_state.data_root(wt)
    assert (root, basis) == (main, box_state.MAIN_WORKTREE)
    assert box_state.resolved(basis)
    assert "gitignored" in box_state.describe(root, basis)


def test_a_vanished_main_checkout_is_UNRESOLVED_not_a_silent_fallback(tmp_path):
    """The silent fallback to `this worktree` IS the defect -- it is what turns an unreadable
    vantage point into a confident verdict about the box."""
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {tmp_path}/gone/.git/worktrees/wt\n", "utf-8")

    _, basis = box_state.data_root(wt)
    assert basis == box_state.UNRESOLVED
    assert not box_state.resolved(basis)


def test_a_submodule_style_gitfile_is_UNRESOLVED(tmp_path):
    """A `.git` FILE that names no worktree segment: we do not know where this box keeps its
    state, and guessing is how a fabricated verdict gets made."""
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / ".git").write_text("gitdir: ../.git/modules/sub\n", "utf-8")
    _, basis = box_state.data_root(sub)
    assert basis == box_state.UNRESOLVED


def test_an_unreadable_gitfile_is_UNRESOLVED(tmp_path):
    d = tmp_path / "wt"
    d.mkdir()
    (d / ".git").write_bytes(b"\xff\xfe not utf-8 and not a marker")
    _, basis = box_state.data_root(d)
    assert basis == box_state.UNRESOLVED


def test_the_real_repo_resolves_from_wherever_this_test_runs():
    """The live property: this suite runs from a worktree and from the main checkout, and both
    must land on a root that actually holds the box's gitignored state."""
    here = Path(__file__).resolve().parent.parent.parent
    root, basis = box_state.data_root(here)
    assert box_state.resolved(basis), box_state.describe(root, basis)
    assert (root / ".git").is_dir()
