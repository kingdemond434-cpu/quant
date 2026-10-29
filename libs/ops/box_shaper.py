"""THE BOX BOTTLENECK HUNTER: measure every process, report the top consumers, shape CPU by rule.

WHY THIS EXISTS (2026-10-29). The trading box's CPU rules lived in a hand-installed SYSTEM task
(`Quant-CpuShaper`, C:\\ProgramData\\QuantBox\\cpu_shaper.ps1, every 2 min) that no release
carries and no test reads. Measured that day with the box at 100%: `pf_allocator --mode heavy`
at 3162% (31 cores' worth of an 18-core box over a 10 s window), MsMpEng 232%, the judge's shards
at 30-40% each, and the memecoin bot uncapped until the owner pasted a cap by hand. Every change
of rule was a human paste.

WHAT IT IS. One pass, called by `MT5-StallWatch` (desks/mt5/scripts/stall_watch.ps1, SYSTEM,
every 10 min -- an existing task that runs adopted code, so a committed change here or in
`desks/mt5/ops/CPU_SHAPE.json` reaches the box on the next hourly adoption with no installer
re-run). It takes no arguments and reads no queue: what it may do is this file plus that one.

  1. MEASURE (psutil; never CIM, which has hung on this box): per-process CPU% over a short
     window, threads, RSS, IO bytes; box CPU%, RAM and C: free. Each process is tagged
     money / judge / memecoin / protected / system / mining / other.
  2. PLAN, inside fixed rails (`plan`, pure, tested):
       * no class above AboveNormal, ever;
       * the Adopt-And-Seal / Adopt-Release tree (group `adopt`, by command line and parent
         chain) is raised to AboveNormal while it runs and never narrowed;
       * money path, judge and protected writers are only RAISED -- never an affinity, never a
         lower class;
       * mining never below BelowNormal; an affinity cap on mining only while the judge is
         starved and never narrower than `mining_floor_cores`;
       * memecoin's mask is narrowed to its `max_box_share` of the box;
       * any other single process above `share_cap.threshold_cores` for `sustained_runs`
         consecutive passes is pinned to `share_cap.mask` -- only while the judge is starved
         and never under `mining_floor_cores`, exactly as for mining -- and once the judge is
         no longer starved every process it pinned is widened back to the side mask
         (`release_share_cap`; the pins are carried pass to pass in `share_cap_moved`);
       * nothing is deleted, and nothing is killed EXCEPT an exact duplicate (same exe, same
         command line, unrelated launchers) of a run-once loop that `dedupe.allow` names, seen on
         two consecutive passes; the oldest instance is always kept (`plan_dedupe`). The allow
         list is empty by default, so on a fresh rules file duplicates are only reported.
  2b. RESERVE JUDGE CORES (`plan_reserve`, owner override 2026-10-29): mining/other python
     processes always stay off `judge_reserve.base_mask` (cores 8-15); during the judge's serial
     phases (desks/mt5/reports/JUDGE_SWEEP_PHASE.json) or while it is starved they also leave
     `boost_mask`, and are widened back when the boost ends. The side left to them never holds
     fewer than `mining_floor_cores`. Money, judge, protected, memecoin and any process a rule
     already pins (pf_allocator) are never moved.
  3. APPLY (Windows only) and write desks/mt5/reports/BOX_BOTTLENECKS.json: the top consumers,
     the judge's share, memecoin's share, and every action with whether it landed.

The last stdout line is one JSON object with a `line` summary, which stall_watch.ps1 carries
into data/stall_watch.json beside its other verdicts.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import socket
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:  # psutil is optional: without it the pass reports UNMEASURED and changes nothing
    import psutil  # type: ignore[import-untyped,unused-ignore]
except ImportError:  # pragma: no cover - exercised only where psutil is absent
    psutil = None  # type: ignore[assignment,unused-ignore]

REPO = Path(__file__).resolve().parents[2]
RULES_PATH = REPO / "desks" / "mt5" / "ops" / "CPU_SHAPE.json"
REPORT_PATH = REPO / "desks" / "mt5" / "reports" / "BOX_BOTTLENECKS.json"
PHASE_PATH = REPO / "desks" / "mt5" / "reports" / "JUDGE_SWEEP_PHASE.json"
ADOPT_HEARTBEAT_PATH = REPO / "desks" / "mt5" / "reports" / "ADOPTION_HEARTBEAT.json"

#: Windows priority classes, lowest to highest. HIGH and REALTIME are named only so a rule that
#: asks for them is REFUSED by name rather than silently misread.
PRIORITY_ORDER: tuple[str, ...] = ("Idle", "BelowNormal", "Normal", "AboveNormal", "High",
                                   "RealTime")
_PSUTIL_CLASS = {
    "Idle": "IDLE_PRIORITY_CLASS", "BelowNormal": "BELOW_NORMAL_PRIORITY_CLASS",
    "Normal": "NORMAL_PRIORITY_CLASS", "AboveNormal": "ABOVE_NORMAL_PRIORITY_CLASS",
    "High": "HIGH_PRIORITY_CLASS", "RealTime": "REALTIME_PRIORITY_CLASS",
}
#: Groups that may only ever be raised: no affinity, no lower class. "adopt" is the
#: Adopt-And-Seal / Adopt-Release tree (the release path rides with the money path): never put on
#: the side mask, never share-capped, and widened back to every core if an earlier pass narrowed it.
RAISE_ONLY = frozenset({"money", "judge", "protected", "adopt"})
#: Groups no rule or cap touches at all.
UNTOUCHED = frozenset({"system"})
#: The only groups an exact duplicate may be stopped in. Money, judge, memecoin, protected
#: writers (tick recorders, ledgers, certificates, tape) and system processes never are.
DEDUPE_GROUPS = frozenset({"mining", "other"})
#: Pool workers share one command line by design; they are never duplicates.
_WORKER_MARKERS: tuple[str, ...] = ("multiprocessing", "spawn_main", "joblib", "loky",
                                    "shard_worker")
TOP_N = 25
#: Changes are applied on the Windows box only; read once, so a test can stand in for it.
IS_WINDOWS = os.name == "nt"
#: login/account/server cover terminal64's /login: /server: switches and their kin.
_SECRET = re.compile(
    r"(?i)(key|token|secret|passw\w*|auth\w*|login|account|server)([=:\s]+)\S+")


@dataclass
class Proc:
    """One measured process (injectable for tests)."""
    pid: int
    name: str
    ppid: int = 0
    exe: str = ""
    cmdline: str = ""
    create_time: float = 0.0
    cpu_pct: float = 0.0          # percent of ONE core over the window (Task Manager x cores)
    threads: int = 0
    rss_mb: float = 0.0
    io_mb: float = 0.0
    priority: str | None = None   # one of PRIORITY_ORDER, None when unreadable
    affinity: list[int] | None = None
    group: str = "other"

    @property
    def key(self) -> str:
        return f"{self.pid}:{int(self.create_time)}"

    @property
    def haystack(self) -> str:
        return f"{self.exe} {self.cmdline}".lower()


@dataclass
class Action:
    pid: int
    name: str
    group: str
    rule: str
    kind: str                     # "priority" | "affinity"
    before: Any
    after: Any
    applied: bool = False
    error: str | None = None


@dataclass
class Plan:
    actions: list[Action] = field(default_factory=list)
    refused: list[dict[str, Any]] = field(default_factory=list)
    heavy: list[str] = field(default_factory=list)


# ------------------------------------------------------------------------------------ rules
def mask_to_cpus(mask: str | int, n_cpu: int) -> list[int]:
    """Bit positions of an affinity mask, clipped to the CPUs this box has."""
    value = int(mask, 16) if isinstance(mask, str) else int(mask)
    return [i for i in range(n_cpu) if value >> i & 1]


def cpus_to_mask(cpus: Sequence[int]) -> str:
    return hex(sum(1 << c for c in cpus))


def narrow_to_share(cpus: Sequence[int], share: float, n_cpu: int) -> list[int]:
    """Keep the HIGHEST cores of `cpus` so the set holds at most `share` of the box (min 1)."""
    k = max(1, int(share * n_cpu + 1e-9))
    return sorted(cpus)[-k:] if len(cpus) > k else list(cpus)


def load_rules(path: Path = RULES_PATH) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    validate_rules(data)
    return data


def validate_rules(data: Mapping[str, Any]) -> None:
    """Refuse a rules file that asks for anything outside the rails, before any process is read."""
    ceiling = data.get("priority_ceiling", "AboveNormal")
    if ceiling not in PRIORITY_ORDER or PRIORITY_ORDER.index(ceiling) > PRIORITY_ORDER.index(
            "AboveNormal"):
        raise ValueError(f"priority_ceiling {ceiling!r} is above AboveNormal")
    for rule in data.get("rules", []):
        name = rule.get("name")
        if not name or not (rule.get("match") or rule.get("group")):
            raise ValueError(f"rule without name and match/group: {rule!r}")
        if rule.get("group") in RAISE_ONLY and "affinity" in rule:
            raise ValueError(f"rule {name}: the {rule['group']} group is never affinity-capped")
        prio = rule.get("priority")
        if prio is not None and (prio not in PRIORITY_ORDER or
                                 PRIORITY_ORDER.index(prio) > PRIORITY_ORDER.index(ceiling)):
            raise ValueError(f"rule {name}: priority {prio!r} is above {ceiling}")
        if "affinity" in rule and int(rule["affinity"], 16) <= 0:
            raise ValueError(f"rule {name}: empty affinity mask")
        share = rule.get("max_box_share")
        if share is not None and not 0 < float(share) <= 1:
            raise ValueError(f"rule {name}: max_box_share {share!r} outside (0, 1]")
    for pattern in (data.get("dedupe") or {}).get("allow", []):
        if not isinstance(pattern, str) or len(pattern.strip()) < 6:
            raise ValueError(f"dedupe.allow entry {pattern!r} is too broad (6+ characters)")
    reserve = data.get("judge_reserve") or {}
    if reserve:
        base = int(reserve["base_mask"], 16)
        boost = int(reserve["boost_mask"], 16)
        if base <= 0 or base & ~boost:
            raise ValueError("judge_reserve.boost_mask must contain base_mask")
        if not reserve.get("serial_phases"):
            raise ValueError("judge_reserve.serial_phases is empty")
    cap = data.get("share_cap") or {}
    if cap:
        cap_cores = bin(int(cap["mask"], 16)).count("1")
        if cap_cores < int(data.get("mining_floor_cores", 1)):
            raise ValueError("share_cap.mask is narrower than mining_floor_cores")
        if float(cap["threshold_cores"]) <= 0 or int(cap["sustained_runs"]) not in (1, 2):
            raise ValueError("share_cap needs threshold_cores > 0 and sustained_runs of 1 or 2"
                             " (the previous pass is the only history kept)")


# ------------------------------------------------------------------------------------ groups
def classify(procs: Sequence[Proc], groups: Mapping[str, Sequence[str]]) -> None:
    """Tag each process; the adopt and judge trees are whole. Precedence: money first, always."""
    def hit(p: Proc, kind: str) -> bool:
        return any(s.lower() in p.haystack for s in groups.get(kind, ()))

    children: dict[int, list[Proc]] = {}
    for p in procs:
        children.setdefault(p.ppid, []).append(p)

    def tree(kind: str) -> set[int]:
        out: set[int] = set()
        stack = [p.pid for p in procs if hit(p, kind)]
        while stack:
            cur = stack.pop()
            if cur in out:
                continue
            out.add(cur)
            stack.extend(c.pid for c in children.get(cur, ()) if c.pid != cur)
        return out

    # THE RELEASE PATH RIDES WITH THE MONEY PATH (2026-10-29): the first automatic Adopt-And-Seal
    # run was measured with its python child on ~13% of a core, a 2.5-minute step past 25. Its
    # powershell and every py/python/git below it are `adopt` by parent chain, not by name.
    adopt_tree = tree("adopt")
    judge_tree = tree("judge")
    system = {s.lower() for s in groups.get("system_names", ())}
    for p in procs:
        if hit(p, "money"):
            p.group = "money"
        elif p.pid in adopt_tree:
            p.group = "adopt"
        elif p.pid in judge_tree:
            p.group = "judge"
        elif hit(p, "memecoin"):
            p.group = "memecoin"
        elif hit(p, "protected"):
            p.group = "protected"
        elif p.name.lower() in system or p.pid in (0, 4):
            p.group = "system"
        elif hit(p, "mining"):
            p.group = "mining"
        else:
            p.group = "other"


def summarize(procs: Sequence[Proc], n_cpu: int, box_cpu_pct: float | None,
              starved_cfg: Mapping[str, Any]) -> dict[str, Any]:
    busy = sum(p.cpu_pct for p in procs) or 0.0
    capacity = 100.0 * max(1, n_cpu)
    by_group: dict[str, dict[str, Any]] = {}
    for p in procs:
        g = by_group.setdefault(p.group, {"n": 0, "cpu_pct": 0.0, "rss_mb": 0.0})
        g["n"] += 1
        g["cpu_pct"] += p.cpu_pct
        g["rss_mb"] += p.rss_mb
    for g in by_group.values():
        g["cpu_pct"] = round(g["cpu_pct"], 1)
        g["rss_mb"] = round(g["rss_mb"], 1)
        g["share_of_box"] = round(g["cpu_pct"] / capacity, 4)
    judge_pct = by_group.get("judge", {}).get("cpu_pct", 0.0)
    share_busy = (judge_pct / busy) if busy > 0 else None
    starved = bool(
        box_cpu_pct is not None and share_busy is not None
        and box_cpu_pct >= float(starved_cfg.get("box_cpu_pct_at_least", 90))
        and share_busy < float(starved_cfg.get("judge_share_of_busy_below", 0.5))
        and by_group.get("judge", {}).get("n", 0) > 0)
    return {
        "busy_cpu_pct": round(busy, 1),
        "by_group": by_group,
        "judge": {"cpu_pct": judge_pct, "share_of_box": round(judge_pct / capacity, 4),
                  "share_of_busy": None if share_busy is None else round(share_busy, 4),
                  "starved": starved},
        "memecoin": {"cpu_pct": by_group.get("memecoin", {}).get("cpu_pct", 0.0),
                     "share_of_box": by_group.get("memecoin", {}).get("share_of_box", 0.0)},
    }


# ------------------------------------------------------------------------------------ plan
def _rank(prio: str | None) -> int:
    return PRIORITY_ORDER.index(prio) if prio in PRIORITY_ORDER else -1


def plan(procs: Sequence[Proc], rules: Mapping[str, Any], n_cpu: int, *, judge_starved: bool,
         previous_heavy: Sequence[str] = ()) -> Plan:
    """Every change this pass would make, and every one the rails refused. Pure."""
    out = Plan()
    floor_cores = int(rules.get("mining_floor_cores", 1))
    ruled_affinity: set[int] = set()
    for p in procs:
        if p.group in UNTOUCHED:
            continue
        for rule in rules.get("rules", []):
            if rule.get("group"):
                if p.group != rule["group"]:
                    continue
            elif str(rule["match"]).lower() not in p.haystack:
                continue
            prio = rule.get("priority")
            if prio and prio != p.priority:
                lowering = _rank(prio) < _rank(p.priority)
                if p.group in RAISE_ONLY and p.priority is None:
                    out.refused.append({"pid": p.pid, "name": p.name, "group": p.group,
                                        "rule": rule["name"],
                                        "why": f"{p.group} is only ever raised; class unreadable"})
                elif p.group in RAISE_ONLY and lowering:
                    pass  # already above the rule's class: a raise-only group is never lowered
                elif p.group == "mining" and _rank(prio) < _rank("BelowNormal"):
                    out.refused.append({"pid": p.pid, "name": p.name, "group": p.group,
                                        "rule": rule["name"],
                                        "why": "mining never below BelowNormal"})
                else:
                    out.actions.append(Action(p.pid, p.name, p.group, rule["name"], "priority",
                                              p.priority, prio))
            if "affinity" in rule:
                ruled_affinity.add(p.pid)
                cpus = mask_to_cpus(rule["affinity"], n_cpu)
                if rule.get("max_box_share") is not None:
                    cpus = narrow_to_share(cpus, float(rule["max_box_share"]), n_cpu)
                why = _affinity_refusal(p, cpus, judge_starved, floor_cores)
                if why:
                    out.refused.append({"pid": p.pid, "name": p.name, "group": p.group,
                                        "rule": rule["name"], "why": why})
                elif p.affinity is None or sorted(p.affinity) != cpus:
                    out.actions.append(Action(p.pid, p.name, p.group, rule["name"], "affinity",
                                              _mask(p.affinity), cpus_to_mask(cpus)))
    cap = rules.get("share_cap") or {}
    if cap:
        limit = 100.0 * float(cap["threshold_cores"])
        need = int(cap["sustained_runs"])
        cap_cpus = mask_to_cpus(cap["mask"], n_cpu)
        seen = set(previous_heavy)
        for p in procs:
            if p.cpu_pct <= limit or p.group not in ("mining", "other"):
                continue
            out.heavy.append(p.key)
            if p.pid in ruled_affinity or (need > 1 and p.key not in seen):
                continue
            # AN UNLISTED PROCESS IS NEVER THROTTLED ON ITS OWN SIZE ALONE: "other" waits for the
            # same starved-judge condition and the same core floor as mining. Only a committed
            # rule above may pin a process the judge is not losing CPU to.
            why = _affinity_refusal(p, cap_cpus, judge_starved, floor_cores)
            if why is None and not judge_starved:
                why = "share_cap acts only while the judge is starved"
            if why is None and len(cap_cpus) < floor_cores:
                why = f"mask below the floor of {floor_cores} cores"
            if why:
                out.refused.append({"pid": p.pid, "name": p.name, "group": p.group,
                                    "rule": "share_cap", "why": why})
            elif cap_cpus and (p.affinity is None or len(p.affinity) > len(cap_cpus)):
                out.actions.append(Action(p.pid, p.name, p.group, "share_cap", "affinity",
                                          _mask(p.affinity), cpus_to_mask(cap_cpus)))
    return out


def memecoin_cap_holds(procs: Sequence[Proc], rules: Mapping[str, Any], the_plan: Plan,
                       share_of_box: float) -> tuple[bool, str]:
    """Does the report POSITIVELY show the memecoin cap holding? (Gate for retiring hand tasks.)

    True only when a memecoin process is live; every memecoin rule action was applied without
    error (no action at all means each process already sat on the narrowed mask and class --
    `plan` emits one for any mismatch); no memecoin rule was refused; and the measured share of
    the box is within the rule's `max_box_share`. Anything else keeps the hand tasks enabled.
    """
    mrules = [r for r in rules.get("rules", []) if str(r.get("match", "")).lower() == "memecoin"]
    if not mrules:
        return False, "no memecoin rule in CPU_SHAPE.json"
    names = {r["name"] for r in mrules}
    if not any(p.group == "memecoin" for p in procs):
        return False, "no memecoin process live: the cap is unproven this pass"
    bad = [a for a in the_plan.actions if a.rule in names and (not a.applied or a.error)]
    if bad:
        return False, f"{len(bad)} memecoin action(s) did not land: {bad[0].error}"
    if any(r.get("rule") in names for r in the_plan.refused):
        return False, "a memecoin rule was refused"
    share = min(float(r.get("max_box_share", 1.0)) for r in mrules)
    if share_of_box > share:
        return False, f"memecoin measured at {share_of_box:.1%} of the box, above {share:.0%}"
    return True, f"memecoin cap holds at {share_of_box:.1%} of the box"


def judge_phase(doc: Mapping[str, Any] | None, alive: Any) -> tuple[str | None, int | None]:
    """The judge's sweep phase, believed only while the pid that wrote it is alive."""
    if not isinstance(doc, Mapping):
        return None, None
    phase = doc.get("phase")
    pid = doc.get("pid")
    try:
        pid_i = int(pid) if pid is not None else None
    except (TypeError, ValueError):
        pid_i = None
    if not isinstance(phase, str) or pid_i is None or not alive(pid_i):
        return None, pid_i
    return phase, pid_i


