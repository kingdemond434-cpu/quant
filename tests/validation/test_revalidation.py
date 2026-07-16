"""Walk-forward governance and automated revalidation (fail-closed)."""

from __future__ import annotations

import numpy as np

from libs.self_improvement.models import DecayLevel
from libs.validation.revalidation import (
    RevalidationController,
    RevalidationTrigger,
    WalkForwardEngine,
    WalkForwardStatus,
)


def _passing_report() -> object:
    rng = np.random.default_rng(0)
    returns = 0.01 + rng.normal(0.0, 0.001, size=200)  # strong positive drift
    return WalkForwardEngine().evaluate(returns, n_splits=4, test_size=20)


def test_walk_forward_passes_on_persistent_edge() -> None:
    report = WalkForwardEngine().evaluate(
        0.01 + np.random.default_rng(1).normal(0, 0.001, 200), n_splits=4, test_size=20
    )
    assert report.status is WalkForwardStatus.PASSED
    assert report.stability == 1.0
    assert report.oos_sharpe > 0
    assert 0.0 <= report.walk_forward_score <= 100.0


def test_walk_forward_fails_on_no_edge() -> None:
    report = WalkForwardEngine().evaluate(
        np.random.default_rng(2).normal(-0.001, 0.02, 200), n_splits=4, test_size=20,
        min_oos_sharpe=0.5,
    )
    assert report.status is WalkForwardStatus.FAILED


def test_revalidation_allows_capital_only_when_passed() -> None:
    report = _passing_report()
    decision = RevalidationController().assess(report)  # type: ignore[arg-type]
    assert decision.production_capital_allowed is True
    assert decision.required is False


def test_hard_trigger_downgrades_to_stale_and_blocks() -> None:
    report = _passing_report()
    decision = RevalidationController().assess(report, drift=True)  # type: ignore[arg-type]
    assert decision.required is True
    assert RevalidationTrigger.DRIFT in decision.triggers
    assert decision.status is WalkForwardStatus.STALE
    assert decision.production_capital_allowed is False


def test_dead_signal_blocks_capital() -> None:
    report = _passing_report()
    decision = RevalidationController().assess(  # type: ignore[arg-type]
        report, decay_level=DecayLevel.DEAD
    )
    assert RevalidationTrigger.SIGNAL_DEAD in decision.triggers
    assert decision.production_capital_allowed is False


def test_soft_trigger_requires_reval_but_keeps_capital() -> None:
    report = _passing_report()
    decision = RevalidationController().assess(  # type: ignore[arg-type]
        report, sharpe_deteriorated=True, decay_level=DecayLevel.DECAYING, age_days=40.0
    )
    assert decision.required is True
    assert decision.production_capital_allowed is True  # soft triggers do not cut capital
    assert RevalidationTrigger.SHARPE_DETERIORATION in decision.triggers
    assert RevalidationTrigger.SIGNAL_DECAYING in decision.triggers
    assert RevalidationTrigger.STALE in decision.triggers


def test_failed_report_never_allows_capital() -> None:
    failed = WalkForwardEngine().evaluate(
        np.random.default_rng(3).normal(-0.002, 0.02, 200), n_splits=4, test_size=20,
        min_oos_sharpe=1.0,
    )
    decision = RevalidationController().assess(failed)
    assert decision.production_capital_allowed is False
