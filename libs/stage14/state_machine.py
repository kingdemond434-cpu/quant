"""Portfolio state machine — NORMAL / CAUTION / DEFENSIVE / CRISIS / RECOVERY.

The state modulates risk budgets, Kelly fractions, leverage, and allocations. Survival dominates:
deteriorating drawdown or survival pushes the portfolio defensive long before it would push it back.
"""

from __future__ import annotations

from libs.stage14.models import PortfolioState

_RISK_MULTIPLIER: dict[PortfolioState, float] = {
    PortfolioState.NORMAL: 1.0,
    PortfolioState.CAUTION: 0.7,
    PortfolioState.DEFENSIVE: 0.4,
    PortfolioState.CRISIS: 0.0,
    PortfolioState.RECOVERY: 0.5,
}


class PortfolioStateMachine:
    """Classifies the portfolio risk regime and the risk multiplier it implies."""

    def classify(
        self,
        *,
        drawdown: float,
        survival_score: float = 100.0,
        regime_uncertainty: float = 0.0,
        recovering: bool = False,
    ) -> PortfolioState:
        if drawdown >= 0.20 or survival_score < 50.0:
            return PortfolioState.CRISIS
        if drawdown >= 0.12 or survival_score < 70.0 or regime_uncertainty > 0.7:
            return PortfolioState.DEFENSIVE
        if recovering and drawdown < 0.06:
            return PortfolioState.RECOVERY
        if drawdown >= 0.06 or regime_uncertainty > 0.4:
            return PortfolioState.CAUTION
        return PortfolioState.NORMAL

    @staticmethod
    def risk_multiplier(state: PortfolioState) -> float:
        return _RISK_MULTIPLIER[state]
