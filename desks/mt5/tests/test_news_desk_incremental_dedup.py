"""MT5-NewsDesk read ~457 GB in 7 days (2026-10-29): every 60 s poll re-read the whole ~50 MB
news_captures.jsonl to rebuild its dedup set. The set is now kept in-process and each poll reads
only the bytes appended since the last one."""
from __future__ import annotations

import builtins
import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

import news_desk  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    monkeypatch.setattr(news_desk, "_SEEN", {"keys": set(), "offset": 0, "ident": None})


def _rows(*keys: str) -> str:
    return "".join(json.dumps({"key": k}) + "\n" for k in keys)


def test_each_poll_reads_only_what_was_appended(tmp_path, monkeypatch):
    f = tmp_path / "news_captures.jsonl"
    f.write_text(_rows("a", "b"), "utf-8")
    assert news_desk._seen_keys(f) == {"a", "b"}
    first = news_desk._SEEN["offset"]
    assert first == f.stat().st_size
    with open(f, "a", encoding="utf-8") as h:
        h.write(_rows("c") + '{"key": "par')          # a line still being written
    reads: list[int] = []
    real_open = builtins.open

    def counting_open(path, mode="r", *a, **k):
        fh = real_open(path, mode, *a, **k)
        if "b" in mode:
            orig = fh.read
            fh.read = lambda *x: (lambda b: reads.append(len(b)) or b)(orig(*x))
        return fh

    monkeypatch.setattr(builtins, "open", counting_open)
    assert news_desk._seen_keys(f) == {"a", "b", "c"}
    assert reads == [f.stat().st_size - first]          # only the tail, never the whole file
    monkeypatch.setattr(builtins, "open", real_open)
    with open(f, "a", encoding="utf-8") as h:
        h.write('tial"}\n')
    assert "partial" in news_desk._seen_keys(f)
    # an unchanged file is not read at all
    monkeypatch.setattr(builtins, "open", counting_open)
    reads.clear()
    news_desk._seen_keys(f)
    assert reads == []


def test_a_replaced_or_shrunk_file_is_read_again(tmp_path):
    f = tmp_path / "news_captures.jsonl"
    f.write_text(_rows("a", "b", "c"), "utf-8")
    news_desk._seen_keys(f)
    f.write_text(_rows("z"), "utf-8")
    assert news_desk._seen_keys(f) == {"z"}


def test_the_poll_loop_no_longer_reads_the_whole_file():
    src = (_DESK / "research" / "news_desk.py").read_text("utf-8")
    body = src.split("def poll_official_rss", 1)[1].split("\ndef ", 1)[0]
    assert "CAPTURES.read_text" not in body and "_seen_keys()" in body
