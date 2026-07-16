"""Automatic successor pools over the alpha lifecycle.

Maintains Candidate / Probation / Active pools and continuously generates ranked replacement
candidates for alphas that will eventually retire (drawn from the same market or family).
"""

from __future__ import annotations

from collections.abc import Sequence

from libs.alpha.card import AlphaCard, NewAlpha
from libs.alpha.manager import AlphaLifecycleManager
from libs.alpha.state import AlphaState


class SuccessorPools:
    """A thin pool view + replacement generator on top of the lifecycle manager."""

    def __init__(self, manager: AlphaLifecycleManager) -> None:
        self.manager = manager

    @property
    def candidate_pool(self) -> list[AlphaCard]:
        return self.manager.list_by_status(AlphaState.CANDIDATE)

    @property
    def probation_pool(self) -> list[AlphaCard]:
        return self.manager.list_by_status(AlphaState.PROBATION)

    @property
    def active_pool(self) -> list[AlphaCard]:
        return self.manager.list_by_status(AlphaState.ACTIVE)

    def register_candidates(self, specs: Sequence[NewAlpha]) -> list[AlphaCard]:
        """Add new candidates to the pool."""
        return [self.manager.register_alpha(spec) for spec in specs]

    def replacements_for(self, alpha_id: str, *, top_n: int = 3) -> list[AlphaCard]:
        """Ranked replacement candidates for an alpha (same market or category)."""
        return self.manager.recommend_successors(alpha_id, top_n=top_n)

    def summary(self) -> dict[str, int]:
        return {
            "candidate": len(self.candidate_pool),
            "probation": len(self.probation_pool),
            "active": len(self.active_pool),
        }
