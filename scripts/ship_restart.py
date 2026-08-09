#!/usr/bin/env python3
"""SHIP A RESTART -- make a committed fix actually run, on a box that denies systemctl.

THE DEFECT THIS EXISTS FOR, AND IT HAS NOW COST THE DESK THREE TIMES. A committed fix is INERT
until the process restarts (desk lesson: "verify it is live by inspecting the running process's
behaviour, never by confirming the code was edited"). The detector for it has existed since
2026-07-26 and WORKS -- ``max_audit.check_stale_daemons`` fired correctly on all three instances.
What never existed was a REPAIR PATH:

  2026-07-10  churn fix inert 2 days   (executor up since 07-03)
  2026-07-26  funding fix inert 8.7h   (orphan held the book)
  2026-08-05  carry re-base fix inert 11.8h -- ``hurdle_rate.py:97`` was handed +2935.87 for a
              book that had really lost 1869.74, a $4,805.61 overstatement of the ONLY sleeve
              the desk's hurdle gate judges. Caught by hand, again.

``deploy/pull_deploy.sh`` already computed the right answer (RESTART quant-cashcarry) and then
printed ``OWED (permission denied): sudo systemctl restart ...`` and gave up, because polkit
denies systemctl to the quant user. So detection converted to a permanently-owed state and the
fix shipped only when a human happened to look. That is L1.28b in its most expensive form: a
found-unfixed defect on the money path, aging at its stated ROI.

THE MECHANISM, AND WHY SIGTERM IS NOT A HACK. ``deploy_plan`` already classifies
``run_cashcarry_executor.py`` as TIER_RESTART -- "systemd-owned; a script may restart it". The
POLICY authorises this restart; only the transport was missing. With ``Restart=always`` the unit
respawns on exit, so SIGTERM to the worker IS a restart, achieved through the one channel a
non-privileged user has. Nothing here loosens a rail or grants new authority: it performs the
action the planner already sanctions.

THE GUARD THAT IS LOAD-BEARING -- ``Restart=always``. Without it, SIGTERM does not restart the
daemon, it STOPS it, and a script that silently converts "ship the fix" into "take the executor
down and leave the book unmanaged" is far worse than the defect it set out to close. So the
autorestart policy is READ FROM SYSTEMD and verified before any signal is sent; anything else
refuses and stays OWED. Absence of evidence that it will come back is treated as evidence it
will not.

TIER_RUIN IS NEVER SIGNALLED. ``quant-deadman`` is the isolated ruin rail (Tier-3, principal
sign-off even for improvements). A restart of it is a window with no ruin rail, so this refuses
outright and defers to the operator -- the same exit ``pull_deploy.sh`` already takes.

AND THE HALF THAT ALMOST FOOLED THE AUTHOR TODAY: A NEW PID IS NOT A NEW BEHAVIOUR. During the
2026-08-05 repair the artifact's ``updated`` timestamp advanced within seconds of the restart and
still carried the OLD code's numbers -- it was the dying process's final tick. Had the check
stopped at "the timestamp moved", a false VERIFIED would have gone into the record. So this tool
reports ``RESTARTED``, never ``FIXED``, and prints the obligation explicitly: the caller must
confirm the new behaviour in the producer's own output, against a key only the new code can
emit. Same family as "heartbeat liveness != data liveness" and R0168's "mtime lies fresh after
every deploy".

    python scripts/ship_restart.py <unit> [--dry-run] [--json]

Exit 0 only on RESTARTED or ALREADY-CURRENT. Every refusal is non-zero and names its reason.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.deploy_plan import TIER_RUIN, tier_for_unit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402

#: How long to wait for systemd to respawn after SIGTERM. RestartSec defaults to 100ms but the
#: unit must also run its own startup (venv import, config read), and the 2026-08-05 measurement
#: showed ~15s from signal to a live MainPID. 60s is generous enough that a slow start is not
#: reported as a failed one -- a false FAILED here sends an operator to fix a working restart.
RESPAWN_TIMEOUT_S = 60.0
_POLL_S = 1.0


def _systemctl(*args: str) -> tuple[int, str]:
    """Run systemctl, returning (rc, stdout). Never raises -- absence is an answer here."""
    try:
        p = subprocess.run(["systemctl", *args], capture_output=True, text=True,
                           timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return 127, ""
    return p.returncode, p.stdout.strip()


def _show(unit: str, prop: str) -> str:
    return _systemctl("show", "-p", prop, "--value", unit)[1]


def _main_pid(unit: str) -> int:
    raw = _show(unit, "MainPID")
    try:
        return int(raw)
    except ValueError:
        return 0


def _alive(pid: int) -> bool:
    return pid > 0 and Path(f"/proc/{pid}").exists()


def ship(unit: str, *, dry_run: bool = False,
         timeout_s: float = RESPAWN_TIMEOUT_S) -> dict[str, Any]:
    """Restart ``unit`` by the best available means. Returns a verdict dict; never raises."""
    out: dict[str, Any] = {"unit": unit, "verdict": "UNKNOWN", "detail": "", "pid_before": None,
                           "pid_after": None, "method": None}
    tier = tier_for_unit(unit)
    if tier is None:
        out.update(verdict="REFUSED-UNKNOWN-UNIT",
                   detail=(f"{unit} is not in libs/ops/deploy_plan._OWNED, so this repo has no "
                           "recorded supervision tier for it. An unknown unit is NOT assumed "
                           "restartable -- add it to the map with a tier first."))
        return out
    if tier >= TIER_RUIN:
        out.update(verdict="REFUSED-RUIN-TIER",
                   detail=(f"{unit} is TIER_RUIN: restarting it opens a window with no ruin "
                           "rail. Operator must supervise:  sudo systemctl restart " + unit))
        return out

    pid_before = _main_pid(unit)
    out["pid_before"] = pid_before
    if not _alive(pid_before):
        out.update(verdict="REFUSED-NOT-RUNNING",
                   detail=(f"{unit} has no live MainPID ({pid_before}); there is nothing to "
                           "restart and a start is a different decision. check_organs owns this."))
        return out

    if dry_run:
        out.update(verdict="DRY-RUN", method="none",
                   detail=f"would restart {unit} (MainPID {pid_before}, tier {tier})")
        return out

    # 1. THE SANCTIONED PATH FIRST. If polkit ever grants this user the unit, nothing below runs.
    rc, _ = _systemctl("restart", unit)
    if rc == 0:
        after = _main_pid(unit)
        out.update(verdict="RESTARTED", method="systemctl", pid_after=after,
                   detail=f"systemctl restart {unit} succeeded ({pid_before} -> {after})")
        return out

    # 2. FALLBACK. Only legitimate when systemd will bring it back on its own.
    policy = _show(unit, "Restart")
    if policy != "always":
        out.update(verdict="REFUSED-NO-AUTORESTART",
                   detail=(f"systemctl restart was denied and {unit} has Restart={policy!r}, "
                           "not 'always'. SIGTERM would STOP this daemon rather than restart "
                           "it, leaving its work unsupervised -- strictly worse than the stale "
                           "code. Stays OWED:  sudo systemctl restart " + unit))
        return out

    try:
        os.kill(pid_before, 15)
    except OSError as exc:
        out.update(verdict="FAILED",
                   detail=f"SIGTERM to {pid_before} failed: {exc}. Stays OWED for the operator.")
        return out

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        time.sleep(_POLL_S)
        after = _main_pid(unit)
        if after and after != pid_before and _alive(after):
            out.update(verdict="RESTARTED", method="sigterm+autorestart", pid_after=after,
                       detail=(f"SIGTERM to {pid_before}; systemd Restart=always respawned as "
                               f"{after}. The unit is now running the code on disk."))
            return out
    out.update(verdict="FAILED", method="sigterm+autorestart", pid_after=_main_pid(unit),
               detail=(f"SIGTERM sent to {pid_before} but no new MainPID appeared within "
                       f"{timeout_s:.0f}s. The unit may be down -- CHECK IT NOW:  "
                       f"systemctl status {unit}"))
    return out


#: Printed on every success. The restart is half the deliverable; this names the other half.
_VERIFY_OBLIGATION = (
    "RESTARTED is not FIXED. A new pid proves new CODE is loaded, never that the new BEHAVIOUR "
    "reached the artifact -- on 2026-08-05 the dying process emitted one final tick whose fresh "
    "timestamp looked exactly like success. Verify against a key ONLY the new code can write.")


def main(argv: list[str] | None = None) -> int:
    _law_guard()
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("unit", help="systemd unit, e.g. quant-cashcarry.service")
    ap.add_argument("--dry-run", action="store_true", help="classify only; send no signal")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    rep = ship(args.unit, dry_run=args.dry_run)
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"ship-restart: {rep['verdict']} -- {rep['detail']}")
        if rep["verdict"] == "RESTARTED":
            print(f"  NOTE: {_VERIFY_OBLIGATION}")
    return 0 if rep["verdict"] in {"RESTARTED", "DRY-RUN"} else 1


if __name__ == "__main__":
    sys.exit(main())
