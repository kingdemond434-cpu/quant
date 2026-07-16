"""Event types and the event queue for the event-driven engine.

The loop flows MARKET -> SIGNAL -> ORDER -> FILL: each bar emits a market event, the strategy
turns it into a signal, the order manager into an order, and the fill engine into a fill the
portfolio consumes.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import StrEnum

import pandas as pd


class EventType(StrEnum):
    MARKET = "market"
    SIGNAL = "signal"
    ORDER = "order"
    FILL = "fill"


@dataclass(frozen=True)
class MarketEvent:
    index: int
    timestamp: pd.Timestamp
    open: float
    high: float
    low: float
    close: float
    volume: float
    type: EventType = EventType.MARKET


@dataclass(frozen=True)
class SignalEvent:
    timestamp: pd.Timestamp
    target: float  # desired position (units, or signed fraction of equity)
    stop_loss: float | None = None  # fraction of entry price
    take_profit: float | None = None  # fraction of entry price
    trailing: float | None = None  # fraction trailing stop
    type: EventType = EventType.SIGNAL


@dataclass(frozen=True)
class OrderEvent:
    timestamp: pd.Timestamp
    target_units: float
    reason: str
    type: EventType = EventType.ORDER


@dataclass(frozen=True)
class FillEvent:
    timestamp: pd.Timestamp
    units_delta: float
    price: float
    commission: float
    type: EventType = EventType.FILL


class EventQueue:
    """A FIFO queue of engine events."""

    def __init__(self) -> None:
        self._q: deque[object] = deque()

    def put(self, event: object) -> None:
        self._q.append(event)

    def get(self) -> object:
        return self._q.popleft()

    def empty(self) -> bool:
        return not self._q

    def __len__(self) -> int:
        return len(self._q)
