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
import re
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

#: Table identifiers safe to interpolate into a COUNT(*) -- sqlite cannot bind a table name.
_SAFE_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

#: name -> (relative path, kind). Small and irreplaceable only -- regenerable artifacts do not
#: belong here (they cost cycles, not history). Absence is recorded, never silently skipped.
_STORES: dict[str, tuple[str, str]] = {
    "execution_tape": ("data/moat/execution_tape", "tree"),
    # data/research_memory.db REMOVED 2026-08-01: it is a PHANTOM. It has never existed on this
    # host, so it recorded ABSENT on every run since the backup was built -- padding the store
    # count with a store that can never be backed up, and making "4/6 replicated" read as a
    # shortfall when the real figure was 4/4 of what exists. The same phantom path has four
    # readers elsewhere (rowed as R0079, repoint to sor_research.sqlite). A backup must not
    # declare coverage of a file nobody writes.
    # "sor_research" MOVED TO BULK 2026-08-26: added 2026-08-01 at 487KB, it grew 1300x to
    # 637MB and the covered-class assumption ("small, fits in git") rotted silently -- the
    # 04:04Z replica was rejected by GitHub's 100MB pre-receive hook, so the off-box copy
    # this class promises never existed. It is now a measured-bulk store (uncovered gap
    # stays a NUMBER every run); _COVERED_MAX_BYTES below prevents the class from rotting
    # silently again for any store.
    "alpha_registry": ("data/alpha_registry.sqlite", "sqlite"),
    "capital_events": ("data/capital_events.jsonl", "file"),
    # FORWARD EVIDENCE (added 2026-08-27): the 14-day clocks are time that cannot be re-earned.
    # The registry was re-based to day zero three times in 32 hours before atomic writes fixed
    # the writer -- and had these been in the backup, the evidence would have been recoverable
    # instead of gone. Every store here rides the existing sha256 manifest + per-backup drill.
    "forward_registry": ("desks/mt5/data/sleeve_registry.json", "file"),
    "shadow_state": ("desks/mt5/reports/shadow/shadow_state.json", "file"),
    "shadow_ledgers": ("desks/mt5/reports/shadow", "tree"),
    "universal_canon": ("desks/mt5/reports/UNIVERSAL_SURVIVORS.json", "file"),
    "cost_model": ("data/cost_model.json", "file"),
    "graveyard": ("docs/graveyard.md", "file"),
}

#: Bulk stores git cannot carry -- measured every run so the uncovered gap stays a NUMBER.
_NOT_COVERED = ("data/lake", "data/moat", "data/sor_research.sqlite")

#: A covered store larger than this cannot reach the off-box replica (GitHub pre-receive
#: rejects >100MB), so bundling it manufactures a replica that LOOKS covered and can never
#: push. Refuse loudly instead: the store reports OVERSIZED (degraded), and the fix is a
#: deliberate reclassification or a real bulk route -- never a silent giant bundle.
_COVERED_MAX_BYTES = 50 * 1024 * 1024


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


def _table_census(con: sqlite3.Connection) -> dict[str, int]:
    """{table: row_count} -- the content-level fingerprint a byte hash cannot provide here.

    A sqlite backup is deliberately NOT byte-identical to its source (page ordering, freelist,
    vacuum state), so `_sha256(src) == _sha256(dst)` is the wrong assertion for this kind. Row
    counts per table ARE comparable across the two, and they catch the failure that matters: a
    replica that opened, integrity-checked clean, and copied a fraction of the data.
    """
    tabs = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    out: dict[str, int] = {}
    for t in tabs:
        # A table name cannot be bound as a parameter in sqlite, so it is VALIDATED instead. These
        # names come from our own sqlite_master rather than any external input, but a whitelist is
        # cheap and the alternative is a bare noqa that stops being true the day someone reuses
        # this helper on an attacker-influenced database.
        if not _SAFE_IDENT.fullmatch(t):
            raise RuntimeError(f"refusing to census a table with an unsafe identifier: {t!r}")
        out[t] = int(con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0])  # noqa: S608
    return out


