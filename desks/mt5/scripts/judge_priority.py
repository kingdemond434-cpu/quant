"""THE JUDGE RUNS AT THE MINERS' PRIORITY -- EQUAL, NEVER ABOVE (principal, 2026-10-20).

THE FINDING (box, 2026-10-20 15:43Z, reports/JUDGING_THROUGHPUT.json): non-judge work used 17.24
of 18 cores and the judge 0.32, across 68 python processes, while the judge's single-process merge
ran 51,198 s. The principal's constraints on any fix are binding and are the rule this module
enforces:

    1. the judge gets NO CPU priority above the miners; EQUAL is fine;
    2. mining is never cut or slowed: no miner is lowered, capped or confined to fewer cores;
    3. no gate is lowered and no cell is skipped (this module touches neither).

WHAT THE REPOSITORY SAYS THE CLASSES RUN AT (read 2026-10-20, every installer and spawn site):

    judge   MT5-Gauntlet task Priority 7 (install_state_vector_task.ps1 pins it) = BELOW_NORMAL;
            run_sharded_gauntlet spawns the sweep child with BELOW_NORMAL_PRIORITY_CLASS and the
            shards inherit it; the cache warmer's pool drops itself to IDLE.
    miners  department_resident, scout_swarm and moat_swarms spawn BELOW_NORMAL explicitly; every
            task Install-QuantWindows registers takes the scheduler default, Priority 7 =
            BELOW_NORMAL; a child of a BELOW_NORMAL parent inherits BELOW_NORMAL on Windows.
    audit   MT5-FrontierAudit: SYSTEM, scheduler default Priority 7 = BELOW_NORMAL.
    live    E8-Executor / E8-Gold Priority 4 = NORMAL (install_e8_tasks.ps1). terminal64.exe was
            measured BELOW_NORMAL on 2026-09-24 and is nobody's to change from here.

So on paper the judge is ALREADY level with the miners, and a single-threaded merge competing
with ~60 runnable equal-priority threads on 18 cores gets 18/60 ~= 0.3 of a core -- which is
what was measured. Priority is then not the lever, and raising the judge ABOVE the miners is
forbidden. But "on paper" is not a measurement: tasks with `installer="NONE"` exist only in the
box's registry, and the 2026-09-24 census found 8 of 104 desk processes at NORMAL. This module
MEASURES it and enforces equality on whatever it finds:

    target = min(priority of every measured miner)          -- never above ANY miner
             capped strictly below the lowest live clock   -- the 2026-10-08 rule: E8 at 4 must
                                                              preempt the judge (it starved when
                                                              they were level)
             capped at NORMAL                               -- never AboveNormal/High/Realtime

A judge process below the target is RAISED to it; one above it is brought DOWN to it (rule 1).
No miner, audit or live process is ever touched. The cache warmer stays IDLE by its own rule.

    python desks/mt5/scripts/judge_priority.py            # read-only census, prints + writes report
    python desks/mt5/scripts/judge_priority.py --no-write # read-only, prints only
    python desks/mt5/scripts/judge_priority.py --apply    # also equalise the judge processes

UNMEASURED IS A REAL ANSWER (L1.28a): with no miner process visible the target is UNMEASURED and
nothing is changed -- the launcher then keeps today's BELOW_NORMAL.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
REPORT = DESK / "reports" / "JUDGE_PRIORITY.json"
UNMEASURED = "UNMEASURED"

#: Windows priority classes as psutil / kernel32 number them, and their ORDER. The constants are
#: the kernel's, so this table is valid on a box where psutil is present or absent.
IDLE, BELOW_NORMAL, NORMAL, ABOVE_NORMAL, HIGH, REALTIME = 0x40, 0x4000, 0x20, 0x8000, 0x80, 0x100
CLASS_RANK = {IDLE: 0, BELOW_NORMAL: 1, NORMAL: 2, ABOVE_NORMAL: 3, HIGH: 4, REALTIME: 5}
RANK_CLASS = {v: k for k, v in CLASS_RANK.items()}
RANK_NAME = {0: "IDLE", 1: "BELOW_NORMAL", 2: "NORMAL", 3: "ABOVE_NORMAL", 4: "HIGH", 5: "REALTIME"}
#: The judge is never raised past this, whatever the miners run at.
JUDGE_CEILING_RANK = CLASS_RANK[NORMAL]
#: What the launcher used before this module and keeps whenever the target is UNMEASURED.
DEFAULT_RANK = CLASS_RANK[BELOW_NORMAL]

#: THE REGISTERED LIVE CLASS IS A FIXED CEILING (audit HOLD of be6a305b7). E8-Executor and E8-Gold
#: run every 5 minutes for at most 4, so a census taken between their runs sees no live clock at
#: all -- and the class it sets lasts a sweep of hours. The ceiling is therefore read from what
#: the repository REGISTERS (`install_e8_tasks.ps1 -Priority N`), whether or not E8 is running at
#: the census, and the judge stays strictly below it. Task Scheduler levels map to classes as
#: 0 realtime, 1 high, 2-3 above normal, 4-6 normal, 7-8 below normal, 9-10 idle.
E8_INSTALLER = DESK / "scripts" / "install_e8_tasks.ps1"


def _task_level_rank(level: int) -> int:
    if level <= 0:
        return CLASS_RANK[REALTIME]
    if level == 1:
        return CLASS_RANK[HIGH]
    if level <= 3:
        return CLASS_RANK[ABOVE_NORMAL]
    if level <= 6:
        return CLASS_RANK[NORMAL]
    if level <= 8:
        return CLASS_RANK[BELOW_NORMAL]
    return CLASS_RANK[IDLE]


def registered_live_rank(path: Path | None = None) -> int | None:
    """The LOWEST class the live E8 tasks are registered at; None when it cannot be read."""
    import re

    try:
        text = Path(path or E8_INSTALLER).read_text("utf-8", errors="replace")
    except OSError:
        return None
    levels = [int(m) for m in re.findall(r"-Priority\s+(\d+)\b", text)]
    return min(_task_level_rank(v) for v in levels) if levels else None


_JUDGE_SCRIPTS = frozenset({"external_gauntlet.py", "run_sharded_gauntlet.py", "rungauntlet.cmd"})
_WARM_SCRIPTS = frozenset({"warm_gauntlet_cache.py"})
_AUDIT_MARK = "run_frontier_audit.cmd"
_LIVE_SCRIPTS = frozenset(
    {"gateway_resident.py", "run_gateway_loop.py", "e8_executor.py", "e8_gold.py"}
)
_LIVE_NAMES = frozenset({"terminal64.exe"})


def rank_of(nice: Any) -> int | None:
    """A process's priority as an ORDERED rank (0 idle .. 5 realtime); None when unreadable.

    Windows psutil returns the class constant; POSIX returns niceness, mapped onto the same ranks
    so the rule is testable off the box (19 idle, 1..14 below normal, 0 normal, <0 above).
    """
    if not isinstance(nice, int) or isinstance(nice, bool):
        return None
    if nice > 19:  # every Windows class constant is above POSIX's range
        return CLASS_RANK.get(nice)
    if nice >= 15:
        return 0
    if nice >= 1:
        return 1
    if nice == 0:
        return 2
    return 3 if nice >= -10 else 4


def _script_names(cmdline: Iterable[Any]) -> set[str]:
    args = [str(a) for a in (cmdline or [])]
    if "-c" in args:  # a diagnostic `python -c` names no script
        args = args[: args.index("-c")]
    return {a.strip('"').replace("\\", "/").rsplit("/", 1)[-1].lower() for a in args}


def own_class(name: str, cmdline: Iterable[Any]) -> str | None:
    """The class a process belongs to by ITS OWN command line; None when only its parents say.

    Only an INTERPRETER running a script is that script: git, an editor or a grep with
    `external_gauntlet.py` in its argv is not the judge (audit probe G). The judge's .cmd
    launcher and the frontier lane are recognised under cmd.exe only.
    """
    args = [str(a) for a in (cmdline or [])]
    joined = " ".join(args).replace("\\", "/").lower()
    scripts = _script_names(args)
    n = str(name or "").lower()
    if n in _LIVE_NAMES:
        return "live"
    if _is_python(n):
        if scripts & _WARM_SCRIPTS:
            return "judge_warm"
        if (
            scripts & _JUDGE_SCRIPTS
            or "from scripts.external_gauntlet import shard_worker" in joined
        ):
            return "judge"
        if scripts & _LIVE_SCRIPTS:
            return "live"
        return None
    if n == "cmd.exe":
        if _AUDIT_MARK in joined:
            return "audit"
        if "rungauntlet.cmd" in scripts:
            return "judge"
    return None


def _is_python(name: str) -> bool:
    n = str(name or "").lower()
    return n.startswith("python") or n.startswith("py.exe") or n == "py"


def classify(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach `cls` to each {pid, ppid, name, cmdline, nice, cpu_cores} row.

    A process inherits the class of its nearest classified ancestor (shard workers, the frontier
    organs under cmd.exe); an unclaimed PYTHON process is a `miner` -- everything the judge
    competes with for research CPU; anything else is `other` and plays no part in the rule.
    """
    by_pid = {int(r["pid"]): r for r in rows if r.get("pid") is not None}
    own = {pid: own_class(r.get("name", ""), r.get("cmdline") or []) for pid, r in by_pid.items()}
    out = []
    for pid, r in by_pid.items():
        cls, cur, seen = own[pid], pid, 0
        while cls is None and seen < 16:
            parent = int(by_pid.get(cur, {}).get("ppid") or 0)
            if not parent or parent not in by_pid or not _born_before(by_pid[parent], by_pid[cur]):
                break  # a reused parent pid is not a parent (audit probe H)
            cur = parent
            cls, seen = own.get(cur), seen + 1
        if cls is None:
            cls = "miner" if _is_python(r.get("name", "")) else "other"
        out.append({**r, "cls": cls, "rank": rank_of(r.get("nice")), "unreadable": _unreadable(r)})
    return out


