"""Meta model — a deterministic calibration mapping signal features to a success probability.

This is a fixed, transparent logistic blend (NOT a trained black box): it turns the engine's own
sub-scores into a single 0..1 probability the confidence engine can consume. Keeping it
deterministic preserves reproducibility; the weights are documented and auditable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Fixed logistic weights over normalized 0..1 features. Documented and reproducible.
_BIAS = -2.0
_WEIGHTS: dict[str, float] = {
    "edge": 2.2,
    "agreement": 1.6,
    "persistence": 1.0,
    "stability": 1.0,
}


@dataclass(frozen=True)
class MetaModel:
    """Calibrates a probability of success from normalized signal features."""

    def predict_proba(
        self, *, edge: float, agreement: float, persistence: float, stability: float
    ) -> float:
        feats = {
            "edge": _clip01(edge),
            "agreement": _clip01(agreement),
            "persistence": _clip01(persistence),
            "stability": _clip01(stability),
        }
        z = _BIAS + sum(_WEIGHTS[k] * v for k, v in feats.items())
        return 1.0 / (1.0 + math.exp(-z))


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))
