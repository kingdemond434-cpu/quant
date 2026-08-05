"""Backup/restore, watchdog, and safe-halt orchestration."""

from __future__ import annotations

from pathlib import Path

from libs.ops.backup import BackupManager, RestoreDrill
from libs.ops.watchdog import ProcessWatchdog, SafeHaltController
from libs.risk.drawdown import DrawdownLevel
from libs.store.connection import Database


def test_backup_creates_verifiable_manifest(db: Database, db_path: Path, tmp_path: Path) -> None:
    db.execute("SELECT 1").fetchone()  # ensure the file exists/flushed
    mgr = BackupManager(source_db=db_path)
    dest = tmp_path / "backup"
    manifest = mgr.backup(dest)
    assert manifest.db_version == 7
    assert (dest / "sor.sqlite").exists()
    assert (dest / "manifest.json").exists()
    assert mgr.verify(dest, manifest) is True


def test_verify_detects_corruption(db: Database, db_path: Path, tmp_path: Path) -> None:
    mgr = BackupManager(source_db=db_path)
    dest = tmp_path / "backup"
    manifest = mgr.backup(dest)
    (dest / "sor.sqlite").write_bytes(b"corrupted")
    assert mgr.verify(dest, manifest) is False


def test_restore_drill_succeeds(db: Database, db_path: Path, tmp_path: Path) -> None:
    mgr = BackupManager(source_db=db_path)
    dest = tmp_path / "backup"
    manifest = mgr.backup(dest)
    assert RestoreDrill().run(dest, manifest, workdir=tmp_path / "restore") is True


def test_restore_drill_fails_on_tamper(db: Database, db_path: Path, tmp_path: Path) -> None:
    mgr = BackupManager(source_db=db_path)
    dest = tmp_path / "backup"
    manifest = mgr.backup(dest)
    (dest / "sor.sqlite").write_bytes(b"corrupted")
    assert RestoreDrill().run(dest, manifest, workdir=tmp_path / "restore") is False


def test_process_watchdog_action() -> None:
    wd = ProcessWatchdog(max_silence_seconds=10.0)
    assert wd.action(last_beat_epoch=0.0, now_epoch=5.0) == "ok"
    assert wd.action(last_beat_epoch=0.0, now_epoch=20.0) == "restart"


def test_safe_halt_fail_closed() -> None:
    ctrl = SafeHaltController()
    assert ctrl.evaluate().halt is False
    assert ctrl.evaluate(reconciliation_divergence=True).halt is True
    assert ctrl.evaluate(drawdown_level=DrawdownLevel.HALT).halt is True
    assert ctrl.evaluate(heartbeat_alive=False).halt is True
    decision = ctrl.evaluate(critical_alerts=2)
    assert decision.halt is True
    assert "2 unresolved critical alert(s)" in decision.reasons
    # a non-halt drawdown level alone does not halt
    assert ctrl.evaluate(drawdown_level=DrawdownLevel.MODERATE).halt is False
