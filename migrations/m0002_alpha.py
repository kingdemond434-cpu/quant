"""Migration 0002 — alpha lifecycle tables.

Adds the rich alpha card (7-state lifecycle), an append-only alpha event log (audit trail),
and a live-performance history table. Kept separate from the coarse Stage-2 ``alpha_registry``
so each layer evolves independently.
"""

from __future__ import annotations

from libs.store.migrations import Migration

_STATES = (
    "'candidate', 'probation', 'active', 'watch', 'decaying', "
    "'retirement_candidate', 'retired'"
)

STATEMENTS: tuple[str, ...] = (
    f"""
    CREATE TABLE alpha_cards (
        id                TEXT PRIMARY KEY,
        created_at        TEXT NOT NULL,
        updated_at        TEXT NOT NULL,
        name              TEXT NOT NULL,
        market            TEXT NOT NULL,
        category          TEXT NOT NULL,
        thesis            TEXT NOT NULL,
        entry_logic       TEXT NOT NULL,
        exit_logic        TEXT NOT NULL,
        expected_cagr     REAL,
        expected_sharpe   REAL,
        expected_drawdown REAL,
        dsr               REAL,
        pbo               REAL,
        cpcv_json         TEXT,
        walk_forward_json TEXT,
        holdout_json      TEXT,
        deployment_date   TEXT,
        retirement_date   TEXT,
        live_cagr         REAL,
        live_sharpe       REAL,
        live_drawdown     REAL,
        decay_score       REAL NOT NULL DEFAULT 0,
        status            TEXT NOT NULL CHECK (status IN ({_STATES})),
        successor_id      TEXT,
        predecessor_id    TEXT,
        extra_json        TEXT
    )
    """,
    """
    CREATE TABLE alpha_events (
        seq         INTEGER PRIMARY KEY AUTOINCREMENT,
        id          TEXT NOT NULL UNIQUE,
        alpha_id    TEXT NOT NULL REFERENCES alpha_cards(id),
        created_at  TEXT NOT NULL,
        event_type  TEXT NOT NULL,
        from_status TEXT,
        to_status   TEXT,
        detail_json TEXT,
        actor       TEXT NOT NULL
    )
    """,
    """
    CREATE TRIGGER alpha_events_no_update
    BEFORE UPDATE ON alpha_events
    BEGIN
        SELECT RAISE(ABORT, 'alpha_events is append-only');
    END
    """,
    """
    CREATE TRIGGER alpha_events_no_delete
    BEFORE DELETE ON alpha_events
    BEGIN
        SELECT RAISE(ABORT, 'alpha_events is append-only');
    END
    """,
    """
    CREATE TABLE alpha_performance (
        seq           INTEGER PRIMARY KEY AUTOINCREMENT,
        id            TEXT NOT NULL UNIQUE,
        alpha_id      TEXT NOT NULL REFERENCES alpha_cards(id),
        created_at    TEXT NOT NULL,
        sharpe        REAL,
        cagr          REAL,
        max_drawdown  REAL,
        win_rate      REAL,
        profit_factor REAL,
        expectancy    REAL,
        sample        INTEGER,
        detail_json   TEXT
    )
    """,
    "CREATE INDEX idx_alpha_cards_status ON alpha_cards(status)",
    "CREATE INDEX idx_alpha_events_alpha ON alpha_events(alpha_id)",
    "CREATE INDEX idx_alpha_perf_alpha ON alpha_performance(alpha_id)",
)

MIGRATION = Migration(version=2, name="alpha", statements=STATEMENTS)
