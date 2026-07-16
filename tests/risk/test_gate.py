"""Risk-gate tests — approval minting, fail-closed rejection, and the structural invariant."""

from __future__ import annotations

import numpy as np
import pytest
from tests.risk.conftest import make_account, make_intent

from libs.risk.config import PreservationConfig, RiskConfig
from libs.risk.gate import risk_gate
from libs.store.connection import Database
from libs.store.registries import RiskRegistry
from libs.store.trading import OrderStore


def test_benign_intent_is_approved() -> None:
    decision = risk_gate(make_intent(), make_account())
    assert decision.approved
    assert decision.sized_units > 0
    assert decision.global_scalar == pytest.approx(1.0)
    assert decision.risk_approval_id is None  # no registry supplied


def test_approval_persisted_and_order_can_be_created(db: Database) -> None:
    registry = RiskRegistry(db)
    decision = risk_gate(make_intent(), make_account(), registry=registry)
    assert decision.approved
    assert decision.risk_approval_id is not None

    order = OrderStore(db).create_order(
        instrument="XAUUSD", side="buy", qty=0.1, order_type="market",
        risk_approval_id=decision.risk_approval_id,
    )
    assert order.status == "pending"
    assert order.risk_approval_id == decision.risk_approval_id


def test_no_order_without_valid_approval(db: Database) -> None:
    store = OrderStore(db)
    # a fabricated id does not exist
    with pytest.raises(ValueError):
        store.create_order(
            instrument="XAUUSD", side="buy", qty=0.1, order_type="market",
            risk_approval_id="risk_does_not_exist",
        )
    # a non-approval risk record (a limit) cannot authorize an order
    limit_id = RiskRegistry(db).add_limit(scope="global", metric="dd", threshold=0.2).id
    with pytest.raises(ValueError):
        store.create_order(
            instrument="XAUUSD", side="buy", qty=0.1, order_type="market",
            risk_approval_id=limit_id,
        )


def test_rejected_gate_yields_no_approval_id() -> None:
    decision = risk_gate(make_intent(), make_account(kill_switch_tripped=True))
    assert not decision.approved
    assert decision.risk_approval_id is None


@pytest.mark.parametrize(
    ("account_kwargs", "config"),
    [
        ({"kill_switch_tripped": True}, None),
        ({"data_stale": True}, None),
        ({"equity": 75_000.0, "peak_equity": 100_000.0}, None),  # 25% drawdown -> halt
        ({"equity": -1.0}, None),  # fail-closed
    ],
)
def test_reject_paths(account_kwargs: dict[str, object], config: RiskConfig | None) -> None:
    decision = risk_gate(make_intent(), make_account(**account_kwargs), config)
    assert not decision.approved
    assert decision.sized_units == 0.0


def test_equity_floor_rejects() -> None:
    cfg = RiskConfig(preservation=PreservationConfig(equity_floor=50_000.0))
    decision = risk_gate(make_intent(), make_account(equity=40_000.0, peak_equity=100_000.0), cfg)
    assert not decision.approved


def test_cost_hurdle_rejects() -> None:
    decision = risk_gate(make_intent(edge_value=1.0, cost=2.0), make_account())
    assert not decision.approved


def test_sizing_respects_position_and_heat_caps() -> None:
    # aggressive intent: heat cap (20% of equity) is the binding limit
    decision = risk_gate(make_intent(kelly_fraction=0.5, risk_budget=1.0), make_account())
    assert decision.approved
    risk_amount = abs(decision.sized_units) * 10.0  # units * risk_per_unit
    assert risk_amount <= 0.20 * 100_000.0 + 1e-3


def test_monte_carlo_approved_orders_within_limits() -> None:
    rng = np.random.default_rng(0)
    approvals = 0
    for _ in range(200):
        equity = float(rng.uniform(10_000, 500_000))
        intent = make_intent(
            kelly_fraction=float(rng.uniform(0.0, 0.5)),
            risk_budget=float(rng.uniform(0.0, 1.0)),
            risk_per_unit=float(rng.uniform(1.0, 100.0)),
        )
        account = make_account(equity=equity, peak_equity=equity, forecast_vol=0.10)
        decision = risk_gate(intent, account)
        if decision.approved:
            approvals += 1
            risk_amount = abs(decision.sized_units) * intent.risk_per_unit
            # heat cap (20%) is the tightest standing limit on a clean book
            assert risk_amount <= 0.20 * equity + 1e-3
    assert approvals > 0  # the benign Monte Carlo should approve some


def test_monte_carlo_adverse_states_always_rejected() -> None:
    rng = np.random.default_rng(1)
    for _ in range(100):
        equity = float(rng.uniform(10_000, 500_000))
        account = make_account(
            equity=equity, peak_equity=equity, kill_switch_tripped=True
        )
        assert not risk_gate(make_intent(), account).approved
