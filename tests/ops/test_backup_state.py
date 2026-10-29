"""BACKUP_STATE.json (v5f): the fields, no secrets, the 8-day restore-drill page, absent means
UNMEASURED (and pages, never OK). Every test runs on a temp tree with a fake sender."""

from __future__ import annotations

import importlib.util
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("backup_state_under_test",
                                               ROOT / "ops" / "backup_state.py")
assert _spec and _spec.loader
bs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bs)

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
#: Things that must never reach the published file. The source reports below carry every one.
SECRETS = ("hunter2-repo-password", "s3:https://user5551234:pw@backup.example/repo",
           "C:\\Users\\acct7000001\\AppData", "5551234", "7000001",
           "3f2a9c0d1e2b4a5f6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b",
           "restic-key-0123456789abcdef", "account_key.hmac", "data/secrets")


class _Pages:
    def __init__(self, delivered: int = 1) -> None:
        self.sent: list[tuple[str, str]] = []
        self.delivered = delivered

    def __call__(self, title: str, body: str) -> dict[str, Any]:
        self.sent.append((title, body))
        return {"armed": 1, "delivered": self.delivered}


@pytest.fixture
def box(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(bs, "ROOT", tmp_path)
    monkeypatch.setattr(bs, "_PAGED", set())
    monkeypatch.setattr(bs, "_LAST_TRY", {})
    monkeypatch.setattr(bs, "_key_backup", lambda: {
        "state": "OK", "present": True, "size_bytes": 32, "matches": True, "box_local": True})
    pages = _Pages()
    monkeypatch.setattr(bs, "SENDER", pages)
    monkeypatch.setattr(bs, "_default_sender",
                        lambda **_k: pytest.fail("the real sender was reached"))
    (tmp_path / "desks" / "mt5" / "reports").mkdir(parents=True)
    (tmp_path / "data").mkdir()
    return tmp_path


def _reports(box: Path) -> Path:
    return box / "desks" / "mt5" / "reports"


def _offsite(box: Path, drill_age_days: float | None, verdict: str = "PASS") -> None:
    doc: dict[str, Any] = {
        "at": (NOW - timedelta(hours=2)).isoformat(),
        "status": "OK",
        "included": ["C:\\moat\\bronze", "C:\\Users\\acct7000001\\AppData\\MetaQuotes\\Terminal"],
        "missing": [],
        "encryption": "restic AES-256 (client side)",
        "last_success_at": (NOW - timedelta(hours=2)).isoformat(),
        "last_check_at": (NOW - timedelta(days=1)).isoformat(),
        "last_check_ok": True,
        "last_prune_at": (NOW - timedelta(hours=20)).isoformat(),
        "key_escrowed_off_box": True,
        # free text the real job writes: restic stderr naming the repository, with a login in it
        "why": "Fatal: unable to open repo at s3:https://user5551234:pw@backup.example/repo",
        "backup": {"snapshot": "3f2a9c0d1e2b4a5f6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b"},
        "password": "hunter2-repo-password",
        "restic_key": "restic-key-0123456789abcdef",
    }
    if drill_age_days is not None:
        doc["restore_drill"] = {"at": (NOW - timedelta(days=drill_age_days)).isoformat(),
                                "verdict": verdict,
                                "why": "3/3 restored from C:\\Users\\acct7000001 ok"}
    (_reports(box) / "OFFSITE_BACKUP.json").write_text(json.dumps(doc), "utf-8")


def _others(box: Path) -> None:
    (_reports(box) / "OPS_REDUNDANCY.json").write_text(json.dumps({
        "generated_utc": NOW.isoformat(), "status": "PARTIAL",
        "offbox_restore_drill": {"status": "PASS", "path": "data/secrets/x"}}), "utf-8")
    # PowerShell's Set-Content -Encoding UTF8 writes a BOM
    (_reports(box) / "REBOOT_DRILL.json").write_text("\ufeff" + json.dumps({
        "checked_at": NOW.isoformat(), "verdict": "PASS", "failures": [],
        "required": ["MT5-Gateway"]}), "utf-8")
    (box / "data" / "backup_status.json").write_text(json.dumps({
        "generated": NOW.isoformat(), "status": "OK", "restore_drill_passed": True,
        "stores": {"ledger": {"path": "C:\\Users\\acct7000001\\x", "sha256": SECRETS[5]}},
        "absent_stores": []}), "utf-8")
    (_reports(box) / "restore_drill.json").write_text(json.dumps({
        "drilled_at": NOW.isoformat(), "status": "PASS", "backup": "/home/acct7000001/b"}), "utf-8")


def test_the_fields(box: Path) -> None:
    _offsite(box, 2.0)
    _others(box)
    doc = bs.build(NOW)
    assert doc["schema"] == "backup_state/1" and doc["host"]
    assert doc["last_backup_at"] == (NOW - timedelta(hours=2)).isoformat(timespec="seconds")
    assert doc["last_restore_drill_at"] == (NOW - timedelta(days=2)).isoformat(timespec="seconds")
    assert doc["restore_drill"]["state"] == "OK" and doc["restore_drill"]["max_age_days"] == 8
    off = doc["offsite"]
    assert off["job"] == "MT5-OffsiteBackup" and off["state"] == "OK"
    assert off["verdict"] == "PASS"   # offsite_backup.verdict's own state, not its sentence
    assert off["encrypted"] is True and off["key_escrowed_off_box"] is True
    assert off["n_included"] == 2 and off["n_missing"] == 0 and off["last_check_ok"] is True
    assert doc["ops_redundancy"] == {"state": "PARTIAL", "at": NOW.isoformat(timespec="seconds"),
                                     "offbox_restore_drill": "PASS"}
    assert doc["reboot_drill"]["state"] == "PASS" and doc["reboot_drill"]["n_failures"] == 0
    assert doc["moat"]["backup"]["state"] == "OK" and doc["moat"]["backup"]["n_stores"] == 1
    assert doc["moat"]["restore_drill"]["state"] == "PASS"
    assert doc["key_backup"] == {"state": "OK", "present": True, "size_bytes": 32,
                                 "matches": True, "box_local": True}
    assert doc["status"] == "OK"


def test_no_secret_no_path_no_hash_no_account_reaches_the_file(box: Path) -> None:
    _offsite(box, 2.0)
    _others(box)
    bs.write(NOW)
    text = (_reports(box) / "BACKUP_STATE.json").read_text("utf-8")
    for s in SECRETS:
        assert s not in text, s
    assert not re.search(r"[0-9a-f]{32,}", text), "a hash-shaped string was published"
    assert not re.search(r"[A-Za-z]:\\\\|/home/|/Users/|s3:|https?://", text), "a path or URL"


def test_the_key_backup_is_present_size_match_only_and_never_its_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import sys
    import types
    fake = types.ModuleType("libs.ops.provenance")
    fake.key_backup_state = lambda: {  # type: ignore[attr-defined]
        "path": "C:\\ProgramData\\quant-keys\\account_key.hmac", "state": "mismatch",
        "present": True, "size_bytes": 32, "matches": False}
    monkeypatch.setitem(sys.modules, "libs.ops.provenance", fake)
    import libs.ops
    monkeypatch.setattr(libs.ops, "provenance", fake, raising=False)
    kb = bs._key_backup()
    assert kb == {"state": "MISMATCH", "present": True, "size_bytes": 32, "matches": False,
                  "box_local": True}


def test_the_writer_moves_nothing_off_the_box() -> None:
    src = (ROOT / "ops" / "backup_state.py").read_text("utf-8")
    for verb in ("shutil.copy", "copyfile", "upload", "requests.", "urllib", "subprocess",
                 "socket.create_connection"):
        assert verb not in src, verb


@pytest.mark.parametrize("age", [8.5, 30.0])
def test_a_restore_drill_older_than_8_days_pages(box: Path, age: float) -> None:
    _offsite(box, age)
    doc = bs.write(NOW)
    assert doc["restore_drill"]["state"] == "STALE" and doc["status"] == "ATTENTION"
    [(title, body)] = bs.SENDER.sent
    assert "STALE" in title and "8" in body
    assert doc["page"]["sent"] is True


def test_a_drill_inside_8_days_does_not_page(box: Path) -> None:
    _offsite(box, 7.9)
    doc = bs.write(NOW)
    assert doc["restore_drill"]["state"] == "OK"
    assert bs.SENDER.sent == []


def test_a_failed_drill_pages_even_when_recent(box: Path) -> None:
    _offsite(box, 1.0, verdict="FAIL")
    doc = bs.write(NOW)
    assert doc["restore_drill"]["state"] == "FAILED" and doc["status"] == "ATTENTION"
    assert len(bs.SENDER.sent) == 1


@pytest.mark.parametrize("how", ["no report", "report without a drill", "unreadable report"])
def test_absent_is_unmeasured_and_pages_never_ok(box: Path, how: str) -> None:
    if how == "report without a drill":
        _offsite(box, None)
    elif how == "unreadable report":
        (_reports(box) / "OFFSITE_BACKUP.json").write_text("{not json", "utf-8")
    doc = bs.write(NOW)
    assert doc["restore_drill"]["state"] == "UNMEASURED"
    assert doc["status"] == "UNMEASURED" and doc["status"] != "OK"
    assert doc["last_restore_drill_at"] is None
    assert len(bs.SENDER.sent) == 1, "an absent restore drill pages"
    for k in ("ops_redundancy", "reboot_drill"):
        assert doc[k]["state"] == "UNMEASURED"


def test_the_page_is_deduplicated_and_recovery_pages_once(
    monkeypatch: pytest.MonkeyPatch, box: Path
) -> None:
    _offsite(box, 10.0)
    bs.write(NOW)
    bs.write(NOW)
    monkeypatch.setattr(bs, "_PAGED", set())   # a fresh process: the state file dedups
    bs.write(NOW)
    assert len(bs.SENDER.sent) == 1
    _offsite(box, 1.0)
    bs.write(NOW)
    bs.write(NOW)
    monkeypatch.setattr(bs, "_PAGED", set())
    bs.write(NOW)
    assert [t for t, _ in bs.SENDER.sent][1].startswith("Restore drill recovered")
    assert len(bs.SENDER.sent) == 2


def test_an_undelivered_page_is_not_a_page(monkeypatch: pytest.MonkeyPatch, box: Path) -> None:
    monkeypatch.setattr(bs, "SENDER", _Pages(delivered=0))
    doc = bs.write(NOW)   # absent drill
    assert doc["page"]["sent"] is False
    assert not (box / "desks" / "mt5" / "logs" / "backup_state_page.json").exists()
    monkeypatch.setattr(bs, "_LAST_TRY", {})
    monkeypatch.setattr(bs, "SENDER", _Pages(delivered=1))
    assert bs.write(NOW)["page"]["sent"] is True


def test_a_sender_that_raises_never_breaks_the_report(
    monkeypatch: pytest.MonkeyPatch, box: Path
) -> None:
    def boom(title: str, body: str) -> dict[str, Any]:
        raise RuntimeError("channel down")

    monkeypatch.setattr(bs, "SENDER", boom)
    doc = bs.write(NOW)
    assert doc["page"]["sent"] is False
    assert (_reports(box) / "BACKUP_STATE.json").exists()


def test_a_source_sentence_is_never_copied_as_a_state(box: Path) -> None:
    (_reports(box) / "OPS_REDUNDANCY.json").write_text(json.dumps(
        {"status": "see C:\\Users\\acct7000001\\notes"}), "utf-8")
    assert bs.build(NOW)["ops_redundancy"]["state"] == "UNRECOGNISED"


def test_it_is_in_the_publish_set_and_on_an_hourly_clock() -> None:
    sync = (ROOT / "desks" / "mt5" / "scripts" / "sync_shadow_to_git.ps1").read_text("utf-8")
    assert '"desks/mt5/reports/BACKUP_STATE.json"' in sync
    assert "!desks/mt5/reports/BACKUP_STATE.json" in (ROOT / ".gitignore").read_text("utf-8")
    for f in ("libs/ops/release.py", "desks/mt5/mt5desk/release_identity.py"):
        assert '"desks/mt5/reports/BACKUP_STATE.json"' in (ROOT / f).read_text("utf-8"), f
    ph = (ROOT / "ops" / "process_health.py").read_text("utf-8")
    assert "_backup_state()" in ph.split("def main", 1)[1]


def test_process_health_never_writes_the_real_report_from_a_moved_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    spec = importlib.util.spec_from_file_location("ph_for_backup",
                                                  ROOT / "ops" / "process_health.py")
    assert spec and spec.loader
    ph = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ph)
    monkeypatch.setattr(ph, "ROOT", tmp_path)
    assert ph._backup_state().startswith("SKIPPED")
