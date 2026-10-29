"""Count a large append-only graph without retaining every verdict blob in RAM."""

import json

from libs.research import experiment_ledger as el
from libs.research import hypothesis_graph as hg


def _append(path, rows):
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def test_latest_fate_counts_are_cached_by_exact_graph_version(tmp_path, monkeypatch):
    graph = tmp_path / "hypothesis_graph.jsonl"
    _append(graph, [
        {"id": "a", "family": "carry", "fate": "BORN", "gates": {"large": [1] * 100}},
        {"id": "b", "family": "formula", "fate": "FAILED"},
        {"id": "a", "family": "carry", "fate": "CERTIFIED"},
    ])
    monkeypatch.setattr(hg, "LEDGER", graph)
    monkeypatch.setattr(el, "DESK", tmp_path)

    assert el._graph_counts() == (2, {"carry": 1, "formula": 1})
    cache = tmp_path / "data" / "experiment_graph_counts.json"
    assert json.loads(cache.read_text("utf-8"))["judged_cells"] == 2
    assert el._graph_counts() == (2, {"carry": 1, "formula": 1})

    _append(graph, [{"id": "b", "family": "formula", "fate": "RETIRED"},
                    {"id": "c", "family": "carry", "fate": "JUDGED"}])
    assert el._graph_counts() == (2, {"carry": 2})
    assert json.loads(cache.read_text("utf-8"))["graph_stamp"]["size"] == graph.stat().st_size


def test_malformed_verdict_cannot_silently_zero_lifetime_trials(tmp_path, monkeypatch):
    graph = tmp_path / "hypothesis_graph.jsonl"
    graph.write_text('{"id":"a","family":"carry","fate":"JUDGED"}\n{bad}\n',
                     encoding="utf-8")
    monkeypatch.setattr(hg, "LEDGER", graph)
    monkeypatch.setattr(el, "DESK", tmp_path)

    try:
        el._graph_counts()
    except json.JSONDecodeError:
        pass
    else:
        raise AssertionError("malformed graph was silently accepted as a smaller trial count")
