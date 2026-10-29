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

LOCAL FIRST (2026-10-29). The job never ran because it had nowhere to send to, so nothing on the
box had a versioned copy at all. `--init-local C:\\backup\\restic` writes the config with a
repository on this box's own disk and a random password (never printed), so snapshots, prune,
check and the restore drill start now. A local repository protects against deletion, corruption
and a bad deploy, not against losing the box: its verdict is LOCAL_ONLY, never PASS, until the
repository is pointed off-site.

LEDGERS, CERTS AND MOAT TOO (2026-10-29). The moat replica in git refuses the stores over 64 MB
(alpha_registry, shadow_ledgers) and was last written 2026-08-29, so the desk's own data dirs
are sources here as well. Restic deduplicates, so a source inside another costs nothing.

SECRETS BY CONSTRUCTION, NOT BY PATTERN. restic is handed an explicit file list
(`--files-from-verbatim`) built here, and no path with a component starting `secret` or a name
starting `accounts.dat` ever enters it, nor a symlink, a junction, a file whose real path is under
a secrets directory, or a hard link to a file there (see `files_to_ship`); the `--exclude`
patterns stay as a second fence. A Windows-path quirk in restic's own pattern matching can
therefore never ship a secret.

WHAT THE TERMINAL PROFILE SHIPS, ON PURPOSE. Everything under `%APPDATA%\\MetaQuotes\\Terminal`
except `accounts.dat*`, including `Config\\common.ini` (server names, the last login number and
terminal settings, no password): it is needed to rebuild the terminal, and it leaves the box only
as restic ciphertext.

WHO MUST BE ABLE TO READ THE CONFIG. MT5-OffsiteBackup runs as SYSTEM (install_offsite_backup_
task.ps1), which can read `data/secrets/offsite_backup.json` whoever wrote it; `--init-local` is
run from the same admin installer. If the task principal ever changes, it must keep read access
to that file, or every run is NOT_ARMED.

Writes `desks/mt5/reports/OFFSITE_BACKUP.json`, read by `research/ops_redundancy.py`.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import secrets
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
    # ledgers, sleeve registry, certs, shadow ledgers, the moat stores and their git replica
    str(BASE / "data"),
    str(BASE / "reports"),
    str(ROOT / "data"),
    str(ROOT / "backups"),
)
#: Repository schemes that live somewhere other than this box. Anything else (a drive path) is
#: local: versioned, but gone with the box.
REMOTE_SCHEMES = ("s3", "sftp", "rest", "b2", "azure", "gs", "swift", "rclone")
#: Path components and names that never enter the file list.
NEVER = ("secret",)   # a prefix: secrets, Secrets.bak, secret_old
NEVER_NAMES = ("accounts.dat",)
#: Where the box keeps its secrets: every file under these is refused by identity as well as by
#: name, so a hard link to one under another name never ships.
SECRET_DIRS: tuple[str, ...] = (str(ROOT / "data" / "secrets"), str(BASE / "data" / "secrets"))
#: Never shipped, whatever the config says.
EXCLUDES: tuple[str, ...] = ("**/secrets/**", "**/secret*/**", "**/accounts.dat*", "**/*.lock",
                             "**/logs/**")
#: ONE SNAPSHOT SERIES, WHATEVER THE FILE LIST. restic groups snapshots by host and paths by
#: default, and with `--files-from-verbatim` the paths are the file list, which changes every run
#: (a new tick file). Grouped that way every run is its own series: `forget` keeps each one (the
#: repository never shrinks) and `backup` finds no parent (a full re-read of ~75 GB every 6
#: hours). Grouping by host and tag makes every run one series. Audit of #483, MF1.
GROUP_BY = ("--group-by", "host,tags")
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


def _secretish(part: str) -> bool:
    """`secrets`, `Secrets.bak`, `secret_old`: any component that starts like one is one."""
    return part.lower().startswith(NEVER)


def _never_name(name: str) -> bool:
    low = name.lower()
    return low.startswith(NEVER_NAMES) or low.endswith(".lock")


def _is_link(p: str) -> bool:
    """A symlink or (on Windows) a junction, which os.walk follows: either can point a harmless
    name at data/secrets, so neither is ever walked into or shipped."""
    isjunction = getattr(os.path, "isjunction", None)
    return os.path.islink(p) or bool(isjunction and isjunction(p))


