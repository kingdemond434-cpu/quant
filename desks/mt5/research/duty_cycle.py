"""DUTY CYCLE -- what fraction of the day the desk actually mints and judges, and why not more.

THE FINDING THIS ORGAN EXISTS FOR (measured on the trading box 2026-09-23/24). The desk is not
slow. It is IDLE. Both production stages have demonstrated a peak hour on this machine and then
spend most of the day producing nothing:

    stage   demonstrated peak hour   observed in 24h   duty cycle   hours with any output
    mint    35,043 cells             50,828            6%           5 of 24 (93% in two)
    judge   44,310 verdicts          80,603            8%           2 of 24

CAPACITY IS NOT THE BINDING CONSTRAINT AND HAS NOT BEEN FOR SOME TIME. Closing the duty-cycle gap
is worth more than any further speedup, because the machine already holds the capacity and leaves
it on the floor. A million cells a day needs ~29 peak hours of minting; the box has 24 hours.

WHAT THE IDLE HOURS TURNED OUT TO BE, and it is not scheduling philosophy -- it is a dead clock.
`MT5-Gauntlet` runs the sealed judge every five minutes. Its Windows trigger carried
`<Repetition><Interval>PT5M</Interval><Duration>P7DT1H35M</Duration><StopAtDurationEnd>true`.
THE REPETITION WINDOW EXPIRED. The task stayed Enabled, its Last Run Time stayed a real
timestamp, and its Next Run Time became `N/A` -- so every dashboard that asks "is the task there
and enabled" said yes while the judge had not fired since 06:51. Twenty-two of the day's
twenty-four hours produced no verdict at all for that one reason.

THE SHAPE TO RECOGNISE, because it is the sibling of the truncated-job defect this desk already
has a scar for: AN EXPIRED REPETITION READS AS A HEALTHY TASK. `stall_watch` heals tasks that are
missing or disabled; this one is neither. `schtasks /Change /RI` -- which `judging_throughput`
issues every hour -- sets the INTERVAL and leaves the DURATION alone, so the organ whose whole job
was to raise the judge's cadence was writing five-minute intervals onto a trigger that had already
stopped. Nothing in the tree looked at Next Run Time.

WHAT THIS ORGAN DOES, in order:

  1. MEASURES the two stages from the artifacts that own them -- minting from the canonical
     registry's own `research_candidates.created_at` (the table whose 21:00 hour IS the 35,043),
     judging from the gate verdict ledger the sealed gauntlet appends to. Never from a label.
  2. ACCOUNTS FOR EVERY HOUR of the box's compute ledger: seconds in which a mint-lane leg was
     running, a judge-lane leg was running, some other leg was running, or NOTHING WAS. An hour
     in which nothing ran is the most valuable row in the report.
  3. READS EVERY CLOCK and names the dead ones: a scheduled task that is Enabled, carries a
     repetition interval, and has no next run time. That is the defect above, measurable.
  4. RE-ARMS them, one way only. The interval is left exactly as configured and the DURATION is
     pushed out; nothing is ever slowed, disabled, or given a shorter window. Re-arming an expired
     trigger is the removal of a limit, never the addition of one.
  5. RATCHETS. `data/duty_cycle_ratchet.json` holds the best duty cycle each stage has ever
     MEASURED WITH THE MARKET OPEN, and it moves up only. `scripts/check_duty_cycle.py` fails when
     a stage falls below its own floor or when a lane's clock is dead.

WHAT IS NOT HERE, deliberately. Nothing throttles: there is no cap, no veto, no shrink and no
queue in this file. Leftovers are not held -- both stages read their own backlog and this organ
only measures how often they get to. And the judge itself is never touched: `external_gauntlet.py`
is sealed, and everything here is about HOW OFTEN it is allowed to run, never what it decides.

Clock: hourly leg `duty_cycle` (department validate). Artifact:
`desks/mt5/reports/DUTY_CYCLE.json`. Fence: `scripts/check_duty_cycle.py`.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sqlite3
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = BASE / "reports" / "DUTY_CYCLE.json"
RATCHET = BASE / "data" / "duty_cycle_ratchet.json"
REGISTRY = ROOT / "data" / "alpha_registry.sqlite"
VERDICTS = BASE / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
COMPUTE = BASE / "data" / "compute_ledger.jsonl"

UNMEASURED = "UNMEASURED"

#: The window every duty cycle is quoted over. A day, because the principal's target is per day
#: and because both stages' clocks are hourly or faster -- a shorter window would price a single
#: sweep as a trend.
WINDOW_HOURS = 24

#: THE LANES, by the leg name the compute ledger records. A leg named in neither is `other`, which
#: is a real category and not a failure: the desk does more than mint and judge. These names are
#: the ones the box's own ledger carries, read off it rather than invented.
MINT_LEGS: frozenset[str] = frozenset({
    "compile_candidates", "merge_docket", "miner_conversion", "independence_intake",
    "expression_factory", "axis_proposer", "axis_registry", "alpha_evolution", "alpha_lineage",
    "coevolution", "sandbox_runner", "math_lab", "physics_lab", "weak_signals", "scout_swarm",
    "moat_miner", "deepen", "world_crawler", "deep_forest_miner", "graveyard_resurrection",
    "trajectory_evolution", "paradigm_router", "pack_cells", "alpha_replenishment",
})
JUDGE_LEGS: frozenset[str] = frozenset({
    "external_gauntlet", "backtest", "falsifier_run", "adversaries", "universal_gate",
    "blind_reviewer", "counterexample_agent", "probation",
})

#: THE CLOCKS EACH LANE DEPENDS ON, by Windows task name. Declared here rather than discovered so
#: a task that VANISHES is as visible as one that stopped: an absent clock is UNMEASURED, which is
#: a verdict (L1.28a), never a pass. `MT5-Gauntlet` is the judge's five-minute clock and is the
#: one that was found dead.
LANE_TASKS: dict[str, tuple[str, ...]] = {
    "judge": ("MT5-Gauntlet", "MT5-UniversalGate", "MT5-QQuantGatesCertify"),
    "mint": ("MT5-Moat-Exploit", "MT5-Moat-Explore", "MT5-Moat-Resurrect",
             "MT5-IndependenceIntake", "MT5-Hourly", "MT5-HourlyCore", "MT5-ConvertSwarm",
             "MT5-LocalConvert", "MT5-Deepening"),
}

#: The repetition duration a re-armed trigger is given, in `schtasks` `HHHH:MM`. 9999:59 is the
#: maximum the tool accepts -- about 416 days -- and this organ re-arms every hour, so the window
#: can never run out again. It is a CEILING ON EXPIRY, not a ceiling on work.
REARM_DURATION = "9999:59"

#: `schtasks /query /v` enumerates every task on the box and MEASURED 2026-09-23 takes over a
#: minute here. The leg's budget is 400 s, so the call is given most of it and its failure is
#: UNMEASURED rather than an exception that loses the whole measurement.
SCHTASKS_TIMEOUT_S = 240.0


def _now(now: datetime | None = None) -> datetime:
    return now or datetime.now(tz=UTC)


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def market_closed(now: datetime | None = None) -> bool:
    """True inside the weekly FX close, Friday 21:00 UTC to Sunday 21:00 UTC.

    The same rule `judging_throughput` restates, and for the same reason: the ratchet must compare
    like with like. A weekend hour that judges nothing because nothing was minted is not a
    regression, and a floor that could not tell the difference would be a fence nobody trusts.
    """
    t = _now(now)
    wd, h = t.weekday(), t.hour
    return (wd == 4 and h >= 21) or wd == 5 or (wd == 6 and h < 21)


# --------------------------------------------------------------------- 1. the two stages
def _hour_key(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H")


def mint_hours(since: datetime, until: datetime) -> dict[str, Any]:
    """Cells minted per hour, from the canonical registry's own `created_at`.

    READ-ONLY AND BY ONE COLUMN. This organ never writes the registry and never touches identity
    or leasing; it opens the file `mode=ro` and counts rows by the hour they were created, which
    is the same column the desk's 35,043-cell hour is visible in.
    """
    out: dict[str, Any] = {"source": str(REGISTRY), "status": UNMEASURED, "per_hour": {}}
    if not REGISTRY.exists():
        out["why"] = f"{REGISTRY.name} absent: minting is UNMEASURED, which is never zero"
        return out
    try:
        conn = sqlite3.connect(f"file:{REGISTRY}?mode=ro", uri=True, timeout=30)
    except sqlite3.Error as exc:
        out["why"] = f"{type(exc).__name__}: {exc}"
        return out
    try:
        rows = conn.execute(
            "SELECT substr(created_at, 1, 13) AS h, COUNT(*) FROM research_candidates "
            "WHERE created_at >= ? AND created_at < ? GROUP BY h",
            (since.isoformat(), until.isoformat())).fetchall()
    except sqlite3.Error as exc:
        out["why"] = f"{type(exc).__name__}: {exc}"
        return out
    finally:
        conn.close()
    out["status"] = "MEASURED"
    out["per_hour"] = {str(h): int(n) for h, n in rows if h}
    return out


def judge_hours(since: datetime, until: datetime) -> dict[str, Any]:
    """Verdicts per hour, from the gate verdict ledger the sealed gauntlet appends to.

    EVERY ROW IS AN EVENT. A cell may be judged more than once and each judgement is a verdict the
    box paid for, so the count is of rows, not of distinct cells -- the same basis
    `gauntlet_backpressure` publishes as `testing.verdicts`, so the two can be compared.
    """
    out: dict[str, Any] = {"source": str(VERDICTS), "status": UNMEASURED, "per_hour": {}}
    if not VERDICTS.exists():
        out["why"] = f"{VERDICTS.name} absent: judging is UNMEASURED, which is never zero"
        return out
    lo, hi = since.strftime("%Y-%m-%dT%H"), until.strftime("%Y-%m-%dT%H")
    per: Counter[str] = Counter()
    try:
        with VERDICTS.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                at = row.get("at")
                if isinstance(at, str) and len(at) >= 13 and lo <= at[:13] < hi:
                    per[at[:13]] += 1
    except OSError as exc:
        out["why"] = f"{type(exc).__name__}: {exc}"
        return out
    out["status"] = "MEASURED"
    out["per_hour"] = dict(per)
    return out


def duty(per_hour: dict[str, int], hours: int = WINDOW_HOURS) -> dict[str, Any]:
    """Observed, demonstrated capacity, and the fraction of capacity actually used.

    CAPACITY IS THE BEST HOUR THIS MACHINE HAS ACTUALLY DONE, times the hours in the window. Not a
    benchmark, not a projection: a number the box produced, so the gap it implies cannot be argued
    away as optimism. A stage that produced nothing at all has NO demonstrated capacity and its
    duty cycle is UNMEASURED -- zero over zero is not zero.
    """
    observed = int(sum(per_hour.values()))
    peak = int(max(per_hour.values())) if per_hour else 0
    active = sum(1 for v in per_hour.values() if v > 0)
    capacity = peak * hours
    return {
        "observed_per_day": observed,
        "peak_hour": peak,
        "capacity_per_day": capacity,
        "duty_cycle": round(observed / capacity, 4) if capacity > 0 else UNMEASURED,
        "active_hours": active,
        "window_hours": hours,
        "active_hour_share": round(active / hours, 4) if hours else UNMEASURED,
        "hours_to_million": (round(1_000_000 / peak, 2) if peak > 0 else UNMEASURED),
    }


# ------------------------------------------------------------------ 2. accounting for the hours
def account_hours(since: datetime, until: datetime) -> dict[str, Any]:
    """Every hour of the window, split into mint / judge / other / NOTHING.

    AN HOUR IN WHICH NOTHING RAN IS THE FINDING. The compute ledger records `started_at` and
    `finished_at` for every costed leg, so an hour's occupancy is the union of the spans that
    overlap it -- union, not sum, because legs run concurrently across departments and adding
    them would report 1,325,012 seconds inside a 86,400-second day.
    """
    out: dict[str, Any] = {"source": str(COMPUTE), "status": UNMEASURED, "hours": []}
    if not COMPUTE.exists():
        out["why"] = f"{COMPUTE.name} absent: hour accounting is UNMEASURED"
        return out
    spans: list[tuple[datetime, datetime, str]] = []
    try:
        with COMPUTE.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                a, b = row.get("started_at"), row.get("finished_at")
                if not isinstance(a, str) or not isinstance(b, str):
                    continue
                try:
                    t0, t1 = datetime.fromisoformat(a), datetime.fromisoformat(b)
                except ValueError:
                    continue
                if t1 <= since or t0 >= until:
                    continue
                run = str(row.get("run") or "")
                lane = ("mint" if run in MINT_LEGS
                        else "judge" if run in JUDGE_LEGS
                        else "mint" if run.startswith(("moat_exploit:", "moat_explore:",
                                                       "moat_resurrect:", "forest_"))
                        else "other")
                spans.append((t0, t1, lane))
    except OSError as exc:
        out["why"] = f"{type(exc).__name__}: {exc}"
        return out

    rows: list[dict[str, Any]] = []
    idle = 0
    for i in range(int((until - since).total_seconds() // 3600)):
        h0 = since + timedelta(hours=i)
        h1 = h0 + timedelta(hours=1)
        cover = {lane: _union_seconds([(max(a, h0), min(b, h1))
                                       for a, b, ln in spans if ln == lane and a < h1 and b > h0])
                 for lane in ("mint", "judge", "other")}
        any_s = _union_seconds([(max(a, h0), min(b, h1))
                                for a, b, _ in spans if a < h1 and b > h0])
        nothing = round(max(0.0, 3600.0 - any_s), 1)
        if nothing >= 3600.0:
            idle += 1
        rows.append({"hour": _hour_key(h0),
                     "mint_s": round(cover["mint"], 1), "judge_s": round(cover["judge"], 1),
                     "other_s": round(cover["other"], 1), "nothing_s": nothing})
    out["status"] = "MEASURED"
    out["hours"] = rows
    total = {k: round(sum(float(r[k]) for r in rows), 1)
             for k in ("mint_s", "judge_s", "other_s", "nothing_s")}
    wall = 3600.0 * max(1, len(rows))
    out["totals"] = total
    out["share_of_wall"] = {k: round(v / wall, 4) for k, v in total.items()}
    out["fully_idle_hours"] = idle
    out["why"] = ("mint_s / judge_s / other_s are the UNION of the spans in that lane, so they "
                  "overlap each other; nothing_s is the hour minus the union of every span, and "
                  "is the only one of the four that means the box did nothing")
    return out


def _union_seconds(spans: list[tuple[datetime, datetime]]) -> float:
    """Total seconds covered by a set of intervals, counting overlap once."""
    ordered = sorted((a, b) for a, b in spans if b > a)
    total, cur_a, cur_b = 0.0, None, None
    for a, b in ordered:
        if cur_b is None or a > cur_b:
            if cur_a is not None and cur_b is not None:
                total += (cur_b - cur_a).total_seconds()
            cur_a, cur_b = a, b
        elif b > cur_b:
            cur_b = b
    if cur_a is not None and cur_b is not None:
        total += (cur_b - cur_a).total_seconds()
    return total


# ------------------------------------------------------------------------------ 3. the clocks
def read_clocks(timeout_s: float = SCHTASKS_TIMEOUT_S) -> dict[str, Any]:
    """Every scheduled task, and which of them have STOPPED FIRING.

    DEAD means: Enabled, carries a repetition interval, and has NO next run time. That is exactly
    the state `MT5-Gauntlet` was found in -- present, enabled, a real Last Run Time, and a trigger
    whose repetition window had closed. It is invisible to every check that asks whether the task
    exists or is enabled, which is why nothing caught it for eighteen hours.
    """
    out: dict[str, Any] = {"status": UNMEASURED, "tasks": {}, "dead": [], "source": "schtasks"}
    if sys.platform != "win32":
        out["why"] = "scheduled tasks are a Windows mechanism; this host has none to read"
        return out
    try:
        proc = subprocess.run(["schtasks", "/query", "/fo", "csv", "/v"],
                              capture_output=True, text=True, timeout=timeout_s, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        out["why"] = f"{type(exc).__name__}: {exc}"
        return out
    if proc.returncode != 0:
        out["why"] = f"schtasks exited {proc.returncode}: {(proc.stderr or '')[:200]}"
        return out
    wanted = {name for names in LANE_TASKS.values() for name in names}
    seen: dict[str, dict[str, Any]] = {}
    for row in csv.DictReader(io.StringIO(proc.stdout)):
        raw = (row.get("TaskName") or "").strip()
        if not raw or raw == "TaskName":
            continue
        name = raw.lstrip("\\")
        if name not in wanted or name in seen:
            continue
        every = (row.get("Repeat: Every") or "").strip()
        nxt = (row.get("Next Run Time") or "").strip()
        state = (row.get("Scheduled Task State") or "").strip()
        rec = {"state": state, "next_run": nxt,
               "last_run": (row.get("Last Run Time") or "").strip(),
               "every": every,
               "duration": (row.get("Repeat: Until: Duration") or "").strip(),
               "repeats": bool(every) and every.lower() not in ("n/a", "disabled")}
        rec["dead"] = bool(rec["repeats"] and state.lower() == "enabled"
                           and nxt.lower() in ("", "n/a"))
        seen[name] = rec
    for lane, names in LANE_TASKS.items():
        for name in names:
            if name in seen:
                seen[name]["lane"] = lane
            else:
                seen[name] = {"lane": lane, "state": UNMEASURED, "dead": False, "repeats": False,
                              "why": "not present in this box's task registry"}
    out["status"] = "MEASURED"
    out["tasks"] = seen
    out["dead"] = sorted(n for n, r in seen.items() if r.get("dead"))
    return out


def _interval_minutes(every: str) -> int | None:
    """`0 Hour(s), 5 Minute(s)` -> 5. None when the box does not say."""
    hours = minutes = 0
    for part in str(every).split(","):
        digits = "".join(ch for ch in part if ch.isdigit())
        if not digits:
            continue
        if "Hour" in part:
            hours = int(digits)
        elif "Minute" in part:
            minutes = int(digits)
    total = hours * 60 + minutes
    return total or None


#: THE MINT CLOCKS THIS ORGAN MAY RUN FASTER, and why only these two. Both are SINGLE-ORGAN,
#: SELF-BUDGETED tasks -- `independence_intake.py --once --budget-s 600` and
#: `deepening_worker.py --limit 25` -- so running one more often costs one more bounded process.
#: The cycle drivers and the department residents are deliberately NOT here: each spawns dozens of
#: subprocesses, and the box holding the live terminal is not the place to find out what four of
#: them at once does. What is not raised is published with that reason, so the decision is visible
#: rather than absent.
CADENCE_RAISABLE: tuple[str, ...] = ("MT5-IndependenceIntake", "MT5-Deepening")

#: The cadence those two are taken to, and the only reason it is not faster: `independence_intake`
#: budgets itself 600 s, so a 15-minute period leaves a clear margin between passes even when a
#: pass runs long. NOTHING IS EVER SLOWED -- a task already faster than this is left alone.
MINT_CADENCE_MIN = 15

#: THE LIVE TERMINAL ALWAYS WINS, and this is the whole of the condition. Cadence is raised only
#: while the box measurably has room: cores beyond the three the sealed gauntlet reserves in
#: session, and free physical memory beyond this. It is a condition on RAISING, never a cap on
#: work already running -- unmeasured or thin headroom changes nothing at all.
RAISE_RESERVE_CORES = 3
RAISE_RESERVE_PHYS_MB = 8_192


def _free_phys_mb() -> int | None:
    """Free physical memory on THIS machine, or None. Never a number from a document."""
    try:
        import judging_throughput as jt
    except ImportError:
        return None
    free = jt.measure_memory().get("free_phys_mb")
    return int(free) if isinstance(free, int) else None


def raise_cadence(clocks: dict[str, Any], apply: bool = True) -> dict[str, Any]:
    """Run the raisable mint clocks more often when the box measurably has room. ONE WAY.

    CADENCE IS THROUGHPUT, and on the mint side it is also the no-queue law. `independence_intake`
    minted 66 cells in one hour and 32,673 in the next: it was not producing at 32,673 an hour, it
    was draining a backlog that had been building since the last time it ran. A row is meant to be
    processed on arrival with leftovers going first next pass; an hourly clock on a self-budgeted
    ten-minute organ is how a backlog gets an hour to form. Four passes an hour is four times the
    drain and a quarter of the age.

    NOTHING HERE CAN SLOW ANYTHING. A task already at or below `MINT_CADENCE_MIN` is left exactly
    as it is, an unreadable interval is skipped rather than guessed at, and measured headroom below
    the reserve raises nothing -- the box keeps the cadence it already had.
    """
    out: dict[str, Any] = {"status": "NOT_APPLIED", "raised": [], "skipped": [],
                           "target_minutes": MINT_CADENCE_MIN}
    if clocks.get("status") != "MEASURED" or sys.platform != "win32":
        out["why"] = "clocks are UNMEASURED or this host has no scheduled tasks"
        return out
    cores, free = int(os.cpu_count() or 1), _free_phys_mb()
    out["headroom"] = {"cores": cores, "free_phys_mb": free if free is not None else UNMEASURED,
                       "reserve_cores": RAISE_RESERVE_CORES,
                       "reserve_phys_mb": RAISE_RESERVE_PHYS_MB}
    if free is None or free < RAISE_RESERVE_PHYS_MB or cores <= RAISE_RESERVE_CORES:
        out["why"] = ("headroom is UNMEASURED or under the terminal's reserve, so no clock is run "
                      "faster; every task keeps the cadence it already had")
        return out
    for name in CADENCE_RAISABLE:
        rec = (clocks.get("tasks") or {}).get(name) or {}
        now_min = _interval_minutes(rec.get("every") or "")
        if now_min is None or str(rec.get("state", "")).lower() != "enabled":
            out["skipped"].append({"task": name, "why": "absent, disabled, or no published "
                                                        "repetition interval to raise"})
            continue
        if now_min <= MINT_CADENCE_MIN:
            out["skipped"].append({"task": name, "minutes": now_min,
                                   "why": "already at or faster than the target; never slowed"})
            continue
        if not apply:
            out["raised"].append({"task": name, "status": "DRY_RUN",
                                  "from_minutes": now_min, "to_minutes": MINT_CADENCE_MIN})
            continue
        cmd = ["schtasks", "/Change", "/TN", name, "/RI", str(MINT_CADENCE_MIN),
               "/DU", REARM_DURATION]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            out["raised"].append({"task": name, "status": "FAILED", "from_minutes": now_min,
                                  "why": f"{type(exc).__name__}: {exc}"})
            continue
        after = _next_run(name)
        out["raised"].append({"task": name, "from_minutes": now_min,
                              "to_minutes": MINT_CADENCE_MIN, "rc": proc.returncode,
                              "next_run_after": after,
                              "status": ("APPLIED" if proc.returncode == 0 and after
                                         and after.lower() not in ("", "n/a") else "FAILED"),
                              "stderr": (proc.stderr or "")[:200]})
    out["status"] = "APPLIED" if out["raised"] else "NOTHING_TO_DO"
    return out


def rearm(clocks: dict[str, Any], apply: bool = True) -> dict[str, Any]:
    """Push out the repetition window of every dead lane clock. ONE WAY ONLY.

    THE INTERVAL IS NEVER TOUCHED. `schtasks /Change /RI <the interval it already has> /DU
    9999:59` re-opens the window at the cadence the box was already configured for, so this can
    restore a stopped clock and can never slow a running one. Nothing here disables a task, none
    of it shortens a duration, and a task that is not dead is not touched at all.

    Every attempt is verified by RE-READING the next run time, because the whole class of defect
    this organ exists for is a command that returned SUCCESS onto a trigger that stayed stopped.
    """
    done: list[dict[str, Any]] = []
    if clocks.get("status") != "MEASURED" or sys.platform != "win32":
        return {"status": "NOT_APPLIED", "rearmed": done,
                "why": "clocks are UNMEASURED or this host has no scheduled tasks"}
    for name in clocks.get("dead") or []:
        rec = (clocks.get("tasks") or {}).get(name) or {}
        minutes = _interval_minutes(rec.get("every") or "")
        if minutes is None:
            done.append({"task": name, "status": "SKIPPED",
                         "why": "the box does not publish this task's repetition interval, and "
                                "this organ never invents one"})
            continue
        if not apply:
            done.append({"task": name, "status": "DRY_RUN", "interval_minutes": minutes})
            continue
        cmd = ["schtasks", "/Change", "/TN", name, "/RI", str(minutes), "/DU", REARM_DURATION]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            done.append({"task": name, "status": "FAILED", "interval_minutes": minutes,
                         "why": f"{type(exc).__name__}: {exc}"})
            continue
        after = _next_run(name)
        done.append({"task": name,
                     "status": ("APPLIED" if proc.returncode == 0 and after
                                and after.lower() not in ("", "n/a") else "FAILED"),
                     "interval_minutes": minutes, "duration": REARM_DURATION,
                     "next_run_before": rec.get("next_run"), "next_run_after": after,
                     "rc": proc.returncode, "stderr": (proc.stderr or "")[:200]})
    return {"status": "APPLIED" if done else "NOTHING_TO_DO", "rearmed": done}


def _next_run(task: str) -> str:
    """The task's next run time, re-read from the box. Empty when it cannot be read."""
    try:
        proc = subprocess.run(["schtasks", "/query", "/tn", task, "/fo", "csv", "/v"],
                              capture_output=True, text=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    for row in csv.DictReader(io.StringIO(proc.stdout)):
        if (row.get("TaskName") or "").strip():
            return (row.get("Next Run Time") or "").strip()
    return ""


# ------------------------------------------------------------------------------ 4. the ratchet
def ratchet(stages: dict[str, Any], closed: bool, path: Path | None = None,
            write: bool = True, now: datetime | None = None) -> dict[str, Any]:
    """The best duty cycle each stage has MEASURED with the market open. Up only.

    WHY THE MARKET-OPEN CONDITION IS NOT A LOOPHOLE. The weekly FX close mints and judges less
    because there is less to mint and judge, not because the desk got lazier; a floor that read a
    Sunday as a regression would be switched off within a week, and a floor nobody trusts fences
    nothing. Readings taken while the market is closed are PUBLISHED and never raise or lower the
    floor, which is the same discipline `judging_throughput` applies to standing down.
    """
    p = Path(path or RATCHET)
    doc = _read_json(p, {}) or {}
    floors: dict[str, Any] = dict(doc.get("stages") or {})
    moved: dict[str, Any] = {}
    for stage, meas in stages.items():
        cur = meas.get("duty_cycle")
        prev = floors.get(stage) or {}
        prev_floor = prev.get("floor")
        if not isinstance(cur, (int, float)) or closed:
            floors[stage] = {**prev, "last_seen": cur, "last_seen_market_closed": closed}
            continue
        if not isinstance(prev_floor, (int, float)) or float(cur) > float(prev_floor):
            floors[stage] = {"floor": round(float(cur), 4),
                             "peak_hour": meas.get("peak_hour"),
                             "observed_per_day": meas.get("observed_per_day"),
                             "at": _now(now).isoformat(timespec="seconds"),
                             "last_seen": cur, "last_seen_market_closed": False}
            moved[stage] = {"from": prev_floor, "to": round(float(cur), 4)}
        else:
            floors[stage] = {**prev, "last_seen": cur, "last_seen_market_closed": False}
    payload = {"at": _now(now).isoformat(timespec="seconds"), "stages": floors,
               "rule": ("duty cycle per stage is a RATCHET: the floor is the best reading taken "
                        "with the market open and it moves up only. A reading below the floor is "
                        "a regression and scripts/check_duty_cycle.py fails on it.")}
    if write:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        os.replace(tmp, p)
    return {"floors": floors, "moved": moved, "path": str(p)}


# ------------------------------------------------------------------------------------- the pass
def run(write: bool = True, apply: bool = True, clocks_timeout_s: float = SCHTASKS_TIMEOUT_S,
        now: datetime | None = None) -> dict[str, Any]:
    """Measure both stages, account for every hour, read the clocks, re-arm the dead ones."""
    end = _now(now).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=WINDOW_HOURS)
    mint, judged = mint_hours(start, end), judge_hours(start, end)
    stages = {
        "mint": {**duty(mint.get("per_hour") or {}), "status": mint.get("status"),
                 "source": mint.get("source"), "why": mint.get("why")},
        "judge": {**duty(judged.get("per_hour") or {}), "status": judged.get("status"),
                  "source": judged.get("source"), "why": judged.get("why")},
    }
    closed = market_closed(now)
    clocks = read_clocks(clocks_timeout_s)
    rearmed = rearm(clocks, apply=apply)
    faster = raise_cadence(clocks, apply=apply)
    if rearmed.get("rearmed") or faster.get("raised"):
        clocks = read_clocks(clocks_timeout_s)
    rat = ratchet(stages, closed, write=write, now=now)
    payload: dict[str, Any] = {
        "at": _now(now).isoformat(timespec="seconds"),
        "window": {"since": start.isoformat(), "until": end.isoformat(),
                   "hours": WINDOW_HOURS, "market_closed": closed},
        "stages": stages,
        "per_hour": {"mint": mint.get("per_hour") or {}, "judge": judged.get("per_hour") or {}},
        "hour_accounting": account_hours(start, end),
        "clocks": clocks,
        "rearm": rearmed,
        "cadence": faster,
        "ratchet": rat,
        "rule": ("duty cycle = what the stage produced in the window / (the best hour this "
                 "machine has actually produced x the hours in the window). Capacity is a "
                 "measurement, never a benchmark; a stage that produced nothing has NO "
                 "demonstrated capacity and its duty cycle is UNMEASURED, not zero."),
    }
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, OUT)
        try:
            from libs.ops.events import leg_events
            leg_events("duty_cycle", "OK",
                       mint_duty=stages["mint"]["duty_cycle"],
                       judge_duty=stages["judge"]["duty_cycle"],
                       dead_clocks=len(clocks.get("dead") or []))
        except Exception as exc:   # an event bus outage never loses the report
            payload["events"] = f"UNMEASURED: {type(exc).__name__}: {exc}"
    return payload


