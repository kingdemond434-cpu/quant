#!/usr/bin/env python3
"""THE FORMAL-CLAIM FENCE: the order protocol is called VERIFIED only when the gateway backs it.

    python scripts/check_formal_claim.py [--require-state] [--json]

Reads `desks/mt5/reports/tier_s/FORMAL.json` (the formal organ's hourly model check, AST
conformance of the real send sites, and the counterexample traces driven through the real
decision core) and derives the claim with `libs/tiers/formal.claim`:

    VERIFIED     every invariant PROVEN in the model, every knob its proof rests on present at
                 the gateway's send sites, and no counterexample admitted by the decision core
    MODEL_ONLY   the model is proven, the implementation does not yet back every invariant --
                 the knobs it lacks are named; the desk may say "model proven", never "verified"
    VIOLATED     an invariant fails in the desk's OWN protocol model
    UNMEASURED   FORMAL.json absent, unreadable, stale (> 3h) or bounded

WHAT FAILS. A VIOLATED model always fails: a protocol the desk runs that its own checker breaks is
a law-gate event. A REGRESSION fails: fewer implementation-backed invariants than the best ever
recorded by `tier_s.organ_formal_claim` (a send site lost a knob it had). UNMEASURED fails only
with `--require-state` (the box, where tier_s runs hourly and an absent report is an organ that
did not run). MODEL_ONLY passes -- it is the truth stated, with its debt in `self_model` -- because
closing it is a money-path change this fence must never force by going permanently red.

It writes nothing: the hourly half (`organ_formal_claim`) publishes
`desks/mt5/reports/tier_s/FORMAL_CLAIM.json` and holds the ratchet.

Exit: 2 on VIOLATED, on a regression, or (with --require-state) on UNMEASURED; 0 otherwise.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops.fence_exit import fence_exit  # noqa: E402

FORMAL = ROOT / "desks" / "mt5" / "reports" / "tier_s" / "FORMAL.json"
RATCHET = ROOT / "desks" / "mt5" / "data" / "tier_s" / "formal_claim.json"
#: MODEL_ONLY is the honest state of a proven model the gateway does not fully implement
_PASSING = frozenset({"VERIFIED", "MODEL_ONLY"})
_PASSING_NO_STATE = _PASSING | {"UNMEASURED"}


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def measure(formal_path: Path = FORMAL, ratchet_path: Path = RATCHET) -> dict[str, Any]:
    from libs.tiers import formal
    best = (_read(ratchet_path) or {}).get("best_implemented")
    c = formal.claim(_read(formal_path),
                     best_implemented=int(best) if best is not None else None)
    status = "REGRESSED" if c["regressed"] and c["claim"] != "VIOLATED" else c["claim"]
    return {**c, "status": status, "formal": str(formal_path)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--require-state", action="store_true",
                    help="an absent or stale FORMAL.json is a failure (box gate)")
    ap.add_argument("--formal", type=Path, default=FORMAL)
    ap.add_argument("--ratchet", type=Path, default=RATCHET)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    doc = measure(a.formal, a.ratchet)
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
    print(f"formal claim: {doc['status']} -- {doc['implemented']}/{doc['of']} invariants backed "
          f"by the gateway (best {doc['best_implemented']}); "
          + ("; ".join(doc["reasons"])[:400] or "every invariant implemented"))
    passing = _PASSING if a.require_state else _PASSING_NO_STATE
    return fence_exit(doc["status"], passing, fail=2)


if __name__ == "__main__":
    raise SystemExit(main())
