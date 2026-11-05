"""The weekly hunt sweep may not crash on a family the library renamed or retired.

MEASURED 11-01, 11-02, 11-04 on the Contabo box: `weekly_hunt_refresh` failed at 20 s every
time with `module 'mt5desk.families' has no attribute 'family7_spread_state_avoidance'`, raised
at run_hunt7's import, so hunts 7-12 never ran. Families are now resolved by name; a retired one
is dropped and named, and a NEW missing name fails here instead of on the box.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk import families  # noqa: E402

#: Retired from the library on purpose (see run_edges_macro_fusion_sweep.EDGE_NAMES).
RETIRED = {"family7_spread_state_avoidance"}


def _names() -> list[str]:
    tree = ast.parse((_DESK / "research" / "run_hunt7.py").read_text("utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", "") == "_GLOBAL_FAMILY_NAMES" for t in node.targets):
            return [e.elts[1].value for e in node.value.elts]  # type: ignore[attr-defined]
    raise AssertionError("_GLOBAL_FAMILY_NAMES is gone from run_hunt7 -- re-pin this test")


def test_every_hunt7_family_resolves_or_is_a_known_retirement() -> None:
    missing = {n for n in _names() if not hasattr(families, n)}
    assert missing <= RETIRED, f"run_hunt7 names families the library lacks: {missing - RETIRED}"


def test_the_family_list_is_resolved_by_name_never_by_bare_attribute() -> None:
    src = (_DESK / "research" / "run_hunt7.py").read_text("utf-8")
    assert "families.family7_spread_state_avoidance" not in src
    assert "families.family4_comex_settlement_effect" not in src
