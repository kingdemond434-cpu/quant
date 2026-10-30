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
    assert pats[:3] == ["**", ".github/**", ".*"]  # dot paths named outright (#521 audit)
    neg = {p[1:] for p in pats if p.startswith("!")}
    assert neg == {p + "**" for p in STATE_PREFIXES} | set(STATE_FILES)
    pos = [p for p in pats[3:] if not p.startswith("!")]
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


def test_the_box_sweep_skips_pending_prs_streams_and_stops_on_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """2026-10-29: a full run for each of 231 PRs outlasted the task limit, so no line was ever
    logged. A PR whose gating checks still run costs one read; the pass stops at its budget."""
    prs = [{"number": n, "head": {"sha": f"{n:040d}"}} for n in (1, 2, 3)]
    green = [{"name": j, "status": "completed", "conclusion": "success",
              "started_at": "t"} for j in ag.GATING_JOBS]  # fmt: skip
    pending = [dict(green[0], status="queued", conclusion=None), *green[1:]]

    def gh(path: str, *a: Any, **k: Any) -> Any:
        if path.startswith("repos/o/r/pulls?"):
            return [prs]
        if "/check-runs" in path:
            return {
                "check_runs": pending if path.split("/")[4].startswith("0" * 39 + "2") else green
            }
        raise AssertionError(path)

    ran: list[int] = []

    def fake_run(repo: str, n: int, *a: Any, **k: Any) -> int:
        ran.append(n)
        return 0

    monkeypatch.setattr(ag, "_gh", gh)
    monkeypatch.setattr(ag, "run", fake_run)
    assert ag.sweep("o/r", ag.LIVE) == 0 and ran == [1, 3, 2]  # still running: last
    ticks = iter([0.0] * 5 + [10_000.0] * 5)  # start, three pre-reads, one run, then out
    ran.clear()
    ag.sweep("o/r", ag.LIVE, budget_s=60, clock=lambda: next(ticks))
    assert ran == [1]


def test_the_watcher_runs_on_every_exit_of_the_box_sweep() -> None:
    ps = (ROOT / "ops/box/workflow_gate.ps1").read_text(encoding="utf-8")
    assert 'Beat 3 "gh not logged in" $false; Watch; exit 3' in ps
    catch = ps.split("} catch {", 1)[1].split("} finally {", 1)[0]
    assert "Watch" in catch
    call = next(ln for ln in ps.splitlines() if "& $Python" in ln and "--sweep --box" in ln)
    assert "ForEach-Object" in call and "Out-String" not in call  # streamed, never buffered


def test_one_manifest_row_per_task_and_the_watcher_has_an_independent_contract() -> None:
    import collections

    rows = re.findall(r'^TASK name="([^"]+)"', (ROOT / "desks/mt5/ops/box_tasks.manifest")
                      .read_text(encoding="utf-8"), flags=re.M)  # fmt: skip
    gate = [r for r in rows if r == "Quant-WorkflowGate"]
    assert len(gate) == 1
    dup = [n for n, c in collections.Counter(rows).items() if c > 1 and n.startswith("Quant-")]
    assert dup == []
    oc = (ROOT / "ops/organ_contract.py").read_text(encoding="utf-8")
    assert '"desks/mt5/reports/MERGE_PIPELINE.json", 45' in oc


def _lf() -> Any:
    import importlib.util

    spec = importlib.util.spec_from_file_location("lf", ROOT / "scripts/live_first_ci.py")
    assert spec and spec.loader
    lf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lf)
    return lf


def test_live_first_moves_pr_runs_queued_ahead_of_a_waiting_live_run_behind_it() -> None:
    """2026-10-29 19:45Z: ~120 PR runs queued before LIVE's push runs held every runner."""
    lf = _lf()
    live = {"id": 1, "event": "push", "head_branch": lf.LIVE, "created_at": _iso(30)}
    old = {"id": 2, "event": "pull_request", "head_branch": "b1", "head_sha": "h1",
           "created_at": _iso(60)}  # fmt: skip
    moved = {**old, "id": 3, "head_sha": "gone"}
    later = {**old, "id": 4, "created_at": _iso(10)}
    rerun = {**old, "id": 5, "run_started_at": _iso(1)}  # a re-run joined the queue again
    target = {**old, "id": 6, "event": "pull_request_target", "head_sha": "base-sha"}
    other = {**old, "id": 7, "head_branch": "not-a-pr", "head_sha": "x"}
    heads = {"b1": "h1"}
    waste, ahead = lf.plan(NOW, [live, old, moved, later, rerun, target, other], heads)
    assert waste == [3] and ahead == [2]  # audit-gate and unknown branches are never touched
    fresh = dict(live, created_at=_iso(2))  # LIVE queued under 5 min: nothing moves yet
    assert lf.plan(NOW, [fresh, old, moved], heads) == ([3], [])
    assert lf.plan(NOW, [old, moved], heads) == ([3], [])  # no LIVE run waiting
    assert lf.plan(NOW, [live, old, moved], {}) == ([], [])  # no PR read: nothing cancelled
    dispatch = dict(live, event="workflow_dispatch")  # the gate's merge is a LIVE run too
    assert lf.plan(NOW, [dispatch, old], heads) == ([], [2])
    gate = (ROOT / "ops/box/workflow_gate.ps1").read_text(encoding="utf-8")
    assert "scripts\\live_first_ci.py" in gate and "live-first rc=" in gate


