"""THE EXPERIMENT MEMORY GRAPH -- not result storage. What has never been tried, as a query.

THE PRINCIPAL (RD-Agent closure, item 16): an experiment memory graph holding parents, children,
failed assumptions, model, data, representation, regime and verdict per experiment, answering
*"what has never been tried from this surviving mechanism?"* as a FIRST-CLASS QUERY that the
proposers read.

WHY A GRAPH AND NOT A RESULTS TABLE. The desk already stores results: `research_candidates` carries
verdicts, `trials_ledger` carries the charged trials, the shadow states carry forward evidence.
What none of them can answer is the question above, because a result table is indexed by what WAS
run. The interesting quantity is the COMPLEMENT: from a mechanism that survived on EURUSD at H1 in
a high-volatility regime, the desk has never tried it at M15, never on AUDJPY, never with a rank
representation, never under a trending regime -- and the proposer that would have suggested those
has no way to know which of them are new. An adjacent-possible query needs the graph.

IT LIVES IN THE REGISTRY, NEVER BESIDE IT. The node table is `experiments` (declared in
`libs.moat.registry.MOAT_TABLES`, created by the registry's own `_evolve`); the edges are the
registry's `provenance` DAG with the node kind `experiment`; the verdicts are read back from
`research_candidates` and `trials_ledger`. This module adds no store of its own -- if it needs a
column it is added to the registry's table through the EXTENSIONS mechanism.

THE AXIS DOMAINS ARE MEASURED, NOT INVENTED. `never_tried` enumerates over the axis values THIS
DESK HAS ACTUALLY USED somewhere in the graph (every model it has run, every representation it has
built, every chart, regime, session and horizon it has tested), because an untried combination of
values the desk cannot produce is not an opportunity, it is a typo. An axis with no observed values
reports UNMEASURED and is dropped from the product rather than silently contributing one blank.

    from libs.research import experiment_graph as G
    G.upsert(spec)                                  # a node, and its lineage edges
    G.record_verdict(exp_id, "SURVIVED", ...)       # verdict + failed assumptions
    G.never_tried(mechanism="carry_unwind", axes=("model", "chart"))   # the frontier query
    G.refresh()                                     # statuses and forward/live numbers, from the
                                                    # registry's own rows -- never re-measured
"""
from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from itertools import product
from typing import Any

from libs.moat import registry
from libs.research.experiment_spec import ExperimentSpec

#: The axes an experiment is placed on. These are the columns `never_tried` takes its product
#: over; each one is a real column of the `experiments` table so the query is a GROUP BY.
AXES: tuple[str, ...] = ("model", "representation", "chart", "horizon", "regime", "session",
                         "symbol", "target")

#: Which column answers an axis. `symbol` is the first symbol of the spec's instrument list,
#: stored denormalised in `symbols_json`, so it is handled by the reader rather than SQL.
_AXIS_COLUMN: dict[str, str] = {a: a for a in AXES if a != "symbol"}

#: A verdict is one of these. UNJUDGED is a state, not an absence: an experiment that has never
#: been judged is a different thing from one judged and rejected, and the frontier query counts
#: only JUDGED work as "tried" when asked to.
VERDICTS: tuple[str, ...] = ("UNJUDGED", "SURVIVED", "REJECTED", "BLOCKED", "UNMEASURED")


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _j(obj: Any) -> str | None:
    return None if obj is None else json.dumps(obj, sort_keys=True, default=str)


def _loads(value: Any) -> Any:
    if value in (None, "", "None"):
        return None
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(str(value))
    except ValueError:
        return value


def _rows(cur: sqlite3.Cursor) -> list[dict[str, Any]]:
    return [dict(r) for r in cur.fetchall()]


