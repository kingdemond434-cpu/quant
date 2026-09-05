"""What the allocator says a rebalance is worth right now -- the macro interrupt's economic input.

WHY THIS EXISTS

`macro.interrupt.should_fire` refuses to preempt the allocator's clock unless the value lost by
waiting exceeds the turnover the move would cost. Both quantities belong to the allocator's world,
so the gate takes them as arguments, and `run_macro_intel` passed:

    expected_gain_per_day=None, expected_turnover=0.0
    # The allocator prices the move, not this layer. None until the hook is landed.

`None` means HOLD. So every interrupt decision the macro layer ever made died at the same gate --
"expected gain not priced by the allocator" -- whatever the event was. The layer could observe,
classify, price surprise, replay and request an interrupt, and could never actually get one. This
module is that hook, and it invents nothing: both numbers already existed inside the allocator's
own solve and simply had no publisher.

    expected_gain_per_day   `pf_allocation.json -> no_trade.gain_per_day`, which the allocator
                            computes as (what the new solve is worth) - (what the desk is actually
                            HOLDING), in mean log growth per day. That is precisely "the value of
                            acting now rather than on the stale book", in the allocator's units,
                            measured on its own evidence rather than estimated here.
    expected_turnover       `no_trade.turnover` -- half the L1 distance between held and proposed
                            heat, i.e. the fraction of the book that would actually move.

THE GAIN IS AN UPPER BOUND ON WHAT A MACRO INTERRUPT BUYS, and saying so is the point. It is the
value of re-solving now for ANY reason, not the value attributable to this event; a macro-specific
figure would need a conditional forecast per sleeve, which the desk does not yet have (that is
what `attribution` is accruing toward). Using the bound is conservative in the direction that
matters -- it can only make the gate fire when a re-solve is genuinely worth something -- and it
is honest about which number it is, which an invented event-specific estimate would not be.

STALE IS NOT A PRICE. A solve from hours ago describes a book the desk may no longer hold, and
acting on it would be worse than not acting: the interrupt exists to catch fast-decaying
information, so pricing it off slow-decayed evidence is self-defeating. Past `MAX_AGE_S` this
returns None with the reason, and None is HOLD.
"""
from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
REPORT = BASE / "reports" / "pf_allocation.json"

#: The allocator's NORMAL pass period, in seconds. EXTERNAL TO THIS FILE: the research
#: supervisor's PERIODIC clock runs the allocator fast every 5 min, NORMAL every 15 min, heavy
#: hourly (desks/mt5/AGENTS.md), and it is the normal pass that rebuilds evidence and writes the
#: `no_trade` verdict this module reads. The fast pass re-solves on cached worlds and does not
#: refresh the number being priced here, so 15 minutes -- not 5 -- is the cadence that matters.
ALLOCATOR_NORMAL_PERIOD_S = 900.0

#: How old the allocator's solve may be and still price a move. DERIVED FROM THAT CADENCE, not
#: chosen: a tolerance below one normal period would call every price stale, including a perfectly
#: current one read seconds before the next pass. TWO periods is the floor that admits a healthy
#: desk -- one for the pass that produced the file, one for a pass that overran or was skipped --
#: and it sits comfortably inside the gateway's own rule that a book older than an hour is refused
#: outright, so this can never authorise a move on a book the gateway would already have rejected.
#:
#: Past it the answer is "cannot price", never a stale number treated as current: this layer exists
#: to act on FAST-decaying information, so pricing it off a book the desk may no longer hold is
#: the one failure mode that would make the interrupt worse than doing nothing.
#:
#: OVERRIDABLE BY ENV because the supervisor's cadence is a property of the box on the day, not of
#: this file -- a box running the allocator on a slower clock needs a wider tolerance or every
#: interrupt silently holds.
MAX_AGE_S = float(os.environ.get("MACRO_PRICE_MAX_AGE_S", "0") or 0) or None


def _max_age_s() -> float:
    return float(MAX_AGE_S) if MAX_AGE_S else ALLOCATOR_NORMAL_PERIOD_S * 2.0


def price_the_move(report: Path | None = None,
                   now: float | None = None) -> tuple[float | None, float, str]:
    """(expected_gain_per_day, expected_turnover, why) from the allocator's last published solve.

    A `None` gain is the FAIL-CLOSED answer and carries its reason: no report, unreadable report,
    a solve too old to describe the current book, or a book with no finite growth rate to improve
    on. The interrupt gate reads None as HOLD, so every one of those refuses the interrupt and
    leaves the event to the allocator's own clock, which is the correct outcome for all four.
    """
    path = REPORT if report is None else report
    t = time.time() if now is None else now
    if not path.exists():
        return None, 0.0, f"no allocator solve at {path.name}: nothing has priced a move"
    try:
        doc: dict[str, Any] = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return None, 0.0, f"allocator solve unreadable ({type(exc).__name__}: {exc})"
    try:
        age = t - path.stat().st_mtime
    except OSError as exc:
        return None, 0.0, f"allocator solve age unknown ({type(exc).__name__}: {exc})"
    limit = _max_age_s()
    if age > limit:
        return None, 0.0, (f"allocator solve is {age:.0f}s old (limit {limit:.0f}s): it prices a "
                           f"book the desk may no longer hold, and a stale price is worse than "
                           f"no price for information this layer exists to catch early")
    nt = doc.get("no_trade")
    if not isinstance(nt, dict):
        return None, 0.0, "allocator solve carries no no_trade block: the move was never priced"
    gain = nt.get("gain_per_day")
    turnover = nt.get("turnover")
    if gain is None:
        return None, 0.0, ("allocator published no finite gain_per_day -- the held book has no "
                           "growth rate to improve on, so there is no gain to compare to a cost")
    try:
        g = float(gain)
        tv = float(turnover) if turnover is not None else 0.0
    except (TypeError, ValueError):
        return None, 0.0, f"allocator gain/turnover not numeric: {gain!r} / {turnover!r}"
    if not math.isfinite(g) or not math.isfinite(tv):
        return None, 0.0, f"allocator gain/turnover not finite: {g} / {tv}"
    return g, max(tv, 0.0), (f"allocator solve {age:.0f}s old: re-solving now is worth "
                             f"{g:.3e} log-wealth/day against {tv:.4f} of the book moving")
