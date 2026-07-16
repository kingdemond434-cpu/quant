"""Config version history.

Records the content and hash of every distinct configuration the system has run under, so a
run's ``config_hash`` (Stage 1 reproducibility stamp) can be resolved back to exact content.
Identical configs collapse to one row (the hash is unique).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from typing import Any

from libs.core.config import hash_config
from libs.core.ids import generate_id
from libs.core.time import to_iso8601, utcnow
from libs.store.connection import Database
from libs.store.hashchain import canonical_json
from libs.store.models import ConfigVersion


def _row_to_version(row: sqlite3.Row) -> ConfigVersion:
    return ConfigVersion(
        id=row["id"],
        created_at=row["created_at"],
        config_hash=row["config_hash"],
        environment=row["environment"],
        content=json.loads(row["content_json"]),
        note=row["note"],
    )


def record_config_version(
    db: Database,
    config: Mapping[str, Any],
    *,
    environment: str | None = None,
    note: str | None = None,
) -> ConfigVersion:
    """Record a config version (idempotent on the config hash) and return it."""
    config_dict = dict(config)
    config_hash = hash_config(config_dict)
    existing = get_config_version(db, config_hash)
    if existing is not None:
        return existing
    version_id = generate_id("cfg")
    created_at = to_iso8601(utcnow())
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO config_versions "
            "(id, created_at, config_hash, environment, content_json, note) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (version_id, created_at, config_hash, environment, canonical_json(config_dict), note),
        )
    version = get_config_version(db, config_hash)
    assert version is not None
    return version


def get_config_version(db: Database, config_hash: str) -> ConfigVersion | None:
    row = db.execute(
        "SELECT * FROM config_versions WHERE config_hash = ?", (config_hash,)
    ).fetchone()
    return _row_to_version(row) if row else None


def list_config_versions(db: Database) -> list[ConfigVersion]:
    rows = db.execute("SELECT * FROM config_versions ORDER BY created_at").fetchall()
    return [_row_to_version(row) for row in rows]
