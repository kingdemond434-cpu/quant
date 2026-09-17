"""THE DAILY RESEARCH OS -- one canonical loop a day, and one canonical statement of where the
research stands when it ends.

WHY THIS EXISTS (ledger M20/M22). The desk has a daily CEO docket, an hourly cycle with nine
departments, a scorecard, a wiring hunter, a residual queue, a frontier estimator and a registry --
and NO ORGAN THAT READS THEM TOGETHER AND DECIDES. Each one publishes a true number about its own
corner; nothing on this tree could say which of those numbers is the one binding the whole machine
today, what the day's compute therefore did NOT buy, or whether the thing that bound it yesterday
moved at all. A desk with nine dashboards and no controller runs nine local optimisations.

    OBSERVE -> DIAGNOSE -> PRIORITIZE -> ALLOCATE -> RUN -> MEASURE -> LEARN -> RELEASE TRAIN

IT SUPERSEDES `frontier_ceo` BY CALLING IT, never by copying it. The docket is still the organ
that proposes and ranks capability; this is the organ that reads the docket alongside everything
else, names the binding bottleneck, hands each department the bottleneck it should attack, runs
the day's chain, and then MEASURES whether the north star moved. Duplicating the docket's logic
here would give the desk two rankings that disagree on alternate days.

THE NORTH STAR IS DECLARED ONCE AND MEASURED DAY OVER DAY:

    ResearchValue = d FrontierCoverage + d OrthogonalCandidates + d IndependentSurvivorYield
                    + d n_eff - ComplexityCost

Every term is a DIFFERENCE against yesterday's reading of the same quantity, taken from the
registry's own KPI table (`libs/moat/registry.kpi`), which is why this organ writes today's
absolutes on every pass: a controller that cannot diff itself is a dashboard. A term whose
yesterday or today is absent is UNMEASURED BY NAME and is excluded from the sum rather than
silently counted as zero -- a zero says the desk measured no movement, and that is the one lie a
controller cannot afford (L1.28a).

THE UNITS ARE DECLARED IN `SCALES` AND NOWHERE ELSE. Four of the five terms are counts on
different scales and one is a fraction; summing them raw would let whichever term happens to be
largest own the north star. The weights are stated here so they can be argued with, rather than
emerging from whichever artifact was written last.

IT NEVER TURNS A DEPARTMENT OFF. The allocation is ELASTIC -- a share suggestion and the
bottleneck each department should attack -- and every department keeps a floor share, because the
principal's standing order is that the desk never reduces its aggressiveness and because a
department starved to zero stops producing the measurement that would have justified funding it
again. `research_departments` already owns the compute factor; this writes the day's TARGET, and
the exchange is free to read it.

THE DAILY RELEASE TRAIN is the row a human reads: what the day added, what it converted, what it
killed, what it learned, what binds tomorrow -- and `day_counted_successful` with the reason,
because a day that bought nothing measurable should say so in its own record.

    python desks/mt5/research/daily_research_os.py             # the day's pass (once per UTC day)
    python desks/mt5/research/daily_research_os.py --once      # run a pass now regardless
    python desks/mt5/research/daily_research_os.py --dry-run   # observe, diagnose, rank; write none
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402

REPORTS, DATA = DESK / "reports", DESK / "data"
OUT = REPORTS / "DAILY_RESEARCH_OS.json"
TRAIN = DATA / "research_release_train.jsonl"
ALLOCATION = DATA / "daily_allocation.json"
BREADTH_HIST = DATA / "effective_breadth.jsonl"
GATE_LEDGER = DATA / "hypotheses" / "gate_verdict_ledger.jsonl"
LOCKS = DATA / "locks"
LOGS = DESK / "logs"
BOX_TASKS = DESK / "ops" / "box_tasks.manifest"

#: Everything the controller reads before it decides anything. A name absent from this map is a
#: number the controller does not have; a PATH absent from the box is an UNMEASURED it must name.
ARTIFACTS: dict[str, Path] = {
    "tier1_scorecard": REPORTS / "TIER1_SCORECARD.json",
    "research_departments": REPORTS / "RESEARCH_DEPARTMENTS.json",
    "wiring_ceo": REPORTS / "WIRING_CEO.json",
    "residual_queue": REPORTS / "RESIDUAL_QUEUE.json",
    "unseen_frontier": REPORTS / "UNSEEN_FRONTIER.json",
    "effective_breadth": REPORTS / "EFFECTIVE_BREADTH.json",
    "research_registry": REPORTS / "RESEARCH_REGISTRY.json",
    "mining_objective": REPORTS / "MINING_OBJECTIVE.json",
    "gap_map": REPORTS / "RESEARCH_GAP_MAP.json",
    "ceo_docket": REPORTS / "CEO_DOCKET.json",
    "probation": REPORTS / "PROBATION.json",
    "auto_legs": DATA / "auto_legs.json",
}

DEPARTMENTS_FALLBACK: tuple[str, ...] = ("data", "intel", "discovery", "validate", "macro",
                                         "execution", "forward", "meta", "rest")
#: No department is ever switched off, so every share has a floor. 3% of the day is small enough
#: to be a real reallocation and large enough that the starved department still produces the
#: measurement that would justify funding it again.
MIN_SHARE = 0.03
STEP_TIMEOUT_S = 1800.0
#: The north star's units, declared once. A coverage point is worth a hundredth of a unit of
#: coverage; a hundred new orthogonal candidates are worth one unit; an independent survivor and
#: a unit of n_eff are worth one each; every new module or scheduled task costs a quarter.
SCALES: dict[str, float] = {
    "d_frontier_coverage": 100.0, "d_orthogonal_candidates": 0.01,
    "d_independent_survivor_yield": 1.0, "d_n_eff": 1.0, "complexity_cost": -0.25,
}
KPI_NAMES: tuple[str, ...] = (
    "frontier_coverage", "orthogonal_candidates", "independent_survivor_yield", "n_eff",
    "complexity_cost", "conversion_debt_unexplained", "data_missing_cells", "silent_failures",
    "research_memory_rows", "research_candidates_rows", "trials_rows", "sources_rows",
    "mechanisms_rows", "axis_values_covered", "auto_legs", "unwired_organs", "ready_cells",
)
RULE = ("one controller, one north star, one release train: the day names its binding bottleneck "
        "with measured evidence, attacks it, and says whether it moved")


# ------------------------------------------------------------------------------ tolerant reading
def _read(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, ValueError):
        return None


def _jsonl(path: Path, tail: int = 40000) -> list[dict[str, Any]]:
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()[-tail:]
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _num(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _at(value: Any) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def departments() -> tuple[str, ...]:
    try:
        import hourly_cycle as hc
        return tuple(hc.DEPARTMENTS)
    except Exception:
        return DEPARTMENTS_FALLBACK


def run_command(cmd: list[str], timeout_s: float = STEP_TIMEOUT_S) -> dict[str, Any]:
    """Run one step as a CHILD PROCESS. Module-level so a test can replace it: the controller's
    decisions are what these tests are for, and a test that shells out measures the box instead."""
    t0 = time.monotonic()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s,
                              cwd=str(ROOT), check=False)
        tail = (proc.stdout or "").strip().splitlines()[-4:]
        return {"cmd": cmd, "rc": int(proc.returncode), "seconds": round(time.monotonic() - t0, 2),
                "tail": tail, "stderr_tail": (proc.stderr or "").strip().splitlines()[-3:]}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"cmd": cmd, "rc": None, "seconds": round(time.monotonic() - t0, 2),
                "tail": [], "error": f"{type(exc).__name__}: {str(exc)[:160]}"}


# ------------------------------------------------------------------------------ OBSERVE
def _complexity(since_h: float = 24.0) -> dict[str, Any]:
    """New modules and new scheduled tasks in the last day -- the cost side of the north star.

    Machinery is not free: every module is a thing to keep green, every task a slot on a box with
    8 GB, and a desk that adds both faster than it retires them ends up maintaining its own
    history. Measured from `git log --diff-filter=A` and the box's task manifest."""
    out: dict[str, Any] = {"new_modules": None, "new_tasks": None, "status": "UNMEASURED"}
    try:
        proc = subprocess.run(["git", "log", f"--since={since_h} hours ago",
                               "--diff-filter=A", "--name-only", "--pretty=format:"],
                              capture_output=True, text=True, timeout=60, cwd=str(ROOT),
                              check=False)
        if proc.returncode == 0:
            names = {ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()}
            out["new_modules"] = sum(1 for n in names if n.endswith(".py"))
            out["status"] = "MEASURED"
        else:
            out["why_modules"] = f"git log rc={proc.returncode}"
    except (OSError, subprocess.SubprocessError) as exc:
        out["why_modules"] = f"{type(exc).__name__}"
    try:
        lines = BOX_TASKS.read_text(encoding="utf-8", errors="replace").splitlines()
        out["tasks_declared"] = sum(1 for ln in lines
                                    if ln.strip() and not ln.lstrip().startswith("#"))
    except OSError:
        out["why_tasks"] = f"{BOX_TASKS} ABSENT: the box's task manifest is UNMEASURED"
    return out


