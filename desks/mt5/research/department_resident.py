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
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
CYCLE = DESK / "research" / "hourly_cycle.py"
LOCKS = DESK / "data" / "locks"
LOGS = DESK / "logs"
# 90 min (2026-11-03). Three hours let two hung passes hold two of three slots for an afternoon
# while twenty departments queued. The tail of a long department is not lost at the shorter
# clock: leg_rotation plans strictly inside PASS_BUDGET_FILL of it, a leg whose measured cost no
# longer fits yields, and every leg that did not finish leads the next pass oldest-first.
PASS_TIMEOUT_S = int(os.environ.get("DEPT_PASS_TIMEOUT_S", "5400"))
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
#
# SIX SLOTS, ADMITTED BY MEASURED CPU (2026-11-03). Three slots on an 18-core box with 65 GB free
# left twenty departments queued for hours. The cap is now six, but a pass is admitted only while
# (logical cores - JUDGE_RESERVED_CORES - busy non-judge cores) >= MIN_FREE_CORES_TO_ADMIT, so the
# judge keeps its eight and mining is never cut: a busy box simply admits nothing new. An
# unmeasurable CPU falls back to LEGACY_SLOTS -- unmeasured never licenses more than before.
CONCURRENT_PASSES = max(1, int(os.environ.get("DEPT_CONCURRENT_PASSES", "6")))
LEGACY_SLOTS = 3
JUDGE_RESERVED_CORES = float(os.environ.get("DEPT_JUDGE_RESERVED_CORES", "8"))
MIN_FREE_CORES_TO_ADMIT = float(os.environ.get("DEPT_MIN_FREE_CORES", "2"))
# THE PASS HEARTBEAT. The child touches it at every leg boundary and the resident touches it
# whenever the child's process tree burns CPU. A pass with neither for HEARTBEAT_STALL_S is hung:
# its own resident kills its own child tree, releases the slot and requeues the department.
HEARTBEAT_STALL_S = int(os.environ.get("DEPT_HEARTBEAT_STALL_S", "1800"))
HEARTBEAT_POLL_S = int(os.environ.get("DEPT_HEARTBEAT_POLL_S", "30"))
CPU_PROGRESS_S = 1.0          # child-tree CPU seconds per poll that count as progress
# I/O is progress too: a leg waiting on a remote queue (CDS/ERA5), a slow paginated fetch or a
# streamed download burns almost no CPU but moves bytes. Any tree I/O (read, write, and on
# Windows other_bytes, which includes network) since the last poll counts as alive.
IO_PROGRESS_BYTES = int(os.environ.get("DEPT_IO_PROGRESS_BYTES", "1"))
# The same leg reclaimed this many passes in a row never completes: DEPT_QUEUE.json goes RED.
RECLAIM_REPEAT_N = 2
RECLAIM_REPEAT_FRESH_S = 24 * 3600
# A ticket that has waited longer than this is STARVED: DEPT_QUEUE.json goes RED.
STARVATION_S = int(os.environ.get("DEPT_STARVATION_S", "7200"))
REPORT_EVERY_S = 60
REPORTS = DESK / "reports"
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


_TICKET = re.compile(r"^dept_wait_(\d+)_(\d+)_(.+)\.ticket$", re.IGNORECASE)
ALIVE, DEAD, UNMEASURED = "alive", "dead", "unmeasured"


def _parse_ticket(path: Path) -> tuple[int, int, str] | None:
    """(entered ns, owner pid, dept) from the ticket's NAME, the ticket's only clock. st_mtime is
    not read, so an ACL hiding a SYSTEM-owned file's attributes cannot reorder or drop it."""
    m = _TICKET.match(path.name)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), m.group(3)


def _owner_state_os(pid: int) -> str:
    """Owner liveness without psutil. Only a definite answer is DEAD; refusal is UNMEASURED."""
    if sys.platform == "win32":
        try:
            k32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            handle = k32.OpenProcess(0x1000, False, int(pid))  # QUERY_LIMITED_INFORMATION
            if not handle:
                return DEAD if k32.GetLastError() == 87 else UNMEASURED  # 87: no such pid
            try:
                code = ctypes.c_ulong()
                if not k32.GetExitCodeProcess(handle, ctypes.byref(code)):
                    return UNMEASURED
                return ALIVE if code.value == 259 else DEAD               # 259: STILL_ACTIVE
            finally:
                k32.CloseHandle(handle)
        except Exception:
            return UNMEASURED
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return DEAD
    except OSError:
        return UNMEASURED
    return ALIVE


