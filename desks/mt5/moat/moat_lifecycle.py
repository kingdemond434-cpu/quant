"""THE MOAT MUST GROW WITHOUT CLOGGING THE BOX -- and it must never shrink by accident.

THE PRINCIPAL, 2026-09-12: "it needs to be in a way where it gets deleted or put off vps as it
grows and old data is already tested or sum idk we dont want it clogging box either".

THE ASYMMETRY THAT DECIDES EVERY RULE HERE. Disk is replaceable and tape is not. 2029 cannot
re-record 2026, so a byte deleted in error is gone in a way no amount of money or compute
recovers -- while a byte kept too long costs pennies and a purchase decision. Those two mistakes
are not symmetric, and a lifecycle that treats them as if they were is how a desk loses its only
genuinely proprietary asset to a tidy-up.

So the order of preference is fixed: COMPRESS, then ARCHIVE OFF-BOX, and DELETE only what is
provably reconstructible from something the desk still holds. Nothing here deletes on age alone.

WHAT "ALREADY TESTED" HAS TO MEAN BEFORE IT LICENSES ANYTHING. A bronze day is safe to compress
once its SILVER rollup exists -- silver is the normalised form every consumer actually reads, and
`moat_silver` reports 1,514 current day-files against the bronze it was built from. It is safe to
ARCHIVE off-box once silver exists AND the day is outside the window any live research reads. It
is never safe to DELETE merely because a backtest once ran over it: a backtest is not a proof that
the raw bytes will never be wanted, and every re-derivation the desk has ever needed went back to
bronze.

THE MEASUREMENT THAT SETS THE URGENCY, taken 2026-09-12 on the trading box: 2.89 GB over 19 days
= ~56 GB/year, against 1,055 GB free. That is NINETEEN YEARS of runway. So the honest answer today
is that nothing needs deleting and the correct action is compression plus a standing measurement
-- and this file says so rather than inventing work. It exists so that when the answer changes,
it changes on a number this organ published, not on somebody noticing a full disk.

    python desks/mt5/moat/moat_lifecycle.py [--apply]
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import shutil
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
OUT = DESK / "reports" / "MOAT_LIFECYCLE.json"

MOAT = Path(os.environ.get("MOAT_ROOT", r"C:\moat"))
BRONZE = MOAT / "bronze"
SILVER = Path(os.environ.get("MOAT_SILVER", str(MOAT / "silver")))
ARCHIVE = Path(os.environ.get("MOAT_ARCHIVE", str(MOAT / "archive")))

#: Days of bronze kept UNCOMPRESSED. The moat miner rotates 40 symbols a slice and reads recent
#: days most often, so the working set is small; beyond this the read cost of a gunzip is paid
#: rarely and the space saved is large (tick text compresses roughly 5-10x).
HOT_DAYS = 7

#: Free-space floor below which the report escalates. Not a delete trigger -- a PURCHASE trigger.
#: The desk's standing order is to buy more of a binding resource rather than to do less, and disk
#: is the cheapest resource it will ever be short of.
FREE_GB_FLOOR = 100.0

_DATE = re.compile(r"(20\d{2})(\d{2})(\d{2})")


def _day(name: str) -> str | None:
    m = _DATE.search(name)
    return m.group(0) if m else None


def _silver_days() -> set[str]:
    """Days that have a SILVER rollup, which is the only thing that licenses compression."""
    out: set[str] = set()
    for base in (SILVER, MOAT / "silver", DESK / "data" / "moat_silver"):
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_file():
                d = _day(p.name) or _day(p.parent.name)
                if d:
                    out.add(d)
    return out


def survey() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    per_day: dict[str, list[Path]] = defaultdict(list)
    total = 0
    if BRONZE.exists():
        for p in BRONZE.rglob("*"):
            if not p.is_file():
                continue
            d = _day(p.name) or _day(p.parent.name)
            if d is None:
                continue
            per_day[d].append(p)
            total += p.stat().st_size

    silver = _silver_days()
    days = sorted(per_day)
    try:
        usage = shutil.disk_usage(str(MOAT if MOAT.exists() else ROOT))
        free_gb, total_gb = usage.free / 1e9, usage.total / 1e9
    except OSError:
        free_gb = total_gb = 0.0

    per_day_gb = (total / 1e9 / len(days)) if days else 0.0
    yearly_gb = per_day_gb * 365
    runway_years = (free_gb / yearly_gb) if yearly_gb else None

    today = now.date()
    hot, warm, uncompressed = [], [], []
    for d in days:
        try:
            age = (today - datetime.strptime(d, "%Y%m%d").date()).days
        except ValueError:
            continue
        plain = [p for p in per_day[d] if p.suffix != ".gz"]
        if age <= HOT_DAYS:
            hot.append(d)
            continue
        warm.append(d)
        if plain:
            uncompressed.append({"day": d, "age_days": age, "files": len(plain),
                                 "megabytes": round(sum(p.stat().st_size for p in plain) / 1e6, 1),
                                 "has_silver": d in silver})

    # COMPRESSIBLE REQUIRES A SILVER ROLLUP, not age. A day with no silver is raw truth nothing
    # else can reproduce, and it stays exactly as it is however old it gets.
    compressible = [u for u in uncompressed if u["has_silver"]]
    blocked = [u for u in uncompressed if not u["has_silver"]]

    return {
        "at": now.isoformat(timespec="seconds"),
        "moat_root": str(MOAT),
        "n_days": len(days), "first_day": days[0] if days else None,
        "last_day": days[-1] if days else None,
        "total_gb": round(total / 1e9, 3),
        "gb_per_day": round(per_day_gb, 4),
        "gb_per_year": round(yearly_gb, 1),
        "disk_free_gb": round(free_gb, 1), "disk_total_gb": round(total_gb, 1),
        "runway_years": None if runway_years is None else round(runway_years, 1),
        "n_silver_days": len(silver),
        "hot_days": len(hot), "warm_days": len(warm),
        "compressible": compressible[:40],
        "n_compressible": len(compressible),
        "reclaimable_mb": round(sum(u["megabytes"] for u in compressible), 1),
        "blocked_no_silver": blocked[:20],
        "n_blocked_no_silver": len(blocked),
        "policy": {
            "order": "COMPRESS -> ARCHIVE OFF-BOX -> DELETE only what is provably reconstructible",
            "never": ("delete on age alone, or because a backtest once ran over it. A backtest is "
                      "not a proof the raw bytes will never be wanted, and every re-derivation "
                      "this desk has needed went back to bronze."),
            "why": ("disk is replaceable and tape is not: 2029 cannot re-record 2026. Keeping a "
                    "byte too long costs pennies; deleting one in error costs it permanently, and "
                    "a lifecycle that treats those as symmetric is how the asset is lost."),
        },
        "verdict": _verdict(free_gb, runway_years, len(blocked)),
    }


def _verdict(free_gb: float, runway: float | None, blocked: int) -> dict[str, Any]:
    if free_gb and free_gb < FREE_GB_FLOOR:
        return {"state": "BUY_DISK",
                "why": (f"{free_gb:.0f} GB free is below the {FREE_GB_FLOOR:.0f} GB floor. The "
                        f"standing order is to BUY MORE of a binding resource rather than to do "
                        f"less of the thing it constrains -- and disk is the cheapest resource "
                        f"this desk will ever be short of. Deleting tape to save it would trade "
                        f"an irreplaceable asset for a replaceable one.")}
    if blocked:
        return {"state": "SILVER_LAGGING",
                "why": (f"{blocked} warm day(s) have no silver rollup, so they cannot be "
                        f"compressed and nothing downstream reads them in normalised form. That "
                        f"is a rollup gap, not a storage one -- fix moat_silver, not the disk.")}
    return {"state": "HEALTHY",
            "why": ("growth is inside the runway and every warm day has a silver rollup. Nothing "
                    "needs deleting; compression is the only action, and it is optional.")}


def compress(rows: list[dict[str, Any]], limit: int = 200) -> dict[str, Any]:
    """Gzip in place, ORIGINAL REMOVED ONLY AFTER THE COPY IS VERIFIED READABLE.

    The sequence matters more than the saving: write the .gz, read it back, compare the byte
    count, and only then unlink. A compressor that unlinks first and fails second is a shredder,
    and this is the one directory on the desk where that is unrecoverable.
    """
    done, failed, saved = 0, [], 0
    for row in rows[:limit]:
        day = row["day"]
        for p in BRONZE.rglob(f"*{day}*"):
            if not p.is_file() or p.suffix == ".gz":
                continue
            gz = p.with_suffix(p.suffix + ".gz")
            try:
                raw = p.read_bytes()
                with gzip.open(gz, "wb") as fh:
                    fh.write(raw)
                with gzip.open(gz, "rb") as fh:
                    back = fh.read()
                if back != raw:
                    failed.append(f"{p.name}: round-trip mismatch, original kept")
                    gz.unlink(missing_ok=True)
                    continue
                saved += len(raw) - gz.stat().st_size
                p.unlink()
                done += 1
            except OSError as exc:
                failed.append(f"{p.name}: {type(exc).__name__}: {exc}")
                gz.unlink(missing_ok=True)
    return {"compressed": done, "megabytes_saved": round(saved / 1e6, 1),
            "failed": failed[:10], "n_failed": len(failed)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="actually gzip the compressible days (verified round-trip first)")
    a = ap.parse_args(argv)
    doc = survey()
    if a.apply and doc.get("compressible"):
        doc["compression"] = compress(doc["compressible"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")

    v = doc["verdict"]
    print(f"moat lifecycle: {v['state']}   {doc['n_days']} day(s), {doc['total_gb']} GB, "
          f"{doc['gb_per_year']} GB/yr")
    print(f"  disk      : {doc['disk_free_gb']} GB free of {doc['disk_total_gb']} GB "
          f"-> {doc['runway_years']} year(s) of runway")
    print(f"  silver    : {doc['n_silver_days']} day(s) rolled up")
    print(f"  compress  : {doc['n_compressible']} warm day(s), ~{doc['reclaimable_mb']} MB "
          f"reclaimable")
    if doc["n_blocked_no_silver"]:
        print(f"  BLOCKED   : {doc['n_blocked_no_silver']} warm day(s) with NO silver rollup -- "
              f"kept uncompressed, on purpose")
    print(f"  {v['why'][:150]}")
    if doc.get("compression"):
        c = doc["compression"]
        print(f"  applied   : {c['compressed']} file(s), {c['megabytes_saved']} MB saved, "
              f"{c['n_failed']} failed")
    print(f"\n-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
