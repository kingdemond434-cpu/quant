"""SQLite connection management — ACID, WAL, single-writer.

The :class:`Database` wraps one connection configured for the platform's invariants:
WAL journaling (one writer, many readers), enforced foreign keys, and manual transaction
control. Readers (e.g. dashboards) open a separate read-only connection that physically
cannot write — the single-writer rule made structural.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

# Applied to every writable connection.
_WRITE_PRAGMAS: tuple[str, ...] = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA foreign_keys=ON",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA busy_timeout=5000",
)
_READ_PRAGMAS: tuple[str, ...] = (
    "PRAGMA foreign_keys=ON",
    "PRAGMA busy_timeout=5000",
)


class Database:
    """A single SQLite connection with WAL + foreign keys + manual transactions."""

    def __init__(self, path: str | Path, *, read_only: bool = False) -> None:
        self.path = Path(path)
        self.read_only = read_only
        if read_only:
            uri = f"file:{self.path}?mode=ro"
            self._conn = sqlite3.connect(uri, uri=True, isolation_level=None)
            pragmas = _READ_PRAGMAS
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.path), isolation_level=None)
            pragmas = _WRITE_PRAGMAS
        self._conn.row_factory = sqlite3.Row
        for pragma in pragmas:
            self._conn.execute(pragma)

    @property
    def connection(self) -> sqlite3.Connection:
        """The underlying connection (use within :meth:`transaction` for writes)."""
        return self._conn

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> sqlite3.Cursor:
        """Execute a single statement (autocommit outside a transaction block)."""
        return self._conn.execute(sql, params)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Run a block atomically; commit on success, roll back on any exception."""
        if self.read_only:
            raise RuntimeError("cannot open a write transaction on a read-only Database")
        self._conn.execute("BEGIN")
        try:
            yield self._conn
            self._conn.execute("COMMIT")
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise

    def journal_mode(self) -> str:
        """Return the active journal mode (``wal`` for on-disk databases)."""
        row = self._conn.execute("PRAGMA journal_mode").fetchone()
        return str(row[0]).lower()

    def close(self) -> None:
        """Close the connection."""
        self._conn.close()

    def __enter__(self) -> Database:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
