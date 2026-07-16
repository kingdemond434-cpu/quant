"""Tests for edge-gated leverage."""

from __future__ import annotations

from libs.risk.edge_gate import gated_leverage


def test_unproven_edge_stays_at_floor() -> None:
    assert gated_leverage(None, 0) == 2.0                      # no shadow
    assert gated_leverage(-0.5, 60) == 2.0                     # negative forward Sharpe
    assert gated_leverage(1.5, 10) == 2.0                      # too few forward days


def test_scales_up_with_forward_evidence() -> None:
    # positive forward Sharpe, partial confidence -> between floor and half-Kelly
    mid = gated_leverage(1.5, 60)                              # 60/90 days, Sharpe 1.5
    assert 2.0 < mid < 4.5
    full = gated_leverage(1.5, 90)                             # full window -> half-Kelly(1.5)=4.5
    assert abs(full - 4.5) < 1e-6


def test_capped_at_growth_optimal() -> None:
    assert gated_leverage(5.0, 200) == 6.0                     # huge Sharpe still capped at 6x
    assert gated_leverage(1.0, 90) == 3.0                      # Sharpe 1 at full window -> 3x


def test_monotonic_in_days_and_sharpe() -> None:
    assert gated_leverage(1.2, 90) >= gated_leverage(1.2, 45)
    assert gated_leverage(2.0, 90) >= gated_leverage(1.0, 90)
