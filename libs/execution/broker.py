"""Broker gateway abstraction.

The execution engine talks only to this interface, so it is broker-agnostic and testable. The
real MT5 implementation isolates the Windows-bound, single-session MetaTrader5 API; tests use a
fake. Orders carry a client-side ``idempotency_key`` so a retry never places a duplicate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from libs.execution.errors import BrokerError


@dataclass(frozen=True)
class OrderRequest:
    """A request to the broker. ``idempotency_key`` dedups retries."""

    idempotency_key: str
    instrument: str
    side: str  # "buy" | "sell"
    qty: float
    order_type: str  # "market" | "limit" | "stop"
    risk_approval_id: str
    price: float | None = None
    alpha_id: str | None = None


@dataclass(frozen=True)
class BrokerOrderResult:
    client_order_id: str
    broker_order_id: int
    status: str  # "filled" | "rejected" | "pending"
    filled_qty: float = 0.0
    fill_price: float | None = None
    deal_id: int | None = None
    message: str = ""


@dataclass(frozen=True)
class BrokerPosition:
    instrument: str
    qty: float  # signed lots
    avg_price: float


@runtime_checkable
class BrokerGateway(Protocol):
    """The minimal broker contract the execution engine depends on."""

    def place_order(self, request: OrderRequest) -> BrokerOrderResult: ...

    def cancel_order(self, broker_order_id: int) -> bool: ...

    def get_positions(self) -> list[BrokerPosition]: ...

    def get_order(self, client_order_id: str) -> BrokerOrderResult | None: ...


class MT5Broker:  # pragma: no cover - requires a live Windows MT5 terminal
    """Real broker gateway backed by the ``MetaTrader5`` package."""

    def __init__(self) -> None:
        try:
            import MetaTrader5 as mt5
        except ImportError as exc:
            raise BrokerError("the MetaTrader5 package is not installed") from exc
        self._mt5 = mt5
        if not mt5.initialize():
            raise BrokerError(f"MT5 initialize() failed: {mt5.last_error()}")

    def place_order(self, request: OrderRequest) -> BrokerOrderResult:
        mt5 = self._mt5
        symbol_info = mt5.symbol_info_tick(request.instrument)
        order_kind = mt5.ORDER_TYPE_BUY if request.side == "buy" else mt5.ORDER_TYPE_SELL
        price = request.price or (symbol_info.ask if request.side == "buy" else symbol_info.bid)
        send = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": request.instrument,
            "volume": request.qty,
            "type": order_kind,
            "price": price,
            "comment": request.idempotency_key,  # idempotency anchor
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(send)
        if result is None:
            raise BrokerError(f"order_send returned None: {mt5.last_error()}")
        filled = result.retcode == mt5.TRADE_RETCODE_DONE
        return BrokerOrderResult(
            client_order_id=request.idempotency_key,
            broker_order_id=int(result.order),
            status="filled" if filled else "rejected",
            filled_qty=float(result.volume),
            fill_price=float(result.price),
            deal_id=int(result.deal),
            message=str(result.comment),
        )

    def cancel_order(self, broker_order_id: int) -> bool:
        mt5 = self._mt5
        result = mt5.order_send(
            {"action": mt5.TRADE_ACTION_REMOVE, "order": broker_order_id}
        )
        return bool(result is not None and result.retcode == mt5.TRADE_RETCODE_DONE)

    def get_positions(self) -> list[BrokerPosition]:
        positions = self._mt5.positions_get() or []
        return [
            BrokerPosition(
                instrument=p.symbol,
                qty=p.volume if p.type == self._mt5.POSITION_TYPE_BUY else -p.volume,
                avg_price=float(p.price_open),
            )
            for p in positions
        ]

    def get_order(self, client_order_id: str) -> BrokerOrderResult | None:
        for deal in self._mt5.history_deals_get() or []:
            if deal.comment == client_order_id:
                return BrokerOrderResult(
                    client_order_id=client_order_id, broker_order_id=int(deal.order),
                    status="filled", filled_qty=float(deal.volume), fill_price=float(deal.price),
                    deal_id=int(deal.ticket),
                )
        return None
