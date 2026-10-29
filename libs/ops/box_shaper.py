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
         no longer starved every process it pinned is widened back to where it was -- its
         original cores, or the side mask where the judge reservation applies
         (`release_share_cap`; the pins are carried pass to pass in `share_cap_moved`, and an
         UNMEASURED or RULES_REFUSED pass carries them and `judge_reserve.moved` forward);
       * the adopt tree never above the lowest money-path class; money raises land first;
       * every throttle bills a two-sided `missed_growth` line (cost and judge gain);
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

import hashlib
import json
import os
import re
import shutil
import socket
import sys
import time
from collections.abc import Collection, Mapping, Sequence
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
#: "money_feed" is what sizes the money path's book (the allocators, audit MF1): raise-only too.
RAISE_ONLY = frozenset({"money", "money_feed", "judge", "protected", "adopt"})
#: Groups no rule or cap touches at all.
UNTOUCHED = frozenset({"system"})
#: The only groups an exact duplicate may be stopped in. Money, judge, memecoin, protected
#: writers (tick recorders, ledgers, certificates, tape) and system processes never are.
DEDUPE_GROUPS = frozenset({"mining", "other"})
#: A stop is refused when any descendant of the duplicate is in one of these groups: a tree kill
#: must never take a money, judge, protected, memecoin or adopt process down with a loop.
NEVER_IN_A_STOPPED_TREE = frozenset({"money", "money_feed", "judge", "protected", "memecoin",
                                     "adopt"})
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
    money_root: bool = False      # matched a money token by name (not by tree or stickiness)
    #: a feed script in a pinned mode (groups.money_feed_pinned: pf_allocator heavy). Its group
    #: stays the one its pin rule governs, but it is never a dedupe candidate and never inside
    #: a stopped tree (audit SF-b, 2026-10-29)
    pinned_mode: bool = False
    #: identity of a dedupe candidate (read only for those): working directory and a hash of the
    #: environment. None = unread; a duplicate is never stopped on an unread identity.
    cwd: str | None = None
    env_sig: str | None = None

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
    tree: list[str] = field(default_factory=list)   # a stop's measured descendants (keys)
    ancestors: list[str] = field(default_factory=list)  # a stop's measured parent chain (keys)
    died: list[str] = field(default_factory=list)  # a stop's processes that actually died (keys)
    #: the measured process key ("pid:create_time"); apply refuses to write to a pid whose
    #: creation time is no longer this one (a reused pid), and to an action that carries none
    key: str = ""


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
        if not name or not (rule.get("match") or rule.get("group") or rule.get("script")):
            raise ValueError(f"rule without name and match/group/script: {rule!r}")
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
def script_identity(cmdline: str) -> tuple[str | None, list[str]]:
    """(script, its arguments) of a python command line, by PATH OR MODULE FORM. Pure.

    `... research\\pf_allocator.py --mode fast` and `-m research.pf_allocator --mode fast` are
    both "pf_allocator" (audit MF-A, 2026-10-29: exact substrings missed `-m`, `--mode=fast`,
    double spaces and a bare run). A `-c` program or no script at all is (None, [])."""
    toks = [t.strip("\"'") for t in cmdline.split()]
    for i, tok in enumerate(toks):
        low = tok.lower()
        if low == "-c":
            return None, []
        if low == "-m" and i + 1 < len(toks):
            return toks[i + 1].lower().rsplit(".", 1)[-1] or None, toks[i + 2:]
        if low.endswith((".py", ".pyw")):
            base = re.split(r"[\\/]", low)[-1]
            return base.rsplit(".", 1)[0] or None, toks[i + 1:]
    return None, []


#: The `--mode` spellings argparse accepts for pf_allocator (allow_abbrev, the default): every
#: unambiguous prefix down to `--m` (its only other long options are --seed and --help).
_MODE_FLAGS = ("--m", "--mo", "--mod", "--mode")


def parse_mode(args: Sequence[str], default: str = "normal") -> str:
    """The `--mode` argument AS ARGPARSE READS IT. Pure.

    `--mode X` / `--mode=X`, and the unambiguous prefixes argparse accepts (`--mod`, `--mo`,
    `--m`, each with `=` too); when it is given more than once the LAST one wins, as argparse
    stores it (audit SF-a, 2026-10-29: the first one was taken, so `--mode fast --mode heavy`
    read fast and escaped the heavy pin). Nothing after a bare `--` is an option. Absent is the
    script's default.
    """
    mode = default
    i = 0
    while i < len(args):
        low = args[i].lower()
        if low == "--":
            break
        flag, eq, value = low.partition("=")
        if flag in _MODE_FLAGS:
            if eq:
                mode = value or default
            elif i + 1 < len(args):
                mode = args[i + 1].lower()
                i += 1
        i += 1
    return mode


def script_mode(p: Proc) -> tuple[str | None, str]:
    """(script identity, parsed mode) of a process. Pure."""
    script, args = script_identity(p.cmdline)
    return script, parse_mode(args)


def rule_matches(rule: Mapping[str, Any], p: Proc) -> bool:
    """A rule names a process by `group`, by `script` (+ optional `mode`, parsed from argv), or
    by a `match` substring of exe + command line. Pure."""
    if rule.get("group"):
        return p.group == str(rule["group"])
    if rule.get("script"):
        script, mode = script_mode(p)
        return (script == str(rule["script"]).lower()
                and (rule.get("mode") is None or mode == str(rule["mode"]).lower()))
    return str(rule.get("match", "")).lower() in p.haystack and bool(rule.get("match"))


