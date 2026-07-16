"""Alpha weighting — turn raw alpha votes into regime/health/decay-aware weights.

The weight of an alpha's vote is its conviction scaled by quality (health), durability (decay
multiplier), and regime fit. ``DynamicWeighting`` normalizes the weights across the contributing
alphas for one symbol so the aggregator works with a convex combination.
"""

from __future__ import annotations

from collections.abc import Sequence

from libs.signal_engine.models import AlphaSignal, MarketState
from libs.signal_engine.regime import RegimeRouter, RegimeTransitionRouter

_EPS = 1e-12


class AlphaWeighting:
    """Computes a non-negative weight for a single alpha vote."""

    def __init__(
        self,
        *,
        router: RegimeRouter | None = None,
        transition_router: RegimeTransitionRouter | None = None,
    ) -> None:
        self.router = router or RegimeRouter()
        self.transition_router = transition_router or RegimeTransitionRouter()

    def weight(self, signal: AlphaSignal, state: MarketState) -> float:
        """conviction x health x decay x current-regime-fit x predicted-regime-fit."""
        regime_fit = self.router.route(signal, state)
        future_fit = self.transition_router.route(signal, state)
        return float(
            max(0.0, signal.strength)
            * max(0.0, signal.health_score / 100.0)
            * max(0.0, signal.decay_multiplier)
            * max(0.0, regime_fit)
            * max(0.0, future_fit)
        )


class DynamicWeighting:
    """Normalizes per-alpha weights across the alphas voting on one symbol."""

    def __init__(self, *, weighting: AlphaWeighting | None = None) -> None:
        self.weighting = weighting or AlphaWeighting()

    def weights(
        self, signals: Sequence[AlphaSignal], state: MarketState
    ) -> dict[str, float]:
        raw = {s.alpha_id: self.weighting.weight(s, state) for s in signals}
        total = sum(raw.values())
        if total <= _EPS:
            return dict.fromkeys(raw, 0.0)
        return {k: v / total for k, v in raw.items()}
