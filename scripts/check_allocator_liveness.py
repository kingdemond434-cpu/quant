#!/usr/bin/env python3
"""FENCE: the allocator produced, proved and published THIS cycle, on inputs it can name.

THE DEFECT THIS EXISTS FOR (2026-09-23). A read-only probe reported the allocation and the
certificate ABSENT and concluded the desk's money brain was dead. Both files were minutes old --
at `desks/mt5/reports/pf_allocation.json` and at the REPO ROOT's `reports/ALLOCATOR_PROOF.json`,
neither of which the probe looked at. Nothing published where the allocator's outputs live, how
old they may be, or which input each pass conditioned on, so the question "is the allocator
alive" had no answer except a guess, and the guess was wrong in the most dangerous direction.

It fails on exactly four things, each of them a real state the desk can be in:

  * the ALLOCATION is missing or older than its own cadence (two allocator clocks);
  * the PROOF certificate is missing or older than `allocator_proof.MAX_AGE_S` -- without it the
    gateway cannot let the dynamic book size anything, so a dead certificate is a book that
    silently falls back;
  * an INPUT the allocator conditions on is stale and the pass on disk does NOT declare it
    UNMEASURED -- conditioning on yesterday's world while reporting today's is the failure mode
    that leaves every artifact looking correct;
  * a cycle produced NEITHER an allocation NOR a named stand-down. Absence must never be
    readable as "the allocator decided not to" (L1.28a).

A HOST WITH NO ALLOCATOR AT ALL IS UNMEASURED, NOT A PASS. On a clean checkout none of the four
artifacts exists and no `PF_ALLOCATOR_ARMED` file was ever written; that is a fact about the
HOST, is reported as UNMEASURED, and is not a verdict about the allocator. `--require-state`
turns that into a failure, which is what the box gate uses: on the trading box an absent
allocator IS the defect.

    python scripts/check_allocator_liveness.py [--json] [--require-state]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: The organ's published report. The fence RE-MEASURES rather than trusting it, but a report
#: that is absent or older than the organ's own clock means the measurement stopped -- and a
#: fence that cannot cash its own gate is exactly what L1.49 forbids.
LIVENESS = DESK / "reports" / "ALLOCATOR_LIVENESS.json"
LIVENESS_MAX_AGE_S = 2 * 3600

#: Any one of these existing means this host HAS an allocator and its silence is a defect.
_EVIDENCE_OF_AN_ALLOCATOR = (
    DESK / "reports" / "pf_allocation.json",
    DESK / "reports" / "DONE_pf_allocation",
    DESK / "data" / "pf_forecast_log.jsonl",
    DESK / "data" / "PF_ALLOCATOR_ARMED",
    ROOT / "reports" / "ALLOCATOR_PROOF.json",
)


def _host_has_allocator() -> bool:
    return any(p.exists() for p in _EVIDENCE_OF_AN_ALLOCATOR)


def check(*, require_state: bool = False) -> dict[str, Any]:
    try:
        from research.allocator_liveness import measure
    except Exception as exc:                                   # pragma: no cover - import guard
        return {"status": "UNMEASURED", "findings": [],
                "why": f"allocator_liveness unimportable ({type(exc).__name__}: {exc})"}
    if not _host_has_allocator():
        return {"status": "FAIL" if require_state else "UNMEASURED",
                "findings": ([{"check": "HOST", "why": "no allocator artifact has ever been "
                                                       "written on this host"}]
                             if require_state else []),
                "why": ("this host has never run the allocator: no allocation, no certificate, "
                        "no forecast log, no arm file. A fact about the HOST, not a verdict "
                        "about the allocator")}
    rep = measure()
    findings = [dict(b) for b in rep.get("breaches") or []]
    # THE ORGAN'S OWN CLOCK. Everything above is re-measured live, so a stale report cannot hide
    # a defect -- but it CAN hide that nobody is looking, which is the quieter failure.
    try:
        age = time.time() - LIVENESS.stat().st_mtime
        if age > LIVENESS_MAX_AGE_S:
            findings.append({"check": "REPORT_STALE",
                             "why": f"reports/ALLOCATOR_LIVENESS.json is {age / 3600:.1f}h old "
                                    f"(> {LIVENESS_MAX_AGE_S / 3600:.0f}h): the liveness leg "
                                    f"stopped publishing"})
    except OSError:
        findings.append({"check": "REPORT_ABSENT",
                         "why": "reports/ALLOCATOR_LIVENESS.json absent: the allocator_liveness "
                                "leg has not run on this host"})
    return {"status": "FAIL" if findings else "OK", "findings": findings,
            "why": str(rep.get("why", ""))[:400], "verdict": rep.get("verdict"),
            "heat": rep.get("heat", {}), "n_inputs_stale": rep.get("n_inputs_stale"),
            "n_inputs_unmeasured": rep.get("n_inputs_unmeasured")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=str(__doc__ or "").split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--require-state", action="store_true",
                    help="a host with no allocator artifact at all FAILS (the box gate)")
    a = ap.parse_args(argv)
    res = check(require_state=a.require_state)
    if a.json:
        print(json.dumps(res, indent=1, default=str))
    else:
        findings: list[dict[str, Any]] = list(res.get("findings") or [])
        print(f"allocator liveness: {res['status']} -- {str(res.get('why', ''))[:240]}")
        heat = res.get("heat") or {}
        if isinstance(heat, dict) and heat.get("status") == "MEASURED":
            lb = heat.get("live_book") or {}
            print(f"  heat resolved={heat.get('resolved')} floor={heat.get('floor')} "
                  f"filled={heat.get('filled')}; live book "
                  f"{lb.get('n_joined')}/{lb.get('n_live')} rows joined, "
                  f"sum_risk_frac={lb.get('sum_risk_frac')}")
        for f in findings:
            print(f"  BREACH {f['check']}: {str(f['why'])[:220]}")
    return 1 if res["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
