"""What is actually on this disk, biggest first, each labelled by what it costs to delete.

WHY THIS EXISTS. The box kept hitting zero free and the response was always the same: shed the
bar lake, buy a few gigabytes, carry on. That treats a symptom. The principal asked the question
that should have been asked first -- "it's 80 GB, so how are we short?" -- and nothing on this
desk could answer it. `stall_watch` reads `(Get-PSDrive C).Free` and prunes two directories it
was told about; `reclaim_disk` measures only the three things it already knows how to remove. If
the answer is a 40 GB MetaTrader history cache or a 20 GB git object store, every one of those
sweeps could run to completion and the disk would still be full tomorrow.

So this measures FIRST and deletes NOTHING. Not a flag, not a mode: there is no code path in this
file that removes a file. Reclaiming is `reclaim_disk.py`'s job and it protects the tape; this
one only has to be honest, and a measurement tool that can also delete is a measurement tool
people are afraid to run when it matters.

EVERY ROW SAYS WHAT IT WOULD COST TO LOSE, because "biggest first" is not actionable on its own:

    REFETCHABLE   bars, caches, package downloads. Minutes to rebuild, no information lost.
    SYSTEM        Windows, page file, installers. Not ours to delete; named so it is not hunted.
    IRREPLACEABLE the tick tape. Broker-native ticks nobody else holds -- a tick that was not
                  recorded cannot be bought back at any price. Reported so it is never a
                  surprise, and never as a candidate.
    REVIEW        anything else. Big, ours, and this file will not guess.

    python desks/mt5/scripts/disk_census.py            # top 25 consumers
    python desks/mt5/scripts/disk_census.py --all      # every row it measured
    python desks/mt5/scripts/disk_census.py --depth 3  # dig further into the big trees
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
REPO = BASE.parent.parent
REPORT = BASE / "reports" / "DISK_CENSUS.json"

REFETCHABLE, SYSTEM, IRREPLACEABLE, REVIEW = "REFETCHABLE", "SYSTEM", "IRREPLACEABLE", "REVIEW"

#: Substrings of a resolved path that decide its class. Ordered: first match wins, so the tape's
#: rule sits above the generic desk-data rule and cannot be overridden by it.
CLASSES: tuple[tuple[str, str, str], ...] = (
    ("desks/mt5/data/tape", IRREPLACEABLE, "broker-native ticks -- NEVER delete, move instead"),
    ("desks/mt5/data/universe", REFETCHABLE, "bar lake: re-downloads from the terminal in minutes"),
    ("metaquotes/terminal", REFETCHABLE, "MT5's own history cache -- the terminal refills it"),
    ("/bases", REFETCHABLE, "MT5 history cache"),
    ("/.git", REVIEW, "git objects: `git gc --aggressive --prune=now` is usually large here"),
    ("__pycache__", REFETCHABLE, "bytecode"),
    ("/pip/cache", REFETCHABLE, "pip download cache"),
    ("/temp", REFETCHABLE, "temp"),
    ("/tmp", REFETCHABLE, "temp"),
    ("windows", SYSTEM, "operating system"),
    ("program files", SYSTEM, "installed software"),
    ("pagefile.sys", SYSTEM, "virtual memory -- sized by Windows, not by this desk"),
    ("hiberfil.sys", SYSTEM, "hibernation image -- `powercfg /h off` reclaims it"),
    ("$recycle.bin", REFETCHABLE, "recycle bin -- empty it"),
    ("desks/mt5/logs", REFETCHABLE, "logs"),
    ("desks/mt5/data/intelligence", REVIEW, "discovery rows: reclaim_disk dedups these"),
)


def classify(path: Path) -> tuple[str, str]:
    s = str(path).replace("\\", "/").lower()
    for needle, kind, why in CLASSES:
        if needle in s:
            return kind, why
    return REVIEW, ""


def tree_size(path: Path) -> int:
    """Bytes under `path`, following no links and raising on nothing.

    `os.scandir` rather than `rglob`: on a tree of ~300,000 discovery files the difference is
    minutes, and a census nobody waits for is a census nobody runs.
    """
    total = 0
    stack = [str(path)]
    while stack:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    try:
                        if e.is_symlink():
                            continue
                        if e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                        else:
                            total += e.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
    # A directory we may not read is not a measurement failure worth aborting for; it is a row
    # we cannot see, and the total below says so rather than pretending completeness.
        except OSError:
            continue
    return total


def roots() -> list[Path]:
    """Where to look. The desk's own tree, plus the places a Windows box actually fills up."""
    out = [REPO]
    for env in ("APPDATA", "LOCALAPPDATA", "TEMP", "ProgramData"):
        v = os.environ.get(env)
        if v and Path(v).exists():
            out.append(Path(v))
    drive = Path(os.environ.get("SystemDrive", "C:") + os.sep)
    if drive.exists():
        out.append(drive)
    seen, uniq = set(), []
    for p in out:
        try:
            r = p.resolve()
        except OSError:
            continue
        if r not in seen:
            seen.add(r)
            uniq.append(r)
    return uniq


