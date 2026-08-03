"""IMPACT MEASURED ON THE RECORDED BOOK BEATS IMPACT ASSUMED FROM A FORMULA.

The desk already had a square-root participation model with literature coefficients. It also had
8.2GB of its own L2 depth, which the model never touched. These tests pin the arithmetic that
replaces the assumption, and the guards that stop a torn snapshot from producing an exciting
number.

The sign convention gets its own test because a slippage that flips sign with direction is how a
book ends up looking profitable to trade into, and it would be believed.
"""

from __future__ import annotations

import numpy as np
import pytest

from libs.execution.book_walk import (
    BookSide,
    book_from_row,
    calibrate_impact,
    capacity_at_impact,
    fill_probability,
    walk_book,
)


def _asks(n: int = 10, top: float = 100.0, tick: float = 0.01, size: float = 1.0) -> BookSide:
    return BookSide(np.array([top + i * tick for i in range(n)]), np.full(n, size))


def _bids(n: int = 10, top: float = 99.99, tick: float = 0.01, size: float = 1.0) -> BookSide:
    return BookSide(np.array([top - i * tick for i in range(n)]), np.full(n, size))


# ------------------------------------------------------------------- parsing

def test_both_recorder_schemas_parse() -> None:
    """Binance stamps depth k='d' with b/a; Bybit uses k='depth'. Reading one and not the other
    returns clean, plausible, half-empty results over the other venue's archive -- the bug that
    made moat_mine blind to 4.4GB."""
    for kind in ("d", "depth"):
        row = {"k": kind, "t": 1, "b": [["99.9", "2"]], "a": [["100.1", "3"]]}
        parsed = book_from_row(row)
        assert parsed is not None, kind
        bids, asks = parsed
        assert bids.price[0] == 99.9 and asks.price[0] == 100.1


def test_a_crossed_book_is_dropped() -> None:
    """bid >= ask is physically impossible and means a torn snapshot. Walking it yields NEGATIVE
    slippage -- 'the venue pays us to trade' -- which is exactly the artifact that survives review
    because it is exciting."""
    assert book_from_row({"k": "d", "b": [["101", "1"]], "a": [["100", "1"]]}) is None


def test_levels_are_sorted_not_trusted() -> None:
    """Every consumer indexes [0] as the touch. A tape that is merely USUALLY sorted produces a
    finding that looks like microstructure and is a parse bug."""
    bids, asks = book_from_row(
        {"k": "d", "b": [["98", "1"], ["99", "1"]], "a": [["102", "1"], ["101", "1"]]})
    assert bids.price[0] == 99.0
    assert asks.price[0] == 101.0


def test_a_malformed_level_is_skipped_not_guessed() -> None:
    parsed = book_from_row({"k": "d", "b": [["99", "1"], ["bad"]], "a": [["100", "1"]]})
    assert parsed is not None
    assert len(parsed[0]) == 1


def test_a_non_depth_row_returns_none() -> None:
    assert book_from_row({"k": "t", "p": "100", "q": "1"}) is None


# ---------------------------------------------------------------- the walk

def test_an_order_inside_the_touch_pays_no_slippage() -> None:
    r = walk_book(_asks(), qty=0.5, is_buy=True)
    assert r.slippage_bps == pytest.approx(0.0)
    assert r.levels_consumed == 1
    assert r.complete


def test_walking_deeper_costs_more() -> None:
    small = walk_book(_asks(), qty=1.0, is_buy=True).slippage_bps
    large = walk_book(_asks(), qty=8.0, is_buy=True).slippage_bps
    assert large > small > -1e-9


def test_the_vwap_is_the_actual_weighted_price() -> None:
    """Three units against 1@100.00, 1@100.01, 1@100.02."""
    r = walk_book(_asks(), qty=3.0, is_buy=True)
    assert r.vwap == pytest.approx((100.00 + 100.01 + 100.02) / 3)
    assert r.filled == pytest.approx(3.0)


def test_slippage_is_a_cost_in_both_directions() -> None:
    """A convention that flips sign with direction makes selling into a book look profitable, and
    it would be believed because the number is positive."""
    buy = walk_book(_asks(), qty=5.0, is_buy=True).slippage_bps
    sell = walk_book(_bids(), qty=5.0, is_buy=False).slippage_bps
    assert buy > 0 and sell > 0


def test_an_order_larger_than_the_book_is_flagged_exhausted() -> None:
    """Silently filling the remainder at the last price would understate the cost of the size the
    desk could NOT execute -- which is the size that matters for capacity."""
    r = walk_book(_asks(n=5), qty=50.0, is_buy=True)
    assert r.exhausted
    assert not r.complete
    assert r.filled == pytest.approx(5.0)


def test_an_empty_book_is_refused_rather_than_filled() -> None:
    with pytest.raises(ValueError, match="empty book"):
        walk_book(BookSide(np.empty(0), np.empty(0)), qty=1.0, is_buy=True)


def test_a_nonpositive_order_is_refused() -> None:
    with pytest.raises(ValueError, match="qty must be positive"):
        walk_book(_asks(), qty=0.0, is_buy=True)


