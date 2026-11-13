"""THE ROSTER LEAVES ON POSITIVE EVIDENCE ONLY, and the sub-field counts too.

`accumulate` pops rows out of a PERSISTED roster (`reports/FORWARD_CURE_ROSTER.json`), so it is a
destructive path and is declared as one in `libs.ops.reference_freshness.DESTRUCTIVE_PATHS`. It is
`positive` because an absent, unreadable or verdict-less gate report retires nothing -- and because
a validity gate the verdict does not carry is UNJUDGED rather than failed. That last clause read
the other way until 2026-09-24, when 32,773 of the 140,090 verdicts in the live report were
measured carrying non-empty stages with no validity gate in them at all.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK / "research"), str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import forward_cure_route as FCR  # noqa: E402


def _w(p: Path, doc: object) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=1), encoding="utf-8")


def _r(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _desk(tmp_path: Path, verdicts: object) -> Path:
    base = tmp_path / "desk"
    reports = base / "desks" / "mt5" / "reports"
    _w(reports / "POWER_CURE_CANDIDATES.json", {
        "swept_at": "2026-09-24T00:00:00+00:00",
        "candidates": {
            "external.EURUSD.carry": {"promotion_authority": False},
            "external.AUDNZD.session_range_breakout": {"promotion_authority": False}}})
    if verdicts is not None:
        _w(reports / "universal_gates_external.json", {"verdicts": verdicts})
    return base


def _roster(base: Path) -> dict:
    return _r(base / "desks" / "mt5" / "reports" / "FORWARD_CURE_ROSTER.json")


def test_an_absent_gate_report_retires_nothing(tmp_path: Path):
    base = _desk(tmp_path, None)
    census = FCR.accumulate(base)
    assert census["n_roster"] == 2 and census["retired_this_pass"] == 0


def test_a_verdict_with_no_stages_retires_nothing(tmp_path: Path):
    base = _desk(tmp_path, [{"cell": "EURUSD.carry", "stages": {}, "passed": False}])
    FCR.accumulate(base)
    census = FCR.accumulate(base)
    assert census["retired_this_pass"] == 0
    assert "external.EURUSD.carry" in _roster(base)["rows"]


def test_a_validity_gate_absent_from_a_present_verdict_is_unjudged_never_failed(tmp_path: Path):
    """THE FIX, PINNED. A verdict that carries stages but not one validity gate -- 32,773 of the
    140,090 in the live report -- is a cell the judge did not finish, never a cell that failed."""
    base = _desk(tmp_path, [{"cell": "EURUSD.carry", "passed": False,
                             "stages": {"observations": {"n": 12}}}])
    FCR.accumulate(base)
    census = FCR.accumulate(base)
    assert census["retired_this_pass"] == 0
    assert "external.EURUSD.carry" in _roster(base)["rows"]


def test_a_validity_gate_that_is_present_and_failed_still_retires_the_row(tmp_path: Path):
    """AND THE FIX DOES NOT DISARM THE RULE: an explicit validity failure is positive evidence."""
    base = _desk(tmp_path, [{"cell": "EURUSD.carry", "passed": False,
                             "stages": {"observations": {"n": 12},
                                        "pbo": {"passed": False}}}])
    FCR.accumulate(base)
    census = FCR.accumulate(base)
    assert census["retired_this_pass"] == 1
    assert census["retired_by_reason"] == {"VALIDITY_FAIL": 1}
    assert "external.EURUSD.carry" not in _roster(base)["rows"]


def test_a_cell_that_now_passes_all_ten_leaves_for_the_canon(tmp_path: Path):
    base = _desk(tmp_path, [{"cell": "EURUSD.carry", "passed": True,
                             "stages": {"pbo": {"passed": True}}}])
    FCR.accumulate(base)
    census = FCR.accumulate(base)
    assert census["retired_by_reason"] == {"CERTIFIED": 1}


def test_the_destructive_path_is_declared():
    from libs.ops import reference_freshness as RFR
    row = RFR.by_id("forward_cure_route.accumulate")
    assert row is not None and row.status == "positive"
    assert row.module == "desks/mt5/research/forward_cure_route.py"
