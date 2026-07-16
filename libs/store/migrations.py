"""A small, forward-only migration runner over SQLite.

Migrations are ordered :class:`Migration` objects (defined under ``migrations/``). Each is
a list of statements applied in one transaction and recorded in ``schema_migrations`` with a
content hash, so re-running is a no-op and drift is detectable. No destructive/ down paths —
v1.0 migrations are additive.
"""

from __future__ import annotations

from dataclasses import dataclass

from libs.core.time import to_iso8601, utcnow
from libs.store.connection import Database
from libs.store.hashchain import canonical_json, sha256_hex

_SCHEMA_MIGRATIONS = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    sha256     TEXT NOT NULL,
    applied_at TEXT NOT NULL
)
"""


@dataclass(frozen=True)
class Migration:
    """An ordered, immutable unit of schema change."""

    version: int
    name: str
    statements: tuple[str, ...]

    @property
    def sha256(self) -> str:
        return sha256_hex(canonical_json([self.version, self.name, list(self.statements)]))


def _ensure_bootstrap(db: Database) -> None:
    db.execute(_SCHEMA_MIGRATIONS)


def applied_versions(db: Database) -> list[int]:
    """Return the sorted versions already applied."""
    _ensure_bootstrap(db)
    rows = db.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
    return [int(row[0]) for row in rows]


def current_version(db: Database) -> int:
    """Return the highest applied version, or 0 if none."""
    versions = applied_versions(db)
    return versions[-1] if versions else 0


def run_migrations(db: Database, migrations: tuple[Migration, ...]) -> list[int]:
    """Apply all pending migrations in version order. Returns the versions applied now."""
    _ensure_bootstrap(db)
    done = set(applied_versions(db))
    ordered = sorted(migrations, key=lambda m: m.version)

    seen: set[int] = set()
    for migration in ordered:
        if migration.version in seen:
            raise ValueError(f"duplicate migration version {migration.version}")
        seen.add(migration.version)

    newly_applied: list[int] = []
    for migration in ordered:
        if migration.version in done:
            continue
        with db.transaction() as conn:
            for statement in migration.statements:
                conn.execute(statement)
            conn.execute(
                "INSERT INTO schema_migrations(version, name, sha256, applied_at) "
                "VALUES (?, ?, ?, ?)",
                (migration.version, migration.name, migration.sha256, to_iso8601(utcnow())),
            )
        newly_applied.append(migration.version)
    return newly_applied
