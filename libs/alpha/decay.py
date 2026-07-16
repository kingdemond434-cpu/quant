"""Alpha decay detection — a 0..1 decay score from four deterioration components.

decay_score blends performance, risk, stability, and regime-mismatch deterioration (0 = healthy,
1 = fully decayed) and maps to a recommended lifecycle state. Thesis invalidation (handled by the
operator) should override statistics, which are slow for low-frequency alphas.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from libs.alpha.card import ExpectedMetrics, LiveMetrics
from libs.alpha.health import _higher_better, _lower_better
from libs.alpha.state import AlphaState


class DecayResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    decay_score: float
    components: dict[str, float]
    recommended_state: AlphaState


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def detect_decay(
    expected: ExpectedMetrics,
    live: LiveMetrics,
    *,
    watch_threshold: float = 0.30,
    decaying_threshold: float = 0.50,
    retire_threshold: float = 0.70,
) -> DecayResult:
    """Compute the decay score and recommend a lifecycle state."""
    perf_health = [
        h for h in (_higher_better(live.sharpe, expected.sharpe),
                    _higher_better(live.cagr, expected.cagr)) if h is not None
    ]
    stability_health = [
        h for h in (_higher_better(live.profit_factor, expected.profit_factor),
                    _higher_better(live.expectancy, expected.expectancy),
                    _higher_better(live.win_rate, expected.win_rate)) if h is not None
    ]
    risk_health = _lower_better(live.max_drawdown, expected.max_drawdown)

    performance_deterioration = 1.0 - _mean(perf_health) if perf_health else 0.0
    stability_deterioration = 1.0 - _mean(stability_health) if stability_health else 0.0
    risk_deterioration = (1.0 - risk_health) if risk_health is not None else 0.0
    regime_mismatch = 1.0 - max(0.0, min(1.0, live.regime_stability))

    components = {
        "performance": performance_deterioration,
        "risk": risk_deterioration,
        "stability": stability_deterioration,
        "regime_mismatch": regime_mismatch,
    }
    decay_score = max(0.0, min(1.0, sum(components.values()) / len(components)))

    if decay_score >= retire_threshold:
        recommended = AlphaState.RETIREMENT_CANDIDATE
    elif decay_score >= decaying_threshold:
        recommended = AlphaState.DECAYING
    elif decay_score >= watch_threshold:
        recommended = AlphaState.WATCH
    else:
        recommended = AlphaState.ACTIVE

    return DecayResult(
        decay_score=decay_score, components=components, recommended_state=recommended
    )
