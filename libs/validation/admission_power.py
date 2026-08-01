"""WHAT DOES RANKED ADMISSION ACTUALLY RESOLVE, AND WHAT DOES A WRONG ADMISSION COST?

Two arithmetic questions that a Monte Carlo cannot answer on its own, kept here so the answer is
a function with a test rather than a paragraph in a report.

  1. WHERE IS THE SENSITIVITY FLOOR. `power_crossing` reads a measured power curve and returns
     the true Sharpe at which admission power first exceeds 50%. That is the honest restatement
     of "certified floor": the gauntlet's old certified floor of TRUE SHARPE 5.0 is the smallest
     level at which the all-gates rule passed anything at all, and the recorded audit
     (reports/gate_power_audit.json, 240 true alphas per level) put its power AT 5.0 at 12.08% --
     so "5.0" was already a generous reading of a gate that missed seven of eight genuine edges
     there. A 50% crossing is the level at which the screen is more likely than not to see a real
     edge, and it is the number a research plan can actually be built on.

  2. WHAT A FALSE ADMISSION COSTS. `slot_occupancy_cost` converts a false-admission RATE into the
     only unit that matters here: SLOTS. Admission is not promotion -- an admitted candidate gets
     a forward clock and never capital -- so a false admission does not lose money, it loses one
     of MAX_FORWARD_SLOTS=12 pre-registered forward experiments for one forward period. The
     multiplicity cost of those twelve is already paid whether or not they are used
     (libs/validation/screen_admission), so the real question is not "is the rate above zero" but
     "does the rate saturate the twelve". Those are completely different findings and the desk
     has no way to tell them apart by eye: at 4,800 screened nulls, a false-admission rate of
     1e-4 wastes 0.5 slots per campaign and a rate of 1e-2 wastes 48 -- four times the entire
     forward stage, permanently. Same order-of-magnitude language, opposite verdicts.

WHY THE CROSSING IS SCANNED UPWARD AND NEVER FITTED. A logistic or probit fit through the whole
curve would use the 10.0 point to decide where the 3.0 point sits, and Monte Carlo power curves
are not exactly monotone -- 240 true alphas per level gives a +/-6pp Wilson half-width, so two
adjacent levels routinely invert. Fitting would then let a level ABOVE the crossing move the
crossing, which is the same defect class as a rolling statistic peeking at future data. Scanning
upward and interpolating within the first bracket makes the answer depend only on the levels at
or below it -- prefix invariance, locked by `test_crossing_is_prefix_invariant`.

AND IF NOTHING CROSSES, IT SAYS SO. `power_crossing` returns `bracketed=False` and an infinite
floor when the top of the grid never reaches the target. Returning the top grid level there would
be the exact `beats_baselines` failure -- an unmeasured quantity reading as a measured one -- and
it is how "the floor is 10" gets written down about a grid that stopped at 10 with 40% power.

NOTHING HERE SIMULATES, SCORES OR PROMOTES ANYTHING. It is arithmetic on a measured curve.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

__all__ = [
    "BRAIN_TARGET_SHARPE",
    "OLD_CERTIFIED_FLOOR",
    "POWER_TARGET",
    "Crossing",
    "SlotCost",
    "power_crossing",
    "slot_occupancy_cost",
]

#: Power at which a screen stops being a wall. Below 0.5 the screen misses a genuine edge more
#: often than it finds one, so its null result carries no information about the price space --
#: which is the entire reason certify_gauntlet exists.
POWER_TARGET = 0.5

#: The floor the all-gates-must-pass rule was certified at. Kept here so every ratio this module
#: reports moves if the certification moves, rather than being restated in a report by hand.
OLD_CERTIFIED_FLOOR = 5.0

#: WorldQuant BRAIN's stated target Sharpe -- a live pipeline that pays research consultants,
#: submitting at fitness 1.0. The external anchor for "what a real institution calls an edge".
BRAIN_TARGET_SHARPE = 1.25

#: Magnitude floor on the power difference used as an interpolation denominator. A `> 0` test does
#: not survive floating-point dust: two Monte Carlo levels can differ by 1/240 - 1/240 == 4e-17
#: after float arithmetic, and dividing by that returns a crossing thousands of Sharpe units away
#: from the bracket it was interpolated inside. Below this the bracket is treated as FLAT and the
#: conservative end (the upper level) is reported.
_MIN_POWER_GAP = 1e-9

#: Magnitude floor on a level gap, same reasoning applied to the x-axis: duplicated grid levels
#: give a zero-width bracket, and interpolating across it is a divide-by-dust.
_MIN_LEVEL_GAP = 1e-12


@dataclass(frozen=True)
class Crossing:
    """Where a measured power curve first crosses the target, and whether it crossed at all."""

    target: float
    sensitivity_floor: float
    bracket_lo: float
    bracket_hi: float
    power_lo: float
    power_hi: float
    bracketed: bool
    max_power_measured: float
    level_at_max_power: float
    note: str

    def summary(self) -> str:
        if not self.bracketed:
            return (f"NO CROSSING: power never reached {self.target:.0%} on the measured grid "
                    f"(best {self.max_power_measured:.1%} at true Sharpe "
                    f"{self.level_at_max_power:g}) -- the floor is ABOVE the grid, not at its top")
        return (f"{self.target:.0%} power at true Sharpe {self.sensitivity_floor:.2f} "
                f"(bracketed by {self.bracket_lo:g} at {self.power_lo:.1%} and "
                f"{self.bracket_hi:g} at {self.power_hi:.1%})")


def power_crossing(levels: Sequence[float], powers: Sequence[float],
                   *, target: float = POWER_TARGET) -> Crossing:
    """The lowest true Sharpe at which measured power exceeds `target`, by upward scan.

    `levels` and `powers` are paired and are sorted ascending by level here rather than being
    assumed sorted -- a caller that builds its grid as a dict has no ordering guarantee, and an
    unsorted scan would report whichever bracket happened to come first in insertion order.

    THE FIRST CROSSING, NOT THE LAST. On a noisy curve power can dip back below the target above
    the crossing; the question asked is where the screen STARTS to resolve, so the scan stops at
    the first bracket whose upper end is at or above target and never revisits.

    A LEVEL ALREADY AT OR ABOVE TARGET AT THE BOTTOM OF THE GRID IS REPORTED AS THE GRID'S OWN
    LIMIT, not as the floor. If the lowest level measured already has 60% power, the true crossing
    is somewhere below it and this grid cannot see it: the floor is returned as that lowest level
    with a note saying the answer is an upper bound. Reporting it as if it were located would
    overstate the screen's strictness, which on this desk is the flattering direction.

    Returns `bracketed=False` with an infinite floor when nothing crosses. UNMEASURED IS NOT
    PASSED, and it is emphatically not "the top of the grid".
    """
    lv = np.asarray(list(levels), dtype="float64")
    pw = np.asarray(list(powers), dtype="float64")
    tgt = float(target)
    if lv.size == 0 or lv.size != pw.size:
        return Crossing(tgt, float("inf"), float("nan"), float("nan"), float("nan"), float("nan"),
                        False, float("nan"), float("nan"),
                        "UNMEASURABLE: levels and powers must be non-empty and the same length")
    finite = np.isfinite(lv) & np.isfinite(pw)
    lv, pw = lv[finite], pw[finite]
    if lv.size == 0:
        return Crossing(tgt, float("inf"), float("nan"), float("nan"), float("nan"), float("nan"),
                        False, float("nan"), float("nan"),
                        "UNMEASURABLE: no finite (level, power) pairs")
    order = np.argsort(lv, kind="stable")
    lv, pw = lv[order], pw[order]
    i_best = int(np.argmax(pw))
    best, at_best = float(pw[i_best]), float(lv[i_best])

    if pw[0] >= tgt:
        return Crossing(tgt, float(lv[0]), float(lv[0]), float(lv[0]), float(pw[0]), float(pw[0]),
                        True, best, at_best,
                        f"UPPER BOUND ONLY: the lowest level measured ({lv[0]:g}) is already at "
                        f"{pw[0]:.1%} power, so the crossing lies BELOW this grid. Extend the grid "
                        "downward before quoting this as the floor.")

    for k in range(1, lv.size):
        if pw[k] < tgt:
            continue
        lo, hi = float(lv[k - 1]), float(lv[k])
        p_lo, p_hi = float(pw[k - 1]), float(pw[k])
        gap_p, gap_l = p_hi - p_lo, hi - lo
        if gap_p <= _MIN_POWER_GAP or gap_l <= _MIN_LEVEL_GAP:
            # A flat or zero-width bracket carries no information about where inside it the
            # crossing sits. Report the upper end: it is the only level actually MEASURED at or
            # above target, and it is the conservative (stricter) read of the floor.
            return Crossing(tgt, hi, lo, hi, p_lo, p_hi, True, best, at_best,
                            "bracket is flat or zero-width; reported at its upper end, which is "
                            "the only level measured at or above target")
        floor = lo + (tgt - p_lo) * gap_l / gap_p
        return Crossing(tgt, float(floor), lo, hi, p_lo, p_hi, True, best, at_best,
                        "linear interpolation inside the first bracket that reaches target; "
                        "depends only on levels at or below it")

    return Crossing(tgt, float("inf"), float(lv[-1]), float("inf"), float(pw[-1]), float("nan"),
                    False, best, at_best,
                    f"power never reached {tgt:.0%}: highest measured is {best:.1%} at true "
                    f"Sharpe {at_best:g}. The floor is ABOVE this grid; quoting the grid's top "
                    "level as the floor would report an unmeasured quantity as measured.")


@dataclass(frozen=True)
class SlotCost:
    """What a false-admission rate costs, denominated in forward slots rather than in p-values."""

    false_admission_rate: float
    n_screened_nulls: int
    n_slots: int
    expected_false_admissions: int | float
    slots_wasted_per_campaign: float
    fraction_of_slots_wasted: float
    saturated: bool
    verdict: str

    def summary(self) -> str:
        return (f"false-admission rate {self.false_admission_rate:.3%} on "
                f"{self.n_screened_nulls} nulls -> {self.expected_false_admissions:.1f} admissible "
                f"nulls per campaign, occupying {self.slots_wasted_per_campaign:.1f} of "
                f"{self.n_slots} slots ({self.fraction_of_slots_wasted:.0%}) :: {self.verdict}")


def slot_occupancy_cost(false_admission_rate: float, *, n_screened_nulls: int,
                        n_slots: int, saturation_fraction: float = 1.0) -> SlotCost:
    """Translate a false-admission rate into wasted forward slots, which is the real currency.

    THE ARITHMETIC, AND WHY IT IS NOT THE RATE. A campaign screens `n_screened_nulls` zero-edge
    candidates. The expected number that clear admission is rate * n. Slots are capped, so the
    number actually WASTED is min(that, n_slots) -- and once the expected count exceeds the cap
    the twelve slots are filled by noise before a real candidate is even ranked, because the
    ranking is on OOS Sharpe and a lucky null that cleared a relevance floor by luck ranks exactly
    like a real edge that cleared it by edge. That is the failure mode worth naming: not "some
    noise gets in", which is priced and acceptable, but "noise crowds out everything", which is a
    guaranteed discovery rate of zero wearing a full slot table.

    IT IS A CEILING ON THE COST, NOT A FORECAST, and the distinction matters. Real candidates
    compete for the same slots and out-rank most lucky nulls, so the realised waste is lower --
    the ranked competition is measured directly by the Monte Carlo rather than modelled here.
    This function prices the WORST case a rate implies: a campaign in which nothing real was
    submitted, which is precisely the campaign the desk has actually been running (129 mechanisms,
    zero survivors).

    `saturation_fraction` is the share of the slot table above which the desk calls the forward
    stage permanently occupied by noise. It defaults to 1.0 -- full saturation -- deliberately:
    anything lower is a judgement about how much noise is tolerable, and this function reports the
    arithmetic rather than making that judgement. Callers wanting a stricter alarm pass it in.
    """
    rate = float(false_admission_rate)
    n_null = max(0, int(n_screened_nulls))
    slots = max(0, int(n_slots))
    frac = float(saturation_fraction)
    if not np.isfinite(rate) or rate < 0.0 or not np.isfinite(frac):
        return SlotCost(rate, n_null, slots, float("nan"), float("nan"), float("nan"), False,
                        "UNMEASURABLE -- BLOCKED: false-admission rate is not a finite "
                        "non-negative number. An unknown rate is not a safe rate.")
    expected = rate * n_null
    wasted = min(float(slots), expected)
    share = (wasted / slots) if slots > 0 else float("nan")
    saturated = bool(slots > 0 and expected >= frac * slots)
    if slots == 0:
        verdict = ("no forward slots exist to waste -- the cost of a false admission is undefined "
                   "until the slot table does")
    elif saturated:
        verdict = (f"SATURATED: {expected:.1f} admissible nulls per campaign against {slots} "
                   "slot(s). The forward stage would be permanently occupied by noise and the "
                   "discovery rate is zero however good the candidates are. This is a real "
                   "problem and the relevance floor is the lever, not the slot count.")
    elif expected >= 1.0:
        verdict = (f"BOUNDED: {expected:.1f} of {slots} slot(s) lost to noise per campaign, for "
                   "one forward period each. Admission is a clock, not capital, so the loss is "
                   "forfeited experiments -- not drawdown.")
    else:
        verdict = (f"NEGLIGIBLE: {expected:.2f} admissible nulls per campaign -- fewer than one "
                   f"of {slots} slot(s). At this rate the binding constraint on the forward stage "
                   "is the supply of candidates, not contamination.")
    return SlotCost(rate, n_null, slots, expected, wasted, share, saturated, verdict)
