"""Equity preservation — protect the base so long-term compounding survives.

Modes escalate as equity approaches the floor: normal -> recovery (clawing back from a
drawdown) -> preservation (near the floor) -> survival (at/through the floor: halt). The
absolute equity floor is the ultimate ruin backstop.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from libs.risk.config import PreservationConfig
from libs.risk.drawdown import compute_drawdown
from libs.risk.errors import RiskError

_PRESERVATION_SCALAR = 0.30
_RECOVERY_SCALAR = 0.50


class PreservationMode(StrEnum):
    NORMAL = "normal"
    RECOVERY = "recovery"
    PRESERVATION = "preservation"
    SURVIVAL = "survival"


class PreservationResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    mode: PreservationMode
    scalar: float
    halt: bool

    def __bool__(self) -> bool:
        return not self.halt


def equity_preservation_controller(
    equity: float, peak_equity: float, *, config: PreservationConfig | None = None
) -> PreservationResponse:
    """Return the preservation mode + exposure scalar (halts at/through the floor)."""
    cfg = config or PreservationConfig()
    if peak_equity <= 0:
        raise RiskError("peak_equity must be positive")

    floor = cfg.equity_floor
    if floor > 0 and equity <= floor:
        return PreservationResponse(mode=PreservationMode.SURVIVAL, scalar=0.0, halt=True)
    if floor > 0 and equity <= floor * (1.0 + cfg.floor_buffer_frac):
        return PreservationResponse(
            mode=PreservationMode.PRESERVATION, scalar=_PRESERVATION_SCALAR, halt=False
        )
    if compute_drawdown(equity, peak_equity) >= cfg.recovery_drawdown:
        return PreservationResponse(
            mode=PreservationMode.RECOVERY, scalar=_RECOVERY_SCALAR, halt=False
        )
    return PreservationResponse(mode=PreservationMode.NORMAL, scalar=1.0, halt=False)
