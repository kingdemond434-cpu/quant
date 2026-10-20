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
RANK_NAME = {0: "IDLE", 1: "BELOW_NORMAL", 2: "NORMAL", 3: "ABOVE_NORMAL", 4: "HIGH",
             5: "REALTIME"}
#: The judge is never raised past this, whatever the miners run at.
JUDGE_CEILING_RANK = CLASS_RANK[NORMAL]
#: What the launcher used before this module and keeps whenever the target is UNMEASURED.
DEFAULT_RANK = CLASS_RANK[BELOW_NORMAL]

_JUDGE_SCRIPTS = frozenset({"external_gauntlet.py", "run_sharded_gauntlet.py", "rungauntlet.cmd"})
_WARM_SCRIPTS = frozenset({"warm_gauntlet_cache.py"})
_AUDIT_MARK = "run_frontier_audit.cmd"
_LIVE_SCRIPTS = frozenset({"gateway_resident.py", "run_gateway_loop.py", "e8_executor.py",
                           "e8_gold.py"})
_LIVE_NAMES = frozenset({"terminal64.exe"})


def rank_of(nice: Any) -> int | None:
    """A process's priority as an ORDERED rank (0 idle .. 5 realtime); None when unreadable.

    Windows psutil returns the class constant; POSIX returns niceness, mapped onto the same ranks
    so the rule is testable off the box (19 idle, 1..14 below normal, 0 normal, <0 above).
    """
    if not isinstance(nice, int) or isinstance(nice, bool):
        return None
    if nice > 19:                          # every Windows class constant is above POSIX's range
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
    if "-c" in args:                       # a diagnostic `python -c` names no script
        args = args[:args.index("-c")]
    return {a.strip('"').replace("\\", "/").rsplit("/", 1)[-1].lower() for a in args}


def own_class(name: str, cmdline: Iterable[Any]) -> str | None:
    """The class a process belongs to by ITS OWN command line; None when only its parents say."""
    args = [str(a) for a in (cmdline or [])]
    joined = " ".join(args).replace("\\", "/").lower()
    scripts = _script_names(args)
    if scripts & _WARM_SCRIPTS:
        return "judge_warm"
    if scripts & _JUDGE_SCRIPTS or "from scripts.external_gauntlet import shard_worker" in joined:
        return "judge"
    if _AUDIT_MARK in joined:
        return "audit"
    if str(name or "").lower() in _LIVE_NAMES or scripts & _LIVE_SCRIPTS:
        return "live"
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
            cur = int(by_pid.get(cur, {}).get("ppid") or 0)
            if not cur or cur not in by_pid:
                break
            cls, seen = own.get(cur), seen + 1
        if cls is None:
            cls = "miner" if _is_python(r.get("name", "")) else "other"
        out.append({**r, "cls": cls, "rank": rank_of(r.get("nice"))})
    return out


