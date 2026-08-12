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
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops import deepseek_cycle as ds  # noqa: E402


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
    report["policy"] = {"verdict": gate["verdict"], "version": gate["version"],
                        "hash": gate["policy_hash"]}
    if not gate["ok"]:
        report["result"] = "BLOCKED_POLICY"
        report["why"] = gate["why"]
        print(json.dumps(report, indent=1) if args.json else
              f"DEEPSEEK BLOCKED: {gate['verdict']} -- {gate['why']}")
        return 2

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

    # ---- 4/5. Cold phase and routing run here once the seat is lit on a real box.
    roles = [r for r, _ in ds.SEED_ROLES]
    if args.roles:
        want = {s.strip() for s in args.roles.split(",") if s.strip()}
        roles = [r for r in roles if r in want]
    report["result"] = "READY"
    report["roles"] = roles
    report["escalation"] = ds.escalation_mix(args.state)
    report["authority"] = ("RESEARCH GENERATION ONLY -- cannot promote a survivor, allocate "
                           "capital, override policy or merge authoritative code (CXCV-12..15)")
    print(json.dumps(report, indent=1) if args.json else
          f"DEEPSEEK READY: policy {gate['version']}, {len(roles)} role(s), "
          f"{seat.provider}:{seat.bulk_model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
