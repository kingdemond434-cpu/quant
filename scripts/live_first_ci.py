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

  4. NEVER-STARTED RE-RUN (2026-11-04 00:12Z, Desk health). A PR run cancelled while still
     queued -- by a reorder, a burst or a sweep -- with ZERO jobs that ever reached a runner is
     not a failure of that head, but the audit gate quarantines the PR as "CI failed
     (cancelled)" and nothing re-ran it: hands did. Each call, inside the budget, re-runs at most
     MAX_UNSTARTED such runs: first attempt only (so each run is re-run by this at most ONCE),
     on a CURRENT open-PR head, created in the last UNSTARTED_H hours, newest per (head, workflow),
     and only when that head has no newer run of the same workflow. A run with any started job,
     or one this call or the ledger already owns, is never touched here.
  4b. CANCELLED GATE RUNS ARE RE-QUEUED TOO (2026-11-13, Autonomy). On 11-13 at 16:27Z 505 queued
     PR runs were cancelled by hand to free LIVE's seal. Rule 4 never brought the gate's own runs
     back: it listed only `pull_request` runs, only the newest 100, only 24 h back. So #1041 (CLEAR,
     approved, every other check green) sat with a cancelled audit-gate run and nothing re-fired it.
     Rule 4 now also re-runs never-started `pull_request_target` runs (audit-gate, trusted-eval)
     on a current open-PR head, those first, reads up to UNSTARTED_PAGES pages per event, looks
     back UNSTARTED_H hours, and re-runs only while the queue has room: at most REQUEUE_QMAX
     minus the runs already queued (zuck 11-13: no re-runs while the queue is over 60).
     Re-running a run that never reached a runner changes nothing but its place in the queue.

Rules 1-3 never touch `pull_request_target` runs (the audit gate, trusted-eval), nor
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
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
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
#: Rule 4b: the events whose never-started cancelled runs are re-run, gate runs first.
RERUN_EVENTS = ("pull_request_target", "pull_request")
#: Rule 4b: pages of cancelled runs read per event (100 a page), and the queue ceiling.
UNSTARTED_PAGES = 5
REQUEUE_QMAX = 60
#: THE WHOLE CALL'S WALL-CLOCK BUDGET (2026-11-03 23:31Z, box at 100% CPU). This runs inside
#: Quant-WorkflowGate BEFORE the audit gate, under the task's 30-minute limit. Unbounded, it made
#: one `gh api` call per cleared-check comment page and two per cancel; at 13-120 s per call
#: under load it outran the limit, the scheduler killed the task (0x41306), and the gate sweep
#: behind it -- the only automatic merge path -- never ran. Past the budget this call stops
#: ordering: a branch it has not read is ordered as uncleared, a run it has not cancelled stays
#: where it is, and an owed re-run it has not reached is carried unchanged. Nothing is lost; the
#: next call, ten minutes later, continues.
BUDGET_S = 300.0
#: Rule 4: re-runs of never-started cancelled PR runs per call, and how far back it looks.
MAX_UNSTARTED = 20
UNSTARTED_H = 72.0
#: Share of the budget CLEARed-first may spend reading comments; the rest is LIVE-first's.
CLEARED_SHARE = 0.4
#: Pages of queued runs older than LIVE's newest waiting run read per call (100 a page).
OLDER_PAGES = 10
#: Parallel cancel / re-run calls (2026-11-13 20:05Z: 98 runs ahead of LIVE, the box's gh calls
#: took 13-60 s each, one at a time, and the budget ran out after 2 cancels).
WORKERS = 8
#: A cancel or re-run that GitHub has not answered in this long is carried to the next call.
WRITE_TIMEOUT_S = 20


