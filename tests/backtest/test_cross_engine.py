"""Tests for cross-engine verification."""

from __future__ import annotations

import numpy as np
import pytest
from tests.backtest.conftest import make_bars

from libs.backtest.cross_engine import (
    verify_against_backtrader,
    verify_against_vectorbt,
    verify_against_vectorized,
    verify_cross_engine,
)
from libs.backtest.errors import VerificationError


def _targets(bars) -> list[float]:  # type: ignore[no-untyped-def]
    up = bars["close"].diff() > 0
    return np.where(up, 1.0, 0.0).tolist()


def test_verify_cross_engine_passes_when_close() -> None:
    ours = {"total_return": 0.10, "final_equity": 110_000.0, "max_drawdown": -0.05}
    reference = {"total_return": 0.10, "final_equity": 110_000.0, "max_drawdown": -0.05}
    diffs = verify_cross_engine(ours, reference)
    assert all(v == 0.0 for v in diffs.values())


def test_verify_cross_engine_raises_on_divergence() -> None:
    ours = {"total_return": 0.20, "final_equity": 120_000.0, "max_drawdown": -0.05}
    reference = {"total_return": 0.10, "final_equity": 110_000.0, "max_drawdown": -0.05}
    with pytest.raises(VerificationError):
        verify_cross_engine(ours, reference)


def test_engine_matches_numpy_reference_exactly() -> None:
    bars = make_bars(120, seed=3)
    diffs = verify_against_vectorized(bars, _targets(bars), tolerance=1e-9)
    assert max(diffs.values()) < 1e-9


@pytest.mark.filterwarnings("ignore")
def test_engine_matches_backtrader() -> None:
    pytest.importorskip("backtrader")
    bars = make_bars(120, seed=5)
    diffs = verify_against_backtrader(bars, _targets(bars), tolerance=1e-2)
    assert diffs["total_return"] < 1e-2


@pytest.mark.filterwarnings("ignore")
def test_engine_matches_vectorbt() -> None:
    pytest.importorskip("vectorbt")
    bars = make_bars(120, seed=7)
    diffs = verify_against_vectorbt(bars, _targets(bars), tolerance=5e-2)
    assert diffs["total_return"] < 5e-2
