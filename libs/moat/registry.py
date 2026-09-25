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

import contextlib
import hashlib
import json
import os
import re
import shutil
import socket
import sqlite3
import sys
import time
import uuid
from collections.abc import Iterable, Iterator, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from libs.research import attribution as _attr

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
        # THE CAUSAL ADJUDICATOR'S VERDICT (LAWS 5m; event_graph_lab): SUPPORTED / REFUTED /
        # UNIDENTIFIABLE / UNMEASURED with the failing rung named. Recorded, never a status
        # change: the ten gates keep their authority (L1.60). `causal_eligible` is the LAWS 5k
        # contract -- a falsifier and competing explanations declared -- as 0/1.
        ("causal_verdict", "TEXT"), ("causal_failing_test", "TEXT"), ("causal_effect", "REAL"),
        ("causal_judged_at", "TEXT"), ("causal_eligible", "INTEGER"),
        # THE UNIVERSALCELL'S SIMULATOR FIELDS (LAWS 5m / RESEARCH.md): the simulator family
        # and the posterior-world robustness `research/digital_twin.py` writes -- the share
        # of calibrated posterior worlds in which the candidate's rule stays positive, NULL
        # (UNMEASURED) when the twin failed its predictive checks. ADD COLUMN, never a rewrite.
        ("simulator_family", "TEXT"), ("posterior_world_robustness", "REAL"),
        # THE INDEPENDENT REPLICATION CIVILIZATION'S VERDICT (replication_civilization):
        # REPLICATED / MISMATCH / UNMEASURED and, on a mismatch, the divergence it quarantined on.
        ("replication_verdict", "TEXT"), ("replication_mismatch_json", "TEXT"),
        ("replication_judged_at", "TEXT"),
        # THE RESEARCH GENOME (LAWS 5k; research/science_controller.py): C = (M, D, R, G, S,
        # H, E, F) stamped from the row's own columns, the near-duplicate family it belongs
        # to, and the science controller's launch state (OPEN | BLOCKED:<reason>). ADD COLUMN.
        ("genome_json", "TEXT"), ("family_id", "TEXT"), ("science_state", "TEXT"),
        # THE COUNTEREXAMPLE AGENT'S VERDICT (Tier-1 W6; research/counterexample_agent.py):
        # ALL_SURVIVED / BROKEN / UNMEASURED and, when broken, which of the five attacks did it
        # (placebo symbol, placebo date, sign flip, neighbouring parameter, excluded window).
        # RECORDED, NEVER A STATUS CHANGE and never a veto -- the ten gates keep their authority
        # (L1.60). ALL_SURVIVED is the POSITIVE signal the queue prioritises on. ADD COLUMN.
        ("counterexample_verdict", "TEXT"), ("counterexample_broken_by", "TEXT"),
        ("counterexample_judged_at", "TEXT"),
        # ATTRIBUTION AT BIRTH (libs/research/attribution.py, 2026-09-23). WHO produced the cell
        # and from WHICH regional ground, stamped by `enqueue_candidate` through the one helper
        # rather than re-derived by each reader. Measured that day: 3,663 of 3,862 unique cells
        # were attributed to nobody and the regional scoreboard read `Europe: 1,973 sources, 0
        # cells` -- not because Europe produced nothing but because its cells could not be traced
        # back. `attribution_route` records HOW each was reached, so a number can be checked.
        ("producer", "TEXT"), ("region", "TEXT"), ("attribution_route", "TEXT"),
    ),
    #: The same three on the discovery, which is where a cell's regional ground is still visible:
    #: the compiler that turns a discovery into candidates writes its OWN generator, so a cell
    #: joined only to the compiler credits one pass-through with the whole desk's output.
    "discoveries": (("producer", "TEXT"), ("region", "TEXT"), ("attribution_route", "TEXT")),
    "research_memory": (("kind", "TEXT"), ("memory_key", "TEXT"), ("payload_json", "TEXT"),
                        ("evidence_json", "TEXT"), ("updated_at", "TEXT")),
    "workers": (("kind", "TEXT"), ("beat", "TEXT"), ("department", "TEXT"),
                ("generator", "TEXT")),
    #: THE FEATURE GENOME (LAWS 5m): a typed or minted representation carries its genome, the
    #: DatasetContract its data origin is held under, and the lineage hash its data version
    #: replays from. Written by research/feature_compiler.py through representation_upsert.
    "representations": (("genome_json", "TEXT"), ("contract_id", "TEXT"),
                        ("lineage_hash", "TEXT")),
    "research_runs": (("organ", "TEXT"), ("department", "TEXT"), ("started_at", "TEXT"),
                      ("finished_at", "TEXT"), ("compute_s", "REAL"), ("outcome", "TEXT"),
                      ("inputs_json", "TEXT"), ("outputs_json", "TEXT")),
    "trials_ledger": (("candidate_id", "TEXT"), ("terminal_gate", "TEXT"), ("passed", "INTEGER"),
                      ("verdict_json", "TEXT"), ("symbol", "TEXT")),
    "alpha_cards": (("desk_ref", "TEXT"), ("lane", "TEXT"), ("symbol", "TEXT"),
                    ("family", "TEXT"), ("params_json", "TEXT"), ("chart", "TEXT"),
                    ("mechanism", "TEXT")),
    # THE ACCESS ROUTING LAW (LAWS 5e, rewritten 2026-09-23): three INDEPENDENT dimensions on
    # every source -- access label, credibility, predictive state -- written by
    # research/evidence_router.py through libs/research/access_classifier.py. The labels ROUTE
    # REDISTRIBUTION and WEIGHT; they never stop a source being mined or tested. `quarantine` is
    # now 0 on every row: the ACCESS_UNCLEAR quarantine was deleted and the column is kept only
    # so old readers find a 0 rather than a missing field. Only a refused label (PRIVATE,
    # CONFIDENTIAL_MNPI, STOLEN_UNAUTHORIZED -- the five acts) withholds use, with its reason in
    # `route_reason`. ADD COLUMN, never a rewrite.
    "sources": (("access_label", "TEXT"), ("credibility", "TEXT"),
                ("predictive_state", "TEXT"), ("quarantine", "INTEGER"),
                ("routed_at", "TEXT"), ("route_reason", "TEXT")),
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
    #: THE REPRESENTATION FORGE'S LEDGER (principal 2026-09-17: "representation invention mints
    #: new features from ingested series and tracks their ROI"). A representation is neither a
    #: discovery nor a candidate -- it is the FEATURE a candidate was built out of, and until it
    #: had a row here the question "which representation earned its compute" had no place to be
    #: answered. Declared as a MOAT table rather than as columns on an existing one for the
    #: reason the others are: it is a new noun, not a new adjective on an old one.
    "representations": "representation_id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT,"
                       " dataset TEXT, transform TEXT, family TEXT, params_json TEXT,"
                       " region TEXT, information_type TEXT, n_points INTEGER,"
                       " first_available TEXT, last_available TEXT, pit_json TEXT,"
                       " novelty REAL, expected_value REAL, used_by_candidates INTEGER,"
                       " survivors INTEGER, forward_rows INTEGER, live_attribution REAL,"
                       " explained_variance REAL, compute_s REAL, origin TEXT, payload_json TEXT",
    #: THE EXPERIMENT MEMORY GRAPH (RD-Agent closure items 1/11/16, principal 2026-09-22). One
    #: canonical ExperimentSpec per research object -- factor, model, world-miner lead, physics
    #: law, macro idea, country mechanism, sandbox hypothesis -- so that "what has never been
    #: tried from this surviving mechanism?" is a QUERY rather than a memory. It is a node table
    #: only: the edges are `provenance` (kind `experiment`), the verdicts are `trials_ledger`
    #: and `research_candidates`, and nothing here duplicates a result another table owns.
    "experiments": "experiment_id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, kind TEXT,"
                   " spec_hash TEXT, family TEXT, symbols_json TEXT, model TEXT,"
                   " representation TEXT, features_json TEXT, target TEXT, horizon TEXT,"
                   " chart TEXT, regime TEXT, session TEXT, mechanism TEXT, mechanism_id TEXT,"
                   " method TEXT, source_id TEXT, generator TEXT, origin TEXT,"
                   " discovery_id TEXT, candidate_id TEXT, parents_json TEXT,"
                   " snapshot_hash TEXT, snapshot_vintage TEXT, pit_status TEXT,"
                   " falsifier TEXT, trial_family TEXT, costs_json TEXT, novelty_json TEXT,"
                   " status TEXT, verdict TEXT, verdict_at TEXT, failed_assumptions_json TEXT,"
                   " forward_r REAL, live_delta_elogw REAL, compute_s REAL, spec_json TEXT",
    #: THE RESEARCH CREDIT LEDGER (item 5): one row per ANCESTOR (source, miner, method,
    #: representation, model, family, region), carrying what its descendants actually earned --
    #: survivors, independent survivors, forward R and live dE[log W] -- so the desk learns
    #: which miners, operators, representations and models create valid alpha rather than rows.
    "research_credit": "ancestor_kind TEXT, ancestor_id TEXT, experiments INTEGER,"
                       " candidates INTEGER, judged INTEGER, survivors INTEGER,"
                       " independent_survivors REAL, forward_r REAL, forward_n INTEGER,"
                       " live_delta_elogw REAL, compute_s REAL, credit REAL, basis TEXT,"
                       " updated_at TEXT, PRIMARY KEY(ancestor_kind, ancestor_id)",
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
#: `experiment` joined 2026-09-22: the canonical ExperimentSpec is a node of the DAG, sitting
#: between the discovery and the cell, so credit walks back from a live sleeve to the experiment,
#: the method that minted it and the source that suggested it without a second graph beside this.
PROVENANCE_KINDS: tuple[str, ...] = ("source", "discovery", "mechanism", "cell", "trial",
                                     "verdict", "card", "miner", "transformation", "experiment")
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


