"""A kill switch for the crypto recorders that does not require root.

WHY THIS EXISTS

The three crypto L2 recorders run as systemd units with `Restart=always`, and the `quant` user
that owns the repo has no sudo on the VPS. So the documented way to stop them -- `systemctl stop`
-- is unavailable to the person who needs to stop them, and killing the process is worse than
useless because systemd restarts it in ten seconds.

Meanwhile bybit alone had grown to 16GB on a 37GB disk, with the root filesystem at 87%. Deleting
the tape reclaims the space exactly once; the recorders refill it. A desk that cannot turn off its
own data collection without a sysadmin does not control its own disk.

The units already grant `ReadWritePaths=/home/quant/quant-platform/data`, so the repo's own data
directory is the one thing the recorders and the operator can both reach. A flag file there is
therefore the switch: no privileges, no restart loop to fight, and visible in `git status` rather
than buried in systemd state.

WHY IT IDLES RATHER THAN EXITS. Exiting would make systemd restart the unit immediately, log a
failure every ten seconds, and fill the journal instead of the disk. Idling holds the process
open, writing nothing, and it resumes the moment the flag is removed -- so re-enabling recording
is also a non-root operation.

    touch data/RECORDERS_OFF        # stop recording, no root needed
    rm    data/RECORDERS_OFF        # resume

THE CONSTITUTIONAL POINT. The recorder units carry a header saying that leaving them off is a
breach of P26, on the grounds that an unrecorded second is permanently unbuyable. That was true
of the crypto tape while the desk traded crypto. Irish retail rules make that leg spot-only and
the desk has moved to MT5, so the obligation TRANSFERS to mt5desk.tape rather than disappearing.
Turning these off is a deliberate decision recorded in the constitution, not a lapse.
"""

from __future__ import annotations

import time
from pathlib import Path

#: Repo data directory. The units' ReadWritePaths already covers it, which is what makes this
#: switch reachable from both sides without privileges.
_DATA = Path(__file__).resolve().parent.parent / "data"
FLAG = _DATA / "RECORDERS_OFF"

#: How often an idling recorder re-checks the flag. Long enough to cost nothing, short enough that
#: re-enabling feels immediate.
POLL_S = 30


def recorders_disabled() -> bool:
    return FLAG.exists()


def wait_while_disabled(label: str = "recorder") -> bool:
    """Block while the flag is present. Returns True if it ever waited.

    Called at the top of each recorder's loop. Deliberately does not exit the process: systemd
    restarts on exit, so exiting trades a full disk for a full journal.
    """
    if not FLAG.exists():
        return False
    print(f"{label}: data/RECORDERS_OFF present -- recording paused, not exiting "
          f"(systemd would restart an exit). Remove the file to resume.", flush=True)
    while FLAG.exists():
        time.sleep(POLL_S)
    print(f"{label}: RECORDERS_OFF cleared -- resuming", flush=True)
    return True