def classify(procs: Sequence[Proc], groups: Mapping[str, Sequence[str]],
             sticky_money: Collection[str] = ()) -> None:
    """Tag each process; the money, adopt and judge trees are whole. Precedence: money first.

    A tree is every process matched by name plus all its descendants by parent chain. A child
    is counted only if it was born no earlier than its parent (a ppid reused by a later process
    is not a parent): Windows recycles pids and keeps a dead parent's id in the child.

    MONEY IS STICKY BY KEY (audit MF2, 2026-10-29): `sticky_money` holds the keys
    ("pid:create_time") classified money on an earlier pass and still alive. A gateway child
    whose parent died is no longer under a live money root, so the tree alone would read it
    "other" and move, narrow, cap or dedupe it; a sticky key keeps it (and anything it spawns)
    money for as long as that process lives. `money_root` marks only the name-matched roots.
    """
    feed = {str(x).lower() for x in groups.get("money_feed", ())}
    pinned = {str(x).lower() for x in groups.get("money_feed_pinned", ())}

    def is_pinned(p: Proc) -> bool:
        script, mode = script_mode(p)
        return f"{script}:{mode}" in pinned

    def hit(p: Proc, kind: str) -> bool:
        if kind == "money_feed":
            # BY SCRIPT IDENTITY AND PARSED MODE (audit MF-A): every mode of a feed script is
            # money_feed except a pinned one (pf_allocator heavy keeps its committed pin)
            script, _mode = script_mode(p)
            return script in feed and not is_pinned(p)
        return any(s.lower() in p.haystack for s in groups.get(kind, ()))

    children: dict[int, list[Proc]] = {}
    by_pid = {p.pid: p for p in procs}
    for p in procs:
        if p.ppid == p.pid:
            continue
        parent = by_pid.get(p.ppid)
        if (parent is not None and parent.create_time and p.create_time
                and p.create_time < parent.create_time):
            continue  # the "parent" is a later process that reused the pid
        children.setdefault(p.ppid, []).append(p)

    sticky = set(sticky_money)

    def tree(kind: str) -> set[int]:
        out: set[int] = set()
        stack = [p.pid for p in procs
                 if hit(p, kind) or (kind == "money" and p.key in sticky)]
        while stack:
            cur = stack.pop()
            if cur in out:
                continue
            out.add(cur)
            stack.extend(c.pid for c in children.get(cur, ())
                         if c.pid != cur and not (kind == "money_feed" and is_pinned(c)))
        return out

    # THE RELEASE PATH RIDES WITH THE MONEY PATH (2026-10-29): the first automatic Adopt-And-Seal
    # run was measured with its python child on ~13% of a core, a 2.5-minute step past 25. Its
    # powershell and every py/python/git below it are `adopt` by parent chain, not by name.
    # THE MONEY PATH IS A TREE TOO (audit MF1, 2026-10-29): the gateway's python child
    # (state_pusher_loop.py) matched no money name and was narrowed by plan_reserve and share_cap.
    # Every descendant of a money process is money: raise-only, never narrowed.
    money_tree = tree("money")
    feed_tree = tree("money_feed")
    adopt_tree = tree("adopt")
    judge_tree = tree("judge")
    system = {s.lower() for s in groups.get("system_names", ())}
    for p in procs:
        p.money_root = hit(p, "money")
        p.pinned_mode = is_pinned(p)
        if p.pid in money_tree:
            p.group = "money"
        elif p.pid in feed_tree:
            p.group = "money_feed"
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
    # pid 0 is the System Idle Process: its "CPU" is the box's idle time, not work. Counted, it
    # inflated `busy` and so hid a starved judge (audit, 2026-10-29).
    procs = [p for p in procs if p.pid != 0]
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
            if not rule_matches(rule, p):
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
    _clamp_adopt_under_money(procs, out)
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


def _clamp_adopt_under_money(procs: Sequence[Proc], out: Plan) -> None:
    """MONEY PATH ON TOP (audit MF2, 2026-10-29). Pure; edits `out` in place.

    The adopt tree is raised, but never ABOVE the lowest class the money path will hold after
    this pass's own raises: the gateway python (MT5-GatewayResident) ran at Normal while the adopt
    tree went to AboveNormal. The floor is taken over the NAME-MATCHED money roots only (a money
    child at Idle is not the gateway) and is never below Normal (audit MF3). Each adopt priority
    action is cut to that money floor; one that would
    then be no raise at all is dropped, and with any money class unreadable the adopt raise is
    refused (a money path we cannot read is never assumed to be on top). Money raises are applied
    before adopt raises (`apply_ordered`), and an adopt raise lands only if every one did.
    """
    planned = {a.pid: a.after for a in out.actions if a.kind == "priority" and a.group == "money"}
    money = [p for p in procs if p.group == "money" and p.money_root]
    if not money:
        return
    classes = [planned.get(p.pid, p.priority) for p in money]
    unreadable = any(c not in PRIORITY_ORDER for c in classes)
    floor = (max(_rank("Normal"), min(_rank(c) for c in classes)) if not unreadable else -1)
    keep: list[Action] = []
    by_pid = {p.pid: p for p in procs}
    for a in out.actions:
        if a.kind != "priority" or a.group != "adopt":
            keep.append(a)
            continue
        if unreadable:
            out.refused.append({"pid": a.pid, "name": a.name, "group": a.group, "rule": a.rule,
                                "why": "a money-path class is unreadable: adopt is never raised "
                                       "over a money path that cannot be shown on top"})
            continue
        if _rank(str(a.after)) > floor:
            cur = by_pid[a.pid].priority if a.pid in by_pid else a.before
            if _rank(PRIORITY_ORDER[floor]) <= _rank(cur):
                out.refused.append({"pid": a.pid, "name": a.name, "group": a.group,
                                    "rule": a.rule,
                                    "why": f"adopt held at {cur}: the lowest money-path class is "
                                           f"{PRIORITY_ORDER[floor]}"})
                continue
            a.after = PRIORITY_ORDER[floor]
        keep.append(a)
    out.actions[:] = keep