def _identity(p: str) -> tuple[int, int] | None:
    try:
        st = os.stat(p, follow_symlinks=False)
    except OSError:
        return None
    return (st.st_dev, st.st_ino) if st.st_ino else None


def _secret_identities(dirs: set[str]) -> set[tuple[int, int]]:
    """(device, inode) of every file under a secrets directory, so a hard link to one under an
    innocent name is still refused."""
    ids: set[tuple[int, int]] = set()
    for top in dirs:
        for d, _sub, names in os.walk(top):
            for n in names:
                i = _identity(os.path.join(d, n))
                if i:
                    ids.add(i)
    return ids


def files_to_ship(sources: list[str], secret_dirs: tuple[str, ...] | None = None) -> list[str]:
    """Every file under the sources except secrets, the broker login, locks and logs; each file
    once, however many sources contain it.

    FOUR FENCES, each enough alone (audit of #483): a path component that starts with `secret`
    (so `Secrets.bak` too) and a name that starts with `accounts.dat` are never listed; symlinks
    and junctions are never walked or listed; a file whose real path has a secret component is
    refused; and a file that is the same file (device, inode) as one under a secrets directory,
    i.e. a hard link, is refused."""
    found = {str(x) for x in (secret_dirs if secret_dirs is not None else SECRET_DIRS)}
    cand: set[str] = set()
    for src in sources:
        root = Path(src)
        if _is_link(str(root)) or any(_secretish(x) for x in root.parts):
            continue
        walk = [(str(root.parent), [], [root.name])] if root.is_file() else os.walk(root)
        for d, dirs, names in walk:
            keep = []
            for x in dirs:
                full = os.path.join(d, x)
                if _secretish(x):
                    found.add(full)
                elif x.lower() != "logs" and not _is_link(full):
                    keep.append(x)
            dirs[:] = keep
            if any(_secretish(part) for part in Path(d).parts):
                continue
            for n in names:
                full = os.path.join(d, n)
                if _never_name(n) or _is_link(full):
                    continue
                cand.add(full)
    banned = _secret_identities({x for x in found if os.path.isdir(x)})
    out = []
    for f in cand:
        if any(_secretish(part) for part in Path(os.path.realpath(f)).parts):
            continue
        if banned and _identity(f) in banned:
            continue
        out.append(f)
    return sorted(out)


def is_remote(repository: str) -> bool:
    return str(repository).split(":", 1)[0].lower() in REMOTE_SCHEMES


def _scheme(repository: str) -> str:
    return str(repository).split(":", 1)[0].lower() if is_remote(repository) else "local"


def init_local(path: str, config: Path = CONFIG) -> str:
    """Arm a repository on this box's disk with a fresh random password. Never overwrites a
    config that exists (that one holds the only key to its snapshots) and never prints the key."""
    if config.exists():
        return f"kept: {config.name} already exists"
    config.parent.mkdir(parents=True, exist_ok=True)
    doc = {"repository": path, "password": secrets.token_urlsafe(32),
           "key_escrowed_off_box": False}
    config.write_text(json.dumps(doc, indent=1), "utf-8")
    return f"armed: local repository, key in {config.name} (copy it off the box to escrow it)"


def _snap_root(src: str) -> str:
    """A source as restic writes it in a snapshot: `C:\\x\\y` -> `/C/x/y`."""
    p = src.replace("\\", "/")
    if len(p) > 1 and p[1] == ":":
        p = "/" + p[0] + p[2:]
    return p.rstrip("/")