def _owner_state(pid: int, entered_s: float) -> str:
    """ALIVE, DEAD or UNMEASURED for a ticket's owner.

    THE EUROPE SKIP (measured 2026-11-03). The old check answered a bare bool and folded every
    OSError into "dead"; the caller then tried to delete the ticket, and on a SYSTEM-owned ticket
    seen from a user-account resident the delete is refused, the refusal was caught by
    `except OSError: continue`, and the ticket silently left the contention. Europe's own SYSTEM
    resident saw itself at the head while every other resident admitted the next ticket. DEAD now
    needs proof -- no such process, or a process born after the ticket (pid reuse); access
    denied, a raw WinError or any other doubt is UNMEASURED, and UNMEASURED keeps its place.
    """
    if int(pid) == os.getpid():
        return ALIVE
    try:
        import psutil
    except ImportError:
        return _owner_state_os(pid)
    try:
        created = psutil.Process(int(pid)).create_time()
    except psutil.NoSuchProcess:         # ZombieProcess is a NoSuchProcess: it will never poll
        return DEAD
    except Exception:
        return UNMEASURED
    try:
        if float(created) > float(entered_s) + 2.0:
            return DEAD                  # the pid was reused after the ticket was written
    except (TypeError, ValueError):
        return UNMEASURED
    return ALIVE


def _ticket_alive(path: Path, pid: int) -> bool:
    """A crashed waiter must not block the queue forever; an unreadable one keeps its turn."""
    parsed = _parse_ticket(path)
    entered_s = parsed[0] / 1e9 if parsed else time.time()
    return _owner_state(pid, entered_s) != DEAD


def _queue() -> tuple[list[dict], list[str]]:
    """Every live-or-unmeasured contender, STRICTLY by ticket time, and the names set aside.

    Only a ticket whose owner is proven DEAD leaves the contention, and it leaves whether or not
    the delete succeeds (a dead owner can never take its turn). A ticket whose owner cannot be
    read stays in line -- skipping it is exactly how a later ticket was admitted ahead of it.
    """
    contenders: list[dict] = []
    set_aside: list[str] = []
    try:
        paths = list(LOCKS.glob("dept_wait_*.ticket"))
    except OSError:
        return [], ["UNREADABLE: the ticket directory could not be listed"]
    for path in paths:
        parsed = _parse_ticket(path)
        if parsed is None:
            set_aside.append(f"{path.name}: malformed name")
            continue
        entered, owner, dept = parsed
        try:
            alive = _ticket_alive(path, owner)
        except Exception:
            alive = True
        if not alive:
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                set_aside.append(f"{path.name}: dead owner, delete refused ({type(exc).__name__})")
            continue
        contenders.append({"entered": entered, "name": path.name, "path": path,
                           "pid": owner, "dept": dept})
    contenders.sort(key=lambda c: (c["entered"], c["name"]))
    return contenders, set_aside


def _oldest_waiter() -> Path | None:
    """Return the oldest live contender; remove abandoned process tickets only."""
    contenders, _ = _queue()
    return contenders[0]["path"] if contenders else None


def _logical_cores() -> int | None:
    try:
        import psutil
        return int(psutil.cpu_count(logical=True) or 0) or os.cpu_count()
    except Exception:
        return os.cpu_count()


def busy_cores() -> tuple[float | None, str]:
    """Cores in use by everything except the judge's own reservation, or None when unmeasurable.

    The repo's convention first (`judging_throughput.measure_cpu`: psutil per process, the
    gauntlet tree attributed to the judge), so the judge's reserved eight are not counted twice;
    judge use ABOVE its reservation is counted as busy. Fallback: psutil per-core percentages
    summed, counting everything as busy -- conservative, never optimistic.
    """
    try:
        research = str(DESK / "research")
        if research not in sys.path:
            sys.path.insert(0, research)
        from judging_throughput import measure_cpu
        cpu = measure_cpu(1.0)
        other, judge = cpu.get("busy_other_cores"), cpu.get("busy_judge_cores")
        if isinstance(other, (int, float)) and isinstance(judge, (int, float)):
            busy = float(other) + max(0.0, float(judge) - JUDGE_RESERVED_CORES)
            return busy, f"measure_cpu other={float(other):.1f} judge={float(judge):.1f}"
    except Exception:
        pass
    try:
        import psutil
        per = psutil.cpu_percent(interval=1.0, percpu=True)
        return sum(float(x) for x in per) / 100.0, "psutil per-core (judge not separated)"
    except Exception:
        return None, "UNMEASURED"


