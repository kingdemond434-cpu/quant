"""The box must publish its state even when origin is ahead of it -- which is nearly always.

MEASURED 2026-09-30: no box-authored state commit had reached the live branch since 2026-09-25,
and the shadow lane files on it still carried `updated_at: 2026-09-16`. Since ff281c49b the
publisher handed inbound code to MT5-AdoptRelease and EXITED whenever origin was ahead -- before
staging anything. The branch takes dozens of commits a day and the adopter runs hourly, so the
box deferred at almost every slot, and every reader off the box measured a frozen copy and
called the forward engine silent.

The fix (`Publish-StateOnto`) keeps the code/state split: it never merges and never touches the
working tree, HEAD or the real index. It hashes allowlisted box state, lays those blobs over
FETCH_HEAD's tree in a PRIVATE index and pushes a fast-forward whose only parent is origin's tip.

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


def test_being_behind_no_longer_exits_before_publication() -> None:
    src = _src()
    pull = src.index("Sync-Pull -RepoRoot $RepoRoot -Branch $branch")
    publish = src.index("$ok = Publish-StateOnto -RepoRoot")
    between = src[pull:publish]
    assert "exit 0" not in between.replace('"SKIP: none of the tracked', ""
                                           ).split("if ($existing.Count -eq 0)")[0], (
        "the publisher exits between the pull and publication again -- a box behind origin "
        "publishes nothing, which is what froze the branch's copy for a week")


def test_every_inbound_path_publishes_onto_origin() -> None:
    src = _src()
    assert src.index("function Publish-StateOnto") < src.index("Publish-StateOnto -RepoRoot")
    tail = src[src.index("# ONE DELIVERY PATH"):]
    assert "$ok = Publish-StateOnto -RepoRoot $RepoRoot -Branch $branch -Paths $existing" in tail


def _code(src: str) -> str:
    return "\n".join(ln.split("#", 1)[0] for ln in src.splitlines())


def test_the_publisher_never_pushes_the_box_branch() -> None:
    """MEASURED: the box's unpushed backlog (506 commits of parquet, 2026-09-24) made every
    `git push origin <branch>` die on HTTP 408, and no automated state commit reached origin
    after 2026-09-12. The only push left is Publish-StateOnto's one-commit fast-forward."""
    code = _code(_src())
    pushes = re.findall(r'@\("push"[^)]*\)', code)
    assert len(pushes) == 1, pushes
    assert '"push", "--no-verify", $remote' in pushes[0]
    assert '"{0}:refs/heads/{1}"' in pushes[0]
    assert '"push", "origin", $branch' not in code
    assert '"push", "origin", "HEAD"' not in code


def test_a_refused_push_is_quoted_in_the_log() -> None:
    src = _src()
    body = src[src.index("function Push-Logged"):]
    body = body[:body.index("\n}") + 2]
    assert "2>&1" in body and "push said:" in body
    assert 'Push-Logged @("push", "--no-verify", $remote' in src


def test_state_only_push_is_independently_fenced_before_code_hook_exemption() -> None:
    body = _src().split("function Publish-StateOnto", 1)[1].split("# Desk-relative paths", 1)[0]
    diff = body.index('"diff-tree", "--name-only"')
    push = body.index('Push-Logged @("push", "--no-verify"')
    assert diff < push
    assert '$outside = @($changed | Where-Object { $_ -notin $Paths })' in body
    assert '$script:GitLinesRc -ne 0 -or $changed.Count -eq 0 -or $outside.Count -gt 0' in body


def test_a_stale_fetch_head_is_never_trusted() -> None:
    src = _src()
    assert "$script:FetchHeadFresh = $true" in src[src.index("function Sync-Pull"):]
    body = src[src.index("function Publish-StateOnto"):]
    assert "-not $script:FetchHeadFresh" in body[:body.index("rev-parse\", \"FETCH_HEAD")]

def test_the_publisher_never_merges_or_touches_the_real_index() -> None:
    src = _src()
    body = src[src.index("function Publish-StateOnto"):]
    body = body[:body.index("\n}", 0) + 2]
    code = "\n".join(ln for ln in body.splitlines() if not ln.lstrip().startswith("#"))
    for banned in ('"merge"', "checkout", '"add"', "stash", "reset"):
        assert banned not in code, f"Publish-StateOnto runs {banned}"
    assert "$env:GIT_INDEX_FILE = $idx" in code
    assert '"commit-tree", $tree, "-p", $base' in code


def test_shared_staged_research_cannot_enter_the_state_commit() -> None:
    """The scheduled publisher must keep other controllers' staged paths untouched."""
    src = _src()
    runtime = src[src.index("Sync-Pull -RepoRoot $RepoRoot -Branch $branch"):]
    code = _code(runtime)
    assert '$addRc = Git-In-Repo' not in code
    assert 'Git-In-Repo @("commit"' not in code
    publisher = _code(
        src[src.index("function Publish-StateOnto"):src.index("# Desk-relative paths")]
    )
    assert 'hash-object -w --stdin-paths' in publisher
    assert 'Git-IndexInfo -Entries $entries' in publisher
    assert 'function Git-IndexInfo' in src
    assert '"check-ignore", "--"' in publisher


