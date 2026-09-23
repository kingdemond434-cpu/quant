#!/usr/bin/env python3
"""RESUME THE INSTANT QUOTA RETURNS -- not at the next fixed timer slot.

THE WASTE THIS REMOVES (principal 2026-08-26: "make the diggers resume automatically once the
session limit is back, instantly, without restarting"). The desk's answer to quota exhaustion was
three fixed retry slots -- 03:00, 06:20, 08:00. If a dig dies on quota at 03:05 and the pool
refills at 04:30, the desk sits idle for nearly two hours waiting for a clock, then digs. That
idle time is not caution; it is a research slot that existed and was not taken, which is idle
capital's research twin (LAWS 2a).

THE VENDOR TELLS US WHEN. The exhaustion error carries the reset time verbatim:

    ERROR: You've hit your usage limit ... try again at Aug 26th, 2026 12:29 AM

So there is no need to guess, poll blindly, or hammer the API to discover availability. This
parses that timestamp, records it, and fires the dig the first time a check runs after it passes.
Checking every few minutes costs nothing; hammering a rate-limited endpoint to find out costs the
next window.

WHY THIS DOES NOT RESTART ANYTHING. `run_frontier_rotation.sh` is already resumable: it skips a
ground whose REAL log exists today (>=1500 bytes -- "a stub does not count"), so re-invoking it
continues owed work rather than re-digging what is finished. This adds the trigger; the resume
semantics were already correct and are left alone.

WHAT IT REFUSES.
  * It never fires while quota is still blocked -- that would burn the retry on a certain refusal
    and, on some vendors, extend the block.
  * It never fires when nothing is owed. A resume with no owed work is just an unscheduled dig.
  * An UNPARSEABLE reset time is not treated as "probably fine now": it falls back to the
    conservative vendor-typical window and says so, because guessing early is the failure mode
    that wastes the window it is trying to save.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "data" / "cro_ai_logs"
STATE = ROOT / "data" / "quota_state.json"

#: How far back to look for a fresh exhaustion. Older blocks have long since expired.
LOOKBACK_H = 36.0
#: Used only when the vendor's message carries no parseable reset time.
FALLBACK_BLOCK_H = 5.0
#: The unit that actually performs the resumable dig.
RESUME_UNIT = "quant-seat-frontier.service"

_QUOTA = re.compile(r"(hit your usage limit|usage limit reached|rate limit|insufficient credit)",
                    re.I)
_RESET = re.compile(r"try again at\s+([A-Za-z]{3,9})\s+(\d{1,2})[a-z]{0,2},?\s+(\d{4}),?\s+"
                    r"(\d{1,2}):(\d{2})\s*([AP]M)", re.I)
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _parse_reset(text: str) -> datetime | None:
    m = _RESET.search(text)
    if not m:
        return None
    mon, day, year, hh, mm, ampm = m.groups()
    month = _MONTHS.get(mon[:3].lower())
    if not month:
        return None
    hour = int(hh) % 12 + (12 if ampm.upper() == "PM" else 0)
    try:
        return datetime(int(year), month, int(day), hour, int(mm), tzinfo=UTC)
    except ValueError:
        return None


def _owed_today() -> bool:
    """Is today's unified dig still owed? Same rule the rotation itself uses."""
    today = datetime.now(tz=UTC).strftime("%Y%m%d")
    for f in LOGS.glob(f"frontier_unified_{today}T*.log"):
        try:
            if f.stat().st_size > 1500:
                return False          # a REAL log exists; a stub does not count
        except OSError:
            continue
    return True


def main() -> int:
    now = datetime.now(tz=UTC)
    cutoff = now - timedelta(hours=LOOKBACK_H)
    state = {}
    try:
        state = json.loads(STATE.read_text("utf-8"))
    except (OSError, ValueError):
        state = {}

    blocked_until, source, parsed = None, None, True
    for f in sorted(LOGS.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)[:40]:
        try:
            if datetime.fromtimestamp(f.stat().st_mtime, tz=UTC) < cutoff:
                break
            text = f.read_text("utf-8", errors="ignore")[-20000:]
        except OSError:
            continue
        if not _QUOTA.search(text):
            continue
        reset = _parse_reset(text)
        if reset is None:
            reset = datetime.fromtimestamp(f.stat().st_mtime, tz=UTC) + timedelta(
                hours=FALLBACK_BLOCK_H)
            parsed = False
        if blocked_until is None or reset > blocked_until:
            blocked_until, source = reset, f.name
        break

    owed = _owed_today()
    fired = False
    if blocked_until is None:
        status = "NO_RECENT_BLOCK"
        why = "no quota exhaustion in the lookback window"
    elif now < blocked_until:
        status = "BLOCKED"
        why = (f"quota returns {blocked_until.isoformat(timespec='minutes')} "
               f"({(blocked_until - now).total_seconds() / 60:.0f} min) -- not firing into a "
               f"certain refusal" + ("" if parsed else "; reset time was NOT parseable, using the "
                                     "conservative fallback rather than guessing early"))
    elif not owed:
        status = "CLEAR_NOTHING_OWED"
        why = "quota is back but today's dig already produced a real log -- a resume with no owed "\
              "work is just an unscheduled dig"
    else:
        status = "RESUMING"
        why = (f"quota returned at {blocked_until.isoformat(timespec='minutes')} and today's dig "
               f"is still owed -- firing now instead of waiting for the next fixed slot")
        subprocess.Popen(["systemctl", "--user", "start", "--no-block", RESUME_UNIT])
        fired = True

    state.update({
        "checked_at": now.isoformat(timespec="seconds"),
        "status": status, "why": why,
        "blocked_until": None if blocked_until is None else blocked_until.isoformat(),
        "reset_time_parsed": parsed, "source_log": source,
        "dig_owed_today": owed, "resume_fired": fired,
        "last_resume_at": now.isoformat(timespec="seconds") if fired
        else state.get("last_resume_at"),
    })
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=1, default=str), "utf-8")
    print(f"quota resume: {status} -- {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
