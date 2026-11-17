"""THE JUDGE'S CORE SHARE: a floor of reserved cores, borrowing idle ones while it is behind pace.

THE DECISION (principal zuck, 2026-11-13, project timeline):
    23:10:40Z  "Yes give judging 6 cores"
    23:12:39Z  "Yes adaptive"  -- a floor of 6 cores; borrow idle cores while the backlog grows or
               first verdicts run below the 150k/day pace; give them back when mining needs them;
               trading and live keep priority.

WHY CORES, NOT PRIORITY. `scripts/judge_priority.py` keeps the judge's priority CLASS equal to the
miners' (BELOW_NORMAL) and strictly below the live clocks (E8 at NORMAL): there is no class
between the two, so priority cannot give the judge a share without putting it level with live
trading, which starved E8 when tried (2026-10-08). The measured cost of equality (box,
2026-11-13 21:46Z, JUDGING_THROUGHPUT.json): judge 0.63 busy cores beside 16.43 for everything
else, and 15,625 first-terminal verdicts in 24h -- 10.4% of the 150k/day floor.

THE MECHANISM: processor AFFINITY on the research processes, never on the judge or live.
  * `reserve` logical CPUs (the highest-numbered) are taken out of the affinity of POSITIVELY
    IDENTIFIED mining and audit processes only (`confinable`: the mining residents named in
    MINER_SCRIPTS and their children, and the frontier audit lane; never a PROTECTED money or
    clock script or its child, never an unknown script). Those cores then run only the judge,
    live trading, the terminal and every process not on that list.
  * The judge's own affinity is never touched: it keeps every core, so it still uses any core
    the miners leave idle (borrowing in the plain sense), and the live processes keep every core
    and their higher class -- trading always preempts everything here.
  * No priority class is changed by this module.

THE ADAPTIVE RULE (`decide`), re-read every INTERVAL_S inside the judge's own sweep process:
  demand   = judge processes doing work (leaves of the judge's process tree: one during the
             single-threaded plan/merge, the pool or shard workers during prewarm/build). Zero
             -> nothing is reserved and every miner gets its cores back (IDLE).
  floor    = min(FLOOR, demand, cores - MINER_MIN)       always reserved while the judge works.
  borrow   = only while the pace reads MEASURED and BELOW (24h first-terminal verdicts under
             PACE_FLOOR_PER_DAY, or the burndown GROWING): the reservation grows by the miners'
             idle allowed cores, up to min(CEILING, demand, cores - MINER_MIN).
  give back= the moment the miners' busy cores come within SATURATED of their allowed cores, the
             reservation drops straight back to the floor. Pace UNMEASURED -> floor only.

FAILS SAFE. Every process is re-identified by start time before its affinity is set (pid reuse),
its original affinity is recorded in STATE before the first change, and `release` restores it:
on the sweep's exit (`Enforcer.stop`), and from `judging_throughput.run` when the sweep that owned
the reservation is gone (`release_orphaned`). Any error in a tick is caught and published; it can
never stop the judge. `JUDGE_CORE_SHARE=0` turns it off (and the next tick releases).

GROWTH GOVERNANCE: confining the miners is a cap on mining, so every change of the reservation
publishes a missed-growth line on REPORT (`missed_growth`), carried into MISSED_GROWTH.json by
`research/missed_growth.py` (`organ_published_lines`). Its price in E[log W] is UNMEASURED; its
units are the miners' confined cores, with their measured busy cores beside them.
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
import threading
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

SCHEMA = "judge-core-share/1"
REPORT = DESK / "reports" / "JUDGE_CORE_SHARE.json"
STATE = DESK / "data" / "judge_core_share_state.json"
RATE = DESK / "reports" / "JUDGING_RATE.json"
THROUGHPUT = DESK / "reports" / "JUDGING_THROUGHPUT.json"
UNMEASURED = "UNMEASURED"

FLOOR = 6
CEILING = 12
MINER_MIN = 4
INTERVAL_S = 10.0
PUBLISH_S = 60.0
PACE_FLOOR_PER_DAY = 150_000
#: The miners leave at least this many of their allowed cores idle -> the judge may borrow.
SLACK_BORROW = 1.5
#: The miners' busy cores within this of their allowed cores -> they need them: give back.
SATURATED = 0.5
RESTRICT = frozenset({"miner", "audit"})
JUDGE = frozenset({"judge", "judge_warm"})
#: THE CONFINED SET IS AN ALLOWLIST (audit HOLD MF1 of 3697de46). `judge_priority.classify`
#: calls every UNCLAIMED python process a miner, which is harmless where it only sets the
#: judge's own class and wrong here, where the class decides whose cores are taken: the FTMO
#: executor, the promoter's hourly cycle and the forward clocks are unclaimed python too. So a
#: process is confined only when it, or an ancestor born before it, runs one of these MINING
#: residents (the box's research tasks in ops/box_tasks.manifest, and their department, forest,
#: swarm and deepening children) or the frontier audit lane -- and NEVER when it or any ancestor
#: up to that miner runs a PROTECTED script, so a money or clock organ started under a miner is
#: still left alone. An unknown python script is never confined.
MINER_SCRIPTS = frozenset({
    "department_resident.py",    # MT5-Dept-*, MT5-Forest-* (dept:* plans run no core leg)
    "moat_swarms.py",            # MT5-Moat-Exploit / Explore / Resurrect
    "scout_swarm.py", "forest_runner.py", "deep_forest_miner.py", "qd_frontier.py",
    "deepening_worker.py",       # MT5-Deepening
    "moat_miner.py",             # MT5-MoatMiner
})
AUDIT_MARK = "run_frontier_audit.cmd"
PROTECTED_SCRIPTS = frozenset({
    # live money and its guards
    "gateway_resident.py", "run_gateway_loop.py", "gateway.py", "e8_executor.py", "e8_gold.py",
    "e8_guard.py", "e8_window_guard.py", "ftmo_executor.py", "ftmo_follower.py", "ftmo_follow.py",
    "fusion_deadman.py", "allocator_trigger.py", "scalp_exec.py",
    # promotion and the forward clocks
    "promoter.py", "shadow_forward.py", "forward_clock.py", "qquant_shadow.py",
    "box_heartbeat.py", "stall_watch.py",
    # the allocator's solve and its heavy admission scan, which gates STANDBY -> LIVE (audit SF2
    # of 667dabe3: promotion latency must never depend on judge load, whichever plan runs it)
    "pf_allocator.py", "state_admission_run.py",
})
#: A department resident whose whole plan is promotion and capital work. `dept:forward` runs
#: enrol_clocks, state_admission, pf_allocator, the forward lanes and allocator_trigger
#: (hourly_cycle.LEG_DEPARTMENT), so its resident and every child of it is left alone.
PROTECTED_DEPTS = frozenset({"forward"})
RAIL = "judge_core_share"
HISTORY = 200
APPROVAL = ("principal zuck 2026-11-13, project timeline: "
            "cmsg_012XFUfE12Rvggnu86fDb8pr59X51zLTU2AVN3ARu8Zb2T 23:10:40Z "
            "'Yes give judging 6 cores'; "
            "cmsg_012XFUfE12Rvggnu86fDb8prNjscKHSai3YwEysTRsHbP9 23:12:39Z 'Yes adaptive'")


def _env_int(name: str, default: int, lo: int, hi: int) -> int:
    try:
        v = int(os.environ.get(name, ""))
    except ValueError:
        return default
    return min(max(v, lo), hi)


def settings() -> dict[str, Any]:
    """The rule's knobs; FLOOR / CEILING may be moved by env without a release."""
    floor = _env_int("JUDGE_CORE_FLOOR", FLOOR, 0, 256)
    ceiling = max(floor, _env_int("JUDGE_CORE_CEILING", CEILING, 0, 256))
    enabled = os.environ.get("JUDGE_CORE_SHARE", "1").strip().lower() not in (
        "0", "off", "false", "no")
    return {"enabled": enabled, "floor": floor, "ceiling": ceiling, "miner_min": MINER_MIN,
            "interval_s": INTERVAL_S, "pace_floor_per_day": PACE_FLOOR_PER_DAY}


