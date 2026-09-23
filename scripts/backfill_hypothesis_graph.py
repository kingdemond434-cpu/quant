#!/usr/bin/env python3
"""Load the desk's 47,150 judged hypotheses into the hypothesis graph as negative knowledge.

    python scripts/backfill_hypothesis_graph.py            # report what would be recorded
    python scripts/backfill_hypothesis_graph.py --write    # append to the graph ledger

`research_queue.json` carries every card the canonical gauntlet has judged: family, params, the
canonical cell (which names the symbol), the verdict, and the `geneology_id` that says which
miner or hunt produced it. The graph indexes the same facts by (symbol, family, parameter
region) so a proposer can ask "has the desk already buried this?" before spending a trial. This
moves the existing judgments in, once, idempotently: a node whose current fate in the graph
already matches is skipped, so the script can run after every reconcile without duplicating.

A card with no canonical cell has no symbol and is not recorded -- a region with no instrument
is not a region. Those are counted and reported, never guessed from the prose.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from libs.research.hypothesis_graph import CERTIFIED, FAILED, Graph, Node  # noqa: E402

QUEUE = ROOT / "desks" / "mt5" / "data" / "research_queue.json"
VERDICT_FATE = {"REJECTED": FAILED, "PASSED": CERTIFIED}


#: The gauntlet reports a queue row points at, loaded once each and indexed by cell.
_REPORT_CACHE: dict[str, dict[str, dict]] = {}


def _verdicts_by_cell(rel: str) -> dict[str, dict]:
    """`{cell: verdict}` from a canonical gauntlet report, or {} when it cannot be read.

    The report is the ONLY place the cause lives. A queue row carries the verdict word and a
    path; the gate that produced it -- and the message that gate wrote -- are in `verdicts[].
    stages`, keyed by the same `canonical_cell` the row names.
    """
    if rel in _REPORT_CACHE:
        return _REPORT_CACHE[rel]
    index: dict[str, dict] = {}
    try:
        doc = json.loads((ROOT / rel).read_text("utf-8"))
        for v in doc.get("verdicts") or []:
            if isinstance(v, dict) and v.get("cell"):
                index[str(v["cell"])] = v
    except (OSError, ValueError, TypeError):
        index = {}
    _REPORT_CACHE[rel] = index
    return index


def failure_cause(row: dict) -> tuple[str, dict]:
    """(why, gates) for one judged card: WHICH GATE said no, and what it said.

    WHY THIS EXISTS (2026-09-05). Every one of the graveyard's 30,208 FAILED rows carried the
    same sentence -- "research_queue ext-<id>: canonical verdict REJECTED" -- so the largest
    dataset this desk produces said only that something was tried and never what to try instead.
    `search_populations.graveyard_derived` reads exactly this field to choose a mutation axis
    (cost -> horizon, turnover -> state, leak -> lag, correlation -> residualisation, ...) and
    correctly yielded NOTHING from thirty thousand rows, because "REJECTED" names no cause and
    mutating on it would be mutating on noise wearing the word failure.

    The cause was never lost, only unfollowed: the row names its report and the report names the
    failing gate. This reads it. A row whose report cannot be found keeps the bare verdict AND
    says the cause was unrecoverable, so a silent absence never reads as a stated one.
    """
    rid, verdict = row.get("id"), row.get("canonical_verdict")
    cell = str(row.get("canonical_cell") or "")
    rel = str(row.get("canonical_report") or "")
    v = _verdicts_by_cell(rel).get(cell) if (rel and cell) else None
    if not isinstance(v, dict):
        return (f"research_queue {rid}: canonical verdict {verdict} "
                f"(cause unrecoverable: no row for {cell or '?'} in {rel or 'no report'})",
                {"canonical_report": {"path": rel}})
    stages = v.get("stages") if isinstance(v.get("stages"), dict) else {}
    failed = [(n, st) for n, st in stages.items()
              if isinstance(st, dict) and not st.get("passed", True)]
    if not failed:
        return (f"research_queue {rid}: canonical verdict {verdict} "
                f"(no gate is marked failed in {rel})",
                {"canonical_report": {"path": rel}, **stages})
    names = ", ".join(n for n, _ in failed[:3])
    msg = str(next((st.get("message") for _, st in failed if st.get("message")), "")).strip()
    why = f"research_queue {rid}: {verdict} at {names}"
    if msg:
        why += f" -- {msg[:160]}"
    return why, {"canonical_report": {"path": rel}, **stages}


def _symbol_of(row: dict) -> str | None:
    cell = row.get("canonical_cell")
    if isinstance(cell, str) and "." in cell:
        return cell.split(".")[0].upper()
    return None


#: A `why` that names no gate. The bare verdict sentence every pre-2026-09-05 row carries.
def cause_is_named(why: str) -> bool:
    """Does this `why` name the gate that said no, rather than only that something said no?

    `graveyard_derived` matches vocabulary in the reason to choose a mutation axis. "canonical
    verdict REJECTED" matches nothing by construction, which is why thirty thousand buried rows
    produced zero research. The marker is the verdict word followed by ` at <gate>`.
    """
    return " at " in str(why) and "canonical verdict" not in str(why)


def backfill(write: bool, rewrite_causes: bool = False) -> dict:
    rows = json.loads(QUEUE.read_text("utf-8"))
    rows = rows if isinstance(rows, list) else (rows.get("rows") or [])
    graph = Graph()
    current = graph.current()
    counts: Counter = Counter()
    by_source: Counter = Counter()
    for r in rows:
        if not isinstance(r, dict):
            continue
        fate = VERDICT_FATE.get(str(r.get("canonical_verdict")))
        sym = _symbol_of(r)
        if fate is None:
            counts["unjudged"] += 1
            continue
        if sym is None:
            counts["no_symbol"] += 1
            continue
        why, gates = failure_cause(r)
        counts["cause_named" if " at " in why else "cause_unrecoverable"] += 1
        gen = str(r.get("geneology_id") or r.get("source") or "research_queue")
        node = Node(symbol=sym, family=str(r.get("family")), params=dict(r.get("params") or {}),
                    source=gen.split(":")[0], fate=fate,
                    parent=hashlib.sha256(gen.encode()).hexdigest()[:16],
                    why=why, gates=gates,
                    at=str(r.get("reconciled_at") or r.get("created_at") or ""))
        cur = current.get(node.id)
        if cur and cur.get("fate") == fate:
            # THE REPAIR, AND ONLY WHERE IT IS AN IMPROVEMENT. A row already buried under the
            # bare verdict keeps that sentence forever otherwise, and the ledger is append-only,
            # so the correction is a new row whose `why` names the gate -- never an edit, never
            # a re-judgement. The fate is identical; only the reason gets better.
            if not (rewrite_causes and cause_is_named(why)
                    and not cause_is_named(cur.get("why", ""))):
                counts["already"] += 1
                continue
            counts["cause_repaired"] += 1
        counts[fate] += 1
        by_source[node.source] += 1
        if write:
            graph.append(node)
    # A ROW WHOSE FATE ALREADY MATCHES IS SKIPPED, so a re-run does not restate a cause onto a
    # row that already has one -- but a row buried under the bare verdict keeps it until the
    # graph is rebuilt. `--rewrite-causes` is the one-shot that repairs the existing 30,208.
    return {"rows": len(rows), "counts": dict(counts), "by_source": dict(by_source),
            "wrote": write, "graph_census": (graph.census() if write else None)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--rewrite-causes", action="store_true",
                    help="append a corrected row for every buried hypothesis whose reason names "
                         "no gate and whose cause is recoverable from its canonical report")
    a = ap.parse_args()
    d = backfill(a.write, rewrite_causes=a.rewrite_causes)
    verb = "recorded" if a.write else "would record"
    print(f"hypothesis graph backfill: {d['rows']} queue rows; {verb} "
          f"{d['counts'].get(FAILED, 0)} FAILED + {d['counts'].get(CERTIFIED, 0)} CERTIFIED; "
          f"{d['counts'].get('already', 0)} already in graph; "
          f"{d['counts'].get('unjudged', 0)} unjudged; {d['counts'].get('no_symbol', 0)} "
          "without a canonical cell (skipped)")
    c = d["counts"]
    print(f"  causes: {c.get('cause_named', 0)} named, "
          f"{c.get('cause_unrecoverable', 0)} unrecoverable"
          + (f", {c.get('cause_repaired', 0)} repaired" if c.get("cause_repaired") else ""))
    for s, n in sorted(d["by_source"].items(), key=lambda kv: -kv[1])[:10]:
        print(f"  {s:24s} {n}")
    if d["graph_census"]:
        c = d["graph_census"]
        print(f"graph now: {c['nodes']} nodes, {c['buried_regions']} buried regions, "
              f"by fate {c['by_fate']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
