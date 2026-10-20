"""Gateway watchdog unit: ONE gateway pass per invocation.

Windows Task Scheduler runs this every minute (task MT5-Gateway). A file lock
prevents overlapping passes (double-bracket race at window hours).

Never trade a weekend/holiday: gateway.main() itself idles on stale ticks.
"""

from __future__ import annotations

import contextlib
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# THE REPO ROOT, FIRST -- so `libs.*` resolves to the real package. Only the desk root was on the
# path, and `libs/` lives beside `desks/`, not inside it. MEASURED 2026-09-08 in the gateway log,
# every minute, for weeks:
#
#     sizing: proof unreadable (ModuleNotFoundError: No module named 'libs.portfolio')
#     release-refusal record failed (non-fatal) [gold_afternoon]: ... 'libs.research'
#
# Both failures are swallowed by design (a telemetry import must not break the money path), so
# the gateway kept running -- on BASE sizing, never once reading the allocator's certificate,
# with `sizing: no allocator book` as the only trace. The allocator solved a book every five
# minutes and the process that places orders could not import the module that reads it.
#
# Index 0, ahead of the desk root, deliberately: the box carries untracked copies of desk files
# beside the tracked ones, and a stale `libs/` under `desks/mt5` would otherwise win. Nothing
# under the repo root collides with a bare desk import (checked: no `config`, `data`, `scripts`,
# `tests`... imported bare anywhere in mt5desk/ or research/).
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from mt5desk import gateway

# LATENT ON THIS BRANCH, ALREADY CORRECT ON THE BOX'S -- which is the dangerous shape.
#
# The live branch fixed this to the desk root; desk-sync-clean and this branch still carried
# the retired laptop's path. Nothing breaks here because the VPS has no MT5 terminal and never
# runs this file, so the defect is invisible on the machine that holds it -- and would have
# been reinstated on the box by the first merge that resolved this file the other way.
#
# It matters because of WHERE it sits: `LOCK.write_text()` runs BEFORE `gateway.main()`, so a
# missing parent directory raises FileNotFoundError before any trading logic is reached, and
# `LOCK.exists()` being permanently False also disables the overlap guard the lock exists for.
# Same resolution as the hunt7 sweep below and as `mt5desk.config.desk_root()`.
LOCK = Path(__file__).resolve().parents[1] / "data" / "gateway.lock"
LOCK.parent.mkdir(parents=True, exist_ok=True)


#: A lock older than this whose OWNER IS GONE is stale. Only used when the pid is unreadable or
#: the platform cannot be asked -- the pid check is the real test.
LOCK_MAX_MIN = 45
#: THE OVERLONG-PASS WATCHDOG (audit r5 must-fix 5). An MT5 call that hangs (order_send included)
#: used to hold this lock, the cross-account placement lock and every rail with it for as long as
#: it hung. Past this many minutes the pass's own process ends itself (`os._exit`): the dead pid
#: frees this lock (`_holder_alive` is False) and the placement lock (`cross_account._holder_gone`),
#: and the next invocation starts clean. 30 minutes sits below the armed deadman's 45-minute STALE
#: rail, so a hang is ended by the process before the rail has to flatten for it. Normal pass
#: length is UNMEASURED here; a false kill costs one pass.
PASS_WATCHDOG_S = 30 * 60
#: What the watchdog leaves behind, so a kill is never silent.
WATCHDOG_STAMP = LOCK.parent / "GATEWAY_WATCHDOG.json"