def _sample(nodes: list[dict[str, Any]], k: int = RESTORE_FILES,
            roots: list[str] | None = None) -> list[dict[str, Any]]:
    """Up to k restorable files, spread across the snapshot: every n-th of the size-bounded files
    in path order, so the drill touches every source rather than one directory. With `roots`, the
    k are shared out source by source (a file belongs to the longest root containing it), so the
    tick archive's file count cannot crowd the ledgers out of the drill."""
    files = sorted((n for n in nodes if n.get("type") == "file"
                    and 0 < int(n.get("size") or 0) <= RESTORE_MAX_BYTES),
                   key=lambda n: str(n.get("path")))
    if not roots:
        step = max(1, len(files) // k) if files else 1
        return files[::step][:k]
    snap = sorted({_snap_root(r) for r in roots}, key=len, reverse=True)
    groups: dict[str, list[dict[str, Any]]] = {}
    for n in files:
        path = str(n.get("path")).replace("\\", "/")
        owner = next((r for r in snap if path == r or path.startswith(r + "/")), "")
        groups.setdefault(owner, []).append(n)
    per = max(1, -(-k // max(1, len(groups))))
    pick: list[dict[str, Any]] = []
    for owner in sorted(groups):
        g = groups[owner]
        step = max(1, len(g) // per)
        pick.extend(g[::step][:per])
    return pick


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
                  now: datetime | None = None,
                  roots: list[str] | None = None) -> dict[str, Any]:
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
    pick = _sample(nodes, roots=roots)
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
        doc.update(status="DRY_RUN", scheme=_scheme(cfg["repository"]))
    else:
        doc["scheme"] = _scheme(cfg["repository"])
        doc["offsite"] = is_remote(cfg["repository"])
        env = {**os.environ, **{str(k): str(v) for k, v in (cfg.get("env") or {}).items()},
               "RESTIC_REPOSITORY": str(cfg["repository"]),
               "RESTIC_PASSWORD": str(cfg["password"])}
        probe = runner([exe, "cat", "config"], env)
        if probe.returncode != 0:
            init = runner([exe, "init"], env)
            doc["initialised"] = init.returncode == 0
        ex = [a for e in EXCLUDES for a in ("--exclude", e)]
        listing = files_to_ship(have)
        doc["files_listed"] = len(listing)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt",
                                         delete=False) as fl:
            fl.write("\n".join(listing) + "\n")
        try:
            b = runner([exe, "backup", "--json", "--tag", "quant-box", "--exclude-caches",
                        *GROUP_BY, *ex, "--files-from-verbatim", fl.name], env)
        finally:
            with contextlib.suppress(OSError):
                os.unlink(fl.name)
        # restic exits 3 when some source files could not be read (a tick file mid-write):
        # the snapshot exists and covers everything else, so it is a success with a warning.
        doc["backup"] = {"exit": b.returncode, **_summary(b.stdout)}
        ok = b.returncode in (0, 3) and bool(doc["backup"].get("snapshot_id"))
        if ok:
            doc["last_success_at"] = doc["at"]
            if _due(prev, "last_prune_at", PRUNE_EVERY, now):
                f = runner([exe, "forget", "--tag", "quant-box", *GROUP_BY, *RETENTION,
                            "--prune"], env)
                doc["prune_exit"] = f.returncode
                if f.returncode == 0:
                    doc["last_prune_at"] = doc["at"]
            if _due(prev, "last_check_at", CHECK_EVERY, now):
                c = runner([exe, "check", f"--read-data-subset={CHECK_SUBSET}"], env)
                doc["last_check_at"], doc["last_check_ok"] = doc["at"], c.returncode == 0
            last_drill = _ts((doc.get("restore_drill") or {}).get("at"))
            if last_drill is None or now - last_drill >= RESTORE_EVERY:
                try:
                    doc["restore_drill"] = restore_drill(exe, env, runner, now, roots=have)
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
    if doc.get("offsite") is False:
        return "LOCAL_ONLY", ("versioned, read back and restore-drilled, but the repository is on "
                              "this box: losing the box loses it. Point it off-site.")
    if not doc.get("key_escrowed_off_box"):
        return "KEY_NOT_ESCROWED", ("encrypted and verified, but the repository password is not "
                                    "attested as held off the box: a dead box takes the key")
    return "PASS", (f"encrypted off-site snapshot {doc.get('last_success_at')}, read back OK, "
                    f"restore drill {rd.get('why')}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--init-local", metavar="PATH",
                    help="arm a repository on this box's disk with a random key, then exit")
    a = ap.parse_args(argv)
    if a.init_local:
        print(init_local(a.init_local))
        return 0
    doc = run(dry_run=a.dry_run)
    print(json.dumps({k: doc.get(k) for k in ("status", "included", "missing",
                                              "last_success_at")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
