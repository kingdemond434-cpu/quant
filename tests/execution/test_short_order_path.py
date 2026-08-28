"""THE SHORT PATH -- every way a short is NOT a mirrored long, pinned as a refusal.

The happy path is two orders. What ends an account is the stop on the wrong side, a gross cap
borrowed from the long book, or a fill with no stop behind it -- and on a short the loss above is
unbounded, so there is no natural floor to catch any of them.
"""

from __future__ import annotations

from typing import Any

import pytest

from libs.execution import short_order_path as S


class _Margin:
    """Borrowing-wallet stub. Records the exact orders so a wrong SIDE is visible, not inferred."""

    SUPPORTS_BORROW = True
    MAX_SHORT_GROSS = 2.0

    def __init__(self, *, armed: bool = True, filled: float = 0.5,
                 entry_raises: bool = False, stop_raises: bool = False) -> None:
        self._armed, self._filled = armed, filled
        self._entry_raises, self._stop_raises = entry_raises, stop_raises
        self.market: list[tuple[str, str, float, bool]] = []
        self.stops: list[tuple[str, str, float, float, float]] = []

    @staticmethod
    def short_liquidation_distance(g: float) -> float:
        return (1.0 + g) / (1.1 * g) - 1.0

    def is_armed(self) -> tuple[bool, str]:
        return self._armed, "armed" if self._armed else "no keyfile"

    def place_market_quote(self, sym: str, side: str, usd: float, *, cycle: str,
                           borrow: bool = False) -> dict[str, Any]:
        if self._entry_raises:
            raise RuntimeError("venue rejected")
        self.market.append((sym, side, usd, borrow))
        return {"orderId": 1, "status": "FILLED", "executedQty": str(self._filled)}

    def place_stop_loss_limit(self, sym: str, side: str, qty: float, stop: float,
                              limit: float, *, cycle: str | None = None) -> dict[str, Any]:
        if self._stop_raises:
            raise RuntimeError("stop rejected")
        self.stops.append((sym, side, qty, stop, limit))
        return {"orderId": 2, "status": "NEW"}


@pytest.fixture(autouse=True)
def _clear_rail(monkeypatch: pytest.MonkeyPatch) -> None:
    """A TEST MAY NOT READ THE DESK'S LIVE RAIL STATE (found 2026-08-28).

    `data/CASHCARRY_KILL` has been latched on this box since 2026-08-01, and the rail is consulted
    FIRST by design -- so every test in this file was refused before its subject ever ran, and all
    16 reported the rail's message instead of the property they pin. They were red for as long as
    the desk was correctly frozen: a suite whose verdict flips with an operational latch is
    measuring the box, not the code.

    PATCHED ON THE MODULE THAT READS IT, WHICH IS NOT WHERE THE SIBLING PATCHES. `short_order_path`
    does `from ...ruin_rail import frozen` at module scope (line 57), so the name is bound at
    import and `monkeypatch.setattr("libs.execution.ruin_rail.frozen", ...)` -- exactly what
    tests/execution/test_spot_order_path.py does, correctly, because `spot_order_path` imports it
    INSIDE the function -- would be a silent no-op here. Two sibling order paths, two import
    styles, one fixture text that works on one and quietly does nothing on the other.

    So the patch is asserted rather than assumed: a fixture that can no-op silently is the exact
    class this suite exists to catch, and TestTheRailsStillBind is the positive control proving
    the rail still refuses when it is genuinely latched.
    """
    monkeypatch.setattr(S, "frozen", lambda *_a, **_k: (False, "clear"))
    assert S.frozen()[0] is False, "the rail patch did not take -- check how S imports frozen"


def _short(v: Any, **kw: Any) -> S.ShortOutcome:
    args: dict[str, Any] = {"cycle": "c1", "quote": "USDC", "equity_usd": 1000.0,
                            "entry_price": 100.0, "stop_price": 105.0,
                            "min_notional": 5.0, "step": 0.001}
    args.update(kw)
    return S.place_short_entry(v, "AAAUSDT", args.pop("usd", 100.0), **args)


class TestTheStopIsAboveTheEntry:
    """A stop below a short is a TAKE-PROFIT wearing a stop's name: it closes the winner and
    leaves the loser running, with nothing bounding the loss above."""

    def test_a_stop_below_entry_is_REFUSED_not_inverted(self) -> None:
        v = _Margin()
        out = _short(v, entry_price=100.0, stop_price=95.0)
        assert not out.placed
        assert "TAKE-PROFIT" in out.why
        assert v.market == [], "an inverted stop must stop the ENTRY, not just the stop"

    def test_a_stop_equal_to_entry_is_refused(self) -> None:
        assert not _short(_Margin(), entry_price=100.0, stop_price=100.0).placed

    def test_the_stop_order_is_a_BUY(self) -> None:
        # The closing leg of a short buys the borrowed asset back. A SELL stop would double it.
        v = _Margin()
        assert _short(v).placed
        assert v.stops[0][1] == "BUY"

    def test_the_stop_LIMIT_sits_ABOVE_the_trigger(self) -> None:
        # Exactly inverting the long path: a closing BUY needs room UPWARD to fill.
        v = _Margin()
        _short(v, stop_price=105.0)
        _sym, _side, _qty, stop, limit = v.stops[0]
        assert limit > stop, "a short's stop limit below its trigger cannot fill on a gap up"

    def test_a_stop_inside_the_minimum_gap_is_refused(self) -> None:
        out = _short(_Margin(), entry_price=100.0, stop_price=100.1)
        assert not out.placed and "minimum" in out.why