def render(payload: dict[str, Any]) -> str:
    s, c = payload["stages"], payload["clocks"]
    acct = payload["hour_accounting"]
    win = payload["window"]
    lines = [f"DUTY CYCLE  window={win['since'][:13]}..{win['until'][:13]} "
             f"market_closed={win['market_closed']}"]
    for name in ("mint", "judge"):
        d = s[name]
        lines.append(f"  {name:6s} observed={d['observed_per_day']} peak_hour={d['peak_hour']} "
                     f"capacity/day={d['capacity_per_day']} duty={d['duty_cycle']} "
                     f"active_hours={d['active_hours']}/{d['window_hours']} "
                     f"hours_to_1M={d['hours_to_million']}")
    if acct.get("status") == "MEASURED":
        lines.append(f"  hours: idle={acct['fully_idle_hours']} share={acct['share_of_wall']}")
    lines.append(f"  clocks: {c.get('status')} dead={c.get('dead')} "
                 f"rearmed={[r.get('task') for r in payload['rearm'].get('rearmed') or []]}")
    cad = payload.get("cadence") or {}
    raised = [(r.get("task"), r.get("from_minutes"), r.get("status"))
              for r in cad.get("raised") or []]
    lines.append(f"  cadence: {cad.get('status')} -> {MINT_CADENCE_MIN}m raised={raised}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Measure and ratchet the desk's duty cycle.")
    ap.add_argument("--once", action="store_true", help="one measured pass (the leg's mode)")
    ap.add_argument("--budget-s", type=float, default=400.0,
                    help="seconds this pass may spend; it is a measurement, not a search")
    ap.add_argument("--dry-run", action="store_true",
                    help="measure and print; write no artifact and re-arm nothing")
    ap.add_argument("--no-clocks", action="store_true",
                    help="skip the scheduled-task read (it enumerates every task on the box)")
    args = ap.parse_args(argv)
    payload = run(write=not args.dry_run, apply=not args.dry_run,
                  clocks_timeout_s=0.0 if args.no_clocks else min(SCHTASKS_TIMEOUT_S,
                                                                  max(30.0, args.budget_s * 0.6)))
    print(render(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
