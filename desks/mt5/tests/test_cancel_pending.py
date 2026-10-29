"""The desk's own lever to withdraw resting orders (mt5desk/cancel_pending.py), and the three
executors that honour it."""

from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK))
from mt5desk import cancel_pending as cp  # noqa: E402

NOW = datetime(2026, 10, 28, 7, 30, tzinfo=UTC)


def _req(tmp: Path, *rows: dict) -> Path:
    f = tmp / "CANCEL_PENDING.json"
    f.write_text(json.dumps({"requests": list(rows)}))
    return f


def _r(**kw: object) -> dict:
    base = {
        "id": "r1",
        "lane": "ftmo",
        "tickets": [111616773],
        "expires_at": (NOW + timedelta(hours=4)).isoformat(),
        "why": "stale leg",
    }
    base.update(kw)
    return {k: v for k, v in base.items() if v is not None}


def test_only_own_tickets_are_cancelled_and_a_done_one_is_not_resent(tmp_path: Path) -> None:
    f = _req(tmp_path, _r(tickets=[111616773, 5]))
    todo, notes = cp.due("ftmo", [111616773, 9], now=NOW, path=f, ack_dir=tmp_path / "a")
    assert [c["ticket"] for c in todo] == [111616773]
    assert notes == ["request r1: ticket 5 is not a resting order of this lane"]
    cp.record("ftmo", "r1", 111616773, True, ack_dir=tmp_path / "a", now=NOW)
    assert cp.due("ftmo", [111616773], now=NOW, path=f, ack_dir=tmp_path / "a")[0] == []
    # another lane never sees it
    assert cp.due("e8", [111616773], now=NOW, path=f, ack_dir=tmp_path / "a")[0] == []


def test_a_failed_cancel_is_retried(tmp_path: Path) -> None:
    f = _req(tmp_path, _r())
    cp.record("ftmo", "r1", 111616773, False, ack_dir=tmp_path / "a", now=NOW)
    assert cp.due("ftmo", [111616773], now=NOW, path=f, ack_dir=tmp_path / "a")[0]


def _at(minutes: int) -> datetime:
    return NOW + timedelta(minutes=minutes)


def test_all_is_bounded_by_setup_time_never_a_standing_veto(tmp_path: Path) -> None:
    """v7 audit MF6: the bound is the request's own placed_before, not a snapshot an ack holds."""
    f = _req(tmp_path, _r(tickets=None, all=True, placed_before=_at(-5).isoformat()))
    own = {1: _at(-60), 2: _at(-6), 3: _at(-1), 4: None}
    todo, notes = cp.due("ftmo", own, now=NOW, path=f, ack_dir=tmp_path / "a")
    assert sorted(c["ticket"] for c in todo) == [1, 2]  # 3 placed after, 4 unknown: left alone
    assert any("order 4 has no readable setup time" in n for n in notes)


def test_all_is_also_bounded_by_when_the_lane_first_saw_it(tmp_path: Path) -> None:
    f = _req(tmp_path, _r(tickets=None, all=True, placed_before=_at(60).isoformat()))
    cp.due("ftmo", {1: _at(-1)}, now=NOW, path=f, ack_dir=tmp_path / "a")
    later = cp.due("ftmo", {1: _at(-1), 2: _at(10)}, now=_at(20), path=f, ack_dir=tmp_path / "a")
    assert [c["ticket"] for c in later[0]] == [1]


@pytest.mark.parametrize("lost", ["garbled", "deleted"])
def test_a_lost_or_garbled_ack_never_widens_all(tmp_path: Path, lost: str) -> None:
    """v7 audit A2/A3: an order placed after the request is never cancelled, whatever the acks."""
    acks = tmp_path / "a"
    f = _req(tmp_path, _r(tickets=None, all=True, placed_before=_at(0).isoformat()))
    cp.due("ftmo", {1: _at(-1)}, now=NOW, path=f, ack_dir=acks)
    if lost == "garbled":
        (acks / "ftmo.json").write_text("{half")
    else:
        (acks / "ftmo.json").unlink()
    todo, notes = cp.due("ftmo", {1: _at(-1), 2: _at(5)}, now=_at(10), path=f, ack_dir=acks)
    if lost == "garbled":
        assert todo == [] and "person" in notes[0]
        cp.record("ftmo", "r1", 1, True, ack_dir=acks, now=NOW)  # never overwrites the evidence
        assert (acks / "ftmo.json").read_text() == "{half"
    else:
        assert [c["ticket"] for c in todo] == [1]


def test_mt5_setup_time_is_read_on_the_server_clock() -> None:
    utc = datetime(2026, 10, 28, 4, 0, tzinfo=UTC)  # US summer time: server = UTC + 3
    assert cp.server_time_utc(utc.timestamp() + 3 * 3600) == utc
    winter = datetime(2026, 12, 1, 4, 0, tzinfo=UTC)  # server = UTC + 2
    assert cp.server_time_utc(winter.timestamp() + 2 * 3600) == winter
    assert cp.server_time_utc(0) is None and cp.server_time_utc(True) is None


def test_expired_or_too_long_requests_are_ignored(tmp_path: Path) -> None:
    for exp in (NOW - timedelta(minutes=1), NOW + timedelta(hours=49)):
        f = _req(tmp_path, _r(expires_at=exp.isoformat()))
        assert cp.due("ftmo", [111616773], now=NOW, path=f, ack_dir=tmp_path / "a")[0] == []


