"""Order / fill / position tables.

The structural invariant lives here: :func:`OrderStore.create_order` refuses to write an
order unless ``risk_approval_id`` points at an *approved* ``risk_registry`` row. Combined with
the ``NOT NULL`` foreign key in the schema, there is no path to an order without a risk
approval — "risk overrides alpha" by construction.
"""

from __future__ import annotations

import sqlite3

from libs.core.ids import generate_id
from libs.core.time import to_iso8601, utcnow
from libs.store.connection import Database
from libs.store.models import Fill, Order, Position


def _row_to_order(row: sqlite3.Row) -> Order:
    return Order(
        id=row["id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        instrument=row["instrument"],
        side=row["side"],
        qty=float(row["qty"]),
        order_type=row["order_type"],
        intended_price=row["intended_price"],
        alpha_id=row["alpha_id"],
        risk_approval_id=row["risk_approval_id"],
        status=row["status"],
        idempotency_key=row["idempotency_key"],
        mt5_ticket=row["mt5_ticket"],
    )


def _row_to_fill(row: sqlite3.Row) -> Fill:
    return Fill(
        id=row["id"],
        order_id=row["order_id"],
        created_at=row["created_at"],
        fill_price=float(row["fill_price"]),
        fill_qty=float(row["fill_qty"]),
        commission=float(row["commission"]),
        mt5_deal_id=row["mt5_deal_id"],
    )


def _row_to_position(row: sqlite3.Row) -> Position:
    return Position(
        instrument=row["instrument"],
        qty=float(row["qty"]),
        avg_price=float(row["avg_price"]),
        realized_pnl=float(row["realized_pnl"]),
        unrealized_pnl=float(row["unrealized_pnl"]),
        updated_at=row["updated_at"],
    )


class OrderStore:
    """Writer/reader for ``orders``, ``fills``, and ``positions``."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def create_order(
        self,
        *,
        instrument: str,
        side: str,
        qty: float,
        order_type: str,
        risk_approval_id: str,
        intended_price: float | None = None,
        alpha_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Order:
        """Create an order, only if ``risk_approval_id`` is a valid approval."""
        approval = self.db.execute(
            "SELECT kind, action FROM risk_registry WHERE id = ?", (risk_approval_id,)
        ).fetchone()
        if approval is None:
            raise ValueError(f"risk approval not found: {risk_approval_id}")
        if approval["kind"] != "approval" or approval["action"] != "approve":
            raise ValueError(
                f"risk_approval_id {risk_approval_id} is not an approved approval "
                f"(kind={approval['kind']}, action={approval['action']})"
            )
        order_id = generate_id("order")
        now = to_iso8601(utcnow())
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO orders "
                "(id, created_at, updated_at, instrument, side, qty, order_type, intended_price, "
                " alpha_id, risk_approval_id, status, idempotency_key, mt5_ticket) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    order_id, now, now, instrument, side, qty, order_type, intended_price,
                    alpha_id, risk_approval_id, "pending", idempotency_key, None,
                ),
            )
        order = self.get_order(order_id)
        assert order is not None
        return order

    def set_order_status(
        self, order_id: str, status: str, *, mt5_ticket: int | None = None
    ) -> Order:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE orders SET status = ?, mt5_ticket = COALESCE(?, mt5_ticket), "
                "updated_at = ? WHERE id = ?",
                (status, mt5_ticket, to_iso8601(utcnow()), order_id),
            )
        order = self.get_order(order_id)
        if order is None:
            raise KeyError(f"order not found: {order_id}")
        return order

    def record_fill(
        self,
        *,
        order_id: str,
        fill_price: float,
        fill_qty: float,
        commission: float = 0.0,
        mt5_deal_id: int | None = None,
    ) -> Fill:
        fill_id = generate_id("fill")
        now = to_iso8601(utcnow())
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO fills "
                "(id, order_id, created_at, fill_price, fill_qty, commission, mt5_deal_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (fill_id, order_id, now, fill_price, fill_qty, commission, mt5_deal_id),
            )
        fill = self.db.execute("SELECT * FROM fills WHERE id = ?", (fill_id,)).fetchone()
        return _row_to_fill(fill)

    def upsert_position(
        self,
        *,
        instrument: str,
        qty: float,
        avg_price: float,
        realized_pnl: float = 0.0,
        unrealized_pnl: float = 0.0,
    ) -> Position:
        now = to_iso8601(utcnow())
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO positions "
                "(instrument, qty, avg_price, realized_pnl, unrealized_pnl, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(instrument) DO UPDATE SET "
                "qty = excluded.qty, avg_price = excluded.avg_price, "
                "realized_pnl = excluded.realized_pnl, unrealized_pnl = excluded.unrealized_pnl, "
                "updated_at = excluded.updated_at",
                (instrument, qty, avg_price, realized_pnl, unrealized_pnl, now),
            )
        position = self.get_position(instrument)
        assert position is not None
        return position

    def get_order(self, order_id: str) -> Order | None:
        row = self.db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        return _row_to_order(row) if row else None

    def get_order_by_idempotency_key(self, key: str) -> Order | None:
        row = self.db.execute(
            "SELECT * FROM orders WHERE idempotency_key = ?", (key,)
        ).fetchone()
        return _row_to_order(row) if row else None

    def list_positions(self) -> list[Position]:
        rows = self.db.execute("SELECT * FROM positions ORDER BY instrument").fetchall()
        return [_row_to_position(row) for row in rows]

    def fills_for(self, order_id: str) -> list[Fill]:
        rows = self.db.execute(
            "SELECT * FROM fills WHERE order_id = ? ORDER BY created_at", (order_id,)
        ).fetchall()
        return [_row_to_fill(row) for row in rows]

    def get_position(self, instrument: str) -> Position | None:
        row = self.db.execute(
            "SELECT * FROM positions WHERE instrument = ?", (instrument,)
        ).fetchone()
        return _row_to_position(row) if row else None
