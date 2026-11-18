""".github/scripts/land.py: a change that touches no live money lands on LIVE as a fast-forward,
judged by LIVE's own classifier and switch; anything else is refused and LIVE is untouched.
Every git test runs against a throwaway origin."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, rel: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


land: Any = _load("land_t", ".github/scripts/land.py")
gate: Any = _load("land_gate_t", ".github/scripts/audit_gate.py")

FAST = """
def classify(paths, head=None):
    bad = [p for p in paths if p.startswith("libs/")]
    return (False, bad[0] + " is on the money path") if bad else (True, "off the money path")
"""
GATE = """
def activated(comments, phrase="ACTIVATE RELEASE CONTROLLER"):
    last = [c["body"] for c in comments][-1:] or ["none"]
    return last[0] == phrase, "switch: " + last[0]


def verdicts(comments):
    out = []
    for c in comments:
        verdict, sha = c["body"].split()[1:3]
        out.append({"verdict": verdict, "sha": sha})
    return out
"""
ON = [{"body": "ACTIVATE RELEASE CONTROLLER"}]
OFF = [{"body": "DEACTIVATE RELEASE CONTROLLER"}]


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True,
                          check=True).stdout.strip()  # fmt: skip


def _commit(repo: Path, files: dict[str, str], msg: str) -> str:
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
        _git(repo, "add", "--", rel)
    _git(repo, "commit", "-q", "-m", msg)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for k in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        monkeypatch.setenv(k, "t")
    for k in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(k, "t@t")
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", land.LIVE, str(origin))
    seed = tmp_path / "seed"
    _git(tmp_path, "clone", "-q", str(origin), str(seed))
    _git(seed, "checkout", "-q", "-b", land.LIVE)
    _commit(seed, {".github/scripts/fast_lane.py": FAST, ".github/scripts/audit_gate.py": GATE,
                   "libs/money.py": "M = 1\n", "research/r.py": "R = 1\n"}, "base")  # fmt: skip
    _git(seed, "push", "-q", "origin", land.LIVE)
    c = tmp_path / "c"
    _git(tmp_path, "clone", "-q", "-b", land.LIVE, str(origin), str(c))
    _git(c, "checkout", "-q", "-b", "claude/work")
    # LIVE moves on after the branch was cut, as it always does
    _commit(seed, {"research/other.py": "O = 1\n"}, "live moved")
    _git(seed, "push", "-q", "origin", land.LIVE)
    return c


def _live(c: Path) -> str:
    _git(c, "fetch", "-q", "origin")
    return _git(c, "rev-parse", f"origin/{land.LIVE}")


def _ok(_cwd: Path, _paths: Any) -> None:
    return None


def _no_prs(path: str) -> list[dict[str, Any]]:
    return []


def test_a_non_money_change_lands_as_a_fast_forward_merge(clone: Path) -> None:
    before = _live(clone)
    head = _commit(clone, {"research/r.py": "R = 2\n"}, "research change")
    dry = land.land(clone, push=False, fetch=lambda: ON, check=_ok, api=_no_prs)
    assert dry.startswith("would land")
    assert _live(clone) == before  # a dry run pushes nothing
    out = land.land(clone, push=True, fetch=lambda: ON, check=_ok, api=_no_prs)
    assert out.startswith("landed"), out
    tip = _live(clone)
    assert _git(clone, "rev-list", "--parents", "-n1", tip).split()[1:] == [before, head]
    assert _git(clone, "show", f"{tip}:research/r.py") == "R = 2"
    assert _git(clone, "show", f"{tip}:research/other.py") == "O = 1"  # LIVE's work kept
    assert gate.is_registry_merge(_git(clone, "log", "-1", "--format=%B", tip))  # auto-revert


@pytest.mark.parametrize(
    ("files", "board", "why"),
    [
        ({"libs/money.py": "M = 2\n"}, ON, "money path"),
        ({"research/r.py": "R = 3\n"}, OFF, "DEACTIVATE"),
    ],
)
def test_money_or_a_switched_off_lane_is_refused_and_live_is_untouched(
    clone: Path, files: dict[str, str], board: list[dict[str, str]], why: str
) -> None:
    before = _live(clone)
    _commit(clone, files, "change")
    with pytest.raises(land.Refused, match=why):
        land.land(clone, push=True, fetch=lambda: board, check=_ok, api=_no_prs)
    assert _live(clone) == before


def test_uncommitted_work_a_failed_smoke_and_a_conflict_are_refused(clone: Path) -> None:
    before = _live(clone)
    _commit(clone, {"research/r.py": "R = 2\n"}, "change")
    (clone / "research/r.py").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(land.Refused, match="uncommitted"):
        land.land(clone, push=True, fetch=lambda: ON, check=_ok, api=_no_prs)
    _git(clone, "checkout", "--", "research/r.py")

    def red(_cwd: Path, _paths: Any) -> None:
        raise land.Refused("smoke failed: x")

    with pytest.raises(land.Refused, match="smoke"):
        land.land(clone, push=True, fetch=lambda: ON, check=red, api=_no_prs)
    _commit(clone, {"research/other.py": "MINE\n"}, "clashes with LIVE's new file")
    with pytest.raises(land.Refused, match="conflicts with LIVE"):
        land.land(clone, push=True, fetch=lambda: ON, check=_ok, api=_no_prs)
    assert _live(clone) == before


def test_an_unreadable_board_never_lands(clone: Path) -> None:
    _commit(clone, {"research/r.py": "R = 2\n"}, "change")

    def boom() -> list[dict[str, str]]:
        raise OSError("offline")

    with pytest.raises(land.Refused, match="not landing blind"):
        land.land(clone, push=True, fetch=boom, check=_ok, api=_no_prs)


def test_an_audit_hold_on_the_branch_s_pr_stops_the_landing(clone: Path) -> None:
    """#1240 audit MF2: an Audit HOLD beats a direct landing exactly as it beats green CI."""
    before = _live(clone)
    _commit(clone, {"research/r.py": "R = 2\n"}, "change")

    def api(path: str) -> list[dict[str, Any]]:
        if "/pulls?state=open&head=" in path:
            return [{"number": 9, "state": "open"}]
        if path.endswith("/issues/9/comments?per_page=100"):
            return [{"body": "AUDIT CLEAR aaaa"}, {"body": "AUDIT HOLD bbbbbbbbbbbb"}]
        return []

    with pytest.raises(land.Refused, match="AUDIT HOLD bbbbbbbbb stands on #9"):
        land.land(clone, push=True, fetch=lambda: ON, check=_ok, api=api)

    def unreadable(path: str) -> list[dict[str, Any]]:
        raise subprocess.CalledProcessError(1, "gh")

    with pytest.raises(land.Refused, match="verdicts could not be read"):
        land.land(clone, push=True, fetch=lambda: ON, check=_ok, api=unreadable)
    assert _live(clone) == before


def test_smoke_runs_on_the_merge_it_lands_not_the_branch(clone: Path) -> None:
    """#1240 audit SF1: the merged tree holds LIVE's new file as well as the branch's change."""
    _commit(clone, {"research/r.py": "R = 2\n"}, "change")
    seen: list[Path] = []

    def look(cwd: Path, _paths: Any) -> None:
        assert (cwd / "research/other.py").read_text(encoding="utf-8") == "O = 1\n"
        assert (cwd / "research/r.py").read_text(encoding="utf-8") == "R = 2\n"
        seen.append(cwd)

    land.land(clone, push=False, fetch=lambda: ON, check=look, api=_no_prs)
    assert seen and seen[0] != clone and not seen[0].exists()  # a private checkout, removed
    assert "Claude-Session" not in land.TRAILER  # SF2: no one session's name on every landing
