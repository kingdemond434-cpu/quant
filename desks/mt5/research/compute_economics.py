"""THE COMPUTE-ECONOMICS SCIENTIST (LAWS 5m, 5k): survivors per CPU-hour, per wall-clock hour and
per data-pound, by department, forest, search family and layer -- and the scheduler policy that
follows them.

    "Compute follows delayed real truth with an exploration budget so obscure systems can prove
    themselves"                                                               -- LAWS 5m
    "ROI_i = forward survivors x incremental portfolio value x novelty / (compute + data + trials
    consumed), and compute follows it"                                        -- LAWS 5k

WHAT THIS MEASURES AND WHERE THE NUMBERS COME FROM. The denominator is the compute ledger
(`desks/mt5/data/compute_ledger.jsonl`, wall and CPU seconds per costed leg); the numerator is
the desk's own record of what survived: certified cells in the hypothesis graph inside the
window, the research-ROI organ's credited survivors and dE[log W] per generator and per region,
and the forest allocator's file for what each forest was given. Nothing is re-measured here; the
organ JOINS the ledgers the desk already keeps, which is why a missing ledger reads UNMEASURED by
name and never as zero -- a zero denominator would make the cheapest department the best one.

THE THREE TIERS AND THE DEFAULT SPLIT. Research compute is one of three kinds: EXPLOITATION
(validating, forwarding and executing what the desk already believes), EXPLORATION (new
hypotheses, new sources, new regions) and the OPEN-ENDED FRONTIER (residual hunting, coverage
holes, world-model gaps, the machine evolving itself). The DEFAULT split is 70 / 20 / 10 and it
is a PRIOR, not a rule: each tier's measured survivors per hour moves its share against the
survivor-weighted mean, two-sided and clipped, and the three are renormalised so they always sum
to one. UNMEASURED (no survivors in the window, or a tier with no costed hours) leaves the
default standing with `applied: false` and the reason -- a missing measurement moves no seconds.

WHO READS IT. `data/compute_policy.json` carries a per-department factor (tier share over the
tier's default share) that `research_departments.spend()` folds into its elastic factor the way
it folds in the delayed-credit ROI, and a forest factor that `libs/research/forests.allocation_for`
applies to a forest's budget -- both two-sided, both reading exactly 1.0 when the policy is
UNMEASURED, so a policy that has not been earned changes nothing. `research_evolution` reads the
split as its selection shares.

MULTI-FIDELITY EARLY STOPPING is a RECOMMENDATION, published from the gate-verdict ledger: the
share of every family's cells killed at each rung of the gauntlet says how much of the gauntlet's
compute a cheap rung recovers and what promotion rate a successive-halving schedule would use.
Nothing here changes a gate, a threshold or a budget: it prices, and the organs that spend read
the price.

    python desks/mt5/research/compute_economics.py --once [--budget-s 300] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DATA = DESK / "data"
REPORTS = DESK / "reports"
COMPUTE_LEDGER = DATA / "compute_ledger.jsonl"
GRAPH = DATA / "hypothesis_graph.jsonl"
GATE_LEDGER = DATA / "hypotheses" / "gate_verdict_ledger.jsonl"
API_LEDGER = DATA / "research_api_calls.jsonl"
FOREST_ALLOCATION = DATA / "forest_allocation.json"
ROI_REPORT = REPORTS / "RESEARCH_ROI.json"
POLICY = DATA / "compute_policy.json"
OUT = REPORTS / "COMPUTE_ECONOMICS.json"

UNMEASURED = "UNMEASURED"
WINDOW_DAYS = 30
BUDGET_S = 300.0
DEFAULT_SPLIT: dict[str, float] = {"exploitation": 0.70, "exploration": 0.20, "frontier": 0.10}
TIERS: tuple[str, ...] = ("exploitation", "exploration", "frontier")
#: How far a measured tier may move from its default, per pass, and the gain on the deviation
#: from the survivor-weighted mean rate. Two-sided: above the mean rises, below falls.
POLICY_CLIP = (0.5, 1.5)
POLICY_GAIN = 0.25

#: Departments whose legs are exploitation compute; every other research department is
#: exploration; the frontier is named by LEG because it cuts across departments. `meta` is the
#: machine running the machine and is reported as OVERHEAD outside the split.
EXPLOIT_DEPARTMENTS: frozenset[str] = frozenset({"validate", "forward", "execution", "discovery"})
OVERHEAD_DEPARTMENTS: frozenset[str] = frozenset({"meta", "rest"})
FRONTIER_LEGS: frozenset[str] = frozenset({
    "residual_hunt", "unseen_frontier", "world_lab", "research_evolution", "coverage_tensor",
    "source_frontier", "exogenous_search", "qd_frontier", "residual_queue", "world_model",
    "representation_forge", "missed_trade_archaeologist"})
#: hypothesis-graph `source` prefix -> the tier that minted the cell.
SOURCE_TIER: dict[str, str] = {
    "external": "exploitation", "miner": "exploration", "fund_playbook": "exploration",
    "alpha_evolution": "exploration", "residual": "frontier", "coverage_gap": "frontier",
    "world_model": "frontier", "research_evolution": "frontier", "qd_frontier": "frontier"}
#: hypothesis-graph `source` prefix -> search family (the machinery that proposed the cell).
SOURCE_FAMILY: dict[str, str] = {
    "external": "external_gauntlet_sweep", "miner": "moat_miners",
    "fund_playbook": "fund_playbook", "alpha_evolution": "grammar_evolution",
    "residual": "residual_hunt", "coverage_gap": "coverage_tensor",
    "world_model": "world_model", "research_evolution": "meta_evolution",
    "qd_frontier": "qd_frontier", "program_alpha_lane": "program_ir",
    "research_tree": "mcts_tree", "trajectory_evolution": "trajectory_evolution"}
try:
    from miner_specialisation import GATE_ORDER
except Exception:
    GATE_ORDER = ("economic_prior", "in_sample_screen", "deflated_sharpe", "pbo", "cpcv",
                  "cost_stress", "regime_stability", "forward", "replication", "swap_cost")


# --------------------------------------------------------------------------------- utilities
def _now() -> datetime:
    return datetime.now(tz=UTC)


def _iso(t: datetime | None = None) -> str:
    return (t or _now()).isoformat(timespec="seconds")


def _at(v: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _jsonl(path: Path, since: datetime | None = None) -> tuple[list[dict[str, Any]], str | None]:
    if not path.exists():
        return [], f"absent: {path}"
    out: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not isinstance(row, dict):
                continue
            if since is not None:
                t = _at(row.get("at") or row.get("time"))
                if t is None or t < since:
                    continue
            out.append(row)
    except OSError as exc:
        return [], f"unreadable: {exc}"
    return out, None


def _atomic_write(path: Path, doc: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    try:
        os.replace(tmp, path)
    except PermissionError:
        path.write_bytes(tmp.read_bytes())
        tmp.unlink(missing_ok=True)
    return path


def _rate(num: float, hours: float) -> float | None:
    return round(num / hours, 6) if hours > 0 else None


def leg_department() -> tuple[dict[str, str], str]:
    try:
        from research_departments import leg_departments
        legs, _names = leg_departments()
        return legs, "hourly_cycle.LEG_DEPARTMENT"
    except Exception as exc:
        return {}, f"hourly_cycle unavailable ({type(exc).__name__}); every leg reads `rest`"


def leg_layer() -> dict[str, str]:
    try:
        from libs.research.layers import LEG_LAYER
        return dict(LEG_LAYER)
    except Exception:
        return {}


def tier_of(leg: str, dept: str) -> str:
    if leg in FRONTIER_LEGS:
        return "frontier"
    if dept in OVERHEAD_DEPARTMENTS:
        return "overhead"
    if dept in EXPLOIT_DEPARTMENTS:
        return "exploitation"
    return "exploration"


# --------------------------------------------------------------------------------- the joins
def compute_by(rows: list[dict[str, Any]], legs: dict[str, str],
               layers: dict[str, str]) -> dict[str, dict[str, dict[str, float]]]:
    """Wall/CPU hours and run counts, grouped four ways off one pass over the ledger."""
    groups: dict[str, dict[str, dict[str, float]]] = {
        k: defaultdict(lambda: {"wall_h": 0.0, "cpu_h": 0.0, "runs": 0.0, "failed": 0.0})
        for k in ("department", "forest", "tier", "layer", "leg")}
    for r in rows:
        leg = str(r.get("run") or "?")
        dept = legs.get(leg, "rest")
        wall = float(r.get("wall_s") or 0.0) / 3600.0
        cpu = float(r.get("cpu_s") or 0.0) / 3600.0
        failed = 1.0 if str(r.get("outcome") or "ok") != "ok" else 0.0
        keys = {"department": dept, "tier": tier_of(leg, dept),
                "layer": layers.get(leg, "unassigned"), "leg": leg}
        if leg.startswith("forest_"):
            keys["forest"] = leg[len("forest_"):]
        elif dept in ("japan", "macro"):
            keys["forest"] = dept
        for g, key in keys.items():
            b = groups[g][key]
            b["wall_h"] += wall
            b["cpu_h"] += cpu
            b["runs"] += 1.0
            b["failed"] += failed
    return {g: {k: {kk: round(vv, 6) for kk, vv in v.items()} for k, v in d.items()}
            for g, d in groups.items()}


def survivors_by(graph: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Certified cells in the window by tier and by search family, from the graph's `source`."""
    by_tier: Counter[str] = Counter()
    by_family: Counter[str] = Counter()
    born_family: Counter[str] = Counter()
    for r in graph:
        prefix = str(r.get("source") or "?").split(":")[0]
        fam = SOURCE_FAMILY.get(prefix, prefix)
        if str(r.get("fate")) == "CERTIFIED":
            by_tier[SOURCE_TIER.get(prefix, "exploration")] += 1
            by_family[fam] += 1
        born_family[fam] += 1
    return {"tier": dict(by_tier), "family": dict(by_family), "born_family": dict(born_family)}


