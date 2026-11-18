"""ops/daily_fills.py: one verdict per account per market day, alarms only after the close.

Every case builds its own box tree under tmp_path; nothing reads the repository's ledgers.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from ops import daily_fills as df

D = "desks/mt5/data"
# Wednesday 2026-11-18; the close is 20:30 UTC.
MID = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)
AFTER = datetime(2026, 11, 18, 21, 0, tzinfo=UTC)


def _jsonl(root: Path, rel: str, rows: list[dict[str, Any]]) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _json(root: Path, rel: str, doc: dict[str, Any]) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), encoding="utf-8")


def _all_sources_quiet(root: Path, *, positions_at: str = "2026-11-18T20:50:00+00:00") -> None:
    """Every needed source readable and empty of entries: the ZERO_FILLS baseline."""
    for rel in ("live_ledger.jsonl", "order_intents.jsonl", "decision_ledger.jsonl",
                "e8_gold_intents.jsonl", "ftmo_follower_intents.jsonl",
                "ftmo_exec_intents.jsonl"):
        _jsonl(root, f"{D}/{rel}", [])
    _json(root, f"{D}/account_positions.json", {"updated_at": positions_at, "positions": []})
    _json(root, f"{D}/e8_gold_state.json", {"date": "2026-11-18", "windows": {}})


def test_quiet_day_before_close_does_not_alarm(tmp_path: Path) -> None:
    _all_sources_quiet(tmp_path, positions_at="2026-11-18T11:50:00+00:00")
    doc = df.build(MID, root=tmp_path, previous={})
    assert doc["today"]["final"] is False
    assert {a["verdict"] for a in doc["today"]["accounts"].values()} == {"ZERO_FILLS"}
    # The judged day is the previous market day (Tuesday), which this tree says nothing about
    # being filled; what matters here is that TODAY raises nothing before its close.
    assert doc["judged"]["date"] == "2026-11-17"
    assert all(a["date"] == "2026-11-17" for a in doc["alarms"])


def test_quiet_day_after_close_alarms_every_account(tmp_path: Path) -> None:
    _all_sources_quiet(tmp_path)
    doc = df.build(AFTER, root=tmp_path, previous={})
    assert doc["judged"]["date"] == "2026-11-18" and doc["judged"]["final"] is True
    keys = {a["key"]: a for a in doc["alarms"]}
    assert set(keys) == {"daily_fills:fusion", "daily_fills:e8", "daily_fills:ftmo"}
    for a in keys.values():
        assert a["kind"] == "zero_fills" and a["verdict"] == "ZERO_FILLS"
        assert a["task"] and a["last_error"]
    assert doc["status"] == "ALARM"


def test_fusion_closed_and_open_entries_count(tmp_path: Path) -> None:
    _all_sources_quiet(tmp_path)
    _jsonl(tmp_path, f"{D}/live_ledger.jsonl", [
        {"entry_time": "2026-11-18T04:30:00+00:00", "position_id": 11, "sleeve": "gold_asia"},
        {"entry_time": "2026-11-17T04:30:00+00:00", "position_id": 10, "sleeve": "gold_asia"}])
    _json(tmp_path, f"{D}/account_positions.json", {
        "updated_at": "2026-11-18T20:50:00+00:00",
        "positions": [{"ticket": 12, "opened_at": "2026-11-18T14:05:00+00:00"},
                      {"ticket": 11, "opened_at": "2026-11-18T04:30:00+00:00"}]})
    acc = df.build(AFTER, root=tmp_path, previous={})["judged"]["accounts"]["fusion"]
    assert acc["verdict"] == "FILLED"
    assert acc["fills"] == 2                       # ticket 11 is one fill seen twice
    assert acc["last_fill_at"] == "2026-11-18T14:05:00+00:00"


def test_skip_reasons_are_codes_newest_first(tmp_path: Path) -> None:
    _all_sources_quiet(tmp_path)
    _jsonl(tmp_path, f"{D}/order_intents.jsonl", [
        {"status": "SKIPPED", "reason": "late_send", "why": "price 1234.5",
         "time": "2026-11-18T10:06:00+00:00"},
        {"ticket": 5, "retcode": 10009, "time": "2026-11-18T10:07:00+00:00"}])
    _jsonl(tmp_path, f"{D}/decision_ledger.jsonl", [
        {"outcome": "VENUE_UNAVAILABLE", "reason": "release_identity_refused",
         "decided_at": "2026-11-18T14:00:00+00:00"},
        {"outcome": "VENUE_UNAVAILABLE", "reason": "release_identity_refused",
         "decided_at": "2026-11-18T07:00:00+00:00"},
        {"outcome": "EXECUTED", "reason": "placed", "decided_at": "2026-11-18T04:00:00+00:00"}])
    acc = df.build(AFTER, root=tmp_path, previous={})["judged"]["accounts"]["fusion"]
    assert acc["verdict"] == "ZERO_FILLS"          # a placed stop is not an entry
    codes = [(r["source"], r["code"], r["n"]) for r in acc["skip_reasons"]]
    assert codes == [("decision_ledger", "release_identity_refused", 2),
                     ("order_intents", "late_send", 1)]
    assert "1234.5" not in json.dumps(acc)          # no why-text is published


def test_unreadable_source_is_unmeasured_never_zero(tmp_path: Path) -> None:
    _all_sources_quiet(tmp_path)
    (tmp_path / D / "e8_gold_state.json").unlink()
    doc = df.build(AFTER, root=tmp_path, previous={})
    e8 = doc["judged"]["accounts"]["e8"]
    assert e8["verdict"] == "UNMEASURED" and e8["unreadable"] == ["e8_gold_state"]
    alarm = next(a for a in doc["alarms"] if a["key"] == "daily_fills:e8")
    assert alarm["kind"] == "fills_unmeasured"


def test_stale_positions_snapshot_is_unmeasured(tmp_path: Path) -> None:
    _all_sources_quiet(tmp_path, positions_at="2026-11-18T09:00:00+00:00")
    acc = df.build(datetime(2026, 11, 18, 15, 0, tzinfo=UTC), root=tmp_path,
                   previous={})["today"]["accounts"]["fusion"]
    assert acc["verdict"] == "UNMEASURED"


def test_e8_fill_is_the_state_position_and_survives_the_rollover(tmp_path: Path) -> None:
    _all_sources_quiet(tmp_path)
    _json(tmp_path, f"{D}/e8_gold_state.json", {"date": "2026-11-18", "windows": {
        "asia": {"orders": {}, "position_id": 777},
        "london_am": {"orders": {}, "position_id": None},
        "carried:asia": {"position_id": 555}}})
    first = df.build(MID, root=tmp_path, previous={})
    assert first["today"]["accounts"]["e8"]["fills"] == 1
    # The server day rolls over before the UTC close is judged: the state forgets the window.
    _json(tmp_path, f"{D}/e8_gold_state.json", {"date": "2026-11-19", "windows": {}})
    later = df.build(AFTER, root=tmp_path, previous=first)
    e8 = later["judged"]["accounts"]["e8"]
    assert e8["verdict"] == "FILLED" and e8["fills"] == 1
    assert "777" not in json.dumps(later)           # the venue's position number is hashed


def test_e8_fx_market_send_is_a_fill(tmp_path: Path) -> None:
    _all_sources_quiet(tmp_path)
    _jsonl(tmp_path, f"{D}/e8_intents.jsonl", [
        {"at": "2026-11-18T09:00:00+00:00", "status": "NO_SIGNAL"},
        {"at": "2026-11-18T09:05:00+00:00", "status": "SPREAD_TOO_WIDE"},
        {"at": "2026-11-18T09:10:00+00:00", "status": "SENT", "order_id": 9,
         "acked_at": "2026-11-18T09:10:01+00:00"}])
    e8 = df.build(AFTER, root=tmp_path, previous={})["judged"]["accounts"]["e8"]
    assert e8["verdict"] == "FILLED" and e8["last_fill_at"] == "2026-11-18T09:10:01+00:00"
    assert [r["code"] for r in e8["skip_reasons"]] == ["SPREAD_TOO_WIDE"]


def test_ftmo_pending_send_is_not_a_fill_market_send_is(tmp_path: Path) -> None:
    _all_sources_quiet(tmp_path)
    _jsonl(tmp_path, f"{D}/ftmo_follower_intents.jsonl", [
        {"at": "2026-11-18T05:00:00+00:00", "status": "SENT", "kind": "buy_stop",
         "order_id": 1}])
    assert df.build(AFTER, root=tmp_path, previous={})[
        "judged"]["accounts"]["ftmo"]["verdict"] == "ZERO_FILLS"
    _jsonl(tmp_path, f"{D}/ftmo_exec_intents.jsonl", [
        {"at": "2026-11-18T06:00:00+00:00", "status": "SENT", "order_id": 2},
        {"at": "2026-11-18T06:05:00+00:00", "status": "RAIL_BLOCKED",
         "rail": "ftmo_loss_guard"}])
    ftmo = df.build(AFTER, root=tmp_path, previous={})["judged"]["accounts"]["ftmo"]
    assert ftmo["verdict"] == "FILLED" and ftmo["fills"] == 1
    assert ftmo["skip_reasons"][0]["code"] == "ftmo_loss_guard"


def test_ftmo_closed_prop_ledger_counts(tmp_path: Path) -> None:
    _all_sources_quiet(tmp_path)
    _jsonl(tmp_path, f"{D}/live_ledger_prop.jsonl", [
        {"book": "ftmo", "entry_time": "2026-11-18T04:10:00+00:00", "entry_order": 3}])
    ftmo = df.build(AFTER, root=tmp_path, previous={})["judged"]["accounts"]["ftmo"]
    assert ftmo["verdict"] == "FILLED"


@pytest.mark.parametrize("now, judged", [
    (datetime(2026, 11, 21, 12, 0, tzinfo=UTC), "2026-11-20"),   # Saturday -> Friday
    (datetime(2026, 11, 23, 9, 0, tzinfo=UTC), "2026-11-20"),    # Monday morning -> Friday
    (datetime(2026, 11, 23, 20, 30, tzinfo=UTC), "2026-11-23"),  # Monday at the close
])
def test_the_alarm_stands_until_the_next_market_day_is_judged(
        tmp_path: Path, now: datetime, judged: str) -> None:
    assert df.last_closed_market_day(now).isoformat() == judged


def test_weekend_today_never_alarms_itself(tmp_path: Path) -> None:
    _all_sources_quiet(tmp_path)
    sat = datetime(2026, 11, 21, 22, 0, tzinfo=UTC)
    doc = df.build(sat, root=tmp_path, previous={})
    assert doc["today"]["market_day"] is False
    assert all(a["date"] == "2026-11-20" for a in doc["alarms"])


def test_report_is_written_and_self_describing(tmp_path: Path) -> None:
    _all_sources_quiet(tmp_path)
    out = df.write(df.build(AFTER, root=tmp_path, previous={}), root=tmp_path)
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert out.relative_to(tmp_path).as_posix() == "desks/mt5/reports/DAILY_FILLS.json"
    for a in doc["alarms"]:
        assert {"key", "kind", "task", "verdict", "last_error"} <= set(a)


def test_the_check_makes_no_venue_call() -> None:
    src = Path(df.__file__).read_text(encoding="utf-8")
    for banned in ("MetaTrader5", "mt5.", "order_send", "tradelocker", "TradeLocker(",
                   "requests", "subprocess"):
        assert banned not in src, banned
