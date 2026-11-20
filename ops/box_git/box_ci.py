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

import json
import os
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


def plan_full_run(state: Mapping[str, Any], live_head: str) -> FullRunPlan:
    """Coalescing: one full run at a time; while it runs only the NEWEST head waits behind it."""
    running = state.get("full_running")
    done = {r.get("head") for r in state.get("full_results") or [] if r.get("kind") == FULL}
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


def record(state: dict[str, Any], *, head: str, kind: str, ok: bool, why: str,
           now: datetime | None = None) -> dict[str, Any]:
    rows = [*(state.get("full_results") or []),
            {"head": head, "kind": kind, "ok": ok, "why": why[:400],
             "at": (now or datetime.now(UTC)).isoformat(timespec="seconds")}]
    state["full_results"] = rows[-KEEP_RESULTS:]
    return state


def pytest_argv(python: str, tests: Sequence[str] | str, workers: int,
                junit: Path) -> list[str]:
    from ops.box_git.impacted import ALL
    argv = [python, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={junit}"]
    if workers > 1:
        argv += ["-n", str(workers), "--dist", "loadfile"]
    if tests != ALL:
        argv += list(tests)
    return argv


def idle_priority_kwargs() -> dict[str, Any]:
    """subprocess kwargs that start the job at IDLE priority (Windows) or nice 19 (elsewhere)."""
    if os.name == "nt":
        import subprocess
        return {"creationflags": getattr(subprocess, "IDLE_PRIORITY_CLASS", 0x40)}
    return {"preexec_fn": lambda: os.nice(19)}


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
