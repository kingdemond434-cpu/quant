"""A cell the judge could not test for want of observations leaves the backlog, named, until its
history grows -- and a cell with a fixable defect does not.

MEASURED ON THE TRADING BOX 2026-10-07: JUDGE_COVERAGE read 1,389,434 unjudged cells, GROWING,
while the latest sweep's UNKNOWN rows were mostly "never fires" (174,024) and "too rare"
(10,188): cells that WERE judged and came back with under the 60 daily observations CPCV and
walk-forward need. They were parked in the unrunnable bank with a re-admission rule, yet still
counted as backlog, so the count could only rise. These tests pin the NOT_TESTABLE class: out of
the backlog, counted per family and per reason, back in when the bank re-admits the cell, and
never applied to the defect classes (`series_exception`, `missing_identity_input`).
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import judge_coverage as jc  # noqa: E402
from research import judging_burndown as jb  # noqa: E402

NOW = datetime(2026, 10, 7, 2, 0, tzinfo=UTC)


def _rows(n: int, fam: str = "alpha") -> list[dict]:
    seen = (NOW - timedelta(hours=5)).isoformat()
    return [{"symbol": f"S{i}", "family": fam, "params": {"rr": 1.0 + i}, "first_seen": seen}
            for i in range(n)]


@pytest.fixture()
def bank(tmp_path, monkeypatch):
    path = tmp_path / "unrunnable_specs.json"
    monkeypatch.setattr(jc, "UNRUNNABLE_BANK", path)
    return path


def _park(path: Path, cells: dict[str, str]) -> None:
    path.write_text(json.dumps({c: {"reason": r, "sym": "S", "family": "alpha", "tf": "H1",
                                    "days": 0, "bar_bytes": 10, "parked_at": NOW.isoformat()}
                                for c, r in cells.items()}), "utf-8")


def test_not_testable_cells_leave_the_backlog_and_are_counted(bank, tmp_path) -> None:
    rows = _rows(5)
    ids = [jc._cell_id(r) for r in rows]
    _park(bank, {ids[0]: "never_fires", ids[1]: "too_rare", ids[2]: "series_exception"})
    doc = jc.build(rows, ledger=tmp_path / "none.jsonl", ratchet=tmp_path / "r.json", now=NOW)
    t = doc["totals"]
    assert t["unjudged_total"] == 3                     # the defect stays owed, as do 2 fresh cells
    assert t["not_testable_total"] == 2
    assert t["not_testable_by_reason"] == {"never_fires": 1, "too_rare": 1}
    assert doc["families"]["alpha"]["not_testable"] == 2


def test_the_defect_classes_are_never_not_testable() -> None:
    assert "series_exception" not in jc.NOT_TESTABLE_REASONS
    assert "missing_identity_input" not in jc.NOT_TESTABLE_REASONS
    assert "missing_bars" not in jc.NOT_TESTABLE_REASONS


def test_an_unreadable_bank_counts_everything_as_backlog(bank, tmp_path) -> None:
    bank.write_text("{not json", "utf-8")
    doc = jc.build(_rows(3), ledger=tmp_path / "none.jsonl", ratchet=tmp_path / "r.json",
                   now=NOW)
    assert doc["totals"]["unjudged_total"] == 3
    assert doc["totals"]["not_testable_total"] == 0


def test_a_readmitted_cell_is_backlog_again(bank, tmp_path) -> None:
    """The class is the bank's state, so `readmit_due` decides when a cell is owed again."""
    rows = _rows(1)
    _park(bank, {jc._cell_id(rows[0]): "never_fires"})
    assert jc.not_testable_index() == {jc._cell_id(rows[0]): "never_fires"}
    bank.write_text("{}", "utf-8")                       # re-admitted by the bank
    doc = jc.build(rows, ledger=tmp_path / "none.jsonl", ratchet=tmp_path / "r.json", now=NOW)
    assert doc["totals"]["unjudged_total"] == 1


def test_burndown_counts_a_first_not_testable_reading_as_drain(tmp_path) -> None:
    at = (NOW - timedelta(hours=1)).isoformat()
    rows = [
        {"cell": "a", "terminal_gate": "UNKNOWN", "unknown_reason": "no_signals"},
        {"cell": "b", "terminal_gate": "UNKNOWN", "unknown_reason": "too_rare"},
        {"cell": "c", "terminal_gate": "UNKNOWN", "unknown_reason": "series_exception"},
        {"cell": "d", "terminal_gate": "cpcv", "passed": False},
        {"cell": "b", "terminal_gate": "walk_forward", "passed": False},   # b ruled later
    ]
    led = tmp_path / "gate.jsonl"
    led.write_text("".join(json.dumps({**r, "at": at}) + "\n" for r in rows), "utf-8")
    d = jb.drain(NOW, led)
    assert d["first_rulings"]["24h"] == 2               # d, b
    assert d["first_settled"]["24h"] == 3               # a, b (once), d -- never c
    assert d["rows"]["24h"]["not_testable"] == 2
    assert d["rows"]["24h"]["unknown"] == 1


def test_classify_names_only_data_scarcity_as_not_testable() -> None:
    for why in jb.NOT_TESTABLE_UNKNOWN:
        assert jb.classify({"terminal_gate": "UNKNOWN", "unknown_reason": why}) == "not_testable"
    for why in ("series_exception", "no_series", "no_terminal_gate_recorded", ""):
        assert jb.classify({"terminal_gate": "UNKNOWN", "unknown_reason": why}) == "unknown"


def test_the_verdict_divides_by_the_backlogs_own_outflow() -> None:
    b = {"status": "MEASURED", "unjudged": 1000}
    i = {"status": "MEASURED", "created_per_hour": {"7d": 10.0, "24h": 10.0}}
    d = {"status": "MEASURED", "first_rulings_per_hour": {"7d": 5.0, "24h": 5.0},
         "first_settled_per_hour": {"7d": 20.0, "24h": 20.0}}
    v = jb.verdict(b, d, i, "7d")
    assert v["status"] == "DRAINING" and v["first_settled_per_hour"] == 20.0
    assert v["first_rulings_per_hour"] == 5.0


def test_fetch_universe_writes_the_swap_reading() -> None:
    src = (DESK / "research" / "fetch_universe.py").read_text("utf-8")
    assert '("swap_long", "swap_short", "swap_mode")' in src
