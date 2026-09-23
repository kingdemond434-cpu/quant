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

THE SHADOW PRICE NOW ALLOCATES (review R4, 2026-09-17). Naming the binding resource and then
spending nothing against it is a price nobody pays: `factors` was an elastic REPORT, clipped to
[0.75, 1.5], that `research_budget` multiplied in whether or not a single input behind it had
been measured. `spend()` publishes the ALLOCATING block beside it -- the same two-sided rule,
referenced to the MEDIAN measured marginal value of the binding resource, clipped to the
consumer's own [0.5, 2.0] so the exchange can never hand out a factor `research_budget` would
clip away -- and stamps it `authoritative` ONLY when every input behind it is measured. An
unmeasured input does not silently become a 1.0 that still gets multiplied: it becomes
`authoritative: false` with the reason, the budget falls back to the reporting factor, and
RESEARCH_BUDGET.json records which of the two actually decided the leg's seconds.

A department scaled BELOW 1.0 is a reduction, so it carries its missed-growth line
(`spend.missed_growth_lines`) in the department's own measured units -- what the seconds it did
not get would have bought at its own measured rate. Growth governance rule 1 in the one place
this organ can reduce anything.

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
#: The ALLOCATING clip, and it is deliberately the consumer's own: `research_budget.FLOOR/CEIL`.
#: A factor outside it would be clipped there anyway, so publishing one would be publishing a
#: decision that does not survive the trip. 0.5 is the floor a department is already guaranteed.
SPEND_CLIP = (0.5, 2.0)
#: How hard the spend block leans on the median. The reporting factor uses 0.25 against the mean;
#: this one allocates, so it leans twice as hard -- still bounded by SPEND_CLIP in both
#: directions, and a department at the median is left at exactly 1.0.
SPEND_GAIN = 0.5
#: The measured denominator for each resource the exchange can name. A resource with no
#: denominator can still BIND -- it just cannot be spent against, and saying so is the difference
#: between an authoritative allocation and a number that merely looks like one.
RESOURCE_DENOMINATOR: dict[str, str | None] = {
    "compute": "compute hours in the window, measured in data/compute_ledger.jsonl",
    "forward_slots": None,   # needs a measured queue depth per department
    "data": None,            # needs a measured value per UNMEASURED axis cell, per department
    "sample": None,          # needs a measured value per additional trade, per department
}
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


def productivity(row: dict[str, Any]) -> float:
    """A department's measured research value per compute-hour: certified survivors plus a tenth
    of a novel hypothesis. ONE definition, read by both the reporting factor and the spend
    block -- two definitions of "value per hour" is how the report and the allocation come to
    disagree about which department is winning."""
    return (row.get("certified_per_hour") or 0.0) + 0.1 * (row.get("novel_per_hour") or 0.0)


def marginal_value(depts: dict[str, dict[str, Any]],
                   resource: str | None) -> tuple[dict[str, float | None], str | None]:
    """({department: marginal value per unit of `resource`}, the denominator) -- or (all None,
    None) when the desk has no measured denominator for that resource.

    Only `compute` has one today: the ledger measures hours per department, and the graph and the
    novelty gate measure what those hours bought. Forward slots, data axes and statistical sample
    all BIND in principle and none of them is measured PER DEPARTMENT, so the honest answer is
    that they cannot be spent against yet -- not a fabricated proxy that would let an unmeasured
    axis move real seconds.
    """
    denom = RESOURCE_DENOMINATOR.get(str(resource or ""))
    if denom is None:
        return dict.fromkeys(depts, None), None
    out: dict[str, float | None] = {}
    for name, row in depts.items():
        out[name] = productivity(row) if row.get("status") == "MEASURED" else None
    return out, denom


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        return 0.0
    mid = n // 2
    return ordered[mid] if n % 2 else 0.5 * (ordered[mid - 1] + ordered[mid])


#: THE DELAYED-CREDIT ROI INPUT (LAWS 5f rule 10, 2026-09-17). `research_roi.py` prices every
#: department by the measured ROI of the generators inside it and publishes a share per
#: department; this block folds that share into the seconds, two-sided and floored.
#:
#: THE PATH IS DERIVED FROM `OUT` AT CALL TIME, ON PURPOSE. A module constant would be read from
#: the live box during this organ's own tests -- which repoint `OUT` into a tmp tree and nothing
#: else -- so the suite's verdict would depend on what the trading box happened to have written
#: this hour. Deriving it keeps the pair moving together and the tests hermetic.
ROI_FILENAME = "research_allocation.json"
#: How stale the ROI file may be before it stops moving seconds. A share computed from last
#: week's yields is a claim about a desk that no longer exists.
ROI_MAX_AGE_H = 24.0


