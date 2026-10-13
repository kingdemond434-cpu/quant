"""Two per-sweep costs of the judge's merging core, cut without changing what is recorded.

Measured 2026-10-07: acknowledging the judge's 1.44M-row docket parsed the whole ~1.8 GB array
(21.5 s, 5.8 GB peak) in the certifying process, only to fall through to the sidecar.
"""
from __future__ import annotations

import json
from pathlib import Path

from libs.ops.control_plane import lease


def _sidecar(p: Path, env: dict) -> None:
    p.with_name(p.name + lease.ENVELOPE_SUFFIX).write_text(json.dumps(env), encoding="utf-8")


def test_an_array_document_is_never_parsed_and_the_sidecar_answers(tmp_path, monkeypatch):
    doc = tmp_path / "external_survivors.json"
    doc.write_text("﻿  \n" + json.dumps([{"symbol": "EURUSD"}] * 50), encoding="utf-8")
    _sidecar(doc, {"artifact_id": "a", "producer_run_id": "r1"})
    parsed: list[int] = []
    real = lease.json.loads

    def _loads(s, *a, **k):
        parsed.append(len(s))
        return real(s, *a, **k)

    monkeypatch.setattr(lease.json, "loads", _loads)
    assert lease.read_envelope(doc)["producer_run_id"] == "r1"
    assert all(n < 200 for n in parsed)          # only the sidecar was parsed


def test_an_object_document_still_carries_its_own_envelope(tmp_path):
    doc = tmp_path / "report.json"
    doc.write_text(json.dumps({lease.ENVELOPE_KEY: {"producer_run_id": "inside"}, "n": 1}),
                   encoding="utf-8")
    _sidecar(doc, {"producer_run_id": "sidecar"})
    assert lease.read_envelope(doc)["producer_run_id"] == "inside"


def test_an_array_with_no_sidecar_is_unleased(tmp_path):
    doc = tmp_path / "rows.json"
    doc.write_text("[1, 2, 3]", encoding="utf-8")
    assert lease.read_envelope(doc) is None


def test_graph_batch_append_writes_the_same_rows_once(tmp_path, monkeypatch):
    """`record_gauntlet_verdicts` writes its new fates through one open, same rows, same order."""
    from libs.research import hypothesis_graph as hg

    g = hg.Graph(tmp_path / "graph.jsonl")
    nodes = [hg.Node(symbol="EURUSD", family="carry", params={"n": i}, source="t",
                     fate=hg.FAILED, at="2026-10-07T00:00:00+00:00") for i in range(3)]
    opens: list[str] = []
    real_open = Path.open

    def _open(self, *a, **k):
        opens.append(str(self))
        return real_open(self, *a, **k)

    monkeypatch.setattr(Path, "open", _open)
    rows = g.append_rows([n.to_row() for n in nodes])
    assert opens.count(str(g.path)) == 1
    monkeypatch.setattr(Path, "open", real_open)
    assert [r["id"] for r in g.rows()] == [r["id"] for r in rows] == [n.id for n in nodes]