def _snapshot_sqlite(src: Path, dst: Path) -> tuple[str, dict[str, int]]:
    """Consistent online snapshot, integrity check, AND a source-vs-replica content comparison.

    THE DRILL USED TO CERTIFY ITSELF. This returned `_sha256(dst)` -- the REPLICA's hash -- which
    `_drill` then re-derived from that same replica and compared. The two were the same bytes read
    twice, so the check could only ever detect corruption arriving BETWEEN the copy and the drill,
    and never a bad copy. Measured 2026-08-01: 4/6 stores REPLICATED, drill PASS, on a run whose
    correctness nothing had actually tested. A backup whose verification compares the copy to
    itself is worse than none -- it is an untested backup carrying a certificate.

    The comparison now runs against the SOURCE: table-by-table row counts must match. Raises rather
    than returning a bad replica, because a backup that knows it is wrong must never be recorded as
    a backup.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    con_src = sqlite3.connect(str(src))
    try:
        src_census = _table_census(con_src)
        con_dst = sqlite3.connect(str(dst))
        try:
            con_src.backup(con_dst)
            ok = con_dst.execute("PRAGMA integrity_check").fetchone()[0]
            dst_census = _table_census(con_dst)
        finally:
            con_dst.close()
    finally:
        con_src.close()
    if ok != "ok":
        raise RuntimeError(f"integrity_check failed on replica of {src}: {ok}")
    if dst_census != src_census:
        missing = {t: (src_census.get(t), dst_census.get(t))
                   for t in set(src_census) | set(dst_census)
                   if src_census.get(t) != dst_census.get(t)}
        raise RuntimeError(
            f"replica of {src} does not match its source (table: src_rows -> dst_rows): {missing}")
    return _sha256(dst), src_census


def _copy_capped(src: Path, dst: Path, skipped: list[dict[str, Any]]) -> dict[str, str]:
    """Copy file or tree, skipping (and RECORDING) anything over the git-sane cap.

    THE DIGEST IS TAKEN FROM THE SOURCE, and that one word is the whole difference between a real
    restore drill and a self-certifying one. This used to record `_sha256(out)` -- the copy's own
    hash -- which `_drill` then recomputed from the same file and compared to itself. It passed
    unconditionally, including on a truncated or empty copy.
    """
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
        digests[rel] = _sha256(f)          # SOURCE, never `out` -- see the docstring
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
        if _du(src) > _COVERED_MAX_BYTES:
            # The sor_research lesson (2026-08-26): a covered store that outgrows the off-box
            # route must go LOUD, never become a giant bundle the remote pre-receive rejects --
            # that replica looks covered and can never push, the worst of both.
            stores[name] = {"status": "OVERSIZED", "kind": kind, "path": rel,
                            "bytes": _du(src), "sha256": {},
                            "note": f"source exceeds the {_COVERED_MAX_BYTES // (1024*1024)}MB "
                                    "covered-class cap -- reclassify to measured-bulk or "
                                    "provision a real bulk route; a silent giant bundle is "
                                    "refused by design"}
            continue
        target = dest / name
        census: dict[str, int] | None = None
        if kind == "sqlite":
            digest, census = _snapshot_sqlite(src, target)
            digests = {name: digest}
        else:
            if target.is_dir():
                shutil.rmtree(target)
            digests = _copy_capped(src, target, skipped)
        stores[name] = {"status": "REPLICATED", "kind": kind, "path": rel,
                        "bytes": _du(src), "sha256": digests}
        if census is not None:
            stores[name]["table_rows"] = census

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
    # A DECLARED STORE THAT IS MISSING IS A DEGRADATION, NOT A DETAIL. This used to reach "OK"
    # unless EVERY store was absent, so a backup covering one store out of six reported the same
    # verdict as a complete one. Absence is now surfaced in the status itself -- the whole purpose
    # of declaring a store is the claim that it is covered, and a claim nobody checks is the
    # unmeasured-reports-OK class. (The phantom research_memory.db, which made this fire on every
    # historical run for a file that never existed, is removed from _STORES above -- the fix for a
    # store that cannot exist is to stop declaring it, never to tolerate absence generally.)
    absent = sorted(n for n, s in stores.items() if s["status"] == "ABSENT")
    oversized = sorted(n for n, s in stores.items() if s["status"] == "OVERSIZED")
    manifest["absent_stores"] = absent
    manifest["oversized_stores"] = oversized
    status = "OK"
    if free < FUSE_PCT:
        status = "DISK-FUSE"
    elif not manifest["restore_drill_passed"]:
        status = "DRILL-FAILED"
    elif all(s["status"] == "ABSENT" for s in stores.values()):
        status = "NOTHING-REPLICATED"
    elif absent or oversized:
        status = "DEGRADED"
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
    if rep.get("absent_stores"):
        print(f"   ABSENT (declared but missing): {', '.join(rep['absent_stores'])}")
    if rep.get("oversized_stores"):
        print(f"   OVERSIZED (outgrew the covered class, refused loudly): "
              f"{', '.join(rep['oversized_stores'])}")
    if args.report_only:
        return 0
    # DEGRADED joins the failing set: every store here is declared "small and irreplaceable", so a
    # missing one is unbacked irreplaceable data, which is exactly what this organ exists to
    # prevent. It cannot cry wolf on a fresh host -- no stores at all is NOTHING-REPLICATED.
    return 2 if rep["status"] in (
        "DISK-FUSE", "DRILL-FAILED", "NOTHING-REPLICATED", "DEGRADED") else 0


if __name__ == "__main__":
    sys.exit(main())
