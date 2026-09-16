"""THE RESOURCE EXCHANGE -- every department at full throughput, measured, with a floor nobody
can take and an elastic share that follows marginal research value.

THE PRINCIPAL'S ORDER (2026-09-16): not "30% explore, 30% exploit" as permanent limits, but
"Explore = 100% || Exploit = 100% || Transfer = 100% || Validate = 100% || Intel = 100% ||
Meta = 100%" -- each department with its own workers, queues and compute reservation, running
continuously at maximum useful throughput, and a central exchange that hands spare capacity to
the best current opportunity without ever shutting a department down.

WHAT THE DESK'S OWN NUMBERS SAID. One sequential heavy pass summed to three hours: the gauntlet
waited for the crawler, the macro brain waited for the backtest, and everything after the kill
point ran never (lesson L0357). hourly_cycle now runs each department as its own scheduled task
(HOURLY_PLAN=dept:<name>), which IS the guaranteed baseline: a department's clock is its floor.
This organ measures what each department produced for what it cost and publishes the ELASTIC
part: a bounded factor per department that research_budget multiplies into its legs' seconds,
so the department whose last week bought the most survivors, novelty and breadth per compute
hour gets more seconds, and no factor ever falls below the floor that keeps a department alive.
Two-sided, evidence-derived, never a percentage anyone typed.

THE SHADOW PRICE. The exchange also names the resource that binds the whole machine today --
compute (departments hitting their budgets), forward slots (certified cells waiting for a
clock), data (UNMEASURED axes), or statistical sample (thin posteriors) -- because buying more
of a resource that does not bind buys nothing (principal: "if the gauntlet has 100,000
candidates and 12 forward clocks, reality is the bottleneck").

Reads: the compute ledger, hypothesis_graph.jsonl (fates by source -> department via the
bandit's arm_of and the leg tables), NOVELTY_GATE.json, EFFECTIVE_BREADTH history, shadow
state (forward conversion), POSTERIOR_ALPHA.json, AXIS_REGISTRY.json.
Writes: reports/RESEARCH_DEPARTMENTS.json. Consumer: research_budget.budget_s (factor).
"""
from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
LEDGER = DESK / "data" / "compute_ledger.jsonl"
GRAPH = DESK / "data" / "hypothesis_graph.jsonl"
NOVELTY = DESK / "reports" / "NOVELTY_GATE.json"
BREADTH_HIST = DESK / "data" / "effective_breadth.jsonl"
SHADOW = DESK / "reports" / "shadow" / "shadow_state.json"
POSTERIOR = DESK / "reports" / "POSTERIOR_ALPHA.json"
AXIS = DESK / "reports" / "AXIS_REGISTRY.json"
BUDGET = DESK / "reports" / "RESEARCH_BUDGET.json"
OUT = DESK / "reports" / "RESEARCH_DEPARTMENTS.json"
WINDOW_DAYS = 7
FACTOR_CLIP = (0.75, 1.5)
#: Which hypothesis sources belong to which department (the bandit's SOURCE_ARM is finer; this
#: is the coarse map the exchange prices). Unknown sources are `discovery`.
SOURCE_DEPARTMENT: dict[str, str] = {
    "world_crawler": "intel", "deep_forest": "intel", "repo_miner": "intel", "crawler": "intel",
    "world": "intel", "kimi": "intel", "deepseek": "intel", "standing_questions": "intel",
    "axis_registry": "discovery", "qd_frontier": "discovery", "alpha_evolution": "discovery",
    "edge_search": "discovery", "breadth_sweep": "discovery", "deepening": "discovery",
    "mutation": "discovery", "research_tree": "discovery", "joint_evolution": "discovery",
    "factor_residual": "macro", "cross_asset_graph": "macro", "lead_lag": "macro",
    "macro_graph": "macro", "world_lab": "macro", "causal_lab": "macro",
    "residual_queue": "macro", "event_response_atlas": "macro",
    "excursions": "execution", "exit_accounts": "execution", "fill_surface": "execution",
    "microstructure_miner": "execution",
    "failure_miner": "meta", "graveyard": "meta", "revival_engine": "meta",
}


def _read(p: Path) -> dict[str, Any]:
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _jsonl(p: Path, tail: int = 200000) -> list[dict[str, Any]]:
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()[-tail:]
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict):
            out.append(r)
    return out


