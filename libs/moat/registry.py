"""THE CANONICAL RESEARCH REGISTRY -- data/alpha_registry.sqlite, the one store every miner writes.

THE FINDING THAT ORDERED THIS (principal, 2026-09-17). The replicated moat snapshot held 8 alpha
cards and 1,344 alpha events and ZERO rows in research_memory, research_candidates,
research_runs, trials_ledger, workers, campaigns, candidate_returns and metric_points: the
registry preserved knowledge and no organ wrote to its research chain. Measured today the file
is not even on the trading box -- only the backup copy exists -- and data/research_os.sqlite's
six tables are all empty too. The desk's actual research record lives in JSONL and JSON
artifacts that nothing joins. The order: ONE canonical registry, not another parallel database:
alpha_cards -> alpha_events -> research_memory -> research_candidates -> research_runs ->
trials_ledger -> the gauntlet, with workers, campaigns, candidate_returns and metric_points
populated by the organs that do the work.

WHAT THIS MODULE IS. (1) The registry's SCHEMA as the replicated file holds it (CANON), so the
restored file keeps its rows and migrations, plus the EXTENSIONS the moat factory needs (the
principal's candidate record, the memory kinds, the worker beats), applied as ADD COLUMN --
never a drop, never a rewrite. (2) A single connection door that restores the file from the
moat backup when it is absent, evolves the schema, and installs the CONSTITUTION as triggers:
trials_ledger, alpha_events, audit_log, candidate_returns and provenance accept no UPDATE and
no DELETE (complete trial accounting and provenance are not knobs). (3) Writers for every table
in the chain, a content-hash dedupe on candidates (candidate quantity has zero intrinsic value:
the same rule twice is one candidate with search_count 2), the candidate SCORE
V = P(edge) x Novelty x Independence x DataQuality x MechanismStrength x Capacity
x InformationGain / ResearchCost x (1 + bonus for an EMPTY cell of the breadth grid
Asset x Mechanism x Actor x Information x Chart x Session x Horizon x Regime), and a
hash-chained trials ledger. (4) The DISCOVERY OBJECT and its state machine (UNPROCESSED ->
INTERPRETED -> EXPANDED -> COMPILED -> QUEUED -> TESTED, or BLOCKED(reason)): no miner row,
finding, failure, lead, artifact, residual or mechanism exists here without a disposition, and
conversion_debt() is the ledger that says how many economically valid cells each discovery
still owes. (5) The PROVENANCE DAG: Source -> Discovery -> Mechanism -> Cell -> Trial -> Verdict
as immutable typed edges, so a survivor can be traced to the miner that found it and a miner
can be paid by the independent survivors it produced. (6) sync_from_desk: the bridge that
pours the desk's existing record into the chain incrementally -- hypothesis_graph rows become
candidates, gate verdicts become trials and candidate verdicts, compute-ledger runs become
research_runs, sleeves and certified cells become cards with events on every status change,
lessons become research_memory, department locks become workers. Everything the desk already
writes now lands in one queryable place; every new miner writes here directly.

The eight crypto-era cards the backup carries are RETIRED on restore with an event that names
the universe mandate (2026-08-18); their events stay, because events are immutable.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import sqlite3
import uuid
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
_PATH: Path = ROOT / "data" / "alpha_registry.sqlite"
BACKUP: Path = ROOT / "backups" / "moat" / "alpha_registry"
DESK = ROOT / "desks" / "mt5"

#: The tables as the replicated registry holds them (column order preserved).
CANON: dict[str, str] = {
    "alpha_cards": "id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, name TEXT, market TEXT,"
                   " category TEXT, thesis TEXT, entry_logic TEXT, exit_logic TEXT,"
                   " expected_cagr REAL, expected_sharpe REAL, expected_drawdown REAL, dsr REAL,"
                   " pbo REAL, cpcv_json TEXT, walk_forward_json TEXT, holdout_json TEXT,"
                   " deployment_date TEXT, retirement_date TEXT, live_cagr REAL, live_sharpe REAL,"
                   " live_drawdown REAL, decay_score REAL, status TEXT, successor_id TEXT,"
                   " predecessor_id TEXT, extra_json TEXT",
    "alpha_events": "seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT, alpha_id TEXT,"
                    " created_at TEXT, event_type TEXT, from_status TEXT, to_status TEXT,"
                    " detail_json TEXT, actor TEXT",
    "alpha_performance": "seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT, alpha_id TEXT,"
                         " created_at TEXT, sharpe REAL, cagr REAL, max_drawdown REAL,"
                         " win_rate REAL, profit_factor REAL, expectancy REAL, sample INTEGER,"
                         " detail_json TEXT",
    "alpha_registry": "id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, name TEXT,"
                      " instruments_json TEXT, status TEXT, card_json TEXT, owner TEXT,"
                      " deploy_date TEXT, retire_date TEXT",
    "audit_log": "seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT, created_at TEXT,"
                 " decision_type TEXT, actor TEXT, inputs_json TEXT, rationale TEXT, outcome TEXT,"
                 " prev_hash TEXT, row_hash TEXT",
    "campaigns": "seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE, content_hash TEXT,"
                 " spec_json TEXT, priority INTEGER, status TEXT, worker_id TEXT,"
                 " lease_expires_at TEXT, attempts INTEGER, max_attempts INTEGER, created_at TEXT,"
                 " updated_at TEXT, started_at TEXT, finished_at TEXT, error TEXT,"
                 " result_json TEXT",
    "candidate_returns": "seq INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id TEXT, kind TEXT,"
                         " epoch_key TEXT, n_obs INTEGER, dtype TEXT, timeframe TEXT,"
                         " checksum TEXT, series_blob BLOB, recorded_at TEXT",
    "metric_points": "seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT, created_at TEXT, name TEXT,"
                     " value REAL, tags_json TEXT",
    "research_candidates": "seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE, created_at TEXT,"
                           " campaign_id TEXT, family TEXT, subtype TEXT, symbol TEXT,"
                           " params_json TEXT, content_hash TEXT, status TEXT, mechanism TEXT,"
                           " annual_sharpe REAL, dsr REAL, pbo REAL, reality_p REAL,"
                           " oos_sharpe REAL, capacity_usd REAL, fragility REAL, survived INTEGER,"
                           " rejection_reason TEXT, updated_at TEXT",
    "research_memory": "id TEXT PRIMARY KEY, created_at TEXT, category TEXT, statement TEXT,"
                       " result TEXT, failure_cause TEXT, failure_reason TEXT, success_reason TEXT,"
                       " failure_stage TEXT, lessons TEXT, metrics_json TEXT, predecessor_id TEXT",
    "research_runs": "id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, hypothesis_id TEXT,"
                     " name TEXT, git_commit TEXT, snapshot_id TEXT, config_hash TEXT,"
                     " seed INTEGER,"
                     " status TEXT, metrics_json TEXT",
    "trials_ledger": "seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT, created_at TEXT,"
                     " hypothesis_id TEXT, family TEXT, method TEXT, params_json TEXT,"
                     " data_snapshot TEXT, in_sample_metric REAL, git_commit TEXT, prev_hash TEXT,"
                     " row_hash TEXT",
    "workers": "worker_id TEXT PRIMARY KEY, pid INTEGER, host TEXT, status TEXT,"
               " current_campaign TEXT, started_at TEXT, last_seen TEXT, campaigns_done INTEGER",
    "schema_migrations": "version INTEGER PRIMARY KEY, name TEXT, sha256 TEXT, applied_at TEXT",
}

#: The moat factory's columns, added to the canonical tables (ADD COLUMN, never a rewrite).
EXTENSIONS: dict[str, tuple[tuple[str, str], ...]] = {
    "research_candidates": (
        ("origin", "TEXT"), ("parent_ids_json", "TEXT"), ("economic_actor", "TEXT"),
        ("constraint_text", "TEXT"), ("causal_rationale", "TEXT"), ("asset_class", "TEXT"),
        ("chart", "TEXT"), ("session", "TEXT"), ("horizon", "TEXT"), ("regime", "TEXT"),
        ("exact_rules", "TEXT"), ("required_data_json", "TEXT"), ("pit_status", "TEXT"),
        ("expected_costs", "REAL"), ("expected_capacity", "REAL"), ("novelty_vs_live", "REAL"),
        ("novelty_vs_graveyard", "REAL"), ("expected_return_independence", "REAL"),
        ("falsifier", "TEXT"), ("trial_family", "TEXT"), ("search_count", "INTEGER"),
        ("p_edge", "REAL"), ("data_quality", "REAL"), ("mechanism_strength", "REAL"),
        ("research_cost", "REAL"), ("expected_info_gain", "REAL"), ("score", "REAL"),
        ("grid_cell", "TEXT"), ("empty_axis_bonus", "REAL"), ("department", "TEXT"),
        ("generator", "TEXT"), ("source_id", "TEXT"), ("discovery_id", "TEXT"),
        ("transformation", "TEXT"), ("information", "TEXT"), ("claimed_by", "TEXT"),
        ("claimed_at", "TEXT"), ("donated_cell", "TEXT"), ("judged_at", "TEXT"),
        ("terminal_gate", "TEXT"), ("failure_class", "TEXT"), ("lineage_json", "TEXT"),
    ),
    "research_memory": (("kind", "TEXT"), ("memory_key", "TEXT"), ("payload_json", "TEXT"),
                        ("evidence_json", "TEXT"), ("updated_at", "TEXT")),
    "workers": (("kind", "TEXT"), ("beat", "TEXT"), ("department", "TEXT"),
                ("generator", "TEXT")),
    "research_runs": (("organ", "TEXT"), ("department", "TEXT"), ("started_at", "TEXT"),
                      ("finished_at", "TEXT"), ("compute_s", "REAL"), ("outcome", "TEXT"),
                      ("inputs_json", "TEXT"), ("outputs_json", "TEXT")),
    "trials_ledger": (("candidate_id", "TEXT"), ("terminal_gate", "TEXT"), ("passed", "INTEGER"),
                      ("verdict_json", "TEXT"), ("symbol", "TEXT")),
    "alpha_cards": (("desk_ref", "TEXT"), ("lane", "TEXT"), ("symbol", "TEXT"),
                    ("family", "TEXT"), ("params_json", "TEXT"), ("chart", "TEXT"),
                    ("mechanism", "TEXT")),
}

#: New tables the intelligence side keeps in the SAME file (one registry, no parallel database).
MOAT_TABLES: dict[str, str] = {
    "discoveries": "discovery_id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT,"
                   " source_id TEXT, source_type TEXT, parent_ids_json TEXT, actor TEXT,"
                   " constraint_text TEXT, mechanism TEXT, information TEXT,"
                   " economic_rationale TEXT, assets_json TEXT, horizons_json TEXT,"
                   " sessions_json TEXT, regimes_json TEXT, exact_rule TEXT,"
                   " required_data_json TEXT, pit_requirements_json TEXT, novelty REAL,"
                   " confidence REAL, falsifier TEXT, state TEXT, blocked_reason TEXT,"
                   " mechanism_id TEXT, origin TEXT, generator TEXT, content_hash TEXT,"
                   " possible_cells INTEGER, generated_cells INTEGER, compiled_cells INTEGER,"
                   " queued_cells INTEGER, tested_cells INTEGER, blocked_cells INTEGER,"
                   " payload_json TEXT",
    "provenance": "seq INTEGER PRIMARY KEY AUTOINCREMENT, from_kind TEXT, from_id TEXT,"
                  " to_kind TEXT, to_id TEXT, relation TEXT, created_at TEXT,"
                  " UNIQUE(from_kind, from_id, to_kind, to_id, relation)",
    "sources": "source_id TEXT PRIMARY KEY, url TEXT, kind TEXT, language TEXT, country TEXT,"
               " asset_classes_json TEXT, discovered_from TEXT, discovered_via TEXT,"
               " first_seen TEXT, last_crawled TEXT, status TEXT, licence_note TEXT,"
               " meta_json TEXT",
    "source_yield": "source_id TEXT PRIMARY KEY, leads INTEGER, claims INTEGER,"
                    " mechanisms INTEGER, candidates INTEGER, donated INTEGER, judged INTEGER,"
                    " survivors INTEGER, independent_survivors INTEGER, compute_s REAL,"
                    " updated_at TEXT",
    "mechanisms": "mechanism_id TEXT PRIMARY KEY, created_at TEXT, actor TEXT, constraint_text"
                  " TEXT, counterparty TEXT, mechanism TEXT, why_edge_can_persist TEXT,"
                  " asset_mapping_json TEXT, horizon TEXT, session TEXT, required_data_json TEXT,"
                  " pit_status TEXT, expected_cost REAL, falsifier TEXT, source_id TEXT,"
                  " language TEXT, quality REAL, novelty REAL, structured_complete INTEGER,"
                  " first_claim_id TEXT, genealogy_json TEXT",
    "claims": "claim_id TEXT PRIMARY KEY, created_at TEXT, doc_id TEXT, source_id TEXT,"
              " text TEXT, language TEXT, knowable_at TEXT, mechanism_id TEXT,"
              " instruments_json TEXT, kind TEXT, media_type TEXT, provenance_json TEXT",
    "claim_edges": "seq INTEGER PRIMARY KEY AUTOINCREMENT, from_claim TEXT, to_claim TEXT,"
                   " relation TEXT, created_at TEXT, UNIQUE(from_claim, to_claim, relation)",
    "frontier_map": "cell TEXT PRIMARY KEY, language TEXT, country TEXT, source_type TEXT,"
                    " asset_class TEXT, mechanism_class TEXT, n_sources INTEGER, n_leads INTEGER,"
                    " n_distinct INTEGER, n_singletons INTEGER, n_doubletons INTEGER,"
                    " chao1_unseen REAL, last_scouted TEXT, cold INTEGER, updated_at TEXT",
    "generator_yield": "generator TEXT PRIMARY KEY, generated INTEGER, donated INTEGER,"
                       " judged INTEGER, survivors INTEGER, independent_survivors INTEGER,"
                       " delta_n_eff REAL, delta_elogw REAL, compute_s REAL, updated_at TEXT",
    "kpis": "day TEXT, name TEXT, value REAL, detail_json TEXT, updated_at TEXT,"
            " PRIMARY KEY(day, name)",
    "sync_cursor": "key TEXT PRIMARY KEY, value TEXT, updated_at TEXT",
}

IMMUTABLE_TABLES: tuple[str, ...] = ("trials_ledger", "alpha_events", "audit_log",
                                     "candidate_returns", "provenance")
CANDIDATE_FIELDS: tuple[str, ...] = (
    "candidate_id", "parent_ids", "origin", "mechanism", "economic_actor", "constraint",
    "causal_rationale", "symbol", "asset_class", "chart", "session", "horizon", "regime",
    "exact_rules", "parameters", "required_data", "pit_status", "expected_costs",
    "expected_capacity", "novelty_vs_live", "novelty_vs_graveyard",
    "expected_return_independence", "falsifier", "trial_family", "search_count",
)
DISCOVERY_FIELDS: tuple[str, ...] = (
    "discovery_id", "source_id", "source_type", "parent_discovery_ids", "actor", "constraint",
    "mechanism", "information", "economic_rationale", "assets", "horizons", "sessions",
    "regimes", "exact_rule_if_known", "required_data", "PIT_requirements", "novelty",
    "confidence", "falsifier",
)
DISCOVERY_STATES: tuple[str, ...] = ("UNPROCESSED", "INTERPRETED", "EXPANDED", "COMPILED",
                                     "QUEUED", "TESTED", "BLOCKED")
FAILURE_CLASSES: tuple[str, ...] = ("no_edge", "cost_killed", "regime_specific",
                                    "wrong_direction", "wrong_horizon", "wrong_asset",
                                    "redundant", "unstable", "execution_killed", "forward_decay")
GRID_AXES: tuple[str, ...] = ("asset_class", "mechanism", "economic_actor", "information",
                              "chart", "session", "horizon", "regime")
PROVENANCE_KINDS: tuple[str, ...] = ("source", "discovery", "mechanism", "cell", "trial",
                                     "verdict", "card", "miner", "transformation")
CRYPTO_MARKETS: tuple[str, ...] = ("BINANCE", "BYBIT", "OKX", "HYPERLIQUID", "DERIBIT", "KRAKEN")
EMPTY_CELL_BONUS = 0.5
PRIOR = 0.5


def now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def set_path(p: Path | None) -> Path:
    """Point the registry at another file (tests); None restores the canonical path."""
    global _PATH
    _PATH = Path(p) if p is not None else ROOT / "data" / "alpha_registry.sqlite"
    return _PATH


def path() -> Path:
    return _PATH


def _sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def _j(obj: Any) -> str | None:
    return None if obj is None else json.dumps(obj, sort_keys=True, default=str)


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [str(r[1]) for r in conn.execute(f'PRAGMA table_info("{table}")')]


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {str(r[0]) for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _evolve(conn: sqlite3.Connection) -> dict[str, int]:
    """Create what is missing, add what is missing, never drop or rewrite."""
    added = {"tables": 0, "columns": 0}
    have = _tables(conn)
    for table, ddl in list(CANON.items()) + list(MOAT_TABLES.items()):
        if table not in have:
            conn.execute(f'CREATE TABLE "{table}" ({ddl})')
            added["tables"] += 1
    for table, cols in EXTENSIONS.items():
        present = set(_columns(conn, table))
        for col, typ in cols:
            if col not in present:
                conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{col}" {typ}')
                added["columns"] += 1
    for table in IMMUTABLE_TABLES:
        for op in ("UPDATE", "DELETE"):
            conn.execute(
                f'CREATE TRIGGER IF NOT EXISTS "constitution_{table}_{op.lower()}" BEFORE {op} '
                f'ON "{table}" BEGIN SELECT RAISE(ABORT, "{table} is immutable: the '
                f'constitution keeps complete trial accounting"); END')
    conn.execute("CREATE INDEX IF NOT EXISTS ix_candidates_status ON research_candidates(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_candidates_hash ON research_candidates"
                 "(content_hash)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_candidates_disc ON research_candidates"
                 "(discovery_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_events_alpha ON alpha_events(alpha_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_trials_hyp ON trials_ledger(hypothesis_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_disc_state ON discoveries(state)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_prov_from ON provenance(from_kind, from_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_prov_to ON provenance(to_kind, to_id)")
    return added


def _restore_if_absent() -> bool:
    if _PATH.exists():
        return False
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    if BACKUP.exists() and BACKUP.stat().st_size > 0:
        shutil.copyfile(BACKUP, _PATH)
        return True
    return False


def connect() -> sqlite3.Connection:
    """The one door: restore from the moat backup when absent, evolve, install the constitution."""
    restored = _restore_if_absent()
    conn = sqlite3.connect(str(_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    _evolve(conn)
    conn.commit()
    if restored:
        _retire_crypto_cards(conn)
        conn.execute("INSERT OR REPLACE INTO sync_cursor(key, value, updated_at) VALUES(?,?,?)",
                     ("restored_from_backup", str(BACKUP), now()))
        conn.commit()
    return conn


def _retire_crypto_cards(conn: sqlite3.Connection) -> int:
    n = 0
    for row in conn.execute("SELECT id, name, market, status FROM alpha_cards").fetchall():
        market = str(row["market"] or "").upper()
        name = str(row["name"] or "")
        if row["status"] != "retired" and (name.startswith("crypto::")
                                           or any(m in market for m in CRYPTO_MARKETS)):
            _event(conn, str(row["id"]), "retire", str(row["status"] or ""), "retired",
                   {"why": "MT5 universe mandate 2026-08-18: crypto-exchange ground is never "
                           "hunted again; the card stays as history"}, "moat.registry")
            conn.execute("UPDATE alpha_cards SET status='retired', retirement_date=?, "
                         "updated_at=? WHERE id=?", (now(), now(), row["id"]))
            n += 1
    conn.commit()
    return n


def counts(conn: sqlite3.Connection | None = None) -> dict[str, int]:
    """The snapshot the principal quoted: rows per table."""
    c = conn or connect()
    try:
        out: dict[str, int] = {}
        for t in sorted(_tables(c)):
            if t.startswith("sqlite_"):
                continue
            out[t] = int(c.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0])  # noqa: S608
        return out
    finally:
        if conn is None:
            c.close()


def _rows(cur: sqlite3.Cursor) -> list[dict[str, Any]]:
    return [dict(r) for r in cur.fetchall()]


# --------------------------------------------------------------------------- cards and events
def _event(conn: sqlite3.Connection, alpha_id: str, event_type: str, from_status: str | None,
           to_status: str | None, detail: Any, actor: str) -> str:
    eid = new_id("aev")
    conn.execute("INSERT INTO alpha_events(id, alpha_id, created_at, event_type, from_status, "
                 "to_status, detail_json, actor) VALUES(?,?,?,?,?,?,?,?)",
                 (eid, alpha_id, now(), event_type, from_status, to_status, _j(detail), actor))
    return eid


def record_event(alpha_id: str, event_type: str, *, from_status: str | None = None,
                 to_status: str | None = None, detail: Any = None, actor: str = "moat",
                 conn: sqlite3.Connection | None = None) -> str:
    c = conn or connect()
    try:
        eid = _event(c, alpha_id, event_type, from_status, to_status, detail, actor)
        c.commit()
        return eid
    finally:
        if conn is None:
            c.close()


def upsert_card(card_id: str, *, name: str, market: str, category: str, thesis: str = "",
                status: str = "candidate", actor: str = "moat", entry_logic: str = "",
                exit_logic: str = "", extra: Mapping[str, Any] | None = None,
                conn: sqlite3.Connection | None = None, **cols: Any) -> bool:
    """Create or update a card; every creation and status change is an immutable event."""
    c = conn or connect()
    try:
        row = c.execute("SELECT status FROM alpha_cards WHERE id=?", (card_id,)).fetchone()
        allowed = set(_columns(c, "alpha_cards"))
        extra_cols = {k: (_j(v) if k.endswith("_json") and not isinstance(v, str) else v)
                      for k, v in cols.items() if k in allowed}
        changed = False
        if row is None:
            fields = {"id": card_id, "created_at": now(), "updated_at": now(), "name": name,
                      "market": market, "category": category, "thesis": thesis,
                      "entry_logic": entry_logic, "exit_logic": exit_logic, "status": status,
                      "extra_json": _j(dict(extra or {})), **extra_cols}
            keys = list(fields)
            c.execute(f'INSERT INTO alpha_cards({",".join(keys)}) '
                      f'VALUES({",".join("?" * len(keys))})', [fields[k] for k in keys])
            _event(c, card_id, "creation", None, status, {"name": name, "market": market}, actor)
            changed = True
        else:
            old = str(row["status"] or "")
            sets = {"updated_at": now(), "name": name, "market": market, "category": category,
                    "status": status, **extra_cols}
            if thesis:
                sets["thesis"] = thesis
            if extra is not None:
                sets["extra_json"] = _j(dict(extra))
            c.execute("UPDATE alpha_cards SET " + ", ".join(f"{k}=?" for k in sets)  # noqa: S608
                      + " WHERE id=?", [*sets.values(), card_id])
            if old != status:
                _event(c, card_id, "status", old, status, {"name": name}, actor)
                changed = True
        c.commit()
        return changed
    finally:
        if conn is None:
            c.close()


def cards(status: str | None = None, conn: sqlite3.Connection | None = None
          ) -> list[dict[str, Any]]:
    c = conn or connect()
    try:
        if status is None:
            return _rows(c.execute("SELECT * FROM alpha_cards ORDER BY created_at"))
        return _rows(c.execute("SELECT * FROM alpha_cards WHERE status=? ORDER BY created_at",
                               (status,)))
    finally:
        if conn is None:
            c.close()


def events(alpha_id: str | None = None, limit: int = 1000,
           conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    c = conn or connect()
    try:
        if alpha_id is None:
            return _rows(c.execute("SELECT * FROM alpha_events ORDER BY seq DESC LIMIT ?",
                                   (limit,)))
        return _rows(c.execute("SELECT * FROM alpha_events WHERE alpha_id=? ORDER BY seq LIMIT ?",
                               (alpha_id, limit)))
    finally:
        if conn is None:
            c.close()


# --------------------------------------------------------------------------- candidates
def content_hash(family: str, symbol: str, params: Mapping[str, Any] | None, chart: str = "",
                 session: str = "", regime: str = "", horizon: str = "") -> str:
    return _sha({"family": family, "symbol": symbol, "params": dict(params or {}),
                 "chart": chart, "session": session, "regime": regime, "horizon": horizon})[:32]


def grid_cell(c: Mapping[str, Any]) -> str:
    """Where a candidate sits in Asset x Mechanism x Actor x Information x Chart x Session x
    Horizon x Regime; an unknown axis value is the literal 'unknown', never a blank."""
    return "|".join(str(c.get(a) or "unknown").lower() for a in GRID_AXES)


def _f(c: Mapping[str, Any], key: str, default: float) -> float:
    v = c.get(key)
    try:
        return default if v is None else float(v)
    except (TypeError, ValueError):
        return default


def score_candidate(c: Mapping[str, Any], cell_empty: bool) -> float:
    """V = P(edge) x Novelty x Independence x DataQuality x MechanismStrength x Capacity
    x InformationGain / ResearchCost x (1 + EMPTY_CELL_BONUS when the breadth cell is empty).
    Unmeasured factors take the PRIOR (0.5), never 1.0: an unmeasured candidate cannot outrank
    a measured one by absence. This is the READY_PRIORITY order; READY_ALL is every queued row."""
    novelty = min(_f(c, "novelty_vs_live", PRIOR), _f(c, "novelty_vs_graveyard", PRIOR))
    v = (_f(c, "p_edge", PRIOR) * novelty * _f(c, "expected_return_independence", PRIOR)
         * _f(c, "data_quality", PRIOR) * _f(c, "mechanism_strength", PRIOR)
         * min(1.0, _f(c, "expected_capacity", PRIOR)) * _f(c, "expected_info_gain", PRIOR))
    cost = max(_f(c, "research_cost", 1.0), 1e-3)
    return float(v / cost * (1.0 + (EMPTY_CELL_BONUS if cell_empty else 0.0)))


_FIELD_TO_COLUMN: dict[str, str] = {
    "parent_ids": "parent_ids_json", "parameters": "params_json",
    "required_data": "required_data_json", "constraint": "constraint_text",
    "lineage": "lineage_json",
}


def enqueue_candidate(*, family: str, symbol: str, params: Mapping[str, Any] | None,
                      origin: str, mechanism: str = "", candidate_id: str | None = None,
                      status: str = "queued", conn: sqlite3.Connection | None = None,
                      **fields: Any) -> tuple[str, bool]:
    """Write a candidate once. The same rule (family, symbol, params, chart, session, regime,
    horizon) enqueued again is NOT a second candidate: search_count rises and the existing id
    returns. Returns (id, created)."""
    c = conn or connect()
    try:
        h = content_hash(family, symbol, params, str(fields.get("chart") or ""),
                         str(fields.get("session") or ""), str(fields.get("regime") or ""),
                         str(fields.get("horizon") or ""))
        row = c.execute("SELECT id, search_count FROM research_candidates WHERE content_hash=?",
                        (h,)).fetchone()
        if row is not None:
            c.execute("UPDATE research_candidates SET search_count=?, updated_at=? WHERE id=?",
                      (int(row["search_count"] or 1) + 1, now(), row["id"]))
            if candidate_id and candidate_id != str(row["id"]):
                # The same rule reached the registry under a second name (a donation first, the
                # graph's cell id later): keep ONE candidate and remember the alias, so trials
                # and verdicts keyed by the cell id land on it.
                c.execute("UPDATE research_candidates SET donated_cell=COALESCE(donated_cell, ?) "
                          "WHERE id=?", (candidate_id, row["id"]))
            c.commit()
            return str(row["id"]), False
        cid = candidate_id or new_id("cand")
        cell = grid_cell({**fields, "mechanism": mechanism, "symbol": symbol})
        empty = c.execute("SELECT 1 FROM research_candidates WHERE grid_cell=? LIMIT 1",
                          (cell,)).fetchone() is None
        rec: dict[str, Any] = {
            "id": cid, "created_at": now(), "updated_at": now(), "family": family,
            "symbol": symbol, "params_json": _j(dict(params or {})), "content_hash": h,
            "status": status, "mechanism": mechanism, "origin": origin, "grid_cell": cell,
            "empty_axis_bonus": EMPTY_CELL_BONUS if empty else 0.0, "search_count": 1,
        }
        allowed = set(_columns(c, "research_candidates"))
        for k, v in fields.items():
            col = _FIELD_TO_COLUMN.get(k, k)
            if col in allowed and col not in rec:
                rec[col] = _j(v) if col.endswith("_json") and not isinstance(v, str) else v
        rec["score"] = score_candidate({**fields, "mechanism": mechanism}, empty)
        keys = list(rec)
        c.execute(f'INSERT INTO research_candidates({",".join(keys)}) '
                  f'VALUES({",".join("?" * len(keys))})', [rec[k] for k in keys])
        if fields.get("discovery_id"):
            _link(c, "discovery", str(fields["discovery_id"]), "cell", cid,
                  str(fields.get("transformation") or "compiled"))
        c.commit()
        return cid, True
    finally:
        if conn is None:
            c.close()


def claim_candidates(department: str, n: int, origin: str | None = None,
                     conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    """A department bids compute: the best-scored queued candidates become its claims."""
    c = conn or connect()
    try:
        q = "SELECT * FROM research_candidates WHERE status='queued'"
        args: list[Any] = []
        if origin:
            q += " AND origin=?"
            args.append(origin)
        q += " ORDER BY score DESC, created_at LIMIT ?"
        args.append(n)
        rows = _rows(c.execute(q, args))
        for r in rows:
            c.execute("UPDATE research_candidates SET status='claimed', claimed_by=?, claimed_at=?,"
                      " updated_at=? WHERE id=?", (department, now(), now(), r["id"]))
        c.commit()
        return rows
    finally:
        if conn is None:
            c.close()


def mark_candidate(candidate_id: str, status: str, conn: sqlite3.Connection | None = None,
                   **updates: Any) -> bool:
    c = conn or connect()
    try:
        allowed = set(_columns(c, "research_candidates"))
        sets: dict[str, Any] = {"status": status, "updated_at": now()}
        for k, v in updates.items():
            if k in allowed:
                sets[k] = _j(v) if k.endswith("_json") and not isinstance(v, str) else v
        cur = c.execute("UPDATE research_candidates SET "  # noqa: S608
                        + ", ".join(f"{k}=?" for k in sets) + " WHERE id=? OR donated_cell=?",
                        [*sets.values(), candidate_id, candidate_id])
        c.commit()
        return cur.rowcount > 0
    finally:
        if conn is None:
            c.close()


def candidates(status: str | None = None, origin: str | None = None, limit: int = 500,
               conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    c = conn or connect()
    try:
        q = "SELECT * FROM research_candidates WHERE 1=1"
        args: list[Any] = []
        if status:
            q += " AND status=?"
            args.append(status)
        if origin:
            q += " AND origin=?"
            args.append(origin)
        q += " ORDER BY score DESC, created_at DESC LIMIT ?"
        args.append(limit)
        return _rows(c.execute(q, args))
    finally:
        if conn is None:
            c.close()


def queue_depth(conn: sqlite3.Connection | None = None) -> dict[str, dict[str, int]]:
    c = conn or connect()
    try:
        out: dict[str, dict[str, int]] = {}
        for r in c.execute("SELECT origin, status, COUNT(*) AS n FROM research_candidates "
                           "GROUP BY origin, status"):
            out.setdefault(str(r["origin"] or "unknown"), {})[str(r["status"])] = int(r["n"])
        return out
    finally:
        if conn is None:
            c.close()


def grid_coverage(conn: sqlite3.Connection | None = None) -> dict[str, int]:
    c = conn or connect()
    try:
        return {str(r["grid_cell"]): int(r["n"]) for r in c.execute(
            "SELECT grid_cell, COUNT(*) AS n FROM research_candidates GROUP BY grid_cell")}
    finally:
        if conn is None:
            c.close()


# --------------------------------------------------------------------------- discoveries
def record_discovery(*, source_id: str, source_type: str, mechanism: str, origin: str,
                     generator: str = "", discovery_id: str | None = None,
                     conn: sqlite3.Connection | None = None, **fields: Any) -> tuple[str, bool]:
    """Every miner row becomes ONE DiscoveryObject in state UNPROCESSED; the same discovery
    (source, mechanism, assets, exact rule) recorded again returns the existing id."""
    c = conn or connect()
    try:
        h = _sha({"source_id": source_id, "mechanism": mechanism,
                  "assets": fields.get("assets"), "rule": fields.get("exact_rule_if_known")
                  or fields.get("exact_rule")})[:32]
        row = c.execute("SELECT discovery_id FROM discoveries WHERE content_hash=?",
                        (h,)).fetchone()
        if row is not None:
            return str(row["discovery_id"]), False
        did = discovery_id or new_id("disc")
        rec: dict[str, Any] = {
            "discovery_id": did, "created_at": now(), "updated_at": now(),
            "source_id": source_id, "source_type": source_type, "mechanism": mechanism,
            "origin": origin, "generator": generator, "state": "UNPROCESSED",
            "content_hash": h, "possible_cells": 0, "generated_cells": 0, "compiled_cells": 0,
            "queued_cells": 0, "tested_cells": 0, "blocked_cells": 0,
        }
        allowed = set(_columns(c, "discoveries"))
        alias = {"parent_discovery_ids": "parent_ids_json", "parent_ids": "parent_ids_json",
                 "constraint": "constraint_text", "assets": "assets_json",
                 "horizons": "horizons_json", "sessions": "sessions_json",
                 "regimes": "regimes_json", "exact_rule_if_known": "exact_rule",
                 "required_data": "required_data_json",
                 "PIT_requirements": "pit_requirements_json",
                 "pit_requirements": "pit_requirements_json", "payload": "payload_json"}
        for k, v in fields.items():
            col = alias.get(k, k)
            if col in allowed and col not in rec:
                rec[col] = _j(v) if col.endswith("_json") and not isinstance(v, str) else v
        keys = list(rec)
        c.execute(f'INSERT INTO discoveries({",".join(keys)}) '
                  f'VALUES({",".join("?" * len(keys))})', [rec[k] for k in keys])
        _link(c, "source", source_id, "discovery", did, "produced")
        for pid in fields.get("parent_discovery_ids") or fields.get("parent_ids") or []:
            _link(c, "discovery", str(pid), "discovery", did, "derived")
        c.commit()
        return did, True
    finally:
        if conn is None:
            c.close()


def set_discovery_state(discovery_id: str, state: str, *, reason: str | None = None,
                        mechanism_id: str | None = None, conn: sqlite3.Connection | None = None,
                        **counters: int) -> bool:
    """Move a discovery along UNPROCESSED -> INTERPRETED -> EXPANDED -> COMPILED -> QUEUED ->
    TESTED, or park it as BLOCKED(reason); counters are the conversion-debt cell counts."""
    if state not in DISCOVERY_STATES:
        raise ValueError(f"unknown discovery state {state!r}")
    if state == "BLOCKED" and not reason:
        raise ValueError("BLOCKED requires a reason; silence is not a disposition")
    c = conn or connect()
    try:
        sets: dict[str, Any] = {"state": state, "updated_at": now()}
        if reason is not None:
            sets["blocked_reason"] = reason
        if mechanism_id is not None:
            sets["mechanism_id"] = mechanism_id
            _link(c, "discovery", discovery_id, "mechanism", mechanism_id, "interpreted")
        for k in ("possible_cells", "generated_cells", "compiled_cells", "queued_cells",
                  "tested_cells", "blocked_cells"):
            if k in counters:
                sets[k] = int(counters[k])
        cur = c.execute("UPDATE discoveries SET " + ", ".join(f"{k}=?" for k in sets)  # noqa: S608
                        + " WHERE discovery_id=?", [*sets.values(), discovery_id])
        c.commit()
        return cur.rowcount > 0
    finally:
        if conn is None:
            c.close()


def discoveries(state: str | None = None, origin: str | None = None, limit: int = 500,
                conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    c = conn or connect()
    try:
        q = "SELECT * FROM discoveries WHERE 1=1"
        args: list[Any] = []
        if state:
            q += " AND state=?"
            args.append(state)
        if origin:
            q += " AND origin=?"
            args.append(origin)
        q += " ORDER BY created_at LIMIT ?"
        args.append(limit)
        return _rows(c.execute(q, args))
    finally:
        if conn is None:
            c.close()


def conversion_debt(conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """The CONVERSION_DEBT ledger: cells owed by every discovery. Coverage = (compiled +
    blocked with a reason) / possible; unexplained_missing = possible - generated - blocked,
    the number that must go to zero."""
    c = conn or connect()
    try:
        by_state = {str(r["state"]): int(r["n"]) for r in c.execute(
            "SELECT state, COUNT(*) AS n FROM discoveries GROUP BY state")}
        tot = c.execute("SELECT COALESCE(SUM(possible_cells),0) p, COALESCE(SUM(generated_cells),0)"
                        " g, COALESCE(SUM(compiled_cells),0) c, COALESCE(SUM(queued_cells),0) q,"
                        " COALESCE(SUM(tested_cells),0) t, COALESCE(SUM(blocked_cells),0) b "
                        "FROM discoveries").fetchone()
        possible, generated, compiled = int(tot["p"]), int(tot["g"]), int(tot["c"])
        queued, tested, blocked = int(tot["q"]), int(tot["t"]), int(tot["b"])
        n_disc = sum(by_state.values())
        unexplained = max(0, possible - generated - blocked)
        coverage = None if possible == 0 else min(1.0, (compiled + blocked) / possible)
        silent = int(by_state.get("UNPROCESSED", 0))
        return {"n_discoveries": n_disc, "by_state": by_state, "possible_cells": possible,
                "generated_cells": generated, "compiled_cells": compiled, "queued_cells": queued,
                "tested_cells": tested, "blocked_cells": blocked,
                "unexplained_missing_cells": unexplained, "conversion_coverage": coverage,
                "unprocessed_discoveries": silent,
                "rule": "no discovery exists without a disposition; unexplained conversion debt"
                        " must go to zero, not every cell must be tested today"}
    finally:
        if conn is None:
            c.close()


# --------------------------------------------------------------------------- provenance
def _link(c: sqlite3.Connection, from_kind: str, from_id: str, to_kind: str, to_id: str,
          relation: str) -> None:
    if from_kind not in PROVENANCE_KINDS or to_kind not in PROVENANCE_KINDS:
        raise ValueError(f"unknown provenance kind {from_kind!r}/{to_kind!r}")
    c.execute("INSERT OR IGNORE INTO provenance(from_kind, from_id, to_kind, to_id, relation, "
              "created_at) VALUES(?,?,?,?,?,?)", (from_kind, from_id, to_kind, to_id, relation,
                                                  now()))


def link(from_kind: str, from_id: str, to_kind: str, to_id: str, relation: str,
         conn: sqlite3.Connection | None = None) -> None:
    """One immutable edge of the DAG Source -> Discovery -> Mechanism -> Cell -> Trial ->
    Verdict."""
    c = conn or connect()
    try:
        _link(c, from_kind, from_id, to_kind, to_id, relation)
        c.commit()
    finally:
        if conn is None:
            c.close()


def provenance_of(kind: str, node_id: str, *, depth: int = 8,
                  conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    """Every ancestor edge of a node, walking backwards: which verdict came from which trial,
    cell, mechanism, discovery, source and miner."""
    c = conn or connect()
    try:
        out: list[dict[str, Any]] = []
        frontier = [(kind, node_id)]
        seen: set[tuple[str, str]] = set()
        for _ in range(depth):
            nxt: list[tuple[str, str]] = []
            for k, i in frontier:
                if (k, i) in seen:
                    continue
                seen.add((k, i))
                for r in _rows(c.execute("SELECT * FROM provenance WHERE to_kind=? AND to_id=?",
                                         (k, i))):
                    out.append(r)
                    nxt.append((str(r["from_kind"]), str(r["from_id"])))
            if not nxt:
                break
            frontier = nxt
        return out
    finally:
        if conn is None:
            c.close()


def descendants_of(kind: str, node_id: str, *, depth: int = 8,
                   conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    c = conn or connect()
    try:
        out: list[dict[str, Any]] = []
        frontier = [(kind, node_id)]
        seen: set[tuple[str, str]] = set()
        for _ in range(depth):
            nxt: list[tuple[str, str]] = []
            for k, i in frontier:
                if (k, i) in seen:
                    continue
                seen.add((k, i))
                for r in _rows(c.execute("SELECT * FROM provenance WHERE from_kind=? AND from_id=?",
                                         (k, i))):
                    out.append(r)
                    nxt.append((str(r["to_kind"]), str(r["to_id"])))
            if not nxt:
                break
            frontier = nxt
        return out
    finally:
        if conn is None:
            c.close()


# --------------------------------------------------------------------------- memory
def remember(category: str, statement: str, *, kind: str = "note", memory_key: str | None = None,
             result: str | None = None, failure_cause: str | None = None,
             failure_stage: str | None = None, lessons: str | None = None,
             metrics: Mapping[str, Any] | None = None, predecessor_id: str | None = None,
             payload: Any = None, evidence: Any = None,
             conn: sqlite3.Connection | None = None) -> str:
    """Research memory: a lesson, a failure cluster, a counter-hypothesis, a replication. A
    memory_key makes the write an upsert (the cluster's row is refreshed, not duplicated)."""
    c = conn or connect()
    try:
        if memory_key is not None:
            row = c.execute("SELECT id FROM research_memory WHERE memory_key=?",
                            (memory_key,)).fetchone()
            if row is not None:
                c.execute("UPDATE research_memory SET statement=?, result=?, failure_cause=?, "
                          "failure_stage=?, lessons=?, metrics_json=?, payload_json=?, "
                          "evidence_json=?, updated_at=? WHERE id=?",
                          (statement, result, failure_cause, failure_stage, lessons, _j(metrics),
                           _j(payload), _j(evidence), now(), row["id"]))
                c.commit()
                return str(row["id"])
        mid = new_id("mem")
        c.execute("INSERT INTO research_memory(id, created_at, category, statement, result, "
                  "failure_cause, failure_stage, lessons, metrics_json, predecessor_id, kind, "
                  "memory_key, payload_json, evidence_json, updated_at) "
                  "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (mid, now(), category, statement, result, failure_cause, failure_stage, lessons,
                   _j(metrics), predecessor_id, kind, memory_key, _j(payload), _j(evidence), now()))
        c.commit()
        return mid
    finally:
        if conn is None:
            c.close()


