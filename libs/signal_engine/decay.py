"""Signal decay engine — reuse the Stage 13 decay classification for signals.

The decay levels and PF thresholds are identical to the alpha decay model (single source of
truth): ``libs.self_improvement.classify_decay``. A decayed signal loses weight *and* confidence
and, when dead, is retired (action only; capital changes still require Portfolio Engine approval).
"""

from __future__ import annotations

from libs.self_improvement.decay_engine import classify_decay
from libs.self_improvement.models import DecayLevel
from libs.signal_engine.models import SignalDecayResult

# decay level -> (weight_multiplier, confidence_multiplier, recommended_action)
_ACTIONS: dict[DecayLevel, tuple[float, float, str]] = {
    DecayLevel.HEALTHY: (1.0, 1.0, "no_action"),
    DecayLevel.WATCH: (0.90, 0.90, "reduce_weight_and_confidence"),
    DecayLevel.WEAK: (0.75, 0.80, "reduce_weight_and_confidence"),
    DecayLevel.DECAYING: (0.50, 0.60, "pause_signal"),
    DecayLevel.DEAD: (0.0, 0.0, "retire_signal"),
}


class SignalDecayEngine:
    """Maps rolling profit factor / Sharpe to a decay level and its actions."""

    def assess(self, *, profit_factor: float | None, sharpe: float) -> SignalDecayResult:
        level = classify_decay(profit_factor=profit_factor, sharpe=sharpe)
        weight_mult, conf_mult, action = _ACTIONS[level]
        return SignalDecayResult(
            decay_level=level,
            weight_multiplier=weight_mult,
            confidence_multiplier=conf_mult,
            recommended_action=action,
        )
