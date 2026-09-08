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
import re
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


#: The prefixes the script keeps for the box, verbatim from the script (the test below pins
#: them to `libs.ops.release.STATE_PREFIXES` minus docs/).
STATE_PREFIXES = ("desks/mt5/data/", "desks/mt5/reports/", "desks/mt5/logs/",
                  "data/", "reports/", "logs/", "web/")


def _is_state(rel: str) -> bool:
    return any(rel.startswith(p) for p in STATE_PREFIXES)


def _adopt(repo: Path, target: str, kept: list[str] | None = None,
           untracked: list[str] | None = None) -> list[str]:
    """The script's steps 2-5, in Python, against a real repository.

    Deliberately a re-implementation rather than a call: PowerShell does not exist on the CI
    runner, and the thing worth pinning is the GIT sequence -- which calls, in which order, and
    what each one leaves behind. The in-place write is `r+b`/truncate for the same reason the
    script uses FileMode.Truncate: it rewrites the bytes of an existing entry and issues no
    unlink.

    THE KEEP RULE (2026-09-08), exactly as the script applies it: a state path THIS BOX changed
    since the merge base is the box's evidence and is neither written, deleted nor staged. It
    is appended to `kept` so the caller can assert on it.

    THE UNTRACK RULE (2026-09-08, later the same day), checked BEFORE the keep rule as the
    script does: a state path the target DELETES leaves the index only (`git rm --cached`),
    is never unlinked, and is not staged. It is appended to `untracked`.
    """
    records = _git(repo, "-c", "core.quotePath=false", "diff",
                   "--name-status", "HEAD", target).splitlines()
    base = _git(repo, "merge-base", "HEAD", target).strip()
    touched = set(_git(repo, "diff", "--name-only", base, "HEAD").split()) if base else None
    staged: list[str] = []
    for rec in [r for r in records if r.strip()]:
        cols = rec.split("\t")
        ops = ([("D", cols[1]), ("A", cols[2])] if cols[0][0] in "RC"
               else [(cols[0][0], cols[1])])
        for kind, rel in ops:
            full = repo / rel
            if kind == "D" and _is_state(rel):
                subprocess.run(["git", "-C", str(repo), "rm", "--cached", "--quiet", "--", rel],
                               check=False, capture_output=True)
                if untracked is not None:
                    untracked.append(rel)
                continue
            if _is_state(rel) and (touched is None or rel in touched):
                if kept is not None:
                    kept.append(rel)
                continue
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
    # unconditional on `staged`: the index may hold only `rm --cached` removals
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


