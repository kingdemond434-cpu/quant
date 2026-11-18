"""MERGE PIPELINE LIVENESS: is approved work reaching LIVE, and if not, which stage holds it?

    python scripts/merge_pipeline_watch.py --repo OWNER/NAME          # writes the report, rc 2 on RED
    python scripts/merge_pipeline_watch.py --repo OWNER/NAME --print  # stdout only

Writes desks/mt5/reports/MERGE_PIPELINE.json (box state, published with the box's state commits).

THE CLASS THIS CLOSES (measured 2026-10-29). From 14:05Z to past 17:51Z nothing but box state
reached LIVE. zuck had approved #462, #498 and #439 at ~16:11Z, and the urgent FTMO fix #516 had
its checks QUEUED from 16:03Z. Every organ was green: each PR's checks just said "queued", which
is not a failure, so nothing went RED. The cause was a runner backlog (189 runs queued against
the free plan's job limit, the oldest from 14:05Z), made worse by gates that held runners while
they waited and by a full LIVE CI run for every 15-min state publish. "Queued" with no clock is
silence. This report puts a clock on every stage:

    queue        runs queued / in progress for the repo, the oldest queued age, and how many of
                 them test a head that has since moved (waste: they can never count)
    prs          per open PR into LIVE: the oldest queued check on its CURRENT head, its age,
                 whether a trusted AUDIT CLEAR names that head, and how long ago
    live         hours since the last CODE commit on LIVE (box state and seal commits excluded)

RED when any of these holds:
    CI_QUEUED       a check on a PR's current head has been queued over 30 min
    CLEAR_WAITING   a head with a trusted AUDIT CLEAR is still open 2 h after the CLEAR
    LIVE_STALLED    no code commit on LIVE for 6 h while any PR holds a CLEAR
    REVIEWER_FP     over half of (3+) open heads the independent reviewer FAILed carry an
                    Auditor CLEAR: the reviewer is blocking what the audit passed
    LIVE_CI_QUEUED  a push run on LIVE itself has been queued over 30 min: the box cannot adopt
                    (Adopt-And-Seal waits for green) and the gate cannot see LIVE green
    NO_MERGE_24H    no PR merged into LIVE for 24 h while an open PR's gating jobs (quality,
                    mt5-money-path, coverage-floor) are green on its head (10-30 to 11-03: four
                    days with nothing merged, and every rule above stayed quiet, because no CLEAR
                    sat on a PR comment and the AUTO path never went fully green)
    SIGN_TRAIN_*    the sign train's heartbeat (logs/sign_train.json) is unread, over 30 min old,
                    failed past two runs in a row, found its mutex held past two (#541 MF3), or
                    has waited on one open sign PR over 2 h

BOUNDED (2026-11-13). The watcher read every open PR one by one, two gh calls each, with no clock
on any call. At 652 open PRs that is about 1,300 calls, over the box sweep's 30-min task limit, so
Task Scheduler killed the sweep mid-watch every run and the report went stale (zuck: "the status
reporter's underlying hang"). Now every gh call has a timeout, the CLEARs come from one repo-wide
comment listing (about 10 calls), and per-PR check reads run most-important first (ready PRs,
CLEARed heads, heads with queued runs) inside a time budget. What the budget left unread is
counted in "coverage"; a priority PR left unread is WATCH_PARTIAL (RED), the rest is not.

Read-only on GitHub: it never cancels, re-runs, comments or merges. What to do about a RED is
the owner's call (Autonomy thread), and the report names the stage so the call is quick.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LIVE = "claude/llm-auto-upgrade-verify-gcjac3"
REPORT = ROOT / "desks" / "mt5" / "reports" / "MERGE_PIPELINE.json"
QUEUED_RED_MIN = 30.0
CLEAR_RED_H = 2.0
LIVE_RED_H = 6.0
NO_MERGE_RED_H = 24.0
GATING = ("quality", "mt5-money-path", "coverage-floor")
#: REVIEWER_FP: of the open heads the independent reviewer FAILed, the share an Auditor CLEARed
#: (the human-grade audit read the same head and found nothing): a proxy false-positive rate.
REVIEWER_FP_MIN_FAILS = 3
REVIEWER_FP_RED = 0.5
REVIEWER = "independent-review"
#: Every check a no-comment merge needs (audit_gate GATING_JOBS + AUTO_JOBS).
ALL_CHECKS = (
    "quality", "mt5-money-path", "coverage-floor",
    "risk-invariants", "replay-shadow", "independent-review",
)  # fmt: skip
GATE_STATUS = "audit/clear"
SWEEP_STALE_MIN = 30.0
SWEEP_WEDGED_RUNS = 2
TRUSTED = ("OWNER", "MEMBER", "COLLABORATOR")
#: Matched with ALL whitespace removed: zuck's CLEARs arrive with the sha wrapped over lines.
CLEAR_RE = re.compile(r"AUDITCLEAR([0-9a-f]{7,40})", re.I)
#: Commits on LIVE that carry no code: the box's state publishes and CI's own seal commits.
NOT_CODE_RE = re.compile(r"^(mt5 box state|seal release)\b", re.I)
#: One gh call never waits longer than this (the hang that held the gate's mutex, 11-13).
GH_TIMEOUT_S = 45.0
#: The whole read stays inside this, far under the sweep task's 30-min limit.
BUDGET_S = 300.0
#: CLEARs older than this name heads that have long since moved (the listing's `since`).
CLEAR_LOOKBACK_D = 30
CLEAR_PAGES = 40


def _streak(v: Any) -> int:
    """A beat's run counter; anything that is not a whole number reads as past the RED bar."""
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return SWEEP_WEDGED_RUNS + 1


