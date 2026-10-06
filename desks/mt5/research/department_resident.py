"""DEPARTMENT RESIDENT -- a research department runs 24/7: a pass restarts when it finishes.

THE PRINCIPAL'S QUESTION (2026-09-17): "should we make all hunters pure 24/7 instead of hourly
in the whole research system?" Yes for the producers. An hourly clock leaves dead time: a
department that finishes its pass in twenty minutes waits forty for the next start, and one
that needs ninety is cut by its task limit. A resident loop runs the department's plan, and
the moment it ends -- ok, failed or budget-cut -- starts the next pass, so every department
is at its full useful throughput every hour of the day. The core plan (governance, forward,
publication: cheap, once an hour is right) stays on MT5-HourlyCore; the gauntlet keeps its
own ten-minute clock; this loop is for the producers.

WHAT KEEPS IT SAFE ON THE BOX THAT TRADES. (1) A singleton lock per department, so the
keep-alive trigger that restarts a dead resident is a no-op while one is alive. (2) The pass
runs as a child process under the same HOURLY_PLAN=dept:<name> the hourly task used, with a
hard timeout, so a hung leg never freezes the loop and every leg keeps its budget and ledger
row. (3) BELOW_NORMAL priority for the child, so the gateway resident and the terminal always
win the CPU. (4) A memory guard: a pass does not start while free physical memory is under
MIN_FREE_MB. (5) A floor between passes (MIN_CYCLE_S) so an empty department does not spin.
(6) The loop's own memory is tiny; it recycles itself after RECYCLE_PASSES passes anyway.

THE WORK-SEEKING LANE (principal 2026-10-06: "cadence must never be the primary driver").
A department pass is still a loop, but the organs that FEED the judge and the producers whose
inputs arrive between passes were timer-only: they sat in `CORE_LEGS` and ran once an hour on
MT5-HourlyCore whether or not anything had happened, and a candidate compiled at :05 waited up
to fifty-five minutes for the docket writer. Each resident now also runs a LANE -- a thread of
the same process, launched by the same keep-alive task, never a second launcher -- that consumes
the `RESIDENT_UNITS` of its department as WORK: a unit is READY when an event it subscribes to
arrives (priority 3), when one of its declared inputs changed since the watermark it last
consumed (priority 2), or when its watchdog age passes (priority 1). The lane takes the highest-
priority READY unit, holds an OS LEASE on it (a byte-range lock the kernel drops if the process
dies, plus `lease_until` in the checkpoint for observers), runs it as `HOURLY_PLAN=legs:<unit>`
(the leg's own `_costed` boundary, ledger row and budget), and CHECKPOINTS the input watermark
it consumed. Events pre-empt at the unit boundary: they are re-read before every pick, so an
arriving event jumps every queued data-change and watchdog unit; a running unit is never killed
mid-write. Nothing READY means a short poll, not an hour. MT5-HourlyCore stays as the WATCHDOG:
`resident_owns` tells the core pass to skip a unit whose resident checkpoint is fresh and to run
it, exactly as before, when the lane is dead or the unit failed. Backpressure goes to the judge
only -- no unit waits on the judge's backlog; the memory guard every pass already obeys is the
one shared brake.

    python department_resident.py --dept discovery       # loop until stopped
    python department_resident.py --dept intel --once    # one pass (tests, probes)
    python department_resident.py --unit merge_docket --once   # one work unit, now
    python department_resident.py --census               # write reports/RESIDENT_ORGANS.json
"""
from __future__ import annotations

import argparse
import contextlib
import ctypes
import json
import os
import socket
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
CYCLE = DESK / "research" / "hourly_cycle.py"
LOCKS = DESK / "data" / "locks"
LOGS = DESK / "logs"
PASS_TIMEOUT_S = int(os.environ.get("DEPT_PASS_TIMEOUT_S", "10800"))      # 3 h, as the task had
MIN_CYCLE_S = int(os.environ.get("DEPT_MIN_CYCLE_S", "600"))              # never spin faster
PAUSE_S = int(os.environ.get("DEPT_PAUSE_S", "30"))
MIN_FREE_MB = float(os.environ.get("DEPT_MIN_FREE_MB", "4096"))
RECYCLE_PASSES = int(os.environ.get("DEPT_RECYCLE_PASSES", "48"))
# Department singletons stop one department duplicating itself; they do not stop twenty
# different departments from observing the same free-memory snapshot and all starting together.
# That race was measured on the trading box on 2026-09-30: 20+ hourly_cycle children overlapped,
# while deepening/descendant/gauntlet workers held tens of GB each.  Bound cross-department
# passes with OS-held slots.  Three keeps useful parallel discovery on the 98GB box while leaving
# the terminal, gateway, gauntlet and core loop headroom.  A crashed process releases its byte
# lock in the kernel, so there is no stale-file recovery path.
CONCURRENT_PASSES = max(1, int(os.environ.get("DEPT_CONCURRENT_PASSES", "3")))
# A department child still has a hard timeout.  Plan strictly inside it so every admitted
# oldest-first tranche can checkpoint and publish instead of losing the same tail every pass.
PASS_BUDGET_FILL = min(
    0.95,
    max(0.50, float(os.environ.get("DEPT_PASS_BUDGET_FILL", "0.82"))),
)
BELOW_NORMAL_PRIORITY_CLASS = 0x00004000


