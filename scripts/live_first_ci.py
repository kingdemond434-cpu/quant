"""LIVE FIRST: a push run on LIVE never waits behind PR runs for a runner.

    python scripts/live_first_ci.py --repo OWNER/NAME [--state PATH] [--dry-run]

Writes desks/mt5/reports/LIVE_FIRST_CI.json on the box (reports/ is gitignored: box-local), the
ledger of re-runs owed and what the last call moved. rc 2 when a re-run was given up on.

THE CLASS THIS CLOSES (2026-10-29 19:45Z). The free plan runs 20 jobs at once and serves queued
jobs oldest first. ~120 PR runs queued from 15:00Z sat ahead of LIVE's push runs of 19:03 and
19:09Z, so LIVE had no green run, Adopt-And-Seal held on "waiting for CI" and the FTMO fix #516
was not adopted. GitHub has no priority for a run, so the only lever is the order of the queue.

EACH CALL (the box sweep, workflow_gate.ps1, with zuck's gh login; zuck 19:50Z "yes"):
  1. A queued `pull_request` run whose branch is an open PR's head branch but whose sha is no
     longer that PR's head can never count: it is cancelled (merge_pipeline_watch's "stale").
  2. When a push or workflow_dispatch run on LIVE has been queued LIVE_FIRST_MIN or more, every
     queued `pull_request` run on a CURRENT PR head that joined the queue before it is cancelled
     and re-run: the re-run queues behind LIVE, nothing is lost.
  2b. CLEARED FIRST (zuck 22:08Z "yes", standing: never ask about queue order again). A PR whose
     current head carries a trusted, unedited AUDIT CLEAR waits like LIVE: once one of its runs
     has been queued LIVE_FIRST_MIN, every queued run of a PR WITHOUT a CLEAR that joined before
     it is moved behind it the same way. On 10-29 the fix that greened every PR's quality waited
     over an hour behind 155 runs of PRs nobody could merge yet.
  3. The owed re-runs are written to the ledger BEFORE the first cancel. A run is re-run only
     when it completed as `cancelled` on the attempt this call cancelled; one still cancelling
     is carried to the next call, at most MAX_CALLS calls, then given up on (rc 2).

`pull_request_target` runs (the audit gate: its head_sha is the base's) are never touched, nor
push, dispatch or schedule runs, nor a run that has started: each is re-read just before its
cancel. Every open PR is listed (any base), and the runs are read before the PRs, so a head that
moves in between reads as current (never cancelled) rather than stale.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
LIVE = "claude/llm-auto-upgrade-verify-gcjac3"
LIVE_FIRST_MIN = 5.0
#: Calls an owed re-run is carried before it is given up on (the sweep calls every 10 min).
MAX_CALLS = 6
#: The ledger: re-runs owed and what the last call did (box-local: reports/ is gitignored).
REPORT = ROOT / "desks" / "mt5" / "reports" / "LIVE_FIRST_CI.json"
LIVE_EVENTS = ("push", "workflow_dispatch")


def _gh(path: str, method: str = "GET") -> Any:
    gh = os.environ.get("GH_BIN") or "gh"
    args = [gh, "api", path] + (["-X", method] if method != "GET" else [])
    try:
        p = subprocess.run(
            args, capture_output=True, text=True, encoding="utf-8", errors="replace",
            check=False, timeout=60,
        )  # fmt: skip
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"gh api {method} {path}: timed out") from exc
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
    now: datetime,
    queued: list[dict[str, Any]],
    heads: dict[str, str],
    base: str = LIVE,
    cleared: frozenset[str] = frozenset(),
) -> tuple[list[int], list[int]]:
    """(cancel only, cancel then re-run) from already-fetched data (pure: the tests drive it).
    `heads`: head branch -> head sha of EVERY open PR. `cleared`: head branches whose current
    head is audit-CLEARed: they wait like LIVE and are never moved. Only `pull_request` runs are
    candidates."""
    prs = [r for r in queued if r.get("event") == "pull_request"]
    known = [r for r in prs if str(r.get("head_branch")) in heads]
    waste = [int(r["id"]) for r in known if str(r.get("head_sha")) != heads[str(r["head_branch"])]]
    current = [r for r in known if str(r.get("head_sha")) == heads[str(r["head_branch"])]]
    first = [
        r for r in queued if r.get("event") in LIVE_EVENTS and str(r.get("head_branch")) == base
    ] + [r for r in current if str(r.get("head_branch")) in cleared]
    waiting = [
        _queued_at(r) for r in first if (_age_min(now, _queued_at(r)) or 0.0) >= LIVE_FIRST_MIN
    ]
    if not waiting:
        return waste, []
    newest = max(waiting)  # every other PR run queued before the newest waiting one goes behind
    ahead = [
        int(r["id"])
        for r in current
        if str(r.get("head_branch")) not in cleared and _queued_at(r) < newest
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


_NUMBERS: dict[str, int] = {}  # head branch -> PR number, from the last _heads() listing


def _heads(repo: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for page in range(1, 11):  # every open PR, into any base (#546 audit MF1)
        batch = _gh(f"repos/{repo}/pulls?state=open&per_page=100&page={page}")
        out.update({str(p["head"]["ref"]): str(p["head"]["sha"]) for p in batch})
        _NUMBERS.update({str(p["head"]["ref"]): int(p["number"]) for p in batch if p.get("number")})
        if len(batch) < 100:
            break
    return out


def _clear_at() -> Callable[..., Any]:
    """merge_pipeline_watch.clear_at: the one reading of a trusted, unedited CLEAR (run with -I,
    so the script's own directory is not on sys.path)."""
    spec = importlib.util.spec_from_file_location("_mpw", Path(__file__).with_name(
        "merge_pipeline_watch.py"))  # fmt: skip
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return cast(Callable[..., Any], mod.clear_at)


def _cleared(repo: str, queued: list[dict[str, Any]], heads: dict[str, str]) -> frozenset[str]:
    """The head branches with a queued run whose current head is audit-CLEARed. A comment read
    that fails leaves that PR uncleared: it is only ordered, never dropped."""
    clear_at = _clear_at()
    out = set()
    for b in {str(r.get("head_branch")) for r in queued if r.get("event") == "pull_request"}:
        n = _NUMBERS.get(b)
        if not n or b not in heads:
            continue
        got: list[dict[str, Any]] = []
        try:
            for page in range(1, 6):
                batch = _gh(f"repos/{repo}/issues/{n}/comments?per_page=100&page={page}") or []
                got += batch
                if len(batch) < 100:
                    break
        except RuntimeError as exc:
            print(f"  comments #{n}: {exc}")
            continue
        if clear_at(got, heads[b]):
            out.add(b)
    return frozenset(out)


def _load(path: Path) -> list[dict[str, int]]:
    try:
        rows = json.loads(path.read_text(encoding="utf-8")).get("owed") or []
        return [{k: int(r[k]) for k in ("id", "attempt", "calls")} for r in rows]
    except (OSError, ValueError, AttributeError, KeyError, TypeError):
        return []


def _save(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc) + "\n", encoding="utf-8")
    tmp.replace(path)


