"""E8 gold asks the ONE guard, and holds one gold trade at risk at a time (2026-10-20).

FIX 1. `e8_gold` read the raw `stood_down` flag from `e8_guard_state.json`. Only the executor's
`assess` call rolled that file to a new server day, so on 2026-10-15 a flag latched on 10-14 stood
the gold book down for the whole day ("guard stood down; managing open exposure only" on every
pass, 00:01Z..23:56Z, no placement). It also never saw CAPPED, BREACHED or PASSED.

FIX 3. Three windows at 0.75% can all be open in one direction (the agreeing leg is placed):
2.25% to the stops, ~2.8% with slippage, against a 2.5% daily floor. A window now waits while an
earlier XAU position is still at risk (stop short of break-even) or an earlier bracket rests,
and as a fail-safe the committed risk x SLIP_BUFFER must fit the guard's room to the floor.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent), str(_DESK / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from prop import e8_gold as g  # noqa: E402
from prop import e8_guard  # noqa: E402

_DAY = pd.Timestamp("2026-10-15", tz="UTC")
_NOW = _DAY + pd.Timedelta(hours=17, minutes=30)      # afternoon window due (signal hour 17)
_ENTRY, _STOP = 4300.0, 4315.0                          # a short, 15 points to its stop
_QTY = 0.5                                              # 15 x 0.5 x 100 oz = 750 USD = 0.75%


class _MT5:
    TIMEFRAME_H1 = 16385

    class _Tick:
        time = int(_NOW.timestamp())

    def symbol_info_tick(self, symbol: str) -> Any:
        return self._Tick()

    def copy_rates_from_pos(self, symbol: str, tf: int, start: int, count: int) -> list[dict]:
        idx = pd.date_range(end=_DAY + pd.Timedelta(hours=17), periods=120, freq="h")
        rows = []
        for t in idx:
            hi, lo = (4310.0, 4290.0) if t.date() == _DAY.date() else (4320.0, 4280.0)
            rows.append({"time": int(t.timestamp()), "open": 4300.0, "high": hi, "low": lo,
                         "close": 4300.0})
        return rows


class _Api:
    # The test venue's TLAPI identity (r7.2): the conftest declares this account in its tmp
    # E8_ACCOUNT.json, so an armed E8-Gold pass joins its declaration.
    account_id = 31337
    _credentials = {"server": "E8-Test"}  # noqa: RUF012
    @staticmethod
    def get_all_orders(history: bool = False, lookback_period: str = "") -> list:
        return []


class _Venue:
    _api = _Api()

    def __init__(self, positions: list[dict] | None = None, stops: dict[int, float] | None = None,
                 *, equity: float = 100_000.0, positions_raise: bool = False) -> None:
        self._positions = positions or []
        self._stops = stops or {}
        self._equity = equity
        self._raise = positions_raise

    def account(self) -> dict:
        return {"equity": self._equity}

    def quote(self, symbol: str) -> tuple[float, float]:
        return 4300.0, 4300.4

    def instrument_id(self, symbol: str) -> int:
        return 6102

    def positions(self) -> list[dict]:
        if self._raise:
            raise ConnectionError("positions endpoint returned HTML")
        return list(self._positions)

    def orders(self, symbol: str | None = None) -> list[dict]:
        return [{"id": oid, "stopPrice": px} for oid, px in self._stops.items()]

    def min_lot(self, symbol: str) -> float:
        return 0.01

    def details(self, symbol: str) -> dict:
        return {"contractSize": 100.0, "currency": "USD", "lotStep": 0.01}

    def cancel(self, order_id: int) -> bool:
        return True

    def modify_stop(self, position_id: int, stop: float) -> bool:
        return True

    def close(self, position_id: int, quantity: float = 0) -> bool:
        return True


def _short(pid: int, stop_id: int) -> dict:
    return {"id": pid, "tradableInstrumentId": 6102, "side": "sell", "qty": _QTY,
            "avgPrice": _ENTRY, "stopLossId": stop_id,
            "openDate": int((_DAY + pd.Timedelta(hours=8)).timestamp() * 1000)}


def _sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, placed: tuple[str, ...] = (),
             guard: dict | None = None) -> Path:
    for name in ("OUT", "INTENTS", "LOG", "KELLY_FILE", "CERT_BOOK_FILE"):
        monkeypatch.setattr(g, name, tmp_path / f"{name.lower()}.json")
    # These tests are about the guard and open-risk mechanics across all three windows, so the
    # principal's code pin of london_am/afternoon (decision_core.PRINCIPAL_ZERO["e8"], r6) is
    # lifted here; test_fusion_book_r6.py pins that the pin itself holds.
    from mt5desk import decision_core as _dc
    monkeypatch.setitem(_dc.PRINCIPAL_ZERO, "e8", frozenset())
    # Likewise the late-gold-send rule (decision_core.GOLD_SEND_GRACE_MIN, r6): the clock here is
    # 17:30 server, past the 5-minute grace; test_fusion_book_r6.py pins the rule itself.
    monkeypatch.setattr(_dc, "GOLD_SEND_GRACE_MIN", 24 * 60.0)
    monkeypatch.setattr(_dc, "E8_GOLD_SEND_GRACE_MIN", 24 * 60.0)
    # A VOID cert book sizes every E8 window at 0 since r7, so these mechanics run under an
    # enabled book that funds all three windows at RISK_FRAC (what a void book used to give).
    (tmp_path / "cert_book_file.json").write_text(json.dumps({"enabled": True, "e8": {
        "gold_asia": g.RISK_FRAC, "gold_london_am": g.RISK_FRAC,
        "gold_afternoon": g.RISK_FRAC}}), encoding="utf-8")
    gp = tmp_path / "e8_guard_state.json"
    if guard is not None:
        gp.write_text(json.dumps(guard), encoding="utf-8")
    monkeypatch.setattr(g, "GUARD", gp)
    windows = {n: {"placed_hour": 7.0, "orders": {}, "position_id": 100 + i, "shadow": False}
               for i, n in enumerate(placed)}
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"date": str(_DAY.date()), "carried": {}, "windows": windows}),
                     encoding="utf-8")
    monkeypatch.setattr(g, "STATE", state)
    return gp


def _placed(doc: dict) -> list[str]:
    return [p["window"] for p in doc["placed"]]


def _why(doc: dict, window: str) -> str:
    return " | ".join(str(s.get("why")) for s in doc["skipped"] if s.get("window") == window)


# ------------------------------------------------------------------------ FIX 1: the one guard

def test_a_stood_down_flag_from_a_previous_server_day_does_not_block_today(
        monkeypatch, tmp_path) -> None:
    gp = _sandbox(monkeypatch, tmp_path, guard={
        "day": "2026-10-14", "day_start": 98_000.0, "peak_equity": 100_000.0,
        "stood_down": True})
    doc = g.run(_Venue(), _MT5(), armed=False)
    assert "guard" not in doc, doc.get("guard")
    assert doc["guard_decision"]["verdict"] == "OK"
    assert _placed(doc) == ["afternoon"]
    rolled = json.loads(gp.read_text(encoding="utf-8"))
    assert rolled["day"] == e8_guard.server_day() and rolled["stood_down"] is False


def test_a_stood_down_flag_from_today_still_blocks(monkeypatch, tmp_path) -> None:
    _sandbox(monkeypatch, tmp_path, guard={
        "day": e8_guard.server_day(), "day_start": 100_000.0, "peak_equity": 100_000.0,
        "stood_down": True})
    doc = g.run(_Venue(), _MT5(), armed=False)
    assert doc["guard_decision"]["verdict"] == "STOOD_DOWN"
    assert doc["guard"].startswith("STOOD_DOWN")
    assert _placed(doc) == []


def test_a_capped_day_blocks_new_placements(monkeypatch, tmp_path) -> None:
    _sandbox(monkeypatch, tmp_path, guard={
        "day": e8_guard.server_day(), "day_start": 100_000.0, "peak_equity": 102_000.0,
        "stood_down": False})
    doc = g.run(_Venue(equity=102_050.0), _MT5(), armed=False)
    assert doc["guard_decision"]["verdict"] == "CAPPED"
    assert _placed(doc) == []


def test_an_unreadable_state_file_fails_safe_by_re_anchoring_on_current_equity(
        monkeypatch, tmp_path) -> None:
    gp = _sandbox(monkeypatch, tmp_path)
    gp.write_bytes(b"\xff\xfe{ not json")
    assert e8_guard.load_state(gp) == {}
    doc = g.run(_Venue(equity=99_000.0), _MT5(), armed=False)
    # load_state's semantics: nothing latched, the day re-anchored on the equity in hand.
    assert doc["guard_decision"]["day_start"] == pytest.approx(99_000.0)
    assert doc["guard_decision"]["verdict"] == "OK"


def test_an_equity_the_venue_cannot_state_is_never_anchored_on(monkeypatch, tmp_path) -> None:
    gp = _sandbox(monkeypatch, tmp_path)
    doc = g.run(_Venue(equity=0.0), _MT5(), armed=False)
    assert _placed(doc) == [] and "equity unreadable" in doc["guard"]
    assert not gp.exists(), "a zero equity must not be written as the day's start"


def test_a_guard_that_raises_refuses_placements(monkeypatch, tmp_path) -> None:
    _sandbox(monkeypatch, tmp_path)

    def boom(*a: Any, **k: Any) -> Any:
        raise OSError("disk gone")

    monkeypatch.setattr(e8_guard, "assess", boom)
    doc = g.run(_Venue(), _MT5(), armed=False)
    assert _placed(doc) == [] and "guard unreadable" in doc["guard"]


def test_the_guard_helpers_never_carry_yesterdays_latch() -> None:
    today = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
    stale = {"day": "2026-10-14", "day_start": 1.0, "peak_equity": 1.0, "stood_down": True}
    assert e8_guard.stood_down_today(stale, today) is False
    rolled = e8_guard.today_state(stale, 100_000.0, today)
    assert rolled == {"day": e8_guard.server_day(today), "day_start": 100_000.0,
                      "peak_equity": 100_000.0, "stood_down": False}
    same = {**stale, "day": e8_guard.server_day(today)}
    assert e8_guard.stood_down_today(same, today) is True
    assert e8_guard.today_state(same, 5.0, today) == same
    # assess, handed yesterday's latched state, opens today
    assert e8_guard.assess(100_000.0, now=today, state=stale, persist=False).may_open


def test_e8_gold_no_longer_reads_the_raw_flag() -> None:
    src = (_DESK / "prop" / "e8_gold.py").read_text(encoding="utf-8")
    assert "_read_json(GUARD" not in src
    assert "e8_guard.assess(equity, now=now, state_path=GUARD)" in src


# ------------------------------------------------------------- FIX 3: one gold trade at risk

def test_the_third_window_waits_while_the_first_two_are_open_at_full_risk(
        monkeypatch, tmp_path) -> None:
    _sandbox(monkeypatch, tmp_path, placed=("asia", "london_am"))
    venue = _Venue([_short(100, 9100), _short(101, 9101)], {9100: _STOP, 9101: _STOP})
    doc = g.run(venue, _MT5(), armed=False)
    assert _placed(doc) == []
    assert "one gold trade at risk at a time" in _why(doc, "afternoon")
    # v5.2: 750 to each stop plus 24.13 points of slip on each 0.5 lot (1,206.5 apiece).
    assert doc["committed_risk"]["total_usd"] == pytest.approx(1_500.0 + 2 * 1_206.5, abs=25)


def test_the_slip_buffered_floor_check_alone_refuses_the_third_window() -> None:
    # The fail-safe on its own: 1,500 committed + 750 new = 2,250 x 1.25 = 2,812 > 2,400.
    ok, why = g.risk_budget_allows(1_500.0, 750.0, 2_500.0)
    assert not ok and "x1.25" in why
    assert g.risk_budget_allows(750.0, 750.0, 2_500.0)[0]       # 1,875 <= 2,400


def test_a_break_even_ratcheted_position_frees_the_window(monkeypatch, tmp_path) -> None:
    _sandbox(monkeypatch, tmp_path, placed=("asia", "london_am"))
    # one stop ratcheted to the entry: not at risk, so the one-at-a-time rule frees the window;
    # its 24.13 points of slip on 0.5 lot (1,206.5) still count against the floor (v5.2).
    venue = _Venue([_short(100, 9100)], {9100: _ENTRY})
    doc = g.run(venue, _MT5(), armed=False)
    assert _placed(doc) == ["afternoon"], doc["skipped"]
    assert all(not r["at_risk"] for r in doc["committed_risk"]["positions"])
    assert doc["committed_risk"]["positions"][0]["slip_usd"] == pytest.approx(1_206.5)


def test_two_break_even_positions_still_carry_their_slip_and_defer(monkeypatch, tmp_path) -> None:
    """v5.2 (audit HOLD on 8fe4edce): neither is at risk, but 2 x 1,206.5 of stop slip is.
    (2,413 + 500) x 1.25 > 2,400, so the window waits under the concurrent budget."""
    _sandbox(monkeypatch, tmp_path, placed=("asia", "london_am"))
    venue = _Venue([_short(100, 9100), _short(101, 9101)], {9100: _ENTRY, 9101: _ENTRY - 1.0})
    doc = g.run(venue, _MT5(), armed=False)
    assert _placed(doc) == []
    assert "concurrent risk would reach today's floor" in _why(doc, "afternoon")


def test_one_position_still_at_risk_blocks_even_beside_a_break_even_one(
        monkeypatch, tmp_path) -> None:
    _sandbox(monkeypatch, tmp_path, placed=("asia", "london_am"))
    venue = _Venue([_short(100, 9100), _short(101, 9101)], {9100: _ENTRY, 9101: _STOP})
    doc = g.run(venue, _MT5(), armed=False)
    assert _placed(doc) == [] and "101" in _why(doc, "afternoon")


def test_a_resting_bracket_counts_every_leg_and_blocks() -> None:
    journal = [
        {"status": "SENT", "order_id": 1, "window": "asia", "side": "buy_stop",
         "at": "2026-10-15T04:00:00+00:00", "risk_usd": 750.0},
        {"status": "SENT", "order_id": 2, "window": "asia", "side": "sell_stop",
         "at": "2026-10-15T04:00:00+00:00", "risk_usd": 700.0},
    ]
    resting = [{"id": 1, "stopPrice": 4310.0}, {"id": 2, "stopPrice": 4290.0}]
    total, detail = g.committed_risk([], resting, journal, {"date": "2026-10-15"},
                                     bid=4300.0, ask=4300.4, contract_size=100.0)
    # v5.2: BOTH legs count -- until the cross-account OCO lands, both can fill.
    assert total == pytest.approx(750.0 + 700.0)
    assert detail["pending_brackets"] == {"2026-10-15/asia": 1450.0}
    assert "bracket(s) 2026-10-15/asia still rest" in str(g.one_at_risk_blocker(detail))
    # a leg that is no longer resting at the venue is not counted
    total, detail = g.committed_risk([], [], journal, {}, bid=4300.0, ask=4300.4,
                                     contract_size=100.0)
    assert total == 0.0 and g.one_at_risk_blocker(detail) is None


def test_unreadable_positions_refuse_every_window(monkeypatch, tmp_path) -> None:
    _sandbox(monkeypatch, tmp_path)
    doc = g.run(_Venue(positions_raise=True), _MT5(), armed=False)
    assert _placed(doc) == [] and "positions_unreadable" in doc


def test_unreadable_orders_refuse_every_window(monkeypatch, tmp_path) -> None:
    _sandbox(monkeypatch, tmp_path)
    venue = _Venue()

    def broken(symbol: str | None = None) -> list[dict]:
        raise ConnectionError("orders endpoint 502")

    venue.orders = broken  # type: ignore[method-assign]
    doc = g.run(venue, _MT5(), armed=False)
    assert _placed(doc) == []
    assert "concurrent open risk unmeasurable" in _why(doc, "afternoon")


def test_a_position_whose_stop_cannot_be_read_is_unbounded_and_refuses(
        monkeypatch, tmp_path) -> None:
    _sandbox(monkeypatch, tmp_path, placed=("asia",))
    doc = g.run(_Venue([_short(100, 9100)], {}), _MT5(), armed=False)
    assert _placed(doc) == []
    assert "concurrent open risk unmeasurable" in _why(doc, "afternoon")


def test_a_winning_break_even_leg_still_counts_its_floating_profit_in_the_fail_safe() -> None:
    # stop at entry (not at risk), but the mark has run 20 points in its favour: the floor is
    # measured on equity, which includes that profit, so the fail-safe counts it.
    p = _short(1, 9)
    assert not g.stop_is_at_risk(p, _ENTRY)
    usd = g.position_risk_usd(p, _ENTRY, bid=4279.6, ask=4280.0, contract_size=100.0)
    assert usd == pytest.approx(20.0 * _QTY * 100.0)


# --------------------------------------------- FIX 4: a stop move the venue keeps refusing

def _refusing_harness(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bid: float, ask: float
                      ) -> tuple[Any, Any, Path]:
    import test_stop_rests_at_venue as harness

    class _Refusing(harness._GoldVenue):
        def modify_stop(self, position_id: int, stop: float) -> bool:
            self.modified.append((int(position_id), float(stop)))
            return False                                   # TradeLocker says no, every time

    monkeypatch.setattr(harness, "_GoldVenue", _Refusing)
    doc, venue = harness._seed(monkeypatch, tmp_path, bid, ask)
    return harness, venue, tmp_path / "state.json"


def test_a_refused_stop_move_is_retried_only_a_bounded_number_of_times_then_held(
        monkeypatch, tmp_path) -> None:
    # 4248.00/4248.40: the ratchet rests and is wanted, but the short is only ~0.77R in profit,
    # short of the break-even trigger -- so after the bound the resting stop is HELD.
    harness, venue, state = _refusing_harness(monkeypatch, tmp_path, 4248.00, 4248.40)
    for _ in range(g.MAX_STOP_REFUSALS - 1):
        g.run(venue, harness._MT5(), armed=True)
    assert len(venue.modified) == g.MAX_STOP_REFUSALS
    saved = json.loads(state.read_text(encoding="utf-8"))
    assert saved["windows"]["asia"]["stop_refusals"]["count"] == g.MAX_STOP_REFUSALS
    doc = g.run(venue, harness._MT5(), armed=True)
    assert len(venue.modified) == g.MAX_STOP_REFUSALS, "no stop move is sent past the bound"
    held = [a for a in doc["actions"] if a["act"] == "stop_refused_hold"]
    assert held and "held" in held[0]["why"] and doc.get("alerts")
    assert venue.closed == []
    doc = g.run(venue, harness._MT5(), armed=True)
    assert not [a for a in doc["actions"] if a["act"] == "stop_refused_hold"], "alerted once"
    assert len(venue.modified) == g.MAX_STOP_REFUSALS


def test_a_refused_stop_on_a_trade_beyond_the_trigger_is_closed_at_market(
        monkeypatch, tmp_path) -> None:
    harness, venue, state = _refusing_harness(monkeypatch, tmp_path, 4248.00, 4248.40)
    for _ in range(g.MAX_STOP_REFUSALS - 1):
        g.run(venue, harness._MT5(), armed=True)
    venue._bid, venue._ask = 4236.00, 4236.40          # ~1.16R in the short's favour
    doc = g.run(venue, harness._MT5(), armed=True)
    closes = [a for a in doc["actions"] if a["act"] == "stop_refused_close"]
    assert closes and closes[0]["ok"] and venue.closed == [harness._POSITION_ID]
    assert "closed at market" in closes[0]["why"]


def test_a_successful_stop_move_clears_the_refusal_count(monkeypatch, tmp_path) -> None:
    harness, venue, state = _refusing_harness(monkeypatch, tmp_path, 4248.00, 4248.40)
    assert json.loads(state.read_text("utf-8"))["windows"]["asia"]["stop_refusals"]["count"] == 1
    type(venue).modify_stop = lambda self, pid, stop: True  # type: ignore[method-assign]
    g.run(venue, harness._MT5(), armed=True)
    assert "stop_refusals" not in json.loads(state.read_text("utf-8"))["windows"]["asia"]


def test_the_refusal_response_is_close_beyond_the_trigger_else_hold() -> None:
    w = {"orders": {"sell_stop": {"price": 4272.36, "sl": 4303.25}}}
    p = {"side": "sell", "avgPrice": 4272.36}
    assert g.stop_refusal_response(p, w, bid=4235.6, ask=4236.0)[0] == "close"
    assert g.stop_refusal_response(p, w, bid=4250.0, ask=4250.4)[0] == "hold"
    assert g.stop_refusal_response(p, {"orders": {}}, bid=4200.0, ask=4200.4)[0] == "hold"