def read_doc(path: Path) -> tuple[dict[str, Any] | None, str]:
    """(document, "ok" | "absent" | "unreadable"). Absent and unreadable are kept apart."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return None, "absent"
    except OSError:
        return None, "unreadable"
    try:
        doc = json.loads(text)
    except ValueError:
        return None, "unreadable"
    return (doc, "ok") if isinstance(doc, dict) else (None, "unreadable")


def phase_status(doc: Mapping[str, Any] | None, file_state: str, alive: Any,
                 wait_phases: Sequence[str]) -> tuple[str | None, int | None, str]:
    """(phase, pid, status) of the judge's sweep. Pure.

    status is one of:
      absent / unreadable / no_pid -- WE DO NOT KNOW whether the judge has work: an unknown,
                                      counted as an unmeasured strike by `health`;
      dead / done                  -- truly no runnable work (the writer is gone, or it says
                                      it is in a wait phase);
      live                         -- runnable work.
    """
    if file_state != "ok" or not isinstance(doc, Mapping):
        return None, None, file_state if file_state != "ok" else "unreadable"
    phase, pid = judge_phase(doc, alive)
    if pid is None:
        return None, None, "no_pid"
    if phase is None:
        raw = doc.get("phase")
        return None, pid, ("dead" if isinstance(raw, str) else "unreadable")
    if phase in set(wait_phases):
        return phase, pid, "done"
    return phase, pid, "live"


#: phase_status values that are a KNOWN answer (anything else is an unknown).
PHASE_KNOWN = frozenset({"dead", "done", "live"})


def adopt_overdue(doc: Mapping[str, Any] | None, now: float, limit_s: float,
                  alive: Any = None) -> str | None:
    """Why an Adopt-And-Seal run is overdue, or None. Pure.

    Adopt-And-Seal stamps ADOPTION_HEARTBEAT.json `started_at` (finished_at null) when it starts
    and `finished_at` + `stage` in `Done`, which every exit -- every seal and every refusal --
    goes through. A heartbeat started more than `limit_s` ago with no finished_at is a run with no
    seal or refusal line: RED. (A killed run reads the same until the next run restamps it, and
    the why says whether its pid still lives.)
    """
    if not isinstance(doc, Mapping) or doc.get("finished_at"):
        return None
    started = _parse_ts(doc.get("started_at"))
    if started is None:
        return None
    age = now - started
    if age <= limit_s:
        return None
    pid = doc.get("pid")
    state = ""
    if alive is not None and isinstance(pid, int):
        state = " (pid alive)" if alive(pid) else " (pid gone: killed?)"
    return (f"Adopt-And-Seal pid {pid}{state} started {round(age / 60)} min ago with no seal or "
            f"refusal line (stage {doc.get('stage')!r}; limit {round(limit_s / 60)} min)")


def _parse_ts(value: Any) -> float | None:
    """ISO-8601 to epoch seconds. PowerShell's 'o' format has 7 fractional digits: cut to 6."""
    if not isinstance(value, str) or not value.strip():
        return None
    v = re.sub(r"(\.\d{6})\d+", r"\1", value.strip()).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.timestamp()


