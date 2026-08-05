"""Candidate store + checkpoint — durable research memory and resumable lab state.

Persists every tested candidate (family/subtype/params/metrics/rejection/status) to the
append-only ``research_candidates`` table, deduplicates by content hash (no repeated testing of a
known idea), and reads/writes the ``lab_checkpoint`` so the lab resumes after any interruption.
"""

from __future__ import annotations

import json
import sqlite3

from libs.autodiscovery.models import (
    CandidateRecord,
    CandidateStatus,
    Hypothesis,
    ValidationMetrics,
)
from libs.core.ids import generate_id
from libs.core.time import to_iso8601, utcnow
from libs.store.connection import Database
from libs.store.hashchain import canonical_json, sha256_hex

_COLS = (
    "id, created_at, updated_at, campaign_id, family, subtype, symbol, params_json, content_hash, "
    "status, mechanism, annual_sharpe, dsr, pbo, reality_p, oos_sharpe, capacity_usd, fragility, "
    "survived, rejection_reason"
)


def content_hash(hyp: Hypothesis) -> str:
    """Stable identity of a hypothesis (family+subtype+symbol+params) for dedup."""
    payload = [hyp.family.value, hyp.subtype, hyp.symbol, sorted(hyp.params.items())]
    return sha256_hex(canonical_json(payload))


def _row_to_record(row: sqlite3.Row) -> CandidateRecord:
    return CandidateRecord(
        id=row["id"], created_at=row["created_at"], updated_at=row["updated_at"],
        campaign_id=row["campaign_id"], family=row["family"], subtype=row["subtype"],
        symbol=row["symbol"], params=json.loads(row["params_json"]),
        content_hash=row["content_hash"], status=CandidateStatus(row["status"]),
        mechanism=row["mechanism"] or "",
        metrics=ValidationMetrics(
            annual_sharpe=row["annual_sharpe"] or 0.0, oos_sharpe=row["oos_sharpe"] or 0.0,
            dsr=row["dsr"] or 0.0, pbo=row["pbo"] or 0.0, reality_p=row["reality_p"] or 1.0,
            capacity_usd=row["capacity_usd"] or 0.0, fragility=row["fragility"] or 0.0,
        ),
        survived=bool(row["survived"]), rejection_reason=row["rejection_reason"],
    )


