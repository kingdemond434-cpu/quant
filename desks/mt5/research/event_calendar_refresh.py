"""Weekly refresh of the scheduled-event calendar from the publishers' own pages.

Runs inside the hourly cycle; it fetches only when a refresh is due (`event_calendar.due`: a
week old, a core publisher unread last time, or no calendar written by this organ yet), so most
passes cost one file read. Every page goes through the robots gate (fail closed) under an honest
UA. A publisher it cannot read keeps its last good events for CARRY_MAX_D days, then reads
UNMEASURED; a core publisher past that empties `valid_through`, and `event_guard` blocks.

THE CALENDAR IS NEVER REPLACED BY A WORSE ONE: a build that fails `event_calendar.refusal`
leaves the file on disk as it was and says so. Health (FRESH or STALE, with the reason) goes to
reports/EVENT_CALENDAR_HEALTH.json every pass, and a STALE calendar exits 2 so the hourly
cycle's ledger shows the leg red rather than quiet.

    python research/event_calendar_refresh.py [--force] [--out PATH]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import event_calendar as ec  # noqa: E402

#: The file `libs/execution/event_guard.py`, `libs/research/event_calendar.py` and
#: `research/residual_hunt.py` read.
OUT = ROOT / "data" / "event_calendar.json"
HEALTH = DESK / "reports" / "EVENT_CALENDAR_HEALTH.json"


def _read(path: Path) -> dict[str, Any] | None:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", "utf-8")
    os.replace(tmp, path)


def run(*, out: Path = OUT, health_path: Path = HEALTH, force: bool = False,
        now: datetime | None = None, fetch: Any = None) -> dict[str, Any]:
    now = (now or datetime.now(tz=UTC)).astimezone(UTC)
    prev = _read(out)
    why_due = "forced" if force else ec.due(prev, now)
    report: dict[str, Any] = {"generated_at": now.isoformat(timespec="seconds"),
                              "calendar": str(out), "refreshed": False, "due": why_due}
    if why_due:
        pages, refused = (fetch or ec.fetch_pages)()
        doc = ec.carry_forward(ec.build(pages, now, refused), prev, now)
        bad = ec.refusal(doc)
        report["coverage"] = doc["coverage"]
        if bad:
            report["refused_write"] = bad
            report["missed_growth"] = ec.MISSED_GROWTH
        else:
            doc["missed_growth"] = ec.MISSED_GROWTH
            _write(out, doc)
            report["refreshed"] = True
            prev = doc
    report["health"] = ec.health(prev, now)
    _write(health_path, report)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--force", action="store_true", help="refresh even when not due")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    rep = run(out=Path(a.out), force=a.force)
    cov = rep.get("coverage") or {}
    print(json.dumps({"refreshed": rep["refreshed"], "due": rep["due"],
                      "health": rep["health"],
                      "unread": sorted(p for p, c in cov.items() if c.get("status") != "OK"),
                      "refused_write": rep.get("refused_write")}))
    return 2 if rep["health"]["state"] == "STALE" else 0


if __name__ == "__main__":
    sys.exit(main())
