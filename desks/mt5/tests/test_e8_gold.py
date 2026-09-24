"""The gold windows on the prop account (2026-09-16): the pure decisions, without a venue."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK.parent.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk.decision_core import BRACKET_TTL_HOURS, CANCEL_HOUR, CLOSE_HOUR  # noqa: E402
from prop import e8_gold as g  # noqa: E402


def _bars(hours: int = 120) -> pd.DataFrame:
    """Hourly bars ending at 12:00 server on the last day, a 4300-4340 range that morning."""
    end = pd.Timestamp("2026-09-16 12:00", tz="UTC")
    idx = pd.date_range(end=end, periods=hours, freq="h")
    rng = np.random.default_rng(1)
    close = 4320.0 + np.cumsum(rng.normal(0, 3.0, hours))
    df = pd.DataFrame({"open": close, "high": close + 6.0, "low": close - 6.0, "close": close},
                      index=idx)
    day = df.index.date == end.date()
    df.loc[day, "high"] = np.minimum(df.loc[day, "high"], 4340.0)
    df.loc[day, "low"] = np.maximum(df.loc[day, "low"], 4300.0)
    return df


def test_a_window_is_planned_once_at_or_after_its_signal_hour_before_the_cancel_hour() -> None:
    df = _bars()
    # 07:30 server: the Asia window (signal hour 7, range 00-07) is due; london_am (13) is not.
    due = g.plan(df, 7.5, {"windows": {}})
    assert [d["window"] for d in due] == ["asia"]
    spec = due[0]["spec"]
    assert spec["buy_stop"]["price"] == due[0]["hi"] and spec["sell_stop"]["price"] == due[0]["lo"]
    assert spec["buy_stop"]["sl"] < spec["buy_stop"]["price"] < spec["buy_stop"]["tp"]
    assert spec["sell_stop"]["tp"] < spec["sell_stop"]["price"] < spec["sell_stop"]["sl"]
    # Already placed today: not again.
    assert g.plan(df, 7.5, {"windows": {"asia": {}}}) == []
    # Past the cancel hour: nothing is placed.
    assert g.plan(df, CANCEL_HOUR + 0.1, {"windows": {}}) == []
    # Before the signal hour: nothing.
    assert g.plan(df, 6.9, {"windows": {}}) == []


def test_a_resting_leg_must_sit_on_the_right_side_of_the_quote() -> None:
    assert g.leg_is_legal("buy_stop", 4341.0, 4338.0, 4338.5)[0]
    assert not g.leg_is_legal("buy_stop", 4338.5, 4338.0, 4338.5)[0]
    assert g.leg_is_legal("sell_stop", 4300.0, 4338.0, 4338.5)[0]
    assert not g.leg_is_legal("sell_stop", 4338.0, 4338.0, 4338.5)[0]


def _state(placed_hour: float = 7.1, position_id: int | None = None) -> dict:
    return {"date": "2026-09-16", "windows": {"asia": {
        "placed_hour": placed_hour, "position_id": position_id,
        "orders": {"buy_stop": {"id": 11, "price": 4340.0},
                   "sell_stop": {"id": 12, "price": 4300.0}}}}}


def test_one_fill_cancels_the_other_leg_and_the_position_is_recorded() -> None:
    acts = g.manage_actions(_state(), 8.0, open_ids={12}, filled={11: 900}, position_ids={900})
    assert [a["act"] for a in acts] == ["record_position", "oco_cancel"]
    assert acts[0]["position_id"] == 900 and acts[1]["order_id"] == 12


def test_an_unfilled_pair_is_cancelled_after_the_ttl_and_at_the_end_of_day() -> None:
    both = {11, 12}
    assert g.manage_actions(_state(7.1), 7.1 + BRACKET_TTL_HOURS - 0.1, both, {}, set()) == []
    acts = g.manage_actions(_state(7.1), 7.1 + BRACKET_TTL_HOURS, both, {}, set())
    assert sorted(a["order_id"] for a in acts) == [11, 12]
    assert {a["act"] for a in acts} == {"ttl_cancel"}
    acts = g.manage_actions(_state(CANCEL_HOUR - 1.0), CANCEL_HOUR, both, {}, set())
    assert {a["act"] for a in acts} == {"eod_cancel"}


def test_the_position_is_closed_at_the_close_hour_and_only_while_it_exists() -> None:
    acts = g.manage_actions(_state(7.1, position_id=900), CLOSE_HOUR, set(), {}, {900})
    assert [a["act"] for a in acts] == ["close"] and acts[0]["position_id"] == 900
    # Already gone at the venue (stop or target hit): nothing to close.
    assert g.manage_actions(_state(7.1, position_id=900), CLOSE_HOUR, set(), {}, set()) == []
    # Before the close hour a live position is left to its stop and target.
    assert g.manage_actions(_state(7.1, position_id=900), CLOSE_HOUR - 0.5, set(), {}, {900}) == []


def test_only_this_instrument_s_open_positions_block_another_gold_window() -> None:
    rows = [{"id": 1, "tradableInstrumentId": 6102, "side": "buy"},
            {"id": 2, "tradableInstrumentId": 99, "side": "sell"}]
    assert g.gold_positions(rows, 6102) == [rows[0]]
    assert g.gold_positions(rows, 7) == []


def test_the_book_s_direction_is_read_from_sides_and_an_unreadable_side_is_not_flat() -> None:
    assert g.book_direction([]) == 0
    assert g.book_direction([{"side": "buy"}, {"side": "BUY "}]) == 1
    assert g.book_direction([{"side": "sell"}, {"Side": "Sell"}]) == -1
    # Both directions already held: a second bracket cannot make the hedge worse.
    assert g.book_direction([{"side": "buy"}, {"side": "sell"}]) == 0
    # Unreadable is None, NOT 0 -- treating it as flat would unblock the opposing leg exactly
    # when the desk cannot tell what it is holding.
    assert g.book_direction([{"side": ""}]) is None
    assert g.book_direction([{"qty": 1.0}]) is None
    assert g.book_direction([{"side": "buy"}, {"side": "long"}]) is None
    assert g.OPPOSING_LEG == {1: "sell_stop", -1: "buy_stop"}


# ---------------------------------------------------------------- the placement pass, no venue

class _Api:
    @staticmethod
    def get_all_orders(history: bool = False, lookback_period: str = "") -> list:
        return []


class _Venue:
    """Only what `run` actually calls. It records sends instead of making them."""

    _api = _Api()

    def __init__(self, positions: list[dict], raise_on_positions: bool = False) -> None:
        self._positions = positions
        self._raise = raise_on_positions
        self.sent: list[tuple[str, float, float]] = []

    def account(self) -> dict:
        return {"equity": 100_000.0}

    def quote(self, symbol: str) -> tuple[float, float]:
        return 4320.0, 4320.5

    def instrument_id(self, symbol: str) -> int:
        return 6102

    def positions(self) -> list[dict]:
        if self._raise:
            raise RuntimeError("429 Too Many Requests")
        return self._positions

    def min_lot(self, symbol: str) -> float:
        return 0.01

    def details(self, symbol: str) -> dict:
        return {"contractSize": 100.0, "currency": "USD", "lotStep": 0.01}

    def orders(self, symbol: str | None = None) -> list[dict]:
        return []

    def place_stop(self, symbol: str, side: str, lot: float, *, price: float,
                   stop: float, take_profit: float) -> int:
        self.sent.append((side, lot, price))
        return 7000 + len(self.sent)


class _MT5:
    """The two reads `run` makes of the terminal: one tick and 400 H1 bars."""

    TIMEFRAME_H1 = 16385
    _END = pd.Timestamp("2026-09-16 07:00", tz="UTC")

    class _Tick:
        time = int(pd.Timestamp("2026-09-16 07:30", tz="UTC").timestamp())

    def symbol_info_tick(self, symbol: str) -> _Tick:
        return self._Tick()

    def copy_rates_from_pos(self, symbol: str, tf: int, start: int, count: int) -> list[dict]:
        """A flat 4320 tape whose LAST day ranges 4300-4340, so the asia bracket straddles the
        quote and both legs are legal. Deterministic: the point under test is which leg is sent,
        and a random walk that wandered off the quote would fail for an unrelated reason."""
        idx = pd.date_range(end=self._END, periods=120, freq="h")
        rows = []
        for t in idx:
            hi, lo = (4340.0, 4300.0) if t.date() == self._END.date() else (4324.0, 4316.0)
            rows.append({"time": int(t.timestamp()), "open": 4320.0, "high": hi,
                         "low": lo, "close": 4320.0})
        return rows


def _isolate(monkeypatch, tmp_path) -> None:
    """No test writes the desk's real state, report, intent ledger or log."""
    for name in ("STATE", "OUT", "INTENTS", "GUARD", "LOG"):
        monkeypatch.setattr(g, name, tmp_path / f"{name.lower()}.json")