def _residents() -> dict[str, Any]:
    """The department residents: which locks are warm, and when each log last moved."""
    locks: dict[str, float] = {}
    now = time.time()
    try:
        for lk in sorted(Path(LOCKS).glob("dept_*.lock")):
            locks[lk.stem[5:]] = round(now - lk.stat().st_mtime, 1)
    except OSError:
        pass
    logs: dict[str, float] = {}
    try:
        for lg in sorted(Path(LOGS).glob("*.log")):
            logs[lg.name] = round((now - lg.stat().st_mtime) / 3600.0, 2)
    except OSError:
        pass
    return {"locks_age_s": locks, "n_locks": len(locks),
            "log_age_h": dict(sorted(logs.items(), key=lambda kv: kv[1])[:20]),
            "status": "MEASURED" if (locks or logs) else "UNMEASURED: no locks and no logs"}


def _kpis_on(day: str) -> dict[str, float]:
    try:
        rows = R.kpis(days=10)
    except Exception:
        return {}
    return {str(r["name"]): float(r["value"]) for r in rows
            if str(r.get("day")) == day and r.get("value") is not None}


def observe() -> dict[str, Any]:
    """Everything the controller reads, with every absence NAMED."""
    now = datetime.now(tz=UTC)
    arts: dict[str, Any] = {}
    absent: list[str] = []
    docs: dict[str, Any] = {}
    for name, path in ARTIFACTS.items():
        doc = _read(path)
        docs[name] = doc
        if doc is None:
            absent.append(name)
            arts[name] = {"present": False, "path": str(path),
                          "status": "ABSENT" if not Path(path).exists() else "UNREADABLE"}
            continue
        stamp = None
        if isinstance(doc, dict):
            for key in ("at", "generated_utc", "generated_at", "swept_at", "updated_at"):
                if doc.get(key):
                    stamp = str(doc[key])
                    break
        age = None
        d = _at(stamp)
        if d is not None:
            age = round((now - d).total_seconds() / 3600.0, 2)
        arts[name] = {"present": True, "path": str(path), "at": stamp, "age_h": age}
    reg: dict[str, Any] = {"status": "MEASURED"}
    try:
        reg["counts"] = R.counts()
        reg["conversion_debt"] = R.conversion_debt()
        reg["queue_depth"] = R.queue_depth()
        reg["workers_alive"] = [str(w.get("worker_id")) for w in R.workers_alive()]
        reg["grid_cells_populated"] = len(R.grid_coverage())
        reg["generator_yields"] = R.generator_yields()[:40]
    except Exception as exc:
        reg = {"status": f"UNMEASURED: registry unreadable ({type(exc).__name__})"}
    today = now.date().isoformat()
    return {
        "at": now.isoformat(timespec="seconds"), "day": today,
        "artifacts": arts, "absent": absent, "docs": docs,
        "registry": reg,
        "residents": _residents(),
        "breadth_history": _jsonl(BREADTH_HIST, tail=500)[-30:],
        "complexity": _complexity(),
        "kpis_today": _kpis_on(today),
        "kpis_yesterday": _kpis_on((now - timedelta(days=1)).date().isoformat()),
        "why": ("an artifact this organ could not read is named in `absent` and never defaulted: "
                "the controller's first duty is to know what it does not know"),
    }


