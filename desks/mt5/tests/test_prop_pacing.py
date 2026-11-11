"""THE FTMO CHALLENGE PACING LEDGER (research/prop_pacing.py, idea 625): measured, never sizing."""
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

import prop_pacing as pp  # noqa: E402

NOW = datetime(2026, 11, 11, 10, 0, tzinfo=UTC)            # Wednesday, 11:00 CET
KEY = "sha256:0123456789abcdef"                            # fake


def _state(**kw: Any) -> dict[str, Any]:
    doc = {"status": "OK", "generated_at": (NOW - timedelta(minutes=2)).isoformat(),
           "account_key": KEY, "phase": "phase1", "initial_balance": 100_000.0,
           "balance": 103_000.0, "equity": 102_500.0, "day_start_balance": 103_400.0,
           "days_traded": 2, "phase_started_at": "2026-11-09T08:00:00+00:00"}   # Monday
    doc.update(kw)
    return doc


def _alloc(days_median: float = 8.0, phase: str = "phase1", **kw: Any) -> dict[str, Any]:
    doc = {"generated_at": (NOW - timedelta(minutes=30)).isoformat(),
           "account": {"phase": phase},
           "phases": {phase: {"status": "OK", "total_risk": 0.02, "validation": {
               "as_estimated": {"days_median": days_median, "days_p90": 20.0, "p_pass": 0.81,
                                "p_fail": 0.04},
               "edges_halved": {"days_median": 14.0, "p_pass": 0.66}}}}}
    doc.update(kw)
    return doc


@pytest.fixture
def files(monkeypatch, tmp_path) -> Path:
    for name in ("OUT", "PUBLIC_OUT", "LEDGER", "ACCOUNT_STATE", "ALLOCATOR"):
        monkeypatch.setattr(pp, name, tmp_path / f"{name.lower()}.json")
    return tmp_path


def _write(path: Path, doc: dict) -> None:
    path.write_text(json.dumps(doc), "utf-8")


def _ledger() -> list[dict]:
    p = Path(pp.LEDGER)
    return [json.loads(x) for x in p.read_text("utf-8").splitlines()] if p.exists() else []


def test_progress_days_and_room_are_measured_off_the_account() -> None:
    doc = pp.build(_state(), _alloc(), [], now=NOW)
    assert doc["status"] == "OK"
    assert doc["progress"]["target_usd"] == 10_000.0 and doc["progress"]["gained_usd"] == 3000.0
    assert doc["progress"]["share"] == 0.3 and doc["progress"]["left_usd"] == 7000.0
    assert doc["days"] == {"traded": 2, "min_days": 4, "min_days_left": 2,
                           "phase_started_at": "2026-11-09T08:00:00+00:00",
                           "weekdays_elapsed": 3}
    # Daily: 5,000 limit, 900 used (103,400 -> 102,500 equity); floor 90,000.
    assert doc["room"]["daily_used_usd"] == 900.0 and doc["room"]["daily_room_usd"] == 4100.0
    assert doc["room"]["max_room_usd"] == 12_500.0
    assert doc["room"]["max_room_in_daily_limits"] == 2.5
    assert doc["plan"]["days_median"] == 8.0 and doc["plan"]["halved_p_pass"] == 0.66


def test_pace_against_the_plan_now() -> None:
    # 3,000 over 3 weekdays = 1,000/day realised; 7,000 left over 8 plan days = 875/day needed.
    doc = pp.build(_state(), _alloc(8.0), [], now=NOW)
    assert doc["pace"]["realised_usd_per_day"] == 1000.0
    assert doc["pace"]["needed_usd_per_day_on_plan"] == 875.0
    assert doc["pace"]["vs_plan_now"] == "AHEAD" and doc["pace"]["verdict"] == "AHEAD"
    doc = pp.build(_state(), _alloc(5.0), [], now=NOW)                 # 1,400/day needed
    assert doc["pace"]["verdict"] == "BEHIND"
    doc = pp.build(_state(), _alloc(7.0), [], now=NOW)                 # 1,000/day needed
    assert doc["pace"]["verdict"] == "ON_PACE"


def test_pace_against_the_plan_the_phase_started_on_wins() -> None:
    first = {"kind": "phase_start", "cet_date": "2026-11-09", "account_key": KEY,
             "phase": "phase1", "plan": {"days_median": 10.0}, "weekdays_elapsed": 1}
    doc = pp.build(_state(), _alloc(8.0), [first], now=NOW)
    # Straight line to day 10: 3 of 10 days -> 3,000 expected, 3,000 gained.
    assert doc["pace"]["expected_gain_by_now_usd"] == 3000.0
    assert doc["pace"]["vs_plan_at_start"] == "ON_PACE" and doc["pace"]["verdict"] == "ON_PACE"
    doc = pp.build(_state(balance=101_000.0), _alloc(8.0), [first], now=NOW)
    assert doc["pace"]["verdict"] == "BEHIND"


@pytest.mark.parametrize(("state", "alloc", "why"), [
    (None, _alloc(), "no FTMO account state"),
    (_state(generated_at=(NOW - timedelta(hours=1)).isoformat()), _alloc(), "min old"),
    (_state(status="UNMEASURED", phase_why="first-seen account"), _alloc(), "first-seen"),
])
def test_an_unmeasured_account_is_said_so(state, alloc, why) -> None:
    doc = pp.build(state, alloc, [], now=NOW)
    assert doc["status"] == "UNMEASURED" and why in doc["why"]
    assert (doc.get("pace") or {}).get("verdict", "UNMEASURED") == "UNMEASURED"