def _json(path: Path) -> dict[str, Any]:
    try:
        got = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return got if isinstance(got, dict) else {}


def pace(rate: dict[str, Any] | None = None, throughput: dict[str, Any] | None = None, *,
         floor_per_day: int = PACE_FLOOR_PER_DAY) -> dict[str, Any]:
    """Is the judge behind? 24h first-terminal verdicts vs the floor, and the burndown trend."""
    rate = _json(RATE) if rate is None else rate
    throughput = _json(THROUGHPUT) if throughput is None else throughput
    counts = ((rate.get("verdicts") or {}).get("first_terminal_counts") or {})
    per_day = counts.get("24h")
    burndown = (throughput.get("queue") or {}).get("burndown_status", UNMEASURED)
    if not isinstance(per_day, (int, float)) or isinstance(per_day, bool):
        return {"status": UNMEASURED, "first_terminal_per_day": None, "floor": floor_per_day,
                "burndown": burndown, "below_pace": None,
                "why": "JUDGING_RATE.json carries no 24h first-terminal count"}
    below = per_day < floor_per_day or burndown == "GROWING"
    return {"status": "MEASURED", "first_terminal_per_day": per_day, "floor": floor_per_day,
            "burndown": burndown, "below_pace": below,
            "share_of_floor": round(per_day / floor_per_day, 4) if floor_per_day else None}