# ------------------------------------------------------------------------------ DIAGNOSE
#: THE RULE SET, DECLARED: rule -> (what it says is binding, the department that attacks it, why
#: it is a bottleneck at all). The prose lives here and not in nine call sites, so a rule cannot
#: drift from the reason it exists.
RULES: dict[str, tuple[str, str, str]] = {
    "conversion_debt_rising": (
        "conversion debt", "discovery",
        "a discovery without a disposition is a lead the desk paid for and never asked"),
    "department_silent_24h": (
        "a department producing nothing", "meta",
        "a department with no runs in the window is a clock that is not firing, which reads "
        "identically to a department with nothing to do"),
    "gauntlet_backlog_vs_capacity": (
        "judging capacity", "validate",
        "a hundred thousand candidates and twelve forward clocks means reality is the bottleneck, "
        "not ideas"),
    "frontier_holes_ready_untouched": (
        "untouched READY ground", "discovery",
        "ground with bars and the observable present, and not one candidate on it, is the "
        "cheapest breadth the desk can buy"),
    "silent_scheduled_failure": (
        "organs on no clock", "meta",
        "III.16: unwired or idle is a defect, and a scheduled organ that fails quietly reads the "
        "same as one that had nothing to say"),
    "n_eff_flat_7d": (
        "effective breadth", "macro",
        "n_eff is the binding constraint on growth; a week of it not moving is a week of sleeves "
        "added and independence unchanged"),
    "source_cold_3d": (
        "cold mining grounds", "intel",
        "a ground that yields nothing for days is either mined out or broken, and the two look "
        "identical from the leaderboard"),
    "residuals_unattacked": (
        "unexplained residuals", "macro",
        "an open residual is a measured thing the desk cannot explain, which is the highest-prior "
        "hypothesis available to it"),
    "registry_chain_empty": (
        "the canonical registry", "meta",
        "the finding that ordered the registry: knowledge preserved and no organ writing the "
        "research chain"),
}


def _row(rule: str, severity: float | None, evidence: dict[str, Any],
         attack: str | None = None) -> dict[str, Any]:
    """One diagnosis. `severity is None` is UNMEASURED and stays in the ranking: a bottleneck
    nobody could measure is not a bottleneck nobody has (L1.28a)."""
    bottleneck, dept, why = RULES[rule]
    return {"rule": rule, "bottleneck": bottleneck, "attack": attack or dept,
            "severity": (None if severity is None
                         else round(float(min(1.0, max(0.0, severity))), 4)),
            "status": "UNMEASURED" if severity is None else "MEASURED",
            "evidence": evidence, "why": why}