def _born_before(parent: dict[str, Any], child: dict[str, Any]) -> bool:
    """A parent must have existed before its child; an unknown start time proves nothing."""
    p, c = parent.get("create_time"), child.get("create_time")
    return isinstance(p, (int, float)) and isinstance(c, (int, float)) and p <= c


def _unreadable(r: dict[str, Any]) -> bool:
    """A python or live row whose command line or priority could not be read."""
    n = str(r.get("name") or "").strip().lower()
    if not n:
        return True  # an unnamed row could be anything, a live clock included
    if not (_is_python(n) or n in _LIVE_NAMES):
        return False
    return r.get("cmdline") is None or rank_of(r.get("nice")) is None


def judge_target(
    miner_ranks: Iterable[int | None],
    live_ranks: Iterable[int | None] = (),
    *,
    registered_live: int | str | None = "READ",
    unreadable: int = 0,
) -> dict[str, Any]:
    """THE RULE, in one place, and it FAILS CLOSED (audit HOLD of be6a305b7).

    target = the LOWEST priority held by any miner         -- never above ANY miner
             capped at NORMAL                              -- never AboveNormal/High/Realtime
             strictly below every live class: the REGISTERED E8 class (a fixed ceiling, read
             from install_e8_tasks.ps1, whether or not E8 runs at the census) AND every live
             process observed (terminal64, the gateway, E8)
             no raise at all while any python or live row is unreadable, or the registered
             class cannot be read
    and never below BELOW_NORMAL, where the judge already sits: the caps only ever stop a RAISE.

    In practice, with E8 registered at Priority 4 (NORMAL), the judge never goes above
    BELOW_NORMAL: a raise needs every live process provably above the new class.

    IDLE-CLASS MINERS ARE REPORTED, NOT COUNTED: a process at IDLE has declared it takes only CPU
    nothing else wants, and counting it would drag the judge below every working miner.
    """
    floor = CLASS_RANK[BELOW_NORMAL]
    reg = registered_live_rank() if registered_live == "READ" else registered_live
    all_m = sorted(r for r in miner_ranks if isinstance(r, int))
    miners = [r for r in all_m if r >= floor]
    lives = sorted(r for r in live_ranks if isinstance(r, int))
    idle_miners = len(all_m) - len(miners)
    if not miners:
        return {
            "status": UNMEASURED,
            "rank": None,
            "idle_miners": idle_miners,
            "why": "no miner measured at BELOW_NORMAL or above: the judge keeps the "
            "launcher default (BELOW_NORMAL)",
        }
    rank, bound = miners[0], "equal to the lowest-priority miner"
    if rank > JUDGE_CEILING_RANK:
        rank, bound = JUDGE_CEILING_RANK, "capped at NORMAL"
    ceilings = [*lives, *([reg] if isinstance(reg, int) else [])]
    if ceilings and rank >= min(ceilings):
        capped = max(min(ceilings) - 1, floor)
        if capped < rank:
            rank, bound = capped, "strictly below the lowest live class (registered or observed)"
    if rank > floor and (unreadable or not isinstance(reg, int)):
        rank = floor
        bound = "no raise: " + (
            f"{unreadable} python/live row(s) unreadable"
            if unreadable
            else "the registered live class is unreadable"
        )
    return {
        "status": "MEASURED",
        "rank": rank,
        "class": RANK_NAME[rank],
        "lowest_miner": RANK_NAME[miners[0]],
        "highest_miner": RANK_NAME[miners[-1]],
        "idle_miners": idle_miners,
        "unreadable_rows": int(unreadable),
        "registered_live": RANK_NAME.get(reg) if isinstance(reg, int) else UNMEASURED,
        "lowest_live": RANK_NAME[lives[0]] if lives else None,
        "bound": bound,
        "above_any_miner": rank > miners[0],
    }


