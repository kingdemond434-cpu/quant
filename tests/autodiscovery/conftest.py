"""Fixtures for the autonomous research-lab tests (deterministic, no MT5)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
from migrations import MIGRATIONS

from libs.autodiscovery.models import MarketSeries
from libs.store.connection import Database
from libs.store.migrations import run_migrations


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database(tmp_path / "sor.sqlite")
    run_migrations(database, MIGRATIONS)
    yield database
    database.close()


def noise_series(n: int = 3000, seed: int = 0) -> MarketSeries:
    """A pure random-walk series — no edge exists; the gauntlet must reject everything."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0, 0.01, size=n)
    close = 100.0 * np.cumprod(1.0 + rets)
    high = close * 1.001
    low = close * 0.999
    hour = np.array([i % 24 for i in range(n)], dtype="float64")
    volume = rng.uniform(100, 1000, size=n)
    return MarketSeries(close=close, high=high, low=low, volume=volume, hour=hour)


def noise_provider(seed: int = 0):
    def provider(symbol: str) -> MarketSeries:
        return noise_series(seed=seed + hash(symbol) % 100)
    return provider
