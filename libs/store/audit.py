"""The append-only, hash-chained audit log — the platform's system of record for decisions.

Every risk decision, veto, alpha lifecycle transition, and order approval writes here. Rows
are immutable (DB triggers reject UPDATE/DELETE) and hash-chained (tamper-evident).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from typing import Any

from libs.core.ids import generate_id
from libs.core.time import to_iso8601, utcnow
from libs.store.connection import Database
from libs.store.hashchain import (
    GENESIS_PREV_HASH,
    canonical_json,
    compute_chain_hash,
    verify_chain,
)
from libs.store.models import AuditEntry, ChainVerification


def _hash_fields(row: Mapping[str, Any]) -> dict[str, Any]:
    """The exact field set hashed into an audit row's ``row_hash`` (rebuilt from a DB row)."""
    return {
        "seq": int(row["seq"]),
        "id": row["id"],
        "created_at": row["created_at"],
        "decision_type": row["decision_type"],
        "actor": row["actor"],
        "inputs": json.loads(row["inputs_json"]),
        "rationale": row["rationale"],
        "outcome": row["outcome"],
        "prev_hash": row["prev_hash"],
    }


def _row_to_entry(row: sqlite3.Row) -> AuditEntry:
    return AuditEntry(
        seq=int(row["seq"]),
        id=row["id"],
        created_at=row["created_at"],
        decision_type=row["decision_type"],
        actor=row["actor"],
        inputs=json.loads(row["inputs_json"]),
        rationale=row["rationale"],
        outcome=row["outcome"],
        prev_hash=row["prev_hash"],
        row_hash=row["row_hash"],
    )


class AuditLog:
    """Writer/reader for the ``audit_log`` table."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def append(
        self,
        decision_type: str,
        actor: str,
        inputs: Mapping[str, Any],
        *,
        rationale: str | None = None,
        outcome: str | None = None,
    ) -> AuditEntry:
        """Append one immutable, hash-chained decision record and return it."""
        inputs_dict = dict(inputs)
        with self.db.transaction() as conn:
            last = conn.execute(
                "SELECT seq, row_hash FROM audit_log ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            seq = (int(last["seq"]) + 1) if last else 1
            prev_hash = last["row_hash"] if last else GENESIS_PREV_HASH
            entry_id = generate_id("audit")
            created_at = to_iso8601(utcnow())
            fields = {
                "seq": seq,
                "id": entry_id,
                "created_at": created_at,
                "decision_type": decision_type,
                "actor": actor,
                "inputs": inputs_dict,
                "rationale": rationale,
                "outcome": outcome,
                "prev_hash": prev_hash,
            }
            row_hash = compute_chain_hash(fields)
            conn.execute(
                "INSERT INTO audit_log "
                "(seq, id, created_at, decision_type, actor, inputs_json, rationale, "
                " outcome, prev_hash, row_hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    seq,
                    entry_id,
                    created_at,
                    decision_type,
                    actor,
                    canonical_json(inputs_dict),
                    rationale,
                    outcome,
                    prev_hash,
                    row_hash,
                ),
            )
        return AuditEntry(
            seq=seq,
            id=entry_id,
            created_at=created_at,
            decision_type=decision_type,
            actor=actor,
            inputs=inputs_dict,
            rationale=rationale,
            outcome=outcome,
            prev_hash=prev_hash,
            row_hash=row_hash,
        )

    def all(self) -> list[AuditEntry]:
        rows = self.db.execute("SELECT * FROM audit_log ORDER BY seq").fetchall()
        return [_row_to_entry(row) for row in rows]

    def count(self) -> int:
        return int(self.db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0])


def verify_audit_chain(db: Database) -> ChainVerification:
    """Verify the integrity of the entire audit chain."""
    rows = db.execute("SELECT * FROM audit_log ORDER BY seq").fetchall()
    ok, broken_seq, message = verify_chain(rows, _hash_fields)
    return ChainVerification(ok=ok, length=len(rows), broken_seq=broken_seq, message=message)