def _watchdog_fire(started: float) -> None:
    """Called on the watchdog thread when the pass has overrun. Never returns."""
    import json
    import os
    import time
    msg = (f"WATCHDOG: gateway pass pid {os.getpid()} overran {PASS_WATCHDOG_S}s "
           f"({time.time() - started:.0f}s); the process ends itself so the locks free")
    with contextlib.suppress(Exception):
        gateway.log(msg)
    with contextlib.suppress(Exception):
        WATCHDOG_STAMP.write_text(json.dumps({"pid": os.getpid(), "at": time.time(),
                                              "overran_s": PASS_WATCHDOG_S, "why": msg}),
                                  encoding="utf-8")
    with contextlib.suppress(Exception):
        LOCK.unlink(missing_ok=True)
    # A resident loop gets a successor at once (the keep-alive trigger is the backstop).
    res = sys.modules.get("__main__")
    spawn = getattr(res, "_spawn_successor", None)
    if callable(spawn):
        with contextlib.suppress(Exception):
            spawn()
    os._exit(70)


def start_watchdog(timeout_s: float | None = None) -> threading.Timer:
    """A daemon timer that ends this process if the pass outlives `timeout_s`. Cancel it with
    `.cancel()` when the pass returns. A thread, not a subprocess: the MetaTrader5 module binds
    one terminal per process and is not safe to call from a second thread, so the watchdog never
    touches it -- it only ends the process, which Windows and POSIX both do cleanly."""
    import time
    started = time.time()
    t = threading.Timer(float(PASS_WATCHDOG_S if timeout_s is None else timeout_s),
                        _watchdog_fire, args=(started,))
    t.daemon = True
    t.start()
    return t


def _holder_alive(pid: int) -> bool:
    """Is the process that wrote the lock still running? Unknown counts as ALIVE.

    Failing towards "alive" is the safe direction: a second gateway pass placing orders beside a
    live one is worse than a pass skipped.
    """
    if pid <= 0:
        return False
    try:
        import subprocess
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                           capture_output=True, text=True, timeout=15, check=False)
        return str(pid) in (r.stdout or "")
    except Exception:
        return True


def main() -> None:
    # THE LOCK IS NOW PID-AWARE, AND THE OLD ONE WAS THE REASON THE BOX RAN OUT OF MEMORY.
    #
    # It stole any lock older than five minutes. That was fine while a pass took seconds -- most
    # sleeves refused instantly on unresolvable parameters. Once the forex sleeves actually
    # started computing signals a pass began taking MINUTES, so every five minutes a second copy
    # stole the lock and started while the first was still working, on a task that fires every
    # minute. Measured 2026-09-15: EIGHT concurrent `run_gateway_loop` processes, one of them 138
    # minutes old holding 588 MB, on a box with 1.2 GB free -- and three background jobs killed by
    # the OS for memory pressure. Fixing the strategies made the stacking worse, which is the
    # signature of a timeout standing in for a liveness check.
    #
    # Duration is not evidence of death. The owner's PID is: a lock whose writer is still running
    # is held, however long the pass takes, and one whose writer is gone is free immediately
    # rather than after an arbitrary wait.
    if LOCK.exists():
        raw = ""
        with contextlib.suppress(OSError):
            raw = LOCK.read_text(encoding="utf-8").strip()
        pid = int(raw) if raw.isdigit() else 0
        age_min = (__import__("time").time() - LOCK.stat().st_mtime) / 60
        if pid and _holder_alive(pid):
            return                                    # the owner is genuinely still working
        if not pid and age_min < LOCK_MAX_MIN:
            return                                    # legacy lock with no pid: fall back to age
        LOCK.unlink(missing_ok=True)                  # owner gone, or unreadable and ancient
    LOCK.write_text(str(__import__("os").getpid()), encoding="utf-8")
    dog = start_watchdog()
    try:
        gateway.main()
        # Research and promotion run on their own canonical hourly/daily lanes. Holding the
        # gateway lock while doing either blocks every minute-by-minute order check. In
        # particular, the former 22:00 UTC branch ran on *every* gateway pass in that hour,
        # not once per day, and could strand the resident inside shadow processing.
    except Exception as e:  # watchdog must never die
        gateway.log(f"LOOP ERROR: {e!r}")
    finally:
        dog.cancel()
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
