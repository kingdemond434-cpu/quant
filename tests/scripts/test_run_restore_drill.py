"""The restore drill restores a fixture backup and checks it against the live stores (audit I19,
2026-10-06: `scripts/run_restore_drill.py` had no test)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import run_restore_drill as drill


def _write(p: Path, doc: object) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), "utf-8")


def _live_and_backup(root: Path, *, backed_sleeves: int = 10) -> Path:
    sleeves = {f"S{i}": {"status": "LIVE"} for i in range(10)}
    _write(root / "desks/mt5/data/sleeve_registry.json", {"sleeves": sleeves})
    _write(root / "desks/mt5/reports/shadow/shadow_state.json", {"a": {}, "b": {}})
    _write(root / "desks/mt5/reports/UNIVERSAL_SURVIVORS.json", {"survivors": {"x": {}}})
    snap = root / "backups" / "moat" / "2026-10-06"
    _write(snap / "manifest.json", {"files": 3})
    _write(snap / "forward_registry",
           {"sleeves": {f"S{i}": {"status": "LIVE"} for i in range(backed_sleeves)}})
    _write(snap / "shadow_state" / "shadow_state.json", {"a": {}, "b": {}})
    _write(snap / "UNIVERSAL_SURVIVORS.json", {"survivors": {"x": {}}})
    return snap


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(drill, "ROOT", tmp_path)
    monkeypatch.setattr(drill, "OUT", tmp_path / "restore_drill.json")
    return tmp_path


def _verdict(root: Path) -> dict:
    return json.loads((root / "restore_drill.json").read_text("utf-8"))


def test_a_complete_backup_restores_and_reconciles(sandbox: Path) -> None:
    live = (sandbox / "desks/mt5/data/sleeve_registry.json").read_bytes()
    _live_and_backup(sandbox)
    assert drill.main() == 0
    v = _verdict(sandbox)
    assert v["status"] == "PASS"
    assert v["stores"]["forward_registry"] == {"backed_up": True, "parses": True,
                                               "restored_rows": 10, "live_rows": 10,
                                               "sufficient": True}
    assert all(s["sufficient"] for s in v["stores"].values())
    assert (sandbox / "desks/mt5/data/sleeve_registry.json").read_bytes() == live, (
        "the drill never touches a live path")


def test_a_backup_that_lost_clocks_fails(sandbox: Path) -> None:
    _live_and_backup(sandbox, backed_sleeves=8)        # 80% < the 90% floor
    assert drill.main() == 1
    v = _verdict(sandbox)
    assert v["status"] == "FAIL" and v["stores"]["forward_registry"]["sufficient"] is False


def test_an_unparseable_or_missing_store_fails(sandbox: Path) -> None:
    snap = _live_and_backup(sandbox)
    (snap / "forward_registry").write_text("{torn", "utf-8")
    (snap / "UNIVERSAL_SURVIVORS.json").unlink()
    assert drill.main() == 1
    v = _verdict(sandbox)
    assert v["stores"]["forward_registry"]["parses"] is False
    assert v["stores"]["universal_canon"] == {"backed_up": False}


def test_no_backup_is_named_never_passed(sandbox: Path) -> None:
    assert drill.main() == 1
    assert _verdict(sandbox)["status"] == "NO_BACKUP_FOUND"
