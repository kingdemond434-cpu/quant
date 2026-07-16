"""Registries: research runs, the alpha registry, and the risk registry.

These are mutable governance tables (status transitions, metrics) written only through the
store. Hash-chained immutability lives in the audit log and trials ledger, not here.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping, Sequence
from typing import Any

from libs.core.ids import generate_id
from libs.core.time import to_iso8601, utcnow
from libs.store.connection import Database
from libs.store.hashchain import canonical_json
from libs.store.models import Alpha, ResearchRun, RiskRecord


def _loads(value: str | None) -> Any:
    return json.loads(value) if value is not None else None


# --------------------------------------------------------------------------- research runs


def _row_to_run(row: sqlite3.Row) -> ResearchRun:
    return ResearchRun(
        id=row["id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        hypothesis_id=row["hypothesis_id"],
        name=row["name"],
        git_commit=row["git_commit"],
        snapshot_id=row["snapshot_id"],
        config_hash=row["config_hash"],
        seed=int(row["seed"]),
        status=row["status"],
        metrics=_loads(row["metrics_json"]),
    )


class ResearchRuns:
    """Writer/reader for ``research_runs``."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def create(
        self,
        *,
        git_commit: str,
        config_hash: str,
        seed: int,
        hypothesis_id: str | None = None,
        name: str | None = None,
        snapshot_id: str | None = None,
        status: str = "running",
    ) -> ResearchRun:
        run_id = generate_id("run")
        now = to_iso8601(utcnow())
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO research_runs "
                "(id, created_at, updated_at, hypothesis_id, name, git_commit, snapshot_id, "
                " config_hash, seed, status, metrics_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id, now, now, hypothesis_id, name, git_commit, snapshot_id,
                    config_hash, seed, status, None,
                ),
            )
        run = self.get(run_id)
        assert run is not None
        return run

    def set_status(
        self, run_id: str, status: str, *, metrics: Mapping[str, Any] | None = None
    ) -> ResearchRun:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE research_runs SET status = ?, metrics_json = ?, updated_at = ? "
                "WHERE id = ?",
                (
                    status,
                    canonical_json(dict(metrics)) if metrics is not None else None,
                    to_iso8601(utcnow()),
                    run_id,
                ),
            )
        run = self.get(run_id)
        if run is None:
            raise KeyError(f"research run not found: {run_id}")
        return run

    def get(self, run_id: str) -> ResearchRun | None:
        row = self.db.execute("SELECT * FROM research_runs WHERE id = ?", (run_id,)).fetchone()
        return _row_to_run(row) if row else None


# --------------------------------------------------------------------------- alpha registry


def _row_to_alpha(row: sqlite3.Row) -> Alpha:
    return Alpha(
        id=row["id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        name=row["name"],
        instruments=json.loads(row["instruments_json"]),
        status=row["status"],
        card=_loads(row["card_json"]),
        owner=row["owner"],
        deploy_date=row["deploy_date"],
        retire_date=row["retire_date"],
    )


class AlphaRegistry:
    """Writer/reader for ``alpha_registry``."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def create(
        self,
        *,
        name: str,
        instruments: Sequence[str],
        status: str = "candidate",
        card: Mapping[str, Any] | None = None,
        owner: str | None = None,
    ) -> Alpha:
        alpha_id = generate_id("alpha")
        now = to_iso8601(utcnow())
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO alpha_registry "
                "(id, created_at, updated_at, name, instruments_json, status, card_json, owner, "
                " deploy_date, retire_date) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    alpha_id, now, now, name, canonical_json(list(instruments)), status,
                    canonical_json(dict(card)) if card is not None else None, owner, None, None,
                ),
            )
        alpha = self.get(alpha_id)
        assert alpha is not None
        return alpha

    def set_status(
        self,
        alpha_id: str,
        status: str,
        *,
        deploy_date: str | None = None,
        retire_date: str | None = None,
    ) -> Alpha:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE alpha_registry SET status = ?, updated_at = ?, "
                "deploy_date = COALESCE(?, deploy_date), retire_date = COALESCE(?, retire_date) "
                "WHERE id = ?",
                (status, to_iso8601(utcnow()), deploy_date, retire_date, alpha_id),
            )
        alpha = self.get(alpha_id)
        if alpha is None:
            raise KeyError(f"alpha not found: {alpha_id}")
        return alpha

    def get(self, alpha_id: str) -> Alpha | None:
        row = self.db.execute(
            "SELECT * FROM alpha_registry WHERE id = ?", (alpha_id,)
        ).fetchone()
        return _row_to_alpha(row) if row else None

    def list_by_status(self, status: str) -> list[Alpha]:
        rows = self.db.execute(
            "SELECT * FROM alpha_registry WHERE status = ? ORDER BY created_at", (status,)
        ).fetchall()
        return [_row_to_alpha(row) for row in rows]


# --------------------------------------------------------------------------- risk registry


def _row_to_risk(row: sqlite3.Row) -> RiskRecord:
    return RiskRecord(
        id=row["id"],
        created_at=row["created_at"],
        kind=row["kind"],
        scope=row["scope"],
        metric=row["metric"],
        threshold=row["threshold"],
        observed=row["observed"],
        action=row["action"],
        target_ref=row["target_ref"],
        detail=_loads(row["detail_json"]),
        active=bool(row["active"]),
    )


class RiskRegistry:
    """Writer/reader for ``risk_registry`` (limits, events, approvals)."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def _insert(
        self,
        *,
        kind: str,
        scope: str | None = None,
        metric: str | None = None,
        threshold: float | None = None,
        observed: float | None = None,
        action: str | None = None,
        target_ref: str | None = None,
        detail: Mapping[str, Any] | None = None,
        active: bool = True,
    ) -> RiskRecord:
        risk_id = generate_id("risk")
        now = to_iso8601(utcnow())
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO risk_registry "
                "(id, created_at, kind, scope, metric, threshold, observed, action, target_ref, "
                " detail_json, active) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    risk_id, now, kind, scope, metric, threshold, observed, action, target_ref,
                    canonical_json(dict(detail)) if detail is not None else None,
                    1 if active else 0,
                ),
            )
        record = self.get(risk_id)
        assert record is not None
        return record

    def add_limit(
        self, *, scope: str, metric: str, threshold: float, detail: Mapping[str, Any] | None = None
    ) -> RiskRecord:
        return self._insert(
            kind="limit", scope=scope, metric=metric, threshold=threshold, detail=detail
        )

    def record_event(
        self,
        *,
        scope: str,
        metric: str,
        observed: float,
        action: str,
        target_ref: str | None = None,
        detail: Mapping[str, Any] | None = None,
    ) -> RiskRecord:
        return self._insert(
            kind="event", scope=scope, metric=metric, observed=observed, action=action,
            target_ref=target_ref, detail=detail,
        )

    def create_approval(
        self,
        *,
        target_ref: str,
        action: str = "approve",
        detail: Mapping[str, Any] | None = None,
    ) -> RiskRecord:
        """Record a pre-trade risk approval/rejection. ``action`` is ``approve`` or ``reject``."""
        if action not in ("approve", "reject"):
            raise ValueError("approval action must be 'approve' or 'reject'")
        return self._insert(kind="approval", action=action, target_ref=target_ref, detail=detail)

    def get(self, risk_id: str) -> RiskRecord | None:
        row = self.db.execute("SELECT * FROM risk_registry WHERE id = ?", (risk_id,)).fetchone()
        return _row_to_risk(row) if row else None
