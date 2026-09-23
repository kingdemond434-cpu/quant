"""THE DESK'S COMPONENT REGISTRY -- every executable organ, DERIVED, never hand-listed.

    DESIRED STATE - OBSERVED STATE = RECONCILIATION WORK

This module is the DESIRED half. It answers, for every executable thing this desk owns, the
questions the reconciler has to ask: when must it run, what does it consume, what does it own,
who reads that, how long may it be silent, what proves it is making progress, and what repairs it.

NOTHING HERE IS A LIST SOMEONE MAINTAINS. A maintained list drifts the first week and lies the
second -- which is exactly what `clock_fixer.RESIDENTS`, `moat_swarms.TASK_NAMES`,
`forests.FOREST_TASKS` and `box_tasks.manifest` were: four registries of the same machine, each
true about a different subset. The specs are DERIVED from the places the desk already declares
work:

    hourly legs      desks/mt5/research/hourly_cycle.py  (LEG_DEPARTMENT, LEG_BUDGET_SEC, the
                     _costed/_producer call sites, read from the source)
    daily steps      desks/mt5/research/daily_cycle.py   (STEPS)
    box tasks        desks/mt5/ops/box_tasks.manifest    (name/trigger/runs/installer/lane)
    residents        the departments of hourly_cycle, the forests of libs/research/forests and
                     the swarms of moat_swarms -- the three families that run 24/7
    VPS timers       ops/quant-*.timer plus their .service
    federation       libs/research/external_federation (its workers register HERE; the roster is
                     never re-declared in this file)
    everything else  a DECLARED spec per executable file, with its unknowns named UNMEASURED

so a new leg joins the registry the moment it joins a clock, and an executable that joins neither
is COUNTABLE (`scripts/check_component_registry.py` ratchets that count down) instead of invisible.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops.control_plane.specs import (  # noqa: E402
    UNMEASURED,
    ComponentSpec,
    Registry,
    derive_max_silence,
)

MANIFEST = DESK / "ops" / "box_tasks.manifest"
HOURLY = DESK / "research" / "hourly_cycle.py"
DAILY = DESK / "research" / "daily_cycle.py"
RESIDENT = DESK / "research" / "department_resident.py"
SWARMS = DESK / "research" / "moat_swarms.py"
LEDGER = ROOT / "docs" / "research" / "tier1_program.json"

#: The areas the birth fence walks. An executable outside them is not this desk's to schedule.
EXECUTABLE_AREAS: tuple[str, ...] = ("desks/mt5/research", "desks/mt5/scripts", "desks/mt5/moat",
                                     "desks/mt5/ops", "scripts", "libs/ops")

#: The keep-alive cadence every 24/7 resident's task fires on (manifest: "every 10 minutes").
RESIDENT_KEEPALIVE_S = 600
#: One department pass's ceiling (department_resident.PASS_TIMEOUT_S default).
DEPT_PASS_TIMEOUT_S = 10_800
#: One moat swarm pass's ceiling (moat_swarms PASS_BUDGET_S + GRACE_S defaults).
SWARM_PASS_TIMEOUT_S = 1_920

_TASK_LINE = re.compile(r"^TASK\s+(.*)$")
_KV = re.compile(r'(\w+)="([^"]*)"')


# ------------------------------------------------------------------- cadence, in one place
def cadence_from_trigger(trigger: str) -> int | None:
    """Seconds between firings, read from the manifest's own plain-words trigger.

    UNDECLARED STAYS UNDECLARED. `check_box_tasks.py` ratchets the count of triggers this repo
    does not know precisely because nobody may invent one, and a cadence invented here would be
    laundered into an SLA that looks measured. None is the honest answer and the reconciler
    reports it as UNMEASURED.
    """
    t = str(trigger or "").strip().lower()
    if not t or t.startswith("undeclared"):
        return None
    m = re.search(r"every\s+(\d+)\s*(second|minute|hour|day)", t)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        return n * {"second": 1, "minute": 60, "hour": 3600, "day": 86400}[unit]
    if "keep-alive" in t or "at startup + every" in t:
        return RESIDENT_KEEPALIVE_S
    if t.startswith("hourly") or "every hour" in t:
        return 3600
    if t.startswith("daily") or "daily " in t:
        return 86_400
    if "continuous loop" in t or "resident" in t or t.startswith("at system start-up"):
        return RESIDENT_KEEPALIVE_S
    if t.startswith("at startup"):
        return None
    return None


def _camel(name: str) -> str:
    return "".join(part.capitalize() for part in str(name).split("_") if part)


# ----------------------------------------------------------------- the hourly cycle's legs
@lru_cache(maxsize=1)
def _hourly_module() -> Any:
    """`hourly_cycle` loaded BY PATH, so this module works from the repo root and from the desk.

    Imported rather than regex-scraped for the two tables that are built programmatically
    (`LEG_DEPARTMENT` composes `dict.fromkeys` calls with a comprehension over the forest ids;
    `LEG_BUDGET_SEC` likewise), because a regex over those would silently miss the forests --
    fifteen legs -- and a registry that misses the newest fifteen legs is the drift it exists to
    end. It is import-safe: everything in that file sits under `if __name__ == "__main__"`.
    """
    try:
        spec = importlib.util.spec_from_file_location("_cp_hourly_cycle", HOURLY)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


@lru_cache(maxsize=1)
def _hourly_source() -> str:
    try:
        return HOURLY.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


@lru_cache(maxsize=1)
def _producer_calls() -> dict[str, tuple[str, tuple[str, ...]]]:
    """leg -> (script path, production args), read from the `_producer(...)` call sites by AST.

    AST rather than regex: the calls are written three ways (direct, inside a lambda, with the
    args as a tuple) and a regex that handles two of them quietly drops the third.
    """
    out: dict[str, tuple[str, tuple[str, ...]]] = {}
    try:
        tree = ast.parse(_hourly_source())
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id != "_producer" or len(node.args) < 2:
            continue
        name, script = node.args[0], node.args[1]
        if not (isinstance(name, ast.Constant) and isinstance(name.value, str)):
            continue
        if not (isinstance(script, ast.Constant) and isinstance(script.value, str)):
            continue
        args: list[str] = []
        for a in node.args[2:]:
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                args.append(a.value)
            elif isinstance(a, (ast.Tuple, ast.List)):
                args.extend(e.value for e in a.elts
                            if isinstance(e, ast.Constant) and isinstance(e.value, str))
        out[name.value] = (script.value, tuple(args))
    return out


@lru_cache(maxsize=1)
def _ledger_outputs() -> dict[str, dict[str, str]]:
    """leg -> {artifact, consumer}, from the Tier-1 ledger's own `scheduled_by` claims.

    The ledger is already the desk's declaration of what a leg OWNS and who reads it (the same
    source `hourly_cycle._leg_artifacts` uses for the provenance envelope), so reading it here
    keeps one declaration instead of minting a second that can disagree with it.
    """
    out: dict[str, dict[str, str]] = {}
    try:
        doc = json.loads(LEDGER.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return out
    for it in doc.get("items", []):
        sched, art = str(it.get("scheduled_by") or ""), str(it.get("artifact") or "")
        if not art or "hourly_cycle:" not in sched:
            continue
        for tok in sched.split(","):
            tok = tok.strip()
            if tok.startswith("hourly_cycle:"):
                leg = tok.split(":", 1)[1].split()[0]
                out.setdefault(leg, {"artifact": art,
                                     "consumer": str(it.get("consumer") or UNMEASURED)})
    return out


def leg_names() -> list[str]:
    """Every costed leg of the hourly cycle, read from its own source."""
    return sorted(set(re.findall(r'_costed\("([^"]+)"', _hourly_source())))


def hourly_leg_specs() -> list[ComponentSpec]:
    """One spec per hourly leg. Cadence is the cycle's own hour; the budget is the leg's."""
    mod = _hourly_module()
    dept = dict(getattr(mod, "LEG_DEPARTMENT", {}) or {})
    budget = dict(getattr(mod, "LEG_BUDGET_SEC", {}) or {})
    default_budget = int(getattr(mod, "SEARCH_BUDGET_SEC", 720) or 720)
    producers = _producer_calls()
    ledger = _ledger_outputs()
    specs: list[ComponentSpec] = []
    for leg in leg_names():
        department = dept.get(leg, "rest")
        script, args = producers.get(leg, ("", ()))
        code = ["desks/mt5/research/hourly_cycle.py"]
        if script:
            for root in (DESK, ROOT):
                cand = root / script
                if cand.exists():
                    code.append(cand.resolve().relative_to(ROOT).as_posix())
                    break
        timeout = int(budget.get(leg, default_budget))
        decl = ledger.get(leg, {})
        specs.append(ComponentSpec(
            component_id=f"leg:{leg}",
            kind="leg", host="box", code_paths=tuple(dict.fromkeys(code)),
            outputs=(str(decl["artifact"]),) if decl.get("artifact") else (),
            consumers=(str(decl["consumer"]),) if decl.get("consumer") else (),
            dependencies=(f"resident:dept_{department}",),
            cadence_s=3600, timeout_s=timeout,
            progress_metric="leg_completions",
            production_args=args,
            expected_artifact_schema=decl.get("artifact") or UNMEASURED,
            owner=f"department:{department}",
            restart_action=f"restart:resident:dept_{department}",
            criticality="optional",
            resource_budget={"budget_s": timeout, "cpu": "below_normal"},
            schedule=f"hourly_cycle:{leg}",
            artifact_class="hourly",
            notes=f"department {department}"))
    return specs


# -------------------------------------------------------------------- the daily cycle's steps
@lru_cache(maxsize=1)
def daily_step_names() -> tuple[str, ...]:
    try:
        src = DAILY.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ()
    m = re.search(r"^STEPS\s*=\s*\((.*?)\n\n", src, re.S | re.M)
    body = m.group(1) if m else src
    return tuple(dict.fromkeys(re.findall(r'\(\s*"([a-z0-9_]+)"\s*,\s*_', body)))


def daily_step_specs() -> list[ComponentSpec]:
    return [ComponentSpec(
        component_id=f"daily:{step}",
        kind="daily_step", host="box",
        code_paths=("desks/mt5/research/daily_cycle.py",),
        cadence_s=86_400, timeout_s=3_600,
        progress_metric="daily_step_completions",
        owner="daily_cycle", restart_action="restart:task:MT5-Daily",
        criticality="optional",
        resource_budget={"budget_s": 3600},
        schedule="MT5-Daily", artifact_class="daily",
        notes="one step of the midnight chain; the stamp is step-aware, so a new step self-heals")
        for step in daily_step_names()]


# ------------------------------------------------------------------------- the box's tasks
def manifest_rows(path: Path | None = None) -> list[dict[str, str]]:
    p = path or MANIFEST
    rows: list[dict[str, str]] = []
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return rows
    for line in text.splitlines():
        m = _TASK_LINE.match(line.strip())
        if m:
            rows.append(dict(_KV.findall(m.group(1))))
    return rows


#: Lanes whose failure costs MONEY or the desk's ability to know it is broken. These are the only
#: `required` box tasks: a research task that misses an hour costs an hour of research.
REQUIRED_LANES: frozenset[str] = frozenset({"money"})
#: Tasks that are required whatever their lane, because the control plane itself rides on them.
REQUIRED_TASKS: frozenset[str] = frozenset({"MT5-ClockFixer", "MT5-Gateway", "MT5-AdoptRelease"})


def manifest_task_specs(path: Path | None = None) -> list[ComponentSpec]:
    """One spec per manifest task. Several manifest lines can share a name (MT5-CostState runs
    three scripts); they collapse to one component owning three code paths, which is what the
    scheduler actually holds."""
    by_name: dict[str, dict[str, Any]] = {}
    for row in manifest_rows(path):
        name = row.get("name") or ""
        if not name:
            continue
        cur = by_name.setdefault(name, {"runs": [], "trigger": row.get("trigger", UNMEASURED),
                                        "installer": row.get("installer", "NONE"),
                                        "lane": row.get("lane", UNMEASURED)})
        runs = row.get("runs") or ""
        if runs and runs != "UNKNOWN" and (ROOT / runs).exists():
            cur["runs"].append(runs)
    out: list[ComponentSpec] = []
    for name, row in sorted(by_name.items()):
        cadence = cadence_from_trigger(row["trigger"])
        required = name in REQUIRED_TASKS or row["lane"] in REQUIRED_LANES
        out.append(ComponentSpec(
            component_id=f"task:{name}",
            kind="task", host="box",
            code_paths=tuple(dict.fromkeys(row["runs"])),
            cadence_s=cadence,
            timeout_s=None,
            progress_metric="task_runs",
            owner=f"lane:{row['lane']}",
            restart_action=f"restart:task:{name}",
            criticality="required" if (required and cadence) else "optional",
            resource_budget={},
            schedule=name,
            artifact_class=_class_for_cadence(cadence),
            notes=f"trigger={row['trigger']!r} installer={row['installer']}"))
    return out


def _class_for_cadence(cadence_s: int | None) -> str:
    if cadence_s is None:
        return UNMEASURED
    if cadence_s <= 300:
        return "minute"
    if cadence_s <= 900:
        return "fifteen_minute"
    if cadence_s <= 3_600:
        return "hourly"
    if cadence_s <= 86_400:
        return "daily"
    return "weekly"


# -------------------------------------------------------------------------- the 24/7 residents
#: THE TASK-NAME PREFIXES ARE BUILT, NEVER WRITTEN (the rule `libs/research/forests.py` states
#: for its own): `scripts/check_box_tasks.py` reads every CamelCase task literal in the tree as
#: a task reference the manifest must cover, and a truncated prefix stem matches nothing there.
DEPT_TASK_PREFIX = "MT5-" + "Dept-"
FOREST_TASK_PREFIX = "MT5-" + "Forest-"


@lru_cache(maxsize=1)
def forests_module() -> Any:
    try:
        from libs.research import forests
    except Exception:
        return None
    return forests


def _forest_ids() -> tuple[str, ...]:
    f = forests_module()
    return tuple(getattr(f, "OWN_RESIDENT", ()) or ()) if f else ()


def _forest_task(fid: str) -> str:
    f = forests_module()
    if f is None:
        return FOREST_TASK_PREFIX + _camel(fid)
    return str(getattr(f, "FOREST_TASKS", {}).get(fid) or FOREST_TASK_PREFIX + _camel(fid))


@lru_cache(maxsize=1)
def swarm_tasks() -> dict[str, str]:
    """moat_swarms.TASK_NAMES, read from its source without importing the swarm runtime."""
    try:
        src = SWARMS.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    m = re.search(r"TASK_NAMES:\s*dict\[str,\s*str\]\s*=\s*\{(.*?)\}", src, re.S)
    if not m:
        return {}
    return dict(re.findall(r'"([a-z_]+)"\s*:\s*"([A-Za-z0-9-]+)"', m.group(1)))


def department_names() -> tuple[str, ...]:
    mod = _hourly_module()
    return tuple(getattr(mod, "DEPARTMENTS", ()) or ())


def department_task(dept: str) -> str:
    """The keep-alive task of one department's resident.

    `discovery` rides MT5-Hourly -- the box's original research task, kept because retiring a task
    name that `stall_watch.ps1` heals by name is how a resident stops being restarted.
    """
    if dept == "discovery":
        return "MT5-Hourly"
    if dept in _forest_ids():
        return _forest_task(dept)
    return DEPT_TASK_PREFIX + _camel(dept)


@lru_cache(maxsize=1)
def _manifest_triggers() -> dict[str, str]:
    """task name -> the manifest's trigger. MEASURED BEATS DERIVED: the manifest's 2026-09-16
    block was read off the box with `schtasks /Query`, so where it knows a resident's trigger
    (MT5-Hourly fires hourly, not on the ten-minute keep-alive the other residents use) that
    reading wins over this module's default."""
    return {r["name"]: r.get("trigger", UNMEASURED) for r in manifest_rows() if r.get("name")}


