"""KEEP THE NEAR-MISSES. A candidate at 80% of the bar is a WORK ITEM, not a corpse.

THE GAP THIS CLOSES, quoted from the desk's own comparison table. `brain_calibration.gap_report()`
emits a row for "near-miss triage" whose desk value is `None` and whose direction reads
**"NO DESK COUNTERPART -- recorded as ABSENT, not as satisfied"**. The external pipeline's practice
is that an alpha at roughly 80% of the submission metrics -- Sharpe 0.9 against a 1.0 bar -- is
"near-submittable", and near-submittable alphas are IMPROVED rather than discarded. This desk emits
PASS/FAIL, so a candidate that came within a hair of the bar is marked FAILED, dies silently, and
leaves no record that it was ever close.

WHY THAT IS EXPENSIVE ON THIS DESK SPECIFICALLY, AND NOT MERELY UNTIDY:

  1. This desk's own accounting says 107 of 201 refutations -- 53% -- were MEASUREMENT failures
     (data quality plus wrong construction), not absent alpha (docs/DESK_BRIEF.md). So the
     near-misses being discarded are disproportionately the FIXABLE ones. Discarding them is not
     pruning a dead branch, it is throwing away the half of the pile the desk already knows is
     mostly repairable.
  2. Lesson L0042: a candidate dropped before scoring is not a small loss, it is an UNMEASURED one.
     A near-miss with no ledger entry cannot be counted, cannot be ranked, and cannot be re-run
     when the data that would have settled it finally arrives.
  3. The scale is not hypothetical. The 2026-08-01 campaign screened 129 candidates and produced
     ZERO survivors; data/forward_slots.json has never existed. Whatever fraction of those 129 sat
     just under a bar, the desk cannot say -- because nothing wrote it down. That is the current
     state this module changes.

WHAT THIS MODULE IS NOT, and this is the load-bearing sentence in the file:

    IT CHANGES NO VERDICT. Every candidate that reaches `triage()` has ALREADY FAILED. Nothing here
    exposes a pass, a promotion, a slot, or a size; `NearMissVerdict.__bool__` is hard-wired to
    False precisely so that `if triage(...)` can never be misread as an approval. NEAR_MISS is a
    label on a corpse's file, not a resurrection. The candidate is still failed when this module is
    done with it; the only thing that changed is that the desk now has a record.

THE THREE CLASSES, and why the split is the same one screen_admission already uses:

  STRUCTURAL_DEAD  it failed a gate that NO amount of re-measurement repairs. The gate list is
                   IMPORTED from libs/validation/screen_admission (`STRUCTURAL_GATES`) and never
                   restated here -- two copies of that list would drift, and the copy that drifted
                   loose would be the one quietly reclassifying a dead mechanism as fixable.
  NEAR_MISS        every failure is statistical AND the worst shortfall is inside
                   MAX_NEAR_MISS_SHORTFALL. Worth re-measuring or re-engineering.
  FAR_MISS         it failed only statistical gates but missed by more than that -- and, equally,
                   anything the module could not SCORE. See the unknown-input rule below.

THE UNKNOWN-INPUT RULE. A failed gate whose metric or threshold was not supplied cannot be scored,
and the tempting behaviour -- treat the missing number as a zero shortfall -- would classify the
least-measured candidates as the closest to passing. That is the `beats_baselines` defect exactly:
it returned True for every candidate for months because no caller ever supplied its input.
UNMEASURED IS NOT NEAR. So an unscoreable failure yields a NaN shortfall, is named in
`unmeasured_gates`, and BLOCKS the NEAR_MISS label. It still lands in the ledger with a hint saying
which input to supply, so nothing is killed silently -- the record is the point.

THE ONE PLACE THE IMPORTED LIST IS UNCOMFORTABLE, stated rather than papered over. `sample_adequacy`
is carried in STRUCTURAL_GATES, yet it is the one structural failure that MORE DATA genuinely does
repair. This module does not fork the list to fix that -- a divergent copy is the worse defect -- so
such a candidate is still classified STRUCTURAL_DEAD and can never be a NEAR_MISS. What it does
instead is set `re_runnable`, a LEDGER flag and not a verdict, so the candidate is re-queued when
the sample grows. The classification is unchanged; only the re-run queue knows the difference.

STATUS. DRAFTED, in this desk's sense: it has tests and no production importer yet, exactly like
`screen_admission` alongside which it is meant to run. The call site it is shaped for is the
screen's REJECT path -- everything `admit()` returns as `blocked` or `ranked_out` -- and it is
deliberately a pure function of already-computed gate results so that wiring it there cannot
perturb anything upstream of it.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from libs.core.time import to_iso8601, utcnow
from libs.validation.screen_admission import STATISTICAL_GATES, STRUCTURAL_GATES

__all__ = [
    "CLASSIFICATIONS",
    "DATA_REPAIRABLE_STRUCTURAL",
    "FAR_MISS",
    "GATE_HINTS",
    "MAX_NEAR_MISS_SHORTFALL",
    "NEAR_MISS",
    "NEAR_MISS_FRACTION",
    "NO_FAILURE_RECORDED",
    "STRUCTURAL_DEAD",
    "GateShortfall",
    "NearMissVerdict",
    "Threshold",
    "all_hints",
    "improvement_hint",
    "log_near_misses",
    "read_near_miss_ledger",
    "relative_shortfall",
    "triage",
]

#: THE PROVENANCE, verbatim: "near-submittable = maybe 80% of the submission metrics ... it's very
#: much possible to make it submittable" -- WorldQuant BRAIN webinar transcript, 2026-08-01
#: (principal-supplied), the same source as `BRAIN_NEAR_SUBMITTABLE_FRACTION`. Marked APPROXIMATE
#: there: it is a spoken aside ("maybe 80%"), not a slide, and it is used here as a TRIAGE BOUNDARY
#: -- which candidate gets a second look -- never as a threshold on evidence. Nothing passes or
#: fails because of this number.
#:
#: WHY IT IS RESTATED HERE RATHER THAN IMPORTED. brain_calibration's own docstring forbids any
#: decision path from importing it, so that an external number cannot quietly become a threshold.
#: This module is not a decision path, but the rule is honoured literally and drift is prevented
#: the other way: tests/validation/test_near_miss.py asserts this constant EQUALS
#: brain_calibration.BRAIN_NEAR_SUBMITTABLE_FRACTION, so the two cannot separate silently. A single
#: fenced scalar can be handled that way; a LIST (see STRUCTURAL_GATES, imported above) cannot,
#: which is why the two are treated differently.
NEAR_MISS_FRACTION = 0.80

#: DERIVED, never spoken: a candidate at 80% of the bar has missed it by 20% OF THE BAR. Expressed
#: as a shortfall because that is the quantity `triage` actually computes and ranks on, and it is
#: symmetric across gate direction, which the raw "fraction attained" is not (see
#: `relative_shortfall`).
MAX_NEAR_MISS_SHORTFALL = 1.0 - NEAR_MISS_FRACTION

NEAR_MISS = "NEAR_MISS"
FAR_MISS = "FAR_MISS"
STRUCTURAL_DEAD = "STRUCTURAL_DEAD"

#: Returned when the caller hands in a candidate with no failed gate at all. This is NOT a pass and
#: must never be read as one -- this module has no pass verdict and cannot issue one. It exists so a
#: caller bug (triaging a candidate that never failed) surfaces as its own label instead of being
#: folded into FAR_MISS, where it would be invisible.
NO_FAILURE_RECORDED = "NO_FAILURE_RECORDED"

CLASSIFICATIONS: tuple[str, ...] = (NEAR_MISS, FAR_MISS, STRUCTURAL_DEAD, NO_FAILURE_RECORDED)

#: Structural gates that MORE DATA repairs. See the module docstring: this does not reclassify
#: anything -- a candidate failing one of these is still STRUCTURAL_DEAD and still cannot be a
#: NEAR_MISS -- it only marks the ledger entry as worth re-running when the sample grows.
DATA_REPAIRABLE_STRUCTURAL: tuple[str, ...] = ("sample_adequacy",)

#: A threshold whose magnitude is below this cannot serve as the denominator of a relative
#: shortfall: dividing by ~0 manufactures an arbitrarily large "miss" from an arbitrarily small
#: absolute gap, which is the same defect class as the `> 0` variance guard that shipped a 1.4e31
#: prediction premium here on 2026-08-01. The fix is a MEANINGFUL magnitude floor, not a tighter
#: comparison against zero. Gates thresholded at exactly zero (an "expected value > 0" shape) are
#: therefore reported UNMEASURABLE rather than scored -- and an unmeasurable shortfall blocks
#: NEAR_MISS.
_THRESHOLD_MAGNITUDE_FLOOR = 1e-6

#: The 0.80/0.20 boundary is hit exactly by realistic inputs -- Sharpe 0.9 against a 1.0 bar, or a
#: reality-check p of 0.06 against 0.05 -- and both compute to 0.19999999999999998 in binary
#: floating point. Without this tolerance the canonical BRAIN example would classify FAR_MISS.
_BOUNDARY_TOLERANCE = 1e-12


@dataclass(frozen=True)
class Threshold:
    """The bar a gate had to clear, plus WHICH WAY the gate points.

    `higher_is_better` is mandatory in spirit even though it carries a default, because getting it
    wrong silently inverts every number downstream: a PBO of 0.60 against a 0.20 bar would be
    scored as a 67% overshoot in the candidate's favour rather than a 200% miss. The same sign
    error is the one `brain_calibration._direction` exists to prevent on the reporting side, where
    it would have turned "this desk is 3x more concentrated" into "3x safer".
    """

    value: float
    higher_is_better: bool = True
    label: str = ""


@dataclass(frozen=True)
class GateShortfall:
    """How far one FAILED gate was from its bar, in units of the bar.

    `shortfall` is NaN, and `measured` is False, whenever the gap could not be computed honestly --
    a missing metric, a missing threshold, a non-finite value, or a threshold too close to zero to
    divide by. NaN is used rather than a large sentinel so that any arithmetic performed on it
    stays NaN instead of silently becoming a plausible-looking number.
    """

    gate: str
    metric: float
    threshold: float
    higher_is_better: bool
    shortfall: float
    structural: bool
    measured: bool
    note: str = ""

    def summary(self) -> str:
        direction = "needed >=" if self.higher_is_better else "needed <="
        if not self.measured:
            return f"{self.gate}: UNMEASURED ({self.note})"
        return (f"{self.gate}: {self.metric:.4g} vs {direction} {self.threshold:.4g} "
                f"-- short by {self.shortfall * 100:.1f}% of the bar")


def relative_shortfall(metric: float, threshold: Threshold) -> float:
    """How far `metric` fell short of `threshold`, as a fraction of the threshold's magnitude.

        higher-is-better:  (threshold - metric) / |threshold|
        lower-is-better:   (metric - threshold) / |threshold|

    Zero when the gate was actually cleared; negative is never returned, because a cleared gate is
    not this module's business and reporting a negative shortfall would let a passing gate drag a
    "worst shortfall" downwards and manufacture a NEAR_MISS out of one bad gate plus several good
    ones. Callers only ever pass FAILED gates here; the clamp makes the misuse harmless rather than
    subtly wrong.

    WHY BOTH DIRECTIONS ARE MEASURED IN UNITS OF THE THRESHOLD, rather than as "fraction of the bar
    attained". The attained-fraction reading is natural for a higher-is-better gate (Sharpe 0.9 of
    a 1.0 bar = 80%) but inverts awkwardly for a lower-is-better one, where the symmetric-looking
    `threshold / metric` compresses large overshoots -- a PBO of 1.0 against a 0.20 bar would read
    as "20% attained", i.e. bounded, when the true miss is unbounded. Distance from the bar in
    units of the bar is the same scale in both directions, is unbounded in both directions, and
    makes 0.9-vs-1.0 and 0.055-vs-0.05 directly comparable, which is what the ranking needs.

    Returns NaN when the arithmetic would be meaningless: a non-finite input, or a threshold whose
    magnitude is below `_THRESHOLD_MAGNITUDE_FLOOR`. NaN is a refusal to answer, not a big number.
    """
    m, t = float(metric), float(threshold.value)
    if not math.isfinite(m) or not math.isfinite(t):
        return math.nan
    if abs(t) < _THRESHOLD_MAGNITUDE_FLOOR:
        return math.nan
    gap = (t - m) if threshold.higher_is_better else (m - t)
    return max(0.0, gap / abs(t))


@dataclass(frozen=True)
class NearMissVerdict:
    """The triage of ONE already-failed candidate. Carries no authority to change its fate.

    `shortfalls` is ranked CLOSEST FIRST, so `shortfalls[0]` (equivalently `closest_gate`) is the
    single gate a re-measurement should attack first. Unmeasurable gates sort last regardless of
    anything else: an un-scored gate must never present itself as the closest one.
    """

    name: str
    classification: str
    failed_gates: tuple[str, ...]
    structural_failures: tuple[str, ...]
    statistical_failures: tuple[str, ...]
    unknown_gates: tuple[str, ...]
    unmeasured_gates: tuple[str, ...]
    shortfalls: tuple[GateShortfall, ...]
    worst_shortfall: float
    reason: str

    def __bool__(self) -> bool:
        """ALWAYS FALSE. Every candidate reaching this module has already failed.

        Hard-wired rather than left to Python's default object truthiness because the default is
        True, and `if triage(...):` is a one-character-plausible way for a caller to turn a triage
        label into an approval. There is no input to this module that produces a truthy result.
        """
        return False

    @property
    def closest_gate(self) -> str | None:
        """The single measured gate nearest to passing, or None if none could be scored."""
        for s in self.shortfalls:
            if s.measured:
                return s.gate
        return None

    @property
    def re_runnable(self) -> bool:
        """Whether re-measurement could plausibly change this candidate's fate.

        True when nothing structural blocks it, and ALSO true when the only structural blocks are
        in DATA_REPAIRABLE_STRUCTURAL -- `sample_adequacy` fails today and passes in six months
        with no change to the mechanism. This is a re-run QUEUE flag on a ledger row. It is not a
        verdict, it does not appear in `classification`, and a STRUCTURAL_DEAD candidate stays
        STRUCTURAL_DEAD whatever this says.
        """
        return all(g in DATA_REPAIRABLE_STRUCTURAL for g in self.structural_failures)

    def summary(self) -> str:
        worst = ("unmeasurable" if not math.isfinite(self.worst_shortfall)
                 else f"{self.worst_shortfall * 100:.1f}% of the bar")
        return (f"{self.name}: {self.classification} -- {len(self.failed_gates)} failed gate(s), "
                f"worst miss {worst}, closest {self.closest_gate or 'n/a'}")

    def to_record(self, *, as_of: str) -> dict[str, Any]:
        """One JSONL row. NaN is emitted as null -- `json.dumps` writes a bare NaN happily and no
        conforming parser downstream will read it back."""
        return {
            "as_of": as_of,
            "name": self.name,
            "classification": self.classification,
            "re_runnable": self.re_runnable,
            "failed_gates": list(self.failed_gates),
            "structural_failures": list(self.structural_failures),
            "statistical_failures": list(self.statistical_failures),
            "unknown_gates": list(self.unknown_gates),
            "unmeasured_gates": list(self.unmeasured_gates),
            "worst_shortfall": _jsonable(self.worst_shortfall),
            "closest_gate": self.closest_gate,
            "shortfalls": [
                {
                    "gate": s.gate,
                    "metric": _jsonable(s.metric),
                    "threshold": _jsonable(s.threshold),
                    "higher_is_better": s.higher_is_better,
                    "shortfall": _jsonable(s.shortfall),
                    "structural": s.structural,
                    "measured": s.measured,
                    "note": s.note,
                }
                for s in self.shortfalls
            ],
            "improvement_hint": improvement_hint(self),
            "near_miss_fraction": NEAR_MISS_FRACTION,
            "reason": self.reason,
        }


def _jsonable(x: float) -> float | None:
    return None if not math.isfinite(x) else float(x)


def _rank_key(s: GateShortfall) -> tuple[int, float, str]:
    """Closest first; unmeasured last. `not s.measured` leads the key so no NaN ever reaches the
    float comparison -- NaN sorts unpredictably and would scatter unmeasured gates through the
    ranking rather than parking them at the end."""
    return (0 if s.measured else 1, s.shortfall if s.measured else math.inf, s.gate)


def triage(gates: Mapping[str, bool], metrics: Mapping[str, float],
           thresholds: Mapping[str, Threshold], *, name: str = "?") -> NearMissVerdict:
    """Classify an ALREADY-FAILED candidate as NEAR_MISS / FAR_MISS / STRUCTURAL_DEAD.

    `gates` maps gate name -> cleared?; only the False entries are examined. `metrics` and
    `thresholds` supply, per failed gate, the value measured and the bar it had to clear.

    THE ORDER OF THE BRANCHES IS THE SAFETY PROPERTY, and each one is locked by a test:

      1. ANY structural failure -> STRUCTURAL_DEAD, first, before a single shortfall is compared.
         A mechanism with no story for who is forced to trade against you does not become fixable
         by missing narrowly; there is nothing to fix. This ordering is why "however small its
         shortfall" is testable as an invariant rather than an accident of the numbers.
      2. No failed gate at all -> NO_FAILURE_RECORDED, which is a caller bug, not a pass.
      3. An unrecognised gate name, or a failure that could not be SCORED -> FAR_MISS. Unknown must
         not land in the favourable class. It is deliberately not STRUCTURAL_DEAD either: calling a
         thing structurally dead on no evidence tells the desk to stop working on it, and on a desk
         where 53% of refutations are measurement failures that is the expensive direction to err.
      4. Everything else: NEAR_MISS iff the WORST measured shortfall is within
         MAX_NEAR_MISS_SHORTFALL. Worst, not mean -- a candidate that missed one gate by 2% and
         another by 300% is not 151% away from submittable, it is 300% away, and averaging would
         let a pile of nearly-passed gates hide a catastrophic one.

    Returns a verdict that is always falsy. It classifies; it never promotes.
    """
    failed = tuple(g for g, ok in gates.items() if not ok)
    structural = tuple(g for g in failed if g in STRUCTURAL_GATES)
    statistical = tuple(g for g in failed if g in STATISTICAL_GATES)
    unknown = tuple(g for g in failed
                    if g not in STRUCTURAL_GATES and g not in STATISTICAL_GATES)

    scored: list[GateShortfall] = []
    for g in failed:
        thr = thresholds.get(g)
        raw = metrics.get(g)
        if thr is None or raw is None:
            missing = "no threshold supplied" if thr is None else "no metric supplied"
            scored.append(GateShortfall(
                gate=g, metric=math.nan, threshold=math.nan,
                higher_is_better=True if thr is None else thr.higher_is_better,
                shortfall=math.nan, structural=g in STRUCTURAL_GATES, measured=False,
                note=f"{missing}; UNMEASURED is not NEAR"))
            continue
        sf = relative_shortfall(raw, thr)
        measured = math.isfinite(sf)
        note = "" if measured else (
            f"threshold {thr.value:.3g} is below the {_THRESHOLD_MAGNITUDE_FLOOR:g} magnitude "
            "floor or an input is non-finite, so a relative shortfall would be meaningless")
        scored.append(GateShortfall(
            gate=g, metric=float(raw), threshold=float(thr.value),
            higher_is_better=thr.higher_is_better, shortfall=sf,
            structural=g in STRUCTURAL_GATES, measured=measured, note=note))

    ranked = tuple(sorted(scored, key=_rank_key))
    unmeasured = tuple(s.gate for s in ranked if not s.measured)
    measured_gaps = [s.shortfall for s in ranked if s.measured]
    worst = max(measured_gaps) if measured_gaps else math.nan

    if structural:
        cls = STRUCTURAL_DEAD
        reason = (
            f"STRUCTURAL_DEAD: failed {', '.join(structural)}. A structural gate asks whether the "
            "thing can be traded at all and whether there is any reason it should work -- no "
            "amount of re-measurement repairs that, so the size of the miss is irrelevant and is "
            "not consulted.")
        if all(g in DATA_REPAIRABLE_STRUCTURAL for g in structural):
            reason += (" Flagged re-runnable: every structural failure here is one that a LARGER "
                       "SAMPLE repairs, so the ledger re-queues it when the data exists. The "
                       "classification is unchanged.")
    elif not failed:
        cls = NO_FAILURE_RECORDED
        reason = ("NO_FAILURE_RECORDED: no gate is marked failed. This module triages candidates "
                  "that ALREADY FAILED and has no pass verdict to give -- this label is a caller "
                  "bug surfacing, not an approval.")
    elif unknown:
        cls = FAR_MISS
        reason = (
            f"FAR_MISS: {', '.join(unknown)} is not a recognised gate, so it cannot be shown to be "
            "statistical. An unrecognised failure must not buy the favourable label; add the gate "
            "to screen_admission's STRUCTURAL_GATES or STATISTICAL_GATES to make it triageable.")
    elif unmeasured:
        cls = FAR_MISS
        reason = (
            f"FAR_MISS: {', '.join(unmeasured)} failed but could not be scored, so the candidate "
            "is not DEMONSTRATED to be close. Treating a missing input as a zero shortfall is the "
            "beats_baselines defect -- it returned True for every candidate for months because no "
            "caller supplied its input. Supply the metric and threshold and re-triage.")
    elif worst <= MAX_NEAR_MISS_SHORTFALL + _BOUNDARY_TOLERANCE:
        cls = NEAR_MISS
        reason = (
            f"NEAR_MISS: every failure is statistical and the worst is {worst * 100:.1f}% of its "
            f"bar, inside the {MAX_NEAR_MISS_SHORTFALL * 100:.0f}% band. The candidate is still "
            "FAILED; it is recorded as worth re-measuring or re-engineering rather than discarded.")
    else:
        cls = FAR_MISS
        reason = (
            f"FAR_MISS: worst statistical shortfall is {worst * 100:.1f}% of its bar, outside the "
            f"{MAX_NEAR_MISS_SHORTFALL * 100:.0f}% band. Recorded so the distance is countable, "
            "but it is not a near-term work item.")

    return NearMissVerdict(
        name=name, classification=cls, failed_gates=failed, structural_failures=structural,
        statistical_failures=statistical, unknown_gates=unknown, unmeasured_gates=unmeasured,
        shortfalls=ranked, worst_shortfall=worst, reason=reason)


# -------------------------------------------------------------------------------------------
# Hints. EVERY string this module can emit as advice lives in this section, and every one of them
# is checked by tests/validation/test_near_miss.py against a banned vocabulary. A hint that says
# "consider a lower bar" is not a mild wording problem on this desk -- it is the exact mechanism by
# which a gate gets relaxed to manufacture survivors, arriving as helpful-sounding prose. The rule
# these are written to: a hint may ask for MORE MEASUREMENT (more data, a longer sample, an honest
# trial count, a real cost model, correct alignment) or a BETTER MECHANISM. It may never ask for a
# different bar. The banned vocabulary lives in the TEST, not here, so that a hint cannot be
# legalised by editing the guard alongside the violation.
# -------------------------------------------------------------------------------------------

GATE_HINTS: dict[str, str] = {
    # ---- statistical: re-measurement or re-engineering can genuinely move these -------------
    "dsr": (
        "Deflated Sharpe is a function of sample length AND the number of trials it is deflated "
        "for. Extend the sample, and check the trial count being charged is the number of "
        "hypotheses actually tested rather than every variant ever fitted -- an inflated trial "
        "count deflates a Sharpe the candidate genuinely earned."),
    "pbo": (
        "Probability of backtest overfitting is driven by how much the parameter set is tuned per "
        "split. Re-fit with fewer free parameters, or with parameters chosen once and held fixed "
        "across splits, and confirm the splits are purged and embargoed so the same trade is not "
        "in both halves."),
    "reality_check": (
        "White's reality check compares the candidate against the best of the null over the FULL "
        "set of strategies searched. Supply the complete competing set and more bootstrap "
        "resamples; a truncated set and a short bootstrap both make the null look stronger than "
        "it is."),
    "walk_forward": (
        "Walk-forward efficiency measures whether the fit survives being re-fitted forward. Add "
        "history so there are more folds, and make the refit cadence match how the desk would "
        "actually re-parameterise in production rather than an idealised schedule."),
    "cpcv": (
        "Combinatorial purged cross-validation fails when leakage crosses the fold boundary. "
        "Verify the purge window covers the full holding period and the embargo covers the "
        "signal's lookback, then re-run on more history."),
    "not_too_lucky": (
        "The luck check flags a result carried by a handful of observations. Re-measure with the "
        "outlier bars retained but the position sized as it would really have been, and confirm "
        "the fills are executable rather than a mid-price fantasy -- an honest cost model usually "
        "moves this more than any parameter does."),
    "beats_baselines": (
        "THE MEASURED CASE ON THIS DESK: beats_baselines returned True for every candidate for "
        "months because no caller ever supplied its input. Supply the baseline series -- buy-and- "
        "hold, the cohort's own median, and the naive momentum variant -- and re-run. An "
        "unsupplied comparison is unmeasured, never satisfied."),
    # ---- structural: measurement does not repair these; the mechanism has to change ---------
    "economic_mechanism": (
        "There is no story for WHO is forced to trade against this and WHAT forces them. That is "
        "not a measurement shortfall, it is the absence of a reason for the edge to exist, and it "
        "makes the result a data artifact by default. Name the constrained counterparty and the "
        "constraint, or work on a different mechanism."),
    "expected_value": (
        "Expectancy is negative. Re-measure once with the desk's real cost model -- funding every "
        "eight hours, fees, and slippage applied per fill rather than post-hoc -- because a "
        "mis-applied cost model has flipped this sign before. If expectancy is still negative net "
        "of honest costs, the mechanism must change; forward-testing it is a paid way to lose."),
    "capacity": (
        "The mechanism cannot absorb the desk's size. Re-measure capacity against real book depth "
        "and the participation rate actually used, then either find the edge in a deeper part of "
        "the universe or accept that it is untradeable here at any confidence level."),
    "fragility": (
        "Tail behaviour that would damage the book. This is a safety property, not a p-value, so "
        "no sample size settles it. Change the mechanism -- cap the exposure that produces the "
        "tail, or hedge it explicitly -- and re-measure the stressed path afterwards."),
    "break_even_win_rate": (
        "The per-trade arithmetic does not close: p* = |avg_loss| / (avg_win + |avg_loss|) sits "
        "above the realised win rate. The desk's own worked case is p* = 35.4% against a realised "
        "41.3%, and that 5.9-point gap over 758 trades WAS the entire 24.9x return. Grow the "
        "average winner or cut the average loser -- the exit logic is the lever here, not the "
        "entry signal."),
    "sample_adequacy": (
        "There is not enough data to measure this candidate yet. The one structural failure that "
        "time alone repairs: re-queue it and re-run when the sample has grown. Nothing about the "
        "mechanism has been refuted."),
}

_UNMEASURED_HINT = (
    "FIRST, SUPPLY THE MISSING INPUT: {gates} failed with no metric or no usable threshold to "
    "score against, so how close this came is unknown rather than known-to-be-far. An unsupplied "
    "input is unmeasured, never passed.")

_UNKNOWN_GATE_HINT = (
    "FIRST, NAME THE GATE: {gates} is not in screen_admission's STRUCTURAL_GATES or "
    "STATISTICAL_GATES, so this module cannot tell whether re-measurement could help. Register it "
    "in the correct list and re-triage.")

_NO_FAILURE_HINT = (
    "Nothing to triage: no gate is marked failed. This module classifies candidates that already "
    "failed and issues no pass verdict; check what the caller handed in.")

_NO_HINT = (
    "No gate-specific guidance is registered for the failing gate. Add one to GATE_HINTS keyed to "
    "that gate rather than acting on a guess.")

_NEAR_MISS_PREFIX = (
    "NEAR-MISS at {pct:.1f}% of the bar on '{gate}', which is the single closest gate and "
    "therefore where re-measurement buys the most. This candidate remains FAILED; it is queued "
    "for improvement, not admitted.")

_FAR_MISS_PREFIX = (
    "FAR MISS: '{gate}' is the closest gate and still {pct:.1f}% of the bar away. Recorded so the "
    "distance is countable and re-checkable, but the work below is a bigger job than a re-run.")

_STRUCTURAL_PREFIX = (
    "STRUCTURALLY DEAD on '{gate}'. No sample size and no re-measurement changes this verdict; "
    "what follows is what would have to be TRUE of the mechanism instead.")


def improvement_hint(verdict: NearMissVerdict) -> str:
    """What would have to CHANGE for this candidate to clear the bar it missed.

    Keyed to the specific gate: the closest measured statistical gate when there is one, the
    blocking structural gate when the candidate is structurally dead, and an explicit
    supply-the-input instruction when the failure could not be scored at all.

    THE INVARIANT, asserted over every hint this module can emit: no hint ever suggests moving a
    threshold. Every one asks for more or better MEASUREMENT (data, sample length, honest trial
    count, real cost model, correct alignment) or a better MECHANISM. Relaxing a statistical gate
    to manufacture survivors is the failure this desk has been burned by and forbids outright, and
    it would arrive here disguised as a helpful suggestion, which is why the ban is enforced by a
    keyword test over `all_hints()` rather than by intention.
    """
    if verdict.classification == NO_FAILURE_RECORDED:
        return _NO_FAILURE_HINT

    if verdict.structural_failures:
        gate = next((s.gate for s in verdict.shortfalls if s.structural),
                    verdict.structural_failures[0])
        return f"{_STRUCTURAL_PREFIX.format(gate=gate)} {GATE_HINTS.get(gate, _NO_HINT)}"

    if verdict.unknown_gates:
        return _UNKNOWN_GATE_HINT.format(gates=", ".join(verdict.unknown_gates))

    if verdict.unmeasured_gates:
        head = _UNMEASURED_HINT.format(gates=", ".join(verdict.unmeasured_gates))
        # Still append the gate-specific guidance when SOMETHING was scoreable: the missing input
        # is the first job, but naming the second one costs nothing and is what makes the ledger
        # row actionable in one pass.
        near = verdict.closest_gate
        return head if near is None else f"{head} {GATE_HINTS.get(near, _NO_HINT)}"

    closest = verdict.closest_gate
    if closest is None:
        return _NO_HINT
    pct = next(s.shortfall for s in verdict.shortfalls if s.gate == closest) * 100.0
    prefix = (_NEAR_MISS_PREFIX if verdict.classification == NEAR_MISS else _FAR_MISS_PREFIX)
    return f"{prefix.format(gate=closest, pct=pct)} {GATE_HINTS.get(closest, _NO_HINT)}"


def all_hints() -> tuple[str, ...]:
    """Every advice string this module can emit, for exhaustive checking by the test suite.

    Enumerated rather than sampled ON PURPOSE. A banned-vocabulary test that only inspects the
    hints a handful of constructed verdicts happen to reach would pass while an unreachable-today
    hint sat in the table saying "consider a lower bar", waiting for the branch that emits it. The
    test also asserts this covers every gate in STRUCTURAL_GATES + STATISTICAL_GATES, so adding a
    gate without a hint fails CI rather than silently degrading to _NO_HINT.
    """
    return (*GATE_HINTS.values(), _UNMEASURED_HINT, _UNKNOWN_GATE_HINT, _NO_FAILURE_HINT, _NO_HINT,
            _NEAR_MISS_PREFIX, _FAR_MISS_PREFIX, _STRUCTURAL_PREFIX)


# -------------------------------------------------------------------------------------------
# The ledger. The whole point of the module: a near-miss that leaves no record is the status quo.
# -------------------------------------------------------------------------------------------


def log_near_misses(verdicts: Iterable[NearMissVerdict], path: Path | str,
                    *, as_of: str | None = None) -> int:
    """APPEND triage rows to a JSONL ledger. Returns how many rows were written.

    APPEND, never rewrite. The value of this file is that it ACCUMULATES: a near-miss recorded in
    March is re-runnable in September when the sample that would have settled it exists, and a
    ledger that is overwritten each campaign has exactly the memory the desk already lacks.

    EVERY verdict handed in is written, including FAR_MISS and STRUCTURAL_DEAD, with its
    classification and `re_runnable` flag on the row. Filtering at WRITE time is how the current
    silent death happens -- the defect being fixed is that no record was written at all -- and a
    reader wanting only the work queue filters on `re_runnable`, which costs nothing and keeps the
    denominator. Without the denominator "we had 8 near-misses" is unreadable; with it, the ratio
    of near to far to dead is itself a measurement of where the campaign died.

    THE TRAILING-NEWLINE REPAIR IS NOT COSMETIC. If a previous writer was killed mid-line, the file
    ends without a newline, and appending would splice a new record onto the tail of the truncated
    one -- corrupting a good row with a bad one and losing BOTH. A separator is written first when
    the existing file does not end in a newline, which leaves the truncated line corrupt (it
    already was) and the new row intact.
    """
    stamp = as_of if as_of is not None else to_iso8601(utcnow())
    rows = [v.to_record(as_of=stamp) for v in verdicts]
    if not rows:
        return 0
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    needs_separator = False
    if p.exists():
        try:
            with p.open("rb") as fh:
                if fh.seek(0, 2) > 0:
                    fh.seek(-1, 2)
                    needs_separator = fh.read(1) != b"\n"
        except OSError:
            needs_separator = False
    with p.open("a", encoding="utf-8") as fh:
        if needs_separator:
            fh.write("\n")
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    return len(rows)


def read_near_miss_ledger(path: Path | str) -> tuple[dict[str, Any], ...]:
    """Read the ledger back, SKIPPING lines that will not parse.

    A ledger that raises on one bad line is a ledger that loses every good line after it, and the
    bad line is usually the half-written tail of a process that was killed -- i.e. exactly the
    moment the surviving history matters most. Corrupt lines are dropped silently here rather than
    repaired or guessed at; the count of parsed rows is the honest output, and a caller comparing
    it against the file's line count can see the loss.

    A missing file returns an empty tuple: the ledger not existing yet is the desk's CURRENT state
    (data/forward_slots.json has never existed either) and is not an error.
    """
    p = Path(path)
    if not p.exists():
        return ()
    try:
        text = p.read_text("utf-8")
    except OSError:
        return ()
    out: list[dict[str, Any]] = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except json.JSONDecodeError:
            continue
        # A parsed non-object is as unusable as an unparseable line -- a bare number or list has no
        # classification to read -- so it is dropped on the same terms rather than crashing later.
        if isinstance(obj, dict):
            out.append(obj)
    return tuple(out)
