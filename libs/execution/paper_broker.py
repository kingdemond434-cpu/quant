"""Paper broker — a deterministic in-memory gateway for demo/paper trading.

Implements the :class:`BrokerGateway` protocol with deterministic fills at a per-symbol mark price
(plus optional fixed slippage), idempotent dedup, and position tracking. No real capital and no
external connectivity: this is the demo/paper execution venue. The real venue is ``MT5Broker``.
"""

from __future__ import annotations

from libs.execution.broker import BrokerOrderResult, BrokerPosition, OrderRequest


class PaperBroker:
    """A deterministic, idempotent paper-trading broker (no live capital)."""

    def __init__(self, *, default_price: float = 100.0, slippage_bps: float = 0.0) -> None:
        self.default_price = default_price
        self.slippage_bps = slippage_bps
        self._prices: dict[str, float] = {}
        self._by_client: dict[str, BrokerOrderResult] = {}
        self._positions: dict[str, list[float]] = {}  # instrument -> [qty, avg]
        self._next_ticket = 1

    def set_price(self, instrument: str, price: float) -> None:
        self._prices[instrument] = price

    def _fill_price(self, instrument: str, side: str) -> float:
        mark = self._prices.get(instrument, self.default_price)
        slip = mark * (self.slippage_bps / 1e4)
        return mark + slip if side == "buy" else mark - slip  # adverse slippage

    # --- BrokerGateway protocol ------------------------------------------------
    def place_order(self, request: OrderRequest) -> BrokerOrderResult:
        if request.idempotency_key in self._by_client:
            return self._by_client[request.idempotency_key]  # idempotent dedup
        ticket = self._next_ticket
        self._next_ticket += 1
        price = self._fill_price(request.instrument, request.side)
        self._apply_position(request, price)
        result = BrokerOrderResult(
            client_order_id=request.idempotency_key, broker_order_id=ticket, status="filled",
            filled_qty=request.qty, fill_price=price, deal_id=ticket, message="paper fill",
        )
        self._by_client[request.idempotency_key] = result
        return result

    def _apply_position(self, request: OrderRequest, price: float) -> None:
        signed = request.qty if request.side == "buy" else -request.qty
        qty, avg = self._positions.get(request.instrument, [0.0, 0.0])
        new_qty = qty + signed
        if qty == 0:
            new_avg = price
        elif (qty > 0) == (signed > 0) and new_qty != 0:
            new_avg = (avg * abs(qty) + price * abs(signed)) / abs(new_qty)
        else:
            new_avg = price if new_qty != 0 else 0.0
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