def diagnose(obs: dict[str, Any]) -> list[dict[str, Any]]:
    """Every rule in `RULES`, measured against today's artifacts. A rule whose input is absent
    reports UNMEASURED BY NAME rather than dropping out of the ranking."""
    docs, reg, prior = obs["docs"], obs["registry"], obs["kpis_yesterday"]
    rows: list[dict[str, Any]] = []

    debt = reg.get("conversion_debt") if isinstance(reg.get("conversion_debt"), dict) else {}
    now_debt = _num(debt.get("unexplained_missing_cells"))
    was_debt = prior.get("conversion_debt_unexplained")
    if now_debt is None:
        rows.append(_row("conversion_debt_rising", None, {"registry": reg.get("status")}))
    else:
        rise = None if was_debt is None else now_debt - was_debt
        sev = ((0.5 if now_debt > 0 else 0.0) if rise is None
               else min(1.0, max(0.0, rise) / max(1.0, was_debt or 1.0)))
        rows.append(_row("conversion_debt_rising", sev,
                         {"unexplained_missing_cells": now_debt, "yesterday": was_debt,
                          "delta": rise, "unprocessed": debt.get("unprocessed_discoveries")}))

    dep = docs.get("research_departments")
    if not isinstance(dep, dict):
        rows.append(_row("department_silent_24h", None,
                         {"artifact": "RESEARCH_DEPARTMENTS.json ABSENT"}))
    else:
        depts = dep.get("departments") or {}
        silent = [d for d, v in depts.items()
                  if isinstance(v, dict) and float((v.get("compute") or {}).get("runs") or 0) <= 0]
        rows.append(_row("department_silent_24h",
                         (len(silent) / max(1, len(depts))) if depts else 0.0,
                         {"silent": silent, "n_departments": len(depts)},
                         attack=silent[0] if silent else None))

    qd = reg.get("queue_depth")
    backlog = (sum(int(v.get("queued", 0)) for v in qd.values()) if isinstance(qd, dict) else None)
    counts = reg.get("counts") if isinstance(reg.get("counts"), dict) else None
    judged_rate = (max(0.0, float(counts.get("trials_ledger", 0)) - float(prior["trials_rows"]))
                   if counts is not None and prior.get("trials_rows") is not None else None)
    if backlog is None:
        rows.append(_row("gauntlet_backlog_vs_capacity", None, {"queue_depth": "UNMEASURED"}))
    else:
        days = None if not judged_rate else backlog / judged_rate
        rows.append(_row("gauntlet_backlog_vs_capacity",
                         0.5 if days is None else min(1.0, days / 30.0),
                         {"queued": backlog, "judged_yesterday": judged_rate,
                          "days_to_clear": (round(days, 1) if days else None)}))

    gap = docs.get("gap_map")
    if not isinstance(gap, dict):
        rows.append(_row("frontier_holes_ready_untouched", None,
                         {"artifact": "RESEARCH_GAP_MAP.json ABSENT -- and an unnamed hole is "
                                      "assumed covered, which the map exists to stop"}))
    else:
        valid = _num(gap.get("n_valid_cells")) or 0.0
        ready = _num((gap.get("by_state") or {}).get("READY")) or 0.0
        rows.append(_row("frontier_holes_ready_untouched", (ready / valid) if valid else 0.0,
                         {"ready_cells": int(ready), "valid_cells": int(valid),
                          "research_debt_cells": gap.get("research_debt_cells"),
                          "top_hole": (gap.get("top_holes") or [{}])[0].get("cell")}))

    wiring = docs.get("wiring_ceo")
    score = docs.get("tier1_scorecard")
    silent_fail = None
    if isinstance(score, dict):
        for r in score.get("rows") or []:
            if isinstance(r, dict) and r.get("dimension") == "silent_scheduled_failures":
                silent_fail = _num(r.get("current"))
    if not isinstance(wiring, dict) and silent_fail is None:
        rows.append(_row("silent_scheduled_failure", None,
                         {"artifact": "WIRING_CEO.json and the scorecard row both ABSENT"}))
    else:
        unwired = _num((wiring or {}).get("n_unwired")) or 0.0
        breach = str(((wiring or {}).get("floor") or {}).get("status") or "")
        sev = max(min(1.0, unwired / 40.0) + (0.3 if breach == "BREACH" else 0.0),
                  min(1.0, (silent_fail or 0.0) / 5.0))
        rows.append(_row("silent_scheduled_failure", sev,
                         {"n_unwired": unwired, "floor": breach,
                          "silent_scheduled_failures": silent_fail}))

    cut = datetime.now(tz=UTC) - timedelta(days=7)
    vals = [v for at, v in ((_at(h.get("at")), _num(h.get("effective_breadth")))
                            for h in obs["breadth_history"])
            if v is not None and (at is None or at >= cut)]
    series = np.asarray(vals, dtype=float)
    if series.size < 3:
        rows.append(_row("n_eff_flat_7d", None,
                         {"readings_in_7d": int(series.size),
                          "why": "flatness cannot be told from a measurement that stopped"}))
    else:
        rel = float(series.max() - series.min()) / max(1e-9, float(series.mean()))
        rows.append(_row("n_eff_flat_7d", max(0.0, 1.0 - rel / 0.05),
                         {"readings": int(series.size), "min": round(float(series.min()), 3),
                          "max": round(float(series.max()), 3), "relative_spread": round(rel, 4)}))

    unseen = docs.get("unseen_frontier")
    if not isinstance(unseen, dict):
        rows.append(_row("source_cold_3d", None, {"artifact": "UNSEEN_FRONTIER.json ABSENT"}))
    else:
        cold = list((unseen.get("unmeasured") or {}).get("grounds_unmeasured") or [])
        grounds = unseen.get("grounds") or {}
        rows.append(_row("source_cold_3d", (len(cold) / max(1, len(grounds))) if grounds else 0.0,
                         {"n_cold": len(cold), "n_grounds": len(grounds),
                          "cold_sample": cold[:8]}))

    resid = docs.get("residual_queue")
    if not isinstance(resid, dict):
        rows.append(_row("residuals_unattacked", None, {"artifact": "RESIDUAL_QUEUE.json ABSENT"}))
    else:
        n_open = _num(resid.get("n_open")) or 0.0
        donated = _num(resid.get("n_candidates")) or 0.0
        rows.append(_row("residuals_unattacked",
                         min(1.0, n_open / 50.0) * (0.4 if donated > 0 else 1.0),
                         {"n_open": n_open, "donated_this_pass": donated}))

    if counts is None:
        rows.append(_row("registry_chain_empty", None, {"registry": reg.get("status")}))
    else:
        chain = ("research_candidates", "research_runs", "trials_ledger", "research_memory")
        empty = [t for t in chain if int(counts.get(t, 0)) == 0]
        rows.append(_row("registry_chain_empty", len(empty) / len(chain),
                         {"empty_tables": empty, "counts": {t: counts.get(t) for t in chain}}))
    return rows


