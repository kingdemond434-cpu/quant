"""Tests for the queue-position + latency maker-fill model (hftbacktest method)."""

from __future__ import annotations

import pytest

from libs.backtest.queue_fill import maker_fill


def test_full_fill_when_through_volume_clears_queue_and_size() -> None:
    f = maker_fill(order_size=10.0, queue_ahead=5.0, through_volume=20.0)
    assert f.queue_cleared
    assert f.filled_units == 10.0
    assert f.fill_fraction == 1.0
    assert bool(f) is True


def test_no_fill_when_queue_not_cleared() -> None:
    f = maker_fill(order_size=10.0, queue_ahead=50.0, through_volume=20.0)
    assert not f.queue_cleared
    assert f.filled_units == 0.0
    assert f.fill_fraction == 0.0
    assert bool(f) is False


def test_partial_fill_only_the_through_volume_past_the_queue() -> None:
    f = maker_fill(order_size=10.0, queue_ahead=5.0, through_volume=10.0)  # 5 units past the queue
    assert f.filled_units == 5.0
    assert f.fill_fraction == 0.5
    assert f.queue_cleared


def test_latency_eats_the_front_of_the_window() -> None:
    base = maker_fill(order_size=10.0, queue_ahead=0.0, through_volume=10.0, resting_window_s=1.0)
    delayed = maker_fill(
        order_size=10.0, queue_ahead=0.0, through_volume=10.0,
        feed_latency_s=0.5, resting_window_s=1.0,
    )
    assert base.filled_units == 10.0
    assert delayed.filled_units == pytest.approx(5.0)  # half the window lost to latency
    assert delayed.filled_units < base.filled_units


def test_latency_capped_at_full_window_gives_no_fill() -> None:
    f = maker_fill(
        order_size=10.0, queue_ahead=0.0, through_volume=10.0,
        feed_latency_s=5.0, resting_window_s=1.0,
    )
    assert f.filled_units == 0.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"order_size": 0.0, "queue_ahead": 1.0, "through_volume": 1.0},
        {"order_size": 1.0, "queue_ahead": -1.0, "through_volume": 1.0},
        {"order_size": 1.0, "queue_ahead": 1.0, "through_volume": -1.0},
        {"order_size": 1.0, "queue_ahead": 0.0, "through_volume": 1.0, "resting_window_s": 0.0},
    ],
)
def test_invalid_inputs_raise(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        maker_fill(**kwargs)
