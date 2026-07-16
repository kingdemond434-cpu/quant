"""Factor risk model and shrinkage covariance.

Two estimators of the asset covariance the optimizer consumes:

* :class:`ShrinkageCovariance` — Ledoit-Wolf shrinkage of the sample covariance toward a
  constant-correlation target (well-conditioned, deterministic; auto or explicit intensity).
* :class:`FactorRiskModel` — a structured covariance ``B F B' + diag(specific)`` from factor
  exposures, a factor covariance, and idiosyncratic variances.

Both return a symmetric PSD-ish covariance usable directly by the portfolio engine.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast

import numpy as np

from libs.portfolio.errors import PortfolioError


def _constant_correlation_target(sample: np.ndarray) -> np.ndarray:
    std = np.sqrt(np.diag(sample))
    std_safe = np.where(std > 0, std, 1.0)
    corr = sample / np.outer(std_safe, std_safe)
    n = sample.shape[0]
    if n < 2:
        return sample.copy()
    off = (corr.sum() - np.trace(corr)) / (n * (n - 1))
    target = off * np.outer(std, std)
    np.fill_diagonal(target, np.diag(sample))
    return cast("np.ndarray", target)


class ShrinkageCovariance:
    """Ledoit-Wolf shrinkage toward a constant-correlation target."""

    def estimate(self, returns: np.ndarray, *, shrinkage: float | None = None) -> np.ndarray:
        x = np.asarray(returns, dtype="float64")
        if x.ndim != 2:
            raise PortfolioError("returns must be a (T x N) matrix")
        t = x.shape[0]
        if t < 2:
            raise PortfolioError("need at least 2 observations")
        demeaned = x - x.mean(axis=0)
        sample = (demeaned.T @ demeaned) / t  # MLE covariance
        target = _constant_correlation_target(sample)
        delta = (
            self._auto_intensity(demeaned, sample, target)
            if shrinkage is None
            else max(0.0, min(1.0, shrinkage))
        )
        return cast("np.ndarray", delta * target + (1.0 - delta) * sample)

    @staticmethod
    def _auto_intensity(demeaned: np.ndarray, sample: np.ndarray, target: np.ndarray) -> float:
        t = demeaned.shape[0]
        # pi: sum of asymptotic variances of the sample covariance entries.
        prod = np.einsum("ti,tj->tij", demeaned, demeaned)
        pi_mat = ((prod - sample) ** 2).mean(axis=0)
        pi = float(pi_mat.sum())
        gamma = float(((target - sample) ** 2).sum())
        if gamma <= 0.0:
            return 0.0
        # rho approximated by the diagonal terms (standard, robust simplification).
        rho = float(np.trace(pi_mat))
        kappa = (pi - rho) / gamma
        intensity: float = max(0.0, min(1.0, kappa / float(t)))
        return intensity


class FactorRiskModel:
    """Structured covariance from factor exposures: ``cov = B F B' + diag(specific)``."""

    def __init__(self, factors: Sequence[str]) -> None:
        if not factors:
            raise PortfolioError("at least one factor is required")
        self.factors = list(factors)

    def build(
        self,
        *,
        exposures: Mapping[str, Mapping[str, float]],
        factor_cov: np.ndarray,
        specific_var: Mapping[str, float],
    ) -> tuple[list[str], np.ndarray]:
        assets = sorted(exposures)
        if not assets:
            raise PortfolioError("at least one asset is required")
        k = len(self.factors)
        f = np.asarray(factor_cov, dtype="float64")
        if f.shape != (k, k):
            raise PortfolioError(f"factor_cov shape {f.shape} != ({k}, {k})")
        loadings = np.array(
            [[float(exposures[a].get(factor, 0.0)) for factor in self.factors] for a in assets],
            dtype="float64",
        )
        specific = np.array([float(specific_var.get(a, 0.0)) for a in assets], dtype="float64")
        if np.any(specific < 0):
            raise PortfolioError("specific variances must be non-negative")
        cov = loadings @ f @ loadings.T + np.diag(specific)
        return assets, cast("np.ndarray", cov)
