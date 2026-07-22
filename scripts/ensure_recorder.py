"""Recorder keeper -- respawn the data-moat recorder if its heartbeat is stale (daily cycle).

No sudo/systemd available to the quant user, so liveness is enforced two ways: this daily
respawner + a 10-minute staleness page via run_alerts. Detached via setsid so it survives
the cycle process.

    python scripts/ensure_recorder.py
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

_HB = Path("data/recorder_heartbeat")
_PAT = r"python.*run_recorder\.py"


def _running() -> bool:
    """Heartbeat AGE is not liveness. A freshly-killed process leaves a fresh heartbeat
    behind, so an age-only check reports "alive" while nothing is running -- observed
    directly 2026-07-22 (printed "recorder: alive" with zero processes), giving a 10-minute
    blind window after every crash and masking a crash-loop indefinitely. Check the PROCESS,
    and keep the heartbeat check too (a hung-but-alive process is also a failure).
    """
    try:
        r = subprocess.run(["pgrep", "-f", _PAT], capture_output=True, text=True,
                           check=False, timeout=10)
        return r.returncode == 0 and bool(r.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return False


def main() -> None:
    if _running() and _HB.exists() and time.time() - _HB.stat().st_mtime < 600:
        print("recorder: alive")
        return
    subprocess.Popen(["setsid", "nohup", sys.executable, "scripts/run_recorder.py"],
                     stdout=open("data/recorder.log", "ab"),  # noqa: SIM115 -- handed to child
                     stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                     start_new_session=True)
    print("recorder: (re)spawned detached")


if __name__ == "__main__":
    main()