@pytest.mark.parametrize(("alloc", "why"), [
    (None, "absent"),
    (_alloc(generated_at=(NOW - timedelta(hours=4)).isoformat()), "old"),
    (_alloc(phase="phase2"), "solved phase"),
])
def test_a_stale_or_other_phase_plan_is_not_used(alloc, why) -> None:
    doc = pp.build(_state(), alloc, [], now=NOW)
    assert why in doc["plan"]["why"]
    assert doc["pace"]["needed_usd_per_day_on_plan"] is None
    assert doc["pace"]["vs_plan_now"] == "UNMEASURED"
    assert doc["progress"]["gained_usd"] == 3000.0                  # the account still reads


def test_at_target_before_the_minimum_days() -> None:
    doc = pp.build(_state(balance=110_500.0, equity=110_500.0), _alloc(), [], now=NOW)
    assert doc["target_reached_min_days_left"] is True
    assert doc["progress"]["left_usd"] == 0.0 and doc["pace"]["vs_plan_now"] == "AHEAD"


def test_funded_has_room_and_no_target() -> None:
    doc = pp.build(_state(phase="funded"), _alloc(phase="funded"), [], now=NOW)
    assert doc["progress"]["target"] is None and doc["room"]["daily_room_usd"] == 4100.0
    assert doc["pace"]["verdict"] == "UNMEASURED"


def test_the_ledger_records_the_phase_start_and_one_close_per_day(files) -> None:
    _write(pp.ACCOUNT_STATE, _state())
    _write(pp.ALLOCATOR, _alloc())
    doc = pp.run(now=NOW)
    assert doc["status"] == "OK" and [r["kind"] for r in _ledger()] == ["phase_start"]
    # A worse moment later the same day: the day's worst room is kept.
    _write(pp.ACCOUNT_STATE, _state(equity=101_000.0,
                                    generated_at=(NOW + timedelta(hours=2)).isoformat()))
    pp.run(now=NOW + timedelta(hours=2, minutes=1))
    _write(pp.ACCOUNT_STATE, _state(generated_at=(NOW + timedelta(hours=3)).isoformat()))
    doc = pp.run(now=NOW + timedelta(hours=3, minutes=1))
    assert doc["worst_daily_room_usd"] == 2600.0                     # 5,000 - 2,400
    assert [r["kind"] for r in _ledger()] == ["phase_start"]         # the day is still open
    # The next CE(S)T day: yesterday's close is written once.
    nxt = NOW + timedelta(days=1)
    _write(pp.ACCOUNT_STATE, _state(generated_at=(nxt - timedelta(minutes=1)).isoformat()))
    _write(pp.ALLOCATOR, _alloc(generated_at=(nxt - timedelta(minutes=10)).isoformat()))
    doc = pp.run(now=nxt)
    pp.run(now=nxt + timedelta(minutes=5))
    rows = _ledger()
    assert [r["kind"] for r in rows] == ["phase_start", "day_close"]
    assert rows[1]["cet_date"] == "2026-11-11" and rows[1]["worst_daily_room_usd"] == 2600.0
    assert doc["closed_day"] == "2026-11-11"


def test_run_never_raises(files, monkeypatch) -> None:
    monkeypatch.setattr(pp, "build", lambda *a, **k: 1 / 0)
    assert pp.run(now=NOW)["status"] == "ERROR"


def test_it_never_writes_the_cert_book_or_any_sizing_file() -> None:
    src = (_DESK / "research" / "prop_pacing.py").read_text("utf-8")
    assert "CERT_BOOK" not in src and "order_send" not in src


def test_the_venue_reader_runs_it_every_pass() -> None:
    src = (_DESK / "prop" / "ftmo_venue_reader.py").read_text("utf-8")
    assert "prop_pacing.run()" in src


def _numbers(obj: Any) -> list[float]:
    if isinstance(obj, dict):
        return [x for v in obj.values() for x in _numbers(v)]
    if isinstance(obj, list):
        return [x for v in obj for x in _numbers(v)]
    return [float(obj)] if isinstance(obj, (int, float)) and not isinstance(obj, bool) else []


def test_the_public_summary_carries_verdicts_and_shares_never_dollars(files) -> None:
    pos = [{"symbol": "XAUUSD", "side": "long", "volume": 1.0, "profit": -500.0}]
    _write(pp.ACCOUNT_STATE, _state(open_positions=pos))
    _write(pp.ALLOCATOR, _alloc())
    pp.run(now=NOW)
    text = Path(pp.PUBLIC_OUT).read_text("utf-8")
    pub = json.loads(text)
    assert pub["status"] == "OK" and pub["open_positions"] == 1
    assert pub["pace"]["verdict"] == "AHEAD" and pub["progress_share"] == 0.3
    assert pub["daily_room_share"] == 0.82 and pub["max_room_in_daily_limits"] == 2.5
    assert pub["worst_daily_room_share"] == 0.82 and pub["days"]["min_days_left"] == 2
    for banned in ("usd", "balance", "equity\"", "account_key", KEY, "sha256", "profit", "XAUUSD"):
        assert banned not in text, banned
    # No figure in it is an account-sized amount.
    assert max(abs(x) for x in _numbers(pub)) < 1000


def test_an_unmeasured_account_publishes_unmeasured(files) -> None:
    pp.run(now=NOW)
    pub = json.loads(Path(pp.PUBLIC_OUT).read_text("utf-8"))
    assert pub["status"] == "UNMEASURED" and pub["pace"]["verdict"] is None
    assert pub["open_positions"] is None


def test_the_public_summary_rides_the_state_wire() -> None:
    root = _DESK.parent.parent
    rel = "desks/mt5/reports/FTMO_PACING_PUBLIC.json"
    assert rel in (root / "desks/mt5/scripts/sync_shadow_to_git.ps1").read_text("utf-8")
    assert f"!{rel}" in (root / ".gitignore").read_text("utf-8")
