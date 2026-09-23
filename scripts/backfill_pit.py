#!/usr/bin/env python3
"""Stamp the intelligence rows that predate `libs.data.pit` with what they can honestly carry.

    python scripts/backfill_pit.py            # report what would change
    python scripts/backfill_pit.py --write    # rewrite the files in place

WHAT A BACKFILL MAY CLAIM. A row written before the stamp existed has ONE honest availability
time: the moment the desk recorded it (`found_at`, `captured_at`, `published_at` -- whichever the
producer wrote). That is what `stamp` uses, so a backfilled row says "the desk could have known
this from the time it wrote it down", never earlier. A row with none of those fields gets
`available_time = ingested_time = now`, which is the most conservative claim possible and makes
the row unusable for any decision dated before today. `source_version` is set to `backfill` so
the rows are distinguishable from those stamped at ingestion; nothing a producer set is changed.

WHY REWRITE IN PLACE. The compiler, the census and every joiner read the files as they are; a
parallel stamped copy would be a second truth. Each file is rewritten atomically (temp + rename)
and only when at least one row changed.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from libs.data.pit import is_stamped, stamp  # noqa: E402

INTEL = ROOT / "desks" / "mt5" / "data" / "intelligence"


def _load(path: Path):
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _rows_of(doc):
    if isinstance(doc, list):
        return doc, None
    if isinstance(doc, dict):
        for key in ("discoveries", "rows"):
            if isinstance(doc.get(key), list):
                return doc[key], key
    return None, None


def backfill(write: bool) -> dict:
    per_source: dict[str, dict[str, int]] = {}
    files_changed = 0
    for src_dir in sorted(p for p in INTEL.iterdir() if p.is_dir()) if INTEL.exists() else []:
        counts = {"files": 0, "rows": 0, "already": 0, "stamped": 0}
        for f in sorted(glob.glob(str(src_dir / "discoveries_*.json"))):
            path = Path(f)
            doc = _load(path)
            rows, key = _rows_of(doc)
            if rows is None:
                continue
            counts["files"] += 1
            changed = False
            new_rows = []
            for r in rows:
                if not isinstance(r, dict):
                    new_rows.append(r)
                    continue
                counts["rows"] += 1
                if is_stamped(r):
                    counts["already"] += 1
                    new_rows.append(r)
                    continue
                new_rows.append(stamp(r, src_dir.name, source_version="backfill"))
                counts["stamped"] += 1
                changed = True
            if changed and write:
                out = new_rows if key is None else {**doc, key: new_rows}
                tmp = path.with_suffix(".json.tmp")
                tmp.write_text(json.dumps(out, indent=1, default=str), "utf-8")
                os.replace(tmp, path)
                files_changed += 1
        if counts["rows"]:
            per_source[src_dir.name] = counts
    total = {k: sum(c[k] for c in per_source.values()) for k in
             ("files", "rows", "already", "stamped")}
    return {"per_source": per_source, "total": total, "files_rewritten": files_changed,
            "wrote": write}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="rewrite files in place")
    a = ap.parse_args()
    d = backfill(a.write)
    t = d["total"]
    verb = "stamped" if a.write else "would stamp"
    print(f"PIT backfill: {t['rows']} rows in {t['files']} files across "
          f"{len(d['per_source'])} sources; {t['already']} already stamped; "
          f"{verb} {t['stamped']}; files rewritten: {d['files_rewritten']}")
    for s, c in sorted(d["per_source"].items(), key=lambda kv: -kv[1]["stamped"])[:25]:
        print(f"  {s:32s} rows={c['rows']:6d} already={c['already']:6d} {verb}={c['stamped']:6d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
