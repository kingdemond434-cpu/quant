"""Market-data feeds for the runtime.

A ``Feed`` yields batches of :class:`SymbolObservation` (alpha votes + market state) for the signal
engine. ``ReplayFeed`` plays a deterministic, scripted sequence (demo/backtest/tests — fully
runnable offline). ``MT5Feed`` is the production adapter over a live terminal; it needs a
``signal_builder`` to turn bars into alpha votes (the strategy layer) and cannot run in a sandbox.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol

from app.mt5_adapter import Bar, MT5Adapter
from libs.signal_engine.engine import SymbolObservation
from libs.signal_engine.models import AlphaSignal, MarketState


class Feed(Protocol):
    """Yields the next batch of observations, or an empty list when exhausted."""

    def poll(self) -> list[SymbolObservation]: ...


class ReplayFeed:
    """Deterministic replay of scripted observation batches (offline; demo and tests)."""

    def __init__(self, ticks: Sequence[Sequence[SymbolObservation]]) -> None:
        self._ticks: list[list[SymbolObservation]] = [list(t) for t in ticks]
        self._index = 0

    @property
    def remaining(self) -> int:
        return len(self._ticks) - self._index

    def poll(self) -> list[SymbolObservation]:
        if self._index >= len(self._ticks):
            return []
        batch = self._ticks[self._index]
        self._index += 1
        return batch


# strategy layer: turns market state + recent bars into alpha votes for one symbol.
SignalBuilder = Callable[[MarketState, list[Bar]], list[AlphaSignal]]


class MT5Feed:  # pragma: no cover - requires a live MT5 terminal + a wired strategy layer
    """Production feed over a live MT5 terminal (data path built; strategy layer wired later)."""

    def __init__(
        self,
        adapter: MT5Adapter,
        symbols: Sequence[str],
        *,
        signal_builder: SignalBuilder | None = None,
        timeframe: str = "H1",
        bars: int = 500,
    ) -> None:
        self._adapter = adapter
        self._symbols = list(symbols)
        self._signal_builder = signal_builder
        self._timeframe = timeframe
        self._bars = bars

    def poll(self) -> list[SymbolObservation]:
        if self._signal_builder is None:
            raise NotImplementedError(
                "MT5Feed requires a signal_builder (the alpha strategy layer) to convert bars into "
                "alpha votes; this is wired during Alpha Campaign 1."
            )
        observations: list[SymbolObservation] = []
        for symbol in self._symbols:
            history = self._adapter.fetch_bars(symbol, timeframe=self._timeframe, count=self._bars)
            state = MarketState(symbol=symbol)
            signals = self._signal_builder(state, history)
            if signals:
                observations.append(SymbolObservation(signals=signals, state=state))
        return observations
