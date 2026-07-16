"""Ensemble optimizer — proposes the best *portfolio* of alphas (not the best single alpha).

Reuses the Portfolio Engine's robust optimizer; the result is advisory (requires approval).
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from libs.portfolio.engine import build_portfolio
from libs.portfolio.models import AlphaInput
from libs.self_improvement.models import WeightProposal


class EnsembleOptimizer:
    """Wraps the Portfolio Engine to propose diversified ensemble weights."""

    def optimize(
        self, alphas: Sequence[AlphaInput], *, correlation: np.ndarray | None = None
    ) -> WeightProposal:
        target = build_portfolio(alphas, correlation=correlation, method="optimize")
        return WeightProposal(
            weights=target.weights,
            rationale="ensemble optimization via Portfolio Engine (diversification-aware)",
        )
