"""Regime routing — align alpha votes with the current and predicted regime.

``RegimeRouter`` scores how well an alpha fits the *current* regime; ``RegimeTransitionRouter``
blends current and predicted regimes by the (confidence-weighted) transition probability so the
engine leans into regimes it expects to enter. Both return 0..1 multipliers; neither trades.
"""

from __future__ import annotations

from libs.signal_engine.models import AlphaSignal, MarketState, Regime

_DEFAULT_AFFINITY = 0.5  # neutral when an alpha has no stated affinity for a regime


def regime_affinity(signal: AlphaSignal, regime: Regime) -> float:
    """An alpha's stated 0..1 affinity for ``regime`` (neutral 0.5 if unstated)."""
    if not signal.regime_affinity:
        return _DEFAULT_AFFINITY
    return float(signal.regime_affinity.get(regime.value, 0.0))


def transition_confidence(state: MarketState) -> float:
    """How certain we are that a regime change is *real* (0..1).

    A transition is only credible when the probability is decisive; probabilities near 0.5 are
    coin-flips and earn low confidence so false transition calls cannot drive signals.
    """
    p = state.transition_probability
    return float(max(0.0, min(1.0, abs(p - 0.5) * 2.0)))


class RegimeRouter:
    """Routes an alpha by its fit to the current regime."""

    def route(self, signal: AlphaSignal, state: MarketState) -> float:
        """Return a 0..1 multiplier for how well the alpha fits the current regime."""
        return regime_affinity(signal, state.regime)


class RegimeTransitionRouter:
    """Routes an alpha by a blend of current and predicted regime affinity."""

    def route(self, signal: AlphaSignal, state: MarketState) -> float:
        """Blend current/predicted affinity, weighted by confident transition probability."""
        current = regime_affinity(signal, state.regime)
        if state.predicted_regime == state.regime:
            return current
        future = regime_affinity(signal, state.predicted_regime)
        # Only shift toward the predicted regime to the extent the transition is credible.
        weight = state.transition_probability * transition_confidence(state)
        weight = max(0.0, min(1.0, weight))
        return float(current * (1.0 - weight) + future * weight)
