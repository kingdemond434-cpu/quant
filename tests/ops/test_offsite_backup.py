"""Off-site backup: unarmed and uninstalled are recorded states, secrets are never shipped, the
password never reaches the report, and ops_redundancy grades PASS only on a fresh, read-back,
key-escrowed snapshot."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desks" / "mt5" / "scripts"))

import offsite_backup as ob  # noqa: E402

NOW = datetime(2026, 9, 30, 12, tzinfo=UTC)


def _restored_fixture_path(target: Path, source: Path) -> Path:
    """A restic archive path under its restore root, including a Windows drive."""
    return target / source.as_posix().lstrip("/").replace(":", "")


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
            tgt = _restored_fixture_path(Path(cmd[cmd.index("--target") + 1]), src)
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
    assert "**/secrets/**" in b and "**/accounts.dat*" in b
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
            (_restored_fixture_path(root, good)).parent.mkdir(parents=True, exist_ok=True)
            (_restored_fixture_path(root, good)).write_text("{not json")     # restored but corrupt
        return subprocess.CompletedProcess(cmd, 0, nodes if cmd[1] == "ls" else "", "")

    rep = ob.restore_drill("restic", {}, runner, NOW)
    assert rep["verdict"] == "FAIL" and rep["counts"]["MISSING"] == 1
    assert rep["counts"]["CORRUPT"] == 1


def test_ops_redundancy_row_reads_the_report() -> None:
    sys.path.insert(0, str(ROOT / "desks" / "mt5"))
    from research import ops_redundancy as orr
    row = orr._offsite_backup_row()
    assert row["item"] == "encrypted_offbox_backup" and row["status"] != "PASS"


def test_restore_drill_identical_is_by_content_and_full_path(tmp_path: Path) -> None:
    """IDENTICAL is earned by bytes, not by a timestamp string in whichever zone restic used; and
    a restored file is found by its full path, never by a name another directory also uses."""
    a, b = tmp_path / "EURUSD" / "ticks.parquet", tmp_path / "GBPUSD" / "ticks.parquet"
    for p, body in ((a, b"PAR1-eur-PAR1"), (b, b"PAR1-gbp-PAR1")):
        p.parent.mkdir(parents=True)
        p.write_bytes(body)
    # restic's mtime is local time with an offset: it must not matter
    nodes = "\n".join(json.dumps({"struct_type": "node", "type": "file", "path": str(p),
                                   "size": p.stat().st_size,
                                   "mtime": "2026-09-30T14:00:00.000+02:00"}) for p in (a, b))

    def runner(cmd: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        if cmd[1] == "restore":
            root = Path(cmd[cmd.index("--target") + 1]) / "C"      # a drive component
            for p in (a, b):
                q = _restored_fixture_path(root, p)
                q.parent.mkdir(parents=True, exist_ok=True)
                q.write_bytes(p.read_bytes())
        return subprocess.CompletedProcess(cmd, 0, nodes if cmd[1] == "ls" else "", "")

    rep = ob.restore_drill("restic", {}, runner, NOW)
    assert rep["verdict"] == "PASS" and rep["counts"]["IDENTICAL"] == 2, rep

    def swapped(cmd: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        if cmd[1] == "restore":                       # only GBPUSD's file comes back
            q = _restored_fixture_path(Path(cmd[cmd.index("--target") + 1]) / "C", b)
            q.parent.mkdir(parents=True, exist_ok=True)
            q.write_bytes(b.read_bytes())
        return subprocess.CompletedProcess(cmd, 0, nodes if cmd[1] == "ls" else "", "")

    rep = ob.restore_drill("restic", {}, swapped, NOW)
    # EURUSD's file is MISSING, never graded against GBPUSD's same-named file
    assert rep["counts"]["MISSING"] == 1 and rep["counts"]["IDENTICAL"] == 1, rep


def test_the_file_list_never_holds_a_secret_and_lists_each_file_once(tmp_path: Path) -> None:
    """Secrets are out by construction: restic only ever sees this list (2026-10-29)."""
    desk = tmp_path / "desk"
    for rel in ("data/ledger.jsonl", "data/secrets/key.json", "data/Secrets/x.json",
                "data/tape/t.parquet", "term/accounts.dat", "term/ok.ini", "logs/a.log",
                "data/run.lock"):
        p = desk / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x")
    got = ob.files_to_ship([str(desk), str(desk / "data"), str(desk / "data" / "tape")])
    names = [Path(f).relative_to(desk).as_posix() for f in got]
    assert names == ["data/ledger.jsonl", "data/tape/t.parquet", "term/ok.ini"]


def test_secret_lookalikes_links_and_hard_links_never_enter_the_list(tmp_path: Path) -> None:
    """Audit of #483 MF2: a prefix, not an exact name, and links are fenced by what they are."""
    desk = tmp_path / "desk"
    secret = desk / "data" / "secrets" / "key.json"
    for rel in ("data/Secrets.bak/old.json", "data/secret_old/k.json", "term/accounts.dat.bak",
                "term/ACCOUNTS.DAT~", "data/ledger.jsonl", "data/secrets/key.json"):
        p = desk / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x")
    try:
        os.link(secret, desk / "data" / "innocent.json")          # same file, harmless name
        os.symlink(secret, desk / "data" / "alias.json")           # a link to a secret file
        os.symlink(desk / "data" / "secrets", desk / "data" / "cfg", target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"links unavailable here: {exc}")
    got = ob.files_to_ship([str(desk)], secret_dirs=())
    names = [Path(f).relative_to(desk).as_posix() for f in got]
    # the secrets dir is found by the walk itself, so the hard link is refused with no hint
    assert names == ["data/ledger.jsonl"], names


