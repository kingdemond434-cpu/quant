"""Backup watch (rule E40): a stale, unarmed, unverified or box-local backup pages, and the guardian
starts (or re-registers) the job; a fully verified off-site backup is PASS and silent."""
from __future__ import annotations

import io
import json
import sys
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from libs.ops import backup_watch as bw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desks" / "mt5" / "scripts"))
import offsite_backup as ob  # noqa: E402

NOW = datetime(2026, 11, 25, 22, tzinfo=UTC)


def _good(**kw: object) -> dict[str, object]:
    t = (NOW - timedelta(hours=3)).isoformat()
    d: dict[str, object] = {"status": "OK", "last_success_at": t, "last_check_at": t,
                            "last_check_ok": True, "restore_drill": {"at": t, "verdict": "PASS"},
                            "offsite": True, "key_escrowed_off_box": True}
    d.update(kw)
    return d


def test_judge_every_flag() -> None:
    assert bw.judge({}, NOW) == ["NO_REPORT"]
    assert bw.judge(_good(), NOW) == []
    assert "STALE" in bw.judge(_good(last_success_at=(NOW - timedelta(hours=13)).isoformat()), NOW)
    assert "CHECK_STALE" in bw.judge(_good(last_check_ok=False), NOW)
    assert "DRILL_STALE" in bw.judge(_good(restore_drill={"at": NOW.isoformat(),
                                                          "verdict": "FAIL"}), NOW)
    assert bw.judge(_good(offsite=False), NOW) == ["LOCAL_ONLY"]
    assert bw.judge(_good(key_escrowed_off_box=False), NOW) == ["KEY_NOT_ESCROWED"]
    na = bw.judge({"status": "NOT_ARMED"}, NOW)
    assert na[:2] == ["NOT_ARMED", "STALE"] and "DRILL_STALE" in na


def test_never_backed_up_pages_and_repairs_bounded(tmp_path: Path) -> None:
    cmds: list[list[str]] = []
    pages: list[str] = []

    def runner(c: list[str]) -> bool:
        cmds.append(c)
        return True

    d = bw.run_once(tmp_path, now=NOW, runner=runner, page=pages.append)
    assert d["verdict"] == "BROKEN" and d["repair"] == "started"
    assert cmds == [["schtasks.exe", "/Run", "/TN", "MT5-OffsiteBackup"]]
    assert len(pages) == 1 and pages[0].startswith("BACKUP WATCH:")
    bw.run_once(tmp_path, now=NOW + timedelta(minutes=15), runner=runner, page=pages.append)
    assert len(cmds) == 1 and len(pages) == 1   # no repair storm, no page storm
    bw.run_once(tmp_path, now=NOW + timedelta(hours=7), runner=runner, page=pages.append)
    assert len(cmds) == 2 and len(pages) == 2


def test_missing_task_is_reregistered(tmp_path: Path) -> None:
    inst = tmp_path / bw.INSTALLER_REL
    inst.parent.mkdir(parents=True)
    inst.write_text("# installer")
    seen: list[str] = []

    def runner(c: list[str]) -> bool:
        seen.append(c[0])
        return c[0] == "powershell.exe" or seen.count("schtasks.exe") > 1

    assert bw.repair(tmp_path, runner) == "registered+started"
    assert seen == ["schtasks.exe", "powershell.exe", "schtasks.exe"]


def test_local_only_pages_daily_not_six_hourly(tmp_path: Path) -> None:
    rp = tmp_path / bw.REPORT_REL
    rp.parent.mkdir(parents=True)
    pages: list[str] = []
    for h in (0, 7, 25):
        now = NOW + timedelta(hours=h)
        t = (now - timedelta(hours=1)).isoformat()
        rp.write_text(json.dumps(_good(offsite=False, last_success_at=t)))
        d = bw.run_once(tmp_path, now=now, runner=lambda c: True, page=pages.append)
        assert d["verdict"] == "SOFT" and d["repair"] is None
    assert len(pages) == 2


def test_verified_offsite_is_silent(tmp_path: Path) -> None:
    rp = tmp_path / bw.REPORT_REL
    rp.parent.mkdir(parents=True)
    rp.write_text(json.dumps(_good()))
    pages: list[str] = []
    d = bw.run_once(tmp_path, now=NOW, runner=lambda c: False, page=pages.append)
    assert d["verdict"] == "PASS" and pages == [] and d["repair"] is None


def _zip(name: str = "restic_x.exe") -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr(name, b"MZ-restic")
    return b.getvalue()


def test_install_restic_verifies_pinned_sha(tmp_path: Path) -> None:
    import hashlib
    blob = _zip()
    want = hashlib.sha256(blob).hexdigest()
    exe, how = ob.install_restic(tmp_path / "r", want=want, fetch=lambda u: blob)
    assert exe and Path(exe).read_bytes() == b"MZ-restic" and "verified" in how
    exe, how = ob.install_restic(tmp_path / "s", want="0" * 64, fetch=lambda u: blob)
    assert exe is None and how.startswith("refused")
    assert not list((tmp_path / "s").glob("*"))
    def boom(u: str) -> bytes:
        raise OSError("offline")

    exe, how = ob.install_restic(tmp_path / "t", fetch=boom)
    assert exe is None and how.startswith("install failed")


def test_self_arm_writes_key_never_reports_it(tmp_path: Path) -> None:
    cfg = tmp_path / "secrets" / "offsite_backup.json"
    out = tmp_path / "o.json"
    d = ob.run(config=cfg, out=out, sources=(str(tmp_path / "nope"),), restic=None,
               self_arm=True, installer=lambda: (None, "install failed: offline"))
    assert cfg.exists() and d["self_armed"]["what"].startswith("armed")
    assert d["status"] == "NO_RESTIC" and d["restic_installed"]["what"] == "install failed: offline"
    pw = json.loads(cfg.read_text())["password"]
    assert pw not in out.read_text()
    # an existing config (the only key to its snapshots) is never replaced
    before = cfg.read_text()
    ob.run(config=cfg, out=out, sources=(), restic="", self_arm=True)
    assert cfg.read_text() == before
    # without self-arm the old recorded states stand
    d = ob.run(config=tmp_path / "none.json", out=out, sources=(), restic="r")
    assert d["status"] == "NOT_ARMED" and not (tmp_path / "none.json").exists()


def test_local_repo_prefers_a_non_system_volume() -> None:
    assert ob.local_repo_path(["C:\\", "D:\\"]).startswith("D:")
    assert ob.local_repo_path([]).replace("/", "\\").endswith("backup\\restic")
