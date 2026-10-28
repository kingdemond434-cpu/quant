"""The audit gate (scripts/audit_gate.py, .github/workflows/audit-gate.yml): a PR into LIVE merges
by itself only when the auditor's latest verdict CLEARs its exact change and CI is green."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from scripts import audit_gate as ag

ROOT = Path(__file__).resolve().parents[2]
A, B, C = "a" * 40, "b" * 40, "c" * 40


def _c(body: str, at: str, assoc: str = "OWNER") -> dict[str, Any]:
    return {
        "body": body,
        "created_at": at,
        "author_association": assoc,
        "user": {"login": "kingdemond434-cpu"},
    }


def _never(_sha: str) -> bool:
    return False


# ------------------------------------------------------------------------------ verdicts


def test_only_a_trusted_exact_verdict_line_counts() -> None:
    found = ag.verdicts(
        [
            _c(f"AUDIT CLEAR {A}", "2026-10-28T10:00:00Z", assoc="NONE"),  # a stranger
            _c(f"looks fine, AUDIT CLEAR {A}", "2026-10-28T10:01:00Z"),  # not line-start
            _c(f"AUDIT CLEAR {A[:12]}", "2026-10-28T10:02:00Z"),  # short sha
            _c(f"report attached\nAUDIT CLEAR {A} squash\n", "2026-10-28T10:03:00Z"),
        ]
    )
    assert [(v["verdict"], v["sha"], v["method"]) for v in found] == [("CLEAR", A, "squash")]


def test_the_latest_verdict_rules_and_a_later_hold_blocks() -> None:
    clear = ag.verdicts([_c(f"AUDIT CLEAR {A}", "2026-10-28T10:00:00Z")])
    got, why = ag.cleared(clear, A, _never)
    assert got is not None and got["method"] == "merge"
    held = ag.verdicts(
        [
            _c(f"AUDIT CLEAR {A}", "2026-10-28T10:00:00Z"),
            _c(f"AUDIT HOLD {A}", "2026-10-28T10:05:00Z"),
        ]
    )
    got, why = ag.cleared(held, A, _never)
    assert got is None and "HOLD" in why
    again = ag.verdicts(
        [
            _c(f"AUDIT HOLD {A}", "2026-10-28T10:05:00Z"),
            _c(f"AUDIT CLEAR {B}", "2026-10-28T10:09:00Z"),
        ]
    )
    assert ag.cleared(again, B, _never)[0] is not None


def _edited(body: str, at: str, edited_at: str) -> dict[str, Any]:
    return {**_c(body, at), "updated_at": edited_at}


@pytest.mark.parametrize(
    "body",
    [f"AUDIT CLEAR {A}", f"AUDIT HOLD {A}\nMF1 added later", "(text that replaced a HOLD)"],
)
def test_an_edited_comment_is_a_hold_whatever_it_says_now(body: str) -> None:
    """#445 audit: a HOLD must be sticky. REST shows only the latest body, so an edit can hide
    a HOLD (edited into a CLEAR, edited away, or just a typo fixed): every edited trusted
    comment is a HOLD at its edit time, and only a NEW CLEAR comment lifts it."""
    found = ag.verdicts(
        [
            _c(f"AUDIT CLEAR {A}", "2026-10-28T10:00:00Z"),
            _edited(body, "2026-10-28T10:05:00Z", "2026-10-28T10:20:00Z"),
        ]
    )
    got, why = ag.cleared(found, A, _never)
    assert got is None and "HOLD" in why
    lifted = [*found, ag.verdicts([_c(f"AUDIT CLEAR {A}", "2026-10-28T10:30:00Z")])[0]]
    assert ag.cleared(lifted, A, _never)[0] is not None
    same = {**_c(f"AUDIT CLEAR {A}", "2026-10-28T10:00:00Z"), "updated_at": "2026-10-28T10:00:00Z"}
    assert ag.verdicts([same])[0]["verdict"] == "CLEAR"  # never edited


def test_a_clear_then_an_edited_hold_merges_nothing(hub: Any) -> None:
    h = hub(
        comments=[
            _c(f"AUDIT CLEAR {A}", "2026-10-28T10:00:00Z"),
            _edited(f"AUDIT HOLD {A} (typo fixed)", "2026-10-28T10:05:00Z", "2026-10-28T10:06:00Z"),
        ]
    )
    assert ag.run("o/r", 7, ag.LIVE, wait_min=0, poll_s=0) == 0 and _merges(h) == []


def test_a_clear_for_another_head_needs_the_same_change() -> None:
    found = ag.verdicts([_c(f"AUDIT CLEAR {A}", "2026-10-28T10:00:00Z")])
    assert ag.cleared(found, B, _never)[0] is None
    assert ag.cleared(found, B, lambda sha: sha == A)[0] is not None
    assert ag.cleared([], A, _never) == (None, "no AUDIT verdict on this PR yet")


# ------------------------------------------------------------------------------- CI checks


def _r(
    name: str,
    status: str = "completed",
    conclusion: str | None = "success",
    at: str = "2026-10-28T10:00:00Z",
) -> dict[str, Any]:
    return {"name": name, "status": status, "conclusion": conclusion, "started_at": at}


def _green() -> list[dict[str, Any]]:
    return [
        _r("quality"),
        _r("mt5-money-path"),
        _r("coverage-floor"),
        _r("seal", conclusion="skipped"),
        _r("promote", conclusion="skipped"),
    ]


def test_ci_passes_only_when_every_run_finished_and_the_gating_jobs_succeeded() -> None:
    assert ag.checks(_green())[0] == "pass"
    assert ag.checks([*_green(), _r("gate", status="in_progress", conclusion=None)])[0] == "pass"
    assert ag.checks(_green()[:2])[0] == "pending"  # not started
    assert ag.checks([*_green()[:2], _r("coverage-floor", "in_progress", None)])[0] == "pending"
    assert ag.checks([*_green(), _r("lint", conclusion="failure")])[0] == "fail"


def test_a_skipped_gating_job_is_not_a_success() -> None:
    runs = [_r("quality", conclusion="skipped"), _r("mt5-money-path"), _r("coverage-floor")]
    state, why = ag.checks(runs)
    assert state == "fail" and "quality" in why


def test_a_rerun_job_is_read_by_its_newest_run() -> None:
    runs = [
        _r("quality", conclusion="failure", at="2026-10-28T09:00:00Z"),
        _r("quality", at="2026-10-28T10:00:00Z"),
        _r("mt5-money-path"),
        _r("coverage-floor"),
    ]
    assert ag.checks(runs)[0] == "pass"


# ------------------------------------------------------------------------------- patch-id


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def test_a_clean_merge_in_keeps_the_patch_id_and_a_new_change_does_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, work = tmp_path / "origin", tmp_path / "work"
    _git(tmp_path, "init", "-q", "-b", "live", str(origin))
    for k, v in (("user.name", "t"), ("user.email", "t@t")):
        _git(origin, "config", k, v)
    (origin / "a.txt").write_text("base\n")
    _git(origin, "add", ".")
    _git(origin, "commit", "-qm", "base")
    _git(origin, "checkout", "-qb", "pr")
    (origin / "pr.txt").write_text("the change\n")
    _git(origin, "add", ".")
    _git(origin, "commit", "-qm", "pr")
    cleared = _git(origin, "rev-parse", "HEAD")
    _git(origin, "checkout", "-q", "live")
    (origin / "b.txt").write_text("live moved\n")
    _git(origin, "add", ".")
    _git(origin, "commit", "-qm", "live moves")
    _git(origin, "checkout", "-q", "pr")
    _git(origin, "merge", "-q", "--no-edit", "live")
    merged_in = _git(origin, "rev-parse", "HEAD")
    (origin / "pr.txt").write_text("the change, edited\n")
    _git(origin, "commit", "-qam", "more")
    edited = _git(origin, "rev-parse", "HEAD")
    _git(tmp_path, "clone", "-q", str(origin), str(work))
    monkeypatch.chdir(work)
    pid = ag.patch_id("live", cleared)
    assert pid is not None and ag.patch_id("live", merged_in) == pid
    assert ag.patch_id("live", edited) not in (None, pid)
    assert ag.patch_id("live", "d" * 40) is None  # unfetchable


def test_an_indentation_only_change_does_not_carry_the_clear(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#445 audit MF1: `git patch-id --stable` ignores whitespace, so moving a `return` into an
    `if` kept the id. The change identity is the diff's exact bytes."""
    origin, work = tmp_path / "origin", tmp_path / "work"
    _git(tmp_path, "init", "-q", "-b", "live", str(origin))
    for k, v in (("user.name", "t"), ("user.email", "t@t")):
        _git(origin, "config", k, v)
    (origin / "m.py").write_text("def f(x):\n    return 0\n")
    _git(origin, "add", ".")
    _git(origin, "commit", "-qm", "base")
    _git(origin, "checkout", "-qb", "pr")
    (origin / "m.py").write_text("def f(x):\n    if x:\n        launch()\n    return 1\n")
    _git(origin, "commit", "-qam", "cleared")
    cleared = _git(origin, "rev-parse", "HEAD")
    (origin / "m.py").write_text("def f(x):\n    if x:\n        launch()\n        return 1\n")
    _git(origin, "commit", "-qam", "indent only")
    moved = _git(origin, "rev-parse", "HEAD")
    _git(tmp_path, "clone", "-q", str(origin), str(work))
    monkeypatch.chdir(work)
    assert ag.patch_id("live", cleared) != ag.patch_id("live", moved)


