"""The adoption sequence must land a tree without ever unlinking, and restore the sync.

WHAT BROKE. The hard power-off of 2026-09-07 left one tracked path with a corrupt NTFS directory
entry, so every filesystem call that goes through DeleteFile/MoveFile returned EINVAL:

    error: unable to unlink old 'desks/mt5/side_channels/run_external_backtest.py':
    Invalid argument

`git merge`, `git checkout <ref> -- .` and `git pull` all update a file by unlinking the old one,
so all three died on that single path and took the WHOLE adoption with them -- and `Sync-Pull`
exits 1 before it publishes, which is the desk going silent again from a new cause.

`scripts/Adopt-Release.ps1` lands the tree by rewriting each file's CONTENTS in place
(FileMode.Truncate never touches the directory entry) and only then records the merge. This
suite pins the two halves of that claim.

THE GIT SEQUENCE is checked on a real repository, because it is where the subtle failure lives:
recording the merge with `-s ours` keeps THIS tree, so if the tree does not already match the
target, recording it BURIES the incoming work under a commit that claims to contain it. The
ordering -- write, stage, commit, VERIFY, only then record -- is the safety property, and the
final assertion is the one that actually matters operationally: a later `git merge` must be a
no-op, or the box repeats this every hour and nothing has been fixed.

THE UNLINK HALF needs a filesystem that refuses to unlink. A read-only parent directory does
that for an ordinary user and does NOT for root, which ignores the permission bits, so that half
skips under a root CI runner rather than passing vacuously.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
SCRIPT = BASE / "scripts" / "Adopt-Release.ps1"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, capture_output=True, text=True,
    ).stdout


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "box"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    return repo


def _adopt(repo: Path, target: str) -> list[str]:
    """The script's steps 2-5, in Python, against a real repository.

    Deliberately a re-implementation rather than a call: PowerShell does not exist on the CI
    runner, and the thing worth pinning is the GIT sequence -- which calls, in which order, and
    what each one leaves behind. The in-place write is `r+b`/truncate for the same reason the
    script uses FileMode.Truncate: it rewrites the bytes of an existing entry and issues no
    unlink.
    """
    records = _git(repo, "-c", "core.quotePath=false", "diff",
                   "--name-status", "HEAD", target).splitlines()
    staged: list[str] = []
    for rec in [r for r in records if r.strip()]:
        cols = rec.split("\t")
        ops = ([("D", cols[1]), ("A", cols[2])] if cols[0][0] in "RC"
               else [(cols[0][0], cols[1])])
        for kind, rel in ops:
            full = repo / rel
            if kind == "D":
                full.unlink(missing_ok=True)
            else:
                blob = subprocess.run(
                    ["git", "-C", str(repo), "cat-file", "blob", f"{target}:{rel}"],
                    check=True, capture_output=True,
                ).stdout
                full.parent.mkdir(parents=True, exist_ok=True)
                if full.exists():
                    with open(full, "r+b") as fh:      # no unlink: truncate in place
                        fh.truncate(0)
                        fh.write(blob)
                else:
                    full.write_bytes(blob)
            staged.append(rel)
    if staged:
        _git(repo, "add", "--all", "--", *staged)
        if _git(repo, "diff", "--cached", "--name-only").strip():
            _git(repo, "commit", "-q", "-m", "Adopt in place")
    return staged


def test_the_sequence_lands_the_tree_and_makes_a_later_merge_a_no_op(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "desks").mkdir()
    (repo / "desks" / "backtest.py").write_text("old\n")
    (repo / "desks" / "gone.py").write_text("doomed\n")
    _git(repo, "add", "--", "desks/backtest.py", "desks/gone.py")
    _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD").strip()

    # The incoming release: one path modified, one added, one deleted.
    _git(repo, "checkout", "-q", "-b", "release")
    (repo / "desks" / "backtest.py").write_text("new, with a cursor and a budget\n")
    (repo / "desks" / "gone.py").unlink()
    (repo / "desks" / "enrol.py").write_text("enrol_clocks\n")
    _git(repo, "add", "--all", "--", "desks")
    _git(repo, "commit", "-q", "-m", "release")
    target = _git(repo, "rev-parse", "HEAD").strip()

    _git(repo, "checkout", "-q", "main")
    assert _git(repo, "rev-parse", "HEAD").strip() == base

    _adopt(repo, target)

    # 1. The tree matches the target -- the gate the script refuses to record the merge without.
    assert _git(repo, "diff", "--name-only", "HEAD", target).strip() == ""
    assert (repo / "desks" / "backtest.py").read_text() == "new, with a cursor and a budget\n"
    assert (repo / "desks" / "enrol.py").exists()
    assert not (repo / "desks" / "gone.py").exists()

    # 2. Recording the merge changes no file.
    before = (repo / "desks" / "backtest.py").read_text()
    _git(repo, "merge", "-s", "ours", target, "-m", "Record the release merge")
    assert (repo / "desks" / "backtest.py").read_text() == before
    assert _git(repo, "diff", "--name-only", "HEAD", target).strip() == ""

    # 3. THE POINT OF STEP 5. Without the recorded merge every later Sync-Pull sees itself
    #    behind, tries to merge, and dies on the same corrupt entry -- an adoption that has to
    #    be repeated every hour is not an adoption.
    assert _git(repo, "rev-list", "--count", f"{target}..HEAD").strip() != "0"
    out = _git(repo, "merge", target)
    assert "Already up to date" in out


def test_recording_the_merge_before_the_tree_matches_would_bury_the_release(
    tmp_path: Path,
) -> None:
    """Why the verification in step 4 is not a formality.

    This is the failure the script is built to refuse: `-s ours` keeps the current tree and
    records the target as a parent, so running it on a tree that has NOT adopted the work leaves
    a repository that claims to contain the release, reports itself up to date, and is running
    the old code. Silent, permanent, and indistinguishable from success on a dashboard.
    """
    repo = _repo(tmp_path)
    (repo / "money.py").write_text("old\n")
    _git(repo, "add", "--", "money.py")
    _git(repo, "commit", "-q", "-m", "base")

    _git(repo, "checkout", "-q", "-b", "release")
    (repo / "money.py").write_text("new\n")
    _git(repo, "add", "--", "money.py")
    _git(repo, "commit", "-q", "-m", "release")
    target = _git(repo, "rev-parse", "HEAD").strip()

    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-s", "ours", target, "-m", "recorded too early")

    assert (repo / "money.py").read_text() == "old\n"          # the release did NOT land
    assert "Already up to date" in _git(repo, "merge", target)  # and git now says it is done
    assert _git(repo, "diff", "--name-only", "HEAD", target).strip() == "money.py"


@pytest.mark.skipif(os.geteuid() == 0,
                    reason="root ignores directory permission bits, so unlink still succeeds")
def test_in_place_truncate_writes_a_file_that_cannot_be_unlinked(tmp_path: Path) -> None:
    """The claim the whole script rests on, against a filesystem that refuses to unlink."""
    d = tmp_path / "locked"
    d.mkdir()
    f = d / "run_external_backtest.py"
    f.write_bytes(b"old contents\n")
    d.chmod(0o555)                       # entries may not be created or removed
    try:
        with pytest.raises(PermissionError):
            f.unlink()
        with open(f, "r+b") as fh:       # ... but the bytes are still ours to rewrite
            fh.truncate(0)
            fh.write(b"new contents\n")
        assert f.read_bytes() == b"new contents\n"
    finally:
        d.chmod(0o755)


def _executable_lines(text: str) -> str:
    """The script with its comment block and `#` lines removed.

    Necessary, not fussy: the script EXPLAINS at length why `git stash` and a bare `git add -A`
    are banned here, so a naive substring search over the whole file flags the prose that
    documents the ban. A test that cannot tell a prohibition from its violation would force the
    next author to delete the explanation to make it pass.
    """
    out, in_block = [], False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("<#"):
            in_block = True
        if in_block:
            if "#>" in stripped:
                in_block = False
            continue
        if stripped.startswith("#"):
            continue
        out.append(line.split(" # ")[0])
    return "\n".join(out)


def test_the_script_never_uses_the_operations_this_desk_has_banned() -> None:
    code = _executable_lines(SCRIPT.read_text("utf-8"))
    # `git stash` in a tree another process is writing has already lost work here (R0423), and a
    # bare `git add -A` on this box would sweep logs, caches and data/secrets into the branch.
    assert "stash" not in code
    for banned in ('"add", "-A"', '"add", "--all")', "add -A", '"add", "--all", "."'):
        assert banned not in code, f"{banned} is a bare add: it stages paths nobody enumerated"
    # Every staging call must name paths: `add --all --` followed by an explicit pathspec list.
    assert '@("add", "--all", "--") + $chunk' in code
    # And the ordering that makes step 5 safe must still be there.
    assert code.index("REFUSING to record the merge") < code.index('"merge", "-s", "ours"')