def log(dept: str, msg: str) -> None:
    line = f"{datetime.now(tz=UTC).isoformat(timespec='seconds')} dept[{dept}]: {msg}"
    print(line, flush=True)
    with contextlib.suppress(OSError):
        LOGS.mkdir(parents=True, exist_ok=True)
        with (LOGS / "department_resident.log").open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def free_phys_mb() -> float | None:
    """Free physical memory on Windows via GlobalMemoryStatusEx; None where unmeasurable."""
    if sys.platform != "win32":
        return None
    try:
        class _MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        ms = _MS()
        ms.dwLength = ctypes.sizeof(_MS)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms)):  # type: ignore[attr-defined]
            return None
        return float(ms.ullAvailPhys) / (1024 * 1024)
    except Exception:
        return None


def claim_singleton(dept: str):
    """Hold data/locks/dept_<name>.lock for the life of this process; None when another holds it."""
    LOCKS.mkdir(parents=True, exist_ok=True)
    path = LOCKS / f"dept_{dept}.lock"
    try:
        fh = open(path, "a+", encoding="utf-8")  # noqa: SIM115 -- held for the process lifetime
    except OSError:
        return None
    try:
        if sys.platform == "win32":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    with contextlib.suppress(OSError):
        fh.seek(0)
        fh.truncate()
        fh.write(f"{os.getpid()} {datetime.now(tz=UTC).isoformat(timespec='seconds')}\n")
        fh.flush()
    return fh


def claim_capacity_slot(slots: int = CONCURRENT_PASSES):
    """Claim one of the shared department-pass slots, or None when all are busy."""
    LOCKS.mkdir(parents=True, exist_ok=True)
    for index in range(max(1, int(slots))):
        path = LOCKS / f"dept_capacity_{index}.lock"
        try:
            fh = open(path, "a+", encoding="utf-8")  # noqa: SIM115 -- held across the pass
        except OSError:
            continue
        try:
            if sys.platform == "win32":
                import msvcrt
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            continue
        with contextlib.suppress(OSError):
            fh.seek(0)
            fh.truncate()
            fh.write(f"{os.getpid()} {datetime.now(tz=UTC).isoformat(timespec='seconds')}\n")
            fh.flush()
        return fh
    return None


def _wait_ticket(dept: str) -> Path:
    """An OS-visible FIFO ticket; the department singleton permits only one per department."""
    LOCKS.mkdir(parents=True, exist_ok=True)
    path = LOCKS / f"dept_wait_{time.time_ns()}_{os.getpid()}_{dept}.ticket"
    path.touch(exist_ok=False)
    return path


def _ticket_alive(path: Path, pid: int) -> bool:
    """A crashed waiter must not block the queue forever, including after PID reuse."""
    try:
        import psutil
        proc = psutil.Process(pid)
        return proc.is_running() and proc.create_time() <= path.stat().st_mtime + 1.0
    except (ImportError, PermissionError):
        return True  # unmeasured ownership is not permission to steal another waiter's turn
    except (OSError, ValueError):
        return False
    except Exception as exc:
        if type(exc).__name__ in ("NoSuchProcess", "ZombieProcess"):
            return False
        return True


def _oldest_waiter() -> Path | None:
    """Return the oldest live contender; remove abandoned process tickets only."""
    contenders: list[tuple[int, str, Path]] = []
    for path in LOCKS.glob("dept_wait_*.ticket"):
        try:
            _, _, stamp, pid, _dept = path.stem.split("_", 4)
            entered = int(stamp)
            owner = int(pid)
            if not _ticket_alive(path, owner):
                path.unlink(missing_ok=True)
                continue
            contenders.append((entered, path.name, path))
        except (ValueError, OSError):
            # An unreadable ticket is not evidence of an available slot. Leave it visible.
            continue
    return min(contenders)[2] if contenders else None


def wait_for_capacity(dept: str, *, slots: int = CONCURRENT_PASSES,
                      poll_s: int = PAUSE_S):
    """Wait FIFO for bounded capacity; reacquiring departments rejoin at the tail."""
    announced = False
    ticket = _wait_ticket(dept)
    try:
        while True:
            if _oldest_waiter() == ticket:
                handle = claim_capacity_slot(slots)
                if handle is not None:
                    if announced:
                        log(dept, f"capacity available: admitted to one of {slots} department slots")
                    return handle
            if not announced:
                log(dept, "waiting: bounded department slots or older pass(es) ahead")
                announced = True
            time.sleep(max(1, int(poll_s)))
    finally:
        ticket.unlink(missing_ok=True)


def _tree_runner():
    """libs/ops/proctree.run when it imports (kills the whole tree on timeout), else
    subprocess.run -- a resident must keep running even when the rail cannot load."""
    try:
        root = str(DESK.parents[1])
        if root not in sys.path:
            sys.path.insert(0, root)
        from libs.ops import proctree
        return proctree.run
    except Exception:
        return subprocess.run


_run_tree = _tree_runner()


