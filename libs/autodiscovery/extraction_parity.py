"""Reconcile the DATA-UTILIZATION LAW with the GATE-OPTIMALITY MONITOR.

Two of the desk's own laws conflict if left implicit:
  - DATA-UTILIZATION LAW: idle ingested data is DATA PARALYSIS; convert every axis.
  - GATE-OPTIMALITY MONITOR: the DSR bar goes unclearable when the trial count explodes.

Satisfying the first by mass combinatorial/genetic generation ("scale extraction") triggers the
second -- the 420->0 dynamic at 20-axis scale: obey one law, break the other. This module encodes
the binding reconciliation as pure, testable primitives so the two laws cannot fight:

  1. COVERAGE, NOT VOLUME. Paralysis clears when every idle axis carries >=1 screened,
     economically-motivated hypothesis -- ~one good mechanism-first trial per axis (~20 trials),
     never thousands. ``axis_coverage``.
  2. EXPANSION IS EARNED. Combinatorial/genetic expansion of an axis is licensed only AFTER its
     single-axis screen shows signal (|IC|/Sharpe past threshold). Never explode an axis that has
     shown nothing -- pure DSR deflation, zero upside. ``expansion_licensed``.
  3. EFFECTIVE (independence-clustered) TRIAL COUNT. Cross-mechanism DSR deflates by INDEPENDENT
     trials, clustered by mechanism, not the raw tally. 20 axes converted mechanism-first ~= 20
     independent trials, so the bar stays clearable. ``effective_trial_count``.
  4. The paralysis flag is a COVERAGE flag. If "fix paralysis" ever becomes "generate more", the
     desk has built a survivor-killing volume machine that obeys one law by breaking the other.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict


class CoverageReport(BaseModel):
    """The parity metric: is every ingested axis converted (screened once), regardless of volume."""

    model_config = ConfigDict(frozen=True)

    n_axes: int  # distinct ingested data axes (the acquisition surface)
    n_covered: int  # axes that carry >=1 screened, economically-motivated hypothesis
    idle: tuple[str, ...]  # ingested axes with 0 screened hypotheses -- the true paralysis set
    coverage_frac: float  # n_covered / n_axes
    cleared: bool  # paralysis cleared == every axis covered (COVERAGE, never hypothesis count)
    verdict: str

    def __bool__(self) -> bool:
        return self.cleared


def axis_coverage(*, axes: Sequence[str], screened_axes: Sequence[str]) -> CoverageReport:
    """Data-paralysis is a COVERAGE gap, never a volume gap (reconciliation rules 1 & 4).

    Paralysis clears when every ingested ``axis`` carries at least one screened, economically-
    motivated hypothesis -- ``screened_axes`` is the axis each recorded mechanism-first hypothesis
    screens. ~One good trial per axis, not thousands. Measuring "idle" by coverage rather than by
    hypothesis count is exactly what stops "fix paralysis" from degenerating into a volume machine:
    the 21st hypothesis on an already-covered axis moves this metric not at all, so there is no
    incentive to pile trials onto one axis and every incentive to reach the next uncovered one.
    """
    universe = list(dict.fromkeys(a for a in axes if a))  # de-dup, preserve order
    covered_set = {a for a in screened_axes if a} & set(universe)
    idle = tuple(a for a in universe if a not in covered_set)
    n = len(universe)
    frac = round(len(covered_set) / n, 3) if n else 1.0
    cleared = not idle
    if n == 0:
        verdict = "no axes ingested -- nothing to convert"
    elif cleared:
        verdict = f"coverage complete: all {n} ingested axes carry >=1 screened hypothesis"
    else:
        shown = ", ".join(idle[:8]) + (" ..." if len(idle) > 8 else "")
        verdict = (
            f"{len(idle)}/{n} axes idle (0 screened hypotheses): {shown} -- convert "
            "MECHANISM-FIRST (one screened hypothesis each), NOT by combinatorial volume"
        )
    return CoverageReport(
        n_axes=n, n_covered=len(covered_set), idle=idle, coverage_frac=frac,
        cleared=cleared, verdict=verdict,
    )


class ExpansionDecision(BaseModel):
    """Whether combinatorial/genetic expansion of an axis is EARNED yet."""

    model_config = ConfigDict(frozen=True)

    axis: str
    licensed: bool
    reason: str

    def __bool__(self) -> bool:
        return self.licensed


def expansion_licensed(
    *, axis: str, screened: bool, screen_metric: float | None, threshold: float
) -> ExpansionDecision:
    """Combinatorial/genetic expansion of ``axis`` is EARNED, never default (reconciliation rule 2).

    Licensed only once the axis's own single-axis screen has RUN (``screened``) and shown signal
    (``|screen_metric| >= threshold`` -- e.g. |IC| or forward Sharpe). Exploding an unscreened axis,
    or one that screened flat, is pure cumulative-trial DSR deflation with zero upside -- the exact
    420->0 dynamic. Screen first; expand only what proved it deserves the trials.
    """
    if not screened or screen_metric is None:
        return ExpansionDecision(
            axis=axis, licensed=False,
            reason="unscreened -- run the single-axis screen before spending any expansion trials",
        )
    strength = abs(screen_metric)
    if strength < threshold:
        return ExpansionDecision(
            axis=axis, licensed=False,
            reason=(
                f"screen flat (|metric| {strength:.4f} < {threshold:.4f}) -- expanding a dead axis "
                "is pure DSR deflation with zero upside; retire or re-construct, do NOT explode"
            ),
        )
    return ExpansionDecision(
        axis=axis, licensed=True,
        reason=(f"screen shows signal (|metric| {strength:.4f} >= {threshold:.4f}) -- "
                "expansion earned"),
    )


class EffectiveTrials(BaseModel):
    """Independence-clustered trial count -- what CROSS-mechanism DSR should deflate by."""

    model_config = ConfigDict(frozen=True)

    raw: int  # raw cumulative trial tally -- over-counts correlated variations of one mechanism
    effective: int  # number of independent mechanism clusters -- the honest cross-mechanism count
    n_clusters: int  # == effective; distinct mechanisms seen
    inflation: float  # raw / effective -- how much the raw tally over-charges the DSR bar
    top_clusters: tuple[tuple[str, int], ...]  # (mechanism, raw_trials) heaviest-first, for audit
    verdict: str


def effective_trial_count(mechanisms: Sequence[str]) -> EffectiveTrials:
    """Independence-clustered trial count for CROSS-mechanism DSR deflation (reconciliation rule 3;
    gate-calibration audit (a) from MAX_SURVIVORS Part 1.2).

    DSR must deflate by the number of INDEPENDENT trials, not the raw tally. Cluster the trial
    ledger by mechanism (the ``family``/``method`` key already on every trials-ledger row): N
    variations of one economically-distinct mechanism are ~1 independent trial, not N. So the
    effective cross-mechanism count is the number of distinct mechanism clusters -- 20 axes
    converted mechanism-first ~= 20 independent trials, keeping the bar clearable.

    This is the COMPLEMENT of the pre-registered per-family budget
    (``orchestrator._family_trials``), which prices *within*-mechanism search: counting the raw
    within-family tally AND this global term would double-charge. This term exists so the gate-
    optimality monitor can report effective-vs-raw honestly instead of only telling a human to
    "audit" it.
    """
    raw = len(mechanisms)
    clusters = Counter(m for m in mechanisms if m)
    eff = len(clusters)
    inflation = round(raw / eff, 2) if eff else 0.0
    top = tuple(clusters.most_common(5))
    if eff == 0:
        verdict = "no mechanisms recorded -- effective trial count is 0"
    elif inflation <= 1.5:
        verdict = f"raw {raw} ~= effective {eff} ({eff} mechanisms) -- bar is honestly calibrated"
    else:
        verdict = (
            f"raw {raw} inflates to {inflation:.1f}x the effective {eff} independent mechanisms -- "
            "deflating DSR by raw sets the bar unclearable; use the effective count"
        )
    return EffectiveTrials(
        raw=raw, effective=eff, n_clusters=eff, inflation=inflation,
        top_clusters=top, verdict=verdict,
    )