# ------------------------------------------------------------------------------- the run


class _Hub:
    """A fake `gh api`: the PR, its comments and check runs, and the writes the gate makes."""

    def __init__(
        self,
        *,
        head: str = A,
        comments: list[dict[str, Any]] | None = None,
        runs: list[dict[str, Any]] | None = None,
        draft: bool = False,
        fork: bool = False,
        labels: tuple[str, ...] = ("audit-clear",),
    ) -> None:
        self.pr = {
            "state": "open",
            "draft": draft,
            "head": {"sha": head, "repo": {"full_name": "o/fork" if fork else "o/r"}},
            "base": {"ref": ag.LIVE},
            "labels": [{"name": n} for n in labels],
        }
        self.comments = comments or []
        self.runs = runs if runs is not None else _green()
        self.writes: list[tuple[str, ...]] = []

    def __call__(self, *args: str, data: Any = None) -> Any:
        path = args[0]
        if "-X" in args:
            self.writes.append(
                (
                    args[args.index("-X") + 1],
                    path,
                    *([f"{k}={v}" for k, v in sorted((data or {}).items())]),
                )
            )
            return None
        if path.endswith("/comments?per_page=100"):
            return [self.comments]
        if "/check-runs" in path:
            return {"check_runs": self.runs}
        return self.pr


