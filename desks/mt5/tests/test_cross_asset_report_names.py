"""The cross-asset proposer writes two files; on the Windows trading box names are compared
without case, so two names that differ only by case are ONE file and the second write wins."""
from __future__ import annotations

import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import cross_asset_graph as x  # noqa: E402


def test_the_edge_list_and_the_summary_are_different_files_on_windows() -> None:
    assert x.GRAPH.parent == x.REPORT.parent
    assert x.GRAPH.name.casefold() != x.REPORT.name.casefold()