def _resident_clock(task: str, default_s: int) -> tuple[int | None, str]:
    """(cadence, trigger words) for one resident's keep-alive task."""
    trigger = _manifest_triggers().get(task)
    if trigger and trigger != UNMEASURED:
        return cadence_from_trigger(trigger), trigger
    return default_s, "at startup + every 10 minutes (keep-alive of a 24/7 resident)"


def resident_specs() -> list[ComponentSpec]:
    """The three families that run 24/7: departments, forests and moat swarms.

    MAX SILENCE IS PER FAMILY, DERIVED. The clock fixer carried a flat four hours for all of
    them. A department's pass may legitimately run three hours (so four hours was almost no
    margin) and a swarm's is capped at thirty-two minutes (so four hours was eight times too
    long, and a dead swarm sat unnoticed for most of a shift). Both now come from
    `derive_max_silence(keep-alive cadence, that family's own pass ceiling)`.
    """
    out: list[ComponentSpec] = []
    for dept in department_names():
        task = department_task(dept)
        cadence, trigger = _resident_clock(task, RESIDENT_KEEPALIVE_S)
        out.append(ComponentSpec(
            component_id=f"resident:dept_{dept}",
            kind="resident", host="box",
            code_paths=("desks/mt5/research/department_resident.py",),
            outputs=(f"desks/mt5/data/locks/dept_{dept}.lock",),
            consumers=("libs/moat/registry.py: worker_heartbeat",),
            dependencies=("desks/mt5/research/hourly_cycle.py",),
            cadence_s=cadence, timeout_s=DEPT_PASS_TIMEOUT_S,
            max_silence_s=derive_max_silence(cadence, DEPT_PASS_TIMEOUT_S),
            progress_metric="passes",
            production_args=("--dept", dept),
            expected_artifact_schema="desks/mt5/logs/" + task + ".log",
            owner=f"department:{dept}",
            restart_action=f"restart:task:{task}",
            criticality="required",
            resource_budget={"min_free_mb": 4096, "cpu": "below_normal",
                             "pass_timeout_s": DEPT_PASS_TIMEOUT_S},
            schedule=task, artifact_class="fifteen_minute",
            notes=(f"24/7 singleton; trigger={trigger!r} -- a keep-alive is a no-op while it "
                   f"lives")))
    for swarm, task in sorted(swarm_tasks().items()):
        cadence, trigger = _resident_clock(task, RESIDENT_KEEPALIVE_S)
        out.append(ComponentSpec(
            component_id=f"resident:moat_{swarm}",
            kind="resident", host="box",
            code_paths=("desks/mt5/research/moat_swarms.py",),
            outputs=(f"desks/mt5/data/locks/moat_{swarm}.lock",
                     "desks/mt5/reports/MOAT_SWARMS.json"),
            cadence_s=cadence, timeout_s=SWARM_PASS_TIMEOUT_S,
            max_silence_s=derive_max_silence(cadence, SWARM_PASS_TIMEOUT_S),
            progress_metric="passes",
            production_args=("--swarm", swarm),
            owner="moat", restart_action=f"restart:task:{task}",
            criticality="required",
            resource_budget={"min_free_mb": 4096, "pass_budget_s": SWARM_PASS_TIMEOUT_S},
            schedule=task, artifact_class="fifteen_minute",
            notes=(f"one of the three concurrent moat swarms; trigger={trigger!r}")))
    return out