@pytest.fixture
def hub(monkeypatch: pytest.MonkeyPatch) -> Any:
    def make(**kw: Any) -> _Hub:
        h = _Hub(**kw)
        monkeypatch.setattr(ag, "_gh", h)
        monkeypatch.setattr(ag, "patch_id", lambda base, sha: {A: "p1", B: "p1"}.get(sha, sha))
        return h

    return make


def _merges(h: _Hub) -> list[tuple[str, ...]]:
    return [w for w in h.writes if w[1].endswith("/merge")]


def test_a_cleared_green_head_merges_pinned_to_its_sha_and_reseals_live(hub: Any) -> None:
    h = hub(comments=[_c(f"AUDIT CLEAR {A}", "2026-10-28T10:00:00Z")])
    assert ag.run("o/r", 7, ag.LIVE, wait_min=0, poll_s=0) == 0
    (merge,) = _merges(h)
    assert f"sha={A}" in merge and "merge_method=merge" in merge
    assert any(
        w[1].endswith("actions/workflows/ci.yml/dispatches") and f"ref={ag.LIVE}" in w
        for w in h.writes
    )
    assert any(w[0] == "DELETE" and w[1].endswith("/labels/audit-clear") for w in h.writes)


@pytest.mark.parametrize("case", ["no_clear", "hold", "other_change", "fork", "red_ci"])
def test_nothing_merges_without_a_clear_green_own_head(hub: Any, case: str) -> None:
    comments = {
        "no_clear": [],
        "hold": [
            _c(f"AUDIT CLEAR {A}", "2026-10-28T10:00:00Z"),
            _c(f"AUDIT HOLD {A}", "2026-10-28T10:01:00Z"),
        ],
        "other_change": [_c(f"AUDIT CLEAR {C}", "2026-10-28T10:00:00Z")],
    }.get(case, [_c(f"AUDIT CLEAR {A}", "2026-10-28T10:00:00Z")])
    runs = [*_green(), _r("lint", conclusion="failure")] if case == "red_ci" else None
    h = hub(comments=comments, fork=case == "fork", runs=runs)
    code = ag.run("o/r", 7, ag.LIVE, wait_min=0, poll_s=0)
    assert _merges(h) == [] and code == (1 if case == "red_ci" else 0)


