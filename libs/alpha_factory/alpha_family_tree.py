"""Alpha family tree — track which research directions create winners.

A directed lineage of alphas: each node records its parent, the mutation that produced it, and its
performance. Used to learn which mutation paths (e.g. Trend_v1 -> v2 -> v3) compound into edge.
"""

from __future__ import annotations

from libs.alpha_factory.errors import AlphaFactoryError
from libs.alpha_factory.models import FamilyNode
from libs.core.time import to_iso8601, utcnow


class AlphaFamilyTree:
    """An in-memory lineage graph of alphas and their mutations."""

    def __init__(self) -> None:
        self._nodes: dict[str, FamilyNode] = {}

    def add(
        self,
        alpha_id: str,
        *,
        parent_id: str | None = None,
        mutation_type: str = "root",
        performance: float = 0.0,
    ) -> FamilyNode:
        if alpha_id in self._nodes:
            raise AlphaFactoryError(f"alpha {alpha_id} already in tree")
        if parent_id is not None and parent_id not in self._nodes:
            raise AlphaFactoryError(f"unknown parent {parent_id}")
        node = FamilyNode(
            alpha_id=alpha_id, parent_id=parent_id, mutation_type=mutation_type,
            created_at=to_iso8601(utcnow()), performance=performance,
        )
        self._nodes[alpha_id] = node
        return node

    def get(self, alpha_id: str) -> FamilyNode | None:
        return self._nodes.get(alpha_id)

    def lineage(self, alpha_id: str) -> list[FamilyNode]:
        """Root-to-node ancestry chain."""
        chain: list[FamilyNode] = []
        current = self._nodes.get(alpha_id)
        while current is not None:
            chain.append(current)
            current = self._nodes.get(current.parent_id) if current.parent_id else None
        return list(reversed(chain))

    def children(self, alpha_id: str) -> list[FamilyNode]:
        return [n for n in self._nodes.values() if n.parent_id == alpha_id]

    def best_lineage(self) -> list[FamilyNode]:
        """The ancestry of the highest-performing alpha (the winning research direction)."""
        if not self._nodes:
            return []
        best = max(self._nodes.values(), key=lambda n: n.performance)
        return self.lineage(best.alpha_id)