# ------------------------------------------------------------ the box's state is the box's
def test_the_box_s_own_state_is_kept_and_only_origin_s_inputs_are_adopted(
    tmp_path: Path,
) -> None:
    """The 2026-09-07 shape. The box has not pushed for a day; origin's copy of its ledger is
    old, origin also carries a new gateway, a research budget a session wrote FOR the box, and
    new docs. The first version rewrote all four with origin's bytes -- the ledger included,
    rolling the box's forward record back to its last push."""
    repo = _repo(tmp_path)
    for rel, body in (("desks/mt5/mt5desk/gateway.py", "old gateway\n"),
                      ("desks/mt5/data/ledger.json", "day 1\n"),
                      ("desks/mt5/data/research_budget.json", "budget v1\n"),
                      ("docs/desk_lessons.jsonl", "L1\n")):
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(body)
        _git(repo, "add", "--", rel)
    _git(repo, "commit", "-q", "-m", "base")

    # origin: code, an input for the box, docs -- and a touch on the ledger too (both sides).
    _git(repo, "checkout", "-q", "-b", "release")
    (repo / "desks/mt5/mt5desk/gateway.py").write_text("new gateway\n")
    (repo / "desks/mt5/data/research_budget.json").write_text("budget v2\n")
    (repo / "docs/desk_lessons.jsonl").write_text("L1\nL2\n")
    (repo / "desks/mt5/data/ledger.json").write_text("day 1 (origin's older copy, re-stamped)\n")
    _git(repo, "add", "--", "desks", "docs")
    _git(repo, "commit", "-q", "-m", "release")
    target = _git(repo, "rev-parse", "HEAD").strip()

    # the box: a day of forward record, committed by step 1 exactly as the script does.
    _git(repo, "checkout", "-q", "main")
    (repo / "desks/mt5/data/ledger.json").write_text("day 1\nday 2\n")
    _git(repo, "add", "--", "desks/mt5/data/ledger.json")
    _git(repo, "commit", "-q", "-m", "Box state captured before release adoption")

    kept: list[str] = []
    _adopt(repo, target, kept)

    assert kept == ["desks/mt5/data/ledger.json"]
    assert (repo / "desks/mt5/data/ledger.json").read_text() == "day 1\nday 2\n"      # kept
    assert (repo / "desks/mt5/mt5desk/gateway.py").read_text() == "new gateway\n"      # code
    assert (repo / "desks/mt5/data/research_budget.json").read_text() == "budget v2\n"  # input
    assert (repo / "docs/desk_lessons.jsonl").read_text() == "L1\nL2\n"               # docs

    # The gate: nothing OUTSIDE the kept set differs from the target.
    drift = [p for p in _git(repo, "diff", "--name-only", "HEAD", target).split()
             if not (_is_state(p) and p in kept)]
    assert drift == []

    # Recording the merge keeps the box's ledger, and the next sync is a fast-forward.
    _git(repo, "merge", "-s", "ours", target, "-m", "Record the release merge")
    assert (repo / "desks/mt5/data/ledger.json").read_text() == "day 1\nday 2\n"
    assert "Already up to date" in _git(repo, "merge", target)
    assert _git(repo, "merge-base", "--is-ancestor", target, "HEAD") == ""   # exit 0: descends


def test_a_state_path_the_box_never_touched_is_adopted_like_code(tmp_path: Path) -> None:
    """A research budget a session wrote for the box to read is an input, not evidence: the
    box did not measure it, so origin's copy is the newer one."""
    repo = _repo(tmp_path)
    (repo / "desks/mt5/data").mkdir(parents=True)
    (repo / "desks/mt5/data/research_budget.json").write_text("v1\n")
    _git(repo, "add", "--", "desks/mt5/data/research_budget.json")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "checkout", "-q", "-b", "release")
    (repo / "desks/mt5/data/research_budget.json").write_text("v2\n")
    _git(repo, "add", "--", "desks/mt5/data/research_budget.json")
    _git(repo, "commit", "-q", "-m", "release")
    target = _git(repo, "rev-parse", "HEAD").strip()
    _git(repo, "checkout", "-q", "main")
    kept: list[str] = []
    _adopt(repo, target, kept)
    assert kept == []
    assert (repo / "desks/mt5/data/research_budget.json").read_text() == "v2\n"
    assert _git(repo, "diff", "--name-only", "HEAD", target).strip() == ""


def test_the_script_s_keep_rule_is_the_release_module_s_state_list_minus_docs() -> None:
    """Two copies of one list, pinned to each other: the script cannot import `libs` (it runs
    before the adopted `libs` is on disk), so it carries the prefixes as a literal."""
    import sys
    repo_root = str(BASE.parent.parent)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from libs.ops import release
    assert tuple(p for p in release.STATE_PREFIXES if p != "docs/") == STATE_PREFIXES
    code = _executable_lines(SCRIPT.read_text("utf-8"))
    m = re.search(r"\$StatePrefixes = @\(([^)]*)\)", code, re.S)
    assert m, "the script no longer declares $StatePrefixes"
    assert tuple(re.findall(r'"([^"]+)"', m.group(1))) == STATE_PREFIXES
    assert "docs/" not in m.group(1)          # origin's docs are adopted; the box never writes them


