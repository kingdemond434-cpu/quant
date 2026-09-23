"""What the search budget bought, per mechanism, and where the next trial should go.

WHY THIS EXISTS (principal blueprint, 2026-08-29)

    "Portfolio-aware discovery from birth... a 1.1-Sharpe genuinely independent mechanism can
     outrank a 2.0-Sharpe clone of an existing strategy."
    "Live-to-research feedback... a family that backtests beautifully but repeatedly decays in
     forward trading should lose future research budget automatically."

Measured the same day, from the desk's own funnel:

    discovered               10,624 candidates ->  7 certificates   0.07%
    session_range_breakout      126 candidates -> 20 certificates  15.87%
    overnight_gap_decay         232 candidates -> 12 certificates   5.17%
    seven other families      1,308 candidates ->  0 certificates   0.00%

`discovered` consumed 85% of every trial the desk spent and returned 17% of its certificates --
227x less productive per trial than `session_range_breakout`. That allocation was never a
decision. It was the residue of which generator happened to emit the most rows, and nothing
measured it, so nothing could act on it.

THIS REPORTS; IT DOES NOT REALLOCATE. The allocation it prints is a recommendation, and it stops
there deliberately. Redirecting the desk's compute is a research-policy change with the same
standing as a gate threshold: it decides what the desk will and will not discover, and a script
that quietly rewrote it every two hours would make the search unauditable -- nobody could say
later why a mechanism went unexplored. The numbers are the contribution; the decision is the
principal's.

WHAT IT WATCHES FOR, beyond the ranking:
  * UNATTRIBUTED rows -- sleeves and certificates whose mechanism nothing records. Currently 84
    forward rows. A sleeve whose mechanism is unknown cannot be reasoned about, cannot be
    credited to a family, and silently shrinks every denominator here.
  * NO_DENOMINATOR families -- certified through a generator that does not write to the shared
    docket, so their pass rate is unknown rather than small (LAWS L1.28a).
  * UNCONFIRMED families -- 100+ attempts, zero certificates. NOT "barren": every one of those
    attempts ran through a validator since found defective in four independent ways, so the zero
    describes the test rather than the mechanism (LAWS L1.49). They keep their exploration floor.

BREADTH IS THE OBJECTIVE, YIELD IS THE TIEBREAK. Every known mechanism receives a guaranteed
share and no mechanism may exceed a cap. That is not a hedge against a good ranking -- it is the
recognition that this desk's binding constraint is INDEPENDENCE (n_eff ~5.5 across 23
certificates), so a search that narrows toward whatever certified last manufactures correlation
and finds more of what the book already holds.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "research_allocation.json"

#: Fixed so two runs an hour apart are comparable. A drifting seed would make every Thompson
#: draw a fresh opinion and the report unreadable as a time series.
SEED = 20260829

#: The notional budget the recommendation is expressed in. Trials, not percent, because the
#: sweep thinks in cells and a percentage would have to be converted by whoever acts on it.
BUDGET = 1000


def main() -> int:
    from libs.research.funnel_census import allocate, build, report

    now = datetime.now(tz=UTC)
    recs = build(ROOT)
    rep = report(recs, seed=SEED)
    alloc = allocate(recs, BUDGET, seed=SEED)

    print(f"RESEARCH ALLOCATION {now.isoformat(timespec='seconds')}")
    print(f"  {rep['total_candidates']} candidates -> {rep['total_certified']} certificates "
          f"({rep['overall_yield_pct']}% overall), {rep['rankable']} rankable families")
    print()
    print(f"  {'family':26s} {'cand':>6s} {'cert':>5s} {'yield%':>7s} {'trials/1000':>12s}")
    for s in rep["ranked"][:12]:
        c = s["counts"]
        cand, cert = c.get("candidates", 0), c.get("certified", 0)
        y = (100.0 * cert / cand) if cand else 0.0
        print(f"  {s['family']:26s} {cand:6d} {cert:5d} {y:7.2f} {alloc.get(s['family'], 0):12d}")

    un = rep.get("unattributed") or {}
    if un.get("forward_enrolled") or un.get("certified"):
        print(f"\n  UNATTRIBUTED: {un.get('certified', 0)} certificate(s) and "
              f"{un.get('forward_enrolled', 0)} forward row(s) record no family. They cannot be "
              f"credited to any mechanism, and they shrink every denominator above.")
    if rep.get("no_denominator"):
        print(f"  NO DENOMINATOR: {', '.join(rep['no_denominator'])} -- certified through a "
              f"generator that does not write the shared docket, so the pass rate is UNKNOWN "
              f"(not small) and they are excluded from the ranking rather than flattered by it.")
    if rep.get("unconfirmed_high_attempts"):
        print(f"  UNCONFIRMED (100+ attempts, 0 certificates -- but those attempts ran through a "
              f"validator since found defective in four ways, so this describes the TEST, not "
              f"the mechanism): {', '.join(rep['unconfirmed_high_attempts'])}")
    if rep.get("barely_attempted"):
        print(f"  BARELY ATTEMPTED (too few tries to say anything): "
              f"{', '.join(rep['barely_attempted'])}")
    zeroed = [f for f in alloc if alloc[f] == 0]
    if zeroed:
        print(f"  WARNING: {len(zeroed)} mechanism(s) allocated zero despite the "
              f"MIN_FAMILY_SHARE floor -- that is a bug, not a decision: {', '.join(zeroed)}")

    payload = {"checked_at": now.isoformat(timespec="seconds"), "seed": SEED,
               "budget": BUDGET, "recommended_allocation": alloc, **rep}
    OUT.write_text(json.dumps(payload, indent=1, default=str), "utf-8")
    print(f"\n  -> {OUT}")
    # Unattributed rows are the only actionable defect here; a lopsided allocation is a finding
    # to act on, not a failure, and exiting non-zero for it would make this check permanently red.
    return 1 if (un.get("forward_enrolled") or un.get("certified")) else 0


if __name__ == "__main__":
    raise SystemExit(main())