def run_pass(dept: str, timeout_s: int = PASS_TIMEOUT_S) -> dict:
    """One department pass as a child under HOURLY_PLAN=dept:<name>, BELOW_NORMAL priority."""
    env = dict(os.environ)
    env["HOURLY_PLAN"] = f"dept:{dept}"
    # leg_rotation otherwise treats departments as unbounded, which is false: this child is
    # killed at timeout_s. Deferred work leads the immediately following resident pass.
    safe_budget = max(1, int(timeout_s * PASS_BUDGET_FILL))
    try:
        inherited_budget = float(env.get("HOURLY_BUDGET_S", "0") or 0)
    except ValueError:
        inherited_budget = 0.0
    # Preserve a stricter caller budget, but never inherit one that reaches past our kill clock.
    env["HOURLY_BUDGET_S"] = str(int(min(inherited_budget, safe_budget))
                                 if inherited_budget > 0 else safe_budget)
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = BELOW_NORMAL_PRIORITY_CLASS
    t0 = time.monotonic()
    try:
        r = _run_tree([sys.executable, "-W", "ignore", str(CYCLE)], cwd=str(DESK),
                      env=env, timeout=timeout_s, check=False, **kwargs)
        return {"rc": r.returncode, "seconds": round(time.monotonic() - t0, 1), "status": "ok"
                if r.returncode == 0 else "exit"}
    except subprocess.TimeoutExpired:
        return {"rc": None, "seconds": round(time.monotonic() - t0, 1), "status": "timeout"}
    except OSError as exc:
        return {"rc": None, "seconds": round(time.monotonic() - t0, 1),
                "status": f"failed_to_start: {type(exc).__name__}"}


#: Cores kept for the live terminal, the gateway and the core hourly pass before a resident is
#: allowed to start its next pass early. The same three the sealed gauntlet reserves in session.
IDLE_RESERVE_CORES = int(os.environ.get("DEPT_RESERVE_CORES", "3"))


def spare_cores() -> float | None:
    """Cores this box measurably is NOT using, or None where it cannot be measured.

    psutil, never CIM: CIM on this box is slow enough to be its own defect. An unreadable counter
    is UNMEASURED, and UNMEASURED keeps the conservative floor -- it never licenses a faster loop.
    """
    try:
        import psutil
    except ImportError:
        return None
    try:
        busy = float(psutil.cpu_percent(interval=1.0))
        return (psutil.cpu_count() or 1) * (100.0 - busy) / 100.0
    except Exception:
        return None


def cycle_floor_s() -> tuple[float, str]:
    """The seconds between the START of one pass and the start of the next. ONE WAY: it is only
    ever LOWERED below MIN_CYCLE_S, and only while the box measurably has room to spare.

    WHAT THE FLAT 600 s WAS COSTING, measured on the trading box 2026-09-23/24. Thirteen forest
    departments finish a pass in a median of 130-270 seconds and then sat out the rest of the ten
    minutes: `europe` worked 183 s of every 600 and `japan` 22 s. That is a duty cycle of 3% to
    45% imposed by a constant, on a box whose desk processes were measured holding 401% of an
    1800% CPU -- four cores of eighteen, with fourteen idle. The floor's own stated purpose is
    that "an empty department does not spin", and `PAUSE_S` already does that: a department whose
    pass returns immediately still waits thirty seconds. The extra 570 was a cadence cap sized
    from nothing, and it is exactly the gap this desk's duty-cycle work exists to close.

    THE LIVE TERMINAL STILL WINS. The cap is lifted only while free physical memory clears the
    same guard a pass already waits on AND at least `IDLE_RESERVE_CORES` cores measure idle. An
    unmeasurable counter keeps the old floor, which is the behaviour this file has always had.
    """
    free = free_phys_mb()
    if free is not None and free < MIN_FREE_MB:
        return float(MIN_CYCLE_S), (f"free memory {free:.0f}MB is under the {MIN_FREE_MB:.0f}MB "
                                    f"guard: the conservative floor stands")
    spare = spare_cores()
    if spare is None:
        return float(MIN_CYCLE_S), "spare cores UNMEASURED: the conservative floor stands"
    if spare < IDLE_RESERVE_CORES:
        return float(MIN_CYCLE_S), (f"{spare:.1f} spare cores is under the terminal's reserve of "
                                    f"{IDLE_RESERVE_CORES}: the conservative floor stands")
    return float(PAUSE_S), (f"{spare:.1f} cores measure idle and free memory clears the guard, so "
                            f"the next pass starts after {PAUSE_S}s instead of {MIN_CYCLE_S}s")


def wait_for_memory(dept: str, min_free_mb: float = MIN_FREE_MB, max_wait_s: int = 1800) -> None:
    waited = 0
    while waited < max_wait_s:
        free = free_phys_mb()
        if free is None or free >= min_free_mb:
            return
        if waited == 0:
            log(dept, f"waiting: free memory {free:.0f}MB below {min_free_mb:.0f}MB")
        time.sleep(30)
        waited += 30


def heartbeat(dept: str, passes: int, status: str = "running", done_inc: int = 0) -> None:
    """The resident is a WORKER of the canonical registry (principal 2026-09-17)."""
    # A FILE ANY READER CAN SEE (2026-10-06): `RESIDENT_ORGANS.json` publishes it beside the lock
    # state, so "alive" and "working" are both readable without the registry database.
    with contextlib.suppress(Exception):
        _write_json(RESIDENT_STATE / f"dept_{dept}.json",
                    {"dept": dept, "pid": os.getpid(), "passes": passes, "status": status,
                     "beat_at": _iso()})
    try:
        root = str(DESK.parents[1])
        if root not in sys.path:
            sys.path.insert(0, root)
        from libs.moat import registry as reg
        reg.worker_heartbeat(f"dept:{dept}", kind="department_resident", department=dept,
                             status=status, pid=os.getpid(), current_campaign=f"pass {passes}",
                             campaigns_done_inc=done_inc)
    except Exception:
        pass
    # THE PROGRESS WATERMARK (LAWS.md 7). The heartbeat above says this process is alive; the
    # watermark says it is WORKING. A resident holding its lock with a frozen pass counter was
    # green to every liveness probe this desk had and is STALLED to the control plane.
    try:
        root = str(DESK.parents[1])
        if root not in sys.path:
            sys.path.insert(0, root)
        from libs.ops.control_plane import watermarks as wm
        wm.progress(f"resident:dept_{dept}", "passes", passes, run_id=f"pid:{os.getpid()}",
                    status=status)
    except Exception:
        pass