def data_pounds(api_rows: list[dict[str, Any]], why: str | None) -> dict[str, Any]:
    """Pounds spent on data and API calls. The ledger has never carried a cost on this box, so
    this reads UNMEASURED by name until it does; a count of calls is published beside it."""
    if why:
        return {"status": UNMEASURED, "why": f"API ledger {why}; the data-pound term is "
                                              f"UNMEASURED, never 0", "calls": 0, "gbp": None}
    gbp = 0.0
    priced = 0
    for r in api_rows:
        for key in ("gbp", "cost_gbp", "cost"):
            v = r.get(key)
            if isinstance(v, (int, float)):
                gbp += float(v)
                priced += 1
                break
    if priced == 0:
        return {"status": UNMEASURED, "why": f"{len(api_rows)} API call(s) logged, none priced "
                                              f"in pounds", "calls": len(api_rows), "gbp": None}
    return {"status": "MEASURED", "calls": len(api_rows), "priced_calls": priced,
            "gbp": round(gbp, 4)}


def roi_rates(roi: Any) -> dict[str, Any]:
    """The ROI organ's per-generator and per-region credited value per compute hour, read as
    published -- never re-derived."""
    out: dict[str, Any] = {"generators": {}, "regions": {}, "status": UNMEASURED}
    if not isinstance(roi, dict):
        out["why"] = f"{ROI_REPORT.name} absent or unreadable"
        return out
    sci = roi.get("scientist_roi") if isinstance(roi.get("scientist_roi"), dict) else {}
    for gen, row in sci.items():
        if isinstance(row, dict):
            out["generators"][str(gen)] = {
                "credited_survivors": row.get("credited_survivors"),
                "independent_survivors": row.get("independent_survivors"),
                "credited_delta_elogw": row.get("credited_delta_elogw"),
                "compute_hours": row.get("compute_hours"), "roi": row.get("roi"),
                "roi_status": row.get("roi_status")}
    reg = roi.get("region_roi") if isinstance(roi.get("region_roi"), dict) else {}
    per = reg.get("by_region") if isinstance(reg.get("by_region"), dict) else {}
    for r, row in per.items():
        if isinstance(row, dict):
            out["regions"][str(r)] = {"roi": row.get("roi"), "roi_status": row.get("roi_status")}
    out["status"] = "MEASURED" if (out["generators"] or out["regions"]) else UNMEASURED
    out["at"] = roi.get("at")
    return out


