"""Event-driven backtest engine.

Each bar: execute the order queued last bar at this bar's OPEN (no look-ahead), check
protective exits intrabar, mark equity at the close, then ask the strategy for a new target
which is queued for next bar. Sizing is in fixed ``units`` or signed ``fraction`` of equity.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from libs.backtest.errors import BacktestError
from libs.backtest.events import EventQueue, FillEvent, MarketEvent, OrderEvent, SignalEvent
from libs.backtest.fills import FillEngine
from libs.backtest.metrics import Metrics, compute_metrics
from libs.backtest.orders import OrderManager, ProtectiveState
from libs.backtest.portfolio import PortfolioEngine, Trade
from libs.backtest.strategy import BarContext, SignalStrategy, Strategy
from libs.data.schema import validate_bars


@dataclass(frozen=True)
class BacktestConfig:
    init_cash: float = 100_000.0
    sizing_mode: str = "fraction"  # "fraction" of equity, or fixed "units"
    slippage_frac: float = 0.0
    commission_per_unit: float = 0.0
    periods_per_year: float = 252.0


@dataclass(frozen=True)
class BacktestResult:
    equity: pd.Series
    trades: list[Trade]
    metrics: Metrics


class Backtest:
    """Runs an event-driven backtest of a strategy over a bar frame."""

    def __init__(self, config: BacktestConfig | None = None) -> None:
        self.config = config or BacktestConfig()
        if self.config.sizing_mode not in ("fraction", "units"):
            raise BacktestError("sizing_mode must be 'fraction' or 'units'")

    def _target_to_units(self, target: float, equity: float, price: float) -> float:
        if self.config.sizing_mode == "units":
            return target
        return target * equity / price if price > 0 else 0.0

    def run(self, bars: pd.DataFrame, strategy: Strategy) -> BacktestResult:
        validate_bars(bars, require_sorted=True)
        cfg = self.config
        portfolio = PortfolioEngine(init_cash=cfg.init_cash)
        fills = FillEngine(
            slippage_frac=cfg.slippage_frac, commission_per_unit=cfg.commission_per_unit
        )
        queue = EventQueue()

        protective: ProtectiveState | None = None
        pending_order: OrderEvent | None = None
        pending_signal: SignalEvent | None = None
        equity_index: list[pd.Timestamp] = []
        equity_values: list[float] = []

        records = bars.itertuples(index=False)
        for i, row in enumerate(records):
            ts = row.timestamp
            bar = MarketEvent(
                index=i, timestamp=ts, open=float(row.open), high=float(row.high),
                low=float(row.low), close=float(row.close), volume=float(row.volume),
            )
            queue.put(bar)

            # 1) execute the order queued on the previous bar, at this bar's open
            if pending_order is not None:
                delta = pending_order.target_units - portfolio.units
                if delta != 0.0:
                    portfolio.apply_fill(fills.fill(ts, delta, bar.open))
                protective = self._open_protective(portfolio, pending_signal, bar.open)
                pending_order = None
                pending_signal = None

            # 2) protective exits, intrabar
            if protective is not None and portfolio.units != 0.0:
                exit_price = OrderManager.check_protective(protective, bar)
                if exit_price is not None:
                    commission = abs(portfolio.units) * cfg.commission_per_unit
                    portfolio.apply_fill(
                        FillEvent(ts, -portfolio.units, exit_price, commission=commission)
                    )
                    protective = None

            # 3) mark to market at the close
            eq = portfolio.equity(bar.close)
            equity_index.append(ts)
            equity_values.append(eq)

            # 4) strategy decision (queued for next bar's open)
            ctx = BarContext(
                index=i, timestamp=ts, bars=bars, equity=eq, position_units=portfolio.units
            )
            signal = strategy.on_bar(ctx)
            if signal is not None:
                target_units = self._target_to_units(signal.target, eq, bar.close)
                if not math.isclose(target_units, portfolio.units, rel_tol=0.0, abs_tol=1e-12):
                    pending_order = OrderEvent(ts, target_units, reason="signal")
                    pending_signal = signal

        equity = pd.Series(equity_values, index=pd.DatetimeIndex(equity_index), name="equity")
        metrics = compute_metrics(equity, portfolio.trades, periods_per_year=cfg.periods_per_year)
        return BacktestResult(equity=equity, trades=portfolio.trades, metrics=metrics)

    @staticmethod
    def _open_protective(
        portfolio: PortfolioEngine, signal: SignalEvent | None, ref_price: float
    ) -> ProtectiveState | None:
        if portfolio.units == 0.0 or signal is None:
            return None
        if signal.stop_loss is None and signal.take_profit is None and signal.trailing is None:
            return None
        sign = 1 if portfolio.units > 0 else -1
        return ProtectiveState(
            entry_price=portfolio.entry_price,
            sign=sign,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            trailing=signal.trailing,
            anchor=ref_price,
        )


def run_signal_backtest(
    bars: pd.DataFrame,
    targets: list[float],
    *,
    init_cash: float = 100_000.0,
    periods_per_year: float = 252.0,
) -> BacktestResult:
    """Convenience: run a fixed-units, cost-free signal backtest (the cross-engine mode)."""
    config = BacktestConfig(
        init_cash=init_cash, sizing_mode="units", periods_per_year=periods_per_year
    )
    return Backtest(config).run(bars, SignalStrategy(targets))
