"""Factor exposure engine — prevent hidden factor concentration.

Aggregates net USD, net directional, beta, and volatility exposures into a 0-100 score (higher =
more concentrated). The portfolio layer supplies the netted exposures; this scores them against a
cap and flags excessive concentration for hedging.
"""

from __future__ import annotations

from libs.stage14_5.models import FactorExposureResult


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class FactorExposureEngine:
    """Scores portfolio factor concentration."""

    def __init__(self, *, cap: float = 1.0, threshold: float = 70.0) -> None:
        self.cap = cap
        self.threshold = threshold

    def evaluate(
        self,
        *,
        net_usd: float,
        net_directional: float,
        beta: float,
        volatility_exposure: float,
    ) -> FactorExposureResult:
        worst = max(abs(net_usd), abs(net_directional), abs(beta), abs(volatility_exposure))
        score = 100.0 * _clip01(worst / self.cap if self.cap > 0 else 1.0)
        return FactorExposureResult(
            net_usd=net_usd, net_directional=net_directional, beta=beta,
            volatility_exposure=volatility_exposure, factor_exposure_score=score,
            acceptable=score <= self.threshold,
        )