# --------------------------------------------------------------------------------- the policy
def learn_split(tier_compute: dict[str, dict[str, float]],
                tier_survivors: dict[str, int]) -> dict[str, Any]:
    """The 70/20/10 prior moved by measured survivors per hour, two-sided, clipped, renormalised.

    UNMEASURED when any research tier has no costed hours or no tier produced a survivor in the
    window: a split learned from nothing is the default wearing a measurement's clothes.
    """
    hours = {t: float((tier_compute.get(t) or {}).get("wall_h") or 0.0) for t in TIERS}
    surv = {t: int(tier_survivors.get(t) or 0) for t in TIERS}
    rates = {t: _rate(surv[t], hours[t]) for t in TIERS}
    total_surv = sum(surv.values())
    total_h = sum(hours.values())
    if any(h <= 0 for h in hours.values()):
        missing = [t for t in TIERS if hours[t] <= 0]
        return {"status": UNMEASURED, "applied": False, "split": dict(DEFAULT_SPLIT),
                "factors": dict.fromkeys(TIERS, 1.0), "rates": rates,
                "why": f"no costed hours for tier(s) {missing} in the window"}
    if total_surv <= 0:
        return {"status": UNMEASURED, "applied": False, "split": dict(DEFAULT_SPLIT),
                "factors": dict.fromkeys(TIERS, 1.0), "rates": rates,
                "why": "no certified survivor in the window in any tier: no rate to follow"}
    mean_rate = total_surv / total_h
    factors: dict[str, float] = {}
    for t in TIERS:
        raw = 1.0 + POLICY_GAIN * ((rates[t] or 0.0) - mean_rate) / mean_rate
        factors[t] = round(max(POLICY_CLIP[0], min(POLICY_CLIP[1], raw)), 4)
    moved = {t: DEFAULT_SPLIT[t] * factors[t] for t in TIERS}
    z = sum(moved.values())
    split = {t: round(moved[t] / z, 4) for t in TIERS}
    # rounding must not break the sum-to-one contract downstream organs pin
    drift = round(1.0 - sum(split.values()), 4)
    if drift:
        split["exploitation"] = round(split["exploitation"] + drift, 4)
    return {"status": "MEASURED", "applied": True, "split": split, "factors": factors,
            "rates": rates, "mean_rate": round(mean_rate, 6),
            "why": (f"{total_surv} survivor(s) over {total_h:.2f}h; each tier's share moved by "
                    f"{POLICY_GAIN} x its rate's deviation from the mean, clipped to "
                    f"{list(POLICY_CLIP)}, renormalised")}