# ------------------------------------------------------------------------------------ writers
def upsert(spec: ExperimentSpec, *, candidate_id: str = "", mechanism_id: str = "",
           conn: sqlite3.Connection | None = None) -> tuple[str, bool]:
    """Write one experiment node and its lineage edges. Returns `(experiment_id, created)`.

    An experiment already present is UPDATED in place (the spec may have been enriched with a
    representation or a snapshot since), never duplicated: identity is `experiment_id`, and the
    content identity `spec_hash` rides beside it so two ids carrying the same content can be
    found by the never-tried query without either being deleted.
    """
    c = conn or registry.connect()
    try:
        snap = spec.data_snapshot.resolved()
        rec: dict[str, Any] = {
            "experiment_id": spec.experiment_id, "updated_at": _now(), "kind": spec.kind,
            "spec_hash": spec.spec_hash(), "family": spec.family,
            "symbols_json": _j(list(spec.symbols)), "model": spec.model,
            "representation": spec.representation, "features_json": _j(list(spec.features)),
            "target": spec.target, "horizon": spec.horizon, "chart": spec.chart,
            "regime": spec.regime, "session": spec.session, "mechanism": spec.mechanism,
            "mechanism_id": mechanism_id or _mechanism_key(spec), "method": spec.method,
            "source_id": spec.source, "generator": spec.generator, "origin": spec.origin,
            "discovery_id": spec.discovery_id, "candidate_id": candidate_id,
            "parents_json": _j(list(spec.parents)), "snapshot_hash": snap.snapshot_hash,
            "snapshot_vintage": snap.vintage, "pit_status": snap.pit_status,
            "falsifier": spec.falsifier, "trial_family": spec.trial_family,
            "costs_json": _j(dict(spec.costs)), "novelty_json": _j(dict(spec.novelty_axes)),
            "status": spec.status, "spec_json": _j(spec.to_dict()),
        }
        existing = c.execute("SELECT experiment_id FROM experiments WHERE experiment_id=?",
                             (spec.experiment_id,)).fetchone()
        if existing is not None:
            c.execute("UPDATE experiments SET "                      # noqa: S608 -- the
                      # column names are this module's own literals, never caller input; the
                      # values are bound.
                      + ", ".join(f"{k}=?" for k in rec) + " WHERE experiment_id=?",
                      [*rec.values(), spec.experiment_id])
            created = False
        else:
            rec["created_at"] = _now()
            rec["verdict"] = "UNJUDGED"
            keys = list(rec)
            c.execute(f'INSERT INTO experiments({",".join(keys)}) '
                      f'VALUES({",".join("?" * len(keys))})', [rec[k] for k in keys])
            created = True
        for p in spec.parents:
            registry.link("experiment", p, "experiment", spec.experiment_id, "derived", conn=c)
        if spec.discovery_id:
            registry.link("discovery", spec.discovery_id, "experiment", spec.experiment_id,
                          "compiled", conn=c)
        if spec.source:
            registry.link("source", spec.source, "experiment", spec.experiment_id, "suggested",
                          conn=c)
        if candidate_id:
            registry.link("experiment", spec.experiment_id, "cell", candidate_id, "compiled",
                          conn=c)
        c.commit()
        return spec.experiment_id, created
    finally:
        if conn is None:
            c.close()


def record_verdict(experiment_id: str, verdict: str, *, failed_assumptions: Sequence[str] = (),
                   forward_r: float | None = None, live_delta_elogw: float | None = None,
                   compute_s: float | None = None, status: str = "",
                   conn: sqlite3.Connection | None = None) -> bool:
    """A completed experiment's verdict, and the ASSUMPTIONS that failed with it.

    The failed assumptions are the part no result table holds and the part the next proposer most
    needs: "this mechanism does not survive costs at M15" is a different lesson from "this
    mechanism does not exist", and only the first one leaves H1 worth trying.
    """
    if verdict not in VERDICTS:
        raise ValueError(f"verdict {verdict!r} is not one of {VERDICTS}")
    c = conn or registry.connect()
    try:
        sets: dict[str, Any] = {"verdict": verdict, "verdict_at": _now(), "updated_at": _now(),
                                "failed_assumptions_json": _j(list(failed_assumptions))}
        if status:
            sets["status"] = status
        for k, v in (("forward_r", forward_r), ("live_delta_elogw", live_delta_elogw),
                     ("compute_s", compute_s)):
            if v is not None:
                sets[k] = float(v)
        cur = c.execute("UPDATE experiments SET "                    # noqa: S608 -- keys are
                        # this module's own literals; every value is bound.
                        + ", ".join(f"{k}=?" for k in sets)
                        + " WHERE experiment_id=?", [*sets.values(), experiment_id])
        c.commit()
        return cur.rowcount > 0
    finally:
        if conn is None:
            c.close()


