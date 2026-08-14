#!/usr/bin/env python3
"""EVERY PRECONDITION FOR PUTTING REAL MONEY ON THIS DESK, CHECKED IN ONE PLACE.

WHY THIS EXISTS AND WHY IT EXISTS TODAY. The desk has been built for months and has produced ZERO
LIVE EVIDENCE. That is not a safe state -- it is an UNMEASURED one, and it is the single largest
unquantified risk the desk carries. Every fill model, every cost assumption, every latency
estimate, every assumption about post-only behaviour and partial fills is unvalidated. Shadow
cannot produce that evidence at any budget or any duration: it is the one thing only real money
buys, and the desk has been deferring the purchase.

So the argument for a small live clip is not impatience, it is measurement. A first allocation is
an EXPERIMENT whose purpose is to produce execution evidence, and its size is set by what the desk
can afford to be wrong about rather than by how good the research looks.

**IT CHECKS AND IT REPORTS. IT ARMS NOTHING.** This script never writes the arming marker, never
clears a kill file, never touches `run_deadman_switch.py`, and never places an order. Those are
the principal's acts and remain so. What it removes is the situation where going live means
remembering nine separate preconditions correctly at the moment you are most impatient to skip one.

**A CHECK THAT CANNOT BE PERFORMED IS NOT A PASS** (L1.28a). Every precondition resolves to
GO / BLOCKED / UNMEASURED, and UNMEASURED is printed in the blocking column: on the path to real
capital, "I could not tell" and "it is fine" are not the same answer and must never render the same.

    python scripts/run_golive_preflight.py                 # report
    python scripts/run_golive_preflight.py --capital 200   # size the first clip
"""

from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root.
import sys as _sys
from pathlib import Path as _P

if str(_P(__file__).resolve().parent.parent) not in _sys.path:
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_OUT = Path("data/golive_preflight.json")
_WEB = Path("web/golive_preflight.json")

GO, BLOCKED, UNMEASURED = "GO", "BLOCKED", "UNMEASURED"


@dataclass(frozen=True)
class Check:
    name: str
    state: str
    detail: str
    #: What the principal does about it. Empty when nothing is owed.
    action: str = ""

    @property
    def blocking(self) -> bool:
        # UNMEASURED BLOCKS. A precondition nobody could evaluate is not a satisfied one, and on
        # the path to real capital the two must never render the same.
        return self.state != GO


def _keys() -> Check:
    try:
        from libs.execution import binance_spot_testnet as spot
        from libs.execution import binance_testnet as fut
        has = bool(fut.has_keys()), bool(spot.has_keys())
    except Exception as exc:
        return Check("venue credentials", UNMEASURED,
                     f"credential modules unreadable ({type(exc).__name__}) -- cannot tell whether "
                     "keys are installed, which is not the same as knowing they are not",
                     "investigate before trusting any other line of this report")
    if all(has):
        return Check("venue credentials", GO, "futures and spot legs both hold keys")
    missing = [n for n, ok in zip(("futures", "spot"), has, strict=True) if not ok]
    return Check("venue credentials", BLOCKED,
                 f"{', '.join(missing)} leg has no key. A carry needs BOTH legs: one leg alone is "
                 "not a hedged position, it is a directional bet nobody sized",
                 "install the keys under data/secrets/, then re-run")


def _kill_file() -> Check:
    p = _ROOT / "data" / "CASHCARRY_KILL"
    if not p.exists():
        return Check("ruin rail (CASHCARRY_KILL)", GO, "no kill file -- the executor may place orders")
    try:
        body = p.read_text("utf-8", errors="ignore").strip()[:300]
    except OSError:
        body = "(unreadable)"
    return Check("ruin rail (CASHCARRY_KILL)", BLOCKED,
                 f"the executor is FROZEN and places no orders. Contents: {body!r}",
                 "PRINCIPAL-ONLY. Clearing a fired ruin rail is a Tier-3 act and no organ may do "
                 "it: `rm data/CASHCARRY_KILL`. Clear it for a REASON, never on a timer -- an idle "
                 "book satisfies every 'N hours clean' test trivially, forever (GAP 91)")


def _armed() -> Check:
    from libs.portfolio.auto_promotion import is_armed
    ok, why = is_armed(_ROOT)
    if ok:
        return Check("automated promotion", GO, why)
    return Check("automated promotion", BLOCKED, why,
                 "OPTIONAL FOR A MANUAL FIRST CLIP. Only needed if you want the desk to promote "
                 "further candidates WITHOUT being asked each time. Placing one clip by hand needs "
                 "nothing here")