def adopt_floor_actions(procs: Sequence[Proc], money_actions: Sequence[Action]) -> list[Action]:
    """Lower any adopt process left ABOVE the money path after this pass's money raises. Pure.

    THE ADOPT TREE NEVER OUTLIVES THE MONEY PATH'S CLASS (audit P6, 2026-10-29). An adopt process
    raised on an EARLIER pass carries no action now, so holding back this pass's adopt raises is
    not enough: a gateway that restarted at Normal and whose raise failed would sit under an
    adopt tree still at AboveNormal. The money floor is each money process's class after this
    pass (a landed raise's target, else the class measured), over the NAME-MATCHED money roots
    only, and never below Normal (audit MF3: a money child at Idle dragged the whole adopt tree
    to Idle); every adopt process above it is lowered to it, billed in missed_growth. With a
    money class unreadable the floor is unknown and the adopt tree is held
    at Normal, the class it started at, never assumed under a money path that cannot be read.
    """
    landed = {a.pid: str(a.after) for a in money_actions
              if a.kind == "priority" and a.applied and not a.error}
    money = [p for p in procs if p.group == "money" and p.money_root]
    if not money:
        return []
    classes = [landed.get(p.pid, p.priority) for p in money]
    if any(c not in PRIORITY_ORDER for c in classes):
        target = "Normal"
    else:
        target = PRIORITY_ORDER[max(_rank("Normal"), min(_rank(c) for c in classes))]
    out: list[Action] = []
    for p in procs:
        if p.group == "adopt" and _rank(p.priority) > _rank(target):
            out.append(Action(p.pid, p.name, p.group, "adopt_under_money", "priority",
                              p.priority, target, key=p.key))
    return out


def apply_ordered(actions: Sequence[Action], n_cpu: int,
                  procs: Sequence[Proc] = ()) -> list[Action]:
    """Apply money-path raises first; adopt raises only once every money raise has landed.

    Then (`procs` given) any adopt process still above the money floor is lowered to it
    (`adopt_floor_actions`); those extra actions are applied and returned for the report.
    """
    money = [a for a in actions if a.group == "money" and a.kind == "priority"]
    adopt = [a for a in actions if a.group == "adopt" and a.kind == "priority"]
    first = {id(a) for a in money} | {id(a) for a in adopt}
    rest = [a for a in actions if id(a) not in first]
    apply(money, n_cpu)
    failed = [a for a in money if not a.applied or a.error]
    if failed:
        for a in adopt:
            a.error = (f"not applied: money raise on pid {failed[0].pid} did not land "
                       f"({failed[0].error})")[:200]
    else:
        apply(adopt, n_cpu)
    lowered = adopt_floor_actions(procs, money) if procs else []
    apply(lowered, n_cpu)
    apply(rest, n_cpu)
    return lowered


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


def _cap_record(value: Any) -> tuple[str | None, list[int] | None]:
    """(mask set, original cores) of a share_cap_moved record. A bare string is the pre-SF1
    record (mask only, original unknown)."""
    if isinstance(value, Mapping):
        orig = value.get("orig")
        cores = [int(c) for c in orig] if isinstance(orig, list) else None
        return (str(value.get("mask")) if value.get("mask") else None), cores
    return (str(value) if value else None), None


def release_share_cap(procs: Sequence[Proc], previous: Mapping[str, Any], *, judge_starved: bool,
                      side_now: Sequence[int], side_base: Sequence[int], n_cpu: int,
                      skip_pids: set[int],
                      reserved: Any = None) -> tuple[list[Action], dict[str, Any]]:
    """Widen back what share_cap pinned once the judge is no longer starved. Pure.

    `previous` is last pass's `share_cap_moved` (process key -> {"mask": set, "orig": the cores
    it held before the pin}). While the judge is starved a pin stands. Once it is not, a pinned
    mining/other process is widened back to WHERE IT WAS (audit SF1): its original cores -- or,
    when the judge reservation applies to it (`reserved(p)`: mining/other python not exempt), the
    side mask, which the reservation would hold it to anyway. A non-python "other" pinned off 18
    cores gets 18 back, not the side mask. The record is kept while the process is narrower than
    that target under the BASE side (a boost still on), so the widening finishes when the boost
    ends. A process now in a raise-only
    group (e.g. it turned out to be the adopt tree) is widened to every core.
    """
    full = set(range(n_cpu))
    is_reserved = reserved if reserved is not None else (lambda _p: True)
    actions: list[Action] = []
    keep: dict[str, Any] = {}
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
        _set, orig_l = _cap_record(previous[p.key])
        orig = (set(orig_l) & full) if orig_l else full
        if is_reserved(p):
            # the reservation keeps it on the side mask whatever it held before: its recorded
            # cores inside the side (the side itself when they held none of it)
            target_now = (orig & set(side_now)) or set(side_now)
            target_base = (orig & set(side_base)) or set(side_base)
        else:
            target_now = target_base = orig
        # RESTORE EXACTLY WHAT WAS RECORDED (audit, 2026-10-29): the pin's cores are not kept on
        # top of the original (cur | orig gave a mask the process never held).
        after = cur
        if target_now and target_now != cur:
            actions.append(Action(p.pid, p.name, p.group, "share_cap_release", "affinity",
                                  _mask(p.affinity), cpus_to_mask(sorted(target_now))))
            after = target_now
        if target_base != after:
            rec = previous[p.key]
            keep[p.key] = dict(rec) if isinstance(rec, Mapping) else {"mask": rec, "orig": None}
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