def memories(category: str | None = None, kind: str | None = None, limit: int = 500,
             conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    c = conn or connect()
    try:
        q = "SELECT * FROM research_memory WHERE 1=1"
        args: list[Any] = []
        if category:
            q += " AND category=?"
            args.append(category)
        if kind:
            q += " AND kind=?"
            args.append(kind)
        q += " ORDER BY updated_at DESC LIMIT ?"
        args.append(limit)
        return _rows(c.execute(q, args))
    finally:
        if conn is None:
            c.close()


# --------------------------------------------------------------------------- runs, trials, workers
def record_run(run_id: str, *, name: str, status: str, hypothesis_id: str = "",
               git_commit: str = "", config_hash: str = "", seed: int | None = None,
               metrics: Mapping[str, Any] | None = None, organ: str = "", department: str = "",
               started_at: str | None = None, finished_at: str | None = None,
               compute_s: float | None = None, outcome: str | None = None, inputs: Any = None,
               outputs: Any = None, conn: sqlite3.Connection | None = None) -> None:
    c = conn or connect()
    try:
        c.execute("INSERT INTO research_runs(id, created_at, updated_at, hypothesis_id, name, "
                  "git_commit, config_hash, seed, status, metrics_json, organ, department, "
                  "started_at, finished_at, compute_s, outcome, inputs_json, outputs_json) "
                  "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                  "updated_at=excluded.updated_at, status=excluded.status, "
                  "metrics_json=excluded.metrics_json, finished_at=excluded.finished_at, "
                  "compute_s=excluded.compute_s, outcome=excluded.outcome, "
                  "outputs_json=excluded.outputs_json",
                  (run_id, now(), now(), hypothesis_id, name, git_commit, config_hash, seed, status,
                   _j(metrics), organ, department, started_at, finished_at, compute_s, outcome,
                   _j(inputs), _j(outputs)))
        c.commit()
    finally:
        if conn is None:
            c.close()


def record_trial(hypothesis_id: str, *, family: str, method: str, params: Mapping[str, Any] | None,
                 data_snapshot: str = "", in_sample_metric: float | None = None,
                 git_commit: str = "", candidate_id: str | None = None,
                 terminal_gate: str | None = None, passed: bool | None = None, verdict: Any = None,
                 symbol: str | None = None, conn: sqlite3.Connection | None = None) -> str:
    """One row per trial, hash-chained: prev_hash is the last row's hash, row_hash covers the
    row's content and prev_hash. The trigger refuses any later edit. The cell -> trial ->
    verdict edges of the provenance DAG are written here."""
    c = conn or connect()
    try:
        last = c.execute("SELECT row_hash FROM trials_ledger ORDER BY seq DESC LIMIT 1").fetchone()
        prev = str(last["row_hash"]) if last is not None and last["row_hash"] else ""
        body = {"hypothesis_id": hypothesis_id, "family": family, "method": method,
                "params": dict(params or {}), "data_snapshot": data_snapshot,
                "in_sample_metric": in_sample_metric, "git_commit": git_commit,
                "candidate_id": candidate_id, "terminal_gate": terminal_gate, "passed": passed,
                "verdict": verdict, "symbol": symbol, "prev_hash": prev}
        rh = _sha(body)
        tid = new_id("trial")
        c.execute("INSERT INTO trials_ledger(id, created_at, hypothesis_id, family, method, "
                  "params_json, data_snapshot, in_sample_metric, git_commit, prev_hash, row_hash, "
                  "candidate_id, terminal_gate, passed, verdict_json, symbol) "
                  "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (tid, now(), hypothesis_id, family, method, _j(dict(params or {})),
                   data_snapshot, in_sample_metric, git_commit, prev, rh, candidate_id,
                   terminal_gate, None if passed is None else int(passed), _j(verdict), symbol))
        _link(c, "cell", candidate_id or hypothesis_id, "trial", tid, method)
        if passed is not None:
            _link(c, "trial", tid, "verdict", f"{tid}:{'pass' if passed else 'fail'}",
                  str(terminal_gate or "terminal"))
        c.commit()
        return rh
    finally:
        if conn is None:
            c.close()


