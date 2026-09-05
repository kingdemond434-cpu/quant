"""Wait for memory headroom, then run. The permanent answer to OOM on a swapless 4GB box.

WHY THIS EXISTS (measured 2026-08-29)

    total 3814MB, available 937MB, SWAP: none

    memecoin-shadow python      446MB  (89% CPU)
    claude remote cli           413MB  (28h elapsed)
    claude                      340MB
    claude remote cli           303MB
    quant-platform, ALL procs   224MB

`ops/gates.sh` was killed with signal 9 mid-run. mypy over 688 source files plus a pytest
collection needs several hundred MB, and on a box with 937MB free and NO SWAP the kernel has
exactly one move: kill the largest thing. That is usually the job doing real work, not whatever
caused the pressure.

THE DIAGNOSIS THAT MATTERS, and it has been wrong here before: the quant platform is NOT the
memory hog. Its entire process tree is 224MB. Over a gigabyte sits in Claude Code sessions and
another 446MB in the memecoin shadow desk. Tuning the platform's own jobs would have shaved a few
tens of MB off the wrong process and left the box exactly as fragile.

WHAT THIS DOES, AND WHY WAITING BEATS FAILING. A job that dies on OOM has burned its whole
runtime and produced nothing; the same job started ninety seconds later usually completes. So
this blocks until there is genuine headroom rather than racing into a doomed allocation, and it
gives up loudly after a bounded wait instead of hanging forever.

WHY THE READING IS A MEDIAN. `available` on this box swings hundreds of MB within seconds as
page cache is reclaimed and Claude sessions allocate. A single sample caught at a trough stands
a job down that had plenty of room; caught at a peak it green-lights one that dies. Three reads
spaced apart, take the middle -- the same rule `research/job_lock.py` already uses for the sweep
admission door, restated here rather than imported because this must work with no repo on the
path at all.

WHAT IT DELIBERATELY DOES NOT DO. It never kills anything. The processes holding this box's
memory are the principal's own sessions and a separate live desk; a script that freed headroom by
killing whatever was largest would eventually kill the trading gateway, and "the memory guard
stopped the desk trading" is a far worse outcome than a late gate run.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

#: A heavy job (mypy over ~700 files, a pytest collection, a gauntlet sweep) needs roughly this
#: much headroom to finish without the kernel reaching for the OOM killer.
DEFAULT_NEED_MB = 700

#: Give up after this long rather than blocking a timer forever. A job that cannot start in ten
#: minutes is a box-level problem to report, not one to keep queueing behind.
DEFAULT_MAX_WAIT_S = 600

#: Between polls. Long enough that waiting is nearly free, short enough to catch a window.
_POLL_S = 20

#: Three reads, spaced -- see the module docstring on why a single sample lies in both directions.
_SAMPLES = 3
_SAMPLE_GAP_S = 3


def available_mb() -> int:
    """MemAvailable in MB, as the median of three spaced readings."""
    reads: list[int] = []
    for i in range(_SAMPLES):
        if i:
            time.sleep(_SAMPLE_GAP_S)
        try:
            with open("/proc/meminfo", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("MemAvailable:"):
                        reads.append(int(line.split()[1]) // 1024)
                        break
        except OSError:
            return 0
    return sorted(reads)[len(reads) // 2] if reads else 0


def wait_for_headroom(need_mb: int, max_wait_s: int) -> tuple[bool, str]:
    start = time.monotonic()
    first = available_mb()
    if first >= need_mb:
        return True, f"{first}MB available, need {need_mb}MB"
    while time.monotonic() - start < max_wait_s:
        time.sleep(_POLL_S)
        got = available_mb()
        if got >= need_mb:
            waited = int(time.monotonic() - start)
            return True, f"{got}MB available after waiting {waited}s (need {need_mb}MB)"
    return False, (f"only {available_mb()}MB available after {max_wait_s}s, need {need_mb}MB -- "
                   f"NOT started. This is a box-level shortage, not a job to retry: something is "
                   f"holding memory that this refuses to kill (see the module docstring).")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--need-mb", type=int, default=DEFAULT_NEED_MB)
    ap.add_argument("--max-wait-s", type=int, default=DEFAULT_MAX_WAIT_S)
    ap.add_argument("--label", default="job")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    args = ap.parse_args()
    if not args.cmd:
        print("memory_guard: no command given", file=sys.stderr)
        return 2
    cmd = args.cmd[1:] if args.cmd and args.cmd[0] == "--" else args.cmd

    ok, why = wait_for_headroom(args.need_mb, args.max_wait_s)
    print(f"memory_guard[{args.label}]: {why}", file=sys.stderr)
    if not ok:
        return 75            # EX_TEMPFAIL: a retryable shortage, not a failed job

    env = dict(os.environ)
    # glibc allocates a 64MB arena PER THREAD by default; numpy/pytest spawn enough threads that
    # the arenas alone can cost hundreds of MB of address space this workload never touches.
    # Capping arenas is the single cheapest real reduction available without root.
    env.setdefault("MALLOC_ARENA_MAX", "2")
    env.setdefault("PYTHONMALLOC", "malloc")
    return subprocess.call(cmd, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
