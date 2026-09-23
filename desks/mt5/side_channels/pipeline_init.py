"""MT5 Research Pipeline — unified interface for the 5-stage pipeline.

Stages:
  1. discover  — generate hypotheses from economic mechanisms
  2. validate  — statistical gauntlet (10 gates)
  3. shadow    — forward evidence on venue-native bars
  4. promote   — auto-promotion with forward cure
  5. allocate  — portfolio optimization and capital allocation
"""
from __future__ import annotations

from .discover import discover_from_mechanism, run_discovery, Hypothesis, load_hypothesis, save_hypothesis
from .validate import validate_hypothesis, run_validation, ValidationResult
from .shadow import run_shadow, ShadowVerdict
from .promote import promote_hypothesis, run_promotion, PromotionDecision
from .allocate import run_allocation, compute_allocation, AllocationResult

__all__ = [
    "discover_from_mechanism",
    "run_discovery",
    "Hypothesis",
    "load_hypothesis",
    "save_hypothesis",
    "validate_hypothesis",
    "run_validation",
    "ValidationResult",
    "run_shadow",
    "ShadowVerdict",
    "promote_hypothesis",
    "run_promotion",
    "PromotionDecision",
    "run_allocation",
    "compute_allocation",
    "AllocationResult",
]