def _roi_path(out: Path | None = None) -> Path:
    base = (out or OUT).parent
    return (base.parent / "data" / ROI_FILENAME) if base.name == "reports" \
        else base / "data" / ROI_FILENAME


def roi_shares(out: Path | None = None) -> tuple[dict[str, float], str]:
    """(share per department, why). Empty means UNMEASURED and reallocates nothing."""
    p = _roi_path(out)
    doc = _read(p)
    block = doc.get("departments") if isinstance(doc.get("departments"), dict) else {}
    if not block:
        return {}, f"no ROI allocation at {p.name}: the research ROI organ has not published one"
    if str(block.get("status")) != "MEASURED":
        return {}, f"ROI allocation is {block.get('status')}: {block.get('why') or 'no reason'}"
    at = _at(doc.get("at"))
    if at is None:
        return {}, "ROI allocation carries no readable stamp"
    age_h = (datetime.now(tz=UTC) - at).total_seconds() / 3600.0
    if age_h > ROI_MAX_AGE_H:
        return {}, f"ROI allocation is {age_h:.1f}h old (max {ROI_MAX_AGE_H}h)"
    shares = block.get("shares") if isinstance(block.get("shares"), dict) else {}
    out_shares = {str(k): float(v) for k, v in shares.items()
                  if isinstance(v, (int, float))}
    return out_shares, (f"delayed-credit ROI shares from {p.name}, {age_h:.1f}h old, floored at "
                        f"{block.get('floor_share')}")


POLICY_FILENAME = "compute_policy.json"


def policy_factors(depts: dict[str, dict[str, Any]], out: Path | None = None) -> dict[str, Any]:
    """THE COMPUTE-ECONOMICS POLICY as a two-sided factor per department (LAWS 5m/5k).

    `compute_economics` publishes the exploitation / exploration / frontier split it LEARNED from
    survivors per hour and, for each department, the ratio of its tier's share to that tier's
    default -- above 1.0 when the tier earned more than its prior, below when less. Read here
    exactly as `roi_factors` reads the delayed-credit ROI: clipped to `SPEND_CLIP`, and reading
    EXACTLY 1.0 for every department when the policy is absent, unreadable, or UNMEASURED (its
    own `applied` false). A policy that has not been earned moves no seconds.
    """
    base = (out or OUT).parent
    p = ((base.parent / "data" / POLICY_FILENAME) if base.name == "reports"
         else base / "data" / POLICY_FILENAME)
    doc = _read(p)
    names = sorted(depts)
    factors = dict.fromkeys(names, 1.0)
    if not doc:
        return {"applied": False, "factors": factors, "split": None,
                "why": f"no compute policy at {p.name}: the compute-economics organ has not "
                       f"published one; every department reads 1.0"}
    if not doc.get("applied") or str(doc.get("status")) != "MEASURED":
        return {"applied": False, "factors": factors, "split": doc.get("split"),
                "why": f"compute policy is {doc.get('status')}: {doc.get('why') or 'no reason'}; "
                       f"every department reads 1.0"}
    raw = (doc.get("factors") or {}).get("departments") if isinstance(doc.get("factors"),
                                                                       dict) else None
    if not isinstance(raw, dict):
        return {"applied": False, "factors": factors, "split": doc.get("split"),
                "why": "compute policy carries no per-department factors; every department "
                       "reads 1.0"}
    for d in names:
        v = raw.get(d)
        if isinstance(v, (int, float)):
            factors[d] = round(max(SPEND_CLIP[0], min(SPEND_CLIP[1], float(v))), 3)
    return {"applied": True, "factors": factors, "split": doc.get("split"),
            "why": (f"compute policy {doc.get('status')} from {p.name}: split "
                    f"{doc.get('split')} learned from survivors per hour, two-sided"),
            "rule": ("a department in a tier that earned more survivors per hour than its "
                     "70/20/10 prior gets more elastic seconds, one that earned fewer gets "
                     "fewer; clipped, never zero, and UNMEASURED reads 1.0")}


