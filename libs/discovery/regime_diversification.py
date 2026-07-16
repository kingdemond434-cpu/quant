"""regime_diversification_engine — productivity across market environments.

Penalizes alphas dependent on a single regime; prefers regime-balanced exposure. Score reflects
both *breadth* (how many regimes are productive) and *evenness* (no single regime dominates).
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict

REGIMES = (
    "trend", "range", "high_vol", "low_vol", "crisis",
    "risk_on", "risk_off", "inflationary", "deflationary",
)


class RegimeDiversificationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    regime_diversification_score: float  # 0-100, higher = more regime-robust
    robust: bool
    productive_fraction: float
    evenness: float

    def __bool__(self) -> bool:
        return self.robust


def _gini_evenness(values: list[float]) -> float:
    positive = [v for v in values if v > 0]
    if len(positive) <= 1:
        return 0.0 if not positive else 1.0
    total = sum(positive)
    shares = sorted(v / total for v in positive)
    n = len(shares)
    cum = sum((i + 1) * s for i, s in enumerate(shares))
    gini = (2.0 * cum) / (n * sum(shares)) - (n + 1.0) / n
    return max(0.0, 1.0 - gini)


def regime_diversification(
    regime_performance: Mapping[str, float], *, threshold: float = 50.0
) -> RegimeDiversificationResult:
    """Score an alpha's productivity and balance across regimes."""
    values = list(regime_performance.values())
    if not values:
        return RegimeDiversificationResult(
            regime_diversification_score=0.0, robust=False, productive_fraction=0.0, evenness=0.0
        )
    productive_fraction = sum(1 for v in values if v > 0) / len(values)
    evenness = _gini_evenness(values)
    score = 100.0 * productive_fraction * (0.5 + 0.5 * evenness)
    return RegimeDiversificationResult(
        regime_diversification_score=score,
        robust=productive_fraction >= 0.5 and score >= threshold,
        productive_fraction=productive_fraction,
        evenness=evenness,
    )
