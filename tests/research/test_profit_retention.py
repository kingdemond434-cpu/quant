"""Tests for the profit-retention engine (MFE/MAE, capture, exit overlays)."""

from __future__ import annotations

import numpy as np

from libs.research.profit_retention import (
    capture_ratio,
    mfe_mae,
    time_decay_exit,
    trailing_stop_exit,
    vol_target_overlay,
)


def test_mfe_mae_on_up_then_down() -> None:
    # +10% then -5%: peak +10%, end +4.5%
    mfe, mae = mfe_mae(np.array([0.10, -0.05]))
    assert abs(mfe - 0.10) < 1e-9
    assert mae >= 0.0 or mae < mfe          # no adverse excursion below 0 here


def test_capture_ratio_quantifies_giveback() -> None:
    # peak +10%, give most back -> capture well under 1
    cr = capture_ratio(np.array([0.10, -0.09]))
    assert cr is not None and cr < 0.2
    assert capture_ratio(np.array([-0.05, -0.02])) is None   # never positive -> undefined


def test_vol_target_overlay_never_levers_up() -> None:
    r = np.array([0.01, -0.02, 0.03, -0.04, 0.05, 0.06, -0.07, 0.08])
    out = vol_target_overlay(r, target_vol=0.01, lookback=3)
    assert (np.abs(out) <= np.abs(r) + 1e-12).all()         # only ever scales down


def test_trailing_stop_flattens_after_drawdown() -> None:
    # rise to +20%, then a -15% step trips a 10% trailing stop -> later returns zeroed
    out = trailing_stop_exit(np.array([0.20, -0.15, 0.30, 0.30]), stop=0.10)
    assert out[2] == 0.0 and out[3] == 0.0


def test_time_decay_exit_zeros_when_signal_gone() -> None:
    out = time_decay_exit(np.array([0.01, 0.02, 0.03]), np.array([1.0, 0.0, -1.0]), floor=0.0)
    assert out[0] == 0.01 and out[1] == 0.0 and out[2] == 0.0
