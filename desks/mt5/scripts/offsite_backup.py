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
once a day; `check --read-data-subset` once a week, which downloads and decrypts a sample and is
the restore evidence (a backup nobody has read back is a claim, L1.49).

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
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
CONFIG = ROOT / "data" / "secrets" / "offsite_backup.json"
OUT = BASE / "reports" / "OFFSITE_BACKUP.json"
RESTIC_CANDIDATES = (r"C:\opt\restic\restic.exe", r"C:\ProgramData\chocolatey\bin\restic.exe")
#: Box-only data, in priority order. A path that does not exist is listed as missing, never an error.
SOURCES: tuple[str, ...] = (
    r"C:\moat\bronze",
    str(ROOT / "data" / "tape"),
    str(BASE / "data" / "tape"),
    os.path.expandvars(r"%APPDATA%\MetaQuotes\Terminal"),
)
#: Never shipped, whatever the config says.
EXCLUDES: tuple[str, ...] = ("**/secrets/**", "**/accounts.dat", "**/*.lock", "**/logs/**")
RETENTION = ("--keep-hourly", "24", "--keep-daily", "30", "--keep-weekly", "12",
             "--keep-monthly", "24")
PRUNE_EVERY = timedelta(hours=20)
CHECK_EVERY = timedelta(days=7)
CHECK_SUBSET = "2%"
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
    if not doc.get("key_escrowed_off_box"):
        return "KEY_NOT_ESCROWED", ("encrypted and verified, but the repository password is not "
                                    "attested as held off the box: a dead box takes the key")
    return "PASS", f"encrypted off-site snapshot {doc.get('last_success_at')}, read back OK"


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
