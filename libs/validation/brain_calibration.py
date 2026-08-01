"""AN INDEPENDENT WITNESS ON THE ONE NUMBER THIS DESK MEASURED ITSELF GETTING WRONG.

WHY THIS FILE EXISTS. On 2026-08-01 the desk audited its own gauntlet end to end
(docs/research/gate_power_audit.md). The sensitivity floor -- the true Sharpe at which the gate
finally admits a real candidate with usable probability -- sits at TRUE SHARPE 5.0 (85.42% power;
23.75% at 3.0, 5.83% at 2.0, 1.67% at 1.5). The same desk records
`REAL_EDGE_OOS_SHARPE_BAND = (0.5, 1.5)` in libs/validation/robustness_filters.py as the band where
verified edge is empirically observed to live, from a 131,441-backtest external sweep. The gate is
therefore calibrated 3.3-10x above the ENTIRE range its own evidence says it is hunting in, and the
audit closes by recording that as a job explicitly not finished (§9).

A miss that large wants a witness that has never seen this repo. This module is that witness.

THE WITNESS. A WorldQuant BRAIN webinar transcript (2026-08-01, principal-supplied) states the
operational thresholds of a LIVE institutional alpha pipeline -- one that pays research consultants
on its output, so its thresholds are not a teaching example or a paper's suggestion but numbers
somebody's money passes through daily. It is calibrating the same quantity: "how good must a
candidate be before we act on it". It arrives at a Sharpe bar of 1.0 and a target of ~1.25.

THE HEADLINE, and it is the entire reason to read this file:

    desk sensitivity floor   5.00 true Sharpe   (measured, gate_power_audit §1)
    BRAIN submission target  1.25 Sharpe        (stated, transcript)
    ratio                    4.0x

    desk real-edge band      (0.50, 1.50) OOS Sharpe   (external 131k sweep)
    BRAIN recent-period floor 0.50 Sharpe               (stated, transcript)
    ratio                    1.0x  -- EXACT AGREEMENT at the bottom of the band

Two independent sources -- a 131,441-backtest sweep and a live institutional pipeline -- put the
lower edge of actionable edge at 0.5 Sharpe, from completely different data. The desk's gate is
positioned an order of magnitude above the point where both of them agree real alpha begins. That
is a far stronger statement than either source alone, and it is what this module exists to make
countable.

ANNUALISATION AND ASSET-CLASS CAVEAT -- READ BEFORE USING ANY NUMBER HERE.
BRAIN alphas are US EQUITY, daily rebalanced, dollar-neutral, and their "Sharpe" is computed on
their own platform convention (their own PnL definition, their own annualisation, their own cost
model). This desk trades CRYPTO PERPS continuously, funds every eight hours, and annualises on 365
days. Neither the periodicity, the cost base, the return definition, nor the survivorship
properties of the two universes match. These numbers are COMPARABLE IN ORDER OF MAGNITUDE ONLY and
must NEVER be pasted into a gate as-is.
A READER WHO TAKES 1.25 AS A THRESHOLD HAS MISUSED THIS MODULE.
The comparison that is legitimate is "is this desk's bar 1x or 10x off?", and the answer to that
survives every convention difference above. The comparison that is not legitimate is "therefore set
the threshold to 1.25".

STATUS -- stated plainly because this desk's own rule says a module with tests and no production
importer is DRAFTED, not built. This one is deliberately DRAFTED. It is a CALIBRATION REFERENCE and
it is wired into no decision path on purpose: an external number that quietly becomes a threshold
is precisely the failure the caveat above exists to prevent. `gap_report()` is shaped for a
reporting script to dump as JSON; nothing here may be imported by a gate, a screen, or a sizer.

CONFIDENCE MARKING. Several of the transcript's numbers are spoken asides rather than slides, and
an aside quoted to two decimal places is how a soft number becomes a hard threshold six months
later. Every constant below therefore carries its verbatim quote and one of three markers, and
`SOURCE_NOTES` exposes the same thing machine-readably:
    STATED      -- said as a definite threshold
    APPROXIMATE -- hedged, rounded, or spoken as an aside ("about", "at least 0.5 or 1.0")
    DERIVED     -- computed here from a stated number, never spoken (e.g. the OOS score weight)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

from libs.validation.robustness_filters import REAL_EDGE_OOS_SHARPE_BAND

__all__ = [
    "BRAIN",
    "BRAIN_FITNESS_SUBMISSION_BAR",
    "BRAIN_IS_SCORE_WEIGHT",
    "BRAIN_NEAR_SUBMITTABLE_FITNESS_SHORTFALL",
    "BRAIN_NEAR_SUBMITTABLE_FRACTION",
    "BRAIN_OOS_SCORE_WEIGHT",
    "BRAIN_RECENT_SHARPE_FLOOR",
    "BRAIN_RECENT_SHARPE_FLOOR_UPPER",
    "BRAIN_SELF_CORRELATION_CAP",
    "BRAIN_SHARPE_BAR",
    "BRAIN_SHARPE_TARGET",
    "BRAIN_STAGE2_ACCEPTANCE_FRACTION",
    "BRAIN_TRUNCATION_BAND",
    "BRAIN_TRUNCATION_DEFAULT",
    "BRAIN_TS_BACKFILL_FITNESS_AFTER",
    "BRAIN_TS_BACKFILL_FITNESS_BEFORE",
    "DESK_CAMPAIGN_N",
    "DESK_CORRELATION_CLUSTER_THRESHOLD",
    "DESK_FORWARD_SLOTS",
    "DESK_MAX_SINGLE_NAME_WEIGHT",
    "DESK_REAL_EDGE_BAND",
    "DESK_SENSITIVITY_FLOOR_SHARPE",
    "SOURCE_NOTES",
    "Calibration",
    "Comparison",
    "annualisation_caveat",
    "compare",
    "gap_report",
]

Confidence = Literal["STATED", "APPROXIMATE", "DERIVED"]

SOURCE = "WorldQuant BRAIN webinar transcript, 2026-08-01 (principal-supplied)"

# ---------------------------------------------------------------------------------------------
# BRAIN thresholds. Transcribed verbatim; see SOURCE_NOTES for the quote behind each one.
# ---------------------------------------------------------------------------------------------

#: STATED. The alpha submission bar, on BRAIN's own composite `fitness` statistic. NOT a Sharpe and
#: NOT convertible to one here: fitness folds returns, turnover and drawdown together on a formula
#: the transcript never states, so any conversion would be this desk inventing the missing half.
#: Kept because the ratio between a candidate's fitness and this bar is meaningful even when the
#: absolute number is not portable.
BRAIN_FITNESS_SUBMISSION_BAR = 1.0

#: STATED, as the bar being missed in "you're only getting 0.7 sharpe instead of one, or instead of
#: 1.25", and again in the near-submittable example ("Sharpe 0.9 vs a 1.0 bar").
BRAIN_SHARPE_BAR = 1.0

#: APPROXIMATE. Same breath as the line above -- two numbers quoted together, so both are kept
#: rather than one being picked. 1.0 is the bar an alpha must clear; 1.25 is what a submitter is
#: actually aiming at. The gap between them is the transcript's own margin of safety, and this
#: desk keeping both is the difference between reading a threshold and reading a practice.
BRAIN_SHARPE_TARGET = 1.25

#: APPROXIMATE. "Near-submittable" = roughly 80% of the submission metrics -- e.g. Sharpe 0.9
#: against a 1.0 bar. The operationally important half is what it MEANS: near-submittable alphas
#: are worth IMPROVING, not discarding. That is a triage policy this desk does not have; its
#: gauntlet emits PASS/FAIL and a near-miss dies silently.
BRAIN_NEAR_SUBMITTABLE_FRACTION = 0.80

#: APPROXIMATE. The same near-miss band expressed on fitness: "fitness ~30% below threshold" still
#: counts as worth working on. Not the exact complement of the 80% figure above (that would be 20%),
#: and the discrepancy is left standing rather than reconciled -- reconciling two spoken asides into
#: one tidy number is how a transcript becomes a fabrication.
BRAIN_NEAR_SUBMITTABLE_FITNESS_SHORTFALL = 0.30

#: STATED, and the single most transferable number in the transcript: "25% weightage is only for
#: IS". A live pipeline that pays people gives in-sample performance a QUARTER of the score.
BRAIN_IS_SCORE_WEIGHT = 0.25

#: DERIVED -- the complement, never spoken. Out-of-sample carries ~75% of the score.
BRAIN_OOS_SCORE_WEIGHT = 1.0 - BRAIN_IS_SCORE_WEIGHT

#: APPROXIMATE ("around 0.7"). Cap on a new alpha's correlation to the SUBMITTER'S OWN existing
#: pool -- not to the market, and not the cohort-average correlation that
#: libs/research/cohort_independence.py benchmarks at 0.159. It is a per-candidate admission cap
#: against an already-live book, which is a check this desk does not run at all.
BRAIN_SELF_CORRELATION_CAP = 0.7

#: STATED. Position truncation = the maximum weight any single name may carry. Ideal band 5-10%.
BRAIN_TRUNCATION_BAND = (0.05, 0.10)
#: STATED. The platform default inside that band.
BRAIN_TRUNCATION_DEFAULT = 0.08

#: APPROXIMATE ("at least 0.5 or 1.0"). The recent-period floor: the last few years must be
#: POSITIVE on their own, and a negative recent Sharpe is unacceptable however good the full
#: history looks. The LOWER of the two spoken figures is taken as the floor, because taking the
#: higher would be this desk inventing strictness the source did not state.
#:
#: If this ever were ported into a gate -- which the module docstring forbids -- note that the
#: operative encoding is `>= 0.5`, NOT `> 0`. A bare `> 0` on a Sharpe is exactly the guard that
#: shipped a 1.4e31 fake signal here on 2026-08-01: floating-point dust clears it, and a frozen or
#: pegged series produces dust rather than zero.
BRAIN_RECENT_SHARPE_FLOOR = 0.5
BRAIN_RECENT_SHARPE_FLOOR_UPPER = 1.0

#: APPROXIMATE ("approximately top 20%"). Stage-1 -> stage-2 competition acceptance rate.
BRAIN_STAGE2_ACCEPTANCE_FRACTION = 0.20

#: STATED, as a worked example: fitness 1.28 -> 1.42 from adding `ts_backfill` alone. Recorded
#: because it sizes what a single engineering fix is worth on a real pipeline -- +10.9%, from
#: handling missing data properly rather than from a new mechanism. This desk's own audit found the
#: same shape of result (53% of its refutations were measurement failures, not absent alpha).
BRAIN_TS_BACKFILL_FITNESS_BEFORE = 1.28
BRAIN_TS_BACKFILL_FITNESS_AFTER = 1.42

# ---------------------------------------------------------------------------------------------
# This desk's counterpart numbers. Every one is imported or cited, never retyped from memory.
# ---------------------------------------------------------------------------------------------

#: MEASURED, docs/research/gate_power_audit.md §1: the true annualised Sharpe at which the fixed
#: gauntlet first reaches usable power (85.42%; 23.75% at 3.0, 5.83% at 2.0, 1.67% at 1.5). This is
#: the quantity BRAIN's submission bar is the external calibration OF.
DESK_SENSITIVITY_FLOOR_SHARPE = 5.0

#: Imported rather than copied so it cannot silently drift out of agreement with the filter module
#: that owns it. (0.5, 1.5) OOS Sharpe, from a 131,441-backtest external sweep.
DESK_REAL_EDGE_BAND = REAL_EDGE_OOS_SHARPE_BAND

#: libs/portfolio/models.py :: PortfolioConstraints.max_weight default -- the desk's counterpart to
#: BRAIN's position truncation, and the one comparison in this file that runs the OTHER way.
DESK_MAX_SINGLE_NAME_WEIGHT = 0.25

#: libs/portfolio/diversification.py :: apply_correlation_controls(cluster_threshold=0.8). A LOOSE
#: analogue of BRAIN's self-correlation cap: it is a clustering linkage threshold over the existing
#: book, not a per-candidate admission cap, so the two numbers are the same shape but not the same
#: measurement. Reported with that caveat attached rather than dropped.
DESK_CORRELATION_CLUSTER_THRESHOLD = 0.8

#: libs/research/slot_registry.py :: MAX_FORWARD_SLOTS, and the campaign size the gate audit ran.
#: 12/420 = 2.9% is the desk's CAPACITY ceiling on advancement; the measured gate promoted 0.00 of
#: 20 genuine alphas at true SR 2.0-3.0 (audit §6), so the realised rate is lower still.
DESK_FORWARD_SLOTS = 12
DESK_CAMPAIGN_N = 420

#: Below this a Sharpe is not a small Sharpe, it is zero wearing a decimal point, and using it as
#: the denominator of a ratio manufactures an arbitrarily large "gap". Same defect class as the
#: `> 0` variance guard that produced a 1.4e31 prediction premium here on 2026-08-01: the fix is a
#: MEANINGFUL floor, not a tighter comparison against zero. 1e-3 annualised Sharpe is far below any
#: measurable edge and far above float dust.
_SHARPE_FLOOR = 1e-3

#: Ratios inside [1/1.25, 1.25] are reported as COMPARABLE rather than as one side being stricter.
#: The module docstring says these numbers agree to an order of magnitude and no further; declaring
#: a winner on a 6% difference would be reading precision that provably is not there.
_COMPARABLE_RATIO = 1.25

#: Verbatim quotes and confidence markers, machine-readable so a report can carry the provenance
#: alongside the number instead of stripping it. Keyed by constant name.
SOURCE_NOTES: dict[str, tuple[Confidence, str]] = {
    "BRAIN_FITNESS_SUBMISSION_BAR": ("STATED", "alpha submission bar: fitness > 1.0"),
    "BRAIN_SHARPE_BAR": (
        "STATED", "you're only getting 0.7 sharpe instead of one, or instead of 1.25"),
    "BRAIN_SHARPE_TARGET": (
        "APPROXIMATE", "you're only getting 0.7 sharpe instead of one, or instead of 1.25"),
    "BRAIN_NEAR_SUBMITTABLE_FRACTION": (
        "APPROXIMATE", "near-submittable = ~80% of the submission metrics (Sharpe 0.9 vs a 1.0 "
                       "bar) -- worth improving rather than discarding"),
    "BRAIN_NEAR_SUBMITTABLE_FITNESS_SHORTFALL": (
        "APPROXIMATE", "fitness ~30% below threshold is still near-submittable"),
    "BRAIN_IS_SCORE_WEIGHT": ("STATED", "25% weightage is only for IS"),
    "BRAIN_OOS_SCORE_WEIGHT": ("DERIVED", "complement of the stated 25% IS weight; never spoken"),
    "BRAIN_SELF_CORRELATION_CAP": (
        "APPROXIMATE", "self-correlation against your own existing alpha pool capped around 0.7"),
    "BRAIN_TRUNCATION_BAND": ("STATED", "truncation ideal band 5-10%"),
    "BRAIN_TRUNCATION_DEFAULT": ("STATED", "truncation default 8%"),
    "BRAIN_RECENT_SHARPE_FLOOR": (
        "APPROXIMATE", "the last few years must be positive, at least 0.5 or 1.0 sharpe; a "
                       "negative recent sharpe is not acceptable even if the full history looks "
                       "fine"),
    "BRAIN_RECENT_SHARPE_FLOOR_UPPER": ("APPROXIMATE", "at least 0.5 or 1.0"),
    "BRAIN_STAGE2_ACCEPTANCE_FRACTION": (
        "APPROXIMATE", "stage-1 to stage-2 acceptance is approximately the top 20%"),
    "BRAIN_TS_BACKFILL_FITNESS_BEFORE": ("STATED", "fitness 1.28 -> 1.42 from ts_backfill alone"),
    "BRAIN_TS_BACKFILL_FITNESS_AFTER": ("STATED", "fitness 1.28 -> 1.42 from ts_backfill alone"),
}


@dataclass(frozen=True)
class Calibration:
    """One external pipeline's operating thresholds, as a bundle.

    A dataclass rather than loose constants so a SECOND external calibration can be written down
    later and compared on the same axes. One outside number is an anecdote; two that disagree
    would be the more informative result, and there is nowhere to put the second one otherwise.
    """

    source: str
    fitness_bar: float
    sharpe_bar: float
    sharpe_target: float
    near_submittable_fraction: float
    is_score_weight: float
    self_correlation_cap: float
    truncation_default: float
    truncation_band: tuple[float, float]
    recent_sharpe_floor: float
    stage2_acceptance_fraction: float

    @property
    def oos_score_weight(self) -> float:
        """DERIVED, not stated: whatever is not weighted in-sample is weighted out-of-sample."""
        return 1.0 - self.is_score_weight

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "fitness_bar": self.fitness_bar,
            "sharpe_bar": self.sharpe_bar,
            "sharpe_target": self.sharpe_target,
            "near_submittable_fraction": self.near_submittable_fraction,
            "is_score_weight": self.is_score_weight,
            "oos_score_weight": self.oos_score_weight,
            "self_correlation_cap": self.self_correlation_cap,
            "truncation_default": self.truncation_default,
            "truncation_band": list(self.truncation_band),
            "recent_sharpe_floor": self.recent_sharpe_floor,
            "stage2_acceptance_fraction": self.stage2_acceptance_fraction,
        }


BRAIN = Calibration(
    source=SOURCE,
    fitness_bar=BRAIN_FITNESS_SUBMISSION_BAR,
    sharpe_bar=BRAIN_SHARPE_BAR,
    sharpe_target=BRAIN_SHARPE_TARGET,
    near_submittable_fraction=BRAIN_NEAR_SUBMITTABLE_FRACTION,
    is_score_weight=BRAIN_IS_SCORE_WEIGHT,
    self_correlation_cap=BRAIN_SELF_CORRELATION_CAP,
    truncation_default=BRAIN_TRUNCATION_DEFAULT,
    truncation_band=BRAIN_TRUNCATION_BAND,
    recent_sharpe_floor=BRAIN_RECENT_SHARPE_FLOOR,
    stage2_acceptance_fraction=BRAIN_STAGE2_ACCEPTANCE_FRACTION,
)


@dataclass(frozen=True)
class Comparison:
    """The desk's gate position measured against an external pipeline's, in ratios.

    `stricter` is one of DESK / BRAIN / COMPARABLE / UNKNOWN. UNKNOWN is returned for any input
    that cannot be compared and it is deliberately NOT a synonym for COMPARABLE -- an unreadable
    input must produce a verdict a reader stops at, never one that reads as agreement.
    """

    desk_floor_sharpe: float
    desk_band: tuple[float, float]
    brain_sharpe_bar: float
    brain_sharpe_target: float
    ratio_floor_to_bar: float
    ratio_floor_to_target: float
    ratio_floor_to_band_top: float
    stricter: str
    verdict: str

    def summary(self) -> str:
        return (f"desk floor {self.desk_floor_sharpe:.2f} SR vs BRAIN target "
                f"{self.brain_sharpe_target:.2f} SR = {self.ratio_floor_to_target:.2f}x "
                f":: {self.stricter} :: {self.verdict}")


def annualisation_caveat() -> str:
    """The comparability caveat, as text a report can print next to the numbers.

    Duplicated from the module docstring ON PURPOSE. A caveat that lives only in a docstring is
    read once by the author and never again by the person pasting a number into a config; this
    version travels with `gap_report()` into whatever JSON or dashboard consumes it. The test
    suite asserts BOTH copies still contain every load-bearing phrase, because a calibration module
    whose caveat quietly got deleted is more dangerous than no calibration module at all.
    """
    return (
        "COMPARABILITY CAVEAT. BRAIN alphas are US equity, daily rebalanced, dollar-neutral, and "
        "their Sharpe is computed on their own platform convention -- their PnL definition, their "
        "annualisation, their cost model. This desk trades crypto perps continuously, funds every "
        "eight hours, and annualises on 365 days. Periodicity, cost base, return definition and "
        "universe survivorship all differ. These numbers are COMPARABLE IN ORDER OF MAGNITUDE "
        "ONLY and must never be pasted into a gate as-is. A reader who takes 1.25 as a threshold "
        "has misused this module. The legitimate question is 'is this desk's bar 1x or 10x off?', "
        "whose answer survives every convention difference above; the illegitimate one is "
        "'therefore set the threshold to 1.25'."
    )


def _ratio(desk: float, external: float) -> float:
    """desk / external, with a MEANINGFUL floor on the denominator rather than a `> 0` guard."""
    if not math.isfinite(desk) or not math.isfinite(external):
        return math.nan
    if abs(external) < _SHARPE_FLOOR:
        return math.nan
    return desk / external


def compare(desk_floor_sharpe: float, desk_band: tuple[float, float]) -> Comparison:
    """This desk's sensitivity floor against BRAIN's submission bar.

    Direction convention: for a FLOOR, higher means stricter, so a ratio above 1 means this desk
    demands more than the external pipeline does before it will act.

    Every unreadable input lands in the UNKNOWN branch and reports no ratio. That is the house rule
    about ambiguous branches applied to a reference module: the tempting behaviour here is to fall
    back on defaults and print a reassuring number, and a fabricated 4.0x is indistinguishable from
    a measured one once it is in a report.
    """
    floor = float(desk_floor_sharpe)
    lo, hi = float(desk_band[0]), float(desk_band[1])
    bar, target = BRAIN.sharpe_bar, BRAIN.sharpe_target
    nan = math.nan

    if not all(math.isfinite(v) for v in (floor, lo, hi)):
        return Comparison(floor, (lo, hi), bar, target, nan, nan, nan, "UNKNOWN",
                          "UNCOMPARABLE: non-finite desk input, so no ratio is reported. A "
                          "missing measurement is not a passing one")
    if floor < _SHARPE_FLOOR:
        return Comparison(floor, (lo, hi), bar, target, nan, nan, nan, "UNKNOWN",
                          f"UNCOMPARABLE: a sensitivity floor of {floor:.3g} Sharpe is at or "
                          f"below the {_SHARPE_FLOOR:g} noise floor -- that is not a low bar, it "
                          "is an unmeasured one")
    if hi < lo or hi < _SHARPE_FLOOR:
        return Comparison(floor, (lo, hi), bar, target, nan, nan, nan, "UNKNOWN",
                          f"UNCOMPARABLE: desk band ({lo:.3g}, {hi:.3g}) is inverted or "
                          "degenerate")

    r_bar = _ratio(floor, bar)
    r_target = _ratio(floor, target)
    r_band = _ratio(floor, hi)

    if r_target > _COMPARABLE_RATIO:
        stricter = "DESK"
        verdict = (
            f"DESK STRICTER BY {r_target:.1f}x. This desk admits candidates only from true Sharpe "
            f"{floor:.2f}, against a live institutional pipeline that submits at {bar:.2f} and "
            f"targets {target:.2f}. It also sits {r_band:.1f}x above {hi:.2f}, the TOP of the "
            f"band where this desk's own evidence says real edge lives -- so the gate is not "
            f"merely conservative, it is positioned outside the range it is hunting in. BRAIN "
            f"pays consultants for alphas this gauntlet would never show anyone.")
    elif r_target < 1.0 / _COMPARABLE_RATIO:
        stricter = "BRAIN"
        verdict = (
            f"BRAIN STRICTER BY {1.0 / r_target:.1f}x. This desk's floor of {floor:.2f} Sharpe "
            f"sits BELOW the external submission target of {target:.2f}, which reverses the "
            f"2026-08-01 finding and should be checked against docs/research/gate_power_audit.md "
            f"before anything is concluded from it.")
    else:
        stricter = "COMPARABLE"
        verdict = (
            f"COMPARABLE. Desk floor {floor:.2f} and BRAIN target {target:.2f} agree within "
            f"{_COMPARABLE_RATIO:.2f}x, which is as close as two conventions this different can "
            f"meaningfully be read.")

    return Comparison(floor, (lo, hi), bar, target, r_bar, r_target, r_band, stricter, verdict)


def _jsonable(x: float) -> float | None:
    """NaN is not valid JSON. An unmeasurable ratio is emitted as null, never as 0.0 or a guess."""
    return None if not math.isfinite(x) else float(x)


def _direction(ratio: float | None, *, higher_is_stricter: bool, desk_present: bool) -> str:
    """Which side is tighter, given that some of these quantities invert.

    A FLOOR is stricter when it is higher; a position CAP is stricter when it is LOWER. Reporting
    both as 'ratio > 1 means stricter' would flip the sign of the most interesting row in the
    report -- the desk's 25% single-name cap against BRAIN's 8% -- and turn a finding that this
    desk is three times more concentrated into a claim that it is three times safer.

    Three ways to have no ratio, kept DISTINCT because collapsing them loses the finding: the desk
    has no such check at all (ABSENT), the desk has one but the value handed in is unreadable
    (UNMEASURED), or the external number is too small to divide by. Only the first is a statement
    about the desk's process; reporting the other two the same way would invent a missing gate.
    """
    if not desk_present:
        return "NO DESK COUNTERPART -- recorded as ABSENT, not as satisfied"
    if ratio is None:
        return "UNMEASURED -- the desk value handed in is not a finite number, so no ratio"
    if 1.0 / _COMPARABLE_RATIO <= ratio <= _COMPARABLE_RATIO:
        return "COMPARABLE"
    tighter = ratio > 1.0 if higher_is_stricter else ratio < 1.0
    factor = ratio if ratio > 1.0 else 1.0 / ratio
    return f"DESK {'STRICTER' if tighter else 'LOOSER'} by {factor:.1f}x"


def _row(quantity: str, desk_value: float | None, desk_source: str, brain_key: str,
         brain_value: float, *, higher_is_stricter: bool, note: str) -> dict[str, Any]:
    ratio = None if desk_value is None else _jsonable(_ratio(desk_value, brain_value))
    confidence, quote = SOURCE_NOTES.get(brain_key, ("STATED", ""))
    return {
        "quantity": quantity,
        # _jsonable, not float(): a non-finite desk value would otherwise emit a bare NaN, which
        # json.dumps writes happily and no JSON parser downstream accepts.
        "desk_value": None if desk_value is None else _jsonable(float(desk_value)),
        "desk_source": desk_source,
        "brain_constant": brain_key,
        "brain_value": float(brain_value),
        "brain_confidence": confidence,
        "brain_quote": quote,
        "ratio_desk_over_brain": ratio,
        "higher_is_stricter": higher_is_stricter,
        "direction": _direction(ratio, higher_is_stricter=higher_is_stricter,
                                desk_present=desk_value is not None),
        "note": note,
    }


def gap_report(desk_floor_sharpe: float = DESK_SENSITIVITY_FLOOR_SHARPE,
               desk_band: tuple[float, float] = DESK_REAL_EDGE_BAND) -> dict[str, Any]:
    """Every desk threshold beside its BRAIN counterpart and the ratio, JSON-serialisable.

    Rows whose desk counterpart DOES NOT EXIST are emitted with a null ratio and the direction
    "NO DESK COUNTERPART", never omitted. An absent check that vanishes from a comparison table
    reads as a passed one, which is the same defect the `asset_drift` filter exists to avoid: a
    gate that appears to guard and guards nothing is worse than no gate, because it is counted.
    """
    cmp_ = compare(desk_floor_sharpe, desk_band)
    lo, hi = float(desk_band[0]), float(desk_band[1])
    slot_rate = DESK_FORWARD_SLOTS / DESK_CAMPAIGN_N

    rows = [
        _row("gate sensitivity floor vs submission target (Sharpe)",
             float(desk_floor_sharpe), "gate_power_audit.md §1 -- 85.42% power at true SR 5.0",
             "BRAIN_SHARPE_TARGET", BRAIN.sharpe_target, higher_is_stricter=True,
             note="THE HEADLINE. The desk's own audit records this gap as unfinished business."),
        _row("gate sensitivity floor vs submission bar (Sharpe)",
             float(desk_floor_sharpe), "gate_power_audit.md §1",
             "BRAIN_SHARPE_BAR", BRAIN.sharpe_bar, higher_is_stricter=True,
             note="Same floor against the hard bar rather than the target."),
        _row("real-edge band, upper (OOS Sharpe)", hi,
             "robustness_filters.REAL_EDGE_OOS_SHARPE_BAND (131,441-backtest sweep)",
             "BRAIN_SHARPE_BAR", BRAIN.sharpe_bar, higher_is_stricter=True,
             note="Neither side is a gate here: an observed band against a live bar. That two "
                  "unrelated sources land within 1.5x is what makes the headline row credible."),
        _row("real-edge band, lower (OOS Sharpe)", lo,
             "robustness_filters.REAL_EDGE_OOS_SHARPE_BAND (131,441-backtest sweep)",
             "BRAIN_RECENT_SHARPE_FLOOR", BRAIN.recent_sharpe_floor, higher_is_stricter=True,
             note="EXACT AGREEMENT. A 131k-backtest sweep and a live institutional pipeline put "
                  "the bottom of actionable edge at the same 0.5 Sharpe from unrelated data."),
        _row("max single-name weight", DESK_MAX_SINGLE_NAME_WEIGHT,
             "libs/portfolio/models.py :: PortfolioConstraints.max_weight",
             "BRAIN_TRUNCATION_DEFAULT", BRAIN.truncation_default, higher_is_stricter=False,
             note="THE ROW THAT RUNS THE OTHER WAY. On concentration this desk is the loose one, "
                  "which is worth more than the rows confirming what the audit already said."),
        _row("correlation control", DESK_CORRELATION_CLUSTER_THRESHOLD,
             "libs/portfolio/diversification.py :: cluster_threshold",
             "BRAIN_SELF_CORRELATION_CAP", BRAIN.self_correlation_cap, higher_is_stricter=False,
             note="LOOSE ANALOGUE, not a like-for-like: a clustering linkage threshold over the "
                  "existing book versus a per-candidate admission cap against a live pool. The "
                  "numbers are the same shape; the measurements are not."),
        _row("stage advancement rate", slot_rate,
             f"MAX_FORWARD_SLOTS={DESK_FORWARD_SLOTS} over an N={DESK_CAMPAIGN_N} campaign",
             "BRAIN_STAGE2_ACCEPTANCE_FRACTION", BRAIN.stage2_acceptance_fraction,
             higher_is_stricter=False,
             note="Capacity ceiling only. The measured gate promoted 0.00 of 20 genuine alphas at "
                  "true SR 2.0-3.0 (audit §6), so the realised rate is lower than this row."),
        _row("out-of-sample share of the candidate score", None,
             "ABSENT -- the gauntlet emits PASS/FAIL, so nothing is weighted",
             "BRAIN_OOS_SCORE_WEIGHT", BRAIN.oos_score_weight, higher_is_stricter=True,
             note="No counterpart exists because this desk SCREENS where BRAIN RANKS. Audit §6 "
                  "names the top-K ranked screen as the largest remaining lever (R0262); this is "
                  "the same finding arriving from outside."),
        _row("near-miss triage", None,
             "ABSENT -- a near-miss is FAILED and dies silently",
             "BRAIN_NEAR_SUBMITTABLE_FRACTION", BRAIN.near_submittable_fraction,
             higher_is_stricter=True,
             note="BRAIN keeps candidates at ~80% of the bar and IMPROVES them. On a desk whose "
                  "own measurement blames 53% of refutations on measurement failure rather than "
                  "absent alpha, discarding near-misses discards mostly fixable ones."),
    ]

    return {
        "module": "libs/validation/brain_calibration.py",
        "status": "CALIBRATION REFERENCE -- wired into no decision path, by design",
        "source": SOURCE,
        "caveat": annualisation_caveat(),
        "headline": cmp_.verdict,
        "comparison": {
            # _jsonable throughout: an UNKNOWN comparison must still produce a report a parser can
            # read, with nulls where the numbers are, rather than a NaN that dies downstream.
            "desk_floor_sharpe": _jsonable(cmp_.desk_floor_sharpe),
            "desk_band": [lo, hi],
            "brain_sharpe_bar": float(cmp_.brain_sharpe_bar),
            "brain_sharpe_target": float(cmp_.brain_sharpe_target),
            "ratio_floor_to_bar": _jsonable(cmp_.ratio_floor_to_bar),
            "ratio_floor_to_target": _jsonable(cmp_.ratio_floor_to_target),
            "ratio_floor_to_band_top": _jsonable(cmp_.ratio_floor_to_band_top),
            "stricter": cmp_.stricter,
        },
        "brain": BRAIN.to_dict(),
        "rows": rows,
    }
