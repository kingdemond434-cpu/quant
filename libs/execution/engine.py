"""Execution engine — submit, cancel, track, and reconcile, with idempotency and fail-closed.

Honours the structural rule that an order can only exist with a valid ``risk_approval_id``.
Idempotency keys prevent duplicate orders (store-level and broker-level). Ambiguous broker
timeouts never assume a fill — they force reconciliation. The broker is the source of truth for
positions; on any divergence the engine fails closed.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from libs.execution.broker import BrokerGateway, OrderRequest
from libs.execution.errors import BrokerTimeout, ExecutionError, TransientBrokerError
from libs.execution.journal import TradeJournal
from libs.execution.retry import retry_call
from libs.store.models import Order
from libs.store.trading import OrderStore


class ExecStatus(StrEnum):
    FILLED = "filled"
    REJECTED = "rejected"
    SUBMITTED = "submitted"
    DUPLICATE = "duplicate"
    NEEDS_RECONCILE = "needs_reconcile"
    CANCELLED = "cancelled"


class ExecutionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: ExecStatus
    order: Order | None
    broker_order_id: int | None = None
    filled_qty: float = 0.0
    fill_price: float | None = None
    message: str = ""


class ReconciliationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    broker_positions: dict[str, float]
    internal_positions: dict[str, float]
    deltas: dict[str, float]
    divergence: bool
    halted: bool

    @property
    def ok(self) -> bool:
        return not self.halted


class ExecutionEngine:
    """Translates approved intents into broker orders and keeps state reconciled."""

    def __init__(
        self,
        store: OrderStore,
        broker: BrokerGateway,
        journal: TradeJournal,
        *,
        attempts: int = 3,
        backoff: float = 0.0,
    ) -> None:
        self.store = store
        self.broker = broker
        self.journal = journal
        self.attempts = attempts
        self.backoff = backoff

    # ---------------------------------------------------------------- submit

    def submit_order(self, request: OrderRequest) -> ExecutionResult:
        """Submit an approved order. Idempotent; fails closed without a valid approval."""
        if not request.risk_approval_id:
            raise ExecutionError("fail-closed: order requires a risk_approval_id")

        existing = self.store.get_order_by_idempotency_key(request.idempotency_key)
        if existing is not None:
            self.journal.record(
                "order_duplicate_ignored",
                {"idempotency_key": request.idempotency_key, "order_id": existing.id},
                outcome="duplicate",
            )
            return ExecutionResult(
                status=ExecStatus.DUPLICATE, order=existing, broker_order_id=existing.mt5_ticket,
                message="idempotent: order already exists",
            )

        try:
            order = self.store.create_order(
                instrument=request.instrument, side=request.side, qty=request.qty,
                order_type=request.order_type, risk_approval_id=request.risk_approval_id,
                intended_price=request.price, alpha_id=request.alpha_id,
                idempotency_key=request.idempotency_key,
            )
        except ValueError as exc:
            self.journal.record(
                "order_rejected_no_approval",
                {"idempotency_key": request.idempotency_key}, outcome="rejected",
                rationale=str(exc),
            )
            raise ExecutionError(f"fail-closed: {exc}") from exc

        self.journal.record(
            "order_submitted",
            {"order_id": order.id, "instrument": request.instrument, "side": request.side,
             "qty": request.qty},
        )

        try:
            result = retry_call(
                lambda: self.broker.place_order(request),
                attempts=self.attempts, backoff=self.backoff, retry_on=(TransientBrokerError,),
            )
        except BrokerTimeout as exc:
            self.store.set_order_status(order.id, "pending")
            self.journal.record(
                "order_timeout", {"order_id": order.id}, outcome="needs_reconcile",
                rationale=str(exc),
            )
            return ExecutionResult(
                status=ExecStatus.NEEDS_RECONCILE, order=self.store.get_order(order.id),
                message="ambiguous broker timeout; reconciliation required",
            )
        except TransientBrokerError as exc:
            self.store.set_order_status(order.id, "rejected")
            self.journal.record(
                "order_failed", {"order_id": order.id}, outcome="rejected", rationale=str(exc)
            )
            return ExecutionResult(
                status=ExecStatus.REJECTED, order=self.store.get_order(order.id), message=str(exc)
            )

        if result.status == "filled":
            self.store.record_fill(
                order_id=order.id, fill_price=result.fill_price or 0.0,
                fill_qty=result.filled_qty, mt5_deal_id=result.deal_id,
            )
            updated = self.store.set_order_status(
                order.id, "filled", mt5_ticket=result.broker_order_id
            )
            self._sync_instrument(request.instrument)
            self.journal.record(
                "order_filled",
                {"order_id": order.id, "fill_price": result.fill_price,
                 "fill_qty": result.filled_qty}, outcome="filled",
            )
            return ExecutionResult(
                status=ExecStatus.FILLED, order=updated, broker_order_id=result.broker_order_id,
                filled_qty=result.filled_qty, fill_price=result.fill_price, message="filled",
            )

        if result.status == "rejected":
            updated = self.store.set_order_status(
                order.id, "rejected", mt5_ticket=result.broker_order_id
            )
            self.journal.record(
                "order_rejected", {"order_id": order.id}, outcome="rejected",
                rationale=result.message,
            )
            return ExecutionResult(
                status=ExecStatus.REJECTED, order=updated, broker_order_id=result.broker_order_id,
                message=result.message,
            )

        updated = self.store.set_order_status(
            order.id, "pending", mt5_ticket=result.broker_order_id
        )
        self.journal.record("order_working", {"order_id": order.id}, outcome="pending")
        return ExecutionResult(
            status=ExecStatus.SUBMITTED, order=updated, broker_order_id=result.broker_order_id,
            message="working order",
        )

    # ---------------------------------------------------------------- cancel

    def cancel_order(self, order_id: str) -> ExecutionResult:
        """Cancel a working order (only pending orders may be cancelled)."""
        order = self.store.get_order(order_id)
        if order is None:
            raise ExecutionError(f"unknown order {order_id}")
        if order.status != "pending":
            raise ExecutionError(f"cannot cancel order in status {order.status!r}")

        broker_ok = True
        if order.mt5_ticket is not None:
            broker_ok = retry_call(
                lambda: self.broker.cancel_order(order.mt5_ticket),  # type: ignore[arg-type]
                attempts=self.attempts, backoff=self.backoff, retry_on=(TransientBrokerError,),
            )
        updated = self.store.set_order_status(order_id, "cancelled")
        self.journal.record(
            "order_cancelled", {"order_id": order_id, "broker_ok": broker_ok}, outcome="cancelled"
        )
        return ExecutionResult(
            status=ExecStatus.CANCELLED, order=updated, broker_order_id=order.mt5_ticket,
            message="cancelled",
        )

    # ------------------------------------------------------------ reconcile

    def reconcile_positions(
        self, *, halt_on_divergence: bool = True, tolerance: float = 1e-9
    ) -> ReconciliationReport:
        """Sync internal positions to the broker (source of truth); fail closed on divergence."""
        broker_positions = retry_call(
            self.broker.get_positions, attempts=self.attempts, backoff=self.backoff,
            retry_on=(TransientBrokerError,),
        )
        broker_map = {p.instrument: p for p in broker_positions}
        internal = {p.instrument: p for p in self.store.list_positions()}
        instruments = sorted(set(broker_map) | set(internal))

        broker_vals: dict[str, float] = {}
        internal_vals: dict[str, float] = {}
        deltas: dict[str, float] = {}
        for sym in instruments:
            bq = broker_map[sym].qty if sym in broker_map else 0.0
            iq = internal[sym].qty if sym in internal else 0.0
            broker_vals[sym] = bq
            internal_vals[sym] = iq
            deltas[sym] = bq - iq
            avg = broker_map[sym].avg_price if sym in broker_map else 0.0
            self.store.upsert_position(instrument=sym, qty=bq, avg_price=avg)  # adopt broker truth

        divergence = any(abs(d) > tolerance for d in deltas.values())
        halted = bool(divergence and halt_on_divergence)
        self.journal.record(
            "reconciliation", {"deltas": deltas}, outcome="halt" if halted else "ok"
        )
        return ReconciliationReport(
            broker_positions=broker_vals, internal_positions=internal_vals, deltas=deltas,
            divergence=divergence, halted=halted,
        )

    def safe_start(self) -> ReconciliationReport:
        """Reconcile against the broker before resuming trading (never blind-resume)."""
        self.journal.record("safe_start", {}, rationale="reconcile before resuming")
        return self.reconcile_positions(halt_on_divergence=False)

    # ------------------------------------------------------------- internal

    def _sync_instrument(self, instrument: str) -> None:
        for position in self.broker.get_positions():
            if position.instrument == instrument:
                self.store.upsert_position(
                    instrument=instrument, qty=position.qty, avg_price=position.avg_price
                )
                return
        self.store.upsert_position(instrument=instrument, qty=0.0, avg_price=0.0)
