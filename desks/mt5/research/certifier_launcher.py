"""Acquire the certifier's lease before importing numerical libraries.

The QQuant battery imports NumPy, pandas and SciPy at module import time.  Taking
the lease inside that module is therefore too late: two scheduled certifiers can
exhaust Windows commit/pagefile while merely importing.  This lightweight
launcher owns the lease first, constrains native BLAS fan-out, and only then
starts the battery in a child process.

ITS OWN LANE, ADMITTED ON MEMORY (2026-11-11). Until today this launcher shared
`certification_lane` with the judge's sweep. Since the sweep runs back to back so the
judge never idles, it held that lane almost every minute of the day. Every launch
(about every 27 min) therefore printed DEFERRED and exited 0, and QQUANT_GATES.json
(the ONLY input the promoter accepts for live promotion) sat at 341 min against its
180 min contract with no failure anywhere. The shared lane only existed to keep two heavy
certifiers from exhausting commit together. `exclusive_job`'s memory admission says that
directly: median-of-three free memory, a wait for room, and the measured p75 peak as
the need. So the launcher now takes its own single-instance lock and is admitted on
memory, never by queueing behind the judge. Neither certifier gives up any work.

NEVER SILENT. Every launch writes reports/QQUANT_CERTIFY_LAUNCH.json with its outcome:
RAN with the child's rc, or STOOD_DOWN with the reason (DUPLICATE: a live holder, with its
pid and heartbeat; NO_ROOM: need and free MB). A stand-down while QQUANT_GATES.json is
already past its contract exits STANDDOWN_BREACH_EXIT, so the task's last result reads as a
failure instead of rc 0.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

#: A launcher owns no artifact of its own: its proof of running is the battery it launches, which
#: writes reports/QQUANT_GATES.json. Declared so the component registry and the runtime
#: attestation can hold this organ's row against the file that actually moves when it runs.
ARTIFACT = BASE / "reports" / "QQUANT_GATES.json"
#: Every launch's outcome, so a stand-down is a reading and not an absence.
LAUNCH_REPORT = BASE / "reports" / "QQUANT_CERTIFY_LAUNCH.json"
#: The certifier's own single-instance lock: two QQuant batteries never run at once.
LANE = "qquant_certification"
#: Declared memory floor for the battery and its workers (BLAS pinned to one thread each).
#: `job_lock.measured_need_mb` raises it to the measured p75 peak once runs are recorded.
NEED_MB = 3000
#: QQUANT_GATES.json's freshness contract (minutes); a stand-down past it is a failure.
CONTRACT_MIN = 180.0
STANDDOWN_BREACH_EXIT = 75
BELOW_NORMAL_PRIORITY_CLASS = 0x00004000

from research.job_lock import LAST_REFUSAL, exclusive_job  # noqa: E402


def _age_min(path: Path) -> float | None:
    """The report's age by its OWN stamp (`swept_at`), never mtime unless it has none."""
    return _age(path)[0]


def _age(path: Path) -> tuple[float | None, str]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        doc = None
    if isinstance(doc, dict):
        for key in ("swept_at", "generated_at", "at"):
            raw = doc.get(key)
            if not raw:
                continue
            try:
                at = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except ValueError:
                continue
            if at.tzinfo is None:
                at = at.replace(tzinfo=UTC)
            return round((datetime.now(UTC) - at).total_seconds() / 60.0, 1), key
    try:
        return round((time.time() - path.stat().st_mtime) / 60.0, 1), "mtime"
    except OSError:
        return None, "absent"


def _record(doc: dict[str, Any], path: Path | None = None) -> None:
    target = path or LAUNCH_REPORT
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
        os.replace(tmp, target)
    except OSError as exc:
        print(f"qquant_gates: launch record NOT written ({type(exc).__name__}: {exc})",
              flush=True)


def stand_down(refusal: dict[str, Any] | None, *, artifact: Path | None = None,
               report: Path | None = None) -> int:
    """Record why this launch did not run, and the exit code the task should show."""
    why = dict(refusal or {})
    reason = "NO_ROOM" if why.get("reason") == "NO_ROOM" else "DUPLICATE"
    age, basis = _age(artifact or ARTIFACT)
    breach = age is None or age > CONTRACT_MIN
    doc = {"at": datetime.now(UTC).isoformat(timespec="seconds"), "verdict": "STOOD_DOWN",
           "reason": reason, "detail": why, "lane": LANE,
           "artifact_age_min": age, "artifact_age_basis": basis,
           "contract_min": CONTRACT_MIN, "contract_breached": breach}
    _record(doc, report)
    print(f"qquant_gates: STOOD DOWN ({reason}) {json.dumps(why, default=str)}; "
          f"QQUANT_GATES.json age={age}min contract={CONTRACT_MIN:.0f}min", flush=True)
    return STANDDOWN_BREACH_EXIT if breach else 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    env = os.environ.copy()
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
                 "NUMEXPR_NUM_THREADS"):
        env[name] = "1"

    with exclusive_job(LANE, need_mb=NEED_MB) as acquired:
        if not acquired:
            return stand_down(LAST_REFUSAL.get(LANE))
        started = datetime.now(UTC).isoformat(timespec="seconds")
        command = [sys.executable, "-u", "-W", "ignore",
                   str(BASE / "research" / "qquant_gates.py"), *args]
        flags = BELOW_NORMAL_PRIORITY_CLASS if os.name == "nt" else 0
        rc = subprocess.run(command, cwd=BASE, env=env, check=False,
                            creationflags=flags).returncode
        _record({"at": datetime.now(UTC).isoformat(timespec="seconds"), "verdict": "RAN",
                 "started_at": started, "rc": rc, "lane": LANE,
                 "artifact_age_min": _age_min(ARTIFACT), "contract_min": CONTRACT_MIN})
        return rc


if __name__ == "__main__":
    raise SystemExit(main())
