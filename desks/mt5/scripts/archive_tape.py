"""Move old tick-tape day-partitions OFF the box, verifying every byte before deleting one.

WHY THIS EXISTS. `reclaim_disk.py` frees space by deleting things that can be rebuilt -- caches,
duplicate discovery rows, bar parquets the terminal will re-serve in minutes. It refuses, at every
threshold and in every mode, to touch `data/tape`, because a broker-native tick that was not
recorded cannot be re-downloaded from anywhere at any price. That refusal is correct and it is
also why the disk cannot be fixed by deletion alone: measured on the box 2026-09-07, C: was at
0.1 GB free with a 5.664 GB tick tape on it. Caches and duplicate rows came to 0.007 GB between
them. The tape IS the disk problem, and the only honest answer to an irreplaceable 5.664 GB is to
MOVE it, not to shrink it.

WHAT MAKES THIS SAFE, AND IT IS NOT CARE. Every reader of the tape takes a bounded tail:

    research/orthogonal_sweep._ticks    sorted(d.glob("*.parquet"))[-30:]
    research/edge_search                sorted(tape_dir.glob("*.parquet"))[-30:]
    research/mined_ground               WINDOW_DAYS = 7
    build_zentech_state (moat_coverage) files with mtime inside 7 days

So nothing on this desk reads a partition older than thirty days. `KEEP_DAYS` is 45 and the flag
refuses to go below `READER_WINDOW_DAYS + 5`: the archive can never ship a file out from under a
reader that was going to open it. That is a property of the retention arithmetic, not a promise
about timing.

AGE COMES FROM THE FILENAME, NEVER FROM mtime. `tape.record_ticks` appends by read-concat-rewrite,
so a partition holding March ticks carries today's mtime the moment one late tick lands in it, and
an mtime rule would both keep that file forever and, on the other side, archive a file that was
rewritten today. The name IS the UTC day the ticks belong to. A partition whose name does not
parse as a date is skipped entirely -- an undateable file is never archived, because the one thing
worse than a full disk is moving a tick you could not account for.

DELETE ONLY AFTER THE COPY READS BACK IDENTICAL. Row count, column set and a SHA-256 of the file's
own bytes are compared against the destination after the copy lands. A mismatch leaves the source
exactly where it was and reports a failure; there is no mode, flag or threshold in this file that
removes a source partition that has not been verified at its destination first.

WHAT STAYS BEHIND. `data/tape/ARCHIVE_MANIFEST.jsonl` -- one append-only line per moved partition
carrying symbol, day, rows, bytes, digest and destination. A few hundred KB for the whole tape. A
tick archived to a place nobody recorded is lost in the same way as a tick never recorded, so the
index stays on the box even when the bytes do not.

    python desks/mt5/scripts/archive_tape.py --dest D:\\tape-archive             # measure only
    python desks/mt5/scripts/archive_tape.py --dest D:\\tape-archive --apply     # move
    python desks/mt5/scripts/archive_tape.py --dest D:\\tape-archive --verify    # re-check
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import UTC, date, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
TAPE = BASE / "data" / "tape"
TICKS = TAPE / "ticks"
MANIFEST = TAPE / "ARCHIVE_MANIFEST.jsonl"
REPORT = BASE / "reports" / "TAPE_ARCHIVE.json"

#: The longest tail any reader on this desk takes (orthogonal_sweep and edge_search: last 30
#: files). Retention is measured against THIS, so the two move together if a reader ever widens.
READER_WINDOW_DAYS = 30
#: Days of tape that stay resident. Fifteen days of headroom over the widest reader.
KEEP_DAYS = 45
#: Destination must hold the batch with room to spare -- a copy that fills the far side leaves
#: BOTH disks full and the source still undeleted, which is strictly worse than not starting.
SPACE_HEADROOM = 1.10


def _gb(n: int) -> float:
    return round(n / (1024 ** 3), 3)


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _shape(path: Path) -> tuple[int, tuple[str, ...]] | None:
    """(row count, column names) from the parquet FOOTER -- no column data is read.

    Returns None for a file pyarrow cannot open, which is how a torn partition is detected: it is
    reported and left alone rather than copied somewhere and deleted here.
    """
    try:
        import pyarrow.parquet as pq
        md = pq.ParquetFile(str(path))
        return int(md.metadata.num_rows), tuple(md.schema_arrow.names)
    except Exception:
        return None


def _day_of(path: Path) -> date | None:
    """The UTC day this partition holds, from its NAME. None when the name is not a date."""
    try:
        return date.fromisoformat(path.stem)
    except ValueError:
        return None


def _free_bytes(path: Path) -> int | None:
    try:
        return shutil.disk_usage(str(path)).free
    except OSError:
        return None


def _inside(child: Path, parent: Path) -> bool:
    try:
        c, p = child.resolve(), parent.resolve()
    except OSError:
        return True                     # unresolvable: treat as inside and refuse
    return c == p or p in c.parents


def candidates(keep_days: int, today: date | None = None) -> tuple[list[dict], dict]:
    """Partitions older than the retention window, with why each other file was left.

    The skip reasons are returned rather than logged because "nothing to archive" and "everything
    was undateable" look identical from the outside and mean opposite things.
    """
    today = today or datetime.now(UTC).date()
    out: list[dict] = []
    skipped = {"resident": 0, "undateable": 0, "not_a_file": 0}
    if not TICKS.exists():
        return out, {"note": "no tick tape on this host", **skipped}
    for sym_dir in sorted(p for p in TICKS.iterdir() if p.is_dir()):
        for f in sorted(sym_dir.glob("*.parquet")):
            if not f.is_file():
                skipped["not_a_file"] += 1
                continue
            day = _day_of(f)
            if day is None:
                skipped["undateable"] += 1
                continue
            if (today - day).days <= keep_days:
                skipped["resident"] += 1
                continue
            try:
                size = f.stat().st_size
            except OSError:
                skipped["not_a_file"] += 1
                continue
            out.append({"symbol": sym_dir.name, "day": day.isoformat(),
                        "path": f, "bytes": size})
    out.sort(key=lambda r: (r["day"], r["symbol"]))
    return out, skipped


def _verified_copy(src: Path, dst: Path) -> tuple[bool, str]:
    """Copy src to dst and prove the copy is byte-identical. Never deletes anything.

    A destination that already verifies is accepted without recopying, so an interrupted run
    resumes instead of re-shipping gigabytes it already shipped.
    """
    shape = _shape(src)
    if shape is None:
        return False, "source parquet is unreadable -- left in place"
    src_digest = _digest(src)
    if dst.exists():
        if dst.stat().st_size == src.stat().st_size and _digest(dst) == src_digest:
            return True, "already archived and verified"
        return False, "destination exists and DIFFERS from the source -- refusing to overwrite"
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".partial")
    try:
        shutil.copyfile(src, tmp)
        os.replace(tmp, dst)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        return False, f"copy failed: {exc}"
    if _digest(dst) != src_digest:
        dst.unlink(missing_ok=True)
        return False, "digest mismatch after copy -- destination removed, source kept"
    if _shape(dst) != shape:
        dst.unlink(missing_ok=True)
        return False, "row count or columns differ after copy -- destination removed, source kept"
    return True, "copied and verified"


def _is_object_store(dest: str) -> bool:
    return dest.startswith("s3://") or dest == "s3"


def _object_key(prefix: str, symbol: str, day: str) -> str:
    p = prefix.strip("/")
    return f"{p}/{symbol}/{day}.parquet" if p else f"{symbol}/{day}.parquet"


def _verified_upload(cfg, prefix: str, src: Path, symbol: str, day: str) -> tuple[bool, str, str]:
    """Upload one partition and PROVE it arrived. Returns (ok, note, sha256 of the bytes sent).

    The proof is the same standard the local path holds: the source is not removed until the
    destination has been read back and shown to be these bytes. Here that is a HEAD comparing
    length and ETag rather than a re-download -- see `object_store.verify` for why an ETag is
    sufficient for a single-part PUT and why a multipart one is refused instead of trusted.

    An object that is ALREADY correct is accepted without re-uploading, so an interrupted run
    resumes over the network instead of re-shipping gigabytes it already shipped.
    """
    from mt5desk import object_store
    key = _object_key(prefix, symbol, day)
    try:
        data = src.read_bytes()
    except OSError as exc:
        return False, f"cannot read source: {exc}", ""
    digest = hashlib.sha256(data).hexdigest()
    ok, why = object_store.verify(cfg, key, data)
    if ok:
        return True, "already archived and verified", digest
    ok, detail = object_store.put(cfg, key, data)
    if not ok:
        return False, f"upload failed: {detail}", digest
    ok, why = object_store.verify(cfg, key, data)
    if not ok:
        return False, f"uploaded but NOT verified ({why}) -- source kept", digest
    return True, "uploaded and verified", digest


def _append_manifest(row: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def _manifest_rows() -> list[dict]:
    if not MANIFEST.exists():
        return []
    rows = []
    for line in MANIFEST.read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def verify(dest: Path) -> dict:
    """Re-read every archived partition and confirm it is still there and still itself."""
    ok, missing, corrupt = 0, [], []
    for row in _manifest_rows():
        p = dest / row["symbol"] / f"{row['day']}.parquet"
        if not p.is_file():
            missing.append(f"{row['symbol']} {row['day']}")
            continue
        if _digest(p) != row.get("sha256"):
            corrupt.append(f"{row['symbol']} {row['day']}")
            continue
        ok += 1
    return {"archived_partitions": len(_manifest_rows()), "verified": ok,
            "missing": missing[:50], "missing_count": len(missing),
            "corrupt": corrupt[:50], "corrupt_count": len(corrupt)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest", required=True,
                    help="where partitions move to. Either a DIRECTORY (another volume, a mapped "
                         "drive, a mounted remote -- must not be inside data/tape), or an "
                         "S3-COMPATIBLE URL `s3://<prefix>` using the bucket and endpoint from "
                         "TAPE_ARCHIVE_* / data/secrets/tape_archive.json. The object store is "
                         "the one destination that never becomes another machine's disk problem.")
    ap.add_argument("--keep-days", type=int, default=KEEP_DAYS,
                    help=f"days of tape that stay on the box (default {KEEP_DAYS}; the flag "
                         f"refuses anything below {READER_WINDOW_DAYS + 5})")
    ap.add_argument("--max-gb", type=float, default=None,
                    help="stop after moving this many GB (oldest first). Omit to move everything "
                         "outside the window.")
    ap.add_argument("--apply", action="store_true", help="actually move; default measures only")
    ap.add_argument("--verify", action="store_true",
                    help="re-check the existing archive against the manifest and exit")
    ap.add_argument("--if-configured", action="store_true",
                    help="exit 0 (not 2) when no object store is configured. For the hourly "
                         "roster: an unconfigured box is a state to report, not a failing leg.")
    ap.add_argument("--allow-unmeasured-space", action="store_true",
                    help="proceed when the destination's free space cannot be read")
    args = ap.parse_args(argv)

    dest = Path(args.dest).expanduser()
    if args.verify:
        result = verify(dest)
        print(json.dumps(result, indent=1))
        return 0 if not (result["missing_count"] or result["corrupt_count"]) else 1

    s3_prefix = None
    if _is_object_store(args.dest):
        s3_prefix = args.dest[len("s3://"):] if args.dest.startswith("s3://") else ""
    # A destination inside the tape would "move" a file onto itself and then delete the source.
    if s3_prefix is None and _inside(dest, TAPE):
        print(f"REFUSING: --dest {dest} is inside {TAPE}. The archive must leave this tree.")
        return 2
    if args.keep_days < READER_WINDOW_DAYS + 5:
        print(f"REFUSING: --keep-days {args.keep_days} is below the reader window "
              f"({READER_WINDOW_DAYS} files) plus five days of headroom. The sweep and "
              f"edge_search would open partitions this run had already shipped away.")
        return 2

    rows, skipped = candidates(args.keep_days)
    if args.max_gb is not None:
        budget, kept = args.max_gb * (1024 ** 3), []
        for r in rows:
            if budget - r["bytes"] < 0:
                break
            budget -= r["bytes"]
            kept.append(r)
        rows = kept

    total = sum(r["bytes"] for r in rows)
    free_here = _free_bytes(TAPE if TAPE.exists() else BASE)
    print(f"tick tape        {_gb(sum(f.stat().st_size for f in TICKS.rglob('*.parquet') if f.is_file())) if TICKS.exists() else 0} GB")
    print(f"outside {args.keep_days}d      {len(rows)} partitions, {_gb(total)} GB")
    print(f"staying resident {skipped.get('resident', 0)} partitions"
          + (f", {skipped['undateable']} undateable (never archived)" if skipped.get("undateable") else ""))
    print(f"free here        {_gb(free_here) if free_here is not None else 'UNMEASURED'} GB")

    if not rows:
        print("nothing outside the retention window -- nothing to move")
        return 0

    if not args.apply:
        print(f"\nMEASURE ONLY. --apply would move {_gb(total)} GB to {dest}")
        return 0

    if s3_prefix is not None:
        from mt5desk import object_store
        cfg, why = object_store.load()
        if cfg is None:
            # ON THE HOURLY ROSTER THIS IS NOT A FAILURE. A box with no bucket yet must not turn
            # every cycle red -- that trains the reader to ignore the one leg that will matter
            # the day the tape has to move. It says what is missing, once an hour, and exits 0.
            print(f"tape archive not configured, nothing moved: {why}")
            return 0 if args.if_configured else 2
        print(f"destination     : {cfg.describe()} prefix={s3_prefix or '(root)'}")
        moved = failed = already = 0
        moved_bytes = 0
        problems: list[str] = []
        at = datetime.now(UTC).isoformat(timespec="seconds")
        for r in rows:
            src: Path = r["path"]
            shape = _shape(src)
            if shape is None:
                failed += 1
                problems.append(f"{r['symbol']} {r['day']}: unreadable parquet -- left in place")
                continue
            ok, note, digest = _verified_upload(cfg, s3_prefix, src, r["symbol"], r["day"])
            if not ok:
                failed += 1
                problems.append(f"{r['symbol']} {r['day']}: {note}")
                continue
            # Manifest BEFORE the delete, as on the local path: a crash between the two leaves a
            # recorded partition present in both places, which is recoverable. The other order
            # loses the only record of where an irreplaceable file went.
            _append_manifest({"symbol": r["symbol"], "day": r["day"], "bytes": r["bytes"],
                              "rows": shape[0], "columns": list(shape[1]), "sha256": digest,
                              "dest": f"s3://{cfg.bucket}/{_object_key(s3_prefix, r['symbol'], r['day'])}",
                              "moved_at": at})
            try:
                src.unlink()
            except OSError as exc:
                failed += 1
                problems.append(f"{r['symbol']} {r['day']}: uploaded and verified but source not "
                                f"removed: {exc}")
                continue
            moved_bytes += r["bytes"]
            moved += 1
            if note.startswith("already"):
                already += 1
        free_after = _free_bytes(TAPE if TAPE.exists() else BASE)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(
            {"generated_at": at, "dest": f"s3://{cfg.bucket}/{s3_prefix}",
             "keep_days": args.keep_days, "partitions_moved": moved,
             "already_archived": already, "failed": failed, "gb_moved": _gb(moved_bytes),
             "free_gb_before": _gb(free_here) if free_here is not None else None,
             "free_gb_after": _gb(free_after) if free_after is not None else None,
             "problems": problems[:100]}, indent=1), "utf-8")
        print(f"\nuploaded   {moved} partitions, {_gb(moved_bytes)} GB")
        if failed:
            print(f"FAILED     {failed} -- every one still has its source file on this box")
            for pr in problems[:10]:
                print(f"  {pr}")
        print(f"free here  {_gb(free_here) if free_here is not None else '?'} GB -> "
              f"{_gb(free_after) if free_after is not None else '?'} GB")
        print(f"manifest   {MANIFEST}")
        return 1 if failed else 0

    dest.mkdir(parents=True, exist_ok=True)
    free_there = _free_bytes(dest)
    if free_there is None and not args.allow_unmeasured_space:
        print(f"REFUSING: cannot read free space at {dest}. Pass --allow-unmeasured-space to "
              f"proceed anyway (each copy is still verified before its source is removed).")
        return 2
    if free_there is not None and free_there < total * SPACE_HEADROOM:
        need = total * SPACE_HEADROOM - free_there
        print(f"REFUSING: {dest} has {_gb(free_there)} GB free and this batch needs "
              f"{_gb(int(total * SPACE_HEADROOM))} GB. Short by {_gb(int(need))} GB. "
              f"Use --max-gb to move what fits.")
        return 2

    moved = failed = already = 0
    moved_bytes = 0
    problems: list[str] = []
    at = datetime.now(UTC).isoformat(timespec="seconds")
    for r in rows:
        src: Path = r["path"]
        dst = dest / r["symbol"] / f"{r['day']}.parquet"
        shape = _shape(src)
        ok, note = _verified_copy(src, dst)
        if not ok:
            failed += 1
            problems.append(f"{r['symbol']} {r['day']}: {note}")
            continue
        # The manifest line is written BEFORE the source goes, so a crash between the two leaves
        # a recorded partition present in both places -- recoverable. The other order loses it.
        _append_manifest({"symbol": r["symbol"], "day": r["day"], "bytes": r["bytes"],
                          "rows": shape[0] if shape else None,
                          "columns": list(shape[1]) if shape else None,
                          "sha256": _digest(dst), "dest": str(dst), "moved_at": at})
        try:
            src.unlink()
        except OSError as exc:
            failed += 1
            problems.append(f"{r['symbol']} {r['day']}: copied and verified but source not "
                            f"removed: {exc}")
            continue
        moved_bytes += r["bytes"]
        if note.startswith("already"):
            already += 1
        moved += 1

    free_after = _free_bytes(TAPE if TAPE.exists() else BASE)
    report = {
        "generated_at": at, "dest": str(dest), "keep_days": args.keep_days,
        "partitions_moved": moved, "already_archived": already, "failed": failed,
        "gb_moved": _gb(moved_bytes),
        "free_gb_before": _gb(free_here) if free_here is not None else None,
        "free_gb_after": _gb(free_after) if free_after is not None else None,
        "problems": problems[:100],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=1), "utf-8")
    print(f"\nmoved      {moved} partitions, {_gb(moved_bytes)} GB")
    if failed:
        print(f"FAILED     {failed} -- every one of these still has its source file on this box")
        for p in problems[:10]:
            print(f"  {p}")
    print(f"free here  {_gb(free_here) if free_here is not None else '?'} GB -> "
          f"{_gb(free_after) if free_after is not None else '?'} GB")
    print(f"manifest   {MANIFEST}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