def release_share_cap(procs: Sequence[Proc], previous: Mapping[str, str], *, judge_starved: bool,
                      side_now: Sequence[int], side_base: Sequence[int], n_cpu: int,
                      skip_pids: set[int]) -> tuple[list[Action], dict[str, str]]:
    """Widen back what share_cap pinned once the judge is no longer starved. Pure.

    `previous` is last pass's `share_cap_moved` (process key -> mask set). While the judge is
    starved a pin stands. Once it is not, a pinned mining/other process still narrower than this
    pass's side mask is widened to it; the record is kept while the process is narrower than the
    BASE side (a boost still on), so the widening finishes when the boost ends. A process now in a
    raise-only group (e.g. it turned out to be the adopt tree) is widened to every core.
    """
    full = set(range(n_cpu))
    now_mask = cpus_to_mask(side_now)
    actions: list[Action] = []
    keep: dict[str, str] = {}
    for p in procs:
        if p.key not in previous or p.pid in skip_pids:
            continue
        cur = set(p.affinity) if p.affinity is not None else full
        if p.group in RAISE_ONLY:
            if cur != full:
                actions.append(Action(p.pid, p.name, p.group, "share_cap_release", "affinity",
                                      _mask(p.affinity), cpus_to_mask(sorted(full))))
            continue
        if p.group not in ("mining", "other"):
            continue
        if judge_starved:
            keep[p.key] = previous[p.key]
            continue
        after = cur
        if side_now and cur < set(side_now):
            actions.append(Action(p.pid, p.name, p.group, "share_cap_release", "affinity",
                                  _mask(p.affinity), now_mask))
            after = cur | set(side_now)
        if after < set(side_base):
            keep[p.key] = now_mask
    return actions, keep


