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

Then the gate marks a draft ready, merges through the REST API PINNED TO THE HEAD SHA (GitHub
refuses the merge if the head moved), and dispatches ci.yml on LIVE: a merge made with the
workflow token starts no push run, so without the dispatch the seal and promote jobs would never
see the merged code.

    python .github/scripts/audit_gate.py --repo OWNER/NAME --pr N [--base LIVE] [--wait-min 300]

WORKFLOW-FILE PRs. A PR that changes .github/workflows/** -- this gate's own fixes included --
is refused by GitHub for the workflow token (it holds no `workflows` permission). The Actions run
therefore leaves such a PR alone (status "pending: the box merges this") and the BOX merges it
under the SAME rule, with zuck's own gh token (which carries the `workflow` scope):

    python scripts/audit_gate.py --repo OWNER/NAME --sweep --box

run every 10 minutes by ops/box/workflow_gate.ps1 from a clean checkout of LIVE (trusted code,
never the PR's). The box mode merges ONLY workflow-file PRs, never waits (a PR whose CI is still
running is left for the next sweep), and dispatches nothing: a merge made with a user token
starts the normal push run on LIVE.

Exit 0 when merged or when there is honestly nothing to do yet (no CLEAR); exit 1 when the gate
refused or gave up, with the reason in the job summary and on the `audit/clear` commit status.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable, Iterable, Mapping
from typing import Any

LIVE = "claude/llm-auto-upgrade-verify-gcjac3"
#: The CI jobs that gate a merge (ci.yml). Each must have a SUCCESS run on the head.
GATING_JOBS = ("quality", "mt5-money-path", "coverage-floor")
#: Who may post a verdict (GitHub's author_association).
TRUSTED = ("OWNER", "MEMBER", "COLLABORATOR")
STATUS_CONTEXT = "audit/clear"
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


def checks(
    runs: Iterable[Mapping[str, Any]], gating: tuple[str, ...] = GATING_JOBS
) -> tuple[str, str]:
    """("pass" | "pending" | "fail", why) over the head's check runs. A job re-run keeps only
    its newest run."""
    newest: dict[str, Mapping[str, Any]] = {}
    for r in runs:
        name = str(r.get("name") or "")
        if name in SELF_NAMES:
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
) -> int:
    """Merge #pr when the rule holds. `box`: the box's run with a user token -- it merges ONLY
    workflow-file PRs, which the Actions run (box=False) leaves to it, and dispatches nothing."""
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
    wf = touches_workflows(files)
    if wf and not box:
        _status(repo, head, "pending", BOX_MERGES)
        _summary(f"#{pr} @ {head[:9]}: {BOX_MERGES}")
        return 0
    if box and not wf:
        _summary(f"#{pr}: no workflow change; the Actions gate merges it")
        return 0
    # The label only STARTS a run; it is taken off so the next CLEAR can put it back on (adding
    # a label a PR already carries starts nothing). A removal by the workflow token starts no run.
    if not box and any(lb.get("name") == LABEL for lb in p.get("labels") or []):
        try:
            _gh(f"repos/{repo}/issues/{pr}/labels/{LABEL}", "-X", "DELETE")
        except RuntimeError as exc:
            _summary(f"(label not removed: {exc})")
    head_id = patch_id(base, head)

    def verdict_now() -> tuple[dict[str, str] | None, str]:
        pages = _gh(f"repos/{repo}/issues/{pr}/comments?per_page=100", "--paginate", "--slurp")
        return cleared(
            verdicts(_flat(pages)),
            head,
            lambda sha: head_id is not None and patch_id(base, sha) == head_id,
        )

    clear, why = verdict_now()
    if clear is None:
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
        state, cwhy = checks(runs)
        if state == "pass":
            break
        if state == "fail":
            _summary(f"#{pr} @ {head[:9]}: not merged -- CI {cwhy}")
            return 1
        if box:
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
    if p.get("draft"):
        subprocess.run(["gh", "pr", "ready", str(pr), "-R", repo], check=True)
    _gh(
        f"repos/{repo}/pulls/{pr}/merge",
        "-X",
        "PUT",
        data={
            "sha": head,
            "merge_method": clear["method"],
            "commit_title": f"Merge #{pr} ({clear['method']}): audit CLEAR {clear['sha'][:9]}",
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


def sweep(repo: str, base: str) -> int:
    """The box's pass: every open, non-fork PR into `base` that changes workflow files gets one
    box-mode run. One PR's failure never stops the others; the worst exit code is returned."""
    pages = _gh(f"repos/{repo}/pulls?state=open&base={base}&per_page=100", "--paginate", "--slurp")
    rc = 0
    for p in _flat(pages):
        n = int(p["number"])
        try:
            rc = max(rc, run(repo, n, base, 0.0, box=True))
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
    ap.add_argument("--box", action="store_true", help="the box's run: workflow-file PRs only")
    ap.add_argument("--sweep", action="store_true", help="every open PR into --base (with --box)")
    a = ap.parse_args(argv)
    if a.sweep:
        if not a.box:
            ap.error("--sweep is the box's pass: give --box too")
        return sweep(a.repo, a.base)
    if a.pr is None:
        ap.error("--pr or --sweep is required")
    try:
        return run(a.repo, a.pr, a.base, 0.0 if a.box else a.wait_min, box=a.box)
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        _summary(f"#{a.pr}: the gate failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
