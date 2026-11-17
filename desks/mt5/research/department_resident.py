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

SUPERVISED, RESTART-ON-EXIT (BACKLOG 2026-09-29, "22 daemons on a 10-minute trigger"). The
department and forest tasks are 24/7 residents whose Windows trigger is a ten-minute keep-alive.
Until this change the loop process WAS the task, so every recycle (and every crash) left the
department dead until the next keep-alive slot: up to ten minutes of no passes, every RECYCLE_PASSES
passes, on 22 tasks. The task now starts a tiny SUPERVISOR that holds the department lock for its
whole life and runs the loop as a `--worker` child; when the worker exits -- recycled, crashed or
killed -- the supervisor starts the next one within RESPAWN_S, with a bounded backoff only for a
worker that keeps dying young. The keep-alive trigger is then only the supervisor's own watchdog,
and the 0x800710E0 refusals it records are that watchdog finding the supervisor alive. A worker
holds its own `deptworker_<name>.lock` (outside the `dept_*.lock` glob the registry reads), so a
worker orphaned by a killed supervisor is never doubled by the next one: the new supervisor waits
for it to finish instead. No trigger and no task
registration changes, so adoption alone rolls it out -- each running loop is replaced by a
supervisor the first time it recycles.

    python department_resident.py --dept discovery       # supervise the loop until stopped
    python department_resident.py --dept discovery --worker   # the loop itself (the supervisor's child)
    python department_resident.py --dept intel --once    # one pass (tests, probes)
"""
from __future__ import annotations

import argparse
import contextlib
import ctypes
import json
import os
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import UTC, datetime
from pathlib import Path

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
# lock in the kernel -- but a LIVE holder that hangs does not (2026-11-11: MT5-Dept-Mathlab sat
# 8 h on "waiting: bounded department slots or older pass(es) ahead").  Two leak paths, both
# now reclaimed on liveness and logged:
#   * a slot held by a live process past its OWN budget (pass timeout + the post-admission memory
#     wait + the tree-kill grace).  libs/ops/proctree.run leaves `with Popen(...)` through an
#     unbounded wait() when kill_tree cannot end the child, so the holder can sit inside run_pass
#     forever with the slot locked.  Such a slot is no longer counted: the head waiter takes the
#     slot's next generation file, so live, in-budget passes are still bounded at
#     CONCURRENT_PASSES and a hung one costs nothing;
#   * a FIFO ticket whose owner died without its `finally` (a hard kill: Task Scheduler stop,
#     reaper, reboot) and whose PID then reads as alive or unmeasurable.  `_ticket_alive` treats
#     unmeasured ownership as alive, and only the head ticket may claim, so that ticket blocked
#     every department forever even with free slots.  Waiters now refresh their ticket every
#     poll; a ticket not refreshed for TICKET_STALE_S has no owner polling it and is removed.
# The resident no longer reads this constant for admission: `derived_slot_count` measures the
# count at every claim (floor 3, ONE WAY UP) and an explicit DEPT_CONCURRENT_PASSES still wins.
# It stays the default for direct callers of claim_capacity_slot.
CONCURRENT_PASSES = max(1, int(os.environ.get("DEPT_CONCURRENT_PASSES", "3")))
#: A waiter touches its ticket every PAUSE_S; twenty missed polls means no live owner is waiting.
TICKET_STALE_S = max(600, 20 * PAUSE_S)
#: How long the resident itself can wait for memory after admission while holding a slot.
POST_ADMISSION_MEMORY_WAIT_S = 1800
#: proctree.run's communicate(timeout=10) after kill_tree, plus a margin for the log/heartbeat.
HOLDER_GRACE_S = 600
#: How often a still-waiting resident re-logs where it stands in the queue.
WAIT_REPORT_S = 1800
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
    return _claim_lock(f"dept_{dept}.lock")


def claim_worker(dept: str):
    """Hold data/locks/deptworker_<name>.lock for the worker's life; None when a worker -- an
    orphan of a killed supervisor, say -- is still running this department."""
    return _claim_lock(f"deptworker_{dept}.lock")


def _claim_lock(name: str):
    LOCKS.mkdir(parents=True, exist_ok=True)
    path = LOCKS / name
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


def holder_budget_s(timeout_s: int | None = None) -> int:
    """The longest a LIVE holder can legitimately keep a slot: its own measured budget."""
    t = PASS_TIMEOUT_S if timeout_s is None else int(timeout_s)
    return int(t + POST_ADMISSION_MEMORY_WAIT_S + HOLDER_GRACE_S)


def _proc_create_time(pid: int) -> float | None:
    try:
        import psutil
        return float(psutil.Process(pid).create_time())
    except Exception:
        return None


def _pid_state(pid: int, create_time: float | None) -> str:
    """'alive', 'dead' or 'unmeasured' -- a reused PID (another create time) is 'dead'."""
    try:
        import psutil
    except ImportError:
        return "unmeasured"
    try:
        proc = psutil.Process(int(pid))
        if not proc.is_running():
            return "dead"
        if create_time is not None and abs(proc.create_time() - float(create_time)) > 1.0:
            return "dead"
        return "alive"
    except Exception as exc:
        if type(exc).__name__ in ("NoSuchProcess", "ZombieProcess"):
            return "dead"
        return "unmeasured"


class CapacitySlot:
    """A held department-pass slot: the OS byte lock plus a readable holder record.

    The lock file's byte 0 is mandatorily locked on Windows, so nobody else can read who holds
    it; the sidecar `<lock>.holder.json` says (pid, dept, admitted, budget) for the reclaim
    check and for a box read. Closing removes the record first, then releases the lock.
    """

    def __init__(self, fh, lock_path: Path, record: dict) -> None:
        self.fh = fh
        self.lock_path = lock_path
        self.record = record

    def close(self) -> None:
        with contextlib.suppress(OSError):
            _holder_path(self.lock_path).unlink(missing_ok=True)
        self.fh.close()


def _slot_lock_path(index: int, generation: int) -> Path:
    if generation <= 0:
        return LOCKS / f"dept_capacity_{index}.lock"
    return LOCKS / f"dept_capacity_{index}.g{generation}.lock"


def _holder_path(lock_path: Path) -> Path:
    return lock_path.with_name(lock_path.name + ".holder.json")


def _read_holder(lock_path: Path) -> dict | None:
    try:
        row = json.loads(_holder_path(lock_path).read_text(encoding="utf-8"))
        return row if isinstance(row, dict) else None
    except (OSError, ValueError):
        return None


def _try_lock(path: Path):
    try:
        fh = open(path, "a+", encoding="utf-8")  # noqa: SIM115 -- held across the pass
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


def _holder_leaked(lock_path: Path, now: float) -> str | None:
    """Why a LOCKED slot's holder is leaked, or None while it is a live, in-budget pass.

    A dead holder's byte lock is released by the kernel, so a dead PID on a locked slot means
    a NEW holder is between taking the lock and writing its record: busy, never reclaimed. A
    missing or unreadable record is unmeasured, and unmeasured is busy too. Only a holder that
    is measurably the same live process, past its own budget, is reclaimed.
    """
    row = _read_holder(lock_path)
    if not row:
        return None
    try:
        pid = int(row["pid"])
        admitted = float(row["admitted_epoch"])
        budget = float(row.get("budget_s") or holder_budget_s())
    except (KeyError, TypeError, ValueError):
        return None
    age = now - admitted
    if age <= budget:
        return None
    state = _pid_state(pid, row.get("pid_create_time"))
    if state == "dead":
        return None
    return (f"holder pid {pid} dept[{row.get('dept', '?')}] {state}, holding "
            f"{age:.0f}s against its own budget of {budget:.0f}s")


_RECLAIMS_LOGGED: set[tuple[str, str]] = set()


def _holder_rss(pid: int) -> str:
    """The holder's resident set, psutil memory_info().rss, or UNMEASURED when unreadable."""
    try:
        import psutil
        return f"{psutil.Process(int(pid)).memory_info().rss / (1024 * 1024):.0f}MB"
    except Exception:
        return "UNMEASURED"


