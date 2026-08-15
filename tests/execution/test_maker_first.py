"""MAKER-FIRST ROUTING -- the failure modes, not the happy path.

The happy path of "quote, wait, cross the rest" is three lines and nobody gets it wrong. What kills
an account is the double-place: a quote whose state is unknown, crossed on top of, leaving twice the
intended position and on margin twice the borrow. Most of this file is that one question.
"""

from __future__ import annotations

from typing import Any

import pytest

from libs.execution import maker_first as mf


class _Venue:
    """A connector stub. Records every call so a duplicate placement is visible, not inferred."""

    SUPPORTS_BORROW = True

    def __init__(self, *, bid: float = 100.0, ask: float = 100.1,
                 maker_filled_qty: float = 0.0, maker_raises: bool = False,
                 cancel_raises: bool = False, status: dict[str, Any] | None = None,
                 status_raises: bool = False, book_raises: bool = False) -> None:
        self.bid, self.ask = bid, ask
        self.maker_filled_qty = maker_filled_qty
        self.maker_raises = maker_raises
        self.cancel_raises = cancel_raises
        self.status = status
        self.status_raises = status_raises
        self.book_raises = book_raises
        self.market_calls: list[tuple[str, str, float]] = []
        self.maker_calls: list[tuple[str, str, float, float]] = []

    def book_ticker(self) -> dict[str, tuple[float, float]]:
        if self.book_raises:
            raise RuntimeError("book down")
        return {"AAAUSDC": (self.bid, self.ask)}

    def place_post_only(self, sym: str, side: str, qty: float, price: float,
                        **kw: Any) -> dict[str, Any]:
        if self.maker_raises:
            raise RuntimeError("-2010 Order would immediately match and take")
        self.maker_calls.append((sym, side, qty, price))
        return {"orderId": 42, "status": "NEW"}

    def cancel_order(self, sym: str, order_id: int | str) -> dict[str, Any]:
        if self.cancel_raises:
            raise RuntimeError("network")
        q = self.maker_filled_qty
        return {"orderId": order_id, "status": "CANCELED", "executedQty": str(q),
                "cummulativeQuoteQty": str(q * self.bid)}

    def order_status(self, sym: str, order_id: int | str) -> dict[str, Any]:
        if self.status_raises:
            raise RuntimeError("network")
        return self.status or {"status": "NEW", "executedQty": "0"}

    def place_market_quote(self, sym: str, side: str, usd: float, **kw: Any) -> dict[str, Any]:
        self.market_calls.append((sym, side, usd))
        return {"orderId": 99, "status": "FILLED", "executedQty": str(usd / self.ask),
                "cummulativeQuoteQty": str(usd)}


def _run(v: _Venue, usd: float = 100.0, **kw: Any) -> mf.MakerOutcome:
    return mf.maker_first_buy(v, "AAAUSDC", usd, cycle="c1", min_notional=5.0,
                              step=0.001, tick=0.01, sleep=lambda _s: None, **kw)


class TestTheDoublePlace:
    """An unresolved quote must never be crossed on top of. This is the whole file."""

    def test_unreadable_cancel_and_status_places_nothing_more(self) -> None:
        v = _Venue(cancel_raises=True, status_raises=True)
        out = _run(v)
        assert out.mode == "UNRESOLVED"
        assert v.market_calls == [], "crossed on top of a quote whose state is unknown"

    def test_quote_still_resting_after_a_failed_cancel_is_not_crossed(self) -> None:
        # Cancel failed AND the venue says the order is still live. Crossing here doubles the leg.
        v = _Venue(cancel_raises=True,
                   status={"status": "PARTIALLY_FILLED", "executedQty": "0.3",
                           "cummulativeQuoteQty": "30.0"})
        out = _run(v)
        assert out.mode == "UNRESOLVED"
        assert v.market_calls == []
        assert out.maker_usd == pytest.approx(30.0)

    def test_a_cancel_that_failed_because_it_already_filled_does_not_cross(self) -> None:
        v = _Venue(cancel_raises=True,
                   status={"status": "FILLED", "executedQty": "1.0",
                           "cummulativeQuoteQty": "100.0"})
        out = _run(v)
        assert out.mode == "maker"
        assert v.market_calls == []

    def test_no_order_id_means_no_fallback(self) -> None:
        v = _Venue()
        v.place_post_only = lambda *a, **k: {"status": "NEW"}      # type: ignore[method-assign]
        out = _run(v)
        assert out.mode == "UNRESOLVED"
        assert v.market_calls == []


