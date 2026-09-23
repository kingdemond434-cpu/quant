"""PROVE EDGES, NOT JUST NODES.

Every liveness census this desk ever built counted NODES: which organ ran, which file exists, which
task is Ready. A desk made entirely of healthy nodes can still be dead, and has been -- a compiler
that ran hourly while the donations it was meant to read sat in a directory nothing scanned; a
gauntlet judging a docket the forward lane never saw; 4,822 intelligence artifacts on one branch
that never reached the compiler on the other. Each node was green. The EDGE between them did not
exist, and nothing in the desk was shaped to notice.

So the mandatory pipeline is declared here AS DATA -- producer, consumer, the artifact that passes
between them -- and an edge is OBSERVED only when all of this is true at once:

    the producer wrote the artifact (a lineage row with its producer_run_id),
    the artifact's lease is still valid (freshness proven, not assumed),
    the consumer acknowledged THAT RUN of it (an ack naming the same producer_run_id).

CLOSED LOOP = every required edge observed inside valid freshness leases. An ack that does not
name the producer run is WEAK: it proves someone read a file with that name, not that they read
the run under judgement, so it is reported and never counted.

THE STORE. `desks/mt5/data/lineage.sqlite`, two tables, opened on demand and degrading to "no
rows" rather than raising -- the pattern `libs/moat/registry.py` uses for the canonical registry.
A lineage store that can take down the organ it is recording is a store that gets removed.
"""
from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"
LINEAGE_DB = DESK / "data" / "lineage.sqlite"

UNMEASURED = "UNMEASURED"

_ARTIFACTS_DDL = """
CREATE TABLE IF NOT EXISTS lineage_artifacts (
    artifact_id TEXT NOT NULL,
    producer_component_id TEXT NOT NULL,
    producer_run_id TEXT NOT NULL,
    epoch_id TEXT,
    code_sha TEXT,
    config_hash TEXT,
    content_hash TEXT,
    created_at TEXT NOT NULL,
    valid_until TEXT,
    producer_generation INTEGER,
    input_artifact_ids TEXT,
    PRIMARY KEY (artifact_id, producer_run_id)
)
"""
_ACKS_DDL = """
CREATE TABLE IF NOT EXISTS lineage_acks (
    consumer_component_id TEXT NOT NULL,
    consumed_artifact_id TEXT NOT NULL,
    consumer_run_id TEXT NOT NULL,
    producer_run_id TEXT,
    epoch_id TEXT,
    consumed_at TEXT NOT NULL,
    PRIMARY KEY (consumer_component_id, consumed_artifact_id, consumer_run_id)
)
"""
_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_lineage_artifacts_aid ON lineage_artifacts(artifact_id)",
    "CREATE INDEX IF NOT EXISTS ix_lineage_acks_aid ON lineage_acks(consumed_artifact_id)",
)


@dataclass(frozen=True)
class Edge:
    """One mandatory hop of the pipeline."""

    producer: str
    consumer: str
    artifact: str
    stage: str
    why: str = ""
    criticality: str = "required"

    @property
    def edge_id(self) -> str:
        return f"{self.producer} -> {self.consumer}"


