"""The single placement primitive -- every refusal here was paid for in a real rejected order.

Eleven discretionary rules plus the momentum book end at the same question: turn a dollar figure
into a spot order, or refuse with a reason. Two implementations of that would drift silently in the
one place where drift costs money, so there is one, and these tests pin its behaviour.
"""

from __future__ import annotations

from typing import Any

import pytest

from libs.execution import spot_order_path as P


class _Venue:
    """A connector stand-in. Injected rather than imported so no test can reach the live venue."""

    def __init__(self, *, armed: bool = True, fill: float = 1.0,
                 fail_order: bool = False, fail_stop: bool = False) -> None:
        self.armed, self.fill = armed, fill
        self.fail_order, self.fail_stop = fail_order, fail_stop
        self.orders: list[tuple[Any, ...]] = []
        self.stops: list[tuple[Any, ...]] = []

    def is_armed(self) -> tuple[bool, str]:
        return self.armed, f"armed={self.armed}"

    def place_market_quote(self, sym: str, side: str, usd: float, *, cycle: str) -> dict[str, Any]:
        if self.fail_order:
            raise RuntimeError("venue rejected the call: HTTP 400")
        self.orders.append((sym, side, usd, cycle))
        return {"orderId": 1, "status": "FILLED", "executedQty": str(self.fill)}

    def place_stop_loss_limit(self, sym: str, side: str, qty: float, stop: float,
                              limit: float, *, cycle: str) -> dict[str, Any]:
        if self.fail_stop:
            raise RuntimeError("stop rejected")
        self.stops.append((sym, side, qty, stop, limit))
        return {"orderId": 2, "status": "NEW"}


@pytest.fixture(autouse=True)
def _clear_rail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("libs.execution.ruin_rail.frozen", lambda *a, **k: (False, "clear"))


def test_A_LATCHED_RAIL_REFUSES_BEFORE_ANYTHING_ELSE_IS_CHECKED(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Order of checks is order of cost. A beautifully-validated order on a halted book is the
    wrong output, so the rail is consulted first and nothing downstream runs."""
    monkeypatch.setattr("libs.execution.ruin_rail.frozen", lambda *a, **k: (True, "KILL present"))
    v = _Venue()
    out = P.place_entry(v, "BNBUSDT", 100.0, cycle="c", quote="USDC", free_quote=1000.0,
                        min_notional=5.0)
    assert out.placed is False and "RUIN RAIL" in out.why
    assert not v.orders


def test_AN_UNARMED_CONNECTOR_PLACES_NOTHING() -> None:
    v = _Venue(armed=False)
    out = P.place_entry(v, "BNBUSDT", 100.0, cycle="c", quote="USDC", free_quote=1000.0,
                        min_notional=5.0)
    assert out.placed is False and "NOT ARMED" in out.why and not v.orders


def test_THE_QUOTE_IS_RETARGETED_NOT_THE_SIGNAL() -> None:
    """EEA retail may not trade Binance USDT pairs; the base asset is the hypothesis and the quote
    is a settlement detail."""
    v = _Venue()
    out = P.place_entry(v, "BNBUSDT", 50.0, cycle="c", quote="USDC", free_quote=1000.0,
                        min_notional=5.0)
    assert out.symbol == "BNBUSDC" and v.orders[0][0] == "BNBUSDC"
    assert P.retarget("BNBUSDT", "") == "BNB", "balances are keyed by the bare base"


def test_A_BUY_IS_CLAMPED_TO_THE_CASH_AND_SAYS_SO() -> None:
    """Targets come from EQUITY, which counts coins already held; a buy spends CASH."""
    v = _Venue()
    out = P.place_entry(v, "ADAUSDT", 40.0, cycle="c", quote="USDC", free_quote=36.20972275,
                        min_notional=5.0)
    assert out.placed and out.usd == 36.20, "the order must floor to the cent, not round"
    assert "CLAMPED" in out.why and "underweight" in out.why


def test_THE_CLAMP_FLOORS_SO_IT_NEVER_EXCEEDS_THE_BALANCE() -> None:
    """36.20972275 rounded to 36.21 is $0.00028 more than exists, and the venue said so twice.
    Rounding to nearest is safe on every order except the one spending the whole balance -- which
    is exactly the order a rebalance ends on."""
    assert P.floor_2dp(36.20972275) == 36.20
    for v in (0.001, 1.005, 99.999, 36.20972275):
        assert P.floor_2dp(v) <= v


def test_BELOW_THE_VENUE_MINIMUM_IT_REFUSES_RATHER_THAN_SENDING() -> None:
    v = _Venue()
    out = P.place_entry(v, "ADAUSDT", 40.0, cycle="c", quote="USDC", free_quote=3.0,
                        min_notional=5.0)
    assert out.placed is False and "below the venue minimum" in out.why and not v.orders


def test_A_STOP_RESTS_AT_THE_VENUE_AND_IS_SIZED_FROM_THE_FILL() -> None:
    """A partial fill with a full-size stop is a stop that cannot execute."""
    v = _Venue(fill=0.4)
    out = P.place_entry(v, "BNBUSDT", 100.0, cycle="c", quote="USDC", free_quote=1000.0,
                        min_notional=5.0, stop_price=600.0, step=0.001)
    assert out.protected is True
    _sym, side, qty, stop, limit = v.stops[0]
    assert side == "SELL" and qty == pytest.approx(0.4)
    assert limit < stop, "the limit must sit below the trigger or it cannot fill on the way down"


def test_A_FAILED_STOP_REPORTS_AN_UNPROTECTED_POSITION() -> None:
    """THE ONE THAT MATTERS. A stop that was never placed and one that was are indistinguishable
    in a journal that logs only the fill."""
    v = _Venue(fail_stop=True)
    out = P.place_entry(v, "BNBUSDT", 100.0, cycle="c", quote="USDC", free_quote=1000.0,
                        min_notional=5.0, stop_price=600.0)
    assert out.placed is True and out.protected is False
    assert "UNPROTECTED" in out.why


def test_NO_DECLARED_STOP_IS_STATED_NOT_ASSUMED() -> None:
    v = _Venue()
    out = P.place_entry(v, "BNBUSDT", 100.0, cycle="c", quote="USDC", free_quote=1000.0,
                        min_notional=5.0, stop_price=None)
    assert out.protected is False and "NO STOP DECLARED" in out.why


def test_THE_STOP_QUANTITY_ROUNDS_DOWN_TO_THE_LOT_STEP() -> None:
    """Rounding up asks to sell more than is held; the venue refuses, and the position is left
    unprotected at the moment it matters."""
    v = _Venue(fill=1.23456)
    P.place_entry(v, "BNBUSDT", 100.0, cycle="c", quote="USDC", free_quote=1000.0,
                  min_notional=5.0, stop_price=600.0, step=0.01)
    assert v.stops[0][2] == pytest.approx(1.23)


def test_A_REJECTED_ORDER_NEVER_CLAIMS_A_FILL() -> None:
    v = _Venue(fail_order=True)
    out = P.place_entry(v, "BNBUSDT", 100.0, cycle="c", quote="USDC", free_quote=1000.0,
                        min_notional=5.0, stop_price=600.0)
    assert out.placed is False and "ORDER REJECTED" in out.why and not v.stops


def test_DRY_RUN_SPENDS_NOTHING() -> None:
    v = _Venue()
    out = P.place_entry(v, "BNBUSDT", 100.0, cycle="c", quote="USDC", free_quote=1000.0,
                        min_notional=5.0, stop_price=600.0, place=False)
    assert out.placed is False and "DRY RUN" in out.why
    assert not v.orders and not v.stops
