"""`record_gauntlet_verdicts` reads the graph in one streamed pass, with the full read's answers."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.research import hypothesis_graph as hg


def _reference(g: hg.Graph) -> tuple[dict, dict]:
    """The pre-2026-10-20 read: every row resident, then the three fields and the earliest at."""
    cur = {k: (r.get("fate"), r.get("prereg_status"), r.get("terminal_gate"))
           for k, r in g.current().items()}
    earliest: dict[str, str] = {}
    for r in g.rows():
        if r.get("fate") in (hg.FAILED, hg.CERTIFIED, hg.JUDGED) and r.get("at"):
            rid, rat = str(r.get("id")), str(r["at"])
            if rid not in earliest or rat < earliest[rid]:
                earliest[rid] = rat
    return cur, earliest


ROWS = [{"id": "a", "fate": "FAILED", "at": "2026-10-03", "terminal_gate": "cpcv"},
        {"id": "a", "fate": "JUDGED", "at": "2026-10-01", "prereg_status": "POST_HOC"},
        {"id": "b", "fate": "BORN", "at": "2026-09-01"},
        {"id": "b", "fate": "CERTIFIED", "at": "", "terminal_gate": None},
        {}, {"id": None, "fate": "FAILED", "at": "2026-10-09"}]


@pytest.mark.parametrize("tail", ["", '{"id": "x", "fa', "\n  \n"])
def test_fate_index_equals_the_full_read(tmp_path: Path, tail: str) -> None:
    p = tmp_path / "g.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in ROWS) + tail, encoding="utf-8")
    assert hg._fate_index(hg.Graph(p)) == _reference(hg.Graph(p))


def test_missing_ledger_and_non_object_row(tmp_path: Path) -> None:
    assert hg._fate_index(hg.Graph(tmp_path / "absent.jsonl")) == ({}, {})
    p = tmp_path / "g.jsonl"
    p.write_text(json.dumps(ROWS[0]) + "\n[1, 2]\n", encoding="utf-8")
    with pytest.raises(AttributeError):
        hg.Graph(p).current()
    with pytest.raises(AttributeError):
        hg._fate_index(hg.Graph(p))


def test_the_recorder_never_holds_the_graph(tmp_path: Path, monkeypatch) -> None:
    p = tmp_path / "g.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in ROWS), encoding="utf-8")
    monkeypatch.setattr(hg.Graph, "rows", lambda self: pytest.fail("whole graph parsed"))
    out = hg.record_gauntlet_verdicts([{"cell": "c", "sym": "EURUSD", "family": "carry",
                                        "params": {"k": 1}, "passed": False,
                                        "stages": {"cpcv": {"passed": False}},
                                        "terminal_gate": "cpcv"}],
                                      graph=hg.Graph(p), prereg_path=tmp_path / "none.jsonl",
                                      at="2026-10-20T00:00:00+00:00")
    assert out["recorded"] == 1


@pytest.mark.parametrize("lines", [["null"], ["null", "[1]"], ["[1]", "null"],
                                   [json.dumps(ROWS[0]), "null", json.dumps(ROWS[2])]])
def test_a_null_row_raises_like_the_full_read(tmp_path: Path, lines: list[str]) -> None:
    """A JSON `null` row is a non-object row: the full read raises on the FIRST one, so the
    stream must too, with the same message -- never swallow it (audit of 2a0ad049)."""
    p = tmp_path / "g.jsonl"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(AttributeError) as full:
        hg.Graph(p).current()
    with pytest.raises(AttributeError) as streamed:
        hg._fate_index(hg.Graph(p))
    assert str(streamed.value) == str(full.value)


def test_a_null_row_stamps_and_appends_nothing(tmp_path: Path) -> None:
    p = tmp_path / "g.jsonl"
    p.write_text(json.dumps(ROWS[0]) + "\nnull\n", encoding="utf-8")
    before = p.read_bytes()
    with pytest.raises(AttributeError):
        hg.record_gauntlet_verdicts([{"cell": "c", "sym": "EURUSD", "family": "carry",
                                      "params": {"k": 1}, "passed": False,
                                      "stages": {"cpcv": {"passed": False}}}],
                                    graph=hg.Graph(p), prereg_path=tmp_path / "none.jsonl",
                                    at="2026-10-20T00:00:00+00:00")
    assert p.read_bytes() == before
