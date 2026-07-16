"""``libs.backtest`` — the event-driven, cost-aware backtest engine + cross-engine verification.

Event queue -> order manager -> fill engine -> portfolio engine -> metrics engine. Supports
long/short, stop-loss, take-profit, trailing stop, partial exits, and portfolio accounting.
Results are cross-checked against an independent NumPy reference (always) and backtrader /
vectorbt (when installed).
"""

from __future__ import annotations

from libs.backtest.cross_engine import (
    reference_from_backtrader,
    reference_from_vectorbt,
    summarize_result,
    vectorized_reference,
    verify_against_backtrader,
    verify_against_vectorbt,
    verify_against_vectorized,
    verify_cross_engine,
)
from libs.backtest.engine import Backtest, BacktestConfig, BacktestResult, run_signal_backtest
from libs.backtest.errors import BacktestError, VerificationError
from libs.backtest.events import (
    EventQueue,
    EventType,
    FillEvent,
    MarketEvent,
    OrderEvent,
    SignalEvent,
)
from libs.backtest.fills import FillEngine
from libs.backtest.metrics import Metrics, compute_metrics
from libs.backtest.orders import OrderManager, ProtectiveState
from libs.backtest.portfolio import PortfolioEngine, Trade
from libs.backtest.strategy import (
    BarContext,
    MovingAverageCrossStrategy,
    SignalStrategy,
    Strategy,
)

__all__ = [  # noqa: RUF022  # grouped by concern
    # engine
    "Backtest",
    "BacktestConfig",
    "BacktestResult",
    "run_signal_backtest",
    # components
    "EventQueue",
    "EventType",
    "MarketEvent",
    "SignalEvent",
    "OrderEvent",
    "FillEvent",
    "FillEngine",
    "OrderManager",
    "ProtectiveState",
    "PortfolioEngine",
    "Trade",
    "Metrics",
    "compute_metrics",
    # strategy
    "Strategy",
    "BarContext",
    "SignalStrategy",
    "MovingAverageCrossStrategy",
    # cross-engine verification
    "verify_cross_engine",
    "vectorized_reference",
    "summarize_result",
    "verify_against_vectorized",
    "reference_from_backtrader",
    "verify_against_backtrader",
    "reference_from_vectorbt",
    "verify_against_vectorbt",
    # errors
    "BacktestError",
    "VerificationError",
]
