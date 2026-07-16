"""False Discovery Rate control (Benjamini-Hochberg / Benjamini-Yekutieli).

Bounds the expected proportion of false discoveries among the rejected hypotheses across the
whole research program — the program-wide layer of the family-wise error budget.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict


class FDRResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    rejected: list[bool]
    threshold: float
    n_rejected: int
    method: str


def _control(pvalues: np.ndarray, alpha: float, *, dependent: bool) -> tuple[np.ndarray, float]:
    p = np.asarray(pvalues, dtype="float64")
    m = len(p)
    if m == 0:
        return np.zeros(0, dtype=bool), 0.0
    order = np.argsort(p)
    ranks = np.arange(1, m + 1)
    c_m = float(np.sum(1.0 / ranks)) if dependent else 1.0
    crit = (ranks / (m * c_m)) * alpha
    sorted_p = p[order]
    below = sorted_p <= crit
    if not below.any():
        rejected = np.zeros(m, dtype=bool)
        return rejected, 0.0
    k_max = int(np.max(np.where(below)[0]))
    threshold = float(sorted_p[k_max])
    rejected = p <= threshold
    return rejected, threshold


def benjamini_hochberg(pvalues: np.ndarray, *, alpha: float = 0.1) -> FDRResult:
    """Benjamini-Hochberg FDR control (assumes independence / positive dependence)."""
    rejected, threshold = _control(np.asarray(pvalues), alpha, dependent=False)
    return FDRResult(
        rejected=rejected.tolist(), threshold=threshold, n_rejected=int(rejected.sum()),
        method="benjamini_hochberg",
    )


def benjamini_yekutieli(pvalues: np.ndarray, *, alpha: float = 0.1) -> FDRResult:
    """Benjamini-Yekutieli FDR control (valid under arbitrary dependence)."""
    rejected, threshold = _control(np.asarray(pvalues), alpha, dependent=True)
    return FDRResult(
        rejected=rejected.tolist(), threshold=threshold, n_rejected=int(rejected.sum()),
        method="benjamini_yekutieli",
    )
