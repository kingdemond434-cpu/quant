"""Fixtures and builders for the Alpha Factory test suite."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from migrations import MIGRATIONS

from libs.alpha_factory.models import AlphaDNA, IdeaCandidate
from libs.store.connection import Database
from libs.store.migrations import run_migrations


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database(tmp_path / "sor.sqlite")
    run_migrations(database, MIGRATIONS)
    yield database
    database.close()


def make_dna(**overrides: Any) -> AlphaDNA:
    defaults: dict[str, Any] = {
        "signal_type": "trend",
        "market": "XAUUSD",
        "timeframe": "H1",
        "holding_period": "swing",
        "factor_exposures": {"momentum": 0.8, "volatility": 0.2},
        "regime_affinity": {"trend": 1.0},
        "volatility_sensitivity": 0.3,
        "trend_sensitivity": 0.9,
        "mean_reversion_sensitivity": 0.1,
        "capacity_estimate": 1e6,
        "turnover_profile": 0.4,
        "risk_profile": 0.5,
    }
    defaults.update(overrides)
    return AlphaDNA(**defaults)


def make_candidate(idea_id: str = "idea_1", **overrides: Any) -> IdeaCandidate:
    defaults: dict[str, Any] = {
        "idea_id": idea_id,
        "category": "momentum",
        "expected_edge": 0.8,
        "expected_robustness": 0.7,
        "expected_capacity": 0.6,
        "novelty": 0.7,
        "crowding": 0.1,
        "regime_need": 0.5,
        "portfolio_need": 0.5,
    }
    defaults.update(overrides)
    return IdeaCandidate(**defaults)
