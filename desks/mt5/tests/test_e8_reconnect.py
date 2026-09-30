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
       "why": "VenueError: html", "first_at": "2026-09-28T07:00:05+00:00", "risk_usd": 1000.0}
IID = 316
SENT_MS = g._iso_ms(LEG["first_at"])


def _order(oid: int, side: str, level: float, **kw: Any) -> dict:
    """A venue order row carrying every field the matcher requires, landed just after the send."""
    return {"id": oid, "side": side, "stopPrice": level, "tradableInstrumentId": IID,
            "qty": 0.5, "createdDate": SENT_MS + 2_000, **kw}


MATCH = {"lot": 0.5, "instrument_id": IID, "since_ms": SENT_MS}


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
    book = [_order(11, "sell", 4300.0), _order(77, "sell", 4340.0), _order(78, "buy", 4340.02)]
    assert g.matching_resting_order(book, "buy_stop", 4340.0, {11}, **MATCH) == 78
    # An id the lane already owns is never claimed a second time.
    assert g.matching_resting_order(book, "buy_stop", 4340.0, {11, 78}, **MATCH) is None
    assert g.matching_resting_order(book, "buy_stop", 4341.0, {11}, **MATCH) is None


# The audit's probe (2026-09-30): a 40-hour-old 7-lot fill on another instrument at the leg's
# side and level was adopted as the leg, and management then cancelled the live twin.
@pytest.mark.parametrize(("change", "why"), [
    ({"tradableInstrumentId": 999}, "another instrument"),
    ({"tradableInstrumentId": None}, "no instrument on the row"),
    ({"qty": 7.0}, "another quantity"),
    ({"qty": None}, "no quantity on the row"),
    ({"createdDate": SENT_MS - 40 * 3_600_000}, "a fill from 40 hours before the send"),
    ({"createdDate": None}, "no creation time on the row"),
])
def test_an_order_that_is_not_this_leg_is_never_adopted(change, why) -> None:
    row = _order(78, "buy", 4340.0, **change)
    if change.get("createdDate", 0) is None:
        row.pop("createdDate")
    assert g.matching_resting_order([row], "buy_stop", 4340.0, set(), **MATCH) is None, why


def test_no_instrument_id_matches_nothing() -> None:
    kw = {**MATCH, "instrument_id": 0}
    row = _order(78, "buy", 4340.0, tradableInstrumentId=0)
    assert g.matching_resting_order([row], "buy_stop", 4340.0, set(), **kw) is None


def test_an_unreadable_send_time_adopts_nothing() -> None:
    kw = {**MATCH, "since_ms": g._iso_ms("not a time")}
    assert g.matching_resting_order([_order(78, "buy", 4340.0)], "buy_stop", 4340.0, set(),
                                    **kw) is None


# ----------------------------------------------------------------- the pass itself

class _Venue:
    def __init__(self, book: list[dict] | None = None, fail: bool = False,
                 min_lot: float = 0.01) -> None:
        self.book, self.fail, self.sent = list(book or []), fail, []
        self._min = min_lot

    def min_lot(self, _s: str) -> float:
        return self._min

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
            "xau_positions": [], "positions_ok": True, "stood_down": False, "armed": True,
            "hist_rows": [], "history_ok": True, "instrument_id": IID, **kw}
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
    v, st = _Venue(book=[_order(42, "buy", 4340.0)]), _state()
    _retry(v, st)
    assert v.sent == [] and st["windows"]["asia"]["orders"]["buy_stop"]["id"] == 42


def test_a_second_failure_counts_the_attempt_and_keeps_the_leg() -> None:
    v, st = _Venue(fail=True), _state()
    _retry(v, st)
    assert st["windows"]["asia"]["failed"]["buy_stop"]["attempts"] == 2


@pytest.mark.parametrize("kw", [{"stood_down": True}, {"orders_ok": False},
                                {"positions_ok": False}, {"armed": False},
                                {"history_ok": False}, {"instrument_id": 0}])
def test_nothing_is_re_sent_blind_and_the_skip_says_why(kw) -> None:
    v, st = _Venue(), _state()
    doc = _retry(v, st, **kw)
    assert v.sent == [] and "buy_stop" in st["windows"]["asia"]["failed"]
    assert doc["retry_skipped"]["legs"] == ["asia/buy_stop"] and doc["retry_skipped"]["why"]
    assert "not re-sent this pass" in g.LOG.read_text()


def test_an_abandoned_leg_leaves_the_retry_queue_with_its_reason() -> None:
    v, st = _Venue(), _state()
    _retry(v, st, hour=13.5)
    w = st["windows"]["asia"]
    assert v.sent == [] and "failed" not in w
    assert w["abandoned"]["buy_stop"]["why"] == "the window's session is over"


def test_a_send_that_landed_and_filled_is_adopted_from_history_not_doubled() -> None:
    v, st = _Venue(), _state()
    hist = [_order(55, "buy", 4340.0, status="Filled", positionId=9)]
    _retry(v, st, hist_rows=hist, filled={55: 9})
    assert v.sent == [] and st["windows"]["asia"]["orders"]["buy_stop"]["id"] == 55