def _at(v: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def leg_departments() -> tuple[dict[str, str], tuple[str, ...]]:
    """hourly_cycle's own tables, imported lazily (this organ must not fail without them)."""
    try:
        import hourly_cycle as hc
        return dict(hc.LEG_DEPARTMENT), tuple(hc.DEPARTMENTS)
    except Exception:
        return {}, ("data", "intel", "discovery", "validate", "macro", "execution", "forward",
                    "meta", "rest")


def compute_by_department(ledger: list[dict[str, Any]], legs: dict[str, str],
                          since: datetime) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = defaultdict(lambda: {"hours": 0.0, "runs": 0.0,
                                                            "timeouts": 0.0, "failed": 0.0})
    for r in ledger:
        t = _at(r.get("at"))
        if t is None or t < since:
            continue
        name = str(r.get("run") or "")
        dept = legs.get(name, "rest")
        if name.startswith("auto_"):
            dept = "rest"
        d = out[dept]
        d["hours"] += float(r.get("wall_s") or 0.0) / 3600.0
        d["runs"] += 1
        oc = str(r.get("outcome") or "")
        if oc.upper().startswith("TIMEOUT"):
            d["timeouts"] += 1
        elif oc.upper().startswith("FAILED") or oc.upper().startswith("LEG_FAILED"):
            d["failed"] += 1
    return dict(out)


def source_department(source: Any) -> str:
    s = str(source or "").split(":")[0].strip().lower()
    for k, v in SOURCE_DEPARTMENT.items():
        if s == k or s.startswith(k):
            return v
    return "discovery"


def yield_by_department(graph: list[dict[str, Any]], since: datetime) -> dict[str, dict[str, int]]:
    """Born / certified / failed hypotheses per department in the window, latest row per id."""
    latest: dict[str, dict[str, Any]] = {}
    for r in graph:
        if r.get("id"):
            latest[str(r["id"])] = r
    out: dict[str, dict[str, int]] = defaultdict(lambda: {"born": 0, "certified": 0, "failed": 0})
    for r in latest.values():
        t = _at(r.get("at") or r.get("born_at"))
        if t is not None and t < since:
            continue
        d = out[source_department(r.get("source"))]
        d["born"] += 1
        fate = str(r.get("fate") or "").upper()
        if fate == "CERTIFIED":
            d["certified"] += 1
        elif fate in ("FAILED", "BURIED"):
            d["failed"] += 1
    return dict(out)


def novelty_by_department(nov: dict[str, Any]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = defaultdict(lambda: {"novel": 0, "screened": 0})
    by_src = nov.get("by_source") if isinstance(nov.get("by_source"), dict) else {}
    for src, v in by_src.items():
        if not isinstance(v, dict):
            continue
        d = out[source_department(src)]
        d["novel"] += int(v.get("novel") or 0)
        d["screened"] += int(v.get("screened") or (int(v.get("novel") or 0)
                                                    + int(v.get("redundant") or 0)))
    return dict(out)


def binding_resource(depts: dict[str, dict[str, Any]], shadow: dict[str, Any],
                     posterior: dict[str, Any], axis: dict[str, Any]) -> dict[str, Any]:
    """Which resource binds the machine: compute, forward slots, data or sample."""
    timeouts = sum(float(d.get("compute", {}).get("timeouts", 0)) for d in depts.values())
    runs = sum(float(d.get("compute", {}).get("runs", 0)) for d in depts.values())
    compute_pressure = timeouts / runs if runs else 0.0
    active = sum(1 for v in shadow.values() if isinstance(v, dict)
                 and str(v.get("status") or "").upper() == "ACTIVE")
    thin = 0
    for row in (posterior.get("sleeves") or []) if isinstance(posterior, dict) else []:
        if isinstance(row, dict) and isinstance(row.get("n"), (int, float)) and row["n"] < 20:
            thin += 1
    n_rows = len(posterior.get("sleeves") or []) if isinstance(posterior, dict) else 0
    by_state = axis.get("by_state") if isinstance(axis.get("by_state"), dict) else {}
    unm = int(by_state.get("UNMEASURED", 0) or 0)
    n_cells = sum(int(v) for v in by_state.values() if isinstance(v, (int, float))) or 1
    scores = {
        "compute": round(compute_pressure, 3),
        "sample": round(thin / n_rows, 3) if n_rows else None,
        "data": round(unm / n_cells, 3),
        "forward_slots": None,   # UNMEASURED until the forward ranker publishes a queue depth
    }
    measured = {k: v for k, v in scores.items() if isinstance(v, (int, float))}
    binding = max(measured, key=lambda k: measured[k]) if measured else None
    return {"binding": binding, "scores": scores, "forward_clocks_active": active,
            "why": ("the resource with the highest measured pressure binds; buying a resource "
                    "that does not bind buys nothing")}


def build(window_days: int = WINDOW_DAYS) -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    since = now - timedelta(days=window_days)
    legs, names = leg_departments()
    comp = compute_by_department(_jsonl(LEDGER), legs, since)
    yld = yield_by_department(_jsonl(GRAPH), since)
    nov = novelty_by_department(_read(NOVELTY))
    depts: dict[str, dict[str, Any]] = {}
    for d in names:
        c = comp.get(d, {"hours": 0.0, "runs": 0.0, "timeouts": 0.0, "failed": 0.0})
        y = yld.get(d, {"born": 0, "certified": 0, "failed": 0})
        n = nov.get(d, {"novel": 0, "screened": 0})
        hours = float(c["hours"])
        depts[d] = {
            "legs": sorted(k for k, v in legs.items() if v == d),
            "compute": {k: round(float(v), 3) for k, v in c.items()},
            "yield": y,
            "novelty": n,
            "certified_per_hour": (round(y["certified"] / hours, 4) if hours > 0 else None),
            "novel_per_hour": (round(n["novel"] / hours, 4) if hours > 0 else None),
            "born_per_hour": (round(y["born"] / hours, 4) if hours > 0 else None),
            "status": ("UNMEASURED: no compute recorded in the window" if hours <= 0
                       else "MEASURED"),
        }
    # elastic factors: productivity relative to the median measured department, clipped;
    # UNMEASURED departments read 1.0 (a missing measurement reallocates nothing).
    prods = {d: (v["certified_per_hour"] or 0.0) + 0.1 * (v["novel_per_hour"] or 0.0)
             for d, v in depts.items() if v["status"] == "MEASURED"}
    factors: dict[str, float] = {}
    if prods:
        ref = sum(prods.values()) / len(prods)
        for d in depts:
            if d not in prods or ref <= 0:
                factors[d] = 1.0
            else:
                raw = 1.0 + (prods[d] - ref) / ref * 0.25
                factors[d] = round(max(FACTOR_CLIP[0], min(FACTOR_CLIP[1], raw)), 3)
    else:
        factors = dict.fromkeys(depts, 1.0)
    for d, f in factors.items():
        depts[d]["factor"] = f
    return {
        "at": now.isoformat(timespec="seconds"), "window_days": window_days,
        "departments": depts, "factors": factors,
        "floor": ("each department's own scheduled task (HOURLY_PLAN=dept:<name>) is its "
                  "guaranteed baseline; the factor is the elastic part, clipped to "
                  f"{list(FACTOR_CLIP)}"),
        "binding_resource": binding_resource(depts, _read(SHADOW), _read(POSTERIOR), _read(AXIS)),
        "rule": ("every department runs at full useful throughput on its own clock; spare "
                 "seconds follow measured survivors and novelty per compute-hour; UNMEASURED "
                 "reallocates nothing"),
    }


def factor_for(leg: str, doc: dict[str, Any] | None = None) -> float:
    """The department factor for a leg (1.0 when unmeasured or unknown)."""
    d = doc if doc is not None else _read(OUT)
    legs, _ = leg_departments()
    dept = legs.get(leg, "rest")
    fac = d.get("factors") if isinstance(d.get("factors"), dict) else {}
    try:
        return float(fac.get(dept, 1.0) or 1.0)
    except (TypeError, ValueError):
        return 1.0


def write(doc: dict[str, Any], path: Path | None = None) -> Path:
    p = path or OUT
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, p)
    return p


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--days", type=int, default=WINDOW_DAYS)
    a = ap.parse_args(argv)
    doc = build(a.days)
    print(f"research departments ({a.days}d): binding resource = "
          f"{doc['binding_resource']['binding']}")
    for d, v in doc["departments"].items():
        c = v["compute"]
        print(f"  {d:<10} {c['hours']:6.2f}h {int(c['runs']):4d} runs  "
              f"born {v['yield']['born']:5d} "
              f"cert {v['yield']['certified']:3d}  novel {v['novelty']['novel']:5d}  "
              f"x{v['factor']:.2f}  {v['status'][:10]}")
    if not a.dry_run:
        print(f"-> {write(doc)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