def verify_trial_chain(conn: sqlite3.Connection | None = None) -> tuple[bool, int]:
    c = conn or connect()
    try:
        prev, n = "", 0
        for r in c.execute("SELECT * FROM trials_ledger ORDER BY seq"):
            if str(r["prev_hash"] or "") != prev:
                return False, n
            prev = str(r["row_hash"])
            n += 1
        return True, n
    finally:
        if conn is None:
            c.close()


def worker_heartbeat(worker_id: str, *, kind: str, beat: str = "", department: str = "",
                     status: str = "running", pid: int | None = None, host: str | None = None,
                     current_campaign: str | None = None, generator: str = "",
                     last_seen: str | None = None, campaigns_done_inc: int = 0,
                     conn: sqlite3.Connection | None = None) -> None:
    c = conn or connect()
    try:
        seen = last_seen or now()
        row = c.execute("SELECT campaigns_done, started_at FROM workers WHERE worker_id=?",
                        (worker_id,)).fetchone()
        done = (int(row["campaigns_done"] or 0) if row is not None else 0) + campaigns_done_inc
        started = str(row["started_at"]) if row is not None and row["started_at"] else seen
        c.execute("INSERT INTO workers(worker_id, pid, host, status, current_campaign, started_at, "
                  "last_seen, campaigns_done, kind, beat, department, generator) "
                  "VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(worker_id) DO UPDATE SET "
                  "pid=excluded.pid,"
                  " host=excluded.host, status=excluded.status, "
                  "current_campaign=excluded.current_campaign, last_seen=excluded.last_seen, "
                  "campaigns_done=excluded.campaigns_done, kind=excluded.kind, beat=excluded.beat, "
                  "department=excluded.department, generator=excluded.generator",
                  (worker_id, pid if pid is not None else os.getpid(), host or socket.gethostname(),
                   status, current_campaign, started, seen, done, kind, beat, department,
                   generator))
        c.commit()
    finally:
        if conn is None:
            c.close()