def test_an_unowned_position_on_the_leg_side_since_the_failure_stops_the_resend() -> None:
    v, st = _Venue(), _state()
    pos = [{"id": 9, "side": "buy", "openDate": 4_102_444_800_000}]      # 2100: after first_at
    doc = _retry(v, st, xau_positions=pos)
    w = st["windows"]["asia"]
    assert v.sent == [] and "failed" not in w and "buy_stop" in w["abandoned"]
    assert doc["actions"][0]["act"] == "leg_abandon"
    # The veto's cost is on the record: the leg's whole certified risk goes undeployed.
    assert doc["actions"][0]["missed_growth_risk_usd"] == 1000.0
    assert "MISSED GROWTH" in g.LOG.read_text()


def test_yesterdays_own_leg_in_the_history_is_not_adopted_as_todays(monkeypatch) -> None:
    """The likely real trigger: after the rollover empties the windows, yesterday's own filled
    leg (same side, same level, same size) still sits in the two-day history."""
    v, st = _Venue(), _state()
    hist = [_order(55, "buy", 4340.0, status="Filled", positionId=9)]
    monkeypatch.setattr(g, "_journal_rows",
                        lambda: [{"status": "SENT", "order_id": 55, "window": "asia"}])
    _retry(v, st, hist_rows=hist, filled={55: 9})
    assert st["windows"]["asia"]["orders"]["buy_stop"]["id"] == 901 and len(v.sent) == 1


def test_a_position_that_predates_the_failure_or_is_ours_does_not_block() -> None:
    old = [{"id": 9, "side": "buy", "openDate": 1_000}]                  # 1970: before it
    assert g.position_since_failure(old, "buy_stop", LEG["first_at"], _state(), {}) is False
    ours = [{"id": 9, "side": "buy", "openDate": 4_102_444_800_000}]
    st = _state()
    assert g.position_since_failure(ours, "buy_stop", LEG["first_at"], st, {11: 9}) is False
    assert g.position_since_failure(ours, "sell_stop", LEG["first_at"], st, {}) is False


# ----------------------------------------------------------------- third audit (2026-09-30)
MIN = 60_000


def _journal(*rows: dict) -> None:
    import json
    g.INTENTS.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")


def test_the_venue_clock_is_measured_on_the_lanes_own_sends() -> None:
    journal = [{"status": "SENT", "order_id": 11, "at": "2026-09-28T06:00:00+00:00"},
               {"status": "SENT", "order_id": 12, "at": "2026-09-28T06:05:00+00:00"},
               {"status": "REJECTED", "at": "2026-09-28T06:06:00+00:00"}]
    rows = [{"id": 11, "createdDate": g._iso_ms("2026-09-28T05:45:00+00:00")},
            {"id": 12, "createdDate": g._iso_ms("2026-09-28T05:50:00+00:00")}]
    assert g.venue_clock_skew_ms(journal, rows) == -15 * MIN      # the box runs 15 min fast
    assert g.venue_clock_skew_ms(journal, []) is None


def test_a_box_running_fifteen_minutes_fast_still_finds_the_send_that_landed() -> None:
    """The audit's skew probe: the landed send is stamped 15 minutes before the box's clock said
    it was sent. Measured against the lane's own earlier send, it is adopted, never doubled."""
    _journal({"status": "SENT", "order_id": 11, "at": "2026-09-28T06:00:00+00:00"})
    own = _order(11, "sell", 4300.0, createdDate=g._iso_ms("2026-09-28T05:45:00+00:00"))
    landed = _order(78, "buy", 4340.0, createdDate=SENT_MS - 15 * MIN + 2_000)
    v, st = _Venue(book=[own, landed]), _state()
    _retry(v, st)
    assert v.sent == [] and st["windows"]["asia"]["orders"]["buy_stop"]["id"] == 78


def test_with_no_own_send_to_measure_the_bound_widens_but_still_refuses_old_fills() -> None:
    landed = _order(78, "buy", 4340.0, createdDate=SENT_MS - 15 * MIN)
    v, st = _Venue(book=[landed]), _state()
    _retry(v, st)
    assert v.sent == [] and st["windows"]["asia"]["orders"]["buy_stop"]["id"] == 78
    stale = _order(79, "buy", 4340.0, createdDate=SENT_MS - 40 * 60 * MIN)
    v, st = _Venue(book=[stale]), _state()
    _retry(v, st)
    assert len(v.sent) == 1 and st["windows"]["asia"]["orders"]["buy_stop"]["id"] == 901


def test_a_small_lot_is_matched_at_the_size_the_venue_actually_sent() -> None:
    """The adapter floors every lot at the venue minimum, so a 0.005 leg rests as 0.01."""
    v, st = _Venue(book=[_order(78, "buy", 4340.0, qty=0.01)], min_lot=0.01), _state()
    st["windows"]["asia"]["failed"]["buy_stop"]["lot"] = 0.005
    _retry(v, st)
    assert v.sent == [] and st["windows"]["asia"]["orders"]["buy_stop"]["id"] == 78


def test_the_unowned_position_block_is_billed_to_its_registered_rail() -> None:
    from libs.portfolio.rails import rail
    assert rail(g.UNOWNED_BLOCK_RAIL).kind == "integrity"
    v, st = _Venue(), _state()
    _retry(v, st, xau_positions=[{"id": 9, "side": "buy", "openDate": 4_102_444_800_000}])
    [row] = [r for r in g._journal_rows() if r.get("status") == "RAIL_BLOCKED"]
    assert row["rail"] == g.UNOWNED_BLOCK_RAIL and row["missed_growth_risk_usd"] == 1000.0
