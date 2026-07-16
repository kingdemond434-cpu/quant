"""``libs.alpha`` — alpha lifecycle management.

Registry + cards + metadata, a 7-state lifecycle state machine, health monitoring, decay
detection, ranking, successor recommendations, live performance tracking, and an append-only
audit trail — orchestrated by :class:`AlphaLifecycleManager`.
"""

from __future__ import annotations

from libs.alpha.card import (
    AlphaCard,
    AlphaEvent,
    AlphaPerformance,
    ExpectedMetrics,
    LiveMetrics,
    NewAlpha,
)
from libs.alpha.decay import DecayResult, detect_decay
from libs.alpha.errors import AlphaError, AlphaStateError
from libs.alpha.health import AlphaHealth, calculate_alpha_health
from libs.alpha.manager import AlphaLifecycleManager
from libs.alpha.ranking import RankedAlpha, rank_alphas
from libs.alpha.registry import AlphaAuditTrail, AlphaCardStore, PerformanceTracker
from libs.alpha.state import (
    ALLOWED_TRANSITIONS,
    AlphaState,
    assert_transition,
    can_transition,
    promote_target,
)
from libs.alpha.successor import recommend_successors

__all__ = [  # noqa: RUF022  # grouped by concern
    # state machine
    "AlphaState",
    "ALLOWED_TRANSITIONS",
    "can_transition",
    "assert_transition",
    "promote_target",
    # cards / models
    "NewAlpha",
    "AlphaCard",
    "ExpectedMetrics",
    "LiveMetrics",
    "AlphaEvent",
    "AlphaPerformance",
    # health / decay / ranking / successor
    "calculate_alpha_health",
    "AlphaHealth",
    "detect_decay",
    "DecayResult",
    "rank_alphas",
    "RankedAlpha",
    "recommend_successors",
    # store + manager
    "AlphaCardStore",
    "AlphaAuditTrail",
    "PerformanceTracker",
    "AlphaLifecycleManager",
    # errors
    "AlphaError",
    "AlphaStateError",
]
