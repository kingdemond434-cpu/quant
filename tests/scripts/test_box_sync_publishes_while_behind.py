"""The box must publish its state even when origin is ahead of it -- which is nearly always.

MEASURED 2026-09-30: no box-authored state commit had reached the live branch since 2026-09-25,
and the shadow lane files on it still carried `updated_at: 2026-09-16`. Since ff281c49b the
publisher handed inbound code to MT5-AdoptRelease and EXITED whenever origin was ahead -- before
staging anything. The branch takes dozens of commits a day and the adopter runs hourly, so the
box deferred at almost every slot, and every reader off the box measured a frozen copy and
called the forward engine silent.

The fix (`Publish-StateOnto`) keeps the code/state split: it never merges and never touches the
working tree, HEAD or the real index. It lays the box's committed state blobs over FETCH_HEAD's
tree in a PRIVATE index and pushes a fast-forward whose only parent is origin's tip.

There is no pwsh on the research host, so this pins the script's structure and proves the exact
git plumbing sequence the function runs, on a throwaway repository and a bare remote.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from libs.ops import release

ROOT = Path(__file__).resolve().parents[2]
SYNC = ROOT / "desks" / "mt5" / "scripts" / "sync_shadow_to_git.ps1"

#: The research measurements the audit found never committed from the box.
REQUIRED_REPORTS = (
    "desks/mt5/reports/RESEARCH_BUDGET.json",
    "desks/mt5/reports/JUDGING_RATE.json",
    "desks/mt5/reports/JUDGING_THROUGHPUT.json",
    "desks/mt5/reports/GAUNTLET_BACKPRESSURE.json",
    "desks/mt5/reports/EFFECTIVE_BREADTH.json",
    "desks/mt5/reports/TIER1_SCORECARD.json",
    "desks/mt5/reports/ALT_DATA_YIELD.json",
    "desks/mt5/reports/FORWARD_ENROLMENT.json",
)


def _src() -> str:
    return SYNC.read_text("utf-8", errors="ignore")


def _report_paths() -> list[str]:
    src = _src()
    start = src.index("$reportPaths = @(")
    block = src[start:src.index("\n)", start)]
    return [p for p in re.findall(r'"([^"]+)"', block) if "/" in p]


def test_the_report_list_carries_every_audited_artifact() -> None:
    listed = set(_report_paths())
    missing = [p for p in REQUIRED_REPORTS if p not in listed]
    assert not missing, f"$reportPaths does not publish {missing}"


def test_every_report_is_state_to_the_seal() -> None:
    """A published path the seal reads as code would refuse new risk on the next sync."""
    code = [p for p in _report_paths() if not release.is_state_path(p)]
    assert not code, f"{code} would read as unreleased CODE to release.accepts()"


def test_every_report_survives_gitignore() -> None:
    """`git add` on an ignored path exits 0 and stages nothing. Asked in a clean sandbox."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        (root / ".gitignore").write_text((ROOT / ".gitignore").read_text("utf-8"), "utf-8")
        ignored = []
        for rel in _report_paths():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("{}\n", "utf-8")
            if subprocess.run(["git", "check-ignore", "-q", "--", rel], cwd=root).returncode == 0:
                ignored.append(rel)
    assert not ignored, f"{ignored} are listed in $reportPaths but .gitignore excludes them"


def test_being_behind_no_longer_exits_before_staging() -> None:
    src = _src()
    pull = src.index("Sync-Pull -RepoRoot $RepoRoot -Branch $branch")
    add = src.index("$addRc = Git-In-Repo")
    between = src[pull:add]
    assert "exit 0" not in between.replace('"SKIP: none of the tracked', ""
                                           ).split("if ($existing.Count -eq 0)")[0], (
        "the publisher exits between the pull and staging again -- a box behind origin "
        "publishes nothing, which is what froze the branch's copy for a week")


def test_every_inbound_path_publishes_onto_origin() -> None:
    src = _src()
    assert src.index("function Publish-StateOnto") < src.index("Publish-StateOnto -RepoRoot")
    assert src.count("Publish-StateOnto -RepoRoot") >= 3, (
        "the no-change, fresh-commit and push-race paths must each publish when behind")
    loop = src[src.index("for ($attempt = 1;"):]
    assert "Publish-StateOnto -RepoRoot" in loop