# ================================================================ THE WORK-SEEKING LANE
#: Where the lane keeps its checkpoints and heartbeats. Box state: small JSON, one per unit and
#: per lane, replaced atomically.
RESIDENT_STATE = DESK / "data" / "resident"
CENSUS_OUT = DESK / "reports" / "RESIDENT_ORGANS.json"
#: Seconds between looks at the work when nothing is READY. A look is a handful of stat calls
#: and one bounded tail read of the event log -- this is a poll for WORK, not a cadence.
UNIT_POLL_S = int(os.environ.get("DEPT_UNIT_POLL_S", "20"))
#: A unit's checkpoint keeps the core watchdog away for this long past its own watchdog age.
OWNERSHIP_GRACE_S = int(os.environ.get("DEPT_UNIT_GRACE_S", "1800"))
#: A lane whose heartbeat is older than this is dead to the watchdog.
LANE_STALE_S = int(os.environ.get("DEPT_LANE_STALE_S", "600"))
UNIT_PRIORITY = {"event": 3, "input": 2, "watchdog": 1}

#: THE UNITS: legs that were timer-only on MT5-HourlyCore (`CORE_LEGS`) and either feed the judge
#: or produce cells. `inputs` are DESK-relative paths whose change makes the unit READY;
#: `events` are `libs/ops/events.KINDS` that pre-empt; `min_gap_s` stops a unit whose input is
#: appended continuously from re-running back to back (the run is still taken the moment the gap
#: closes); `watchdog_s` is the age after which it runs with nothing new, as the hour did.
RESIDENT_UNITS: dict[str, dict[str, Any]] = {
    # THE DOCKET WRITER: the judge's only feeder. Every compiled, swept or deepened candidate
    # reaches the judge through it, so it runs when one of its SOURCES changes, not at :00.
    "merge_docket": {
        "dept": "discovery", "kind": "judge_feeder",
        "inputs": ("data/hypotheses/miner_candidates.json",
                   "data/hypotheses/orthogonal_candidates.json",
                   "data/hypotheses/moat_candidates.json",
                   "data/hypotheses/requeue_named.json",
                   "data/hypotheses/deepened_candidates.json",
                   "data/hypotheses/external_backtest_results.json",
                   "data/hypotheses/edge_search_results.json",
                   "data/hypotheses/coverage_search_results.json"),
        "events": ("CANDIDATES_COMPILED",), "min_gap_s": 600, "watchdog_s": 3600,
        "timeout_s": 3600},
    # Docket rows the judge cannot run, re-queued once they become runnable: a judge feeder.
    "requeue_unrunnable": {
        "dept": "discovery", "kind": "judge_feeder",
        "inputs": ("data/hypotheses/external_survivors.json",),
        "events": ("DOCKET_MERGED",), "min_gap_s": 600, "watchdog_s": 3600,
        "timeout_s": 1800},
    # Every certified mechanism on every chart: runs when a certificate lands.
    "timeframe_fanout": {
        "dept": "discovery", "kind": "producer",
        "inputs": ("reports/UNIVERSAL_SURVIVORS.json", "reports/COUNTERFACTUAL_TIMEFRAMES.json"),
        "events": ("GAUNTLET_SWEPT",), "min_gap_s": 300, "watchdog_s": 3600, "timeout_s": 900},
    # The quality-diversity frontier's proposals: runs when the judge's verdicts move.
    "qd_frontier": {
        "dept": "discovery", "kind": "producer",
        "inputs": ("data/hypotheses/gate_verdict_ledger.jsonl",
                   "reports/UNIVERSAL_SURVIVORS.json", "reports/AXIS_REGISTRY.json"),
        "events": ("GAUNTLET_SWEPT",), "min_gap_s": 600, "watchdog_s": 3600, "timeout_s": 1800},
    # Country-pack signals into cells: runs when the pack registry is re-mined.
    "pack_cells": {
        "dept": "intel", "kind": "producer",
        "inputs": ("data/asia_sources.json",),
        "events": ("INTEL_MINED",), "min_gap_s": 300, "watchdog_s": 3600, "timeout_s": 900},
    # Residual questions donated as cells: runs when a residual source report changes.
    "residual_queue": {
        "dept": "intel", "kind": "producer",
        "inputs": ("reports/STANDING_QUESTIONS.json", "reports/factor_residual.json",
                   "reports/OPPORTUNITY_GAP.json", "reports/POSTERIOR_ALPHA.json",
                   "reports/COUNTERFACTUAL_WORLD.json"),
        "events": ("INTEL_MINED",), "min_gap_s": 300, "watchdog_s": 3600, "timeout_s": 900},
    # Drains collected sources into the lake: runs when the collector's state moves.
    "source_drain": {
        "dept": "data", "kind": "producer",
        "inputs": ("data/asia_sources.json", "data/lake/collector_state.json",
                   "reports/SOURCE_EVIG.json"),
        "events": ("DATA_UPDATED",), "min_gap_s": 300, "watchdog_s": 3600, "timeout_s": 900},
}


