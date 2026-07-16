"""Alpha marketplace — the master registry view (reuses ``AlphaCardStore``).

Single source of truth: the marketplace is a read/grouping view over the existing
``alpha_cards`` registry. Production status is the lifecycle ACTIVE state; no alpha reaches
production without passing through the lifecycle (registry approval).
"""

from __future__ import annotations

from libs.alpha.card import AlphaCard
from libs.alpha.registry import AlphaCardStore
from libs.alpha.state import AlphaState
from libs.self_improvement.models import AlphaCategory
from libs.store.connection import Database


class AlphaMarketplace:
    """A categorized, status-aware view of the master alpha registry."""

    def __init__(self, db: Database) -> None:
        self.store = AlphaCardStore(db)

    def all(self) -> list[AlphaCard]:
        return self.store.list_all()

    def by_status(self, state: AlphaState) -> list[AlphaCard]:
        return self.store.list_by_status(state)

    def production(self) -> list[AlphaCard]:
        """Production alphas are those in the ACTIVE lifecycle state."""
        return self.store.list_by_status(AlphaState.ACTIVE)

    def by_category(self) -> dict[AlphaCategory, list[AlphaCard]]:
        grouped: dict[AlphaCategory, list[AlphaCard]] = {}
        for card in self.store.list_all():
            grouped.setdefault(AlphaCategory.from_text(card.category), []).append(card)
        return grouped

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for card in self.store.list_all():
            counts[card.status.value] = counts.get(card.status.value, 0) + 1
        return counts