def snapshot(sample_s: float = 0.0) -> list[dict[str, Any]]:
    """Every process's pid, parent, name, command line, priority and (optionally) CPU, by psutil.

    psutil ONLY (never CIM, which has hung on this box). A process that vanishes or refuses is
    skipped; nothing here can raise.
    """
    import time

    import psutil  # type: ignore[import-untyped,unused-ignore]

    procs = []
    for p in psutil.process_iter(["pid", "ppid", "name", "cmdline"]):
        try:
            if sample_s:
                p.cpu_percent(None)
            procs.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    if sample_s:
        time.sleep(sample_s)
    rows = []
    for p in procs:
        try:
            nice = p.nice()
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            nice = None
        try:
            cpu = round(p.cpu_percent(None) / 100.0, 3) if sample_s else None
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            cpu = None
        try:
            created = p.create_time()
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            created = None
        # None (never []) when the command line was refused: an unreadable row is evidence of
        # nothing and blocks any raise (see `judge_target`).
        rows.append(
            {
                "pid": p.info.get("pid"),
                "ppid": p.info.get("ppid"),
                "name": p.info.get("name") or "",
                "cmdline": p.info.get("cmdline"),
                "nice": nice,
                "cpu_cores": cpu,
                "create_time": created,
            }
        )
    return rows


