import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research import discovery_compiler as dc

_OPEN: list[sqlite3.Connection] = []


@pytest.fixture(autouse=True)
def _close_dbs():
    yield
    while _OPEN:
        _OPEN.pop().close()


def _db(spec):
    c = sqlite3.connect(":memory:")
    _OPEN.append(c)
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE discoveries (discovery_id TEXT, origin TEXT, state TEXT, "
              "created_at TEXT, generator TEXT, source_type TEXT)")
    for spec_row in spec:
        gen, count, start = spec_row[:3]
        origin = spec_row[3] if len(spec_row) > 3 else "DESK"
        for k in range(count):
            c.execute("INSERT INTO discoveries VALUES (?,?,?,?,?,?)",
                      (f"{gen or 'blank'}-{k}", origin, "UNPROCESSED",
                       f"2026-{start}-{k:05d}", gen, "intelligence" if gen == "" else None))
    return c


def test_deep_backlog_no_longer_holds_the_door():
    c = _db([("forest_runner", 5000, "10-01"), ("seat", 50, "11-10"),
             ("country_labs", 50, "11-12"), ("missed_trade", 50, "11-15")])
    got = dc.fair_unprocessed(200, conn=c)
    gens = [r["generator"] for r in got]
    assert len(got) == 200
    assert {"seat", "country_labs", "missed_trade"} <= set(gens)
    assert gens.count("forest_runner") == 50


def test_oldest_first_inside_each_origin():
    c = _db([("a", 10, "10-01"), ("b", 10, "10-02")])
    got = dc.fair_unprocessed(6, conn=c)
    assert [r["discovery_id"] for r in got] == ["a-0", "b-0", "a-1", "b-1", "a-2", "b-2"]


def test_single_origin_is_plain_oldest_first():
    c = _db([("only", 30, "10-01")])
    got = dc.fair_unprocessed(5, conn=c)
    assert [r["discovery_id"] for r in got] == [f"only-{k}" for k in range(5)]


def test_processed_rows_are_not_taken():
    c = _db([("a", 3, "10-01"), ("b", 3, "10-02")])
    c.execute("UPDATE discoveries SET state='COMPILED' WHERE generator='a'")
    got = dc.fair_unprocessed(10, conn=c)
    assert {r["generator"] for r in got} == {"b"}


def test_fault_falls_back_to_old_query(monkeypatch):
    calls = []

    class Boom:
        def execute(self, *a, **k):
            raise RuntimeError("locked")

    monkeypatch.setattr(dc.R, "discoveries",
                        lambda **kw: calls.append(kw) or [{"discovery_id": "x"}])
    assert dc.fair_unprocessed(7, conn=Boom()) == [{"discovery_id": "x"}]
    assert calls[-1]["limit"] == 7


def test_intel_files_one_pass_newest_first(tmp_path, monkeypatch):
    import os

    seat = tmp_path / "kimi"
    seat.mkdir()
    for i, name in enumerate(("a.json", "b.jsonl", "c.txt")):
        f = seat / name
        f.write_text("[]")
        os.utime(f, (1_000_000 + i, 1_000_000 + i))
    monkeypatch.setattr(dc, "INTEL", tmp_path)
    got = dc._intel_files()
    assert [p.name for p, _s, _m in got] == ["b.jsonl", "a.json"]
    cursor = {"files": {}}
    p, size, mtime = got[0]
    assert dc._fresh_st(cursor, p, size, mtime)
    cursor["files"][str(p)] = {"size": size, "mtime": mtime}
    assert not dc._fresh_st(cursor, p, size, mtime)


def test_seats_get_their_share_when_backlog_is_deep(tmp_path, monkeypatch):
    seat = tmp_path / "deepseek"
    seat.mkdir()
    (seat / "d.json").write_text("[]")
    monkeypatch.setattr(dc, "INTEL", tmp_path)
    asked = []
    monkeypatch.setattr(dc, "fair_unprocessed",
                        lambda n, conn=None: asked.append(n) or [])
    dc.intake({"files": {}}, conn=None, limit=200, record=False)
    assert asked == [150]


def test_same_origin_producers_still_rotate():
    c = _db([("forest_runner", 5000, "10-01", "EXTERNAL"),
             ("ingestion_ledger", 40, "11-01", "EXTERNAL"),
             ("seat:kimi", 40, "11-02", "EXTERNAL")])
    gens = [r["generator"] for r in dc.fair_unprocessed(90, conn=c)]
    assert gens.count("forest_runner") == 30
    assert gens.count("ingestion_ledger") == 30 and gens.count("seat:kimi") == 30


def test_blank_producer_key_never_duplicates():
    c = _db([("", 20, "10-01", ""), ("a", 20, "10-02"), ("b", 20, "10-03")])
    c.execute("UPDATE discoveries SET source_type=NULL WHERE generator=''")
    got = dc.fair_unprocessed(30, conn=c)
    ids = [r["discovery_id"] for r in got]
    assert len(ids) == len(set(ids)) == 30
    assert sum(1 for i in ids if i.startswith("blank-")) == 10


def test_short_queue_is_topped_up_to_the_limit():
    c = _db([("a", 2, "10-01"), ("b", 50, "10-02")])
    got = dc.fair_unprocessed(20, conn=c)
    ids = [r["discovery_id"] for r in got]
    assert len(ids) == len(set(ids)) == 20
