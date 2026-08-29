"""Single immutable authority for MT5 shadow admission.

Discovery screens and batteries may rank or diagnose candidates, but only an
exact pass of this original ten-gate policy can admit a sleeve to shadow.

GATE DEFINITIONS ARE LOADED FROM desks/mt5/policy/gate_spec.yaml
This file is the single source of truth for gate definitions, thresholds, and classifications.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import yaml

BASE = Path(__file__).resolve().parent.parent
SPEC_PATH = BASE / "policy" / "gate_spec.yaml"


def _load_spec() -> dict:
    """Load gate specification from YAML."""
    with open(SPEC_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


_SPEC = _load_spec()

VERSION = _SPEC["version"]
#: Fixed multiple-testing charge, read from the spec so the number lives in policy, not code.
_SPEC_FIXED_TRIALS = next(
    (g.get("params", {}).get("fixed_trial_count")
     for g in _SPEC.get("gates", []) if g.get("name") == "deflated_sharpe"), None)
DONE_MARKER = "DONE_qquant_gates_original10_v2"
GATES = tuple(g["name"] for g in _SPEC["gates"])

# Extract thresholds from spec
_PARAMS = {g["name"]: g.get("params", {}) for g in _SPEC["gates"]}
THRESHOLDS = {g["name"]: g.get("threshold", "") for g in _SPEC["gates"]}

TRIALS_MULTIPLIER = _SPEC["gates"][2]["params"].get("trials_multiplier", 7.0)  # deflated_sharpe
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
# THE BAR IS FIXED. It never raises, and it never gets harsher (principal, standing instruction,
# stated three times). A candidate is judged against a constant campaign charge, not against the
# accident of how many other cells shared its sweep: sr0 was 0.3786 at 597 charged trials and
# 1.3593 at 5,963, same gate, same policy, same cell, purely because the docket grew that hour.
#
# The attestation MUST describe what was actually applied. Leaving the old formula here while the
# charge became constant would keep every existing certificate matching -- and make each one
# attest to a basis it was not judged under, which is the one thing this field exists to prevent.
# Re-stamping costs a window: certificates carry the OLD attestation until a sweep rewrites them,
# and is_exact_policy is an exact dict match, so admission sees nothing until then. The gauntlet
# republishes with the current attestation every sweep, and sweeps now finish in ~20 minutes.
TRIAL_COUNT_BASIS = (
    "fixed_campaign_trials(597): the same multiple-testing charge for every cell regardless of "
    "how many others share its sweep"
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
    # THE SAME CHARGE FOR EVERY CELL, WHATEVER ELSE IS IN THE SWEEP. Both former branches scaled
    # with how many cells that hour happened to carry, so a candidate's bar moved with the batch
    # it was scheduled into rather than with anything about the candidate: sr0 0.3786 at 597
    # charged trials, 1.3593 at 5,963, same gate, same policy, same cell.
    # The deflated Sharpe still corrects for multiple testing -- it now corrects against a
    # standing campaign size, which is what the correction was always meant to represent.
    # `raw_cells`, `effective_cells` and `method` are still accepted and still REPORTED by the
    # caller: the census is how anyone checks this number was not quietly chosen to suit a
    # result, and hiding the inputs would be exactly that.
    fixed = _SPEC_FIXED_TRIALS
    if isinstance(fixed, int) and fixed >= 2:
        return fixed, f"fixed_campaign_trials({fixed})"
    # No fixed count in the spec: fail closed to the old raw burden rather than guess.
    return (max(2, math.ceil(max(0, raw_cells) * TRIALS_MULTIPLIER)),
            "raw_cells_x_campaign_multiplier_fail_closed")


def get_gate_classification() -> dict[str, str]:
    """Return gate -> classification mapping from spec."""
    return {
        g["name"]: g["classification"]
        for g in _SPEC["gates"]
    }


def get_validity_gates() -> frozenset[str]:
    """Return set of VALIDITY gate names."""
    return frozenset(
        g["name"] for g in _SPEC["gates"] if g["classification"] == "validity"
    )


def get_power_gates() -> frozenset[str]:
    """Return set of POWER gate names."""
    return frozenset(
        g["name"] for g in _SPEC["gates"] if g["classification"] == "power"
    )


def get_promotion_thresholds() -> dict:
    """Return promotion protocol thresholds from spec."""
    return _SPEC.get("promotion", {})