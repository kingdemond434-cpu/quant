#!/usr/bin/env python3
"""Join the gate-verdict ledger to the hypothesis graph, once, for the rows written before
`graph_id` existed.

    python scripts/backfill_verdict_graph_ids.py --dry-run   # measure, write nothing
    python scripts/backfill_verdict_graph_ids.py             # write the map

TWO NAMES FOR ONE CELL. `desks/mt5/data/hypotheses/gate_verdict_ledger.jsonl` names the judged
cell `EURAUD.overnight_gap_decay.p=<sha of params>` (`frontier_identity.cell_id`), while
`desks/mt5/data/hypothesis_graph.jsonl` names the same rule `f668ed18...`
(`hypothesis_graph.node_id` over symbol/family/params). Nothing joined them, so
`libs/moat/registry.sync_from_desk` recorded a trial under one id and the candidate it judged
under the other: the provenance DAG had trials hanging off cells that exist in no graph.

THIS SCRIPT REWRITES NOTHING. It reads both ledgers and writes ONE new artifact,
`desks/mt5/data/hypotheses/gate_verdict_graph_ids.json`, which `registry.graph_id_map` reads as
a fallback for rows that carry no `graph_id` of their own. The verdict ledger, the graph and the
verdict index are untouched -- an append-only record is not edited in place to add a field.

THREE WAYS A CELL RESOLVES, and a cell resolves by exactly one of them:

    graph_row     the graph holds a row whose own `cell_id` is this string -- the authoritative
                  answer, because it is the id the graph actually wrote
    empty_params  the params digest is the sha of `{}`, so the params ARE {} and the node id is
                  computable from the cell string alone
    rr_wb         the legacy `rr=2.0_wb=8` short form spells its whole parameter set out

Everything else is UNRESOLVED and NAMED (L1.28a): a cell whose params are a 16-character digest
of a dict nobody kept cannot be joined, and reporting it as a zero would be a lie. The two
direct forms are cross-checked against the graph wherever both answer; a disagreement is
reported and the graph's answer wins.

KNOWN LIMIT, inherited from `node_id` and stated rather than hidden: a cell whose CHART rides on
the row instead of in `params` shares a node id with the H1 cell of the same parameters, so the
`@M5`/`@D1` suffix is dropped when parsing. Two charts of one rule therefore map to one graph
node -- which is what the graph itself did when it recorded them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "desks" / "mt5"))

from libs.research.hypothesis_graph import node_id  # noqa: E402

DESK = ROOT / "desks" / "mt5"
GRAPH = DESK / "data" / "hypothesis_graph.jsonl"
LEDGER = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
OUT = DESK / "data" / "hypotheses" / "gate_verdict_graph_ids.json"

#: `cell_id`'s digest of an EMPTY parameter set. The one digest that can be inverted.
EMPTY_PARAMS_DIGEST = hashlib.sha256(
    json.dumps({}, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()[:16]

#: Unresolved cells named in the artifact. The COUNT is exact; the list is bounded, because a
#: file nobody can open is not evidence.
MAX_NAMED = 200


def cell_id_of(symbol: Any, family: Any, params: dict[str, Any]) -> str:
    """`frontier_identity.cell_id` for a graph row. Imported lazily so this script runs on a box
    with no MT5 desk on the path; the formula is the desk's, not this file's."""
    from research.frontier_identity import cell_id
    return str(cell_id({"sym": symbol, "family": family, "params": params}))


def _num(text: str) -> Any:
    """`2.0` -> 2.0, `8` -> 8, anything else unchanged: the legacy short form's own spelling."""
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def parse_cell(cell: str) -> tuple[str, str]:
    """(graph node id, method) for a cell whose SPEC is recoverable from its own string.

    Returns ("", "") when it is not -- which is most of them, and is the measurement.
    """
    parts = str(cell or "").split(".", 2)
    if len(parts) != 3:
        return "", ""
    sym, family, tail = parts
    sym = sym.split("@", 1)[0]          # see KNOWN LIMIT in the module docstring
    if not sym or not family:
        return "", ""
    if tail == f"p={EMPTY_PARAMS_DIGEST}":
        return node_id(sym, family, {}), "empty_params"
    if tail.startswith("rr=") and "_wb=" in tail:
        rr, _, wb = tail[3:].partition("_wb=")
        return node_id(sym, family, {"rr": _num(rr), "wait_bars": _num(wb)}), "rr_wb"
    return "", ""


