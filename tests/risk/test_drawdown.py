"""Drawdown governor tests — the 0/5/10/15/20% ladder."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from libs.risk.drawdown import DrawdownLevel, compute_drawdown, drawdown_governor
from libs.risk.errors import RiskError


def test_compute_drawdown() -> None:
    assert compute_drawdown(90.0, 100.0) == pytest.approx(0.10)
    assert compute_drawdown(110.0, 100.0) == 0.0  # above HWM
    with pytest.raises(RiskError):
        compute_drawdown(100.0, 0.0)


@pytest.mark.parametrize(
    ("dd", "level", "halt"),
    [
        (0.02, DrawdownLevel.NORMAL, False),
        (0.07, DrawdownLevel.MODERATE, False),
        (0.12, DrawdownLevel.SIGNIFICANT, False),
        (0.17, DrawdownLevel.AGGRESSIVE, False),
        (0.25, DrawdownLevel.HALT, True),
    ],
)
def test_ladder_levels(dd: float, level: DrawdownLevel, halt: bool) -> None:
    response = drawdown_governor(dd)
    assert response.level is level
    assert response.halt is halt
    if halt:
        assert response.scalar == 0.0


def test_halt_at_twenty_percent() -> None:
    assert drawdown_governor(0.20).halt is True
    assert drawdown_governor(0.50).scalar == 0.0


@given(dd=st.floats(min_value=0.0, max_value=1.0))
def test_scalar_in_unit_interval_and_monotone(dd: float) -> None:
    response = drawdown_governor(dd)
    assert 0.0 <= response.scalar <= 1.0
    # deeper drawdown never increases exposure
    deeper = drawdown_governor(min(1.0, dd + 0.05))
    assert deeper.scalar <= response.scalar + 1e-9
