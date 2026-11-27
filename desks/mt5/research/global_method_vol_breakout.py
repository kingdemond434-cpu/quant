"""The hourly leg `global_vol_breakout`: one pass of
`research/global_methods.py --method vol_breakout`.

A file of its own so the leg's clock, its producer and its artifact are one declaration each
(`desks/mt5/ops/components.own_artifact` reads REPORT below, unimported). All the logic is in
`global_methods.py`; this only names the method.

    python research/global_method_vol_breakout.py --once --budget-s 240
"""
from __future__ import annotations

import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
REPORT = _DESK / "reports" / "GLOBAL_METHOD_VOL_BREAKOUT.json"
METHOD = "vol_breakout"


def main(argv: list[str] | None = None) -> int:
    for p in (str(_DESK), str(_DESK / "research"), str(_DESK.parents[1])):
        if p not in sys.path:
            sys.path.insert(0, p)
    from research import global_methods

    return global_methods.main(["--method", METHOD, *(sys.argv[1:] if argv is None else argv)])


if __name__ == "__main__":
    sys.exit(main())