def workers_alive(stale_s: float = 900.0, conn: sqlite3.Connection | None = None
                  ) -> list[dict[str, Any]]:
    c = conn or connect()
    try:
        out = []
        for r in _rows(c.execute("SELECT * FROM workers")):
            try:
                age = (datetime.now(tz=UTC) - datetime.fromisoformat(str(r["last_seen"]))
                       ).total_seconds()
            except ValueError:
                continue
            if age <= stale_s and str(r["status"]) == "running":
                out.append({**r, "age_s": round(age, 1)})
        return out
    finally:
        if conn is None:
            c.close()


def campaign_upsert(campaign_id: str, *, spec: Mapping[str, Any], priority: int = 0,
                    status: str = "queued", worker_id: str | None = None, result: Any = None,
                    error: str | None = None, conn: sqlite3.Connection | None = None) -> None:
    c = conn or connect()
    try:
        c.execute("INSERT INTO campaigns(id, content_hash, spec_json, priority, status, worker_id, "
                  "attempts, max_attempts, created_at, updated_at, error, result_json) "
                  "VALUES(?,?,?,?,?,?,0,3,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                  "status=excluded.status,"
                  " worker_id=excluded.worker_id, updated_at=excluded.updated_at, "
                  "error=excluded.error, result_json=excluded.result_json, "
                  "attempts=campaigns.attempts+1",
                  (campaign_id, _sha(dict(spec))[:32], _j(dict(spec)), priority, status, worker_id,
                   now(), now(), error, _j(result)))
        c.commit()
    finally:
        if conn is None:
            c.close()


