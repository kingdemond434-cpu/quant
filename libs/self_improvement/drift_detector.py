"""Alpha drift detector — training vs live distribution shift (PSI).

When the live distribution drifts from training, confidence should drop and revalidation should
be triggered. Detection is statistical (Population Stability Index); the response is a
recommendation (Stage 13 does not pause capital directly).
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict


class DriftResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    psi: float
    drifted: bool
    recommendation: str

    def __bool__(self) -> bool:
        return not self.drifted


def population_stability_index(
    expected: np.ndarray, actual: np.ndarray, *, bins: int = 10, eps: float = 1e-6
) -> float:
    """Population Stability Index between a training (expected) and live (actual) sample."""
    e = np.asarray(expected, dtype="float64")
    a = np.asarray(actual, dtype="float64")
    if len(e) < 2 or len(a) < 2:
        return 0.0
    edges = np.unique(np.quantile(e, np.linspace(0.0, 1.0, bins + 1)))
    if len(edges) < 2:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    e_prop = np.histogram(e, edges)[0] / len(e) + eps
    a_prop = np.histogram(a, edges)[0] / len(a) + eps
    return float(np.sum((a_prop - e_prop) * np.log(a_prop / e_prop)))


class AlphaDriftDetector:
    """Flags distribution drift and recommends reduce-confidence / revalidate."""

    def __init__(self, *, psi_threshold: float = 0.20) -> None:
        self.psi_threshold = psi_threshold

    def detect(self, training: np.ndarray, live: np.ndarray) -> DriftResult:
        psi = population_stability_index(training, live)
        drifted = psi > self.psi_threshold
        recommendation = (
            "reduce confidence, pause signal, trigger revalidation"
            if drifted
            else "no drift detected"
        )
        return DriftResult(psi=psi, drifted=drifted, recommendation=recommendation)
