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


def _symbol_of(row: dict) -> str | None:
    cell = row.get("canonical_cell")
    if isinstance(cell, str) and "." in cell:
        return cell.split(".")[0].upper()
    return None


def backfill(write: bool) -> dict:
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
        gen = str(r.get("geneology_id") or r.get("source") or "research_queue")
        node = Node(symbol=sym, family=str(r.get("family")), params=dict(r.get("params") or {}),
                    source=gen.split(":")[0], fate=fate,
                    parent=hashlib.sha256(gen.encode()).hexdigest()[:16],
                    why=f"research_queue {r.get('id')}: canonical verdict "
                        f"{r.get('canonical_verdict')}",
                    gates={"canonical_report": {"path": r.get("canonical_report")}},
                    at=str(r.get("reconciled_at") or r.get("created_at") or ""))
        cur = current.get(node.id)
        if cur and cur.get("fate") == fate:
            counts["already"] += 1
            continue
        counts[fate] += 1
        by_source[node.source] += 1
        if write:
            graph.append(node)
    return {"rows": len(rows), "counts": dict(counts), "by_source": dict(by_source),
            "wrote": write, "graph_census": (graph.census() if write else None)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    d = backfill(a.write)
    verb = "recorded" if a.write else "would record"
    print(f"hypothesis graph backfill: {d['rows']} queue rows; {verb} "
          f"{d['counts'].get(FAILED, 0)} FAILED + {d['counts'].get(CERTIFIED, 0)} CERTIFIED; "
          f"{d['counts'].get('already', 0)} already in graph; "
          f"{d['counts'].get('unjudged', 0)} unjudged; {d['counts'].get('no_symbol', 0)} "
          "without a canonical cell (skipped)")
    for s, n in sorted(d["by_source"].items(), key=lambda kv: -kv[1])[:10]:
        print(f"  {s:24s} {n}")
    if d["graph_census"]:
        c = d["graph_census"]
        print(f"graph now: {c['nodes']} nodes, {c['buried_regions']} buried regions, "
              f"by fate {c['by_fate']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
