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

    #: Spot by default. A margin stand-in sets this True, exactly as the real connectors do.
    SUPPORTS_BORROW = False

    def __init__(self, *, armed: bool = True, fill: float = 1.0,
                 fail_order: bool = False, fail_stop: bool = False) -> None:
        self.armed, self.fill = armed, fill
        self.fail_order, self.fail_stop = fail_order, fail_stop
        self.orders: list[tuple[Any, ...]] = []
        self.stops: list[tuple[Any, ...]] = []
        self.borrowed: list[bool] = []

    def is_armed(self) -> tuple[bool, str]:
        return self.armed, f"armed={self.armed}"

    def place_market_quote(self, sym: str, side: str, usd: float, *, cycle: str,
                           borrow: bool = False) -> dict[str, Any]:
        if self.fail_order:
            raise RuntimeError("venue rejected the call: HTTP 400")
        self.orders.append((sym, side, usd, cycle))
        self.borrowed.append(borrow)
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


# ------------------------------------------------------------------------------ borrowing legs
class _MarginVenue(_Venue):
    SUPPORTS_BORROW = True


def test_A_BORROWING_LEG_IS_NOT_CLAMPED_TO_FREE_CASH() -> None:
    """THE WHOLE POINT OF A MARGIN WALLET. Clamping to free quote would cap the book at 1x and
    silently discard the leverage the policy computed -- every leg filled, every leg smaller than
    the sizing assumed, and nothing in the journal saying so."""
    v = _MarginVenue()
    out = P.place_entry(v, "BTCUSDT", 500.0, cycle="20260815", quote="USDC",
                        free_quote=100.0, min_notional=5.0, borrow=True)
    assert out.placed and out.usd == 500.0
    assert v.borrowed == [True], "the venue must be told to MARGIN_BUY, not NO_SIDE_EFFECT"


def test_WITHOUT_BORROW_THE_CLAMP_STILL_BINDS_ON_MARGIN() -> None:
    """Leverage is opt-in per leg. A margin connector is not a licence to spend cash it lacks."""
    v = _MarginVenue()
    out = P.place_entry(v, "BTCUSDT", 500.0, cycle="20260815", quote="USDC",
                        free_quote=100.0, min_notional=5.0, borrow=False)
    assert out.placed and out.usd == 100.0 and "CLAMPED" in out.why
    assert v.borrowed == [False]


def test_BORROW_ON_A_SPOT_CONNECTOR_IS_REFUSED_BEFORE_ANYTHING_IS_SENT() -> None:
    """Spot is 1x by construction. Routing a levered size there would clamp it to free cash and
    fill -- a leg that looks successful while carrying a fraction of its intended exposure, which
    is the quietest way to be wrong about a position."""
    v = _Venue()
    out = P.place_entry(v, "BTCUSDT", 500.0, cycle="20260815", quote="USDC",
                        free_quote=100.0, min_notional=5.0, borrow=True)
    assert not out.placed and "BORROW REQUESTED" in out.why
    assert v.orders == [], "nothing may reach the venue once the mismatch is known"


def test_THE_RAIL_STILL_OUTRANKS_A_BORROWING_LEG(monkeypatch: pytest.MonkeyPatch) -> None:
    """Leverage does not buy an exemption from the ruin rails, and the rail is checked FIRST --
    before arming, before the borrow capability, before any sizing."""
    monkeypatch.setattr("libs.execution.ruin_rail.frozen", lambda root=None: (True, "KILL latched"))
    v = _MarginVenue()
    out = P.place_entry(v, "BTCUSDT", 500.0, cycle="20260815", quote="USDC",
                        free_quote=1e9, min_notional=5.0, borrow=True)
    assert not out.placed and "RUIN RAIL LATCHED" in out.why
    assert v.orders == []


def test_A_DRY_RUN_SAYS_IT_WOULD_BORROW() -> None:
    v = _MarginVenue()
    out = P.place_entry(v, "BTCUSDT", 500.0, cycle="20260815", quote="USDC",
                        free_quote=100.0, min_notional=5.0, borrow=True, place=False)
    assert not out.placed and "MARGIN_BUY" in out.why and v.orders == []


# --------------------------------------------------------------- side, and the day it inverted
def test_A_SELL_IS_REFUSED_AND_NEVER_SENT_AS_A_BUY() -> None:
    """MEASURED LIVE ON THE PRINCIPAL'S ACCOUNT, 2026-08-15. `run_discretionary_live` refused
    shorts only under --spot-only. Run without that flag against the margin wallet, two SELL
    signals reached place_entry and were placed as BUYS -- the opposite of the trade the rule
    called -- with stops sized for a short resting ABOVE the market where they protect nothing.
    Every printed line read TAKE.

    The caller's guard was a FLAG, which is an instruction to whoever types the command. This is
    the mechanism, and it binds on every wallet."""
    v = _MarginVenue()
    out = P.place_entry(v, "BTCUSDT", 100.0, cycle="20260815", quote="USDC",
                        free_quote=1e9, min_notional=5.0, side="SELL")
    assert not out.placed and "LONGS ONLY" in out.why
    assert out.side == "SELL", "the refusal must report the side that was ASKED for"
    assert v.orders == [], "nothing may reach the venue"


def test_THE_SIDE_CHECK_OUTRANKS_EVERY_OTHER_GATE() -> None:
    """Checked before the rail, before arming, before sizing -- because an inverted order is wrong
    at every one of those stages and the earliest refusal is the clearest one."""
    for free, minn in ((0.0, 5.0), (1e9, 1e9)):
        out = P.place_entry(_Venue(armed=False), "BTCUSDT", 100.0, cycle="c", quote="USDC",
                            free_quote=free, min_notional=minn, side="SELL")
        assert "LONGS ONLY" in out.why, "the side refusal must not be masked by another gate"


def test_BUY_IS_UNAFFECTED_AND_CASE_IS_NOT_A_LOOPHOLE() -> None:
    v = _Venue()
    assert P.place_entry(v, "BTCUSDT", 50.0, cycle="c", quote="USDC",
                         free_quote=1e9, min_notional=5.0, side="BUY").placed
    assert P.place_entry(v, "BTCUSDT", 50.0, cycle="c", quote="USDC",
                         free_quote=1e9, min_notional=5.0, side="buy").placed
    for bad in ("Sell", "SHORT", "", "sel"):
        out = P.place_entry(v, "BTCUSDT", 50.0, cycle="c", quote="USDC",
                            free_quote=1e9, min_notional=5.0, side=bad)
        assert not out.placed, f"side={bad!r} must not reach the venue"
