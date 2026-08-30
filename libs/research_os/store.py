"""One queryable research memory. SQLite, append-only, machine-readable.

WHY THIS EXISTS (external audit, 2026-08-29)

    "Make research memory queryable by machine. Not giant markdown memory."
    "One persistent canonical ResearchArtifact/state store."

The desk's memory was spread across ~15 JSON artifacts, each written by whoever produced it and
read by whoever remembered it existed. That is fine for a dashboard and useless for a research
policy, because the questions that decide where to spend the next trial are all JOINS:

    which mechanisms failed for MEASUREMENT reasons rather than being refuted?
    which observables block the most mechanisms?
    which generator produces candidates that actually progress, versus pretty duplicates?
    what has this desk already tried at this coordinate?

None of those can be answered by reading a file. All of them are one SELECT.

APPEND-ONLY, AND THAT IS THE POINT. A research record that can be edited is a research record
that will be edited -- quietly, by a later process, in the direction that makes the current
hypothesis look better. Rows here are inserted and never updated; a changed verdict is a NEW row
with a later timestamp, so the history of what the desk believed is itself queryable.

WHY SQLITE AND NOT A SERVICE. It is in the standard library, needs no daemon, survives a reboot,
and this desk has already lost work to a component that required something to be running. A
research memory that is unavailable when the box is under pressure is a research memory that is
absent exactly when the desk is deciding what to cut.

IT STORES DECISIONS AND DIAGNOSES, NEVER PRICES. Bars live in parquet; this holds what the desk
CONCLUDED and why. Mixing them would make the file enormous and the queries slow, and the
conclusions are the part nothing else records.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "research_os.sqlite"

#: Every table is append-only. `ts` is when the row was WRITTEN, never when the thing happened --
#: those differ, and conflating them is how a backfilled record reads as a contemporaneous one.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS hypotheses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    hypothesis_id TEXT NOT NULL,
    origin TEXT,
    generator TEXT,
    mechanism TEXT,
    payer TEXT,
    coordinate TEXT,
    parent_ids TEXT,
    generation INTEGER DEFAULT 0,
    brain_version TEXT,
    spec TEXT
);
CREATE INDEX IF NOT EXISTS ix_hyp_mech ON hypotheses(mechanism);
CREATE INDEX IF NOT EXISTS ix_hyp_coord ON hypotheses(coordinate);

CREATE TABLE IF NOT EXISTS measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    hypothesis_id TEXT,
    mechanism TEXT,
    adapter TEXT,
    status TEXT,
    attributable INTEGER,
    pit_safe INTEGER,
    missing_observable TEXT,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS ix_meas_mech ON measurements(mechanism);
CREATE INDEX IF NOT EXISTS ix_meas_status ON measurements(status);

CREATE TABLE IF NOT EXISTS experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    hypothesis_id TEXT,
    mechanism TEXT,
    coordinate TEXT,
    symbol TEXT,
    n_trades INTEGER,
    exp_r_gross REAL,
    exp_r_net REAL,
    t_stat REAL,
    stage TEXT,
    passed INTEGER
);
CREATE INDEX IF NOT EXISTS ix_exp_mech ON experiments(mechanism);

CREATE TABLE IF NOT EXISTS failures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    hypothesis_id TEXT,
    mechanism TEXT,
    state TEXT NOT NULL,
    updates_posterior INTEGER,
    measurement_class TEXT,
    missing_observable TEXT,
    next_action TEXT,
    reason TEXT
);
CREATE INDEX IF NOT EXISTS ix_fail_state ON failures(state);
CREATE INDEX IF NOT EXISTS ix_fail_mech ON failures(mechanism);

CREATE TABLE IF NOT EXISTS generator_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    generator TEXT NOT NULL,
    model TEXT,
    proposed INTEGER DEFAULT 0,
    parsed INTEGER DEFAULT 0,
    compiled INTEGER DEFAULT 0,
    refused INTEGER DEFAULT 0,
    duplicate INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_gen ON generator_stats(generator);

CREATE TABLE IF NOT EXISTS data_needs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    observable TEXT NOT NULL,
    mechanisms_blocked TEXT,
    hypotheses_blocked INTEGER,
    value REAL,
    candidate_sources TEXT
);
CREATE INDEX IF NOT EXISTS ix_need_obs ON data_needs(observable);
"""


