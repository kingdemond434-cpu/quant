"""The audit gate (.github/scripts/audit_gate.py, .github/workflows/audit-gate.yml): a PR into
LIVE merges by itself only when the auditor's latest verdict CLEARs its exact change and CI is
green."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
# A GitHub Actions helper, not a desk organ: it lives under .github/scripts (outside the desk's
# executable areas), so it is loaded by path.
_spec = importlib.util.spec_from_file_location("audit_gate", ROOT / ".github/scripts/audit_gate.py")
assert _spec is not None and _spec.loader is not None
ag = importlib.util.module_from_spec(_spec)
sys.modules["audit_gate"] = ag
_spec.loader.exec_module(ag)
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
        files: tuple[str, ...] = ("scripts/x.py",),
        approvals: list[dict[str, Any]] | None = None,
    ) -> None:
        self.pr = {
            "state": "open",
            "draft": draft,
            "head": {"sha": head, "repo": {"full_name": "o/fork" if fork else "o/r"}},
            "base": {"ref": ag.LIVE},
            "labels": [{"name": n} for n in labels],
            "changed_files": len(files),
        }
        self.files = [
            {"filename": f, "status": "modified", "additions": 1, "deletions": 0} for f in files
        ]
        # zuck's daily approval, by default given after every CLEAR these tests post
        self.approvals = approvals if approvals is not None else [_ok()]
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
        if f"/issues/{ag.APPROVALS_ISSUE}/comments" in path:
            return [self.approvals]
        if path.endswith("/comments?per_page=100"):
            return [self.comments]
        if "/check-runs" in path:
            return {"check_runs": self.runs}
        if "/files?" in path:
            return [self.files]
        if "/pulls?" in path:
            return [[{"number": 7}]]
        return self.pr


def _ok(at: str = "2026-10-28T23:00:00Z", app: str | None = None, **kw: Any) -> dict[str, Any]:
    """zuck's approval comment on the tracking issue."""
    c = {
        "body": kw.get("body", ag.APPROVE),
        "created_at": at,
        "updated_at": kw.get("updated_at", at),
        "author_association": kw.get("assoc", "OWNER"),
        "user": {"login": "kingdemond434-cpu"},
        "performed_via_github_app": {"slug": app} if app else None,
    }
    return c


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


# --------------------------------------------------------------- workflow-file PRs: the box


WF = (".github/workflows/ci.yml", "scripts/x.py")


def test_touches_workflows_sees_either_side_of_a_rename() -> None:
    assert ag.touches_workflows([{"filename": ".github/workflows/a.yml"}])
    assert ag.touches_workflows(
        [{"filename": "old/a.yml", "previous_filename": ".github/workflows/a.yml"}]
    )
    assert not ag.touches_workflows([{"filename": ".github/CODEOWNERS"}, {"filename": "x.py"}])


def test_the_actions_gate_leaves_a_workflow_pr_to_the_box_without_failing(hub: Any) -> None:
    h = hub(comments=[_c(f"AUDIT CLEAR {A}", "2026-10-28T10:00:00Z")], files=WF)
    assert ag.run("o/r", 7, ag.LIVE, wait_min=0, poll_s=0) == 0
    assert _merges(h) == []
    assert any(w[1].endswith(f"statuses/{A}") and "state=pending" in w for w in h.writes)


def test_the_box_merges_a_cleared_green_workflow_pr_pinned_and_dispatches_nothing(
    hub: Any,
) -> None:
    h = hub(comments=[_c(f"AUDIT CLEAR {A}", "2026-10-28T10:00:00Z")], files=WF)
    assert ag.main(["--repo", "o/r", "--sweep", "--box"]) == 0
    (merge,) = _merges(h)
    assert f"sha={A}" in merge
    assert not any("dispatches" in w[1] for w in h.writes)
    assert not any(w[0] == "DELETE" for w in h.writes)  # the label is the Actions run's


@pytest.mark.parametrize("case", ["no_clear", "hold", "red_ci", "pending_ci"])
def test_the_box_merges_nothing_else(hub: Any, case: str) -> None:
    comments = {
        "no_clear": [],
        "hold": [
            _c(f"AUDIT CLEAR {A}", "2026-10-28T10:00:00Z"),
            _c(f"AUDIT HOLD {A}", "2026-10-28T10:01:00Z"),
        ],
    }.get(case, [_c(f"AUDIT CLEAR {A}", "2026-10-28T10:00:00Z")])
    runs = {
        "red_ci": [*_green(), _r("lint", conclusion="failure")],
        "pending_ci": _green()[:2],
    }.get(case)
    h = hub(comments=comments, runs=runs, files=WF)
    code = ag.run("o/r", 7, ag.LIVE, wait_min=0, poll_s=0, box=True)
    assert _merges(h) == [] and code == (1 if case == "red_ci" else 0)
    assert not any("state=pending" in w for w in h.writes)  # the Actions run owns pending