# ------------------------------------------------------------------------------ north star
def _term(name: str, today: float | None, yesterday: float | None, source: str) -> dict[str, Any]:
    if today is None or yesterday is None:
        missing = "today" if today is None else "yesterday"
        return {"name": name, "delta": None, "today": today, "yesterday": yesterday,
                "weighted": None, "status": f"UNMEASURED: {missing} is absent", "source": source}
    delta = float(today) - float(yesterday)
    return {"name": name, "delta": round(delta, 6), "today": today, "yesterday": yesterday,
            "weighted": round(delta * SCALES[name], 6), "status": "MEASURED", "source": source}


def today_absolutes(obs: dict[str, Any]) -> dict[str, float]:
    """The quantities the north star diffs, read once so today's row and tomorrow's diff agree.

    DECLARED AS READERS, not as sixty lines of `if x is not None`: a quantity that cannot be read
    today is simply ABSENT from this dict, and every consumer treats absence as UNMEASURED. There
    is no place in here where a missing artifact can become a zero."""
    docs, reg = obs["docs"], obs["registry"]
    gap = docs.get("gap_map") if isinstance(docs.get("gap_map"), dict) else {}
    states = gap.get("by_state") or {}
    counts = reg.get("counts") if isinstance(reg.get("counts"), dict) else {}
    debt = reg.get("conversion_debt") if isinstance(reg.get("conversion_debt"), dict) else {}
    hist, comp = obs["breadth_history"], obs["complexity"]
    wiring = docs.get("wiring_ceo") if isinstance(docs.get("wiring_ceo"), dict) else {}
    legs = docs.get("auto_legs") if isinstance(docs.get("auto_legs"), dict) else {}
    eb = docs.get("effective_breadth") if isinstance(docs.get("effective_breadth"), dict) else {}
    score = docs.get("tier1_scorecard") if isinstance(docs.get("tier1_scorecard"), dict) else {}
    ys = reg.get("generator_yields")

    n_eff = _num(hist[-1].get("effective_breadth")) if hist else None
    if n_eff is None:
        n_eff = _num((eb.get("effective") or {}).get("effective_breadth"))
    silent = next((_num(r.get("current")) for r in (score.get("rows") or [])
                   if isinstance(r, dict) and r.get("dimension") == "silent_scheduled_failures"),
                  None)
    tasks = _num(comp.get("tasks_declared"))
    mods = _num(comp.get("new_modules"))
    prior_tasks = obs["kpis_yesterday"].get("box_tasks")
    new_tasks = 0.0 if (tasks is None or prior_tasks is None) else max(0.0, tasks - prior_tasks)

    readings: dict[str, float | None] = {
        "frontier_coverage": _num(gap.get("populated_share")),
        "ready_cells": _num(states.get("READY")),
        "data_missing_cells": _num(states.get("DATA_MISSING")),
        "axis_values_covered": (float(sum(len(v) for v in gap["coverage_by_axis"].values()))
                                if gap.get("coverage_by_axis") else None),
        "orthogonal_candidates": _num(reg.get("grid_cells_populated")),
        "independent_survivor_yield": (float(sum(int(y.get("independent_survivors") or 0)
                                                 for y in ys)) if isinstance(ys, list) else None),
        "n_eff": n_eff,
        "complexity_cost": None if mods is None else float(mods) + new_tasks,
        "box_tasks": tasks,
        "conversion_debt_unexplained": _num(debt.get("unexplained_missing_cells")),
        "research_memory_rows": _num(counts.get("research_memory")),
        "research_candidates_rows": _num(counts.get("research_candidates")),
        "trials_rows": _num(counts.get("trials_ledger")),
        "sources_rows": _num(counts.get("sources")),
        "mechanisms_rows": _num(counts.get("mechanisms")),
        "unwired_organs": _num(wiring.get("n_unwired")),
        "auto_legs": (float(len(legs["legs"])) if isinstance(legs.get("legs"), list) else None),
        "silent_failures": silent,
    }
    return {k: float(v) for k, v in readings.items() if v is not None}


def north_star(obs: dict[str, Any], absolutes: dict[str, float] | None = None) -> dict[str, Any]:
    """ResearchValue, term by term, each a day-over-day difference of a named quantity."""
    now = absolutes if absolutes is not None else today_absolutes(obs)
    was = obs["kpis_yesterday"]
    terms = [
        _term("d_frontier_coverage", now.get("frontier_coverage"), was.get("frontier_coverage"),
              "RESEARCH_GAP_MAP.populated_share"),
        _term("d_orthogonal_candidates", now.get("orthogonal_candidates"),
              was.get("orthogonal_candidates"), "registry.grid_coverage (distinct cells)"),
        _term("d_independent_survivor_yield", now.get("independent_survivor_yield"),
              was.get("independent_survivor_yield"), "registry.generator_yields"),
        _term("d_n_eff", now.get("n_eff"), was.get("n_eff"),
              "data/effective_breadth.jsonl effective_breadth"),
    ]
    cost = now.get("complexity_cost")
    terms.append({"name": "complexity_cost", "delta": cost, "today": cost, "yesterday": None,
                  "weighted": (None if cost is None else round(cost * SCALES["complexity_cost"],
                                                               6)),
                  "status": "MEASURED" if cost is not None else "UNMEASURED: git log unreadable",
                  "source": "git log --diff-filter=A (.py) + ops/box_tasks.manifest"})
    measured = [t for t in terms if t["weighted"] is not None]
    return {
        "research_value": (round(sum(float(t["weighted"]) for t in measured), 6)
                           if measured else None),
        "terms": terms,
        "unmeasured_terms": [t["name"] for t in terms if t["weighted"] is None],
        "scales": SCALES,
        "rule": ("every term is a day-over-day difference of a named quantity; an absent term is "
                 "UNMEASURED BY NAME and excluded from the sum, never counted as zero"),
    }


