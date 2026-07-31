#!/usr/bin/env python3
"""MOAT BACKUP (L1.23) -- the irreplaceable stores get an off-box replica through git.

THE T4 DEFECT INSIDE A T2 PROCESS (deep sweep 2026-07-31, DM-1 = infra F5): one disk holds the
only copy of stores that CANNOT be re-earned -- the execution tape (fills at our own timestamps),
the research memory, the SoR -- with a ~29-day fuse to the 80% disk guard, whose response is to
sacrifice the moat. libs/ops/backup.py existed the whole time with ZERO production callers (the
built-never-wired class, confirmed 2026-07-31: only its own tests import it).

THE DESIGN, honest about what it does and does not cover:
  COVERED (small, irreplaceable, fits in git): every store in _STORES is replicated into
  backups/moat/ -- sqlite via the online-backup API (consistent while open) + integrity check,
  files/dirs via copy -- with a sha256 manifest and a restore drill run ON EVERY BACKUP (a backup
  that never restored is a hope, not a backup). backups/ is NOT gitignored, so the box's
  10-minute snapshot/push cycle carries the replicas to GitHub: a second machine, different
  failure domain, zero cost, already running.
  NOT COVERED (recorded, never silent -- L1.28b's no-silent-caps rule): the L2 depth lake and
  bulk lake hours (multi-GB; git is the wrong transport). Their sizes are measured into the
  artifact each run so the gap is a number, not a vibe. Closing it is the standing EUR-4/mo
  Storage Box (or R2 free-tier) principal decision on PRINCIPAL_ACTION.
  DISK FUSE: free space below FUSE_PCT fails this fence loudly (exit 2) -- the 29-day countdown
  becomes a paged event long before the 80% guard starts eating the moat.

    python scripts/run_moat_backup.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent

# L1.42 LAWFUL ENTRY: this organ ran on a cron line that passed through no gate at
# all -- 60 manifest lines did. guard() verifies the sealed core and that the doctrine
# still carries every law family; it is TTL-cached (~0ms after the first call in a
# window) and pages-but-does-not-block, so a governance fault never silences an organ.
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

FUSE_PCT = 15.0          # free-disk % below which this fence FAILS (the fuse, pre-guard)
_MAX_FILE_MB = 64.0      # git-sane cap per file; larger files are SKIPPED and RECORDED

#: name -> (relative path, kind). Small and irreplaceable only -- regenerable artifacts do not
#: belong here (they cost cycles, not history). Absence is recorded, never silently skipped.
_STORES: dict[str, tuple[str, str]] = {
    "execution_tape": ("data/moat/execution_tape", "tree"),
    "research_memory": ("data/research_memory.db", "sqlite"),
    "sor_research": ("data/sor_research.sqlite", "sqlite"),
    "capital_events": ("data/capital_events.jsonl", "file"),
    "cost_model": ("data/cost_model.json", "file"),
    "graveyard": ("docs/graveyard.md", "file"),
}

#: Bulk stores git cannot carry -- measured every run so the uncovered gap stays a NUMBER.
_NOT_COVERED = ("data/lake", "data/moat")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _du(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) if path.is_dir() else 0


def _snapshot_sqlite(src: Path, dst: Path) -> str:
    """Consistent online snapshot + integrity check; returns the replica's sha256."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    con_src = sqlite3.connect(str(src))
    try:
        con_dst = sqlite3.connect(str(dst))
        try:
            con_src.backup(con_dst)
            ok = con_dst.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            con_dst.close()
    finally:
        con_src.close()
    if ok != "ok":
        raise RuntimeError(f"integrity_check failed on replica of {src}: {ok}")
    return _sha256(dst)


