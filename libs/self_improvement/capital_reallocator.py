"""Capital reallocator — proposes (does not execute) capital moves weak -> strong.

Every proposed move is an :class:`ImprovementAction` that requires Portfolio Engine approval and
is bounded by ``max_move_frac`` so no single reallocation is abrupt. No capital is moved here.
"""

from __future__ import annotations

from collections.abc import Mapping

from libs.self_improvement.models import ImprovementAction, ImprovementActionType

_EPS = 1e-6


class CapitalReallocator:
    """Recommends bounded capital reallocations toward the proposed target weights."""

    def __init__(self, *, max_move_frac: float = 0.20) -> None:
        self.max_move_frac = max_move_frac

    def propose(
        self,
        current_weights: Mapping[str, float],
        target_weights: Mapping[str, float],
        *,
        total_capital: float,
    ) -> list[ImprovementAction]:
        ids = sorted(set(current_weights) | set(target_weights))
        actions: list[ImprovementAction] = []
        for alpha_id in ids:
            current = float(current_weights.get(alpha_id, 0.0))
            target = float(target_weights.get(alpha_id, 0.0))
            delta = target - current
            delta = max(-self.max_move_frac, min(self.max_move_frac, delta))  # bounded move
            if abs(delta) <= _EPS:
                continue
            actions.append(
                ImprovementAction(
                    type=ImprovementActionType.CAPITAL_REALLOCATION,
                    target_id=alpha_id,
                    rationale="move capital toward higher-quality alpha (bounded)",
                    detail={
                        "from_weight": current,
                        "to_weight": current + delta,
                        "capital_delta": delta * total_capital,
                    },
                    requires_portfolio_approval=True,
                )
            )
        return actions