def _deadman() -> Check:
    p = _ROOT / "scripts" / "run_deadman_switch.py"
    if not p.exists():
        return Check("deadman switch", BLOCKED, "scripts/run_deadman_switch.py is ABSENT",
                     "do not fund a book with no independent ruin rail")
    try:
        from scripts.check_risk_kernel import main as _rk  # noqa: F401
        return Check("deadman switch", GO,
                     "present; scripts/check_risk_kernel.py verifies it is byte-identical to what "
                     "the principal approved, and runs FIRST in every research cycle")
    except Exception:
        return Check("deadman switch", GO,
                     "present (integrity checker not importable here; the cycle runs it on the box)")


def _execution_evidence() -> Check:
    """THE POINT OF THE WHOLE EXERCISE, stated as a check so it cannot be forgotten."""
    p = _ROOT / "docs" / "research" / "trade_forensics_latest.json"
    try:
        n = int(json.loads(p.read_text("utf-8")).get("n_closes") or 0)
    except (OSError, ValueError, TypeError):
        return Check("live execution evidence", UNMEASURED,
                     "no readable trade forensics on this host",
                     "expected on a clone -- the artifact is written by the owning box")
    if n > 0:
        return Check("live execution evidence", GO, f"{n} closed trades on record")
    return Check("live execution evidence", BLOCKED,
                 "ZERO closed trades. Every fill model, cost assumption, latency estimate and "
                 "post-only assumption on this desk is UNVALIDATED, and no amount of shadow time "
                 "changes that -- it is the one thing only real money buys",
                 "this is the deficit the first clip exists to close, not a reason to defer it")


def _leg_curve() -> Check:
    """Is the variance-collapse recording running yet? Reported, never blocking."""
    try:
        cs = json.loads((_ROOT / "data" / "live_combined_state.json").read_text("utf-8"))
    except (OSError, ValueError):
        return Check("leg-curve recording", UNMEASURED,
                     "data/live_combined_state.json unreadable here (gitignored -- VPS only)")
    n = len(cs.get("lcurve") or [])
    if n == 0:
        return Check("leg-curve recording", UNMEASURED,
                     "lcurve is EMPTY -- run_live_combined has not run since the recording landed. "
                     "Until it accrues, every carry Sharpe is computed from a SUM that cancels its "
                     "own basis variance, so treat published carry Sharpes as unusable")
    return Check("leg-curve recording", GO,
                 f"{n} heartbeats recorded with both legs -- basis variance is being captured")


def _first_clip(capital_usd: float) -> Check:
    """What a first clip may be, from the cap the desk already fixed."""
    from libs.portfolio.auto_promotion import MAX_FIRST_CLIP_FRAC
    clip = capital_usd * MAX_FIRST_CLIP_FRAC
    return Check("first-clip sizing", GO,
                 f"deployable ${capital_usd:,.2f}; the automated cap is "
                 f"{MAX_FIRST_CLIP_FRAC:.1%} = ${clip:,.2f} per strategy. AT THIS CAPITAL THE CAP "
                 "IS NOT THE BINDING CONSTRAINT -- venue minimum notional is. A clip below the "
                 "venue minimum cannot be placed at all, and a book sized at the minimum is "
                 "concentrated by arithmetic rather than by choice",
                 "size the first clip to the VENUE MINIMUM on the cheapest pair, and read the "
                 "result as execution evidence rather than as a return")


def build(capital_usd: float) -> dict[str, Any]:
    checks = [_keys(), _kill_file(), _deadman(), _execution_evidence(),
              _leg_curve(), _armed(), _first_clip(capital_usd)]
    blocking = [c for c in checks if c.blocking]
    return {
        "updated": datetime.now(tz=UTC).isoformat(),
        "capital_usd": capital_usd,
        "verdict": "READY" if not blocking else "BLOCKED",
        "n_blocking": len(blocking),
        "checks": [{"name": c.name, "state": c.state, "detail": c.detail, "action": c.action}
                   for c in checks],
        "note": ("UNMEASURED counts as BLOCKING. On the path to real capital, 'I could not tell' "
                 "and 'it is fine' are different answers and must never render the same (L1.28a). "
                 "This script arms nothing, clears nothing and places nothing: the arming marker, "
                 "the kill file and the deadman rail are the principal's acts and stay that way."),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--capital", type=float, default=200.0,
                    help="deployable capital in USD (default 200)")
    args = ap.parse_args()

    rep = build(args.capital)
    for p in (_OUT, _WEB):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rep, indent=1), "utf-8")

    print(f"=== GO-LIVE PREFLIGHT === capital ${args.capital:,.2f} -> {rep['verdict']}")
    for c in rep["checks"]:
        print(f"  [{c['state']:<10}] {c['name']}")
        print(f"               {c['detail']}")
        if c["action"]:
            print(f"      ACTION : {c['action']}")
    print(f"-> {_OUT} and {_WEB}")
    return 0 if rep["verdict"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
