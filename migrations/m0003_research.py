"""Migration 0003 — Alpha Factory research memory.

A durable, never-deleted record of every research idea/hypothesis ever tested, with its outcome
and (for failures) a structured cause and lessons. The Alpha Factory learns from this so it never
repeats a failed research path. Rows may be updated to record an outcome, but never deleted.
"""

from __future__ import annotations

from libs.store.migrations import Migration

_RESULTS = "'pending', 'success', 'failure'"

STATEMENTS: tuple[str, ...] = (
    f"""
    CREATE TABLE research_memory (
        id             TEXT PRIMARY KEY,
        created_at     TEXT NOT NULL,
        category       TEXT NOT NULL,
        statement      TEXT NOT NULL,
        result         TEXT NOT NULL CHECK (result IN ({_RESULTS})),
        failure_cause  TEXT,
        failure_reason TEXT,
        success_reason TEXT,
        failure_stage  TEXT,
        lessons        TEXT,
        metrics_json   TEXT,
        predecessor_id TEXT
    )
    """,
    """
    CREATE TRIGGER research_memory_no_delete
    BEFORE DELETE ON research_memory
    BEGIN
        SELECT RAISE(ABORT, 'research_memory is append-only (never lose research knowledge)');
    END
    """,
    "CREATE INDEX idx_research_memory_category ON research_memory(category)",
    "CREATE INDEX idx_research_memory_result ON research_memory(result)",
)

MIGRATION = Migration(version=3, name="research", statements=STATEMENTS)
