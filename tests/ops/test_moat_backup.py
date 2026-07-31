"""Moat backup (L1.23) -- replicas are verified and drilled, gaps are numbers, the fuse fires."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.run_moat_backup import FUSE_PCT, build_backup


def _seed(root: Path) -> None:
    tape = root / "data/moat/execution_tape"
    tape.mkdir(parents=True)
    (tape / "cashcarry_trades.jsonl").write_text('{"fill": 1}\n{"fill": 2}\n', "utf-8")
    db = root / "data/research_memory.db"
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE findings (id TEXT, note TEXT)")
    con.execute("INSERT INTO findings VALUES ('F1', 'negative result, first-class')")
    con.commit()
    con.close()
    (root / "data/cost_model.json").write_text('{"taker_bps": 4.5}', "utf-8")


def test_backup_replicates_verifies_and_drills(tmp_path):
    _seed(tmp_path)
    rep = build_backup(tmp_path, free_pct=50.0)
    assert rep["status"] == "OK"
    assert rep["restore_drill_passed"] is True
    assert rep["stores"]["execution_tape"]["status"] == "REPLICATED"
    assert rep["stores"]["research_memory"]["status"] == "REPLICATED"
    # The replica actually restores: open it and read the row back.
    con = sqlite3.connect(str(tmp_path / "backups/moat/research_memory"))
    assert con.execute("SELECT id FROM findings").fetchone()[0] == "F1"
    con.close()


def test_absent_store_is_recorded_never_silent(tmp_path):
    _seed(tmp_path)
    rep = build_backup(tmp_path)
    assert rep["stores"]["sor_research"]["status"] == "ABSENT"
    assert "recorded" in rep["stores"]["sor_research"]["note"]


def test_disk_fuse_fails_loud(tmp_path):
    _seed(tmp_path)
    rep = build_backup(tmp_path, free_pct=FUSE_PCT - 1)
    assert rep["status"] == "DISK-FUSE"


def test_corrupted_replica_fails_the_drill(tmp_path):
    _seed(tmp_path)
    build_backup(tmp_path)
    # Corrupt the tape replica AFTER manifest write, then re-verify via a fresh run's drill
    # against the stored manifest hashes.
    replica = tmp_path / "backups/moat/execution_tape/cashcarry_trades.jsonl"
    manifest = json.loads((tmp_path / "backups/moat/manifest.json").read_text("utf-8"))
    replica.write_text("corrupted\n", "utf-8")
    from scripts.run_moat_backup import _drill
    assert _drill(tmp_path / "backups/moat", manifest) is False


def test_uncovered_bulk_is_a_number(tmp_path):
    _seed(tmp_path)
    (tmp_path / "data/lake/bronze").mkdir(parents=True)
    (tmp_path / "data/lake/bronze/big.parquet").write_bytes(b"x" * 1000)
    rep = build_backup(tmp_path)
    assert rep["not_covered_bytes"]["data/lake"] >= 1000


def test_nothing_replicated_is_a_failure_not_a_pass(tmp_path):
    rep = build_backup(tmp_path, free_pct=50.0)  # no stores seeded at all
    assert rep["status"] == "NOTHING-REPLICATED"
