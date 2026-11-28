"""PAGE WHEN A MONEY TASK IS KILLED BY ITS TIME LIMIT, AND WHEN C: RUNS OUT. Pages; never fixes.

    py -3 desks/mt5/scripts/money_task_pager.py      # one JSON line, last; stall_watch reads it

WHY (2026-11-11). `E8-Gold` (every 5 min, ExecutionTimeLimit PT4M) was terminated by the
scheduler at 01:10Z and 01:15Z, and silently from about 00:46Z, and MT5-TerminalBoot (PT5M) in
the same window. Result 267014 (0x41306, "terminated, exceeded the time allocated") was on the
task the whole time and nothing paged: stall_watch treats 267014 as benign, and only for research
tasks. A money lane that is killed every pass is a money lane that does not trade.

THE RULE. Two CONSECUTIVE observed runs of a task in MONEY_TASKS ending 267014 page once. One
kill does not page (a single slow pass is weather); any other result resets the count. The page
repeats every REPAGE_H hours while the streak stands, and not more often.

HOW "CONSECUTIVE" IS SEEN: a strike file, not the event log. LastTaskResult only describes the
latest run, so this keeps per-task state in desks/mt5/logs/money_task_strikes.json (the way
stall_watch keeps low_mem_strikes) keyed on LastRunTime: a strike counts only when LastRunTime
has moved, so an hourly task read six times is still one run. Chosen over the Task Scheduler
Operational log (event 329 / 102 / 201) because that log is DISABLED by default on Windows
("Enable All Tasks History"); a pager that depends on a switch nobody can see being on is a
pager that can be silently off. The cost, stated: stall_watch runs every 10 minutes, so on a
5-minute task it sees every other run -- a kill/ok/kill pattern can read as two kills. That
errs toward paging, which is the right side for a money lane.

DISK FLOOR. When C: free is below DISK_FLOOR_GB (the floor stall_watch's prune ladder works to,
and this runs AFTER that ladder) it pages and names the largest .git/objects/pack directories
under the clone roots (disk_census.pack_dirs), so the page says who is growing. Nothing here
deletes anything: a guard that can delete is a guard people are afraid to run.

Sender: `libs.ops.alert_channels.send_all`, directly (the money-path pager; never the digest).
"""
from __future__ import annotations

import contextlib
import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for _p in (str(ROOT), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import disk_census  # noqa: E402

#: The money path's scheduled tasks, from desks/mt5/ops/box_tasks.manifest (lane money/prop) and
#: the install_*_task.ps1 scripts: the Fusion gateway and its dead-man, the terminal, the E8 and
#: FTMO executors and followers, and the allocators that size them. ONE list; edit it here.
MONEY_TASKS: tuple[str, ...] = (
    "E8-Gold", "E8-Executor", "MT5-E8WindowGuard",
    "MT5-TerminalBoot", "MT5-Gateway", "MT5-GatewayResident",
    "MT5-FusionDeadman", "MT5-FusionDeadmanLive",
    "MT5-FTMO-Executor", "MT5-FTMO-Follower", "MT5-FTMOFollow", "MT5-FTMO-VenueReader",
    "MT5-FTMO-Allocator", "MT5-AllocatorPulse", "MT5-AllocatorFast",
)
TIME_LIMIT_KILL = 267014        # 0x41306 SCHED_S_TASK_TERMINATED: exceeded the time allocated
STILL_RUNNING = 267009          # 0x41301: no verdict yet -- wait for the run to end
NEVER_RAN = 267011              # 0x41303
STRIKES_TO_PAGE = 2
REPAGE_H = 6.0
DISK_FLOOR_GB = 5.0             # = stall_watch $DiskFloorGB = desk_self_heal.DISK_FLOOR_GB
#: The strike / dedup state, rewritten every pass: it is also this organ's run artifact.
OUT = ROOT / "desks" / "mt5" / "logs" / "money_task_strikes.json"
STATE_REL = OUT.relative_to(ROOT).as_posix()

Sender = Callable[[str, str], dict[str, Any]]
Facts = dict[str, dict[str, Any]]   # task -> {"last_run": iso | None, "result": int | None}


def _due(paged_at: str | None, now: datetime) -> bool:
    if not paged_at:
        return True
    try:
        return (now - datetime.fromisoformat(paged_at)).total_seconds() / 3600 >= REPAGE_H
    except ValueError:
        return True


def judge_tasks(facts: Facts, state: dict[str, Any], now: datetime) -> list[str]:
    """Advance each task's strike count in `state` (in place); return the tasks to page now."""
    tasks = state.setdefault("tasks", {})
    page = []
    for name, f in facts.items():
        last_run, result = f.get("last_run"), f.get("result")
        if not last_run or result is None or result in (STILL_RUNNING, NEVER_RAN):
            continue                                 # unmeasured or unfinished: no new run
        t = tasks.setdefault(name, {"last_run": None, "strikes": 0, "paged_at": None})
        if t["last_run"] == last_run:
            continue                                 # the same run, read again
        t["last_run"], t["result"] = last_run, result
        if result == TIME_LIMIT_KILL:
            t["strikes"] += 1
        else:
            t["strikes"], t["paged_at"] = 0, None    # a finished run ends the streak
        if t["strikes"] >= STRIKES_TO_PAGE and _due(t["paged_at"], now):
            t["paged_at"] = now.isoformat(timespec="seconds")
            page.append(name)
    return page


def judge_disk(free_gb: float | None, state: dict[str, Any], now: datetime) -> bool:
    """True when the disk breach should page now (on entry, then every REPAGE_H while it stands)."""
    d = state.setdefault("disk", {"paged_at": None})
    if free_gb is None:
        return False                                 # unmeasured neither pages nor clears
    if free_gb >= DISK_FLOOR_GB:
        d["paged_at"] = None
        return False
    if _due(d["paged_at"], now):
        d["paged_at"] = now.isoformat(timespec="seconds")
        return True
    return False


_PS = (
    "$ErrorActionPreference='Stop'; $out=@{}; foreach ($n in $args) { try {"
    " $i = Get-ScheduledTaskInfo -TaskName $n -TaskPath '\\';"
    " $out[$n] = @{ last_run = $(if ($i.LastRunTime) { $i.LastRunTime.ToUniversalTime()"
    ".ToString('o') } else { $null }); result = [int64]$i.LastTaskResult }"
    " } catch { } }; $out | ConvertTo-Json -Compress"
)


def read_task_facts(names: tuple[str, ...] = MONEY_TASKS) -> Facts:
    """LastRunTime and LastTaskResult per task, one PowerShell call. A task that cannot be read
    is left out (unmeasured), never reported as healthy or killed."""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                            "& {" + _PS + "}", *names],
                           capture_output=True, text=True, timeout=90, check=False)
        doc = json.loads(r.stdout or "{}")
    except (OSError, subprocess.SubprocessError, ValueError):
        return {}
    return {k: v for k, v in doc.items() if isinstance(v, dict)} if isinstance(doc, dict) else {}