#: THE MANDATORY PATH. Three chains, exactly as the principal's spec names them:
#:
#:   forests/miners -> data -> representation forge -> candidate compiler -> gauntlet ->
#:   forward -> promoter/allocator -> gateway
#:   discovery -> registry -> compiler
#:   controller -> allocation -> departments
#:
#: The artifact on each hop is the file that actually passes between the two, so an edge is a
#: statement about bytes rather than about intent.
REQUIRED_EDGES: tuple[Edge, ...] = (
    Edge("leg:forest_korea", "leg:compile_candidates",
         "desks/mt5/reports/FOREST_KOREA.json", "forest->compiler",
         "a regional forest that mints no candidate is a civilization nobody reads"),
    Edge("leg:deep_forest", "leg:compile_candidates",
         "desks/mt5/reports/DEEP_FOREST.json", "miner->compiler",
         "the deep forest's verbatim claims must reach the compiler or the mining is a diary"),
    Edge("leg:representation_forge", "leg:compile_candidates",
         "desks/mt5/reports/REPRESENTATION_FORGE.json", "data->representation->compiler",
         "representations exist to be searched over; unread, they are stranded data (LAWS 5c)"),
    Edge("leg:compile_candidates", "leg:merge_docket",
         "desks/mt5/data/hypotheses/miner_candidates.json", "compiler->docket",
         "a candidate nothing merges is a trial the desk paid for and never spent"),
    Edge("leg:merge_docket", "leg:external_gauntlet",
         "desks/mt5/data/hypotheses/external_survivors.json", "docket->gauntlet",
         "the judge's docket: an empty or unread one wipes certificates with exit code 0"),
    Edge("leg:external_gauntlet", "leg:enrol_clocks",
         "desks/mt5/reports/UNIVERSAL_SURVIVORS.json", "gauntlet->forward",
         "a certificate with no forward clock is the defect the clock fixer was raised for"),
    Edge("leg:enrol_clocks", "leg:promoter",
         "desks/mt5/reports/shadow/shadow_state.json", "forward->promoter",
         "forward evidence that reaches no promoter never becomes capital"),
    Edge("leg:promoter", "leg:pf_allocator",
         "desks/mt5/data/sleeves.json", "promoter->allocator",
         "a promoted sleeve the allocator does not see gets no fraction"),
    Edge("leg:pf_allocator", "task:MT5-Gateway",
         "desks/mt5/reports/pf_allocation.json", "allocator->gateway",
         "the gateway deploys the allocator's fractions un-re-shrunk, or the book is not the "
         "book the evidence bought (growth governance)"),
    Edge("leg:moat_miner", "leg:compile_candidates",
         "data/alpha_registry.sqlite", "discovery->registry->compiler",
         "discovery lands in the canonical registry and the compiler reads the registry"),
    Edge("leg:meta_controller", "leg:research_roi",
         "desks/mt5/reports/META_CONTROLLER.json", "controller->allocation",
         "the controller's epoch decides the hour's compute or it decides nothing"),
    Edge("leg:research_roi", "leg:japan_department",
         "desks/mt5/data/research_allocation.json", "allocation->departments",
         "compute/information/capital reallocation is observed at the department that spends it"),
    Edge("leg:control_plane", "task:MT5-ClockFixer",
         "desks/mt5/reports/CONTROL_PLANE.json", "reconciler->actuators",
         "the fifteen-minute apply pass acts on the observe pass's plan, not on its own guesses"),
    # THE COST WIRE, declared after it was found broken (2026-09-23). `net_edge_spine` read
    # `reports/EXECUTION_COST_SURFACE.json` and NOTHING wrote that name -- `cost_surface.py`
    # writes `reports/COST_SURFACE.json` -- so the spine's own inputs block said "absent" and
    # 212 of 273 priced rows carried no measured spread at all. Exactly the RESEARCH_BANDIT.json
    # shape this check exists for: both ends green, the wire absent. Declaring the pair is what
    # makes the next one fail loudly instead of silently pricing on a model.
    Edge("leg:cost_truth", "leg:net_edge",
         "desks/mt5/reports/EXECUTION_COST_SURFACE.json", "cost->net",
         "the spread the spine charges must be the one the broker quoted at the desk's own "
         "fills, or a real edge dies on a cost it would never have paid"),
    # And the OTHER half of the same defect: the venue-cost surface had no reader at all. It
    # carries commission and swap per (asset, time, size, state, order) -- NOT the crossing --
    # so its consumer is cost_truth, which publishes it beside the measurement and never feeds
    # it to the spine's spread slot, where it would charge commission twice.
    Edge("task:MT5-CostState", "leg:cost_truth",
         "desks/mt5/reports/COST_SURFACE.json", "venue-cost->cost-truth",
         "a surface nothing reads is a measurement the desk paid for and never spent"),
)


def edges_for(producer: str | None = None, consumer: str | None = None) -> list[Edge]:
    return [e for e in REQUIRED_EDGES
            if (producer is None or e.producer == producer)
            and (consumer is None or e.consumer == consumer)]