def units_of(dept: str) -> list[str]:
    return [u for u, spec in RESIDENT_UNITS.items() if spec.get("dept") == dept]


def _now_utc() -> datetime:
    return datetime.now(tz=UTC)


def _iso(t: datetime | None = None) -> str:
    return (t or _now_utc()).isoformat(timespec="seconds")


def _parse(ts: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _write_json(path: Path, doc: dict[str, Any]) -> None:
    with contextlib.suppress(OSError):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, path)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def checkpoint_path(unit: str) -> Path:
    return RESIDENT_STATE / "units" / f"{unit}.json"


def lane_path(dept: str) -> Path:
    return RESIDENT_STATE / f"lane_{dept}.json"


def read_checkpoint(unit: str) -> dict[str, Any]:
    return _read_json(checkpoint_path(unit))


def input_watermark(spec: dict[str, Any]) -> tuple[int, list[str]]:
    """(newest mtime_ns across the unit's inputs, the inputs that exist). 0 when none exists."""
    newest, present = 0, []
    for rel in spec.get("inputs") or ():
        try:
            st = (DESK / rel).stat()
        except OSError:
            continue
        present.append(rel)
        newest = max(newest, int(st.st_mtime_ns))
    return newest, present


def _events_since(stamp: str | None, kinds: tuple[str, ...]) -> list[dict[str, Any]]:
    """Events of `kinds` after `stamp` from the desk's event log; [] when it is unreadable."""
    if not kinds:
        return []
    try:
        root = str(DESK.parents[1])
        if root not in sys.path:
            sys.path.insert(0, root)
        from libs.ops import events as ev
        return list(ev.since(stamp, kinds=kinds) or [])
    except Exception:
        return []


def unit_readiness(unit: str, spec: dict[str, Any], ck: dict[str, Any], *,
                   now: datetime | None = None,
                   events: list[dict[str, Any]] | None = None) -> tuple[int, str]:
    """(priority, why) -- 0 means not READY, and `why` says what it is waiting for."""
    at = now or _now_utc()
    started = _parse(ck.get("started_at"))
    finished = _parse(ck.get("finished_at"))
    if ck.get("status") == "running":
        until = _parse(ck.get("lease_until"))
        if until is not None and until > at:
            return 0, f"leased to pid {ck.get('pid')} until {ck.get('lease_until')}"
    gap = float(spec.get("min_gap_s") or 0)
    if started is not None and (at - started).total_seconds() < gap:
        return 0, f"min gap: started {(at - started).total_seconds():.0f}s ago (< {gap:.0f}s)"
    evs = events if events is not None else _events_since(
        ck.get("started_at"), tuple(spec.get("events") or ()))
    fresh = [e for e in evs if str(e.get("kind")) in tuple(spec.get("events") or ())
             and (started is None or ((_parse(e.get("at")) or at) > started))]
    if fresh:
        last = fresh[-1]
        return UNIT_PRIORITY["event"], f"event {last.get('kind')} at {last.get('at')}"
    wm, present = input_watermark(spec)
    if wm and wm > int(ck.get("consumed_watermark") or 0):
        return UNIT_PRIORITY["input"], f"input changed ({len(present)} input(s) watched)"
    wd = float(spec.get("watchdog_s") or 3600)
    if finished is None or (at - finished).total_seconds() >= wd:
        age = "never ran here" if finished is None else \
            f"last finished {(at - finished).total_seconds():.0f}s ago"
        return UNIT_PRIORITY["watchdog"], f"watchdog: {age} (>= {wd:.0f}s)"
    return 0, "idle: no event, no new input, inside its watchdog age"


def claim_unit_lease(unit: str):
    """The OS lease on one unit: a byte-range lock the kernel releases if this process dies."""
    LOCKS.mkdir(parents=True, exist_ok=True)
    path = LOCKS / f"unit_{unit}.lock"
    try:
        fh = open(path, "a+", encoding="utf-8")  # noqa: SIM115 -- held across the unit's run
    except OSError:
        return None
    try:
        if sys.platform == "win32":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    return fh


