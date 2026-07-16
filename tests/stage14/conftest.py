"""Fixtures and builders for the Stage 14 test suite."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from migrations import MIGRATIONS

from libs.signal_engine.models import Direction, Regime, SignalPackage
from libs.store.connection import Database
from libs.store.migrations import run_migrations


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database(tmp_path / "sor.sqlite")
    run_migrations(database, MIGRATIONS)
    yield database
    database.close()


def make_signal(symbol: str = "XAUUSD", **overrides: Any) -> SignalPackage:
    defaults: dict[str, Any] = {
        "symbol": symbol,
        "direction": Direction.BUY,
        "quality_score": 85.0,
        "confidence": 0.8,
        "edge_score": 70.0,
        "expected_return": 0.05,
        "expected_drawdown": 0.08,
        "expected_sharpe": 1.6,
        "expected_sortino": 2.0,
        "expected_calmar": 1.5,
        "expected_pf": 1.6,
        "expected_value": 0.02,
        "regime": Regime.TREND,
        "predicted_regime": Regime.TREND,
        "alpha_breakdown": {"trend_alpha": 0.6, "momentum_alpha": 0.4},
        "factor_exposures": {"momentum": 0.9},
        "execution_score": 90.0,
        "capacity_score": 90.0,
        "crowding_score": 10.0,
        "portfolio_contribution": 0.5,
        "institutional_score": 82.0,
    }
    defaults.update(overrides)
    return SignalPackage(**defaults)