def judge_demand(rows: Iterable[dict[str, Any]]) -> int:
    """Judge processes doing work: the leaves of the judge's process tree (a parent that only
    waits on its workers is not counted, a lone merging process is)."""
    judge = [r for r in rows if r.get("cls") in JUDGE]
    parents = {int(r.get("ppid") or 0) for r in judge}
    return sum(1 for r in judge if int(r.get("pid") or 0) not in parents)


def _scripts(cmdline: Any) -> set[str]:
    out = set()
    for a in (cmdline or []):
        name = str(a).replace("\\", "/").rsplit("/", 1)[-1].lower()
        if name.endswith((".py", ".cmd")):
            out.add(name)
    return out


def _dept(cmdline: Any) -> str | None:
    args = [str(a) for a in (cmdline or [])]
    for i, a in enumerate(args):
        if a == "--dept" and i + 1 < len(args):
            return args[i + 1].strip().lower()
        if a.startswith("--dept="):
            return a.split("=", 1)[1].strip().lower()
    return None


def confinable(rows: list[dict[str, Any]]) -> set[int]:
    """Pids this rule may confine: positively identified mining or audit work only (see
    MINER_SCRIPTS). Never a judge, live or protected process, never an unknown script."""
    by_pid = {int(r["pid"]): r for r in rows if r.get("pid") is not None}

    def born_before(parent: dict[str, Any], child: dict[str, Any]) -> bool:
        p, c = parent.get("create_time"), child.get("create_time")
        return isinstance(p, (int, float)) and isinstance(c, (int, float)) and p <= c

    out: set[int] = set()
    for pid, r in by_pid.items():
        if r.get("cls") not in RESTRICT:
            continue
        cur, seen, ok = r, 0, False
        while cur is not None and seen < 32:
            sc = _scripts(cur.get("cmdline"))
            if sc & PROTECTED_SCRIPTS:
                break                       # a money or clock organ, or a child of one
            if "department_resident.py" in sc and _dept(cur.get("cmdline")) in PROTECTED_DEPTS:
                break                       # the promotion / allocator department
            joined = " ".join(str(a) for a in (cur.get("cmdline") or [])).lower()
            if sc & MINER_SCRIPTS or AUDIT_MARK in joined:
                ok = True
                break
            parent = by_pid.get(int(cur.get("ppid") or 0))
            if parent is None or parent is cur or not born_before(parent, cur):
                break
            cur, seen = parent, seen + 1
        if ok:
            out.add(pid)
    return out


