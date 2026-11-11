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

    python department_resident.py --dept discovery       # loop until stopped
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
import time
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


def wait_for_capacity(dept: str, *, slots: int = CONCURRENT_PASSES,
                      poll_s: int = PAUSE_S):
    """Wait FIFO for bounded capacity; reacquiring departments rejoin at the tail."""
    announced = False
    ticket = _wait_ticket(dept)
    started = time.monotonic()
    reported = started
    try:
        while True:
            with contextlib.suppress(OSError):
                os.utime(ticket, None)  # the waiter's own heartbeat (see TICKET_STALE_S)
            queue = _waiters()
            if queue and queue[0][2] == ticket:
                handle = claim_capacity_slot(slots, dept=dept)
                if handle is not None:
                    if announced:
                        log(dept, f"capacity available after {time.monotonic() - started:.0f}s: "
                                  f"admitted to one of {slots} department slots")
                    return handle
            if not announced:
                log(dept, "waiting: bounded department slots or older pass(es) ahead")
                announced = True
                reported = time.monotonic()
            elif time.monotonic() - reported >= WAIT_REPORT_S:
                ahead = next((k for k, row in enumerate(queue) if row[2] == ticket), len(queue))
                log(dept, f"still waiting {time.monotonic() - started:.0f}s: {ahead} older "
                          f"waiter(s) ahead of {len(queue)}; slots: {_slot_census(slots)}")
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dept", required=True)
    ap.add_argument("--once", action="store_true", help="one pass, then exit")
    a = ap.parse_args(argv)
    dept = a.dept.strip().lower()
    handle = claim_singleton(dept)
    if handle is None:
        print(f"dept[{dept}]: another resident holds the slot; exiting", flush=True)
        return 0
    log(dept, f"resident started pid {os.getpid()}; pass timeout {PASS_TIMEOUT_S}s, "
              f"min cycle {MIN_CYCLE_S}s, recycle after {RECYCLE_PASSES} passes")
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
        heartbeat(dept, passes, status="stopped")
        with contextlib.suppress(OSError):
            handle.close()


if __name__ == "__main__":
    raise SystemExit(main())
