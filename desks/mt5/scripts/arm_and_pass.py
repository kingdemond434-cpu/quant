"""Restore the money path to HEAD and run ONE gateway pass, atomically.

WHY THE TWO STEPS CANNOT BE SEPARATE. `release_identity` refuses new risk whenever any tracked
code path differs from the sealed release, and the gateway checks that verdict before it reaches
`place_bracket` (gateway.py:2116). On this box something rewrites the tree continuously -- measured
2026-09-11, a single file (`shadow_forward.py`) reappeared between a restore and the next pass, and
that alone was enough to log:

    [xau_m15_anti_breakout] WOULD PLACE (scalp exec not armed; enable=GENERIC_EXEC_ENABLED):
        SELL 0.01 XAUUSD @market sl=4363.42416 tp=4339.23876

The signal was computed, the size was computed, the order was fully described -- and it was not
sent, because `armed = st["armed"] and GENERIC_EXEC_ENABLED.exists() and NEW_RISK_OK` had one
false term. Restoring in one shell and passing in the next leaves a window of seconds, and the
window is losing.

This closes it: restore, verify, then pass, in one process. It is a STOPGAP for exactly as long as
the tree keeps moving. The real fix is that nothing rewrites it; delete this once that holds.

    python desks/mt5/scripts/arm_and_pass.py
"""
from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from libs.ops.git_writer_lock import git_writer_lock, run_git  # noqa: E402

DESK = ROOT / "desks" / "mt5"


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True,
                          text=True, check=False)


def main() -> int:
    drift = [p for p in _git("diff", "--name-only", "HEAD").stdout.splitlines()
             if p.endswith((".py", ".ps1", ".cmd"))]
    if drift:
        # A CHECKOUT TAKES `.git/index.lock`, SO IT TAKES THE DESK'S LOCK FIRST (2026-09-23).
        # This runs on the trading box beside an hourly adoption that stages thousands of paths
        # of its own; whichever writer lost the index died on `fatal: Unable to create
        # '.git/index.lock': File exists`, and when the loser was the adoption the box ran
        # unshipped code for another hour -- four days of it. A lock this pass could not take is
        # REPORTED, never written through: restoring code under another writer's index is how
        # drift becomes corruption.
        with git_writer_lock(ROOT, timeout_s=120.0) as lock:
            if not lock.held:
                print(f"NOT restoring {len(drift)} code path(s): {lock.why} ({lock.mechanism})")
            else:
                rc, out, notes = run_git(ROOT, ["checkout", "HEAD", "--", *drift], timeout=180)
                for note in notes:
                    print(note)
                if rc != 0:
                    print(f"git checkout HEAD -- <{len(drift)} path(s)> rc={rc}: "
                          f"{out.strip()[:200]}")
                else:
                    print(f"restored {len(drift)} code path(s)")
    left = [p for p in _git("diff", "--name-only", "HEAD").stdout.splitlines()
            if p.endswith((".py", ".ps1", ".cmd"))]
    print(f"code drift after restore: {len(left)}" + (f" -> {left[:4]}" if left else ""))

    # Import AFTER the restore, so the modules loaded are the sealed ones.
    sys.path.insert(0, str(DESK / "research"))
    sys.path.insert(0, str(DESK))
    sys.path.insert(0, str(ROOT))
    # `mt5desk` is a namespace package under desks/mt5 that exists on sys.path only AFTER the
    # three inserts above, so a STATIC import of it is a claim the checker cannot verify and
    # resolves differently depending on which other files are in the same mypy run. The import
    # is deliberately late; saying so with importlib makes the lateness the visible fact.
    gateway = importlib.import_module("mt5desk.gateway")

    gateway.main()
    print("PASS COMPLETED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
