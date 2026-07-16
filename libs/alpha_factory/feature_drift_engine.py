"""Feature drift engine — detect when a research feature's distribution shifts.

Reuses the Stage 13 Population Stability Index (single source of truth for drift). When a
feature's live distribution drifts from its training distribution, dependent alphas should be
revalidated before further research effort is spent on them.
"""

from __future__ import annotations

import numpy as np

from libs.alpha_factory.models import DriftResult
from libs.self_improvement.drift_detector import population_stability_index


class FeatureDriftEngine:
    """Flags feature distribution drift and recommends revalidation."""

    def __init__(self, *, psi_threshold: float = 0.20) -> None:
        self.psi_threshold = psi_threshold

    def detect(self, training: np.ndarray, live: np.ndarray) -> DriftResult:
        psi = population_stability_index(training, live)
        drifted = psi > self.psi_threshold
        recommendation = (
            "feature drifted; revalidate dependent alphas before further research"
            if drifted
            else "no feature drift"
        )
        return DriftResult(psi=psi, drifted=drifted, recommendation=recommendation)
