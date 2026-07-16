"""Stress signal engine — how fragile is a signal to shocks?

Stress-tests a signal against volatility shocks, liquidity shocks, regime changes, and
correlation breakdowns (each expressed as a 0..1 edge-degradation sensitivity). Produces a
0-100 fragility score and its complement robustness; fragile signals are rejected / penalized.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StressResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    fragility_score: float   # 0-100 (higher = more fragile, worse)
    robustness_score: float  # 0-100 (higher = more robust, better)
    survived: bool
    shock_impacts: dict[str, float]


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class StressSignalEngine:
    """Scores signal fragility under a battery of market shocks."""

    def __init__(self, *, fragility_threshold: float = 60.0) -> None:
        self.fragility_threshold = fragility_threshold

    def assess(
        self,
        *,
        volatility_shock: float,
        liquidity_shock: float,
        regime_change: float,
        correlation_breakdown: float,
    ) -> StressResult:
        shocks = {
            "volatility_shock": _clip01(volatility_shock),
            "liquidity_shock": _clip01(liquidity_shock),
            "regime_change": _clip01(regime_change),
            "correlation_breakdown": _clip01(correlation_breakdown),
        }
        fragility = 100.0 * (sum(shocks.values()) / len(shocks))
        return StressResult(
            fragility_score=fragility,
            robustness_score=100.0 - fragility,
            survived=fragility <= self.fragility_threshold,
            shock_impacts=shocks,
        )
