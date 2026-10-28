#!/usr/bin/env python3
"""THE AUDIT GATE -- a PR merges by itself once the auditor CLEARs its head and CI is green.

WHY (2026-10-28). zuck: "i want this to fully auto merge without me after these". Every merge
so far was a block of `gh pr merge ... --match-head-commit` that zuck pasted on the box, because
an agent's own merge is refused. GitHub's own auto-merge needs branch protection to wait for
anything, and protection with required checks would refuse the CI seal job's push to LIVE (the
github-actions identity is no admin) and the box's state publish. So the gate is this script,
run by .github/workflows/audit-gate.yml on `pull_request_target` -- the workflow file and this
script are read from the BASE branch, never from the PR, so a PR cannot rewrite its own gate.

THE RULE. "Audit HOLD beats green CI" stands. A PR into LIVE merges only when ALL hold:

  1. The LATEST verdict comment on the PR, from the owner or a collaborator, is
     `AUDIT CLEAR <40-hex head sha> [merge|squash]` -- one line, at the start of a line. An
     `AUDIT HOLD <sha>` posted later blocks it until a newer CLEAR.
  2. The CLEARed sha is the PR's head now, OR the head carries the SAME CHANGE: the patch-id of
     the PR's diff from its merge-base with LIVE is identical. A clean merge-in of LIVE keeps
     the CLEAR; any conflict resolution or new commit changes the diff and needs a new CLEAR.
  3. Every CI check run on the head has finished, none failed, and the gating jobs
     (quality, mt5-money-path, coverage-floor) each succeeded.
  4. The PR is from this repository (never a fork) and targets LIVE.
  5. zuck's own `APPROVE MERGES` comment on #453 is newer than that CLEAR (see below).

Then the gate marks a draft ready, merges through the REST API PINNED TO THE HEAD SHA (GitHub
refuses the merge if the head moved), and dispatches ci.yml on LIVE: a merge made with the
workflow token starts no push run, so without the dispatch the seal and promote jobs would never
see the merged code.

    python .github/scripts/audit_gate.py --repo OWNER/NAME --pr N [--base LIVE] [--wait-min 300]

WORKFLOW-FILE PRs. A PR that changes .github/workflows/** -- this gate's own fixes included --
is refused by GitHub for the workflow token (it holds no `workflows` permission). The Actions run
therefore leaves such a PR alone (status "pending: the box merges this") and the BOX merges it
under the SAME rule, with zuck's own gh token (which carries the `workflow` scope).

THE BOX SWEEPS EVERY PR, NOT ONLY WORKFLOW ONES (2026-10-28, Desk health): the cloud sessions are
refused the two writes that start or finish an Actions run -- adding the `audit-clear` label and
marking a draft ready. So the box pass needs no label: it reads the trusted CLEAR comment on
every open PR into LIVE and merges (marking ready first) under the same rule:

    python .github/scripts/audit_gate.py --repo OWNER/NAME --sweep --box

run every 10 minutes by ops/box/workflow_gate.ps1 from a clean checkout of LIVE (trusted code,
never the PR's). The box mode never waits (a PR whose CI is still running is left for the next
sweep), posts no `pending` status (the Actions run owns that), and dispatches nothing: a merge
made with a user token starts the normal push run on LIVE. A PR the Actions gate merged first is
closed by the time the box looks, and a race between the two loses nothing: both merges are
pinned to the same head sha, so GitHub accepts at most one.

FOR A WORKFLOW-FILE PR, "CI GREEN" IS SELF-ATTESTED (#447 audit): its `pull_request` run uses the
PR's own ci.yml, which can rename or neuter quality / mt5-money-path / coverage-floor and still
read green. The CLEAR of the exact bytes is the only real gate there, so the auditor reads every
change to a CI job in such a PR as its critical part.

ZUCK'S DAILY APPROVAL (2026-10-28, zuck: "Fine do one tap a day"). The cloud refuses a Claude
session's own merge trigger, so a CLEAR alone merges nothing. A merge also needs zuck's own
comment, exactly `APPROVE MERGES`, on the tracking issue (#453), POSTED AFTER the CLEAR it
covers: one comment approves every CLEAR already given, and a CLEAR that comes later waits for
the next one. Only zuck's own typing counts -- author_association OWNER, not posted through any
GitHub App (a Claude session's comment carries `performed_via_github_app`), never edited. Claude
never posts it or any substitute.

TWO TIERS (2026-10-28, zuck: "eliminate recurring manual merge approvals"). A PR is LOW tier
only when EVERY file it touches (both sides of a rename) is prose no program reads: a .md or image
under docs/, context/, desks/mt5/docs/ or reports/, whose path and file name appear in no code
file of LIVE (.py .ps1 .sh .cmd .txt .yml .yaml .toml .manifest .service, the git hooks), and
whose name says nothing of laws, constitution, protocol, mandate, policy, prompt, doctrine,
charter, governance or agent instructions -- plus pure appends to context/decision_journal.jsonl.
A LOW-tier PR merges on green gating CI alone, with no comment from anyone; a HOLD still stops it
-- but ONLY ONCE ZUCK HAS ACTIVATED THE CONTROLLER: his own comment, exactly
`ACTIVATE RELEASE CONTROLLER`, on #453 (same identity rules as his approval). Until then, and after
any `DEACTIVATE RELEASE CONTROLLER` -- which anyone trusted may post, a Claude session included,
because stopping is always safe -- a LOW-tier PR takes the LIVE-tier path.
EVERYTHING ELSE IS LIVE TIER and keeps the CLEAR + zuck's approval above: all code (the box runs
research and miners with the MT5 terminals attached), data, configs, tests, workflows, this file.
Unsure is LIVE: a file count that does not add up, an unreadable tree, a grep that errors.
The allowlist lives here, in .github/scripts, which is itself LIVE tier: only a LIVE-tier merge
(auditor CLEAR + zuck's comment) can widen it.

THREE TIERS (step B). LIVE splits in two. PROTECTED -- this controller and every workflow, the
ceilings and the release suite (ops/release/), the release and adopter machinery, the signed
judge manifest, the box and bridge installers, secrets, agent instructions; and any PR the
controller cannot classify for certain -- only ever takes the CLEAR + APPROVE MERGES path.
AUTO -- everything else, execution, sizing, risk, allocation and the judge included -- merges with
no comment once zuck has ALSO typed `ACTIVATE LIVE AUTO-MERGE` on #453 (after the box canary is
ready), no HOLD stands, and the gating jobs AND the AUTO jobs (risk-invariants, replay-shadow,
independent-review) all succeeded. A PR whose CI fails on the LOW or AUTO path is QUARANTINED:
labelled `quarantined`, left open, never merged until a new head passes.

STEP C. The PROTECTED floor above is widened by ops/release/protected_paths.txt (every LAWS 5m
rail, test configuration, signing, kill switches); an unreadable list makes every PR PROTECTED.
The AUTO jobs come from .github/workflows/release-gates.yml. A gating job counts only from GitHub
Actions, and the manual path neither waits on nor fails by the AUTO jobs.

STEP D, ZERO API COST (zuck 2026-10-28 19:47Z). replay-shadow replays the live E8 gold book on
the base and on the PR over a fixed scenario grid and fails on any changed decision or any
money-path file it never imported. independent-review asks free models only, through $0-capped
keys. When no free model answers, the review ends UNAVAILABLE: the PR is QUEUED (pending status,
no quarantine) and the review is re-run later by whichever gate run looks next (the box sweep or
a new event), never merged without it.

Exit 0 when merged or when there is honestly nothing to do yet (no CLEAR); exit 1 when the gate
refused or gave up, with the reason in the job summary and on the `audit/clear` commit status.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

LIVE = "claude/llm-auto-upgrade-verify-gcjac3"
#: The CI jobs that gate a merge (ci.yml). Each must have a SUCCESS run on the head.
GATING_JOBS = ("quality", "mt5-money-path", "coverage-floor")
#: Who may post a verdict (GitHub's author_association).
TRUSTED = ("OWNER", "MEMBER", "COLLABORATOR")
STATUS_CONTEXT = "audit/clear"
#: The issue zuck approves merges on, and his approval line (the whole comment, nothing else).
APPROVALS_ISSUE = 453
APPROVE = "APPROVE MERGES"
ACTIVATE = "ACTIVATE RELEASE CONTROLLER"
DEACTIVATE = "DEACTIVATE RELEASE CONTROLLER"
#: LOW tier: where, what kind of file, and what it may never be named.
LOW_DIRS = ("docs/", "context/", "desks/mt5/docs/", "reports/")
LOW_EXTS = (".md", ".png", ".jpg", ".jpeg", ".svg", ".gif")
APPEND_ONLY = ("context/decision_journal.jsonl",)
FORCED_LIVE = re.compile(
    r"law|constitution|protocol|mandate|polic|prompt|doctrine|charter|governance|claude|agents"
    r"|prereg|register|ruling"
)
#: The files that count as "a program reads it" when they name a path or file name.
CODE_SPECS = (
    "*.py", "*.ps1", "*.sh", "*.cmd", "*.txt", "*.yml", "*.yaml", "*.toml", "*.manifest",
    "*.service", "ops/githooks/*",
)  # fmt: skip
#: PROTECTED: never merged without zuck. fnmatch patterns ("*" crosses "/"). This tuple is the
#: floor; ops/release/protected_paths.txt (itself protected) adds every LAWS 5m rail and more.
PROTECTED = (
    ".github/*", "CODEOWNERS", "*/CODEOWNERS", "ops/release/*", "ops/box/*", "ops/bridge/*",
    "ops/githooks/*", "IMMUTABLE_MANIFEST*", "*/IMMUTABLE_MANIFEST*", "data/secrets/*",
    "*/data/secrets/*", "scripts/check_immutable_evaluator.py", "libs/ops/release.py",
    "libs/ops/release_promotion.py", "desks/mt5/scripts/Adopt*", "desks/mt5/scripts/Seal-*",
    "desks/mt5/scripts/smoke_release.py", "desks/mt5/mt5desk/release_identity.py",
    "CLAUDE.md", "*/CLAUDE.md", "AGENTS.md", "*/AGENTS.md", ".claude/*", "*/.claude/*",
    # what the checks execute (#455 audit MF3)
    "ops/gates.sh", "pyproject.toml", "conftest.py", "*/conftest.py", "setup.cfg", "setup.py",
    "pytest.ini", "tox.ini", "*sitecustomize.py", "*usercustomize.py", "*.pth",
    ".pre-commit-config.yaml", "scripts/moneypath_precommit_guard.py",
    # Tier-3 and the sealed core: never modified autonomously (LAWS 4)
    "scripts/run_deadman_switch.py", "ops/principal_doctrine.txt",
    "scripts/check_constitution_core.py", "ops/brain_env.sh",
    # bars that never move without zuck
    "desks/mt5/research/tier_s.py", "libs/ops/canonical_policy.py",
    "desks/mt5/research/heat_policy.py",
    # the principal's own switches and ceilings, and the kill files
    "*allocator_sovereign*", "*margin_clause_disabled*", "*recorders_off*",
    "*ftmo_copy_principal*", "*gold_oco_mode*", "*gateway_paused*", "*cashcarry_kill*",
    "*deadman_fired*", "data/freeze", "*/data/freeze",
    # governing prose
    "docs/research.md", "docs/cro/*", "ops/memory/*", ".mcp.json", "*/.mcp.json",
)  # fmt: skip
#: Prose files: one whose name matches FORCED_LIVE is a governing document, so PROTECTED.
DOC_EXTS = (".md", ".txt", ".rst")
#: The jobs an AUTO-tier PR needs on top of the gating jobs (step C builds them; until then no
#: AUTO-tier PR can merge, because a missing job is never a pass).
AUTO_JOBS = ("risk-invariants", "replay-shadow", "independent-review")
PROTECTED_FILE = Path(__file__).resolve().parents[2] / "ops" / "release" / "protected_paths.txt"
ACTIVATE_AUTO = "ACTIVATE LIVE AUTO-MERGE"
#: The app every required check run must come from.
CI_APP = "github-actions"
#: The workflow file each required job must come from (#455 audit MF1: any workflow on any
#: branch, or any App, can post a check run with any name on any sha).
WORKFLOW_OF = {
    **dict.fromkeys(("quality", "mt5-money-path", "coverage-floor"), ".github/workflows/ci.yml"),
    **dict.fromkeys(
        ("risk-invariants", "replay-shadow", "independent-review"),
        ".github/workflows/release-gates.yml",
    ),
}
#: The free reviewer's "no model answered" mark (ops/release/independent_review.py): a review
#: that ended this way is QUEUED -- re-run later, never a pass and never a quarantine.
REVIEWER = "independent-review"
UNAVAILABLE_MARK = "REVIEW_UNAVAILABLE"
#: A queued review is re-run once its last attempt is this old, up to GitHub's attempt limit.
RETRY_AFTER_S = 20 * 60
MAX_ATTEMPTS = 48
QUARANTINE = "quarantined"
#: The GitHub files API lists at most 3000 files; past that the PR is never LOW.
MAX_FILES = 3000
#: The label that starts a gate run (the CLEAR comment itself starts none).
LABEL = "audit-clear"
VERDICT = re.compile(r"^AUDIT (CLEAR|HOLD) ([0-9a-f]{40})(?: (merge|squash))?[ \t]*$", re.M)
#: Check-run conclusions that are not a failure.
OK_CONCLUSIONS = ("success", "skipped", "neutral")
#: The gate's own check runs never gate themselves.
SELF_NAMES = ("audit-gate", "gate")
#: Files GitHub refuses to let the workflow token merge.
WORKFLOW_DIR = ".github/workflows/"
BOX_MERGES = "workflow change: the box merges this"


def verdicts(comments: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    """Every verdict line from a trusted author, oldest first. A comment carries at most one
    verdict: its first verdict line."""
    out: list[dict[str, str]] = []
    for c in comments:
        if str(c.get("author_association") or "") not in TRUSTED:
            continue
        m = VERDICT.search(str(c.get("body") or ""))
        by = str((c.get("user") or {}).get("login") or "")
        # AN EDIT IS A HOLD (#445 audit). REST shows only a comment's latest body, so an edit can
        # hide what it replaced: a HOLD edited into a CLEAR, or edited away, would revive the
        # CLEAR before it. So ANY edited trusted comment, whatever it says now, counts as a HOLD
        # at the time of its edit. It fails closed: a new CLEAR comment lifts it.
        updated = c.get("updated_at")
        if updated not in (None, c.get("created_at")):
            out.append(
                {
                    "at": str(updated),
                    "verdict": "HOLD",
                    "sha": m.group(2) if m else "0" * 40,
                    "method": "merge",
                    "by": by + " (an edited comment)",
                }
            )
            continue
        if m is None:
            continue
        out.append(
            {
                "at": str(c.get("created_at") or ""),
                "verdict": m.group(1),
                "sha": m.group(2),
                "method": m.group(3) or "merge",
                "by": by,
            }
        )
    return sorted(out, key=lambda v: v["at"])


def referenced_by_code(base_ref: str, path: str) -> bool:
    """Does any code file on the base branch name this path or its file name, in any letter case
    (the box checks out on NTFS, where `gap_register.md` IS `GAP_REGISTER.md`)? An error is a
    yes."""
    name = path.rsplit("/", 1)[-1]
    p = subprocess.run(
        [
            "git",
            "grep",
            "-q",
            "-i",
            "-F",
            "-e",
            path,
            "-e",
            name,
            f"origin/{base_ref}",
            "--",
            *CODE_SPECS,
        ],
        capture_output=True,
        check=False,
    )
    return p.returncode != 1  # 0 = found, 1 = not found, anything else = could not look


def protected_patterns() -> tuple[str, ...] | None:
    """The patterns in ops/release/protected_paths.txt; None when it cannot be read."""
    try:
        text = PROTECTED_FILE.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return tuple(
        ln.strip() for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")
    )


def is_protected(name: str, extra: Iterable[str] = ()) -> bool:
    """Case-blind (#455 audit MF2): on the box's NTFS checkout `claude.md` IS `CLAUDE.md`."""
    low = name.lower()
    if low.endswith(DOC_EXTS) and FORCED_LIVE.search(low):
        return True  # a governing document
    return any(fnmatch.fnmatchcase(low, pat.lower()) for pat in (*PROTECTED, *extra))


def tier(
    files: list[Mapping[str, Any]], changed: int, referenced: Callable[[str], bool]
) -> tuple[str, str]:
    """("LOW" | "AUTO" | "PROTECTED", why). The strictest file decides; unsure is PROTECTED."""
    if not files or len(files) != changed or len(files) >= MAX_FILES:
        return "PROTECTED", f"PROTECTED: {len(files)} of {changed} changed files listed"
    extra = protected_patterns()
    if extra is None:
        return "PROTECTED", "PROTECTED: ops/release/protected_paths.txt is unreadable"
    names = [
        (str(n), f) for f in files for n in (f.get("filename"), f.get("previous_filename")) if n
    ]
    for name, _ in names:
        if is_protected(name, extra):
            return "PROTECTED", f"PROTECTED: {name}"
    for name, f in names:
        if (
            name in APPEND_ONLY
            and f.get("status") == "modified"
            and f.get("deletions") == 0
            and not f.get("previous_filename")
        ):
            continue
        if not (name.startswith(LOW_DIRS) and name.lower().endswith(LOW_EXTS)):
            return "AUTO", f"AUTO tier: {name}"
        if FORCED_LIVE.search(name.lower()):
            return "AUTO", f"AUTO tier: {name} (a governing document)"
        if referenced(name):
            return "AUTO", f"AUTO tier: {name} is read by code"
    return "LOW", f"LOW tier: {len(files)} prose file(s) no program reads"


def _zuck_typed(c: Mapping[str, Any]) -> bool:
    """By the OWNER, typed by him (no GitHub App posted it: a Claude session's comment carries
    `performed_via_github_app`) and never edited (an edit could turn an old comment into this)."""
    created = c.get("created_at")
    return (
        str(c.get("author_association") or "") == "OWNER"
        and not c.get("performed_via_github_app")
        and bool(created)
        and c.get("updated_at") in (None, created)
    )


def approval_at(comments: Iterable[Mapping[str, Any]]) -> str | None:
    """When zuck last approved merges: the newest zuck-typed comment that is exactly APPROVE."""
    best: str | None = None
    for c in comments:
        if str(c.get("body") or "").strip() == APPROVE and _zuck_typed(c):
            best = max(best or "", str(c["created_at"]))
    return best


def activated(comments: Iterable[Mapping[str, Any]], phrase: str = ACTIVATE) -> tuple[bool, str]:
    """Is this switch on? The newest of zuck's own `phrase` and any trusted DEACTIVATE decides;
    none at all is off. One DEACTIVATE switches off every switch. Fail safe: any EDITED trusted
    comment on the issue counts as a DEACTIVATE at its edit time (an edit can hide what a comment
    said), and OFF wins a tie. Limit: a DEACTIVATE that is DELETED leaves no trace in the API, so
    deleting one re-enables the switches; deactivate by posting, never by removing an ACTIVATE."""
    last: tuple[str, bool] | None = None
    for c in comments:
        body = str(c.get("body") or "").strip()
        at = str(c.get("created_at") or "")
        trusted = str(c.get("author_association") or "") in TRUSTED
        edited = c.get("updated_at") not in (None, c.get("created_at"))
        if trusted and edited:
            on, at = False, str(c.get("updated_at"))
        elif body == phrase and _zuck_typed(c):
            on = True
        elif body == DEACTIVATE and trusted:
            on = False
        else:
            continue
        if last is None or at > last[0] or (at == last[0] and not on):
            last = (at, on)
    if last is None:
        return False, f"`{phrase}` has not been given (zuck, on #453)"
    return last[1], f"`{phrase}` is {'ON' if last[1] else 'OFF'} since {last[0]}"


def approved(clear: Mapping[str, str], at: str | None) -> tuple[bool, str]:
    """Does zuck's latest approval cover this CLEAR? Only a CLEAR given BEFORE it does."""
    if at is None:
        return False, f"no `{APPROVE}` from zuck on #{APPROVALS_ISSUE} yet"
    if clear["at"] >= at:
        return False, (
            f"the CLEAR ({clear['at']}) came after zuck's latest approval ({at}): "
            "it waits for the next one"
        )
    return True, f"approved by zuck at {at}"


def cleared(
    found: list[dict[str, str]], head: str, same_change: Callable[[str], bool]
) -> tuple[dict[str, str] | None, str]:
    """(the CLEAR that covers `head`, or None; why)."""
    if not found:
        return None, "no AUDIT verdict on this PR yet"
    last = found[-1]
    if last["verdict"] != "CLEAR":
        return None, f"the latest verdict is AUDIT HOLD {last['sha'][:9]} ({last['at']})"
    if last["sha"] == head:
        return last, f"AUDIT CLEAR {head[:9]} by {last['by']} ({last['at']})"
    if same_change(last["sha"]):
        return last, (
            f"AUDIT CLEAR {last['sha'][:9]} carries to head {head[:9]}: the PR's diff "
            "is byte-identical (patch-id)"
        )
    return None, (
        f"the CLEAR is for {last['sha'][:9]}, and head {head[:9]} carries a different "
        "change: it needs its own AUDIT CLEAR"
    )


def _from_ci_app(r: Mapping[str, Any]) -> bool:
    return str((r.get("app") or {}).get("slug") or "") == CI_APP


def checks(
    runs: Iterable[Mapping[str, Any]],
    gating: tuple[str, ...] = GATING_JOBS,
    genuine: Callable[[Mapping[str, Any]], bool] = _from_ci_app,
) -> tuple[str, str]:
    """("pass" | "pending" | "fail", why) over the head's check runs. A job re-run keeps only
    its newest run. A required job counts only from a run `genuine` accepts (by default: posted
    by GitHub Actions; the gate also checks which workflow file made it), so a forged
    same-name success can neither pass a job nor mask a real failure. An AUTO job that is not
    required here is ignored, so the manual path never waits on, or fails by, the AUTO jobs."""
    newest: dict[str, Mapping[str, Any]] = {}
    for r in runs:
        name = str(r.get("name") or "")
        if name in SELF_NAMES or (name in AUTO_JOBS and name not in gating):
            continue
        if name in gating and not genuine(r):
            continue
        prev = newest.get(name)
        if prev is None or str(r.get("started_at") or "") >= str(prev.get("started_at") or ""):
            newest[name] = r
    bad = sorted(
        n
        for n, r in newest.items()
        if r.get("status") == "completed" and r.get("conclusion") not in OK_CONCLUSIONS
    )
    if bad:
        return "fail", "failed: " + ", ".join(f"{n} ({newest[n].get('conclusion')})" for n in bad)
    running = sorted(n for n, r in newest.items() if r.get("status") != "completed")
    missing = [g for g in gating if g not in newest]
    if running or missing:
        return "pending", "waiting on: " + ", ".join(
            running + [f"{g} (not started)" for g in missing]
        )
    not_ok = [g for g in gating if newest[g].get("conclusion") != "success"]
    if not_ok:
        return "fail", "gating jobs did not succeed: " + ", ".join(not_ok)
    return "pass", f"{len(newest)} check run(s) green, gating jobs succeeded"


# ------------------------------------------------------------------------ the GitHub side


def _gh(*args: str, data: Mapping[str, Any] | None = None) -> Any:
    cmd = ["gh", "api", *args]
    if data is not None:
        cmd += ["--input", "-"]
    p = subprocess.run(
        cmd,
        input=json.dumps(data) if data is not None else None,
        capture_output=True,
        text=True,
        check=False,
    )
    if p.returncode != 0:
        raise RuntimeError(f"gh api {' '.join(args)}: {p.stderr.strip()[:300]}")
    return json.loads(p.stdout) if p.stdout.strip() else None


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


def provenance(repo: str, pr: int, head: str) -> Callable[[Mapping[str, Any]], bool]:
    """A `genuine` for checks(): the check run IS a job of a workflow run of the job's own
    workflow file, on this very head, for this PR (or a push of it). The job id must equal the
    check run id: a check run POSTed through the API by some other workflow (#456 audit MF1:
    any same-repo PR can add one with `checks: write`) lands in a suite but is no job of any run.
    Every lookup is cached; one that fails is a no."""
    suites: dict[int, list[Mapping[str, Any]]] = {}
    jobs: dict[int, set[int]] = {}

    def runs_of(sid: int) -> list[Mapping[str, Any]]:
        if sid not in suites:
            try:
                got = _gh(f"repos/{repo}/actions/runs?check_suite_id={sid}&per_page=10")
                suites[sid] = list((got or {}).get("workflow_runs") or [])
            except RuntimeError:
                suites[sid] = []
        return suites[sid]

    def jobs_of(run_id: int) -> set[int]:
        if run_id not in jobs:
            try:
                pages = _gh(
                    f"repos/{repo}/actions/runs/{run_id}/jobs?per_page=100", "--paginate", "--slurp"
                )
                jobs[run_id] = {
                    int(j["id"]) for page in _flat_pages(pages) for j in (page.get("jobs") or [])
                }
            except (RuntimeError, KeyError, TypeError, ValueError):
                jobs[run_id] = set()
        return jobs[run_id]

    def genuine(r: Mapping[str, Any]) -> bool:
        want = WORKFLOW_OF.get(str(r.get("name") or ""))
        sid = (r.get("check_suite") or {}).get("id")
        rid = r.get("id")
        if not want or not _from_ci_app(r) or not isinstance(sid, int) or not isinstance(rid, int):
            return False
        for w in runs_of(sid):
            if str(w.get("path") or "") != want or str(w.get("head_sha") or "") != head:
                continue
            event = str(w.get("event") or "")
            prs = {int(x.get("number") or 0) for x in (w.get("pull_requests") or [])}
            if not (event == "push" or (event == "pull_request" and pr in prs)):
                continue
            if isinstance(w.get("id"), int) and rid in jobs_of(int(w["id"])):
                return True
        return False

    return genuine


def up_to_date(base_ref: str, head: str) -> tuple[bool, str]:
    """May a no-comment path test-and-merge this head? Only when the head already contains the
    base's tip (#456 audit MF3: otherwise the tree that merges, base + PR, was never tested) and
    carries exactly the base's .github (#455 audit MF1: a stale branch runs older checks under
    the same job names). Any git error is a no."""
    try:
        _git("fetch", "-q", "--no-tags", "origin", base_ref)
        _git("fetch", "-q", "--no-tags", "origin", head)
    except subprocess.CalledProcessError:
        return False, "the head or the base could not be fetched"
    behind = subprocess.run(
        ["git", "merge-base", "--is-ancestor", f"origin/{base_ref}", head],
        capture_output=True,
        check=False,
    )
    if behind.returncode != 0:
        return False, f"it is behind {base_ref} (merge {base_ref} in first)"
    same = subprocess.run(
        ["git", "diff", "--quiet", f"origin/{base_ref}", head, "--", ".github"],
        capture_output=True,
        check=False,
    )
    if same.returncode != 0:
        return False, f"its .github differs from {base_ref}"
    return True, "up to date"


def queued_review(
    repo: str,
    runs: Iterable[Mapping[str, Any]],
    genuine: Callable[[Mapping[str, Any]], bool],
) -> Mapping[str, Any] | None:
    """The head's newest genuine independent-review run when it ended UNAVAILABLE (no free
    model answered), else None. Only the job's own annotation says so: its steps run the base's
    script, so a PR cannot write it, and a real FAIL never carries it."""
    newest: Mapping[str, Any] | None = None
    for r in runs:
        later = newest is None or str(r.get("started_at") or "") >= str(
            newest.get("started_at") or ""
        )
        if str(r.get("name") or "") == REVIEWER and later and genuine(r):
            newest = r
    if newest is None or newest.get("status") != "completed":
        return None
    if newest.get("conclusion") != "failure":
        return None
    try:
        notes = _gh(f"repos/{repo}/check-runs/{newest['id']}/annotations?per_page=100")
    except RuntimeError:
        return None
    marked = any(str(a.get("title") or "") == UNAVAILABLE_MARK for a in notes or [])
    return newest if marked else None


def requeue(repo: str, review: Mapping[str, Any], now: float | None = None) -> str:
    """Ask GitHub to re-run a queued review once its last attempt is RETRY_AFTER_S old."""
    done = str(review.get("completed_at") or "")
    try:
        age = (now or time.time()) - datetime.fromisoformat(done.replace("Z", "+00:00")).timestamp()
    except ValueError:
        age = RETRY_AFTER_S
    if age < RETRY_AFTER_S:
        return f"re-run due in {int((RETRY_AFTER_S - age) // 60) + 1} min"
    try:
        job = _gh(f"repos/{repo}/actions/jobs/{review['id']}")
        attempt = int((job or {}).get("run_attempt") or 0)
        if attempt >= MAX_ATTEMPTS:
            return f"{attempt} attempts and no free reviewer: still queued, never bypassed"
        _gh(f"repos/{repo}/actions/jobs/{review['id']}/rerun", "-X", "POST")
    except (RuntimeError, TypeError, ValueError) as exc:
        return f"re-run not requested ({exc})"
    return f"re-run requested (attempt {attempt + 1})"


def patch_id(base_ref: str, sha: str) -> str | None:
    """The identity of the PR's own change at `sha`: sha256 of the exact bytes of its diff from
    the merge-base with the base branch. None when the commit cannot be fetched or diffed.

    BYTES, NOT `git patch-id` (#445 audit MF1): `--stable` hashes with all whitespace removed,
    so moving a Python `return` into an `if` kept the id and would have carried a CLEAR to a
    different program. Exact bytes are conservative: a merge-in of LIVE that shifts the
    context or the pre-image of a file the PR touches also changes them, and needs a new CLEAR.
    No external diff or textconv driver is run."""
    try:
        _git("fetch", "-q", "--no-tags", "origin", sha)
        mb = _git("merge-base", f"origin/{base_ref}", sha)
        diff = subprocess.run(
            [
                "git",
                "diff",
                "--binary",
                "--full-index",
                "--no-ext-diff",
                "--no-textconv",
                "--no-renames",
                mb,
                sha,
            ],
            capture_output=True,
            check=True,
        ).stdout
        return hashlib.sha256(diff).hexdigest()
    except subprocess.CalledProcessError:
        return None


def _flat_pages(pages: Any) -> list[Any]:
    """`gh api --paginate --slurp` gives a list of pages; a single page is a list of one."""
    if isinstance(pages, list):
        return pages
    return [pages] if pages else []


def _flat(pages: Any) -> list[Any]:
    """The items of every page of a paginated list endpoint."""
    return [c for page in _flat_pages(pages) for c in (page if isinstance(page, list) else [])]


def _summary(line: str) -> None:
    print(line)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def _status(repo: str, sha: str, state: str, why: str) -> None:
    try:
        _gh(
            f"repos/{repo}/statuses/{sha}",
            "-X",
            "POST",
            data={"state": state, "context": STATUS_CONTEXT, "description": why[:139]},
        )
    except RuntimeError as exc:
        _summary(f"(status not posted: {exc})")


def touches_workflows(files: Iterable[Mapping[str, Any]]) -> bool:
    """True when the PR changes .github/workflows/** (a rename counts from either side)."""
    for f in files:
        for name in (f.get("filename"), f.get("previous_filename")):
            if isinstance(name, str) and name.startswith(WORKFLOW_DIR):
                return True
    return False


def run(
    repo: str,
    pr: int,
    base: str,
    wait_min: float,
    poll_s: float = 60.0,
    box: bool = False,
    approvals_issue: int = APPROVALS_ISSUE,
) -> int:
    """Merge #pr when the rule holds. `box`: the box's run with a user token -- it needs no label,
    merges workflow-file PRs too (the Actions run, box=False, leaves those to it), posts no
    pending status and dispatches nothing."""
    p = _gh(f"repos/{repo}/pulls/{pr}")
    head = str(p["head"]["sha"])
    if p.get("state") != "open":
        _summary(f"#{pr} is {p.get('state')}: nothing to do")
        return 0
    if p["base"]["ref"] != base:
        _summary(f"#{pr} targets {p['base']['ref']}, not {base}: the gate does not merge it")
        return 0
    if (p["head"].get("repo") or {}).get("full_name") != repo:
        _summary(f"#{pr} comes from a fork: never merged by the gate")
        return 0
    files = _flat(_gh(f"repos/{repo}/pulls/{pr}/files?per_page=100", "--paginate", "--slurp"))
    p2 = _gh(f"repos/{repo}/pulls/{pr}")
    if str(p2["head"]["sha"]) != head:
        _summary(f"#{pr}: head moved while its files were read; the next run decides")
        return 0
    level, twhy = tier(
        files, int(p2.get("changed_files") or 0), lambda n: referenced_by_code(base, n)
    )

    def switches() -> tuple[bool, str]:
        board = _flat(
            _gh(
                f"repos/{repo}/issues/{approvals_issue}/comments?per_page=100",
                "--paginate",
                "--slurp",
            )
        )
        on, owhy = activated(board)
        if on and level == "AUTO":
            on, owhy = activated(board, ACTIVATE_AUTO)
        return on, owhy

    def pr_verdicts() -> list[dict[str, str]]:
        pages = _gh(f"repos/{repo}/issues/{pr}/comments?per_page=100", "--paginate", "--slurp")
        return verdicts(_flat(pages))

    # The path a PR takes: "low" / "auto" (no comment needed) or "manual" (CLEAR + APPROVE).
    # Once the auditor has spoken on a PR (any CLEAR or HOLD, on any sha), the audit governs it:
    # it takes the manual path.
    mode = "manual"
    if level in ("LOW", "AUTO"):
        on, owhy = switches()
        if not on:
            twhy = f"{twhy}, but {owhy}: it takes the CLEAR + APPROVE path"
        elif pr_verdicts():
            twhy = f"{twhy}, but it carries an AUDIT verdict: it takes the CLEAR + APPROVE path"
        else:
            fresh, fwhy = up_to_date(base, head)
            if fresh:
                mode = level.lower()
            else:
                twhy = f"{twhy}, but {fwhy}: it takes the CLEAR + APPROVE path"
    low = mode != "manual"  # no verdict or approval needed on this path
    required = GATING_JOBS + (AUTO_JOBS if mode == "auto" else ())
    _summary(f"#{pr} @ {head[:9]}: {twhy}")
    wf = touches_workflows(files)
    if wf and not box:
        _status(repo, head, "pending", BOX_MERGES)
        _summary(f"#{pr} @ {head[:9]}: {BOX_MERGES}")
        return 0
    # The label only STARTS a run; it is taken off so the next CLEAR can put it back on (adding
    # a label a PR already carries starts nothing). A removal by the workflow token starts no run.
    if not box and any(lb.get("name") == LABEL for lb in p.get("labels") or []):
        try:
            _gh(f"repos/{repo}/issues/{pr}/labels/{LABEL}", "-X", "DELETE")
        except RuntimeError as exc:
            _summary(f"(label not removed: {exc})")
    # The head's own diff identity, computed only when a CLEAR names another sha (a sweep looks
    # at every open PR, most of which carry no verdict at all).
    ids: dict[str, str | None] = {}

    def same_change(sha: str) -> bool:
        if "head" not in ids:
            ids["head"] = patch_id(base, head)
        return ids["head"] is not None and patch_id(base, sha) == ids["head"]

    def verdict_now() -> tuple[dict[str, str] | None, str]:
        found = pr_verdicts()
        if low:
            if found:  # the auditor spoke mid-run: the next run takes the manual path
                return None, f"{twhy}, but an AUDIT verdict arrived: the audit governs it now"
            on, owhy = switches()  # a DEACTIVATE since the first read is honoured
            if not on:
                return None, f"{twhy}, but {owhy}"
            fresh, fwhy = up_to_date(base, head)  # LIVE may have moved: the merged tree
            if not fresh:  # must still be the tested one
                return None, f"{twhy}, but {fwhy}"
            return {"verdict": mode.upper(), "sha": head, "method": "merge", "at": "", "by": ""}, (
                twhy
            )
        clear, why = cleared(found, head, same_change)
        if clear is None:
            return None, why
        ap = _gh(
            f"repos/{repo}/issues/{approvals_issue}/comments?per_page=100", "--paginate", "--slurp"
        )
        ok, awhy = approved(clear, approval_at(_flat(ap)))
        return (clear if ok else None), f"{why}; {awhy}"

    clear, why = verdict_now()
    if clear is None:
        if not box:
            _status(repo, head, "pending", why)
        _summary(f"#{pr} @ {head[:9]}: not merged -- {why}")
        return 0
    _status(repo, head, "success", why)
    _summary(f"#{pr} @ {head[:9]}: {why}")
    deadline = time.monotonic() + wait_min * 60
    while True:
        now_head = str(_gh(f"repos/{repo}/pulls/{pr}")["head"]["sha"])
        if now_head != head:
            _summary(f"#{pr}: head moved to {now_head[:9]}; its own run decides")
            return 0
        # A HOLD posted while CI runs stops the merge (#445 audit MF2): the verdict is re-read on
        # every poll, and once more right before the merge below.
        clear, why = verdict_now()
        if clear is None:
            _status(repo, head, "pending", why)
            _summary(f"#{pr} @ {head[:9]}: not merged -- the verdict changed: {why}")
            return 0
        pages = _gh(f"repos/{repo}/commits/{head}/check-runs?per_page=100", "--paginate", "--slurp")
        runs = [r for page in _flat_pages(pages) for r in (page.get("check_runs") or [])]
        genuine = provenance(repo, pr, head) if low else _from_ci_app
        state, cwhy = checks(runs, required, genuine)
        if state == "pass":
            break
        if state == "fail" and REVIEWER in required:
            review = queued_review(repo, runs, genuine)
            rest = [r for r in runs if r is not review]
            if review is not None and checks(rest, required, genuine)[0] != "fail":
                # no free reviewer answered: QUEUED, never a pass and never a quarantine
                qwhy = f"{REVIEWER} queued: no free reviewer answered; {requeue(repo, review)}"
                _status(repo, head, "pending", qwhy)
                _summary(f"#{pr} @ {head[:9]}: not merged -- {qwhy}")
                return 0
        if state == "fail":
            _summary(f"#{pr} @ {head[:9]}: not merged -- CI {cwhy}")
            if low:  # the no-comment paths quarantine a failure; the manual path reports it
                _status(repo, head, "failure", f"{QUARANTINE}: CI {cwhy}")
                try:
                    _gh(f"repos/{repo}/issues/{pr}/labels", "-X", "POST",
                        data={"labels": [QUARANTINE]})  # fmt: skip
                except RuntimeError as exc:
                    _summary(f"(quarantine label not added: {exc})")
            return 1
        if box or low:  # a LOW-tier PR never holds a runner: the box sweep looks again
            _summary(f"#{pr} @ {head[:9]}: CI {cwhy}; the next sweep looks again")
            return 0
        if time.monotonic() > deadline:
            _summary(f"#{pr} @ {head[:9]}: gave up after {wait_min:.0f} min -- {cwhy}")
            return 1
        time.sleep(poll_s)
    _summary(f"#{pr} @ {head[:9]}: CI {cwhy}")
    clear, why = verdict_now()
    if clear is None:
        _status(repo, head, "pending", why)
        _summary(f"#{pr} @ {head[:9]}: not merged -- the verdict changed: {why}")
        return 0
    if low and any(lb.get("name") == QUARANTINE for lb in p.get("labels") or []):
        try:  # a new head passed: the quarantine of an older one is lifted
            _gh(f"repos/{repo}/issues/{pr}/labels/{QUARANTINE}", "-X", "DELETE")
        except RuntimeError as exc:
            _summary(f"(quarantine label not removed: {exc})")
    if p.get("draft"):
        subprocess.run(["gh", "pr", "ready", str(pr), "-R", repo], check=True)
    _gh(
        f"repos/{repo}/pulls/{pr}/merge",
        "-X",
        "PUT",
        data={
            "sha": head,
            "merge_method": clear["method"],
            "commit_title": (
                f"Merge #{pr} ({mode.upper()} tier, no comment: {twhy})"[:250]
                if clear["verdict"] == mode.upper()
                else f"Merge #{pr} ({clear['method']}): audit CLEAR {clear['sha'][:9]}"
            ),
        },
    )
    _summary(f"#{pr} @ {head[:9]}: MERGED ({clear['method']}){' from the box' if box else ''}")
    if box:
        return 0  # a user-token merge starts the push run on LIVE by itself
    # A merge made with the workflow token starts no push run: dispatch ci.yml on the base so
    # its seal and promote jobs see the merged code.
    _gh(f"repos/{repo}/actions/workflows/ci.yml/dispatches", "-X", "POST", data={"ref": base})
    _summary(f"dispatched ci.yml on {base}")
    return 0


def sweep(repo: str, base: str, approvals_issue: int = APPROVALS_ISSUE) -> int:
    """The box's pass: every open PR into `base` gets one box-mode run (forks are refused inside).
    One PR's failure never stops the others; the worst exit code is returned."""
    pages = _gh(f"repos/{repo}/pulls?state=open&base={base}&per_page=100", "--paginate", "--slurp")
    rc = 0
    for p in _flat(pages):
        n = int(p["number"])
        try:
            rc = max(rc, run(repo, n, base, 0.0, box=True, approvals_issue=approvals_issue))
        except (RuntimeError, subprocess.CalledProcessError) as exc:
            _summary(f"#{n}: the box gate failed: {exc}")
            rc = 1
    return rc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--pr", type=int)
    ap.add_argument("--base", default=LIVE)
    ap.add_argument("--wait-min", type=float, default=300.0)
    ap.add_argument("--box", action="store_true", help="the box's run: no label, workflow PRs too")
    ap.add_argument("--sweep", action="store_true", help="every open PR into --base (with --box)")
    ap.add_argument("--approvals-issue", type=int, default=APPROVALS_ISSUE)
    a = ap.parse_args(argv)
    if a.sweep:
        if not a.box:
            ap.error("--sweep is the box's pass: give --box too")
        return sweep(a.repo, a.base, a.approvals_issue)
    if a.pr is None:
        ap.error("--pr or --sweep is required")
    try:
        return run(
            a.repo,
            a.pr,
            a.base,
            0.0 if a.box else a.wait_min,
            box=a.box,
            approvals_issue=a.approvals_issue,
        )
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        _summary(f"#{a.pr}: the gate failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
