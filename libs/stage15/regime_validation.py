"""Regime-specific alpha validation — prefer alphas that survive many environments.

Validates an alpha's performance across bull / bear / high-vol / low-vol / trending / range /
crisis regimes and produces a regime-resilience score. Reuses the discovery layer's
regime-diversification primitive (Gini evenness + productive fraction).
"""

from __future__ import annotations

from collections.abc import Mapping

from libs.discovery.regime_diversification import regime_diversification
from libs.stage15.models import RegimeValidationResult, ResearchRegime


class RegimeValidationEngine:
    """Scores how robustly an alpha performs across market regimes."""

    def validate(
        self,
        regime_performance: Mapping[ResearchRegime | str, float],
        *,
        threshold: float = 50.0,
    ) -> RegimeValidationResult:
        by_regime = {
            (r.value if isinstance(r, ResearchRegime) else str(r)): float(v)
            for r, v in regime_performance.items()
        }
        result = regime_diversification(by_regime, threshold=threshold)
        return RegimeValidationResult(
            regime_resilience_score=result.regime_diversification_score,
            by_regime=by_regime,
            productive_fraction=result.productive_fraction,
            robust=result.robust,
        )