def _gh(path: str, method: str = "GET") -> Any:
    gh = os.environ.get("GH_BIN") or "gh"
    args = [gh, "api", path] + (["-X", method] if method != "GET" else [])
    try:
        p = subprocess.run(
            args, capture_output=True, text=True, encoding="utf-8", errors="replace",
            check=False, timeout=60 if method == "GET" else WRITE_TIMEOUT_S,
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


def unstarted_candidates(
    now: datetime,
    cancelled: list[dict[str, Any]],
    heads: dict[str, str],
    owned: set[int] = frozenset(),  # type: ignore[assignment]
) -> list[dict[str, Any]]:
    """Rule 4's candidates from already-fetched cancelled runs (pure): first-attempt
    `pull_request` or `pull_request_target` runs on a current PR head, recent, not owned by the
    ledger, newest per (head sha, workflow), the gate's `pull_request_target` runs first. Whether
    any job started is read per candidate afterwards."""
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for r in sorted(cancelled, key=lambda r: str(r.get("created_at")), reverse=True):
        key = (str(r.get("head_sha")), str(r.get("workflow_id") or r.get("name")))
        if key in seen:
            continue
        seen.add(key)
        age = _age_min(now, r.get("created_at"))
        if (
            r.get("event") not in RERUN_EVENTS
            or r.get("status") != "completed"
            or r.get("conclusion") != "cancelled"
            or int(r.get("run_attempt") or 1) != 1
            or int(r["id"]) in owned
            or heads.get(str(r.get("head_branch"))) != str(r.get("head_sha"))
            or age is None
            or age > UNSTARTED_H * 60
        ):
            continue
        out.append(r)
    out.sort(key=lambda r: RERUN_EVENTS.index(str(r.get("event"))))  # stable: newest first in each
    return out


def never_started(jobs: list[dict[str, Any]]) -> bool:
    """True only when the run has jobs and NONE of them reached a runner or ran a step."""
    return bool(jobs) and all(
        not j.get("steps") and not j.get("runner_name") and not j.get("runner_id") for j in jobs
    )


def _rerun_unstarted(
    repo: str,
    now: datetime,
    heads: dict[str, str],
    owned: set[int],
    over: Callable[[], bool],
    n_queued: int = 0,
) -> int:
    room = min(MAX_UNSTARTED, REQUEUE_QMAX - n_queued)
    if room <= 0:
        print(f"  never-started: {n_queued} runs queued (ceiling {REQUEUE_QMAX}), none re-run")
        return 0
    since = now.timestamp() - UNSTARTED_H * 3600
    day = datetime.fromtimestamp(since, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    runs: dict[int, dict[str, Any]] = {}
    for event in RERUN_EVENTS:
        for page in range(1, UNSTARTED_PAGES + 1):
            if over():
                break
            got = _gh(f"repos/{repo}/actions/runs?status=cancelled&event={event}"
                      f"&created=%3E%3D{day}&per_page=100&page={page}") or {}  # fmt: skip
            batch = got.get("workflow_runs") or []
            runs.update({int(r["id"]): r for r in batch})
            if len(batch) < 100:
                break
    done = 0
    for r in unstarted_candidates(now, list(runs.values()), heads, owned):
        if done >= room or over():
            break
        rid = int(r["id"])
        try:
            jobs = (_gh(f"repos/{repo}/actions/runs/{rid}/jobs?per_page=100") or {}).get("jobs")
            if not never_started(jobs or []):
                continue
            newer = (_gh(f"repos/{repo}/actions/runs?head_sha={r['head_sha']}&per_page=100")
                     or {}).get("workflow_runs") or []  # fmt: skip
            if any(
                x.get("workflow_id") == r.get("workflow_id")
                and str(x.get("created_at")) > str(r.get("created_at"))
                for x in newer
            ):
                continue  # that head already has a newer run of this workflow
            _gh(f"repos/{repo}/actions/runs/{rid}/rerun", "POST")
            done += 1
        except RuntimeError as exc:
            print(f"  never-started {rid}: {exc}")
    return done


def _queued(repo: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for page in range(1, 6):
        got = _gh(f"repos/{repo}/actions/runs?status=queued&per_page=100&page={page}")
        batch = got.get("workflow_runs") or []
        out += batch
        if len(batch) < 100:
            break
    return out


def _older(repo: str, base: str, now: datetime) -> list[dict[str, Any]]:
    """LIVE's own queued runs and, when one is waiting, the queued runs created BEFORE the newest
    waiting one (GitHub lists newest first, so with more than 500 queued, `_queued` never reaches
    the oldest: on 11-11 09:45Z, 1,223 were queued, LIVE's runs of 11-10 sat past page 5 and the
    call saw "0 ahead of LIVE"). Bounded at OLDER_PAGES pages."""
    got = _gh(f"repos/{repo}/actions/runs?branch={base}&status=queued&per_page=100") or {}
    mine = [r for r in got.get("workflow_runs") or [] if r.get("event") in LIVE_EVENTS]
    waiting = [
        _queued_at(r) for r in mine if (_age_min(now, _queued_at(r)) or 0.0) >= LIVE_FIRST_MIN
    ]
    if not waiting:
        return mine
    out = list(mine)
    for page in range(1, OLDER_PAGES + 1):
        batch = (
            _gh(
                f"repos/{repo}/actions/runs?status=queued&created=%3C{max(waiting)}"
                f"&per_page=100&page={page}"
            )
            or {}
        ).get("workflow_runs") or []
        out += batch
        if len(batch) < 100:
            break
    return out


def _merge_runs(*lists: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[Any] = set()
    out = []
    for lst in lists:
        for r in lst:
            if r.get("id") not in seen:
                seen.add(r.get("id"))
                out.append(r)
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


def _cleared(
    repo: str,
    queued: list[dict[str, Any]],
    heads: dict[str, str],
    over: Callable[[], bool] = lambda: False,
) -> frozenset[str]:
    """The head branches with a queued run whose current head is audit-CLEARed. A comment read
    that fails, or one the budget did not reach, leaves that PR uncleared: it is only ordered,
    never dropped."""
    clear_at = _clear_at()
    out = set()
    for b in sorted(
        {str(r.get("head_branch")) for r in queued if r.get("event") == "pull_request"}
    ):
        if over():
            print("  cleared-first: budget spent; the remaining branches are ordered as uncleared")
            break
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


def _cancel_batch(
    repo: str,
    waste: list[int],
    ahead: list[int],
    owed: list[dict[str, int]],
    state: Path,
    at: str,
    over: Callable[[], bool],
) -> list[dict[str, int]]:
    """Cancel `waste` (never re-run) and `ahead` (owed a re-run) with WORKERS calls at once.
    One fresh listing of the newest queued runs replaces a read per run; a run not in it (past
    its pages) is read on its own. A run that is no longer queued has started and is never
    cancelled. Every owed row is saved BEFORE its cancel goes out (#546 MF2)."""
    if not (waste or ahead) or over():
        return []
    try:
        fresh = {int(r["id"]): r for r in _queued(repo)}
    except RuntimeError as exc:
        print(f"  fresh listing: {exc}; each run is read on its own")
        fresh = {}

    def still_queued(rid: int) -> dict[str, Any] | None:
        if rid in fresh:
            return fresh[rid]
        if over():
            return None
        try:
            cur = _gh(f"repos/{repo}/actions/runs/{rid}")
        except RuntimeError as exc:
            print(f"  read {rid}: {exc}")
            return None
        return cur if cur.get("status") == "queued" else None

    ids = list(dict.fromkeys(waste + ahead))
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        cur = dict(zip(ids, pool.map(still_queued, ids), strict=True))
    go = [rid for rid in ids if cur[rid] is not None]
    rows: list[dict[str, int]] = []
    lock = threading.Lock()

    def cancel(rid: int) -> None:
        if over():
            return
        if rid in ahead:  # owed BEFORE its cancel goes out, so a crash never loses it (#546 MF2)
            row = {"id": rid, "attempt": int((cur[rid] or {}).get("run_attempt") or 1), "calls": 0}
            with lock:
                rows.append(row)
                _save(state, {"at": at, "owed": owed + rows})
        try:
            _gh(f"repos/{repo}/actions/runs/{rid}/cancel", "POST")
        except RuntimeError as exc:
            print(f"  cancel {rid}: {exc}")

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        list(pool.map(cancel, go))
    if over():
        print("  budget spent: the remaining runs keep their place until the next call")
    return rows


def run(
    repo: str,
    base: str,
    state: Path,
    settle_s: float = 60.0,
    dry: bool = False,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    budget_s: float = BUDGET_S,
) -> int:
    # BUDGET_S is a ceiling, never a default to raise: a caller can only shorten the call
    t0 = clock()
    budget = min(max(budget_s, 0.0), BUDGET_S)
    stop = t0 + budget
    # CLEARed-first may spend at most CLEARED_SHARE of the budget: on 11-11 09:45Z it spent all
    # of it reading comments and the call cancelled nothing ("budget spent" before rule 2).
    cleared_stop = t0 + CLEARED_SHARE * budget

    def over() -> bool:
        return clock() >= stop

    def over_cleared() -> bool:
        return clock() >= cleared_stop

    now = datetime.now(UTC)
    at = now.isoformat(timespec="seconds")
    queued = _queued(repo)  # runs BEFORE heads: a head moving in between reads as current
    try:  # the oldest queued runs, past `_queued`'s pages; a failed read orders what it has
        queued = _merge_runs(queued, _older(repo, base, now))
    except Exception as exc:
        print(f"  older runs skipped: {type(exc).__name__}: {exc}")
    heads = _heads(repo)
    owed = _load(state)
    # LIVE-FIRST BEFORE ANY COMMENT READ (2026-11-13 20:05Z: the box log read "98 ahead of LIVE",
    # "budget spent", 2 cancelled). LIVE's own order needs no comment read, so it is cancelled
    # first, in parallel, from one fresh listing; CLEARed-first reads comments with what is left.
    waste, ahead = plan(now, queued, heads, base)
    print(f"live-first: {len(waste)} superseded, {len(ahead)} ahead of LIVE, {len(owed)} owed")
    if dry:
        return 0
    cancelled = _cancel_batch(repo, waste, ahead, owed, state, at, over)
    try:  # CLEARed-first never costs LIVE-first: any failure here orders by LIVE alone (#556 SF1)
        cleared = _cleared(repo, queued, heads, over_cleared)
    except Exception as exc:
        print(f"  cleared-first skipped: {type(exc).__name__}: {exc}")
        cleared = frozenset()
    if cleared and not over():
        done = set(waste) | set(ahead)
        _, more = plan(now, queued, heads, base, cleared)
        more = [rid for rid in more if rid not in done]
        print(f"cleared-first: {len(more)} more ahead of {len(cleared)} CLEARed PR(s)")
        cancelled += _cancel_batch(repo, [], more, owed + cancelled, state, at, over)
    ahead_ids = {r["id"] for r in cancelled}
    owed = [r for r in owed if r["id"] not in ahead_ids]
    deadline = clock() + (settle_s if cancelled else 0.0)
    left: list[dict[str, int]] = []
    carried: list[dict[str, int]] = []  # not reached this call: carried with its count unchanged
    rerun = 0
    lock = threading.Lock()

    def settle(row: dict[str, int]) -> None:
        """Re-run one owed run once it has finished cancelling. A run this call cancelled is
        waited for until `deadline`; an older owed one is read once."""
        nonlocal rerun
        rid = row["id"]
        while True:
            try:
                cur = _gh(f"repos/{repo}/actions/runs/{rid}")
            except RuntimeError as exc:
                print(f"  read {rid}: {exc}")
                with lock:
                    left.append(row)
                return
            if int(cur.get("run_attempt") or 1) != row["attempt"]:
                return  # someone re-ran it already
            if cur.get("status") == "completed":
                if cur.get("conclusion") != "cancelled":
                    return  # it ran to an end of its own: nothing to re-run (#546 MF3)
                if str(cur.get("head_sha")) != heads.get(str(cur.get("head_branch"))):
                    return  # its head moved: the new head has its own runs
                try:
                    _gh(f"repos/{repo}/actions/runs/{rid}/rerun", "POST")
                    with lock:
                        rerun += 1
                except RuntimeError as exc:
                    print(f"  rerun {rid}: {exc}")
                    with lock:
                        left.append(row)
                return
            if row in owed or clock() >= deadline or over():
                with lock:
                    left.append(row)  # still cancelling: the next call re-runs it
                return
            sleep(5)

    todo: list[dict[str, int]] = []
    for row in cancelled + owed:
        if over() and row not in cancelled:
            carried.append(row)
        else:
            todo.append(row)
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        list(pool.map(settle, todo))
    keep: list[dict[str, int]] = list(carried)
    given_up = 0
    for row in left:
        row = {**row, "calls": row["calls"] + 1}
        if row["calls"] >= MAX_CALLS:
            given_up += 1
            print(f"  gave up re-running {row['id']} after {row['calls']} calls")
        else:
            keep.append(row)
    unstarted = 0
    if not over():
        owned = {r["id"] for r in cancelled + owed + keep}
        try:
            unstarted = _rerun_unstarted(repo, now, heads, owned, over, len(queued))
        except Exception as exc:  # rule 4 never costs rules 1-3, whatever it hits
            print(f"  never-started skipped: {type(exc).__name__}: {exc}")
    _save(state, {"at": at, "owed": keep, "cancelled_superseded": len(waste),
                  "moved_behind_live": len(cancelled), "rerun": rerun,
                  "rerun_never_started": unstarted, "given_up": given_up})  # fmt: skip
    print(f"live-first: re-ran {rerun}, {len(keep)} owed to the next call, {given_up} given up, "
          f"{unstarted} never-started re-run")  # fmt: skip
    return 2 if given_up else 0


def _budget(text: str) -> float:
    """--budget-s may only shorten the call: anything above BUDGET_S, or not positive, is refused."""
    v = float(text)
    if not 0 < v <= BUDGET_S:
        raise argparse.ArgumentTypeError(f"budget must be in (0, {BUDGET_S:.0f}] s, got {text}")
    return v


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--base", default=LIVE)
    ap.add_argument("--state", type=Path, default=REPORT, help="the ledger of owed re-runs")
    ap.add_argument("--dry-run", action="store_true", help="say what it would do, touch nothing")
    ap.add_argument("--settle-s", type=float, default=60.0, help="wait for cancels to finish")
    ap.add_argument("--budget-s", type=_budget, default=BUDGET_S,
                    help=f"the whole call's budget, at most {BUDGET_S:.0f} s")  # fmt: skip
    a = ap.parse_args(argv)
    try:
        return run(a.repo, a.base, a.state, a.settle_s, a.dry_run, budget_s=a.budget_s)
    except RuntimeError as exc:  # an API failure does nothing more
        print(f"live-first: stopped ({exc})")
        return 1


if __name__ == "__main__":
    sys.exit(main())