# ------------------------------------------------------------------------------ the store
def connect(path: Path | None = None) -> sqlite3.Connection | None:
    """The lineage store, created on first use. None when it cannot be opened -- a read-only
    tree, a locked file -- because recording lineage may never break the organ being recorded."""
    p = path or LINEAGE_DB
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(p), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute(_ARTIFACTS_DDL)
        conn.execute(_ACKS_DDL)
        for ddl in _INDEXES:
            conn.execute(ddl)
        conn.commit()
    except sqlite3.Error:
        return None
    return conn


def record_artifact(envelope: Mapping[str, Any], path: Path | None = None) -> bool:
    conn = connect(path)
    if conn is None:
        return False
    try:
        conn.execute(
            "INSERT OR REPLACE INTO lineage_artifacts (artifact_id, producer_component_id, "
            "producer_run_id, epoch_id, code_sha, config_hash, content_hash, created_at, "
            "valid_until, producer_generation, input_artifact_ids) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (str(envelope.get("artifact_id") or ""),
             str(envelope.get("producer_component_id") or UNMEASURED),
             str(envelope.get("producer_run_id") or UNMEASURED),
             str(envelope.get("epoch_id") or UNMEASURED),
             str(envelope.get("code_sha") or UNMEASURED),
             str(envelope.get("config_hash") or UNMEASURED),
             str(envelope.get("content_hash") or UNMEASURED),
             str(envelope.get("created_at") or ""),
             str(envelope.get("valid_until") or UNMEASURED),
             int(envelope.get("producer_generation") or 1),
             ",".join(str(x) for x in (envelope.get("input_artifact_ids") or []))))
        conn.commit()
    except sqlite3.Error:
        return False
    finally:
        with contextlib.suppress(sqlite3.Error):
            conn.close()
    return True


def record_ack(row: Mapping[str, Any], path: Path | None = None) -> bool:
    conn = connect(path)
    if conn is None:
        return False
    try:
        conn.execute(
            "INSERT OR REPLACE INTO lineage_acks (consumer_component_id, consumed_artifact_id, "
            "consumer_run_id, producer_run_id, epoch_id, consumed_at) VALUES (?,?,?,?,?,?)",
            (str(row.get("consumer_component_id") or ""),
             str(row.get("consumed_artifact_id") or ""),
             str(row.get("consumer_run_id") or UNMEASURED),
             str(row.get("producer_run_id") or UNMEASURED),
             str(row.get("epoch_id") or UNMEASURED),
             str(row.get("consumed_at") or "")))
        conn.commit()
    except sqlite3.Error:
        return False
    finally:
        with contextlib.suppress(sqlite3.Error):
            conn.close()
    return True


def _rows(conn: sqlite3.Connection, sql: str, args: Sequence[Any]) -> list[dict[str, Any]]:
    try:
        return [dict(r) for r in conn.execute(sql, tuple(args))]
    except sqlite3.Error:
        return []


def latest_artifact(artifact_id: str, path: Path | None = None) -> dict[str, Any] | None:
    conn = connect(path)
    if conn is None:
        return None
    try:
        # rowid breaks the tie: two runs stamped inside the same second are ordered by INSERT,
        # so the latest writer is the latest writer and not whichever row sqlite met first.
        rows = _rows(conn, "SELECT * FROM lineage_artifacts WHERE artifact_id = ? "
                           "ORDER BY created_at DESC, rowid DESC LIMIT 1", (artifact_id,))
    finally:
        with contextlib.suppress(sqlite3.Error):
            conn.close()
    return rows[0] if rows else None


def acks_of(artifact_id: str, consumer: str | None = None,
            path: Path | None = None) -> list[dict[str, Any]]:
    conn = connect(path)
    if conn is None:
        return []
    try:
        if consumer is None:
            return _rows(conn, "SELECT * FROM lineage_acks WHERE consumed_artifact_id = ? "
                               "ORDER BY consumed_at DESC", (artifact_id,))
        return _rows(conn, "SELECT * FROM lineage_acks WHERE consumed_artifact_id = ? "
                           "AND consumer_component_id = ? ORDER BY consumed_at DESC",
                     (artifact_id, consumer))
    finally:
        with contextlib.suppress(sqlite3.Error):
            conn.close()