def decide(ncpu: int, *, demand: int, reserved_now: int, miner_busy: float | None,
           pace_doc: dict[str, Any], floor: int = FLOOR, ceiling: int = CEILING,
           miner_min: int = MINER_MIN) -> dict[str, Any]:
    """How many cores to reserve for the judge this tick, and why."""
    if demand <= 0:
        return {"reserve": 0, "mode": "IDLE", "why": "no judge process is working"}
    top = max(0, min(ceiling, demand, ncpu - miner_min))
    base = min(floor, top)
    if pace_doc.get("status") != "MEASURED":
        return {"reserve": base, "mode": "FLOOR", "why": "pace UNMEASURED: the floor only"}
    if not pace_doc.get("below_pace"):
        return {"reserve": base, "mode": "FLOOR", "why": "at or above pace: the floor only"}
    if top <= base:
        return {"reserve": base, "mode": "FLOOR",
                "why": "behind pace, but the judge's demand or the miners' minimum caps it here"}
    if not isinstance(miner_busy, (int, float)):
        return {"reserve": base, "mode": "FLOOR",
                "why": "behind pace, miners' load UNMEASURED: no borrowing on an unread load"}
    allowed = ncpu - reserved_now
    if miner_busy >= allowed - SATURATED:
        mode = "GIVING_BACK" if reserved_now > base else "FLOOR"
        return {"reserve": base, "mode": mode,
                "why": f"miners busy {miner_busy:.2f} of {allowed} allowed cores: they need them"}
    slack = allowed - miner_busy
    target = reserved_now + int(slack - SATURATED) if slack >= SLACK_BORROW else reserved_now
    reserve = min(max(target, base), top)
    return {"reserve": reserve, "mode": "BORROWING" if reserve > base else "FLOOR",
            "why": (f"behind pace; miners busy {miner_busy:.2f} of {allowed} allowed cores, "
                    f"{slack:.2f} idle")}


def cores_for(ncpu: int, reserve: int) -> tuple[list[int], list[int]]:
    """(reserved for the judge, allowed for the miners): the judge takes the highest CPUs."""
    reserve = max(0, min(reserve, ncpu))
    return list(range(ncpu - reserve, ncpu)), list(range(0, ncpu - reserve))


def _key(pid: Any, create_time: Any) -> str:
    return f"{int(pid)}:{create_time}"


def snapshot() -> list[dict[str, Any]]:
    """Every process with what the rule reads, by psutil only (never CIM). Never raises."""
    import psutil  # type: ignore[import-untyped,unused-ignore]

    attrs = ["pid", "ppid", "name", "cmdline", "create_time", "cpu_times", "nice"]
    if hasattr(psutil.Process, "cpu_affinity"):
        attrs.append("cpu_affinity")
    rows = []
    for p in psutil.process_iter(attrs, ad_value=None):
        info = p.info
        ct = info.get("cpu_times")
        rows.append({"pid": info.get("pid"), "ppid": info.get("ppid"),
                     "name": info.get("name") or "", "cmdline": info.get("cmdline"),
                     "create_time": info.get("create_time"), "nice": info.get("nice"),
                     "cpu_s": (float(ct.user + ct.system) if ct is not None else None),
                     "affinity": info.get("cpu_affinity")})
    return rows


def _default_setter(pid: int, cores: list[int], expect: dict[str, Any]) -> None:
    """Set one pid's affinity -- only if it is STILL the process the snapshot saw."""
    import psutil  # type: ignore[import-untyped,unused-ignore]

    p = psutil.Process(pid)
    if expect.get("create_time") is None or p.create_time() != expect.get("create_time"):
        raise LookupError("pid reused: start time differs from the snapshot")
    p.cpu_affinity(list(cores))


