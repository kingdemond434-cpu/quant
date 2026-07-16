"""Tests for the snapshot catalog and database snapshot/restore."""

from __future__ import annotations

from pathlib import Path

import pytest

from libs.store.audit import AuditLog
from libs.store.connection import Database
from libs.store.snapshots import (
    create_snapshot,
    get_snapshot,
    list_snapshots,
    register_dataset_snapshot,
    restore_snapshot,
)


def test_create_snapshot_writes_file_and_catalog(db: Database, tmp_path: Path) -> None:
    AuditLog(db).append("a", actor="x", inputs={"i": 1})
    record = create_snapshot(db, tmp_path / "snaps", label="nightly")
    assert record.kind == "database"
    assert record.label == "nightly"
    assert record.path is not None
    assert Path(record.path).is_file()
    assert record.sha256 is not None and len(record.sha256) == 64
    assert get_snapshot(db, record.id) is not None


def test_restore_snapshot_roundtrip(db: Database, tmp_path: Path) -> None:
    AuditLog(db).append("a", actor="x", inputs={"i": 1})
    record = create_snapshot(db, tmp_path / "snaps")
    target = tmp_path / "restored.sqlite"
    restored = restore_snapshot(db, record.id, target)
    assert restored == target
    assert target.is_file()
    # the restored database contains the audit row
    restored_db = Database(target)
    try:
        assert restored_db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 1
    finally:
        restored_db.close()


def test_restore_detects_tampering(db: Database, tmp_path: Path) -> None:
    record = create_snapshot(db, tmp_path / "snaps")
    assert record.path is not None
    Path(record.path).write_bytes(b"corrupted")
    with pytest.raises(ValueError):
        restore_snapshot(db, record.id, tmp_path / "restored.sqlite")


def test_restore_unknown_snapshot_raises(db: Database, tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        restore_snapshot(db, "snap_missing", tmp_path / "x.sqlite")


def test_dataset_snapshot_registration(db: Database) -> None:
    record = register_dataset_snapshot(
        db, label="gold_2026", path="lake/gold/XAUUSD", sha256="a" * 64,
        row_counts={"XAUUSD": 5000},
    )
    assert record.kind == "dataset"
    assert record.row_counts == {"XAUUSD": 5000}
    assert [r.id for r in list_snapshots(db, kind="dataset")] == [record.id]


def test_restore_rejects_dataset_snapshot(db: Database, tmp_path: Path) -> None:
    record = register_dataset_snapshot(db, label="x", path="lake/x", sha256="b" * 64)
    with pytest.raises(ValueError):
        restore_snapshot(db, record.id, tmp_path / "x.sqlite")