def reserve_masks(cfg: Mapping[str, Any], n_cpu: int, floor_cores: int,
                  boost: bool) -> tuple[list[int], list[int], str | None]:
    """(reserve cores, side cores, why-the-boost-fell-back). The side never drops under the floor.

    With the boost on, the reserve is `boost_mask` only if what it leaves holds `floor_cores`;
    otherwise the base reserve stands and the reason is returned. With the BASE alone under the
    floor (a smaller box) nothing is reserved at all.
    """
    full = list(range(n_cpu))
    base = mask_to_cpus(cfg["base_mask"], n_cpu)
    wide = mask_to_cpus(cfg["boost_mask"], n_cpu)
    note = None
    reserve = base
    if boost:
        if n_cpu - len(wide) >= floor_cores:
            reserve = wide
        else:
            note = (f"boost would leave {n_cpu - len(wide)} cores, under the floor of "
                    f"{floor_cores}; base reserve kept")
    if n_cpu - len(reserve) < floor_cores:
        return [], full, f"base reserve would leave under {floor_cores} cores; nothing reserved"
    return reserve, [c for c in full if c not in reserve], note


def plan_reserve(procs: Sequence[Proc], cfg: Mapping[str, Any], n_cpu: int, *, boost: bool,
                 floor_cores: int, skip_pids: set[int],
                 previous_moved: Mapping[str, str]) -> tuple[list[Action], dict[str, str],
                                                              dict[str, Any]]:
    """Keep mining/other python off the judge's cores. Pure.

    A process with any core inside the reserve is moved to the side mask. A process the
    reservation itself narrowed earlier (`previous_moved`, key -> mask it set) and that now sits
    on a narrower side than this pass allows (the boost ended) is widened back to the side mask.
    Anything else -- including a process already inside the side mask by another rule -- is left.
    """
    reserve, side, note = reserve_masks(cfg, n_cpu, floor_cores, boost)
    exempt = [str(e).lower() for e in cfg.get("exempt", [])]
    side_mask = cpus_to_mask(side)
    moved: dict[str, str] = {}
    actions: list[Action] = []
    full = set(range(n_cpu))
    for p in procs:
        if p.group in RAISE_ONLY and p.key in previous_moved and p.pid not in skip_pids:
            # narrowed while it read as mining/other; it is raise-only now: every core back
            if p.affinity is not None and set(p.affinity) != full:
                actions.append(Action(p.pid, p.name, p.group, "judge_reserve", "affinity",
                                      _mask(p.affinity), cpus_to_mask(sorted(full))))
            continue
        if (p.group not in ("mining", "other") or "python" not in p.name.lower()
                or p.pid in skip_pids or any(e in p.haystack for e in exempt)):
            continue
        cur = set(p.affinity) if p.affinity is not None else set(range(n_cpu))
        if reserve and cur & set(reserve):
            actions.append(Action(p.pid, p.name, p.group, "judge_reserve", "affinity",
                                  _mask(p.affinity), side_mask))
            moved[p.key] = side_mask
        elif p.key in previous_moved:
            if cur < set(side):
                actions.append(Action(p.pid, p.name, p.group, "judge_reserve", "affinity",
                                      _mask(p.affinity), side_mask))
            moved[p.key] = side_mask
    meta = {"mode": "boost" if boost and len(reserve) > len(mask_to_cpus(cfg["base_mask"], n_cpu))
            else ("base" if reserve else "off"),
            "reserve_mask": cpus_to_mask(reserve) if reserve else None, "side_mask": side_mask,
            "side_cores": len(side), "note": note}
    return actions, moved, meta


