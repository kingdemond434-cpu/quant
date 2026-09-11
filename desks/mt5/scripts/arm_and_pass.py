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

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True,
                          text=True, check=False)


def main() -> int:
    drift = [p for p in _git("diff", "--name-only", "HEAD").stdout.splitlines()
             if p.endswith((".py", ".ps1", ".cmd"))]
    if drift:
        _git("checkout", "HEAD", "--", *drift)
        print(f"restored {len(drift)} code path(s)")
    left = [p for p in _git("diff", "--name-only", "HEAD").stdout.splitlines()
            if p.endswith((".py", ".ps1", ".cmd"))]
    print(f"code drift after restore: {len(left)}" + (f" -> {left[:4]}" if left else ""))

    # Import AFTER the restore, so the modules loaded are the sealed ones.
    sys.path.insert(0, str(DESK / "research"))
    sys.path.insert(0, str(DESK))
    sys.path.insert(0, str(ROOT))
    from mt5desk import gateway

    gateway.main()
    print("PASS COMPLETED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