def test_a_cleared_pr_waits_like_live_and_uncleared_runs_ahead_of_it_go_behind() -> None:
    """zuck 2026-10-29 22:08Z: the CLEARed fixes waited an hour behind 155 uncleared runs."""
    lf = _lf()
    clr = {"id": 1, "event": "pull_request", "head_branch": "c", "head_sha": "hc",
           "created_at": _iso(30)}  # fmt: skip
    old = {"id": 2, "event": "pull_request", "head_branch": "u", "head_sha": "hu",
           "created_at": _iso(60)}  # fmt: skip
    old_clr = {**clr, "id": 3, "created_at": _iso(90)}  # a CLEARed run is never moved
    heads = {"c": "hc", "u": "hu"}
    assert lf.plan(NOW, [clr, old, old_clr], heads, cleared=frozenset({"c"})) == ([], [2])
    assert lf.plan(NOW, [clr, old], heads) == ([], [])  # no CLEAR, no LIVE: nothing moves
    fresh = dict(clr, created_at=_iso(2))
    assert lf.plan(NOW, [fresh, old], heads, cleared=frozenset({"c"})) == ([], [])
    stale_clr = dict(clr, head_sha="old")  # a run of a superseded head is waste, not a waiter
    assert lf.plan(NOW, [stale_clr, old], heads, cleared=frozenset({"c"})) == ([1], [])


def test_cleared_reads_a_trusted_unedited_clear_of_the_current_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lf = _lf()
    lf._NUMBERS.update({"c": 7, "u": 8, "e": 9})
    heads = {"c": "abcdef1234", "u": "1234abcd", "e": "eeeeeee99"}

    def note(body: str, assoc: str = "OWNER", edited: bool = False) -> dict[str, Any]:
        return {"body": body, "author_association": assoc, "created_at": "t",
                "updated_at": "t2" if edited else "t"}  # fmt: skip

    by = {7: [note("AUDIT CLEAR abcdef1")], 8: [note("AUDIT CLEAR 1234abcd", assoc="NONE")],
          9: [note("AUDIT CLEAR eeeeeee", edited=True)]}  # fmt: skip

    def gh(path: str, method: str = "GET") -> Any:
        return by[int(path.split("/issues/")[1].split("/")[0])]

    monkeypatch.setattr(lf, "_gh", gh)
    queued = [{"event": "pull_request", "head_branch": b} for b in heads]
    assert lf._cleared("o/r", queued, heads) == {"c"}


