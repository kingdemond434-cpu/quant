"""Research graph — relationships across thousands of experiments.

A typed directed graph: Idea -> Feature -> Signal -> Factor -> Alpha -> Performance. It lets the
factory mine patterns, e.g. which features recur in the lineages of high-performing alphas.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

from libs.alpha_factory.errors import AlphaFactoryError

_NODE_TYPES = frozenset({"idea", "feature", "signal", "factor", "alpha", "performance"})


@dataclass
class _Node:
    node_id: str
    node_type: str
    attrs: dict[str, Any] = field(default_factory=dict)


class ResearchGraph:
    """A typed directed graph over the research pipeline."""

    def __init__(self) -> None:
        self._nodes: dict[str, _Node] = {}
        self._out: dict[str, set[str]] = {}
        self._in: dict[str, set[str]] = {}

    def add_node(self, node_id: str, node_type: str, **attrs: Any) -> None:
        if node_type not in _NODE_TYPES:
            raise AlphaFactoryError(f"unknown node_type {node_type!r}")
        self._nodes[node_id] = _Node(node_id, node_type, dict(attrs))
        self._out.setdefault(node_id, set())
        self._in.setdefault(node_id, set())

    def add_edge(self, src: str, dst: str) -> None:
        if src not in self._nodes or dst not in self._nodes:
            raise AlphaFactoryError("both nodes must exist before adding an edge")
        self._out[src].add(dst)
        self._in[dst].add(src)

    def neighbors(self, node_id: str) -> list[str]:
        return sorted(self._out.get(node_id, set()))

    def predecessors(self, node_id: str) -> list[str]:
        return sorted(self._in.get(node_id, set()))

    def nodes_of_type(self, node_type: str) -> list[str]:
        return sorted(n.node_id for n in self._nodes.values() if n.node_type == node_type)

    def path_exists(self, src: str, dst: str) -> bool:
        if src not in self._nodes or dst not in self._nodes:
            return False
        seen, queue = {src}, deque([src])
        while queue:
            cur = queue.popleft()
            if cur == dst:
                return True
            for nxt in self._out.get(cur, set()):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        return False

    def feature_importance(self, *, min_performance: float) -> dict[str, int]:
        """Count features that feed into alphas whose performance node clears the threshold."""
        counts: dict[str, int] = {}
        winners = [
            n.node_id
            for n in self._nodes.values()
            if n.node_type == "performance" and float(n.attrs.get("value", 0.0)) >= min_performance
        ]
        for perf in winners:
            for feature in self._ancestors_of_type(perf, "feature"):
                counts[feature] = counts.get(feature, 0) + 1
        return counts

    def _ancestors_of_type(self, node_id: str, node_type: str) -> set[str]:
        found: set[str] = set()
        seen, queue = {node_id}, deque([node_id])
        while queue:
            cur = queue.popleft()
            for prev in self._in.get(cur, set()):
                if prev not in seen:
                    seen.add(prev)
                    queue.append(prev)
                    if self._nodes[prev].node_type == node_type:
                        found.add(prev)
        return found
