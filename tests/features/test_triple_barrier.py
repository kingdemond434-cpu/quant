"""Tests for triple-barrier labels (López de Prado / mlfinlab method, owned port)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from libs.features.errors import FeatureError
from libs.features.labels import triple_barrier_labels


def _series(values: list[float]) -> pd.Series:
    return pd.Series(values, dtype="float64")


def test_upper_barrier_touched_first_labels_plus_one() -> None:
    close = _series([100.0, 101.0, 103.0, 100.0])  # +3% by bar 2, before any -2%
    lab = triple_barrier_labels(close, horizon=3, upper=0.02, lower=0.02)
    assert lab.iloc[0] == 1.0


def test_lower_barrier_touched_first_labels_minus_one() -> None:
    close = _series([100.0, 99.0, 97.0, 100.0])  # -3% by bar 2
    lab = triple_barrier_labels(close, horizon=3, upper=0.02, lower=0.02)
    assert lab.iloc[0] == -1.0


def test_vertical_barrier_no_touch_labels_zero() -> None:
    close = _series([100.0, 100.5, 100.2, 100.3, 100.1])  # never moves 5%
    lab = triple_barrier_labels(close, horizon=3, upper=0.05, lower=0.05)
    assert lab.iloc[0] == 0.0


def test_truncated_forward_path_is_nan_not_zero() -> None:
    close = _series([100.0, 100.1])  # bar 0's 3-bar path is truncated and touches nothing
    lab = triple_barrier_labels(close, horizon=3, upper=0.05, lower=0.05)
    assert np.isnan(lab.iloc[0])   # undetermined, never a fabricated 0
    assert np.isnan(lab.iloc[-1])  # last bar has no forward bar at all


def test_vol_scaling_widens_the_barriers() -> None:
    close = _series([100.0, 101.0, 100.0, 100.0])  # +1% at bar 1
    tight = triple_barrier_labels(
        close, horizon=3, upper=1.0, lower=1.0, vol=_series([0.005] * 4)
    )  # 0.5% barrier -> the +1% move touches it
    wide = triple_barrier_labels(
        close, horizon=3, upper=1.0, lower=1.0, vol=_series([0.05] * 4)
    )  # 5% barrier -> the +1% move does not
    assert tight.iloc[0] == 1.0
    assert wide.iloc[0] == 0.0


def test_invalid_arguments_raise() -> None:
    with pytest.raises(FeatureError):
        triple_barrier_labels(_series([100.0, 101.0]), horizon=0, upper=0.02, lower=0.02)
    with pytest.raises(FeatureError):
        triple_barrier_labels(_series([100.0, 101.0]), horizon=1, upper=0.0, lower=0.02)