def test_the_script_keeps_before_it_deletes_and_verifies_outside_the_kept_set() -> None:
    code = _executable_lines(SCRIPT.read_text("utf-8"))
    # the keep test runs before the D branch, so a kept path is never unlinked
    assert code.index("if (Test-KeptByBox $rel)") < code.index('if ($op.Kind -eq "D")')
    # a kept path is not staged either -- it is left for the sync that owns it
    keep_branch = code[code.index("if (Test-KeptByBox $rel)"):code.index('if ($op.Kind -eq "D")')]
    assert "$staged.Add" not in keep_branch and "continue" in keep_branch
    # the verification gate excludes exactly the kept set, nothing wider
    assert "Where-Object { -not (Test-KeptByBox $_) })" in code
    # box-touched is measured from the merge base AFTER the box's own state is committed
    assert (code.index("Box state captured before release adoption")
            < code.index('"merge-base", "HEAD", $target'))
    # and no merge base means every state path is the box's -- never "adopt everything"
    assert "if (-not $mergeBase) { return $true }" in code


# --------------------------------------- a state path origin dropped is untracked, never unlinked
def test_a_state_path_origin_stopped_tracking_is_untracked_not_unlinked(tmp_path: Path) -> None:
    """The a4bd8663 shape, MEASURED 2026-09-08 from the box's own error. Origin untracked
    desks/mt5/logs/ (console logs that running hunts hold open) and the box's HEAD still tracks
    them; the box reported `unable to unlink old 'desks/mt5/logs/signal_gate_console.txt'`,
    which can only come from a merge trying to delete it, so its base predates a4bd8663.

    Two logs arrive as D ops: one the box appended to since the base (the old branch KEPT it
    tracked and the next push re-tracked it upstream), one it did not (the old branch called
    File.Delete on a held-open handle and refused the whole adoption). Both must end untracked,
    on disk with the box's bytes, and outside `git diff HEAD target`.
    """
    repo = _repo(tmp_path)
    for rel, body in (("desks/mt5/mt5desk/gateway.py", "old gateway\n"),
                      ("desks/mt5/logs/signal_gate_console.txt", "tick 1\n"),
                      ("desks/mt5/logs/hunt16_console.txt", "hunt 1\n"),
                      ("desks/mt5/side_channels/dead.py", "code origin removed\n")):
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(body)
        _git(repo, "add", "--", rel)
    _git(repo, "commit", "-q", "-m", "base")

    # origin: new gateway, the logs untracked and ignored, one CODE file really deleted
    _git(repo, "checkout", "-q", "-b", "release")
    (repo / "desks/mt5/mt5desk/gateway.py").write_text("new gateway\n")
    _git(repo, "rm", "-q", "--cached", "desks/mt5/logs/signal_gate_console.txt",
         "desks/mt5/logs/hunt16_console.txt")
    _git(repo, "rm", "-q", "desks/mt5/side_channels/dead.py")
    (repo / ".gitignore").write_text("desks/mt5/logs/\n")
    _git(repo, "add", "--", ".gitignore", "desks/mt5/mt5desk/gateway.py")
    _git(repo, "commit", "-q", "-m", "release: untrack the console logs")
    target = _git(repo, "rev-parse", "HEAD").strip()

    # the box: a hunt appended to one log since the base (step 1 commits it as itself)
    _git(repo, "checkout", "-q", "main")
    (repo / "desks/mt5/logs/signal_gate_console.txt").write_text("tick 1\ntick 2\n")
    (repo / "desks/mt5/logs/hunt16_console.txt").write_text("hunt 1\n")
    _git(repo, "add", "--", "desks/mt5/logs/signal_gate_console.txt")
    _git(repo, "commit", "-q", "-m", "Box state captured before release adoption")

    kept: list[str] = []
    untracked: list[str] = []
    staged = _adopt(repo, target, kept, untracked)

    assert sorted(untracked) == ["desks/mt5/logs/hunt16_console.txt",
                                 "desks/mt5/logs/signal_gate_console.txt"]
    assert kept == []                                       # the untrack rule ran first
    assert "desks/mt5/logs/signal_gate_console.txt" not in staged
    # on disk, the box's bytes; in git, nowhere
    assert (repo / "desks/mt5/logs/signal_gate_console.txt").read_text() == "tick 1\ntick 2\n"
    assert (repo / "desks/mt5/logs/hunt16_console.txt").read_text() == "hunt 1\n"
    assert "desks/mt5/logs/" not in _git(repo, "ls-files")
    # the code deletion still unlinks, and the code arrives
    assert not (repo / "desks/mt5/side_channels/dead.py").exists()
    assert (repo / "desks/mt5/mt5desk/gateway.py").read_text() == "new gateway\n"
    # THE GATE: nothing differs from the target, so the merge may be recorded ...
    assert _git(repo, "diff", "--name-only", "HEAD", target).strip() == ""
    _git(repo, "merge", "-s", "ours", target, "-m", "Record the release merge")
    assert "Already up to date" in _git(repo, "merge", target)
    # ... and the next push carries NO re-tracked log: the ignored path stays untracked
    assert _git(repo, "status", "--porcelain", "--", "desks/mt5/logs").strip() == ""


