"""Migration 0005 — autonomous research lab state.

A durable, append-only record of every candidate the autonomous lab tests (family, subtype,
parameterization, validation metrics, rejection reason, lifecycle status) plus a checkpoint table so
the lab resumes exactly where it left off after any interruption. Status may be updated as a
candidate moves through the lifecycle; rows are never deleted.
"""

from __future__ import annotations

from libs.store.migrations import Migration

_STATUS = (
    "'candidate', 'validation', 'rejected', 'shadow', 'paper', 'registry', 'archived'"
)

STATEMENTS: tuple[str, ...] = (
    f"""
    CREATE TABLE research_candidates (
        seq             INTEGER PRIMARY KEY AUTOINCREMENT,
        id              TEXT NOT NULL UNIQUE,
        created_at      TEXT NOT NULL,
        campaign_id     TEXT NOT NULL,
        family          TEXT NOT NULL,
        subtype         TEXT NOT NULL,
        symbol          TEXT NOT NULL,
        params_json     TEXT NOT NULL,
        content_hash    TEXT NOT NULL UNIQUE,
        status          TEXT NOT NULL CHECK (status IN ({_STATUS})),
        mechanism       TEXT,
        annual_sharpe   REAL,
        dsr             REAL,
        pbo             REAL,
        reality_p       REAL,
        oos_sharpe      REAL,
        capacity_usd    REAL,
        fragility       REAL,
        survived        INTEGER NOT NULL DEFAULT 0,
        rejection_reason TEXT,
        updated_at      TEXT NOT NULL
    )
    """,
    """
    CREATE TRIGGER research_candidates_no_delete
    BEFORE DELETE ON research_candidates
    BEGIN
        SELECT RAISE(ABORT, 'research_candidates is append-only');
    END
    """,
    """
    CREATE TABLE lab_checkpoint (
        key        TEXT PRIMARY KEY,
        value      TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX idx_research_candidates_family ON research_candidates(family)",
    "CREATE INDEX idx_research_candidates_status ON research_candidates(status)",
)

MIGRATION = Migration(version=5, name="autodiscovery", statements=STATEMENTS)
