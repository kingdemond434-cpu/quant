"""Walk-forward governance and automated revalidation (fail-closed).

Re-proves a strategy on rolling out-of-sample windows and gates production capital on the result:
no strategy may hold production capital unless ``walk_forward_status == PASSED``. A set of triggers
(structural break, drift, regime transition, performance/capacity deterioration, signal decay,
staleness) forces revalidation; a hard trigger downgrades an otherwise-passing strategy to STALE
until it re-passes. Reuses the existing walk-forward splits, Sharpe, and Stage 13 decay levels.
"""

from __future__ import annotations

from enum import StrEnum

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from libs.self_improvement.models import DecayLevel
from libs.validation.dsr import sharpe_ratio
from libs.validation.errors import ValidationError
from libs.validation.walk_forward import walk_forward_splits


class WalkForwardStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    STALE = "stale"      # was passing but a hard trigger requires re-proof
    PENDING = "pending"  # never evaluated


class RevalidationTrigger(StrEnum):
    STRUCTURAL_BREAK = "structural_break"
    DRIFT = "drift"
    REGIME_TRANSITION = "regime_transition"
    SHARPE_DETERIORATION = "sharpe_deterioration"
    PF_DETERIORATION = "pf_deterioration"
    CAPACITY_DETERIORATION = "capacity_deterioration"
    SIGNAL_DECAYING = "signal_decaying"
    SIGNAL_DEAD = "signal_dead"
    STALE = "stale"
    MANUAL = "manual"


# Triggers that, on their own, must block production until the strategy re-passes.
_HARD_TRIGGERS = frozenset(
    {
        RevalidationTrigger.STRUCTURAL_BREAK,
        RevalidationTrigger.DRIFT,
        RevalidationTrigger.SIGNAL_DEAD,
    }
)


class WalkForwardReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: WalkForwardStatus
    walk_forward_score: float  # 0-100
    n_windows: int
    oos_sharpe: float
    oos_mean_return: float
    stability: float  # fraction of OOS windows with positive mean return
    message: str
    #: IN-SAMPLE counterparts, added 2026-08-01 so the IS-vs-OOS degradation can be TESTED rather
    #: than eyeballed. The engine was already splitting train/test and computing statistics on the
    #: test side only, throwing the train side away -- which meant the single most diagnostic
    #: comparison in backtesting ("how much worse did it get out of sample, and is that gap larger
    #: than sampling noise?") could not be made by any caller. libs/validation/robustness_filters
    #: .not_too_lucky needs exactly these four numbers. Defaults keep every existing construction
    #: valid; a report built without them reads is_sharpe 0.0, which not_too_lucky treats as
    #: "nothing to compare" and passes rather than inventing a verdict.
    is_sharpe: float = 0.0
    n_is: int = 0
    n_oos: int = 0


class RevalidationDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    required: bool
    triggers: list[RevalidationTrigger] = Field(default_factory=list)
    status: WalkForwardStatus
    production_capital_allowed: bool
    rationale: str


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class WalkForwardEngine:
    """Rolling out-of-sample evaluation producing a PASS/FAIL walk-forward verdict."""

    def evaluate(
        self,
        returns: np.ndarray,
        *,
        n_splits: int = 4,
        test_size: int,
        min_oos_sharpe: float = 0.0,
        min_stability: float = 0.5,
        anchored: bool = True,
        embargo: int = 0,
    ) -> WalkForwardReport:
        arr = np.asarray(returns, dtype="float64")
        if arr.ndim != 1:
            raise ValidationError("returns must be a 1-D array")
        splits = walk_forward_splits(
            len(arr), n_splits=n_splits, test_size=test_size, anchored=anchored, embargo=embargo
        )
        oos_sharpes: list[float] = []
        oos_means: list[float] = []
        is_sharpes: list[float] = []
        n_is_total = 0
        n_oos_total = 0
        for split in splits:
            test = arr[split.test]
            oos_sharpes.append(sharpe_ratio(test) if len(test) > 1 else 0.0)
            oos_means.append(float(test.mean()) if len(test) else 0.0)
            # The TRAIN side, which this loop previously discarded. Averaging per-window IS
            # Sharpes rather than computing one Sharpe over the pooled training data is
            # deliberate: it matches how oos_sharpe is built two lines up, and the luck filter
            # compares the two, so any asymmetry in how they are aggregated would show up as a
            # degradation that is an artefact of the arithmetic rather than of the strategy.
            train = arr[split.train]
            if len(train) > 1:
                is_sharpes.append(sharpe_ratio(train))
                n_is_total += len(train)
            n_oos_total += len(test)

        oos_sharpe = float(np.mean(oos_sharpes)) if oos_sharpes else 0.0
        is_sharpe = float(np.mean(is_sharpes)) if is_sharpes else 0.0
        oos_mean = float(np.mean(oos_means)) if oos_means else 0.0
        stability = float(np.mean([m > 0 for m in oos_means])) if oos_means else 0.0
        passed = oos_sharpe >= min_oos_sharpe and stability >= min_stability
        # Score blends OOS Sharpe (capped) and stability into 0-100.
        score = 100.0 * (0.6 * _clip01(oos_sharpe / 2.0) + 0.4 * stability)
        return WalkForwardReport(
            status=WalkForwardStatus.PASSED if passed else WalkForwardStatus.FAILED,
            walk_forward_score=score,
            n_windows=len(splits),
            oos_sharpe=oos_sharpe,
            oos_mean_return=oos_mean,
            stability=stability,
            is_sharpe=is_sharpe,
            # Anchored splits reuse the same early data in every training window, so n_is_total
            # counts observations-used, not distinct observations. That is the right input for
            # not_too_lucky's standard error, which is about how precisely the IS Sharpe was
            # estimated -- but it is NOT a count of independent data and must not be read as one.
            n_is=n_is_total,
            n_oos=n_oos_total,
            message=(
                f"oos_sharpe={oos_sharpe:.2f} (>= {min_oos_sharpe}), "
                f"stability={stability:.2f} (>= {min_stability})"
            ),
        )


class RevalidationController:
    """Decides when revalidation is required and whether production capital is allowed."""

    def assess(
        self,
        report: WalkForwardReport,
        *,
        structural_break: bool = False,
        drift: bool = False,
        regime_transition: bool = False,
        sharpe_deteriorated: bool = False,
        pf_deteriorated: bool = False,
        capacity_deteriorated: bool = False,
        decay_level: DecayLevel | None = None,
        age_days: float | None = None,
        max_age_days: float = 30.0,
        manual: bool = False,
    ) -> RevalidationDecision:
        triggers: list[RevalidationTrigger] = []
        if structural_break:
            triggers.append(RevalidationTrigger.STRUCTURAL_BREAK)
        if drift:
            triggers.append(RevalidationTrigger.DRIFT)
        if regime_transition:
            triggers.append(RevalidationTrigger.REGIME_TRANSITION)
        if sharpe_deteriorated:
            triggers.append(RevalidationTrigger.SHARPE_DETERIORATION)
        if pf_deteriorated:
            triggers.append(RevalidationTrigger.PF_DETERIORATION)
        if capacity_deteriorated:
            triggers.append(RevalidationTrigger.CAPACITY_DETERIORATION)
        if decay_level is DecayLevel.DEAD:
            triggers.append(RevalidationTrigger.SIGNAL_DEAD)
        elif decay_level is DecayLevel.DECAYING:
            triggers.append(RevalidationTrigger.SIGNAL_DECAYING)
        if age_days is not None and age_days > max_age_days:
            triggers.append(RevalidationTrigger.STALE)
        if manual:
            triggers.append(RevalidationTrigger.MANUAL)

        # Fail-closed: capital allowed only when the walk-forward verdict is PASSED and no hard
        # trigger has invalidated it. A hard trigger downgrades a passing strategy to STALE.
        status = report.status
        if status is WalkForwardStatus.PASSED and any(t in _HARD_TRIGGERS for t in triggers):
            status = WalkForwardStatus.STALE
        production_capital_allowed = status is WalkForwardStatus.PASSED
        return RevalidationDecision(
            required=bool(triggers),
            triggers=triggers,
            status=status,
            production_capital_allowed=production_capital_allowed,
            rationale=(
                "production capital permitted (walk-forward PASSED, no hard triggers)"
                if production_capital_allowed
                else f"production capital blocked (status={status.value}); "
                f"triggers={[t.value for t in triggers]}"
            ),
        )
