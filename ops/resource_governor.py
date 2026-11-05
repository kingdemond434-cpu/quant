#!/usr/bin/env python3
"""THE BOX RESOURCE GOVERNOR -- release, risk and deploy always get CPU ahead of research.

WHY (measured on the Contabo box, 2026-11-03 23:31Z). CPU sat at 100%. Every Quant-WorkflowGate
sweep since 22:46Z was killed by its 30-minute limit before it logged (0x41306), so no PR could
merge automatically. The 22:50Z adoption stalled for more than 40 minutes holding the git
writer lock. Scheduled tasks start BELOW_NORMAL by default, so the gate and the adoption
competed at the SAME priority as about 60 research threads on 18 cores.

zuck 2026-11-03 23:43Z: guarantee resources for risk controls, the release authority, the merge
gate and deployment; keep research running wherever capacity safely permits; no simple timeout
or priority bump. zuck 2026-09-29 (never-throttle-mining): no scheduler may leave any miner's
throughput below today's. Both hold here: release ops are put AHEAD of research, and research
is never put BEHIND anything it runs level with today.

THE RULES (each tick, every 60 s):

  1. CLASSES, from the command line (the governor runs as SYSTEM, so it sees every one):
       LIVE       -- terminals and executors that move money. NEVER touched, at any load.
       JUDGE      -- the judge and its workers. judge_priority.py owns its class (zuck 10-29
                     reserved it 8 cores); never touched here.
       CRITICAL   -- the gate, live-first, the release authority, adoption, promotion, seal,
                     and risk/kill-switch monitors.
       RESEARCH   -- the desk's research and mining pythons. NEVER lowered.
       UNREADABLE -- a command line this token cannot read (an Administrator token reads no
                     SYSTEM process). Counted, never guessed from the image name, never touched.
                     An unreadable non-OS ancestor shields its whole tree: it could be the gate.
       OTHER      -- everything else. Never touched.
  2. RESERVE. A CRITICAL process (its whole tree) runs at NORMAL. Research and scheduled tasks
     start at BELOW_NORMAL, so this alone puts the gate, adoption and risk ahead of research.
     It never goes above NORMAL, so it never outranks LIVE. A process already at NORMAL or
     higher, or whose class cannot be read, is left alone.
  3. OVERLOAD AND FAN-OUT ARE REPORTED, NOT ACTED ON (Auditor HOLD on d89cba424). Sustained CPU
     >= OVERLOAD_PCT, free RAM below MIN_FREE_RAM_GB, or more than MAX_RESEARCH_PROCS research
     processes are written to REPORT, with how many research processes a throttle would have
     lowered, until a throttle is proven not to cut mining. Nothing is lowered.
  4. JUDGE CORES (zuck 2026-10-29 14:37Z, judge-reserved-cores: "8 of 18 cores reserved for
     the judge, 10 for research"). While any JUDGE process exists, every RESEARCH process is
     kept on RESEARCH_CORES (0-7 and 16-17) by processor affinity, so the judge's 8 cores
     (8-15) stay free for it. Priority cannot do this: the judge must stay below the live E8
     clocks (zuck 10-08), and research at NORMAL out-ranks the judge's BELOW_NORMAL workers
     (measured 11-05 22:40Z: 15 judge workers shared 1.64 cores). Research keeps all 10 of its
     cores and its priority; only the judge's 8 are closed to it. A process the shaper already
     pinned inside the research cores (memecoin 16-17, pf_allocator 0-7) is left as it is.
     When no judge process is left, each process this governor narrowed gets its own affinity
     back, unless something else changed it since. Only on the 18-core box: any other core
     count is reported and nothing is pinned. The judge's own affinity is the judge's
     (judge_priority.py); never set here.
  5. NEVER: a kill, a suspend, a lowered priority, a LIVE, JUDGE or CRITICAL affinity, a
     priority above NORMAL, or a change to a process it cannot classify or whose class or
     affinity it cannot read.

Every tick writes REPORT with the measurements and every action, so a bad tick is visible.

    python ops/resource_governor.py --once            # one tick (what the task runs)
    python ops/resource_governor.py --once --dry-run  # say what it would do, touch nothing
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "desks" / "mt5" / "reports" / "RESOURCE_GOVERNOR.json"
STATE = ROOT / "desks" / "mt5" / "data" / "resource_governor_state.json"

#: Windows priority classes as psutil and kernel32 number them, ranked (judge_priority.py).
IDLE, BELOW_NORMAL, NORMAL, ABOVE_NORMAL, HIGH, REALTIME = 0x40, 0x4000, 0x20, 0x8000, 0x80, 0x100
RANK = {IDLE: 0, BELOW_NORMAL: 1, NORMAL: 2, ABOVE_NORMAL: 3, HIGH: 4, REALTIME: 5}
UNKNOWN = -1  # a class the token could not read

OVERLOAD_PCT = 95.0
OVERLOAD_TICKS = 3
RECOVER_PCT = 80.0
RECOVER_TICKS = 3
MIN_FREE_RAM_GB = 8.0
MAX_RESEARCH_PROCS = 48

#: zuck 2026-10-29 14:37Z: of the box's 18 cores, 8 are the judge's and 10 are research's. The
#: research side keeps the cores the box-local shaper already uses (pf_allocator heavy 0-7,
#: memecoin 16-17), so no research process it pinned has to move.
BOX_CORES = 18
JUDGE_CORES: tuple[int, ...] = tuple(range(8, 16))
RESEARCH_CORES: tuple[int, ...] = tuple(c for c in range(BOX_CORES) if c not in JUDGE_CORES)
NAMED_HIGH = 10  # research processes at NORMAL or above, named in the report

#: Money moves here. Checked FIRST: a command line matching LIVE is never anything else.
LIVE_MARKERS = (
    "terminal64.exe", "metatrader", "e8_executor", "e8-executor", "gold_oco", "ftmo_executor",
    "ftmo_follower", "fusion_executor", "mt5desk\\engine", "mt5desk/engine", "executor.py",
    "deadman", "kill_switch",
)  # fmt: skip
#: The judge (judge_priority.py's own_class names the same scripts).
JUDGE_MARKERS = (
    "external_gauntlet", "run_sharded_gauntlet", "rungauntlet.cmd", "warm_gauntlet_cache",
    "run_frontier_audit",
)  # fmt: skip
#: Release, authority, deployment and risk controls.
CRITICAL_MARKERS = (
    "workflow_gate.ps1", "audit_gate.py", "memecoin_gate.py", "live_first_ci.py",
    "merge_pipeline_watch.py", "release_authority", "authority.py", "run_authority.ps1",
    "adopt-release.ps1", "adopt-and-seal.ps1", "adopt_guard.py", "release_promotion.py",
    "smoke_release.py", "seal-", "box_self_heal.py", "check_desk_health.py", "risk_invariants",
    "rail_monitor", "heat_monitor",
)  # fmt: skip
#: The desk's research tree; a python whose command line names one of these is RESEARCH.
RESEARCH_MARKERS = (
    "desks\\mt5\\research", "desks/mt5/research", "desks\\mt5\\moat", "desks/mt5/moat",
    "department_resident", "deepening_worker", "scout_swarm", "moat_swarm",
    "libs\\alpha_factory", "libs/alpha_factory", "miner",
    "multiprocessing.spawn", "spawn_main", "joblib", "loky",
)  # fmt: skip
#: Unreadable ancestors that are only the OS or the scheduler starting things: they shield
#: nothing. Any OTHER unreadable ancestor (a SYSTEM python or powershell) could be the gate or
#: adoption, so nothing under it is counted as research.
OS_ROOTS = frozenset({
    "system", "system idle process", "smss.exe", "csrss.exe", "wininit.exe", "services.exe",
    "svchost.exe", "taskhostw.exe", "taskeng.exe", "explorer.exe", "winlogon.exe",
})  # fmt: skip


@dataclass
class Proc:
    pid: int
    ppid: int
    cmd: str
    prio: int  # UNKNOWN when the token cannot read it
    started: float  # epoch seconds
    name: str = ""  # image name; readable even when the command line is not
    affinity: tuple[int, ...] | None = None  # None when the token cannot read it


@dataclass
class Plan:
    mode: str
    set_to: dict[int, int] = field(default_factory=dict)  # pid -> NORMAL (the only write)
    why: dict[int, str] = field(default_factory=dict)
    classes: dict[str, int] = field(default_factory=dict)
    would_yield: int = 0  # research a throttle would have lowered: REPORTED, never applied
    pin: dict[int, tuple[int, ...]] = field(default_factory=dict)  # research -> research cores
    unpin: dict[int, tuple[int, ...]] = field(default_factory=dict)  # pid -> its own affinity
    narrowed: dict[str, dict[str, list[int]]] = field(default_factory=dict)  # kept in STATE
    reserve: str = "off"
    research_by_class: dict[str, int] = field(default_factory=dict)
    research_high: list[dict[str, Any]] = field(default_factory=list)


def classify(cmd: str) -> str:
    low = cmd.lower()
    if not low.strip():
        return "UNREADABLE"
    if any(m in low for m in LIVE_MARKERS):
        return "LIVE"
    if any(m in low for m in JUDGE_MARKERS):
        return "JUDGE"
    if any(m in low for m in CRITICAL_MARKERS):
        return "CRITICAL"
    if "python" in low and any(m in low for m in RESEARCH_MARKERS):
        return "RESEARCH"
    return "OTHER"


def _trees(procs: list[Proc], roots: set[int]) -> set[int]:
    """`roots` plus every descendant. A "parent" that started after its child is a reused pid
    (Windows recycles them), never a parent, so its tree is not inherited."""
    by = {p.pid: p for p in procs}
    kids: dict[int, list[int]] = {}
    for p in procs:
        parent = by.get(p.ppid)
        if p.ppid != p.pid and parent is not None and parent.started <= p.started:
            kids.setdefault(p.ppid, []).append(p.pid)
    out, todo = set(), list(roots)
    while todo:
        pid = todo.pop()
        if pid in out:
            continue
        out.add(pid)
        todo.extend(kids.get(pid, []))
    return out


def next_mode(mode: str, hot: int, cool: int) -> str:
    if mode == "NORMAL" and hot >= OVERLOAD_TICKS:
        return "THROTTLE"
    if mode == "THROTTLE" and cool >= RECOVER_TICKS:
        return "NORMAL"
    return mode


def _key(p: Proc) -> str:
    """A pid with its start time: Windows recycles pids, so a pid alone names nobody."""
    return f"{p.pid}:{p.started:.3f}"


CLASS_NAME = {IDLE: "IDLE", BELOW_NORMAL: "BELOW_NORMAL", NORMAL: "NORMAL",
              ABOVE_NORMAL: "ABOVE_NORMAL", HIGH: "HIGH", REALTIME: "REALTIME"}  # fmt: skip


def plan(
    procs: list[Proc],
    mode: str,
    ncpu: int = BOX_CORES,
    narrowed: Mapping[str, Mapping[str, list[int]]] | None = None,
) -> Plan:
    """What to change, from the processes and the load mode. Pure. It plans two kinds of
    change: CRITICAL up to NORMAL, and, while the judge runs, research held to the research
    cores (rule 4). `narrowed` is what earlier ticks narrowed, by _key, so it can be given back."""
    by = {p.pid: p for p in procs}
    cls = {p.pid: classify(p.cmd) for p in procs}
    live = _trees(procs, {pid for pid, c in cls.items() if c == "LIVE"})
    judge = _trees(procs, {pid for pid, c in cls.items() if c == "JUDGE"}) - live
    crit = _trees(procs, {pid for pid, c in cls.items() if c == "CRITICAL"}) - live - judge
    unreadable = {pid for pid, c in cls.items() if c == "UNREADABLE"}
    shield = _trees(procs, {p for p in unreadable if by[p].name.lower() not in OS_ROOTS})
    research_roots = {pid for pid, c in cls.items() if c == "RESEARCH"}
    research = _trees(procs, research_roots) - live - judge - crit - shield - unreadable
    out = Plan(mode=mode, classes={
        "LIVE": len(live), "JUDGE": len(judge), "CRITICAL": len(crit),
        "RESEARCH": len(research), "UNREADABLE": len(unreadable),
        "SHIELDED": len(shield - unreadable - live - judge - crit),
        "OTHER": len(procs) - len(live | judge | crit | research | unreadable | shield),
    })  # fmt: skip
    for pid in crit:
        if by[pid].prio != UNKNOWN and RANK.get(by[pid].prio, 0) < RANK[NORMAL]:
            out.set_to[pid] = NORMAL
            out.why[pid] = "critical: reserved above research"
    out.would_yield = (
        len(research) if mode == "THROTTLE" else max(0, len(research) - MAX_RESEARCH_PROCS)
    )
    _reserve_judge_cores(out, procs, research, judge, ncpu, dict(narrowed or {}))
    for pid in sorted(research):
        name = CLASS_NAME.get(by[pid].prio, "UNKNOWN")
        out.research_by_class[name] = out.research_by_class.get(name, 0) + 1
        if RANK.get(by[pid].prio, 0) >= RANK[NORMAL] and len(out.research_high) < NAMED_HIGH:
            parent = by.get(by[pid].ppid)
            out.research_high.append({
                "pid": pid, "class": name, "cmd": by[pid].cmd[:200],
                "parent": (parent.cmd or parent.name)[:200] if parent else "",
            })  # fmt: skip
    return out


def _reserve_judge_cores(
    out: Plan,
    procs: list[Proc],
    research: set[int],
    judge: set[int],
    ncpu: int,
    narrowed: dict[str, Mapping[str, list[int]]],
) -> None:
    """Rule 4. Narrow research to RESEARCH_CORES while a judge process exists; give each
    narrowed process its own affinity back once none does. Never touches anything else."""
    by_key = {_key(p): p for p in procs}
    allowed = set(RESEARCH_CORES)
    if ncpu != BOX_CORES:
        out.reserve = f"off: {ncpu} cores, the split is for the {BOX_CORES}-core box"
    elif judge:
        out.reserve = f"on: {len(judge)} judge process(es); research held to {RESEARCH_CORES}"
    else:
        out.reserve = "off: no judge process"
    on = out.reserve.startswith("on")
    for key, rec in narrowed.items():
        p = by_key.get(key)
        if p is None or p.affinity is None or list(p.affinity) != list(rec["set"]):
            continue  # gone, unreadable, or changed by something else since: not ours now
        if on and p.pid in research:
            out.narrowed[key] = {"orig": list(rec["orig"]), "set": list(rec["set"])}
        else:
            out.unpin[p.pid] = tuple(rec["orig"])
    if not on:
        return
    by = {q.pid: q for q in procs}
    for pid in sorted(research):
        p = by[pid]
        if p.affinity is None or _key(p) in out.narrowed:
            continue
        keep = tuple(sorted(set(p.affinity) & allowed)) or RESEARCH_CORES
        if keep != tuple(sorted(p.affinity)):
            out.pin[pid] = keep
            out.narrowed[_key(p)] = {"orig": list(p.affinity), "set": list(keep)}


# ------------------------------------------------------------------ actuation (box only)
def _snapshot() -> tuple[list[Proc], float, float]:
    import psutil  # type: ignore[import-untyped,unused-ignore]

    procs = []
    for p in psutil.process_iter(["pid", "ppid", "cmdline", "name", "create_time"]):
        # process_iter leaves a refused field as None: an unreadable command line stays ""
        # (UNREADABLE, never guessed from the image name) and an unreadable class UNKNOWN.
        try:
            info = p.info
            try:
                prio = int(p.nice())
            except (psutil.AccessDenied, OSError):
                prio = UNKNOWN
            try:
                aff: tuple[int, ...] | None = tuple(p.cpu_affinity())
            except (psutil.AccessDenied, OSError, AttributeError):
                aff = None
            procs.append(
                Proc(
                    int(info["pid"]),
                    int(info.get("ppid") or 0),
                    " ".join(info.get("cmdline") or []),
                    prio,
                    float(info.get("create_time") or 0.0),
                    str(info.get("name") or ""),
                    aff,
                )
            )
        except (psutil.NoSuchProcess, ValueError, TypeError):
            continue
    cpu = float(psutil.cpu_percent(interval=5.0))
    free_gb = float(psutil.virtual_memory().available) / 2**30
    return procs, cpu, free_gb


def _set(pid: int, prio: int) -> str | None:
    import psutil  # type: ignore[import-untyped,unused-ignore]

    try:
        psutil.Process(pid).nice(prio)
        return None
    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError) as exc:
        return f"{type(exc).__name__}: {exc}"


def _set_affinity(pid: int, cores: tuple[int, ...]) -> str | None:
    import psutil  # type: ignore[import-untyped,unused-ignore]

    try:
        psutil.Process(pid).cpu_affinity(list(cores))
        return None
    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError, ValueError) as exc:
        return f"{type(exc).__name__}: {exc}"


def _load(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(path: Path, doc: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def tick(
    snapshot: Callable[[], tuple[list[Proc], float, float]] = _snapshot,
    setter: Callable[[int, int], str | None] = _set,
    state_path: Path = STATE,
    report_path: Path = REPORT,
    dry: bool = False,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    pinner: Callable[[int, tuple[int, ...]], str | None] = _set_affinity,
    ncpu: int | None = None,
) -> dict[str, Any]:
    procs, cpu, free_gb = snapshot()
    st = _load(state_path)
    hot = int(st.get("hot") or 0)
    cool = int(st.get("cool") or 0)
    overloaded = cpu >= OVERLOAD_PCT or free_gb < MIN_FREE_RAM_GB
    hot = hot + 1 if overloaded else 0
    cool = cool + 1 if (cpu < RECOVER_PCT and free_gb >= MIN_FREE_RAM_GB) else 0
    mode = next_mode(str(st.get("mode") or "NORMAL"), hot, cool)
    by = {p.pid: p for p in procs}
    narrowed = st.get("narrowed") if isinstance(st.get("narrowed"), dict) else {}
    p = plan(procs, mode, ncpu if ncpu is not None else (os.cpu_count() or 0), narrowed)
    errors: dict[int, str] = {}
    actions = []
    for pid, prio in sorted(p.set_to.items()):
        if prio != NORMAL:  # the one write this governor may make
            raise RuntimeError(f"resource_governor planned class {prio:#x} for {pid}")
        err = None if dry else setter(pid, prio)
        if err:
            errors[pid] = err
            continue
        actions.append({"pid": pid, "to": prio, "from": by[pid].prio, "why": p.why[pid]})
    pins = []
    for pid, cores in [*sorted(p.pin.items()), *sorted(p.unpin.items())]:
        if pid in p.pin and not set(cores) <= set(RESEARCH_CORES):
            raise RuntimeError(f"resource_governor planned judge cores {cores} for {pid}")
        err = None if dry else pinner(pid, cores)
        if err:
            errors[pid] = err
            p.narrowed = {k: v for k, v in p.narrowed.items() if not k.startswith(f"{pid}:")}
            continue
        pins.append({"pid": pid, "cores": list(cores), "from": list(by[pid].affinity or ()),
                     "why": "research off the judge's cores" if pid in p.pin
                     else "judge idle: own affinity back"})  # fmt: skip
    doc = {
        "at": now().isoformat(timespec="seconds"), "dry_run": dry, "mode": mode,
        "cpu_pct": round(cpu, 1), "free_ram_gb": round(free_gb, 1), "hot": hot, "cool": cool,
        "classes": p.classes, "actions": actions, "affinity": pins,
        "judge_cores": {"state": p.reserve, "judge": list(JUDGE_CORES),
                        "research": list(RESEARCH_CORES), "narrowed": len(p.narrowed)},
        "research_by_class": p.research_by_class, "research_at_normal_or_above": p.research_high,
        "errors": {str(k): v for k, v in errors.items()},
        "report_only": {
            "overload": mode == "THROTTLE",
            "research_over_bound": max(0, p.classes["RESEARCH"] - MAX_RESEARCH_PROCS),
            "would_yield": p.would_yield,
            "missed_growth": f"{p.would_yield} research process(es) a throttle would lower; "
            "NOT applied (never-throttle-mining)",
        },
        "limits": {"overload_pct": OVERLOAD_PCT, "recover_pct": RECOVER_PCT,
                   "min_free_ram_gb": MIN_FREE_RAM_GB, "max_research_procs": MAX_RESEARCH_PROCS},
    }  # fmt: skip
    if not dry:
        _save(state_path, {"mode": mode, "hot": hot, "cool": cool, "narrowed": p.narrowed})
    _save(report_path, doc)
    return doc


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one tick (the scheduled task runs this)")
    ap.add_argument("--dry-run", action="store_true", help="measure and plan, change nothing")
    a = ap.parse_args(list(argv) if argv is not None else None)
    if sys.platform != "win32" and not a.dry_run:
        print("resource_governor: acts only on the Windows box; use --dry-run elsewhere")
        return 0
    doc = tick(dry=a.dry_run)
    print(json.dumps({k: doc[k] for k in ("mode", "cpu_pct", "free_ram_gb", "classes")}),
          f"actions={len(doc['actions'])} errors={len(doc['errors'])}")  # fmt: skip
    return 1 if doc["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
