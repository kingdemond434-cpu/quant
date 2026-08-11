"""Recorder keeper -- liveness AND un-hang for all three moat recorders (R0282).

Supervision was asymmetric on the crown jewel: the futures recorder had process+heartbeat
supervision here, while spot and bybit relied on cron pgrep-guards that detect a DEAD process
but not a HUNG one -- and a hung recorder holds a fresh-looking process while archiving nothing
(the heartbeat-vs-data lesson, the desk's most expensive class).

DIVISION OF LABOUR, deliberate: this script is the HANG DETECTOR AND TERMINATOR for all three
(SIGTERM first -- the recorders drain buffered rows on signal -- then SIGKILL stragglers), but
it only SPAWNS the futures recorder. Spot/bybit respawn stays with their */10 cron pgrep-guards:
two spawners for one process is a double-recorder race (both check-then-spawn on the same */10
tick), and a kill-here-respawn-there handoff adds at most one guard period to an outage that was
already total (the process was hung). This also fixes the latent futures bug where a
running-but-hung recorder got a SECOND copy spawned beside it, both writing the same archive.

No sudo/systemd available to the quant user. Detached via setsid so children survive the cycle.

    python scripts/ensure_recorder.py
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

_HB_STALE_S = 600.0

#: name -> (pgrep -f pattern, heartbeat, script path, we_spawn: False=cron-guard respawns, log)
_RECORDERS: dict[str, tuple[str, Path, str, bool, Path]] = {
    "futures": (r"python.*run_recorder\.py", Path("data/recorder_heartbeat"),
                "scripts/run_recorder.py", True, Path("data/recorder.log")),
    "spot": (r"python.*run_recorder_spot\.py", Path("data/recorder_spot_heartbeat"),
             "scripts/run_recorder_spot.py", False, Path("data/recorder_spot.log")),
    "bybit": (r"python.*run_recorder_bybit\.py", Path("data/recorder_bybit_heartbeat"),
              "scripts/run_recorder_bybit.py", False, Path("data/recorder_bybit.log")),
}


def _pids(pattern: str, script: str) -> list[int]:
    """pgrep candidates, then verify each against /proc cmdline: interpreter + the script.

    The raw -f match also catches the */10 cron guard's SHELL line (it contains both "python"
    and the script path in its respawn half) exactly when both fire on the same tick -- and
    SIGTERMing the guard between its pgrep check and its spawn silently eats a respawn. Only a
    real interpreter actually running the script is a recorder."""
    try:
        r = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True,
                           check=False, timeout=10)
        out = []
        for p in r.stdout.split():
            if not p.strip().isdigit() or int(p) == os.getpid():
                continue
            try:
                argv = Path(f"/proc/{p}/cmdline").read_bytes().split(b"\0")
            except OSError:
                continue
            args = [a.decode("utf-8", "replace") for a in argv if a]
            if any("python" in Path(a).name for a in args[:1]) and \
               any(a == script or a.endswith("/" + script) for a in args):
                out.append(int(p))
        return out
    except (OSError, subprocess.SubprocessError):
        return []


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _kill(pid: int, sig: int) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.kill(pid, sig)


def _terminate(pids: list[int], grace_s: float = 20.0) -> None:
    """SIGTERM (the recorders drain buffered rows at the top of their loop), then SIGKILL.

    A hung event loop may never reach its drain point, so the wait is bounded: better to lose
    one flush buffer than to leave a corpse holding the pgrep slot and blocking the respawn."""
    for p in pids:
        _kill(p, signal.SIGTERM)
    deadline = time.time() + grace_s
    while time.time() < deadline and any(_alive(p) for p in pids):
        time.sleep(1.0)
    for p in pids:
        if _alive(p):
            _kill(p, signal.SIGKILL)


def _hb_age(hb: Path) -> float | None:
    try:
        return time.time() - hb.stat().st_mtime
    except OSError:
        return None


def _spawn(script: str, log: Path) -> None:
    subprocess.Popen(["setsid", "nohup", sys.executable, script],
                     stdout=open(log, "ab"),  # noqa: SIM115 -- handed to child
                     stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                     start_new_session=True)


def main() -> None:
    for name, (pattern, hb, script, we_spawn, log) in _RECORDERS.items():
        pids = _pids(pattern, script)
        age = _hb_age(hb)
        stale = age is None or age > _HB_STALE_S
        if pids and not stale:
            print(f"{name}: alive (hb {age:.0f}s)")
            continue
        if pids and stale:
            # Alive process, dead heartbeat = HUNG. Kill it first: spawning beside it would
            # double-record the same archive, and for cron-guarded recorders the guard cannot
            # respawn while the corpse holds the pgrep slot.
            print(f"{name}: HUNG (process {pids}, hb "
                  f"{'absent' if age is None else f'{age:.0f}s'}) -- terminating")
            _terminate(pids)
        if we_spawn:
            _spawn(script, log)
            print(f"{name}: (re)spawned detached")
        else:
            print(f"{name}: {'terminated' if pids else 'not running'} -- "
                  "cron pgrep-guard owns the respawn (<=10min)")


if __name__ == "__main__":
    main()
