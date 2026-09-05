"""Build the lineage DAG from the research store, so crossover has a graph to run on.

WHY THIS EXISTS (2026-09-04)

`lineage_dag.crossover_candidates` implements QuantaAlpha's trajectory crossover -- pair two
lineages whose FAILING STEPS differ, so each contributes the segment its own failure exonerated --
and it had NEVER BEEN CALLED. Not because it was wrong, but because nothing built the graph: the
`hypotheses` table that carries parentage and generation had zero rows until this session, so
`LineageDAG` had nothing to add.

ADD IN GENERATION ORDER, ALWAYS. `LineageDAG.add` raises KeyError when a parent is not already in
the graph, deliberately -- a node whose ancestry cannot be walked defeats fertility and credit
assignment. Rows come out of SQLite in insertion order, and a child can be recorded before its
parent, so this sorts by generation first and drops any orphan whose parent genuinely is not in
the store rather than fabricating a root for it.

THE FAILING STEP IS THE CROSSOVER SIGNAL, so it is read from the failures table rather than left
blank: a pair of lineages that failed at the SAME step has nothing to exchange.
"""
from __future__ import annotations

import json
from typing import Any


def build_dag() -> Any:
    """The descent graph as the store currently records it, plus a note on what was dropped."""
    from libs.research.lineage_dag import LineageDAG, Node
    from libs.research_os import store
    from libs.research_os.credit import STAGE_VALUE, _stage_for

    dag = LineageDAG()
    with store.connect() as conn:
        rows = conn.execute(
            "SELECT hypothesis_id, mechanism, coordinate, parent_ids, generation, spec "
            "FROM hypotheses ORDER BY generation ASC, id ASC").fetchall()
        steps = {str(r[0]): str(r[1] or "") for r in conn.execute(
            "SELECT hypothesis_id, next_action FROM failures ORDER BY id ASC").fetchall()}
        classes = {str(r[0]): str(r[1] or "") for r in conn.execute(
            "SELECT hypothesis_id, state FROM failures ORDER BY id ASC").fetchall()}

        added, dropped = 0, 0
        for hid, mech, coord, parents, gen, spec in rows:
            hid = str(hid)
            if hid in dag.nodes:
                continue                      # artifacts are immutable; first write wins
            try:
                pids = tuple(str(p) for p in json.loads(parents or "[]"))
            except (json.JSONDecodeError, TypeError):
                pids = ()
            if any(p not in dag.nodes for p in pids):
                dropped += 1
                continue
            try:
                spec_d = json.loads(spec or "{}")
            except (json.JSONDecodeError, TypeError):
                spec_d = {}
            stage, _cls, _adapter = _stage_for(hid, conn)
            dag.add(Node(
                artifact_id=hid, hypothesis_id=hid, parents=pids, generation=int(gen or 0),
                mechanism=str(mech or ""), coordinate=str(coord or ""),
                mutation_operation=str(spec_d.get("mutation") or ""),
                furthest_stage=stage,
                survived=STAGE_VALUE.get(stage, 0.0) >= STAGE_VALUE["FORWARD_SURVIVED"],
                failure_class=classes.get(hid, ""), failing_step=steps.get(hid, "")))
            added += 1
    return dag, {"nodes": added, "dropped_orphans": dropped}


def crossover(seed: int = 0, k: int = 5) -> dict[str, Any]:
    """QuantaAlpha trajectory crossover over the recorded lineage."""
    from libs.research.lineage_dag import crossover_candidates

    dag, stats = build_dag()
    if len(dag.nodes) < 2:
        return {"pairs": [], "n_pairs": 0, **stats,
                "why": "fewer than two lineages recorded -- crossover needs two to recombine"}
    pairs = crossover_candidates(dag, seed=seed, k=k)
    return {"pairs": pairs, "n_pairs": len(pairs), **stats,
            "why": ("pairs whose FAILING STEPS differ: each parent contributes the segment its "
                    "own failure exonerated. Children start at IDEA with no inherited standing.")}
