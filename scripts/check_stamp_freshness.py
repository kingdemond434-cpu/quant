"""Find artifacts that are REWRITTEN but not RE-STAMPED, across the whole desk.

THE DEFECT CLASS. An organ rewrites its artifact every pass and leaves the timestamp inside it
wherever it last landed. The file is fresh; the stamp is ancient; every consumer that reads the
stamp -- which is most of them, because a file mtime is destroyed by a checkout or a sync -- is
told the organ is dead.

MEASURED 2026-09-14, and it is why this exists: `shadow_state.json` was rewritten every thirty
minutes carrying `updated_at: 2026-08-27T00:01:46`, frozen for EIGHTEEN DAYS, while every row
inside it was current to the minute. `shadow_forward` set `last_run` (a DATE) on every pass and
never touched `updated_at`. Two freshness fields, one maintained, and the consumers read the
other: `heal_forward_lane` derives STALE_ATTEMPT from `updated_at` and had been announcing
"engine last evaluated this row 434.1h ago" about rows the engine had just evaluated. 434.1h was
precisely the age of the frozen stamp.

WHY A DEDICATED CHECK RATHER THAN AN EXISTING ONE. `ops/organ_contract.py` and `ops/never_stale.py`
both judge freshness by FILE AGE, so a rewritten-but-unstamped artifact passes them cleanly -- the
file really is fresh. `scripts/build_zentech_state.py` reads the internal STAMP, so the dashboard
shows it as dead. Neither can see the contradiction because neither looks at both numbers. This
looks at both, and the contradiction IS the finding.

A DATE IS NOT A TIMESTAMP, and that is the trap that hid this one for eighteen days. `last_run`
was being written faithfully every pass, so the writer looked maintained; a date cannot
distinguish a run at 00:01 from one at 23:59, so it carries no usable freshness whatever. Fields
that are date-only are reported separately rather than counted as a stamp.

    python scripts/check_stamp_freshness.py            # report; exit 1 on any divergence
    python scripts/check_stamp_freshness.py --quiet    # artifact only
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "desks" / "mt5" / "reports" / "STAMP_FRESHNESS.json"

#: Where the desk's state artifacts live. Scanned rather than listed, because a hardcoded list
#: cannot cover an artifact written next week -- and an artifact nobody thought to list is exactly
#: the one that goes stale unnoticed.
SCAN_DIRS = (
    Path("desks") / "mt5" / "reports",
    Path("desks") / "mt5" / "data",
    Path("data"),
    Path("reports"),
)

#: Keys that mean "this is when I last ran". Order matters only for reporting which one was read.
STAMP_KEYS = ("updated_at", "generated_utc", "generated_at", "measured_at", "at",
              "swept_at", "checked_at", "fetched_at", "last_updated")

#: Keys that LOOK like freshness and are not, because they carry no time of day.
DATE_ONLY_KEYS = ("last_run", "date", "day", "as_of_date")

#: A file rewritten more recently than this is "fresh on disk" for the purposes of the contrast.
FRESH_FILE_HOURS = 6.0

#: How much older the stamp must be than the file before it is a divergence rather than ordinary
#: lag. Generous on purpose: an organ that writes its artifact in two stages, or a report rebuilt
#: from a source computed an hour earlier, is not what this is hunting.
DIVERGENCE_HOURS = 12.0

#: Files that are APPEND LOGS or caches rather than organ state; their stamp is a record of an
#: event, not a claim about when the writer last ran.
SKIP_SUFFIXES = (".jsonl", ".parquet", ".npz", ".pkl", ".log", ".tmp")


def _stamp_of(doc: Any) -> tuple[str, datetime] | None:
    if not isinstance(doc, dict):
        return None
    for k in STAMP_KEYS:
        v = doc.get(k)
        if not isinstance(v, str) or len(v) < 10:
            continue
        try:
            t = datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            continue
        if t.tzinfo is None:
            t = t.replace(tzinfo=UTC)
        return k, t
    return None


def scan(root: Path | None = None) -> dict[str, Any]:
    base = root or ROOT
    now = datetime.now(UTC)
    diverged: list[dict[str, Any]] = []
    date_only: list[dict[str, Any]] = []
    checked = 0

    for rel in SCAN_DIRS:
        d = base / rel
        if not d.is_dir():
            continue
        for f in d.rglob("*.json"):
            if f.suffix in SKIP_SUFFIXES:
                continue
            try:
                file_age = (now.timestamp() - f.stat().st_mtime) / 3600.0
            except OSError:
                continue
            if file_age > FRESH_FILE_HOURS:
                continue          # not rewritten recently: ordinary staleness, not this defect
            try:
                doc = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            checked += 1
            got = _stamp_of(doc)
            if got is None:
                # NO STAMP AT ALL is a separate and lesser problem: a consumer reading this file
                # falls back to its mtime, which is at least honest. Reported, not failed.
                if isinstance(doc, dict) and any(k in doc for k in DATE_ONLY_KEYS):
                    date_only.append({
                        "file": str(f.relative_to(base)).replace("\\", "/"),
                        "file_age_h": round(file_age, 2),
                        "date_only_fields": [k for k in DATE_ONLY_KEYS if k in doc],
                        "why": ("carries a DATE but no timestamp: a consumer cannot tell a run at "
                                "00:01 from one at 23:59"),
                    })
                continue
            key, stamp = got
            stamp_age = (now - stamp).total_seconds() / 3600.0
            if stamp_age - file_age >= DIVERGENCE_HOURS:
                diverged.append({
                    "file": str(f.relative_to(base)).replace("\\", "/"),
                    "stamp_field": key,
                    "stamp": stamp.isoformat(timespec="seconds"),
                    "stamp_age_h": round(stamp_age, 2),
                    "file_age_h": round(file_age, 2),
                    "lag_h": round(stamp_age - file_age, 2),
                    "why": ("the file was rewritten and this field was not: every consumer that "
                            "reads the stamp is being told this organ is dead"),
                })

    diverged.sort(key=lambda r: -float(r["lag_h"]))
    return {
        "generated_utc": now.isoformat(timespec="seconds"),
        "rule": (f"a .json rewritten within {FRESH_FILE_HOURS}h whose internal stamp is "
                 f"{DIVERGENCE_HOURS}h or more older than the file is REWRITTEN BUT NOT "
                 f"RE-STAMPED"),
        "n_checked": checked,
        "n_diverged": len(diverged),
        "diverged": diverged,
        "n_date_only": len(date_only),
        "date_only": date_only[:20],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--quiet", action="store_true", help="write the artifact, print nothing")
    args = ap.parse_args(argv)

    doc = scan()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")

    if not args.quiet:
        print(f"stamp freshness: {doc['n_checked']} recently-written artifact(s) checked, "
              f"{doc['n_diverged']} rewritten but NOT re-stamped")
        for r in doc["diverged"][:15]:
            print(f"  {r['file']:52} {r['stamp_field']:14} stamp {r['stamp_age_h']:8.1f}h  "
                  f"file {r['file_age_h']:5.1f}h  lag {r['lag_h']:8.1f}h")
        if doc["n_date_only"]:
            print(f"\n  {doc['n_date_only']} artifact(s) carry a DATE and no timestamp:")
            for r in doc["date_only"][:6]:
                print(f"    {r['file']:52} {r['date_only_fields']}")
        print(f"  -> {OUT}")
    # A divergence is a real defect and fails, because the alternative is a health board that
    # reports a live organ as eighteen days dead and nobody notices for eighteen days.
    return 1 if doc["n_diverged"] else 0


if __name__ == "__main__":
    sys.exit(main())
