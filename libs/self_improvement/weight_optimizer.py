"""Dynamic weight optimizer — proposes (does not apply) target weights.

Allocates toward strong, healthy, regime-aligned, uncorrelated alphas and away from decaying or
correlated ones. The output is a :class:`WeightProposal` that *requires Portfolio Engine
approval*; Stage 13 cannot set production weights itself.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from libs.self_improvement.models import WeightProposal

_EPS = 1e-9


@dataclass(frozen=True)
class WeightCandidate:
    alpha_id: str
    health_score: float          # 0-100
    decay_multiplier: float = 1.0  # from the decay engine
    regime_match: float = 1.0      # 0-1
    correlation_penalty: float = 0.0  # 0-1 (higher = more correlated -> less weight)


def _score(c: WeightCandidate) -> float:
    return (
        max(0.0, c.health_score / 100.0)
        * max(0.0, c.decay_multiplier)
        * max(0.0, min(1.0, c.regime_match))
        * max(0.0, 1.0 - min(1.0, c.correlation_penalty))
    )


class DynamicWeightOptimizer:
    """Computes advisory target weights from health/decay/regime/correlation signals."""

    def __init__(self, *, max_weight: float = 0.25) -> None:
        self.max_weight = max_weight

    def propose(self, candidates: Sequence[WeightCandidate]) -> WeightProposal:
        scores = {c.alpha_id: _score(c) for c in candidates}
        total = sum(scores.values())
        if total <= _EPS:
            weights = dict.fromkeys(scores, 0.0)
            return WeightProposal(
                weights=weights, rationale="no healthy alpha; recommend zero allocation"
            )
        weights = {cid: s / total for cid, s in scores.items()}
        weights = self._cap_and_renormalize(weights)
        return WeightProposal(
            weights=weights,
            rationale="allocate toward stronger/healthier alphas (Portfolio Engine approval req.)",
        )

    def _cap_and_renormalize(self, weights: dict[str, float]) -> dict[str, float]:
        w = dict(weights)
        for _ in range(100):
            over = {i: v for i, v in w.items() if v > self.max_weight + _EPS}
            if not over:
                break
            excess = sum(v - self.max_weight for v in over.values())
            for i in over:
                w[i] = self.max_weight
            under = {i: w[i] for i in w if i not in over}
            headroom = sum(max(0.0, self.max_weight - v) for v in under.values())
            if headroom <= _EPS:
                break
            for i in under:
                w[i] += excess * max(0.0, self.max_weight - w[i]) / headroom
        return w