class CandidateStore:
    """Reader/writer for the durable candidate ledger (append-only) and the lab checkpoint."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def exists(self, hyp: Hypothesis) -> bool:
        chash = content_hash(hyp)
        row = self.db.execute(
            "SELECT 1 FROM research_candidates WHERE content_hash = ?", (chash,)
        ).fetchone()
        return row is not None

    def record(
        self, *, campaign_id: str, hyp: Hypothesis, status: CandidateStatus,
        metrics: ValidationMetrics, survived: bool, rejection_reason: str | None,
    ) -> CandidateRecord:
        now = to_iso8601(utcnow())
        rec = CandidateRecord(
            id=generate_id("cand"), created_at=now, updated_at=now, campaign_id=campaign_id,
            family=hyp.family.value, subtype=hyp.subtype, symbol=hyp.symbol,
            params=dict(hyp.params),
            content_hash=content_hash(hyp), status=status, mechanism=hyp.mechanism.value,
            metrics=metrics, survived=survived, rejection_reason=rejection_reason,
        )
        with self.db.transaction() as conn:
            conn.execute(
                f"INSERT INTO research_candidates ({_COLS}) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    rec.id, now, now, campaign_id, rec.family, rec.subtype, rec.symbol,
                    json.dumps(rec.params), rec.content_hash, status.value, rec.mechanism,
                    metrics.annual_sharpe, metrics.dsr, metrics.pbo, metrics.reality_p,
                    metrics.oos_sharpe, metrics.capacity_usd, metrics.fragility,
                    int(survived), rejection_reason,
                ),
            )
        return rec

    def all(self, *, include_retired: bool = False) -> list[CandidateRecord]:
        """The candidate population -- by default WITHOUT retired (``archived``) rows.

        RETIRED IS NOT A CANDIDATE (§42, 2026-08-05). A row archived by ``retire`` has left the
        population: it must not be ranked, promoted, shadow-tracked or counted as scored
        inventory, and every reader that means "the candidates" gets exactly that by default.
        Readers that mean "the full historical ledger" (rejection histograms, research-ROI spend
        accounting) pass ``include_retired=True`` -- history is never shrunk, it is filtered.
        """
        where = "" if include_retired else \
            f" WHERE status != '{CandidateStatus.ARCHIVED.value}'"
        rows = self.db.execute(
            f"SELECT {_COLS} FROM research_candidates{where} ORDER BY seq"
        ).fetchall()
        return [_row_to_record(r) for r in rows]

    def survivors(self) -> list[CandidateRecord]:
        rows = self.db.execute(
            f"SELECT {_COLS} FROM research_candidates WHERE survived = 1 "
            f"AND status != '{CandidateStatus.ARCHIVED.value}' ORDER BY seq"
        ).fetchall()
        return [_row_to_record(r) for r in rows]

    def rejects(self) -> list[CandidateRecord]:
        """The rejected candidates -- the input to the rejection-shadow audit (gate-calibration).

        A gate that has drifted over-strict silently leaks these; shadow-tracking a sample forward
        is pure recovery (no new data). This is the reject ledger MAX_SURVIVORS Part 1.2 calls for
        -- it already exists as ``survived = 0`` rows, so the audit reads it, never rebuilds it.

        Retired (``archived``) rows are excluded: an UNFILLABLE candidate leaks nothing a gate
        recalibration could recover -- the desk cannot fill it at ANY gate strictness -- and
        shadow-tracking it back to life would undo its retirement by the side door. Its mechanism
        lives in the retirement bank with a named way back (capacity_screen.RESURRECT_CONDITION).
        """
        rows = self.db.execute(
            f"SELECT {_COLS} FROM research_candidates WHERE survived = 0 "
            f"AND status != '{CandidateStatus.ARCHIVED.value}' ORDER BY seq"
        ).fetchall()
        return [_row_to_record(r) for r in rows]

    def retire(self, candidate_id: str) -> bool:
        """Mark one candidate retired (status -> ``archived``). Returns False if nothing changed.

        THE ONE SANCTIONED MUTATION. The table is append-only with a no-delete trigger
        (migrations/m0005: "Status may be updated as a candidate moves through the lifecycle;
        rows are never deleted"), so retirement is a status transition, never a DELETE. The row
        keeps its metrics, its original ``rejection_reason`` (the gate history the failure
        histograms are built from) and its ``survived`` flag untouched -- the WHY of the
        retirement, plus the full mechanism and the named resurrection condition, live in
        ``data/capacity_retired_bank.jsonl`` keyed by this id (L1.17).

        Dedup (``exists``), trial counts (``total``) and family deflation priors
        (``family_counts``) still see retired rows on purpose: the trials really ran, and a
        retirement must never quietly loosen the DSR wall or re-open a tested hypothesis.
        """
        with self.db.transaction() as conn:
            cur = conn.execute(
                "UPDATE research_candidates SET status = ?, updated_at = ? "
                "WHERE id = ? AND status != ?",
                (CandidateStatus.ARCHIVED.value, to_iso8601(utcnow()), candidate_id,
                 CandidateStatus.ARCHIVED.value),
            )
        return cur.rowcount == 1

    def status_counts(self) -> dict[str, int]:
        rows = self.db.execute(
            "SELECT status, COUNT(*) AS n FROM research_candidates GROUP BY status"
        ).fetchall()
        return {r["status"]: int(r["n"]) for r in rows}

    def family_counts(self) -> dict[str, int]:
        rows = self.db.execute(
            "SELECT family, COUNT(*) AS n FROM research_candidates GROUP BY family"
        ).fetchall()
        return {r["family"]: int(r["n"]) for r in rows}

    def total(self) -> int:
        return int(self.db.execute("SELECT COUNT(*) FROM research_candidates").fetchone()[0])

    # ----------------------------------------------------------------- checkpoint
    def get_checkpoint(self, key: str) -> str | None:
        row = self.db.execute("SELECT value FROM lab_checkpoint WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_checkpoint(self, key: str, value: str) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO lab_checkpoint (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
                "updated_at = excluded.updated_at",
                (key, value, to_iso8601(utcnow())),
            )