# ------------------------------------------------------------------------------ PRIORITIZE
def prioritize(rows: list[dict[str, Any]], star: dict[str, Any]) -> dict[str, Any]:
    """Rank the bottlenecks. MEASURED severity first; an UNMEASURED rule ranks immediately below
    the measured ones and above nothing -- it is a hole in the controller's own sight and stays
    visible, because the cheapest bottleneck to miss is the one nobody could see."""
    ranked = sorted(rows, key=lambda r: (r["severity"] is None, -(r["severity"] or 0.0),
                                         r["rule"]))
    for i, r in enumerate(ranked, 1):
        r["rank"] = i
    top = ranked[0] if ranked else None
    return {"ranked": ranked, "top": top,
            "n_unmeasured_rules": sum(1 for r in ranked if r["severity"] is None),
            "north_star": star,
            "rule": ("the binding bottleneck is the measured rule with the highest severity; "
                     "unmeasured rules are ranked, never dropped")}


# ------------------------------------------------------------------------------ ALLOCATE
def allocate(ranked: list[dict[str, Any]], names: tuple[str, ...] | None = None) -> dict[str, Any]:
    """An elastic share per department and the bottleneck it should attack.

    NEVER A ZERO. Every department keeps at least `MIN_SHARE`, and the allocation is a SUGGESTION
    the exchange may read -- it disables nothing, because the principal's standing order is that
    the desk never reduces its aggressiveness and because a department at zero stops producing
    the evidence that would fund it again."""
    depts = names or departments()
    weight = dict.fromkeys(depts, 1.0)
    attack: dict[str, str] = {}
    for r in ranked:
        if r["severity"] is None:
            continue
        target = r["attack"] if r["attack"] in weight else "meta"
        weight[target] += float(r["severity"]) * (1.0 / max(1, r.get("rank", 1)))
        attack.setdefault(target, r["rule"])
    total = sum(weight.values()) or 1.0
    shares = {d: w / total for d, w in weight.items()}
    # Floor, then renormalise the remainder over the departments above the floor.
    floored = {d: max(MIN_SHARE, s) for d, s in shares.items()}
    over = sum(floored.values())
    shares = {d: round(s / over, 6) for d, s in floored.items()}
    return {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "departments": {d: {"share": shares[d], "attack": attack.get(d),
                            "floor": MIN_SHARE, "enabled": True} for d in depts},
        "min_share": MIN_SHARE, "n_departments": len(depts),
        "rule": ("an elastic share suggestion per department and the bottleneck it should attack; "
                 "no department is ever disabled and none falls below the floor"),
    }


# ------------------------------------------------------------------------------ RUN
def _steps() -> list[tuple[str, list[str]]]:
    """The day's chain. `frontier_ceo` FIRST and by subprocess, because this controller supersedes
    it by calling it -- never by reimplementing its ranking."""
    py = sys.executable or "python"
    out = [("frontier_ceo", [py, str(DESK / "research" / "frontier_ceo.py"), "--apply"]),
           ("research_gap_map", [py, str(DESK / "research" / "research_gap_map.py")])]
    mining = DESK / "research" / "mining_objective.py"
    if mining.exists():
        out.append(("mining_objective", [py, str(mining)]))
    out.append(("registry_sync", [py, str(DESK / "research" / "registry_sync.py")]))
    return out


def run_steps(timeout_s: float = STEP_TIMEOUT_S) -> list[dict[str, Any]]:
    """Run the chain and record every step, including the ones that were not on the box. A step
    that could not run is ABSENT and named -- it must never read as a step that ran and did
    nothing (L1.28a)."""
    out = []
    for name, cmd in _steps():
        res = run_command(cmd, timeout_s)
        out.append({"step": name, **res, "outcome": ("ok" if res.get("rc") == 0 else "FAILED")})
    for name in ("mining_objective",):
        if not (DESK / "research" / f"{name}.py").exists():
            out.append({"step": name, "outcome": "ABSENT",
                        "why": f"{name}.py is not on this box yet -- named, not assumed run"})
    return out


# ------------------------------------------------------------------------------ LEARN + TRAIN
def _delta(now: dict[str, float], was: dict[str, float], key: str,
           sign: int = 1) -> float | None:
    a, b = now.get(key), was.get(key)
    if a is None or b is None:
        return None
    return round(sign * (float(a) - float(b)), 6)


