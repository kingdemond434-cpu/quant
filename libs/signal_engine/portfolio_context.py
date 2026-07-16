"""Portfolio context engine — "is this the best trade for the current portfolio?"

Evaluates a candidate against the existing book: marginal risk-adjusted improvement (discounted
by correlation to what is already held) and whether it would breach factor concentration. Rejects
trades that add correlated, concentrating, or efficiency-reducing exposure.
"""

from __future__ import annotations

from libs.signal_engine.models import PortfolioContextResult


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class PortfolioContextEngine:
    """Scores a signal's marginal contribution to portfolio quality."""

    def __init__(self, *, max_concentration: float = 0.40) -> None:
        self.max_concentration = max_concentration

    def evaluate(
        self,
        *,
        candidate_sharpe: float,
        candidate_sortino: float,
        candidate_calmar: float,
        correlation_to_portfolio: float,
        marginal_diversification: float,
        concentration_after: float,
    ) -> PortfolioContextResult:
        independence = 1.0 - _clip01(correlation_to_portfolio)
        marginal_sharpe = candidate_sharpe * independence
        marginal_sortino = candidate_sortino * independence
        marginal_calmar = candidate_calmar * independence

        diversification_score = 100.0 * _clip01(marginal_diversification)
        contribution_score = 100.0 * independence * _clip01(candidate_sharpe / 2.0)

        accept = marginal_sharpe > 0.0 and concentration_after <= self.max_concentration
        return PortfolioContextResult(
            portfolio_contribution_score=contribution_score,
            portfolio_diversification_score=diversification_score,
            marginal_sharpe_improvement=marginal_sharpe,
            marginal_sortino_improvement=marginal_sortino,
            marginal_calmar_improvement=marginal_calmar,
            accept=accept,
        )