def census(depth: int) -> list[dict]:
    """(path, bytes, class, why) for every directory within `depth` of a root."""
    rows: list[dict] = []
    measured: set[str] = set()

    def visit(path: Path, level: int) -> None:
        key = str(path).lower()
        if key in measured:
            return
        measured.add(key)
        size = tree_size(path)
        if size < 64 * 1024 * 1024:          # below 64 MB it is not why a disk is full
            return
        kind, why = classify(path)
        rows.append({"path": str(path), "bytes": size, "gb": round(size / (1024 ** 3), 2),
                     "class": kind, "note": why})
        if level >= depth or kind == IRREPLACEABLE:
            return                            # never enumerate inside the tape; it is one fact
        try:
            children = [Path(e.path) for e in os.scandir(path)
                        if e.is_dir(follow_symlinks=False)]
        except OSError:
            return
        for c in children:
            visit(c, level + 1)

    for r in roots():
        try:
            for e in os.scandir(r):
                if e.is_dir(follow_symlinks=False):
                    visit(Path(e.path), 1)
                else:
                    # pagefile.sys and hiberfil.sys are FILES at the drive root and are routinely
                    # the two largest things on a Windows box. A directory-only walk misses them
                    # entirely, which is how a census can account for 30 GB of an 80 GB disk and
                    # call the rest a mystery.
                    try:
                        sz = e.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
                    if sz >= 64 * 1024 * 1024:
                        kind, why = classify(Path(e.path))
                        rows.append({"path": e.path, "bytes": sz,
                                     "gb": round(sz / (1024 ** 3), 2),
                                     "class": kind, "note": why})
        except OSError:
            continue
    rows.sort(key=lambda r: -r["bytes"])
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--depth", type=int, default=2, help="directory levels to break down (2)")
    ap.add_argument("--all", action="store_true", help="print every row, not the top 25")
    ap.add_argument("--top", type=int, default=25)
    args = ap.parse_args(argv)

    try:
        du = shutil.disk_usage(str(REPO))
        total, used, free = du.total, du.used, du.free
    except OSError:
        total = used = free = 0

    print(f"drive   total {total / (1024 ** 3):.1f} GB   used {used / (1024 ** 3):.1f} GB   "
          f"free {free / (1024 ** 3):.1f} GB")
    rows = census(args.depth)
    accounted = 0
    # Only top-level rows count toward the total; a nested row is already inside its parent and
    # adding both would double-count its way past the size of the disk.
    tops = [r for r in rows if not any(
        r["path"] != o["path"] and r["path"].lower().startswith(o["path"].lower().rstrip("\\/") + os.sep)
        for o in rows)]
    accounted = sum(r["bytes"] for r in tops)
    print(f"census  {len(rows)} tree(s) over 64 MB; top-level rows account for "
          f"{accounted / (1024 ** 3):.1f} GB of the {used / (1024 ** 3):.1f} GB used\n")

    print(f"{'GB':>8}  {'class':<14} path")
    shown = rows if args.all else rows[:args.top]
    for r in shown:
        print(f"{r['gb']:>8.2f}  {r['class']:<14} {r['path']}"
              + (f"\n{'':>8}  {'':<14} -> {r['note']}" if r["note"] else ""))

    by_class: dict[str, int] = {}
    for r in tops:
        by_class[r["class"]] = by_class.get(r["class"], 0) + r["bytes"]
    print("\nby class (top-level only):")
    for k in (REFETCHABLE, REVIEW, SYSTEM, IRREPLACEABLE):
        if k in by_class:
            print(f"  {k:<14} {by_class[k] / (1024 ** 3):>7.2f} GB")
    if by_class.get(REFETCHABLE):
        print(f"\n{by_class[REFETCHABLE] / (1024 ** 3):.1f} GB is REFETCHABLE -- that is the "
              f"headroom available without losing a single fact.")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "total_gb": round(total / (1024 ** 3), 2), "used_gb": round(used / (1024 ** 3), 2),
        "free_gb": round(free / (1024 ** 3), 2),
        "accounted_gb": round(accounted / (1024 ** 3), 2),
        "by_class_gb": {k: round(v / (1024 ** 3), 2) for k, v in by_class.items()},
        "rows": rows[:400],
    }, indent=1), "utf-8")
    print(f"\nwritten: {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
