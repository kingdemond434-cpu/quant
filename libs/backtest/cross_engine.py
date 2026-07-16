"""Cross-engine verification.

A one-person event-driven engine *will* contain subtle P&L bugs (adversarial review W3.2), so
results are cross-checked against independent implementations. Three references are provided:

* :func:`vectorized_reference` — an in-house NumPy implementation (always available, strict).
* :func:`reference_from_backtrader` — backtrader (independent library; next-open fills).
* :func:`reference_from_vectorbt` — vectorbt (best-effort; looser tolerance).

:func:`verify_cross_engine` raises :class:`VerificationError` if any compared metric diverges
beyond tolerance.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

from libs.backtest.engine import BacktestResult, run_signal_backtest
from libs.backtest.errors import VerificationError

_SUMMARY_KEYS = ("total_return", "final_equity", "max_drawdown")


def _summary_from_equity(equity: np.ndarray) -> dict[str, float]:
    start = float(equity[0])
    last = float(equity[-1])
    running_max = np.maximum.accumulate(equity)
    drawdown = equity / running_max - 1.0
    return {
        "total_return": (last / start - 1.0) if start > 0 else 0.0,
        "final_equity": last,
        "max_drawdown": float(drawdown.min()),
    }


def summarize_result(result: BacktestResult) -> dict[str, float]:
    """Summarize an engine result into the comparable metric set."""
    return _summary_from_equity(result.equity.to_numpy(dtype="float64"))


def vectorized_reference(
    bars: pd.DataFrame, targets: Sequence[float], *, init_cash: float = 100_000.0
) -> dict[str, float]:
    """Independent NumPy reference for the fixed-units, next-open, cost-free signal model."""
    opens = bars["open"].to_numpy(dtype="float64")
    closes = bars["close"].to_numpy(dtype="float64")
    n = len(closes)
    positions = np.zeros(n, dtype="float64")
    if n > 1:
        positions[1:] = np.asarray(targets, dtype="float64")[: n - 1]
    deltas = np.diff(positions, prepend=0.0)
    cash = init_cash + np.cumsum(-deltas * opens)
    equity = cash + positions * closes
    return _summary_from_equity(equity)


def verify_cross_engine(
    ours: Mapping[str, float],
    reference: Mapping[str, float],
    *,
    keys: Sequence[str] = _SUMMARY_KEYS,
    tolerance: float = 1e-6,
    relative: bool = True,
) -> dict[str, float]:
    """Compare two metric sets; raise :class:`VerificationError` on divergence.

    Returns the per-key (relative) differences when within tolerance.
    """
    diffs: dict[str, float] = {}
    breaches: list[str] = []
    for key in keys:
        a = float(ours[key])
        b = float(reference[key])
        diff = abs(a - b)
        denom = max(abs(b), 1e-9) if relative else 1.0
        rel = diff / denom
        diffs[key] = rel
        if rel > tolerance:
            breaches.append(f"{key}: ours={a:.8g} ref={b:.8g} rel_diff={rel:.3g}")
    if breaches:
        raise VerificationError(
            "cross-engine divergence beyond tolerance "
            f"{tolerance:g}: " + "; ".join(breaches)
        )
    return diffs


def verify_against_vectorized(
    bars: pd.DataFrame,
    targets: Sequence[float],
    *,
    init_cash: float = 100_000.0,
    tolerance: float = 1e-9,
) -> dict[str, float]:
    """Run our engine and the NumPy reference on the same signals and verify they agree."""
    result = run_signal_backtest(bars, list(targets), init_cash=init_cash)
    ours = summarize_result(result)
    reference = vectorized_reference(bars, targets, init_cash=init_cash)
    return verify_cross_engine(ours, reference, tolerance=tolerance)


def reference_from_backtrader(
    bars: pd.DataFrame, targets: Sequence[float], *, init_cash: float = 100_000.0
) -> dict[str, float]:
    """Compute the comparable summary using backtrader (independent engine)."""
    import backtrader as bt

    frame = bars.copy()
    index = pd.DatetimeIndex(frame["timestamp"])
    if index.tz is not None:
        index = index.tz_convert("UTC").tz_localize(None)
    frame.index = index
    targets_list = list(targets)

    class _TargetStrategy(bt.Strategy):  # type: ignore[misc]
        def next(self) -> None:
            i = len(self) - 1
            if i < len(targets_list):
                self.order_target_size(target=targets_list[i])

    cerebro = bt.Cerebro(stdstats=False)
    cerebro.broker.setcash(init_cash)
    cerebro.broker.setcommission(commission=0.0)
    feed = bt.feeds.PandasData(dataname=frame[["open", "high", "low", "close", "volume"]])
    cerebro.adddata(feed)
    cerebro.addstrategy(_TargetStrategy)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="dd")
    strat = cerebro.run()[0]
    final_equity = float(cerebro.broker.getvalue())
    max_dd_pct = float(strat.analyzers.dd.get_analysis()["max"]["drawdown"])
    return {
        "total_return": final_equity / init_cash - 1.0,
        "final_equity": final_equity,
        "max_drawdown": -max_dd_pct / 100.0,
    }


def reference_from_vectorbt(
    bars: pd.DataFrame, targets: Sequence[float], *, init_cash: float = 100_000.0
) -> dict[str, float]:
    """Compute the comparable summary using vectorbt (best-effort; next-open fills)."""
    import vectorbt as vbt

    index = pd.DatetimeIndex(bars["timestamp"])
    close = pd.Series(bars["close"].to_numpy(dtype="float64"), index=index)
    fill_price = pd.Series(bars["open"].to_numpy(dtype="float64"), index=index).shift(-1)
    size = pd.Series(np.asarray(targets, dtype="float64"), index=index)
    portfolio = vbt.Portfolio.from_orders(
        close=close,
        size=size,
        size_type="targetamount",
        price=fill_price,
        fees=0.0,
        slippage=0.0,
        init_cash=init_cash,
        freq="1D",
    )
    equity = portfolio.value().to_numpy(dtype="float64")
    return _summary_from_equity(equity)


def verify_against_backtrader(
    bars: pd.DataFrame,
    targets: Sequence[float],
    *,
    init_cash: float = 100_000.0,
    tolerance: float = 1e-3,
) -> dict[str, float]:
    """Verify our engine against backtrader on the same signals."""
    result = run_signal_backtest(bars, list(targets), init_cash=init_cash)
    ours = summarize_result(result)
    reference = reference_from_backtrader(bars, targets, init_cash=init_cash)
    return verify_cross_engine(ours, reference, tolerance=tolerance)


def verify_against_vectorbt(
    bars: pd.DataFrame,
    targets: Sequence[float],
    *,
    init_cash: float = 100_000.0,
    tolerance: float = 5e-2,
) -> dict[str, float]:
    """Verify our engine against vectorbt on the same signals (looser tolerance)."""
    result = run_signal_backtest(bars, list(targets), init_cash=init_cash)
    ours = summarize_result(result)
    reference = reference_from_vectorbt(bars, targets, init_cash=init_cash)
    return verify_cross_engine(
        ours, reference, keys=("total_return", "final_equity"), tolerance=tolerance
    )
