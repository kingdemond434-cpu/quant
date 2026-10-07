#!/usr/bin/env python3
"""Encrypted, off-site, versioned backup of what exists ONLY on the trading box.

    python desks/mt5/scripts/offsite_backup.py            # MT5-OffsiteBackup, every 6 hours
    python desks/mt5/scripts/offsite_backup.py --dry-run  # say what would be backed up

WHY (infra survey, 2026-09-30). Code and ledgers reach git every 15 minutes, so the repo is its
own backup. What does not reach git has no copy anywhere off the machine: `C:\\moat\\bronze`
(recorded ticks, ~7 GB, cannot be re-downloaded), `data\\tape` (~7 GB) and the terminal's own
profile (charts, templates, MQL5). `ops/migrate_to_new_box.ps1` copies them box to box, which
protects against nothing that takes the box. `ops_redundancy` has reported the gap as
`encrypted_offbox_backup: NOT_ENCRYPTED` since it was written.

HOW. restic: client-side AES-256 encryption (the destination only ever holds ciphertext),
content-addressed deduplication (a 6-hourly run uploads only new ticks) and versioned snapshots
with a retention policy. One run: `backup` every time; `forget --prune` with the retention below
once a day; `check --read-data-subset` once a week, which downloads and decrypts a sample; and a
RESTORE DRILL once a week, which is the restore evidence (a backup nobody has read back is a
claim, L1.49). `check` proves the packs decrypt; it never writes a file back to disk or compares
one with the original, so on its own it is not a restore. The drill restores a bounded sample of
files from the latest snapshot into a temporary directory and compares each with the box's copy:
byte-identical when the source is unchanged since the snapshot, otherwise readable as its format
(JSON parses, Parquet carries its magic, any other file is non-empty). Recovery drills, 2026-10-06.

WHAT NEVER LEAVES THE BOX, encrypted or not: `data/secrets/**` (standing law) and the terminal's
`accounts.dat` (the broker login). Both are hard exclusions below, not configuration.

CONFIG, on the box only: `data/secrets/offsite_backup.json`
    {"repository": "s3:https://<endpoint>/<bucket>/quant-box" | "sftp:u@host:/path" | "rest:...",
     "password": "<restic repository password>",
     "env": {"AWS_ACCESS_KEY_ID": "...", "AWS_SECRET_ACCESS_KEY": "..."},
     "key_escrowed_off_box": true}
The repository password is the ONLY key to the data: `key_escrowed_off_box` is the operator's
attestation that a copy is held somewhere that is not this box (without it a dead box takes the
key with it and the backup is unreadable). Absent config: NOT_ARMED. Absent restic: NO_RESTIC.
Both are recorded states and exit 0. Nothing here prints the password, the env or the repository
URL (which can carry a credential); the report carries the scheme only.

Writes `desks/mt5/reports/OFFSITE_BACKUP.json`, read by `research/ops_redundancy.py`.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
CONFIG = ROOT / "data" / "secrets" / "offsite_backup.json"
OUT = BASE / "reports" / "OFFSITE_BACKUP.json"
RESTIC_CANDIDATES = (r"C:\opt\restic\restic.exe", r"C:\ProgramData\chocolatey\bin\restic.exe")
#: Box-only data, in priority order. A path that does not exist is listed as missing, never an
#: error.
SOURCES: tuple[str, ...] = (
    r"C:\moat\bronze",
    str(ROOT / "data" / "tape"),
    str(BASE / "data" / "tape"),
    os.path.expandvars(r"%APPDATA%\MetaQuotes\Terminal"),
    # FIRST-SEEN VINTAGES (ARCH-26, 2026-10-07): `acquire_datasets` appends what each publisher's
    # file said every time the box read it. The store is gitignored (it is parquet) and cannot be
    # re-downloaded -- a publisher that restates history no longer serves its old values -- so a
    # lost disk would lose every revised source's point-in-time record AND the authority earned
    # on it. Small (a few rows a series a day); restic deduplicates the unchanged prefix.
    str(BASE / "data" / "acquired" / "vintages"),
)
#: Never shipped, whatever the config says.
EXCLUDES: tuple[str, ...] = ("**/secrets/**", "**/accounts.dat", "**/*.lock", "**/logs/**")
RETENTION = ("--keep-hourly", "24", "--keep-daily", "30", "--keep-weekly", "12",
             "--keep-monthly", "24")
PRUNE_EVERY = timedelta(hours=20)
CHECK_EVERY = timedelta(days=7)
CHECK_SUBSET = "2%"
RESTORE_EVERY = timedelta(days=7)
#: The drill's sample: at most this many files, none larger than this, so a weekly drill costs
#: minutes and megabytes rather than a full download of the tick archive.
RESTORE_FILES = 24
RESTORE_MAX_BYTES = 32 * 1024 * 1024
TIMEOUT_S = 5 * 3600


def restic_bin() -> str | None:
    return shutil.which("restic") or next((c for c in RESTIC_CANDIDATES if Path(c).exists()), None)


def _load(p: Path) -> dict[str, Any]:
    with contextlib.suppress(OSError, ValueError):
        d = json.loads(p.read_text("utf-8"))
        return d if isinstance(d, dict) else {}
    return {}


def _ts(x: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(x))
    except ValueError:
        return None


def _due(prev: dict[str, Any], key: str, every: timedelta, now: datetime) -> bool:
    t = _ts(prev.get(key))
    return t is None or now - t >= every


def _run(cmd: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=TIMEOUT_S,
                          check=False)


def _summary(stdout: str) -> dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        with contextlib.suppress(ValueError):
            d = json.loads(line)
            if isinstance(d, dict) and d.get("message_type") == "summary":
                return {k: d.get(k) for k in ("snapshot_id", "data_added", "files_new",
                                              "files_changed", "total_files_processed",
                                              "total_bytes_processed", "total_duration")}
    return {}


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _readable(p: Path) -> bool:
    """Is a restored file usable as its format? JSON parses, Parquet has its magic both ends,
    anything else is non-empty."""
    try:
        if p.suffix.lower() == ".json":
            json.loads(p.read_text("utf-8"))
            return True
        if p.suffix.lower() == ".parquet":
            with p.open("rb") as f:
                head = f.read(4)
                f.seek(-4, os.SEEK_END)
                return head == b"PAR1" and f.read(4) == b"PAR1"
        return p.stat().st_size > 0
    except (OSError, ValueError):
        return False


def _sample(nodes: list[dict[str, Any]], k: int = RESTORE_FILES) -> list[dict[str, Any]]:
    """Up to k restorable files, spread across the snapshot: every n-th of the size-bounded files
    in path order, so the drill touches every source rather than one directory."""
    files = sorted((n for n in nodes if n.get("type") == "file"
                    and 0 < int(n.get("size") or 0) <= RESTORE_MAX_BYTES),
                   key=lambda n: str(n.get("path")))
    step = max(1, len(files) // k) if files else 1
    return files[::step][:k]


def _restored_at(target: Path, snap_path: str) -> Path | None:
    """Where restic wrote `snap_path` under `target`, matched on the FULL path below the drive.

    restic keeps a Windows drive as a leading component (`/C/opt/...`), so the direct join can
    miss; the fallback matches every component after the drive, never the bare file name -- tick
    archives reuse one name across symbol directories, and a name match would grade one symbol's
    file against another's source."""
    parts = [p for p in snap_path.replace("\\", "/").split("/") if p and p != "."]
    if not parts:
        return None
    rel = "/".join(parts[1:] if len(parts) > 1 and parts[0].rstrip(":").isalpha()
                   and len(parts[0].rstrip(":")) == 1 else parts)
    for cand in target.rglob(parts[-1]):
        if cand.is_file() and cand.relative_to(target).as_posix().endswith(rel):
            return cand
    return None


