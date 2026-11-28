"""Convert a thread-briefs INDEX.json into web/threads.json for the terminal's Agents tab.

WHY. `web/terminal.html` draws one hut per project thread and one robot walking to it. The page
reads `threads.json` beside `desk_state.json`; this script is the only writer of that file. It runs
on every `ops/refresh_desk_state.sh` tick (quant-desk-refresh.timer, every 3 minutes), so the
file is rebuilt on the same schedule that rebuilds the desk state.

INPUT. The thread-briefs INDEX format: {"generated_utc", "threads": [{"title", "open_rows",
"pm_open", "prs", "has_resume_note", "next_step", ...}]}. Default path
`docs/thread_briefs/INDEX.json` (tracked, so the cloud hourly routine can commit it and the VPS
picks it up through the same merge that delivers the box's state). Override with --index or
THREAD_BRIEFS_INDEX.

OUTPUT SCHEMA (threads.json, schema_version 1):
  {"schema_version": 1, "generated_at": ISO-8601, "status": "MEASURED" | "UNMEASURED",
   "why": str | null, "source": str, "source_generated_at": str | null,
   "counts": {"working": n, "blocked": n, "done": n},
   "threads": [{"title": str, "state": "working"|"blocked"|"done",
                "last_activity": ISO-8601 | null, "open_prs": int | null,
                "open_rows": int | null}]}

STATE. An explicit `state` field in a row wins when it is one of the three. Otherwise a row with
no open rows and no open principal messages is `done`; a row whose next step names a block
(BLOCKED / waiting on / principal-gated) is `blocked`; anything else is `working`.

ABSENT IS NOT EMPTY (L1.28a). A missing or unreadable index writes status UNMEASURED with the
reason and an empty thread list; it never writes a confident zero. A partial row is kept with
null for what it lacks. Free text (next_step, file names) is NOT copied: the page shows titles,
states and counts only, so nothing personal or secret can ride through it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
STATES = ("working", "blocked", "done")
DEFAULT_INDEX = "docs/thread_briefs/INDEX.json"
DEFAULT_OUT = "web/threads.json"
_BLOCKED = re.compile(r"\b(blocked|waiting on|principal[- ]gated|needs the principal)\b", re.I)
_TITLE_MAX = 80


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _state(row: dict[str, Any]) -> str:
    explicit = str(row.get("state") or "").strip().lower()
    if explicit in STATES:
        return explicit
    open_rows = _int_or_none(row.get("open_rows"))
    pm_open = _int_or_none(row.get("pm_open"))
    if open_rows == 0 and pm_open in (0, None):
        return "done"
    if _BLOCKED.search(str(row.get("next_step") or "")):
        return "blocked"
    return "working"


def _thread(row: dict[str, Any], fallback_at: str | None) -> dict[str, Any] | None:
    title = str(row.get("title") or "").strip()
    if not title:
        return None
    last = row.get("last_activity") or row.get("last_activity_at") or row.get("updated_at")
    return {
        "title": title[:_TITLE_MAX],
        "state": _state(row),
        "last_activity": str(last) if last else fallback_at,
        "open_prs": _int_or_none(row.get("open_prs", row.get("prs"))),
        "open_rows": _int_or_none(row.get("open_rows")),
    }


def build(index_path: Path, now: datetime | None = None) -> dict[str, Any]:
    """Return the threads.json document for `index_path`; never raises on bad input."""
    at = (now or datetime.now(UTC)).isoformat(timespec="seconds")
    doc: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION, "generated_at": at, "status": "UNMEASURED",
        "why": None, "source": str(index_path), "source_generated_at": None,
        "counts": dict.fromkeys(STATES, 0), "threads": [],
    }
    try:
        raw = json.loads(index_path.read_text("utf-8"))
    except FileNotFoundError:
        doc["why"] = f"no thread index at {index_path}: nothing has published thread status here"
        return doc
    except (OSError, ValueError) as exc:
        doc["why"] = f"thread index unreadable: {type(exc).__name__}"
        return doc
    rows = raw.get("threads") if isinstance(raw, dict) else None
    if not isinstance(rows, list):
        doc["why"] = "thread index has no 'threads' list"
        return doc
    src_at = raw.get("generated_utc") or raw.get("generated_at")
    doc["source_generated_at"] = str(src_at) if src_at else None
    threads = [t for r in rows if isinstance(r, dict) and (t := _thread(r, doc["source_generated_at"]))]
    for t in threads:
        doc["counts"][t["state"]] += 1
    doc["threads"] = threads
    doc["status"] = "MEASURED"
    if len(threads) < len(rows):
        doc["why"] = f"{len(rows) - len(threads)} row(s) without a title were skipped"
    return doc


def write(doc: dict[str, Any], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1), "utf-8")
    os.replace(tmp, out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--index", default=os.environ.get("THREAD_BRIEFS_INDEX", DEFAULT_INDEX))
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    doc = build(Path(args.index))
    write(doc, Path(args.out))
    print(f"threads.json {doc['status']}: {len(doc['threads'])} thread(s)"
          + (f" -- {doc['why']}" if doc["why"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