class Enforcer:
    """The reservation, re-decided every INTERVAL_S on a daemon thread of the judge's sweep."""

    def __init__(self, *, snap: Callable[[], list[dict[str, Any]]] | None = None,
                 setter: Callable[[int, list[int], dict[str, Any]], None] | None = None,
                 classify: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None = None,
                 ncpu: int | None = None, clock: Callable[[], float] = time.monotonic,
                 pace_reader: Callable[[], dict[str, Any]] | None = None,
                 report: Path = REPORT, state: Path = STATE,
                 owner: dict[str, Any] | None = None) -> None:
        self.snap = snap or snapshot
        self.setter = setter or _default_setter
        if classify is None:
            from scripts import judge_priority as jp
            classify = jp.classify
        self.classify = classify
        self.ncpu = int(ncpu or os.cpu_count() or 1)
        self.clock = clock
        self.pace_reader = pace_reader or (lambda: pace(floor_per_day=PACE_FLOOR_PER_DAY))
        self.report, self.state_path = report, state
        self.owner = owner or _own_identity()
        self.reserved = 0
        self.mode = "STARTING"
        self._cpu: dict[str, tuple[float, float]] = {}
        self._last_publish = -1e18
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last: dict[str, Any] = {}

    # ---------------------------------------------------------------- measurement
    def _busy(self, rows: list[dict[str, Any]], now: float) -> dict[str, float | None]:
        out: dict[str, float] = {}
        seen: dict[str, tuple[float, float]] = {}
        measured = bool(self._cpu)
        for r in rows:
            cpu = r.get("cpu_s")
            if not isinstance(cpu, (int, float)) or r.get("pid") is None:
                continue
            k = _key(r["pid"], r.get("create_time"))
            seen[k] = (float(cpu), now)
            prev = self._cpu.get(k)
            if prev is None or now <= prev[1]:
                continue
            out[r["cls"]] = out.get(r["cls"], 0.0) + max(0.0, cpu - prev[0]) / (now - prev[1])
        self._cpu = seen
        if not measured:
            return {"judge": None, "miner": None}
        return {"judge": round(sum(v for c, v in out.items() if c in JUDGE), 3),
                "miner": round(sum(v for c, v in out.items() if c in RESTRICT), 3)}

    # ---------------------------------------------------------------- state
    def _load_state(self) -> dict[str, Any]:
        st = _json(self.state_path)
        touched = st.get("touched")
        return {"owner": st.get("owner"), "touched": touched if isinstance(touched, dict) else {}}

    def _save_state(self, st: dict[str, Any]) -> None:
        with contextlib.suppress(OSError, TypeError, ValueError):
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.state_path.with_name(f"{self.state_path.name}.{os.getpid()}.tmp")
            tmp.write_text(json.dumps(st, indent=1), "utf-8")
            os.replace(tmp, self.state_path)

    # ---------------------------------------------------------------- one tick
    def tick(self) -> dict[str, Any]:
        cfg = settings()
        now = self.clock()
        rows = self.classify(self.snap())
        busy = self._busy(rows, now)
        demand = judge_demand(rows)
        pace_doc = self.pace_reader()
        st = self._load_state()
        owner = st.get("owner")
        if (isinstance(owner, dict) and owner.get("pid") != self.owner.get("pid")
                and _alive(owner, rows)):
            out = {"mode": "NOT_OWNER", "why": f"sweep pid {owner.get('pid')} owns the share"}
            self.last = out
            return out
        st["owner"] = self.owner
        d: dict[str, Any]
        if not cfg["enabled"]:
            d = {"reserve": 0, "mode": "DISABLED", "why": "JUDGE_CORE_SHARE=0"}
        else:
            d = decide(self.ncpu, demand=demand, reserved_now=self.reserved,
                       miner_busy=busy["miner"], pace_doc=pace_doc, floor=cfg["floor"],
                       ceiling=cfg["ceiling"], miner_min=cfg["miner_min"])
        reserve = int(d["reserve"])
        reserved_cores, allowed = cores_for(self.ncpu, reserve)
        changes = self._apply(rows, allowed, st, restore=reserve == 0)
        self._save_state(st)
        moved = reserve != self.reserved
        prev_reserve, self.reserved, self.mode = self.reserved, reserve, str(d["mode"])
        doc = {"schema": SCHEMA, "at": datetime.now(UTC).isoformat(timespec="seconds"),
               "host": os.environ.get("COMPUTERNAME") or "", "cores": self.ncpu,
               "floor": cfg["floor"], "ceiling": cfg["ceiling"], "miner_min": cfg["miner_min"],
               "mode": d["mode"], "why": d["why"], "reserved": reserve,
               "reserved_cores": reserved_cores, "miner_allowed_cores": len(allowed),
               "judge_demand": demand, "judge_busy_cores": busy["judge"],
               "miner_busy_cores": busy["miner"], "pace": pace_doc,
               "affinity_changes": len([c for c in changes if c.get("applied")]),
               "affinity_errors": [c for c in changes if c.get("error")][:10],
               "confined_processes": len(st["touched"]), "approval": APPROVAL,
               "rule": ("judge keeps every core; miners and audit lose the reserved cores; "
                        "live and the judge are never touched; no priority is changed")}
        self.last = doc
        if moved or now - self._last_publish >= PUBLISH_S:
            self._publish(doc, line=self._line(doc, prev_reserve) if moved else None)
            self._last_publish = now
        return doc

    def _apply(self, rows: list[dict[str, Any]], allowed: list[int], st: dict[str, Any], *,
               restore: bool) -> list[dict[str, Any]]:
        touched: dict[str, Any] = st["touched"]
        live_keys = {_key(r["pid"], r.get("create_time")) for r in rows
                     if r.get("pid") is not None}
        for k in [k for k in touched if k not in live_keys]:
            touched.pop(k)                       # the process is gone: nothing to restore
        changes = []
        allowed_set = set(allowed)
        mine = confinable(rows)
        for r in rows:
            if r.get("pid") is None:
                continue
            k0 = _key(r["pid"], r.get("create_time"))
            if int(r["pid"]) not in mine and not (restore and k0 in touched):
                continue
            cur = r.get("affinity")
            if not isinstance(cur, list) or not cur:
                continue                         # unreadable: never set what was not read
            k = _key(r["pid"], r.get("create_time"))
            rec = touched.get(k)
            prev = rec.get("prev") if isinstance(rec, dict) else None
            if restore:
                if not isinstance(prev, list):
                    continue
                want = sorted(prev)
            else:
                base = prev if isinstance(prev, list) else cur
                want = sorted(set(base) & allowed_set) or sorted(allowed_set)
            if sorted(cur) == want:
                if restore:
                    touched.pop(k, None)
                continue
            c: dict[str, Any] = {"pid": r["pid"], "cls": r["cls"], "from": sorted(cur),
                                 "to": want, "applied": False}
            try:
                self.setter(int(r["pid"]), want, r)
                c["applied"] = True
                if restore:
                    touched.pop(k, None)
                elif k not in touched:
                    touched[k] = {"pid": r["pid"], "create_time": r.get("create_time"),
                                  "prev": sorted(cur), "cls": r["cls"]}
            except Exception as exc:
                c["error"] = f"{type(exc).__name__}: {exc}"
            changes.append(c)
        return changes

    # ---------------------------------------------------------------- publication
    def _line(self, doc: dict[str, Any], prev_reserve: int) -> dict[str, Any]:
        now = datetime.now(UTC)
        return {"day": now.date().isoformat(), "at": now.isoformat(timespec="seconds"),
                "rail": RAIL, "kind": "opportunity_cost", "value": None,
                "verdict": UNMEASURED, "lost_s": None,
                "direction": "confine" if doc["reserved"] > prev_reserve else "release",
                "from_reserved": prev_reserve, "to_reserved": doc["reserved"],
                "mode": doc["mode"], "miner_busy_cores": doc["miner_busy_cores"],
                "miner_allowed_cores": doc["miner_allowed_cores"], "by": "judge_core_share",
                "units": "logical cores taken out of the miners' and audit's affinity",
                "why": (f"{doc['why']}; the miners' cost is bounded by their busy cores beside "
                        "their allowed cores; the E[log W] price is not measured")}

    def _publish(self, doc: dict[str, Any], line: dict[str, Any] | None) -> None:
        prior = _json(self.report).get("missed_growth")
        lines = [x for x in prior if isinstance(x, dict)] if isinstance(prior, list) else []
        if line is not None:
            lines.append(line)
        out = {**doc, "missed_growth": lines[-HISTORY:]}
        with contextlib.suppress(OSError, TypeError, ValueError):
            self.report.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.report.with_name(f"{self.report.name}.{os.getpid()}.tmp")
            tmp.write_text(json.dumps(out, indent=1, default=str), "utf-8")
            os.replace(tmp, self.report)

    # ---------------------------------------------------------------- lifecycle
    def release(self, why: str = "released") -> dict[str, Any]:
        """Give every confined process its recorded affinity back."""
        rows = self.classify(self.snap())
        st = self._load_state()
        changes = self._apply(rows, list(range(self.ncpu)), st, restore=True)
        st["owner"] = None
        self._save_state(st)
        prev, self.reserved, self.mode = self.reserved, 0, "RELEASED"
        doc = {"schema": SCHEMA, "at": datetime.now(UTC).isoformat(timespec="seconds"),
               "cores": self.ncpu, "mode": "RELEASED", "why": why, "reserved": 0,
               "reserved_cores": [], "miner_allowed_cores": self.ncpu,
               "affinity_changes": len([c for c in changes if c.get("applied")]),
               "affinity_errors": [c for c in changes if c.get("error")][:10],
               "confined_processes": len(st["touched"]), "approval": APPROVAL}
        line = self._line({**doc, "miner_busy_cores": None}, prev) if prev else None
        self._publish(doc, line)
        self.last = doc
        return doc

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception as exc:              # a report: never a reason the judge stops
                self.last = {"mode": "ERROR", "why": f"{type(exc).__name__}: {exc}"}
            self._stop.wait(settings()["interval_s"])

    def start(self) -> Enforcer:
        self._thread = threading.Thread(target=self._loop, name="judge-core-share", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=30)
        with contextlib.suppress(Exception):
            self.release("the sweep ended")


