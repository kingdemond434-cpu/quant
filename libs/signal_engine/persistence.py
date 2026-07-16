"""Signal persistence and stability — durability and steadiness of a signal.

``SignalPersistenceEngine`` rewards age, survival, and regime consistency while penalizing flips
and noise. ``SignalStabilityEngine`` measures oscillation/direction changes/prediction steadiness
and rejects signals that are too jittery to trust. Both emit 0-100 scores.
"""

from __future__ import annotations

from libs.signal_engine.models import PersistenceResult, StabilityResult


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class SignalPersistenceEngine:
    """Scores how durable a signal has been over its observed life."""

    def assess(
        self,
        *,
        signal_age: int,
        survival: float,
        flip_frequency: float,
        noise_level: float,
        regime_consistency: float,
        max_age: int = 60,
    ) -> PersistenceResult:
        age_factor = _clip01(signal_age / max_age) if max_age > 0 else 0.0
        components = {
            "age_factor": age_factor,
            "survival": _clip01(survival),
            "regime_consistency": _clip01(regime_consistency),
            "flip_penalty": _clip01(flip_frequency),
            "noise_penalty": _clip01(noise_level),
        }
        base = (
            0.20 * age_factor
            + 0.30 * components["survival"]
            + 0.30 * components["regime_consistency"]
            + 0.20 * (1.0 - components["flip_penalty"])
        )
        score = 100.0 * _clip01(base) * (1.0 - 0.5 * components["noise_penalty"])
        return PersistenceResult(persistence_score=score, components=components)


class SignalStabilityEngine:
    """Scores signal steadiness; below ``threshold`` the signal is rejected."""

    def __init__(self, *, threshold: float = 60.0) -> None:
        self.threshold = threshold

    def assess(
        self,
        *,
        oscillation: float,
        direction_change_rate: float,
        prediction_stability: float,
        alpha_stability: float,
        regime_stability: float,
    ) -> StabilityResult:
        components = {
            "steadiness": 1.0 - _clip01(oscillation),
            "direction_consistency": 1.0 - _clip01(direction_change_rate),
            "prediction_stability": _clip01(prediction_stability),
            "alpha_stability": _clip01(alpha_stability),
            "regime_stability": _clip01(regime_stability),
        }
        score = 100.0 * (sum(components.values()) / len(components))
        return StabilityResult(
            stability_score=score, components=components, passed=score >= self.threshold
        )
