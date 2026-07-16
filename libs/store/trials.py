"""The append-only, hash-chained trials ledger.

Nothing is validated without a ledger entry first: every hypothesis evaluation, parameter
point, and search candidate is recorded here so the Deflated Sharpe Ratio can deflate by the
*true* cumulative trial count. Rows are immutable and tamper-evident, like the audit log.
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
from libs.store.models import ChainVerification, TrialRecord


def _hash_fields(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "seq": int(row["seq"]),
        "id": row["id"],
        "created_at": row["created_at"],
        "hypothesis_id": row["hypothesis_id"],
        "family": row["family"],
        "method": row["method"],
        "params": json.loads(row["params_json"]),
        "data_snapshot": row["data_snapshot"],
        "in_sample_metric": row["in_sample_metric"],
        "git_commit": row["git_commit"],
        "prev_hash": row["prev_hash"],
    }


def _row_to_record(row: sqlite3.Row) -> TrialRecord:
    return TrialRecord(
        seq=int(row["seq"]),
        id=row["id"],
        created_at=row["created_at"],
        hypothesis_id=row["hypothesis_id"],
        family=row["family"],
        method=row["method"],
        params=json.loads(row["params_json"]),
        data_snapshot=row["data_snapshot"],
        in_sample_metric=row["in_sample_metric"],
        git_commit=row["git_commit"],
        prev_hash=row["prev_hash"],
        row_hash=row["row_hash"],
    )


class TrialsLedger:
    """Writer/reader for the ``trials_ledger`` table."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def append(
        self,
        hypothesis_id: str,
        family: str,
        method: str,
        params: Mapping[str, Any],
        *,
        data_snapshot: str | None = None,
        in_sample_metric: float | None = None,
        git_commit: str | None = None,
    ) -> TrialRecord:
        """Append one immutable, hash-chained trial record and return it."""
        params_dict = dict(params)
        with self.db.transaction() as conn:
            last = conn.execute(
                "SELECT seq, row_hash FROM trials_ledger ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            seq = (int(last["seq"]) + 1) if last else 1
            prev_hash = last["row_hash"] if last else GENESIS_PREV_HASH
            trial_id = generate_id("trial")
            created_at = to_iso8601(utcnow())
            fields = {
                "seq": seq,
                "id": trial_id,
                "created_at": created_at,
                "hypothesis_id": hypothesis_id,
                "family": family,
                "method": method,
                "params": params_dict,
                "data_snapshot": data_snapshot,
                "in_sample_metric": in_sample_metric,
                "git_commit": git_commit,
                "prev_hash": prev_hash,
            }
            row_hash = compute_chain_hash(fields)
            conn.execute(
                "INSERT INTO trials_ledger "
                "(seq, id, created_at, hypothesis_id, family, method, params_json, "
                " data_snapshot, in_sample_metric, git_commit, prev_hash, row_hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    seq,
                    trial_id,
                    created_at,
                    hypothesis_id,
                    family,
                    method,
                    canonical_json(params_dict),
                    data_snapshot,
                    in_sample_metric,
                    git_commit,
                    prev_hash,
                    row_hash,
                ),
            )
        return TrialRecord(
            seq=seq,
            id=trial_id,
            created_at=created_at,
            hypothesis_id=hypothesis_id,
            family=family,
            method=method,
            params=params_dict,
            data_snapshot=data_snapshot,
            in_sample_metric=in_sample_metric,
            git_commit=git_commit,
            prev_hash=prev_hash,
            row_hash=row_hash,
        )

    def count(self) -> int:
        """Return the true cumulative trial count (feeds the Deflated Sharpe Ratio)."""
        return int(self.db.execute("SELECT COUNT(*) FROM trials_ledger").fetchone()[0])

    def count_for_hypothesis(self, hypothesis_id: str) -> int:
        return int(
            self.db.execute(
                "SELECT COUNT(*) FROM trials_ledger WHERE hypothesis_id = ?", (hypothesis_id,)
            ).fetchone()[0]
        )

    def all(self) -> list[TrialRecord]:
        rows = self.db.execute("SELECT * FROM trials_ledger ORDER BY seq").fetchall()
        return [_row_to_record(row) for row in rows]


def verify_trials_chain(db: Database) -> ChainVerification:
    """Verify the integrity of the entire trials ledger chain."""
    rows = db.execute("SELECT * FROM trials_ledger ORDER BY seq").fetchall()
    ok, broken_seq, message = verify_chain(rows, _hash_fields)
    return ChainVerification(ok=ok, length=len(rows), broken_seq=broken_seq, message=message)
