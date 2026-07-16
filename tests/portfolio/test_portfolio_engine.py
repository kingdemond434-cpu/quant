"""Tests for build_portfolio, the engine audit trail, and portfolio analytics."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from migrations import MIGRATIONS
from tests.portfolio.conftest import constant_correlation, make_alpha, synthetic_returns

from libs.portfolio.analytics import portfolio_analytics
from libs.portfolio.engine import PortfolioEngine, build_portfolio
from libs.portfolio.errors import PortfolioError
from libs.portfolio.models import PortfolioConstraints, StrategyType
from libs.risk.instruments import Factor
from libs.store.audit import verify_audit_chain
from libs.store.connection import Database
from libs.store.migrations import run_migrations

_LOOSE = PortfolioConstraints(max_weight=0.5, max_factor_weight=1.0, max_asset_class_weight=1.0)


def _diversified_alphas() -> list:
    return [
        make_alpha("gold", factor=Factor.PRECIOUS_METALS, strategy_type=StrategyType.TREND),
        make_alpha("eur", factor=Factor.FX, strategy_type=StrategyType.MEAN_REVERSION),
        make_alpha("spx", factor=Factor.EQUITY_INDEX, strategy_type=StrategyType.MOMENTUM),
    ]


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database(tmp_path / "sor.sqlite")
    run_migrations(database, MIGRATIONS)
    yield database
    database.close()


@pytest.mark.parametrize("method", ["risk_parity", "hrp", "optimize"])
def test_build_portfolio_methods(method: str) -> None:
    target = build_portfolio(_diversified_alphas(), constraints=_LOOSE, method=method)
    assert sum(target.weights.values()) == pytest.approx(1.0, abs=1e-6)
    assert all(w > 0 for w in target.weights.values())
    assert set(target.factor_exposures) == {"precious_metals", "fx", "equity_index"}
    assert target.diversification_ratio >= 1.0
    assert target.effective_bets > 1.0
    assert sum(target.risk_contributions.values()) == pytest.approx(1.0)


def test_default_constraints_respect_caps() -> None:
    alphas = [make_alpha(f"a{i}", factor=Factor.FX) for i in range(6)]
    target = build_portfolio(alphas, method="risk_parity")  # default max_weight 0.25
    assert max(target.weights.values()) <= 0.25 + 1e-9
    assert sum(target.weights.values()) <= 1.0 + 1e-9


def test_correlation_controls_applied() -> None:
    alphas = _diversified_alphas()
    corr = constant_correlation(3, 0.9)
    target = build_portfolio(alphas, correlation=corr, constraints=_LOOSE, method="risk_parity")
    assert sum(target.weights.values()) <= 1.0 + 1e-9


def test_invalid_inputs() -> None:
    with pytest.raises(PortfolioError):
        build_portfolio([], method="hrp")
    with pytest.raises(PortfolioError):
        build_portfolio([make_alpha("a"), make_alpha("a")], method="hrp")
    with pytest.raises(PortfolioError):
        build_portfolio(_diversified_alphas(), method="bogus")


def test_engine_journals_to_audit_log(db: Database) -> None:
    engine = PortfolioEngine(db)
    engine.build_portfolio(_diversified_alphas(), constraints=_LOOSE, method="hrp")
    count = db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    assert count == 1
    assert verify_audit_chain(db).ok


def test_portfolio_analytics() -> None:
    alphas = _diversified_alphas()
    order = [a.alpha_id for a in alphas]
    returns = synthetic_returns(300, 3, seed=1)
    weights = dict(zip(order, [1 / 3, 1 / 3, 1 / 3], strict=True))
    analytics = portfolio_analytics(weights, returns, order, alphas=alphas)
    assert sum(analytics.risk_contributions.values()) == pytest.approx(1.0)
    assert sum(analytics.factor_contributions.values()) == pytest.approx(1.0)
    assert analytics.volatility > 0
    assert isinstance(analytics.cagr, float)
