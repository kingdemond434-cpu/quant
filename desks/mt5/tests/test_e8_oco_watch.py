"""THE E8 GOLD OCO WATCH (prop/e8_oco_watch.py): every minute, cancel and flatten only.

Audit HOLD on #959 (M1): FTMO mirrors E8's bracket, so FTMO's copy can fill on FTMO's quote while
E8's opposite leg still rests, and E8's own pass cancels that leg only every five minutes. These
tests drive the asymmetric path -- FTMO fills first, then E8's opposite leg -- and show the
opposite exposure cannot stand past the watch's minute. A stub venue and fake ids only.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import gold_oco as oco  # noqa: E402
from mt5desk import order_door as door  # noqa: E402
from prop import e8_oco_watch as w  # noqa: E402

NOW = datetime(2026, 11, 11, 5, 5, tzinfo=UTC)       # 07:05 on the UTC+2 server clock
DAY = "2026-11-11"
IID = 7
OPEN_MS = int((NOW + timedelta(hours=2)).timestamp() * 1000)   # broker-clock stamp, today
FT_KEY_ARGS = (63456789, "FTMO-Test")                           # fake
E8_BUY, E8_SELL = 501, 502


class _Api:
    def __init__(self, venue: _Venue) -> None:
        self.venue = venue

    def get_all_orders(self, *, history: bool, lookback_period: str) -> list[dict]:
        return list(self.venue.history)


class _Venue:
    """TradeLocker as e8_gold reads it: E8's asia bracket resting, nothing filled."""

    def __init__(self) -> None:
        self.orders_ = [{"id": E8_BUY, "side": "buy", "type": "stop", "tradableInstrumentId": IID},
                        {"id": E8_SELL, "side": "sell", "type": "stop",
                         "tradableInstrumentId": IID}]
        self.positions_: list[dict] = []
        self.history: list[dict] = []
        self.cancelled: list[int] = []
        self.closed: list[int] = []
        self._api = _Api(self)

    def instrument_id(self, symbol: str) -> int:
        return IID

    def positions(self) -> list[dict]:
        return [dict(p) for p in self.positions_]

    def orders(self, symbol: str | None = None) -> list[dict]:
        return [dict(o) for o in self.orders_]

    def cancel(self, order_id: int) -> bool:
        self.cancelled.append(int(order_id))
        self.orders_ = [o for o in self.orders_ if o["id"] != int(order_id)]
        return True

    def close(self, position_id: int, quantity: float = 0) -> bool:
        self.closed.append(int(position_id))
        self.positions_ = [p for p in self.positions_ if p["id"] != int(position_id)]
        return True

    def place_stop(self, *a: Any, **k: Any) -> int:
        raise AssertionError("the OCO watch never places an order")

    def fill(self, order_id: int, position_id: int) -> None:
        """A resting leg triggers: the order becomes a position opened today."""
        (o,) = [o for o in self.orders_ if o["id"] == order_id]
        self.orders_.remove(o)
        self.positions_.append({"id": position_id, "side": o["side"],
                                "tradableInstrumentId": IID, "openDate": OPEN_MS})
        self.history.append({"id": order_id, "status": "Filled", "positionId": position_id})


def e8_key() -> str:
    return oco.tradelocker_oco_key(_Venue())


def ft_key() -> str:
    return oco.oco_account_key(*FT_KEY_ARGS)


@pytest.fixture
def world(monkeypatch, tmp_path) -> _Venue:
    for name in ("E8_STATE", "E8_INTENTS", "OUT", "LOG"):
        monkeypatch.setattr(w, name, tmp_path / f"{name.lower()}.json")
    oco.MODE_FILE.write_text(json.dumps({"lanes": ["e8", "fusion", "ftmo"],
                                         "modes": {"fusion": "fallback"}}), "utf-8")
    with Path(w.E8_INTENTS).open("w", encoding="utf-8") as fh:
        for oid, side in ((E8_BUY, "buy_stop"), (E8_SELL, "sell_stop")):
            fh.write(json.dumps({"at": (NOW - timedelta(minutes=5)).isoformat(),
                                 "window": "asia", "side": side, "status": "SENT",
                                 "order_id": oid}) + "\n")
    oco.publish_lane("fusion", oco.oco_account_key(72345678, "FusionMarkets-Test"),
                     positions=[], orders=[], date=DAY)
    oco.publish_lane("ftmo", ft_key(), positions=[],
                     orders=[{"id": 9001, "side": "buy"}, {"id": 9002, "side": "sell"}], date=DAY)
    return _Venue()


def _ftmo_copy_fills_long() -> None:
    """FTMO's buy-stop copy fills on FTMO's quote; its follower publishes and claims it."""
    oco.publish_lane("ftmo", ft_key(), positions=[{"id": 9500, "side": "long",
                                                   "opened_date": DAY}],
                     orders=[{"id": 9002, "side": "sell"}], date=DAY)
    assert oco.claim_fill("ftmo", ft_key(), "buy", date=DAY)["won"]


def test_the_server_date_is_new_york_plus_seven() -> None:
    assert w.server_date(NOW) == DAY
    assert w.server_date(datetime(2026, 11, 10, 22, 30, tzinfo=UTC)) == DAY   # 00:30 server
    assert w.server_date(datetime(2026, 7, 1, 20, 59, tzinfo=UTC)) == "2026-07-01"  # 23:59 UTC+3
    assert w.server_date(datetime(2026, 7, 1, 21, 0, tzinfo=UTC)) == "2026-07-02"


