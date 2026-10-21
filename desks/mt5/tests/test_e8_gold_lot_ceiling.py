"""E8 gold caps every leg at GOLD_MAX_LOT -- shrunk, never skipped (audit HOLDs, 2026-10-20).

`lot_for_risk` sizes a leg as the window's risk over its stop distance, and nothing bounded the
quotient. v1 skipped a window whose leg needed more than 0.75 lots; the audit rejected that under
growth-governance Rule 1 (a tight stop is exactly where a capped leg is safe). The leg is sent AT
the ceiling; v4 then FITS it to the concurrent-risk budget on its risk plus the lane's slip in
points (`bracket_slip`, 24.13 until 20 stop exits are measured) instead of deferring the window
silently. Every cut is journalled RAIL_SHRUNK (published two-sided by missed_growth); a lot that
cannot fit above the venue minimum is a RAIL_BLOCKED row with reason `lot_ceiling`, never a
silent skip. An override above E8's 20-lot cap or below the venue minimum is refused.

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

    def place_stop(
        self, symbol: str, side: str, lot: float, *, price: float, stop: float, take_profit: float
    ) -> int:
        self.sent.append((side, float(lot), float(price)))
        return 7000 + len(self.sent)


def _sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, override: Any = None) -> Path:
    h._sandbox(monkeypatch, tmp_path)
    p = tmp_path / "E8_GOLD_MAX_LOT.json"
    if override is not None:
        p.write_text(
            override if isinstance(override, str) else json.dumps(override), encoding="utf-8"
        )
    monkeypatch.setattr(g, "GOLD_MAX_LOT_FILE", p)
    return p


def _journal(tmp_path: Path) -> list[dict[str, Any]]:
    path = tmp_path / "intents.json"
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def test_a_window_under_the_ceiling_is_sent_unchanged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path)
    venue = _Venue()
    doc = g.run(venue, h._MT5(), armed=True)
    assert doc["lot_ceiling"] == {"max_lot": g.GOLD_MAX_LOT, "source": "default GOLD_MAX_LOT"}
    assert "shrunk" not in doc
    assert sorted(venue.sent) == [("buy", 0.14, 4310.0), ("sell", 0.14, 4290.0)]
    legs = doc["placed"][0]["legs"]
    assert {side: leg["lot"] for side, leg in legs.items()} == {"buy_stop": 0.14, "sell_stop": 0.14}
    rows = _journal(tmp_path)
    assert [r["status"] for r in rows] == ["SENT", "SENT"]
    assert all("lot_ceiling" not in r and r["risk_usd"] == 500.0 for r in rows)


def test_a_leg_over_the_ceiling_is_sent_at_the_ceiling_and_the_withheld_risk_billed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path)
    venue = _Venue(contract=10.0)  # 500 USD / (33.5 x 10) = 1.49 lots
    doc = g.run(venue, h._MT5(), armed=True)
    assert sorted(venue.sent) == [("buy", 0.75, 4310.0), ("sell", 0.75, 4290.0)]
    assert [p["window"] for p in doc["placed"]] == ["afternoon"]
    (shrink,) = doc["shrunk"]
    assert shrink["rail"] == g.LOT_CEILING_RAIL and shrink["reason"] == g.LOT_CEILING_REASON
    assert shrink["unshrunk_lots"] == {"buy_stop": 1.49, "sell_stop": 1.49}
    assert shrink["lots"] == {"buy_stop": 0.75, "sell_stop": 0.75}
    assert shrink["risk_usd"] == pytest.approx(33.5 * 0.75 * 10)  # 251.25
    assert shrink["missed_growth_risk_usd"] == pytest.approx(500.0 - 251.25)
    assert not [s for s in doc["skipped"] if s.get("rail") == g.LOT_CEILING_RAIL]
    rows = _journal(tmp_path)
    (billed,) = [r for r in rows if r.get("rail") == g.LOT_CEILING_RAIL]
    assert billed["status"] == "RAIL_SHRUNK" and billed.get("order_id") is None
    sent = [r for r in rows if r["status"] == "SENT"]
    assert len(sent) == 2 and all(r["risk_usd"] == 251.25 and r["lot"] == 0.75 for r in sent)
    assert all(r["shrunk"] == {"unshrunk_lot": 1.49, "by": [g.LOT_CEILING_REASON]} for r in sent)
    assert "SHRUNK" in (tmp_path / "log.json").read_text(encoding="utf-8")
    # The window is placed: the next pass neither re-sends nor bills it again.
    again = g.run(venue, h._MT5(), armed=True)
    assert len(venue.sent) == 2 and "shrunk" not in again
    assert len([r for r in _journal(tmp_path) if r.get("rail") == g.LOT_CEILING_RAIL]) == 1


def test_the_capped_leg_is_fitted_to_the_budget_not_deferred(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert g.shrunk_budget_risk(0.75, 33.5, 10.0) == pytest.approx(0.75 * 10 * (33.5 + 24.13))
    # (2,500 - 100) / 1.25 = 1,920 of budget over 10 oz x (33.5 + 400) points -> 0.44 lots.
    assert g.ceiling_budget_lot(0.0, 2500.0, 33.5, 10.0, 400.0) == pytest.approx(1920 / 4335)
    _sandbox(monkeypatch, tmp_path)
    monkeypatch.setattr(g, "DEFAULT_SLIP_POINTS", 400.0)
    venue = _Venue(contract=10.0)
    doc = g.run(venue, h._MT5(), armed=True)
    assert sorted(venue.sent) == [("buy", 0.44, 4310.0), ("sell", 0.44, 4290.0)]
    assert [p["window"] for p in doc["placed"]] == ["afternoon"]
    assert not [s for s in doc["skipped"] if s["window"] == "afternoon"]
    ceil = [x for x in doc["shrunk"] if x["rail"] == g.LOT_CEILING_RAIL]
    assert ceil and ceil[-1]["lots"] == {"buy_stop": 0.44, "sell_stop": 0.44}
    assert ceil[0]["unshrunk_lots"] == {"buy_stop": 1.49, "sell_stop": 1.49}


def test_a_100oz_leg_over_the_ceiling_is_fitted_and_sent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The venue's real contract. 3% of 100k over a 33.5-point stop is 0.89 lots, capped to 0.75;
    the budget (1,920 over 100 x (33.5 + 24.13)) fits 0.33; the floor (2,500 over
    100 x (2 x 33.5 + 24.13)) fits 0.27. The window is SENT at 0.27, with every cut billed."""
    _sandbox(monkeypatch, tmp_path)
    monkeypatch.setattr(g, "RISK_FRAC", 0.03)
    venue = _Venue(contract=100.0)
    doc = g.run(venue, h._MT5(), armed=True)
    assert sorted(venue.sent) == [("buy", 0.27, 4310.0), ("sell", 0.27, 4290.0)]
    assert [p["window"] for p in doc["placed"]] == ["afternoon"]
    rails = [x["rail"] for x in doc["shrunk"]]
    assert g.LOT_CEILING_RAIL in rails and g.DAILY_FLOOR_RAIL in rails
    assert doc["shrunk"][-1]["lots"] == {"buy_stop": 0.27, "sell_stop": 0.27}
    rows = _journal(tmp_path)
    sent = [r for r in rows if r["status"] == "SENT"]
    assert len(sent) == 2 and all(r["lot"] == 0.27 for r in sent)
    assert all(r["risk_usd"] == pytest.approx(33.5 * 0.27 * 100) for r in sent)
    shrunk = [r for r in rows if r["status"] == "RAIL_SHRUNK"]
    assert {r["rail"] for r in shrunk} >= {g.LOT_CEILING_RAIL, g.DAILY_FLOOR_RAIL}
    assert sum(r["missed_growth_risk_usd"] for r in shrunk) == pytest.approx(
        3000.0 - 33.5 * 0.27 * 100, abs=1.0
    )


