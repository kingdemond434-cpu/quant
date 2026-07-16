"""Store accessors for alpha cards, the append-only event log, and performance history."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from typing import Any

from libs.alpha.card import AlphaCard, AlphaEvent, AlphaPerformance, LiveMetrics
from libs.alpha.state import AlphaState
from libs.core.ids import generate_id
from libs.core.time import to_iso8601, utcnow
from libs.store.connection import Database


def _loads(value: str | None) -> Any:
    return json.loads(value) if value is not None else None


def _dumps(value: Mapping[str, Any] | None) -> str | None:
    return json.dumps(dict(value), sort_keys=True) if value is not None else None


def _row_to_card(row: sqlite3.Row) -> AlphaCard:
    return AlphaCard(
        id=row["id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        name=row["name"],
        market=row["market"],
        category=row["category"],
        thesis=row["thesis"],
        entry_logic=row["entry_logic"],
        exit_logic=row["exit_logic"],
        expected_cagr=row["expected_cagr"],
        expected_sharpe=row["expected_sharpe"],
        expected_drawdown=row["expected_drawdown"],
        dsr=row["dsr"],
        pbo=row["pbo"],
        cpcv=_loads(row["cpcv_json"]),
        walk_forward=_loads(row["walk_forward_json"]),
        holdout=_loads(row["holdout_json"]),
        deployment_date=row["deployment_date"],
        retirement_date=row["retirement_date"],
        live_cagr=row["live_cagr"],
        live_sharpe=row["live_sharpe"],
        live_drawdown=row["live_drawdown"],
        decay_score=float(row["decay_score"]),
        status=AlphaState(row["status"]),
        successor_id=row["successor_id"],
        predecessor_id=row["predecessor_id"],
        extra=_loads(row["extra_json"]) or {},
    )


class AlphaCardStore:
    """CRUD for the ``alpha_cards`` table."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def insert(self, card: AlphaCard) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO alpha_cards "
                "(id, created_at, updated_at, name, market, category, thesis, entry_logic, "
                " exit_logic, expected_cagr, expected_sharpe, expected_drawdown, dsr, pbo, "
                " cpcv_json, walk_forward_json, holdout_json, deployment_date, retirement_date, "
                " live_cagr, live_sharpe, live_drawdown, decay_score, status, successor_id, "
                " predecessor_id, extra_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                " ?, ?, ?, ?)",
                (
                    card.id, card.created_at, card.updated_at, card.name, card.market,
                    card.category, card.thesis, card.entry_logic, card.exit_logic,
                    card.expected_cagr, card.expected_sharpe, card.expected_drawdown, card.dsr,
                    card.pbo, _dumps(card.cpcv), _dumps(card.walk_forward), _dumps(card.holdout),
                    card.deployment_date, card.retirement_date, card.live_cagr, card.live_sharpe,
                    card.live_drawdown, card.decay_score, card.status.value, card.successor_id,
                    card.predecessor_id, _dumps(card.extra),
                ),
            )

    def update(self, card: AlphaCard) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE alpha_cards SET updated_at=?, name=?, market=?, category=?, thesis=?, "
                "entry_logic=?, exit_logic=?, expected_cagr=?, expected_sharpe=?, "
                "expected_drawdown=?, dsr=?, pbo=?, cpcv_json=?, walk_forward_json=?, "
                "holdout_json=?, deployment_date=?, retirement_date=?, live_cagr=?, live_sharpe=?, "
                "live_drawdown=?, decay_score=?, status=?, successor_id=?, predecessor_id=?, "
                "extra_json=? WHERE id=?",
                (
                    card.updated_at, card.name, card.market, card.category, card.thesis,
                    card.entry_logic, card.exit_logic, card.expected_cagr, card.expected_sharpe,
                    card.expected_drawdown, card.dsr, card.pbo, _dumps(card.cpcv),
                    _dumps(card.walk_forward), _dumps(card.holdout), card.deployment_date,
                    card.retirement_date, card.live_cagr, card.live_sharpe, card.live_drawdown,
                    card.decay_score, card.status.value, card.successor_id, card.predecessor_id,
                    _dumps(card.extra), card.id,
                ),
            )

    def get(self, alpha_id: str) -> AlphaCard | None:
        row = self.db.execute("SELECT * FROM alpha_cards WHERE id = ?", (alpha_id,)).fetchone()
        return _row_to_card(row) if row else None

    def list_all(self) -> list[AlphaCard]:
        rows = self.db.execute("SELECT * FROM alpha_cards ORDER BY created_at").fetchall()
        return [_row_to_card(row) for row in rows]

    def list_by_status(self, status: AlphaState) -> list[AlphaCard]:
        rows = self.db.execute(
            "SELECT * FROM alpha_cards WHERE status = ? ORDER BY created_at", (status.value,)
        ).fetchall()
        return [_row_to_card(row) for row in rows]


