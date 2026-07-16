"""Signal uncertainty and tail risk.

``SignalUncertaintyEngine`` separates epistemic uncertainty (alpha disagreement, thin evidence)
from aleatoric uncertainty (irreducible market noise). ``signal_tail_risk`` reuses the discovery
tail-risk model. High uncertainty / tail risk later reduces confidence, size, and rank.
"""

from __future__ import annotations

import math

import numpy as np

from libs.discovery.tail_risk import tail_risk
from libs.signal_engine.models import UncertaintyResult


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def signal_tail_risk(returns: np.ndarray, *, threshold: float = 60.0) -> float:
    """Return the 0-100 hidden tail-risk score for a signal's return sample."""
    return tail_risk(returns, threshold=threshold).tail_risk_score


class SignalUncertaintyEngine:
    """Estimates epistemic + aleatoric uncertainty (0..1; higher is worse)."""

    def estimate(
        self,
        *,
        alpha_agreement: float,
        n_alphas: int,
        sample_size: int,
        volatility_state: float,
    ) -> UncertaintyResult:
        disagreement = 1.0 - _clip01(alpha_agreement)
        thin_panel = 1.0 - _clip01(n_alphas / 5.0)
        thin_sample = 1.0 / math.sqrt(max(sample_size, 1))
        epistemic = _clip01(0.5 * disagreement + 0.3 * thin_panel + 0.2 * thin_sample)
        aleatoric = _clip01(volatility_state)
        uncertainty = _clip01(0.6 * epistemic + 0.4 * aleatoric)
        return UncertaintyResult(
            epistemic_uncertainty=epistemic,
            aleatoric_uncertainty=aleatoric,
            uncertainty_score=uncertainty,
        )