#: Column lists keyed by (connection, table, schema_version). `PRAGMA table_info` cost 0.121 ms
#: and the write door asked for it TWICE per row (measured on the box 2026-09-23: 1,200 calls =
#: 0.142 s of a 4.35 s 600-row write). The schema_version in the key is what makes the cache
#: safe: SQLite bumps it on every DDL, so an ALTER or a table rebuild in `_evolve` invalidates
#: every entry for that table by construction -- a cache that can never serve a stale column.
_COLUMNS_CACHE: dict[tuple[int, str, int], list[str]] = {}


def _schema_version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("PRAGMA schema_version").fetchone()[0])


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    key = (id(conn), table, _schema_version(conn))
    hit = _COLUMNS_CACHE.get(key)
    if hit is not None:
        return hit
    cols = [str(r[1]) for r in conn.execute(f'PRAGMA table_info("{table}")')]
    if len(_COLUMNS_CACHE) > 4096:          # never a leak across long-lived processes
        _COLUMNS_CACHE.clear()
    _COLUMNS_CACHE[key] = cols
    return cols


#: Connections inside a `batch(...)`: THE COMMIT THAT COST THE DESK ITS THROUGHPUT.
#: `proposer_common._record_in_registry` calls record_discovery + set_discovery_state +
#: enqueue_candidate per donated row, and each one committed -- three commits a row. Measured on
#: the box 2026-09-23 over 600 rows: 1,800 commits took 3.643 s of the 4.351 s total, 84% of the
#: write path, because a commit in WAL mode writes and syncs the frames for discoveries,
#: research_candidates, provenance and every index they carry. A commit per CHUNK instead of per
#: row is not a queue and not a weaker guarantee: a crash between the discovery commit and the
#: candidate commit used to leave a discovery with no cell, and now cannot.
_BATCHED: dict[int, dict[str, int]] = {}


def _begin_immediate(c: sqlite3.Connection) -> None:
    """Take the write lock UP FRONT. Python's sqlite3 opens a DEFERRED transaction on the first
    INSERT, so two producers that both read first and then write race to UPGRADE a read lock --
    and SQLite cannot make either wait for the other, so one dies instantly with `database is
    locked` no matter how long the busy timeout is. Measured on the box 2026-09-23: four
    concurrent writers on one registry file, 30 s timeout, killed in under a second. With the
    lock taken at BEGIN there is nothing to upgrade, so the busy timeout does its job and the
    loser WAITS. `_record_in_registry` swallows its exception, so every one of those deaths was
    a silently unrecorded donation, not an error anybody saw."""
    if c.in_transaction:
        return
    with contextlib.suppress(sqlite3.OperationalError):
        c.execute("BEGIN IMMEDIATE")


def _commit(c: sqlite3.Connection) -> None:
    """Commit, unless the caller opened a `batch()` -- then once per chunk, never per row."""
    st = _BATCHED.get(id(c))
    if st is None:
        c.commit()
        return
    st["n"] += 1
    if st["n"] % st["every"] == 0:
        c.commit()
        _begin_immediate(c)


@contextlib.contextmanager
def batch(conn: sqlite3.Connection, every: int = 500) -> Iterator[None]:
    """Write many rows through the registry's own doors with ONE commit per `every` writes.

    The chunk bounds how long the writer holds SQLite's write lock (at ~1,000 rows/s a 500-row
    chunk is half a second), so other producers are never shut out by one large donation. On the
    way out the remainder is committed; on an exception the incomplete chunk is rolled back, so
    no half-written row survives an abort.
    """
    key = id(conn)
    prev = _BATCHED.get(key)
    _BATCHED[key] = {"n": 0, "every": max(1, int(every))}
    _begin_immediate(conn)
    try:
        yield
        conn.commit()
        # THE WRITER PAYS ITS OWN CHECKPOINT. Raising wal_autocheckpoint defers the fsync work,
        # it does not delete it, and a deferred cost that lands on whoever happens to commit
        # next is how the live registry ended up carrying a 456 MB WAL. PASSIVE never blocks and
        # never waits on a reader, so this cannot stall the producer either.
        with contextlib.suppress(sqlite3.Error):
            conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
    except BaseException:
        conn.rollback()
        raise
    finally:
        if prev is None:
            _BATCHED.pop(key, None)
        else:
            _BATCHED[key] = prev


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {str(r[0]) for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


#: The replicated file carries the crypto-era daemon's CHECK vocabularies (research_candidates
#: status IN candidate/validation/rejected/...; research_runs status IN running/completed/failed;
#: research_memory result IN pending/success/failure; alpha_cards status IN candidate/.../retired;
#: candidate_returns kind IN net/stressed with dtype '<f8'). The moat writes the desk's own
#: vocabulary (queued/claimed/donated/judged/survived; live/standby/certified; epsilon series),
#: so every write to the restored file raised IntegrityError while every test on the CANON
#: schema passed (measured 2026-09-17: 0 of 27 priors landed). SQLite cannot ALTER a CHECK, so
#: a table whose live DDL still carries one is REBUILT once from CANON with its rows copied --
#: the rows survive, the constraint goes, and schema_migrations records the migration.
MIGRATION_VERSION = 8
MIGRATION_NAME = "moat_lift_check_vocabularies"
_CHECK_RE = re.compile(r"\bCHECK\s*\(", re.IGNORECASE)   # a real constraint, not the word checksum


def _lift_checks(conn: sqlite3.Connection) -> list[str]:
    rebuilt: list[str] = []
    for table, ddl in CANON.items():
        row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                           (table,)).fetchone()
        if row is None or not _CHECK_RE.search(str(row[0])):
            continue
        cols = _columns(conn, table)
        canon_cols = [c.split()[0] for c in ddl.split(", ")]
        keep = [c for c in cols if c in canon_cols]
        conn.execute(f'ALTER TABLE "{table}" RENAME TO "{table}__old"')
        conn.execute(f'CREATE TABLE "{table}" ({ddl})')
        if keep:
            cl = ", ".join(f'"{c}"' for c in keep)
            conn.execute(
                f'INSERT INTO "{table}" ({cl}) SELECT {cl} FROM "{table}__old"')  # noqa: S608
        conn.execute(f'DROP TABLE "{table}__old"')
        rebuilt.append(table)
    if rebuilt:
        conn.execute("INSERT OR REPLACE INTO schema_migrations(version, name, sha256, applied_at) "
                     "VALUES(?,?,?,?)", (MIGRATION_VERSION, MIGRATION_NAME,
                                         _sha(sorted(rebuilt)), now()))
    return rebuilt