class AlphaAuditTrail:
    """Append-only writer/reader for ``alpha_events``."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def append(
        self,
        alpha_id: str,
        event_type: str,
        *,
        from_status: AlphaState | None = None,
        to_status: AlphaState | None = None,
        detail: Mapping[str, Any] | None = None,
        actor: str = "alpha_manager",
    ) -> AlphaEvent:
        event_id = generate_id("aev")
        created_at = to_iso8601(utcnow())
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO alpha_events "
                "(id, alpha_id, created_at, event_type, from_status, to_status, detail_json, "
                " actor) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_id, alpha_id, created_at, event_type,
                    from_status.value if from_status else None,
                    to_status.value if to_status else None,
                    _dumps(detail), actor,
                ),
            )
            seq = int(cursor.lastrowid or 0)
        return AlphaEvent(
            seq=seq, id=event_id, alpha_id=alpha_id, created_at=created_at, event_type=event_type,
            from_status=from_status.value if from_status else None,
            to_status=to_status.value if to_status else None,
            detail=dict(detail) if detail else None, actor=actor,
        )

    def list(self, alpha_id: str) -> list[AlphaEvent]:
        rows = self.db.execute(
            "SELECT * FROM alpha_events WHERE alpha_id = ? ORDER BY seq", (alpha_id,)
        ).fetchall()
        return [
            AlphaEvent(
                seq=int(r["seq"]), id=r["id"], alpha_id=r["alpha_id"], created_at=r["created_at"],
                event_type=r["event_type"], from_status=r["from_status"], to_status=r["to_status"],
                detail=_loads(r["detail_json"]), actor=r["actor"],
            )
            for r in rows
        ]


class PerformanceTracker:
    """Writer/reader for ``alpha_performance``."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def record(self, alpha_id: str, live: LiveMetrics) -> AlphaPerformance:
        perf_id = generate_id("aperf")
        created_at = to_iso8601(utcnow())
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO alpha_performance "
                "(id, alpha_id, created_at, sharpe, cagr, max_drawdown, win_rate, profit_factor, "
                " expectancy, sample, detail_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    perf_id, alpha_id, created_at, live.sharpe, live.cagr, live.max_drawdown,
                    live.win_rate, live.profit_factor, live.expectancy, live.sample, None,
                ),
            )
        return AlphaPerformance(
            id=perf_id, alpha_id=alpha_id, created_at=created_at, sharpe=live.sharpe,
            cagr=live.cagr, max_drawdown=live.max_drawdown, win_rate=live.win_rate,
            profit_factor=live.profit_factor, expectancy=live.expectancy, sample=live.sample,
        )

    def history(self, alpha_id: str) -> list[AlphaPerformance]:
        rows = self.db.execute(
            "SELECT * FROM alpha_performance WHERE alpha_id = ? ORDER BY seq", (alpha_id,)
        ).fetchall()
        return [
            AlphaPerformance(
                id=r["id"], alpha_id=r["alpha_id"], created_at=r["created_at"], sharpe=r["sharpe"],
                cagr=r["cagr"], max_drawdown=r["max_drawdown"], win_rate=r["win_rate"],
                profit_factor=r["profit_factor"], expectancy=r["expectancy"], sample=r["sample"],
            )
            for r in rows
        ]
