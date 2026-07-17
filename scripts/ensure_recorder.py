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


def main() -> None:
    if _HB.exists() and time.time() - _HB.stat().st_mtime < 600:
        print("recorder: alive")
        return
    subprocess.Popen(["setsid", "nohup", sys.executable, "scripts/run_recorder.py"],
                     stdout=open("data/recorder.log", "ab"),  # noqa: SIM115 -- handed to child
                     stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                     start_new_session=True)
    print("recorder: (re)spawned detached")


if __name__ == "__main__":
    main()