def run_unit(unit: str, *, trigger: str = "manual", dept: str = "") -> dict[str, Any]:
    """One unit, now: lease, run as HOURLY_PLAN=legs:<unit>, checkpoint. Never raises."""
    spec = RESIDENT_UNITS.get(unit)
    if spec is None:
        return {"unit": unit, "status": "unknown_unit"}
    lease = claim_unit_lease(unit)
    if lease is None:
        return {"unit": unit, "status": "leased_elsewhere"}
    timeout = int(spec.get("timeout_s") or 1800)
    wm, _present = input_watermark(spec)
    prev = read_checkpoint(unit)
    started = _now_utc()
    ck = {**prev, "unit": unit, "dept": spec.get("dept"), "kind": spec.get("kind"),
          "status": "running", "pid": os.getpid(), "host": socket.gethostname(),
          "started_at": _iso(started), "trigger": trigger,
          "lease_until": _iso(datetime.fromtimestamp(started.timestamp() + timeout, tz=UTC)),
          "watermark_at_start": wm}
    _write_json(checkpoint_path(unit), ck)
    env = dict(os.environ)
    env["HOURLY_PLAN"] = f"legs:{unit}"
    env.pop("HOURLY_BUDGET_S", None)          # an unbounded plan: rotation never defers a unit
    env["RESIDENT_UNIT"] = unit
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = BELOW_NORMAL_PRIORITY_CLASS
    t0 = time.monotonic()
    try:
        r = _run_tree([sys.executable, "-W", "ignore", str(CYCLE)], cwd=str(DESK), env=env,
                      timeout=timeout, check=False, **kwargs)
        rc, status = r.returncode, ("ok" if r.returncode == 0 else "exit")
    except subprocess.TimeoutExpired:
        rc, status = None, "timeout"
    except OSError as exc:
        rc, status = None, f"failed_to_start: {type(exc).__name__}"
    finally:
        with contextlib.suppress(OSError):
            lease.close()
    done = {**ck, "status": status, "rc": rc, "finished_at": _iso(),
            "seconds": round(time.monotonic() - t0, 1), "lease_until": None,
            "runs": int(prev.get("runs") or 0) + 1,
            "failures": int(prev.get("failures") or 0) + (0 if status == "ok" else 1)}
    # THE CHECKPOINT ADVANCES ONLY ON SUCCESS: a failed run leaves the input unconsumed, so the
    # next look takes it again -- and the core watchdog, reading a non-ok status, runs it too.
    if status == "ok":
        done["consumed_watermark"] = wm
    _write_json(checkpoint_path(unit), done)
    if dept:
        log(dept, f"unit {unit}: {status} rc={rc} in {done['seconds']}s ({trigger})")
    return done


def pick_unit(dept: str, *, now: datetime | None = None
              ) -> tuple[str | None, dict[str, tuple[int, str]]]:
    """The highest-priority READY unit of `dept` and every unit's readiness, for the census."""
    units = units_of(dept)
    kinds = tuple(sorted({k for u in units for k in (RESIDENT_UNITS[u].get("events") or ())}))
    cks = {u: read_checkpoint(u) for u in units}
    starts = [str(c.get("started_at")) for c in cks.values() if c.get("started_at")]
    evs = _events_since(min(starts) if len(starts) == len(units) else None, kinds)
    ready: dict[str, tuple[int, str]] = {}
    for u in units:
        ready[u] = unit_readiness(u, RESIDENT_UNITS[u], cks[u], now=now, events=evs)
    best = max((u for u in units if ready[u][0] > 0),
               key=lambda u: (ready[u][0], -units.index(u)), default=None)
    return best, ready


def lane_heartbeat(dept: str, status: str, *, current: str | None = None,
                   ready: dict[str, tuple[int, str]] | None = None, units_done: int = 0) -> None:
    _write_json(lane_path(dept), {
        "dept": dept, "pid": os.getpid(), "host": socket.gethostname(), "status": status,
        "beat_at": _iso(), "current_unit": current, "units_done": units_done,
        "ready": {u: {"priority": p, "why": w} for u, (p, w) in (ready or {}).items()}})


def feeder_lane(dept: str, stop: threading.Event, *, poll_s: int | None = None,
                max_units: int = 0) -> int:
    """The lane: take READY work in priority order until stopped. Returns units run."""
    done = 0
    poll = max(1, int(poll_s if poll_s is not None else UNIT_POLL_S))
    while not stop.is_set():
        try:
            unit, ready = pick_unit(dept)
        except Exception as exc:                       # the lane outlives a bad look
            log(dept, f"lane: look failed ({type(exc).__name__}: {exc})")
            unit, ready = None, {}
        if unit is None:
            lane_heartbeat(dept, "idle", ready=ready, units_done=done)
            stop.wait(poll)
            continue
        wait_for_memory(dept)
        lane_heartbeat(dept, "running", current=unit, ready=ready, units_done=done)
        run_unit(unit, trigger=ready[unit][1], dept=dept)
        done += 1
        lane_heartbeat(dept, "idle", ready=ready, units_done=done)
        with contextlib.suppress(Exception):
            write_census()
        if max_units and done >= max_units:
            break
    lane_heartbeat(dept, "stopped", units_done=done)
    return done


def resident_owns(unit: str, *, now: datetime | None = None) -> tuple[bool, str]:
    """Does the work-seeking lane own `unit` right now? The core watchdog's question.

    OWNED when the unit's lane is alive (heartbeat inside LANE_STALE_S) AND the unit is either
    running under a live lease or finished OK inside its watchdog age plus grace. Anything else
    -- no checkpoint, a failed run, a dead lane, an unreadable file -- is NOT owned, and the hourly
    clock runs the leg exactly as it did before the lane existed."""
    spec = RESIDENT_UNITS.get(unit)
    if spec is None:
        return False, "not a resident unit"
    at = now or _now_utc()
    lane = _read_json(lane_path(str(spec.get("dept"))))
    beat = _parse(lane.get("beat_at"))
    if beat is None or (at - beat).total_seconds() > LANE_STALE_S \
            or lane.get("status") == "stopped":
        return False, f"lane {spec.get('dept')} not alive (beat {lane.get('beat_at')})"
    ck = read_checkpoint(unit)
    if ck.get("status") == "running":
        until = _parse(ck.get("lease_until"))
        if until is not None and until > at:
            return True, f"running under lease until {ck.get('lease_until')}"
        return False, "lease expired without a finish"
    fin = _parse(ck.get("finished_at"))
    if ck.get("status") != "ok" or fin is None:
        return False, f"last run {ck.get('status') or 'never'}"
    age = (at - fin).total_seconds()
    limit = float(spec.get("watchdog_s") or 3600) + OWNERSHIP_GRACE_S
    if age > limit:
        return False, f"last ok {age:.0f}s ago, past {limit:.0f}s"
    return True, f"last ok {age:.0f}s ago (lane {spec.get('dept')} alive)"