def test_a_capped_leg_that_cannot_fit_writes_a_reasoned_row(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path)
    monkeypatch.setattr(g, "RISK_FRAC", 0.03)
    monkeypatch.setattr(g, "DEFAULT_SLIP_POINTS", 100_000.0)
    venue = _Venue(contract=100.0)
    doc = g.run(venue, h._MT5(), armed=True)
    assert venue.sent == [] and doc["placed"] == []
    (skip,) = [s for s in doc["skipped"] if s.get("rail") == g.LOT_CEILING_RAIL]
    assert skip["reason"] == g.LOT_CEILING_REASON and "venue minimum" in skip["why"]
    (row,) = [r for r in _journal(tmp_path) if r["status"] == "RAIL_BLOCKED"]
    assert row["rail"] == g.LOT_CEILING_RAIL and row["reason"] == g.LOT_CEILING_REASON
    assert row["missed_growth_risk_usd"] > 0


def test_cap_lot_is_pure_and_only_ever_shrinks() -> None:
    assert g.cap_lot(0.75, 0.75) == (0.75, False)
    assert g.cap_lot(0.14, 0.75) == (0.14, False)
    assert g.cap_lot(1.49, 0.75) == (0.75, True)
    assert g.cap_lot(1.49, 0.755, lambda x: 0.75) == (0.75, True)


