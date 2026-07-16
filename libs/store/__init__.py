"""``libs.store`` — the SQLite system of record.

ACID, WAL, single-writer. Hash-chained, append-only audit log and trials ledger; mutable
registries; order/fill/position tables (with the structural risk-approval invariant); a
snapshot catalog with database snapshot/restore; and config-version history.
"""

from __future__ import annotations

from libs.store.audit import AuditLog, verify_audit_chain
from libs.store.config_versions import (
    get_config_version,
    list_config_versions,
    record_config_version,
)
from libs.store.connection import Database
from libs.store.hashchain import (
    GENESIS_PREV_HASH,
    canonical_json,
    compute_chain_hash,
    sha256_hex,
    verify_chain,
)
from libs.store.migrations import (
    Migration,
    applied_versions,
    current_version,
    run_migrations,
)
from libs.store.models import (
    Alpha,
    AuditEntry,
    ChainVerification,
    ConfigVersion,
    Fill,
    Order,
    Position,
    ResearchRun,
    RiskRecord,
    SnapshotRecord,
    TrialRecord,
)
from libs.store.registries import AlphaRegistry, ResearchRuns, RiskRegistry
from libs.store.snapshots import (
    create_snapshot,
    get_snapshot,
    list_snapshots,
    register_dataset_snapshot,
    restore_snapshot,
)
from libs.store.trading import OrderStore
from libs.store.trials import TrialsLedger, verify_trials_chain

__all__ = [  # noqa: RUF022  # grouped by concern
    # connection / migrations
    "Database",
    "Migration",
    "run_migrations",
    "applied_versions",
    "current_version",
    # hash chain
    "GENESIS_PREV_HASH",
    "canonical_json",
    "sha256_hex",
    "compute_chain_hash",
    "verify_chain",
    # audit + trials
    "AuditLog",
    "verify_audit_chain",
    "TrialsLedger",
    "verify_trials_chain",
    # registries
    "ResearchRuns",
    "AlphaRegistry",
    "RiskRegistry",
    # trading
    "OrderStore",
    # snapshots
    "create_snapshot",
    "restore_snapshot",
    "register_dataset_snapshot",
    "get_snapshot",
    "list_snapshots",
    # config versions
    "record_config_version",
    "get_config_version",
    "list_config_versions",
    # models
    "AuditEntry",
    "TrialRecord",
    "ResearchRun",
    "Alpha",
    "RiskRecord",
    "Order",
    "Fill",
    "Position",
    "SnapshotRecord",
    "ConfigVersion",
    "ChainVerification",
]
