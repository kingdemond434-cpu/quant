"""Research allocator — split the research budget across categories.

Allocates effort using historical success (from research memory), current regime/portfolio needs,
and crowding. Output is a recommendation only (fractions summing to ~1); the factory never spends
production capital.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from libs.alpha_factory.models import AllocationResult, AlphaCategory
from libs.alpha_factory.research_memory import ResearchMemory

_DEFAULT_SUCCESS = 0.5


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class ResearchAllocator:
    """Recommends a research-budget split across alpha categories."""

    def allocate(
        self,
        categories: Sequence[AlphaCategory],
        *,
        memory: ResearchMemory | None = None,
        regime_gaps: Mapping[str, float] | None = None,
        portfolio_gaps: Mapping[str, float] | None = None,
        crowding: Mapping[str, float] | None = None,
    ) -> AllocationResult:
        regime_gaps = regime_gaps or {}
        portfolio_gaps = portfolio_gaps or {}
        crowding = crowding or {}

        raw: dict[str, float] = {}
        rationale: dict[str, str] = {}
        for category in categories:
            key = category.value
            success = memory.success_rate(key) if memory is not None else _DEFAULT_SUCCESS
            need = _clip01((regime_gaps.get(key, 0.0) + portfolio_gaps.get(key, 0.0)) / 2.0)
            crowd = _clip01(crowding.get(key, 0.0))
            weight = max(0.0, 0.4 * success + 0.3 * need + 0.3 * (1.0 - crowd))
            raw[key] = weight
            rationale[key] = (
                f"success={success:.2f}, need={need:.2f}, crowding={crowd:.2f}"
            )

        total = sum(raw.values())
        if total <= 0.0:
            equal = 1.0 / len(raw) if raw else 0.0
            allocations = dict.fromkeys(raw, equal)
        else:
            allocations = {k: v / total for k, v in raw.items()}
        return AllocationResult(allocations=allocations, rationale=rationale)
