"""Off-site backup: unarmed and uninstalled are recorded states, secrets are never shipped, the
password never reaches the report, and ops_redundancy grades PASS only on a fresh, read-back,
key-escrowed snapshot."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desks" / "mt5" / "scripts"))

import offsite_backup as ob  # noqa: E402

NOW = datetime(2026, 9, 30, 12, tzinfo=UTC)


def _cfg(tmp: Path, **extra: Any) -> Path:
    p = tmp / "offsite_backup.json"
    p.write_text(json.dumps({"repository": "s3:https://x/bucket/q?key=CRED",
                             "password": "PW-SECRET", **extra}))
    return p


def test_unarmed_and_no_restic(tmp_path: Path) -> None:
    src = (str(tmp_path),)
    d = ob.run(config=tmp_path / "none.json", out=tmp_path / "o.json", sources=src, restic="r")
    assert d["status"] == "NOT_ARMED"
    d = ob.run(config=_cfg(tmp_path), out=tmp_path / "o.json", sources=src, restic="")
    assert d["status"] == "NO_RESTIC"


def test_backup_prune_check_and_nothing_secret_written(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    envs: list[dict[str, str]] = []

    src = tmp_path / "tape.json"
    src.write_text('{"tick": 1}')

    def runner(cmd: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        envs.append(env)
        out = (json.dumps({"message_type": "summary", "snapshot_id": "abc", "data_added": 9})
               if cmd[1] == "backup" else "")
        if cmd[1] == "ls":
            out = json.dumps({"struct_type": "node", "type": "file", "path": str(src),
                              "size": src.stat().st_size})
        if cmd[1] == "restore":
            tgt = Path(cmd[cmd.index("--target") + 1]) / str(src).lstrip("/")
            tgt.parent.mkdir(parents=True, exist_ok=True)
            tgt.write_text(src.read_text())
        return subprocess.CompletedProcess(cmd, 0, out, "")

    out = tmp_path / "o.json"
    d = ob.run(config=_cfg(tmp_path, key_escrowed_off_box=True), out=out,
               sources=(str(tmp_path), str(tmp_path / "gone")), restic="restic",
               runner=runner, now=NOW)
    assert d["status"] == "OK" and d["backup"]["snapshot_id"] == "abc"
    assert [c[1] for c in calls] == ["cat", "backup", "forget", "check", "ls", "restore"]
    assert d["restore_drill"]["verdict"] == "PASS", d["restore_drill"]
    assert d["restore_drill"]["counts"]["MISSING"] == 0
    b = next(c for c in calls if c[1] == "backup")
    assert "**/secrets/**" in b and "**/accounts.dat" in b
    assert envs[0]["RESTIC_PASSWORD"] == "PW-SECRET"
    text = out.read_text()
    assert "PW-SECRET" not in text and "CRED" not in text and '"scheme": "s3"' in text
    assert d["missing"] == [str(tmp_path / "gone")]
    assert ob.verdict(d, NOW) == ("PASS", ob.verdict(d, NOW)[1])
    calls.clear()
    ob.run(config=_cfg(tmp_path, key_escrowed_off_box=True), out=out, sources=(str(tmp_path),),
           restic="restic", runner=runner, now=NOW + timedelta(hours=6))
    assert [c[1] for c in calls] == ["cat", "backup"]


def test_verdict_ladder() -> None:
    assert ob.verdict({}, NOW)[0] == "UNMEASURED"
    assert ob.verdict({"status": "NOT_ARMED", "why": "x"}, NOW)[0] == "NOT_ARMED"
    base = {"status": "OK", "last_success_at": NOW.isoformat(),
            "last_check_at": NOW.isoformat(), "last_check_ok": True}
    assert ob.verdict({**base, "last_success_at": (NOW - timedelta(days=2)).isoformat()},
                      NOW)[0] == "STALE"
    assert ob.verdict({**base, "last_check_ok": False}, NOW)[0] == "UNVERIFIED"
    # decrypting is not restoring: no restore drill, or a failed or old one, is UNVERIFIED
    assert ob.verdict({**base, "key_escrowed_off_box": True}, NOW)[0] == "UNVERIFIED"
    drill = {"at": NOW.isoformat(), "verdict": "PASS", "why": "1/1"}
    old = {**drill, "at": (NOW - timedelta(days=9)).isoformat()}
    assert ob.verdict({**base, "restore_drill": {**drill, "verdict": "FAIL"}}, NOW)[0] == \
        "UNVERIFIED"
    assert ob.verdict({**base, "restore_drill": old}, NOW)[0] == "UNVERIFIED"
    base = {**base, "restore_drill": drill}
    assert ob.verdict(base, NOW)[0] == "KEY_NOT_ESCROWED"
    assert ob.verdict({**base, "key_escrowed_off_box": True}, NOW)[0] == "PASS"


def test_restore_drill_names_missing_and_corrupt_files(tmp_path: Path) -> None:
    good, bad = tmp_path / "a.json", tmp_path / "b.json"
    good.write_text("{}")
    bad.write_text("{}")
    nodes = "\n".join(json.dumps({"struct_type": "node", "type": "file", "path": str(p),
                                   "size": 2}) for p in (good, bad))

    def runner(cmd: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        if cmd[1] == "restore":
            root = Path(cmd[cmd.index("--target") + 1])
            (root / str(good).lstrip("/")).parent.mkdir(parents=True, exist_ok=True)
            (root / str(good).lstrip("/")).write_text("{not json")     # restored but corrupt
        return subprocess.CompletedProcess(cmd, 0, nodes if cmd[1] == "ls" else "", "")

    rep = ob.restore_drill("restic", {}, runner, NOW)
    assert rep["verdict"] == "FAIL" and rep["counts"]["MISSING"] == 1
    assert rep["counts"]["CORRUPT"] == 1


def test_ops_redundancy_row_reads_the_report() -> None:
    sys.path.insert(0, str(ROOT / "desks" / "mt5"))
    from research import ops_redundancy as orr
    row = orr._offsite_backup_row()
    assert row["item"] == "encrypted_offbox_backup" and row["status"] != "PASS"