# ------------------------------------------------------------------------------ the census
def _lock_probe(stem: str) -> dict[str, Any]:
    """Read-only, by `clock_fixer`'s rule: an unreadable lock is HELD (a live byte-range lock)."""
    p = LOCKS / f"{stem}.lock"
    if not p.exists():
        return {"state": "FREE"}
    try:
        first = p.read_text(encoding="utf-8", errors="replace").split()
    except OSError:
        return {"state": "HELD"}
    if first and first[0].isdigit():
        out: dict[str, Any] = {"state": "PID", "pid": int(first[0]),
                               "since": first[1] if len(first) > 1 else None}
        try:
            import psutil
            out["alive"] = bool(psutil.pid_exists(int(first[0])))
        except Exception:
            out["alive"] = "UNMEASURED"
        return out
    return {"state": "STALE"}


def build_census(*, now: datetime | None = None) -> dict[str, Any]:
    """WHICH ORGANS ARE RESIDENT AND WHICH ARE STILL ON A TIMER, with lease and heartbeat state.

    Derived from the component registry (`desks/mt5/ops/components.py`), the hourly cycle's own
    plan tables and the box task manifest -- never a list kept here -- plus this module's units."""
    at = now or _now_utc()
    try:
        root = str(DESK.parents[1])
        for pth in (str(DESK), root):
            if pth not in sys.path:
                sys.path.insert(0, pth)
        from ops import components as comp
        hc = comp._hourly_module()
        legs = list(comp.leg_names())
        depts = list(comp.department_names())
        manifest = comp.manifest_rows()
        task_of = {d: comp.department_task(d) for d in depts}
    except Exception as exc:
        return {"generated_at": _iso(at), "status": "UNMEASURED",
                "why": f"component registry unreadable ({type(exc).__name__}: {exc})"[:300]}
    core = set(getattr(hc, "CORE_LEGS", ()) or ())
    own = set(getattr(hc, "OWN_CLOCK_LEGS", ()) or ())
    dept_of = getattr(hc, "department_of", lambda _n: "rest")
    organs: dict[str, dict[str, Any]] = {}
    for leg in legs:
        if leg in RESIDENT_UNITS:
            d = str(RESIDENT_UNITS[leg]["dept"])
            mode = "resident_work_seeking"
            clock = f"{task_of.get(d, d)} lane (watchdog: MT5-HourlyCore)"
        elif leg in own:
            mode, clock = "own_task", "own box task (OWN_CLOCK_LEGS)"
        elif leg in core:
            mode, clock = "timer_only", "MT5-HourlyCore (hourly)"
        else:
            d = str(dept_of(leg))
            mode, clock = "resident_pass", f"{task_of.get(d, d)} (department {d} pass loop)"
        organs[leg] = {"mode": mode, "clock": clock}
    tasks: dict[str, dict[str, Any]] = {}
    for row in manifest:
        trig = str(row.get("trigger") or "").lower()
        kind = ("resident_keepalive" if ("resident" in trig or "keep-alive" in trig
                                         or "continuous" in trig) else "timer")
        tasks[str(row.get("name"))] = {"mode": kind, "trigger": row.get("trigger"),
                                       "runs": row.get("runs")}
    residents: dict[str, dict[str, Any]] = {}
    for d in depts:
        lane = _read_json(lane_path(d))
        beat = _parse(lane.get("beat_at"))
        hb = _read_json(RESIDENT_STATE / f"dept_{d}.json")
        hb_at = _parse(hb.get("beat_at"))
        residents[d] = {
            "task": task_of.get(d), "lock": _lock_probe(f"dept_{d}"),
            "heartbeat": ({"at": hb.get("beat_at"), "age_s": round((at - hb_at).total_seconds()),
                           "passes": hb.get("passes"), "status": hb.get("status")}
                          if hb_at else "UNMEASURED"),
            "units": units_of(d),
            "lane": ({"status": lane.get("status"), "beat_at": lane.get("beat_at"),
                      "age_s": round((at - beat).total_seconds()),
                      "alive": (at - beat).total_seconds() <= LANE_STALE_S
                      and lane.get("status") != "stopped",
                      "current_unit": lane.get("current_unit"),
                      "units_done": lane.get("units_done")}
                     if beat else ("UNMEASURED" if units_of(d) else "no units")),
        }
    units: dict[str, dict[str, Any]] = {}
    for u, spec in RESIDENT_UNITS.items():
        ck = read_checkpoint(u)
        prio, why = unit_readiness(u, spec, ck, now=at, events=[])
        owned, owned_why = resident_owns(u, now=at)
        units[u] = {"dept": spec["dept"], "kind": spec["kind"],
                    "in_cycle": u in organs, "status": ck.get("status") or "never_ran",
                    "started_at": ck.get("started_at"), "finished_at": ck.get("finished_at"),
                    "rc": ck.get("rc"), "seconds": ck.get("seconds"), "trigger": ck.get("trigger"),
                    "runs": ck.get("runs", 0), "failures": ck.get("failures", 0),
                    "lease": ({"pid": ck.get("pid"), "until": ck.get("lease_until")}
                              if ck.get("status") == "running" else None),
                    "lease_lock": _lock_probe(f"unit_{u}"),
                    "ready_now": {"priority": prio, "why": why},
                    "owned_by_resident": owned, "owned_why": owned_why,
                    "events": list(spec.get("events") or ()),
                    "inputs": list(spec.get("inputs") or ())}
    modes: dict[str, int] = {}
    for o in organs.values():
        modes[o["mode"]] = modes.get(o["mode"], 0) + 1
    timer_only = sorted(n for n, o in organs.items() if o["mode"] == "timer_only")
    return {
        "generated_at": _iso(at),
        "rule": ("an organ is RESIDENT when a 24/7 process takes its work (a department pass loop "
                 "or the work-seeking lane); TIMER_ONLY when only MT5-HourlyCore fires it. The "
                 "lane's units run on events and input changes with an OS lease and a "
                 "checkpointed input watermark; the hourly core pass is their watchdog. "
                 "UNMEASURED where no heartbeat or checkpoint exists, never alive."),
        "counts": {"legs": len(organs), **modes, "units": len(RESIDENT_UNITS),
                   "box_tasks": len(tasks),
                   "box_tasks_resident": sum(1 for t in tasks.values()
                                             if t["mode"] == "resident_keepalive"),
                   "box_tasks_timer": sum(1 for t in tasks.values() if t["mode"] == "timer")},
        "timer_only_legs": timer_only,
        "units": units,
        "residents": residents,
        "organs": organs,
        "box_tasks": tasks,
    }