def metric(name: str, value: float, tags: Mapping[str, Any] | None = None,
           conn: sqlite3.Connection | None = None) -> None:
    c = conn or connect()
    try:
        c.execute("INSERT INTO metric_points(id, created_at, name, value, tags_json) "
                  "VALUES(?,?,?,?,?)", (new_id("mp"), now(), name, float(value), _j(tags)))
        c.commit()
    finally:
        if conn is None:
            c.close()


def record_candidate_returns(candidate_id: str, kind: str, epoch_key: str,
                             series: Sequence[float] | np.ndarray, timeframe: str = "",
                             conn: sqlite3.Connection | None = None) -> str:
    arr = np.asarray(series, dtype=np.float32)
    blob = arr.tobytes()
    ck = hashlib.sha256(blob).hexdigest()[:32]
    c = conn or connect()
    try:
        c.execute("INSERT INTO candidate_returns(candidate_id, kind, epoch_key, n_obs, dtype, "
                  "timeframe, checksum, series_blob, recorded_at) VALUES(?,?,?,?,?,?,?,?,?)",
                  (candidate_id, kind, epoch_key, int(arr.size), "float32", timeframe, ck, blob,
                   now()))
        c.commit()
        return ck
    finally:
        if conn is None:
            c.close()


def candidate_returns(candidate_id: str, conn: sqlite3.Connection | None = None
                      ) -> list[tuple[str, str, np.ndarray]]:
    c = conn or connect()
    try:
        out = []
        for r in c.execute("SELECT kind, epoch_key, series_blob FROM candidate_returns "
                           "WHERE candidate_id=? ORDER BY seq", (candidate_id,)):
            out.append((str(r["kind"]), str(r["epoch_key"]),
                        np.frombuffer(r["series_blob"], dtype=np.float32)))
        return out
    finally:
        if conn is None:
            c.close()


