""".github/scripts/resolve_pr_conflicts.py: generated and append-only conflicts resolve
mechanically, real ones are never touched. Every git test runs in a throwaway repository."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "resolve_t", ROOT / ".github/scripts/resolve_pr_conflicts.py"
)
assert _spec and _spec.loader
rc: Any = importlib.util.module_from_spec(_spec)
sys.modules["resolve_t"] = rc
_spec.loader.exec_module(rc)


# --------------------------------------------------------------------------- pure merges


def test_lines_keep_both_sides_additions_and_honour_a_pr_removal() -> None:
    base = "a\nb\nc\n"
    ours = "a\nc\nd\n"  # the PR removed b, added d
    theirs = "a\nb\nc\ne\n"  # LIVE added e
    assert rc.merge_lines(base, ours, theirs) == "a\nc\ne\nd\n"


def test_a_line_both_sides_added_appears_once() -> None:
    assert rc.merge_lines("a\n", "a\nx\n", "a\nx\n") == "a\nx\n"


def test_json_merges_by_key_and_refuses_a_real_clash() -> None:
    base = {"legs": {"a": 1}, "max": 3}
    ours = {"legs": {"a": 1, "mine": 2}, "max": 3}
    theirs = {"legs": {"a": 1, "live": 4}, "max": 2}
    assert rc.merge_json(base, ours, theirs) == {"legs": {"a": 1, "live": 4, "mine": 2}, "max": 2}
    with pytest.raises(rc.Conflict):
        rc.merge_json({"legs": {"a": 1}}, {"legs": {"a": 2}}, {"legs": {"a": 3}})


def test_a_key_one_side_deleted_stays_deleted() -> None:
    assert rc.merge_json({"a": 1, "b": 2}, {"a": 1}, {"a": 1, "b": 2}) == {"a": 1}


def test_only_the_pr_s_own_new_organs_are_wanted_and_a_row_live_dropped_stays_dropped() -> None:
    """2026-11-18 (#1142, #1147): the FTMO-Allocator row LIVE dropped under audit HOLD came back
    on every PR whose monolith still had it."""
    base = {"leg:a", "task:MT5-FTMO-Allocator"}
    ours = {"leg:a", "task:MT5-FTMO-Allocator", "leg:new"}
    live = {"leg:a", "leg:live_only"}
    assert rc.wanted_organs(base, ours, live) == {"leg:new"}
    assert rc.wanted_organs(base, ours, live | {"leg:new"}) == set()  # LIVE has it already


def test_organs_in_reads_a_monolith_and_refuses_an_unreadable_one() -> None:
    assert rc.organs_in(json.dumps({"organs": [{"organ": "leg:a"}, {"x": 1}]})) == {"leg:a"}
    assert rc.organs_in("") == set()
    with pytest.raises(rc.Conflict):
        rc.organs_in("{not json")


def test_the_sidecar_name_matches_runtime_attestation() -> None:
    src = (ROOT / "desks/mt5/research/runtime_attestation.py").read_text("utf-8")
    assert 'SIDECAR_DIR = "runtime_state.d"' in src and rc.SIDECARS.endswith("runtime_state.d")
    for organ in ("leg:limit_optimality", "task:MT5-FTMO-Allocator", "a/b c:d"):
        slug = re.sub(r"[^A-Za-z0-9._-]", "~", organ)[:80]
        assert rc.sidecar_name(organ).startswith(slug + "-")


# ---------------------------------------------------------------------- the git merge


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True,
                          check=True).stdout.strip()  # fmt: skip


def _commit(repo: Path, files: dict[str, str], msg: str) -> str:
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
        _git(repo, "add", "--", rel)
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", msg)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for k in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        monkeypatch.setenv(k, "t")
    for k in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(k, "t@t")
    r = tmp_path / "r"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _commit(r, {
        rc.LINE_FILES[0]: "j1\n",
        rc.STATE_JSON: json.dumps({"organs": [{"organ": "leg:a"}]}),
        rc.STATE_MD: "# state\n",
        "code.py": "x = 1\n",
    }, "base")  # fmt: skip
    return r


def _sides(repo: Path, live: dict[str, str], pr: dict[str, str]) -> tuple[str, str]:
    base = _git(repo, "rev-parse", "HEAD")
    live_sha = _commit(repo, live, "live")
    _git(repo, "checkout", "-q", base)
    pr_sha = _commit(repo, pr, "pr")
    return pr_sha, live_sha


def _stamped(cwd: Path, tree: str, organs: set[str]) -> dict[str, str]:
    """A stand-in for runtime_attestation --only-missing: a stamped row per wanted organ."""
    return {f"{rc.SIDECARS}/{rc.sidecar_name(o)}":
            json.dumps({"organ": o, "only_missing": {"host": "t"}}) for o in organs}  # fmt: skip


def test_generated_and_append_only_conflicts_resolve_into_one_merge_commit(repo: Path) -> None:
    pr, live = _sides(
        repo,
        {rc.LINE_FILES[0]: "j1\nlive\n", rc.STATE_MD: "# live\n",
         rc.STATE_JSON: json.dumps({"organs": [{"organ": "leg:a"}, {"organ": "leg:l"}]})},
        {rc.LINE_FILES[0]: "j1\nmine\n", rc.STATE_MD: "# mine\n",
         rc.STATE_JSON: json.dumps({"organs": [{"organ": "leg:a"}, {"organ": "leg:p"}]})},
    )  # fmt: skip
    asked: list[set[str]] = []

    def mint(cwd: Path, tree: str, organs: set[str]) -> dict[str, str]:
        asked.append(set(organs))
        return _stamped(cwd, tree, organs)

    sha, files = rc.merge_commit(repo, pr, live, "b", mint=mint)
    assert _git(repo, "rev-list", "--parents", "-n1", sha).split()[1:] == [pr, live]
    assert _git(repo, "show", f"{sha}:{rc.LINE_FILES[0]}") == "j1\nlive\nmine"
    assert _git(repo, "show", f"{sha}:{rc.STATE_MD}") == "# live"  # LIVE's, byte for byte
    live_json = _git(repo, "show", f"{live}:{rc.STATE_JSON}")
    assert _git(repo, "show", f"{sha}:{rc.STATE_JSON}") == live_json
    side = f"{rc.SIDECARS}/{rc.sidecar_name('leg:p')}"
    assert asked == [{"leg:p"}]
    row = json.loads(_git(repo, "show", f"{sha}:{side}"))
    assert side in files and row["organ"] == "leg:p" and row["only_missing"]  # minted, stamped
    assert _git(repo, "status", "--porcelain") == ""  # nothing on disk was touched


def test_a_row_live_dropped_is_never_minted_back(repo: Path) -> None:
    """The merge base named task:MT5-FTMO-Allocator, LIVE dropped it, the PR still has it."""
    held = {"organs": [{"organ": "leg:a"}, {"organ": "task:MT5-FTMO-Allocator"}]}
    _commit(repo, {rc.STATE_JSON: json.dumps(held)}, "base has the row")
    pr, live = _sides(
        repo,
        {rc.STATE_JSON: json.dumps({"organs": [{"organ": "leg:a"}, {"organ": "leg:l"}]})},
        {rc.STATE_JSON: json.dumps({"organs": [{"organ": "leg:a"}, {"organ": "leg:p"},
                                               {"organ": "task:MT5-FTMO-Allocator"}]})},
    )  # fmt: skip
    asked: list[set[str]] = []

    def mint(cwd: Path, tree: str, organs: set[str]) -> dict[str, str]:
        asked.append(set(organs))
        return _stamped(cwd, tree, organs)

    sha, files = rc.merge_commit(repo, pr, live, "b", mint=mint)
    assert asked == [{"leg:p"}]
    ftmo = f"{rc.SIDECARS}/{rc.sidecar_name('task:MT5-FTMO-Allocator')}"
    assert ftmo not in files
    assert ftmo not in _git(repo, "ls-tree", "-r", "--name-only", sha)


def test_a_row_the_minter_cannot_write_leaves_the_pr_alone(repo: Path) -> None:
    pr, live = _sides(
        repo,
        {rc.STATE_JSON: json.dumps({"organs": [{"organ": "leg:a"}, {"organ": "leg:l"}]})},
        {rc.STATE_JSON: json.dumps({"organs": [{"organ": "leg:a"}, {"organ": "leg:p"}]})},
    )  # fmt: skip

    def mint(cwd: Path, tree: str, organs: set[str]) -> dict[str, str]:
        raise rc.Conflict("--only-missing minted no row for leg:p")

    with pytest.raises(rc.Conflict, match="leg:p"):
        rc.merge_commit(repo, pr, live, "b", mint=mint)


def test_no_new_organ_mints_nothing(repo: Path) -> None:
    pr, live = _sides(
        repo,
        {rc.STATE_JSON: json.dumps({"organs": [{"organ": "leg:a"}, {"organ": "leg:l"}]})},
        {rc.STATE_JSON: json.dumps({"organs": [{"organ": "leg:a"}], "x": 1})},
    )  # fmt: skip

    def mint(cwd: Path, tree: str, organs: set[str]) -> dict[str, str]:
        raise AssertionError("nothing to mint")

    _sha, files = rc.merge_commit(repo, pr, live, "b", mint=mint)
    assert files == [rc.STATE_JSON]


def test_a_real_conflict_is_left_alone(repo: Path) -> None:
    pr, live = _sides(repo, {"code.py": "x = 2\n"}, {"code.py": "x = 3\n"})
    with pytest.raises(rc.Conflict, match=r"code\.py"):
        rc.merge_commit(repo, pr, live, "b")


def test_a_clean_merge_is_just_a_merge(repo: Path) -> None:
    pr, live = _sides(repo, {"live.txt": "l\n"}, {"pr.txt": "p\n"})
    sha, files = rc.merge_commit(repo, pr, live, "b")
    assert files == [] and _git(repo, "show", f"{sha}:live.txt") == "l"


def test_gitattributes_unions_the_append_only_files() -> None:
    text = (ROOT / ".gitattributes").read_text("utf-8")
    for rel in rc.LINE_FILES:
        assert f"{rel} merge=union" in text


def test_a_pr_that_merges_cleanly_is_never_pushed(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only a conflicting PR gets a merge-in: each push queues a full set of CI runs."""
    pr, live = _sides(repo, {"live.txt": "l\n"}, {"pr.txt": "p\n"})
    p = {"state": "open", "base": {"ref": rc.LIVE}, "head": {"repo": {"full_name": rc.REPO},
         "ref": "b", "sha": pr}, "updated_at": "2000-01-01T00:00:00Z"}  # fmt: skip
    monkeypatch.setattr(rc, "gh", lambda *a: p)
    calls: list[tuple[str, ...]] = []
    real = rc.git

    def git(cwd: Path, *args: str, **kw: Any) -> str:
        calls.append(args)
        if args[0] == "fetch":
            return ""
        if args[:2] == ("rev-parse", "origin/live"):
            return live
        return str(real(cwd, *args, **kw))

    monkeypatch.setattr(rc, "git", git)
    out = rc.one(repo, 5, push=True, quiet_min=0)
    assert "merges cleanly" in out and not any(c[0] == "push" for c in calls)


def test_the_minter_runs_the_pr_s_code_without_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Audit soft fix on #1258: runtime_attestation --only-missing runs PR-tree code."""
    for k in ("GH_TOKEN", "GITHUB_TOKEN", "OPENROUTER_API_KEY", "HCNSEC_SECRET", "GIT_DIR"):
        monkeypatch.setenv(k, "x")
    monkeypatch.setenv("PATH_KEEP_ME", "y")
    seen: dict[str, Any] = {}

    def fake_run(cmd: list[str], **kw: Any) -> Any:
        seen.update(kw["env"])
        return subprocess.CompletedProcess(cmd, 1, "", "stop here")

    monkeypatch.setattr(rc, "git", lambda cwd, *a, **k: str(tmp_path) if "rev-parse" in a else "c")
    (tmp_path / rc.MINT_WT / ".git").mkdir(parents=True)
    monkeypatch.setattr(rc.subprocess, "run", fake_run)
    with pytest.raises(rc.Conflict):
        rc.mint_only_missing(tmp_path, "t", {"leg:p"})
    assert seen["PATH_KEEP_ME"] == "y"
    for k in ("GH_TOKEN", "GITHUB_TOKEN", "OPENROUTER_API_KEY", "HCNSEC_SECRET", "GIT_DIR"):
        assert k not in seen