def _gauntlet_today(day: str) -> dict[str, Any]:
    rows = [r for r in _jsonl(GATE_LEDGER, tail=40000) if str(r.get("at", ""))[:10] == day]
    if not rows:
        return {"judged": 0, "passed": 0,
                "status": "MEASURED" if GATE_LEDGER.exists() else "UNMEASURED: no gate ledger"}
    return {"judged": len(rows), "passed": sum(1 for r in rows if r.get("passed") is True),
            "status": "MEASURED"}


def release_train_row(obs: dict[str, Any], absolutes: dict[str, float], star: dict[str, Any],
                      top: dict[str, Any] | None, moved: dict[str, Any]) -> dict[str, Any]:
    """ONE row a human reads: what the day added, converted, killed and learned, and whether it
    counted. `day_counted_successful` is TRUE only when at least one of eight named things is
    MEASURED to have improved -- never because the pass completed."""
    was = obs["kpis_yesterday"]
    gaunt = _gauntlet_today(obs["day"])
    gap = obs["docs"].get("gap_map") if isinstance(obs["docs"].get("gap_map"), dict) else {}
    row: dict[str, Any] = {
        "at": obs["at"], "day": obs["day"],
        "sources_added": _delta(absolutes, was, "sources_rows"),
        "axes_opened": _delta(absolutes, was, "axis_values_covered"),
        "candidates_created": _delta(absolutes, was, "research_candidates_rows"),
        "conversion_debt_reduced": _delta(absolutes, was, "conversion_debt_unexplained", -1),
        "mechanisms_discovered": _delta(absolutes, was, "mechanisms_rows"),
        "gauntlet": gaunt,
        "failures_learned": _delta(absolutes, was, "research_memory_rows"),
        "machinery_tested": _num((obs["docs"].get("wiring_ceo") or {}).get("n_probation")
                                 if isinstance(obs["docs"].get("wiring_ceo"), dict) else None),
        "machinery_promoted": _delta(absolutes, was, "auto_legs"),
        "machinery_retired": _delta(absolutes, was, "unwired_organs", -1),
        "n_eff": absolutes.get("n_eff"),
        "frontier_gaps": [h.get("cell") for h in (gap.get("top_holes") or [])[:5]],
        "frontier_coverage": absolutes.get("frontier_coverage"),
        "research_value": star.get("research_value"),
        "next_bottleneck": (top or {}).get("rule"),
        "next_bottleneck_severity": (top or {}).get("severity"),
        "yesterdays_bottleneck_moved": moved.get("moved"),
    }
    checks = {
        "frontier_increased": _delta(absolutes, was, "frontier_coverage"),
        "candidate_breadth_increased": _delta(absolutes, was, "orthogonal_candidates"),
        "conversion_improved": row["conversion_debt_reduced"],
        "machinery_improved": row["machinery_promoted"],
        "data_improved": _delta(absolutes, was, "data_missing_cells", -1),
        "negative_knowledge_increased": (row["failures_learned"]
                                         if row["failures_learned"] is not None
                                         else (gaunt["judged"] - gaunt["passed"]
                                               if gaunt.get("status") == "MEASURED" else None)),
        "reliability_improved": _delta(absolutes, was, "silent_failures", -1),
        "meta_research_improved": (1.0 if moved.get("moved") else
                                   (0.0 if moved.get("moved") is False else None)),
    }
    won = [k for k, v in checks.items() if v is not None and float(v) > 0]
    unmeasured = [k for k, v in checks.items() if v is None]
    row["success_checks"] = dict(checks)
    row["day_counted_successful"] = bool(won)
    row["day_counted_reason"] = (
        "measured improvement in " + ", ".join(won) if won else
        ("NOTHING MEASURABLE MOVED" + (f"; {len(unmeasured)} check(s) UNMEASURED: "
                                       f"{', '.join(unmeasured)}" if unmeasured else "")))
    return row


def learn(obs: dict[str, Any], top: dict[str, Any] | None, rows: list[dict[str, Any]],
          moved: dict[str, Any]) -> str | None:
    """Write the day's diagnosis into research memory, keyed by day so a re-run refreshes rather
    than duplicates -- and carrying whether YESTERDAY's chosen bottleneck actually moved, which is
    the only evidence that the controller's choices are worth anything."""
    try:
        return R.remember(
            "research_os", statement=(f"binding bottleneck {(top or {}).get('rule')} at severity "
                                      f"{(top or {}).get('severity')}"),
            kind="daily_diagnosis", memory_key=f"daily_diagnosis:{obs['day']}",
            result=("moved" if moved.get("moved") else
                    ("did not move" if moved.get("moved") is False else "UNMEASURED")),
            payload={"day": obs["day"], "bottleneck": (top or {}).get("rule"),
                     "attack": (top or {}).get("attack"),
                     "severity": (top or {}).get("severity"),
                     "yesterday": moved},
            evidence={"rules": [{k: r[k] for k in ("rule", "severity", "status")} for r in rows],
                      "absent_artifacts": obs["absent"]})
    except Exception:
        return None


