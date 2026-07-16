"""Snapshot catalog + database snapshot/restore.

Two snapshot kinds share one catalog:

* ``database`` — a consistent point-in-time copy of the SQLite system of record (via the
  SQLite online-backup API), hashed for tamper detection. :func:`create_snapshot` /
  :func:`restore_snapshot`.
* ``dataset`` — a reference to an immutable Parquet dataset version (registered by Stage 3
  via :func:`register_dataset_snapshot`) so an experiment can bind an exact data version.
"""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from libs.core.ids import generate_id
from libs.core.time import to_iso8601, utcnow
from libs.store.connection import Database
from libs.store.hashchain import canonical_json
from libs.store.models import SnapshotRecord


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _row_to_snapshot(row: sqlite3.Row) -> SnapshotRecord:
    import json

    return SnapshotRecord(
        id=row["id"],
        created_at=row["created_at"],
        kind=row["kind"],
        label=row["label"],
        path=row["path"],
        sha256=row["sha256"],
        row_counts=json.loads(row["row_counts_json"]) if row["row_counts_json"] else None,
        meta=json.loads(row["meta_json"]) if row["meta_json"] else None,
    )


def _insert_catalog_row(
    db: Database,
    *,
    snapshot_id: str,
    kind: str,
    label: str | None,
    path: str | None,
    sha256: str | None,
    row_counts: Mapping[str, Any] | None,
    meta: Mapping[str, Any] | None,
) -> SnapshotRecord:
    created_at = to_iso8601(utcnow())
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO snapshots "
            "(id, created_at, kind, label, path, sha256, row_counts_json, meta_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                snapshot_id, created_at, kind, label, path, sha256,
                canonical_json(dict(row_counts)) if row_counts is not None else None,
                canonical_json(dict(meta)) if meta is not None else None,
            ),
        )
    record = get_snapshot(db, snapshot_id)
    assert record is not None
    return record


def create_snapshot(
    db: Database,
    snapshot_dir: str | Path,
    *,
    label: str | None = None,
    meta: Mapping[str, Any] | None = None,
) -> SnapshotRecord:
    """Create a consistent database snapshot file and register it in the catalog."""
    snapshot_dir = Path(snapshot_dir)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_id = generate_id("snap")
    target = snapshot_dir / f"{snapshot_id}.sqlite"

    dest = sqlite3.connect(str(target))
    try:
        db.connection.backup(dest)
    finally:
        dest.close()

    sha256 = _sha256_file(target)
    return _insert_catalog_row(
        db,
        snapshot_id=snapshot_id,
        kind="database",
        label=label,
        path=str(target),
        sha256=sha256,
        row_counts=None,
        meta=meta,
    )


def restore_snapshot(db: Database, snapshot_id: str, target_path: str | Path) -> Path:
    """Restore a database snapshot to ``target_path`` after verifying its hash.

    Raises:
        KeyError: if the snapshot id is unknown.
        ValueError: if the snapshot is not a database snapshot, the file is missing, or its
            SHA-256 no longer matches the catalog (tamper detection).
    """
    record = get_snapshot(db, snapshot_id)
    if record is None:
        raise KeyError(f"snapshot not found: {snapshot_id}")
    if record.kind != "database":
        raise ValueError(f"snapshot {snapshot_id} is not a database snapshot")
    if record.path is None:
        raise ValueError(f"snapshot {snapshot_id} has no file path")
    source = Path(record.path)
    if not source.is_file():
        raise ValueError(f"snapshot file is missing: {source}")
    actual = _sha256_file(source)
    if actual != record.sha256:
        raise ValueError(
            f"snapshot {snapshot_id} failed integrity check: "
            f"expected {record.sha256}, got {actual}"
        )
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return target


def register_dataset_snapshot(
    db: Database,
    *,
    label: str,
    path: str,
    sha256: str,
    row_counts: Mapping[str, Any] | None = None,
    meta: Mapping[str, Any] | None = None,
) -> SnapshotRecord:
    """Register an immutable Parquet dataset version in the catalog (used by Stage 3)."""
    snapshot_id = generate_id("snap")
    return _insert_catalog_row(
        db,
        snapshot_id=snapshot_id,
        kind="dataset",
        label=label,
        path=path,
        sha256=sha256,
        row_counts=row_counts,
        meta=meta,
    )


def get_snapshot(db: Database, snapshot_id: str) -> SnapshotRecord | None:
    row = db.execute("SELECT * FROM snapshots WHERE id = ?", (snapshot_id,)).fetchone()
    return _row_to_snapshot(row) if row else None


def list_snapshots(db: Database, *, kind: str | None = None) -> list[SnapshotRecord]:
    if kind is None:
        rows = db.execute("SELECT * FROM snapshots ORDER BY created_at").fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM snapshots WHERE kind = ? ORDER BY created_at", (kind,)
        ).fetchall()
    return [_row_to_snapshot(row) for row in rows]
