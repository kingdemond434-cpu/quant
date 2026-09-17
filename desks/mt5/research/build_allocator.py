"""THE DAILY BUILD ALLOCATOR -- of everything the desk could build today, what is worth building.

    "Only the highest-value machinery gets built."                   -- the principal, 2026-09-17

WHAT IT REPLACES. The desk had seven separate queues of things-to-build and no way to compare
them: the Tier-1 ledger's PARTIAL rows with their `next_step`, wiring_ceo's unwired organs, the
scout roster's open beats, the conversion ledger's unexplained debt, the gap map's data holes,
module_rent's MERGE and REDUCE verdicts, and four R5 specs held deliberately as prose. Each was
sorted by its own organ's idea of urgency, none of them priced, and the ordering between them
was whichever artifact a session happened to open. That is how a desk builds the ninth miner
before the first backfill: not by deciding wrongly, but by never putting the two on one page.

THE PRICE. Everything here is one ratio:

    BuildPriority = E[delta orthogonal candidate yield]
                    / (BuildCost + MaintenanceCost + ComplexityCost)

The numerator comes from the candidate's CLASS, measured where the desk has the number and
UNMEASURED-with-a-prior where it does not -- and the row always says which:

    scout          the roster's median leads-per-source x P(testable), both measured
    wiring         the organ's own measured candidates while it ran, else the census median
    compiler_fix   unexplained conversion-debt cells x the measured conversion rate
    data_backfill  the hole's declared value, from the gap map
    tier1          the measured candidates of the organs its evidence names, else the 0.5 prior
    merge/reduce   the compute hours it frees x the census median candidates per compute hour
    spec           0.5 prior x whether its unblock trigger is MEASURED MET (0 when it is not)

The denominator is the declared LOC of the class (CLASS_LOC, in units of LOC_PER_UNIT), plus the
target module's own 30-day maintenance history, plus its complexity -- all three from
MODULE_RENT_RESEARCH.json where a target exists, the class defaults where it does not.

THE COMPLEXITY BUDGET, and it is the part that binds. A candidate that adds a PERMANENT
SUBSYSTEM must either REPLACE an older one by name, or show

    delta Value > LAMBDA x delta Complexity          (LAMBDA = 1.0 candidate per kLOC, declared)

Otherwise it is not refused -- it is FILED AS LAB, built as an experiment with no clock, where it
costs nothing until it earns its way out. The desk is anti-timid by standing order: the budget
never says no, it says "not yet permanent".

LAB -> SHADOW -> CANONICAL, measured, never asserted:

    LAB        built, on no clock
    SHADOW     on probation (probation_state.json), or auto-clocked with < 7 clean runs
    CANONICAL  a named leg with >= CANONICAL_CLEAN_RUNS clean runs AND a consumer

REPORT ONLY. Nothing here builds anything, opens a ticket or edits a cycle. It ranks, and a
session or the CEO docket picks off the top.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = DESK / "reports" / "BUILD_ALLOCATOR.json"
TIER1 = ROOT / "docs" / "research" / "tier1_program.json"
WIRING = DESK / "reports" / "WIRING_CEO.json"
RENT = DESK / "reports" / "MODULE_RENT_RESEARCH.json"
GAP_MAP = DESK / "reports" / "RESEARCH_GAP_MAP.json"
SCOUTS = DESK / "reports" / "SCOUT_ROSTER.json"
ROW_CONVERSION = DESK / "reports" / "ROW_CONVERSION.json"
CONVERSION_LEDGER = DESK / "data" / "conversion_ledger.json"
LIVE_LEDGER = DESK / "data" / "live_ledger.jsonl"
MARKOUT = DESK / "reports" / "markout.json"
PF_ALLOCATION = DESK / "reports" / "pf_allocation.json"
PROBATION_STATE = DESK / "data" / "probation_state.json"
AUTO_LEGS = DESK / "data" / "auto_legs.json"

#: The complexity exchange rate: one expected orthogonal candidate per kLOC of permanent
#: subsystem. Declared, visible, and the only number the budget turns on.
LAMBDA = 1.0
LOC_PER_UNIT = 100.0
PRIOR = 0.5
MIN_COST = 1e-3
CANONICAL_CLEAN_RUNS = 7

#: Declared build size per class, in lines of code. These are estimates and they are labelled as
#: estimates: the point is that a 20-line wiring row and a 600-line spec are not the same bet.
CLASS_LOC: dict[str, int] = {
    "wiring": 20, "reduce": 20, "merge": 200, "compiler_fix": 120,
    "data_backfill": 150, "scout": 250, "tier1": 300, "spec": 600,
}
#: Which classes add a PERMANENT SUBSYSTEM and therefore face the complexity budget. A wiring
#: row, a cadence change and a compiler fix add no subsystem: they change what already exists.
PERMANENT: frozenset[str] = frozenset({"scout", "spec", "data_backfill", "tier1"})
#: Where a built candidate LANDS, before the budget has its say.
STAGE_IF_BUILT: dict[str, str] = {
    "wiring": "SHADOW", "reduce": "CANONICAL", "merge": "CANONICAL",
    "compiler_fix": "CANONICAL", "data_backfill": "SHADOW", "scout": "SHADOW",
    "tier1": "SHADOW", "spec": "LAB",
}

#: THE FOUR R5 SPECS, held as prose on purpose (tier1_program.json R5): each would be a module
#: with no data and no caller today, which is III.16, so the TRIGGER is the disposition. The
#: allocator's job is to check them daily and open the item the hour one is measured met.
R5_SPECS: dict[str, dict[str, Any]] = {
    "crowding_decay_monitor": {
        "trigger": ">= 30 closed trades per sleeve with a realized R", "loc": 450,
        "reads": "desks/mt5/data/live_ledger.jsonl"},
    "meta_labeling": {
        "trigger": ">= 200 live samples on one primary sleeve", "loc": 500,
        "reads": "desks/mt5/data/live_ledger.jsonl"},
    "capacity_model": {
        "trigger": "markouts populated AND deliberate size variation in the fills", "loc": 400,
        "reads": "desks/mt5/reports/markout.json + live_ledger"},
    "regime_conditioned_sizing": {
        "trigger": "portfolio vol targeting live (the allocator armed on a measured regime)",
        "loc": 350, "reads": "desks/mt5/reports/pf_allocation.json"},
}


# --------------------------------------------------------------------------- readers
def _read(p: Path) -> dict[str, Any]:
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def _jsonl(p: Path, tail: int = 200_000) -> list[dict[str, Any]]:
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


def _atomic(p: Path, payload: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, p)


def paths_for(rt: Path) -> dict[str, Path]:
    """Every input, derived from ONE root, so a test can plant a whole synthetic tree."""
    if Path(rt) == ROOT:
        return {"tier1": TIER1, "wiring": WIRING, "rent": RENT, "gap": GAP_MAP,
                "scouts": SCOUTS, "row_conversion": ROW_CONVERSION,
                "conversion_ledger": CONVERSION_LEDGER, "live": LIVE_LEDGER,
                "markout": MARKOUT, "pf": PF_ALLOCATION, "probation": PROBATION_STATE,
                "auto_legs": AUTO_LEGS, "out": OUT}
    rt = Path(rt)
    d, rp, dt = rt / "desks" / "mt5", rt / "desks" / "mt5" / "reports", \
        rt / "desks" / "mt5" / "data"
    return {"tier1": rt / "docs" / "research" / "tier1_program.json",
            "wiring": rp / "WIRING_CEO.json", "rent": rp / "MODULE_RENT_RESEARCH.json",
            "gap": rp / "RESEARCH_GAP_MAP.json", "scouts": rp / "SCOUT_ROSTER.json",
            "row_conversion": rp / "ROW_CONVERSION.json",
            "conversion_ledger": dt / "conversion_ledger.json",
            "live": dt / "live_ledger.jsonl", "markout": rp / "markout.json",
            "pf": rp / "pf_allocation.json", "probation": dt / "probation_state.json",
            "auto_legs": dt / "auto_legs.json", "out": rp / "BUILD_ALLOCATOR.json",
            "_desk": d}


# --------------------------------------------------------------------------- the R5 triggers
def _per_sleeve(rows: list[dict[str, Any]]) -> dict[str, int]:
    n: dict[str, int] = defaultdict(int)
    for r in rows:
        if r.get("sleeve") and r.get("r_multiple") is not None:
            n[str(r["sleeve"])] += 1
    return dict(n)


def triggers(pp: dict[str, Path]) -> dict[str, dict[str, Any]]:
    """Each of the four, measured from the artifact that owns it. An absent artifact is
    UNMEASURED -- which is NOT the same as a trigger that is measured and not met, and the two
    must never collapse into one `False` (L1.28a)."""
    out: dict[str, dict[str, Any]] = {}
    live = _jsonl(pp["live"])
    per = _per_sleeve(live)
    best = max(per.values()) if per else 0
    if not pp["live"].exists():
        no_live = {"met": "UNMEASURED", "evidence": f"{pp['live']} absent"}
        out["crowding_decay_monitor"] = dict(no_live)
        out["meta_labeling"] = dict(no_live)
    else:
        name = max(per, key=lambda k: per[k]) if per else "none"
        out["crowding_decay_monitor"] = {
            "met": best >= 30,
            "evidence": f"best sleeve {name} has {best} closed trades with a realized R "
                        f"(need 30); {len(per)} sleeve(s) in the ledger"}
        out["meta_labeling"] = {
            "met": best >= 200,
            "evidence": f"best sleeve {name} has {best} live samples (need 200)"}

    mk = _read(pp["markout"])
    vols = {round(float(r.get("volume") or 0.0), 4) for r in live if r.get("volume")}
    if not pp["markout"].exists():
        out["capacity_model"] = {"met": "UNMEASURED", "evidence": f"{pp['markout']} absent"}
    else:
        matched = int(mk.get("n_matched") or 0)
        out["capacity_model"] = {
            "met": bool(matched > 0 and len(vols) >= 2),
            "evidence": f"markout n_matched={matched} (usable={mk.get('usable')}), "
                        f"{len(vols)} distinct fill sizes in the live ledger (need >= 2)"}

    pf = _read(pp["pf"])
    if not pf:
        out["regime_conditioned_sizing"] = {"met": "UNMEASURED",
                                            "evidence": f"{pp['pf']} absent or unreadable"}
    else:
        armed = bool(pf.get("armed"))
        regime = pf.get("regime") or pf.get("macro_regime")
        heat = pf.get("effective_heat")
        out["regime_conditioned_sizing"] = {
            "met": bool(armed and regime and heat is not None),
            "evidence": f"pf_allocation armed={armed}, regime={'present' if regime else 'absent'},"
                        f" effective_heat={'present' if heat is not None else 'absent'}"}
    return out


# --------------------------------------------------------------------------- stages
def stage_of(module: str, probation: dict[str, Any], auto: dict[str, Any],
             clock: str | None, consumers: int) -> str:
    """LAB / SHADOW / CANONICAL, from the artifacts that own each."""
    hist = probation.get("history") if isinstance(probation.get("history"), dict) else {}
    legs = {str(x.get("organ")): x for x in (auto.get("legs") or []) if isinstance(x, dict)}
    clean = int((hist.get(module) or {}).get("clean", 0) or 0)
    if module in hist or module in legs:
        return "CANONICAL" if (clean >= CANONICAL_CLEAN_RUNS and consumers > 0) else "SHADOW"
    if not clock or clock == "none":
        return "LAB"
    return "CANONICAL" if consumers > 0 else "SHADOW"


# --------------------------------------------------------------------------- candidate sources
def _rent_index(rent: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(r.get("module")): r for r in (rent.get("rows") or []) if isinstance(r, dict)}


def _median(values: list[float]) -> float | None:
    arr = np.array([v for v in values if v is not None], dtype=float)
    return float(np.median(arr)) if arr.size else None


def from_tier1(doc: dict[str, Any], rent_idx: dict[str, dict[str, Any]],
               census_med: float | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in doc.get("items") or []:
        if not isinstance(item, dict) or str(item.get("status")) != "PARTIAL":
            continue
        step = str(item.get("next_step") or "").strip()
        if not step:
            continue
        ev = [str(e) for e in (item.get("evidence") or []) if isinstance(e, str)]
        named = [p for e in ev for p in re.findall(r"[\w/]+\.py", e)]
        got = [float(rent_idx[p]["candidates_30d"]) for p in named
               if p in rent_idx and rent_idx[p].get("candidates_30d") is not None]
        if got:
            yld = float(np.mean(got))
            basis = f"mean measured candidates of {len(got)} named file(s)"
        elif census_med is not None:
            yld, basis = PRIOR * census_med, "0.5 prior x the census median candidates"
        else:
            yld, basis = PRIOR, "0.5 prior: UNMEASURED, nothing measured this item's files"
        replaces = None
        low = step.lower()
        for word in ("replace", "supersede", "instead of", "retire", "in place of"):
            if word in low:
                replaces = f"its own next_step names a replacement ({word})"
                break
        out.append({"candidate": f"{item['id']}: {step[:180]}", "class": "tier1",
                    "source": "docs/research/tier1_program.json", "target": named[0]
                    if named else None, "expected_yield": yld, "yield_basis": basis,
                    "replaces": replaces})
    return out


def unwired_rows(wiring: dict[str, Any],
                 rent_idx: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    """The unwired organs, from wiring_ceo's artifact when it exists on this host and from the
    rent census's own measured `clock` column when it does not. Measured 2026-09-17: WIRING_CEO
    .json had never been written on the trading box, so the first draft of this allocator
    produced no wiring candidate at all and said UNMEASURED -- true, and useless, when the rent
    report beside it already carries a clock for every one of 1,151 modules."""
    rows = [r for r in (wiring.get("unwired") or []) if isinstance(r, dict) and r.get("organ")]
    if rows:
        return rows, "desks/mt5/reports/WIRING_CEO.json"
    rows = [{"organ": m, "suggested_clock": "hourly_cycle (probation first)"}
            for m, r in sorted(rent_idx.items())
            if r.get("clock") == "none" and str(m).endswith(".py")]
    return rows, "desks/mt5/reports/MODULE_RENT_RESEARCH.json (clock column)"


def from_wiring(rows: list[dict[str, Any]], source: str,
                rent_idx: dict[str, dict[str, Any]],
                census_med: float | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        organ = str(row["organ"])
        r = rent_idx.get(organ) or {}
        got = r.get("candidates_30d")
        if got:
            yld, basis = float(got), "its own measured candidates while it ran"
        elif census_med is not None:
            yld, basis = census_med, "census median candidates (it has never run on a clock)"
        else:
            yld, basis = PRIOR, "0.5 prior: UNMEASURED, no rent report on this host"
        out.append({"candidate": f"wire {organ} ({row.get('suggested_clock')})",
                    "class": "wiring", "source": source, "target": organ,
                    "expected_yield": yld, "yield_basis": basis, "replaces": None})
    return out


def from_rent(rent: dict[str, Any], cand_per_hour: float | None) -> list[dict[str, Any]]:
    """MERGE and REDUCE both FREE COMPUTE; the yield is what that compute buys elsewhere."""
    out: list[dict[str, Any]] = []
    for r in rent.get("rows") or []:
        if not isinstance(r, dict) or r.get("verdict") not in ("MERGE", "REDUCE"):
            continue
        freed = float(r.get("compute_h_30d") or 0.0)
        freed = freed / 2.0 if r["verdict"] == "REDUCE" else freed
        if cand_per_hour is None:
            yld, basis = PRIOR, "0.5 prior: candidates-per-compute-hour is UNMEASURED"
        else:
            yld = freed * cand_per_hour
            basis = (f"{freed:.2f}h freed x {cand_per_hour:.2f} census candidates per "
                     f"compute hour")
        verb = "halve the cadence of" if r["verdict"] == "REDUCE" else \
            f"merge {r['module']} with {r.get('merge_with')}"
        out.append({"candidate": (f"{verb} {r['module']}" if r["verdict"] == "REDUCE" else verb),
                    "class": r["verdict"].lower(),
                    "source": "desks/mt5/reports/MODULE_RENT_RESEARCH.json",
                    "target": str(r["module"]), "expected_yield": yld, "yield_basis": basis,
                    "replaces": str(r.get("merge_with")) if r["verdict"] == "MERGE" else None})
    return out


def from_gap_map(doc: dict[str, Any], top: int) -> list[dict[str, Any]]:
    """The gap map is optional on this host; when it is absent the caller records UNMEASURED
    rather than inventing holes to backfill."""
    holes = doc.get("holes") or doc.get("gaps") or doc.get("rows") or []
    out: list[dict[str, Any]] = []
    for h in holes if isinstance(holes, list) else []:
        if not isinstance(h, dict):
            continue
        status = str(h.get("status") or h.get("why") or "").upper()
        if "DATA_MISSING" not in status:
            continue
        val = h.get("value")
        if val is None:
            yld, basis = PRIOR, "0.5 prior: the hole declares no value"
        else:
            yld, basis = float(val), "the hole's declared value from the gap map"
        out.append({"candidate": f"backfill data for {h.get('cell') or h.get('name') or 'hole'}",
                    "class": "data_backfill",
                    "source": "desks/mt5/reports/RESEARCH_GAP_MAP.json", "target": None,
                    "expected_yield": yld, "yield_basis": basis, "replaces": None})
        if len(out) >= top:
            break
    return out


def from_scouts(doc: dict[str, Any], p_testable: float, p_basis: str) -> list[dict[str, Any]]:
    scouts = [s for s in (doc.get("scouts") or []) if isinstance(s, dict)]
    per_source = [float((s.get("yield") or {}).get("leads") or 0.0)
                  / max(float(s.get("n_sources") or 1.0), 1.0) for s in scouts]
    med = _median(per_source)
    out: list[dict[str, Any]] = []
    for beat in doc.get("open_beats") or []:
        if not isinstance(beat, dict):
            continue
        if med is None:
            yld, basis = PRIOR, "0.5 prior: no scout carries a measured lead count"
        else:
            yld = med * p_testable
            basis = (f"median {med:.2f} leads per source over {len(scouts)} scout(s) x "
                     f"P(testable)={p_testable:.3f} ({p_basis})")
        out.append({"candidate": f"add a scout for {beat.get('ground_or_axis')} "
                                 f"({beat.get('n_grounds')} ground(s) uncovered)",
                    "class": "scout", "source": "desks/mt5/reports/SCOUT_ROSTER.json",
                    "target": str(beat.get("best_scout") or "") or None,
                    "expected_yield": yld, "yield_basis": basis,
                    "replaces": (f"the broken scout {beat.get('best_scout')}"
                                 if beat.get("best_scout") else None)})
    return out


def conversion_debt(pp: dict[str, Path]) -> tuple[int | None, float | None, str]:
    """(unexplained debt cells, conversion rate, basis). The registry owns the debt ledger; the
    ROW_CONVERSION artifact owns the rate. Either may be absent, and then it says so."""
    debt: int | None = None
    basis = []
    try:
        from libs.moat import registry
        d = registry.conversion_debt()
        debt = int(d.get("unexplained_missing_cells") or 0)
        basis.append("registry.conversion_debt()")
    except Exception as exc:
        basis.append(f"registry unreadable ({type(exc).__name__})")
    if debt is None:
        led = _read(pp["conversion_ledger"])
        v = led.get("unexplained_missing_cells")
        if isinstance(v, (int, float)):
            debt = int(v)
            basis.append("data/conversion_ledger.json")
    rc = _read(pp["row_conversion"])
    rows, cands = rc.get("n_rows"), rc.get("n_candidates")
    rate: float | None = None
    if isinstance(rows, (int, float)) and rows and isinstance(cands, (int, float)):
        rate = float(cands) / float(rows)
        basis.append(f"ROW_CONVERSION {cands}/{rows} = {rate:.3f} candidates per mined row")
    else:
        basis.append("ROW_CONVERSION absent: conversion rate UNMEASURED")
    return debt, rate, "; ".join(basis)


def from_conversion(debt: int | None, rate: float | None, basis: str) -> list[dict[str, Any]]:
    if not debt or debt <= 0:
        return []
    if rate is None:
        yld, why = PRIOR, f"0.5 prior: conversion rate UNMEASURED ({basis})"
    else:
        yld, why = float(debt) * rate, f"{debt} unexplained cells x {rate:.3f} ({basis})"
    return [{"candidate": f"fix the compiler: {debt} unexplained conversion-debt cell(s)",
             "class": "compiler_fix", "source": "registry.conversion_debt / ROW_CONVERSION.json",
             "target": "desks/mt5/research/miner_candidate_compiler.py",
             "expected_yield": yld, "yield_basis": why, "replaces": None}]


def from_specs(trig: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name, spec in R5_SPECS.items():
        t = trig.get(name) or {"met": "UNMEASURED", "evidence": "not checked"}
        met = t.get("met")
        if met is True:
            yld, basis = PRIOR, f"0.5 prior x trigger MET: {t.get('evidence')}"
        elif met == "UNMEASURED":
            yld, basis = 0.0, f"trigger UNMEASURED, so the item stays closed: {t.get('evidence')}"
        else:
            yld, basis = 0.0, f"trigger not met: {t.get('evidence')}"
        out.append({"candidate": f"build R5 spec {name} ({spec['trigger']})", "class": "spec",
                    "source": "docs/research/tier1_program.json R5", "target": None,
                    "expected_yield": yld, "yield_basis": basis, "replaces": None,
                    "spec_loc": int(spec["loc"]), "trigger_met": met})
    return out


# --------------------------------------------------------------------------- pricing
def price(c: dict[str, Any], rent_idx: dict[str, dict[str, Any]],
          med_maint: float | None, med_complexity: float | None) -> dict[str, Any]:
    cls = str(c["class"])
    loc = int(c.get("spec_loc") or CLASS_LOC.get(cls, 200))
    build_cost = loc / LOC_PER_UNIT
    tgt = rent_idx.get(str(c.get("target") or ""), {})
    maint = tgt.get("maintenance_commits_30d")
    if maint is None:
        maint = med_maint if med_maint is not None else 0.0
        maint_basis = "census median maintenance (this candidate has no measured target)"
    else:
        maint_basis = f"{int(maint)} commit(s) touched {c['target']} in 30 days"
    cplx = tgt.get("complexity")
    if cplx is None:
        cplx = float(loc) if med_complexity is None else float(med_complexity)
        cplx_basis = f"class LOC estimate {loc} (no measured target)"
    else:
        cplx_basis = f"measured complexity {cplx} of {c['target']}"
    cost = max(build_cost + float(maint) + float(cplx) / 1000.0, MIN_COST)
    return {**c, "cost": round(cost, 4), "build_cost": round(build_cost, 4),
            "maintenance_cost": round(float(maint), 4),
            "complexity_cost": round(float(cplx) / 1000.0, 4),
            "cost_basis": f"{maint_basis}; {cplx_basis}",
            "priority": round(float(c["expected_yield"]) / cost, 5),
            "delta_complexity_kloc": round(loc / 1000.0, 4)}


def apply_complexity_budget(c: dict[str, Any]) -> dict[str, Any]:
    """A permanent subsystem replaces one by name, or beats LAMBDA x delta Complexity, or is
    filed as LAB. Never refused -- the desk does not get more timid, it gets more provisional."""
    stage = STAGE_IF_BUILT.get(str(c["class"]), "LAB")
    if str(c["class"]) not in PERMANENT:
        return {**c, "stage_if_built": stage, "budget": "n/a: adds no permanent subsystem"}
    if c.get("replaces"):
        return {**c, "stage_if_built": stage, "budget": f"REPLACES {c['replaces']}"}
    dv, dc = float(c["expected_yield"]), float(c["delta_complexity_kloc"])
    if dv > LAMBDA * dc:
        return {**c, "stage_if_built": stage,
                "budget": f"delta Value {dv:.3f} > LAMBDA {LAMBDA} x delta Complexity {dc:.3f}"}
    return {**c, "stage_if_built": "LAB",
            "budget": (f"FILED AS LAB: delta Value {dv:.3f} <= LAMBDA {LAMBDA} x delta "
                       f"Complexity {dc:.3f}, and it replaces nothing by name")}


# --------------------------------------------------------------------------- the build
def build(root: Path | None = None, *, top: int = 20,
          now: datetime | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    rt = Path(root) if root is not None else ROOT
    pp = paths_for(rt)
    at = now or datetime.now(tz=UTC)
    unmeasured: list[str] = []

    rent = _read(pp["rent"])
    if not rent:
        unmeasured.append(f"module rent: {pp['rent']} absent; every cost term falls back to its "
                          f"class default and no MERGE/REDUCE candidate exists")
    rent_idx = _rent_index(rent)
    cand_vals = [float(r["candidates_30d"]) for r in rent_idx.values()
                 if r.get("candidates_30d") is not None]
    census_med = _median(cand_vals)
    hours = [float(r["compute_h_30d"]) for r in rent_idx.values()
             if r.get("compute_h_30d")]
    total_h, total_c = float(sum(hours)), float(sum(cand_vals))
    cand_per_hour = (total_c / total_h) if total_h > 0 else None
    if cand_per_hour is None:
        unmeasured.append("candidates per compute hour: no module carries both a candidate count "
                          "and measured hours; MERGE/REDUCE yields use the 0.5 prior")
    med_maint = _median([float(r["maintenance_commits_30d"]) for r in rent_idx.values()
                         if r.get("maintenance_commits_30d") is not None])
    med_complexity = _median([float(r["complexity"]) for r in rent_idx.values()
                              if r.get("complexity") is not None])

    debt, rate, debt_basis = conversion_debt(pp)
    if debt is None:
        unmeasured.append(f"conversion debt: UNMEASURED ({debt_basis}); no compiler_fix candidate")
    p_test, p_basis = PRIOR, "0.5 prior: no measured testable rate"
    scouts_doc = _read(pp["scouts"])
    lead_tot = sum(float((s.get("yield") or {}).get("leads") or 0.0)
                   for s in (scouts_doc.get("scouts") or []) if isinstance(s, dict))
    test_tot = sum(float((s.get("yield") or {}).get("testable") or 0.0)
                   for s in (scouts_doc.get("scouts") or []) if isinstance(s, dict))
    if lead_tot > 0:
        p_test, p_basis = test_tot / lead_tot, f"{test_tot:.0f} testable / {lead_tot:.0f} leads"
    elif rate is not None:
        p_test, p_basis = min(1.0, rate), "ROW_CONVERSION candidates per mined row"
    else:
        unmeasured.append("P(testable): no scout carries leads and ROW_CONVERSION is absent; "
                          "scout yields use the 0.5 prior")

    trig = triggers(pp)
    wiring = _read(pp["wiring"])
    unwired, unwired_src = unwired_rows(wiring, rent_idx)
    if not wiring:
        unmeasured.append(f"wiring census: {pp['wiring']} absent; the unwired set is read from "
                          f"{unwired_src} instead ({len(unwired)} organ(s) on no clock)")
    gap = _read(pp["gap"])
    if not gap:
        unmeasured.append(f"research gap map: {pp['gap']} absent on this host; no data_backfill "
                          f"candidate (its holes are UNMEASURED, not zero)")

    cands: list[dict[str, Any]] = []
    cands += from_tier1(_read(pp["tier1"]), rent_idx, census_med)
    cands += from_wiring(unwired, unwired_src, rent_idx, census_med)
    cands += from_rent(rent, cand_per_hour)
    cands += from_gap_map(gap, top)
    cands += from_scouts(scouts_doc, p_test, p_basis)
    cands += from_conversion(debt, rate, debt_basis)
    cands += from_specs(trig)

    probation, auto = _read(pp["probation"]), _read(pp["auto_legs"])
    priced = [apply_complexity_budget(price(c, rent_idx, med_maint, med_complexity))
              for c in cands]
    for c in priced:
        tgt = rent_idx.get(str(c.get("target") or ""))
        if tgt is not None and c["class"] in ("reduce", "merge", "compiler_fix"):
            c["stage_if_built"] = stage_of(str(c["target"]), probation, auto,
                                           str(tgt.get("clock") or "none"),
                                           1 if tgt.get("clock") != "none" else 0)
        c["why"] = f"{c['yield_basis']} / {c['cost_basis']}; {c['budget']}"
    priced.sort(key=lambda d: (-float(d["priority"]), str(d["candidate"])))

    by_class: dict[str, int] = defaultdict(int)
    for c in priced:
        by_class[str(c["class"])] += 1
    lab = sum(1 for c in priced if c["stage_if_built"] == "LAB")
    doc = {
        "at": at.isoformat(timespec="seconds"),
        "n_candidates": len(priced),
        "elapsed_s": round(time.monotonic() - t0, 2),
        "by_class": dict(sorted(by_class.items())),
        "ranked": [{k: v for k, v in c.items() if k != "yield_basis"} for c in priced[:top]],
        "triggers": trig,
        "complexity_budget": {"lambda": LAMBDA, "filed_as_lab": lab,
                              "unit": "expected orthogonal candidates per kLOC",
                              "permanent_classes": sorted(PERMANENT),
                              "rule": ("a permanent subsystem replaces one by name or shows "
                                       "delta Value > LAMBDA x delta Complexity; otherwise it is "
                                       "built as LAB, with no clock")},
        "stages": {"LAB": "built, on no clock",
                   "SHADOW": "on probation, or auto-clocked with < "
                             f"{CANONICAL_CLEAN_RUNS} clean runs",
                   "CANONICAL": f"a named leg with >= {CANONICAL_CLEAN_RUNS} clean runs and a "
                                f"consumer"},
        "inputs": {"census_median_candidates": census_med,
                   "candidates_per_compute_hour": cand_per_hour,
                   "p_testable": round(p_test, 4), "p_testable_basis": p_basis,
                   "conversion_debt_cells": debt, "conversion_rate": rate,
                   "median_maintenance_commits": med_maint},
        "unmeasured": unmeasured,
        "formula": ("BuildPriority = E[delta orthogonal candidate yield] / (BuildCost + "
                    "MaintenanceCost + ComplexityCost)"),
        "rule": ("only the highest-value machinery gets built; every new permanent subsystem "
                 "replaces one or proves its value exceeds its complexity"),
    }
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="rank and print; write nothing")
    ap.add_argument("--top", type=int, default=20)
    a = ap.parse_args(argv)
    doc = build(top=a.top)
    print(f"build allocator: {doc['n_candidates']} candidate(s) in {doc['elapsed_s']}s; "
          + ", ".join(f"{k}={v}" for k, v in doc["by_class"].items())
          + f"; filed as LAB {doc['complexity_budget']['filed_as_lab']}")
    for c in doc["ranked"]:
        print(f"  {c['priority']:>9.4f} {c['class']:<14} {c['stage_if_built']:<9} "
              f"{c['candidate'][:74]}")
    for name, t in doc["triggers"].items():
        print(f"  trigger {name:<28} {t['met']!s:<11} {t['evidence'][:66]}")
    for u in doc["unmeasured"]:
        print(f"  UNMEASURED: {u}")
    if a.dry_run:
        return 0
    _atomic(OUT, doc)
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