def _evolve(conn: sqlite3.Connection) -> dict[str, int]:
    """Create what is missing, add what is missing, lift the crypto-era CHECKs, never lose a row."""
    added = {"tables": 0, "columns": 0, "rebuilt": 0}
    have = _tables(conn)
    for table, ddl in list(CANON.items()) + list(MOAT_TABLES.items()):
        if table not in have:
            conn.execute(f'CREATE TABLE "{table}" ({ddl})')
            added["tables"] += 1
    added["rebuilt"] = len(_lift_checks(conn))
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
    # THE INDEX THAT COST THE DESK ITS GRID (measured on the box 2026-09-23). Every
    # `enqueue_candidate` asks "is this breadth cell empty?" -- `SELECT 1 FROM research_candidates
    # WHERE grid_cell=? LIMIT 1` -- and that column had no index, so EXPLAIN read
    # `SCAN research_candidates` over 321,168 rows for every single write. One enqueue cost
    # 0.927 s of which ~0.93 s was this scan; with the index it costs 0.0012 s, a 772x fall.
    # What it bought: `independence_intake`'s grid filler has a 75 s slice of its budget, so it
    # minted EIGHT cells an hour into 8,410 reachable empty ones -- a thousand hours to fill a
    # grid it can now fill in a single ten-second pass. The lesson generalises past this organ:
    # a write door that scans the whole table on every write is a throttle on every producer
    # that uses it, and it is invisible because nothing reports it as a limit.
    conn.execute("CREATE INDEX IF NOT EXISTS ix_candidates_gridcell ON research_candidates"
                 "(grid_cell)")
    # THE SECOND SCAN, AND THE ONE THAT SET THE DESK'S WHOLE MINT RATE (measured on the box
    # 2026-09-23). `record_discovery` asks "have I seen this discovery?" -- `SELECT discovery_id
    # FROM discoveries WHERE content_hash=?` -- and `discoveries.content_hash` carried no index,
    # so EXPLAIN read `SCAN discoveries` over 78,115 rows for every donated row at 231.9 ms a
    # call. That is 4.3 rows/second, which is exactly the rate the desk measured end to end: a
    # 10,005-row donation still writing forty minutes later. With the index the same write path
    # runs at 149.6 rows/s, a 24x lift, and the lookup is a SEARCH. The pattern is now twice
    # proven on this one file: a write door that scans a table on every write is a throttle on
    # every producer behind it, and nothing reports it as a limit.
    conn.execute("CREATE INDEX IF NOT EXISTS ix_disc_hash ON discoveries(content_hash)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_events_alpha ON alpha_events(alpha_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_trials_hyp ON trials_ledger(hypothesis_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_disc_state ON discoveries(state)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_exp_mech ON experiments(mechanism_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_exp_hash ON experiments(spec_hash)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_exp_status ON experiments(status)")
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


#: Pages the WAL may hold before a committing writer stops to checkpoint. THE LAST COST IN THE
#: WRITE PATH (measured on the box 2026-09-23). Once the missing index and the per-row commits
#: were gone, a 800-row write still spent 3.70 s of 4.54 s inside FIVE commits -- 0.74 s each --
#: because SQLite's default `wal_autocheckpoint=1000` made roughly every other commit stop and
#: fsync a 707 MB database whose index pages this write had scattered dirt across. The checkpoint
#: is real work and raising this does not delete it; it BATCHES it, so the fsyncs are paid once
#: over many rows instead of once per chunk. Measured over 2,000 rows, counting the final
#: checkpoint honestly in the total: 191.8 rows/s as shipped -> 223.8 at 8,000 pages -> 345.5 at
#: 32,000. Nothing here touches `synchronous=NORMAL`: no durability is traded for it. (For the
#: record, `synchronous=OFF` measured 651 rows/s and is NOT taken -- a 3.4x that risks the
#: canonical registry on an OS crash is not a trade this desk makes.)
WAL_AUTOCHECKPOINT_PAGES = 32000


def _tuning() -> tuple[int, int]:
    """(cache KiB, mmap bytes) DERIVED from the memory this box has right now, never a constant.

    The desk has paid for a memory figure copied from the wrong machine before (CLAUDE.md keeps
    that case visible on purpose), so this measures. The floor is what an unreadable counter
    gets, and it is still far above SQLite's 2 MB default, so a box that cannot answer is slower
    than it could be and never broken."""
    free_mb = 0.0
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
        free_mb = float(psutil.virtual_memory().available) / 1048576.0
    except Exception:
        free_mb = 0.0
    # 1% of free memory per connection: many desk processes hold one at the same time.
    cache_mb = max(64.0, min(512.0, free_mb * 0.01))
    mmap_mb = max(256.0, min(8192.0, free_mb * 0.10))
    return int(cache_mb * 1024), int(mmap_mb * 1048576)


