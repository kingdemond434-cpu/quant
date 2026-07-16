"""Marketplace view, drift detection, and the per-alpha kill switch."""

from __future__ import annotations

import numpy as np
from tests.self_improvement.conftest import register

from libs.alpha.manager import AlphaLifecycleManager
from libs.alpha.state import AlphaState
from libs.self_improvement.drift_detector import (
    AlphaDriftDetector,
    population_stability_index,
)
from libs.self_improvement.kill_switch import AlphaKillSwitch
from libs.self_improvement.marketplace import AlphaMarketplace
from libs.self_improvement.models import AlphaCategory, ImprovementActionType
from libs.store.connection import Database


def test_marketplace_status_category_and_summary(
    db: Database, manager: AlphaLifecycleManager
) -> None:
    a = register(manager, name="gold_trend", category="trend_following")
    register(manager, name="fx_carry", category="carry")
    # promote one alpha to production: candidate -> probation -> active
    manager.promote_alpha(a.id)
    manager.promote_alpha(a.id)

    market = AlphaMarketplace(db)
    assert len(market.all()) == 2
    production = market.production()
    assert [c.id for c in production] == [a.id]
    assert market.by_status(AlphaState.CANDIDATE)
    summary = market.summary()
    assert summary["active"] == 1
    assert summary["candidate"] == 1

    grouped = market.by_category()
    assert AlphaCategory.TREND_FOLLOWING in grouped
    assert AlphaCategory.CARRY in grouped


def test_alpha_category_from_text_normalizes_and_falls_back() -> None:
    assert AlphaCategory.from_text("Trend Following") is AlphaCategory.TREND_FOLLOWING
    assert AlphaCategory.from_text("totally_unknown") is AlphaCategory.OTHER


def test_psi_returns_zero_for_tiny_samples() -> None:
    assert population_stability_index(np.array([1.0]), np.array([1.0, 2.0])) == 0.0
    # a degenerate (single-valued) expected sample yields a single bin edge -> 0.0
    assert population_stability_index(np.zeros(50), np.zeros(50)) == 0.0


def test_psi_low_for_same_distribution_high_for_shift() -> None:
    rng = np.random.default_rng(0)
    base = rng.normal(0.0, 1.0, size=2000)
    same = rng.normal(0.0, 1.0, size=2000)
    shifted = rng.normal(5.0, 1.0, size=2000)
    assert population_stability_index(base, same) < 0.1
    assert population_stability_index(base, shifted) > 0.25


def test_drift_detector_flags_shift() -> None:
    rng = np.random.default_rng(1)
    detector = AlphaDriftDetector(psi_threshold=0.2)
    no_drift = detector.detect(rng.normal(0, 1, 2000), rng.normal(0, 1, 2000))
    assert no_drift.drifted is False
    assert bool(no_drift) is True  # truthy when healthy
    drift = detector.detect(rng.normal(0, 1, 2000), rng.normal(4, 1, 2000))
    assert drift.drifted is True
    assert "revalidation" in drift.recommendation
    assert bool(drift) is False


def test_kill_switch_trip_and_reset() -> None:
    ks = AlphaKillSwitch()
    action = ks.trip("alpha_1", reason="anomalous live behavior")
    assert action.type is ImprovementActionType.PAUSE
    assert action.requires_portfolio_approval is True
    assert ks.is_tripped("alpha_1")
    assert "alpha_1" in ks.tripped
    ks.reset("alpha_1")
    assert not ks.is_tripped("alpha_1")
