"""Queue-position + latency maker-fill model (method extracted from nkaz001/hftbacktest).

``libs.backtest.fills.FillEngine`` answers *at what price* a fill happens (slippage + commission).
It does NOT answer the prior question every maker strategy lives or dies on: **did the passive
order fill at all, and how much of it?** A post-only limit order joins the BACK of the queue at its
price level and fills only as same-side trades first consume the ``queue_ahead`` size in front of
it, then its own size (FIFO price-time priority) — and only after order latency puts it on the book.

hftbacktest models this on full L2/L3 tick data. This is a small, owned, reduced-form port of the
*mechanism* (queue priority + latency + partial fill) — enough to stop the backtest assuming a 100%
passive fill rate, which is a silent P&L lie for the maker-carry / cash-and-carry book (adversarial
finding: an over-optimistic maker fill rate manufactures edge that does not exist live).

Deliberately NOT modelled (documented, not hidden): book replenishment, cancellations ahead
shrinking the queue faster than trades, and price-level jumps. Use this for maker fill-rate realism,
not as an L3 HFT simulator.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class MakerFill(BaseModel):
    """Outcome of a passive order resting for one window."""

    model_config = ConfigDict(frozen=True)

    filled_units: float
    fill_fraction: float  # in [0, 1]: portion of the order that filled passively this window
    queue_cleared: bool  # did through-volume fully consume the queue ahead of the order?

    def __bool__(self) -> bool:
        return self.filled_units > 0.0


def maker_fill(
    *,
    order_size: float,
    queue_ahead: float,
    through_volume: float,
    feed_latency_s: float = 0.0,
    resting_window_s: float = 1.0,
) -> MakerFill:
    """Passive fill of ``order_size`` given ``queue_ahead`` units in front at the same level and
    ``through_volume`` units that traded at/through the level while the order rested.

    Latency eats the *front* of the resting window: trades arriving before the order is actually on
    the book — a ``feed_latency_s / resting_window_s`` fraction of ``through_volume`` — pass without
    ever queuing behind them. The order then fills only the through-volume that exceeds the queue
    ahead, capped at its own size. All sizes are in the same units (contracts or base qty).

    Raises:
        ValueError: on a non-positive ``order_size`` / ``resting_window_s`` or negative volumes.
    """
    if order_size <= 0.0:
        raise ValueError("order_size must be > 0")
    if queue_ahead < 0.0 or through_volume < 0.0:
        raise ValueError("queue_ahead and through_volume must be >= 0")
    if resting_window_s <= 0.0:
        raise ValueError("resting_window_s must be > 0")
    latency_frac = min(1.0, max(0.0, feed_latency_s / resting_window_s))
    effective_through = through_volume * (1.0 - latency_frac)
    past_queue = max(0.0, effective_through - queue_ahead)
    filled = min(order_size, past_queue)
    return MakerFill(
        filled_units=filled,
        fill_fraction=filled / order_size,
        queue_cleared=effective_through >= queue_ahead,
    )
