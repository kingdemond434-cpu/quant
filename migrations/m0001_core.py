"""Migration 0001 — core schema for the system of record.

Creates the snapshot catalog, config versions, the two hash-chained append-only tables
(audit_log, trials_ledger) with immutability triggers, the registries, and the order/fill/
position tables. The ``orders.risk_approval_id NOT NULL`` foreign key encodes the structural
invariant "no order without a risk approval".
"""

from __future__ import annotations

from libs.store.migrations import Migration

STATEMENTS: tuple[str, ...] = (
    # --- snapshot catalog -------------------------------------------------
    """
    CREATE TABLE snapshots (
        id            TEXT PRIMARY KEY,
        created_at    TEXT NOT NULL,
        kind          TEXT NOT NULL CHECK (kind IN ('database', 'dataset')),
        label         TEXT,
        path          TEXT,
        sha256        TEXT,
        row_counts_json TEXT,
        meta_json     TEXT
    )
    """,
    # --- config versions --------------------------------------------------
    """
    CREATE TABLE config_versions (
        id           TEXT PRIMARY KEY,
        created_at   TEXT NOT NULL,
        config_hash  TEXT NOT NULL UNIQUE,
        environment  TEXT,
        content_json TEXT NOT NULL,
        note         TEXT
    )
    """,
    # --- audit log (append-only, hash-chained) ----------------------------
    """
    CREATE TABLE audit_log (
        seq           INTEGER PRIMARY KEY AUTOINCREMENT,
        id            TEXT NOT NULL UNIQUE,
        created_at    TEXT NOT NULL,
        decision_type TEXT NOT NULL,
        actor         TEXT NOT NULL,
        inputs_json   TEXT NOT NULL,
        rationale     TEXT,
        outcome       TEXT,
        prev_hash     TEXT NOT NULL,
        row_hash      TEXT NOT NULL UNIQUE
    )
    """,
    """
    CREATE TRIGGER audit_log_no_update
    BEFORE UPDATE ON audit_log
    BEGIN
        SELECT RAISE(ABORT, 'audit_log is append-only');
    END
    """,
    """
    CREATE TRIGGER audit_log_no_delete
    BEFORE DELETE ON audit_log
    BEGIN
        SELECT RAISE(ABORT, 'audit_log is append-only');
    END
    """,
    # --- trials ledger (append-only, hash-chained) ------------------------
    """
    CREATE TABLE trials_ledger (
        seq              INTEGER PRIMARY KEY AUTOINCREMENT,
        id               TEXT NOT NULL UNIQUE,
        created_at       TEXT NOT NULL,
        hypothesis_id    TEXT NOT NULL,
        family           TEXT NOT NULL,
        method           TEXT NOT NULL,
        params_json      TEXT NOT NULL,
        data_snapshot    TEXT,
        in_sample_metric REAL,
        git_commit       TEXT,
        prev_hash        TEXT NOT NULL,
        row_hash         TEXT NOT NULL UNIQUE
    )
    """,
    """
    CREATE TRIGGER trials_ledger_no_update
    BEFORE UPDATE ON trials_ledger
    BEGIN
        SELECT RAISE(ABORT, 'trials_ledger is append-only');
    END
    """,
    """
    CREATE TRIGGER trials_ledger_no_delete
    BEFORE DELETE ON trials_ledger
    BEGIN
        SELECT RAISE(ABORT, 'trials_ledger is append-only');
    END
    """,
    # --- registries -------------------------------------------------------
    """
    CREATE TABLE alpha_registry (
        id               TEXT PRIMARY KEY,
        created_at       TEXT NOT NULL,
        updated_at       TEXT NOT NULL,
        name             TEXT NOT NULL,
        instruments_json TEXT NOT NULL,
        status           TEXT NOT NULL CHECK (
            status IN ('candidate', 'validated', 'deployed', 'decaying', 'retired', 'archived')
        ),
        card_json        TEXT,
        owner            TEXT,
        deploy_date      TEXT,
        retire_date      TEXT
    )
    """,
    """
    CREATE TABLE risk_registry (
        id          TEXT PRIMARY KEY,
        created_at  TEXT NOT NULL,
        kind        TEXT NOT NULL CHECK (kind IN ('limit', 'event', 'approval')),
        scope       TEXT,
        metric      TEXT,
        threshold   REAL,
        observed    REAL,
        action      TEXT,
        target_ref  TEXT,
        detail_json TEXT,
        active      INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
    )
    """,
    """
    CREATE TABLE research_runs (
        id           TEXT PRIMARY KEY,
        created_at   TEXT NOT NULL,
        updated_at   TEXT NOT NULL,
        hypothesis_id TEXT,
        name         TEXT,
        git_commit   TEXT NOT NULL,
        snapshot_id  TEXT REFERENCES snapshots(id),
        config_hash  TEXT NOT NULL,
        seed         INTEGER NOT NULL,
        status       TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
        metrics_json TEXT
    )
    """,
    # --- orders / fills / positions ---------------------------------------
    """
    CREATE TABLE orders (
        id               TEXT PRIMARY KEY,
        created_at       TEXT NOT NULL,
        updated_at       TEXT NOT NULL,
        instrument       TEXT NOT NULL,
        side             TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
        qty              REAL NOT NULL CHECK (qty > 0),
        order_type       TEXT NOT NULL CHECK (order_type IN ('market', 'limit', 'stop')),
        intended_price   REAL,
        alpha_id         TEXT REFERENCES alpha_registry(id),
        risk_approval_id TEXT NOT NULL REFERENCES risk_registry(id),
        status           TEXT NOT NULL CHECK (
            status IN ('pending', 'filled', 'partial', 'rejected', 'cancelled')
        ),
        idempotency_key  TEXT UNIQUE,
        mt5_ticket       INTEGER
    )
    """,
    """
    CREATE TABLE fills (
        id          TEXT PRIMARY KEY,
        order_id    TEXT NOT NULL REFERENCES orders(id),
        created_at  TEXT NOT NULL,
        fill_price  REAL NOT NULL,
        fill_qty    REAL NOT NULL CHECK (fill_qty > 0),
        commission  REAL NOT NULL DEFAULT 0,
        mt5_deal_id INTEGER
    )
    """,
    """
    CREATE TABLE positions (
        instrument     TEXT PRIMARY KEY,
        qty            REAL NOT NULL,
        avg_price      REAL NOT NULL,
        realized_pnl   REAL NOT NULL DEFAULT 0,
        unrealized_pnl REAL NOT NULL DEFAULT 0,
        updated_at     TEXT NOT NULL
    )
    """,
    # --- indexes ----------------------------------------------------------
    "CREATE INDEX idx_trials_hypothesis ON trials_ledger(hypothesis_id)",
    "CREATE INDEX idx_alpha_status ON alpha_registry(status)",
    "CREATE INDEX idx_risk_kind ON risk_registry(kind)",
    "CREATE INDEX idx_orders_status ON orders(status)",
    "CREATE INDEX idx_fills_order ON fills(order_id)",
    "CREATE INDEX idx_runs_status ON research_runs(status)",
)

MIGRATION = Migration(version=1, name="core", statements=STATEMENTS)
