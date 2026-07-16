"""Signal aggregation — combine weighted alpha votes into one net directional view.

Produces the net direction, an aggregated strength (net signed weight), an alpha-agreement ratio
(how much of the weight pulls the same way), and a per-alpha signed breakdown used for the
explainability layer and audit.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from libs.signal_engine.models import AlphaSignal, Direction

_EPS = 1e-12


@dataclass(frozen=True)
class Aggregation:
    direction: Direction
    aggregated_strength: float  # 0..1
    alpha_agreement: float  # 0..1
    breakdown: dict[str, float]  # alpha_id -> signed contribution


class SignalAggregator:
    """Aggregates directional alpha votes weighted by :class:`DynamicWeighting`."""

    def __init__(self, *, flat_band: float = 1e-6) -> None:
        # Net strength within +/- flat_band is treated as no edge -> FLAT.
        self.flat_band = flat_band

    def aggregate(
        self, signals: Sequence[AlphaSignal], weights: Mapping[str, float]
    ) -> Aggregation:
        breakdown = {
            s.alpha_id: weights.get(s.alpha_id, 0.0) * s.direction.sign for s in signals
        }
        net = sum(breakdown.values())
        total_weight = sum(weights.get(s.alpha_id, 0.0) for s in signals)

        if abs(net) <= self.flat_band:
            return Aggregation(Direction.FLAT, 0.0, 0.0, breakdown)

        direction = Direction.BUY if net > 0 else Direction.SELL
        # Agreement = share of total weight pulling in the net direction.
        agreeing = sum(
            weights.get(s.alpha_id, 0.0)
            for s in signals
            if s.direction.sign == direction.sign
        )
        agreement = agreeing / total_weight if total_weight > _EPS else 0.0
        return Aggregation(
            direction=direction,
            aggregated_strength=min(1.0, abs(net)),
            alpha_agreement=min(1.0, agreement),
            breakdown=breakdown,
        )