def test_the_box_override_is_read(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _sandbox(monkeypatch, tmp_path, override={"max_lot": 0.10})
    assert g.gold_max_lot() == (0.10, "E8_GOLD_MAX_LOT.json")
    venue = _Venue()  # 0.14 lots, over a 0.10 ceiling
    doc = g.run(venue, h._MT5(), armed=True)
    assert sorted(venue.sent) == [("buy", 0.10, 4310.0), ("sell", 0.10, 4290.0)]
    (shrink,) = doc["shrunk"]
    assert shrink["max_lot"] == 0.10 and shrink["max_lot_source"] == "E8_GOLD_MAX_LOT.json"


def test_a_raised_override_lets_a_larger_leg_through(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path, override={"max_lot": 2.0})
    venue = _Venue(contract=10.0)
    doc = g.run(venue, h._MT5(), armed=True)
    assert "shrunk" not in doc
    assert sorted(venue.sent) == [("buy", 1.49, 4310.0), ("sell", 1.49, 4290.0)]


def test_the_bounds_of_the_override_are_inclusive(tmp_path: Path) -> None:
    p = tmp_path / "E8_GOLD_MAX_LOT.json"
    p.write_text(json.dumps({"max_lot": g.GOLD_MAX_LOT_CAP}), encoding="utf-8")
    assert g.gold_max_lot(p, min_lot=0.01)[0] == g.GOLD_MAX_LOT_CAP
    p.write_text(json.dumps({"max_lot": 0.01}), encoding="utf-8")
    assert g.gold_max_lot(p, min_lot=0.01)[0] == 0.01


@pytest.mark.parametrize(
    "override",
    [
        {"max_lot": 0},
        {"max_lot": -1.0},
        {"max_lot": "1.0"},
        {"max_lot": True},
        {"max_lot": None},
        {},
        [0.5],
        "NaN",
        '{"max_lot": Infinity}',
        "{ not json",
        {"max_lot": 1e9},
        {"max_lot": 75},
        {"max_lot": 20.5},
        {"max_lot": 0.001},
    ],
)
def test_an_invalid_override_falls_back_to_the_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, override: Any
) -> None:
    _sandbox(monkeypatch, tmp_path, override=override)
    lot, src = g.gold_max_lot(min_lot=0.01)
    assert lot == g.GOLD_MAX_LOT and src.startswith("default GOLD_MAX_LOT (")
    venue = _Venue(contract=10.0)
    doc = g.run(venue, h._MT5(), armed=True)
    assert doc["lot_ceiling"]["max_lot"] == g.GOLD_MAX_LOT
    assert sorted(venue.sent) == [("buy", 0.75, 4310.0), ("sell", 0.75, 4290.0)], (
        "a bad override never switches the ceiling off, nor idles the lane"
    )


def test_an_unreadable_override_never_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    p = _sandbox(monkeypatch, tmp_path)
    p.mkdir()  # exists, but is not a readable file
    assert g.gold_max_lot()[0] == g.GOLD_MAX_LOT


def test_missed_growth_publishes_the_ceiling_two_sided(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sys.path.insert(0, str(_DESK / "research"))
    import missed_growth as mg

    journal = tmp_path / "intents.json"
    monkeypatch.setattr(mg, "E8_INTENTS", journal)
    assert mg.published_e8_gold_lines()["verdict"] == mg.UNMEASURED  # absent: never a zero
    journal.write_text(json.dumps({"status": "SENT", "order_id": 1}) + "\n", encoding="utf-8")
    assert mg.published_e8_gold_lines()["verdict"] == mg.NOT_BINDING
    _sandbox(monkeypatch, tmp_path)
    g.run(_Venue(contract=10.0), h._MT5(), armed=True)
    out = mg.published_e8_gold_lines()
    (line,) = out["lines"]
    assert line["rail"] == g.LOT_CEILING_RAIL and line["n_shrunk"] == 1
    assert line["cost"]["risk_withheld_usd"] == pytest.approx(248.75)
    assert line["saving"]["verdict"] == mg.UNMEASURED and out["verdict"] == mg.UNMEASURED