def policy_doc(split: dict[str, Any], legs: dict[str, str], names: list[str]) -> dict[str, Any]:
    """`data/compute_policy.json`: the split plus the two-sided factors its consumers read."""
    applied = bool(split.get("applied"))
    tier_factor = {t: (round(split["split"][t] / DEFAULT_SPLIT[t], 4) if applied else 1.0)
                   for t in TIERS}
    dept_factor: dict[str, float] = {}
    for d in sorted(set(names) | set(legs.values())):
        tier = tier_of("", d)
        dept_factor[d] = tier_factor.get(tier, 1.0) if tier in tier_factor else 1.0
    return {
        "at": _iso(), "status": split["status"], "applied": applied,
        "split": split["split"], "default_split": dict(DEFAULT_SPLIT),
        "tier_factors": tier_factor,
        "factors": {"departments": dept_factor, "forests": tier_factor["exploration"]},
        "rates": split.get("rates"), "why": split.get("why"),
        "consumers": ["desks/mt5/research/research_departments.py spend() (policy_factors)",
                      "libs/research/forests.py allocation_for (policy factor on budget_s)",
                      "desks/mt5/research/research_evolution.py (selection shares)"],
        "rule": ("70/20/10 exploitation/exploration/frontier is the PRIOR; measured survivors per "
                 "hour move each share two-sided and the three always sum to one; UNMEASURED "
                 "reads 1.0 everywhere downstream and moves nothing"),
        "writer": "desks/mt5/research/compute_economics.py",
    }


