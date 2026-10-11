"""A bracket crossed before entry is an unfilled signal, never a fabricated huge-R loss."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mt5desk.engine import Costs, Signal, run_backtest

from libs.validation import independent_replica, replay2


def _independent_replays(bars, signal):
    spec = independent_replica.Sig(signal.time, signal.side, signal.stop,
                                   signal.target, signal.ttl_bars)
    meta = {"tick_size": 0.0001, "median_spread_pts": 12, "contract_size": 1}
    return (replay2.replay(bars, [signal], cost_price_units=0.001),
            independent_replica.simulate(bars, [spec], meta))


@pytest.mark.parametrize("side", [1, -1])
@pytest.mark.parametrize("stop_case", ["equal", "roundoff", "crossed", "nan"])
def test_unexecutable_stop_keeps_signal_receipt_without_a_trade(side, stop_case):
    idx = pd.date_range("2026-06-01", periods=5, freq="15min", tz="UTC")
    bars = pd.DataFrame({"open": 0.82332, "high": 0.824, "low": 0.822,
                         "close": 0.82332}, index=idx)
    entry = 0.82332
    stop = {"equal": entry, "roundoff": np.nextafter(entry, entry - side),
            "crossed": entry + side * 0.0002, "nan": float("nan")}[stop_case]
    sig = Signal(time=idx[0], side=side, stop=stop, target=entry + side * 0.002,
                 ttl_bars=2, tag="retained_trial")
    result = run_backtest(bars, [sig], Costs())
    assert result.signal_count == 1 and result.n == 0
    assert len(result.geometry_rejections) == 1
    assert result.geometry_rejections[0]["tag"] == "retained_trial"
    assert result.geometry_rejections[0]["fill_time"] == str(idx[1])
    assert all(not fills for fills in _independent_replays(bars, sig))


def test_finite_costly_tight_stop_is_not_clipped_or_silently_rejected():
    idx = pd.date_range("2026-06-01", periods=5, freq="15min", tz="UTC")
    bars = pd.DataFrame({"open": 0.82332, "high": 0.824, "low": 0.822,
                         "close": 0.82332}, index=idx)
    sig = Signal(time=idx[0], side=1, stop=0.823319, target=0.825,
                 ttl_bars=2, tag="valid_tight_stop")
    result = run_backtest(bars, [sig], Costs())
    assert result.n == 1 and result.trades[0].r_multiple < -100
    assert result.geometry_rejections == []
    for fills in _independent_replays(bars, sig):
        assert len(fills) == 1 and np.isfinite(fills[0].r) and fills[0].r < -100


@pytest.mark.parametrize("side", [1, -1])
def test_already_crossed_target_is_not_a_new_trade(side):
    idx = pd.date_range("2026-06-01", periods=5, freq="15min", tz="UTC")
    bars = pd.DataFrame({"open": 1.0, "high": 1.1, "low": 0.9,
                         "close": 1.0}, index=idx)
    sig = Signal(time=idx[0], side=side, stop=1-side*0.01, target=1-side*0.005,
                 ttl_bars=2, tag="expired_bracket")
    result = run_backtest(bars, [sig], Costs())
    assert result.signal_count == 1 and result.n == 0
    assert len(result.geometry_rejections) == 1
    assert all(not fills for fills in _independent_replays(bars, sig))