def _short(cmdline: list[Any]) -> str:
    """A command line reduced to its script (or module) and up to three arguments after it."""
    args = [str(x) for x in cmdline]
    for i, a in enumerate(args):
        if a.lower().endswith((".py", ".cmd")) or (a == "-m" and i + 1 < len(args)):
            j = i + 1 if a == "-m" else i
            head = args[j].replace("\\", "/").rsplit("/", 1)[-1]
            return " ".join([head, *args[j + 1 : j + 4]])
    return " ".join(args[:4])


def census(
    rows: list[dict[str, Any]], registered_live: int | str | None = "READ"
) -> dict[str, Any]:
    """Per class: process count, priorities held, CPU, and DUPLICATED command lines."""
    rows = classify(rows)
    classes: dict[str, dict[str, Any]] = {}
    for cls in ("judge", "judge_warm", "miner", "audit", "live", "other"):
        mine = [r for r in rows if r["cls"] == cls]
        cpu = [r["cpu_cores"] for r in mine if isinstance(r.get("cpu_cores"), (int, float))]
        classes[cls] = {
            "n": len(mine),
            "priorities": dict(Counter(RANK_NAME.get(r["rank"], UNMEASURED) for r in mine)),
            "cpu_cores": round(sum(cpu), 2) if cpu else UNMEASURED,
        }
    # A DUPLICATE is the same command line running more than once: a stacked or hung schedule.
    # Pool workers of one parent are NOT duplicates (they share a parent), so only distinct
    # parents count -- a pool is one job, ten copies of one organ under ten parents is not.
    groups: dict[tuple[str, str], set[int]] = defaultdict(set)
    for r in rows:
        if r["cls"] in ("other",) or not r.get("cmdline"):
            continue
        groups[(r["cls"], _short(r["cmdline"]))].add(int(r.get("ppid") or 0))
    dup_rows = sorted(
        ((len(pp), c, cmd) for (c, cmd), pp in groups.items() if len(pp) > 1), reverse=True
    )
    dups = [{"class": c, "command": cmd, "distinct_parents": n} for n, c, cmd in dup_rows]
    target = judge_target(
        (r["rank"] for r in rows if r["cls"] == "miner"),
        (r["rank"] for r in rows if r["cls"] == "live"),
        registered_live=registered_live,
        unreadable=sum(1 for r in rows if r["unreadable"]),
    )
    judge_ranks = sorted(
        {r["rank"] for r in rows if r["cls"] == "judge" and isinstance(r["rank"], int)}
    )
    verdict = UNMEASURED
    if target["status"] == "MEASURED" and judge_ranks:
        t = target["rank"]
        verdict = (
            "EQUAL"
            if judge_ranks == [t]
            else "JUDGE_ABOVE_MINERS"
            if max(judge_ranks) > t
            else "JUDGE_BELOW_MINERS"
        )
    return {
        "classes": classes,
        "target": target,
        "judge_priorities_now": [RANK_NAME[r] for r in judge_ranks],
        "verdict": verdict,
        "duplicates": dups[:40],
        "rows": rows,
    }


