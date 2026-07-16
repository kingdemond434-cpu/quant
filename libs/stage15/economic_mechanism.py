"""Economic mechanism engine — every alpha must have a documented causal explanation.

Statistical significance alone is insufficient. Reuses the validation layer's economic-prior gate
(which requires the mechanism plus why-it-works / why-it-might-fail / decay-detection fields). No
causal mechanism -> REJECT.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from libs.stage15.models import MechanismResult, MechanismType
from libs.validation.economic_prior import EconomicPrior, economic_prior_gate


class EconomicMechanismEngine:
    """Requires a documented causal mechanism for every alpha (fail-closed)."""

    def require(self, prior: Mapping[str, Any] | EconomicPrior) -> MechanismResult:
        gate = economic_prior_gate(prior)
        mechanism = self._extract_mechanism(prior)
        return MechanismResult(
            present=gate.passed,
            mechanism=mechanism,
            missing=list(gate.missing),
            message=gate.message,
        )

    def has_mechanism(self, prior: Mapping[str, Any] | EconomicPrior) -> bool:
        return self.require(prior).present

    @staticmethod
    def _extract_mechanism(prior: Mapping[str, Any] | EconomicPrior) -> MechanismType | None:
        raw = prior.mechanism if isinstance(prior, EconomicPrior) else prior.get("mechanism")
        if raw is None:
            return None
        try:
            return MechanismType(raw)
        except ValueError:
            return None