def roi_factors(depts: dict[str, dict[str, Any]], out: Path | None = None) -> dict[str, Any]:
    """The ROI share as a TWO-SIDED factor about the equal share: above it gets more, below gets
    less, clipped, and an unpriced department reads exactly 1.0. Never a cap and never zero."""
    shares, why = roi_shares(out)
    names = sorted(depts)
    factors = dict.fromkeys(names, 1.0)
    if not shares or not names:
        return {"applied": False, "why": why, "factors": factors, "shares": {}}
    equal = 1.0 / len(names)
    for d in names:
        s = shares.get(d)
        if isinstance(s, float) and equal > 0:
            factors[d] = round(max(SPEND_CLIP[0], min(SPEND_CLIP[1], s / equal)), 3)
    return {"applied": True, "why": why, "factors": factors,
            "shares": {d: shares.get(d) for d in names},
            "rule": ("a department whose generators produced measured downstream value gets a "
                     "larger share of the elastic seconds and one that produced none gets a "
                     "smaller one -- floored, never zero, and the total is conserved")}


def spend(depts: dict[str, dict[str, Any]], binding: dict[str, Any],
          window_days: int, roi: dict[str, Any] | None = None,
          policy: dict[str, Any] | None = None) -> dict[str, Any]:
    """THE ALLOCATING BLOCK: the binding resource's seconds follow measured marginal value.

    Above the median gets MORE, below gets less, both bounded by SPEND_CLIP -- the same two-sided
    shape as the reporting factor and never a percentage anyone typed. `authoritative` is true
    only when the resource is named, the desk has a measured denominator for it, every department
    is MEASURED, and the median is positive; otherwise it is false WITH THE REASON and
    `research_budget` falls back to the reporting factor. A missing measurement must not be able
    to move a single second.
    """
    resource = binding.get("binding") if isinstance(binding, dict) else None
    values, denom = marginal_value(depts, resource)
    measured = {d: v for d, v in values.items() if isinstance(v, (int, float))}
    unmeasured = sorted(d for d in depts if d not in measured)
    med = _median(list(measured.values()))
    # THE PIVOT IS THE MEDIAN AND THE SCALE IS THE MEAN, and the two have to be different numbers.
    # Dividing by the median is the obvious form and it is unusable here: on this desk most
    # departments certify nothing in a given week, so the median is routinely 0.0 and (v - med)/med
    # is a division by zero -- the block would be inert exactly when the ranking is clearest.
    # The mean of the measured values is always positive when anything at all was produced, so the
    # rule reads: above the MEDIAN department gets more, measured in units of the desk's AVERAGE
    # productivity. With a zero median nothing lands below 1.0, which is correct -- no department
    # is below a median of zero, and nothing should be reduced when there is nothing to rank.
    scale = (sum(measured.values()) / len(measured)) if measured else 0.0
    factors: dict[str, float] = dict.fromkeys(depts, 1.0)
    if measured and scale > 0:
        for d, v in measured.items():
            raw = 1.0 + (v - med) / scale * SPEND_GAIN
            factors[d] = round(max(SPEND_CLIP[0], min(SPEND_CLIP[1], raw)), 3)
    if resource is None:
        why = "no resource binds measurably this pass: nothing to allocate against"
    elif denom is None:
        why = (f"{resource} binds but the desk measures no per-department denominator for it "
               f"({RESOURCE_DENOMINATOR.get(resource, 'unknown resource')!r}); reported, "
               "never spent")
    elif unmeasured:
        why = (f"{len(unmeasured)} department(s) recorded no compute in the window "
               f"({', '.join(unmeasured)}): an unmeasured department reallocates nothing")
    elif scale <= 0:
        why = ("every measured department bought zero certified survivors and zero novelty this "
               "window: there is no ranking to spend on")
    else:
        why = (f"every input measured: {resource} binds, {denom}, {len(measured)} department(s) "
               f"priced against a median marginal value of {med:.4f} in units of the mean "
               f"{scale:.4f}")
    authoritative = bool(resource is not None and denom is not None and not unmeasured
                         and scale > 0)
    # THE DELAYED-CREDIT ROI, FOLDED IN. The productivity ranking above asks "what did this
    # department's compute buy THIS WINDOW"; the ROI share asks "what did the generators inside it
    # ever produce, credited along the provenance DAG". They are different questions and the
    # second is the slower, truer one, so it multiplies rather than replaces. Both are clipped to
    # the same band, so no combination can drive a department's seconds toward zero.
    #
    # IT IS PASSED IN, NEVER READ HERE. `spend` is the pure function the suite pins its
    # arithmetic on with a fabricated department table; a file read inside it would make that
    # arithmetic depend on what the trading box wrote this hour. `build` does the reading.
    roi = roi if roi is not None else {"applied": False, "factors": dict.fromkeys(depts, 1.0),
                                       "shares": {},
                                       "why": "no ROI passed to spend(): the pure function "
                                              "reallocates on the window's productivity alone"}
    if roi["applied"]:
        for d in factors:
            factors[d] = round(max(SPEND_CLIP[0],
                                   min(SPEND_CLIP[1], factors[d] * roi["factors"][d])), 3)
        why = f"{why}; x delayed-credit ROI ({roi['why']})"
    # THE COMPUTE-ECONOMICS POLICY, FOLDED IN THE SAME WAY (LAWS 5m/5k): the learned 70/20/10
    # split as a per-department factor, two-sided, clipped to the same band, passed in and never
    # read here for the same reason the ROI is. UNMEASURED reads exactly 1.0.
    policy = policy if policy is not None else {"applied": False,
                                                "factors": dict.fromkeys(depts, 1.0),
                                                "split": None,
                                                "why": "no compute policy passed to spend(): "
                                                       "every department reads 1.0"}
    if policy.get("applied"):
        for d in factors:
            factors[d] = round(max(SPEND_CLIP[0],
                                   min(SPEND_CLIP[1],
                                       factors[d] * float(policy["factors"].get(d, 1.0)))), 3)
        why = f"{why}; x compute policy ({policy['why']})"
    return {
        "roi": roi,
        "compute_policy": policy,
        "resource": resource, "authoritative": authoritative, "why": why,
        "denominator": denom, "median_marginal_value": round(med, 6) if measured else None,
        "mean_marginal_value": round(scale, 6) if measured else None,
        "marginal_value": {d: (round(v, 6) if isinstance(v, (int, float)) else None)
                           for d, v in values.items()},
        "unmeasured": unmeasured, "factors": factors, "clip": list(SPEND_CLIP),
        "gain": SPEND_GAIN,
        "missed_growth_lines": _spend_missed_growth(depts, factors, values, authoritative,
                                                    window_days),
        "rule": ("the binding resource's elastic seconds follow measured marginal value against "
                 "the MEDIAN department, in units of the mean: above it gets more, below it gets "
                 f"less, both clipped to {list(SPEND_CLIP)} -- and none of it is applied unless "
                 "`authoritative`"),
    }