def _lease_valid(artifact_row: Mapping[str, Any], now: datetime) -> bool | None:
    until = str(artifact_row.get("valid_until") or "")
    if not until or until == UNMEASURED:
        return None
    try:
        t = datetime.fromisoformat(until)
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    return now <= t


def observe(edge: Edge, now: datetime | None = None,
            path: Path | None = None) -> dict[str, Any]:
    """The verdict for one edge. OBSERVED is the only value that counts as wired.

    OBSERVED         producer run recorded, lease valid, consumer acked THAT run
    ACK_WEAK         the consumer acked the artifact but not the run under judgement
    UNACKED          the producer wrote it and no consumer has ever said they read it
    LEASE_EXPIRED    it was produced and consumed, and the evidence is out of date
    UNPRODUCED       no lineage row: nothing has ever claimed authorship of this artifact
    """
    t = now or datetime.now(tz=UTC)
    art = latest_artifact(edge.artifact, path)
    if art is None:
        return {"edge": edge.edge_id, "artifact": edge.artifact, "stage": edge.stage,
                "state": "UNPRODUCED", "observed": False,
                "why": (f"no lineage row for {edge.artifact}: {edge.producer} has never stamped "
                        f"an envelope on it, so nothing can prove it produced it")}
    if str(art.get("producer_component_id")) != edge.producer:
        return {"edge": edge.edge_id, "artifact": edge.artifact, "stage": edge.stage,
                "state": "WRONG_PRODUCER", "observed": False,
                "producer_seen": art.get("producer_component_id"),
                "why": (f"{edge.artifact} was last written by "
                        f"{art.get('producer_component_id')}, not {edge.producer}: two "
                        f"components hold write authority over one artifact")}
    lease = _lease_valid(art, t)
    rows = acks_of(edge.artifact, edge.consumer, path)
    exact = [r for r in rows if str(r.get("producer_run_id")) == str(art.get("producer_run_id"))]
    base = {"edge": edge.edge_id, "artifact": edge.artifact, "stage": edge.stage,
            "producer_run_id": art.get("producer_run_id"), "epoch_id": art.get("epoch_id"),
            "lease_valid": lease, "acks": len(rows), "acks_of_this_run": len(exact)}
    if not rows:
        return {**base, "state": "UNACKED", "observed": False,
                "why": (f"{edge.consumer} has never acknowledged {edge.artifact}: the output is "
                        f"produced and unconsumed, which is unwired by the one definition")}
    if lease is False:
        return {**base, "state": "LEASE_EXPIRED", "observed": False,
                "why": f"{edge.artifact} was consumed, but its lease expired at "
                       f"{art.get('valid_until')}"}
    if lease is None:
        return {**base, "state": "LEASE_UNMEASURED", "observed": False,
                "why": f"{edge.artifact} carries no TTL, so its freshness is UNMEASURED"}
    if not exact:
        return {**base, "state": "ACK_WEAK", "observed": False,
                "why": (f"{edge.consumer} acknowledged {edge.artifact} but not run "
                        f"{art.get('producer_run_id')}: proof it read a file with that name, "
                        f"not proof it read this run")}
    return {**base, "state": "OBSERVED", "observed": True, "why": ""}


def closed_loop(edges: Iterable[Edge] = REQUIRED_EDGES, now: datetime | None = None,
                path: Path | None = None) -> dict[str, Any]:
    """Every required edge, judged. `closed` is the one bit: all required edges OBSERVED."""
    rows = [observe(e, now, path) for e in edges]
    required = [(e, r) for e, r in zip(edges, rows, strict=False)
                if e.criticality == "required"]
    open_edges = [r["edge"] for _e, r in required if not r["observed"]]
    return {
        "at": (now or datetime.now(tz=UTC)).isoformat(timespec="seconds"),
        "edges": rows,
        "required": len(required),
        "observed": sum(1 for _e, r in required if r["observed"]),
        "open": open_edges,
        "closed": bool(required) and not open_edges,
        "rule": ("an edge is OBSERVED when the producer's run is recorded, its lease is still "
                 "valid, and the consumer acknowledged THAT RUN; a timestamp near another "
                 "timestamp is not lineage"),
    }
