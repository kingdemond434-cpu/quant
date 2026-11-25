"""Acquire the shared certification lease before importing numerical libraries.

The QQuant battery imports NumPy, pandas and SciPy at module import time.  Taking
the lease inside that module is therefore too late: two scheduled certifiers can
exhaust Windows commit/pagefile while merely importing.  This lightweight
launcher owns the lease first, constrains native BLAS fan-out, and only then
starts the battery in a child process.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

#: A launcher owns no artifact of its own: its proof of running is the battery it launches, which
#: writes reports/QQUANT_GATES.json. Declared so the component registry and the runtime
#: attestation can hold this organ's row against the file that actually moves when it runs.
ARTIFACT = BASE / "reports" / "QQUANT_GATES.json"

from research.job_lock import exclusive_job  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    env = os.environ.copy()
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
                 "NUMEXPR_NUM_THREADS"):
        env[name] = "1"

    # TAKE A TURN, DON'T TRY ONCE (research/lane_turn.py, 2026-11-25). The resident judge holds
    # the lane sweep after sweep with zero cadence, so one try found it held every hour and
    # QQUANT_GATES starved. A held lane now posts a waiter record and retries; the judge yields
    # at its next sweep boundary.
    from research import lane_turn

    deadline = time.monotonic() + lane_turn.CERT_WAIT_S
    announced = False
    try:
        while True:
            with exclusive_job("certification_lane", need_mb=0) as acquired:
                if acquired:
                    if announced:
                        print("qquant_gates: took the lane after waiting for the judge's sweep "
                              "boundary", flush=True)
                    command = [sys.executable, "-u", "-W", "ignore",
                               str(BASE / "research" / "qquant_gates.py"), *args]
                    return subprocess.run(command, cwd=BASE, env=env, check=False).returncode
            if time.monotonic() >= deadline:
                print("qquant_gates: DEFERRED -- another canonical certifier owns the lane "
                      f"(waited {lane_turn.CERT_WAIT_S // 60} min for a turn)", flush=True)
                return 0
            if not announced:
                lane_turn.announce("qquant_gates")
                announced = True
            time.sleep(lane_turn.CERT_RETRY_S)
    finally:
        if announced:
            lane_turn.clear()


if __name__ == "__main__":
    raise SystemExit(main())