def reserve_holds(actions: Sequence[Action], meta: Mapping[str, Any]) -> tuple[bool, str]:
    """The reservation is verified this pass: a reserve is in force and every move landed."""
    if not meta.get("reserve_mask"):
        return False, f"no judge reserve in force ({meta.get('note') or 'not configured'})"
    bad = [a for a in actions if not a.applied or a.error]
    if bad:
        return False, f"{len(bad)} judge-reserve move(s) did not land: {bad[0].error}"
    return True, f"judge reserve {meta['reserve_mask']} holds ({meta['mode']})"


def log_switch(history: Sequence[Mapping[str, Any]], *, at: str, mode: str,
               phase: str | None, starved: bool, judge_share: float | None,
               mining_share: float | None = None,
               side_cores: int | None = None) -> list[dict[str, Any]]:
    """Append a mode switch with the judge's and mining's shares before it; fill the previous
    switch's after on the next pass. `mining_donation` is what mining gave up across the
    switch (its share before minus after, of the whole box); `side_cores` is how many cores the
    new mode leaves mining/other."""
    out = [dict(h) for h in history][-19:]
    if out and out[-1].get("judge_share_after") is None and out[-1].get("mode") != "init":
        last = out[-1]
        last["judge_share_after"] = judge_share
        last["mining_share_after"] = mining_share
        before = last.get("mining_share_before")
        if isinstance(before, (int, float)) and mining_share is not None:
            last["mining_donation"] = round(float(before) - mining_share, 4)
    last_mode = out[-1]["mode"] if out else None
    if mode != last_mode:
        out.append({"at": at, "from": last_mode, "mode": mode, "phase": phase,
                    "starved": starved, "side_cores": side_cores,
                    "judge_share_before": judge_share, "judge_share_after": None,
                    "mining_share_before": mining_share, "mining_share_after": None,
                    "mining_donation": None})
    return out


#: Consecutive failing passes tolerated before the hunter goes RED (owner rule 23).
RED_AFTER_RUNS = 2


def health(previous: Mapping[str, Any] | None, *, measured: bool, runnable: bool,
           judge_share: float | None, min_share: float, phase_known: bool = True,
           phase_status: str | None = None, adopt_why: str | None = None) -> dict[str, Any]:
    """THE HUNTER'S OWN RED CHECK (owner rule 23, 2026-10-29). Pure.

    RED when any of:
      * the judge's share of the box stayed below `min_share` for MORE than RED_AFTER_RUNS
        consecutive passes while it had runnable work (a live sweep not in a wait phase);
      * this hunter's own measurement has been UNMEASURED for more than RED_AFTER_RUNS passes;
      * the judge's phase has been UNKNOWN (JUDGE_SWEEP_PHASE.json absent, unreadable or with no
        pid) for more than RED_AFTER_RUNS passes -- an unknown is never read as "no work";
      * `adopt_why` is set: an Adopt-And-Seal run is past its limit with no seal or refusal
        line (immediately: the release path rides with the money path).
    One or two strikes read WATCH; a clean pass resets its counter. A pass with an unknown phase
    neither adds to nor resets the judge-low counter.
    """
    prev = previous or {}
    low = int(prev.get("judge_low_strikes") or 0)
    unmeasured = int(prev.get("unmeasured_strikes") or 0)
    unknown = int(prev.get("phase_unknown_strikes") or 0)
    if not measured:
        unmeasured += 1
    else:
        unmeasured = 0
        if not phase_known:
            unknown += 1
        else:
            unknown = 0
            starved = runnable and judge_share is not None and judge_share < min_share
            low = low + 1 if starved else 0
    out: dict[str, Any] = {"judge_low_strikes": low, "unmeasured_strikes": unmeasured,
                           "phase_unknown_strikes": unknown, "phase_status": phase_status,
                           "judge_min_share": min_share, "red_after_runs": RED_AFTER_RUNS,
                           "adopt_overdue": adopt_why}
    if adopt_why:
        out.update(verdict="RED", why=f"release path stalled: {adopt_why}")
    elif unmeasured > RED_AFTER_RUNS:
        out.update(verdict="RED", why=f"the hunter has been UNMEASURED for {unmeasured} "
                   "consecutive passes: nobody is watching the box's CPU")
    elif unknown > RED_AFTER_RUNS:
        out.update(verdict="RED", why=f"the judge's phase has been unknown ({phase_status}) for "
                   f"{unknown} consecutive passes: nobody can say whether it is starved")
    elif low > RED_AFTER_RUNS:
        out.update(verdict="RED", why=f"judge below {min_share:.0%} of the box for {low} "
                   "consecutive passes with runnable work")
    elif not measured:
        out.update(verdict="UNMEASURED", why=f"unmeasured pass {unmeasured} of "
                   f"{RED_AFTER_RUNS} tolerated")
    elif unknown:
        out.update(verdict="UNMEASURED", why=f"judge phase unknown ({phase_status}), pass "
                   f"{unknown} of {RED_AFTER_RUNS} tolerated")
    elif low:
        out.update(verdict="WATCH", why=f"judge below {min_share:.0%} of the box, pass {low} of "
                   f"{RED_AFTER_RUNS} tolerated")
    elif runnable:
        share = "unmeasured" if judge_share is None else f"{judge_share:.0%}"
        out.update(verdict="GREEN", why=f"at/above floor: judge {share} of the box with "
                   f"runnable work, floor {min_share:.0%}")
    else:
        out.update(verdict="GREEN", why=f"no runnable work: judge phase {phase_status or 'n/a'} "
                   "(writer gone or in a wait phase)")
    return out


