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
import json
import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from libs.ops.release import (
    GOVERNED_STATE_FILES,
    GOVERNED_STATE_GLOBS,
    STATE_FILES,
    STATE_PREFIXES,
    is_governed_state,
)

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


def _push_paths() -> list[str]:
    text = (WF / "ci.yml").read_text(encoding="utf-8")
    block = text.split("    paths:", 1)[1].split("pull_request:", 1)[0]
    return re.findall(r'^\s+- "([^"]+)"', block, flags=re.M)


def _runs_on_push(changed: list[str]) -> bool:
    """GitHub's rule for `paths` with `!`: a path counts when the LAST pattern it matches is
    positive; the push runs when any changed path counts. `*` stays in one directory."""

    def match(path: str, pat: str) -> bool:
        rx = re.escape(pat).replace(r"\*\*", "\0").replace(r"\*", "[^/]*").replace("\0", ".*")
        return re.fullmatch(rx, path) is not None

    def counts(path: str) -> bool:
        keep = False
        for pat in _push_paths():
            neg = pat.startswith("!")
            if match(path, pat.lstrip("!")):
                keep = not neg
        return keep

    return any(counts(p) for p in changed)


def test_ci_push_paths_are_exactly_the_state_classification() -> None:
    pats = _push_paths()
    assert pats[0] == "**"
    neg = {p[1:] for p in pats if p.startswith("!")}
    assert neg == {p + "**" for p in STATE_PREFIXES} | set(STATE_FILES)
    pos = [p for p in pats[1:] if not p.startswith("!")]
    assert set(pos) == set(GOVERNED_STATE_FILES) | set(GOVERNED_STATE_GLOBS)
    assert pats.index(pos[0]) > max(i for i, p in enumerate(pats) if p.startswith("!"))


def test_a_state_only_push_skips_and_code_or_governed_state_runs() -> None:
    assert not _runs_on_push(["desks/mt5/data/sleeves.json", "desks/mt5/reports/X.json"])
    for code in (
        "desks/mt5/gateway.py",
        "libs/ops/release.py",
        ".github/workflows/ci.yml",
        "desks/mt5/scripts/x.ps1",
        "scripts/merge_pipeline_watch.py",
    ):
        assert _runs_on_push(["desks/mt5/data/sleeves.json", code]), code
    for gov in (
        "desks/mt5/data/IMMUTABLE_MANIFEST.json",
        "desks/mt5/data/GENERIC_EXEC_ENABLED",
        "desks/mt5/data/MARGIN_CLAUSE_DISABLED.json",
        "desks/mt5/reports/ALLOCATOR_PROOF.json",
    ):
        assert _runs_on_push([gov]), gov
        assert is_governed_state(gov), gov
    assert not is_governed_state("desks/mt5/data/sub/X_ENABLED")  # one directory, both sides


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


def test_a_governed_state_lag_still_needs_the_merge(repo: Any) -> None:
    """#521 audit MF1: a sign row alone on LIVE (IMMUTABLE_MANIFEST) is not a state-only lag."""
    head, live_commit, clone = repo
    live_commit("desks/mt5/data/IMMUTABLE_MANIFEST.json", '{"sign": 2}\n')
    clone()
    ok, why = ag.up_to_date(ag.LIVE, head)
    assert not ok and "behind" in why


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


def test_green_and_mergeable_but_open_past_2h_is_red() -> None:
    """How #516 sat: AUTO, every check green, the gate's status success, nobody merging."""
    prs = [_pr(516, "1" * 40, "ftmo")]
    rep = mp.assess(NOW, prs, {}, {}, [], 0, [_commit("fix", 30)], ready={516: _iso(130)})
    assert [r.split()[0] for r in rep["red"]] == ["GREEN_WAITING"]
    rep = mp.assess(NOW, prs, {}, {}, [], 0, [_commit("fix", 30)], ready={516: _iso(60)})
    assert rep["status"] == "GREEN"


def test_live_stalls_on_green_work_too() -> None:
    prs = [_pr(516, "1" * 40, "ftmo")]
    rep = mp.assess(NOW, prs, {}, {}, [], 0, [_commit("fix", 7 * 60)], ready={516: _iso(10)})
    assert any(r.startswith("LIVE_STALLED") for r in rep["red"])


def test_the_sweep_heartbeat_reds_when_stale_wedged_or_unread() -> None:
    live = [_commit("fix", 1)]
    ok = {"at": _iso(5), "rc": 0, "mutex_held_runs": 0}
    assert mp.assess(NOW, [], {}, {}, [], 0, live, beat=ok, beat_expected=True)["status"] == "GREEN"
    stale = dict(ok, at=_iso(45))
    wedged = dict(ok, rc=4, mutex_held_runs=3)
    for beat, kind in ((stale, "SWEEP_STALE"), (wedged, "SWEEP_WEDGED"), (None, "SWEEP_BLIND")):
        rep = mp.assess(NOW, [], {}, {}, [], 0, live, beat=beat, beat_expected=True)
        assert [r.split(":")[0] for r in rep["red"]] == [kind]


def test_a_fresh_report_is_not_re_read_unless_the_sweep_is_wedged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out, beat = tmp_path / "MP.json", tmp_path / "wg.json"
    out.write_text(json.dumps({"at": datetime.now(UTC).isoformat(), "status": "GREEN", "red": []}))
    beat.write_text('{"at": "x", "mutex_held_runs": 0}')
    monkeypatch.setattr(mp, "collect", lambda *a, **k: pytest.fail("re-read a fresh report"))
    assert mp.main(["--repo", "o/r", "--out", str(out), "--heartbeat", str(beat)]) == 0
    beat.write_text('{"at": "x", "mutex_held_runs": 3}')
    seen: list[Any] = []

    def collect(*a: Any, **k: Any) -> dict[str, Any]:
        seen.append(a)
        return {"at": "now", "status": "RED", "red": ["SWEEP_WEDGED: 3"]}

    monkeypatch.setattr(mp, "collect", collect)
    assert mp.main(["--repo", "o/r", "--out", str(out), "--heartbeat", str(beat)]) == 2 and seen


def test_a_second_merger_looks_when_checks_complete() -> None:
    text = (WF / "audit-gate.yml").read_text(encoding="utf-8")
    assert "workflow_run:" in text and 'workflows: ["ci", "release-gates"]' in text
    job = text.split("  after-checks:", 1)[1]
    assert "--wait-min 0" in job and "ref: claude/llm-auto-upgrade-verify-gcjac3" in job
    assert "github.event.workflow_run.event == 'pull_request'" in job


def test_every_gh_call_of_the_gate_can_time_out() -> None:
    src = (ROOT / ".github/scripts/audit_gate.py").read_text(encoding="utf-8")
    assert "timeout=GH_TIMEOUT_S" in src.split("def _gh(", 1)[1].split("\ndef ", 1)[0]
    assert '"pr", "ready"' in src and "check=True, timeout=GH_TIMEOUT_S" in src


def test_the_box_sweep_never_exits_silently_on_a_held_mutex() -> None:
    ps = (ROOT / "ops/box/workflow_gate.ps1").read_text(encoding="utf-8")
    held = ps.split("if (-not $mutex.WaitOne(0)) {", 1)[1].split("\n}", 1)[0]
    assert "Say " in held and "Beat 4" in held and "exit 4" in held and "Watch" in held
    assert "exit 0 }" not in ps.split("$mutex = New-Object", 1)[1].split("\n", 2)[1]
    assert "merge_pipeline_watch.py" in ps and "--heartbeat $beat" in ps