class TestTheRemainder:
    """A partial maker fill must be topped up by the SHORTFALL, never by the whole order again."""

    def test_partial_fill_crosses_only_the_shortfall(self) -> None:
        v = _Venue(maker_filled_qty=0.4)          # 0.4 @ 100 = $40 of a $100 order
        out = _run(v, usd=100.0)
        assert out.mode == "taker_fallback"
        assert out.maker_usd == pytest.approx(40.0)
        assert len(v.market_calls) == 1
        assert v.market_calls[0][2] == pytest.approx(60.0)

    def test_unfilled_quote_crosses_the_whole_amount(self) -> None:
        v = _Venue(maker_filled_qty=0.0)
        out = _run(v, usd=100.0)
        assert out.mode == "taker_fallback"
        assert v.market_calls[0][2] == pytest.approx(100.0)

    def test_a_remainder_below_the_venue_minimum_is_not_crossed(self) -> None:
        v = _Venue(maker_filled_qty=0.97)         # $97 of $100; $3 left, below the $5 floor
        out = _run(v, usd=100.0)
        assert out.mode == "maker"
        assert v.market_calls == [], "paid a fee for $3 of noise"

    def test_filled_qty_sums_both_legs_so_the_stop_covers_the_position(self) -> None:
        # THE STOP IS SIZED FROM THIS. Reading either response alone leaves half the position naked.
        v = _Venue(maker_filled_qty=0.4)
        out = _run(v, usd=100.0)
        assert out.maker_qty == pytest.approx(0.4)
        assert out.taker_qty > 0
        assert out.filled_qty == pytest.approx(out.maker_qty + out.taker_qty)


class TestFallbacksAreOrdinary:
    """Routing to taker is a normal outcome. It must be NAMED, so a zero maker share is diagnosable
    rather than mysterious."""

    def test_connector_without_a_passive_path_crosses_and_says_so(self) -> None:
        class _Old:
            def __init__(self) -> None:
                self.calls: list[Any] = []

            def place_market_quote(self, sym: str, side: str, usd: float,
                                   **kw: Any) -> dict[str, Any]:
                self.calls.append(usd)
                return {"executedQty": "1.0"}

        old = _Old()
        out = mf.maker_first_buy(old, "AAAUSDC", 50.0, cycle="c", min_notional=5.0,
                                 sleep=lambda _s: None)
        assert out.mode == "taker"
        assert "no passive path" in out.why
        assert old.calls == [50.0]

    def test_unreadable_book_crosses(self) -> None:
        v = _Venue(book_raises=True)
        out = _run(v)
        assert out.mode == "taker"
        assert len(v.market_calls) == 1

    def test_crossed_quote_rejection_falls_back(self) -> None:
        v = _Venue(maker_raises=True)
        out = _run(v)
        assert out.mode == "taker"
        assert "would have crossed" in out.why
        assert len(v.market_calls) == 1

    def test_size_below_the_minimum_in_base_units_crosses(self) -> None:
        # A quote-sized MARKET order can express $6; a lot-stepped LIMIT at step=1.0 cannot.
        v = _Venue(bid=100.0, ask=100.1)
        out = mf.maker_first_buy(v, "AAAUSDC", 6.0, cycle="c", min_notional=5.0,
                                 step=1.0, tick=0.01, sleep=lambda _s: None)
        assert out.mode == "taker"
        assert v.maker_calls == []
        assert len(v.market_calls) == 1


class TestTheQuotePrice:
    def test_a_buy_quotes_at_the_bid_never_the_ask(self) -> None:
        v = _Venue(bid=100.0, ask=100.1)
        _run(v)
        assert v.maker_calls[0][3] == pytest.approx(100.0), "quoted at the ask -- that is a taker"

    def test_the_price_is_rounded_DOWN_to_the_tick(self) -> None:
        # Rounding UP could lift the bid through the ask, and LIMIT_MAKER rejects a crossing quote.
        v = _Venue(bid=100.077, ask=100.1)
        mf.maker_first_buy(v, "AAAUSDC", 100.0, cycle="c", min_notional=5.0,
                           step=0.001, tick=0.05, sleep=lambda _s: None)
        assert v.maker_calls[0][3] == pytest.approx(100.05)
        assert v.maker_calls[0][3] <= 100.077


class _ReduceVenue(_Venue):
    """The closing mirror. Adds the margin reduce path so AUTO_REPAY can be asserted."""

    def __init__(self, **kw: Any) -> None:
        super().__init__(**kw)
        self.reduce_calls: list[tuple[str, str, float]] = []
        self.post_only_kw: list[dict[str, Any]] = []

    def place_post_only(self, sym: str, side: str, qty: float, price: float,
                        **kw: Any) -> dict[str, Any]:
        self.post_only_kw.append(dict(kw))
        return super().place_post_only(sym, side, qty, price, **kw)

    def place_market_reduce(self, sym: str, side: str, qty: float, **kw: Any) -> dict[str, Any]:
        self.reduce_calls.append((sym, side, qty))
        return {"orderId": 7, "status": "FILLED", "executedQty": str(qty)}


