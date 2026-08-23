"""Single immutable authority for MT5 shadow admission.

Discovery screens and batteries may rank or diagnose candidates, but only an
exact pass of this original ten-gate policy can admit a sleeve to shadow.
"""
from __future__ import annotations

from typing import Any

VERSION = "mt5-original-universal-10-v1"
GATES = (
    "economic_prior", "in_sample_screen", "deflated_sharpe", "pbo",
    "reality_check_spa", "cpcv", "walk_forward", "stress_costs",
    "lockbox", "expected_value",
)
TRIALS_MULTIPLIER = 7.0
DSR_THRESHOLD = 0.95
PBO_THRESHOLD = 0.5
SPA_ALPHA = 0.05
WF_SPLITS = 4
WF_MIN_STABILITY = 0.5
COST_SCENARIO = 3.0

ATTESTATION = {
    "version": VERSION,
    "gates": list(GATES),
    "trials_multiplier": TRIALS_MULTIPLIER,
    "dsr_threshold": DSR_THRESHOLD,
    "pbo_max": PBO_THRESHOLD,
    "spa_alpha": SPA_ALPHA,
    "wf_splits": WF_SPLITS,
    "wf_test_size": "max(20,len//6)",
    "wf_min_oos_sharpe": 0.0,
    "wf_min_stability": WF_MIN_STABILITY,
    "cost_multiplier": COST_SCENARIO,
    "cpcv_mean_oos_sharpe_min_exclusive": 0.0,
    "lockbox_oos_sharpe_min": 0.0,
    "expected_value_min_exclusive": 0.0,
}


def is_exact_policy(value: Any) -> bool:
    """Require the complete attestation; missing/extra/changed bars fail closed."""
    return isinstance(value, dict) and value == ATTESTATION


def all_ten_pass(stages: Any) -> bool:
    """A partial or extra gate set is not the canonical ten-gate verdict."""
    return (
        isinstance(stages, dict)
        and tuple(stages) == GATES
        and all(isinstance(stages[name], dict) and stages[name].get("passed") is True
                for name in GATES)
    )