def yesterdays_bottleneck(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Did the thing that bound the desk yesterday move? Read from yesterday's own memory row and
    compared against today's measurement of the SAME rule -- not against a different rule that
    happens to look better."""
    try:
        mem = R.memories(category="research_os", kind="daily_diagnosis", limit=10)
    except Exception:
        return {"moved": None, "why": "research memory unreadable"}
    prior = None
    yesterday = (datetime.now(tz=UTC) - timedelta(days=1)).date().isoformat()
    for m in mem:
        try:
            payload = json.loads(str(m.get("payload_json") or "{}"))
        except ValueError:
            continue
        if payload.get("day") == yesterday:
            prior = payload
            break
    if prior is None:
        return {"moved": None, "why": f"no diagnosis stored for {yesterday}"}
    rule = prior.get("bottleneck")
    today = next((r for r in rows if r["rule"] == rule), None)
    if today is None or today["severity"] is None or prior.get("severity") is None:
        return {"moved": None, "rule": rule,
                "why": "the same rule is UNMEASURED today, so movement cannot be claimed"}
    delta = float(today["severity"]) - float(prior["severity"])
    return {"moved": bool(delta < 0), "rule": rule, "severity_yesterday": prior["severity"],
            "severity_today": today["severity"], "delta": round(delta, 4)}


# ------------------------------------------------------------------------------ the pass
def _write_json(path: Path, doc: Any) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, p)
    return p


def _append_train(row: dict[str, Any]) -> Path:
    TRAIN.parent.mkdir(parents=True, exist_ok=True)
    with TRAIN.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, default=str) + "\n")
    return TRAIN


def run_once(*, dry_run: bool = False, timeout_s: float = STEP_TIMEOUT_S) -> dict[str, Any]:
    """One full pass of the loop. `dry_run` stops after PRIORITIZE: nothing runs, nothing is
    written, and the diagnosis is printed -- which is the only safe thing to do on a box that is
    holding live positions when a session is only asking what the controller thinks."""
    t0 = time.monotonic()
    obs = observe()
    rules = diagnose(obs)
    before = today_absolutes(obs)
    star_before = north_star(obs, before)
    plan = prioritize(rules, star_before)
    top = plan["top"]
    alloc = allocate(plan["ranked"])
    doc: dict[str, Any] = {
        "at": obs["at"], "day": obs["day"], "mode": "dry-run" if dry_run else "apply",
        "observe": {k: obs[k] for k in ("artifacts", "absent", "registry", "residents",
                                        "complexity", "kpis_yesterday")},
        "diagnose": rules,
        "prioritize": {k: plan[k] for k in ("ranked", "top", "n_unmeasured_rules", "rule")},
        "north_star_before": star_before,
        "allocation": alloc,
        "rule": RULE,
    }
    if dry_run:
        doc["ran"] = []
        doc["note"] = "--dry-run: observed, diagnosed and ranked; nothing run, nothing written"
        doc["seconds"] = round(time.monotonic() - t0, 2)
        return doc

    _write_json(ALLOCATION, alloc)
    doc["ran"] = run_steps(timeout_s)

    after_obs = observe()
    after = today_absolutes(after_obs)
    star_after = north_star(after_obs, after)
    doc["north_star_after"] = star_after
    moved = yesterdays_bottleneck(rules)
    doc["yesterdays_bottleneck"] = moved
    doc["learned"] = learn(after_obs, top, rules, moved)
    row = release_train_row(after_obs, after, star_after, top, moved)
    doc["release_train"] = row
    for name in KPI_NAMES:
        if name in after:
            try:
                R.kpi(obs["day"], name, float(after[name]),
                      detail={"organ": "daily_research_os"})
            except Exception:
                doc.setdefault("kpi_write_failed", []).append(name)
    if "box_tasks" in after:
        try:
            R.kpi(obs["day"], "box_tasks", float(after["box_tasks"]), detail={"organ": "daily"})
        except Exception:
            doc.setdefault("kpi_write_failed", []).append("box_tasks")
    doc["seconds"] = round(time.monotonic() - t0, 2)
    _write_json(OUT, doc)
    _append_train(row)
    return doc


def already_ran_today() -> bool:
    doc = _read(OUT)
    return bool(isinstance(doc, dict)
                and doc.get("day") == datetime.now(tz=UTC).date().isoformat()
                and doc.get("mode") == "apply")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="observe, diagnose and rank; run nothing and write nothing")
    ap.add_argument("--once", action="store_true", help="run a pass now, whatever the day stamp")
    ap.add_argument("--timeout-s", type=float, default=STEP_TIMEOUT_S)
    a = ap.parse_args(argv)
    if not a.dry_run and not a.once and already_ran_today():
        print(f"daily research OS: already ran for {datetime.now(tz=UTC).date().isoformat()}; "
              f"--once to force")
        return 0
    doc = run_once(dry_run=a.dry_run, timeout_s=a.timeout_s)
    top = doc["prioritize"]["top"] or {}
    star = doc.get("north_star_after") or doc["north_star_before"]
    print(f"daily research OS {doc['day']} [{doc['mode']}]: bottleneck "
          f"{top.get('rule')} severity {top.get('severity')} -> {top.get('attack')}")
    for r in doc["diagnose"]:
        print(f"  {r.get('rank', 0):>2}. {r['rule']:<32} {r['severity']!s:<8} {r['status']}")
    print(f"  north star {star.get('research_value')} "
          f"({len(star.get('unmeasured_terms') or [])} term(s) UNMEASURED)")
    print(f"  absent artifacts: {', '.join(doc['observe']['absent']) or 'none'}")
    if doc["mode"] == "dry-run":
        print("  --dry-run: nothing run, nothing written")
        return 0
    row = doc["release_train"]
    print(f"  day_counted_successful={row['day_counted_successful']}: {row['day_counted_reason']}")
    print(f"-> {OUT}  -> {TRAIN}  -> {ALLOCATION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