def admission_slots() -> tuple[int, str]:
    """How many slots a pass may be admitted into right now (0: wait for CPU)."""
    cores = _logical_cores()
    busy, how = busy_cores()
    if busy is None or not cores:
        slots = min(LEGACY_SLOTS, CONCURRENT_PASSES)
        return slots, f"CPU UNMEASURED ({how}): the legacy {slots} slots stand"
    free = cores - JUDGE_RESERVED_CORES - busy
    why = (f"{cores} cores - {JUDGE_RESERVED_CORES:g} judge-reserved - {busy:.1f} busy "
           f"= {free:.1f} free ({how})")
    if free < MIN_FREE_CORES_TO_ADMIT:
        # ANTI-STARVATION FLOOR: one pass is always admitted, so a judge-saturated box can slow
        # departments to one at a time but never hold all of them. The judge keeps its 8.
        return 1, f"{why} < {MIN_FREE_CORES_TO_ADMIT:g}: floor of 1 slot only"
    return CONCURRENT_PASSES, why


def _last_leg(beat: Path) -> str:
    """The last leg the child announced at a boundary; '' when none or unreadable."""
    try:
        doc = json.loads(beat.read_text(encoding="utf-8"))
    except Exception:
        return ""
    return str(doc.get("leg") or "") if isinstance(doc, dict) else ""


def reclaim_path(dept: str) -> Path:
    return LOCKS / f"dept_reclaim_{dept}.json"


def note_reclaim(dept: str, leg: str, *, now: float | None = None) -> dict:
    """Count consecutive reclaims of the same leg; a REPEAT (>= RECLAIM_REPEAT_N) goes RED in
    DEPT_QUEUE.json, because a leg killed at the same point every pass never completes."""
    t = now if now is not None else time.time()
    path = reclaim_path(dept)
    try:
        prev = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        prev = {}
    same = isinstance(prev, dict) and prev.get("leg") == leg
    count = int(prev.get("count", 0)) + 1 if same else 1
    doc = {"dept": dept, "leg": leg, "count": count, "at": t,
           "repeat": count >= RECLAIM_REPEAT_N}
    with contextlib.suppress(OSError):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(doc), encoding="utf-8")
        os.replace(tmp, path)
    return doc


def clear_reclaim(dept: str) -> None:
    with contextlib.suppress(OSError):
        reclaim_path(dept).unlink(missing_ok=True)


def pass_heartbeat_path(dept: str) -> Path:
    return LOCKS / f"dept_pass_{dept}.heartbeat"


def touch_pass_heartbeat(path: Path, **info) -> None:
    with contextlib.suppress(OSError):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                                    "resident_pid": os.getpid(), **info}), encoding="utf-8")


def _heartbeat_age_s(path: Path, now: float | None = None) -> float | None:
    try:
        return max(0.0, (now if now is not None else time.time()) - path.stat().st_mtime)
    except OSError:
        return None


def queue_report(contenders: list[dict], set_aside: list[str], *,
                 now: float | None = None) -> dict:
    """The queue as process_health reads it: RED when any ticket has waited over STARVATION_S."""
    t = now if now is not None else time.time()
    tickets = [{"dept": c["dept"], "pid": c["pid"], "ticket": c["name"],
                "waited_s": round(max(0.0, t - c["entered"] / 1e9), 1)} for c in contenders]
    starved = [x for x in tickets if x["waited_s"] > STARVATION_S]
    passes = []
    with contextlib.suppress(OSError):
        for hb in sorted(LOCKS.glob("dept_pass_*.heartbeat")):
            age = _heartbeat_age_s(hb, t)
            passes.append({"dept": hb.stem[len("dept_pass_"):],
                           "heartbeat_age_s": None if age is None else round(age, 1),
                           "stale": age is not None and age > HEARTBEAT_STALL_S})
    repeats = []
    with contextlib.suppress(OSError):
        for rp in sorted(LOCKS.glob("dept_reclaim_*.json")):
            try:
                d = json.loads(rp.read_text(encoding="utf-8"))
            except Exception:
                continue
            if (isinstance(d, dict) and d.get("repeat")
                    and t - float(d.get("at") or 0) <= RECLAIM_REPEAT_FRESH_S):
                repeats.append({"dept": d.get("dept"), "leg": d.get("leg"),
                                "count": d.get("count")})
    verdict = "RED" if (starved or repeats) else "GREEN"
    parts = []
    if starved:
        parts.append(f"{len(starved)} ticket(s) waited over {STARVATION_S}s: "
                     + ", ".join(f"{x['dept']} {x['waited_s'] / 3600:.1f}h" for x in starved))
    if repeats:
        parts.append("RECLAIMED_REPEAT: " + ", ".join(
            f"{x['dept']}:{x['leg'] or '?'} x{x['count']}" for x in repeats))
    why = "; ".join(parts) if parts else f"{len(tickets)} waiting, none over {STARVATION_S}s"
    return {"at": datetime.fromtimestamp(t, tz=UTC).isoformat(timespec="seconds"),
            "verdict": verdict, "why": why, "starvation_s": STARVATION_S,
            "concurrent_passes": CONCURRENT_PASSES, "waiting": tickets, "starved": starved,
            "set_aside": set_aside, "passes": passes, "reclaim_repeats": repeats,
            "writer_pid": os.getpid()}


