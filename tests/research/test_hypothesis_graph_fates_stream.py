"""current_fates is the streaming, rows-free twin of Graph.current() -- same answer, bounded
memory -- and one torn line no longer blanks the whole graph."""
from __future__ import annotations

import json
from pathlib import Path

from libs.research import hypothesis_graph as hg


def _ledger(tmp_path: Path) -> Path:
    rows = [{"id": "a", "region": "X", "fate": "BORN", "why": "has \"fate\": \"FAILED\" in prose"},
            {"id": "b", "region": "Y", "fate": "BORN", "params": {"k": 1}},
            {"id": "a", "region": "X", "fate": "FAILED"},
            {"id": "q\"uote", "fate": "CERTIFIED"},
            {"id": "c", "region": "Z"}]
    p = tmp_path / "hypothesis_graph.jsonl"
    body = "\n".join(json.dumps(r) for r in rows)
    p.write_text(body + '\n{"id": "torn", "fate": "BO\n\n', encoding="utf-8")
    return p


def test_fates_match_the_full_reader_row_for_row(tmp_path: Path) -> None:
    p = _ledger(tmp_path)
    full = {k: str(r.get("fate") or hg.BORN) for k, r in hg.Graph(p).current().items()}
    assert hg.current_fates(p) == full
    assert full["a"] == "FAILED" and full["c"] == hg.BORN and full['q"uote'] == "CERTIFIED"


def test_one_torn_line_costs_one_row_not_the_graph(tmp_path: Path) -> None:
    assert len(hg.Graph(_ledger(tmp_path)).rows()) == 5


def test_an_absent_ledger_is_empty_not_an_error(tmp_path: Path) -> None:
    assert hg.current_fates(tmp_path / "nope.jsonl") == {}
