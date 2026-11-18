"""The five acceptance properties, MEASURED from the desk's own artifacts -- never asserted.

    python scripts/check_acceptance_properties.py            # measure, write the report, print
    python scripts/check_acceptance_properties.py --ledger   # also copy the verdicts into the
                                                             # programme ledger's AP rows

The principal's 10/10 bar (2026-09-08) is five properties, each with a stated measure:

  AP1  no fixed discovery frontier    frontier cells opened by the system itself, per week
  AP2  no unmeasured intelligence     every seat/miner/organ has a yield row and a rent verdict
  AP3  no semantic breaks             share of closed deals with a complete chain (target 1.0)
  AP4  the portfolio creates missions missions issued per week; candidates tagged by mission
  AP5  the machine improves itself    A/B arms with a recorded verdict

WHY A SCRIPT. Tier-1 item I18 measured that "properties 2 and 3 are the binding ones and both
fail at the same place -- the money end". That was a finding in a sweep; it decays the moment
the artifacts move. This script re-derives every number from the artifact that owns it, on the
box, every hour, and refuses to grade a property whose artifact is absent: UNMEASURED is a
verdict, MET is a number.

The status vocabulary is the ledger's (MET / PARTIAL / MISSING); `measured` says whether the
artifacts existed to decide. A property that reads MISSING because its artifact has not been
produced yet is reported as MISSING with measured=False, which is exactly the distinction the
programme ledger exists to keep.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DESK = ROOT / "desks" / "mt5"
LEDGER = ROOT / "docs" / "research" / "tier1_program.json"
REPORT = DESK / "reports" / "acceptance_properties.json"
WEEK = timedelta(days=7)

#: Missions have no single home yet (wave W5b writes them); every candidate path is read.
MISSION_PATHS = ("reports/RESEARCH_MISSIONS.json", "reports/research_missions.json",
                 "data/research_missions.json", "reports/missions.json", "data/missions.json")


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _stamp(s: Any) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(s))
        return d if d.tzinfo else d.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def _recent(stamps: list[Any], now: datetime) -> int:
    return sum(1 for s in stamps if (d := _stamp(s)) is not None and now - d <= WEEK)


# ------------------------------------------------------------------ AP1 discovery frontier
def ap1(desk: Path, root: Path, now: datetime) -> dict[str, Any]:
    cov = _read(desk / "data" / "hunt_coverage.json")
    uni = _read(desk / "data" / "universe" / "universe.json")
    umap = _read(desk / "data" / "data_universe_map.json")
    if cov is None and uni is None:
        return {"status": "MISSING", "measured": False,
                "why": "neither hunt_coverage.json nor universe.json reached this host"}
    vectors = (cov or {}).get("vectors") or {}
    v_new = _recent([v.get("first_seen") for v in vectors.values() if isinstance(v, dict)], now)
    v_hunted = sum(1 for v in vectors.values() if isinstance(v, dict)
                   and v.get("outcome") in ("YIELDED", "EMPTY"))
    sym_new = 0
    if isinstance(uni, dict):
        sym_new = _recent([((v.get("_provenance") or {}).get("bars") or {}).get("at")
                           for v in uni.values() if isinstance(v, dict)], now)
    try:
        sys.path.insert(0, str(desk))
        from mt5desk.families_orthogonal import ORTHOGONAL_FAMILIES
        fams = len(ORTHOGONAL_FAMILIES)
    except Exception:
        fams = None
    opened = v_new + sym_new
    return {
        "status": "MET" if opened > 0 else "PARTIAL", "measured": True,
        "cells_opened_7d": opened, "frontier_vectors": len(vectors),
        "frontier_vectors_new_7d": v_new, "frontier_vectors_hunted": v_hunted,
        "universe_symbols": len(uni) if isinstance(uni, dict) else None,
        "universe_symbols_new_7d": sym_new,
        "data_universe_map_entries": (len(umap) if isinstance(umap, (dict, list)) else None),
        "registered_families": fams,
        "why": ("frontier vectors are named by the hunters themselves and universe rows by the "
                "bar refresh -- both open without a code change; families still need one"),
    }


# ------------------------------------------------------------------ AP2 unmeasured intelligence
def ap2(desk: Path) -> dict[str, Any]:
    compiled = _read(desk / "data" / "hypotheses" / "miner_candidates.json") or {}
    rent = _read(desk / "reports" / "MODULE_RENT.json")
    from libs.ops.compute_ledger import cost_by_run
    from libs.research.layers import LEG_LAYER
    costs = cost_by_run()
    per_source = compiled.get("per_source") or {}
    seats = compiled.get("seats") or {}
    modules = (rent or {}).get("modules") or {}
    measured_mods = [n for n, r in modules.items()
                     if isinstance(r, dict) and r.get("verdict") not in (None, "UNMEASURED")]
    legs_costed = sorted(set(LEG_LAYER) & set(costs))
    legs_dark = sorted(set(LEG_LAYER) - set(costs))
    seats_dark = list(compiled.get("seats_dark") or [s for s, st in seats.items()
                                                      if isinstance(st, dict) and not st.get("rows")])
    if not compiled and rent is None and not costs:
        return {"status": "MISSING", "measured": False,
                "why": "no compiled artifact, rent ledger or compute ledger on this host"}
    dark = bool(seats_dark) or (modules and len(measured_mods) < len(modules)) or bool(legs_dark)
    return {
        "status": "PARTIAL" if dark else "MET", "measured": True,
        "sources_with_yield_row": len(per_source), "seats": list(seats), "seats_dark": seats_dark,
        "modules": len(modules), "modules_measured": len(measured_mods),
        "modules_unmeasured": sorted(set(modules) - set(measured_mods))[:20],
        "legs": len(LEG_LAYER), "legs_costed": len(legs_costed), "legs_dark": legs_dark,
        "why": ("MET needs every seat donating, every module with a rent verdict and every "
                "leg with a cost row; the lists name what is dark"),
    }


# ------------------------------------------------------------------ AP3 semantic breaks
def ap3(desk: Path) -> dict[str, Any]:
    chain = _read(desk / "reports" / "attribution_chain.json")
    if not isinstance(chain, dict):
        return {"status": "MISSING", "measured": False,
                "why": "reports/attribution_chain.json absent -- the daily cycle has not run "
                       "the attribution join on this host"}
    deals = int(chain.get("deals") or 0)
    share = chain.get("share")
    status = ("MISSING" if deals == 0 else "MET" if share is not None and float(share) >= 1.0
              else "PARTIAL")
    return {"status": status, "measured": deals > 0, "deals": deals,
            "attributed": chain.get("attributed"), "share": share, "target": 1.0,
            "unmatched": (chain.get("unmatched_deals") or [])[:10], "at": chain.get("at"),
            "why": "share of closed strategy deals walked back to an intent, release and state"}


# ------------------------------------------------------------------ AP4 missions
def ap4(desk: Path, now: datetime) -> dict[str, Any]:
    doc, found = None, None
    for rel in MISSION_PATHS:
        doc = _read(desk / rel)
        if doc is not None:
            found = rel
            break
    compiled = _read(desk / "data" / "hypotheses" / "miner_candidates.json") or {}
    cands = compiled.get("hypotheses") or compiled.get("candidates") or []
    tagged = sum(1 for c in cands if isinstance(c, dict)
                 and (c.get("mission_id") or c.get("mission")))
    if doc is None:
        return {"status": "MISSING", "measured": False, "candidates_tagged": tagged,
                "why": f"no missions artifact at any of {MISSION_PATHS}"}
    missions = doc.get("missions") if isinstance(doc, dict) else doc
    missions = missions if isinstance(missions, list) else list((missions or {}).values())
    issued = _recent([m.get("at") or m.get("issued_at") or m.get("created_at")
                      for m in missions if isinstance(m, dict)], now)
    status = "MET" if issued > 0 and tagged > 0 else "PARTIAL" if missions else "MISSING"
    return {"status": status, "measured": True, "source": found, "missions": len(missions),
            "issued_7d": issued, "candidates_tagged": tagged,
            "why": "missions issued this week and candidates that carry the mission that caused them"}


# ------------------------------------------------------------------ AP5 machine improves machine
def ap5(desk: Path) -> dict[str, Any]:
    bandit = _read(desk / "reports" / "RESEARCH_BANDIT.json")
    rent = _read(desk / "reports" / "MODULE_RENT.json")
    if bandit is None and rent is None:
        return {"status": "MISSING", "measured": False,
                "why": "neither RESEARCH_BANDIT.json nor MODULE_RENT.json on this host"}
    arms = (bandit or {}).get("arms") or {}
    arms = arms if isinstance(arms, dict) else {str(i): a for i, a in enumerate(arms)}
    with_verdict = [k for k, a in arms.items() if isinstance(a, dict)
                    and (a.get("verdict") or a.get("retired") is not None or a.get("decision"))]
    retire = (rent or {}).get("retire") or []
    n = len(with_verdict) + len(retire)
    return {"status": "MET" if n > 0 else "PARTIAL", "measured": True,
            "arms": len(arms), "arms_with_verdict": len(with_verdict),
            "rent_retire_named": len(retire),
            "why": "arms judged by survivor yield / realised Elog, plus organs the rent ledger names"}


# ------------------------------------------------- versioned specification completion
#: The acceptance audit's own freshness bound (global_research_acceptance.MAX_RUNTIME_AGE_H).
SPEC_MAX_AGE_H = 26.0


def specification_completion(desk: Path, now: datetime) -> dict[str, Any]:
    """Which acceptance-spec versions the desk may say it is complete against, right now.

    `GLOBAL_RESEARCH_ACCEPTANCE.json` names them in `complete_against`; this is the reader that
    carries that verdict into the hourly acceptance report beside AP1..AP5. A report that is
    absent, unreadable or older than its own freshness bound completes against NOTHING: a stale
    "complete" is a claim the desk cannot cash, so it reads UNMEASURED with an empty list.
    """
    doc = _read(desk / "reports" / "GLOBAL_RESEARCH_ACCEPTANCE.json")
    if not isinstance(doc, dict):
        return {"measured": False, "complete_against": [], "partial_against": [],
                "why": "GLOBAL_RESEARCH_ACCEPTANCE.json absent or unreadable on this host"}
    at = _stamp(doc.get("at"))
    age_h = None if at is None else round((now - at).total_seconds() / 3600.0, 3)
    raw_spec = doc.get("by_specification")
    by_spec: dict[str, Any] = raw_spec if isinstance(raw_spec, dict) else {}
    partial = sorted(k for k, v in by_spec.items()
                     if isinstance(v, dict) and int(v.get("PARTIAL") or 0) > 0)
    base = {"by_specification": by_spec, "partial_against": partial, "age_h": age_h,
            "release": doc.get("release"), "open_blockers": doc.get("open_blockers"),
            "ownerless_blockers": list(doc.get("ownerless_blockers") or [])}
    if age_h is None or age_h > SPEC_MAX_AGE_H or age_h < 0:
        return {**base, "measured": False, "complete_against": [],
                "why": f"acceptance report stamp unusable or stale (age_h={age_h})"}
    claimed = [str(k) for k in doc.get("complete_against") or []]
    # Re-derive rather than trust: a version named complete must have nothing PARTIAL in it.
    complete = sorted(k for k in claimed if k in by_spec and k not in partial)
    return {**base, "measured": True, "complete_against": complete,
            "rejected_claims": sorted(set(claimed) - set(complete)),
            "why": "spec versions with zero PARTIAL requirements in a fresh acceptance audit"}


def measure(desk: Path = DESK, root: Path = ROOT, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    props = {"AP1": ap1(desk, root, now), "AP2": ap2(desk), "AP3": ap3(desk),
             "AP4": ap4(desk, now), "AP5": ap5(desk)}
    met = sum(1 for p in props.values() if p["status"] == "MET")
    unmeasured = [k for k, p in props.items() if not p["measured"]]
    return {"at": now.isoformat(timespec="seconds"), "properties": props,
            "met": met, "of": 5, "unmeasured": unmeasured,
            "score": f"{met}/5 met, {len(unmeasured)} unmeasured",
            "specifications": specification_completion(desk, now)}


def patch_ledger(doc: dict[str, Any], ledger_path: Path = LEDGER) -> int:
    ledger = _read(ledger_path)
    if not isinstance(ledger, dict):
        return 0
    n = 0
    for ap in ledger.get("acceptance_properties", []):
        p = doc["properties"].get(ap.get("id"))
        if not p:
            continue
        ap["status"] = p["status"]
        numbers = {k: v for k, v in p.items() if k not in ("status", "measured", "why")}
        ap["evidence"] = [f"{doc['at']} {'MEASURED' if p['measured'] else 'UNMEASURED'}: "
                          f"{json.dumps(numbers, default=str)[:400]} -- {p['why']}"]
        n += 1
    ledger_path.write_text(json.dumps(ledger, indent=1, ensure_ascii=False), "utf-8")
    return n


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ledger", action="store_true", help="copy verdicts into the programme ledger")
    ap.add_argument("--out", type=Path, default=REPORT)
    args = ap.parse_args(argv)
    doc = measure()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    print(f"acceptance properties: {doc['score']}")
    for k, p in doc["properties"].items():
        print(f"  {k}: {p['status']:8} {'measured' if p['measured'] else 'UNMEASURED'} -- {p['why']}")
    spec = doc["specifications"]
    print(f"  complete against: {spec['complete_against'] or 'nothing'}"
          f" ({'measured' if spec['measured'] else 'UNMEASURED'} -- {spec['why']})")
    if args.ledger:
        print(f"  ledger rows updated: {patch_ledger(doc)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
