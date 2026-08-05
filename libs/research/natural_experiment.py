"""CAUSAL IDENTIFICATION from a dated exogenous shock -- difference-in-differences with a matched
control cohort, and the refusal paths that make the difference between identification and a
correlation with better vocabulary (R0207).

WHAT THE DESK COULD NOT DO BEFORE THIS MODULE. Every hypothesis this desk has ever tested is
OBSERVATIONAL: an IC or a Sharpe on a correlational panel, defended by de-contamination and
multiplicity control. Both defences are real and neither is identification -- they establish that
a relationship is not an ARTIFACT, never that it is CAUSAL. `libs/validation/event_study.py` is
the closest existing organ and it is a one-sample cross-sectional mean test: its `Event` type
carries a single scalar return and has no field in which a treated/control contrast could even be
expressed. So the desk held hundreds of dated exogenous shocks with untreated peers available as
controls, and no shape to put them in.

WHY A CAUSAL ANSWER IS WORTH BUILDING FOR rather than another correlational screen: an edge whose
MECHANISM is identified survives regime change for a reason you can state, and L1.16 makes that
the condition for calling an edge durable at all. It is also the cheapest possible defence against
the desk's dominant failure mode -- 420 tested, 0 survivors, most of them dying on de-contamination
-- because a shock that is genuinely exogenous cannot be contaminated by the thing it is supposed
to be predicting.

=================================================================================================
THE ARCHITECTURE, AND WHAT THIS MODULE DELIBERATELY DOES NOT DO
=================================================================================================
This module supplies IDENTIFICATION only. The INFERENCE -- multiplicity-corrected bar, bootstrap
against fat tails, overlap discount, degenerate-input refusal -- is delegated verbatim to
`libs.validation.event_study.event_study` by handing it the per-unit DiD estimates as `Event`
returns. That is deliberate and it is the whole reason this file is short: a second copy of the
desk's inference machinery would drift from the audited one, and the first divergence would be
invisible. Upgrade before build (L2.9).

=================================================================================================
PRE-REGISTRATION. Every threshold below is a module-level CONSTANT, not an argument.
=================================================================================================
If they were tunable a caller would sweep them and report the passing configuration, and the
multiplicity charge would be a lie -- the same discipline `listing_events.py` holds its window and
direction to. Changing one is a code change with a diff, which is the point.

THE ESTIMATOR
    For each treated unit i with event at t_i:
        DiD_i = (mean(treated post) - mean(treated pre))
              - (mean(control post) - mean(control pre))
    where the control legs are the matched untreated peers measured over the SAME CALENDAR
    WINDOWS as unit i. Differencing twice is what removes both the unit's own level and whatever
    the whole market did across the event -- neither of which a one-sample event study can remove.

=================================================================================================
THE FOUR WAYS THIS PRODUCES A FAKE CAUSAL CLAIM, AND THE RAIL AGAINST EACH
=================================================================================================
1. SELECTION INTO TREATMENT -- THE ONE THAT WILL ACTUALLY BITE HERE. A venue does not delist at
   random: it delists what has ALREADY died. Run naively, a delisting DiD would report a large,
   beautifully significant "effect" that is entirely the selection rule, and it would look exactly
   like an edge. This is not a hypothetical -- it is the expected default outcome for the first
   cohort this desk has available, so the module REFUSES rather than reports when it detects it.
   The rail is the parallel-trends test below: selection on prior performance is visible in the
   PRE-period, because that is where the selection happened.

2. PARALLEL TRENDS ASSUMED INSTEAD OF TESTED. DiD identifies the effect only if treated and
   control would have moved together absent the shock. That is an assumption about a
   counterfactual and it is not verifiable -- but its observable implication IS: the treated-minus-
   control gap should be indistinguishable from zero BEFORE the event. `PARALLEL_TRENDS_MAX_T`
   refuses when it is not.

   AND THE INVERSION THAT MAKES THAT TEST DANGEROUS ON ITS OWN: failing to reject on a short
   pre-window is not evidence of parallel trends, it is absence of power, and a module that
   reported PASS there would be laundering ignorance into identification. So a pre-window shorter
   than `MIN_PRE_OBS` returns ASSUMPTION-UNTESTABLE, never OK (L1.28a: unmeasured is never fine).

3. SUTVA / CONTROL CONTAMINATION. If the shock reaches the controls -- a market-wide rule change,
   or a treated cohort large enough to move the whole cross-section -- then the control leg
   contains the treatment and DiD differences the effect away toward zero. `MAX_TREATED_SHARE`
   refuses when the treated cohort is too large a share of the universe to leave a clean control.

4. EVENT-DATE CLUSTERING. Treated units sharing an event date share one market draw, so N is not
   N. Handled by constructing each unit's Event over its own post-window and letting
   `event_study.overlap_fraction` apply its discount -- the same effective-vs-raw discipline the
   desk applies to trial counts.

WHAT THIS MODULE STILL CANNOT TELL YOU, stated so a caller does not over-read a PASS: it cannot
prove the shock was exogenous. That is a claim about the WORLD -- about the venue's decision rule
-- and it must be argued from the announcement, not from the returns. `exogeneity_note` is a
REQUIRED field on the request for exactly that reason: a study that cannot state why its shock is
exogenous has not identified anything, and the type system now says so.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict

from libs.validation.errors import ValidationError
from libs.validation.event_study import Event, EventStudyResult, event_study

#: Pre-period observations per unit below which the parallel-trends test has no power. Failing to
#: reject on 3 points is not evidence of parallel trends; it is a short window.
MIN_PRE_OBS = 10

#: Post-period observations per unit. Below this the "after" leg is a point, not a mean.
MIN_POST_OBS = 3

#: |t| on the cross-sectional pre-period treated-minus-control gap. Above this, the two groups
#: were ALREADY diverging before the shock, DiD does not identify anything, and the study is
#: refused. 2.0 is the conventional two-sided 5% level and is deliberately NOT lenient: a
#: generous threshold here buys a significant "effect" made entirely of selection.
PARALLEL_TRENDS_MAX_T = 2.0

#: |t| on a placebo DiD run at the midpoint of the PRE window, where the true effect is zero by
#: construction. A significant placebo means the design manufactures effects out of nothing.
PLACEBO_MAX_T = 2.0

#: Treated units as a share of (treated + control). Above this the "control" group is too small
#: or too entangled to be untreated, and SUTVA fails.
MAX_TREATED_SHARE = 0.25


class TreatedUnit(BaseModel):
    """One unit that received the shock, with its matched control leg over the SAME windows.

    `control_pre`/`control_post` are the cross-sectional mean return of the matched untreated
    peers on the same calendar days -- NOT a benchmark index and NOT the unit's own history. The
    caller owns the matching; this module owns what happens once it is done.
    """

    model_config = ConfigDict(frozen=True)

    unit_id: str
    event_ts: float                          # epoch seconds -- when the shock hit THIS unit
    treated_pre: list[float]
    treated_post: list[float]
    control_pre: list[float]
    control_post: list[float]
    #: The CROSS-SECTIONAL member this event belongs to -- the symbol, not the event. Empty means
    #: "this unit is its own member". It exists only for the SUTVA share test, and it is the
    #: difference between that test working and refusing every well-powered study: a symbol with
    #: 30 dated unlocks is ONE treated member of the cross-section, not 30, while `n_control_pool`
    #: counts SYMBOLS. Comparing an event count to a symbol count is apples to oranges, and it
    #: fails in the direction nobody notices -- 1,019 insider events against a 195-symbol control
    #: pool computes a treated share of 84% and refuses SUTVA-VIOLATED on a cohort whose real
    #: cross-sectional share is 20%. Found by running the module on the first real cohort rather
    #: than by reading it.
    cohort_key: str = ""

    @property
    def did(self) -> float:
        return (float(np.mean(self.treated_post)) - float(np.mean(self.treated_pre))) - (
            float(np.mean(self.control_post)) - float(np.mean(self.control_pre)))

    @property
    def pre_gap(self) -> float:
        """Treated-minus-control BEFORE the shock. Should be ~0 if the groups are comparable."""
        return float(np.mean(self.treated_pre)) - float(np.mean(self.control_pre))


class DiDResult(BaseModel):
    """Verdict over a treated cohort. `passed` requires identification AND inference."""

    model_config = ConfigDict(frozen=True)

    n_treated: int
    n_control_pool: int
    treated_share: float
    effect: float                            # mean DiD across treated units
    parallel_trends_t: float
    parallel_trends_ok: bool
    placebo_t: float
    placebo_ok: bool
    identified: bool                         # every identification rail cleared
    inference: EventStudyResult | None       # None when identification failed -- never computed
    passed: bool
    verdict: str
    exogeneity_note: str
    direction: str                           # the PRE-REGISTERED sign -- see the arg's docstring


def _cross_sectional_t(x: np.ndarray) -> float:
    """Cross-sectional t of a mean. Zero on degenerate input rather than an exploding ratio.

    Returning 0.0 for a constant series is the SAFE direction here and only here: this feeds the
    parallel-trends and placebo REFUSAL tests, where a large |t| refuses. A NaN or an exploding
    ratio would refuse a study for a data defect while reporting it as a trend violation, which
    sends the reader to fix the wrong thing. Degenerate INPUT to the effect itself is caught by
    event_study's own DEGENERATE guard, which is where it belongs.
    """
    n = len(x)
    if n < 2:
        return 0.0
    sd = float(np.std(x, ddof=1))
    if sd <= 1e-12 or not np.isfinite(sd):
        return 0.0
    return float(np.mean(x) / (sd / np.sqrt(n)))


def difference_in_differences(
    units: list[TreatedUnit],
    *,
    n_control_pool: int,
    exogeneity_note: str,
    direction: str,
    n_cohort: int = 1,
    rank: int = 1,
    post_window_s: float = 86_400.0,
) -> DiDResult:
    """Estimate the causal effect of a dated shock, or refuse and say which rail stopped it.

    `n_control_pool` is the size of the untreated universe the control legs were drawn from, used
    for the SUTVA share test. `exogeneity_note` must state WHY the shock is exogenous -- it is
    required, non-empty, and never inspected by the code, because that argument is about the
    world and cannot be made from the returns.

    `direction` is "increase" or "decrease": the sign the hypothesis PRE-REGISTERS, and it has no
    default on purpose. It exists because `event_study` is a ONE-SIDED POSITIVE test -- it was
    built for listing funding spikes, where the hypothesis is "the return is high" -- so handing
    it a genuinely negative effect returns t=-3.67 against a bar of +1.64 and reports NO-EFFECT
    forever. That is not a hypothetical: supply dilution is the desk's first real cohort and its
    predicted sign is DOWN, so the first natural experiment this module ever ran would have been
    structurally incapable of detecting the thing it was built to detect. Found by a planted
    positive control, which is the only way a silent one-sided failure ever surfaces.

    Signing the estimate by a PRE-REGISTERED direction tests the hypothesis actually being made,
    at the same alpha, one-sided -- it loosens nothing. Choosing the direction AFTER seeing the
    sign would be a free doubling of the multiplicity budget, which is why this is a required
    argument recorded on the result rather than an inferred convenience.

    `n_cohort`/`rank` plug into the desk's Holm discipline exactly as `event_study` documents.
    """
    if direction not in ("increase", "decrease"):
        raise ValidationError(
            f"direction must be pre-registered as 'increase' or 'decrease', got {direction!r}. "
            "event_study is one-sided positive; an unsigned DiD silently cannot detect a negative "
            "effect, and picking the sign after seeing the estimate doubles the multiplicity "
            "budget for free.")
    if not exogeneity_note.strip():
        raise ValidationError(
            "exogeneity_note is required: a study that cannot state why its shock is exogenous "
            "has identified nothing. Name the venue decision rule and why it does not depend on "
            "the outcome being measured.")

    n = len(units)
    pool = max(0, int(n_control_pool))
    # SUTVA is a question about the CROSS-SECTION, so it is measured on cross-sectional members
    # (symbols), never on events. See TreatedUnit.cohort_key for what this cost when it was wrong.
    #
    # AND IT IS A SIMULTANEITY QUESTION, NOT A LIFETIME ONE. The concern is that treatment reaches
    # the controls -- which can only happen while treatment is ON. Counting every member ever
    # treated against a same-day control pool refuses every STAGGERED design outright: 44 symbols
    # unlocking on 500 different dates would score a 49% treated share though only a handful are
    # ever in a window at once. So the statistic is PEAK SIMULTANEOUS treatment -- the most
    # distinct members whose treatment windows cover any single instant. For a cohort that shares
    # one event date this is identical to the old count, so nothing is loosened; for a staggered
    # cohort it asks the question SUTVA actually poses.
    n_members = len({u.cohort_key or u.unit_id for u in units})
    peak = 0
    for probe in {u.event_ts for u in units}:
        live = {u.cohort_key or u.unit_id for u in units
                if u.event_ts <= probe <= u.event_ts + post_window_s}
        peak = max(peak, len(live))
    share = round(peak / max(peak + pool, 1), 3)

    def _refuse(why: str, **kw: float | bool) -> DiDResult:
        base: dict[str, object] = {
            "n_treated": n, "n_control_pool": pool, "treated_share": share, "effect": 0.0,
            "parallel_trends_t": 0.0, "parallel_trends_ok": False, "placebo_t": 0.0,
            "placebo_ok": False, "identified": False, "inference": None, "passed": False,
            "verdict": why, "exogeneity_note": exogeneity_note, "direction": direction}
        base.update(kw)
        # NOT `DiDResult(**base)  # type: ignore[arg-type]`: that ignore is REQUIRED on some
        # in-pin mypy versions and reads as UNUSED on others, so the pinned box and the deploy
        # box disagree about whether this file is clean -- the pyarrow straddle one module over
        # (libs/data/lake.py), which pyproject had to paper over with a scoped override.
        # `model_validate` is typed to accept `Any` on every version, so no version can disagree
        # and no override is needed. Identical at runtime: pydantic routes both `__init__` and
        # `model_validate` to `__pydantic_validator__.validate_python(<the same dict>)`.
        return DiDResult.model_validate(base)

    if n == 0:
        return _refuse("No treated units supplied -- nothing to identify.")

    short = [u.unit_id for u in units
             if len(u.treated_pre) < MIN_PRE_OBS or len(u.control_pre) < MIN_PRE_OBS
             or len(u.treated_post) < MIN_POST_OBS or len(u.control_post) < MIN_POST_OBS]
    if short:
        return _refuse(
            f"ASSUMPTION-UNTESTABLE: {len(short)}/{n} unit(s) have a pre-window shorter than "
            f"{MIN_PRE_OBS} or a post-window shorter than {MIN_POST_OBS} obs "
            f"(e.g. {', '.join(short[:4])}). Failing to reject parallel trends on a short window "
            "is ABSENCE OF POWER, not evidence for the assumption -- reporting PASS here would "
            "launder ignorance into identification. Collect more pre-period, or drop the unit.")

    # SUTVA. Checked before anything is estimated: if the control group is not untreated, every
    # number below is a difference between two treated groups and means nothing.
    if share > MAX_TREATED_SHARE:
        return _refuse(
            f"SUTVA-VIOLATED: at peak {peak} of {n_members} treated member(s) are in a treatment "
            f"window at once (carrying {n} event(s)) against a {pool}-member control pool -- a "
            f"simultaneous treated share of {share:.0%}, above the {MAX_TREATED_SHARE:.0%} bar. A "
            "cohort this concentrated either moves the whole cross-section or shares its shock "
            "with the controls; either way the control leg contains the treatment and DiD "
            "differences the effect toward zero.")

    # RAIL 1 -- PARALLEL TRENDS. The identifying assumption's observable implication.
    pre_gaps = np.array([u.pre_gap for u in units], dtype="float64")
    pt_t = _cross_sectional_t(pre_gaps)
    pt_ok = bool(abs(pt_t) <= PARALLEL_TRENDS_MAX_T)

    # RAIL 2 -- PLACEBO. Split the pre-window and run the identical estimator on a fake event at
    # its midpoint, where the true effect is zero BY CONSTRUCTION. A significant placebo means
    # the design manufactures effects, and the real estimate is then uninterpretable.
    placebo = []
    for u in units:
        half_t, half_c = len(u.treated_pre) // 2, len(u.control_pre) // 2
        placebo.append(
            (float(np.mean(u.treated_pre[half_t:])) - float(np.mean(u.treated_pre[:half_t])))
            - (float(np.mean(u.control_pre[half_c:])) - float(np.mean(u.control_pre[:half_c]))))
    pb_t = _cross_sectional_t(np.array(placebo, dtype="float64"))
    pb_ok = bool(abs(pb_t) <= PLACEBO_MAX_T)

    effect = float(np.mean([u.did for u in units]))
    identified = pt_ok and pb_ok

    # INFERENCE IS NOT RUN WHEN IDENTIFICATION FAILED, and that is not a shortcut. A p-value on an
    # unidentified estimate is the single most misleading number this module could emit: it is
    # precise, it looks like evidence, and it is measuring the selection rule. Refusing to compute
    # it is what stops a reader quoting it.
    if not identified:
        why = ("PARALLEL-TRENDS-VIOLATED" if not pt_ok else "PLACEBO-FAILED")
        detail = (
            f"treated and control were ALREADY diverging before the shock (pre-period gap "
            f"t={pt_t:+.2f} vs bar {PARALLEL_TRENDS_MAX_T}). The most likely cause is SELECTION: "
            "the shock was applied to units chosen on their prior performance, so the 'effect' is "
            "the selection rule. DiD cannot separate the two here."
            if not pt_ok else
            f"a placebo event at the midpoint of the PRE window, where the true effect is zero by "
            f"construction, returned t={pb_t:+.2f} vs bar {PLACEBO_MAX_T}. The design produces "
            "effects out of nothing, so the real estimate is uninterpretable.")
        return _refuse(
            f"{why}: {detail} Raw DiD was {effect:+.4%} and is NOT reported as an effect.",
            effect=effect, parallel_trends_t=round(pt_t, 3), parallel_trends_ok=pt_ok,
            placebo_t=round(pb_t, 3), placebo_ok=pb_ok)

    # Each unit's post-window becomes its Event window, so units sharing an event date are
    # discounted by event_study's overlap machinery rather than counted as independent draws.
    # SIGNED BY THE PRE-REGISTERED DIRECTION, never by the observed sign. `effect` below stays in
    # natural units so a reader sees the real number; only the inference input is oriented.
    sign = 1.0 if direction == "increase" else -1.0
    events = [Event(event_id=u.unit_id, t_start=u.event_ts,
                    t_end=u.event_ts + post_window_s, ret=sign * u.did) for u in units]
    inf = event_study(events, n_cohort=n_cohort, rank=rank)

    passed = bool(inf.passed)
    verdict = (
        f"{'PASS' if passed else 'NO-EFFECT'}: identified (parallel trends t={pt_t:+.2f}, placebo "
        f"t={pb_t:+.2f}, treated share {share:.0%}), effect {effect:+.4%} over {n} treated "
        f"unit(s) on {n_members} cross-sectional member(s) against a {pool}-member control pool, "
        f"pre-registered direction {direction}. Inference: {inf.verdict}")
    return DiDResult(
        n_treated=n, n_control_pool=pool, treated_share=share, effect=round(effect, 6),
        parallel_trends_t=round(pt_t, 3), parallel_trends_ok=pt_ok, placebo_t=round(pb_t, 3),
        placebo_ok=pb_ok, identified=True, inference=inf, passed=passed, verdict=verdict,
        exogeneity_note=exogeneity_note, direction=direction)


#: Convenience for callers assembling a control leg: the cross-sectional mean of the untreated
#: peers on each day. Exposed rather than left to every caller because getting it wrong (using a
#: single benchmark, or the treated unit's own history) is the difference between DiD and a
#: one-sample event study wearing its name.
def control_mean(peer_returns: list[list[float]]) -> list[float]:
    """Per-day cross-sectional mean across peers. Raises on ragged input rather than truncating."""
    if not peer_returns:
        raise ValidationError("control leg is empty -- DiD needs untreated peers, not a benchmark")
    widths = {len(p) for p in peer_returns}
    if len(widths) != 1:
        raise ValidationError(
            f"ragged control leg: peer series have lengths {sorted(widths)}. Truncating would "
            "silently drop days from some peers and not others, biasing the control mean.")
    return [float(x) for x in np.asarray(peer_returns, dtype="float64").mean(axis=0)]
