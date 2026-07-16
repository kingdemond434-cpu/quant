"""Metrics engine — performance statistics from an equity curve and realized trades."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict

from libs.backtest.portfolio import Trade


class Metrics(BaseModel):
    """Performance metrics computed on NET equity."""

    model_config = ConfigDict(frozen=True)

    total_return: float
    cagr: float
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown: float
    volatility: float
    profit_factor: float
    expectancy: float
    n_trades: int
    win_rate: float


def compute_metrics(
    equity: pd.Series, trades: list[Trade], *, periods_per_year: float = 252.0
) -> Metrics:
    """Compute performance metrics from an equity curve and realized trades."""
    equity = equity.astype("float64")
    start = float(equity.iloc[0]) if len(equity) else 0.0
    last = float(equity.iloc[-1]) if len(equity) else 0.0
    total_return = (last / start - 1.0) if start > 0 else 0.0

    returns = equity.pct_change(fill_method=None).dropna()
    n = len(returns)
    ann = math.sqrt(periods_per_year)

    mean_r = float(returns.mean()) if n else 0.0
    std_r = float(returns.std(ddof=1)) if n >= 2 else 0.0
    sharpe = (mean_r / std_r * ann) if std_r > 0 else 0.0

    downside = returns[returns < 0]
    dstd = float(downside.std(ddof=1)) if len(downside) >= 2 else 0.0
    sortino = (mean_r / dstd * ann) if dstd > 0 else 0.0

    cagr = ((last / start) ** (periods_per_year / n) - 1.0) if (n > 0 and start > 0) else 0.0
    volatility = std_r * ann

    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    max_drawdown = float(drawdown.min()) if len(equity) else 0.0
    calmar = (cagr / abs(max_drawdown)) if max_drawdown < 0 else 0.0

    pnls = np.array([t.pnl for t in trades], dtype="float64")
    n_trades = len(pnls)
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gross_win = float(wins.sum())
    gross_loss = float(abs(losses.sum()))
    if gross_loss > 0:
        profit_factor = gross_win / gross_loss
    elif gross_win > 0:
        profit_factor = math.inf
    else:
        profit_factor = 0.0
    expectancy = float(pnls.mean()) if n_trades else 0.0
    win_rate = float(len(wins) / n_trades) if n_trades else 0.0

    return Metrics(
        total_return=total_return,
        cagr=cagr,
        sharpe=sharpe,
        sortino=sortino,
        calmar=calmar,
        max_drawdown=max_drawdown,
        volatility=volatility,
        profit_factor=profit_factor,
        expectancy=expectancy,
        n_trades=n_trades,
        win_rate=win_rate,
    )
