"""Read-only data access for the dashboard API.

Opens the existing SQLite system-of-record in immutable read-only mode (URI ``mode=ro``) and reads
the report JSONs the engines already emit. This module NEVER writes and NEVER imports engine logic
-- it is a pure presentation adapter over artifacts the backend produced.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
# Prefer the most complete research DB present; all share the m0005 ``research_candidates`` schema.
_DB_CANDIDATES = (
    "data/sor_research.sqlite",          # the autonomous daemon's SoR (queue + workers + ledger)
    "data/sor_research_lake_v2.sqlite",
    "data/sor_research_lake.sqlite",
    "data/sor_autodiscovery.sqlite",
    "data/sor.sqlite",
)


def research_db_path() -> Path | None:
    for rel in _DB_CANDIDATES:
        p = _ROOT / rel
        if p.exists():
            return p
    return None


def query(sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
    """Run a read-only query; returns [] if no DB or the table is absent (honest empty)."""
    path = research_db_path()
    if path is None:
        return []
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except sqlite3.OperationalError:
        return []  # table/column missing -> empty, not an error


def table_exists(name: str) -> bool:
    rows = query("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return bool(rows)


def schema_version() -> int:
    rows = query("SELECT MAX(version) AS v FROM schema_migrations")
    if rows and rows[0].get("v") is not None:
        return int(rows[0]["v"])
    return 0


def read_report(*relative: str) -> Any:
    """Read a JSON report, e.g. read_report('research_lake', 'survivor_report')."""
    p = _ROOT / "reports"
    for part in relative:
        p = p / part
    p = p.with_suffix(".json")
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text("utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
