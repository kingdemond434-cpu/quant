"""Fixtures and builders for the risk test suite."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
from migrations import MIGRATIONS

from libs.risk.gate import AccountState, OrderIntent
from libs.store.connection import Database
from libs.store.migrations import run_migrations


@pytest.fixture(autouse=True)
def _hermetic_fee_burn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the gap-#98 cost-rate brake at empty per-test paths.

    `risk_controls.evaluate` defaults to reading the executor's live income artifact (that is what
    lets the brake reach the executor's call site without an executor edit). On a production box
    that artifact EXISTS, so without this redirect the suite's verdicts would depend on the box's
    live burn state -- a green suite must be evidence about the code, not about last night's fees.
    Tests that want the brake exercised pass `fee_burn=`/paths explicitly.
    """
    from libs.risk import risk_controls
    monkeypatch.setattr(risk_controls, "INCOME_ARTIFACT", tmp_path / "cashcarry_live.json")
    monkeypatch.setattr(risk_controls, "BURN_WINDOW_FILE", tmp_path / "fee_burn_window.json")


def make_account(**overrides: object) -> AccountState:
    defaults: dict[str, object] = {
        "equity": 100_000.0,
        "peak_equity": 100_000.0,
        "forecast_vol": 0.10,        # == default target -> vol scalar 1.0
        "average_correlation": 0.0,
        "vol_now": 1.0,
        "vol_baseline": 1.0,
        "kill_switch_tripped": False,
        "data_stale": False,
        "factor_exposures": {},
        "current_heat_total": 0.0,
    }
    defaults.update(overrides)
    return AccountState(**defaults)  # type: ignore[arg-type]


def make_intent(**overrides: object) -> OrderIntent:
    defaults: dict[str, object] = {
        "instrument": "XAUUSD",
        "side": "buy",
        "kelly_fraction": 0.25,
        "risk_budget": 0.5,
        "risk_per_unit": 10.0,
    }
    defaults.update(overrides)
    return OrderIntent(**defaults)  # type: ignore[arg-type]


def correlated_returns(*, n: int = 300, k: int = 4, rho: float, seed: int = 0) -> np.ndarray:
    """k columns of returns with pairwise correlation ~ rho (via a shared common factor)."""
    rng = np.random.default_rng(seed)
    common = rng.normal(0, 1, size=(n, 1))
    idio = rng.normal(0, 1, size=(n, k))
    w = np.sqrt(max(0.0, min(1.0, rho)))
    return w * common + np.sqrt(1.0 - w**2) * idio


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database(tmp_path / "sor.sqlite")
    run_migrations(database, MIGRATIONS)
    yield database
    database.close()
