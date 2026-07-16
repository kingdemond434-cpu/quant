"""Alpha lifecycle manager — registry + state machine + health/decay + audit + successors.

Ties the pieces together: registers candidates, enforces lifecycle transitions (writing an
immutable audit event for each), tracks live performance, evaluates health and decay (with
optional automatic downgrade), and recommends successors when an alpha decays.
"""

from __future__ import annotations

from typing import Any

from libs.alpha.card import (
    AlphaCard,
    AlphaEvent,
    AlphaPerformance,
    ExpectedMetrics,
    LiveMetrics,
    NewAlpha,
)
from libs.alpha.decay import DecayResult, detect_decay
from libs.alpha.errors import AlphaError
from libs.alpha.health import AlphaHealth, calculate_alpha_health
from libs.alpha.registry import AlphaAuditTrail, AlphaCardStore, PerformanceTracker
from libs.alpha.state import AlphaState, assert_transition, promote_target
from libs.alpha.successor import recommend_successors as _recommend_successors
from libs.core.ids import generate_id
from libs.core.time import to_iso8601, utcnow

_UPDATABLE: frozenset[str] = frozenset(
    {
        "name", "market", "category", "thesis", "entry_logic", "exit_logic",
        "expected_cagr", "expected_sharpe", "expected_drawdown", "dsr", "pbo",
        "cpcv", "walk_forward", "holdout", "live_cagr", "live_sharpe", "live_drawdown",
        "decay_score", "extra",
    }
)
_SEVERITY: dict[AlphaState, int] = {
    AlphaState.ACTIVE: 0,
    AlphaState.WATCH: 1,
    AlphaState.DECAYING: 2,
    AlphaState.RETIREMENT_CANDIDATE: 3,
}
_STATE_BY_SEVERITY: dict[int, AlphaState] = {sev: state for state, sev in _SEVERITY.items()}


