"""research_gap_map reads only the tail of its JSONL inputs (daily chain stall 2026-11-10)."""
from __future__ import annotations

import json

import pytest
import research_gap_map as G

LS = chr(0x2028)


def _write(path, rows, crlf=False, trailing=True):
    sep = "\r\n" if crlf else "\n"
    body = sep.join(json.dumps(r, ensure_ascii=False) for r in rows)
    path.write_bytes((body + (sep if trailing else "")).encode("utf-8"))


@pytest.mark.parametrize("block", [7, 64, 1 << 20])
@pytest.mark.parametrize("tail", [1, 3, 50, 500])
@pytest.mark.parametrize("trailing", [True, False])
def test_tail_matches_the_whole_file_read(tmp_path, block, tail, trailing):
    p = tmp_path / "g.jsonl"
    rows = [{"id": i, "s": "x" * (i % 13)} for i in range(120)]
    _write(p, rows, trailing=trailing)
    want = p.read_text("utf-8").splitlines()[-tail:]
    assert G._tail_lines(p, tail, block=block) == want


def test_crlf_and_blank_lines(tmp_path):
    p = tmp_path / "g.jsonl"
    _write(p, [{"a": 1}, {"a": 2}, {"a": 3}], crlf=True)
    assert G._tail_lines(p, 2, block=5) == ['{"a": 2}', '{"a": 3}']


def test_a_raw_line_separator_stays_inside_its_row(tmp_path):
    p = tmp_path / "g.jsonl"
    _write(p, [{"a": "x" + LS + "y"}, {"a": 2}])
    note: dict[str, str] = {}
    assert G._read_jsonl(p, note, 10) == [{"a": "x" + LS + "y"}, {"a": 2}]


def test_empty_absent_and_zero_tail(tmp_path):
    p = tmp_path / "e.jsonl"
    p.write_bytes(b"")
    assert G._tail_lines(p, 5) == []
    assert G._tail_lines(p, 0) == []
    note: dict[str, str] = {}
    assert G._read_jsonl(tmp_path / "missing.jsonl", note, 5) == []
    assert note[str(tmp_path / "missing.jsonl")] == "ABSENT"


def test_reads_only_the_tail_bytes(tmp_path, monkeypatch):
    p = tmp_path / "big.jsonl"
    _write(p, [{"id": i, "pad": "y" * 200} for i in range(20_000)])
    read = {"n": 0}
    real_open = open

    class Spy:
        def __init__(self, fh):
            self.fh = fh

        def __enter__(self):
            return self

        def __exit__(self, *a):
            self.fh.close()

        def seek(self, *a):
            return self.fh.seek(*a)

        def tell(self):
            return self.fh.tell()

        def read(self, n=-1):
            b = self.fh.read(n)
            read["n"] += len(b)
            return b

    monkeypatch.setattr(G, "open", lambda *a, **k: Spy(real_open(*a, **k)), raising=False)
    out = G._tail_lines(p, 10, block=4096)
    assert [json.loads(x)["id"] for x in out] == list(range(19_990, 20_000))
    assert read["n"] < 16_384 < p.stat().st_size