def reserve_applies(p: Proc, cfg: Mapping[str, Any]) -> bool:
    """The judge reservation moves only mining/other python that no exemption names."""
    exempt = [str(e).lower() for e in cfg.get("exempt", [])]
    return (p.group in ("mining", "other") and "python" in p.name.lower()
            and not any(e in p.haystack for e in exempt))


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
        if p.pid in skip_pids or not reserve_applies(p, cfg):
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


#: Groups widened to every core on every pass (audit MF-B): what the money path runs on.
WIDENED_EVERY_PASS = frozenset({"money", "money_feed"})


def widen_money(procs: Sequence[Proc], n_cpu: int, skip_pids: set[int]) -> list[Action]:
    """Every money / money_feed process not already on every core is widened to every core. Pure.

    A CHILD INHERITS ITS PARENT'S MASK (audit MF-B, 2026-10-29): hourly_cycle (other) and
    research_supervisor (mining) sit on the side mask, so the allocators they launch started on
    10 cores (6 boosted), and nothing widened them -- plan_reserve widens only what it moved
    and release_share_cap only what it pinned. This runs every pass, whoever narrowed it. The
    pf_allocator heavy pin is untouched: a pinned mode is never money_feed (`classify`).
    """
    full = list(range(n_cpu))
    out: list[Action] = []
    for p in procs:
        if (p.group in WIDENED_EVERY_PASS and p.pid not in skip_pids
                and p.affinity is not None and sorted(set(p.affinity)) != full):
            out.append(Action(p.pid, p.name, p.group, "money_widen", "affinity",
                              _mask(p.affinity), cpus_to_mask(full), key=p.key))
    return out


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


#: TWO-SIDED THROTTLES (audit SF2, 2026-10-29; growth governance): every throttle this module
#: applies carries a ledger line in BOX_BOTTLENECKS.json `missed_growth` -- what the throttled
#: process gave up AND what the judge gained across it. tests/ops/test_box_shaper.py fences every
#: libs/ops module that throttles another process (scripts/check_growth_governance.py is signed).
THROTTLE_LEDGER = "missed_growth"
_LEDGER_KEEP = 20


def throttle_mechanisms(rules: Mapping[str, Any]) -> list[str]:
    """Every mechanism in the rules that can take CPU from a process: affinity rules, rules that
    may lower a class (not raise-only), the share cap, the judge reserve and the dedupe stop
    (a stopped duplicate is the hardest throttle there is: its whole share goes)."""
    ceiling = rules.get("priority_ceiling", "AboveNormal")
    out = [str(r["name"]) for r in rules.get("rules", [])
           if "affinity" in r or (r.get("priority") and r.get("group") not in RAISE_ONLY
                                  and r.get("priority") != ceiling)]
    if rules.get("share_cap"):
        out.append("share_cap")
    if rules.get("judge_reserve"):
        out.append("judge_reserve")
    if rules.get("dedupe") is not None:
        out.append("dedupe")
    # lowering the adopt tree under the money floor takes CPU class from it (audit MF3)
    out.append("adopt_under_money")
    return out


def _narrows(a: Action) -> bool:
    if a.kind == "stop":
        return True
    if a.kind == "priority":
        # A class set from an UNREADABLE one may be a lowering, so it is billed as one (audit,
        # 2026-10-29): before, _rank(None) = -1 made every such set read as a raise.
        if a.before not in PRIORITY_ORDER:
            return True
        return _rank(str(a.after)) < _rank(a.before)
    before = len(mask_to_cpus(str(a.before), 4096)) if a.before is not None else 4096
    return len(mask_to_cpus(str(a.after), 4096)) < before


