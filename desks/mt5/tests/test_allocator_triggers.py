"""ONE TRIGGER, EVERY ALLOCATOR (research/allocator_triggers.py): events start the allocators'
own tasks early; it never sizes or sends."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import allocator_triggers as at  # noqa: E402

NOW = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)


def _ftmo(**kw: Any) -> dict[str, Any]:
    doc = {"status": "OK", "phase": "phase1", "initial_balance": 100_000.0,
           "day_start_balance": 100_000.0, "equity": 100_000.0, "open_positions": []}
    doc.update(kw)
    return doc


@pytest.fixture
def box(monkeypatch, tmp_path) -> dict[str, list[str]]:
    for name in ("OUT", "STATE", "LEDGER", "FTMO_STATE", "E8_EXEC", "SURVIVORS", "DOOR"):
        monkeypatch.setattr(at, name, tmp_path / f"{name.lower()}.json")
    _write(at.FTMO_STATE, _ftmo())
    _write(at.SURVIVORS, {"survivors": {"a": {}, "b": {}}})
    return {"started": []}


def _write(p: Path, doc: Any) -> None:
    p.write_text(json.dumps(doc), "utf-8")


def _run(box: dict[str, list[str]], now: datetime) -> dict[str, Any]:
    def start(task: str) -> str:
        box["started"].append(task)
        return "started"
    return at.run(now=now, start_task=start)


def test_a_first_sighting_starts_nothing(box) -> None:
    doc = _run(box, NOW)
    assert doc["status"] == "OK" and box["started"] == []


def test_a_fill_restarts_the_ftmo_allocator_only(box) -> None:
    _run(box, NOW)
    _write(at.FTMO_STATE, _ftmo(open_positions=[{"symbol": "XAUUSD", "side": "long",
                                                  "volume": 0.5}]))
    doc = _run(box, NOW + timedelta(minutes=5))
    assert box["started"] == ["MT5-FTMO-Allocator"]
    assert doc["subscribers"]["ftmo_allocator"]["events"] == ["FILL"]
    rows = [json.loads(x) for x in Path(at.LEDGER).read_text("utf-8").splitlines()]
    assert rows[0]["subscriber"] == "ftmo_allocator" and rows[0]["events"] == ["FILL"]


def test_equity_toward_the_daily_limit_and_back_both_trigger(box) -> None:
    _run(box, NOW)
    _write(at.FTMO_STATE, _ftmo(equity=98_600.0))           # 1,400 of 5,000 used: quarter 1
    _run(box, NOW + timedelta(minutes=15))
    _write(at.FTMO_STATE, _ftmo(equity=99_000.0))           # 1,000 used: back to quarter 0
    _run(box, NOW + timedelta(minutes=30))
    _write(at.FTMO_STATE, _ftmo(equity=100_100.0))          # still quarter 0: no event
    _run(box, NOW + timedelta(minutes=45))
    assert box["started"] == ["MT5-FTMO-Allocator", "MT5-FTMO-Allocator"]


def test_a_phase_change_triggers(box) -> None:
    _run(box, NOW)
    _write(at.FTMO_STATE, _ftmo(phase="phase2"))
    doc = _run(box, NOW + timedelta(minutes=5))
    assert "PHASE" in doc["subscribers"]["ftmo_allocator"]["events"]


def test_a_new_certificate_restarts_every_subscriber(box) -> None:
    _run(box, NOW)
    _write(at.SURVIVORS, {"survivors": {"a": {}, "b": {}, "c": {}}})
    doc = _run(box, NOW + timedelta(minutes=5))
    assert sorted(box["started"]) == sorted(t for t, _, _ in at.SUBSCRIBERS.values())
    assert doc["new_certified"] == 1


def test_a_burst_is_debounced_and_kept_pending(box) -> None:
    _run(box, NOW)
    _write(at.FTMO_STATE, _ftmo(open_positions=[{"symbol": "EURUSD", "side": "long",
                                                  "volume": 1}]))
    _run(box, NOW + timedelta(minutes=1))
    _write(at.FTMO_STATE, _ftmo(open_positions=[]))
    doc = _run(box, NOW + timedelta(minutes=2))                 # inside the 600 s debounce
    assert box["started"] == ["MT5-FTMO-Allocator"]
    assert doc["subscribers"]["ftmo_allocator"]["pending"] == ["FILL"]
    doc = _run(box, NOW + timedelta(minutes=12))                # the gap has passed
    assert box["started"] == ["MT5-FTMO-Allocator"] * 2
    assert doc["subscribers"]["ftmo_allocator"]["pending"] == ["FILL"]  # what it dispatched
    assert at._read(at.STATE)["pending"]["ftmo_allocator"] == []


def test_new_acknowledged_door_rows_are_an_order_event(box) -> None:
    door = Path(at.DOOR)
    door.write_text(json.dumps({"at": "2026-11-16T08:00:00+00:00", "caller": "e8_executor",
                                "outcome": "acknowledged"}) + "\n", "utf-8")
    _run(box, NOW)
    with door.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": "2026-11-16T09:01:00+00:00", "caller": "e8_gold:oco_watch",
                             "outcome": "acknowledged"}) + "\n")
    doc = _run(box, NOW + timedelta(minutes=5))
    assert box["started"] == ["E8-Book"] and doc["subscribers"]["e8_book"]["events"] == ["ORDER"]


def test_e8_daily_room_from_the_guard(box) -> None:
    def guard(equity: float, room: float) -> dict[str, Any]:
        return {"guard": {"day_start": 100_000.0, "equity": equity,
                          "room_to_daily_floor": room}}
    _write(at.E8_EXEC, guard(100_000.0, 2_500.0))
    _run(box, NOW)
    _write(at.E8_EXEC, guard(98_700.0, 1_200.0))                # 52% of the day's room used
    doc = _run(box, NOW + timedelta(minutes=5))
    assert doc["subscribers"]["e8_book"]["events"] == ["DAILY_ROOM"]


def test_unreadable_sources_trigger_nothing_and_never_raise(box) -> None:
    Path(at.FTMO_STATE).write_text("{torn", "utf-8")
    Path(at.SURVIVORS).unlink()
    doc = _run(box, NOW)
    assert doc["status"] == "OK" and box["started"] == []
    assert doc["sources"] == {"ftmo": False, "e8": False, "roster": False, "door": False}


def test_run_never_raises(box, monkeypatch) -> None:
    monkeypatch.setattr(at, "ftmo_snapshot", lambda *a: 1 / 0)
    assert at.run(now=NOW)["status"] == "ERROR"


def test_it_never_sizes_or_sends() -> None:
    src = (_DESK / "research" / "allocator_triggers.py").read_text("utf-8")
    for banned in ("order_send", "CERT_BOOK", "positions_get", "__main__"):
        assert banned not in src


def test_the_venue_reader_runs_it_every_pass() -> None:
    src = (_DESK / "prop" / "ftmo_venue_reader.py").read_text("utf-8")
    assert "allocator_triggers.run()" in src