def restore_drill(exe: str, env: dict[str, str], runner: Any = _run,
                  now: datetime | None = None) -> dict[str, Any]:
    """Restore a sample of the latest snapshot to a temp directory and compare it with the box.

    PASS needs at least one file restored and every restored file either byte-identical to its
    unchanged source or readable as its format; a file the snapshot lists but the restore did not
    write is a failure. Never touches the sources: the target is a fresh temporary directory."""
    now = now or datetime.now(tz=UTC)
    rep: dict[str, Any] = {"at": now.isoformat(timespec="seconds")}
    ls = runner([exe, "ls", "--json", "latest", "--tag", "quant-box"], env)
    if ls.returncode != 0:
        rep.update(verdict="FAIL", why=f"restic ls latest exit {ls.returncode}")
        return rep
    nodes = []
    for line in ls.stdout.splitlines():
        with contextlib.suppress(ValueError):
            d = json.loads(line)
            if isinstance(d, dict) and d.get("struct_type") == "node":
                nodes.append(d)
    pick = _sample(nodes)
    if not pick:
        rep.update(verdict="FAIL", why="the latest snapshot lists no restorable file")
        return rep
    with tempfile.TemporaryDirectory(prefix="restore_drill_") as tmp:
        inc = [a for n in pick for a in ("--include", str(n["path"]))]
        r = runner([exe, "restore", "latest", "--tag", "quant-box", "--target", tmp, *inc], env)
        rep["restore_exit"] = r.returncode
        files: list[dict[str, Any]] = []
        for n in pick:
            snap_path = str(n["path"])
            got = Path(tmp) / snap_path.lstrip("/").replace(":", "")
            if not got.exists():
                got = _restored_at(Path(tmp), snap_path) or got
            row: dict[str, Any] = {"path": snap_path, "size": n.get("size")}
            if not got.exists():
                row["result"] = "MISSING"
            else:
                src = Path(snap_path[1] + ":" + snap_path[2:]) if (
                    os.name == "nt" and len(snap_path) > 2 and snap_path[0] == "/"
                    and snap_path[2] == "/") else Path(snap_path)
                same = False
                # CONTENT, NEVER TIMESTAMPS: restic reports mtime in the box's local zone, so a
                # string compare against a UTC stamp never matched off-UTC and IDENTICAL could not
                # occur. Same size and same SHA-256 is identical; a source edited since the
                # snapshot differs and falls through to the format check, as it should.
                with contextlib.suppress(OSError):
                    same = (src.stat().st_size == got.stat().st_size
                            and _sha256(src) == _sha256(got))
                row["result"] = ("IDENTICAL" if same else
                                 "READABLE" if _readable(got) else "CORRUPT")
            files.append(row)
    rep["files"] = files
    bad = [f for f in files if f["result"] in ("MISSING", "CORRUPT")]
    rep["counts"] = {k: sum(1 for f in files if f["result"] == k)
                     for k in ("IDENTICAL", "READABLE", "MISSING", "CORRUPT")}
    rep["verdict"] = "FAIL" if bad or r.returncode != 0 else "PASS"
    rep["why"] = (f"{len(files) - len(bad)}/{len(files)} sampled files restored and verified"
                  if not bad else f"{len(bad)} sampled file(s) missing or corrupt after restore")
    return rep