def graph_index(path: Path = GRAPH) -> tuple[dict[str, str], int]:
    """(cell id -> node id, rows read). Streamed: the live ledger is 18 MB on this box.

    FIRST WRITER WINS, because the graph is append-only and the same cell is re-recorded on
    every fate change: the earliest row holds the id every later row repeats.
    """
    index: dict[str, str] = {}
    rows = 0
    if not path.exists():
        return index, 0
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not isinstance(row, dict):
                continue
            rows += 1
            nid = str(row.get("id") or "")
            params = row.get("params")
            if not nid or not isinstance(params, dict):
                continue
            try:
                cid = cell_id_of(row.get("symbol"), row.get("family"), params)
            except (KeyError, TypeError, ValueError):
                continue
            index.setdefault(cid, nid)
    return index, rows


def ledger_cells(path: Path = LEDGER) -> tuple[list[str], int]:
    """(distinct cells named by the verdict ledger, rows read)."""
    cells: dict[str, None] = {}
    rows = 0
    if not path.exists():
        return [], 0
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not isinstance(row, dict):
                continue
            rows += 1
            cell = str(row.get("cell") or "")
            if cell:
                cells.setdefault(cell, None)
    return list(cells), rows


def build(graph: Path = GRAPH, ledger: Path = LEDGER) -> dict[str, Any]:
    """The whole measurement: the map, how each cell resolved, and what could not be resolved."""
    index, graph_rows = graph_index(graph)
    cells, ledger_rows = ledger_cells(ledger)
    ids: dict[str, str] = {}
    how: Counter[str] = Counter()
    unresolved: list[str] = []
    disagreements: list[dict[str, str]] = []
    for cell in sorted(cells):
        from_graph = index.get(cell, "")
        parsed, method = parse_cell(cell)
        if from_graph:
            ids[cell] = from_graph
            how["graph_row"] += 1
            if parsed and parsed != from_graph and len(disagreements) < MAX_NAMED:
                disagreements.append({"cell": cell, "graph": from_graph, "parsed": parsed})
        elif parsed:
            ids[cell] = parsed
            how[method] += 1
        else:
            how["UNRESOLVED"] += 1
            if len(unresolved) < MAX_NAMED:
                unresolved.append(cell)
    return {
        "generated_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "rule": "one cell, one id: the verdict ledger's cell string joined to the hypothesis "
                "graph's node id, so a trial can name the candidate it judged",
        "graph_rows_read": graph_rows,
        "graph_cells_indexed": len(index),
        "ledger_rows_read": ledger_rows,
        "n_cells": len(cells),
        "n_resolved": len(ids),
        "n_unresolved": how["UNRESOLVED"],
        "by_method": dict(sorted(how.items())),
        # UNMEASURED BY NAME, not by silence: these cells hold a params digest whose dict is not
        # in the graph, so nothing on this box can say which hypothesis they tested.
        "unresolved_note": "UNMEASURED: the cell's params are a digest and no graph row carries "
                           "them; the cell keeps its own id in the registry, joined to nothing",
        "unresolved_named": unresolved,
        "unresolved_named_capped_at": MAX_NAMED,
        "direct_parse_disagreements": disagreements,
        "graph_ids": ids,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="measure and print, write nothing")
    ap.add_argument("--graph", type=Path, default=GRAPH)
    ap.add_argument("--ledger", type=Path, default=LEDGER)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    doc = build(a.graph, a.ledger)
    summary = {k: v for k, v in doc.items() if k not in ("graph_ids", "unresolved_named",
                                                         "direct_parse_disagreements")}
    summary["unresolved_sample"] = doc["unresolved_named"][:5]
    summary["n_direct_parse_disagreements"] = len(doc["direct_parse_disagreements"])
    print(json.dumps(summary, indent=1))
    if a.dry_run:
        print("DRY RUN: nothing written")
        return 0
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=1, sort_keys=False), encoding="utf-8")
    print(f"wrote {a.out} ({doc['n_resolved']} of {doc['n_cells']} cell(s) joined)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
