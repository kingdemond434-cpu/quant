"""Fixtures and builders for the alpha test suite."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from migrations import MIGRATIONS

from libs.alpha.card import AlphaCard, ExpectedMetrics, LiveMetrics, NewAlpha
from libs.alpha.manager import AlphaLifecycleManager
from libs.alpha.state import AlphaState
from libs.core.ids import generate_id
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
        "name": "gold_session",
        "market": "XAUUSD",
        "category": "session",
        "thesis": "London-open overreaction in gold",
        "entry_logic": "fade the first 15m range break",
        "exit_logic": "exit at session close or stop",
        "expected_cagr": 0.20,
        "expected_sharpe": 1.5,
        "expected_drawdown": 0.10,
        "dsr": 0.96,
        "pbo": 0.20,
        "cpcv": {"folds": 10},
        "walk_forward": {"windows": 5},
        "holdout": {"sharpe": 1.4},
        "extra": {
            "expected_win_rate": 0.55,
            "expected_profit_factor": 1.6,
            "expected_expectancy": 0.30,
        },
    }
    defaults.update(overrides)
    return NewAlpha(**defaults)


def make_expected(**overrides: Any) -> ExpectedMetrics:
    defaults: dict[str, Any] = {
        "sharpe": 1.5, "cagr": 0.20, "max_drawdown": 0.10,
        "win_rate": 0.55, "profit_factor": 1.6, "expectancy": 0.30,
    }
    defaults.update(overrides)
    return ExpectedMetrics(**defaults)


def make_live(**overrides: Any) -> LiveMetrics:
    defaults: dict[str, Any] = {
        "sharpe": 1.5, "cagr": 0.20, "max_drawdown": 0.10,
        "win_rate": 0.55, "profit_factor": 1.6, "expectancy": 0.30,
        "regime_stability": 1.0, "sample": 200,
    }
    defaults.update(overrides)
    return LiveMetrics(**defaults)


def make_card(**overrides: Any) -> AlphaCard:
    defaults: dict[str, Any] = {
        "id": generate_id("alpha"), "created_at": "t", "updated_at": "t", "name": "a",
        "market": "XAUUSD", "category": "session", "thesis": "t", "entry_logic": "e",
        "exit_logic": "x", "expected_cagr": 0.2, "expected_sharpe": 1.5,
        "expected_drawdown": 0.1, "dsr": 0.96, "pbo": 0.2, "cpcv": None, "walk_forward": None,
        "holdout": None, "deployment_date": None, "retirement_date": None, "live_cagr": None,
        "live_sharpe": None, "live_drawdown": None, "decay_score": 0.0,
        "status": AlphaState.CANDIDATE, "successor_id": None, "predecessor_id": None, "extra": {},
    }
    defaults.update(overrides)
    return AlphaCard(**defaults)