def test_a_clean_merge_in_carries_the_clear_to_the_new_head(hub: Any) -> None:
    h = hub(head=B, comments=[_c(f"AUDIT CLEAR {A} squash", "2026-10-28T10:00:00Z")])
    assert ag.run("o/r", 7, ag.LIVE, wait_min=0, poll_s=0) == 0
    (merge,) = _merges(h)
    assert f"sha={B}" in merge and "merge_method=squash" in merge


def test_a_hold_posted_while_ci_runs_stops_the_merge(hub: Any) -> None:
    """#445 audit MF2: the verdict is re-read on every poll and right before the merge."""
    clear = _c(f"AUDIT CLEAR {A}", "2026-10-28T10:00:00Z")
    h = hub(comments=[clear], runs=_green()[:2])
    polls = {"n": 0}
    real = h.__call__

    def gh(*args: str, data: Any = None) -> Any:
        if "/check-runs" in args[0]:
            polls["n"] += 1
            if polls["n"] == 1:  # between poll 1 and poll 2: the HOLD lands, CI goes green
                h.comments = [clear, _c(f"AUDIT HOLD {A}", "2026-10-28T10:05:00Z")]
                h.runs = _green()
        return real(*args, data=data)

    ag._gh = gh  # the fixture's monkeypatch restores it
    assert ag.run("o/r", 7, ag.LIVE, wait_min=5, poll_s=0) == 0
    assert _merges(h) == [] and polls["n"] == 1


def test_a_hold_after_green_ci_but_before_the_merge_stops_it(hub: Any) -> None:
    clear = _c(f"AUDIT CLEAR {A}", "2026-10-28T10:00:00Z")
    h = hub(comments=[clear])
    real = h.__call__

    def gh(*args: str, data: Any = None) -> Any:
        out = real(*args, data=data)
        if "/check-runs" in args[0]:
            h.comments = [clear, _c(f"AUDIT HOLD {A}", "2026-10-28T10:05:00Z")]
        return out

    ag._gh = gh
    assert ag.run("o/r", 7, ag.LIVE, wait_min=5, poll_s=0) == 0 and _merges(h) == []


def test_pending_ci_past_the_wait_gives_up_without_merging(hub: Any) -> None:
    h = hub(comments=[_c(f"AUDIT CLEAR {A}", "2026-10-28T10:00:00Z")], runs=_green()[:2])
    assert ag.run("o/r", 7, ag.LIVE, wait_min=0, poll_s=0) == 1 and _merges(h) == []


# ------------------------------------------------------------------------------ the wiring


def test_the_gate_runs_from_the_base_branch_and_never_runs_pr_code() -> None:
    wf = (ROOT / ".github" / "workflows" / "audit-gate.yml").read_text(encoding="utf-8")
    assert "pull_request_target:" in wf and "\n  pull_request:" not in wf
    assert "ref: ${{ github.event.pull_request.base.ref }}" in wf
    assert "head.sha" not in wf and "head.ref" not in wf  # never checks the PR out
    assert "persist-credentials: false" in wf
    assert "github.event.pull_request.head.repo.full_name == github.repository" in wf
    assert "github.event.label.name == 'audit-clear'" in wf
    assert 'branches: ["claude/llm-auto-upgrade-verify-gcjac3"]' in wf
    assert "python scripts/audit_gate.py" in wf


def test_a_dispatched_ci_run_on_live_seals_and_promotes_like_a_push() -> None:
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in ci
    both = "(github.event_name == 'push' || github.event_name == 'workflow_dispatch')"
    for job in ("seal", "promote"):
        start = ci.index(f"\n  {job}:\n")
        assert both in ci[start : start + 400], job
    assert f"{both} && github.sha || 'pr'" in ci