def connect() -> sqlite3.Connection:
    """The one door: restore from the moat backup when absent, evolve, install the constitution."""
    restored = _restore_if_absent()
    conn = sqlite3.connect(str(_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    cache_kib, mmap_bytes = _tuning()
    conn.execute(f"PRAGMA cache_size=-{cache_kib}")
    conn.execute(f"PRAGMA mmap_size={mmap_bytes}")
    conn.execute(f"PRAGMA wal_autocheckpoint={WAL_AUTOCHECKPOINT_PAGES}")
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
                      "market": market, "category": category, "thesis": thesis or "",
                      "entry_logic": entry_logic or "", "exit_logic": exit_logic or "",
                      "decay_score": 0.0, "status": status,
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


def _source_country(c: sqlite3.Connection, source_id: Any) -> str | None:
    """The ground a source sits on, from the registry's own `sources` table, or None."""
    if not source_id:
        return None
    try:
        row = c.execute("SELECT country FROM sources WHERE source_id=?",
                        (str(source_id),)).fetchone()
    except sqlite3.Error:
        return None
    return str(row["country"]) if row is not None and row["country"] else None


def _parent_attribution(c: sqlite3.Connection, discovery_id: Any) -> Any:
    """The attribution the discovery this row was compiled from already carries, or None.

    THE JOIN THAT WAS NEVER MADE. Cells reach `research_candidates` through
    `discovery_compiler`, which writes its OWN generator; reading the candidate's stamp alone
    credits one pass-through with the desk's whole output. The discovery is where the producer
    and the regional ground are still visible, so the candidate INHERITS them at birth.
    """
    if not discovery_id:
        return None
    try:
        row = c.execute("SELECT producer, region, generator, origin, source_id FROM discoveries "
                        "WHERE discovery_id=?", (str(discovery_id),)).fetchone()
    except sqlite3.Error:
        return None
    if row is None:
        return None
    return _attr.attribute(producer=row["producer"], region=row["region"],
                           generator=row["generator"], origin=row["origin"],
                           source_country=_source_country(c, row["source_id"]),
                           source_id=row["source_id"])


def _stamp(c: sqlite3.Connection, fields: Mapping[str, Any], *, origin: Any = None,
           generator: Any = None) -> dict[str, str]:
    """THE BIRTH STAMP. Every cell and discovery carries its producer and, where the producer
    belongs to one, its region -- written here, by the creating call, through the ONE helper
    (`libs/research/attribution.py`). A later sweep can only recover what lineage still holds."""
    return _attr.stamp(
        producer=fields.get("producer"), region=fields.get("region"),
        generator=generator if generator is not None else fields.get("generator"),
        origin=origin, department=fields.get("department"),
        source_country=_source_country(c, fields.get("source_id")),
        source_id=fields.get("source_id"),
        parent=_parent_attribution(c, fields.get("discovery_id")))


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
            _commit(c)
            return str(row["id"]), False
        cid = candidate_id or new_id("cand")
        if candidate_id and c.execute("SELECT 1 FROM research_candidates WHERE id=?",
                                      (candidate_id,)).fetchone() is not None:
            # The cell id is already taken by a DIFFERENT rule (the desk re-used a cell id with
            # new params, or two donors named the same cell). Measured on the box 2026-09-17:
            # the desk bridge died on `UNIQUE constraint failed: research_candidates.id` and
            # poured nothing. A second content under one name is a second candidate whose id
            # carries the content, and the cell id stays reachable through donated_cell.
            cid = f"{candidate_id}~{h[:10]}"
            fields = {**fields, "donated_cell": candidate_id}
        cell = grid_cell({**fields, "mechanism": mechanism, "symbol": symbol})
        empty = c.execute("SELECT 1 FROM research_candidates WHERE grid_cell=? LIMIT 1",
                          (cell,)).fetchone() is None
        rec: dict[str, Any] = {
            "id": cid, "created_at": now(), "updated_at": now(), "family": family,
            "symbol": symbol, "params_json": _j(dict(params or {})), "content_hash": h,
            "status": status, "mechanism": mechanism, "origin": origin, "grid_cell": cell,
            "empty_axis_bonus": EMPTY_CELL_BONUS if empty else 0.0, "search_count": 1,
            "campaign_id": str(fields.get("campaign_id") or ""),
            "subtype": str(fields.get("transformation") or ""), "survived": 0,
            **_stamp(c, fields, origin=origin),
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
        _commit(c)
        return cid, True
    finally:
        if conn is None:
            c.close()


#: THE LEASE THE JUDGE CAN ACTUALLY DRINK FROM, measured, never a constant.
#:
#: WHAT IT WAS. `moat_candidate_compiler.CLAIM_PER_DEPARTMENT = 12` across the hourly cycle's
#: departments was the ONLY door out of this database into the file the sealed gauntlet reads.
#: Measured on the trading box 2026-09-24 it leased 276 rows an hour (12 x 23 departments)
#: against 356,087 candidates -- 54 days to walk the population ONCE, against a population that
#: grows faster than that. A number chosen for politeness, sitting in front of a judge that had
#: already recorded 44,310 verdicts inside a single hour on that same box.
#:
#: WHAT IT IS NOW. The judge's OWN demonstrated consumption, read from the verdict ledger it
#: writes: the busiest hour it has ever recorded. That is not an estimate of what the judge might
#: take, it is a receipt for what it did take. The floor is the historic lease, so an unreadable
#: or absent ledger leaves the desk exactly where it was and can never make this smaller --
#: growth governance Rule 1: this mechanism only ever raises throughput, so it owes no
#: missed-growth line, and a brake added here would.
LEASE_FLOOR = 276
#: Bytes of the ledger's tail read to find that hour. The busiest hour is recent by construction
#: (the population and the sweep both only grow), and an unbounded read of a 34 MB ledger on
#: every pass is a cost with no answer attached.
LEASE_LEDGER_TAIL_BYTES = 16 * 1024 * 1024
#: Ids per claiming UPDATE. Well under SQLite's default 32,766 host-parameter ceiling, and small
#: enough that no single statement holds the write lock for long at a judge-sized lease.
CLAIM_CHUNK = 500


def judge_consumption_per_hour(path: Path | None = None,
                               tail_bytes: int = LEASE_LEDGER_TAIL_BYTES) -> tuple[int, str]:
    """(verdicts in the judge's busiest recorded hour, how it was measured).

    UNMEASURED is a real answer (L1.28a): an absent or unreadable ledger returns 0 with the reason,
    and the caller then keeps the historic lease rather than inventing a number.
    """
    p = path or (DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl")
    try:
        size = p.stat().st_size
        with p.open("rb") as fh:
            if size > tail_bytes:
                fh.seek(size - tail_bytes)
                fh.readline()                      # drop the partial line the seek landed inside
            blob = fh.read()
    except OSError as exc:
        return 0, f"UNMEASURED: {type(exc).__name__} reading {p}"
    per_hour: dict[str, int] = {}
    rows = 0
    for line in blob.splitlines():
        if not line.strip():
            continue
        try:
            at = str(json.loads(line).get("at") or "")
        except ValueError:
            continue
        rows += 1
        if len(at) >= 13:
            per_hour[at[:13]] = per_hour.get(at[:13], 0) + 1
    if not per_hour:
        return 0, f"UNMEASURED: {rows} row(s) in the tail of {p.name} carry no timestamp"
    best = max(per_hour.values())
    return int(best), (f"the busiest hour in the last {len(blob)} bytes of {p.name}: {best} "
                       f"verdicts, over {len(per_hour)} hour(s) and {rows} row(s)")


def lease_size(departments: int = 1, *, path: Path | None = None) -> tuple[int, dict[str, Any]]:
    """(rows ONE department may lease per pass, the measurement behind it).

    The judge's busiest measured hour, divided across the departments that bid, floored at the
    historic lease so this can only ever open the door wider.
    """
    consumed, how = judge_consumption_per_hour(path)
    d = max(1, int(departments))
    want = -(-consumed // d)                       # ceil: the lease must reach the whole rate
    floor_per_dept = -(-LEASE_FLOOR // d)
    per_dept = max(floor_per_dept, want)
    return per_dept, {"judge_consumption_per_hour": consumed, "how": how,
                      "departments": d, "per_department": per_dept,
                      "total_per_pass": per_dept * d, "floor_total": LEASE_FLOOR,
                      "rule": ("the lease is the judge's own busiest recorded hour, split across "
                               "the bidding departments and floored at the historic lease; it "
                               "never shrinks, so it is a throughput mechanism and not a brake")}


def claim_candidates(department: str, n: int, origin: str | None = None,
                     conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    """A department bids compute: the best-scored queued candidates become its claims.

    SET-BASED ON PURPOSE. This used to issue one UPDATE per claimed row, which is invisible at a
    12-row lease and is the whole cost at a judge-sized one: the lease below is now thousands of
    rows a pass, and a Python loop around `UPDATE ... WHERE id=?` would hold the registry's single
    write lock for the length of it and shut every producer out. The ids the SELECT returned are
    claimed in chunks of one statement each -- exactly those rows, never a re-run of the query
    against a table the first half of the update has already changed.
    """
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
        ids = [str(r["id"]) for r in rows]
        stamp = now()
        for i in range(0, len(ids), CLAIM_CHUNK):
            chunk = ids[i:i + CLAIM_CHUNK]
            c.execute("UPDATE research_candidates SET status='claimed', claimed_by=?, "  # noqa: S608
                      "claimed_at=?, updated_at=? WHERE id IN ("
                      + ",".join("?" * len(chunk)) + ")", [department, stamp, stamp, *chunk])
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
        # THROUGH `_commit`, NOT `c.commit()` (measured 2026-09-24). `batch()` was written for
        # the DONATION path and bound only the three doors that path uses --
        # `enqueue_candidate`, `record_discovery`, `set_discovery_state` -- so it worked
        # perfectly for its one caller and was inert for everybody else. This door and `link`
        # committed directly, so no batch could ever bind them. The conversion DRAIN repairs a
        # row with three writes (enqueue, link, mark): two of the three could not be batched at
        # any chunk size, which is why its pass spent 99.95% of an hour waiting for the write
        # lock. What a batch buys that caller is FEWER LOCK ACQUISITIONS, not cheaper commits --
        # measured 2026-09-24, an uncontended three-write repair runs at 322 rows/s per-row and
        # 276 rows/s batched, while the live box runs it at 0.72 rows/s. Outside a batch
        # `_commit` IS `c.commit()`, so nothing changes for every other caller.
        _commit(c)
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
            **_stamp(c, {**fields, "source_id": source_id}, origin=origin, generator=generator),
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
        _commit(c)
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
        _commit(c)
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
        # See `mark_candidate`: `_commit` honours an open `batch()` and is a plain commit without
        # one. A provenance edge is written once per repaired row, so this door carried a third
        # of the conversion drain's write-lock traffic on its own and no batch could reach it.
        _commit(c)
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
                          (statement, result or "pending", failure_cause, failure_stage, lessons,
                           _j(metrics), _j(payload), _j(evidence), now(), row["id"]))
                c.commit()
                return str(row["id"])
        mid = new_id("mem")
        result = result or "pending"
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
                  (run_id, now(), now(), hypothesis_id, name, git_commit or "", config_hash or "",
                   0 if seed is None else int(seed), status, _j(metrics), organ, department,
                   started_at, finished_at, compute_s, outcome, _j(inputs), _j(outputs)))
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


def representation_upsert(representation_id: str, *, dataset: str, transform: str, family: str,
                          conn: sqlite3.Connection | None = None, **fields: Any) -> bool:
    """Register a minted representation. Returns True when the row is new.

    The IDENTITY columns are rewritten on every pass (a longer series, a later last_available);
    the ROI counters are NOT touched here -- they are additive and belong to
    `representation_roi_update`, because a forge pass reports what it minted and never what it
    thinks the downstream total should now be.
    """
    c = conn or connect()
    try:
        row = c.execute("SELECT representation_id FROM representations WHERE representation_id=?",
                        (representation_id,)).fetchone()
        rec: dict[str, Any] = {"dataset": dataset, "transform": transform, "family": family,
                               "updated_at": now()}
        allowed = set(_columns(c, "representations"))
        for k, v in fields.items():
            col = {"params": "params_json", "pit": "pit_json", "payload": "payload_json"}.get(k, k)
            if col in allowed and col not in rec:
                rec[col] = _j(v) if col.endswith("_json") and not isinstance(v, str) else v
        if row is None:
            rec.update({"representation_id": representation_id, "created_at": now()})
            for counter in ("used_by_candidates", "survivors", "forward_rows"):
                rec.setdefault(counter, 0)
            keys = list(rec)
            c.execute(f'INSERT INTO representations({",".join(keys)}) '
                      f'VALUES({",".join("?" * len(keys))})', [rec[k] for k in keys])
            c.commit()
            return True
        c.execute("UPDATE representations SET " + ", ".join(f"{k}=?" for k in rec)  # noqa: S608
                  + " WHERE representation_id=?", [*rec.values(), representation_id])
        c.commit()
        return False
    finally:
        if conn is None:
            c.close()


def representation_roi_update(representation_id: str, *, conn: sqlite3.Connection | None = None,
                              **inc: float) -> None:
    """Additive ROI counters (used_by_candidates, survivors, forward_rows, compute_s) and
    absolute readings (live_attribution, explained_variance) for one representation."""
    c = conn or connect()
    try:
        row = c.execute("SELECT * FROM representations WHERE representation_id=?",
                        (representation_id,)).fetchone()
        if row is None:
            return
        cur = dict(row)
        sets: dict[str, Any] = {"updated_at": now()}
        for k in ("used_by_candidates", "survivors", "forward_rows"):
            if k in inc:
                sets[k] = int(float(cur.get(k) or 0) + float(inc[k]))
        if "compute_s" in inc:
            sets["compute_s"] = float(cur.get("compute_s") or 0.0) + float(inc["compute_s"])
        for k in ("live_attribution", "explained_variance", "novelty", "expected_value"):
            if k in inc:
                sets[k] = float(inc[k])
        c.execute("UPDATE representations SET " + ", ".join(f"{k}=?" for k in sets)  # noqa: S608
                  + " WHERE representation_id=?", [*sets.values(), representation_id])
        c.commit()
    finally:
        if conn is None:
            c.close()


def representations(family: str | None = None, limit: int = 500,
                    conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    """The ROI table: minted representations ordered by what they have actually earned."""
    c = conn or connect()
    try:
        q = "SELECT * FROM representations WHERE 1=1"
        args: list[Any] = []
        if family:
            q += " AND family=?"
            args.append(family)
        q += (" ORDER BY COALESCE(survivors,0) DESC, COALESCE(used_by_candidates,0) DESC,"
              " created_at DESC LIMIT ?")
        args.append(limit)
        return _rows(c.execute(q, args))
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


def _iter_new_lines(c: sqlite3.Connection, key: str, p: Path, max_rows: int
                    ) -> Iterator[tuple[dict[str, Any], int]]:
    """(row, offset AFTER that row) for every JSONL row past the byte cursor, at most max_rows.

    The generator exists so the caller can persist PARTIAL progress. `_new_lines` materialised the
    whole batch and the cursor advanced only after every row of it had been poured, so a stream
    that could not finish inside a leg's budget wrote no cursor at all and restarted from the same
    byte next hour, for ever -- which is how 3,368 gauntlet verdicts sat unsynced from the
    2026-09-17 restore to 2026-09-23 while a 28 MB `hypothesis_graph.jsonl` consumed every pass
    ahead of them. Yield-as-you-go plus a deadline makes progress monotone.
    """
    if not p.exists():
        return
    start = _cursor_get(c, key)
    size = p.stat().st_size
    if start > size:
        start = 0
    n = 0
    with p.open("rb") as f:
        f.seek(start)
        pos = start
        for raw in f:
            if n >= max_rows:
                return
            pos += len(raw)
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                n += 1
                yield obj, pos


def _new_lines(c: sqlite3.Connection, key: str, p: Path, max_rows: int
               ) -> tuple[list[dict[str, Any]], int]:
    """JSONL rows after the byte cursor, at most max_rows; returns rows and the new offset."""
    if not p.exists():
        return [], 0
    rows: list[dict[str, Any]] = []
    pos = _cursor_get(c, key)
    size = p.stat().st_size
    if pos > size:
        pos = 0
    for obj, at_pos in _iter_new_lines(c, key, p, max_rows):
        rows.append(obj)
        pos = at_pos
    return rows, pos


# --------------------------------------------------------------- the streams and their receipts
#: EVERY JSONL STREAM THIS BRIDGE POURS: cursor key -> path, relative to ROOT. The cursor key is
#: the stream's RECEIPT -- present means "this stream has been read to byte N", absent means "this
#: stream has never been read at all". The registry was restored from backup on 2026-09-17, which
#: wiped every receipt, and nothing said so: `_cursor_get` reads an absent key as 0, which is
#: indistinguishable from a stream that is merely at its start. So a missing key is now a
#: MEASURED defect (`missing_cursor_keys`), seeded at the top of every sync and fenced by
#: `scripts/check_conversion_debt.py`. A stream the sync knows about with no receipt fails.
SYNC_STREAMS: tuple[tuple[str, str], ...] = (
    ("gate_verdicts", "desks/mt5/data/hypotheses/gate_verdict_ledger.jsonl"),
    ("hypothesis_graph", "desks/mt5/data/hypothesis_graph.jsonl"),
    ("compute_ledger", "desks/mt5/data/compute_ledger.jsonl"),
    ("desk_lessons", "docs/desk_lessons.jsonl"),
)
#: One sync cycle: the hourly leg `registry_sync`. A stream further behind than this is a backlog.
SYNC_CYCLE_S = 3600.0
#: The most of one pass's wall-clock budget the hypothesis graph may take. It is the biggest
#: stream (28 MB) and it runs first because a verdict marks the candidate it enqueues -- so it is
#: bounded by a SHARE, never by the whole pass, and the verdicts behind it can never be starved.
GRAPH_BUDGET_SHARE = 0.4
#: How often a stream persists its cursor mid-loop. The leg runs as a subprocess under the hour's
#: budget and is SIGKILLed when it overruns, and a kill between the last row and the cursor write
#: replays every row of the batch -- so progress is durable every this many rows, not once.
CURSOR_EVERY = 200


def stream_path(key: str, desk: Path | None = None, lessons: Path | None = None) -> Path | None:
    """The file a stream key names, or None when the key is not one this sync knows."""
    for name, rel in SYNC_STREAMS:
        if name != key:
            continue
        if name == "desk_lessons" and lessons is not None:
            return Path(lessons)
        if rel.startswith("desks/mt5/") and desk is not None:
            return Path(desk) / rel[len("desks/mt5/"):]
        return ROOT / rel
    return None


def missing_cursor_keys(conn: sqlite3.Connection | None = None) -> list[str]:
    """Streams the sync knows about that hold NO cursor row -- loud absence, never a silent 0."""
    c = conn or connect()
    try:
        have = {str(r["key"]) for r in c.execute("SELECT key FROM sync_cursor")}
        return [k for k, _ in SYNC_STREAMS if k not in have]
    finally:
        if conn is None:
            c.close()


def _seed_cursors(c: sqlite3.Connection) -> list[str]:
    """Give every known stream a receipt at 0 so absence can never recur silently. Returns the
    keys that were missing -- the sync reports them, which is how a lost stream becomes visible."""
    missing = missing_cursor_keys(c)
    for k in missing:
        c.execute("INSERT OR IGNORE INTO sync_cursor(key, value, updated_at) VALUES(?,?,?)",
                  (k, "0", now()))
    if missing:
        c.commit()
    return missing


def verdict_backlog(desk: Path | None = None,
                    conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """HOW FAR THE GAUNTLET'S VERDICTS ARE AHEAD OF THE REGISTRY, in rows and in seconds.

    The gauntlet appends a verdict to `data/hypotheses/gate_verdict_ledger.jsonl`; this bridge is
    the only thing that turns it into a trial with a candidate edge, and `cells_judged` -- per
    source, per pack, per region -- counts nothing else. So a ledger ahead of the registry is not
    a lag, it is the funnel's last stage reading zero. Measured here (never asserted) and fenced
    by `scripts/check_conversion_debt.py`: missing receipt, or a row older than one sync cycle
    still unpoured, is a BREACH.
    """
    d = desk or DESK
    c = conn or connect()
    out: dict[str, Any] = {"cycle_s": SYNC_CYCLE_S}
    try:
        p = d / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
        out["ledger"] = str(p)
        missing = missing_cursor_keys(c)
        out["cursor_keys_missing"] = missing
        if not p.exists():
            out.update({"status": "UNMEASURED", "why": f"no verdict ledger at {p}"})
            return out
        row = c.execute("SELECT value FROM sync_cursor WHERE key='gate_verdicts'").fetchone()
        cursor = int(row["value"]) if row is not None else None
        size = p.stat().st_size
        out.update({"cursor": cursor, "size_bytes": size})
        if cursor is None:
            out.update({"status": "BREACH", "unsynced_rows": None, "oldest_unsynced_age_s": None,
                        "why": "the registry holds NO 'gate_verdicts' cursor key: the stream has "
                               "never been read, or a restore wiped its receipt and nothing said "
                               "so -- every verdict on disk is invisible to the registry"})
            return out
        start = 0 if cursor > size else cursor
        n, oldest = 0, None
        with p.open("rb") as f:
            f.seek(start)
            for raw in f:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(obj, dict):
                    continue
                n += 1
                at = str(obj.get("at") or "")
                if at and (oldest is None or at < oldest):
                    oldest = at
        age = None
        if oldest:
            try:
                age = (datetime.now(tz=UTC) - datetime.fromisoformat(oldest)).total_seconds()
            except ValueError:
                age = None
        out.update({"unsynced_rows": n, "oldest_unsynced": oldest, "oldest_unsynced_age_s": age})
        if missing:
            out.update({"status": "BREACH",
                        "why": f"streams with no cursor receipt: {', '.join(missing)}"})
        elif age is not None and age > SYNC_CYCLE_S:
            out.update({"status": "BREACH",
                        "why": f"{n} verdict(s) unpoured, the oldest {age/3600:.1f}h old -- the "
                               f"ledger is ahead of the registry by more than one sync cycle "
                               f"({SYNC_CYCLE_S/3600:.0f}h), so cells_judged is short by that "
                               f"many cells for every source, pack and region"})
        else:
            out.update({"status": "OK",
                        "why": f"{n} verdict(s) unpoured, none older than one sync cycle"})
        return out
    finally:
        if conn is None:
            c.close()


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


def graph_id_map(desk: Path) -> dict[str, str]:
    """cell string -> `hypothesis_graph` node id, from `scripts/backfill_verdict_graph_ids.py`.

    The gate ledger names a cell `EURAUD.overnight_gap_decay.p=<sha of params>` and the graph
    names it `f668ed18...`, so a trial recorded under the first name could never join the
    candidate enqueued under the second. New verdict rows carry `graph_id` themselves; this map
    is the fallback for the rows written before that field existed. An absent or unreadable file
    reads as EMPTY -- every cell then keeps its own name, exactly as before, which is the safe
    direction: a missing map costs a join, a wrong one would merge two hypotheses.
    """
    p = desk / "data" / "hypotheses" / "gate_verdict_graph_ids.json"
    try:
        doc = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    if not isinstance(doc, dict):
        return {}
    raw = doc.get("graph_ids")
    if not isinstance(raw, dict):
        raw = doc
    return {str(k): str(v) for k, v in raw.items() if isinstance(v, str) and v}


def _identity_fns() -> tuple[Any, Any]:
    """(parts, parse_clock_key) from the desk's ONE identity module, or (None, None).

    Imported, never re-implemented: `desks/mt5/research/certificate_truth.py` owns the canonical
    identity (symbol|family|selector, lowercased -- the shadow_spec the sealed gauntlet stamps and
    the promoter matches), and a second copy of that rule here is how two stores start disagreeing
    again. Unreachable is UNMEASURED, and the join then falls back exactly as it did before.
    """
    for p in (str(DESK / "research"), str(DESK)):
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        from certificate_truth import (  # type: ignore[import-not-found]
            parse_clock_key,
            parts,
        )
    except ImportError:                                                  # pragma: no cover
        return None, None
    return parts, parse_clock_key


def _spec_key(symbol: Any, family: Any, params_json: Any) -> str | None:
    """`hypothesis_graph.node_id(symbol, family, params)` -- THE PARAMETERS ARE IN THE KEY.

    This is the same function `external_gauntlet` calls to stamp `graph_id` on every gate-verdict
    row it writes, so a key built here and a verdict's own stamp are the SAME string by
    construction rather than by agreement. Unreachable or unhashable is None, which costs this
    tier and nothing else.
    """
    try:
        from libs.research.hypothesis_graph import node_id
    except ImportError:                                                  # pragma: no cover
        return None
    try:
        p = json.loads(params_json) if isinstance(params_json, str) else (params_json or {})
    except ValueError:
        p = {}
    if not isinstance(p, dict):
        p = {}
    try:
        return str(node_id(str(symbol or ""), str(family or ""), p))
    except Exception:
        return None


def candidate_identity_index(c: sqlite3.Connection) -> dict[str, dict[str, str]]:
    """Four tiers, widest identity first: {'ids', 'spec', 'exact', 'pair'} -> candidate id.

    The registry's candidates are keyed `cand_<hex>`; the gate ledger names its cells
    `EURAUD.overnight_gap_decay.p=<sha>`. Neither name can ever join the other, which is why every
    verdict poured in before today landed with a candidate_id matching no row. The desk already
    settled what joins them (certificate_truth.IDENTITY_RULE), so the join is made on the parts.

    WHAT WAS WRONG, AND IT WAS NOT A SLOW CLOCK (measured on the trading box 2026-09-24). This
    index held TWO tiers, `symbol|family|session` and `symbol|family|`, and built both with
    `setdefault` over `ORDER BY seq`. The lowest-seq row therefore OWNED its identity forever and
    every later candidate sharing the triple was structurally unreachable by any verdict: 16,216
    identities against 356,087 candidates, so 95.4% of the population could not be judged however
    much compute was spent on it, and `GBPSEK|overnight_drift|` alone swallowed 3,797 cells into
    one reachable row. An identity only its oldest holder can own is not an identity, it is a
    first-come lock, and it capped the whole desk's judgeable population.

    THE FIX IS TO PUT THE PARAMETERS IN THE KEY, which is what a parameterised cell's identity
    has always been: `spec` is `node_id(symbol, family, params)`, the EXACT string
    `external_gauntlet` stamps on its own verdicts as `graph_id`. Measured on the same file:
    267,301 distinct spec keys against 16,216 triples -- a 16.5x lift in reachable identities,
    and the tier a verdict reaches FIRST because the judge already names its cells this way.

    The two coarse tiers stay, because a verdict whose params were never recorded has nothing but
    `symbol|family|selector` to offer -- but they no longer lock: where several candidates share a
    coarse key the UNJUDGED one is preferred, so the second verdict on a triple reaches a second
    cell instead of landing on row #1 again. `ids` is the existence check: a `graph_id` naming no
    row in this file is a dangling id, and recording it as a join was how 17,773 of 25,592 trials
    came to carry a candidate_id that matched nothing.
    """
    parts, _ = _identity_fns()
    out: dict[str, dict[str, str]] = {"ids": {}, "spec": {}, "exact": {}, "pair": {}}
    judged: dict[str, bool] = {}          # coarse key -> is the incumbent already judged?
    for r in c.execute("SELECT id, COALESCE(symbol,'') s, COALESCE(family,'') f, "
                       "COALESCE(session,'') w, params_json, judged_at "
                       "FROM research_candidates "
                       "WHERE symbol IS NOT NULL AND symbol != '' AND family != '' "
                       "ORDER BY seq"):
        cid = str(r["id"])
        out["ids"][cid] = cid
        spec = _spec_key(r["s"], r["f"], r["params_json"])
        if spec is not None:
            out["spec"].setdefault(spec, cid)
        if parts is None:
            continue
        is_judged = bool(r["judged_at"])
        for tier, key in (("exact", parts(r["s"], r["f"], r["w"])),
                          ("pair", parts(r["s"], r["f"], None))):
            # First writer wins, EXCEPT that an unjudged row displaces a judged incumbent: a
            # coarse key with 3,797 holders must not hand every verdict to the same one.
            if key not in out[tier] or (judged.get(f"{tier}\x00{key}") and not is_judged):
                out[tier][key] = cid
                judged[f"{tier}\x00{key}"] = is_judged
    return out


def verdict_candidate(row: Mapping[str, Any], gmap: Mapping[str, str],
                      index: Mapping[str, Mapping[str, str]]) -> tuple[str, str]:
    """(candidate id, how it was found) for one gate-verdict row -- the edge back to what was
    judged.

    THE ORDER IS NARROWEST IDENTITY FIRST, AND EVERY HIT IS CHECKED AGAINST THE FILE. A stamped
    `graph_id` used to be returned unchecked, so a verdict on a hypothesis this registry has never
    held was recorded as a join and updated zero rows. Measured on the trading box 2026-09-24 over
    the last 20,000 verdicts: 19,211 were recorded as `graph_id` joins and only 2,614 of them
    named a row that exists -- 16,611 false joins, which is why 17,773 of 25,592 trials carry a
    candidate_id matching nothing. The same stamp is now tried first as an id and then as the
    `spec` key, which it IS: both are `hypothesis_graph.node_id(symbol, family, params)`, so the
    registry's own `cand_<hex>` name for that exact rule is found instead of dangling.

    A DANGLING `graph_id` DOES NOT FALL THROUGH TO THE COARSE TIERS, and that refusal is the
    point. A stamp naming a rule this file does not hold is POSITIVE evidence the registry never
    saw the cell; joining it to a sibling that merely shares `symbol|family|selector` -- and
    16,216 such keys cover 356,087 candidates, one of them with 3,797 holders -- would mark a
    candidate JUDGED that no judge ever looked at, and the docket feed would then stop offering it.
    That is manufacturing a verdict, so the row keeps the graph's own name and is recorded as
    unjoined (L1.28a). The coarse tiers stay for verdicts that carry no stamp at all, which is the
    only case where `symbol|family|selector` is the best identity in evidence.
    """
    cell = str(row.get("cell") or "")
    ids = index.get("ids", {})
    spec = index.get("spec", {})
    for gid, how in ((str(row.get("graph_id") or ""), "graph_id"),
                     (gmap.get(cell, ""), "graph_id_map")):
        if not gid:
            continue
        if not ids or gid in ids:
            return gid, how
        hit = spec.get(gid)
        if hit:
            return hit, f"{how}_spec"
        return gid, f"{how}_unjoined"
    parts, parse = _identity_fns()
    if parts is not None:
        sym, fam = row.get("sym"), row.get("family")
        selector = ((parse(cell) or {}).get("selector") if parse is not None else None)
        if sym and fam:
            hit = index.get("exact", {}).get(parts(sym, fam, selector))
            if hit:
                return hit, "identity_exact"
            hit = index.get("pair", {}).get(parts(sym, fam, None))
            if hit:
                return hit, "identity_pair"
    return cell, "cell_name_unjoined"


def _status_of_fate(fate: Any) -> str:
    f = str(fate or "").lower()
    if not f or f in ("born", "pending", "queued", "donated"):
        return "donated"
    if f in ("certified", "survived", "promoted", "live"):
        return "survived"
    return "judged"


def sync_from_desk(desk: Path | None = None, *, max_rows: int = 20000,
                   lessons: Path | None = None, conn: sqlite3.Connection | None = None,
                   budget_s: float | None = None) -> dict[str, Any]:
    """Pour the desk's existing record into the chain, incrementally and idempotently.

    ORDER, BUDGET AND RECEIPTS ARE THE FIX (2026-09-23). Every stream used to be read in file
    order with its cursor written only after the whole batch had been poured, and the 28 MB
    `hypothesis_graph.jsonl` came first: a leg that ran out of budget inside it wrote no cursor,
    restarted at the same byte next hour, and NEVER REACHED the gate verdicts behind it. Measured
    that day: 3,368 gauntlet verdicts on disk, no `gate_verdicts` cursor key at all, 140 trials in
    the registry (none of them a gauntlet verdict) and `cells_judged` therefore 0 for every source,
    pack and region. So the VERDICTS go first -- they are the funnel's last stage -- the cursor
    advances row by row, each stream commits its own progress, and a stream that fails is recorded
    by name in the return rather than discarding every other stream's work with it.
    """
    d = desk or DESK
    c = conn or connect()
    out: dict[str, Any] = {"candidates": 0, "trials": 0, "runs": 0, "cards": 0, "events": 0,
                           "memories": 0, "workers": 0}
    deadline = None if budget_s is None else time.monotonic() + float(budget_s)

    def over() -> bool:
        return deadline is not None and time.monotonic() > deadline
    streams: dict[str, Any] = {}
    out["streams"] = streams
    out["cursor_keys_seeded"] = _seed_cursors(c)
    try:
        # ------------------------------------------------------------- 1. the hypothesis graph
        # Bounded by a SHARE of the budget, never the whole of it. It runs first because a verdict
        # marks the candidate the graph enqueues, and it is the stream that starved the others:
        # 28 MB of it ahead of everything else, with a cursor that only moved if it finished.
        try:
            pos = _cursor_get(c, "hypothesis_graph")
            n = 0
            share = (None if deadline is None
                     else time.monotonic() + float(budget_s or 0.0) * GRAPH_BUDGET_SHARE)
            for r, at_pos in _iter_new_lines(c, "hypothesis_graph",
                                         d / "data" / "hypothesis_graph.jsonl", max_rows):
                pos = at_pos
                cid = str(r.get("id") or "")
                if not cid:
                    continue
                src = str(r.get("source") or "")
                _, created = enqueue_candidate(
                    family=str(r.get("family") or ""), symbol=str(r.get("symbol") or ""),
                    params=r.get("params") if isinstance(r.get("params"), dict) else {},
                    origin=origin_of(src), mechanism=str(r.get("why") or "")[:200],
                    candidate_id=cid, status=_status_of_fate(r.get("fate")), generator=src,
                    parent_ids=[r["parent"]] if r.get("parent") else [], conn=c)
                out["candidates"] += int(created)
                n += 1
                if n % CURSOR_EVERY == 0:
                    _cursor_set(c, "hypothesis_graph", pos)
                    c.commit()
                if share is not None and time.monotonic() > share:
                    break
            _cursor_set(c, "hypothesis_graph", pos)
            c.commit()
            streams["hypothesis_graph"] = {"rows": n, "cursor": pos}
        except Exception as exc:  # a failing stream is named, never silent
            streams["hypothesis_graph"] = {"error": f"{type(exc).__name__}: {exc}"}

        # ------------------------------------------------- 2. THE VERDICTS (the starved stream)
        try:
            pos = _cursor_get(c, "gate_verdicts")
            gmap = graph_id_map(d)
            index = candidate_identity_index(c)
            joins: dict[str, int] = {}
            n = 0
            for r, at_pos in _iter_new_lines(
                    c, "gate_verdicts",
                    d / "data" / "hypotheses" / "gate_verdict_ledger.jsonl", max_rows):
                pos = at_pos
                cell = str(r.get("cell") or "")
                if not cell:
                    continue
                passed = r.get("passed")
                # THE CANDIDATE THIS TRIAL JUDGED. The trial keeps the cell's own name as its
                # hypothesis id (that is what a reader recognises), but the CANDIDATE edge needs
                # an id the registry holds: the writer's `graph_id`, the backfill map, or the
                # desk's canonical identity (symbol|family|selector). The cell name joins nothing.
                cand, how = verdict_candidate(r, gmap, index)
                joins[how] = joins.get(how, 0) + 1
                record_trial(cell, family=str(r.get("family") or ""), method="gauntlet",
                             params=None, terminal_gate=str(r.get("terminal_gate") or ""),
                             passed=None if passed is None else bool(passed),
                             verdict={"downstream_status": r.get("downstream_status"),
                                      "at": r.get("at"), "join": how},
                             symbol=str(r.get("sym") or ""), candidate_id=cand, conn=c)
                out["trials"] += 1
                n += 1
                mark_candidate(cand, "survived" if passed else "judged",
                               judged_at=str(r.get("at") or now()),
                               terminal_gate=str(r.get("terminal_gate") or ""),
                               survived=1 if passed else 0, conn=c)
                if n % CURSOR_EVERY == 0:
                    _cursor_set(c, "gate_verdicts", pos)
                    c.commit()
                if over():
                    break
            _cursor_set(c, "gate_verdicts", pos)
            c.commit()
            streams["gate_verdicts"] = {"rows": n, "cursor": pos, "joins": joins}
            out["verdict_joins"] = joins
        except Exception as exc:  # a failing stream is named, never silent
            streams["gate_verdicts"] = {"error": f"{type(exc).__name__}: {exc}"}

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
        streams["compute_ledger"] = {"rows": len(rows), "cursor": pos}
        c.commit()

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
        streams["desk_lessons"] = {"rows": len(rows), "cursor": pos}
        out["cursor_keys_missing"] = missing_cursor_keys(c)
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