#: The complete set of tables. `summary` validates against this rather than interpolating a
#: caller-supplied name into SQL -- table names cannot be bound as parameters, so the allowlist
#: IS the parameterisation.
_TABLES = ("hypotheses", "measurements", "experiments", "failures",
           "generator_stats", "data_needs")


@contextmanager
def connect() -> Any:
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def record_hypothesis(**kw: Any) -> None:
    with connect() as c:
        c.execute(
            "INSERT INTO hypotheses (ts, hypothesis_id, origin, generator, mechanism, payer, "
            "coordinate, parent_ids, generation, brain_version, spec) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (_now(), kw.get("hypothesis_id", ""), kw.get("origin", ""), kw.get("generator", ""),
             kw.get("mechanism", ""), kw.get("payer", ""), kw.get("coordinate", ""),
             json.dumps(kw.get("parent_ids") or []), int(kw.get("generation", 0)),
             kw.get("brain_version", ""), json.dumps(kw.get("spec") or {})))


def record_measurement(**kw: Any) -> None:
    with connect() as c:
        c.execute(
            "INSERT INTO measurements (ts, hypothesis_id, mechanism, adapter, status, "
            "attributable, pit_safe, missing_observable, notes) VALUES (?,?,?,?,?,?,?,?,?)",
            (_now(), kw.get("hypothesis_id", ""), kw.get("mechanism", ""), kw.get("adapter", ""),
             kw.get("status", ""), int(bool(kw.get("attributable"))),
             int(bool(kw.get("pit_safe", True))), kw.get("missing_observable", ""),
             str(kw.get("notes", ""))[:600]))


def record_experiment(**kw: Any) -> None:
    with connect() as c:
        c.execute(
            "INSERT INTO experiments (ts, hypothesis_id, mechanism, coordinate, symbol, "
            "n_trades, exp_r_gross, exp_r_net, t_stat, stage, passed) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (_now(), kw.get("hypothesis_id", ""), kw.get("mechanism", ""),
             kw.get("coordinate", ""), kw.get("symbol", ""), int(kw.get("n_trades", 0) or 0),
             kw.get("exp_r_gross"), kw.get("exp_r_net"), kw.get("t_stat"),
             kw.get("stage", ""), int(bool(kw.get("passed")))))


def record_failure(diagnosis: Any, hypothesis_id: str = "") -> None:
    """Store a Diagnosis. The six states are the whole reason this table exists."""
    with connect() as c:
        c.execute(
            "INSERT INTO failures (ts, hypothesis_id, mechanism, state, updates_posterior, "
            "measurement_class, missing_observable, next_action, reason) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (_now(), hypothesis_id, getattr(diagnosis, "mechanism", ""),
             diagnosis.state, int(bool(diagnosis.updates_mechanism_posterior)),
             getattr(diagnosis, "measurement_class", ""),
             getattr(diagnosis, "missing_observable", ""),
             diagnosis.next_action, str(diagnosis.reason)[:600]))


def record_generator(**kw: Any) -> None:
    with connect() as c:
        c.execute(
            "INSERT INTO generator_stats (ts, generator, model, proposed, parsed, compiled, "
            "refused, duplicate) VALUES (?,?,?,?,?,?,?,?)",
            (_now(), kw.get("generator", ""), kw.get("model", ""),
             int(kw.get("proposed", 0)), int(kw.get("parsed", 0)), int(kw.get("compiled", 0)),
             int(kw.get("refused", 0)), int(kw.get("duplicate", 0))))


def record_data_need(need: Any, sources: list[str] | None = None) -> None:
    with connect() as c:
        c.execute(
            "INSERT INTO data_needs (ts, observable, mechanisms_blocked, hypotheses_blocked, "
            "value, candidate_sources) VALUES (?,?,?,?,?,?)",
            (_now(), need.observable, json.dumps(sorted(set(need.mechanisms_blocked))),
             int(need.hypotheses_blocked), float(need.value), json.dumps(sources or [])))