def judge_runnable(phase: str | None, wait_phases: Sequence[str]) -> bool:
    """The judge has runnable work: a live sweep in a phase that is not a pure wait."""
    return phase is not None and phase not in set(wait_phases)


def track_wall(procs: Sequence[Proc], match: str, previous: Mapping[str, Any] | None,
               now: float) -> dict[str, Any]:
    """Wall time of each run of a tracked process, carried pass to pass. Pure.

    A run still live reports `wall_s` so far; a run seen last pass and gone now moves to
    `finished` with `wall_s_at_least` (its last reading: the true end is up to one pass later).
    """
    prev = previous or {}
    running = [{"key": p.key, "started_at": datetime.fromtimestamp(p.create_time, UTC)
                .isoformat(timespec="seconds"), "wall_s": round(max(0.0, now - p.create_time)),
                "cores": None if p.affinity is None else len(p.affinity)}
               for p in procs if match.lower() in p.haystack]
    live = {r["key"] for r in running}
    finished = list(prev.get("finished") or [])
    for r in prev.get("running") or []:
        if isinstance(r, dict) and r.get("key") not in live:
            finished.append({"key": r.get("key"), "started_at": r.get("started_at"),
                             "wall_s_at_least": r.get("wall_s"), "cores": r.get("cores")})
    return {"running": running, "finished": finished[-10:]}


def plan_dedupe(procs: Sequence[Proc], cfg: Mapping[str, Any],
                previous_duplicates: Sequence[str] = (),
                ) -> tuple[list[Action], list[dict[str, Any]]]:
    """Exact duplicates of a run-once loop: report all, stop only the allow-listed. Pure.

    A duplicate is a second live process with the SAME exe and the SAME full command line whose
    launcher is unrelated to the first's: neither is the other's parent and no two share a
    parent (a pool, or a launcher's own shards, share one -- and Task Scheduler's svchost parent
    is shared by two scheduled starts, which IgnoreNew serialises -- so duplicates launched
    straight by Task Scheduler are NOT REPORTED here at all). The oldest is kept. A stop is
    planned only when an allow pattern names the command line AND the same duplicate (pid and
    creation time) was already reported on the previous pass.
    """
    allow = [str(a).lower() for a in cfg.get("allow", [])]
    seen_before = set(previous_duplicates)
    buckets: dict[tuple[str, str], list[Proc]] = {}
    for p in procs:
        if p.group not in DEDUPE_GROUPS or not p.cmdline.strip():
            continue
        if any(m in p.cmdline.lower() for m in _WORKER_MARKERS):
            continue
        buckets.setdefault((p.exe.lower(), p.cmdline), []).append(p)
    stops: list[Action] = []
    report: list[dict[str, Any]] = []
    for members in buckets.values():
        if len(members) < 2:
            continue
        pids = {m.pid for m in members}
        parents = [m.ppid for m in members]
        if any(pp in pids for pp in parents) or len(set(parents)) < len(parents):
            continue
        members = sorted(members, key=lambda m: (m.create_time, m.pid))
        keeper = members[0]
        allowed = any(a in keeper.haystack for a in allow)
        for dup in members[1:]:
            report.append({"keep": keeper.key, "duplicate": dup.key, "name": dup.name,
                           "group": dup.group, "allowed": allowed, "cmd": _short_cmd(dup)})
            if allowed and dup.key in seen_before:
                stops.append(Action(dup.pid, dup.name, dup.group, "dedupe", "stop", dup.key,
                                    f"stopped; kept {keeper.key}"))
    return stops, report


def _affinity_refusal(p: Proc, cpus: Sequence[int], judge_starved: bool,
                      floor_cores: int) -> str | None:
    if not cpus:
        return "mask names no CPU on this box"
    if p.group in RAISE_ONLY:
        return f"{p.group} is never affinity-capped"
    if p.group == "mining":
        if not judge_starved:
            return "mining is capped only while the judge is starved"
        if len(cpus) < floor_cores:
            return f"mask below the mining floor of {floor_cores} cores"
    return None


def _mask(cpus: Sequence[int] | None) -> str | None:
    return None if cpus is None else cpus_to_mask(cpus)


# ------------------------------------------------------------------------------------ measure
def _priority_name(value: int) -> str | None:
    if psutil is None:
        return None
    for name, attr in _PSUTIL_CLASS.items():
        if getattr(psutil, attr, None) == value:
            return name
    return None