def _kill_tree(pid: int) -> dict:
    """libs/ops/proctree.kill_tree (never raises); a resident keeps running if it cannot load."""
    try:
        root = str(DESK.parents[1])
        if root not in sys.path:
            sys.path.insert(0, root)
        from libs.ops import proctree
        return dict(proctree.kill_tree(int(pid)))
    except Exception as exc:
        return {"pid": pid, "killed": 0, "method": None, "note": f"{type(exc).__name__}"}


def _reap_leaked_holder(lock_path: Path) -> tuple[str, str]:
    """Measure, then try ONCE to end, a holder already judged past its own budget.

    Reclaiming the slot stops a hung holder counting against the bound, but the process is
    still resident: without this the reclaim line hides a 4th live pass and whatever memory it
    holds. The RSS is logged so a box read sees the cost; kill_tree is attempted once (the
    caller logs once per holder) and its outcome is logged, so that process is then either
    visibly still there or gone.

    The kill is attempted ONLY on a holder measured to be the SAME process that took the slot
    (its recorded create time matches): a reused PID could be anything on the box -- the live
    terminal included -- and an unmeasured identity is never a licence to kill. Never self.
    """
    row = _read_holder(lock_path) or {}
    try:
        pid = int(row["pid"])
    except (KeyError, TypeError, ValueError):
        return "UNMEASURED", "not attempted: holder pid unreadable"
    rss = _holder_rss(pid)
    if pid == os.getpid():
        return rss, "not attempted: holder is this process"
    if row.get("pid_create_time") is None:
        return rss, "not attempted: holder create time UNMEASURED (PID reuse not excluded)"
    if _pid_state(pid, row.get("pid_create_time")) != "alive":
        return rss, "not attempted: holder identity UNMEASURED or gone"
    out = _kill_tree(pid)
    still = _pid_state(pid, row.get("pid_create_time"))
    return rss, (f"attempted pid {pid}: killed {out.get('killed', 0)} via "
                 f"{out.get('method')}{'; ' + str(out['note']) if out.get('note') else ''}; "
                 f"holder now {still}")


