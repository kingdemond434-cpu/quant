#!/usr/bin/env python3
"""THE NOON LANE'S OWN STATE, PUBLISHED: its checkpoint's structured fields and its exit codes.

    python scripts/publish_cro_lane_state.py [--lane noon] [--events 20] [--out <json>]

Clock: hourly leg `cro_lane_state` (desks/mt5/research/hourly_cycle.py, meta), run just before
`cro_noon_freshness`, which reads this file. Artifact: desks/mt5/reports/CRO_NOON_STATE.json,
carried to origin by sync_shadow_to_git.ps1's $reportPaths.

WHY (backlog finding K6, 2026-11-17). `Run-DeskCycle.ps1 -Lane noon` writes its checkpoint to
desks/mt5/data/cycle_state_noon.json and its log to desks/mt5/logs/cycle_noon.log, and neither
ever left the box: the lane exited 5 on 11-13 (lease not acquired) and 1 on 11-17, and no cloud
session could see either. An early exit writes no ledger row at all, so the only trace was a log
line on a machine nobody outside it reads. This leg publishes what those two files say about the
lane's exits. It runs from the hourly cycle rather than from the launcher because the launcher's
early exits (2, 3, 4, 5) end before any step that could publish.

NO FREE TEXT IS PUBLISHED (audit MF1, 2026-11-18). The log carries agent CLI stderr, result prose
and raw exception messages, and a scrubber is a denylist: whatever it does not know to remove
crosses the wire. So nothing is scrubbed and nothing is copied. The artifact is BUILT from parsed
values only:

  * from the log, the launcher's own exit lines (`launcher exit rc=N`, `cycle end rc=N after M
    min`), each re-emitted as {at, event, rc[, minutes]} -- a re-formatted timestamp, one of two
    fixed event names and integers. Every other line is counted, never published.
  * from the checkpoint, an ALLOWLIST of fields, each validated to its type: `lane` and `status`
    against fixed vocabularies, timestamps and dates re-formatted from their parse, integers as
    integers, and `completed` / `work_items` as counts. `report`, `binding_constraint`, `why`,
    `controller`, `research_supervisor` and every key not on the list are withheld; a value that
    fails its check is published as null and named in `rejected`.

tests/scripts/test_publish_cro_lane_state.py proves it: a log and checkpoint stuffed with secrets,
paths, hosts, money and prose yield an artifact whose every string is a fixed token or a
re-formatted timestamp.

THE LAST EXIT IS READ, NEVER ASSUMED (L1.28a). The newest exit line is the lane's last exit code.
With no such line the checkpoint's `last_exit` is used; with neither, `last_rc` is null and the
verdict is UNMEASURED, never OK. An absent checkpoint and an absent log are ABSENT.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops.win_write import write_text_resilient  # noqa: E402

DESK = ROOT / "desks" / "mt5"
#: The noon lane's report (the leg's lane); `--lane midnight` writes CRO_MIDNIGHT_STATE.json.
OUT = DESK / "reports" / "CRO_NOON_STATE.json"
#: How many of the newest exit lines are published.
EVENTS = 20
#: Read at most this much of the log's end: the log only grows, and the exits are near its end.
TAIL_BYTES = 256 * 1024
LANES = frozenset({"noon", "midnight"})
STATUSES = frozenset({"DONE", "RUNNING"})
#: Checkpoint fields published, by type. Anything else is withheld unread.
TIME_KEYS = ("started_at", "finished_at")
INT_KEYS = ("last_exit", "minutes", "resumed", "lease_epoch")
COUNT_KEYS = ("completed", "work_items")

_TS = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?"
_EXIT = re.compile(rf"^(?P<at>{_TS})\s+\[(?:noon|midnight)\]\s+"
                   r"(?P<event>launcher exit|cycle end) rc=(?P<rc>-?\d{1,6})"
                   r"(?: after (?P<min>\d{1,6}) min)?\s*$")
_TS_PARTS = re.compile(r"^(?P<base>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(?P<frac>\d+))?"
                       r"(?P<tz>Z|[+-]\d{2}:\d{2})?$")


def iso(raw: Any) -> str | None:
    """A timestamp re-formatted from its parse (never the input string), or None."""
    if not isinstance(raw, str):
        return None
    m = _TS_PARTS.match(raw.strip())
    if not m:
        return None
    frac = (m.group("frac") or "")[:6]  # PowerShell's "o" carries 7 digits
    tz = m.group("tz") or "+00:00"
    try:
        t = datetime.fromisoformat(m.group("base") + (f".{frac}" if frac else "")
                                   + ("+00:00" if tz == "Z" else tz))
    except ValueError:
        return None
    return t.astimezone(UTC).isoformat()


def _int(v: Any) -> int | None:
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def structured_state(doc: dict[str, Any]) -> tuple[dict[str, Any], list[str], int]:
    """(published fields, keys rejected by their check, keys withheld unread)."""
    out: dict[str, Any] = {}
    rejected: list[str] = []
    lane, status = doc.get("lane"), doc.get("status")
    out["lane"] = lane if lane in LANES else None
    out["status"] = status if status in STATUSES else None
    raw_date = doc.get("date")
    try:
        out["date"] = date.fromisoformat(raw_date).isoformat() if isinstance(raw_date, str) else None
    except ValueError:
        out["date"] = None
    for k in TIME_KEYS:
        out[k] = iso(doc.get(k))
    for k in INT_KEYS:
        out[k] = _int(doc.get(k))
    for k in COUNT_KEYS:
        v = doc.get(k)
        out[f"{k}_count"] = len(v) if isinstance(v, list) else (
            1 if isinstance(v, (str, dict)) and v else 0 if v in (None, "") else None)
    for k in ("lane", "status", "date", *TIME_KEYS, *INT_KEYS):
        if doc.get(k) is not None and out[k] is None:
            rejected.append(k)
    for k in COUNT_KEYS:
        if out[f"{k}_count"] is None:
            rejected.append(k)
    known = {"lane", "status", "date", *TIME_KEYS, *INT_KEYS, *COUNT_KEYS}
    withheld = sum(1 for k in doc if k not in known)
    return out, sorted(rejected), withheld


def read_state(path: Path) -> tuple[str, dict[str, Any] | None]:
    if not path.exists():
        return "ABSENT", None
    try:
        # utf-8-sig: PowerShell 5.1's Set-Content -Encoding UTF8 writes a BOM.
        doc = json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return "UNREADABLE", None
    return ("PRESENT", doc) if isinstance(doc, dict) else ("UNREADABLE", None)


def read_lines(path: Path) -> tuple[str, list[str]]:
    if not path.exists():
        return "ABSENT", []
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - TAIL_BYTES))
            raw = fh.read()
    except OSError:
        return "UNREADABLE", []
    # Add-Content on PS 5.1 writes the system code page; replace what is not UTF-8.
    lines = [ln.rstrip("\r") for ln in raw.decode("utf-8", errors="replace").split("\n")]
    if size > TAIL_BYTES and lines:
        lines = lines[1:]  # the first line was cut mid-way by the seek
    return "PRESENT", [ln for ln in lines if ln.strip()]


def exit_events(lines: list[str]) -> list[dict[str, Any]]:
    """The launcher's exit lines, parsed; oldest first. Nothing of the line itself survives."""
    out: list[dict[str, Any]] = []
    for ln in lines:
        m = _EXIT.match(ln.strip())
        if not m:
            continue
        ev: dict[str, Any] = {"at": iso(m.group("at")),
                              "event": "launcher_exit" if m.group("event") == "launcher exit"
                              else "cycle_end",
                              "rc": int(m.group("rc"))}
        if m.group("min") is not None:
            ev["minutes"] = int(m.group("min"))
        out.append(ev)
    return out


