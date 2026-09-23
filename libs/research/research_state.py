"""The canonical research state store. One place that knows what the desk has tried.

WHY A STORE AND NOT MORE FILES. This desk already writes research state to a dozen artifacts --
research_queue.json, miner_candidates.json, UNIVERSAL_SURVIVORS.json, sleeve_registry.json,
lineage DAGs, anomaly dumps -- and each is authoritative for its own stage and blind to the rest.
The cost is not tidiness. It is that NOTHING CAN ANSWER A CROSS-STAGE QUESTION: which generator
produced the candidates that survived? which mechanism class has ever cashed? did this exact
hypothesis already die, in a different file, last week? Every one of those is the question that
decides where the next hour of compute goes, and the desk had to guess at all of them.

SQLITE, DELIBERATELY. It is in the standard library, it is a single file that survives a reboot,
it gives real transactions, and it can be queried by anything. A Postgres or Redis dependency on a
box with 3.8GB and no swap would be a new failure mode in exchange for features this scale cannot
use. The schema is append-mostly: rows are inserted and their STATE is updated, never deleted, so
the store is a ledger rather than a cache.

WHAT IT IS NOT. It is not a second source of truth for certificates or clocks -- those remain
UNIVERSAL_SURVIVORS.json and sleeve_registry.json, which the gauntlet and the forward engine own,
and which the desk box is authoritative for. This store RECORDS what happened; it never grants
authority. A row here saying PASSED is a note that a gate said so, not a certificate.

IDEMPOTENT BY FINGERPRINT. Every artifact carries a content fingerprint and is upserted on it, so
a miner re-proposing the same hypothesis after a restart updates one row instead of minting a
duplicate. Duplicate proposals are the silent way a trial count inflates and a deflated Sharpe
becomes a lie.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = _ROOT / "desks" / "mt5" / "data" / "research_state.db"

#: Lifecycle. Ordered weakest to strongest; a row may only move FORWARD, and every move records
#: the evidence that justified it. Mirrors the promotion firewall the desk already enforces.
STATES = ("PROPOSED", "EXPLAINED", "COMPILED", "SCREENED", "GATED", "CERTIFIED",
          "FORWARD", "LIVE", "RETIRED", "KILLED")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS artifacts (
    fingerprint   TEXT PRIMARY KEY,
    kind          TEXT NOT NULL,
    state         TEXT NOT NULL,
    generator     TEXT NOT NULL,
    mechanism     TEXT,
    symbol        TEXT,
    payload       TEXT NOT NULL,
    trials        INTEGER DEFAULT 0,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_state     ON artifacts(state);
CREATE INDEX IF NOT EXISTS ix_generator ON artifacts(generator);
CREATE INDEX IF NOT EXISTS ix_mechanism ON artifacts(mechanism);

CREATE TABLE IF NOT EXISTS transitions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint  TEXT NOT NULL,
    from_state   TEXT,
    to_state     TEXT NOT NULL,
    evidence     TEXT NOT NULL,
    at           TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_tr_fp ON transitions(fingerprint);

CREATE TABLE IF NOT EXISTS lineage (
    child   TEXT NOT NULL,
    parent  TEXT NOT NULL,
    op      TEXT NOT NULL,
    at      TEXT NOT NULL,
    PRIMARY KEY (child, parent)
);
"""

_LOCK = threading.Lock()


@dataclass(frozen=True)
class Artifact:
    fingerprint: str
    kind: str
    state: str
    generator: str
    mechanism: str | None
    symbol: str | None
    payload: dict[str, Any]
    trials: int
    created_at: str
    updated_at: str


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=30.0)
    try:
        c.execute("PRAGMA journal_mode=WAL")     # a reader never blocks the hourly writers
        c.executescript(_SCHEMA)
        yield c
        c.commit()
    finally:
        c.close()


