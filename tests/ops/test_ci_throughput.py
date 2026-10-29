"""CI throughput under a runner backlog (2026-10-29: 189 runs queued, nothing reached LIVE for 4 h).

Four leaks, one test each, plus the RED that puts a clock on "queued":
  1. a box-state-only push on LIVE starts no ci run (paths-ignore == the state classification)
  2. the Actions audit gate looks once and never holds a runner to wait for runners
  3. a new PR head supersedes the old head's release-gates run
  4. a no-comment PR behind LIVE by box state only is still up to date
  5. scripts/merge_pipeline_watch.py goes RED on a check queued over 30 min
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from libs.ops.release import STATE_FILES, STATE_PREFIXES

ROOT = Path(__file__).resolve().parents[2]
WF = ROOT / ".github" / "workflows"


def _load(name: str, rel: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ag = _load("audit_gate_tp", ".github/scripts/audit_gate.py")
mp = _load("merge_pipeline_watch", "scripts/merge_pipeline_watch.py")


def _push_ignores() -> list[str]:
    text = (WF / "ci.yml").read_text(encoding="utf-8")
    block = text.split("paths-ignore:", 1)[1].split("pull_request:", 1)[0]
    return re.findall(r'^\s+- "([^"]+)"', block, flags=re.M)


def test_ci_push_ignores_exactly_the_box_state_paths() -> None:
    want = {p + "**" for p in STATE_PREFIXES} | set(STATE_FILES)
    assert set(_push_ignores()) == want


def test_a_code_path_is_never_ignored() -> None:
    import fnmatch

    pats = _push_ignores()
    for code in (
        "desks/mt5/gateway.py",
        "libs/ops/release.py",
        ".github/workflows/ci.yml",
        "desks/mt5/scripts/x.ps1",
        "scripts/merge_pipeline_watch.py",
    ):
        assert not any(fnmatch.fnmatch(code, p.replace("**", "*")) for p in pats), code


def test_the_actions_gate_looks_once() -> None:
    text = (WF / "audit-gate.yml").read_text(encoding="utf-8")
    assert "--wait-min 0" in text and "--wait-min 300" not in text
    assert int(re.search(r"timeout-minutes:\s*(\d+)", text).group(1)) <= 15  # type: ignore[union-attr]


def test_release_gates_supersede_an_old_head() -> None:
    text = (WF / "release-gates.yml").read_text(encoding="utf-8")
    top = text.split("\njobs:", 1)[0]
    assert "group: release-gates-${{ github.event.pull_request.number }}" in top
    assert "cancel-in-progress: true" in top


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    origin, work = tmp_path / "origin", tmp_path / "work"
    _git(tmp_path, "init", "-q", "-b", ag.LIVE, str(origin))
    for k, v in (("user.name", "t"), ("user.email", "t@t")):
        _git(origin, "config", k, v)
    (origin / ".github").mkdir()
    (origin / ".github" / "ci.yml").write_text("v1\n")
    (origin / "desks/mt5/data").mkdir(parents=True)
    (origin / "desks/mt5/data/sleeves.json").write_text("{}\n")
    _git(origin, "add", ".")
    _git(origin, "commit", "-qm", "base")
    _git(origin, "checkout", "-qb", "pr")
    (origin / "x.py").write_text("x = 1\n")
    _git(origin, "add", ".")
    _git(origin, "commit", "-qm", "pr")
    head = _git(origin, "rev-parse", "HEAD")
    _git(origin, "checkout", "-q", ag.LIVE)

    def live_commit(rel: str, body: str) -> None:
        (origin / rel).parent.mkdir(parents=True, exist_ok=True)
        (origin / rel).write_text(body)
        _git(origin, "add", ".")
        _git(origin, "commit", "-qm", f"live {rel}")
        if work.exists():
            _git(work, "fetch", "-q", "origin")

    def clone() -> None:
        _git(tmp_path, "clone", "-q", str(origin), str(work))
        monkeypatch.chdir(work)

    return head, live_commit, clone


def test_a_state_only_lag_is_up_to_date(repo: Any) -> None:
    head, live_commit, clone = repo
    live_commit("desks/mt5/data/sleeves.json", '{"a": 1}\n')
    live_commit("desks/mt5/reports/BACKUP_STATE.json", "{}\n")
    clone()
    ok, why = ag.up_to_date(ag.LIVE, head)
    assert ok and "2 box-state path(s)" in why


def test_a_code_lag_still_needs_the_merge(repo: Any) -> None:
    head, live_commit, clone = repo
    live_commit("desks/mt5/data/sleeves.json", '{"a": 1}\n')
    live_commit("desks/mt5/gateway.py", "x = 2\n")
    clone()
    ok, why = ag.up_to_date(ag.LIVE, head)
    assert not ok and "behind" in why


def test_a_github_change_on_live_is_never_state(repo: Any) -> None:
    head, live_commit, clone = repo
    live_commit(".github/ci.yml", "v2\n")
    clone()
    assert ag.up_to_date(ag.LIVE, head)[0] is False


def test_no_classifier_means_every_path_is_code(repo: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    head, live_commit, clone = repo
    live_commit("desks/mt5/data/sleeves.json", '{"a": 1}\n')
    clone()
    monkeypatch.setattr(ag, "_is_state_path", lambda: None)
    assert ag.up_to_date(ag.LIVE, head)[0] is False


# ------------------------------------------------------------------ the RED: merge_pipeline_watch

NOW = datetime(2026, 10, 29, 18, 0, tzinfo=UTC)


def _iso(minutes_ago: float) -> str:
    return (NOW - timedelta(minutes=minutes_ago)).isoformat().replace("+00:00", "Z")


def _pr(n: int, sha: str, ref: str) -> dict[str, Any]:
    return {"number": n, "head": {"sha": sha, "ref": ref}, "draft": True}


def _commit(msg: str, minutes_ago: float) -> dict[str, Any]:
    return {"sha": "c" * 40, "commit": {"message": msg, "committer": {"date": _iso(minutes_ago)}}}


def test_a_check_queued_past_30_min_is_red_and_one_under_is_not() -> None:
    prs = [_pr(1, "a" * 40, "b1"), _pr(2, "b" * 40, "b2")]
    checks = {
        "a" * 40: [{"name": "quality", "status": "queued", "started_at": _iso(31)}],
        "b" * 40: [{"name": "quality", "status": "queued", "started_at": _iso(29)}],
    }
    rep = mp.assess(NOW, prs, checks, {}, [], 0, [_commit("fix x", 10)])
    assert rep["status"] == "RED" and len(rep["red"]) == 1 and "#1" in rep["red"][0]


def test_superseded_runs_are_counted_as_waste() -> None:
    prs = [_pr(1, "a" * 40, "b1")]
    runs = [
        {
            "id": 9,
            "event": "pull_request",
            "head_branch": "b1",
            "head_sha": "0" * 40,
            "created_at": _iso(50),
        },
        {
            "id": 8,
            "event": "pull_request",
            "head_branch": "b1",
            "head_sha": "a" * 40,
            "created_at": _iso(5),
        },
    ]
    rep = mp.assess(NOW, prs, {}, {}, runs, 3, [_commit("fix", 1)])
    q = rep["queue"]
    assert q["superseded_queued_runs"] == 1 and q["superseded_run_ids"] == [9]
    assert q["oldest_queued_min"] == 50.0


def test_cleared_work_waiting_and_a_stalled_live_are_red() -> None:
    prs = [_pr(462, "4963e62d5" + "0" * 31, "judge")]
    live = [
        _commit("mt5 box state 2026-10-29_1751", 9),
        _commit("seal release x", 100),
        _commit("Merge #472", 7 * 60),
    ]
    rep = mp.assess(NOW, prs, {}, {462: _iso(150)}, [], 0, live)
    kinds = {r.split()[0].rstrip(":") for r in rep["red"]}
    assert kinds == {"CLEAR_WAITING", "LIVE_STALLED"}
    assert rep["live"]["hours_since_code"] == 7.0


def test_clear_at_reads_a_wrapped_sha_and_ignores_edits_and_strangers() -> None:
    head = "f5421619744394e6779cd8378dc24c282528baa5"
    ok = {
        "author_association": "OWNER",
        "body": "AUDIT CLEAR\nf5421619744394e6779cd8378dc24c28\n2528baa5",
        "created_at": "t1",
        "updated_at": "t1",
    }
    edited = dict(ok, created_at="t2", updated_at="t3")
    stranger = dict(ok, author_association="NONE", created_at="t4", updated_at="t4")
    assert mp.clear_at([ok], head) == "t1"
    assert mp.clear_at([edited, stranger], head) is None
    assert mp.clear_at([ok], "0" * 40) is None


def test_a_blind_watcher_is_red(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def boom(*a: Any, **k: Any) -> Any:
        raise RuntimeError("HTTP 503")

    monkeypatch.setattr(mp, "collect", boom)
    out = tmp_path / "MP.json"
    assert mp.main(["--repo", "o/r", "--out", str(out)]) == 2
    assert "WATCH_BLIND" in out.read_text()


def test_reviewer_fails_the_audit_cleared_are_a_red_rate() -> None:
    prs = [_pr(n, f"{n:040d}", f"b{n}") for n in (1, 2, 3, 4)]
    checks = {
        f"{n:040d}": [{"name": "independent-review", "status": "completed", "conclusion": c}]
        for n, c in ((1, "failure"), (2, "failure"), (3, "failure"), (4, "success"))
    }
    clears = {1: _iso(10), 2: _iso(10)}
    rep = mp.assess(NOW, prs, checks, clears, [], 0, [_commit("fix", 1)])
    assert rep["reviewer"] == {"fails": 3, "cleared_fails": [1, 2], "fp_rate": 0.67}
    assert any(r.startswith("REVIEWER_FP") for r in rep["red"])
    rep = mp.assess(NOW, prs, checks, {1: _iso(10)}, [], 0, [_commit("fix", 1)])
    assert not any(r.startswith("REVIEWER_FP") for r in rep["red"])