def _default_setter(pid: int, cls_const: int, expect: dict[str, Any]) -> None:
    """Set one pid's class -- only if it is STILL the process the census saw (audit: pid reuse).

    The start time and command line are re-read and must match the snapshot; otherwise the pid
    now belongs to someone else and nothing is changed.
    """
    import psutil  # type: ignore[import-untyped,unused-ignore]

    p = psutil.Process(pid)
    if expect.get("create_time") is None or p.create_time() != expect.get("create_time"):
        raise LookupError("pid reused: start time differs from the census")
    if (expect.get("cmdline") or None) != (p.cmdline() or None):
        raise LookupError("pid reused: command line differs from the census")
    if sys.platform == "win32":
        p.nice(cls_const)
    else:
        p.nice({IDLE: 19, BELOW_NORMAL: 10, NORMAL: 0}.get(cls_const, 0))


def equalise(
    rows: list[dict[str, Any]], target_rank: int | None, *, apply: bool, setter: Any = None
) -> list[dict[str, Any]]:
    """Set every JUDGE process (never judge_warm, miner, audit, live or other) to the target.

    `setter(pid, class_constant, row)` must refuse a pid that is no longer the row's process.
    """
    if target_rank is None:
        return []
    setter = setter or _default_setter
    changes = []
    for r in rows:
        if r.get("cls") != "judge" or r.get("rank") == target_rank or r.get("rank") is None:
            continue
        rec = {
            "pid": r["pid"],
            "from": RANK_NAME[r["rank"]],
            "to": RANK_NAME[target_rank],
            "command": _short(r.get("cmdline") or []),
            "applied": False,
            "create_time": r.get("create_time"),
        }
        if apply:
            try:
                setter(int(r["pid"]), RANK_CLASS[target_rank], r)
                rec["applied"] = True
            except Exception as exc:
                rec["error"] = f"{type(exc).__name__}: {exc}"
        changes.append(rec)
    return changes