class TestTheEntryBorrowsTheBase:
    def test_the_entry_is_a_SELL_that_BORROWS(self) -> None:
        v = _Margin()
        assert _short(v).placed
        _sym, side, _usd, borrow = v.market[0]
        assert side == "SELL", "a short entry that BUYS is the opposite trade"
        assert borrow is True, "without MARGIN_BUY there is no base asset to sell"

    def test_a_wallet_that_cannot_borrow_is_refused(self) -> None:
        class _Spot:
            SUPPORTS_BORROW = False

            def is_armed(self) -> tuple[bool, str]:
                return True, "armed"

        out = _short(_Spot())
        assert not out.placed and "CANNOT BORROW" in out.why

    def test_an_unarmed_wallet_is_refused(self) -> None:
        assert not _short(_Margin(armed=False)).placed


class TestTheShortGrossCapIsNotTheLongs:
    """The call band starts at 2.00x gross for a short and 3.00x for a long. Sharing one constant
    would open every short already inside the band."""

    def test_the_cap_is_two_x_not_three(self) -> None:
        cap, why = S.max_short_notional(1000.0, _Margin())
        assert cap == pytest.approx(2000.0)
        assert "3.00x" in why, "the long's band must be stated beside it or the number reads loose"

    def test_the_cap_refuses_rather_than_clamps(self) -> None:
        v = _Margin()
        out = _short(v, usd=900.0, gross_open_usd=1500.0, equity_usd=1000.0)
        assert not out.placed and "GROSS CAP" in out.why
        assert v.market == [], "a silently shrunk short is a position nobody chose"

    def test_the_liquidation_distance_is_published_with_the_cap(self) -> None:
        # A headroom figure without its distance is the half that looks like opportunity.
        _cap, why = S.max_short_notional(1000.0, _Margin())
        assert "ADVERSE MOVE" in why

    def test_a_short_is_liquidated_SOONER_than_a_long_at_equal_gross(self) -> None:
        from libs.execution.binance_margin_live import (
            liquidation_distance,
            short_liquidation_distance,
        )
        for g in (1.5, 2.0, 3.0):
            assert short_liquidation_distance(g) < liquidation_distance(g), (
                f"at {g}x the short must be the tighter rail -- an adverse move GROWS a short's "
                "debt while a long's debt is fixed")


class TestRiskSizing:
    def test_a_wider_stop_gives_a_SMALLER_position(self) -> None:
        tight, _ = S.size_from_risk(1000.0, 100.0, 102.0, risk_frac=0.01)
        wide, _ = S.size_from_risk(1000.0, 100.0, 120.0, risk_frac=0.01)
        assert tight > wide
        assert tight == pytest.approx(1000.0 * 0.01 / 0.02)

    def test_an_inverted_stop_sizes_to_zero_with_a_reason(self) -> None:
        usd, why = S.size_from_risk(1000.0, 100.0, 95.0, risk_frac=0.01)
        assert usd == 0.0 and "TAKE-PROFIT" in why

    def test_a_stop_inside_the_minimum_gap_sizes_to_zero(self) -> None:
        usd, _ = S.size_from_risk(1000.0, 100.0, 100.1, risk_frac=0.01)
        assert usd == 0.0


class TestAFillWithoutAStopSaysSo:
    def test_a_failed_stop_reports_UNPROTECTED_and_unbounded(self) -> None:
        v = _Margin(stop_raises=True)
        out = _short(v)
        assert out.placed and not out.protected
        assert "UNBOUNDED" in out.why

    def test_a_zero_fill_does_not_claim_protection(self) -> None:
        v = _Margin(filled=0.0)
        out = _short(v)
        assert out.placed and not out.protected
        assert v.stops == [], "a stop for zero units protects nothing and may still be an order"

    def test_the_stop_quantity_rounds_DOWN_to_the_step(self) -> None:
        # The stop BUYS BACK what was sold. Rounding UP would buy more than was borrowed and leave
        # a residual LONG in an asset the desk never chose to hold.
        v = _Margin(filled=0.5678)
        _short(v, step=0.01)
        assert v.stops[0][2] == pytest.approx(0.56)

    def test_a_rejected_entry_places_no_stop(self) -> None:
        v = _Margin(entry_raises=True)
        out = _short(v)
        assert not out.placed and v.stops == []


class TestTheRailsStillBind:
    def test_a_latched_ruin_rail_refuses_before_anything_else(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(S, "frozen", lambda *_a, **_k: (True, "DEADMAN_FIRED"))
        v = _Margin()
        out = _short(v)
        assert not out.placed and "RUIN RAIL" in out.why
        assert v.market == []

    def test_dry_run_places_nothing(self) -> None:
        v = _Margin()
        out = _short(v, place=False)
        assert not out.placed and v.market == [] and v.stops == []
        assert "DRY RUN" in out.why