def missed_growth_ledger(previous: Mapping[str, Any] | None, *, rules: Mapping[str, Any],
                         procs: Sequence[Proc], actions: Sequence[Action], n_cpu: int, at: str,
                         judge_share: float | None, lives: Any = None) -> dict[str, Any]:
    """THE TWO-SIDED LINE FOR EVERY THROTTLE (growth governance). Pure.

    Each landed action that narrows a process (fewer cores, lower class) opens an event with the
    process's share of the box and the judge's share BEFORE. The next measured pass closes it:
    `forgone_share` is what the throttled process gave up (before minus after; a process gone by
    then reads 0 after and says so), `judge_gain_share` is what the judge gained, and
    `net_share` = gain minus forgone. A throttle whose net stays negative is costing growth, and
    the line says so in numbers; one whose gain is unmeasured says UNMEASURED, never zero.
    A process this pass did not read but that still lives (`lives(key)`: alive, same create
    time) is not "gone": its event stays open until a pass reads it, so an unreadable process is
    never billed its whole share as forgone.
    """
    prev = previous or {}
    cap = 100.0 * max(1, n_cpu)
    by_key = {p.key: p for p in procs}
    out: dict[str, Any] = {}
    for name in throttle_mechanisms(rules):
        raw_old = prev.get(name)
        old: Mapping[str, Any] = raw_old if isinstance(raw_old, Mapping) else {}
        totals = dict(old.get("totals") or {"n": 0, "forgone_share": 0.0,
                                             "judge_gain_share": 0.0, "net_share": 0.0,
                                             "unmeasured": 0})
        closed = list(old.get("closed") or [])
        still_open: list[dict[str, Any]] = []
        for ev in old.get("open") or []:
            if not isinstance(ev, Mapping):
                continue
            ev = dict(ev)
            if isinstance(ev.get("keys"), list):
                # a stop bills the processes that died, read again by key (all gone, normally)
                left = [by_key[str(k)] for k in ev["keys"] if str(k) in by_key]
                ev["share_after"] = round(sum(q.cpu_pct for q in left) / cap, 4)
                ev["gone"] = not left
            else:
                p = by_key.get(str(ev.get("key")))
                if p is None and lives is not None and lives(str(ev.get("key"))):
                    still_open.append(ev)   # alive but unread this pass: not closed as gone
                    continue
                ev["share_after"] = round(p.cpu_pct / cap, 4) if p is not None else 0.0
                ev["gone"] = p is None
            ev["judge_share_after"] = judge_share
            ev["forgone_share"] = round(float(ev.get("share_before") or 0.0)
                                        - ev["share_after"], 4)
            jb = ev.get("judge_share_before")
            if isinstance(jb, (int, float)) and judge_share is not None:
                ev["judge_gain_share"] = round(judge_share - float(jb), 4)
                ev["net_share"] = round(ev["judge_gain_share"] - ev["forgone_share"], 4)
                totals["judge_gain_share"] = round(totals["judge_gain_share"]
                                                   + ev["judge_gain_share"], 4)
                totals["net_share"] = round(totals["net_share"] + ev["net_share"], 4)
            else:
                ev["judge_gain_share"] = ev["net_share"] = "UNMEASURED"
                totals["unmeasured"] = int(totals.get("unmeasured", 0)) + 1
            totals["n"] = int(totals["n"]) + 1
            totals["forgone_share"] = round(totals["forgone_share"] + ev["forgone_share"], 4)
            closed.append(ev)
        for a in actions:
            if a.rule != name or not _narrows(a):
                continue
            p = next((q for q in procs if q.pid == a.pid), None)
            if p is None:
                continue
            if a.kind == "stop":
                # A STOP BILLS WHAT ACTUALLY DIED (audit #482 SF3): the duplicate and the
                # measured descendants that are gone -- children killed under a denied root
                # are billed although the stop did not land; a denied child that still lives
                # is not billed as forgone.
                died = [k for k in a.died if k in by_key]
                if not died:
                    continue
                still_open.append({"at": at, "key": p.key, "pid": p.pid, "name": p.name,
                                   "group": p.group, "kind": a.kind, "before": a.before,
                                   "after": a.after, "keys": died, "landed": a.applied,
                                   "share_before": round(sum(by_key[k].cpu_pct for k in died)
                                                         / cap, 4),
                                   "judge_share_before": judge_share})
                continue
            if not a.applied or a.error:
                continue
            still_open.append({"at": at, "key": p.key, "pid": p.pid, "name": p.name,
                               "group": p.group, "kind": a.kind, "before": a.before,
                               "after": a.after, "share_before": round(p.cpu_pct / cap, 4),
                               "judge_share_before": judge_share})
        out[name] = {"two_sided": True,
                     "cost": "forgone_share: the throttled process's share of the box given up",
                     "gain": "judge_gain_share: the judge's share of the box gained across it",
                     "open": still_open[-_LEDGER_KEEP:], "closed": closed[-_LEDGER_KEEP:],
                     "totals": totals}
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


