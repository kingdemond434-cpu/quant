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

#: How long a cron-guarded recorder may stay down before this script spawns it anyway. The guard
#: runs every 10 minutes; three periods is comfortably past "the guard is slow" and squarely in
#: "the guard is not running". Below this, deferring is still correct and the race the module
#: header describes is still real.
_CRON_GRACE_S = 30 * 60

#: name -> (pgrep -f pattern, heartbeat, script path, we_spawn: False=cron-guard respawns, log,
#: archive root). THE ARCHIVE ROOT IS THE SECOND CLOCK, and it is the authoritative one. This
#: module's own header names the lesson -- "a hung recorder holds a fresh-looking process while
#: archiving nothing" -- and then supervised on the heartbeat, which is exactly the signal that
#: stays fresh in that failure. A heartbeat says the loop is turning; the newest partition says
#: rows are landing. Only the second is what the desk is paying for.
_RECORDERS: dict[str, tuple[str, Path, str, bool, Path, Path]] = {
    "futures": (r"python.*run_recorder\.py", Path("data/recorder_heartbeat"),
                "scripts/run_recorder.py", True, Path("data/recorder.log"),
                Path("data/moat/perp")),
    "spot": (r"python.*run_recorder_spot\.py", Path("data/recorder_spot_heartbeat"),
             "scripts/run_recorder_spot.py", False, Path("data/recorder_spot.log"),
             Path("data/moat/spot")),
    "bybit": (r"python.*run_recorder_bybit\.py", Path("data/recorder_bybit_heartbeat"),
              "scripts/run_recorder_bybit.py", False, Path("data/recorder_bybit.log"),
              Path("data/moat/bybit")),
}


def _data_age(root: Path) -> float | None:
    """Seconds since the newest partition under `root`, or None when the tree does not exist.

    THE MEASURE THAT CANNOT BE FAKED BY A LIVE PROCESS. A heartbeat is written by the loop; this
    is written by the DATA. When they disagree the archive is right, because the archive is the
    thing the recorder exists to produce.
    """
    if not root.is_dir():
        return None
    newest = 0.0
    for f in root.rglob("*.jsonl.gz"):
        with contextlib.suppress(OSError):
            newest = max(newest, f.stat().st_mtime)
    return None if newest <= 0 else max(0.0, time.time() - newest)


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
    for name, (pattern, hb, script, we_spawn, log, archive) in _RECORDERS.items():
        pids = _pids(pattern, script)
        age = _hb_age(hb)
        data_age = _data_age(archive)
        # STALE IF EITHER CLOCK IS STALE. A fresh heartbeat with a two-day-old archive is the
        # hang this module was written for, and supervising on the heartbeat alone would call it
        # healthy -- which is precisely what happened to the spot tape for 47.6 hours.
        stale = (age is None or age > _HB_STALE_S) or (
            data_age is not None and data_age > _HB_STALE_S)
        if pids and not stale:
            print(f"{name}: alive (hb {age:.0f}s, newest partition "
                  f"{'n/a' if data_age is None else f'{data_age / 60:.0f}min'})")
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
            continue
        # SPAWN OF LAST RESORT. Deferring to the cron guard is right ONLY while that guard is
        # firing, and nothing here ever checked whether it was. Measured 2026-08-15: the spot
        # tape was 47.6 HOURS stale -- H4 and H5, the desk's only genuinely orthogonal pair, read
        # UNMEASURED for two days while this script printed "cron pgrep-guard owns the respawn"
        # once a day and moved on. The guard is a USER-level schedule, and user timers do not fire
        # at all unless lingering is enabled for the account: the same failure mode that put the
        # money path in the root crontab.
        #
        # The double-spawn race the header warns about is real and this does not reintroduce it:
        # the guard runs every 10 minutes, so an outage OLDER than _CRON_GRACE_S is proof the
        # guard is not doing its job. Below that, defer exactly as before.
        # THE LONGER OF THE TWO OUTAGES, and an absent heartbeat no longer means "unknown" when
        # the archive can answer. Deferring forever on a missing file is the absence-as-verdict
        # defect on the one signal that decides whether data is being collected at all.
        outage = max([x for x in (age, data_age) if x is not None], default=None)
        if outage is not None and outage > _CRON_GRACE_S:
            _spawn(script, log)
            print(f"{name}: cron guard has not respawned it in {outage / 3600:.1f}h "
                  f"(> {_CRON_GRACE_S / 60:.0f}min grace) -- SPAWNED HERE as last resort. "
                  "The guard itself is the defect to fix; this stops the data loss meanwhile")
            continue
        print(f"{name}: {'terminated' if pids else 'not running'} -- "
              f"cron pgrep-guard owns the respawn (<=10min); "
              f"outage {'unknown' if outage is None else f'{outage:.0f}s'} within grace")


if __name__ == "__main__":
    main()