def run(*, dry_run: bool = False, config: Path = CONFIG, out: Path = OUT,
        sources: tuple[str, ...] = SOURCES, runner: Any = _run,
        restic: str | None = None, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    prev = _load(out)
    cfg = _load(config)
    have = [s for s in sources if s and Path(s).exists()]
    doc: dict[str, Any] = {
        "at": now.isoformat(timespec="seconds"), "included": have,
        "missing": [s for s in sources if s not in have], "excludes": list(EXCLUDES),
        "retention": " ".join(RETENTION), "encryption": "restic AES-256 (client side)",
        "last_success_at": prev.get("last_success_at"), "last_prune_at": prev.get("last_prune_at"),
        "last_check_at": prev.get("last_check_at"), "last_check_ok": prev.get("last_check_ok"),
        "restore_drill": prev.get("restore_drill"),
        "key_escrowed_off_box": bool(cfg.get("key_escrowed_off_box")),
    }
    exe = restic if restic is not None else restic_bin()
    if not cfg.get("repository") or not cfg.get("password"):
        doc.update(status="NOT_ARMED", why=f"no repository/password in {config.name}; the box-"
                                            "only data has no off-site copy")
    elif not exe:
        doc.update(status="NO_RESTIC", why="restic is not installed (C:\\opt\\restic\\restic.exe "
                                           "or on PATH)")
    elif not have:
        doc.update(status="FAIL", why="none of the box-only sources exists on this machine")
    elif dry_run:
        doc.update(status="DRY_RUN", scheme=str(cfg["repository"]).split(":", 1)[0])
    else:
        doc["scheme"] = str(cfg["repository"]).split(":", 1)[0]
        env = {**os.environ, **{str(k): str(v) for k, v in (cfg.get("env") or {}).items()},
               "RESTIC_REPOSITORY": str(cfg["repository"]),
               "RESTIC_PASSWORD": str(cfg["password"])}
        probe = runner([exe, "cat", "config"], env)
        if probe.returncode != 0:
            init = runner([exe, "init"], env)
            doc["initialised"] = init.returncode == 0
        ex = [a for e in EXCLUDES for a in ("--exclude", e)]
        b = runner([exe, "backup", "--json", "--tag", "quant-box", "--exclude-caches",
                    *ex, *have], env)
        # restic exits 3 when some source files could not be read (a tick file mid-write):
        # the snapshot exists and covers everything else, so it is a success with a warning.
        doc["backup"] = {"exit": b.returncode, **_summary(b.stdout)}
        ok = b.returncode in (0, 3) and bool(doc["backup"].get("snapshot_id"))
        if ok:
            doc["last_success_at"] = doc["at"]
            if _due(prev, "last_prune_at", PRUNE_EVERY, now):
                f = runner([exe, "forget", "--tag", "quant-box", *RETENTION, "--prune"], env)
                doc["prune_exit"] = f.returncode
                if f.returncode == 0:
                    doc["last_prune_at"] = doc["at"]
            if _due(prev, "last_check_at", CHECK_EVERY, now):
                c = runner([exe, "check", f"--read-data-subset={CHECK_SUBSET}"], env)
                doc["last_check_at"], doc["last_check_ok"] = doc["at"], c.returncode == 0
            last_drill = _ts((doc.get("restore_drill") or {}).get("at"))
            if last_drill is None or now - last_drill >= RESTORE_EVERY:
                try:
                    doc["restore_drill"] = restore_drill(exe, env, runner, now)
                except Exception as exc:   # a drill that cannot run is a failed drill
                    doc["restore_drill"] = {"at": doc["at"], "verdict": "FAIL",
                                            "why": f"{type(exc).__name__}: {exc}"[:300]}
        doc["status"] = "OK" if ok else "FAIL"
        if not ok:
            doc["why"] = (b.stderr or "").strip().splitlines()[-1][:300] if b.stderr else \
                f"restic backup exit {b.returncode}"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1), "utf-8")
    return doc


