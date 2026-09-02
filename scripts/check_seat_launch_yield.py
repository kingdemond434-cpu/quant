#!/usr/bin/env python3
"""SEAT LAUNCH YIELD (L1.28a / L1.25a) -- how many headless digs actually RAN.

WHY THIS FENCE EXISTS. On 2026-08-26 the desk's own conversion gauge reported
`ARRIVALS COLLAPSED -- 25 raised against a baseline of 158.0/week` and instructed the next
seat to HUNT HARDER. It was measuring the right number and drawing the wrong conclusion: over
the preceding 7 days 102 headless seats were launched and only 27 produced a real dig (28.1%
of the 96 billable). 56 died on `auth unavailable` before launching at all, in a clean
time-of-day pattern -- the productive hours measured 05:00 and 07:00 UTC, while 14:00 and 18:00
burned every slot they were given and 15:00 ran 36 attempts for 3 digs (8%). Whole families sat
at zero: dataaxis at 14:00, prospector at 18:00, litminer at 19:00, and the six regional
frontier seats that all fired together at 15:00. The miners were not hunting too little;
they were dying at launch, and no organ measured the difference. Arrivals and yield are two
different questions, and only one of them was being asked.

THE DISTINCTION THIS FENCE ADDS, and it is the whole point: a low finding count has two very
different causes. Ground genuinely picked clean is a research verdict and the answer is to hunt
harder (L1.25a -- a null streak escalates, it never rests). Seats that never launched is an
INFRASTRUCTURE defect and hunting harder cannot touch it: it fires more seats into the same
wall. Attributing the second to the first is how a desk spends its scarcest resource attacking
a problem it does not have.

WHAT IT MEASURES. Every seat launcher writes `=== <seat> attempt <date> ===` as its first line
before anything can fail, so the attempt is recorded even when the run dies instantly. A launch
that produced carries a log above _REAL_LOG_BYTES -- the desk's own existing definition of a
real dig log, reused from run_frontier_rotation.sh's `-size +1500c` resume rule rather than
invented here. Everything between those two is a launch the desk paid a slot for and got
nothing from, classified by the reason it names.

    python scripts/check_seat_launch_yield.py [--days N] [--json]

Exit 2 on a breach: yield below the ratcheted floor, or any hour burning >= _DEAD_HOUR_MIN
attempts for zero output. Exit 0 clean. The floor only ever ratchets UP (L1.50).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "data" / "cro_ai_logs"
OUT = ROOT / "data" / "seat_launch_yield.json"
FLOOR = ROOT / "data" / "seat_launch_yield_floor.json"
QUOTA_LOG = ROOT / "data" / "brain_quota_windows.jsonl"

#: A real dig log. NOT a new magic number: run_frontier_rotation.sh already treats `-size +1500c`
#: as "this region really produced today" for its resume rule, so the fence and the resume logic
#: agree on what counts as output. A stub death is 58-686 bytes; a real dig is tens of KB.
_REAL_LOG_BYTES = 1500

#: An hour with this many attempts and zero output is a dead window, not bad luck.
_DEAD_HOUR_MIN = 3

#: A STARVED hour is judged on its RATE, not on whether it ever squeaked out one dig. The first
#: cut of this fence tested `produced == 0` and therefore MISSED the exact window that caused
#: the collapse it was written for: 15:00 UTC ran 36 attempts for 3 digs (8%) against a desk
#: yield of 28%, and a zero-test called that healthy. A window burning four slots in five is
#: the defect whether or not the fifth one lands.
_STARVED_MIN_ATTEMPTS = 5
_STARVED_RATIO = 0.5          # hour yield below half the desk's own yield = starved

_ATTEMPT_RE = re.compile(r"^=== ([a-z0-9_-]+) attempt ", re.M)
_STAMP_RE = re.compile(r"_(\d{8})T(\d{2})(\d{2})")

#: Words the CLI uses when it refuses a seat because the quota window is closed. The auth chain
#: already pages these as quota events (ops/brain_env.sh brain_auth_check greps "limit"), so the
#: fence must agree with the pager on what a wall looks like. Measured real shapes kept HERE so a
#: new sentence from the vendor shows up as an AUTH_UNAVAILABLE rather than a fabricated death:
#:   "You've hit your weekly limit · resets Sep 1, 3pm (UTC)"
#:   "You've hit your session limit - resets 1am (UTC)"
#:   "usage credits" / "rate limit" / "usage limit" (metered fallback shape)
_QUOTA_WORD_RE = re.compile(r"\b(limit|usage credits|rate limit|reset)\b", re.I)


#: How long a launch is allowed to hold nothing but its attempt header before the absence of a
#: second line counts as a death. The header is written before the memory gate, the mutex and the
#: auth chain; the auth chain alone has been measured taking ~60 seconds to print its verdict.
SETTLE_SECONDS = 300


def classify(text: str, size: int) -> str:
    """Why this launch produced nothing -- or PRODUCED."""
    low = text.lower()
    if size >= _REAL_LOG_BYTES:
        return "PRODUCED"
    # QUOTA WALLS COME IN MORE THAN ONE SENTENCE. The seat launchers say "auth unavailable"
    # (old shape) and the CLI itself says "You've hit your weekly limit"/"session limit" (new
    # shape, measured 2026-08-30 on brain-hunter). Both are a closed window, never a death:
    # the desk's own auth chain pages "limit" as a quota event and records it in
    # brain_quota_windows.jsonl. A launch that names a limit must be counted like the one that
    # names the wall, or every reset-day burn shows up as a fabricated crash.
    if "auth unavailable" in low or _QUOTA_WORD_RE.search(low):
        return "AUTH_UNAVAILABLE"      # quota wall; the seat never launched, cost ~one ping
    if "deferred" in low:
        return "MUTEX_DEFERRED"        # correct behaviour: organ_catchup re-fires the loser
    if " start " in low:
        return "DIED_AFTER_START"      # launched and was killed -- usually the OOM killer
    # A log holding ONLY its attempt header (~60 bytes) is a SILENT death: the wrapper wrote
    # the header, the process died, and nothing explained why. Measured 2026-08-28: six of
    # these were gap-wirer, whose cause was the kernel OOM killer under box-wide memory
    # pressure from retired crypto services -- bounded and freed the same night. Naming the
    # shape separately is what let the cause be found at all.
    if size <= 200:
        return "DIED_SILENT_NO_OUTPUT"
    return "DIED_AT_ATTEMPT"           # never got past the launcher


def scan(days: float) -> dict[str, object]:
    now = time.time()
    launches: list[dict[str, object]] = []
    for path in LOGS.glob("*.log"):
        try:
            stat = path.stat()
            if (now - stat.st_mtime) > days * 86400:
                continue
            text = path.read_text("utf-8", errors="ignore")
        except OSError:
            continue
        m = _ATTEMPT_RE.match(text)
        if not m:
            continue
        # A LAUNCH STILL IN FLIGHT IS NOT A DEATH. The header is written first and the auth
        # chain's first line lands up to a minute later, so a log read inside that window holds
        # nothing but its 65-byte header and looks exactly like a silent crash. MEASURED
        # 2026-09-02: frontier_unified_20260902T1148.log was reported as DIED_SILENT_NO_OUTPUT
        # and gained "auth unavailable -- next run resumes" seconds afterwards. A meter that
        # invents crashes trains the reader to ignore the row, which costs the real ones.
        age_h = (now - stat.st_mtime) / 3600.0
        outcome = classify(text, stat.st_size)
        if outcome.startswith("DIED") and age_h * 3600.0 < SETTLE_SECONDS:
            outcome = "IN_FLIGHT"
        launches.append({
            "age_h": age_h,
            "seat": m.group(1),
            "hour": int(stamp.group(2)) if (stamp := _STAMP_RE.search(path.name)) else None,
            "outcome": outcome,
            "log": path.name,
        })

    outcomes = Counter(str(x["outcome"]) for x in launches)
    produced = outcomes["PRODUCED"]
    total = len(launches)
    # MUTEX_DEFERRED is excluded from the denominator ON PURPOSE. It is the mutex doing its job
    # -- one brain at a time on one quota -- and organ_catchup re-fires the loser within 5
    # minutes, so it is a delay, not a lost slot. Counting it as failure would make correct
    # serialisation look like a defect and push a future seat to remove the protection that
    # stopped two --effort max brains sharing one working tree.
    # IN_FLIGHT leaves the denominator with MUTEX_DEFERRED: neither is an outcome yet, and
    # counting an unfinished launch as a failure would understate yield by whatever is running.
    billable = total - outcomes["MUTEX_DEFERRED"] - outcomes["IN_FLIGHT"]
    yield_pct = round(100.0 * produced / billable, 1) if billable else None

    by_hour: dict[int, list[int]] = defaultdict(lambda: [0, 0])   # hour -> [dead, produced]
    by_seat: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for x in launches:
        if x["outcome"] == "MUTEX_DEFERRED":
            continue
        ok = 1 if x["outcome"] == "PRODUCED" else 0
        if x["hour"] is not None:
            by_hour[int(x["hour"])][ok] += 1
        by_seat[str(x["seat"])][ok] += 1

    dead_hours = sorted(h for h, (d, p) in by_hour.items() if p == 0 and d >= _DEAD_HOUR_MIN)
    # A SEAT THAT IS NOT SUPPOSED TO LAUNCH IS NOT A DEAD SEAT. Two legitimate reasons a seat
    # produces nothing, neither of which is a defect, and counting them as death is how a
    # scorecard trains its reader to ignore it (measured 2026-08-28: six "dead" seats reported,
    # and SIX were correct behaviour):
    #   * MERGED -- the five regional grounds (ar/br/jp/kr/ru) were folded into the unified dig
    #     by principal order 2026-08-25, "one big cycle, EV-allocated, replaces the fixed
    #     7-region equal-time rotation -- picky allocation beats coverage theater". Their prompt
    #     files remain as the unified dig's source material; nothing should invoke them alone.
    #   * GATED -- litminer stands down on its own monthly gate ("last real dig is younger than
    #     28 days"), which is the organ exercising restraint exactly as designed.
    # A seat is DEAD only when it is expected to run, is not gated, and still produced nothing.
    merged_or_gated = {"frontier-ar", "frontier-br", "frontier-jp", "frontier-kr",
                       "frontier-ru", "litminer"}
    dead_seats = sorted(s for s, (d, p) in by_seat.items()
                        if p == 0 and d >= _DEAD_HOUR_MIN and s not in merged_or_gated)
    not_expected = sorted(s for s in by_seat if s in merged_or_gated)

    def _rate(pair: list[int]) -> float:
        dead, prod = pair
        return prod / (dead + prod) if (dead + prod) else 0.0

    desk_rate = (produced / billable) if billable else 0.0
    starved_hours = sorted(
        h for h, pair in by_hour.items()
        if sum(pair) >= _STARVED_MIN_ATTEMPTS and _rate(pair) < _STARVED_RATIO * desk_rate)
    # "Productive" must mean BETTER THAN THE DESK'S OWN AVERAGE, not merely non-zero -- these
    # are the hours the report tells a seat to move INTO, so a window that is merely less dead
    # than the worst one is not an answer.
    live_hours = sorted(
        h for h, pair in by_hour.items()
        if sum(pair) >= _DEAD_HOUR_MIN and _rate(pair) >= desk_rate)
    return {
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "window_days": days,
        "launches": total,
        "billable": billable,
        "produced": produced,
        "yield_pct": yield_pct,
        "outcomes": dict(outcomes),
        "by_hour": {str(h): by_hour[h] for h in sorted(by_hour)},
        "dead_hours_utc": dead_hours,
        "starved_hours_utc": starved_hours,
        "died_recent_24h": sum(1 for x in launches
                               if str(x["outcome"]).startswith("DIED")
                               and float(x.get("age_h") or 999) <= 24),
        "dead_seats": dead_seats,
        "not_expected_to_launch": not_expected,
        "not_expected_note": ("regional grounds merged into the unified dig (principal "
                              "2026-08-25) and organs standing down on their own gates -- "
                              "correct behaviour, never counted as death"),
        "productive_hours_utc": live_hours,
        "quota_walls": quota_walls(now - days * 86400.0, now),
    }


def quota_walls(since: float, until: float) -> dict[str, object]:
    """The MEASURED brain-quota wall over the window, or an honest UNMEASURED.

    This is the consumer half of the quota memo added to ops/brain_env.sh on 2026-08-26. The
    memo exists because AUTH_UNAVAILABLE was 55 of the 94 billable launches this fence measured,
    and every one of them re-discovered the same wall with its own probes because the reset stamp
    `brain_reset_wait_s` computes was never written down. `blocked_hours` is what the desk now
    knows about when its brain is actually reachable -- previously UNMEASURED, which is why the
    dead windows below could only be inferred from log forensics done by hand.

    ABSENCE IS NOT ZERO (L1.28a). No jsonl means no observation has been recorded yet, which is a
    different statement from "the wall never went up", and reporting it as 0 hours would let a
    silent recorder read as a healthy quota.
    """
    if not QUOTA_LOG.is_file():
        return {"recorded": False, "note": "no quota observations yet -- UNMEASURED, not zero"}
    rows: list[dict[str, Any]] = []
    for line in QUOTA_LOG.read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue          # a torn append is one lost observation, never a crashed fence
    blocked_s = 0.0
    walls = 0
    for r in rows:
        try:
            at = float(r.get("observed_at_epoch") or 0)
            end = float(r.get("blocked_until_epoch") or 0)
        except (TypeError, ValueError):
            continue
        if r.get("state") != "blocked" or end <= at:
            continue
        walls += 1
        # clip to the measurement window so a wall straddling its edge is not double counted
        blocked_s += max(0.0, min(end, until) - max(at, since))
    return {
        "recorded": True,
        "observations": len(rows),
        "walls_in_window": walls,
        "blocked_hours": round(blocked_s / 3600.0, 2),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=float, default=7.0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rep = scan(args.days)
    floor = 0.0
    if FLOOR.is_file():
        try:
            floor = float(json.loads(FLOOR.read_text("utf-8")).get("yield_pct_floor", 0.0))
        except (OSError, ValueError, TypeError):
            floor = 0.0

    breaches: list[str] = []
    y = rep["yield_pct"]
    if y is None:
        # ABSENCE IS NOT A CLEAN VERDICT (L1.28a/WS-005). Zero billable launches in the window
        # means the seats are not even being FIRED, which is worse than firing and failing.
        breaches.append(f"no seat launches at all in {args.days}d -- the fleet is not being fired")
    else:
        if float(y) < floor:
            breaches.append(f"launch yield {y}% is BELOW its floor {floor}% (L1.50 ratchet)")
        if rep["dead_hours_utc"] or rep["starved_hours_utc"]:
            breaches.append(
                f"dead launch window(s) UTC {rep['dead_hours_utc']} (zero output) + starved "
                f"{rep['starved_hours_utc']} (under half the desk yield). Productive hours are "
                f"{rep['productive_hours_utc']} -- MOVE those seats there; firing more seats "
                "into the same wall raises the attempt count and not the finding count")
        if rep["dead_seats"]:
            breaches.append(f"seat(s) that never produced: {rep['dead_seats']}")

    OUT.write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
    # Ratchet the floor UP only, and only on a real measurement.
    if y is not None and float(y) > floor:
        FLOOR.write_text(json.dumps({
            "yield_pct_floor": float(y),
            "raised_at": rep["measured_at"],
            "measured_by": f"scripts/check_seat_launch_yield.py --days {args.days}",
        }, indent=1) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(rep, indent=1))
    else:
        head = "BREACH" if breaches else "OK"
        print(f"seat launch yield: {head} -- {rep['produced']}/{rep['billable']} produced "
              f"({y}%, floor {floor}%) over {args.days}d")
        for k, v in sorted(rep["outcomes"].items(), key=lambda kv: -kv[1]):  # type: ignore[union-attr]
            print(f"    {v:4d}  {k}")
        for b in breaches:
            print(f"  BREACH: {b}")
    print(f"-> {OUT}")
    return 2 if breaches else 0


if __name__ == "__main__":
    sys.exit(main())
