"""Tests for order-book imbalance features (algotrading-example method)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from libs.research.microstructure import book_imbalance, depth_imbalance_signal


def test_book_imbalance_range_sign_and_empty_book() -> None:
    imb = book_imbalance(np.array([10.0, 5.0, 0.0]), np.array([0.0, 5.0, 0.0]))
    assert imb[0] == 1.0   # all bid -> +1
    assert imb[1] == 0.0   # balanced -> 0
    assert imb[2] == 0.0   # no resting book -> 0 (not NaN)
    assert np.all((imb >= -1.0) & (imb <= 1.0))


def test_book_imbalance_negative_when_ask_heavy() -> None:
    assert book_imbalance(np.array([1.0]), np.array([3.0]))[0] == -0.5


def test_depth_imbalance_signal_smoothes_and_is_lag_ready() -> None:
    idx = pd.date_range("2026-01-01", periods=5, freq="D", tz="UTC")
    bid = pd.DataFrame({"A": [10.0, 10.0, 10.0, 10.0, 10.0]}, index=idx)
    ask = pd.DataFrame({"A": [10.0, 10.0, 10.0, 10.0, 10.0]}, index=idx)
    sig = depth_imbalance_signal(bid, ask, lookback=2)
    assert sig["A"].iloc[-1] == 0.0     # balanced book -> 0 imbalance
    assert np.isnan(sig["A"].iloc[0])   # rolling(2) leaves the first bar undefined


def test_lookback_validation() -> None:
    with pytest.raises(ValueError):
        depth_imbalance_signal(pd.DataFrame({"A": [1.0]}), pd.DataFrame({"A": [1.0]}), lookback=0)
