"""Tests for the CAGR optimizer, acceptance gates, and successor pools."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from migrations import MIGRATIONS
from tests.discovery.conftest import make_returns

from libs.alpha.card import NewAlpha
from libs.alpha.manager import AlphaLifecycleManager
from libs.discovery.acceptance import alpha_acceptance, portfolio_acceptance
from libs.discovery.cagr_optimizer import optimize_allocation
from libs.discovery.pools import SuccessorPools
from libs.store.connection import Database
from libs.store.migrations import run_migrations


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database(tmp_path / "sor.sqlite")
    run_migrations(database, MIGRATIONS)
    yield database
    database.close()


def test_optimizer_noise_allocates_safely() -> None:
    result = optimize_allocation(
        {"a": make_returns(mu=0.0, sd=0.01, seed=1), "b": make_returns(mu=0.0, sd=0.01, seed=2)},
        n_sims=300,
    )
    assert result.passed  # survival holds (it de-risks toward zero on no edge)
    assert 0.0 <= result.leverage <= 1.0
    assert result.survival_probability >= 0.95


def test_optimizer_deploys_on_real_edge() -> None:
    result = optimize_allocation(
        {
            "a": make_returns(mu=0.002, sd=0.006, seed=3),
            "b": make_returns(mu=0.0018, sd=0.006, seed=4),
        },
        n_sims=300,
    )
    assert result.leverage > 0.0
    assert result.expected_log_growth > 0.0
    assert result.worst_case_drawdown < 0.20


def test_optimizer_never_levers_beyond_cap() -> None:
    result = optimize_allocation(
        {"a": make_returns(mu=0.01, sd=0.002, seed=5)}, n_sims=200, leverage_cap=1.0
    )
    assert result.leverage <= 1.0
    assert sum(result.weights.values()) <= 1.0 + 1e-9


def test_alpha_acceptance_gate() -> None:
    passing = alpha_acceptance(
        dsr_pass=True, pbo_pass=True, cpcv_pass=True, walk_forward_pass=True, holdout_pass=True,
        cost_pass=True, parameter_stability_pass=True, fragility_pass=True, capacity_pass=True,
        tail_pass=True, stress_pass=True, regime_pass=True,
    )
    assert passing.passed
    failing = alpha_acceptance(
        dsr_pass=False, pbo_pass=True, cpcv_pass=True, walk_forward_pass=True, holdout_pass=True,
        cost_pass=True, parameter_stability_pass=True, fragility_pass=True, capacity_pass=True,
        tail_pass=True, stress_pass=True, regime_pass=True,
    )
    assert not failing.passed and "dsr" in failing.reasons


def test_portfolio_acceptance_survival_and_drawdown() -> None:
    ok = portfolio_acceptance(
        survival_probability=0.97, max_drawdown=0.12, dsr_pass=True, cpcv_pass=True,
        pbo_pass=True, walk_forward_pass=True, holdout_pass=True, tail_pass=True, stress_pass=True,
        failure_independent=True, family_balanced=True, regime_diversified=True,
    )
    assert ok.passed
    bad = portfolio_acceptance(
        survival_probability=0.90, max_drawdown=0.25, dsr_pass=True, cpcv_pass=True,
        pbo_pass=True, walk_forward_pass=True, holdout_pass=True, tail_pass=True, stress_pass=True,
        failure_independent=True, family_balanced=True, regime_diversified=True,
    )
    assert not bad.passed
    assert "survival>95%" in bad.reasons
    assert "max_drawdown<20%" in bad.reasons


def test_successor_pools(db: Database) -> None:
    manager = AlphaLifecycleManager(db)
    pools = SuccessorPools(manager)
    pools.register_candidates(
        [
            NewAlpha(
                name=f"a{i}", market="XAUUSD", category="session", thesis="t",
                entry_logic="e", exit_logic="x", expected_sharpe=1.0 + i,
            )
            for i in range(3)
        ]
    )
    assert len(pools.candidate_pool) == 3
    summary = pools.summary()
    assert summary["candidate"] == 3
    target = pools.candidate_pool[0]
    replacements = pools.replacements_for(target.id, top_n=2)
    assert all(r.id != target.id for r in replacements)
