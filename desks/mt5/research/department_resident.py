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
            started = time.monotonic()
            heartbeat(dept, passes)
            res = run_pass(dept)
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
