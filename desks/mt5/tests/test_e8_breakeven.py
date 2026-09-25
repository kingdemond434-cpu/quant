"""E8's half of the break-even order: the account that could not move a stop at all.

THE DEFECT THIS PINS. The principal's 2026-09-24 order covers BOTH accounts. On MT5 that was a
change to an existing ratchet; on E8 there was no mechanism and no adapter surface to build one
with -- `TradeLockerVenue` exposed connect/quote/place/place_stop/cancel/close/close_all and
nothing between "open it" and "close it". An E8 position's stop was whatever `place` attached at
entry, for the life of the trade, while the same sleeves on Fusion ratcheted every pass. Two
accounts, one book, two different exits, and no test would have noticed.

Everything here runs against a fake venue: no credentials, no network, no funded account. An
adapter whose first real exercise is a real order on a prop account is the thing this desk's own
adapter docstring refuses to be.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prop import e8_executor
from prop.tradelocker_venue import TradeLockerVenue, VenueError


class FakeVenue:
    """The shape `manage_breakeven` reads, and a record of every write it attempts."""

    def __init__(self, positions: list[dict[str, Any]], bid: float, ask: float) -> None:
        self._positions = positions
        self._bid, self._ask = bid, ask
        self._by_key = {"XAUUSD": 101}
        self.modified: list[tuple[int, float]] = []

    def positions(self) -> list[dict[str, Any]]:
        return self._positions

    def quote(self, symbol: str) -> tuple[float, float]:
        return self._bid, self._ask

    def modify_stop(self, position_id: int, stop: float) -> bool:
        self.modified.append((int(position_id), float(stop)))
        return True


def _pos(**kw: Any) -> dict[str, Any]:
    base = {"id": 7, "tradableInstrumentId": 101, "side": "buy",
            "qty": 0.5, "avgPrice": 4300.0, "stopLoss": 4290.0}
    return base | kw


@pytest.fixture(autouse=True)
def _isolated_basis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Never let a test touch the real e8_stop_basis.json on the trading box."""
    monkeypatch.setattr(e8_executor, "STOP_BASIS", tmp_path / "e8_stop_basis.json")


# ------------------------------------------------------------------ the adapter surface
def test_the_venue_can_now_modify_a_stop_at_all() -> None:
    """Before this method there was no path from a decision to an E8 stop."""
    assert hasattr(TradeLockerVenue, "modify_stop")


def test_modify_stop_sends_an_absolute_level_matching_how_place_attaches_one() -> None:
    sent: dict[str, Any] = {}

    class Api:
        def modify_position(self, position_id: int, modification_params: dict) -> bool:
            sent.update({"id": position_id, **modification_params})
            return True

    v = TradeLockerVenue(api=Api())
    assert v.modify_stop(7, 4300.04)
    assert sent == {"id": 7, "stopLoss": 4300.04, "stopLossType": "absolute"}


def test_modify_stop_refuses_a_non_positive_level_rather_than_removing_the_stop() -> None:
    v = TradeLockerVenue(api=object())
    with pytest.raises(VenueError):
        v.modify_stop(7, 0.0)


# ------------------------------------------------------------------ the management pass
def test_a_long_past_the_trigger_is_moved_to_break_even() -> None:
    # R = 10.0; E8 is commission-free, so 0.85R of bid excursion is enough.
    v = FakeVenue([_pos()], bid=4309.0, ask=4309.2)
    rows = e8_executor.manage_breakeven(v, armed=True)
    assert v.modified == [(7, 4300.0)], rows
    assert rows[0]["action"] == "MODIFY"


def test_shadow_by_default_sends_nothing() -> None:
    v = FakeVenue([_pos()], bid=4309.0, ask=4309.2)
    rows = e8_executor.manage_breakeven(v, armed=False)
    assert v.modified == []
    assert rows[0]["action"] == "SHADOW"
    assert rows[0]["stop_now"] == pytest.approx(4300.0)


def test_a_position_short_of_the_trigger_is_left_alone() -> None:
    v = FakeVenue([_pos()], bid=4302.0, ask=4302.2)   # 0.2R
    rows = e8_executor.manage_breakeven(v, armed=True)
    assert v.modified == []
    assert rows[0]["action"] == "HOLD"


def test_a_stop_that_already_protects_more_is_never_widened() -> None:
    """The invariant, on the account where a widened stop breaches a prop drawdown rule."""
    v = FakeVenue([_pos(stopLoss=4305.0)], bid=4309.0, ask=4309.2)
    rows = e8_executor.manage_breakeven(v, armed=True)
    assert v.modified == []
    assert rows[0]["action"] == "HOLD"
    assert "never widened" in rows[0]["why"]


