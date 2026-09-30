"""Point-in-time storage for everything the miners fetch, with as-of reads enforced at READ time.

Every record carries three clocks:

    publication_time           what the source says (may be absent, may be wrong)
    acquisition_time           when this desk fetched it (always present, never backdated)
    available_for_decision_at  when a decision may first use it

`available_for_decision_at` is the acquisition time unless the source's own timestamp is
IMMUTABLE (a GitHub commit, a Reddit post's created_utc, a Telegram message id's date) and not
later than the fetch; a page that can be edited silently (a forum post, a broker spec page, a
prop firm's rules) is knowable only from the moment we saw it. A record dated in the future is
stored with that future time, so no earlier decision can see it.

REVISIONS NEVER OVERWRITE. The same URI with different content is a new VINTAGE chained to its
predecessor (`revision_of`, `revision_n`), available only from its own acquisition. A backtest
at t reads the vintage that existed at t (`as_of`), the live desk reads the latest. A source
that claimed immutable timestamps and then changed content under an unchanged timestamp has
proved the claim false: the new vintage is flagged LEAKAGE_REVISION and every later record from
that source is stamped at acquisition.

`as_of` is the only read path for decisions, and it filters `available_for_decision_at <=
decision_time` in SQL, so no caller can forget the join.

Every record gets a STATE in the same transaction that stores it: there is no instant at which
a fetched record exists without one ("zero silent drops").
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

#: Record states. ACQUIRED is the only initial state; the rest are written by later stages.
RECORD_STATES: tuple[str, ...] = (
    "ACQUIRED",            # stored, not yet extracted
    "EXTRACTED",           # produced >= 1 cell
    "HANDED_OFF",          # produced claims that went to the deepening worker (LLM extraction)
    "FEED_PUBLISHED",      # a broker/prop fact record published to the mechanics feed
    "REJECTED",            # killed with a reason code in the rejection ledger
    "DUPLICATE_CONTENT",   # byte-identical to a record already stored (same source)
    "ROUTED",              # a civilization record whose ontology outcomes went to a non-gauntlet
                           # consumer, or whose alpha rules wait in the PARKED queue
                           # (libs/civilizations/resident.py)
)

#: Slack for clock skew before a publication time counts as "in the future".
FUTURE_SLACK = timedelta(minutes=5)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    record_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    source_uri TEXT NOT NULL,
    source_version TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    publication_time TEXT,
    acquisition_time TEXT NOT NULL,
    available_for_decision_at TEXT NOT NULL,
    original_language TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    meta TEXT NOT NULL DEFAULT '{}',
    revision_of TEXT NOT NULL DEFAULT '',
    revision_n INTEGER NOT NULL DEFAULT 0,
    flags TEXT NOT NULL DEFAULT '',
    state TEXT NOT NULL,
    state_reason TEXT NOT NULL DEFAULT '',
    state_stage TEXT NOT NULL DEFAULT '',
    state_at TEXT NOT NULL,
    n_cells INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS records_uri ON records(source_uri, acquisition_time);
CREATE INDEX IF NOT EXISTS records_state ON records(state);
CREATE INDEX IF NOT EXISTS records_avail ON records(available_for_decision_at);
CREATE UNIQUE INDEX IF NOT EXISTS records_content ON records(source_id, source_uri, content_hash);
CREATE TABLE IF NOT EXISTS untrusted_clock_sources (
    source_id TEXT PRIMARY KEY, since TEXT NOT NULL, why TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source_runs (
    source_id TEXT NOT NULL, at TEXT NOT NULL, outcome TEXT NOT NULL,
    fetched INTEGER NOT NULL, new INTEGER NOT NULL, detail TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS source_runs_src ON source_runs(source_id, at);
"""


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


def iso(t: datetime) -> str:
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    return t.astimezone(UTC).isoformat(timespec="seconds")


def parse_time(v: Any) -> datetime | None:
    """ISO string, epoch seconds or datetime -> aware UTC datetime; None when unparseable."""
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=UTC)
    if isinstance(v, (int, float)):
        try:
            return datetime.fromtimestamp(float(v), tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    s = str(v).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        t = datetime.fromisoformat(s)
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def content_hash(title: str, body: str) -> str:
    norm = " ".join(f"{title}\n{body}".split())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:24]


@dataclass
class RawRecord:
    """One fetched document, as the acquirer hands it to the store."""
    source_id: str
    source_uri: str
    body: str
    title: str = ""
    publication_time: str | None = None
    acquisition_time: str = ""
    source_version: str = "v1"
    original_language: str = ""
    immutable_time: bool = False
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PutResult:
    record_id: str
    inserted: bool
    revision_n: int
    flags: tuple[str, ...]


