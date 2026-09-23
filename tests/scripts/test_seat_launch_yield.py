"""Tests for scripts/check_seat_launch_yield.py -- the arrivals-collapse fence.

The desk read `ARRIVALS COLLAPSED -- 25 raised against a baseline of 158/week` as a research
verdict and told the next seat to hunt harder. It was an infrastructure defect: 56 of 96
billable seat launches in that week died on `auth unavailable` before launching, concentrated
in a quota-exhausted window. These pin the distinction, because getting it wrong sends the
desk's scarcest resource at a problem it does not have.
"""
from __future__ import annotations

import json

from scripts import check_seat_launch_yield as fence


def test_classify_separates_the_reasons_a_launch_produced_nothing() -> None:
    assert fence.classify("=== x attempt ===\n" + "z" * 5000, 5000) == "PRODUCED"
    assert fence.classify("=== x attempt ===\nauth unavailable -- next run", 60) == \
        "AUTH_UNAVAILABLE"
    assert fence.classify("=== x attempt ===\n... DEFERRED -- brain mutex held", 90) == \
        "MUTEX_DEFERRED"
    assert fence.classify("=== x attempt ===\n=== x start ===", 118) == "DIED_AFTER_START"
    assert fence.classify("=== x attempt ===\n", 58) == "DIED_AT_ATTEMPT"


def _write(logs, name: str, body: str) -> None:
    (logs / name).write_text(body, encoding="utf-8")


def _run(tmp_path, monkeypatch, files: dict[str, str]) -> dict:
    logs = tmp_path / "cro_ai_logs"
    logs.mkdir()
    for name, body in files.items():
        _write(logs, name, body)
    monkeypatch.setattr(fence, "LOGS", logs)
    monkeypatch.setattr(fence, "OUT", tmp_path / "yield.json")
    monkeypatch.setattr(fence, "FLOOR", tmp_path / "floor.json")
    return fence.scan(7.0)


def test_mutex_deferral_is_not_counted_as_a_failed_launch(tmp_path, monkeypatch) -> None:
    """A deferral is the mutex working, and organ_catchup re-fires the loser within 5 minutes.

    Counting it as failure would make correct serialisation look like a defect and push a
    future seat to delete the lock that stopped two --effort max brains sharing one working
    tree and one quota.
    """
    rep = _run(tmp_path, monkeypatch, {
        "a_20260826T0500.log": "=== a attempt x ===\n" + "z" * 5000,
        "b_20260826T0500.log": "=== b attempt x ===\n2026 b DEFERRED -- brain mutex held by a",
    })
    assert rep["launches"] == 2
    assert rep["billable"] == 1          # the deferral is not a slot the desk lost
    assert rep["yield_pct"] == 100.0


def test_starved_hour_is_caught_even_when_it_produced_something(tmp_path, monkeypatch) -> None:
    """REGRESSION on this fence's own first cut, which tested `produced == 0`.

    That zero-test called 15:00 UTC healthy while it burned 36 attempts for 3 digs (8%) against
    a desk yield of 28% -- it would have missed the exact window that caused the collapse the
    fence was written for. A window losing four slots in five is the defect whether or not the
    fifth one lands, so the test is a RATE against the desk's own average.
    """
    files = {}
    # 05:00 -- healthy: 4 of 4 produce.
    for i in range(4):
        files[f"good{i}_20260826T0500.log"] = "=== good attempt x ===\n" + "z" * 5000
    # 15:00 -- starved: 1 of 8 produces (12.5%), far under the desk rate, but NOT zero.
    files["bad0_20260826T1500.log"] = "=== bad attempt x ===\n" + "z" * 5000
    for i in range(1, 8):
        files[f"bad{i}_20260826T1500.log"] = "=== bad attempt x ===\nauth unavailable -- next"

    rep = _run(tmp_path, monkeypatch, files)
    assert 15 in rep["starved_hours_utc"], "a window producing 1-in-8 must be flagged"
    assert 15 not in rep["dead_hours_utc"], "it is starved, not dead -- it did produce once"
    assert rep["productive_hours_utc"] == [5]


def test_productive_hours_must_beat_the_desk_average_not_merely_be_nonzero(
        tmp_path, monkeypatch) -> None:
    """The report tells seats to MOVE INTO these hours, so 'less bad than the worst' is not an
    answer -- a window at half the desk rate would send miners into a second wall."""
    files = {f"g{i}_20260826T0500.log": "=== g attempt x ===\n" + "z" * 5000 for i in range(5)}
    for i in range(3):   # 20:00 -- 1 of 3, below the desk average once 05:00 is counted
        files[f"m{i}_20260826T2000.log"] = "=== m attempt x ===\nauth unavailable -- next"
    files["m9_20260826T2000.log"] = "=== m attempt x ===\n" + "z" * 5000

    rep = _run(tmp_path, monkeypatch, files)
    assert rep["productive_hours_utc"] == [5]
    assert 20 not in rep["productive_hours_utc"]


def test_no_launches_at_all_is_a_breach_not_a_clean_verdict(tmp_path, monkeypatch) -> None:
    """L1.28a / WS-005: absence never resolves to a pass. Seats not being FIRED is worse than
    seats firing and failing, so an empty window must not read as 100% healthy."""
    rep = _run(tmp_path, monkeypatch, {"unrelated.log": "no attempt header here\n"})
    assert rep["launches"] == 0
    assert rep["yield_pct"] is None      # UNMEASURED, never 0.0-that-rounds-to-fine


def test_floor_ratchets_up_only(tmp_path, monkeypatch, capsys) -> None:
    logs = tmp_path / "cro_ai_logs"
    logs.mkdir()
    _write(logs, "a_20260826T0500.log", "=== a attempt x ===\n" + "z" * 5000)
    monkeypatch.setattr(fence, "LOGS", logs)
    monkeypatch.setattr(fence, "OUT", tmp_path / "yield.json")
    floor = tmp_path / "floor.json"
    monkeypatch.setattr(fence, "FLOOR", floor)
    monkeypatch.setattr("sys.argv", ["check_seat_launch_yield.py"])

    fence.main()
    assert json.loads(floor.read_text())["yield_pct_floor"] == 100.0

    # A worse week must NOT lower the floor -- it must breach against it.
    _write(logs, "b_20260826T0500.log", "=== b attempt x ===\nauth unavailable -- next")
    rc = fence.main()
    assert json.loads(floor.read_text())["yield_pct_floor"] == 100.0
    assert rc == 2