def residents() -> dict[str, tuple[str, str, int]]:
    """`clock_fixer.RESIDENTS` in its own shape: lock stem -> (task, log, max silence seconds).

    THE FIXER NO LONGER OWNS THIS MAP. It owned a hand-written copy of it that had to be edited
    every time a department, a forest or a swarm was added -- and the drift test in
    `desks/mt5/tests/test_control_plane_organ.py` exists because that edit was forgotten twice.
    """
    out: dict[str, tuple[str, str, int]] = {}
    for s in resident_specs():
        stem = s.component_id.split(":", 1)[1]
        task = s.schedule
        silence = s.max_silence_s or derive_max_silence(RESIDENT_KEEPALIVE_S,
                                                        DEPT_PASS_TIMEOUT_S) or 11_400
        out[stem] = (task, f"{task}.log", int(silence))
    return out


# ------------------------------------------------------------------------------- VPS timers
_TIMER_EXEC = re.compile(r"^ExecStart=\S*?(?:python\S*\s+)?(\S+\.py)", re.M)
_TIMER_TIMEOUT = re.compile(r"^TimeoutStartSec=(\d+)", re.M)
_ON_ACTIVE = re.compile(r"^OnUnitActiveSec=(\d+)(s|m|h|min|sec|hour)?", re.M)
_ON_CAL = re.compile(r"^OnCalendar=(.+)$", re.M)


