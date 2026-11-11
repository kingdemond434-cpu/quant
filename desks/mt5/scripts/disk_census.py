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
from typing import Any

BASE = Path(__file__).resolve().parent.parent
REPO = BASE.parent.parent
REPORT = BASE / "reports" / "DISK_CENSUS.json"
#: One compact row per census (2026-11-10): the drive used 370 GB more on 11-10 than on 11-03 and
#: nothing could say WHERE, because the census kept only its latest snapshot and ran on no clock.
#: The history is what turns "the disk is full" into "this directory grew N GB since yesterday".
HISTORY = BASE / "reports" / "DISK_CENSUS_HISTORY.jsonl"
HISTORY_TOP = 40          # rows per history entry: the 40 largest trees carry the story
#: Retention (Auditor should-fix on #880): the box sync refuses files over 4 MB, so the history
#: keeps only a tail -- entries from the last HISTORY_DAYS, and never more than HISTORY_KEEP rows
#: (a month at the 6 h cadence is 120; ~4 KB each keeps the file well under 1 MB).
HISTORY_DAYS = 31
HISTORY_KEEP = 150

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


def _parse(ts: str | None) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def report_age_h(now: datetime, report: Path = REPORT) -> float | None:
    """Hours since the last census by its OWN stamp (never file mtime: adoption rewrites mtimes)."""
    try:
        t = _parse(json.loads(report.read_text("utf-8")).get("generated_at"))
    except (OSError, ValueError, AttributeError):
        return None
    return None if t is None else (now - t).total_seconds() / 3600


def read_history(path: Path = HISTORY) -> list[dict[str, Any]]:
    try:
        lines = path.read_text("utf-8").splitlines()
    except OSError:
        return []
    out = []
    for ln in lines:
        try:
            row = json.loads(ln)
        except ValueError:
            continue
        if isinstance(row, dict) and _parse(row.get("at")):
            out.append(row)
    return out


def history_row(at: str, used_gb: float, free_gb: float, by_class: dict[str, float],
                rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"at": at, "used_gb": used_gb, "free_gb": free_gb, "by_class_gb": by_class,
            "top": {r["path"]: r["gb"] for r in rows[:HISTORY_TOP]}}


def growth(history: list[dict[str, Any]], now_row: dict[str, Any],
           hours: float) -> dict[str, Any]:
    """Used-GB and per-directory growth against the newest entry at least `hours` old.

    A directory absent from the old entry counts from 0 (it was under the top-N or did not
    exist), so a NEW 50 GB tree is named as a grower rather than silently skipped.
    """
    now_t = _parse(now_row["at"])
    base: dict[str, Any] | None = None
    base_t: datetime | None = None
    for row in history:
        t = _parse(row.get("at"))
        if t is None or now_t is None or (now_t - t).total_seconds() < hours * 3600:
            continue
        if base_t is None or t > base_t:
            base, base_t = row, t
    if base is None:
        return {"status": "UNMEASURED", "why": f"no census at least {hours:g} h old yet"}
    old = base.get("top") or {}
    growers = sorted(((p, round(gb - float(old.get(p, 0.0)), 2))
                      for p, gb in now_row["top"].items()), key=lambda x: -x[1])
    return {"status": "MEASURED", "since": base["at"],
            "used_gb_delta": round(now_row["used_gb"] - float(base.get("used_gb", 0.0)), 2),
            "top_growers": [{"path": p, "gb_delta": d} for p, d in growers[:10] if d > 0]}


def append_history(row: dict[str, Any], path: Path = HISTORY) -> None:
    now_t = _parse(row.get("at"))
    kept = [r for r in read_history(path)
            if now_t is None or (t := _parse(r.get("at"))) is None
            or (now_t - t).total_seconds() <= HISTORY_DAYS * 86400]
    rows = [*kept[-(HISTORY_KEEP - 1):], row]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".jsonl.tmp")
    tmp.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), "utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--depth", type=int, default=2, help="directory levels to break down (2)")
    ap.add_argument("--all", action="store_true", help="print every row, not the top 25")
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--min-age-h", type=float, default=0.0,
                    help="skip (exit 0) when the last census is younger than this, by its stamp")
    args = ap.parse_args(argv)

    now = datetime.now(UTC)
    age = report_age_h(now, REPORT)
    if args.min_age_h > 0 and age is not None and age < args.min_age_h:
        print(f"disk_census: last census {age:.1f} h old (< {args.min_age_h:g} h) -- skipped")
        return 0

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

    at = now.isoformat(timespec="seconds")
    by_class_gb = {k: round(v / (1024 ** 3), 2) for k, v in by_class.items()}
    hrow = history_row(at, round(used / (1024 ** 3), 2), round(free / (1024 ** 3), 2),
                       by_class_gb, rows)
    hist = read_history(HISTORY)
    grow = {"24h": growth(hist, hrow, 24), "7d": growth(hist, hrow, 24 * 7)}
    for k, g in grow.items():
        if g["status"] == "MEASURED":
            print(f"growth {k}: used {g['used_gb_delta']:+.1f} GB since {g['since']}; top "
                  + ", ".join(f"{x['path']} {x['gb_delta']:+.1f}" for x in g["top_growers"][:3]))
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({
        "generated_at": at, "growth": grow,
        "total_gb": round(total / (1024 ** 3), 2), "used_gb": round(used / (1024 ** 3), 2),
        "free_gb": round(free / (1024 ** 3), 2),
        "accounted_gb": round(accounted / (1024 ** 3), 2),
        "by_class_gb": by_class_gb,
        "rows": rows[:400],
    }, indent=1), "utf-8")
    append_history(hrow, HISTORY)
    print(f"\nwritten: {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
