"""Live judge appends cannot restart the compiler's historical annotations."""
import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

from libs.research.hypothesis_graph import FAILED, Graph, Node  # noqa: E402
from research import miner_candidate_compiler as compiler  # noqa: E402


def test_one_pass_keeps_history_stable_while_next_sees_judge_append(tmp_path):
    path = tmp_path / "history.jsonl"
    writer = Graph(path)
    writer.append(Node(symbol="USDJPY", family="carry", params={"x": 1}, fate=FAILED))
    snapshot = compiler._graph_snapshot(path)
    assert snapshot.prior_failures("USDJPY", "carry", {"x": 1})["n_failed"] == 1
    writer.append(Node(symbol="EURUSD", family="carry", params={"x": 2}, fate=FAILED))
    assert snapshot.prior_failures("EURUSD", "carry", {"x": 2})["n_failed"] == 0
    assert compiler._graph_snapshot(path).prior_failures(
        "EURUSD", "carry", {"x": 2})["n_failed"] == 1
    assert len(Graph(path).rows()) == 2


def test_interrupted_publication_keeps_previous_complete_artifact(tmp_path, monkeypatch):
    path = tmp_path / "compiled.json"
    path.write_text('{"previous": true}', encoding="utf-8")

    def interrupted(*args):
        raise OSError("publication interrupted")

    monkeypatch.setattr(compiler.os, "replace", interrupted)
    with pytest.raises(OSError, match="publication interrupted"):
        compiler._atomic_json(path, {"new": True})
    assert json.loads(path.read_text("utf-8")) == {"previous": True}
    assert list(tmp_path.glob("*.tmp")) == []
