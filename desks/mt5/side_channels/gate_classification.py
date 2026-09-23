from typing import Literal

GateType = Literal["validity", "power", "independent"]

GATE_CLASSIFICATION = {
    "economic_prior": "validity",
    "pbo": "validity",
    "reality_check_spa": "validity",
    "stress_costs": "validity",
    "lockbox": "validity",
    "in_sample_screen": "power",
    "deflated_sharpe": "power",
    "cpcv": "power",
    "walk_forward": "power",
    "expected_value": "power",
}

VALIDITY_GATES = frozenset(k for k, v in GATE_CLASSIFICATION.items() if v == "validity")
POWER_GATES = frozenset(k for k, v in GATE_CLASSIFICATION.items() if v == "power")


def classify_gates(stages):
    result = {"validity": {"passed": [], "failed": []}, "power": {"passed": [], "failed": []}}
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


def validity_all_pass(stages):
    for gate in VALIDITY_GATES:
        gate_result = stages.get(gate)
        if not isinstance(gate_result, dict) or gate_result.get("passed") is not True:
            return False
    return True


def power_deficiencies(stages):
    failed = []
    for gate in POWER_GATES:
        gate_result = stages.get(gate)
        if not isinstance(gate_result, dict) or gate_result.get("passed") is not True:
            failed.append(gate)
    return failed


def historical_certificate_status(cert):
    stages = cert.get("gates", {})
    return {
        "validity_pass": validity_all_pass(stages),
        "power_deficiencies": power_deficiencies(stages),
        "validity_passed": [g for g in VALIDITY_GATES if stages.get(g, {}).get("passed")],
        "validity_failed": [g for g in VALIDITY_GATES if not stages.get(g, {}).get("passed")],
        "power_passed": [g for g in POWER_GATES if stages.get(g, {}).get("passed")],
        "power_failed": power_deficiencies(stages),
    }