#: THE MISSED-GROWTH LINE (GROWTH GOVERNANCE; audit HOLD of be6a305b7 and of d465792f118). A
#: raise to EQUAL can cost a miner at that class its share of the CPU the judge now competes for;
#: a LOWERING (a judge found above the miners) costs the judge its share. The rail register is
#: sealed (`libs/portfolio/rails.py`), so -- exactly as the judge's watchdog does with
#: GAUNTLET_STALL.json -- every APPLIED change is PUBLISHED as one line on this organ's own
#: artifact, and `research/missed_growth.py` carries it into MISSED_GROWTH.json
#: (`organ_published_lines`). Appended under an exclusive lock file (several processes write:
#: the launcher, each sweep child, a manual --apply), deduplicated per (day, pid, create_time,
#: by) so a pid Windows reuses the same day is a second line, never a hidden one. A write that
#: cannot take the lock is NOT made unlocked: it raises `LineUnrecorded`, and the caller reverts
#: the change it could not account for (or says so, UNMEASURED).
RAISES = DESK / "reports" / "JUDGE_PRIORITY_RAISES.json"
MISSED_GROWTH_RAIL = "judge_priority_raise"
RAISES_HISTORY = 200
RAISES_LOCK_S = 30.0


class LineUnrecorded(RuntimeError):
    """The missed-growth line for an applied change could not be written (lock not held)."""


def _rank_by_name(name: Any) -> int | None:
    return {v: k for k, v in RANK_NAME.items()}.get(str(name))


def _change_line(c: dict[str, Any], by: str, now: datetime) -> dict[str, Any]:
    up = (_rank_by_name(c.get("to")) or 0) > (_rank_by_name(c.get("from")) or 0)
    return {
        "day": now.date().isoformat(),
        "at": now.isoformat(timespec="seconds"),
        "rail": MISSED_GROWTH_RAIL,
        "kind": "opportunity_cost",
        "value": None,
        "verdict": UNMEASURED,
        "direction": "raise" if up else "lower",
        "units": (
            "miner CPU shared with the judge at its new class"
            if up
            else "judge CPU given back to the miners at its new class"
        ),
        "lost_s": None,
        "pid": c.get("pid"),
        "create_time": c.get("create_time"),
        "from": c.get("from"),
        "to": c.get("to"),
        "by": by,
        "command": c.get("command"),
        "why": (
            (
                "the judge was raised to EQUAL the miners: it now shares their class "
                "round-robin (it can never preempt one), bounded by its own busy cores"
            )
            if up
            else (
                "the judge was found ABOVE the miners and lowered to EQUAL them: it now "
                "gets their round-robin share, not more; the judging it loses is bounded "
                "by its own busy cores"
            )
        )
        + "; measure with reports/JUDGING_THROUGHPUT.json busy_other_cores "
        "before/after. The E[log W] price is not measured",
    }


