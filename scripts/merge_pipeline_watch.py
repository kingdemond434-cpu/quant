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
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LIVE = "claude/llm-auto-upgrade-verify-gcjac3"
REPORT = ROOT / "desks" / "mt5" / "reports" / "MERGE_PIPELINE.json"
QUEUED_RED_MIN = 30.0
CLEAR_RED_H = 2.0
LIVE_RED_H = 6.0
#: REVIEWER_FP: of the open heads the independent reviewer FAILed, the share an Auditor CLEARed
#: (the human-grade audit read the same head and found nothing): a proxy false-positive rate.
REVIEWER_FP_MIN_FAILS = 3
REVIEWER_FP_RED = 0.5
REVIEWER = "independent-review"
TRUSTED = ("OWNER", "MEMBER", "COLLABORATOR")
#: Matched with ALL whitespace removed: zuck's CLEARs arrive with the sha wrapped over lines.
CLEAR_RE = re.compile(r"AUDITCLEAR([0-9a-f]{7,40})", re.I)
#: Commits on LIVE that carry no code: the box's state publishes and CI's own seal commits.
NOT_CODE_RE = re.compile(r"^(mt5 box state|seal release)\b", re.I)


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
) -> dict[str, Any]:
    """The report, from already-fetched data (pure: the tests drive this)."""
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
            }
        )
        if qmax is not None and qmax > QUEUED_RED_MIN:
            red.append(f"CI_QUEUED #{n}: a check queued {qmax:.0f} min on {head[:9]}")
        if cage is not None and cage / 60.0 > CLEAR_RED_H:
            red.append(f"CLEAR_WAITING #{n}: CLEARed {cage / 60.0:.1f} h ago, still open")
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
    if any(r["clear_at"] for r in rows) and (code_age is None or code_age / 60.0 > LIVE_RED_H):
        hours = "an unknown number of" if code_age is None else f"{code_age / 60.0:.1f}"
        red.append(f"LIVE_STALLED: no code on LIVE for {hours} h while CLEARed work waits")
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
        "live": {
            "last_code_commit": None if code is None else str(code["sha"])[:9],
            "last_code_at": code_at,
            "hours_since_code": None if code_age is None else round(code_age / 60.0, 2),
        },
        "prs": sorted(rows, key=lambda r: -(r["oldest_queued_min"] or 0.0)),
        "thresholds": {
            "queued_red_min": QUEUED_RED_MIN,
            "clear_red_h": CLEAR_RED_H,
            "live_red_h": LIVE_RED_H,
        },
    }


def _gh(path: str) -> Any:
    gh = os.environ.get("GH_BIN") or "gh"
    p = subprocess.run(
        [gh, "api", path],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
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


def collect(repo: str, base: str = LIVE) -> dict[str, Any]:
    now = datetime.now(UTC)
    prs: list[dict[str, Any]] = []
    for page in range(1, 11):  # 231 PRs were open on 2026-10-29: one page of 100 is not all
        batch = _gh(f"repos/{repo}/pulls?state=open&base={base}&per_page=100&page={page}")
        prs += batch
        if len(batch) < 100:
            break
    checks: dict[str, list[Mapping[str, Any]]] = {}
    clears: dict[int, str | None] = {}
    for p in prs:
        head = str(p["head"]["sha"])
        got = _gh(f"repos/{repo}/commits/{head}/check-runs?per_page=100")
        checks[head] = list(got.get("check_runs") or [])
        comments = _gh(f"repos/{repo}/issues/{p['number']}/comments?per_page=100")
        clears[int(p["number"])] = clear_at(comments, head)
    queued = _runs(repo, "queued")
    running = len(_runs(repo, "in_progress", pages=1))
    live = _gh(f"repos/{repo}/commits?sha={base}&per_page=100")
    return assess(now, prs, checks, clears, queued, running, live)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--base", default=LIVE)
    ap.add_argument("--out", type=Path, default=REPORT)
    ap.add_argument("--print", action="store_true", help="stdout only, write nothing")
    a = ap.parse_args(argv)
    try:
        rep = collect(a.repo, a.base)
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