# ----------------------------------------------------------------- capacity

def test_capacity_respects_the_impact_budget() -> None:
    """The number that sizes a strategy: an alpha with a 30bp edge and 5bp of capacity at the size
    it needs is not an alpha."""
    cap = capacity_at_impact(_asks(n=50), max_bps=1.0, is_buy=True)
    assert cap > 0
    assert walk_book(_asks(n=50), qty=cap, is_buy=True).slippage_bps <= 1.0 + 1e-6


def test_a_tighter_budget_gives_less_capacity() -> None:
    book = _asks(n=50)
    assert (capacity_at_impact(book, max_bps=0.5) <= capacity_at_impact(book, max_bps=5.0))


def test_a_deep_book_carries_more_than_a_thin_one() -> None:
    deep = capacity_at_impact(_asks(n=50, size=10.0), max_bps=2.0)
    thin = capacity_at_impact(_asks(n=50, size=0.1), max_bps=2.0)
    assert deep > thin


def test_an_empty_book_has_zero_capacity() -> None:
    assert capacity_at_impact(BookSide(np.empty(0), np.empty(0)), max_bps=10.0) == 0.0


# -------------------------------------------------------------- calibration

def test_the_coefficient_is_fitted_from_the_books_themselves() -> None:
    books = [_asks(n=40, size=1.0 + i / 10) for i in range(30)]
    sizes = [2.0 + i for i in range(30)]
    fit = calibrate_impact(books, sizes)
    assert np.isfinite(fit["k"]) and fit["k"] > 0
    assert fit["n"] == 30


def test_a_thin_sample_refuses_to_produce_a_coefficient() -> None:
    """A number gets used because it exists. Eight snapshots cannot support one."""
    fit = calibrate_impact([_asks() for _ in range(3)], [1.0, 2.0, 3.0])
    assert np.isnan(fit["k"])
    assert "noise" in fit["note"]


def test_fit_quality_is_reported_alongside_the_coefficient() -> None:
    """r2 is returned so a bad fit is visible, rather than a coefficient being trusted because it
    was produced."""
    fit = calibrate_impact([_asks(n=40) for _ in range(20)], [float(i + 1) for i in range(20)])
    assert "r2" in fit


# ------------------------------------------------------- queue fill probability

def test_you_fill_NOTHING_until_the_queue_ahead_clears() -> None:
    """FIFO PRICE-TIME PRIORITY, AND MY FIRST VERSION GOT IT WRONG IN THE FLATTERING DIRECTION.

    I wrote `min(volume / need, 1)` -- 10 units trading against 100 ahead gave 0.1, implying a
    tenth of the order fills. It does not. Under price-time priority nothing fills until the
    queue in front is consumed; the answer is ZERO. A linear fraction manufactures partial maker
    fills that never happened, which is exactly how a passive strategy's backtest invents edge.

    The mechanism now lives in `libs/backtest/queue_fill.maker_fill`, which the desk already had
    and which I duplicated without checking -- it carries feed latency and partial fills my
    version simply lacked. Two implementations of one mechanism is worse than either alone,
    because the one that gets used is whichever the caller happened to import.
    """
    assert fill_probability(depth_ahead=100.0, traded_volume=10.0) == 0.0
    assert fill_probability(depth_ahead=100.0, traded_volume=500.0) == 1.0


def test_the_queue_ahead_comes_from_the_recorded_book() -> None:
    """The input the existing maker model could not know: how much size actually sits in front.
    That is a fact about the recorded book, which is what this module supplies."""
    from libs.execution.book_walk import queue_ahead_at
    asks = _asks(n=10, top=100.0, tick=0.01, size=2.0)
    assert queue_ahead_at(asks, 100.02, is_bid=False) == pytest.approx(6.0)
    assert queue_ahead_at(asks, 99.0, is_bid=False) == 0.0


def test_our_own_size_joins_the_queue() -> None:
    assert (fill_probability(depth_ahead=10.0, traded_volume=15.0, own_size=10.0)
            < fill_probability(depth_ahead=10.0, traded_volume=15.0))


def test_an_empty_queue_fills_certainly() -> None:
    assert fill_probability(depth_ahead=0.0, traded_volume=0.0) == 1.0


def test_negative_sizes_are_refused() -> None:
    with pytest.raises(ValueError, match="negative"):
        fill_probability(depth_ahead=-1.0, traded_volume=1.0)


def test_the_probability_is_documented_as_an_upper_bound() -> None:
    """Book replenishment, cancellations shrinking the queue and price-level jumps are documented
    as unmodelled in queue_fill, and all push the true figure DOWN. An execution assumption that
    errs generous must say which way it errs."""
    assert "UPPER BOUND" in fill_probability.__doc__


def test_it_delegates_rather_than_reimplementing() -> None:
    """One mechanism, one implementation. Two versions of a passive-fill model is worse than
    either alone: the one that gets used is whichever the caller happened to import."""
    import inspect

    from libs.execution import book_walk
    assert "maker_fill" in inspect.getsource(book_walk.fill_probability)
