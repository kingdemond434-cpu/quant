"""Builders for the Stage 15 test suite."""

from __future__ import annotations

from typing import Any

from libs.stage15.models import AlphaScores
from libs.stage15.orchestrator import AlphaPipelineInput


def good_scores(**overrides: Any) -> AlphaScores:
    defaults: dict[str, Any] = {
        "expected_return": 0.12, "sharpe": 1.8, "sortino": 2.2, "calmar": 1.6,
        "capacity_score": 85.0, "fragility_score": 15.0, "stability_score": 85.0,
        "decay_score": 10.0, "survival_score": 90.0, "diversification_score": 80.0,
        "economic_score": 80.0,
    }
    defaults.update(overrides)
    return AlphaScores(**defaults)


def passing_candidate(alpha_id: str = "alpha_1", **overrides: Any) -> AlphaPipelineInput:
    defaults: dict[str, Any] = {
        "alpha_id": alpha_id,
        "scores": good_scores(),
        "cpcv_passed": True, "pbo_acceptable": True, "dsr_passed": True,
        "reality_check_passed": True, "economic_mechanism_present": True,
        "capacity_acceptable": True, "fragility_acceptable": True, "walk_forward_passed": True,
        "shadow_ready": True,
    }
    defaults.update(overrides)
    return AlphaPipelineInput(**defaults)