def claim_capacity_slot(slots: int = CONCURRENT_PASSES, dept: str = "?",
                        budget_s: int | None = None):
    """Claim one of the shared department-pass slots, or None when all are busy.

    A slot whose live holder is past its own budget is RECLAIMED (logged): the claimant takes
    that slot's next generation lock file, so the hung holder no longer counts against the
    bound and every in-budget pass is still bounded at `slots`.
    """
    LOCKS.mkdir(parents=True, exist_ok=True)
    budget = holder_budget_s() if budget_s is None else int(budget_s)
    for index in range(max(1, int(slots))):
        generation = 0
        while True:
            path = _slot_lock_path(index, generation)
            fh = _try_lock(path)
            if fh is not None:
                record = {"pid": os.getpid(), "pid_create_time": _proc_create_time(os.getpid()),
                          "dept": dept, "slot": index, "generation": generation,
                          "admitted_epoch": time.time(),
                          "admitted_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                          "budget_s": budget}
                with contextlib.suppress(OSError):
                    fh.seek(0)
                    fh.truncate()
                    fh.write(f"{os.getpid()} {record['admitted_utc']}\n")
                    fh.flush()
                with contextlib.suppress(OSError):
                    tmp = _holder_path(path).with_suffix(f".{os.getpid()}.tmp")
                    tmp.write_text(json.dumps(record), encoding="utf-8")
                    os.replace(tmp, _holder_path(path))
                return CapacitySlot(fh, path, record)
            why = _holder_leaked(path, time.time())
            if why is None:
                break  # a live, in-budget pass holds this slot
            key = (str(path), str((_read_holder(path) or {}).get("pid")))
            if key not in _RECLAIMS_LOGGED:  # once per leaked holder, not once per 30 s poll
                _RECLAIMS_LOGGED.add(key)
                rss, killed = _reap_leaked_holder(path)
                log(dept, f"RECLAIM department slot {index} generation {generation}: {why}; "
                          f"holder rss {rss}; kill_tree {killed}; "
                          f"claiming generation {generation + 1}")
            generation += 1
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


def _waiters() -> list[tuple[int, str, Path]]:
    """Every live contender, oldest first; abandoned tickets are removed and logged."""
    contenders: list[tuple[int, str, Path]] = []
    now = time.time()
    for path in LOCKS.glob("dept_wait_*.ticket"):
        try:
            _, _, stamp, pid, owner_dept = path.stem.split("_", 4)
            entered = int(stamp)
            owner = int(pid)
            if not _ticket_alive(path, owner):
                path.unlink(missing_ok=True)
                log(owner_dept, f"RECLAIM wait ticket {path.name}: owner pid {owner} not alive")
                continue
            idle = now - path.stat().st_mtime
            if idle > TICKET_STALE_S:
                # Liveness of the WAITER, not only of the PID: a live waiter refreshes its
                # ticket every poll. One untouched for twenty polls has no owner in the queue,
                # whatever psutil says about a (possibly reused, possibly unreadable) PID.
                path.unlink(missing_ok=True)
                log(owner_dept, f"RECLAIM wait ticket {path.name}: not refreshed for "
                                f"{idle:.0f}s (> {TICKET_STALE_S}s) by pid {owner}")
                continue
            contenders.append((entered, path.name, path))
        except (ValueError, OSError):
            # An unreadable ticket is not evidence of an available slot. Leave it visible.
            continue
    return sorted(contenders)


def _oldest_waiter() -> Path | None:
    """Return the oldest live contender; remove abandoned tickets only."""
    contenders = _waiters()
    return contenders[0][2] if contenders else None


def _slot_census(slots: int) -> str:
    """Who holds the slots right now, for the waiting log (a box read needs no other file)."""
    now = time.time()
    held = []
    for index in range(max(1, int(slots))):
        for lock in sorted(LOCKS.glob(f"dept_capacity_{index}*.lock")):
            row = _read_holder(lock)
            if row:
                age = now - float(row.get("admitted_epoch") or now)
                held.append(f"{lock.stem}={row.get('dept', '?')}/pid{row.get('pid')}/"
                            f"{age:.0f}s")
    return ", ".join(held) or "no holder records"


def wait_for_capacity(dept: str, *, slots: int | None = None,
                      poll_s: int = PAUSE_S):
    """Wait FIFO for bounded capacity; reacquiring departments rejoin at the tail.

    `slots=None` derives the count at every claim (`derived_slot_count`); an int fixes it.
    Every poll also feeds this resident's windowed idle-core history, so the head waiter
    judges extra slots on several minutes of readings, never one.
    """
    announced = False
    ticket = _wait_ticket(dept)
    started = time.monotonic()
    reported = started
    try:
        while True:
            with contextlib.suppress(OSError):
                os.utime(ticket, None)  # the waiter's own heartbeat (see TICKET_STALE_S)
            if slots is None:
                sample_idle_cores()
            queue = _waiters()
            count = slots
            if queue and queue[0][2] == ticket:
                derivation = "fixed by caller"
                if count is None:
                    count, derivation = derived_slot_count()
                handle = claim_capacity_slot(count, dept=dept)
                if handle is not None:
                    log(dept, f"admitted after {time.monotonic() - started:.0f}s to slot "
                              f"{handle.record['slot']} of {count} department slots "
                              f"({derivation})")
                    return handle
            if not announced:
                log(dept, "waiting: bounded department slots or older pass(es) ahead")
                announced = True
                reported = time.monotonic()
            elif time.monotonic() - reported >= WAIT_REPORT_S:
                ahead = next((k for k, row in enumerate(queue) if row[2] == ticket), len(queue))
                log(dept, f"still waiting {time.monotonic() - started:.0f}s: {ahead} older "
                          f"waiter(s) ahead of {len(queue)}; slots: "
                          f"{_slot_census(max(count or 0, DEPT_SLOTS_MAX))}")
                reported = time.monotonic()
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
    meter = PassMeter()
    meter.start()
    try:
        r = _run_tree([sys.executable, "-W", "ignore", str(CYCLE)], cwd=str(DESK),
                      env=env, timeout=timeout_s, check=False, **kwargs)
        res = {"rc": r.returncode, "seconds": round(time.monotonic() - t0, 1), "status": "ok"
               if r.returncode == 0 else "exit"}
    except subprocess.TimeoutExpired:
        res = {"rc": None, "seconds": round(time.monotonic() - t0, 1), "status": "timeout"}
    except OSError as exc:
        res = {"rc": None, "seconds": round(time.monotonic() - t0, 1),
               "status": f"failed_to_start: {type(exc).__name__}"}
    finally:
        meter.stop()
    record_pass_cost(dept, res, meter.summary(res["seconds"]))
    return res


#: What one department pass costs, measured by the resident that ran it (box-local, under logs/).
PASS_COST_NAME = "department_pass_cost.jsonl"
PASS_METER_INTERVAL_S = 5.0
#: The estimates below are read from the last PASS_COST_WINDOW measured passes once at least
#: PASS_COST_MIN_ROWS of them exist; the 90th percentile, so a heavy pass is what a slot is sized
#: for. Fewer rows keep the placeholders, which are deliberately heavy.
PASS_COST_WINDOW = 200
PASS_COST_MIN_ROWS = 10
PASS_COST_MIN_SAMPLES = 3


class PassMeter:
    """Samples this resident's child process tree while a pass runs: peak summed RSS and the
    CPU seconds each child had used when last seen (a child's CPU stops counting when it exits,
    so a short-lived child read only once is under-counted, never over-counted)."""

    def __init__(self, interval_s: float = PASS_METER_INTERVAL_S) -> None:
        self.interval_s = interval_s
        self.peak_rss_mb = 0.0
        self.cpu_by_proc: dict[tuple[int, float], float] = {}
        self.samples = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def sample(self) -> None:
        try:
            import psutil
        except ImportError:
            return
        try:
            kids = psutil.Process().children(recursive=True)
        except Exception:
            return
        rss = 0.0
        for k in kids:
            try:
                with k.oneshot():
                    ct = k.cpu_times()
                    key = (k.pid, k.create_time())
                    rss += k.memory_info().rss / 1048576.0
                self.cpu_by_proc[key] = max(self.cpu_by_proc.get(key, 0.0), ct.user + ct.system)
            except Exception:
                continue
        if kids:
            self.samples += 1
            self.peak_rss_mb = max(self.peak_rss_mb, rss)

    def _loop(self) -> None:
        while not self._stop.wait(self.interval_s):
            self.sample()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="pass-meter", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval_s + 5)

    def summary(self, seconds: float) -> dict:
        cpu_s = sum(self.cpu_by_proc.values())
        return {"cpu_s": round(cpu_s, 1), "peak_rss_mb": round(self.peak_rss_mb, 1),
                "cores": round(cpu_s / seconds, 3) if seconds > 0 else None,
                "samples": self.samples}