def test_a_hard_link_to_a_known_secrets_dir_outside_the_sources_is_refused(
        tmp_path: Path) -> None:
    vault = tmp_path / "vault" / "secrets"
    vault.mkdir(parents=True)
    (vault / "k.json").write_text("x")
    src = tmp_path / "src"
    src.mkdir()
    (src / "ok.json").write_text("y")
    try:
        os.link(vault / "k.json", src / "copy.json")
    except OSError as exc:
        pytest.skip(f"hard links unavailable here: {exc}")
    got = ob.files_to_ship([str(src)], secret_dirs=(str(vault),))
    assert [Path(f).name for f in got] == ["ok.json"]


def test_a_junction_is_never_walked(tmp_path: Path) -> None:
    if os.name != "nt":
        pytest.skip("junctions exist only on Windows")
    secrets_dir = tmp_path / "data" / "secrets"
    secrets_dir.mkdir(parents=True)
    (secrets_dir / "k.json").write_text("x")
    src = tmp_path / "src"
    src.mkdir()
    subprocess.run(["cmd", "/c", "mklink", "/J", str(src / "cfg"), str(secrets_dir)], check=True,
           capture_output=True)
    assert ob.files_to_ship([str(src)], secret_dirs=()) == []


def test_every_run_is_one_snapshot_series_whatever_the_file_list(tmp_path: Path) -> None:
    """Audit of #483 MF1: grouped by host,paths each run (a new file list) would be its own
    series, so forget would keep everything and backup would find no parent."""
    src = tmp_path / "ticks"
    src.mkdir()
    calls: list[list[str]] = []

    def runner(cmd: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        out = (json.dumps({"message_type": "summary", "snapshot_id": "s"})
               if cmd[1] == "backup" else "")
        return subprocess.CompletedProcess(cmd, 0, out, "")

    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"repository": str(tmp_path / "repo"), "password": "K"}))
    out = tmp_path / "o.json"
    for i, when in enumerate((NOW, NOW + timedelta(days=1))):
        (src / f"t{i}.parquet").write_bytes(b"PAR1xPAR1")      # the list grows every run
        ob.run(config=cfg, out=out, sources=(str(src),), restic="restic", runner=runner,
               now=when)
    for verb in ("backup", "forget"):
        runs = [c for c in calls if c[1] == verb]
        assert len(runs) == 2, verb
        for c in runs:
            i = c.index("--group-by")
            assert c[i + 1] == "host,tags", c


def test_the_backup_hands_restic_the_list_and_drills_every_source(tmp_path: Path) -> None:
    ledgers, ticks = tmp_path / "ledgers", tmp_path / "ticks"
    files = [ledgers / "l.json", *(ticks / f"t{i}.parquet" for i in range(40))]
    for f in files:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"PAR1xPAR1" if f.suffix == ".parquet" else b"{}")
    seen: dict[str, Any] = {}

    def runner(cmd: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        out = ""
        if cmd[1] == "backup":
            i = cmd.index("--files-from-verbatim")
            seen["listed"] = Path(cmd[i + 1]).read_text().split()
            out = json.dumps({"message_type": "summary", "snapshot_id": "s1"})
        if cmd[1] == "ls":
            out = "\n".join(json.dumps({"struct_type": "node", "type": "file", "path": str(f),
                                        "size": f.stat().st_size}) for f in files)
        if cmd[1] == "restore":
            inc = [cmd[i + 1] for i, a in enumerate(cmd) if a == "--include"]
            seen["restored"] = inc
            for f in inc:
                t = _restored_fixture_path(Path(cmd[cmd.index("--target") + 1]), Path(f))
                t.parent.mkdir(parents=True, exist_ok=True)
                t.write_bytes(Path(f).read_bytes())
        return subprocess.CompletedProcess(cmd, 0, out, "")

    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"repository": str(tmp_path / "repo"), "password": "K"}))
    d = ob.run(config=cfg, out=tmp_path / "o.json", sources=(str(ledgers), str(ticks)),
               restic="restic", runner=runner, now=NOW)
    assert sorted(seen["listed"]) == sorted(str(f) for f in files)
    assert str(ledgers / "l.json") in seen["restored"]   # 40 tick files cannot crowd it out
    assert d["restore_drill"]["verdict"] == "PASS"
    assert d["scheme"] == "local" and d["offsite"] is False


def test_a_local_repository_is_never_graded_off_site() -> None:
    drill = {"at": NOW.isoformat(), "verdict": "PASS", "why": "1/1"}
    base = {"status": "OK", "last_success_at": NOW.isoformat(), "last_check_at": NOW.isoformat(),
            "last_check_ok": True, "restore_drill": drill, "key_escrowed_off_box": True}
    assert ob.verdict({**base, "offsite": False}, NOW)[0] == "LOCAL_ONLY"
    assert ob.verdict({**base, "offsite": True}, NOW)[0] == "PASS"
    assert ob.is_remote("sftp:u@h:/q") and not ob.is_remote(r"C:\backup\restic")


def test_init_local_arms_once_and_never_prints_the_key(tmp_path: Path) -> None:
    cfg = tmp_path / "secrets" / "offsite_backup.json"
    msg = ob.init_local(r"C:\backup\restic", cfg)
    doc = json.loads(cfg.read_text())
    assert doc["repository"] == r"C:\backup\restic" and len(doc["password"]) >= 40
    assert doc["password"] not in msg and doc["key_escrowed_off_box"] is False
    assert ob.init_local(r"D:\other", cfg).startswith("kept")
    assert json.loads(cfg.read_text()) == doc   # the only key to its snapshots is never replaced