def test_the_publisher_never_merges_or_touches_the_real_index() -> None:
    src = _src()
    body = src[src.index("function Publish-StateOnto"):]
    body = body[:body.index("\n}", 0) + 2]
    code = "\n".join(ln for ln in body.splitlines() if not ln.lstrip().startswith("#"))
    for banned in ('"merge"', "checkout", '"add"', "stash", "reset"):
        assert banned not in code, f"Publish-StateOnto runs {banned}"
    assert "$env:GIT_INDEX_FILE = $idx" in code
    assert '"commit-tree", $tree, "-p", $base' in code


def _git(cwd: Path, *args: str, env: dict | None = None) -> str:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                          check=True, env=env).stdout.strip()


@pytest.mark.skipif(shutil.which("git") is None, reason="git required")
def test_the_plumbing_publishes_state_onto_a_moved_origin(tmp_path: Path) -> None:
    """The function's exact git sequence, end to end: box behind, origin moved, state lands."""
    bare = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "live", str(bare))
    box = tmp_path / "box"
    _git(tmp_path, "clone", "-q", str(bare), str(box))
    for r in (box,):
        _git(r, "config", "user.email", "b@example.com")
        _git(r, "config", "user.name", "box")
        _git(r, "config", "commit.gpgsign", "false")
    _git(box, "checkout", "-q", "-b", "live")
    (box / "code.py").write_text("v1\n", "utf-8")
    state = box / "desks" / "mt5" / "reports" / "JUDGING_RATE.json"
    state.parent.mkdir(parents=True)
    state.write_text('{"rate": 1}\n', "utf-8")
    _git(box, "add", "code.py", "desks/mt5/reports/JUDGING_RATE.json")
    _git(box, "commit", "-q", "-m", "base")
    _git(box, "push", "-q", "origin", "live")

    other = tmp_path / "other"
    _git(tmp_path, "clone", "-q", "-b", "live", str(bare), str(other))
    _git(other, "config", "user.email", "o@example.com")
    _git(other, "config", "user.name", "other")
    _git(other, "config", "commit.gpgsign", "false")
    (other / "code.py").write_text("v2\n", "utf-8")
    _git(other, "commit", "-qam", "origin moves on")
    _git(other, "push", "-q", "origin", "live")

    # The box writes and commits its state LOCALLY, and is now behind origin.
    state.write_text('{"rate": 219}\n', "utf-8")
    _git(box, "add", "desks/mt5/reports/JUDGING_RATE.json")
    _git(box, "commit", "-q", "-m", "box state")
    head_before = _git(box, "rev-parse", "HEAD")
    _git(box, "fetch", "-q", "origin", "live")

    # --- Publish-StateOnto, step for step -------------------------------------------------
    entries = _git(box, "ls-tree", "HEAD", "--", "desks/mt5/reports/JUDGING_RATE.json")
    base = _git(box, "rev-parse", "FETCH_HEAD")
    env = {**os.environ, "GIT_INDEX_FILE": str(tmp_path / "private-index")}
    _git(box, "read-tree", base, env=env)
    meta, rel = entries.split("\t", 1)
    mode, _kind, sha = meta.split()
    _git(box, "update-index", "--add", "--cacheinfo", f"{mode},{sha},{rel}", env=env)
    tree = _git(box, "write-tree", env=env)
    commit = _git(box, "commit-tree", tree, "-p", base, "-m", "mt5 box state", env=env)
    _git(box, "push", "-q", "origin", f"{commit}:refs/heads/live")
    # ---------------------------------------------------------------------------------------

    assert _git(box, "rev-parse", "HEAD") == head_before, "the publisher moved the box's HEAD"
    assert (box / "code.py").read_text("utf-8") == "v1\n", "the publisher touched code on disk"
    assert _git(box, "status", "--porcelain") == "", "the publisher dirtied the real index"
    _git(other, "pull", "-q", "--ff-only", "origin", "live")
    assert (other / "code.py").read_text("utf-8") == "v2\n", "origin's code was reverted"
    published = other / "desks" / "mt5" / "reports" / "JUDGING_RATE.json"
    assert published.read_text("utf-8") == '{"rate": 219}\n', "the box's state did not land"
