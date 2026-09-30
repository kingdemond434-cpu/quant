"""The canonical cell registry: every cell's schema row and every status change it went through.

Each pipeline stage writes here and only moves a cell FORWARD; there is no path from QUEUED to
EVALUATED that does not pass through the preregistration seal (`transition` refuses it), which
is how "no stage can skip downstream" is enforced rather than described.

The event table is append-only and carries a timestamp per transition, so queue ages per stage
and the source -> evaluation latency are measured from the record of what happened, not from a
counter that can drift.
"""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from libs.mining.pit_store import iso, utcnow

#: The schema's statuses. BLOCKED_* is a family: the suffix names what blocked it.
STATUSES: tuple[str, ...] = ("TESTABLE", "QUEUED", "EVALUATING", "EVALUATED", "RESEARCH_ONLY")
BLOCKED_PREFIX = "BLOCKED_"

#: Stage a status sits in, for queue-age accounting.
STAGE_OF_STATUS: dict[str, str] = {
    "TESTABLE": "compile",        # extracted and compiled, waiting for its seal
    "QUEUED": "preregister",      # sealed, waiting to be donated to the gauntlet docket
    "EVALUATING": "gauntlet",     # in the docket, waiting for a verdict
}

#: Allowed forward moves. EVALUATED is reachable only from EVALUATING, and EVALUATING only
#: from QUEUED, which only the preregistration seal produces. A cell killed before the
#: evaluator is BLOCKED_<REASON> with its rejection code; EVALUATED means the gauntlet (or the
#: seal check on its verdict) ruled.
_ALLOWED: dict[str, frozenset[str]] = {
    "": frozenset({"TESTABLE", "RESEARCH_ONLY", "BLOCKED_*"}),
    "TESTABLE": frozenset({"QUEUED", "RESEARCH_ONLY", "BLOCKED_*"}),
    "QUEUED": frozenset({"EVALUATING", "BLOCKED_*"}),
    "EVALUATING": frozenset({"EVALUATED", "BLOCKED_*"}),
    "RESEARCH_ONLY": frozenset({"TESTABLE", "BLOCKED_*"}),
    "BLOCKED_*": frozenset({"TESTABLE", "QUEUED", "RESEARCH_ONLY", "BLOCKED_*"}),
    "EVALUATED": frozenset(),
}


class IllegalTransitionError(RuntimeError):
    """A stage tried to skip one downstream of it (or move a cell backwards)."""


def _cls(status: str) -> str:
    return "BLOCKED_*" if status.startswith(BLOCKED_PREFIX) else status


