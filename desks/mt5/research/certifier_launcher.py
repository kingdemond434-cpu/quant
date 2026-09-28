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
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from research.job_lock import exclusive_job  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    env = os.environ.copy()
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[name] = "1"

    with exclusive_job("certification_lane", need_mb=0) as acquired:
        if not acquired:
            print("qquant_gates: DEFERRED -- another canonical certifier owns the lane", flush=True)
            return 0
        command = [sys.executable, "-u", "-W", "ignore", str(BASE / "research" / "qquant_gates.py"), *args]
        return subprocess.run(command, cwd=BASE, env=env, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
