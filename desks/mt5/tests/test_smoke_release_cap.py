"""The hourly smoke's subprocess cap sits above its measured run time (box, 11-08..11-11)."""
from __future__ import annotations

import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

MEASURED_P90_S = 121.9  # compute_ledger, 73 runs: 26 were killed at the old 120 s cap


def test_the_cap_is_above_the_measured_p90() -> None:
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert "timeout=SMOKE_RELEASE_TIMEOUT_S" in src
    import hourly_cycle

    assert hourly_cycle.SMOKE_RELEASE_TIMEOUT_S >= 2 * MEASURED_P90_S
