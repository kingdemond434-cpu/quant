"""An E8 entry never opens against the Fusion book (E8 bans opposite-account hedging)."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK))

from prop import cross_account as ca  # noqa: E402

NOW = datetime(2026, 10, 13, 21, 0, tzinfo=UTC)


class _Mt5:
    def __init__(self, rows: Any) -> None:
        self.rows = rows

    def positions_get(self) -> Any:
        if isinstance(self.rows, Exception):
            raise self.rows
        return self.rows


def _pos(symbol: str, kind: int) -> SimpleNamespace:
    return SimpleNamespace(symbol=symbol, type=kind)


def _file(tmp_path: Path, positions: list[dict], *, age_s: float = 60) -> Path:
    p = tmp_path / "account_positions.json"
    at = (NOW - timedelta(seconds=age_s)).isoformat()
    p.write_text(json.dumps({"updated_at": at, "positions": positions}), encoding="utf-8")
    return p


def test_an_entry_opposite_to_a_fusion_position_is_refused() -> None:
    book = ca.book_from_terminal(_Mt5([_pos("XAUUSD", 0)]))
    assert book == {"XAUUSD": {1}}
    assert "CROSS_ACCOUNT_HEDGE" in (ca.refusal("XAUUSD", "sell_stop", book) or "")
    assert "CROSS_ACCOUNT_HEDGE" in (ca.refusal("XAU/USD", "sell", book) or "")


def test_an_agreeing_entry_and_another_symbol_pass() -> None:
    book = {"XAUUSD": {1}}
    assert ca.refusal("XAUUSD", "buy_stop", book) is None
    assert ca.refusal("AUDCHF", "sell", book) is None
    assert ca.refusal("XAUUSD", "sell", {}) is None


def test_fusion_holding_both_sides_refuses_both() -> None:
    book = ca.book_from_terminal(_Mt5([_pos("AUDCHF", 0), _pos("AUDCHF", 1)]))
    assert ca.refusal("AUDCHF", "buy", book) and ca.refusal("AUDCHF", "sell", book)


def test_an_unreadable_book_refuses_every_entry() -> None:
    assert ca.book_from_terminal(_Mt5(None)) is None
    assert ca.book_from_terminal(_Mt5(RuntimeError("ipc"))) is None
    assert ca.book_from_terminal(_Mt5([_pos("XAUUSD", 7)])) is None
    assert "CROSS_ACCOUNT_UNREAD" in (ca.refusal("XAUUSD", "buy", None, "UNREADABLE") or "")
    assert "CROSS_ACCOUNT_UNREAD" in (ca.refusal("XAUUSD", "sideways", {}) or "")


def test_the_terminal_is_preferred_and_the_file_is_the_fallback(tmp_path: Path) -> None:
    f = _file(tmp_path, [{"symbol": "USDZAR", "side": "sell"}])
    book, src = ca.fusion_book(_Mt5([_pos("XAUUSD", 1)]), path=f, now=NOW)
    assert (book, src) == ({"XAUUSD": {-1}}, "terminal")
    book, src = ca.fusion_book(_Mt5(None), path=f, now=NOW)
    assert (book, src) == ({"USDZAR": {-1}}, "account_positions.json")
    book, src = ca.fusion_book(None, path=f, now=NOW)
    assert src == "account_positions.json"


def test_a_stale_or_absent_file_is_unreadable_not_flat(tmp_path: Path) -> None:
    stale = _file(tmp_path, [], age_s=ca.MAX_FILE_AGE_S + 1)
    assert ca.fusion_book(None, path=stale, now=NOW) == (None, "UNREADABLE")
    assert ca.fusion_book(None, path=tmp_path / "absent.json", now=NOW) == (None, "UNREADABLE")
    fresh_empty = _file(tmp_path, [], age_s=10)
    assert ca.fusion_book(None, path=fresh_empty, now=NOW) == ({}, "account_positions.json")


def test_the_file_age_follows_the_publisher_period() -> None:
    manifest = (DESK / "ops" / "box_tasks.manifest").read_text(encoding="utf-8")
    line = next(ln for ln in manifest.splitlines() if 'name="MT5-AccountState"' in ln)
    assert 'trigger="every 15 minutes"' in line
    assert ca.PUBLISHER_PERIOD_S == 15 * 60 and ca.MAX_FILE_AGE_S == 2 * ca.PUBLISHER_PERIOD_S


def test_only_resting_legs_that_would_hedge_are_named_for_cancel() -> None:
    legs = {"buy_stop": {"id": 5}, "sell_stop": {"id": 6}}
    assert ca.opposing_resting(legs, "XAUUSD", {"XAUUSD": {1}}) == [("sell_stop", 6)]
    assert ca.opposing_resting(legs, "XAUUSD", {}) == []
    assert ca.opposing_resting(legs, "XAUUSD", None) == []
    assert ca.opposing_resting({"buy_stop": {"id": None}}, "XAUUSD", {"XAUUSD": {-1}}) == []


def test_e8_gold_cancels_its_resting_leg_that_would_fill_against_fusion(
        monkeypatch: Any, tmp_path: Path) -> None:
    """The afternoon bracket rests both legs; Fusion has since gone long gold. The pass cancels
    the sell_stop (its fill would be the banned hedge) and leaves the buy_stop resting."""
    from prop import e8_gold
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "stop_rests_harness", Path(__file__).with_name("test_stop_rests_at_venue.py"))
    assert spec is not None and spec.loader is not None
    h = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h)

    class _Venue(h._GoldVenue):
        def __init__(self) -> None:
            super().__init__(h.EVENT["bid"], h.EVENT["ask"])
            self.cancelled: list[int] = []

        def positions(self) -> list[dict]:
            return []

        def orders(self, symbol: str | None = None) -> list[dict]:
            return [{"id": 77, "stopPrice": 4300.0}, {"id": 78, "stopPrice": 4260.0}]

        def cancel(self, order_id: int) -> bool:
            self.cancelled.append(int(order_id))
            return True

    class _Fusion(h._MT5):
        def positions_get(self) -> list[SimpleNamespace]:
            return [_pos("XAUUSD", 0)]

    for name in ("OUT", "INTENTS", "GUARD", "LOG"):
        monkeypatch.setattr(e8_gold, name, tmp_path / f"{name.lower()}.json")
    state = tmp_path / "state.json"
    legs = {"buy_stop": {"id": 77, "price": 4300.0, "sl": 4280.0, "tp": 4340.0, "lot": 0.1},
            "sell_stop": {"id": 78, "price": 4260.0, "sl": 4280.0, "tp": 4220.0, "lot": 0.1}}
    done = {"orders": {}, "position_id": None, "shadow": False, "placed_hour": 7.0}
    state.write_text(json.dumps({
        "date": str(h._NOW.date()), "carried": {},
        "windows": {"asia": dict(done), "london_am": dict(done),
                    "afternoon": {"placed_at": str(h._NOW), "placed_hour": 14.0, "hi": 4300.0,
                                  "lo": 4260.0, "orders": legs, "position_id": None,
                                  "shadow": False}}}), encoding="utf-8")
    monkeypatch.setattr(e8_gold, "STATE", state)
    venue = _Venue()
    doc = e8_gold.run(venue, _Fusion(), armed=True)
    assert doc["fusion_book"] == "terminal"
    acts = [a for a in doc["actions"] if a["act"] == "cross_account_cancel"]
    assert [(a["side"], a["order_id"]) for a in acts] == [("sell_stop", 78)]
    assert 78 in venue.cancelled and 77 not in venue.cancelled