# --------------------------------------------------------------------------------- fidelity
def fidelity_ladder(gate_rows: list[dict[str, Any]], why: str | None) -> dict[str, Any]:
    """Where cells die on the gauntlet, per family, and the successive-halving schedule that
    implies. A recommendation: it moves no gate."""
    if why:
        return {"status": UNMEASURED, "why": f"gate ledger {why}"}
    per_family: dict[str, Counter[str]] = defaultdict(Counter)
    for r in gate_rows:
        fam = str(r.get("family") or "?")
        gate = str(r.get("terminal_gate") or ("PASSED" if r.get("passed") else "?"))
        per_family[fam][gate] += 1
    ladder = [g for g in GATE_ORDER]
    out: dict[str, Any] = {}
    total_cells = 0
    cheap_kills = 0
    for fam, hist in sorted(per_family.items()):
        n = sum(hist.values())
        total_cells += n
        cum = 0
        rungs: list[dict[str, Any]] = []
        for i, g in enumerate(ladder):
            k = hist.get(g, 0)
            reached = n - cum
            cum += k
            if i < 2:
                cheap_kills += k
            rungs.append({"rung": g, "reached": reached, "killed": k,
                          "promotion_rate": round((reached - k) / reached, 4) if reached else None})
        survivors = n - cum
        first_two = sum(hist.get(g, 0) for g in ladder[:2])
        out[fam] = {
            "cells": n, "survived_all": survivors,
            "killed_on_cheap_rungs": first_two,
            "cheap_rung_share": round(first_two / n, 4) if n else None,
            "rungs": rungs,
            "recommendation": (
                f"successive halving: run every cell through {ladder[0]} and {ladder[1]} "
                f"({round(first_two / n, 2) if n else 0} of this family's cells die there) and "
                f"promote the survivors; the expensive rungs then see "
                f"{max(0, n - first_two)} cell(s) instead of {n}"),
        }
    return {"status": "MEASURED" if out else UNMEASURED, "ladder": ladder,
            "families": out, "cells": total_cells,
            "gauntlet_compute_recoverable_share": (round(cheap_kills / total_cells, 4)
                                                   if total_cells else None),
            "rule": ("a cell killed on a cheap rung should never have reached an expensive one; "
                     "the share killed there is the gauntlet compute a Tier-0/1 screen recovers. "
                     "Published as a recommendation -- no gate, threshold or budget moves here")}


