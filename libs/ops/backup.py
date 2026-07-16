"""Backup and restore for the SQLite system of record.

Uses SQLite's online backup API for a consistent copy (safe while the DB is open), records a
sha256 manifest for tamper/corruption detection, and provides a restore drill that proves a backup
actually restores and passes an integrity + schema-version check. Deterministic and side-effect
explicit (writes only under the destination directory).
"""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from libs.core.time import to_iso8601, utcnow
from libs.ops.errors import OpsError
from libs.store.connection import Database
from libs.store.migrations import current_version

_DB_NAME = "sor.sqlite"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class BackupManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    created_at: str
    db_version: int
    files: dict[str, str] = Field(default_factory=dict)  # relative name -> sha256


class BackupManager:
    """Creates verified, consistent backups of the system-of-record database."""

    def __init__(self, *, source_db: Path) -> None:
        self.source_db = Path(source_db)

    def backup(self, dest_dir: Path) -> BackupManifest:
        if not self.source_db.exists():
            raise OpsError(f"source db not found: {self.source_db}")
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_db = dest_dir / _DB_NAME

        # Online backup API: a consistent snapshot even if the source is in use.
        src = sqlite3.connect(str(self.source_db))
        try:
            dst = sqlite3.connect(str(dest_db))
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()

        version = self._db_version(dest_db)
        manifest = BackupManifest(
            created_at=to_iso8601(utcnow()),
            db_version=version,
            files={_DB_NAME: _sha256_file(dest_db)},
        )
        (dest_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2), "utf-8")
        return manifest

    def verify(self, dest_dir: Path, manifest: BackupManifest) -> bool:
        """Recompute checksums and confirm the backup matches its manifest."""
        dest_dir = Path(dest_dir)
        for name, digest in manifest.files.items():
            path = dest_dir / name
            if not path.exists() or _sha256_file(path) != digest:
                return False
        return True

    @staticmethod
    def _db_version(db_path: Path) -> int:
        db = Database(db_path)
        try:
            return current_version(db)
        finally:
            db.close()


class RestoreDrill:
    """Proves a backup restores cleanly: integrity check + schema-version match + checksum."""

    def run(self, backup_dir: Path, manifest: BackupManifest, *, workdir: Path) -> bool:
        backup_dir = Path(backup_dir)
        workdir = Path(workdir)
        workdir.mkdir(parents=True, exist_ok=True)
        src_db = backup_dir / _DB_NAME
        if not src_db.exists() or _sha256_file(src_db) != manifest.files.get(_DB_NAME):
            return False
        restored = workdir / _DB_NAME
        shutil.copyfile(src_db, restored)

        db = Database(restored)
        try:
            integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                return False
            return current_version(db) == manifest.db_version
        finally:
            db.close()