def write_census(path: Path | None = None) -> dict[str, Any]:
    doc = build_census()
    _write_json(path or CENSUS_OUT, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dept", default=None)
    ap.add_argument("--once", action="store_true", help="one pass, then exit")
    ap.add_argument("--unit", default=None, help="run one RESIDENT_UNITS work unit now")
    ap.add_argument("--census", action="store_true",
                    help="write reports/RESIDENT_ORGANS.json and exit")
    a = ap.parse_args(argv)
    if a.census:
        doc = write_census()
        c = doc.get("counts") or {}
        print(f"resident census: {c.get('legs')} leg(s) -- {c.get('resident_work_seeking', 0)} "
              f"work-seeking, {c.get('resident_pass', 0)} in department passes, "
              f"{c.get('timer_only', 0)} timer-only, {c.get('own_task', 0)} on their own task "
              f"-> {CENSUS_OUT}", flush=True)
        return 0 if doc.get("counts") else 1
    if a.unit:
        res = run_unit(a.unit.strip(), trigger="manual", dept=str(
            (RESIDENT_UNITS.get(a.unit.strip()) or {}).get("dept") or "manual"))
        with contextlib.suppress(Exception):
            write_census()
        return 0 if res.get("status") == "ok" else 1
    if not a.dept:
        ap.error("--dept is required unless --unit or --census is given")
    dept = a.dept.strip().lower()
    handle = claim_singleton(dept)
    if handle is None:
        print(f"dept[{dept}]: another resident holds the slot; exiting", flush=True)
        return 0
    log(dept, f"resident started pid {os.getpid()}; pass timeout {PASS_TIMEOUT_S}s, "
              f"min cycle {MIN_CYCLE_S}s, recycle after {RECYCLE_PASSES} passes")
    passes = 0
    heartbeat(dept, 0)
    # THE LANE RIDES THIS PROCESS: same keep-alive task, same singleton, same log. `--once` is a
    # probe of one department pass and starts no lane.
    stop = threading.Event()
    lane: threading.Thread | None = None
    if units_of(dept) and not a.once:
        lane = threading.Thread(target=feeder_lane, args=(dept, stop), daemon=True,
                                name=f"lane:{dept}")
        lane.start()
        log(dept, f"work-seeking lane started over {', '.join(units_of(dept))}")
    try:
        while True:
            passes += 1
            wait_for_memory(dept)
            capacity = wait_for_capacity(dept)
            started = time.monotonic()
            heartbeat(dept, passes)
            try:
                # Recheck after admission: several residents may have waited on memory before
                # taking different slots.  The second check prevents the same snapshot race.
                wait_for_memory(dept)
                res = run_pass(dept)
            finally:
                with contextlib.suppress(OSError):
                    capacity.close()
            log(dept, f"pass {passes}: {res['status']} rc={res['rc']} in {res['seconds']}s")
            heartbeat(dept, passes, done_inc=1)
            if a.once:
                return 0 if res["status"] == "ok" else 1
            if passes >= RECYCLE_PASSES:
                log(dept, "recycling: the keep-alive trigger restarts a fresh resident")
                return 0
            elapsed = time.monotonic() - started
            floor, why = cycle_floor_s()
            nap = max(PAUSE_S, floor - elapsed)
            if floor < MIN_CYCLE_S:
                log(dept, f"next pass in {nap:.0f}s (floor {floor:.0f}s, not {MIN_CYCLE_S}s): "
                          f"{why}")
            time.sleep(nap)
    finally:
        stop.set()
        if lane is not None:
            # A recycling resident lets the lane FINISH the unit it holds -- killing it mid-write
            # is the one interruption this lane never makes. The lane takes no new unit once
            # `stop` is set, so the wait is at most one unit's own timeout.
            lane.join(timeout=max([int(RESIDENT_UNITS[u].get("timeout_s") or 1800)
                                   for u in units_of(dept)] or [5]))
        heartbeat(dept, passes, status="stopped")
        with contextlib.suppress(OSError):
            handle.close()


if __name__ == "__main__":
    raise SystemExit(main())
