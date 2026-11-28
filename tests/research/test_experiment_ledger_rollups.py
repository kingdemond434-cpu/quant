"""Lifetime trials survive disk_guard's rollup, and are charged once (audit 2026-10-14).

`scripts/disk_guard.rollup` compacts discovery files older than RETAIN_DAYS into
`rollup_<day>.jsonl.gz` (one contract document per line) and deletes the originals. Reading only
the live files dropped every rolled contract's `tests_run` from the lifetime count.
"""
from __future__ import annotations

import gzip
import json

from libs.research import experiment_ledger as el


def _doc(n, fam, stamp):
    return {"tests_run": n, "generated_at": stamp,
            "discoveries": [{"family": fam, "symbol": "EURUSD"}]}


def _seat(tmp_path):
    seat = tmp_path / "data" / "intelligence" / "seat"
    seat.mkdir(parents=True)
    return seat


def test_count_is_unchanged_by_a_rollup(tmp_path, monkeypatch):
    monkeypatch.setattr(el, "DESK", tmp_path)
    seat = _seat(tmp_path)
    docs = [_doc(4, "carry", "2026-10-01T00:00:00Z"), _doc(6, "carry", "2026-10-01T01:00:00Z")]
    for i, d in enumerate(docs):
        (seat / f"discoveries_20261001_{i}.json").write_text(json.dumps(d), "utf-8")
    before = el._proposer_counts()
    assert before == (10, {"carry": 10})
    # exactly what disk_guard.rollup does: one document per line, originals deleted
    with gzip.open(seat / "rollup_20261001.jsonl.gz", "at", encoding="utf-8") as out:
        for i, d in enumerate(docs):
            out.write(json.dumps(d, separators=(",", ":")) + "\n")
            (seat / f"discoveries_20261001_{i}.json").unlink()
    assert el._proposer_counts() == before


def test_a_contract_in_both_a_file_and_a_rollup_is_charged_once(tmp_path, monkeypatch):
    monkeypatch.setattr(el, "DESK", tmp_path)
    seat = _seat(tmp_path)
    d = _doc(7, "formula", "2026-10-02T00:00:00Z")
    (seat / "discoveries_20261002_0.json").write_text(json.dumps(d), "utf-8")  # unlink failed
    with gzip.open(seat / "rollup_20261002.jsonl.gz", "at", encoding="utf-8") as out:
        out.write(json.dumps(d) + "\n")
        out.write(json.dumps(d) + "\n")                                      # re-run append
    assert el._proposer_counts() == (7, {"formula": 7})


def test_distinct_contracts_with_equal_counts_both_count(tmp_path, monkeypatch):
    monkeypatch.setattr(el, "DESK", tmp_path)
    seat = _seat(tmp_path)
    with gzip.open(seat / "rollup_20261003.jsonl.gz", "at", encoding="utf-8") as out:
        out.write(json.dumps(_doc(5, "carry", "2026-10-03T00:00:00Z")) + "\n")
        out.write(json.dumps(_doc(5, "carry", "2026-10-03T01:00:00Z")) + "\n")
        out.write("{torn\n")
    assert el._proposer_counts() == (10, {"carry": 10})


def test_torn_archive_keeps_what_was_readable(tmp_path, monkeypatch):
    monkeypatch.setattr(el, "DESK", tmp_path)
    seat = _seat(tmp_path)
    raw = gzip.compress((json.dumps(_doc(3, "carry", "x")) + "\n").encode() * 50)
    (seat / "rollup_20261004.jsonl.gz").write_bytes(raw[: len(raw) - 8])   # truncated trailer
    total, _ = el._proposer_counts()
    assert total == 3                                                     # identical docs: once


def test_a_rolled_learned_seat_is_still_one_max_charge(tmp_path, monkeypatch):
    # the learned miners re-run one grid daily: their files are reconciled by MAX per seat, and a
    # rollup of those files must neither add a second charge nor drop the first
    monkeypatch.setattr(el, "DESK", tmp_path)
    seat = tmp_path / "data" / "intelligence" / "learned_x"
    seat.mkdir(parents=True)
    docs = [_doc(30, "carry", "2026-10-05T00:00:00Z"), _doc(30, "carry", "2026-10-06T00:00:00Z")]
    for i, d in enumerate(docs):
        (seat / f"discoveries_2026100{5 + i}_0.json").write_text(json.dumps(d), "utf-8")
    before = el._proposer_counts()
    assert before == (30, {"carry": 30})
    with gzip.open(seat / "rollup_20261005.jsonl.gz", "at", encoding="utf-8") as out:
        out.write(json.dumps(docs[0], separators=(",", ":")) + "\n")
    (seat / "discoveries_20261005_0.json").unlink()
    assert el._proposer_counts() == before


def test_a_list_file_counts_the_same_before_and_after_its_rollup(tmp_path, monkeypatch):
    # disk_guard writes a list file's elements one per line; elements without tests_run (the
    # scrapers' rows) are never trials, before or after
    monkeypatch.setattr(el, "DESK", tmp_path)
    seat = _seat(tmp_path)
    rows = [{"source": "s", "url": "u1"}, {"source": "s", "url": "u2"}]
    f = seat / "discoveries_20261007_0.json"
    f.write_text(json.dumps(rows), "utf-8")
    before = el._proposer_counts()
    assert before == (0, {})
    with gzip.open(seat / "rollup_20261007.jsonl.gz", "at", encoding="utf-8") as out:
        for r in rows:
            out.write(json.dumps(r, separators=(",", ":")) + "\n")
    f.unlink()
    assert el._proposer_counts() == before
