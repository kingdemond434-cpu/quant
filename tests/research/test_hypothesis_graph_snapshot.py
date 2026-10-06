"""Pass-local history must preserve prior evidence without rereading a growing ledger."""
import json
from pathlib import Path

import pytest

from libs.research.hypothesis_graph import Graph


def test_snapshot_retains_original_receipts_while_live_view_tracks_new_fates(tmp_path, monkeypatch):
    path = tmp_path / "graph.jsonl"
    first = {"id": "a", "fate": "FAILED", "region": "region-a"}
    path.write_text(json.dumps(first) + "\n", encoding="utf-8")
    original_read_text = Path.read_text
    monkeypatch.setattr(Path, "read_text", lambda self, *a, **kw:
                        (_ for _ in ()).throw(AssertionError("bulk history read"))
                        if self == path else original_read_text(self, *a, **kw))
    graph = Graph(path)
    snapshot = graph.snapshot()
    with path.open("a", encoding="utf-8") as ledger:
        ledger.write(json.dumps({"id": "a", "fate": "PASSED", "region": "region-a"}) + "\n")
        ledger.write(json.dumps({"id": "b", "fate": "FAILED", "region": "region-b"}) + "\n")
    assert graph.current()["a"]["fate"] == "PASSED"
    assert len(graph.rows()) == 3
    assert snapshot.rows() == [first]
    assert snapshot.current() == {"a": first}
    assert snapshot.buried() == {"region-a": [first]}
    # Once captured, a deleted/unreadable live file cannot force a pass to reread it.
    path.unlink()
    assert snapshot.rows() == [first]
    with pytest.raises(RuntimeError, match="read-only"):
        snapshot.append(None)


def test_empty_snapshot_remains_empty_if_ledger_is_created_later(tmp_path):
    path = tmp_path / "graph.jsonl"
    snapshot = Graph(path).snapshot()
    path.write_text(json.dumps({"id": "new"}) + "\n", encoding="utf-8")
    assert snapshot.rows() == []
    assert snapshot.current() == {}