def record_pass_cost(dept: str, res: dict, cost: dict) -> None:
    row = {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"), "dept": dept,
           "status": res.get("status"), "seconds": res.get("seconds"), **cost}
    with contextlib.suppress(OSError):
        LOGS.mkdir(parents=True, exist_ok=True)
        with (LOGS / PASS_COST_NAME).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")


def _p90(values: list[float]) -> float:
    v = sorted(values)
    return v[min(len(v) - 1, int(0.9 * len(v)))]


def measured_pass_cost(path: Path | None = None) -> tuple[float | None, float | None, str]:
    """(p90 cores per pass, p90 peak MB per pass, why) from the measured ledger, or Nones while
    it is thinner than PASS_COST_MIN_ROWS usable rows."""
    path = LOGS / PASS_COST_NAME if path is None else path
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[-PASS_COST_WINDOW:]
    except OSError:
        return None, None, "pass cost UNMEASURED (no ledger)"
    cores: list[float] = []
    mbs: list[float] = []
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if (r.get("status") in ("ok", "exit", "timeout")
                and int(r.get("samples") or 0) >= PASS_COST_MIN_SAMPLES
                and isinstance(r.get("cores"), (int, float)) and r["cores"] > 0
                and isinstance(r.get("peak_rss_mb"), (int, float)) and r["peak_rss_mb"] > 0):
            cores.append(float(r["cores"]))
            mbs.append(float(r["peak_rss_mb"]))
    if len(cores) < PASS_COST_MIN_ROWS:
        return None, None, (f"pass cost UNMEASURED ({len(cores)} usable passes; needs "
                            f"{PASS_COST_MIN_ROWS})")
    return _p90(cores), _p90(mbs), f"pass cost p90 over {len(cores)} measured passes"


