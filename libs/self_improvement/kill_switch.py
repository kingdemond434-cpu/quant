"""Per-alpha kill switch — pauses an alpha (recommendation; capital stop needs approval)."""

from __future__ import annotations

from libs.self_improvement.models import ImprovementAction, ImprovementActionType


class AlphaKillSwitch:
    """Tracks paused alphas and emits pause recommendations (fail-closed on uncertainty)."""

    def __init__(self) -> None:
        self._tripped: set[str] = set()

    def trip(self, alpha_id: str, *, reason: str) -> ImprovementAction:
        self._tripped.add(alpha_id)
        return ImprovementAction(
            type=ImprovementActionType.PAUSE,
            target_id=alpha_id,
            rationale=reason,
            detail={"paused": True},
            requires_portfolio_approval=True,  # taking capital to zero is a Portfolio Engine action
        )

    def reset(self, alpha_id: str) -> None:
        self._tripped.discard(alpha_id)

    def is_tripped(self, alpha_id: str) -> bool:
        return alpha_id in self._tripped

    @property
    def tripped(self) -> frozenset[str]:
        return frozenset(self._tripped)