def _run(monkeypatch, tmp_path, positions: list[dict], **kw) -> tuple[dict, _Venue]:
    _isolate(monkeypatch, tmp_path)
    venue = _Venue(positions, **kw)
    return g.run(venue, _MT5(), armed=True), venue


def _placed_sides(doc: dict) -> set[str]:
    return {s for p in doc["placed"] for s in (p["legs"] or {})}


def test_a_flat_book_still_places_both_legs(monkeypatch, tmp_path) -> None:
    doc, venue = _run(monkeypatch, tmp_path, [])
    assert _placed_sides(doc) == {"buy_stop", "sell_stop"}
    assert sorted(s[0] for s in venue.sent) == ["buy", "sell"]


def test_an_open_long_keeps_the_buy_leg_and_drops_only_the_opposing_sell(
        monkeypatch, tmp_path) -> None:
    doc, venue = _run(monkeypatch, tmp_path,
                      [{"id": 5, "tradableInstrumentId": 6102, "side": "buy", "qty": 0.1}])
    # The harmless half is NOT thrown away with the opposing one.
    assert _placed_sides(doc) == {"buy_stop"}
    assert [s[0] for s in venue.sent] == ["buy"]
    dropped = [s for s in doc["skipped"] if s.get("side") == "sell_stop"]
    assert len(dropped) == 1 and "trade against" in dropped[0]["why"]
    assert doc["state"]["windows"]["asia"]["orders"].keys() == {"buy_stop"}