def pass_estimates(path: Path | None = None) -> tuple[float, float, str]:
    """Cores and MB one pass is sized at: an env override wins, then the measured p90, then the
    heavy placeholders."""
    c_env = os.environ.get("DEPT_PASS_CORES_ESTIMATE", "").strip()
    m_env = os.environ.get("DEPT_PASS_MB_ESTIMATE", "").strip()
    c_meas, m_meas, why = measured_pass_cost(path)
    try:
        cores = float(c_env) if c_env else (c_meas if c_meas is not None
                                            else PASS_CORES_ESTIMATE)
        mb = float(m_env) if m_env else (m_meas if m_meas is not None else PASS_MB_ESTIMATE)
    except ValueError:
        cores, mb = PASS_CORES_ESTIMATE, PASS_MB_ESTIMATE
    src = "env override" if (c_env or m_env) else ("measured" if c_meas is not None
                                                   else "placeholder")
    # a pass can never be sized at zero: that would divide the room by nothing
    return max(0.1, cores), max(64.0, mb), f"{src}; {why}"


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


#: TODAY'S BOUND IS THE FLOOR. The derived slot count is ONE WAY: it only ever rises above the
#: three slots this file has always had, and only while the box measurably has room.
DEPT_SLOTS_FLOOR = 3
#: A FILE-COUNT bound, not a research cap: every slot index owns a `dept_capacity_<i>` lock plus
#: its reclaim generations and holder records, and every claim and census walks them. Eight keeps
#: that directory and the per-poll scan bounded; the measured inputs below decide the count
#: beneath it, and DEPT_CONCURRENT_PASSES remains the manual override for the box.
DEPT_SLOTS_MAX = 8
#: Cores kept free for the MONEY tasks, on top of the terminal's IDLE_RESERVE_CORES. Measured on
#: the trading box 2026-11-11: around 01:42Z total CPU read 90-95%, the allocator alone held
#: about 4.8 cores, and in the crunch 00:41-01:17Z E8-Gold and TerminalBoot were killed at their
#: time limits. BELOW_NORMAL priority for department children did not save them, so an extra
#: slot is only ever added while the windowed idle cores still leave this reserve AND the
#: terminal's free. Generous on purpose: six covers the allocator's measured 4.8 with margin.
MONEY_RESERVE_CORES = float(os.environ.get("DEPT_MONEY_RESERVE_CORES", "6"))
#: PLACEHOLDERS, used only until the box has measured its own passes: every pass now records
#: its tree's peak RSS and CPU seconds / wall seconds (PassMeter -> logs/department_pass_cost.jsonl)
#: and `pass_estimates` sizes a slot at the p90 of those once PASS_COST_MIN_ROWS exist. Until
#: then these are deliberately heavy, so the derivation under-admits rather than over-admits.
#: DEPT_PASS_CORES_ESTIMATE / DEPT_PASS_MB_ESTIMATE in the environment still win over both.
PASS_CORES_ESTIMATE = 2.0
PASS_MB_ESTIMATE = 8192.0
#: Idle cores are read over a WINDOW, never one sample: the minimum of the samples a resident
#: took while waiting, spread over at least IDLE_WINDOW_MIN_SPAN_S. A one-second read at a quiet
#: instant is exactly how a crunch like 2026-11-11 00:41Z would be missed.
IDLE_WINDOW_S = 600
IDLE_WINDOW_MIN_SPAN_S = 180
IDLE_WINDOW_MIN_SAMPLES = 5
_IDLE_SAMPLES: deque[tuple[float, float]] = deque(maxlen=256)


def sample_idle_cores(now: float | None = None) -> None:
    """Append one spare_cores() reading to this resident's rolling history (if measurable)."""
    t = time.time() if now is None else float(now)
    value = spare_cores()
    if value is not None:
        _IDLE_SAMPLES.append((t, float(value)))
    while _IDLE_SAMPLES and t - _IDLE_SAMPLES[0][0] > IDLE_WINDOW_S:
        _IDLE_SAMPLES.popleft()