def measure(window_s: float) -> tuple[list[Proc], float | None]:
    """Two psutil snapshots `window_s` apart; CPU% per process and for the box."""
    if psutil is None:
        return [], None
    t0: dict[int, tuple[float, float]] = {}
    for pr in psutil.process_iter(["pid", "create_time", "cpu_times"]):
        try:
            ct = pr.info["cpu_times"]
            t0[pr.info["pid"]] = (pr.info["create_time"] or 0.0, ct.user + ct.system)
        except (psutil.Error, AttributeError, TypeError):
            continue
    psutil.cpu_percent(None)
    start = time.monotonic()
    time.sleep(max(0.5, window_s))
    elapsed = time.monotonic() - start
    box = float(psutil.cpu_percent(None))
    procs: list[Proc] = []
    attrs = ["pid", "ppid", "name", "exe", "cmdline", "create_time", "cpu_times", "num_threads",
             "memory_info", "io_counters", "nice", "cpu_affinity"]
    for pr in psutil.process_iter(attrs):
        try:
            info = pr.info
            ct = info.get("cpu_times")
            now_cpu = (ct.user + ct.system) if ct else 0.0
            base = t0.get(info["pid"])
            if base is None or base[0] != (info.get("create_time") or 0.0):
                continue  # born inside the window: no honest rate yet
            io = info.get("io_counters")
            mi = info.get("memory_info")
            nice = info.get("nice")
            readable = isinstance(nice, int) and os.name == "nt"
            procs.append(Proc(
                pid=int(info["pid"]), name=str(info.get("name") or ""),
                ppid=int(info.get("ppid") or 0), exe=str(info.get("exe") or ""),
                cmdline=" ".join(info.get("cmdline") or []),
                create_time=float(info.get("create_time") or 0.0),
                cpu_pct=max(0.0, (now_cpu - base[1]) / elapsed * 100.0),
                threads=int(info.get("num_threads") or 0),
                rss_mb=(mi.rss / 1048576.0) if mi else 0.0,
                io_mb=((io.read_bytes + io.write_bytes) / 1048576.0) if io else 0.0,
                priority=_priority_name(nice) if readable else None,
                affinity=list(info["cpu_affinity"]) if info.get("cpu_affinity") else None))
        except (psutil.Error, AttributeError, TypeError, ValueError):
            continue
    return procs, box


def apply(actions: Sequence[Action], n_cpu: int) -> None:
    """Make each planned change on Windows; record the outcome on the action itself."""
    for a in actions:
        if not IS_WINDOWS or psutil is None:
            a.error = "not applied: not the Windows box"
            continue
        try:
            pr = psutil.Process(a.pid)
            if a.kind == "stop":
                # THE PID MUST STILL BE THE PROCESS THAT WAS MEASURED: a reused pid is refused.
                if f"{a.pid}:{int(pr.create_time())}" != str(a.before):
                    a.error = "pid reused since measurement; not stopped"
                    continue
                # THE DESK'S OWN TREE KILL (libs/ops/proctree.kill_tree), so a duplicate loop's
                # pool goes with it instead of being orphaned against the commit limit.
                from libs.ops.proctree import kill_tree
                result = kill_tree(a.pid)
                if not result.get("killed") and result.get("method") != "taskkill":
                    a.error = f"kill_tree killed nothing: {result}"[:200]
                    continue
            elif a.kind == "priority":
                pr.nice(getattr(psutil, _PSUTIL_CLASS[str(a.after)]))
            else:
                pr.cpu_affinity(mask_to_cpus(str(a.after), n_cpu))
            a.applied = True
        except Exception as exc:  # a gone or protected process is a reading, not a crash
            a.error = f"{type(exc).__name__}: {exc}"[:200]


# ------------------------------------------------------------------------------------ report
def _short_cmd(p: Proc) -> str:
    text = p.cmdline or p.exe or p.name
    return _SECRET.sub(r"\1\2***", text)[:160]


def _row(p: Proc) -> dict[str, Any]:
    return {"pid": p.pid, "name": p.name, "group": p.group, "cpu_pct": round(p.cpu_pct, 1),
            "threads": p.threads, "rss_mb": round(p.rss_mb, 1), "io_mb": round(p.io_mb, 1),
            "priority": p.priority, "cores": None if p.affinity is None else len(p.affinity),
            "cmd": _short_cmd(p)}


