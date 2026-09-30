"""E8 sizes a non-USD-quoted pair in dollars (2026-09-30).

The venue's instrument details carried no currency for FX, so `lot_for_risk` treated every cross
as USD-quoted: EURCHF shorts ~25% over-sized on 2026-09-15, JPY crosses at the 0.01 floor."""
from __future__ import annotations

import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK.parent.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

from prop.e8_executor import lot_for_risk  # noqa: E402


class _Venue:
    def __init__(self, quotes: dict[str, float], details: dict | None = None) -> None:
        self._q = quotes
        self._d = details or {"contractSize": 100000, "lotStep": 0.01}

    def min_lot(self, symbol: str) -> float:
        return 0.01

    def details(self, symbol: str) -> dict:
        return dict(self._d)

    def quote(self, symbol: str) -> tuple[float, float]:
        if symbol not in self._q:
            raise KeyError(symbol)
        m = self._q[symbol]
        return m, m


def test_a_chf_quoted_cross_is_converted_at_the_venue_s_rate() -> None:
    v = _Venue({"USDCHF": 0.80})
    # 10 pips on 100k = 100 CHF/lot = 125 USD/lot; $500 risk -> 4.00 lots, not 5.00.
    lot, basis = lot_for_risk(v, "EURCHF", 0.0010, 500.0)
    assert abs(lot - 4.00) < 1e-9, basis
    assert "USD/CHF" in basis


def test_a_jpy_cross_is_sized_to_its_risk_not_to_the_floor() -> None:
    v = _Venue({"USDJPY": 150.0})
    # 30 pips on 100k = 30,000 JPY/lot = 200 USD/lot; $150 risk -> 0.75 lots.
    lot, _ = lot_for_risk(v, "GBPJPY", 0.30, 150.0)
    assert abs(lot - 0.75) < 1e-9


def test_a_ccyusd_rate_multiplies() -> None:
    v = _Venue({"NZDUSD": 0.58})
    lot, _ = lot_for_risk(v, "AUDNZD", 0.0020, 116.0)   # 200 NZD = 116 USD per lot
    assert abs(lot - 1.00) < 1e-9


def test_no_readable_rate_falls_back_to_the_minimum_never_over() -> None:
    lot, basis = lot_for_risk(_Venue({}), "EURCHF", 0.0010, 500.0)
    assert lot == 0.01 and "UNDER-sized" in basis


def test_usd_quoted_and_gold_are_unchanged() -> None:
    v = _Venue({})
    assert abs(lot_for_risk(v, "EURUSD", 0.0010, 500.0)[0] - 5.00) < 1e-9
    gold = _Venue({}, {"contractSize": 100, "lotStep": 0.01})
    assert abs(lot_for_risk(gold, "XAUUSD", 20.0, 490.0)[0] - 0.24) < 1e-9
