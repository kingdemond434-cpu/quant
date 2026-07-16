"""Fixtures for the app/runtime test suite."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from migrations import MIGRATIONS

from libs.signal_engine.engine import SymbolObservation
from libs.signal_engine.models import AlphaSignal, Direction, MarketState, Regime
from libs.store.connection import Database
from libs.store.migrations import run_migrations


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database(tmp_path / "sor.sqlite")
    run_migrations(database, MIGRATIONS)
    yield database
    database.close()


def buy_observation(symbol: str = "EURUSD") -> SymbolObservation:
    """A clean, corroborated BUY that passes Stage 13.5 selection."""
    signals = [
        AlphaSignal(
            alpha_id=f"{name}_1", symbol=symbol, direction=Direction.BUY, strength=0.9,
            expected_return=0.01, win_rate=0.6, avg_win=0.012, avg_loss=0.008, profit_factor=1.8,
            sharpe=1.8, health_score=95.0, regime_affinity={Regime.TREND.value: 1.0},
            governance_passed=True,
        )
        for name in ("trend", "momentum")
    ]
    state = MarketState(symbol=symbol, regime=Regime.TREND, predicted_regime=Regime.TREND,
                        volatility_state=0.2)
    return SymbolObservation(signals=signals, state=state)
