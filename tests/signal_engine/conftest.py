"""Fixtures and builders for the Stage 13.5 signal-engine test suite."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from migrations import MIGRATIONS

from libs.signal_engine.engine import SymbolObservation
from libs.signal_engine.governance import GovernanceVerdict
from libs.signal_engine.models import AlphaSignal, Direction, MarketState, Regime
from libs.store.connection import Database
from libs.store.migrations import run_migrations


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database(tmp_path / "sor.sqlite")
    run_migrations(database, MIGRATIONS)
    yield database
    database.close()


def make_alpha(alpha_id: str = "trend_1", **overrides: Any) -> AlphaSignal:
    defaults: dict[str, Any] = {
        "alpha_id": alpha_id,
        "symbol": "EURUSD",
        "direction": Direction.BUY,
        "strength": 0.9,
        "expected_return": 0.01,
        "win_rate": 0.60,
        "avg_win": 0.012,
        "avg_loss": 0.008,
        "profit_factor": 1.8,
        "sharpe": 1.8,
        "health_score": 95.0,
        "decay_multiplier": 1.0,
        "regime_affinity": {Regime.TREND.value: 1.0},
        "governance_passed": True,
    }
    defaults.update(overrides)
    return AlphaSignal(**defaults)


def make_state(**overrides: Any) -> MarketState:
    defaults: dict[str, Any] = {
        "symbol": "EURUSD",
        "regime": Regime.TREND,
        "predicted_regime": Regime.TREND,
        "transition_probability": 0.0,
        "volatility_state": 0.2,
        "spread_bps": 1.0,
        "liquidity_score": 1.0,
        "cross_asset_score": 1.0,
        "microstructure_score": 1.0,
        "adv_usd": 1e9,
    }
    defaults.update(overrides)
    return MarketState(**defaults)


def full_governance() -> GovernanceVerdict:
    return GovernanceVerdict(
        cpcv_pass=True, dsr_pass=True, pbo_pass=True, deflated_sharpe_pass=True,
        reality_check_pass=True, capacity_pass=True, structural_break_pass=True,
        shadow_period_complete=True,
    )


def strong_obs(**overrides: Any) -> SymbolObservation:
    """A clean, well-corroborated BUY that should pass final selection."""
    defaults: dict[str, Any] = {
        "signals": [make_alpha("trend_1"), make_alpha("mom_1")],
        "state": make_state(),
        "slippage_bps": 0.5,
    }
    defaults.update(overrides)
    return SymbolObservation(**defaults)