def _spend_missed_growth(depts: dict[str, dict[str, Any]], factors: dict[str, float],
                         values: dict[str, float | None], authoritative: bool,
                         window_days: int) -> list[dict[str, Any]]:
    """One line per department the spend block scales BELOW 1.0: what the seconds it did not get
    would have bought at its own measured rate. Published here, never appended to
    data/missed_growth.jsonl -- that ledger is keyed by `libs.portfolio.rails.RAILS` and this
    factor registers no rail; the shape is `forward_slot_ranker`'s."""
    now = datetime.now(tz=UTC)
    lines: list[dict[str, Any]] = []
    for name, factor in sorted(factors.items()):
        if factor >= 1.0:
            continue
        hours = float((depts.get(name, {}).get("compute") or {}).get("hours") or 0.0)
        mv = values.get(name)
        line: dict[str, Any] = {
            "day": now.date().isoformat(), "at": now.isoformat(timespec="seconds"),
            "rail": f"research_spend:{name}", "kind": "opportunity_cost",
            "units": "certified survivors + 0.1 x novel hypotheses, forgone in the window",
            "department": name, "factor": factor, "hours_in_window": round(hours, 3),
            "marginal_value": round(mv, 6) if isinstance(mv, (int, float)) else None,
            "window_days": window_days, "applied": authoritative,
            "why": ("what this department's reduced share of the binding resource costs at its "
                    "own measured rate; `applied` false means the block is not authoritative and "
                    "the reduction was published rather than spent"),
        }
        if isinstance(mv, (int, float)):
            line["value"] = round(-(1.0 - factor) * hours * float(mv), 8)
            line["verdict"] = "COSTS_GROWTH" if line["value"] < 0 else "NOT_BINDING"
        else:
            line["value"] = None
            line["verdict"] = "UNMEASURED"
            line["unmeasured"] = "no measured marginal value for this department"
        lines.append(line)
    return lines


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
    prods = {d: productivity(v) for d, v in depts.items() if v["status"] == "MEASURED"}
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
    binding = binding_resource(depts, _read(SHADOW), _read(POSTERIOR), _read(AXIS))
    return {
        "at": now.isoformat(timespec="seconds"), "window_days": window_days,
        "departments": depts, "factors": factors,
        "floor": ("each department's own scheduled task (HOURLY_PLAN=dept:<name>) is its "
                  "guaranteed baseline; the factor is the elastic part, clipped to "
                  f"{list(FACTOR_CLIP)}"),
        "binding_resource": binding,
        # THE SAME PRICE, SPENT. `factors` above reports; this decides -- but only when every
        # input behind it is measured, which `research_budget` checks and records.
        "spend": spend(depts, binding, window_days, roi_factors(depts),
                       policy_factors(depts)),
        "rule": ("every department runs at full useful throughput on its own clock; spare "
                 "seconds follow measured survivors and novelty per compute-hour; UNMEASURED "
                 "reallocates nothing"),
    }