def judge_target(miner_ranks: Iterable[int | None],
                 live_ranks: Iterable[int | None] = ()) -> dict[str, Any]:
    """THE RULE, in one place.

    target = the LOWEST priority held by any miner        -- so never above ANY miner
             capped at NORMAL                             -- never AboveNormal/High/Realtime
             strictly below the lowest live CLOCK         -- E8 at 4 must preempt the judge
                                                             (2026-10-08: it starved when level)
    and it is always BELOW_NORMAL or NORMAL: the live cap can only stop a RAISE, it never pushes
    the judge below the BELOW_NORMAL it already holds.

    IDLE-CLASS MINERS ARE REPORTED, NOT COUNTED. A process at IDLE has declared that it takes only
    CPU nothing else wants (the warm cache's own rule); a judge level with every other miner
    preempts it exactly as every other miner already does. Counting it would let one self-yielding
    process drag the judge to IDLE, below every working miner -- a cut of the judge, not equality.
    With no miner at BELOW_NORMAL or above the target is UNMEASURED and nothing changes.
    """
    all_m = sorted(r for r in miner_ranks if isinstance(r, int))
    miners = [r for r in all_m if r >= CLASS_RANK[BELOW_NORMAL]]
    lives = sorted(r for r in live_ranks if isinstance(r, int))
    idle_miners = len(all_m) - len(miners)
    if not miners:
        return {"status": UNMEASURED, "rank": None, "idle_miners": idle_miners,
                "why": "no miner measured at BELOW_NORMAL or above: the judge keeps the "
                       "launcher default (BELOW_NORMAL)"}
    rank, bound = miners[0], "equal to the lowest-priority miner"
    if rank > JUDGE_CEILING_RANK:
        rank, bound = JUDGE_CEILING_RANK, "capped at NORMAL"
    if lives and rank >= lives[0]:
        capped = max(lives[0] - 1, CLASS_RANK[BELOW_NORMAL])
        if capped < rank:
            rank, bound = capped, "strictly below the lowest live clock (2026-10-08)"
    return {"status": "MEASURED", "rank": rank, "class": RANK_NAME[rank],
            "lowest_miner": RANK_NAME[miners[0]], "highest_miner": RANK_NAME[miners[-1]],
            "idle_miners": idle_miners,
            "lowest_live": RANK_NAME[lives[0]] if lives else None, "bound": bound,
            "above_any_miner": rank > miners[0]}


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
        rows.append({"pid": p.info.get("pid"), "ppid": p.info.get("ppid"),
                     "name": p.info.get("name") or "", "cmdline": p.info.get("cmdline") or [],
                     "nice": nice, "cpu_cores": cpu, "create_time": created})
    return rows


def _short(cmdline: list[Any]) -> str:
    """A command line reduced to its script (or module) and up to three arguments after it."""
    args = [str(x) for x in cmdline]
    for i, a in enumerate(args):
        if a.lower().endswith((".py", ".cmd")) or (a == "-m" and i + 1 < len(args)):
            j = i + 1 if a == "-m" else i
            head = args[j].replace("\\", "/").rsplit("/", 1)[-1]
            return " ".join([head, *args[j + 1:j + 4]])
    return " ".join(args[:4])


