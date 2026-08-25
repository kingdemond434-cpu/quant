"""Moat-node coverage fence (GAP 127) -- the recorder's own L1.0/L2.0 ratchet.

Reads the recorder's heartbeat and today's health rows and holds them against a FLOOR THAT ONLY
RISES: symbols recorded, heartbeat freshness, tick progress. A recorder outage becomes a loud,
dated alarm artifact and a nonzero exit -- never silence (WS-005). Run every 15m by task.

    py -3 moat_fence.py            # verify; exit 1 + C:\\moat\\FENCE_ALARM.txt on breach
"""
from __future__ import annotations

import gzip
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

MOAT = Path(os.environ.get("MOAT_ROOT", r"C:\moat"))
HEARTBEAT = MOAT / "heartbeat.json"
FLOOR = MOAT / "coverage_floor.json"
ALARM = MOAT / "FENCE_ALARM.txt"
BRONZE = MOAT / "bronze"

MAX_HEARTBEAT_AGE_MIN = 30      # recorder writes health every 60s; 30 min dead = outage
SYMBOL_SLACK = 10               # universe may legitimately shrink a little (delistings)


def read_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def main() -> int:
    problems: list[str] = []
    hb = read_json(HEARTBEAT)
    now = datetime.now(tz=UTC)

    ts = hb.get("ts")
    if not ts:
        problems.append("heartbeat.json missing/unreadable -- recorder has never run or died "
                        "before its first health row")
    else:
        age = now - datetime.fromisoformat(ts)
        if age > timedelta(minutes=MAX_HEARTBEAT_AGE_MIN):
            problems.append(f"heartbeat is {age} old (floor {MAX_HEARTBEAT_AGE_MIN} min) -- "
                            f"the recorder is DOWN and every unrecorded tick is unbuyable")
    if hb.get("paused"):
        problems.append("recorder is PAUSED (disk floor) -- the gap is being recorded but the "
                        "moat is not growing; free disk now")

    floor = read_json(FLOOR)
    symbols = int(hb.get("symbols") or 0)
    ticks = int(hb.get("ticks") or 0)
    sym_floor = int(floor.get("symbols_floor") or 0)
    if symbols + SYMBOL_SLACK < sym_floor:
        problems.append(f"symbols recorded {symbols} fell below floor {sym_floor} "
                        f"(slack {SYMBOL_SLACK}) -- universe coverage regressed")
    prev_ticks = int(floor.get("last_ticks") or 0)
    prev_at = floor.get("checked_at")
    if prev_at and ticks <= prev_ticks and not hb.get("paused"):
        prev_dt = datetime.fromisoformat(prev_at)
        if now - prev_dt > timedelta(minutes=45):
            problems.append(f"tick counter stalled at {ticks} since {prev_at} -- recorder "
                            f"alive but recording NOTHING (silent-zero class)")

    # today's gap events, straight from the health rows the recorder itself wrote
    day_file = BRONZE / "terminal_health" / f"{now:%Y%m%d}.jsonl.gz"
    gaps = 0
    try:
        with gzip.open(day_file, "rt", encoding="utf-8") as f:
            for line in f:
                try:
                    gaps = max(gaps, int(json.loads(line).get("gaps") or 0))
                except ValueError:
                    continue
    except OSError:
        pass

    # RATCHET: floors only rise; counters recorded for the next stall check.
    new_floor = {
        "symbols_floor": max(sym_floor, symbols),
        "last_ticks": max(prev_ticks, ticks),
        "gaps_today": gaps,
        "checked_at": now.isoformat(),
        "breaches": problems,
    }
    FLOOR.parent.mkdir(parents=True, exist_ok=True)
    FLOOR.write_text(json.dumps(new_floor, indent=2), "utf-8")

    if problems:
        ALARM.write_text(f"MOAT FENCE BREACH {now.isoformat()}\n\n"
                         + "\n".join(f"- {p}" for p in problems) + "\n", "utf-8")
        print("MOAT FENCE: BREACH\n" + "\n".join(f"  - {p}" for p in problems))
        return 1
    if ALARM.exists():
        ALARM.unlink()
    print(f"MOAT FENCE: ok (symbols={symbols} floor={new_floor['symbols_floor']} "
          f"ticks={ticks} gaps_today={gaps})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