def track_wall(procs: Sequence[Proc], match: str | Mapping[str, Any],
               previous: Mapping[str, Any] | None, now: float) -> dict[str, Any]:
    """Wall time of each run of a tracked process, carried pass to pass. Pure.

    A run still live reports `wall_s` so far; a run seen last pass and gone now moves to
    `finished` with `wall_s_at_least` (its last reading: the true end is up to one pass later).
    """
    prev = previous or {}
    running = [{"key": p.key, "started_at": datetime.fromtimestamp(p.create_time, UTC)
                .isoformat(timespec="seconds"), "wall_s": round(max(0.0, now - p.create_time)),
                "cores": None if p.affinity is None else len(p.affinity)}
               for p in procs
               if (rule_matches(match, p) if isinstance(match, Mapping)
                   else match.lower() in p.haystack)]
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
    creation time) was already reported on the previous pass, AND no descendant AND no ancestor
    of the duplicate is in NEVER_IN_A_STOPPED_TREE (a child of the gateway is the money path),
    AND both share one working directory and environment (`read_identity`; unread is never
    stopped). The refusal is reported on the row. At apply time the pid, the tree and the parent
    chain are re-checked against the measurement, the verified process object itself is killed
    (no pid-only fallback), and the stop counts only once the root is gone.

    TORN OUTPUT (audit S3): on Windows psutil's terminate() and kill() are the same
    TerminateProcess -- a detached SYSTEM-run loop has no console to send CTRL_BREAK to -- so
    there is no graceful stop to wait on, and a duplicate stopped mid-write can leave a
    half-written file. Allow-list only a loop whose writes are atomic (tmp file + os.replace),
    whose surviving twin rewrites the same outputs on its next cycle.
    """
    allow = [str(a).lower() for a in cfg.get("allow", [])]
    seen_before = set(previous_duplicates)
    buckets: dict[tuple[str, str], list[Proc]] = {}
    for p in dedupe_candidates(procs):
        buckets.setdefault((p.exe.lower(), p.cmdline), []).append(p)
    stops: list[Action] = []
    report: list[dict[str, Any]] = []
    children: dict[int, list[Proc]] = {}
    by_pid = {p.pid: p for p in procs}
    for p in procs:
        children.setdefault(p.ppid, []).append(p)

    def ancestors(p: Proc) -> list[Proc]:
        """The measured parent chain, nearest first (audit #482 MF1)."""
        out: list[Proc] = []
        seen: set[int] = {p.pid}
        cur = p
        while cur.ppid in by_pid and cur.ppid not in seen and len(out) < 64:
            cur = by_pid[cur.ppid]
            seen.add(cur.pid)
            out.append(cur)
        return out

    def descendants(pid: int) -> list[Proc]:
        out: list[Proc] = []
        seen: set[int] = {pid}
        stack = [pid]
        while stack:
            for c in children.get(stack.pop(), ()):
                if c.pid not in seen:
                    seen.add(c.pid)
                    out.append(c)
                    stack.append(c.pid)
        return out

    for members in buckets.values():
        if len(members) < 2:
            continue
        pids = {m.pid for m in members}
        parents = [m.ppid for m in members]
        if any(pp in pids for pp in parents) or len(set(parents)) < len(parents):
            continue
        # SAME LOOP, NOT JUST THE SAME COMMAND LINE (audit #482 SF3): two loops for different
        # accounts can share exe and command line and differ only in working directory or
        # environment. Members are grouped by (cwd, env hash) too; a member whose identity was
        # not read is reported but never stopped.
        unread = any(m.cwd is None or m.env_sig is None for m in members)
        if unread:
            sets = [members]
        else:
            groups: dict[tuple[str, str], list[Proc]] = {}
            for m in members:
                groups.setdefault((str(m.cwd).lower(), str(m.env_sig)), []).append(m)
            sets = [g for g in groups.values() if len(g) > 1]
        for same in sets:
            same = sorted(same, key=lambda m: (m.create_time, m.pid))
            keeper = same[0]
            allowed = any(a in keeper.haystack for a in allow)
            for dup in same[1:]:
                tree = descendants(dup.pid)
                chain = ancestors(dup)
                guarded = [c for c in tree if _never_stopped(c)]
                guarded_up = [c for c in chain if _never_stopped(c)]
                row: dict[str, Any] = {"keep": keeper.key, "duplicate": dup.key,
                                       "name": dup.name, "group": dup.group, "allowed": allowed,
                                       "cmd": _short_cmd(dup)}
                if guarded:
                    row["refused"] = (f"descendant {guarded[0].pid} ({guarded[0].name}) is "
                                      f"{_guard_label(guarded[0])}: a tree stop would take it "
                                      "down")
                elif guarded_up:
                    # A CHILD OF THE MONEY PATH IS PART OF THE MONEY PATH (audit #482 MF1): the
                    # gateway's own state_pusher_loop was planned for a stop because an older,
                    # unrelated launcher ran the same command line.
                    row["refused"] = (f"ancestor {guarded_up[0].pid} ({guarded_up[0].name}) is "
                                      f"{_guard_label(guarded_up[0])}: its child is never "
                                      "stopped")
                elif unread:
                    row["refused"] = ("cwd/environment unread: not shown to be the same loop "
                                      "(different accounts can share one command line)")
                report.append(row)
                if allowed and dup.key in seen_before and "refused" not in row:
                    stops.append(Action(dup.pid, dup.name, dup.group, "dedupe", "stop", dup.key,
                                        f"stopped; kept {keeper.key}",
                                        tree=sorted(c.key for c in tree),
                                        ancestors=[c.key for c in chain]))
    return stops, report


def _never_stopped(p: Proc) -> bool:
    """In a guarded group, or a feed script in its pinned mode (pf_allocator heavy, SF-b)."""
    return p.group in NEVER_IN_A_STOPPED_TREE or p.pinned_mode


def _guard_label(p: Proc) -> str:
    if p.group in NEVER_IN_A_STOPPED_TREE:
        return p.group
    return "a pinned allocator (money_feed_pinned)"


def dedupe_candidates(procs: Sequence[Proc]) -> list[Proc]:
    """Processes that may be a duplicate: mining/other with a command line, no pool worker, not
    a pinned allocator run."""
    return [p for p in procs if p.group in DEDUPE_GROUPS and p.cmdline.strip()
            and not p.pinned_mode
            and not any(m in p.cmdline.lower() for m in _WORKER_MARKERS)]


def read_identity(procs: Sequence[Proc]) -> None:
    """Fill cwd / env_sig for every candidate whose exe + command line appears twice (the only
    ones dedupe compares), from the SAME process (pid and creation time re-checked). An
    unreadable one stays None, which dedupe never stops on."""
    if psutil is None:
        return
    counts: dict[tuple[str, str], int] = {}
    cands = dedupe_candidates(procs)
    for p in cands:
        counts[(p.exe.lower(), p.cmdline)] = counts.get((p.exe.lower(), p.cmdline), 0) + 1
    for p in cands:
        if counts[(p.exe.lower(), p.cmdline)] < 2:
            continue
        try:
            pr = psutil.Process(p.pid)
            if int(pr.create_time()) != int(p.create_time):
                continue
            cwd = pr.cwd()
            env = pr.environ()
        except Exception:  # access denied / gone: identity unread, never guessed
            continue
        p.cwd = str(cwd)
        blob = json.dumps(sorted((str(k).upper(), str(v)) for k, v in env.items()))
        p.env_sig = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


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


def _keys_to_ctimes(keys: Sequence[str]) -> dict[int, float]:
    """Measured process keys ("pid:create_time") -> {pid: create_time}; a malformed key drops."""
    out: dict[int, float] = {}
    for k in keys:
        pid_s, _sep, ct_s = str(k).partition(":")
        try:
            out[int(pid_s)] = float(ct_s)
        except ValueError:
            continue
    return out


def _ctime_of(pr: Any) -> int | None:
    """A live psutil.Process's creation second, or None when it cannot be read."""
    try:
        return int(pr.create_time())
    except Exception:  # gone / denied: unread, never guessed
        return None


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
                # THE TREE MUST STILL BE THE ONE THAT WAS CLASSIFIED: a descendant born since
                # the measurement was never checked against the guarded groups, so it refuses.
                verified = _keys_to_ctimes(a.tree)
                unknown = sorted(c.pid for c in pr.children(recursive=True)
                                 if c.pid not in verified
                                 or _ctime_of(c) != int(verified[c.pid]))
                if unknown:
                    a.error = (f"tree changed since measurement (unclassified descendant(s) "
                               f"{unknown[:5]}); not stopped")[:200]
                    continue
                # THE PARENT CHAIN MUST BE THE ONE THAT WAS CLASSIFIED (audit #482 MF1): a live
                # ancestor the plan never saw was never checked against the guarded groups.
                up = [f"{x.pid}:{int(x.create_time())}" for x in pr.parents()]
                foreign = [k for k in up if k not in set(a.ancestors)]
                if foreign:
                    a.error = (f"ancestor chain changed since measurement (unclassified "
                               f"{foreign[:3]}); not stopped")[:200]
                    continue
                # THE VERIFIED PROCESS IS WHAT IS KILLED (audit #482 SF1): never the bare pid,
                # and no taskkill /PID fallback that could hit a pid reused since the check.
                # LANDED ONLY WHEN THE ROOT IS GONE (SF2): its children dying is not a stop.
                from libs.ops.proctree import kill_verified_tree
                result = kill_verified_tree(pr, verified=verified)
                # WHAT ACTUALLY DIED is what missed_growth bills (audit #482 SF3): children
                # killed under a denied root, or a root gone with one child denied, are partial.
                a.died = [str(k) for k in result.get("dead") or []]
                if result.get("refused"):
                    a.error = str(result["refused"])[:200]
                    continue
                if not result.get("root_gone"):
                    a.error = f"the duplicate's root is still running: {result}"[:200]
                    continue
                a.applied = True
                continue
            # THE PID MUST STILL BE THE PROCESS THAT WAS MEASURED (audit SF1, 2026-10-29): a
            # class or mask is never written to a pid reused since the measurement.
            if not a.key:
                a.error = "not applied: no measured key to verify the pid against"
                continue
            if f"{a.pid}:{int(pr.create_time())}" != a.key:
                a.error = "pid reused since measurement; not applied"
                continue
            if a.kind == "priority":
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


def carried_records(prev: Mapping[str, Any]) -> dict[str, Any]:
    """The pass-to-pass records an unmeasured pass must carry forward unchanged. Pure."""
    cap = prev.get("share_cap_moved")
    res = prev.get("judge_reserve")
    res = res if isinstance(res, Mapping) else {}
    moved = res.get("moved")
    out: dict[str, Any] = {
        "share_cap_moved": dict(cap) if isinstance(cap, Mapping) else {},
        "judge_reserve": {"moved": dict(moved) if isinstance(moved, Mapping) else {},
                          "switches": list(res.get("switches") or []),
                          "carried_from": prev.get("generated_at")}}
    if isinstance(prev.get("wall"), Mapping):
        out["wall"] = dict(prev["wall"])
    if isinstance(prev.get(THROTTLE_LEDGER), Mapping):
        out[THROTTLE_LEDGER] = dict(prev[THROTTLE_LEDGER])
    if isinstance(prev.get("money_keys"), list):
        out["money_keys"] = list(prev["money_keys"])
    return out


def sticky_money_keys(previous: Any, seen: Mapping[str, Proc], alive: Any,
                      create_time: Any = None) -> set[str]:
    """Last pass's money keys whose process still lives (`key_lives`). Pure.

    A key seen this pass lives by definition; an unseen one is kept while its pid is alive with
    the key's creation time, so one unread pass never drops a process out of the money path."""
    keys = previous if isinstance(previous, list) else []
    return {str(k) for k in keys
            if str(k) in seen or key_lives(str(k), alive, create_time)}


def pid_create_time(pid: int) -> float | None:
    """The live process's create time, or None when it cannot be read (gone, denied, no psutil)."""
    if psutil is None:
        return None
    try:
        return float(psutil.Process(pid).create_time())
    except Exception:  # a gone or protected process is a reading, not a crash
        return None


def key_lives(key: str, alive: Any, create_time: Any = None) -> bool:
    """Is the process named by `key` ("pid:create_time") still the one alive at that pid? Pure.

    The pid must be alive AND, when its create time can be read, born at the key's second: a
    reused pid is a different process (audit, 2026-10-29). An alive pid whose create time cannot
    be read is not proven to be another process, so it still counts as the same one.
    """
    try:
        pid_s, _sep, ct_s = str(key).partition(":")
        pid = int(pid_s)
        ct_key = int(ct_s) if ct_s else None
    except ValueError:
        return False
    if alive is None or not alive(pid):
        return False
    ct = create_time(pid) if create_time is not None else None
    return ct is None or ct_key is None or int(ct) == ct_key


def keep_unseen(records: dict[str, Any], previous: Mapping[str, Any], seen: set[str],
                alive: Any, create_time: Any = None) -> dict[str, Any]:
    """Records of processes this pass did not read (a psutil error on one) but that still live
    are kept: the pid alive and its create time the key's (`key_lives`). Pure."""
    for k, v in previous.items():
        if k in records or k in seen:
            continue
        if key_lives(str(k), alive, create_time):
            records[k] = v
    return records


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
        # A PASS THAT MEASURES NOTHING FORGETS NOTHING (audit MF1, 2026-10-29): the pins this
        # shaper set are carried forward verbatim, or one empty or refused pass would strand a
        # miner narrowed to 0x3000F on six cores for good.
        report.update(carried_records(prev))
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
    seen_by_key = {p.key: p for p in procs}
    sticky = sticky_money_keys(prev.get("money_keys"), seen_by_key, psutil.pid_exists,
                               pid_create_time)
    classify(procs, rules.get("groups", {}), sticky)
    # carried forward: this pass's money, and last pass's money that lives but went unread
    money_keys = sorted({p.key for p in procs if p.group == "money"}
                        | {k for k in sticky if k not in seen_by_key})
    summary = summarize(procs, n_cpu, box_pct, rules.get("judge_starved", {}))
    starved_now = bool(summary["judge"]["starved"])
    the_plan = plan(procs, rules, n_cpu, judge_starved=starved_now,
                    previous_heavy=list(prev.get("heavy") or []))
    read_identity(procs)
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
        n_cpu=n_cpu, skip_pids=pinned_now,
        reserved=(lambda p: reserve_applies(p, reserve_cfg)) if reserve_cfg else
        (lambda _p: False))
    the_plan.actions.extend(release_actions)
    for a in the_plan.actions:
        if a.rule == "share_cap" and a.pid in key_of:
            k = key_of[a.pid]
            _old_set, old_orig = _cap_record(prev_cap.get(k)) if k in prev_cap else (None, None)
            before = None if a.before is None else mask_to_cpus(str(a.before), n_cpu)
            cap_moved[k] = {"mask": str(a.after),
                            "orig": old_orig if old_orig else (before or list(range(n_cpu)))}
    seen_keys = {p.key for p in procs}
    keep_unseen(cap_moved, prev_cap, seen_keys, psutil.pid_exists, pid_create_time)
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
        keep_unseen(moved, prev_moved, seen_keys, psutil.pid_exists, pid_create_time)
        reserve_doc = {**meta, "phase": phase, "phase_pid": phase_pid, "serial": serial,
                       "starved": summary["judge"]["starved"], "moved": moved,
                       "switches": log_switch(prev_res.get("switches") or [], at=now,
                                              mode=str(meta["mode"]), phase=phase,
                                              starved=starved_now,
                                              judge_share=summary["judge"]["share_of_box"],
                                              mining_share=summary["by_group"].get(
                                                  "mining", {}).get("share_of_box", 0.0),
                                              side_cores=int(meta["side_cores"]))}
    the_plan.actions.extend(widen_money(
        procs, n_cpu, {a.pid for a in the_plan.actions if a.kind == "affinity"}))
    for a in the_plan.actions:       # every write is verified against the measured key
        if not a.key and a.pid in key_of:
            a.key = key_of[a.pid]
    the_plan.actions.extend(apply_ordered(the_plan.actions, n_cpu, procs))
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
    wall = {r["name"]: track_wall(procs, r, prev_wall.get(r["name"]), time.time())
            for r in rules.get("rules", []) if r.get("track_wall")}
    prev_ledger = prev.get(THROTTLE_LEDGER)
    ledger = missed_growth_ledger(
        prev_ledger if isinstance(prev_ledger, Mapping) else None, rules=rules, procs=procs,
        actions=the_plan.actions, n_cpu=n_cpu, at=now,
        judge_share=float(summary["judge"]["share_of_box"]),
        lives=lambda k: key_lives(k, psutil.pid_exists, pid_create_time))
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
        judge_reserve=reserve_doc, money_keys=money_keys, missed_growth=ledger,
        health=hunter_health, judge_phase=phase, judge_phase_status=phase_st,
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