def kpi(day: str, name: str, value: float | None, detail: Any = None,
        conn: sqlite3.Connection | None = None) -> None:
    c = conn or connect()
    try:
        c.execute("INSERT INTO kpis(day, name, value, detail_json, updated_at) VALUES(?,?,?,?,?) "
                  "ON CONFLICT(day, name) DO UPDATE SET value=excluded.value, "
                  "detail_json=excluded.detail_json, updated_at=excluded.updated_at",
                  (day, name, value, _j(detail), now()))
        c.commit()
    finally:
        if conn is None:
            c.close()


def kpis(days: int = 30, conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    c = conn or connect()
    try:
        return _rows(c.execute("SELECT * FROM kpis ORDER BY day DESC, name LIMIT ?", (days * 40,)))
    finally:
        if conn is None:
            c.close()


def generator_yield_update(generator: str, *, conn: sqlite3.Connection | None = None,
                           **inc: float) -> None:
    """Additive counters per generator (generated, donated, judged, survivors,
    independent_survivors, compute_s) and absolute delta_n_eff / delta_elogw."""
    c = conn or connect()
    try:
        row = c.execute("SELECT * FROM generator_yield WHERE generator=?", (generator,)).fetchone()
        cur = dict(row) if row is not None else {}
        vals: dict[str, float] = {}
        for k in ("generated", "donated", "judged", "survivors", "independent_survivors",
                  "compute_s"):
            vals[k] = float(cur.get(k) or 0) + float(inc.get(k, 0.0))
        for k in ("delta_n_eff", "delta_elogw"):
            vals[k] = float(inc[k]) if k in inc else float(cur.get(k) or 0.0)
        c.execute("INSERT OR REPLACE INTO generator_yield(generator, generated, donated, judged, "
                  "survivors, independent_survivors, delta_n_eff, delta_elogw, compute_s, "
                  "updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (generator, int(vals["generated"]), int(vals["donated"]), int(vals["judged"]),
                   int(vals["survivors"]), int(vals["independent_survivors"]), vals["delta_n_eff"],
                   vals["delta_elogw"], vals["compute_s"], now()))
        c.commit()
    finally:
        if conn is None:
            c.close()


