"""NO ORGAN MATERIALISES THE WHOLE HYPOTHESIS GRAPH (2026-11-03, the item-23 class fix).

The box's graph is 4.4 GB (~5.7M rows). `Graph().rows()`, `.current()` and `.snapshot()` parse and
keep every row, which Desk health measured at ~11 min on the trading box -- longer than the
240-720 s leg cap of every organ that called them, so each was killed before it wrote:
`descendants` (1,833 TIMEOUTs), `graveyard_resurrection` (1,934), and thirteen more readers were
ported in the same change. Read what you need instead:

  hg.current_fates(path)                 id -> fate, by pattern, no rows
  hg.latest_rows(fates, path, limit)     full rows of the nodes whose present fate is in `fates`
  hg.iter_fields(fields, path)           every row, projected to the named fields, streamed
  hg.latest_fields(fields, path)         `current()` projected to the named fields
  Graph(path).buried()                   now read through `latest_rows`

A call this scan cannot see past (an attribute chain, a graph passed in) is out of its reach and
is not claimed. An organ that genuinely needs every full row goes in ALLOWED with the reason.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNED = ("desks/mt5/research", "desks/mt5/side_channels", "desks/mt5/mt5desk", "libs",
           "scripts", "ops")
WHOLE = frozenset({"rows", "current", "snapshot"})
#: path -> why it may read the whole graph. Keep it short; every entry is a cost on the box.
ALLOWED: dict[str, str] = {
    "libs/research/hypothesis_graph.py": "the graph's own reader",
    "scripts/backfill_hypothesis_graph.py": "a hand-run one-off backfill on no clock; it rewrites "
                                            "rows and needs every current row in full",
}


def _is_graph_ctor(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    f = node.func
    return (isinstance(f, ast.Name) and f.id == "Graph") or (
        isinstance(f, ast.Attribute) and f.attr == "Graph")


def whole_graph_reads(tree: ast.AST) -> list[int]:
    bound: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and _is_graph_ctor(n.value):
            bound.update(t.id for t in n.targets if isinstance(t, ast.Name))
    hits: list[int] = []
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr in WHOLE):
            continue
        recv = n.func.value
        if _is_graph_ctor(recv) or (isinstance(recv, ast.Name) and recv.id in bound):
            hits.append(n.lineno)
    return hits


def test_no_organ_reads_the_whole_hypothesis_graph() -> None:
    found: list[str] = []
    for top in SCANNED:
        for p in sorted((ROOT / top).rglob("*.py")):
            rel = p.relative_to(ROOT).as_posix()
            if "/tests/" in f"/{rel}" or rel in ALLOWED:
                continue
            try:
                tree = ast.parse(p.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            found += [f"{rel}:{ln}" for ln in whole_graph_reads(tree)]
    assert not found, ("whole-graph reads (Graph().rows/current/snapshot) in an organ -- use "
                       "current_fates / latest_rows / iter_fields / latest_fields: "
                       + ", ".join(found))


def test_the_scan_sees_the_shapes_it_claims() -> None:
    src = ("from libs.research.hypothesis_graph import Graph\n"
           "a = Graph().rows()\n"
           "g = Graph(p)\n"
           "b = g.current()\n"
           "import libs.research.hypothesis_graph as hg\n"
           "c = hg.Graph().snapshot()\n"
           "d = Graph().buried()\n")
    assert whole_graph_reads(ast.parse(src)) == [2, 4, 6]