def _seconds(n: int, unit: str | None) -> int:
    return n * {"s": 1, "sec": 1, "m": 60, "min": 60, "h": 3600, "hour": 3600}.get(unit or "s", 1)


def timer_specs(root: Path | None = None) -> list[ComponentSpec]:
    """One spec per VPS systemd timer, with its cadence and its unit's script."""
    base = root or ROOT
    out: list[ComponentSpec] = []
    for timer in sorted((base / "ops").glob("quant-*.timer")):
        unit = timer.stem
        try:
            ttext = timer.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        service = timer.with_suffix(".service")
        stext = _read_text(service)
        cadence: int | None = None
        m = _ON_ACTIVE.search(ttext)
        if m:
            cadence = _seconds(int(m.group(1)), m.group(2))
        elif _ON_CAL.search(ttext):
            cal = _ON_CAL.search(ttext)
            cadence = 86_400 if cal and "*-*-*" in cal.group(1) else None
        scripts = [s for s in _TIMER_EXEC.findall(stext) if (base / s).exists()]
        to = _TIMER_TIMEOUT.search(stext)
        out.append(ComponentSpec(
            component_id=f"timer:{unit}",
            kind="timer", host="vps",
            code_paths=tuple(dict.fromkeys(scripts)),
            cadence_s=cadence, timeout_s=int(to.group(1)) if to else None,
            progress_metric="timer_runs",
            owner="vps", restart_action=f"systemctl --user restart {unit}.timer",
            criticality="optional",
            resource_budget={},
            schedule=unit, artifact_class=_class_for_cadence(cadence),
            notes="VPS systemd user timer; quant-unit-health copies it into place every 10 min"))
    return out


# --------------------------------------------------------------- the federation's workers
def federation_worker_specs() -> list[ComponentSpec]:
    """The open-source research federation's workers, registered HERE rather than re-declared.

    LAWS 5h gives each external system a disposition, and DIRECT / WRAPPED / REBUILT put it on a
    clock -- which makes it an executable organ of this desk and therefore a component. The
    roster, the dispositions and the operational conjunction all come from
    `libs/research/external_federation`; this function adds nothing to them but a ComponentSpec.
    """
    try:
        from libs.research import external_federation as fed
    except Exception:
        return []
    state_path = DESK / "data" / "external_federation.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        state = {}
    rows = state.get("systems") if isinstance(state, dict) else None
    disposition: dict[str, str] = {}
    if isinstance(rows, dict):
        for sid, row in rows.items():
            if isinstance(row, dict) and row.get("disposition"):
                disposition[str(sid)] = str(row["disposition"])
    elif isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and row.get("system_id") and row.get("disposition"):
                disposition[str(row["system_id"])] = str(row["disposition"])
    out: list[ComponentSpec] = []
    for sid, disp in sorted(disposition.items()):
        if disp not in getattr(fed, "RUNNING_DISPOSITIONS", frozenset()):
            continue
        out.append(ComponentSpec(
            component_id=f"federation:{sid}",
            kind="federation_worker", host="box",
            code_paths=("desks/mt5/research/external_federation.py",),
            outputs=(f"desks/mt5/data/intelligence/external_federation/{sid}.json",),
            consumers=("leg:compile_candidates",),
            cadence_s=3_600, timeout_s=getattr(fed, "FEDERATION_BUDGET_S", 3_600),
            progress_metric="packets_drained",
            owner="external_federation", restart_action="restart:resident:dept_intel",
            criticality="optional",
            resource_budget={"budget_s": getattr(fed, "FEDERATION_BUDGET_S", 3_600)},
            schedule="hourly_cycle:external_federation", artifact_class="hourly",
            notes=f"disposition {disp}; an external engine is a researcher, never a validator"))
    return out


