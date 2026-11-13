"""The incremental ledger folds give the full read's answer on every call, or hand back to it."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.research import append_fold
from libs.research import hypothesis_graph as hg
from libs.research import preregistration as pr

GRAPH = [{"id": "a", "fate": "FAILED", "at": "2026-10-03", "terminal_gate": "cpcv"},
         {"id": "a", "fate": "JUDGED", "at": "2026-10-01", "prereg_status": "POST_HOC"},
         {"id": "b", "fate": "BORN", "at": "2026-09-01"},
         {"id": "b", "fate": "CERTIFIED", "at": "", "terminal_gate": None},
         {}, {"id": None, "fate": "FAILED", "at": "2026-10-09"}]
MORE = [{"id": "a", "fate": "CERTIFIED", "at": "2026-09-30", "terminal_gate": 3},
        {"id": "c", "fate": "FAILED", "at": "2026-11-01", "prereg_status": "PREREGISTERED"}]

PREREG = [{"spec_id": "s1", "registered_utc": "2026-10-02", "prereg_hash": "h1"},
          {"spec_id": "s1", "registered_utc": "2026-10-01", "prereg_hash": "h0"},
          {"kind": pr.BATCH_KIND, "specs": ["s2", "s3"], "registered_utc": "2026-10-05",
           "prereg_hash": "hb"},
          {"spec_id": "s4", "registered_utc": "", "prereg_hash": "x"}, [1, 2]]
PMORE = [{"spec_id": "s2", "registered_utc": "2026-10-04", "prereg_hash": "h2"},
         {"spec_id": "s9", "registered_utc": "2026-11-01", "prereg_hash": "h9"}]


def _lines(rows: list) -> str:
    return "".join(json.dumps(r) + "\n" for r in rows)


def _full_fate(p: Path) -> tuple:
    with append_fold_off():
        return hg._fate_index(hg.Graph(p))


def _full_spec(p: Path) -> dict:
    with append_fold_off():
        return pr.spec_index(p)


class append_fold_off:
    def __enter__(self) -> None:
        self.mp = pytest.MonkeyPatch()
        self.mp.setenv("APPEND_FOLD_CACHE", "0")

    def __exit__(self, *a: object) -> None:
        self.mp.undo()


def test_graph_fold_matches_the_full_read_across_appends(tmp_path: Path) -> None:
    p = tmp_path / "g.jsonl"
    p.write_text(_lines(GRAPH), encoding="utf-8")
    assert hg._fate_index(hg.Graph(p)) == _full_fate(p)
    assert append_fold.cache_path(p, "fate_index").exists()
    with p.open("a", encoding="utf-8") as fh:
        fh.write(_lines(MORE))
    assert hg._fate_index(hg.Graph(p)) == _full_fate(p)
    # a call with nothing appended is the cached answer, still the full read's
    assert hg._fate_index(hg.Graph(p)) == _full_fate(p)


def test_only_the_appended_rows_are_parsed(tmp_path: Path, monkeypatch) -> None:
    p = tmp_path / "g.jsonl"
    p.write_text(_lines(GRAPH), encoding="utf-8")
    hg._fate_index(hg.Graph(p))
    with p.open("a", encoding="utf-8") as fh:
        fh.write(_lines(MORE))
    seen: list[bytes] = []
    real = append_fold._line
    monkeypatch.setattr(append_fold, "_line", lambda raw, *a: (seen.append(raw), real(raw, *a))[1])
    hg._fate_index(hg.Graph(p))
    assert len(seen) == len(MORE)


@pytest.mark.parametrize("edit", ["rewrite_middle", "truncate", "replace_whole"])
def test_a_changed_prefix_is_folded_from_byte_zero(tmp_path: Path, edit: str) -> None:
    p = tmp_path / "g.jsonl"
    p.write_text(_lines(GRAPH + MORE), encoding="utf-8")
    hg._fate_index(hg.Graph(p))
    if edit == "rewrite_middle":
        rows = list(GRAPH + MORE)
        rows[1] = {"id": "a", "fate": "FAILED", "at": "2026-01-01", "prereg_status": "XXXXXXXX"}
        p.write_text(_lines(rows), encoding="utf-8")
    elif edit == "truncate":
        p.write_text(_lines(GRAPH[:2]), encoding="utf-8")
    else:
        p.write_text(_lines(MORE), encoding="utf-8")
    assert hg._fate_index(hg.Graph(p)) == _full_fate(p)


@pytest.mark.parametrize("tail", ['{"id": "x", "fa', '{"id": "t", "fate": "FAILED", "at": "z"}',
                                  "\n  \n", "null", "[1]"])
def test_a_trailing_partial_line_answers_like_the_full_read(tmp_path: Path, tail: str) -> None:
    p = tmp_path / "g.jsonl"
    p.write_text(_lines(GRAPH) + tail, encoding="utf-8")
    try:
        want = _full_fate(p)
    except AttributeError:
        with pytest.raises(AttributeError):
            hg._fate_index(hg.Graph(p))
        return
    assert hg._fate_index(hg.Graph(p)) == want
    # the partial line never entered the cache: completing it is folded correctly
    with p.open("a", encoding="utf-8") as fh:
        fh.write("\n" + _lines(MORE))
    try:
        want2 = _full_fate(p)
    except AttributeError:
        with pytest.raises(AttributeError):
            hg._fate_index(hg.Graph(p))
        return
    assert hg._fate_index(hg.Graph(p)) == want2


def test_a_non_object_row_still_raises_after_a_cached_prefix(tmp_path: Path) -> None:
    p = tmp_path / "g.jsonl"
    p.write_text(_lines(GRAPH), encoding="utf-8")
    hg._fate_index(hg.Graph(p))
    with p.open("a", encoding="utf-8") as fh:
        fh.write("null\n")
    with pytest.raises(AttributeError):
        hg.Graph(p).current()
    with pytest.raises(AttributeError):
        hg._fate_index(hg.Graph(p))


@pytest.mark.parametrize("junk", ["", "{", '{"v": 1}', "[]", '{"v":1,"kind":"fate_index"}'])
def test_a_corrupt_cache_is_ignored(tmp_path: Path, junk: str) -> None:
    p = tmp_path / "g.jsonl"
    p.write_text(_lines(GRAPH), encoding="utf-8")
    hg._fate_index(hg.Graph(p))
    append_fold.cache_path(p, "fate_index").write_text(junk, encoding="utf-8")
    with p.open("a", encoding="utf-8") as fh:
        fh.write(_lines(MORE))
    assert hg._fate_index(hg.Graph(p)) == _full_fate(p)


def test_a_poisoned_cache_with_a_wrong_hash_is_never_trusted(tmp_path: Path) -> None:
    p = tmp_path / "g.jsonl"
    p.write_text(_lines(GRAPH), encoding="utf-8")
    hg._fate_index(hg.Graph(p))
    cp = append_fold.cache_path(p, "fate_index")
    doc = json.loads(cp.read_text(encoding="utf-8"))
    doc["state"]["cur"]["a"] = ["CERTIFIED", "PREREGISTERED", ""]
    doc["sha256"] = "0" * 64
    cp.write_text(json.dumps(doc), encoding="utf-8")
    assert hg._fate_index(hg.Graph(p)) == _full_fate(p)


def test_crlf_and_bare_cr_lines(tmp_path: Path) -> None:
    p = tmp_path / "g.jsonl"
    p.write_bytes(_lines(GRAPH).replace("\n", "\r\n").encode())
    assert hg._fate_index(hg.Graph(p)) == _full_fate(p)
    q = tmp_path / "q.jsonl"
    q.write_bytes(json.dumps(GRAPH[0]).encode() + b"\r" + json.dumps(MORE[1]).encode() + b"\n")
    assert hg._fate_index(hg.Graph(q)) == _full_fate(q)


def test_spec_index_matches_the_full_read_across_appends(tmp_path: Path) -> None:
    p = tmp_path / "prereg.jsonl"
    p.write_text(_lines(PREREG) + "not json\n", encoding="utf-8")
    assert pr.spec_index(p) == _full_spec(p)
    assert append_fold.cache_path(p, "spec_index").exists()
    with p.open("a", encoding="utf-8") as fh:
        fh.write(_lines(PMORE) + '{"spec_id": "s7", "regis')
    assert pr.spec_index(p) == _full_spec(p)
    p.write_bytes(p.read_bytes() + b'tered_utc": "2026-12-01", "prereg_hash": "h7"}\n\xff\xfe\n')
    assert pr.spec_index(p) == _full_spec(p)
    assert pr.spec_index(p)["s7"] == ("2026-12-01", "h7")


def test_switch_off_writes_no_cache(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("APPEND_FOLD_CACHE", "0")
    p = tmp_path / "prereg.jsonl"
    p.write_text(_lines(PREREG), encoding="utf-8")
    assert pr.spec_index(p) == {"s1": ("2026-10-01", "h0"), "s2": ("2026-10-05", "hb"),
                                "s3": ("2026-10-05", "hb")}
    assert not append_fold.cache_path(p, "spec_index").exists()


def test_missing_ledger(tmp_path: Path) -> None:
    assert pr.spec_index(tmp_path / "absent.jsonl") == {}
    assert hg._fate_index(hg.Graph(tmp_path / "absent.jsonl")) == ({}, {})