def generator_yields(conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    """Yield_g = independent survivors / generated, with delta n_eff and delta E[log W]: the
    downstream value a miner is paid by, never its candidate count."""
    c = conn or connect()
    try:
        out = []
        for r in _rows(c.execute("SELECT * FROM generator_yield ORDER BY generator")):
            gen = int(r.get("generated") or 0)
            r["yield"] = None if gen == 0 else float(r.get("independent_survivors") or 0) / gen
            out.append(r)
        return out
    finally:
        if conn is None:
            c.close()


# --------------------------------------------------------------------------- the desk bridge
def _cursor_get(c: sqlite3.Connection, key: str) -> int:
    r = c.execute("SELECT value FROM sync_cursor WHERE key=?", (key,)).fetchone()
    return int(r["value"]) if r is not None else 0


def _cursor_set(c: sqlite3.Connection, key: str, value: int) -> None:
    c.execute("INSERT OR REPLACE INTO sync_cursor(key, value, updated_at) VALUES(?,?,?)",
              (key, str(value), now()))


def _new_lines(c: sqlite3.Connection, key: str, p: Path, max_rows: int
               ) -> tuple[list[dict[str, Any]], int]:
    """JSONL rows after the byte cursor, at most max_rows; returns rows and the new offset."""
    if not p.exists():
        return [], 0
    start = _cursor_get(c, key)
    size = p.stat().st_size
    if start > size:
        start = 0
    rows: list[dict[str, Any]] = []
    with p.open("rb") as f:
        f.seek(start)
        pos = start
        for raw in f:
            if len(rows) >= max_rows:
                break
            pos += len(raw)
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    return rows, pos


MOAT_SOURCES: tuple[str, ...] = ("moat", "card_explosion", "lineage", "resurrect", "graveyard",
                                 "shadow_ledger", "execution_tape", "forward_result",
                                 "recombination", "unused_information", "descendants",
                                 "trajectory_evolution", "transformation")
EXTERNAL_SOURCES: tuple[str, ...] = ("miner", "seat", "kimi", "deepseek", "frontier", "forest",
                                     "story", "scout", "analyst", "world", "intel", "lead")


def origin_of(source: str) -> str:
    s = (source or "").lower()
    if any(s.startswith(k) or f":{k}" in s for k in MOAT_SOURCES):
        return "MOAT"
    if any(k in s for k in EXTERNAL_SOURCES):
        return "EXTERNAL"
    return "DESK"


def _status_of_fate(fate: Any) -> str:
    f = str(fate or "").lower()
    if not f or f in ("born", "pending", "queued", "donated"):
        return "donated"
    if f in ("certified", "survived", "promoted", "live"):
        return "survived"
    return "judged"


def sync_from_desk(desk: Path | None = None, *, max_rows: int = 20000,
                   lessons: Path | None = None, conn: sqlite3.Connection | None = None
                   ) -> dict[str, int]:
    """Pour the desk's existing record into the chain, incrementally and idempotently."""
    d = desk or DESK
    c = conn or connect()
    out = {"candidates": 0, "trials": 0, "runs": 0, "cards": 0, "events": 0, "memories": 0,
           "workers": 0}
    try:
        rows, pos = _new_lines(c, "hypothesis_graph", d / "data" / "hypothesis_graph.jsonl",
                               max_rows)
        for r in rows:
            cid = str(r.get("id") or "")
            if not cid:
                continue
            src = str(r.get("source") or "")
            _, created = enqueue_candidate(
                family=str(r.get("family") or ""), symbol=str(r.get("symbol") or ""),
                params=r.get("params") if isinstance(r.get("params"), dict) else {},
                origin=origin_of(src), mechanism=str(r.get("why") or "")[:200], candidate_id=cid,
                status=_status_of_fate(r.get("fate")), generator=src,
                parent_ids=[r["parent"]] if r.get("parent") else [], conn=c)
            out["candidates"] += int(created)
        _cursor_set(c, "hypothesis_graph", pos)

        rows, pos = _new_lines(c, "gate_verdicts",
                               d / "data" / "hypotheses" / "gate_verdict_ledger.jsonl", max_rows)
        for r in rows:
            cell = str(r.get("cell") or "")
            if not cell:
                continue
            passed = r.get("passed")
            record_trial(cell, family=str(r.get("family") or ""), method="gauntlet", params=None,
                         terminal_gate=str(r.get("terminal_gate") or ""),
                         passed=None if passed is None else bool(passed),
                         verdict={"downstream_status": r.get("downstream_status"),
                                  "at": r.get("at")},
                         symbol=str(r.get("sym") or ""), candidate_id=cell, conn=c)
            out["trials"] += 1
            mark_candidate(cell, "survived" if passed else "judged",
                           judged_at=str(r.get("at") or now()),
                           terminal_gate=str(r.get("terminal_gate") or ""),
                           survived=1 if passed else 0, conn=c)
        _cursor_set(c, "gate_verdicts", pos)

        rows, pos = _new_lines(c, "compute_ledger", d / "data" / "compute_ledger.jsonl", max_rows)
        for r in rows:
            kind = str(r.get("kind") or "")
            run = str(r.get("run") or "")
            at = str(r.get("at") or "")
            if not kind or not at:
                continue
            record_run(f"{kind}:{run}:{at}", name=kind, status=str(r.get("outcome") or "unknown"),
                       organ=kind, outcome=str(r.get("outcome") or ""), finished_at=at,
                       compute_s=float(r.get("wall_s") or 0.0),
                       git_commit=str(r.get("commit_sha") or ""),
                       config_hash=str(r.get("config_hash") or ""),
                       metrics={k: r[k] for k in ("cpu_s", "wall_s", "input_hash", "output_hash")
                                if k in r}, conn=c)
            out["runs"] += 1
        _cursor_set(c, "compute_ledger", pos)

        sl = d / "data" / "sleeves.json"
        if sl.exists():
            try:
                doc = json.loads(sl.read_text(encoding="utf-8-sig"))
                srows = doc.get("sleeves") if isinstance(doc, dict) else doc
                items: Iterable[Any] = (srows.values() if isinstance(srows, dict) else srows or [])
                for s in items:
                    if not isinstance(s, dict) or not s.get("name"):
                        continue
                    params = {k: s.get(k) for k in ("stop_atr", "target_atr", "max_hold", "lot",
                                                    "risk_frac") if k in s}
                    changed = upsert_card(
                        f"sleeve:{s['name']}", name=str(s["name"]),
                        market=str(s.get("symbol") or ""),
                        category="sleeve", thesis=str(s.get("family") or ""),
                        status=str(s.get("status") or "").lower() or "unknown",
                        actor="moat.registry.sync", desk_ref=str(s["name"]), lane="live",
                        symbol=str(s.get("symbol") or ""), family=str(s.get("family") or ""),
                        params_json=params, chart=str(s.get("timeframe") or ""), conn=c)
                    out["cards"] += 1
                    out["events"] += int(changed)
            except (OSError, ValueError):
                pass
        us = d / "reports" / "UNIVERSAL_SURVIVORS.json"
        if us.exists():
            try:
                doc = json.loads(us.read_text(encoding="utf-8-sig"))
                sv = doc.get("survivors") if isinstance(doc, dict) else None
                items = sv.values() if isinstance(sv, dict) else (sv or [])
                for s in items:
                    if not isinstance(s, dict) or not s.get("cell"):
                        continue
                    raw_spec = s.get("shadow_spec")
                    spec: dict[str, Any] = raw_spec if isinstance(raw_spec, dict) else {}
                    changed = upsert_card(
                        f"cell:{s['cell']}", name=str(s["cell"]), market=str(s.get("sym") or ""),
                        category="certified_cell", thesis=str(spec.get("family") or ""),
                        status=str(s.get("status") or "certified").lower(),
                        actor="moat.registry.sync", desk_ref=str(s["cell"]), lane="forward",
                        symbol=str(s.get("sym") or ""), family=str(spec.get("family") or ""),
                        params_json=spec.get("params") or {}, chart=str(spec.get("chart") or ""),
                        conn=c)
                    out["cards"] += 1
                    out["events"] += int(changed)
            except (OSError, ValueError):
                pass
        lp = lessons or (ROOT / "docs" / "desk_lessons.jsonl")
        rows, pos = _new_lines(c, "desk_lessons", lp, max_rows)
        for r in rows:
            if not r.get("id") or not r.get("lesson"):
                continue
            remember("lesson", str(r["lesson"]), kind="lesson", memory_key=f"lesson:{r['id']}",
                     evidence=r.get("evidence"), lessons=str(r.get("cost") or ""),
                     payload={"tags": r.get("tags"), "source": r.get("source"),
                              "learned": r.get("learned")}, conn=c)
            out["memories"] += 1
        _cursor_set(c, "desk_lessons", pos)
        locks = d / "data" / "locks"
        if locks.exists():
            for lk in locks.glob("dept_*.lock"):
                try:
                    text = lk.read_text(encoding="utf-8", errors="replace").split()
                    pid = int(text[0]) if text and text[0].isdigit() else None
                    seen = datetime.fromtimestamp(lk.stat().st_mtime, tz=UTC).isoformat(
                        timespec="seconds")
                except (OSError, ValueError):
                    continue
                worker_heartbeat(f"dept:{lk.stem[5:]}", kind="department_resident",
                                 department=lk.stem[5:], pid=pid, last_seen=seen, conn=c)
                out["workers"] += 1
        c.commit()
        return out
    finally:
        if conn is None:
            c.close()


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="the canonical research registry")
    ap.add_argument("--sync", action="store_true", help="pour the desk's record into the chain")
    ap.add_argument("--counts", action="store_true")
    ap.add_argument("--verify", action="store_true", help="verify the trials hash chain")
    ap.add_argument("--debt", action="store_true", help="print the conversion-debt ledger")
    a = ap.parse_args(argv)
    if a.sync:
        print(json.dumps({"synced": sync_from_desk()}, indent=1))
    if a.verify:
        ok, n = verify_trial_chain()
        print(json.dumps({"trial_chain_ok": ok, "n": n}))
    if a.debt:
        print(json.dumps(conversion_debt(), indent=1))
    if a.counts or not (a.sync or a.verify or a.debt):
        print(json.dumps(counts(), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