def run(
    repo: str,
    base: str,
    state: Path,
    settle_s: float = 60.0,
    dry: bool = False,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    now = datetime.now(UTC)
    at = now.isoformat(timespec="seconds")
    queued = _queued(repo)  # runs BEFORE heads: a head moving in between reads as current
    heads = _heads(repo)
    try:  # CLEARed-first never costs LIVE-first: any failure here orders by LIVE alone (#556 SF1)
        cleared = _cleared(repo, queued, heads)
    except Exception as exc:
        print(f"  cleared-first skipped: {type(exc).__name__}: {exc}")
        cleared = frozenset()
    waste, ahead = plan(now, queued, heads, base, cleared)
    owed = [r for r in _load(state) if r["id"] not in ahead]
    print(f"live-first: {len(waste)} superseded, {len(ahead)} ahead of LIVE or a CLEARed PR "
          f"({len(cleared)} CLEARed), {len(owed)} owed")  # fmt: skip
    if dry:
        return 0
    cancelled: list[dict[str, int]] = []
    for rid in waste + ahead:
        try:
            cur = _gh(f"repos/{repo}/actions/runs/{rid}")
            if cur.get("status") != "queued":
                continue  # it started meanwhile: a started job is never cancelled
            if rid in ahead:  # owed BEFORE its cancel, so a crash never loses it (#546 MF2)
                row = {"id": rid, "attempt": int(cur.get("run_attempt") or 1), "calls": 0}
                cancelled.append(row)
                _save(state, {"at": at, "owed": owed + cancelled})
            _gh(f"repos/{repo}/actions/runs/{rid}/cancel", "POST")
        except RuntimeError as exc:
            print(f"  cancel {rid}: {exc}")
    deadline = clock() + (settle_s if cancelled else 0.0)
    left: list[dict[str, int]] = []
    rerun = 0
    for row in cancelled + owed:
        rid = row["id"]
        while True:
            try:
                cur = _gh(f"repos/{repo}/actions/runs/{rid}")
            except RuntimeError as exc:
                print(f"  read {rid}: {exc}")
                left.append(row)
                break
            if int(cur.get("run_attempt") or 1) != row["attempt"]:
                break  # someone re-ran it already
            if cur.get("status") == "completed":
                if cur.get("conclusion") != "cancelled":
                    break  # it ran to an end of its own: nothing to re-run (#546 MF3)
                if str(cur.get("head_sha")) != heads.get(str(cur.get("head_branch"))):
                    break  # its head moved: the new head has its own runs
                try:
                    _gh(f"repos/{repo}/actions/runs/{rid}/rerun", "POST")
                    rerun += 1
                except RuntimeError as exc:
                    print(f"  rerun {rid}: {exc}")
                    left.append(row)
                break
            if row in owed or clock() >= deadline:
                left.append(row)  # still cancelling: the next call re-runs it
                break
            sleep(5)
    keep: list[dict[str, int]] = []
    given_up = 0
    for row in left:
        row = {**row, "calls": row["calls"] + 1}
        if row["calls"] >= MAX_CALLS:
            given_up += 1
            print(f"  gave up re-running {row['id']} after {row['calls']} calls")
        else:
            keep.append(row)
    _save(state, {"at": at, "owed": keep, "cancelled_superseded": len(waste),
                  "moved_behind_live": len(cancelled), "rerun": rerun,
                  "given_up": given_up})  # fmt: skip
    print(f"live-first: re-ran {rerun}, {len(keep)} owed to the next call, {given_up} given up")
    return 2 if given_up else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--base", default=LIVE)
    ap.add_argument("--state", type=Path, default=REPORT, help="the ledger of owed re-runs")
    ap.add_argument("--dry-run", action="store_true", help="say what it would do, touch nothing")
    ap.add_argument("--settle-s", type=float, default=60.0, help="wait for cancels to finish")
    a = ap.parse_args(argv)
    try:
        return run(a.repo, a.base, a.state, a.settle_s, a.dry_run)
    except RuntimeError as exc:  # an API failure does nothing more
        print(f"live-first: stopped ({exc})")
        return 1


if __name__ == "__main__":
    sys.exit(main())
