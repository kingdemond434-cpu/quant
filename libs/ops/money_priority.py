"""MONEY RUNS ABOVE RESEARCH: put a money-lane process (and every process it starts) in a Windows
job object whose priority class is ABOVE_NORMAL, so the box's research, mining and judging can
use every free core and still never starve a money runner of CPU.

WHY (Hourly pass idea 582, 2026-11-11). E8-Gold was killed by its 4-minute time limit at 00:56Z
and again at 01:11Z, in the Asia window, while research filled all 18 cores at the same NORMAL
priority. Raising only the runner's own priority is not enough. On Windows a process started by an
ABOVE_NORMAL parent starts at NORMAL again (only IDLE and BELOW_NORMAL are inherited), so a
runner's workers and helpers would drop back level with research. A job object's priority-class
limit applies to every process in the job, and children join their parent's job, so the whole
money tree stays above research.

WHAT IT NEVER DOES. It lowers nothing and caps nothing. Research keeps every cycle the money
runners leave idle (never-throttle-mining). It is not HIGH or REALTIME, so the OS, the
MT5 terminal's own I/O and the box's control tasks are never starved either. It never raises
and never blocks: priority is an optimisation, so any failure leaves the runner exactly as it
was and returns why.

    from libs.ops.money_priority import enter
    enter()        # first thing in a money runner's __main__ block

Every python runner on a lane="money" or lane="prop" row of desks/mt5/ops/box_tasks.manifest
calls it (tests/ops/test_money_priority.py enforces that), except the two canon watchers that
must stay byte-identical to the box originals (CANON_EXEMPT) and the deadman rails, which are
never modified autonomously (RAIL_EXEMPT). Wrap those, or any other command, with the CLI:

    python -m libs.ops.money_priority -- <command> [args...]
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Any

#: Windows priority classes (winbase.h).
ABOVE_NORMAL_PRIORITY_CLASS = 0x00008000
#: JOBOBJECT_BASIC_LIMIT_INFORMATION.LimitFlags: enforce PriorityClass on every process in the job.
JOB_OBJECT_LIMIT_PRIORITY_CLASS = 0x00000020
#: ...and let a child that asks to leave the job (CREATE_BREAKAWAY_FROM_JOB, e.g. terminal64.exe
#: started by mt5.initialize) do so instead of failing with access denied.
JOB_OBJECT_LIMIT_BREAKAWAY_OK = 0x00000800
#: The ONLY limits this module ever sets (tests pin it: no cap can be added here).
LIMIT_FLAGS = JOB_OBJECT_LIMIT_PRIORITY_CLASS | JOB_OBJECT_LIMIT_BREAKAWAY_OK
#: JOBOBJECTINFOCLASS: JobObjectExtendedLimitInformation.
_EXTENDED_LIMIT_INFORMATION = 9

#: Manifest runners that are byte-identical canon copies of box originals: never edited, so the
#: priority comes from the CLI wrapper when their task is next registered.
CANON_EXEMPT = (
    "desks/mt5/scripts/watchers/ftmo_follow.py",
    "desks/mt5/scripts/watchers/e8_window_guard.py",
)
#: The deadman / ruin rails, which are never modified autonomously (docs/LAWS.md): same, the CLI
#: wrapper at task registration instead.
RAIL_EXEMPT = (
    "scripts/run_deadman_switch.py",
    "desks/mt5/proposals/fusion_deadman.py",
)
EXEMPT = CANON_EXEMPT + RAIL_EXEMPT

_STATE: dict[str, str] = {}


def _job_limits() -> tuple[Any, Any]:
    import ctypes

    class _Basic(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", ctypes.c_uint32),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", ctypes.c_uint32),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", ctypes.c_uint32),
            ("SchedulingClass", ctypes.c_uint32),
        ]

    class _Io(ctypes.Structure):
        _fields_ = [(n, ctypes.c_uint64) for n in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]  # fmt: skip

    class _Extended(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _Basic),
            ("IoInfo", _Io),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    return _Extended, ctypes


def limits() -> Any:
    """The extended-limit structure this module sets: only the priority-class limit."""
    ext_t, _ = _job_limits()
    info = ext_t()
    info.BasicLimitInformation.LimitFlags = LIMIT_FLAGS
    info.BasicLimitInformation.PriorityClass = ABOVE_NORMAL_PRIORITY_CLASS
    return info


def enter() -> str:
    """Put THIS process (and so every process it starts from now on) in an ABOVE_NORMAL job.
    Idempotent; never raises. Returns what happened, one line."""
    if "status" in _STATE:
        return _STATE["status"]
    _STATE["status"] = status = _enter()
    return status


def _windows() -> bool:
    return os.name == "nt"


def _enter() -> str:
    if not _windows():
        return "not Windows: nothing changed"
    try:
        import ctypes
        from ctypes import wintypes

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateJobObjectW.restype = wintypes.HANDLE
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                                wintypes.DWORD]  # fmt: skip
        k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        k32.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        me = k32.GetCurrentProcess()
        # the runner itself, whatever happens with the job
        own = bool(k32.SetPriorityClass(me, ABOVE_NORMAL_PRIORITY_CLASS))
        job = k32.CreateJobObjectW(None, None)
        if not job:
            return f"no job object (error {ctypes.get_last_error()}); runner above normal: {own}"
        info = limits()
        if not k32.SetInformationJobObject(job, _EXTENDED_LIMIT_INFORMATION, ctypes.byref(info),
                                           ctypes.sizeof(info)):  # fmt: skip
            err = ctypes.get_last_error()
            return f"job limit refused (error {err}); runner above normal: {own}"
        if not k32.AssignProcessToJobObject(job, me):
            # e.g. an old Windows without nested jobs: the runner alone stays above normal
            return f"not joined (error {ctypes.get_last_error()}); runner above normal: {own}"
        # the job handle is deliberately kept open for the life of the process
        _STATE["job"] = str(job)
        return "money job: this process and its children run ABOVE_NORMAL"
    except Exception as exc:  # priority must never break a money runner
        return f"unchanged ({type(exc).__name__}: {str(exc)[:120]})"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["--"]:
        args = args[1:]
    if not args:
        print("usage: python -m libs.ops.money_priority -- <command> [args...]", file=sys.stderr)
        return 2
    print(f"money_priority: {enter()}", file=sys.stderr, flush=True)
    return subprocess.call(args)  # the child joins this process's job, so it runs above normal


if __name__ == "__main__":
    raise SystemExit(main())
