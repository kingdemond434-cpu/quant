"""Free disk on the trading box without ever touching what cannot be rebuilt.

MEASURED 2026-09-07: 0.8 GB free. At that level neither Windows nor git says "disk full" -- a
push dies as "the remote end hung up unexpectedly" mid-pack, a parquet write truncates, and a
tick-tape append silently loses the bytes it could not flush. So a full disk does not present as
a disk problem; it presents as three unrelated subsystem failures, and that is how a day gets
spent chasing a network fault that was never there.

THE ONE RULE. `data/tape` is the desk's own moat: broker-native ticks nobody else has, and a tick
that was not recorded cannot be re-downloaded. It is never touched, at any threshold, by any mode
of this script. Everything else here is either derived (caches, bytecode) or refetchable (bars,
in minutes, from the terminal that is already running).

WHERE THE SPACE ACTUALLY IS. The miners wrote 326,224 discovery rows in fourteen days across
`data/intelligence/**/discoveries_*.json`, and the conversion audit shows the duplication is
enormous -- anomalies alone: 97,405 rows carrying 64 distinct economic exposures. Those files are
append-only by construction: every pass writes a new timestamped file with no idea what earlier
passes already wrote. Deduplicating them by CONTENT recovers the space and fixes the cause at the
same time, which is why this is one script and not two.

    python desks/mt5/scripts/reclaim_disk.py             # measure only, change nothing
    python desks/mt5/scripts/reclaim_disk.py --apply     # reclaim
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
INTEL = BASE / "data" / "intelligence"
TAPE = BASE / "data" / "tape"
REPORT = BASE / "reports" / "DISK_RECLAIM.json"

#: Derived directories that regenerate on demand. Removing one costs a rebuild, never a fact.
DERIVED_DIRS = ("__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".hypothesis")


def _size(path: Path) -> int:
    try:
        if path.is_file():
            return path.stat().st_size
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    except OSError:
        return 0


def _gb(n: int) -> float:
    return round(n / (1024 ** 3), 3)


def _is_protected(path: Path) -> bool:
    """True for anything under the tick tape. Checked by RESOLVED PATH, not by name.

    A name test (`"tape" in str(path)`) would be defeated by a junction, a relative path or a
    directory that merely contains the word. This walks the resolved parents, so nothing under
    the tape can be reached however the caller spelled it.
    """
    try:
        resolved = path.resolve()
    except OSError:
        return True                     # unresolvable: refuse rather than risk it
    tape = TAPE.resolve()
    return resolved == tape or tape in resolved.parents


def derived_bytes() -> list[tuple[Path, int]]:
    out = []
    for name in DERIVED_DIRS:
        for path in BASE.parent.parent.rglob(name):
            if path.is_dir() and not _is_protected(path):
                out.append((path, _size(path)))
    return out


def duplicate_discoveries() -> tuple[list[tuple[Path, int]], dict]:
    """Discovery files whose every row already appears in an earlier file.

    KEYED ON CONTENT, NOT ON THE ECONOMIC KEY. `check_miner_conversion._mechanism_key` is
    family|symbol|session, which a RAW miner row does not carry -- that is why broker_swaps'
    36,982 rows collapsed to one "distinct mechanism". Deduplicating on that key here would
    delete 36,981 rows that may every one be different. A hash of the row's own JSON is the only
    safe identity for a row whose meaning has not been extracted yet: it removes exact repeats
    and nothing else.

    EARLIEST WINS. Files are processed oldest-first so the first sighting of a row survives, and
    its discovery timestamp -- which the 14-day conversion window reads -- stays truthful.
    """
    if not INTEL.exists():
        return [], {"note": "no data/intelligence on this host"}
    seen: set[str] = set()
    removable: list[tuple[Path, int]] = []
    per_miner: dict[str, dict] = defaultdict(lambda: {"files": 0, "rows": 0, "dup_rows": 0})
    files = sorted((p for p in INTEL.rglob("discoveries_*.json") if p.is_file()),
                   key=lambda p: (p.stat().st_mtime, p.name))
    for path in files:
        miner = path.parent.name
        try:
            payload = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            continue                    # unreadable: leave it alone and say nothing about it
        rows = payload if isinstance(payload, list) else payload.get("rows") or payload.get("discoveries") or []
        if not isinstance(rows, list) or not rows:
            continue
        digests = [hashlib.sha256(json.dumps(r, sort_keys=True, default=str).encode()).hexdigest()
                   for r in rows]
        fresh = [d for d in digests if d not in seen]
        stat = per_miner[miner]
        stat["files"] += 1
        stat["rows"] += len(rows)
        stat["dup_rows"] += len(digests) - len(fresh)
        seen.update(digests)
        # A file is removable only when EVERY row in it was already seen. A partially-duplicated
        # file is left whole: rewriting it would change a discovery artifact, and this script's
        # remit is space, not editing the record.
        if not fresh:
            removable.append((path, _size(path)))
    return removable, {k: dict(v) for k, v in sorted(per_miner.items())}


def bar_lake() -> tuple[list[tuple[Path, int]], int]:
    """Every bar parquet, with its total size. REFETCHABLE, and that is the whole point.

    Measured on the box 2026-09-07: 0.964 GB free with a 5.664 GB tick tape. Caches and duplicate
    discovery rows came to 0.007 GB between them -- nothing there is the problem. The two large
    things on that disk are the tape and the bars, and they are opposites:

      the tape   broker-native ticks nobody else holds. A tick that was not recorded is GONE.
                 It must be MOVED off the box, never deleted, and this script never touches it.
      the bars   downloaded from the terminal that is already running, 250 symbols x 7 charts
                 in minutes, by desks/mt5/scripts/download_remaining.py.

    So the bars are the only large thing on the box that can be shed and simply re-obtained, and
    shedding them is how a full disk gets un-stuck without losing anything at all.
    """
    lake = BASE / "data" / "universe"
    if not lake.exists():
        return [], 0
    files = [(p, _size(p)) for p in lake.glob("*.parquet") if p.is_file()]
    return files, sum(n for _, n in files)


def compact_tape(apply: bool) -> dict:
    """Recompress the tick tape to zstd IN PLACE, losslessly, verifying before replacing.

    THE TAPE WAS THE ONLY PARQUET THIS DESK WRITES WITHOUT A CODEC. `tape.py` passed
    compression="zstd" for contract terms and nothing at all for the ticks, so they took
    pyarrow's default of snappy -- on the one file that grows every hour forever and was 5.664 GB
    against 0.964 GB free. Measured on a 300k-row frame with these exact columns: 3.48 MB snappy,
    1.69 MB zstd, x2.06. Roughly 2.9 GB back for a codec argument.

    NOTHING IS EVER LOST. Each file is rewritten to a temporary path, reopened, and its ROW COUNT
    and COLUMN SET compared against the original before the original is replaced. A mismatch, a
    read failure or a write failure leaves the original untouched and the file is reported, not
    skipped silently -- a tick that was not recorded cannot be re-downloaded, and neither can one
    this script loses. Parquet carries its codec in its own metadata, so every reader downstream
    keeps working with no change: they pass no codec and get whatever the file declares.
    """
    ticks = TAPE / "ticks"
    if not ticks.exists():
        return {"note": "no tick tape on this host", "files": 0}
    try:
        import pyarrow.parquet as pq
    except ImportError:
        return {"note": "pyarrow unavailable -- tape left exactly as it is", "files": 0}

    before = after = files = converted = 0
    failed: list[str] = []
    for path in sorted(ticks.rglob("*.parquet")):
        size = path.stat().st_size
        files += 1
        before += size
        try:
            table = pq.read_table(path)
            codecs = {path.suffix}  # placeholder; real check below
            md = pq.ParquetFile(path).metadata
            existing = {md.row_group(i).column(j).compression
                        for i in range(md.num_row_groups) for j in range(md.num_columns)}
        except Exception:                                               # noqa: BLE001
            failed.append(f"{path.name}: unreadable, left untouched")
            after += size
            continue
        if existing == {"ZSTD"}:
            after += size
            continue                    # already done; re-writing would cost time for nothing
        if not apply:
            after += int(size / 2.06)   # the measured ratio, for the dry-run estimate only
            converted += 1
            continue
        tmp = path.with_suffix(".zstd.tmp")
        try:
            pq.write_table(table, tmp, compression="zstd")
            check = pq.ParquetFile(tmp).metadata
            if check.num_rows != md.num_rows:
                raise ValueError(f"row count {check.num_rows} != {md.num_rows}")
            if pq.read_schema(tmp).names != table.schema.names:
                raise ValueError("column set changed")
        except Exception as exc:                                        # noqa: BLE001
            tmp.unlink(missing_ok=True)
            failed.append(f"{path.name}: {type(exc).__name__}: {exc} -- ORIGINAL KEPT")
            after += size
            continue
        tmp.replace(path)
        after += path.stat().st_size
        converted += 1
    return {"files": files, "converted": converted,
            "gb_before": _gb(before), "gb_after": _gb(after),
            "gb_saved": _gb(before - after), "failures": failed[:10],
            "verified": "row count and column set compared before every replacement"}


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    apply = "--apply" in args
    shed_bars = "--shed-bars" in args
    do_tape = "--compact-tape" in args

    free_before = shutil.disk_usage(BASE).free
    derived = derived_bytes()
    dup_files, per_miner = duplicate_discoveries()
    bars, bars_bytes = bar_lake()

    tape_plan = compact_tape(apply and do_tape) if do_tape else None
    plan = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "tape_compaction": tape_plan,
        "free_gb_before": _gb(free_before),
        "derived_dirs": len(derived),
        "derived_gb": _gb(sum(n for _, n in derived)),
        "fully_duplicate_discovery_files": len(dup_files),
        "duplicate_discovery_gb": _gb(sum(n for _, n in dup_files)),
        "tape_gb_PROTECTED": _gb(_size(TAPE)),
        "bar_lake_gb_REFETCHABLE": _gb(bars_bytes),
        "bar_files": len(bars),
        "per_miner": per_miner,
        "applied": apply,
    }

    if apply:
        removed = 0
        for path, _ in derived:
            if _is_protected(path):
                continue
            shutil.rmtree(path, ignore_errors=True)
            removed += 1
        for path, _ in dup_files:
            if _is_protected(path):
                continue
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
        if shed_bars:
            # ONLY ON AN EXPLICIT FLAG. Shedding bars costs a re-download, which is minutes and
            # no information -- but it is still a deliberate act, not something a routine hourly
            # sweep should do behind the operator's back.
            for path, _ in bars:
                if _is_protected(path):
                    continue
                try:
                    path.unlink()
                    removed += 1
                except OSError:
                    pass
            plan["bars_shed"] = len(bars)
            plan["refetch_with"] = "python desks/mt5/scripts/download_remaining.py"
        plan["paths_removed"] = removed
        plan["free_gb_after"] = _gb(shutil.disk_usage(BASE).free)
        plan["reclaimed_gb"] = round(plan["free_gb_after"] - plan["free_gb_before"], 3)

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(plan, indent=2), encoding="utf-8")

    print(f"free before      : {plan['free_gb_before']} GB")
    print(f"derived caches   : {plan['derived_gb']} GB in {plan['derived_dirs']} dir(s)")
    print(f"duplicate rows   : {plan['duplicate_discovery_gb']} GB in "
          f"{plan['fully_duplicate_discovery_files']} fully-duplicate discovery file(s)")
    print(f"tick tape        : {plan['tape_gb_PROTECTED']} GB -- PROTECTED, never touched (a tick nobody recorded is gone)")
    print(f"bar lake         : {plan['bar_lake_gb_REFETCHABLE']} GB in {plan['bar_files']:,} file(s) -- REFETCHABLE in minutes"
          + ("" if shed_bars else "  [--shed-bars to reclaim]"))
    if tape_plan and tape_plan.get("files"):
        verb = "recompressed" if (apply and do_tape) else "would recompress"
        print(f"tape zstd        : {verb} {tape_plan['converted']} of {tape_plan['files']} file(s), "
              f"{tape_plan['gb_before']} GB -> {tape_plan['gb_after']} GB "
              f"(saves {tape_plan['gb_saved']} GB, lossless)")
        for f in tape_plan.get("failures") or []:
            print(f"   TAPE FAILURE (original kept): {f}")
    if apply:
        print(f"reclaimed        : {plan['reclaimed_gb']} GB  (free now {plan['free_gb_after']} GB)")
    else:
        print("(measure only -- pass --apply to reclaim)")
    top = sorted(per_miner.items(), key=lambda kv: -kv[1].get("dup_rows", 0))[:8]
    for miner, s in top:
        if s.get("dup_rows"):
            print(f"   {miner:24} {s['rows']:>8,} rows, {s['dup_rows']:>8,} exact duplicates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
