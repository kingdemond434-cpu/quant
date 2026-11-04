"""A mechanism-genome cross is donated only with params its family reads.

2026-11-04: children were donated as {mechanism_genome, crossed_slot}, params no family reads, so
every cross ran as its parent's default cell. A cross now executes through the parent's own
time-exit kwarg (the holding slot) or is reported UNEXECUTABLE, never relabelled.
"""
from __future__ import annotations

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
for _p in (str(BASE), str(BASE.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import alpha_genome as ag  # noqa: E402


def test_holding_cross_carries_the_donor_time_exit() -> None:
    params, why = ag.executable_cross({"slot": "holding", "from_family": "session_range_breakout",
                                       "to_family": "overnight_drift"})
    assert why == "" and params == {"ttl_bars": 8}


def test_a_slot_with_no_kwarg_is_unexecutable_not_a_default_cell() -> None:
    params, why = ag.executable_cross({"slot": "actor", "from_family": "session_range_breakout",
                                       "to_family": "overnight_drift"})
    assert params is None and "no family kwarg" in why


def test_identical_holding_is_unexecutable() -> None:
    params, why = ag.executable_cross({"slot": "holding", "from_family": "session_range_breakout",
                                       "to_family": "level_breakout"})
    assert params is None and "is its parent" in why


def test_unknown_family_is_unexecutable() -> None:
    params, _why = ag.executable_cross({"slot": "holding", "from_family": "no_such_family",
                                       "to_family": "overnight_drift"})
    assert params is None