def _mechanism_key(spec: ExperimentSpec) -> str:
    """The grouping key for "this mechanism". The mechanism sentence when there is one, else the
    family: the question "what has never been tried from this surviving mechanism" must still be
    answerable for a row whose mechanism was never written in prose."""
    return (spec.mechanism or spec.family or spec.kind).strip()[:160]


# ------------------------------------------------------------------------------------ readers
def node(experiment_id: str, *, conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
    c = conn or registry.connect()
    try:
        row = c.execute("SELECT * FROM experiments WHERE experiment_id=?",
                        (experiment_id,)).fetchone()
        return None if row is None else dict(row)
    finally:
        if conn is None:
            c.close()


def experiments(*, mechanism: str = "", status: str = "", verdict: str = "", kind: str = "",
                limit: int = 5000,
                conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    c = conn or registry.connect()
    try:
        q = "SELECT * FROM experiments WHERE 1=1"
        args: list[Any] = []
        for col, val in (("mechanism_id", mechanism), ("status", status),
                         ("verdict", verdict), ("kind", kind)):
            if val:
                q += f" AND {col}=?"
                args.append(val)
        q += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)
        return _rows(c.execute(q, args))
    finally:
        if conn is None:
            c.close()


def parents_of(experiment_id: str, *,
               conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    return registry.provenance_of("experiment", experiment_id, depth=6, conn=conn)


def children_of(experiment_id: str, *,
                conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    return registry.descendants_of("experiment", experiment_id, depth=6, conn=conn)


def _axis_values(rows: Iterable[Mapping[str, Any]], axis: str) -> list[str]:
    seen: dict[str, int] = {}
    for r in rows:
        if axis == "symbol":
            for s in (_loads(r.get("symbols_json")) or []):
                if str(s):
                    seen[str(s)] = seen.get(str(s), 0) + 1
            continue
        v = r.get(_AXIS_COLUMN.get(axis, axis))
        if v not in (None, "", "None"):
            seen[str(v)] = seen.get(str(v), 0) + 1
    return sorted(seen, key=lambda k: (-seen[k], k))


def _tried_key(row: Mapping[str, Any], axes: Sequence[str]) -> list[tuple[str, ...]]:
    """The axis tuples this row occupies. A row with several symbols occupies several cells."""
    per_axis: list[list[str]] = []
    for a in axes:
        if a == "symbol":
            syms = [str(s) for s in (_loads(row.get("symbols_json")) or []) if str(s)]
            per_axis.append(syms or [""])
        else:
            per_axis.append([str(row.get(_AXIS_COLUMN.get(a, a)) or "")])
    return [tuple(t) for t in product(*per_axis)]


def never_tried(*, mechanism: str = "", axes: Sequence[str] = ("model", "chart", "regime"),
                only_judged: bool = False, limit: int = 200,
                domain_from: str = "graph",
                conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """THE FIRST-CLASS QUERY: what has this desk never tried from this mechanism?

    `mechanism` is a mechanism key (`mechanism_id` on the node, which is the mechanism sentence or
    the family). `axes` names the product to enumerate. `domain_from` says where the axis values
    come from: `graph` (every value the desk has used anywhere -- the adjacent possible) or
    `mechanism` (only values this mechanism itself has used -- a narrower, cheaper frontier).

    Returns the untried cells with the tried ones counted beside them, plus an `unmeasured` list
    naming any axis with no observed values -- which is a finding, not a zero: an axis the desk
    has never recorded a single value for cannot be enumerated and is DROPPED from the product
    rather than contributing a blank that would make every cell look untried.
    """
    bad = [a for a in axes if a not in AXES]
    if bad:
        raise ValueError(f"unknown axes {bad}; known axes are {AXES}")
    c = conn or registry.connect()
    try:
        all_rows = _rows(c.execute("SELECT * FROM experiments LIMIT 20000"))
        mine = [r for r in all_rows if not mechanism or str(r.get("mechanism_id")) == mechanism]
        if only_judged:
            mine = [r for r in mine if str(r.get("verdict") or "UNJUDGED") != "UNJUDGED"]
        domain_rows = mine if domain_from == "mechanism" else all_rows
        domains: dict[str, list[str]] = {}
        unmeasured: list[str] = []
        for a in axes:
            vals = _axis_values(domain_rows, a)
            if vals:
                domains[a] = vals
            else:
                unmeasured.append(a)
        live_axes = [a for a in axes if a in domains]
        tried: dict[tuple[str, ...], int] = {}
        for r in mine:
            for key in _tried_key(r, live_axes):
                tried[key] = tried.get(key, 0) + 1
        untried: list[dict[str, str]] = []
        n_cells = 0
        for combo in product(*(domains[a] for a in live_axes)) if live_axes else ():
            n_cells += 1
            if combo not in tried and len(untried) < limit:
                untried.append(dict(zip(live_axes, combo, strict=True)))
        survivors = sum(1 for r in mine if str(r.get("verdict")) == "SURVIVED")
        return {
            "mechanism": mechanism or "(every mechanism)",
            "axes": list(live_axes),
            "unmeasured_axes": unmeasured,
            "domain_from": domain_from,
            "n_experiments": len(mine), "n_survivors": survivors,
            "n_cells": n_cells, "n_tried": len(tried),
            "n_untried": max(0, n_cells - len(tried)),
            "coverage": None if n_cells == 0 else round(len(tried) / n_cells, 6),
            "untried": untried,
            "truncated": max(0, (n_cells - len(tried)) - len(untried)),
            "basis": ("axis domains are the values this desk has ACTUALLY used; an axis with no "
                      "observed value is reported unmeasured and dropped from the product"),
        }
    finally:
        if conn is None:
            c.close()


def surviving_mechanisms(*, limit: int = 50,
                         conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    """Mechanisms with at least one SURVIVED experiment, newest evidence first. This is what a
    proposer iterates over before calling `never_tried` on each."""
    c = conn or registry.connect()
    try:
        return _rows(c.execute(
            "SELECT mechanism_id, COUNT(*) AS n, "
            " SUM(CASE WHEN verdict='SURVIVED' THEN 1 ELSE 0 END) AS survivors, "
            " MAX(verdict_at) AS last_verdict_at "
            "FROM experiments WHERE mechanism_id IS NOT NULL AND mechanism_id<>'' "
            "GROUP BY mechanism_id HAVING survivors > 0 "
            "ORDER BY survivors DESC, last_verdict_at DESC LIMIT ?", (limit,)))
    finally:
        if conn is None:
            c.close()


def failed_assumptions(*, mechanism: str = "", limit: int = 200,
                       conn: sqlite3.Connection | None = None) -> dict[str, int]:
    """What has failed, and how often -- the negative knowledge the proposers must not re-spend."""
    out: dict[str, int] = {}
    for r in experiments(mechanism=mechanism, limit=limit, conn=conn):
        for a in (_loads(r.get("failed_assumptions_json")) or []):
            out[str(a)] = out.get(str(a), 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


# ------------------------------------------------------------------------------------ refresh
#: How a registry candidate status maps onto an experiment verdict. `donated` and `queued` are
#: not verdicts: an experiment waiting in the queue is UNJUDGED, which is what makes the
#: never-tried query honest.
_VERDICT_OF_STATUS: dict[str, str] = {
    "survived": "SURVIVED", "rejected": "REJECTED", "judged": "JUDGED",
    "blocked": "BLOCKED", "live": "SURVIVED", "forward": "SURVIVED",
}


def refresh(*, limit: int = 20000, budget_s: float | None = None,
            conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Pull each experiment's status and verdict from the registry rows that OWN them.

    Nothing is re-measured here: `research_candidates.status`, `survived` and `rejection_reason`
    are the gauntlet's own record, and the graph copies them onto the node so the frontier query
    does not need a join per cell. An experiment whose candidate has vanished keeps its last
    verdict and is counted in `orphans` -- a node with no cell is a real defect, not a zero.
    """
    c = conn or registry.connect()
    try:
        nodes = _rows(c.execute("SELECT experiment_id, candidate_id, verdict, status FROM "
                                "experiments LIMIT ?", (limit,)))
        updated = orphans = judged = survived = 0
        # A REFRESH THAT EATS THE WHOLE PASS IS THE TRUNCATED-JOB DEFECT. Measured on the first
        # live run: 2,056 nodes took the rest of a 150 s budget and the credit ledger, the prior
        # update and the funnel all read UNMEASURED. With a deadline the refresh reports how far
        # it got and the four stages that LEARN from it still run.
        t0 = time.monotonic()
        stopped = False
        for i, n in enumerate(nodes):
            if budget_s is not None and time.monotonic() - t0 > budget_s:
                stopped = True
                nodes = nodes[:i]
                break
            cid = str(n.get("candidate_id") or "")
            if not cid:
                orphans += 1
                continue
            row = c.execute("SELECT status, survived, rejection_reason, terminal_gate, "
                            "failure_class FROM research_candidates WHERE id=? OR donated_cell=?",
                            (cid, cid)).fetchone()
            if row is None:
                orphans += 1
                continue
            status = str(row["status"] or "")
            verdict = _VERDICT_OF_STATUS.get(status.lower(), "UNJUDGED")
            if int(row["survived"] or 0) == 1:
                verdict = "SURVIVED"
            elif row["rejection_reason"]:
                verdict = "REJECTED"
            if verdict == "JUDGED":
                verdict = "REJECTED" if row["rejection_reason"] else "UNJUDGED"
            fails: list[str] = []
            for key in ("rejection_reason", "terminal_gate", "failure_class"):
                v = row[key]
                if v:
                    fails.append(f"{key}:{v}")
            if verdict != str(n.get("verdict") or "UNJUDGED") or status != str(n.get("status")):
                c.execute("UPDATE experiments SET verdict=?, status=?, verdict_at=?, "
                          "failed_assumptions_json=?, updated_at=? WHERE experiment_id=?",
                          (verdict, status.upper() or str(n.get("status") or "PROPOSED"),
                           _now(), _j(fails), _now(), n["experiment_id"]))
                updated += 1
            judged += int(verdict != "UNJUDGED")
            survived += int(verdict == "SURVIVED")
        c.commit()
        return {"nodes": len(nodes), "updated": updated, "orphans": orphans,
                "judged": judged, "survived": survived, "budget_stopped": stopped,
                "status": "PARTIAL" if stopped else "OK"}
    finally:
        if conn is None:
            c.close()


def census(*, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """The graph in one dict: nodes, kinds, verdicts, edges and the axis domains it can search."""
    c = conn or registry.connect()
    try:
        n = int(c.execute("SELECT COUNT(*) AS n FROM experiments").fetchone()["n"])
        by_kind = {str(r["kind"] or "?"): int(r["n"]) for r in c.execute(
            "SELECT kind, COUNT(*) AS n FROM experiments GROUP BY kind")}
        by_verdict = {str(r["verdict"] or "UNJUDGED"): int(r["n"]) for r in c.execute(
            "SELECT verdict, COUNT(*) AS n FROM experiments GROUP BY verdict")}
        edges = int(c.execute("SELECT COUNT(*) AS n FROM provenance WHERE from_kind='experiment'"
                              " OR to_kind='experiment'").fetchone()["n"])
        rows = _rows(c.execute("SELECT * FROM experiments LIMIT 20000"))
        domains = {a: len(_axis_values(rows, a)) for a in AXES}
        return {"nodes": n, "by_kind": by_kind, "by_verdict": by_verdict, "edges": edges,
                "axis_domain_sizes": domains,
                "mechanisms": int(c.execute(
                    "SELECT COUNT(DISTINCT mechanism_id) AS n FROM experiments").fetchone()["n"])}
    finally:
        if conn is None:
            c.close()