class PitStore:
    """SQLite, WAL, one file. Safe to open from several processes."""

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
            conn.execute("PRAGMA synchronous=NORMAL")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------------------ writes
    def put(self, rec: RawRecord, *, now: datetime | None = None) -> PutResult:
        """Store a record (idempotent on source+uri+content). Returns whether it was new.

        A second identical fetch is a no-op, which is what makes the acquirer's crash-resume
        safe: re-fetching the item a crash interrupted can neither lose it nor double it."""
        t_now = now or utcnow()
        acq = parse_time(rec.acquisition_time) or t_now
        chash = content_hash(rec.title, rec.body)
        rid = hashlib.sha256(f"{rec.source_id}|{rec.source_uri}|{chash}".encode()
                             ).hexdigest()[:20]
        pub = parse_time(rec.publication_time)
        flags: list[str] = []
        with self._conn() as c:
            hit = c.execute("SELECT record_id, revision_n FROM records WHERE record_id=?",
                            (rid,)).fetchone()
            if hit is not None:
                return PutResult(rid, False, int(hit["revision_n"]), ())
            prev = c.execute(
                "SELECT record_id, revision_n, publication_time, acquisition_time "
                "FROM records WHERE source_id=? AND source_uri=? "
                "ORDER BY acquisition_time DESC, revision_n DESC LIMIT 1",
                (rec.source_id, rec.source_uri)).fetchone()
            untrusted = c.execute("SELECT 1 FROM untrusted_clock_sources WHERE source_id=?",
                                  (rec.source_id,)).fetchone() is not None
            revision_of, revision_n = "", 0
            state, reason, stage = "ACQUIRED", "", ""
            if prev is not None:
                revision_of, revision_n = str(prev["record_id"]), int(prev["revision_n"]) + 1
                same_stamp = (pub is not None and prev["publication_time"]
                              and parse_time(prev["publication_time"]) == pub)
                if rec.immutable_time and not untrusted and same_stamp:
                    # Content changed under a timestamp the source called immutable: its clock
                    # cannot be used as availability, now or for any later record.
                    flags.append("backdated_revision")
                    state, reason, stage = "REJECTED", "LEAKAGE_REVISION", "pit"
                    c.execute("INSERT OR IGNORE INTO untrusted_clock_sources VALUES (?,?,?)",
                              (rec.source_id, iso(t_now),
                               f"content of {rec.source_uri} changed under publication_time "
                               f"{iso(pub) if pub else ''}"))
                    untrusted = True
            avail = acq
            if pub is not None and pub > acq + FUTURE_SLACK:
                # A future-dated observation: kept, and invisible until its own time.
                flags.append("future_dated")
                avail = pub
            elif (pub is not None and rec.immutable_time and not untrusted
                  and revision_n == 0):
                avail = min(pub, acq)
            c.execute(
                "INSERT INTO records (record_id, source_id, source_uri, source_version, "
                "content_hash, publication_time, acquisition_time, available_for_decision_at, "
                "original_language, title, body, meta, revision_of, revision_n, flags, state, "
                "state_reason, state_stage, state_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (rid, rec.source_id, rec.source_uri, rec.source_version or "v1", chash,
                 iso(pub) if pub else None, iso(acq), iso(avail), rec.original_language or "",
                 rec.title[:1000], rec.body[:200_000],
                 json.dumps(rec.meta, ensure_ascii=False, default=str), revision_of,
                 revision_n, ",".join(flags), state, reason, stage, iso(t_now)))
        return PutResult(rid, True, revision_n, tuple(flags))

    def set_state(self, record_id: str, state: str, *, reason: str = "", stage: str = "",
                  n_cells: int | None = None, now: datetime | None = None) -> None:
        if state not in RECORD_STATES:
            raise ValueError(f"unknown record state {state!r}")
        with self._conn() as c:
            if n_cells is None:
                c.execute("UPDATE records SET state=?, state_reason=?, state_stage=?, "
                          "state_at=? WHERE record_id=?",
                          (state, reason, stage, iso(now or utcnow()), record_id))
            else:
                c.execute("UPDATE records SET state=?, state_reason=?, state_stage=?, "
                          "state_at=?, n_cells=? WHERE record_id=?",
                          (state, reason, stage, iso(now or utcnow()), int(n_cells),
                           record_id))

    def log_run(self, source_id: str, outcome: str, fetched: int, new: int, detail: str = "",
                now: datetime | None = None) -> None:
        with self._conn() as c:
            c.execute("INSERT INTO source_runs VALUES (?,?,?,?,?,?)",
                      (source_id, iso(now or utcnow()), outcome, int(fetched), int(new),
                       detail[:500]))

    # ------------------------------------------------------------------------------- reads
    def get(self, record_id: str) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM records WHERE record_id=?", (record_id,)).fetchone()
        return _row(row) if row is not None else None

    def pending(self, limit: int = 1000) -> list[dict[str, Any]]:
        """Records still in ACQUIRED, oldest acquisition first."""
        with self._conn() as c:
            rows = c.execute("SELECT * FROM records WHERE state='ACQUIRED' "
                             "ORDER BY acquisition_time LIMIT ?", (int(limit),)).fetchall()
        return [_row(r) for r in rows]

    def as_of(self, decision_time: datetime, *, source_id: str | None = None,
              source_uri: str | None = None) -> list[dict[str, Any]]:
        """The latest vintage per URI that a decision at `decision_time` could have used.

        THE PIT JOIN LIVES HERE AND ONLY HERE: `available_for_decision_at <= decision_time` is
        in the SQL, so a record that was not yet knowable cannot reach the caller."""
        t = iso(decision_time)
        q = ("SELECT * FROM records WHERE available_for_decision_at <= ? "
             "AND state != 'REJECTED'")
        args: list[Any] = [t]
        if source_id is not None:
            q += " AND source_id = ?"
            args.append(source_id)
        if source_uri is not None:
            q += " AND source_uri = ?"
            args.append(source_uri)
        q += " ORDER BY source_uri, available_for_decision_at, revision_n"
        with self._conn() as c:
            rows = c.execute(q, args).fetchall()
        latest: dict[tuple[str, str], dict[str, Any]] = {}
        for r in rows:
            d = _row(r)
            latest[(str(d["source_id"]), str(d["source_uri"]))] = d
        return list(latest.values())

    def state_counts(self) -> dict[str, int]:
        with self._conn() as c:
            rows = c.execute("SELECT state, COUNT(*) AS n FROM records GROUP BY state"
                             ).fetchall()
        out = dict.fromkeys(RECORD_STATES, 0)
        for r in rows:
            out[str(r["state"])] = int(r["n"])
        return out

    def count(self, *, since: datetime | None = None) -> int:
        with self._conn() as c:
            if since is None:
                row = c.execute("SELECT COUNT(*) AS n FROM records").fetchone()
            else:
                row = c.execute("SELECT COUNT(*) AS n FROM records WHERE acquisition_time >= ?",
                                (iso(since),)).fetchone()
        return int(row["n"]) if row is not None else 0

    def last_runs(self) -> dict[str, dict[str, Any]]:
        """Latest fetch outcome per source."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT r.* FROM source_runs r JOIN (SELECT source_id, MAX(at) AS m FROM "
                "source_runs GROUP BY source_id) x ON r.source_id=x.source_id AND r.at=x.m"
            ).fetchall()
        return {str(r["source_id"]): dict(r) for r in rows}

    def records_by_source(self, since: datetime | None = None) -> dict[str, int]:
        with self._conn() as c:
            if since is None:
                rows = c.execute("SELECT source_id, COUNT(*) AS n FROM records "
                                 "GROUP BY source_id").fetchall()
            else:
                rows = c.execute("SELECT source_id, COUNT(*) AS n FROM records WHERE "
                                 "acquisition_time >= ? GROUP BY source_id",
                                 (iso(since),)).fetchall()
        return {str(r["source_id"]): int(r["n"]) for r in rows}


    def vintages(self, decision_time: datetime, *, source_id: str) -> list[dict[str, Any]]:
        """EVERY vintage of a source knowable at `decision_time`, oldest first (the forward
        laboratory needs the series, not just the latest page). Same PIT filter as `as_of`."""
        with self._conn() as c:
            rows = c.execute("SELECT * FROM records WHERE available_for_decision_at <= ? AND "
                             "source_id = ? ORDER BY available_for_decision_at, revision_n",
                             (iso(decision_time), source_id)).fetchall()
        return [_row(r) for r in rows]

    def first_seen_by_source(self) -> dict[str, str]:
        with self._conn() as c:
            rows = c.execute("SELECT source_id, MIN(acquisition_time) AS t FROM records "
                             "GROUP BY source_id").fetchall()
        return {str(r["source_id"]): str(r["t"]) for r in rows}


def _row(r: sqlite3.Row) -> dict[str, Any]:
    d = dict(r)
    try:
        d["meta"] = json.loads(str(d.get("meta") or "{}"))
    except ValueError:
        d["meta"] = {}
    d["flags"] = [f for f in str(d.get("flags") or "").split(",") if f]
    return d
