#!/usr/bin/env python3
"""systemd ExecCondition: is there room to start this job? Exit 0 = yes, 1 = skip cleanly.

WHY A CONDITION AND NOT A BIGGER LIMIT. Three units -- external-panel, prove-future,
unmeasurable-claims -- were failing with exit 137, SIGKILL, on a 3.8 GB box with no swap. They
spawn Claude seats and were sized at MemoryMax=800M. Raising the cap does not create memory; it
moves the kill from the cgroup to the kernel, where it can take a neighbour instead. And a unit
that is KILLED reports `failed`, which is indistinguishable on a dashboard from a unit that is
broken -- so a recurring memory shortage looked like three broken organs for as long as nobody
ran them by hand.

ExecCondition is the right instrument: a non-zero exit here SKIPS the unit cleanly, so a
starved run is a skipped run rather than a failure, and the next trigger simply tries again.
That is the same rule `brain_mem_gate` applies to the shell launchers, in the form systemd
offers for a Python one.

FAILS OPEN. If /proc/meminfo cannot be read, the job is allowed to start: this gate exists to
avoid a predictable kill, not to become a new way for work to stop.

    ExecCondition=/path/to/python scripts/have_memory.py 700
"""
from __future__ import annotations

import sys
from pathlib import Path


def available_mb() -> int | None:
    try:
        for line in Path("/proc/meminfo").read_text("utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def main() -> int:
    need = int(sys.argv[1]) if len(sys.argv) > 1 else 700
    have = available_mb()
    if have is None:
        print("have_memory: /proc/meminfo unreadable -- allowing the start (fails open)")
        return 0
    if have < need:
        # LOUD, because a silent skip is indistinguishable from a unit nobody scheduled.
        print(f"have_memory: {have}MB available < {need}MB needed -- SKIPPING this trigger "
              f"cleanly rather than being OOM-killed; the next one retries")
        return 1
    print(f"have_memory: {have}MB available >= {need}MB -- go")
    return 0


if __name__ == "__main__":
    sys.exit(main())
