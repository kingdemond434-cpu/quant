"""Multi-period, cost-aware glide-path optimizer."""

from __future__ import annotations

import pytest

from libs.portfolio.errors import PortfolioError
from libs.portfolio.models import PortfolioConstraints
from libs.portfolio.multiperiod import MultiPeriodOptimizer


def test_glide_path_converges_to_target() -> None:
    opt = MultiPeriodOptimizer(
        constraints=PortfolioConstraints(max_weight=1.0),
        max_step_turnover=0.1, cost_per_turnover=0.001,
    )
    plan = opt.plan(current={"A": 0.0, "B": 1.0}, target={"A": 0.5, "B": 0.5}, n_steps=20)
    final = plan.path[-1]
    assert final["A"] == pytest.approx(0.5, abs=1e-6)
    assert final["B"] == pytest.approx(0.5, abs=1e-6)
    assert plan.total_cost > 0


def test_step_turnover_is_bounded() -> None:
    opt = MultiPeriodOptimizer(
        constraints=PortfolioConstraints(max_weight=1.0), max_step_turnover=0.1
    )
    plan = opt.plan(current={"A": 0.0, "B": 1.0}, target={"A": 1.0, "B": 0.0}, n_steps=20)
    assert all(t <= 0.1 + 1e-9 for t in plan.step_turnover)
    assert len(plan.path) > 1  # could not jump in one step


def test_respects_max_weight_constraint() -> None:
    opt = MultiPeriodOptimizer(constraints=PortfolioConstraints(max_weight=0.3))
    plan = opt.plan(current={"A": 0.0}, target={"A": 1.0}, n_steps=10)
    assert all(step["A"] <= 0.3 + 1e-9 for step in plan.path)


def test_already_at_target_is_cheap() -> None:
    opt = MultiPeriodOptimizer(constraints=PortfolioConstraints(max_weight=1.0))
    plan = opt.plan(current={"A": 0.5, "B": 0.5}, target={"A": 0.5, "B": 0.5}, n_steps=5)
    assert plan.total_cost == pytest.approx(0.0)


def test_rejects_zero_steps() -> None:
    with pytest.raises(PortfolioError):
        MultiPeriodOptimizer().plan(current={"A": 1.0}, target={"A": 0.0}, n_steps=0)
