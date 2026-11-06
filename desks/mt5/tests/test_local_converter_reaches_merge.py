"""local_converter's rows must reach the docket even while MT5-MergeDocket holds the writer lane.

Measured on the trading box 2026-11-05: MT5-MergeDocket holds the shared `merge_hypotheses`
lane for its whole run (~27h for one run, 5h54m into the next), so every hourly
MT5-LocalConvert push was refused. The fix is a second door: the converter writes its rows in
the docket's own shape to `local_candidates.json["docket_rows"]`, and merge_hypotheses reads
that file as a SOURCE under its own lock. These tests read both modules' constants, so a
rename on either side fails here instead of silently reopening the hole.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parent.parent
ROOT = DESK.parent.parent
for _p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

merge_hypotheses = pytest.importorskip("merge_hypotheses")
local_converter = pytest.importorskip("local_converter")


def test_the_converter_output_is_a_docket_source() -> None:
    key = dict(merge_hypotheses.SOURCES).get(local_converter.OUT.name, "__ABSENT__")
    assert key == "docket_rows", (
        f"{local_converter.OUT.name} must be read by merge_hypotheses under 'docket_rows'; "
        "without it the converter reaches the docket only through a lane MergeDocket holds "
        "for a day at a time")


def test_docket_rows_are_docket_shaped_stamped_and_deduped() -> None:
    cand = {"kind": "hypothesis", "family": "session_range_breakout", "symbols": ["XAUUSD"],
            "selector": "asia", "source": "local_converter/guba", "evidence": "x"}
    rows = local_converter.docket_rows([cand, dict(cand), {**cand, "selector": None},
                                        {"family": "x"}])
    assert [(r["symbol"], r["family"], r["params"]) for r in rows] == [
        ("XAUUSD", "session_range_breakout", {"selector": "asia"}),
        ("XAUUSD", "session_range_breakout", {}),
    ]
    from libs.data.pit import is_stamped
    assert all(is_stamped(r) for r in rows)
    assert all(r["n"] == 0 and r["exp_r"] is None for r in rows), "no performance is claimed"