def record(fingerprint: str, kind: str, generator: str, payload: dict[str, Any], *,
           mechanism: str | None = None, symbol: str | None = None,
           trials: int = 0, state: str = "PROPOSED") -> bool:
    """Upsert one artifact. Returns True if it was NEW.

    IDEMPOTENT ON THE FINGERPRINT. A generator that re-proposes the same thing after a restart
    updates one row; it does not mint a second. That matters beyond tidiness: duplicates inflate
    the trial count that deflated Sharpe charges against, so a store that double-counts proposals
    silently raises the bar every honest candidate must clear.
    """
    now = datetime.now(UTC).isoformat(timespec="seconds")
    blob = json.dumps(payload, sort_keys=True, default=str)
    with _LOCK, _conn() as c:
        cur = c.execute("SELECT state FROM artifacts WHERE fingerprint=?", (fingerprint,))
        row = cur.fetchone()
        if row is None:
            c.execute(
                "INSERT INTO artifacts (fingerprint, kind, state, generator, mechanism, symbol,"
                " payload, trials, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (fingerprint, kind, state, generator, mechanism, symbol, blob, trials, now, now))
            c.execute("INSERT INTO transitions (fingerprint, from_state, to_state, evidence, at)"
                      " VALUES (?,?,?,?,?)",
                      (fingerprint, None, state, f"proposed by {generator}", now))
            return True
        c.execute("UPDATE artifacts SET payload=?, trials=MAX(trials, ?), updated_at=?"
                  " WHERE fingerprint=?", (blob, trials, now, fingerprint))
        return False


def advance(fingerprint: str, to_state: str, evidence: str) -> str:
    """Move an artifact forward. Returns the resulting state.

    EVIDENCE IS REQUIRED AND BACKWARDS IS REFUSED. A state that can be set without saying why is
    a label, not a measurement, and a lifecycle that can run backwards lets a later pass quietly
    undo a verdict. Both rules are the promotion firewall this desk already enforces one layer up.
    """
    if to_state not in STATES:
        raise ValueError(f"unknown state {to_state!r}")
    if not evidence.strip():
        raise ValueError("a transition without evidence is a label, not a measurement")
    now = datetime.now(UTC).isoformat(timespec="seconds")
    with _LOCK, _conn() as c:
        row = c.execute("SELECT state FROM artifacts WHERE fingerprint=?",
                        (fingerprint,)).fetchone()
        if row is None:
            raise KeyError(fingerprint)
        cur_state = str(row[0])
        if STATES.index(to_state) < STATES.index(cur_state):
            return cur_state                      # never backwards; the caller learns nothing new
        c.execute("UPDATE artifacts SET state=?, updated_at=? WHERE fingerprint=?",
                  (to_state, now, fingerprint))
        c.execute("INSERT INTO transitions (fingerprint, from_state, to_state, evidence, at)"
                  " VALUES (?,?,?,?,?)", (fingerprint, cur_state, to_state, evidence, now))
    return to_state


def link(child: str, parent: str, op: str) -> None:
    """Record that `child` came from `parent` by `op`. The lineage graph, one edge at a time."""
    now = datetime.now(UTC).isoformat(timespec="seconds")
    with _LOCK, _conn() as c:
        c.execute("INSERT OR IGNORE INTO lineage (child, parent, op, at) VALUES (?,?,?,?)",
                  (child, parent, op, now))


def get(fingerprint: str) -> Artifact | None:
    with _conn() as c:
        r = c.execute("SELECT fingerprint, kind, state, generator, mechanism, symbol, payload,"
                      " trials, created_at, updated_at FROM artifacts WHERE fingerprint=?",
                      (fingerprint,)).fetchone()
    if r is None:
        return None
    return Artifact(r[0], r[1], r[2], r[3], r[4], r[5], json.loads(r[6]), r[7], r[8], r[9])


def generator_yield() -> list[dict[str, Any]]:
    """Rows produced and rows CASHED, per generator. The question the desk could not answer.

    THIS IS THE POINT OF THE STORE. Compute goes where yield is, and yield is measured at the far
    end -- certificates and forward clocks -- not at the near end where every generator looks busy.
    The desk already learned this the expensive way from `miner_candidates.per_source`: structured
    feeds converted at 100%, 96% and 64% while six prose sources converted 0 of 341, and that fact
    was only visible because ONE file happened to carry per-source counts. This makes it a
    standing query over every stage instead of an accident of one artifact's schema.
    """
    with _conn() as c:
        rows = c.execute(
            "SELECT generator, COUNT(*),"
            " SUM(CASE WHEN state IN ('CERTIFIED','FORWARD','LIVE') THEN 1 ELSE 0 END),"
            " SUM(CASE WHEN state='KILLED' THEN 1 ELSE 0 END), MAX(trials)"
            " FROM artifacts GROUP BY generator ORDER BY 2 DESC").fetchall()
    out = []
    for gen, n, cashed, killed, width in rows:
        # SEARCH WIDTH, NOT A SUM. Every candidate from one sweep carries that sweep's trial count
        # -- which is correct, because deflated Sharpe charges each of them for the full width it
        # was selected from. SUMMING those across candidates was meaningless: 200 candidates from
        # a 21,945-cell sweep reported 4,389,000 "trials", and trials_per_cash built on it would
        # have been off by the size of the docket. The width is the max, and cost per cash is
        # measured in CANDIDATES spent, which is the quantity the desk actually allocates.
        out.append({
            "generator": gen, "proposed": int(n), "cashed": int(cashed or 0),
            "killed": int(killed or 0), "search_width": int(width or 0),
            "yield_pct": round(100.0 * (cashed or 0) / n, 2) if n else 0.0,
            "proposed_per_cash": (round(n / cashed, 1) if cashed else None),
        })
    return out


def mechanism_yield() -> list[dict[str, Any]]:
    """The same question by mechanism class -- which CAUSES have ever cashed on this desk."""
    with _conn() as c:
        rows = c.execute(
            "SELECT COALESCE(mechanism,'UNNAMED'), COUNT(*),"
            " SUM(CASE WHEN state IN ('CERTIFIED','FORWARD','LIVE') THEN 1 ELSE 0 END)"
            " FROM artifacts GROUP BY 1 ORDER BY 2 DESC").fetchall()
    return [{"mechanism": m, "proposed": int(n), "cashed": int(c_ or 0),
             "yield_pct": round(100.0 * (c_ or 0) / n, 2) if n else 0.0}
            for m, n, c_ in rows]


def census() -> dict[str, Any]:
    """What the store holds, by state. For the health fences."""
    with _conn() as c:
        by_state = dict(c.execute("SELECT state, COUNT(*) FROM artifacts GROUP BY state")
                        .fetchall())
        total = c.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]
        edges = c.execute("SELECT COUNT(*) FROM lineage").fetchone()[0]
    return {"total": int(total), "by_state": {k: int(v) for k, v in by_state.items()},
            "lineage_edges": int(edges), "db": str(DB_PATH),
            "note": "Records what happened. Never grants authority: certificates and clocks "
                    "remain owned by the gauntlet and the forward engine."}