def _reduce(v: _Venue, qty: float = 1.0, **kw: Any) -> mf.MakerOutcome:
    return mf.maker_first_reduce(v, "AAAUSDC", qty, cycle="c1", min_notional=5.0,
                                 step=0.001, tick=0.01, mark=100.0,
                                 sleep=lambda _s: None, **kw)


class TestTheReduceLeg:
    """The exit was still crossing after the first pass -- half a spread saving described as a
    spread saving. These pin the sell-side mirror, whose failure mode is worse than the buy's."""

    def test_a_sell_quotes_at_the_ASK_never_the_bid(self) -> None:
        v = _ReduceVenue(bid=100.0, ask=100.1)
        _reduce(v)
        assert v.maker_calls[0][3] == pytest.approx(100.1), "quoted at the bid -- that is a taker"
        assert v.maker_calls[0][1] == "SELL"

    def test_the_sell_price_rounds_UP_to_the_tick(self) -> None:
        # Rounding DOWN would drop the offer into the spread, where LIMIT_MAKER is rejected.
        v = _ReduceVenue(bid=99.0, ask=100.023)
        mf.maker_first_reduce(v, "AAAUSDC", 1.0, cycle="c", min_notional=5.0,
                              step=0.001, tick=0.05, mark=100.0, sleep=lambda _s: None)
        assert v.maker_calls[0][3] == pytest.approx(100.05)
        assert v.maker_calls[0][3] >= 100.023

    def test_the_passive_close_carries_AUTO_REPAY(self) -> None:
        # A close that removes the asset and leaves the loan has kept the debt and lost the
        # collateral behind it. The market fallback hard-codes AUTO_REPAY; so must the quote.
        v = _ReduceVenue()
        _reduce(v)
        assert v.post_only_kw[0].get("repay") is True

    def test_it_closes_through_the_REDUCE_path_not_a_plain_sell(self) -> None:
        v = _ReduceVenue(maker_filled_qty=0.0)
        _reduce(v, qty=1.0)
        assert v.reduce_calls and v.reduce_calls[0][1] == "SELL"
        assert v.market_calls == [], "a plain market sell leaves the debt behind"

    def test_partial_fill_crosses_only_the_UNSOLD_units(self) -> None:
        v = _ReduceVenue(maker_filled_qty=0.4)
        out = _reduce(v, qty=1.0)
        assert out.mode == "taker_fallback"
        assert out.maker_qty == pytest.approx(0.4)
        assert v.reduce_calls[0][2] == pytest.approx(0.6)

    def test_an_unresolved_quote_is_NEVER_oversold(self) -> None:
        # THE WORST CASE ON THIS BOOK. Selling the remainder on top of a live quote does not fail
        # on cross margin -- it borrows the base asset and OPENS A SHORT.
        v = _ReduceVenue(cancel_raises=True, status_raises=True)
        out = _reduce(v, qty=1.0)
        assert out.mode == "UNRESOLVED"
        assert v.reduce_calls == [] and v.market_calls == []

    def test_a_crossed_reduce_still_counts_toward_the_maker_share(self) -> None:
        # Without a mark price a crossed leg would carry taker_usd = 0 and vanish from the KPI,
        # which would report a high maker share for a book that crossed everything.
        v = _ReduceVenue(book_raises=True)
        out = _reduce(v, qty=1.0)
        assert out.mode == "taker"
        assert out.taker_usd == pytest.approx(100.0)
        assert mf.maker_share([out]) == pytest.approx(0.0)


class TestRoundStepUp:
    def test_it_ceilings_rather_than_flooring(self) -> None:
        assert mf.round_step_up(100.021, 0.05) == pytest.approx(100.05)
        assert mf.round_step_up(100.05, 0.05) == pytest.approx(100.05)

    def test_a_zero_step_is_a_passthrough(self) -> None:
        assert mf.round_step_up(100.0217, 0.0) == pytest.approx(100.0217)

    def test_no_binary_float_tail(self) -> None:
        # `math.ceil(x/step)*step` reproduces the 15th-decimal tail the venue rejected with 51077.
        v = mf.round_step_up(60.7, 0.1)
        assert repr(v) == repr(60.7) or v == pytest.approx(60.7, abs=1e-12)
        assert len(repr(v)) < 10, f"binary tail survived: {v!r}"


class TestMakerShare:
    def test_an_empty_book_is_None_not_zero(self) -> None:
        # L1.28a on a KPI: no legs is not a bad maker share, it is no measurement.
        assert mf.maker_share([]) is None

    def test_share_is_by_notional_not_by_leg(self) -> None:
        rows = [mf.MakerOutcome("A", "maker", 500.0, maker_usd=500.0),
                *(mf.MakerOutcome("B", "taker", 5.0, taker_usd=5.0) for _ in range(20))]
        # Twenty $5 taker legs against one $500 maker leg: by leg this is 4.8%, by dollars 83%.
        assert mf.maker_share(rows) == pytest.approx(0.8333, abs=1e-3)
