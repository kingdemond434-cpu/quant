"""Keep the gateway passing even when the Task Scheduler cannot start it.

WHY A RESIDENT LOOP AND NOT JUST THE TASK. `MT5-Gateway` runs as Administrator with
`LogonType=Interactive`, so it executes only while that user holds an interactive desktop
session; without one it returns `ERROR_NO_SUCH_LOGON_SESSION` (2147946720) and no pass happens.
Measured 2026-09-15: that is the task's last result, while `E8-Executor` -- which runs as
SYSTEM/ServiceAccount -- returns 0 every time.

AND THE PRINCIPAL CANNOT SIMPLY BE CHANGED TO SYSTEM. The MT5 Python API talks to a running
`terminal64` over local IPC, and the terminal lives in the interactive session. A task under
SYSTEM sits in Session 0, cannot see that terminal, and would fail to initialise -- trading a
working gateway for a silent one. Interactive is not a mistake here; it is a requirement.

So the durable answer is the pattern this box already runs successfully: a resident process
started once inside the session, exactly like `macro_intel --loop`, `meta_desk` and
`crowding_miner`, which have been up since 2026-09-08. A loop that is already running needs no
logon session to be created for it.

IT CANNOT DOUBLE-TRADE WITH THE TASK. `run_gateway_loop` holds a PID-aware lock: whichever of the
two starts a pass owns it, and the other returns immediately while the owner is alive. Running
both is belt and braces, not a race.

    pythonw -u -W ignore research/gateway_resident.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: Seconds between passes. The gateway's own work is bar-driven, so this only decides how soon
#: after a bar closes the desk looks -- not how often it trades.
INTERVAL_S = 60

#: The singleton's name. Held for the life of the process, so a second copy started by the
#: keep-alive task exits instead of stacking.
_SINGLETON = "Local\\MT5-GatewayResident"


def _claim_singleton() -> object | None:
    """Own the resident slot, or return None because another copy already does.

    WHY THIS EXISTS. `AtLogOn` NEVER FIRES ON A HEADLESS SERVER. The task was registered to start
    this loop at logon, and nobody logs on to a box that is reached by RDP only occasionally --
    measured 2026-09-15, `MT5-GatewayResident` had result 267011 ("has not yet run") while
    `MT5-Gateway`, an Interactive task, returned 2147946720 (ERROR_NO_SUCH_LOGON_SESSION) on
    every trigger. Between them the gateway had executed ZERO scheduled passes: no forex sleeve
    could trade because nothing was walking them, and the release fence being open changed
    nothing while no process was there to pass through it.

    The fix is a keep-alive trigger on an ordinary clock rather than a logon, and a trigger that
    fires every few minutes needs this guard or it stacks a new loop each time. A named mutex is
    the right shape: the OS releases it when the process dies, however it dies, so a crashed
    resident is replaced by the next tick with no stale lock file to reap.
    """
    try:
        import ctypes
        h = ctypes.windll.kernel32.CreateMutexW(None, True, _SINGLETON)
        if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            ctypes.windll.kernel32.CloseHandle(h)
            return None
        return h
    except Exception:
        # No mutex means no guard, not no gateway: run anyway. `run_gateway_loop` holds its own
        # PID-aware lock, so the worst case is a second process that does nothing each pass.
        return True


def main() -> int:
    if _claim_singleton() is None:
        print("another resident gateway already holds the slot; exiting")
        return 0
    import run_gateway_loop

    while True:
        started = time.monotonic()
        try:
            run_gateway_loop.main()
        except Exception as exc:
            # A failed pass is one missed look, not a dead gateway. The failure is already logged
            # by the pass itself; swallowing it here is what keeps the next bar reachable.
            try:
                from mt5desk import gateway
                gateway.log(f"RESIDENT: pass raised {type(exc).__name__}: {exc}")
            except Exception:
                pass
        time.sleep(max(1.0, INTERVAL_S - (time.monotonic() - started)))


if __name__ == "__main__":
    raise SystemExit(main())