# --------------------------------------------------------------------------------- the pass
def run(*, budget_s: float = BUDGET_S, dry_run: bool = False,
        window_days: int = WINDOW_DAYS) -> dict[str, Any]:
    t0 = time.monotonic()
    now = _now()
    since = now - timedelta(days=window_days)
    unmeasured: list[dict[str, str]] = []
    legs, legs_basis = leg_department()
    layers = leg_layer()
    ledger, ledger_why = _jsonl(COMPUTE_LEDGER, since)
    if ledger_why:
        unmeasured.append({"what": "compute ledger", "why": ledger_why})
    graph, graph_why = _jsonl(GRAPH, since)
    if graph_why:
        unmeasured.append({"what": "hypothesis graph", "why": graph_why})
    api_rows, api_why = _jsonl(API_LEDGER)
    gate_rows, gate_why = _jsonl(GATE_LEDGER, since)
    roi = _read(ROI_REPORT)
    forest_alloc = _read(FOREST_ALLOCATION)

    comp = compute_by(ledger, legs, layers)
    surv = survivors_by(graph)
    pounds = data_pounds(api_rows, api_why)
    if pounds["status"] != "MEASURED":
        unmeasured.append({"what": "data pounds", "why": str(pounds.get("why"))})
    rates = roi_rates(roi)
    if rates["status"] != "MEASURED":
        unmeasured.append({"what": "research ROI", "why": str(rates.get("why") or "no rows")})

    total_surv = sum(surv["tier"].values())
    by_department: dict[str, Any] = {}
    for d, c in sorted(comp["department"].items()):
        by_department[d] = {**c, "tier": tier_of("", d),
                            "survivors_per_wall_hour": None, "survivors_per_cpu_hour": None,
                            "status": UNMEASURED if c["wall_h"] <= 0 else "COSTED"}
    by_tier: dict[str, Any] = {}
    for t in (*TIERS, "overhead"):
        c = comp["tier"].get(t, {"wall_h": 0.0, "cpu_h": 0.0, "runs": 0.0, "failed": 0.0})
        s = int(surv["tier"].get(t, 0))
        by_tier[t] = {**c, "survivors": s,
                      "survivors_per_wall_hour": _rate(s, c["wall_h"]),
                      "survivors_per_cpu_hour": _rate(s, c["cpu_h"]),
                      "survivors_per_data_pound": (_rate(s, float(pounds["gbp"]))
                                                   if pounds.get("gbp") else None),
                      "status": ("MEASURED" if c["wall_h"] > 0 and total_surv > 0
                                 else UNMEASURED)}
    by_family: dict[str, Any] = {}
    fam_hours = {"grammar_evolution": comp["leg"].get("alpha_evolution", {}).get("wall_h"),
                 "mcts_tree": comp["leg"].get("research_tree", {}).get("wall_h"),
                 "program_ir": comp["leg"].get("program_alpha_lane", {}).get("wall_h"),
                 "external_gauntlet_sweep": comp["leg"].get("external_gauntlet", {}).get("wall_h"),
                 "residual_hunt": comp["leg"].get("residual_hunt", {}).get("wall_h"),
                 "coverage_tensor": comp["leg"].get("coverage_tensor", {}).get("wall_h"),
                 "meta_evolution": comp["leg"].get("research_evolution", {}).get("wall_h"),
                 "trajectory_evolution": comp["leg"].get("trajectory_evolution", {}).get("wall_h"),
                 "qd_frontier": comp["leg"].get("qd_frontier", {}).get("wall_h")}
    for fam in sorted(set(surv["family"]) | set(surv["born_family"]) | set(fam_hours)):
        h = fam_hours.get(fam)
        s = int(surv["family"].get(fam, 0))
        by_family[fam] = {"survivors": s, "born": int(surv["born_family"].get(fam, 0)),
                          "wall_h": round(float(h), 6) if isinstance(h, (int, float)) else None,
                          "survivors_per_wall_hour": (_rate(s, float(h))
                                                      if isinstance(h, (int, float)) else None),
                          "status": ("MEASURED" if isinstance(h, (int, float)) and h > 0
                                     else UNMEASURED)}
    by_forest: dict[str, Any] = {}
    forests = forest_alloc.get("forests") if isinstance(forest_alloc, dict) else None
    for fid in sorted(set(comp["forest"]) | set(forests or {})):
        c = comp["forest"].get(fid, {"wall_h": 0.0, "cpu_h": 0.0, "runs": 0.0, "failed": 0.0})
        given = (forests or {}).get(fid) if isinstance(forests, dict) else None
        rr = rates["regions"].get(fid, {})
        by_forest[fid] = {**c, "allocated": given, "region_roi": rr.get("roi"),
                          "region_roi_status": rr.get("roi_status", UNMEASURED),
                          "status": "COSTED" if c["wall_h"] > 0 else UNMEASURED}

    split = learn_split(comp["tier"], surv["tier"])
    names = sorted({*legs.values(), *EXPLOIT_DEPARTMENTS, "intel", "data", "macro", "japan",
                    "regions", "meta", "rest"})
    policy = policy_doc(split, legs, names)
    fidelity = fidelity_ladder(gate_rows, gate_why)
    if fidelity["status"] != "MEASURED":
        unmeasured.append({"what": "fidelity ladder", "why": str(fidelity.get("why"))})

    report = {
        "at": _iso(now), "window_days": window_days, "budget_s": budget_s,
        "elapsed_s": round(time.monotonic() - t0, 2), "dry_run": dry_run,
        "law": "LAWS 5m/5k -- compute follows delayed real truth with an exploration budget",
        "legs_basis": legs_basis,
        "ledger": {"rows": len(ledger), "legs": len(comp["leg"]),
                   "wall_h": round(sum(c["wall_h"] for c in comp["leg"].values()), 4),
                   "cpu_h": round(sum(c["cpu_h"] for c in comp["leg"].values()), 4)},
        "survivors": {"certified_in_window": total_surv, "by_tier": surv["tier"],
                      "by_family": surv["family"]},
        "data_pounds": pounds,
        "by_tier": by_tier, "by_department": by_department, "by_forest": by_forest,
        "by_search_family": by_family,
        "by_layer": {k: v for k, v in sorted(comp["layer"].items())},
        "roi": rates,
        "policy": policy,
        "early_stopping": fidelity,
        "unmeasured": unmeasured,
        "limitations": [
            "survivors are certified cells in the window by graph source; a department's own "
            "survivor count needs the cell->leg join the graph does not carry, so departments "
            "are costed and tiers are rated",
            "the data-pound term is UNMEASURED until research_api_calls.jsonl carries a cost",
        ],
    }
    if not dry_run:
        _atomic_write(POLICY, policy)
        _atomic_write(OUT, report)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--days", type=int, default=WINDOW_DAYS)
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s, dry_run=a.dry_run, window_days=a.days)
    pol = doc["policy"]
    print(f"compute economics ({a.days}d): {doc['ledger']['rows']} costed runs, "
          f"{doc['ledger']['wall_h']}h wall; {doc['survivors']['certified_in_window']} "
          f"survivor(s); policy {pol['status']} split {pol['split']}; early stopping "
          f"{doc['early_stopping']['status']}"
          + ("; DRY RUN, nothing written" if a.dry_run else f" -> {OUT}"))
    for u in doc["unmeasured"]:
        print(f"  UNMEASURED {u['what']}: {u['why']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