# ------------------------------------------------------------------------ explicit specs
def explicit_specs() -> list[ComponentSpec]:
    """The components that exist because the CONTROL PLANE exists, declared by hand because
    nothing else declares them."""
    return [
        ComponentSpec(
            component_id="component:control_plane",
            kind="task", host="box",
            code_paths=("desks/mt5/research/control_plane.py",
                        "libs/ops/control_plane/reconciler.py"),
            inputs=("desks/mt5/data/watermarks/", "desks/mt5/data/lineage.sqlite"),
            outputs=("desks/mt5/reports/CONTROL_PLANE.json",),
            consumers=("scripts/check_closed_loop.py", "desks/mt5/research/clock_fixer.py"),
            cadence_s=900, timeout_s=720,
            progress_metric="reconcile_passes",
            production_args=("--once", "--budget-s", "600"),
            expected_artifact_schema="desks/mt5/reports/CONTROL_PLANE.json",
            owner="meta", restart_action="restart:task:MT5-ClockFixer",
            criticality="required",
            resource_budget={"budget_s": 720},
            schedule="MT5-ClockFixer", artifact_class="fifteen_minute",
            notes="the reconciler; the observe pass also runs as hourly leg control_plane"),
    ]


# ------------------------------------------------------------------- everything else, named
def executables(root: Path | None = None) -> list[str]:
    """Every executable python file under the walked areas, repo-relative.

    EXECUTABLE means it can be put on a clock: a `__main__` block, an argparse parser, or a
    `main()`. A library module cannot be scheduled and is judged by REACH elsewhere
    (`wiring_ceo.library_reach`), never by clock.
    """
    base = root or ROOT
    out: list[str] = []
    for area in EXECUTABLE_AREAS:
        d = base / area
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*.py")):
            # `_retired/` holds files a session retired with a row in docs/research/
            # retirements.jsonl; they are kept for the record and are not this desk's to run.
            if "__pycache__" in p.parts or "_retired" in p.parts or p.name.startswith("_"):
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if '__main__' in text or "argparse" in text or re.search(r"^def main\(", text, re.M):
                out.append(p.relative_to(base).as_posix())
    return sorted(set(out))


def discovered_specs(claimed: set[str], root: Path | None = None) -> list[ComponentSpec]:
    """A DECLARED spec for every executable no clock claims.

    This is not padding. It is the honest half of "100% component coverage": the desk knows the
    file exists, knows nothing schedules it, and says so by name -- cadence None, schedule
    UNMEASURED, criticality optional -- instead of the file being invisible to the reconciler.
    `scripts/check_component_registry.py` counts these and ratchets the count DOWN.
    """
    out: list[ComponentSpec] = []
    for rel in executables(root):
        if rel in claimed:
            continue
        out.append(ComponentSpec(
            component_id=f"exe:{rel}",
            kind="executable", host="any",
            code_paths=(rel,),
            cadence_s=None, timeout_s=None,
            progress_metric=UNMEASURED,
            owner=UNMEASURED, restart_action=UNMEASURED,
            criticality="optional",
            resource_budget={},
            schedule=UNMEASURED, artifact_class=UNMEASURED,
            notes="DECLARED: executable with no clock in this repository"))
    return out


# ------------------------------------------------- the VPS crontab, the law gate, the hooks
CRONTAB = ROOT / "ops" / "crontab.manifest"
LAW_GATE = ROOT / "scripts" / "run_law_gate.py"
#: Files that run on a git event rather than a timer: every commit and every push is a trigger.
HOOK_FILES: tuple[str, ...] = ("ops/githooks/pre-commit", "ops/githooks/pre-push", "ops/gates.sh")
_CRON_LINE = re.compile(r"^([-*/,\d]+)\s+([-*/,\d]+)\s+\S+\s+\S+\s+\S+\s+(.*)$")
_PATH_REF = re.compile(r"(?<![\w/\\.-])((?:desks|scripts|libs|ops|deploy|research|mt5desk|moat)"
                       r"[/\\][\w./\\-]+?\.(?:py|sh|ps1|cmd))(?![\w.])")
_MODULE_REF = re.compile(r"-m\s+([A-Za-z_][\w.]*)")
_FENCE_REF = re.compile(r'\(\s*"(check_[\w]+\.py)"\s*,')


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _cron_cadence(minute: str, hour: str) -> int | None:
    """Seconds between firings for the two fields that decide it; None when unreadable."""
    m = re.fullmatch(r"\*/(\d+)", minute)
    if m and hour == "*":
        return int(m.group(1)) * 60
    if minute == "*" and hour == "*":
        return 60
    h = re.fullmatch(r"\*/(\d+)", hour)
    if h:
        return int(h.group(1)) * 3600
    if hour == "*":
        return 3600
    if re.fullmatch(r"\d+(,\d+)*", hour):
        return 86_400 // max(1, hour.count(",") + 1)
    return None


@lru_cache(maxsize=1 << 16)
def _named_path(rel: str, base_s: str) -> str | None:
    """One candidate path, resolved against the root and the desk -- or None if no such file.

    MEMOISED, and the reason is measured: the reach closure grew from a handful of clock texts
    to every organ a clock reaches, the same paths recur in hundreds of files, and `Path.resolve`
    is a syscall-heavy call on Windows. Without this the registry build took 216 s on the box
    and timed out inside a test; with it, seconds.
    """
    base = Path(base_s)
    for prefix in (base, base / "desks" / "mt5"):
        cand = prefix / rel
        if cand.is_file():
            return cand.resolve().relative_to(base.resolve()).as_posix()
    return None


def scripts_named_in(text: str, root: Path | None = None) -> list[str]:
    """Repo-relative files a clock text or wrapper names: path literals (either slash) and
    `-m dotted.module`, resolved against the repo root and the desk, existing files only."""
    base_s = str(root or ROOT)
    out: list[str] = []
    for raw in _PATH_REF.findall(text):
        hit = _named_path(raw.replace("\\", "/"), base_s)
        if hit:
            out.append(hit)
    for dotted in _MODULE_REF.findall(text):
        hit = _named_path(dotted.replace(".", "/") + ".py", base_s)
        if hit:
            out.append(hit)
    return list(dict.fromkeys(out))


