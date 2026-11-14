"""THE BASE PINS THE CHECKS THAT JUDGE A PR (2026-11-14).

A PR that changes .github/workflows runs ITS OWN copy of them in `pull_request`, so its green is
self-attested. trusted-eval.yml (pull_request_target, the BASE's file) runs the BASE's copy of
this file against the PR's tree: a head that renames, neuters, skips or soft-fails a gating job
fails here, judged by code the PR cannot touch. That is what lets a change to the workflows move
off zuck's per-PR approval (Governance's follow-up to #1162) without anyone judging their own
gate. Listed in ops/release/trusted_eval_suites.txt (grow-only).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WF = ROOT / ".github" / "workflows"

#: The only `if:` a gating job may carry: same-repo only, and (since 2026-11-14) skip a draft.
DRAFT_SKIP = "github.event_name != 'pull_request' || !github.event.pull_request.draft"
SAME_REPO = "github.event.pull_request.head.repo.full_name == github.repository"


def _wf(name: str) -> dict[Any, Any]:
    doc = yaml.safe_load((WF / name).read_text("utf-8"))
    assert isinstance(doc, dict)
    return doc


def _on(doc: dict[Any, Any]) -> dict[str, Any]:
    on = doc.get("on", doc.get(True))  # YAML 1.1 reads a bare `on:` key as True
    assert isinstance(on, dict)
    return on


def _runs(job: dict[str, Any]) -> str:
    return "\n".join(str(s.get("run") or "") for s in job.get("steps") or [])


def _gate() -> Any:
    spec = importlib.util.spec_from_file_location("ag_pin", ROOT / ".github/scripts/audit_gate.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


#: The steps allowed to soft-fail, by job and exact step name. Serving the local reviewer models
#: may fail: the review then asks the free remote models, and no answer at all ends UNAVAILABLE
#: (queued, never a pass).
SOFT_OK = {"independent-review": {"Serve the pinned open-weight reviewers on this runner"}}


def _no_soft_fail(job: dict[str, Any], name: str) -> None:
    assert not job.get("continue-on-error"), f"{name} may not soft-fail"
    for s in job.get("steps") or []:
        if s.get("continue-on-error"):
            assert s.get("name") in SOFT_OK.get(name, set()), f"{name} step may not soft-fail: {s}"


def test_the_gate_requires_exactly_these_jobs_from_exactly_these_files() -> None:
    ag = _gate()
    assert ag.GATING_JOBS == ("quality", "mt5-money-path", "coverage-floor")
    assert ag.AUTO_JOBS == ("risk-invariants", "replay-shadow", "independent-review")
    for j in ag.GATING_JOBS:
        assert ag.WORKFLOW_OF[j] == ".github/workflows/ci.yml"
    for j in ag.AUTO_JOBS:
        assert ag.WORKFLOW_OF[j] == ".github/workflows/release-gates.yml"
    assert ag.WORKFLOW_OF["trusted-eval"] == ".github/workflows/trusted-eval.yml"
    assert ag.CI_APP == "github-actions"


@pytest.mark.parametrize("name", ["quality", "mt5-money-path", "coverage-floor"])
def test_ci_keeps_each_gating_job_running_on_every_ready_pr(name: str) -> None:
    ci = _wf("ci.yml")
    on = _on(ci)
    assert "pull_request" in on and "push" in on
    job = ci["jobs"][name]
    assert job.get("if") in (None, DRAFT_SKIP), f"{name} may skip only a draft: {job.get('if')}"
    _no_soft_fail(job, name)


def test_quality_really_lints_types_and_runs_the_suite_with_coverage() -> None:
    run = _runs(_wf("ci.yml")["jobs"]["quality"])
    for must in ("ruff check .", "mypy", "run_law_gate.py --laws-only", "pytest ",
                 "--cov=libs", "--cov-branch", "--junitxml"):  # fmt: skip
        assert must in run, f"quality no longer runs {must!r}"


def test_the_money_path_job_runs_the_desk_suite_and_its_ratcheted_floor() -> None:
    run = _runs(_wf("ci.yml")["jobs"]["mt5-money-path"])
    for must in ("pytest desks/mt5/tests", "check_mt5_coverage_floor.py", "check_reachability.py",
                 "check_pit.py"):  # fmt: skip
        assert must in run, f"mt5-money-path no longer runs {must!r}"


def test_the_coverage_floor_combines_both_suites_and_checks_the_floors() -> None:
    job = _wf("ci.yml")["jobs"]["coverage-floor"]
    assert set(job["needs"]) == {"quality", "mt5-money-path"}
    run = _runs(job)
    assert "coverage combine" in run and "check_coverage_floors.py" in run


def test_seal_and_promote_wait_for_every_gating_job() -> None:
    jobs = _wf("ci.yml")["jobs"]
    assert {"quality", "mt5-money-path", "coverage-floor"} <= set(jobs["seal"]["needs"])
    assert {"quality", "mt5-money-path", "coverage-floor", "seal"} <= set(jobs["promote"]["needs"])


@pytest.mark.parametrize("name", ["risk-invariants", "replay-shadow", "independent-review"])
def test_release_gates_keep_each_auto_job(name: str) -> None:
    rg = _wf("release-gates.yml")
    on = _on(rg)
    assert "pull_request" in on
    job = rg["jobs"][name]
    assert job.get("if") in (SAME_REPO, f"{SAME_REPO} && !github.event.pull_request.draft"), (
        f"{name} may skip only a fork or a draft: {job.get('if')}"
    )
    _no_soft_fail(job, name)


def test_replay_shadow_runs_the_base_s_harness_on_base_and_head() -> None:
    job = _wf("release-gates.yml")["jobs"]["replay-shadow"]
    steps = job["steps"]
    harness = [s for s in steps if (s.get("with") or {}).get("path") == "harness"]
    assert harness and harness[0]["with"]["ref"] == "${{ github.event.pull_request.base.sha }}"
    base = [s for s in steps if (s.get("with") or {}).get("path") == "base"]
    head = [s for s in steps if (s.get("with") or {}).get("path") == "head"]
    assert base and base[0]["with"]["ref"] == "${{ github.event.pull_request.base.sha }}"
    assert head and head[0]["with"]["ref"] == "${{ github.event.pull_request.head.sha }}"
    run = _runs(job)
    assert "python -I harness/ops/release/replay_shadow.py --base base --head head" in run


def test_risk_invariants_and_the_reviewer_run_their_release_scripts() -> None:
    jobs = _wf("release-gates.yml")["jobs"]
    assert "ops/release/risk_invariants.py" in _runs(jobs["risk-invariants"])
    assert "ops/release/independent_review.py" in _runs(jobs["independent-review"])
