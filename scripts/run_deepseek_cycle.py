#!/usr/bin/env python3
"""DEEPSEEK HOURLY RESEARCH CYCLE -- mandate V, the heartbeat of the second flywheel.

RUN ORDER IS THE POLICY, and each step gates the next:

  1. POLICY GATE (CXCV-4/5). Resolve the canonical hash BEFORE anything consequential. A
     mismatch fails VISIBLY and the cycle stops -- research conducted under rules nobody can
     name is research nobody can attribute.
  2. SEAT (IV + the dark-seat rule). No key -> report DARK and EXIT 0. A dark seat is never an
     excuse to stop the desk, and never a reason to fail the scheduler.
  3. IDENTITY (IV). Record the exact provider/model. If the DeepSeek model is unavailable,
     record MODEL_UNAVAILABLE -- never silently substitute another family.
  4. COLD PHASE A (VIII). Build a context of FACTS with every other agent's conclusion stripped,
     then SEAL the output before Phase B may see anyone else's view.
  5. ROUTE (CXCV-18). Findings enter the SAME canonical machinery. No parallel registry.
  6. LABORATORY (third-brain addendum, libs/ops/deepseek_lab.py). Steps 4-5 run as a persistent
     scored job queue over labs A-Q + conversion, k calls a cycle; a dark or spent seat still
     runs the maintenance pass (enqueue, debt drain, feedback, metrics) with zero calls.

EXIT CODES: 0 = ran, or DARK, or nothing to do. 2 = policy gate failed (visible failure).
Never a silent 0 on a policy failure -- that is the one outcome that must wake somebody.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops import deepseek_cycle as ds  # noqa: E402
from libs.ops import deepseek_lab as lab  # noqa: E402
from libs.ops import llm_lab_seats as seats  # noqa: E402

_REPORT = _ROOT / "desks" / "mt5" / "reports" / "DEEPSEEK_RESEARCH.json"


def _publish(report: dict[str, object]) -> None:
    """Publish liveness and the packet hash even on a dark or budget-held cycle.

    UNMEASURED is never rendered as healthy: the report carries the exact result and why, so a
    silent seat cannot read as a working one.
    """
    try:
        _REPORT.parent.mkdir(parents=True, exist_ok=True)
        tmp = _REPORT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(report, indent=1, default=str), "utf-8")
        tmp.replace(_REPORT)
    except OSError:
        pass


def _lab(report: dict[str, object], gate: dict[str, Any], *, calls: int | None
         ) -> dict[str, Any]:
    """Run one laboratory pass. `calls=0` is the maintenance pass a dark or spent seat still
    owes: events and cadences enqueue, coverage debt drains, feedback joins and metrics publish
    -- the research organism stays alive when inference is not available. Never raises."""
    try:
        packet = ds.research_packet(_ROOT)
        report["packet"] = {"status": packet.get("status"), "hash": packet.get("packet_hash"),
                            "sections": packet.get("sections_measured"),
                            "generated_utc": packet.get("generated_utc"),
                            "why": packet.get("why")}
        out = lab.cycle(_ROOT, packet=packet, policy_hash=str(gate.get("policy_hash")),
                        k=calls)
        runs = out.get("runs") or []
        out["result"] = ("OK" if any(r.get("status") == "OK" for r in runs) else
                         "MAINTENANCE_ONLY" if calls == 0 or not runs else "ALL_CALLS_FAILED")
        return out
    except Exception as exc:          # the lab failing must never fail the scheduler
        return {"result": "LAB_ERROR", "why": f"{type(exc).__name__}: {str(exc)[:300]}"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state", default="NORMAL",
                    help="escalation state: LOW_VALUE | NORMAL | MAJOR_DISCOVERY | "
                         "CRITICAL_HIGH_VOI")
    ap.add_argument("--roles", default="", help="comma-separated role subset (default: report all)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    started = datetime.now(tz=UTC).isoformat(timespec="seconds")
    report: dict[str, object] = {"started_utc": started}

    # ---- 1. POLICY GATE, before anything else.
    gate = ds.policy_gate()
    # .get, not []: a gate that REFUSES must still be able to report the refusal. Reading a
    # key the refusing branch cannot supply turns a clean exit-2 verdict into a crash.
    report["policy"] = {"verdict": gate.get("verdict"), "version": gate.get("version"),
                        "hash": gate.get("policy_hash")}
    if not gate["ok"]:
        report["result"] = "BLOCKED_POLICY"
        report["why"] = gate["why"]
        _publish(report)
        print(json.dumps(report, indent=1) if args.json else
              f"DEEPSEEK BLOCKED: {gate['verdict']} -- {gate['why']}")
        return 2

    # ---- 1b. BUDGET, before the seat and before any work. A 24/7 hourly organ against a $20
    # default cap needs only pennies a cycle to exhaust the month, so the check is cheap and
    # early. Exhausted is EXIT 0 -- a spent budget is a normal state, not an outage.
    budget = ds.budget_gate()
    report["budget"] = budget
    if not budget["ok"]:
        report["result"] = "BUDGET_EXHAUSTED"
        report["lab"] = _lab(report, gate, calls=0)
        _publish(report)
        print(json.dumps(report, indent=1) if args.json else
              f"DEEPSEEK HOLD: {budget['why']}")
        return 0

    # ---- 2. SEAT. Dark is a state, not a failure.
    seat = ds.seat_state()
    report["seat"] = {"lit": seat.lit, "provider": seat.provider, "why": seat.why}
    if not seat.lit and not seats.local_seat(dict(os.environ))[0]:
        report["result"] = "DARK"
        report["lab"] = _lab(report, gate, calls=0)
        mix = ds.escalation_mix(args.state)
        report["would_run"] = {"roles": len(ds.SEED_ROLES), "escalation": mix}
        _publish(report)
        if args.json:
            print(json.dumps(report, indent=1))
        else:
            print(f"DEEPSEEK DARK -- {seat.why}")
            print(f"  policy RESOLVED {gate['version']} ({str(gate['policy_hash'])[:26]}...)")
            print(f"  {len(ds.SEED_ROLES)} seed roles registered; escalation "
                  f"{mix['state']} = {mix['bulk_share']:.0%} bulk / {mix['deep_share']:.0%} deep")
            print("  export OPENROUTER_API_KEY to light the seat. Exit 0 by design: the desk's "
                  "improvement rate must not depend on a credential.")
        return 0

    # ---- 3. IDENTITY. Every job records the seat that actually answered.
    available = bool(seat.bulk_model) or bool(seats.local_seat(dict(os.environ))[0]) \
        or bool(seats.refresh_models(_ROOT).get("models") or [])
    ident = ds.record_identity(provider=seat.provider, model=seat.bulk_model or "<unset>",
                               available=available)
    report["identity"] = ident
    if not available:
        report["result"] = "MODEL_UNAVAILABLE"
        _publish(report)
        print(json.dumps(report, indent=1) if args.json else
              "DEEPSEEK MODEL_UNAVAILABLE: DEEPSEEK_BULK_MODEL is unset. Recorded rather than "
              "substituted -- a silent substitution would corrupt the only measurement this "
              "flywheel exists to produce.")
        return 0

    # ---- 4/5. THE LABORATORY (third-brain addendum 6-13, 21, 25-27). The single role per hour
    # is replaced by a persistent, scored job queue over labs A-Q + conversion: events and
    # cadences enqueue, measured downstream yield orders, k calls run, and every object is
    # validated, frozen, de-duplicated and routed into the SAME compiler and gauntlet. The old
    # `run_role` stays importable; `--roles` still runs it for a named seed role on demand.
    if args.roles:
        want = [s.strip() for s in args.roles.split(",") if s.strip()]
        roles = [r for r in ds.SEED_ROLES if r[0] in want] or [ds.SEED_ROLES[0]]
        packet = ds.research_packet(_ROOT)
        result = ds.run_role(roles[0][0], roles[0][1], deep=False, state=packet, root=_ROOT)
        report["result"] = result["status"]
        report["role"] = roles[0][0]
        report["run"] = result
    else:
        lab_out = _lab(report, gate, calls=None)
        report["lab"] = lab_out
        report["result"] = lab_out.get("result", "OK")
    report["authority"] = ("RESEARCH GENERATION ONLY -- cannot promote a survivor, allocate "
                           "capital, override policy or merge authoritative code (CXCV-12..15)")
    _publish(report)
    if args.json:
        print(json.dumps(report, indent=1))
    else:
        lab_doc: dict[str, Any] = report.get("lab") or {}  # type: ignore[assignment]
        runs: list[dict[str, Any]] = lab_doc.get("runs") or []
        print(f"DEEPSEEK {report['result']}: {len(runs)} lab job(s) "
              f"{[(r.get('lab'), r.get('status')) for r in runs]}; queue "
              f"{(lab_doc.get('metrics') or {}).get('queue', {}).get('pending')} pending; "
              f"debt {(lab_doc.get('debt') or {}).get('owed')} owed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
