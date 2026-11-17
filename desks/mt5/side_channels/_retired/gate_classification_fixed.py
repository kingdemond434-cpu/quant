"""Gate classification: VALIDITY vs POWER vs INDEPENDENT.

Loaded from desks/mt5/policy/gate_spec.yaml — single source of truth.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml

BASE = Path(__file__).resolve().parent.parent
SPEC_PATH = BASE / "policy" / "gate_spec.yaml"


def _load_spec() -> dict:
    with open(SPEC_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


_SPEC = _load_spec()

GateType = Literal["validity", "power", "independent"]

GATE_CLASSIFICATION: dict[str, GateType] = {
    g["name"]: g["classification"]  # type: ignore[assignment]
    for g in _SPEC["gates"]
}

VALIDITY_GATES = frozenset(
    g["name"] for g in _SPEC["gates"] if g["classification"] == "validity"
)
POWER_GATES = frozenset(
    g["name"] for g in _SPEC["gates"] if g["classification"] == "power"
)


def classify_gates(stages: dict) -> dict:
    """Classify gate results into validity/power with pass/fail."""
    result = {
        "validity": {"passed": [], "failed": []},
        "power": {"passed": [], "failed": []},
    }
    for gate_name, gate_result in stages.items():
        if not isinstance(gate_result, dict):
            continue
        classification = GATE_CLASSIFICATION.get(gate_name)
        if classification is None:
            continue
        passed = gate_result.get("passed") is True
        target = result[classification]
        if passed:
            target["passed"].append(gate_name)
        else:
            target["failed"].append(gate_name)
    return result


def validity_all_pass(stages: dict) -> bool:
    """All validity gates must pass - hard fail otherwise."""
    for gate in VALIDITY_GATES:
        gate_result = stages.get(gate)
        if not isinstance(gate_result, dict) or gate_result.get("passed") is not True:
            return False
    return True


def power_deficiencies(stages: dict) -> list[str]:
    """Return list of power gates that failed."""
    failed = []
    for gate in POWER_GATES:
        gate_result = stages.get(gate)
        if not isinstance(gate_result, dict) or gate_result.get("passed") is not True:
            failed.append(gate)
    return failed


def historical_certificate_status(cert: dict) -> dict:
    """Extract validity/power status from a historical certificate."""
    stages = cert.get("gates", {})
    return {
        "validity_pass": validity_all_pass(stages),
        "power_deficiencies": power_deficiencies(stages),
        "validity_passed": [g for g in VALIDITY_GATES if stages.get(g, {}).get("passed")],
        "validity_failed": [g for g in VALIDITY_GATES if not stages.get(g, {}).get("passed")],
        "power_passed": [g for g in POWER_GATES if stages.get(g, {}).get("passed")],
        "power_failed": power_deficiencies(stages),
    }


def get_promotion_config() -> dict:
    """Return promotion protocol config from spec."""
    return _SPEC.get("promotion", {})