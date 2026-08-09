"""§42 ledger: the SKIP test is denominated in live sweeps, and the queue is measured as a queue.

MEASURED 2026-08-05, over the ledger's whole life: the old fence -- "any row open past 24h is a
DEFECT" -- read RED for 226 of its 226 informative hours (the only 24 green ones were before any
row could age past grace). Median disposition latency was 37.8h against a 24h grace, so only 41.8%
of rows ever cleared it. A gate that is always on carries no information (L1.43), and the desk's own
§37 brief was independently computing the discriminating measure -- sweeps the brain was AWAKE for
-- from `data/carryover_sweeps.jsonl` while this fence, looking at the same backlog, judged on
elapsed hours alone.

The obligation is UNCHANGED: every row still owes a disposition and every owed row is still printed.
What changed is which rows are called SKIPS, plus a detector the desk did not have at all -- on
2026-08-01 the ledger took 131 arrivals against 48 dispositions and the level-based fence said
exactly what it said on a day the queue drained.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import scripts.recommendations as rec


def _row(rid: str, *, age_h: float, status: str = "open", due: str | None = None) -> dict[str, Any]:
    raised = (datetime.now(tz=UTC) - timedelta(hours=age_h)).isoformat()
    return {"id": rid, "source": "cycle", "summary": f"{rid} summary", "roi_bps": 1.0,
            "raised": raised, "status": status, "reason": None, "commit": None,
            "due": due, "disposed": None}


def _sweeps(tmp_path: Any, sweeps: list[tuple[bool, list[str]]]) -> None:
    path = tmp_path / "carryover_sweeps.jsonl"
    path.write_text("\n".join(
        json.dumps({"ts": 1.0, "alive": alive, "ids": [f"rec-owed-{i}" for i in ids]})
        for alive, ids in sweeps), "utf-8")
    rec.SWEEPS = path


@pytest.fixture(autouse=True)
def _restore() -> Any:
    original = rec.SWEEPS
    yield
    rec.SWEEPS = original


def test_a_row_shown_to_live_sweeps_is_a_skip(tmp_path: Any) -> None:
    _sweeps(tmp_path, [(True, ["R1"]), (True, ["R1"])])
    assert rec.sweeps_shown() == {"R1": 2}


def test_a_sweep_the_brain_slept_through_shows_nobody_anything(tmp_path: Any) -> None:
    """17 cycles were lost to quota. A row raised into one of them was walked past by no one."""
    _sweeps(tmp_path, [(False, ["R1"]), (False, ["R1"]), (True, ["R1"])])
    assert rec.sweeps_shown() == {"R1": 1}          # the two dead sweeps do not count


def test_an_absent_sweep_record_degrades_toward_more_alarm_not_less(tmp_path: Any) -> None:
    """Every owed row then reports zero sweeps and none can claim the queued exemption."""
    rec.SWEEPS = tmp_path / "does-not-exist.jsonl"
    assert rec.sweeps_shown() == {}


def test_an_unreadable_sweep_line_is_skipped_not_fatal(tmp_path: Any) -> None:
    path = tmp_path / "s.jsonl"
    path.write_text('{"alive": true, "ids": ["rec-owed-R1"]}\nNOT JSON\n\n', "utf-8")
    rec.SWEEPS = path
    assert rec.sweeps_shown() == {"R1": 1}


def test_drain_separates_a_queue_being_worked_from_one_running_away() -> None:
    """The property a LEVEL cannot express, and the old fence only had a level."""
    now = datetime.now(tz=UTC)
    runaway = {"recommendations": [
        *[_row(f"A{i}", age_h=5.0) for i in range(6)],
        {**_row("D1", age_h=5.0), "disposed": (now - timedelta(hours=2)).isoformat()},
    ]}
    fl = rec.drain(runaway)
    assert fl["arrived"] == 7 and fl["disposed"] == 1 and fl["net"] == -6

    draining = {"recommendations": [
        _row("A1", age_h=5.0),
        *[{**_row(f"D{i}", age_h=200.0), "disposed": (now - timedelta(hours=2)).isoformat()}
          for i in range(4)],
    ]}
    fl2 = rec.drain(draining)
    assert fl2["arrived"] == 1 and fl2["disposed"] == 4 and fl2["net"] == +3


def test_drain_ignores_activity_outside_the_window() -> None:
    old = {"recommendations": [_row("A1", age_h=500.0)]}
    assert rec.drain(old, window_h=72.0)["arrived"] == 0


def test_the_obligation_is_unchanged_only_the_skip_label_narrows(tmp_path: Any) -> None:
    """THE ANTI-LOOSENING TEST. Every owed row is still owed and still printed."""
    _sweeps(tmp_path, [(True, ["R1"]), (True, ["R1"])])       # R1 shown twice, R2 never
    d = {"recommendations": [_row("R1", age_h=100.0), _row("R2", age_h=100.0)]}
    orphans, overdue = rec.owed(d)
    assert {r["id"] for r in orphans} == {"R1", "R2"}          # BOTH still owe a disposition
    assert not overdue

    shown = rec.sweeps_shown()
    assert shown.get("R1", 0) >= rec.SKIP_SWEEPS               # genuinely skipped
    assert shown.get("R2", 0) < rec.SKIP_SWEEPS                # queued, never presented


def test_grace_still_decides_who_is_owed_at_all(tmp_path: Any) -> None:
    """The duty horizon is untouched -- a fresh row owes nothing yet, an aged one does."""
    _sweeps(tmp_path, [])
    d = {"recommendations": [_row("FRESH", age_h=1.0), _row("AGED", age_h=rec.GRACE_H + 1.0)]}
    orphans, _ = rec.owed(d)
    assert [r["id"] for r in orphans] == ["AGED"]


def test_a_terminal_row_with_no_disposed_stamp_is_counted_not_dropped() -> None:
    """R0259: 15 rows (35 by 2026-08-05) reached a terminal state through organs writing the JSON
    directly, so they carry no `disposed` stamp. An undercounted numerator biases the drain verdict
    toward RUNNING AWAY -- the direction that manufactures a false alarm."""
    d = {"recommendations": [
        {**_row("T1", age_h=200.0), "status": "screened"},
        {**_row("T2", age_h=200.0), "status": "done"},
        _row("OPEN1", age_h=200.0),                                    # still owed, not terminal
        {**_row("S1", age_h=200.0, status="scheduled", due="2099-01-01")},
    ]}
    fl = rec.drain(d)
    assert fl["terminal_unstamped"] == 2          # T1 and T2 only
    assert fl["arrived"] == 0 and fl["disposed"] == 0


@pytest.mark.parametrize("status", ["done", "screened"])
def test_the_real_cli_accepts_the_vocabulary_the_desk_actually_writes(
    tmp_path: Any, monkeypatch: Any, status: str,
) -> None:
    """Teaching the CLI beats migrating rows to `implemented`: a SCREENED axis is not an
    implemented recommendation, and collapsing them makes the conversion record lie.

    Drives the REAL `main()` against a temp ledger -- a test that rebuilds its own argparse copy
    would pass whether or not the shipped CLI ever learned the words.
    """
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps({"recommendations": [_row("R1", age_h=100.0)]}), "utf-8")
    monkeypatch.setattr(rec, "LEDGER", ledger)
    monkeypatch.setattr(rec, "_forecast_add", lambda *a, **k: None, raising=False)
    reason = "a substantive reason, long enough to be a record"
    monkeypatch.setattr("sys.argv", ["recommendations.py", "dispose", "--id", "R1",
                                     "--status", status, "--reason", reason])
    rec.main()
    assert json.loads(ledger.read_text("utf-8"))["recommendations"][0]["status"] == status
