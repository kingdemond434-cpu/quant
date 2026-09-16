"""Keep the gateway passing even when the Task Scheduler cannot start it.

WHY A RESIDENT LOOP AND NOT JUST THE TASK. `MT5-Gateway` runs as Administrator with
`LogonType=Interactive`, so it executes only while that user holds an interactive desktop
session; without one it returns `ERROR_NO_SUCH_LOGON_SESSION` (2147946720) and no pass happens.
Measured 2026-09-15: that is the task's last result, while `E8-Executor` -- which runs as
SYSTEM/ServiceAccount -- returns 0 every time.

AND THE PRINCIPAL CANNOT SIMPLY BE CHANGED TO SYSTEM. The MT5 Python API talks to a running
`terminal64` over local IPC, and the terminal lives in the interactive session. A task under
SYSTEM sits in Session 0, cannot see that terminal, and would fail to initialise -- trading a
working gateway for a silent one. Interactive is not a mistake here; it is a requirement.

So the durable answer is the pattern this box already runs successfully: a resident process
started once inside the session, exactly like `macro_intel --loop`, `meta_desk` and
`crowding_miner`, which have been up since 2026-09-08. A loop that is already running needs no
logon session to be created for it.

IT CANNOT DOUBLE-TRADE WITH THE TASK. `run_gateway_loop` holds a PID-aware lock: whichever of the
two starts a pass owns it, and the other returns immediately while the owner is alive. Running
both is belt and braces, not a race.

    pythonw -u -W ignore research/gateway_resident.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
# THE ORDER IS THE POINT, AND `if not in sys.path` BROKE IT (measured 2026-09-16). Python puts
# this script's own directory (`desks/mt5/research`) at sys.path[0] before anything runs, so the
# guard skipped it and then inserted `desks/mt5` in front of it. `import run_gateway_loop` then
# resolved to the LEGACY wrapper at the desk root -- the one that writes a pid-less "locked" lock
# and steals any lock older than five minutes -- while the per-minute task ran the modern wrapper
# with a pid lock. Two wrappers with different lock rules ran passes CONCURRENTLY whenever a pass
# took more than five minutes, and the same signal bar was sent twice, 8-18 minutes apart, by
# both. Every entry is inserted at the front in this order, so `research` is always first.
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    while _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)

#: Seconds after a minute boundary at which a pass starts, so the pass that follows a bar close
#: sees the new bar (the venue needs a tick to open it) and starts as early as it usefully can.
BOUNDARY_SLACK_S = float(os.environ.get("GATEWAY_BOUNDARY_SLACK_S", "3"))


def next_boundary_wait(now_s: float, elapsed_s: float, *, interval_s: float = 60.0,
                       slack_s: float = BOUNDARY_SLACK_S) -> float:
    """Seconds to sleep so the next pass starts `slack_s` after the next minute boundary.

    PASSES ARE ALIGNED TO THE CLOCK, NOT TO EACH OTHER. `sleep(interval - elapsed)` kept the
    passes a minute apart from wherever the first one happened to start, so the pass after a bar
    close began anywhere in the following minute. The families fill "at the open of the next
    bar"; a pass that begins three seconds after the boundary is the closest the live lane can
    get to that contract. A pass that overran the interval starts again after one second.
    """
    if elapsed_s >= interval_s:
        return 1.0
    into = now_s % interval_s
    wait = (interval_s - into) + slack_s
    if into < slack_s:
        wait = slack_s - into
    return max(1.0, float(wait))


def loop_module_path() -> str:
    """Where `import run_gateway_loop` resolves from this module's sys.path: the test pins it to
    the research wrapper so the legacy desk-root copy can never be imported again by accident."""
    import importlib.util
    spec = importlib.util.find_spec("run_gateway_loop")
    return str(spec.origin) if spec and spec.origin else ""

#: Seconds between passes. The gateway's own work is bar-driven, so this only decides how soon
#: after a bar closes the desk looks -- not how often it trades.
INTERVAL_S = 60

#: RECYCLE ABOVE THIS RESIDENT SET, in MB. A LOOP IS NOT A TASK, AND THIS IS THE DIFFERENCE.
#:
#: `MT5-Gateway` ran one pass per process, so every frame cache, every pandas block and every
#: MT5 handle the pass allocated went back to the OS when it exited. That reclamation was free
#: and invisible, and turning the pass into a resident `while True` silently removed it.
#:
#: MEASURED 2026-09-15: the resident started at 416 MB and reached 1,907 MB within the hour on a
#: box with 8 GB total, while `external_gauntlet` needs ~1,200 MB to start and stands down
#: without it. A background job was killed by the OS for memory in the same window. The gateway
#: was not leaking because of a bug in a pass; it was leaking because nothing ever ended.
#:
#: So the loop ends itself and lets the keep-alive trigger start a clean one. `MT5-GatewayResident`
#: fires every 10 minutes and the named-mutex singleton means the restart is a no-op while a
#: healthy loop holds the slot -- so exiting here is the ONLY thing needed, and the gap is at
#: most one trigger. A pass is idempotent and the PID-aware lock is released on exit, so nothing
#: is half-done across the boundary.
def _total_phys_mb() -> float | None:
    """Physical memory of THIS machine in MB, or None when it cannot be read."""
    try:
        import ctypes
        from ctypes import wintypes

        class _MS(ctypes.Structure):
            _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        m = _MS()
        m.dwLength = ctypes.sizeof(_MS)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
            return None
        return float(m.ullTotalPhys) / (1024.0 * 1024.0)
    except Exception:
        return None


def default_recycle_mb(total_phys_mb: float | None) -> float:
    """The recycle ceiling for a box with `total_phys_mb` of memory: a tenth of it, never below
    the 900 MB the 8 GB box was tuned to.

    MEASURED ON THE MACHINE, NEVER A CONSTANT FROM ANOTHER (CLAUDE.md's floor rule). At a flat
    900 MB the resident on the 98 GB box recycled after every 2-4 passes ("1737MB resident
    (limit 900MB)" 2026-09-16 06:14, again at 06:26 and 06:38), so every third pass paid a cold
    start -- module imports, bars, primitives -- and the passes stretched to 7-10 minutes apart.
    That gap is the entry drift `decision_core.family_bracket` documents: the engine fills at the
    bar's open, the gateway got there up to 14 minutes later. An unreadable counter keeps the
    old 900, which is the floor doing its job rather than a guess.
    """
    if total_phys_mb is None or not total_phys_mb > 0:
        return 900.0
    return float(max(900.0, round(0.10 * total_phys_mb)))


RECYCLE_RSS_MB = float(os.environ.get("GATEWAY_RECYCLE_RSS_MB", "")
                       or default_recycle_mb(_total_phys_mb()))

#: A ceiling on passes even if the RSS reading is unavailable. At 60s a pass this is ~2 hours.
RECYCLE_AFTER_PASSES = int(os.environ.get("GATEWAY_RECYCLE_PASSES", "120"))


def _rss_mb() -> float | None:
    """This process's resident set in MB, or None when it cannot be read.

    None is a real answer: an unreadable counter must not be treated as 0 (which would never
    recycle) nor as huge (which would recycle every pass). The pass ceiling covers that case.
    """
    try:
        import ctypes
        from ctypes import wintypes

        class _PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD),
                        ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]

        # THE SIGNATURES ARE DECLARED, AND WITHOUT THEM THIS SILENTLY RETURNS NOTHING. ctypes
        # defaults an undeclared return to C int, so `GetCurrentProcess`'s 64-bit pseudo-handle
        # is TRUNCATED before it is passed on -- the call then fails with ok=0 and sets no error
        # code, which reads exactly like "this box cannot report RSS". Measured here: undeclared
        # returned ok=0 from both psapi and kernel32; declared returns ok=1 and a real figure.
        # A recycle guard that always measures None is a recycle guard that never fires.
        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = wintypes.HANDLE
        fn = k.K32GetProcessMemoryInfo          # kernel32 forwarder: no psapi.dll dependency
        fn.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PMC), wintypes.DWORD]
        fn.restype = wintypes.BOOL

        c = _PMC()
        c.cb = ctypes.sizeof(_PMC)
        if not fn(k.GetCurrentProcess(), ctypes.byref(c), c.cb):
            return None
        return float(c.WorkingSetSize) / (1024.0 * 1024.0)
    except Exception:
        return None

#: The singleton's name. Held for the life of the process, so a second copy started by the
#: keep-alive task exits instead of stacking.
_SINGLETON = "Local\\MT5-GatewayResident"


def _claim_singleton() -> object | None:
    """Own the resident slot, or return None because another copy already does.

    WHY THIS EXISTS. `AtLogOn` NEVER FIRES ON A HEADLESS SERVER. The task was registered to start
    this loop at logon, and nobody logs on to a box that is reached by RDP only occasionally --
    measured 2026-09-15, `MT5-GatewayResident` had result 267011 ("has not yet run") while
    `MT5-Gateway`, an Interactive task, returned 2147946720 (ERROR_NO_SUCH_LOGON_SESSION) on
    every trigger. Between them the gateway had executed ZERO scheduled passes: no forex sleeve
    could trade because nothing was walking them, and the release fence being open changed
    nothing while no process was there to pass through it.

    The fix is a keep-alive trigger on an ordinary clock rather than a logon, and a trigger that
    fires every few minutes needs this guard or it stacks a new loop each time. A named mutex is
    the right shape: the OS releases it when the process dies, however it dies, so a crashed
    resident is replaced by the next tick with no stale lock file to reap.
    """
    try:
        import ctypes
        h = ctypes.windll.kernel32.CreateMutexW(None, True, _SINGLETON)
        if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            ctypes.windll.kernel32.CloseHandle(h)
            return None
        return h
    except Exception:
        # No mutex means no guard, not no gateway: run anyway. `run_gateway_loop` holds its own
        # PID-aware lock, so the worst case is a second process that does nothing each pass.
        return True


def _release_singleton(handle: object) -> None:
    """Hand the slot back BEFORE the successor is started, so it can claim it at once."""
    try:
        import ctypes
        if isinstance(handle, int):
            ctypes.windll.kernel32.ReleaseMutex(handle)
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        pass


def _spawn_successor() -> bool:
    """Start a fresh resident, detached, so a recycle costs seconds rather than the up-to-ten
    minutes until the keep-alive trigger. Measured 2026-09-16: every recycle left the desk with
    no pass until that trigger, and the families' bar-close entries slipped by that much."""
    import subprocess
    exe = sys.executable
    args = [exe, "-u", "-W", "ignore", str(Path(__file__).resolve())]
    base = (getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    breakaway = 0x01000000                                  # CREATE_BREAKAWAY_FROM_JOB
    for flags in (base | breakaway, base):
        try:
            subprocess.Popen(args, cwd=str(DESK), creationflags=flags, close_fds=True,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            return True
        except Exception:
            continue
    return False


def main() -> int:
    handle = _claim_singleton()
    if handle is None:
        print("another resident gateway already holds the slot; exiting")
        return 0
    import run_gateway_loop
    try:
        from mt5desk import gateway as _gw
        _gw.log(f"RESIDENT: started pid {os.getpid()}; loop wrapper {loop_module_path()}; "
                f"recycle at {RECYCLE_RSS_MB:.0f}MB / {RECYCLE_AFTER_PASSES} passes; passes "
                f"aligned {BOUNDARY_SLACK_S:g}s after each minute boundary")
    except Exception:
        pass

    passes = 0
    while True:
        started = time.monotonic()
        passes += 1
        rss = _rss_mb()
        if (rss is not None and rss >= RECYCLE_RSS_MB) or passes > RECYCLE_AFTER_PASSES:
            # END CLEANLY BETWEEN PASSES, never inside one. The slot is released first and a
            # successor started at once; the keep-alive trigger remains the backstop should the
            # spawn fail, and the singleton makes that a no-op if one is already up.
            _release_singleton(handle)
            spawned = _spawn_successor()
            try:
                from mt5desk import gateway
                gateway.log(f"RESIDENT: recycling after {passes} pass(es) at "
                            f"{'unmeasured' if rss is None else f'{rss:.0f}MB'} resident "
                            f"(limit {RECYCLE_RSS_MB:.0f}MB / {RECYCLE_AFTER_PASSES} passes); "
                            f"{'successor started' if spawned else 'successor spawn FAILED'}; "
                            f"the keep-alive trigger is the backstop")
            except Exception:
                pass
            return 0
        try:
            run_gateway_loop.main()
        except Exception as exc:
            # A failed pass is one missed look, not a dead gateway. The failure is already logged
            # by the pass itself; swallowing it here is what keeps the next bar reachable.
            try:
                from mt5desk import gateway
                gateway.log(f"RESIDENT: pass raised {type(exc).__name__}: {exc}")
            except Exception:
                pass
        time.sleep(next_boundary_wait(time.time(), time.monotonic() - started,
                                      interval_s=float(INTERVAL_S)))


if __name__ == "__main__":
    raise SystemExit(main())
