"""Signal crowding — penalize positions that are correlated, concentrated, or crowded.

A higher ``crowding_score`` (0-100) is worse. It blends internal redundancy (how correlated the
contributing alphas are), factor overlap with the existing book, and an external crowding proxy.
"""

from __future__ import annotations

from libs.signal_engine.models import CrowdingResult


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class SignalCrowdingEngine:
    """Scores how crowded a candidate is; above ``threshold`` it is unacceptable."""

    def __init__(self, *, threshold: float = 70.0) -> None:
        self.threshold = threshold

    def assess(
        self,
        *,
        avg_alpha_correlation: float,
        factor_overlap: float,
        public_crowding: float = 0.0,
    ) -> CrowdingResult:
        score = 100.0 * _clip01(
            0.4 * avg_alpha_correlation + 0.3 * factor_overlap + 0.3 * public_crowding
        )
        return CrowdingResult(crowding_score=score, acceptable=score <= self.threshold)