def test_an_unreadable_file_cancels_nothing_and_never_raises(tmp_path: Path) -> None:
    f = tmp_path / "CANCEL_PENDING.json"
    f.write_text("{not json")
    todo, notes = cp.due("ftmo", [1], now=NOW, path=f, ack_dir=tmp_path / "a")
    assert todo == [] and "unreadable" in notes[0]
    assert cp.due("ftmo", [1], now=NOW, path=tmp_path / "absent.json") == ([], [])


@pytest.mark.parametrize(
    ("row", "why"),
    [
        (_r(lane="cme"), "lane"),
        (_r(tickets=[]), "non-empty"),
        (_r(tickets=[True]), "positive integers"),
        (_r(all=True), "exactly one"),
        (_r(tickets=None, all=False), "all must be true"),
        (_r(tickets=None, all=True), "placed_before"),
        (_r(placed_before=NOW.isoformat()), "only with all"),
        (_r(expires_at="soon"), "ISO"),
        (_r(expires_at=(NOW + timedelta(hours=60)).isoformat()), "expires more than"),
        ({**_r(), "close": True}, "unknown keys"),
    ],
)
def test_the_check_refuses_what_an_executor_would_misread(row: dict, why: str) -> None:
    assert why in (cp.problem({"requests": [row]}, now=NOW) or "")
    assert cp.problem({"requests": [_r()]}, now=NOW) is None


@pytest.mark.parametrize(
    ("path", "lane", "cancel"),
    [
        ("prop/ftmo_follower.py", "LANE", "mt5.TRADE_ACTION_REMOVE"),
        ("prop/e8_gold.py", '"e8"', 'venue.cancel(int(c["ticket"]))'),
        ("mt5desk/gateway.py", '"fusion"', "mt5.TRADE_ACTION_REMOVE"),
    ],
)
def test_every_executor_cancels_only_its_own_and_only_when_armed(
    path: str, lane: str, cancel: str
) -> None:
    src = (DESK / path).read_text(encoding="utf-8")
    found = re.search(r"_cancel_req\.due\(\s*" + re.escape(lane), src)
    assert found is not None
    block = src[found.start() : found.start() + 2800]
    assert cancel in block and "_cancel_req.record(" in block
    # Rule 1: every order the lane withdraws is billed, at its own risk (v7 audit MF2)
    assert "_cancel_req.RAIL" in block and "missed_growth_risk_usd" in block
    near = src[found.start() - 900 : found.start() + 300]
    assert "server_time_utc" in near or "fromtimestamp(ms / 1000, UTC)" in near  # setup times
    assert "armed" in block and "shadow" in block.lower()
    assert (
        "TRADE_ACTION_DEAL" not in block
        and 'order_send({"action": mt5.TRADE_ACTION_PENDING' not in block
    )


def test_the_request_files_are_box_local() -> None:
    gi = (DESK.parents[1] / ".gitignore").read_text()
    assert (
        "desks/mt5/data/CANCEL_PENDING.json" in gi and "desks/mt5/data/cancel_pending_acks/" in gi
    )


@pytest.mark.parametrize(
    ("path", "call"),
    [
        ("prop/ftmo_follower.py", "_cancel_req.withdraw_check(LANE, armed)"),
        ("prop/e8_gold.py", '_cancel_req.withdraw_reason("e8", armed)'),
        ("mt5desk/gateway.py", "_cancel_req.withdraw_check(lane, armed or defaulted)"),
    ],
)
def test_every_executor_withdraws_when_its_lane_is_removed_or_paused(path: str, call: str) -> None:
    """2026-10-28, FTMO ticket 111616773: removing a lane left its resting entry to fill. Every
    executor applies the rule itself, so it holds whatever removed or paused the lane."""
    src = (DESK / path).read_text(encoding="utf-8")
    assert call in src and "_cancel_req.WITHDRAWN" in src


def test_withdraw_reason_follows_the_mode_file_and_the_arm(monkeypatch, tmp_path: Path) -> None:
    from mt5desk import gold_oco

    mode = tmp_path / "GOLD_OCO_MODE.json"
    monkeypatch.setattr(gold_oco, "MODE_FILE", mode)
    mode.write_text(json.dumps({"lanes": ["e8", "fusion", "ftmo"]}))
    assert cp.withdraw_reason("ftmo", True) is None
    assert "paused" in (cp.withdraw_reason("ftmo", False) or "")
    mode.write_text(json.dumps({"lanes": ["e8", "fusion"], "modes": {"fusion": "fallback"}}))
    assert "not declared" in (cp.withdraw_reason("ftmo", True) or "")
    assert cp.withdraw_reason("fusion", True) is None and cp.withdraw_reason("e8", True) is None
    # present but unreadable or malformed: UNMEASURED, nothing withdrawn (v14 audit MF1)
    for bad in ("{torn", '{"lanes": "e8,fusion,ftmo"}', '{"modes": {}}', "[1]"):
        mode.write_text(bad)
        why, unmeasured = cp.withdraw_check("ftmo", True)
        assert why is None and "UNMEASURED" in (unmeasured or ""), bad
        assert cp.withdraw_reason("ftmo", False) is not None  # a pause still withdraws
    mode.unlink()  # absent: documented as the default lanes, which leave ftmo out
    assert cp.withdraw_reason("ftmo", True) is not None
    assert cp.withdraw_reason("fusion", True) is None