def test_an_open_short_keeps_the_sell_leg_and_drops_only_the_opposing_buy(
        monkeypatch, tmp_path) -> None:
    doc, venue = _run(monkeypatch, tmp_path,
                      [{"id": 5, "tradableInstrumentId": 6102, "side": "sell", "qty": 0.1}])
    assert _placed_sides(doc) == {"sell_stop"}
    assert [s[0] for s in venue.sent] == ["sell"]


def test_a_position_in_another_instrument_blocks_nothing(monkeypatch, tmp_path) -> None:
    doc, _ = _run(monkeypatch, tmp_path,
                  [{"id": 5, "tradableInstrumentId": 99, "side": "buy", "qty": 0.1}])
    assert _placed_sides(doc) == {"buy_stop", "sell_stop"}


def test_an_unreadable_position_side_still_defers_the_whole_bracket(
        monkeypatch, tmp_path) -> None:
    doc, venue = _run(monkeypatch, tmp_path,
                      [{"id": 5, "tradableInstrumentId": 6102, "side": None, "qty": 0.1}])
    assert doc["placed"] == [] and venue.sent == []
    assert any("unreadable side" in s["why"] for s in doc["skipped"])
    # Not marked placed: the next pass may still act once the side is readable again.
    assert doc["state"]["windows"] == {}


def test_an_unreadable_position_book_still_stands_the_pass_down(monkeypatch, tmp_path) -> None:
    doc, venue = _run(monkeypatch, tmp_path, [], raise_on_positions=True)
    assert doc["placed"] == [] and venue.sent == []
    assert "RuntimeError" in doc["positions_unreadable"]
    assert doc["state"]["windows"] == {}


def test_e8_uses_the_same_profit_ratchet_as_the_fusion_gold_book() -> None:
    idx = pd.date_range("2026-09-16", periods=100, freq="h", tz="UTC")
    close = np.full(len(idx), 100.0)
    bars = pd.DataFrame({"open": close, "high": close + 1.0, "low": close - 1.0,
                         "close": close}, index=idx)
    # A profitable move after entry with a small live ATR must lift this stop; using openDate in
    # the broker clock is what selects the post-entry bars without a UTC conversion mismatch.
    bars.loc[idx[-4]:, "high"] = [106.0, 108.0, 110.0, 110.0]
    pos = {"id": 9, "side": "buy", "avgPrice": 100.0,
           "openDate": int(idx[-4].timestamp() * 1000)}
    window = {"orders": {"buy_stop": {"price": 100.0, "sl": 90.0}}}
    decision = g.trail_decision(pos, window, bars, current_stop=90.0)
    assert decision is not None and decision.moves
    assert decision.new_stop > 90.0 and decision.protected_r_after > decision.protected_r_before
