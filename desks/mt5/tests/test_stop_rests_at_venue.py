"""A stop the market has already passed is not a stop, and one venue will execute it.

THE EVENT THIS PINS, RECONSTRUCTED FROM THE ACCOUNT RATHER THAN DESCRIBED (2026-09-24, E8
position 360287970193246861). The gold asia sell stop filled at 4272.36 against a 4303.25 stop
attached by the venue at entry -- a real resting order, which is how the desk's own log was able
to read it back as `current_stop`. Four and three-quarter hours later the first stop ratchet this
account has ever sent arrived: the extreme low of 4244.21 was three H1 bars old, `is_stalled`
collapsed k from 4 to 1, and the chandelier came out at 4244.21 + 1 x 15.57 = 4259.78.

Every test upstream of the send passed, correctly. 4259.78 protects more than 4303.25 for a
short; `stop_protected_r` rose from -1.000R to +0.407R; the never-widen guard was satisfied. What
none of them asked is where the market was, and the market was at 4283.5 -- 23.8 points the wrong
side of the level. The venue accepted the modification, the protective buy stop was through its
trigger the moment it landed, and it filled at market: 4283.91, for -0.391R. The venue's own
order history is unambiguous about which of the two stories is true: order 360287970211082260,
type `stop`, price 4259.78, status Filled, avgPrice 4283.91.

THE SAME MISTAKE IS FREE ON THE OTHER ACCOUNT, which is exactly why it survived long enough to
be made here. MetaTrader answers retcode 10016 and changes nothing; this desk's gateway log holds
92 such refusals against 15 accepted modifies, every one of them harmless. TradeLocker has no
such backstop, so a defect that had been a noisy log line on Fusion became 386.08 USD on E8 the
first time the lane could move a stop at all.

So the predicate is measured on the arithmetic, and the two lanes that send are pinned against
fakes: no credentials, no network, no funded account.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk import position_manager as pm  # noqa: E402
from prop import e8_executor, e8_gold  # noqa: E402

#: The measured trade, to the tick. Entry and stop are the venue's own numbers; the quote is the
#: one reconstructed from the account's equity at 13:03:08 and the fill the history reports.
EVENT = {"entry": 4272.36, "original_stop": 4303.25, "ratchet_to": 4259.78,
         "bid": 4283.50, "ask": 4283.91, "extreme": 4244.21, "atr": 15.57456}


# ---------------------------------------------------------------- the predicate

def test_a_shorts_stop_must_sit_above_the_ask_and_a_longs_below_the_bid() -> None:
    ok, why = pm.stop_rests_at_venue(stop=4300.0, side=-1, bid=4283.50, ask=4283.91)
    assert ok and "rests above the ask" in why
    ok, why = pm.stop_rests_at_venue(stop=4270.0, side=1, bid=4283.50, ask=4283.91)
    assert ok and "rests below the bid" in why


def test_the_measured_ratchet_level_is_refused_at_the_measured_quote() -> None:
    """The whole event in one assertion: 4259.78, for a short, at 4283.50/4283.91."""
    ok, why = pm.stop_rests_at_venue(stop=EVENT["ratchet_to"], side=-1,
                                     bid=EVENT["bid"], ask=EVENT["ask"])
    assert not ok
    assert "market exit" in why and "NOT sent" in why


def test_a_level_on_the_market_itself_is_refused_because_equality_is_not_protection() -> None:
    assert not pm.stop_rests_at_venue(stop=4283.91, side=-1, bid=4283.50, ask=4283.91)[0]
    assert not pm.stop_rests_at_venue(stop=4283.50, side=1, bid=4283.50, ask=4283.91)[0]


def test_the_venue_minimum_distance_is_honoured_on_both_sides() -> None:
    assert pm.stop_rests_at_venue(stop=4284.50, side=-1, bid=4283.50, ask=4283.91)[0]
    assert not pm.stop_rests_at_venue(stop=4284.50, side=-1, bid=4283.50, ask=4283.91,
                                      min_distance=2.0)[0]
    assert pm.stop_rests_at_venue(stop=4282.50, side=1, bid=4283.50, ask=4283.91)[0]
    assert not pm.stop_rests_at_venue(stop=4282.50, side=1, bid=4283.50, ask=4283.91,
                                      min_distance=2.0)[0]


def test_an_unreadable_quote_refuses_rather_than_guesses() -> None:
    """The account keeps a stop that is known good; a send made blind costs the giveback."""
    for bad in ({"bid": 0.0, "ask": 4283.91}, {"bid": 4283.50, "ask": 0.0},
                {"bid": 4284.00, "ask": 4283.00}):
        ok, why = pm.stop_rests_at_venue(stop=4300.0, side=-1, **bad)  # type: ignore[arg-type]
        assert not ok and "degenerate quote" in why


def test_a_bad_side_or_a_negative_distance_raises_rather_than_defaulting() -> None:
    with pytest.raises(ValueError):
        pm.stop_rests_at_venue(stop=4300.0, side=0, bid=1.0, ask=1.1)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        pm.stop_rests_at_venue(stop=4300.0, side=-1, bid=1.0, ask=1.1, min_distance=-1.0)


def test_the_ratchet_itself_still_approves_the_level_that_the_market_has_passed() -> None:
    """The guard is NEEDED, not redundant: `ratchet` has no quote and cannot see the defect."""
    decision = pm.ratchet(entry=EVENT["entry"], current_stop=EVENT["original_stop"],
                          stop_distance=abs(EVENT["entry"] - EVENT["original_stop"]),
                          extreme=EVENT["extreme"], atr=EVENT["atr"], side=-1,
                          bars_since_extreme=pm.STALL_BARS)
    assert decision.moves
    assert decision.new_stop == pytest.approx(EVENT["ratchet_to"], abs=0.01)
    assert decision.protected_r_after > decision.protected_r_before   # it "improves"
    assert not pm.stop_rests_at_venue(stop=float(decision.new_stop), side=-1,
                                      bid=EVENT["bid"], ask=EVENT["ask"])[0]


# ---------------------------------------------------------------- the E8 gold exit path

_POSITION_ID = 360287970193246861
_STOP_ORDER_ID = 9001
_OPENED = pd.Timestamp("2026-09-24 08:00", tz="UTC")
_NOW = pd.Timestamp("2026-09-24 16:00", tz="UTC")


class _Api:
    @staticmethod
    def get_all_orders(history: bool = False, lookback_period: str = "") -> list:
        return []


class _GoldVenue:
    """Only what `e8_gold.run` calls, recording every write instead of making one."""

    _api = _Api()

    def __init__(self, bid: float, ask: float) -> None:
        self._bid, self._ask = bid, ask
        self.modified: list[tuple[int, float]] = []
        self.closed: list[int] = []

    def account(self) -> dict:
        return {"equity": 100_000.0}

    def quote(self, symbol: str) -> tuple[float, float]:
        return self._bid, self._ask

    def instrument_id(self, symbol: str) -> int:
        return 6102

    def positions(self) -> list[dict]:
        return [{"id": _POSITION_ID, "tradableInstrumentId": 6102, "side": "sell", "qty": 0.16,
                 "avgPrice": EVENT["entry"], "stopLossId": _STOP_ORDER_ID,
                 "openDate": int(_OPENED.timestamp() * 1000)}]

    def orders(self, symbol: str | None = None) -> list[dict]:
        return [{"id": _STOP_ORDER_ID, "stopPrice": EVENT["original_stop"]}]

    def min_lot(self, symbol: str) -> float:
        return 0.01

    def details(self, symbol: str) -> dict:
        return {"contractSize": 100.0, "currency": "USD", "lotStep": 0.01}

    def modify_stop(self, position_id: int, stop: float) -> bool:
        self.modified.append((int(position_id), float(stop)))
        return True

    def close(self, position_id: int, quantity: float = 0) -> bool:
        self.closed.append(int(position_id))
        return True

    def cancel(self, order_id: int) -> bool:
        return True


class _MT5:
    """The tape of the day: a short that ran 28 points, then gave it all back and more."""

    TIMEFRAME_H1 = 16385

    class _Tick:
        time = int(_NOW.timestamp())

    def symbol_info_tick(self, symbol: str) -> _Tick:
        return self._Tick()

    def copy_rates_from_pos(self, symbol: str, tf: int, start: int, count: int) -> list[dict]:
        idx = pd.date_range(end=_NOW, periods=120, freq="h")
        rows = []
        for t in idx:
            if t < _OPENED:                       # quiet pre-entry tape, ATR ~15
                hi, lo, cl = 4290.0, 4275.0, 4282.0
            elif t <= _OPENED + pd.Timedelta(hours=5):
                hi, lo, cl = 4275.0, EVENT["extreme"], 4250.0     # the run down
            else:
                hi, lo, cl = 4285.0, 4270.0, EVENT["bid"]         # the rally back through
            rows.append({"time": int(t.timestamp()), "open": cl, "high": hi, "low": lo,
                         "close": cl})
        return rows


def _seed(monkeypatch, tmp_path, bid: float, ask: float) -> tuple[dict, _GoldVenue]:
    """A state file that already holds the open asia position, so the pass only manages."""
    for name in ("OUT", "INTENTS", "GUARD", "LOG"):
        monkeypatch.setattr(e8_gold, name, tmp_path / f"{name.lower()}.json")
    state = tmp_path / "state.json"
    window = {"placed_at": str(_OPENED), "placed_hour": 7.0, "hi": 4303.25, "lo": 4273.7,
              "orders": {"sell_stop": {"id": 1, "price": 4273.7,
                                       "sl": EVENT["original_stop"], "tp": 4214.6, "lot": 0.16}},
              "position_id": _POSITION_ID, "shadow": False}
    blank = {"orders": {}, "position_id": None, "shadow": False, "placed_hour": 7.0}
    state.write_text(json.dumps({"date": str(_NOW.date()), "carried": {},
                                 "windows": {"asia": window, "london_am": dict(blank),
                                             "afternoon": dict(blank)}}), encoding="utf-8")
    monkeypatch.setattr(e8_gold, "STATE", state)
    venue = _GoldVenue(bid, ask)
    return e8_gold.run(venue, _MT5(), armed=True), venue


def test_e8_gold_refuses_to_send_a_ratchet_the_market_has_already_passed(
        monkeypatch, tmp_path) -> None:
    doc, venue = _seed(monkeypatch, tmp_path, EVENT["bid"], EVENT["ask"])
    refusals = [a for a in doc["actions"] if a["act"] == "ratchet_refused"]
    assert refusals, f"expected a refusal, got {doc['actions']}"
    assert refusals[0]["position_id"] == _POSITION_ID
    assert "market exit" in refusals[0]["why"]
    assert venue.modified == [], "a level behind the market must never reach the venue"
    assert venue.closed == [], "the refusal manages a stop; it never closes a position"


def test_e8_gold_still_sends_a_ratchet_that_genuinely_rests(monkeypatch, tmp_path) -> None:
    """The guard refuses a market exit, not a ratchet: with price still below, it goes."""
    doc, venue = _seed(monkeypatch, tmp_path, 4248.00, 4248.40)
    sent = [a for a in doc["actions"] if a["act"] == "ratchet_stop" and a.get("ok")]
    assert sent, f"expected the ratchet to be sent, got {doc['actions']}"
    assert venue.modified and venue.modified[0][0] == _POSITION_ID
    assert venue.modified[0][1] > 4248.40, "the level sent must rest above the ask"
    assert venue.modified[0][1] < EVENT["original_stop"], "and must protect more than before"


# ---------------------------------------------------------------- the break-even floor

class _FloorVenue:
    def __init__(self, bid: float, ask: float) -> None:
        self._bid, self._ask = bid, ask
        self._by_key = {"XAUUSD": 6102}
        self.modified: list[tuple[int, float]] = []

    def positions(self) -> list[dict[str, Any]]:
        return [{"id": _POSITION_ID, "tradableInstrumentId": 6102, "side": "sell", "qty": 0.16,
                 "avgPrice": EVENT["entry"], "stopLoss": EVENT["original_stop"]}]

    def quote(self, symbol: str) -> tuple[float, float]:
        return self._bid, self._ask

    def modify_stop(self, position_id: int, stop: float) -> bool:
        self.modified.append((int(position_id), float(stop)))
        return True


def _floor(monkeypatch, tmp_path, bid: float, ask: float) -> tuple[list[dict], _FloorVenue]:
    basis = tmp_path / "basis.json"
    basis.write_text(json.dumps({str(_POSITION_ID): {
        "stop_distance": abs(EVENT["entry"] - EVENT["original_stop"]),
        "extreme": EVENT["extreme"]}}), encoding="utf-8")
    monkeypatch.setattr(e8_executor, "STOP_BASIS", basis)
    venue = _FloorVenue(bid, ask)
    return e8_executor.manage_breakeven(venue, armed=True), venue


def test_the_breakeven_floor_is_held_when_price_is_already_past_the_entry(
        monkeypatch, tmp_path) -> None:
    """The floor level comes off the ENTRY, so a retrace through it puts it behind the market."""
    rows, venue = _floor(monkeypatch, tmp_path, EVENT["bid"], EVENT["ask"])
    row = next(r for r in rows if r["id"] == str(_POSITION_ID))
    assert row["action"] == "HOLD"
    assert row["stop_wanted"] == pytest.approx(EVENT["entry"])
    assert "market exit" in row["why"]
    assert venue.modified == []


def test_the_breakeven_floor_is_still_sent_while_it_rests(monkeypatch, tmp_path) -> None:
    rows, venue = _floor(monkeypatch, tmp_path, 4248.00, 4248.40)
    row = next(r for r in rows if r["id"] == str(_POSITION_ID))
    assert row["action"] == "MODIFY" and row["ok"]
    assert venue.modified == [(_POSITION_ID, pytest.approx(EVENT["entry"]))]