def census(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Per class: process count, priorities held, CPU, and DUPLICATED command lines."""
    rows = classify(rows)
    classes: dict[str, dict[str, Any]] = {}
    for cls in ("judge", "judge_warm", "miner", "audit", "live", "other"):
        mine = [r for r in rows if r["cls"] == cls]
        cpu = [r["cpu_cores"] for r in mine if isinstance(r.get("cpu_cores"), (int, float))]
        classes[cls] = {
            "n": len(mine),
            "priorities": dict(Counter(RANK_NAME.get(r["rank"], UNMEASURED) for r in mine)),
            "cpu_cores": round(sum(cpu), 2) if cpu else UNMEASURED}
    # A DUPLICATE is the same command line running more than once: a stacked or hung schedule.
    # Pool workers of one parent are NOT duplicates (they share a parent), so only distinct
    # parents count -- a pool is one job, ten copies of one organ under ten parents is not.
    groups: dict[tuple[str, str], set[int]] = defaultdict(set)
    for r in rows:
        if r["cls"] in ("other",) or not r.get("cmdline"):
            continue
        groups[(r["cls"], _short(r["cmdline"]))].add(int(r.get("ppid") or 0))
    dup_rows = sorted(((len(pp), c, cmd) for (c, cmd), pp in groups.items() if len(pp) > 1),
                      reverse=True)
    dups = [{"class": c, "command": cmd, "distinct_parents": n} for n, c, cmd in dup_rows]
    target = judge_target((r["rank"] for r in rows if r["cls"] == "miner"),
                          (r["rank"] for r in rows if r["cls"] == "live"
                           and _is_python(r.get("name", ""))))
    judge_ranks = sorted({r["rank"] for r in rows if r["cls"] == "judge"
                          and isinstance(r["rank"], int)})
    verdict = UNMEASURED
    if target["status"] == "MEASURED" and judge_ranks:
        t = target["rank"]
        verdict = ("EQUAL" if judge_ranks == [t] else
                   "JUDGE_ABOVE_MINERS" if max(judge_ranks) > t else "JUDGE_BELOW_MINERS")
    return {"classes": classes, "target": target, "judge_priorities_now":
            [RANK_NAME[r] for r in judge_ranks], "verdict": verdict, "duplicates": dups[:40],
            "rows": rows}


def equalise(rows: list[dict[str, Any]], target_rank: int | None, *, apply: bool,
             setter: Any = None) -> list[dict[str, Any]]:
    """Set every JUDGE process (never judge_warm, miner, audit, live or other) to the target."""
    if target_rank is None:
        return []
    if setter is None:
        def setter(pid: int, cls_const: int) -> None:
            import psutil  # type: ignore[import-untyped,unused-ignore]
            psutil.Process(pid).nice(cls_const if sys.platform == "win32"
                                     else {0: 19, 1: 10, 2: 0}.get(target_rank, 0))
    changes = []
    for r in rows:
        if r.get("cls") != "judge" or r.get("rank") == target_rank or r.get("rank") is None:
            continue
        rec = {"pid": r["pid"], "from": RANK_NAME[r["rank"]], "to": RANK_NAME[target_rank],
               "command": _short(r.get("cmdline") or []), "applied": False}
        if apply:
            try:
                setter(int(r["pid"]), RANK_CLASS[target_rank])
                rec["applied"] = True
            except Exception as exc:
                rec["error"] = f"{type(exc).__name__}: {exc}"
        changes.append(rec)
    return changes


def sweep_creationflags(rows: list[dict[str, Any]] | None = None) -> tuple[int, dict[str, Any]]:
    """The Windows creation flag for the judge's next sweep child, and the reading behind it.

    Falls back to BELOW_NORMAL (exactly what the launcher used before) on any failure, so this
    can never put the judge anywhere it has not already been except LEVEL with measured miners.
    """
    try:
        c = census(snapshot() if rows is None else rows)
        t = c["target"]
        rank = t["rank"] if t.get("status") == "MEASURED" else DEFAULT_RANK
        return RANK_CLASS[rank], {"target": t, "verdict_before": c["verdict"],
                                  "classes": c["classes"]}
    except Exception as exc:
        return BELOW_NORMAL, {"target": {"status": UNMEASURED,
                                         "why": f"{type(exc).__name__}: {exc}"}}


def _cadence_state() -> dict[str, Any]:
    try:
        doc = json.loads((DESK / "data" / "gauntlet_cadence_state.json").read_text("utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {"status": UNMEASURED, "why": "data/gauntlet_cadence_state.json absent"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true",
                    help="set every judge process to the measured target (judge ONLY)")
    ap.add_argument("--no-write", action="store_true", help="print only; write no report")
    ap.add_argument("--sample-s", type=float, default=2.0, help="CPU sample window")
    a = ap.parse_args(argv)
    rows = snapshot(a.sample_s)
    c = census(rows)
    changes = equalise(c["rows"], c["target"].get("rank"), apply=a.apply)
    host = os.environ.get("COMPUTERNAME") or (os.uname().nodename if hasattr(os, "uname")
                                              else "")
    doc = {"at": datetime.now(UTC).isoformat(timespec="seconds"), "host": host,
           "cores": os.cpu_count(), "mode": "apply" if a.apply else "census",
           "classes": c["classes"], "target": c["target"],
           "judge_priorities_now": c["judge_priorities_now"], "verdict": c["verdict"],
           "changes": changes, "duplicates": c["duplicates"], "cadence": _cadence_state(),
           "rule": ("judge priority == the lowest miner priority, never above any miner, "
                    "strictly below live clocks, never above NORMAL; only judge processes are "
                    "ever changed; miners, audit and live are read, never touched")}
    print(json.dumps({k: v for k, v in doc.items() if k != "duplicates"}, indent=1))
    for d in doc["duplicates"][:15]:
        print(f"  DUPLICATE x{d['distinct_parents']:<3} {d['class']:<6} {d['command']}")
    if not a.no_write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        tmp = REPORT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, REPORT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
