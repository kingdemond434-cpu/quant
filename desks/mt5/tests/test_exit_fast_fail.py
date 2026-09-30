from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_DESK))
sys.path.insert(0, str(_DESK / "research"))

from research.exit_study import apply_fast_fail


def _trade(side: int = 1):
    return SimpleNamespace(
        entry_time=pd.Timestamp("2026-01-01T10:00:00Z"),
        exit_time=pd.Timestamp("2026-01-01T11:00:00Z"),
        side=side, entry=100.0, stop=90.0 if side > 0 else 110.0,
        target=120.0 if side > 0 else 80.0, exit=90.0 if side > 0 else 110.0,
        r_multiple=-1.1)


def _bars(rows):
    idx = pd.date_range("2026-01-01T10:00:00Z", periods=len(rows), freq="5min")
    return pd.DataFrame(rows, index=idx, columns=["open", "high", "low", "close"])


def test_fast_fail_waits_for_a_completed_bar_and_exits_at_the_next_open() -> None:
    bars = _bars([
        (99, 101, 98, 100.5),       # fill bar: ignored for the decision
        (100.5, 101, 97, 98),       # reclaim, 0.3R adverse, <=0.1R favourable
        (97.5, 99, 96, 98),         # executable next open = 97.5
    ])
    out = apply_fast_fail(bars, [_trade()], max_bars=2, min_mae_r=.2,
                          max_mfe_r=.1, reclaim_closes=1)
    assert out["triggered"] == 1
    # Baseline includes 0.1R costs, so the fast exit is -0.25R gross - 0.1R costs.
    assert out["variant"] == pytest.approx([-0.35])


def test_normal_noise_without_range_reclaim_does_not_exit() -> None:
    bars = _bars([
        (99, 101, 98, 100.5),
        (100.5, 103, 98, 101),
        (101, 104, 99, 103),
    ])
    out = apply_fast_fail(bars, [_trade()], max_bars=2, min_mae_r=.15,
                          max_mfe_r=.5, reclaim_closes=1)
    assert out["triggered"] == 0
    assert out["variant"] == [-1.1]


def test_a_hard_stop_in_the_same_bar_owns_ambiguous_ordering() -> None:
    bars = _bars([
        (99, 101, 98, 100.5),
        (100.5, 101, 89, 91),       # hard stop and reclaim in the same M5 bar
        (91, 92, 88, 90),
    ])
    out = apply_fast_fail(bars, [_trade()], max_bars=2, min_mae_r=.15,
                          max_mfe_r=.2, reclaim_closes=1)
    assert out["triggered"] == 0
    assert out["variant"] == [-1.1]