def verdict(doc: dict[str, Any], now: datetime | None = None) -> tuple[str, str]:
    """What `ops_redundancy` reports for the off-box backup gap row."""
    now = now or datetime.now(tz=UTC)
    if not doc:
        return "UNMEASURED", "no OFFSITE_BACKUP.json: MT5-OffsiteBackup has not run on this box"
    st = str(doc.get("status"))
    if st in ("NOT_ARMED", "NO_RESTIC"):
        return st, str(doc.get("why", ""))
    last, chk = _ts(doc.get("last_success_at")), _ts(doc.get("last_check_at"))
    if last is None or now - last > timedelta(hours=36):
        return "STALE", f"last encrypted off-site snapshot {doc.get('last_success_at')}"
    if chk is None or now - chk > timedelta(days=8) or not doc.get("last_check_ok"):
        return "UNVERIFIED", "snapshots exist but no passing read-back check in 8 days"
    rd = doc.get("restore_drill") or {}
    rd_at = _ts(rd.get("at"))
    if rd_at is None or now - rd_at > timedelta(days=8) or rd.get("verdict") != "PASS":
        return "UNVERIFIED", ("snapshots decrypt, but no passing RESTORE drill in 8 days: "
                              f"{rd.get('why') or 'never restored'}")
    if not doc.get("key_escrowed_off_box"):
        return "KEY_NOT_ESCROWED", ("encrypted and verified, but the repository password is not "
                                    "attested as held off the box: a dead box takes the key")
    return "PASS", (f"encrypted off-site snapshot {doc.get('last_success_at')}, read back OK, "
                    f"restore drill {rd.get('why')}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = run(dry_run=a.dry_run)
    print(json.dumps({k: doc.get(k) for k in ("status", "included", "missing",
                                              "last_success_at")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