def _ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _age_min(now: datetime, s: str | None) -> float | None:
    t = _ts(s)
    return None if t is None else round((now - t).total_seconds() / 60.0, 1)


def clear_at(comments: Iterable[Mapping[str, Any]], head: str) -> str | None:
    """When a trusted, unedited AUDIT CLEAR last named `head` (a prefix of 7+ hex is a name)."""
    at = None
    for c in comments:
        if c.get("author_association") not in TRUSTED:
            continue
        if c.get("updated_at") and c.get("updated_at") != c.get("created_at"):
            continue  # an edited verdict is not a CLEAR (the gate's own rule)
        m = CLEAR_RE.match(re.sub(r"\s+", "", str(c.get("body") or "")))
        if m and head.startswith(m.group(1).lower()):
            at = c.get("created_at")
    return at


def assess(
    now: datetime,
    prs: list[Mapping[str, Any]],
    checks: Mapping[str, list[Mapping[str, Any]]],
    clears: Mapping[int, str | None],
    queued_runs: list[Mapping[str, Any]],
    running: int,
    live_commits: list[Mapping[str, Any]],
    ready: Mapping[int, str] | None = None,
    beat: Mapping[str, Any] | None = None,
    beat_expected: bool = False,
    sign_beat: Mapping[str, Any] | None = None,
    sign_expected: bool = False,
    base: str = LIVE,
    merged: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """The report, from already-fetched data (pure: the tests drive this). `ready`: PR -> when
    its last required check went green, for heads the gate has marked mergeable (audit/clear
    success). `beat`: the box sweep's heartbeat (logs/workflow_gate.json), when it is read.
    `merged`: recently closed PRs into the base (None: not read, so NO_MERGE_24H is not judged)."""
    ready = ready or {}
    heads = {str(p["head"]["ref"]): str(p["head"]["sha"]) for p in prs}
    stale = [
        r
        for r in queued_runs
        if r.get("event") in ("pull_request", "pull_request_target")
        and str(r.get("head_branch")) in heads
        and str(r.get("head_sha")) != heads[str(r.get("head_branch"))]
    ]
    oldest = min((str(r.get("created_at")) for r in queued_runs), default=None)
    red: list[str] = []
    rows = []
    for p in prs:
        n, head = int(p["number"]), str(p["head"]["sha"])
        q = [c for c in checks.get(head, []) if c.get("status") in ("queued", "waiting", "pending")]
        # a queued check run's started_at is its creation (GitHub sets it at queue time)
        ages = [a for a in (_age_min(now, c.get("started_at")) for c in q) if a is not None]
        qmax = max(ages, default=None)
        cat = clears.get(n)
        cage = _age_min(now, cat)
        rat = ready.get(n)
        rage = _age_min(now, rat)
        review = next(
            (c.get("conclusion") for c in checks.get(head, []) if c.get("name") == REVIEWER), None
        )
        rows.append(
            {
                "pr": n,
                "head": head[:9],
                "draft": bool(p.get("draft")),
                "queued_checks": sorted(str(c.get("name")) for c in q),
                "oldest_queued_min": qmax,
                "clear_at": cat,
                "clear_age_h": None if cage is None else round(cage / 60.0, 2),
                "review": review,
                "gating_green": all(
                    any(
                        c.get("name") == k and c.get("conclusion") == "success"
                        for c in checks.get(head, [])
                    )
                    for k in GATING
                ),
                "green_since": rat,
            }
        )
        if qmax is not None and qmax > QUEUED_RED_MIN:
            red.append(f"CI_QUEUED #{n}: a check queued {qmax:.0f} min on {head[:9]}")
        if cage is not None and cage / 60.0 > CLEAR_RED_H:
            red.append(f"CLEAR_WAITING #{n}: CLEARed {cage / 60.0:.1f} h ago, still open")
        if rage is not None and rage / 60.0 > CLEAR_RED_H:  # how #516 sat: green, eligible, open
            red.append(f"GREEN_WAITING #{n}: mergeable and green {rage / 60.0:.1f} h, still open")
    fails = [r for r in rows if r["review"] == "failure"]
    fp = [r["pr"] for r in fails if r["clear_at"]]
    fp_rate = round(len(fp) / len(fails), 2) if fails else None
    if len(fails) >= REVIEWER_FP_MIN_FAILS and fp_rate is not None and fp_rate > REVIEWER_FP_RED:
        red.append(
            f"REVIEWER_FP: {len(fp)} of {len(fails)} reviewer FAILs carry an Auditor CLEAR "
            f"({', '.join(f'#{n}' for n in fp[:8])})"
        )
    code = next(
        (c for c in live_commits if not NOT_CODE_RE.match(str(c["commit"]["message"]))), None
    )
    code_at = None if code is None else code["commit"]["committer"]["date"]
    code_age = _age_min(now, code_at)
    waiting = any(r["clear_at"] or r["green_since"] for r in rows)
    if waiting and (code_age is None or code_age / 60.0 > LIVE_RED_H):
        hours = "an unknown number of" if code_age is None else f"{code_age / 60.0:.1f}"
        red.append(f"LIVE_STALLED: no code on LIVE for {hours} h while mergeable work waits")
    last_merge = max(
        (str(m["merged_at"]) for m in merged or [] if m.get("merged_at")), default=None
    )
    merge_age = _age_min(now, last_merge)
    green = [r["pr"] for r in rows if r["gating_green"]]
    if merged is not None and green and (merge_age is None or merge_age / 60.0 > NO_MERGE_RED_H):
        hours = "over the read window's" if merge_age is None else f"{merge_age / 60.0:.1f}"
        red.append(
            f"NO_MERGE_24H: no PR merged into LIVE for {hours} h while {len(green)} open "
            f"PR(s) are green on the gating jobs ({', '.join(f'#{n}' for n in green[:8])})"
        )
    live_q = [
        a
        for a in (
            _age_min(now, str(r.get("created_at")))
            for r in queued_runs
            if r.get("event") == "push" and str(r.get("head_branch")) == base
        )
        if a is not None
    ]
    if live_q and max(live_q) > QUEUED_RED_MIN:
        red.append(f"LIVE_CI_QUEUED: a push run on LIVE queued {max(live_q):.0f} min")
    sign: dict[str, Any] | None = None
    if sign_expected:
        if not sign_beat:
            red.append("SIGN_TRAIN_BLIND: the sign train's heartbeat could not be read")
        else:
            sage = _age_min(now, str(sign_beat.get("at") or ""))
            sfails = _streak(sign_beat.get("fail_runs"))
            sheld = _streak(sign_beat.get("mutex_held_runs"))
            sign = {"at": sign_beat.get("at"), "age_min": sage, "rc": sign_beat.get("rc"),
                    "note": sign_beat.get("note"), "fail_runs": sfails,
                    "mutex_held_runs": sheld}  # fmt: skip
            if sage is None or sage > SWEEP_STALE_MIN:
                red.append(f"SIGN_TRAIN_STALE: the sign train last beat {sage} min ago")
            if sfails > SWEEP_WEDGED_RUNS:
                red.append(f"SIGN_TRAIN_FAILING: {sfails} runs in a row failed")
            if sheld > SWEEP_WEDGED_RUNS:
                red.append(f"SIGN_TRAIN_WEDGED: its mutex refused {sheld} runs in a row")
            wage = _age_min(now, str(sign_beat.get("waiting_since") or ""))
            sign["waiting_on"], sign["waiting_min"] = sign_beat.get("waiting_on"), wage
            if sign_beat.get("waiting_on") and wage is None:  # a wait nobody can time
                red.append(f"SIGN_TRAIN_WAITING: {sign_beat.get('waiting_on')} has no readable "
                           "waiting_since")  # fmt: skip
            if wage is not None and wage / 60.0 > CLEAR_RED_H:  # a sign PR open, never merged
                red.append(f"SIGN_TRAIN_WAITING: {sign_beat.get('waiting_on')} open "
                           f"{wage / 60.0:.1f} h")  # fmt: skip
    sweep: dict[str, Any] | None = None
    if beat_expected:
        if not beat:
            red.append("SWEEP_BLIND: the box sweep's heartbeat could not be read")
        else:
            bage = _age_min(now, str(beat.get("at") or ""))
            held = _streak(beat.get("mutex_held_runs"))
            sweep = {"at": beat.get("at"), "age_min": bage, "rc": beat.get("rc"),
                     "note": beat.get("note"), "mutex_held_runs": held}  # fmt: skip
            if bage is None or bage > SWEEP_STALE_MIN:
                red.append(f"SWEEP_STALE: the box sweep last beat {bage} min ago")
            if held > SWEEP_WEDGED_RUNS:
                red.append(f"SWEEP_WEDGED: the sweep's mutex refused {held} runs in a row")
    return {
        "at": now.isoformat(timespec="seconds"),
        "status": "RED" if red else "GREEN",
        "red": red,
        "queue": {
            "queued_runs": len(queued_runs),
            "in_progress_runs": running,
            "oldest_queued_min": _age_min(now, oldest),
            "superseded_queued_runs": len(stale),
            "superseded_run_ids": [r.get("id") for r in stale][:50],
        },
        "reviewer": {"fails": len(fails), "cleared_fails": fp, "fp_rate": fp_rate},
        "sweep": sweep,
        "sign_train": sign,
        "live": {
            "last_code_commit": None if code is None else str(code["sha"])[:9],
            "last_code_at": code_at,
            "hours_since_code": None if code_age is None else round(code_age / 60.0, 2),
            "last_merge_at": last_merge,
            "hours_since_merge": None if merge_age is None else round(merge_age / 60.0, 2),
        },
        "prs": sorted(rows, key=lambda r: -(r["oldest_queued_min"] or 0.0)),
        "thresholds": {
            "queued_red_min": QUEUED_RED_MIN,
            "clear_red_h": CLEAR_RED_H,
            "live_red_h": LIVE_RED_H,
            "no_merge_red_h": NO_MERGE_RED_H,
        },
    }


def _gh(path: str, timeout: float = GH_TIMEOUT_S) -> Any:
    gh = os.environ.get("GH_BIN") or "gh"
    try:
        p = subprocess.run(
            [gh, "api", path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout,  # subprocess.run kills the gh child when it expires
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"gh api {path}: timed out after {exc.timeout}s") from exc
    if p.returncode != 0:
        raise RuntimeError(f"gh api {path}: {p.stderr.strip()[:300]}")
    return json.loads(p.stdout or "null")


def _runs(repo: str, status: str, pages: int = 5) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        got = _gh(f"repos/{repo}/actions/runs?status={status}&per_page=100&page={page}")
        batch = got.get("workflow_runs") or []
        out += batch
        if len(batch) < 100:
            break
    return out


def _beat(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _issue_no(c: Mapping[str, Any]) -> int | None:
    m = re.search(r"/issues/(\d+)$", str(c.get("issue_url") or ""))
    return int(m.group(1)) if m else None


def _clears(
    repo: str, prs: list[Mapping[str, Any]], now: datetime, deadline: float
) -> tuple[dict[int, str | None], bool]:
    """Each open PR's CLEAR time for its current head, from ONE repo-wide comment listing
    (about 10 pages) instead of one call per PR. True when the listing was read to its end."""
    since = (now - timedelta(days=CLEAR_LOOKBACK_D)).strftime("%Y-%m-%dT%H:%M:%SZ")
    by_pr: dict[int, list[Mapping[str, Any]]] = {}
    complete = False
    for page in range(1, CLEAR_PAGES + 1):
        if time.monotonic() > deadline:
            break
        batch = _gh(f"repos/{repo}/issues/comments?since={since}&per_page=100&page={page}")
        for c in batch or []:
            n = _issue_no(c)
            if n is not None:
                by_pr.setdefault(n, []).append(c)
        if len(batch or []) < 100:
            complete = True
            break
    return {
        int(p["number"]): clear_at(by_pr.get(int(p["number"]), []), str(p["head"]["sha"]))
        for p in prs
    }, complete


def read_order(
    prs: list[Mapping[str, Any]],
    clears: Mapping[int, str | None],
    queued_runs: list[Mapping[str, Any]],
) -> tuple[list[Mapping[str, Any]], set[int]]:
    """Per-PR check reads, most important first, and the PRs that must not be left unread:
    ready (non-draft) PRs, CLEARed heads and heads with a queued run. The rest follow, newest
    push first, as far as the budget goes."""
    queued_heads = {str(r.get("head_sha")) for r in queued_runs}
    must = {
        int(p["number"])
        for p in prs
        if not p.get("draft")
        or clears.get(int(p["number"]))
        or str(p["head"]["sha"]) in queued_heads
    }
    rest = sorted(
        (p for p in prs if int(p["number"]) not in must),
        key=lambda p: str(p.get("updated_at") or ""),
        reverse=True,
    )
    first = [p for p in prs if int(p["number"]) in must]
    return first + rest, must


def collect(
    repo: str,
    base: str = LIVE,
    heartbeat: Path | None = None,
    sign_beat: Path | None = None,
    budget_s: float = BUDGET_S,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    deadline = time.monotonic() + budget_s
    prs: list[dict[str, Any]] = []
    for page in range(1, 11):  # 231 PRs were open on 2026-10-29: one page of 100 is not all
        batch = _gh(f"repos/{repo}/pulls?state=open&base={base}&per_page=100&page={page}")
        prs += batch
        if len(batch) < 100:
            break
    queued = _runs(repo, "queued")
    running = len(_runs(repo, "in_progress", pages=1))
    live = _gh(f"repos/{repo}/commits?sha={base}&per_page=100")
    merged = _gh(
        f"repos/{repo}/pulls?state=closed&base={base}&sort=updated&direction=desc&per_page=100"
    )
    clears, clears_complete = _clears(repo, prs, now, deadline)
    order, must = read_order(prs, clears, queued)
    checks: dict[str, list[Mapping[str, Any]]] = {}
    ready: dict[int, str] = {}
    unread: list[int] = []
    for p in order:
        n, head = int(p["number"]), str(p["head"]["sha"])
        if time.monotonic() > deadline:
            unread.append(n)
            continue
        got = _gh(f"repos/{repo}/commits/{head}/check-runs?per_page=100")
        checks[head] = list(got.get("check_runs") or [])
        done = {c.get("name"): c for c in checks[head] if c.get("status") == "completed"}
        if all(done.get(k, {}).get("conclusion") == "success" for k in ALL_CHECKS):
            st = _gh(f"repos/{repo}/commits/{head}/status")
            if any(
                x.get("context") == GATE_STATUS and x.get("state") == "success"
                for x in st.get("statuses") or []
            ):
                ready[n] = max(str(done[k].get("completed_at")) for k in ALL_CHECKS)
    rep = assess(
        now, prs, checks, clears, queued, running, live, ready, _beat(heartbeat),
        heartbeat is not None, _beat(sign_beat), sign_beat is not None, base, merged,
    )  # fmt: skip
    return with_coverage(rep, len(prs), len(prs) - len(unread), unread, must, clears_complete)


def with_coverage(
    rep: dict[str, Any],
    total: int,
    read: int,
    unread: list[int],
    must: set[int],
    clears_complete: bool,
) -> dict[str, Any]:
    """Says what the budget left unread; a priority PR unread, or a cut CLEAR listing, is RED."""
    missed = sorted(n for n in unread if n in must)
    rep["coverage"] = {
        "open_prs": total,
        "checks_read": read,
        "unread": len(unread),
        "priority_unread": missed[:50],
        "clears_complete": clears_complete,
    }
    if missed:
        rep["red"].append(
            f"WATCH_PARTIAL: {len(missed)} ready, CLEARed or queued PR(s) unread inside the "
            f"budget ({', '.join(f'#{n}' for n in missed[:8])})"
        )
    if not clears_complete:
        rep["red"].append("WATCH_PARTIAL: the CLEAR listing was cut by the budget")
    rep["status"] = "RED" if rep["red"] else "GREEN"
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--base", default=LIVE)
    ap.add_argument("--out", type=Path, default=REPORT)
    ap.add_argument("--print", action="store_true", help="stdout only, write nothing")
    ap.add_argument("--heartbeat", type=Path, help="the box sweep's logs/workflow_gate.json")
    ap.add_argument("--sign-heartbeat", type=Path, help="the sign train's logs/sign_train.json")
    ap.add_argument(
        "--min-interval-min", type=float, default=25.0,
        help="skip when --out is younger (the sweep calls this every 10 min; ~2 calls per open PR)",
    )  # fmt: skip
    ap.add_argument(
        "--budget-s", type=float, default=BUDGET_S,
        help="stop the per-PR reads after this many seconds (the rest is counted, not read)",
    )  # fmt: skip
    a = ap.parse_args(argv)
    if not a.print and a.min_interval_min > 0:
        try:
            prev = json.loads(a.out.read_text(encoding="utf-8"))
            age = _age_min(datetime.now(UTC), str(prev.get("at") or ""))
        except (OSError, ValueError):
            age = None
        held = 0
        if a.heartbeat is not None:
            try:
                held = int(
                    json.loads(a.heartbeat.read_text("utf-8-sig")).get("mutex_held_runs") or 0
                )
            except (OSError, ValueError):
                held = 0
        if age is not None and age < a.min_interval_min and held <= SWEEP_WEDGED_RUNS:
            print(f"fresh ({age:.0f} min old): not re-read")
            return 0
    try:
        rep = collect(a.repo, a.base, a.heartbeat, a.sign_heartbeat, a.budget_s)
    except (RuntimeError, ValueError) as exc:
        # no data is not GREEN: the report says the watcher itself could not see
        rep = {
            "at": datetime.now(UTC).isoformat(timespec="seconds"),
            "status": "RED",
            "red": [f"WATCH_BLIND: {exc}"],
        }
    text = json.dumps(rep, indent=2)
    if a.print:
        print(text)
    else:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        tmp = a.out.with_suffix(".tmp")
        tmp.write_text(text + "\n", encoding="utf-8")
        tmp.replace(a.out)
        print(f"{rep['status']}: {'; '.join(rep['red'][:5]) or 'merge pipeline flowing'}")
    return 2 if rep["status"] == "RED" else 0


if __name__ == "__main__":
    sys.exit(main())