def _git(cwd: Path, *args: str, env: dict | None = None) -> str:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                          check=True, env=env).stdout.strip()


@pytest.mark.skipif(os.name != "nt" or shutil.which("powershell") is None,
                    reason="Windows PowerShell required")
def test_batch_index_writer_uses_lf_and_private_index(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "b@example.com")
    _git(repo, "config", "user.name", "box")
    (repo / "state.json").write_text("old\n", "utf-8")
    _git(repo, "add", "state.json")
    _git(repo, "commit", "-qm", "base")
    (repo / "state.json").write_text("new\n", "utf-8")
    sha = _git(repo, "hash-object", "-w", "state.json")
    private = tmp_path / "private-index"
    env = {**os.environ, "GIT_INDEX_FILE": str(private)}
    _git(repo, "read-tree", "HEAD", env=env)
    src = _src()
    helper = src[src.index("function Git-IndexInfo"):src.index("# A PUSH")]
    command = (f"$RepoRoot = '{repo}'; function Write-SyncLog($msg) {{ throw $msg }}; "
               + helper + "\n"
               + f'$rc = Git-IndexInfo -Entries @("100644 blob {sha}`tstate.json"); '
               + "if ($rc -ne 0) { exit 1 }")
    result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                            cwd=repo, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert _git(repo, "ls-files", "-s", "--", "state.json", env=env).split()[1] == sha
    assert _git(repo, "ls-files", "-s", "--", "state.json").split()[1] != sha


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

    # The box writes state and has unrelated staged work; neither may be committed locally.
    state.write_text('{"rate": 219}\n', "utf-8")
    (box / "research.yaml").write_text("work in progress\n", "utf-8")
    _git(box, "add", "research.yaml")
    head_before = _git(box, "rev-parse", "HEAD")
    _git(box, "fetch", "-q", "origin", "live")

    # --- Publish-StateOnto, step for step -------------------------------------------------
    rel = "desks/mt5/reports/JUDGING_RATE.json"
    sha = subprocess.run(
        ["git", "hash-object", "-w", "--stdin-paths"],
        cwd=box, input=rel + "\n", capture_output=True, text=True, check=True,
    ).stdout.strip()
    base = _git(box, "rev-parse", "FETCH_HEAD")
    env = {**os.environ, "GIT_INDEX_FILE": str(tmp_path / "private-index")}
    _git(box, "read-tree", base, env=env)
    subprocess.run(
        ["git", "update-index", "--index-info"], cwd=box,
        input=f"100644 blob {sha}\t{rel}\n".encode("ascii"),
        capture_output=True, check=True, env=env,
    )
    tree = _git(box, "write-tree", env=env)
    base_tree = _git(box, "rev-parse", f"{base}^{{tree}}")
    changed = _git(box, "diff-tree", "--name-only", "-r", base_tree, tree).splitlines()
    assert changed == [rel]
    # A private index with an extra code blob must fail the publisher's exact-path fence.
    code_sha = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=box,
                              input=b"unexpected code\n", capture_output=True,
                              check=True).stdout.decode().strip()
    subprocess.run(["git", "update-index", "--index-info"], cwd=box,
                   input=f"100644 blob {code_sha}\tcode.py\n".encode("ascii"),
                   capture_output=True, check=True, env=env)
    bad_tree = _git(box, "write-tree", env=env)
    bad_paths = _git(box, "diff-tree", "--name-only", "-r", base_tree, bad_tree).splitlines()
    assert "code.py" in bad_paths and set(bad_paths) - {rel} == {"code.py"}
    commit = _git(box, "commit-tree", tree, "-p", base, "-m", "mt5 box state", env=env)
    _git(box, "push", "-q", "origin", f"{commit}:refs/heads/live")
    # ---------------------------------------------------------------------------------------

    assert _git(box, "rev-parse", "HEAD") == head_before, "the publisher moved the box's HEAD"
    assert (box / "code.py").read_text("utf-8") == "v1\n", "the publisher touched code on disk"
    assert _git(box, "diff", "--cached", "--name-only") == "research.yaml", (
        "the publisher changed unrelated staged research work")
    assert state.read_text("utf-8") == '{"rate": 219}\n'
    _git(other, "pull", "-q", "--ff-only", "origin", "live")
    assert (other / "code.py").read_text("utf-8") == "v2\n", "origin's code was reverted"
    published = other / "desks" / "mt5" / "reports" / "JUDGING_RATE.json"
    assert published.read_text("utf-8") == '{"rate": 219}\n', "the box's state did not land"
