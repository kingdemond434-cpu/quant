"""Fixtures and builders for the Stage 13 self-improvement test suite."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from migrations import MIGRATIONS

from libs.alpha.card import AlphaCard, LiveMetrics, NewAlpha
from libs.alpha.manager import AlphaLifecycleManager
from libs.store.connection import Database
from libs.store.migrations import run_migrations


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database(tmp_path / "sor.sqlite")
    run_migrations(database, MIGRATIONS)
    yield database
    database.close()


@pytest.fixture
def manager(db: Database) -> AlphaLifecycleManager:
    return AlphaLifecycleManager(db)


def make_new(**overrides: Any) -> NewAlpha:
    defaults: dict[str, Any] = {
        "name": "gold_trend",
        "market": "XAUUSD",
        "category": "trend_following",
        "thesis": "trend premium in gold",
        "entry_logic": "fast > slow",
        "exit_logic": "fast < slow or stop",
        "expected_cagr": 0.20,
        "expected_sharpe": 1.5,
        "expected_drawdown": 0.10,
        "dsr": 0.96,
        "pbo": 0.20,
        "extra": {
            "expected_win_rate": 0.55,
            "expected_profit_factor": 1.6,
            "expected_expectancy": 0.30,
        },
    }
    defaults.update(overrides)
    return NewAlpha(**defaults)


def make_live(**overrides: Any) -> LiveMetrics:
    defaults: dict[str, Any] = {
        "sharpe": 1.6, "cagr": 0.22, "max_drawdown": 0.08, "win_rate": 0.56,
        "profit_factor": 1.7, "expectancy": 0.32, "regime_stability": 1.0, "sample": 200,
    }
    defaults.update(overrides)
    return LiveMetrics(**defaults)


def make_live_poor(**overrides: Any) -> LiveMetrics:
    defaults: dict[str, Any] = {
        "sharpe": 0.2, "cagr": 0.0, "max_drawdown": 0.30, "win_rate": 0.40,
        "profit_factor": 0.7, "expectancy": 0.0, "regime_stability": 0.3, "sample": 200,
    }
    defaults.update(overrides)
    return LiveMetrics(**defaults)


def register(manager: AlphaLifecycleManager, **overrides: Any) -> AlphaCard:
    return manager.register_alpha(make_new(**overrides))
