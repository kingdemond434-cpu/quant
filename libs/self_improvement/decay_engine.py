"""Alpha decay detection (reuses ``libs.alpha.detect_decay``; adds PF/Sharpe decay levels).

Decay levels and their recommended (recommend-only) actions follow the Stage 13 spec. Stage 13
never applies these directly — capital reductions require Portfolio Engine approval; retirement
is applied via the existing AlphaLifecycleManager.
"""

from __future__ import annotations

from libs.alpha.card import AlphaCard, ExpectedMetrics, LiveMetrics
from libs.alpha.decay import detect_decay
from libs.self_improvement.models import DecayAssessment, DecayLevel

# decay level -> (recommended_action, weight_multiplier, allow_increase)
_ACTIONS: dict[DecayLevel, tuple[str, float, bool]] = {
    DecayLevel.HEALTHY: ("no_action", 1.0, True),
    DecayLevel.WATCH: ("reduce_weight_10pct", 0.90, True),
    DecayLevel.WEAK: ("reduce_weight_25pct", 0.75, True),
    DecayLevel.DECAYING: ("pause_capital_increases", 1.0, False),
    DecayLevel.DEAD: ("retire", 0.0, False),
}


def classify_decay(*, profit_factor: float | None, sharpe: float) -> DecayLevel:
    """Map profit factor (with a Sharpe proxy/confirmation) to a decay level."""
    pf = profit_factor
    if pf is None:
        pf = 1.5 if sharpe >= 1.5 else (1.0 if sharpe >= 0 else 0.7)
    if pf < 0.8:
        return DecayLevel.DEAD
    if pf < 1.0:
        return DecayLevel.DECAYING
    if pf < 1.2:
        return DecayLevel.WEAK
    if pf < 1.5:
        return DecayLevel.WATCH
    return DecayLevel.HEALTHY if sharpe > 1.5 else DecayLevel.WATCH


class AlphaDecayEngine:
    """Assesses decay and recommends an action (no action is applied here)."""

    def assess(self, card: AlphaCard, live: LiveMetrics) -> DecayAssessment:
        level = classify_decay(profit_factor=live.profit_factor, sharpe=live.sharpe)
        decay = detect_decay(ExpectedMetrics.from_card(card), live)
        action, multiplier, allow_increase = _ACTIONS[level]
        return DecayAssessment(
            alpha_id=card.id,
            decay_level=level,
            decay_score=decay.decay_score,
            recommended_action=action,
            weight_multiplier=multiplier,
            allow_increase=allow_increase,
        )
