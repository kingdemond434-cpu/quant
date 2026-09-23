"""THE RATE IS AN ARTIFACT AND THE RATCHET ONLY GOES UP.

These pin the three things the throughput lane exists to keep true: the writer's fast path
really does batch (one commit per chunk, not three per row), a measured rate is published per
stage with the binding stage named, and a stage that slows down fails a fence instead of
quietly costing the desk a decimal place.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from libs.moat import registry as reg
from libs.ops import throughput


# --------------------------------------------------------------------------- the ledger
def test_record_and_summarise_names_the_binding_stage(tmp_path: Path) -> None:
    s = tmp_path / "samples.jsonl"
    throughput.SAMPLES = s
    throughput.record("registry_write", 1000, 1.0)
    throughput.record("judge", 10, 10.0)          # 1/s: far slower, so it binds
    doc = throughput.summarise(path=s)
    assert doc["stages"]["registry_write"]["rows_per_s"] == pytest.approx(1000.0)
    assert doc["stages"]["judge"]["rows_per_s"] == pytest.approx(1.0)
    assert doc["binding_stage"] == "judge"
    assert doc["chain_rows_per_day"] == 86400


def test_unmeasured_stage_is_a_verdict_not_a_zero(tmp_path: Path) -> None:
    s = tmp_path / "samples.jsonl"
    throughput.SAMPLES = s
    throughput.record("registry_write", 100, 1.0)
    doc = throughput.summarise(path=s)
    assert doc["stages"]["judge"]["status"] == "UNMEASURED"
    assert "judge" in doc["unmeasured_stages"]
    assert "rows_per_s" not in doc["stages"]["judge"]


def test_record_never_raises_on_a_bad_path(tmp_path: Path) -> None:
    throughput.SAMPLES = tmp_path / "nope" / "x" / "s.jsonl"
    throughput.record("registry_write", 1, 1.0)   # creates the tree
    throughput.SAMPLES = Path("\0invalid")
    throughput.record("registry_write", 1, 1.0)   # must not raise


# --------------------------------------------------------------------------- the ratchet
def test_ratchet_raises_the_mark_and_never_lowers_it(tmp_path: Path) -> None:
    s, rep = tmp_path / "s.jsonl", tmp_path / "THROUGHPUT.json"
    throughput.SAMPLES = s
    throughput.record("registry_write", 1000, 1.0)            # 1000/s
    assert throughput.publish(path=s, report=rep)["verdict"] == "MEASURED"
    assert json.loads(rep.read_text())["high_water_rows_per_s"]["registry_write"] == 1000.0
    s.unlink()
    throughput.record("registry_write", 900, 1.0)             # 900/s: slower, mark holds
    doc = throughput.publish(path=s, report=rep)
    assert doc["high_water_rows_per_s"]["registry_write"] == 1000.0
    assert doc["verdict"] == "MEASURED"                       # inside tolerance


def test_a_real_slowdown_is_a_REGRESSION(tmp_path: Path) -> None:
    s, rep = tmp_path / "s.jsonl", tmp_path / "THROUGHPUT.json"
    throughput.SAMPLES = s
    throughput.record("registry_write", 1000, 1.0)
    throughput.publish(path=s, report=rep)
    s.unlink()
    throughput.record("registry_write", 100, 1.0)             # the 10x fall the fence is for
    doc = throughput.publish(path=s, report=rep)
    assert doc["verdict"] == "REGRESSION"
    assert doc["regressions"][0]["stage"] == "registry_write"
    assert doc["regressions"][0]["factor"] == pytest.approx(10.0)


# ------------------------------------------------------------------- the writer's fast path
@pytest.fixture
def db(tmp_path: Path):
    prev = reg.path()
    reg.set_path(tmp_path / "reg.sqlite")
    yield
    reg.set_path(prev)


def test_the_discovery_hash_lookup_is_indexed(db: None) -> None:
    """THE 231.9 ms SCAN. Without this index `record_discovery` reads every discovery row on
    every write, which is what held the desk to four rows a second."""
    conn = reg.connect()
    try:
        plan = " ".join(str(x) for r in conn.execute(
            "EXPLAIN QUERY PLAN SELECT discovery_id FROM discoveries WHERE content_hash=?",
            ("z" * 32,)) for x in r)
        assert "SCAN discoveries" not in plan
        assert "ix_disc_hash" in plan
    finally:
        conn.close()


def _visible(path: Path) -> int:
    """What ANOTHER connection can see -- i.e. what has actually been committed."""
    obs = sqlite3.connect(str(path), timeout=30)
    try:
        return int(obs.execute("SELECT COUNT(*) FROM research_candidates").fetchone()[0])
    finally:
        obs.close()


def test_batch_commits_once_per_chunk_not_once_per_row(db: None) -> None:
    """Per-row commits were 84% of the write path. A second connection sees nothing until the
    chunk closes, which is what proves the commits were folded rather than merely reordered."""
    conn = reg.connect()
    try:
        with reg.batch(conn, every=10):
            for i in range(5):
                reg.enqueue_candidate(family="f", symbol="EURUSD", params={"i": i},
                                      origin="DESK", conn=conn)
            assert _visible(reg.path()) == 0, "mid-chunk rows must not be committed one by one"
            for i in range(5, 10):
                reg.enqueue_candidate(family="f", symbol="EURUSD", params={"i": i},
                                      origin="DESK", conn=conn)
            assert _visible(reg.path()) == 10, "the chunk boundary must commit"
            for i in range(10, 20):
                reg.enqueue_candidate(family="f", symbol="EURUSD", params={"i": i},
                                      origin="DESK", conn=conn)
        n = int(conn.execute("SELECT COUNT(*) FROM research_candidates").fetchone()[0])
        assert n == 20, "every row must still land: batching writes fewer commits, not fewer rows"
        assert _visible(reg.path()) == 20
    finally:
        conn.close()


def test_batch_rolls_back_the_incomplete_chunk_and_reraises(db: None) -> None:
    conn = reg.connect()
    try:
        with pytest.raises(RuntimeError), reg.batch(conn, every=500):
            reg.enqueue_candidate(family="f", symbol="EURUSD", params={"i": 1},
                                  origin="DESK", conn=conn)
            raise RuntimeError("boom")
        assert int(conn.execute(
            "SELECT COUNT(*) FROM research_candidates").fetchone()[0]) == 0
    finally:
        conn.close()


def test_batch_takes_the_write_lock_up_front(db: None) -> None:
    """Two producers write the registry at once. With a DEFERRED transaction the second dies
    instantly with `database is locked` -- SQLite cannot make a lock UPGRADE wait -- and
    `_record_in_registry` swallows it, so the donation is silently unrecorded."""
    a, b = reg.connect(), reg.connect()
    try:
        with reg.batch(a, every=500):
            reg.enqueue_candidate(family="f", symbol="EURUSD", params={"i": 1},
                                  origin="DESK", conn=a)
            assert a.in_transaction, "the batch must hold a write transaction, not a read one"
    finally:
        a.close()
        b.close()


def test_columns_cache_follows_a_schema_change(db: None) -> None:
    """The cached column list is keyed by schema_version, so DDL invalidates it by construction."""
    conn = reg.connect()
    try:
        before = list(reg._columns(conn, "research_candidates"))
        conn.execute('ALTER TABLE research_candidates ADD COLUMN "zz_probe" TEXT')
        conn.commit()
        after = reg._columns(conn, "research_candidates")
        assert "zz_probe" in after
        assert "zz_probe" not in before
    finally:
        conn.close()
