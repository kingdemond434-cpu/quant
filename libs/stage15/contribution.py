"""Portfolio contribution forecaster — alpha quality is portfolio contribution, not standalone.

Estimates an alpha's marginal contribution to portfolio CAGR / Sharpe, its diversification and
survival benefit, and its correlation impact. An alpha that is excellent alone but redundant or
correlated to the book contributes little and is not preferred.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from libs.stage15.models import ContributionForecast


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class AlphaContributionForecaster:
    """Forecasts an alpha's marginal portfolio contribution."""

    def __init__(self, *, max_correlation: float = 0.6) -> None:
        self.max_correlation = max_correlation

    def forecast(
        self,
        *,
        alpha_return: float,
        alpha_sharpe: float,
        weight: float,
        survival_score: float,
        correlations_to_book: Sequence[float] = (),
    ) -> ContributionForecast:
        avg_corr = float(np.mean([abs(c) for c in correlations_to_book])) if correlations_to_book \
            else 0.0
        diversification_benefit = 1.0 - _clip01(avg_corr)
        # Marginal contribution scaled by how much new (uncorrelated) information it adds.
        cagr_contribution = weight * alpha_return * diversification_benefit
        sharpe_contribution = weight * alpha_sharpe * diversification_benefit
        survival_benefit = _clip01(survival_score / 100.0)
        net_beneficial = (
            cagr_contribution > 0.0
            and avg_corr <= self.max_correlation
            and survival_benefit > 0.0
        )
        return ContributionForecast(
            cagr_contribution=cagr_contribution,
            sharpe_contribution=sharpe_contribution,
            diversification_benefit=diversification_benefit,
            survival_benefit=survival_benefit,
            correlation_impact=_clip01(avg_corr),
            net_beneficial=net_beneficial,
        )