def _changed(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for c in changes:
        a, b = _rank_by_name(c.get("from")), _rank_by_name(c.get("to"))
        if c.get("applied") and a is not None and b is not None and a != b:
            out.append(c)
    return out


def _dedup_key(day: Any, x: dict[str, Any]) -> tuple[Any, str, str, Any]:
    return day, str(x.get("pid")), str(x.get("create_time")), x.get("by")


def record_raises(
    changes: list[dict[str, Any]], by: str, path: Path | None = None, *, lock_s: float | None = None
) -> int:
    """Publish a missed-growth line for every APPLIED change of class (raise OR lower).

    Returns how many lines were added. Raises `LineUnrecorded` when the lock cannot be held --
    the write is skipped, never made unlocked -- and lets any write error propagate, so a caller
    that applied a change always learns its line is missing.
    """
    moved = _changed(changes)
    if not moved:
        return 0
    target = Path(path or RAISES)
    now = datetime.now(UTC)
    from libs.research.artifact_chain import _locked

    with _locked(target, RAISES_LOCK_S if lock_s is None else lock_s) as held:
        if not held:
            raise LineUnrecorded(
                f"lock on {target.name} not held: line skipped, not written unlocked"
            )
        try:
            doc = json.loads(target.read_text("utf-8"))
            doc = doc if isinstance(doc, dict) else {}
        except (OSError, ValueError):
            doc = {}
        lines = [x for x in (doc.get("missed_growth") or []) if isinstance(x, dict)]
        seen = {_dedup_key(x.get("day"), x) for x in lines}
        day = now.date().isoformat()
        fresh = [
            _change_line(c, by, now) for c in moved if _dedup_key(day, {**c, "by": by}) not in seen
        ]
        if not fresh:
            return 0
        doc.update(
            {
                "at": now.isoformat(timespec="seconds"),
                "missed_growth": [*lines, *fresh][-RAISES_HISTORY:],
                "rule": "one line per applied judge priority change (raise or lower); "
                "carried by research/missed_growth.py",
            }
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f"{target.name}.{os.getpid()}.{os.urandom(4).hex()}.tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, target)
    return len(fresh)


def _is_raise(c: dict[str, Any]) -> bool:
    return (_rank_by_name(c.get("to")) or 0) > (_rank_by_name(c.get("from")) or 0)


def spill_path(path: Path | None = None) -> Path:
    """Where lines that could not reach the locked artifact go: an append-only sidecar that
    `research/missed_growth.py` reads beside it (audit HOLD of f798fe7293d)."""
    target = Path(path or RAISES)
    return target.with_name(target.stem + "_UNRECORDED.jsonl")


#: How long a spill waits for its OWN lock (a different file from the artifact's).
SPILL_LOCK_S = 5.0


def _spill(lines: list[dict[str, Any]], path: Path | None = None) -> str:
    """Append the lines to the sidecar under the sidecar's own lock, as ONE buffer written in
    full (audit HOLD of 1235ab79c10: the Windows C runtime emulates O_APPEND with a seek before
    each write, so two unlocked writers can overwrite each other). Returns WRITTEN or FAILED:
    ... -- never raises; a FAILED spill stays visible through the caller's published record,
    which `research/missed_growth.py` also reads."""
    if not lines:
        return "NONE"
    try:
        from libs.research.artifact_chain import _locked

        target = spill_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        data = "".join(json.dumps(ln, default=str) + "\n" for ln in lines).encode("utf-8")
        with _locked(target, SPILL_LOCK_S) as held:
            if not held:
                return f"FAILED: LineUnrecorded: lock on {target.name} not held"
            fd = os.open(str(target), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
            try:
                view = memoryview(data)
                while view:
                    n = os.write(fd, view)
                    if n <= 0:
                        raise OSError("short write")
                    view = view[n:]
            finally:
                os.close(fd)
        return "WRITTEN"
    except Exception as exc:
        return f"FAILED: {type(exc).__name__}: {exc}"


def account(
    changes: list[dict[str, Any]], by: str, revert: Any, path: Path | None = None
) -> dict[str, Any]:
    """Record the applied changes' lines; if that fails, UNDO each RAISE and say so.

    Only a RAISE is reverted (audit HOLD of f798fe7293d): a lowering is the safe direction --
    reverting it would put the judge back ABOVE the miners -- so it STANDS, reported
    `changed: True` with an UNMEASURED line. `revert(change)` puts one raised process back to its
    `from` class and must refuse a pid that is no longer the change's process. A raise that could
    not be reverted is likewise `changed: True` with an UNMEASURED line. Every such line is also
    appended to the sidecar `spill_path()`, which the missed-growth organ reads, so no standing
    change is invisible to the ledger.
    """
    try:
        return {
            "missed_growth_lines": record_raises(changes, by, path),
            "changed": bool(_changed(changes)),
            "line": "WRITTEN",
        }
    except Exception as exc:
        why = f"{type(exc).__name__}: {exc}"
    reverted, stuck, kept = [], [], []
    for c in _changed(changes):
        if not _is_raise(c):
            c["kept"] = "lowering stands: the safe direction is never undone"
            kept.append(c)
            continue
        try:
            revert(c)
            c["reverted"] = True
            reverted.append(c.get("pid"))
        except Exception as exc:
            c["revert_error"] = f"{type(exc).__name__}: {exc}"
            stuck.append(c)
    now = datetime.now(UTC)
    lines = [
        {
            **_change_line(c, by, now),
            "line_error": why,
            "why": (
                f"line NOT written to {Path(path or RAISES).name} ({why}); "
                + (
                    "the judge was LOWERED to equal the miners and stays lowered (the safe "
                    "direction)"
                    if c in kept
                    else "the raise could not be reverted: it stands unaccounted"
                )
                + "; the E[log W] price is not measured"
            ),
        }
        for c in [*kept, *stuck]
    ]
    return {
        "missed_growth_lines": 0,
        "line": UNMEASURED,
        "line_error": why,
        "reverted": reverted,
        "unreverted": [c.get("pid") for c in stuck],
        "kept_lowered": [c.get("pid") for c in kept],
        "changed": bool(stuck or kept),
        "missed_growth": lines,
        "spill": _spill(lines, path),
    }


def revert_with(rows: list[dict[str, Any]], setter: Any = None) -> Any:
    """A `revert(change)` that sets the change's pid back to its `from` class, through the same
    identity-checked setter as the change itself: the census row it acted on (matched by pid AND
    create_time) is the expectation, so a pid reused since is refused, never touched."""
    setter = setter or _default_setter
    by_id = {(r.get("pid"), r.get("create_time")): r for r in rows}

    def _revert(c: dict[str, Any]) -> None:
        rank = _rank_by_name(c.get("from"))
        row = by_id.get((c.get("pid"), c.get("create_time")))
        if rank is None or row is None:
            raise LookupError(f"no census row for pid {c.get('pid')} / class {c.get('from')!r}")
        setter(int(c["pid"]), RANK_CLASS[rank], row)

    return _revert


def sweep_creationflags(rows: list[dict[str, Any]] | None = None) -> tuple[int, dict[str, Any]]:
    """The Windows creation flag for the judge's next sweep child, and the reading behind it.

    Falls back to BELOW_NORMAL (exactly what the launcher used before) on any failure, so this
    can never put the judge anywhere it has not already been except LEVEL with measured miners.
    """
    try:
        c = census(snapshot() if rows is None else rows)
        t = c["target"]
        rank = t["rank"] if t.get("status") == "MEASURED" else DEFAULT_RANK
        return RANK_CLASS[rank], {
            "target": t,
            "verdict_before": c["verdict"],
            "classes": c["classes"],
        }
    except Exception as exc:
        return BELOW_NORMAL, {
            "target": {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}
        }


def _cadence_state() -> dict[str, Any]:
    try:
        doc = json.loads((DESK / "data" / "gauntlet_cadence_state.json").read_text("utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {"status": UNMEASURED, "why": "data/gauntlet_cadence_state.json absent"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--apply",
        action="store_true",
        help="set every judge process to the measured target (judge ONLY)",
    )
    ap.add_argument("--no-write", action="store_true", help="print only; write no report")
    ap.add_argument("--sample-s", type=float, default=2.0, help="CPU sample window")
    a = ap.parse_args(argv)
    rows = snapshot(a.sample_s)
    c = census(rows)
    changes = equalise(c["rows"], c["target"].get("rank"), apply=a.apply)
    accounted = None
    if a.apply:
        accounted = account(changes, "judge_priority --apply", revert_with(c["rows"]))
    host = os.environ.get("COMPUTERNAME") or (os.uname().nodename if hasattr(os, "uname") else "")
    doc = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "host": host,
        "cores": os.cpu_count(),
        "mode": "apply" if a.apply else "census",
        "classes": c["classes"],
        "target": c["target"],
        "judge_priorities_now": c["judge_priorities_now"],
        "verdict": c["verdict"],
        "changes": changes,
        "accounted": accounted,
        "duplicates": c["duplicates"],
        "cadence": _cadence_state(),
        "rule": (
            "judge priority == the lowest miner priority, never above any miner, "
            "strictly below live clocks, never above NORMAL; only judge processes are "
            "ever changed; miners, audit and live are read, never touched"
        ),
    }
    print(json.dumps({k: v for k, v in doc.items() if k != "duplicates"}, indent=1))
    for d in doc["duplicates"][:15]:
        print(f"  DUPLICATE x{d['distinct_parents']:<3} {d['class']:<6} {d['command']}")
    if not a.no_write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        tmp = REPORT.with_name(f"{REPORT.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, REPORT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
