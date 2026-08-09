"""THE PASS IS A DECISION, SO IT IS GRADED -- does the filter ADD value or merely avoid deciding?

THE TRAP THIS CLOSES (external critique, GPT 2026-07-31; row R0123). A discretionary sleeve that
is scored only when it TRADES has a dominant strategy available to it: never trade. Its calibration
record stays spotless because the record only ever contains the calls it chose to be graded on, and
its economic contribution is zero. The brief the model is handed already promises otherwise -- "a
PASS is also scored... marked against the same horizon as a real call" -- and until now that
sentence was prose. `record_call` logged a forecast for `action == "CALL"` and nothing else, so
across 2026-07-31..08-05 the sleeve wrote NINE book rows, all nine of them PASS, and logged ZERO
scoreable forecasts. The trap was not hypothetical and the model had already walked into it.

WHAT A DECLINE'S OUTCOME EVEN MEANS, stated before any of it is computed. A PASS row carries the
model's own `direction` and `probability` -- what it WOULD have done. Grading that against the
realised move over the SAME horizon answers the only question worth asking about a filter:

  * declined directions right ~50% of the time -> THE FILTER IS WORKING. This is the good case and
    it must not be read as failure: a coin-flip trade is a LOSING trade once fees are paid, so
    declining it is correct. The desk has this on its own record -- 88.3% of the live carry book's
    loss was fees, not thesis.
  * declined directions right WELL ABOVE half -> THE FILTER IS DESTROYING VALUE. The model is
    systematically talking itself out of correct calls, and that is expensive in a way nothing
    else on this desk would have detected, because a decline leaves no P&L trace.
  * declined directions right WELL BELOW half -> the filter is adding value, and the declines are
    additionally informative as a contrarian signal in their own right.

WHY THE DECLINE POOL IS KEPT OUT OF THE SIZING STATISTIC, which is the load-bearing safety property
here. `forecast_calibration.report()` pools every resolved forecast into one bias term, and
`calibrated_confidence` subtracts that bias from raw probabilities feeding `kelly_leverage` in
run_conviction_trader. Most declines are asserted at p=0.50 -- near-zero information each -- so
pouring them into that pool would swamp the handful of real calls and move LIVE POSITION SIZE on
the strength of trades the desk never took. This desk has already paid for exactly that error once:
a mis-pooled calibration set inverted the measured bias and sized a self-rated no-edge call at
6.00x, because the risk cap bounds SIZE and can never restore the SIGN of an edge. Declines are
therefore logged under their own kinds and excluded from the sizing pool by default; they are
scored in this module instead, where the statistic answers a question about the FILTER.

THE HONEST NULL IS 0.5 AND SMALL SAMPLES SAY SO. A hit-rate is reported with the two-sided
binomial reading against a fair coin and, below the evidence bar, the verdict is UNMEASURED rather
than a direction. `n=8` is not a finding, and naming it one would be the same premature-surrender
error L1.25 forbids in the other direction.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

#: Forecast kinds that are NOT decisions the desk sized capital on, and so must never enter the
#: bias term that shrinks live Kelly probabilities. Consumed by forecast_calibration.report().
DECLINE_KINDS: tuple[str, ...] = ("discretionary_pass", "discretionary_pass_backfill")

#: Below this many graded declines the filter verdict is UNMEASURED. Matches evidence_clock's
#: MIN_OBS rather than restating a second, quieter bar -- one number, one meaning, desk-wide.
MIN_DECLINES = 20

#: How far from a fair coin the declined-direction hit-rate must sit before the filter is called
#: anything. Two standard errors, the same admission bar as evidence_clock.MIN_T.
MIN_Z = 2.0

_DIRECTIONS = ("LONG", "SHORT")


@dataclass(frozen=True)
class Decline:
    """One graded decline: what the model said it would have done, and whether that was right."""

    key: str
    symbol: str
    direction: str
    probability: float
    entry_px: float
    exit_px: float
    #: True when the DECLINED direction would have been right over the stated horizon.
    would_have_been_right: bool
    #: Signed return of the declined direction, in bps. The economic size of the miss, which a
    #: bare hit-rate cannot express: eight small misses are not one large one.
    forgone_bps: float
    pass_reason: str


def scoreable(row: Mapping[str, Any]) -> tuple[bool, str]:
    """Does this book row carry what grading needs -- WITHOUT inventing any of it?

    A row missing a symbol or a direction is genuinely ungradeable, and the correct response is to
    say so on the row rather than to drop it silently. Under L1.28a unmeasured counts as zero, not
    as fine, and a decline that vanishes from the accounting is precisely how the pass-optimisation
    trap stays invisible.
    """
    if not row.get("symbol"):
        return False, "no symbol -- nothing to price the decline against"
    if row.get("direction") not in _DIRECTIONS:
        return False, (f"direction {row.get('direction')!r} is not LONG/SHORT -- the model stated "
                       "no counterfactual to grade")
    try:
        p = float(row["probability"])
    except (KeyError, TypeError, ValueError):
        return False, "no numeric probability -- a decline without one asserts nothing scoreable"
    if not 0.0 <= p <= 1.0:
        return False, f"probability {p} outside [0,1]"
    if not row.get("at") or not row.get("resolve_by"):
        return False, "no pre-registered horizon (at / resolve_by) -- not a forecast (L1.29)"
    return True, "scoreable"


def grade(direction: str, entry_px: float, exit_px: float) -> bool:
    """Would the declined direction have been right over the window?

    Strict inequality both ways, so an EXACTLY unchanged price grades a LONG as wrong and a SHORT
    as wrong. That is not a coin-flip tiebreak: a flat market pays neither leg and still charges
    two round trips, so declining it was correct on both sides.
    """
    if direction == "LONG":
        return exit_px > entry_px
    if direction == "SHORT":
        return exit_px < entry_px
    raise ValueError(f"direction must be one of {_DIRECTIONS}, got {direction!r}")


def forgone_bps(direction: str, entry_px: float, exit_px: float) -> float:
    """Signed return of the declined direction in bps -- positive means the decline cost money."""
    if entry_px <= 0:
        return 0.0
    raw = (exit_px - entry_px) / entry_px
    return round((raw if direction == "LONG" else -raw) * 1e4, 2)


def make_decline(row: Mapping[str, Any], entry_px: float, exit_px: float, *,
                 key: str = "") -> Decline:
    """Grade one pre-registered decline against the two prices its own horizon defines."""
    direction = str(row["direction"])
    return Decline(
        key=key or str(row.get("forecast_key") or row.get("at") or ""),
        symbol=str(row["symbol"]), direction=direction,
        probability=float(row["probability"]), entry_px=float(entry_px), exit_px=float(exit_px),
        would_have_been_right=grade(direction, entry_px, exit_px),
        forgone_bps=forgone_bps(direction, entry_px, exit_px),
        pass_reason=str(row.get("pass_reason") or ""),
    )


def _binomial_z(hits: int, n: int) -> float:
    """Standard-normal z of a hit-rate against a fair coin. Zero when undefined."""
    if n <= 0:
        return 0.0
    return (hits - 0.5 * n) / math.sqrt(0.25 * n)


def filter_verdict(declines: Sequence[Decline], *, min_declines: int = MIN_DECLINES,
                   min_z: float = MIN_Z) -> dict[str, Any]:
    """Does the filter ADD value, DESTROY value, or is it not yet distinguishable from a coin?

    The verdict is about the FILTER, never about position size -- this module has no vocabulary
    for sizing and nothing downstream of it consumes the number as a Kelly input.
    """
    n = len(declines)
    if n == 0:
        return {"n_declines": 0, "verdict": "UNMEASURED",
                "why": "no graded declines -- unmeasured, which is not the same as none forgone"}
    hits = sum(1 for d in declines if d.would_have_been_right)
    hit_rate = hits / n
    z = _binomial_z(hits, n)
    mean_forgone = round(sum(d.forgone_bps for d in declines) / n, 2)
    # Brier of the model's OWN stated probability against the declined outcome: whether it knew
    # what it was passing on. Separate question from whether passing was right.
    brier = round(sum((d.probability - (1.0 if d.would_have_been_right else 0.0)) ** 2
                      for d in declines) / n, 4)

    if n < min_declines:
        verdict, why = "UNMEASURED", (
            f"{n}/{min_declines} graded declines -- too few to tell this filter from a coin, "
            f"whatever the {hit_rate:.0%} reads. Needs more declines, not a lower bar")
    elif z >= min_z:
        verdict, why = "DESTROYING-VALUE", (
            f"declined directions were right {hit_rate:.0%} of the time (z={z:+.2f} vs a fair "
            f"coin) -- the filter is systematically talking the desk out of correct calls, at a "
            f"mean {mean_forgone:+.1f} bps forgone per decline")
    elif z <= -min_z:
        verdict, why = "ADDING-VALUE", (
            f"declined directions were right only {hit_rate:.0%} (z={z:+.2f}) -- the filter is "
            f"screening out losers, and the declines carry contrarian information of their own")
    else:
        verdict, why = "WORKING-AS-INTENDED", (
            f"declined directions were right {hit_rate:.0%} (z={z:+.2f}), indistinguishable from "
            f"a coin -- which is the GOOD case: a coin-flip trade is a losing trade once fees are "
            f"paid, so declining it was correct")
    return {
        "n_declines": n, "hits": hits, "hit_rate": round(hit_rate, 4),
        "z_vs_fair_coin": round(z, 3), "mean_forgone_bps": mean_forgone,
        "total_forgone_bps": round(sum(d.forgone_bps for d in declines), 2),
        "brier_on_declined_view": brier,
        "verdict": verdict, "why": why,
        "bar": {"min_declines": min_declines, "min_z": min_z},
    }


def pass_rate(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """How often the sleeve declines at all -- the other half of the pass-optimisation trap.

    A filter can be perfectly calibrated on the declines it grades and still contribute nothing by
    declining EVERYTHING. That is a property of the book, not of any single row, and it is visible
    only here. Reported unconditionally so an all-pass sleeve cannot read as a healthy one.
    """
    rows = list(rows)
    n = len(rows)
    n_pass = sum(1 for r in rows if r.get("action") == "PASS")
    n_call = sum(1 for r in rows if r.get("action") == "CALL")
    rate = n_pass / n if n else 0.0
    if n == 0:
        flag, why = "EMPTY", "no book rows -- the sleeve has never produced a decision"
    elif n_call == 0:
        flag, why = "ALL-PASS", (
            f"{n_pass}/{n} rows are PASS and the sleeve has NEVER made a call. Its calibration "
            f"record is spotless because it is empty -- the exact failure the decline grading "
            f"exists to make visible")
    elif rate >= 0.95:
        flag, why = "NEAR-ALL-PASS", f"{n_pass}/{n} rows are PASS ({rate:.0%})"
    else:
        flag, why = "OK", f"{n_pass}/{n} rows are PASS ({rate:.0%}), {n_call} call(s) made"
    return {"n_rows": n, "n_pass": n_pass, "n_call": n_call,
            "pass_rate": round(rate, 4), "flag": flag, "why": why}
