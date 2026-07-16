"""Lifecycle apply-side helpers (reuse the existing AlphaLifecycleManager).

These are the *approved* application of Stage 13 recommendations. Retirement is applied via the
manager (audited, archived — never deleted). Reactivation re-enters a fresh CANDIDATE linked to
the retired alpha as predecessor, so it must pass validation again (no bypass).
"""

from __future__ import annotations

from libs.alpha.card import AlphaCard, NewAlpha
from libs.alpha.manager import AlphaLifecycleManager


def apply_retirement(
    manager: AlphaLifecycleManager, alpha_id: str, *, reason: str = "stage13: decay confirmed"
) -> AlphaCard:
    """Retire an alpha through the lifecycle manager (audited; archived, not deleted)."""
    return manager.retire_alpha(alpha_id, reason=reason)


def apply_reactivation(
    manager: AlphaLifecycleManager,
    retired: AlphaCard,
    *,
    reason: str = "stage13: market structure changed",
) -> AlphaCard:
    """Re-enter a retired alpha as a fresh CANDIDATE (must re-pass validation; no bypass)."""
    spec = NewAlpha(
        name=f"{retired.name}_reactivated",
        market=retired.market,
        category=retired.category,
        thesis=f"{retired.thesis} [reactivation: {reason}]",
        entry_logic=retired.entry_logic,
        exit_logic=retired.exit_logic,
        expected_cagr=retired.expected_cagr,
        expected_sharpe=retired.expected_sharpe,
        expected_drawdown=retired.expected_drawdown,
        predecessor_id=retired.id,
    )
    return manager.register_alpha(spec)
