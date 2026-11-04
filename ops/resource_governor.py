#!/usr/bin/env python3
"""THE BOX RESOURCE GOVERNOR -- release, risk and deploy always get CPU; research takes the rest.

WHY (measured on the Contabo box, 2026-11-03 23:31Z). CPU sat at 100%. Every Quant-WorkflowGate
sweep since 22:46Z was killed by its 30-minute limit before it logged (0x41306), so no PR could
merge automatically. The 22:50Z adoption stalled for more than 40 minutes holding the git
writer lock. About 50 research pythons fanned out from one SYSTEM tree in the hour, and five
had been running for days. Scheduled tasks start BELOW_NORMAL by default, so the gate and the
adoption competed at the SAME priority as about 60 research threads on 18 cores.

zuck 2026-11-03 23:43Z: guarantee resources for risk controls, the release authority, the merge
gate and deployment; keep research running wherever capacity safely permits; bounded research
concurrency, overload-triggered throttling, no uncontrolled fan-outs, no simple timeout or
priority bump.

THE RULES (each tick, every 60 s):

  1. CLASSES, from the command line (the governor runs as SYSTEM, so it sees every one):
       LIVE      -- terminals and executors that move money. NEVER touched, at any load.
       CRITICAL  -- the gate, live-first, the release authority, adoption, promotion, seal,
                    and risk/kill-switch monitors.
       RESEARCH  -- the desk's research, mining, judging and data-derivation pythons. The judge
                    is research too, so it stays level with the miners (judge_priority.py rule).
       OTHER     -- everything else. Never touched.
  2. RESERVE. A CRITICAL process (its whole tree) runs at NORMAL: above every research process,
     and never above NORMAL, so it never outranks LIVE. Raising a process that is already
     NORMAL or higher does nothing.
  3. OVERLOAD THROTTLE. When CPU stays >= OVERLOAD_PCT for OVERLOAD_TICKS ticks, or free RAM
     falls below MIN_FREE_RAM_GB, every RESEARCH process goes to IDLE. It keeps running and
     uses every cycle no higher-priority work wants; nothing is suspended or killed. It is
     restored to its own previous class once CPU stays below RECOVER_PCT for RECOVER_TICKS
     ticks with RAM recovered.
  4. FAN-OUT BOUND. More than MAX_RESEARCH_PROCS research pythons at once: the newest beyond
     the bound go to IDLE (oldest first keep their class, so long jobs finish). They are
     restored when the count falls back under the bound.
  5. NEVER: a kill, a suspend, a LIVE process, a priority above NORMAL, or a change to a
     process this governor cannot classify.

It remembers every class it changed (STATE) and restores exactly that class. A process it
lowered that has since exited is forgotten. Every tick writes REPORT with the measurements
and every action, so a bad tick is visible, not silent.

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

OVERLOAD_PCT = 95.0
OVERLOAD_TICKS = 3
RECOVER_PCT = 80.0
RECOVER_TICKS = 3
MIN_FREE_RAM_GB = 8.0
MAX_RESEARCH_PROCS = 48

#: Money moves here. Checked FIRST: a command line matching LIVE is never anything else.
LIVE_MARKERS = (
    "terminal64.exe", "metatrader", "e8_executor", "e8-executor", "gold_oco", "ftmo_executor",
    "ftmo_follower", "fusion_executor", "mt5desk\\engine", "mt5desk/engine", "executor.py",
    "deadman", "kill_switch",
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
    "department_resident", "deepening_worker", "run_sharded_gauntlet", "warm_gauntlet_cache",
    "scout_swarm", "moat_swarm", "libs\\alpha_factory", "libs/alpha_factory", "miner",
    "multiprocessing.spawn", "spawn_main", "joblib", "loky",
)  # fmt: skip


@dataclass
class Proc:
    pid: int
    ppid: int
    cmd: str
    prio: int
    started: float  # epoch seconds


@dataclass
class Plan:
    mode: str
    set_to: dict[int, int] = field(default_factory=dict)  # pid -> new class
    restore: dict[int, int] = field(default_factory=dict)  # pid -> class to restore
    why: dict[int, str] = field(default_factory=dict)
    classes: dict[str, int] = field(default_factory=dict)


def classify(cmd: str) -> str:
    low = cmd.lower()
    if any(m in low for m in LIVE_MARKERS):
        return "LIVE"
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


def plan(procs: list[Proc], mode: str, lowered: Mapping[int, int]) -> Plan:
    """What to set, from the processes, the load mode and what was lowered before. Pure."""
    by = {p.pid: p for p in procs}
    cls = {p.pid: classify(p.cmd) for p in procs}
    live = _trees(procs, {pid for pid, c in cls.items() if c == "LIVE"})
    crit = _trees(procs, {pid for pid, c in cls.items() if c == "CRITICAL"}) - live
    research_roots = {pid for pid, c in cls.items() if c == "RESEARCH"}
    research = _trees(procs, research_roots) - live - crit
    out = Plan(mode=mode, classes={
        "LIVE": len(live), "CRITICAL": len(crit), "RESEARCH": len(research),
        "OTHER": len(procs) - len(live) - len(crit) - len(research)})  # fmt: skip
    for pid in crit:
        if RANK.get(by[pid].prio, 0) < RANK[NORMAL]:
            out.set_to[pid] = NORMAL
            out.why[pid] = "critical: reserved above research"
    if mode == "THROTTLE":
        idle = set(research)
        reason = "overload: research yields to release and risk"
    else:
        ranked = sorted(research, key=lambda pid: (by[pid].started, pid))
        idle = set(ranked[MAX_RESEARCH_PROCS:])
        reason = f"fan-out: beyond {MAX_RESEARCH_PROCS} research processes"
    for pid in idle:
        if RANK.get(by[pid].prio, 0) > RANK[IDLE]:
            out.set_to[pid] = IDLE
            out.why[pid] = reason
    for pid, was in lowered.items():
        if pid in by and pid in research and pid not in idle and by[pid].prio == IDLE:
            out.restore[pid] = was
    return out


# ------------------------------------------------------------------ actuation (box only)
def _snapshot() -> tuple[list[Proc], float, float]:
    import psutil  # type: ignore[import-untyped,unused-ignore]

    procs = []
    for p in psutil.process_iter(["pid", "ppid", "cmdline", "name", "create_time"]):
        try:
            info = p.info
            cmd = " ".join(info.get("cmdline") or []) or str(info.get("name") or "")
            procs.append(
                Proc(
                    int(info["pid"]),
                    int(info.get("ppid") or 0),
                    cmd,
                    int(p.nice()),
                    float(info.get("create_time") or 0.0),
                )
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError, TypeError):
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
) -> dict[str, Any]:
    procs, cpu, free_gb = snapshot()
    st = _load(state_path)
    hot = int(st.get("hot") or 0)
    cool = int(st.get("cool") or 0)
    overloaded = cpu >= OVERLOAD_PCT or free_gb < MIN_FREE_RAM_GB
    hot = hot + 1 if overloaded else 0
    cool = cool + 1 if (cpu < RECOVER_PCT and free_gb >= MIN_FREE_RAM_GB) else 0
    mode = next_mode(str(st.get("mode") or "NORMAL"), hot, cool)
    live_pids = {p.pid for p in procs}
    lowered = {int(k): int(v) for k, v in (st.get("lowered") or {}).items() if int(k) in live_pids}
    by = {p.pid: p for p in procs}
    p = plan(procs, mode, lowered)
    errors: dict[int, str] = {}
    actions = []
    for pid, prio in sorted(p.set_to.items()):
        err = None if dry else setter(pid, prio)
        if err:
            errors[pid] = err
            continue
        if prio == IDLE and pid not in lowered:
            lowered[pid] = by[pid].prio
        actions.append({"pid": pid, "to": prio, "from": by[pid].prio, "why": p.why[pid]})
    for pid, prio in sorted(p.restore.items()):
        err = None if dry else setter(pid, prio)
        if err:
            errors[pid] = err
            continue
        lowered.pop(pid, None)
        actions.append({"pid": pid, "to": prio, "from": IDLE, "why": "restored"})
    doc = {
        "at": now().isoformat(timespec="seconds"), "dry_run": dry, "mode": mode,
        "cpu_pct": round(cpu, 1), "free_ram_gb": round(free_gb, 1), "hot": hot, "cool": cool,
        "classes": p.classes, "lowered": len(lowered), "actions": actions,
        "errors": {str(k): v for k, v in errors.items()},
        "limits": {"overload_pct": OVERLOAD_PCT, "recover_pct": RECOVER_PCT,
                   "min_free_ram_gb": MIN_FREE_RAM_GB, "max_research_procs": MAX_RESEARCH_PROCS},
    }  # fmt: skip
    if not dry:
        _save(state_path, {"mode": mode, "hot": hot, "cool": cool,
                           "lowered": {str(k): v for k, v in lowered.items()}})  # fmt: skip
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
