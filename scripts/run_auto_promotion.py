#!/usr/bin/env python3
"""THE VERB ON THE PROMOTION PATH -- the organ that actually calls the decider.

MEASURED 2026-08-14: `libs/portfolio/auto_promotion.decide()` had ZERO CALLERS. `is_armed` and
`MAX_FIRST_CLIP_FRAC` were imported by one preflight report and the DECISION function itself was
invoked by nothing, in no cycle, ever. So arming automated promotion would have changed exactly
nothing -- the marker would flip to armed, every gate inside `decide()` would stay unevaluated, and
the desk would believe its research-to-capital path was automated while the last link did not
exist. The desk's own recurring defect, on the one path that ends in money.

WHAT THIS DOES, ONCE PER CYCLE. Reads every Stage-B row, asks `decide()` about each one, and
publishes the verdicts. Nothing else. The gates all live in `auto_promotion` and stay there: a
runner that re-implemented any of them would be a second copy of the promotion rules, and two
copies of a rule are two rules.

**IT STILL PLACES NOTHING.** A PROMOTE verdict is an instruction to the executor, published as an
artifact, not an order sent to a venue. The executor places, the risk kernel bounds, the deadman
stops. Same separation the carry and discretionary paths use, for the same reason: a promotion
organ that could reach the venue directly would be a third order path with its own rails.

**REFUSALS ARE THE OUTPUT THAT MATTERS.** On a desk with no eligible candidate this prints a list
of reasons and promotes nothing, and that is the pipeline WORKING. A promotion path whose refusals
are silent is indistinguishable from one that is not running -- which is precisely the state this
script was written to end.

    python scripts/run_auto_promotion.py --capital 200 --min-notional 10
"""

from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root.
import sys as _sys
from pathlib import Path as _P

if str(_P(__file__).resolve().parent.parent) not in _sys.path:
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.portfolio.auto_promotion import decide, is_armed, summarise

_ROOT = Path(__file__).resolve().parent.parent
_SHADOWS = Path("web/axis_shadows.json")
_KILL = Path("data/CASHCARRY_KILL")
_STATE = Path("data/auto_promotion_state.json")
_OUT = Path("data/auto_promotion_decisions.json")
_WEB = Path("web/auto_promotion.json")


def _candidates() -> tuple[list[dict[str, Any]], str]:
    """Stage-B rows, or an explanation. NEVER an empty list standing in for an unreadable file."""
    try:
        doc = json.loads(_SHADOWS.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return [], (f"{_SHADOWS} unreadable ({type(exc).__name__}) -- UNMEASURED. This is NOT "
                    "'no candidates': a promotion path that cannot read its own input must say so, "
                    "because silence here is identical to a healthy desk with nothing eligible")
    rows = doc.get("axes") if isinstance(doc, dict) else doc
    rows = [r for r in (rows or []) if isinstance(r, dict)]
    return rows, f"{len(rows)} Stage-B row(s) read from {_SHADOWS}"


def _rails() -> tuple[bool, str]:
    """Are the risk rails clear? FAIL-CLOSED, and the kill file is the authority.

    Deliberately reads the SAME file the executor's order loop reads, rather than re-deriving a
    verdict from equity. A promotion organ holding its own opinion of whether the book is safe is
    how two rails come to disagree, and the one that disagrees quietly is always the one that
    spends money.
    """
    if _KILL.exists():
        return False, (f"{_KILL} is present -- the executor is flatten-only and places no orders. "
                       "Promoting into a frozen book would queue capital behind a ruin rail")
    return True, "no kill file; the executor may place orders"


def _live_count() -> int:
    """How many strategies already hold auto-promoted capital. Absent state means ZERO, which is
    the conservative reading only because the cap is an upper bound: under-counting would let one
    extra promotion through, so the state file is written on every run to keep it honest."""
    try:
        return int(json.loads(_STATE.read_text("utf-8")).get("live_count") or 0)
    except (OSError, ValueError, TypeError):
        return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--capital", type=float, default=None,
                    help="deployable equity in USD; enables the venue-minimum check")
    ap.add_argument("--min-notional", type=float, default=None)
    args = ap.parse_args()

    armed, why_armed = is_armed(_ROOT)
    rows, why_rows = _candidates()
    rails_ok, rails_why = _rails()
    live = _live_count()

    decisions = [
        decide(r, live_count=live, rails_ok=rails_ok, rails_why=rails_why, root=_ROOT,
               deployable_usd=args.capital, min_notional_usd=args.min_notional)
        for r in rows
    ]
    rep: dict[str, Any] = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "armed": armed, "armed_why": why_armed,
        "rails_ok": rails_ok, "rails_why": rails_why,
        "live_count": live,
        "candidates_why": why_rows,
        "deployable_usd": args.capital,
        **summarise(decisions),
    }
    for p in (_OUT, _WEB):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rep, indent=1), "utf-8")

    # THE STATE IS WRITTEN EVERY RUN, promoted or not. A live count that only updates on a
    # promotion drifts the moment a strategy is retired by hand, and it drifts in the direction
    # that admits one more.
    _STATE.write_text(json.dumps({
        "live_count": live + rep["n_promoted"],
        "updated": rep["updated"],
        "note": ("Strategies holding AUTO-promoted capital. Separate from the Holm cohort cap: "
                 "that one bounds multiplicity, this one bounds how much of the book sits on "
                 "decisions no human reviewed."),
    }, indent=1), "utf-8")

    print(f"auto-promotion: armed={armed} rails_ok={rails_ok} live={live} "
          f"-> {rep['n_promoted']} promoted, {rep['n_refused']} refused of {rep['n_considered']}")
    for p_ in rep["promoted"]:
        print(f"  PROMOTE  {p_['candidate']:<34} clip={p_['clip_frac']:.4%}")
    for r_ in rep["refusals"][:8]:
        print(f"  refuse   {r_['candidate']:<34} {r_['why'][:120]}")
    if not rows:
        print(f"  {why_rows}")
    print(f"-> {_OUT} and {_WEB}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