def _own_identity() -> dict[str, Any]:
    ct: float | None = None
    with contextlib.suppress(Exception):
        import psutil  # type: ignore[import-untyped,unused-ignore]
        ct = psutil.Process(os.getpid()).create_time()
    return {"pid": os.getpid(), "create_time": ct}


def _alive(owner: dict[str, Any], rows: list[dict[str, Any]]) -> bool:
    return any(r.get("pid") == owner.get("pid") and r.get("create_time") == owner.get("create_time")
               for r in rows)


def start_for_sweep() -> Enforcer | None:
    """The sweep's entry point: the Windows judging box only (the rule is about its 18 cores;
    `JUDGE_CORE_SHARE_ANY_OS=1` allows another OS). Never raises."""
    if sys.platform != "win32" and os.environ.get("JUDGE_CORE_SHARE_ANY_OS") != "1":
        return None
    try:
        return Enforcer().start()
    except Exception:
        return None


def release_orphaned(enforcer: Enforcer | None = None) -> dict[str, Any]:
    """Restore the miners when the sweep that confined them is gone (called hourly from
    `judging_throughput.run`). Never raises."""
    try:
        st = _json(STATE if enforcer is None else enforcer.state_path)
        touched = st.get("touched")
        if not isinstance(touched, dict) or not touched:
            return {"status": "NOTHING_CONFINED"}
        e = enforcer or Enforcer(owner={"pid": None, "create_time": None})
        rows = e.classify(e.snap())
        owner = st.get("owner")
        if isinstance(owner, dict) and _alive(owner, rows):
            return {"status": "OWNER_ALIVE", "owner": owner.get("pid")}
        doc = e.release("the sweep that confined the miners is gone")
        return {"status": "RELEASED", "affinity_changes": doc.get("affinity_changes")}
    except Exception as exc:
        return {"status": "FAILED", "why": f"{type(exc).__name__}: {exc}"}
