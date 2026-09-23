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

EXIT CODES: 0 = ran, or DARK, or nothing to do. 2 = policy gate failed (visible failure).
Never a silent 0 on a policy failure -- that is the one outcome that must wake somebody.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops import deepseek_cycle as ds  # noqa: E402

_CYCLE_STATE = _ROOT / "data" / "deepseek_cycle_state.json"


def _next_cycle_index() -> int:
    """Persisted round-robin pointer over SEED_ROLES. A counter that resets every run would
    re-run role 0 every hour and never reach role 33 -- the opposite of X's 'every role gets a
    genuine turn.'"""
    try:
        idx = int(json.loads(_CYCLE_STATE.read_text("utf-8")).get("cycle_index", -1)) + 1
    except (OSError, ValueError, TypeError):
        idx = 0
    _CYCLE_STATE.parent.mkdir(parents=True, exist_ok=True)
    _CYCLE_STATE.write_text(json.dumps({"cycle_index": idx, "updated_utc":
                                        datetime.now(tz=UTC).isoformat(timespec="seconds")}),
                            "utf-8")
    return idx


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
        print(json.dumps(report, indent=1) if args.json else
              f"DEEPSEEK HOLD: {budget['why']}")
        return 0

    # ---- 2. SEAT. Dark is a state, not a failure.
    seat = ds.seat_state()
    report["seat"] = {"lit": seat.lit, "provider": seat.provider, "why": seat.why}
    if not seat.lit:
        report["result"] = "DARK"
        mix = ds.escalation_mix(args.state)
        report["would_run"] = {"roles": len(ds.SEED_ROLES), "escalation": mix}
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

    # ---- 3. IDENTITY. Never substitute another family for DeepSeek.
    available = bool(seat.bulk_model)
    ident = ds.record_identity(provider=seat.provider, model=seat.bulk_model or "<unset>",
                               available=available)
    report["identity"] = ident
    if not available:
        report["result"] = "MODEL_UNAVAILABLE"
        print(json.dumps(report, indent=1) if args.json else
              "DEEPSEEK MODEL_UNAVAILABLE: DEEPSEEK_BULK_MODEL is unset. Recorded rather than "
              "substituted -- a silent substitution would corrupt the only measurement this "
              "flywheel exists to produce.")
        return 0

    # ---- 4/5. COLD PHASE + ROUTE. One role per cycle, round-robin over SEED_ROLES (X: no role
    # is favoured by list order), bulk/deep drawn per the state's escalation_mix (IV: not sacred,
    # a starting point). ONE call, matching budget_gate's "checked once, cheaply, before the
    # cycle" design -- a 24/7 hourly organ multiplying calls per cycle is exactly how V's own
    # docstring says a month's budget disappears by the 3rd.
    all_roles = ds.SEED_ROLES
    if args.roles:
        want = {s.strip() for s in args.roles.split(",") if s.strip()}
        all_roles = tuple(r for r in all_roles if r[0] in want) or all_roles
    idx = _next_cycle_index()
    role_name, role_brief = all_roles[idx % len(all_roles)]
    mix = ds.escalation_mix(args.state)
    deep = random.random() < mix["deep_share"]  # noqa: S311 -- research-cadence draw, not security

    result = ds.run_role(role_name, role_brief, deep=deep, state={}, root=_ROOT)
    report["result"] = result["status"]
    report["role"] = role_name
    report["cycle_index"] = idx
    report["escalation"] = mix
    report["deep_this_cycle"] = deep
    report["run"] = result
    report["authority"] = ("RESEARCH GENERATION ONLY -- cannot promote a survivor, allocate "
                           "capital, override policy or merge authoritative code (CXCV-12..15)")
    if args.json:
        print(json.dumps(report, indent=1))
    else:
        print(f"DEEPSEEK {result['status']}: role={role_name} "
              f"({'deep' if deep else 'bulk'}:{result.get('model', '?')}) -- "
              f"{result.get('n_findings', 0)} finding(s), "
              f"{result.get('capability_walks_proposed', 0)} capability walk(s), "
              f"{result.get('why', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
