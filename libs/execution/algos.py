"""Execution algorithm framework — deterministic child-order schedules.

Produces a schedule of child orders (offset + quantity) for a parent order without submitting them;
the :class:`ExecutionEngine` submits the slices. Three algos: TWAP (even over time), POV (paced to
a volume curve at a participation rate), and Implementation Shortfall (front-loaded by urgency).
Every schedule's quantities sum exactly to the parent quantity (the final slice absorbs rounding).
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from libs.execution.errors import ExecutionError


class ChildOrder(BaseModel):
    model_config = ConfigDict(frozen=True)

    offset_seconds: int
    qty: float


class ExecutionPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    algo: str
    symbol: str
    side: str
    total_qty: float
    slices: list[ChildOrder] = Field(default_factory=list)
    notes: str = ""

    @property
    def scheduled_qty(self) -> float:
        return sum(c.qty for c in self.slices)


def _validate(symbol: str, side: str, total_qty: float) -> None:
    if side not in ("buy", "sell"):
        raise ExecutionError(f"side must be 'buy' or 'sell', got {side!r}")
    if total_qty <= 0:
        raise ExecutionError("total_qty must be positive")
    if not symbol:
        raise ExecutionError("symbol is required")


def _finalize(
    weights: Sequence[float], total_qty: float, interval_seconds: int
) -> list[ChildOrder]:
    """Turn slice weights into child orders whose quantities sum exactly to ``total_qty``."""
    total_w = sum(weights)
    if total_w <= 0:
        raise ExecutionError("schedule weights must be positive")
    slices: list[ChildOrder] = []
    allocated = 0.0
    n = len(weights)
    for i, w in enumerate(weights):
        if i == n - 1:
            qty = total_qty - allocated  # last slice absorbs rounding
        else:
            qty = round(total_qty * (w / total_w), 10)
            allocated += qty
        slices.append(ChildOrder(offset_seconds=i * interval_seconds, qty=qty))
    return slices


class ExecutionScheduler:
    """Builds deterministic execution schedules."""

    def twap(
        self, *, symbol: str, side: str, total_qty: float, n_slices: int, interval_seconds: int
    ) -> ExecutionPlan:
        _validate(symbol, side, total_qty)
        if n_slices < 1:
            raise ExecutionError("n_slices must be >= 1")
        slices = _finalize([1.0] * n_slices, total_qty, interval_seconds)
        return ExecutionPlan(
            algo="twap", symbol=symbol, side=side, total_qty=total_qty, slices=slices,
            notes=f"even over {n_slices} slices",
        )

    def pov(
        self,
        *,
        symbol: str,
        side: str,
        total_qty: float,
        volume_curve: Sequence[float],
        participation_rate: float,
        interval_seconds: int,
    ) -> ExecutionPlan:
        _validate(symbol, side, total_qty)
        if not 0.0 < participation_rate <= 1.0:
            raise ExecutionError("participation_rate must be in (0, 1]")
        if not volume_curve or any(v < 0 for v in volume_curve):
            raise ExecutionError("volume_curve must be non-empty and non-negative")
        slices: list[ChildOrder] = []
        remaining = total_qty
        for i, bucket_volume in enumerate(volume_curve):
            if remaining <= 0:
                break
            qty = min(remaining, participation_rate * bucket_volume)
            if qty <= 0:
                continue
            slices.append(ChildOrder(offset_seconds=i * interval_seconds, qty=qty))
            remaining -= qty
        if remaining > 1e-12:  # curve capacity exhausted before the order filled
            if slices:
                last = slices[-1]
                slices[-1] = ChildOrder(
                    offset_seconds=last.offset_seconds, qty=last.qty + remaining
                )
            else:
                slices.append(ChildOrder(offset_seconds=0, qty=total_qty))
        return ExecutionPlan(
            algo="pov", symbol=symbol, side=side, total_qty=total_qty, slices=slices,
            notes=f"participation {participation_rate:.2%} of volume",
        )

    def implementation_shortfall(
        self,
        *,
        symbol: str,
        side: str,
        total_qty: float,
        n_slices: int,
        interval_seconds: int,
        urgency: float = 0.5,
    ) -> ExecutionPlan:
        _validate(symbol, side, total_qty)
        if n_slices < 1:
            raise ExecutionError("n_slices must be >= 1")
        urgency = max(0.0, min(1.0, urgency))
        # Front-load with geometric decay: higher urgency -> steeper decay -> more traded early.
        decay = 1.0 - 0.9 * urgency  # urgency 0 -> 1.0 (flat/TWAP), urgency 1 -> 0.1 (steep)
        weights = [decay**i for i in range(n_slices)]
        slices = _finalize(weights, total_qty, interval_seconds)
        return ExecutionPlan(
            algo="implementation_shortfall", symbol=symbol, side=side, total_qty=total_qty,
            slices=slices, notes=f"front-loaded, urgency={urgency:.2f}",
        )
