"""ONE rate-limited door to the repair organ, shared by every fence that can call it.

WHY THIS EXISTS (measured 2026-08-26). Five fences invoke `quant-gap-wirer.service` --
check_p0_liveness, check_authority_ratchet, check_job_manifest, check_sameday_pipeline and
check_miner_conversion -- and exactly ONE of them had a cooldown. The other four fired on every
run that found a breach, and their timers are every 10 minutes (authority-ratchet), every 30
(job-manifest) and hourly (sameday). A breach that persists -- which is the normal state of a
breach, since the repair takes hours -- therefore re-fired the repair organ continuously.

WHAT THAT COST, from the journal rather than from theory. On the night of 2026-08-26 the
gap-wirer started at 03:12 (OOM-killed 03:19), 03:20 (OOM-killed 03:26), 03:32 (ran 47 min,
1.6GB peak) and 04:20 -- against a timer whose schedule is WEEKLY. Each start is a headless
Claude seat on a 3814MB box with ZERO swap, and each one:

  1. takes the desk-wide brain mutex, so every miner that wakes during the run is DEFERRED --
     the discovery organs starve behind the repair organ;
  2. competes for memory with the live organs, which is how three seats and the same-day
     external pipeline were OOM-killed in 24h;
  3. spends subscription quota, feeding the `auth unavailable` deaths that made 56 of 96 seat
     launches produce nothing that week.

So the detector-to-repairer edge, built to satisfy DETECT IMPLIES REPAIR, was itself suppressing
discovery. The principle is right and the wiring was unbounded: a repair organ invoked faster
than it can repair is a denial-of-service the desk performs on itself.

THIS DOES NOT WEAKEN ANY FENCE. Every fence still detects, still writes its alarm artifact,
still returns its non-zero exit, and still escalates. What is bounded is only how often the
EXPENSIVE actuator is spawned -- and a second gap-wirer started while the first is still working
was never additional repair, it was contention. A breach that outlives the cooldown re-fires,
which is the behaviour anyone reading these fences already expects.
"""
from __future__ import annotations

import contextlib
import json
import subprocess
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent

#: Shared across every caller ON PURPOSE. A per-fence stamp would let five fences fire five
#: seats inside one cooldown window, which is the defect this module exists to end.
STAMP = _ROOT / "data" / "gap_wirer_last_fired"

#: 6h, inherited from check_p0_liveness's already-chosen value rather than invented here, so the
#: one fence that WAS rate-limited does not silently change behaviour by adopting this module.
COOLDOWN_S = 6 * 3600

_UNIT = "quant-gap-wirer.service"


def _already_running() -> bool:
    """True if a gap-wirer is active right now.

    The cooldown alone is not enough: a run that exceeds the window (the 03:32 run took 47
    minutes, and a full cycle takes hours) would otherwise be joined by a second seat, and two
    headless brains on one working tree is the exact contention the desk's brain mutex exists to
    prevent -- measured 2026-07-30, one agent committed a working tree it did not author.
    """
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        res = subprocess.run(["systemctl", "--user", "is-active", _UNIT],
                             capture_output=True, text=True, check=False, timeout=15)
        return res.stdout.strip() in {"active", "activating"}
    return False  # cannot tell -> do not block the repair path on a broken probe


def request_repair(reason: str, *, cooldown_s: float = COOLDOWN_S) -> bool:
    """Ask for a gap-wirer run. Returns True if one was actually started.

    Fails OPEN on an unreadable stamp (a missing stamp means "never fired", so the first call
    after a fresh clone repairs rather than waits) and CLOSED on an already-running unit.
    """
    now = time.time()
    last = 0.0
    with contextlib.suppress(OSError, ValueError, TypeError):
        last = float(json.loads(STAMP.read_text("utf-8")))

    if now - last < cooldown_s:
        print(f"repair-invoke: SKIPPED ({reason}) -- gap-wirer fired "
              f"{int((now - last) / 60)}min ago, cooldown {int(cooldown_s / 60)}min. The breach "
              "stands and this fence still exits non-zero; only the actuator is rate-limited.")
        return False
    if _already_running():
        print(f"repair-invoke: SKIPPED ({reason}) -- a gap-wirer is already running. A second "
              "seat is contention, not extra repair.")
        return False

    STAMP.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        STAMP.write_text(json.dumps(now), "utf-8")
    print(f"repair-invoke: STARTING gap-wirer ({reason})")
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        subprocess.Popen(["systemctl", "--user", "start", "--no-block", _UNIT])
        return True
    return False