def test_the_box_needs_no_label_and_marks_a_draft_ready_for_any_cleared_pr(
    hub: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cloud sessions cannot add the label or mark ready (2026-10-28): the box does both jobs."""
    h = hub(comments=[_c(f"AUDIT CLEAR {A}", "2026-10-28T10:00:00Z")], draft=True, labels=())
    ran: list[list[str]] = []
    monkeypatch.setattr(ag.subprocess, "run", lambda cmd, **kw: ran.append(cmd))
    assert ag.main(["--repo", "o/r", "--sweep", "--box"]) == 0
    (merge,) = _merges(h)
    assert f"sha={A}" in merge
    assert ran == [["gh", "pr", "ready", "7", "-R", "o/r"]]
    assert not any("dispatches" in w[1] for w in h.writes)


def test_sweep_needs_box() -> None:
    with pytest.raises(SystemExit):
        ag.main(["--repo", "o/r", "--sweep"])


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
    assert "python .github/scripts/audit_gate.py" in wf


def test_a_dispatched_ci_run_on_live_seals_and_promotes_like_a_push() -> None:
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in ci
    both = "(github.event_name == 'push' || github.event_name == 'workflow_dispatch')"
    for job in ("seal", "promote"):
        start = ci.index(f"\n  {job}:\n")
        assert both in ci[start : start + 400], job
    assert f"{both} && github.sha || 'pr'" in ci


# ------------------------------------------------------------- zuck's daily approval (#453)


@pytest.mark.parametrize(
    "approvals",
    [
        [],  # none yet
        [_ok("2026-10-28T09:00:00Z")],  # before the CLEAR: the CLEAR waits for the next one
        [_ok(app="claude")],  # posted through the Claude app: never an approval
        [_ok(assoc="COLLABORATOR")],  # not the owner
        [_ok(updated_at="2026-10-28T23:05:00Z")],  # edited
        [_ok(body="APPROVE MERGES please")],  # not exactly the line
    ],
)
def test_a_clear_without_zucks_later_approval_merges_nothing(
    hub: Any, approvals: list[dict[str, Any]]
) -> None:
    for box in (False, True):
        h = hub(comments=[_c(f"AUDIT CLEAR {A}", "2026-10-28T10:00:00Z")], approvals=approvals)
        assert ag.run("o/r", 7, ag.LIVE, wait_min=0, poll_s=0, box=box) == 0
        assert _merges(h) == []


def test_one_approval_covers_every_clear_given_before_it_and_the_newest_counts(hub: Any) -> None:
    h = hub(
        comments=[_c(f"AUDIT CLEAR {A}", "2026-10-28T10:00:00Z")],
        approvals=[
            _ok("2026-10-28T09:00:00Z"),
            _ok("2026-10-28T11:00:00Z", app="claude"),
            _ok("2026-10-28T12:00:00Z"),
        ],
    )
    assert ag.main(["--repo", "o/r", "--sweep", "--box"]) == 0
    (merge,) = _merges(h)
    assert f"sha={A}" in merge


def test_a_hold_after_the_approval_still_wins(hub: Any) -> None:
    h = hub(
        comments=[
            _c(f"AUDIT CLEAR {A}", "2026-10-28T10:00:00Z"),
            _c(f"AUDIT HOLD {A}", "2026-10-28T13:00:00Z"),
        ],
        approvals=[_ok("2026-10-28T12:00:00Z")],
    )
    assert ag.run("o/r", 7, ag.LIVE, wait_min=0, poll_s=0, box=True) == 0 and _merges(h) == []


# ------------------------------------------------------------------------------ the two tiers

DOC = "docs/research/notes_on_carry.md"


def _f(name: str, **kw: Any) -> dict[str, Any]:
    return {"filename": name, "status": "modified", "additions": 1, "deletions": 0, **kw}


@pytest.mark.parametrize(
    ("files", "changed", "read", "low"),
    [
        ([_f(DOC)], 1, set(), True),
        ([_f("context/decision_journal.jsonl")], 1, {"context/decision_journal.jsonl"}, True),
        ([_f("context/decision_journal.jsonl", deletions=1)], 1, set(), False),  # not an append
        ([_f(DOC)], 2, set(), False),  # the count does not add up
        ([], 0, set(), False),
        ([_f(DOC)], 1, {DOC}, False),  # a program reads it
        ([_f("docs/LAWS.md")], 1, set(), False),  # a governing document
        ([_f("docs/x/CLAUDE.md")], 1, set(), False),
        ([_f("docs/ops/prompt_notes.md")], 1, set(), False),
        ([_f("desks/mt5/research/x.py")], 1, set(), False),  # code
        ([_f("docs/research/x.json")], 1, set(), False),  # data
        ([_f("tests/test_x.py")], 1, set(), False),
        ([_f(".github/scripts/audit_gate.py")], 1, set(), False),
        ([_f(DOC, previous_filename="ops/x.py", status="renamed")], 1, set(), False),
        ([_f(DOC), _f("libs/risk/x.py")], 2, set(), False),
    ],
)
def test_only_prose_no_program_reads_is_low_tier(
    files: list[dict[str, Any]], changed: int, read: set[str], low: bool
) -> None:
    assert ag.tier(files, changed, lambda n: n in read)[0] is low


@pytest.fixture
def low_hub(hub: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    def make(**kw: Any) -> Any:
        h = hub(files=(DOC,), approvals=kw.pop("approvals", [_ok(body=ag.ACTIVATE)]), **kw)
        monkeypatch.setattr(ag, "referenced_by_code", lambda base, n: False)
        return h

    return make


def test_a_low_tier_pr_merges_on_green_ci_with_no_comment_from_anyone(low_hub: Any) -> None:
    h = low_hub(comments=[])
    assert ag.run("o/r", 7, ag.LIVE, wait_min=0, poll_s=0) == 0
    (merge,) = _merges(h)
    assert f"sha={A}" in merge and "LOW tier" in " ".join(merge)


def test_a_low_tier_pr_never_waits_and_a_hold_still_stops_it(low_hub: Any) -> None:
    h = low_hub(comments=[], runs=_green()[:2])
    assert ag.run("o/r", 7, ag.LIVE, wait_min=300, poll_s=0) == 0 and _merges(h) == []
    h = low_hub(comments=[_c(f"AUDIT HOLD {A}", "2026-10-28T10:00:00Z")])
    assert ag.run("o/r", 7, ag.LIVE, wait_min=0, poll_s=0, box=True) == 0 and _merges(h) == []


def test_a_low_tier_file_that_code_reads_needs_the_full_live_path(
    hub: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = hub(files=(DOC,), approvals=[_ok(body=ag.ACTIVATE)], comments=[])
    monkeypatch.setattr(ag, "referenced_by_code", lambda base, n: True)
    assert ag.run("o/r", 7, ag.LIVE, wait_min=0, poll_s=0, box=True) == 0 and _merges(h) == []


def test_referenced_by_code_fails_closed_when_git_cannot_look(tmp_path: Path) -> None:
    import os

    cwd = os.getcwd()
    os.chdir(tmp_path)  # not a repository: git grep exits 128
    try:
        assert ag.referenced_by_code(ag.LIVE, DOC) is True
    finally:
        os.chdir(cwd)


@pytest.mark.parametrize(
    "approvals",
    [
        [],  # never activated: ships off
        [_ok(body=ag.ACTIVATE, app="claude")],  # a Claude session cannot switch it on
        [_ok(body=ag.ACTIVATE, assoc="COLLABORATOR")],
        [_ok(body=ag.ACTIVATE, updated_at="2026-10-28T23:09:00Z")],  # edited
        # anyone trusted may switch it off, a Claude session included
        [_ok("2026-10-28T20:00:00Z", body=ag.ACTIVATE), _ok(body=ag.DEACTIVATE, app="claude")],
    ],
)
def test_the_low_tier_is_off_until_zuck_himself_activates_it(
    low_hub: Any, approvals: list[dict[str, Any]]
) -> None:
    h = low_hub(comments=[], approvals=approvals)
    assert ag.run("o/r", 7, ag.LIVE, wait_min=0, poll_s=0, box=True) == 0 and _merges(h) == []


def test_zuck_can_switch_it_back_on_after_a_deactivate(low_hub: Any) -> None:
    h = low_hub(
        comments=[],
        approvals=[
            _ok("2026-10-28T20:00:00Z", body=ag.DEACTIVATE, app="claude"),
            _ok("2026-10-28T21:00:00Z", body=ag.ACTIVATE),
        ],
    )
    assert ag.run("o/r", 7, ag.LIVE, wait_min=0, poll_s=0, box=True) == 0
    assert len(_merges(h)) == 1


# ------------------------------------------------------------------------ #454 audit fixes


def test_a_case_variant_of_a_code_named_path_is_read_by_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#454 audit MF1: the box checks out on NTFS, where a new `gap_register.md` overwrites the
    `GAP_REGISTER.md` a program reads, so the reference check ignores case."""
    origin, work = tmp_path / "origin", tmp_path / "work"
    _git(tmp_path, "init", "-q", "-b", ag.LIVE, str(origin))
    for k, v in (("user.name", "t"), ("user.email", "t@t")):
        _git(origin, "config", k, v)
    (origin / "reader.py").write_text('P = "docs/GAP_REGISTER.md"\n')
    _git(origin, "add", ".")
    _git(origin, "commit", "-qm", "base")
    _git(tmp_path, "clone", "-q", str(origin), str(work))
    monkeypatch.chdir(work)
    assert ag.referenced_by_code(ag.LIVE, "docs/GAP_REGISTER.md") is True
    assert ag.referenced_by_code(ag.LIVE, "docs/gap_register.md") is True
    assert ag.referenced_by_code(ag.LIVE, "docs/research/other.md") is False


@pytest.mark.parametrize(
    "name",
    [
        "docs/research/FAILED_BREAKOUT_PREREGISTRATION.md",
        "docs/research/axis_preregistrations.md",
        "docs/GAP_REGISTER.md",
        "docs/research/panel_rulings.md",
    ],
)
def test_preregistrations_registers_and_rulings_are_governing(name: str) -> None:
    """#454 audit MF2: a study's pre-registered bar never moves on the no-comment path."""
    assert ag.tier([_f(name)], 1, lambda n: False)[0] is False


def test_once_the_auditor_has_spoken_a_low_pr_takes_the_live_path(low_hub: Any) -> None:
    """#454 audit S1: any AUDIT verdict, on any sha, sends the PR down the full LIVE path."""
    stale_clear = [
        _c(f"AUDIT HOLD {A}", "2026-10-28T10:00:00Z"),
        _c(f"AUDIT CLEAR {C}", "2026-10-28T10:05:00Z"),  # a stale sha, a different change
    ]
    h = low_hub(comments=stale_clear)
    assert ag.run("o/r", 7, ag.LIVE, wait_min=0, poll_s=0, box=True) == 0 and _merges(h) == []
    h = low_hub(
        comments=[_c(f"AUDIT CLEAR {A}", "2026-10-28T10:00:00Z")],
        approvals=[_ok("2026-10-28T20:00:00Z", body=ag.ACTIVATE), _ok()],
    )
    assert ag.run("o/r", 7, ag.LIVE, wait_min=0, poll_s=0, box=True) == 0
    (merge,) = _merges(h)
    assert "audit CLEAR" in " ".join(merge)


@pytest.mark.parametrize(
    "board",
    [
        # an edited trusted comment, whatever it says now, switches it off at its edit time
        [
            _ok("2026-10-28T20:00:00Z", body=ag.ACTIVATE),
            _ok("2026-10-28T19:00:00Z", body="hi", updated_at="2026-10-28T21:00:00Z"),
        ],
        # OFF wins a tie
        [
            _ok("2026-10-28T20:00:00Z", body=ag.ACTIVATE),
            _ok("2026-10-28T20:00:00Z", body=ag.DEACTIVATE),
        ],
        [
            _ok("2026-10-28T20:00:00Z", body=ag.DEACTIVATE),
            _ok("2026-10-28T20:00:00Z", body=ag.ACTIVATE),
        ],
    ],
)
def test_the_switch_fails_safe(board: list[dict[str, Any]]) -> None:
    assert ag.activated(board)[0] is False


def test_a_deactivate_between_the_reads_stops_the_low_merge(
    low_hub: Any,
) -> None:
    """#454 audit S3: the switch is read again right before the merge."""
    h = low_hub(comments=[])
    reads = {"n": 0}
    on = [_ok("2026-10-28T20:00:00Z", body=ag.ACTIVATE)]
    off = [*on, _ok("2026-10-28T21:00:00Z", body=ag.DEACTIVATE, app="claude")]

    class _Board(list):  # type: ignore[type-arg]
        def __iter__(self):  # type: ignore[no-untyped-def]
            reads["n"] += 1
            return iter(on if reads["n"] < 3 else off)

    h.approvals = _Board()
    assert ag.run("o/r", 7, ag.LIVE, wait_min=0, poll_s=0, box=True) == 0
    assert _merges(h) == [] and reads["n"] >= 3
