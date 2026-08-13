"""Fixtures and a fake broker for the execution test suite."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from migrations import MIGRATIONS

from libs.execution.broker import BrokerOrderResult, BrokerPosition, OrderRequest
from libs.execution.engine import ExecutionEngine
from libs.execution.errors import BrokerTimeout, TransientBrokerError
from libs.execution.journal import TradeJournal
from libs.store.connection import Database
from libs.store.migrations import run_migrations
from libs.store.registries import RiskRegistry
from libs.store.trading import OrderStore


class FakeBroker:
    """A deterministic, idempotent in-memory broker for tests."""

    def __init__(self, *, fill_price: float = 2000.0) -> None:
        self.fill_price = fill_price
        self.place_calls = 0
        self._by_client: dict[str, BrokerOrderResult] = {}
        self._positions: dict[str, list[float]] = {}  # instrument -> [qty, avg]
        self._next_ticket = 1000
        self._transient_remaining = 0
        self._timeout = False
        self._reject = False
        self._pending = False

    # --- test controls ---
    def fail_transient(self, n: int) -> None:
        self._transient_remaining = n

    def set_timeout(self, value: bool = True) -> None:
        self._timeout = value

    def set_reject(self, value: bool = True) -> None:
        self._reject = value

    def set_pending(self, value: bool = True) -> None:
        self._pending = value

    def add_position(self, instrument: str, qty: float, avg: float) -> None:
        self._positions[instrument] = [qty, avg]

    # --- BrokerGateway protocol ---
    def place_order(self, request: OrderRequest) -> BrokerOrderResult:
        self.place_calls += 1
        if self._transient_remaining > 0:
            self._transient_remaining -= 1
            raise TransientBrokerError("requote")
        if self._timeout:
            raise BrokerTimeout("no acknowledgement")
        if request.idempotency_key in self._by_client:
            return self._by_client[request.idempotency_key]  # idempotent dedup

        ticket = self._next_ticket
        self._next_ticket += 1
        if self._reject:
            result = BrokerOrderResult(
                client_order_id=request.idempotency_key, broker_order_id=ticket,
                status="rejected", message="rejected by broker",
            )
        elif self._pending:
            result = BrokerOrderResult(
                client_order_id=request.idempotency_key, broker_order_id=ticket, status="pending",
            )
        else:
            self._apply_position(request)
            result = BrokerOrderResult(
                client_order_id=request.idempotency_key, broker_order_id=ticket, status="filled",
                filled_qty=request.qty, fill_price=self.fill_price, deal_id=ticket,
            )
        self._by_client[request.idempotency_key] = result
        return result

    def _apply_position(self, request: OrderRequest) -> None:
        signed = request.qty if request.side == "buy" else -request.qty
        qty, avg = self._positions.get(request.instrument, [0.0, 0.0])
        new_qty = qty + signed
        if qty == 0:
            new_avg = self.fill_price
        elif (qty > 0) == (signed > 0) and new_qty != 0:
            new_avg = (avg * abs(qty) + self.fill_price * abs(signed)) / abs(new_qty)
        else:
            new_avg = self.fill_price if new_qty != 0 else 0.0
        self._positions[request.instrument] = [new_qty, new_avg]

    def cancel_order(self, broker_order_id: int) -> bool:
        return True

    def get_positions(self) -> list[BrokerPosition]:
        return [
            BrokerPosition(instrument=sym, qty=qa[0], avg_price=qa[1])
            for sym, qa in self._positions.items()
            if qa[0] != 0
        ]

    def get_order(self, client_order_id: str) -> BrokerOrderResult | None:
        return self._by_client.get(client_order_id)


@pytest.fixture(autouse=True)
def _never_write_the_live_bleed_cache(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No test may seed the executor's last-good denylist cache with fixture symbols.

    `_structurally_bleeding` writes through every non-empty read, and the tests that exercise it
    monkeypatch `_FORENSICS` but have no reason to know a second path exists. Without this,
    running the suite would leave synthetic rows (FRESHUSDT, ZZZBLEEDUSDT) in the real
    `data/structural_bleed_last_good.json`, which the live executor consults whenever forensics
    is unreadable -- a test run silently editing a money-path fallback.

    Autouse and directory-wide on purpose: opt-in isolation only protects the tests that
    remembered to ask, and the next test to touch this fence will not know to. Covers every
    LOADED copy of the module, because test_carry_entry_gate.py execs the same source under an
    alias to avoid opening venue connections -- patching one name would leave the other live.
    """
    seen = [m for m in list(sys.modules.values())
            if getattr(m, "__name__", "").startswith("scripts.run_cashcarry_executor")
            or (hasattr(m, "_BLEED_CACHE") and hasattr(m, "_structurally_bleeding"))]
    for mod in seen:
        monkeypatch.setattr(mod, "_BLEED_CACHE",
                            tmp_path_factory.mktemp("bleed") / "last_good.json", raising=False)


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database(tmp_path / "sor.sqlite")
    run_migrations(database, MIGRATIONS)
    yield database
    database.close()


@pytest.fixture
def broker() -> FakeBroker:
    return FakeBroker()


@pytest.fixture
def engine(db: Database, broker: FakeBroker) -> ExecutionEngine:
    return ExecutionEngine(OrderStore(db), broker, TradeJournal(db), attempts=3, backoff=0.0)


def approval_id(db: Database, target: str = "intent_1") -> str:
    return RiskRegistry(db).create_approval(target_ref=target).id


def make_request(approval: str, **overrides: object) -> OrderRequest:
    defaults: dict[str, object] = {
        "idempotency_key": "idem-1",
        "instrument": "XAUUSD",
        "side": "buy",
        "qty": 0.1,
        "order_type": "market",
        "risk_approval_id": approval,
    }
    defaults.update(overrides)
    return OrderRequest(**defaults)  # type: ignore[arg-type]
