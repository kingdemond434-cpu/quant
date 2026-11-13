#!/usr/bin/env python3
"""A STALE VITALS HEARTBEAT IS RED (2026-11-13).

Reads desks/mt5/reports/VITALS.json and exits 1 with a loud RED line when its heartbeat is older
than --max-age-s, or the file is absent or unreadable (absence is never a clean verdict). Run it
at the start of any pass that reasons about the desk: a reader on a stale VITALS is reading the
past.

    python scripts/check_vitals_fresh.py                 # box copy, 120 s
    python scripts/check_vitals_fresh.py --max-age-s 1200 # a mirror published every 15 min
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT = REPO / "desks" / "mt5" / "reports" / "VITALS.json"


def verdict(path: Path, max_age_s: float, now: datetime | None = None) -> tuple[bool, str]:
    now = now or datetime.now(UTC)
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
        at = datetime.fromisoformat(str(doc["heartbeat_at"]).replace("Z", "+00:00"))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return False, f"RED: VITALS unreadable at {path} ({type(exc).__name__}) -- UNMEASURED"
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    age = (now - at).total_seconds()
    if age > max_age_s:
        return False, f"RED: VITALS heartbeat {age:.0f}s old (limit {max_age_s:.0f}s), at {at}"
    return True, f"OK: VITALS heartbeat {age:.0f}s old"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=str(DEFAULT))
    ap.add_argument("--max-age-s", type=float, default=120.0)
    a = ap.parse_args(argv)
    ok, msg = verdict(Path(a.path), a.max_age_s)
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
