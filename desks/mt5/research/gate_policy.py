"""Single immutable authority for MT5 shadow admission.

Discovery screens and batteries may rank or diagnose candidates, but only an
exact pass of this original ten-gate policy can admit a sleeve to shadow.
"""
from __future__ import annotations

import math
from typing import Any

VERSION = "mt5-original-universal-10-v2-calibrated-inputs"
DONE_MARKER = "DONE_qquant_gates_original10_v2"
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
REGIME_ADMISSION_UNIT = (
    "strategy x instrument x side x horizon/session x preregistered point-in-time regime"
)
REGIME_CONTROL = (
    "regime frozen before OOS; unconditional arm is a separately counted control; "
    "unknown or incompatible live regime is OFF"
)
TRIAL_COUNT_BASIS = (
    "ceil(null_calibrated_participation_ratio_effective_cells * 7); "
    "fail closed to ceil(raw_cells * 7) when dependence is unmeasurable"
)

ATTESTATION = {
    "version": VERSION,
    "gates": list(GATES),
    "trials_multiplier": TRIALS_MULTIPLIER,
    "trial_count_basis": TRIAL_COUNT_BASIS,
    "dsr_threshold": DSR_THRESHOLD,
    "pbo_max": PBO_THRESHOLD,
    "spa_alpha": SPA_ALPHA,
    "wf_splits": WF_SPLITS,
    "wf_test_size": "max(20,len//6)",
    "wf_min_oos_sharpe": 0.0,
    "wf_min_stability": WF_MIN_STABILITY,
    "cost_multiplier": COST_SCENARIO,
    "regime_admission_unit": REGIME_ADMISSION_UNIT,
    "regime_control": REGIME_CONTROL,
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


def charged_trial_count(raw_cells: int, effective_cells: Any,
                        method: Any) -> tuple[int, str]:
    """Charge measured independent cells plus the unchanged 7x campaign history.

    Dependence relief is available only from the fixed participation-ratio instrument and only
    when its result is finite and bounded by the cells actually run. Every missing or malformed
    measurement fails closed to the raw-cell burden.
    """
    raw = max(2, math.ceil(max(0, raw_cells) * TRIALS_MULTIPLIER))
    if (method == "null_calibrated_participation_ratio"
            and isinstance(effective_cells, (int, float))
            and not isinstance(effective_cells, bool)
            and math.isfinite(float(effective_cells))
            and 2.0 <= float(effective_cells) <= raw_cells):
        return (
            max(2, math.ceil(float(effective_cells) * TRIALS_MULTIPLIER)),
            "measured_effective_cells_x_campaign_multiplier",
        )
    return raw, "raw_cells_x_campaign_multiplier_fail_closed"