def write_queue_report(contenders: list[dict], set_aside: list[str], *,
                       force: bool = False) -> dict | None:
    """Write reports/DEPT_QUEUE.json, at most every REPORT_EVERY_S unless forced."""
    out = REPORTS / "DEPT_QUEUE.json"
    age = _heartbeat_age_s(out)
    if not force and age is not None and age < REPORT_EVERY_S:
        return None
    doc = queue_report(contenders, set_aside)
    with contextlib.suppress(OSError):
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_name(f"{out.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        os.replace(tmp, out)
    return doc


def wait_for_capacity(dept: str, *, slots: int = CONCURRENT_PASSES,
                      poll_s: int = PAUSE_S, admit=None):
    """Wait FIFO for bounded capacity; reacquiring departments rejoin at the tail.

    Strictly by ticket time: only the head may claim, the head is the same ticket in every
    resident's view, and the head is admitted only while the CPU rule leaves room.
    """
    admit = admit or admission_slots
    announced = False
    starved_logged = False
    cpu_logged = ""
    ticket = _wait_ticket(dept)
    try:
        while True:
            contenders, set_aside = _queue()
            doc = write_queue_report(contenders, set_aside)
            if doc and doc["verdict"] == "RED" and not starved_logged:
                log(dept, f"RED: queue starvation -- {doc['why']}")
                starved_logged = True
            if contenders and contenders[0]["name"] == ticket.name:
                allowed, why = admit()
                handle = claim_capacity_slot(min(int(slots), allowed)) if allowed > 0 else None
                if handle is not None:
                    log(dept, f"admitted to {Path(handle.name).stem} of {slots}: {why}")
                    return handle
                if allowed <= 0 and why != cpu_logged:
                    log(dept, f"head of queue, waiting for CPU: {why}")
                    cpu_logged = why
            if not announced:
                log(dept, "waiting: bounded department slots or older pass(es) ahead")
                announced = True
            time.sleep(max(1, int(poll_s)))
    finally:
        ticket.unlink(missing_ok=True)


def _kill_own_tree(proc: subprocess.Popen) -> dict:
    """Kill THIS resident's own child and its descendants -- never any other process. The Popen
    handle is still unreaped, so its pid cannot have been reused by a stranger."""
    out: dict = {"pid": proc.pid}
    try:
        root = str(DESK.parents[1])
        if root not in sys.path:
            sys.path.insert(0, root)
        from libs.ops import proctree
        out.update(proctree.kill_tree(proc.pid))
    except Exception as exc:
        out["proctree"] = type(exc).__name__
        with contextlib.suppress(OSError):
            proc.kill()
    with contextlib.suppress(Exception):
        proc.wait(timeout=10)
    return out


def _spawn(args: list[str], **kwargs) -> subprocess.Popen:
    return subprocess.Popen(args, **kwargs)


def _io_bytes(pr) -> int | None:
    try:
        io = pr.io_counters()
    except Exception:
        return None
    return int(getattr(io, "read_bytes", 0) or 0) + int(getattr(io, "write_bytes", 0) or 0) \
        + int(getattr(io, "other_bytes", 0) or 0)


def _tree_cpu_progress(pid: int, seen: dict) -> bool | None:
    """Did the child's tree burn CPU_PROGRESS_S, or move IO_PROGRESS_BYTES of I/O, since the last
    poll? None when unmeasurable. `seen` maps pid -> (cpu_s, io_bytes or None)."""
    try:
        import psutil
        root = psutil.Process(pid)
        procs = [root, *root.children(recursive=True)]
    except Exception:
        return None
    delta, io_delta, fresh = 0.0, 0, False
    now_seen: dict = {}
    for pr in procs:
        try:
            ct = pr.cpu_times()
            used = float(ct.user) + float(ct.system)
        except Exception:
            continue
        io = _io_bytes(pr)
        now_seen[pr.pid] = (used, io)
        if pr.pid in seen:
            prev_cpu, prev_io = seen[pr.pid]
            delta += max(0.0, used - prev_cpu)
            if io is not None and prev_io is not None:
                io_delta += max(0, io - prev_io)
        else:
            fresh = fresh or bool(seen)   # a new descendant after the first poll is progress
    first = not seen
    seen.clear()
    seen.update(now_seen)
    if not now_seen:
        return None
    return (not first) and (fresh or delta >= CPU_PROGRESS_S or io_delta >= IO_PROGRESS_BYTES)


def run_pass(dept: str, timeout_s: int = PASS_TIMEOUT_S, *, slot: str = "",
             stall_s: int = HEARTBEAT_STALL_S, poll_s: float = HEARTBEAT_POLL_S) -> dict:
    """One department pass as a child under HOURLY_PLAN=dept:<name>, BELOW_NORMAL priority,
    supervised by the pass heartbeat: a child with no leg boundary and no CPU for `stall_s` is
    hung, and this resident kills its own child tree and reports `stalled`."""
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
    beat = pass_heartbeat_path(dept)
    env["DEPT_PASS_HEARTBEAT"] = str(beat)
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = BELOW_NORMAL_PRIORITY_CLASS
    t0 = time.monotonic()
    touch_pass_heartbeat(beat, dept=dept, slot=slot, source="admitted")
    try:
        proc = _spawn([sys.executable, "-W", "ignore", str(CYCLE)], cwd=str(DESK),
                      env=env, **kwargs)
    except OSError as exc:
        with contextlib.suppress(OSError):
            beat.unlink(missing_ok=True)
        return {"rc": None, "seconds": round(time.monotonic() - t0, 1),
                "status": f"failed_to_start: {type(exc).__name__}"}
    seen: dict[int, float] = {}
    try:
        while True:
            left = timeout_s - (time.monotonic() - t0)
            try:
                rc = proc.wait(timeout=max(0.05, min(float(poll_s), left)))
                return {"rc": rc, "seconds": round(time.monotonic() - t0, 1),
                        "status": "ok" if rc == 0 else "exit"}
            except subprocess.TimeoutExpired:
                pass
            if time.monotonic() - t0 >= timeout_s:
                killed = _kill_own_tree(proc)
                return {"rc": None, "seconds": round(time.monotonic() - t0, 1),
                        "status": "timeout", "killed": killed}
            progressed = _tree_cpu_progress(proc.pid, seen)
            if progressed:
                touch_pass_heartbeat(beat, dept=dept, slot=slot, source="cpu",
                                     child_pid=proc.pid)
            age = _heartbeat_age_s(beat)
            # UNMEASURED NEVER KILLS: without a readable tree, only the hard timeout stands.
            if progressed is not None and age is not None and age > stall_s:
                leg = _last_leg(beat)
                killed = _kill_own_tree(proc)
                return {"rc": None, "seconds": round(time.monotonic() - t0, 1),
                        "status": "stalled", "killed": killed, "leg": leg,
                        "why": f"no heartbeat (leg boundary or child CPU) for {age:.0f}s "
                               f"> {stall_s}s"}
    finally:
        with contextlib.suppress(OSError):
            beat.unlink(missing_ok=True)


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
                slot = Path(getattr(capacity, "name", "")).stem
                res = run_pass(dept, slot=slot)
            finally:
                with contextlib.suppress(OSError):
                    capacity.close()
            log(dept, f"pass {passes}: {res['status']} rc={res['rc']} in {res['seconds']}s")
            if res["status"] == "stalled":
                # Reclaimed: the child tree is dead, the slot is released (closed above), and
                # the department rejoins the queue now. A hung pass is not completed work.
                log(dept, f"RECLAIMED {slot}: {res.get('why')}; killed own child tree "
                          f"{res.get('killed')}; requeued")
                rec = note_reclaim(dept, str(res.get("leg") or ""))
                if rec["repeat"]:
                    log(dept, f"RECLAIMED_REPEAT RED: leg {rec['leg'] or '?'} reclaimed "
                              f"{rec['count']} passes in a row; it never completes")
                heartbeat(dept, passes, status="stalled")
                if a.once:
                    return 1
                if passes >= RECYCLE_PASSES:
                    return 0
                time.sleep(PAUSE_S)
                continue
            clear_reclaim(dept)
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
