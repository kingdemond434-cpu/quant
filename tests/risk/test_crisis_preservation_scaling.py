"""Crisis controls, equity preservation, and the global scaling dial."""

from __future__ import annotations

import pytest

from libs.risk.config import PreservationConfig
from libs.risk.crisis import crisis_controller
from libs.risk.errors import RiskError
from libs.risk.preservation import PreservationMode, equity_preservation_controller
from libs.risk.scaling import global_risk_scalar


def test_crisis_calm_is_not_crisis() -> None:
    response = crisis_controller(vol_now=1.0, vol_baseline=1.0, average_correlation=0.2)
    assert not response.in_crisis
    assert response.exposure_scalar == 1.0


def test_crisis_vol_spike_detected() -> None:
    response = crisis_controller(vol_now=3.0, vol_baseline=1.0, average_correlation=0.2)
    assert response.in_crisis
    assert response.exposure_scalar < 1.0
    assert response.suspend_negative_tail


def test_crisis_correlation_convergence() -> None:
    response = crisis_controller(vol_now=1.0, vol_baseline=1.0, average_correlation=0.9)
    assert response.in_crisis


def test_crisis_fails_closed_on_stale_data() -> None:
    response = crisis_controller(
        vol_now=1.0, vol_baseline=1.0, average_correlation=0.0, data_stale=True
    )
    assert response.in_crisis
    assert response.exposure_scalar < 1.0


def test_preservation_modes() -> None:
    normal = equity_preservation_controller(100_000.0, 100_000.0)
    assert normal.mode is PreservationMode.NORMAL and normal.scalar == 1.0

    recovery = equity_preservation_controller(88_000.0, 100_000.0)  # 12% dd
    assert recovery.mode is PreservationMode.RECOVERY
    assert recovery.scalar < 1.0

    cfg = PreservationConfig(equity_floor=50_000.0, floor_buffer_frac=0.10)
    preservation = equity_preservation_controller(54_000.0, 100_000.0, config=cfg)
    assert preservation.mode is PreservationMode.PRESERVATION

    survival = equity_preservation_controller(49_000.0, 100_000.0, config=cfg)
    assert survival.mode is PreservationMode.SURVIVAL
    assert survival.halt
    assert survival.scalar == 0.0


def test_global_scalar_is_minimum() -> None:
    scalar = global_risk_scalar(
        drawdown=0.66, correlation=1.0, crisis=0.25, floor=1.0, confidence=1.0
    )
    assert scalar.value == pytest.approx(0.25)
    assert scalar.binding == "crisis"


def test_global_scalar_validates_range() -> None:
    with pytest.raises(RiskError):
        global_risk_scalar(drawdown=1.5)