def department_of(leg: str) -> str:
    legs, _ = leg_departments()
    return legs.get(leg, "rest")


def factor_for(leg: str, doc: dict[str, Any] | None = None) -> float:
    """The department REPORTING factor for a leg (1.0 when unmeasured or unknown)."""
    d = doc if doc is not None else _read(OUT)
    dept = department_of(leg)
    fac = d.get("factors") if isinstance(d.get("factors"), dict) else {}
    try:
        return float(fac.get(dept, 1.0) or 1.0)
    except (TypeError, ValueError):
        return 1.0


def spend_factor_for(leg: str, doc: dict[str, Any] | None = None) -> tuple[float, bool, str]:
    """(factor, authoritative, why) -- what the exchange DECIDES for this leg's department.

    The spend block when it is authoritative; otherwise the reporting factor with `authoritative`
    false and the reason, so a consumer records which of the two set the seconds. The fallback is
    never a silent 1.0: an unmeasured exchange leaves the leg exactly where it was, and the record
    says that is what happened.
    """
    d = doc if doc is not None else _read(OUT)
    block = d.get("spend") if isinstance(d.get("spend"), dict) else {}
    dept = department_of(leg)
    if not block:
        return factor_for(leg, d), False, "no `spend` block on RESEARCH_DEPARTMENTS.json"
    if not block.get("authoritative"):
        return (factor_for(leg, d), False,
                f"exchange not authoritative: {block.get('why') or 'no reason recorded'}")
    fac = block.get("factors") if isinstance(block.get("factors"), dict) else {}
    try:
        value = float(fac.get(dept, 1.0) or 1.0)
    except (TypeError, ValueError):
        return factor_for(leg, d), False, f"spend factor for {dept} unreadable"
    return value, True, (f"{dept} priced against the median marginal value of "
                         f"{block.get('resource')}: {block.get('why')}")


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
    sp = doc["spend"]
    print(f"research departments ({a.days}d): binding resource = "
          f"{doc['binding_resource']['binding']}")
    print(f"  spend: {'AUTHORITATIVE' if sp['authoritative'] else 'reported only'} -- {sp['why']}")
    for d, v in doc["departments"].items():
        c = v["compute"]
        print(f"  {d:<10} {c['hours']:6.2f}h {int(c['runs']):4d} runs  "
              f"born {v['yield']['born']:5d} "
              f"cert {v['yield']['certified']:3d}  novel {v['novelty']['novel']:5d}  "
              f"x{v['factor']:.2f} spend x{sp['factors'].get(d, 1.0):.2f}  {v['status'][:10]}")
    for line in sp["missed_growth_lines"]:
        print(f"  missed growth {line['department']:<10} x{line['factor']:.2f} "
              f"value={line['value']} {line['verdict']}")
    if not a.dry_run:
        print(f"-> {write(doc)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
