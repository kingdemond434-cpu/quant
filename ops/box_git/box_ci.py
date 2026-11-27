"""BOX CI: the checks GitHub Actions ran, run on the trading box's IDLE cores only.

WHY (principal 2026-11-19; decision journal D-20261119-BOXGIT; coordinator 19:44Z). GitHub is
gone as a dependency. The trading box already runs everything else, so CI must never take what
trading, the tick recorder or the judge need.

THE RULES THIS MODULE ENFORCES (each pure, each tested):
  * DISK FLOOR. No job starts below DISK_FLOOR_GB free on the box's data volume. The tick
    recorder has hit the desk's 5 GB floor before; CI's floor is well above it, so CI is the
    first thing to stop when space runs short, never the recorder.
  * IDLE CORES ONLY. Workers = the cores measured idle right now, minus a reserve, capped; zero
    idle cores means the job waits. Every process runs at Windows IDLE priority.
  * PR CHECK = IMPACTED TESTS (ops/box_git/impacted.py) plus the static checks. The fast lane is
    the gate's: a PR the gate tiers as non-money gets no test run at all.
  * FULL SUITE AFTER EVERY MONEY-PATH MERGE, COALESCED. A merge to LIVE asks for a full run of
    LIVE's head; merges that land while one runs collapse into ONE next run of the newest head.
    Plus a nightly run.
  * PROMOTE ONLY A FULLY GREEN HEAD. `promotable` names the newest LIVE head whose full suite
    passed; nothing older than the last promotion and nothing that only passed impacted tests.
  * OUTPUTS PRUNED. Each job's work folder is deleted when it finishes; only a small result row
    is kept, KEEP_RESULTS rows at most.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DISK_FLOOR_GB = 25.0
RESERVE_CORES = 2
MAX_WORKERS = 8
IDLE_THRESHOLD_PCT = 20.0
#: Workers always run at IDLE priority even on a saturated box: they take only cycles no other
#: process wants, so research never slows, and merges never wait forever (box 2026-11-20: the
#: research load held every core and CI never started). FOUR, not one (box 11-20 22:05Z): one
#: idle worker got ~0.6 of a core and took over 48 min on one PR, with 17 CLEARed PRs queued
#: behind it -- a queue measured in a day. Idle class cannot take a cycle research wants, so more
#: idle workers only collect more of the leftovers.
FLOOR_WORKERS = 4
#: (boot r20, Audit HOLD MF1 2026-11-27 03:07Z) Concurrent checks share ONE reservation: each
#: checkout is charged WORKTREE_GB against the disk floor before it is made, and each running
#: check RAM_PER_CHECK_GB above a RAM floor that keeps the trading terminal's memory free.
WORKTREE_GB = 4.0
RAM_FLOOR_GB = 8.0
RAM_PER_CHECK_GB = 2.0
KEEP_RESULTS = 500

FULL = "full"
IMPACTED = "impacted"


def disk_ok(free_gb: float | None, floor_gb: float = DISK_FLOOR_GB) -> tuple[bool, str]:
    if free_gb is None:
        return False, "free disk is UNMEASURED: CI does not start blind"
    if free_gb < floor_gb:
        return False, f"{free_gb:.1f} GB free, under CI's {floor_gb:.0f} GB floor: CI waits"
    return True, f"{free_gb:.1f} GB free"


def idle_workers(per_core_pct: Sequence[float] | None, *, reserve: int = RESERVE_CORES,
                 cap: int = MAX_WORKERS, idle_pct: float = IDLE_THRESHOLD_PCT,
                 floor: int = FLOOR_WORKERS) -> int:
    """Workers CI may use now: cores under `idle_pct` busy, minus `reserve`, at most `cap`, and
    never under `floor` (idle priority). Unmeasured cores start nothing."""
    if not per_core_pct:
        return 0
    idle = sum(1 for p in per_core_pct if p < idle_pct)
    return max(floor, min(cap, idle - reserve))


@dataclass(frozen=True)
class FullRunPlan:
    start: str | None
    pending: str | None
    why: str


#: (boot r20) A FULL result caused by the BOX, not the code, is run again: 11-20 the only full
#: run of LIVE a301e334c died on the worker's unreadable checkout (PermissionError on
#: pyproject.toml, fixed by shared_dir the same day) and a law-gate timeout, and since a recorded
#: head counted as done it was never run again -- so nothing was ever promotable and nothing
#: reached production for a week. At most FULL_ENV_RERUNS more runs, FULL_ENV_RERUN_AFTER_S
#: apart. An env-classed result never counts as green (nor, later, as a baseline).
FULL_ENV_RERUNS = 2
FULL_ENV_RERUN_AFTER_S = 3600
_FULL_ENV = re.compile(r"law gate rc=124\b|pytest rc=124\b|did not answer in time|PermissionError"
                       r"|No space left|exit status 128|Could not determine home directory")


def full_env(why: str) -> bool:
    return bool(_FULL_ENV.search(why or ""))


def _done_heads(rows: Sequence[Mapping[str, Any]], now: datetime) -> set[Any]:
    by: dict[Any, list[Mapping[str, Any]]] = {}
    for r in rows:
        if r.get("kind") == FULL:
            by.setdefault(r.get("head"), []).append(r)
    done = set()
    for head, rs in by.items():
        env = [r for r in rs if r.get("ok") is not True and full_env(str(r.get("why") or ""))]
        if len(env) < len(rs) or len(env) > FULL_ENV_RERUNS:
            done.add(head)  # a code answer exists, or the re-runs are spent
            continue
        try:
            last = max(datetime.fromisoformat(str(r.get("at"))) for r in env)
        except (TypeError, ValueError):
            done.add(head)
            continue
        if (now - last).total_seconds() < FULL_ENV_RERUN_AFTER_S:
            done.add(head)  # not yet: the re-run waits its interval
    return done


def plan_full_run(state: Mapping[str, Any], live_head: str,
                  now: datetime | None = None) -> FullRunPlan:
    """Coalescing: one full run at a time; while it runs only the NEWEST head waits behind it."""
    running = state.get("full_running")
    done = _done_heads(state.get("full_results") or [], now or datetime.now(UTC))
    if live_head in done or live_head == running:
        return FullRunPlan(None, state.get("full_pending"), "LIVE's head is already run or running")
    if running:
        return FullRunPlan(None, live_head, f"a full run of {str(running)[:9]} is in progress; "
                                            f"{live_head[:9]} runs next (older waiters collapse)")
    return FullRunPlan(live_head, None, f"full suite for {live_head[:9]}")


def promotable(state: Mapping[str, Any], is_ancestor: Any) -> str | None:
    """The newest LIVE head whose FULL suite passed and that descends from the last promotion."""
    last = state.get("promoted")
    greens = [r for r in state.get("full_results") or []
              if r.get("kind") == FULL and r.get("ok") is True]
    best: str | None = None
    for r in greens:
        h = str(r.get("head"))
        if last and (h == last or not is_ancestor(last, h)):
            continue
        if best is None or is_ancestor(best, h):
            best = h
    return best


def direct_promotable(state: Mapping[str, Any], live: str, is_ancestor: Any,
                      code_diff: Any) -> str | None:
    """(boot r21, direct live) LIVE's head itself, as soon as it lands: no full run is waited
    for. Nothing when it IS the last promotion, does not descend from it, or differs from it only
    by the seal (`code_diff(a, b)` lists the changed paths other than RELEASE.json), so the seal
    commit a promotion lands on LIVE is never promoted again."""
    live = (live or "").strip()
    if len(live) != 40:
        return None
    last = state.get("promoted")
    if not last:
        return live
    if live == last or not is_ancestor(last, live):
        return None
    return live if str(code_diff(last, live) or "").strip() else None


def record(state: dict[str, Any], *, head: str, kind: str, ok: bool, why: str,
           now: datetime | None = None) -> dict[str, Any]:
    rows = [*(state.get("full_results") or []),
            {"head": head, "kind": kind, "ok": ok, "why": why[:400],
             "at": (now or datetime.now(UTC)).isoformat(timespec="seconds")}]
    state["full_results"] = rows[-KEEP_RESULTS:]
    return state


#: Per-test limit for box CI. The repo's 300 s (pyproject) assumes a normal-priority runner;
#: box CI runs at IDLE priority on whatever cycles research leaves, so the same test can take
#: several times as long in wall time. Box 11-20 22:20Z: PR #17's 141 impacted files on one
#: starved core ended "+++ Timeout +++" with no failing assertion. A test that is truly stuck
#: still dies, at 1200 s; the full suite's own 6 h job limit still bounds the run.
BOX_TEST_TIMEOUT_S = 1200


def pytest_argv(python: str, tests: Sequence[str] | str, workers: int,
                junit: Path) -> list[str]:
    from ops.box_git.impacted import ALL
    argv = [python, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={junit}",
            "-o", f"timeout={BOX_TEST_TIMEOUT_S}"]
    if workers > 1:
        argv += ["-n", str(workers), "--dist", "loadfile"]
    if tests != ALL:
        argv += list(tests)
    return argv


def idle_priority_kwargs() -> dict[str, Any]:
    """subprocess kwargs that start a CI job at BELOW-NORMAL priority (Windows) or nice 10.

    Not IDLE (11-26 01:45Z): on a box whose 18 cores the judge and research keep busy, an IDLE job
    got ~60 CPU-s in 15 min and the PR checks hit their 1h caps (rc 124), so no Audit CLEAR could
    reach LIVE. Below-normal still yields to everything at normal priority (MT5, the gateway,
    the money path) and runs ahead of nothing that trades."""
    if os.name == "nt":
        import subprocess
        return {"creationflags": getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0x4000)}
    return {"preexec_fn": lambda: os.nice(10)}


def prune(work: Path) -> None:
    shutil.rmtree(work, ignore_errors=True)


def load_state(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def save_state(path: Path, state: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def shared_dir(parent: Path, prefix: str) -> Path:
    """A fresh directory that INHERITS `parent`'s ACL, so the CI worker account can read it.
    tempfile.mkdtemp gives Python 3.13+ on Windows an owner-only ACL (box 2026-11-20: every
    worktree was unreadable to quantci and pytest died on pyproject.toml)."""
    import uuid
    for _ in range(100):
        d = parent / f"{prefix}{uuid.uuid4().hex[:10]}"
        try:
            os.mkdir(d)  # no mode argument: Windows applies the inherited ACL
            return d
        except FileExistsError:
            continue
    raise OSError(f"no free directory name under {parent}")


#: (boot r20) Every FULL run keeps its per-test outcomes, so a later promotion rule can compare
#: a head's reds with a reviewed baseline (Audit 11-27 01:29Z: node ids plus a signature each,
#: collected count, collection errors). Written beside the CI state; read by nothing yet.
FULL_NODES = "full_nodes"


def junit_outcomes(junit: Path) -> dict[str, Any]:
    """{collected, failed, errors, skipped, outcomes: {node: outcome}, sigs: {node: signature}}
    from a pytest junit file; {"unreadable": why} when it cannot be read. Never raises."""
    import xml.etree.ElementTree as ET
    try:
        root = ET.parse(junit).getroot()
    except (OSError, ET.ParseError) as exc:
        return {"unreadable": f"{type(exc).__name__}: {str(exc)[:200]}"}
    outcomes: dict[str, str] = {}
    sigs: dict[str, str] = {}
    for tc in root.iter("testcase"):
        cls, name = tc.get("classname") or "", tc.get("name") or ""
        node = f"{cls.replace('.', '/')}.py::{name}" if cls else name
        outcome, sig = "passed", None
        for tag in ("failure", "error", "skipped"):
            el = tc.find(tag)
            if el is not None:
                outcome = {"failure": "failed", "error": "error", "skipped": "skipped"}[tag]
                if tag != "skipped":
                    first = (el.get("message") or (el.text or "")).strip().splitlines()
                    sig = f"{el.get('type') or tag}: {first[0][:200] if first else ''}"
                break
        outcomes[node] = outcome
        if sig:
            sigs[node] = sig
    count = {k: sum(1 for v in outcomes.values() if v == k)
             for k in ("passed", "failed", "error", "skipped")}
    errs = 0
    for suite in root.iter("testsuite"):
        with contextlib.suppress(ValueError):
            errs = max(errs, int(suite.get("errors") or 0))
    return {"collected": len(outcomes), **count, "suite_errors": errs,
            "outcomes": outcomes, "sigs": sigs}


def save_full_nodes(state_path: Path, head: str, doc: Mapping[str, Any]) -> Path | None:
    try:
        d = state_path.parent / FULL_NODES
        d.mkdir(parents=True, exist_ok=True)
        f = d / f"{head}.json"
        save_state(f, {"head": head, "at": datetime.now(UTC).isoformat(timespec="seconds"),
                       **doc})
        return f
    except OSError:
        return None
