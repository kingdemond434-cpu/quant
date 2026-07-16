"""Shadow deployment — evaluate a candidate signal live without risking capital.

Records the production vs shadow decision and (paper) return on each observation and reports
agreement, cumulative returns, and tracking error. It allocates **no capital** and never promotes;
readiness only signals that enough evidence exists for champion/challenger + walk-forward to judge.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict

from libs.signal_engine.models import Direction


class ShadowResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    variant_id: str
    n_decisions: int
    agreement_rate: float       # fraction where shadow == production direction
    production_return: float    # cumulative (paper)
    shadow_return: float        # cumulative (paper)
    tracking_error: float       # std of per-step return differences
    ready_for_promotion: bool   # enough evidence to evaluate (NOT a promotion itself)


class ShadowDeployment:
    """Accumulates shadow-vs-production observations; capital is never allocated."""

    def __init__(self, variant_id: str) -> None:
        self.variant_id = variant_id
        self._agreements: list[bool] = []
        self._prod_returns: list[float] = []
        self._shadow_returns: list[float] = []

    def observe(
        self,
        *,
        production_direction: Direction,
        shadow_direction: Direction,
        production_return: float,
        shadow_return: float,
    ) -> None:
        self._agreements.append(production_direction is shadow_direction)
        self._prod_returns.append(float(production_return))
        self._shadow_returns.append(float(shadow_return))

    def result(self, *, min_decisions: int = 100) -> ShadowResult:
        n = len(self._agreements)
        if n == 0:
            return ShadowResult(
                variant_id=self.variant_id, n_decisions=0, agreement_rate=0.0,
                production_return=0.0, shadow_return=0.0, tracking_error=0.0,
                ready_for_promotion=False,
            )
        prod = np.asarray(self._prod_returns, dtype="float64")
        shadow = np.asarray(self._shadow_returns, dtype="float64")
        tracking_error = float((shadow - prod).std(ddof=1)) if n > 1 else 0.0
        return ShadowResult(
            variant_id=self.variant_id,
            n_decisions=n,
            agreement_rate=float(np.mean(self._agreements)),
            production_return=float(prod.sum()),
            shadow_return=float(shadow.sum()),
            tracking_error=tracking_error,
            ready_for_promotion=n >= min_decisions,
        )
