"""LIVE FIRST: a push run on LIVE never waits behind PR runs for a runner.

    python scripts/live_first_ci.py --repo OWNER/NAME [--state PATH] [--dry-run]

Writes desks/mt5/reports/LIVE_FIRST_CI.json: what the call moved and the re-runs it still owes.

THE CLASS THIS CLOSES (2026-10-29 19:45Z). The free plan runs 20 jobs at once and serves queued
jobs oldest first. ~120 PR runs queued from 15:00Z sat ahead of LIVE's push runs of 19:03 and
19:09Z, so LIVE had no green run, Adopt-And-Seal held on "waiting for CI" and the FTMO fix #516
was not adopted. GitHub has no priority for a run, so the only lever is the order of the queue.

EACH RUN (the box sweep calls it, workflow_gate.ps1, with zuck's gh login; zuck 19:50Z "yes"):
  1. A queued PR run on a head that has since moved can never count: it is cancelled, always.
  2. When a push run on LIVE has been queued LIVE_FIRST_MIN or more, every queued PR run created
     before it is cancelled and re-run: the re-run queues behind LIVE, nothing is lost.
  3. A re-run needs the cancel to have finished, so a cancelled run not yet re-runnable is kept
     in the state file and re-run on the next call. A run whose head moved meanwhile is dropped.

Only QUEUED runs are touched: a started job is never cancelled. Push runs are never touched.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LIVE = "claude/llm-auto-upgrade-verify-gcjac3"
LIVE_FIRST_MIN = 5.0
PR_EVENTS = ("pull_request", "pull_request_target")
#: What each call did and the re-runs it owes the next one (box state, published with the rest).
REPORT = ROOT / "desks" / "mt5" / "reports" / "LIVE_FIRST_CI.json"


def _gh(path: str, method: str = "GET") -> Any:
    gh = os.environ.get("GH_BIN") or "gh"
    args = [gh, "api", path] + (["-X", method] if method != "GET" else [])
    p = subprocess.run(
        args, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        timeout=60,
    )  # fmt: skip
    if p.returncode != 0:
        raise RuntimeError(f"gh api {method} {path}: {p.stderr.strip()[:300]}")
    return json.loads(p.stdout) if p.stdout.strip() else None


def _age_min(now: datetime, s: str | None) -> float | None:
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (now - t).total_seconds() / 60.0


def _queued_at(r: dict[str, Any]) -> str:
    """When a run joined the queue: a re-run keeps its created_at and restarts run_started_at."""
    return str(r.get("run_started_at") or r.get("created_at"))


def plan(
    now: datetime, queued: list[dict[str, Any]], heads: set[str], base: str = LIVE
) -> tuple[list[int], list[int]]:
    """(cancel only, cancel then re-run) from already-fetched data (pure: the tests drive it).
    `heads`: the current head sha of every open PR into LIVE."""
    prs = [r for r in queued if r.get("event") in PR_EVENTS]
    waste = [int(r["id"]) for r in prs if str(r.get("head_sha")) not in heads]
    live = [
        _queued_at(r)
        for r in queued
        if r.get("event") == "push"
        and str(r.get("head_branch")) == base
        and (_age_min(now, _queued_at(r)) or 0.0) >= LIVE_FIRST_MIN
    ]
    if not live:
        return waste, []
    newest = max(live)  # every PR run queued before LIVE's newest waiting run goes behind it
    ahead = [
        int(r["id"]) for r in prs if str(r.get("head_sha")) in heads and _queued_at(r) < newest
    ]
    return waste, ahead


def _queued(repo: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for page in range(1, 6):
        got = _gh(f"repos/{repo}/actions/runs?status=queued&per_page=100&page={page}")
        batch = got.get("workflow_runs") or []
        out += batch
        if len(batch) < 100:
            break
    return out


def _heads(repo: str, base: str) -> set[str]:
    out: set[str] = set()
    for page in range(1, 11):
        batch = _gh(f"repos/{repo}/pulls?state=open&base={base}&per_page=100&page={page}")
        out |= {str(p["head"]["sha"]) for p in batch}
        if len(batch) < 100:
            break
    return out


def _load(path: Path) -> list[int]:
    try:
        return [int(x) for x in json.loads(path.read_text(encoding="utf-8")).get("pending") or []]
    except (OSError, ValueError, AttributeError):
        return []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--base", default=LIVE)
    ap.add_argument("--state", type=Path, default=REPORT, help="re-runs owed from the last call")
    ap.add_argument("--dry-run", action="store_true", help="say what it would do, touch nothing")
    ap.add_argument("--settle-s", type=float, default=60.0, help="wait for cancels to finish")
    a = ap.parse_args(argv)
    now = datetime.now(UTC)
    heads = _heads(a.repo, a.base)
    waste, ahead = plan(now, _queued(a.repo), heads, a.base)
    owed = [r for r in _load(a.state) if r not in ahead]
    print(f"live-first: {len(waste)} superseded, {len(ahead)} ahead of LIVE, {len(owed)} owed")
    if a.dry_run:
        return 0
    for rid in waste + ahead:
        try:
            _gh(f"repos/{a.repo}/actions/runs/{rid}/cancel", "POST")
        except RuntimeError as exc:  # it started or finished meanwhile: leave it
            print(f"  cancel {rid}: {exc}")
    pending = ahead + owed
    deadline = time.monotonic() + (a.settle_s if ahead else 0.0)
    left: list[int] = []
    for rid in pending:
        while True:
            run = _gh(f"repos/{a.repo}/actions/runs/{rid}")
            if str(run.get("head_sha")) not in heads:
                break  # its head moved: the new head has its own runs
            if run.get("status") == "completed":
                try:
                    _gh(f"repos/{a.repo}/actions/runs/{rid}/rerun", "POST")
                except RuntimeError as exc:
                    print(f"  rerun {rid}: {exc}")
                    left.append(rid)
                break
            if rid in owed:
                break  # cancelled a call ago and not completed: someone re-ran it already
            if time.monotonic() >= deadline:
                left.append(rid)  # still cancelling: the next call re-runs it
                break
            time.sleep(5)
    a.state.parent.mkdir(parents=True, exist_ok=True)
    tmp = a.state.with_suffix(".tmp")
    doc = {"at": now.isoformat(timespec="seconds"), "pending": left,
           "cancelled_superseded": len(waste), "moved_behind_live": len(ahead)}  # fmt: skip
    tmp.write_text(json.dumps(doc) + "\n", encoding="utf-8")
    tmp.replace(a.state)
    print(f"live-first: re-ran {len(pending) - len(left)}, {len(left)} owed to the next call")
    return 0


if __name__ == "__main__":
    sys.exit(main())