class AlphaLifecycleManager:
    """The orchestration entry point for alpha lifecycle management."""

    def __init__(self, db: Any) -> None:
        self.cards = AlphaCardStore(db)
        self.audit = AlphaAuditTrail(db)
        self.performance = PerformanceTracker(db)

    # ------------------------------------------------------------- helpers

    def _require(self, alpha_id: str) -> AlphaCard:
        card = self.cards.get(alpha_id)
        if card is None:
            raise AlphaError(f"unknown alpha {alpha_id}")
        return card

    # ----------------------------------------------------------- registration

    def register_alpha(self, new: NewAlpha) -> AlphaCard:
        """Register a new alpha as a CANDIDATE and journal its creation."""
        now = to_iso8601(utcnow())
        card = AlphaCard(
            id=generate_id("alpha"), created_at=now, updated_at=now, name=new.name,
            market=new.market, category=new.category, thesis=new.thesis,
            entry_logic=new.entry_logic, exit_logic=new.exit_logic,
            expected_cagr=new.expected_cagr, expected_sharpe=new.expected_sharpe,
            expected_drawdown=new.expected_drawdown, dsr=new.dsr, pbo=new.pbo,
            cpcv=new.cpcv, walk_forward=new.walk_forward, holdout=new.holdout,
            deployment_date=None, retirement_date=None, live_cagr=None, live_sharpe=None,
            live_drawdown=None, decay_score=0.0, status=AlphaState.CANDIDATE,
            successor_id=None, predecessor_id=new.predecessor_id, extra=dict(new.extra),
        )
        self.cards.insert(card)
        self.audit.append(card.id, "creation", to_status=AlphaState.CANDIDATE)
        if new.predecessor_id is not None:
            self._link_successor(new.predecessor_id, card.id)
        return card

    def _link_successor(self, predecessor_id: str, successor_id: str) -> None:
        predecessor = self.cards.get(predecessor_id)
        if predecessor is None:
            return
        updated = predecessor.model_copy(
            update={"successor_id": successor_id, "updated_at": to_iso8601(utcnow())}
        )
        self.cards.update(updated)
        self.audit.append(
            predecessor_id, "successor_assigned", detail={"successor_id": successor_id}
        )

    # ------------------------------------------------------------- updates

    def update_alpha(self, alpha_id: str, **fields: Any) -> AlphaCard:
        """Update mutable card fields (never the status — use transitions)."""
        card = self._require(alpha_id)
        unknown = set(fields) - _UPDATABLE
        if unknown:
            raise AlphaError(f"cannot update fields: {sorted(unknown)}")
        updated = card.model_copy(update={**fields, "updated_at": to_iso8601(utcnow())})
        self.cards.update(updated)
        self.audit.append(alpha_id, "update", detail={"fields": sorted(fields)})
        return updated

    # ----------------------------------------------------------- transitions

    def transition(
        self,
        alpha_id: str,
        to_state: AlphaState,
        *,
        reason: str,
        event_type: str = "status_change",
        detail: dict[str, Any] | None = None,
    ) -> AlphaCard:
        """Move an alpha to ``to_state`` if the transition is legal; journal the change."""
        card = self._require(alpha_id)
        assert_transition(card.status, to_state)
        now = to_iso8601(utcnow())
        changes: dict[str, Any] = {"status": to_state, "updated_at": now}
        if to_state is AlphaState.ACTIVE and card.deployment_date is None:
            changes["deployment_date"] = now
        if to_state is AlphaState.RETIRED:
            changes["retirement_date"] = now
        updated = card.model_copy(update=changes)
        self.cards.update(updated)
        self.audit.append(
            alpha_id, event_type, from_status=card.status, to_status=to_state,
            detail={"reason": reason, **(detail or {})},
        )
        return updated

    def promote_alpha(self, alpha_id: str, *, reason: str = "promote") -> AlphaCard:
        """Promote an alpha to its next lifecycle state."""
        card = self._require(alpha_id)
        return self.transition(
            alpha_id, promote_target(card.status), reason=reason, event_type="promotion"
        )

    def retire_alpha(
        self, alpha_id: str, *, reason: str = "retire", successor_id: str | None = None
    ) -> AlphaCard:
        """Retire an alpha (optionally recording its successor)."""
        retired = self.transition(
            alpha_id, AlphaState.RETIRED, reason=reason, event_type="retirement"
        )
        if successor_id is not None:
            retired = retired.model_copy(
                update={"successor_id": successor_id, "updated_at": to_iso8601(utcnow())}
            )
            self.cards.update(retired)
            self._link_predecessor(successor_id, alpha_id)
            self.audit.append(alpha_id, "successor_assigned", detail={"successor_id": successor_id})
        return retired

    def _link_predecessor(self, alpha_id: str, predecessor_id: str) -> None:
        card = self.cards.get(alpha_id)
        if card is None:
            return
        self.cards.update(
            card.model_copy(
                update={"predecessor_id": predecessor_id, "updated_at": to_iso8601(utcnow())}
            )
        )

    # ----------------------------------------------------- performance/health

    def record_performance(self, alpha_id: str, live: LiveMetrics) -> AlphaPerformance:
        """Record a live-performance snapshot and refresh the card's live metrics."""
        card = self._require(alpha_id)
        snapshot = self.performance.record(alpha_id, live)
        self.cards.update(
            card.model_copy(
                update={
                    "live_cagr": live.cagr, "live_sharpe": live.sharpe,
                    "live_drawdown": live.max_drawdown, "updated_at": to_iso8601(utcnow()),
                }
            )
        )
        self.audit.append(
            alpha_id, "performance",
            detail={"sharpe": live.sharpe, "cagr": live.cagr, "drawdown": live.max_drawdown},
        )
        return snapshot

    def evaluate_health(self, alpha_id: str, live: LiveMetrics) -> AlphaHealth:
        """Compute the alpha's health (live vs expected)."""
        return calculate_alpha_health(ExpectedMetrics.from_card(self._require(alpha_id)), live)

    def evaluate_decay(
        self, alpha_id: str, live: LiveMetrics, *, auto_transition: bool = True
    ) -> DecayResult:
        """Score decay, persist it, and (optionally) auto-downgrade the lifecycle state."""
        card = self._require(alpha_id)
        result = detect_decay(ExpectedMetrics.from_card(card), live)
        self.cards.update(
            card.model_copy(
                update={"decay_score": result.decay_score, "updated_at": to_iso8601(utcnow())}
            )
        )
        self.audit.append(
            alpha_id, "decay_evaluated",
            detail={"decay_score": result.decay_score, "recommended": result.recommended_state},
        )
        if auto_transition:
            self._maybe_downgrade(card.status, alpha_id, result.recommended_state)
        return result

    def _maybe_downgrade(
        self, current: AlphaState, alpha_id: str, recommended: AlphaState
    ) -> None:
        cur_sev = _SEVERITY.get(current, -1)
        rec_sev = _SEVERITY.get(recommended, -1)
        if cur_sev < 0 or rec_sev <= cur_sev:
            return  # only auto-move downward, and only from a live state
        target = _STATE_BY_SEVERITY[min(cur_sev + 1, rec_sev)]  # step one level (gradual)
        try:
            assert_transition(current, target)
        except AlphaError:
            return
        self.transition(alpha_id, target, reason="auto-decay", event_type="status_change")
        if target is AlphaState.DECAYING:
            successors = self.recommend_successors(alpha_id)
            self.audit.append(
                alpha_id, "successor_recommendation",
                detail={"successors": [c.id for c in successors]},
            )

    # ------------------------------------------------------------ successors

    def recommend_successors(self, alpha_id: str, *, top_n: int = 3) -> list[AlphaCard]:
        """Rank eligible replacements for an alpha (same market or category)."""
        card = self._require(alpha_id)
        return _recommend_successors(self.cards.list_all(), card, top_n=top_n)

    # ---------------------------------------------------------------- queries

    def get_alpha(self, alpha_id: str) -> AlphaCard | None:
        return self.cards.get(alpha_id)

    def audit_trail(self, alpha_id: str) -> list[AlphaEvent]:
        return self.audit.list(alpha_id)

    def list_all(self) -> list[AlphaCard]:
        return self.cards.list_all()

    def list_by_status(self, status: AlphaState) -> list[AlphaCard]:
        return self.cards.list_by_status(status)

    def list_active(self) -> list[AlphaCard]:
        return self.cards.list_by_status(AlphaState.ACTIVE)

    def list_candidates(self) -> list[AlphaCard]:
        return self.cards.list_by_status(AlphaState.CANDIDATE)
