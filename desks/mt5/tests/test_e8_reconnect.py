"""E8 gold survives a dead terminal pipe and a dropped venue leg (2026-09-30).

~70 minutes of MT5 "No IPC connection" in one day, and TradeLocker answering a send with an HTML
page on 09-17, 09-22 and 09-28 -- each of those days traded half a bracket, because the rejected
leg was written off with its window marked placed.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK.parent.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk.decision_core import CANCEL_HOUR  # noqa: E402
from prop import e8_gold as g  # noqa: E402

LEG = {"price": 4340.0, "sl": 4320.0, "tp": 4380.0, "lot": 0.5, "attempts": 1,
       "why": "VenueError: html", "first_at": "2026-09-28T07:00:05+00:00"}


def _state(**window: Any) -> dict:
    w = {"placed_hour": 7.0, "orders": {"sell_stop": {"id": 11, "price": 4300.0}},
         "position_id": None, "failed": {"buy_stop": dict(LEG)}, **window}
    return {"date": "2026-09-28", "windows": {"asia": w}, "carried": {}}


# ----------------------------------------------------------------- the terminal

class _Terminal:
    def __init__(self, ok_on: int) -> None:
        self.ok_on, self.attaches, self.shutdowns = ok_on, 0, 0

    def attach(self, api: Any, **kw: Any) -> bool:
        self.attaches += 1
        return self.attaches >= self.ok_on

    def symbol_info_tick(self, _sym: str) -> Any:
        return SimpleNamespace(time=0) if self.attaches >= self.ok_on else None

    def last_error(self) -> tuple[int, str]:
        return (-10004, "No IPC connection")

    def shutdown(self) -> None:
        self.shutdowns += 1


def test_a_dropped_pipe_is_reinitialised_until_the_terminal_answers() -> None:
    t, waited = _Terminal(ok_on=3), []
    ok, tries = g.connect_terminal(t, t.attach, "t.exe", sleep=waited.append)
    assert (ok, tries) == (True, 3)
    # The stale handle is shut down before each fresh attempt, with a growing wait.
    assert t.shutdowns == 2
    assert waited == list(g.MT5_RETRY_WAITS_S[1:3])


def test_a_handshake_without_a_tick_is_not_a_connection() -> None:
    t = _Terminal(ok_on=99)
    t.attach = lambda api, **kw: True  # type: ignore[method-assign]
    ok, tries = g.connect_terminal(t, t.attach, "t.exe", sleep=lambda _s: None)
    assert (ok, tries) == (False, len(g.MT5_RETRY_WAITS_S))


def test_an_attach_that_raises_is_retried_not_fatal() -> None:
    t, n = _Terminal(ok_on=1), {"i": 0}

    def attach(api: Any, **kw: Any) -> bool:
        n["i"] += 1
        if n["i"] == 1:
            raise OSError("pipe broken")
        return t.attach(api, **kw)

    assert g.connect_terminal(t, attach, "t.exe", sleep=lambda _s: None)[0] is True


def test_no_bars_mid_pass_reconnects_and_runs_again(tmp_path, monkeypatch) -> None:
    from mt5desk import config

    from research import mt5_session

    fake = SimpleNamespace(last_error=lambda: (0, ""), shutdown=lambda: None,
                           symbol_info_tick=lambda _s: SimpleNamespace(time=0))
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    monkeypatch.setattr(config, "terminal_path", lambda: "t.exe")
    monkeypatch.setattr(mt5_session, "attach_or_initialize", lambda api, **kw: True)
    import prop.tradelocker_venue as tv
    monkeypatch.setattr(tv, "load_credentials", lambda: None)
    monkeypatch.setattr(tv.TradeLockerVenue, "connect", lambda self: self)
    runs = iter([{"status": "NO_BARS"}, {"status": "OK", "hour": 7.1}])
    seen: list[dict] = []
    monkeypatch.setattr(g, "run", lambda v, m, armed=False: seen.append(next(runs)) or seen[-1])
    monkeypatch.setattr(g, "LOG", tmp_path / "log")
    monkeypatch.setattr(g, "ARMED_MARKER", tmp_path / "unarmed")
    monkeypatch.setattr(g.time, "sleep", lambda _s: None)
    assert g.main([]) == 0
    assert [d["status"] for d in seen] == ["NO_BARS", "OK"]


# ----------------------------------------------------------------- the dropped leg

def test_a_dropped_leg_is_retried_while_its_window_is_open() -> None:
    [d] = g.retry_decisions(_state(), 8.0, bid=4320.0, ask=4320.3, filled={})
    assert (d["window"], d["side"], d["act"]) == ("asia", "buy_stop", "retry")


@pytest.mark.parametrize(("hour", "state_kw", "filled", "bid", "why"), [
    (8.0, {"position_id": 555}, {}, 4320.0, "the other leg filled"),
    (8.0, {}, {11: 555}, 4320.0, "the other leg filled"),
    (13.0, {}, {}, 4320.0, "the window's session is over"),
    (CANCEL_HOUR, {}, {}, 4320.0, "the window's session is over"),
    (8.0, {}, {}, 4345.0, "price already through"),
])
def test_a_dropped_leg_is_abandoned_once_the_certified_trade_is_gone(hour, state_kw, filled,
                                                                      bid, why) -> None:
    [d] = g.retry_decisions(_state(**state_kw), hour, bid=bid, ask=bid + 0.3, filled=filled)
    assert d["act"] == "abandon" and d["why"].startswith(why)


def test_retries_are_bounded() -> None:
    st = _state()
    st["windows"]["asia"]["failed"]["buy_stop"]["attempts"] = g.MAX_LEG_RETRIES
    [d] = g.retry_decisions(st, 8.0, bid=4320.0, ask=4320.3, filled={})
    assert d["act"] == "abandon"


def test_a_leg_against_an_open_position_is_held_not_abandoned() -> None:
    [d] = g.retry_decisions(_state(), 8.0, bid=4320.0, ask=4320.3, filled={},
                            blocked="buy_stop")
    assert d["act"] == "hold"


def test_a_send_that_landed_is_adopted_not_doubled() -> None:
    book = [{"id": 11, "side": "sell", "stopPrice": 4300.0},
            {"id": 77, "side": "sell", "stopPrice": 4340.0},
            {"id": 78, "side": "buy", "stopPrice": 4340.02}]
    assert g.matching_resting_order(book, "buy_stop", 4340.0, known_ids={11}) == 78
    # An id the lane already owns is never claimed a second time.
    assert g.matching_resting_order(book, "buy_stop", 4340.0, known_ids={11, 78}) is None
    assert g.matching_resting_order(book, "buy_stop", 4341.0, known_ids={11}) is None


# ----------------------------------------------------------------- the pass itself

class _Venue:
    def __init__(self, book: list[dict] | None = None, fail: bool = False) -> None:
        self.book, self.fail, self.sent = list(book or []), fail, []

    def quote(self, _s: str) -> tuple[float, float]:
        return 4320.0, 4320.3

    def place_stop(self, sym: str, side: str, lot: float, **kw: Any) -> int:
        self.sent.append((side, lot, kw))
        if self.fail:
            raise RuntimeError("<html>502</html>")
        return 901


def _retry(venue: _Venue, st: dict, *, hour: float = 8.0, **kw: Any) -> dict:
    from datetime import UTC, datetime
    doc: dict = {"actions": []}
    args = {"open_orders": list(venue.book), "orders_ok": True, "filled": {},
            "xau_positions": [], "positions_ok": True, "stood_down": False, **kw}
    g._retry_failed_legs(venue, st, doc, hour=hour, now=datetime.now(UTC), **args)
    return doc


@pytest.fixture(autouse=True)
def _no_journal(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(g, "INTENTS", tmp_path / "intents.jsonl")
    monkeypatch.setattr(g, "LOG", tmp_path / "log")


def test_the_pass_re_sends_the_leg_and_moves_it_into_the_bracket() -> None:
    v, st = _Venue(), _state()
    doc = _retry(v, st)
    w = st["windows"]["asia"]
    assert v.sent == [("buy", 0.5, {"price": 4340.0, "stop": 4320.0, "take_profit": 4380.0})]
    assert w["orders"]["buy_stop"]["id"] == 901 and "failed" not in w
    assert doc["actions"][0]["act"] == "leg_retry" and doc["actions"][0]["ok"] is True


def test_the_pass_adopts_a_landed_send_without_sending_again() -> None:
    v, st = _Venue(book=[{"id": 42, "side": "buy", "stopPrice": 4340.0}]), _state()
    _retry(v, st)
    assert v.sent == [] and st["windows"]["asia"]["orders"]["buy_stop"]["id"] == 42


def test_a_second_failure_counts_the_attempt_and_keeps_the_leg() -> None:
    v, st = _Venue(fail=True), _state()
    _retry(v, st)
    assert st["windows"]["asia"]["failed"]["buy_stop"]["attempts"] == 2


@pytest.mark.parametrize("kw", [{"stood_down": True}, {"orders_ok": False},
                                {"positions_ok": False}])
def test_nothing_is_re_sent_blind(kw) -> None:
    v, st = _Venue(), _state()
    _retry(v, st, **kw)
    assert v.sent == [] and "buy_stop" in st["windows"]["asia"]["failed"]


def test_an_abandoned_leg_leaves_the_retry_queue_with_its_reason() -> None:
    v, st = _Venue(), _state()
    _retry(v, st, hour=13.5)
    w = st["windows"]["asia"]
    assert v.sent == [] and "failed" not in w
    assert w["abandoned"]["buy_stop"]["why"] == "the window's session is over"
