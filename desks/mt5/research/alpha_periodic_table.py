#!/usr/bin/env python3
"""The cartographer's leg: the mechanism x axis matrix, produced on the daily clock.

WHY A MODULE HERE AND THE IMPLEMENTATION THERE (Tier-1 audit G15, 2026-09-08). The matrix lives
in `desks/mt5/side_channels/alpha_periodic_table.py` -- 7 mechanisms x 9 axes, with every cell
the desk has put a hypothesis in marked and every cell it has not left EMPTY -- and it had no
caller anywhere: grep matched only the package's own docstring index. So the desk had no
maintained map of where it has not looked, while the white-space walker that DOES run
(`frontier_intel/unknowns`) reported zero unknown firms and zero unknown capabilities.

`daily_cycle._state_research_feedback` imports its legs BY BARE NAME off `desks/mt5/research`,
so a module inside the side-channel package cannot be one however it is written. This is the
leg; the implementation stays where it is, imported through the same path the package uses.

Pure reader: no network, no terminal, no proposal. An empty cell is a research TARGET -- a
mechanism x axis pair nobody has put a hypothesis in -- which is a fact about the desk's
coverage and never a claim about the market.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
for _p in (str(BASE), str(BASE / "side_channels")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _impl() -> Any:
    """The side-channel implementation, however this process was started."""
    try:
        from side_channels import alpha_periodic_table as impl
    except ImportError:
        import alpha_periodic_table as impl  # type: ignore[no-redef]
    return impl


def run() -> dict[str, Any]:
    """Build and write the matrix. Returns its own summary; raises nothing the cycle must see."""
    return dict(_impl().run())


def main() -> int:
    return int(_impl().main())


if __name__ == "__main__":
    raise SystemExit(main())
