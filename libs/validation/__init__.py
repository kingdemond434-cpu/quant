"""``libs.validation`` — the trials-adjusted validation gauntlet (the Skeptic).

DSR / PBO / CPCV / walk-forward / White's Reality Check / Hansen's SPA / block bootstrap /
FDR control / locked holdout, plus the economic-prior gate and stress-cost validation, wired
into an ordered :class:`Gauntlet` that emits a PASS/FAIL verdict and JSON/HTML reports.
"""

from __future__ import annotations

from libs.validation.bootstrap import (
    block_bootstrap,
    confidence_interval,
    moving_block_indices,
    stationary_block_indices,
    stationary_bootstrap,
)
from libs.validation.cpcv import CPCV, CPCVSplit
from libs.validation.dsr import (
    DSRResult,
    deflated_sharpe_ratio,
    expected_max_sharpe,
    min_track_record_length,
    probabilistic_sharpe_ratio,
    sharpe_ratio,
)
from libs.validation.economic_prior import (
    EconomicPrior,
    MechanismType,
    PriorGateResult,
    economic_prior_gate,
)
from libs.validation.errors import ValidationError
from libs.validation.fdr import FDRResult, benjamini_hochberg, benjamini_yekutieli
from libs.validation.gauntlet import (
    CandidateEvaluation,
    Gauntlet,
    GauntletResult,
    StageResult,
)
from libs.validation.lockbox import LockedHoldout
from libs.validation.pbo import PBOResult, probability_backtest_overfitting
from libs.validation.reality_check import RealityCheckResult, hansen_spa, whites_reality_check
from libs.validation.report import generate_validation_report
from libs.validation.revalidation import (
    RevalidationController,
    RevalidationDecision,
    RevalidationTrigger,
    WalkForwardEngine,
    WalkForwardReport,
    WalkForwardStatus,
)
from libs.validation.stress_costs import (
    StressCostResult,
    StressScenarioResult,
    stress_cost_validation,
)
from libs.validation.walk_forward import WalkForwardSplit, walk_forward_splits

__all__ = [  # noqa: RUF022  # grouped by concern
    # deflated sharpe
    "sharpe_ratio",
    "probabilistic_sharpe_ratio",
    "expected_max_sharpe",
    "deflated_sharpe_ratio",
    "min_track_record_length",
    "DSRResult",
    # pbo
    "probability_backtest_overfitting",
    "PBOResult",
    # cpcv / walk-forward
    "CPCV",
    "CPCVSplit",
    "walk_forward_splits",
    "WalkForwardSplit",
    # walk-forward governance / revalidation
    "WalkForwardEngine",
    "WalkForwardReport",
    "WalkForwardStatus",
    "RevalidationController",
    "RevalidationDecision",
    "RevalidationTrigger",
    # reality check / spa
    "whites_reality_check",
    "hansen_spa",
    "RealityCheckResult",
    # bootstrap
    "block_bootstrap",
    "stationary_bootstrap",
    "moving_block_indices",
    "stationary_block_indices",
    "confidence_interval",
    # fdr
    "benjamini_hochberg",
    "benjamini_yekutieli",
    "FDRResult",
    # lockbox
    "LockedHoldout",
    # economic prior
    "economic_prior_gate",
    "EconomicPrior",
    "MechanismType",
    "PriorGateResult",
    # stress costs
    "stress_cost_validation",
    "StressCostResult",
    "StressScenarioResult",
    # gauntlet + report
    "Gauntlet",
    "CandidateEvaluation",
    "GauntletResult",
    "StageResult",
    "generate_validation_report",
    # errors
    "ValidationError",
]