def test_a_short_is_floored_below_its_entry_and_pays_the_spread_to_arm() -> None:
    p = _pos(side="sell", stopLoss=4310.0)
    # bid 4291.0 -> gross 9.0, minus the 0.2 spread = 8.8 net, which clears 0.85 x 10.
    v = FakeVenue([p], bid=4291.0, ask=4291.2)
    rows = e8_executor.manage_breakeven(v, armed=True)
    assert v.modified == [(7, 4300.0)], rows

    # One spread short of the trigger the same position must NOT arm: gross 8.6, less the 0.2
    # spread the short must pay to buy back, is 8.4 against a 8.5 trigger. The basis file is
    # cleared first because the watermark from the call above would otherwise carry the arming
    # over -- which is the watermark working, and is pinned separately below.
    e8_executor.STOP_BASIS.unlink()
    v2 = FakeVenue([_pos(side="sell", stopLoss=4310.0)], bid=4291.4, ask=4291.6)
    assert e8_executor.manage_breakeven(v2, armed=True)[0]["action"] == "HOLD"
    assert v2.modified == []


def test_a_position_with_no_stop_is_skipped_rather_than_given_an_invented_one() -> None:
    v = FakeVenue([_pos(stopLoss=None)], bid=4309.0, ask=4309.2)
    rows = e8_executor.manage_breakeven(v, armed=True)
    assert v.modified == []
    assert rows[0]["action"] == "SKIP"
    assert "none invented" in rows[0]["why"]


def test_a_position_with_no_entry_price_is_skipped() -> None:
    v = FakeVenue([_pos(avgPrice=None)], bid=4309.0, ask=4309.2)
    assert e8_executor.manage_breakeven(v, armed=True)[0]["action"] == "SKIP"


# ------------------------------------------------------------------ the state file
def test_the_watermark_survives_a_pullback_so_the_floor_does_not_disarm() -> None:
    p = _pos()
    v = FakeVenue([p], bid=4309.0, ask=4309.2)
    e8_executor.manage_breakeven(v, armed=True)          # arms and moves
    v2 = FakeVenue([_pos(stopLoss=4300.0)], bid=4301.0, ask=4301.2)   # price falls back
    rows = e8_executor.manage_breakeven(v2, armed=True)
    # Still armed off the watermark, but the stop already sits at break-even, so: hold.
    assert v2.modified == []
    assert "never widened" in rows[0]["why"]


def test_the_basis_is_pruned_when_a_position_closes(tmp_path: Path) -> None:
    """The MT5 side's equivalent store grows without bound; this one must not copy that."""
    v = FakeVenue([_pos()], bid=4309.0, ask=4309.2)
    e8_executor.manage_breakeven(v, armed=True)
    assert json.loads(e8_executor.STOP_BASIS.read_text())["7"]["stop_distance"] == 10.0
    e8_executor.manage_breakeven(FakeVenue([], bid=4309.0, ask=4309.2), armed=True)
    assert json.loads(e8_executor.STOP_BASIS.read_text()) == {}


def test_the_level_is_recomputed_from_the_venue_not_from_the_state_file() -> None:
    """A corrupt watermark can delay the floor. It must never be able to MOVE it."""
    v = FakeVenue([_pos()], bid=4309.0, ask=4309.2)
    e8_executor.manage_breakeven(v, armed=True)
    e8_executor.STOP_BASIS.write_text(json.dumps({"7": {"stop_distance": 10.0,
                                                        "extreme": 9999.0}}))
    v2 = FakeVenue([_pos(avgPrice=4400.0, stopLoss=4390.0)], bid=4409.0, ask=4409.2)
    e8_executor.manage_breakeven(v2, armed=True)
    assert v2.modified == [(7, 4400.0)], "the level must follow avgPrice, not the state file"


def test_an_unreadable_basis_file_degrades_to_a_fresh_watermark(tmp_path: Path) -> None:
    e8_executor.STOP_BASIS.write_text("{not json")
    v = FakeVenue([_pos()], bid=4309.0, ask=4309.2)
    assert e8_executor.manage_breakeven(v, armed=True)[0]["action"] == "MODIFY"


def test_a_venue_that_raises_on_quote_skips_that_position_without_taking_the_pass_down() -> None:
    class Broken(FakeVenue):
        def quote(self, symbol: str) -> tuple[float, float]:
            raise VenueError("no quote")

    rows = Broken([_pos()], bid=0.0, ask=0.0).__class__(
        [_pos()], bid=0.0, ask=0.0)
    out = e8_executor.manage_breakeven(rows, armed=True)
    assert out[0]["action"] == "SKIP"