def _copy_capped(src: Path, dst: Path, skipped: list[dict[str, Any]]) -> dict[str, str]:
    """Copy file or tree, skipping (and RECORDING) anything over the git-sane cap."""
    digests: dict[str, str] = {}
    files = [src] if src.is_file() else sorted(p for p in src.rglob("*") if p.is_file())
    for f in files:
        rel = f.name if src.is_file() else str(f.relative_to(src))
        if f.stat().st_size > _MAX_FILE_MB * 1e6:
            skipped.append({"file": str(f.relative_to(_ROOT) if f.is_absolute() else f),
                            "bytes": f.stat().st_size,
                            "reason": f"over the {_MAX_FILE_MB}MB git-sane cap"})
            continue
        out = dst / rel if not src.is_file() else dst
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, out)
        digests[rel] = _sha256(out)
    return digests


def _drill(dest: Path, manifest: dict[str, Any]) -> bool:
    """Restore drill on EVERY run: sqlite replicas must integrity-check, files must re-hash."""
    for store, entry in manifest["stores"].items():
        if entry["status"] != "REPLICATED":
            continue
        base = dest / store
        for rel, digest in entry["sha256"].items():
            # file and sqlite replicas ARE the store path; only trees nest under it
            p = base / rel if entry["kind"] == "tree" else base
            if not p.exists() or _sha256(p) != digest:
                return False
        if entry["kind"] == "sqlite":
            con = sqlite3.connect(str(base))
            try:
                if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    return False
            finally:
                con.close()
    return True


def build_backup(root: Path, dest: Path | None = None,
                 free_pct: float | None = None) -> dict[str, Any]:
    dest = dest or root / "backups/moat"
    dest.mkdir(parents=True, exist_ok=True)
    skipped: list[dict[str, Any]] = []
    stores: dict[str, Any] = {}
    for name, (rel, kind) in _STORES.items():
        src = root / rel
        if not src.exists():
            stores[name] = {"status": "ABSENT", "kind": kind, "path": rel, "sha256": {},
                            "note": "store missing on this host -- recorded, not skipped silently"}
            continue
        target = dest / name
        if kind == "sqlite":
            digests = {name: _snapshot_sqlite(src, target)}
        else:
            if target.is_dir():
                shutil.rmtree(target)
            digests = _copy_capped(src, target, skipped)
        stores[name] = {"status": "REPLICATED", "kind": kind, "path": rel,
                        "bytes": _du(src), "sha256": digests}

    usage = shutil.disk_usage(root)
    free = free_pct if free_pct is not None else usage.free / usage.total * 100
    manifest: dict[str, Any] = {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.23 -- survival first: the moat is capital in information form",
        "stores": stores,
        "skipped_over_cap": skipped,
        "not_covered_bytes": {p: _du(root / p) for p in _NOT_COVERED if (root / p).exists()},
        "not_covered_note": "bulk lake/L2 need the Storage-Box/R2 principal decision -- "
                            "measured here every run so the gap stays a number",
        "disk_free_pct": round(free, 2),
        "fuse_pct": FUSE_PCT,
    }
    manifest["restore_drill_passed"] = _drill(dest, manifest)
    status = "OK"
    if free < FUSE_PCT:
        status = "DISK-FUSE"
    elif not manifest["restore_drill_passed"]:
        status = "DRILL-FAILED"
    elif all(s["status"] == "ABSENT" for s in stores.values()):
        status = "NOTHING-REPLICATED"
    manifest["status"] = status
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2), "utf-8")
    return manifest


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_backup(_ROOT)
    out = _ROOT / "data/backup_status.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    n_rep = sum(1 for s in rep["stores"].values() if s["status"] == "REPLICATED")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"moat backup (L1.23): {rep['status']} -- {n_rep}/{len(rep['stores'])} stores "
              f"replicated, drill={'PASS' if rep['restore_drill_passed'] else 'FAIL'}, "
              f"disk free {rep['disk_free_pct']}% (fuse {FUSE_PCT}%)")
        print(f"-> {out}")
    if args.report_only:
        return 0
    return 2 if rep["status"] in ("DISK-FUSE", "DRILL-FAILED", "NOTHING-REPLICATED") else 0


if __name__ == "__main__":
    sys.exit(main())