def test_ftmo_filling_first_cancels_e8s_opposite_leg_within_the_minute(world) -> None:
    _ftmo_copy_fills_long()
    doc = w.run(world, armed=True, now=NOW)
    assert world.cancelled == [E8_SELL] and world.closed == []
    assert doc["direction"] == {"direction": "long", "first_fill_lane": "ftmo"}
    rows = [r for r in door.read_ledger() if r.get("action") == "cancel"]
    assert [(r["caller"], r["args"]) for r in rows] == [(w.CALLER, [E8_SELL])]
    # E8's published book no longer rests the short: no lane reads an opposite E8 entry.
    st, _ = oco.read_lane("e8")
    assert st is not None and [o["side"] for o in st["orders"]] == ["long"]


def test_the_asymmetric_path_e8s_opposite_leg_fills_after_ftmo_and_cannot_stand(world) -> None:
    """FTMO fills long first; inside the same minute the price reverses through E8's sell stop
    before anything cancels it. E8 is then short against FTMO's long -- and the watch's next pass
    (within the minute) closes E8's short: the opposite exposure does not stand."""
    _ftmo_copy_fills_long()
    world.fill(E8_SELL, 7002)                              # E8 short, opened today
    doc = w.run(world, armed=True, now=NOW)
    assert world.closed == [7002] and world.positions_ == []
    assert any("against" in a for a in doc["alerts"])
    # E8's buy leg agrees with the direction and is kept; the claim recorded the conflict.
    assert world.cancelled == [] and [o["id"] for o in world.orders_] == [E8_BUY]
    entry, _ = oco.day_entry(DAY)
    assert entry is not None and entry["first_fill_lane"] == "ftmo"
    assert [c["lane"] for c in entry.get("conflicts") or []] == ["e8"]
    # And no opposite exposure is left on any lane's published book.
    e8, _ = oco.read_lane("e8")
    assert e8 is not None and e8["positions"] == []


def test_an_e8_fill_claims_the_direction_and_cancels_the_twin_in_the_same_minute(world) -> None:
    world.fill(E8_BUY, 7001)
    doc = w.run(world, armed=True, now=NOW)
    assert doc["direction"] == {"direction": "long", "first_fill_lane": "e8"}
    assert world.cancelled == [E8_SELL] and world.closed == []
    # A fallback lane may follow it at once: E8's own fill.
    entry, _ = oco.day_entry(DAY)
    assert oco.leader_set(entry, date=DAY)


def test_it_never_touches_an_order_or_position_this_lane_did_not_place(world) -> None:
    _ftmo_copy_fills_long()
    world.orders_.append({"id": 888, "side": "sell", "type": "stop", "tradableInstrumentId": IID})
    world.positions_.append({"id": 889, "side": "sell", "tradableInstrumentId": IID,
                             "openDate": OPEN_MS})
    doc = w.run(world, armed=True, now=NOW)
    assert world.cancelled == [E8_SELL] and world.closed == []
    assert any("889" in a for a in doc["alerts"])               # alerted, never closed


def test_a_blind_direction_state_cancels_every_e8_leg(world) -> None:
    oco.direction_path().write_text("{torn", "utf-8")
    doc = w.run(world, armed=True, now=NOW)
    assert sorted(world.cancelled) == [E8_BUY, E8_SELL]
    assert doc["status"] == "DIRECTION_UNREADABLE"


def test_unarmed_it_reports_and_sends_nothing(world) -> None:
    _ftmo_copy_fills_long()
    world.fill(E8_SELL, 7002)
    doc = w.run(world, armed=False, now=NOW)
    assert world.cancelled == [] and world.closed == []
    assert {a["act"] for a in doc["actions"]} == {"oco_direction_flatten"}
    assert all(a.get("shadow") for a in doc["actions"])


def test_no_direction_no_cancel(world) -> None:
    doc = w.run(world, armed=True, now=NOW)
    assert world.cancelled == [] and doc["status"] == "OK" and doc["direction"] is None


def test_an_unnamed_account_does_nothing(world, monkeypatch) -> None:
    def refuse(venue: object) -> str:
        raise oco.IdentityUnavailable("no key")
    monkeypatch.setattr(oco, "tradelocker_oco_key", refuse)
    _ftmo_copy_fills_long()
    doc = w.run(world, armed=True, now=NOW)
    assert doc["status"] == "ACCOUNT_UNNAMED" and world.cancelled == []


def test_the_task_is_registered_through_the_adoption_ensure_list() -> None:
    root = _DESK.parent.parent
    seal = (_DESK / "scripts" / "Adopt-And-Seal.ps1").read_text("utf-8")
    assert '@{ Task = "MT5-E8-OcoWatch"; Installer = "install_e8_oco_watch_task.ps1" }' in seal
    inst = (_DESK / "scripts" / "install_e8_oco_watch_task.ps1").read_text("utf-8")
    assert "$IfMissing" in inst and "prop\\e8_oco_watch.py" in inst
    assert "-RepetitionInterval (New-TimeSpan -Minutes 1)" in inst
    manifest = (_DESK / "ops" / "box_tasks.manifest").read_text("utf-8")
    assert 'TASK name="MT5-E8-OcoWatch" trigger="every 1 minute"' in manifest
    assert "desks/mt5/prop/e8_oco_watch.py" in (root / "ops" / "money_closure.txt").read_text(
        "utf-8")
