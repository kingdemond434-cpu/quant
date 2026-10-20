"""E8 gold skips a window whose leg would need more than GOLD_MAX_LOT (2026-10-20).

`lot_for_risk` sizes a leg as the window's risk over its stop distance, and nothing bounded the
quotient. The principal's coordinator ruled that a stop tight enough to need more than 0.75 lots
at the window's risk is SKIPPED, never shrunk: the whole bracket stands aside (no lone leg
rests), the skip is journalled RAIL_BLOCKED with the window's risk as missed growth, and the box
may move the ceiling through data/E8_GOLD_MAX_LOT.json without a code change.

The fixture is test_e8_gold_guard_and_open_risk's: the afternoon window is due with a 33.5-point
stop, 500 USD of risk -> 0.14 lots at the venue's 100 oz contract. A 10 oz contract makes the
same risk 1.49 lots, over the default ceiling.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent), str(_DESK / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import test_e8_gold_guard_and_open_risk as h  # noqa: E402
from prop import e8_gold as g  # noqa: E402


class _Venue(h._Venue):
    """The shared fake, able to take an armed send, with a settable contract size."""

    def __init__(self, contract: float = 100.0) -> None:
        super().__init__()
        self._contract = contract
        self.sent: list[tuple[str, float, float]] = []

    def details(self, symbol: str) -> dict[str, Any]:
        return {"contractSize": self._contract, "currency": "USD", "lotStep": 0.01}

    def place_stop(self, symbol: str, side: str, lot: float, *, price: float, stop: float,
                   take_profit: float) -> int:
        self.sent.append((side, float(lot), float(price)))
        return 7000 + len(self.sent)


def _sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
             override: Any = None) -> Path:
    h._sandbox(monkeypatch, tmp_path)
    p = tmp_path / "E8_GOLD_MAX_LOT.json"
    if override is not None:
        p.write_text(override if isinstance(override, str) else json.dumps(override),
                     encoding="utf-8")
    monkeypatch.setattr(g, "GOLD_MAX_LOT_FILE", p)
    return p


def _journal(tmp_path: Path) -> list[dict[str, Any]]:
    path = tmp_path / "intents.json"
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _ceiling_skips(doc: dict[str, Any]) -> list[dict[str, Any]]:
    return [s for s in doc["skipped"] if s.get("rail") == g.LOT_CEILING_RAIL]


def test_a_window_under_the_ceiling_is_sent_unchanged(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _sandbox(monkeypatch, tmp_path)
    venue = _Venue()
    doc = g.run(venue, h._MT5(), armed=True)
    assert doc["lot_ceiling"] == {"max_lot": g.GOLD_MAX_LOT, "source": "default GOLD_MAX_LOT"}
    assert not _ceiling_skips(doc)
    assert sorted(venue.sent) == [("buy", 0.14, 4310.0), ("sell", 0.14, 4290.0)]
    legs = doc["placed"][0]["legs"]
    assert {side: leg["lot"] for side, leg in legs.items()} == {"buy_stop": 0.14,
                                                               "sell_stop": 0.14}


def test_a_window_over_the_ceiling_sends_neither_leg_and_bills_the_risk(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _sandbox(monkeypatch, tmp_path)
    venue = _Venue(contract=10.0)                     # 500 USD / (33.5 x 10) = 1.49 lots
    doc = g.run(venue, h._MT5(), armed=True)
    assert venue.sent == [], "no leg of an over-ceiling bracket reaches the venue"
    assert doc["placed"] == []
    (skip,) = _ceiling_skips(doc)
    assert skip["window"] == "afternoon" and "lot ceiling" in skip["why"]
    assert "skipped, not shrunk" in skip["why"]
    assert skip["lots"] == {"buy_stop": 1.49, "sell_stop": 1.49}
    assert skip["max_lot"] == g.GOLD_MAX_LOT
    assert skip["missed_growth_risk_usd"] == pytest.approx(500.0)
    (row,) = [r for r in _journal(tmp_path) if r.get("rail") == g.LOT_CEILING_RAIL]
    assert row["status"] == "RAIL_BLOCKED" and row["missed_growth_risk_usd"] == 500.0
    assert row.get("order_id") is None
    assert "lot ceiling" in (tmp_path / "log.json").read_text(encoding="utf-8")
    # The window is spent for the day: the next pass neither sends it nor bills it again.
    saved = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert saved["windows"]["afternoon"]["orders"] == {}
    assert saved["windows"]["afternoon"]["skipped"] == g.LOT_CEILING_RAIL
    again = g.run(venue, h._MT5(), armed=True)
    assert venue.sent == [] and not _ceiling_skips(again)
    assert len([r for r in _journal(tmp_path) if r.get("rail") == g.LOT_CEILING_RAIL]) == 1


def test_one_leg_over_the_ceiling_skips_its_twin_too() -> None:
    why = g.lot_ceiling_breach({"buy_stop": 0.5, "sell_stop": 0.8}, 0.75)
    assert why is not None and "sell_stop 0.8" in why and "buy_stop" not in why
    assert g.lot_ceiling_breach({"buy_stop": 0.75, "sell_stop": 0.75}, 0.75) is None
    assert g.lot_ceiling_breach({}, 0.75) is None


def test_the_box_override_is_read(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _sandbox(monkeypatch, tmp_path, override={"max_lot": 0.10})
    assert g.gold_max_lot() == (0.10, "E8_GOLD_MAX_LOT.json")
    venue = _Venue()                                   # 0.14 lots, over a 0.10 ceiling
    doc = g.run(venue, h._MT5(), armed=True)
    assert venue.sent == []
    (skip,) = _ceiling_skips(doc)
    assert skip["max_lot"] == 0.10 and skip["max_lot_source"] == "E8_GOLD_MAX_LOT.json"


def test_a_raised_override_lets_a_larger_leg_through(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _sandbox(monkeypatch, tmp_path, override={"max_lot": 2.0})
    venue = _Venue(contract=10.0)
    doc = g.run(venue, h._MT5(), armed=True)
    assert not _ceiling_skips(doc)
    assert sorted(venue.sent) == [("buy", 1.49, 4310.0), ("sell", 1.49, 4290.0)]


@pytest.mark.parametrize("override", [
    {"max_lot": 0}, {"max_lot": -1.0}, {"max_lot": "1.0"}, {"max_lot": True},
    {"max_lot": None}, {}, [0.5], "NaN", '{"max_lot": Infinity}', "{ not json",
])
def test_an_invalid_override_falls_back_to_the_default(monkeypatch: pytest.MonkeyPatch,
                                                       tmp_path: Path, override: Any) -> None:
    _sandbox(monkeypatch, tmp_path, override=override)
    lot, src = g.gold_max_lot()
    assert lot == g.GOLD_MAX_LOT and src.startswith("default GOLD_MAX_LOT (")
    venue = _Venue(contract=10.0)
    doc = g.run(venue, h._MT5(), armed=True)
    assert venue.sent == [], "a bad override never switches the ceiling off"
    assert _ceiling_skips(doc)[0]["max_lot"] == g.GOLD_MAX_LOT


def test_an_unreadable_override_never_raises(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    p = _sandbox(monkeypatch, tmp_path)
    p.mkdir()                                          # exists, but is not a readable file
    assert g.gold_max_lot()[0] == g.GOLD_MAX_LOT