def test_an_adoption_whose_only_change_is_untracking_is_still_committed(tmp_path: Path) -> None:
    """Nested under `if ($staged.Count -gt 0)`, the commit never ran when every op was an
    index-side removal, so HEAD still listed the path and the verify step refused."""
    repo = _repo(tmp_path)
    (repo / "desks/mt5/logs").mkdir(parents=True)
    (repo / "desks/mt5/logs/supervisor_state.json").write_text("{}\n")
    _git(repo, "add", "--", "desks/mt5/logs/supervisor_state.json")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "checkout", "-q", "-b", "release")
    _git(repo, "rm", "-q", "--cached", "desks/mt5/logs/supervisor_state.json")
    _git(repo, "commit", "-q", "-m", "release: untrack")
    target = _git(repo, "rev-parse", "HEAD").strip()
    (repo / "desks/mt5/logs/supervisor_state.json").unlink()   # main's checkout restores it
    _git(repo, "checkout", "-q", "main")
    untracked: list[str] = []
    staged = _adopt(repo, target, untracked=untracked)
    assert staged == [] and untracked == ["desks/mt5/logs/supervisor_state.json"]
    assert (repo / "desks/mt5/logs/supervisor_state.json").exists()
    assert _git(repo, "diff", "--name-only", "HEAD", target).strip() == ""


def test_the_script_untracks_state_deletions_before_it_keeps_or_deletes() -> None:
    code = _executable_lines(SCRIPT.read_text("utf-8"))
    untrack = code.index('if ($op.Kind -eq "D" -and (Test-StatePath $rel))')
    assert untrack < code.index("if (Test-KeptByBox $rel)")
    assert untrack < code.index("[System.IO.File]::Delete($full)")
    branch = code[untrack:code.index("if (Test-KeptByBox $rel)")]
    assert '"rm", "--cached", "--quiet", "--", $rel' in branch
    assert "$staged.Add" not in branch and "Delete" not in branch and "continue" in branch
    # the commit is not nested under the staged-count guard
    guard = code.index("if ($staged.Count -gt 0)")
    pending = code.index("$pending = ")
    assert guard < pending
    assert re.search(r"^\}\s*$", code[guard:pending], re.M), "the add block closes before $pending"
    assert re.search(r"^\$pending = ", code, re.M), "$pending is at top level"
    assert code.index('"commit", "-m"', pending) > pending


def test_a_locked_file_is_retried_before_it_is_reported() -> None:
    code = _executable_lines(SCRIPT.read_text("utf-8"))
    assert "catch [System.IO.IOException]" in code
    assert "if ($tries -ge 3) { throw }" in code
    assert "Start-Sleep -Seconds 2" in code