def test_a_broken_cleared_read_never_stops_live_first(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """#556 audit SF1: CLEARed-first failing leaves LIVE-first intact."""
    lf = _lf()

    def boom(*a: Any) -> Any:
        raise ImportError("no watcher")

    monkeypatch.setattr(lf, "_cleared", boom)
    monkeypatch.setattr(lf, "_queued", lambda repo: [])
    monkeypatch.setattr(lf, "_heads", lambda repo: {})
    assert lf.run("o/r", lf.LIVE, tmp_path / "s.json", settle_s=0, sleep=lambda s: None) == 0


def test_live_first_owes_before_it_cancels_and_reruns_only_its_own_cancel(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    lf = _lf()
    live = {"id": 1, "event": "push", "head_branch": lf.LIVE, "created_at": "2000-01-01T00:00:00Z"}
    pr = {"id": 2, "event": "pull_request", "head_branch": "b1", "head_sha": "h1",
          "created_at": "1999-12-31T00:00:00Z"}  # fmt: skip
    state = tmp_path / "lf.json"
    runs = {2: {**pr, "status": "queued", "run_attempt": 1}}
    calls: list[tuple[str, str]] = []

    def gh(path: str, method: str = "GET") -> Any:
        calls.append((method, path))
        if "status=queued" in path:
            return {"workflow_runs": [live, pr]}
        if "/pulls?" in path:
            return [{"head": {"ref": "b1", "sha": "h1"}}]
        if path.endswith("/cancel"):
            assert json.loads(state.read_text())["owed"][0]["id"] == 2  # owed BEFORE the cancel
            runs[2] = {**runs[2], "status": "completed", "conclusion": "cancelled"}
            return None
        if path.endswith("/rerun"):
            return None
        return runs[int(path.rsplit("/", 1)[1])]

    monkeypatch.setattr(lf, "_gh", gh)
    assert lf.run("o/r", lf.LIVE, state, settle_s=0, sleep=lambda s: None) == 0
    assert ("POST", "repos/o/r/actions/runs/2/rerun") in calls
    assert json.loads(state.read_text())["owed"] == []
    # a run that completed on its own (not cancelled) is never re-run
    calls.clear()
    runs[2] = {**pr, "status": "queued", "run_attempt": 1}

    def gh2(path: str, method: str = "GET") -> Any:
        if path.endswith("/cancel"):
            runs[2] = {**runs[2], "status": "completed", "conclusion": "success"}
            calls.append((method, path))
            return None
        out = gh(path, method)
        return out

    monkeypatch.setattr(lf, "_gh", gh2)
    assert lf.run("o/r", lf.LIVE, state, settle_s=0, sleep=lambda s: None) == 0
    assert not any(p.endswith("/rerun") for _, p in calls)


def test_the_box_sweep_runs_merge_ready_prs_first_and_failed_ones_last(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Desk health 2026-10-29 20:20Z: in listing order, a green PR waited behind PRs that could
    not merge. Every check green first, then gating green, then a failed gating check."""
    prs = [{"number": n, "head": {"sha": f"{n:040d}"}} for n in (1, 2, 3, 4)]

    def ok(j: str, c: str = "success") -> dict[str, Any]:
        return {"name": j, "status": "completed", "conclusion": c, "started_at": "t"}

    gating = [ok(j) for j in ag.GATING_JOBS]
    every = gating + [ok(j) for j in ag.AUTO_JOBS]
    red = [ok(ag.GATING_JOBS[0], "failure"), *gating[1:]]
    by = {1: gating, 2: red, 3: every, 4: gating}

    def gh(path: str, *a: Any, **k: Any) -> Any:
        if path.startswith("repos/o/r/pulls?"):
            return [prs]
        if "/check-runs" in path:
            return {"check_runs": by[int(path.split("/")[4])]}
        raise AssertionError(path)

    ran: list[int] = []
    budgets: list[list[int]] = []

    def fake_run(repo: str, n: int, *a: Any, **k: Any) -> int:
        ran.append(n)
        budgets.append(k["bring_ups"])
        return 0

    monkeypatch.setattr(ag, "_gh", gh)
    monkeypatch.setattr(ag, "run", fake_run)
    # #552 audit SF4: a failed PR still gets its run (it quarantines and counts), last
    assert ag.sweep("o/r", ag.LIVE) == 0 and ran == [3, 1, 4, 2]
    # SF2: one bring-up budget for the whole pass
    assert all(b is budgets[0] for b in budgets) and budgets[0] == [ag.BRING_UPS_PER_SWEEP]
    ps = (ROOT / "ops/box/workflow_gate.ps1").read_text(encoding="utf-8")
    assert "-cmatch ': MERGED \\('" in ps  # the count reads the gate's own word only


def test_a_queued_live_push_run_is_red() -> None:
    """2026-10-29 19:45Z: LIVE's push runs sat queued behind ~120 PR runs and Adopt-And-Seal
    waited on them; nothing went RED because no PR check was the one waiting."""
    live = [_commit("fix", 1)]
    run = {"event": "push", "head_branch": mp.LIVE, "created_at": _iso(45)}
    rep = mp.assess(NOW, [], {}, {}, [run], 20, live)
    assert [r.split(":")[0] for r in rep["red"]] == ["LIVE_CI_QUEUED"]
    pr_run = dict(run, event="pull_request")
    assert (
        mp.assess(NOW, [], {}, {}, [pr_run, dict(run, created_at=_iso(5))], 20, live)["status"]
        == "GREEN"
    )


def test_the_sign_train_heartbeat_reds_when_stale_failing_wedged_or_unread() -> None:
    """#541 audit MF3: a failing or wedged sign train is never silent."""
    live = [_commit("fix", 1)]
    ok = {"at": _iso(5), "rc": 0, "fail_runs": 0, "mutex_held_runs": 0}
    rep = mp.assess(NOW, [], {}, {}, [], 0, live, sign_beat=ok, sign_expected=True)
    assert rep["status"] == "GREEN" and rep["sign_train"]["rc"] == 0
    cases = (
        (dict(ok, at=_iso(45)), "SIGN_TRAIN_STALE"),
        (dict(ok, rc=1, fail_runs=3), "SIGN_TRAIN_FAILING"),
        (dict(ok, rc=4, mutex_held_runs=3), "SIGN_TRAIN_WEDGED"),
        (None, "SIGN_TRAIN_BLIND"),
    )
    for beat, kind in cases:
        rep = mp.assess(NOW, [], {}, {}, [], 0, live, sign_beat=beat, sign_expected=True)
        assert [r.split(":")[0] for r in rep["red"]] == [kind]
    waiting = dict(ok, waiting_on="claude/sign-train-abc", waiting_since=_iso(150))
    rep = mp.assess(NOW, [], {}, {}, [], 0, live, sign_beat=waiting, sign_expected=True)
    assert [r.split(":")[0] for r in rep["red"]] == ["SIGN_TRAIN_WAITING"]
    two = dict(ok, rc=1, fail_runs=2)  # two in a row is not yet RED
    assert mp.assess(NOW, [], {}, {}, [], 0, live, sign_beat=two, sign_expected=True)["red"] == []
    # v3: a closed-unmerged wait carries waiting_on too, so it reds like an open one
    closed = dict(ok, waiting_on="claude/sign-train-def", waiting_since=_iso(150),
                  note="a sign PR for def was closed unmerged; waiting for LIVE to move")
    rep = mp.assess(NOW, [], {}, {}, [], 0, live, sign_beat=closed, sign_expected=True)
    assert [r.split(":")[0] for r in rep["red"]] == ["SIGN_TRAIN_WAITING"]
    # v3 SF: an untimeable wait, or a counter that is not a number, reds instead of raising
    for odd in (dict(ok, waiting_on="claude/sign-train-abc", waiting_since="soon"),
                dict(ok, fail_runs={"n": 1}), dict(ok, mutex_held_runs="x")):
        rep = mp.assess(NOW, [], {}, {}, [], 0, live, sign_beat=odd, sign_expected=True)
        assert rep["status"] == "RED"
    swept = {"at": _iso(5), "rc": 0, "mutex_held_runs": [1]}
    rep = mp.assess(NOW, [], {}, {}, [], 0, live, beat=swept, beat_expected=True)
    assert [r.split(":")[0] for r in rep["red"]] == ["SWEEP_WEDGED"]


def test_the_sign_train_leg_never_stacks_a_sign_and_is_watched() -> None:
    ps = (ROOT / "ops/box/sign_train_leg.ps1").read_text(encoding="utf-8")
    # #541 audit MF1/v2: every train branch from git, each asked by its exact head
    assert "'refs/heads/claude/sign-train-*'" in ps and "'--head', $b, '--state', 'open'" in ps
    # v2 MF1: never reuse a pushed branch; sign locally and force-push the box's own commit
    assert "reused the" not in ps and "--push" not in ps
    assert "--body-file $bodyFile" in ps and "--body $" not in ps  # v2 MF2: nothing to argv
    assert "'--state', 'closed'" in ps  # a closed sign PR is not reopened for the same head
    # v3 MF1: a closed wait is timed like an open one; gh counts are stdout-only numbers
    assert 'Wait $branch "a sign PR' in ps and ps.count("GhCount @('pr', 'list'") == 2
    assert "-notmatch '^\\d+$'" in ps
    # v3 SF: leased push, one single-parent commit touching exactly the two sealed-state files
    assert "--force-with-lease=$lease" in ps and "push -q --force origin" not in ps
    assert "desks/mt5/data/IMMUTABLE_MANIFEST.json,desks/mt5/research/quantbench.py" in ps
    assert "rev-list --parents -n 1 HEAD" in ps and "Set-Content" not in ps  # no BOM
    assert "AbandonedMutexException" in ps and "mutex_held_runs" in ps  # S1, S2
    assert "--principal" not in ps.split("& $Python", 1)[1].split("\n", 1)[0]
    assert "signed \\d+ file" not in ps  # S3: read from git, not the wording
    gate = (ROOT / "ops/box/workflow_gate.ps1").read_text(encoding="utf-8")
    assert "--sign-heartbeat $sign" in gate
    rows = (ROOT / "desks/mt5/ops/box_tasks.manifest").read_text(encoding="utf-8")
    assert 'TASK name="Quant-SignTrain"' in rows
    inst = (ROOT / "ops/box/install_unattended.ps1").read_text(encoding="utf-8")
    assert "Add-QuantTask 'Quant-SignTrain' 'sign_train_leg.ps1'" in inst
