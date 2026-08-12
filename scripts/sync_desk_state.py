#!/usr/bin/env python3
"""MIRROR THE DESK'S MEASUREMENT ARTIFACTS INTO GIT — run on the VPS, read anywhere.

WHY. `data/` is gitignored, so every ephemeral container starts with none of it. A capability
ratchet run there scores two dozen aspects off files that do not exist and reports the CONTAINER
as a collapsing desk. The principal asked the right question -- what would make a container able
to measure -- and this is the answer: mirror the small measurement reports into a tracked
directory, exactly as the desk already force-adds nineteen files under `data/`.

WHAT IT MIRRORS: the ~27 JSON/JSONL reports the ratchet, gate board and audit read. Kilobytes
each.

WHAT IT NEVER MIRRORS, and the exclusions are enforced rather than remembered: `data/secrets/`
(credentials do not go in a repo, ever), the ~10GB moat tape, the lake, any .sqlite/.parquet/.db,
and anything over 2 MB. This is a MEASUREMENT MIRROR, not a backup.

EVERY FILE CARRIES ITS SOURCE AGE AT SYNC TIME, which is the difference between this being useful
and being a new way to lie. A clone is seconds old; the numbers inside it may be days old.
`libs.ops.desk_state.read()` reports SNAPSHOT with that age carried forward, so nothing can score
a stale mirror as current fact -- the failure recorded on 2026-08-05 when a four-day-stale
conversion file scored 0.276 against a live 0.431.

    python scripts/sync_desk_state.py            # mirror + write manifest
    python scripts/sync_desk_state.py --check    # report what WOULD sync, write nothing
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.desk_state import (  # noqa: E402
    MANIFEST,
    MAX_BYTES,
    NEVER_SYNC,
    SNAPSHOT_DIR,
    SYNC_SET,
    syncable,
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report only; write nothing")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    now = datetime.now(tz=UTC)
    out_dir = _ROOT / SNAPSHOT_DIR
    files: dict[str, dict] = {}
    copied, skipped, absent = [], [], []

    for name in SYNC_SET:
        src = _ROOT / "data" / name
        if not syncable(name):
            skipped.append((name, "excluded by NEVER_SYNC"))
            continue
        if not src.exists() or src.stat().st_size == 0:
            absent.append(name)
            continue
        size = src.stat().st_size
        if size > MAX_BYTES:
            # A report that outgrew the cap is a DATA STORE wearing a report's name. Skipping it
            # silently would leave a hole nobody could see, so it is recorded with its size.
            skipped.append((name, f"{size} bytes over the {MAX_BYTES} cap -- this is a store, "
                                  "not a measurement report"))
            continue
        age_h = (now.timestamp() - src.stat().st_mtime) / 3600.0
        files[name] = {"bytes": size, "source_age_h_at_sync": round(age_h, 2),
                       "synced_utc": now.isoformat(timespec="seconds")}
        if not args.check:
            out_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, out_dir / name)
        copied.append(name)

    doc = {
        "what": "measurement-artifact mirror so a fresh clone can measure the desk rather than "
                "itself",
        "generated_utc": now.isoformat(timespec="seconds"),
        "n_mirrored": len(copied), "n_absent": len(absent), "n_skipped": len(skipped),
        "absent": sorted(absent),
        "skipped": [{"name": n, "why": w} for n, w in skipped],
        "never_sync": list(NEVER_SYNC),
        "law": "the age recorded here is the SOURCE age on the producing box, never the checkout "
               "age. desk_state.read() carries it forward so a snapshot can never be scored as "
               "current fact",
        "files": files,
    }
    if not args.check:
        out_dir.mkdir(parents=True, exist_ok=True)
        (_ROOT / MANIFEST).write_text(json.dumps(doc, indent=1), "utf-8")

    if args.json:
        print(json.dumps(doc, indent=1))
    else:
        verb = "would mirror" if args.check else "mirrored"
        print(f"{verb} {len(copied)}/{len(SYNC_SET)} artifact(s) -> {SNAPSHOT_DIR}/")
        if absent:
            print(f"  absent on this box ({len(absent)}): {', '.join(sorted(absent)[:8])}"
                  f"{' ...' if len(absent) > 8 else ''}")
        for n, w in skipped:
            print(f"  SKIPPED {n}: {w}")
        if not args.check:
            print(f"  manifest -> {MANIFEST}")
            print("  NEXT: git add -f docs/state && commit -- the mirror is only useful once it "
                  "travels with the clone")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