@dataclass
class Cell:
    """The MT5_GLOBAL_MINING_V1 cell schema, field for field."""
    cell_id: str
    source_id: str
    source_uri: str
    source_version: str
    content_hash: str
    publication_time: str | None
    acquisition_time: str
    available_for_decision_at: str
    original_language: str
    translation_provenance: str
    mechanism_family: str
    mechanism_subtype: str
    directly_published_rules: dict[str, Any] | None = None
    reconstructed_rules: dict[str, Any] | None = None
    required_data: list[str] = field(default_factory=list)
    required_instruments: list[str] = field(default_factory=list)
    falsifier: str = ""
    preregistration_id: str = ""
    trial_lineage_id: str = ""
    status: str = ""
    rejection_reason: str = ""
    rejection_stage: str = ""
    # lineage and joins (beyond the schema's minimum, all needed downstream)
    record_id: str = ""
    parent_cell_id: str = ""
    trial_family_id: str = ""
    mechanism_hash: str = ""
    duplicate_of: str = ""
    claim: str = ""
    spec: dict[str, Any] | None = None
    gauntlet_cell: str = ""
    verdict: dict[str, Any] | None = None
    use: str = "direct_cells"            # direct_cells | indirect_cells | allocation_intel

    def as_row(self) -> dict[str, Any]:
        return asdict(self)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS cells (
    cell_id TEXT PRIMARY KEY,
    record_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    status TEXT NOT NULL,
    rejection_reason TEXT NOT NULL DEFAULT '',
    rejection_stage TEXT NOT NULL DEFAULT '',
    mechanism_hash TEXT NOT NULL DEFAULT '',
    trial_family_id TEXT NOT NULL DEFAULT '',
    gauntlet_cell TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    doc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS cells_status ON cells(status);
CREATE INDEX IF NOT EXISTS cells_gauntlet ON cells(gauntlet_cell);
CREATE INDEX IF NOT EXISTS cells_source ON cells(source_id);
CREATE TABLE IF NOT EXISTS cell_events (
    cell_id TEXT NOT NULL, at TEXT NOT NULL, from_status TEXT NOT NULL,
    to_status TEXT NOT NULL, stage TEXT NOT NULL, reason TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS cell_events_cell ON cell_events(cell_id, at);
CREATE INDEX IF NOT EXISTS cell_events_at ON cell_events(at);
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT NOT NULL);
"""


class CellRegistry:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(_SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=60.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    # --------------------------------------------------------------------------- writes
    def add(self, cell: Cell, *, stage: str, now: datetime | None = None) -> bool:
        """Insert a new cell in its initial status. False when the cell_id already exists."""
        t = iso(now or utcnow())
        if _cls(cell.status) not in _ALLOWED[""]:
            raise IllegalTransitionError(f"a new cell cannot start in {cell.status!r}")
        with self._conn() as c:
            if c.execute("SELECT 1 FROM cells WHERE cell_id=?", (cell.cell_id,)).fetchone():
                return False
            c.execute("INSERT INTO cells VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                      (cell.cell_id, cell.record_id, cell.source_id, cell.status,
                       cell.rejection_reason, cell.rejection_stage, cell.mechanism_hash,
                       cell.trial_family_id, cell.gauntlet_cell, t, t,
                       json.dumps(cell.as_row(), ensure_ascii=False, default=str)))
            c.execute("INSERT INTO cell_events VALUES (?,?,?,?,?,?)",
                      (cell.cell_id, t, "", cell.status, stage, cell.rejection_reason))
        return True

    def transition(self, cell_id: str, to_status: str, *, stage: str, reason: str = "",
                   updates: Mapping[str, Any] | None = None,
                   now: datetime | None = None) -> Cell:
        t = iso(now or utcnow())
        with self._conn() as c:
            row = c.execute("SELECT status, doc FROM cells WHERE cell_id=?",
                            (cell_id,)).fetchone()
            if row is None:
                raise KeyError(cell_id)
            frm = str(row["status"])
            if _cls(to_status) not in _ALLOWED[_cls(frm)]:
                raise IllegalTransitionError(f"{cell_id}: {frm} -> {to_status} skips a stage")
            doc = json.loads(str(row["doc"]))
            doc.update(dict(updates or {}))
            doc["status"] = to_status
            if reason:
                doc["rejection_reason"] = reason
                doc["rejection_stage"] = stage
            c.execute("UPDATE cells SET status=?, rejection_reason=?, rejection_stage=?, "
                      "gauntlet_cell=?, mechanism_hash=?, trial_family_id=?, updated_at=?, "
                      "doc=? WHERE cell_id=?",
                      (to_status, doc.get("rejection_reason") or "",
                       doc.get("rejection_stage") or "", doc.get("gauntlet_cell") or "",
                       doc.get("mechanism_hash") or "", doc.get("trial_family_id") or "", t,
                       json.dumps(doc, ensure_ascii=False, default=str), cell_id))
            c.execute("INSERT INTO cell_events VALUES (?,?,?,?,?,?)",
                      (cell_id, t, frm, to_status, stage, reason))
        return Cell(**doc)

    def update_doc(self, cell_id: str, updates: Mapping[str, Any]) -> None:
        with self._conn() as c:
            row = c.execute("SELECT doc FROM cells WHERE cell_id=?", (cell_id,)).fetchone()
            if row is None:
                raise KeyError(cell_id)
            doc = json.loads(str(row["doc"]))
            doc.update(dict(updates))
            c.execute("UPDATE cells SET doc=?, gauntlet_cell=?, mechanism_hash=?, "
                      "trial_family_id=? WHERE cell_id=?",
                      (json.dumps(doc, ensure_ascii=False, default=str),
                       doc.get("gauntlet_cell") or "", doc.get("mechanism_hash") or "",
                       doc.get("trial_family_id") or "", cell_id))

    def kv_get(self, k: str, default: str = "") -> str:
        with self._conn() as c:
            row = c.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
        return str(row["v"]) if row is not None else default

    def kv_set(self, k: str, v: str) -> None:
        with self._conn() as c:
            c.execute("INSERT INTO kv VALUES (?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                      (k, v))

    # ---------------------------------------------------------------------------- reads
    def get(self, cell_id: str) -> Cell | None:
        with self._conn() as c:
            row = c.execute("SELECT doc FROM cells WHERE cell_id=?", (cell_id,)).fetchone()
        return Cell(**json.loads(str(row["doc"]))) if row is not None else None

    def by_status(self, status: str, limit: int = 100_000) -> list[Cell]:
        with self._conn() as c:
            rows = c.execute("SELECT doc FROM cells WHERE status=? ORDER BY created_at LIMIT ?",
                             (status, int(limit))).fetchall()
        return [Cell(**json.loads(str(r["doc"]))) for r in rows]

    def by_gauntlet_cell(self, gauntlet_cell: str) -> list[Cell]:
        with self._conn() as c:
            rows = c.execute("SELECT doc FROM cells WHERE gauntlet_cell=? AND status IN "
                             "('EVALUATING','QUEUED')", (gauntlet_cell,)).fetchall()
        return [Cell(**json.loads(str(r["doc"]))) for r in rows]

    def status_counts(self) -> dict[str, int]:
        with self._conn() as c:
            rows = c.execute("SELECT status, COUNT(*) AS n FROM cells GROUP BY status"
                             ).fetchall()
        return {str(r["status"]): int(r["n"]) for r in rows}

    def events_since(self, since: datetime) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM cell_events WHERE at >= ? ORDER BY at",
                             (iso(since),)).fetchall()
        return [dict(r) for r in rows]

    def open_ages(self, now: datetime | None = None) -> dict[str, list[float]]:
        """Age in days of every cell currently waiting in each stage, since it entered it."""
        t = now or utcnow()
        out: dict[str, list[float]] = {s: [] for s in STAGE_OF_STATUS.values()}
        with self._conn() as c:
            rows = c.execute("SELECT status, updated_at FROM cells WHERE status IN "
                             "('TESTABLE','QUEUED','EVALUATING')").fetchall()
        for r in rows:
            try:
                entered = datetime.fromisoformat(str(r["updated_at"]))
            except ValueError:
                continue
            out[STAGE_OF_STATUS[str(r["status"])]].append(
                max(0.0, (t - entered).total_seconds() / 86_400))
        return out

    def evaluated_by_source(self, since: datetime) -> dict[str, int]:
        """Cells that reached EVALUATED since `since`, per source: the consumer receipt."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT c.source_id AS s, COUNT(DISTINCT e.cell_id) AS n FROM cell_events e "
                "JOIN cells c ON c.cell_id=e.cell_id WHERE e.to_status='EVALUATED' "
                "AND e.at >= ? GROUP BY c.source_id", (iso(since),)).fetchall()
        return {str(r["s"]): int(r["n"]) for r in rows}

    def created_since(self, since: datetime) -> list[Cell]:
        with self._conn() as c:
            rows = c.execute("SELECT doc FROM cells WHERE created_at >= ?",
                             (iso(since),)).fetchall()
        return [Cell(**json.loads(str(r["doc"]))) for r in rows]

    def all_cells(self) -> list[Cell]:
        with self._conn() as c:
            rows = c.execute("SELECT doc FROM cells").fetchall()
        return [Cell(**json.loads(str(r["doc"]))) for r in rows]
