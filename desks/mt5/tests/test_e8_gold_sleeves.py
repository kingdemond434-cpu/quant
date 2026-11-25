"""CERTIFIED XAUUSD SLEEVES ON E8 (prop/e8_executor.GOLD_SLEEVES, 2026-11-25).

Every XAUUSD sleeve used to be refused as OWNED_BY_GOLD_LANE, so the certified gold sleeves that
FTMO trades (#1323) had no E8 route. A sleeve leg is now placed only under the cross-account gold
direction lock, never while this account rests a gold entry on the other side, and fails closed
on anything unreadable. Stub venue; the OCO's own behaviour is pinned in test_gold_oco.py.
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import gold_oco as oco  # noqa: E402
from prop import e8_executor as ex  # noqa: E402
from prop import e8_guard  # noqa: E402

NOW = datetime(2026, 11, 25, 3, 0, tzinfo=UTC)
IID = 4242


class Venue:
    def __init__(self, orders: list[dict[str, Any]] | None = None) -> None:
        self._orders = orders or []

    def positions(self) -> list[dict[str, Any]]:
        return []

    def orders(self) -> list[dict[str, Any]]:
        return list(self._orders)

    def instrument_id(self, sym: str) -> int:
        return IID


@pytest.fixture
def wired(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    seen: dict[str, Any] = {"gate": []}
    monkeypatch.setattr(oco, "tradelocker_oco_key", lambda venue: "tl:key")

    def sync_lane(lane: str, key: str, rows: Any, *, date: str, holder: str) -> dict[str, Any]:
        seen["sync"] = (lane, key, date, holder)
        rows()
        return {"published": True, "claims": []}

    def gate(lane: str, side: str, *, key: str, date: str) -> Any:
        seen["gate"].append((lane, side, key, date))
        return SimpleNamespace(allowed=seen.get("allow", True), why="gold OCO: refused")

    monkeypatch.setattr(oco, "sync_lane", sync_lane)
    monkeypatch.setattr(oco, "gate", gate)
    return seen


def test_the_flag_is_on_and_the_revert_is_the_old_refusal() -> None:
    assert ex.GOLD_SLEEVES is True
    src = Path(ex.__file__).read_text(encoding="utf-8")
    assert 'if str(sym).upper() == "XAUUSD" and not GOLD_SLEEVES:' in src
    assert '"OWNED_BY_GOLD_LANE"' in src


def test_a_clean_account_is_judged_by_the_direction_lock_on_the_e8_server_day(wired: dict[str, Any]) -> None:
    why, ctx = ex._gold_sleeve_refusal(Venue(), "buy", now=NOW, holder="e8_executor:s")
    assert why is None
    assert ctx == ("tl:key", e8_guard.server_day(NOW))
    assert wired["sync"][0] == "e8" and wired["sync"][2] == e8_guard.server_day(NOW)
    assert wired["gate"] == [("e8", "buy", "tl:key", e8_guard.server_day(NOW))]


def test_the_direction_lock_refusal_is_returned(wired: dict[str, Any]) -> None:
    wired["allow"] = False
    why, _ = ex._gold_sleeve_refusal(Venue(), "sell", now=NOW, holder="h")
    assert why == "gold OCO: refused"


def test_a_resting_gold_entry_on_the_other_side_keeps_the_window_slot(wired: dict[str, Any]) -> None:
    bracket = [{"id": 1, "side": "buy", "type": "stop", "tradableInstrumentId": IID},
               {"id": 2, "side": "sell", "type": "stop", "tradableInstrumentId": IID}]
    why, _ = ex._gold_sleeve_refusal(Venue(bracket), "buy", now=NOW, holder="h")
    assert why is not None and "other side" in why and "2" in why
    assert wired["gate"] == []


def test_a_resting_gold_entry_on_the_same_side_does_not_refuse(wired: dict[str, Any]) -> None:
    same = [{"id": 7, "side": "buy", "type": "stop", "tradableInstrumentId": IID}]
    why, _ = ex._gold_sleeve_refusal(Venue(same), "buy", now=NOW, holder="h")
    assert why is None


def test_an_unnamed_account_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(venue: Any) -> str:
        raise oco.IdentityUnavailable("no keyed identity")
    monkeypatch.setattr(oco, "tradelocker_oco_key", boom)
    why, ctx = ex._gold_sleeve_refusal(Venue(), "buy", now=NOW, holder="h")
    assert why is not None and "fail closed" in why and ctx is None


def test_an_unpublished_gold_state_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(oco, "tradelocker_oco_key", lambda venue: "tl:key")
    monkeypatch.setattr(oco, "sync_lane",
                        lambda *a, **k: {"published": False, "why": "lock held"})
    monkeypatch.setattr(oco, "gate", lambda *a, **k: pytest.fail("gate read without a publish"))
    why, _ = ex._gold_sleeve_refusal(Venue(), "buy", now=NOW, holder="h")
    assert why is not None and "not republished" in why and "fail closed" in why


def test_the_republish_after_a_send_reports_what_happened(wired: dict[str, Any]) -> None:
    out = ex._gold_republish(Venue(), ("tl:key", "2026-11-25"), holder="h")
    assert out["published"] is True and wired["sync"][:3] == ("e8", "tl:key", "2026-11-25")