def _default_sender(root: Path) -> Sender:
    def send(title: str, body: str) -> dict[str, Any]:
        from libs.ops import alert_channels
        return alert_channels.send_all(title, body,
                                       config=root / "data/secrets/alert_channels.json",
                                       ledger=root / "data/alert_delivery.jsonl")
    return send


def _send(sender: Sender, title: str, body: str) -> dict[str, Any]:
    try:
        res = sender(title, body)
    except Exception as exc:  # the pager must never take down stall_watch
        return {"title": title, "armed": None, "delivered": 0, "error": type(exc).__name__}
    return {"title": title, "armed": res.get("armed"), "delivered": res.get("delivered")}


def run(root: Path = ROOT, *, facts: Facts | None = None, free_gb: float | None = None,
        packs: Callable[[], list[dict]] = disk_census.pack_dirs,
        sender: Sender | None = None, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    path = root / STATE_REL
    try:
        state = json.loads(path.read_text("utf-8"))
        state = state if isinstance(state, dict) else {}
    except (OSError, ValueError):
        state = {}
    if facts is None:
        facts = read_task_facts()
    if free_gb is None:
        with contextlib.suppress(OSError):
            free_gb = shutil.disk_usage(str(root)).free / (1024 ** 3)
    send = sender or _default_sender(root)
    out: dict[str, Any] = {"checked_at": now.isoformat(timespec="seconds"),
                           "tasks_measured": len(facts), "pages": []}
    # An empty read (PowerShell failed or timed out; ScheduledTasks is CIM-backed and CIM has
    # hung on this box) must not pass for "no kills": a blind pager is said out loud.
    out["facts"] = "MEASURED" if facts else "UNMEASURED"

    killed = judge_tasks(facts, state, now)
    if killed:
        lines = [f"{n}: {state['tasks'][n]['strikes']} consecutive runs terminated by its "
                 f"time limit (267014), last run {state['tasks'][n]['last_run']}" for n in killed]
        out["pages"].append(_send(send, "MONEY TASK KILLED BY TIME LIMIT: " + ", ".join(killed),
                                  "\n".join(lines)))
    out["killed"] = killed
    out["streaks"] = {n: t["strikes"] for n, t in state.get("tasks", {}).items() if t["strikes"]}

    out["free_gb"] = None if free_gb is None else round(free_gb, 1)
    if judge_disk(free_gb, state, now):
        top = packs()
        out["pack_dirs"] = top
        body = [f"C: {free_gb:.1f} GB free, under the {DISK_FLOOR_GB:g} GB floor after "
                "stall_watch's prune ladder. Largest git pack dirs (nothing was deleted):"]
        body += [f"  {p['gb']:.1f} GB  {p['packs']} packs  {p['path']}" for p in top] or [
            "  none found under the clone roots"]
        out["pages"].append(_send(send, f"DISK FLOOR: C: {free_gb:.1f} GB free", "\n".join(body)))

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=1), "utf-8")
    except OSError as exc:
        out["state_write_error"] = type(exc).__name__
    return out


def main() -> int:
    # ONE LINE OF JSON, LAST: stall_watch.ps1 parses the final stdout line.
    print(json.dumps(run(), default=str, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
