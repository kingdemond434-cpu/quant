"""Pre-registered Campaign 1 strategies — shape, determinism, no-lookahead."""

from __future__ import annotations

import numpy as np

from app.signal_builder import (
    STRATEGIES,
    Bars,
    momentum_positions,
    strategy_returns,
    trend_positions,
)


def _trending_bars(n: int = 400) -> Bars:
    close = np.linspace(100.0, 140.0, n) + np.sin(np.linspace(0, 20, n))
    high = close + 0.5
    low = close - 0.5
    return Bars(close=close, high=high, low=low)


def test_positions_are_ternary_and_right_length() -> None:
    bars = _trending_bars()
    for name, (fn, _mech, _why) in STRATEGIES.items():
        pos = fn(bars)
        assert len(pos) == len(bars), name
        assert set(np.unique(pos)).issubset({-1.0, 0.0, 1.0}), name


def test_trend_and_momentum_go_long_in_uptrend() -> None:
    bars = _trending_bars()
    assert trend_positions(bars)[-1] == 1.0
    assert momentum_positions(bars)[-1] == 1.0


def test_strategy_returns_have_no_lookahead() -> None:
    bars = _trending_bars()
    pos = trend_positions(bars)
    rets = strategy_returns(bars, pos)
    # one shorter than bars (first bar has no prior), and finite/deterministic
    assert len(rets) == len(bars) - 1
    assert np.all(np.isfinite(rets))
    # changing only the LAST bar must not change any earlier return (causality)
    bars2 = Bars(close=bars.close.copy(), high=bars.high.copy(), low=bars.low.copy())
    bars2.close[-1] *= 1.05
    rets2 = strategy_returns(bars2, trend_positions(bars2))
    assert np.allclose(rets[:-2], rets2[:-2])


def test_deterministic() -> None:
    bars = _trending_bars()
    assert np.array_equal(trend_positions(bars), trend_positions(bars))