def cron_specs(root: Path | None = None) -> list[ComponentSpec]:
    """One spec per live crontab line of the VPS (ops/crontab.manifest), owning the scripts the
    line runs and the scripts its shell wrappers run. The manifest IS the VPS's clock
    (check_scheduler_manifest keeps it honest against the live crontab)."""
    base = root or ROOT
    out: list[ComponentSpec] = []
    for no, line in enumerate(_read_text(base / "ops" / "crontab.manifest").splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#") or s[0] not in "*0123456789@":
            continue
        m = _CRON_LINE.match(s)
        if not m:
            continue
        minute, hour, cmd = m.group(1), m.group(2), m.group(3)
        scripts = scripts_named_in(cmd, base)
        # a wrapper (ops/run_x.sh) runs the scripts it names; they are on this clock too
        for wrapper in [p for p in scripts if p.endswith((".sh", ".cmd", ".ps1"))]:
            scripts += [p for p in scripts_named_in(_read_text(base / wrapper), base)
                        if p not in scripts]
        if not scripts:
            continue
        cadence = _cron_cadence(minute, hour)
        out.append(ComponentSpec(
            component_id=f"cron:{no}:{Path(scripts[0]).stem}",
            kind="timer", host="vps", code_paths=tuple(dict.fromkeys(scripts)),
            cadence_s=cadence, timeout_s=None, progress_metric="cron_runs",
            owner="vps", restart_action="crontab (ops/crontab.manifest, applied by hand)",
            criticality="optional", resource_budget={},
            schedule=f"crontab:{no}", artifact_class=_class_for_cadence(cadence),
            notes=f"ops/crontab.manifest line {no}: {minute} {hour} ..."))
    return out


_SYSTEMD_LINE = re.compile(r'^SYSTEMD\s+unit="([^"]+)"\s+on="([^"]*)"\s+exec="([^"]+)"')


def _systemd_cadence(on: str) -> int | None:
    """Seconds between firings for a systemd OnCalendar/OnUnitActiveSec expression, or None."""
    m = re.search(r"OnUnitActiveSec=(\d+)", on)
    if m:
        return int(m.group(1))
    m = re.search(r"\*:(?:\*/(\d+)|\d+)", on)          # *-*-* *:05:00 or *:*/15:00
    if m:
        return int(m.group(1)) * 60 if m.group(1) else 3_600
    hours = re.search(r"\s((?:\d{2})(?:,\d{2})*):\d{2}:\d{2}", on)
    if hours:
        return 86_400 // max(1, hours.group(1).count(",") + 1)
    if on.strip():
        return 86_400 * 30 if on.strip().startswith("*-*-01") else 86_400
    return None


def systemd_manifest_specs(root: Path | None = None) -> list[ComponentSpec]:
    """One spec per SYSTEMD unit the VPS manifest declares (`ops/crontab.manifest`).

    `cron_specs` reads the five-field cron lines and skips these, so eighty-eight declared units
    -- `quant-x-deepmine.timer` among them -- owned a script the census then called unclocked.
    The manifest IS the VPS's clock (check_scheduler_manifest keeps it honest against the live
    crontab), and a unit line names its ExecStart the same way a cron line does.
    """
    base = root or ROOT
    out: list[ComponentSpec] = []
    for no, line in enumerate(_read_text(base / "ops" / "crontab.manifest").splitlines(), 1):
        m = _SYSTEMD_LINE.match(line.strip())
        if not m:
            continue
        unit, on, exec_s = m.group(1), m.group(2), m.group(3)
        scripts = scripts_named_in(exec_s, base)
        for wrapper in [p for p in scripts if p.endswith((".sh", ".cmd", ".ps1"))]:
            scripts += [p for p in scripts_named_in(_read_text(base / wrapper), base)
                        if p not in scripts]
        if not scripts:
            continue
        cadence = _systemd_cadence(on)
        out.append(ComponentSpec(
            component_id=f"systemd:{unit}",
            kind="timer", host="vps", code_paths=tuple(dict.fromkeys(scripts)),
            cadence_s=cadence, timeout_s=None, progress_metric="timer_runs",
            owner="vps", restart_action=f"systemctl --user restart {unit}",
            criticality="optional", resource_budget={},
            schedule=unit, artifact_class=_class_for_cadence(cadence),
            notes=f"ops/crontab.manifest line {no}: SYSTEMD {unit} on={on or 'UNMEASURED'}"))
    return out


def law_gate_specs(root: Path | None = None) -> list[ComponentSpec]:
    """One spec per fence the law gate runs. The gate itself fires hourly on the VPS crontab and
    on every push, so every fence it lists is on a clock and none of them is 'a script nobody
    runs'."""
    base = root or ROOT
    out: list[ComponentSpec] = []
    for name in dict.fromkeys(_FENCE_REF.findall(_read_text(base / "scripts" / "run_law_gate.py"))):
        rel = f"scripts/{name}"
        if not (base / rel).is_file():
            continue
        out.append(ComponentSpec(
            component_id=f"fence:{Path(name).stem}",
            kind="task", host="any", code_paths=(rel,),
            cadence_s=3600, timeout_s=600, progress_metric="gate_runs",
            owner="law_gate", restart_action="scripts/run_law_gate.py",
            criticality="optional", resource_budget={"budget_s": 600},
            schedule="run_law_gate.py", artifact_class="hourly",
            notes="fence listed in scripts/run_law_gate.py (_LAW_FENCES/_STATE_FENCES)"))
    return out


def hook_specs(root: Path | None = None) -> list[ComponentSpec]:
    """The git hooks and the gate wrapper: they fire on every commit and push, and the scripts
    they name run then."""
    base = root or ROOT
    out: list[ComponentSpec] = []
    for rel in HOOK_FILES:
        p = base / rel
        if not p.is_file():
            continue
        scripts = [s for s in scripts_named_in(_read_text(p), base) if s != rel]
        out.append(ComponentSpec(
            component_id=f"hook:{Path(rel).name}",
            kind="task", host="any", code_paths=tuple(dict.fromkeys([rel, *scripts])),
            cadence_s=None, timeout_s=None, progress_metric="hook_runs",
            owner="git", restart_action="git config core.hooksPath ops/githooks",
            criticality="optional", resource_budget={},
            schedule=f"git-hook:{Path(rel).name}", artifact_class=UNMEASURED,
            notes="fires on every commit/push; the scripts it names run then"))
    return out


# ------------------------------------------------------ reach: what a clocked organ pulls in
_AREA_FILES: dict[str, dict[str, Path]] = {}


def _area_files(root: Path | None = None) -> dict[str, Path]:
    """rel -> path for every .py under the walked areas (libraries included), read once."""
    base = root or ROOT
    key = str(base)
    if key not in _AREA_FILES:
        files: dict[str, Path] = {}
        for area in EXECUTABLE_AREAS:
            d = base / area
            if not d.is_dir():
                continue
            for p in d.rglob("*.py"):
                if "__pycache__" in p.parts or "_retired" in p.parts:
                    continue
                files[p.relative_to(base).as_posix()] = p
        _AREA_FILES[key] = files
    return _AREA_FILES[key]


def _import_stems(text: str) -> set[str]:
    """Module stems a file imports: `import x`, `from pkg.x import y` (both `x` and `y`, since
    `from research import x` binds a module) -- the wide form, because the question is REACH."""
    out: set[str] = set()
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {a.name.split(".")[-1] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                out.add(node.module.split(".")[-1])
            out |= {a.name.split(".")[0] for a in node.names}
    return out


BATTERIES = "desks/mt5/research/batteries.py"
#: One rostered organ per `_e("<path>", ...)` line, inside the roster tuple that names it.
_BATTERY_BLOCK = re.compile(r"^(FENCES|ORGANS):\s*tuple\[Entry.*?^\)\s*$", re.S | re.M)
_BATTERY_ENTRY = re.compile(r'_e\(\s*"([^"]+)"')
#: leg name and pass budget per roster, as `hourly_cycle.py` runs them. Kept here because the
#: registry must name the CLOCK, and the clock is the leg, not the battery module.
BATTERY_LEGS: dict[str, tuple[str, int]] = {"fences": ("fence_battery", 600),
                                            "organs": ("organ_battery", 600)}


def battery_specs(root: Path | None = None) -> list[ComponentSpec]:
    """One spec per organ on a standing battery roster (`research/batteries.py`).

    A battery runs its roster IN ROTATION under one hourly leg, so a rostered organ's clock is
    real but slower than hourly: `cadence_s` is the rotation bound (roster size over the organs
    one pass affords) and `max_silence_s` is twice it, which is the FRESHNESS EXPECTATION a
    reader -- or the loop-liveness prover -- can hold the organ to. Parsed from the source, never
    imported: the registry must mean the same thing in CI, a fresh clone and on the box.
    """
    base = root or ROOT
    text = _read_text(base / BATTERIES)
    out: list[ComponentSpec] = []
    for m in _BATTERY_BLOCK.finditer(text):
        roster = m.group(1).lower()
        leg, budget_s = BATTERY_LEGS.get(roster, (f"{roster}_battery", 600))
        paths = [p for p in _BATTERY_ENTRY.findall(m.group(0)) if (base / p).is_file()]
        if not paths:
            continue
        # One pass affords budget/slice organs; the slice is batteries.slice_s of that budget.
        per_pass = max(1, int(budget_s // max(20, min(150, budget_s * 0.34))))
        rotation_s = int(3600 * -(-len(paths) // per_pass))
        for rel in paths:
            out.append(ComponentSpec(
                component_id=f"battery:{rel}",
                kind="executable", host="box", code_paths=(rel,),
                outputs=(f"desks/mt5/reports/BATTERY_{roster.upper()}.json",),
                consumers=("desks/mt5/research/wiring_ceo.py",),
                cadence_s=rotation_s, max_silence_s=2 * rotation_s,
                timeout_s=int(min(150, budget_s * 0.34)),
                progress_metric="battery_rotation_runs",
                owner=f"batteries:{roster}", restart_action="restart:task:MT5-Hourly",
                criticality="optional", resource_budget={"budget_s": budget_s},
                schedule=f"hourly_cycle:{leg}", artifact_class="hourly",
                notes=(f"ROSTERED on the {roster} battery: run in rotation by "
                       f"{BATTERIES}; its verdict and the AGE of that verdict are published in "
                       f"BATTERY_{roster.upper()}.json, and a stale or failing row is named "
                       "there rather than being silence")))
    return out


FOREST_RUNNER = "desks/mt5/research/forest_runner.py"
#: `research.countries.<cc>.<leaf>` as forest_runner builds it at runtime (pack_module,
#: data_plane_module). The LEAVES are read out of that file rather than listed here, so a new
#: dynamic import is picked up by re-reading the source instead of by editing this module.
_DYN_COUNTRY = re.compile(r"research\.countries\.\{code\}\.(\w+)")


def dynamic_reach_roots(root: Path | None = None) -> dict[str, str]:
    """rel -> the clocked file that imports it BY PATTERN, for edges a static walk cannot see.

    `forest_runner` is on eleven hourly legs and imports every country pack and data plane as
    `importlib.import_module(f"research.countries.{code}.pack")` (and `.data_plane`), and a
    region package's `<pkg>.mandate`. An f-string is invisible to `_import_stems`, so the ten
    official data planes read as executables no clock reaches -- which is how `countries/za/
    data_plane.py` sat in the unclocked census while the Africa forest ran it every hour.

    THE EDGE IS DERIVED FROM THE SAME TWO SOURCES THE RUNNER USES, never declared: the leaf
    names come from forest_runner's own source, and the country codes and region packages come
    from the forest roster (`libs.research.forests`). If the runner stops importing them, the
    pattern disappears from its source and so do these roots.
    """
    base = root or ROOT
    text = _read_text(base / FOREST_RUNNER)
    if not text:
        return {}
    leaves = sorted(set(_DYN_COUNTRY.findall(text)))
    try:
        from libs.research import forests as F
    except Exception:
        return {}
    out: dict[str, str] = {}
    roster = F.FORESTS
    for f in (roster.values() if isinstance(roster, dict) else roster):
        for cc in getattr(f, "countries", ()):
            for leaf in leaves:
                rel = f"desks/mt5/research/countries/{str(cc).lower()}/{leaf}.py"
                if (base / rel).is_file():
                    out[rel] = f"{FOREST_RUNNER} (dynamic research.countries.{cc.lower()}.{leaf})"
        pkg = str(getattr(f, "package", "") or "")
        if pkg:
            for leaf in ("mandate", "__init__"):
                rel = f"{pkg}/{leaf}.py"
                if (base / rel).is_file():
                    out[rel] = f"{FOREST_RUNNER} (dynamic region package {pkg})"
    return out


def reach_specs(reg: Registry, root: Path | None = None,
                extra_roots: dict[str, str] | None = None) -> list[ComponentSpec]:
    """A spec for every executable a CLOCKED organ reaches -- by import (kind `library`,
    schedule `import:<importer>`) or by naming it as a script to run (kind `executable`,
    schedule `invoked:<invoker>`). The closure walks from every scheduled spec's code paths
    through imports and invocations, so a module three imports below an hourly leg is on that
    leg's clock, which is where it actually runs. Nothing here invents a clock: every schedule
    names the file that carries the edge, and a reader can open it."""
    base = root or ROOT
    files = _area_files(base)
    exes = set(executables(base))
    by_stem: dict[str, list[str]] = {}
    for rel, p in files.items():
        by_stem.setdefault(p.stem, []).append(rel)
    claimed = reg.claimed_paths()
    reached: dict[str, tuple[str, str]] = {}
    frontier = [p for s in reg.all() if s.scheduled for p in s.code_paths]
    # The dynamic edges first, as closure ROOTS: what a region pack imports statically is then
    # reached by the ordinary walk below, from the pack the runner imports by pattern.
    for rel, via in (extra_roots or {}).items():
        if rel not in claimed and rel not in reached:
            reached[rel] = ("library", via)
            frontier.append(rel)
    while frontier:
        rel = frontier.pop()
        text = _read_text(base / rel)
        if not text:
            continue
        if rel.endswith(".py"):
            for stem in _import_stems(text):
                for target in by_stem.get(stem, ()):
                    if target != rel and target not in claimed and target not in reached:
                        reached[target] = ("library", rel)
                        frontier.append(target)
        for target in scripts_named_in(text, base):
            if target != rel and target not in claimed and target not in reached:
                reached[target] = ("executable", rel)
                frontier.append(target)
    out: list[ComponentSpec] = []
    for rel, (kind, via) in sorted(reached.items()):
        if rel not in exes:
            continue                     # a pure library: not an executable, nothing to claim
        out.append(ComponentSpec(
            component_id=f"{kind}:{rel}",
            kind=kind, host="any", code_paths=(rel,),
            cadence_s=None, timeout_s=None, progress_metric=UNMEASURED,
            owner=UNMEASURED, restart_action=UNMEASURED,
            criticality="optional", resource_budget={},
            schedule=f"{'import' if kind == 'library' else 'invoked'}:{via}",
            artifact_class=UNMEASURED,
            notes=("REACHED: imported by a clocked organ, runs when it runs" if kind == "library"
                   else "REACHED: named as a script by a clocked organ, runs when it runs")))
    return out


# ------------------------------------------------------------------------------ the registry
def build_registry(root: Path | None = None) -> Registry:
    reg = Registry()
    for group in (explicit_specs(), resident_specs(), hourly_leg_specs(), daily_step_specs(),
                  manifest_task_specs(), timer_specs(root), federation_worker_specs(),
                  cron_specs(root), systemd_manifest_specs(root), law_gate_specs(root),
                  hook_specs(root), battery_specs(root)):
        for s in group:
            reg.add(s, replace=True)
    reg.add_all(reach_specs(reg, root, dynamic_reach_roots(root)), replace=True)
    reg.add_all(discovered_specs(reg.claimed_paths(), root), replace=True)
    return reg


_CACHE: dict[str, Registry] = {}


def registry(root: Path | None = None, refresh: bool = False) -> Registry:
    """The desk's registry, built once per process. `refresh=True` rebuilds it (tests)."""
    key = str(root or ROOT)
    if refresh or key not in _CACHE:
        _CACHE[key] = build_registry(root)
    return _CACHE[key]


def census(root: Path | None = None) -> dict[str, Any]:
    reg = registry(root)
    exes = executables(root)
    claimed = reg.claimed_paths()
    unclaimed = [e for e in exes if e not in claimed]
    # UNCLOCKED means kind `executable` AND no schedule: a file a clocked organ invokes carries
    # `invoked:<file>` and is on that organ's clock; a `library` runs whenever its importer does.
    unclocked = [s.component_id for s in reg.by_kind("executable") if not s.scheduled]
    return {**reg.census(root), "executables": len(exes),
            "executables_unclaimed": unclaimed,
            "executables_without_clock": len(unclocked),
            "unclocked": sorted(s.split(":", 1)[1] for s in unclocked),
            "reached_library": sum(1 for s in reg.by_kind("library")),
            "reached_invoked": sum(1 for s in reg.by_kind("executable") if s.scheduled),
            "coverage": round(1.0 - len(unclaimed) / len(exes), 6) if exes else None}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true", help="print the full registry as json")
    a = ap.parse_args(argv)
    reg = registry()
    if a.json:
        print(json.dumps(reg.to_json(), indent=1, default=str))
        return 0
    c = census()
    print(f"components: {c['components']} ({c['scheduled']} scheduled, {c['unscheduled']} not) "
          f"over {c['executables']} executables; coverage {c['coverage']}; "
          f"{c['executables_without_clock']} executable(s) with no clock; "
          f"{len(c['problems'])} registry problem(s)")
    for p in c["problems"][:20]:
        print("   problem:", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