def windowed_idle_cores(now: float | None = None) -> tuple[float | None, str]:
    """The MINIMUM idle cores across the window, or None (UNMEASURED) when the window is thin."""
    t = time.time() if now is None else float(now)
    rows = [(ts, v) for ts, v in _IDLE_SAMPLES if t - ts <= IDLE_WINDOW_S]
    if not rows:
        return None, "idle cores UNMEASURED (no samples in window)"
    span = rows[-1][0] - rows[0][0]
    if len(rows) < IDLE_WINDOW_MIN_SAMPLES or span < IDLE_WINDOW_MIN_SPAN_S:
        return None, (f"idle cores UNMEASURED ({len(rows)} samples over {span:.0f}s; needs "
                      f"{IDLE_WINDOW_MIN_SAMPLES} over {IDLE_WINDOW_MIN_SPAN_S}s)")
    low = min(v for _, v in rows)
    return low, f"idle cores min {low:.1f} over {len(rows)} samples / {span:.0f}s"


def derived_slot_count(now: float | None = None) -> tuple[int, str]:
    """How many department slots a claim may scan right now, and the inputs that said so.

        slots = clamp(max(FLOOR, min(by_cores, by_memory)), FLOOR, DEPT_SLOTS_MAX)
        by_cores  = floor((windowed min idle cores - IDLE_RESERVE_CORES - MONEY_RESERVE_CORES)
                          / PASS_CORES_ESTIMATE)
        by_memory = floor((free_phys_mb - MIN_FREE_MB) / PASS_MB_ESTIMATE)

    An explicit DEPT_CONCURRENT_PASSES wins (the box's manual override). Anything UNMEASURED
    gives the floor, which is exactly today's three. Conservative by construction: both readings
    are taken WHILE the current passes run, so they measure room for MORE passes, yet the count
    is compared against ALL holders -- a slot is added only when the room clears the whole count.
    """
    override = os.environ.get("DEPT_CONCURRENT_PASSES")
    if override is not None and override.strip():
        try:
            return max(1, int(override)), f"DEPT_CONCURRENT_PASSES={override.strip()} override"
        except ValueError:
            pass
    idle, idle_why = windowed_idle_cores(now)
    free = free_phys_mb()
    free_why = "free memory UNMEASURED" if free is None else f"free {free:.0f}MB"
    if idle is None or free is None:
        return DEPT_SLOTS_FLOOR, f"floor {DEPT_SLOTS_FLOOR}: {idle_why}; {free_why}"
    per_core, per_mb, est_why = pass_estimates()
    by_cores = int((idle - IDLE_RESERVE_CORES - MONEY_RESERVE_CORES) // per_core)
    by_memory = int((free - MIN_FREE_MB) // per_mb)
    count = min(DEPT_SLOTS_MAX, max(DEPT_SLOTS_FLOOR, min(by_cores, by_memory)))
    # What the money reserve cost this claim, in slots (the reserve's missed-compute line).
    unreserved = min(DEPT_SLOTS_MAX, max(DEPT_SLOTS_FLOOR, min(
        int((idle - IDLE_RESERVE_CORES) // per_core), by_memory)))
    return count, (f"{count} = max({DEPT_SLOTS_FLOOR}, min(by_cores {by_cores}, by_memory "
                   f"{by_memory})) cap {DEPT_SLOTS_MAX}; {idle_why} less reserves "
                   f"{IDLE_RESERVE_CORES}+{MONEY_RESERVE_CORES:g} at {per_core:g} cores/pass; "
                   f"{free_why} less {MIN_FREE_MB:.0f} at {per_mb:.0f}MB/pass ({est_why}); "
                   f"money reserve withheld {unreserved - count} slot(s)")


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
    # watermark says a pass COMPLETED. Process-local pass numbers restart at one after recycling;
    # the durable counter must continue instead of regressing behind its previous high water.
    # Starting or stopping a pass is liveness, not completed work, and cannot refresh this clock.
    if done_inc <= 0:
        return
    try:
        root = str(DESK.parents[1])
        if root not in sys.path:
            sys.path.insert(0, root)
        from libs.ops.control_plane import watermarks as wm
        component = f"resident:dept_{dept}"
        previous = wm.read(component) or {}
        wm.progress(component, "passes", int(previous.get("value") or 0) + done_inc,
                    run_id=f"pid:{os.getpid()}", status=status, local_pass=passes)
    except Exception:
        pass


#: A worker that recycled cleanly is replaced after this many seconds -- not after the next
#: keep-alive slot, which was up to ten minutes of a dead department.
RESPAWN_S = int(os.environ.get("DEPT_RESPAWN_S", "5"))
#: A worker that dies younger than this counts toward the crash backoff; one that lived longer
#: resets it. The backoff doubles from CRASH_BACKOFF_S and never exceeds CRASH_BACKOFF_MAX_S, so a
#: department broken by a bad adoption retries at least every five minutes -- faster than the old
#: keep-alive -- without spinning a crash loop on the box that trades.
YOUNG_DEATH_S = 600
CRASH_BACKOFF_S = 15
CRASH_BACKOFF_MAX_S = 300
#: The worker's exit code when another worker of this department is still alive.
WORKER_BUSY_RC = 3
#: How long to wait for an orphaned worker before asking again.
WORKER_BUSY_WAIT_S = 60


#: THE SCHEDULER'S OWN CEILING ON A TASK RUN (audit of #1004). A supervisor lives as long as its
#: task does, so a task ExecutionTimeLimit -- 72 h is the scheduler's default, and the hand-made
#: resident tasks were never shown to carry anything else -- would kill it mid-run (0x41306) and
#: orphan its worker. The supervisor therefore retires ITSELF, cleanly, after a worker exit and
#: well inside the limit; the keep-alive starts a fresh one. An unreadable limit is taken to be
#: this default: assuming "no limit" would be the guess that gets the supervisor killed.
DEFAULT_TASK_LIMIT_S = 72 * 3600
#: The environment variable a supervisor hands its worker: the epoch second after which the
#: worker recycles at the end of its current pass, so the supervisor is free to retire.
RETIRE_AT_ENV = "RESIDENT_RETIRE_AT"


def _iso_duration_s(text: str) -> int | None:
    """`PT72H`, `P3D`, `PT4H30M`, `PT0S` -> seconds (0 means "no limit"); None if unparseable."""
    import re
    m = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", text.strip())
    if not m or not any(m.groups()):
        return None
    d, h, mi, sec = (int(g or 0) for g in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + sec


def task_time_limit_s(task: str, *, run=None) -> int:
    """The ExecutionTimeLimit of `task` in seconds, 0 when the task has none. Falls back to
    DEFAULT_TASK_LIMIT_S whenever the scheduler cannot be read (off-box, timeout, odd XML)."""
    if sys.platform != "win32" and run is None:
        return DEFAULT_TASK_LIMIT_S
    query = run or (lambda: subprocess.run(["schtasks", "/Query", "/TN", task, "/XML"],
                                           capture_output=True, text=True, timeout=60,
                                           check=False).stdout)
    try:
        xml = str(query() or "")
    except (OSError, subprocess.SubprocessError):
        return DEFAULT_TASK_LIMIT_S
    import re
    m = re.search(r"<ExecutionTimeLimit>([^<]+)</ExecutionTimeLimit>", xml)
    if not m:
        # no element in a readable definition is the scheduler's default, i.e. 72 h
        return DEFAULT_TASK_LIMIT_S
    secs = _iso_duration_s(m.group(1))
    return DEFAULT_TASK_LIMIT_S if secs is None else secs


def retire_after_s(limit_s: int, pass_ceiling_s: float) -> float | None:
    """How long a supervisor may live under a task limit; None when the task has no limit.

    The worker is asked to recycle at this point and may then finish one pass of up to
    `pass_ceiling_s`, so a full pass plus thirty minutes of slack is kept below the limit -- and
    never less than half the limit, so a short limit still gets a working supervisor.
    """
    if limit_s <= 0:
        return None
    return float(max(limit_s / 2.0, limit_s - pass_ceiling_s - 1800.0))


def worker_should_retire(now_epoch: float | None = None) -> bool:
    """True once the supervisor's retirement point has passed (read from RETIRE_AT_ENV)."""
    raw = os.environ.get(RETIRE_AT_ENV, "")
    try:
        at = float(raw)
    except ValueError:
        return False
    return (time.time() if now_epoch is None else now_epoch) >= at


def source_digest(*paths: Path) -> str:
    """One digest over the supervisor's own source files; "" when one cannot be read."""
    import hashlib
    h = hashlib.sha256()
    try:
        for p in paths or (Path(__file__),):
            h.update(Path(p).read_bytes())
    except OSError:
        return ""
    return h.hexdigest()


def _spawn_worker(dept: str) -> int:
    r = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--dept", dept, "--worker"],
                       cwd=str(DESK), check=False)
    return int(r.returncode)


def respawn_delay(rc: int | None, lived_s: float, young_deaths: int) -> tuple[float, int]:
    """(seconds before the next worker, the updated young-death count). Pure, so it is pinned."""
    if rc == WORKER_BUSY_RC:
        return float(WORKER_BUSY_WAIT_S), young_deaths
    if rc == 0:
        return float(RESPAWN_S), 0
    deaths = young_deaths + 1 if lived_s < YOUNG_DEATH_S else 1
    return float(min(CRASH_BACKOFF_MAX_S, CRASH_BACKOFF_S * 2 ** (deaths - 1))), deaths


def run_supervised(name: str, *, claim, spawn, say, sleep=time.sleep, clock=time.monotonic,
                   digest, max_workers: int | None = None, retire_after: float | None = None,
                   wall=time.time) -> int:
    """THE ONE SUPERVISOR every 24/7 resident family shares (departments, forests, moat swarms).

    `claim()` takes the resident's singleton lock (None: another supervisor or a pre-supervisor
    loop holds it, so this one exits 0 and the keep-alive stays a no-op). `spawn()` runs one worker
    to its exit and returns its code; the next worker starts after `respawn_delay`. Returns only
    when `digest()` changes (its code was adopted, so the keep-alive starts the new supervisor),
    when `retire_after` seconds have passed (it retires inside its task's ExecutionTimeLimit
    rather than be killed with a worker still running), or when `max_workers` (tests) is reached.
    """
    started_digest = digest()
    handle = claim()
    if handle is None:
        print(f"{name}: another resident holds the slot; exiting", flush=True)
        return 0
    retire_at = None if retire_after is None else wall() + retire_after
    if retire_at is not None:
        os.environ[RETIRE_AT_ENV] = f"{retire_at:.0f}"   # the worker inherits it
        say(f"retires after {retire_after / 3600:.1f}h, inside its task's time limit")
    say(f"supervisor started pid {os.getpid()}: restarts the worker on exit "
        f"(respawn {RESPAWN_S}s, crash backoff {CRASH_BACKOFF_S}-{CRASH_BACKOFF_MAX_S}s)")
    workers = deaths = 0
    try:
        while max_workers is None or workers < max_workers:
            workers += 1
            t0 = clock()
            try:
                rc: int | None = spawn()
            except OSError as exc:
                say(f"worker failed to start: {type(exc).__name__}: {exc}")
                rc = None
            lived = clock() - t0
            delay, deaths = respawn_delay(rc, lived, deaths)
            say(f"worker {workers} exited rc={rc} after {lived:.0f}s; next in {delay:.0f}s")
            if started_digest and digest() not in ("", started_digest):
                say("supervisor source changed on disk: exiting so the keep-alive starts the "
                    "adopted code")
                return 0
            if retire_at is not None and wall() >= retire_at:
                say("retiring inside the task's time limit, with no worker running: the "
                    "keep-alive starts a fresh supervisor")
                return 0
            sleep(delay)
        return 0
    finally:
        if retire_at is not None:
            os.environ.pop(RETIRE_AT_ENV, None)
        with contextlib.suppress(OSError):
            handle.close()


def supervise(dept: str, *, spawn=None, sleep=time.sleep, clock=time.monotonic,
              digest=None, max_workers: int | None = None,
              retire_after: float | None = None) -> int:
    """Hold the department and keep exactly one worker running, restarting it on every exit."""
    run_one = spawn or _spawn_worker
    if retire_after is None:
        retire_after = retire_after_s(task_time_limit_s(_task_name(dept)), PASS_TIMEOUT_S)
    return run_supervised(f"dept[{dept}]", claim=lambda: claim_singleton(dept),
                          spawn=lambda: run_one(dept), say=lambda m: log(dept, m),
                          sleep=sleep, clock=clock, digest=digest or source_digest,
                          max_workers=max_workers, retire_after=retire_after)


def _task_name(dept: str) -> str:
    """This department's Windows task, from the component registry; a guess only when it fails
    to import -- and a wrong name merely falls back to the 72 h default limit."""
    try:
        # Loaded by FILE, never as bare `ops`: the repo root has an `ops/` too, and a bare import
        # resolves to whichever comes first on sys.path (test_gateway_loop_finds_libs pins this).
        import importlib.util
        spec = importlib.util.spec_from_file_location("_dr_components",
                                                      DESK / "ops" / "components.py")
        if spec is None or spec.loader is None:
            raise ImportError("desks/mt5/ops/components.py has no loader")
        components = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(components)
        return str(components.department_task(dept))
    except Exception:
        return "MT5-Dept-" + "".join(p.capitalize() for p in dept.split("_") if p)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dept", required=True)
    ap.add_argument("--once", action="store_true", help="one pass, then exit")
    ap.add_argument("--worker", action="store_true",
                    help="run the loop itself (the supervisor's child); recycles by exiting")
    a = ap.parse_args(argv)
    dept = a.dept.strip().lower()
    if not a.once and not a.worker:
        return supervise(dept)
    handle = claim_worker(dept) if a.worker else claim_singleton(dept)
    if handle is None:
        print(f"dept[{dept}]: another {'worker' if a.worker else 'resident'} holds the slot; "
              "exiting", flush=True)
        return WORKER_BUSY_RC if a.worker else 0
    log(dept, f"{'worker' if a.worker else 'resident'} started pid {os.getpid()}; pass timeout "
              f"{PASS_TIMEOUT_S}s, min cycle {MIN_CYCLE_S}s, recycle after {RECYCLE_PASSES} passes")
    passes = 0
    heartbeat(dept, 0)
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
                log(dept, "recycling: the supervisor starts a fresh worker")
                return 0
            if a.worker and worker_should_retire():
                log(dept, "recycling early: the supervisor is retiring inside its task limit")
                return 0
            elapsed = time.monotonic() - started
            floor, why = cycle_floor_s()
            nap = max(PAUSE_S, floor - elapsed)
            if floor < MIN_CYCLE_S:
                log(dept, f"next pass in {nap:.0f}s (floor {floor:.0f}s, not {MIN_CYCLE_S}s): "
                          f"{why}")
            time.sleep(nap)
    finally:
        heartbeat(dept, passes, status="stopped")
        with contextlib.suppress(OSError):
            handle.close()


if __name__ == "__main__":
    raise SystemExit(main())
