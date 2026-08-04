"""Moat backup (L1.23) -- replicas are verified and drilled, gaps are numbers, the fuse fires."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.run_moat_backup import _STORES, FUSE_PCT, build_backup


def _seed(root: Path) -> None:
    """Seed the fixture from the PRODUCTION store list, never from an invented path.

    THE FIXTURE USED TO ASSERT THE WORLD BACKWARDS. It created `data/research_memory.db` -- a path
    that has NEVER existed on this desk -- and asserted it REPLICATED, while asserting that
    `sor_research`, which DOES exist in production, was ABSENT. So the suite was green on exactly
    the inverse of reality, and could not have caught a store being dropped from _STORES.

    A fixture built from the narrowest invented schema is structurally incapable of revealing what
    the code is blind to; this one is built from _STORES itself, so a store added there without a
    fixture entry shows up as a test failure rather than as silent non-coverage.
    """
    tape = root / "data/moat/execution_tape"
    tape.mkdir(parents=True)
    (tape / "cashcarry_trades.jsonl").write_text('{"fill": 1}\n{"fill": 2}\n', "utf-8")
    for name, (rel, kind) in _STORES.items():
        target = root / rel
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if kind == "sqlite":
            con = sqlite3.connect(str(target))
            con.execute("CREATE TABLE findings (id TEXT, note TEXT)")
            con.execute("INSERT INTO findings VALUES (?, ?)", ("F1", f"seeded for {name}"))
            con.commit()
            con.close()
        elif kind == "file":
            target.write_text('{"seeded": true}', "utf-8")


def test_backup_replicates_verifies_and_drills(tmp_path):
    _seed(tmp_path)
    rep = build_backup(tmp_path, free_pct=50.0)
    assert rep["status"] == "OK"
    assert rep["restore_drill_passed"] is True
    assert rep["stores"]["execution_tape"]["status"] == "REPLICATED"
    # EVERY declared store, not a hand-picked one -- that is what makes the fixture a coverage
    # check on _STORES rather than a spot check on whichever store the author remembered.
    for name in _STORES:
        assert rep["stores"][name]["status"] == "REPLICATED", f"{name} not replicated"
    # The replica actually restores: open it and read the row back.
    con = sqlite3.connect(str(tmp_path / "backups/moat/sor_research"))
    assert con.execute("SELECT id FROM findings").fetchone()[0] == "F1"
    con.close()


def test_absent_store_is_recorded_AND_degrades_the_status(tmp_path):
    """Absence used to be recorded and then TOLERATED: status stayed OK unless EVERY store was
    missing, so a backup covering one store of six reported the same verdict as a complete one.
    Declaring a store IS the claim that it is covered."""
    _seed(tmp_path)
    (tmp_path / "data/cost_model.json").unlink()
    rep = build_backup(tmp_path, free_pct=50.0)
    assert rep["stores"]["cost_model"]["status"] == "ABSENT"
    assert "recorded" in rep["stores"]["cost_model"]["note"]
    assert rep["status"] == "DEGRADED", "a missing irreplaceable store must not report OK"
    assert "cost_model" in rep["absent_stores"]


def test_disk_fuse_fails_loud(tmp_path):
    _seed(tmp_path)
    rep = build_backup(tmp_path, free_pct=FUSE_PCT - 1)
    assert rep["status"] == "DISK-FUSE"


def test_a_copy_that_was_WRONG_WHEN_WRITTEN_fails_the_drill(tmp_path, monkeypatch):
    """THE BUG THE OLD DRILL COULD NOT SEE. Digests were taken from the REPLICA, so a copy that
    was already corrupt at write time recorded its own corruption as the expected value and the
    drill confirmed it. Verified against the real code 2026-08-01: a truncating copyfile gave
    drill PASS under the old semantics and drill FAIL under source digests."""
    import shutil as _sh
    _seed(tmp_path)
    real = _sh.copyfile

    def truncating(src, dst, **kw):
        data = Path(src).read_bytes()
        Path(dst).write_bytes(data[: len(data) // 2])
        return dst

    monkeypatch.setattr(_sh, "copyfile", truncating)
    rep = build_backup(tmp_path, free_pct=50.0)
    monkeypatch.setattr(_sh, "copyfile", real)
    assert rep["restore_drill_passed"] is False, "a half-written copy must never certify itself"
    assert rep["status"] == "DRILL-FAILED"


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