def last_exit(events: list[dict[str, Any]], state: dict[str, Any] | None
              ) -> tuple[int | None, str | None, str]:
    """(rc, when, where it was read): the newest exit line, else the checkpoint."""
    if events:
        ev = events[-1]
        return ev["rc"], ev["at"], "log"
    if state is not None:
        rc = _int(state.get("last_exit"))
        if rc is not None:
            return rc, iso(state.get("started_at")), "state.last_exit"
        if state.get("status") == "DONE":
            return 0, iso(state.get("finished_at")), "state.status"
    return None, None, "none"


def build(lane: str, state_path: Path, log_path: Path, n_events: int,
          now: datetime) -> dict[str, Any]:
    state_status, state = read_state(state_path)
    log_status, lines = read_lines(log_path)
    events = exit_events(lines)
    rc, rc_at, rc_from = last_exit(events, state)
    if rc is None:
        verdict, why = "UNMEASURED", "no launcher exit line in the log and no exit in the checkpoint"
    elif rc == 0:
        verdict, why = "OK", f"last {lane} launch exited 0 ({rc_from})"
    else:
        verdict, why = "FAILED", f"last {lane} launch exited rc={rc} ({rc_from})"
    pub_state, rejected, withheld = (structured_state(state) if state is not None
                                     else (None, [], 0))
    n = max(n_events, 0)
    return {
        "at": now.isoformat(), "lane": lane,
        "source": {"state": f"desks/mt5/data/{state_path.name}",
                   "log": f"desks/mt5/logs/{log_path.name}"},
        "state_status": state_status, "state": pub_state,
        "state_rejected": rejected, "state_keys_withheld": withheld,
        "log_status": log_status, "log_lines_read": len(lines),
        "exit_events_found": len(events),
        "exit_events": events[-n:] if n else [],
        "last_rc": rc, "last_rc_at": rc_at, "last_rc_from": rc_from,
        "verdict": verdict, "why": why,
        "publication": "parsed fields only: no log line, message or checkpoint text is copied",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--lane", choices=sorted(LANES), default="noon")
    ap.add_argument("--events", type=int, default=EVENTS)
    ap.add_argument("--state", type=Path)
    ap.add_argument("--log", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    state = a.state or DESK / "data" / f"cycle_state_{a.lane}.json"
    log = a.log or DESK / "logs" / f"cycle_{a.lane}.log"
    out = a.out or (OUT if a.lane == "noon" else OUT.with_name(f"CRO_{a.lane.upper()}_STATE.json"))
    doc = build(a.lane, state, log, a.events, datetime.now(UTC))
    out.parent.mkdir(parents=True, exist_ok=True)
    write_text_resilient(out, json.dumps(doc, indent=1) + "\n")
    print(json.dumps({"lane": a.lane, "verdict": doc["verdict"], "last_rc": doc["last_rc"],
                      "state": doc["state_status"], "log": doc["log_status"]}))
    # A FAILED lane is the reading, not this leg's failure: the freshness check turns it RED.
    return 0


if __name__ == "__main__":
    sys.exit(main())