def _previous_doc(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def _disk_free_gb() -> float | None:
    try:
        return round(shutil.disk_usage("C:\\" if os.name == "nt" else "/").free / 1024**3, 1)
    except OSError:
        return None


def run_once(*, rules_path: Path = RULES_PATH, report_path: Path = REPORT_PATH,
             phase_path: Path = PHASE_PATH,
             adopt_heartbeat_path: Path = ADOPT_HEARTBEAT_PATH) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    alive = psutil.pid_exists if psutil is not None else None
    adopt_doc, _adopt_state = read_doc(adopt_heartbeat_path)
    report: dict[str, Any] = {"schema": "box_bottlenecks/v1", "generated_at": now,
                              "host": socket.gethostname(), "rules": str(rules_path.name)}
    prev = _previous_doc(report_path)
    prev_health = prev.get("health") if isinstance(prev.get("health"), dict) else None

    def _unmeasured(verdict: str, why: str, line: str, min_share: float,
                    adopt_why: str | None = None) -> dict[str, Any]:
        h = health(prev_health, measured=False, runnable=False, judge_share=None,
                   min_share=min_share, adopt_why=adopt_why)
        report.update(verdict=verdict, why=why, health=h,
                      line=f"{line} [{h['verdict']}: {h['why']}]"[:300])
        _write(report_path, report)
        return report

    try:
        rules = load_rules(rules_path)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return _unmeasured("RULES_REFUSED", f"{type(exc).__name__}: {exc}"[:300],
                           f"CPU SHAPE RULES REFUSED: {exc}"[:200], 0.0,
                           adopt_overdue(adopt_doc, time.time(), 15 * 60.0, alive))
    min_share = float(rules.get("judge_min_share", 0.0))
    adopt_why = adopt_overdue(adopt_doc, time.time(),
                              60.0 * float(rules.get("adopt_red_after_min", 15)), alive)
    report["adopt_run"] = {"heartbeat": adopt_doc, "overdue": adopt_why}
    if psutil is None:
        return _unmeasured("UNMEASURED", "psutil is not importable on this interpreter",
                           "CPU SHAPE UNMEASURED: psutil absent; nothing shaped", min_share,
                           adopt_why)
    n_cpu = int(psutil.cpu_count() or 1)
    procs, box_pct = measure(float(rules.get("window_s", 5)))
    if not procs or box_pct is None:
        return _unmeasured("UNMEASURED", "psutil returned no process with a CPU rate",
                           "CPU SHAPE UNMEASURED: no process measured; nothing shaped", min_share,
                           adopt_why)
    wait_phases = rules.get("judge_wait_phases", ["done"])
    phase_doc, phase_file = read_doc(phase_path)
    phase, phase_pid, phase_st = phase_status(phase_doc, phase_file, psutil.pid_exists,
                                              wait_phases)
    classify(procs, rules.get("groups", {}))
    summary = summarize(procs, n_cpu, box_pct, rules.get("judge_starved", {}))
    starved_now = bool(summary["judge"]["starved"])
    the_plan = plan(procs, rules, n_cpu, judge_starved=starved_now,
                    previous_heavy=list(prev.get("heavy") or []))
    stops, duplicates = plan_dedupe(
        procs, rules.get("dedupe") or {},
        [str(d.get("duplicate")) for d in prev.get("duplicates") or []
         if isinstance(d, dict)])
    the_plan.actions.extend(stops)
    reserve_cfg = rules.get("judge_reserve") or {}
    floor_cores = int(rules.get("mining_floor_cores", 1))
    serial = bool(reserve_cfg) and phase in set(reserve_cfg.get("serial_phases", []))
    boost = bool(serial or starved_now)
    if reserve_cfg:
        side_now = reserve_masks(reserve_cfg, n_cpu, floor_cores, boost)[1]
        side_base = reserve_masks(reserve_cfg, n_cpu, floor_cores, False)[1]
    else:
        side_now = side_base = list(range(n_cpu))
    # SHARE-CAP PINS ARE RECORDED AND RELEASED (audit MF1, 2026-10-29): without this a miner
    # pinned to 0x3000F stayed on six cores after starvation ended -- `plan` refuses outside
    # starvation and `plan_reserve` never knew the shaper had narrowed it.
    prev_cap_raw = prev.get("share_cap_moved")
    prev_cap: dict[str, str] = prev_cap_raw if isinstance(prev_cap_raw, dict) else {}
    key_of = {p.pid: p.key for p in procs}
    pinned_now = {a.pid for a in the_plan.actions if a.kind == "affinity"}
    release_actions, cap_moved = release_share_cap(
        procs, prev_cap, judge_starved=starved_now, side_now=side_now, side_base=side_base,
        n_cpu=n_cpu, skip_pids=pinned_now)
    the_plan.actions.extend(release_actions)
    for a in the_plan.actions:
        if a.rule == "share_cap" and a.pid in key_of:
            cap_moved[key_of[a.pid]] = str(a.after)
    reserve_doc: dict[str, Any] = {}
    reserve_actions: list[Action] = []
    if reserve_cfg:
        prev_res_raw = prev.get("judge_reserve")
        prev_res: dict[str, Any] = prev_res_raw if isinstance(prev_res_raw, dict) else {}
        prev_moved_raw = prev_res.get("moved")
        prev_moved: dict[str, str] = prev_moved_raw if isinstance(prev_moved_raw, dict) else {}
        pinned = {a.pid for a in the_plan.actions if a.kind in ("affinity", "stop")}
        reserve_actions, moved, meta = plan_reserve(
            procs, reserve_cfg, n_cpu, boost=boost,
            floor_cores=floor_cores, skip_pids=pinned,
            previous_moved=prev_moved)
        the_plan.actions.extend(reserve_actions)
        reserve_doc = {**meta, "phase": phase, "phase_pid": phase_pid, "serial": serial,
                       "starved": summary["judge"]["starved"], "moved": moved,
                       "switches": log_switch(prev_res.get("switches") or [], at=now,
                                              mode=str(meta["mode"]), phase=phase,
                                              starved=starved_now,
                                              judge_share=summary["judge"]["share_of_box"],
                                              mining_share=summary["by_group"].get(
                                                  "mining", {}).get("share_of_box", 0.0),
                                              side_cores=int(meta["side_cores"]))}
    apply(the_plan.actions, n_cpu)
    if reserve_cfg:
        ok, why = reserve_holds(reserve_actions, reserve_doc)
        reserve_doc.update(holds=ok, holds_why=why)
    hunter_health = health(
        prev_health, measured=True, runnable=phase_st == "live",
        judge_share=float(summary["judge"]["share_of_box"]), min_share=min_share,
        phase_known=phase_st in PHASE_KNOWN, phase_status=phase_st, adopt_why=adopt_why)
    holds, holds_why = memecoin_cap_holds(procs, rules, the_plan,
                                          float(summary["memecoin"]["share_of_box"]))
    summary["memecoin"].update(cap_holds=holds, cap_why=holds_why)
    prev_wall_raw = prev.get("wall")
    prev_wall: dict[str, Any] = prev_wall_raw if isinstance(prev_wall_raw, dict) else {}
    wall = {r["name"]: track_wall(procs, str(r["match"]), prev_wall.get(r["name"]), time.time())
            for r in rules.get("rules", []) if r.get("track_wall")}
    vm = psutil.virtual_memory()
    top = sorted(procs, key=lambda p: p.cpu_pct, reverse=True)[:TOP_N]
    landed = sum(1 for a in the_plan.actions if a.applied)
    report.update(
        verdict="MEASURED", cpu_count=n_cpu, box_cpu_pct=box_pct,
        window_s=rules.get("window_s", 5), n_processes=len(procs),
        ram={"total_mb": round(vm.total / 1048576), "available_mb": round(vm.available / 1048576)},
        disk_free_gb=_disk_free_gb(), **summary,
        top=[_row(p) for p in top],
        actions=[asdict(a) for a in the_plan.actions], refused=the_plan.refused,
        heavy=the_plan.heavy, share_cap_moved=cap_moved, wall=wall, duplicates=duplicates,
        judge_reserve=reserve_doc, health=hunter_health, judge_phase=phase,
        judge_phase_status=phase_st,
        line=(f"CPU SHAPE {hunter_health['verdict']}: box {box_pct}% on {n_cpu} cores; judge "
              f"{summary['judge']['share_of_box']:.0%} of box"
              f"{' (STARVED)' if summary['judge']['starved'] else ''}; memecoin "
              f"{summary['memecoin']['share_of_box']:.0%}; top {top[0].name if top else '-'} "
              f"{round(top[0].cpu_pct) if top else 0}%; {landed}/{len(the_plan.actions)} changes "
              f"applied, {len(the_plan.refused)} refused; {len(duplicates)} exact duplicate(s), "
              f"{sum(1 for a in stops if a.applied)} stopped; judge reserve "
              f"{reserve_doc.get('mode', 'off')} {reserve_doc.get('reserve_mask') or ''}"
              f"{' phase ' + str(reserve_doc['phase']) if reserve_doc.get('phase') else ''}"))
    _write(report_path, report)
    return report


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def main() -> int:
    report = run_once()
    meme = report.get("memecoin") or {}
    res = report.get("judge_reserve") or {}
    hh = report.get("health") or {}
    print(json.dumps({"verdict": report.get("verdict"), "line": report.get("line"),
                      "health": hh.get("verdict") or "UNMEASURED",
                      "health_why": hh.get("why") or "no health computed",
                      "memecoin_cap_holds": bool(meme.get("cap_holds")),
                      "memecoin_cap_why": meme.get("cap_why") or "not measured",
                      "judge_reserve_holds": bool(res.get("holds")),
                      "judge_reserve_why": res.get("holds_why") or "not measured"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