# ---------------------------------------------------------------------------------------------
# THE QUERIES THAT DECIDE WHERE THE NEXT TRIAL GOES. Each one is a join no JSON file can answer.
# ---------------------------------------------------------------------------------------------

def mechanism_policy() -> list[dict[str, Any]]:
    """Per mechanism: what was actually learned, separated by WHY it failed.

    The column that matters is `genuine_refutations` -- failures the desk is ENTITLED to hold
    against the mechanism. A mechanism with fifty failures and zero genuine refutations has not
    been tested; it has been mismeasured fifty times, and defunding it would be the single
    costliest mistake the allocator can make.
    """
    with connect() as c:
        rows = c.execute("""
            SELECT mechanism,
                   COUNT(*)                                            AS failures,
                   SUM(CASE WHEN state='MECHANISM_REFUTED'
                             AND updates_posterior=1 THEN 1 ELSE 0 END) AS genuine_refutations,
                   SUM(CASE WHEN state='MEASUREMENT_FAILED' THEN 1 ELSE 0 END) AS measurement,
                   SUM(CASE WHEN state='DATA_UNAVAILABLE'  THEN 1 ELSE 0 END) AS no_data,
                   SUM(CASE WHEN state='COST_FAILED'       THEN 1 ELSE 0 END) AS cost,
                   SUM(CASE WHEN state='REDUNDANT'         THEN 1 ELSE 0 END) AS redundant
            FROM failures GROUP BY mechanism ORDER BY failures DESC
        """).fetchall()
    return [dict(r) for r in rows]


def blocking_observables() -> list[dict[str, Any]]:
    """Observables blocking the most mechanisms -- the acquisition queue, ranked."""
    with connect() as c:
        rows = c.execute("""
            SELECT missing_observable                       AS observable,
                   COUNT(DISTINCT mechanism)                AS mechanisms_blocked,
                   COUNT(*)                                 AS hypotheses_blocked
            FROM failures
            WHERE state='DATA_UNAVAILABLE' AND missing_observable != ''
            GROUP BY missing_observable
            ORDER BY mechanisms_blocked DESC, hypotheses_blocked DESC
        """).fetchall()
    return [dict(r) for r in rows]


def generator_yield() -> list[dict[str, Any]]:
    """Which generator produces candidates that survive intake, versus pretty duplicates."""
    with connect() as c:
        rows = c.execute("""
            SELECT generator,
                   SUM(proposed)  AS proposed,
                   SUM(parsed)    AS parsed,
                   SUM(compiled)  AS compiled,
                   SUM(refused)   AS refused,
                   SUM(duplicate) AS duplicate,
                   ROUND(CAST(SUM(compiled) AS REAL) /
                         NULLIF(SUM(proposed), 0), 4) AS compile_rate
            FROM generator_stats GROUP BY generator ORDER BY compile_rate DESC
        """).fetchall()
    return [dict(r) for r in rows]


def coordinate_history(coordinate: str) -> list[dict[str, Any]]:
    """Everything this desk has already tried at one coordinate. Prevents silent re-mining."""
    with connect() as c:
        rows = c.execute("""
            SELECT e.ts, e.mechanism, e.symbol, e.n_trades, e.exp_r_net, e.stage, e.passed
            FROM experiments e WHERE e.coordinate = ? ORDER BY e.ts DESC LIMIT 50
        """, (coordinate,)).fetchall()
    return [dict(r) for r in rows]


def summary() -> dict[str, Any]:
    with connect() as c:
        out: dict[str, Any] = {}
        # Table names cannot be parameterised in SQL, so they are validated against a fixed
        # tuple rather than interpolated from anything a caller supplies. The literal is the
        # allowlist; nothing reaches the query string that is not in it.
        for t in ("hypotheses", "measurements", "experiments", "failures",
                  "generator_stats", "data_needs"):
            if t not in _TABLES:
                continue
            out[t] = c.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]  # noqa: S608
    return out
